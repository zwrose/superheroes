# plugins/superheroes/lib/tests/test_cloud_parked_links_2658.py
"""Issue 2658: the advisor's park and cleanup verbs read a PR's issues only from what GitHub records.

One test per fail-closed edge, P1-P14, named for the edge. A description mention alone is never a link: a PR on
its default base is linked by GitHub's closing list, a PR in a native stack on another base by the REST
timeline's cross-reference, and a read that cannot be made is `unreadable`, never "no link".
Every repository, ledger and state file is built under tmp_path; the `gh` answers are a fake `run`."""
import os
import sys
from types import SimpleNamespace

import pytest

_LIB = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import cloud_cleanup as CC  # noqa: E402
import cloud_parked as CP  # noqa: E402
import launch_ledger as ll  # noqa: E402
import test_cloud_cleanup as TCC  # noqa: E402

from test_cloud_parked import (  # noqa: E402,F401  (w is a fixture)
    REPO, _cross_ref, _entries, _lane, _lapsed_comment, _layer, _notice, _park, _pull, _ref, _renew, _send,
    _state_file, w,
)
from test_launch_ledger import _declare, _init_repo, _ledger_env  # noqa: E402


def _links(w, pr):
    return CP._linked_issues(w.gh.pulls[pr], REPO, pr, w.env, w.gh)


def _timeline_path(n):
    return "repos/%s/issues/%d/timeline" % (REPO, n)


def _timeline_reads(w):
    return [c for c in w.gh.calls if "/timeline" in c[-1]]


@pytest.fixture
def cw(tmp_path, monkeypatch):
    """The cleanup suite's own world (its fake `gh`, its pull, its ledger), built here to be used beside `w`."""
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    repo = _init_repo(tmp_path / "cleanup-repo")
    root = _ledger_env(tmp_path, monkeypatch)
    env = {"HOME": str(tmp_path / "home"), "PATH": os.environ["PATH"], ll.LEDGER_ROOT_ENV: root}
    assert _declare(repo, TCC.BATCH, 4, env=env)["ok"]
    gh = TCC.Gh()
    gh.pulls[TCC.PR] = TCC._pull(head_sha=TCC.HEAD)
    return SimpleNamespace(repo=repo, env=env, gh=gh, head=TCC.HEAD)


# ---------------------------------------------------------------- a default-base PR


# axis: the description's first line never links a default-base PR; only GitHub's list does (the DoD no-link test) — see bite-proof record i2658_parked_links
def test_p1_a_default_base_pr_whose_first_line_names_an_issue_githubs_list_lacks_is_not_linked(w):
    _lane(w, "l-a", 101, "session-a", "a")
    w.gh.comments[10] = [_lapsed_comment(10)]
    w.gh.pulls[10] = dict(_pull(), body="Part of #101.\n\nthe work")  # GitHub's closing list is empty
    assert _links(w, 10) == ([], "github")
    w.gh.pulls[10]["body"] = "#101\n\nthe work"
    assert _links(w, 10) == ([], "github")
    out = _notice(w, 10)
    assert out["kind"] == "lapsed-pass" and out["linkSource"] == "github", out
    assert _entries(w)[0]["launchId"] is None  # never the lane of the issue the description only names


def test_p1_a_default_base_pr_whose_first_line_names_an_issue_githubs_list_lacks_is_unlinked_to_cleanup(cw):
    TCC._lane(cw, "l-1", 101)
    cw.gh.pulls[TCC.PR] = dict(TCC._pull(issues=(), head_sha=cw.head), body="Part of #101.\n\nthe work")
    want = {"ok": False, "reason": "pr-unlinked"}
    assert CC.plan(cw.repo, REPO, TCC.PR, env=cw.env, run=cw.gh) == want
    assert CC.branch(cw.repo, REPO, TCC.PR, env=cw.env, run=cw.gh) == want
    assert cw.gh.deletes == [] and TCC.BRANCH in cw.gh.branches


# axis: the repository leg; another repository's issue in GitHub's list is never this repository's — see bite-proof record i2658_parked_links
def test_p2_githubs_list_naming_another_repositorys_issue_is_not_this_repositorys(w):
    w.gh.pulls[10] = _pull()
    w.gh.closing[10] = [_ref(101, "other/repo")]
    assert _links(w, 10) == ([], "github")
    w.gh.closing[10] = [_ref(101, "other/repo"), _ref(102), _ref(102)]
    assert _links(w, 10) == ([102], "github")


