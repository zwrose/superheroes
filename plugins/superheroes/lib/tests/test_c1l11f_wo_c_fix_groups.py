"""C1-L11f WO-C: a fix group ties only when a test-carrying member was carved out, and a member repaired alone after
the group's shared fix says so.

C-a: `verification.merge_and_rank` ties a group into `fixGroups` exactly when, after the carve-out, it has two or more
resulting findings and a carved-out member carries a break-it test; a `carriedTestLost` member is carved out (never
merged) but forms no fix group on its own.
C-b: a fix-group member's record bullet reads "repaired alone" exactly when its latest fix binding is in a later round
than a round whose commit bound it with another member, and that binding's commit binds no other member of the group in
that round; `review_record_session` carries the fact as `fixGroup.repairedAlone: true` and the record's validator takes
that key only with the value `true`.

Edges (C-a): carriedTestLost + plain -> no group, both unmerged findings kept; carriedTestLost + carrier + plain -> one
group of all three; carrier + plain -> one group; only carriedTestLost members -> no group; an invalid grouping -> none.
Edges (C-b): only the shared binding -> shared; two members re-bound together later -> both shared; three members, two
re-bound together later -> all shared; a later commit that also binds another group's member -> judged by this group's
members only; unreadable rounds -> shared.

Bite-proof record: plugins/superheroes/lib/tests/bite_proofs/c1l11f_wo_c_fix_groups.md
"""
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _p in (_HERE, _LIB):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import break_it  # noqa: E402
import review_record as REC  # noqa: E402
import review_record_session as RS  # noqa: E402
import round_driver as RD  # noqa: E402
import session_contract as SC  # noqa: E402
import test_break_it_loop as BL  # noqa: E402
import verification as V  # noqa: E402
from test_fix_groups_c1l11c import A_PATH, A_TITLE, B_TITLE, Grouped, _pinned_git  # noqa: E402,F401
from test_review_record import Fake as RecFake, account, finding as rec_finding, put  # noqa: E402


# ---- C-a: merge_and_rank ------------------------------------------------------------------------------------

def _plain(fid):
    return {"id": fid, "file": "f%s.py" % fid, "line": 1, "title": "t%s" % fid, "severity": "Important"}


def _carrier(fid):
    return dict(_plain(fid), taxonomy=break_it.TAXONOMY, suggestion=BL._block(A_PATH, BL._TEST_FAILING))


def _lost(fid):
    return dict(_plain(fid), carriedTestLost=True)


def test_a_carried_test_lost_member_beside_a_plain_one_is_carved_out_but_ties_no_fix_group():
    out = V.merge_and_rank([_lost("v0"), _plain("v1")], [{"member_ids": ["v0", "v1"]}])
    assert out["fixGroups"] == []
    assert sorted(f["id"] for f in out["findings"]) == ["v0", "v1"] and out["merges"] == []
    # only carriedTestLost members: carved out, nothing to tie
    out = V.merge_and_rank([_lost("v0"), _lost("v1")], [{"member_ids": ["v0", "v1"]}])
    assert out["fixGroups"] == [] and sorted(f["id"] for f in out["findings"]) == ["v0", "v1"] and out["merges"] == []
    # the carriedTestLost marker survives, unmerged, beside two plain members that do merge
    out = V.merge_and_rank([_lost("v0"), _plain("v1"), _plain("v2")], [{"member_ids": ["v0", "v1", "v2"]}])
    assert out["fixGroups"] == [] and len(out["merges"]) == 1
    assert [f["id"] for f in out["findings"] if f.get("carriedTestLost") is True] == ["v0"]


def test_a_carried_test_lost_member_beside_a_test_carrier_and_a_plain_one_still_ties_all_three_results():
    out = V.merge_and_rank([_lost("v0"), _carrier("v1"), _plain("v2")], [{"member_ids": ["v0", "v1", "v2"]}])
    assert out["fixGroups"] == [{"group_id": "g0", "member_ids": ["v0", "v1", "v2"]}]
    assert out["merges"] == [] and sorted(f["id"] for f in out["findings"]) == ["v0", "v1", "v2"]
    # unchanged: a carrier beside one plain member ties; an invalid grouping and no grouping tie nothing
    assert V.merge_and_rank([_carrier("v0"), _plain("v1")], [{"member_ids": ["v0", "v1"]}])["fixGroups"] == [
        {"group_id": "g0", "member_ids": ["v0", "v1"]}]
    assert V.merge_and_rank([_lost("v0"), _plain("v1")], [{"member_ids": ["v0"]}])["fixGroups"] == []
    assert V.merge_and_rank([_lost("v0"), _plain("v1")], None)["fixGroups"] == []


