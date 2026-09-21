"""Fake-based units for stack_check.py. No real gh or network — every gh call is faked."""
import json
import subprocess
from types import SimpleNamespace

import pytest

import stack_check as sc

REPO = "owner/example"
OWNER = "owner"
NAME = "example"
PR = 103
STACK_NUMBER = 7
STACK_SIZE = 5
STACK_BASE = "main"

TOTAL_KEYS = {
    "ok",
    "reason",
    "detail",
    "repo",
    "pr",
    "stack",
    "queried",
    "members",
    "pages",
}


@pytest.fixture(autouse=True)
def _gh_on_path(monkeypatch):
    monkeypatch.setattr(sc.shutil, "which", lambda name: "/usr/bin/gh" if name == "gh" else None)


def _make_run(handlers):
    calls = []
    kw_calls = []
    queues = {}
    for key, value in handlers.items():
        if isinstance(value, list):
            queues[key] = list(value)
            if len(queues[key]) == 1:
                queues[key] = queues[key] + queues[key]
        else:
            queues[key] = [value, value]

    def _run(argv, **kwargs):
        calls.append(list(argv))
        kw_calls.append(dict(kwargs))
        key = tuple(argv)
        if key not in queues or not queues[key]:
            raise AssertionError("unexpected gh argv: %r" % (argv,))
        handler = queues[key].pop(0)
        if isinstance(handler, Exception):
            raise handler
        return handler

    _run.kw_calls = kw_calls
    return _run, calls


def _graphql_ok(pull_request, errors=None):
    payload = {"data": {"repository": {"pullRequest": pull_request}}}
    if errors is not None:
        payload["errors"] = errors
    return SimpleNamespace(returncode=0, stdout=json.dumps(payload), stderr="")


def _member(position, number=None, **overrides):
    number = number if number is not None else (100 + position)
    pr_fields = {
        "number": number,
        "state": "OPEN",
        "isDraft": False,
        "headRefName": "branch-%d" % position,
        "headRefOid": "oid%d" % position,
        "baseRefName": STACK_BASE,
    }
    pr_fields.update(overrides)
    return {"position": position, "pullRequest": pr_fields}


def _pull_request(
    *,
    pr_number=PR,
    position=3,
    stack_number=STACK_NUMBER,
    stack_size=STACK_SIZE,
    nodes,
    has_next_page=False,
    end_cursor=None,
    stack_entry=None,
    head_ref_name=None,
    head_ref_oid=None,
    base_ref_name=None,
):
    queried_head_ref = head_ref_name or "branch-%d" % position
    queried_head_oid = head_ref_oid or "oid%d" % position
    queried_base_ref = base_ref_name or STACK_BASE
    if stack_entry is None:
        stack_entry = {
            "position": position,
            "stack": {
                "number": stack_number,
                "size": stack_size,
                "baseRefName": STACK_BASE,
                "entries": {
                    "pageInfo": {
                        "hasNextPage": has_next_page,
                        "endCursor": end_cursor,
                    },
                    "nodes": nodes,
                },
            },
        }
    return {
        "number": pr_number,
        "baseRefName": queried_base_ref,
        "headRefName": queried_head_ref,
        "headRefOid": queried_head_oid,
        "stackEntry": stack_entry,
    }


def _argv_page(pr, page_size, after=None):
    return tuple(sc._graphql_argv(OWNER, NAME, pr, page_size, after))


def _assert_refusal(result, reason):
    assert set(result.keys()) == TOTAL_KEYS
    assert result["ok"] is False
    assert result["reason"] == reason
    assert result["detail"] is not None
    assert result["members"] == []


def _success_handlers(pr_number=PR, position=3, page_size=2):
    page1 = _pull_request(
        pr_number=pr_number,
        position=position,
        nodes=[_member(1), _member(2)],
        has_next_page=True,
        end_cursor="cursor-1",
    )
    page2 = _pull_request(
        pr_number=pr_number,
        position=position,
        nodes=[_member(3, number=pr_number), _member(4)],
        has_next_page=True,
        end_cursor="cursor-2",
    )
    page3 = _pull_request(
        pr_number=pr_number,
        position=position,
        nodes=[_member(5)],
        has_next_page=False,
        end_cursor=None,
    )
    return {
        _argv_page(pr_number, page_size): _graphql_ok(page1),
        _argv_page(pr_number, page_size, "cursor-1"): _graphql_ok(page2),
        _argv_page(pr_number, page_size, "cursor-2"): _graphql_ok(page3),
    }


# --- register E1-E10: bad-argument ------------------------------------------------


def test_e1_pr_not_int():
    result = sc.read_membership(pr=True, repo=REPO, run=lambda *a, **k: None)
    _assert_refusal(result, sc.REASON_BAD_ARGUMENT)
    assert result["repo"] == REPO
    assert result["pr"] is None


def test_e2_pr_less_than_one():
    result = sc.read_membership(pr=0, repo=REPO, run=lambda *a, **k: None)
    _assert_refusal(result, sc.REASON_BAD_ARGUMENT)
    assert result["pr"] is None


def test_e3_repo_not_string():
    result = sc.read_membership(pr=PR, repo=123, run=lambda *a, **k: None)
    _assert_refusal(result, sc.REASON_BAD_ARGUMENT)
    assert result["repo"] is None
    assert result["pr"] == PR


def test_e4_repo_bad_pattern():
    result = sc.read_membership(pr=PR, repo="bad repo", run=lambda *a, **k: None)
    _assert_refusal(result, sc.REASON_BAD_ARGUMENT)
    assert result["repo"] is None


def test_e5_expect_stack_not_int():
    result = sc.read_membership(pr=PR, repo=REPO, expect_stack=True, run=lambda *a, **k: None)
    _assert_refusal(result, sc.REASON_BAD_ARGUMENT)


def test_e6_expect_stack_less_than_one():
    result = sc.read_membership(pr=PR, repo=REPO, expect_stack=0, run=lambda *a, **k: None)
    _assert_refusal(result, sc.REASON_BAD_ARGUMENT)


def test_e7_page_size_not_int():
    result = sc.read_membership(pr=PR, repo=REPO, page_size=True, run=lambda *a, **k: None)
    _assert_refusal(result, sc.REASON_BAD_ARGUMENT)


def test_e8_page_size_below_min():
    result = sc.read_membership(pr=PR, repo=REPO, page_size=0, run=lambda *a, **k: None)
    _assert_refusal(result, sc.REASON_BAD_ARGUMENT)


def test_e9_page_size_above_max():
    result = sc.read_membership(pr=PR, repo=REPO, page_size=101, run=lambda *a, **k: None)
    _assert_refusal(result, sc.REASON_BAD_ARGUMENT)


def test_e10_parse_boundary(capsys):
    rc = sc.main([])
    out = capsys.readouterr().out
    result = json.loads(out)
    _assert_refusal(result, sc.REASON_BAD_ARGUMENT)
    assert rc == 1
    assert "usage:" not in out.lower()


# --- register E11-E27: stack-unreadable -------------------------------------------


def test_e11_gh_not_on_path(monkeypatch):
    monkeypatch.setattr(sc.shutil, "which", lambda _name: None)
    result = sc.read_membership(pr=PR, repo=REPO, run=lambda *a, **k: None)
    _assert_refusal(result, sc.REASON_STACK_UNREADABLE)


def test_e12_run_raises_file_not_found():
    def _run(*args, **kwargs):
        raise FileNotFoundError("missing gh")

    result = sc.read_membership(pr=PR, repo=REPO, run=_run)
    _assert_refusal(result, sc.REASON_STACK_UNREADABLE)


def test_e13_run_raises_timeout_expired():
    def _run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="gh", timeout=120)

    result = sc.read_membership(pr=PR, repo=REPO, run=_run)
    _assert_refusal(result, sc.REASON_STACK_UNREADABLE)


def test_e14_gh_exits_nonzero():
    run, _calls = _make_run(
        {
            _argv_page(PR, sc.DEFAULT_PAGE_SIZE): SimpleNamespace(
                returncode=1, stdout="", stderr="graphql failed"
            ),
        }
    )
    result = sc.read_membership(pr=PR, repo=REPO, run=run)
    _assert_refusal(result, sc.REASON_STACK_UNREADABLE)


