"""Seriositäts-Score 0-100 mit Begründungen."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from .models import Item, Watch
from .sources.kleinanzeigen import account_age_days

# Starke Betrugs-Hinweise: drücken den Score IMMER unter min_trust.
STRONG_PATTERNS = {
    "WhatsApp": r"whats\s?app",
    "Telegram": r"telegram",
    "PayPal Freunde": r"pay\s?pal[\s\-]*(an\s+)?(freunde|friends|f\s?&\s?f|ff\b)|freunde\s*(und|&)\s*familie|friends\s*(and|&)\s*family",
    "Western Union": r"western\s*union|moneygram",
    "Krypto": r"krypto|crypto|bitcoin|\bbtc\b|usdt",
    "Zahlung außerhalb": r"(au(ß|ss)erhalb|nicht\s+über)\s+(von\s+)?(ebay|kleinanzeigen|der\s+plattform)",
    "Anzahlung": r"anzahlung",
    "Treuhand": r"treuhand",
    "Kontakt per Mail": r"kontakt\s+(nur\s+)?(per|via|über|by)\s+(e-?)?mail|schreib(t|en sie)?\s+(mir\s+)?(eine\s+)?(e-?)?mail\s+an|[\w.+-]+@[\w-]+\.(de|com|net)",
}
# Weiche Hinweise: leichter Abzug.
SOFT_PATTERNS = {
    "nur Vorkasse": r"(nur\s+)?vorkasse",
    "nur Überweisung": r"nur\s+(per\s+)?überweisung",
    "Telefonnummer im Text": r"(\+49|0)1[5-7]\d[\s/-]?\d{3,}",
}

EU_NEAR = {"DE", "AT", "NL", "BE", "LU", "FR", "DK", "PL", "CZ", "CH"}


@dataclass
class Score:
    value: int
    reasons: list[str] = field(default_factory=list)
    strong_flags: list[str] = field(default_factory=list)
    price_ratio: float | None = None

    def text(self) -> str:
        return "; ".join(self.reasons)


def find_flags(text: str) -> tuple[list[str], list[str]]:
    t = (text or "").lower()
    strong = [k for k, p in STRONG_PATTERNS.items() if re.search(p, t)]
    soft = [k for k, p in SOFT_PATTERNS.items() if re.search(p, t)]
    return strong, soft


def score_item(item: Item, watch: Watch, min_trust: int, today: date | None = None) -> Score:
    pts = 70
    why: list[str] = []
    s = item.seller

    if item.source == "ebay":
        fp, fs = s.feedback_percent, s.feedback_score
        if fp is not None:
            if fp >= 99.5:
                pts += 10; why.append(f"{fp:g}% positiv")
            elif fp >= 98:
                pts += 5; why.append(f"{fp:g}% positiv")
            elif fp < 90:
                pts -= 30; why.append(f"nur {fp:g}% positiv")
            elif fp < 96:
                pts -= 15; why.append(f"nur {fp:g}% positiv")
            else:
                why.append(f"{fp:g}% positiv")
        if fs is not None:
            if fs < 5:
                pts -= 25; why.append(f"neuer Account ({fs} Bew.)")
            elif fs < 20:
                pts -= 15; why.append(f"wenige Bewertungen ({fs})")
            elif fs < 100:
                pts -= 3; why.append(f"{fs} Bewertungen")
            elif fs >= 1000:
                pts += 10; why.append(f"{fs} Bewertungen")
            else:
                pts += 5; why.append(f"{fs} Bewertungen")
        else:
            pts -= 5; why.append("Bewertungen unbekannt")
        if item.country and item.country != "DE":
            if item.country in EU_NEAR:
                pts -= 5; why.append(f"Standort {item.country}")
            else:
                pts -= 20; why.append(f"Standort {item.country} (Ausland)")

    elif item.source == "kleinanzeigen":
        if not item.details_loaded:
            pts -= 5; why.append("Profil nicht geprüft")
        age = account_age_days(s.active_since, today)
        if age is not None:
            if age < 30:
                pts -= 25; why.append(f"Account neu (seit {s.active_since})")
            elif age < 180:
                pts -= 10; why.append(f"Account jung (seit {s.active_since})")
            elif age > 3 * 365:
                pts += 10; why.append(f"aktiv seit {s.active_since}")
            else:
                pts += 3; why.append(f"aktiv seit {s.active_since}")
        for b in s.badges:
            if "TOP" in b:
                pts += 10
            elif "Zufriedenheit" in b:
                pts += 3
            else:
                pts += 5
        if s.badges:
            why.append(", ".join(s.badges))
        if s.commercial is True:
            pts += 3; why.append("gewerblich")
        elif s.commercial is False:
            why.append("privat")
        if s.other_ads is not None:
            if s.other_ads >= 5:
                pts += 3
            why.append(f"{s.other_ads} Anzeigen online")
        if item.secure_payment:
            pts += 10; why.append("Direkt kaufen/Sicher bezahlen")
        elif item.shipping:
            pts += 2; why.append("Versand möglich")

    # Preis vs. Referenzpreis (bei eBay nur Sofort-Kaufen, Auktionen sind anfangs billig)
    ratio = None
    if watch.ref_price and item.price and not (item.source == "ebay" and item.is_auction):
        ratio = item.price / watch.ref_price
        pct = round(ratio * 100)
        if ratio < 0.5:
            pts -= 40; why.append(f"⚠ Preis nur {pct}% vom Ref.-Preis")
        elif ratio < 0.7:
            pts -= 15; why.append(f"Preis {pct}% vom Ref.-Preis (auffällig)")
        else:
            why.append(f"Preis {pct}% vom Ref.-Preis")

    strong, soft = find_flags(f"{item.title}\n{item.description or ''}")
    if soft:
        pts -= 10 * len(soft); why.append("Hinweis: " + ", ".join(soft))
    if strong:
        pts -= 30
        pts = min(pts, min_trust - 1)
        why.insert(0, "🚩 " + ", ".join(strong))

    return Score(value=max(0, min(100, pts)), reasons=why, strong_flags=strong, price_ratio=ratio)
