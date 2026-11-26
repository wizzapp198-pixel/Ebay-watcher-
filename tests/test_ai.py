import json
from types import SimpleNamespace

from conftest import FakeNotifier, FakeSource, good_ka
from watcher.ai import AIChecker, build_prompt
from watcher.config import Settings
from watcher.models import Watch
from watcher.runner import Runner


class FakeClient:
    def __init__(self, answers):
        self.answers = list(answers)
        self.prompts = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self.create))

    def create(self, **kw):
        self.prompts.append(kw)
        a = self.answers.pop(0)
        return SimpleNamespace(stop_reason="end_turn",
                               content=[SimpleNamespace(type="text", text=json.dumps(a))])


def run_twice(settings, store, watch, items, ai):
    n = FakeNotifier()
    src = FakeSource("kleinanzeigen", [[good_ka(0)], items])
    Runner(settings, store, n, {"kleinanzeigen": src}, ai=ai).run([watch])
    st = Runner(settings, store, n, {"kleinanzeigen": src}, ai=ai).run([watch])
    return n, st


def test_ai_rejects_toy_and_wanted_ad(settings, store, watch):
    client = FakeClient([
        {"matches": False, "is_offer": True, "reason": "Spielzeugrad, kein echtes Fahrrad"},
        {"matches": True, "is_offer": False, "reason": "Gesuch"},
        {"matches": True, "is_offer": True, "reason": "Genau das gesuchte Modell"},
    ])
    ai = AIChecker(Settings(), client=client)
    n, st = run_twice(settings, store, watch, [good_ka(1), good_ka(2), good_ka(3)], ai)
    assert st.ai_rejected == 2 and len(n.sent) == 1
    assert "KI ✓ Genau das gesuchte Modell" in n.sent[0]["message"]
    kw = client.prompts[0]
    assert kw["output_config"]["format"]["type"] == "json_schema"
    assert kw["model"] == "claude-opus-5-5"


def test_ai_off_without_key(settings, store, watch, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    ai = AIChecker(Settings())
    assert not ai.enabled and ai.check(good_ka(1), watch) is None


def test_ai_limit_per_run(settings, store, watch):
    s = Settings(); s.ai = {"max_checks_per_run": 1}
    client = FakeClient([{"matches": False, "is_offer": True, "reason": "x"}])
    ai = AIChecker(s, client=client)
    n, st = run_twice(settings, store, watch, [good_ka(1), good_ka(2)], ai)
    assert st.ai_checks == 1 and len(n.sent) == 1  # zweites Angebot ungeprüft durchgelassen


def test_wanted_ad_skipped_without_ai(settings, store, watch):
    it = good_ka(5); it.offer_type = "Gesuch"
    n, st = run_twice(settings, store, watch, [it], AIChecker(Settings()))
    assert n.sent == []


def test_prompt_contains_hint_and_listing():
    w = Watch(name="GPU", query="rx 9070 xt", ai_hint="nur einzelne Karte, kein PC", max_price=800)
    p = build_prompt(good_ka(1, title="Gaming PC mit RX 9070 XT"), w)
    assert "nur einzelne Karte" in p and "Gaming PC" in p and "800 €" in p
