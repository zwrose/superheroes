"""C7 L3 (WO-3): a finding a fixer reported fixed, that a later COMPLETE full panel did not raise
again, ends `fixed` — never a leftover — provided the fix report came after the finding's latest raise.

Drives the real round driver: the fold functions (`_stage_findings`, `_fold_fixer`, `_fold_panel`) over
a staged state for each edge, and `run_loop` with scripted seams through to a terminal and
`review_record_session.account_from_session` for the vet's case (a converged loop whose fix a later
full panel confirmed, with no fix audit).

Measured: a `fixes` entry is the orchestrator's git-derived record and names no finding, so the credit
keys on the identity keys the fixer fold records beside it (`fixReportedKeys`), never on wording.

Bite-proof record: plugins/superheroes/lib/tests/bite_proofs/c7l3_wo3_driver.md
"""
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _p in (_HERE, _LIB):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import review_record_session as rs  # noqa: E402
import session_contract as SC  # noqa: E402
import test_review_record_session as TRS  # noqa: E402
import test_round_driver as TRD  # noqa: E402

RD = TRD.RD  # run_loop runs on test_round_driver's own load of the module

CONSEQUENCE = "users lose their saved work"
RECEIPT = {"kind": "full-panel-not-reraised", "panelRound": 2}


def _finding(title="Bug", line=1):
    return {"file": "f.py", "line": line, "title": title, "severity": "Important",
            "consequence": CONSEQUENCE, "consequenceKind": "real"}


def _key(title="Bug", line=1):
    return "f.py::%s@L%d" % (title.lower(), line)


def _ledger(state):
    return {SC.finding_identity_key(e): e for e in state.get(SC.DISPOSITION_LEDGER_KEY) or []}


def _round_one_state(*findings):
    """A state at the end of round 1: the findings staged, verified and live."""
    state = RD.new_state(TRD._cfg_cert())
    compiled, _ = RD.mechanical_compile([dict(f) for f in findings], TRD.DIFF)
    RD._stage_findings(state, compiled)
    RD._set_findings(state, state["_toVerify"])
    return state


def _fix(state, *, fixes=True, escalated=False, batch=None):
    """The round's fixer folds. No head diff comes back, so the next round is a full panel over the
    git-derived diff (no fix audit sits between the fix and the panel)."""
    state["_fixBatch"] = [dict(f) for f in (batch if batch is not None else state["findings"])]
    artifact = {"fixes": [{"file": "f.py", "summary": "guard restored"}] if fixes else [],
                "escalated": escalated}
    RD._fold_fixer(state, state["config"], artifact,
                   changed_subjects_seam=lambda *args: ["Code"],
                   panel_diff_seam=lambda config, head: (TRD.DIFF, None))


def _panel(state, raised=(), missing=()):
    """Fold a full panel at the state's round: every dimension runs but `missing`, and the code
    reviewer raises `raised`."""
    seats = {dim: {"findings": [], "confidence": "high"}
             for dim in RD._panel_dimensions(state["config"]) if dim not in missing}
    seats["code-reviewer"]["findings"] = [dict(f) for f in raised]
    RD._fold_panel(state, state["config"], {"seats": seats})


def _credited(state, key):
    row = _ledger(state)[key]
    return row.get("disposition") == "fixed" and row.get("dispositionReceipt") == RECEIPT


def test_a_fix_a_later_complete_panel_did_not_raise_again_is_fixed():
    state = _round_one_state(_finding())
    _fix(state)
    assert state["round"] == 2
    assert "disposition" not in _ledger(state)[_key()]
    _panel(state)
    row = _ledger(state)[_key()]
    assert row["disposition"] == "fixed"
    assert row["dispositionRound"] == 2
    assert row["dispositionReceipt"] == RECEIPT


def test_the_fixer_fold_records_the_keys_it_was_handed_beside_its_fix_report():
    state = _round_one_state(_finding(), _finding("Other", 2))
    _fix(state)
    assert sorted(state["rounds"]["1"]["fixReportedKeys"]) == sorted([_key(), _key("Other", 2)])
    assert state["rounds"]["1"]["fix"]["fixes"]


