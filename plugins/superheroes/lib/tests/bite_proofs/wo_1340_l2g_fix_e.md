# FIX-E (#1340 layer 2g, adoption lane r3) bite-proof

Per-guard bite proof for stack-state baseline advance on fire in `_payload_stack_state_changed`.

**Register:** 1 guard — **1 proven**, **0 unproven**.

**Provenance:** cursor / composer-2.5 (FIX-E, layer 2g adoption lane r3)

**Method:** replace `stack_state[0] = snapshot` with `pass  # bite-proof FIX-E neutralization` under the loop-invocation comment in `_payload_stack_state_changed`, reverted by the inverse edit.

**Command:**

```
perl -e 'alarm shift; exec @ARGV' 120 /usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest -p no:cacheprovider -q "plugins/superheroes/lib/tests/test_wave_watch.py::test_baseline_advances_unchanged_complete_does_not_refire"
```

## E-1 — stack-state baseline advance

**neutralization** (in `_payload_stack_state_changed` under `# loop() returns on this event, so a new loop invocation starts without one.`):

```python
    stack_state[0] = snapshot
```
→
```python
    pass  # bite-proof FIX-E neutralization
```

**node id:** `plugins/superheroes/lib/tests/test_wave_watch.py::test_baseline_advances_unchanged_complete_does_not_refire`

**raw red:**
```
E       AssertionError: assert 'stack-state-changed' != 'stack-state-changed'
FAILED plugins/superheroes/lib/tests/test_wave_watch.py::test_baseline_advances_unchanged_complete_does_not_refire
1 failed in 3.97s
```

**restore:** `pass  # bite-proof FIX-E neutralization` → `stack_state[0] = snapshot`

**raw green:**
```
.                                                                        [100%]
1 passed in 6.25s
```
