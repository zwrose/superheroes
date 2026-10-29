"""#2115: a finding an audit raised rides the next audit as its own target.

An audit that rules `discharged-but-new-issue` raises a new finding (a child of the audited target, its
parent). When a later fix round's batch carries the parent again, the child is audited in the delta round
after that fix, under its own key, as a rider on the parent's audit. A discharge records it `fixed` at the
audits fold; anything else leaves it with no disposition, so the end-of-loop settle leaves it for the owner
exactly as before. A rider never joins the fix list, the audit-stall breaker's outcomes or the PR-body
audited set.

Drives the real round driver: `run_loop` with scripted seams for the loop-shaped cases (the #2105 replay
among them), and `_fold_scoped`, `_audit_targets`, `_fold_audits` and `_settle_open_findings` on a built
state for the rest.

Bite-proof record: plugins/superheroes/lib/tests/bite_proofs/audit_spawned_riders_2115.md
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

import review_record as rr  # noqa: E402
import review_record_session as rs  # noqa: E402
import session_contract as SC  # noqa: E402
import test_review_record_session as TRS  # noqa: E402
import test_round_driver as TRD  # noqa: E402
from test_fix_scope_c7 import (  # noqa: E402,F401
    _decide, _decisions, _finding, _key, _ledger, _staged_state, captured_state)

RD = TRD.RD  # run_loop runs on test_round_driver's own load of the module

P_KEY = _key("Null deref", 1)
X_KEY = _key("Stale comment", 2)
LEFT_OPEN = "left unfixed when the review loop converged"


def _parent(**extra):
    return _finding("Null deref", line=1, body="the value can be missing", suggestion="check it first",
                    **extra)


def _child(**over):
    child = _finding("Stale comment", line=2, severity="Minor", body="the comment is out of date",
                     suggestion="reword it")
    child.update(over)
    return child


# --- the loop: the #2105 replay -----------------------------------------------------------------

def _spawn_loop(x_ruling="discharged", reraise_parent=True):
    """Round 1 raises P (Important) and fixes it. Round 2's audit of P rules `discharged-but-new-issue`
    and emits X (Minor); the round's scoped finder raises P again, so round 2's fix batch carries P.
    Round 3's audit rules P `discharged` and X (the rider) `x_ruling`."""
    offers, seen = [], []

    def reviewer(dim, tier, rnd, ctx):
        if rnd == 1 and dim == "code-reviewer":
            return {"findings": [_parent()]}
        if rnd == 2 and dim == "scoped-finder" and reraise_parent:
            return {"findings": [_parent()]}
        return []

    def fix_step(batch, rnd, payload):
        offers.append((rnd, [RD._fix_batch_row_key(r) for r in batch]))
        # a new file in the head diff gives the delta round's scoped finder a surface to scan
        return {"fixes": [], "headDiff": TRD._headf_ns(len(offers)), "changedSubjects": ["Code"]}

    def auditor(targets, rnd):
        seen.append((rnd, copy.deepcopy(targets)))
        out = []
        for t in targets or []:
            result = {"id": t["id"], "ruling": "discharged", "reason": "fix resolves it",
                      "evidence": "tests pass", "auditorVendor": t.get("auditorVendor")}
            if rnd == 2:
                result.update(ruling="discharged-but-new-issue", newIssues=[_child()])
            elif t["id"] == X_KEY:
                result.update(ruling=x_ruling, reason="the comment now says what the code does")
            out.append(result)
        return out

    seams = TRD._seams(reviewer=reviewer, fix_step=fix_step, auditor=auditor)
    # the scoped finder is seated on a non-panel cell, so the config names the cells proven live
    config = TRD._cfg_cert(maxRounds=20, seatMap=TRD._nonpanel_cell_proof(["claude", "codex"]))
    _result, state = TRD._run_loop_capturing_state(seams, config)
    return state, offers, seen