def test_e14_gh_exits_nonzero_with_valid_stdout():
    page = _pull_request(
        pr_number=PR,
        position=1,
        nodes=[_member(1, number=PR)],
        has_next_page=False,
        stack_size=1,
    )
    page["number"] = PR
    page["stackEntry"]["position"] = 1
    run, _calls = _make_run(
        {
            _argv_page(PR, sc.DEFAULT_PAGE_SIZE): SimpleNamespace(
                returncode=1, stdout=json.dumps({"data": {"repository": {"pullRequest": page}}}), stderr=""
            ),
        }
    )
    result = sc.read_membership(pr=PR, repo=REPO, run=run)
    _assert_refusal(result, sc.REASON_STACK_UNREADABLE)


def test_e15_stdout_not_json():
    run, _calls = _make_run(
        {
            _argv_page(PR, sc.DEFAULT_PAGE_SIZE): SimpleNamespace(
                returncode=0, stdout="not json", stderr=""
            ),
        }
    )
    result = sc.read_membership(pr=PR, repo=REPO, run=run)
    _assert_refusal(result, sc.REASON_STACK_UNREADABLE)


def test_e15_payload_not_object():
    run, _calls = _make_run(
        {
            _argv_page(PR, sc.DEFAULT_PAGE_SIZE): SimpleNamespace(
                returncode=0, stdout=json.dumps(["not", "an", "object"]), stderr=""
            ),
        }
    )
    result = sc.read_membership(pr=PR, repo=REPO, run=run)
    _assert_refusal(result, sc.REASON_STACK_UNREADABLE)


def test_e15_payload_missing_data_key():
    run, _calls = _make_run(
        {
            _argv_page(PR, sc.DEFAULT_PAGE_SIZE): SimpleNamespace(
                returncode=0, stdout="{}", stderr=""
            ),
        }
    )
    result = sc.read_membership(pr=PR, repo=REPO, run=run)
    _assert_refusal(result, sc.REASON_STACK_UNREADABLE)
    assert "graphql data/repository is null or not an object" in result["detail"]


def test_e16_graphql_errors_nonempty():
    page = _pull_request(
        pr_number=PR,
        position=1,
        nodes=[_member(1, number=PR)],
        has_next_page=False,
        stack_size=1,
    )
    page["number"] = PR
    page["stackEntry"]["position"] = 1
    run, _calls = _make_run(
        {
            _argv_page(PR, sc.DEFAULT_PAGE_SIZE): _graphql_ok(page, errors=[{"message": "boom"}]),
        }
    )
    result = sc.read_membership(pr=PR, repo=REPO, run=run)
    _assert_refusal(result, sc.REASON_STACK_UNREADABLE)


def test_e16_errors_not_list():
    page = _pull_request(
        pr_number=PR,
        position=1,
        nodes=[_member(1, number=PR)],
        has_next_page=False,
        stack_size=1,
    )
    page["number"] = PR
    page["stackEntry"]["position"] = 1
    payload = {"data": {"repository": {"pullRequest": page}}, "errors": False}
    run, _calls = _make_run(
        {
            _argv_page(PR, sc.DEFAULT_PAGE_SIZE): SimpleNamespace(
                returncode=0, stdout=json.dumps(payload), stderr=""
            ),
        }
    )
    result = sc.read_membership(pr=PR, repo=REPO, run=run)
    _assert_refusal(result, sc.REASON_STACK_UNREADABLE)


def test_e17_data_or_repository_missing():
    payload = {"data": {"repository": None}}
    run, _calls = _make_run(
        {
            _argv_page(PR, sc.DEFAULT_PAGE_SIZE): SimpleNamespace(
                returncode=0, stdout=json.dumps(payload), stderr=""
            ),
        }
    )
    result = sc.read_membership(pr=PR, repo=REPO, run=run)
    _assert_refusal(result, sc.REASON_STACK_UNREADABLE)


def test_e18_pull_request_missing():
    payload = {"data": {"repository": {"pullRequest": None}}}
    run, _calls = _make_run(
        {
            _argv_page(PR, sc.DEFAULT_PAGE_SIZE): SimpleNamespace(
                returncode=0, stdout=json.dumps(payload), stderr=""
            ),
        }
    )
    result = sc.read_membership(pr=PR, repo=REPO, run=run)
    _assert_refusal(result, sc.REASON_STACK_UNREADABLE)


def test_e19_required_pull_request_field_wrong_type():
    page = _pull_request(nodes=[_member(1)], stack_size=1)
    page["headRefOid"] = 123
    run, _calls = _make_run({_argv_page(PR, sc.DEFAULT_PAGE_SIZE): _graphql_ok(page)})
    result = sc.read_membership(pr=PR, repo=REPO, run=run)
    _assert_refusal(result, sc.REASON_STACK_UNREADABLE)


def test_e20_stack_entry_bad():
    page = _pull_request(nodes=[_member(1)], stack_size=1)
    page["stackEntry"] = "not-an-object"
    run, _calls = _make_run({_argv_page(PR, sc.DEFAULT_PAGE_SIZE): _graphql_ok(page)})
    result = sc.read_membership(pr=PR, repo=REPO, run=run)
    _assert_refusal(result, sc.REASON_STACK_UNREADABLE)


def test_e21_stack_field_wrong_type():
    page = _pull_request(nodes=[_member(1)], stack_size=1)
    page["stackEntry"]["stack"]["size"] = "five"
    run, _calls = _make_run({_argv_page(PR, sc.DEFAULT_PAGE_SIZE): _graphql_ok(page)})
    result = sc.read_membership(pr=PR, repo=REPO, run=run)
    _assert_refusal(result, sc.REASON_STACK_UNREADABLE)


def test_e22_entries_page_info_nodes_wrong_type():
    page = _pull_request(nodes=[_member(1)], stack_size=1)
    page["stackEntry"]["stack"]["entries"]["nodes"] = "nope"
    run, _calls = _make_run({_argv_page(PR, sc.DEFAULT_PAGE_SIZE): _graphql_ok(page)})
    result = sc.read_membership(pr=PR, repo=REPO, run=run)
    _assert_refusal(result, sc.REASON_STACK_UNREADABLE)


def test_e22_entries_page_info_empty_object():
    page = _pull_request(
        pr_number=PR,
        position=1,
        nodes=[_member(1, number=PR)],
        has_next_page=False,
        stack_size=1,
    )
    page["number"] = PR
    page["stackEntry"]["position"] = 1
    nodes = page["stackEntry"]["stack"]["entries"]["nodes"]
    page["stackEntry"]["stack"]["entries"] = {"nodes": nodes}
    run, _calls = _make_run({_argv_page(PR, sc.DEFAULT_PAGE_SIZE): _graphql_ok(page)})
    result = sc.read_membership(pr=PR, repo=REPO, run=run)
    _assert_refusal(result, sc.REASON_STACK_UNREADABLE)


def test_e23_node_field_wrong_type():
    page = _pull_request(
        pr_number=101,
        position=1,
        nodes=[{"position": 1, "pullRequest": {"number": 101}}],
        stack_size=1,
        head_ref_name="branch-1",
        head_ref_oid="oid1",
    )
    run, _calls = _make_run({_argv_page(PR, sc.DEFAULT_PAGE_SIZE): _graphql_ok(page)})
    result = sc.read_membership(pr=PR, repo=REPO, run=run)
    _assert_refusal(result, sc.REASON_STACK_UNREADABLE)


def test_e24_zero_nodes_with_has_next_page():
    page = _pull_request(nodes=[], has_next_page=True, end_cursor="cursor-1", stack_size=5)
    run, _calls = _make_run({_argv_page(PR, 2): _graphql_ok(page)})
    result = sc.read_membership(pr=PR, repo=REPO, page_size=2, run=run)
    _assert_refusal(result, sc.REASON_STACK_UNREADABLE)


def test_e25_repeated_end_cursor():
    page1 = _pull_request(
        nodes=[_member(1), _member(2)],
        has_next_page=True,
        end_cursor="cursor-dup",
        stack_size=5,
    )
    page2 = _pull_request(
        nodes=[_member(3, number=PR), _member(4), _member(5)],
        has_next_page=True,
        end_cursor="cursor-dup",
        stack_size=5,
    )
    page3 = _pull_request(
        nodes=[],
        has_next_page=False,
        end_cursor=None,
        stack_size=5,
    )
    run, _calls = _make_run(
        {
            _argv_page(PR, 2): _graphql_ok(page1),
            _argv_page(PR, 2, "cursor-dup"): [_graphql_ok(page2), _graphql_ok(page3)],
        }
    )
    result = sc.read_membership(pr=PR, repo=REPO, page_size=2, run=run)
    _assert_refusal(result, sc.REASON_STACK_UNREADABLE)


