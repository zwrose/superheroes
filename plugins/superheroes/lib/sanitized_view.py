#!/usr/bin/env python3
"""Disposable git export of a repo with agent/IDE config paths stripped (#684).

Config path matching folds ASCII A–Z to a–z on every platform (including
case-sensitive filesystems) so behavior is predictable and case-variant agent
config cannot leak. Non-ASCII letters are not folded.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import time

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

from guardian_tools import path_is_confidently_under, path_is_under_repo  # noqa: E402

SANITIZED_VIEW_STRATEGY = "git-tree-export"

SANITIZED_VIEW_DIR_PREFIX = "superheroes-sanitized-view-"

SANITIZED_VIEW_EXPORT_MAX_BYTES = 2 * 1024 * 1024 * 1024
SANITIZED_VIEW_EXPORT_TIMEOUT_SECONDS = 120
SANITIZED_VIEW_STALE_AGE_SECONDS = 24 * 60 * 60
SANITIZED_VIEW_STALE_SCAN_LIMIT = 256

SANITIZED_CONFIG_FILES = (
    "AGENTS.md",
    "AGENTS.local.md",
    "AGENTS.override.md",
    "CLAUDE.md",
    "CLAUDE.local.md",
    "GEMINI.md",
    "copilot-instructions.md",
    ".cursorrules",
    ".windsurfrules",
    ".clinerules",
    ".aiderrules",
    ".goosehints",
)

SANITIZED_CONFIG_DIRS = (
    ".claude",
    ".codex",
    ".cursor",
    ".aider",
    ".windsurf",
    ".gemini",
)

_GIT_IDENTITY = (
    "-c",
    "user.email=sanitized-view@test.local",
    "-c",
    "user.name=sanitized-view",
)

_CATFILE_READ_CHUNK = 1024 * 1024
SANITIZED_VIEW_MAX_SYMLINK_TARGET_BYTES = 8 * 1024


def _ascii_fold(s):
    return "".join(c.lower() if "A" <= c <= "Z" else c for c in s)


_CONFIG_FILES_ASCII = frozenset(_ascii_fold(n) for n in SANITIZED_CONFIG_FILES)
_CONFIG_DIRS_ASCII = frozenset(_ascii_fold(n) for n in SANITIZED_CONFIG_DIRS)


class SanitizedViewError(Exception):
    """Carries a stable .detail token for build failures."""

    def __init__(self, detail):
        self.detail = detail
        super().__init__(detail)


def _platform_normalized_basename(name):
    """Strip trailing dots/spaces (Win32 alias rules) before config matching."""
    return name.rstrip(". ")


def _is_config_file_basename(name):
    return _ascii_fold(_platform_normalized_basename(name)) in _CONFIG_FILES_ASCII


def _is_config_dir_basename(name):
    return _ascii_fold(_platform_normalized_basename(name)) in _CONFIG_DIRS_ASCII


def _rel_path_would_be_stripped(rel_posix):
    parts = rel_posix.replace("\\", "/").split("/")
    if not parts or not parts[0]:
        return False
    if _is_config_file_basename(parts[-1]):
        return True
    for part in parts[:-1]:
        if _is_config_dir_basename(part):
            return True
    return False


def _stripped_marker_for_rel(rel_posix):
    """Path recorded in ``stripped`` for a census entry, or None if not stripped."""
    if not _rel_path_would_be_stripped(rel_posix):
        return None
    parts = rel_posix.replace("\\", "/").split("/")
    if _is_config_file_basename(parts[-1]):
        return rel_posix.replace("\\", "/")
    for i, part in enumerate(parts[:-1]):
        if _is_config_dir_basename(part):
            return "/".join(parts[: i + 1])
    return None


def _canonical_names_from_stripped(stripped):
    """Map stripped relative paths to canonical constant names (never repo path text)."""
    file_names = set()
    dir_names = set()
    for rel in stripped:
        base = rel.rsplit("/", 1)[-1]
        af = _ascii_fold(_platform_normalized_basename(base))
        for canon in SANITIZED_CONFIG_FILES:
            if _ascii_fold(canon) == af:
                file_names.add(canon)
        for canon in SANITIZED_CONFIG_DIRS:
            if _ascii_fold(canon) == af:
                dir_names.add(canon)
    return sorted(file_names), sorted(dir_names)


def sanitized_view_notice(view):
    """Plain-language notice appended to reviewer dispatch prompts (#684)."""
    stripped = view.get("stripped") or []
    head = view.get("headSha") or "unknown"
    lines = [
        "SANITIZED REVIEW VIEW: Your working directory is a disposable sanitized copy of the "
        "repository at commit %s, not the operator's live checkout. "
        "Repo-local agent and IDE config files were removed on purpose; their absence is NOT a "
        "finding. Do NOT list any stripped path in your investigated array — citing a stripped "
        "path fails the investigation floor and forfeits this seat. "
        "This view has no git log or git blame (only a single synthetic commit).\n"
        % head,
    ]
    if stripped:
        file_names, dir_names = _canonical_names_from_stripped(stripped)
        labels = file_names + dir_names
        if labels:
            lines.append(
                "Stripped agent/IDE config names: %s (%d path(s) removed)"
                % (", ".join(labels), len(stripped))
            )
        else:
            lines.append(
                "Stripped non-config paths (e.g. symlinks outside the view): "
                "%d path(s) removed" % len(stripped)
            )
        lines.append("")
    else:
        lines.append("")
    return "\n".join(lines)


def _owned_view_realpath(path, _under=path_is_confidently_under):
    """Resolved path when authorized to destroy; None when not. Fails CLOSED.

    ``_under`` defaults to ``path_is_confidently_under`` at import time on purpose: a
    test that monkeypatches the module-global helper must not disable this guard during
    teardown (see ``test_symlink_containment_oserror_fail_closed``).
    """
    try:
        real = os.path.realpath(path)
        if not os.path.basename(real).startswith(SANITIZED_VIEW_DIR_PREFIX):
            return None
        tmp_base = tempfile.gettempdir()
        tmp_base_real = os.path.realpath(tmp_base)
        is_temp_base = False
        try:
            # Catches a case-variant path naming the temp base itself; that identity
            # is only observable on case-insensitive filesystems (#699 rider 15).
            is_temp_base = os.path.samefile(real, tmp_base_real)
        except OSError:
            is_temp_base = real == tmp_base_real
        if is_temp_base:
            return None
        if not _under(real, tmp_base):
            return None
        return real
    except Exception:
        return None


def destroy_sanitized_view(path):
    """Best-effort removal of a view directory; never raises.

    Returns True when the path is gone (or was already absent), False when the path
    is not an owned sanitized-view directory, when removal failed after one retry, or
    when ownership cannot be established.
    """
    if not path:
        return True
    real = _owned_view_realpath(path)
    if real is None:
        return False
    for _ in range(2):
        try:
            if not os.path.exists(real):
                return True
            shutil.rmtree(real, ignore_errors=False)
        except Exception:
            pass
        if not os.path.exists(real):
            return True
    return not os.path.exists(real)


def _sweep_stale_views(tmp_base):
    """Remove old owned sanitized-view directories (best-effort; never raises).

    ``tmp_base`` selects what is **listed** (the caller's checked enumeration base).
    ``_owned_view_realpath`` alone authorizes deletion; its containment root is
    ``tempfile.gettempdir()``, so an entry is deleted only when it is an owned view
    under **that** root — which is why a base disjoint from ``gettempdir()`` deletes
    nothing. Age and directory kind are additional sweep-only conditions on top of
    that predicate.
    """
    try:
        names = os.listdir(tmp_base)
    except OSError:
        return
    scanned = 0
    now = time.time()
    for name in names:
        if not name.startswith(SANITIZED_VIEW_DIR_PREFIX):
            continue
        if scanned >= SANITIZED_VIEW_STALE_SCAN_LIMIT:
            break
        scanned += 1
        full = os.path.join(tmp_base, name)
        if os.path.islink(full):
            continue
        real = _owned_view_realpath(full)
        if real is None:
            continue
        try:
            if not os.path.isdir(real):
                continue
            if now - os.path.getmtime(real) < SANITIZED_VIEW_STALE_AGE_SECONDS:
                continue
            # Authorization resolves; deletion must target the enumerated entry so
            # rmtree's own symlink refusal is the atomic backstop against a swap
            # after the islink check.
            shutil.rmtree(full, ignore_errors=True)
        except OSError:
            continue


def _git_rev_parse_head(repo_real):
    try:
        proc = subprocess.run(
            ["git", "-C", repo_real, "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
        )
    except OSError:
        raise SanitizedViewError("sanitized-view-head-unresolved")
    if proc.returncode != 0 or not proc.stdout.strip():
        raise SanitizedViewError("sanitized-view-head-unresolved")
    return proc.stdout.strip()


def _parse_ls_tree_z(raw):
    """Parse ``git ls-tree -r -z`` records (raw path bytes, no C-quoting)."""
    entries = []
    for record in raw.split(b"\0"):
        if not record:
            continue
        sp1 = record.find(b" ")
        sp2 = record.find(b" ", sp1 + 1)
        tab = record.find(b"\t", sp2)
        if sp1 < 0 or sp2 < 0 or tab < 0:
            raise SanitizedViewError("sanitized-view-export-failed")
        mode = record[:sp1].decode("ascii")
        obj_type = record[sp1 + 1 : sp2].decode("ascii")
        oid = record[sp2 + 1 : tab].decode("ascii")
        path = record[tab + 1 :].decode("utf-8", errors="surrogateescape")
        entries.append((mode, obj_type, oid, path))
    return entries


def _expected_git_type_for_mode(mode):
    if mode in ("100644", "100755", "120000"):
        return "blob"
    if mode == "160000":
        return "commit"
    return None


def _git_ls_tree_census(repo_real, head_sha):
    # ls-tree uses capture_output=True, so an absurdly large tree may allocate in
    # full before the post-exit byte-limit check runs; bounding that would need
    # streaming parse and is accepted as out of scope for now.
    try:
        proc = subprocess.run(
            ["git", "-C", repo_real, "ls-tree", "-r", "-z", head_sha],
            capture_output=True,
        )
    except OSError:
        raise SanitizedViewError("sanitized-view-export-failed")
    if proc.returncode != 0:
        raise SanitizedViewError("sanitized-view-export-failed")
    if len(proc.stdout) > SANITIZED_VIEW_EXPORT_MAX_BYTES:
        raise SanitizedViewError("sanitized-view-export-too-large")
    return _parse_ls_tree_z(proc.stdout)


def _close_process_pipes(proc):
    if proc is None:
        return
    for stream in (proc.stdin, proc.stdout, proc.stderr):
        if stream is not None:
            try:
                stream.close()
            except (OSError, AttributeError):
                pass


def _terminate_process(proc):
    if proc is None:
        return
    if proc.poll() is not None:
        _close_process_pipes(proc)
        return
    try:
        proc.terminate()
        proc.wait(timeout=5)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass
        try:
            proc.wait(timeout=5)
        except Exception:
            pass
    _close_process_pipes(proc)


def _check_export_deadline(started):
    # Deadline is checked between pipe reads only; a cat-file child that stalls
    # mid-read is not interrupted by the export timeout (accepted bound).
    if time.monotonic() - started > SANITIZED_VIEW_EXPORT_TIMEOUT_SECONDS:
        raise SanitizedViewError("sanitized-view-export-timeout")


class _CatFileBatch:
    """Single long-lived ``git cat-file --batch`` session (strict request-then-response).

    Stderr is discarded so git diagnostics cannot fill an undrained pipe and deadlock
    the parent. A single pathological blocking ``read()`` on stdout is still theoretically
    unbounded; chunked reads plus DEVNULL stderr reduce exposure to git's own behaviour.
    """

    def __init__(self, repo_real):
        try:
            self._proc = subprocess.Popen(
                ["git", "-C", repo_real, "cat-file", "--batch"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
        except OSError as exc:
            raise SanitizedViewError("sanitized-view-export-failed") from exc
        self._stdin = self._proc.stdin
        self._stdout = self._proc.stdout

    def _read_header(self, oid):
        try:
            header = self._stdout.readline()
        except OSError as exc:
            raise SanitizedViewError("sanitized-view-export-failed") from exc
        if not header or header == b"\n":
            raise SanitizedViewError("sanitized-view-export-failed")
        parts = header.decode("ascii", errors="replace").split()
        if len(parts) != 3:
            raise SanitizedViewError("sanitized-view-export-failed")
        resp_oid, obj_type, size_text = parts
        if resp_oid != oid or obj_type != "blob":
            raise SanitizedViewError("sanitized-view-export-failed")
        try:
            size = int(size_text)
        except ValueError as exc:
            raise SanitizedViewError("sanitized-view-export-failed") from exc
        if size < 0:
            raise SanitizedViewError("sanitized-view-export-failed")
        return size

    def read_blob_bytes(self, oid, started, total_bytes, *, max_blob_bytes=None):
        _check_export_deadline(started)
        try:
            self._stdin.write(oid.encode("ascii") + b"\n")
            self._stdin.flush()
        except OSError as exc:
            raise SanitizedViewError("sanitized-view-export-failed") from exc
        size = self._read_header(oid)
        if max_blob_bytes is not None and size > max_blob_bytes:
            raise SanitizedViewError("sanitized-view-export-failed")
        if total_bytes + size > SANITIZED_VIEW_EXPORT_MAX_BYTES:
            raise SanitizedViewError("sanitized-view-export-too-large")
        chunks = []
        remaining = size
        while remaining > 0:
            _check_export_deadline(started)
            to_read = min(remaining, _CATFILE_READ_CHUNK)
            try:
                data = self._stdout.read(to_read)
            except OSError as exc:
                raise SanitizedViewError("sanitized-view-export-failed") from exc
            if len(data) != to_read:
                raise SanitizedViewError("sanitized-view-export-failed")
            chunks.append(data)
            remaining -= to_read
            total_bytes += len(data)
            if total_bytes > SANITIZED_VIEW_EXPORT_MAX_BYTES:
                raise SanitizedViewError("sanitized-view-export-too-large")
        try:
            trailing = self._stdout.read(1)
            if trailing != b"\n":
                raise SanitizedViewError("sanitized-view-export-failed")
        except OSError as exc:
            raise SanitizedViewError("sanitized-view-export-failed") from exc
        return b"".join(chunks), total_bytes

    def write_blob_to_file(self, oid, dest_fh, started, total_bytes):
        _check_export_deadline(started)
        try:
            self._stdin.write(oid.encode("ascii") + b"\n")
            self._stdin.flush()
        except OSError as exc:
            raise SanitizedViewError("sanitized-view-export-failed") from exc
        size = self._read_header(oid)
        if total_bytes + size > SANITIZED_VIEW_EXPORT_MAX_BYTES:
            raise SanitizedViewError("sanitized-view-export-too-large")
        remaining = size
        while remaining > 0:
            _check_export_deadline(started)
            to_read = min(remaining, _CATFILE_READ_CHUNK)
            try:
                data = self._stdout.read(to_read)
            except OSError as exc:
                raise SanitizedViewError("sanitized-view-export-failed") from exc
            if len(data) != to_read:
                raise SanitizedViewError("sanitized-view-export-failed")
            dest_fh.write(data)
            remaining -= to_read
            total_bytes += len(data)
            if total_bytes > SANITIZED_VIEW_EXPORT_MAX_BYTES:
                raise SanitizedViewError("sanitized-view-export-too-large")
        try:
            trailing = self._stdout.read(1)
            if trailing != b"\n":
                raise SanitizedViewError("sanitized-view-export-failed")
        except OSError as exc:
            raise SanitizedViewError("sanitized-view-export-failed") from exc
        return total_bytes

    def close(self):
        if self._stdin is not None:
            try:
                self._stdin.close()
            except OSError:
                pass
            self._stdin = None
        _terminate_process(self._proc)
        self._proc = None


class _CatFileBatchCheck:
    """Single ``git cat-file --batch-check`` session (strict request-then-response)."""

    def __init__(self, repo_real):
        try:
            self._proc = subprocess.Popen(
                ["git", "-C", repo_real, "cat-file", "--batch-check"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
        except OSError as exc:
            raise SanitizedViewError("sanitized-view-export-failed") from exc
        self._stdin = self._proc.stdin
        self._stdout = self._proc.stdout

    def check_object_type(self, oid, started):
        _check_export_deadline(started)
        try:
            self._stdin.write(oid.encode("ascii") + b"\n")
            self._stdin.flush()
        except OSError as exc:
            raise SanitizedViewError("sanitized-view-export-failed") from exc
        try:
            line = self._stdout.readline()
        except OSError as exc:
            raise SanitizedViewError("sanitized-view-export-failed") from exc
        if not line or line == b"\n":
            raise SanitizedViewError("sanitized-view-export-failed")
        parts = line.decode("ascii", errors="replace").split()
        if len(parts) == 2 and parts[0] == oid and parts[1] == "missing":
            return "missing"
        if len(parts) == 3 and parts[0] == oid:
            return parts[1]
        raise SanitizedViewError("sanitized-view-export-failed")

    def close(self):
        if self._stdin is not None:
            try:
                self._stdin.close()
            except OSError:
                pass
            self._stdin = None
        _terminate_process(self._proc)
        self._proc = None


def _resolve_gitlink_object_types(repo_real, oids, started):
    """Map gitlink object ids to actual types (``missing`` when not in this repo)."""
    if not oids:
        return {}
    unique = list(dict.fromkeys(oids))
    batch = None
    try:
        batch = _CatFileBatchCheck(repo_real)
        return {oid: batch.check_object_type(oid, started) for oid in unique}
    finally:
        if batch is not None:
            batch.close()


def _assert_path_under_view(view_root, rel_posix):
    full = os.path.normpath(os.path.join(view_root, rel_posix))
    if not path_is_confidently_under(full, view_root):
        raise SanitizedViewError("sanitized-view-export-failed")
    return full


def _symlink_escapes_view(view_root, rel_posix, target_bytes):
    link_dir = os.path.dirname(os.path.join(view_root, rel_posix))
    try:
        target_text = target_bytes.decode("utf-8", errors="surrogateescape")
    except Exception:
        return True
    resolved = os.path.normpath(os.path.join(link_dir, target_text))
    try:
        return not path_is_confidently_under(resolved, view_root)
    except OSError:
        return True


def _materialize_from_tree(repo_real, head_sha, view_root, started):
    """Materialize HEAD from the git tree via cat-file (no .gitattributes processing).

    ``git cat-file`` returns raw blob bytes, so export-ignore and export-subst from
    .gitattributes cannot apply.
    """
    census = _git_ls_tree_census(repo_real, head_sha)
    gitlink_oids = [oid for mode, _obj_type, oid, _path in census if mode == "160000"]
    gitlink_types = _resolve_gitlink_object_types(repo_real, gitlink_oids, started)
    stripped_set = set()
    submodules = set()
    escaping_symlinks = set()
    materialized = set()
    total_bytes = 0
    batch = None
    try:
        batch = _CatFileBatch(repo_real)
        for mode, obj_type, oid, path in census:
            _check_export_deadline(started)

            expected_type = _expected_git_type_for_mode(mode)
            if expected_type is None:
                raise SanitizedViewError("sanitized-view-export-failed")
            if obj_type != expected_type:
                raise SanitizedViewError("sanitized-view-export-failed")

            marker = _stripped_marker_for_rel(path)
            if marker is not None:
                stripped_set.add(marker)
                continue

            if mode == "160000":
                actual_type = gitlink_types[oid]
                if actual_type == "commit":
                    submodules.add(path)
                    continue
                if actual_type == "missing":
                    # Parent repos usually lack the submodule commit object locally.
                    submodules.add(path)
                    continue
                raise SanitizedViewError("sanitized-view-export-failed")

            if mode == "120000":
                blob, total_bytes = batch.read_blob_bytes(
                    oid,
                    started,
                    total_bytes,
                    max_blob_bytes=SANITIZED_VIEW_MAX_SYMLINK_TARGET_BYTES,
                )
                if _symlink_escapes_view(view_root, path, blob):
                    stripped_set.add(path)
                    escaping_symlinks.add(path)
                    continue
                dest = _assert_path_under_view(view_root, path)
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                os.symlink(blob.decode("utf-8", errors="surrogateescape"), dest)
                materialized.add(path)
                continue

            if mode in ("100644", "100755"):
                dest = _assert_path_under_view(view_root, path)
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                with open(dest, "wb") as fh:
                    total_bytes = batch.write_blob_to_file(oid, fh, started, total_bytes)
                if mode == "100755":
                    os.chmod(dest, os.stat(dest).st_mode | 0o111)
                materialized.add(path)
                continue

            raise SanitizedViewError("sanitized-view-export-failed")
    except SanitizedViewError:
        raise
    except OSError as exc:
        raise SanitizedViewError("sanitized-view-export-failed") from exc
    finally:
        if batch is not None:
            batch.close()

    _verify_export_complete(
        view_root, census, materialized, submodules, escaping_symlinks
    )
    return sorted(stripped_set)


def _rel_posix(view_root, abspath):
    rel = os.path.relpath(abspath, view_root)
    return rel.replace(os.sep, "/")


def _disk_paths_in_view(view_root):
    """Materialized blob/symlink paths under view_root (excluding ``.git``), via ``lstat``."""
    on_disk = set()
    for dirpath, dirnames, filenames in os.walk(view_root, followlinks=False):
        if ".git" in dirnames:
            dirnames.remove(".git")
        for name in filenames:
            full = os.path.join(dirpath, name)
            os.lstat(full)
            on_disk.add(_rel_posix(view_root, full))
        for name in list(dirnames):
            full = os.path.join(dirpath, name)
            if os.path.islink(full):
                os.lstat(full)
                on_disk.add(_rel_posix(view_root, full))
                dirnames.remove(name)
    return on_disk


def _verify_export_complete(
    view_root, census, materialized, submodules, escaping_symlinks
):
    """Fail closed when on-disk paths differ from census − stripped − submodules."""
    expected = set()
    for mode, obj_type, oid, path in census:
        if mode == "160000":
            continue
        if _rel_path_would_be_stripped(path):
            continue
        if path in escaping_symlinks:
            continue
        expected.add(path)
    on_disk = _disk_paths_in_view(view_root)
    if expected != on_disk:
        raise SanitizedViewError("sanitized-view-export-incomplete")
    if set(materialized) != on_disk:
        raise SanitizedViewError("sanitized-view-export-incomplete")


def _init_view_git(view_root):
    steps = (
        ["git", "-C", view_root, "init", "--quiet", "--template="],
        ["git", "-C", view_root, "add", "-A"],
        [
            "git",
            "-C",
            view_root,
            *_GIT_IDENTITY,
            "commit",
            "-q",
            "--allow-empty",
            "-m",
            "sanitized view",
        ],
    )
    for argv in steps:
        try:
            proc = subprocess.run(argv, capture_output=True)
        except OSError:
            raise SanitizedViewError("sanitized-view-init-failed")
        if proc.returncode != 0:
            raise SanitizedViewError("sanitized-view-init-failed")


def _source_is_dirty(repo_real):
    """Tri-state: True if dirty, False if clean, None if the probe could not run."""
    try:
        proc = subprocess.run(
            [
                "git",
                "-C",
                repo_real,
                "status",
                "--porcelain",
                "--untracked-files=no",
            ],
            capture_output=True,
            text=True,
        )
    except OSError:
        return None
    if proc.returncode != 0:
        return None
    return bool(proc.stdout.strip())


def _measure_worktree(view_root):
    total_bytes = 0
    file_count = 0
    for dirpath, dirnames, filenames in os.walk(view_root):
        if ".git" in dirnames:
            dirnames.remove(".git")
        for fname in filenames:
            fp = os.path.join(dirpath, fname)
            try:
                total_bytes += os.path.getsize(fp)
            except OSError:
                pass
            file_count += 1
    return total_bytes, file_count


def build_sanitized_view(repo_root):
    """Materialize a stripped copy of ``repo_root`` at HEAD from the git tree.

    ``sourceDirty`` in the returned dict is ``True`` when tracked files differ
    from HEAD, ``False`` when they match, and ``None`` when git status could not
    be run.
    """
    repo_real = os.path.realpath(repo_root)
    tmp_base = tempfile.gettempdir()
    if path_is_under_repo(tmp_base, repo_real):
        raise SanitizedViewError("sanitized-view-tempbase-inside-repo")
    _sweep_stale_views(tmp_base)

    view_root = None
    started = time.monotonic()
    try:
        view_root = tempfile.mkdtemp(prefix=SANITIZED_VIEW_DIR_PREFIX)
        if path_is_under_repo(view_root, repo_real):
            raise SanitizedViewError("sanitized-view-tempbase-inside-repo")

        head_sha = _git_rev_parse_head(repo_real)
        stripped = _materialize_from_tree(repo_real, head_sha, view_root, started)
        _init_view_git(view_root)

        build_seconds = time.monotonic() - started
        total_bytes, file_count = _measure_worktree(view_root)
        return {
            "path": view_root,
            "strategy": SANITIZED_VIEW_STRATEGY,
            "stripped": stripped,
            "strippedCount": len(stripped),
            "headSha": head_sha,
            "sourceDirty": _source_is_dirty(repo_real),
            "buildSeconds": build_seconds,
            "bytes": total_bytes,
            "fileCount": file_count,
        }
    except SanitizedViewError:
        if view_root is not None:
            destroy_sanitized_view(view_root)
        raise
    except OSError:
        if view_root is not None:
            destroy_sanitized_view(view_root)
        raise SanitizedViewError("sanitized-view-export-failed")
    except Exception:
        if view_root is not None:
            destroy_sanitized_view(view_root)
        raise
