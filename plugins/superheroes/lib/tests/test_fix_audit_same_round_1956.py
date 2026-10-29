"""#1956: the fix audit admits a same-round fix and a revert (and nothing else).

A clearing audit result that reports an unnamed change is discharged only when an owner ruling allows
it, or when the auditor attributes every unnamed change to claims that each verify against the
driver's own record: `unnamedChangeFixes` (ids in the target's `roundFindings`) and/or
`unnamedChangeReverts` (refs in the target's `reportedUnnamedChanges`).

Drives the real round driver: `run_loop` with scripted seams for the loop-shaped cases, the audit fold,
the audit-target builder, the submit guard and the native-result transport directly for the rest.

Bite-proof record: plugins/superheroes/lib/tests/bite_proofs/fix_audit_same_round_1956.md
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

import audits as AU  # noqa: E402
import engine_adapter as EA  # noqa: E402
import engine_dispatch as ED  # noqa: E402
import engine_result_channel as ERC  # noqa: E402
import payload_contracts as PC  # noqa: E402
import test_round_driver as TRD  # noqa: E402
from test_fix_scope_c7 import (  # noqa: E402,F401
    UNNAMED, UNNAMED_REASON_PREFIX, _decide, _decisions, _finding, _key, _ledger,
    _native_ruling_branch, _ruling_schema, _staged_state, captured_state)

RD = TRD.RD  # run_loop runs on test_round_driver's own load of the module

# --- the audit fold -----------------------------------------------------------------------------

def _target(round_findings=("m",), reported=("r2:a",), **extra):
    target = {"id": "a", "file": "f.py", "line": 1, "title": "t", "severity": "Important"}
    if round_findings is not None:
        target["roundFindings"] = [{"id": i, "file": "g.py", "line": 3, "title": "other"}
                                   for i in round_findings]
    if reported is not None:
        target["reportedUnnamedChanges"] = [{"ref": r, "round": 2, "id": "a", "text": "earlier"}
                                            for r in reported]
    target.update(extra)
    return target


def _fold(result, allowed=(), target=None, **kw):
    body = {"id": "a", "ruling": "discharged", "reason": "the fix resolves it"}
    body.update(result)
    return AU.apply_audit_results([target or _target()], [body], change_allowed_ids=allowed, **kw)


def _refused(out):
    assert out["discharged"] == [] and out["notDischarged"] == ["a"]
    assert out["unnamedChange"] == ["a"] and out["attributedChange"] == []
    audit = out["audits"][0]
    assert audit["ruling"] == "not-discharged"
    assert audit["reason"] == "%s: %s" % (UNNAMED_REASON_PREFIX, UNNAMED)
    assert "attributedChange" not in audit and "allowedChange" not in audit


def test_a_fixes_claim_naming_a_round_finding_discharges_and_records_the_attribution():
    out = _fold({"unnamedChange": "  %s " % UNNAMED, "unnamedChangeFixes": ["m"]})
    assert out["discharged"] == ["a"] and out["unnamedChange"] == []
    assert out["attributedChange"] == ["a"]
    audit = out["audits"][0]
    assert audit["ruling"] == "discharged"
    assert audit["attributedChange"] == UNNAMED and audit["sameRoundFixes"] == ["m"]
    assert audit["reportedUnnamedChange"] == UNNAMED
    assert "revertedChanges" not in audit and "allowedChange" not in audit


def test_a_reverts_claim_naming_a_reported_change_discharges_and_records_the_attribution():
    out = _fold({"unnamedChange": UNNAMED, "unnamedChangeReverts": ["r2:a"]})
    assert out["discharged"] == ["a"] and out["attributedChange"] == ["a"]
    audit = out["audits"][0]
    assert audit["revertedChanges"] == ["r2:a"] and audit["attributedChange"] == UNNAMED
    assert "sameRoundFixes" not in audit and "allowedChange" not in audit


def test_a_discharged_but_new_issue_result_with_a_verifying_claim_keeps_its_new_issues():
    issue = {"file": "g.py", "line": 3, "title": "fresh", "severity": "Minor"}
    out = _fold({"ruling": "discharged-but-new-issue", "unnamedChange": UNNAMED,
                 "unnamedChangeFixes": ["m"], "newIssues": [issue]})
    assert out["discharged"] == ["a"] and out["attributedChange"] == ["a"]
    assert out["audits"][0]["ruling"] == "discharged-but-new-issue"
    assert [n["title"] for n in out["newIssues"]] == ["fresh"]


def test_an_unnamed_change_with_no_claim_is_refused_though_the_record_has_candidates():
    # axis: an unclaimed unnamed change keeps today's refusal, same reason text and outcome list
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/fix_audit_same_round_1956.md
    out = _fold({"unnamedChange": UNNAMED})
    _refused(out)
    for empty in ({"unnamedChangeFixes": []}, {"unnamedChangeReverts": []},
                  {"unnamedChangeFixes": None, "unnamedChangeReverts": None}):
        _refused(_fold({"unnamedChange": UNNAMED, **empty}))


def test_a_discharged_but_new_issue_result_with_no_claim_is_still_refused():
    issue = {"file": "g.py", "line": 3, "title": "fresh", "severity": "Minor"}
    out = _fold({"ruling": "discharged-but-new-issue", "unnamedChange": UNNAMED, "newIssues": [issue]})
    assert out["discharged"] == [] and out["unnamedChange"] == ["a"]
    assert [n["title"] for n in out["newIssues"]] == ["fresh"]


def test_a_fixes_claim_naming_an_id_outside_round_findings_is_refused():
    # axis: the fixes claim must be a finding of the driver's own roundFindings
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/fix_audit_same_round_1956.md
    _refused(_fold({"unnamedChange": UNNAMED, "unnamedChangeFixes": ["elsewhere"]}))


@pytest.mark.parametrize("target", [
    _target(round_findings=None), _target(round_findings=()), _target(roundFindings="m"),
    _target(roundFindings=[{"title": "no id"}, "m", {"id": "  "}, {"id": 7}]),
], ids=["absent", "empty", "not-a-list", "no-usable-id"])
def test_a_fixes_claim_on_a_target_with_no_usable_round_findings_is_refused(target):
    _refused(_fold({"unnamedChange": UNNAMED, "unnamedChangeFixes": ["m"]}, target=target))


def test_a_fixes_claim_naming_one_known_and_one_unknown_id_is_refused():
    _refused(_fold({"unnamedChange": UNNAMED, "unnamedChangeFixes": ["m", "elsewhere"]}))


def test_a_reverts_claim_naming_a_ref_outside_reported_changes_is_refused():
    # axis: the reverts claim must be a ref of the driver's own reportedUnnamedChanges
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/fix_audit_same_round_1956.md
    _refused(_fold({"unnamedChange": UNNAMED, "unnamedChangeReverts": ["r9:a"]}))


@pytest.mark.parametrize("target", [
    _target(reported=None), _target(reported=()), _target(reportedUnnamedChanges="r2:a"),
    _target(reportedUnnamedChanges=[{"round": 2}, "r2:a", {"ref": ""}, {"ref": 7}]),
], ids=["absent", "empty", "not-a-list", "no-usable-ref"])
def test_a_reverts_claim_on_a_target_with_no_usable_reported_changes_is_refused(target):
    _refused(_fold({"unnamedChange": UNNAMED, "unnamedChangeReverts": ["r2:a"]}, target=target))


def test_both_claims_verifying_are_admitted_and_both_recorded():
    out = _fold({"unnamedChange": UNNAMED, "unnamedChangeFixes": ["m"],
                 "unnamedChangeReverts": ["r2:a"]})
    assert out["discharged"] == ["a"] and out["attributedChange"] == ["a"]
    audit = out["audits"][0]
    assert audit["sameRoundFixes"] == ["m"] and audit["revertedChanges"] == ["r2:a"]


def test_a_failing_fixes_claim_is_not_rescued_by_a_verifying_reverts_claim():
    # axis: every claim given must verify — one failing claim refuses the whole result
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/fix_audit_same_round_1956.md
    _refused(_fold({"unnamedChange": UNNAMED, "unnamedChangeFixes": ["elsewhere"],
                    "unnamedChangeReverts": ["r2:a"]}))


def test_a_failing_reverts_claim_is_not_rescued_by_a_verifying_fixes_claim():
    _refused(_fold({"unnamedChange": UNNAMED, "unnamedChangeFixes": ["m"],
                    "unnamedChangeReverts": ["r9:a"]}))


def test_claims_without_an_unnamed_change_have_no_effect_and_record_nothing():
    out = _fold({"unnamedChangeFixes": ["m"], "unnamedChangeReverts": ["r2:a"]})
    assert out["discharged"] == ["a"] and out["attributedChange"] == []
    audit = out["audits"][0]
    for key in ("attributedChange", "sameRoundFixes", "revertedChanges", "reportedUnnamedChange",
                "allowedChange"):
        assert key not in audit


def test_a_not_discharged_ruling_is_unchanged_and_only_records_the_reported_change():
    out = _fold({"ruling": "not-discharged", "reason": "still wrong", "unnamedChange": UNNAMED,
                 "unnamedChangeFixes": ["m"]})
    assert out["discharged"] == [] and out["attributedChange"] == [] and out["unnamedChange"] == []
    audit = out["audits"][0]
    assert audit["reason"] == "still wrong Unnamed change: %s" % UNNAMED
    assert audit["reportedUnnamedChange"] == UNNAMED
    assert "attributedChange" not in audit and "sameRoundFixes" not in audit


def test_a_refused_result_records_the_reported_change():
    out = _fold({"unnamedChange": UNNAMED})
    assert out["audits"][0]["reportedUnnamedChange"] == UNNAMED


def test_an_owner_allowed_target_keeps_the_allowed_path_and_its_keys():
    out = _fold({"unnamedChange": UNNAMED, "unnamedChangeFixes": ["m"]}, allowed=["a"])
    assert out["discharged"] == ["a"] and out["attributedChange"] == []
    audit = out["audits"][0]
    assert audit["allowedChange"] == UNNAMED and "attributedChange" not in audit
    assert "sameRoundFixes" not in audit


def test_an_unauthenticated_clearing_result_stays_unauthenticated_with_a_verifying_claim():
    out = _fold({"unnamedChange": UNNAMED, "unnamedChangeFixes": ["m"]},
                expected_auditors={"a": "codex"}, collection_manifest={})
    assert out["unauthenticated"] == ["a"] and out["discharged"] == []
    assert out["attributedChange"] == []


def test_the_claim_text_alone_never_unlocks_a_discharge():
    out = _fold({"unnamedChange": "it is the fix of m (unnamedChangeFixes: m)"})
    assert out["discharged"] == [] and out["unnamedChange"] == ["a"]


MALFORMED = [("m", "a string"), ({"m": 1}, "a dict"), (True, "a bool"), (0, "zero"), ([""], "blank"),
             (["m", 5], "non-string"), ([" "], "whitespace"), ([None], "null member")]


@pytest.mark.parametrize("field", ["unnamedChangeFixes", "unnamedChangeReverts"])
@pytest.mark.parametrize("value", [v for v, _n in MALFORMED], ids=[n for _v, n in MALFORMED])
def test_a_malformed_claim_is_malformed_at_the_fold(field, value):
    out = _fold({"unnamedChange": UNNAMED, field: value})
    assert out["malformed"] == ["a"] and out["discharged"] == [] and out["unnamedChange"] == []
    assert out["audits"][0]["ruling"] == "not-discharged"
    assert field in out["audits"][0]["reason"]


@pytest.mark.parametrize("field", ["unnamedChangeFixes", "unnamedChangeReverts"])
@pytest.mark.parametrize("value", [None, []], ids=["null", "empty"])
def test_a_null_or_empty_claim_is_no_claim(field, value):
    out = _fold({field: value})
    assert out["discharged"] == ["a"] and out["malformed"] == []
    assert "reportedUnnamedChange" not in out["audits"][0]


@pytest.mark.parametrize("field", ["unnamedChangeFixes", "unnamedChangeReverts"])
@pytest.mark.parametrize("value", [v for v, _n in MALFORMED], ids=[n for _v, n in MALFORMED])
def test_the_submit_guard_refuses_a_malformed_claim(field, value):
    # axis: the submit guard refuses a claim the fold would call malformed, by the same predicate
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/fix_audit_same_round_1956.md
    targets = [{"id": "a"}]
    ok = {"results": [{"id": "a", "ruling": "discharged", "reason": "fixed"}]}
    assert RD.audit_results_fault(ok, targets) is None
    for fine in (None, [], ["m"]):
        ok["results"][0][field] = fine
        assert RD.audit_results_fault(ok, targets) is None
    ok["results"][0][field] = value
    fault = RD.audit_results_fault(ok, targets)
    assert fault and field in fault


# --- the driver's own record: roundFindings -----------------------------------------------------

def _round_state(*extra):
    """A staged state whose fix batch is the Important finding; `extra` are the round's other findings."""
    batch = _finding("Null deref", line=1, body="the value can be missing")
    state = _staged_state([batch] + [dict(f) for f in extra])
    state["fixBatch"] = [dict(f) for f in state["findings"] if f["title"] == "Null deref"]
    return state


