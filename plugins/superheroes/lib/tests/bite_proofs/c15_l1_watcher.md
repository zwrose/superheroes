# C15 layer 1 watcher bite-proof — `wave_watch.py`

**Provenance:** cursor / composer-2.5.

## Summary

| ID | Axis | Proving test | Verdict |
|---|---|---|---|
| E1 | loop passes over benign `pr-set-changed` | `test_loop_passes_over_pr_set_change` | proven |
| 1c-E2 | second live loop refused at flock | `test_second_loop_on_same_batch_refuses` | proven |
| E3 | `run` never sleeps | `test_run_is_one_shot_against_quiet_live_lane` | proven |
| E4 | PR baseline advances on fire | `test_loop_two_distinct_pr_set_changes_passed_over` | proven |
| E5 | loop exits on a stack change carrying the idle-seat flag | `test_loop_stack_state_idle_seat_exits_otherwise_passes_over` | proven |
| 1c-E5 | lock-unavailable refusal fails closed (`loop-lock-unavailable`, `arms: 0`) | `test_loop_lock_unavailable_flock_oserror` | proven |
| 1c-E6 | non-regular lock file refused | `test_loop_lock_unavailable_non_regular_lock_file` | proven |
| 1c-E7 | lock released on normal exit | `test_loop_lock_released_allows_sequential_loops` | proven |
| 1c-E8 | passedOver / passedOverCount drift pins | `test_wave_watch_doc_pins_the_suppression_wire_contract` | proven |

Rows prefixed `1c-` are layer 1c's lock proofs (the issue names them E2, E5 and E6; the prefix keeps them apart from layer 1b's E5).

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

## 1c-E2 — start check (flock contention)

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

---

## 1c-E5 — lock-unavailable refusal fails closed

**neutralization:** in `_acquire_loop_lock`, the `except OSError` fallback after `fcntl.flock` (non-`EWOULDBLOCK` / non-`EAGAIN`) — replace `return None, _loop_lock_refusal(f"flock:...")` with `pass`.

**raw red** (tail; full: `/private/tmp/claude-501/-Users-zwrose--superheroes-worktrees-superheroes-issue-1423-3cb6374d4cb5ed6b/51b9dabe-506e-48d3-ac54-e23a3a57e7a4/scratchpad/bp-fix/1c-e5-red.txt`):
```
>       assert result["reason"] == ww.REFUSAL_LOOP_LOCK_UNAVAILABLE
E       AssertionError: assert 'test-violation' == 'loop-lock-unavailable'
FAILED ...::test_loop_lock_unavailable_flock_oserror
EXIT=1
```

**restore:** reinstate the `return None, _loop_lock_refusal(f"flock:...")` arm.

**raw green** (tail; full: `/private/tmp/claude-501/-Users-zwrose--superheroes-worktrees-superheroes-issue-1423-3cb6374d4cb5ed6b/51b9dabe-506e-48d3-ac54-e23a3a57e7a4/scratchpad/bp-fix/1c-e5-green.txt`):
```
1 passed in 2.21s
EXIT=0
```

---

## 1c-E6 — `S_ISREG` on lock file

**neutralization:** remove `S_ISREG` refusal block in `_acquire_loop_lock`.

**fixture seam:** test plants a regular lock file (open succeeds everywhere), calls `_acquire_loop_lock` directly (the neutralized function), tracks only the batch's `wave-watch-locks/<sha256>.lock` open by exact name (not every `*.lock` under the ledger), then `monkeypatch` on `wave_watch.os.fstat` reports `S_IFIFO` for that fd so the guard is exercised without OS-specific `open` refusal; `flock` is wrapped to assert it is not reached when the guard holds.

**raw red** (tail; full: `/private/tmp/c15-wo-a/bp-e6-red.txt`):
```
>       assert lock_fd is None
E       AssertionError: assert 16 is None
FAILED ...::test_loop_lock_unavailable_non_regular_lock_file
EXIT=1
```

**restore:** reinstate `S_ISREG` refusal block.

**raw green** (tail; full: `/private/tmp/c15-wo-a/bp-e6-green.txt`):
```
1 passed in 0.34s
EXIT=0
```

---

## 1c-E7 — lock release on normal exit

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

## 1c-E8 — passedOver / passedOverCount drift pins

**neutralization:** in `wave_watch.py`, change `RESULT_KEY_PASSED_OVER` from `"passedOver"` to `"passedOverX"` (in-place).

**raw red** (tail; full: `/private/tmp/claude-501/-Users-zwrose--superheroes-worktrees-superheroes-issue-1423-3cb6374d4cb5ed6b/51b9dabe-506e-48d3-ac54-e23a3a57e7a4/scratchpad/bp-fix/1c-e8-red.txt`):
```
E       AssertionError: reference/wave-watch.md missing token(s): ['`passedOverX`']
FAILED ...::test_wave_watch_doc_pins_the_suppression_wire_contract
EXIT=1
```

**restore:** the inverse edit (`"passedOverX"` → `"passedOver"`).

**raw green** (tail; full: `/private/tmp/claude-501/-Users-zwrose--superheroes-worktrees-superheroes-issue-1423-3cb6374d4cb5ed6b/51b9dabe-506e-48d3-ac54-e23a3a57e7a4/scratchpad/bp-fix/1c-e8-green.txt`):
```
1 passed in 0.36s
EXIT=0
```
