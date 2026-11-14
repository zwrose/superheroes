#!/usr/bin/env python3
"""Is a stack linear, and did a straightening keep every layer's files?

A stack is pull requests where each layer's base is the layer below's branch. A base branch with a
merge queue drops a stack whose layers carry merge commits. Before merging, the advisor rebases the
whole stack onto the main commit its bottom already contains; this module answers two questions:

`check` - is every layer linear? A stack is linear only when every layer's own commits were read
completely and none has two or more parents. An unreadable or incomplete read is never "linear".
It has a REST form (the pull requests' commit lists, for a cloud session) and a local form (a git
repository and refs).

`prove` - did the straightening keep every layer's files and leave no merge commit? It is proven only
when, for every layer bottom to top, the new head's tree equals the vetted head's tree, no merge
commit lies between the layer below's new head (the base, for the bottom) and the new head, the new
head descends from the layer below's new head (the base, for the bottom), and the base is an ancestor
of the vetted bottom. Only a proven result carries the dated re-pin lines and the one leased, atomic
push argv. The module prints that argv; it never runs a push.

When `prove` is given each layer's pull request number and body, it proves one thing more: no body carries a
`fixed-above #<PR> <commit>` line (the grammar of `leftover_accepting.FIXED_ABOVE_RE`) naming a layer of this stack
with a commit that is not an ancestor of (or equal to) that layer's new head. A straightening rewrites every commit,
so such a line would point at a commit the stack no longer holds; it refuses `fixed-above-stale` and prints the
replacement line. A line naming a pull request outside the stack refuses `fixed-above-unknown-layer`.

Every answer is JSON on stdout. Exit code 0 only when the result's `ok` is true."""
import argparse
import datetime
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import gh_pages  # noqa: E402

GH_TIMEOUT = 120
GIT_TIMEOUT = 60
# GitHub's pulls/{n}/commits returns at most 250 commits, so a list this long may be truncated.
PR_COMMITS_CAP = 250
MAX_DETAIL = 1000

REASON_BAD_ARGUMENT = "bad-argument"
REASON_STACK_NOT_LINEAR = "stack-not-linear"
REASON_LINEARITY_UNREADABLE = "linearity-unreadable"
REASON_TREE_CHANGED = "tree-changed"
REASON_MERGE_COMMIT_REMAINS = "merge-commit-remains"
REASON_NOT_ON_LAYER_BELOW = "not-on-layer-below"
REASON_BASE_NOT_CONTAINED = "base-not-contained"
REASON_HISTORY_SHALLOW = "history-shallow"
REASON_GIT_FAILED = "git-failed"
REASON_FIXED_ABOVE_STALE = "fixed-above-stale"
REASON_FIXED_ABOVE_UNKNOWN_LAYER = "fixed-above-unknown-layer"

_REPO_RE = re.compile(r"^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+\Z")
_OBJECT_ID_RE = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")
_REF_BAD_RE = re.compile(r"[\s\x00-\x1f\x7f]")
_BRANCH_BAD_RE = re.compile(r"[\s:~^?*\[\\\x00-\x1f\x7f]")


class _ParseError(Exception):
    pass


class _LinearParser(argparse.ArgumentParser):
    def error(self, message):
        raise _ParseError(message)

    def exit(self, status=0, message=None):
        raise _ParseError(message or "")

    def _print_message(self, message, file=None):
        pass


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _is_positive_finite(value):
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value > 0
    )


def _is_finite_number(value):
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _clip(text):
    text = text if isinstance(text, str) else str(text)
    if len(text) > MAX_DETAIL:
        return text[:MAX_DETAIL] + "..."
    return text


def _valid_ref(value):
    """A git ref this module will hand to git: a non-empty string that cannot read as an option and
    carries no whitespace or control character."""
    return (
        isinstance(value, str)
        and value != ""
        and not value.startswith("-")
        and _REF_BAD_RE.search(value) is None
    )


# ---------------------------------------------------------------------------------------------
# Result builders: one per verb.
# ---------------------------------------------------------------------------------------------

def _check_result(*, linear, reason, detail, layers):
    """The one `check` result builder. ok and linear are the same flag, true only for a complete
    read that found no merge commit."""
    return {
        "ok": linear is True,
        "linear": linear,
        "reason": reason,
        "detail": None if detail is None else _clip(detail),
        "layers": layers,
    }


def _check_bad_argument(detail):
    return _check_result(linear=None, reason=REASON_BAD_ARGUMENT, detail=detail, layers=[])


