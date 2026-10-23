#!/usr/bin/env python3
"""Merge a native stack through GitHub's REST merge-async endpoint.

`gh stack merge` and `gh pr *` go through GraphQL, which a cloud session's proxy refuses.
GitHub's REST `merge-async` endpoint, called on the TOP pull request of a stack, merges
everything up to and including it. The request is pinned to the top head sha, and the
result says merged only when a response GitHub returned for this request carries
`status == "merged"` — every other outcome is a refusal with a reason token. The helper
never adopts or polls a merge request it did not start (a refused PUT is never followed by a
poll), and leaves `merge_action` at GitHub's default (a merge queue when the base branch
has one, otherwise a direct merge). Exit code 0 only when GitHub reports `merged`."""
import argparse
import json
import math
import re
import shutil
import subprocess
import sys
import time

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
        "uuid": uuid if _valid_uuid(uuid) else None,
        "commit": commit if isinstance(commit, str) and _SHA40_RE.match(commit) else None,
        "message": message if isinstance(message, str) else None,
    }, None


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
    while monotonic() < end:
        sleep(min(poll_interval, end - monotonic()))
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

    # axis: the budget starts before the PUT, so the PUT and the polling share one deadline
    start = monotonic()
    try:
        proc = run(_put_argv(repo, top, sha), capture_output=True, text=True,
                   timeout=min(timeout, poll_timeout))
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
