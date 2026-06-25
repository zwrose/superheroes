# plugins/superheroes/lib/worker_recovery.py
"""Bounded build-worker recovery (UFR-3), a sibling of recover.rearm_action. Pure decision:
(attempt, signal, max_attempts) -> {"action","reason"} where action ∈ retry_with_context |
escalate | park. A "plan is wrong" / structurally-too-large signal parks immediately; otherwise
retry (early attempts), escalate on the attempt before the cap, then park at the cap."""

PLAN_WRONG = "plan_wrong"
DEFAULT_MAX_ATTEMPTS = 3


def decide(attempt, signal, max_attempts=DEFAULT_MAX_ATTEMPTS):
    if signal == PLAN_WRONG:
        return {"action": "park",
                "reason": "worker signalled the plan/task is wrong or too large — park (UFR-3)"}
    if attempt >= max_attempts:
        return {"action": "park",
                "reason": "worker still blocked at the fixed maximum (%d) — park (UFR-3)" % max_attempts}
    if attempt == max_attempts - 1:
        return {"action": "escalate",
                "reason": "retry budget nearly spent — escalate to a more capable worker (UFR-3)"}
    return {"action": "retry_with_context",
            "reason": "worker needs more context — retry (attempt %d of %d)" % (attempt, max_attempts)}
