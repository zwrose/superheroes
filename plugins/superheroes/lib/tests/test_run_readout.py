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
