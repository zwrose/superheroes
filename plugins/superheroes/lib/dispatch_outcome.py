"""Single home for dispatch outcome vocabulary (#747).

A new outcome member is a fall-open vector (#732 pattern): consumers that compare
against the old members silently mis-handle the new one. ``test_dispatch_outcome_census.py``
keeps producers and consumers honest — no module outside this file may name an outcome
token as a literal.

Run-dir refusal detail tokens (``run-dir-is-symlink``, ``run-dir-not-empty-unopened``,
``run-dir-reused``) also live here; ``test_run_dir_refusal_census.py`` binds them.
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

CLASSIFICATION_REFUSAL = "refusal"
CLASSIFICATION_RESULT = "result"

DETAIL_RUN_DIR_IS_SYMLINK = "run-dir-is-symlink"
DETAIL_RUN_DIR_NOT_EMPTY_UNOPENED = "run-dir-not-empty-unopened"
DETAIL_RUN_DIR_REUSED = "run-dir-reused"

ALL_RUN_DIR_REFUSAL_DETAILS = frozenset({
    DETAIL_RUN_DIR_IS_SYMLINK,
    DETAIL_RUN_DIR_NOT_EMPTY_UNOPENED,
    DETAIL_RUN_DIR_REUSED,
})


def exit_code(classification):
    """axis: refusal-vs-result — a refusal must never be readable as success by exit code."""
    if classification == CLASSIFICATION_RESULT:
        return 0
    return 1


def classify_dispatch_result(result):
    """Classify a dispatch-review / dispatch-write structured result."""
    if not isinstance(result, dict):
        return CLASSIFICATION_REFUSAL
    if result.get("terminal") and result.get("reason") == REASON_UNRUNNABLE:
        return CLASSIFICATION_REFUSAL
    return CLASSIFICATION_RESULT


def classify_payload(payload):
    """Classify a dispatch_guard check / build-argv payload."""
    if not isinstance(payload, dict):
        return CLASSIFICATION_REFUSAL
    if payload.get("ok") is not True:
        return CLASSIFICATION_REFUSAL
    return CLASSIFICATION_RESULT


def is_forfeit(reason):
    """True when reason is a terminal non-result forfeit."""
    return reason in FORFEIT_REASONS


def counts_as_run(reason):
    """True when reason is absent (success) or not a not-run outcome."""
    return reason is None or reason not in NOT_RUN_REASONS


def is_terminal(reason):
    """True when reason is a terminal dispatch outcome (not running)."""
    return reason in TERMINAL_REASONS
