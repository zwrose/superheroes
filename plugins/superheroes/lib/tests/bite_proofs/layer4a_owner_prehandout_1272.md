# layer4a owner pre-handout bite-proof (issue #1272, WO-A)

| ID | guarded element | proving test |
|---|---|---|
| A1 | unrecognized-owner check inside `_next_response` | `test_next_refuses_unrecognized_owner_on_stored_pending` |

## A1 — unrecognized-owner check inside `_next_response`

**Axis:** unrecognized dispositionLedgerOwner refuses before a non-terminal step is handed out.

**Guarded code:** `round_driver._next_response`

**Neutralization:**

```python
    if (False and action != P_TERMINAL
```

**Detector:** `test_next_refuses_unrecognized_owner_on_stored_pending`

**Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
____________ test_next_refuses_unrecognized_owner_on_stored_pending ____________

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-5296/test_next_refuses_unrecognized0')

    def test_next_refuses_unrecognized_owner_on_stored_pending(tmp_path):
        """T1: idempotent re-emit of a stored non-terminal pending refuses before hand-out."""
        session_dir = str(tmp_path)
        n = RD.cmd_next(session_dir, _cfg())
        assert n["ok"], n
        ok, state = RD.load_state(session_dir)
        assert ok and state is not None
        state["dispositionLedgerOwner"] = "ledger-v2"
        RD.save_state(session_dir, state)
        out = RD.cmd_next(session_dir)
>       assert out["ok"] is False
E       assert True is False

plugins/superheroes/lib/tests/test_layer4a_owner_prehandout_1272.py:49: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_layer4a_owner_prehandout_1272.py::test_next_refuses_unrecognized_owner_on_stored_pending
1 failed in 2.78s
```

**Restore (quoted restored lines):**

```python
    if (action != P_TERMINAL
            and session_contract.disposition_ledger_owner_classification(state)
            == session_contract.DISPOSITION_LEDGER_OWNER_UNRECOGNIZED):
```

**Green:**

```
.                                                                        [100%]
1 passed in 3.21s
```
