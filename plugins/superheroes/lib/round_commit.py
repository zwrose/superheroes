#!/usr/bin/env python3
"""Two-phase commit primitive for the review round driver (#918).

CONTRACT. This is the transaction seam the round driver uses to keep durable on-disk artifacts
mutually consistent: a store envelope and its blob, a manifest and its anchor in state, a receipt,
a sidecar, state and journal rows. Targets are written only after ``SEALED`` is durable, and
``SEALED`` is written only after every staged part payload is durable.

Stdlib-only. Imports ``round_records`` for session containment only — no cycle back.
"""
import errno
import hashlib
import json
import os
import shutil
import uuid

from round_records import _guard_within

# =============================================================================================
# schema constants
# =============================================================================================

SCHEMA = "superheroes/round-commit@1"

_PART_REPLACE = "replace-file"
_PART_JOURNAL = "journal-append"
_PART_SIDECAR = "external-sidecar"

_SEALED = "SEALED"
_DONE = "DONE"
_INTENT = "intent.json"
_PARTS = "parts"

_STOP_POINTS = frozenset(("staged", "sealed", "applied", "done", "renamed"))

_DURABILITY_UNSUPPORTED = (errno.EINVAL, errno.ENOTSUP, errno.EPERM)


# =============================================================================================
# exceptions
# =============================================================================================

class CommitRefused(Exception):
    """A commit or recovery step refused — carries a stable ``reason`` token and optional detail."""

    def __init__(self, reason, detail=None):
        super().__init__(reason if detail is None else "%s: %s" % (reason, detail))
        self.reason = reason
        self.detail = detail


class StopPoint(Exception):
    """Raised by the injected stop-point for crash-recovery tests. Carries ``where``."""

    def __init__(self, where):
        super().__init__(where)
        self.where = where


# =============================================================================================
# durability helpers
# =============================================================================================

def _canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def fsync_dir_strict(directory):
    """Fsync a directory entry — every ``OSError`` propagates (no errno tolerance)."""
    fd = None
    try:
        fd = os.open(directory, os.O_RDONLY)
        os.fsync(fd)
    finally:
        if fd is not None:
            os.close(fd)


def fsync_dir_tolerant(directory):
    """Legacy directory fsync — swallow only the three exotic-filesystem errnos."""
    fd = None
    try:
        fd = os.open(directory, os.O_RDONLY)
        os.fsync(fd)
    except OSError as exc:
        if exc.errno not in _DURABILITY_UNSUPPORTED:
            raise
    finally:
        if fd is not None:
            os.close(fd)


def atomic_write_bytes(path, data):
    """Write bytes atomically: tmp → flush → fsync(file) → replace → tolerant parent fsync."""
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "wb") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)
    fsync_dir_tolerant(parent)
    return path


def atomic_write_json(path, obj):
    """Canonical JSON with trailing newline, via ``atomic_write_bytes``."""
    return atomic_write_bytes(path, (_canonical(obj) + "\n").encode("utf-8"))


def commits_root(session_dir):
    return os.path.join(session_dir, "commits")


# =============================================================================================
# path helpers
# =============================================================================================

def _session_relative(session_dir, absolute_path):
    root = os.path.realpath(session_dir)
    resolved = os.path.realpath(os.path.abspath(absolute_path))
    if not resolved.startswith(root + os.sep):
        raise CommitRefused("target-escapes-session", absolute_path)
    return os.path.relpath(resolved, root)


def _resolve_session_relative(session_dir, rel_path):
    joined = os.path.join(session_dir, rel_path)
    try:
        return _guard_within(session_dir, joined)
    except ValueError as exc:
        raise CommitRefused("target-escapes-session", str(exc))


def _strict_fsync_staging(directory):
    """Strict directory fsync on the staging path — unsupported fsync becomes a refusal."""
    try:
        fsync_dir_strict(directory)
    except OSError as exc:
        if exc.errno in _DURABILITY_UNSUPPORTED:
            raise CommitRefused("commit-durability-unsupported", str(exc))
        raise


