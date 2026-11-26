"""A blocker's pull request is found from the links GitHub records, never from a pull request body's text (#2652).

A stack layer (a pull request based on a branch other than the default) is linked by the cross-reference GitHub
records on the blocker's timeline; a pull request based on the default branch is linked only when the blocker's
closing pull requests (read once, for the blocker) name it, a manual Development link included, whatever the
timeline says. Every read that cannot answer makes the whole judgement unreadable."""
import json
import subprocess

import pytest

import issue_contract as ic
from test_issue_contract import (
    NO_LINK_WHY, PARENT, PULLS, REPO_PATH, SUBS, _assert_unreadable_and_no_pass, _build_ready, _closing_answer, _cross_ref,
    _card, _head, _in_stack, _Members, _pr_row, _row, _sub, _timeline_path, _vet, _world,
)

TIMELINE = _timeline_path(12)


def _graphql_calls(fake):
    return [call for call in fake.calls if call[:3] == ["gh", "api", "graphql"]]


def _accepted_prs(out):
    return [row["pr"] for row in out["blockers"]["accepted"]]


# --- the two linked forms -----------------------------------------------------


def test_stack_layer_is_linked_by_its_timeline_cross_reference_and_reads_no_closing_references(tmp_path, capsys):
    # axis: a stack layer (based on another branch) is linked by its timeline cross-reference alone
    fake = _world(prs=[_pr_row(101, closes=12)])
    out = _build_ready(tmp_path, capsys, fake, members=_Members({101: _in_stack(900, 1)}))
    assert out["ok"] is True
    assert _accepted_prs(out) == [101]
    assert _graphql_calls(fake) == []


def test_default_base_pr_is_linked_when_the_blockers_closing_references_name_it(tmp_path, capsys):
    # axis: a pull request based on the default branch is linked when the blocker's closing pull requests name it
    fake = _world(prs=[_pr_row(101, closes=12, base="main")])
    out = _build_ready(tmp_path, capsys, fake, members=_Members({101: _in_stack(900, 1)}))
    assert out["ok"] is True
    assert _accepted_prs(out) == [101]
    assert fake.responses[PULLS][1].count("Closes") == 0
    [call] = _graphql_calls(fake)
    # axis: the read asks for the blocker issue's closing pull requests, by the blocker's number
    assert call[:9] == ["gh", "api", "graphql", "-f", "owner=acme", "-f", "name=widgets", "-F", "number=12"]
    assert call[9] == "-f" and call[10].startswith("query=")
    # axis: the GitHub GraphQL names are pinned as literals, never against the production query constant
    query = " ".join(call[10].split())
    for literal in ("repository(owner: $owner, name: $name)", "issue(number: $number)",
                    "closedByPullRequestsReferences(", "pageInfo { hasNextPage }",
                    "nodes { number repository { nameWithOwner } }"):
        assert literal in query, literal


def test_default_base_pr_the_blockers_closing_references_omit_is_not_linked(tmp_path, capsys):
    # axis: a default-base pull request on the timeline that the blocker's closing references do not name is not linked
    fake = _world(
        prs=[_pr_row(101, closes=12, base="main")],
        responses={("graphql", 12): _closing_answer([102])},
    )
    members = _Members({101: _in_stack(900, 1)})
    out = _build_ready(tmp_path, capsys, fake, members=members)
    assert out["reason"] == ic.REFUSAL_BLOCKER_OPEN
    assert out["blockers"]["accepted"] == []
    assert out["blockers"]["held"][0]["why"] == NO_LINK_WHY
    assert members.calls == []


def test_the_default_branch_is_the_one_github_names_not_main(tmp_path, capsys):
    # axis: with default branch `trunk`, a pull request based on `trunk` needs a closing reference, and one based on
    # `main` is a stack layer linked by its timeline cross-reference
    trunk = {REPO_PATH: (0, json.dumps({"default_branch": "trunk"})), ("graphql", 12): _closing_answer([])}
    fake = _world(prs=[_pr_row(101, closes=12, base="trunk")], responses=trunk)
    out = _build_ready(tmp_path, capsys, fake, members=_Members({101: _in_stack(900, 1)}))
    assert out["reason"] == ic.REFUSAL_BLOCKER_OPEN
    assert out["blockers"]["accepted"] == []
    assert [call[8] for call in _graphql_calls(fake)] == ["number=12"]
    layer = _world(prs=[_pr_row(101, closes=12, base="main")], responses={REPO_PATH: trunk[REPO_PATH]})
    out = _build_ready(tmp_path, capsys, layer, members=_Members({101: _in_stack(900, 1)}))
    assert out["ok"] is True
    assert _accepted_prs(out) == [101]
    assert _graphql_calls(layer) == []


