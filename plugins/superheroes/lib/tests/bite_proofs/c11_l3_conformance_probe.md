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
