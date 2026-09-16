# WO-10 (#1269) bite-proof — spawn gate argv coherence + guard-refusal disposition

**Provenance:** cursor / composer-2.5

## Guarded elements

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| BP-10-1 | `_spawn_argv_coherence` in `_run_engine_files` | stored argv must match resolvedInputs canonical argv before Popen | `test_wo10_edge1_run_child_refuses_argv_snapshot_mismatch` |
| BP-10-2 | `_journal_spawn_guard_refusal` / supervision fold | guard refusal is terminal unrunnable, not a forfeit with retry | `test_wo10_edge3_supervise_folds_guard_refusal_terminal_unrunnable_no_retry` |

---

## BP-10-1 — argv/snapshot coherence

- **axis:** stored argv must match the seat snapshot's canonical argv before spawn

**neutralization** (`plugins/superheroes/lib/engine_dispatch.py`, `_run_engine_files` — removed coherence check block after allowlist gate):
```python
    # spawn_argv, coherence_err = _spawn_argv_coherence(opened, argv)
    # if coherence_err:
    #     _journal_spawn_guard_refusal(run_dir_real, attempt, coherence_err)
    #     return
    # argv = spawn_argv
```
(block deleted; `dispatch_path = _dispatch_path_from_opened(opened)` followed stored argv directly)

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_engine_dispatch.py::test_wo10_edge1_run_child_refuses_argv_snapshot_mismatch -q
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
___________ test_wo10_edge1_run_child_refuses_argv_snapshot_mismatch ___________

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-657/test_wo10_edge1_run_child_refu0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x108f72280>

    def test_wo10_edge1_run_child_refuses_argv_snapshot_mismatch(tmp_path, monkeypatch):
        ...
        ended = next(r for r in records if r.get("kind") == "attempt-ended" and r.get("attempt") == 1)
>       assert ended.get("guardRefusal") is True
E       AssertionError: assert None is True
E        +  where None = <built-in method get of dict object at 0x1091201c0>('guardRefusal')
E        +    where <built-in method get of dict object at 0x1091201c0> = {'activityStream': None, 'at': 1789542463.617376, 'attempt': 1, 'capSeconds': 900, ...}.get

plugins/superheroes/lib/tests/test_engine_dispatch.py:8707: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_wo10_edge1_run_child_refuses_argv_snapshot_mismatch
1 failed in 1.52s
```

**restore:** re-inserted the `_spawn_argv_coherence` block in `_run_engine_files` after the allowlist gate.

**restore receipt:** coherence check restored — `spawn_argv, coherence_err = _spawn_argv_coherence(opened, argv)` through `argv = spawn_argv` before `dispatch_path = _dispatch_path_from_opened(opened)`.

**raw green:**
```
.                                                                        [100%]
1 passed in 0.51s
```

---

## BP-10-2 — refusal is terminal, not a forfeit

- **axis:** spawn-gate refusal folds as terminal `unrunnable` without retry

**neutralization** (`plugins/superheroes/lib/engine_dispatch.py`, `_journal_spawn_guard_refusal` — removed `guardRefusal` key):
```python
        "refusal": reason[:_STDERR_TAIL], "at": time.time(),
        # "guardRefusal": True,  # bite-proof neutralization
```

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_engine_dispatch.py::test_wo10_edge3_supervise_folds_guard_refusal_terminal_unrunnable_no_retry -q
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
__ test_wo10_edge3_supervise_folds_guard_refusal_terminal_unrunnable_no_retry __

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-660/test_wo10_edge3_supervise_fold0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x1054d1310>

    def test_wo10_edge3_supervise_folds_guard_refusal_terminal_unrunnable_no_retry(tmp_path, monkeypatch):
        ...
        ended = next(r for r in records if r.get("kind") == "attempt-ended" and r.get("attempt") == 1)
>       assert ended.get("guardRefusal") is True
E       AssertionError: assert None is True
E        +  where None = <built-in method get of dict object at 0x108f39e80>('guardRefusal')
E        +    where <built-in method get of dict object at 0x108f39e80> = {'at': 1789542548.279451, 'attempt': 1, 'exit': 127, 'kind': 'attempt-ended', ...}.get

plugins/superheroes/lib/tests/test_engine_dispatch.py:8754: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_wo10_edge3_supervise_folds_guard_refusal_terminal_unrunnable_no_retry
1 failed in 0.88s
```

**restore:** re-added `"guardRefusal": True` to `_journal_spawn_guard_refusal`.

**restore receipt:** `"guardRefusal": True,` line restored inside the `attempt-ended` record dict in `_journal_spawn_guard_refusal`.

**raw green:**
```
.                                                                        [100%]
1 passed in 0.88s
```