def test_a_closing_pull_request_in_another_repository_is_not_this_blockers_link(tmp_path, capsys):
    # axis: a closing pull request counts only when it is a pull request of this repository
    other = _closing_answer([101], repo="other/lib")
    fake = _world(prs=[_pr_row(101, closes=12, base="main")], responses={("graphql", 12): other})
    out = _build_ready(tmp_path, capsys, fake, members=_Members({101: _in_stack(900, 1)}))
    assert out["reason"] == ic.REFUSAL_BLOCKER_OPEN
    assert out["blockers"]["held"][0]["why"] == NO_LINK_WHY


def test_a_closing_pull_request_names_the_repository_ignoring_case(tmp_path, capsys):
    # axis: GitHub repository names ignore case, so a differently cased closing pull request's repository is the same one
    cased = _closing_answer([101], repo="ACME/Widgets")
    fake = _world(prs=[_pr_row(101, closes=12, base="main")], responses={("graphql", 12): cased})
    out = _build_ready(tmp_path, capsys, fake, members=_Members({101: _in_stack(900, 1)}))
    assert out["ok"] is True
    assert _accepted_prs(out) == [101]


def test_closing_references_are_read_once_for_the_blocker_and_never_for_a_stack_layer(tmp_path, capsys):
    # axis: no closing-reference read for a stack layer; the blocker's closing pull requests are read once, however many
    # default-base pull requests are open, so an unrelated pull request's references are never read
    prs = [
        _pr_row(101, closes=12),
        _pr_row(102, closes=12, base="main", links=[]),
        _pr_row(103, closes=12, base="main", links=[]),
    ]
    fake = _world(prs=prs)
    out = _build_ready(tmp_path, capsys, fake, members=_Members({101: _in_stack(900, 1)}))
    assert out["ok"] is True
    assert _accepted_prs(out) == [101]
    assert [call[8] for call in _graphql_calls(fake)] == ["number=12"]
    only_layers = _world(prs=[_pr_row(101, closes=12)])
    _build_ready(tmp_path, capsys, only_layers, members=_Members({101: _in_stack(900, 1)}))
    assert _graphql_calls(only_layers) == []


def test_a_default_base_pr_linked_by_hand_with_no_timeline_mention_is_linked(tmp_path, capsys):
    # axis: a manual Development link shows in the closing references but not as a timeline cross-reference; it links
    fake = _world(
        prs=[_pr_row(101, closes=12, base="main")],
        responses={TIMELINE: (0, json.dumps([{"event": "connected"}]))},
    )
    out = _build_ready(tmp_path, capsys, fake, members=_Members({101: _in_stack(900, 1)}))
    assert out["ok"] is True
    assert _accepted_prs(out) == [101]


def test_a_stack_layer_closing_the_blocker_with_no_timeline_mention_is_not_linked(tmp_path, capsys):
    # axis: a stack layer is linked only by the timeline cross-reference, never by a closing reference alone
    fake = _world(prs=[_pr_row(101, closes=12)], responses={TIMELINE: (0, json.dumps([]))})
    out = _build_ready(tmp_path, capsys, fake, members=_Members({101: _in_stack(900, 1)}))
    assert out["reason"] == ic.REFUSAL_BLOCKER_OPEN
    assert out["blockers"]["held"][0]["why"] == NO_LINK_WHY
    assert _graphql_calls(fake) == []


def test_a_card_never_clears_a_blocker_under_a_feature_in_another_repository(tmp_path, capsys):
    # axis: a card names its feature only by number, so under a parent in another repository only READY clears
    plan_subs = "repos/acme/plans/issues/50/sub_issues?per_page=100&page=1"
    fake = _world(
        prs=[_pr_row(101, closes=12, vet=_card(_head(101)))],
        responses={
            PARENT: (0, json.dumps(_row(50, "open", repo="acme/plans"))),
            plan_subs: (0, json.dumps([_sub(12), _sub(7)])),
        },
    )
    out = _build_ready(tmp_path, capsys, fake, members=_Members({101: _in_stack(900, 1)}))
    assert out["reason"] == ic.REFUSAL_BLOCKER_OPEN
    assert out["blockers"]["accepted"] == []
    assert out["blockers"]["held"][0]["why"] == (
        "its pull request #101's vet card mark names feature #50, not this stack's acme/plans#50")


