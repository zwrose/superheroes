#!/usr/bin/env python3
"""PreCompact hook — the plain-text fallback for the compaction directive (#911, #1814).

Claude Code appends this hook's raw stdout to the compaction instructions; it ignores
``additionalContext``, so the output here is plain text, not JSON. The directive text and the
checkpoint-file path both come from ``lib/compaction_directive.py`` — this hook holds neither.

The compaction mod is the primary path. When it has already delivered for this session (a
fresh ``<session_id>.delivered`` marker, consumed here so a retry cannot reuse it) this hook prints nothing; otherwise it prints the
directive for the detected mode plus this session's checkpoint notes. The owner's own
``custom_instructions`` are deliberately NOT repeated — the harness already carries them.

Fail-open: never exit non-zero, never raise — blocking auto-compact can wedge a session.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lib"))


def main():
    try:
        import compaction_directive
        raw = sys.stdin.read() or "{}"
        payload = json.loads(raw)
    except Exception:
        return 0
    if not isinstance(payload, dict):
        return 0

    session_id = payload.get("session_id")
    if compaction_directive.consume_delivered(session_id):
        return 0

    mode = compaction_directive.detect_mode(payload.get("transcript_path"))
    notes, mtime = compaction_directive.read_notes(session_id)
    text = compaction_directive.compose(
        mode, notes, compaction_directive.checkpoint_path(session_id), mtime)
    sys.stdout.write(text.rstrip("\n") + "\n")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
