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

Filled by FIX-B2.
