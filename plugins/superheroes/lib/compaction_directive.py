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
    python3 -B compaction_directive.py save --session-id ID        (notes text on stdin)
    python3 -B compaction_directive.py unmark --session-id ID --since MS --until MS
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
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import charter_detect
import config_dir

MODES = tuple(charter_detect.CHARTER_NAMES) + ("generic",)

_SESSION_ID_RE = re.compile(r"[A-Za-z0-9_-]{1,128}")

# The one home of how long a session's notes file is kept before ``reap`` removes it.
NOTES_MAX_AGE_DAYS = 30

_DROP = """\
DROP (recoverable from GitHub or the ledger — do not spend summary budget):
- Verbatim tool output, file diffs, probe transcripts, and command stdout
"""

# The post-compaction recap rule — one home; SessionStart recovery (session_context) reuses it.
RECAP_INSTRUCTION = 'open your first reply with a short recap of "where we are and what you need from me".'

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

""" + _DROP + "\nAFTER compaction, " + RECAP_INSTRUCTION + "\n",
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


def checkpoint_dir(env=None, cwd=None):
    """``<config dir>/superheroes/checkpoints``, or None when the config dir is unresolvable.

    A relative ``CLAUDE_CONFIG_DIR`` resolves against ``cwd`` (the session's working directory);
    with no absolute ``cwd`` it is unresolvable, so the result is None."""
    try:
        root = config_dir.resolve(env=env, cwd=cwd)
        if not root:
            return None
        return os.path.join(root, "superheroes", "checkpoints")
    except Exception:
        return None


def _session_file(session_id, suffix, env, cwd=None):
    try:
        if not _valid_session_id(session_id):
            return None
        base = checkpoint_dir(env, cwd)
        if base is None:
            return None
        return os.path.join(base, session_id + suffix)
    except Exception:
        return None


def checkpoint_path(session_id, env=None, cwd=None):
    """This session's checkpoint notes file, or None (invalid session id / no config dir)."""
    return _session_file(session_id, ".md", env, cwd)


def delivered_marker_path(session_id, env=None, cwd=None):
    """The marker the mod touches once it has delivered the directive, or None."""
    return _session_file(session_id, ".delivered", env, cwd)


def find_transcript(session_id, env=None, cwd=None):
    """The first existing ``<config dir>/projects/*/<session_id>.jsonl``, or None.

    Used only when no transcript path was supplied."""
    try:
        if not _valid_session_id(session_id):
            return None
        root = config_dir.resolve(env=env, cwd=cwd)
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
def read_notes(session_id, env=None, max_chars=20000, cwd=None):
    """``(text, mtime)`` of this session's checkpoint notes, or ``("", None)``."""
    try:
        path = checkpoint_path(session_id, env, cwd)
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


def _atomic_write(path, text):
    """Write ``text`` to ``path`` through a temp file in the same directory and ``os.replace``:
    the destination is only ever absent/old or complete. Raises on I/O failure (temp removed)."""
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".checkpoint.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def save_notes(session_id, text, env=None, cwd=None):
    """Atomically replace this session's checkpoint notes with ``text``; the notes path, or
    ``None`` when there is no path. The destination is only replaced once the whole text is
    on disk, so a failed save leaves the last good notes intact. Raises on I/O failure."""
    path = checkpoint_path(session_id, env, cwd)
    if path is None:
        return None
    _atomic_write(path, text)
    return path


def mark_delivered(session_id, env=None, now=None, cwd=None):
    """Atomically publish this session's delivery marker (a complete timestamp or no marker at
    all, so a failed write cannot leave an empty or partial marker for the PreCompact fallback to
    consume); the marker path, or ``None`` when there is no path. Raises on I/O failure."""
    path = delivered_marker_path(session_id, env, cwd)
    if path is None:
        return None
    _atomic_write(path, str(int((time.time() if now is None else now) * 1000)))
    return path


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
def delivered_recently(session_id, env=None, window_seconds=120, now=None, cwd=None):
    """True only when THIS session's marker exists and its mtime is within the window."""
    try:
        marker = delivered_marker_path(session_id, env, cwd)
        if marker is None:
            return False
        mtime = os.stat(marker).st_mtime
        current = time.time() if now is None else now
        return abs(current - mtime) <= window_seconds
    except Exception:
        return False


def consume_delivered(session_id, env=None, window_seconds=120, now=None, cwd=None):
    """One-shot read of this session's delivery marker: True when it was fresh, and the marker
    is deleted so a retry of the same compaction cannot reuse this attempt's evidence."""
    try:
        if not delivered_recently(session_id, env, window_seconds, now, cwd):
            return False
        marker = delivered_marker_path(session_id, env, cwd)
        try:
            os.remove(marker)
        except FileNotFoundError:
            pass
        return True
    except Exception:
        return False


def unmark_attempt(session_id, since_ms, until_ms, env=None, cwd=None):
    """Remove this session's delivery marker when the millisecond stamp inside it (written by
    ``mark_delivered``) lies within ``[since_ms, until_ms]``: the marker of a compaction attempt
    that did not complete. True when removed; a missing marker, unreadable content or an
    out-of-window stamp leaves it alone. Never raises."""
    try:
        marker = delivered_marker_path(session_id, env, cwd)
        if marker is None:
            return False
        with open(marker, encoding="utf-8") as fh:
            stamp = int(fh.read().strip())
        if not since_ms <= stamp <= until_ms:
            return False
        os.remove(marker)
        return True
    except Exception:
        return False


# ----------------------------------------------------------------- reaping
def reap(session_id, env=None, cwd=None, now=None):
    """Remove stale files from the checkpoint directory: ``<id>.md`` notes older than
    ``NOTES_MAX_AGE_DAYS`` (by mtime) and ``<id>.delivered`` markers outside the delivery window.
    Only regular files with a valid session-id name, never a symlink, never a subdirectory's
    content, never ``session_id``'s own files. Returns the number removed; never raises."""
    removed = 0
    try:
        if not _valid_session_id(session_id):
            return 0
        base = checkpoint_dir(env, cwd)
        if base is None:
            return 0
        current = time.time() if now is None else now
        with os.scandir(base) as entries:
            listing = list(entries)
        for entry in listing:
            try:
                stem, suffix = os.path.splitext(entry.name)
                if suffix not in (".md", ".delivered") or not _valid_session_id(stem) or stem == session_id:
                    continue
                if entry.is_symlink() or not entry.is_file(follow_symlinks=False):
                    continue
                if suffix == ".md":
                    is_stale = current - entry.stat(follow_symlinks=False).st_mtime > NOTES_MAX_AGE_DAYS * 86400
                else:
                    is_stale = not delivered_recently(stem, env, now=current, cwd=cwd)
                if is_stale:
                    os.remove(entry.path)
                    removed += 1
            except Exception:
                continue
    except Exception:
        pass
    return removed


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


# The CLI vocabulary (verb names and flag names) lives in compaction_cli.json, the one
# definition the Claude Code mod (hooks/mod/argv.ts) reads too. Whether a flag is
# required is this parser's own semantics and stays here, keyed by the JSON's role names.
_CLI_VOCABULARY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "compaction_cli.json")
_REQUIRED_ROLES = {
    "path": ("sessionId",),
    "save": ("sessionId",),
    "mark": ("sessionId",),
    "unmark": ("sessionId", "since", "until"),
    "mode": ("transcriptPath",),
    "instructions": ("sessionId",),
}


