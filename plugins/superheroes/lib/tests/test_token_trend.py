import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import journal
import token_trend


def test_classify_completed_parked_other():
    assert token_trend.classify([{"type": "phase_cost"}, {"type": "run_completed"}]) == "completed"
    assert token_trend.classify([{"type": "phase_cost"}, {"type": "parked"}]) == "parked"
    # run_completed wins even when a later transient park exists earlier in history
    assert token_trend.classify([{"type": "parked"}, {"type": "run_completed"}]) == "completed"
    assert token_trend.classify([{"type": "phase_record"}]) == "other"
    assert token_trend.classify([]) == "other"


def test_build_trend_averages_per_item_and_per_park():
    runs = [
        {"workItem": "130", "state": "completed", "dispatches": 100, "outputTokens": 9000000, "measured": True},
        {"workItem": "118", "state": "completed", "dispatches": 60, "outputTokens": 3000000, "measured": True},
        {"workItem": "125", "state": "parked", "dispatches": 40, "outputTokens": 1000000, "measured": True},
    ]
    t = token_trend.build_trend(runs)
    assert t["completed"]["count"] == 2
    assert t["completed"]["dispatchesPerItem"] == 80
    assert t["completed"]["tokensPerItem"] == 6000000
    assert t["parked"]["count"] == 1
    assert t["parked"]["tokensPerPark"] == 1000000
    assert t["parked"]["dispatchesPerPark"] == 40


def test_build_trend_excludes_unmeasured_from_token_average_but_not_dispatch():
    runs = [
        {"workItem": "a", "state": "completed", "dispatches": 100, "outputTokens": 8000000, "measured": True},
        {"workItem": "b", "state": "completed", "dispatches": 50, "outputTokens": None, "measured": False},
    ]
    t = token_trend.build_trend(runs)
    assert t["completed"]["dispatchesPerItem"] == 75          # both counted
    assert t["completed"]["tokensPerItem"] == 8000000         # only the measured run
    assert t["completed"]["tokenItems"] == 1


def test_collect_runs_over_a_store_checkout(tmp_path):
    checkout = tmp_path / "checkouts" / "keyabc"
    for wi, evs in {
        "130": [("phase_cost", {"phase": "workhorse", "dispatches": {"total": 9, "byModel": {}}, "tokens": {"output": 500, "measured": True}}),
                ("run_completed", None)],
        "118": [("phase_cost", {"phase": "plan", "dispatches": {"total": 3, "byModel": {}}, "tokens": {"output": 100, "measured": True}}),
                ("parked", None)],
    }.items():
        ev_path = str(checkout / "issues" / wi / "events.jsonl")
        for etype, payload in evs:
            kw = {"payload": payload} if payload is not None else {}
            journal.append(ev_path, etype, root=str(tmp_path), **kw)
    runs = {r["workItem"]: r for r in token_trend.collect_runs(str(checkout))}
    assert set(runs) == {"130", "118"}
    assert runs["130"]["state"] == "completed" and runs["130"]["dispatches"] == 9
    assert runs["118"]["state"] == "parked"


def test_collect_runs_missing_store_is_empty():
    assert token_trend.collect_runs("/no/such/store") == []


def test_render_trend_has_headers_and_numbers():
    runs = [
        {"workItem": "130", "state": "completed", "dispatches": 100, "outputTokens": 9000000, "measured": True},
        {"workItem": "125", "state": "parked", "dispatches": 40, "outputTokens": 1000000, "measured": True},
    ]
    text = token_trend.render_trend(token_trend.build_trend(runs))
    assert "Token trend" in text
    assert "130" in text and "125" in text
    assert "per completed work-item" in text.lower()
