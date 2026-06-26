# plugins/superheroes/lib/pr_phase.py
"""Pure decisions for the draft-PR / mark-ready phases (the band's recover.pr_action style).
The showrunner leaf gathers the gh world-reads; these functions decide. Fail-closed."""


def mark_ready_action(pr):
    """pr: the gh world-read of the run's PR, or the string 'unknown' on a transient read.
    -> 'skip' (already ready, idempotent), 'flip' (draft -> ready), or 'gate' (unreadable/
    malformed/ambiguous -> don't guess, never re-flip blind)."""
    if not isinstance(pr, dict) or not pr.get("number"):
        return "gate"
    draft = pr.get("isDraft")
    if draft is True:
        return "flip"
    if draft is False:
        return "skip"
    return "gate"          # isDraft missing / None / non-bool -> fail closed, never flip blind


def mark_ready_status_action(status_result):
    """Gate mark-ready on the durable test-pilot readiness result."""
    if not isinstance(status_result, dict):
        return {"action": "gate", "reason": "test-pilot status unreadable"}
    if status_result.get("ok") is True:
        return {"action": "proceed"}
    return {"action": "gate", "reason": status_result.get("reason") or "test-pilot status not ready"}
