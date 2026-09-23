"""#1272 layer 3: terminal condition — discharged exclusion, empty-batch convergence, delta base."""
import importlib.util
import os
import re
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_LIB, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


RD = _load("round_driver")
SC = _load("session_contract")

_BASE_DIFF = (
    "diff --git a/f.py b/f.py\nindex 1..2 100644\n--- a/f.py\n+++ b/f.py\n"
    "@@ -1 +1 @@\n-old base\n+new base\n"
)
_HEAD_DIFF = (
    "diff --git a/f.py b/f.py\nindex 2..3 100644\n--- a/f.py\n+++ b/f.py\n"
    "@@ -1 +1 @@\n-new base\n+head line\n"
)


def _cfg(**over):
    base = {"leg": "code", "vendors": ["claude", "codex"], "diff": _BASE_DIFF,
            "fixerVendor": "codex"}
    base.update(over)
    return base


def _finding():
    return {"file": "f.py", "line": 1, "title": "bug", "severity": "Important"}


def _compile_one(finding=None):
    finding = finding or _finding()
    compiled, _ = RD.mechanical_compile([finding], None)
    return compiled[0], SC.finding_identity_key(compiled[0])


def _ledger_by_key(state):
    return {SC.finding_identity_key(e): e
            for e in (state.get("dispositionLedger") or []) if isinstance(e, dict)}


def _fix_row(compiled_row):
    return dict(compiled_row)


def _stage_and_discharge(state, round_no=1):
    compiled, key = _compile_one()
    state["round"] = round_no
    RD._stage_findings(state, [compiled])
    RD._record_disposition(state, key, "fixed", round_no,
                           dispositionReceipt={"headSha": "a" * 40})
    return compiled, key


# --- A1: exclusion chokepoint -------------------------------------------------

def test_l3_a1_excludes_discharged_row():
    """axis: stamped ledger row with dispositionSeq > raisedSeq is excluded."""
    state = RD.new_state(_cfg())
    compiled, key = _stage_and_discharge(state)
    config = _cfg()
    RD._queue_fix_batch(state, config, [_fix_row(compiled)])
    assert state.get("_fixBatch") in (None, [])
    assert state["step"] != RD.P_FIXER


def test_l3_a1_mixed_batch_keeps_the_open_row():
    state = RD.new_state(_cfg())
    discharged, _ = _stage_and_discharge(state)
    open_compiled, _ = _compile_one(
        {"file": "g.py", "line": 2, "title": "open", "severity": "Important"})
    RD._stage_findings(state, [open_compiled])
    config = _cfg()
    RD._queue_fix_batch(state, config, [_fix_row(discharged), _fix_row(open_compiled)])
    assert [r["title"] for r in state["_fixBatch"]] == ["open"]
    assert state["step"] == RD.P_FIXER
    assert not any(d["kind"] == "fix-batch-excluded" for d in state["decisions"])


def test_l3_a1_mixed_batch_continuation_keeps_the_open_row():
    state = RD.new_state(_cfg())
    discharged, _ = _stage_and_discharge(state)
    open_compiled, _ = _compile_one(
        {"file": "g.py", "line": 2, "title": "open", "severity": "Important"})
    RD._stage_findings(state, [open_compiled])
    state["fixBatch"] = [{"title": "prior slice"}]
    config = _cfg()
    RD._queue_fix_batch(
        state, config, [_fix_row(discharged), _fix_row(open_compiled)],
        reset_accumulator=False, batch_index=1)
    assert [r["title"] for r in state["_fixBatch"]] == ["open"]
    assert state["step"] == RD.P_FIXER
    assert not any(d["kind"] == "fix-batch-excluded" for d in state["decisions"])