def _check_unreadable(detail, layers):
    return _check_result(linear=None, reason=REASON_LINEARITY_UNREADABLE, detail=detail,
                         layers=layers)


def _prove_result(*, proven, reason, detail, base, layers, repin, push, fixed_above=None):
    """The one `prove` result builder. ok and proven are the same flag; repin and push are set only
    by the caller that proved every layer. `fixedAbove` is present only when the bodies were checked."""
    result = {
        "ok": proven,
        "proven": proven,
        "reason": reason,
        "detail": None if detail is None else _clip(detail),
        "base": base,
        "layers": layers,
        "repin": repin,
        "push": push,
    }
    if fixed_above is not None:
        result["fixedAbove"] = fixed_above
    return result


def _prove_refused(reason, detail, base=None, layers=None):
    return _prove_result(proven=False, reason=reason, detail=detail, base=base,
                         layers=[] if layers is None else layers, repin=[], push=None)


# ---------------------------------------------------------------------------------------------
# The shared verdict of both check forms.
# ---------------------------------------------------------------------------------------------

def _verdict(layers, problems):
    """Decide linearity from a read of every layer: `layers` are the per-layer entries, `problems`
    the unreadable ones' details."""
    # axis: an unreadable layer wins over a merge commit - the answer is then linearity-unreadable
    if problems:
        return _check_unreadable("; ".join(problems), layers)

    named = ["layer %s: %s" % (entry["layer"], ", ".join(entry["mergeCommits"]))
             for entry in layers if entry["mergeCommits"]]
    # axis: any merge commit in any layer makes the stack not linear
    if named:
        return _check_result(linear=False, reason=REASON_STACK_NOT_LINEAR,
                             detail="merge commits: " + "; ".join(named), layers=layers)

    return _check_result(linear=True, reason=None, detail=None, layers=layers)


# ---------------------------------------------------------------------------------------------
# check, REST form.
# ---------------------------------------------------------------------------------------------

def _validate_rest(repo, prs, timeout, deadline_at):
    """Return None when arguments are good, or the refusal dict to return."""
    # axis: repo is not an owner/name string
    if not isinstance(repo, str) or not _REPO_RE.match(repo):
        return _check_bad_argument("repo must be owner/name")

    # axis: prs is not a non-empty list
    if not isinstance(prs, list) or not prs:
        return _check_bad_argument("prs must be a non-empty list of pull request numbers")

    # axis: a pr is not a positive int (bool is not an int here)
    if not all(_is_int(pr) and pr >= 1 for pr in prs):
        return _check_bad_argument("every pr must be a positive integer")

    # axis: the same pr is listed twice
    if len(set(prs)) != len(prs):
        return _check_bad_argument("prs must not repeat a pull request")

    # axis: timeout is not a positive finite number
    if not _is_positive_finite(timeout):
        return _check_bad_argument("timeout must be a positive number of seconds")

    # axis: deadline_at is neither None nor a finite number
    if deadline_at is not None and not _is_finite_number(deadline_at):
        return _check_bad_argument("deadline_at must be None or a finite number")

    return None


def _scan_rows(rows):
    """Return the merge-commit shas in one layer's commit rows, or None when any row is not a
    readable commit (a dict with a string sha and a parents list of dicts with string shas)."""
    merges = []
    for row in rows:
        # axis: a row that is not an object makes the layer unreadable
        if not isinstance(row, dict):
            return None
        sha = row.get("sha")
        # axis: a row whose sha is not a non-empty string makes the layer unreadable
        if not isinstance(sha, str) or not sha:
            return None
        parents = row.get("parents")
        # axis: a row whose parents is not a list makes the layer unreadable
        if not isinstance(parents, list):
            return None
        # axis: a parent that is not an object with a string sha makes the layer unreadable
        if not all(isinstance(p, dict) and isinstance(p.get("sha"), str) for p in parents):
            return None
        # axis: REST merge-commit decision - two or more parents is a merge commit
        if len(parents) >= 2:
            merges.append(sha)
    return merges


