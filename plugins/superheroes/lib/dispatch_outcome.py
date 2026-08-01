"""Single home for dispatch outcome vocabulary (#747).

A new outcome member is a fall-open vector (#732 pattern): consumers that compare
against the old members silently mis-handle the new one. ``test_dispatch_outcome_census.py``
keeps producers and consumers honest — no module outside this file may name an outcome
token as a literal.
"""
REASON_FORFEITED = "forfeited"
REASON_VACUOUS = "vacuous"
REASON_FORFEIT_ENGAGED_ARTIFACT = "forfeit-with-engaged-artifact"
REASON_UNRUNNABLE = "unrunnable"
REASON_RUNNING = "running"

FORFEIT_REASONS = frozenset({
    REASON_FORFEITED,
    REASON_VACUOUS,
    REASON_FORFEIT_ENGAGED_ARTIFACT,
})
NOT_RUN_REASONS = FORFEIT_REASONS | {REASON_UNRUNNABLE}
ALL_REASONS = NOT_RUN_REASONS | {REASON_RUNNING}
TERMINAL_REASONS = ALL_REASONS - {REASON_RUNNING}

ATTRIBUTION_CALLER_ERROR = "caller-error"
ATTRIBUTION_TRANSPORT = "our-transport-contract"
ATTRIBUTION_ENVIRONMENT = "our-environment"
ATTRIBUTION_ENGINE_SIDE = "engine-side"
ATTRIBUTION_UNKNOWN = "unknown"  # unknown is a queue, not a bucket — unattributed forfeit is pending work
ATTRIBUTIONS = frozenset({
    ATTRIBUTION_CALLER_ERROR,
    ATTRIBUTION_TRANSPORT,
    ATTRIBUTION_ENVIRONMENT,
    ATTRIBUTION_ENGINE_SIDE,
    ATTRIBUTION_UNKNOWN,
})

STAGE_ENGAGED = "engaged"
STAGE_DELIVERED = "delivered"


def is_forfeit(reason):
    """True when reason is a terminal non-result forfeit."""
    return reason in FORFEIT_REASONS


def counts_as_run(reason):
    """True when reason is absent (success) or not a not-run outcome."""
    return reason is None or reason not in NOT_RUN_REASONS


def is_terminal(reason):
    """True when reason is a terminal dispatch outcome (not running)."""
    return reason in TERMINAL_REASONS
