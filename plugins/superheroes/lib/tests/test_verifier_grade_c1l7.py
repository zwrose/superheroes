"""The verifier grades every finding it judges, and only its grade is kept (C1-L7, #2211, WO-B).

Every finding the verifier fold gives an honored judgment carries
`grade: {"verdict": "confirmed" | "plausible" | "wrong", "reason": <non-empty>}` on its staged survivor copy
and on its ledger row. A finding the verifier was silent on, or gave a malformed or ambiguous verdict,
carries none. No `grade` reaches the ledger or `_toVerify` from anywhere but this fold: a seat-supplied
`grade` is stripped where findings are staged.

Edges: G1 a REFUTED that executed and gave a reason is graded `wrong` (truth table, driver fold) · G2 silence,
an unknown verdict, a reasonless verdict and an ambiguous id carry no grade, and a grade the input copy
held is removed · G3 the refuted ledger row carries the `wrong` grade · G4 a seat-supplied grade is stripped
at seeding, and a finding refuted earlier in the same round keeps the grade that closed it · a not-executed
REFUTED is never `wrong` · the author-justification post-filter's refuted row carries no grade · a verdict id
that resolves to no staged finding writes no grade · a keyless staged finding writes no ledger row.

Bite-proof record: plugins/superheroes/lib/tests/bite_proofs/c1l7_wo_b_verifier_grade.md
"""
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _p in (_HERE, _LIB):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import test_round_driver as TRD  # noqa: E402
import test_synthesis_seat_1858 as S1858  # noqa: E402
import test_verification as TV  # noqa: E402
import verification as V  # noqa: E402

RD = TRD.RD
SC = RD.session_contract
_GRADE_VERDICTS = {"confirmed", "plausible", "wrong"}


def _apply(verdict, **finding_kw):
    findings = TV._stage([TV._f("a.py", "bug", "Important", **finding_kw)])
    return V.apply_verdicts(findings, [verdict] if verdict is not None else [])


def _assert_grade(grade, verdict, reason):
    assert grade == {"verdict": verdict, "reason": reason}, grade
    assert grade["verdict"] in _GRADE_VERDICTS


# ---- apply_verdicts truth table ---------------------------------------------------------------

def test_g1_executed_refuted_with_reason_drops_with_a_wrong_grade():
    out = _apply({"id": "v0", "verdict": "REFUTED", "reason": "  the guard at line 40 returns early  "})
    assert out["findings"] == []
    assert len(out["drops"]) == 1
    _assert_grade(out["drops"][0]["grade"], "wrong", "the guard at line 40 returns early")


def test_confirmed_with_a_receipt_is_graded_confirmed():
    out = _apply({"id": "v0", "verdict": "CONFIRMED", "reason": " reproduced ", "evidence": "ran: 1 failed"})
    kept = out["findings"][0]
    assert kept["verdict"] == "CONFIRMED"
    _assert_grade(kept["grade"], "confirmed", "reproduced")


def test_plausible_is_graded_plausible_with_its_reason():
    out = _apply({"id": "v0", "verdict": "PLAUSIBLE", "reason": "could not fully verify"})
    kept = out["findings"][0]
    assert kept["verdict"] == "PLAUSIBLE"
    _assert_grade(kept["grade"], "plausible", "could not fully verify")


@pytest.mark.parametrize("evidence", [None, "", "   "])
def test_receiptless_confirmed_is_graded_plausible_naming_the_missing_receipt(evidence):
    verdict = {"id": "v0", "verdict": "CONFIRMED", "reason": "looks real"}
    if evidence is not None:
        verdict["evidence"] = evidence
    kept = _apply(verdict)["findings"][0]
    assert kept["verdict"] == "PLAUSIBLE"
    _assert_grade(kept["grade"], "plausible", "looks real (confirmed without an executed receipt)")


@pytest.mark.parametrize("field, text, token", [
    ("reason", "probe failed: sh: 1: vitest: command not found (exit 127)", "command-not-found"),
    ("evidence", "ModuleNotFoundError: No module named 'x'", "module-not-found"),
])
def test_not_executed_refuted_is_kept_plausible_and_never_wrong(field, text, token):
    verdict = {"id": "v0", "verdict": "REFUTED", "reason": "refuted by the probe"}
    verdict[field] = text
    out = _apply(verdict)
    assert out["drops"] == []
    kept = out["findings"][0]
    assert kept["grade"]["verdict"] == "plausible"
    assert kept["grade"]["reason"] == out["notExecuted"][0]["reason"]
    assert kept["grade"]["reason"].startswith("not-executed: %s: " % token)


def test_g2_a_silent_verdict_carries_no_grade():
    out = _apply(None)
    assert "grade" not in out["findings"][0]
    assert out["unverified"] == ["v0"]