def test_a_parent_in_another_repository_has_its_sub_issues_read_there(tmp_path, capsys):
    # axis: the feature may live in another repository; its sub-issues are read from the repository the parent names
    plan_subs = "repos/acme/plans/issues/50/sub_issues?per_page=100&page=1"
    fake = _world(
        prs=[_pr_row(101, closes=12)],
        responses={
            PARENT: (0, json.dumps(_row(50, "open", repo="acme/plans"))),
            plan_subs: (0, json.dumps([_sub(12), _sub(7)])),
            SUBS: (1, "", "gh: Not Found (HTTP 404)"),
        },
    )
    out = _build_ready(tmp_path, capsys, fake, members=_Members({101: _in_stack(900, 1)}))
    assert out["ok"] is True
    assert _accepted_prs(out) == [101]
    assert ["gh", "api", plan_subs] in fake.calls
    # axis: the accepted row records no feature for a parent in another repository, so no card can match it at launch
    assert out["blockers"]["accepted"][0]["feature"] is None


# --- the link is GitHub's record, never body text -----------------------------


def test_a_body_whose_first_line_closes_the_blocker_is_no_link_without_a_github_record(tmp_path, capsys):
    # axis: a pull request body's text is never read for the link; no timeline row and no closing reference holds
    body = "Closes #12\n\n" + _vet("READY", _head(101))
    for base in ("layer-base", "main"):
        fake = _world(prs=[_pr_row(101, body=body, base=base)])
        members = _Members({101: _in_stack(900, 1)})
        out = _build_ready(tmp_path, capsys, fake, members=members)
        assert out["reason"] == ic.REFUSAL_BLOCKER_OPEN, base
        assert out["blockers"]["accepted"] == [], base
        assert out["blockers"]["held"][0]["why"] == NO_LINK_WHY, base
        assert members.calls == [], base


def test_a_cross_reference_from_another_repository_or_an_issue_is_no_link(tmp_path, capsys):
    # axis: only a pull request of this repository on the timeline links the blocker
    for row in (
        _cross_ref(101, repo="other/lib"),
        {"event": "cross-referenced", "source": {"issue": {"number": 101, "repository": {"full_name": "acme/widgets"}}}},
    ):
        fake = _world(prs=[_pr_row(101, closes=12)], responses={TIMELINE: (0, json.dumps([row]))})
        out = _build_ready(tmp_path, capsys, fake, members=_Members({101: _in_stack(900, 1)}))
        assert out["reason"] == ic.REFUSAL_BLOCKER_OPEN, row
        assert out["blockers"]["held"][0]["why"] == NO_LINK_WHY, row


def test_a_timeline_cross_reference_names_the_repository_ignoring_case_among_other_events(tmp_path, capsys):
    # axis: a differently cased repository name is the same one, and events that are not cross-references are skipped
    rows = [{"event": "labeled"}, _cross_ref(101, repo="ACME/Widgets"), {"event": "commented"}]
    fake = _world(prs=[_pr_row(101, closes=12)], responses={TIMELINE: (0, json.dumps(rows))})
    out = _build_ready(tmp_path, capsys, fake, members=_Members({101: _in_stack(900, 1)}))
    assert out["ok"] is True
    assert _accepted_prs(out) == [101]


def test_a_timeline_link_to_a_pull_request_that_is_not_open_is_no_link(tmp_path, capsys):
    # axis: only an open pull request is a handed-back layer; a linked one not among the open pulls holds
    fake = _world(prs=[], responses={TIMELINE: (0, json.dumps([_cross_ref(101)]))})
    out = _build_ready(tmp_path, capsys, fake, members=_Members({}))
    assert out["reason"] == ic.REFUSAL_BLOCKER_OPEN
    assert out["blockers"]["held"][0]["why"] == NO_LINK_WHY


def test_two_linked_pull_requests_hold_naming_both(tmp_path, capsys):
    # axis: a stack layer and a closing default-base pull request both linked to one blocker are ambiguous
    prs = [_pr_row(101, closes=12), _pr_row(102, closes=12, base="main")]
    out = _build_ready(tmp_path, capsys, _world(prs=prs), members=_Members({}))
    assert out["reason"] == ic.REFUSAL_BLOCKER_OPEN
    assert out["blockers"]["held"][0]["why"] == "more than one open pull request is linked to it (#101, #102)"


