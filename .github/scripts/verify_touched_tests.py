#!/usr/bin/env python3
"""Run the tests a diff touched — the second half of this project's verify command (#1307).

The four validators say nothing about the test suite, so a certified review loop's fix round
could leave tests red and still report the verify gate green (observed three times on PR #1295).
This script closes that: every changed file in the diff is either matched to the test files that
reference it, refused with a named reason, or named on stdout as referenced by nothing — no
changed file is silently dropped.

Selection is computed from test files' own text on every run; there is no maintained list of
modules, roots, or mappings. Direct references only — a test that reaches a changed module
through another module is not selected. CI's full suite is the receipt for anything this gate
does not run. The matcher deliberately over-selects for short, generic module names, because
the fail direction is toward running more tests, never fewer. On a stacked branch the diff still
includes the lower layers' files, so the selection is a superset.

Fail direction, by construction:
  * a still-present changed Python source file that NO test file references exits **non-zero**
    naming the file — an unreferenced source is loud, never a silent no-op;
  * a changed ``conftest.py`` exits **non-zero** with a tree-naming message;
  * a diff that changed no code exits **0** and says so;
  * otherwise the exit status is pytest's own.

Stdlib only; runs under the repo's `/usr/bin/python3` (3.9) as well as CI's 3.12.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys

# CLAUDE.md pins these: Apple's python caches bytecode outside the tree, so a same-size,
# same-second edit otherwise runs stale bytecode.
DEFAULT_PYTHON = "/usr/bin/python3"
PYCACHE_PREFIX = "/private/tmp/superheroes-pyc"
PYTEST_ARGS = ("-q", "-n", "auto", "-p", "no:cacheprovider")

BASE_REF_CANDIDATES = ("origin/main", "main")

_PATH_SEP_ALT = r"(?:/|['\"][ \t]*[,/][ \t]*['\"])"


class GitError(RuntimeError):
    """A git invocation this script depends on failed."""


def _git(repo_root, *args):
    proc = subprocess.run(
        ("git", "-C", repo_root) + args,
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise GitError("git %s failed: %s" % (" ".join(args), (proc.stderr or "").strip()))
    return proc.stdout


def _git_paths(repo_root, *args):
    """Paths from a NUL-delimited git listing.

    `-z` is not cosmetic: with git's default ``core.quotePath``, a path holding a non-ASCII
    character comes back C-quoted (``"plugins/.../test_caf\\303\\251.py"``), which no longer
    ends in ``.py`` — the resolver would read the diff as touching no code and exit 0. A path
    holding a newline would split into two bogus entries for the same reason.
    """
    out = _git(repo_root, *(args + ("-z",)))
    return [p for p in out.split("\0") if p]


def _rev_exists(repo_root, ref):
    proc = subprocess.run(
        ("git", "-C", repo_root, "rev-parse", "--verify", "--quiet", ref + "^{commit}"),
        capture_output=True, text=True,
    )
    return proc.returncode == 0


def resolve_base(repo_root, base=None):
    """The ref the diff is taken from: the one given, else the first candidate that exists."""
    if base:
        if not _rev_exists(repo_root, base):
            raise GitError("base ref %r does not resolve" % base)
        return base
    for candidate in BASE_REF_CANDIDATES:
        if _rev_exists(repo_root, candidate):
            return candidate
    raise GitError(
        "no base ref found (tried %s) — pass --base or --range" % ", ".join(BASE_REF_CANDIDATES)
    )


def changed_paths(repo_root, *, base=None, diff_range=None):
    """Repo-relative paths the diff touched.

    ``--range`` is a pure commit-to-commit comparison. Otherwise the comparison runs from the
    merge-base with the base ref to the **working tree**, untracked files included — a fix
    round's edits are uncommitted, and they are exactly what this gate exists to see.
    """
    if diff_range:
        return sorted(set(_git_paths(repo_root, "diff", "--name-only", "--no-renames", diff_range)))
    base_ref = resolve_base(repo_root, base)
    merge_base = _git(repo_root, "merge-base", base_ref, "HEAD").strip()
    paths = set(_git_paths(repo_root, "diff", "--name-only", "--no-renames", merge_base))
    paths |= set(_git_paths(repo_root, "ls-files", "--others", "--exclude-standard"))
    return sorted(paths)


def _is_test_file(path):
    if not path.endswith(".py"):
        return False
    parts = path.split("/")
    if not parts[-1].startswith("test_"):
        return False
    return "tests" in parts[:-1]


def _is_conftest(path):
    return os.path.basename(path) == "conftest.py"


def _is_tests_tree_helper(path):
    if not path.endswith(".py"):
        return False
    parts = path.split("/")
    if "tests" not in parts[:-1]:
        return False
    if parts[-1] == "conftest.py":
        return False
    if parts[-1].startswith("test_"):
        return False
    return True


def _classify_path(path):
    if _is_test_file(path):
        return "test"
    if _is_conftest(path):
        return "conftest"
    if _is_tests_tree_helper(path):
        return "helper"
    if path.endswith(".py"):
        return "python"
    return "non_python"


def _all_test_files(repo_root):
    paths = set(_git_paths(repo_root, "ls-files"))
    paths |= set(_git_paths(repo_root, "ls-files", "--others", "--exclude-standard"))
    return sorted(p for p in paths if _is_test_file(p))


def _read_test_text(repo_root, path):
    try:
        with open(os.path.join(repo_root, path), encoding="utf-8", errors="replace") as handle:
            return handle.read()
    except OSError:
        return None


def _reference_patterns(changed_path, is_python):
    """Compiled patterns that select test files referencing ``changed_path``."""
    patterns = []
    basename = os.path.basename(changed_path)
    segments = changed_path.split("/")

    if is_python:
        mod = basename[:-3]
        patterns.append(re.compile(
            r"^[ \t]*from[ \t]+" + re.escape(mod) + r"\b", re.MULTILINE))
        patterns.append(re.compile(
            r"^[ \t]*import[ \t]+(?:[^,\n#]*,\s*)*" + re.escape(mod) + r"\b",
            re.MULTILINE))
        patterns.append(re.compile(r'["\']' + re.escape(mod) + r'["\']'))
        patterns.append(re.compile(r'["\']' + re.escape(mod) + r"\.[a-zA-Z_]"))
        patterns.append(re.compile(re.escape(basename)))
    else:
        patterns.append(re.compile(r'["\']' + re.escape(basename) + r'["\']'))

    for index in range(len(segments) - 1):
        suffix = segments[index:]
        if len(suffix) < 2:
            continue
        escaped = [re.escape(part) for part in suffix]
        patterns.append(re.compile(_PATH_SEP_ALT.join(escaped)))

    return patterns


def _find_referencing_tests(changed_path, is_python, test_texts):
    patterns = _reference_patterns(changed_path, is_python)
    selected = set()
    for test_path, text in test_texts.items():
        if text is None:
            continue
        for pattern in patterns:
            if pattern.search(text):
                selected.add(test_path)
                break
    return selected


def select_targets(repo_root, paths):
    """Classify every changed path and resolve the test files to run.

    Returns (selected_tests, conftest_refusals, no_reference_refusals, deleted_tests,
    retired_python, unreferenced_non_python, code_changed).
    """
    selected_tests = set()
    conftest_refusals = []
    no_reference_refusals = []
    deleted_tests = []
    retired_python = []
    unreferenced_non_python = []
    code_changed = False

    all_tests = _all_test_files(repo_root)
    test_texts = {path: _read_test_text(repo_root, path) for path in all_tests}

    for path in paths:
        exists = os.path.exists(os.path.join(repo_root, path))
        shape = _classify_path(path)

        if path.endswith(".py"):
            code_changed = True

        if shape == "test":
            if exists:
                selected_tests.add(path)
            else:
                deleted_tests.append(path)
            continue

        if shape == "conftest":
            conftest_refusals.append(path)
            continue

        if shape == "helper":
            selected_tests.update(_find_referencing_tests(path, True, test_texts))
            continue

        if shape == "python":
            refs = _find_referencing_tests(path, True, test_texts)
            if exists:
                if refs:
                    selected_tests.update(refs)
                else:
                    no_reference_refusals.append(path)
            else:
                if refs:
                    selected_tests.update(refs)
                else:
                    retired_python.append(path)
            continue

        refs = _find_referencing_tests(path, False, test_texts)
        if refs:
            selected_tests.update(refs)
        else:
            unreferenced_non_python.append(path)

    return (
        sorted(selected_tests),
        sorted(conftest_refusals),
        sorted(no_reference_refusals),
        sorted(deleted_tests),
        sorted(retired_python),
        sorted(unreferenced_non_python),
        code_changed,
    )


def pytest_command(python, test_files):
    return [python, "-B", "-X", "pycache_prefix=" + PYCACHE_PREFIX,
            "-m", "pytest"] + list(test_files) + list(PYTEST_ARGS)


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="run the tests the diff touched (the project's verify command, #1307)")
    ap.add_argument("--repo-root", default=None,
                    help="repository root (default: the git root of the current directory)")
    ap.add_argument("--base", default=None,
                    help="base ref to diff from (default: origin/main, else main)")
    ap.add_argument("--range", dest="diff_range", default=None,
                    help="an explicit git diff range (A..B); compares commits only")
    ap.add_argument("--python", default=DEFAULT_PYTHON,
                    help="interpreter that runs pytest (default: %s)" % DEFAULT_PYTHON)
    ap.add_argument("--list-only", action="store_true",
                    help="print the resolved test files and exit without running pytest")
    args = ap.parse_args(argv)

    repo_root = args.repo_root
    if repo_root is None:
        try:
            repo_root = _git(os.getcwd(), "rev-parse", "--show-toplevel").strip()
        except GitError as exc:
            sys.stderr.write("verify-touched-tests: %s\n" % exc)
            return 2
    repo_root = os.path.abspath(repo_root)

    try:
        paths = changed_paths(repo_root, base=args.base, diff_range=args.diff_range)
    except GitError as exc:
        sys.stderr.write("verify-touched-tests: %s\n" % exc)
        return 2

    (
        test_files,
        conftest_refusals,
        no_reference_refusals,
        deleted_tests,
        retired_python,
        unreferenced_non_python,
        code_changed,
    ) = select_targets(repo_root, paths)

    if deleted_tests:
        sys.stdout.write(
            "verify-touched-tests: %d test file(s) deleted; not run:\n%s"
            % (len(deleted_tests), "".join("  - %s\n" % p for p in deleted_tests)))

    if retired_python:
        sys.stdout.write(
            "verify-touched-tests: %d Python source file(s) deleted with no surviving "
            "referencing tests; nothing left to run for them:\n%s"
            % (len(retired_python), "".join("  - %s\n" % p for p in retired_python)))

    if unreferenced_non_python:
        sys.stdout.write(
            "verify-touched-tests: %d path(s) referenced by nothing:\n%s"
            % (len(unreferenced_non_python),
               "".join("  - %s\n" % p for p in unreferenced_non_python)))

    if conftest_refusals:
        # axis: refusal fires on a changed conftest.py by path shape alone — not on whether
        # any test resolves for it.
        sys.stderr.write(
            "verify-touched-tests: a conftest.py changed; this gate cannot select for it:\n%s"
            "A conftest change can affect every test in its tree. run that tree's suite "
            "yourself;\nCI is the receipt.\n"
            % ("".join("  - %s\n" % p for p in conftest_refusals)))

    if no_reference_refusals:
        # axis: refusal fires on a still-present Python source that NO test file references —
        # not on absence of tests generally, and not on a deleted file.
        sys.stderr.write(
            "verify-touched-tests: no test file references %d changed Python source "
            "file(s):\n%s\n"
            "Add a test that imports or names the source, or run that module's suite "
            "yourself; CI is the receipt.\n"
            % (len(no_reference_refusals),
               "".join("  - %s\n" % p for p in no_reference_refusals)))

    if conftest_refusals or no_reference_refusals:
        return 1

    if not test_files:
        if not code_changed:
            sys.stdout.write("verify-touched-tests: no code changed; no tests to run.\n")
        else:
            sys.stdout.write(
                "verify-touched-tests: code changed but no touched test files resolved "
                "(no changed file selected any test).\n")
        return 0

    sys.stdout.write("verify-touched-tests: %d test file(s) resolved:\n%s"
                     % (len(test_files), "".join("  - %s\n" % f for f in test_files)))
    command = pytest_command(args.python, test_files)
    if args.list_only:
        sys.stdout.write("verify-touched-tests: would run %s\n" % " ".join(command))
        return 0
    sys.stdout.write("verify-touched-tests: running %s\n" % " ".join(command))
    sys.stdout.flush()
    return subprocess.run(command, cwd=repo_root).returncode


if __name__ == "__main__":
    raise SystemExit(main())
