# FIX-D (#1340 layer 2g, adoption lane r2) bite-proof

Per-guard bite proof for advancing-monotonic clock helper preventing watcher-test hangs at deadline instead of hanging indefinitely.

**Register:** 4 guards — **4 proven**, **0 unproven**.

**Provenance:** cursor / composer-2.5 (FIX-D amendment, layer 2g adoption lane r2)

**Method:** set `payload = None  # bite-proof FIX-D neutralization` in place of the event-payload builder call in `run()`, reverted by the inverse edit.

**Command** (referred to as *the command* below, with `<node-id>` replaced per guard):

```
perl -e 'alarm shift; exec @ARGV' 120 /usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest -p no:cacheprovider -q "<node-id>"
```

## D-0 — the frozen clock hangs (contrast, orchestrator-run at f4079ccc)

```
command: perl -e 'alarm shift; exec @ARGV' 30 /usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-probe -m pytest -p no:cacheprovider -q "plugins/superheroes/lib/tests/test_wave_watch.py::test_lane_terminal_makes_zero_gh_run_calls"
exit=142 elapsed=30s   (killed by the alarm; pytest printed no result: the test hung)
```

This is why the clock changed: under the frozen monotonic, neutralizing only the expected event's builder still let a lower-precedence event fire on the first tick, so the test failed (or hung) without ever reaching the deadline.

## D-1 — lane-terminal payload builder

**neutralization** (shared, in `run()` under `# Every non-timer member of EVENT_PRECEDENCE has a builder.`):

```python
                payload = _EVENT_PAYLOAD_BUILDERS[event](event_ctx)
```
→
```python
                payload = None  # bite-proof FIX-D neutralization
```

**node id:** `plugins/superheroes/lib/tests/test_wave_watch.py::test_lane_terminal_makes_zero_gh_run_calls`

**raw red:**
```
E       AssertionError: assert 'timer' == 'lane-terminal'
FAILED plugins/superheroes/lib/tests/test_wave_watch.py::test_lane_terminal_makes_zero_gh_run_calls
4 failed in 2.48s
```

**restore:** `payload = None  # bite-proof FIX-D neutralization` → `payload = _EVENT_PAYLOAD_BUILDERS[event](event_ctx)`

**raw green:**
```
....                                                                     [100%]
4 passed in 1.16s
```

## D-2 — lane-blocked payload builder

**neutralization** (shared, in `run()` under `# Every non-timer member of EVENT_PRECEDENCE has a builder.`):

```python
                payload = _EVENT_PAYLOAD_BUILDERS[event](event_ctx)
```
→
```python
                payload = None  # bite-proof FIX-D neutralization
```

**node id:** `plugins/superheroes/lib/tests/test_wave_watch.py::test_lane_blocked_makes_zero_gh_run_calls`

**raw red:**
```
E       AssertionError: assert 'timer' == 'lane-blocked'
FAILED plugins/superheroes/lib/tests/test_wave_watch.py::test_lane_blocked_makes_zero_gh_run_calls
4 failed in 2.48s
```

**restore:** `payload = None  # bite-proof FIX-D neutralization` → `payload = _EVENT_PAYLOAD_BUILDERS[event](event_ctx)`

**raw green:**
```
....                                                                     [100%]
4 passed in 1.16s
```

## D-3 — builder-exited payload builder

**neutralization** (shared, in `run()` under `# Every non-timer member of EVENT_PRECEDENCE has a builder.`):

```python
                payload = _EVENT_PAYLOAD_BUILDERS[event](event_ctx)
```
→
```python
                payload = None  # bite-proof FIX-D neutralization
```

**node id:** `plugins/superheroes/lib/tests/test_wave_watch.py::test_builder_exited_makes_zero_gh_run_calls`

**raw red:**
```
E       AssertionError: assert 'timer' == 'builder-exited'
FAILED plugins/superheroes/lib/tests/test_wave_watch.py::test_builder_exited_makes_zero_gh_run_calls
4 failed in 2.48s
```

**restore:** `payload = None  # bite-proof FIX-D neutralization` → `payload = _EVENT_PAYLOAD_BUILDERS[event](event_ctx)`

**raw green:**
```
....                                                                     [100%]
4 passed in 1.16s
```

## D-4 — pr-set-changed payload builder

**neutralization** (shared, in `run()` under `# Every non-timer member of EVENT_PRECEDENCE has a builder.`):

```python
                payload = _EVENT_PAYLOAD_BUILDERS[event](event_ctx)
```
→
```python
                payload = None  # bite-proof FIX-D neutralization
```

**node id:** `plugins/superheroes/lib/tests/test_wave_watch.py::test_suppressed_terminal_lane_polls_prs_for_pr_set_changed`

**raw red:**
```
E       AssertionError: assert 'timer' == 'pr-set-changed'
FAILED plugins/superheroes/lib/tests/test_wave_watch.py::test_suppressed_terminal_lane_polls_prs_for_pr_set_changed
4 failed in 2.48s
```

**restore:** `payload = None  # bite-proof FIX-D neutralization` → `payload = _EVENT_PAYLOAD_BUILDERS[event](event_ctx)`

**raw green:**
```
....                                                                     [100%]
4 passed in 1.16s
```

The per-builder neutralization in the first version of this record was vacuous for the clock, because a lower event fired first; it is replaced by this one.
