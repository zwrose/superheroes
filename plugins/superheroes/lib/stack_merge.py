#!/usr/bin/env python3
"""Merge a native stack through GitHub's REST merge-async endpoint.

`gh stack merge` and `gh pr *` go through GraphQL, which a cloud session's proxy refuses.
GitHub's REST `merge-async` endpoint, called on the TOP pull request of a stack, merges
everything up to and including it. The request is pinned to the top head sha, and the
result says merged only when a response GitHub returned for this request carries
`status == "merged"` — every other outcome is a refusal with a reason token. The helper
never adopts or polls a merge request it did not start (a refused PUT is never followed by a
poll), and leaves `merge_action` at GitHub's default (a merge queue when the base branch
has one, otherwise a direct merge). Exit code 0 only when GitHub reports `merged`.

Before the PUT, `merge` checks linearity when the base branch has a merge queue: a queue drops a
stack whose layers carry merge commits, so a queue base with a merge commit in any layer at or
below the top is refused `stack-not-linear` with no request sent, and a stack whose layers, queue
or commits cannot be read (or whose budget ran out) is refused `linearity-unreadable`. A base with
no queue merges as before. The check, the PUT and the polling share the one invocation budget."""
import argparse
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

import merge_queue  # noqa: E402
import stack_check  # noqa: E402
import stack_linear  # noqa: E402

GH_TIMEOUT = 120
# One budget bounds a whole `merge` or `poll` invocation, the PUT included. 420 seconds
# leaves the invocation well below the 600-second host command cap, so a poll-timeout
# result (with its uuid) is always printed before the host kills the helper.
DEFAULT_POLL_TIMEOUT = 420
DEFAULT_POLL_INTERVAL = 5
MAX_DETAIL = 500

REASON_BAD_ARGUMENT = "bad-argument"
REASON_GH_UNAVAILABLE = "gh-unavailable"
REASON_MERGE_REQUEST_REFUSED = "merge-request-refused"
REASON_MERGE_RESPONSE_UNREADABLE = "merge-response-unreadable"
REASON_HEAD_MISMATCH = "head-mismatch"
REASON_MERGE_FAILED = "merge-failed"
REASON_MERGE_ENQUEUED = "merge-enqueued"
REASON_POLL_TIMEOUT = "poll-timeout"
REASON_STACK_NOT_LINEAR = "stack-not-linear"
REASON_LINEARITY_UNREADABLE = "linearity-unreadable"

STATUS_PENDING = "pending"
STATUS_MERGED = "merged"
STATUS_ENQUEUED = "enqueued"
STATUS_FAILED = "failed"
STATUSES = frozenset({STATUS_PENDING, STATUS_MERGED, STATUS_ENQUEUED, STATUS_FAILED})

MERGE_METHOD = "squash"

_REPO_RE = re.compile(r"^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+\Z")
_SHA40_RE = re.compile(r"^[0-9a-fA-F]{40}\Z")
_UUID_RE = re.compile(r"^[A-Za-z0-9-]{1,64}\Z")


class _ParseError(Exception):
    pass


class _StackMergeParser(argparse.ArgumentParser):
    def error(self, message):
        raise _ParseError(message)

    def exit(self, status=0, message=None):
        raise _ParseError(message or "")

    def _print_message(self, message, file=None):
        pass


def _put_argv(repo, top, sha):
    return [
        "gh", "api", "-X", "PUT",
        "repos/%s/pulls/%d/merge-async" % (repo, top),
        "-f", "merge_method=%s" % MERGE_METHOD,
        "-f", "sha=%s" % sha,
    ]


def _poll_argv(repo, top, uuid):
    return ["gh", "api", "repos/%s/pulls/%d/merge-async/%s" % (repo, top, uuid)]


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _is_positive_finite(value):
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value > 0
    )


def _clip(text):
    text = text if isinstance(text, str) else str(text)
    if len(text) > MAX_DETAIL:
        return text[:MAX_DETAIL] + "..."
    return text