def test_t1_a_child_the_audit_raised_and_a_later_audit_discharged_is_fixed_not_left_for_the_owner(
        captured_state, tmp_path):
    # axis: the #2105 replay end to end — the rider is audited under its own key and recorded fixed
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/audit_spawned_riders_2115.md
    state, offers, seen = _spawn_loop()
    assert state["terminal"] == "converged", state.get("certification")
    assert state["auditSpawned"] == {X_KEY: P_KEY}
    assert offers == [(1, [P_KEY]), (2, [P_KEY])]  # the rider never joined a fix batch
    (_rnd, targets), = [s for s in seen if s[0] == 3]
    assert [t["id"] for t in targets] == [P_KEY, X_KEY]
    assert [t.get("spawnedFrom") for t in targets] == [None, P_KEY]
    ledger = _ledger(state)
    assert ledger[X_KEY]["disposition"] == "fixed" and ledger[X_KEY]["dispositionRound"] == 3
    assert ledger[X_KEY]["dispositionSeq"] > ledger[X_KEY]["raisedSeq"]
    assert "settledReason" not in ledger[X_KEY]
    assert not [r for r in ledger.values() if r.get("disposition") == "left-for-owner"]
    # the review record reads the child fixed, with no owner wait for it
    session = TRS.Session(tmp_path, **state).seat("code-reviewer")
    account = rs.account_from_session(session.save(), TRS.extras(), TRS.Fake().readers())
    outcomes = {f["findingKey"]: f["outcome"] for f in account["findings"]}
    assert outcomes == {P_KEY: "fixed", X_KEY: "fixed"}
    record = rr.build_record(account, TRS.Fake().readers())
    x_id = next(f["id"] for f in account["findings"] if f["findingKey"] == X_KEY)
    assert x_id not in record["leftForOwner"] and record["leftForOwner"] == []
    assert not [line for line in record["whatIsMissing"] if "waits for the owner" in line]


def test_t2_a_rider_the_audit_does_not_discharge_is_left_for_the_owner_and_never_refixed(
        captured_state):
    # axis: E1 — a rider ruled not-discharged has no disposition, is no fix, no breaker outcome, and is disclosed
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/audit_spawned_riders_2115.md
    state, offers, seen = _spawn_loop(x_ruling="not-discharged")
    assert state["terminal"] == "converged", state.get("certification")
    assert offers == [(1, [P_KEY]), (2, [P_KEY])]  # no fix leg for X, no stall
    row = _ledger(state)[X_KEY]
    assert row["disposition"] == "left-for-owner" and row["settledReason"].endswith(LEFT_OPEN)
    assert _ledger(state)[P_KEY]["disposition"] == "fixed"
    assert state["rounds"]["3"]["spawnedAudits"] == [
        {"id": X_KEY, "spawnedFrom": P_KEY, "ruling": "not-discharged"}]
    assert [d["detail"] for d in _decisions(state, "spawned-audit-not-discharged")] == [X_KEY]
    assert _decisions(state, "not-discharged") == []
    assert [o["ruling"] for o in state["auditRounds"][-1]["outcomes"]] == ["discharged"]
    assert not any(t["id"] == X_KEY for rnd, targets in seen if rnd > 3 for t in targets or [])


def test_t4_e5_a_parent_no_later_fix_batch_carries_gives_no_rider_and_the_child_is_left(
        captured_state):
    # axis: E5 — a child whose parent was never batched again is audited by no one and settles as before
    state, offers, seen = _spawn_loop(reraise_parent=False)
    assert state["terminal"] == "converged", state.get("certification")
    assert state["auditSpawned"] == {X_KEY: P_KEY}  # the link was bound; nothing batched the parent again
    assert offers == [(1, [P_KEY])]
    assert not any(t.get("spawnedFrom") for _rnd, targets in seen for t in targets or [])
    assert "spawnedAudits" not in state["rounds"].get("2", {})
    row = _ledger(state)[X_KEY]
    assert row["disposition"] == "left-for-owner" and row["settledReason"].endswith(LEFT_OPEN)


# --- the audits fold, on a built state ----------------------------------------------------------