# axis: a closing list whose read fails is unreadable, never "no link" — see bite-proof record i2658_parked_links
def test_p3_a_closing_list_read_that_fails_is_unreadable(w):
    w.gh.pulls[10] = _pull(101)  # the description says "Closes #101"
    w.gh.closing[10] = None  # gh exits non-zero
    assert _links(w, 10) == ([], "unreadable")


def test_p4_a_malformed_closing_list_is_unreadable(w):
    w.gh.pulls[10] = _pull(101)
    for rows in ([{"number": 101}], [{"number": 101, "repository": {"name": "name"}}],
                 [{"repository": {"name": "name", "owner": {"login": "owner"}}}], ["101"]):
        w.gh.closing[10] = rows
        assert _links(w, 10) == ([], "unreadable"), rows


# ---------------------------------------------------------------- a PR on another base


def _unlinked_layer(n, body, stack):
    """A layer's pull on a non-default base before the advisor links it into a native stack."""
    pull = _layer(n, body)
    if stack is None:
        pull["stack"] = None
    else:
        del pull["stack"]
    return pull


# axis: a non-default base not yet in a native stack is confirmed through the timeline like a stack layer, never read as no link — see bite-proof record i2658_parked_links
def test_p5_a_non_default_base_pr_not_yet_in_a_stack_is_linked_only_by_the_timeline(w):
    for stack in (None, "absent"):
        w.gh.timelines.pop(101, None)
        w.gh.pulls[10] = _unlinked_layer(10, "Part of #101\n\nthe work", stack)
        assert _links(w, 10) == ([], "timeline")  # the description alone links nothing
        w.gh.timelines[101] = [_cross_ref(10)]
        assert _links(w, 10) == ([101], "timeline")  # GitHub's record of this PR links it
    assert _timeline_reads(w)


# axis: cleanup reads a non-default-base PR outside a native stack as having no link, so its issue reference never selects a lane or a branch — see bite-proof record i2658_parked_links
def test_p5_cleanup_refuses_a_non_default_base_pr_not_in_a_stack(cw):
    TCC._lane(cw, "l-1", 101)
    TCC._as_layer(cw, TCC.PR, 101)
    assert CC.plan(cw.repo, REPO, TCC.PR, env=cw.env, run=cw.gh)["linkSource"] == "timeline"  # a stack layer plans
    cw.gh.pulls[TCC.PR]["stack"] = None  # the same pull, outside a native stack
    want = {"ok": False, "reason": "pr-unlinked"}
    assert CC.plan(cw.repo, REPO, TCC.PR, env=cw.env, run=cw.gh) == want
    assert CC.branch(cw.repo, REPO, TCC.PR, env=cw.env, run=cw.gh) == want
    assert cw.gh.deletes == [] and TCC.BRANCH in cw.gh.branches
    assert CP._linked_issues(cw.gh.pulls[TCC.PR], REPO, TCC.PR, cw.env, cw.gh) == ([101], "timeline")  # parks still bind


# axis: an upper layer parked before the advisor links its stack binds its launch at the first notice — see bite-proof record i2658_parked_links
def test_p5_a_park_on_a_layer_not_yet_in_a_stack_binds_its_launch(w):
    _lane(w, "l-a", 101, "session-a", "a")
    w.gh.comments[10] = [_lapsed_comment(10)]
    w.gh.pulls[10] = _unlinked_layer(10, "Part of #101\n\nthe work", None)
    w.gh.timelines[101] = [_cross_ref(10)]
    out = _notice(w, 10)
    assert out["kind"] == "lapsed-pass" and out["linkSource"] == "timeline", out
    assert _entries(w)[0]["launchId"] == "l-a"


