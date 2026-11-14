"""Fake-based units for `merge_queue.slots` (issue 2480). No real gh or network: every gh call is faked.

Shapes and their provenance.
MEASURED (cloud session, recorded in test_merge_queue.py's docstring): the GraphQL call exits 1,
stdout a JSON object with a `message` key, stderr ending "(HTTP 403)" and containing "use the REST
API". Used for the gh-non-zero case of the GraphQL read.
MEASURED (live REST on this repository's main, recorded in the same docstring): ordinary rules rows
such as {"parameters": null, "type": "deletion"}.
UNMEASURED (built from GitHub's REST docs, repository rules page, fetched 2026-11-14, not recorded
from a live call): the rules row {"type": "merge_queue", "parameters": {"merge_method": "SQUASH",
"max_entries_to_build": 5, ...}}, where `max_entries_to_build` is required, an integer, minimum 0,
maximum 100.
UNMEASURED (built from GitHub's published schema, docs.github.com/public/fpt/schema.docs.graphql,
fetched 2026-11-14, not recorded from a live call): the GraphQL success bodies
{"data": {"repository": {"mergeQueue": null}}} and
{"data": {"repository": {"mergeQueue": {"configuration": {"maximumEntriesToBuild": 5},
"entries": {"totalCount": 2}}}}}, from MergeQueue.configuration: MergeQueueConfiguration,
MergeQueueConfiguration.maximumEntriesToBuild: Int, MergeQueue.entries(first: Int):
MergeQueueEntryConnection and MergeQueueEntryConnection.totalCount: Int!."""
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
SLOTS_GRAPHQL = [
    "gh", "api", "graphql",
    "-f", "query=query($owner:String!,$name:String!,$branch:String!)"
          "{repository(owner:$owner,name:$name){mergeQueue(branch:$branch)"
          "{configuration{maximumEntriesToBuild} entries(first:1){totalCount}}}}",
    "-f", "owner=owner", "-f", "name=example", "-f", "branch=main",
]
READ_GRAPHQL = [
    "gh", "api", "graphql",
    "-f", "query=query($owner:String!,$name:String!,$branch:String!)"
          "{repository(owner:$owner,name:$name){mergeQueue(branch:$branch){id}}}",
    "-f", "owner=owner", "-f", "name=example", "-f", "branch=main",
]

SLOTS_KEYS = {"ok", "fits", "queue", "limit", "queued", "free", "layers", "reads", "reason",
              "detail", "repo", "branch"}
READ_KEYS = {"ok", "queue", "source", "method", "reads", "reason", "detail", "repo", "branch"}

OTHER_ROWS = [
    {"parameters": None, "type": "deletion"},
    {"parameters": None, "type": "non_fast_forward"},
    {"parameters": {"allowed_merge_methods": ["merge", "squash", "rebase"]},
     "type": "pull_request"},
]
FILLER_PAGE = [{"parameters": None, "type": "deletion"}] * 100


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


def _row(limit):
    return {"type": "merge_queue",
            "parameters": {"merge_method": "SQUASH", "max_entries_to_build": limit}}


def _gql_body(merge_queue):
    return _proc(json.dumps({"data": {"repository": {"mergeQueue": merge_queue}}}))


def _gql(limit, queued):
    return _gql_body({"configuration": {"maximumEntriesToBuild": limit},
                      "entries": {"totalCount": queued}})


GQL_NO_QUEUE = _gql_body(None)

CLOUD_REFUSAL = _proc(
    json.dumps({"message": "GraphQL is not available", "documentation_url": "x"}), 1,
    "gh: GraphQL is blocked here, use the REST API instead (HTTP 403)")

RAISERS = [
    pytest.param(OSError("no gh"), id="oserror"),
    pytest.param(FileNotFoundError("gh"), id="filenotfound"),
    pytest.param(subprocess.TimeoutExpired(["gh"], 5), id="timeout"),
]


def _slots(handlers, layers=3, **kwargs):
    run, calls = _make_run(handlers)
    result = mq.slots(repo=REPO, branch=BRANCH, layers=layers, run=run, **kwargs)
    assert set(result) == SLOTS_KEYS
    return result, calls, run


def _assert_unreadable(result, queue=None):
    assert result["ok"] is True
    assert result["fits"] is False
    assert result["reason"] == "slots-unreadable"
    assert result["queue"] is queue
    assert isinstance(result["detail"], str)


def _assert_bad_argument(result):
    assert set(result) == SLOTS_KEYS
    assert result["ok"] is False
    assert result["fits"] is False
    assert result["reason"] == "bad-argument"
    assert isinstance(result["detail"], str)
    for key in ("queue", "limit", "queued", "free", "layers", "reads", "repo", "branch"):
        assert result[key] is None


# ---- the decisions ----

def test_d1_classic_protection_queue_with_room_fits():
    result, calls, run = _slots({tuple(RULES1): _rules(OTHER_ROWS),
                                 tuple(SLOTS_GRAPHQL): _gql(5, 2)}, layers=3)
    assert result == {
        "ok": True, "fits": True, "queue": True, "limit": 5, "queued": 2, "free": 3,
        "layers": 3, "reads": {"rules": "ok", "graphql": "ok"}, "reason": None,
        "detail": None, "repo": REPO, "branch": BRANCH,
    }
    assert calls == [RULES1, SLOTS_GRAPHQL]
    assert [kw["timeout"] for kw in run.kw_calls] == [mq.GH_TIMEOUT, mq.GH_TIMEOUT]


