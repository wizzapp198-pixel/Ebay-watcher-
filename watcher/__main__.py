"""CLI: python -m watcher [--once | --loop] [--test-push] [--dry-run]"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from pathlib import Path

from .config import ROOT, load_dotenv, load_settings, load_watches
from .notify import Notifier, PushError
from .runner import Runner
from .store import Store

EBAY_DAILY_LIMIT = 5000


def ebay_budget_check(watches, interval_s: int) -> str:
    n = sum(1 for w in watches if w.active and "ebay" in w.sources)
    per_day = n * (86400 // max(interval_s, 60))
    status = "OK" if per_day < EBAY_DAILY_LIMIT * 0.8 else "ZU HOCH"
    return f"eBay-Aufrufe/Tag ≈ {per_day} bei {n} eBay-Suchaufträgen (Limit ~{EBAY_DAILY_LIMIT}) → {status}"


def export_found(found: list, path: str) -> None:
    """Im Actions-Lauf: nur die neuen Funde (der Workflow führt sie zusammen).
    Lokal/Dauerbetrieb: direkt in found.json einsortieren."""
    import json
    from .found import merge_files
    p = Path(path)
    if p.name == "new_found.json":
        old = json.loads(p.read_text(encoding="utf-8")) if p.exists() else []
        p.write_text(json.dumps(old + found, ensure_ascii=False), encoding="utf-8")
    else:
        tmp = p.with_suffix(".new.json")
        tmp.write_text(json.dumps(found, ensure_ascii=False), encoding="utf-8")
        merge_files(tmp, p)
        tmp.unlink()


def probe(settings) -> int:
    from .models import Watch
    from .sources import REGISTRY
    w = Watch(name="Probe", query=os.environ.get("PROBE_QUERY", "fahrrad"),
              max_price=float(os.environ["PROBE_MAX"]) if os.environ.get("PROBE_MAX") else None)
    for name, cls in REGISTRY.items():
        if not settings.source_enabled(name):
            logging.info("PROBE %s: abgeschaltet", name)
            continue
        src = cls(settings)
        ok, why = src.configured()
        if not ok:
            logging.info("PROBE %s: nicht konfiguriert (%s)", name, why)
            continue
        try:
            items = src.search(w)
            logging.info("PROBE %s: OK, %d Treffer, z. B. %s", name, len(items),
                         items[0].title[:60] if items else "-")
        except Exception as e:  # noqa: BLE001
            logging.error("PROBE %s: FEHLER %s", name, e)
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="watcher")
    ap.add_argument("--once", action="store_true", help="ein Durchlauf (Standard)")
    ap.add_argument("--loop", action="store_true", help="Dauerbetrieb")
    ap.add_argument("--interval", type=int, help="Sekunden zwischen Läufen im Dauerbetrieb")
    ap.add_argument("--test-push", action="store_true", help="Test-Nachricht senden")
    ap.add_argument("--probe", action="store_true",
                    help="Diagnose: je eine Testsuche pro Quelle, nichts pushen/speichern")
    ap.add_argument("--sources", help="nur diese Quellen, z. B. kleinanzeigen (Komma-getrennt)")
    ap.add_argument("--found-out", default=os.environ.get("FOUND_OUT", str(ROOT / "found.json")),
                    help="Datei für gefundene Angebote (Apps lesen sie)")
    ap.add_argument("--config", default=str(ROOT / "config.yaml"))
    ap.add_argument("--watches", default=str(ROOT / "watches.yaml"))
    ap.add_argument("--schedule-interval", type=int, default=None,
                    help="tatsächliches Aufruf-Intervall (für die eBay-Limit-Rechnung)")
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    load_dotenv(ROOT / ".env")
    settings = load_settings(Path(args.config))
    if args.sources:
        wanted = {x.strip().lower() for x in args.sources.split(",")}
        for name in ("ebay", "kleinanzeigen"):
            if name not in wanted:
                settings.sources.setdefault(name, {})["enabled"] = False
    notifier = Notifier(settings.ntfy_server, settings.ntfy_topic, settings.ntfy_token)

    if args.test_push:
        try:
            notifier.send("✅ Watcher-Test: Push funktioniert",
                          "Wenn du das liest, ist ntfy richtig eingerichtet. Umlaute: äöüß €",
                          priority=3, tags=["white_check_mark"])
            logging.info("Test-Push gesendet")
        except PushError as e:
            logging.error("Test-Push fehlgeschlagen: %s", e)
            return 2

    if args.probe:
        return probe(settings)

    interval = args.interval or settings.loop_interval
    store = Store(settings.db_path)
    try:
        while True:
            watches = load_watches(Path(args.watches))
            logging.info("%d Suchaufträge geladen. %s", len(watches),
                         ebay_budget_check(watches, args.schedule_interval or interval))
            runner = Runner(settings, store, notifier)
            st = runner.run(watches)
            logging.info("Fertig: %d gepusht, %d Erstlauf gemerkt, %d aussortiert (davon %d durch KI, "
                         "%d KI-Prüfungen), %d Push-Fehler, Fehler: %s",
                         st.pushed, st.baseline, st.skipped, st.ai_rejected, st.ai_checks,
                         st.failed_push, st.errors or "keine")
            if st.found:
                export_found(st.found, args.found_out)
            if not args.loop:
                break
            time.sleep(interval)
    finally:
        store.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
