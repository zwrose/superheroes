"""C7 L3 (WO-3), as it stands now that no later round runs a full panel: nothing credits a fix by a later
panel's silence. A finding the build session reported fixed ends `fixed` only on a fix audit's discharge,
and a finished session of an earlier version can still carry the `full-panel-not-reraised` receipt, which
the review record keeps reading.

Drives the real round driver's fold functions (`_stage_findings`, `_fold_apply_fixes`, `_fold_panel`) over
a staged state.

Measured: a `fixes` entry is the orchestrator's git-derived record and names no finding, so the fixer
fold records the identity keys it was handed beside the fix report (`fixReportedKeys`).

The credit step, its raised-closure and reopening cases, and their tests are deleted with the later
panel they belonged to; the bite-proof record c7l3_wo3_driver.md describes the earlier behaviour.
"""
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _p in (_HERE, _LIB):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import session_contract as SC  # noqa: E402
import test_round_driver as TRD  # noqa: E402

RD = TRD.RD  # run_loop runs on test_round_driver's own load of the module

CONSEQUENCE = "users lose their saved work"
RECEIPT = {"kind": SC.FULL_PANEL_NOT_RERAISED, "panelRound": 2}


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


def _fix(state, *, fixes=True, batch=None):
    """The round's apply-fixes report folds. No head diff comes back, so the next round's surface is
    unknown and hands the PR back; the report's keys are recorded all the same."""
    state["_fixBatch"] = [dict(f) for f in (batch if batch is not None else state["findings"])]
    artifact = {"fixes": [{"file": "f.py", "summary": "guard restored"}] if fixes else []}
    RD._fold_apply_fixes(state, state["config"], artifact,
                         changed_subjects_seam=lambda *args: ["Code"],
                         panel_diff_seam=lambda config, head: (TRD.DIFF, None))


def test_the_fixer_fold_records_the_keys_it_was_handed_beside_its_fix_report():
    state = _round_one_state(_finding(), _finding("Other", 2))
    _fix(state)
    assert sorted(state["rounds"]["1"]["fixReportedKeys"]) == sorted([_key(), _key("Other", 2)])
    assert state["rounds"]["1"]["fix"]["fixes"]


def test_a_panel_that_does_not_raise_a_reported_fix_again_credits_nothing():
    """Re-pinned from the later-panel credit tests: no panel runs after round 1, and a panel that did
    fold in a later round (a hand-built state) marks no finding `fixed` by its silence."""
    state = _round_one_state(_finding())
    _fix(state)
    state["round"] = 2
    seats = {dim: {"findings": [], "confidence": "high"} for dim in RD._panel_dimensions(state["config"])}
    RD._fold_panel(state, state["config"], {"seats": seats})
    row = _ledger(state)[_key()]
    assert "disposition" not in row and "dispositionReceipt" not in row


def test_the_driver_has_no_later_panel_credit_step():
    assert not hasattr(RD, "_credit_fixes_not_reraised")
    assert not hasattr(RD, "FULL_PANEL_NOT_RERAISED")


def test_the_receipt_kind_stays_registered_for_the_record_that_reads_a_finished_earlier_session():
    assert SC.FULL_PANEL_NOT_RERAISED == RECEIPT["kind"] == "full-panel-not-reraised"


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