def test_d2_classic_protection_queue_one_slot_short():
    result, _, _ = _slots({tuple(RULES1): _rules(OTHER_ROWS),
                           tuple(SLOTS_GRAPHQL): _gql(5, 3)}, layers=3)
    detail = result.pop("detail")
    assert result == {
        "ok": True, "fits": False, "queue": True, "limit": 5, "queued": 3, "free": 2,
        "layers": 3, "reads": {"rules": "ok", "graphql": "ok"}, "reason": "slots-short",
        "repo": REPO, "branch": BRANCH,
    }
    # The detail says why with the numbers; its wording is free to change.
    assert isinstance(detail, str)
    for number in ("5", "3", "2"):
        assert number in detail


def test_d3_ruleset_queue_exact_boundary_fits():
    result, calls, _ = _slots({tuple(RULES1): _rules(OTHER_ROWS + [_row(5)]),
                               tuple(SLOTS_GRAPHQL): _gql(5, 0)}, layers=5)
    assert result["fits"] is True
    assert result["reason"] is None
    assert result["detail"] is None
    assert result["queue"] is True
    assert (result["limit"], result["queued"], result["free"]) == (5, 0, 5)
    assert calls == [RULES1, SLOTS_GRAPHQL]


def test_d4_ruleset_queue_one_entry_inside_the_boundary_is_short():
    result, _, _ = _slots({tuple(RULES1): _rules(OTHER_ROWS + [_row(5)]),
                           tuple(SLOTS_GRAPHQL): _gql(5, 1)}, layers=5)
    assert result["fits"] is False
    assert result["reason"] == "slots-short"
    assert result["queue"] is True
    assert (result["limit"], result["queued"], result["free"]) == (5, 1, 4)


def test_d5_limit_zero_can_never_fit_one_layer():
    result, _, _ = _slots({tuple(RULES1): _rules(OTHER_ROWS),
                           tuple(SLOTS_GRAPHQL): _gql(0, 0)}, layers=1)
    assert result["fits"] is False
    assert result["reason"] == "slots-never-fits"
    assert (result["limit"], result["queued"], result["free"]) == (0, 0, 0)


def test_more_layers_than_the_build_limit_can_never_fit_even_on_an_empty_queue():
    result, _, _ = _slots({tuple(RULES1): _rules(OTHER_ROWS),
                           tuple(SLOTS_GRAPHQL): _gql(5, 0)}, layers=6)
    assert result["ok"] is True
    assert result["fits"] is False
    assert result["reason"] == "slots-never-fits"
    assert result["queue"] is True
    assert (result["limit"], result["queued"], result["free"], result["layers"]) == (5, 0, 5, 6)
    assert "owner" in result["detail"]


def test_layers_equal_to_the_build_limit_on_an_empty_queue_fits():
    result, _, _ = _slots({tuple(RULES1): _rules(OTHER_ROWS),
                           tuple(SLOTS_GRAPHQL): _gql(5, 0)}, layers=5)
    assert result["fits"] is True
    assert result["reason"] is None


def test_more_layers_than_the_limit_on_a_busy_queue_is_never_fits_not_short():
    result, _, _ = _slots({tuple(RULES1): _rules(OTHER_ROWS + [_row(5)]),
                           tuple(SLOTS_GRAPHQL): _gql(5, 3)}, layers=6)
    assert result["reason"] == "slots-never-fits"


def test_the_slots_cli_exits_one_on_never_fits(monkeypatch, capsys):
    run, _ = _make_run({tuple(RULES1): _rules(OTHER_ROWS), tuple(SLOTS_GRAPHQL): _gql(5, 0)})
    code = mq.main(["slots", "--repo", REPO, "--branch", BRANCH, "--layers", "6"], run=run)
    answer = json.loads(capsys.readouterr().out)
    assert code == 1
    assert answer["reason"] == "slots-never-fits"


def test_d6_queued_above_the_limit_is_short_with_negative_free():
    result, _, _ = _slots({tuple(RULES1): _rules(OTHER_ROWS),
                           tuple(SLOTS_GRAPHQL): _gql(5, 7)}, layers=1)
    assert result["fits"] is False
    assert result["reason"] == "slots-short"
    assert (result["limit"], result["queued"], result["free"]) == (5, 7, -2)


def test_d7_both_reads_no_queue_fits_with_no_numbers():
    result, calls, _ = _slots({tuple(RULES1): _rules(OTHER_ROWS),
                               tuple(SLOTS_GRAPHQL): GQL_NO_QUEUE}, layers=4)
    assert result == {
        "ok": True, "fits": True, "queue": False, "limit": None, "queued": None, "free": None,
        "layers": 4, "reads": {"rules": "ok", "graphql": "ok"}, "reason": None,
        "detail": None, "repo": REPO, "branch": BRANCH,
    }
    assert calls == [RULES1, SLOTS_GRAPHQL]


def test_d8_queue_row_on_rules_page_two_is_found_and_its_limit_checked():
    handlers_match = {tuple(RULES1): _rules(FILLER_PAGE),
                      tuple(RULES2): _rules([_row(5)]),
                      tuple(SLOTS_GRAPHQL): _gql(5, 0)}
    result, calls, _ = _slots(handlers_match, layers=2)
    assert result["fits"] is True
    assert result["queue"] is True
    assert calls == [RULES1, RULES2, SLOTS_GRAPHQL]

    handlers_differ = {tuple(RULES1): _rules(FILLER_PAGE),
                       tuple(RULES2): _rules([_row(7)]),
                       tuple(SLOTS_GRAPHQL): _gql(5, 0)}
    result, _, _ = _slots(handlers_differ, layers=2)
    _assert_unreadable(result, queue=True)
    assert "differs" in result["detail"]


def test_a_rules_row_beside_a_null_graphql_queue_is_not_a_no_queue_answer_on_page_two():
    # D7 holds only when no page carries a merge_queue row.
    result, _, _ = _slots({tuple(RULES1): _rules(FILLER_PAGE),
                           tuple(RULES2): _rules([_row(5)]),
                           tuple(SLOTS_GRAPHQL): GQL_NO_QUEUE})
    _assert_unreadable(result, queue=True)


