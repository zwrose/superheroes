# C15 layer 1 watcher bite-proof — `wave_watch.py`

**Provenance:** cursor / composer-2.5.

## Summary

| ID | Axis | Proving test | Verdict |
|---|---|---|---|
| E1 | loop passes over benign `pr-set-changed` | `test_loop_passes_over_pr_set_change` | proven |
| E2 | second live loop refused at flock | `test_second_loop_on_same_batch_refuses` | proven |
| E3 | `run` never sleeps | `test_run_is_one_shot_against_quiet_live_lane` | proven |
| E4 | PR baseline advances on fire | `test_loop_two_distinct_pr_set_changes_passed_over` | proven |
| E5 | lock released on normal exit | `test_loop_lock_released_allows_sequential_loops` | proven |
| E6 | non-regular lock file refused | `test_loop_lock_unavailable_non_regular_lock_file` | proven |

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

## E2 — start check (flock contention)

**neutralization:** `fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)` → `pass  # bite-proof E2`

**raw red** (tail; full: `/private/tmp/c15-wo-a/bp-e2-red.txt`):
```
>       assert result["reason"] == ww.REFUSAL_LOOP_ALREADY_LIVE
E       AssertionError: assert 'test-violation' == 'loop-already-live'
FAILED ...::test_second_loop_on_same_batch_refuses
EXIT=1
```

**restore:** `pass` → `fcntl.flock(...)`.

**raw green:** `/private/tmp/c15-wo-a/bp-e2-green.txt` — `1 passed`, `EXIT=0`.

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

## E5 — lock release on normal exit

**neutralization:** omit `_release_loop_lock(lock_fd)` on the `_loop_exits_on` success path.

**raw red** (tail; full: `/private/tmp/c15-wo-a/bp-e5-red.txt`):
```
>       assert second["ok"] is True
E       assert False is True
FAILED ...::test_loop_lock_released_allows_sequential_loops
EXIT=1
```

**restore:** reinstate `_release_loop_lock(lock_fd)`.

**raw green:** `/private/tmp/c15-wo-a/bp-e5-green.txt` — `1 passed`, `EXIT=0`.

---

## E6 — `S_ISREG` on lock file

**neutralization:** remove `S_ISREG` refusal block in `_acquire_loop_lock`.

**fixture seam:** test plants a regular lock file (open succeeds everywhere), then `monkeypatch` on `wave_watch.os.fstat` reports `S_IFIFO` for that inode so the guard is exercised without OS-specific `open` refusal; `flock` is wrapped to assert it is not reached when the guard holds.

**raw red** (tail; full: `/private/tmp/c15-wo-a/bp-e6-red.txt`):
```
>       assert flock_calls == []
E       AssertionError: assert [(3, 6)] == []
FAILED ...::test_loop_lock_unavailable_non_regular_lock_file
EXIT=1
```

**restore:** reinstate `S_ISREG` refusal block.

**raw green** (tail; full: `/private/tmp/c15-wo-a/bp-e6-green.txt`):
```
1 passed in 0.34s
EXIT=0
```
