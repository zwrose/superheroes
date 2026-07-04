"""Assemble the codified success readout (FR-10) from a run's end state, and project the
machine-readable run-outcome (#112's consumer contract). build_readout already owns the
secret-scrubbing + the element layout; this only maps run state onto its context keys.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _cost_summary(state):
    """#130: the run-cost rollup for the readout. Prefer a precomputed `cost` dict; otherwise
    derive it from the run's own events.jsonl (`events_path`). Best-effort — any failure yields
    None and the readout simply omits the cost block (telemetry is never load-bearing)."""
    if isinstance(state.get("cost"), dict):
        return state["cost"]
    ev_path = state.get("events_path")
    if not ev_path:
        return None
    try:
        import journal
        import cost_report
        return cost_report.summarize(journal.read_events(ev_path))
    except Exception:
        return None


def assemble(state):
    """Map run-end state -> the build_readout context dict (FR-10 elements)."""
    state = state or {}
    ci = state.get("ci")
    ci_status = ("no required checks gate this PR — confirm checks before merging"
                 if ci in (None, "none") else "checks %s" % ci)
    return {
        "pr_url": state.get("pr_url"),
        "ci_status": ci_status,
        "built_vs_acceptance": state.get("built_vs_acceptance"),
        "test_results": state.get("test_results"),
        "dev_url": state.get("dev_url"),
        "smoke": state.get("smoke") or [],
        "raw_ci_excerpt": state.get("raw_ci_excerpt"),
        "cost": _cost_summary(state),
        "root": state.get("root"),
    }


def run_outcome(state):
    """The machine-readable projection #112 asserts against (status/PR/checks/phases)."""
    state = state or {}
    return {
        "status": state.get("status"),
        "phase": state.get("phase"),
        "reason": state.get("reason"),
        "prUrl": state.get("pr_url"),
        "checks": state.get("ci") or "none",
        "phasesTraversed": state.get("phases") or [],
        "readoutPath": state.get("readout_path"),
    }