def test_e26_has_next_page_without_end_cursor():
    page1 = _pull_request(
        nodes=[_member(1), _member(2)],
        has_next_page=True,
        end_cursor=None,
        stack_size=5,
    )
    page1["stackEntry"]["stack"]["entries"]["pageInfo"]["endCursor"] = 42
    page2 = _pull_request(
        nodes=[_member(3, number=PR), _member(4)],
        has_next_page=True,
        end_cursor="cursor-2",
        stack_size=5,
    )
    page3 = _pull_request(
        nodes=[_member(5)],
        has_next_page=False,
        end_cursor=None,
        stack_size=5,
    )
    run, _calls = _make_run(
        {
            _argv_page(PR, 2): _graphql_ok(page1),
            _argv_page(PR, 2, 42): _graphql_ok(page2),
            _argv_page(PR, 2, "cursor-2"): _graphql_ok(page3),
        }
    )
    result = sc.read_membership(pr=PR, repo=REPO, page_size=2, run=run)
    _assert_refusal(result, sc.REASON_STACK_UNREADABLE)


def test_e26_has_next_page_not_boolean():
    page = _pull_request(
        nodes=[_member(1), _member(2), _member(3, number=PR), _member(4), _member(5)],
        has_next_page=False,
        stack_size=5,
    )
    page["stackEntry"]["stack"]["entries"]["pageInfo"]["hasNextPage"] = 0
    run, _calls = _make_run({_argv_page(PR, sc.DEFAULT_PAGE_SIZE): _graphql_ok(page)})
    result = sc.read_membership(pr=PR, repo=REPO, run=run)
    _assert_refusal(result, sc.REASON_STACK_UNREADABLE)


def test_e27_collected_count_would_exceed_size():
    page = _pull_request(
        nodes=[_member(1), _member(2), _member(3)],
        has_next_page=False,
        stack_size=2,
    )
    run, _calls = _make_run({_argv_page(PR, 3): _graphql_ok(page)})
    result = sc.read_membership(pr=PR, repo=REPO, page_size=3, run=run)
    _assert_refusal(result, sc.REASON_STACK_UNREADABLE)


def test_e32_full_size_with_has_next_page_fetches_next_and_refuses():
    page1 = _pull_request(
        pr_number=PR,
        position=1,
        nodes=[_member(1, number=PR)],
        has_next_page=True,
        end_cursor="cursor-1",
        stack_size=1,
    )
    page1["number"] = PR
    page1["stackEntry"]["position"] = 1
    page2 = _pull_request(
        pr_number=PR,
        position=1,
        nodes=[_member(2)],
        has_next_page=False,
        stack_size=1,
    )
    page2["number"] = PR
    page2["stackEntry"]["position"] = 1
    run, calls = _make_run(
        {
            _argv_page(PR, sc.DEFAULT_PAGE_SIZE): _graphql_ok(page1),
            _argv_page(PR, sc.DEFAULT_PAGE_SIZE, "cursor-1"): _graphql_ok(page2),
        }
    )
    result = sc.read_membership(pr=PR, repo=REPO, run=run)
    _assert_refusal(result, sc.REASON_STACK_UNREADABLE)
    assert len(calls) == 2


# --- register E28: not-linked -----------------------------------------------------


def test_e28_stack_entry_null():
    page = {
        "number": PR,
        "baseRefName": STACK_BASE,
        "headRefName": "branch-3",
        "headRefOid": "oid3",
        "stackEntry": None,
    }
    run, _calls = _make_run({_argv_page(PR, sc.DEFAULT_PAGE_SIZE): _graphql_ok(page)})
    result = sc.read_membership(pr=PR, repo=REPO, run=run)
    _assert_refusal(result, sc.REASON_NOT_LINKED)


# --- register E29-E31: order-mismatch -------------------------------------------


def test_e33_collected_count_not_equal_stack_size():
    page = _pull_request(nodes=[_member(1), _member(2)], has_next_page=False, stack_size=5)
    run, _calls = _make_run({_argv_page(PR, 2): _graphql_ok(page)})
    result = sc.read_membership(pr=PR, repo=REPO, page_size=2, run=run)
    _assert_refusal(result, sc.REASON_ORDER_MISMATCH)
    assert result["detail"] == "collected member count does not equal stack size"


def test_e34_collected_positions_not_one_to_size():
    page = _pull_request(
        pr_number=PR,
        position=1,
        nodes=[_member(1, number=PR), _member(3)],
        has_next_page=False,
        stack_size=2,
        head_ref_name="branch-1",
        head_ref_oid="oid1",
    )
    page["number"] = PR
    page["stackEntry"]["position"] = 1
    run, _calls = _make_run({_argv_page(PR, 2): _graphql_ok(page)})
    result = sc.read_membership(pr=PR, repo=REPO, page_size=2, run=run)
    _assert_refusal(result, sc.REASON_ORDER_MISMATCH)
    assert result["detail"] == "collected positions are not exactly 1..size"


def test_e30_collected_positions_not_exact():
    page = _pull_request(
        pr_number=PR,
        position=1,
        nodes=[_member(1, number=PR), _member(3)],
        has_next_page=False,
        stack_size=2,
        head_ref_name="branch-1",
        head_ref_oid="oid1",
    )
    page["number"] = PR
    page["stackEntry"]["position"] = 1
    run, _calls = _make_run({_argv_page(PR, 2): _graphql_ok(page)})
    result = sc.read_membership(pr=PR, repo=REPO, page_size=2, run=run)
    _assert_refusal(result, sc.REASON_ORDER_MISMATCH)
    assert result["detail"] == "collected positions are not exactly 1..size"


def test_e30_queried_pr_not_at_reported_position():
    page = _pull_request(
        pr_number=PR,
        position=3,
        nodes=[_member(1), _member(2)],
        has_next_page=False,
        stack_size=2,
    )
    run, _calls = _make_run({_argv_page(PR, 2): _graphql_ok(page)})
    result = sc.read_membership(pr=PR, repo=REPO, page_size=2, run=run)
    _assert_refusal(result, sc.REASON_ORDER_MISMATCH)


def test_e37_mixed_time_member_head_change_refuses():
    page1_pass1 = _pull_request(
        nodes=[_member(1, headRefOid="old-oid"), _member(2)],
        has_next_page=True,
        end_cursor="cursor-1",
        stack_size=5,
    )
    page2_pass1 = _pull_request(
        nodes=[_member(3, number=PR), _member(4)],
        has_next_page=True,
        end_cursor="cursor-2",
        stack_size=5,
    )
    page3_pass1 = _pull_request(
        nodes=[_member(5)],
        has_next_page=False,
        stack_size=5,
    )
    page1_pass2 = _pull_request(
        nodes=[_member(1, headRefOid="new-oid"), _member(2)],
        has_next_page=True,
        end_cursor="cursor-1",
        stack_size=5,
    )
    run, _calls = _make_run(
        {
            _argv_page(PR, 2): [
                _graphql_ok(page1_pass1),
                _graphql_ok(page1_pass2),
            ],
            _argv_page(PR, 2, "cursor-1"): [
                _graphql_ok(page2_pass1),
                _graphql_ok(page2_pass1),
            ],
            _argv_page(PR, 2, "cursor-2"): [
                _graphql_ok(page3_pass1),
                _graphql_ok(page3_pass1),
            ],
        }
    )
    result = sc.read_membership(pr=PR, repo=REPO, page_size=2, run=run)
    _assert_refusal(result, sc.REASON_ORDER_MISMATCH)
    assert "enumeration passes" in result["detail"]


def test_e31_later_page_snapshot_mismatch():
    page1 = _pull_request(
        nodes=[_member(1), _member(2)],
        has_next_page=True,
        end_cursor="cursor-1",
        stack_size=5,
    )
    page2 = _pull_request(
        nodes=[_member(3, number=PR), _member(4)],
        has_next_page=True,
        end_cursor="cursor-2",
        stack_size=5,
    )
    page2["stackEntry"]["stack"]["number"] = 99
    run, _calls = _make_run(
        {
            _argv_page(PR, 2): _graphql_ok(page1),
            _argv_page(PR, 2, "cursor-1"): _graphql_ok(page2),
        }
    )
    result = sc.read_membership(pr=PR, repo=REPO, page_size=2, run=run)
    _assert_refusal(result, sc.REASON_ORDER_MISMATCH)


