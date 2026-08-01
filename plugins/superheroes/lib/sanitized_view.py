#!/usr/bin/env python3
"""Disposable git export of a repo with agent/IDE config paths stripped (#684).

Config path matching folds ASCII A–Z to a–z on every platform (including
case-sensitive filesystems) so behavior is predictable and case-variant agent
config cannot leak. Non-ASCII letters are not folded.
"""
import os
import select
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

REVIEW_DIFF_FILE_NAME = "SUPERHEROES_REVIEW_DIFF.patch"
REVIEW_DIFF_MAX_BYTES = 8 * 1024 * 1024
_REVIEW_DIFF_ARGV_MAX_BYTES = 128 * 1024
_REVIEW_DIFF_ARGV_MARGIN = 8 * 1024

_GIT_ROUTING_VARS = (
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_CONFIG",
    "GIT_CONFIG_GLOBAL",
    "GIT_CONFIG_SYSTEM",
    "GIT_COMMON_DIR",
    "GIT_NAMESPACE",
    "GIT_EXTERNAL_DIFF",
    "GIT_REPLACE_REF_BASE",
)

_DIFF_CONFIG_OVERRIDES = (
    "-c",
    "core.quotePath=false",
    "-c",
    "diff.noprefix=false",
    "-c",
    "diff.mnemonicPrefix=false",
    "-c",
    "diff.relative=false",
)

# Belt-and-braces for census paths; -z already suppresses quoting. Patch-presentation
# keys from _DIFF_CONFIG_OVERRIDES deliberately do not appear here.
_CENSUS_CONFIG_OVERRIDES = ("-c", "core.quotePath=false")

_DIFF_PATCH_FLAGS = (
    "diff",
    "--no-ext-diff",
    "--no-textconv",
    "--no-color",
    "--no-renames",
    "--submodule=short",
    "--ignore-submodules=none",
    "--src-prefix=a/",
    "--dst-prefix=b/",
)

_DIFF_READ_POLL_SECONDS = 1.0

_ANCESTRY_SCRATCH_PREFIX = "superheroes-ancestry-"

# Pins for our own reader. core.commitGraph defaults on since git 2.24, and a
# commit-graph file lives inside the object directory we alternate to, so it is
# disabled explicitly rather than trusted.
_ANCESTRY_CONFIG_OVERRIDES = (
    "-c",
    "core.commitGraph=false",
    "-c",
    "core.useReplaceRefs=false",
)


def _git_env():
    env = os.environ.copy()
    for var in _GIT_ROUTING_VARS:
        env.pop(var, None)
    env["GIT_LITERAL_PATHSPECS"] = "1"
    env["GIT_NO_REPLACE_OBJECTS"] = "1"
    env["LC_ALL"] = "C"
    env["LANGUAGE"] = ""
    # Lazy fetch stays enabled on partial clones; the export deadline bounds it.
    return env


def _git_run(*args, **kwargs):
    kwargs["env"] = _git_env()
    return subprocess.run(*args, **kwargs)


def _git_popen(*args, **kwargs):
    kwargs["env"] = _git_env()
    return subprocess.Popen(*args, **kwargs)


def _is_git_object_id_hex(value):
  """True when ``value`` is a 40- or 64-char lowercase/uppercase hex object id."""
  if len(value) not in (40, 64):
    return False
  return all(c in "0123456789abcdef" for c in value.lower())


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
        "This view has no origin/main, no remote, no parent commit, and only a single synthetic "
        "commit. git diff <ref>, git log, git blame, and git show <ref> cannot work here and "
        "must not be attempted.\n"
        % head,
    ]
    diff_path = view.get("diffPath")
    if diff_path:
        lines.append(
            "The change under review is the patch at %s — read it first. It is a generated "
            "artifact, not repository source; do not review the patch file itself, do not list "
            "it in your investigated array, and exclude it from repo-wide searches.\n"
            % diff_path
        )
    withheld = view.get("diffWithheldCount") or 0
    if withheld:
        lines.append(
            "%d changed path(s) were withheld from the review patch because they are stripped "
            "agent/IDE config; their absence is not a finding.\n" % withheld
        )
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


def _owned_ancestry_scratch_realpath(path):
    """Resolved path when authorized to reap a stale ancestry scratch dir; None otherwise."""
    try:
        real = os.path.realpath(path)
        if not os.path.basename(real).startswith(_ANCESTRY_SCRATCH_PREFIX):
            return None
        tmp_base = tempfile.gettempdir()
        tmp_base_real = os.path.realpath(tmp_base)
        is_temp_base = False
        try:
            is_temp_base = os.path.samefile(real, tmp_base_real)
        except OSError:
            is_temp_base = real == tmp_base_real
        if is_temp_base:
            return None
        if not path_is_confidently_under(real, tmp_base):
            return None
        return real
    except Exception:
        return None


