#!/usr/bin/env python3
"""Read GitHub native-stack membership for a pull request via GraphQL.

Every membership answer is one complete GitHub read or a refusal — never a partial
or mixed-time picture. All validation lives in read_membership; the CLI is a thin
projection."""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import grounding_stage  # noqa: E402

GH_TIMEOUT = 120
DEFAULT_PAGE_SIZE = 50
MIN_PAGE_SIZE = 1
MAX_PAGE_SIZE = 100

REASON_BAD_ARGUMENT = "bad-argument"
REASON_NOT_LINKED = "not-linked"
REASON_STACK_UNREADABLE = "stack-unreadable"
REASON_ORDER_MISMATCH = "order-mismatch"
REASON_VET_UNREADABLE = "vet-unreadable"

VERDICT_READY = "READY"
VERDICT_NOT_READY = "NOT-READY"
VERDICT_PARKED = "PARKED"
VET_NOT_READY = "vet-not-ready"

_REPO_RE = re.compile(r"^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$")
_SHA40_RE = re.compile(r"^[0-9a-fA-F]{40}$")
PR_VET_STATE_VALUES = frozenset({"OPEN", "CLOSED", "MERGED"})

# Machine-readable home: rubric/vet-verdict-form.json (loaded lazily on first
# read_vet_verdict call). Human-facing statement: skills/showrunner/reference/vet-receipt.md
# (verdict-form clause).
_vet_verdict_form_loaded = False
_vet_verdict_form = None
_vet_verdict_form_error = None


def _vet_verdict_form_path():
    return os.path.normpath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "rubric", "vet-verdict-form.json")
    )


def _reset_vet_verdict_form_cache():
    global _vet_verdict_form_loaded, _vet_verdict_form, _vet_verdict_form_error
    _vet_verdict_form_loaded = False
    _vet_verdict_form = None
    _vet_verdict_form_error = None


def _load_vet_verdict_form():
    """Return (form, error_detail) — form is (separator, tokens) or None."""
    global _vet_verdict_form_loaded, _vet_verdict_form, _vet_verdict_form_error
    if _vet_verdict_form_loaded:
        return _vet_verdict_form, _vet_verdict_form_error

    _vet_verdict_form_loaded = True
    path = _vet_verdict_form_path()
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
    except FileNotFoundError:
        _vet_verdict_form_error = "vet-verdict-form.json is missing"
        return None, _vet_verdict_form_error
    except OSError as exc:
        _vet_verdict_form_error = "vet-verdict-form.json is unreadable: %s" % exc
        return None, _vet_verdict_form_error

    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        _vet_verdict_form_error = "vet-verdict-form.json is not valid JSON"
        return None, _vet_verdict_form_error

    if not isinstance(data, dict):
        _vet_verdict_form_error = "vet-verdict-form.json is not an object"
        return None, _vet_verdict_form_error

    separator = data.get("separator")
    if not isinstance(separator, str):
        _vet_verdict_form_error = "vet-verdict-form.json separator is missing or not a string"
        return None, _vet_verdict_form_error

    tokens_raw = data.get("tokens")
    if not isinstance(tokens_raw, list):
        _vet_verdict_form_error = "vet-verdict-form.json tokens is missing or not a list"
        return None, _vet_verdict_form_error
    if not tokens_raw:
        _vet_verdict_form_error = "vet-verdict-form.json tokens is empty"
        return None, _vet_verdict_form_error

    tokens = []
    for index, entry in enumerate(tokens_raw):
        if not isinstance(entry, dict):
            _vet_verdict_form_error = "vet-verdict-form.json tokens[%d] is not an object" % index
            return None, _vet_verdict_form_error
        token = entry.get("token")
        if not isinstance(token, str):
            _vet_verdict_form_error = "vet-verdict-form.json tokens[%d].token is missing or not a string" % index
            return None, _vet_verdict_form_error
        verdict = entry.get("verdict")
        if not isinstance(verdict, str):
            _vet_verdict_form_error = "vet-verdict-form.json tokens[%d].verdict is missing or not a string" % index
            return None, _vet_verdict_form_error
        tokens.append((token, verdict))

    expected_verdicts = {VERDICT_READY, VERDICT_NOT_READY, VERDICT_PARKED}
    seen_verdicts = set()
    for _token, verdict in tokens:
        if verdict not in expected_verdicts:
            _vet_verdict_form_error = (
                "vet-verdict-form.json verdict %r is not recognised" % verdict
            )
            return None, _vet_verdict_form_error
        if verdict in seen_verdicts:
            _vet_verdict_form_error = (
                "vet-verdict-form.json verdict %r is duplicated" % verdict
            )
            return None, _vet_verdict_form_error
        seen_verdicts.add(verdict)
    if seen_verdicts != expected_verdicts:
        for missing in expected_verdicts - seen_verdicts:
            _vet_verdict_form_error = (
                "vet-verdict-form.json verdict %r is missing" % missing
            )
            return None, _vet_verdict_form_error

    _vet_verdict_form = (separator, tuple(tokens))
    return _vet_verdict_form, None

