from datetime import date

from conftest import good_ebay, good_ka
from watcher.models import Seller, Watch
from watcher.scoring import score_item

W = Watch(name="x", query="x", ref_price=300)
TODAY = date(2026, 11, 26)


def test_good_ebay_seller_high():
    s = score_item(good_ebay(1, price=280), W, 60)
    assert s.value >= 80 and "99.8% positiv" in s.text()


def test_new_ebay_account_low():
    it = good_ebay(1, price=280)
    it.seller = Seller(feedback_percent=100.0, feedback_score=1)
    s = score_item(it, W, 60)
    assert s.value < 75 and "neuer Account" in s.text()


def test_too_cheap_fixed_price_suspicious():
    s = score_item(good_ebay(1, price=120), W, 60)
    assert s.value < 60 and "40%" in s.text()


def test_auction_price_not_compared():
    it = good_ebay(1, price=20)
    it.buying_options = ["AUCTION"]
    s = score_item(it, W, 60)
    assert s.price_ratio is None and s.value >= 60


def test_foreign_location_penalty():
    it = good_ebay(1, price=280)
    it.country = "CN"
    assert score_item(it, W, 60).value < score_item(good_ebay(1, price=280), W, 60).value - 15


def test_strong_keywords_always_below_min_trust():
    it = good_ebay(1, price=290)
    it.description = "Bitte nur Western Union"
    s = score_item(it, W, 70)
    assert s.value < 70 and "Western Union" in s.strong_flags


def test_ka_new_account_vs_old():
    old = score_item(good_ka(1, price=280), W, 60, TODAY)
    new = good_ka(2, price=280)
    new.seller = Seller(active_since="20.11.2026", badges=[], other_ads=1)
    new.secure_payment = False
    s = score_item(new, W, 60, TODAY)
    assert old.value >= 85 and s.value < 60 and "Account neu" in s.text()


def test_soft_keyword_penalty():
    it = good_ka(1, price=280)
    base = score_item(it, W, 60, TODAY).value
    it.description = "Nur Vorkasse"
    assert score_item(it, W, 60, TODAY).value == base - 10


def test_whatsapp_variants():
    it = good_ka(1, price=280)
    it.description = "Meldet euch per Whats App"
    assert "WhatsApp" in score_item(it, W, 60, TODAY).strong_flags