def _targets(state):
    return RD._audit_targets(state, state["config"], {})


def test_audit_targets_carry_the_rounds_other_findings_and_not_the_batch():
    state = _round_state(_finding("Stale comment", line=9, severity="Minor", body="says the wrong thing",
                                  suggestion="reword it"))
    (target,) = _targets(state)
    assert [r["id"] for r in target["roundFindings"]] == [_key("Stale comment", 9)]
    entry = target["roundFindings"][0]
    assert entry["file"] == "f.py" and entry["line"] == 9 and entry["title"] == "Stale comment"
    assert entry["body"] == "says the wrong thing" and entry["suggestion"] == "reword it"
    assert "ownerRuling" not in entry
    assert target["reportedUnnamedChanges"] == []


def test_audit_targets_leave_out_a_round_finding_the_owner_skipped():
    # axis: an owner skip / out-of-scope ruling takes a finding out of the attributable round findings
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/fix_audit_same_round_1956.md
    state = _round_state(_finding("Stale comment", line=9, severity="Minor"),
                         _finding("Dead branch", line=12, severity="Minor"),
                         _finding("Wrong name", line=15, severity="Minor"),
                         _finding("Odd spacing", line=18, severity="Minor"))
    _decide(state, _key("Stale comment", 9), "out-of-scope", 1)
    _decide(state, _key("Wrong name", 15), "guidance", 1)
    RD._record_disposition(state, _key("Dead branch", 12), "refuted", 1, refutedReason="not a defect")
    (target,) = _targets(state)
    ids = [r["id"] for r in target["roundFindings"]]
    assert ids == [_key("Wrong name", 15), _key("Odd spacing", 18)]
    guided = target["roundFindings"][0]
    assert guided["ownerRuling"]["ruling"] == "guidance" and guided["ownerRulingSeq"] == 2
    assert guided["ownerRuling"]["guidance"] == "keep the retry behaviour"


