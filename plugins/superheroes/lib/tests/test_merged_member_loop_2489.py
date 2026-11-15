"""#2489: the review loop rules on each finding the synthesis merged into another.

When review synthesis merges findings, only the representative is fixed and audited. The loop now lists the merged
members on the representative's audit target (`mergedMembers`), credits a member fixed only on the audit's own answer
for it (`memberResults` on the representative's fixed disposition), reopens every other member as its own finding when
the audit discharges the representative, and settles at the loop's end any member left under a fixed representative
with no ruling of its own.

Unit tests drive the real `_audit_targets`, `_fold_audits` and `_settle_open_findings` on hand-built states. The three
end-to-end arms drive the real round driver (`cmd_next` / `cmd_submit`) on a real throwaway repository with the same
scripted fixer (it edits only the lock line) and auditor (it discharges only the target titled LOCK):

  arm A   LOCK and CHECK are merged, the auditor answers no member: CHECK is reopened and never reads fixed;
  arm A2  the same, the auditor answers CHECK `fixed: true` on the LOCK target: CHECK reads fixed;
  arm B   no merge: exactly as before, CHECK is left for the owner at the round cap.

Each arm runs twice: in a fresh session (the panel raises both findings) and in the carried shape (session 1 left CHECK
open, session 2 carries it, and its scoped finder raises LOCK).

Bite-proof record: i2489_member_loop
"""
import copy
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _p in (_HERE, _LIB):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import audits  # noqa: E402
import review_diff_bytes  # noqa: E402
import review_record_session as RS  # noqa: E402
import round_driver as RD  # noqa: E402
import session_contract as SC  # noqa: E402
import test_break_it_loop as BL  # noqa: E402
import test_c1l11b_carried_findings as CF  # noqa: E402
import test_c1l11b_returning_session as TS  # noqa: E402
import test_review_record_session as TRRS  # noqa: E402
import test_round_driver as TRD  # noqa: E402
from test_c1l11b_returning_session import _isolated_git  # noqa: E402,F401  (autouse: no global git config)

CHECKS = {name: {"answer": "yes", "why": "checked"} for name in audits.CHECK_NAMES}
REP, M_A, M_B, M_C, OTHER = "rep-lock", "mem-a", "mem-b", "mem-c", "other-one"
CHARGE = "src/payments/charge.py"


# --- hand-built states ---------------------------------------------------------------------------------------------

def _ledger_row(key, title, line, **over):
    row = {"id": "F-" + key, SC.FINDING_KEY_FIELD: key, "title": title, "severity": "Important", "file": CHARGE,
           "line": line, "consequence": "a customer is charged twice", "body": "body of " + title,
           "suggestion": "suggestion for " + title, "dimension": "code-reviewer", "taxonomy": "Correctness",
           SC.RAISED_ROUND_FIELD: 1, SC.RAISED_SEQ_FIELD: 1}
    row.update(over)
    return row


def _world(tmp_path, members=(M_A, M_B), extra_rows=()):
    """A round-2 state: REP is the fix batch's one finding and every key in ``members`` is merged into it."""
    world = BL.World(tmp_path)
    state = world.state
    state["round"] = 2
    state["rounds"].setdefault("2", {})
    state[SC.DISPOSITION_LEDGER_OWNER_FIELD] = SC.DISPOSITION_LEDGER_OWNER_VALUE
    state["dispositionSeqCounter"] = 10  # a disposition written now is newer than every row raised below (raisedSeq 1)
    rep = _ledger_row(REP, "LOCK: released early", 5)
    rows = [rep] + [_ledger_row(key, "member " + key, 10 + i, **{SC.MERGED_INTO_FIELD: REP})
                    for i, key in enumerate(members)] + list(extra_rows)
    state[SC.DISPOSITION_LEDGER_KEY] = rows
    state["findings"] = [copy.deepcopy(rep)]
    state["fixBatch"] = [copy.deepcopy(rep)]
    return world


