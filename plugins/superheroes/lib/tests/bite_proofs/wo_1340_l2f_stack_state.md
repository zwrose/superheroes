# WO-T1a (#1340 layer 2g) bite-proof — stack completion snapshot in wave_watch.py

Per-guard bite proof for the completion snapshot (`_layers_planned_for_stack`,
`_occupied_layer_positions`, `_position_ready_map`, `_compute_stack_state_snapshot`, and
`_derive_batch_lanes` terminal-inclusive `batch_lanes`).

**Register:** 11 guards in census — **11 proven**, **0 unproven**. One test rewritten
(`test_layers_planned_read_from_terminal_launch`). One guarded element has no claiming test
(position-ready budget — reported as gap).

**Provenance:** cursor / composer-2.5 (WO-T1a, layer 2g)

**Head:** tree = 5deb9d99 + WO-T1a working changes; the orchestrator re-pins at the final head.

**Method:** smallest edit to guarded production code (never the test), reverted by the inverse edit.
Each proof runs by exact node id. A red on the wrong axis is vacuous and not counted.

**Command** (referred to as *the command* below, with `<node-id>` replaced per guard):

```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest "<node-id>" -q
```

## Census and summary

| ID | Guarded element (file:line) | Axis | Proving test | Outcome |
|---|---|---|---|---|
| G1 | wave_watch.py:984-988 | empty `layersPlanned` → `layers-planned-unknown` | `test_layers_planned_unknown_incomplete` | proven |
| G2 | wave_watch.py:989-993 | disagreed `layersPlanned` → `layers-planned-disagreed` | `test_layers_planned_disagreed_incomplete` | proven |
| G3 | wave_watch.py:1001-1005 | unresolved membership → `membership-unresolved` | `test_stack_incomplete_membership_unresolved` | proven |
| G4 | wave_watch.py:1038 | every position `1..layersPlanned` must be ready | `test_stack_incomplete_missing_position` | proven |
| G5 | wave_watch.py:1046 | all positions ready → `stack-complete` | `test_stack_complete_fires_when_every_position_ready` | proven |
| G6 | wave_watch.py:937-938 | PR vet read refusal leaves position not ready | `test_stack_incomplete_pr_read_refuses` | proven |
| G7 | wave_watch.py:944-945 | verdict must be READY | `test_stack_incomplete_not_ready_verdict` | proven |
| G8 | wave_watch.py:939-941 | vet verdict pinned to PR **current** head | `test_stack_incomplete_stale_sha` | proven |
| G9 | wave_watch.py:421 | `batch_lanes` is `all_lanes` (terminal included) | `test_layers_planned_read_from_terminal_launch` | test rewritten, proven |
| G10 | wave_watch.py:976 | each stack in batch evaluated independently | `test_two_stacks_one_complete_one_not` | proven |
| G11 | wave_watch.py:764-769 | membership read budget stops mid-walk | `test_stack_budget_exhausted_mid_walk_remaining_incomplete` | proven |
| — | wave_watch.py:927-928, 1017-1021 | position-ready walk budget → incomplete | *(none in the 11)* | **gap** |

## Test rewritten

**`test_layers_planned_read_from_terminal_launch`** — was inert: `_setup_stack_batch` called
`ll.append(_outcome(...))`, which silently refuses terminal events, so the folded launch never had
`terminal: true` and neutralizing `all_lanes` vs `live_lanes` changed nothing observable.

**Fix:** `_setup_stack_batch` now calls `ll.terminalize(..., child_ever_spawned=True, outcome="handback",
evidence="done")` when `terminal=True`. The test derives lanes via `_derive_batch_lanes` (with
`env=None` so the monkeypatched ledger root is visible), asserts the terminal lane is in
`batch_lanes` but not `live_lanes`, then checks the snapshot reads `layersPlanned` from it.

---

## G1 — layers-planned-unknown

**neutralization:**

```python
        if not layers_values:
            entry["state"] = "stack-incomplete"
            entry["reason"] = "layers-planned-unknown"
```
→
```python
        if not layers_values:
            entry["state"] = "stack-complete"
            entry["reason"] = None
```