def _ensure_parent_dirs_strict(path):
    """Create missing ancestor directories, fsyncing each newly created one strictly.

    Also fsyncs the deepest pre-existing ancestor so the link naming the topmost
    newly created directory is durable — same contract as ``_strict_fsync_staging``.
    """
    parent = os.path.dirname(os.path.abspath(path))
    if not parent:
        return
    created = []
    current = parent
    while current and not os.path.isdir(current):
        created.append(current)
        current = os.path.dirname(current)
    if not created:
        return
    for directory in reversed(created):
        os.makedirs(directory, exist_ok=True)
        fsync_dir_strict(directory)
    if os.path.isdir(current):
        fsync_dir_strict(current)


def _read_intent(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.loads(fh.read()), None
    except OSError:
        return None, "missing"
    except ValueError:
        return None, "unparseable"


def _is_commit_id(name):
    return len(name) == 32 and all(c in "0123456789abcdef" for c in name)


def _cleanup_name(commit_id):
    return ".cleanup-%s" % commit_id


def _parse_stop_at(stop_at):
    if stop_at is None:
        return None
    if stop_at in _STOP_POINTS:
        return stop_at
    if stop_at.startswith("part:"):
        try:
            int(stop_at.split(":", 1)[1])
        except (IndexError, ValueError):
            raise CommitRefused("unknown-stop-point", stop_at)
        return stop_at
    raise CommitRefused("unknown-stop-point", stop_at)


# =============================================================================================
# journal helpers
# =============================================================================================

def _journal_has_append_id(journal_path, append_id):
    try:
        with open(journal_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    parsed = json.loads(line)
                except ValueError:
                    continue
                if isinstance(parsed, dict) and parsed.get("appendId") == append_id:
                    return True
    except OSError:
        pass
    return False


def _apply_journal_append(session_dir, part_spec, entry):
    journal_path = _resolve_session_relative(session_dir, part_spec["journalPath"])
    append_id = part_spec["appendId"]
    entry = dict(entry)
    entry["appendId"] = append_id

    parent = os.path.dirname(os.path.abspath(journal_path))
    newly_created = not os.path.exists(journal_path)
    if newly_created and parent:
        os.makedirs(parent, exist_ok=True)

    if os.path.exists(journal_path) and os.path.getsize(journal_path) > 0:
        with open(journal_path, "rb") as fh:
            fh.seek(-1, os.SEEK_END)
            if fh.read(1) != b"\n":
                with open(journal_path, "ab") as afh:
                    afh.write(b"\n")
                    afh.flush()
                    os.fsync(afh.fileno())

    if _journal_has_append_id(journal_path, append_id):
        return journal_path

    with open(journal_path, "a", encoding="utf-8") as fh:
        fh.write(_canonical(entry) + "\n")
        fh.flush()
        os.fsync(fh.fileno())

    if newly_created and parent:
        fsync_dir_strict(parent)

    return journal_path


def _apply_replace_file(session_dir, commit_id, part_n, part_spec, staged_bytes):
    target = _resolve_session_relative(session_dir, part_spec["target"])
    expected = part_spec["sha256"]
    actual = _sha256_bytes(staged_bytes)
    if actual != expected:
        raise CommitRefused("staged-part-corrupt",
                            "part %d expected %s got %s" % (part_n, expected, actual))

    _ensure_parent_dirs_strict(target)
    tmp = "%s.commit-%s.tmp" % (target, commit_id)
    with open(tmp, "wb") as fh:
        fh.write(staged_bytes)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, target)
    parent = os.path.dirname(os.path.abspath(target))
    if parent:
        fsync_dir_strict(parent)
    return target


def _apply_external_sidecar(session_dir, commit_id, part_n, part_spec, staged_bytes, resolver):
    try:
        target = resolver()
    except Exception as exc:
        raise CommitRefused("sidecar-target-unresolvable", str(exc))
    if target is None:
        raise CommitRefused("sidecar-target-unresolvable")
    target = os.path.abspath(target)

    expected = part_spec["sha256"]
    actual = _sha256_bytes(staged_bytes)
    if actual != expected:
        raise CommitRefused("staged-part-corrupt",
                            "part %d expected %s got %s" % (part_n, expected, actual))

    _ensure_parent_dirs_strict(target)
    tmp = "%s.commit-%s.tmp" % (target, commit_id)
    with open(tmp, "wb") as fh:
        fh.write(staged_bytes)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, target)
    parent = os.path.dirname(os.path.abspath(target))
    if parent:
        fsync_dir_strict(parent)
    return target


