import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import cost_report


def _events():
    return [
        {"type": "run_started"},
        {"type": "phase_cost", "payload": {"phase": "plan",
            "dispatches": {"total": 4, "byModel": {"claude-opus-4-8": 4}},
            "tokens": {"output": 120000, "measured": True, "source": "budget"}}},
        {"type": "phase_cost", "payload": {"phase": "workhorse",
            "dispatches": {"total": 60, "byModel": {"claude-haiku-4-5-20251001": 50, "claude-opus-4-8": 10}},
            "tokens": {"output": 5000000, "measured": True, "source": "budget"}}},
        {"type": "phase_cost", "payload": {"phase": "review-code",
            "dispatches": {"total": 40, "byModel": {"claude-sonnet-5": 40}},
            "tokens": {"output": 2000000, "measured": True, "source": "budget"}}},
        {"type": "external_dispatch", "payload": {"engine": "codex"}},
    ]


def test_summarize_totals_and_top_phases_by_tokens():
    s = cost_report.summarize(_events())
    assert s["totalDispatches"] == 104
    assert s["outputTokens"] == 7120000
    assert s["measured"] is True and s["partial"] is False
    assert s["externalDispatches"] == 1
    # top 1-2 most expensive phases, ranked by measured output tokens
    assert [p["phase"] for p in s["topPhases"]] == ["workhorse", "review-code"]
    # per-tier rollup across phases
    assert s["byTier"]["claude-opus-4-8"] == 14


def test_summarize_no_phase_cost_events_is_empty():
    s = cost_report.summarize([{"type": "run_started"}])
    assert s["totalDispatches"] == 0
    assert s["outputTokens"] is None
    assert s["measured"] is False
    assert s["topPhases"] == []


def test_summarize_proxy_only_ranks_by_dispatches_when_unmeasured():
    evs = [
        {"type": "phase_cost", "payload": {"phase": "plan",
            "dispatches": {"total": 4, "byModel": {"claude-opus-4-8": 4}},
            "tokens": {"output": None, "measured": False, "source": "none"}}},
        {"type": "phase_cost", "payload": {"phase": "workhorse",
            "dispatches": {"total": 30, "byModel": {"claude-haiku-4-5-20251001": 30}},
            "tokens": {"output": None, "measured": False, "source": "none"}}},
    ]
    s = cost_report.summarize(evs)
    assert s["totalDispatches"] == 34
    assert s["outputTokens"] is None and s["measured"] is False
    assert s["topPhases"][0]["phase"] == "workhorse"   # ranked by dispatches


def test_summarize_partial_measured_sums_only_measured():
    evs = [
        {"type": "phase_cost", "payload": {"phase": "plan",
            "dispatches": {"total": 4, "byModel": {}}, "tokens": {"output": 100, "measured": True}}},
        {"type": "phase_cost", "payload": {"phase": "ship",
            "dispatches": {"total": 2, "byModel": {}}, "tokens": {"output": None, "measured": False}}},
    ]
    s = cost_report.summarize(evs)
    assert s["outputTokens"] == 100 and s["measured"] is True and s["partial"] is True


def test_summarize_aggregates_repeated_phase():
    evs = [
        {"type": "phase_cost", "payload": {"phase": "ship",
            "dispatches": {"total": 3, "byModel": {"claude-opus-4-8": 3}}, "tokens": {"output": 100, "measured": True}}},
        {"type": "phase_cost", "payload": {"phase": "ship",
            "dispatches": {"total": 2, "byModel": {"claude-opus-4-8": 2}}, "tokens": {"output": 50, "measured": True}}},
    ]
    s = cost_report.summarize(evs)
    assert s["totalDispatches"] == 5
    assert s["phases"][0]["phase"] == "ship" and s["phases"][0]["dispatches"] == 5
    assert s["outputTokens"] == 150


def test_summarize_tolerates_malformed_entries():
    evs = [
        {"type": "phase_cost", "payload": None},
        {"type": "phase_cost", "payload": {"phase": "plan", "dispatches": "nope", "tokens": 7}},
        {"type": "phase_cost"},
        "not-a-dict",
        {"type": "phase_cost", "payload": {"phase": "ok", "dispatches": {"total": 2, "byModel": {}}, "tokens": {"output": 5, "measured": True}}},
    ]
    s = cost_report.summarize(evs)
    assert s["totalDispatches"] == 2 and s["outputTokens"] == 5


def test_render_cost_line_measured_names_top_phases():
    lines = cost_report.render_cost_line(cost_report.summarize(_events()))
    text = "\n".join(lines)
    assert "Run cost" in text
    assert "104 dispatches" in text
    assert "workhorse" in text and "review-code" in text


def test_render_cost_line_unmeasured_says_so():
    s = cost_report.summarize([
        {"type": "phase_cost", "payload": {"phase": "plan",
            "dispatches": {"total": 4, "byModel": {"claude-opus-4-8": 4}},
            "tokens": {"output": None, "measured": False, "source": "none"}}}])
    text = "\n".join(cost_report.render_cost_line(s))
    assert "not measured" in text.lower()
    assert "4 dispatches" in text


def test_render_cost_line_empty_is_nothing():
    assert cost_report.render_cost_line(cost_report.summarize([])) == []