**node id:** `plugins/superheroes/lib/tests/test_wave_watch.py::test_layers_planned_unknown_incomplete`

**raw red:**
```
AssertionError: assert 'stack-complete' == 'stack-incomplete'
FAILED .../test_layers_planned_unknown_incomplete
1 failed in 1.34s
```

**raw green:**
```
.                                                                        [100%]
1 passed in 1.17s
```

## G2 — layers-planned-disagreed

**neutralization:**

```python
        if len(layers_values) > 1:
            entry["state"] = "stack-incomplete"
            entry["reason"] = "layers-planned-disagreed"
```
→
```python
        if len(layers_values) > 1:
            entry["state"] = "stack-complete"
            entry["reason"] = None
```

**node id:** `plugins/superheroes/lib/tests/test_wave_watch.py::test_layers_planned_disagreed_incomplete`

**raw red:**
```
AssertionError: assert 'stack-complete' == 'stack-incomplete'
FAILED .../test_layers_planned_disagreed_incomplete
1 failed in 1.33s
```

**raw green:**
```
.                                                                        [100%]
1 passed in 1.26s
```

## G3 — membership-unresolved

**neutralization:**

```python
        if not position_map or repo_slug is None:
            entry["state"] = "stack-incomplete"
            entry["reason"] = "membership-unresolved"
```
→
```python
        if not position_map or repo_slug is None:
            entry["state"] = "stack-complete"
            entry["reason"] = None
```

**node id:** `plugins/superheroes/lib/tests/test_wave_watch.py::test_stack_incomplete_membership_unresolved`

**raw red:**
```
AssertionError: assert 'stack-complete' == 'stack-incomplete'
FAILED .../test_stack_incomplete_membership_unresolved
1 failed in 1.32s
```

**raw green:**
```
.                                                                        [100%]
1 passed in 1.14s
```

## G4 — every position must be ready

**neutralization:**

```python
            if position not in position_map or position not in ready_positions:
```
→
```python
            if False:
```

**node id:** `plugins/superheroes/lib/tests/test_wave_watch.py::test_stack_incomplete_missing_position`

**raw red:**
```
AssertionError: assert 'stack-complete' == 'stack-incomplete'
FAILED .../test_stack_incomplete_missing_position
1 failed in 1.15s
```

**raw green:**
```
.                                                                        [100%]
1 passed in 0.54s
```

## G5 — stack-complete when all ready

**neutralization:**

```python
        entry["state"] = "stack-complete"
```
→
```python
        entry["state"] = "stack-incomplete"
```

**node id:** `plugins/superheroes/lib/tests/test_wave_watch.py::test_stack_complete_fires_when_every_position_ready`

**raw red:**
```
AssertionError: assert 'stack-incomplete' == 'stack-complete'
FAILED .../test_stack_complete_fires_when_every_position_ready
1 failed in 2.84s
```

**raw green:**
```
.                                                                        [100%]
1 passed in 0.54s
```

## G6 — PR vet read refusal

**neutralization:**

```python
        if refusal is not None:
            continue
```
→
```python
        if refusal is not None:
            ready[position] = True
            continue
```

**node id:** `plugins/superheroes/lib/tests/test_wave_watch.py::test_stack_incomplete_pr_read_refuses`

**raw red:**
```
AssertionError: assert 'stack-complete' == 'stack-incomplete'
FAILED .../test_stack_incomplete_pr_read_refuses
1 failed in 0.55s
```

**raw green:**
```
.                                                                        [100%]
1 passed in 0.71s
```

## G7 — verdict must be READY

**neutralization:**

```python
        if verdict == sc.VERDICT_READY:
            ready[position] = True
```
→
```python
        if True:
            ready[position] = True
```

**node id:** `plugins/superheroes/lib/tests/test_wave_watch.py::test_stack_incomplete_not_ready_verdict`

**raw red:**
```
AssertionError: assert 'stack-complete' == 'stack-incomplete'
FAILED .../test_stack_incomplete_not_ready_verdict
1 failed in 0.59s
```

