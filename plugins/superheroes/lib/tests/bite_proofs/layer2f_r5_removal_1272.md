# Bite-proof record — #1272 layer 2f, r5 removal lane

Contract: `rubric/bite-proof.md`. Every proof below ran with the **detector unedited**; each
neutralization was a targeted, reversible edit to the guarded production site, restored by its exact
inverse (never `git checkout`), with `git status --porcelain` empty after every restore.

**Who ran these.** The r5 orchestrator (`launch-bb1dc0bc6179a567`), in its own build worktree, with
no other session reading the tree.

**Two heads.** The surviving layer-2f proofs (BP-2f-a..i, n..r, r2-a/b/f) were **re-run at the
removal head `50210df0`** — section 1. The one **new** guarded element this lane adds is BP-2f-t,
proved at the fix head — section 2. The removed finalization's records (BP-2f-j/k/l/m/s and the r2
records r2-c/d/e/g) left with the code they guarded.

Every command below was run as
`/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-bp -m pytest <node-ids> -q -p no:cacheprovider`
and every EXIT line is that runner's own exit code, not a pipe's.

---

## 1. Surviving proofs re-run at the removal head `50210df0`

### BP-2f-a — certification marker refusal

**Neutralization** (`round_certification.py`, asserted `count(old) == 1`):

```python
    if False and classification == "unrecognized":
```

**Detector.** `test_bite_bp2f_a_certification_marker_refusal`.

**Raw red** (EXIT=1):

```
E       assert None is not None
plugins/superheroes/lib/tests/test_layer2f_ledger_preconditions_1272.py:372: AssertionError
FAILED ...::test_bite_bp2f_a_certification_marker_refusal
1 failed in 0.26s
```

**Restore.** Removed the `False and` prefix.

---

### BP-2f-e + BP-2f-r2-a — live disposition-family without a ledger seat refuses

**Element merge disclosed.** At this head BP-2f-e's recorded line
(`if live.get("disposition") is not None:`) **no longer exists** — BP-2f-r2-a widened that same
site to `session_contract.has_disposition_family(live)`. The two records now guard **one** line, so
one neutralization carries both; recording them separately would be recording the same edit twice.

**Neutralization** (`round_certification.py`):

```python
            if False and session_contract.has_disposition_family(live):
```

**Detectors.** `test_bite_bp2f_e_live_disposition_without_ledger_refuses`,
`test_exclusive_read_live_disposition_without_ledger_refuses`,
`test_live_merged_into_without_ledger_seat_refuses`.

**Raw red** (EXIT=1):

```
FAILED ...::test_bite_bp2f_e_live_disposition_without_ledger_refuses
FAILED ...::test_exclusive_read_live_disposition_without_ledger_refuses
FAILED ...::test_live_merged_into_without_ledger_seat_refuses
3 failed in 0.27s
```

**Restore.** Removed the `False and` prefix.

---

### BP-2f-f — `_records` is not a source under ledger ownership

**Neutralization** (`round_certification.py`, appended to the recognized branch before its return):

```python
        for rec in state.get("_records") or []:  # bite neutralized BP-2f-f
            ...
                    by_key[key] = finding
```

**Detectors.** `test_bite_bp2f_f_records_not_a_source`,
`test_exclusive_read_records_disposition_not_seen`.

**Raw red** (EXIT=1):

```
FAILED ...::test_bite_bp2f_f_records_not_a_source
FAILED ...::test_exclusive_read_records_disposition_not_seen
2 failed in 0.18s
```

**Restore.** Removed the appended loop.

---

### BP-2f-r — ledger-owned merge preserves identity from the ledger seat

**Neutralization** (`round_certification.py`): wrapped the identity-carry loop in `if False:`.

**Detectors.** `test_bite_bp2f_r_ledger_identity_survives_merge`,
`test_ledger_owned_merge_preserves_identity_from_ledger_seat`,
`test_receipt_row_carries_identity_through_merge_path`.

**Raw red** (EXIT=1):

```
FAILED ...::test_bite_bp2f_r_ledger_identity_survives_merge
FAILED ...::test_ledger_owned_merge_preserves_identity_from_ledger_seat
FAILED ...::test_receipt_row_carries_identity_through_merge_path
3 failed in 0.25s
```

**Restore.** Removed the `if False:` wrapper.

---

### BP-2f-g — merged-row representative projection

**Neutralization** (`round_certification._project_finding`):