def test_audit_targets_leave_out_an_out_of_scope_ledger_disposition():
    state = _round_state(_finding("Stale comment", line=9, severity="Minor"))
    RD._record_disposition(state, _key("Stale comment", 9), "out-of-scope", 1,
                           outOfScopeReason="owner deferred it",
                           followUp={"item": "backlog", "revisitTrigger": "next", "classClosure": "owner"})
    (target,) = _targets(state)
    assert target["roundFindings"] == []


def test_audit_targets_skip_a_non_dict_round_finding():
    state = _round_state(_finding("Stale comment", line=9, severity="Minor"))
    state["findings"] = state["findings"] + ["not a finding", None]
    (target,) = _targets(state)
    assert [r["id"] for r in target["roundFindings"]] == [_key("Stale comment", 9)]


def test_a_fixes_claim_naming_an_owner_skipped_finding_is_refused_at_the_fold():
    state = _round_state(_finding("Stale comment", line=9, severity="Minor"))
    _decide(state, _key("Stale comment", 9), "out-of-scope", 1)
    (target,) = _targets(state)
    body = {"id": target["id"], "ruling": "discharged", "reason": "ok", "unnamedChange": UNNAMED,
            "unnamedChangeFixes": [_key("Stale comment", 9)]}
    out = AU.apply_audit_results(
        [target], [body], expected_auditors={target["id"]: "codex"},
        collection_manifest={target["id"]: "codex"})
    assert out["discharged"] == [] and out["unnamedChange"] == [target["id"]]