**raw green:**
```
.                                                                        [100%]
1 passed in 0.58s
```

## G8 — vet pinned to PR current head

**neutralization:**

```python
        verdict, vet_refusal = sc.read_vet_verdict(
            state["body"], state["headRefOid"],
        )
```
→
```python
        _probe_sha = None
        for _tok in state["body"].replace("·", " ").split():
            if len(_tok) == 40 and all(
                c in "0123456789abcdefABCDEF" for c in _tok
            ):
                _probe_sha = _tok
                break
        verdict, vet_refusal = sc.read_vet_verdict(
            state["body"], _probe_sha or state["headRefOid"],
        )
```

**node id:** `plugins/superheroes/lib/tests/test_wave_watch.py::test_stack_incomplete_stale_sha`

**raw red:**
```
AssertionError: assert 'stack-complete' == 'stack-incomplete'
FAILED .../test_stack_incomplete_stale_sha
1 failed in 0.66s
```

**raw green:**
```
.                                                                        [100%]
1 passed in 0.58s
```

## G9 — terminal-inclusive batch_lanes

**neutralization:**

```python
    return all_lanes, live_lanes, True
```
→
```python
    return live_lanes, live_lanes, True
```

**node id:** `plugins/superheroes/lib/tests/test_wave_watch.py::test_layers_planned_read_from_terminal_launch`

**raw red:**
```
KeyError: 'lane-term'
FAILED .../test_layers_planned_read_from_terminal_launch
1 failed in 1.63s
```

**raw green:**
```
.                                                                        [100%]
1 passed in 1.59s
```

## G10 — per-stack evaluation

**neutralization:**

```python
    for stack_number in _batch_stack_numbers(batch_lanes):
```
→
```python
    for stack_number in _batch_stack_numbers(batch_lanes)[:1]:
```

**node id:** `plugins/superheroes/lib/tests/test_wave_watch.py::test_two_stacks_one_complete_one_not`

**raw red:**
```
KeyError: 200
FAILED .../test_two_stacks_one_complete_one_not
1 failed in 0.61s
```

**raw green:**
```
.                                                                        [100%]
1 passed in 0.44s
```

## G11 — membership read budget mid-walk

**neutralization:**

```python
        if remaining < _MIN_PR_POLL_SECONDS:
            degraded.add(DEGRADATION_STACK_SIGNAL_UNAVAILABLE)
```
→
```python
        if False:
            degraded.add(DEGRADATION_STACK_SIGNAL_UNAVAILABLE)
```

**node id:** `plugins/superheroes/lib/tests/test_wave_watch.py::test_stack_budget_exhausted_mid_walk_remaining_incomplete`

**raw red:**
```
AssertionError: assert [50, 60] == [50]
FAILED .../test_stack_budget_exhausted_mid_walk_remaining_incomplete
1 failed in 0.47s
```

**raw green:**
```
.                                                                        [100%]
1 passed in 0.43s
```

## Doc disagreements (report only — T1b owns wave-watch.md)

1. **`reason: null` on incomplete stacks.** `wave-watch.md` lists `reason` as `null` only when
   `state` is `stack-complete`. In `test_stack_budget_exhausted_mid_walk_remaining_incomplete`,
   stack 100 is `stack-incomplete` with `reason` left `null` (only `missingPositions` populated via
   the position-ready budget path), while stack 200 correctly gets `membership-unresolved`.
2. **Position-ready budget incomplete shape** is not documented separately from membership budget
   exhaustion; the gap element at 927-928 / 1017-1021 has no test in this order's 11.

## Code removals

None — no guarded element proved redundant or unreachable.

## Event layer (T1b)

**Register:** 7 event-layer guards + 4 Part-3 guards — **11 proven**, **0 unproven**. Three tests
rewritten for bite (`test_stack_complete_fires_on_vet_only_without_pr_set_change`,
`test_incomplete_seeds_silently_complete_fires`, `test_baseline_advances_unchanged_complete_does_not_refire`).
Two gap tests added (`test_stack_position_ready_budget_exhausted`,
`test_stack_incomplete_vet_read_refuses`). `test_stack_incomplete_pr_read_refuses` extended for
`stack-signal-unavailable`.

