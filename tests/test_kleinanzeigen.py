from conftest import FIX
from watcher.http import SourceBlocked
from watcher.models import Item, Watch
from watcher.sources.kleinanzeigen import (_check_block, build_search_url, parse_details,
                                           parse_price, parse_search)
import pytest


def test_parse_search_fixture():
    items = parse_search((FIX / "ka_search.html").read_text(encoding="utf-8"))
    assert len(items) == 25
    first = items[0]
    assert first.id == "3582829736"
    assert first.url.startswith("https://www.kleinanzeigen.de/s-anzeige/")
    assert "iPhone 13 Pro" in first.title
    assert first.image.startswith("https://img.kleinanzeigen.de/")
    assert all(i.source == "kleinanzeigen" for i in items)
    assert sum(1 for i in items if i.price is not None) >= 20
    assert any(i.shipping for i in items) and any(i.secure_payment for i in items)
    assert any(i.location and i.location[:5].isdigit() for i in items)


def test_parse_price():
    assert parse_price("1.250 € VB") == (1250.0, True)
    assert parse_price("99,50 €") == (99.5, False)
    assert parse_price("VB") == (None, True)
    assert parse_price("Zu verschenken") == (0.0, False)


def test_parse_details_fixture():
    it = Item(id="3582829736", source="kleinanzeigen", title="t", url="u")
    it = parse_details((FIX / "ka_ad.html").read_text(encoding="utf-8"), it)
    s = it.seller
    assert s.active_since == "14.11.2026"
    assert "TOP Zufriedenheit" in s.badges and "Zuverlässig" in s.badges
    assert s.commercial is False and s.other_ads == 2 and s.id == "168301492"
    assert it.condition == "Sehr Gut"
    assert "Akkukappazität" in it.description


def test_search_url():
    u = build_search_url(Watch(name="a", query="iphone 13", plz="06773", radius=50, min_price=100, max_price=600))
    assert "keywords=iphone+13" in u and "locationStr=06773" in u and "radius=50" in u
    assert "sortingField=SORTING_DATE" in u and "minPrice=100" in u and "maxPrice=600" in u


def test_block_detection():
    with pytest.raises(SourceBlocked):
        _check_block("<html><body>Bitte lösen Sie das Captcha</body></html>", 200)
    _check_block((FIX / "ka_search.html").read_text(encoding="utf-8"), 200)


def test_ip_block_page_detected():
    html = "<html><body><div id='error'><h1>IP-Bereich vor&uuml;bergehend gesperrt.</h1></div></body></html>"
    with pytest.raises(SourceBlocked):
        _check_block(html, 200)


def test_http_403_raises_blocked():
    from watcher.http import PoliteSession

    class R:
        status_code = 403
        text = "<h1>IP-Bereich vor&uuml;bergehend gesperrt.</h1>"

    ps = PoliteSession(sleep=lambda *_: None)
    ps.s.get = lambda *a, **k: R()
    with pytest.raises(SourceBlocked, match="gesperrt"):
        ps.get("https://www.kleinanzeigen.de/s-suchanfrage.html?x=1")
