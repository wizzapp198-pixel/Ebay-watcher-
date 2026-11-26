"""Einheitliche Datentypen: Item (Angebot) und Watch (Suchauftrag)."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict
from typing import Optional

SOURCE_LABELS = {"ebay": "eBay", "kleinanzeigen": "Kleinanzeigen"}


@dataclass
class Seller:
    name: Optional[str] = None
    id: Optional[str] = None
    # eBay
    feedback_percent: Optional[float] = None
    feedback_score: Optional[int] = None
    # Kleinanzeigen
    active_since: Optional[str] = None  # "TT.MM.JJJJ"
    badges: list[str] = field(default_factory=list)
    commercial: Optional[bool] = None
    other_ads: Optional[int] = None


@dataclass
class Item:
    id: str
    source: str
    title: str
    url: str
    price: Optional[float] = None
    currency: str = "EUR"
    image: Optional[str] = None
    location: Optional[str] = None
    country: Optional[str] = None
    condition: Optional[str] = None
    description: Optional[str] = None
    buying_options: list[str] = field(default_factory=list)  # eBay: FIXED_PRICE/AUCTION/...
    shipping: Optional[bool] = None       # Versand möglich
    secure_payment: Optional[bool] = None  # Kleinanzeigen "Direkt kaufen"/Sicher bezahlen
    price_negotiable: bool = False
    seller: Seller = field(default_factory=Seller)
    details_loaded: bool = False

    @property
    def key(self) -> str:
        return f"{self.source}:{self.id}"

    @property
    def is_auction(self) -> bool:
        return "AUCTION" in self.buying_options and "FIXED_PRICE" not in self.buying_options

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Watch:
    name: str
    query: str
    sources: list[str] = field(default_factory=lambda: ["ebay", "kleinanzeigen"])
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    condition: str = "egal"          # egal | neu | gebraucht
    buying: str = "egal"             # egal | sofort | auktion (nur eBay)
    plz: Optional[str] = None        # Kleinanzeigen-Umkreis
    radius: Optional[int] = None     # km
    shipping_only: bool = False      # Kleinanzeigen: nur "Versand möglich"
    exclude: list[str] = field(default_factory=list)
    ref_price: Optional[float] = None
    min_trust: Optional[int] = None
    send_suspicious: Optional[bool] = None
    active: bool = True

    def search_key(self, source: str) -> str:
        """Fingerabdruck der Suchparameter je Quelle. Ändert sich der Suchbegriff
        o. Ä., gibt es einen neuen Schlüssel -> stiller Erstlauf (kein Push-Spam)."""
        relevant = {
            "q": self.query.strip().lower(),
            "min": self.min_price, "max": self.max_price,
            "cond": self.condition,
        }
        if source == "ebay":
            relevant["buy"] = self.buying
        if source == "kleinanzeigen":
            relevant.update(plz=self.plz, r=self.radius, ship=self.shipping_only)
        raw = json.dumps(relevant, sort_keys=True)
        return f"{source}:{hashlib.sha1(raw.encode()).hexdigest()[:16]}"
