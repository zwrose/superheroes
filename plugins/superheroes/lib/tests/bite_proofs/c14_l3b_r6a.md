# C14 layer 3b R6A bite-proofs

| ID | Guarded element | Axis | Detector |
|----|-----------------|------|----------|
| BP-R6A-1 | `receipt_disclosures.latest_recorded_events` | last-wins per record identity | `test_native_in_session_disclosure_not_named_when_runner_replaces_native` |
| BP-R6A-2 | `receipt_disclosures._native_in_session_seats` | record-missing is never native | `test_native_in_session_disclosure_record_missing_not_named` |
| BP-R6A-3 | `round_certification._collect_seats` | the one reducer chokepoint | `test_native_in_session_and_collect_seats_share_latest_recorded_events` |
| BP-R6A-4 | `round_certification._collect_seats` | runner-only model | `test_receipt_seat_model_none_when_hand_landed_transport` |
| BP-R6A-5 | `receipt_disclosures._is_missing_seat_record` | casToken arm | `test_native_in_session_disclosure_reappended_missing_cas_token_not_named`, `test_native_in_session_disclosure_journal_stored_revision_missing_not_named` |

## BP-R6A-1

**Axis:** last-wins per record identity.

**Neutralization:** `latest_recorded_events` keeps the first event per key (`if key in latest: continue`) instead of the latest.

**Red:** `AssertionError: assert ['code-reviewer'] == []` in `test_native_in_session_disclosure_not_named_when_runner_replaces_native`.

**Restore:** Restored last-wins assignment (`latest[key] = (identity, event)` on every event).

**Green:** `1 passed`.

## BP-R6A-2

**Axis:** record-missing is never native.

**Neutralization:** Deleted the `record-missing` skip in `_native_in_session_seats`.

**Red:** `AssertionError: assert ['code-reviewer'] == []` in `test_native_in_session_disclosure_record_missing_not_named`.

**Restore:** Restored `if event.get("cmd") == "record-missing": continue`.

**Green:** `1 passed`.

## BP-R6A-3

**Axis:** the one reducer chokepoint.

**Neutralization:** `_collect_seats` iterates `ctx["journal"]` directly with an inline copy of the reducer instead of calling `latest_recorded_events`.

**Red:** `AssertionError: assert 1 == 2` in `test_native_in_session_and_collect_seats_share_latest_recorded_events`.

**Restore:** Restored `_collect_seats` to map over `receipt_disclosures.latest_recorded_events(ctx["journal"])`.

**Green:** `1 passed`.

## BP-R6A-4

**Axis:** runner-only model.

**Neutralization:** Dropped the transport condition on `model` in `_collect_seats` (always reads `executionEvidence.engineModel`).

**Red:** `AssertionError: assert 'gpt-5.6-sol' is None` in `test_receipt_seat_model_none_when_hand_landed_transport`.

**Restore:** Restored `if event.get(session_contract.SEAT_TRANSPORT_KEY) == session_contract.SEAT_TRANSPORT_RUNNER:` guard around model extraction.

**Green:** `1 passed`.

## BP-R6A-5

**Axis:** casToken arm.

**Neutralization:** Deleted the `casToken` arm of `_is_missing_seat_record` (kept only `cmd == "record-missing"`).

**Red:** `AssertionError: assert ['code-reviewer'] == []` in `test_native_in_session_disclosure_reappended_missing_cas_token_not_named` and `test_native_in_session_disclosure_journal_stored_revision_missing_not_named`.

**Restore:** Restored `or event.get("casToken") == session_contract.SEAT_MISSING_SCHEMA` in `_is_missing_seat_record`.

**Green:** `2 passed`.