def _round_three(**state_over):
    """P (Important) and X (Minor) staged in round 1; X was raised by the audit of P, and the batch now
    carries P again. The state sits in the delta round whose audits are about to fold."""
    state = _staged_state([_parent(), _child()])
    state["round"] = 3
    state["fixBatch"] = [dict(f) for f in state["findings"] if f["title"] == "Null deref"]
    state["auditSpawned"] = {X_KEY: P_KEY}
    state.update(state_over)
    return state


def _fold_round_three(state, results, manifest="targets", monkeypatch=None):
    """Build the targets, fold `results` against them, and return the outcome."""
    state["_auditTargets"] = RD._audit_targets(state, state["config"], {})
    if manifest == "targets":
        manifest = {t["id"]: t.get("auditorVendor") for t in state["_auditTargets"]}
    RD._fold_audits(state, state["config"], {"results": results, "collectionManifest": manifest})
    return state["_auditOutcome"]


def _ruling(key, ruling="discharged"):
    return {"id": key, "ruling": ruling, "reason": "judged by the auditor"}


@pytest.fixture
def folded_only(monkeypatch):
    """Stop after the audits fold: the scoped-finder routing that follows is not under test."""
    monkeypatch.setattr(RD, "_after_audits", lambda state, config: None)


def _settled(state):
    state["terminal"] = "converged"
    RD._settle_open_findings(state)
    return _ledger(state)


@pytest.mark.parametrize("case", ["no-result", "unauthenticated", "unseatable"])
def test_t3_e2_to_e4_a_rider_with_no_usable_ruling_is_left_for_the_owner(case, folded_only):
    # axis: E2 no result / E3 no manifest entry / E4 no independent auditor — each leaves the rider no disposition
    state = _round_three()
    results = [_ruling(P_KEY), _ruling(X_KEY)]
    manifest = "targets"
    if case == "no-result":
        results = [_ruling(P_KEY)]
    elif case == "unauthenticated":
        manifest = {P_KEY: "codex"}
    else:
        state["config"]["vendors"] = ["claude"]  # the fixer's own family: nothing independent is live
    outcome = _fold_round_three(state, results, manifest)
    rider = next(t for t in state["_auditTargets"] if t["id"] == X_KEY)
    assert rider["spawnedFrom"] == P_KEY
    assert ("auditorVendor" in rider) == (case != "unseatable")
    assert X_KEY not in outcome["discharged"] and X_KEY not in outcome["notDischarged"]
    assert [a["ruling"] for a in state["rounds"]["3"]["audits"] if a["id"] == X_KEY] == ["not-discharged"]
    assert [d["detail"] for d in _decisions(state, "spawned-audit-not-discharged")] == [X_KEY]
    if case == "no-result":
        assert outcome["unaudited"] == [X_KEY]
    elif case == "unauthenticated":
        assert outcome["unauthenticated"] == [X_KEY]
    else:
        assert rider["independence"] == "unseatable"
    row = _settled(state)[X_KEY]
    assert row["disposition"] == "left-for-owner" and row["settledReason"].endswith(LEFT_OPEN)


def test_t8_a_rider_not_discharged_is_in_no_fix_list_no_breaker_outcome_and_not_the_pr_body_check(
        folded_only):
    # axis: the rider split — notDischarged, auditRounds outcomes and prBodyAudited never see a rider
    state = _round_three()
    state["rounds"]["2"] = {"prBodyFix": {"after": "the staged PR body"}}
    outcome = _fold_round_three(state, [_ruling(P_KEY), _ruling(X_KEY, "not-discharged")])
    assert outcome["discharged"] == [P_KEY] and outcome["notDischarged"] == []
    assert state["_auditOutcome"] is outcome
    assert [o["identity"] for o in state["auditRounds"][-1]["outcomes"]] == [RD.finding_identity(_parent())]
    assert state["rounds"]["3"]["prBodyAudited"] == "the staged PR body"
    assert [a["id"] for a in state["rounds"]["3"]["audits"]] == [P_KEY, X_KEY]  # still disclosed
    assert _decisions(state, "not-discharged") == []
    assert RD._open_audit_ids_from_not_discharged(outcome["notDischarged"]) == set()
    assert ledger_disposition(state, X_KEY) is None


