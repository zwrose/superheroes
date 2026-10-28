"""Fake-based units for stack_check.py. No real gh or network — every gh call is faked."""
import copy
import json
import subprocess
from pathlib import Path
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


# --- WO #1340 layer 2g: same_commit -----------------------------------------------------


def test_same_commit_mixed_case_equal():
    sha = "abcdef0123456789abcdef0123456789abcdef01"
    assert sc.same_commit(sha, sha.upper()) is True


def test_same_commit_different_shas():
    a = "abcdef0123456789abcdef0123456789abcdef01"
    b = "1234567890abcdef1234567890abcdef12345678"
    assert sc.same_commit(a, b) is False


@pytest.mark.parametrize(
    "left,right",
    [
        (None, "abcdef0123456789abcdef0123456789abcdef01"),
        ("abcdef0123456789abcdef0123456789abcdef01", None),
        (42, "abcdef0123456789abcdef0123456789abcdef01"),
        ("abcdef0123456789abcdef0123456789abcdef01", 42),
        (b"abcdef0123456789abcdef0123456789abcdef01", "abcdef0123456789abcdef0123456789abcdef01"),
        ("abcdef0123456789abcdef0123456789abcdef01", b"abcdef0123456789abcdef0123456789abcdef01"),
    ],
)
def test_same_commit_non_str_operand_returns_false(left, right):
    assert sc.same_commit(left, right) is False


# --- WO #1340 layer 2f: read_vet_verdict ------------------------------------------------


import pr_body_regions as regions  # noqa: E402

HEAD_SHA = "abcdef0123456789abcdef0123456789abcdef01"
OTHER_SHA = "1234567890abcdef1234567890abcdef12345678"
VET_MARKER = regions.REGION_MARKERS["advisor-vet"]


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


@pytest.fixture(autouse=True)
def _vet_verdict_form_cache_reset(request):
    if "vet_form" in request.node.name:
        sc._reset_vet_verdict_form_cache()
        yield
        sc._reset_vet_verdict_form_cache()
    else:
        yield


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
    tokens = list(_VALID_VET_FORM_TOKENS) + [
        {"token": "**Verdict: SHIPPED**", "verdict": "SHIPPED"},
    ]
    _patch_vet_form(monkeypatch, tmp_path, tokens)
    _assert_vet_refusal(
        _vet_body("**Verdict: READY** · %s" % HEAD_SHA),
        HEAD_SHA,
        sc.REASON_VET_UNREADABLE,
    )


def test_l2f_v32_vet_form_duplicate_verdict_refuses(monkeypatch, tmp_path):
    # axis: duplicated verdict value in the form refuses vet-unreadable
    tokens = list(_VALID_VET_FORM_TOKENS) + [
        {"token": "**Verdict: READY**", "verdict": sc.VERDICT_READY},
    ]
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
    fail_calls = []

    def _fail_run(*args, **kwargs):
        fail_calls.append(list(args))
        raise AssertionError("gh should not run when deadline is exhausted")

    state, refusal = sc.read_pr_vet_state(
        DEP_PR, REPO, deadline=5.0, run=_fail_run,
    )
    assert state is None
    _assert_read_refusal(refusal, sc.REASON_STACK_UNREADABLE)
    assert fail_calls == []


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


# --- #2098: REST transport -------------------------------------------------------
#
# The REST fixtures are recorded verbatim with `gh api` (see fixtures/stack_rest/). The
# GraphQL side of the equality test is constructed from them, because GraphQL cannot be
# recorded from a cloud session.

REST_FIXTURES = Path(__file__).parent / "fixtures" / "stack_rest"
RREPO = "zwrose/superheroes"
ROWNER = "zwrose"
RNAME = "superheroes"
RPR = 2077
RSTACK = 2078
_DELETE = object()


def _fixture_json(name):
    with open(REST_FIXTURES / name, encoding="utf-8") as fh:
        return json.load(fh)


def _fixture_text(name):
    with open(REST_FIXTURES / name, encoding="utf-8") as fh:
        return fh.read()


PULL_2077 = _fixture_json("pulls_2077.json")
PULL_2086_UNSTACKED = _fixture_json("pulls_2086_unstacked.json")
STACKS_2078 = _fixture_json("stacks_2078.json")


def _with(obj, path, value):
    out = copy.deepcopy(obj)
    node = out
    for key in path[:-1]:
        node = node[key]
    if value is _DELETE:
        del node[path[-1]]
    else:
        node[path[-1]] = value
    return out


def _rest_resp(value):
    if isinstance(value, (SimpleNamespace, Exception)):
        return value
    return SimpleNamespace(returncode=0, stdout=json.dumps(value), stderr="")


def _pull_argv(pr=RPR):
    return tuple(sc._rest_pull_argv(ROWNER, RNAME, pr))


def _stack_argv(number=RSTACK):
    return tuple(sc._rest_stack_argv(ROWNER, RNAME, number))


def _rest_handlers(pull=None, stack=None, pr=RPR, stack_number=RSTACK):
    return {
        _pull_argv(pr): _rest_resp(PULL_2077 if pull is None else pull),
        _stack_argv(stack_number): _rest_resp(STACKS_2078 if stack is None else stack),
    }