# axis: a stack layer's first-line candidate is linked when GitHub's timeline records the cross-reference
def test_p6_a_stack_layer_whose_candidate_has_the_cross_reference_is_linked_by_the_timeline(w):
    w.gh.pulls[10] = _layer(10, "Closes #101, see #102 and (#103)\n\nmentions #104 below the first line")
    for n in (101, 102, 104):
        w.gh.timelines[n] = [_cross_ref(10)]
    assert _links(w, 10) == ([101, 102], "timeline")  # 103 holds no cross-reference; 104 is never a candidate
    assert not [c for c in w.gh.calls if c[-1].endswith("/issues/104") or "/issues/104/" in c[-1]]


# axis: a stack layer's candidate is linked only when the timeline holds the cross-reference — see bite-proof record i2658_parked_links
def test_p7_a_stack_layer_whose_candidate_has_no_cross_reference_is_not_linked(w):
    w.gh.pulls[10] = _layer(10, "Part of #101.\n\nthe work")
    assert _links(w, 10) == ([], "timeline")
    w.gh.timelines[101] = [_cross_ref(11), _cross_ref(10, "other/repo"),
                           {"event": "labeled", "label": {"name": "x"}}]  # another PR, another repository, another event
    assert _links(w, 10) == ([], "timeline")
    w.gh.timelines[101].append(_cross_ref(10, "Owner/Name"))  # this repository, spelled with another case
    assert _links(w, 10) == ([101], "timeline")


def test_p8_a_stack_layer_whose_timeline_or_issue_read_fails_is_unreadable(w):
    w.gh.pulls[10] = _layer(10, "Part of #101.\n\nthe work")
    w.gh.timelines[101] = [_cross_ref(10)]
    w.gh.broken.add(_timeline_path(101))
    assert _links(w, 10) == ([], "unreadable")
    w.gh.broken.clear()
    w.gh.broken.add("repos/%s/issues/101" % REPO)
    assert _links(w, 10) == ([], "unreadable")
    w.gh.broken.clear()
    w.gh.issue_objects[101] = ["not", "an", "object"]
    assert _links(w, 10) == ([], "unreadable")
    w.gh.issue_objects.clear()
    assert _links(w, 10) == ([101], "timeline")  # the same pull reads once the reads work


def test_p9_a_malformed_stack_field_or_unreadable_base_is_unreadable(w):
    def pull(**change):
        got = _layer(10, "Part of #101.\n\nthe work")
        for key, value in change.items():
            if value is KeyError:
                got.pop(key)
            else:
                got[key] = value
        return got
    w.gh.timelines[101] = [_cross_ref(10)]
    good_stack = {"number": 7, "position": 2, "size": 3, "base": {"ref": "main"}}
    bad = [
        pull(stack="not an object"),
        pull(stack=dict(good_stack, number="7")),
        pull(stack=dict(good_stack, position=None)),
        pull(stack=dict(good_stack, size=True)),
        pull(stack=dict(good_stack, base=None)),
        pull(stack={k: v for k, v in good_stack.items() if k != "base"}),
        pull(number=KeyError),
        pull(head={"sha": "h1"}),
        pull(head=KeyError),
        pull(base={"ref": 7, "repo": {"default_branch": "main"}}),  # a base ref that is not a string
        pull(base={"repo": {"default_branch": "main"}}),
        pull(base={"ref": "below", "repo": {"default_branch": None}}),  # a default branch that is not a string
        pull(base={"ref": "below"}),
        pull(base=KeyError),
    ]
    for item in bad:
        w.gh.pulls[10] = item
        assert CP._linked_issues(item, REPO, 10, w.env, w.gh) == ([], "unreadable"), item
    w.gh.pulls[10] = pull()
    assert _links(w, 10) == ([101], "timeline")  # the well-formed pull reads


# ---------------------------------------------------------------- the notice


def test_p10_a_notice_with_no_saved_launch_and_unreadable_links_refuses_and_saves_nothing(w):
    w.gh.comments[10] = [_lapsed_comment(10)]
    w.gh.pulls[10] = _pull(101)
    w.gh.closing[10] = None
    assert _notice(w, 10) == {"ok": False, "reason": "pr-links-unreadable"}
    assert not os.path.exists(_state_file(w))
    # a newer park of an entry that holds no launch refuses too, and leaves that entry as it was
    w.gh.closing[10] = []
    assert _notice(w, 10)["kind"] == "lapsed-pass"
    before = _entries(w)
    assert before[0]["launchId"] is None
    w.gh.comments[10].append(_lapsed_comment(10, created_at="2026-10-11T10:00:00Z", cid=1010))
    w.gh.closing[10] = None
    assert _notice(w, 10) == {"ok": False, "reason": "pr-links-unreadable"}
    assert _entries(w) == before