def test_g2_a_silent_verdict_removes_a_grade_the_staged_copy_already_carried():
    out = _apply(None, grade={"verdict": "wrong", "reason": "seat said so"})
    assert len(out["findings"]) == 1
    assert "grade" not in out["findings"][0]


@pytest.mark.parametrize("verdict", [
    {"id": "v0", "verdict": "BOGUS", "reason": "hmm"},
    {"id": "v0", "verdict": "CONFIRMED", "reason": "", "evidence": "ran"},
    {"id": "v0", "verdict": "CONFIRMED", "reason": "   ", "evidence": "ran"},
    {"id": "v0", "verdict": "CONFIRMED", "evidence": "ran"},
    {"id": "v0", "verdict": "PLAUSIBLE", "reason": ""},
    {"id": "v0", "verdict": "PLAUSIBLE"},
    {"id": "v0", "verdict": "REFUTED", "reason": ""},
    {"id": "v0", "verdict": "REFUTED", "reason": "   "},
    {"id": "v0", "verdict": "REFUTED"},
    {"id": "v0", "verdict": "REFUTED", "reason": "", "evidence": "sh: vitest: command not found"},
])
def test_g2_an_unknown_or_reasonless_verdict_carries_no_grade(verdict):
    out = _apply(verdict, grade={"verdict": "wrong", "reason": "seat said so"})
    assert out["drops"] == []
    assert len(out["findings"]) == 1
    assert "grade" not in out["findings"][0], out["findings"][0]


def test_reasonless_confirmed_with_a_receipt_is_kept_plausible():
    kept = _apply({"id": "v0", "verdict": "CONFIRMED", "reason": "", "evidence": "ran"})["findings"][0]
    assert kept["verdict"] == "PLAUSIBLE"
    assert "evidence" not in kept


def test_g2_an_ambiguous_id_carries_no_grade():
    findings = TV._stage([TV._f("a.py", "bug", "Important", grade={"verdict": "wrong", "reason": "x"})])
    out = V.apply_verdicts(findings, [
        {"id": "v0", "verdict": "PLAUSIBLE", "reason": "x"},
        {"id": "v0", "verdict": "REFUTED", "reason": "safe"},
    ])
    assert out["ambiguous"] == ["v0"]
    assert "grade" not in out["findings"][0]


def test_g2_an_unmatched_verdict_leaves_the_finding_ungraded():
    out = _apply({"id": "v99", "verdict": "PLAUSIBLE", "reason": "wrong id"})
    assert out["unmatched"] == ["v99"]
    assert "grade" not in out["findings"][0]


def test_a_drop_without_its_grade_key_never_happens_for_a_non_dropped_finding():
    out = _apply({"id": "v0", "verdict": "PLAUSIBLE", "reason": "r"})
    assert out["drops"] == []
    assert set(out) == {"findings", "drops", "downgrades", "unmatched", "unverified", "ambiguous",
                        "notExecuted", "held"}


# ---- the driver fold --------------------------------------------------------------------------

_CONSEQUENCE = "a reviewer-found defect stays in the change"
_CONFIRMED = {"title": "confirmed bug", "severity": "Important", "file": "f.py", "line": 1,
              "consequence": _CONSEQUENCE}
_PLAUSIBLE = {"title": "plausible bug", "severity": "Important", "file": "f.py", "line": 2,
              "consequence": _CONSEQUENCE}
_REFUTED = {"title": "refuted bug", "severity": "Important", "file": "f.py", "line": 3,
            "consequence": _CONSEQUENCE}
_REFUTED_REASON = "the guard at line 40 already returns early on None"
_DIFF = ("diff --git a/f.py b/f.py\nindex 1..2 100644\n--- a/f.py\n+++ b/f.py\n"
         "@@ -1 +1,4 @@\n-old\n+new\n+more\n+most\n+last\n")