def test_l3_a1_same_round_reraise_stays_in_batch():
    finding = _finding()
    compiled, _ = _compile_one(finding)
    state = RD.new_state(_cfg())
    state["round"] = 2
    key = SC.finding_identity_key(compiled)
    RD._stage_findings(state, [compiled])
    RD._record_disposition(state, key, "fixed", 2,
                           dispositionReceipt={"headSha": "b" * 40})
    RD._stage_findings(state, [compiled])
    entry = _ledger_by_key(state)[key]
    assert entry.get("dispositionSeq", 0) <= entry.get("raisedSeq", 0)
    config = _cfg()
    RD._queue_fix_batch(state, config, [_fix_row(compiled)])
    assert state["_fixBatch"]
    assert state["step"] == RD.P_FIXER


@pytest.mark.parametrize("reraise_round", [1, 2])
def test_l3_a1_caller_supplied_sequence_stamps_stripped_on_reraise(reraise_round):
    """axis: model-authored raisedSeq/dispositionSeq on re-raise cannot suppress a live blocker."""
    finding = _finding()
    state = RD.new_state(_cfg())
    compiled, key = _compile_one(finding)
    state["round"] = 1
    RD._stage_findings(state, [compiled])
    RD._record_disposition(state, key, "fixed", 1,
                           dispositionReceipt={"headSha": "d" * 40})
    state["round"] = reraise_round
    poisoned, _ = RD.mechanical_compile(
        [dict(finding, dispositionSeq=999, raisedSeq=888)])
    RD._stage_findings(state, [poisoned[0]])
    entry = _ledger_by_key(state)[key]
    assert "dispositionSeq" not in entry
    assert entry["raisedSeq"] != 888
    config = _cfg()
    status = RD._queue_fix_batch(state, config, [_fix_row(poisoned[0])])
    assert status == "queued"
    assert state.get("_fixBatch")
    assert state["step"] == RD.P_FIXER


def test_l3_a1_backfill_strips_record_sequence_stamps():
    """axis: backfill must not retain model-authored raisedSeq/dispositionSeq from _records."""
    poisoned = {"file": "o", "line": 1, "title": "old", "severity": "Important",
                "raisedSeq": 888, "dispositionSeq": 999,
                SC.FINDING_KEY_FIELD: "o::old@L1"}
    new_raw = {"file": "n", "line": 2, "title": "new", "severity": "Minor"}
    compiled, _ = RD.mechanical_compile([new_raw], None)
    state = RD.new_state(_cfg())
    state["round"] = 2
    state["_records"] = [{"findings": [poisoned]}]
    RD._stage_findings(state, compiled)
    ledger = _ledger_by_key(state)
    assert "o::old@L1" in ledger
    entry = ledger["o::old@L1"]
    assert "dispositionSeq" not in entry
    assert entry.get("raisedSeq") != 888


def test_l3_a1_surfaced_critical_after_exclusion_rearms_confirmation():
    """axis: delta empty-batch exclusion must re-arm when Critical is still owed."""
    state = RD.new_state(_cfg())
    state["round"] = 2
    state["rounds"] = {"2": {"roundKind": "delta"}}
    state["confirmations"] = 0
    state["surfacedSinceLastPanel"] = ["Critical"]
    discharged, discharged_key = _compile_one(
        {"file": "f.py", "line": 1, "title": "mechanical", "severity": "Important"})
    RD._stage_findings(state, [discharged])
    RD._record_disposition(state, discharged_key, "fixed", 2,
                           dispositionReceipt={"headSha": "f" * 40})
    tradeoff, tradeoff_key = _compile_one(
        {"file": "g.py", "line": 2, "title": "widen API", "severity": "Critical",
         "tradeoff": True})
    RD._stage_findings(state, [tradeoff])
    batch = [_fix_row(discharged), _fix_row(tradeoff)]
    config = _cfg()
    assert RD._route_judgment_blockers(state, batch)
    row_id = RD._judgment_row_ids(state["_judgmentFindings"])[0]
    RD._fold_judgment(state, config, {"dispositions": [
        {"id": row_id, "disposition": "skip", "reason": "owner accepts tradeoff"},
    ]})
    assert state["step"] == RD.P_PANEL
    assert state.get("terminal") is None
    assert state["rounds"]["2"]["confirmationFollowup"]["rearm"] is True


