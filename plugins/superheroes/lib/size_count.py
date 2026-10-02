#!/usr/bin/env python3
"""PR size counters: tripwire vs bar, with whole-file deletions listed (#1447). stdlib only."""
import argparse
import fnmatch
import json
import os
import subprocess
import sys
import time

GIT_TIMEOUT = 60
# Same list as engine_dispatch._GIT_ROUTING_VARS (copied: this module stays stdlib-only).
_GIT_ROUTING_VARS = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY",
                     "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_CONFIG", "GIT_CONFIG_GLOBAL",
                     "GIT_CONFIG_SYSTEM", "GIT_COMMON_DIR")
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


def count(numstat_rows, deleted_paths, bar_exclude=()):
    """Pure size count from parsed numstat rows and deleted path names.

    ``bar_exclude`` lists regenerated artifacts (review-discipline Size § bars): paths
    here still add to ``tripwireCount`` but not ``barCount``, and appear in ``barExcluded``.
    """
    tripwire = 0
    bar = 0
    deleted_files = []
    binary = []
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
        tripwire += added + deleted
        if path in bar_exclude_set:
            bar_excluded.add(path)
        else:
            bar += added

    deleted_files.sort(key=lambda item: item["path"])
    binary.sort()
    out = {
        "tripwireCount": tripwire,
        "barCount": bar,
        "deletedFiles": deleted_files,
        "binary": binary,
    }
    if bar_exclude_set:
        out["barExcluded"] = sorted(bar_excluded)
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
        proc, failure = _run_git(
            repo_root,
            ["diff", "--no-index", "--numstat", "-z", "--", "/dev/null", path],
            deadline,
            ok_codes=(0, 1),
        )
        if failure:
            return None, None, failure
        # Axis: exit 1 is "differences found" only when stderr is empty; git also exits 1 on access errors.
        if proc.stderr.strip() != b"":
            return None, None, _git_failed(proc.stderr)
        rows.extend(_parse_numstat_z(proc.stdout))
    return rows, sorted(repos), None


def collect(repo_root, base, head="HEAD", bar_exclude=(), deadline=None):
    """Run git diffs between ``base`` and ``head`` and return size JSON.

    ``head=None`` counts the working tree of ``repo_root`` against ``base``: committed, uncommitted
    and untracked-but-not-ignored changes, read-only. Failures return ``ok: False`` with a ``reason``.
    """
    worktree = head is None
    diff_tail = ["--end-of-options", base] if worktree else ["--end-of-options", base, head]
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
    result = count(rows, deleted_paths, bar_exclude=bar_exclude)
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
