# WO-B (#1340 layer 2f) bite-proof — the dependency gate in launcher.py

Per-guard bite proof for `_apply_dependency_gate`, the refusal `dependency-open-ready-pr` and its
read-failure sibling `dependency-read-unavailable`.

**Register:** 4 guards — base-equality, READY-only, open-only, verdict-refusal-refuses.

**Provenance:** the guarded code is cursor / composer-2.5 (WO-B). **This record is
orchestrator-produced**: that dispatch forfeited (`worktree-dirtied-by-attempt`, its report not
gradeable) after the work landed and before it wrote the record it declared, so the orchestrator ran
every proof itself rather than re-dispatching onto a dirtied tree. Disclosed in the pull request.

**Head:** every proof below was run at the final head `3a40a88f7e836067c81d6f565665681257d9cbd2`, in a
dedicated **detached** worktree, never in a tree a live seat was reading.

**Method:** the mutation is the smallest possible edit to the **guarded code** (never to the test),
applied through the host's edit action and reverted by the inverse edit. Each proving test is selected
by its **exact node id**, never `-k`.

**Command** (referred to as *the command* below, with `<node-id>` replaced per guard):

```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest "<node-id>" -q
```

## Summary table

| ID | Guarded element (file:line) | Axis | Proving test | Verdict |
|---|---|---|---|---|
| D1 | launcher.py:1584 | the resolved base must equal the dependency's current head | `test_dependency_gate_ready_base_mismatch_refuses` | proven |
| D2 | launcher.py:1577 | only `VERDICT_READY` gates; every other verdict passes | `test_dependency_gate_not_ready_passes` | proven |
| D3 | launcher.py:1562 | only an **open** dependency is gated | `test_dependency_gate_merged_passes_not_gated` | proven |
| D4 | launcher.py:1570 | an unreadable verdict **refuses**, never passes as absent | `test_dependency_gate_vet_refusal_refuses` | proven |

---

## D1 — the resolved base must equal the dependency's current head

**neutralization** (`plugins/superheroes/lib/launcher.py`):

```python
    if resolved_base_commit == head_sha:
```
→
```python
    if True:
```

**node id:** `plugins/superheroes/lib/tests/test_launcher.py::test_dependency_gate_ready_base_mismatch_refuses`

**raw red:**
```
FAILED plugins/superheroes/lib/tests/test_launcher.py::test_dependency_gate_ready_base_mismatch_refuses
1 failed in 22.06s
```

**raw green** after the inverse edit:
```
.                                                                        [100%]
1 passed in 0.79s
```

## D2 — only `VERDICT_READY` gates

**neutralization:**

```python
    if verdict != stack_check.VERDICT_READY:
```
→
```python
    if False:
```

**node id:** `plugins/superheroes/lib/tests/test_launcher.py::test_dependency_gate_not_ready_passes`

**raw red:**
```
FAILED plugins/superheroes/lib/tests/test_launcher.py::test_dependency_gate_not_ready_passes
1 failed in 1.80s
```

**raw green:**
```
.                                                                        [100%]
1 passed in 1.86s
```

## D3 — only an open dependency is gated

**neutralization:**

```python
    if pr_state["state"] != "OPEN":
```
→
```python
    if False:
```

**node id:** `plugins/superheroes/lib/tests/test_launcher.py::test_dependency_gate_merged_passes_not_gated`

**raw red:**
```
FAILED plugins/superheroes/lib/tests/test_launcher.py::test_dependency_gate_merged_passes_not_gated
1 failed in 1.81s
```

**raw green:**
```
.                                                                        [100%]
1 passed in 1.97s
```

## D4 — an unreadable verdict refuses

**neutralization:**

```python
    if vet_refusal is not None:
```
→
```python
    if False:
```

**node id:** `plugins/superheroes/lib/tests/test_launcher.py::test_dependency_gate_vet_refusal_refuses`

**raw red:**
```
FAILED plugins/superheroes/lib/tests/test_launcher.py::test_dependency_gate_vet_refusal_refuses
1 failed in 22.23s
```

**raw green:**
```
.                                                                        [100%]
1 passed in 2.25s
```

## Restore receipt

`git status --porcelain` in the probe worktree after each restore: **empty** (checked after every
guard, and last after D4).