def test_the_branch_is_percent_quoted_into_the_rules_path_slashes_kept():
    branch = "release/1.0#x?y"
    page = ["gh", "api", "repos/owner/example/rules/branches/release/1.0%23x%3Fy"
                         "?per_page=100&page=1"]
    graphql = SLOTS_GRAPHQL[:-1] + ["branch=" + branch]
    run, calls = _make_run({tuple(page): _rules([]), tuple(graphql): GQL_NO_QUEUE})
    result = mq.slots(repo=REPO, branch=branch, layers=2, run=run)
    assert result["fits"] is True
    assert result["queue"] is False
    assert calls == [page, graphql]


# ---- E1 to E5: bad arguments ----

@pytest.mark.parametrize("repo", [None, 5, "owner", "owner/", "/name", "o/n/x", "own er/name",
                                  "o/n\n", ""])
def test_e1_bad_repo(repo):
    run, calls = _make_run({})
    _assert_bad_argument(mq.slots(repo=repo, branch=BRANCH, layers=2, run=run))
    assert calls == []


@pytest.mark.parametrize("branch", [None, 5, "", "a b", "a\tb", "a\nb", "main\n", "a\x00b",
                                    "a\x7fb", "a\x85b"])
def test_e2_bad_branch(branch):
    run, calls = _make_run({})
    _assert_bad_argument(mq.slots(repo=REPO, branch=branch, layers=2, run=run))
    assert calls == []


@pytest.mark.parametrize("timeout", [0, -3, True, "5", None, math.nan, math.inf])
def test_e3_bad_timeout(timeout):
    run, calls = _make_run({})
    _assert_bad_argument(mq.slots(repo=REPO, branch=BRANCH, layers=2, timeout=timeout, run=run))
    assert calls == []


@pytest.mark.parametrize("deadline_at", [True, "5", math.nan, math.inf, -math.inf, [1]])
def test_e4_bad_deadline_at(deadline_at):
    run, calls = _make_run({})
    _assert_bad_argument(mq.slots(repo=REPO, branch=BRANCH, layers=2, deadline_at=deadline_at,
                                  run=run))
    assert calls == []


@pytest.mark.parametrize("layers", [None, "3", 3.0, True, False, 0, -1, [3], {"n": 3}])
def test_e5_bad_layers(layers):
    run, calls = _make_run({})
    _assert_bad_argument(mq.slots(repo=REPO, branch=BRANCH, layers=layers, run=run))
    assert calls == []


def test_bad_argument_comes_before_the_gh_check(monkeypatch):
    monkeypatch.setattr(mq.shutil, "which", lambda name: None)
    _assert_bad_argument(mq.slots(repo="nope", branch=BRANCH, layers=2, run=_make_run({})[0]))
    _assert_bad_argument(mq.slots(repo=REPO, branch=BRANCH, layers=0, run=_make_run({})[0]))


# ---- E6: gh is not on PATH ----

def test_e6_gh_not_on_path_does_not_fit_and_makes_no_call(monkeypatch):
    monkeypatch.setattr(mq.shutil, "which", lambda name: None)
    result, calls, _ = _slots({})
    _assert_unreadable(result)
    assert result["reads"] == {"rules": "failed", "graphql": "failed"}
    assert "gh" in result["detail"]
    assert (result["limit"], result["queued"], result["free"]) == (None, None, None)
    assert result["layers"] == 3
    assert calls == []


# ---- E7: a rules page fails or is not a JSON list ----

@pytest.mark.parametrize("graphql", [GQL_NO_QUEUE, _gql(5, 0)], ids=["null-queue", "queue"])
def test_e7_rules_exit_nonzero_does_not_fit_even_with_a_list_on_stdout(graphql):
    result, calls, _ = _slots({tuple(RULES1): _proc("[]", 1, "gh: Not Found (HTTP 404)"),
                               tuple(SLOTS_GRAPHQL): graphql})
    _assert_unreadable(result, queue=None if graphql is GQL_NO_QUEUE else True)
    assert result["reads"] == {"rules": "failed", "graphql": "ok"}
    assert "rules read failed" in result["detail"]
    assert "HTTP 404" in result["detail"]
    assert calls == [RULES1, SLOTS_GRAPHQL]


@pytest.mark.parametrize("exc", RAISERS)
def test_e7_rules_run_raising_does_not_fit(exc):
    result, calls, _ = _slots({tuple(RULES1): exc, tuple(SLOTS_GRAPHQL): GQL_NO_QUEUE})
    _assert_unreadable(result)
    assert result["reads"] == {"rules": "failed", "graphql": "ok"}
    assert "rules read failed: gh call failed" in result["detail"]
    assert calls == [RULES1, SLOTS_GRAPHQL]


@pytest.mark.parametrize("stdout", ["not json", "", '{"message": "x"}', "null", "5"])
def test_e7_rules_page_not_a_json_list_does_not_fit(stdout):
    result, calls, _ = _slots({tuple(RULES1): _proc(stdout),
                               tuple(SLOTS_GRAPHQL): GQL_NO_QUEUE})
    _assert_unreadable(result)
    assert result["reads"] == {"rules": "failed", "graphql": "ok"}
    assert "not a JSON list" in result["detail"]
    assert calls == [RULES1, SLOTS_GRAPHQL]


def test_e7_a_second_rules_page_that_fails_does_not_fit():
    result, calls, _ = _slots({tuple(RULES1): _rules(FILLER_PAGE),
                               tuple(RULES2): _proc("", 1, "gh: boom"),
                               tuple(SLOTS_GRAPHQL): GQL_NO_QUEUE})
    _assert_unreadable(result)
    assert result["reads"] == {"rules": "failed", "graphql": "ok"}
    assert "gh: boom" in result["detail"]
    assert calls == [RULES1, RULES2, SLOTS_GRAPHQL]


