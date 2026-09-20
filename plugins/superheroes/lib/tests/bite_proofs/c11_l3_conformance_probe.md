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

---

## Orchestrator re-run on the final code head `d120e16f` (2026-09-19, adopting lane `launch-d23bec7c893a0ac8`)

Run by the orchestrator in a detached probe worktree pinned at `d120e16f` (`git status --porcelain` empty before and after every element). Method: exact-string mutation through a file edit (`count(old) == 1` asserted), the named test selected by its exact node id (never `-k`), red captured, inverse edit, green captured. Elements G1–G8 are the implementer's originals re-proved on the final head; **G9–G15 are the detectors the review's fix round 1 added** (`f7edaf67`): the toolCalls ≥ 1 gate, the run-dir-reused and run-dir-setup-failed refusals, the every-dispatchable-engine required set, the field-by-field record validation, and the wave and cell bindings. Round 2's fix (`24e5aba5`) added tests only (the cursor marker-channel probe path), no detector. G8's neutralization on this head plants a synthetic passing record for the missing engine (the 'missing' loop can no longer be simply removed, because the later loop indexes `results_by_engine`), which is the same axis: a missing engine must refuse `probe-missing`.

### G1 — result-production leg

- **site:** `plugins/superheroes/lib/conformance_probe.py`
- **neutralization:** replace `elif not terminal.get("ok"):` with `elif False:`
- **raw red:** `test_result_production_fails_on_schema_invalid_native_result` — E         + result-did-not-validate | FAILED plugins/superheroes/lib/tests/test_conformance_probe.py::test_result_production_fails_on_schema_invalid_native_result
- **restore:** inverse replace (tree clean: `git status --porcelain` empty = True)
- **raw green:** 1 passed in 0.19s
- **verdict:** RED->GREEN

### G2 — completion leg (timedOut)

- **site:** `plugins/superheroes/lib/conformance_probe.py`
- **neutralization:** replace `elif ended.get("timedOut"):` with `elif False:`
- **raw red:** `test_completion_fails_on_timeout` — E       assert True is False | FAILED plugins/superheroes/lib/tests/test_conformance_probe.py::test_completion_fails_on_timeout
- **restore:** inverse replace (tree clean: `git status --porcelain` empty = True)
- **raw green:** 1 passed in 0.19s
- **verdict:** RED->GREEN

### G3 — telemetry leg (telemetry-absent)

- **site:** `plugins/superheroes/lib/conformance_probe.py`
- **neutralization:** replace `if (telemetry == "tool-calls" and source not in (None, "none") and last_at is not None` with `if True:`
- **raw red:** `test_telemetry_fails_when_stream_has_no_tool_calls` — E       assert True is False | FAILED plugins/superheroes/lib/tests/test_conformance_probe.py::test_telemetry_fails_when_stream_has_no_tool_calls
- **restore:** inverse replace (tree clean: `git status --porcelain` empty = True)
- **raw green:** 1 passed in 0.19s
- **verdict:** RED->GREEN

### G9 — telemetry leg requires toolCalls >= 1 (fix r1)

- **site:** `plugins/superheroes/lib/conformance_probe.py`
- **neutralization:** replace `tool_count_ok = isinstance(tool_calls, (int, float)) and not isinstance(tool_calls, bool) ` with `tool_count_ok = True`
- **raw red:** `test_telemetry_fails_on_zero_tool_call_count` — E       assert True is False | FAILED plugins/superheroes/lib/tests/test_conformance_probe.py::test_telemetry_fails_on_zero_tool_call_count
- **restore:** inverse replace (tree clean: `git status --porcelain` empty = True)
- **raw green:** 1 passed in 0.19s
- **verdict:** RED->GREEN

### G4 — loud failure (exit 1 + stderr)

- **site:** `plugins/superheroes/lib/conformance_probe.py`
- **neutralization:** replace `return payload, (0 if all_ok else 1), (_stderr_failure_line(engine, legs, dep_lanes) if no` with `return payload, 0, None`
- **raw red:** `test_cli_failure_is_loud` — E       assert 0 == 1 | FAILED plugins/superheroes/lib/tests/test_conformance_probe.py::test_cli_failure_is_loud
- **restore:** inverse replace (tree clean: `git status --porcelain` empty = True)
- **raw green:** 1 passed in 0.20s
- **verdict:** RED->GREEN

### G5 — owner-word blank gate

- **site:** `plugins/superheroes/lib/conformance_probe.py`
- **neutralization:** replace `if not isinstance(word, str) or not word.strip():` with `if False:`
- **raw red:** `test_preflight_entry_refuses_blank_owner_word_and_unfailed_engine` — E         + launch-without-not-failed:codex | FAILED plugins/superheroes/lib/tests/test_conformance_probe.py::test_preflight_entry_refuses_blank_owner_word_and_unfailed_engine
- **restore:** inverse replace (tree clean: `git status --porcelain` empty = True)
- **raw green:** 1 passed in 0.16s
- **verdict:** RED->GREEN

### G6 — same-family park

- **site:** `plugins/superheroes/lib/conformance_probe.py`
- **neutralization:** replace `if same_family:` with `if False and same_family:`
- **raw red:** `test_preflight_entry_parks_on_same_family` — E         + pass | FAILED plugins/superheroes/lib/tests/test_conformance_probe.py::test_preflight_entry_parks_on_same_family
- **restore:** inverse replace (tree clean: `git status --porcelain` empty = True)
- **raw green:** 1 passed in 0.16s
- **verdict:** RED->GREEN

### G7 — launcher fail branch carries checks

