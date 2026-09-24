# WO-L3AB-B (#1273) bite-proof — completion producer observation

**Provenance:** cursor / composer-2.5 (implementer).

## Guarded elements

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| BP-B1 | per-poll `_observe_attempt_completions` in `_run_engine_files` poll loop | fast-exit stdout delivery must be stamped between heartbeats | `test_completion_producer_stdout_delivery_fast_exit_records_stamp` |
| BP-B2 | `_observe_native_file_completion` once-only guard | first plateau digest must survive a later rewrite (edge 8) | `test_completion_producer_rewrite_keeps_first_digest` |

---

## BP-B1 — fast-exit observation

- **axis:** a claude-print run that emits and exits between heartbeats must carry a completion stamp

**neutralization** (`plugins/superheroes/lib/engine_dispatch.py`, `_run_engine_files` poll loop): per-poll observation disabled; observation moved to heartbeat block only; rc-branch observation disabled:

```python
    while True:
        # bite-proof BP-B1 neutralization: per-poll observation disabled (heartbeat-only)
        rc = proc.poll()
        ...
        if now - last_beat >= HEARTBEAT_INTERVAL:
            last_beat = now
            _observe_attempt_completions(...)
            ...
        if rc is not None:
            natural_rc = rc
            # bite-proof BP-B1 neutralization: rc-branch observation disabled
            break
```

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_engine_dispatch.py::test_completion_producer_stdout_delivery_fast_exit_records_stamp -q
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_______ test_completion_producer_stdout_delivery_fast_exit_records_stamp _______

    def test_completion_producer_stdout_delivery_fast_exit_records_stamp(tmp_path, monkeypatch):
        ...
>       _assert_completion_keys(ended, structured)

plugins/superheroes/lib/tests/test_engine_dispatch.py:16141: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

    def _assert_completion_keys(ended, payload):
        for key in _COMPLETION_KEYS:
>           assert key in ended
E           AssertionError: assert 'resultCompleteAt' in {'activityStream': 'stdout', 'at': 1789933905.740685, 'attempt': 1, 'capSeconds': 30, ...}

plugins/superheroes/lib/tests/test_engine_dispatch.py:15999: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_completion_producer_stdout_delivery_fast_exit_records_stamp
1 failed in 3.16s
```

**restore** (`plugins/superheroes/lib/engine_dispatch.py`, `_run_engine_files` poll loop):
```python
    while True:
        _observe_attempt_completions(
            delivery, stdout_completion_obs, native_completion_obs,
            run_dir_real, attempt, stdout_path,
        )
        rc = proc.poll()
        ...
        if rc is not None:
            natural_rc = rc
            _observe_attempt_completions(
                delivery, stdout_completion_obs, native_completion_obs,
                run_dir_real, attempt, stdout_path,
            )
            break
```

**restore receipt:** post-restore `git status --porcelain` shows only expected worktree edits on order files.

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 2.96s
```

---

## BP-B2 — rewrite once-only

- **axis:** edge 8 — first observation wins; a rewritten native result file must not replace the recorded digest

**neutralization** (`plugins/superheroes/lib/engine_dispatch.py`, `_observe_native_file_completion`):
```python
def _observe_native_file_completion(obs_state, run_dir_real, attempt):
    """Stamp argv/prompt delivery completion on first stable file plateau. Never raises."""
    # bite-proof BP-B2 neutralization: once-only rule disabled (stamp may be replaced)
```

(removes the `if obs_state.get("stamp") is not None: return` guard)

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_engine_dispatch.py::test_completion_producer_rewrite_keeps_first_digest -q
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_____________ test_completion_producer_rewrite_keeps_first_digest ______________

    def test_completion_producer_rewrite_keeps_first_digest(tmp_path, monkeypatch):
        ...
>       _assert_completion_keys(ended, first_payload)

plugins/superheroes/lib/tests/test_engine_dispatch.py:16183: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

    def _assert_completion_keys(ended, payload):
        for key in _COMPLETION_KEYS:
            assert key in ended
>       assert ended[ERC.FIELD_RESULT_COMPLETE_SHA256] == ERC.canonical_payload_digest(payload)
E       AssertionError: assert '7a08056d3867...4a4caa432a52e' == '53dd89efc8a4...cda012b851fb0'

plugins/superheroes/lib/tests/test_engine_dispatch.py:16000: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_completion_producer_rewrite_keeps_first_digest
1 failed in 4.46s
```

**restore** (`plugins/superheroes/lib/engine_dispatch.py`, `_observe_native_file_completion`):
```python
    if obs_state.get("stamp") is not None:
        return
```

**restore receipt:** post-restore `git status --porcelain` shows only expected worktree edits on order files.

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 4.69s
```
