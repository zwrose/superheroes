# WO-O7 bite-proof — dispatch entry channel (one writer)

Three guarded elements: the outcome channel is unconditional at `_entry_refusal_terminal`; undeclared entry tokens from a real producer are normalized; the S10 `--check` stale-doc branch refuses non-zero.

---

## BP-O7-1 — outcome channel is unconditional

- **guarded element:** `plugins/superheroes/lib/engine_dispatch.py::_entry_refusal_terminal` — `result["reason"]` assignment
- **axis:** every entry refusal exposes `reason: unrunnable` on the outcome channel regardless of producer drift

**neutralization** (`plugins/superheroes/lib/engine_dispatch.py`, `_entry_refusal_terminal`):

```python
    if "reason" in refusal:
        result["reason"] = refusal["reason"]
```

(replaces `result["reason"] = dispatch_outcome.REASON_UNRUNNABLE`)

**command:**

```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest "plugins/superheroes/lib/tests/test_engine_dispatch.py::test_entry_refusal_producer_census_declared_reasons" -q
```

**raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_____________ test_entry_refusal_producer_census_declared_reasons ______________
...
>       assert reason == ED.dispatch_outcome.REASON_UNRUNNABLE, (producer, reason, result)
E       AssertionError: ('dispatch-review-library-legacy', None, {...})
E       assert None == 'unrunnable'
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_entry_refusal_producer_census_declared_reasons
1 failed in 0.72s
```

**restore:**

```python
    result["reason"] = dispatch_outcome.REASON_UNRUNNABLE
```

**restore receipt:** neutralization reverted to unconditional `result["reason"] = dispatch_outcome.REASON_UNRUNNABLE` in `_entry_refusal_terminal`.

**raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 0.69s
```

---

## BP-O7-2 — undeclared entry normalization on a real drifted producer

- **guarded element:** `plugins/superheroes/lib/engine_dispatch.py::_mode_invalid_refusal` — `entryReason` literal
- **axis:** a real producer spelling an undeclared entry token is caught by the producer census (`dispatch-review-library-mode-invalid` row)

**neutralization** (`plugins/superheroes/lib/engine_dispatch.py`, `_mode_invalid_refusal`):

```python
    return {"ok": False, "entryReason": "mode-invalidd",
```

(replaces `"mode-invalid"`)

**command:**

```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest "plugins/superheroes/lib/tests/test_engine_dispatch.py::test_entry_refusal_producer_census_declared_reasons" -q
```

**raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_____________ test_entry_refusal_producer_census_declared_reasons ______________
...
>       assert entry_reason == expected_entry_reason, (
E       AssertionError: ('dispatch-review-library-mode-invalid', 'mode-invalid', 'entry-reason-undeclared', {...})
E       assert 'entry-reason-undeclared' == 'mode-invalid'
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_entry_refusal_producer_census_declared_reasons
1 failed in 0.94s
```

**restore:**

```python
    return {"ok": False, "entryReason": "mode-invalid",
```

**restore receipt:** `_mode_invalid_refusal` `entryReason` literal restored to `"mode-invalid"`.

**raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 0.69s
```

---

## BP-O7-3 — S10 entry-doc `--check` stale branch

- **guarded element:** `plugins/superheroes/lib/dispatch_entry_doc.py::main` — stale-doc exit code
- **axis:** `--check` returns non-zero when the committed doc differs from a fresh generation

**neutralization** (`plugins/superheroes/lib/dispatch_entry_doc.py`, `main` stale branch):

```python
            return 0
```

(replaces `return 1` after the `is stale — run the generator` stderr write)

**command:**

```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest "plugins/superheroes/lib/tests/test_dispatch_entry_doc.py::test_cli_check_stale_file_refuses" -q
```

**raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
______________________ test_cli_check_stale_file_refuses _______________________
...
>       assert rc == 1
E       assert 0 == 1
----------------------------- Captured stderr call -----------------------------
dispatch_entry_doc error: .../dispatch-entry.md is stale — run the generator
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_dispatch_entry_doc.py::test_cli_check_stale_file_refuses
1 failed in 0.16s
```

**restore:**

```python
            return 1
```

**restore receipt:** stale `--check` branch restored to `return 1`.

**raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 0.69s
```

(when run together with BP-O7-2 green: `2 passed in 0.69s`)