def check_rest(*, repo, prs, timeout=GH_TIMEOUT, deadline_at=None, run=None, monotonic=None):
    """Read every layer's commit list through REST and answer whether the stack is linear. Argument-
    side and GitHub-side failures return a refusal and raise nothing."""
    run = subprocess.run if run is None else run
    monotonic = time.monotonic if monotonic is None else monotonic

    refusal = _validate_rest(repo, prs, timeout, deadline_at)
    if refusal is not None:
        return refusal

    # axis: gh is not on PATH
    if not shutil.which("gh"):
        return _check_unreadable(
            "gh not on PATH",
            [{"layer": pr, "commits": None, "mergeCommits": []} for pr in prs])

    why = []

    def fetch(endpoint):
        left = timeout if deadline_at is None else min(timeout, deadline_at - monotonic())
        # axis: no time left before the deadline - no call is made and the read fails
        if left <= 0:
            why.append("the deadline passed before the read finished")
            return None
        try:
            proc = run(["gh", "api", endpoint], capture_output=True, text=True, timeout=left)
        except (OSError, subprocess.TimeoutExpired) as exc:
            # axis: run raises OSError or TimeoutExpired - a failed read, never raised
            why.append("gh call failed: %s" % (exc or type(exc).__name__))
            return None
        # axis: gh exits non-zero - a failed read
        if proc.returncode != 0:
            why.append("gh api exited %s" % proc.returncode)
            return None
        return proc.stdout

    layers = []
    problems = []
    for pr in prs:
        del why[:]
        rows = gh_pages.read(fetch, "repos/%s/pulls/%d/commits" % (repo, pr))
        entry = {"layer": pr, "commits": None, "mergeCommits": []}
        layers.append(entry)
        # axis: a list that could not be read page by page is unreadable, never a partial list
        if rows is None:
            problems.append("layer %d: commit list unreadable%s" % (
                pr, " (%s)" % why[-1] if why else ""))
            continue
        # axis: a list at GitHub's 250-commit cap may be truncated - unreadable
        if len(rows) >= PR_COMMITS_CAP:
            problems.append("layer %d: %d commits is at GitHub's %d-commit cap, so the list may be "
                            "truncated" % (pr, len(rows), PR_COMMITS_CAP))
            continue
        merges = _scan_rows(rows)
        # axis: a row that is not a readable commit makes the whole layer unreadable
        if merges is None:
            problems.append("layer %d: a commit row is not readable" % pr)
            continue
        entry["commits"] = len(rows)
        entry["mergeCommits"] = merges

    return _verdict(layers, problems)


# ---------------------------------------------------------------------------------------------
# git helpers, shared by check_local and prove.
# ---------------------------------------------------------------------------------------------

def _git(run, repo_root, *args):
    """Run one git command in repo_root. Return (proc, None) when it ran, or (None, detail) when the
    call could not run (OSError, timeout)."""
    try:
        proc = run(["git"] + list(args), capture_output=True, text=True, timeout=GIT_TIMEOUT,
                   cwd=repo_root)
    except (OSError, subprocess.TimeoutExpired) as exc:
        # axis: run raises OSError or TimeoutExpired - a failed git call, never raised
        return None, "git %s could not run: %s" % (args[0], exc or type(exc).__name__)
    return proc, None


def _proc_text(proc):
    parts = [(proc.stdout or "").strip(), (proc.stderr or "").strip()]
    return "\n".join(part for part in parts if part)


def _shallow(run, repo_root):
    """Return (True|False, None) from `git rev-parse --is-shallow-repository`, or (None, detail)."""
    proc, problem = _git(run, repo_root, "rev-parse", "--is-shallow-repository")
    if proc is None:
        return None, problem
    out = (proc.stdout or "").strip()
    # axis: the shallow probe exits non-zero or prints neither true nor false - unknown, not "full"
    if proc.returncode != 0 or out not in ("true", "false"):
        return None, "git rev-parse --is-shallow-repository failed: %s" % (
            _proc_text(proc) or "exit %s" % proc.returncode)
    return out == "true", None


def _rev_parse(run, repo_root, ref, kind, quiet):
    """Resolve `ref` to a full object id of `kind` (commit or tree). Return (sha, None) or
    (None, detail)."""
    args = ["rev-parse", "--verify"] + (["--quiet"] if quiet else []) + ["%s^{%s}" % (ref, kind)]
    proc, problem = _git(run, repo_root, *args)
    if proc is None:
        return None, problem
    out = (proc.stdout or "").strip()
    # axis: rev-parse exits non-zero or prints something that is not a full object id
    if proc.returncode != 0 or not _OBJECT_ID_RE.match(out):
        return None, "%s does not resolve to a %s%s" % (
            ref, kind, ": " + _proc_text(proc) if _proc_text(proc) else "")
    return out, None