def test_t8_a_batch_target_not_discharged_still_withholds_the_pr_body_check_and_joins_the_fix_list(
        folded_only):
    state = _round_three()
    state["rounds"]["2"] = {"prBodyFix": {"after": "the staged PR body"}}
    outcome = _fold_round_three(state, [_ruling(P_KEY, "not-discharged"), _ruling(X_KEY)])
    assert outcome["notDischarged"] == [P_KEY] and outcome["discharged"] == [X_KEY]
    assert "prBodyAudited" not in state["rounds"]["3"]
    assert [d["detail"] for d in _decisions(state, "not-discharged")] == [P_KEY]
    assert "spawnedAudits" in state["rounds"]["3"]
    assert state["rounds"]["3"]["spawnedAudits"][0]["ruling"] == "discharged"
    assert _decisions(state, "spawned-audit-not-discharged") == []
    assert ledger_disposition(state, X_KEY) == "fixed"


def test_a_discharged_rider_is_recorded_fixed_through_the_ordinary_loop_and_is_no_breaker_outcome(
        folded_only):
    state = _round_three()
    outcome = _fold_round_three(state, [_ruling(P_KEY), _ruling(X_KEY)])
    assert outcome["discharged"] == [P_KEY, X_KEY] and outcome["notDischarged"] == []
    assert ledger_disposition(state, X_KEY) == "fixed" and ledger_disposition(state, P_KEY) == "fixed"
    assert len(state["auditRounds"][-1]["outcomes"]) == 1


def test_a_rider_that_rules_discharged_but_new_issue_passes_its_new_issues_on(folded_only):
    state = _round_three()
    grandchild = _finding("Odd spacing", line=1, severity="Minor")
    rider_ruling = dict(_ruling(X_KEY, "discharged-but-new-issue"), newIssues=[grandchild])
    outcome = _fold_round_three(state, [_ruling(P_KEY), rider_ruling])
    assert [n["originAuditId"] for n in outcome["newIssues"]] == [X_KEY]
    assert state["_newIssues"] == outcome["newIssues"]


def ledger_disposition(state, key):
    return (_ledger(state).get(key) or {}).get("disposition")


# --- the spawn map, bound after the compile -----------------------------------------------------

def _scoped_state(**state_over):
    state = _staged_state([_parent()])
    state["round"] = 2
    state.update(state_over)
    return state


def _audit_issue(origin, **extra):
    issue = _child(**extra)
    issue["originAuditId"] = origin
    return issue


def _fold_scoped(state, scoped=(), issues=()):
    state["_newIssues"] = [dict(i) for i in issues]
    RD._fold_scoped(state, state["config"], {"findings": [dict(f) for f in scoped]})
    return state.get("auditSpawned")


def test_t5_an_audit_new_issue_links_its_survivor_to_the_audit_target_it_came_from():
    state = _scoped_state()
    assert _fold_scoped(state, issues=[_audit_issue(P_KEY)]) == {X_KEY: P_KEY}


def test_t5_e6_a_scoped_finder_candidate_that_forges_an_origin_links_nothing():
    # axis: E6 — the origin is stripped from a scoped-finder candidate before the compile
    state = _scoped_state()
    forged = _child()
    forged["originAuditId"] = P_KEY
    assert _fold_scoped(state, scoped=[forged]) is None
    assert "auditSpawned" not in state
    staged = [f for f in state["_toVerify"] if f["title"] == "Stale comment"]
    assert staged and "originAuditId" not in staged[0]


def test_t5_e6_a_forged_origin_does_not_redirect_a_genuine_audit_link():
    state = _scoped_state()
    forged = _child(title="Other drift")
    forged["originAuditId"] = P_KEY
    spawned = _fold_scoped(state, scoped=[forged], issues=[_audit_issue("other-target")])
    assert spawned == {X_KEY: "other-target"}