def test_a_default_base_pull_request_that_does_not_close_it_does_not_make_a_second_link(tmp_path, capsys):
    # axis: a default-base pull request on the timeline that does not close the blocker is not counted among the links
    prs = [_pr_row(101, closes=12), _pr_row(102, closes=12, base="main")]
    fake = _world(prs=prs, responses={("graphql", 12): _closing_answer([])})
    out = _build_ready(tmp_path, capsys, fake, members=_Members({101: _in_stack(900, 1)}))
    assert out["ok"] is True
    assert _accepted_prs(out) == [101]


# --- every read that cannot answer is unreadable ------------------------------


class _GraphqlFails:
    """A run that serves the world but raises `error` on a graphql call."""

    def __init__(self, fake, error):
        self.fake = fake
        self.error = error

    def __call__(self, argv, **kw):
        if argv[2] == "graphql":
            raise self.error
        return self.fake(argv, **kw)


BAD_TIMELINES = {
    "the timeline read fails": (1, "", "gh: Server Error (HTTP 500)"),
    "the timeline is not JSON": (0, "not json"),
    "the timeline is not a list": (0, json.dumps({"event": "cross-referenced"})),
    "a timeline row that is not an object": (0, json.dumps([_cross_ref(101), "x"])),
    "a cross-reference without a source": (0, json.dumps([{"event": "cross-referenced"}])),
    "a cross-reference without an issue": (0, json.dumps([{"event": "cross-referenced", "source": {"type": "x"}}])),
    "a cross-reference whose issue is not an object": (
        0, json.dumps([{"event": "cross-referenced", "source": {"issue": 5}}])),
    "a cross-reference with a string number": (
        0, json.dumps([{"event": "cross-referenced", "source": {"issue": {
            "number": "101", "pull_request": {}, "repository": {"full_name": "acme/widgets"}}}}])),
    "a cross-reference with a bool number": (
        0, json.dumps([{"event": "cross-referenced", "source": {"issue": {
            "number": True, "pull_request": {}, "repository": {"full_name": "acme/widgets"}}}}])),
    "a cross-reference with a zero number": (
        0, json.dumps([{"event": "cross-referenced", "source": {"issue": {
            "number": 0, "pull_request": {}, "repository": {"full_name": "acme/widgets"}}}}])),
    "a cross-reference with no repository": (
        0, json.dumps([{"event": "cross-referenced", "source": {"issue": {"number": 101, "pull_request": {}}}}])),
    "a cross-reference with a non-string repository name": (
        0, json.dumps([{"event": "cross-referenced", "source": {"issue": {
            "number": 101, "pull_request": {}, "repository": {"full_name": 5}}}}])),
}


@pytest.mark.parametrize("answer", list(BAD_TIMELINES.values()), ids=list(BAD_TIMELINES))
def test_a_timeline_that_cannot_be_read_or_has_a_malformed_row_is_unreadable(tmp_path, capsys, answer):
    # axis: the blocker's timeline read in full, every row well formed, or the whole judgement is unreadable
    members = _Members({101: _in_stack(900, 1)})
    fake = _world(prs=[_pr_row(101, closes=12)], responses={TIMELINE: answer})
    _assert_unreadable_and_no_pass(_build_ready(tmp_path, capsys, fake, members=members))
    assert members.calls == []


BAD_DEFAULT_BRANCHES = {
    "the default-branch read fails": (1, "", "gh: Not Found (HTTP 404)"),
    "the default-branch answer is not JSON": (0, "not json"),
    "the default-branch answer is not an object": (0, json.dumps(["main"])),
    "the default-branch answer has no default_branch": (0, json.dumps({"name": "widgets"})),
    "the default branch is null": (0, json.dumps({"default_branch": None})),
    "the default branch is empty": (0, json.dumps({"default_branch": ""})),
    "the default branch is not a string": (0, json.dumps({"default_branch": 5})),
}


