"""Fake-based units for merge_queue.py. No real gh or network — every gh call is faked.

Shapes. MEASURED (live REST, 2026-11-14, `gh api repos/zwrose/superheroes/rules/branches/main`):
a list of rows such as {"parameters": null, "type": "deletion"} and
{"parameters": {"allowed_merge_methods": [...]}, "type": "pull_request"}. MEASURED (cloud session):
the GraphQL read exits 1, stdout a JSON object with a `message` key, stderr ending "(HTTP 403)" and
containing "use the REST API". UNMEASURED (built from GitHub's REST docs text, not recorded): the
`merge_queue` row {"type": "merge_queue", "parameters": {"merge_method": "SQUASH", ...}} and the
GraphQL success bodies {"data": {"repository": {"mergeQueue": null | {"id": ...}}}}."""
import json
import math
import subprocess
from types import SimpleNamespace

import pytest

import merge_queue as mq

REPO = "owner/example"
BRANCH = "main"

RULES1 = ["gh", "api", "repos/owner/example/rules/branches/main?per_page=100&page=1"]
RULES2 = ["gh", "api", "repos/owner/example/rules/branches/main?per_page=100&page=2"]
GRAPHQL = [
    "gh", "api", "graphql",
    "-f", "query=query($owner:String!,$name:String!,$branch:String!)"
          "{repository(owner:$owner,name:$name){mergeQueue(branch:$branch){id}}}",
    "-f", "owner=owner", "-f", "name=example", "-f", "branch=main",
]

TOTAL_KEYS = {"ok", "queue", "source", "method", "reads", "reason", "detail", "repo", "branch"}

OTHER_ROWS = [
    {"parameters": None, "type": "deletion"},
    {"parameters": None, "type": "non_fast_forward"},
    {"parameters": {"allowed_merge_methods": ["merge", "squash", "rebase"]},
     "type": "pull_request"},
    {"parameters": {"strict_required_status_checks_policy": True},
     "type": "required_status_checks"},
]
QUEUE_ROW = {"type": "merge_queue", "parameters": {"merge_method": "SQUASH"}}

GQL_NO_QUEUE = json.dumps({"data": {"repository": {"mergeQueue": None}}})
GQL_QUEUE = json.dumps({"data": {"repository": {"mergeQueue": {"id": "MQ_x"}}}})


@pytest.fixture(autouse=True)
def _gh_on_path(monkeypatch):
    monkeypatch.setattr(mq.shutil, "which", lambda name: "/usr/bin/gh" if name == "gh" else None)


def _make_run(handlers):
    """Fake run keyed by argv. A list is consumed in order; its last entry then repeats."""
    calls = []
    kw_calls = []
    queues = {}
    for key, value in handlers.items():
        queues[tuple(key)] = list(value) if isinstance(value, list) else [value]

    def _run(argv, **kwargs):
        calls.append(list(argv))
        kw_calls.append(dict(kwargs))
        assert kwargs.get("capture_output") is True
        assert kwargs.get("text") is True
        key = tuple(argv)
        if key not in queues:
            raise AssertionError("unexpected gh argv: %r" % (argv,))
        queue = queues[key]
        handler = queue.pop(0) if len(queue) > 1 else queue[0]
        if isinstance(handler, Exception):
            raise handler
        return handler

    _run.kw_calls = kw_calls
    return _run, calls


def _proc(stdout="", returncode=0, stderr=""):
    return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)


def _rules(rows):
    return _proc(json.dumps(rows))


def _read(handlers, **kwargs):
    run, calls = _make_run(handlers)
    result = mq.read(repo=REPO, branch=BRANCH, run=run, **kwargs)
    assert set(result) == TOTAL_KEYS
    return result, calls, run


def _assert_fail_closed(result):
    assert result["ok"] is True
    assert result["queue"] is True
    assert result["source"] == "read-failed"
    assert result["reason"] is None


# ---- the mandatory cases ----

def test_squash_queue_in_rules_is_found_and_graphql_is_not_called():
    result, calls, _ = _read({tuple(RULES1): _rules(OTHER_ROWS + [QUEUE_ROW])})
    assert result == {
        "ok": True, "queue": True, "source": "rules", "method": "squash",
        "reads": {"rules": "ok", "graphql": "skipped"},
        "reason": None, "detail": None, "repo": REPO, "branch": BRANCH,
    }
    assert calls == [RULES1]


