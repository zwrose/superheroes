# layer4a owner pre-handout bite-proof (issue #1272, WO-A)

| ID | guarded element | proving test |
|---|---|---|
| A1 | unrecognized-owner check in `_disposition_ledger_owner_refusal` | `test_next_refuses_unrecognized_owner_on_stored_pending` |
| A2 | re-emit disposition-ledger owner gate | `test_re_emit_refuses_unrecognized_disposition_ledger_owner` |

## A1 — unrecognized-owner check in `_disposition_ledger_owner_refusal`

**Axis:** unrecognized dispositionLedgerOwner refuses before a non-terminal step is handed out.

**Guarded code:** `round_driver._disposition_ledger_owner_refusal`

**Neutralization:**

```python
    if (False
            and session_contract.disposition_ledger_owner_classification(state)
            == session_contract.DISPOSITION_LEDGER_OWNER_UNRECOGNIZED):
```

**Detector:** `test_next_refuses_unrecognized_owner_on_stored_pending`

**Restore (quoted restored lines):**

```python
    if (session_contract.disposition_ledger_owner_classification(state)
            == session_contract.DISPOSITION_LEDGER_OWNER_UNRECOGNIZED):
```

## A2 — re-emit disposition-ledger owner gate

**Axis:** `cmd_re_emit` refuses when dispositionLedgerOwner is unrecognized and does not bump pending attempt.

**Guarded code:** `_cmd_re_emit_locked` call to `_disposition_ledger_owner_refusal`

**Detector:** `test_re_emit_refuses_unrecognized_disposition_ledger_owner`