def _load_staged_part(commit_dir, part_n, expected_sha):
    part_path = os.path.join(commit_dir, _PARTS, str(part_n))
    if not os.path.isfile(part_path):
        raise CommitRefused("staged-part-missing", part_path)
    with open(part_path, "rb") as fh:
        data = fh.read()
    if _sha256_bytes(data) != expected_sha:
        raise CommitRefused("staged-part-corrupt", part_path)
    return data


def _apply_parts(session_dir, commit_id, commit_dir, intent, sidecar_resolver, stop_at,
                 sidecar_resolver_for=None):
    targets = []
    parts = intent.get("parts") or []
    for part_spec in sorted(parts, key=lambda p: p["n"]):
        part_n = part_spec["n"]
        ptype = part_spec["type"]

        if ptype == _PART_REPLACE:
            staged = _load_staged_part(commit_dir, part_n, part_spec["sha256"])
            targets.append(_apply_replace_file(session_dir, commit_id, part_n,
                                               part_spec, staged))
        elif ptype == _PART_JOURNAL:
            entry = part_spec.get("entry")
            if not isinstance(entry, dict):
                raise CommitRefused("journal-entry-not-a-mapping")
            targets.append(_apply_journal_append(session_dir, part_spec, entry))
        elif ptype == _PART_SIDECAR:
            staged = _load_staged_part(commit_dir, part_n, part_spec["sha256"])
            if sidecar_resolver_for is not None:
                resolver = sidecar_resolver_for(part_spec)
            else:
                resolver = sidecar_resolver
            if resolver is None:
                raise CommitRefused("sidecar-target-unresolvable")
            targets.append(_apply_external_sidecar(session_dir, commit_id, part_n,
                                                   part_spec, staged, resolver))
        else:
            raise CommitRefused("intent-unreadable", "unknown part type %r" % ptype)

        if stop_at == "part:%d" % part_n:
            raise StopPoint(stop_at)

    return targets


def _complete_commit(session_dir, commit_id, commit_dir, stop_at):
    done_path = os.path.join(commit_dir, _DONE)
    with open(done_path, "wb") as fh:
        fh.flush()
        os.fsync(fh.fileno())
    _strict_fsync_staging(commit_dir)

    if stop_at == "done":
        raise StopPoint("done")

    return _cleanup_commit(session_dir, commit_id, commit_dir, stop_at)


def _cleanup_commit(session_dir, commit_id, commit_dir, stop_at):
    root = commits_root(session_dir)
    cleanup = os.path.join(root, _cleanup_name(commit_id))
    try:
        os.rename(commit_dir, cleanup)
    except OSError as exc:
        raise CommitRefused("commit-cleanup-failed", str(exc))
    _strict_fsync_staging(root)

    if stop_at == "renamed":
        raise StopPoint("renamed")

    try:
        shutil.rmtree(cleanup)
    except OSError as exc:
        raise CommitRefused("commit-cleanup-failed", str(exc))


def _replay_commit(session_dir, commit_id, commit_dir, sidecar_resolver, stop_at=None):
    intent_path = os.path.join(commit_dir, _INTENT)
    intent, err = _read_intent(intent_path)
    if err or not isinstance(intent, dict):
        raise CommitRefused("intent-unreadable", intent_path)

    try:
        _apply_parts(session_dir, commit_id, commit_dir, intent,
                       sidecar_resolver, stop_at)
    except OSError as exc:
        raise CommitRefused("commit-apply-failed", str(exc))
    except StopPoint:
        raise

    try:
        _complete_commit(session_dir, commit_id, commit_dir, stop_at)
    except OSError as exc:
        raise CommitRefused("commit-apply-failed", str(exc))
    except StopPoint:
        raise