def _read_rest(pull=None, stack=None, pr=RPR, **kwargs):
    run, calls = _make_run(_rest_handlers(pull=pull, stack=stack, pr=pr))
    kwargs.setdefault("transport", sc.TRANSPORT_REST)
    result = sc.read_membership(pr=pr, repo=RREPO, run=run, **kwargs)
    return result, calls


def _graphql_stack_2078_payload():
    """GraphQL answer for PR 2077 built from the recorded REST files' values.

    Constructed, not recorded: GraphQL cannot be recorded from a cloud session (the
    proxy refuses it), so this mirrors what the GraphQL query returns for the same stack.
    """
    nodes = [
        {
            "position": index + 1,
            "pullRequest": {
                "number": member["number"],
                "state": "MERGED",
                "isDraft": False,
                "headRefName": member["head"]["ref"],
                "headRefOid": member["head"]["sha"],
                "baseRefName": member["base"]["ref"],
            },
        }
        for index, member in enumerate(STACKS_2078["pull_requests"])
    ]
    return {
        "data": {
            "repository": {
                "pullRequest": {
                    "number": PULL_2077["number"],
                    "baseRefName": PULL_2077["base"]["ref"],
                    "headRefName": PULL_2077["head"]["ref"],
                    "headRefOid": PULL_2077["head"]["sha"],
                    "stackEntry": {
                        "position": PULL_2077["stack"]["position"],
                        "stack": {
                            "number": STACKS_2078["number"],
                            "size": PULL_2077["stack"]["size"],
                            "baseRefName": STACKS_2078["base"]["ref"],
                            "entries": {
                                "pageInfo": {"hasNextPage": False, "endCursor": None},
                                "nodes": nodes,
                            },
                        },
                    },
                }
            }
        }
    }


def _graphql_argv_2077():
    return tuple(sc._graphql_argv(ROWNER, RNAME, RPR, sc.DEFAULT_PAGE_SIZE))


def _graphql_ok_2077():
    return SimpleNamespace(
        returncode=0, stdout=json.dumps(_graphql_stack_2078_payload()), stderr="")


def _graphql_refused():
    return SimpleNamespace(
        returncode=1,
        stdout=_fixture_text("graphql_refused.stdout"),
        stderr=_fixture_text("graphql_refused.stderr"),
    )


def _stack_404():
    return SimpleNamespace(
        returncode=1,
        stdout=_fixture_text("stacks_unknown.stdout"),
        stderr=_fixture_text("stacks_unknown.stderr"),
    )


def _graphql_result_2077():
    run, _calls = _make_run({_graphql_argv_2077(): _graphql_ok_2077()})
    return sc.read_membership(
        pr=RPR, repo=RREPO, run=run, transport=sc.TRANSPORT_GRAPHQL)


# T1: equality


def test_r_rest_read_equals_graphql_read():
    result, calls = _read_rest()
    assert result["ok"] is True
    assert result == _graphql_result_2077()
    assert result["pages"] == 1
    assert result["stack"] == {"number": 2078, "size": 2, "baseRefName": "main"}
    assert [m["position"] for m in result["members"]] == [1, 2]
    assert [m["number"] for m in result["members"]] == [2065, 2077]
    assert [m["state"] for m in result["members"]] == ["MERGED", "MERGED"]
    assert calls[0] == ["gh", "api", "repos/zwrose/superheroes/pulls/2077"]
    assert calls[1] == ["gh", "api", "repos/zwrose/superheroes/stacks/2078"]


# T2-T5: auto fallback


def _auto_handlers(graphql_responses):
    handlers = _rest_handlers()
    handlers[_graphql_argv_2077()] = graphql_responses
    return handlers


def test_r_auto_falls_back_to_rest_on_proxy_graphql_refusal():
    run, calls = _make_run(_auto_handlers(_graphql_refused()))
    result = sc.read_membership(pr=RPR, repo=RREPO, run=run)
    assert result == _graphql_result_2077()
    assert tuple(calls[0]) == _graphql_argv_2077()
    assert [tuple(c) for c in calls[1:]] == [_pull_argv(), _stack_argv(), _pull_argv(), _stack_argv()]


def test_r_auto_without_proxy_refusal_does_not_fall_back():
    bad = SimpleNamespace(returncode=1, stdout="", stderr="gh: Something went wrong (HTTP 502)")
    run, calls = _make_run(_auto_handlers(bad))
    result = sc.read_membership(pr=RPR, repo=RREPO, run=run)
    _assert_refusal(result, sc.REASON_STACK_UNREADABLE)
    assert "502" in result["detail"]
    assert [tuple(c) for c in calls] == [_graphql_argv_2077()]