def _targets(world):
    state = world.state
    state["_auditTargets"] = RD._audit_targets(state, state["config"], {})
    return state["_auditTargets"]


def _answer(key, fixed=True, why="the member's own part is fixed"):
    return {"id": key, "fixed": fixed, "why": why}


def _fold(world, members=None, ruling="discharged", targets=None):
    """Fold one audit round over the state's audit targets: every target takes ``ruling`` and answers ``members``."""
    state = world.state
    targets = targets if targets is not None else _targets(world)
    state["_auditTargets"] = targets
    state["_verifyThen"] = RD.VERIFY_THEN_POST_AUDITS
    results = []
    for target in targets:
        result = {"id": target["id"], "ruling": ruling, "reason": "the fix holds", "checks": CHECKS}
        if members is not None:
            result["members"] = members
        results.append(result)
    manifest = {t["id"]: t.get("auditorVendor") for t in targets}
    RD._fold(state, state["config"], RD.P_AUDITS, {"results": results, "collectionManifest": manifest},
             session_dir=str(world.session))
    return state


def _ledger(state, key):
    [row] = [r for r in state[SC.DISPOSITION_LEDGER_KEY] if SC.finding_identity_key(r) == key]
    return row


# --- E4 / edge 1: the target lists its members ---------------------------------------------------------------------

def test_the_target_lists_every_finding_merged_into_it_sorted_by_id_with_its_content(tmp_path):
    # axis: the representative's target carries each merged finding, a chained one included, sorted by id — see bite-proof record i2489_member_loop
    world = _world(tmp_path, members=(M_B, M_A))
    world.state[SC.DISPOSITION_LEDGER_KEY].append(_ledger_row(M_C, "member " + M_C, 30, **{SC.MERGED_INTO_FIELD: M_A}))
    [target] = _targets(world)
    assert [m["id"] for m in target["mergedMembers"]] == [M_A, M_B, M_C]
    assert target["mergedMembers"][0] == {
        "id": M_A, "title": "member " + M_A, "consequence": "a customer is charged twice", "file": CHARGE,
        "line": 11, "body": "body of member " + M_A, "suggestion": "suggestion for member " + M_A}


def test_a_target_with_nothing_merged_into_it_carries_no_members_key(tmp_path):
    other = _ledger_row(OTHER, "an unrelated finding", 40)
    world = _world(tmp_path, members=(M_A,), extra_rows=[other])
    world.state["fixBatch"].append(copy.deepcopy(other))
    targets = {t["id"]: t for t in _targets(world)}
    assert [m["id"] for m in targets[REP]["mergedMembers"]] == [M_A]
    assert "mergedMembers" not in targets[OTHER]


def test_edge10_an_unreadable_ledger_lists_no_members(tmp_path):
    world = _world(tmp_path)
    world.state[SC.DISPOSITION_LEDGER_KEY] = "not a ledger"
    [target] = _targets(world)
    assert "mergedMembers" not in target


# --- edges 1-3: the ruling on each member --------------------------------------------------------------------------

def test_edge1_a_member_answered_fixed_is_listed_fixed_stays_merged_and_reads_fixed_in_the_account(tmp_path):
    world = _world(tmp_path, members=(M_A,))
    state = _fold(world, members=[_answer(M_A, True)])
    rep = _ledger(state, REP)
    assert rep["disposition"] == "fixed"
    assert rep[SC.MEMBER_RESULTS_FIELD] == [{SC.FINDING_KEY_FIELD: M_A, "fixed": True}]
    assert _ledger(state, M_A)[SC.MERGED_INTO_FIELD] == REP
    assert state["_auditOutcome"]["notDischarged"] == [] and len(state["_auditTargets"]) == 1
    assert "membersReopened" not in state["rounds"]["2"]
    outcome, reason, _rep = RS._decide(_ledger(state, M_A), *RS.decision_inputs(state))
    assert outcome == "fixed" and RS.MEMBER_RULED_FIXED_NOTE in reason, (outcome, reason)


