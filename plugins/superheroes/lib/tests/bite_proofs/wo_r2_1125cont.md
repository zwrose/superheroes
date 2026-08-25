# WO-R2 (#1125) bite-proofs — rewrite failure preserves over-cap measurement authority

## Edge-5 — over budget, rewrite fails

**Guarded element:** `_cap_file_tail` rewrite-failure return (`engine_dispatch.py:1970–1972`) — axis: a failed rewrite must not erase a completed over-cap measurement; returns `(True, observed)` not `(False, None)`.

**Neutralization:** changed the rewrite-failure `except` to `return False, None` (pre-change behaviour) at `engine_dispatch.py:1972`.

**Command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest \
  plugins/superheroes/lib/tests/test_engine_dispatch.py::test_cap_file_tail_rewrite_failure_preserves_over_cap_authority \
  plugins/superheroes/lib/tests/test_engine_dispatch.py::test_rewrite_failure_capture_grades_truncated \
  -q
```

**Red run:**
```
FF                                                                       [100%]
=================================== FAILURES ===================================
_______ test_cap_file_tail_rewrite_failure_preserves_over_cap_authority ________

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-9292/test_cap_file_tail_rewrite_fai0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x101ae4790>

    def test_cap_file_tail_rewrite_failure_preserves_over_cap_authority(tmp_path, monkeypatch):
        """axis: a failed rewrite must not erase a completed over-cap measurement."""
        ...
        truncated, observed = ED._cap_file_tail(path_str, cap)
>       assert truncated is True
E       assert False is True

plugins/superheroes/lib/tests/test_engine_dispatch.py:5623: AssertionError
________________ test_rewrite_failure_capture_grades_truncated _________________

    ...
>       assert ED._attempt_stdout_truncated(run_dir, state, 1) is not None
E       AssertionError: assert None is not None

plugins/superheroes/lib/tests/test_engine_dispatch.py:5666: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_cap_file_tail_rewrite_failure_preserves_over_cap_authority
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_rewrite_failure_capture_grades_truncated
2 failed in 1.15s
```

**Restore:** restored `return True, observed` at `engine_dispatch.py:1972`.

**Restore receipt:**
```
 M plugins/superheroes/lib/engine_dispatch.py
 M plugins/superheroes/lib/tests/test_engine_dispatch.py
```

**Green run:**
```
..                                                                       [100%]
2 passed in 1.13s
```

---

## Final green (grading family + capping neighbours + N5 + N6)

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
  plugins/superheroes/lib/tests/test_engine_dispatch.py::test_cap_file_tail_rewrite_failure_preserves_over_cap_authority \
  plugins/superheroes/lib/tests/test_engine_dispatch.py::test_rewrite_failure_capture_grades_truncated \
  -q
```

**Output:**
```
18 passed in 3.15s
```

---

## Whole-file green

**Command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest \
  plugins/superheroes/lib/tests/test_engine_dispatch.py -q
```

**Output:**
```
452 passed in 72.83s (0:01:12)
```
