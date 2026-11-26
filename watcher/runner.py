"""Ein Durchlauf über alle Suchaufträge und Quellen."""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field, replace

from .ai import AIChecker
from .found import entry as found_entry
from .config import Settings
from .http import SourceBlocked, SourceError
from .models import SOURCE_LABELS, Item, Watch
from .notify import Notifier, PushError, build_push
from .scoring import score_item
from .sources import REGISTRY
from .store import Store

log = logging.getLogger(__name__)


@dataclass
class RunStats:
    pushed: int = 0
    baseline: int = 0
    skipped: int = 0
    failed_push: int = 0
    errors: dict = field(default_factory=dict)
    ebay_calls: int = 0
    ai_checks: int = 0
    ai_rejected: int = 0
    found: list = field(default_factory=list)


def _has_word(text: str, words: list[str]) -> str | None:
    """Treffer am Wortanfang, z. B. 'defekt' trifft 'Defekt' und 'defekter', nicht 'perfekt'."""
    t = (text or "").lower()
    for w in words:
        w = w.strip().lower()
        if w and re.search(r"(?<!\w)" + re.escape(w), t):
            return w
    return None


def prefilter(item: Item, watch: Watch, settings: Settings) -> str | None:
    """Gibt einen Grund zurück, wenn das Angebot ausgeschlossen wird."""
    hit = _has_word(item.title, settings.exclude + watch.exclude)
    if hit:
        return f"Ausschlusswort '{hit}'"
    if item.price is not None:
        if watch.min_price is not None and item.price < watch.min_price and not item.is_auction:
            return "unter min_price"
        if watch.max_price is not None and item.price > watch.max_price:
            return "über max_price"
    elif watch.min_price is not None or watch.max_price is not None:
        return "kein Preis"
    return None


ACCESSORY_TYPES = ("zubehör", "ersatzteil", "ersatzteile", "teile", "zubehör & ersatzteile")


def accessory_mismatch(item: Item, watch: Watch) -> str | None:
    """Kleinanzeigen-Angabe "Art: Zubehör/Ersatzteile", obwohl nicht nach Zubehör gesucht wird."""
    q = watch.query.lower() + " " + (watch.ai_hint or "").lower()
    if any(w in q for w in ("zubehör", "ersatzteil", "teile", "reifen", "tasche")):
        return None
    for key in ("Art", "Typ"):
        v = (item.attributes.get(key) or "").strip().lower()
        if v in ACCESSORY_TYPES:
            return f"{key}: {item.attributes[key]}"
    return None


def condition_ok(item: Item, watch: Watch) -> bool:
    if watch.condition == "egal" or not item.condition:
        return True
    c = item.condition.lower()
    is_new = c.startswith("neu") or c == "new" or "brand new" in c
    return is_new if watch.condition == "neu" else not is_new