def _build_parser():
    with open(_CLI_VOCABULARY, encoding="utf-8") as fh:
        verbs = json.load(fh)["verbs"]
    ap = argparse.ArgumentParser(prog="compaction_directive.py")
    sub = ap.add_subparsers(dest="verb", required=True)
    for verb, flags in verbs.items():
        vp = sub.add_parser(verb)
        for role, flag in flags.items():
            vp.add_argument(flag, required=role in _REQUIRED_ROLES[verb])
    return ap


def _verb_path(args):
    if not _valid_session_id(args.session_id):
        return _refuse("session-id-invalid")
    cwd = os.getcwd()
    path = checkpoint_path(args.session_id, cwd=cwd)
    marker = delivered_marker_path(args.session_id, cwd=cwd)
    if path is None or marker is None:
        return _refuse("config-dir-unresolved")
    return _emit({"ok": True, "path": path, "markerPath": marker})


def _verb_save(args):
    if not _valid_session_id(args.session_id):
        return _refuse("session-id-invalid")
    text = sys.stdin.read()
    if not text.strip():
        return _refuse("empty-notes")
    path = save_notes(args.session_id, text, cwd=os.getcwd())
    if path is None:
        return _refuse("config-dir-unresolved")
    return _emit({"ok": True, "path": path})


def _verb_mark(args):
    if not _valid_session_id(args.session_id):
        return _refuse("session-id-invalid")
    path = mark_delivered(args.session_id, cwd=os.getcwd())
    if path is None:
        return _refuse("config-dir-unresolved")
    return _emit({"ok": True, "path": path})


def _verb_unmark(args):
    if not _valid_session_id(args.session_id):
        return _refuse("session-id-invalid")
    try:
        since, until = int(args.since), int(args.until)
    except ValueError:
        return _refuse("window-invalid")
    cwd = os.getcwd()
    if delivered_marker_path(args.session_id, cwd=cwd) is None:
        return _refuse("config-dir-unresolved")
    return _emit({"ok": True, "removed": unmark_attempt(args.session_id, since, until, cwd=cwd)})


def _verb_mode(args):
    return _emit({"ok": True, "mode": detect_mode(args.transcript)})


def _verb_instructions(args):
    if not _valid_session_id(args.session_id):
        return _refuse("session-id-invalid")
    cwd = os.getcwd()
    path = checkpoint_path(args.session_id, cwd=cwd)
    marker = delivered_marker_path(args.session_id, cwd=cwd)
    if path is None or marker is None:
        return _refuse("config-dir-unresolved")
    transcript = args.transcript or find_transcript(args.session_id, cwd=cwd)
    mode = detect_mode(transcript) if transcript else "generic"
    notes, mtime = read_notes(args.session_id, cwd=cwd)
    text = compose(mode, notes, path, mtime, args.user_instructions)
    return _emit({"ok": True, "mode": mode, "instructions": text, "notesPath": path,
                  "notesFound": bool(notes), "markerPath": marker})


def main(argv=None):
    argv = _glue_user_instructions(list(sys.argv[1:] if argv is None else argv))
    args = _build_parser().parse_args(argv)     # argparse usage errors exit 2 by design
    try:
        verb = {"path": _verb_path, "save": _verb_save, "mark": _verb_mark, "unmark": _verb_unmark,
                "mode": _verb_mode, "instructions": _verb_instructions}
        return verb[args.verb](args)
    except Exception:
        return _refuse("internal-error")


if __name__ == "__main__":
    sys.exit(main())