```python
    effective = finding if by_key is not None else finding  # bite neutralized BP-2f-g
```

**Detectors.** `test_bite_bp2f_g_merged_projection`,
`test_merged_row_projection_reports_representative_family`.

**Raw red** (EXIT=1):

```
FAILED ...::test_bite_bp2f_g_merged_projection
FAILED ...::test_merged_row_projection_reports_representative_family
2 failed in 0.27s
```

**Restore.** Restored the `_effective_certification_finding` resolution.

---

### BP-2f-h — write-run execution-only binding

**Neutralization** (`round_certification._hand_landed_evidence_qualifies`, `count(old) == 1`
asserted): replaced `return True, EXECUTION_ONLY_BINDING` with `pass`.

**Detectors.** `test_bite_bp2f_h_write_run_execution_only`,
`test_write_run_stamp_qualifies_execution_only_despite_digest_mismatch`.

**Raw red** (EXIT=1):

```
FAILED ...::test_bite_bp2f_h_write_run_execution_only
FAILED ...::test_write_run_stamp_qualifies_execution_only_despite_digest_mismatch
2 failed in 0.31s
```

**Restore.** Restored the early return.

---

### BP-2f-i — `_fold` chokepoint refusal

**Neutralization** (`round_driver._fold`):

```python
    if False and session_contract.disposition_ledger_owner_classification(state) == "unrecognized":  # bite neutralized BP-2f-i
```

**Detectors.** `test_bite_bp2f_i_fold_chokepoint_refusal`,
`test_marker_fold_chokepoint_raises_before_mutation`,
`test_marker_run_loop_parks_on_unrecognized_disposition_ledger_owner`.

**Raw red** (EXIT=1):

```
FAILED ...::test_bite_bp2f_i_fold_chokepoint_refusal
FAILED ...::test_marker_fold_chokepoint_raises_before_mutation
FAILED ...::test_marker_run_loop_parks_on_unrecognized_disposition_ledger_owner
3 failed in 0.38s
```

**Restore.** Removed the `False and` prefix.

---

### BP-2f-b — driver submit preflight — **VACUOUS AT THIS HEAD, DISCLOSED**

**Neutralization** (`round_driver._cmd_submit_prepare`):

```python
    if False and session_contract.disposition_ledger_owner_classification(state) == "unrecognized":  # bite neutralized BP-2f-b
```

**Detector.** `test_bite_bp2f_b_driver_submit_preflight_refusal`.

**Run with the guard neutralized (EXIT=0 — the detector did NOT bite):**

```
.                                                                        [100%]
1 passed in 3.78s
```

**Why.** The detector asserts two things — that `cmd_submit` refuses, and that `loop-state.json`
is byte-unchanged. With the preflight off, **both still hold**, because `_fold`'s chokepoint
(BP-2f-i) raises `DispositionLedgerOwnerRefusal` before any mutation and `cmd_submit` catches it
and returns the *same* reason without saving. Direct probe at this head, preflight neutralized:

```
submit result: {'ok': False, 'reason': 'disposition-ledger-owner-unrecognized'}
state bytes unchanged: True
```

The preflight is real defence-in-depth (it refuses one frame earlier, before the fold is entered
at all), but it has **no observable this detector can separate from the chokepoint's**. This record
therefore **retracts BP-2f-b's bite claim at this head** rather than restating the earlier red.
The proof it owes is a detector that observes the *pre-fold* refusal distinctly — for example, that
the journal carries the `submit` refusal row with no fold-phase entry beside it. Filed as a
follow-up for the advisor; not built here, because this lane's ratified scope is the removal.

**Restore.** Removed the `False and` prefix.

---

### BP-2f-c — disposition-family sync in `_record_disposition`

**Home moved, disclosed.** The record names `round_driver._apply_disposition_family`; at this head
that is a thin delegate and the pop branch lives in `session_contract.apply_disposition_family`
(the I1 single-home move). The neutralization was applied at the real home.

**Neutralization** (`session_contract.apply_disposition_family`): deleted the
`else: target.pop(field, None)` branch.

**Detectors.** `test_bite_bp2f_c_record_disposition_family_sync`,
`test_bite_bp2f_d_record_merged_into_family_sync`.

**Raw red** (EXIT=1):

```
FAILED ...::test_bite_bp2f_c_record_disposition_family_sync
FAILED ...::test_bite_bp2f_d_record_merged_into_family_sync
2 failed in 0.29s
```

