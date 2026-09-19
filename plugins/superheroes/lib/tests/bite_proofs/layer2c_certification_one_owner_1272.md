# C13 layer 2c (#1272) bite-proof — certification writer one owner (WO-A2)

**Provenance:** branch `l2c-woa2/1272` at `c3d8d305`. Neutralize through a targeted edit of the
quoted production text; restore by exact inverse (never `git checkout`). Command prefix for every
run:

```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-woa2
```

## BP-2c-woa2-E1 — live disposition without ledger entry refuses (not adoption)

**Guarded element.** `round_certification._certification_findings_by_key`, the
`if finding.get("disposition") is not None:` refusal when `key not in ledger_keys`.
**Axis.** Ledger-owner mode must not adopt a live-only disposition.
**Detector.** `test_E1_live_disposition_without_ledger_entry_refuses`.

**Neutralization.** `if finding.get("disposition") is not None:` → `if False:`.

**Raw red** (exit 1):

```
FAILED plugins/superheroes/lib/tests/test_certification_one_owner_1272.py::test_E1_live_disposition_without_ledger_entry_refuses
...
>       assert refusal["detail"] == "live finding carries disposition without a ledger entry"
E       AssertionError: assert 'finding has ...tion recorded' == 'live finding... ledger entry'
```

**Restore.** `if False:` → `if finding.get("disposition") is not None:`.

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 0.15s
```

## BP-2c-woa2-E2 — unknown `dispositionLedgerOwner` refuses (not legacy merge)

**Guarded element.** `round_certification._certification_findings_by_key`, the
`if owner is not None and owner != "ledger":` refusal arm.
**Axis.** An unrecognized owner marker must fail closed instead of falling through to the legacy
three-source merge.
**Detector.** `test_E2_unknown_disposition_ledger_owner_refuses`.

**Neutralization.** `if owner is not None and owner != "ledger":` → `if False:`.

**Raw red** (exit 1):

```
FAILED plugins/superheroes/lib/tests/test_certification_one_owner_1272.py::test_E2_unknown_disposition_ledger_owner_refuses
...
>       assert refusal is not None
E       assert None is not None
```

**Restore.** `if False:` → `if owner is not None and owner != "ledger":`.

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 0.16s
```

## BP-2c-woa2-E4 — merged row without representative disposition refuses

**Guarded element.** `round_certification.check_disposition_without_receipt`, the
`if disposition is None:` refusal after `mergedInto` resolution.
**Axis.** A merged member whose representative lacks disposition must refuse, not project null
disposition past the receipt validator.
**Detector.** `test_E4_merged_row_without_representative_disposition_refuses`.

**Neutralization.** `if disposition is None:` → `if False:` (that line only in the graded loop).

**Raw red** (exit 1):

```
FAILED plugins/superheroes/lib/tests/test_certification_one_owner_1272.py::test_E4_merged_row_without_representative_disposition_refuses
...
>       assert refusal["detail"] == "finding has no disposition recorded"
E       AssertionError: assert 'unknown disposition None' == 'finding has ...tion recorded'
```

**Restore.** `if False:` → `if disposition is None:`.

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 0.14s
```

## BP-2c-woa2-E5 — write-run stamp names `execution-only` (not payload-bound)

**Guarded element.** `round_certification._hand_landed_evidence_qualifies`, the
`return True, EXECUTION_ONLY_BINDING` arm for `result_kind == session_contract.WRITE_RESULT_KIND`.
**Axis.** A write-run stamp admits execution but names the non-binding limit with the literal
`execution-only`; payload digest mismatch on a review kind still refuses.
**Detector.** `test_I3_write_run_stamp_names_execution_only` and
`test_E5_write_run_stamp_does_not_satisfy_payload_bound_proof`.

**Neutralization.** `return True, EXECUTION_ONLY_BINDING` → `return True, None`.

**Raw red** (exit 1):

```
FAILED plugins/superheroes/lib/tests/test_certification_one_owner_1272.py::test_I3_write_run_stamp_names_execution_only
...
>       assert binding == "execution-only"
E       AssertionError: assert None == 'execution-only'

FAILED plugins/superheroes/lib/tests/test_certification_one_owner_1272.py::test_E5_write_run_stamp_does_not_satisfy_payload_bound_proof
...
>       assert binding == "execution-only"
E       AssertionError: assert None == 'execution-only'
```

**Restore.** `return True, None` → `return True, EXECUTION_ONLY_BINDING`.

**Raw green** (exit 0):

```
..                                                                       [100%]
2 passed in 0.16s
```
