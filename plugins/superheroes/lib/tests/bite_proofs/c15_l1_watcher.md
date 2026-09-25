# C15 layer 1 watcher bite-proof — `wave_watch.py`

**Provenance:** cursor / composer-2.5.

## Summary

| ID | Axis | Proving test | Verdict |
|---|---|---|---|
| E3 | `run` never sleeps | `test_run_is_one_shot_against_quiet_live_lane` | proven |

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