# --- the driver's own record: reportedUnnamedChanges --------------------------------------------

def _hist(**rounds):
    return {"rounds": {k[1:]: {"audits": v} for k, v in rounds.items()}}


def test_history_reads_a_structured_reported_change():
    state = _hist(r2=[{"id": "a", "ruling": "not-discharged", "reason": "x",
                       "reportedUnnamedChange": "does X"}])
    assert RD._reported_unnamed_changes(state) == [
        {"ref": "r2:a", "round": 2, "id": "a", "text": "does X"}]


def test_history_reads_a_legacy_downgraded_clearing_reason():
    state = _hist(r3=[{"id": "b", "ruling": "not-discharged",
                       "reason": AU.UNNAMED_CHANGE_REASON_PREFIX + "does Y"}])
    assert RD._reported_unnamed_changes(state) == [
        {"ref": "r3:b", "round": 3, "id": "b", "text": "does Y"}]


def test_history_reads_a_legacy_direct_not_discharged_reason():
    # axis: a session recorded before the structured key still yields its reported change
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/fix_audit_same_round_1956.md
    state = _hist(r4=[{"id": "c", "ruling": "not-discharged",
                       "reason": "still wrong Unnamed change: does Z"}])
    assert RD._reported_unnamed_changes(state) == [
        {"ref": "r4:c", "round": 4, "id": "c", "text": "does Z"}]


