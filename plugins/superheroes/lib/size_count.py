#!/usr/bin/env python3
"""PR size counters: tripwire vs bar, with whole-file deletions listed (#1447). stdlib and sibling lib modules only."""
import argparse
import contextlib
import fnmatch
import json
import os
import subprocess
import sys
import time

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import core_md  # noqa: E402
import git_routing  # noqa: E402  the one home of the git routing-var list

GIT_TIMEOUT = 60
_GIT_ROUTING_VARS = git_routing.GIT_ROUTING_VARS
# ``git ls-files -v`` tags for assume-unchanged (h), skip-worktree (S) and both (s).
_HIDDEN_TAGS = frozenset("hsS")

# Axis: a path is test code iff a directory component (case-insensitive) is a TEST_DIR_NAMES member or the file name (case-sensitive globs) matches TEST_FILE_GLOBS; the one home of the size rule's test-path list (rubric/review-discipline.md § Size).
TEST_DIR_NAMES = frozenset({
    "test", "tests", "__tests__", "spec", "e2e", "testdata", "__mocks__", "__fixtures__",
    # Test-support directories: hand-written doubles and helpers (#1544).
    "test-utils", "test_utils", "testutils", "test-helpers", "test_helpers", "test-support",
})
TEST_FILE_GLOBS = (
    "*.test.*",
    "*.spec.*",
    "test_*.py",
    "*_test.py",
    "*_test.go",
    "conftest.py",
)


def is_test_path(path):
    """True when ``path`` is test code: a test directory component or a test file name (see ``TEST_DIR_NAMES`` / ``TEST_FILE_GLOBS``)."""
    normalized = path.replace("\\", "/")
    parts = normalized.split("/")
    if not parts:
        return False
    name = parts[-1]
    for component in parts[:-1]:
        if component.lower() in TEST_DIR_NAMES:
            return True
    return any(fnmatch.fnmatchcase(name, pattern) for pattern in TEST_FILE_GLOBS)


# Axis: a path is a lockfile iff its base name (the last "/" component, case-sensitive, at any depth) is a LOCKFILE_NAMES member; the one home of the size rule's lockfile list (rubric/review-discipline.md § Size).
LOCKFILE_NAMES = frozenset({
    "package-lock.json", "npm-shrinkwrap.json", "yarn.lock", "pnpm-lock.yaml", "bun.lockb",
    "uv.lock", "poetry.lock", "Pipfile.lock", "Cargo.lock", "Gemfile.lock", "composer.lock",
    "go.sum",
})


def is_lockfile(path):
    """True when the base name of ``path`` is a ``LOCKFILE_NAMES`` member."""
    return path.replace("\\", "/").split("/")[-1] in LOCKFILE_NAMES


def count(numstat_rows, deleted_paths, bar_exclude=(), size_exclude=None):
    """Pure size count from parsed numstat rows and deleted path names.

    ``bar_exclude`` lists regenerated artifacts (review-discipline Size § bars): paths
    here still add to ``tripwireCount`` but not ``barCount``, and appear in ``barExcluded``.
    Lockfiles (``LOCKFILE_NAMES``) and paths matching a ``size_exclude`` glob count toward
    neither number and are listed in ``lockfilesExcluded`` / ``pathsExcluded`` with their line
    counts. ``size_exclude`` None means the calibration key is absent; a list (possibly empty)
    means declared.
    """
    tripwire = 0
    bar = 0
    deleted_files = []
    binary = []
    lockfiles = []
    paths_excluded = []
    bar_exclude_set = frozenset(bar_exclude or ())
    bar_excluded = set()

    for added, deleted, path in numstat_rows:
        if is_test_path(path):
            continue
        if added is None or deleted is None:
            binary.append(path)
            continue
        if path in deleted_paths and added == 0:
            deleted_files.append({"path": path, "lines": deleted})
            continue
        if is_lockfile(path):
            lockfiles.append({"path": path, "lines": added + deleted})
            continue
        if size_exclude is not None:
            normalized = path.replace("\\", "/")
            glob = next((g for g in size_exclude if fnmatch.fnmatchcase(normalized, g)), None)
            if glob is not None:
                paths_excluded.append({"path": path, "lines": added + deleted, "glob": glob})
                continue
        tripwire += added + deleted
        if path in bar_exclude_set:
            bar_excluded.add(path)
        else:
            bar += added

    deleted_files.sort(key=lambda item: item["path"])
    binary.sort()
    lockfiles.sort(key=lambda item: item["path"])
    paths_excluded.sort(key=lambda item: item["path"])
    out = {
        "tripwireCount": tripwire,
        "barCount": bar,
        "deletedFiles": deleted_files,
        "binary": binary,
    }
    if bar_exclude_set:
        out["barExcluded"] = sorted(bar_excluded)
    if lockfiles:
        out["lockfilesExcluded"] = lockfiles
    if size_exclude is not None:
        out["pathsExcluded"] = paths_excluded
    return out