@pytest.mark.parametrize(
    "response",
    [
        SimpleNamespace(returncode=1, stdout="", stderr="gh: x (HTTP 403)"),
        SimpleNamespace(returncode=1, stdout="", stderr="use the REST API"),
        SimpleNamespace(returncode=0, stdout="(HTTP 403) use the REST API", stderr=""),
        subprocess.TimeoutExpired(cmd="gh", timeout=1),
        SimpleNamespace(returncode=0, stdout="not json", stderr=""),
    ],
    ids=["only-403", "only-rest-hint", "exit-zero-with-markers", "timeout", "non-json"],
)
def test_r_auto_other_first_call_failures_do_not_fall_back(response):
    run, calls = _make_run(_auto_handlers(response))
    result = sc.read_membership(pr=RPR, repo=RREPO, run=run)
    _assert_refusal(result, sc.REASON_STACK_UNREADABLE)
    assert [tuple(c) for c in calls] == [_graphql_argv_2077()]


def test_r_auto_parsed_graphql_refusal_does_not_fall_back():
    errors = SimpleNamespace(
        returncode=0,
        stdout=json.dumps({"errors": [{"message": "(HTTP 403) use the REST API"}]}),
        stderr="",
    )
    run, calls = _make_run(_auto_handlers(errors))
    result = sc.read_membership(pr=RPR, repo=RREPO, run=run)
    _assert_refusal(result, sc.REASON_STACK_UNREADABLE)
    assert [tuple(c) for c in calls] == [_graphql_argv_2077()]


def test_r_auto_graphql_refused_on_second_pass_does_not_fall_back():
    run, calls = _make_run(_auto_handlers([_graphql_ok_2077(), _graphql_refused()]))
    result = sc.read_membership(pr=RPR, repo=RREPO, run=run)
    _assert_refusal(result, sc.REASON_STACK_UNREADABLE)
    assert [tuple(c) for c in calls] == [_graphql_argv_2077(), _graphql_argv_2077()]


def test_r_auto_fallback_then_rest_refusal_prefixes_detail():
    handlers = _auto_handlers(_graphql_refused())
    handlers[_stack_argv()] = _stack_404()
    run, _calls = _make_run(handlers)
    result = sc.read_membership(pr=RPR, repo=RREPO, run=run)
    _assert_refusal(result, sc.REASON_STACK_UNREADABLE)
    assert result["detail"].startswith("graphql refused; rest: ")


def test_r_graphql_transport_never_calls_rest():
    handlers = {_graphql_argv_2077(): _graphql_refused()}
    run, calls = _make_run(handlers)
    result = sc.read_membership(pr=RPR, repo=RREPO, run=run, transport=sc.TRANSPORT_GRAPHQL)
    _assert_refusal(result, sc.REASON_STACK_UNREADABLE)
    assert [tuple(c) for c in calls] == [_graphql_argv_2077()]


# T6: one test per REST refusal clause


def test_r_bad_transport_value_refuses():
    for bad in ("soap", "", None, True, ["rest"]):
        result = sc.read_membership(
            pr=RPR, repo=RREPO, transport=bad, run=lambda *a, **k: None)
        _assert_refusal(result, sc.REASON_BAD_ARGUMENT)


def test_r_unstacked_pull_request_is_not_linked():
    result, calls = _read_rest(pull=PULL_2086_UNSTACKED, pr=2086)
    _assert_refusal(result, sc.REASON_NOT_LINKED)
    assert result["pages"] == 0
    assert len(calls) == 1


def test_r_null_stack_is_not_linked():
    result, _calls = _read_rest(pull=_with(PULL_2077, ("stack",), None))
    _assert_refusal(result, sc.REASON_NOT_LINKED)


@pytest.mark.parametrize(
    "path,value",
    [
        (("number",), "2077"),
        (("number",), True),
        (("head", "ref"), _DELETE),
        (("head", "sha"), 7),
        (("head",), None),
        (("base", "ref"), None),
        (("base",), "main"),
    ],
)
def test_r_malformed_pull_request_fields_refuse(path, value):
    result, calls = _read_rest(pull=_with(PULL_2077, path, value))
    _assert_refusal(result, sc.REASON_STACK_UNREADABLE)
    assert result["pages"] == 0
    assert len(calls) == 1


@pytest.mark.parametrize(
    "path,value",
    [
        (("stack",), "main"),
        (("stack",), []),
        (("stack", "number"), True),
        (("stack", "number"), "2078"),
        (("stack", "position"), "2"),
        (("stack", "position"), _DELETE),
        (("stack", "size"), None),
        (("stack", "size"), 2.0),
        (("stack", "base", "ref"), _DELETE),
        (("stack", "base"), "main"),
    ],
)
def test_r_malformed_stack_object_refuses(path, value):
    result, calls = _read_rest(pull=_with(PULL_2077, path, value))
    _assert_refusal(result, sc.REASON_STACK_UNREADABLE)
    assert len(calls) == 1


def test_r_stack_get_404_refuses_and_names_the_endpoint():
    run, calls = _make_run(_rest_handlers(stack=_stack_404()))
    result = sc.read_membership(pr=RPR, repo=RREPO, run=run, transport=sc.TRANSPORT_REST)
    _assert_refusal(result, sc.REASON_STACK_UNREADABLE)
    assert "stacks/2078" in result["detail"]
    assert "Not Found" in result["detail"]
    assert result["pages"] == 0