# ---- E8: a rules row that is not an object with a string type ----

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
def test_e8_malformed_rules_row_does_not_fit(rows):
    result, _, _ = _slots({tuple(RULES1): _rules(rows), tuple(SLOTS_GRAPHQL): GQL_NO_QUEUE})
    _assert_unreadable(result)
    assert result["reads"] == {"rules": "failed", "graphql": "ok"}
    assert "string type" in result["detail"]


# ---- E9: a merge_queue row whose limit is unreadable ----

@pytest.mark.parametrize("row,graphql_limit", [
    ({"type": "merge_queue", "parameters": None}, 5),
    ({"type": "merge_queue"}, 5),
    ({"type": "merge_queue", "parameters": ["x"]}, 5),
    ({"type": "merge_queue", "parameters": {}}, 5),
    ({"type": "merge_queue", "parameters": {"max_entries_to_build": None}}, 5),
    ({"type": "merge_queue", "parameters": {"max_entries_to_build": "5"}}, 5),
    ({"type": "merge_queue", "parameters": {"max_entries_to_build": 5.0}}, 5),
    ({"type": "merge_queue", "parameters": {"max_entries_to_build": True}}, 1),
    ({"type": "merge_queue", "parameters": {"max_entries_to_build": False}}, 0),
    ({"type": "merge_queue", "parameters": {"max_entries_to_build": -1}}, 5),
])
def test_e9_unreadable_rules_limit_does_not_fit(row, graphql_limit):
    result, _, _ = _slots({tuple(RULES1): _rules(OTHER_ROWS + [row]),
                           tuple(SLOTS_GRAPHQL): _gql(graphql_limit, 0)}, layers=1)
    _assert_unreadable(result, queue=True)
    assert result["reads"] == {"rules": "ok", "graphql": "ok"}
    assert "no readable max_entries_to_build" in result["detail"]


# ---- E10: two merge_queue rows with different limits ----

@pytest.mark.parametrize("first,second,graphql_limit", [(5, 7, 7), (7, 5, 7), (5, 7, 5)])
def test_e10_two_rows_with_different_limits_do_not_fit_on_one_page(first, second, graphql_limit):
    result, _, _ = _slots({tuple(RULES1): _rules([_row(first), _row(second)]),
                           tuple(SLOTS_GRAPHQL): _gql(graphql_limit, 0)}, layers=1)
    _assert_unreadable(result, queue=True)
    assert "disagree" in result["detail"]


def test_e10_two_rows_with_different_limits_across_pages_do_not_fit():
    result, _, _ = _slots({tuple(RULES1): _rules([_row(5)] + FILLER_PAGE[:99]),
                           tuple(RULES2): _rules([_row(7)]),
                           tuple(SLOTS_GRAPHQL): _gql(7, 0)}, layers=1)
    _assert_unreadable(result, queue=True)
    assert "disagree" in result["detail"]


def test_e10_two_rows_with_the_same_limit_fit():
    result, _, _ = _slots({tuple(RULES1): _rules([_row(5), _row(5)]),
                           tuple(SLOTS_GRAPHQL): _gql(5, 2)}, layers=3)
    assert result["fits"] is True
    assert result["free"] == 3


# ---- E11: the GraphQL call fails ----

def test_e11_cloud_proxy_graphql_refusal_does_not_fit():
    result, calls, _ = _slots({tuple(RULES1): _rules(OTHER_ROWS),
                               tuple(SLOTS_GRAPHQL): CLOUD_REFUSAL})
    _assert_unreadable(result)
    assert result["reads"] == {"rules": "ok", "graphql": "failed"}
    assert "(HTTP 403)" in result["detail"]
    assert "use the REST API" in result["detail"]
    assert calls == [RULES1, SLOTS_GRAPHQL]


def test_e11_cloud_proxy_graphql_refusal_beside_a_rules_queue_row_reports_queue_true():
    result, _, _ = _slots({tuple(RULES1): _rules([_row(5)]),
                           tuple(SLOTS_GRAPHQL): CLOUD_REFUSAL})
    _assert_unreadable(result, queue=True)
    assert result["reads"] == {"rules": "ok", "graphql": "failed"}
    assert (result["limit"], result["queued"], result["free"]) == (None, None, None)


def test_e11_graphql_exit_nonzero_with_a_good_body_still_does_not_fit():
    result, _, _ = _slots({tuple(RULES1): _rules(OTHER_ROWS),
                           tuple(SLOTS_GRAPHQL): _proc(GQL_NO_QUEUE.stdout, 1, "gh: exit")})
    _assert_unreadable(result)
    assert result["reads"] == {"rules": "ok", "graphql": "failed"}


@pytest.mark.parametrize("exc", RAISERS)
def test_e11_graphql_run_raising_does_not_fit(exc):
    result, _, _ = _slots({tuple(RULES1): _rules(OTHER_ROWS), tuple(SLOTS_GRAPHQL): exc})
    _assert_unreadable(result)
    assert result["reads"] == {"rules": "ok", "graphql": "failed"}
    assert "graphql read failed: gh call failed" in result["detail"]


# ---- E12 to E16: the GraphQL body is unusable ----

@pytest.mark.parametrize("stdout", ["not json", "", "[]", "null", "5"])
def test_e12_graphql_stdout_not_a_json_object_does_not_fit(stdout):
    result, _, _ = _slots({tuple(RULES1): _rules(OTHER_ROWS),
                           tuple(SLOTS_GRAPHQL): _proc(stdout)})
    _assert_unreadable(result)
    assert result["reads"] == {"rules": "ok", "graphql": "failed"}
    assert "not a JSON object" in result["detail"]


