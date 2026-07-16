"""Assemble the codified success readout (FR-10) from a run's end state, and project the
machine-readable run-outcome (#112's consumer contract). build_readout already owns the
secret-scrubbing + the element layout; this only maps run state onto its context keys.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import journal

# Journal event types this readout module may derive from or project (CONVENTIONS §11 copy-holder;
# drift-guarded against journal.EVENT_TYPES in test_ssot_drift.py).
KNOWN_JOURNAL_EVENT_TYPES = frozenset({
    "run_started", "step_entered", "step_completed", "notify", "gate", "error",
    "resumed", "lease_acquired", "lease_reclaimed", "ci_fix_attempt", "parked",
    "run_completed", "phase_record", "external_dispatch", "phase_cost", "phases_skipped",
    "permission_denied", "allowance_fired", "final_review_handoff",
    "routed_forward", "review_convergence", "handoff_provided",
    # #402 Part B (merged from main): terminal classifier-denial decline of a courier answer.
    "courier_declined",
    # #450: terminal receipt for a parked run finished by hand outside the spine.
    "manual_completion",
    # #355: confinement-tripwire security receipt (engine subprocess wrote outside its build worktree).
    "confinement_tripwire",
})


def _permission_denials(state):
    """Enumerate (never decide) the run's timeout-denial events (UFR-3). Reads the run's
    `events` path threaded onto `state` and maps each `permission_denied` journal event to
    a readout entry naming the affected step. Fail-soft: a missing/unreadable path yields no
    denials, never a raise (the enumeration must never break the readout)."""
    events_path = state.get("events_path")
    if not events_path:
        return []
    # Single reader of the literal `permission_denied` type (architecture-001): the shared
    # journal.permission_denied_events (fail-safe []) matches; this projects every one as a
    # disclosure entry (its own shape — step + detail, no build:-step filter).
    return [{"step": ev.get("step"), "detail": ev.get("detail")}
            for ev in journal.permission_denied_events(events_path)]


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


def _route_facts(state):
    """#25: the run's route + the front-half phases a quick run skipped, for the machine-readable
    outcome. Prefer explicit state keys; otherwise DERIVE from the run's own events.jsonl — the
    `phases_skipped` event the spine journals once at a quick-route intake (mirrors `_cost_summary`,
    which derives the cost block from the same journal). Best-effort: any failure, or no journal,
    yields the safe full-route default (route 'full', no skips) — so a full run and an unreadable
    journal both project honestly as full/[]."""
    route = state.get("route")
    skipped = state.get("skipped_phases")
    if route or skipped:
        return (route or "full"), (skipped if isinstance(skipped, list) else [])
    ev_path = state.get("events_path")
    if not ev_path:
        return "full", []
    try:
        import journal
        r, sk = "full", []
        for ev in journal.read_events(ev_path):
            # Last writer wins (a run that parks before its first checkpoint may journal the event
            # more than once across relaunches; all carry the same route + skip list).
            if isinstance(ev, dict) and ev.get("type") == "phases_skipped":
                payload = ev.get("payload") if isinstance(ev.get("payload"), dict) else {}
                r = payload.get("route") or "quick"
                s = payload.get("skipped")
                sk = s if isinstance(s, list) else []
        return r, sk
    except Exception:
        return "full", []


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
        "permissionDenials": _permission_denials(state),
    }


def run_outcome(state):
    """The machine-readable projection #112 asserts against (status/PR/checks/phases).

    #25: also surfaces the route and, on the quick route, the front-half phases it skipped — so the
    outcome is honest that plan/review-plan/tasks/review-tasks were skipped-by-route, not merely
    not-yet-reached. These come from `_route_facts`: explicit state keys, else derived from the run's
    own journal (the `phases_skipped` event). `route` defaults to full and `skippedPhases` to [] —
    byte-identical for a full run or an unreadable journal.
    """
    state = state or {}
    route, skipped_phases = _route_facts(state)
    return {
        "status": state.get("status"),
        "phase": state.get("phase"),
        "reason": state.get("reason"),
        "prUrl": state.get("pr_url"),
        "checks": state.get("ci") or "none",
        "phasesTraversed": state.get("phases") or [],
        "route": route,
        "skippedPhases": skipped_phases,
        "readoutPath": state.get("readout_path"),
    }