def _fold_drive(tmp_path):
    """Drive next/submit with three findings: the verifier CONFIRMS one (with a receipt), finds one PLAUSIBLE
    and REFUTES one. Snapshots the state when the synthesis and the next phase are offered."""
    session_dir = str(tmp_path)
    base = TRD._responder(round1_findings=[dict(_CONFIRMED), dict(_PLAUSIBLE), dict(_REFUTED)])
    snapshots = {}

    def respond(phase, payload, rnd):
        art = base(phase, payload, rnd)
        if phase not in snapshots and phase != RD.P_PANEL:
            ok, state = RD.load_state(session_dir)
            assert ok, state
            snapshots[phase] = state
        if phase == RD.P_VERIFIERS:
            verdicts = []
            for cluster in payload.get("clusters", []):
                for finding, fid in zip(cluster["findings"], cluster["ids"]):
                    if finding["title"] == _CONFIRMED["title"]:
                        verdicts.append({"id": fid, "verdict": "CONFIRMED", "reason": "reproduced",
                                         "evidence": "ran: 1 failed"})
                    elif finding["title"] == _PLAUSIBLE["title"]:
                        verdicts.append({"id": fid, "verdict": "PLAUSIBLE", "reason": "could not run it"})
                    else:
                        verdicts.append({"id": fid, "verdict": "REFUTED", "reason": _REFUTED_REASON})
            ok, state = RD.load_state(session_dir)
            art = {"verdicts": verdicts,
                   "verifierVendor": RD._nonpanel_selection(state, session_dir, phase)[0]}
        return art

    cfg = S1858._cfg()
    cfg.pop("repoRoot")  # the driven session runs in a real checkout
    TRD._drive_cli(session_dir, TRD._cfg(diff=_DIFF, **cfg), respond)
    ok, final = RD.load_state(session_dir)
    assert ok, final
    return snapshots, final


def _ledger(state):
    return {SC.finding_identity_key(e): e for e in state[SC.DISPOSITION_LEDGER_KEY]}


def test_g1_g3_the_driver_fold_grades_every_judged_finding_and_keeps_the_refuted_one_out_of_the_fix(tmp_path):
    snapshots, final = _fold_drive(tmp_path)
    after_verify = snapshots[RD.P_SYNTHESIS]
    keys = {name: SC.finding_identity_key(f) for name, f in
            (("confirmed", _CONFIRMED), ("plausible", _PLAUSIBLE), ("refuted", _REFUTED))}
    ledger = _ledger(after_verify)

    refuted_row = ledger[keys["refuted"]]
    assert refuted_row["disposition"] == "refuted", refuted_row
    _assert_grade(refuted_row["grade"], "wrong", _REFUTED_REASON)
    _assert_grade(ledger[keys["confirmed"]]["grade"], "confirmed", "reproduced")
    _assert_grade(ledger[keys["plausible"]]["grade"], "plausible", "could not run it")
    assert "disposition" not in ledger[keys["confirmed"]] and "disposition" not in ledger[keys["plausible"]]

    verified = {SC.finding_identity_key(f): f for f in after_verify["_verified"]}
    assert set(verified) == {keys["confirmed"], keys["plausible"]}
    _assert_grade(verified[keys["confirmed"]]["grade"], "confirmed", "reproduced")
    _assert_grade(verified[keys["plausible"]]["grade"], "plausible", "could not run it")

    # The refuted finding is in no fix batch: synthesis folded only the survivors into the findings.
    after_synthesis = snapshots[RD.P_FIXER]
    live = {SC.finding_identity_key(f) for f in after_synthesis["findings"]}
    assert keys["refuted"] not in live
    assert live == {keys["confirmed"], keys["plausible"]}
    final_ledger = _ledger(final)
    _assert_grade(final_ledger[keys["refuted"]]["grade"], "wrong", _REFUTED_REASON)
    assert final_ledger[keys["refuted"]]["disposition"] == "refuted"


# ---- a seat-supplied grade is never honored ---------------------------------------------------

_SEAT_GRADE = {"verdict": "wrong", "reason": "x"}


def test_g4_a_panel_seats_own_grade_reaches_neither_to_verify_nor_the_ledger(tmp_path):
    finding = dict(_CONFIRMED, grade=dict(_SEAT_GRADE))
    d = str(tmp_path)
    n = TRD._drive_to_phase(d, TRD._cfg(), TRD._responder(round1_findings=[finding]), RD.P_VERIFIERS)
    ok, state = RD.load_state(d)
    assert ok, state
    assert state["_toVerify"], state
    assert all("grade" not in f for f in state["_toVerify"]), state["_toVerify"]
    ledger_rows = [e for e in state[SC.DISPOSITION_LEDGER_KEY] if isinstance(e, dict)]
    assert ledger_rows
    assert all("grade" not in e for e in ledger_rows), ledger_rows
    for cluster in n["payload"]["clusters"]:
        assert all("grade" not in f for f in cluster["findings"]), cluster


def test_g4_stage_findings_strips_a_seat_grade_from_every_staged_entry():
    state = RD.new_state(TRD._cfg())
    compiled, _ = RD.mechanical_compile([dict(_CONFIRMED, grade=dict(_SEAT_GRADE))], None)
    assert compiled[0].get("grade") == _SEAT_GRADE  # the premise: compile does not strip it
    RD._stage_findings(state, compiled)
    assert all("grade" not in f for f in state["_toVerify"])
    assert all("grade" not in e for e in state[SC.DISPOSITION_LEDGER_KEY])