def _is_ancestor(run, repo_root, older, newer):
    """Return (True, None) when older is an ancestor of newer, (False, None) when it is not, or
    (None, detail) when git could not tell."""
    proc, problem = _git(run, repo_root, "merge-base", "--is-ancestor", older, newer)
    if proc is None:
        return None, problem
    if proc.returncode == 0:
        return True, None
    # axis: exit 1 is the only "not an ancestor" - every other non-zero exit is a git failure
    if proc.returncode == 1:
        return False, None
    return None, "git merge-base --is-ancestor %s %s failed: %s" % (
        older, newer, _proc_text(proc) or "exit %s" % proc.returncode)


# ---------------------------------------------------------------------------------------------
# check, local form.
# ---------------------------------------------------------------------------------------------

def _validate_local(repo_root, base, layers):
    # axis: repo_root is not a non-empty string
    if not isinstance(repo_root, str) or not repo_root:
        return _check_bad_argument("repo_root must be a non-empty path")

    # axis: base is not a usable git ref
    if not _valid_ref(base):
        return _check_bad_argument("base must be a git ref")

    # axis: layers is not a non-empty list
    if not isinstance(layers, list) or not layers:
        return _check_bad_argument("layers must be a non-empty list of git refs")

    # axis: a layer is not a usable git ref
    if not all(_valid_ref(layer) for layer in layers):
        return _check_bad_argument("every layer must be a git ref")

    return None


def check_local(*, repo_root, base, layers, run=None):
    """Read every layer's own commits from a local repository and answer whether the stack is
    linear."""
    run = subprocess.run if run is None else run

    refusal = _validate_local(repo_root, base, layers)
    if refusal is not None:
        return refusal

    blank = [{"layer": layer, "commits": None, "mergeCommits": []} for layer in layers]

    shallow, problem = _shallow(run, repo_root)
    # axis: the shallow probe could not be answered - unreadable
    if shallow is None:
        return _check_unreadable(problem, blank)
    # axis: a shallow repository shows boundary commits as parentless roots, so a hidden merge
    # would read linear - unreadable
    if shallow:
        return _check_unreadable(REASON_HISTORY_SHALLOW, blank)

    resolved = []
    for ref in [base] + list(layers):
        sha, problem = _rev_parse(run, repo_root, ref, "commit", True)
        # axis: a ref that does not resolve - unreadable
        if sha is None:
            return _check_unreadable(problem, blank)
        resolved.append(sha)

    entries = []
    problems = []
    for index, ref in enumerate(layers):
        prev = resolved[index]
        entry = {"layer": ref, "commits": None, "mergeCommits": []}
        entries.append(entry)
        proc, problem = _git(run, repo_root, "rev-list", "--parents",
                             "%s..%s" % (prev, resolved[index + 1]))
        # axis: rev-list could not run - the layer is unreadable
        if proc is None:
            problems.append("layer %s: %s" % (ref, problem))
            continue
        # axis: rev-list exits non-zero - the layer is unreadable
        if proc.returncode != 0:
            problems.append("layer %s: git rev-list failed: %s" % (
                ref, _proc_text(proc) or "exit %s" % proc.returncode))
            continue
        lines = [line.split() for line in (proc.stdout or "").splitlines() if line.strip()]
        entry["commits"] = len(lines)
        # axis: local merge-commit decision - a line of sha plus two or more parents is a merge
        entry["mergeCommits"] = [tokens[0] for tokens in lines if len(tokens) >= 3]

    return _verdict(entries, problems)


# ---------------------------------------------------------------------------------------------
# prove.
# ---------------------------------------------------------------------------------------------

