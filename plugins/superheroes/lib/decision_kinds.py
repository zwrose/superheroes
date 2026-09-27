#!/usr/bin/env python3
"""Decision-kind vocabulary shared by the round driver and certification writer.

Stdlib-only leaf — both consumers may import this module; the writer must not import the
driver or engine adapter (register R5).
"""
DECISION_KINDS = (
    "audit-echo-mismatch",
    "audit-provenance-fail",
    "author-justified-drop",
    "canary-failed",
    "canary-outcome-failed",
    "canary-plant-undetected",
    "canary-unverified",
    "cannot-certify",
    "capped-with-open-blocker",
    "capped-with-open-critical",
    "confirmation-rearm",
    "converged",
    "fix-batch-excluded",
    "fix-batch-split",
    "judgment-fail-closed",
    "judgment-gate",
    "judgment-skip",
    "not-discharged",
    "panel-incomplete-canary-gap",
    "panel-seat-missing",
    "receipt-missing-seat",
    "resume-confirmation",
    "round-ceiling",
    "scoped-finder-skipped",
    "seat-engaged-artifact",
    "seat-map-constraint-violated",
    "seat-vacuous",
    "self-recovery",
    "stall-choice",
    "stall-menu",
    "unknown-surface",
    "verifier-refuted",
    "verify-fail",
    "verify-skip-but-configured",
    "verify-skipped",
    "verify-unresolved",
)