# --- happy paths ------------------------------------------------------------------


def test_happy_path_multi_page():
    run, _calls = _make_run(_success_handlers())
    result = sc.read_membership(pr=PR, repo=REPO, page_size=2, run=run)
    assert set(result.keys()) == TOTAL_KEYS
    assert result["ok"] is True
    assert result["reason"] is None
    assert result["detail"] is None
    assert result["pages"] == 3
    assert result["stack"] == {
        "number": STACK_NUMBER,
        "size": STACK_SIZE,
        "baseRefName": STACK_BASE,
    }
    assert result["queried"] == {
        "number": PR,
        "position": 3,
        "headRefName": "branch-3",
        "headRefOid": "oid3",
        "baseRefName": STACK_BASE,
    }
    assert [member["position"] for member in result["members"]] == [1, 2, 3, 4, 5]
    assert result["members"][2]["number"] == PR


def test_happy_path_single_page():
    page = _pull_request(
        pr_number=PR,
        position=1,
        nodes=[_member(1, number=PR)],
        has_next_page=False,
        stack_size=1,
    )
    page["number"] = PR
    page["stackEntry"]["position"] = 1
    run, _calls = _make_run({_argv_page(PR, sc.DEFAULT_PAGE_SIZE): _graphql_ok(page)})
    result = sc.read_membership(pr=PR, repo=REPO, run=run)
    assert result["ok"] is True
    assert result["pages"] == 1
    assert len(result["members"]) == 1


def test_happy_path_expect_stack_matches():
    page = _pull_request(
        pr_number=PR,
        position=1,
        nodes=[_member(1, number=PR)],
        has_next_page=False,
        stack_size=1,
    )
    page["number"] = PR
    page["stackEntry"]["position"] = 1
    run, _calls = _make_run({_argv_page(PR, sc.DEFAULT_PAGE_SIZE): _graphql_ok(page)})
    result = sc.read_membership(pr=PR, repo=REPO, expect_stack=STACK_NUMBER, run=run)
    assert result["ok"] is True
    assert result["reason"] is None


def test_e29_expect_stack_does_not_equal_stack_number():
    page = _pull_request(
        pr_number=PR,
        position=1,
        nodes=[_member(1, number=PR)],
        has_next_page=False,
        stack_size=1,
    )
    page["number"] = PR
    page["stackEntry"]["position"] = 1
    run, _calls = _make_run({_argv_page(PR, sc.DEFAULT_PAGE_SIZE): _graphql_ok(page)})
    result = sc.read_membership(pr=PR, repo=REPO, expect_stack=STACK_NUMBER + 1, run=run)
    _assert_refusal(result, sc.REASON_ORDER_MISMATCH)


def test_e33_queried_entry_head_ref_oid_disagrees():
    page = _pull_request(
        pr_number=PR,
        position=1,
        nodes=[_member(1, number=PR, headRefOid="other-oid")],
        has_next_page=False,
        stack_size=1,
        head_ref_oid="oid1",
    )
    page["number"] = PR
    page["stackEntry"]["position"] = 1
    run, _calls = _make_run({_argv_page(PR, sc.DEFAULT_PAGE_SIZE): _graphql_ok(page)})
    result = sc.read_membership(pr=PR, repo=REPO, run=run)
    _assert_refusal(result, sc.REASON_ORDER_MISMATCH)


def test_e33_queried_entry_base_ref_name_disagrees():
    page = _pull_request(
        pr_number=PR,
        position=1,
        nodes=[_member(1, number=PR, baseRefName="develop")],
        has_next_page=False,
        stack_size=1,
        base_ref_name=STACK_BASE,
    )
    page["number"] = PR
    page["stackEntry"]["position"] = 1
    run, _calls = _make_run({_argv_page(PR, sc.DEFAULT_PAGE_SIZE): _graphql_ok(page)})
    result = sc.read_membership(pr=PR, repo=REPO, run=run)
    _assert_refusal(result, sc.REASON_ORDER_MISMATCH)


# --- argv pinning -----------------------------------------------------------------


def test_argv_pinning():
    run, calls = _make_run(_success_handlers(page_size=2))
    sc.read_membership(pr=PR, repo=REPO, page_size=2, run=run)
    page_one = calls[0]
    page_two = calls[1]
    assert page_one[0:3] == ["gh", "api", "graphql"]
    assert page_two[0:3] == ["gh", "api", "graphql"]
    page_one_after_pairs = [
        page_one[index : index + 2]
        for index, arg in enumerate(page_one)
        if arg == "-f" and page_one[index + 1].startswith("after=")
    ]
    assert page_one_after_pairs == []
    page_two_after_pairs = [
        page_two[index : index + 2]
        for index, arg in enumerate(page_two)
        if arg == "-f" and page_two[index + 1].startswith("after=")
    ]
    assert ["-f", "after=cursor-1"] in page_two_after_pairs
    form_pairs = [page_one[index : index + 2] for index, arg in enumerate(page_one) if arg == "-F"]
    assert ["-F", "owner=owner"] in form_pairs
    assert ["-F", "repo=example"] in form_pairs
    assert ["-F", "pr=103"] in form_pairs
    assert ["-F", "first=2"] in form_pairs
    query_pairs = [page_one[index : index + 2] for index, arg in enumerate(page_one) if arg == "-f"]
    assert ["-f", "query=%s" % sc.QUERY] in query_pairs


# --- CLI projection ---------------------------------------------------------------


def test_cli_success_projection(capsys, monkeypatch):
    real_read = sc.read_membership
    direct_run, _calls = _make_run(_success_handlers(page_size=2))
    direct = real_read(pr=PR, repo=REPO, page_size=2, run=direct_run)
    cli_run, _calls = _make_run(_success_handlers(page_size=2))
    monkeypatch.setattr(
        sc,
        "read_membership",
        lambda **kwargs: real_read(**dict(kwargs, run=cli_run)),
    )
    rc = sc.main(["list", "--pr", str(PR), "--repo", REPO, "--page-size", "2"])
    out = capsys.readouterr().out
    printed = json.loads(out)
    assert rc == 0
    assert printed == direct


def test_cli_refusal_projection(capsys, monkeypatch):
    monkeypatch.setattr(sc.shutil, "which", lambda _name: None)
    rc = sc.main(["list", "--pr", str(PR), "--repo", REPO])
    out = capsys.readouterr().out
    direct = sc.read_membership(pr=PR, repo=REPO, run=lambda *a, **k: None)
    printed = json.loads(out)
    assert rc == 1
    assert printed == direct


@pytest.mark.parametrize(
    "argv",
    [
        [],
        ["bogus"],
        ["list", "--pr", "1", "--repo", "o/r", "extra"],
        ["list", "--pr", "x", "--repo", "o/r"],
    ],
)
def test_cli_bad_argument_cases(capsys, argv):
    rc = sc.main(argv)
    out = capsys.readouterr().out
    result = json.loads(out)
    _assert_refusal(result, sc.REASON_BAD_ARGUMENT)
    assert rc == 1
    assert "usage:" not in out.lower()


# --- register E39-E41: read budget (WO #1340 layer 2b R1) -----------------------


def test_deadline_not_a_number_refuses():
    for bad_deadline in ("5", True):
        result = sc.read_membership(
            pr=PR, repo=REPO, deadline=bad_deadline, run=lambda *a, **k: None,
        )
        _assert_refusal(result, sc.REASON_BAD_ARGUMENT)


@pytest.mark.parametrize("bad_deadline", [0, -1, float("nan")])
def test_deadline_not_positive_refuses(bad_deadline):
    result = sc.read_membership(
        pr=PR, repo=REPO, deadline=bad_deadline, run=lambda *a, **k: None,
    )
    _assert_refusal(result, sc.REASON_BAD_ARGUMENT)


