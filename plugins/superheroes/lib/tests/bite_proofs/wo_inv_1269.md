# WO-INV-1269 bite-proof — entry-refusal run provenance by invariant

**Provenance:** cursor composer-2.5 / dispatch-write

## Guarded elements

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| BP-INV-1 | AST chokepoint invariant | no inline `runDir` dict literal or `runOpened` stamp on entry-refusal paths | `test_entry_refusal_chokepoint_invariant_no_inline_run_dir_or_run_opened_stamp` |
| BP-INV-2 | `_entry_refusal_terminal` provenance | continuation entry refusal echoes `runOpened: true` and journal `resolvedInputs` | `test_entry_unknown_kwargs_refusal_preserves_existing_review_run_provenance` |
| BP-INV-3 | `resolve_entry` mode/role ordering | resumed review run with mode disagreement reaches `run-dir-mode-mismatch` with provenance | `test_continuation_brief_check_mode_on_review_run_refuses_with_provenance` |

---

## BP-INV-1 — AST chokepoint invariant

- **axis:** entry-refusal paths must not return dict literals carrying `runDir` or assign `runOpened`

**neutralization** (`plugins/superheroes/lib/engine_dispatch.py`, `dispatch_review` legacy-call branch): replace `_entry_refusal_terminal(...)` with an inline dict return carrying `"runDir": ""`.

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_engine_dispatch.py::test_entry_refusal_chokepoint_invariant_no_inline_run_dir_or_run_opened_stamp -q
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_entry_refusal_chokepoint_invariant_no_inline_run_dir_or_run_opened_stamp _

    def test_entry_refusal_chokepoint_invariant_no_inline_run_dir_or_run_opened_stamp():
        ...
>       assert run_dir_violations == []
E       AssertionError: assert [('dispatch_review', 3832)] == []
E         
E         Left contains one more item: ('dispatch_review', 3832)

plugins/superheroes/lib/tests/test_engine_dispatch.py:9152: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_entry_refusal_chokepoint_invariant_no_inline_run_dir_or_run_opened_stamp
1 failed in 0.54s
```

**restore:** revert `dispatch_review` legacy-call branch to `return _entry_refusal_terminal(_legacy_dispatch_refusal(...), run_dir=run_dir, mode=...)`.

**raw green:**
```
.                                                                        [100%]
1 passed in 0.47s
```

---

## BP-INV-2 — entry refusal preserves run provenance

- **axis:** non-allowlist entry refusal on a live opened run echoes `runOpened: true` and `resolvedInputs`

**neutralization** (`plugins/superheroes/lib/engine_dispatch.py`, `_entry_refusal_terminal` tail):
```python
    out["runOpened"] = False
    out["runDir"] = ""
    return out
```
(appended unconditionally before return)

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_engine_dispatch.py::test_entry_unknown_kwargs_refusal_preserves_existing_review_run_provenance -q
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
__ test_entry_unknown_kwargs_refusal_preserves_existing_review_run_provenance __

    def test_entry_unknown_kwargs_refusal_preserves_existing_review_run_provenance(tmp_path):
        ...
        assert res["reason"] == "unknown-dispatch-kwargs"
>       assert res.get("runOpened") is True
E       AssertionError: assert False is True

plugins/superheroes/lib/tests/test_engine_dispatch.py:9197: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_entry_unknown_kwargs_refusal_preserves_existing_review_run_provenance
1 failed in 0.50s
```

**restore:** remove the unconditional `runOpened`/`runDir` stamping; restore direct `return _finish_preflight_terminal(...)` / `return _with_run_fields(...)`.

**raw green:**
```
.                                                                        [100%]
1 passed in 0.42s
```

---

## BP-INV-3 — continuation mode sentinel ordering

- **axis:** resumed review run with caller `mode=brief-check` on a `review` journal reaches `run-dir-mode-mismatch`, not `mode-role-mismatch` with `runOpened: false`

