"""Single home for pilot identity-probe vocabulary (A1).

A new probe reason is a fall-open vector (#732 pattern): consumers that compare
against the old members silently mis-handle the new one. ``test_pilot_probe_census.py``
keeps producers and consumers honest — no module outside this file may name a probe
token as a literal.

Non-goals (this wave): probe execution, lapse handling, re-probe policy — this
module defines the vocabulary and its classes only.
"""
REASON_TRANSPORT_ERROR = "transport-error"
REASON_UNEXPECTED_STATUS = "unexpected-status"
REASON_INVALID_BODY = "invalid-body"
REASON_NO_SESSION = "no-session"
REASON_WRONG_IDENTITY = "wrong-identity"
REASON_DISABLED_ACCOUNT = "disabled-account"
REASON_UNAUTHORIZED = "unauthorized"
REASON_FORBIDDEN = "forbidden"
REASON_RATE_LIMITED = "rate-limited"
REASON_INFRASTRUCTURE_UNAVAILABLE = "infrastructure-unavailable"

LAPSE_REASONS = frozenset({
    REASON_NO_SESSION,
})
INFRASTRUCTURE_REASONS = frozenset({
    REASON_TRANSPORT_ERROR,
    REASON_UNEXPECTED_STATUS,
    REASON_INVALID_BODY,
    REASON_RATE_LIMITED,
    REASON_INFRASTRUCTURE_UNAVAILABLE,
})
IDENTITY_REASONS = frozenset({
    REASON_WRONG_IDENTITY,
    REASON_DISABLED_ACCOUNT,
    REASON_UNAUTHORIZED,
    REASON_FORBIDDEN,
})

ALL_PROBE_REASONS = LAPSE_REASONS | INFRASTRUCTURE_REASONS | IDENTITY_REASONS
EXPECTED_TOKEN_COUNT = 10


def routes_to_lapse(reason):
    """True when reason is the lapse-class token (no-session)."""
    return reason in LAPSE_REASONS


def is_infrastructure(reason):
    """True when reason is an infrastructure-class token."""
    return reason in INFRASTRUCTURE_REASONS


def classify(reason):
    """Return 'lapse', 'infrastructure', or 'identity' for a known probe reason."""
    if reason in LAPSE_REASONS:
        return "lapse"
    if reason in INFRASTRUCTURE_REASONS:
        return "infrastructure"
    if reason in IDENTITY_REASONS:
        return "identity"
    raise ValueError("unknown probe reason: %r" % (reason,))