**Restore.** Restored the pop branch.

---

### BP-2f-d — disposition-family sync in `_record_merged_into`

Proved **separately from BP-2f-c**, on its own site, so the shared-home neutralization above is not
the only evidence for it.

**Neutralization** (`round_driver._record_merged_into`): replaced both
`_apply_disposition_family(...)` calls with direct `MERGED_INTO_FIELD` assignment.

**Detector.** `test_bite_bp2f_d_record_merged_into_family_sync`.

**Raw red** (EXIT=1):

```
plugins/superheroes/lib/tests/test_layer2f_ledger_preconditions_1272.py:424: AssertionError
FAILED ...::test_bite_bp2f_d_record_merged_into_family_sync
1 failed in 0.38s
```

**Restore.** Restored both `_apply_disposition_family` calls.

---

### BP-2f-n — binder refusal reaches both rewritten sinks

**Neutralization** (`round_records.envelope_bind_cited_head_source`):

```python
    if False and cited_head_source not in CITED_HEAD_SOURCES:  # bite neutralized BP-2f-n
```

### BP-2f-q — review-on-fixer run-kind arm

**Neutralization** (`round_driver._assemble_dispatch_evidence`):

```python
        if False and phase == P_FIXER:  # bite neutralized BP-2f-q
```

Both neutralizations were applied together and each detector bit on its own site.

**Detectors.** `test_assemble_refuses_review_run_for_fixer_phase` (q),
`test_record_missing_sink_inherits_binder_refusal` and
`test_orchestrator_fulfilled_sink_inherits_binder_refusal` (n).

**Raw red** (EXIT=1):

```
FAILED ...test_cited_head_1272.py::test_assemble_refuses_review_run_for_fixer_phase
FAILED ...test_layer2f_cited_head_source_1272.py::test_record_missing_sink_inherits_binder_refusal
FAILED ...test_layer2f_cited_head_source_1272.py::test_orchestrator_fulfilled_sink_inherits_binder_refusal
3 failed in 4.37s
```

**Restore.** Removed both `False and` prefixes.

---

### BP-2f-o — direct-assignment census

**Neutralization** (`round_driver.cmd_record_missing`, a second assign beside the bind call):

```python
    envelope["citedHeadSource"] = round_records.CITED_HEAD_SOURCE_ORDER_ANCHOR
```

**Detector.** `test_cited_head_source_envelope_writer_census`.

**Raw red** (EXIT=1):

```
E       AssertionError: expected exactly one envelope citedHeadSource assign; got [(...round_records.py', 198, '    out["citedHeadSource"] = cited_head_source'), (...round_driver.py', 8824, '    envelope["citedHeadSource"] = round_records.CITED_HEAD_SOURCE_ORDER_ANCHOR')]
1 failed in 0.44s
```

**Restore.** Removed the inserted assign.

---

### BP-2f-p — doc-rider drift on `citedHeadSource`

**Neutralization.** Removed the `| \`citedHeadSource\` | … |` row from the documented
`seat-result/2` field table in `round-driver.md` (the authority tuple left unchanged).

**Detector.** `test_documented_seat_result_v2_fields_match_authority`.

**Raw red** (EXIT=1):

```
E       AssertionError: documented v2 fields (…, 'headSha') != SEAT_RESULT_V2_FIELDS (…, 'headSha', 'citedHeadSource')
1 failed in 0.10s
```

**Restore.** Reinstated the table row, byte-identical.

---

### BP-2f-r2-b — census bites stray member-presence read

**Neutralization** (`round_certification.py`, beside the chokepoint):

```python
            if live.get("mergedInto") is not None:
                pass
```

**Detector.** `test_disposition_family_single_home_census`.

**Raw red** (EXIT=1):

```
E       AssertionError: disposition-family member presence outside session_contract:
1 failed in 0.55s
```

**Restore.** Removed the two lines.

---

### BP-2f-r2-f — the census does not fall open on a variable's name

**Neutralization** (`round_certification._project_finding`): replaced
`row = dict(row, dispositionReceipt=proof)` with `row["dispositionReceipt"] = proof`.

**Detector.** `test_disposition_family_single_home_census`.

**Raw red** (EXIT=1):

```
E         round_certification.py:1952: row["dispositionReceipt"] = proof
E       assert not ['round_certification.py:1952: row["dispositionReceipt"] = proof']
1 failed in 0.55s
```