def test_an_incomplete_panel_gives_no_credit():
    """axis: only a complete panel can confirm a fix by silence — an incomplete one may simply not have
    looked — see bite-proof record c7l3_wo3_driver"""
    state = _round_one_state(_finding())
    _fix(state)
    absent = next(d for d in RD._panel_dimensions(state["config"]) if d != "code-reviewer")
    _panel(state, missing=(absent,))
    assert state["fullPanelRan"] is False
    row = _ledger(state)[_key()]
    assert "disposition" not in row and "dispositionReceipt" not in row


def test_a_first_round_panel_gives_no_credit():
    state = _round_one_state(_finding())
    # a fix report that names the finding, held at round 1: nothing earlier than round 1 exists
    state["rounds"].setdefault("1", {})["fix"] = {"fixes": [{"file": "f.py"}], "escalated": False}
    state["rounds"]["1"]["fixReportedKeys"] = [_key()]
    _panel(state)
    assert state["round"] == 1
    assert "disposition" not in _ledger(state)[_key()]


def test_a_finding_the_panel_raises_again_gets_no_credit():
    state = _round_one_state(_finding())
    _fix(state)
    _panel(state, raised=[_finding()])
    row = _ledger(state)[_key()]
    assert "disposition" not in row and "dispositionReceipt" not in row
    assert row["raisedRound"] == 2


def test_a_fix_reported_before_the_latest_raise_gives_no_credit():
    """axis: a fix report made before the finding's latest raise says nothing about the raise after
    it — see bite-proof record c7l3_wo3_driver"""
    state = _round_one_state(_finding())
    _fix(state)                                   # fix reported in round 1
    _panel(state, raised=[_finding()])            # raised again in round 2
    state["round"] = 3                            # round 3's panel omits it; round 2 fixed nothing
    state["rounds"].setdefault("3", {})
    _panel(state)
    row = _ledger(state)[_key()]
    assert row["raisedRound"] == 2
    assert "disposition" not in row and "dispositionReceipt" not in row


def test_a_fix_reported_after_the_latest_raise_is_credited_by_the_next_complete_panel():
    state = _round_one_state(_finding())
    _fix(state)
    _panel(state, raised=[_finding()])            # raised again in round 2
    state["_fixBatch"] = [dict(f) for f in state["findings"]]
    _fix(state)                                   # fixed again in round 2 (after the re-raise)
    assert state["round"] == 3
    _panel(state)
    assert _ledger(state)[_key()]["disposition"] == "fixed"
    assert _ledger(state)[_key()]["dispositionReceipt"] == dict(RECEIPT, panelRound=3)


def test_an_escalated_fix_report_gives_no_credit():
    state = _round_one_state(_finding())
    _fix(state, escalated=True)
    _panel(state)
    assert "disposition" not in _ledger(state)[_key()]


def test_a_fix_report_with_no_fixes_gives_no_credit():
    state = _round_one_state(_finding())
    _fix(state, fixes=False)
    _panel(state)
    assert "disposition" not in _ledger(state)[_key()]


def test_a_finding_the_fixer_was_not_handed_gets_no_credit():
    state = _round_one_state(_finding(), _finding("Other", 2))
    _fix(state, batch=[f for f in _round_one_state(_finding())["findings"]])
    _panel(state)
    ledger = _ledger(state)
    assert ledger[_key()]["disposition"] == "fixed"
    assert "disposition" not in ledger[_key("Other", 2)]


def test_a_finding_that_already_has_a_current_disposition_is_unchanged():
    state = _round_one_state(_finding())
    _fix(state)
    RD._record_disposition(state, _key(), "fixed", 2, dispositionReceipt={"headSha": "abc"})
    before = dict(_ledger(state)[_key()])
    _panel(state)
    assert _ledger(state)[_key()] == before
    assert before["dispositionReceipt"] == {"headSha": "abc"}


def test_a_finding_merged_into_another_is_skipped_and_its_representative_is_credited():
    state = _round_one_state(_finding(), _finding("Twin", 2))
    RD._record_merged_into(state, _key("Twin", 2), _key())
    _fix(state)
    _panel(state)
    ledger = _ledger(state)
    assert ledger[_key()]["disposition"] == "fixed"
    assert "disposition" not in ledger[_key("Twin", 2)]


