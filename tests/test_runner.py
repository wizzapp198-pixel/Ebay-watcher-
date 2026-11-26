from conftest import FakeNotifier, FakeSource, good_ebay, good_ka
from watcher.http import SourceBlocked
from watcher.runner import Runner


def make(settings, store, notifier, *sources):
    return Runner(settings, store, notifier, sources={s.name: s for s in sources})


def test_first_run_is_silent_then_only_new(settings, store, watch):
    n = FakeNotifier()
    src = FakeSource("ebay", [[good_ebay(1), good_ebay(2)], [good_ebay(1), good_ebay(2), good_ebay(3)]])
    st = make(settings, store, n, src).run([watch])
    assert n.sent == [] and st.baseline == 2
    st = make(settings, store, n, src).run([watch])
    assert len(n.sent) == 1 and "[eBay]" in n.sent[0]["title"]
    assert n.sent[0]["click"].endswith("/3")


def test_dedup_across_runs(settings, store, watch):
    n = FakeNotifier()
    src = FakeSource("ebay", [[], [good_ebay(5)], [good_ebay(5)]])
    r = make(settings, store, n, src)
    r.run([watch]); r.run([watch]); r.run([watch])
    assert len(n.sent) == 1


def test_push_failure_keeps_item_unseen(settings, store, watch):
    src = FakeSource("ebay", [[], [good_ebay(7)], [good_ebay(7)]])
    bad = FakeNotifier(fail=True)
    make(settings, store, bad, src).run([watch])
    st = make(settings, store, bad, src).run([watch])
    assert st.failed_push == 1 and not store.is_seen("ebay:7")
    ok = FakeNotifier()
    make(settings, store, ok, src).run([watch])
    assert len(ok.sent) == 1 and store.is_seen("ebay:7")


def test_changed_query_triggers_new_silent_baseline(settings, store, watch):
    n = FakeNotifier()
    src = FakeSource("ebay", [[good_ebay(1)], [good_ebay(10), good_ebay(11)]])
    make(settings, store, n, src).run([watch])
    watch.query = "iphone 14"
    st = make(settings, store, n, src).run([watch])
    assert n.sent == [] and st.baseline == 2


def test_source_failure_other_continues_and_warns_once(settings, store, watch):
    n = FakeNotifier()
    ka = FakeSource("kleinanzeigen", error=SourceBlocked("HTTP 403"))
    eb = FakeSource("ebay", [[], [good_ebay(1)]])
    make(settings, store, n, ka, eb).run([watch])
    warns = [m for m in n.sent if "gestört" in m["title"]]
    assert len(warns) == 1
    st = make(settings, store, n, ka, eb).run([watch])
    warns = [m for m in n.sent if "gestört" in m["title"]]
    assert len(warns) == 1  # max. 1x pro Stunde
    assert any("[eBay]" in m["title"] for m in n.sent)
    assert "kleinanzeigen" in st.errors


def test_exclusion_and_price_filter(settings, store, watch):
    n = FakeNotifier()
    src = FakeSource("ebay", [[], [good_ebay(1, title="iPhone 13 defekt"), good_ebay(2, price=999),
                                   good_ebay(3, price=10), good_ebay(4, title="iPhone 13 perfekt")]])
    make(settings, store, n, src).run([watch]); make(settings, store, n, src).run([watch])
    assert len(n.sent) == 1 and "perfekt" in n.sent[0]["title"]


def test_bargain_high_priority(settings, store, watch):
    n = FakeNotifier()
    src = FakeSource("ebay", [[], [good_ebay(1, price=250)]])  # 83 % vom Ref.
    make(settings, store, n, src).run([watch]); make(settings, store, n, src).run([watch])
    assert n.sent[0]["priority"] == 5 and n.sent[0]["title"].startswith("🔥")


def test_suspicious_not_sent_unless_enabled(settings, store, watch):
    scam = good_ka(9, price=250)
    scam.description = "Zahlung bitte per PayPal Freunde, Kontakt über WhatsApp"
    n = FakeNotifier()
    src = FakeSource("kleinanzeigen", [[], [scam]])
    make(settings, store, n, src).run([watch]); make(settings, store, n, src).run([watch])
    assert n.sent == []
    watch.send_suspicious = True
    scam2 = good_ka(10, price=250); scam2.description = scam.description
    src.batches = [[scam2]]
    make(settings, store, n, src).run([watch])
    assert n.sent[0]["priority"] == 2 and n.sent[0]["title"].startswith("⚠️")


