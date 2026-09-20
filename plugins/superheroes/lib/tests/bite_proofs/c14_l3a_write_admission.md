# C14 layer 3a — native write admission, payload scrub egress, supervisor folds (#1273 WO-A)

## BP-A1 — completed native write result admitted before timeout forfeit

- **guarded element:** `engine_dispatch.py:_grade_write_attempt` — axis: a schema-valid native result written before the wall cap is graded from admission even when `timedOut: true` and post-termination `exit` is non-zero
- **detector:** `plugins/superheroes/lib/tests/test_engine_dispatch.py::test_native_write_timeout_with_valid_result_admits`
- **neutralization:** restored the pre-admission forfeit guard `if ended.get("refusal") or ended.get("timedOut") or ended.get("exit") not in (0, None): return forfeit` ahead of `_admit_native_write_result`
- **raw red:**

```
>       assert grade["ok"] is True
E       KeyError: 'ok'
FAILED ...::test_native_write_timeout_with_valid_result_admits
1 failed in 2.50s
```

- **restore:** removed the `timedOut` / `exit` early-forfeit guard; native admission runs before timeout/exit disqualification
- **restore receipt:** `engine_dispatch.py:_grade_write_attempt` refusal-only early return restored; `git status --porcelain` over `plugins/superheroes/lib/engine_dispatch.py` clean after restore
- **raw green:** `.` / `1 passed in 2.59s`
- **verdict:** RED→GREEN

## BP-A2 — native payload scrubber scrubs dict keys

- **guarded element:** `engine_dispatch.py:_scrub_native_payload` — axis: secret-bearing dict keys are scrubbed and collision disambiguation preserves every entry
- **detector:** `plugins/superheroes/lib/tests/test_engine_dispatch.py::test_scrub_native_payload_scrubs_dict_keys_and_preserves_collisions`
- **neutralization:** reverted delegation to `engine_adapter._scrub_mapping`; dict branch kept keys unscrubbed (`{k: _scrub_native_payload(v) for k, v in obj.items()}`)
- **raw red:**

```
>       assert _ANT_KEY_A not in out and _ANT_KEY_B not in out
E       AssertionError: assert ('sk-ant-api03-AAAA...' not in {'sk-ant-api03-AAAA...': 'v1', ...})
FAILED ...::test_scrub_native_payload_scrubs_dict_keys_and_preserves_collisions
1 failed in 1.05s
```

- **restore:** `_scrub_native_payload` delegates to `engine_adapter._scrub_mapping` inside the existing `try/except Exception: return obj` wrapper
- **restore receipt:** delegation line quoted back in `_scrub_native_payload`; `git status --porcelain` clean after restore
- **raw green:** `.` / `1 passed in 0.84s`
- **verdict:** RED→GREEN

## BP-A3-fold1 — background budget exhaustion ends without resume

- **guarded element:** `engine_dispatch.py:5176` `_attempt_bg_budget_exhausted` branch in `_supervise` — axis: accumulated wall time at cap journals `attempt-ended` with timeout fields and never resumes
- **detector:** `plugins/superheroes/lib/tests/test_engine_dispatch.py::test_supervise_bg_budget_exhaustion_ends_attempt_without_resume`
- **neutralization:** `if _attempt_bg_budget_exhausted(...)` → `if False:  # bite-proof plant`
- **raw red:**

```
>       assert len(ended) == 1
E       assert 0 == 1
FAILED ...::test_supervise_bg_budget_exhaustion_ends_attempt_without_resume
1 failed in 0.98s
```

- **restore:** `if False` → `if _attempt_bg_budget_exhausted(opened, attempts[latest], latest):`
- **restore receipt:** budget-exhaustion condition restored verbatim; `git status --porcelain` clean after restore
- **raw green:** `.` / `1 passed in 1.46s`
- **verdict:** RED→GREEN

## BP-A3-fold2 — pre-retry stop-unconfirmed refusal

- **guarded element:** `engine_dispatch.py:5342` `_background_stop_unconfirmed` gate before retry spawn — axis: terminal `background-stop-unconfirmed` instead of spawning attempt `latest + 1`
- **detector:** `plugins/superheroes/lib/tests/test_engine_dispatch.py::test_supervise_pre_retry_refuses_on_background_stop_unconfirmed`
- **neutralization:** `if _background_stop_unconfirmed(state):` → `if False:  # bite-proof plant`
- **raw red:**

```
>       assert res["detail"] == "background-stop-unconfirmed"
E       AssertionError: assert 'spawn-blocked-for-test' == 'background-stop-unconfirmed'
FAILED ...::test_supervise_pre_retry_refuses_on_background_stop_unconfirmed
1 failed in 0.99s
```

- **restore:** `if False` → `if _background_stop_unconfirmed(state):`
- **restore receipt:** pre-retry gate restored verbatim; `git status --porcelain` clean after restore
- **raw green:** `.` / `1 passed in 0.85s`
- **verdict:** RED→GREEN
