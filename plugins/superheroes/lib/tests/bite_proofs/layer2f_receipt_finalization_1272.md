# C13 layer 2f WO-C2 (#1272) bite-proof — fixed receipt finalization at certified head

Command prefix for every run:

```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc
```

## BP-2f-j — re-bind to the certified head

**Guarded element.** `round_driver._finalize_fixed_disposition_receipts` — `updated_receipt["headSha"] = certified_head`.
**Axis.** Every fixed receipt is rebound to the session certified head before certification reads state.
**Detector.** `test_persistence_order_rebound_on_disk`.

**Neutralization.**

```python
        pass  # bite BP-2f-j neutralized headSha rebind
```

(replaced `updated_receipt["headSha"] = certified_head`)

**Raw red** (exit 1):

```
FAILED ...test_persistence_order_rebound_on_disk
AssertionError: assert 'aaaaaaaa...' == '0000000...'
1 failed in 0.46s
```

**Restore.** Restored `updated_receipt["headSha"] = certified_head`.

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 0.40s
```

## BP-2f-k — leave-untouched rule

**Guarded element.** `round_driver._finalize_fixed_disposition_receipts` — `if binding_failure:`.
**Axis.** Never write a binding you cannot prove — unprovable entries keep their original receipt.
**Detector.** `test_unprovable_rebind_leaves_receipt_untouched_and_does_not_park`.

**Neutralization.**

```python
        if False and binding_failure:
```

**Raw red** (exit 1):

```
FAILED ...test_unprovable_rebind_leaves_receipt_untouched_and_does_not_park
AssertionError: assert {...} == {...}
1 failed
```

**Restore.** Restored `if binding_failure:`.

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed
```

## BP-2f-l — four-class fix-content classification

**Guarded element.** `round_driver._fix_still_present_at_head` — `if blobs.get("schema") != HEAD_CONTENT_BLOBS_SCHEMA:`.
**Axis.** Unsupported blob schema refuses `fix-content-schema-unsupported`, not a generic failure.
**Detector.** `test_driver_fix_content_binding_classes[fix-content-schema-unsupported]`.

**Neutralization.**

```python
    if False and blobs.get("schema") != HEAD_CONTENT_BLOBS_SCHEMA:
```

**Raw red** (exit 1):

```
FAILED ...test_driver_fix_content_binding_classes[fix-content-schema-unsupported]
AssertionError: assert 'fix-content-reverted' == 'fix-content-schema-unsupported'
1 failed
```

**Restore.** Restored schema guard.

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed
```

## BP-2f-r2-c — shared terminal step (materializer leg)

**Guarded element.** `round_driver._materialize_run_loop_session` — `_finalize_certification_inputs(session_dir, state_copy, head_sha=head)`.
**Axis.** The materializer leg runs the same certification-input finalization as the CLI terminal gate.
**Detector.** `test_both_certification_legs_reach_the_shared_terminal_step`.

**Neutralization.**

```python
        pass  # bite BP-2f-r2-c neutralized materializer _finalize_certification_inputs
```

(replaced `_finalize_certification_inputs(session_dir, state_copy, head_sha=head)`)

**Raw red** (exit 1):

```
FAILED ...test_both_certification_legs_reach_the_shared_terminal_step
AssertionError: assert {'headSha': '...', 'verifyResult': 'pass'} == {'fixContentB...', ...}
Right contains 3 more items:
 {'fixContentBytes': 12, 'fixContentDigest': '...', 'fixContentHeadSha': '...'}
1 failed in 0.41s
```

**Restore.** Restored `_finalize_certification_inputs(session_dir, state_copy, head_sha=head)`.

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 0.44s
```

## BP-2f-r2-d — ledger-driven path set

**Guarded element.** `round_driver._persist_head_content_blobs` — `paths = _fixed_ledger_content_paths(state, artifact)`.
**Axis.** Default head-content paths come from fixed ledger rows, not live `state["findings"]`.
**Detector.** `test_terminal_rebind_covers_a_ledger_only_fixed_row`.

**Neutralization.**

```python
        paths = []
        seen = set()
        for finding in (state.get("findings") or []) if isinstance(state, dict) else []:
            ...
```

(replaced `paths = _fixed_ledger_content_paths(state, artifact)` with live-findings scan)

**Raw red** (exit 1):

```
FAILED ...test_terminal_rebind_covers_a_ledger_only_fixed_row
AssertionError: assert 'f.py::fixed bug@L1' not in {'f.py::fixed bug@L1': 'fix-content-missing'}
1 failed in 0.46s
```

**Restore.** Restored `paths = _fixed_ledger_content_paths(state, artifact)`.

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 0.55s
```

## BP-2f-r2-e — one-call-site census

**Guarded element.** `round_driver._finalize_receipt` — extra `_persist_head_content_blobs` call.
**Axis.** Head-content persist has exactly one production call site inside `_finalize_certification_inputs`.
**Detector.** `test_certification_input_finalization_has_one_call_site`.

**Neutralization.**

```python
    _persist_head_content_blobs(session_dir, state, head_sha=certified_head)  # bite BP-2f-r2-e
