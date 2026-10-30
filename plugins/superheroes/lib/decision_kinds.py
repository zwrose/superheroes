#!/usr/bin/env python3
"""Decision-kind vocabulary and the terminal-verdict tables keyed on it.

Holds the decision kinds, the driver's verdict names, the verdict-to-terminal-state map and the
(verdict, decision kind) cause table, with the two lookups over them. Stdlib-only leaf: it
imports nothing from this plugin, so the round driver and the review record may both import it.
"""
LANE_EXPANDED_RECOMPOSE = "lane-expanded-recompose"

DECISION_KINDS = (
    "audit-attributed-change",
    "audit-echo-mismatch",
    "audit-provenance-fail",
    "audit-unnamed-change",
    "author-justified-drop",
    "break-it-change",
    "break-it-kept",
    "break-it-run",
    "break-it-test-mismatch",
    "cannot-certify",
    "capped-with-open-blocker",
    "capped-with-open-critical",
    "confirmation-rearm",
    "converged",
    "extra-audit-open",
    "extra-audit-ordered",
    "fix-batch-excluded",
    "fix-batch-ruled",
    "fix-batch-split",
    "fix-keeps-failing",
    "fix-surface-unknown",
    LANE_EXPANDED_RECOMPOSE,
    "later-round-panel-retired",
    "not-discharged",
    "out-of-scope-fix-spent",
    "owner-choice-held",
    "owner-choice-open",
    "panel-seat-missing",
    "receipt-missing-seat",
    "returning-review",
    "ruling-carried",
    "ruling-carry-revoked",
    "ruling-no-live-finding",
    "ruling-recorded",
    "round-cap",
    "round-ceiling",
    "scoped-finder-skipped",
    "seat-engaged-artifact",
    "seat-map-constraint-violated",
    "seat-vacuous",
    "second-test-held",
    "second-test-held-again",
    "second-test-unseatable",
    "self-recovery",
    "spawned-audit-not-discharged",
    "stall-choice",
    "stall-menu",
    "synthesis-no-survivors",
    "synthesis-unseatable",
    "unknown-surface",
    "verifier-not-executed",
    "verifier-refuted",
    "verify-fail",
    "verify-rerun",
    "verify-rerun-head-moved",
    "verify-rerun-tree-changed",
    "verify-skip-but-configured",
    "verify-skipped",
    "verify-unresolved",
)

CERTIFIED_VERDICTS = (
    "converged",
    "halted",
    # held and stalled: read-only, for sessions an earlier version finished
    "held",
    "stalled",
    "cannot-certify",
    "capped-with-open-critical",
    "capped-with-open-blocker",
    "handed-back",
)
ATTESTED_VERDICT = "uncertified-manual"
ALL_VERDICTS = CERTIFIED_VERDICTS + (ATTESTED_VERDICT,)

VERDICT_TO_TERMINAL_STATE = {
    "converged": "certified",
    "handed-back": "cap",
    "capped-with-open-critical": "cap",
    "capped-with-open-blocker": "cap",
    "cannot-certify": "cannot-certify",
    "halted": "cannot-certify",
    "held": "cannot-certify",
    "stalled": "cannot-certify",
    ATTESTED_VERDICT: "cannot-certify",
}

_TERMINAL_CAUSE_TABLE = {
    ("converged", "converged"): None,
    ("capped-with-open-critical", "capped-with-open-critical"): {
        "kind": "non-loop",
        "reason": "open-findings",
    },
    ("capped-with-open-blocker", "capped-with-open-blocker"): {
        "kind": "non-loop",
        "reason": "open-findings",
    },
    ("cannot-certify", "cannot-certify"): {"kind": "loop", "reason": "detector"},
    ("halted", "verify-fail"): {"kind": "loop", "reason": "detector"},
    ("halted", "verify-rerun-head-moved"): {"kind": "loop", "reason": "detector"},
    ("halted", "verify-rerun-tree-changed"): {"kind": "loop", "reason": "detector"},
    ("halted", "verify-skip-but-configured"): {"kind": "loop", "reason": "detector"},
    ("halted", "verify-unresolved"): {"kind": "loop", "reason": "detector"},
    ("halted", LANE_EXPANDED_RECOMPOSE): {"kind": "loop", "reason": "detector"},
    ("halted", "round-ceiling"): {"kind": "non-loop", "reason": "budget"},
    # The handed-back rows: the PR goes back to its owner with the review's findings still open.
    ("handed-back", "round-cap"): {"kind": "non-loop", "reason": "open-findings"},
    ("handed-back", "fix-keeps-failing"): {"kind": "loop", "reason": "fixer-cycle"},
    ("handed-back", "owner-choice-open"): {"kind": "non-loop", "reason": "open-findings"},
    ("handed-back", "extra-audit-open"): {"kind": "non-loop", "reason": "open-findings"},
    ("handed-back", "fix-surface-unknown"): {"kind": "non-loop", "reason": "open-findings"},
    ("handed-back", "later-round-panel-retired"): {"kind": "non-loop", "reason": "open-findings"},
    # read-only, for sessions an earlier version finished (the driver never writes held or stalled again)
    ("held", "stall-choice"): {"kind": "loop", "reason": "latch"},
    ("stalled", "stall-choice"): {"kind": "loop", "reason": "latch"},
    ("stalled", "stall-menu"): {"kind": "loop", "reason": "latch"},
    (ATTESTED_VERDICT, "cannot-certify"): {"kind": "loop", "reason": "detector"},
    ("cannot-certify", "self-recovery"): {"kind": "loop", "reason": "fixer-cycle"},
}


def map_verdict_to_terminal_state(verdict):
    """Totality table 1 — refuse unknown verdicts."""
    if verdict not in ALL_VERDICTS:
        return None
    return VERDICT_TO_TERMINAL_STATE.get(verdict)


def map_terminal_cause(verdict, decision_key):
    """Totality table 2 — refuse unlisted combinations."""
    if verdict not in ALL_VERDICTS:
        return None
    if decision_key not in DECISION_KINDS:
        return None
    terminal_state = VERDICT_TO_TERMINAL_STATE.get(verdict)
    if terminal_state == "certified":
        if (verdict, decision_key) in _TERMINAL_CAUSE_TABLE:
            return None
        if verdict == "converged" and decision_key == "converged":
            return None
        return None
    return _TERMINAL_CAUSE_TABLE.get((verdict, decision_key))
