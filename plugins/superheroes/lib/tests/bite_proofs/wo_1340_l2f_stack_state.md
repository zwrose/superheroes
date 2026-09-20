# WO-C (#1340 layer 2f) bite-proof — the stack completion signal in wave_watch.py

Per-guard bite proof for `stack-state-changed`: the per-stack completion snapshot, its head pin, its
`layersPlanned` agreement rule, its terminal-inclusive source, and its baseline advance.

**Register:** 5 guards — **3 proven, 2 UNPROVEN**. The two unproven ones are not an omission: the tests
that name those axes were run against a neutralized guard and **passed**, which means those tests cannot
fail when the guard is gone. That finding is the point of this record, and it is disclosed in the pull
request rather than smoothed over.

**Provenance:** the guarded code and its tests are cursor / composer-2.5 (WO-C, WO-C2, WO-C4). **This
record is orchestrator-produced**: the WO-C dispatch forfeited (`worktree-dirtied-by-attempt`, report
not gradeable) after its work landed and before it wrote the record it declared.

**Head:** every proof below was run at the final head `3a40a88f7e836067c81d6f565665681257d9cbd2`, in a
dedicated **detached** worktree, never in a tree a live seat was reading.

**Method:** the mutation is the smallest possible edit to the **guarded code** (never to the test),
applied through the host's edit action and reverted by the inverse edit. Each proving test is selected by
its **exact node id**, never `-k`. A proof whose red run failed for the wrong reason is not counted —
one first attempt at S2 raised `NameError` because the probe used a module the file does not import; it
was discarded as vacuous and re-run with a probe that exercises the guard (recorded below).

**Command** (referred to as *the command* below, with `<node-id>` replaced per guard):

```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest "<node-id>" -q
```

## Summary table

| ID | Guarded element (file:line) | Axis | Proving test | Verdict |
|---|---|---|---|---|
| S1 | wave_watch.py:1038 | complete requires **every** position `1..layersPlanned` | `test_stack_incomplete_missing_position` | proven |
| S2 | wave_watch.py:939 | the verdict is pinned to the pull request's **own current head** | `test_stack_incomplete_stale_sha` | proven |
| S3 | wave_watch.py:989 | a disagreed `layersPlanned` reads incomplete, never a picked value | `test_layers_planned_disagreed_incomplete` | proven |
| S4 | wave_watch.py:975 (`_layers_planned_for_stack`) | `layersPlanned` is sourced from **terminal** launches too | `test_layers_planned_read_from_terminal_launch` | **UNPROVEN — the test passes with the guard neutralized** |
| S5 | wave_watch.py:1086 | the baseline **advances** when the event fires | `test_baseline_advances_unchanged_complete_does_not_refire` | **UNPROVEN — the test passes with the guard neutralized** |

---

## S1 — complete requires every position

**neutralization** (`plugins/superheroes/lib/wave_watch.py`):

```python
            if position not in position_map or position not in ready_positions:
```
→
```python
            if False:
```

**node id:** `plugins/superheroes/lib/tests/test_wave_watch.py::test_stack_incomplete_missing_position`

**raw red:**
```
FAILED plugins/superheroes/lib/tests/test_wave_watch.py::test_stack_incomplete_missing_position
1 failed in 1.88s
```

**raw green:**
```
.                                                                        [100%]
1 passed in 1.08s
```

## S2 — the verdict is pinned to the pull request's own current head

**neutralization** — the head handed to the reader is taken from the body itself instead of from the
pull request's current head, which is exactly the loosening the guard exists to prevent:

```python
        verdict, vet_refusal = sc.read_vet_verdict(
            state["body"], state["headRefOid"],
        )
```
→
```python
        _probe_sha = None
        for _tok in state["body"].replace("·", " ").split():
            if len(_tok) == 40 and all(
                c in "0123456789abcdefABCDEF" for c in _tok
            ):
                _probe_sha = _tok
                break
        verdict, vet_refusal = sc.read_vet_verdict(
            state["body"], _probe_sha or state["headRefOid"],
        )
```

**node id:** `plugins/superheroes/lib/tests/test_wave_watch.py::test_stack_incomplete_stale_sha`

**raw red** (an assertion failure, not an error — the discarded first probe's `NameError` is recorded in
the method note above):
```
plugins/superheroes/lib/tests/test_wave_watch.py:4381: AssertionError
FAILED plugins/superheroes/lib/tests/test_wave_watch.py::test_stack_incomplete_stale_sha
1 failed in 0.93s
```

**raw green:**
```
.                                                                        [100%]
1 passed in 0.97s
```

## S3 — a disagreed `layersPlanned` reads incomplete

**neutralization:**

```python
        if len(layers_values) > 1:
```
→
```python
        if False:
```

**node id:** `plugins/superheroes/lib/tests/test_wave_watch.py::test_layers_planned_disagreed_incomplete`

**raw red:**
```
FAILED plugins/superheroes/lib/tests/test_wave_watch.py::test_layers_planned_disagreed_incomplete
1 failed in 1.86s
```

**raw green:**
```
.                                                                        [100%]
1 passed in 2.04s
```

## S4 — UNPROVEN: `layersPlanned` sourced from terminal launches

**neutralization** — the source is made to skip terminal lanes, which is the exact regression the axis
names:

```python
        if info.get("stack") != stack_number:
            continue
        layers_planned = info.get("layersPlanned")
```
→
```python
        if info.get("stack") != stack_number:
            continue
        if info.get("terminal"):
            continue
        layers_planned = info.get("layersPlanned")
```

**node id:** `plugins/superheroes/lib/tests/test_wave_watch.py::test_layers_planned_read_from_terminal_launch`

**result with the guard neutralized — still green:**
```
.                                                                        [100%]
1 passed in 2.07s
```

**What that means.** The test builds its lanes by folding the ledger directly and asserts that the
lane it calls terminal is the only carrier of `layersPlanned` — but the lane the fixture appends an
outcome event for is **not** marked terminal in the folded record the test then passes in, so skipping
terminal lanes changes nothing the test can see. The **product guard is correct** (the snapshot reads
every lane of the batch, and the sourcing function has no terminal filter); what is missing is a test
that can fail when that changes. **Owed:** a fixture whose terminal lane is genuinely terminal in the
fold, then this proof re-run.

## S5 — UNPROVEN: the baseline advances when the event fires

**neutralization:**

```python
    stack_state[0] = snapshot
    payload = dict(snapshot)
```
→
```python
    payload = dict(snapshot)
```

**node id:** `plugins/superheroes/lib/tests/test_wave_watch.py::test_baseline_advances_unchanged_complete_does_not_refire`

**result with the guard neutralized — still green:**
```
.                                                                        [100%]
1 passed in 2.13s
```

**What that means.** The test asserts only that the **first** arm fired and that `loop` ran one arm. It
never runs a second arm over an unchanged complete state, so a baseline that never advances is invisible
to it. **Owed:** a test that drives a second arm and asserts the event does not re-fire — the property
the axis comment claims.

## Restore receipt

`git status --porcelain` in the probe worktree after each restore: **empty**, checked after every guard
including both unproven ones.