@pytest.mark.parametrize("answer", list(BAD_DEFAULT_BRANCHES.values()), ids=list(BAD_DEFAULT_BRANCHES))
def test_a_default_branch_that_cannot_be_read_is_unreadable(tmp_path, capsys, answer):
    # axis: the default branch must be a non-empty string, or no pull request can be told a layer from a default-base one
    members = _Members({101: _in_stack(900, 1)})
    fake = _world(prs=[_pr_row(101, closes=12)], responses={REPO_PATH: answer})
    _assert_unreadable_and_no_pass(_build_ready(tmp_path, capsys, fake, members=members))
    assert members.calls == []


def _graph(refs):
    return 0, json.dumps({"data": {"repository": {"issue": {"closedByPullRequestsReferences": refs}}}})


def _node(number, name="acme/widgets"):
    return {"number": number, "repository": {"nameWithOwner": name}}


BAD_CLOSING_REFERENCES = {
    "graphql exits non-zero": (1, "", "gh: Bad credentials (HTTP 401)"),
    "graphql output is not JSON": (0, "not json"),
    "graphql output is not an object": (0, json.dumps([1])),
    "graphql answers errors": (0, json.dumps({"errors": [{"message": "boom"}], "data": None})),
    "graphql answers errors beside data": (
        0, json.dumps({"errors": [{"message": "boom"}], "data": {"repository": {"issue": {
            "closedByPullRequestsReferences": {"pageInfo": {"hasNextPage": False}, "nodes": [_node(101)]}}}}})),
    "graphql answers no data": (0, json.dumps({})),
    "the issue is null": (0, json.dumps({"data": {"repository": {"issue": None}}})),
    "hasNextPage is true": _graph({"pageInfo": {"hasNextPage": True}, "nodes": [_node(101)]}),
    "hasNextPage is missing": _graph({"pageInfo": {}, "nodes": [_node(101)]}),
    "pageInfo is missing": _graph({"nodes": [_node(101)]}),
    "nodes is not a list": _graph({"pageInfo": {"hasNextPage": False}, "nodes": None}),
    "a node is not an object": _graph({"pageInfo": {"hasNextPage": False}, "nodes": [_node(101), "x"]}),
    "a node has a string number": _graph({"pageInfo": {"hasNextPage": False}, "nodes": [_node(101), _node("13")]}),
    "a node has a bool number": _graph({"pageInfo": {"hasNextPage": False}, "nodes": [_node(101), _node(True)]}),
    "a node has a zero number": _graph({"pageInfo": {"hasNextPage": False}, "nodes": [_node(101), _node(0)]}),
    "a node has no repository": _graph({"pageInfo": {"hasNextPage": False}, "nodes": [_node(101), {"number": 13}]}),
    "a node has a non-string repository name": _graph({
        "pageInfo": {"hasNextPage": False}, "nodes": [_node(101), _node(13, name=5)]}),
}


@pytest.mark.parametrize("answer", list(BAD_CLOSING_REFERENCES.values()), ids=list(BAD_CLOSING_REFERENCES))
def test_closing_references_that_cannot_be_read_in_full_are_unreadable(tmp_path, capsys, answer):
    # axis: the blocker's closing pull requests read in full and well formed, or the judgement is unreadable
    members = _Members({101: _in_stack(900, 1)})
    fake = _world(prs=[_pr_row(101, closes=12, base="main")], responses={("graphql", 12): answer})
    _assert_unreadable_and_no_pass(_build_ready(tmp_path, capsys, fake, members=members))
    assert members.calls == []


@pytest.mark.parametrize("error", [subprocess.TimeoutExpired(["gh"], 30), OSError("no gh")], ids=["timeout", "no-gh"])
def test_a_closing_reference_call_that_times_out_or_cannot_start_is_unreadable(tmp_path, capsys, error):
    # axis: a timed-out or unstartable closing-reference call is unreadable, never no references
    members = _Members({101: _in_stack(900, 1)})
    fake = _world(prs=[_pr_row(101, closes=12, base="main")])
    _assert_unreadable_and_no_pass(_build_ready(tmp_path, capsys, _GraphqlFails(fake, error), members=members))
    assert members.calls == []


def _without(row, key):
    return {k: v for k, v in row.items() if k != key}


BAD_BASES = {
    "no base": _without(_pr_row(101, closes=12), "base"),
    "a null base": dict(_pr_row(101, closes=12), base=None),
    "a base that is not an object": dict(_pr_row(101, closes=12), base="main"),
    "a base with no ref": dict(_pr_row(101, closes=12), base={}),
    "a base with an empty ref": dict(_pr_row(101, closes=12), base={"ref": ""}),
    "a base with a non-string ref": dict(_pr_row(101, closes=12), base={"ref": 5}),
}