def test_no_queue_when_both_reads_succeed_and_say_none():
    result, calls, run = _read({tuple(RULES1): _rules(OTHER_ROWS),
                                tuple(GRAPHQL): _proc(GQL_NO_QUEUE)})
    assert result == {
        "ok": True, "queue": False, "source": "none", "method": None,
        "reads": {"rules": "ok", "graphql": "ok"},
        "reason": None, "detail": None, "repo": REPO, "branch": BRANCH,
    }
    assert calls == [RULES1, GRAPHQL]
    assert [kw["timeout"] for kw in run.kw_calls] == [mq.GH_TIMEOUT, mq.GH_TIMEOUT]


def test_classic_protection_queue_is_caught_by_graphql():
    result, calls, _ = _read({tuple(RULES1): _rules(OTHER_ROWS),
                              tuple(GRAPHQL): _proc(GQL_QUEUE)})
    assert result == {
        "ok": True, "queue": True, "source": "graphql", "method": None,
        "reads": {"rules": "ok", "graphql": "ok"},
        "reason": None, "detail": None, "repo": REPO, "branch": BRANCH,
    }
    assert calls == [RULES1, GRAPHQL]


def test_two_pages_of_rules_the_queue_row_on_page_two_is_found():
    page1 = [{"parameters": None, "type": "deletion"}] * 100
    result, calls, _ = _read({tuple(RULES1): _rules(page1),
                              tuple(RULES2): _rules([QUEUE_ROW])})
    assert result["queue"] is True
    assert result["source"] == "rules"
    assert result["method"] == "squash"
    assert calls == [RULES1, RULES2]


def test_two_pages_of_rules_with_no_queue_row_reads_both_pages_then_graphql():
    page1 = [{"parameters": None, "type": "deletion"}] * 100
    result, calls, _ = _read({tuple(RULES1): _rules(page1),
                              tuple(RULES2): _rules(OTHER_ROWS),
                              tuple(GRAPHQL): _proc(GQL_NO_QUEUE)})
    assert result["queue"] is False
    assert calls == [RULES1, RULES2, GRAPHQL]


def test_a_second_rules_page_that_fails_fails_the_rules_read():
    page1 = [{"parameters": None, "type": "deletion"}] * 100
    result, calls, _ = _read({tuple(RULES1): _rules(page1),
                              tuple(RULES2): _proc("", 1, "gh: boom"),
                              tuple(GRAPHQL): _proc(GQL_NO_QUEUE)})
    _assert_fail_closed(result)
    assert result["reads"] == {"rules": "failed", "graphql": "ok"}
    assert "gh: boom" in result["detail"]


# ---- method ----

@pytest.mark.parametrize("raw,expected", [
    ("SQUASH", "squash"), ("MERGE", "merge"), ("REBASE", "rebase"), ("squash", "squash"),
])
def test_method_is_reported_lower_cased(raw, expected):
    row = {"type": "merge_queue", "parameters": {"merge_method": raw}}
    result, _, _ = _read({tuple(RULES1): _rules([row])})
    assert result["method"] == expected


@pytest.mark.parametrize("row", [
    {"type": "merge_queue", "parameters": None},
    {"type": "merge_queue"},
    {"type": "merge_queue", "parameters": {}},
    {"type": "merge_queue", "parameters": {"merge_method": 5}},
    {"type": "merge_queue", "parameters": ["x"]},
])
def test_a_queue_row_without_a_string_method_is_a_queue_with_method_null(row):
    result, calls, _ = _read({tuple(RULES1): _rules([row])})
    assert result["queue"] is True
    assert result["source"] == "rules"
    assert result["method"] is None
    assert calls == [RULES1]


# ---- the branch is percent-quoted into the rules path ----

def test_branch_is_percent_quoted_with_slashes_kept():
    branch = "release/1.0#x?y"
    page = ["gh", "api", "repos/owner/example/rules/branches/release/1.0%23x%3Fy"
                         "?per_page=100&page=1"]
    graphql = GRAPHQL[:-1] + ["branch=" + branch]
    run, calls = _make_run({tuple(page): _rules([]), tuple(graphql): _proc(GQL_NO_QUEUE)})
    result = mq.read(repo=REPO, branch=branch, run=run)
    assert result["queue"] is False
    assert calls == [page, graphql]


