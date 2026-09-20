"""Single home for background attempt refusal vocabulary (#1273).

Cross-module reason tokens for claude ``--claude-mode background`` attempt outcomes.
``test_background_outcome_census.py`` keeps producers honest — no module outside this
file may name a background refusal token as a literal.
"""
REFUSAL_LAUNCH_UNACKNOWLEDGED = "background-launch-unacknowledged"
REFUSAL_LAUNCH_FAILED = "background-launch-failed"
REFUSAL_SESSION_UNLISTED = "background-session-unlisted"
REFUSAL_TRANSCRIPT_AMBIGUOUS = "background-transcript-ambiguous"
REFUSAL_AGENTS_UNREADABLE = "background-agents-unreadable"
REFUSAL_SESSION_ENDED_WITHOUT_RESULT = "background-session-ended-without-result"

ALL_REFUSALS = frozenset({
    REFUSAL_LAUNCH_UNACKNOWLEDGED,
    REFUSAL_LAUNCH_FAILED,
    REFUSAL_SESSION_UNLISTED,
    REFUSAL_TRANSCRIPT_AMBIGUOUS,
    REFUSAL_AGENTS_UNREADABLE,
    REFUSAL_SESSION_ENDED_WITHOUT_RESULT,
})