# ---- C-b: the bullet of a member repaired alone ------------------------------------------------------------

@pytest.fixture
def grouped(tmp_path):
    return Grouped(tmp_path)


def _bullets(state):
    return {f["title"]: REC._finding_bullet(f) for f in RS._findings_and_merges(state)[0]}


def _repair(grouped, repaired, discharged):
    """Round 1's shared fix, then `discharged` is recorded fixed, `repaired` is requeued and repaired alone."""
    state, cfg = grouped.state, grouped.state["config"]
    sha = grouped.commit_shared()
    grouped.fold(grouped.bind(sha, grouped.key_a, grouped.key_b))
    RD._record_disposition(state, discharged, "fixed", 1)
    assert RD._queue_fix_batch(state, cfg, [dict(r) for r in state["fixBatch"]]) == "queued"
    BL._write(grouped.world.repo, BL.CHARGE_PATH, BL._CHARGE_IDEMPOTENT + "# idempotent\n")
    repair = BL._commit(grouped.world.repo, "repair the retry alone")
    cfg[RD.FIX_FOLD_HEAD_KEY] = repair
    grouped.fold(grouped.bind(repair, repaired))
    RD._record_disposition(state, repaired, "fixed", 2)
    return sha, repair


def test_a_member_repaired_alone_after_the_shared_fix_reads_so_and_its_sibling_reads_shared(grouped):
    state, ka, kb = grouped.state, grouped.key_a, grouped.key_b
    shared, repair = _repair(grouped, repaired=kb, discharged=ka)
    listed = {f["title"]: f for f in RS._findings_and_merges(state)[0]}
    assert listed[B_TITLE]["fixGroup"]["commit"] == repair and listed[B_TITLE]["fixGroup"]["repairedAlone"] is True
    assert listed[A_TITLE]["fixGroup"]["commit"] == shared and "repairedAlone" not in listed[A_TITLE]["fixGroup"]
    gid = listed[A_TITLE]["fixGroup"]["id"]
    bullets = _bullets(state)
    assert bullets[B_TITLE].endswith(" · repaired alone after the group's shared fix (group %s)" % gid)
    assert "one fix shared" not in bullets[B_TITLE]
    assert bullets[A_TITLE].endswith(" · one fix shared with 1 other finding(s) (group %s)" % gid)
    for f in listed.values():
        assert REC._fix_group_fault(f["fixGroup"]) is None


def test_commit_inequality_is_symmetric_so_only_the_member_actually_repaired_later_reads_alone(grouped):
    state, ka, kb = grouped.state, grouped.key_a, grouped.key_b
    _repair(grouped, repaired=ka, discharged=kb)
    bullets = _bullets(state)
    assert " · repaired alone after the group's shared fix (group " in bullets[A_TITLE]
    assert " · one fix shared with 1 other finding(s) (group " in bullets[B_TITLE]


def _synthetic(rounds, members, fix_group_of=None):
    """A bare session state whose findings are `members` (each in one fix group) and whose rounds carry `rounds`
    ``{n: [(finding, commit)]}`` as the round's fix bindings."""
    gid = "fg-x"
    rows = [{"id": m, "findingKey": m, "file": "%s.py" % m, "line": 1, "title": "title %s" % m, "severity": "Important",
             "fixGroup": {"id": gid, "members": list(members if fix_group_of is None else fix_group_of(m))}}
            for m in members]
    return {"findings": rows, "rounds": {str(n): {"fix": {"commits": [{"finding": f, "commit": c} for f, c in bound]}}
                                         for n, bound in rounds.items()}}


def _synthetic_bullets(state):
    return {f["id"]: REC._finding_bullet(f) for f in RS._findings_and_merges(state)[0]}


ALONE, SHARED = " · repaired alone after the group's shared fix", " · one fix shared with"


def test_two_members_rebound_together_in_a_later_round_both_read_shared():
    state = _synthetic({1: [("a", "c1"), ("b", "c1")], 2: [("a", "c2"), ("b", "c2")]}, ["a", "b"])
    bullets = _synthetic_bullets(state)
    assert all(SHARED in bullets[m] and ALONE not in bullets[m] for m in "ab")