QUERY = """\
query($owner:String!,$repo:String!,$pr:Int!,$first:Int!,$after:String){
  repository(owner:$owner,name:$repo){
    pullRequest(number:$pr){
      number baseRefName headRefName headRefOid
      stackEntry{
        position
        stack{
          number size baseRefName
          entries(first:$first, after:$after){
            pageInfo{ hasNextPage endCursor }
            nodes{ position pullRequest{ number state isDraft headRefName headRefOid baseRefName } }
          }
        }
      }
    }
  }
}"""


class _ParseError(Exception):
    pass


class _StackCheckParser(argparse.ArgumentParser):
    def error(self, message):
        raise _ParseError(message)

    def exit(self, status=0, message=None):
        raise _ParseError(message or "")


def _graphql_argv(owner, name, pr, first, after=None):
    argv = [
        "gh",
        "api",
        "graphql",
        "-F",
        "owner=%s" % owner,
        "-F",
        "repo=%s" % name,
        "-F",
        "pr=%d" % pr,
        "-F",
        "first=%d" % first,
        "-f",
        "query=%s" % QUERY,
    ]
    if after is not None:
        argv.extend(["-f", "after=%s" % after])
    return argv


def _refusal(reason, detail, repo=None, pr=None, pages=0):
    return {
        "ok": False,
        "reason": reason,
        "detail": detail,
        "repo": repo,
        "pr": pr,
        "stack": None,
        "queried": None,
        "members": [],
        "pages": pages,
    }


def _success(repo, pr, stack, queried, members, pages):
    return {
        "ok": True,
        "reason": None,
        "detail": None,
        "repo": repo,
        "pr": pr,
        "stack": stack,
        "queried": queried,
        "members": members,
        "pages": pages,
    }


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _is_positive_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0


def _read_refusal(reason, detail):
    return {"ok": False, "reason": reason, "detail": detail}


def _run_kwargs(env):
    if env is None:
        return {}
    return {"env": env}


def _proc_output(proc):
    return ((proc.stdout or "") + (proc.stderr or "")).strip()


def _snapshot_from_page(pull_request, stack_entry, stack):
    return {
        "pr_number": pull_request["number"],
        "pr_baseRefName": pull_request["baseRefName"],
        "pr_headRefName": pull_request["headRefName"],
        "pr_headRefOid": pull_request["headRefOid"],
        "position": stack_entry["position"],
        "stack_number": stack["number"],
        "stack_size": stack["size"],
        "stack_baseRefName": stack["baseRefName"],
    }


def _snapshot_matches(snapshot, pull_request, stack_entry, stack):
    current = _snapshot_from_page(pull_request, stack_entry, stack)
    return current == snapshot


def _parse_member(node):
    if not isinstance(node, dict):
        return None, "stack entry node is not an object"
    position = node.get("position")
    if not _is_int(position):
        return None, "stack entry position is missing or not an integer"
    pull_request = node.get("pullRequest")
    if not isinstance(pull_request, dict):
        return None, "stack entry pullRequest is missing or not an object"
    number = pull_request.get("number")
    if not _is_int(number):
        return None, "stack entry pullRequest number is missing or not an integer"
    state = pull_request.get("state")
    if not isinstance(state, str):
        return None, "stack entry pullRequest state is missing or not a string"
    is_draft = pull_request.get("isDraft")
    if not isinstance(is_draft, bool):
        return None, "stack entry pullRequest isDraft is missing or not a boolean"
    head_ref_name = pull_request.get("headRefName")
    if not isinstance(head_ref_name, str):
        return None, "stack entry pullRequest headRefName is missing or not a string"
    head_ref_oid = pull_request.get("headRefOid")
    if not isinstance(head_ref_oid, str):
        return None, "stack entry pullRequest headRefOid is missing or not a string"
    base_ref_name = pull_request.get("baseRefName")
    if not isinstance(base_ref_name, str):
        return None, "stack entry pullRequest baseRefName is missing or not a string"
    return (
        {
            "position": position,
            "number": number,
            "state": state,
            "isDraft": is_draft,
            "headRefName": head_ref_name,
            "headRefOid": head_ref_oid,
            "baseRefName": base_ref_name,
        },
        None,
    )


