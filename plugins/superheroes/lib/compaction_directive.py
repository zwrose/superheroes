#!/usr/bin/env python3
"""The one home of every compaction directive and every checkpoint-file path (#1814).

Nothing else in the plugin holds directive text or derives the checkpoint path: the
Claude Code mod and the PreCompact fallback hook both get their text from here (the mod
through this module's CLI), and SessionStart names the checkpoint file through
``checkpoint_path``.

Best-effort and stdlib-only. The public functions never raise; the CLI prints one JSON
object on stdout and exits 0 on success, 1 with ``{"ok": false, "reason": "<token>"}`` on a
refusal (argparse usage errors keep argparse's own exit 2).

    python3 -B compaction_directive.py path --session-id ID
    python3 -B compaction_directive.py mode --transcript P
    python3 -B compaction_directive.py instructions --session-id ID [--transcript P]
                                                    [--user-instructions TEXT]
"""
import argparse
import datetime
import glob
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import charter_detect
import config_dir

MODES = tuple(charter_detect.CHARTER_NAMES) + ("generic",)

_SESSION_ID_RE = re.compile(r"[A-Za-z0-9_-]{1,128}")

_DROP = """\
DROP (recoverable from GitHub or the ledger — do not spend summary budget):
- Verbatim tool output, file diffs, probe transcripts, and command stdout
"""

DIRECTIVES = {
    "showrunner": """\
Superheroes charter session — summarization directive for SHOWRUNNER.

PRESERVE (compact pointers and state, not raw artifacts):
- Resume-point pointer: where it lives in the session, not its full contents
- Live build lanes and their current state (fresh / stale / terminal / parked)
- Vet ordinal and which wave or build is under review
- Open owner decisions awaiting an answer
- Any hard line or standing owner ruling currently in force

""" + _DROP,
    "workhorse": """\
Superheroes charter session — summarization directive for WORKHORSE.

PRESERVE (compact pointers and state, not raw artifacts):
- Issue number being built
- The open PR and its build record (the PR body's build-record section) — the durable record
- Current work order and its scope fence
- Build worktree path and branch name
- Which receipts have been earned versus still owed
- Any open blocker or park condition

""" + _DROP,
    "detective": """\
Superheroes charter session — summarization directive for DETECTIVE.

PRESERVE (compact pointers and state, not raw artifacts):
- Incident under diagnosis and its issue number — the incident issue is the durable record
- Hypotheses already ruled out and what ruled each one out
- Demonstration state: what has been reproduced or A/B'd, and on which disposable copy
- Named diagnosis budget and how much of it is spent
- The standing prohibition: the examined surface is never edited

""" + _DROP,
    "discovery": """\
Superheroes charter session — summarization directive for DISCOVERY.

PRESERVE (compact pointers and state, not raw artifacts):
- The work item slug and the path of the spec draft
- Requirements agreed with the owner so far, including the unhappy paths
- Open questions still owed to the owner
- Where the owner's approval stands

""" + _DROP,
    "generic": """\
Superheroes session — summarization directive (no charter detected).

PRESERVE (compact pointers and state, not raw artifacts):
- In the owner's words: "notes on the important things to preserve, especially your role and responsibilities"
- The task in progress and its state
- Decisions made, and by whom
- What is waiting on the owner

""" + _DROP + """
AFTER compaction, open your first reply with a short recap of "where we are and what you need from me".
""",
}

_NOTES_HEADER = ("Checkpoint notes for this session (written %s, file %s) "
                 "— preserve their substance:")
_OWNER_HEADER = "The owner's own compaction instructions (take precedence where they conflict):"


# ----------------------------------------------------------------- mode
def detect_mode(transcript_path):
    """The charter detected in the transcript, or "generic". Never raises."""
    try:
        mode = charter_detect.detect_charter(transcript_path)
        return mode if mode in MODES else "generic"
    except Exception:
        return "generic"


# ----------------------------------------------------------------- paths
def _valid_session_id(session_id):
    return isinstance(session_id, str) and _SESSION_ID_RE.fullmatch(session_id) is not None


def checkpoint_dir(env=None):
    """``<config dir>/superheroes/checkpoints``, or None when the config dir is unresolvable."""
    try:
        root = config_dir.resolve(env=env)
        if not root:
            return None
        return os.path.join(root, "superheroes", "checkpoints")
    except Exception:
        return None


def _session_file(session_id, suffix, env):
    try:
        if not _valid_session_id(session_id):
            return None
        base = checkpoint_dir(env)
        if base is None:
            return None
        return os.path.join(base, session_id + suffix)
    except Exception:
        return None


def checkpoint_path(session_id, env=None):
    """This session's checkpoint notes file, or None (invalid session id / no config dir)."""
    return _session_file(session_id, ".md", env)


def delivered_marker_path(session_id, env=None):
    """The marker the mod touches once it has delivered the directive, or None."""
    return _session_file(session_id, ".delivered", env)


def find_transcript(session_id, env=None):
    """The first existing ``<config dir>/projects/*/<session_id>.jsonl``, or None.

    Used only when no transcript path was supplied."""
    try:
        if not _valid_session_id(session_id):
            return None
        root = config_dir.resolve(env=env)
        if not root:
            return None
        pattern = os.path.join(glob.escape(root), "projects", "*", session_id + ".jsonl")
        for candidate in sorted(glob.glob(pattern)):
            if os.path.isfile(candidate):
                return candidate
        return None
    except Exception:
        return None