def test_an_out_of_scope_ruling_is_not_overwritten():
    state = _round_one_state(_finding())
    RD._record_disposition(state, _key(), "out-of-scope", 1, outOfScopeReason="a later change")
    _fix(state)
    _panel(state)
    assert _ledger(state)[_key()]["disposition"] == "out-of-scope"


def test_a_credited_finding_is_not_settled_as_a_leftover():
    state = _round_one_state(_finding())
    _fix(state)
    _panel(state)
    RD._set_terminal(state, "converged")
    row = _ledger(state)[_key()]
    assert row["disposition"] == "fixed"
    assert "settledReason" not in row


def _fixed_without_audit_seams():
    """A loop whose fixer reports a fix and returns no head diff: the next round is a full panel,
    which does not raise the finding again."""
    def reviewer(dim, tier, rnd, ctx):
        return [_finding()] if rnd == 1 and dim == "code-reviewer" else []

    def fix_step(batch, rnd, payload):
        return {"fixes": [{"file": "f.py", "summary": "guard restored"}],
                "changedSubjects": ["Code"]}

    seams = TRD._seams(reviewer=reviewer, fix_step=fix_step)
    seams["panel_diff"] = lambda config, head: (TRD.HEAD, None)
    return seams


def test_a_converged_loop_whose_fix_a_later_full_panel_confirmed_reports_it_fixed(tmp_path):
    result, state = TRD._run_loop_capturing_state(_fixed_without_audit_seams(), TRD._cfg_cert())
    assert state["terminal"] == "converged", state.get("certification")
    assert state["fullPanelRan"] is True
    assert not state.get("auditRounds")             # no fix audit ran
    row = _ledger(state)[_key()]
    assert row["disposition"] == "fixed" and row["dispositionReceipt"] == RECEIPT

    session = TRS.Session(tmp_path, **state).seat("code-reviewer")
    account = rs.account_from_session(session.save(), TRS.extras(), TRS.Fake().readers())
    outcomes = {f["findingKey"]: f["outcome"] for f in account["findings"]}
    assert outcomes == {_key(): "fixed"}


def test_a_reraised_member_of_a_merged_group_withholds_the_representatives_credit():
    state = _round_one_state(_finding(), _finding("Twin", 2))
    RD._record_merged_into(state, _key(), _key("Twin", 2))
    _fix(state, batch=[f for f in state["findings"] if f["title"] == "Twin"])
    _panel(state, raised=[_finding()])
    assert "disposition" not in _ledger(state)[_key("Twin", 2)]


def test_a_reraise_the_compile_drops_gets_no_credit():
    state = _round_one_state(_finding())
    _fix(state)
    no_consequence = {k: v for k, v in _finding().items() if k != "consequence"}
    _panel(state, raised=[no_consequence])
    assert not _credited(state, _key())


def test_the_receipt_kind_has_one_home_read_by_writer_and_record():
    assert RD.FULL_PANEL_NOT_RERAISED == SC.FULL_PANEL_NOT_RERAISED == RECEIPT["kind"]


def test_state_and_mirror_land_in_one_commit(tmp_path, monkeypatch):
    """A stop after the commit seals leaves neither file written; recovery replays both."""
    d = str(tmp_path)
    state = RD.new_state(TRD._cfg_cert())
    real_begin = RD.round_commit.begin
    monkeypatch.setattr(RD.round_commit, "begin",
                        lambda *a, **k: real_begin(*a, stop_at="sealed", **k))
    with pytest.raises(RD.round_commit.StopPoint):
        RD.save_state(d, state)
    assert not os.path.exists(os.path.join(d, RD.STATE_FILE))
    assert not os.path.exists(os.path.join(d, RD.MIRROR_FILE))
    RD.round_commit.recover(d)
    assert os.path.exists(os.path.join(d, RD.STATE_FILE))
    assert os.path.exists(os.path.join(d, RD.MIRROR_FILE))