def test_t5_e7_two_origins_at_one_anchor_link_nothing():
    # axis: E7 — an anchor two audit targets both raised has no single parent, so it has none
    state = _scoped_state()
    assert _fold_scoped(state, issues=[_audit_issue("a"), _audit_issue("b")]) is None
    assert "auditSpawned" not in state


def test_t5_e7_a_re_raise_by_two_origins_clears_an_earlier_single_parent_link():
    # axis: E7 — an anchor that became ambiguous in this fold drops its earlier link; an uncertain link stays with the owner
    state = _scoped_state(auditSpawned={X_KEY: "a"})
    _fold_scoped(state, issues=[_audit_issue("a"), _audit_issue("b")])
    assert X_KEY not in state["auditSpawned"]


def test_t5_e7_a_fold_with_no_audit_origin_for_the_child_keeps_its_earlier_link():
    # axis: E7 — only an anchor raised by more than one audit origin loses its link; a scoped-only re-raise keeps it
    state = _scoped_state(auditSpawned={X_KEY: P_KEY})
    assert _fold_scoped(state, scoped=[_child()]) == {X_KEY: P_KEY}


def test_t5_e7_one_origin_raising_an_anchor_twice_still_links():
    state = _scoped_state()
    assert _fold_scoped(state, issues=[_audit_issue("a"), _audit_issue("a")]) == {X_KEY: "a"}


def test_t5_f3_an_equal_severity_scoped_candidate_does_not_lose_the_audits_link():
    # axis: F3 — the compile keeps the scoped dict at an equal-severity anchor; the link is bound by anchor
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/audit_spawned_riders_2115.md
    state = _scoped_state()
    survivors = RD.mechanical_compile([_child(), _audit_issue(P_KEY)], state["reviewedDiff"])[0]
    assert len(survivors) == 1 and "originAuditId" not in survivors[0]  # the audit's origin is gone
    assert _fold_scoped(state, scoped=[_child()], issues=[_audit_issue(P_KEY)]) == {X_KEY: P_KEY}


@pytest.mark.parametrize("origin", ["", "   ", None, 7, ["a"]])
def test_t5_an_audit_new_issue_without_a_usable_origin_links_nothing(origin):
    state = _scoped_state()
    assert _fold_scoped(state, issues=[_audit_issue(origin)]) is None


def test_t5_the_line_is_coerced_as_the_compile_coerces_it_and_an_uncoercible_line_binds_nothing():
    state = _scoped_state()
    assert _fold_scoped(state, issues=[_audit_issue(P_KEY, line="2")]) == {X_KEY: P_KEY}
    state = _scoped_state()
    assert _fold_scoped(state, issues=[_audit_issue(P_KEY, line="two")]) is None
    assert RD.COMPILE_DROP_LINE_NOT_INTEGER in [
        d["reason"] for d in state["rounds"]["2"]["compileDrops"]]


def test_t5_a_malformed_spawn_map_is_replaced_not_trusted():
    state = _scoped_state(auditSpawned=["not", "a", "dict"])
    assert RD._audit_spawned(state) == {}
    assert _fold_scoped(state, issues=[_audit_issue(P_KEY)]) == {X_KEY: P_KEY}


# --- the rider targets --------------------------------------------------------------------------

def _targets(state):
    return RD._audit_targets(state, state["config"], {})