def test_l3_a1_edge_ledger_absent_no_exclusion():
    state = RD.new_state(_cfg())
    compiled, _ = _stage_and_discharge(state)
    state.pop("dispositionLedger", None)
    state.pop(SC.DISPOSITION_LEDGER_OWNER_FIELD, None)
    config = _cfg()
    RD._queue_fix_batch(state, config, [_fix_row(compiled)])
    assert state["_fixBatch"]
    assert state["step"] == RD.P_FIXER


def test_l3_a1_edge_malformed_ledger_parks_before_fixer():
    compiled, key = _compile_one()
    state = RD.new_state(_cfg())
    state["round"] = 1
    RD._stage_findings(state, [compiled])
    RD._record_disposition(state, key, "fixed", 1,
                           dispositionReceipt={"headSha": "c" * 40})
    state["dispositionLedger"] = "not-a-list"
    config = _cfg()
    RD._queue_fix_batch(state, config, [_fix_row(compiled)])
    assert state.get("_fixBatch") in (None, [])
    assert state["step"] == RD.P_TERMINAL
    assert state["terminal"] == "cannot-certify"
    assert any(d["kind"] == "cannot-certify" for d in state["decisions"])


def test_l3_a1_edge_no_identity_key_no_exclusion():
    row = {"title": "no location", "severity": "Important"}
    state = RD.new_state(_cfg())
    state["round"] = 1
    config = _cfg()
    RD._queue_fix_batch(state, config, [row])
    assert state["_fixBatch"] == [row]
    assert state["step"] == RD.P_FIXER


def test_l3_a1_legacy_stamp_less_fixed_row_stays_in_batch():
    """axis: legacy ledger row with disposition fixed but no sequence stamps stays in batch."""
    compiled, key = _compile_one()
    state = RD.new_state(_cfg())
    state["round"] = 1
    RD._stage_findings(state, [compiled])
    entry = _ledger_by_key(state)[key]
    entry["disposition"] = "fixed"
    entry.pop("raisedSeq", None)
    entry.pop("dispositionSeq", None)
    config = _cfg()
    RD._queue_fix_batch(state, config, [_fix_row(compiled)])
    assert state["_fixBatch"]
    assert state["step"] == RD.P_FIXER


def test_l3_a1_edge_disposition_seq_without_raised_seq_no_exclusion():
    compiled, key = _compile_one()
    state = RD.new_state(_cfg())
    state["round"] = 1
    RD._stage_findings(state, [compiled])
    entry = _ledger_by_key(state)[key]
    entry.pop("raisedSeq", None)
    entry["disposition"] = "fixed"
    entry["dispositionSeq"] = 99
    config = _cfg()
    RD._queue_fix_batch(state, config, [_fix_row(compiled)])
    assert state["_fixBatch"]
    assert state["step"] == RD.P_FIXER


def test_l3_a1_edge_disposition_seq_not_after_raise_no_exclusion():
    compiled, key = _compile_one()
    state = RD.new_state(_cfg())
    state["round"] = 1
    RD._stage_findings(state, [compiled])
    entry = _ledger_by_key(state)[key]
    entry["disposition"] = "fixed"
    entry["dispositionSeq"] = entry["raisedSeq"]
    config = _cfg()
    RD._queue_fix_batch(state, config, [_fix_row(compiled)])
    assert state["_fixBatch"]
    assert state["step"] == RD.P_FIXER


def test_l3_a1_edge_non_fixed_disposition_no_exclusion():
    compiled, key = _compile_one()
    state = RD.new_state(_cfg())
    state["round"] = 1
    RD._stage_findings(state, [compiled])
    entry = _ledger_by_key(state)[key]
    entry["disposition"] = "refuted"
    entry["dispositionSeq"] = entry["raisedSeq"] + 10
    config = _cfg()
    RD._queue_fix_batch(state, config, [_fix_row(compiled)])
    assert state["_fixBatch"]
    assert state["step"] == RD.P_FIXER


def test_l3_a1_fix_batch_single_writer_census():
    path = os.path.join(_LIB, "round_driver.py")
    with open(path, encoding="utf-8") as fh:
        src = fh.read()
    count = len(re.findall(r'state\["_fixBatch"\]\s*=', src))
    assert count == 1


