#!/usr/bin/env python3
"""The one home of the review seat-to-dimension association: which agent seat reviews which lens.

A leaf (imports nothing): dispatch (`round_driver`, `review_round_policy`) and the learning loop's
tally (`review_learning`) both read it, so a seat rename or a lens change is made here once.
"""

# The five shared code-leg reviewers, each to its agent-file stem.
AGENT_SUFFIX = {"architecture-reviewer": "architecture", "code-reviewer": "code",
                "security-reviewer": "security", "test-role": "test",
                "premortem-reviewer": "premortem"}
# A seat stem (or a finding's policy-subject word) to its rubric dimension label.
SUBJECT_FALLBACK = {
    "test": "Test",
    "security": "Security",
    "code": "Code",
    "architecture": "Architecture",
    "failure": "Failure-Mode",
    "premortem": "Failure-Mode",
}


def dimension_label(seat):
    """The rubric dimension label a seat reviews, or None for a seat outside the shared five."""
    stem = AGENT_SUFFIX.get(seat)
    return SUBJECT_FALLBACK.get(stem.split("-")[0].lower()) if isinstance(stem, str) and stem else None


# The lower-cased dimension label to its seat (the inverse of `dimension_label`).
DIMENSION_SEAT = {dimension_label(seat).lower(): seat for seat in AGENT_SUFFIX}
