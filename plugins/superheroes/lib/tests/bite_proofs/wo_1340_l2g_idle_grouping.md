# WO-T2 (#1340 layer 2g) bite-proof — idle-seat flag, stack ordering, removed-PR grouping, gh scrub

Per-guard bite proof for the idle-seat flag loop, `_occupied_layer_positions`, early-exit
no-flag paths, stack position ordering in `_resolve_pr_stack_groups`, `changed_prs = added +
removed`, and `_gh_scrub_env` variable families.

**Register:** 11 guards in census — **11 proven**, **0 unproven**. No tests rewritten. No code
removals.

**Provenance:** cursor / composer-2.5 (WO-T2, layer 2g)

**Head:** tree = 4e31b43e + WO-T2 working changes; the orchestrator re-pins at the final head.

**Method:** smallest edit to guarded production code (never the test), reverted by the inverse edit.
Each proof runs by exact node id. A red on the wrong axis is vacuous and not counted.

**Command** (referred to as *the command* below, with `<node-id>` replaced per guard):

```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest "<node-id>" -q
```

## Census and summary

| ID | Guarded element (file:line) | Axis | Proving test | Outcome |
|---|---|---|---|---|
| I1 | wave_watch.py:906-915 | occupied positions from batch lanes | `test_idle_seat_launchable_child_flag_present_and_absent` | proven |
| I2 | wave_watch.py:1027-1037 | idle-seat flag emitted when next position unoccupied | `test_idle_seat_launchable_child_incomplete_unlaunched_position` | proven |
| I3 | wave_watch.py:987-991 | no idle-seat flags when layers-planned-unknown | `test_idle_seat_no_flags_layers_planned_unknown` | proven |
| I4 | wave_watch.py:992-996 | no idle-seat flags when layers-planned-disagreed | `test_idle_seat_no_flags_layers_planned_disagreed` | proven |
| I5 | wave_watch.py:1004-1008 | no idle-seat flags when membership-unresolved | `test_idle_seat_no_flags_membership_unresolved` | proven |
| I6 | wave_watch.py:1026-1047 | idle-seat flags before incomplete determination | `test_idle_seat_launchable_child_incomplete_unlaunched_position` | proven |
| I7 | wave_watch.py:1026-1047 | idle-seat flags on not-READY next member | `test_idle_seat_launchable_child_incomplete_not_ready_next_position` | proven |
| I8 | wave_watch.py:805-809 | stack PRs in position order, not discovery order | `test_resolve_pr_stack_groups_same_stack_position_order_not_append` | proven |
| I9 | wave_watch.py:872 | removed PRs included in changed_prs for grouping | `test_pr_set_changed_removed_pr_grouped_like_added` | proven |
| I10 | wave_watch.py:169 | git path routing vars scrubbed from gh child | `test_gh_scrub_removes_routing_vars_and_ledger_root` | proven |
| I11 | wave_watch.py:169 | GH_REPO, GIT_CONFIG family, and ledger root scrubbed | `test_gh_scrub_removes_routing_vars_and_ledger_root` | proven |

## Tests rewritten

None — all nine scoped tests bite on the axis named above.

## Code removals

None — no guarded element proved redundant or unreachable.

---

## I1 — _occupied_layer_positions

**neutralization:**

```python
def _occupied_layer_positions(batch_lanes, stack_number):
    occupied = set()
    for info in batch_lanes.values():
        ...
    return occupied
```
→
```python
def _occupied_layer_positions(batch_lanes, stack_number):
    return set()
```

**node id:** `plugins/superheroes/lib/tests/test_wave_watch.py::test_idle_seat_launchable_child_flag_present_and_absent`

**raw red:**
```
AssertionError: assert not True
FAILED .../test_idle_seat_launchable_child_flag_present_and_absent
1 failed in 0.80s
```

**raw green:**
```
.                                                                        [100%]
1 passed in 0.63s
```

## I2 — idle-seat flag append

**neutralization:** replace `flags.append({...})` with `pass`.

**node id:** `plugins/superheroes/lib/tests/test_wave_watch.py::test_idle_seat_launchable_child_incomplete_unlaunched_position`

**raw red:**
```
AssertionError: assert {'flag': 'idle-seat-launchable-child', ...} in []
FAILED .../test_idle_seat_launchable_child_incomplete_unlaunched_position
1 failed in 0.93s
```

**raw green:**
```
.                                                                        [100%]
1 passed in 0.72s
```

## I3 — no flags on layers-planned-unknown

**neutralization:** inject `flags.append(...)` before `continue` on the layers-unknown path.

**node id:** `plugins/superheroes/lib/tests/test_wave_watch.py::test_idle_seat_no_flags_layers_planned_unknown`

**raw red:**
```
AssertionError: assert [{'flag': 'idle-seat-launchable-child', ...}] == []
FAILED .../test_idle_seat_no_flags_layers_planned_unknown
1 failed in 0.64s
```

