# C14 layer 3c WO-A — bite-proofs

## BP-A1 — non-zero-exit detail

**Guarded element:** `engine_dispatch.py:_grade_write_attempt` non-zero-exit return — axis: bare forfeit names `nonzero-exit` detail.

**Detector:** `test_engine_dispatch.py::test_write_grade_nonzero_exit_forfeit_names_detail`

**Neutralization:** removed `"detail": "nonzero-exit"` from the non-zero-exit return (bare forfeit dict only).

**Red run:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
______________ test_write_grade_nonzero_exit_forfeit_names_detail ______________
>       assert grade.get("detail") == "nonzero-exit"
E       AssertionError: assert None == 'nonzero-exit'
1 failed in 1.24s
```

**Restore:** re-added `"detail": "nonzero-exit"` to the return dict.

**Restore receipt:** restored lines quoted above.

**Green run:**

```
.                                                                        [100%]
1 passed in 0.92s
```

## BP-A2 — timeout-no-admission detail

**Guarded element:** `engine_dispatch.py:_grade_write_attempt` timed-out non-native return — axis: bare forfeit names `timeout-no-admission` detail.

**Detector:** `test_engine_dispatch.py::test_write_grade_timeout_without_admission_names_detail`

**Neutralization:** removed `"detail": "timeout-no-admission"` from the timed-out nothing-admitted return.

**Red run:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
___________ test_write_grade_timeout_without_admission_names_detail ____________
>       assert grade.get("detail") == "timeout-no-admission"
E       AssertionError: assert None == 'timeout-no-admission'
1 failed in 1.13s
```

**Restore:** re-added `"detail": "timeout-no-admission"` to the return dict.

**Restore receipt:** restored lines quoted above.

**Green run:**

```
.                                                                        [100%]
1 passed in 1.02s
```

## BP-A3 — admittedAfterTimeout on terminal-refusal fold

**Guarded element:** `engine_dispatch.py` write terminal-refusal fold (~line 5727) — axis: `admittedAfterTimeout` propagates from grade to terminal result.

**Detector:** `test_engine_dispatch.py::test_write_terminal_refusal_after_timeout_keeps_admitted_after_timeout`

**Neutralization:** removed the two lines:
```python
                    if grade.get("admittedAfterTimeout"):
                        result["admittedAfterTimeout"] = True
```

**Red run:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
____ test_write_terminal_refusal_after_timeout_keeps_admitted_after_timeout ____
>       assert res.get("admittedAfterTimeout") is True
E       AssertionError: assert None is True
1 failed in 1.30s
```

**Restore:** re-added the two `admittedAfterTimeout` lines on the terminal-refusal fold.

**Restore receipt:** restored lines quoted above.

**Green run:**

```
.                                                                        [100%]
1 passed in 1.24s
```

## BP-A4 — injected single parse

**Guarded element:** `engine_dispatch.py:_execute_injected_attempt` stdout envelope parse — axis: `claude_result_envelope` called exactly once per attempt.

**Detector:** `test_engine_dispatch.py::test_injected_seam_claude_print_stdout_parses_envelope_once`

**Neutralization:** added duplicate call `engine_adapter.claude_result_envelope(stdout)` immediately after the existing one.

**Red run:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_________ test_injected_seam_claude_print_stdout_parses_envelope_once __________
>       assert envelope_calls["count"] == 1
E       assert 2 == 1
1 failed in 1.21s
```

**Restore:** removed the duplicate `claude_result_envelope` call.

**Restore receipt:** restored single-call form.

**Green run:**

```
.                                                                        [100%]
1 passed in 1.07s
```

## BP-A5 — epoch assertion

**Guarded element:** `engine_dispatch.py:_observe_native_file_completion` completion epoch stamp — axis: foreground timed-out path records completion epoch equal to deadline epoch.

**Detector:** `test_engine_dispatch.py::test_completion_producer_timed_out_foreground_carries_deadline_stamp`

**Neutralization:** after `completion_stamp(...)`, set `stamp[engine_result_channel.FIELD_RESULT_COMPLETE_EPOCH] = "wrong-epoch"` before assigning to `obs_state["stamp"]` in `_observe_native_file_completion`.

**Red run:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_____ test_completion_producer_timed_out_foreground_carries_deadline_stamp _____
>       assert ended[ERC.FIELD_DEADLINE_EPOCH] == ended[ERC.FIELD_RESULT_COMPLETE_EPOCH]
E       AssertionError: assert '75939-10ada2...2ad34c6c2a32d' == 'wrong-epoch'
1 failed in 2.61s
```

**Restore:** removed the `wrong-epoch` assignment line.

**Restore receipt:** restored lines quoted above.

**Green run:**

```
.                                                                        [100%]
1 passed in 3.47s
```
