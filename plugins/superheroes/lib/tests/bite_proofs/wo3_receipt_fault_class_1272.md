# Bite-proof record — #1272 WO-3 (receipt-fault typed class)

Contract: `rubric/bite-proof.md`. Every proof below ran with the **detector unedited**; the
neutralization was applied as a targeted, reversible edit to the **production call site**, and
reverted by its exact inverse.

| # | Guarded element | Axis |
|---|---|---|
| G1 | `_terminal_receipt_gate` finalization branch | finalization follows the fault's minted class, not exception text |
| G2 | `_finalize_receipt` write-fault mint | the write fault is minted `receipt-write` where it is raised |

---

## G1 — gate classification (class vs substring)

**Neutralization** (`round_driver.py` `_terminal_receipt_gate`):

```python
-        if fault is None or fault.kind != RECEIPT_FAULT_CERTIFICATION:
+        if fault is None or "certification" not in fault:
```

**Raw red** — `test_receipt_write_fault_with_certification_in_path_is_a_write_fault`:

```
F                                                                        [100%]
=================================== FAILURES ===================================
_____ test_receipt_write_fault_with_certification_in_path_is_a_write_fault _____

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-216/test_receipt_write_fault_with_0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x10377b970>

    def test_receipt_write_fault_with_certification_in_path_is_a_write_fault(tmp_path, monkeypatch):
        session_dir = _certification_refusal_session(tmp_path / "certification-run")
        ok, state = RD.load_state(session_dir)
        assert ok, state
        RD._journal_append(session_dir, {"cmd": "submit", "phase": RD.P_PANEL, "round": 1,
                                         "attempt": 0})
        real_atomic_write_bytes = RD.round_commit.atomic_write_bytes

        def _fail_receipt_write(path, data):
            if os.path.basename(path) == RD.RECEIPT_FILE:
                raise OSError("[Errno 28] No space left on device: %r" % path)
            return real_atomic_write_bytes(path, data)

        monkeypatch.setattr(RD.round_commit, "atomic_write_bytes", _fail_receipt_write)
        fault = RD._terminal_receipt_gate(session_dir, state)
        assert isinstance(fault, RD.ReceiptFault)
        assert fault.kind == RD.RECEIPT_FAULT_WRITE
        assert "certification" in fault
        ok, state_after = RD.load_state(session_dir)
        assert ok, state_after
>       assert state_after.get("_receiptFinalized") is True
E       assert None is True
E        +  where None = <built-in method get of dict object at 0x1073bb540>('_receiptFinalized')
E        +    where <built-in method get of dict object at 0x1073bb540> = {'_receiptFault': "terminal receipt write failed ([Errno 28] No space left on device: '/private/var/folders/dy/s097fm_...ig': {'baseGuard': 'not-checked', 'fixerVendor': 'claude', 'headSha': 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'}, ...}.get

plugins/superheroes/lib/tests/test_receipt_fault_class_1272.py:46: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_receipt_fault_class_1272.py::test_receipt_write_fault_with_certification_in_path_is_a_write_fault
1 failed in 1.44s
```

**Restore:** reverted to `fault.kind != RECEIPT_FAULT_CERTIFICATION`.

**Restore receipt (quoted lines):**

```python
        if fault is None or fault.kind != RECEIPT_FAULT_CERTIFICATION:
```

**Raw green:**

```
.                                                                        [100%]
1 passed in 1.50s
```

---

## G2 — raise-site class on write fault

**Neutralization** (`round_driver.py` `_finalize_receipt`):

```python
-            exc.kind)
+            RECEIPT_FAULT_CERTIFICATION)
```

**Raw red** — `test_receipt_write_fault_with_certification_in_path_is_a_write_fault` (kind
assertion); `test_certification_artifact_fault_is_not_finalized` stays green (expected):

```
F.                                                                       [100%]
=================================== FAILURES ===================================
_____ test_receipt_write_fault_with_certification_in_path_is_a_write_fault _____

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-218/test_receipt_write_fault_with_0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x1040f81c0>

    def test_receipt_write_fault_with_certification_in_path_is_a_write_fault(tmp_path, monkeypatch):
        session_dir = _certification_refusal_session(tmp_path / "certification-run")
        ok, state = RD.load_state(session_dir)
        assert ok, state
        RD._journal_append(session_dir, {"cmd": "submit", "phase": RD.P_PANEL, "round": 1,
                                         "attempt": 0})
        real_atomic_write_bytes = RD.round_commit.atomic_write_bytes

        def _fail_receipt_write(path, data):
            if os.path.basename(path) == RD.RECEIPT_FILE:
                raise OSError("[Errno 28] No space left on device: %r" % path)
            return real_atomic_write_bytes(path, data)

        monkeypatch.setattr(RD.round_commit, "atomic_write_bytes", _fail_receipt_write)
        fault = RD._terminal_receipt_gate(session_dir, state)
        assert isinstance(fault, RD.ReceiptFault)
>       assert fault.kind == RD.RECEIPT_FAULT_WRITE
E       AssertionError: assert 'certification-artifact' == 'receipt-write'
E         
E         - receipt-write
E         + certification-artifact

plugins/superheroes/lib/tests/test_receipt_fault_class_1272.py:42: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_receipt_fault_class_1272.py::test_receipt_write_fault_with_certification_in_path_is_a_write_fault
1 failed, 1 passed in 1.51s
```

**Restore:** reverted to `exc.kind`.

**Restore receipt (quoted lines):**

```python
            exc.kind)
```

**Raw green:**

```
..                                                                       [100%]
2 passed in 1.50s
```