**Restore.** Restored the `dict(row, …)` form.

---

### Section 1 green, tree clean

```
/usr/bin/python3 … -m pytest test_layer2f_exclusive_read_1272.py test_layer2f_ledger_preconditions_1272.py \
  test_layer2f_cited_head_source_1272.py test_disposition_family_home_1272.py test_cited_head_1272.py \
  test_driver_doc_riders.py test_disposition_ledger_1272.py -q -p no:cacheprovider
EXIT=0
115 passed in 50.27s
```

`git status --porcelain` empty after every restore and at the end of section 1.

---

## 2. BP-2f-t — the verify backfill preserves the disposition family

**Guarded element.** `round_driver._backfill_fixed_disposition_verify_receipts` — the family
snapshot it carries into `_record_disposition`.

**Axis.** Stamping `verifyResult` on a same-round fixed receipt adds a field and **erases no
family member**. `_record_disposition` applies a *whole* family and pops every member the family
omits, so passing the receipt alone deletes `mergedInto`, `refutedReason`, `outOfScopeReason` and
`followUp` from a retained row. Losing `mergedInto` is a **fail-direction inversion**: a row that
certification refuses on an unresolved merge chain becomes an independently graded fixed
disposition that can certify.

**Provenance.** Raised as an Important finding by this lane's confirmation read
(codex `gpt-5.6-sol`, effort `xhigh`, attempt 2) against the removal head, verified by the
orchestrator at head, and fixed here.

**Detector.** `test_bite_verify_backfill_preserves_disposition_family`.

**Neutralization** (`round_driver._backfill_fixed_disposition_verify_receipts`) — the exact shape
the seat found:

```python
        _record_disposition(  # bite neutralized BP-2f-t
            state, key, "fixed", round_no, dispositionReceipt=updated_receipt)
```

**Raw red** (EXIT=1):

```
E       KeyError: 'mergedInto'
plugins/superheroes/lib/tests/test_disposition_ledger_1272.py:867: KeyError
FAILED ...::test_bite_verify_backfill_preserves_disposition_family
1 failed in 0.21s
```

**Restore.** Restored the family-carrying form:

```python
        family = session_contract.disposition_family_snapshot(entry)
        family.pop("disposition", None)
        family.pop("dispositionRound", None)
        family["dispositionReceipt"] = updated_receipt
        _record_disposition(state, key, "fixed", round_no, **family)
```

**Raw green** (EXIT=0):

```
/usr/bin/python3 … -m pytest test_disposition_ledger_1272.py test_round_certification.py \
  test_layer2f_exclusive_read_1272.py -q -p no:cacheprovider
178 passed in 1.42s
```

---

## 3. BP-2f-r2-f re-taken on the fix — the census bit this lane's own code

**Not a planted probe.** The first shape of BP-2f-t's fix wrote the family member by subscript:

```python
        family["dispositionReceipt"] = updated_receipt
```

That is exactly the class BP-2f-r2-f's census guards — a disposition-family member spelled
outside `session_contract` — and the **project verify gate caught it**, not the scoped test
commands this lane had been running. The census ran red against real code this session wrote:

**Raw red** (`verify_touched_tests.py --base 6407a927`, `VERIFY_GATE_EXIT=1`):

```
E       AssertionError: disposition-family member presence outside session_contract:
E         round_driver.py:1639: family["dispositionReceipt"] = updated_receipt
E       assert not ['round_driver.py:1639: family["dispositionReceipt"] = updated_receipt']
plugins/superheroes/lib/tests/test_disposition_family_home_1272.py:211: AssertionError
1 failed, 4641 passed in 414.30s (0:06:54)
```

**Fix.** The same sanctioned form BP-2f-r2-f's own restore uses:

```python
        family = dict(family, dispositionReceipt=updated_receipt)
```

**Raw green** (EXIT=0):

```
/usr/bin/python3 … -m pytest test_disposition_family_home_1272.py test_disposition_ledger_1272.py \
  test_round_certification.py test_layer2f_exclusive_read_1272.py \
  test_layer2f_ledger_preconditions_1272.py -q -p no:cacheprovider
202 passed in 14.58s
```

**Lesson recorded, not hidden.** The section-2 green for BP-2f-t did not include the census file,
so a scoped green ran while the project gate was red. The gate is the receipt; a scoped run is not.