def test_edge2_a_member_answered_not_fixed_is_reopened_and_never_reads_fixed(tmp_path):
    # axis: a member's `memberResults` row carries its own answer, never the representative's — see bite-proof record i2489_member_loop
    world = _world(tmp_path, members=(M_A, M_B))
    state = _fold(world, members=[_answer(M_A, True), _answer(M_B, False, "the second part is still unfixed")])
    assert _ledger(state, REP)[SC.MEMBER_RESULTS_FIELD] == [
        {SC.FINDING_KEY_FIELD: M_A, "fixed": True}, {SC.FINDING_KEY_FIELD: M_B, "fixed": False}]
    assert _ledger(state, M_A)[SC.MERGED_INTO_FIELD] == REP
    reopened = _ledger(state, M_B)
    assert SC.MERGED_INTO_FIELD not in reopened and "disposition" not in reopened
    assert state["_auditOutcome"]["notDischarged"] == [M_B]
    [entry] = [a for a in state["_auditOutcome"]["audits"] if a["id"] == M_B]
    assert entry["ruling"] == "not-discharged" and entry["reopenedFrom"] == REP
    assert entry["reason"] == ("merged into %s, whose fix the audit cleared, but the audit did not rule this finding's "
                               "own part fixed (the second part is still unfixed)" % REP)
    assert state["rounds"]["2"]["membersReopened"] == [{"findingKey": M_B, "into": REP, "answer": False}]
    assert [d["detail"] for d in state["decisions"] if d["kind"] == "merged-member-reopened"] == [M_B]
    outcome, _reason, _rep = RS._decide(reopened, *RS.decision_inputs(state))
    assert outcome != "fixed"


def test_edge2_the_reopened_member_stands_as_an_audit_target_built_from_its_ledger_content(tmp_path):
    world = _world(tmp_path, members=(M_A,))
    original = _targets(world)
    state = _fold(world, members=[_answer(M_A, False)], targets=original)
    assert len(original) == 1, "the local target list keeps the original"
    [rep_target, member_target] = state["_auditTargets"]
    assert rep_target["id"] == REP
    assert member_target == {
        "id": M_A, SC.FINDING_KEY_FIELD: M_A, "identity": RD.finding_identity(_ledger(state, M_A)), "file": CHARGE,
        "line": 10, "title": "member " + M_A, "severity": "Important",
        "classKey": member_target["classKey"], "dimension": "code-reviewer", "taxonomy": "Correctness",
        "consequence": "a customer is charged twice", "body": "body of member " + M_A,
        "suggestion": "suggestion for member " + M_A, SC.RAISED_ROUND_FIELD: 1, "reopenedFrom": REP}
    assert member_target["classKey"]


def test_edge3_a_member_the_result_does_not_answer_is_reopened(tmp_path):
    # axis: a member the audit did not answer is reopened, never credited fixed — see bite-proof record i2489_member_loop
    world = _world(tmp_path, members=(M_A, M_B))
    state = _fold(world, members=None)
    assert _ledger(state, REP)[SC.MEMBER_RESULTS_FIELD] == [
        {SC.FINDING_KEY_FIELD: M_A, "fixed": False}, {SC.FINDING_KEY_FIELD: M_B, "fixed": False}]
    for key in (M_A, M_B):
        assert SC.MERGED_INTO_FIELD not in _ledger(state, key)
    assert state["_auditOutcome"]["notDischarged"] == [M_A, M_B]
    assert [t["id"] for t in state["_auditTargets"]] == [REP, M_A, M_B]
    assert state["rounds"]["2"]["membersReopened"] == [
        {"findingKey": M_A, "into": REP, "answer": None}, {"findingKey": M_B, "into": REP, "answer": None}]
    [entry] = [a for a in state["_auditOutcome"]["audits"] if a["id"] == M_A]
    assert entry["reason"].endswith("(not answered)")
    assert "membersReopened" in state["rounds"]["2"]


