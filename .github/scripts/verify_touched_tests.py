#!/usr/bin/env python3
"""Run the tests a diff touched — the second half of this project's verify command (#1307).

The four validators say nothing about the test suite, so a certified review loop's fix round
could leave tests red and still report the verify gate green (observed three times on PR #1295).
This script closes that: it resolves the test files a diff touched and runs pytest on exactly
those, so a fix round that breaks a test it touched goes red.

Resolution, from the changed-file set:
  * every changed ``.py`` file that lives under a ``tests/`` directory, and
  * for every changed module directly under a mapped library root
    (``plugins/superheroes/lib/``, ``eval/lib/``), that root's ``tests/test_<module>*.py``.

Fail direction, by construction:
  * a changed mapped-root module with NO resolvable test file exits **non-zero** naming the
    module — a mapping miss is loud, never a silent no-op;
  * a diff that changed no code exits **0** and says so;
  * otherwise the exit status is pytest's own.

Stdlib only; runs under the repo's `/usr/bin/python3` (3.9) as well as CI's 3.12.
"""
from __future__ import annotations

import argparse
import glob
import os
import subprocess
import sys

# Mapped library roots: a changed module directly inside one of these resolves its test
# siblings under that root's `tests/` directory. Adding a root here is the only edit needed
# to extend the mapping.
LIB_ROOTS = (
    "plugins/superheroes/lib",
    "eval/lib",
)

# CLAUDE.md pins these: Apple's python caches bytecode outside the tree, so a same-size,
# same-second edit otherwise runs stale bytecode.
DEFAULT_PYTHON = "/usr/bin/python3"
PYCACHE_PREFIX = "/private/tmp/superheroes-pyc"
PYTEST_ARGS = ("-q", "-n", "auto", "-p", "no:cacheprovider")

BASE_REF_CANDIDATES = ("origin/main", "main")


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
        return sorted(set(_git_paths(repo_root, "diff", "--name-only", diff_range)))
    base_ref = resolve_base(repo_root, base)
    merge_base = _git(repo_root, "merge-base", base_ref, "HEAD").strip()
    paths = set(_git_paths(repo_root, "diff", "--name-only", merge_base))
    paths |= set(_git_paths(repo_root, "ls-files", "--others", "--exclude-standard"))
    return sorted(paths)


def _under_tests_tree(path):
    return "tests" in path.split("/")[:-1]


def mapped_module(path):
    """(root, module-name) when ``path`` is a module directly under a mapped library root."""
    if not path.endswith(".py") or _under_tests_tree(path):
        return None
    directory, name = os.path.split(path)
    if directory in LIB_ROOTS:
        return directory, name[: -len(".py")]
    return None


def resolve_targets(repo_root, paths):
    """(test_files, unresolved_modules, code_changed) for a changed-path set.

    ``test_files`` are existing, repo-relative and sorted; ``unresolved_modules`` are mapped-root
    modules whose test siblings do not exist; ``code_changed`` says whether the diff touched any
    ``.py`` file at all.
    """
    test_files = set()
    unresolved = []
    code_changed = False
    for path in paths:
        if not path.endswith(".py"):
            continue
        code_changed = True
        if _under_tests_tree(path):
            if os.path.exists(os.path.join(repo_root, path)):
                test_files.add(path)
            continue
        mapped = mapped_module(path)
        if mapped is None:
            continue
        root, module = mapped
        pattern = os.path.join(repo_root, root, "tests", "test_%s*.py" % module)
        matches = sorted(
            os.path.relpath(m, repo_root) for m in glob.glob(pattern) if os.path.isfile(m)
        )
        if matches:
            # Surviving siblings are run whether the module was edited or DELETED — a test
            # left behind by a deletion is exactly the one that should now be failing.
            test_files.update(matches)
        elif os.path.exists(os.path.join(repo_root, path)):
            unresolved.append(path)
        # else: the diff deleted the module and its tests together. Nothing is left to test,
        # so it carries no obligation — a retirement must never read as a mapping miss.
    return sorted(test_files), sorted(unresolved), code_changed


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

    test_files, unresolved, code_changed = resolve_targets(repo_root, paths)

    if unresolved:
        sys.stderr.write(
            "verify-touched-tests: no test file resolves for %d changed module(s):\n%s\n"
            "Add tests/test_<module>.py beside the module, or the touched tests cannot be run.\n"
            % (len(unresolved), "".join("  - %s\n" % m for m in unresolved))
        )
        return 1

    if not test_files:
        if not code_changed:
            sys.stdout.write("verify-touched-tests: no code changed; no tests to run.\n")
        else:
            sys.stdout.write(
                "verify-touched-tests: code changed but no touched test files resolved "
                "(nothing under a tests/ tree and no mapped-root module).\n")
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