```

(added after `_finalize_certification_inputs` in `_finalize_receipt`)

**Raw red** (exit 1):

```
FAILED ...test_certification_input_finalization_has_one_call_site
AssertionError: _persist_head_content_blobs call sites: [('_finalize_certification_inputs', 5620), ('_finalize_receipt', 6625)]
assert 2 == 1
1 failed in 0.46s
```

**Restore.** Removed the extra `_persist_head_content_blobs` line from `_finalize_receipt`.

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 0.55s
```

## BP-2f-m — persistence order (RETRACTED + replacement)

**RETRACTED as vacuous (no bite through this entry point).** Original entry below — `_terminal_receipt_gate` performs another `save_state` after `_finalize_receipt` returns, so neutralizing the save inside `_finalize_receipt` leaves `test_persistence_order_rebound_on_disk` green.

**Guarded element (original).** `round_driver._finalize_receipt` — `save_state(session_dir, state)` before `_write_receipt`.
**Axis (original).** Loop-state on disk is saved after re-bind and before round-receipt write so certification re-read sees rebound receipts.
**Detector (original).** `test_persistence_order_rebound_on_disk` (ledger + live row headSha after terminal gate).

**Unreachable through this entry point.** Swapping `_write_receipt` before `save_state`, skipping `save_state` in `_finalize_receipt`, or moving `_write_receipt` ahead of `save_state` all leave `test_persistence_order_rebound_on_disk` green: `_terminal_receipt_gate` always calls `save_state` after `_finalize_receipt` returns, so the detector reads loop-state only after that closing save. The ordering inside `_finalize_receipt` is not observable through this test path.

**Replacement proof (materializer leg).** `_finalize_certification_inputs` — `save_state(session_dir, state)`.
**Axis.** On-disk loop-state after the shared step carries re-bound receipts and fix-content fields on the materializer leg.
**Detector.** `test_both_certification_legs_reach_the_shared_terminal_step` (materialized session loaded from disk).

**Neutralization.**

```python
    pass  # bite BP-2f-m neutralized save_state inside _finalize_certification_inputs
```

(replaced `save_state(session_dir, state)`)

**Raw red** (exit 1):

```
FAILED ...test_both_certification_legs_reach_the_shared_terminal_step
AssertionError: assert {'headSha': '...', 'verifyResult': 'pass'} == {'fixContentB...', ...}
Right contains 3 more items:
 {'fixContentBytes': 12, 'fixContentDigest': '...', 'fixContentHeadSha': '...'}
1 failed in 0.64s
```

**Restore.** Restored `save_state(session_dir, state)`.

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 0.49s
```

## BP-2f-s — head unchanged stamps verify from covering gate

**Guarded element.** `round_driver._finalize_fixed_disposition_receipts` — `stamp_receipt["verifyResult"] = verify_result` (head-unchanged stamp branch).
**Axis.** When the receipt's headSha already equals the certified head, stamp verifyResult from the gate that covers that head without re-bind.
**Detector.** `test_head_unchanged_stamps_verify_result_when_blobs_unreadable`.

**Neutralization.**

```python
            pass  # bite BP-2f-s neutralized head-unchanged verifyResult stamp
```

(replaced `stamp_receipt["verifyResult"] = verify_result` in the head-unchanged stamp branch)

**Raw red** (exit 1):

```
FAILED ...test_head_unchanged_stamps_verify_result_when_blobs_unreadable
AssertionError: assert None == 'pass'
1 failed
```

**Restore.** Restored `stamp_receipt["verifyResult"] = verify_result`.

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed
```

## BP-2f-r2-g — terminal without certified head still records residuals

**Guarded element.** `round_driver._finalize_certification_inputs` — early return when certified head is unresolvable.
**Axis.** The shared terminal step always re-binds fixed receipts and saves state; only head-content read is skipped when no head resolves.
**Detector.** `test_terminal_without_certified_head_still_records_residuals`.

**Neutralization.**

```python
    if not isinstance(head, str) or not head:
        return
```

(restored WO-R2 early return that skipped re-bind and save when head is missing)

**Raw red** (exit 1):

```
FAILED ...test_terminal_without_certified_head_still_records_residuals
AssertionError: assert None == 'fix-content-missing'
1 failed in 0.46s
```

**Restore.** Removed early return; blob persist conditioned on `isinstance(head, str) and head`:

```python
    if isinstance(head, str) and head:
        _persist_head_content_blobs(session_dir, state, artifact=artifact, head_sha=head)
    _finalize_fixed_disposition_receipts(state, session_dir, state.get("config") or {})
    save_state(session_dir, state)
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 0.41s
```