# --- edges 4-5, 10: where the members are left alone ---------------------------------------------------------------

def test_edge4_a_target_not_discharged_keeps_its_members_merged_and_they_ride_its_next_audit(tmp_path):
    world = _world(tmp_path, members=(M_A, M_B))
    state = _fold(world, members=[_answer(M_A, True), _answer(M_B, True)], ruling="not-discharged")
    assert state["_auditOutcome"]["notDischarged"] == [REP]
    for key in (M_A, M_B):
        assert _ledger(state, key)[SC.MERGED_INTO_FIELD] == REP
    assert SC.MEMBER_RESULTS_FIELD not in _ledger(state, REP) and "membersReopened" not in state["rounds"]["2"]
    assert len(state["_auditTargets"]) == 1
    [again] = RD._audit_targets(state, state["config"], {})
    assert [m["id"] for m in again["mergedMembers"]] == [M_A, M_B]


@pytest.mark.parametrize("kind", ["rider", "carried"])
def test_edge5_a_rider_or_carried_target_gets_no_member_handling(tmp_path, kind):
    world = _world(tmp_path, members=(M_A,))
    state = world.state
    targets = _targets(world)
    if kind == "rider":
        targets[0]["spawnedFrom"] = "a-parent-key"
    else:
        state["_carriedAudited"] = {REP: copy.deepcopy(state["findings"][0])}
        state["rounds"]["2"]["carried"] = {"keys": [REP], "auditBase": None, "discharged": [], "sentBack": []}
    _fold(world, members=None, targets=targets)
    assert SC.MEMBER_RESULTS_FIELD not in _ledger(state, REP)
    assert _ledger(state, M_A)[SC.MERGED_INTO_FIELD] == REP
    assert len(state["_auditTargets"]) == 1 and "membersReopened" not in state["rounds"]["2"]
    assert state["_auditOutcome"]["notDischarged"] == []


def test_edge10_an_unreadable_ledger_at_the_fold_reopens_nothing_and_credits_no_member(tmp_path):
    world = _world(tmp_path, members=(M_A,))
    targets = _targets(world)
    assert [m["id"] for m in targets[0]["mergedMembers"]] == [M_A]
    world.state[SC.DISPOSITION_LEDGER_KEY] = "not a ledger"
    state = _fold(world, members=None, targets=targets)
    assert len(state["_auditTargets"]) == 1 and "membersReopened" not in state["rounds"]["2"]
    assert state["_auditOutcome"]["notDischarged"] == []
    assert not any(SC.MEMBER_RESULTS_FIELD in row for row in state[SC.DISPOSITION_LEDGER_KEY])


# --- edges 7-8: the extra audit round and the cap ------------------------------------------------------------------

def test_edge7_8_a_member_reopened_in_the_extra_audit_round_hands_the_pr_back_naming_it_and_is_left_for_the_owner(tmp_path):
    world = _world(tmp_path, members=(M_A,))
    world.state["extraAudit"] = {"round": 2}
    world.state.pop("_verifyThen", None)
    state = world.state
    targets = _targets(world)
    results = [{"id": REP, "ruling": "discharged", "reason": "the fix holds", "checks": CHECKS}]
    state["_auditTargets"] = targets
    RD._fold(state, state["config"], RD.P_AUDITS,
             {"results": results, "collectionManifest": {REP: targets[0].get("auditorVendor")}},
             session_dir=str(world.session))
    assert state["terminal"] == "handed-back"
    [handed] = [d for d in state["decisions"] if d["kind"] == "extra-audit-open"]
    assert M_A in handed["detail"] and "not discharged" in handed["detail"]
    row = _ledger(state, M_A)
    assert row["disposition"] == "left-for-owner" and row.get(SC.OPEN_AT_LOOP_END_FIELD) is True
    assert SC.MERGED_INTO_FIELD not in row