# ----------------------------------------------------------------- notes
def read_notes(session_id, env=None, max_chars=20000):
    """``(text, mtime)`` of this session's checkpoint notes, or ``("", None)``."""
    try:
        path = checkpoint_path(session_id, env)
        if path is None:
            return "", None
        mtime = os.stat(path).st_mtime
        with open(path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        if not text.strip():
            return "", None
        if len(text) > max_chars:
            text = (text[:max_chars].rstrip("\n")
                    + "\n…(checkpoint notes truncated at %d characters — full file at %s)"
                    % (max_chars, path))
        return text, mtime
    except Exception:
        return "", None


def _iso_utc(mtime):
    try:
        stamp = datetime.datetime.fromtimestamp(mtime, tz=datetime.timezone.utc)
        return stamp.strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        return "unknown time"


def compose(mode, notes="", notes_path=None, notes_mtime=None, user_instructions=None):
    """The directive for ``mode`` (unknown → generic), then the checkpoint notes section when
    ``notes`` is non-empty, then the owner's own instructions when non-empty. Pure."""
    parts = [DIRECTIVES.get(mode) or DIRECTIVES["generic"]]
    if notes and notes.strip():
        header = _NOTES_HEADER % (_iso_utc(notes_mtime) if notes_mtime is not None
                                  else "unknown time", notes_path or "unknown")
        parts.append(header + "\n" + notes.strip("\n") + "\n")
    if user_instructions and user_instructions.strip():
        parts.append(_OWNER_HEADER + "\n" + user_instructions.strip("\n") + "\n")
    return "\n".join(p if p.endswith("\n") else p + "\n" for p in parts)


# ----------------------------------------------------------------- delivery marker
def delivered_recently(session_id, env=None, window_seconds=120, now=None):
    """True only when THIS session's marker exists and its mtime is within the window."""
    try:
        marker = delivered_marker_path(session_id, env)
        if marker is None:
            return False
        mtime = os.stat(marker).st_mtime
        current = time.time() if now is None else now
        return abs(current - mtime) <= window_seconds
    except Exception:
        return False


def consume_delivered(session_id, env=None, window_seconds=120, now=None):
    """One-shot read of this session's delivery marker: True when it was fresh, and the marker
    is deleted so a retry of the same compaction cannot reuse this attempt's evidence."""
    try:
        if not delivered_recently(session_id, env, window_seconds, now):
            return False
        marker = delivered_marker_path(session_id, env)
        try:
            os.remove(marker)
        except FileNotFoundError:
            pass
        return True
    except Exception:
        return False


# ----------------------------------------------------------------- CLI
def _emit(obj, code=0):
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    return code


def _refuse(reason):
    return _emit({"ok": False, "reason": reason}, 1)


def _glue_user_instructions(argv):
    """Fold ``--user-instructions TEXT`` into ``--user-instructions=TEXT`` so owner text that
    starts with ``-`` is read as the value, not mistaken for an option."""
    out = []
    i = 0
    while i < len(argv):
        if argv[i] == "--user-instructions" and i + 1 < len(argv):
            out.append("--user-instructions=" + argv[i + 1])
            i += 2
        else:
            out.append(argv[i])
            i += 1
    return out


def _build_parser():
    ap = argparse.ArgumentParser(prog="compaction_directive.py")
    sub = ap.add_subparsers(dest="verb", required=True)
    p = sub.add_parser("path")
    p.add_argument("--session-id", required=True)
    m = sub.add_parser("mode")
    m.add_argument("--transcript", required=True)
    i = sub.add_parser("instructions")
    i.add_argument("--session-id", required=True)
    i.add_argument("--transcript")
    i.add_argument("--user-instructions")
    return ap


def _verb_path(args):
    if not _valid_session_id(args.session_id):
        return _refuse("session-id-invalid")
    path = checkpoint_path(args.session_id)
    marker = delivered_marker_path(args.session_id)
    if path is None or marker is None:
        return _refuse("config-dir-unresolved")
    return _emit({"ok": True, "path": path, "markerPath": marker})


def _verb_mode(args):
    return _emit({"ok": True, "mode": detect_mode(args.transcript)})


def _verb_instructions(args):
    if not _valid_session_id(args.session_id):
        return _refuse("session-id-invalid")
    path = checkpoint_path(args.session_id)
    marker = delivered_marker_path(args.session_id)
    if path is None or marker is None:
        return _refuse("config-dir-unresolved")
    transcript = args.transcript or find_transcript(args.session_id)
    mode = detect_mode(transcript) if transcript else "generic"
    notes, mtime = read_notes(args.session_id)
    text = compose(mode, notes, path, mtime, args.user_instructions)
    return _emit({"ok": True, "mode": mode, "instructions": text, "notesPath": path,
                  "notesFound": bool(notes), "markerPath": marker})


def main(argv=None):
    argv = _glue_user_instructions(list(sys.argv[1:] if argv is None else argv))
    args = _build_parser().parse_args(argv)     # argparse usage errors exit 2 by design
    try:
        verb = {"path": _verb_path, "mode": _verb_mode, "instructions": _verb_instructions}
        return verb[args.verb](args)
    except Exception:
        return _refuse("internal-error")


if __name__ == "__main__":
    sys.exit(main())