def test_p11_a_newer_park_with_a_saved_launch_and_unreadable_links_keeps_that_launch(w):
    _lane(w, "l-a", 101, "session-a", "a")
    _park(w, 10, issue=101)
    assert _entries(w)[0]["launchId"] == "l-a"
    w.gh.comments[10].append(_lapsed_comment(10, created_at="2026-10-11T10:00:00Z", cid=1010))
    w.gh.closing[10] = None
    out = _notice(w, 10)
    assert out["kind"] == "lapsed-pass" and out["linkSource"] == "unreadable", out  # disclosed
    entry = _entries(w)[0]
    assert entry["launchId"] == "l-a" and entry["parkId"] == 1010 and entry["outcome"] is None


# axis: a saved, unsuperseded launch is kept whatever the link read says; the old `if issues` gate dropped it — see bite-proof record i2658_parked_links
def test_p12_a_newer_park_with_a_saved_launch_and_a_readable_empty_list_keeps_that_launch(w):
    _lane(w, "l-a", 101, "session-a", "a")
    _park(w, 10, issue=101)
    assert _entries(w)[0]["launchId"] == "l-a"
    w.gh.comments[10].append(_lapsed_comment(10, created_at="2026-10-11T10:00:00Z", cid=1010))
    w.gh.pulls[10] = _pull()  # GitHub's list now holds nothing
    out = _notice(w, 10)
    assert out["kind"] == "lapsed-pass" and out["linkSource"] == "github", out
    entry = _entries(w)[0]
    assert entry["launchId"] == "l-a" and entry["parkId"] == 1010 and entry["outcome"] is None


# ---------------------------------------------------------------- the send-back


def test_p13_a_send_back_entry_with_no_saved_launch_and_unreadable_links_is_unread(w):
    _lane(w, "l-a", 101, "session-a", "a")
    _park(w, 10)  # no link: it holds no launch
    _park(w, 11, issue=101)  # a launch is saved
    assert [e["launchId"] for e in _entries(w)] == [None, "l-a"]
    _renew(w)
    w.gh.closing[10] = None
    w.gh.closing[11] = None
    out = _send(w)
    assert {"pr": 10, "reason": "pr-links-unreadable"} in out["unread"]
    assert 10 not in [c["pr"] for c in out["sendBack"] + out["adopt"]] and 10 not in [c["pr"] for c in out["noLane"]]
    # the entry with a saved launch is still sent to that launch's lane, and says its links were unreadable
    assert [(c["pr"], c["launchId"], c["linkSource"]) for c in out["sendBack"]] == [(11, "l-a", "unreadable")]
    assert [e["outcome"] for e in _entries(w)] == [None, None]


# ---------------------------------------------------------------- cleanup


# axis: an unreadable link read refuses the cleanup plan, so nothing is sent or deleted — see bite-proof record i2658_parked_links
def test_p14_a_cleanup_plan_with_unreadable_links_refuses_and_sends_and_deletes_nothing(cw):
    TCC._lane(cw, "l-1", 101)
    want = {"ok": False, "reason": "pr-links-unreadable"}
    cw.gh.closing[TCC.PR] = None  # GitHub's list cannot be read, though the description says "Closes #101"
    assert CC.plan(cw.repo, REPO, TCC.PR, env=cw.env, run=cw.gh) == want
    assert CC.branch(cw.repo, REPO, TCC.PR, env=cw.env, run=cw.gh) == want
    assert CC.record(cw.repo, REPO, TCC.PR, "m-1", "pending", env=cw.env, run=cw.gh) == want
    assert cw.gh.deletes == [] and TCC.BRANCH in cw.gh.branches
    assert not os.path.exists(TCC._state_file(cw))
    cw.gh.closing[TCC.PR] = [_ref(101)]  # the same pull once the read works
    assert CC.plan(cw.repo, REPO, TCC.PR, env=cw.env, run=cw.gh)["ok"] is True