**raw green:**
```
.                                                                        [100%]
1 passed in 0.70s
```

## I4 — no flags on layers-planned-disagreed

**neutralization:** inject `flags.append(...)` before `continue` on the layers-disagreed path.

**node id:** `plugins/superheroes/lib/tests/test_wave_watch.py::test_idle_seat_no_flags_layers_planned_disagreed`

**raw red:**
```
AssertionError: assert [{'flag': 'idle-seat-launchable-child', ...}] == []
FAILED .../test_idle_seat_no_flags_layers_planned_disagreed
1 failed in 0.58s
```

**raw green:**
```
.                                                                        [100%]
1 passed in 0.54s
```

## I5 — no flags on membership-unresolved

**neutralization:** inject `flags.append(...)` before `continue` on the membership-unresolved path.

**node id:** `plugins/superheroes/lib/tests/test_wave_watch.py::test_idle_seat_no_flags_membership_unresolved`

**raw red:**
```
AssertionError: assert [{'flag': 'idle-seat-launchable-child', ...}] == []
FAILED .../test_idle_seat_no_flags_membership_unresolved
1 failed in 0.66s
```

**raw green:**
```
.                                                                        [100%]
1 passed in 1.04s
```

## I6 — flags before incomplete determination

**neutralization:** move the idle-seat flag loop to after the missing-position incomplete check.

**node id:** `plugins/superheroes/lib/tests/test_wave_watch.py::test_idle_seat_launchable_child_incomplete_unlaunched_position`

**raw red:**
```
AssertionError: assert {'flag': 'idle-seat-launchable-child', ...} in []
FAILED .../test_idle_seat_launchable_child_incomplete_unlaunched_position
1 failed in 1.38s
```

**raw green:**
```
.                                                                        [100%]
1 passed in 0.93s
```

## I7 — flags on not-READY next member

**neutralization:** same reorder as I6 (flags after incomplete check).

**node id:** `plugins/superheroes/lib/tests/test_wave_watch.py::test_idle_seat_launchable_child_incomplete_not_ready_next_position`

**raw red:**
```
AssertionError: assert {'flag': 'idle-seat-launchable-child', ...} in []
FAILED .../test_idle_seat_launchable_child_incomplete_not_ready_next_position
1 failed in 1.19s
```

**raw green:**
```
.                                                                        [100%]
1 passed in 0.79s
```

## I8 — stack position ordering

**neutralization:**

```python
        for position in sorted({pair[0] for pair in position_pairs}):
```
→
```python
        for position in sorted({pair[0] for pair in position_pairs}, reverse=True):
```

**node id:** `plugins/superheroes/lib/tests/test_wave_watch.py::test_resolve_pr_stack_groups_same_stack_position_order_not_append`

**raw red:**
```
AssertionError: assert [{'prs': [40, 30], ...}] == [{'prs': [30, 40], ...}]
FAILED .../test_resolve_pr_stack_groups_same_stack_position_order_not_append
1 failed in 0.54s
```

**raw green:**
```
.                                                                        [100%]
1 passed in 0.48s
```

## I9 — removed PRs in changed_prs

**neutralization:** `changed_prs = added + removed` → `changed_prs = added`.

**node id:** `plugins/superheroes/lib/tests/test_wave_watch.py::test_pr_set_changed_removed_pr_grouped_like_added`

**raw red:**
```
AssertionError: assert [] == [{'prs': [30, 40], 'stack': 100}]
FAILED .../test_pr_set_changed_removed_pr_grouped_like_added
1 failed in 1.72s
```

**raw green:**
```
.                                                                        [100%]
1 passed in 1.58s
```

## I10 — git path routing vars scrubbed

**neutralization:** `_gh_scrub_env` omits the seven `GIT_*` path vars from `keys`.

**node id:** `plugins/superheroes/lib/tests/test_wave_watch.py::test_gh_scrub_removes_routing_vars_and_ledger_root`

**raw red:**
```
AssertionError: assert 'GIT_CEILING_DIRECTORIES' not in {...}
FAILED .../test_gh_scrub_removes_routing_vars_and_ledger_root
1 failed in 2.52s
```

**raw green:**
```
.                                                                        [100%]
1 passed in 2.59s
```

## I11 — GH_REPO, GIT_CONFIG family, ledger root scrubbed

**neutralization:** `_gh_scrub_env` scrubs only git path vars (`roots=()`).

**node id:** `plugins/superheroes/lib/tests/test_wave_watch.py::test_gh_scrub_removes_routing_vars_and_ledger_root`

**raw red:**
```
AssertionError: assert 'GIT_CONFIG' not in {...}
FAILED .../test_gh_scrub_removes_routing_vars_and_ledger_root
1 failed in 2.70s
```

**raw green:**
```
.                                                                        [100%]
1 passed in 2.63s
```

## Command count

30 invocations (budget cap 36).
