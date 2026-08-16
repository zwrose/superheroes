#!/usr/bin/env python3
"""Charter detection from session transcripts.

Long-lived superheroes sessions run under one of three charters (showrunner,
workhorse, or detective), invoked via slash command. Hooks need to know which
charter is active without wedging compaction — so detection is best-effort,
never raises, and reads the append-only JSONL transcript forward from the
start (charter invocations appear early; a tail window would miss them in long
sessions).
"""
import json
import os
import re
import sys

MAX_SCAN_BYTES = 200 * 1024 * 1024

CHARTER_NAMES = ("showrunner", "workhorse", "detective")

_PREFILTER = "/superheroes:"
_CHARTER_RE = re.compile(
    r"<command-name>\s*/superheroes:(%s)\s*</command-name>"
    % "|".join(CHARTER_NAMES)
)


def _charter_from_record(rec):
    if not isinstance(rec, dict):
        return None
    if rec.get("type") != "user":
        return None
    if rec.get("isSidechain"):
        return None
    msg = rec.get("message")
    if not isinstance(msg, dict):
        return None
    content = msg.get("content")
    if not isinstance(content, str):
        return None
    m = _CHARTER_RE.search(content)
    return m.group(1) if m else None


def _breadcrumb(transcript_path, exc):
    """One-line diagnostic to stderr. Path and exception type only — never file contents."""
    try:
        sys.stderr.write(
            "superheroes charter_detect: %s — %s\n" % (transcript_path, type(exc).__name__)
        )
    except Exception:
        pass


def detect_charter(transcript_path):
    """Return a charter name from CHARTER_NAMES, or None."""
    try:
        if not transcript_path:
            return None
        try:
            os.stat(transcript_path)
        except FileNotFoundError:
            return None
        except OSError as exc:
            _breadcrumb(transcript_path, exc)
            return None
        if not os.path.isfile(transcript_path):
            return None
        last = None
        scanned = 0
        with open(transcript_path, "rb") as fh:
            for line_b in fh:
                if scanned >= MAX_SCAN_BYTES:
                    break
                if scanned + len(line_b) > MAX_SCAN_BYTES:
                    line_b = line_b[: MAX_SCAN_BYTES - scanned]
                scanned += len(line_b)
                if _PREFILTER not in line_b.decode("utf-8", errors="replace"):
                    continue
                try:
                    rec = json.loads(line_b.decode("utf-8", errors="replace"))
                except (json.JSONDecodeError, ValueError, TypeError):
                    continue
                found = _charter_from_record(rec)
                if found is not None:
                    last = found
        return last
    except Exception as exc:
        _breadcrumb(transcript_path, exc)
        return None