def test_history_keeps_sibling_targets_apart_and_the_earlier_report_after_a_silent_audit():
    state = _hist(
        r3=[{"id": "a", "ruling": "discharged", "reason": "fine"}],
        r2=[{"id": "a", "ruling": "not-discharged", "reason": "x", "reportedUnnamedChange": "does X"},
            {"id": "d", "ruling": "not-discharged", "reason": "y", "reportedUnnamedChange": "does D"}])
    assert [(r["ref"], r["text"]) for r in RD._reported_unnamed_changes(state)] == [
        ("r2:a", "does X"), ("r2:d", "does D")]


def test_history_orders_all_rounds_numerically_and_keeps_the_first_of_a_repeated_id():
    state = _hist(
        r10=[{"id": "a", "ruling": "not-discharged", "reason": "z", "reportedUnnamedChange": "late"}],
        r2=[{"id": "a", "ruling": "not-discharged", "reason": "x", "reportedUnnamedChange": "first"},
            {"id": "a", "ruling": "not-discharged", "reason": "x", "reportedUnnamedChange": "second"}])
    assert [(r["ref"], r["text"]) for r in RD._reported_unnamed_changes(state)] == [
        ("r2:a", "first"), ("r10:a", "late")]


def test_history_skips_what_it_cannot_read():
    state = {"rounds": {
        "2": {"audits": ["not a dict", {"id": "a", "ruling": "not-discharged", "reason": 7},
                         {"ruling": "not-discharged", "reason": "x Unnamed change: no id"},
                         {"id": "b", "ruling": "discharged", "reason": "fine Unnamed change: ignored"},
                         {"id": "c", "ruling": "not-discharged", "reason": "x Unnamed change:    "}]},
        "x": {"audits": [{"id": "a", "ruling": "not-discharged", "reportedUnnamedChange": "odd round"}]},
        "3": "not a dict", "4": {"audits": "not a list"}}}
    assert RD._reported_unnamed_changes(state) == []
    assert RD._reported_unnamed_changes({"rounds": None}) == []
    assert RD._reported_unnamed_changes({}) == []


# --- the loop -----------------------------------------------------------------------------------

