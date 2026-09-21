# FIX-D (#1340 layer 2g, adoption lane r2) bite-proof

Per-guard bite proof for advancing-monotonic clock helper preventing watcher-test hangs.

**Register:** 4 guards — **4 proven**, **0 unproven**.

**Provenance:** cursor / composer-2.5 (FIX-D, layer 2g adoption lane r2)

**Method:** insert `return None  # bite-proof FIX-D neutralization` as the first statement of the payload builder the test expects, reverted by the inverse edit.

**Command** (referred to as *the command* below, with `<node-id>` replaced per guard):

```
perl -e 'alarm shift; exec @ARGV' 120 /usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest -p no:cacheprovider -q "<node-id>"
```

## D-1 — lane-terminal payload builder

**neutralization:** first statement of `_payload_lane_terminal`:

```python
def _payload_lane_terminal(ctx):
    launches = _filter_suppressed_launches(
```
→
```python
def _payload_lane_terminal(ctx):
    return None  # bite-proof FIX-D neutralization
    launches = _filter_suppressed_launches(
```

**node id:** `plugins/superheroes/lib/tests/test_wave_watch.py::test_lane_terminal_makes_zero_gh_run_calls`

**raw red:**
```
AssertionError: assert 'builder-exited' == 'lane-terminal'
FAILED .../test_lane_terminal_makes_zero_gh_run_calls
1 failed in 0.51s
```

**restore:** remove `return None  # bite-proof FIX-D neutralization` line from `_payload_lane_terminal`

**raw green:**
```
.                                                                        [100%]
1 passed in 0.45s
```

## D-2 — lane-blocked payload builder

**neutralization:** first statement of `_payload_lane_blocked`:

```python
def _payload_lane_blocked(ctx):
    launches = _filter_suppressed_launches(
```
→
```python
def _payload_lane_blocked(ctx):
    return None  # bite-proof FIX-D neutralization
    launches = _filter_suppressed_launches(
```

**node id:** `plugins/superheroes/lib/tests/test_wave_watch.py::test_lane_blocked_makes_zero_gh_run_calls`

**raw red:**
```
AssertionError: assert 'builder-exited' == 'lane-blocked'
FAILED .../test_lane_blocked_makes_zero_gh_run_calls
1 failed in 0.51s
```

**restore:** remove `return None  # bite-proof FIX-D neutralization` line from `_payload_lane_blocked`

**raw green:**
```
.                                                                        [100%]
1 passed in 0.45s
```

## D-3 — builder-exited payload builder

**neutralization:** first statement of `_payload_builder_exited`:

```python
def _payload_builder_exited(ctx):
    exited = ctx["exited"]
```
→
```python
def _payload_builder_exited(ctx):
    return None  # bite-proof FIX-D neutralization
    exited = ctx["exited"]
```

**node id:** `plugins/superheroes/lib/tests/test_wave_watch.py::test_builder_exited_makes_zero_gh_run_calls`

**raw red:**
```
AssertionError: assert 'timer' == 'builder-exited'
FAILED .../test_builder_exited_makes_zero_gh_run_calls
1 failed in 0.78s
```

**restore:** remove `return None  # bite-proof FIX-D neutralization` line from `_payload_builder_exited`

**raw green:**
```
.                                                                        [100%]
1 passed in 0.45s
```

## D-4 — pr-set-changed payload builder

**neutralization:** first statement of `_payload_pr_set_changed`:

```python
def _payload_pr_set_changed(ctx):
    pr_change = _evaluate_pr_set_changed(
```
→
```python
def _payload_pr_set_changed(ctx):
    return None  # bite-proof FIX-D neutralization
    pr_change = _evaluate_pr_set_changed(
```

**node id:** `plugins/superheroes/lib/tests/test_wave_watch.py::test_suppressed_terminal_lane_polls_prs_for_pr_set_changed`

**raw red:**
```
AssertionError: assert 'timer' == 'pr-set-changed'
FAILED .../test_suppressed_terminal_lane_polls_prs_for_pr_set_changed
1 failed in 0.76s
```

**restore:** remove `return None  # bite-proof FIX-D neutralization` line from `_payload_pr_set_changed`

**raw green:**
```
.                                                                        [100%]
1 passed in 0.49s
```
