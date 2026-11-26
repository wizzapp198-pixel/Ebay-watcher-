import json
import os

import pytest

from watcher.config import Settings
from watcher.models import Watch
from watcher.notify import Notifier, PushError, build_push
from watcher.scoring import score_item
from watcher.sources.ebay import EbaySource, build_filter, parse_summary

SUMMARY = {
    "itemId": "v1|1234|0", "title": "Apple iPhone 13 128GB Mitternacht",
    "price": {"value": "289.00", "currency": "EUR"},
    "image": {"imageUrl": "https://i.ebayimg.com/x.jpg"},
    "itemWebUrl": "https://www.ebay.de/itm/1234",
    "itemLocation": {"postalCode": "06***", "country": "DE"},
    "condition": "Gebraucht", "conditionId": "3000",
    "seller": {"username": "hans", "feedbackPercentage": "99.6", "feedbackScore": 842},
    "buyingOptions": ["FIXED_PRICE"],
}


class Resp:
    def __init__(self, code, data=None, text=""):
        self.status_code, self._d, self.text = code, data, text or json.dumps(data)

    def json(self):
        return self._d


class FakeHttp:
    def __init__(self, search_resps):
        self.search_resps = list(search_resps)
        self.gets = []
        self.posts = []

    def post(self, url, **kw):
        self.posts.append((url, kw))
        if "oauth2" in url:
            return Resp(200, {"access_token": "T", "expires_in": 7200})
        return Resp(200, {})

    def get(self, url, params=None, headers=None, **kw):
        self.gets.append((url, params, headers))
        return self.search_resps.pop(0)


def test_build_filter():
    w = Watch(name="a", query="q", min_price=100, max_price=350, buying="sofort", condition="neu")
    f = build_filter(w, "DE", "DE")
    assert "price:[100..350]" in f and "priceCurrency:EUR" in f
    assert "buyingOptions:{FIXED_PRICE}" in f and "conditionIds:{1000}" in f
    assert "itemLocationCountry:DE" in f and "deliveryCountry:DE" in f
    assert build_filter(Watch(name="a", query="q"), None, None) == ""


def test_parse_summary():
    it = parse_summary(SUMMARY)
    assert it.id == "v1|1234|0" and it.price == 289.0 and it.seller.feedback_score == 842
    assert it.seller.feedback_percent == 99.6 and it.country == "DE"


def test_ebay_search_headers_and_retry_401():
    s = Settings(); s.ebay_client_id, s.ebay_client_secret = "id", "sec"
    http = FakeHttp([Resp(401, {}), Resp(200, {"itemSummaries": [SUMMARY]})])
    src = EbaySource(s, session=http)
    import watcher.sources.ebay as e
    e.time.sleep = lambda *_: None
    items = src.search(Watch(name="a", query="iphone 13"))
    assert len(items) == 1
    url, params, headers = http.gets[-1]
    assert params["sort"] == "newlyListed" and headers["X-EBAY-C-MARKETPLACE-ID"] == "EBAY_DE"
    assert len(http.posts) == 2  # Token nach 401 erneuert


def test_notifier_json_utf8():
    http = FakeHttp([])
    n = Notifier("https://ntfy.sh/", "topic", session=http)
    n.send("Schnäppchen €", "Größe", priority=5, click="https://x", image="https://i")
    url, kw = http.posts[0]
    assert url == "https://ntfy.sh" and kw["json"]["title"] == "Schnäppchen €"
    assert kw["json"]["attach"] == "https://i" and kw["json"]["priority"] == 5


def test_notifier_error():
    class Bad(FakeHttp):
        def post(self, url, **kw):
            return Resp(500, {}, "err")
    with pytest.raises(PushError):
        Notifier("https://ntfy.sh", "t", session=Bad([])).send("a", "b")
    with pytest.raises(PushError):
        Notifier("https://ntfy.sh", None).send("a", "b")


def test_build_push_shows_source_and_reason():
    it = parse_summary(SUMMARY)
    w = Watch(name="iPhone", query="x", ref_price=300)
    p = build_push(it, w.name, score_item(it, w, 60), "normal")
    assert p["title"].startswith("[eBay] 289 €") and "Vertrauen:" in p["message"]


# --- Issue-Formular -> watches.yaml ------------------------------------
FORM = """### Name des Suchauftrags

iPhone 13

### Suchbegriff

iphone 13 128gb

### Quellen

- [X] eBay
- [X] Kleinanzeigen

### Mindestpreis (€)

100

### Höchstpreis (€)

1.200,50

### Referenzpreis (€)

_No response_

### Zustand

gebraucht

### Kaufart (nur eBay)

Sofort-Kaufen

### PLZ (nur Kleinanzeigen)

06773

### Umkreis (nur Kleinanzeigen)

50 km

### Versand

- [ ] Nur Angebote mit Versand (Kleinanzeigen)

### Ausschlusswörter

Hülle, case

### Mindest-Vertrauen

70

### Optionen

- [ ] Verdächtige Angebote trotzdem senden (⚠️)
- [ ] Suchauftrag pausieren
"""


@pytest.fixture
def manage(tmp_path, monkeypatch):
    import scripts.manage_watches as m
    monkeypatch.setattr(m, "WATCHES", tmp_path / "watches.yaml")
    monkeypatch.setattr(m, "LISTING", tmp_path / "WATCHES.md")
    monkeypatch.setattr(m, "JSON_OUT", tmp_path / "watches.json")
    return m


def test_form_add_change_delete(manage):
    out = manage.handle("[Suchauftrag] iPhone", FORM)
    assert "angelegt" in out
    w = manage.load()[0]
    assert w["max_price"] == 1200.5 and w["plz"] == "06773" and w["radius"] == 50
    assert w["buying"] == "sofort" and w["condition"] == "gebraucht" and w["min_trust"] == 70
    assert w["exclude"] == ["hülle", "case"] and "ref_price" not in w and w["active"] is True
    out = manage.handle("[Suchauftrag] x", FORM.replace("- [ ] Suchauftrag pausieren", "- [X] Suchauftrag pausieren"))
    assert "geändert" in out and manage.load()[0]["active"] is False and len(manage.load()) == 1
    assert "pausiert" in manage.LISTING.read_text(encoding="utf-8")
    assert json.loads(manage.JSON_OUT.read_text(encoding="utf-8"))["watches"][0]["active"] is False
    out = manage.handle("[Löschen] iPhone", "### Name des Suchauftrags\n\niphone 13\n")
    assert "gelöscht" in out and manage.load() == []


def test_form_invalid(manage):
    with pytest.raises(manage.InputError):
        manage.handle("[Suchauftrag]", FORM.replace("06773", "abc"))
    with pytest.raises(manage.InputError):
        manage.handle("[Löschen] y", "### Name des Suchauftrags\n\ngibtsnicht\n")