**Provenance:** cursor / composer-2.5 (WO-T1b, layer 2g)

### Census and summary

| ID | Guarded element (file:line) | Proving test | Outcome |
|---|---|---|---|
| E1 | wave_watch.py:1054-1056 | `test_stack_complete_fires_on_vet_only_without_pr_set_change` | test rewritten, proven |
| E2 | wave_watch.py:1057 | `test_incomplete_seeds_silently_complete_fires` | test rewritten, proven |
| E3 | wave_watch.py:1078-1080 | `test_incomplete_seeds_silently_complete_fires` | test rewritten, proven |
| E4 | wave_watch.py:1081-1082 | `test_baseline_advances_unchanged_complete_does_not_refire` | test rewritten, proven |
| E5 | wave_watch.py:1089 | `test_baseline_advances_unchanged_complete_does_not_refire` | test rewritten, proven |
| E6 | wave_watch.py:243-248 | `test_precedence_stack_state_over_pr_set_pr_baseline_unchanged` | proven |
| E7 | wave_watch.py:251-256 | `test_stack_state_not_suppressible_via_ignore_events` | proven |
| P1 | wave_watch.py:927-929 | `test_stack_position_ready_budget_exhausted` | gap filled, proven |
| P2 | wave_watch.py:937-939 | `test_stack_incomplete_pr_read_refuses` | proven |
| P3 | wave_watch.py:945-947 | `test_stack_incomplete_vet_read_refuses` | gap filled, proven |
| P4 | wave_watch.py:1020-1024 | `test_stack_position_ready_budget_exhausted` | gap filled, proven |

`test_stack_state_watch_read_only_no_store_mutation` guards run() store read-only integration;
neutralization via `hb.stamp` in `_payload_stack_state_changed` goes red (see E7b below).

### Tests rewritten

**`test_baseline_advances_unchanged_complete_does_not_refire`** — was inert for baseline advance:
used `loop()` and only asserted one arm. Now calls `run()` twice with the same `stack_state` cell;
second call must not return `stack-state-changed`.

**`test_stack_complete_fires_on_vet_only_without_pr_set_change`** — added
`assert ww._stack_state_fires(complete_snapshot, None)` so neutralizing the baseline-`None`
complete check goes red.

**`test_incomplete_seeds_silently_complete_fires`** — added direct `_stack_state_fires` transition
asserts and a `_payload_stack_state_changed` seed call asserting `stack_state[0]` is seeded.

### Gap tests added

**`test_stack_position_ready_budget_exhausted`** — ready-walk budget exhausted after membership;
every position missing, `reason` null, `stack-signal-unavailable` in `degraded`.

**`test_stack_incomplete_vet_read_refuses`** — vet verdict read refusal; position not READY,
`stack-signal-unavailable` in `degraded`.

### Code removals

None.

---

## E1 — baseline None fires on any complete stack

**neutralization:** `entry["state"] == "stack-complete"` → `False` in `_stack_state_fires`.

**node id:** `plugins/superheroes/lib/tests/test_wave_watch.py::test_stack_complete_fires_on_vet_only_without_pr_set_change`

**raw red:** `AssertionError` on `assert ww._stack_state_fires(complete_snapshot, None)`

**raw green:** `. [100%] 1 passed`

## E2 — snapshot differs from baseline

**neutralization:** `return snapshot != baseline` → `return False`.

**node id:** `plugins/superheroes/lib/tests/test_wave_watch.py::test_incomplete_seeds_silently_complete_fires`

**raw red:** `AssertionError` on `assert ww._stack_state_fires(complete_snapshot, incomplete_snapshot)`

**raw green:** `. [100%] 1 passed`

## E3 — incomplete seeds baseline silently

**neutralization:** remove `stack_state[0] = snapshot` on seed path.

**node id:** `plugins/superheroes/lib/tests/test_wave_watch.py::test_incomplete_seeds_silently_complete_fires`

**raw red:** `AssertionError` on `assert stack_state[0] == incomplete_snapshot`

**raw green:** `. [100%] 1 passed`