@pytest.mark.parametrize("endpoint", ["pull", "stack"])
@pytest.mark.parametrize(
    "response",
    [
        FileNotFoundError("no gh"),
        OSError("boom"),
        subprocess.TimeoutExpired(cmd="gh", timeout=120),
        SimpleNamespace(returncode=1, stdout="", stderr="gh: Server Error (HTTP 500)"),
        SimpleNamespace(returncode=0, stdout="not json", stderr=""),
        SimpleNamespace(returncode=0, stdout="", stderr=""),
        SimpleNamespace(returncode=0, stdout="[]", stderr=""),
        SimpleNamespace(returncode=0, stdout="null", stderr=""),
    ],
    ids=["file-not-found", "oserror", "timeout", "exit-1", "non-json", "empty", "array", "null"],
)
def test_r_transport_failures_on_either_get_refuse(endpoint, response):
    handlers = _rest_handlers()
    handlers[_pull_argv() if endpoint == "pull" else _stack_argv()] = response
    run, _calls = _make_run(handlers)
    result = sc.read_membership(pr=RPR, repo=RREPO, run=run, transport=sc.TRANSPORT_REST)
    _assert_refusal(result, sc.REASON_STACK_UNREADABLE)
    expected = "pulls/2077" if endpoint == "pull" else "stacks/2078"
    assert expected in result["detail"]
    assert result["pages"] == 0


@pytest.mark.parametrize("endpoint", ["pull", "stack"])
def test_r_gh_exits_nonzero_with_valid_json_stdout_refuses(endpoint):
    valid = PULL_2077 if endpoint == "pull" else STACKS_2078
    failed = SimpleNamespace(returncode=1, stdout=json.dumps(valid), stderr="gh: Bad Gateway (HTTP 502)")
    handlers = _rest_handlers()
    handlers[_pull_argv() if endpoint == "pull" else _stack_argv()] = failed
    run, _calls = _make_run(handlers)
    result = sc.read_membership(pr=RPR, repo=RREPO, run=run, transport=sc.TRANSPORT_REST)
    _assert_refusal(result, sc.REASON_STACK_UNREADABLE)
    assert "HTTP 502" in result["detail"]


@pytest.mark.parametrize(
    "path,value",
    [
        (("number",), "2078"),
        (("number",), True),
        (("base", "ref"), _DELETE),
        (("base",), None),
        (("pull_requests",), {}),
        (("pull_requests",), _DELETE),
    ],
)
def test_r_malformed_stack_response_refuses(path, value):
    result, _calls = _read_rest(stack=_with(STACKS_2078, path, value))
    _assert_refusal(result, sc.REASON_STACK_UNREADABLE)
    assert result["pages"] == 1


def test_r_stack_number_mismatch_is_order_mismatch():
    result, _calls = _read_rest(stack=_with(STACKS_2078, ("number",), 9999))
    _assert_refusal(result, sc.REASON_ORDER_MISMATCH)
    assert "number" in result["detail"]


def test_r_stack_base_mismatch_is_order_mismatch():
    result, _calls = _read_rest(stack=_with(STACKS_2078, ("base", "ref"), "develop"))
    _assert_refusal(result, sc.REASON_ORDER_MISMATCH)
    assert "base" in result["detail"]


@pytest.mark.parametrize(
    "path,value",
    [
        (("pull_requests", 1, "state"), "merged"),
        (("pull_requests", 1, "state"), "OPEN"),
        (("pull_requests", 1, "state"), None),
        (("pull_requests", 1, "merged_at"), 5),
        (("pull_requests", 1, "draft"), "no"),
        (("pull_requests", 1, "draft"), _DELETE),
        (("pull_requests", 0, "head"), _DELETE),
        (("pull_requests", 0, "head", "sha"), 1),
        (("pull_requests", 0, "base", "ref"), None),
        (("pull_requests", 0, "number"), "2065"),
        (("pull_requests", 0), "not-an-object"),
    ],
)
def test_r_malformed_member_refuses(path, value):
    result, _calls = _read_rest(stack=_with(STACKS_2078, path, value))
    _assert_refusal(result, sc.REASON_STACK_UNREADABLE)
    assert result["pages"] == 1


def test_r_member_states_map_to_graphql_vocabulary():
    stack = copy.deepcopy(STACKS_2078)
    stack["pull_requests"][0]["state"] = "closed"
    stack["pull_requests"][0]["merged_at"] = None
    stack["pull_requests"][0]["draft"] = True
    stack["pull_requests"][1]["state"] = "open"
    stack["pull_requests"][1]["merged_at"] = None
    result, _calls = _read_rest(stack=stack)
    assert result["ok"] is True
    assert [m["state"] for m in result["members"]] == ["CLOSED", "OPEN"]
    assert result["members"][0]["isDraft"] is True


def test_r_more_members_than_size_refuses():
    stack = copy.deepcopy(STACKS_2078)
    extra = copy.deepcopy(stack["pull_requests"][1])
    extra["number"] = 2090
    stack["pull_requests"].append(extra)
    result, _calls = _read_rest(stack=stack)
    _assert_refusal(result, sc.REASON_STACK_UNREADABLE)
    assert "exceed stack size" in result["detail"]