def _validate_membership_arguments(pr, repo, expect_stack, page_size, deadline):
    """Return None when arguments are good, or the refusal dict to return."""
    # axis: pr is not an int (bool is not an int here)
    if not _is_int(pr):
        return _refusal(REASON_BAD_ARGUMENT, "pr must be a positive integer", repo=repo, pr=None)

    # axis: pr < 1
    if pr < 1:
        return _refusal(REASON_BAD_ARGUMENT, "pr must be a positive integer", repo=repo, pr=None)

    # axis: repo is not a string
    if not isinstance(repo, str):
        return _refusal(REASON_BAD_ARGUMENT, "repo must be owner/name", repo=None, pr=pr)

    # axis: repo does not match owner/name pattern
    if not _REPO_RE.match(repo):
        return _refusal(REASON_BAD_ARGUMENT, "repo must be owner/name", repo=None, pr=pr)

    # axis: expect_stack supplied and not an int
    if expect_stack is not None and not _is_int(expect_stack):
        return _refusal(REASON_BAD_ARGUMENT,
            "expect_stack must be a positive integer", repo=repo, pr=pr)

    # axis: expect_stack supplied and < 1
    if expect_stack is not None and expect_stack < 1:
        return _refusal(REASON_BAD_ARGUMENT,
            "expect_stack must be a positive integer", repo=repo, pr=pr)

    # axis: page_size is not an int
    if not _is_int(page_size):
        return _refusal(REASON_BAD_ARGUMENT,
            "page_size must be an integer between %d and %d" % (MIN_PAGE_SIZE, MAX_PAGE_SIZE),
            repo=repo, pr=pr)

    # axis: page_size < MIN_PAGE_SIZE
    if page_size < MIN_PAGE_SIZE:
        return _refusal(REASON_BAD_ARGUMENT,
            "page_size must be an integer between %d and %d" % (MIN_PAGE_SIZE, MAX_PAGE_SIZE),
            repo=repo, pr=pr)

    # axis: page_size > MAX_PAGE_SIZE
    if page_size > MAX_PAGE_SIZE:
        return _refusal(REASON_BAD_ARGUMENT,
            "page_size must be an integer between %d and %d" % (MIN_PAGE_SIZE, MAX_PAGE_SIZE),
            repo=repo, pr=pr)

    # axis: deadline supplied and not a real number
    if deadline is not None and (
        not isinstance(deadline, (int, float)) or isinstance(deadline, bool)
    ):
        return _refusal(REASON_BAD_ARGUMENT,
            "deadline must be a positive number of seconds", repo=repo, pr=pr)

    # axis: deadline supplied and not greater than zero
    if deadline is not None and not (deadline > 0):
        return _refusal(REASON_BAD_ARGUMENT,
            "deadline must be a positive number of seconds", repo=repo, pr=pr)

    # axis: gh is not on PATH
    if not shutil.which("gh"):
        return _refusal(REASON_STACK_UNREADABLE, "gh not on PATH", repo=repo, pr=pr)

    return None


def _transport_graphql(
    owner, name, pr, page_size, after, timeout, run, repo, pages, deadline=None, deadline_at=None,
):
    """Run one gh api graphql page. Return (payload, refusal) — exactly one is non-None."""
    # axis: read budget exhausted before a gh page
    if deadline_at is not None and time.monotonic() >= deadline_at:
        return None, _refusal(REASON_STACK_UNREADABLE,
            "read budget of %g seconds exhausted after %d pages" % (deadline, pages),
            repo=repo, pr=pr, pages=pages)

    effective_timeout = timeout
    if deadline_at is not None:
        remaining = deadline_at - time.monotonic()
        # axis: timeout=None beside a read budget
        if timeout is None:
            effective_timeout = remaining
        else:
            effective_timeout = min(timeout, remaining)

    argv = _graphql_argv(owner, name, pr, page_size, after)
    try:
        proc = run(argv, capture_output=True, text=True, timeout=effective_timeout)
    except (FileNotFoundError, OSError) as exc:
        # axis: run raises FileNotFoundError/OSError
        return None, _refusal(REASON_STACK_UNREADABLE, str(exc), repo=repo, pr=pr, pages=pages)
    except subprocess.TimeoutExpired:
        # axis: run raises subprocess.TimeoutExpired
        return None, _refusal(REASON_STACK_UNREADABLE, "gh call timed out", repo=repo, pr=pr, pages=pages)

    # axis: gh exits non-zero
    if proc.returncode != 0:
        return None, _refusal(REASON_STACK_UNREADABLE, _proc_output(proc) or "gh api graphql failed",
            repo=repo, pr=pr, pages=pages + 1)

    try:
        payload = json.loads(proc.stdout or "")
    except json.JSONDecodeError:
        # axis: stdout is not JSON
        return None, _refusal(REASON_STACK_UNREADABLE,
            "gh api graphql returned output that is not JSON", repo=repo, pr=pr, pages=pages + 1)

    # axis: parsed JSON payload is not an object
    if not isinstance(payload, dict):
        return None, _refusal(REASON_STACK_UNREADABLE,
            "gh api graphql returned JSON that is not an object", repo=repo, pr=pr, pages=pages + 1)

    errors = payload.get("errors")
    if errors is None:
        errors = []
    # axis: errors is present but not a list
    if not isinstance(errors, list):
        return None, _refusal(REASON_STACK_UNREADABLE, "gh api graphql errors is not a list",
            repo=repo, pr=pr, pages=pages + 1)
    # axis: response carries a non-empty errors array
    if errors:
        return None, _refusal(REASON_STACK_UNREADABLE, json.dumps(errors), repo=repo, pr=pr, pages=pages + 1)

    return payload, None