@pytest.mark.parametrize("bad", list(BAD_BASES.values()), ids=list(BAD_BASES))
def test_an_open_pr_row_with_no_base_ref_is_unreadable_even_beside_a_good_one(tmp_path, capsys, bad):
    # axis: an open-PR row with no base branch name fails the whole read, never held or accepted
    good = _pr_row(102, closes=12)
    members = _Members({102: _in_stack(900, 1)})
    fake = _world(prs=[good, bad])
    _assert_unreadable_and_no_pass(_build_ready(tmp_path, capsys, fake, members=members))
    assert members.calls == []


# --- one head: a moved pull request holds ------------------------------------


def _moved_why(read_at):
    return (
        "its pull request #101 moved between reads (vet read at %s, stack membership at %s); "
        "it is judged again on the next check" % (_head(101), read_at)
    )


def test_a_stack_membership_read_at_another_head_holds_instead_of_unreadable(tmp_path, capsys):
    # axis: a linked membership answer read at another head than the vet holds the blocker, never unreadable
    moved = _in_stack(900, 1)
    moved["queried"]["headRefOid"] = _head(999)
    out = _build_ready(tmp_path, capsys, _world(prs=[_pr_row(101, closes=12)]), members=_Members({101: moved}))
    assert out["ok"] is False
    assert out["reason"] == ic.REFUSAL_BLOCKER_OPEN
    assert out["blockers"]["checked"] is True
    assert out["blockers"]["accepted"] == []
    assert out["blockers"]["held"][0]["why"] == _moved_why(_head(999))


def test_a_not_linked_membership_read_at_another_head_holds_instead_of_unreadable(tmp_path, capsys):
    # axis: a not-linked membership answer read at another head than the vet holds the blocker, never unreadable
    moved = {"ok": False, "reason": ic.stack_check.REASON_NOT_LINKED, "detail": "x", "queried": {"headRefOid": _head(999)}}
    out = _build_ready(tmp_path, capsys, _world(prs=[_pr_row(101, closes=12)]), members=_Members({101: moved}))
    assert out["reason"] == ic.REFUSAL_BLOCKER_OPEN
    assert out["blockers"]["checked"] is True
    assert out["blockers"]["held"][0]["why"] == _moved_why(_head(999))


def test_a_moved_layer_holds_beside_a_layer_that_is_accepted(tmp_path, capsys):
    # axis: one moved layer holds only itself; the other lower layer is still judged
    moved = _in_stack(900, 2)
    moved["queried"]["headRefOid"] = _head(999)
    prs = [_pr_row(101, closes=11), _pr_row(102, closes=12)]
    fake = _world(blocked=(11, 12), subs=(11, 12, 7), prs=prs)
    out = _build_ready(tmp_path, capsys, fake, members=_Members({101: _in_stack(900, 1), 102: moved}))
    assert out["reason"] == ic.REFUSAL_BLOCKER_OPEN
    assert [row["ref"] for row in out["blockers"]["accepted"]] == ["acme/widgets#11"]
    assert [row["ref"] for row in out["blockers"]["held"]] == ["acme/widgets#12"]


def _reader(result):
    return lambda pr, repo, run: result


@pytest.mark.parametrize("result", [
    {"ok": True, "reason": None, "detail": None, "stack": {"number": 900}, "queried": {"position": 1}},
    {"ok": False, "reason": ic.stack_check.REASON_NOT_LINKED, "detail": "x"},
    {"ok": False, "reason": ic.stack_check.REASON_NOT_LINKED, "detail": "x", "queried": {"headRefOid": 5}},
    {"ok": True, "reason": None, "detail": None, "stack": {"number": True}, "queried": {"position": 1, "headRefOid": _head(101)}},
], ids=["linked-no-head", "not-linked-no-head", "not-linked-non-string-head", "linked-malformed-stack"])
def test_a_membership_answer_with_no_head_or_a_malformed_one_stays_unreadable(tmp_path, capsys, result):
    # axis: only a head that differs is a hold; an answer naming no head, or a malformed linked one, is unreadable
    fake = _world(prs=[_pr_row(101, closes=12)])
    _assert_unreadable_and_no_pass(_build_ready(tmp_path, capsys, fake, members=_reader(result)))
