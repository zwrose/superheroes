# WO-L3AC-C (#1273) bite-proof — stdout is parsed exactly once for the result

**Covers:** WO-C (stdout single-parse materializer path, layer 3ac).

**Head:** `3132fbfbbda1867cba255eeacf955e256c5aa4b2`

**Provenance:** cursor / composer-2.5 (implementer).

Stdout result materialization reads only the held completion event; the real spawn path never
re-parses stdout for the result envelope.

## Guarded elements

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| E1 | `_materialize_stdout_result` stdout branch: `env = stdout_event` | the materializer's stdout branch reads only the held event; it never re-parses stdout | `test_stdout_materializer_without_held_event_is_absent_despite_valid_stdout` |
| E2 | `_materialize_stdout_result` signature: `stdout_event` has no default | a caller cannot omit the held event | `test_stdout_materializer_requires_the_held_event_argument` |
| E3 | `_process_stdout_completion_line`: `obs_state["event"] = obj` set before the admissibility check | every result event replaces the held event — a later inadmissible one governs | `test_stdout_later_inadmissible_result_governs_and_materializes_absent` |
| E4 | `_observe_stdout_completion` eviction block: `obs_state["event"] = None` | eviction clears the event together with the stamp | `test_stdout_eviction_boundary_keeps_at_budget_and_evicts_past_it` |
| E5 | `_observe_stdout_completion` `except (OSError, MemoryError)` terminal clear | a failed terminal read leaves no held event | `test_stdout_terminal_read_failure_clears_held_event` |
| E6 | `_observe_stdout_completion` size-regression block (`if file_size < offset:`) | a file smaller than the bytes consumed poisons the producer | `test_stdout_size_regression_poisons_the_producer` |
| E7 | `_run_engine_files`: the non-terminal `_observe_attempt_completions` call between the poll loop and `_terminate_process_group(pgid)` | a result written before a natural exit is stamped before termination begins | `test_stdout_result_before_natural_exit_is_stamped_before_termination` |
| E8 | `_drain_stdout_completion_bytes`: `if len(new_buf) > MAX_STDOUT_CAPTURE:` | the line bound is the cap itself, with no marker reserve | `test_stdout_unterminated_result_at_cap_admits_under_cap` |
| E9 | `_run_engine_files`: the terminal `_observe_attempt_completions(..., terminal=True)` call after `proc.wait` | on the natural-exit branch, bytes a descendant writes during termination are observed | `test_stdout_natural_exit_descendant_result_on_sigterm_admits` |
| E10 | `_run_engine_files`: the materializer's fifth argument `stdout_completion_obs.get("event")` | the real spawn path hands the held event to the materializer and never re-parses stdout for the result | `test_stdout_result_envelope_never_parsed_on_real_path_through_grading` and `test_stdout_unicode_line_separators_inside_payload_admit` |

---

## E1 — materializer stdout branch reads held event only

- **axis:** the materializer's stdout branch reads only the held event; it never re-parses stdout

**neutralization** (`plugins/superheroes/lib/engine_dispatch.py`, `_materialize_stdout_result` stdout branch):

before:
```python
    if delivery == engine_result_channel.RESULT_DELIVERY_STDOUT:
        env = stdout_event
```

after:
```python
    if delivery == engine_result_channel.RESULT_DELIVERY_STDOUT:
        env = engine_adapter.claude_result_envelope(_read_capped_text(stdout_path, stream=CAP_STREAM_STDOUT))
```

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_engine_dispatch.py::test_stdout_materializer_without_held_event_is_absent_despite_valid_stdout -q -p no:randomly
```

**raw red** (exit 1):
```
F                                                                        [100%]
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_stdout_materializer_without_held_event_is_absent_despite_valid_stdout
1 failed in 2.45s
```
(assertion: `assert status == "absent"` / `AssertionError: assert 'materialized' == 'absent'`)

**restore:** reinstate `env = stdout_event` in `_materialize_stdout_result`.

**restore receipt:** post-restore `git status --porcelain -- plugins/superheroes/lib/engine_dispatch.py` empty.

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 2.22s
```

---

## E2 — materializer requires held event argument

- **axis:** a caller cannot omit the held event

**neutralization** (`plugins/superheroes/lib/engine_dispatch.py`, `_materialize_stdout_result` signature):

before:
```python
def _materialize_stdout_result(
        run_dir_real, attempt, opened, stdout_path, stdout_event,
):
```

after:
```python
def _materialize_stdout_result(
        run_dir_real, attempt, opened, stdout_path, stdout_event=None,
):
```

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_engine_dispatch.py::test_stdout_materializer_requires_the_held_event_argument -q -p no:randomly
```

**raw red** (exit 1):
```
F                                                                        [100%]
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_stdout_materializer_requires_the_held_event_argument
1 failed in 2.69s
```
(assertion: `Failed: DID NOT RAISE <class 'TypeError'>`)

**restore:** remove `=None` default from `stdout_event` parameter.

**restore receipt:** post-restore `git status --porcelain -- plugins/superheroes/lib/engine_dispatch.py` empty.

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 2.28s
```

