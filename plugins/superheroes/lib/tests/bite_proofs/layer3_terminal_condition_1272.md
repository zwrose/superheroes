# Bite-proof record — #1272 layer 3 (terminal condition)

Re-taken at head cfd2dc04 (plus this order's test-only changes).

Contract: `rubric/bite-proof.md`. Neutralizations are targeted, reversible edits to guarded
production code; detectors are unedited.

| # | Guarded element | Detector |
|---|---|---|
| A1 | `_excluded_discharged_fix_row` exclusion predicate | `test_l3_a1_excludes_discharged_row` |
| A2 | `_queue_fix_batch` empty-after-filter convergence | `test_l3_a2_empty_batch_converges_on_the_paths_own_resolver` |
| A3 | `_enter_delta_round` split reviewed side | `test_l3_a3_delta_split_reads_per_round_reviewed_diff` |
| BP-v0 | `_resolve_empty_fix_batch_convergence` delta branch | `test_l3_a1_surfaced_critical_after_exclusion_rearms_confirmation` |
| BP-v1-stage | `_stage_findings` same-round dispositionSeq carry | `test_l3_a1_caller_supplied_sequence_stamps_stripped_on_reraise[1]` |
| BP-v1-backfill | `_backfill_ledger_from_records` sequence stamp pops | `test_l3_a1_backfill_strips_record_sequence_stamps` |

## A1 — discharged row exclusion

**Guarded code:** `round_driver._excluded_discharged_fix_row`

**Neutralization:**

```python
return False  # bite-proof neutralization A1
```

**Detector:** `test_l3_a1_excludes_discharged_row`

**Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
______________________ test_l3_a1_excludes_discharged_row ______________________

    def test_l3_a1_excludes_discharged_row():
        """axis: stamped ledger row with dispositionSeq > raisedSeq is excluded."""
        state = RD.new_state(_cfg())
        compiled, key = _stage_and_discharge(state)
        config = _cfg()
        RD._queue_fix_batch(state, config, [_fix_row(compiled)])
>       assert state.get("_fixBatch") in (None, [])
E       AssertionError: assert [{'classification': 'mechanical', 'file': 'f.py', 'findingKey': 'f.py::bug@L1', 'line': 1, ...}] in (None, [])
E        +  where [{'classification': 'mechanical', 'file': 'f.py', 'findingKey': 'f.py::bug@L1', 'line': 1, ...}] = <built-in method get of dict object at 0x102bd77c0>('_fixBatch')
E        +    where <built-in method get of dict object at 0x102bd77c0> = {'_changedSubjectsSincePanel': [], '_coverage': [], '_fixBatch': [{'classification': 'mechanical', 'file': 'f.py', 'findingKey': 'f.py::bug@L1', 'line': 1, ...}], '_fixBatchIndex': 0, ...}.get

plugins/superheroes/lib/tests/test_layer3_terminal_condition_1272.py:78: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_layer3_terminal_condition_1272.py::test_l3_a1_excludes_discharged_row
1 failed in 0.16s```

**Restore (quoted restored lines):**

```python
return disp_seq > raised_seq
```

**Green:**

```
.                                                                        [100%]
1 passed in 0.15s```

## A2 — empty-after-filter convergence

**Guarded code:** `round_driver._queue_fix_batch`

**Neutralization:**

```python
if batch_index == 0:
            _decision(state, "fix-batch-excluded",
                      "fix batch emptied by discharged-finding exclusion — "
                      "without fixer dispatch")
            pass  # bite-proof neutralization A2
```

**Detector:** `test_l3_a2_empty_batch_converges_on_the_paths_own_resolver`

**Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
__________ test_l3_a2_empty_batch_converges_on_the_paths_own_resolver __________

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
>       assert state["rounds"]["2"].get("confirmationFollowup") is not None
E       AssertionError: assert None is not None
E        +  where None = <built-in method get of dict object at 0x1072f5f40>('confirmationFollowup')
E        +    where <built-in method get of dict object at 0x1072f5f40> = {'fixBatchExcludedByDischarge': 1, 'roundKind': 'delta'}.get

plugins/superheroes/lib/tests/test_layer3_terminal_condition_1272.py:315: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_layer3_terminal_condition_1272.py::test_l3_a2_empty_batch_converges_on_the_paths_own_resolver
1 failed in 0.17s```

**Restore (quoted restored lines):**

```python
if batch_index == 0:
            _decision(state, "fix-batch-excluded",
                      "fix batch emptied by discharged-finding exclusion — "
                      "without fixer dispatch")
            _resolve_empty_fix_batch_convergence(state, config)
```

**Green:**

```
.                                                                        [100%]
1 passed in 0.15s```

## A3 — delta split reads per-round reviewed baseline

**Guarded code:** `round_driver._enter_delta_round`

**Neutralization:**

```python
split = delta_surface.split_fix_surface(
        state.get("reviewedDiff"), state.get("headDiff"), state.get("fixBatch") or [])
```

**Detector:** `test_l3_a3_delta_split_reads_per_round_reviewed_diff`

**Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_____________ test_l3_a3_delta_split_reads_per_round_reviewed_diff _____________

monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x106561250>

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
        state["reviewedDiff"] = _THIRD_DIFF
        state["headDiff"] = _HEAD_DIFF
        state["fixBatch"] = _fix_batch()
        RD._enter_delta_round(state, _cfg(diff=_BASE_DIFF))
>       assert captured["reviewed"] == _HEAD_DIFF
E       AssertionError: assert 'diff --git a...rd-edited\n\n' == 'diff --git a...n+head line\n'
E         
E         - diff --git a/f.py b/f.py
E         ?              ^      ^
E         + diff --git a/h.py b/h.py
E         ?              ^      ^
E         - index 2..3 100644
E         + index 1111111..2222222 100644...
E         
E         ...Full output truncated (14 lines hidden), use '-vv' to show

plugins/superheroes/lib/tests/test_layer3_terminal_condition_1272.py:484: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_layer3_terminal_condition_1272.py::test_l3_a3_delta_split_reads_per_round_reviewed_diff
1 failed in 0.17s```

**Restore (quoted restored lines):**

```python
split = delta_surface.split_fix_surface(
        reviewed, state.get("headDiff"), state.get("fixBatch") or [])
```

**Green:**

```
.                                                                        [100%]
1 passed in 0.15s```

## BP-v0 — delta empty-batch must re-arm confirmation, not terminal-converge

**Guarded code:** `round_driver._resolve_empty_fix_batch_convergence`

**Neutralization:**

```python
if round_rec.get("roundKind") == "delta":
        _terminal_converged(state, config, full_panel=state.get("fullPanelRan"))
        return
```

**Detector:** `test_l3_a1_surfaced_critical_after_exclusion_rearms_confirmation`

**Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_______ test_l3_a1_surfaced_critical_after_exclusion_rearms_confirmation _______

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
>       assert state["step"] == RD.P_PANEL
E       AssertionError: assert 'terminal' == 'dispatch-panel'
E         
E         - dispatch-panel
E         + terminal

plugins/superheroes/lib/tests/test_layer3_terminal_condition_1272.py:194: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_layer3_terminal_condition_1272.py::test_l3_a1_surfaced_critical_after_exclusion_rearms_confirmation
1 failed in 0.17s```

**Restore (quoted restored lines):**

```python
if round_rec.get("roundKind") == "delta":
        _settle_delta_converged(state, config)
        return
```

**Green:**

```
.                                                                        [100%]
1 passed in 0.15s```

## BP-v1-stage — same-round dispositionSeq carry must not survive staging

**Guarded code:** `round_driver._stage_findings`

**Neutralization:**

```python
if (isinstance(existing, dict)
                and session_contract.has_disposition_family(existing)
                and existing.get("dispositionRound") == round_no):
            for field in session_contract.DISPOSITION_FAMILY_FIELDS:
                if field in existing:
                    entry[field] = existing[field]
            disp_seq = existing.get("dispositionSeq")
            if isinstance(disp_seq, int) and not isinstance(disp_seq, bool):
                entry["dispositionSeq"] = disp_seq
```

**Detector:** `test_l3_a1_caller_supplied_sequence_stamps_stripped_on_reraise[1]`

**Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
______ test_l3_a1_caller_supplied_sequence_stamps_stripped_on_reraise[1] _______

reraise_round = 1

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
>       assert "dispositionSeq" not in entry
E       AssertionError: assert 'dispositionSeq' not in {'classification': 'mechanical', 'disposition': 'fixed', 'dispositionReceipt': {'headSha': 'dddddddddddddddddddddddddddddddddddddddd'}, 'dispositionRound': 1, ...}

plugins/superheroes/lib/tests/test_layer3_terminal_condition_1272.py:144: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_layer3_terminal_condition_1272.py::test_l3_a1_caller_supplied_sequence_stamps_stripped_on_reraise[1]
1 failed in 0.16s```

**Restore (quoted restored lines):**

```python
if (isinstance(existing, dict)
                and session_contract.has_disposition_family(existing)
                and existing.get("dispositionRound") == round_no):
            for field in session_contract.DISPOSITION_FAMILY_FIELDS:
                if field in existing:
                    entry[field] = existing[field]
```

**Green:**

```
.                                                                        [100%]
1 passed in 0.15s```

## BP-v1-backfill — record sequence stamps must not survive backfill

**Guarded code:** `round_driver._backfill_ledger_from_records`

**Neutralization:**

```python
entry = _strip_disposition_family(dict(finding))
            pass  # bite-proof neutralization BP-v1-backfill
            if key in preexisting:
```

**Detector:** `test_l3_a1_backfill_strips_record_sequence_stamps`

**Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
______________ test_l3_a1_backfill_strips_record_sequence_stamps _______________

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
>       assert "dispositionSeq" not in entry
E       AssertionError: assert 'dispositionSeq' not in {'dispositionSeq': 999, 'file': 'o', 'findingKey': 'o::old@L1', 'line': 1, ...}

plugins/superheroes/lib/tests/test_layer3_terminal_condition_1272.py:167: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_layer3_terminal_condition_1272.py::test_l3_a1_backfill_strips_record_sequence_stamps
1 failed in 0.17s```

**Restore (quoted restored lines):**

```python
entry = _strip_disposition_family(dict(finding))
            entry.pop(session_contract.RAISED_SEQ_FIELD, None)
            entry.pop(session_contract.DISPOSITION_SEQ_FIELD, None)
            if key in preexisting:
```

**Green:**

```
.                                                                        [100%]
1 passed in 0.15s```