def _parse_membership_page(payload, repo, pr, pages, snapshot, stack_size, collected):
    """Validate and extract one page. Return (page, refusal) — exactly one is non-None."""
    data = payload.get("data")
    repository = data.get("repository") if isinstance(data, dict) else None
    # axis: data/repository is null or not an object
    if not isinstance(data, dict) or not isinstance(repository, dict):
        return None, _refusal(REASON_STACK_UNREADABLE,
            "graphql data/repository is null or not an object", repo=repo, pr=pr, pages=pages)

    pull_request = repository.get("pullRequest")
    # axis: pullRequest is null or not an object
    if not isinstance(pull_request, dict):
        return None, _refusal(REASON_STACK_UNREADABLE, "graphql pullRequest is null or not an object",
            repo=repo, pr=pr, pages=pages)

    pr_number = pull_request.get("number")
    pr_base_ref = pull_request.get("baseRefName")
    pr_head_ref = pull_request.get("headRefName")
    pr_head_oid = pull_request.get("headRefOid")
    # axis: a required top-level pull-request field is missing or of the wrong type
    if (
        not _is_int(pr_number)
        or not isinstance(pr_base_ref, str)
        or not isinstance(pr_head_ref, str)
        or not isinstance(pr_head_oid, str)
    ):
        return None, _refusal(REASON_STACK_UNREADABLE,
            "required pullRequest field is missing or of the wrong type",
            repo=repo, pr=pr, pages=pages)

    stack_entry = pull_request.get("stackEntry")
    # axis: stackEntry is null
    if stack_entry is None:
        return None, _refusal(REASON_NOT_LINKED,
            "pull request is not in a stack", repo=repo, pr=pr, pages=pages)

    entry_position = stack_entry.get("position") if isinstance(stack_entry, dict) else None
    # axis: stackEntry is present but not an object, or position is missing/not an int
    if not isinstance(stack_entry, dict) or not _is_int(entry_position):
        return None, _refusal(REASON_STACK_UNREADABLE,
            "stackEntry is not an object or position is missing or not an integer",
            repo=repo, pr=pr, pages=pages)

    stack = stack_entry.get("stack")
    stack_number = stack.get("number") if isinstance(stack, dict) else None
    stack_size_value = stack.get("size") if isinstance(stack, dict) else None
    stack_base_ref = stack.get("baseRefName") if isinstance(stack, dict) else None
    # axis: stack is missing/not an object, or number/size/baseRefName wrong type
    if (
        not isinstance(stack, dict)
        or not _is_int(stack_number)
        or not _is_int(stack_size_value)
        or not isinstance(stack_base_ref, str)
    ):
        return None, _refusal(REASON_STACK_UNREADABLE, "stack field is missing or of the wrong type",
            repo=repo, pr=pr, pages=pages)

    entries = stack.get("entries")
    page_info = entries.get("pageInfo") if isinstance(entries, dict) else None
    nodes = entries.get("nodes") if isinstance(entries, dict) else None
    # axis: entries/pageInfo/nodes is missing or of the wrong type
    if not isinstance(entries, dict) or not isinstance(page_info, dict) or not isinstance(nodes, list):
        return None, _refusal(REASON_STACK_UNREADABLE,
            "stack entries/pageInfo/nodes is missing or of the wrong type",
            repo=repo, pr=pr, pages=pages)

    page_snapshot = snapshot
    page_stack_size = stack_size
    if pages == 1:
        page_snapshot = _snapshot_from_page(pull_request, stack_entry, stack)
        page_stack_size = stack_size_value
    else:
        # axis: a later page reports a different page-one snapshot value
        if not _snapshot_matches(snapshot, pull_request, stack_entry, stack):
            return None, _refusal(REASON_ORDER_MISMATCH,
                "later page disagrees with page-one snapshot", repo=repo, pr=pr, pages=pages)

    added = 0
    for node in nodes:
        member, parse_err = _parse_member(node)
        if parse_err:
            # axis: a node, its position, or one of its pull-request fields is missing or wrong type
            return None, _refusal(REASON_STACK_UNREADABLE, parse_err, repo=repo, pr=pr, pages=pages)
        # axis: the collected count would exceed size mid-read
        if len(collected) + 1 > page_stack_size:
            return None, _refusal(REASON_STACK_UNREADABLE,
                "collected member count would exceed stack size", repo=repo, pr=pr, pages=pages)
        collected.append(member)
        added += 1

    has_next_page = page_info.get("hasNextPage")
    # axis: pageInfo hasNextPage is missing or not a boolean
    if not isinstance(has_next_page, bool):
        return None, _refusal(REASON_STACK_UNREADABLE,
            "pageInfo hasNextPage is missing or not a boolean", repo=repo, pr=pr, pages=pages)

    end_cursor = page_info.get("endCursor")

    return {
        "has_next_page": has_next_page,
        "end_cursor": end_cursor,
        "added": added,
        "snapshot": page_snapshot,
        "stack_size": page_stack_size,
    }, None