def _parse_numstat_z(raw_bytes):
    text = raw_bytes.decode("utf-8", errors="surrogateescape")
    fields = text.split("\0")
    while fields and fields[-1] == "":
        fields.pop()
    rows = []
    i = 0
    n = len(fields)
    while i < n:
        row = fields[i]
        parts = row.split("\t")
        if len(parts) < 2:
            i += 1
            continue
        a, d = parts[0], parts[1]
        if a == "-" or d == "-":
            added, deleted = None, None
        else:
            try:
                added, deleted = int(a), int(d)
            except ValueError:
                i += 1
                continue
        if len(parts) >= 3 and parts[2] != "":
            path = parts[2]
            i += 1
        elif len(parts) >= 3 and parts[2] == "":
            if i + 2 < n:
                path = fields[i + 2]
                i += 3
            else:
                i += 1
                continue
        else:
            i += 1
            continue
        rows.append((added, deleted, path))
    return rows


def _parse_deleted_paths(raw_bytes):
    text = raw_bytes.decode("utf-8", errors="surrogateescape")
    fields = text.split("\0")
    while fields and fields[-1] == "":
        fields.pop()
    deleted = set()
    i = 0
    while i < len(fields):
        if fields[i] == "D" and i + 1 < len(fields):
            deleted.add(fields[i + 1])
            i += 2
        else:
            i += 1
    return deleted


def _git_failed(stderr_bytes):
    line = stderr_bytes.decode("utf-8", errors="replace").splitlines()
    return {"ok": False, "reason": "git-failed", "detail": line[0] if line else ""}


def _git_env():
    env = {k: v for k, v in os.environ.items() if k not in _GIT_ROUTING_VARS}
    env["GIT_OPTIONAL_LOCKS"] = "0"
    return env


@contextlib.contextmanager
def _git_routing_scrubbed_environ():
    """Hide the ambient Git routing variables from callees that read ``os.environ`` themselves.

    The calibration read resolves its repository through store_core, whose Git subprocess copies
    the ambient environment; the diffs beside it are scrubbed, and the two must name the same
    repository."""
    saved = {k: os.environ.pop(k) for k in _GIT_ROUTING_VARS if k in os.environ}
    try:
        yield
    finally:
        os.environ.update(saved)


def _run_git(repo_root, args, deadline, ok_codes=(0,)):
    """One hardened git call: ``(proc, None)`` on success, ``(None, failure_result)`` otherwise."""
    timeout = GIT_TIMEOUT
    if deadline is not None:
        timeout = min(GIT_TIMEOUT, deadline - time.monotonic())
        # Axis: a call is never started once the caller's deadline has passed.
        if timeout <= 0:
            return None, {"ok": False, "reason": "git-timeout"}
    argv = ["git", "-C", repo_root, "-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=", *args]
    try:
        proc = subprocess.run(argv, capture_output=True, timeout=timeout, env=_git_env())
    except subprocess.TimeoutExpired:
        return None, {"ok": False, "reason": "git-timeout"}
    except FileNotFoundError:
        return None, {"ok": False, "reason": "git-unavailable"}
    if proc.returncode not in ok_codes:
        return None, _git_failed(proc.stderr)
    return proc, None


def _hides_changes(ls_files_v_stdout):
    """True when any ``ls-files -v -z`` entry carries an assume-unchanged or skip-worktree tag."""
    text = ls_files_v_stdout.decode("utf-8", errors="surrogateescape")
    # Axis: index flags that hide working-tree edits from ``git diff`` refuse the count.
    return any(entry[:1] in _HIDDEN_TAGS for entry in text.split("\0") if entry)