def _result(repo, top, sha, *, merged=False, status=None, reason=None, detail=None,
            uuid=None, commit=None):
    """The one result builder. ok and merged are the same flag, set only by the caller
    that read status == merged."""
    return {
        "ok": merged,
        "merged": merged,
        "status": status,
        "reason": reason,
        "detail": None if detail is None else _clip(detail),
        "repo": repo,
        "top": top,
        "sha": sha,
        "uuid": uuid,
        "mergeCommitSha": commit,
    }


def _bad_argument(detail):
    return _result(None, None, None, reason=REASON_BAD_ARGUMENT, detail=detail)


def _validate(repo, top, sha, uuid, require_uuid, poll_timeout, poll_interval, timeout):
    """Return None when arguments are good, or the refusal dict to return."""
    # axis: repo is not an owner/name string
    if not isinstance(repo, str) or not _REPO_RE.match(repo):
        return _bad_argument("repo must be owner/name")

    # axis: top is not a positive int (bool is not an int here)
    if not _is_int(top) or top < 1:
        return _bad_argument("top must be a positive integer")

    # axis: sha is not exactly 40 hex characters
    if not isinstance(sha, str) or not _SHA40_RE.match(sha):
        return _bad_argument("sha must be a 40-character hex string")

    # axis: uuid (poll) is not 1-64 characters of letters, digits and hyphens
    if require_uuid and (not isinstance(uuid, str) or not _UUID_RE.match(uuid)):
        return _bad_argument("uuid must be 1-64 letters, digits or hyphens")

    # axis: poll_timeout is not a positive finite number
    if not _is_positive_finite(poll_timeout):
        return _bad_argument("poll_timeout must be a positive number of seconds")

    # axis: poll_interval is not a positive finite number
    if not _is_positive_finite(poll_interval):
        return _bad_argument("poll_interval must be a positive number of seconds")

    # axis: timeout is not a positive finite number
    if not _is_positive_finite(timeout):
        return _bad_argument("timeout must be a positive number of seconds")

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


def _valid_uuid(value):
    return isinstance(value, str) and _UUID_RE.match(value) is not None


def _refused_parts(proc):
    """Return (detail, uuid) for a gh call that exited non-zero. The uuid is only
    reported, never acted on."""
    body = _load_object(proc.stdout)
    message = None
    uuid = None
    if body is not None:
        message = body.get("message")
        details = body.get("details")
        if isinstance(details, dict) and _valid_uuid(details.get("uuid")):
            uuid = details["uuid"]
    if not (isinstance(message, str) and message):
        message = _proc_text(proc) or "gh api failed"
    return "gh api exited %s: %s" % (proc.returncode, message), uuid


def _read_body(text, pin, require_pending_fields):
    """Interpret one 200/202 body. Return (read, problem) — exactly one is non-None.

    read: {"status", "uuid", "commit", "message"}; problem: (reason, detail, status)."""
    body = _load_object(text)
    # axis: body is not JSON or not an object
    if body is None:
        return None, (REASON_MERGE_RESPONSE_UNREADABLE,
                      "response is not a JSON object", None)

    status = body.get("status")
    # axis: status is not one of pending, merged, enqueued, failed
    if not isinstance(status, str) or status not in STATUSES:
        return None, (REASON_MERGE_RESPONSE_UNREADABLE,
                      "response status is missing or not a known status", None)

    details = body.get("details")
    # axis: details is missing or not an object
    if not isinstance(details, dict):
        return None, (REASON_MERGE_RESPONSE_UNREADABLE,
                      "response details is missing or not an object", status)

    uuid = details.get("uuid")
    expected = details.get("expected_head_sha")

    # axis: expected_head_sha is present but not a string
    if "expected_head_sha" in details and not isinstance(expected, str):
        return None, (REASON_MERGE_RESPONSE_UNREADABLE,
                      "response expected_head_sha is not a string", status)

    # axis: expected_head_sha differs from the pinned sha
    if expected is not None and expected.lower() != pin.lower():
        return None, (REASON_HEAD_MISMATCH,
                      "GitHub expected head %s but the pin is %s" % (expected, pin), status)

    if require_pending_fields and status == STATUS_PENDING:
        # axis: a pending response carries no usable uuid
        if not _valid_uuid(uuid):
            return None, (REASON_MERGE_RESPONSE_UNREADABLE,
                          "pending response has no usable uuid", status)
        # axis: a pending response names no expected_head_sha
        if expected is None:
            return None, (REASON_MERGE_RESPONSE_UNREADABLE,
                          "pending response has no expected_head_sha", status)

    commit = details.get("sha")
    message = details.get("message")
    return {
        "status": status,
        "pinned": expected is not None,
        "uuid": uuid if _valid_uuid(uuid) else None,
        "commit": commit if isinstance(commit, str) and _SHA40_RE.match(commit) else None,
        "message": message if isinstance(message, str) else None,
    }, None


