# WO-L3AB-S (#1273) bite-proof — stdout completion stamp

**Provenance:** cursor / composer-2.5 (implementer).

## Guarded elements

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| BP-S1 | `_observe_stdout_completion` terminal path | terminal observation must parse when size is unchanged since the prior poll | `test_completion_producer_stdout_trailing_non_result_line_stamps_at_terminal` |
| BP-S2 | `_stdout_last_line_is_result_event` line-start scan | large result lines must be visible to non-terminal pre-check before the cap | `test_completion_producer_stdout_large_result_before_cap_admits_after_timeout` |

---

## BP-S1 — unconditional terminal observation

- **axis:** a trailing non-result stdout line must not block terminal stamping

**neutralization** (`plugins/superheroes/lib/engine_dispatch.py`, `_observe_stdout_completion`):

```python
    prev = obs_state.get("prev_size", 0)
    # bite-proof BP-S1 neutralization: size-unchanged guard applies on terminal too
    if size == prev:
        return
    obs_state["prev_size"] = size
    if not terminal and not _stdout_last_line_is_result_event(stdout_path):
        return
```

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_engine_dispatch.py::test_completion_producer_stdout_trailing_non_result_line_stamps_at_terminal -q
```

**raw red** (exit 1):
```
F                                                                        [100%]
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_completion_producer_stdout_trailing_non_result_line_stamps_at_terminal
1 failed, 1 passed in 3.49s
```
(assertion: `assert 'resultCompleteAt' in ended`)

**T1/T2 under same neutralization:** `test_completion_producer_stdout_large_result_immediate_exit_admits` stayed green (line-start scan stamps before terminal).

**restore** (`plugins/superheroes/lib/engine_dispatch.py`, `_observe_stdout_completion`):

```python
    prev = obs_state.get("prev_size", 0)
    if not terminal:
        if size == prev:
            return
        obs_state["prev_size"] = size
        if not _stdout_last_line_is_result_event(stdout_path):
            return
    else:
        obs_state["prev_size"] = size
```

**restore receipt:** post-restore `git diff --stat` matches pre-probe worktree edits on order files only.

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 1.95s
```

---

## BP-S2 — line-start scan

- **axis:** a ≥20 KiB result line must be detected on non-terminal polls, not only at terminal after the cap

**neutralization** (`plugins/superheroes/lib/engine_dispatch.py`, `_stdout_last_line_is_result_event`): fixed 8192-byte tail window restored (replaces backward line-start scan).

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_engine_dispatch.py::test_completion_producer_stdout_large_result_before_cap_admits_after_timeout -q
```

**raw red** (exit 1):
```
F                                                                        [100%]
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_completion_producer_stdout_large_result_before_cap_admits_after_timeout
1 failed in 6.97s
```
(assertion: `assert grade.get("ok") is True` with `admissionDetail': 'result-completion-after-deadline'`)

**restore:** backward line-start scan body restored in `_stdout_last_line_is_result_event` (64 KiB chunks, bounded by `MAX_STDOUT_CAPTURE`).

**restore receipt:** post-restore `git diff --stat` matches pre-probe worktree edits on order files only.

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 2.15s
```