_INVARIANT_TAG_REFUSAL = "refusal"
_INVARIANT_TAG_CONTINUE = "continue"
_INVARIANT_TAG_SUCCESS = "success"


def _validate_stack_invariants(
    collected,
    snapshot,
    stack_size,
    expect_stack,
    repo,
    pr,
    pages,
    prior_members,
    verification_pass,
):
    """Whole-stack invariants after pagination. Return tagged refusal, continue, or success."""
    # axis: expect_stack was supplied and does not equal stack.number
    if expect_stack is not None and expect_stack != snapshot["stack_number"]:
        return {"tag": _INVARIANT_TAG_REFUSAL, "result": _refusal(REASON_ORDER_MISMATCH,
            "expect_stack does not equal stack number", repo=repo, pr=pr, pages=pages)}

    positions = {member["position"] for member in collected}
    expected_positions = set(range(1, stack_size + 1))
    # axis: collected member count does not equal stack size
    if len(collected) != stack_size:
        return {"tag": _INVARIANT_TAG_REFUSAL, "result": _refusal(REASON_ORDER_MISMATCH,
            "collected member count does not equal stack size", repo=repo, pr=pr, pages=pages)}

    # axis: collected positions are not exactly 1..size
    if positions != expected_positions:
        return {"tag": _INVARIANT_TAG_REFUSAL, "result": _refusal(REASON_ORDER_MISMATCH,
            "collected positions are not exactly 1..size", repo=repo, pr=pr, pages=pages)}

    members_at_position = [member for member in collected if member["position"] == snapshot["position"]]
    # axis: the queried pull request is not present exactly once at its reported position
    if len(members_at_position) != 1:
        return {"tag": _INVARIANT_TAG_REFUSAL, "result": _refusal(REASON_ORDER_MISMATCH,
            "queried pull request is not present exactly once at its reported position",
            repo=repo, pr=pr, pages=pages)}
    member_at_position = members_at_position[0]
    # axis: that entry's headRefName/headRefOid/baseRefName disagree with the top-level fields
    if (
        member_at_position["number"] != snapshot["pr_number"]
        or member_at_position["headRefName"] != snapshot["pr_headRefName"]
        or member_at_position["headRefOid"] != snapshot["pr_headRefOid"]
        or member_at_position["baseRefName"] != snapshot["pr_baseRefName"]
    ):
        return {"tag": _INVARIANT_TAG_REFUSAL, "result": _refusal(REASON_ORDER_MISMATCH,
            "queried pull request entry disagrees with top-level pull request fields",
            repo=repo, pr=pr, pages=pages)}

    if verification_pass == 0:
        return {"tag": _INVARIANT_TAG_CONTINUE,
            "prior_members": sorted(collected, key=lambda item: item["position"])}

    current_members = sorted(collected, key=lambda item: item["position"])
    # axis: membership changes between two complete enumeration passes
    if current_members != prior_members:
        return {"tag": _INVARIANT_TAG_REFUSAL, "result": _refusal(REASON_ORDER_MISMATCH,
            "membership changed between enumeration passes", repo=repo, pr=pr, pages=pages)}

    members = sorted(collected, key=lambda item: item["position"])
    stack = {
        "number": snapshot["stack_number"],
        "size": snapshot["stack_size"],
        "baseRefName": snapshot["stack_baseRefName"],
    }
    queried = {
        "number": snapshot["pr_number"],
        "position": snapshot["position"],
        "headRefName": snapshot["pr_headRefName"],
        "headRefOid": snapshot["pr_headRefOid"],
        "baseRefName": snapshot["pr_baseRefName"],
    }
    return {"tag": _INVARIANT_TAG_SUCCESS,
        "result": _success(repo, pr, stack, queried, members, pages)}


def _repo_slug_argv():
    return ["gh", "repo", "view", "--json", "nameWithOwner"]


def _effective_timeout(timeout, deadline_at):
    if deadline_at is None:
        return timeout
    remaining = deadline_at - time.monotonic()
    if timeout is None:
        return remaining
    return min(timeout, remaining)


def _validate_repo_root(repo_root):
    if not isinstance(repo_root, str) or not repo_root:
        return _read_refusal(REASON_BAD_ARGUMENT, "repo_root must be a non-empty string")
    return None