# --- A2: empty-after-filter convergence ---------------------------------------

def test_l3_a2_empty_batch_converges_on_the_paths_own_resolver():
    state = RD.new_state(_cfg())
    state["round"] = 2
    state["rounds"] = {"2": {"roundKind": "delta"}}
    state["surfacedSinceLastPanel"] = []
    state["confirmations"] = 0
    compiled, _ = _stage_and_discharge(state, round_no=2)
    config = _cfg()
    RD._queue_fix_batch(state, config, [_fix_row(compiled)])
    assert state["step"] != RD.P_FIXER
    assert state["rounds"]["2"].get("confirmationFollowup") is not None
    assert any(d["kind"] == "fix-batch-excluded" for d in state["decisions"])


def test_l3_a2_main_path_empty_batch_reaches_terminal():
    state = RD.new_state(_cfg())
    state["round"] = 1
    state["rounds"] = {"1": {}}
    compiled, _ = _stage_and_discharge(state, round_no=1)
    config = _cfg()
    RD._queue_fix_batch(state, config, [_fix_row(compiled)])
    assert state["step"] == RD.P_TERMINAL
    assert state["terminal"] == "converged"


def test_l3_a2_control_open_blocker_reaches_fixer():
    compiled, _ = _compile_one()
    state = RD.new_state(_cfg())
    state["round"] = 1
    state["rounds"] = {"1": {}}
    RD._stage_findings(state, [compiled])
    config = _cfg()
    RD._queue_fix_batch(state, config, [_fix_row(compiled)])
    assert state["step"] == RD.P_FIXER
    assert state["_fixBatch"]


def test_l3_a2_excluded_continuation_enters_post_fix_verify_and_audits():
    state = RD.new_state(_cfg())
    discharged, _ = _stage_and_discharge(state)
    open_compiled, _ = _compile_one(
        {"file": "g.py", "line": 2, "title": "open", "severity": "Important"})
    RD._stage_findings(state, [open_compiled])
    state["round"] = 1
    state["rounds"] = {"1": {}}
    state["_fixBatch"] = [_fix_row(open_compiled)]
    state["_fixQueue"] = [_fix_row(discharged)]
    state["_fixBatchIndex"] = 0
    state["decisions"] = []
    config = _cfg()
    RD._fold_fixer(state, config, {"fixes": [], "headDiff": _HEAD_DIFF})
    assert state["step"] == RD.P_AUDITS
    assert state["round"] == 2
    assert state["_verifyThen"] == RD.VERIFY_THEN_POST_AUDITS
    assert state["terminal"] is None
    assert state["rounds"]["2"]["roundKind"] == "delta"
    audit_targets = [(t["file"], t["line"]) for t in state["_auditTargets"]]
    assert audit_targets == [("g.py", 2)]
    assert not any(d["kind"] == "converged" for d in state["decisions"])
    assert not any(d["kind"] == "fix-batch-split" for d in state["decisions"])
    excluded = [d for d in state["decisions"] if d["kind"] == "fix-batch-excluded"]
    assert len(excluded) == 1
    assert state["rounds"]["1"]["fixBatchExcludedByDischarge"] == 1


def test_l3_a2_excluded_count_accumulates_across_slices():
    state = RD.new_state(_cfg(fixBatchCap=1))
    discharged_a, _ = _stage_and_discharge(state)
    discharged_b, key_b = _compile_one(
        {"file": "h.py", "line": 3, "title": "gone", "severity": "Important"})
    RD._stage_findings(state, [discharged_b])
    RD._record_disposition(state, key_b, "fixed", 1,
                           dispositionReceipt={"headSha": "d" * 40})
    open_compiled, _ = _compile_one(
        {"file": "g.py", "line": 2, "title": "open", "severity": "Important"})
    RD._stage_findings(state, [open_compiled])
    state["round"] = 1
    state["rounds"] = {"1": {}}
    config = _cfg(fixBatchCap=1)
    RD._queue_fix_batch(state, config, [_fix_row(discharged_a)])
    assert state["rounds"]["1"]["fixBatchExcludedByDischarge"] == 1
    state["terminal"] = None
    RD._queue_fix_batch(state, config, [_fix_row(open_compiled)])
    assert state["_fixBatch"] == [_fix_row(open_compiled)]
    assert state["step"] == RD.P_FIXER
    state["_fixQueue"] = [_fix_row(discharged_b)]
    state["_fixBatchIndex"] = 0
    state["decisions"] = []
    RD._fold_fixer(state, config, {"fixes": [], "headDiff": _HEAD_DIFF})
    assert state["rounds"]["1"]["fixBatchExcludedByDischarge"] == 2