@pytest.mark.parametrize("errors", [[{"message": "boom"}], "boom", {"message": "boom"}])
def test_e13_graphql_errors_do_not_fit_even_beside_a_good_body(errors):
    body = {"data": {"repository": {"mergeQueue": None}}, "errors": errors}
    result, _, _ = _slots({tuple(RULES1): _rules(OTHER_ROWS),
                           tuple(SLOTS_GRAPHQL): _proc(json.dumps(body))})
    _assert_unreadable(result)
    assert result["reads"] == {"rules": "ok", "graphql": "failed"}
    assert "errors" in result["detail"]


@pytest.mark.parametrize("errors", [[], None])
def test_e13_an_empty_or_null_errors_key_does_not_fail_the_read(errors):
    body = {"data": {"repository": {"mergeQueue": None}}, "errors": errors}
    result, _, _ = _slots({tuple(RULES1): _rules(OTHER_ROWS),
                           tuple(SLOTS_GRAPHQL): _proc(json.dumps(body))})
    assert result["fits"] is True
    assert result["queue"] is False


@pytest.mark.parametrize("body", [
    {},
    {"data": None},
    {"data": []},
    {"data": {}},
    {"data": {"repository": None}},
    {"data": {"repository": []}},
    {"data": {"repository": "x"}},
])
def test_e14_missing_or_null_repository_does_not_fit(body):
    result, _, _ = _slots({tuple(RULES1): _rules(OTHER_ROWS),
                           tuple(SLOTS_GRAPHQL): _proc(json.dumps(body))})
    _assert_unreadable(result)
    assert result["reads"] == {"rules": "ok", "graphql": "failed"}
    assert "data.repository" in result["detail"]


def test_e15_mergequeue_key_absent_does_not_fit():
    body = {"data": {"repository": {"id": "R_x"}}}
    result, _, _ = _slots({tuple(RULES1): _rules(OTHER_ROWS),
                           tuple(SLOTS_GRAPHQL): _proc(json.dumps(body))})
    _assert_unreadable(result)
    assert result["reads"] == {"rules": "ok", "graphql": "failed"}
    assert "mergeQueue" in result["detail"]


@pytest.mark.parametrize("value", ["MQ_x", [], 5, True, False])
def test_e16_mergequeue_neither_null_nor_object_does_not_fit(value):
    result, _, _ = _slots({tuple(RULES1): _rules(OTHER_ROWS),
                           tuple(SLOTS_GRAPHQL): _gql_body(value)})
    _assert_unreadable(result)
    assert result["reads"] == {"rules": "ok", "graphql": "failed"}
    assert "neither null nor an object" in result["detail"]


# ---- E17 and E18: the queue's numbers are unreadable ----

@pytest.mark.parametrize("merge_queue", [
    {"entries": {"totalCount": 0}},
    {"configuration": None, "entries": {"totalCount": 0}},
    {"configuration": [5], "entries": {"totalCount": 0}},
    {"configuration": "x", "entries": {"totalCount": 0}},
    {"configuration": {}, "entries": {"totalCount": 0}},
    {"configuration": {"maximumEntriesToBuild": None}, "entries": {"totalCount": 0}},
    {"configuration": {"maximumEntriesToBuild": "5"}, "entries": {"totalCount": 0}},
    {"configuration": {"maximumEntriesToBuild": 5.0}, "entries": {"totalCount": 0}},
    {"configuration": {"maximumEntriesToBuild": True}, "entries": {"totalCount": 0}},
    {"configuration": {"maximumEntriesToBuild": -1}, "entries": {"totalCount": 0}},
])
def test_e17_unreadable_graphql_limit_does_not_fit(merge_queue):
    result, _, _ = _slots({tuple(RULES1): _rules(OTHER_ROWS),
                           tuple(SLOTS_GRAPHQL): _gql_body(merge_queue)}, layers=1)
    _assert_unreadable(result, queue=True)
    assert result["reads"] == {"rules": "ok", "graphql": "ok"}
    assert (result["limit"], result["free"]) == (None, None)
    assert "configuration.maximumEntriesToBuild" in result["detail"]


@pytest.mark.parametrize("merge_queue", [
    {"configuration": {"maximumEntriesToBuild": 5}},
    {"configuration": {"maximumEntriesToBuild": 5}, "entries": None},
    {"configuration": {"maximumEntriesToBuild": 5}, "entries": [0]},
    {"configuration": {"maximumEntriesToBuild": 5}, "entries": "x"},
    {"configuration": {"maximumEntriesToBuild": 5}, "entries": {}},
    {"configuration": {"maximumEntriesToBuild": 5}, "entries": {"totalCount": None}},
    {"configuration": {"maximumEntriesToBuild": 5}, "entries": {"totalCount": "0"}},
    {"configuration": {"maximumEntriesToBuild": 5}, "entries": {"totalCount": 0.0}},
    {"configuration": {"maximumEntriesToBuild": 5}, "entries": {"totalCount": True}},
    {"configuration": {"maximumEntriesToBuild": 5}, "entries": {"totalCount": -1}},
])
def test_e18_unreadable_graphql_entry_count_does_not_fit(merge_queue):
    result, _, _ = _slots({tuple(RULES1): _rules(OTHER_ROWS),
                           tuple(SLOTS_GRAPHQL): _gql_body(merge_queue)}, layers=1)
    _assert_unreadable(result, queue=True)
    assert result["reads"] == {"rules": "ok", "graphql": "ok"}
    assert (result["queued"], result["free"]) == (None, None)
    assert "entries.totalCount" in result["detail"]