def _sweep_stale_views(tmp_base):
    """Remove old owned sanitized-view and ancestry-scratch directories (best-effort).

    ``tmp_base`` selects what is **listed** (the caller's checked enumeration base).
    ``_owned_view_realpath`` and ``_owned_ancestry_scratch_realpath`` authorize
    deletion; their containment root is ``tempfile.gettempdir()``, so an entry is
    deleted only when it is an owned directory under **that** root — which is why a
    base disjoint from ``gettempdir()`` deletes nothing. Age and directory kind are
    additional sweep-only conditions on top of that predicate.
    """
    try:
        names = os.listdir(tmp_base)
    except OSError:
        return
    scanned = 0
    now = time.time()
    for name in names:
        is_view = name.startswith(SANITIZED_VIEW_DIR_PREFIX)
        is_ancestry = name.startswith(_ANCESTRY_SCRATCH_PREFIX)
        if not is_view and not is_ancestry:
            continue
        if scanned >= SANITIZED_VIEW_STALE_SCAN_LIMIT:
            break
        scanned += 1
        full = os.path.join(tmp_base, name)
        if os.path.islink(full):
            continue
        if is_view:
            real = _owned_view_realpath(full)
        else:
            real = _owned_ancestry_scratch_realpath(full)
        if real is None:
            continue
        try:
            if not os.path.isdir(real):
                continue
            if now - os.path.getmtime(real) < SANITIZED_VIEW_STALE_AGE_SECONDS:
                continue
            # Authorization resolves; deletion must target the enumerated entry so
            # rmtree's refusal of a top-level symlink (every platform) catches a
            # post-check swap — race-free where avoids_symlink_attacks is True.
            shutil.rmtree(full, ignore_errors=True)
        except OSError:
            continue