def test_ka_details_only_for_candidates(settings, store, watch):
    n = FakeNotifier()
    a = good_ka(1); a.details_loaded = False
    b = good_ka(2, title="iPhone defekt"); b.details_loaded = False
    src = FakeSource("kleinanzeigen", [[good_ka(0)], [a, b]])
    make(settings, store, n, src).run([watch]); make(settings, store, n, src).run([watch])
    assert src.detail_calls == 1 and len(n.sent) == 1


def test_push_cap_per_run(settings, store, watch):
    settings.max_pushes_per_run = 2
    n = FakeNotifier()
    src = FakeSource("ebay", [[], [good_ebay(i) for i in range(5)], [good_ebay(i) for i in range(5)]])
    r = make(settings, store, n, src)
    r.run([watch]); r.run([watch])
    assert len(n.sent) == 2
    r.run([watch])
    assert len(n.sent) == 4


def test_comma_means_or_and_dedup(settings, store, watch):
    seen_queries = []

    class Multi(FakeSource):
        def search(self, w):
            seen_queries.append(w.query)
            return [good_ebay(1), good_ebay(2)] if w.query == "rx 9070 xt" else [good_ebay(2), good_ebay(3)]

    watch.query = "RX 9070 XT , rx 9070 xt, radeon 9070"
    n = FakeNotifier()
    st = make(settings, store, n, Multi("ebay")).run([watch])
    assert seen_queries == ["rx 9070 xt", "radeon 9070"]
    assert st.baseline == 3


def test_found_list_recorded_and_merged(settings, store, watch, tmp_path):
    import json
    from watcher.found import merge, merge_files
    n = FakeNotifier()
    src = FakeSource("ebay", [[], [good_ebay(1), good_ebay(2)]])
    make(settings, store, n, src).run([watch])
    st = make(settings, store, n, src).run([watch])
    assert [f["key"] for f in st.found] == ["ebay:1", "ebay:2"]
    assert st.found[0]["watch"] == "iPhone" and st.found[0]["url"].endswith("/1")
    new = tmp_path / "new.json"; target = tmp_path / "found.json"
    new.write_text(json.dumps(st.found))
    merge_files(new, target); merge_files(new, target)
    data = json.loads(target.read_text())["found"]
    assert [f["key"] for f in data] == ["ebay:2", "ebay:1"]  # neueste zuerst, keine Doppelten
    assert len(merge([{"key": str(i)} for i in range(400)], [], limit=300)) == 300


def test_failed_push_not_in_found(settings, store, watch):
    src = FakeSource("ebay", [[], [good_ebay(1)]])
    make(settings, store, FakeNotifier(), src).run([watch])
    st = make(settings, store, FakeNotifier(fail=True), src).run([watch])
    assert st.found == []


def test_accessory_skipped_unless_searched(settings, store):
    from watcher.models import Watch
    bike = Watch(name="Fahrrad", query="fahrrad", sources=["kleinanzeigen"])
    tyre = good_ka(1, title="Schwalbe Marathon Fahrrad Reifen"); tyre.attributes = {"Art": "Zubehör", "Typ": "Andere Fahrräder"}
    bag = good_ka(2, title="Bikepacking-Set Topeak"); bag.attributes = {"Art": "Zubehör"}
    real = good_ka(3, title="Damenrad 28 Zoll"); real.attributes = {"Art": "Damen", "Typ": "Citybike"}
    n = FakeNotifier()
    src = FakeSource("kleinanzeigen", [[], [tyre, bag, real]])
    make(settings, store, n, src).run([bike]); make(settings, store, n, src).run([bike])
    assert len(n.sent) == 1 and "Damenrad" in n.sent[0]["title"]
    acc = Watch(name="Reifen", query="fahrrad reifen", sources=["kleinanzeigen"])
    from watcher.runner import accessory_mismatch
    assert accessory_mismatch(tyre, acc) is None
