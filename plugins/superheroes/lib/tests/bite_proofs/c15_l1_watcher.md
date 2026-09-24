# C15 layer 1 watcher bite-proof — `wave_watch.py`

**Provenance:** cursor / composer-2.5.

## Summary

| ID | Axis | Proving test | Verdict |
|---|---|---|---|
| E1 | loop passes over benign `pr-set-changed` | `test_loop_passes_over_pr_set_change` | proven |
| E3 | `run` never sleeps | `test_run_is_one_shot_against_quiet_live_lane` | proven |
| E4 | PR baseline advances on fire | `test_loop_two_distinct_pr_set_changes_passed_over` | proven |

---

## E1 — classifier (`_loop_exits_on`)

**neutralization:** `return result.get("event") not in BENIGN_EVENTS` → `return True  # bite-proof E1`

**raw red** (tail; full: `/private/tmp/c15-wo-a/bp-e1-red.txt`):
```
>       assert result["event"] == "lane-terminal"
E       AssertionError: assert 'pr-set-changed' == 'lane-terminal'
FAILED ...::test_loop_passes_over_pr_set_change
EXIT=1
```

**restore:** inverse perl replace restoring `BENIGN_EVENTS` branch.

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
