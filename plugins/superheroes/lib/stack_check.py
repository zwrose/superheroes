#!/usr/bin/env python3
"""Read GitHub native-stack membership for a pull request via GraphQL.

Every membership answer is one complete GitHub read or a refusal — never a partial
or mixed-time picture. All validation lives in read_membership; the CLI is a thin
projection."""
import argparse
import json
import re
import shutil
import subprocess
import sys

GH_TIMEOUT = 120
DEFAULT_PAGE_SIZE = 50
MIN_PAGE_SIZE = 1
MAX_PAGE_SIZE = 100

REASON_BAD_ARGUMENT = "bad-argument"
REASON_NOT_LINKED = "not-linked"
REASON_STACK_UNREADABLE = "stack-unreadable"
REASON_ORDER_MISMATCH = "order-mismatch"

_REPO_RE = re.compile(r"^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$")

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


def _stderr(proc):
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


def read_membership(
    *,
    pr,
    repo,
    expect_stack=None,
    page_size=DEFAULT_PAGE_SIZE,
    timeout=GH_TIMEOUT,
    run=None,
):
    """Return the membership read dict. Never raises."""
    if run is None:
        run = subprocess.run

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

    owner, name = repo.split("/", 1)

    # axis: gh is not on PATH
    if not shutil.which("gh"):
        return _refusal(REASON_STACK_UNREADABLE, "gh not on PATH", repo=repo, pr=pr)

    collected = []
    pages = 0
    snapshot = None
    stack_size = None
    used_cursors = set()
    after = None

    while True:
        argv = _graphql_argv(owner, name, pr, page_size, after)
        try:
            proc = run(argv, capture_output=True, text=True, timeout=timeout)
        except (FileNotFoundError, OSError) as exc:
            # axis: run raises FileNotFoundError/OSError
            return _refusal(REASON_STACK_UNREADABLE, str(exc), repo=repo, pr=pr, pages=pages)
        except subprocess.TimeoutExpired:
            # axis: run raises subprocess.TimeoutExpired
            return _refusal(REASON_STACK_UNREADABLE, "gh call timed out", repo=repo, pr=pr, pages=pages)

        pages += 1

        # axis: gh exits non-zero
        if proc.returncode != 0:
            return _refusal(REASON_STACK_UNREADABLE, _stderr(proc) or "gh api graphql failed",
                repo=repo, pr=pr, pages=pages)

        try:
            payload = json.loads(proc.stdout or "")
        except json.JSONDecodeError:
            # axis: stdout is not JSON
            return _refusal(REASON_STACK_UNREADABLE,
                "gh api graphql returned output that is not JSON", repo=repo, pr=pr, pages=pages)

        if not isinstance(payload, dict):
            return _refusal(REASON_STACK_UNREADABLE,
                "gh api graphql returned JSON that is not an object", repo=repo, pr=pr, pages=pages)

        errors = payload.get("errors")
        if errors is None:
            errors = []
        # axis: response carries a non-empty errors array
        if not isinstance(errors, list):
            return _refusal(REASON_STACK_UNREADABLE, "gh api graphql errors is not a list",
                repo=repo, pr=pr, pages=pages)
        if errors:
            return _refusal(REASON_STACK_UNREADABLE, json.dumps(errors), repo=repo, pr=pr, pages=pages)

        data = payload.get("data")
        repository = data.get("repository") if isinstance(data, dict) else None
        # axis: data/repository is null or not an object
        if not isinstance(data, dict) or not isinstance(repository, dict):
            return _refusal(REASON_STACK_UNREADABLE,
                "graphql data/repository is null or not an object", repo=repo, pr=pr, pages=pages)

        pull_request = repository.get("pullRequest")
        # axis: pullRequest is null or not an object
        if not isinstance(pull_request, dict):
            return _refusal(REASON_STACK_UNREADABLE, "graphql pullRequest is null or not an object",
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
            return _refusal(REASON_STACK_UNREADABLE,
                "required pullRequest field is missing or of the wrong type",
                repo=repo, pr=pr, pages=pages)

        stack_entry = pull_request.get("stackEntry")
        # axis: stackEntry is null
        if stack_entry is None:
            return _refusal(REASON_NOT_LINKED,
                "pull request is not in a stack", repo=repo, pr=pr, pages=pages)

        entry_position = stack_entry.get("position") if isinstance(stack_entry, dict) else None
        # axis: stackEntry is present but not an object, or position is missing/not an int
        if not isinstance(stack_entry, dict) or not _is_int(entry_position):
            return _refusal(REASON_STACK_UNREADABLE,
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
            return _refusal(REASON_STACK_UNREADABLE, "stack field is missing or of the wrong type",
                repo=repo, pr=pr, pages=pages)

        entries = stack.get("entries")
        page_info = entries.get("pageInfo") if isinstance(entries, dict) else None
        nodes = entries.get("nodes") if isinstance(entries, dict) else None
        # axis: entries/pageInfo/nodes is missing or of the wrong type
        if not isinstance(entries, dict) or not isinstance(page_info, dict) or not isinstance(nodes, list):
            return _refusal(REASON_STACK_UNREADABLE,
                "stack entries/pageInfo/nodes is missing or of the wrong type",
                repo=repo, pr=pr, pages=pages)

        if pages == 1:
            snapshot = _snapshot_from_page(pull_request, stack_entry, stack)
            stack_size = stack_size_value
        else:
            # axis: a later page reports a different page-one snapshot value
            if not _snapshot_matches(snapshot, pull_request, stack_entry, stack):
                return _refusal(REASON_ORDER_MISMATCH,
                    "later page disagrees with page-one snapshot", repo=repo, pr=pr, pages=pages)

        added = 0
        for node in nodes:
            member, parse_err = _parse_member(node)
            if parse_err:
                # axis: a node, its position, or one of its pull-request fields is missing or wrong type
                return _refusal(REASON_STACK_UNREADABLE, parse_err, repo=repo, pr=pr, pages=pages)
            # axis: the collected count would exceed size mid-read
            if len(collected) + 1 > stack_size:
                return _refusal(REASON_STACK_UNREADABLE,
                    "collected member count would exceed stack size", repo=repo, pr=pr, pages=pages)
            collected.append(member)
            added += 1

        has_next_page = page_info.get("hasNextPage")
        if not isinstance(has_next_page, bool):
            return _refusal(REASON_STACK_UNREADABLE,
                "pageInfo hasNextPage is missing or not a boolean", repo=repo, pr=pr, pages=pages)

        end_cursor = page_info.get("endCursor")

        if not has_next_page:
            break
        if len(collected) >= stack_size:
            break

        # axis: a page adds zero nodes while hasNextPage is true
        if added == 0:
            return _refusal(REASON_STACK_UNREADABLE,
                "page added zero nodes while hasNextPage is true", repo=repo, pr=pr, pages=pages)

        # axis: hasNextPage is true with a null or absent endCursor
        if end_cursor is None:
            return _refusal(REASON_STACK_UNREADABLE,
                "hasNextPage is true but endCursor is null or absent",
                repo=repo, pr=pr, pages=pages)
        if not isinstance(end_cursor, str):
            return _refusal(REASON_STACK_UNREADABLE, "pageInfo endCursor is not a string",
                repo=repo, pr=pr, pages=pages)

        # axis: endCursor repeats a cursor already used
        if end_cursor in used_cursors:
            return _refusal(REASON_STACK_UNREADABLE, "endCursor repeats a cursor already used",
                repo=repo, pr=pr, pages=pages)

        used_cursors.add(end_cursor)
        after = end_cursor

    # axis: expect_stack was supplied and does not equal stack.number
    if expect_stack is not None and expect_stack != snapshot["stack_number"]:
        return _refusal(REASON_ORDER_MISMATCH, "expect_stack does not equal stack number",
            repo=repo, pr=pr, pages=pages)

    # axis: the collected count is not size
    if len(collected) != stack_size:
        return _refusal(REASON_ORDER_MISMATCH, "collected member count does not equal stack size",
            repo=repo, pr=pr, pages=pages)

    positions = {member["position"] for member in collected}
    expected_positions = set(range(1, stack_size + 1))
    # axis: the positions are not exactly 1..size
    if positions != expected_positions:
        return _refusal(REASON_ORDER_MISMATCH, "member positions are not exactly 1..size",
            repo=repo, pr=pr, pages=pages)

    members_at_position = [member for member in collected if member["position"] == snapshot["position"]]
    # axis: the queried pull request is not present exactly once at its reported position
    if len(members_at_position) != 1:
        return _refusal(REASON_ORDER_MISMATCH,
            "queried pull request is not present exactly once at its reported position",
            repo=repo, pr=pr, pages=pages)
    member_at_position = members_at_position[0]
    # axis: that entry's headRefName/headRefOid/baseRefName disagree with the top-level fields
    if (
        member_at_position["number"] != snapshot["pr_number"]
        or member_at_position["headRefName"] != snapshot["pr_headRefName"]
        or member_at_position["headRefOid"] != snapshot["pr_headRefOid"]
        or member_at_position["baseRefName"] != snapshot["pr_baseRefName"]
    ):
        return _refusal(REASON_ORDER_MISMATCH,
            "queried pull request entry disagrees with top-level pull request fields",
            repo=repo, pr=pr, pages=pages)

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
    return _success(repo, pr, stack, queried, members, pages)


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
