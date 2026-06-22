# plugins/superheroes/lib/phase_step.py
"""Per-phase decision: (phase_result, gate) -> the single terminal the showrunner.js shell
forwards. Pure + fail-closed (the band's recover/ci_loop/loop_state pattern). The JS computes
nothing; this owns the per-phase judgement (FR-5/FR-6/FR-7/FR-8).

Ordering is the safety contract: the assumption / low-confidence parks are evaluated BEFORE
the gate, so a phase that records an assumption or low confidence parks even when its gate is
'passed'. Then the gate maps over the spec's recognized set {pending, passed, changes-requested};
any other or unreadable value fails closed to park_unexpected_gate.
"""


def decide(phase_result, gate):
    pr = phase_result or {}
    # 1. self-assessed park signals first (before the gate) — the safety ordering.
    if pr.get("assumptions"):
        return {"action": "park_assumption",
                "reason": "phase recorded a material assumption"}
    if pr.get("confidence") == "low":
        return {"action": "park_low_confidence",
                "reason": "phase recorded confidence below the parking threshold"}
    # 2. gate dimension. None = an authoring phase with no review gate.
    if gate is None or gate == "passed":
        return {"action": "proceed",
                "reason": "no review gate" if gate is None else "gate passed"}
    if gate == "changes-requested":
        return {"action": "park_changes_requested",
                "reason": "review requested changes"}
    if gate == "pending":
        return {"action": "park_pending",
                "reason": "gate not passed (pending / not yet approved)"}
    return {"action": "park_unexpected_gate",
            "reason": "unexpected or unreadable gate value: %r" % (gate,)}