def _read_back_head(repo, top, pin, run, call_timeout):
    """Return None when the pull request's head is the pin, else (reason, detail)."""
    argv = ["gh", "api", "repos/%s/pulls/%d" % (repo, top)]
    try:
        proc = run(argv, capture_output=True, text=True, timeout=call_timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return (REASON_MERGE_RESPONSE_UNREADABLE,
                "merged head read-back failed: %s" % (exc or type(exc).__name__))
    if proc.returncode != 0:
        return (REASON_MERGE_RESPONSE_UNREADABLE,
                "merged head read-back exited %s: %s" % (
                    proc.returncode, _proc_text(proc) or "gh api failed"))
    body = _load_object(proc.stdout)
    head = body.get("head") if body is not None else None
    head_sha = head.get("sha") if isinstance(head, dict) else None
    if not (isinstance(head_sha, str) and _SHA40_RE.match(head_sha)):
        return (REASON_MERGE_RESPONSE_UNREADABLE,
                "merged head read-back carries no readable head sha")
    if head_sha.lower() != pin.lower():
        return (REASON_HEAD_MISMATCH,
                "the pull request merged at head %s but the pin is %s" % (head_sha, pin))
    return None


def _settle(repo, top, sha, read, known_uuid):
    """Return the final result for a read, or None while the request is still pending."""
    status = read["status"]
    uuid = known_uuid or read["uuid"]
    # axis: the single place that decides merged — only status == merged is success
    if status == STATUS_MERGED:
        return _result(repo, top, sha, merged=True, status=status, uuid=uuid,
                       commit=read["commit"])
    if status == STATUS_PENDING:
        return None
    # axis: status failed is a refusal carrying GitHub's message
    if status == STATUS_FAILED:
        return _result(repo, top, sha, status=status, reason=REASON_MERGE_FAILED,
                       detail=read["message"] or "GitHub reported the merge failed", uuid=uuid)
    # axis: status enqueued is not merged
    if status == STATUS_ENQUEUED:
        return _result(repo, top, sha, status=status, reason=REASON_MERGE_ENQUEUED,
                       detail=read["message"] or "pull request was added to the merge queue, not merged",
                       uuid=uuid)
    # axis: any status this function does not name is not merged
    return _result(repo, top, sha, status=status, reason=REASON_MERGE_RESPONSE_UNREADABLE,
                   detail="unhandled status", uuid=uuid)


def _poll_loop(repo, top, sha, uuid, start, poll_timeout, poll_interval, timeout,
               run, sleep, monotonic, last_status):
    end = start + poll_timeout
    last_error = None
    status = last_status
    while True:
        left = end - monotonic()
        # axis: the poll budget ended before the sleep — no sleep and no GET with no time left
        if left <= 0:
            break
        sleep(min(poll_interval, left))
        # axis: the poll budget ended during the sleep — no GET starts at or after its end
        if monotonic() >= end:
            break
        call_timeout = min(timeout, end - monotonic())
        try:
            proc = run(_poll_argv(repo, top, uuid), capture_output=True, text=True,
                       timeout=call_timeout)
        except (OSError, subprocess.TimeoutExpired) as exc:
            # axis: a poll call that raises is remembered and polling continues
            last_error = "poll call failed: %s" % (exc or type(exc).__name__)
            continue
        if proc.returncode != 0:
            # axis: a poll GET that exits non-zero is remembered and polling continues
            last_error = "poll GET exited %s: %s" % (
                proc.returncode, _proc_text(proc) or "gh api failed")
            continue
        read, problem = _read_body(proc.stdout, sha, False)
        if problem is not None:
            reason, detail, problem_status = problem
            # axis: a poll body naming a different head ends the loop
            if reason == REASON_HEAD_MISMATCH:
                return _result(repo, top, sha, status=problem_status, reason=reason,
                               detail=detail, uuid=uuid)
            # axis: an unreadable poll body is remembered and polling continues
            last_error = "poll response unreadable: %s" % detail
            continue
        status = read["status"]
        settled = _settle(repo, top, sha, read, uuid)
        if settled is not None:
            return settled
        last_error = None
    detail = "merge request still pending after %g seconds" % poll_timeout
    if last_error is not None:
        detail = "%s; last poll error: %s" % (detail, last_error)
    # axis: pending when the poll budget ran out is not merged
    return _result(repo, top, sha, status=status, reason=REASON_POLL_TIMEOUT,
                   detail=detail, uuid=uuid)


def _layers_to_merge(membership):
    """Return (base branch, layer numbers bottom to top) from an ok membership read, covering
    the layers at or below the queried top, or None when the read cannot name them."""
    stack = membership.get("stack")
    queried = membership.get("queried")
    members = membership.get("members")
    if not (isinstance(stack, dict) and isinstance(queried, dict) and isinstance(members, list)):
        return None
    base = stack.get("baseRefName")
    position = queried.get("position")
    if not (isinstance(base, str) and base and _is_int(position)):
        return None
    layers = []
    for member in members:
        if not isinstance(member, dict):
            return None
        member_position = member.get("position")
        number = member.get("number")
        if not (_is_int(member_position) and _is_int(number)):
            return None
        # axis: only layers at or below the top merge — a member above it is ignored
        if member_position <= position:
            layers.append(number)
    return base, layers


def _linear_gate(*, repo, top, end, timeout, run, monotonic):
    """Return None when the merge may be sent, or (reason, detail) when it must be refused: a
    base with a merge queue and a merge commit in a layer at or below the top is not linear, and
    anything this check cannot read is unreadable. One budget, `end`, bounds every read."""
    left = end - monotonic()
    # axis: the budget is already spent before the gate — no read is made and the merge is refused
    if left <= 0:
        return (REASON_LINEARITY_UNREADABLE,
                "the invocation budget ran out before the stack's linearity could be read")

    # axis: the membership read is bounded by the time left — its call timeout and its deadline
    membership = stack_check.read_membership(pr=top, repo=repo, timeout=min(timeout, left),
                                             deadline=left, run=run)
    # axis: a membership read that is not ok (not linked, unreadable) is linearity-unreadable
    if not membership.get("ok"):
        return (REASON_LINEARITY_UNREADABLE, "stack membership: %s: %s" % (
            membership.get("reason"), membership.get("detail")))

    named = _layers_to_merge(membership)
    # axis: no layer at or below the top can be named — nothing was checked, so unreadable
    if named is None or not named[1]:
        return (REASON_LINEARITY_UNREADABLE,
                "stack membership names no layer at or below pull request %d" % top)
    base, layers = named

    # axis: the merge-queue read shares the invocation deadline
    queue = merge_queue.read(repo=repo, branch=base, timeout=timeout, deadline_at=end,
                             run=run, monotonic=monotonic)
    # axis: a merge-queue read that is not ok is linearity-unreadable
    if not queue.get("ok"):
        return (REASON_LINEARITY_UNREADABLE, "merge queue: %s: %s" % (
            queue.get("reason"), queue.get("detail")))
    # axis: a base with no queue passes — only a successful no-queue answer lets the merge go unchecked
    if queue.get("queue") is False:
        return None

    # axis: the commit read shares the invocation deadline
    linear = stack_linear.check_rest(repo=repo, prs=layers, timeout=timeout, deadline_at=end,
                                     run=run, monotonic=monotonic)
    # axis: a complete linear read lets the merge go
    if linear.get("ok") is True:
        return None
    # axis: a merge commit in a layer on a queue base is stack-not-linear
    if linear.get("reason") == stack_linear.REASON_STACK_NOT_LINEAR:
        return (REASON_STACK_NOT_LINEAR, linear.get("detail"))
    # axis: a commit read that is not ok and not stack-not-linear is linearity-unreadable
    return (REASON_LINEARITY_UNREADABLE, "%s: %s" % (linear.get("reason"), linear.get("detail")))


def merge(*, repo, top, sha, poll_timeout=DEFAULT_POLL_TIMEOUT,
          poll_interval=DEFAULT_POLL_INTERVAL, timeout=GH_TIMEOUT,
          run=None, sleep=None, monotonic=None):
    """Merge the stack whose top pull request is `top`, pinned to head `sha`. Return the
    result dict; GitHub-side and argument-side failures return a refusal and raise nothing."""
    run = subprocess.run if run is None else run
    sleep = time.sleep if sleep is None else sleep
    monotonic = time.monotonic if monotonic is None else monotonic

    refusal = _validate(repo, top, sha, None, False, poll_timeout, poll_interval, timeout)
    if refusal is not None:
        return refusal

    # axis: gh is not on PATH
    if not shutil.which("gh"):
        return _result(repo, top, sha, reason=REASON_GH_UNAVAILABLE, detail="gh not on PATH")

    # axis: the budget starts before the linearity gate, so the gate, the PUT and the polling
    # share one deadline
    start = monotonic()
    end = start + poll_timeout

    refused = _linear_gate(repo=repo, top=top, end=end, timeout=timeout, run=run,
                           monotonic=monotonic)
    # axis: the gate runs before the PUT — a refusal sends no merge request
    if refused is not None:
        reason, detail = refused
        return _result(repo, top, sha, reason=reason, detail=detail)

    put_left = end - monotonic()
    # axis: the budget ran out between the gate and the PUT — the PUT is not sent
    if put_left <= 0:
        return _result(repo, top, sha, reason=REASON_LINEARITY_UNREADABLE,
                       detail="the invocation budget ran out before the merge request was sent")
    try:
        # axis: the PUT's call timeout is capped by the time left after the gate
        proc = run(_put_argv(repo, top, sha), capture_output=True, text=True,
                   timeout=min(timeout, put_left))
    except (OSError, subprocess.TimeoutExpired) as exc:
        # axis: run raises OSError or TimeoutExpired on the PUT
        return _result(repo, top, sha, reason=REASON_MERGE_REQUEST_REFUSED,
                       detail="merge request call failed: %s" % (exc or type(exc).__name__))

    # axis: the PUT exits non-zero — refused; an existing request is never adopted or polled
    if proc.returncode != 0:
        detail, uuid = _refused_parts(proc)
        return _result(repo, top, sha, reason=REASON_MERGE_REQUEST_REFUSED,
                       detail=detail, uuid=uuid)

    read, problem = _read_body(proc.stdout, sha, True)
    if problem is not None:
        reason, detail, status = problem
        return _result(repo, top, sha, status=status, reason=reason, detail=detail)

    # axis: an immediate merged response that names no expected_head_sha is checked against
    # the merged pull request's own head before it is accepted
    if read["status"] == STATUS_MERGED and not read["pinned"]:
        # axis: the read-back shares the one invocation budget — only the time left, and none
        # left means it is not attempted and the merge is never reported unverified
        left = start + poll_timeout - monotonic()
        if left <= 0:
            problem = (REASON_MERGE_RESPONSE_UNREADABLE,
                       "the invocation budget ran out before the merged head could be read back")
        else:
            problem = _read_back_head(repo, top, sha, run, min(timeout, left))
        if problem is not None:
            reason, detail = problem
            return _result(repo, top, sha, status=read["status"], reason=reason, detail=detail)

    settled = _settle(repo, top, sha, read, None)
    if settled is not None:
        return settled

    return _poll_loop(repo, top, sha, read["uuid"], start, poll_timeout,
                      poll_interval, timeout, run, sleep, monotonic, read["status"])


def poll(*, repo, top, uuid, sha, poll_timeout=DEFAULT_POLL_TIMEOUT,
         poll_interval=DEFAULT_POLL_INTERVAL, timeout=GH_TIMEOUT,
         run=None, sleep=None, monotonic=None):
    """Resume a merge request that `merge` reported as poll-timeout."""
    run = subprocess.run if run is None else run
    sleep = time.sleep if sleep is None else sleep
    monotonic = time.monotonic if monotonic is None else monotonic

    refusal = _validate(repo, top, sha, uuid, True, poll_timeout, poll_interval, timeout)
    if refusal is not None:
        return refusal

    # axis: gh is not on PATH
    if not shutil.which("gh"):
        return _result(repo, top, sha, reason=REASON_GH_UNAVAILABLE, detail="gh not on PATH",
                       uuid=uuid)

    return _poll_loop(repo, top, sha, uuid, monotonic(), poll_timeout, poll_interval,
                      timeout, run, sleep, monotonic, None)


def main(argv=None, *, run=None, sleep=None, monotonic=None):
    if argv is None:
        argv = sys.argv[1:]
    try:
        parser = _StackMergeParser(prog="stack_merge")
        subparsers = parser.add_subparsers(dest="verb")
        merge_parser = subparsers.add_parser("merge")
        merge_parser.add_argument("--repo", required=True)
        merge_parser.add_argument("--top", type=int, required=True)
        merge_parser.add_argument("--sha", required=True)
        merge_parser.add_argument("--poll-timeout", type=float, default=DEFAULT_POLL_TIMEOUT)
        merge_parser.add_argument("--poll-interval", type=float, default=DEFAULT_POLL_INTERVAL)
        poll_parser = subparsers.add_parser("poll")
        poll_parser.add_argument("--repo", required=True)
        poll_parser.add_argument("--top", type=int, required=True)
        poll_parser.add_argument("--uuid", required=True)
        poll_parser.add_argument("--sha", required=True)
        poll_parser.add_argument("--poll-timeout", type=float, default=DEFAULT_POLL_TIMEOUT)
        poll_parser.add_argument("--poll-interval", type=float, default=DEFAULT_POLL_INTERVAL)
        args = parser.parse_args(argv)
        if args.verb not in ("merge", "poll"):
            raise _ParseError("unknown or missing verb")
    except (_ParseError, SystemExit):
        # axis: the parse boundary (malformed CLI call returns bad-argument instead of argparse exit)
        sys.stdout.write(json.dumps(_bad_argument("invalid command-line arguments")) + "\n")
        return 1

    if args.verb == "merge":
        result = merge(repo=args.repo, top=args.top, sha=args.sha,
                       poll_timeout=args.poll_timeout, poll_interval=args.poll_interval,
                       run=run, sleep=sleep, monotonic=monotonic)
    else:
        result = poll(repo=args.repo, top=args.top, uuid=args.uuid, sha=args.sha,
                      poll_timeout=args.poll_timeout, poll_interval=args.poll_interval,
                      run=run, sleep=sleep, monotonic=monotonic)
    sys.stdout.write(json.dumps(result) + "\n")
    return 0 if result["merged"] else 1


if __name__ == "__main__":
    sys.exit(main())