def _validate_prove(repo_root, base, layers, remote, today, bodies):
    # axis: repo_root is not a non-empty string
    if not isinstance(repo_root, str) or not repo_root:
        return _prove_refused(REASON_BAD_ARGUMENT, "repo_root must be a non-empty path")

    # axis: base is not a usable git ref
    if not _valid_ref(base):
        return _prove_refused(REASON_BAD_ARGUMENT, "base must be a git ref")

    # axis: layers is not a non-empty list
    if not isinstance(layers, list) or not layers:
        return _prove_refused(REASON_BAD_ARGUMENT,
                              "layers must be a non-empty list of (branch, vetted, new, pr)")

    # axis: a layer is not a (branch, vetted, new) triple or a (branch, vetted, new, pr) quadruple
    if not all(isinstance(layer, (tuple, list)) and len(layer) in (3, 4) for layer in layers):
        return _prove_refused(REASON_BAD_ARGUMENT,
                              "every layer must be a (branch, vetted, new) triple or a "
                              "(branch, vetted, new, pr) quadruple")

    branches = [layer[0] for layer in layers]
    # axis: a branch is not a plain branch name (no whitespace, no colon, no leading dash)
    if not all(isinstance(b, str) and b != "" and not b.startswith("-")
               and _BRANCH_BAD_RE.search(b) is None for b in branches):
        return _prove_refused(REASON_BAD_ARGUMENT, "every branch must be a plain branch name")

    # axis: the same branch is listed twice
    if len(set(branches)) != len(branches):
        return _prove_refused(REASON_BAD_ARGUMENT, "branches must not repeat")

    # axis: a vetted or new head is not a usable git ref
    if not all(_valid_ref(layer[1]) and _valid_ref(layer[2]) for layer in layers):
        return _prove_refused(REASON_BAD_ARGUMENT, "every vetted and new head must be a git ref")

    prs = [layer[3] for layer in layers if len(layer) == 4]
    # axis: a layer's pr is not a positive int (bool is not an int here)
    if not all(_is_int(pr) and pr >= 1 for pr in prs):
        return _prove_refused(REASON_BAD_ARGUMENT, "every layer's pr must be a positive integer")

    # axis: the same pr is listed twice
    if len(set(prs)) != len(prs):
        return _prove_refused(REASON_BAD_ARGUMENT, "prs must not repeat a pull request")

    if bodies is not None:
        # axis: bodies are given but a layer is a triple, so it names no pull request
        if len(prs) != len(layers):
            return _prove_refused(REASON_BAD_ARGUMENT,
                                  "bodies are given, so every layer must be a "
                                  "(branch, vetted, new, pr) quadruple")

        # axis: bodies is not a dict
        if not isinstance(bodies, dict):
            return _prove_refused(REASON_BAD_ARGUMENT,
                                  "bodies must be a dict of pull request number to body text")

        # axis: bodies are given but a layer's pull request has no string body
        missing = [pr for pr in prs if not isinstance(bodies.get(pr), str)]
        if missing:
            return _prove_refused(REASON_BAD_ARGUMENT,
                                  "no body text for pull request %s" % ", ".join(
                                      str(pr) for pr in missing))

    # axis: remote is not a usable remote name
    if not _valid_ref(remote):
        return _prove_refused(REASON_BAD_ARGUMENT, "remote must be a remote name")

    # axis: today is neither None nor a date
    if today is not None and not isinstance(today, datetime.date):
        return _prove_refused(REASON_BAD_ARGUMENT, "today must be None or a date")

    return None


def _merges_between(run, repo_root, older, newer):
    """Return (merge shas, None) for `git rev-list --merges older..newer`, or (None, detail)."""
    proc, problem = _git(run, repo_root, "rev-list", "--merges", "%s..%s" % (older, newer))
    if proc is None:
        return None, problem
    # axis: rev-list exits non-zero - git failed, the range is not known to be merge-free
    if proc.returncode != 0:
        return None, "git rev-list --merges %s..%s failed: %s" % (
            older, newer, _proc_text(proc) or "exit %s" % proc.returncode)
    return [line.strip() for line in (proc.stdout or "").splitlines() if line.strip()], None