---

## E3 — every result event replaces held event before admissibility

- **axis:** every result event replaces the held event — a later inadmissible one governs

**neutralization** (`plugins/superheroes/lib/engine_dispatch.py`, `_process_stdout_completion_line`):

before (position 1 — before admissibility check):
```python
        obs_state["event"] = obj
        if obj.get("is_error") is True or "structured_output" not in obj:
```

after (position 2 — after admissibility `return`):
```python
        if obj.get("is_error") is True or "structured_output" not in obj:
            obs_state["stamp"] = None
            obs_state["stamp_line_start"] = None
            return
        obs_state["event"] = obj
```

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_engine_dispatch.py::test_stdout_later_inadmissible_result_governs_and_materializes_absent -q -p no:randomly
```

**raw red** (exit 1):
```
F                                                                        [100%]
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_stdout_later_inadmissible_result_governs_and_materializes_absent
1 failed in 3.59s
```
(assertion: `assert ended["stdoutResult"] == "absent"` / `AssertionError: assert 'materialized' == 'absent'`)

**restore:** move `obs_state["event"] = obj` back before the admissibility check.

**restore receipt:** post-restore `git status --porcelain -- plugins/superheroes/lib/engine_dispatch.py` empty.

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 3.44s
```

---

## E4 — eviction clears held event

- **axis:** eviction clears the event together with the stamp

**neutralization** (`plugins/superheroes/lib/engine_dispatch.py`, `_observe_stdout_completion` eviction block):

before:
```python
                obs_state["stamp"] = None
                obs_state["stamp_line_start"] = None
                obs_state["event"] = None
```

after:
```python
                obs_state["stamp"] = None
                obs_state["stamp_line_start"] = None
```

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_engine_dispatch.py::test_stdout_eviction_boundary_keeps_at_budget_and_evicts_past_it -q -p no:randomly
```

**raw red** (exit 1):
```
F                                                                        [100%]
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_stdout_eviction_boundary_keeps_at_budget_and_evicts_past_it
1 failed in 2.73s
```
(assertion: `assert evict_obs.get("event") is None`)

**restore:** reinstate `obs_state["event"] = None` in the eviction block.

**restore receipt:** post-restore `git status --porcelain -- plugins/superheroes/lib/engine_dispatch.py` empty.

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 2.46s
```

**normalization disclosure:** test patches `MAX_STDOUT_CAPTURE` to `16384` via `_patch_stdout_completion_bounds`. Guarded logic is the eviction block's event clear; pin shrinks fixtures only.

---

## E5 — terminal read failure clears held event

- **axis:** a failed terminal read leaves no held event

**neutralization** (`plugins/superheroes/lib/engine_dispatch.py`, `_observe_stdout_completion` `except (OSError, MemoryError)`):

before:
```python
    except (OSError, MemoryError):
        if terminal:
            obs_state["event"] = None
            obs_state["stamp"] = None
            obs_state["stamp_line_start"] = None
        return
```

after:
```python
    except (OSError, MemoryError):
        if terminal:
            pass
        return
```

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_engine_dispatch.py::test_stdout_terminal_read_failure_clears_held_event -q -p no:randomly
```

**raw red** (exit 1):
```
F                                                                        [100%]
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_stdout_terminal_read_failure_clears_held_event
1 failed in 2.54s
```
(assertion: `assert obs.get("event") is None`)

**restore:** reinstate terminal clear of event, stamp, and stamp_line_start.

**restore receipt:** post-restore `git status --porcelain -- plugins/superheroes/lib/engine_dispatch.py` empty.

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 2.23s
```

---

## E6 — size regression poisons producer

- **axis:** a file smaller than the bytes consumed poisons the producer

**neutralization** (`plugins/superheroes/lib/engine_dispatch.py`, `_observe_stdout_completion` size-regression block):

before:
```python
            if file_size < offset:
```

after:
```python
            if False:
```

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_engine_dispatch.py::test_stdout_size_regression_poisons_the_producer -q -p no:randomly
```

**raw red** (exit 1):
```
F                                                                        [100%]
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_stdout_size_regression_poisons_the_producer
1 failed in 2.66s
```
(assertion: `assert obs.get("event") is None`)

**restore:** reinstate `if file_size < offset:`.

**restore receipt:** post-restore `git status --porcelain -- plugins/superheroes/lib/engine_dispatch.py` empty.

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 2.26s
```

---

## E7 — pre-termination observation stamps result

- **axis:** a result written before a natural exit is stamped before termination begins

**neutralization** (`plugins/superheroes/lib/engine_dispatch.py`, `_run_engine_files`):

before:
```python
    _observe_attempt_completions(
        delivery, stdout_completion_obs, native_completion_obs,
        run_dir_real, attempt, stdout_path,
    )
    _terminate_process_group(pgid)
```

