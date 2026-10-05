# WO 1273-l3b-C bite-proofs

| ID | Guarded element | Axis | Detector |
|----|-----------------|------|----------|
| BP-C1 | `round_certification._collect_seats` model source | receipt `model` comes from `executionEvidence.engineModel`, not seat map | `test_receipt_seat_model_from_execution_evidence_not_seat_map` |
| BP-C2 | `round_driver._journal_execution_evidence_fields` optional copy | `engineModel` copied when present | `test_journal_execution_evidence_fields_copies_optional_engine_model` |
| BP-C3 | `receipt_disclosures._native_in_session_seats` condition | claude seat without evidence is native | `test_native_in_session_disclosure_line_when_claude_seat_has_no_evidence` |

## BP-C1

**Neutralization.** In `_collect_seats`, read `model` from `seat_map_receipts.effective_seat_map(state)` seat config instead of journal `executionEvidence.engineModel`.

**Red.** `test_receipt_seat_model_from_execution_evidence_not_seat_map` — `AssertionError: assert 'gpt-6-astra' == 'gpt-5.6-sol'`.

**Restore.** Reverted `_collect_seats` to read `engineModel` from `event["executionEvidence"]` only.

**Green.** `1 passed in 2.35s`.

## BP-C2

**Neutralization.** Removed the `EXECUTION_EVIDENCE_OPTIONAL_FIELDS` copy loop from `_journal_execution_evidence_fields`.

**Red.** `test_journal_execution_evidence_fields_copies_optional_engine_model` — `KeyError: 'engineModel'`.

**Restore.** Restored optional-field copy loop in `_journal_execution_evidence_fields`.

**Green.** `1 passed in 2.61s`.

## BP-C3

**Neutralization.** Inverted native-seat filter to `if event.get("executionEvidence") is None: continue`.

**Red.** `test_native_in_session_disclosure_line_when_claude_seat_has_no_evidence` — expected disclosure line absent from `degraded`.

**Restore.** Restored `if event.get("executionEvidence") is not None: continue`.

**Green.** `1 passed in 2.07s`.