def _same_round_loop(captured_state, claims_by_round, extra=()):
    """Round 1 raises the Important (the fix batch) and `extra` findings outside the batch; each audit
    round reports an unnamed change plus whatever `claims_by_round[rnd](target)` returns."""
    batch_key = _key("Null deref")
    offers, seen = [], []

    def reviewer(dim, tier, rnd, ctx):
        if rnd == 1 and dim == "code-reviewer":
            return {"findings": [_finding("Null deref", body="the value can be missing",
                                          suggestion="check it first")] + [dict(f) for f in extra]}
        return []

    def fix_step(batch, rnd, payload):
        offers.append((rnd, [RD._fix_batch_row_key(r) for r in batch]))
        return {"fixes": [], "headDiff": TRD._headf(len(offers)), "changedSubjects": ["Code"]}

    def auditor(targets, rnd):
        seen.append((rnd, copy.deepcopy(targets)))
        out = []
        for t in targets or []:
            result = {"id": t["id"], "ruling": "discharged", "reason": "fix resolves it",
                      "evidence": "tests pass", "auditorVendor": t.get("auditorVendor")}
            if rnd in claims_by_round:
                result["unnamedChange"] = UNNAMED
                result.update(claims_by_round[rnd](t))
            out.append(result)
        return out

    seams = TRD._seams(reviewer=reviewer, fix_step=fix_step, auditor=auditor)
    _result, state = TRD._run_loop_capturing_state(seams, TRD._cfg_cert())
    return batch_key, state, offers, seen


_OWNER_STALL_KINDS = frozenset({"stall-menu", "stall-choice", "fix-keeps-failing"})


def _stall_kinds(state):
    return _OWNER_STALL_KINDS & {d["kind"] for d in state["decisions"]}


def test_a_same_round_fix_in_the_fixers_diff_does_not_stop_the_batch_at_the_owner_gate(captured_state):
    # axis: an unnamed change the auditor attributes to a same-round finding is discharged, end to end
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/fix_audit_same_round_1956.md
    # line 2 is the other line of the round's diff: a finding outside the diff is dropped at compile
    minor = _finding("Stale comment", line=2, severity="Minor", body="the comment is out of date")
    minor_key = _key("Stale comment", 2)  # computed here, never read off the target
    key, state, offers, seen = _same_round_loop(
        captured_state, {2: lambda t: {"unnamedChangeFixes": [minor_key]}}, extra=[minor])
    assert state["terminal"] == "converged"
    audit = state["rounds"]["2"]["audits"][0]
    assert audit["ruling"] == "discharged" and audit["sameRoundFixes"] == [minor_key]
    assert audit["attributedChange"] == UNNAMED and "allowedChange" not in audit
    assert "auditUnnamedChange" not in state["rounds"]["2"]
    assert state["rounds"]["2"]["auditAttributedChange"] == [key]
    assert len(_decisions(state, "audit-attributed-change")) == 1
    assert _decisions(state, "audit-unnamed-change") == []
    row = _ledger(state)[key]
    assert row["disposition"] == "fixed" and row["dispositionRound"] == 2
    assert offers == [(1, [key])]
    assert _stall_kinds(state) == set()
    (rnd, targets), = [s for s in seen if s[0] == 2]
    assert [r["id"] for r in targets[0]["roundFindings"]] == [minor_key]
    assert key not in [r["id"] for r in targets[0]["roundFindings"]]


def test_a_revert_of_an_earlier_reported_change_is_discharged_and_does_not_stall(captured_state):
    # axis: an unnamed change the auditor attributes to the undoing of a reported change is discharged
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/fix_audit_same_round_1956.md
    key = _key("Null deref")
    ref_seen = {}

    def revert_round_three(target):
        ref_seen["targets"] = [r for r in target["reportedUnnamedChanges"]]
        return {"unnamedChangeReverts": [target["reportedUnnamedChanges"][0]["ref"]]}

    key, state, offers, seen = _same_round_loop(
        captured_state, {2: lambda t: {}, 3: revert_round_three})
    assert state["terminal"] == "converged"
    assert state["rounds"]["2"]["auditUnnamedChange"] == [key]
    round_three = state["rounds"]["3"]["audits"][0]
    assert round_three["ruling"] == "discharged"
    assert round_three["revertedChanges"] == ["r2:%s" % key]
    assert round_three["attributedChange"] == UNNAMED and "allowedChange" not in round_three
    assert ref_seen["targets"] == [{"ref": "r2:%s" % key, "round": 2, "id": key, "text": UNNAMED}]
    assert state["rounds"]["3"]["auditAttributedChange"] == [key]
    assert offers == [(1, [key]), (2, [key])]
    assert _stall_kinds(state) == set()
    assert _ledger(state)[key]["disposition"] == "fixed"