- **site:** `plugins/superheroes/lib/launcher.py`
- **neutralization:** replace `return _fail("preflight-failed:%s" % check_id, checks=out_checks)` with `return _fail("preflight-failed:%s" % check_id)`
- **raw red:** `test_walk_preflight_failed_check_carries_checks` — E       AssertionError: assert 'checks' in {'ok': False, 'reason': 'preflight-failed:engine-auth'} | FAILED plugins/superheroes/lib/tests/test_launcher.py::test_walk_preflight_failed_check_carries_che
- **restore:** inverse replace (tree clean: `git status --porcelain` empty = True)
- **raw green:** 1 passed in 0.35s
- **verdict:** RED->GREEN

### G8 — missing required engine

- **site:** `plugins/superheroes/lib/conformance_probe.py`
- **neutralization:** replace `for eng in required:` with `for eng in required:`
- **raw red:** `test_preflight_entry_refuses_missing_duplicate_foreign_stale[missing-probe-missing:codex]` — E       assert 0 == 1 | FAILED plugins/superheroes/lib/tests/test_conformance_probe.py::test_preflight_entry_refuses_missing_duplicate_foreign_stale[missing-probe-missing:codex]
- **restore:** inverse replace (tree clean: `git status --porcelain` empty = True)
- **raw green:** 1 passed in 0.16s
- **verdict:** RED->GREEN

### G10 — run-dir-reused refusal (fix r1)

- **site:** `plugins/superheroes/lib/conformance_probe.py`
- **neutralization:** replace `if engine_dispatch._journal_state(records).get("folded") is not None:` with `if False:`
- **raw red:** `test_probe_refuses_reused_run_dir_with_folded_result` — E         + auth-or-config-refusal | FAILED plugins/superheroes/lib/tests/test_conformance_probe.py::test_probe_refuses_reused_run_dir_with_folded_result
- **restore:** inverse replace (tree clean: `git status --porcelain` empty = True)
- **raw green:** 1 passed in 0.19s
- **verdict:** RED->GREEN

### G11 — run-dir setup never raises (fix r1)

- **site:** `plugins/superheroes/lib/conformance_probe.py`
- **neutralization:** replace `try:` with `run_dir = tempfile.mkdtemp(prefix="conformance-probe-")`
- **raw red:** `test_probe_run_dir_setup_failure_never_raises` — E       OSError: disk full | FAILED plugins/superheroes/lib/tests/test_conformance_probe.py::test_probe_run_dir_setup_failure_never_raises
- **restore:** inverse replace (tree clean: `git status --porcelain` empty = True)
- **raw green:** 1 passed in 0.17s
- **verdict:** RED->GREEN

### G12 — required set = every dispatchable engine (fix r1)

- **site:** `plugins/superheroes/lib/conformance_probe.py`
- **neutralization:** replace `return sorted(DISPATCHABLE_ENGINES), None` with `return sorted({row["engine"] for row in rows if isinstance(row, dict) and row.get("engine"`
- **raw red:** `test_preflight_requires_all_dispatchable_engines_not_only_calibrated` — E       assert 0 == 1 | FAILED plugins/superheroes/lib/tests/test_conformance_probe.py::test_preflight_requires_all_dispatchable_engines_not_only_calibrated
- **restore:** inverse replace (tree clean: `git status --porcelain` empty = True)
- **raw green:** 1 passed in 0.16s
- **verdict:** RED->GREEN

### G13 — probe record validated before pass (fix r1)

- **site:** `plugins/superheroes/lib/conformance_probe.py`
- **neutralization:** replace `malformed = _validate_probe_record(raw, path)` with `malformed = None if raw.get("schema") == SCHEMA else "probe-result-malformed:%s" % path`
- **raw red:** `test_preflight_entry_refuses_truthy_ok_without_legs` — E       assert 0 == 1 | FAILED plugins/superheroes/lib/tests/test_conformance_probe.py::test_preflight_entry_refuses_truthy_ok_without_legs
- **restore:** inverse replace (tree clean: `git status --porcelain` empty = True)
- **raw green:** 1 passed in 0.16s
- **verdict:** RED->GREEN

### G14 — wave binding (fix r1, owner-gate guidance)

- **site:** `plugins/superheroes/lib/conformance_probe.py`
- **neutralization:** replace `if not result_wave or result_wave != wave:` with `if False:`
- **raw red:** `test_preflight_entry_refuses_wave_mismatch` — E       assert 0 == 1 | FAILED plugins/superheroes/lib/tests/test_conformance_probe.py::test_preflight_entry_refuses_wave_mismatch
- **restore:** inverse replace (tree clean: `git status --porcelain` empty = True)
- **raw green:** 1 passed in 0.16s
- **verdict:** RED->GREEN

### G15 — probed cell vs selected cell (fix r1, owner-gate guidance)

- **site:** `plugins/superheroes/lib/conformance_probe.py`
- **neutralization:** replace `if expected_cell is None or list(probed_cell[:len(expected_cell)]) != expected_cell:` with `if False:`
- **raw red:** `test_preflight_entry_refuses_probe_cell_mismatch` — E       assert 0 == 1 | FAILED plugins/superheroes/lib/tests/test_conformance_probe.py::test_preflight_entry_refuses_probe_cell_mismatch
- **restore:** inverse replace (tree clean: `git status --porcelain` empty = True)
- **raw green:** 1 passed in 0.16s
- **verdict:** RED->GREEN

**Summary:** 15 of 15 elements RED→GREEN on `d120e16f`; no disclosure owed.
