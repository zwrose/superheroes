"""Single home for background attempt refusal vocabulary (#1273).

Cross-module reason tokens for claude ``--claude-mode background`` attempt outcomes.
``test_background_outcome_census.py`` keeps producers honest — no module outside this
file may name a background refusal token as a literal.
"""
import re
import uuid

REFUSAL_LAUNCH_UNACKNOWLEDGED = "background-launch-unacknowledged"
REFUSAL_LAUNCH_FAILED = "background-launch-failed"
REFUSAL_SESSION_UNLISTED = "background-session-unlisted"
REFUSAL_TRANSCRIPT_AMBIGUOUS = "background-transcript-ambiguous"
REFUSAL_AGENTS_UNREADABLE = "background-agents-unreadable"
REFUSAL_SESSION_ENDED_WITHOUT_RESULT = "background-session-ended-without-result"

# A background session's identity, as the per-account listing reports it: an eight-character
# lowercase-hex listing id, and a session id (a UUID) that begins with it. The acknowledgement
# parser, the launcher's handshake and the ledger's fold all read this one grammar.
BACKGROUND_ID_PATTERN = "[0-9a-f]{8}"


def valid_background_id(value):
    """True for a listing id: exactly eight lowercase hex characters."""
    return isinstance(value, str) and re.fullmatch(BACKGROUND_ID_PATTERN, value) is not None


def valid_background_session_id(session_id, background_id):
    """True for a session id: a UUID that begins with its listing id."""
    if not valid_background_id(background_id) or not isinstance(session_id, str):
        return False
    try:
        uuid.UUID(session_id)
    except (ValueError, AttributeError, TypeError):
        return False
    return session_id.startswith(background_id + "-")


ALL_REFUSALS = frozenset({
    REFUSAL_LAUNCH_UNACKNOWLEDGED,
    REFUSAL_LAUNCH_FAILED,
    REFUSAL_SESSION_UNLISTED,
    REFUSAL_TRANSCRIPT_AMBIGUOUS,
    REFUSAL_AGENTS_UNREADABLE,
    REFUSAL_SESSION_ENDED_WITHOUT_RESULT,
})