**neutralization** (`plugins/superheroes/lib/seat_bundle.py`, `resolve_entry` after `role = parsed["role"]`):
```python
    if verb == "dispatch-review" and mode == _MODE_BRIEF_CHECK and role != "brief-check":
        return _mode_role_coherence_refusal(role)
    elif mode == _MODE_BRIEF_CHECK and role != "brief-check":
        return _mode_role_coherence_refusal(role)
```

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_engine_dispatch.py::test_continuation_brief_check_mode_on_review_run_refuses_with_provenance -q
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
___ test_continuation_brief_check_mode_on_review_run_refuses_with_provenance ___

    def test_continuation_brief_check_mode_on_review_run_refuses_with_provenance(tmp_path):
        ...
>       assert res["detail"] == ED.MODE_REFUSAL_RUN_DIR_MISMATCH
E       assert '--mode brief...anical, pilot' == 'run-dir-mode-mismatch'

plugins/superheroes/lib/tests/test_engine_dispatch.py:9245: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_continuation_brief_check_mode_on_review_run_refuses_with_provenance
1 failed in 0.48s
```

**restore:** remove the two early-return legs; keep the single `_dispatch_review_mode_role_refusal` call after vendor validation and before allowlist.

**raw green:**
```
.                                                                        [100%]
1 passed in 0.42s
```

---

# WO-INV2-1269 bite-proof — confine runDir clearing to entry-refusal chokepoint

**Provenance:** cursor composer-2.5 / dispatch-write

## Guarded elements

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| BP-INV2-1 | `_attach_resolved_inputs_echo` no longer clears `runDir` | non-entry-refusal results preserve caller `runDir` when `runOpened` is false | `test_dispatch_review_engine_config_refusal_preserves_caller_run_dir` |
| BP-INV2-2 | `main()` dropped-flag `--run-dir` scan | attached `--run-dir=<path>` carries opened-run provenance on refusal | `test_main_dropped_flag_attached_run_dir_carries_provenance` |

---

## BP-INV2-1 — run-directory survives on non-entry-refusal paths

- **axis:** pre-open engine-config refusal echoes caller `runDir` with `runOpened: false`

**neutralization** (`plugins/superheroes/lib/engine_dispatch.py`, `_attach_resolved_inputs_echo` tail): restore the two-line clearing:
```python
    if not out.get("runOpened"):
        out["runDir"] = ""
```

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_engine_dispatch.py::test_dispatch_review_engine_config_refusal_preserves_caller_run_dir -q
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_____ test_dispatch_review_engine_config_refusal_preserves_caller_run_dir ______

    def test_dispatch_review_engine_config_refusal_preserves_caller_run_dir(tmp_path, monkeypatch):
        ...
        assert res.get("runOpened") is False
>       assert res["runDir"] == os.path.realpath(run_dir)
E       AssertionError: assert '' == '/private/var...ne-config-run'

plugins/superheroes/lib/tests/test_engine_dispatch.py:9333: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_dispatch_review_engine_config_refusal_preserves_caller_run_dir
1 failed in 0.49s
```

**restore:** remove the two-line clearing from `_attach_resolved_inputs_echo`; clearing lives only in `_entry_refusal_terminal`.

**raw green:**
```
.                                                                        [100%]
1 passed in 0.41s
```

---

## BP-INV2-2 — main() attached-form `--run-dir` scan

- **axis:** dropped-flag refusal with `--run-dir=<path>` on an opened run echoes `runOpened: true` and journal provenance

**neutralization** (`plugins/superheroes/lib/engine_dispatch.py`, `main()` dropped-flag scan): remove the `arg.startswith("--run-dir=")` branch so only the two-token form is accepted.

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_engine_dispatch.py::test_main_dropped_flag_attached_run_dir_carries_provenance -q
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
__________ test_main_dropped_flag_attached_run_dir_carries_provenance __________

    def test_main_dropped_flag_attached_run_dir_carries_provenance(capsys, tmp_path):
        ...
        assert res["reason"] == "legacy-seat-args"
>       assert res.get("runOpened") is True
E       AssertionError: assert False is True

plugins/superheroes/lib/tests/test_engine_dispatch.py:9381: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_main_dropped_flag_attached_run_dir_carries_provenance
1 failed in 0.48s
```

**restore:** re-add the `arg.startswith("--run-dir=")` branch alongside the two-token scan.

**raw green:**
```
.                                                                        [100%]
1 passed in 0.41s
```