def test_deadline_exhausted_in_second_pass_refuses(monkeypatch):
    budget = 100.0
    times = [0, 1, 2, 3, 4, 5, 6, 100]
    index = 0

    def fake_monotonic():
        nonlocal index
        value = times[index] if index < len(times) else times[-1]
        index += 1
        return value

    monkeypatch.setattr(sc.time, "monotonic", fake_monotonic)
    run, _calls = _make_run(_success_handlers(page_size=2))
    result = sc.read_membership(pr=PR, repo=REPO, page_size=2, deadline=budget, run=run)
    _assert_refusal(result, sc.REASON_STACK_UNREADABLE)
    assert str(budget) in result["detail"] or ("%g" % budget) in result["detail"]
    assert result["members"] == []


def test_effective_timeout_is_bounded_by_remaining_budget(monkeypatch):
    budget = 50.0
    times = [0, 39, 40]
    index = 0

    def fake_monotonic():
        nonlocal index
        value = times[index] if index < len(times) else times[-1]
        index += 1
        return value

    monkeypatch.setattr(sc.time, "monotonic", fake_monotonic)
    page = _pull_request(
        pr_number=PR,
        position=1,
        nodes=[_member(1, number=PR)],
        has_next_page=False,
        stack_size=1,
    )
    page["number"] = PR
    page["stackEntry"]["position"] = 1
    run, _calls = _make_run({_argv_page(PR, sc.DEFAULT_PAGE_SIZE): _graphql_ok(page)})
    sc.read_membership(pr=PR, repo=REPO, timeout=120, deadline=budget, run=run)
    assert run.kw_calls[0]["timeout"] == 10.0


def test_deadline_none_leaves_timeout_untouched():
    page = _pull_request(
        pr_number=PR,
        position=1,
        nodes=[_member(1, number=PR)],
        has_next_page=False,
        stack_size=1,
    )
    page["number"] = PR
    page["stackEntry"]["position"] = 1
    run, _calls = _make_run({_argv_page(PR, sc.DEFAULT_PAGE_SIZE): _graphql_ok(page)})
    sc.read_membership(pr=PR, repo=REPO, timeout=120, deadline=None, run=run)
    assert run.kw_calls[0]["timeout"] == 120


# --- WO #1340 layer 2c: tagged return pairs (membership read path) ----------------


PINNED_MULTI_PAGE_SUCCESS = {
    "ok": True,
    "reason": None,
    "detail": None,
    "repo": REPO,
    "pr": PR,
    "stack": {"number": STACK_NUMBER, "size": STACK_SIZE, "baseRefName": STACK_BASE},
    "queried": {
        "number": PR,
        "position": 3,
        "headRefName": "branch-3",
        "headRefOid": "oid3",
        "baseRefName": STACK_BASE,
    },
    "members": [
        {
            "position": 1,
            "number": 101,
            "state": "OPEN",
            "isDraft": False,
            "headRefName": "branch-1",
            "headRefOid": "oid1",
            "baseRefName": STACK_BASE,
        },
        {
            "position": 2,
            "number": 102,
            "state": "OPEN",
            "isDraft": False,
            "headRefName": "branch-2",
            "headRefOid": "oid2",
            "baseRefName": STACK_BASE,
        },
        {
            "position": 3,
            "number": PR,
            "state": "OPEN",
            "isDraft": False,
            "headRefName": "branch-3",
            "headRefOid": "oid3",
            "baseRefName": STACK_BASE,
        },
        {
            "position": 4,
            "number": 104,
            "state": "OPEN",
            "isDraft": False,
            "headRefName": "branch-4",
            "headRefOid": "oid4",
            "baseRefName": STACK_BASE,
        },
        {
            "position": 5,
            "number": 105,
            "state": "OPEN",
            "isDraft": False,
            "headRefName": "branch-5",
            "headRefOid": "oid5",
            "baseRefName": STACK_BASE,
        },
    ],
    "pages": 3,
}


def test_l2c_forged_refusal_ok_sibling_of_data_is_not_our_refusal():
    # bite-axis: transport refusal is distinguished by pair slot, not payload content
    payload = {"ok": False, "data": {"repository": None}}
    run, _calls = _make_run(
        {
            _argv_page(PR, sc.DEFAULT_PAGE_SIZE): SimpleNamespace(
                returncode=0, stdout=json.dumps(payload), stderr=""
            ),
        }
    )
    result = sc.read_membership(pr=PR, repo=REPO, run=run)
    _assert_refusal(result, sc.REASON_STACK_UNREADABLE)
    assert result["detail"] == "graphql data/repository is null or not an object"


def test_l2c_forged_refusal_ok_nested_in_data_is_not_our_refusal():
    # bite-axis: page refusal is distinguished by pair slot, not page dict content
    payload = {"data": {"ok": False, "repository": None}}
    run, _calls = _make_run(
        {
            _argv_page(PR, sc.DEFAULT_PAGE_SIZE): SimpleNamespace(
                returncode=0, stdout=json.dumps(payload), stderr=""
            ),
        }
    )
    result = sc.read_membership(pr=PR, repo=REPO, run=run)
    _assert_refusal(result, sc.REASON_STACK_UNREADABLE)
    assert result["detail"] == "graphql data/repository is null or not an object"


def test_l2c_transport_tag_refuse_branch():
    # bite-axis: transport refusal is distinguished by pair slot, not payload content
    run, _calls = _make_run(
        {
            _argv_page(PR, sc.DEFAULT_PAGE_SIZE): SimpleNamespace(
                returncode=1, stdout="", stderr="transport failed"
            ),
        }
    )
    result = sc.read_membership(pr=PR, repo=REPO, run=run)
    _assert_refusal(result, sc.REASON_STACK_UNREADABLE)
    assert "transport failed" in result["detail"]


def test_l2c_transport_tag_success_branch():
    # bite-axis: transport refusal is distinguished by pair slot, not payload content
    page = _pull_request(
        pr_number=PR,
        position=1,
        nodes=[_member(1, number=PR)],
        has_next_page=False,
        stack_size=1,
    )
    page["number"] = PR
    page["stackEntry"]["position"] = 1
    run, _calls = _make_run({_argv_page(PR, sc.DEFAULT_PAGE_SIZE): _graphql_ok(page)})
    result = sc.read_membership(pr=PR, repo=REPO, run=run)
    assert result["ok"] is True


def test_l2c_parse_tag_refuse_branch():
    # bite-axis: page refusal is distinguished by pair slot, not page dict content
    payload = {"data": {"repository": None}}
    run, _calls = _make_run(
        {
            _argv_page(PR, sc.DEFAULT_PAGE_SIZE): SimpleNamespace(
                returncode=0, stdout=json.dumps(payload), stderr=""
            ),
        }
    )
    result = sc.read_membership(pr=PR, repo=REPO, run=run)
    _assert_refusal(result, sc.REASON_STACK_UNREADABLE)
    assert result["detail"] == "graphql data/repository is null or not an object"


def test_l2c_parse_tag_success_branch():
    # bite-axis: page refusal is distinguished by pair slot, not page dict content
    page = _pull_request(
        pr_number=PR,
        position=1,
        nodes=[_member(1, number=PR)],
        has_next_page=False,
        stack_size=1,
    )
    page["number"] = PR
    page["stackEntry"]["position"] = 1
    run, _calls = _make_run({_argv_page(PR, sc.DEFAULT_PAGE_SIZE): _graphql_ok(page)})
    result = sc.read_membership(pr=PR, repo=REPO, run=run)
    assert result["ok"] is True
    assert result["pages"] == 1


def test_l2c_invariant_tag_refuse_branch():
    # bite-axis: invariant outcome is distinguished by explicit tag, not result shape
    page = _pull_request(
        pr_number=PR,
        position=1,
        nodes=[_member(1, number=PR)],
        has_next_page=False,
        stack_size=1,
    )
    page["number"] = PR
    page["stackEntry"]["position"] = 1
    run, _calls = _make_run({_argv_page(PR, sc.DEFAULT_PAGE_SIZE): _graphql_ok(page)})
    result = sc.read_membership(pr=PR, repo=REPO, expect_stack=STACK_NUMBER + 1, run=run)
    _assert_refusal(result, sc.REASON_ORDER_MISMATCH)
    assert result["detail"] == "expect_stack does not equal stack number"


def test_l2c_invariant_tag_success_branch():
    # bite-axis: invariant outcome is distinguished by explicit tag, not result shape
    run, _calls = _make_run(_success_handlers(page_size=2))
    result = sc.read_membership(pr=PR, repo=REPO, page_size=2, run=run)
    assert result == PINNED_MULTI_PAGE_SUCCESS


