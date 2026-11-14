#!/usr/bin/env python3
"""Does a base branch have a merge queue? Answered fail-closed.

A merge queue can be set by a repository ruleset (a `merge_queue` row in the branch's rules)
or by classic branch protection (visible only through GraphQL `repository.mergeQueue`).
A cloud session's proxy refuses GraphQL, so the answer cannot rest on either read alone.

The invariant: a branch reads as HAVING a queue unless both reads succeed and both say there
is none. A ruleset `merge_queue` row, a non-null GraphQL `mergeQueue`, or any failed or
unfinished read answers `queue: true`. Only two successful "no queue" reads answer
`queue: false`. The rules are read page by page by number (`gh_pages.read`), never with gh's
paginate flag, whose link URLs the cloud proxy refuses."""
import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.parse

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import gh_pages  # noqa: E402

GH_TIMEOUT = 120
MAX_DETAIL = 500

REASON_BAD_ARGUMENT = "bad-argument"

SOURCE_RULES = "rules"
SOURCE_GRAPHQL = "graphql"
SOURCE_NONE = "none"
SOURCE_READ_FAILED = "read-failed"

READ_OK = "ok"
READ_FAILED = "failed"
READ_SKIPPED = "skipped"

QUERY = ("query($owner:String!,$name:String!,$branch:String!)"
         "{repository(owner:$owner,name:$name){mergeQueue(branch:$branch){id}}}")

_REPO_RE = re.compile(r"^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+\Z")
_BAD_BRANCH_CHAR_RE = re.compile(r"[\s\x00-\x1f\x7f-\x9f]")

# The state a single read ends in.
_QUEUE = "queue"
_NO_QUEUE = "none"
_FAILED = "failed"


class _ParseError(Exception):
    pass


class _MergeQueueParser(argparse.ArgumentParser):
    def error(self, message):
        raise _ParseError(message)

    def exit(self, status=0, message=None):
        raise _ParseError(message or "")

    def _print_message(self, message, file=None):
        pass


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


def _result(repo, branch, *, ok=True, queue=None, source=None, method=None, reads=None,
            reason=None, detail=None):
    """The one result builder. Every key is always present; a key with no value is None."""
    return {
        "ok": ok,
        "queue": queue,
        "source": source,
        "method": method,
        "reads": reads,
        "reason": reason,
        "detail": None if detail is None else _clip(detail),
        "repo": repo,
        "branch": branch,
    }


def _bad_argument(detail):
    return _result(None, None, ok=False, reason=REASON_BAD_ARGUMENT, detail=detail)


def _validate(repo, branch, timeout, deadline_at):
    """Return None when arguments are good, or the refusal dict to return."""
    # axis: repo is not an owner/name string
    if not isinstance(repo, str) or not _REPO_RE.match(repo):
        return _bad_argument("repo must be owner/name")

    # axis: branch is not a non-empty string without whitespace or control characters
    if (not isinstance(branch, str) or not branch
            or _BAD_BRANCH_CHAR_RE.search(branch)):
        return _bad_argument("branch must be a non-empty string without whitespace or "
                             "control characters")

    # axis: timeout is not a positive finite number
    if not _is_positive_finite(timeout):
        return _bad_argument("timeout must be a positive number of seconds")

    # axis: deadline_at is neither None nor a finite number
    if deadline_at is not None and not _is_finite_number(deadline_at):
        return _bad_argument("deadline_at must be None or a finite number")

    return None


def _proc_text(proc):
    parts = [(proc.stdout or "").strip(), (proc.stderr or "").strip()]
    return "\n".join(part for part in parts if part)


def _load_object(text):
    """Return the parsed JSON object in text, or None when it is not one."""
    try:
        value = json.loads(text or "")
    except (json.JSONDecodeError, TypeError):
        return None
    return value if isinstance(value, dict) else None


class _Gh:
    """The gh calls of one `read`: one timeout, one optional deadline, and the reason the
    last call failed."""

    def __init__(self, run, monotonic, timeout, deadline_at):
        self.run = run
        self.monotonic = monotonic
        self.timeout = timeout
        self.deadline_at = deadline_at
        self.problem = None

    def call(self, argv):
        """Return the finished process when gh exited 0, else None with `problem` set."""
        self.problem = None
        call_timeout = self.timeout
        if self.deadline_at is not None:
            left = self.deadline_at - self.monotonic()
            # axis: the deadline has passed — the call is not made and counts as a failed read
            if left <= 0:
                self.problem = "the time budget ran out before the gh call was made"
                return None
            # axis: each call's timeout is capped by the time left to the deadline
            call_timeout = min(call_timeout, left)
        try:
            proc = self.run(argv, capture_output=True, text=True, timeout=call_timeout)
        except (OSError, subprocess.TimeoutExpired) as exc:
            # axis: run raises OSError or TimeoutExpired — a failed read
            self.problem = "gh call failed: %s" % (exc or type(exc).__name__)
            return None
        # axis: gh exits non-zero (a refused or failed call, the cloud proxy's GraphQL refusal included)
        if proc.returncode != 0:
            self.problem = "gh exited %s: %s" % (proc.returncode,
                                                 _proc_text(proc) or "gh api failed")
            return None
        return proc


