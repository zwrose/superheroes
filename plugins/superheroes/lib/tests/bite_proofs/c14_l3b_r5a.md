# C14 layer 3b R5A bite-proofs

| ID | Guarded element | Axis | Detector |
|----|-----------------|------|----------|
| BP-R5A-1 | `round_driver._journal_transport_fields` | every recorded row carries transport from the stored envelope | `test_record_result_journal_stamps_transport` |
| BP-R5A-2 | `SEAT_TRANSPORTS_DISCLOSED` | hand-landed transport is disclosed | `test_native_in_session_disclosure_transport_param[hand-landed]` |
| BP-R5A-3 | `receipt_disclosures._native_in_session_seats` | unstamped events fail closed (named) | `test_native_in_session_disclosure_transport_param[missing]` |
| BP-R5A-4 | `receipt_disclosures._native_in_session_seats` | runner transport is never disclosed | `test_unprobed_native_seat_disclosure_at_receipt_boundary` |

## BP-R5A-1

**Axis:** every recorded row carries transport from the stored envelope.

**Neutralization:** `_journal_transport_fields` returns `{}` immediately.

**Red:** `AssertionError: assert None == 'hand-landed'` in `test_record_result_journal_stamps_transport`.

**Restore:** removed the early `return {}`.

**Green:** `1 passed`.

## BP-R5A-2

**Axis:** hand-landed transport is disclosed.

**Neutralization:** `SEAT_TRANSPORTS_DISCLOSED = (SEAT_TRANSPORT_NATIVE,)`.

**Red:** `AssertionError: assert [] == ['code-reviewer']` in `test_native_in_session_disclosure_transport_param[hand-landed]`.

**Restore:** restored `SEAT_TRANSPORT_HAND_LANDED` to the tuple.

**Green:** `1 passed`.

## BP-R5A-3

**Axis:** unstamped events fail closed (named).

**Neutralization:** `_native_in_session_seats` `else: disclosed.add(seat)` → `else: continue`.

**Red:** `AssertionError: assert [] == ['code-reviewer']` in `test_native_in_session_disclosure_transport_param[missing]`.

**Restore:** `else: disclosed.add(seat)`.

**Green:** `1 passed`.

## BP-R5A-4

**Axis:** runner transport is never disclosed.

**Neutralization:** disclosed branch also names `SEAT_TRANSPORT_RUNNER`.

**Red:** `assert any(disclosure_line % native_seat in line for line in degraded)` failed in `test_unprobed_native_seat_disclosure_at_receipt_boundary` (runner co-named on the degraded line).

**Restore:** removed runner from the disclosed branch.

**Green:** `1 passed`.