def test_deadline_with_timeout_none_returns_dict_not_typeerror():
    budget = 50.0
    page = _pull_request(
        pr_number=PR,
        position=1,
        nodes=[_member(1, number=PR)],
        has_next_page=False,
        stack_size=1,
    )
    page["number"] = PR
    page["stackEntry"]["position"] = 1
    run, _calls = _make_run({_argv_page(PR, sc.DEFAULT_PAGE_SIZE): _graphql_ok(page)})
    result = sc.read_membership(
        pr=PR, repo=REPO, timeout=None, deadline=budget, run=run,
    )
    assert set(result.keys()) == TOTAL_KEYS
    assert result["ok"] is True


# --- layer 2d: resolve_repo_slug ------------------------------------------------


REPO_ROOT = "/tmp/example-repo"


def _repo_slug_argv():
    return tuple(sc._repo_slug_argv())


def _repo_slug_ok(name_with_owner=REPO):
    return SimpleNamespace(
        returncode=0,
        stdout=json.dumps({"nameWithOwner": name_with_owner}),
        stderr="",
    )


def _assert_read_refusal(refusal, reason):
    assert refusal == {"ok": False, "reason": reason, "detail": refusal["detail"]}
    assert isinstance(refusal["detail"], str)
    assert refusal["detail"]


def test_l2d_resolve_repo_slug_run_raises():
    # axis: run raises any exception
    def _run(*args, **kwargs):
        raise OSError("boom")

    slug, refusal = sc.resolve_repo_slug(REPO_ROOT, run=_run)
    assert slug is None
    _assert_read_refusal(refusal, sc.REASON_STACK_UNREADABLE)
    assert refusal["detail"] == "boom"


def test_l2d_resolve_repo_slug_nonzero_exit():
    # axis: non-zero return code
    run, calls = _make_run({_repo_slug_argv(): SimpleNamespace(returncode=1, stdout="", stderr="nope")})
    slug, refusal = sc.resolve_repo_slug(REPO_ROOT, run=run)
    assert slug is None
    _assert_read_refusal(refusal, sc.REASON_STACK_UNREADABLE)
    assert "nope" in refusal["detail"]
    assert calls[0] == list(_repo_slug_argv())


def test_l2d_resolve_repo_slug_stdout_not_json():
    # axis: stdout is not JSON
    run, _calls = _make_run(
        {_repo_slug_argv(): SimpleNamespace(returncode=0, stdout="not-json", stderr="")}
    )
    slug, refusal = sc.resolve_repo_slug(REPO_ROOT, run=run)
    assert slug is None
    _assert_read_refusal(refusal, sc.REASON_STACK_UNREADABLE)


def test_l2d_resolve_repo_slug_json_not_object():
    # axis: JSON is not an object
    run, _calls = _make_run(
        {_repo_slug_argv(): SimpleNamespace(returncode=0, stdout=json.dumps([]), stderr="")}
    )
    slug, refusal = sc.resolve_repo_slug(REPO_ROOT, run=run)
    assert slug is None
    _assert_read_refusal(refusal, sc.REASON_STACK_UNREADABLE)


def test_l2d_resolve_repo_slug_name_with_owner_missing():
    # axis: nameWithOwner missing, not a string, or empty
    run, _calls = _make_run(
        {_repo_slug_argv(): SimpleNamespace(returncode=0, stdout=json.dumps({}), stderr="")}
    )
    slug, refusal = sc.resolve_repo_slug(REPO_ROOT, run=run)
    assert slug is None
    _assert_read_refusal(refusal, sc.REASON_STACK_UNREADABLE)


def test_l2d_resolve_repo_slug_name_with_owner_bad_pattern():
    # axis: nameWithOwner present but not matching _REPO_RE
    run, _calls = _make_run({_repo_slug_argv(): _repo_slug_ok("bad repo")})
    slug, refusal = sc.resolve_repo_slug(REPO_ROOT, run=run)
    assert slug is None
    _assert_read_refusal(refusal, sc.REASON_STACK_UNREADABLE)


def test_l2d_resolve_repo_slug_deadline_exhausted(monkeypatch):
    # axis: deadline supplied and already exhausted — refuse without calling gh
    times = [100.0, 105.0]
    index = 0

    def fake_monotonic():
        nonlocal index
        value = times[index] if index < len(times) else times[-1]
        index += 1
        return value

    monkeypatch.setattr(sc.time, "monotonic", fake_monotonic)
    run, calls = _make_run({_repo_slug_argv(): _repo_slug_ok()})
    slug, refusal = sc.resolve_repo_slug(REPO_ROOT, deadline=5.0, run=run)
    assert slug is None
    _assert_read_refusal(refusal, sc.REASON_STACK_UNREADABLE)
    assert calls == []


def test_l2d_resolve_repo_slug_deadline_caps_timeout(monkeypatch):
    # axis: deadline supplied and smaller than timeout — call uses the smaller value
    times = [100.0, 100.5, 100.5]
    index = 0

    def fake_monotonic():
        nonlocal index
        value = times[index] if index < len(times) else times[-1]
        index += 1
        return value

    monkeypatch.setattr(sc.time, "monotonic", fake_monotonic)
    run, _calls = _make_run({_repo_slug_argv(): _repo_slug_ok()})
    slug, refusal = sc.resolve_repo_slug(REPO_ROOT, deadline=2.0, timeout=120.0, run=run)
    assert slug == REPO
    assert refusal is None
    assert run.kw_calls[0]["timeout"] == pytest.approx(1.5)


def test_l2d_resolve_repo_slug_bad_repo_root():
    slug, refusal = sc.resolve_repo_slug("", run=lambda *a, **k: None)
    assert slug is None
    _assert_read_refusal(refusal, sc.REASON_BAD_ARGUMENT)


def test_l2d_resolve_repo_slug_happy_path():
    run, calls = _make_run({_repo_slug_argv(): _repo_slug_ok()})
    slug, refusal = sc.resolve_repo_slug(REPO_ROOT, run=run)
    assert slug == REPO
    assert refusal is None
    assert calls[0] == list(_repo_slug_argv())
    assert run.kw_calls[0]["cwd"] == REPO_ROOT


def test_l2d_resolve_repo_slug_gh_not_on_path(monkeypatch):
    # axis: gh is not on PATH
    monkeypatch.setattr(sc.shutil, "which", lambda _name: None)
    slug, refusal = sc.resolve_repo_slug(REPO_ROOT, run=lambda *a, **k: None)
    assert slug is None
    _assert_read_refusal(refusal, sc.REASON_STACK_UNREADABLE)
    assert refusal["detail"] == "gh not on PATH"


def test_l2d_resolve_repo_slug_run_raises_timeout_expired():
    # axis: run raises subprocess.TimeoutExpired
    def _run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="gh", timeout=120)

    slug, refusal = sc.resolve_repo_slug(REPO_ROOT, run=_run)
    assert slug is None
    _assert_read_refusal(refusal, sc.REASON_STACK_UNREADABLE)
    assert refusal["detail"] == "gh call timed out"


# --- WO #1340 layer 2f: read_vet_verdict ------------------------------------------------


import grounding_stage as gs  # noqa: E402

HEAD_SHA = "abcdef0123456789abcdef0123456789abcdef01"
OTHER_SHA = "1234567890abcdef1234567890abcdef12345678"
VET_MARKER = gs.REGION_MARKERS["advisor-vet"]


def _vet_body(*lines_after_marker):
    return VET_MARKER + "\n" + "\n".join(lines_after_marker)


def _assert_vet_not_ready(body, head_sha=HEAD_SHA):
    verdict, refusal = sc.read_vet_verdict(body, head_sha)
    assert verdict == sc.VET_NOT_READY
    assert refusal is None


def _assert_vet_verdict(body, expected, head_sha=HEAD_SHA):
    verdict, refusal = sc.read_vet_verdict(body, head_sha)
    assert verdict == expected
    assert refusal is None


def _assert_vet_refusal(body, head_sha, reason):
    verdict, refusal = sc.read_vet_verdict(body, head_sha)
    assert verdict is None
    _assert_read_refusal(refusal, reason)


def test_l2f_v1_no_marker():
    # axis: no advisor-vet marker in the body at all
    _assert_vet_not_ready("## Advisor vet\n\nNo marker here.\n")


def test_l2f_v2_marker_whitespace_only():
    # axis: marker present with nothing but whitespace after it
    _assert_vet_not_ready(_vet_body("", "   ", ""))