# --- edge 9: the end-of-loop settle --------------------------------------------------------------------------------

def test_edge9_the_settle_leaves_open_a_member_under_a_fixed_representative_with_no_ruling_of_its_own(tmp_path):
    # axis: a member under a fixed representative with no ruling is settled left-for-owner open at the loop's end, never skipped as merged — see bite-proof record i2489_member_loop
    world = _world(tmp_path, members=(M_A, M_B))
    state = world.state
    rep = _ledger(state, REP)
    rep.update({"disposition": "fixed", "dispositionRound": 2, SC.DISPOSITION_SEQ_FIELD: 9,
                SC.MEMBER_RESULTS_FIELD: [{SC.FINDING_KEY_FIELD: M_B, "fixed": True}]})
    refuted = _ledger_row("rep-refuted", "REFUTED one", 50, disposition="refuted", dispositionRound=1,
                          refutedReason="not a defect", **{SC.DISPOSITION_SEQ_FIELD: 8})
    under_refuted = _ledger_row("mem-refuted", "member of refuted", 51, **{SC.MERGED_INTO_FIELD: "rep-refuted"})
    state[SC.DISPOSITION_LEDGER_KEY] += [refuted, under_refuted]
    state["terminal"] = "handed-back"
    RD._settle_open_findings(state, cap=True)
    opened = _ledger(state, M_A)
    assert opened["disposition"] == "left-for-owner" and opened.get(SC.OPEN_AT_LOOP_END_FIELD) is True, opened
    assert SC.MERGED_INTO_FIELD not in opened
    assert "still open when the loop reached its round cap" in opened["settledReason"]
    # a member its representative's audit ruled fixed stays merged, as does a member under a representative that is not fixed
    assert _ledger(state, M_B)[SC.MERGED_INTO_FIELD] == REP and "disposition" not in _ledger(state, M_B)
    assert _ledger(state, "mem-refuted")[SC.MERGED_INTO_FIELD] == "rep-refuted"
    assert "disposition" not in _ledger(state, "mem-refuted")
    # idempotent: a second settle finds nothing left
    before = copy.deepcopy(state[SC.DISPOSITION_LEDGER_KEY])
    RD._settle_open_findings(state, cap=True)
    assert state[SC.DISPOSITION_LEDGER_KEY] == before


# --- the end-to-end arms -------------------------------------------------------------------------------------------

LOCK_TITLE = "LOCK: the lock is released before the write finishes"
CHECK_TITLE = "CHECK: the result of the write is never checked"
LOCK_LINE, CHECK_LINE = 27, 3  # the two lines the first leg edited, so each sits in a hunk of the pull request


def _panel_finding(title, line):
    return {"title": title, "severity": "Important", "consequence": TRD._CONSEQUENCE, "file": CF.SHARED, "line": line,
            "body": "body of " + title, "suggestion": "suggestion for " + title}


