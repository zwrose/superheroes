"""#2495: only a wrong fix counts toward the two-strike audit stop.

The fix audit ends a review when one finding is not discharged in two audit rounds running (`audit-stall`).
Every not-discharged entry the fold emits now carries a `reasonKind`, and the breaker counts an outcome only when
its kind is `wrong` or it has no recognised kind (fail closed). Three things no longer count:

  scope-only      a fix that is right but changes behaviour its finding does not name reads cleared, with a
                  `scopeNote` for the vet, unless the finding's own decision forbids the change (then `wrong`);
  unanswered      an auditor that never answered (silence, a refusal, a checks fault) is not a wrong fix;
  reopened-merged a merged finding the audit reopens does not count until its own fix has been audited once.

Pins, each at the place the rule is enforced:

C   the classification census: every arm of `_AuditFold` that sets `not-discharged` carries its kind;
S   a scope-only hold clears (with either clearing ruling, and with an accepted `review-guarded` or
    `worthless-test-removed` answer) and a forbidden change is refused;
B   the breaker: wrong twice halts, unanswered twice does not, reopened then wrong does not, and a missing or
    unknown kind counts;
L   whole-loop runs on a real throwaway repository: a scope-only hold, a silent auditor and a reopened member;
R   the review record names the scope note.

Bite-proof record: plugins/superheroes/lib/tests/bite_proofs/i2495_strike_kinds.md
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
import circuit_breaker as CB  # noqa: E402
import decision_kinds  # noqa: E402
import review_record_session as RS  # noqa: E402
import round_driver as RD  # noqa: E402
import session_contract as SC  # noqa: E402
import test_apply_audit_results_characterization_2418 as CHAR  # noqa: E402
import test_audit_review_guarded_2341 as RG  # noqa: E402
import test_audit_test_removal_2434 as TR  # noqa: E402
import test_c1l11b_carried_findings as CF  # noqa: E402
import test_c1l11b_returning_session as TS  # noqa: E402
import test_merged_member_record_2489 as MR  # noqa: E402
import test_review_record_session as TRRS  # noqa: E402
from test_circuit_breaker import a_round, nd  # noqa: E402
from test_c1l11b_returning_session import _isolated_git  # noqa: E402,F401  (autouse: no global git config)
from test_merged_member_loop_2489 import (  # noqa: E402
    CHECK_TITLE, LOCK_TITLE, M_A, M_B, REP, Script, _arm, _drive, _ledger, _panel_finding, _targets, _world)
from test_merged_member_loop_2489 import _fold as _fold_round  # noqa: E402

UNNAMED = CHAR.UNNAMED
FORBIDS = {"ruling": "guidance", "allowsChange": False}
WRONG, UNANSWERED = audits.REASON_KIND_WRONG, audits.REASON_KIND_UNANSWERED
SCOPE_ONLY, REOPENED = audits.REASON_KIND_SCOPE_ONLY, audits.REASON_KIND_REOPENED_MERGED
CLEARS = ("discharged", "discharged-but-new-issue")


# --- the contract constants -----------------------------------------------------------------------------------------

def test_the_shared_contract_constants_are_exactly_the_stated_values():
    assert audits.AUDIT_REASON_KIND_FIELD == "reasonKind"
    assert audits.AUDIT_REASON_KINDS == ("wrong", "unanswered", "scope-only", "reopened-merged")
    assert audits.NON_STRIKE_REASON_KINDS == frozenset({"unanswered", "reopened-merged"})
    assert "audit-scope-held" in decision_kinds.DECISION_KINDS
    assert "audit-unnamed-change" in decision_kinds.DECISION_KINDS


# --- C: the classification census -----------------------------------------------------------------------------------

SCENARIOS = {s["name"]: s for s in CHAR.SCENARIOS}

CENSUS = [
    # (the arm of `_AuditFold`, the characterization scenario that reaches it, the kind it carries)
    ("_fold_silence: silence", "S02_silence_unaudited", UNANSWERED),
    ("_fold_silence: duplicate target id", "T1_duplicate_target_without_a_result", UNANSWERED),
    ("_fold_silence: ambiguous id", "S03_silence_ambiguous_result_id", UNANSWERED),
    ("_fold_duplicate_target", "S04_duplicate_target_with_a_result", UNANSWERED),
    ("_reject_unauthenticated: no auditor recorded", "S06_provenance_no_auditor_recorded", UNANSWERED),
    ("_reject_unauthenticated: manifest entry missing", "S07_provenance_manifest_entry_missing", UNANSWERED),
    ("_reject_unauthenticated: vendor mismatch", "S08_provenance_manifest_vendor_mismatch", UNANSWERED),
    ("_fold_checks_fault", "S11_three_checks_fault", UNANSWERED),
    ("_fold_malformed_unnamed: not a string", "S18_unnamed_change_not_a_string", UNANSWERED),
    ("_fold_malformed_unnamed: seq not an int", "S19_unnamed_change_seq_not_an_int", UNANSWERED),
    ("_fold_malformed_unnamed: claim fault", "S20_claim_fault", UNANSWERED),
    ("_fold_discharged: reasonless", "S24_discharged_with_no_reason", UNANSWERED),
    ("_fold_discharged_new_issue: no usable newIssues", "S27_new_issue_no_usable_candidates", UNANSWERED),
    ("_fold_unrecognized", "S29_unknown_ruling", UNANSWERED),
    ("_fold_not_discharged", "S28_not_discharged_by_selected_auditor", WRONG),
    ("_fold_blocking_test", "S10_blocking_break_it_match_keeps_new_issues", WRONG),
    ("_fold_weakened_test", "S13_weakened_explained_test_precedes_places", WRONG),
    ("_fold_incomplete_places", "S14_incomplete_places_with_unnamed_change", WRONG),
    ("_fold_failed_check", "S15_failed_check", WRONG),
    ("_review_guard refusal", "S16_review_guarded_refused", WRONG),
    ("refuse_unnamed_change: discharged", "S21b_discharged_unnamed_change_forbidden_refused", WRONG),
    ("refuse_unnamed_change: new issue", "S25b_new_issue_unnamed_change_forbidden_refused", WRONG),
]


@pytest.mark.parametrize("arm,name,kind", CENSUS, ids=[row[1] for row in CENSUS])
def test_census_each_not_discharged_arm_carries_its_kind(arm, name, kind):
    # axis: each arm of the fold carries the kind the census names: the unanswered arms `unanswered`, the wrong arms `wrong` — see bite-proof record i2495_strike_kinds
    out = CHAR._run(SCENARIOS[name])
    entries = [e for e in out["audits"] if e["ruling"] == "not-discharged"]
    assert entries, arm
    assert [e["reasonKind"] for e in entries] == [kind] * len(entries), arm
    assert all(e["reasonKind"] in audits.AUDIT_REASON_KINDS for e in entries)


def test_census_the_test_removal_guard_refusal_is_wrong():
    # a delta that touches a non-test file is refused by the worthless-test-removed guard (condition C1)
    outcome = TR._fold([TR._removed()], TR._target(files=(TR.TEST_FILE, TR.LIB_PY)))
    entry = TR._only(outcome)
    assert outcome["testRemovalRefused"] == ["t0"] and entry["ruling"] == "not-discharged"
    assert entry["reasonKind"] == WRONG


@pytest.mark.parametrize("name", sorted(SCENARIOS))
def test_census_every_not_discharged_entry_of_every_scenario_carries_a_recognised_kind(name):
    out = CHAR._run(SCENARIOS[name])
    for entry in out["audits"]:
        if entry["ruling"] == "not-discharged":
            assert entry.get("reasonKind") in audits.AUDIT_REASON_KINDS, entry
        else:
            # a clearing entry carries no kind, unless it is a scope-only hold (listed in `scopeHeld`)
            assert ("reasonKind" in entry) == (entry["id"] in out["scopeHeld"]), entry
            assert entry.get("reasonKind", SCOPE_ONLY) == SCOPE_ONLY, entry
    assert set(out["scopeHeld"]) <= set(out["discharged"])
    assert not set(out["scopeHeld"]) & set(out["notDischarged"])


# --- S: the scope-only hold -----------------------------------------------------------------------------------------

def _scope_result(ruling, **extra):
    body = dict(CHAR._result("t1", ruling=ruling, unnamedChange="  %s  " % UNNAMED, evidence="ran the suite"), **extra)
    if ruling == "discharged-but-new-issue":
        body["newIssues"] = [CHAR._issue("fresh")]
    return body


@pytest.mark.parametrize("ruling", CLEARS)
def test_a_scope_only_hold_reads_cleared_with_a_scope_note(ruling):
    # axis: a clearing result with an unallowed, unattributed unnamed change reads cleared, noted for the vet — see bite-proof record i2495_strike_kinds
    out = audits.apply_audit_results([CHAR._target("t1")], [_scope_result(ruling)])
    (entry,) = out["audits"]
    assert out["discharged"] == ["t1"] and out["scopeHeld"] == ["t1"]
    assert out["notDischarged"] == [] and out["unnamedChange"] == [] and out["attributedChange"] == []
    assert entry["ruling"] == ruling and entry["reason"] == "the fix resolves it"
    assert entry["scopeNote"] == UNNAMED and entry["reportedUnnamedChange"] == UNNAMED
    assert entry["reasonKind"] == SCOPE_ONLY and entry["evidence"] == "ran the suite"
    assert "allowedChange" not in entry and "attributedChange" not in entry
    if ruling == "discharged-but-new-issue":
        assert [(n["title"], n["originAuditId"]) for n in out["newIssues"]] == [("fresh", "t1")]
    else:
        assert out["newIssues"] == []


def test_an_allowed_change_is_never_a_scope_only_hold():
    out = audits.apply_audit_results([CHAR._target("t1")], [_scope_result("discharged")], change_allowed_ids=["t1"])
    (entry,) = out["audits"]
    assert out["discharged"] == ["t1"] and out["scopeHeld"] == []
    assert entry["allowedChange"] == UNNAMED and "scopeNote" not in entry and "reasonKind" not in entry


def test_an_attributed_change_is_never_a_scope_only_hold():
    result = _scope_result("discharged", unnamedChangeFixes=["m"])
    out = audits.apply_audit_results([CHAR._claim_target("t1")], [result])
    (entry,) = out["audits"]
    assert out["discharged"] == ["t1"] and out["scopeHeld"] == [] and out["attributedChange"] == ["t1"]
    assert "scopeNote" not in entry and "reasonKind" not in entry


def test_a_scope_note_never_rescues_a_result_that_an_earlier_arm_refuses():
    # the scope-only arm is reached only after every other arm has passed (a failed check refuses first)
    result = _scope_result("discharged", checks=CHAR._checks(right="no"))
    out = audits.apply_audit_results([CHAR._target("t1")], [result])
    (entry,) = out["audits"]
    assert out["scopeHeld"] == [] and out["notDischarged"] == ["t1"] and out["discharged"] == []
    assert entry["reasonKind"] == WRONG and "scopeNote" not in entry


# --- S: scope-only with an accepted alternate answer (BRIEF-3) ------------------------------------------------------

@pytest.mark.parametrize("ruling", CLEARS)
def test_a_review_guarded_clear_with_an_unnamed_change_is_a_scope_only_hold_and_keeps_review_guarded(ruling):
    extra = {"unnamedChange": UNNAMED}
    if ruling == "discharged-but-new-issue":
        extra.update(ruling=ruling, newIssues=[CHAR._issue("fresh")])
    outcome = RG._fold([RG._guarded(**extra)], RG._target(RG.RUBRIC_MD))
    entry = RG._only(outcome)
    assert outcome["discharged"] == ["t0"] and outcome["scopeHeld"] == ["t0"] and outcome["notDischarged"] == []
    assert outcome["reviewGuarded"] == ["t0"] and outcome["unnamedChange"] == []
    assert entry["ruling"] == ruling and entry["reviewGuarded"]["answer"] == audits.REVIEW_GUARDED
    assert entry["scopeNote"] == UNNAMED and entry["reasonKind"] == SCOPE_ONLY


@pytest.mark.parametrize("ruling", CLEARS)
def test_a_worthless_test_removal_clear_with_an_unnamed_change_is_a_scope_only_hold_and_keeps_test_removal(ruling):
    extra = {"unnamedChange": UNNAMED}
    if ruling == "discharged-but-new-issue":
        extra.update(ruling=ruling, newIssues=[CHAR._issue("fresh")])
    outcome = TR._fold([TR._removed(**extra)], TR._target())
    entry = TR._only(outcome)
    assert outcome["discharged"] == ["t0"] and outcome["scopeHeld"] == ["t0"] and outcome["notDischarged"] == []
    assert outcome["testRemovalCleared"] == ["t0"] and outcome["unnamedChange"] == []
    assert entry["ruling"] == ruling and entry["testRemoval"]["answer"] == audits.WORTHLESS_TEST_REMOVED
    assert entry["testRemoval"]["evidence"]["finding"] == "t0"
    assert entry["scopeNote"] == UNNAMED and entry["reasonKind"] == SCOPE_ONLY


# --- S: the forbidden case ------------------------------------------------------------------------------------------

@pytest.mark.parametrize("ruling", CLEARS)
def test_a_change_the_findings_own_decision_forbids_is_refused_as_a_wrong_fix(ruling):
    # axis: a change the finding's own carried decision forbids stays not-discharged and `wrong` — see bite-proof record i2495_strike_kinds
    target = CHAR._target("t1", ownerRuling=dict(FORBIDS))
    out = audits.apply_audit_results([target], [_scope_result(ruling)])
    (entry,) = out["audits"]
    assert out["discharged"] == [] and out["notDischarged"] == ["t1"] and out["scopeHeld"] == []
    assert out["unnamedChange"] == ["t1"]
    assert entry["ruling"] == "not-discharged" and entry["reasonKind"] == WRONG
    assert entry["reason"] == audits.UNNAMED_CHANGE_REASON_PREFIX + UNNAMED
    assert "scopeNote" not in entry and entry["reportedUnnamedChange"] == UNNAMED
    assert [n["title"] for n in out["newIssues"]] == (["fresh"] if ruling != "discharged" else [])


@pytest.mark.parametrize("owner_ruling", [
    None, "no", ["allowsChange", False], 0, {}, {"ruling": "guidance"}, {"allowsChange": None},
    {"allowsChange": True}, {"allowsChange": "false"}, {"allowsChange": 0},
], ids=["none", "string", "list", "zero", "empty", "no-key", "null", "true", "string-false", "zero-flag"])
def test_a_target_whose_decision_does_not_forbid_the_change_is_a_scope_only_hold(owner_ruling):
    # only a dict with `allowsChange` exactly False forbids; absent, malformed and any other value forbids nothing
    out = audits.apply_audit_results([CHAR._target("t1", ownerRuling=owner_ruling)], [_scope_result("discharged")])
    assert out["discharged"] == ["t1"] and out["scopeHeld"] == ["t1"] and out["unnamedChange"] == []


# --- B: the breaker -------------------------------------------------------------------------------------------------

IDENT = "src/a.py::leak"


def _kinded(*kinds):
    """One audit round per kind, each holding the one finding `t1` not discharged with that kind."""
    return [a_round(n + 1, [nd(IDENT, id="t1", reasonKind=kind)]) for n, kind in enumerate(kinds)]


def test_two_wrong_rounds_still_halt_as_an_audit_stall():
    # axis: a `wrong` outcome still counts toward the stall — see bite-proof record i2495_strike_kinds
    res = CB.check_audit_breaker(_kinded(WRONG, WRONG))
    assert res["halt"] is True and res["reason"] == "audit-stall"
    assert IDENT in res["stalledIdentities"]


def test_two_unanswered_rounds_do_not_halt():
    # axis: an unanswered or reopened-merged outcome never counts toward the stall — see bite-proof record i2495_strike_kinds
    res = CB.check_audit_breaker(_kinded(UNANSWERED, UNANSWERED))
    assert res["halt"] is False and res["reason"] is None and res["stalledIdentities"] == []
    assert CB.check_audit_breaker(_kinded(UNANSWERED, UNANSWERED, UNANSWERED))["halt"] is False
    assert CB.check_audit_breaker(_kinded(UNANSWERED, WRONG))["halt"] is False
    assert CB.check_audit_breaker(_kinded(WRONG, UNANSWERED))["halt"] is False


def test_a_reopened_member_then_a_wrong_answer_does_not_halt_but_a_second_wrong_answer_does():
    assert CB.check_audit_breaker(_kinded(REOPENED, WRONG))["halt"] is False
    assert CB.check_audit_breaker(_kinded(REOPENED, REOPENED))["halt"] is False
    res = CB.check_audit_breaker(_kinded(REOPENED, WRONG, WRONG))
    assert res["halt"] is True and res["reason"] == "audit-stall"


def test_a_round_with_no_reason_kind_counts_as_a_strike():
    # axis: a legacy outcome with no kind counts, so an old record cannot uncount into a silent pass — see bite-proof record i2495_strike_kinds
    rounds = [a_round(1, [nd(IDENT, id="t1")]), a_round(2, [nd(IDENT, id="t1")])]
    assert CB.check_audit_breaker(rounds)["halt"] is True


@pytest.mark.parametrize("kind", ["scope", None, "", 5, ["unanswered"], "UNANSWERED", "scope-only"],
                         ids=["scope", "none", "empty", "number", "unhashable-list", "mis-cased", "scope-only"])
def test_a_round_with_an_unknown_reason_kind_counts_as_a_strike(kind):
    # `scope-only` is a recognised kind but a clearing one; on a not-discharged outcome it is no non-strike kind
    assert CB.check_audit_breaker(_kinded(kind, kind))["halt"] is True


def test_a_cleared_outcome_never_counts_whatever_its_kind():
    rounds = [a_round(1, [nd(IDENT, id="t1", reasonKind=WRONG)]),
              a_round(2, [{"identity": IDENT, "ruling": "discharged", "id": "t1", "reasonKind": SCOPE_ONLY}])]
    assert CB.check_audit_breaker(rounds)["halt"] is False


def test_a_malformed_outcome_or_round_still_counts():
    marker_round = [{"round": 1, "outcomes": ["not-a-dict"]}, {"round": 2, "outcomes": ["not-a-dict"]}]
    assert CB.check_audit_breaker(marker_round)["halt"] is True
    no_identity = [a_round(n, [{"ruling": "not-discharged", "id": "t1", "reasonKind": UNANSWERED}]) for n in (1, 2)]
    assert CB.check_audit_breaker(no_identity)["halt"] is True  # no identity: the malformed marker, counted
    assert CB.check_audit_breaker([{"round": 1}, {"round": 2}])["halt"] is True


# --- L: whole-loop runs ---------------------------------------------------------------------------------------------

SCOPE_TEXT = {LOCK_TITLE: "it also drops the lock log line", CHECK_TITLE: "it also tightens the write timeout"}
BAD_KINDS = {"self-recovery", "fix-keeps-failing", "stall-menu", "stall-choice"}


class ScopeScript(Script):
    """The auditor rules each fix right and names a change its finding does not name. In the first audit it
    discharges only LOCK (CHECK is not discharged, so CHECK is fixed again and audited in a second audit round);
    in the second it discharges CHECK: two audit rounds, each holding a different finding for scope once."""

    def __init__(self, session):
        super().__init__(session, merge=False, member_answer=None)
        self.audits_seen = 0

    def __call__(self, phase, payload, rnd):
        art = super().__call__(phase, payload, rnd)
        if phase == RD.P_AUDITS:
            self.audits_seen += 1
            by_id = {t["id"]: t for t in payload["targets"]}
            for result in art["results"]:
                title = by_id[result["id"]]["title"]
                if title == LOCK_TITLE or self.audits_seen > 1:
                    result.update(ruling="discharged", unnamedChange=SCOPE_TEXT[title])
        return art


def _decisions(state, kind):
    return [d for d in state["decisions"] if d["kind"] == kind]


def test_loop_a_scope_held_fixes_clear_carry_the_note_and_never_stall(tmp_path, monkeypatch):
    # axis: a fix the audit rules right with an unnamed change clears with a scope note and is no strike, end to end — see bite-proof record i2495_strike_kinds
    s = TS.Session(tmp_path, monkeypatch, first=CF.FIRST, earlier=None)
    s.cfg["headSha"] = s.head
    script = ScopeScript(s)
    terminal, seen = _drive(s, script)
    state = s.state()
    account = {f["title"]: f for f in RS.account_from_session(s.dir, TRRS.extras())["findings"]}
    assert script.audits_seen == 2, "LOCK was held in the first audit round, CHECK in the second: %s" % (seen,)
    assert not BAD_KINDS & {d["kind"] for d in state["decisions"]}, state["decisions"]
    assert terminal["payload"]["verdict"] == "converged", seen
    assert len(_decisions(state, "audit-scope-held")) == 2 and not _decisions(state, "audit-unnamed-change")
    held = [(rnd, rec["auditScopeHeld"]) for rnd, rec in state["rounds"].items() if rec.get("auditScopeHeld")]
    assert len(held) == 2 and all(len(ids) == 1 for _rnd, ids in held), held
    for title, text in SCOPE_TEXT.items():
        found = account[title]
        assert found["outcome"] == "fixed", found
        row = _ledger(state, found["findingKey"])
        assert row["disposition"] == "fixed" and row["dispositionReceipt"]["scopeNote"] == text
        assert "listed for the vet: %s" % text in found["reason"], found["reason"]
    # each held finding's audit entry is cleared, carries its kind, and the breaker saw it as no strike
    for rec in state["auditRounds"]:
        assert all(o["ruling"] in CLEARS or o["reasonKind"] == WRONG for o in rec["outcomes"]), rec
    assert CB.check_audit_breaker(state["auditRounds"])["halt"] is False


class SilentScript(Script):
    """The auditor discharges LOCK and never answers CHECK: its result is left out of every audit. The panel
    raises both as Important findings with a real consequence, carrying no owner ruling."""

    def __init__(self, session):
        super().__init__(session, merge=False, member_answer=None)
        real = [dict(_panel_finding(LOCK_TITLE, 27), consequenceKind="real"),
                dict(_panel_finding(CHECK_TITLE, 3), consequenceKind="real")]
        self.base = CF._respond(round1_findings=real)

    def __call__(self, phase, payload, rnd):
        art = super().__call__(phase, payload, rnd)
        if phase == RD.P_AUDITS:
            by_id = {t["id"]: t for t in payload["targets"]}
            art["results"] = [r for r in art["results"] if by_id[r["id"]]["title"] != CHECK_TITLE]
        return art


def test_loop_b_an_auditor_that_never_answers_is_no_strike_and_the_finding_is_never_fixed(tmp_path, monkeypatch):
    # axis: the breaker sees the fold's reason kind on the audit-round outcome, so a silent auditor never stalls the loop — see bite-proof record i2495_strike_kinds
    s = TS.Session(tmp_path, monkeypatch, first=CF.FIRST, earlier=None)
    s.cfg["headSha"] = s.head
    script = SilentScript(s)
    terminal, seen = _drive(s, script)
    state = s.state()
    check_rounds = [rec for rec in state["auditRounds"]
                    if any(o["title"] == CHECK_TITLE for o in rec["outcomes"])]
    assert len(check_rounds) >= 2, "CHECK was audited, and unanswered, in at least two audit rounds: %s" % (seen,)
    for rec in check_rounds:
        (outcome,) = [o for o in rec["outcomes"] if o["title"] == CHECK_TITLE]
        assert outcome["ruling"] == "not-discharged" and outcome["reasonKind"] == UNANSWERED
    assert CB.check_audit_breaker(state["auditRounds"])["halt"] is False
    assert not BAD_KINDS & {d["kind"] for d in state["decisions"]}, state["decisions"]
    # never recorded fixed: by `finding_outcomes.settle` it is left for the owner, open at the loop's end
    account = {f["title"]: f for f in RS.account_from_session(s.dir, TRRS.extras())["findings"]}
    assert account[LOCK_TITLE]["outcome"] == "fixed"
    check = account[CHECK_TITLE]
    assert check["outcome"] == "left-for-owner", check
    row = _ledger(state, check["findingKey"])
    assert row["disposition"] == "left-for-owner" and row[SC.OPEN_AT_LOOP_END_FIELD] is True, row
    assert row.get("severity") == "Important"
    assert "fixed" not in {r.get("disposition") for r in state[SC.DISPOSITION_LEDGER_KEY]
                           if SC.finding_identity_key(r) == check["findingKey"]}


def test_loop_c_a_merged_member_reopened_in_one_round_and_answered_wrong_in_the_next_does_not_stall(tmp_path, monkeypatch):
    # axis: a reopened member carries `reopened-merged`, so it is no strike before its own fix is audited — see bite-proof record i2495_strike_kinds
    s, script, terminal, seen, by_title = _arm(tmp_path, monkeypatch, merge=True, member_answer=None)
    state = s.state()
    rounds = state["auditRounds"]
    assert len(rounds) >= 2, seen

    def by(rec):
        return {o["title"]: o for o in rec["outcomes"]}

    # the behaviour first: the reopened-then-wrong pair is no stall, so the session did not stall at N+1
    assert CB.check_audit_breaker(rounds[:2])["halt"] is False
    assert "selfRecovery" not in state["rounds"][str(rounds[1]["round"])], "the session did not stall at N+1"
    assert by(rounds[0])[LOCK_TITLE]["ruling"] == "discharged"
    reopened = by(rounds[0])[CHECK_TITLE]
    assert reopened["ruling"] == "not-discharged" and reopened["reasonKind"] == REOPENED
    own = by(rounds[1])[CHECK_TITLE]
    assert own["ruling"] == "not-discharged" and own["reasonKind"] == WRONG, "its own audit is classified fresh"
    assert by_title[CHECK_TITLE]["outcome"] == "left-for-owner"


# --- L: the driver edges ----------------------------------------------------------------------------------------------

def test_the_reopened_member_entry_is_classified_in_the_fold(tmp_path):
    # the fold's own entry for a reopened member carries the kind, with its reason text unchanged
    state = _fold_round(_world(tmp_path), members=None)
    entries = {e["id"]: e for e in state["_auditOutcome"]["audits"]}
    for key in (M_A, M_B):
        assert entries[key]["reasonKind"] == REOPENED and entries[key]["ruling"] == "not-discharged"
        assert entries[key]["reason"].startswith("merged into %s, whose fix the audit cleared" % REP)
    assert "reasonKind" not in entries[REP]
    round_outcomes = {o["id"]: o for o in state["auditRounds"][-1]["outcomes"]}
    assert round_outcomes[M_A]["reasonKind"] == REOPENED and round_outcomes[M_B]["reasonKind"] == REOPENED
    assert round_outcomes[REP]["reasonKind"] is None  # a plain clear carries no kind


@pytest.mark.parametrize("kind", ["rider", "carried"])
def test_a_rider_or_carried_target_is_left_out_of_the_audit_round_as_before(tmp_path, kind):
    world = _world(tmp_path, members=(M_A,))
    state = world.state
    targets = _targets(world)
    ruling = "discharged"
    if kind == "rider":
        targets[0]["spawnedFrom"] = "a-parent-key"
    else:
        ruling = "not-discharged"  # a carried finding the audit did not discharge is sent back, out of the round
        state["_carriedAudited"] = {REP: copy.deepcopy(state["findings"][0])}
        state["rounds"]["2"]["carried"] = {"keys": [REP], "auditBase": None, "discharged": [], "sentBack": []}
    _fold_round(world, members=None, ruling=ruling, targets=targets)
    assert state["auditRounds"][-1]["outcomes"] == []


# --- R: the review record -------------------------------------------------------------------------------------------

SCOPE_NOTE = "it also drops the lock log line"
SCOPE_REASON = (MR.REP_REASON + "; the audit ruled the fix right and noted a change its finding does not name, "
                "listed for the vet: " + SCOPE_NOTE)


def test_record_a_fixed_receipt_with_a_scope_note_lists_it_for_the_vet():
    # axis: the record lists the scope note the audit set on the fixed receipt — see bite-proof record i2495_strike_kinds
    rows = MR.ledger({"dispositionReceipt": {"scopeNote": "  %s " % SCOPE_NOTE}})
    assert MR.decide_rep(rows) == ("fixed", SCOPE_REASON)


@pytest.mark.parametrize("note", ["", "   ", None, 5, ["x"], {"a": 1}], ids=["empty", "blank", "none", "int", "list", "dict"])
def test_record_a_blank_or_non_string_scope_note_adds_nothing(note):
    rows = MR.ledger({"dispositionReceipt": {"scopeNote": note}})
    assert MR.decide_rep(rows) == ("fixed", MR.REP_REASON)


def test_record_a_test_removal_with_a_scope_note_names_both():
    evidence = {"taxonomy": "wording pin", "finding": "f-1", "removed": [{"file": "t.py", "ranges": [[10, 14]]}]}
    rows = MR.ledger({"dispositionReceipt": {"testRemoval": {"evidence": evidence}, "scopeNote": SCOPE_NOTE}})
    plain = MR.decide_rep(MR.ledger({"dispositionReceipt": {"testRemoval": {"evidence": evidence}}}))
    assert plain[1].endswith("removed t.py lines 10-14")
    outcome, reason = MR.decide_rep(rows)
    assert outcome == "fixed"
    assert reason == plain[1] + "; the audit noted a change its finding does not name, listed for the vet: " + SCOPE_NOTE


def test_record_a_merged_member_ruled_fixed_inherits_the_representatives_scope_note(tmp_path):
    rows = MR.ledger({"dispositionReceipt": {"scopeNote": SCOPE_NOTE}, MR.RESULTS: [MR.said(True)]})
    via_decide, via_account = MR.both(tmp_path, rows)
    assert via_decide == ("fixed", SCOPE_REASON + MR.NOTE)
    assert via_account == ("fixed", SCOPE_REASON + MR.NOTE + " (merged into rep-1)")
    # a member the audit did not rule fixed still has no outcome: the note never lends it one
    unruled = MR.ledger({"dispositionReceipt": {"scopeNote": SCOPE_NOTE}})
    assert MR.decide(unruled) == (None, RS.MERGED_MEMBER_UNAUDITED)
