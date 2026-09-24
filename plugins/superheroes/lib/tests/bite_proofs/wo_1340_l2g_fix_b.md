# FIX-B1 (#1340 layer 2g, review round 1) bite-proof

Per-guard bite proof for ignored lanes in stack snapshot, no-baseline flag firing,
and stack-state-changed non-suppressibility.

**Register:** 3 guards — **3 proven**, **0 unproven**.

**Provenance:** cursor / composer-2.5 (FIX-B1, layer 2g review round 1)

**Method:** smallest edit to guarded production code (never the test), reverted by the inverse edit.

**Command** (referred to as *the command* below, with `<node-id>` replaced per guard):

```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest "<node-id>" -q
```

## B1-1 — all lanes to the stack path

**neutralization:** restore ignore filter on `all_lanes` in `_derive_batch_lanes`:

```python
    all_lanes = {
        lid: info
        for lid, info in folded["launches"].items()
        if info.get("batchId") == batch_id
    }
```
→
```python
    all_lanes = {
        lid: info
        for lid, info in folded["launches"].items()
        if info.get("batchId") == batch_id and lid not in ignore
    }
```

**node id:** `plugins/superheroes/lib/tests/test_wave_watch.py::test_ignore_launch_stack_snapshot_reads_terminal_layers_planned`

**raw red:**
```
AssertionError: assert 'lane-term' in {'lane-live': {...}}
FAILED .../test_ignore_launch_stack_snapshot_reads_terminal_layers_planned
1 failed in 0.54s
```

**raw green:**
```
.                                                                        [100%]
1 passed in 0.50s
```

## B1-2 — the no-baseline flag arm

**neutralization:** remove `or bool(snapshot.get("flags"))` from `_stack_state_fires`:

```python
        ) or bool(snapshot.get("flags"))
```
→
```python
        )
```

**node id:** `plugins/superheroes/lib/tests/test_wave_watch.py::test_stack_state_fires_no_baseline_incomplete_with_flag`

**raw red:**
```
AssertionError: assert False
FAILED .../test_stack_state_fires_no_baseline_incomplete_with_flag
1 failed in 0.43s
```

**raw green:**
```
.                                                                        [100%]
1 passed in 0.39s
```

## B1-3 — the suppressible allowlist

**neutralization:** add `EVENT_STACK_STATE_CHANGED` to `_SUPPRESSIBLE_EVENTS`.

**node id:** `plugins/superheroes/lib/tests/test_wave_watch.py::test_ignore_event_invalid_direct_call[ignore_events5]` and `plugins/superheroes/lib/tests/test_wave_watch.py::test_ignore_event_invalid_cli[lane-a:stack-state-changed]`

**raw red:**
```
assert True is False
FAILED .../test_ignore_event_invalid_direct_call[ignore_events5]
assert 0 == 1
FAILED .../test_ignore_event_invalid_cli[lane-a:stack-state-changed]
2 failed in 2.93s
```

**raw green:**
```
..                                                                       [100%]
2 passed in 0.34s
```

## FIX-B2

**Register:** 4 guards — **4 proven**, **0 unproven**.

**Provenance:** cursor / composer-2.5 (FIX-B2, layer 2g review round 1)

**Method:** smallest edit to guarded production code (never the test), reverted by the inverse edit.

## B2-1a — open state gate

**neutralization:** drop the `state != "OPEN"` half of the ready check in `_position_ready_map`:

```python
        if state.get("state") != "OPEN" or state.get("isDraft"):
            continue
```
→
```python
        if state.get("isDraft"):
            continue
```

**node id:** `plugins/superheroes/lib/tests/test_wave_watch.py::test_merged_pr_excluded_from_ready_positions`

**raw red:**
```
AssertionError: assert 'stack-complete' == 'stack-incomplete'
FAILED .../test_merged_pr_excluded_from_ready_positions
1 failed in 0.50s
```

**raw green:**
```
.                                                                        [100%]
1 passed in 0.40s
```

## B2-1b — not-draft gate

**neutralization:** drop the `isDraft` half of the ready check in `_position_ready_map`:

```python
        if state.get("state") != "OPEN" or state.get("isDraft"):
            continue
```
→
```python
        if state.get("state") != "OPEN":
            continue
```

**node id:** `plugins/superheroes/lib/tests/test_wave_watch.py::test_draft_pr_excluded_from_ready_positions`