class Script:
    """The scripted seats of one arm. The panel raises LOCK and CHECK; the synthesis merges CHECK into LOCK when
    ``merge``; the fixer edits only the lock line, in a real commit; the auditor discharges only the target titled
    LOCK and answers each member of its target ``member_answer`` (None: it answers none)."""

    def __init__(self, session, merge, member_answer):
        self.s = session
        self.merge = merge
        self.member_answer = member_answer
        self.base = CF._respond(round1_findings=[_panel_finding(LOCK_TITLE, LOCK_LINE),
                                                 _panel_finding(CHECK_TITLE, CHECK_LINE)])
        self.batches = []  # (round, [titles]) of every apply-fixes step
        self.fixes = 0

    def __call__(self, phase, payload, rnd):
        art = self.base(phase, payload, rnd)
        if phase == RD.P_PANEL:
            dims = self.s.state()["config"]["dimensions"]
            art = dict(art, seats={dim: art["seats"].get(dim, {"findings": []}) for dim in dims})
        elif phase == RD.P_SYNTHESIS and self.merge:
            by_title = {f["title"]: f["id"] for f in payload["findings"]}
            # the merge keeps the last of two equally severe members as the representative: LOCK last keeps LOCK
            art = {"grouping": [{"group_id": "g1", "member_ids": [by_title[CHECK_TITLE], by_title[LOCK_TITLE]]}]}
            vendor = RD._nonpanel_selection(self.s.state(), self.s.dir, RD.P_SYNTHESIS)[0]
            if vendor:
                art["synthesisVendor"] = vendor
        elif phase == RD.P_AUDITS:
            by_id = {t["id"]: t for t in payload["targets"]}
            for result in art["results"]:
                target = by_id[result["id"]]
                result["ruling"] = "discharged" if target["title"] == LOCK_TITLE else "not-discharged"
                if self.member_answer is not None and target.get("mergedMembers"):
                    result["members"] = [_answer(m["id"], self.member_answer) for m in target["mergedMembers"]]
        elif phase == RD.P_APPLY_FIXES:
            self.batches.append((rnd, [f["title"] for f in payload["batch"]]))
            self.fixes += 1
            self.s.repo.write(CF.SHARED, CF._shared(**{str(LOCK_LINE): "lock_held_%d = 1\n" % self.fixes}))
            self.s.repo.commit("fix the lock line %d" % self.fixes)
            art = {"fixes": []}
        return art


def _drive(s, script, limit=60):
    """next/submit until the terminal; returns the terminal answer and every (action, round)."""
    seen = []
    for step in range(limit):
        n = s.next(first=step == 0)
        seen.append((n["action"], n["round"]))
        if n["action"] == RD.P_TERMINAL:
            return n, seen
        art = script(n["phase"], n["payload"], n["round"])
        if n["phase"] == RD.P_VERIFIERS:
            vendor = RD._nonpanel_selection(s.state(), s.dir, RD.P_VERIFIERS)[0]
            art = dict(art, verifierVendor=vendor) if vendor else art
        art = TRD._claim_reviewer(s.dir, n["phase"], art)
        sub = RD.cmd_submit(s.dir, n["phase"], n["attempt"], n["expectedStateHash"], art)
        assert sub["ok"], (n["phase"], sub)
    raise AssertionError("no terminal in %d steps: %s" % (limit, seen))


def _arm(tmp_path, monkeypatch, merge, member_answer):
    s = TS.Session(tmp_path, monkeypatch, first=CF.FIRST, earlier=None)
    s.cfg["headSha"] = s.head
    script = Script(s, merge, member_answer)
    terminal, seen = _drive(s, script)
    account = RS.account_from_session(s.dir, TRRS.extras())["findings"]
    by_title = {f["title"]: f for f in account}
    return s, script, terminal, seen, by_title


def test_arm_a_a_merged_member_the_audit_does_not_answer_is_reopened_fixed_in_a_later_batch_and_never_reads_fixed(tmp_path, monkeypatch):
    s, script, terminal, seen, by_title = _arm(tmp_path, monkeypatch, merge=True, member_answer=None)
    first_round, first_batch = script.batches[0]
    assert first_batch == [LOCK_TITLE], "CHECK was merged into LOCK, so only LOCK is fixed and audited at first"
    assert any(CHECK_TITLE in titles for _round, titles in script.batches[1:]), script.batches
    state = s.state()
    assert [d for d in state["decisions"] if d["kind"] == "merged-member-reopened"], state["decisions"]
    assert state["rounds"]["2"]["membersReopened"][0]["answer"] is None
    assert terminal["payload"]["verdict"] != "converged", seen
    assert by_title[LOCK_TITLE]["outcome"] == "fixed"
    assert by_title[CHECK_TITLE]["outcome"] == "left-for-owner", by_title[CHECK_TITLE]
    assert "(merged into" not in by_title[CHECK_TITLE]["reason"]
    assert not any("settle-delta" in str(d.get("detail")) for d in state["decisions"]), state["decisions"]