# ---- E1: a rules page cannot be read (gh exit non-zero) ----

def test_e1_rules_exit_nonzero_is_read_failed_even_with_a_list_on_stdout():
    result, calls, _ = _read({tuple(RULES1): _proc("[]", 1, "gh: Not Found (HTTP 404)"),
                              tuple(GRAPHQL): _proc(GQL_NO_QUEUE)})
    _assert_fail_closed(result)
    assert result["reads"] == {"rules": "failed", "graphql": "ok"}
    assert "rules read failed" in result["detail"]
    assert "HTTP 404" in result["detail"]
    assert calls == [RULES1, GRAPHQL]


def test_e1_rules_failed_but_graphql_finds_a_queue_reports_graphql():
    result, calls, _ = _read({tuple(RULES1): _proc("", 1, "gh: boom"),
                              tuple(GRAPHQL): _proc(GQL_QUEUE)})
    assert result["ok"] is True
    assert result["queue"] is True
    assert result["source"] == "graphql"
    assert result["method"] is None
    assert result["reads"] == {"rules": "failed", "graphql": "ok"}
    assert "rules read failed" in result["detail"]
    assert calls == [RULES1, GRAPHQL]


def test_e1_both_reads_failed_names_both():
    result, _, _ = _read({tuple(RULES1): _proc("", 1, "gh: boom"),
                          tuple(GRAPHQL): _proc("", 1, "gh: bang")})
    _assert_fail_closed(result)
    assert result["reads"] == {"rules": "failed", "graphql": "failed"}
    assert "rules read failed" in result["detail"]
    assert "graphql read failed" in result["detail"]


def test_graphql_failed_after_a_clean_rules_read_is_read_failed():
    result, _, _ = _read({tuple(RULES1): _rules(OTHER_ROWS),
                          tuple(GRAPHQL): _proc("", 1, "gh: bang")})
    _assert_fail_closed(result)
    assert result["reads"] == {"rules": "ok", "graphql": "failed"}
    assert "graphql read failed" in result["detail"]
    assert "rules read failed" not in result["detail"]


# ---- E2: a rules page is not JSON or not a list ----

@pytest.mark.parametrize("stdout", ["not json", "", '{"message": "x"}', "null", "5"])
def test_e2_rules_page_not_a_json_list_is_read_failed(stdout):
    result, calls, _ = _read({tuple(RULES1): _proc(stdout),
                              tuple(GRAPHQL): _proc(GQL_NO_QUEUE)})
    _assert_fail_closed(result)
    assert result["reads"] == {"rules": "failed", "graphql": "ok"}
    assert "not a JSON list" in result["detail"]
    assert calls == [RULES1, GRAPHQL]


# ---- E3: a row that is not a dict or has no string type ----

@pytest.mark.parametrize("rows", [
    ["merge_queue"],
    [None],
    [5],
    [[{"type": "merge_queue"}]],
    [{}],
    [{"parameters": None}],
    [{"type": 5}],
    [{"type": None}],
    [{"type": "deletion"}, "oops"],
])
def test_e3_malformed_rules_row_is_read_failed(rows):
    result, _, _ = _read({tuple(RULES1): _rules(rows), tuple(GRAPHQL): _proc(GQL_NO_QUEUE)})
    _assert_fail_closed(result)
    assert result["reads"] == {"rules": "failed", "graphql": "ok"}
    assert "string type" in result["detail"]


# ---- E4: GraphQL exits non-zero ----

def test_e4_cloud_proxy_graphql_refusal_is_read_failed_with_the_refusal_in_the_detail():
    refusal = _proc(
        json.dumps({"message": "GraphQL is not available", "documentation_url": "x"}), 1,
        "gh: GraphQL is blocked here, use the REST API instead (HTTP 403)")
    result, calls, _ = _read({tuple(RULES1): _rules(OTHER_ROWS), tuple(GRAPHQL): refusal})
    _assert_fail_closed(result)
    assert result["reads"] == {"rules": "ok", "graphql": "failed"}
    assert "(HTTP 403)" in result["detail"]
    assert "use the REST API" in result["detail"]
    assert calls == [RULES1, GRAPHQL]


