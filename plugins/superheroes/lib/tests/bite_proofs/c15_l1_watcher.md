# C15 layer 1 watcher bite-proof — `wave_watch.py`

**Provenance:** cursor / composer-2.5.

## Summary

| ID | Axis | Proving test | Verdict |
|---|---|---|---|
| E1 | loop passes over benign `pr-set-changed` | `test_loop_passes_over_pr_set_change` | proven |
| E3 | `run` never sleeps | `test_run_is_one_shot_against_quiet_live_lane` | proven |
| E4 | PR baseline advances on fire | `test_loop_two_distinct_pr_set_changes_passed_over` | proven |
| E5 | loop exits on a stack change carrying the idle-seat flag | `test_loop_stack_state_idle_seat_exits_otherwise_passes_over` | proven |

---

## E1 — classifier (`_loop_exits_on`)

**neutralization:** insert `return True` as the first statement of `_loop_exits_on` (every wake exits).

**raw red** (tail; full: `/private/tmp/c15-wo-a/bp-e1-red.txt`):
```
>       assert result["event"] == "lane-terminal"
E       AssertionError: assert 'pr-set-changed' == 'lane-terminal'
FAILED ...::test_loop_passes_over_pr_set_change
EXIT=1
```

**restore:** remove that inserted line.

**raw green** (tail; full: `/private/tmp/c15-wo-a/bp-e1-green.txt`):
```
1 passed in 0.34s
EXIT=0
```

---

## E3 — one-shot `run`

**neutralization:** insert `time.sleep(1)  # bite-proof E3` in `run()` after `_evaluate_tick`.

**raw red** (tail; full: `/private/tmp/c15-wo-a/bp-e3-red.txt`):
```
E         Left contains one more item: 1
FAILED ...::test_run_is_one_shot_against_quiet_live_lane
EXIT=1
```

**restore:** remove `time.sleep(1)` line.

**raw green:** `/private/tmp/c15-wo-a/bp-e3-green.txt` — `1 passed`, `EXIT=0`.

---

## E4 — PR baseline advance

**neutralization:** remove `pr_state[0] = pr_set` before fire return in `_evaluate_pr_set_changed`.

**raw red** (tail; full: `/private/tmp/c15-wo-a/bp-e4-red.txt`):
```
E   assert 3 == 2
FAILED ...::test_loop_two_distinct_pr_set_changes_passed_over
EXIT=1
```

**restore:** reinsert `pr_state[0] = pr_set`.

**raw green:** `/private/tmp/c15-wo-a/bp-e4-green.txt` — `1 passed`, `EXIT=0`.

---

## E5 — idle-seat arm of the classifier

**neutralization:** in `_loop_exits_on`, the `return True` inside the `FLAG_IDLE_SEAT_LAUNCHABLE_CHILD` check → `return False`.

**raw red** (a fenced block):
```
E       AssertionError: assert 'timer' == 'stack-state-changed'
FAILED ...::test_loop_stack_state_idle_seat_exits_otherwise_passes_over
1 failed in 13.71s
```

**restore:** the inverse edit (`return False` → `return True`).

**raw green:** `1 passed` (run together with `test_stack_state_changed_emits_flags_on_first_arm_with_idle_seat`: `2 passed in 9.95s`).

The test carries a `max_total_seconds` ceiling on a fake monotonic clock, so the neutralized arm fails at the ceiling (`timer`) instead of hanging.
