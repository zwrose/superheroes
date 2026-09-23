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


def test_l3_a2_fold_fixer_excluded_continuation_records_no_split():
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
    assert not any(d["kind"] == "fix-batch-split" for d in state["decisions"])
    assert any(d["kind"] == "fix-batch-excluded" for d in state["decisions"])
    assert state["step"] != RD.P_FIXER


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


def test_l3_a3_delta_split_reads_per_round_reviewed_diff(monkeypatch):
    captured = {}
    real_split = RD.delta_surface.split_fix_surface

    def _capture_split(reviewed, head, fix_batch):
        captured["reviewed"] = reviewed
        return real_split(reviewed, head, fix_batch)

    monkeypatch.setattr(RD.delta_surface, "split_fix_surface", _capture_split)
    state = RD.new_state(_cfg(diff=_BASE_DIFF))
    state["round"] = 2
    state["reviewedDiff"] = _HEAD_DIFF
    state["headDiff"] = _HEAD_DIFF
    state["fixBatch"] = [{"file": "f.py", "line": 1, "title": "bug", "severity": "Important"}]
    RD._enter_delta_round(state, _cfg(diff=_BASE_DIFF))
    assert captured["reviewed"] == _HEAD_DIFF
    assert captured["reviewed"] != _BASE_DIFF


def test_l3_a3_absent_reviewed_diff_falls_back_to_config_diff(monkeypatch):
    captured = {}
    real_split = RD.delta_surface.split_fix_surface

    def _capture_split(reviewed, head, fix_batch):
        captured["reviewed"] = reviewed
        return real_split(reviewed, head, fix_batch)

    monkeypatch.setattr(RD.delta_surface, "split_fix_surface", _capture_split)
    state = RD.new_state(_cfg(diff=_BASE_DIFF))
    state.pop("reviewedDiff", None)
    state["round"] = 2
    state["headDiff"] = _HEAD_DIFF
    state["fixBatch"] = [{"file": "f.py", "line": 1, "title": "bug", "severity": "Important"}]
    RD._enter_delta_round(state, _cfg(diff=_BASE_DIFF))
    assert captured["reviewed"] == _BASE_DIFF
    assert state["step"] != RD.P_PANEL


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
    state["reviewedDiff"] = after_first_fix
    state["headDiff"] = after_second_fix
    state["fixBatch"] = [{"file": "b.py", "line": 1, "title": "bug-b", "severity": "Important"}]
    RD._enter_delta_round(state, _cfg(diff=base))
    new_surface = state.get("_newSurface") or {}
    audit_targets = state.get("_auditTargets") or []
    assert "a.py" not in new_surface
    assert not new_surface
    assert any(t.get("file") == "b.py" for t in audit_targets if isinstance(t, dict))