def test_a_keyless_staged_finding_loses_a_seat_grade_and_seeds_no_ledger_row(monkeypatch):
    state = RD.new_state(TRD._cfg())
    monkeypatch.setattr(RD, "_finding_identity_key", lambda finding: None)
    RD._stage_findings(state, [dict(_CONFIRMED, grade=dict(_SEAT_GRADE))])
    assert len(state["_toVerify"]) == 1
    assert "grade" not in state["_toVerify"][0]
    assert not state.get(SC.DISPOSITION_LEDGER_KEY)


def test_a_same_round_restaging_of_a_refuted_key_keeps_its_closing_grade():
    state = RD.new_state(TRD._cfg())
    compiled, _ = RD.mechanical_compile([dict(_REFUTED)], None)
    RD._stage_findings(state, compiled)
    key = SC.finding_identity_key(compiled[0])
    RD._record_grade(state, key, {"verdict": "wrong", "reason": _REFUTED_REASON})
    RD._record_disposition(state, key, "refuted", state["round"], refutedReason=_REFUTED_REASON)
    RD._stage_findings(state, [dict(c, grade=dict(_SEAT_GRADE)) for c in compiled])
    row = _ledger(state)[key]
    assert row["disposition"] == "refuted"
    _assert_grade(row["grade"], "wrong", _REFUTED_REASON)


def test_a_later_round_restaging_drops_the_closing_grade_with_its_family():
    state = RD.new_state(TRD._cfg())
    compiled, _ = RD.mechanical_compile([dict(_REFUTED)], None)
    RD._stage_findings(state, compiled)
    key = SC.finding_identity_key(compiled[0])
    RD._record_grade(state, key, {"verdict": "wrong", "reason": _REFUTED_REASON})
    RD._record_disposition(state, key, "refuted", state["round"], refutedReason=_REFUTED_REASON)
    state["round"] += 1
    RD._stage_findings(state, compiled)
    row = _ledger(state)[key]
    assert "disposition" not in row
    assert "grade" not in row


# ---- the fold's other edges -------------------------------------------------------------------

def _fold_cfg():
    # A native `claude` seat takes the seat map's hostFamily, so the verdicts fold without a vendor claim.
    return {"leg": "code", "vendors": ["claude", "codex"], "diff": "d", "fixerVendor": "codex",
            "seatMap": {"hostFamily": "anthropic"}}


def test_a_verdict_id_resolving_to_no_staged_finding_writes_no_grade():
    state = RD.new_state(_fold_cfg())
    compiled, _ = RD.mechanical_compile([dict(_CONFIRMED)], None)
    RD._stage_findings(state, compiled)
    before = [dict(e) for e in state[SC.DISPOSITION_LEDGER_KEY]]
    RD._fold_verifiers(state, state["config"], {"verdicts": [
        {"id": "v99", "verdict": "PLAUSIBLE", "reason": "no such staged id"}]})
    assert [e for e in state[SC.DISPOSITION_LEDGER_KEY]] == before
    assert all("grade" not in f for f in state["_verified"])


def test_a_keyless_survivor_keeps_its_grade_on_the_copy_and_writes_no_ledger_row(monkeypatch):
    state = RD.new_state(_fold_cfg())
    compiled, _ = RD.mechanical_compile([dict(_CONFIRMED)], None)
    RD._stage_findings(state, compiled)
    before = [dict(e) for e in state[SC.DISPOSITION_LEDGER_KEY]]
    monkeypatch.setattr(RD, "_finding_identity_key", lambda finding: None)
    RD._fold_verifiers(state, state["config"], {"verdicts": [
        {"id": "v0", "verdict": "PLAUSIBLE", "reason": "could not run it"}]})
    _assert_grade(state["_verified"][0]["grade"], "plausible", "could not run it")
    assert state[SC.DISPOSITION_LEDGER_KEY] == before


def test_the_author_justification_post_filter_refutes_with_no_grade():
    finding = {"file": "aj.py", "line": 2, "title": "style", "severity": "Important",
               "verdict": "PLAUSIBLE", "consequence": _CONSEQUENCE}
    compiled, _ = RD.mechanical_compile([finding], None)
    state = RD.new_state(_fold_cfg())
    RD._stage_findings(state, compiled)
    staged = V.stage_ids(compiled)
    state["_verified"] = staged
    state["config"]["priorComments"] = [
        {"file": "aj.py", "line": 2, "body": "intentional pattern for performance " + ("x" * 40)}]
    RD._fold_synthesis(state, state["config"], {"grouping": [{"group_id": "g0",
                                                               "member_ids": [staged[0]["id"]]}]})
    key = SC.finding_identity_key(staged[0])
    row = _ledger(state)[key]
    assert row["disposition"] == "refuted"
    assert row["refutedReason"].startswith("author-justified: ")
    assert "grade" not in row
