import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from watcher.config import Settings  # noqa: E402
from watcher.models import Item, Seller, Watch  # noqa: E402
from watcher.notify import PushError  # noqa: E402
from watcher.store import Store  # noqa: E402

FIX = Path(__file__).parent / "fixtures"


class FakeNotifier:
    def __init__(self, fail=False):
        self.sent = []
        self.fail = fail

    def send(self, title, message, priority=3, tags=None, click=None, image=None):
        if self.fail:
            raise PushError("ntfy down")
        self.sent.append(dict(title=title, message=message, priority=priority, tags=tags, click=click))


class FakeSource:
    def __init__(self, name, batches=None, error=None):
        self.name = name
        self.batches = list(batches or [])
        self.error = error
        self.detail_calls = 0

    def configured(self):
        return True, ""

    def search(self, watch):
        if self.error:
            raise self.error
        return self.batches.pop(0) if self.batches else []

    def details(self, item):
        self.detail_calls += 1
        item.details_loaded = True
        return item


def good_ebay(id_, price=200.0, title="iPhone 13 128GB"):
    return Item(id=str(id_), source="ebay", title=title, url=f"https://ebay.de/itm/{id_}", price=price,
                buying_options=["FIXED_PRICE"], country="DE", details_loaded=True,
                seller=Seller(name="s", feedback_percent=99.8, feedback_score=1500))


def good_ka(id_, price=200.0, title="iPhone 13 128GB"):
    return Item(id=str(id_), source="kleinanzeigen", title=title, url=f"https://ka.de/{id_}", price=price,
                country="DE", secure_payment=True, shipping=True, details_loaded=True,
                seller=Seller(active_since="01.01.2018", badges=["TOP Zufriedenheit"], commercial=False, other_ads=3))


@pytest.fixture
def settings():
    s = Settings()
    s.warn_interval_minutes = 60
    return s


@pytest.fixture
def store(tmp_path):
    st = Store(str(tmp_path / "t.db"))
    yield st
    st.close()


@pytest.fixture
def watch():
    return Watch(name="iPhone", query="iphone 13", sources=["ebay", "kleinanzeigen"],
                 min_price=50, max_price=400, ref_price=300)


@pytest.fixture(autouse=True)
def _no_network_ai(monkeypatch):
    """Tests laufen ohne Netzwerk: keine echten KI-Zugänge aus der Umgebung verwenden."""
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