def test_r_fewer_members_than_size_is_order_mismatch():
    stack = copy.deepcopy(STACKS_2078)
    del stack["pull_requests"][0]
    result, _calls = _read_rest(stack=stack)
    _assert_refusal(result, sc.REASON_ORDER_MISMATCH)


def test_r_expect_stack_mismatch_is_order_mismatch():
    result, _calls = _read_rest(expect_stack=1)
    _assert_refusal(result, sc.REASON_ORDER_MISMATCH)
    assert "expect_stack" in result["detail"]
    ok_result, _calls = _read_rest(expect_stack=RSTACK)
    assert ok_result["ok"] is True


def test_r_queried_pull_request_not_at_its_position_is_order_mismatch():
    stack = copy.deepcopy(STACKS_2078)
    stack["pull_requests"].reverse()
    result, _calls = _read_rest(stack=stack)
    _assert_refusal(result, sc.REASON_ORDER_MISMATCH)


def test_r_queried_member_head_mismatch_is_order_mismatch():
    result, _calls = _read_rest(stack=_with(STACKS_2078, ("pull_requests", 1, "head", "sha"), "f" * 40))
    _assert_refusal(result, sc.REASON_ORDER_MISMATCH)


def _fake_monotonic(monkeypatch, times):
    index = 0

    def fake_monotonic():
        nonlocal index
        value = times[index] if index < len(times) else times[-1]
        index += 1
        return value

    monkeypatch.setattr(sc.time, "monotonic", fake_monotonic)


def test_r_deadline_exhausted_before_the_first_get_refuses(monkeypatch):
    _fake_monotonic(monkeypatch, [0, 100])
    result, calls = _read_rest(deadline=100.0)
    _assert_refusal(result, sc.REASON_STACK_UNREADABLE)
    assert "100" in result["detail"]
    assert calls == []


def test_r_deadline_exhausted_before_the_stack_get_refuses(monkeypatch):
    _fake_monotonic(monkeypatch, [0, 1, 100])
    result, calls = _read_rest(deadline=100.0)
    _assert_refusal(result, sc.REASON_STACK_UNREADABLE)
    assert len(calls) == 1


def test_r_effective_timeout_is_bounded_by_remaining_budget(monkeypatch):
    _fake_monotonic(monkeypatch, [0, 1, 40, 41, 42])
    run, _calls = _make_run(_rest_handlers())
    sc.read_membership(
        pr=RPR, repo=RREPO, run=run, transport=sc.TRANSPORT_REST, timeout=120, deadline=50.0)
    assert run.kw_calls[0]["timeout"] == 10.0


def test_r_timeout_none_with_deadline_uses_remaining_budget(monkeypatch):
    _fake_monotonic(monkeypatch, [0, 1, 40])
    run, _calls = _make_run(_rest_handlers())
    result = sc.read_membership(
        pr=RPR, repo=RREPO, run=run, transport=sc.TRANSPORT_REST, timeout=None, deadline=50.0)
    assert isinstance(result, dict)
    assert run.kw_calls[0]["timeout"] == 10.0


def test_r_no_deadline_leaves_timeout_untouched():
    run, _calls = _make_run(_rest_handlers())
    sc.read_membership(pr=RPR, repo=RREPO, run=run, transport=sc.TRANSPORT_REST, timeout=77)
    assert run.kw_calls[0]["timeout"] == 77


# T7: the second pass must match the first pass's whole snapshot


def test_r_graphql_second_pass_different_stack_number_is_order_mismatch():
    def _page(stack_number):
        return _graphql_ok(_pull_request(
            pr_number=PR, position=1, stack_number=stack_number, stack_size=2,
            nodes=[_member(1, number=PR), _member(2)]))

    run, _calls = _make_run({_argv_page(PR, sc.DEFAULT_PAGE_SIZE): [_page(7), _page(8)]})
    result = sc.read_membership(pr=PR, repo=REPO, run=run, transport=sc.TRANSPORT_GRAPHQL)
    _assert_refusal(result, sc.REASON_ORDER_MISMATCH)
    assert result["detail"] == "stack snapshot changed between enumeration passes"


def test_r_rest_second_pass_different_stack_number_is_order_mismatch():
    pull_b = _with(PULL_2077, ("stack", "number"), 2079)
    stack_b = _with(STACKS_2078, ("number",), 2079)
    handlers = {
        _pull_argv(): [_rest_resp(PULL_2077), _rest_resp(pull_b)],
        _stack_argv(2078): _rest_resp(STACKS_2078),
        _stack_argv(2079): _rest_resp(stack_b),
    }
    run, _calls = _make_run(handlers)
    result = sc.read_membership(pr=RPR, repo=RREPO, run=run, transport=sc.TRANSPORT_REST)
    _assert_refusal(result, sc.REASON_ORDER_MISMATCH)
    assert result["detail"] == "stack snapshot changed between enumeration passes"


