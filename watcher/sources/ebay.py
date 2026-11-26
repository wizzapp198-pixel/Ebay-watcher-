"""eBay-Adapter über die offizielle Browse API (item_summary/search).

Doku: https://developer.ebay.com/api-docs/buy/browse/resources/item_summary/methods/search
Filter: https://developer.ebay.com/api-docs/buy/static/ref-buy-browse-filters.html
"""
from __future__ import annotations

import base64
import logging
import time

import requests

from ..http import SourceBlocked, SourceError
from ..models import Item, Seller, Watch
from .base import Source

log = logging.getLogger(__name__)

API = "https://api.ebay.com"
TOKEN_URL = API + "/identity/v1/oauth2/token"
SEARCH_URL = API + "/buy/browse/v1/item_summary/search"
SCOPE = "https://api.ebay.com/oauth/api_scope"

CONDITION_IDS = {
    "neu": "1000",
    # Gebraucht-Varianten (inkl. "Wie neu"/"Sehr gut"/"Gut"/"Akzeptabel")
    "gebraucht": "2750|2990|3000|3010|4000|5000|6000",
}
BUYING = {"sofort": "FIXED_PRICE", "auktion": "AUCTION"}


def build_filter(watch: Watch, item_location_country: str | None, delivery_country: str | None) -> str:
    parts = []
    if watch.min_price is not None or watch.max_price is not None:
        lo = "" if watch.min_price is None else f"{watch.min_price:g}"
        hi = "" if watch.max_price is None else f"{watch.max_price:g}"
        rng = f"[{lo}..{hi}]" if hi else f"[{lo}]"
        parts += [f"price:{rng}", "priceCurrency:EUR"]
    if watch.buying in BUYING:
        parts.append(f"buyingOptions:{{{BUYING[watch.buying]}}}")
    if watch.condition in CONDITION_IDS:
        parts.append(f"conditionIds:{{{CONDITION_IDS[watch.condition]}}}")
    if item_location_country:
        parts.append(f"itemLocationCountry:{item_location_country}")
    if delivery_country:
        parts.append(f"deliveryCountry:{delivery_country}")
    return ",".join(parts)


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def parse_summary(s: dict) -> Item:
    price = s.get("price") or {}
    if "AUCTION" in (s.get("buyingOptions") or []) and s.get("currentBidPrice"):
        price = s["currentBidPrice"]
    loc = s.get("itemLocation") or {}
    seller = s.get("seller") or {}
    loc_txt = " ".join(x for x in [loc.get("postalCode"), loc.get("city")] if x) or None
    return Item(
        id=str(s.get("itemId") or s.get("legacyItemId")),
        source="ebay",
        title=s.get("title") or "",
        url=s.get("itemWebUrl") or s.get("itemAffiliateWebUrl") or "",
        price=_f(price.get("value")),
        currency=price.get("currency") or "EUR",
        image=(s.get("image") or {}).get("imageUrl")
        or ((s.get("thumbnailImages") or [{}])[0].get("imageUrl")),
        location=(loc_txt + f" ({loc['country']})" if loc_txt and loc.get("country") else loc_txt or loc.get("country")),
        country=loc.get("country"),
        condition=s.get("condition"),
        description=s.get("shortDescription"),
        buying_options=list(s.get("buyingOptions") or []),
        shipping=True if s.get("shippingOptions") else None,
        seller=Seller(
            name=seller.get("username"),
            feedback_percent=_f(seller.get("feedbackPercentage")),
            feedback_score=int(seller["feedbackScore"]) if seller.get("feedbackScore") is not None else None,
        ),
        details_loaded=True,
    )


class EbaySource(Source):
    name = "ebay"
    label = "eBay"

    def __init__(self, settings, session: requests.Session | None = None):
        super().__init__(settings)
        self.http = session or requests.Session()
        self._token = None
        self._token_exp = 0.0
        self.calls = 0

    def configured(self):
        if not (self.settings.ebay_client_id and self.settings.ebay_client_secret):
            return False, "EBAY_CLIENT_ID/EBAY_CLIENT_SECRET fehlen"
        return True, ""

    def _get_token(self) -> str:
        if self._token and time.time() < self._token_exp - 60:
            return self._token
        cred = f"{self.settings.ebay_client_id}:{self.settings.ebay_client_secret}"
        auth = base64.b64encode(cred.encode()).decode()
        try:
            r = self.http.post(
                TOKEN_URL,
                headers={"Authorization": f"Basic {auth}",
                         "Content-Type": "application/x-www-form-urlencoded"},
                data={"grant_type": "client_credentials", "scope": SCOPE},
                timeout=20,
            )
        except requests.RequestException as e:
            raise SourceError(f"eBay-Token: {e}") from e
        if r.status_code != 200:
            raise SourceError(f"eBay-Token HTTP {r.status_code}: {r.text[:200]}")
        js = r.json()
        self._token = js["access_token"]
        self._token_exp = time.time() + int(js.get("expires_in", 7200))
        return self._token

    def search(self, watch: Watch) -> list[Item]:
        params = {
            "q": watch.query,
            "sort": "newlyListed",
            "limit": str(self.settings.source_opt("ebay", "limit", 50)),
        }
        flt = build_filter(
            watch,
            self.settings.source_opt("ebay", "item_location_country", "DE"),
            self.settings.source_opt("ebay", "delivery_country", "DE"),
        )
        if flt:
            params["filter"] = flt
        last = None
        for attempt in range(3):
            headers = {
                "Authorization": f"Bearer {self._get_token()}",
                "X-EBAY-C-MARKETPLACE-ID": "EBAY_DE",
                "Accept-Language": "de-DE",
            }
            try:
                self.calls += 1
                r = self.http.get(SEARCH_URL, params=params, headers=headers, timeout=20)
            except requests.RequestException as e:
                last = SourceError(f"eBay: {e}")
            else:
                if r.status_code == 200:
                    return [parse_summary(s) for s in (r.json().get("itemSummaries") or [])]
                if r.status_code == 401:
                    self._token = None
                    last = SourceError("eBay HTTP 401")
                elif r.status_code == 429:
                    raise SourceBlocked("eBay: Tageslimit/Rate-Limit erreicht (HTTP 429)")
                elif r.status_code >= 500:
                    last = SourceError(f"eBay HTTP {r.status_code}")
                else:
                    raise SourceError(f"eBay HTTP {r.status_code}: {r.text[:300]}")
            time.sleep(2 * (attempt + 1))
        raise last or SourceError("eBay: unbekannter Fehler")