def test_e17_e18_both_unreadable_names_both():
    result, _, _ = _slots({tuple(RULES1): _rules(OTHER_ROWS),
                           tuple(SLOTS_GRAPHQL): _gql_body({})})
    _assert_unreadable(result, queue=True)
    assert "configuration.maximumEntriesToBuild" in result["detail"]
    assert "entries.totalCount" in result["detail"]


# ---- E19 and E20: the two reads disagree ----

def test_e19_rules_queue_row_while_graphql_says_null_does_not_fit():
    result, _, _ = _slots({tuple(RULES1): _rules(OTHER_ROWS + [_row(5)]),
                           tuple(SLOTS_GRAPHQL): GQL_NO_QUEUE}, layers=1)
    _assert_unreadable(result, queue=True)
    assert result["reads"] == {"rules": "ok", "graphql": "ok"}
    assert (result["limit"], result["queued"], result["free"]) == (None, None, None)
    assert "no merge queue" in result["detail"]


@pytest.mark.parametrize("rules_limit,graphql_limit,queued,layers", [
    (7, 5, 0, 1),
    (3, 5, 0, 3),
    (5, 7, 0, 5),
    (0, 5, 0, 1),
])
def test_e20_rules_limit_differing_from_graphql_limit_does_not_fit(rules_limit, graphql_limit,
                                                                  queued, layers):
    result, _, _ = _slots({tuple(RULES1): _rules([_row(rules_limit)]),
                           tuple(SLOTS_GRAPHQL): _gql(graphql_limit, queued)}, layers=layers)
    _assert_unreadable(result, queue=True)
    assert result["reads"] == {"rules": "ok", "graphql": "ok"}
    assert (result["limit"], result["queued"], result["free"]) == (
        graphql_limit, queued, graphql_limit - queued)
    assert "differs" in result["detail"]


# ---- E21: the deadline ----

def test_e21_deadline_already_passed_makes_no_call_and_does_not_fit():
    run, calls = _make_run({})
    result = mq.slots(repo=REPO, branch=BRANCH, layers=2, run=run, deadline_at=10.0,
                      monotonic=lambda: 10.0)
    assert set(result) == SLOTS_KEYS
    _assert_unreadable(result)
    assert result["reads"] == {"rules": "failed", "graphql": "failed"}
    assert "time budget" in result["detail"]
    assert calls == []


def test_e21_deadline_passing_between_the_reads_makes_no_graphql_call():
    ticks = iter([0.0, 100.0])
    run, calls = _make_run({tuple(RULES1): _rules(OTHER_ROWS)})
    result = mq.slots(repo=REPO, branch=BRANCH, layers=2, run=run, deadline_at=50.0,
                      monotonic=lambda: next(ticks))
    assert set(result) == SLOTS_KEYS
    _assert_unreadable(result)
    assert result["reads"] == {"rules": "ok", "graphql": "failed"}
    assert "graphql read failed" in result["detail"]
    assert "time budget" in result["detail"]
    assert calls == [RULES1]


def test_e21_graphql_is_attempted_after_a_failed_rules_read_so_reads_reports_both():
    result, calls, _ = _slots({tuple(RULES1): _proc("", 1, "gh: boom"),
                               tuple(SLOTS_GRAPHQL): _proc("", 1, "gh: bang")})
    _assert_unreadable(result)
    assert result["reads"] == {"rules": "failed", "graphql": "failed"}
    assert "rules read failed" in result["detail"]
    assert "graphql read failed" in result["detail"]
    assert calls == [RULES1, SLOTS_GRAPHQL]


@pytest.mark.parametrize("timeout,deadline_at,expected", [
    (120, 10.0, 10.0),
    (3, 10.0, 3),
    (120, 1000.0, 120),
])
def test_e21_each_calls_timeout_is_the_smaller_of_timeout_and_the_time_left(
        timeout, deadline_at, expected):
    result, _, run = _slots({tuple(RULES1): _rules(OTHER_ROWS),
                             tuple(SLOTS_GRAPHQL): GQL_NO_QUEUE},
                            timeout=timeout, deadline_at=deadline_at, monotonic=lambda: 0.0)
    assert result["fits"] is True
    assert [kw["timeout"] for kw in run.kw_calls] == [expected, expected]


# ---- E22: a failed rules read never fits, whatever GraphQL says ----

def test_e22_rules_failed_and_graphql_queue_with_room_does_not_fit_but_reports_numbers():
    result, _, _ = _slots({tuple(RULES1): _proc("", 1, "gh: boom"),
                           tuple(SLOTS_GRAPHQL): _gql(5, 0)}, layers=1)
    _assert_unreadable(result, queue=True)
    assert result["reads"] == {"rules": "failed", "graphql": "ok"}
    assert (result["limit"], result["queued"], result["free"]) == (5, 0, 5)


def test_e22_rules_failed_and_graphql_queue_short_is_unreadable_not_short():
    result, _, _ = _slots({tuple(RULES1): _proc("", 1, "gh: boom"),
                           tuple(SLOTS_GRAPHQL): _gql(5, 5)}, layers=1)
    _assert_unreadable(result, queue=True)
    assert result["free"] == 0


# ---- the invariant: fits only on a no-queue pair or a readable, agreed, roomy queue ----