def test_a_rider_target_has_the_shape_of_a_batch_target_plus_spawned_from():
    targets = _targets(_round_three())
    batch_row, rider = targets
    assert [t["id"] for t in targets] == [P_KEY, X_KEY]
    assert rider.pop("spawnedFrom") == P_KEY and "spawnedFrom" not in batch_row
    assert set(rider) == set(batch_row)
    for field in ("identity", "severity", "independence", "auditorVendor", "fixerVendor", "file", "title"):
        assert field in rider
    assert rider["id"] == rider[SC.FINDING_KEY_FIELD] == X_KEY
    assert (rider["independence"], rider["auditorVendor"]) == (
        batch_row["independence"], batch_row["auditorVendor"])
    assert rider["line"] == 2 and rider["severity"] == "Minor"
    assert rider["body"] == "the comment is out of date" and rider["suggestion"] == "reword it"
    assert rider[RD.review_findings_schema.CONSEQUENCE_KEY] == "users lose their saved work"
    assert [b["id"] for b in rider["batchFindings"]] == [P_KEY]  # the batch the rider rides beside
    assert batch_row["batchFindings"] == []


def test_a_riders_round_findings_never_list_itself_and_a_batch_targets_list_the_rider():
    batch_row, rider = _targets(_round_three())
    assert [r["id"] for r in batch_row["roundFindings"]] == [X_KEY]
    assert rider["roundFindings"] == []


def test_t6_e9_a_session_without_a_usable_spawn_map_gets_todays_targets():
    # axis: E9 — an older session (no auditSpawned, or one that is not a dict) is audited as before
    base = _round_three()
    del base["auditSpawned"]
    today = _targets(base)
    assert [t["id"] for t in today] == [P_KEY] and "spawnedFrom" not in today[0]
    for malformed in ({}, None, [], "x", {X_KEY: None}, {X_KEY: 7}, {X_KEY: "not-in-the-batch"}):
        state = _round_three(auditSpawned=malformed)
        assert _targets(state) == today


def test_t4_e5_a_parent_outside_the_fix_batch_gives_no_rider():
    state = _round_three()
    state["fixBatch"] = [dict(_child(), **{SC.FINDING_KEY_FIELD: X_KEY})]  # the child itself is batched
    assert [t["id"] for t in _targets(state)] == [X_KEY]
    state = _round_three(auditSpawned={X_KEY: "f.py::elsewhere@L9"})
    assert [t["id"] for t in _targets(state)] == [P_KEY]


def _dispose(state, key, disposition, **fields):
    RD._record_disposition(state, key, disposition, 2, **fields)


@pytest.mark.parametrize("case", ["refuted", "fixed", "craft", "merged", "out-of-scope"])
def test_t6_e8_a_child_that_is_already_settled_merged_or_out_of_scope_is_no_rider(case):
    # axis: E8 — a rider is only a child no current disposition, merge or scope ruling has closed
    state = _round_three()
    assert [t["id"] for t in _targets(state)] == [P_KEY, X_KEY]
    if case == "merged":
        RD._record_merged_into(state, X_KEY, P_KEY)
    elif case == "out-of-scope":
        _dispose(state, X_KEY, "out-of-scope", outOfScopeReason="owner deferred it",
                 followUp={"item": "backlog", "revisitTrigger": "next", "classClosure": "owner"})
    elif case == "refuted":
        _dispose(state, X_KEY, "refuted", refutedReason="not a defect")
    else:
        _dispose(state, X_KEY, case)
    assert [t["id"] for t in _targets(state)] == [P_KEY]


def test_t6_e8_a_disposition_an_owner_ruling_reopened_does_not_close_the_child():
    state = _round_three()
    _dispose(state, X_KEY, "fixed")
    assert [t["id"] for t in _targets(state)] == [P_KEY]
    state["restagedAfterDispositionSeq"] = {X_KEY: _ledger(state)[X_KEY][SC.DISPOSITION_SEQ_FIELD]}
    assert [t["id"] for t in _targets(state)] == [P_KEY, X_KEY]


def test_t6_e8_a_disposition_older_than_the_last_raise_does_not_close_the_child():
    state = _round_three()
    _dispose(state, X_KEY, "fixed")
    RD._stage_findings(state, RD.mechanical_compile([_child()], None)[0])  # the child is raised again
    assert [t["id"] for t in _targets(state)] == [P_KEY, X_KEY]