def _check_fixed_above(run, repo_root, base_sha, entries, prs, bodies):
    """Return (refusal, None), or (None, []) when no layer's body carries a stale fixed-above line.
    Every `fixed-above #<PR> <commit>` line (`leftover_accepting.FIXED_ABOVE_RE`) in every body, in
    layer order then body order, must name a layer of this stack with a commit that is an ancestor of
    (or equal to) that layer's new head. All stale lines are collected before the refusal."""
    # lazy import: stack_merge imports this module, and the merge path must not load
    # leftover_accepting's dependencies
    from leftover_accepting import FIXED_ABOVE_RE

    new_of = {pr: entry["new"] for pr, entry in zip(prs, entries)}
    stale = []
    for pr in prs:
        for found in FIXED_ABOVE_RE.finditer(bodies[pr]):
            line, named, commit = found.group(0), int(found.group(1)), found.group(2)
            # axis: a line naming a pull request that is not a layer of this stack - fixed-above-unknown-layer
            if named not in new_of:
                return _prove_result(
                    proven=False, reason=REASON_FIXED_ABOVE_UNKNOWN_LAYER,
                    detail="PR %d line \"%s\" names PR %d, which is not a layer of this stack" % (
                        pr, line, named),
                    base=base_sha, layers=entries, repin=[], push=None, fixed_above=[]), None

            proc, problem = _git(run, repo_root, "rev-parse", "--verify", "--quiet",
                                 commit + "^{commit}")
            # axis: the commit could not be looked up at all - git-failed, never current
            if proc is None:
                return _prove_refused(REASON_GIT_FAILED, "PR %d line \"%s\": %s" % (pr, line, problem),
                                      base=base_sha, layers=entries), None
            commit_sha = (proc.stdout or "").strip()
            resolves = proc.returncode == 0 and _OBJECT_ID_RE.match(commit_sha) is not None
            # axis: a commit that does not resolve counts as stale
            if not resolves:
                stale.append((pr, line, named, commit))
                continue

            current, problem = _is_ancestor(run, repo_root, commit_sha, new_of[named])
            # axis: git could not tell whether the commit is an ancestor of the new head - git-failed
            if current is None:
                return _prove_refused(REASON_GIT_FAILED, "PR %d line \"%s\": %s" % (pr, line, problem),
                                      base=base_sha, layers=entries), None
            # axis: the commit is not an ancestor of (nor equal to) the new head - stale
            if not current:
                stale.append((pr, line, named, commit))

    # axis: any stale line refuses the straightening, with every stale line named
    if stale:
        return _prove_result(
            proven=False, reason=REASON_FIXED_ABOVE_STALE,
            detail="stale fixed-above lines: " + "; ".join(
                "PR %d line \"%s\"" % (pr, line) for pr, line, _named, _commit in stale),
            base=base_sha, layers=entries, repin=[], push=None,
            fixed_above=[{"pr": pr, "line": line, "names": named, "commit": commit,
                          "replacement": "fixed-above #%d %s" % (named, new_of[named])}
                         for pr, line, named, commit in stale]), None
    return None, []


