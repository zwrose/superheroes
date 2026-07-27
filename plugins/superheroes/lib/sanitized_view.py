#!/usr/bin/env python3
"""Disposable git export of a repo with agent/IDE config paths stripped (#684).

Config path matching uses casefold on every platform (including case-sensitive
filesystems) so behavior is predictable and case-variant agent config cannot leak.
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

from guardian_tools import path_is_under_repo  # noqa: E402

SANITIZED_VIEW_STRATEGY = "git-archive-export"

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

_CONFIG_FILES_CASEFOLD = frozenset(n.casefold() for n in SANITIZED_CONFIG_FILES)
_CONFIG_DIRS_CASEFOLD = frozenset(n.casefold() for n in SANITIZED_CONFIG_DIRS)

_EXPORT_CHUNK_SIZE = 65536


class SanitizedViewError(Exception):
    """Carries a stable .detail token for build failures."""

    def __init__(self, detail):
        self.detail = detail
        super().__init__(detail)


def _is_config_file_basename(name):
    return name.casefold() in _CONFIG_FILES_CASEFOLD


def _is_config_dir_basename(name):
    return name.casefold() in _CONFIG_DIRS_CASEFOLD


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


def _canonical_names_from_stripped(stripped):
    """Map stripped relative paths to canonical constant names (never repo path text)."""
    file_names = set()
    dir_names = set()
    for rel in stripped:
        base = rel.rsplit("/", 1)[-1]
        cf = base.casefold()
        for canon in SANITIZED_CONFIG_FILES:
            if canon.casefold() == cf:
                file_names.add(canon)
        for canon in SANITIZED_CONFIG_DIRS:
            if canon.casefold() == cf:
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
        lines.append(
            "Stripped agent/IDE config names: %s (%d path(s) removed)"
            % (", ".join(labels), len(stripped))
        )
        lines.append("")
    else:
        lines.append("")
    return "\n".join(lines)


def destroy_sanitized_view(path):
    """Best-effort removal of a view directory; never raises.

    Returns True when the path is gone (or was already absent), False when removal
    failed after one retry.
    """
    if not path:
        return True
    for _ in range(2):
        try:
            if not os.path.exists(path):
                return True
            shutil.rmtree(path, ignore_errors=False)
        except Exception:
            pass
        if not os.path.exists(path):
            return True
    return not os.path.exists(path)


def _sweep_stale_views(tmp_base):
    """Remove old sanitized-view directories under the temp base (best-effort)."""
    try:
        names = os.listdir(tmp_base)
    except OSError:
        return
    scanned = 0
    now = time.time()
    for name in names:
        if scanned >= SANITIZED_VIEW_STALE_SCAN_LIMIT:
            break
        scanned += 1
        if not name.startswith(SANITIZED_VIEW_DIR_PREFIX):
            continue
        full = os.path.join(tmp_base, name)
        try:
            if not os.path.isdir(full):
                continue
            if now - os.path.getmtime(full) < SANITIZED_VIEW_STALE_AGE_SECONDS:
                continue
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


def _git_ls_tree_paths(repo_real, head_sha):
    try:
        proc = subprocess.run(
            ["git", "-C", repo_real, "ls-tree", "-r", "--name-only", head_sha],
            capture_output=True,
            text=True,
        )
    except OSError:
        raise SanitizedViewError("sanitized-view-export-failed")
    if proc.returncode != 0:
        raise SanitizedViewError("sanitized-view-export-failed")
    text = proc.stdout.strip()
    if not text:
        return []
    return text.splitlines()


def _terminate_process(proc):
    if proc is None or proc.poll() is not None:
        return
    try:
        proc.terminate()
        proc.wait(timeout=5)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


def _export_archive(repo_real, head_sha, view_root):
    started = time.monotonic()
    total_bytes = 0
    archive_proc = None
    tar_proc = None
    try:
        archive_proc = subprocess.Popen(
            ["git", "-C", repo_real, "archive", "--format=tar", head_sha],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        tar_proc = subprocess.Popen(
            ["tar", "-x", "-C", view_root],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except OSError:
        _terminate_process(archive_proc)
        _terminate_process(tar_proc)
        raise SanitizedViewError("sanitized-view-export-failed")

    try:
        while True:
            if time.monotonic() - started > SANITIZED_VIEW_EXPORT_TIMEOUT_SECONDS:
                raise SanitizedViewError("sanitized-view-export-timeout")
            chunk = archive_proc.stdout.read(_EXPORT_CHUNK_SIZE)
            if not chunk:
                break
            total_bytes += len(chunk)
            if total_bytes > SANITIZED_VIEW_EXPORT_MAX_BYTES:
                raise SanitizedViewError("sanitized-view-export-too-large")
            tar_proc.stdin.write(chunk)
        tar_proc.stdin.close()
        archive_proc.wait()
        tar_proc.wait()
        if archive_proc.returncode != 0 or tar_proc.returncode != 0:
            raise SanitizedViewError("sanitized-view-export-failed")
    except SanitizedViewError:
        raise
    except OSError:
        raise SanitizedViewError("sanitized-view-export-failed")
    finally:
        _terminate_process(archive_proc)
        _terminate_process(tar_proc)


def _rel_posix(view_root, abspath):
    rel = os.path.relpath(abspath, view_root)
    return rel.replace(os.sep, "/")


def _list_view_files(view_root):
    paths = set()
    for dirpath, dirnames, filenames in os.walk(view_root):
        if ".git" in dirnames:
            dirnames.remove(".git")
        for fname in filenames:
            paths.add(_rel_posix(view_root, os.path.join(dirpath, fname)))
    return paths


def _verify_export_complete(repo_real, head_sha, view_root):
    """Fail closed when git archive omits tracked paths (e.g. export-ignore).

    export-subst may rewrite file contents in the archive; substitution values
    come from git metadata, not attacker-controlled text. Path-set verification is
    the guard; .gitattributes remains visible in the view when tracked.
    """
    tree_paths = _git_ls_tree_paths(repo_real, head_sha)
    expected = {p for p in tree_paths if not _rel_path_would_be_stripped(p)}
    actual = _list_view_files(view_root)
    if expected != actual:
        raise SanitizedViewError("sanitized-view-export-incomplete")


def _strip_sanitized_configs(view_root):
    stripped = []
    for dirpath, dirnames, filenames in os.walk(view_root, topdown=True):
        if ".git" in dirnames:
            dirnames.remove(".git")
        for idx in range(len(dirnames) - 1, -1, -1):
            name = dirnames[idx]
            if _is_config_dir_basename(name):
                full = os.path.join(dirpath, name)
                stripped.append(_rel_posix(view_root, full))
                shutil.rmtree(full)
                del dirnames[idx]
        for fname in list(filenames):
            if _is_config_file_basename(fname):
                full = os.path.join(dirpath, fname)
                stripped.append(_rel_posix(view_root, full))
                os.remove(full)
    stripped.sort()
    return stripped


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
    """Materialize a stripped git archive of ``repo_root`` at HEAD.

    ``sourceDirty`` in the returned dict is ``True`` when tracked files differ
    from HEAD, ``False`` when they match, and ``None`` when git status could not
    be run.
    """
    repo_real = os.path.realpath(repo_root)
    tmp_base = tempfile.gettempdir()
    _sweep_stale_views(tmp_base)
    if path_is_under_repo(tmp_base, repo_real):
        raise SanitizedViewError("sanitized-view-tempbase-inside-repo")

    view_root = None
    started = time.monotonic()
    try:
        view_root = tempfile.mkdtemp(prefix=SANITIZED_VIEW_DIR_PREFIX)
        if path_is_under_repo(view_root, repo_real):
            raise SanitizedViewError("sanitized-view-tempbase-inside-repo")

        head_sha = _git_rev_parse_head(repo_real)
        _export_archive(repo_real, head_sha, view_root)
        stripped = _strip_sanitized_configs(view_root)
        _verify_export_complete(repo_real, head_sha, view_root)
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
