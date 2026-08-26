# WO-R1 (#1125) bite-proofs — _cap_file_tail is the single source of truth for truncation authority

## Baseline (post-WO-R1 production edit)

**Command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest \
  plugins/superheroes/lib/tests/test_engine_dispatch.py::test_straggler_write_during_cap_window_grades_truncated \
  plugins/superheroes/lib/tests/test_engine_dispatch.py::test_cap_file_tail_over_budget_returns_truncated_and_observed \
  plugins/superheroes/lib/tests/test_engine_dispatch.py::test_cap_file_tail_under_budget_returns_not_truncated_and_observed \
  plugins/superheroes/lib/tests/test_engine_dispatch.py::test_cap_file_tail_missing_path_returns_no_authority \
  plugins/superheroes/lib/tests/test_engine_dispatch.py::test_cap_file_tail_empty_file_returns_zero_observed \
  -q
```

**Output:**
```
5 passed in 1.02s
```

---

## N1 — the window is closed

**Guarded element:** `_run_engine_files` stdoutBytes recording — axis: stdoutBytes from `_cap_file_tail` capping measurement, not a stale pre-cap `os.path.getsize`.

**Neutralization:** reinstated separate `os.path.getsize(stdout_path)` before the cap call (`engine_dispatch.py:2222–2225`) and recorded `stdoutBytes` from `pre_cap_stdout_bytes` instead of `stdout_observed` (`engine_dispatch.py:2238–2241`).

**Command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest \
  plugins/superheroes/lib/tests/test_engine_dispatch.py::test_straggler_write_during_cap_window_grades_truncated \
  -q
```

**Red run:**
```
E       AssertionError: assert None is not None
plugins/superheroes/lib/tests/test_engine_dispatch.py:5518: AssertionError
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_straggler_write_during_cap_window_grades_truncated
1 failed in 1.07s
```

**Restore:** removed `pre_cap_stdout_bytes` getsize block; restored `stdout_observed` recording from `_cap_file_tail` return value.

**Restore receipt:** ` M plugins/superheroes/lib/engine_dispatch.py`

**Green run:**
```
1 passed in 1.00s
```

---

## N2 — the returned flag is the real one

**Guarded element:** `_cap_file_tail` truncated flag — axis: over-budget file returns `(True, observed)`.

**Neutralization:** changed `return True, observed` to `return False, observed` at `engine_dispatch.py:1966`.

**Command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest \
  plugins/superheroes/lib/tests/test_engine_dispatch.py::test_cap_file_tail_over_budget_returns_truncated_and_observed \
  -q
```

**Red run:**
```
E       assert False is True
plugins/superheroes/lib/tests/test_engine_dispatch.py:5528: AssertionError
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_cap_file_tail_over_budget_returns_truncated_and_observed
1 failed in 0.48s
```

**Restore:** restored `return True, observed` at `engine_dispatch.py:1966`.

**Restore receipt:** ` M plugins/superheroes/lib/engine_dispatch.py`

**Green run:**
```
1 passed in 0.36s
```

---

## N3 — `observed` is the pre-cap size

**Guarded element:** `_cap_file_tail` observed count — axis: `observed` is the pre-cap byte count from the bounded read, not post-cap file size.

**Neutralization:** changed `return True, observed` to `return True, os.path.getsize(path)` after the capping write at `engine_dispatch.py:1966`.

**Command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest \
  plugins/superheroes/lib/tests/test_engine_dispatch.py::test_cap_file_tail_over_budget_returns_truncated_and_observed \
  -q
```

**Red run:**
```
E       assert 2048 == 2560
plugins/superheroes/lib/tests/test_engine_dispatch.py:5529: AssertionError
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_cap_file_tail_over_budget_returns_truncated_and_observed
1 failed in 0.45s
```

**Restore:** restored `return True, observed` at `engine_dispatch.py:1966`.

**Restore receipt:** ` M plugins/superheroes/lib/engine_dispatch.py`

**Green run:**
```
1 passed in 0.36s
```

---

## N4 — the no-authority sentinel survives

**Guarded element:** `_cap_file_tail` error-path return — axis: unreadable/missing path returns `(False, None)`, distinguishable from empty-file `(False, 0)`.

**Neutralization:** changed both `return False, None` paths to `return False, 0` at `engine_dispatch.py:1961` and `engine_dispatch.py:1968`.

**Command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest \
  plugins/superheroes/lib/tests/test_engine_dispatch.py::test_cap_file_tail_missing_path_returns_no_authority \
  -q
```

**Red run:**
```
E       assert 0 is None
plugins/superheroes/lib/tests/test_engine_dispatch.py:5548: AssertionError
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_cap_file_tail_missing_path_returns_no_authority
1 failed in 0.51s
```

**Restore:** restored `return False, None` at `engine_dispatch.py:1961` and `engine_dispatch.py:1968`.

**Restore receipt:** ` M plugins/superheroes/lib/engine_dispatch.py`

**Green run:**
```
1 passed in 0.55s
```

---

## Final green (grading family + capping neighbours)

**Command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest \
  plugins/superheroes/lib/tests/test_engine_dispatch.py::test_recorded_under_cap_count_overrides_forged_head_marker \
  plugins/superheroes/lib/tests/test_engine_dispatch.py::test_recorded_cap_boundary_count_overrides_forged_head_marker \
  plugins/superheroes/lib/tests/test_engine_dispatch.py::test_injected_seam_count_does_not_override_head_marker \
  plugins/superheroes/lib/tests/test_engine_dispatch.py::test_unstamped_unknown_producer_count_does_not_override_head_marker \
  plugins/superheroes/lib/tests/test_engine_dispatch.py::test_stamp_without_recorded_count_does_not_suppress \
  plugins/superheroes/lib/tests/test_engine_dispatch.py::test_recorded_over_cap_count_grades_truncated_with_under_cap_file \
  plugins/superheroes/lib/tests/test_engine_dispatch.py::test_file_over_cap_grades_truncated_despite_under_cap_recorded_count \
  plugins/superheroes/lib/tests/test_engine_dispatch.py::test_run_engine_files_stamps_stdout_bytes_pre_cap \
  plugins/superheroes/lib/tests/test_engine_dispatch.py::test_complete_marker_mid_body_not_truncated \
  plugins/superheroes/lib/tests/test_engine_dispatch.py::test_genuine_truncation_detected_without_stdout_bytes \
  plugins/superheroes/lib/tests/test_engine_dispatch.py::test_run_engine_files_caps_only_after_terminate_on_timeout \
  plugins/superheroes/lib/tests/test_engine_dispatch.py::test_stdout_cap_truncation_marker_in_file_tail \
  plugins/superheroes/lib/tests/test_engine_dispatch.py::test_bounded_stdout_cap_file_tail_never_exceeds_budget \
  plugins/superheroes/lib/tests/test_engine_dispatch.py::test_cap_file_tail_memory_error_degrades_like_oserror \
  plugins/superheroes/lib/tests/test_engine_dispatch.py::test_stdout_cap_marker_parity_over_and_under_budget \
  plugins/superheroes/lib/tests/test_engine_dispatch.py::test_read_capped_text_memory_error_degrades_like_oserror \
  -q
```

**Output:**
```
16 passed in 2.63s
```