def prove(*, repo_root, base, layers, remote="origin", today=None, run=None, bodies=None):
    """Prove a straightening kept every layer's files and left no merge commit. `layers` is a list of
    (branch, vetted, new) triples, or (branch, vetted, new, pr) quadruples, bottom to top. When
    `bodies` (pull request number -> body text) is given, every layer must be a quadruple with a body,
    and no body may carry a stale `fixed-above` line. Only a proven result carries repin and push."""
    run = subprocess.run if run is None else run

    refusal = _validate_prove(repo_root, base, layers, remote, today, bodies)
    if refusal is not None:
        return refusal

    shallow, problem = _shallow(run, repo_root)
    # axis: the shallow probe could not be answered - git-failed
    if shallow is None:
        return _prove_refused(REASON_GIT_FAILED, problem)
    # axis: a shallow repository cannot prove a rewrite left no merge commit - history-shallow
    if shallow:
        return _prove_refused(REASON_HISTORY_SHALLOW,
                              "the repository is shallow, so merge commits can hide behind its "
                              "boundary commits")

    base_sha, problem = _rev_parse(run, repo_root, base, "commit", True)
    # axis: base does not resolve - git-failed
    if base_sha is None:
        return _prove_refused(REASON_GIT_FAILED, "base: " + problem)

    resolved = []
    for layer in layers:
        branch, vetted_ref, new_ref = layer[0], layer[1], layer[2]
        vetted_sha, problem = _rev_parse(run, repo_root, vetted_ref, "commit", True)
        # axis: a vetted head does not resolve - git-failed
        if vetted_sha is None:
            return _prove_refused(REASON_GIT_FAILED, "layer %s vetted head: %s" % (branch, problem),
                                  base=base_sha)
        new_sha, problem = _rev_parse(run, repo_root, new_ref, "commit", True)
        # axis: a new head does not resolve - git-failed
        if new_sha is None:
            return _prove_refused(REASON_GIT_FAILED, "layer %s new head: %s" % (branch, problem),
                                  base=base_sha)
        resolved.append((branch, vetted_sha, new_sha))

    contained, problem = _is_ancestor(run, repo_root, base_sha, resolved[0][1])
    # axis: git could not tell whether the base is an ancestor of the vetted bottom - git-failed
    if contained is None:
        return _prove_refused(REASON_GIT_FAILED, problem, base=base_sha)
    # axis: the base is not an ancestor of the vetted bottom - base-not-contained
    if not contained:
        return _prove_refused(REASON_BASE_NOT_CONTAINED,
                              "base %s is not an ancestor of the vetted bottom %s (layer %s)" % (
                                  base_sha, resolved[0][1], resolved[0][0]),
                              base=base_sha)

    entries = []
    prev = base_sha
    for branch, vetted_sha, new_sha in resolved:
        entry = {"branch": branch, "vetted": vetted_sha, "new": new_sha, "tree": None,
                 "treeEqual": None, "mergeCommits": None, "onLayerBelow": None}
        entries.append(entry)

        new_tree, problem = _rev_parse(run, repo_root, new_sha, "tree", False)
        # axis: the new head's tree cannot be read - git-failed
        if new_tree is None:
            return _prove_refused(REASON_GIT_FAILED, "layer %s new tree: %s" % (branch, problem),
                                  base=base_sha, layers=entries)
        vetted_tree, problem = _rev_parse(run, repo_root, vetted_sha, "tree", False)
        # axis: the vetted head's tree cannot be read - git-failed
        if vetted_tree is None:
            return _prove_refused(REASON_GIT_FAILED, "layer %s vetted tree: %s" % (branch, problem),
                                  base=base_sha, layers=entries)
        entry["tree"] = new_tree
        entry["treeEqual"] = new_tree == vetted_tree
        # axis: the new head's tree differs from the vetted head's tree - tree-changed
        if not entry["treeEqual"]:
            return _prove_refused(REASON_TREE_CHANGED,
                                  "layer %s: new head %s has tree %s but the vetted head %s has "
                                  "tree %s" % (branch, new_sha, new_tree, vetted_sha, vetted_tree),
                                  base=base_sha, layers=entries)

        merges, problem = _merges_between(run, repo_root, prev, new_sha)
        # axis: the merge scan failed - git-failed
        if merges is None:
            return _prove_refused(REASON_GIT_FAILED, "layer %s: %s" % (branch, problem),
                                  base=base_sha, layers=entries)
        entry["mergeCommits"] = merges
        # axis: a merge commit lies between the layer below and the new head - merge-commit-remains
        if merges:
            return _prove_refused(REASON_MERGE_COMMIT_REMAINS,
                                  "layer %s: merge commits remain: %s" % (branch, ", ".join(merges)),
                                  base=base_sha, layers=entries)

        below, problem = _is_ancestor(run, repo_root, prev, new_sha)
        # axis: git could not tell whether the new head descends from the layer below - git-failed
        if below is None:
            return _prove_refused(REASON_GIT_FAILED, "layer %s: %s" % (branch, problem),
                                  base=base_sha, layers=entries)
        entry["onLayerBelow"] = below
        # axis: the new head does not descend from the layer below's new head - not-on-layer-below
        if not below:
            return _prove_refused(REASON_NOT_ON_LAYER_BELOW,
                                  "layer %s: new head %s does not descend from %s" % (
                                      branch, new_sha, prev),
                                  base=base_sha, layers=entries)
        prev = new_sha

    fixed_above = None
    if bodies is not None:
        refusal, fixed_above = _check_fixed_above(run, repo_root, base_sha, entries,
                                                  [layer[3] for layer in layers], bodies)
        if refusal is not None:
            return refusal

    if today is None:
        today = datetime.datetime.now(datetime.timezone.utc).date()
    elif isinstance(today, datetime.datetime):
        today = today.date()
    stamp = today.isoformat()

    repin = [
        "Re-pinned %s (stack straightened for a merge-queue base): %s %s -> %s, tree %s equal." % (
            stamp, entry["branch"], entry["vetted"], entry["new"], entry["tree"])
        for entry in entries
    ]
    push = (
        ["git", "push", "--atomic", remote]
        + ["--force-with-lease=refs/heads/%s:%s" % (entry["branch"], entry["vetted"])
           for entry in entries]
        + ["%s:refs/heads/%s" % (entry["new"], entry["branch"]) for entry in entries]
    )
    return _prove_result(proven=True, reason=None,
                         detail="%d layers keep their trees and carry no merge commit" % len(entries),
                         base=base_sha, layers=entries, repin=repin, push=push,
                         fixed_above=fixed_above)


# ---------------------------------------------------------------------------------------------
# Command line.
# ---------------------------------------------------------------------------------------------

