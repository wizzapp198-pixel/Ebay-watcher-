"""Kleinanzeigen-Adapter: wertet öffentliche Suchergebnisseiten aus (keine offizielle API).

- nur öffentliche Seiten, kein Login
- höfliches Rate-Limit (min. 4 s + Zufall zwischen Anfragen), Retry mit Backoff
- bei 403/429/Captcha wird abgebrochen (SourceBlocked) – keine Umgehung
"""
from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime
from urllib.parse import urlencode

from bs4 import BeautifulSoup

from ..http import PoliteSession, SourceBlocked
from ..models import Item, Seller, Watch
from .base import Source

log = logging.getLogger(__name__)

BASE = "https://www.kleinanzeigen.de"
SEARCH = BASE + "/s-suchanfrage.html"
KNOWN_BADGES = ("TOP Zufriedenheit", "OK Zufriedenheit", "Sehr zuverlässig", "Zuverlässig",
                "Besonders freundlich", "Freundlich", "Sehr freundlich")
BLOCK_MARKERS = ("vor&uuml;bergehend gesperrt", "vorübergehend gesperrt", "captcha", "Zugriff verweigert", "Access Denied", "ungewöhnlich viele Anfragen")


def build_search_url(watch: Watch) -> str:
    p = {"keywords": watch.query, "sortingField": "SORTING_DATE"}
    if watch.plz:
        p["locationStr"] = watch.plz
        if watch.radius:
            p["radius"] = str(watch.radius)
    if watch.min_price is not None:
        p["minPrice"] = f"{watch.min_price:.0f}"
    if watch.max_price is not None:
        p["maxPrice"] = f"{watch.max_price:.0f}"
    return SEARCH + "?" + urlencode(p)


PRICE_RE = re.compile(r"(\d{1,3}(?:\.\d{3})*|\d+)(?:,(\d{1,2}))?\s*€")


def parse_price(text: str) -> tuple[float | None, bool]:
    text = (text or "").strip()
    vb = "VB" in text
    if "verschenken" in text.lower():
        return 0.0, False
    m = PRICE_RE.search(text)
    if not m:
        return None, vb
    whole = m.group(1).replace(".", "")
    cents = m.group(2) or "0"
    return float(f"{whole}.{cents}"), vb


def _check_block(html: str, status: int):
    low = html[:20000].lower()
    if any(mk.lower() in low for mk in BLOCK_MARKERS) and "srchrslt" not in low and "viewad" not in low:
        raise SourceBlocked(f"Kleinanzeigen: Sperr-/Captcha-Seite erkannt (HTTP {status})")


def parse_search(html: str) -> list[Item]:
    soup = BeautifulSoup(html, "html.parser")
    container = soup.select_one("#srchrslt-adtable") or soup
    items = []
    for art in container.select("article[data-adid]"):
        ad_id = art.get("data-adid")
        href = art.get("data-href") or ""
        ld = {}
        script = art.find("script", type="application/ld+json")
        if script and script.string:
            try:
                ld = json.loads(script.string)
            except ValueError:
                ld = {}
        h = art.find(["h2", "h3"])
        title = (h.get_text(" ", strip=True) if h else "") or ld.get("title") or ld.get("name") or ""
        loc = None
        svg = art.find("svg", attrs={"data-title": "locationOutline"})
        if svg and svg.parent:
            sp = svg.parent.find("span")
            loc = sp.get_text(" ", strip=True) if sp else None
        price, vb = None, False
        for p in art.find_all("p"):
            cls = " ".join(p.get("class") or [])
            if "line-through" in cls:
                continue
            t = p.get_text(" ", strip=True)
            if re.search(r"€|VB$|verschenken", t) and len(t) < 40:
                price, vb = parse_price(t)
                break
        tags = {sp.get_text(" ", strip=True) for sp in art.find_all("span")}
        li_cls = " ".join((art.parent.get("class") or []) if art.parent else [])
        if "topad" in li_cls or "topad" in " ".join(art.get("class") or []):
            continue  # bezahlte Top-Anzeigen sind nicht "neu"
        img = ld.get("contentUrl")
        if not img:
            im = art.find("img")
            img = im.get("src") if im else None
        items.append(Item(
            id=str(ad_id),
            source="kleinanzeigen",
            title=title,
            url=BASE + href if href.startswith("/") else href,
            price=price,
            price_negotiable=vb,
            image=img,
            location=loc,
            country="DE",
            description=ld.get("description"),
            shipping="Versand möglich" in tags,
            secure_payment="Direkt kaufen" in tags,
        ))
    return items


def parse_details(html: str, item: Item) -> Item:
    soup = BeautifulSoup(html, "html.parser")
    desc = soup.select_one("#viewad-description-text")
    if desc:
        item.description = desc.get_text("\n", strip=True)
    for li in soup.select("#viewad-details li"):
        val = li.find("span")
        label = li.get_text(" ", strip=True).replace(val.get_text(" ", strip=True), "").strip() if val else ""
        if label.lower().startswith("zustand") and val:
            item.condition = val.get_text(" ", strip=True)
    box = soup.select_one("#viewad-profile-box") or soup.select_one("#viewad-contact")
    s = item.seller or Seller()
    if box:
        txt = box.get_text(" | ", strip=True).replace("\xa0", " ")
        name = box.select_one(".userprofile-vip a") or box.select_one(".userprofile-vip")
        if name:
            s.name = name.get_text(" ", strip=True)
        link = box.find("a", href=re.compile(r"userId=\d+"))
        if link:
            s.id = re.search(r"userId=(\d+)", link["href"]).group(1)
        tags = [" ".join(t.get_text(" ", strip=True).split()) for t in box.select(".userbadge-tag, .userbadges-profile-rating, .userbadges-profile-reliability, .userbadges-profile-friendliness")]
        s.badges = list(dict.fromkeys(t for t in tags if t)) or [
            b for b in KNOWN_BADGES if re.search(r"(^|\|\s)" + re.escape(b) + r"(\s\||$)", txt)]
        if "Gewerblich" in txt:
            s.commercial = True
        elif "Privat" in txt:
            s.commercial = False
        m = re.search(r"Aktiv seit\s*(\d{2}\.\d{2}\.\d{4})", txt)
        if m:
            s.active_since = m.group(1)
        m = re.search(r"(\d+)\s*Anzeigen? online", txt)
        if m:
            s.other_ads = int(m.group(1))
    item.seller = s
    item.details_loaded = True
    return item


def account_age_days(active_since: str | None, today: date | None = None) -> int | None:
    if not active_since:
        return None
    try:
        d = datetime.strptime(active_since, "%d.%m.%Y").date()
    except ValueError:
        return None
    return ((today or date.today()) - d).days


class KleinanzeigenSource(Source):
    name = "kleinanzeigen"
    label = "Kleinanzeigen"

    def __init__(self, settings, session: PoliteSession | None = None):
        super().__init__(settings)
        self.http = session or PoliteSession(
            min_delay=float(settings.source_opt("kleinanzeigen", "min_delay", 4)),
            jitter=float(settings.source_opt("kleinanzeigen", "jitter", 2)),
        )

    def search(self, watch: Watch) -> list[Item]:
        r = self.http.get(build_search_url(watch))
        _check_block(r.text, r.status_code)
        items = parse_search(r.text)
        if watch.shipping_only:
            items = [i for i in items if i.shipping]
        return items

    def details(self, item: Item) -> Item:
        r = self.http.get(item.url)
        _check_block(r.text, r.status_code)
        return parse_details(r.text, item)