def test_arm_a2_a_merged_member_the_auditor_answers_fixed_reads_fixed_with_the_merge_in_its_reason(tmp_path, monkeypatch):
    s, script, terminal, seen, by_title = _arm(tmp_path, monkeypatch, merge=True, member_answer=True)
    assert script.batches[0][1] == [LOCK_TITLE] and len(script.batches) == 1, script.batches
    assert terminal["payload"]["verdict"] == "converged", seen
    state = s.state()
    assert "membersReopened" not in state["rounds"]["2"]
    assert by_title[LOCK_TITLE]["outcome"] == "fixed"
    check = by_title[CHECK_TITLE]
    assert check["outcome"] == "fixed", check
    assert check["reason"].endswith(" (merged into %s)" % by_title[LOCK_TITLE]["id"]), check
    assert RS.merged_into(check["reason"]) == by_title[LOCK_TITLE]["id"]


def test_arm_b_with_no_merge_the_unfixed_finding_is_left_for_the_owner_at_the_cap_as_before(tmp_path, monkeypatch):
    s, script, terminal, seen, by_title = _arm(tmp_path, monkeypatch, merge=False, member_answer=None)
    assert sorted(script.batches[0][1]) == sorted([LOCK_TITLE, CHECK_TITLE])
    assert terminal["payload"]["verdict"] == "handed-back", seen
    assert by_title[LOCK_TITLE]["outcome"] == "fixed"
    check = by_title[CHECK_TITLE]
    assert check["outcome"] == "left-for-owner" and "still open when the loop reached its round cap" in check["reason"], check
    assert "membersReopened" not in s.state()["rounds"].get("2", {})


# --- the same three arms in the carried shape ----------------------------------------------------------------------
# Session 1 left CHECK open; session 2 carries it. Session 2's scoped finder raises LOCK, the synthesis merges the two,
# the fixer edits only the lock line, and the auditor discharges only the target titled LOCK.

C_LOCK, C_CHECK = "share the save lock across both writers", "validate the snapshot on initial writes"
C_LOCK_LINE, C_CHECK_LINE = 28, 27


def _carried_arm(tmp_path, monkeypatch, merge, member_answer):
    carried = CF._finding(C_CHECK_LINE, title=C_CHECK, tradeoff=False)
    fresh = {"title": C_LOCK, "severity": "Critical", "file": CF.SHARED, "line": C_LOCK_LINE, "tradeoff": False,
             "consequence": "two writers race on save, and the initial write skips the snapshot check"}
    s = CF._session(tmp_path, monkeypatch, [carried], change=CF.TOUCHES_NEAR_27)
    base = CF._respond(audit="not-discharged", scoped=[fresh], verdict="CONFIRMED")
    batches, merged = [], []

    def respond(phase, payload, rnd):
        if phase == RD.P_SYNTHESIS and not merged:
            merged.append(True)
            by_title = {f["title"]: f["id"] for f in payload["findings"]}
            assert {C_CHECK, C_LOCK} <= set(by_title), by_title  # the carried finding reaches the synthesis with the fresh one
            if not merge:
                return {"grouping": None}
            # CHECK is listed before LOCK, and LOCK is the more severe: LOCK is the representative
            art = {"grouping": [{"group_id": "g1", "member_ids": [by_title[C_CHECK], by_title[C_LOCK]],
                                 "rationale": "same root cause"}]}
            vendor = RD._nonpanel_selection(s.state(), s.dir, RD.P_SYNTHESIS)[0]
            if vendor:
                art["synthesisVendor"] = vendor
            return art
        if phase == RD.P_APPLY_FIXES:
            batches.append((rnd, [f["title"] for f in payload["batch"]]))
            # the fixer edits only the lock line, in a real commit: it never adds the snapshot check
            s.repo.write(CF.SHARED, CF._shared(**{str(C_LOCK_LINE): "edited_c = %d  # lock shared\n" % (rnd + 1)}))
            s.repo.commit("share the save lock (round %d)" % rnd)
            proc = review_diff_bytes.run_git_diff_three_dot(s.repo.root, s.base, s.repo.git("rev-parse", "HEAD"), timeout=60)
            return {"fixes": [{"file": CF.SHARED}], "headDiff": proc.stdout.decode("utf-8"), "changedSubjects": ["Code"]}
        out = base(phase, payload, rnd)
        if phase == RD.P_AUDITS:
            by_id = {t["id"]: t for t in payload["targets"]}
            for result in out["results"]:
                target = by_id[result["id"]]
                result["ruling"] = "discharged" if target["title"] == C_LOCK else "not-discharged"
                if member_answer is not None and target.get("mergedMembers"):
                    result["members"] = [_answer(m["id"], member_answer) for m in target["mergedMembers"]]
        return out

    terminal, seen = CF._run(s, respond, limit=80)
    state = s.state()
    account = RS.account_from_session(s.dir, TRRS.extras())["findings"]
    return s, state, batches, terminal, seen, {f["title"]: f for f in account}, carried[SC.FINDING_KEY_FIELD]