def test_fits_is_answered_only_on_the_two_allowed_paths():
    rules_cases = {
        "none": _rules(OTHER_ROWS),
        "row-5": _rules([_row(5)]),
        "row-bad": _rules([{"type": "merge_queue", "parameters": None}]),
        "failed": _proc("", 1, "gh: boom"),
    }
    graphql_cases = {
        "null": GQL_NO_QUEUE,
        "queue-5-of-0": _gql(5, 0),
        "queue-3-of-0": _gql(3, 0),
        "queue-bad": _gql_body({"configuration": None, "entries": {"totalCount": 0}}),
        "failed": _proc("", 1, "gh: bang"),
    }
    fitting = []
    for rules_key, rules_proc in rules_cases.items():
        for graphql_key, graphql_proc in graphql_cases.items():
            result, _, _ = _slots({tuple(RULES1): rules_proc,
                                   tuple(SLOTS_GRAPHQL): graphql_proc}, layers=2)
            if result["fits"]:
                fitting.append((rules_key, graphql_key))
    assert fitting == [("none", "null"), ("none", "queue-5-of-0"), ("none", "queue-3-of-0"),
                       ("row-5", "queue-5-of-0")]


# ---- D9: the CLI ----

def test_d9_cli_fits_round_trip_prints_one_json_line_and_exits_zero(capsys):
    run, calls = _make_run({tuple(RULES1): _rules(OTHER_ROWS),
                            tuple(SLOTS_GRAPHQL): _gql(5, 2)})
    code = mq.main(["slots", "--repo", REPO, "--branch", BRANCH, "--layers", "3"], run=run)
    out = capsys.readouterr().out
    assert code == 0
    assert out.endswith("\n") and out.count("\n") == 1
    assert json.loads(out) == {
        "ok": True, "fits": True, "queue": True, "limit": 5, "queued": 2, "free": 3,
        "layers": 3, "reads": {"rules": "ok", "graphql": "ok"}, "reason": None,
        "detail": None, "repo": REPO, "branch": BRANCH,
    }
    assert calls == [RULES1, SLOTS_GRAPHQL]


def test_d9_cli_short_round_trip_exits_one(capsys):
    run, _ = _make_run({tuple(RULES1): _rules(OTHER_ROWS), tuple(SLOTS_GRAPHQL): _gql(5, 3)})
    code = mq.main(["slots", "--repo", REPO, "--branch", BRANCH, "--layers", "3"], run=run)
    body = json.loads(capsys.readouterr().out)
    assert code == 1
    assert body["fits"] is False
    assert body["reason"] == "slots-short"
    assert body["free"] == 2


def test_d9_cli_unreadable_round_trip_exits_one(capsys):
    run, _ = _make_run({tuple(RULES1): _rules(OTHER_ROWS), tuple(SLOTS_GRAPHQL): CLOUD_REFUSAL})
    code = mq.main(["slots", "--repo", REPO, "--branch", BRANCH, "--layers", "3"], run=run)
    body = json.loads(capsys.readouterr().out)
    assert code == 1
    assert body["reason"] == "slots-unreadable"


def test_d9_cli_no_queue_round_trip_exits_zero(capsys):
    run, _ = _make_run({tuple(RULES1): _rules(OTHER_ROWS), tuple(SLOTS_GRAPHQL): GQL_NO_QUEUE})
    code = mq.main(["slots", "--repo", REPO, "--branch", BRANCH, "--layers", "9"], run=run)
    body = json.loads(capsys.readouterr().out)
    assert code == 0
    assert body["fits"] is True
    assert body["queue"] is False


def test_d9_cli_missing_layers_prints_the_slots_shaped_bad_argument(capsys):
    run, calls = _make_run({})
    code = mq.main(["slots", "--repo", REPO, "--branch", BRANCH], run=run)
    out = capsys.readouterr().out
    assert code == 1
    assert out.count("\n") == 1
    body = json.loads(out)
    assert set(body) == SLOTS_KEYS
    assert len(body) == 12
    _assert_bad_argument(body)
    assert calls == []


@pytest.mark.parametrize("argv", [
    ["slots"],
    ["slots", "--repo", REPO, "--branch", BRANCH, "--layers", "x"],
    ["slots", "--repo", REPO, "--branch", BRANCH, "--layers", "2.5"],
    ["slots", "--repo", REPO, "--branch", BRANCH, "--layers"],
    ["slots", "--repo", REPO, "--layers", "2"],
    ["slots", "--branch", BRANCH, "--layers", "2"],
    ["slots", "--repo", REPO, "--branch", BRANCH, "--layers", "2", "--nope", "1"],
    ["slots", "--help"],
    ["slots", "--repo", REPO, "--branch", BRANCH, "--layers", "0"],
    ["slots", "--repo", REPO, "--branch", BRANCH, "--layers", "-2"],
    ["slots", "--repo", "nope", "--branch", BRANCH, "--layers", "2"],
])
def test_d9_cli_malformed_slots_call_is_the_slots_shaped_bad_argument(argv, capsys):
    run, calls = _make_run({})
    code = mq.main(argv, run=run)
    out = capsys.readouterr().out
    assert code == 1
    assert out.count("\n") == 1
    _assert_bad_argument(json.loads(out))
    assert calls == []


@pytest.mark.parametrize("argv", [
    [],
    ["read"],
    ["read", "--repo", REPO],
    ["write", "--repo", REPO, "--branch", BRANCH],
    ["--help"],
    ["--repo", REPO, "slots", "--branch", BRANCH, "--layers", "2"],
])
def test_d9_cli_malformed_call_of_any_other_shape_keeps_the_read_shaped_bad_argument(argv,
                                                                                    capsys):
    run, calls = _make_run({})
    code = mq.main(argv, run=run)
    out = capsys.readouterr().out
    body = json.loads(out)
    assert code == 1
    assert set(body) == READ_KEYS
    assert body["ok"] is False
    assert body["reason"] == "bad-argument"
    assert calls == []


def test_d9_read_cli_output_is_unchanged(capsys):
    run, calls = _make_run({tuple(RULES1): _rules(OTHER_ROWS + [_row(5)])})
    code = mq.main(["read", "--repo", REPO, "--branch", BRANCH], run=run)
    out = capsys.readouterr().out
    assert code == 0
    assert out.count("\n") == 1
    assert json.loads(out) == {
        "ok": True, "queue": True, "source": "rules", "method": "squash",
        "reads": {"rules": "ok", "graphql": "skipped"},
        "reason": None, "detail": None, "repo": REPO, "branch": BRANCH,
    }
    assert calls == [RULES1]