class Runner:
    def __init__(self, settings: Settings, store: Store, notifier: Notifier, sources: dict | None = None,
                 ai: AIChecker | None = None):
        self.settings = settings
        self.ai = ai if ai is not None else AIChecker(settings)
        self.store = store
        self.notifier = notifier
        if sources is None:
            sources = {}
            for name, cls in REGISTRY.items():
                if settings.source_enabled(name):
                    sources[name] = cls(settings)
        self.sources = sources

    # ---------------------------------------------------------------------
    def _warn_source(self, name: str, err: Exception) -> None:
        key = f"warn:{name}"
        last = float(self.store.get_meta(key) or 0)
        if time.time() - last < self.settings.warn_interval_minutes * 60:
            return
        label = SOURCE_LABELS.get(name, name)
        blocked = isinstance(err, SourceBlocked)
        msg = f"{label} {'blockiert den Zugriff' if blocked else 'ist gerade nicht erreichbar'}: {err}\n" \
              f"Andere Quellen laufen weiter."
        try:
            self.notifier.send(f"⚠️ Watcher: {label} gestört", msg, priority=2, tags=["warning"])
            self.store.set_meta(key, time.time())
        except PushError as e:
            log.error("Warn-Push fehlgeschlagen: %s", e)

    def run(self, watches: list[Watch]) -> RunStats:
        st = RunStats()
        budget = self.settings.max_pushes_per_run
        for name, src in self.sources.items():
            ok, why = src.configured()
            if not ok:
                log.warning("Quelle %s übersprungen: %s", name, why)
                st.errors[name] = why
                continue
            for watch in watches:
                if not watch.active or name not in watch.sources:
                    continue
                try:
                    budget = self._run_one(src, watch, st, budget)
                except (SourceError, SourceBlocked) as e:
                    log.error("%s / %s: %s", name, watch.name, e)
                    st.errors[name] = str(e)
                    self._warn_source(name, e)
                    break  # diese Quelle für diesen Lauf aufgeben, andere laufen weiter
                except Exception as e:  # Parserfehler o. Ä. -> nicht alles abbrechen
                    log.exception("%s / %s: unerwarteter Fehler", name, watch.name)
                    st.errors[name] = repr(e)
                    self._warn_source(name, e)
                    break
            st.ebay_calls += getattr(src, "calls", 0)
        st.ai_checks = self.ai.checks
        self.store.prune()
        return st

    @staticmethod
    def _search_all(src, watch: Watch) -> list[Item]:
        """Komma im Suchbegriff = mehrere Suchen (ODER), Ergebnisse ohne Doppelte."""
        queries = list(dict.fromkeys(q.strip().lower() for q in watch.query.split(",") if q.strip()))
        if len(queries) <= 1:
            return src.search(watch)
        merged: dict[str, Item] = {}
        for q in queries:
            for it in src.search(replace(watch, query=q)):
                merged.setdefault(it.key, it)
        return list(merged.values())

    def _run_one(self, src, watch: Watch, st: RunStats, budget: int) -> int:
        skey = watch.search_key(src.name)
        items = self._search_all(src, watch)
        log.info("%s / %s: %d Treffer", src.name, watch.name, len(items))

        if not self.store.has_baseline(skey):
            for it in items:
                self.store.mark_seen(it.key, it.title)
            self.store.set_baseline(skey, watch.name)
            st.baseline += len(items)
            log.info("Erstlauf %s / %s: %d Angebote gemerkt, nichts gepusht", src.name, watch.name, len(items))
            return budget

        min_trust = watch.min_trust if watch.min_trust is not None else self.settings.min_trust
        send_susp = watch.send_suspicious if watch.send_suspicious is not None else self.settings.send_suspicious

        for it in items:
            if self.store.is_seen(it.key):
                continue
            reason = prefilter(it, watch, self.settings)
            if reason:
                log.info("  - %s: %s", it.title[:60], reason)
                self.store.mark_seen(it.key, it.title)
                st.skipped += 1
                continue
            if budget <= 0:
                log.info("Push-Limit pro Lauf erreicht, Rest folgt im nächsten Lauf")
                return budget
            if not it.details_loaded:
                try:
                    it = src.details(it)
                except SourceBlocked:
                    raise
                except SourceError as e:
                    log.warning("Details nicht ladbar (%s): %s", it.url, e)
            if not condition_ok(it, watch):
                self.store.mark_seen(it.key, it.title)
                st.skipped += 1
                continue
            acc = accessory_mismatch(it, watch)
            if acc:
                log.info("  - %s: Zubehör/Ersatzteil (%s)", it.title[:60], acc)
                self.store.mark_seen(it.key, it.title)
                st.skipped += 1
                continue
            if it.offer_type and it.offer_type.lower() != "angebot":
                log.info("  - %s: kein Angebot (%s)", it.title[:60], it.offer_type)
                self.store.mark_seen(it.key, it.title)
                st.skipped += 1
                continue
            verdict = self.ai.check(it, watch)
            if verdict is not None and not verdict.ok:
                log.info("  - %s: KI aussortiert – %s", it.title[:60], verdict.reason)
                self.store.mark_seen(it.key, it.title)
                st.skipped += 1
                st.ai_rejected += 1
                continue
            sc = score_item(it, watch, min_trust)
            if verdict is not None:
                sc.reasons.insert(0, f"KI ✓ {verdict.reason}")
            kind = "normal"
            if sc.value < min_trust:
                if not send_susp:
                    log.info("  - %s: Score %d < %d (%s)", it.title[:60], sc.value, min_trust, sc.text())
                    self.store.mark_seen(it.key, it.title)
                    st.skipped += 1
                    continue
                kind = "suspicious"
            elif sc.price_ratio is not None and sc.price_ratio <= 1 - self.settings.bargain_percent / 100:
                kind = "bargain"
            push = build_push(it, watch.name, sc, kind)
            try:
                self.notifier.send(**push)
            except PushError as e:
                log.error("Push fehlgeschlagen, Angebot bleibt ungesehen: %s", e)
                st.failed_push += 1
                continue
            self.store.mark_seen(it.key, it.title)
            st.found.append(found_entry(it, watch.name, sc, kind))
            st.pushed += 1
            budget -= 1
        return budget