after: non-terminal call deleted; `_terminate_process_group(pgid)` follows poll loop directly.

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_engine_dispatch.py::test_stdout_result_before_natural_exit_is_stamped_before_termination -q -p no:randomly
```

**raw red** (exit 1):
```
F                                                                        [100%]
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_stdout_result_before_natural_exit_is_stamped_before_termination
1 failed in 3.64s
```
(assertion: `assert ended[ERC.FIELD_RESULT_COMPLETE_AT] < terminate_entry["t"]`)

**restore:** reinstate the four-line non-terminal `_observe_attempt_completions` call before `_terminate_process_group(pgid)`.

**restore receipt:** post-restore `git status --porcelain -- plugins/superheroes/lib/engine_dispatch.py` empty.

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 3.39s
```

---

## E8 — line bound is cap with no marker reserve

- **axis:** the line bound is the cap itself, with no marker reserve

**neutralization** (`plugins/superheroes/lib/engine_dispatch.py`, `_drain_stdout_completion_bytes`):

before:
```python
                if len(new_buf) > MAX_STDOUT_CAPTURE:
```

after:
```python
                if len(new_buf) > MAX_STDOUT_CAPTURE - 56:
```

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_engine_dispatch.py::test_stdout_unterminated_result_at_cap_admits_under_cap -q -p no:randomly
```

**raw red** (exit 1):
```
F                                                                        [100%]
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_stdout_unterminated_result_at_cap_admits_under_cap
1 failed in 3.61s
```
(assertion: `assert key in ended` / `AssertionError: assert 'resultCompleteAt' in ended`)

**restore:** reinstate `if len(new_buf) > MAX_STDOUT_CAPTURE:`.

**restore receipt:** post-restore `git status --porcelain -- plugins/superheroes/lib/engine_dispatch.py` empty.

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 3.18s
```

**normalization disclosure:** test patches `MAX_STDOUT_CAPTURE` to `16384` via `_patch_stdout_completion_bounds`. Guarded logic is the len-guard branch; pin shrinks fixtures only.

---

## E9 — terminal observation after natural exit

- **axis:** on the natural-exit branch, bytes a descendant writes during termination are observed

**neutralization** (`plugins/superheroes/lib/engine_dispatch.py`, `_run_engine_files`):

before:
```python
    _observe_attempt_completions(
        delivery, stdout_completion_obs, native_completion_obs,
        run_dir_real, attempt, stdout_path, terminal=True,
    )
```

after: terminal call deleted after `proc.wait(timeout=2)`.

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_engine_dispatch.py::test_stdout_natural_exit_descendant_result_on_sigterm_admits -q -p no:randomly
```

**raw red** (exit 1):
```
F                                                                        [100%]
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_stdout_natural_exit_descendant_result_on_sigterm_admits
1 failed in 9.77s
```
(assertion: `assert key in ended` / `AssertionError: assert 'resultCompleteAt' in ended`)

**restore:** reinstate terminal `_observe_attempt_completions(..., terminal=True)` after `proc.wait`.

**restore receipt:** post-restore `git status --porcelain -- plugins/superheroes/lib/engine_dispatch.py` empty.

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 6.60s
```

---

## E10 — real spawn path passes held event to materializer

- **axis:** the real spawn path hands the held event to the materializer and never re-parses stdout for the result

**neutralization** (`plugins/superheroes/lib/engine_dispatch.py`, `_run_engine_files` materializer call):

before:
```python
    stdout_result = _materialize_stdout_result(
        run_dir_real, attempt, opened, stdout_path,
        stdout_completion_obs.get("event"),
    )
```

after:
```python
    stdout_result = _materialize_stdout_result(
        run_dir_real, attempt, opened, stdout_path,
        engine_adapter.claude_result_envelope(_read_capped_text(stdout_path, stream=CAP_STREAM_STDOUT)),
    )
```

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_engine_dispatch.py::test_stdout_result_envelope_never_parsed_on_real_path_through_grading plugins/superheroes/lib/tests/test_engine_dispatch.py::test_stdout_unicode_line_separators_inside_payload_admit -q -p no:randomly
```

**raw red** (exit 1):
```
FF                                                                       [100%]
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_stdout_result_envelope_never_parsed_on_real_path_through_grading
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_stdout_unicode_line_separators_inside_payload_admit
2 failed in 6.55s
```
(assertion 1: `assert envelope_calls["count"] == 0` / `assert 2 == 0`; assertion 2: `FileNotFoundError: ... native-result-1.json`)

**restore:** reinstate `stdout_completion_obs.get("event")` as the materializer's fifth argument.

**restore receipt:** post-restore `git status --porcelain -- plugins/superheroes/lib/engine_dispatch.py` empty.

**raw green** (exit 0):
```
..                                                                       [100%]
2 passed in 7.45s
```

---

## Scoped block run (21st invocation)

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_engine_dispatch.py -k "test_stdout_ or test_completion_stdout_" -n 4 -q -p no:randomly
```

**raw green** (exit 0):
```
......................................                                   [100%]
38 passed in 45.17s
```