def test_e4_graphql_exit_nonzero_with_a_no_queue_body_is_still_read_failed():
    result, _, _ = _read({tuple(RULES1): _rules(OTHER_ROWS),
                          tuple(GRAPHQL): _proc(GQL_NO_QUEUE, 1, "gh: exit")})
    _assert_fail_closed(result)
    assert result["reads"] == {"rules": "ok", "graphql": "failed"}


# ---- E5: GraphQL stdout is not a JSON object ----

@pytest.mark.parametrize("stdout", ["not json", "", "[]", "null", "5"])
def test_e5_graphql_stdout_not_a_json_object_is_read_failed(stdout):
    result, _, _ = _read({tuple(RULES1): _rules(OTHER_ROWS), tuple(GRAPHQL): _proc(stdout)})
    _assert_fail_closed(result)
    assert result["reads"] == {"rules": "ok", "graphql": "failed"}
    assert "not a JSON object" in result["detail"]


# ---- E6: GraphQL errors non-empty ----

@pytest.mark.parametrize("errors", [[{"message": "boom"}], "boom", {"message": "boom"}])
def test_e6_graphql_errors_is_read_failed_even_beside_a_no_queue_data(errors):
    body = {"data": {"repository": {"mergeQueue": None}}, "errors": errors}
    result, _, _ = _read({tuple(RULES1): _rules(OTHER_ROWS),
                          tuple(GRAPHQL): _proc(json.dumps(body))})
    _assert_fail_closed(result)
    assert result["reads"] == {"rules": "ok", "graphql": "failed"}
    assert "errors" in result["detail"]


@pytest.mark.parametrize("errors", [[], None])
def test_e6_an_empty_or_null_errors_key_does_not_fail_the_read(errors):
    body = {"data": {"repository": {"mergeQueue": None}}, "errors": errors}
    result, _, _ = _read({tuple(RULES1): _rules(OTHER_ROWS),
                          tuple(GRAPHQL): _proc(json.dumps(body))})
    assert result["queue"] is False
    assert result["source"] == "none"


# ---- E7: data.repository null or missing ----

@pytest.mark.parametrize("body", [
    {},
    {"data": None},
    {"data": []},
    {"data": {}},
    {"data": {"repository": None}},
    {"data": {"repository": []}},
    {"data": {"repository": "x"}},
])
def test_e7_missing_or_null_repository_is_read_failed(body):
    result, _, _ = _read({tuple(RULES1): _rules(OTHER_ROWS),
                          tuple(GRAPHQL): _proc(json.dumps(body))})
    _assert_fail_closed(result)
    assert result["reads"] == {"rules": "ok", "graphql": "failed"}
    assert "data.repository" in result["detail"]


# ---- E8: the mergeQueue key is absent (or neither null nor an object) ----

def test_e8_mergequeue_key_absent_is_read_failed():
    body = {"data": {"repository": {"id": "R_x"}}}
    result, _, _ = _read({tuple(RULES1): _rules(OTHER_ROWS),
                          tuple(GRAPHQL): _proc(json.dumps(body))})
    _assert_fail_closed(result)
    assert result["reads"] == {"rules": "ok", "graphql": "failed"}
    assert "mergeQueue" in result["detail"]


@pytest.mark.parametrize("value", ["MQ_x", [], 5, True, False])
def test_e8_mergequeue_neither_null_nor_object_is_read_failed(value):
    body = {"data": {"repository": {"mergeQueue": value}}}
    result, _, _ = _read({tuple(RULES1): _rules(OTHER_ROWS),
                          tuple(GRAPHQL): _proc(json.dumps(body))})
    _assert_fail_closed(result)
    assert result["reads"] == {"rules": "ok", "graphql": "failed"}


# ---- E9: run raises OSError or TimeoutExpired ----

RAISERS = [
    pytest.param(OSError("no gh"), id="oserror"),
    pytest.param(FileNotFoundError("gh"), id="filenotfound"),
    pytest.param(subprocess.TimeoutExpired(["gh"], 5), id="timeout"),
]


@pytest.mark.parametrize("exc", RAISERS)
def test_e9_run_raising_on_the_rules_read_is_read_failed(exc):
    result, calls, _ = _read({tuple(RULES1): exc, tuple(GRAPHQL): _proc(GQL_NO_QUEUE)})
    _assert_fail_closed(result)
    assert result["reads"] == {"rules": "failed", "graphql": "ok"}
    assert "rules read failed: gh call failed" in result["detail"]
    assert calls == [RULES1, GRAPHQL]


