import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import run_readout

STATE = {
    "pr_url": "https://github.com/o/r/pull/9", "ci": "none", "dev_url": None,
    "built_vs_acceptance": "FR-1..10 met", "test_results": "n/a — no browser surface",
    "smoke": ["check the path choice appears"], "phases": ["plan", "review-plan", "tasks", "ship"],
    "status": "ready", "phase": "ship", "reason": "merge-ready",
}

def test_assemble_maps_every_fr10_element():
    ctx = run_readout.assemble(STATE)
    for key in ("pr_url", "ci_status", "built_vs_acceptance", "test_results", "smoke"):
        assert key in ctx
    assert ctx["pr_url"] == "https://github.com/o/r/pull/9"

def test_readout_text_has_the_no_required_checks_note_and_merge_reminder():
    import readout
    text = readout.build_readout(run_readout.assemble(STATE))
    assert "Merge is yours" in text
    # ci "none" surfaces honestly (build_readout prints the ci_status string verbatim)
    assert "none" in text.lower() or "no required" in text.lower()

def test_run_outcome_is_the_machine_readable_projection():
    out = run_readout.run_outcome(STATE)
    assert out["status"] == "ready" and out["prUrl"].endswith("/pull/9")
    assert out["checks"] == "none" and out["phasesTraversed"] == STATE["phases"]


def _seed_cost(tmp_path):
    import journal
    e = str(tmp_path / "events.jsonl")
    journal.append(e, "phase_cost", payload={"phase": "workhorse",
        "dispatches": {"total": 9, "byModel": {"claude-opus-4-8": 9}},
        "tokens": {"output": 500, "measured": True, "source": "budget"}}, root=str(tmp_path))
    return e


def test_assemble_computes_cost_from_events_path(tmp_path):
    # #130: the run readout surfaces a cost line derived from the run's own events.jsonl.
    ctx = run_readout.assemble({**STATE, "events_path": _seed_cost(tmp_path)})
    assert ctx["cost"]["totalDispatches"] == 9


def test_readout_text_includes_cost_block_when_present(tmp_path):
    import readout
    text = readout.build_readout(run_readout.assemble({**STATE, "events_path": _seed_cost(tmp_path)}))
    assert "Run cost" in text and "9 dispatches" in text


def test_readout_omits_cost_block_when_absent():
    import readout
    assert "Run cost" not in readout.build_readout(run_readout.assemble(STATE))
