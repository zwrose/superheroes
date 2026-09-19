# C11 layer 3 (#1270 WO-A) bite-proof — conformance probe

**Provenance:** implementer WO-A / `lib/conformance_probe.py` + launcher fold

## Guarded elements

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| G1 | `_grade_result_production` | schema-invalid native result fails `resultProduction` | `test_result_production_fails_on_schema_invalid_native_result` |
| G2 | `_grade_completion` `timedOut` gate | timed-out attempt fails `completionDetection` | `test_completion_fails_on_timeout` |
| G3 | `_grade_telemetry` `telemetry-absent` | stdout without tool-call channel fails `progressTelemetry` | `test_telemetry_fails_when_stream_has_no_tool_calls` |
| G4 | `probe` stderr + exit code | failure is loud on CLI | `test_cli_failure_is_loud` |
| G5 | `preflight_entry` blank owner word | blank `--owner-word` refused | `test_preflight_entry_refuses_blank_owner_word_and_unfailed_engine` |
| G6 | `preflight_entry` same-family park | `same-family` degradation → PARK fail entry | `test_preflight_entry_parks_on_same_family` |
| G7 | `walk_preflight` fail branch | failed check appended to `checks` before `_fail` | `test_walk_preflight_failed_check_carries_checks` |
| G8 | `preflight_entry` missing-engine check | missing required engine → `probe-missing` | `test_preflight_entry_refuses_missing_duplicate_foreign_stale` (missing) |

---

## G1 — result-production leg

- **axis:** `resultProduction` fails on `native-result-schema-invalid`

**neutralization** (`conformance_probe.py`, `_grade_result_production`):
```python
def _grade_result_production(terminal):
    return _leg(True, None, {})
```

**raw red:** `test_result_production_fails_on_schema_invalid_native_result` — `assert payload["legs"]["resultProduction"]["ok"] is False` → `assert True is False`

**restore:** remove unconditional `return _leg(True, None, {})`.

**raw green:** `.` — 1 passed in 0.18s (node re-run after restore)

---

## G2 — completion leg

- **axis:** `completionDetection` fails on `timedOut`

**neutralization** (`conformance_probe.py`, `_grade_completion`):
```python
    # if ended.get("timedOut"):
    #     return _leg(False, "no-response-within-wait", {"timedOut": True})
```

**raw red:** `test_completion_fails_on_timeout` — `assert payload["legs"]["completionDetection"]["ok"] is False` → `assert True is False`

**restore:** uncomment `timedOut` refusal branch.

**raw green:** `.` — 1 passed in 0.18s

---

## G3 — telemetry leg

- **axis:** `progressTelemetry` assigns `telemetry-absent`

**neutralization** (`conformance_probe.py`, `_grade_telemetry` tail):
```python
    return _leg(True, None, { ... })  # was telemetry-absent fail leg
```

**raw red:** `test_telemetry_fails_when_stream_has_no_tool_calls` — `assert payload["legs"]["progressTelemetry"]["ok"] is False` → `assert True is False`

**restore:** restore `return _leg(False, "telemetry-absent", ...)`.

**raw green:** `.` — 1 passed in 0.18s

---

## G4 — loud failure

- **axis:** exit 1 + `CONFORMANCE PROBE FAILED` stderr line

**neutralization** (`conformance_probe.py`, `probe` return):
```python
    return payload, 0, stderr_line  # always exit 0; stderr suppressed
```

**raw red:** `test_cli_failure_is_loud` — `assert code == 1` → `assert 0 == 1`

**restore:** restore `return payload, (0 if all_ok else 1), stderr_line` with stderr emission.

**raw green:** `.` — 1 passed in 0.18s

---

## G5 — owner-word gate

- **axis:** blank owner word refused (`owner-word-blank`)

**neutralization** (`conformance_probe.py`, `preflight_entry`):
```python
        # if not isinstance(word, str) or not word.strip():
        #     return {"ok": False, "reason": "owner-word-blank"}, 1
```

**raw red:** `test_preflight_entry_refuses_blank_owner_word_and_unfailed_engine` — `assert payload["reason"] == "owner-word-blank"` → got `launch-without-not-failed:codex`

**restore:** uncomment blank-word refusal.

**raw green:** `.` — 1 passed in 0.15s

---

## G6 — same-family park

- **axis:** `same-family` degradations force PARK `engine-auth.state == "fail"`

**neutralization** (`conformance_probe.py`, `preflight_entry`):
```python
    if False and same_family:
```

**raw red:** `test_preflight_entry_parks_on_same_family` — `assert payload["engine-auth"]["state"] == "fail"` → `assert 'pass' == 'fail'`

**restore:** `if same_family:`

**raw green:** `.` — 1 passed in 0.15s

