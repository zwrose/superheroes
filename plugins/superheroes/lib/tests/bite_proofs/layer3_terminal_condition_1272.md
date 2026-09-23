# Bite-proof record — #1272 layer 3 (terminal condition)

Contract: `rubric/bite-proof.md`. Neutralizations are targeted, reversible edits to guarded
production code; detectors are unedited. The same-round re-raise control
(`test_l3_a1_same_round_reraise_stays_in_batch`) stayed green under all three neutralizations.

| # | Guarded element | Detector |
|---|---|---|
| A1 | `_excluded_discharged_fix_row` exclusion predicate | `test_l3_a1_excludes_discharged_row` |
| A2 | `_queue_fix_batch` empty-after-filter convergence | `test_l3_a2_empty_batch_converges_on_the_paths_own_resolver` |
| A3 | `_enter_delta_round` split reviewed side | `test_l3_a3_delta_split_reads_per_round_reviewed_diff` |

---

## A1 — discharged row exclusion

**Neutralization** (`round_driver.py`, `_excluded_discharged_fix_row`):

```python
-    return disp_seq > raised_seq
+    return False  # bite-proof neutralization A1
```

**Expected red token:** discharged row **present** in `_fixBatch`.

**Raw red:**

```
F.                                                                       [100%]
=================================== FAILURES ===================================
______________________ test_l3_a1_excludes_discharged_row ______________________

    def test_l3_a1_excludes_discharged_row():
        state = RD.new_state(_cfg())
        compiled, key = _stage_and_discharge(state)
        config = _cfg()
        RD._queue_fix_batch(state, config, [_fix_row(compiled)])
>       assert state.get("_fixBatch") in (None, [])
E       AssertionError: assert [{'classification': 'mechanical', 'file': 'f.py', 'findingKey': 'f.py::bug@L1', 'line': 1, ...}] in (None, [])
E        +  where [{'classification': 'mechanical', 'file': 'f.py', 'findingKey': 'f.py::bug@L1', 'line': 1, ...}] = <built-in method get of dict object at 0x106f82c80>('_fixBatch')
E        +    where <built-in method get of dict object at 0x106f82c80> = {'_changedSubjectsSincePanel': [], '_coverage': [], '_fixBatch': [{'classification': 'mechanical', 'file': 'f.py', 'findingKey': 'f.py::bug@L1', 'line': 1, ...}], '_fixBatchIndex': 0, ...}.get

plugins/superheroes/lib/tests/test_layer3_terminal_condition_1272.py:77: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_layer3_terminal_condition_1272.py::test_l3_a1_excludes_discharged_row
1 failed, 1 passed in 0.26s
```

**Restore:** `return disp_seq > raised_seq`

**Restore receipt (quoted line):**

```python
    return disp_seq > raised_seq
```

**Raw green:**

```
.                                                                        [100%]
1 passed in 0.23s
```

---

## A2 — empty-after-filter convergence

**Neutralization** (`round_driver.py`, `_queue_fix_batch`):

```python
-    if offered_nonempty and not filtered:
-        _record_round(state, "fixBatchExcludedByDischarge", len(rows))
-        _decision(state, "fix-batch-excluded",
-                  "fix batch emptied by discharged-finding exclusion — "
-                  "round converged without fixer dispatch")
-        _resolve_empty_fix_batch_convergence(state, config)
-        return
+    if offered_nonempty and not filtered:
+        pass  # bite-proof neutralization A2
```

**Expected red token:** `state["step"] == "dispatch-fixer"` (`P_FIXER`) where convergence was expected.

**Raw red:**

```
F.                                                                       [100%]
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
>       assert state["step"] != RD.P_FIXER
E       AssertionError: assert 'dispatch-fixer' != 'dispatch-fixer'
E        +  where 'dispatch-fixer' = RD.P_FIXER

plugins/superheroes/lib/tests/test_layer3_terminal_condition_1272.py:196: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_layer3_terminal_condition_1272.py::test_l3_a2_empty_batch_converges_on_the_paths_own_resolver
1 failed, 1 passed in 0.21s
```

**Restore:** restored the full `if offered_nonempty and not filtered:` convergence block verbatim.

**Restore receipt (quoted lines):**

```python
    if offered_nonempty and not filtered:
        _record_round(state, "fixBatchExcludedByDischarge", len(rows))
        _decision(state, "fix-batch-excluded",
                  "fix batch emptied by discharged-finding exclusion — "
                  "round converged without fixer dispatch")
        _resolve_empty_fix_batch_convergence(state, config)
        return
```

**Raw green:**

```
.                                                                        [100%]
1 passed in 0.22s
```

---

## A3 — delta split reads per-round reviewed baseline

**Neutralization** (`round_driver.py`, `_enter_delta_round` split call):

```python
-    split = delta_surface.split_fix_surface(
-        reviewed, state.get("headDiff"), state.get("fixBatch") or [])
+    split = delta_surface.split_fix_surface(
+        state.get("baseReviewedDiff"), state.get("headDiff"), state.get("fixBatch") or [])
```

**Expected red token:** split reviewed side equals session **base** diff rather than per-round reviewed.

**Raw red:**

```
F.                                                                       [100%]
=================================== FAILURES ===================================
____________ test_l3_a3_delta_split_reads_per_round_reviewed_diff ______________

    def test_l3_a3_delta_split_reads_per_round_reviewed_diff(monkeypatch):
        ...
        RD._enter_delta_round(state, _cfg(diff=_BASE_DIFF))
>       assert captured["reviewed"] == _HEAD_DIFF
E       AssertionError: assert 'diff --git a...\n+new base\n' == 'diff --git a...n+head line\n'

plugins/superheroes/lib/tests/test_layer3_terminal_condition_1272.py:272: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_layer3_terminal_condition_1272.py::test_l3_a3_delta_split_reads_per_round_reviewed_diff
1 failed, 1 passed in 0.48s
```

**Restore:** `reviewed` restored as the split's reviewed argument.

**Restore receipt (quoted lines):**

```python
    split = delta_surface.split_fix_surface(
        reviewed, state.get("headDiff"), state.get("fixBatch") or [])
```

**Raw green:**

```
.                                                                        [100%]
1 passed in 0.30s
```