def _build_parser():
    parser = _LinearParser(prog="stack_linear", allow_abbrev=False)
    subparsers = parser.add_subparsers(dest="verb")
    check_parser = subparsers.add_parser("check", allow_abbrev=False)
    check_parser.add_argument("--repo")
    check_parser.add_argument("--pr", type=int, action="append")
    check_parser.add_argument("--repo-root")
    check_parser.add_argument("--base")
    check_parser.add_argument("--layer", action="append")
    prove_parser = subparsers.add_parser("prove", allow_abbrev=False)
    prove_parser.add_argument("--repo-root", required=True)
    prove_parser.add_argument("--base", required=True)
    prove_parser.add_argument("--layer", nargs=4, action="append", required=True)
    prove_parser.add_argument("--pr-body", nargs=2, action="append")
    prove_parser.add_argument("--remote", default="origin")
    return parser


_PR_TEXT_RE = re.compile(r"[1-9][0-9]*\Z")


def _prove_cli_inputs(args):
    """Return (layers, bodies, None) from the parsed `prove` arguments, or (None, None, refusal): each
    --layer's pr as an int, and each --pr-body file read as UTF-8 text."""
    layers = []
    for branch, vetted, new, pr in args.layer:
        # axis: a --layer pr is not a positive integer
        if not _PR_TEXT_RE.match(pr):
            return None, None, _prove_refused(REASON_BAD_ARGUMENT,
                                              "--layer pr must be a positive integer")
        layers.append((branch, vetted, new, int(pr)))

    bodies = {}
    for pr, path in args.pr_body or []:
        # axis: a --pr-body pr is not a positive integer
        if not _PR_TEXT_RE.match(pr):
            return None, None, _prove_refused(REASON_BAD_ARGUMENT,
                                              "--pr-body pr must be a positive integer")
        # axis: the same pr is given two --pr-body files
        if int(pr) in bodies:
            return None, None, _prove_refused(REASON_BAD_ARGUMENT,
                                              "--pr-body is given twice for PR %s" % pr)
        try:
            with open(path, "rb") as handle:
                bodies[int(pr)] = handle.read().decode("utf-8")
        except (OSError, ValueError) as exc:
            # axis: a --pr-body file that cannot be read, or is not UTF-8, is never read as empty
            return None, None, _prove_refused(
                REASON_BAD_ARGUMENT,
                "--pr-body %s file cannot be read as UTF-8 text: %s" % (pr, type(exc).__name__))

    for layer in layers:
        # axis: every layer's PR needs its own --pr-body, so no body is guessed as empty
        if layer[3] not in bodies:
            return None, None, _prove_refused(
                REASON_BAD_ARGUMENT,
                "--pr-body <pr> <file> is required for PR %d" % layer[3])
    return layers, bodies, None


def main(argv=None, *, run=None, monotonic=None, today=None):
    if argv is None:
        argv = sys.argv[1:]
    try:
        args = _build_parser().parse_args(argv)
        if args.verb not in ("check", "prove"):
            raise _ParseError("unknown or missing verb")
    except (_ParseError, SystemExit):
        # axis: the parse boundary (malformed CLI call returns bad-argument instead of argparse exit)
        if argv and argv[0] == "prove":
            result = _prove_refused(REASON_BAD_ARGUMENT, "invalid command-line arguments")
        else:
            result = _check_bad_argument("invalid command-line arguments")
        sys.stdout.write(json.dumps(result) + "\n")
        return 1

    if args.verb == "prove":
        layers, bodies, refusal = _prove_cli_inputs(args)
        if refusal is not None:
            result = refusal
        else:
            result = prove(repo_root=args.repo_root, base=args.base, layers=layers,
                           remote=args.remote, today=today, run=run, bodies=bodies)
    else:
        rest_form = args.repo is not None or args.pr is not None
        local_form = (args.repo_root is not None or args.base is not None
                      or args.layer is not None)
        # axis: exactly one check form - REST (--repo/--pr) or local (--repo-root/--base/--layer)
        if rest_form == local_form:
            result = _check_bad_argument("give exactly one form: --repo with --pr, or "
                                         "--repo-root with --base and --layer")
        elif rest_form:
            result = check_rest(repo=args.repo, prs=args.pr, run=run, monotonic=monotonic)
        else:
            result = check_local(repo_root=args.repo_root, base=args.base, layers=args.layer,
                                 run=run)
    sys.stdout.write(json.dumps(result) + "\n")
    # axis: exit 0 only when the result is ok
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