def _validate_read_timeout(timeout):
    if not _is_positive_number(timeout):
        return _read_refusal(REASON_BAD_ARGUMENT, "timeout must be a positive number of seconds")
    return None


def _validate_read_deadline(deadline):
    if deadline is None:
        return None
    if not _is_positive_number(deadline):
        return _read_refusal(REASON_BAD_ARGUMENT, "deadline must be a positive number of seconds")
    return None


def _parse_repo_slug_payload(proc):
    if proc.returncode != 0:
        return None, _read_refusal(
            REASON_STACK_UNREADABLE, _proc_output(proc) or "gh repo view failed")

    try:
        payload = json.loads(proc.stdout or "")
    except json.JSONDecodeError:
        return None, _read_refusal(
            REASON_STACK_UNREADABLE, "gh repo view returned output that is not JSON")

    if not isinstance(payload, dict):
        return None, _read_refusal(
            REASON_STACK_UNREADABLE, "gh repo view returned JSON that is not an object")

    name = payload.get("nameWithOwner")
    if not isinstance(name, str) or not name:
        return None, _read_refusal(
            REASON_STACK_UNREADABLE, "nameWithOwner is missing, not a string, or empty")

    if not _REPO_RE.match(name):
        return None, _read_refusal(
            REASON_STACK_UNREADABLE, "nameWithOwner is not a valid owner/name slug")

    return name, None


def _pr_vet_state_argv(pr, repo):
    return [
        "gh", "pr", "view", str(pr), "--repo", repo,
        "--json", "state,isDraft,headRefOid,body",
    ]


def _parse_pr_vet_state_payload(proc, pr):
    if proc.returncode != 0:
        return None, _read_refusal(
            REASON_STACK_UNREADABLE, _proc_output(proc) or "gh pr view failed")

    try:
        payload = json.loads(proc.stdout or "")
    except json.JSONDecodeError:
        return None, _read_refusal(
            REASON_STACK_UNREADABLE, "gh pr view returned output that is not JSON")

    if not isinstance(payload, dict):
        return None, _read_refusal(
            REASON_STACK_UNREADABLE, "gh pr view returned JSON that is not an object")

    state = payload.get("state")
    if not isinstance(state, str):
        return None, _read_refusal(
            REASON_STACK_UNREADABLE, "state is missing or not a string")
    if state not in PR_VET_STATE_VALUES:
        return None, _read_refusal(
            REASON_STACK_UNREADABLE,
            "state is not one of the enumerated values: %r" % state)

    is_draft = payload.get("isDraft")
    if not isinstance(is_draft, bool):
        return None, _read_refusal(
            REASON_STACK_UNREADABLE, "isDraft is missing or not a boolean")

    head_ref_oid = payload.get("headRefOid")
    if not isinstance(head_ref_oid, str) or not _SHA40_RE.match(head_ref_oid):
        return None, _read_refusal(
            REASON_STACK_UNREADABLE,
            "headRefOid is missing, not a string, or not 40 hex")

    body = payload.get("body")
    if not isinstance(body, str):
        return None, _read_refusal(
            REASON_STACK_UNREADABLE, "body is missing or not a string")

    return {
        "number": pr,
        "state": state,
        "isDraft": is_draft,
        "headRefOid": head_ref_oid,
        "body": body,
    }, None


def read_pr_vet_state(pr, repo, *, deadline=None, timeout=GH_TIMEOUT, run=None, env=None):
    """Return (state, refusal) — exactly one is non-None.

    state: {"number": int, "state": str, "isDraft": bool, "headRefOid": str, "body": str}
    """
    if run is None:
        run = subprocess.run

    if not _is_int(pr):
        return None, _read_refusal(REASON_BAD_ARGUMENT, "pr must be a positive integer")
    if pr < 1:
        return None, _read_refusal(REASON_BAD_ARGUMENT, "pr must be a positive integer")
    if not isinstance(repo, str) or not _REPO_RE.match(repo):
        return None, _read_refusal(REASON_BAD_ARGUMENT, "repo must be owner/name")

    arg_refusal = _validate_read_timeout(timeout)
    if arg_refusal is not None:
        return None, arg_refusal

    arg_refusal = _validate_read_deadline(deadline)
    if arg_refusal is not None:
        return None, arg_refusal

    deadline_at = None if deadline is None else time.monotonic() + deadline
    if deadline_at is not None and time.monotonic() >= deadline_at:
        return None, _read_refusal(
            REASON_STACK_UNREADABLE,
            "read budget of %g seconds exhausted before gh pr view" % deadline)

    if not shutil.which("gh"):
        return None, _read_refusal(REASON_STACK_UNREADABLE, "gh not on PATH")

    effective_timeout = _effective_timeout(timeout, deadline_at)
    argv = _pr_vet_state_argv(pr, repo)
    run_kwargs = _run_kwargs(env)
    try:
        proc = run(
            argv,
            capture_output=True,
            text=True,
            timeout=effective_timeout,
            **run_kwargs,
        )
    except (FileNotFoundError, OSError) as exc:
        return None, _read_refusal(REASON_STACK_UNREADABLE, str(exc))
    except subprocess.TimeoutExpired:
        return None, _read_refusal(REASON_STACK_UNREADABLE, "gh call timed out")

    return _parse_pr_vet_state_payload(proc, pr)