def test_r_rest_second_pass_member_drift_keeps_the_membership_refusal():
    stack_b = _with(STACKS_2078, ("pull_requests", 0, "head", "sha"), "a" * 40)
    handlers = {
        _pull_argv(): _rest_resp(PULL_2077),
        _stack_argv(): [_rest_resp(STACKS_2078), _rest_resp(stack_b)],
    }
    run, _calls = _make_run(handlers)
    result = sc.read_membership(pr=RPR, repo=RREPO, run=run, transport=sc.TRANSPORT_REST)
    _assert_refusal(result, sc.REASON_ORDER_MISMATCH)
    assert result["detail"] == "membership changed between enumeration passes"


# T8: CLI


def test_r_cli_transport_rest_prints_the_success_json(capsys, monkeypatch):
    run, _calls = _make_run(_rest_handlers())
    monkeypatch.setattr(subprocess, "run", run)
    rc = sc.main(["list", "--pr", str(RPR), "--repo", RREPO, "--transport", "rest"])
    printed = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert printed == _graphql_result_2077()


def test_r_cli_transport_defaults_to_auto(capsys, monkeypatch):
    handlers = _auto_handlers(_graphql_refused())
    run, calls = _make_run(handlers)
    monkeypatch.setattr(subprocess, "run", run)
    rc = sc.main(["list", "--pr", str(RPR), "--repo", RREPO])
    printed = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert printed["ok"] is True
    assert tuple(calls[0]) == _graphql_argv_2077()


def test_r_cli_bogus_transport_is_bad_argument(capsys):
    rc = sc.main(["list", "--pr", str(RPR), "--repo", RREPO, "--transport", "bogus"])
    out = capsys.readouterr().out
    _assert_refusal(json.loads(out), sc.REASON_BAD_ARGUMENT)
    assert rc == 1
    assert "usage:" not in out.lower()


# --- #2108: vet-state and repo-slug REST fallback ---------------------------------------
#
# The refusal is the one recorded from `gh pr view` / `gh repo view` in a cloud session
# (no parentheses around HTTP 403); the REST answers are the recorded `gh api` files. The
# GraphQL side of each equality is the unchanged GraphQL path fed the same fixture's values.

PULL_2111_DRAFT = _fixture_json("pulls_2111_open_draft.json")
PULL_2093_OPEN = _fixture_json("pulls_2093_open.json")
PULL_2075_CLOSED = _fixture_json("pulls_2075_closed_unmerged.json")
REPO_SUPERHEROES = _fixture_json("repos_superheroes.json")
FALLBACK_PREFIX = "graphql refused; rest: "


def _view_refused():
    return SimpleNamespace(
        returncode=1, stdout="", stderr=_fixture_text("gh_view_refused.stderr"))


def _vet_view_argv(pr):
    return tuple(sc._pr_vet_state_argv(pr, RREPO))


def _slug_rest_argv():
    return tuple(sc._rest_repo_argv())


def _vet_fallback(pull, pr=None, view=None, rest=None, **kwargs):
    pr = pull["number"] if pr is None else pr
    run, calls = _make_run({
        _vet_view_argv(pr): _view_refused() if view is None else view,
        _pull_argv(pr): _rest_resp(pull if rest is None else rest),
    })
    state, refusal = sc.read_pr_vet_state(pr, RREPO, run=run, **kwargs)
    return state, refusal, calls, run


def _slug_fallback(repo_payload=None, view=None, rest=None, **kwargs):
    run, calls = _make_run({
        _repo_slug_argv(): _view_refused() if view is None else view,
        _slug_rest_argv(): _rest_resp(REPO_SUPERHEROES if repo_payload is None else repo_payload)
        if rest is None else rest,
    })
    slug, refusal = sc.resolve_repo_slug(REPO_ROOT, run=run, **kwargs)
    return slug, refusal, calls, run


def _assert_fallback_refusal(refusal):
    _assert_read_refusal(refusal, sc.REASON_STACK_UNREADABLE)
    assert refusal["detail"].startswith(FALLBACK_PREFIX)


@pytest.mark.parametrize(
    "pull,graphql_state",
    [
        (PULL_2077, "MERGED"),
        (PULL_2111_DRAFT, "OPEN"),
        (PULL_2093_OPEN, "OPEN"),
        (PULL_2075_CLOSED, "CLOSED"),
    ],
    ids=["merged", "open-draft", "open", "closed-unmerged"],
)
def test_v_vet_state_rest_fallback_equals_graphql_read(pull, graphql_state):
    # axis: REST fallback missing or mapping a pull field differently from the GraphQL read
    pr = pull["number"]
    graphql_run, _graphql_calls = _make_run({
        _vet_view_argv(pr): _pr_vet_ok(
            head_ref_oid=pull["head"]["sha"],
            state=graphql_state,
            is_draft=pull["draft"],
            body=pull["body"] or "",
        ),
    })
    expected = sc.read_pr_vet_state(pr, RREPO, run=graphql_run)
    assert expected[1] is None
    assert expected[0]["state"] == graphql_state

    state, refusal, calls, _run = _vet_fallback(pull)
    assert refusal is None
    assert (state, refusal) == expected
    assert calls == [list(_vet_view_argv(pr)), list(_pull_argv(pr))]