def _classify_entry(name):
    if name.startswith(".cleanup-"):
        commit_id = name[len(".cleanup-"):]
        if _is_commit_id(commit_id):
            return "cleanup", commit_id
        return "unexpected", name
    if _is_commit_id(name):
        return "commit", name
    return "unexpected", name


# =============================================================================================
# Commit builder
# =============================================================================================

class Commit(object):
    """Built by ``begin()``; stages parts, seals, applies, completes, and cleans up."""

    def __init__(self, session_dir, kind, commit_id, stop_at, sidecar_resolver):
        self.session_dir = session_dir
        self.kind = kind
        self.commit_id = commit_id
        self.stop_at = stop_at
        self._sidecar_resolver = sidecar_resolver
        self._parts = []
        self._next_n = 0

    def add_replace_file(self, target, data):
        if isinstance(data, str):
            data = data.encode("utf-8")
        try:
            _guard_within(self.session_dir, target)
        except ValueError as exc:
            raise CommitRefused("target-escapes-session", str(exc))
        rel = _session_relative(self.session_dir, target)
        part = {
            "n": self._next_n,
            "type": _PART_REPLACE,
            "target": rel,
            "sha256": _sha256_bytes(data),
            "_bytes": data,
        }
        self._next_n += 1
        self._parts.append(part)
        return part["n"]

    def add_journal_append(self, journal_path, entry):
        if not isinstance(entry, dict):
            raise CommitRefused("journal-entry-not-a-mapping")
        try:
            _guard_within(self.session_dir, journal_path)
        except ValueError as exc:
            raise CommitRefused("target-escapes-session", str(exc))
        rel = _session_relative(self.session_dir, journal_path)
        part_n = self._next_n
        self._next_n += 1
        append_id = "%s#%d" % (self.commit_id, part_n)
        part = {
            "n": part_n,
            "type": _PART_JOURNAL,
            "journalPath": rel,
            "appendId": append_id,
            "entry": dict(entry),
        }
        self._parts.append(part)
        return part_n

    def add_external_sidecar(self, data, resolve_target):
        if isinstance(data, str):
            data = data.encode("utf-8")
        part = {
            "n": self._next_n,
            "type": _PART_SIDECAR,
            "sha256": _sha256_bytes(data),
            "_bytes": data,
            "_resolver": resolve_target,
        }
        self._next_n += 1
        self._parts.append(part)
        return part["n"]

    def _stage(self):
        root = commits_root(self.session_dir)
        commit_dir = os.path.join(root, self.commit_id)
        cleanup = os.path.join(root, _cleanup_name(self.commit_id))
        if os.path.exists(commit_dir) or os.path.exists(cleanup):
            raise CommitRefused("commit-id-collision", self.commit_id)
        parts_dir = os.path.join(commit_dir, _PARTS)
        os.makedirs(parts_dir, exist_ok=True)

        intent_parts = []
        for part in self._parts:
            if part["type"] in (_PART_REPLACE, _PART_SIDECAR):
                part_path = os.path.join(parts_dir, str(part["n"]))
                data = part["_bytes"]
                with open(part_path, "wb") as fh:
                    fh.write(data)
                    fh.flush()
                    os.fsync(fh.fileno())
                intent_parts.append({
                    "n": part["n"],
                    "type": part["type"],
                    "sha256": part["sha256"],
                    **({"target": part["target"]} if part["type"] == _PART_REPLACE else {}),
                })
            elif part["type"] == _PART_JOURNAL:
                intent_parts.append({
                    "n": part["n"],
                    "type": part["type"],
                    "journalPath": part["journalPath"],
                    "appendId": part["appendId"],
                    "entry": part["entry"],
                })

        intent = {
            "schema": SCHEMA,
            "commitId": self.commit_id,
            "kind": self.kind,
            "parts": intent_parts,
        }
        intent_path = os.path.join(commit_dir, _INTENT)
        with open(intent_path, "w", encoding="utf-8") as fh:
            fh.write(_canonical(intent) + "\n")
            fh.flush()
            os.fsync(fh.fileno())

        _strict_fsync_staging(commit_dir)
        _strict_fsync_staging(root)
        return commit_dir

    def _sidecar_resolver_for(self, part_spec):
        for part in self._parts:
            if part["n"] == part_spec["n"] and part["type"] == _PART_SIDECAR:
                return part["_resolver"]
        return self._sidecar_resolver

    def run(self):
        commit_dir = self._stage()

        if self.stop_at == "staged":
            raise StopPoint("staged")

        sealed_path = os.path.join(commit_dir, _SEALED)
        with open(sealed_path, "wb") as fh:
            fh.flush()
            os.fsync(fh.fileno())
        _strict_fsync_staging(commit_dir)

        if self.stop_at == "sealed":
            raise StopPoint("sealed")

        intent_path = os.path.join(commit_dir, _INTENT)
        intent, err = _read_intent(intent_path)
        if err:
            raise CommitRefused("intent-unreadable", intent_path)

        try:
            targets = _apply_parts(self.session_dir, self.commit_id, commit_dir, intent,
                                   self._sidecar_resolver, self.stop_at,
                                   sidecar_resolver_for=self._sidecar_resolver_for)
        except CommitRefused:
            raise
        except OSError as exc:
            raise CommitRefused("commit-apply-failed", str(exc))

        if self.stop_at == "applied":
            raise StopPoint("applied")

        try:
            _complete_commit(self.session_dir, self.commit_id, commit_dir, self.stop_at)
        except OSError as exc:
            raise CommitRefused("commit-apply-failed", str(exc))

        return {
            "ok": True,
            "commitId": self.commit_id,
            "parts": len(self._parts),
            "targets": targets,
        }


