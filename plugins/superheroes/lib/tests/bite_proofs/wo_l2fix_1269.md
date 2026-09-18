# WO-L2FIX (#1269) bite-proof — loop-2 entry-refusal fixes

**Provenance:** cursor / composer-2.5 (implementer).

## Guarded elements

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| BP-L2FIX-1 | `_seat_dispatch_refusal` undeclared-reason grading | undeclared producer reason becomes `entry-reason-undeclared` | `test_entry_refusal_producer_undeclared_reason_becomes_entry_reason_undeclared` |
| BP-L2FIX-2 | `_entry_refusal_terminal` fail-closed field merge | producer cannot override `ok`/`terminal`/`attempts`/`forfeited` | `test_entry_refusal_terminal_fail_closed_fields_not_overridable` |
| BP-L2FIX-3 | early pre-open `run_dir` threading | opened-run continuation echoes `runOpened: true` on prompt-missing refusal | `test_early_review_prompt_missing_preserves_opened_run_provenance` |
| BP-L2FIX-4 | producer-side behavioural census | every driven producer refusal uses a declared vocabulary token | `test_entry_refusal_producer_census_declared_reasons` |

---

## BP-L2FIX-1 — undeclared seat reason grading

- **axis:** undeclared producer reason becomes `entry-reason-undeclared`

**neutralization** (`plugins/superheroes/lib/engine_dispatch.py`, `_seat_dispatch_refusal`):
```python
    outward_reason = dispatch_outcome.REASON_UNRUNNABLE  # bite-proof neutralization
```
(replaces the `if not isinstance(seat_reason, str) ...` grading block)

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_engine_dispatch.py::test_entry_refusal_producer_undeclared_reason_becomes_entry_reason_undeclared -q
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_entry_refusal_producer_undeclared_reason_becomes_entry_reason_undeclared _

    def test_entry_refusal_producer_undeclared_reason_becomes_entry_reason_undeclared(
        tmp_path, monkeypatch,
    ):
        sentinel = {"ok": False, "reason": "chokepoint-sentinel", "detail": "sentinel"}
        monkeypatch.setattr(ED.seat_bundle, "resolve_entry", lambda *a, **k: sentinel)
        res = ED.dispatch_review(
            seat=_codex_seat(),
            prompt_path=_valid_prompt(tmp_path),
            repo_root=_repo(tmp_path),
            run_engine=_never_call,
            build_view=_never_build_view,
        )
>       assert res["reason"] == ED.seat_bundle.ENTRY_REASON_UNDECLARED
E       AssertionError: assert 'unrunnable' == 'entry-reason-undeclared'

plugins/superheroes/lib/tests/test_engine_dispatch.py:9200: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_entry_refusal_producer_undeclared_reason_becomes_entry_reason_undeclared
1 failed in 0.61s
```

**restore** (`plugins/superheroes/lib/engine_dispatch.py`, `_seat_dispatch_refusal`):
```python
    if not isinstance(seat_reason, str) or seat_reason not in seat_bundle.ENTRY_REFUSAL_REASONS:
        outward_reason = seat_bundle.ENTRY_REASON_UNDECLARED
    else:
        outward_reason = dispatch_outcome.REASON_UNRUNNABLE
```

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.52s
```

---

## BP-L2FIX-2 — non-overridable chokepoint fields

- **axis:** producer cannot override `ok`/`terminal`/`attempts`/`forfeited`

**neutralization** (`plugins/superheroes/lib/engine_dispatch.py`, `_entry_refusal_terminal`):
```python
    result = {
        "attempts": 0,
        "forfeited": False,
        "terminal": True,
        **refusal,
    }  # bite-proof neutralization
```
(replaces merge-last invariant-field assignment)

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_engine_dispatch.py::test_entry_refusal_terminal_fail_closed_fields_not_overridable -q
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
________ test_entry_refusal_terminal_fail_closed_fields_not_overridable ________

    def test_entry_refusal_terminal_fail_closed_fields_not_overridable():
        ...
>       assert with_caller["attempts"] == 0
E       assert 3 == 0

plugins/superheroes/lib/tests/test_engine_dispatch.py:9503: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_entry_refusal_terminal_fail_closed_fields_not_overridable
1 failed in 0.60s
```

**restore** (`plugins/superheroes/lib/engine_dispatch.py`, `_entry_refusal_terminal`):
```python
    result = {
        **refusal,
        "ok": False,
        "terminal": True,
        "attempts": 0,
        "forfeited": False,
    }
```

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.52s
```

---

## BP-L2FIX-3 — early pre-open run provenance

- **axis:** opened-run continuation echoes `runOpened: true` on prompt-missing refusal

**neutralization** (`plugins/superheroes/lib/engine_dispatch.py`, `_dispatch_review_impl` prompt-missing branch):
```python
            engine=engine,  # bite-proof neutralization: run_dir not threaded
```
(replaces `run_dir=run_dir or "", engine=engine`)

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_engine_dispatch.py::test_early_review_prompt_missing_preserves_opened_run_provenance -q
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_______ test_early_review_prompt_missing_preserves_opened_run_provenance _______

    def test_early_review_prompt_missing_preserves_opened_run_provenance(tmp_path):
        ...
>       assert res.get("runOpened") is True
E       AssertionError: assert False is True

plugins/superheroes/lib/tests/test_engine_dispatch.py:9218: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_early_review_prompt_missing_preserves_opened_run_provenance
1 failed in 0.63s
```

**restore** (`plugins/superheroes/lib/engine_dispatch.py`, `_dispatch_review_impl` prompt-missing branch):
```python
            run_dir=run_dir or "", engine=engine,
```

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.54s
```

---

## BP-L2FIX-4 — producer-side behavioural census

- **axis:** every driven producer refusal uses a declared vocabulary token

**neutralization** (`plugins/superheroes/lib/seat_bundle.py`, `ENTRY_REFUSAL_REASONS`):
```python
    # "legacy-seat-args",  # bite-proof neutralization
```
(replaces `"legacy-seat-args",`)

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_engine_dispatch.py::test_entry_refusal_producer_census_declared_reasons -q
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_____________ test_entry_refusal_producer_census_declared_reasons ______________

    def test_entry_refusal_producer_census_declared_reasons(tmp_path, monkeypatch, capsys):
        ...
>       _assert_entry_refusal_reason(guard_legacy, "guard-check-cli-legacy")
E       AssertionError: ('guard-check-cli-legacy', 'legacy-seat-args', {...})
E       assert 'legacy-seat-args' in frozenset({...})

plugins/superheroes/lib/tests/test_engine_dispatch.py:9173: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_entry_refusal_producer_census_declared_reasons
1 failed in 0.77s
```

**restore** (`plugins/superheroes/lib/seat_bundle.py`, `ENTRY_REFUSAL_REASONS`):
```python
    "legacy-seat-args",
```

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.65s
```