def test_an_unclaimed_unnamed_change_still_ends_with_an_unnamed_change_on_the_round(captured_state):
    minor = _finding("Stale comment", line=2, severity="Minor")
    key, state, offers, seen = _same_round_loop(captured_state, {2: lambda t: {}}, extra=[minor])
    assert state["terminal"] == "converged"
    audit = state["rounds"]["2"]["audits"][0]
    assert audit["ruling"] == "not-discharged"
    assert audit["reason"] == "%s: %s" % (UNNAMED_REASON_PREFIX, UNNAMED)
    assert state["rounds"]["2"]["auditUnnamedChange"] == [key]
    assert "auditAttributedChange" not in state["rounds"]["2"]
    assert len(_decisions(state, "audit-unnamed-change")) == 1
    assert offers[:2] == [(1, [key]), (2, [key])]


def test_a_claim_naming_a_finding_that_is_not_a_round_finding_still_ends_with_an_unnamed_change(
        captured_state):
    key, state, _offers, _seen = _same_round_loop(
        captured_state, {2: lambda t: {"unnamedChangeFixes": ["f.py::invented@L4"]}})
    assert state["rounds"]["2"]["auditUnnamedChange"] == [key]
    assert state["rounds"]["2"]["audits"][0]["ruling"] == "not-discharged"


# --- transport ----------------------------------------------------------------------------------

def test_the_audit_contract_declares_both_claims_as_optional_lists():
    contract, reason = PC.payload_contract(PC.P_AUDITS)
    assert reason is None
    for field in ("unnamedChangeFixes", "unnamedChangeReverts"):
        assert field in contract["optional"]
        assert contract["types"][field] == "list"


def test_the_strict_ruling_schema_is_valid_and_lists_both_claims_as_nullable_string_arrays():
    schema = _ruling_schema()
    ERC.assert_strict_mode_valid(schema)
    found = []

    def walk(node):
        if isinstance(node, dict):
            props = node.get("properties")
            if isinstance(props, dict) and "unnamedChangeFixes" in props:
                found.append(node)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(schema)
    assert found
    for holder in found:
        for field in ("unnamedChangeFixes", "unnamedChangeReverts"):
            assert field in holder["required"]
            spec = holder["properties"][field]
            assert "array" in spec["type"] and "null" in spec["type"]


def test_native_audit_branch_claims_arrive_in_the_scrubbed_ruling_record():
    branch = _native_ruling_branch(unnamedChange=UNNAMED, unnamedChangeFixes=["m"],
                                   unnamedChangeReverts=["r2:a"])
    ok, why = ERC.validate(_ruling_schema(), {"result": branch})
    assert ok, why
    normalized = ED._normalize_native_review_branch_for_parser(branch)
    assert normalized["unnamedChangeFixes"] == ["m"] and normalized["unnamedChangeReverts"] == ["r2:a"]
    parsed = EA._REVIEW_CONTRACT_PARSERS["ruling"](normalized, None)
    assert parsed["ok"] is True
    assert parsed["ruling"]["unnamedChangeFixes"] == ["m"]
    assert parsed["ruling"]["unnamedChangeReverts"] == ["r2:a"]


def test_native_audit_branch_with_null_claims_drops_them():
    branch = _native_ruling_branch()
    assert branch["unnamedChangeFixes"] is None and branch["unnamedChangeReverts"] is None
    ok, why = ERC.validate(_ruling_schema(), {"result": branch})
    assert ok, why
    normalized = ED._normalize_native_review_branch_for_parser(branch)
    assert "unnamedChangeFixes" not in normalized and "unnamedChangeReverts" not in normalized
    parsed = EA._REVIEW_CONTRACT_PARSERS["ruling"](normalized, None)
    assert parsed["ok"] is True
    assert "unnamedChangeFixes" not in parsed["ruling"]
    assert "unnamedChangeReverts" not in parsed["ruling"]