def resolve_repo_slug(repo_root, *, deadline=None, timeout=GH_TIMEOUT, run=None, env=None):
    """Return (slug, refusal) — exactly one is non-None."""
    if run is None:
        run = subprocess.run

    arg_refusal = _validate_repo_root(repo_root)
    if arg_refusal is not None:
        return None, arg_refusal

    arg_refusal = _validate_read_timeout(timeout)
    if arg_refusal is not None:
        return None, arg_refusal

    arg_refusal = _validate_read_deadline(deadline)
    if arg_refusal is not None:
        return None, arg_refusal

    deadline_at = None if deadline is None else time.monotonic() + deadline
    if deadline_at is not None and time.monotonic() >= deadline_at:
        return None, _read_refusal(
            REASON_STACK_UNREADABLE,
            "read budget of %g seconds exhausted before gh repo view" % deadline)

    if not shutil.which("gh"):
        return None, _read_refusal(REASON_STACK_UNREADABLE, "gh not on PATH")

    effective_timeout = _effective_timeout(timeout, deadline_at)
    argv = _repo_slug_argv()
    run_kwargs = _run_kwargs(env)
    try:
        proc = run(
            argv,
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=effective_timeout,
            **run_kwargs,
        )
    except (FileNotFoundError, OSError) as exc:
        return None, _read_refusal(REASON_STACK_UNREADABLE, str(exc))
    except subprocess.TimeoutExpired:
        return None, _read_refusal(REASON_STACK_UNREADABLE, "gh call timed out")

    return _parse_repo_slug_payload(proc)


def _validate_head_sha(head_sha):
    if not isinstance(head_sha, str) or not _SHA40_RE.match(head_sha):
        return _read_refusal(REASON_BAD_ARGUMENT, "head_sha must be a 40-character hex string")
    return None


def _first_nonempty_line(text):
    for line in text.splitlines():
        if line.strip():
            return line
    return None


def _parse_vet_verdict_line(line, head_sha, separator, tokens):
    matched_verdict = None
    matched_token = None
    for token, verdict in tokens:
        if line.startswith(token):
            matched_verdict = verdict
            matched_token = token
            break
    if matched_verdict is None:
        return VET_NOT_READY

    rest = line[len(matched_token):]
    for token, _verdict in tokens:
        if token in rest:
            return VET_NOT_READY

    if not rest.startswith(separator):
        return VET_NOT_READY

    after_sep = rest[len(separator):]
    if len(after_sep) < 40:
        return VET_NOT_READY

    sha_part = after_sep[:40]
    after_sha = after_sep[40:]
    if not _SHA40_RE.match(sha_part):
        return VET_NOT_READY

    if after_sha and not after_sha.startswith(" "):
        return VET_NOT_READY

    if sha_part.lower() != head_sha.lower():
        return VET_NOT_READY

    return matched_verdict


def read_vet_verdict(body, head_sha):
    """Return (verdict, refusal) — exactly one is non-None.

    Consumers test ``verdict == VERDICT_READY`` and nothing else; every other
    value, ``VET_NOT_READY`` included, is not-ready."""
    # axis: body is not a str
    if not isinstance(body, str):
        return None, _read_refusal(REASON_VET_UNREADABLE, "body is not a string")

    arg_refusal = _validate_head_sha(head_sha)
    if arg_refusal is not None:
        return None, arg_refusal

    form, form_error = _load_vet_verdict_form()
    if form_error is not None:
        return None, _read_refusal(REASON_VET_UNREADABLE, form_error)

    separator, tokens = form

    marker = grounding_stage.REGION_MARKERS["advisor-vet"]
    scan = grounding_stage._context_scan(body)
    try:
        region_text, _line_count, _region_start_line = grounding_stage._extract_region(
            body, marker, scan, "advisor-vet",
        )
    except grounding_stage._BodyRefusal:
        # axis: more than one live advisor-vet marker
        return VET_NOT_READY, None

    # axis: no advisor-vet marker
    if region_text is None:
        return VET_NOT_READY, None

    # axis: marker present with no non-empty line after it
    line = _first_nonempty_line(region_text)
    if line is None:
        return VET_NOT_READY, None

    return _parse_vet_verdict_line(line, head_sha, separator, tokens), None