def test_d9_read_cli_no_queue_keeps_its_own_graphql_argv(capsys):
    run, calls = _make_run({tuple(RULES1): _rules(OTHER_ROWS),
                            tuple(READ_GRAPHQL): _proc(GQL_NO_QUEUE.stdout)})
    code = mq.main(["read", "--repo", REPO, "--branch", BRANCH], run=run)
    body = json.loads(capsys.readouterr().out)
    assert code == 0
    assert body["queue"] is False
    assert body["source"] == "none"
    assert calls == [RULES1, READ_GRAPHQL]


# ---- D10: every result, every path, has exactly the twelve keys ----

def _kw(**overrides):
    base = {"repo": REPO, "branch": BRANCH, "layers": 3}
    base.update(overrides)
    return base


FAIL_RULES = _proc("", 1, "gh: boom")

CENSUS = [
    pytest.param({tuple(RULES1): _rules(OTHER_ROWS), tuple(SLOTS_GRAPHQL): _gql(5, 2)},
                 _kw(), id="fits-classic"),
    pytest.param({tuple(RULES1): _rules(OTHER_ROWS), tuple(SLOTS_GRAPHQL): _gql(5, 3)},
                 _kw(), id="short-classic"),
    pytest.param({tuple(RULES1): _rules([_row(5)]), tuple(SLOTS_GRAPHQL): _gql(5, 0)},
                 _kw(layers=5), id="fits-boundary-ruleset"),
    pytest.param({tuple(RULES1): _rules([_row(5)]), tuple(SLOTS_GRAPHQL): _gql(5, 7)},
                 _kw(), id="short-negative-free"),
    pytest.param({tuple(RULES1): _rules(OTHER_ROWS), tuple(SLOTS_GRAPHQL): GQL_NO_QUEUE},
                 _kw(), id="fits-no-queue"),
    pytest.param({tuple(RULES1): _rules(FILLER_PAGE), tuple(RULES2): _rules([_row(5)]),
                  tuple(SLOTS_GRAPHQL): _gql(5, 0)}, _kw(), id="fits-row-on-page-two"),
    pytest.param({tuple(RULES1): _rules([_row(7)]), tuple(SLOTS_GRAPHQL): _gql(5, 0)},
                 _kw(), id="unreadable-limit-differs"),
    pytest.param({tuple(RULES1): _rules([_row(5), _row(6)]), tuple(SLOTS_GRAPHQL): _gql(5, 0)},
                 _kw(), id="unreadable-two-rules-limits"),
    pytest.param({tuple(RULES1): _rules([{"type": "merge_queue"}]),
                  tuple(SLOTS_GRAPHQL): _gql(5, 0)}, _kw(), id="unreadable-rules-limit"),
    pytest.param({tuple(RULES1): _rules([_row(5)]), tuple(SLOTS_GRAPHQL): GQL_NO_QUEUE},
                 _kw(), id="unreadable-rules-queue-graphql-null"),
    pytest.param({tuple(RULES1): _rules(OTHER_ROWS), tuple(SLOTS_GRAPHQL): CLOUD_REFUSAL},
                 _kw(), id="unreadable-cloud-refusal"),
    pytest.param({tuple(RULES1): FAIL_RULES, tuple(SLOTS_GRAPHQL): _gql(5, 0)},
                 _kw(), id="unreadable-rules-failed"),
    pytest.param({tuple(RULES1): FAIL_RULES, tuple(SLOTS_GRAPHQL): CLOUD_REFUSAL},
                 _kw(), id="unreadable-both-failed"),
    pytest.param({tuple(RULES1): _rules(["x"]), tuple(SLOTS_GRAPHQL): GQL_NO_QUEUE},
                 _kw(), id="unreadable-bad-row"),
    pytest.param({tuple(RULES1): _rules(OTHER_ROWS), tuple(SLOTS_GRAPHQL): _proc("[]")},
                 _kw(), id="unreadable-graphql-not-object"),
    pytest.param({tuple(RULES1): _rules(OTHER_ROWS), tuple(SLOTS_GRAPHQL): _gql_body({})},
                 _kw(), id="unreadable-numbers"),
    pytest.param({tuple(RULES1): _rules(OTHER_ROWS), tuple(SLOTS_GRAPHQL): _gql_body("x")},
                 _kw(), id="unreadable-mergequeue-string"),
    pytest.param({}, _kw(deadline_at=1.0, monotonic=lambda: 5.0), id="unreadable-deadline"),
    pytest.param({}, _kw(repo="nope"), id="bad-repo"),
    pytest.param({}, _kw(branch=""), id="bad-branch"),
    pytest.param({}, _kw(timeout=0), id="bad-timeout"),
    pytest.param({}, _kw(deadline_at=math.nan), id="bad-deadline"),
    pytest.param({}, _kw(layers=True), id="bad-layers"),
]


@pytest.mark.parametrize("handlers,kwargs", CENSUS)
def test_d10_every_result_has_exactly_the_twelve_keys(handlers, kwargs):
    run, _ = _make_run(handlers)
    result = mq.slots(run=run, **kwargs)
    assert set(result) == SLOTS_KEYS
    assert len(result) == 12
    assert (result["reason"] is None) == result["fits"]
    assert (result["reason"] == "bad-argument") == (result["ok"] is False)
    if result["fits"]:
        assert result["reads"] == {"rules": "ok", "graphql": "ok"}
    if result["free"] is not None:
        assert result["free"] == result["limit"] - result["queued"]