def test_v_vet_state_rest_null_body_is_the_empty_string():
    # axis: null REST body not normalised to the empty string
    state, refusal, _calls, _run = _vet_fallback(_with(PULL_2093_OPEN, ("body",), None))
    assert refusal is None
    assert state["body"] == ""


def test_v_vet_state_fallback_passes_env_to_both_calls():
    # axis: env not passed to the REST call (or the GraphQL call) of the vet-state fallback
    env = {"GH_TOKEN": "x"}
    _state, _refusal, _calls, run = _vet_fallback(PULL_2093_OPEN, env=env)
    assert [kw["env"] for kw in run.kw_calls] == [env, env]


def test_v_repo_slug_rest_fallback_equals_graphql_read():
    # axis: REST fallback missing or yielding a slug different from the GraphQL read
    graphql_run, _graphql_calls = _make_run(
        {_repo_slug_argv(): _repo_slug_ok(REPO_SUPERHEROES["full_name"])})
    expected = sc.resolve_repo_slug(REPO_ROOT, run=graphql_run)
    assert expected == ("zwrose/superheroes", None)

    slug, refusal, calls, run = _slug_fallback()
    assert (slug, refusal) == expected
    assert calls == [list(_repo_slug_argv()), ["gh", "api", "repos/{owner}/{repo}"]]
    assert run.kw_calls[1]["cwd"] == REPO_ROOT
    assert run.kw_calls[0]["cwd"] == REPO_ROOT


def test_v_repo_slug_fallback_passes_env_to_both_calls():
    # axis: env not passed to the REST call (or the GraphQL call) of the repo-slug fallback
    env = {"GH_TOKEN": "x"}
    _slug, _refusal, _calls, run = _slug_fallback(env=env)
    assert [kw["env"] for kw in run.kw_calls] == [env, env]


# Each factory takes the otherwise-valid success payload and returns a failed REST answer.
_REST_FAILURES = [
    lambda valid: SimpleNamespace(
        returncode=1, stdout=json.dumps(valid), stderr="gh: Bad Gateway (HTTP 502)"),
    lambda valid: subprocess.TimeoutExpired(cmd="gh", timeout=120),
    lambda valid: SimpleNamespace(returncode=0, stdout="not json", stderr=""),
    lambda valid: SimpleNamespace(returncode=0, stdout="[]", stderr=""),
]
_REST_FAILURE_IDS = ["exit-1-with-json-stdout", "timeout", "non-json", "json-array"]


@pytest.mark.parametrize("failure", _REST_FAILURES, ids=_REST_FAILURE_IDS)
def test_v_vet_state_rest_failure_after_refusal_refuses(failure):
    # axis: REST failure after the refusal not refused, or refused without the fallback prefix
    state, refusal, calls, _run = _vet_fallback(
        PULL_2093_OPEN, rest=failure(PULL_2093_OPEN))
    assert state is None
    _assert_fallback_refusal(refusal)
    assert len(calls) == 2


@pytest.mark.parametrize("failure", _REST_FAILURES, ids=_REST_FAILURE_IDS)
def test_v_repo_slug_rest_failure_after_refusal_refuses(failure):
    # axis: REST failure after the refusal not refused, or refused without the fallback prefix
    slug, refusal, calls, _run = _slug_fallback(rest=failure(REPO_SUPERHEROES))
    assert slug is None
    _assert_fallback_refusal(refusal)
    assert len(calls) == 2


@pytest.mark.parametrize(
    "pull,path,value",
    [
        (PULL_2093_OPEN, ("state",), _DELETE),
        (PULL_2093_OPEN, ("state",), "all"),
        (PULL_2093_OPEN, ("state",), "OPEN"),
        (PULL_2077, ("merged",), _DELETE),
        (PULL_2077, ("merged",), "true"),
        (PULL_2077, ("merged",), 1),
        (PULL_2075_CLOSED, ("merged",), 0),
        (PULL_2077, ("merged_at",), _DELETE),
        (PULL_2077, ("merged_at",), 5),
        (PULL_2077, ("merged_at",), ""),
        (PULL_2077, ("merged_at",), None),
        (PULL_2075_CLOSED, ("merged_at",), "2026-10-23T19:39:34Z"),
        (_with(_with(PULL_2093_OPEN, ("merged",), True), ("merged_at",), "2026-10-23T19:39:34Z"),
         ("state",), "open"),
        (PULL_2093_OPEN, ("draft",), _DELETE),
        (PULL_2093_OPEN, ("draft",), "no"),
        (PULL_2093_OPEN, ("head",), "abc"),
        (PULL_2093_OPEN, ("head",), None),
        (PULL_2093_OPEN, ("head", "sha"), _DELETE),
        (PULL_2093_OPEN, ("head", "sha"), "abc123"),
        (PULL_2093_OPEN, ("head", "sha"), "A" * 40),
        (PULL_2093_OPEN, ("body",), _DELETE),
        (PULL_2093_OPEN, ("body",), 7),
    ],
    ids=[
        "state-missing", "state-unknown", "state-uppercase",
        "merged-missing", "merged-not-bool", "merged-int-one", "merged-int-zero",
        "merged-at-missing", "merged-at-int", "merged-at-empty",
        "merged-without-merged-at", "unmerged-with-merged-at",
        "open-but-merged",
        "draft-missing", "draft-not-bool",
        "head-not-object", "head-null", "head-sha-missing", "head-sha-short", "head-sha-uppercase",
        "body-missing", "body-not-string",
    ],
)
def test_v_vet_state_malformed_rest_fields_refuse(pull, path, value):
    # axis: a malformed or inconsistent REST pull field accepted instead of refused
    state, refusal, calls, _run = _vet_fallback(pull, rest=_with(pull, path, value))
    assert state is None
    _assert_fallback_refusal(refusal)
    assert len(calls) == 2


