#!/usr/bin/env python3
"""Single home for review-session mode (PR vs branch) resolution (#1151).

Pure, stdlib-only leaf: no imports from other plugin lib modules so consumers
like review_base_guard can import without cycles.
"""

MODE_PR = "pr"
MODE_BRANCH = "branch"
MODES = frozenset({MODE_PR, MODE_BRANCH})

# bite-axis: DIRECTION of failure — a PR-scoped review over a branch session is
# conservative; a branch-scoped review over a PR session silently drops PR-only
# context (prior comments, checkout path, author-justification rules).
UNRESOLVED_MODE = MODE_PR

EVIDENCE_SESSION_META = "session-meta"
EVIDENCE_DRIVER_CONFIG = "driver-config"
EVIDENCE_UNRESOLVED = "unresolved"


def _fresh_result(mode, evidence, resolved, disclosure):
    return {
        "mode": mode,
        "evidence": evidence,
        "resolved": resolved,
        "disclosure": disclosure,
    }


def _valid_mode(value):
    # bite-axis: vocabulary — only the closed lowercase pair is accepted; writers
    # emit lowercase and silent case-normalization would hide a real writer bug.
    if isinstance(value, str) and value in MODES:
        return value
    return None


def _mapping_has_mode_key(mapping):
    return isinstance(mapping, dict) and "mode" in mapping


def _disclosure_for_invalid(source_label, value):
    return (
        "Review session mode in %s was invalid (%s); defaulting to PR review."
        % (source_label, repr(value))
    )


def _disclosure_for_missing():
    return (
        "Review session mode was not set in session metadata or driver "
        "configuration; defaulting to PR review."
    )


def resolve(meta, config):
    """Resolve review-session mode from session metadata and driver config.

    Returns a fresh dict with keys mode, evidence, resolved, disclosure.
    Never raises.
    """
    if _mapping_has_mode_key(meta):
        valid = _valid_mode(meta.get("mode"))
        if valid is not None:
            return _fresh_result(
                valid, EVIDENCE_SESSION_META, True, None,
            )
        # bite-axis: authority — a present-but-invalid higher-authority value must
        # not fall through to driver configuration.
        return _fresh_result(
            UNRESOLVED_MODE,
            EVIDENCE_UNRESOLVED,
            False,
            _disclosure_for_invalid("session metadata", meta.get("mode")),
        )

    if _mapping_has_mode_key(config):
        valid = _valid_mode(config.get("mode"))
        if valid is not None:
            return _fresh_result(
                valid, EVIDENCE_DRIVER_CONFIG, True, None,
            )
        return _fresh_result(
            UNRESOLVED_MODE,
            EVIDENCE_UNRESOLVED,
            False,
            _disclosure_for_invalid("driver configuration", config.get("mode")),
        )

    return _fresh_result(
        UNRESOLVED_MODE,
        EVIDENCE_UNRESOLVED,
        False,
        _disclosure_for_missing(),
    )


def evidence_line(result):
    """Single line of order prose for the MODE_EVIDENCE placeholder."""
    if result["resolved"]:
        if result["evidence"] == EVIDENCE_SESSION_META:
            return "Review session mode %s (from session metadata)." % result["mode"]
        return "Review session mode %s (from driver configuration)." % result["mode"]
    return result["disclosure"]
