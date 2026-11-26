"""Verarbeitet ein Issue-Formular und schreibt watches.yaml + WATCHES.md.

Eingabe über Umgebungsvariablen ISSUE_TITLE und ISSUE_BODY (nie per Shell-Interpolation).
Ausgabe: Bestätigungstext auf stdout (wird als Issue-Kommentar gepostet).
Exit 1 bei ungültiger Eingabe.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from watcher.config import parse_watch  # noqa: E402

WATCHES = ROOT / "watches.yaml"
LISTING = ROOT / "WATCHES.md"
EMPTY = {"", "_no response_", "none"}

LABELS = {
    "Name des Suchauftrags": "name",
    "Suchbegriff": "query",
    "Quellen": "sources",
    "Mindestpreis (€)": "min_price",
    "Höchstpreis (€)": "max_price",
    "Referenzpreis (€)": "ref_price",
    "Zustand": "condition",
    "Kaufart (nur eBay)": "buying",
    "PLZ (nur Kleinanzeigen)": "plz",
    "Umkreis (nur Kleinanzeigen)": "radius",
    "Versand": "shipping",
    "Ausschlusswörter": "exclude",
    "Mindest-Vertrauen": "min_trust",
    "Optionen": "options",
}


class InputError(ValueError):
    pass


def parse_sections(body: str) -> dict[str, str]:
    out, cur, buf = {}, None, []
    for line in (body or "").replace("\r\n", "\n").split("\n"):
        m = re.match(r"^###\s+(.*?)\s*$", line)
        if m:
            if cur:
                out[cur] = "\n".join(buf).strip()
            cur, buf = m.group(1), []
        else:
            buf.append(line)
    if cur:
        out[cur] = "\n".join(buf).strip()
    return {LABELS.get(k, k): v for k, v in out.items()}


def checked(text: str) -> list[str]:
    return [m.group(1).strip() for m in re.finditer(r"- \[[xX]\]\s*(.+)", text or "")]


def val(v: str | None) -> str | None:
    if v is None or v.strip().lower() in EMPTY:
        return None
    return v.strip()


def num(v: str | None, field: str) -> float | None:
    v = val(v)
    if v is None:
        return None
    v = v.replace("€", "").replace(" ", "")
    if re.fullmatch(r"\d{1,3}(\.\d{3})+(,\d+)?", v):
        v = v.replace(".", "")
    v = v.replace(",", ".")
    try:
        f = float(v)
    except ValueError:
        raise InputError(f"„{field}“ ist keine Zahl: {v}")
    if f < 0:
        raise InputError(f"„{field}“ darf nicht negativ sein")
    return f


def form_to_watch(sec: dict) -> dict:
    name = val(sec.get("name"))
    query = val(sec.get("query"))
    if not name or not query:
        raise InputError("Name und Suchbegriff sind Pflicht.")
    srcs = []
    for c in checked(sec.get("sources", "")):
        if c.lower() == "ebay":
            srcs.append("ebay")
        elif c.lower().startswith("kleinanzeigen"):
            srcs.append("kleinanzeigen")
    if not srcs:
        srcs = ["ebay", "kleinanzeigen"]
    w = {"name": name[:60], "query": query[:120], "sources": srcs}
    for k, label in (("min_price", "Mindestpreis"), ("max_price", "Höchstpreis"), ("ref_price", "Referenzpreis")):
        n = num(sec.get(k), label)
        if n is not None:
            w[k] = n
    if "min_price" in w and "max_price" in w and w["min_price"] > w["max_price"]:
        raise InputError("Mindestpreis ist größer als Höchstpreis.")
    cond = (val(sec.get("condition")) or "egal").lower()
    w["condition"] = cond if cond in ("neu", "gebraucht") else "egal"
    buy = (val(sec.get("buying")) or "egal").lower()
    w["buying"] = "sofort" if buy.startswith("sofort") else "auktion" if buy.startswith("auktion") else "egal"
    plz = val(sec.get("plz"))
    if plz:
        if not re.fullmatch(r"\d{5}", plz):
            raise InputError(f"PLZ muss 5 Ziffern haben: {plz}")
        w["plz"] = plz
        m = re.match(r"(\d+)", val(sec.get("radius")) or "")
        if m:
            w["radius"] = int(m.group(1))
    if checked(sec.get("shipping", "")):
        w["shipping_only"] = True
    excl = val(sec.get("exclude"))
    if excl:
        w["exclude"] = [e.strip().lower() for e in excl.split(",") if e.strip()][:30]
    mt = val(sec.get("min_trust"))
    if mt and re.fullmatch(r"\d+", mt):
        w["min_trust"] = int(mt)
    opts = [o.lower() for o in checked(sec.get("options", ""))]
    if any("verdächtig" in o for o in opts):
        w["send_suspicious"] = True
    w["active"] = not any("pausieren" in o for o in opts)
    parse_watch(w)  # Validierung
    return w


def load() -> list[dict]:
    if not WATCHES.exists():
        return []
    return (yaml.safe_load(WATCHES.read_text(encoding="utf-8")) or {}).get("watches") or []


def save(watches: list[dict]) -> None:
    header = ("# Wird automatisch über das Issue-Formular \"Suchauftrag anlegen/ändern\" gepflegt.\n"
              "# Nicht von Hand bearbeiten nötig.\n")
    WATCHES.write_text(header + yaml.safe_dump({"watches": watches}, allow_unicode=True, sort_keys=False),
                       encoding="utf-8")
    LISTING.write_text(render_listing(watches), encoding="utf-8")


def _eur(v):
    return "–" if v is None else f"{v:g} €"


def render_listing(watches: list[dict]) -> str:
    lines = ["# Aktuelle Suchaufträge", "",
             "_Automatisch erzeugt. Ändern/Anlegen/Löschen über **Issues → New issue**._", ""]
    if not watches:
        lines.append("Noch keine Suchaufträge.")
    for w in watches:
        status = "⏸️ pausiert" if not w.get("active", True) else "▶️ aktiv"
        src = " + ".join({"ebay": "eBay", "kleinanzeigen": "Kleinanzeigen"}[s] for s in w["sources"])
        lines.append(f"## {w['name']} ({status})")
        lines.append(f"- Suche: `{w['query']}` · Quellen: {src}")
        lines.append(f"- Preis: {_eur(w.get('min_price'))} bis {_eur(w.get('max_price'))} · Ref.: {_eur(w.get('ref_price'))}")
        extra = [f"Zustand {w.get('condition', 'egal')}"]
        if "ebay" in w["sources"]:
            extra.append(f"eBay-Kaufart {w.get('buying', 'egal')}")
        if "kleinanzeigen" in w["sources"]:
            extra.append(f"KA: {w['plz']} +{w.get('radius', 0)} km" if w.get("plz") else "KA: deutschlandweit")
            if w.get("shipping_only"):
                extra.append("nur Versand")
        if w.get("min_trust") is not None:
            extra.append(f"min. Vertrauen {w['min_trust']}")
        if w.get("send_suspicious"):
            extra.append("⚠️ verdächtige senden")
        lines.append("- " + " · ".join(extra))
        if w.get("exclude"):
            lines.append("- Ausschluss: " + ", ".join(w["exclude"]))
        lines.append("")
    return "\n".join(lines) + "\n"


def handle(title: str, body: str) -> str:
    sec = parse_sections(body)
    watches = load()
    if title.strip().startswith("[Löschen]"):
        name = val(sec.get("name"))
        if not name:
            raise InputError("Name fehlt.")
        rest = [w for w in watches if w["name"].lower() != name.lower()]
        if len(rest) == len(watches):
            raise InputError(f"Kein Suchauftrag „{name}“ gefunden. Namen stehen in WATCHES.md.")
        save(rest)
        return f"🗑️ Suchauftrag **{name}** gelöscht. Noch {len(rest)} aktiv/gespeichert."
    w = form_to_watch(sec)
    for i, old in enumerate(watches):
        if old["name"].lower() == w["name"].lower():
            watches[i] = w
            action = "geändert"
            break
    else:
        watches.append(w)
        action = "angelegt"
    save(watches)
    note = ("Beim ersten Lauf werden vorhandene Angebote nur gemerkt (kein Push). "
            "Danach kommen nur **neue** Angebote.")
    return (f"✅ Suchauftrag **{w['name']}** {action}.\n\n{note}\n\n"
            f"```yaml\n{yaml.safe_dump(w, allow_unicode=True, sort_keys=False)}```")


def main() -> int:
    try:
        print(handle(os.environ.get("ISSUE_TITLE", ""), os.environ.get("ISSUE_BODY", "")))
        return 0
    except InputError as e:
        print(f"❌ Nicht übernommen: {e}\n\nBitte ein neues Issue mit korrigierten Angaben anlegen.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
