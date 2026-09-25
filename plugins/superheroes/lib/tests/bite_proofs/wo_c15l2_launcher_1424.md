# WO-A C15 layer 2 (#1424) bite-proofs — launcher compose refusal + canary truncation bit

## BP-v4 — compose refusal keys on `reason` (not `ok`)

**Guarded element:** `compose_launch` adapter refusal chokepoint — axis: refuse when `reason` is set, not when a nonexistent `ok` is false.

**Neutralization:** replaced condition with `if built.get("ok") is False:` (detail-forwarding body left in place but unreachable for the fake).

**Command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest "plugins/superheroes/lib/tests/test_launcher.py::test_compose_launch_propagates_adapter_refusal" -q -p no:randomly
```

**Red run:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
________________ test_compose_launch_propagates_adapter_refusal ________________
...
>       assert result["ok"] is False
E       assert True is False
plugins/superheroes/lib/tests/test_launcher.py:651: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher.py::test_compose_launch_propagates_adapter_refusal
1 failed in 5.62s
```

**Restore:** `if built.get("reason") is not None:` with detail key forwarding restored.

**Restore receipt:**
```python
    if built.get("reason") is not None:
        if "detail" in built:
            return _fail(built["reason"], detail=built["detail"])
        return _fail(built["reason"])
```

**Green run:**
```
.                                                                        [100%]
1 passed in 5.19s
```

---

## BP-v13 — compose refusal forwards adapter `detail`

**Guarded element:** same chokepoint — axis: `detail` key from adapter copied into `_fail` when present.

**Neutralization:** `return _fail(built["reason"])` only (dropped `detail` branch).

**Command:** same as BP-v4.

**Red run:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
________________ test_compose_launch_propagates_adapter_refusal ________________
...
>       assert result["detail"] == "a canonical lowercase UUID string"
E       KeyError: 'detail'
plugins/superheroes/lib/tests/test_launcher.py:653: KeyError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher.py::test_compose_launch_propagates_adapter_refusal
1 failed in 5.40s
```

**Restore:** detail branch restored (same quoted block as BP-v4 restore).

**Green run:**
```
.                                                                        [100%]
1 passed in 4.18s
```

---

## BP-v1 — canary truncation follows reader bit

**Guarded element:** `canary` transcript truncation refusal — axis: `truncated` from reader, not `size > MAX_STDOUT_CAPTURE`.

**Neutralization:** `if size > engine_dispatch.MAX_STDOUT_CAPTURE and tool_calls == 0:`

**Command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest "plugins/superheroes/lib/tests/test_launcher.py::test_canary_truncation_follows_reader_bit" -q -p no:randomly
```

**Red run:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
__________________ test_canary_truncation_follows_reader_bit ___________________
...
>       assert result["reason"] == "canary-transcript-truncated"
E       AssertionError: assert None == 'canary-transcript-truncated'
plugins/superheroes/lib/tests/test_launcher.py:7841: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher.py::test_canary_truncation_follows_reader_bit
1 failed in 4.47s
```

**Restore:** `if truncated and tool_calls == 0:`

**Restore receipt:**
```python
    if truncated and tool_calls == 0:
        return _fail("canary-transcript-truncated")
```

**Green run:**
```
.                                                                        [100%]
1 passed in 4.30s
```
