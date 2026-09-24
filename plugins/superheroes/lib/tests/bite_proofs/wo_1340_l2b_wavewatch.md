# WO-C (#1340 layer 2b) bite-proof — `wave_watch.py` stack grouping

Per-guard bite proof for `plugins/superheroes/lib/wave_watch.py` stack-resolution walk:
each `# bite-axis:` clause is neutralized in source, the proving test goes red alone,
then the clause is restored and the test goes green.

## BP1 — DEADLINE guard

**Guarded element:** `wave_watch.py` `_resolve_pr_stack_groups` deadline check — axis:
remaining below `_MIN_PR_POLL_SECONDS` stops the walk and marks `stack-signal-unavailable`;
no further membership reads start.

**Neutralization:** replaced `if remaining < _MIN_PR_POLL_SECONDS:` with
`if False and remaining < _MIN_PR_POLL_SECONDS:` on the walk guard (lines ~758).

**Proving test:** `test_pr_set_changed_exhausted_deadline_stops_walk_no_reader_after`

**Red run:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
______ test_pr_set_changed_exhausted_deadline_stops_walk_no_reader_after _______
plugins/superheroes/lib/tests/test_wave_watch.py:3545: in test_pr_set_changed_exhausted_deadline_stops_walk_no_reader_after
    assert reader_calls == [30]
E   assert [30, 40] == [30]
E     
E     Left contains one more item: 40
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch.py::test_pr_set_changed_exhausted_deadline_stops_walk_no_reader_after
1 failed in 1.43s
```

**Restore:** reverted to `if remaining < _MIN_PR_POLL_SECONDS:`

**Restore receipt:** `if remaining < _MIN_PR_POLL_SECONDS:`

**Green run:**
```
.                                                                        [100%]
1 passed in 1.39s
```

## BP2 — COVERED skip

**Guarded element:** `wave_watch.py` `_resolve_pr_stack_groups` covered-pr skip — axis:
a changed PR whose stack was already read costs zero extra `membership_reader` calls.

**Neutralization:** replaced `if pr_num in covered_prs:` with
`if False and pr_num in covered_prs:` (lines ~751).

**Proving test:** `test_pr_set_changed_second_member_in_stack_costs_no_extra_reader_call`

**Red run:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
____ test_pr_set_changed_second_member_in_stack_costs_no_extra_reader_call _____
plugins/superheroes/lib/tests/test_wave_watch.py:3473: in test_pr_set_changed_second_member_in_stack_costs_no_extra_reader_call
    assert calls == [30]
E   assert [30, 40] == [30]
E     
E     Left contains one more item: 40
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch.py::test_pr_set_changed_second_member_in_stack_costs_no_extra_reader_call
1 failed in 1.35s
```

**Restore:** reverted to `if pr_num in covered_prs:`

**Restore receipt:** `if pr_num in covered_prs:`

**Green run:**
```
.                                                                        [100%]
1 passed in 1.58s
```

## BP3 — two-stack grouping

**Guarded element:** `wave_watch.py` `_resolve_pr_stack_groups` stack recording — axis:
a successful membership read records the whole stack in `stacks` with every member in
position order.

**Neutralization:** replaced `if stack_number not in stack_numbers_seen:` with
`if False and stack_number not in stack_numbers_seen:` (lines ~771).

**Proving test:** `test_pr_set_changed_two_stacks_groups_all_members_in_position_order`

**Red run:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_____ test_pr_set_changed_two_stacks_groups_all_members_in_position_order ______
plugins/superheroes/lib/tests/test_wave_watch.py:3449: in test_pr_set_changed_two_stacks_groups_all_members_in_position_order
    assert result["stacks"] == [
E   AssertionError: assert [] == [{'prs': [50,...'stack': 200}]
E     
E     Right contains 2 more items, first extra item: {'prs': [50, 51], 'stack': 100}
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch.py::test_pr_set_changed_two_stacks_groups_all_members_in_position_order
1 failed in 1.61s
```

**Restore:** reverted to `if stack_number not in stack_numbers_seen:`

**Restore receipt:** `if stack_number not in stack_numbers_seen:`

**Green run:**
```
.                                                                        [100%]
1 passed in 1.52s
```
