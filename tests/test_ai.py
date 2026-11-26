import json
from types import SimpleNamespace

from conftest import FakeNotifier, FakeSource, good_ka
from watcher.ai import AIChecker, build_prompt, parse_results
from watcher.config import Settings
from watcher.models import Watch
from watcher.runner import Runner


class FakeClaude:
    """Nachgestellter Anthropic-Client (Claude-API)."""
    def __init__(self, answers):
        self.answers = list(answers)
        self.calls = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self.create))

    def create(self, **kw):
        self.calls.append(kw)
        return SimpleNamespace(stop_reason="end_turn",
                               content=[SimpleNamespace(type="text", text=json.dumps(self.answers.pop(0)))])


class FakeHttp:
    """Nachgestellte GitHub-Models-Antwort."""
    def __init__(self, answers, status=200):
        self.answers = list(answers)
        self.status = status
        self.calls = []

    def post(self, url, headers=None, json=None, timeout=None):
        self.calls.append((url, headers, json))
        body = {"choices": [{"message": {"content": __import__("json").dumps(self.answers.pop(0))}}]} if self.answers else {}
        return SimpleNamespace(status_code=self.status, json=lambda: body, text="", headers={})


def run_twice(settings, store, watch, items, ai):
    n = FakeNotifier()
    src = FakeSource("kleinanzeigen", [[good_ka(0)], items])
    Runner(settings, store, n, {"kleinanzeigen": src}, ai=ai).run([watch])
    st = Runner(settings, store, n, {"kleinanzeigen": src}, ai=ai).run([watch])
    return n, st


RESULTS = {"results": [
    {"id": 1, "matches": False, "is_offer": True, "reason": "Spielzeugrad, kein echtes Fahrrad"},
    {"id": 2, "matches": True, "is_offer": False, "reason": "Gesuch"},
    {"id": 3, "matches": True, "is_offer": True, "reason": "Genau das gesuchte Modell"},
]}


def test_github_models_batch(settings, store, watch, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "t")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    http = FakeHttp([RESULTS])
    ai = AIChecker(Settings(), http=http)
    assert ai.provider == "github" and ai.model == "openai/gpt-4.1-mini"
    n, st = run_twice(settings, store, watch, [good_ka(1), good_ka(2), good_ka(3)], ai)
    assert len(http.calls) == 1                       # alle drei in EINER Anfrage
    assert st.ai_rejected == 2 and len(n.sent) == 1
    assert "KI ✓ Genau das gesuchte Modell" in n.sent[0]["message"]
    url, headers, body = http.calls[0]
    assert url.startswith("https://models.github.ai/") and headers["Authorization"] == "Bearer t"
    assert body["response_format"] == {"type": "json_object"}


def test_github_limit_lets_items_through(settings, store, watch, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "t")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    ai = AIChecker(Settings(), http=FakeHttp([], status=429))
    n, st = run_twice(settings, store, watch, [good_ka(1), good_ka(2)], ai)
    assert len(n.sent) == 2 and not ai.enabled       # ungeprüft durchgelassen


def test_claude_provider_when_key(settings, store, watch):
    client = FakeClaude([RESULTS])
    ai = AIChecker(Settings(), client=client)
    assert ai.provider == "anthropic"
    n, st = run_twice(settings, store, watch, [good_ka(1), good_ka(2), good_ka(3)], ai)
    assert len(n.sent) == 1 and client.calls[0]["output_config"]["format"]["type"] == "json_schema"


def test_ai_off_without_token(monkeypatch, watch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    ai = AIChecker(Settings())
    assert not ai.enabled and ai.check(good_ka(1), watch) is None


def test_wanted_ad_skipped_without_ai(settings, store, watch, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    it = good_ka(5); it.offer_type = "Gesuch"
    n, st = run_twice(settings, store, watch, [it], AIChecker(Settings()))
    assert n.sent == []


def test_prompt_and_parse():
    w = Watch(name="GPU", query="rx 9070 xt", ai_hint="nur einzelne Karte, kein PC", max_price=800)
    a = good_ka(1, title="Gaming PC mit RX 9070 XT"); a.attributes = {"Art": "Komplettsystem"}
    p = build_prompt([a, good_ka(2)], w)
    assert "nur einzelne Karte" in p and 'id="2"' in p and "Komplettsystem" in p and "800 €" in p
    r = parse_results('{"results":[{"id":1,"matches":false,"is_offer":true,"reason":"PC"},{"id":9,"matches":true,"is_offer":true,"reason":"x"}]}', 2)
    assert list(r) == [1] and not r[1].ok