@pytest.mark.parametrize("exc", RAISERS)
def test_e9_run_raising_on_the_graphql_read_is_read_failed(exc):
    result, _, _ = _read({tuple(RULES1): _rules(OTHER_ROWS), tuple(GRAPHQL): exc})
    _assert_fail_closed(result)
    assert result["reads"] == {"rules": "ok", "graphql": "failed"}
    assert "graphql read failed: gh call failed" in result["detail"]


# ---- E10: the deadline ----

def test_e10_deadline_already_passed_makes_no_call_and_fails_closed():
    run, calls = _make_run({})
    result = mq.read(repo=REPO, branch=BRANCH, run=run, deadline_at=10.0,
                     monotonic=lambda: 10.0)
    assert set(result) == TOTAL_KEYS
    _assert_fail_closed(result)
    assert result["reads"] == {"rules": "failed", "graphql": "failed"}
    assert "time budget" in result["detail"]
    assert calls == []


def test_e10_deadline_passing_between_the_reads_makes_no_graphql_call():
    ticks = iter([0.0, 100.0])
    run, calls = _make_run({tuple(RULES1): _rules(OTHER_ROWS)})
    result = mq.read(repo=REPO, branch=BRANCH, run=run, deadline_at=50.0,
                     monotonic=lambda: next(ticks))
    _assert_fail_closed(result)
    assert result["reads"] == {"rules": "ok", "graphql": "failed"}
    assert "graphql read failed" in result["detail"]
    assert "time budget" in result["detail"]
    assert calls == [RULES1]


@pytest.mark.parametrize("timeout,deadline_at,expected", [
    (120, 10.0, 10.0),
    (3, 10.0, 3),
    (120, 1000.0, 120),
])
def test_e10_each_calls_timeout_is_the_smaller_of_timeout_and_the_time_left(
        timeout, deadline_at, expected):
    result, _, run = _read({tuple(RULES1): _rules(OTHER_ROWS),
                            tuple(GRAPHQL): _proc(GQL_NO_QUEUE)},
                           timeout=timeout, deadline_at=deadline_at, monotonic=lambda: 0.0)
    assert result["queue"] is False
    assert [kw["timeout"] for kw in run.kw_calls] == [expected, expected]


# ---- E11: gh is not on PATH ----

def test_e11_gh_not_on_path_fails_closed_with_no_call(monkeypatch):
    monkeypatch.setattr(mq.shutil, "which", lambda name: None)
    result, calls, _ = _read({})
    _assert_fail_closed(result)
    assert result["reads"] == {"rules": "failed", "graphql": "failed"}
    assert result["detail"] == "gh not on PATH"
    assert calls == []


# ---- E12: each bad-argument axis ----

def _assert_bad_argument(result):
    assert set(result) == TOTAL_KEYS
    assert result["ok"] is False
    assert result["queue"] is None
    assert result["source"] is None
    assert result["method"] is None
    assert result["reads"] is None
    assert result["reason"] == "bad-argument"
    assert isinstance(result["detail"], str)
    assert result["repo"] is None
    assert result["branch"] is None


@pytest.mark.parametrize("repo", [None, 5, "owner", "owner/", "/name", "o/n/x", "own er/name",
                                  "o/n\n", ""])
def test_e12_bad_repo(repo):
    run, calls = _make_run({})
    _assert_bad_argument(mq.read(repo=repo, branch=BRANCH, run=run))
    assert calls == []


@pytest.mark.parametrize("branch", [None, 5, "", "a b", "a\tb", "a\nb", "main\n", "a\x00b",
                                    "a\x7fb", "a\x85b"])
def test_e12_bad_branch(branch):
    run, calls = _make_run({})
    _assert_bad_argument(mq.read(repo=REPO, branch=branch, run=run))
    assert calls == []


@pytest.mark.parametrize("timeout", [0, -3, True, "5", None, math.nan, math.inf])
def test_e12_bad_timeout(timeout):
    run, calls = _make_run({})
    _assert_bad_argument(mq.read(repo=REPO, branch=BRANCH, timeout=timeout, run=run))
    assert calls == []