def test_l2f_v3_marker_prose_line():
    # axis: marker present, first non-empty line is ordinary prose
    _assert_vet_not_ready(_vet_body("This PR looks good to merge."))


def test_l2f_v4_unknown_verdict_word():
    # axis: unknown verdict word
    _assert_vet_not_ready(_vet_body("**Verdict: SHIPPED** · %s" % HEAD_SHA))


def test_l2f_v5_negated_verdict_spelling():
    # axis: space-separated negation
    _assert_vet_not_ready(_vet_body("**Verdict: NOT READY** · %s" % HEAD_SHA))


def test_l2f_v6_two_tokens_on_line():
    # axis: more than one token on the line
    _assert_vet_not_ready(
        _vet_body("**Verdict: READY** · %s **Verdict: PARKED**" % HEAD_SHA)
    )


def test_l2f_v7_well_formed_token_no_sha():
    # axis: well-formed token with no sha at all
    _assert_vet_not_ready(_vet_body("**Verdict: READY**"))


def test_l2f_v8_sha_39_hex_chars():
    # axis: sha of 39 hex characters
    _assert_vet_not_ready(_vet_body("**Verdict: READY** · %s" % HEAD_SHA[:39]))


def test_l2f_v9_sha_41_hex_chars():
    # axis: sha of 41 hex characters
    _assert_vet_not_ready(_vet_body("**Verdict: READY** · %s0" % HEAD_SHA))


def test_l2f_v10_sha_non_hex_char():
    # axis: 40-character sha containing a non-hex character
    bad_sha = HEAD_SHA[:39] + "g"
    _assert_vet_not_ready(_vet_body("**Verdict: READY** · %s" % bad_sha))


def test_l2f_v11_sha_differs_from_head():
    # axis: well-formed line whose sha differs from head_sha
    _assert_vet_not_ready(_vet_body("**Verdict: READY** · %s" % OTHER_SHA))


def test_l2f_v12_duplicated_marker():
    # axis: two live advisor-vet markers in one body
    body = (
        _vet_body("**Verdict: READY** · %s" % HEAD_SHA)
        + "\n\n"
        + _vet_body("**Verdict: READY** · %s" % HEAD_SHA)
    )
    _assert_vet_not_ready(body)


def test_l2f_v13_parked_details_ready_bypass():
    # axis: PARKED slot with READY FOR PR inside details — never VERDICT_READY
    body = _vet_body(
        "**Verdict: PARKED** · %s" % HEAD_SHA,
        "<details>",
        "<summary>notes</summary>",
        "READY FOR PR",
        "</details>",
    )
    _assert_vet_verdict(body, sc.VERDICT_PARKED)


def test_l2f_v14_fenced_ready_bypass():
    # axis: well-formed READY line only inside a fenced block
    body = _vet_body(
        "~~~",
        "**Verdict: READY** · %s" % HEAD_SHA,
        "~~~",
    )
    _assert_vet_not_ready(body)


def test_l2f_v15_unterminated_fence_bypass():
    # axis: unterminated fence opener followed by well-formed READY line
    body = _vet_body(
        "~~~",
        "**Verdict: READY** · %s" % HEAD_SHA,
    )
    _assert_vet_not_ready(body)


def test_l2f_v16_head_sha_only_in_fence():
    # axis: head sha only inside fenced region, first line carries different sha
    body = _vet_body(
        "**Verdict: READY** · %s" % OTHER_SHA,
        "~~~",
        HEAD_SHA,
        "~~~",
    )
    _assert_vet_not_ready(body)


def test_l2f_v17_token_not_at_line_start():
    # axis: token preceded by other text on the same line
    _assert_vet_not_ready(_vet_body("Vetted: **Verdict: READY** · %s" % HEAD_SHA))


def test_l2f_v18_wrong_separator():
    # axis: right token and sha with wrong separator
    _assert_vet_not_ready(_vet_body("**Verdict: READY** %s" % HEAD_SHA))
    _assert_vet_not_ready(_vet_body("**Verdict: READY** - %s" % HEAD_SHA))


def test_l2f_v19_lowercase_token():
    # axis: lowercase verdict token
    _assert_vet_not_ready(_vet_body("**verdict: ready** · %s" % HEAD_SHA))


def test_l2f_v20_blockquote_token():
    # axis: token inside blockquote as first non-empty line
    _assert_vet_not_ready(_vet_body("> **Verdict: READY** · %s" % HEAD_SHA))


def test_l2f_v21_ready_exact():
    # axis: well-formed READY line pinned to head_sha
    _assert_vet_verdict(_vet_body("**Verdict: READY** · %s" % HEAD_SHA), sc.VERDICT_READY)


def test_l2f_v22_ready_with_qualifiers():
    # axis: READY with trailing qualifiers on the same line
    _assert_vet_verdict(
        _vet_body("**Verdict: READY** · %s as a layer — held with the stack" % HEAD_SHA),
        sc.VERDICT_READY,
    )


def test_l2f_v23_not_ready_exact():
    # axis: well-formed NOT-READY line pinned to head_sha
    _assert_vet_verdict(_vet_body("**Verdict: NOT-READY** · %s" % HEAD_SHA), sc.VERDICT_NOT_READY)


def test_l2f_v24_parked_exact():
    # axis: well-formed PARKED line pinned to head_sha
    _assert_vet_verdict(_vet_body("**Verdict: PARKED** · %s" % HEAD_SHA), sc.VERDICT_PARKED)


def test_l2f_v25_uppercase_sha_matches_lowercase_head():
    # axis: upper-case-hex sha equal to lower-case-hex head_sha
    upper_sha = HEAD_SHA.upper()
    _assert_vet_verdict(
        _vet_body("**Verdict: READY** · %s" % upper_sha),
        sc.VERDICT_READY,
        head_sha=HEAD_SHA.lower(),
    )


def test_l2f_v26_body_none_refuses():
    # axis: body is None
    _assert_vet_refusal(None, HEAD_SHA, sc.REASON_VET_UNREADABLE)


def test_l2f_v27_body_not_string_refuses():
    # axis: body is not a string
    _assert_vet_refusal(123, HEAD_SHA, sc.REASON_VET_UNREADABLE)


def test_l2f_v28_head_sha_short_refuses():
    # axis: head_sha is not 40 hex characters
    _assert_vet_refusal(_vet_body("**Verdict: READY** · %s" % HEAD_SHA), "short", sc.REASON_BAD_ARGUMENT)


def test_l2f_v29_head_sha_none_refuses():
    # axis: head_sha is None
    _assert_vet_refusal(_vet_body("**Verdict: READY** · %s" % HEAD_SHA), None, sc.REASON_BAD_ARGUMENT)


def test_l2f_v30_vet_form_missing_refuses(monkeypatch):
    # axis: missing vet-verdict-form.json refuses vet-unreadable, never READY
    monkeypatch.setattr(sc, "_vet_verdict_form_path", lambda: "/nonexistent/vet-verdict-form.json")
    sc._reset_vet_verdict_form_cache()
    _assert_vet_refusal(
        _vet_body("**Verdict: READY** · %s" % HEAD_SHA),
        HEAD_SHA,
        sc.REASON_VET_UNREADABLE,
    )


def _write_vet_form(path, tokens):
    import json

    payload = {
        "schema": "vet-verdict-form/1",
        "separator": " · ",
        "tokens": tokens,
    }
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


_VALID_VET_FORM_TOKENS = [
    {"token": "**Verdict: READY**", "verdict": sc.VERDICT_READY},
    {"token": "**Verdict: NOT-READY**", "verdict": sc.VERDICT_NOT_READY},
    {"token": "**Verdict: PARKED**", "verdict": sc.VERDICT_PARKED},
]


def _patch_vet_form(monkeypatch, tmp_path, tokens):
    form_path = tmp_path / "vet-verdict-form.json"
    _write_vet_form(form_path, tokens)
    monkeypatch.setattr(sc, "_vet_verdict_form_path", lambda: str(form_path))
    sc._reset_vet_verdict_form_cache()


def test_l2f_v31_vet_form_unknown_verdict_refuses(monkeypatch, tmp_path):
    # axis: unknown verdict value in the form refuses vet-unreadable
    tokens = list(_VALID_VET_FORM_TOKENS)
    tokens[0] = {"token": "**Verdict: READY**", "verdict": "SHIPPED"}
    _patch_vet_form(monkeypatch, tmp_path, tokens)
    _assert_vet_refusal(
        _vet_body("**Verdict: READY** · %s" % HEAD_SHA),
        HEAD_SHA,
        sc.REASON_VET_UNREADABLE,
    )