def test_a_carrier_bound_with_a_plain_sibling_only_through_the_carrier_reads_a_later_solo_repair_as_alone():
    # the fold stores a binding for the test carrier `a` only; the plain sibling `b` rides in the round's fix report
    state = _synthetic({1: [("a", "c1")], 2: [("a", "c2")]}, ["a", "b"])
    state["rounds"]["1"]["fixReportedKeys"] = ["a", "b"]
    state["rounds"]["2"]["fixReportedKeys"] = ["a"]
    bullets = _synthetic_bullets(state)
    assert ALONE in bullets["a"] and SHARED not in bullets["a"]
    # a later round whose fix report still names the sibling is no solo repair
    state["rounds"]["2"]["fixReportedKeys"] = ["a", "b"]
    assert ALONE not in _synthetic_bullets(state)["a"]


def test_three_members_two_rebound_together_later_read_shared_and_none_reads_alone():
    state = _synthetic({1: [("a", "c1"), ("b", "c1"), ("c", "c1")], 2: [("a", "c2"), ("b", "c2")]}, ["a", "b", "c"])
    bullets = _synthetic_bullets(state)
    assert all(SHARED in bullets[m] and ALONE not in bullets[m] for m in "abc")
    # one of the three repaired alone later: that one reads alone, the other two read shared
    state = _synthetic({1: [("a", "c1"), ("b", "c1"), ("c", "c1")], 2: [("c", "c2")]}, ["a", "b", "c"])
    bullets = _synthetic_bullets(state)
    assert ALONE in bullets["c"] and SHARED in bullets["a"] and SHARED in bullets["b"]


def test_a_member_whose_only_binding_is_the_shared_one_reads_shared():
    state = _synthetic({1: [("a", "c1"), ("b", "c1")]}, ["a", "b"])
    bullets = _synthetic_bullets(state)
    assert all(SHARED in bullets[m] and ALONE not in bullets[m] for m in "ab")


def test_a_member_first_bound_alone_and_never_with_a_sibling_reads_shared():
    # no round bound it together with another member, so there is no shared fix to have been repaired alone after
    state = _synthetic({1: [("a", "c1")], 2: [("a", "c2")]}, ["a", "b"])
    assert ALONE not in _synthetic_bullets(state)["a"]


def test_a_later_commit_that_also_binds_a_member_of_another_group_is_judged_by_this_groups_members_only():
    state = _synthetic({1: [("a", "c1"), ("b", "c1")], 2: [("b", "c2"), ("x", "c2")]}, ["a", "b"])
    state["findings"].append({"id": "x", "findingKey": "x", "file": "x.py", "line": 1, "title": "title x", "severity": "Important",
                              "fixGroup": {"id": "fg-y", "members": ["x", "z"]}})
    bullets = _synthetic_bullets(state)
    assert ALONE in bullets["b"] and SHARED in bullets["a"]


@pytest.mark.parametrize("rounds", [
    [],
    {"1": "not a round"},
    {"1": {"fix": {"commits": "not a list"}}, "2": {"fix": {"commits": [{"finding": "b", "commit": "c2"}]}}},
    {"1": {"fix": {"commits": [{"finding": "a", "commit": "c1"}, {"finding": "b", "commit": "c1"}, "stray"]}},
     "2": {"fix": {"commits": [{"finding": "b", "commit": "c2"}]}}},
])
def test_unreadable_rounds_read_shared_never_alone(rounds):
    state = _synthetic({}, ["a", "b"])
    state["rounds"] = rounds
    assert all(ALONE not in b for b in _synthetic_bullets(state).values())


def test_the_record_takes_repaired_alone_only_as_true_and_the_bullet_reads_it(tmp_path):
    group = {"id": "fg-1", "members": ["a", "b"], "commit": "abc1234"}
    assert REC._fix_group_fault(dict(group, repairedAlone=True)) is None
    for bad in (False, "true", 1, None, [], {}):
        assert REC._fix_group_fault(dict(group, repairedAlone=bad)) == ".repairedAlone", bad
        fake = RecFake()
        out = REC.write(put(tmp_path, account(findings=[rec_finding(fixGroup=dict(group, repairedAlone=bad))])),
                        str(tmp_path), fake.readers())
        assert (out["ok"], out.get("reason")) == (False, "review-account-invalid"), (bad, out)
        assert out["detail"].startswith("findings[0].fixGroup.repairedAlone"), (bad, out)
        assert fake.comments == []
    bullet = REC._finding_bullet(rec_finding(fixGroup=dict(group, repairedAlone=True)))
    assert bullet.endswith(" · repaired alone after the group's shared fix (group fg-1)")