@pytest.mark.parametrize("deadline_at", [True, "5", math.nan, math.inf, -math.inf, [1]])
def test_e12_bad_deadline_at(deadline_at):
    run, calls = _make_run({})
    _assert_bad_argument(mq.read(repo=REPO, branch=BRANCH, deadline_at=deadline_at, run=run))
    assert calls == []


def test_e12_bad_argument_comes_before_the_gh_check(monkeypatch):
    monkeypatch.setattr(mq.shutil, "which", lambda name: None)
    _assert_bad_argument(mq.read(repo="nope", branch=BRANCH, run=_make_run({})[0]))


# ---- the invariant: queue false only on two successful no-queue reads ----

def test_queue_false_is_answered_only_when_both_reads_succeed_and_say_none():
    outcomes = {}
    rules_cases = {
        "none": _rules(OTHER_ROWS),
        "queue": _rules([QUEUE_ROW]),
        "failed": _proc("", 1, "gh: boom"),
    }
    graphql_cases = {
        "none": _proc(GQL_NO_QUEUE),
        "queue": _proc(GQL_QUEUE),
        "failed": _proc("", 1, "gh: bang"),
    }
    for rules_key, rules_proc in rules_cases.items():
        for graphql_key, graphql_proc in graphql_cases.items():
            result, _, _ = _read({tuple(RULES1): rules_proc, tuple(GRAPHQL): graphql_proc})
            outcomes[(rules_key, graphql_key)] = result["queue"]
    assert [key for key, queue in outcomes.items() if queue is False] == [("none", "none")]
    assert all(queue is True for key, queue in outcomes.items() if key != ("none", "none"))


# ---- CLI ----

def test_cli_round_trip_prints_one_json_line_and_exits_zero(capsys):
    run, calls = _make_run({tuple(RULES1): _rules(OTHER_ROWS + [QUEUE_ROW])})
    code = mq.main(["read", "--repo", REPO, "--branch", BRANCH], run=run)
    out = capsys.readouterr().out
    assert code == 0
    assert out.endswith("\n") and out.count("\n") == 1
    assert json.loads(out) == {
        "ok": True, "queue": True, "source": "rules", "method": "squash",
        "reads": {"rules": "ok", "graphql": "skipped"},
        "reason": None, "detail": None, "repo": REPO, "branch": BRANCH,
    }
    assert calls == [RULES1]


def test_cli_no_queue_round_trip(capsys):
    run, _ = _make_run({tuple(RULES1): _rules(OTHER_ROWS), tuple(GRAPHQL): _proc(GQL_NO_QUEUE)})
    code = mq.main(["read", "--repo", REPO, "--branch", BRANCH], run=run)
    body = json.loads(capsys.readouterr().out)
    assert code == 0
    assert body["queue"] is False
    assert body["source"] == "none"


def test_cli_read_failed_still_exits_zero_with_queue_true(capsys):
    run, _ = _make_run({tuple(RULES1): _proc("", 1, "gh: boom"),
                        tuple(GRAPHQL): _proc("", 1, "gh: bang")})
    code = mq.main(["read", "--repo", REPO, "--branch", BRANCH], run=run)
    body = json.loads(capsys.readouterr().out)
    assert code == 0
    assert body["queue"] is True
    assert body["source"] == "read-failed"


def test_cli_bad_argument_value_exits_one(capsys):
    run, calls = _make_run({})
    code = mq.main(["read", "--repo", "nope", "--branch", BRANCH], run=run)
    body = json.loads(capsys.readouterr().out)
    assert code == 1
    _assert_bad_argument(body)
    assert calls == []


@pytest.mark.parametrize("argv", [
    [],
    ["read"],
    ["read", "--repo", REPO],
    ["read", "--branch", BRANCH],
    ["write", "--repo", REPO, "--branch", BRANCH],
    ["read", "--repo", REPO, "--branch", BRANCH, "--nope", "1"],
    ["--help"],
    ["read", "--help"],
])
def test_cli_malformed_is_bad_argument_json_exit_one(argv, capsys):
    run, calls = _make_run({})
    code = mq.main(argv, run=run)
    out = capsys.readouterr().out
    assert code == 1
    assert out.count("\n") == 1
    _assert_bad_argument(json.loads(out))
    assert calls == []