def _git_rev_parse_head(repo_real):
    try:
        proc = _git_run(
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
        proc = _git_run(
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


def _git_tree_entries(repo_real, sha, started):
    """Authoritative tree enumerator for review-diff census (path -> mode, type, oid)."""
    _check_export_deadline(started)
    timeout = _remaining_export_timeout(started)
    try:
        proc = _git_run(
            [
                "git",
                "-C",
                repo_real,
                *_CENSUS_CONFIG_OVERRIDES,
                "ls-tree",
                "-r",
                "-z",
                sha,
            ],
            capture_output=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise SanitizedViewError("sanitized-view-diff-failed")
    except OSError:
        raise SanitizedViewError("sanitized-view-diff-failed")
    if proc.returncode != 0:
        raise SanitizedViewError("sanitized-view-diff-failed")
    if len(proc.stdout) > SANITIZED_VIEW_EXPORT_MAX_BYTES:
        raise SanitizedViewError("sanitized-view-diff-too-large")
    entries = {}
    for mode, obj_type, oid, path in _parse_ls_tree_z(proc.stdout):
        if path in entries:
            raise SanitizedViewError("sanitized-view-diff-unaccounted")
        entries[path] = (mode, obj_type, oid)
    return entries


def _changed_tree_entries(repo_real, base_sha, head_sha, started):
    """Return sorted paths whose (mode, type, oid) differ between two commits."""
    base_map = _git_tree_entries(repo_real, base_sha, started)
    head_map = _git_tree_entries(repo_real, head_sha, started)
    all_paths = set(base_map) | set(head_map)
    changed = [
        p for p in sorted(all_paths) if base_map.get(p) != head_map.get(p)
    ]
    return changed


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


def _remaining_export_timeout(started):
    """Seconds left in the export budget (small positive floor)."""
    remaining = SANITIZED_VIEW_EXPORT_TIMEOUT_SECONDS - (time.monotonic() - started)
    return max(remaining, 0.001)


def _ancestry_env():
    """Environment for ancestry resolution, built by rule rather than by denylist.

    Every inherited ``GIT_*`` variable is dropped — including ones this module has
    never heard of — and only process-owned values are added back. A denylist of
    dangerous names is exactly what this boundary must not depend on.
    """
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env["GIT_NO_REPLACE_OBJECTS"] = "1"
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_CONFIG_SYSTEM"] = os.devnull
    env["LC_ALL"] = "C"
    env["LANGUAGE"] = ""
    return env


def _ancestry_run(argv, started, *, cwd=None):
    """Run one ancestry git command under the hermetic environment and the deadline."""
    _check_export_deadline(started)
    try:
        return subprocess.run(
            argv,
            capture_output=True,
            text=True,
            encoding=sys.getfilesystemencoding(),
            errors="surrogateescape",
            timeout=_remaining_export_timeout(started),
            env=_ancestry_env(),
            cwd=cwd,
        )
    except subprocess.TimeoutExpired:
        raise SanitizedViewError("sanitized-view-diff-failed")
    except (OSError, UnicodeError):
        raise SanitizedViewError("sanitized-view-diff-base-unresolved")


def _reviewed_repo_ancestry_git_argv(repo_real, *args):
    """Argv prefix for ancestry probes run against the reviewed repository."""
    return [
        "git",
        "-C",
        repo_real,
        "-c",
        "safe.directory=%s" % repo_real,
        *args,
    ]


def _repo_object_directory(repo_real, started):
    """Absolute path of the repository's object store.

    ``rev-parse --git-path objects`` (git 2.5+) yields the *common* object directory
    from a linked worktree; it may be relative to the repository root, so it is
    joined and realpath'd here rather than requiring ``--path-format=absolute``
    (git 2.31+).
    """
    proc = _ancestry_run(
        _reviewed_repo_ancestry_git_argv(repo_real, "rev-parse", "--git-path", "objects"),
        started,
    )
    if proc.returncode != 0:
        raise SanitizedViewError("sanitized-view-diff-base-unresolved")
    raw = proc.stdout.strip()
    if not raw:
        raise SanitizedViewError("sanitized-view-diff-base-unresolved")
    objects_dir = raw if os.path.isabs(raw) else os.path.join(repo_real, raw)
    objects_dir = os.path.realpath(objects_dir)
    # The alternates file is newline-delimited; a path containing a newline cannot
    # be expressed in it, so refuse rather than write a file git will misread.
    objects_dir_bytes = os.fsencode(objects_dir)
    if b"\n" in objects_dir_bytes or b"\r" in objects_dir_bytes:
        raise SanitizedViewError("sanitized-view-diff-base-unresolved")
    if not os.path.isdir(objects_dir):
        raise SanitizedViewError("sanitized-view-diff-base-unresolved")
    return objects_dir


def _repo_object_format(repo_real, started):
    """Object format name, or None when git is too old to report one (then sha1)."""
    proc = _ancestry_run(
        _reviewed_repo_ancestry_git_argv(
            repo_real, "rev-parse", "--show-object-format"
        ),
        started,
    )
    if proc.returncode != 0:
        return None
    fmt = proc.stdout.strip()
    # git rev-parse echoes an option it does not recognise and still exits 0, so a
    # git predating --show-object-format answers with the flag itself. That is
    # "this git cannot tell us", not a hostile answer: fall back to sha1.
    if not fmt or fmt == "sha1" or not fmt.isalnum() or len(fmt) > 16:
        return None
    return fmt


def _authoritative_merge_base(repo_real, base_sha, head_sha, started):
    """Merge-base resolved outside the reviewed repository's git directory.

    Ancestry overlays a repository can carry — graft metadata, replacement refs, a
    commit-graph — all live in that repository's git directory. The object store
    holds only oid->bytes. Resolving ancestry in a scratch repository this process
    creates, whose sole link to the repo under review is an
    ``objects/info/alternates`` pointer, therefore puts every such ancestry overlay
    structurally out of reach, without enumerating any of them. Content-side config
    and attributes remain in the reviewed repository's domain and are handled by
    pinned ``-c`` overrides and the ``sanitized-view-diff-opaque`` refusal.

    Trust boundary, stated: the object store's oid->bytes mapping is the trust root
    already shared by the census, the patch generation and the view materialization.
    This function does not defend against an object store that serves wrong bytes for
    an oid, and does not claim to. The guarantee is conditional on every reviewed-
    repository ancestry walk routing through ``_ancestry_run`` — see
    ``test_subprocess_ancestry_git_calls_route_through_ancestry_run``.
    """
    proc = _ancestry_run(
        _reviewed_repo_ancestry_git_argv(
            repo_real, "rev-parse", "--is-shallow-repository"
        ),
        started,
    )
    if proc.returncode == 0 and proc.stdout.strip() == "true":
        raise SanitizedViewError("sanitized-view-diff-base-shallow")
    objects_dir = _repo_object_directory(repo_real, started)
    object_format = _repo_object_format(repo_real, started)

    tmp_base = tempfile.gettempdir()
    if path_is_under_repo(tmp_base, repo_real):
        raise SanitizedViewError("sanitized-view-tempbase-inside-repo")

    scratch_parent = None
    try:
        try:
            scratch_parent = tempfile.mkdtemp(prefix=_ANCESTRY_SCRATCH_PREFIX)
        except OSError:
            raise SanitizedViewError("sanitized-view-diff-base-unresolved")
        if path_is_under_repo(scratch_parent, repo_real):
            raise SanitizedViewError("sanitized-view-tempbase-inside-repo")
        # An empty template directory keeps any init.templateDir content out of the
        # scratch repository.
        template_dir = os.path.join(scratch_parent, "template")
        scratch_git_dir = os.path.join(scratch_parent, "ancestry.git")
        try:
            os.makedirs(template_dir)
        except OSError:
            raise SanitizedViewError("sanitized-view-diff-base-unresolved")

        init_argv = [
            "git",
            "init",
            "-q",
            "--bare",
            "--template=%s" % template_dir,
        ]
        if object_format is not None:
            init_argv.append("--object-format=%s" % object_format)
        init_argv.append(scratch_git_dir)
        proc = _ancestry_run(init_argv, started, cwd=scratch_parent)
        if proc.returncode != 0:
            raise SanitizedViewError("sanitized-view-diff-base-unresolved")

        alternates = os.path.join(scratch_git_dir, "objects", "info", "alternates")
        try:
            os.makedirs(os.path.dirname(alternates), exist_ok=True)
            with open(alternates, "wb") as fh:
                fh.write(os.fsencode(objects_dir) + b"\n")
        except (OSError, ValueError, UnicodeError):
            raise SanitizedViewError("sanitized-view-diff-base-unresolved")

        proc = _ancestry_run(
            [
                "git",
                "--git-dir=%s" % scratch_git_dir,
                *_ANCESTRY_CONFIG_OVERRIDES,
                "merge-base",
                "--end-of-options",
                base_sha,
                head_sha,
            ],
            started,
            cwd=scratch_parent,
        )
        if proc.returncode != 0 or not proc.stdout.strip():
            raise SanitizedViewError("sanitized-view-diff-base-unresolved")
        merge_base = proc.stdout.strip()
        if not _is_git_object_id_hex(merge_base):
            raise SanitizedViewError("sanitized-view-diff-base-unresolved")
        return merge_base
    finally:
        if scratch_parent is not None:
            shutil.rmtree(scratch_parent, ignore_errors=True)


class _CatFileBatch:
    """Single long-lived ``git cat-file --batch`` session (strict request-then-response).

    Stderr is discarded so git diagnostics cannot fill an undrained pipe and deadlock
    the parent. A single pathological blocking ``read()`` on stdout is still theoretically
    unbounded; chunked reads plus DEVNULL stderr reduce exposure to git's own behaviour.
    """

    def __init__(self, repo_real):
        try:
            self._proc = _git_popen(
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
            self._proc = _git_popen(
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
        ["git", "-C", view_root, "add", "-A", "-f"],
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
            proc = _git_run(argv, capture_output=True)
        except OSError:
            raise SanitizedViewError("sanitized-view-init-failed")
        if proc.returncode != 0:
            raise SanitizedViewError("sanitized-view-init-failed")


def _source_is_dirty(repo_real):
    """Tri-state: True if dirty, False if clean, None if the probe could not run."""
    try:
        proc = _git_run(
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


def _assert_no_stripped_paths_in_view(view_root):
    """Fail closed when patch staging re-materialized a stripped config path."""
    for rel in _disk_paths_in_view(view_root):
        if _rel_path_would_be_stripped(rel):
            raise SanitizedViewError("sanitized-view-diff-path-collision")


_DIFF_PATH_UNDERIVABLE = object()


def _scan_c_quoted_end(token):
    """Index of closing quote in a C-quoted token starting with ``b'"'``, or None."""
    if not token.startswith(b'"'):
        return None
    i = 1
    while i < len(token):
        ch = token[i]
        if ch == ord('"'):
            return i
        if ch == ord("\\"):
            if i + 1 >= len(token):
                return None
            esc = token[i + 1]
            if esc in (
                ord("\\"),
                ord('"'),
                ord("a"),
                ord("b"),
                ord("f"),
                ord("n"),
                ord("r"),
                ord("t"),
                ord("v"),
            ):
                i += 2
                continue
            if ord("0") <= esc <= ord("7"):
                j = i + 1
                while j < len(token) and j < i + 4 and ord("0") <= token[j] <= ord("7"):
                    j += 1
                if j == i + 1:
                    return None
                if int(token[i + 1 : j], 8) > 0o377:
                    return None
                i = j
                continue
            return None
        i += 1
    return None


def _unquote_c_style(token):
    """Decode a complete C-quoted git path token; None when malformed."""
    end = _scan_c_quoted_end(token)
    if end is None or end != len(token) - 1:
        return None
    out = bytearray()
    i = 1
    while i < end:
        ch = token[i]
        if ch == ord("\\"):
            esc = token[i + 1]
            if esc == ord("\\"):
                out.append(ord("\\"))
                i += 2
            elif esc == ord('"'):
                out.append(ord('"'))
                i += 2
            elif esc == ord("a"):
                out.append(ord("\a"))
                i += 2
            elif esc == ord("b"):
                out.append(ord("\b"))
                i += 2
            elif esc == ord("f"):
                out.append(ord("\f"))
                i += 2
            elif esc == ord("n"):
                out.append(ord("\n"))
                i += 2
            elif esc == ord("r"):
                out.append(ord("\r"))
                i += 2
            elif esc == ord("t"):
                out.append(ord("\t"))
                i += 2
            elif esc == ord("v"):
                out.append(ord("\v"))
                i += 2
            elif ord("0") <= esc <= ord("7"):
                j = i + 1
                while j < len(token) and j < i + 4 and ord("0") <= token[j] <= ord("7"):
                    j += 1
                out.append(int(token[i + 1 : j], 8))
                i = j
            else:
                return None
        else:
            out.append(ch)
            i += 1
    return bytes(out)


def _path_token_from_minus_plus_rest(rest):
    """Extract one path token from bytes after ``--- `` / ``+++ ``."""
    if rest.startswith(b'"'):
        end = _scan_c_quoted_end(rest)
        if end is None:
            return None
        return rest[: end + 1]
    tab = rest.find(b"\t")
    if tab == -1:
        return rest
    return rest[:tab]


def _decode_diff_path_token(token):
    """Decode one path token from a ``---``/``+++`` line or ``diff --git`` header."""
    if token is None:
        return _DIFF_PATH_UNDERIVABLE
    if token == b"/dev/null":
        return None
    if token.startswith(b'"'):
        decoded = _unquote_c_style(token)
        if decoded is None:
            return _DIFF_PATH_UNDERIVABLE
        token = decoded
    if token.startswith(b"a/"):
        token = token[2:]
    elif token.startswith(b"b/"):
        token = token[2:]
    else:
        return _DIFF_PATH_UNDERIVABLE
    try:
        return token.decode("utf-8", errors="surrogateescape")
    except Exception:
        return _DIFF_PATH_UNDERIVABLE


def _paths_from_diff_git_header(line):
    """Return (old_path, new_path) from a ``diff --git`` line, or underivable sentinels."""
    prefix = b"diff --git "
    if not line.startswith(prefix):
        return _DIFF_PATH_UNDERIVABLE, _DIFF_PATH_UNDERIVABLE
    rest = line[len(prefix) :]
    if rest.startswith(b'"'):
        end = _scan_c_quoted_end(rest)
        if end is None:
            return _DIFF_PATH_UNDERIVABLE, _DIFF_PATH_UNDERIVABLE
        side_one = rest[: end + 1]
        remainder = rest[end + 1 :]
        if not remainder.startswith(b" "):
            return _DIFF_PATH_UNDERIVABLE, _DIFF_PATH_UNDERIVABLE
        side_two = remainder[1:]
        return (
            _decode_diff_path_token(side_one),
            _decode_diff_path_token(side_two),
        )
    # ``--no-renames`` means git never emits differing sides; the `` b/`` split below
    # depends on that invariant — keep them coupled if the flag changes.
    candidates = []
    for i in range(len(rest) - 2):
        if rest[i : i + 3] == b" b/":
            candidates.append((rest[:i], rest[i + 1 :]))
    if not candidates:
        return _DIFF_PATH_UNDERIVABLE, _DIFF_PATH_UNDERIVABLE
    equal_pairs = []
    for side_one, side_two in candidates:
        old_path = _decode_diff_path_token(side_one)
        new_path = _decode_diff_path_token(side_two)
        if (
            old_path is not _DIFF_PATH_UNDERIVABLE
            and new_path is not _DIFF_PATH_UNDERIVABLE
            and old_path == new_path
        ):
            equal_pairs.append((old_path, new_path))
    if len(equal_pairs) == 1:
        return equal_pairs[0]
    if len(equal_pairs) > 1:
        return _DIFF_PATH_UNDERIVABLE, _DIFF_PATH_UNDERIVABLE
    if len(candidates) == 1:
        side_one, side_two = candidates[0]
        return _decode_diff_path_token(side_one), _decode_diff_path_token(side_two)
    return _DIFF_PATH_UNDERIVABLE, _DIFF_PATH_UNDERIVABLE


def _paths_from_diff_section(section):
    """Derive both sides' paths from one patch section (fail-closed on ambiguity)."""
    lines = section.split(b"\n")
    header_lines = []
    for line in lines:
        if line.startswith(b"@@"):
            break
        header_lines.append(line)
    minus_count = 0
    plus_count = 0
    minus_path = None
    plus_path = None
    for line in header_lines:
        if line.startswith(b"--- "):
            minus_count += 1
            minus_path = _decode_diff_path_token(_path_token_from_minus_plus_rest(line[4:]))
        elif line.startswith(b"+++ "):
            plus_count += 1
            plus_path = _decode_diff_path_token(_path_token_from_minus_plus_rest(line[4:]))
    if minus_count > 1 or plus_count > 1:
        return _DIFF_PATH_UNDERIVABLE, _DIFF_PATH_UNDERIVABLE
    git_old, git_new = (
        _paths_from_diff_git_header(lines[0])
        if lines
        else (_DIFF_PATH_UNDERIVABLE, _DIFF_PATH_UNDERIVABLE)
    )
    if minus_count == 0:
        old_path = git_old
    elif minus_path is None:
        old_path = git_old
    else:
        old_path = minus_path
    if plus_count == 0:
        new_path = git_new
    elif plus_path is None:
        new_path = git_new
    else:
        new_path = plus_path
    return old_path, new_path


def _split_patch_sections(patch_bytes):
    """Split a patch at top-level ``diff --`` boundaries; return git sections and span count."""
    if not patch_bytes:
        return [], 0
    boundaries = []
    if patch_bytes.startswith(b"diff --"):
        boundaries.append(0)
    search = 0
    while True:
        idx = patch_bytes.find(b"\ndiff --", search)
        if idx == -1:
            break
        boundaries.append(idx + 1)
        search = idx + 1
    if not boundaries:
        return [], 1 if patch_bytes.strip() else 0
    unrecognized_spans = 0
    if boundaries[0] > 0 and patch_bytes[:boundaries[0]].strip():
        unrecognized_spans += 1
    sections = []
    for i, start in enumerate(boundaries):
        end = boundaries[i + 1] if i + 1 < len(boundaries) else len(patch_bytes)
        span = patch_bytes[start:end]
        if span.startswith(b"diff --git "):
            sections.append(span)
        else:
            unrecognized_spans += 1
    return sections, unrecognized_spans


def _section_withhold_info(section):
    """Return (withhold, stripped_paths, underivable) for one patch section."""
    old_path, new_path = _paths_from_diff_section(section)
    lines = section.split(b"\n")
    git_old, git_new = (
        _paths_from_diff_git_header(lines[0])
        if lines
        else (_DIFF_PATH_UNDERIVABLE, _DIFF_PATH_UNDERIVABLE)
    )
    stripped_paths = set()
    underivable = False
    # Deliberately check all four path spellings: old_path/new_path from ---/+++
    # headers and git_old/git_new from the diff --git line. _paths_from_diff_section
    # resolves one winner per side, so on a header-spoofed section it can return the
    # attacker's path; the diff --git pair is the independent second opinion. A None
    # (/dev/null) side counts as underivable rather than skipped. Removing any of
    # the four reopens the header-spoof defect (see
    # test_patch_filter_modification_both_sides_spoofed_withheld).
    for path in (old_path, new_path, git_old, git_new):
        if path is _DIFF_PATH_UNDERIVABLE or path is None:
            underivable = True
        elif _rel_path_would_be_stripped(path):
            stripped_paths.add(path)
    withhold = underivable or bool(stripped_paths)
    return withhold, stripped_paths, underivable


def _filter_patch_sections(patch_bytes):
    """Output-side guarantee: drop sections touching stripped or underivable paths.

    Returns ``(kept_bytes, stripped_paths, underivable_section_count,
    unrecognized_spans)``.
    """
    if not patch_bytes:
        return b"", set(), 0, 0
    sections, unrecognized_spans = _split_patch_sections(patch_bytes)
    kept = []
    stripped_paths = set()
    underivable_sections = 0
    for section in sections:
        withhold, section_stripped, section_underivable = _section_withhold_info(section)
        if withhold:
            stripped_paths.update(section_stripped)
            if section_underivable and not section_stripped:
                underivable_sections += 1
        else:
            kept.append(section)
    if not kept:
        return b"", stripped_paths, underivable_sections, unrecognized_spans
    return b"".join(kept), stripped_paths, underivable_sections, unrecognized_spans


def _argv_byte_size(argv):
    """Sum NUL-terminated UTF-8 byte lengths for one argv vector."""
    total = 0
    for arg in argv:
        total += len(arg.encode("utf-8", errors="surrogateescape")) + 1
    return total


def _effective_review_diff_argv_budget():
    """Derive argv budget from host limits minus inherited git environment.

    Measured on the build host: ``getconf ARG_MAX`` is 1048576 and ``env | wc -c``
    is 4916, but neither is guaranteed on a user's machine.
    """
    budget = _REVIEW_DIFF_ARGV_MAX_BYTES
    try:
        arg_max = os.sysconf("SC_ARG_MAX")
    except (AttributeError, ValueError, OSError):
        arg_max = None
    if arg_max is not None and arg_max > 0:
        env = _git_env()
        env_bytes = sum(
            len(k.encode("utf-8", errors="surrogateescape"))
            + len(v.encode("utf-8", errors="surrogateescape"))
            + 2
            for k, v in env.items()
        )
        derived = arg_max - env_bytes - _REVIEW_DIFF_ARGV_MARGIN
        budget = min(budget, derived)
    return budget


def _review_diff_argv_prefix(repo_real, merge_base, head_sha):
    return [
        "git",
        "-C",
        repo_real,
        *_DIFF_CONFIG_OVERRIDES,
        *_DIFF_PATCH_FLAGS,
        merge_base,
        head_sha,
        "--",
    ]


_COLLAPSE_DEADLINE_CHECK_INTERVAL = 4096


def _collapse_descendant_pathspecs(pathspecs, started):
    """Drop pathspecs that are descendants of another pathspec in the vector.

    Sorted by path *segments* so that every descendant of a path follows it in one
    contiguous run: raw string order interleaves siblings (``a`` < ``a-b`` < ``a/c``
    by bytes, but ``a`` < ``a/c`` < ``a-b`` by segments), which would break a single
    scan. One pass with an ancestor stack then replaces the previous all-pairs
    comparison, taking the step from O(n^2) to a sort plus O(n). The ``ancestors``
    list is bounded at one element because the ``continue`` skips the push whenever
    an ancestor is already kept.

    ``started`` is the export clock. The deadline is checked before the sort, after
    the sort, and periodically through the scan, so this step cannot run past the
    export budget and then spawn a git subprocess anyway.
    """
    _check_export_deadline(started)
    ordered = sorted(set(pathspecs), key=lambda path: path.split("/"))
    _check_export_deadline(started)
    kept = []
    ancestors = []
    for index, path in enumerate(ordered):
        if index % _COLLAPSE_DEADLINE_CHECK_INTERVAL == 0:
            _check_export_deadline(started)
        while ancestors and not path.startswith(ancestors[-1] + "/"):
            ancestors.pop()
        if ancestors:
            continue
        kept.append(path)
        ancestors.append(path)
    return kept


def _batch_review_diff_pathspecs(repo_real, merge_base, head_sha, pathspecs, started):
    """Batch pathspecs so each emitted argv stays within the effective byte budget."""
    pathspecs = _collapse_descendant_pathspecs(pathspecs, started)
    prefix = _review_diff_argv_prefix(repo_real, merge_base, head_sha)
    prefix_bytes = _argv_byte_size(prefix)
    budget = _effective_review_diff_argv_budget()
    # Floor so at least one pathspec can be attempted; never zero or negative.
    min_budget = prefix_bytes + 1
    if budget < min_budget:
        budget = min_budget
    batches = []
    current = []
    current_path_bytes = 0
    for path in pathspecs:
        path_bytes = len(path.encode("utf-8", errors="surrogateescape")) + 1
        if not current:
            # A single path whose bytes plus the prefix exceed the budget is emitted
            # alone rather than dropped — git will fail loudly if the OS rejects it.
            current = [path]
            current_path_bytes = path_bytes
        elif prefix_bytes + current_path_bytes + path_bytes <= budget:
            current.append(path)
            current_path_bytes += path_bytes
        else:
            batches.append(current)
            current = [path]
            current_path_bytes = path_bytes
    if current:
        batches.append(current)
    return batches


def _section_is_opaque(section):
    """True when the pre-hunk header marks binary/opaque content (line-anchored)."""
    for line in section.split(b"\n"):
        if line.startswith(b"@@"):
            break
        if line.startswith(b"Binary files ") and line.endswith(b" differ"):
            return True
        if line.startswith(b"GIT binary patch"):
            return True
    return False


def _section_resolved_path_raw(section):
    """Resolve the single path for a section without applying withhold policy."""
    old_path, new_path = _paths_from_diff_section(section)
    lines = section.split(b"\n")
    git_old, git_new = (
        _paths_from_diff_git_header(lines[0])
        if lines
        else (_DIFF_PATH_UNDERIVABLE, _DIFF_PATH_UNDERIVABLE)
    )
    paths = set()
    for path in (old_path, new_path, git_old, git_new):
        if path is not None and path is not _DIFF_PATH_UNDERIVABLE:
            paths.add(path)
    if len(paths) != 1:
        return None
    return paths.pop()


def _reconcile_review_patch(patch_bytes, survivors, withheld):
    """Reconcile patch sections against the census survivor set; return kept bytes."""
    survivors_set = set(survivors)
    withheld_set = set(withheld)
    sections, unrecognized_spans = _split_patch_sections(patch_bytes)
    if unrecognized_spans > 0:
        raise SanitizedViewError("sanitized-view-diff-unaccounted")
    kept_sections = []
    rendered_paths = set()
    for section in sections:
        withhold, stripped_paths, underivable = _section_withhold_info(section)
        if underivable:
            raise SanitizedViewError("sanitized-view-diff-unaccounted")
        if withhold:
            # Pathspec prefix expansion on a directory→file transition can
            # legitimately emit diff sections for census-withheld descendants of
            # a survivor pathspec (e.g. pkg/CLAUDE.md when survivor is pkg); a
            # withheld path outside every survivor prefix cannot come from our
            # pathspec set. See test_review_diff_dir_to_file_transition_
            # withheld_child_is_skipped and
            # test_review_diff_withheld_section_outside_survivor_prefix_refuses.
            if (
                stripped_paths
                and stripped_paths.issubset(withheld_set)
                and all(
                    any(p.startswith(s + "/") for s in survivors_set)
                    for p in stripped_paths
                )
            ):
                continue
            raise SanitizedViewError("sanitized-view-diff-unaccounted")
        path = _section_resolved_path_raw(section)
        if path is None or path not in survivors_set:
            raise SanitizedViewError("sanitized-view-diff-unaccounted")
        if path in rendered_paths:
            # Backstop for overlapping pathspec batches (see _collapse_descendant_pathspecs).
            raise SanitizedViewError("sanitized-view-diff-unaccounted")
        kept_sections.append(section)
        rendered_paths.add(path)
    missing = set(survivors) - rendered_paths
    if missing:
        raise SanitizedViewError("sanitized-view-diff-unaccounted")
    if any(_section_is_opaque(section) for section in kept_sections):
        raise SanitizedViewError("sanitized-view-diff-opaque")
    if not kept_sections:
        return b""
    return b"".join(kept_sections)


def _write_review_patch_file(view_root, patch_bytes):
    patch_path = os.path.join(view_root, REVIEW_DIFF_FILE_NAME)
    if os.path.lexists(patch_path):
        raise SanitizedViewError("sanitized-view-diff-path-collision")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(patch_path, flags, 0o600)
    except FileExistsError:
        raise SanitizedViewError("sanitized-view-diff-path-collision")
    except OSError:
        raise SanitizedViewError("sanitized-view-diff-path-collision")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(patch_bytes)
    except Exception:
        try:
            os.unlink(patch_path)
        except OSError:
            pass
        raise
    _assert_no_stripped_paths_in_view(view_root)


def _git_diff_batch_output(argv, started, total_bytes):
    """Stream one pathspec-restricted diff batch; bound bytes and subprocess lifetime."""
    _check_export_deadline(started)
    proc = None
    try:
        try:
            proc = _git_popen(
                argv,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
        except OSError:
            raise SanitizedViewError("sanitized-view-diff-failed")
        chunks = []
        fd = proc.stdout.fileno()
        while True:
            _check_export_deadline(started)
            slice_seconds = min(
                _DIFF_READ_POLL_SECONDS,
                _remaining_export_timeout(started),
            )
            try:
                ready, _, _ = select.select([fd], [], [], slice_seconds)
            except OSError as exc:
                raise SanitizedViewError("sanitized-view-diff-failed") from exc
            if not ready:
                continue
            try:
                data = os.read(fd, _CATFILE_READ_CHUNK)
            except InterruptedError:
                continue
            except OSError as exc:
                raise SanitizedViewError("sanitized-view-diff-failed") from exc
            if not data:
                break
            total_bytes += len(data)
            if total_bytes > REVIEW_DIFF_MAX_BYTES:
                raise SanitizedViewError("sanitized-view-diff-too-large")
            chunks.append(data)
        try:
            proc.wait(timeout=_remaining_export_timeout(started))
        except subprocess.TimeoutExpired:
            raise SanitizedViewError("sanitized-view-diff-failed")
        if proc.returncode != 0:
            raise SanitizedViewError("sanitized-view-diff-failed")
        return b"".join(chunks), total_bytes
    except SanitizedViewError:
        raise
    finally:
        if proc is not None:
            _terminate_process(proc)


def _stage_review_diff(repo_real, head_sha, view_root, diff_base, started):
    """Materialize a review patch at the view root (before ``git init``)."""
    if not diff_base or not diff_base.strip():
        raise SanitizedViewError("sanitized-view-diff-base-unresolved")
    if diff_base.startswith("-"):
        raise SanitizedViewError("sanitized-view-diff-base-unresolved")

    _check_export_deadline(started)
    timeout = _remaining_export_timeout(started)
    try:
        proc = _git_run(
            [
                "git",
                "-C",
                repo_real,
                *_DIFF_CONFIG_OVERRIDES,
                "rev-parse",
                "--verify",
                "--end-of-options",
                "%s^{commit}" % diff_base,
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise SanitizedViewError("sanitized-view-diff-failed")
    except OSError:
        raise SanitizedViewError("sanitized-view-diff-base-unresolved")
    if proc.returncode != 0 or not proc.stdout.strip():
        raise SanitizedViewError("sanitized-view-diff-base-unresolved")
    base_sha = proc.stdout.strip()
    if not _is_git_object_id_hex(base_sha):
        raise SanitizedViewError("sanitized-view-diff-base-unresolved")

    merge_base = _authoritative_merge_base(repo_real, base_sha, head_sha, started)

    changed = _changed_tree_entries(repo_real, merge_base, head_sha, started)
    withheld = [p for p in changed if _rel_path_would_be_stripped(p)]
    survivors = [p for p in changed if not _rel_path_would_be_stripped(p)]

    if not changed:
        raise SanitizedViewError("sanitized-view-diff-empty")
    if not survivors:
        raise SanitizedViewError("sanitized-view-diff-fully-withheld")

    patch_parts = []
    total_bytes = 0
    for batch in _batch_review_diff_pathspecs(
        repo_real, merge_base, head_sha, survivors, started
    ):
        argv = [
            *_review_diff_argv_prefix(repo_real, merge_base, head_sha),
            *batch,
        ]
        chunk, total_bytes = _git_diff_batch_output(argv, started, total_bytes)
        patch_parts.append(chunk)

    patch_bytes = b"".join(patch_parts)
    # _reconcile_review_patch applies _section_withhold_info per section — the
    # output-side withhold check lives there, not in a separate filter pass.
    patch_bytes = _reconcile_review_patch(patch_bytes, survivors, withheld)

    if not patch_bytes:
        raise SanitizedViewError("sanitized-view-diff-empty")

    _write_review_patch_file(view_root, patch_bytes)

    return {
        "diffBase": merge_base,
        "diffPath": REVIEW_DIFF_FILE_NAME,
        "diffBytes": len(patch_bytes),
        "diffWithheldCount": len(withheld),
    }


def build_sanitized_view(repo_root, *, diff_base=None):
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
        if diff_base is None:
            diff_info = {
                "diffBase": None,
                "diffPath": None,
                "diffBytes": None,
                "diffWithheldCount": None,
            }
        else:
            diff_info = _stage_review_diff(
                repo_real, head_sha, view_root, diff_base, started
            )
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
            **diff_info,
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