@pytest.mark.parametrize(
    "value",
    [_DELETE, "", 7, "no-slash", None],
    ids=["missing", "empty", "not-a-string", "no-slash", "null"],
)
def test_v_repo_slug_malformed_full_name_refuses(value):
    # axis: a malformed REST full_name accepted instead of refused
    slug, refusal, calls, _run = _slug_fallback(_with(REPO_SUPERHEROES, ("full_name",), value))
    assert slug is None
    _assert_fallback_refusal(refusal)
    assert "full_name" in refusal["detail"]
    assert len(calls) == 2


_NOT_THE_REFUSAL = [
    SimpleNamespace(returncode=1, stdout="", stderr="gh: Something went wrong (HTTP 502)"),
    SimpleNamespace(returncode=1, stdout="", stderr="gh: x HTTP 403"),
    SimpleNamespace(returncode=1, stdout="", stderr="use the REST API"),
    SimpleNamespace(returncode=0, stdout="HTTP 403 use the REST API", stderr=""),
]
_NOT_THE_REFUSAL_IDS = ["http-502", "only-403", "only-rest-hint", "exit-zero-with-markers"]


@pytest.mark.parametrize("view", _NOT_THE_REFUSAL, ids=_NOT_THE_REFUSAL_IDS)
def test_v_vet_state_without_the_refusal_makes_one_call_and_refuses(view):
    # axis: REST fallback taken although the GraphQL failure is not the proxy refusal
    state, refusal, calls, _run = _vet_fallback(PULL_2093_OPEN, view=view)
    assert state is None
    _assert_read_refusal(refusal, sc.REASON_STACK_UNREADABLE)
    assert not refusal["detail"].startswith(FALLBACK_PREFIX)
    assert calls == [list(_vet_view_argv(PULL_2093_OPEN["number"]))]


@pytest.mark.parametrize("view", _NOT_THE_REFUSAL, ids=_NOT_THE_REFUSAL_IDS)
def test_v_repo_slug_without_the_refusal_makes_one_call_and_refuses(view):
    # axis: REST fallback taken although the GraphQL failure is not the proxy refusal
    slug, refusal, calls, _run = _slug_fallback(view=view)
    assert slug is None
    _assert_read_refusal(refusal, sc.REASON_STACK_UNREADABLE)
    assert not refusal["detail"].startswith(FALLBACK_PREFIX)
    assert calls == [list(_repo_slug_argv())]


@pytest.mark.parametrize(
    "refusal_proc",
    [
        SimpleNamespace(
            returncode=1,
            stdout=_fixture_text("graphql_refused.stdout"),
            stderr=_fixture_text("graphql_refused.stderr")),
        SimpleNamespace(
            returncode=1, stdout="", stderr=_fixture_text("gh_view_refused.stderr")),
    ],
    ids=["gh-api-graphql", "gh-view"],
)
def test_v_both_recorded_refusals_satisfy_the_predicate(refusal_proc):
    # axis: a recorded refusal shape (gh api graphql or gh view) not matched by the predicate
    assert sc._is_graphql_proxy_refusal_proc(refusal_proc) is True
    assert sc._is_graphql_proxy_refusal([refusal_proc]) is True


def test_v_vet_state_deadline_exhausted_before_the_rest_get_refuses(monkeypatch):
    # axis: deadline not honoured before the REST GET — gh called after the deadline is spent
    _fake_monotonic(monkeypatch, [0, 1, 2, 100])
    state, refusal, calls, _run = _vet_fallback(PULL_2093_OPEN, deadline=100.0)
    assert state is None
    _assert_fallback_refusal(refusal)
    assert calls == [list(_vet_view_argv(PULL_2093_OPEN["number"]))]


def test_v_repo_slug_deadline_exhausted_before_the_rest_get_refuses(monkeypatch):
    # axis: deadline not honoured before the REST GET — gh called after the deadline is spent
    _fake_monotonic(monkeypatch, [0, 1, 2, 100])
    slug, refusal, calls, _run = _slug_fallback(deadline=100.0)
    assert slug is None
    _assert_fallback_refusal(refusal)
    assert calls == [list(_repo_slug_argv())]
