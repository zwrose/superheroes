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