def test_l3_a2_continuation_ledger_fault_parks():
    state = RD.new_state(_cfg())
    discharged, _ = _stage_and_discharge(state)
    open_compiled, _ = _compile_one(
        {"file": "g.py", "line": 2, "title": "open", "severity": "Important"})
    RD._stage_findings(state, [open_compiled])
    state["round"] = 1
    state["rounds"] = {"1": {}}
    state["_fixBatch"] = [_fix_row(open_compiled)]
    state["_fixQueue"] = [_fix_row(discharged)]
    state["_fixBatchIndex"] = 0
    state["dispositionLedger"] = "not-a-list"
    state["decisions"] = []
    config = _cfg()
    RD._fold_fixer(state, config, {"fixes": [], "headDiff": _HEAD_DIFF})
    assert state["step"] == RD.P_TERMINAL
    assert state["terminal"] == "cannot-certify"
    assert state["round"] != 2
    assert state.get("_verifyThen") != RD.VERIFY_THEN_POST_AUDITS


def test_l3_a2_fold_fixer_queued_continuation_records_one_split():
    open_a, _ = _compile_one(
        {"file": "a.py", "line": 1, "title": "a", "severity": "Important"})
    open_b, _ = _compile_one(
        {"file": "b.py", "line": 2, "title": "b", "severity": "Important"})
    state = RD.new_state(_cfg(fixBatchCap=1))
    state["round"] = 1
    state["rounds"] = {"1": {}}
    RD._stage_findings(state, [open_a, open_b])
    state["_fixBatch"] = [_fix_row(open_a)]
    state["_fixQueue"] = [_fix_row(open_b)]
    state["_fixBatchIndex"] = 0
    state["decisions"] = []
    config = _cfg(fixBatchCap=1)
    RD._fold_fixer(state, config, {"fixes": [], "headDiff": _HEAD_DIFF})
    splits = [d for d in state["decisions"] if d["kind"] == "fix-batch-split"]
    assert len(splits) == 1
    assert state["step"] == RD.P_FIXER


# --- A3: delta split reads per-round reviewed baseline ------------------------

def _mk_diff(sections):
    parts = []
    for path, body in sections:
        parts.extend([
            "diff --git a/%s b/%s" % (path, path),
            "index 1111111..2222222 100644",
            "--- a/%s" % path,
            "+++ b/%s" % path,
            body,
        ])
    return "\n".join(parts) + "\n"


def _fix_batch():
    return [{"file": "f.py", "line": 1, "title": "bug", "severity": "Important"}]


def _assert_delta_baseline_refusal(state):
    assert state["rounds"]["2"]["roundKind"] == "full-panel-unknown-surface"
    assert state["step"] == RD.P_PANEL
    unknown = [d for d in state["decisions"] if d["kind"] == "unknown-surface"]
    assert len(unknown) == 1
    assert unknown[0]["detail"].startswith(RD.DELTA_BASELINE_ABSENT)


