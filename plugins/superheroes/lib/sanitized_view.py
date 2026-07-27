#!/usr/bin/env python3
"""Disposable git export of a repo with agent/IDE config paths stripped (#684)."""
import os
import shutil
import subprocess
import sys
import tempfile
import time

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

from guardian_tools import _realpath_is_under  # noqa: E402

SANITIZED_VIEW_STRATEGY = "git-archive-export"

SANITIZED_CONFIG_FILES = (
    "AGENTS.md",
    "AGENTS.local.md",
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

_CONFIG_FILES = frozenset(SANITIZED_CONFIG_FILES)
_CONFIG_DIRS = frozenset(SANITIZED_CONFIG_DIRS)


class SanitizedViewError(Exception):
    """Carries a stable .detail token for build failures."""

    def __init__(self, detail):
        self.detail = detail
        super().__init__(detail)


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
        show = stripped[:20]
        lines.append("Stripped paths (sample): " + ", ".join(show))
        if len(stripped) > 20:
            lines.append("(%d additional stripped paths omitted)" % (len(stripped) - 20))
        lines.append("")
    else:
        lines.append("")
    return "\n".join(lines)


def destroy_sanitized_view(path):
    """Best-effort removal of a view directory; never raises."""
    if not path:
        return
    try:
        shutil.rmtree(path, ignore_errors=True)
    except Exception:
        pass


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


def _export_archive(repo_real, head_sha, view_root):
    try:
        archive = subprocess.run(
            ["git", "-C", repo_real, "archive", "--format=tar", head_sha],
            capture_output=True,
        )
    except OSError:
        raise SanitizedViewError("sanitized-view-export-failed")
    if archive.returncode != 0:
        raise SanitizedViewError("sanitized-view-export-failed")
    try:
        tar = subprocess.run(
            ["tar", "-x", "-C", view_root],
            input=archive.stdout,
            capture_output=True,
        )
    except OSError:
        raise SanitizedViewError("sanitized-view-export-failed")
    if tar.returncode != 0:
        raise SanitizedViewError("sanitized-view-export-failed")


def _rel_posix(view_root, abspath):
    rel = os.path.relpath(abspath, view_root)
    return rel.replace(os.sep, "/")


def _strip_sanitized_configs(view_root):
    stripped = []
    for dirpath, dirnames, filenames in os.walk(view_root, topdown=True):
        if ".git" in dirnames:
            dirnames.remove(".git")
        for idx in range(len(dirnames) - 1, -1, -1):
            name = dirnames[idx]
            if name in _CONFIG_DIRS:
                full = os.path.join(dirpath, name)
                stripped.append(_rel_posix(view_root, full))
                shutil.rmtree(full)
                del dirnames[idx]
        for fname in list(filenames):
            if fname in _CONFIG_FILES:
                full = os.path.join(dirpath, fname)
                stripped.append(_rel_posix(view_root, full))
                os.remove(full)
    stripped.sort()
    return stripped


def _init_view_git(view_root):
    steps = (
        ["git", "-C", view_root, "init", "--quiet", "--template="],
        ["git", "-C", view_root, "add", "-A"],
        ["git", "-C", view_root, *_GIT_IDENTITY, "commit", "-q", "-m", "sanitized view"],
    )
    for argv in steps:
        try:
            proc = subprocess.run(argv, capture_output=True)
        except OSError:
            raise SanitizedViewError("sanitized-view-init-failed")
        if proc.returncode != 0:
            raise SanitizedViewError("sanitized-view-init-failed")


def _source_is_dirty(repo_real):
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
        return False
    if proc.returncode != 0:
        return False
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
    """Materialize a stripped git archive of ``repo_root`` at HEAD."""
    repo_real = os.path.realpath(repo_root)
    tmp_base = tempfile.gettempdir()
    if _realpath_is_under(tmp_base, repo_real):
        raise SanitizedViewError("sanitized-view-tempbase-inside-repo")

    view_root = None
    started = time.monotonic()
    try:
        view_root = tempfile.mkdtemp(prefix="superheroes-sanitized-view-")
        if _realpath_is_under(view_root, repo_real):
            raise SanitizedViewError("sanitized-view-tempbase-inside-repo")

        head_sha = _git_rev_parse_head(repo_real)
        _export_archive(repo_real, head_sha, view_root)
        stripped = _strip_sanitized_configs(view_root)
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