**raw red:**
```
AssertionError: assert 'stack-complete' == 'stack-incomplete'
FAILED .../test_draft_pr_excluded_from_ready_positions
1 failed in 0.46s
```

**raw green:**
```
.                                                                        [100%]
1 passed in 0.43s
```

## B2-2a — one slug read per tick

**neutralization:** restore the second `_resolve_repo_slug` call inside `_compute_stack_state_snapshot`:

```python
    _stacks, _ungrouped, membership_by_stack = _resolve_pr_stack_groups(
        ...
        repo_slug,
    )

    for stack_number in _batch_stack_numbers(batch_lanes):
```
→
```python
    _stacks, _ungrouped, membership_by_stack = _resolve_pr_stack_groups(
        ...
        repo_slug,
    )

    repo_slug, _slug_refusal = _resolve_repo_slug(
        repo_root, deadline, monotonic, gh_run, env,
    )

    for stack_number in _batch_stack_numbers(batch_lanes):
```

**node id:** `plugins/superheroes/lib/tests/test_wave_watch.py::test_repo_slug_resolved_once_per_run_tick`

**raw red:**
```
assert 2 == 1
FAILED .../test_repo_slug_resolved_once_per_run_tick
1 failed in 0.62s
```

**raw green:**
```
.                                                                        [100%]
1 passed in 0.47s
```

## B2-2b — slug-failure degradation

**neutralization:** drop the degradation line in `run()` when slug resolution fails:

```python
            if repo_slug is None:
                degraded.add(DEGRADATION_STACK_SIGNAL_UNAVAILABLE)
```
→
```python

```

**node id:** `plugins/superheroes/lib/tests/test_wave_watch.py::test_slug_resolution_failure_adds_stack_signal_degradation`

**raw red:**
```
AssertionError: assert 'stack-signal-unavailable' in []
FAILED .../test_slug_resolution_failure_adds_stack_signal_degradation
1 failed in 2.57s
```

**raw green:**
```
.                                                                        [100%]
1 passed in 2.48s
```

## FIX-C

**Register:** 2 guards — **2 proven**, **0 unproven**.

**Provenance:** cursor / composer-2.5 (FIX-C, layer 2g review round 2)

**Method:** smallest edit to guarded production code (never the test), reverted by the inverse edit.

## C-1 — lane-event tick skips gh poll

**neutralization:** disable the lane-event short-circuit in `run()`:

```python
            if lane_event_due:
```
→
```python
            if False:  # bite-proof C-1 neutralization: short-circuit removed
```

**node ids:** `plugins/superheroes/lib/tests/test_wave_watch.py::test_lane_terminal_makes_zero_gh_run_calls`, `::test_lane_blocked_makes_zero_gh_run_calls`, `::test_builder_exited_makes_zero_gh_run_calls`

**raw red:**
```
assert 1 == 0
FAILED .../test_lane_terminal_makes_zero_gh_run_calls
assert 1 == 0
FAILED .../test_lane_blocked_makes_zero_gh_run_calls
assert 1 == 0
FAILED .../test_builder_exited_makes_zero_gh_run_calls
3 failed in 6.96s
```

**restore:** `if False:  # bite-proof C-1 neutralization: short-circuit removed` → `if lane_event_due:`

**raw green:**
```
...                                                                      [100%]
3 passed in 7.03s
```

## C-2 — stack-state vocabulary bound to wave-watch.md

**Retracted (FIX-D):** the detector this record proves was deleted; CONVENTIONS §11.2 closes the copy-plus-drift-test pattern, and wave-watch.md now names the constants instead of spelling their values.

**neutralization:** change `STACK_STATE_COMPLETE` value in `wave_watch.py`:

```python
STACK_STATE_COMPLETE = "stack-complete"
```
→
```python
STACK_STATE_COMPLETE = "stack-done"
```

**node id:** `plugins/superheroes/lib/tests/test_ssot_drift.py::test_wave_watch_stack_state_vocabulary_in_wave_watch_doc`

**raw red:**
```
AssertionError: wave-watch.md stack-state-changed payload vocabulary drift from wave_watch stack constants — missing from doc paragraph: ['stack-done']
FAILED .../test_wave_watch_stack_state_vocabulary_in_wave_watch_doc
1 failed in 1.16s
```

**restore:** `STACK_STATE_COMPLETE = "stack-done"` → `STACK_STATE_COMPLETE = "stack-complete"`

**raw green:**
```
.                                                                        [100%]
1 passed in 0.90s
```