def test_l3_a3_delta_split_reads_per_round_reviewed_diff(monkeypatch):
    captured = {}
    real_split = RD.delta_surface.split_fix_surface

    def _capture_split(reviewed, head, fix_batch):
        captured["reviewed"] = reviewed
        return real_split(reviewed, head, fix_batch)

    monkeypatch.setattr(RD.delta_surface, "split_fix_surface", _capture_split)
    state = RD.new_state(_cfg(diff=_BASE_DIFF))
    state["round"] = 2
    state["deltaBaseline"] = {"round": 2, "diff": _HEAD_DIFF}
    state["reviewedDiff"] = _HEAD_DIFF
    state["headDiff"] = _HEAD_DIFF
    state["fixBatch"] = _fix_batch()
    RD._enter_delta_round(state, _cfg(diff=_BASE_DIFF))
    assert captured["reviewed"] == _HEAD_DIFF
    assert captured["reviewed"] != _BASE_DIFF


def test_l3_a3_absent_baseline_refuses_to_scope_with_named_reason(monkeypatch):
    def _split_must_not_run(*_args, **_kwargs):
        raise AssertionError("split_fix_surface must not run when baseline is absent")

    monkeypatch.setattr(RD.delta_surface, "split_fix_surface", _split_must_not_run)
    state = RD.new_state(_cfg(diff=_BASE_DIFF))
    state["round"] = 2
    state["reviewedDiff"] = _HEAD_DIFF
    state["headDiff"] = _HEAD_DIFF
    state["fixBatch"] = _fix_batch()
    RD._enter_delta_round(state, _cfg(diff=_BASE_DIFF))
    _assert_delta_baseline_refusal(state)


def test_l3_a3_stale_round_baseline_refuses(monkeypatch):
    def _split_must_not_run(*_args, **_kwargs):
        raise AssertionError("split_fix_surface must not run when baseline round is stale")

    monkeypatch.setattr(RD.delta_surface, "split_fix_surface", _split_must_not_run)
    state = RD.new_state(_cfg(diff=_BASE_DIFF))
    state["round"] = 2
    state["deltaBaseline"] = {"round": 1, "diff": _BASE_DIFF}
    state["reviewedDiff"] = _HEAD_DIFF
    state["headDiff"] = _HEAD_DIFF
    state["fixBatch"] = _fix_batch()
    RD._enter_delta_round(state, _cfg(diff=_BASE_DIFF))
    _assert_delta_baseline_refusal(state)


def test_l3_a3_non_record_baseline_refuses(monkeypatch):
    def _split_must_not_run(*_args, **_kwargs):
        raise AssertionError("split_fix_surface must not run when baseline is not a record")

    monkeypatch.setattr(RD.delta_surface, "split_fix_surface", _split_must_not_run)
    state = RD.new_state(_cfg(diff=_BASE_DIFF))
    state["round"] = 2
    state["deltaBaseline"] = ["x"]
    state["reviewedDiff"] = _HEAD_DIFF
    state["headDiff"] = _HEAD_DIFF
    state["fixBatch"] = _fix_batch()
    RD._enter_delta_round(state, _cfg(diff=_BASE_DIFF))
    _assert_delta_baseline_refusal(state)


def test_l3_a3_empty_text_baseline_is_a_valid_baseline(monkeypatch):
    captured = {}
    real_split = RD.delta_surface.split_fix_surface

    def _capture_split(reviewed, head, fix_batch):
        captured["reviewed"] = reviewed
        return real_split(reviewed, head, fix_batch)

    monkeypatch.setattr(RD.delta_surface, "split_fix_surface", _capture_split)
    state = RD.new_state(_cfg(diff=_BASE_DIFF))
    state["round"] = 2
    state["deltaBaseline"] = {"round": 2, "diff": ""}
    state["reviewedDiff"] = _HEAD_DIFF
    state["headDiff"] = _HEAD_DIFF
    state["fixBatch"] = _fix_batch()
    RD._enter_delta_round(state, _cfg(diff=_BASE_DIFF))
    assert captured["reviewed"] == ""
    assert state["rounds"]["2"]["roundKind"] != "full-panel-unknown-surface"