def test_t6_e8_a_summary_row_is_no_rider():
    state = _round_three()
    state["findings"] = [f for f in state["findings"] if f["title"] != "Stale comment"]
    state["findings"].append({SC.FINDING_KEY_FIELD: X_KEY, "summaryEntry": True, "title": "+ 1 more Nits",
                              "severity": "Nit", "file": None, "line": None, "members": []})
    state[SC.DISPOSITION_LEDGER_KEY] = [r for r in state[SC.DISPOSITION_LEDGER_KEY]
                                        if SC.finding_identity_key(r) != X_KEY]
    assert [t["id"] for t in _targets(state)] == [P_KEY]


def test_t6_a_child_the_owner_ruled_out_of_scope_by_the_rule_verb_is_no_rider():
    # axis: the owner's effective decision, not the ledger disposition, keeps a skip ruling off the audit
    state = _round_three()
    assert [t["id"] for t in _targets(state)] == [P_KEY, X_KEY]
    _decide(state, X_KEY, "out-of-scope", 2)  # a `rule` ruling: the ledger row has no disposition
    assert not _ledger(state)[X_KEY].get("disposition")
    assert [t["id"] for t in _targets(state)] == [P_KEY]


def test_t6_a_child_the_owner_gave_guidance_still_rides():
    # axis: a fix-family owner decision (`guidance`) is no skip ruling, so the child still rides
    state = _round_three()
    _decide(state, X_KEY, "guidance", 2)
    batch_row, rider = _targets(state)
    assert rider["id"] == X_KEY and rider["spawnedFrom"] == P_KEY
    assert rider["ownerRuling"]["ruling"] == "guidance"


def test_t6_e10_a_ledger_that_cannot_be_read_gives_no_riders():
    # axis: E10 — a ledger read fault fails closed: no rider, though the live findings still carry the child
    state = _round_three()
    assert [t["id"] for t in _targets(state)] == [P_KEY, X_KEY]
    state[SC.DISPOSITION_LEDGER_KEY] = {"not": "a list"}
    assert RD._disposition_ledger_by_key(state)[1] is not None
    assert [t["id"] for t in _targets(state)] == [P_KEY]


# --- the attribution context --------------------------------------------------------------------

def test_t7_an_archived_rider_rides_its_parents_round_findings_and_its_fix_is_attributable(folded_only):
    # axis: F2 — a ledger-only rider is in the parent target's roundFindings, so `unnamedChangeFixes` verifies
    state = _round_three()
    state["findings"] = [f for f in state["findings"] if f["title"] == "Null deref"]  # a later scoped round
    assert X_KEY in _ledger(state) and RD._live_finding_by_key(state, X_KEY) is None
    batch_row, rider = _targets(state)
    (entry,) = batch_row["roundFindings"]
    assert entry == {"id": X_KEY, "file": "f.py", "line": 2, "title": "Stale comment",
                     "body": "the comment is out of date", "suggestion": "reword it"}
    assert rider["roundFindings"] == []
    clearing = dict(_ruling(P_KEY), unnamedChange="it also rewords the stale comment",
                    unnamedChangeFixes=[X_KEY])
    outcome = _fold_round_three(state, [clearing, _ruling(X_KEY)])
    assert outcome["discharged"] == [P_KEY, X_KEY] and outcome["unnamedChange"] == []
    assert outcome["attributedChange"] == [P_KEY]
    audit = next(a for a in state["rounds"]["3"]["audits"] if a["id"] == P_KEY)
    assert audit["ruling"] == "discharged" and audit["sameRoundFixes"] == [X_KEY]


def test_t7_without_the_rider_in_round_findings_the_same_claim_is_refused(folded_only):
    state = _round_three()
    state["findings"] = [f for f in state["findings"] if f["title"] == "Null deref"]
    state["auditSpawned"] = {}
    clearing = dict(_ruling(P_KEY), unnamedChange="it also rewords the stale comment",
                    unnamedChangeFixes=[X_KEY])
    outcome = _fold_round_three(state, [clearing])
    assert outcome["unnamedChange"] == [P_KEY] and outcome["discharged"] == []