def _reopened_rounds(state):
    return [rec["membersReopened"] for rec in state["rounds"].values() if rec.get("membersReopened")]


def test_carried_arm_a_the_carried_finding_merged_into_the_lock_and_not_answered_is_reopened_and_never_reads_fixed(tmp_path, monkeypatch):
    s, state, batches, terminal, seen, by_title, ckey = _carried_arm(tmp_path, monkeypatch, True, None)
    assert batches[0][1] == [C_LOCK], "the carried CHECK was merged into LOCK, so only LOCK is fixed first: %s" % (batches,)
    reopened = _reopened_rounds(state)
    assert [row["findingKey"] for rows in reopened for row in rows] == [ckey], reopened
    assert reopened[0][0]["answer"] is None
    assert any(C_CHECK in titles for _round, titles in batches[1:]), "CHECK is in a later apply-fixes batch: %s" % (batches,)
    assert terminal["payload"]["verdict"] != "converged", seen
    assert by_title[C_LOCK]["outcome"] == "fixed"
    assert by_title[C_CHECK]["outcome"] == "left-for-owner", by_title[C_CHECK]
    assert "(merged into" not in by_title[C_CHECK]["reason"]


def test_carried_arm_a2_the_carried_finding_the_auditor_answers_fixed_on_the_lock_target_reads_fixed_with_the_merge_in_its_reason(tmp_path, monkeypatch):
    s, state, batches, terminal, seen, by_title, ckey = _carried_arm(tmp_path, monkeypatch, True, True)
    assert batches[0][1] == [C_LOCK], batches
    assert not _reopened_rounds(state), "the audit answered CHECK fixed: nothing is reopened"
    assert by_title[C_LOCK]["outcome"] == "fixed"
    check = by_title[C_CHECK]
    assert check["outcome"] == "fixed", check
    assert check["reason"].endswith(" (merged into %s)" % by_title[C_LOCK]["id"]), check
    assert RS.merged_into(check["reason"]) == by_title[C_LOCK]["id"]


def test_carried_arm_b_with_no_merge_the_carried_finding_is_left_for_the_owner_at_the_cap_as_before(tmp_path, monkeypatch):
    s, state, batches, terminal, seen, by_title, ckey = _carried_arm(tmp_path, monkeypatch, False, None)
    assert sorted(batches[0][1]) == sorted([C_LOCK, C_CHECK]), batches
    assert not _reopened_rounds(state)
    assert terminal["payload"]["verdict"] == "handed-back", seen
    assert by_title[C_LOCK]["outcome"] == "fixed"
    check = by_title[C_CHECK]
    assert check["outcome"] == "left-for-owner" and "still open when the loop reached its round cap" in check["reason"], check
