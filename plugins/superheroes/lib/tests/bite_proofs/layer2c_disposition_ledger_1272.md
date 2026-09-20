# C13 layer 2c (#1272) bite-proof — disposition ledger is the one owner

**Provenance:** cherry-picks `35d4f485` + `684c6996` onto head `af9ed8f2`, plus layer-2d carry
adaptation `_backfill_fixed_disposition_verify_receipts` (audits-before-verify ordering). Neutralize
through a targeted edit of the quoted production text; restore by exact inverse (never `git checkout`).
Command prefix for every run:

```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc
```

## BP-2c-a — E4 unresolvable `mergedInto` refuses (not graded undisposed)

**Guarded element.** `round_certification.check_disposition_without_receipt`, the
`if resolved is None:` refusal at the `mergedInto` resolution arm.
**Axis.** A broken merge chain must refuse `disposition-without-receipt`, not fall through to grade
the member as undisposed.
**Detector.** `test_L2_merged_away_member_resolves_through_representative` (second half).

**Neutralization.** `if resolved is None:` → `if False:` (that line only).

**Raw red** (exit 1):

```
FAILED plugins/superheroes/lib/tests/test_disposition_ledger_1272.py::test_L2_merged_away_member_resolves_through_representative
...
>           disposition = graded.get("disposition")
E           AttributeError: 'NoneType' object has no attribute 'get'
```

**Restore.** `if False:` → `if resolved is None:`.

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 0.14s
```

## BP-2c-b — E2 disposition-family strip at seeding

**Guarded element.** `round_driver._strip_disposition_family` / the `else: entry = _strip_disposition_family(entry)` arm in `_stage_findings`.
**Axis.** A self-declared disposition on a compiled candidate is stripped at seeding; only an existing ledger entry's disposition survives.
**Detector.** `test_L2_stage_findings_strips_seat_supplied_disposition_family`.

**Neutralization.** `_strip_disposition_family` body → `return dict(entry)` (skip strip).

**Raw red** (exit 1):

```
AssertionError: {'file': 'a.py', 'line': 1, 'title': 'bug', 'severity': 'Important', 'disposition': 'fixed', ...}
```

**Restore.** reinstate the `for field in _DISPOSITION_FAMILY_FIELDS: copy.pop(field, None)` loop.

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 0.14s
```

## BP-2c-c — E3 archive every departure through `_set_findings`

**Guarded element.** `round_driver._archive_departures`, invoked from `_set_findings` when a keyed finding leaves the live list.
**Axis.** Departures through the chokepoint are archived whether or not they carry a disposition.
**Detector.** `test_L7_archive_departure_without_prior_staging`.

**Neutralization.** Insert `return` immediately after the `_archive_departures` docstring (no-op the archiver).

**Raw red** (exit 1):

```
AssertionError: departed finding not archived to ledger
```

**Restore.** remove the inserted `return`.

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 0.14s
```

## BP-2c-d — flipped seam test certifying assertion

**Guarded element.** `round_driver._fold_audits` discharge loop that calls `_record_disposition` for discharged targets.
**Axis.** A converged loop with a raised finding records `fixed` on the ledger with a verify receipt.
**Detector.** `test_real_loop_with_finding_refuses_disposition_without_receipt_until_loop_records_dispositions`.

**Neutralization.** `for tid in outcome.get("discharged") or []:` → `for tid in ():`.

**Raw red** (exit 1):

```
>       assert entry["disposition"] == "fixed"
E       KeyError: 'disposition'
FAILED ...test_real_loop_with_finding_refuses_disposition_without_receipt_until_loop_records_dispositions
1 failed in 3.47s
```

**Restore.** `for tid in ():` → `for tid in outcome.get("discharged") or []:`.

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 3.46s
```

## BP-2c-e — C13 head-equality on prior-round verify carry

**Guarded element.** `round_driver._verify_result_for_disposition`, the `prior_head == bound_head`
check before returning a prior round's `verifyResult`.
**Axis.** A prior round's pass is carried onto a fixed receipt only when that round's recorded
`fixFoldHead` matches the head the receipt binds.
**Detector.** `test_C13_two_round_moving_head_verify_never_passes_refuses`.

**Neutralization.** Drop the head-equality gate — return `val` whenever a prior round has any
`verifyResult`:

```python
        val = prior_rec.get("verifyResult")
        if val is not None:
            return val
```

**Raw red** (exit 1):

```
FAILED plugins/superheroes/lib/tests/test_disposition_ledger_1272.py::test_C13_two_round_moving_head_verify_never_passes_refuses
...
>       assert receipt2.get("verifyResult") is None
E       AssertionError: assert 'pass' is None
E        +  where 'pass' = {'headSha': 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb', 'verifyResult': 'pass'}.get
1 failed in 0.16s
```

**Restore.** Reinstate the `fixFoldHead` presence and `prior_head == bound_head` guard.

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 0.17s
```

## BP-2c-f — C13 `fixFoldHead` round recording at fix fold

**Guarded element.** `round_driver._fold_fixer`, `_record_round(state, "fixFoldHead", head)` on the
successful `_resolve_fix_fold_head_sha` branch.
**Axis.** Each fix fold records the resolved head on the round record so later disposition receipts
can match prior verify verdicts head-for-head.
**Detector.** `test_C13_fix_fold_records_fix_fold_head`.

**Neutralization.** Remove the `_record_round(state, "fixFoldHead", head)` line (leave
`_record_fix_content_on_findings` and blob persistence intact).

**Raw red** (exit 1):

```
FAILED plugins/superheroes/lib/tests/test_disposition_ledger_1272.py::test_C13_fix_fold_records_fix_fold_head
...
>       assert state["rounds"]["2"]["fixFoldHead"] == head
E       KeyError: 'fixFoldHead'
1 failed in 0.16s
```

**Restore.** Reinstate `_record_round(state, "fixFoldHead", head)` before
`_record_fix_content_on_findings`.

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 0.15s
```