def begin(session_dir, kind, *, stop_at=None, commit_id=None):
    """Start a new commit under ``session_dir/commits/``.

    ``stop_at`` is the injected crash point for tests; an unrecognised value refuses at call time.
    """
    parsed_stop = _parse_stop_at(stop_at)
    cid = commit_id if commit_id is not None else uuid.uuid4().hex
    if not _is_commit_id(cid):
        raise CommitRefused("invalid-commit-id", cid)
    return Commit(session_dir, kind, cid, parsed_stop, sidecar_resolver=None)


def recover(session_dir, *, sidecar_target=None):
    """Classify and finish every entry under ``commits/`` before a new commit begins."""
    root = commits_root(session_dir)
    if not os.path.isdir(root):
        return {"ok": True, "replayed": [], "discarded": [], "cleaned": []}

    replayed = []
    discarded = []
    cleaned = []

    try:
        entries = sorted(os.listdir(root))
    except OSError as exc:
        raise CommitRefused("commits-dir-unexpected-entry", str(exc))

    for name in entries:
        path = os.path.join(root, name)
        kind, commit_id = _classify_entry(name)

        if kind == "unexpected":
            raise CommitRefused("commits-dir-unexpected-entry", name)

        if not os.path.isdir(path):
            raise CommitRefused("commits-dir-unexpected-entry", name)

        if kind == "cleanup":
            try:
                shutil.rmtree(path)
            except OSError as exc:
                raise CommitRefused("commit-cleanup-failed", str(exc))
            cleaned.append(commit_id)
            continue

        sealed = os.path.isfile(os.path.join(path, _SEALED))
        done = os.path.isfile(os.path.join(path, _DONE))

        if not sealed:
            try:
                shutil.rmtree(path)
            except OSError as exc:
                raise CommitRefused("commit-cleanup-failed", str(exc))
            discarded.append(commit_id)
            continue

        if done:
            try:
                _cleanup_commit(session_dir, commit_id, path, stop_at=None)
            except OSError as exc:
                raise CommitRefused("commit-cleanup-failed", str(exc))
            cleaned.append(commit_id)
            continue

        try:
            _replay_commit(session_dir, commit_id, path, sidecar_target, stop_at=None)
        except OSError as exc:
            raise CommitRefused("commit-apply-failed", str(exc))
        replayed.append(commit_id)

    return {
        "ok": True,
        "replayed": replayed,
        "discarded": discarded,
        "cleaned": cleaned,
    }
