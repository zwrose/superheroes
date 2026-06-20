#!/usr/bin/env python3
"""Validate that a commit subject (or PR title) is a Conventional Commit.

Used by CI to gate what reaches `main`:
  - the PR-title check (the squash subject == the PR title), and
  - a defensive check on the latest `main` commit subject (catches a non-squash
    merge that lands an unvalidated subject — see the plan's R5).

Conventional Commits 1.0.0, subject line only:
  <type>[optional (scope)][!]: <description>
`type` is one of a fixed set; the scope is any non-empty parenthesized token; `!`
marks a breaking change.
"""
from __future__ import annotations

import re
import sys

TYPES = (
    "feat", "fix", "docs", "style", "refactor", "perf",
    "test", "build", "ci", "chore", "revert",
)

_SUBJECT_RE = re.compile(
    r"^(?:" + "|".join(TYPES) + r")"  # type
    r"(?:\([^()\n]+\))?"               # optional (scope)
    r"!?"                              # optional breaking-change marker
    r": .+$"                          # ": " then a non-empty description
)


def validate(subject: str) -> str | None:
    """Return None if `subject`'s first line is a valid Conventional Commit
    subject, else an error message."""
    first = subject.splitlines()[0] if subject else ""
    if not first.strip():
        return "empty commit subject"
    if not _SUBJECT_RE.match(first):
        return (
            f"not a Conventional Commit: {first!r}\n"
            f"  expected '<type>[(scope)][!]: <description>' "
            f"with type in: {', '.join(TYPES)}"
        )
    return None


def main(argv: list[str]) -> int:
    subject = argv[0] if argv else sys.stdin.read()
    err = validate(subject)
    if err:
        sys.stderr.write("error: " + err + "\n")
        return 1
    print("✓ valid Conventional Commit subject")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
