#!/usr/bin/env python3
"""PreCompact hook — charter-aware compaction preserve/drop skeleton (#911).

Emits a top-level ``additionalContext`` key (not ``hookSpecificOutput``) so the
harness accepts the payload and steers the compaction summarizer. Fail-open:
never exit non-zero, never raise — blocking auto-compact can wedge a session.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lib"))

from charter_detect import detect_charter

_COMPACTION_SKELETONS = {
    "showrunner": """\
Superheroes charter session — summarization directive for SHOWRUNNER.

PRESERVE (compact pointers and state, not raw artifacts):
- Resume-point pointer: where it lives in the session, not its full contents
- Live build lanes and their current state (fresh / stale / terminal / parked)
- Vet ordinal and which wave or build is under review
- Open owner decisions awaiting an answer
- Any hard line or standing owner ruling currently in force

DROP (recoverable from GitHub or the ledger — do not spend summary budget):
- Verbatim tool output, file diffs, probe transcripts, and command stdout
""",
    "workhorse": """\
Superheroes charter session — summarization directive for WORKHORSE.

PRESERVE (compact pointers and state, not raw artifacts):
- Issue number being built
- Current work order and its scope fence
- Build worktree path and branch name
- Which receipts have been earned versus still owed
- Any open blocker or park condition

DROP (recoverable from GitHub or the ledger — do not spend summary budget):
- Verbatim tool output, file diffs, probe transcripts, and command stdout
""",
    "detective": """\
Superheroes charter session — summarization directive for DETECTIVE.

PRESERVE (compact pointers and state, not raw artifacts):
- Incident under diagnosis and its issue number
- Hypotheses already ruled out and what ruled them out
- Demonstration state: what has been reproduced or A/B'd, and on which disposable copy
- Named diagnosis budget and how much of it is spent
- The standing prohibition: the examined surface is never edited

DROP (recoverable from GitHub or the ledger — do not spend summary budget):
- Verbatim tool output, file diffs, probe transcripts, and command stdout
""",
}


def main():
    try:
        raw = sys.stdin.read() or "{}"
        payload = json.loads(raw)
    except (ValueError, TypeError):
        return 0
    if not isinstance(payload, dict):
        return 0

    charter = detect_charter(payload.get("transcript_path"))
    if charter is None:
        return 0

    skeleton = _COMPACTION_SKELETONS.get(charter)
    if not skeleton:
        return 0

    sys.stdout.write(json.dumps({"additionalContext": skeleton}) + "\n")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