def read_membership(
    *,
    pr,
    repo,
    expect_stack=None,
    page_size=DEFAULT_PAGE_SIZE,
    timeout=GH_TIMEOUT,
    deadline=None,
    run=None,
):
    """Return the membership read dict; GitHub-side and argument-side failures return a refusal dict and raise nothing, while a violated internal pair-slot invariant raises AssertionError."""
    if run is None:
        run = subprocess.run

    arg_refusal = _validate_membership_arguments(pr, repo, expect_stack, page_size, deadline)
    if arg_refusal is not None:
        return arg_refusal

    owner, name = repo.split("/", 1)
    deadline_at = None if deadline is None else time.monotonic() + deadline

    prior_members = None
    for verification_pass in (0, 1):
        collected = []
        pages = 0
        snapshot = None
        stack_size = None
        used_cursors = set()
        after = None

        while True:
            payload, transport_refusal = _transport_graphql(
                owner, name, pr, page_size, after, timeout, run, repo, pages,
                deadline=deadline, deadline_at=deadline_at)
            # bite-axis: transport refusal is distinguished by pair slot, not payload content
            if transport_refusal is not None and payload is not None:
                raise AssertionError("_transport_graphql returned both payload and refusal")
            if transport_refusal is not None:
                return transport_refusal
            if payload is None:
                raise AssertionError("_transport_graphql returned neither payload nor refusal")

            pages += 1

            page_result, page_refusal = _parse_membership_page(
                payload, repo, pr, pages, snapshot, stack_size, collected)
            # bite-axis: page refusal is distinguished by pair slot, not page dict content
            if page_refusal is not None and page_result is not None:
                raise AssertionError("_parse_membership_page returned both page and refusal")
            if page_refusal is not None:
                return page_refusal
            if page_result is None:
                raise AssertionError("_parse_membership_page returned neither page nor refusal")

            snapshot = page_result["snapshot"]
            stack_size = page_result["stack_size"]
            has_next_page = page_result["has_next_page"]
            end_cursor = page_result["end_cursor"]
            added = page_result["added"]

            if not has_next_page:
                break

            # axis: a page adds zero nodes while hasNextPage is true
            if added == 0:
                return _refusal(REASON_STACK_UNREADABLE,
                    "page added zero nodes while hasNextPage is true", repo=repo, pr=pr, pages=pages)

            # axis: a next page requires a usable string cursor
            if not isinstance(end_cursor, str):
                return _refusal(REASON_STACK_UNREADABLE,
                    "hasNextPage is true but endCursor is null or absent",
                    repo=repo, pr=pr, pages=pages)

            # axis: endCursor repeats a cursor already used
            if end_cursor in used_cursors:
                return _refusal(REASON_STACK_UNREADABLE, "endCursor repeats a cursor already used",
                    repo=repo, pr=pr, pages=pages)

            used_cursors.add(end_cursor)
            after = end_cursor

        invariant_result = _validate_stack_invariants(
            collected,
            snapshot,
            stack_size,
            expect_stack,
            repo,
            pr,
            pages,
            prior_members,
            verification_pass,
        )
        # bite-axis: invariant outcome is distinguished by explicit tag, not result shape
        invariant_tag = invariant_result.get("tag")
        if invariant_tag == _INVARIANT_TAG_CONTINUE:
            prior_members = invariant_result["prior_members"]
            continue
        if invariant_tag == _INVARIANT_TAG_REFUSAL:
            return invariant_result["result"]
        if invariant_tag == _INVARIANT_TAG_SUCCESS:
            return invariant_result["result"]
        raise AssertionError("_validate_stack_invariants returned unknown tag: %r" % invariant_tag)


def _bad_argument_result(detail):
    return _refusal(REASON_BAD_ARGUMENT, detail, repo=None, pr=None, pages=0)


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    try:
        parser = _StackCheckParser(prog="stack_check")
        subparsers = parser.add_subparsers(dest="verb")
        list_parser = subparsers.add_parser("list")
        list_parser.add_argument("--pr", type=int, required=True)
        list_parser.add_argument("--repo", required=True)
        list_parser.add_argument("--stack", type=int, default=None)
        list_parser.add_argument("--page-size", type=int, default=DEFAULT_PAGE_SIZE)
        args = parser.parse_args(argv)
        if args.verb != "list":
            raise _ParseError("unknown or missing verb")
    except (_ParseError, SystemExit):
        # axis: the parse boundary (malformed CLI call returns bad-argument instead of argparse exit)
        result = _bad_argument_result("invalid command-line arguments")
        sys.stdout.write(json.dumps(result) + "\n")
        return 1

    result = read_membership(
        pr=args.pr,
        repo=args.repo,
        expect_stack=args.stack,
        page_size=args.page_size,
    )
    sys.stdout.write(json.dumps(result) + "\n")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