---

## G7 — launcher fold

- **axis:** `walk_preflight` fail path carries `checks` with failed entry

**neutralization** (`launcher.py`, `walk_preflight`):
```python
        if state == "fail":
            return _fail("preflight-failed:%s" % check_id)
```

**raw red:** `test_walk_preflight_failed_check_carries_checks` — `assert "checks" in result` → absent

**restore:** append failing entry to `out_checks` and `return _fail(..., checks=out_checks)`.

**raw green:** `.` — 1 passed in 0.47s (combined with restored tree)

---

## G8 — derived required set

- **axis:** missing required engine → `probe-missing:<engine>`

**neutralization** (`conformance_probe.py`, `preflight_entry`):
```python
    # for eng in required:
    #     if eng not in results_by_engine:
    #         return {"ok": False, "reason": "probe-missing:%s" % eng}, 1
```

**raw red:** `test_preflight_entry_refuses_missing_duplicate_foreign_stale[missing-probe-missing:codex]` — `KeyError: 'codex'` (missing check removed)

**restore:** uncomment missing-engine loop.

**raw green:** `.` — parametrized node passes after restore (full file green: 16 passed)

---

## Re-run on the WO-A2 head (2026-09-19)

Module compacted to 450 lines; grading consolidated into `_grade_legs`; probe claim is repo-agnostic.

### G1 — result-production leg

- **site:** `conformance_probe.py`, `_grade_legs` result-production block (was `_grade_result_production`)
- **neutralization:** `rp = _leg(True, None, {})` replaces the `if not terminal.get("terminal")` / `elif` / `else` rp assignment chain
- **raw red:** `test_result_production_fails_on_schema_invalid_native_result` — `assert True is False`
- **restore:** reinstate full rp assignment chain
- **raw green:** `.` — 1 passed in 0.18s

### G2 — completion leg

- **site:** `conformance_probe.py`, `_grade_legs` timedOut branch (was `_grade_completion`)
- **neutralization:** comment out `elif ended.get("timedOut"):` refusal branch
- **raw red:** `test_completion_fails_on_timeout` — `assert True is False`
- **restore:** uncomment timedOut branch
- **raw green:** `.` — 1 passed in 0.18s

### G3 — telemetry leg

- **site:** `conformance_probe.py`, `_grade_legs` progressTelemetry tail (was `_grade_telemetry`)
- **neutralization:** `pt = _leg(True, None, {...})` unconditionally
- **raw red:** `test_telemetry_fails_when_stream_has_no_tool_calls` — `assert True is False`
- **restore:** reinstate `if telemetry == "tool-calls"` / `else telemetry-absent` branches
- **raw green:** `.` — 1 passed in 0.18s

### G4 — loud failure

- **site:** `conformance_probe.py`, `probe` return
- **neutralization:** `return payload, 0, None`
- **raw red:** `test_cli_failure_is_loud` — `assert 0 == 1`
- **restore:** `return payload, (0 if all_ok else 1), (_stderr_failure_line(...) if not all_ok else None)`
- **raw green:** `.` — 1 passed in 0.18s

### G5 — owner-word gate

- **site:** `conformance_probe.py`, `preflight_entry` owner-word loop
- **neutralization:** comment out blank-word refusal
- **raw red:** `test_preflight_entry_refuses_blank_owner_word_and_unfailed_engine` — got `launch-without-not-failed:codex`
- **restore:** uncomment blank-word refusal
- **raw green:** `.` — 1 passed in 0.16s

### G6 — same-family park

- **site:** `conformance_probe.py`, `preflight_entry` same-family branch
- **neutralization:** `if False and same_family:`
- **raw red:** `test_preflight_entry_parks_on_same_family` — `assert 'pass' == 'fail'`
- **restore:** `if same_family:`
- **raw green:** `.` — 1 passed in 0.16s

### G7 — launcher fold

- **site:** `launcher.py`, `walk_preflight` fail branch (unchanged)
- **neutralization:** `return _fail("preflight-failed:%s" % check_id)` without appending to `out_checks`
- **raw red:** `test_walk_preflight_failed_check_carries_checks` — `assert 'checks' in result` absent
- **restore:** append failing entry to `out_checks` and `return _fail(..., checks=out_checks)`
- **raw green:** `.` — 1 passed in 0.36s

### G8 — derived required set

- **site:** `conformance_probe.py`, `preflight_entry` missing-engine loop
- **neutralization:** comment out missing-engine loop
- **raw red:** `test_preflight_entry_refuses_missing_duplicate_foreign_stale[missing-probe-missing:codex]` — `KeyError: 'codex'`
- **restore:** uncomment missing-engine loop
- **raw green:** `.` — 1 passed in 0.16s