def _read_rules(gh, owner, name, branch):
    """Read every page of the branch's rules. Return (state, method, detail)."""
    # axis: the branch is percent-quoted into the rules path, slashes kept
    path = "repos/%s/%s/rules/branches/%s" % (owner, name, urllib.parse.quote(branch, safe="/"))

    def _fetch(endpoint):
        proc = gh.call(["gh", "api", endpoint])
        return None if proc is None else (proc.stdout or "")

    rows = gh_pages.read(_fetch, path)
    # axis: a rules page that cannot be read, or is not a JSON list, fails the whole rules read
    if rows is None:
        return _FAILED, None, gh.problem or "rules response was not a JSON list"

    for row in rows:
        # axis: a rules row that is not an object with a string type fails the rules read
        if not isinstance(row, dict) or not isinstance(row.get("type"), str):
            return _FAILED, None, "a rules row is not an object with a string type"

    for row in rows:
        # axis: a rules row of type merge_queue means the branch has a queue
        if row["type"] == "merge_queue":
            parameters = row.get("parameters")
            method = parameters.get("merge_method") if isinstance(parameters, dict) else None
            return _QUEUE, method.lower() if isinstance(method, str) else None, None
    return _NO_QUEUE, None, None


def _read_graphql(gh, owner, name, branch):
    """Ask GraphQL for the branch's merge queue. Return (state, detail)."""
    argv = ["gh", "api", "graphql", "-f", "query=" + QUERY, "-f", "owner=" + owner,
            "-f", "name=" + name, "-f", "branch=" + branch]
    proc = gh.call(argv)
    if proc is None:
        return _FAILED, gh.problem

    body = _load_object(proc.stdout)
    # axis: GraphQL stdout is not a JSON object
    if body is None:
        return _FAILED, "graphql response is not a JSON object"

    # axis: GraphQL carries a non-empty errors key
    if body.get("errors"):
        return _FAILED, "graphql response carries errors: %s" % (body.get("errors"),)

    data = body.get("data")
    repository = data.get("repository") if isinstance(data, dict) else None
    # axis: data.repository is missing, null or not an object
    if not isinstance(repository, dict):
        return _FAILED, "graphql response has no data.repository object"

    # axis: the mergeQueue key is absent from the repository object
    if "mergeQueue" not in repository:
        return _FAILED, "graphql repository carries no mergeQueue key"

    merge_queue = repository["mergeQueue"]
    # axis: a null mergeQueue is a successful "no queue" read
    if merge_queue is None:
        return _NO_QUEUE, None
    # axis: a non-null mergeQueue object means the branch has a queue
    if isinstance(merge_queue, dict):
        return _QUEUE, None
    # axis: a mergeQueue that is neither null nor an object is unreadable
    return _FAILED, "graphql mergeQueue is neither null nor an object"


def _failed_details(rules_detail, graphql_detail):
    parts = []
    if rules_detail is not None:
        parts.append("rules read failed: %s" % rules_detail)
    if graphql_detail is not None:
        parts.append("graphql read failed: %s" % graphql_detail)
    return "; ".join(parts) if parts else None


def read(*, repo, branch, timeout=GH_TIMEOUT, deadline_at=None, run=None, monotonic=None):
    """Return the result dict for `branch` of `repo`: does it have a merge queue?
    Failures return `queue: true` with `source: "read-failed"` and raise nothing."""
    run = subprocess.run if run is None else run
    monotonic = time.monotonic if monotonic is None else monotonic

    refusal = _validate(repo, branch, timeout, deadline_at)
    if refusal is not None:
        return refusal

    # axis: gh is not on PATH — no read can be made, so the branch reads as having a queue
    if not shutil.which("gh"):
        return _result(repo, branch, queue=True, source=SOURCE_READ_FAILED,
                       reads={"rules": READ_FAILED, "graphql": READ_FAILED},
                       detail="gh not on PATH")

    owner, name = repo.split("/")
    gh = _Gh(run, monotonic, timeout, deadline_at)

    rules_state, method, rules_detail = _read_rules(gh, owner, name, branch)
    rules_read = READ_FAILED if rules_state == _FAILED else READ_OK

    # axis: a rules queue row answers queue true at once and the GraphQL read is skipped
    if rules_state == _QUEUE:
        return _result(repo, branch, queue=True, source=SOURCE_RULES, method=method,
                       reads={"rules": rules_read, "graphql": READ_SKIPPED})

    graphql_state, graphql_detail = _read_graphql(gh, owner, name, branch)
    graphql_read = READ_FAILED if graphql_state == _FAILED else READ_OK
    reads = {"rules": rules_read, "graphql": graphql_read}
    detail = _failed_details(rules_detail, graphql_detail)

    # axis: a GraphQL queue answers queue true, even when the rules read failed
    if graphql_state == _QUEUE:
        return _result(repo, branch, queue=True, source=SOURCE_GRAPHQL, reads=reads,
                       detail=detail)

    # axis: any failed read answers queue true — only two successful reads may answer false
    if rules_state == _FAILED or graphql_state == _FAILED:
        return _result(repo, branch, queue=True, source=SOURCE_READ_FAILED, reads=reads,
                       detail=detail)

    # axis: both reads succeeded and both said no queue — the one path to queue false
    return _result(repo, branch, queue=False, source=SOURCE_NONE, reads=reads)


def main(argv=None, *, run=None, monotonic=None):
    if argv is None:
        argv = sys.argv[1:]
    try:
        parser = _MergeQueueParser(prog="merge_queue")
        subparsers = parser.add_subparsers(dest="verb")
        read_parser = subparsers.add_parser("read")
        read_parser.add_argument("--repo", required=True)
        read_parser.add_argument("--branch", required=True)
        args = parser.parse_args(argv)
        if args.verb != "read":
            raise _ParseError("unknown or missing verb")
    except (_ParseError, SystemExit):
        # axis: the parse boundary (malformed CLI call returns bad-argument instead of argparse exit)
        sys.stdout.write(json.dumps(_bad_argument("invalid command-line arguments")) + "\n")
        return 1

    result = read(repo=args.repo, branch=args.branch, run=run, monotonic=monotonic)
    sys.stdout.write(json.dumps(result) + "\n")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