def test_l2f_v32_vet_form_duplicate_verdict_refuses(monkeypatch, tmp_path):
    # axis: duplicated verdict value in the form refuses vet-unreadable
    tokens = list(_VALID_VET_FORM_TOKENS)
    tokens[2] = {"token": "**Verdict: PARKED**", "verdict": sc.VERDICT_READY}
    _patch_vet_form(monkeypatch, tmp_path, tokens)
    _assert_vet_refusal(
        _vet_body("**Verdict: READY** · %s" % HEAD_SHA),
        HEAD_SHA,
        sc.REASON_VET_UNREADABLE,
    )


def test_l2f_v33_vet_form_missing_verdict_refuses(monkeypatch, tmp_path):
    # axis: missing member of the verdict vocabulary refuses vet-unreadable
    tokens = _VALID_VET_FORM_TOKENS[:2]
    _patch_vet_form(monkeypatch, tmp_path, tokens)
    _assert_vet_refusal(
        _vet_body("**Verdict: READY** · %s" % HEAD_SHA),
        HEAD_SHA,
        sc.REASON_VET_UNREADABLE,
    )


# --- WO #1340 layer 2f: read_pr_vet_state ----------------------------------------------


DEP_PR = 701


def _pr_vet_argv():
    return tuple(sc._pr_vet_state_argv(DEP_PR, REPO))


def _pr_vet_ok(
    head_ref_oid=HEAD_SHA,
    state="OPEN",
    is_draft=False,
    body="",
):
    return SimpleNamespace(
        returncode=0,
        stdout=json.dumps({
            "state": state,
            "isDraft": is_draft,
            "headRefOid": head_ref_oid,
            "body": body,
        }),
        stderr="",
    )


def test_l2f_read_pr_vet_state_happy_path():
    # axis: well-formed payload returns every field
    body = "vet body"
    run, calls = _make_run({_pr_vet_argv(): _pr_vet_ok(body=body)})
    state, refusal = sc.read_pr_vet_state(DEP_PR, REPO, run=run)
    assert refusal is None
    assert state == {
        "number": DEP_PR,
        "state": "OPEN",
        "isDraft": False,
        "headRefOid": HEAD_SHA,
        "body": body,
    }
    assert calls[0] == list(_pr_vet_argv())


def test_l2f_read_pr_vet_state_nonzero_exit():
    # axis: gh exits non-zero
    run, _calls = _make_run(
        {_pr_vet_argv(): SimpleNamespace(returncode=1, stdout="", stderr="nope")}
    )
    state, refusal = sc.read_pr_vet_state(DEP_PR, REPO, run=run)
    assert state is None
    _assert_read_refusal(refusal, sc.REASON_STACK_UNREADABLE)


def test_l2f_read_pr_vet_state_stdout_not_json():
    # axis: stdout is not JSON
    run, _calls = _make_run(
        {_pr_vet_argv(): SimpleNamespace(returncode=0, stdout="not-json", stderr="")}
    )
    state, refusal = sc.read_pr_vet_state(DEP_PR, REPO, run=run)
    assert state is None
    _assert_read_refusal(refusal, sc.REASON_STACK_UNREADABLE)


def test_l2f_read_pr_vet_state_missing_state_key():
    # axis: a required key is missing
    run, _calls = _make_run(
        {_pr_vet_argv(): SimpleNamespace(
            returncode=0,
            stdout=json.dumps({"isDraft": False, "headRefOid": HEAD_SHA, "body": ""}),
            stderr="",
        )}
    )
    state, refusal = sc.read_pr_vet_state(DEP_PR, REPO, run=run)
    assert state is None
    _assert_read_refusal(refusal, sc.REASON_STACK_UNREADABLE)


def test_l2f_read_pr_vet_state_is_draft_not_boolean():
    # axis: isDraft is not a boolean
    run, _calls = _make_run(
        {_pr_vet_argv(): SimpleNamespace(
            returncode=0,
            stdout=json.dumps({
                "state": "OPEN",
                "isDraft": "false",
                "headRefOid": HEAD_SHA,
                "body": "",
            }),
            stderr="",
        )}
    )
    state, refusal = sc.read_pr_vet_state(DEP_PR, REPO, run=run)
    assert state is None
    _assert_read_refusal(refusal, sc.REASON_STACK_UNREADABLE)


def test_l2f_read_pr_vet_state_head_ref_oid_not_40_hex():
    # axis: headRefOid is not 40 hex
    run, _calls = _make_run(
        {_pr_vet_argv(): _pr_vet_ok(head_ref_oid="short")}
    )
    state, refusal = sc.read_pr_vet_state(DEP_PR, REPO, run=run)
    assert state is None
    _assert_read_refusal(refusal, sc.REASON_STACK_UNREADABLE)


def test_l2f_read_pr_vet_state_deadline_exhausted(monkeypatch):
    # axis: exhausted deadline — no gh call made
    times = [100.0, 105.0]
    index = 0

    def fake_monotonic():
        nonlocal index
        value = times[index] if index < len(times) else times[-1]
        index += 1
        return value

    monkeypatch.setattr(sc.time, "monotonic", fake_monotonic)
    run, calls = _make_run({_pr_vet_argv(): _pr_vet_ok()})

    def _fail_run(*args, **kwargs):
        raise AssertionError("gh should not run when deadline is exhausted")

    state, refusal = sc.read_pr_vet_state(
        DEP_PR, REPO, deadline=5.0, run=_fail_run,
    )
    assert state is None
    _assert_read_refusal(refusal, sc.REASON_STACK_UNREADABLE)
    assert calls == []


def test_l2f_read_pr_vet_state_gh_not_on_path(monkeypatch):
    # axis: gh is not on PATH
    monkeypatch.setattr(sc.shutil, "which", lambda name: None)
    state, refusal = sc.read_pr_vet_state(DEP_PR, REPO)
    assert state is None
    _assert_read_refusal(refusal, sc.REASON_STACK_UNREADABLE)


def test_l2f_read_pr_vet_state_timeout_expired():
    # axis: run raises subprocess.TimeoutExpired
    def _run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=args[0], timeout=1)

    state, refusal = sc.read_pr_vet_state(DEP_PR, REPO, run=_run)
    assert state is None
    _assert_read_refusal(refusal, sc.REASON_STACK_UNREADABLE)


def test_l2f_read_pr_vet_state_unrecognised_state():
    # axis: unrecognised state value refuses stack-unreadable
    run, _calls = _make_run(
        {_pr_vet_argv(): _pr_vet_ok(state="UNKNOWN")}
    )
    state, refusal = sc.read_pr_vet_state(DEP_PR, REPO, run=run)
    assert state is None
    _assert_read_refusal(refusal, sc.REASON_STACK_UNREADABLE)
    assert "UNKNOWN" in refusal["detail"]
    assert "enumerated" in refusal["detail"]


def test_l2f_read_pr_vet_state_lowercase_open_refuses():
    # axis: case-sensitive allowlist — lowercase open is not OPEN
    run, _calls = _make_run(
        {_pr_vet_argv(): _pr_vet_ok(state="open")}
    )
    state, refusal = sc.read_pr_vet_state(DEP_PR, REPO, run=run)
    assert state is None
    _assert_read_refusal(refusal, sc.REASON_STACK_UNREADABLE)
    assert "open" in refusal["detail"]


def test_l2f_read_pr_vet_state_merged_accepted():
    # axis: MERGED is a legal GitHub state
    run, _calls = _make_run(
        {_pr_vet_argv(): _pr_vet_ok(state="MERGED")}
    )
    state, refusal = sc.read_pr_vet_state(DEP_PR, REPO, run=run)
    assert refusal is None
    assert state["state"] == "MERGED"


def test_l2f_read_pr_vet_state_closed_accepted():
    # axis: CLOSED is a legal GitHub state
    run, _calls = _make_run(
        {_pr_vet_argv(): _pr_vet_ok(state="CLOSED")}
    )
    state, refusal = sc.read_pr_vet_state(DEP_PR, REPO, run=run)
    assert refusal is None
    assert state["state"] == "CLOSED"
