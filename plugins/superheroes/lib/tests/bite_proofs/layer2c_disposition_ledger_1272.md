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
**Detector.** Inline probe (no dedicated unit test): stage a compiled finding carrying `disposition: fixed` and assert the ledger entry has no disposition.

**Neutralization.** `_strip_disposition_family` body → `return dict(entry)` (skip strip).

**Raw red** (exit 1):

```
AssertionError: {'file': 'a.py', 'line': 1, 'title': 'bug', 'severity': 'Important', 'disposition': 'fixed', ...}
```

**Restore.** reinstate the `for field in _DISPOSITION_FAMILY_FIELDS: copy.pop(field, None)` loop.

**Raw green** (exit 0): inline probe completes with no assertion (exit 0).

## BP-2c-c — E3 archive every departure through `_set_findings`

**Guarded element.** `round_driver._archive_departures`, invoked from `_set_findings` when a keyed finding leaves the live list.
**Axis.** Departures through the chokepoint are archived whether or not they carry a disposition.
**Detector.** Inline probe: `_set_findings(state, compiled)` then `_set_findings(state, [])`; assert departed key is on the ledger.

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
(`test_L7_departure_outside_chokepoint_still_on_ledger` also passes restored.)

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