def _untracked_rows(repo_root, deadline):
    """``(rows, nested_repos, None)`` on success, ``(None, None, failure_result)`` otherwise."""
    listed, failure = _run_git(repo_root, ["ls-files", "-o", "--exclude-standard", "-z"], deadline)
    if failure:
        return None, None, failure
    paths = [p for p in listed.stdout.decode("utf-8", errors="surrogateescape").split("\0") if p]
    rows = []
    repos = []
    for path in paths:
        # Axis: a nested repository (listed with a trailing "/") is never diffed; it is named, not counted.
        if path.endswith("/"):
            repos.append(path)
            continue
        # Axis: a file operand of "-" is stdin to --no-index; it is "./"-prefixed and the row keeps the listed path.
        proc, failure = _run_git(
            repo_root,
            ["-c", "core.safecrlf=false", "diff", "--no-index", "--numstat", "-z", "--", "/dev/null", "./" + path],
            deadline,
            ok_codes=(0, 1),
        )
        if failure:
            return None, None, failure
        # Axis: exit 1 is "differences found" only when stderr is empty; git also exits 1 on access errors.
        if proc.stderr.strip() != b"":
            return None, None, _git_failed(proc.stderr)
        rows.extend((added, deleted, path) for added, deleted, _ in _parse_numstat_z(proc.stdout))
    return rows, sorted(repos), None


def collect(repo_root, base, head="HEAD", bar_exclude=(), deadline=None, root=None):
    """Run git diffs between ``base`` and ``head`` and return size JSON.

    ``head=None`` counts the working tree of ``repo_root`` against ``base``: committed, uncommitted
    and untracked-but-not-ignored changes, read-only. Failures return ``ok: False`` with a ``reason``.
    Both modes apply the project's ``sizeExclude`` calibration (read from ``repo_root``) in ``count()``.
    """
    worktree = head is None
    # Axis: the trailing "--" makes base a revision only; an unresolvable base fails instead of becoming a pathspec.
    diff_tail = ["--end-of-options", base, "--"] if worktree else ["--end-of-options", base, head, "--"]
    if worktree:
        flags, failure = _run_git(repo_root, ["ls-files", "-v", "-z"], deadline)
        if failure:
            return failure
        if _hides_changes(flags.stdout):
            return {"ok": False, "reason": "index-flags-hide-changes"}
    numstat, failure = _run_git(repo_root, ["diff", "--numstat", "-z", "-M", *diff_tail], deadline)
    if failure:
        return failure
    status, failure = _run_git(
        repo_root, ["diff", "--name-status", "-z", "-M", "--diff-filter=D", *diff_tail], deadline
    )
    if failure:
        return failure

    rows = _parse_numstat_z(numstat.stdout)
    deleted_paths = _parse_deleted_paths(status.stdout)
    if worktree:
        untracked, repos, failure = _untracked_rows(repo_root, deadline)
        if failure:
            return failure
        rows = rows + untracked
    # Axis: the calibration read runs git too, so it runs after the diffs and never past the deadline.
    if deadline is not None and deadline - time.monotonic() <= 0:
        return {"ok": False, "reason": "git-timeout"}
    try:
        with _git_routing_scrubbed_environ():
            read = core_md.read_size_exclude(repo_root, root)
    except Exception as exc:
        return {"ok": False, "reason": "size-exclude-unreadable",
                "detail": "%s: %s" % (type(exc).__name__, exc)}
    if read["reason"] == "size-exclude-malformed":
        return {"ok": False, "reason": "size-exclude-malformed", "malformed": read["malformed"]}
    if read["reason"] not in (None, "core-md-absent"):
        return {"ok": False, "reason": "size-exclude-unreadable",
                "detail": read["detail"] or read["reason"]}
    result = count(rows, deleted_paths, bar_exclude=bar_exclude, size_exclude=read["globs"])
    result["base"] = base
    result["head"] = head
    if worktree:
        result["worktree"] = True
        result["untrackedRepos"] = repos
    result["ok"] = True
    return result


def _emit(result):
    sys.stdout.write(json.dumps(result, sort_keys=True) + "\n")


def main(argv):
    ap = argparse.ArgumentParser(description="PR size tripwire/bar counters")
    sub = ap.add_subparsers(dest="cmd", required=True)
    cnt = sub.add_parser("count")
    cnt.add_argument("--base", required=True)
    head_group = cnt.add_mutually_exclusive_group()
    head_group.add_argument("--head", default="HEAD")
    head_group.add_argument(
        "--worktree",
        action="store_true",
        help="count the working tree (committed, uncommitted, untracked) against --base",
    )
    cnt.add_argument("--repo-root", default=".")
    cnt.add_argument(
        "--bar-exclude",
        action="append",
        default=[],
        dest="bar_exclude",
        help="path excluded from barCount (repeatable; regenerated artifacts)",
    )
    args = ap.parse_args(argv[1:])
    if args.cmd == "count":
        result = collect(
            args.repo_root,
            args.base,
            None if args.worktree else args.head,
            bar_exclude=tuple(args.bar_exclude),
        )
        _emit(result)
        return 0 if result.get("ok") else 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
