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

## BP-2f-m — persistence order (certification reads post-rebind state)

**Guarded element.** `round_driver._finalize_receipt` — `save_state(session_dir, state)` before `_write_receipt`.
**Axis.** Loop-state on disk is saved after re-bind and before round-receipt write so certification re-read sees rebound receipts.
**Detector.** `test_persistence_order_rebound_on_disk` (ledger + live row headSha after terminal gate).

**Unreachable through this entry point.** Swapping `_write_receipt` before `save_state`, skipping `save_state` in `_finalize_receipt`, or moving `_write_receipt` ahead of `save_state` all leave `test_persistence_order_rebound_on_disk` green: `_terminal_receipt_gate` always calls `save_state` after `_finalize_receipt` returns, so the detector reads loop-state only after that closing save. The ordering inside `_finalize_receipt` is not observable through this test path.