def test_l3_a3_non_text_baseline_refuses(monkeypatch):
    def _split_must_not_run(*_args, **_kwargs):
        raise AssertionError("split_fix_surface must not run when baseline diff is not text")

    monkeypatch.setattr(RD.delta_surface, "split_fix_surface", _split_must_not_run)
    state = RD.new_state(_cfg(diff=_BASE_DIFF))
    state["round"] = 2
    state["deltaBaseline"] = {"round": 2, "diff": None}
    state["reviewedDiff"] = _HEAD_DIFF
    state["headDiff"] = _HEAD_DIFF
    state["fixBatch"] = _fix_batch()
    RD._enter_delta_round(state, _cfg(diff=_BASE_DIFF))
    _assert_delta_baseline_refusal(state)


def test_l3_a3_post_fix_absent_baseline_runs_verify_then_panel(monkeypatch):
    def _split_must_not_run(*_args, **_kwargs):
        raise AssertionError("split_fix_surface must not run when baseline is absent")

    monkeypatch.setattr(RD.delta_surface, "split_fix_surface", _split_must_not_run)
    state = RD.new_state(_cfg(diff=_BASE_DIFF))
    state["round"] = 2
    state["reviewedDiff"] = _HEAD_DIFF
    state["headDiff"] = _HEAD_DIFF
    state["fixBatch"] = _fix_batch()
    state["_postFixEntry"] = True
    RD._enter_delta_round(state, _cfg(diff=_BASE_DIFF))
    assert state["step"] == RD.P_VERIFY
    assert state["_verifyThen"] == RD.VERIFY_THEN_PANEL


def test_l3_a3_advance_round_writes_the_baseline_before_the_head_overwrite(monkeypatch):
    diff_x = _BASE_DIFF
    diff_y = _HEAD_DIFF
    captured = {}
    real_split = RD.delta_surface.split_fix_surface

    def _capture_split(reviewed, head, fix_batch):
        captured["reviewed"] = reviewed
        return real_split(reviewed, head, fix_batch)

    monkeypatch.setattr(RD.delta_surface, "split_fix_surface", _capture_split)
    state = RD.new_state(_cfg(diff=diff_x))
    state["round"] = 1
    state["reviewedDiff"] = diff_x
    state["headDiff"] = diff_y
    state["fixBatch"] = _fix_batch()
    RD._enter_post_fix(state, _cfg(diff=diff_x))
    assert state["deltaBaseline"] == {"round": 2, "diff": diff_x}
    assert state["reviewedDiff"] == diff_y
    assert captured["reviewed"] == diff_x
    assert state["rounds"]["2"]["roundKind"] == "delta"


def test_l3_a3_ceiling_refusal_writes_no_baseline():
    state = RD.new_state(_cfg(maxRoundsAbsolute=1, maxRounds=1))
    state["round"] = 1
    assert RD._advance_round(state, _cfg(maxRoundsAbsolute=1, maxRounds=1),
                             reason="test-ceiling") is False
    assert "deltaBaseline" not in state


def test_l3_a3_second_fix_scoped_surface_excludes_first_fix_unchanged_hunk():
    base = _mk_diff([
        ("a.py", "@@ -1 +1 @@\n-a\n+b"),
        ("b.py", "@@ -1 +1 @@\n-x\n+y"),
    ])
    after_first_fix = _mk_diff([
        ("a.py", "@@ -1 +1 @@\n-a\n+fixed-a"),
        ("b.py", "@@ -1 +1 @@\n-x\n+y"),
    ])
    after_second_fix = _mk_diff([
        ("a.py", "@@ -1 +1 @@\n-a\n+fixed-a"),
        ("b.py", "@@ -1 +1 @@\n-x\n+fixed-b"),
    ])
    state = RD.new_state(_cfg(diff=base))
    state["round"] = 2
    state["deltaBaseline"] = {"round": 2, "diff": after_first_fix}
    state["reviewedDiff"] = after_first_fix
    state["headDiff"] = after_second_fix
    state["fixBatch"] = [{"file": "b.py", "line": 1, "title": "bug-b", "severity": "Important"}]
    RD._enter_delta_round(state, _cfg(diff=base))
    new_surface = state.get("_newSurface") or {}
    audit_targets = state.get("_auditTargets") or []
    assert "a.py" not in new_surface
    assert not new_surface
    assert any(t.get("file") == "b.py" for t in audit_targets if isinstance(t, dict))