## E4 — unchanged snapshot does not refire

**neutralization:** `if baseline is not None and snapshot == baseline: return None` → `if False: return None`.

**node id:** `plugins/superheroes/lib/tests/test_wave_watch.py::test_baseline_advances_unchanged_complete_does_not_refire`

**raw red:** `AssertionError: assert 'stack-state-changed' != 'stack-state-changed'` on second `run()`

**raw green:** `. [100%] 1 passed`

## E5 — baseline advances on fire

**neutralization:** remove `stack_state[0] = snapshot` on firing path (keep payload build).

**node id:** `plugins/superheroes/lib/tests/test_wave_watch.py::test_baseline_advances_unchanged_complete_does_not_refire`

**raw red:** same second-`run()` refire `AssertionError` as E4

**raw green:** `. [100%] 1 passed`

## E6 — stack-state precedes pr-set-changed

**neutralization:** swap `EVENT_STACK_STATE_CHANGED` / `EVENT_PR_SET_CHANGED` in `EVENT_PRECEDENCE`.

**node id:** `plugins/superheroes/lib/tests/test_wave_watch.py::test_precedence_stack_state_over_pr_set_pr_baseline_unchanged`

**raw red:** `AssertionError: assert 'pr-set-changed' == 'stack-state-changed'`

**raw green:** `. [100%] 1 passed`

## E7 — stack-state-changed not suppressible

**neutralization:** early `return None` from `_payload_stack_state_changed` when `ignore_set` non-empty.

**node id:** `plugins/superheroes/lib/tests/test_wave_watch.py::test_stack_state_not_suppressible_via_ignore_events`

**raw red:** `AssertionError: assert 'timer' == 'stack-state-changed'`

**raw green:** `. [100%] 1 passed`

## E7b — run() store read-only during stack evaluation

**neutralization:** `hb.stamp(...)` in `_payload_stack_state_changed` before `return payload`.

**node id:** `plugins/superheroes/lib/tests/test_wave_watch.py::test_stack_state_watch_read_only_no_store_mutation`

**raw red:** `AssertionError: assert before == after` (store files changed)

**raw green:** `. [100%] 1 passed`

## P1 — ready-walk budget adds degradation

**neutralization:** remove `degraded.add(DEGRADATION_STACK_SIGNAL_UNAVAILABLE)` before budget `return None`.

**node id:** `plugins/superheroes/lib/tests/test_wave_watch.py::test_stack_position_ready_budget_exhausted`

**raw red:** `AssertionError: assert 'stack-signal-unavailable' in set()`

**raw green:** `. [100%] 1 passed`

## P2 — PR vet read refusal adds degradation

**neutralization:** remove `degraded.add` on PR refusal branch.

**node id:** `plugins/superheroes/lib/tests/test_wave_watch.py::test_stack_incomplete_pr_read_refuses`

**raw red:** `AssertionError: assert 'stack-signal-unavailable' in set()`

**raw green:** `. [100%] 1 passed`

## P3 — vet verdict read refusal adds degradation

**neutralization:** remove `degraded.add` on vet refusal branch.

**node id:** `plugins/superheroes/lib/tests/test_wave_watch.py::test_stack_incomplete_vet_read_refuses`

**raw red:** `AssertionError: assert 'stack-signal-unavailable' in set()`

**raw green:** `. [100%] 1 passed`

## P4 — ready_positions None marks all positions missing

**neutralization:** `entry["missingPositions"] = list(...)` → `entry["missingPositions"] = []`.

**node id:** `plugins/superheroes/lib/tests/test_wave_watch.py::test_stack_position_ready_budget_exhausted`

**raw red:** `AssertionError: assert [] == [1, 2]`

**raw green:** `. [100%] 1 passed`

## Doc edits (T1b)

- `wave-watch.md`: stack-state `reason` clause corrected; unread-position sentence under **Complete**;
  **Stack-state baseline** bullet after **PR-set baseline**.
- `wave_watch.py`: comment above baseline advance corrected (caller-threaded cell; `loop` returns).

## Command count

30 invocations (budget cap).
