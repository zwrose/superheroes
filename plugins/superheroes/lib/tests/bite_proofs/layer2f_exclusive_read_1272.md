# Bite-proof record — #1272 layer 2f exclusive disposition read

Contract: `rubric/bite-proof.md`. Every proof below ran with the **detector unedited**; each
neutralization was a targeted, reversible edit to the guarded production site, restored by its exact
inverse (never `git checkout`).

**Who ran these.** Dispatched implementer (`l2f-wo-b`).

| # | Guarded element | Axis |
|---|---|---|
| BP-2f-e | `round_certification._certification_findings_by_key` live-disposition refusal | live disposition without a ledger seat refuses — disposition-without-receipt |
| BP-2f-f | `round_certification._certification_findings_by_key` ledger-owned branch | ledger-owned reads take disposition family from the ledger only — `_records` is not a source |
| BP-2f-g | `round_certification._project_finding` merged projection | merged-away members report the representative's disposition family, not their own |
| BP-2f-h | `round_certification._hand_landed_evidence_qualifies` write-run gate | write-run stamp proves the run happened — binds no payload (execution-only) |

**Combined neutralization run** (all four elements neutralized, one red command; all restored, one green command).

---

## BP-2f-e — live disposition without ledger entry refuses

**Neutralization** (`round_certification.py`):

```python
            if False and live.get("disposition") is not None:  # bite neutralized BP-2f-e
```

**Tests.** `test_exclusive_read_live_disposition_without_ledger_refuses`, `test_bite_bp2f_e_live_disposition_without_ledger_refuses`.

**Raw red** (excerpt from combined run):

```
FAILED ... test_exclusive_read_live_disposition_without_ledger_refuses
FAILED ... test_bite_bp2f_e_live_disposition_without_ledger_refuses
E       assert None is not None
8 failed, 3 passed in 0.78s
```

**Restore.** Removed `False and` prefix — restored line:

```python
            if live.get("disposition") is not None:
```

**Raw green:**

```
...........                                                              [100%]
11 passed in 0.83s
```

---

## BP-2f-f — `_records` is not a source under ledger ownership

**Neutralization** (`round_certification.py`, end of recognized branch):

```python
        for rec in state.get("_records") or []:  # bite neutralized BP-2f-f
            if not isinstance(rec, dict):
                continue
            for finding in rec.get("findings") or []:
                ...
                    by_key[key] = finding
```

**Tests.** `test_exclusive_read_records_disposition_not_seen`, `test_bite_bp2f_f_records_not_a_source`.

**Raw red** (excerpt from combined run):

```
FAILED ... test_exclusive_read_records_disposition_not_seen
FAILED ... test_bite_bp2f_f_records_not_a_source
E       AssertionError: assert 'refuted' is None
```

**Restore.** Removed the `_records` merge loop appended during neutralization.

**Raw green:** same as BP-2f-e green (`11 passed`).

---

## BP-2f-g — merged-row representative projection

**Neutralization** (`round_certification.py`, `_project_finding`):

```python
    effective = finding if by_key is not None else finding  # bite neutralized BP-2f-g
```

**Tests.** `test_merged_row_projection_reports_representative_family`, `test_bite_bp2f_g_merged_projection`.

**Raw red** (excerpt from combined run):

```
FAILED ... test_merged_row_projection_reports_representative_family
FAILED ... test_bite_bp2f_g_merged_projection
E       AssertionError: assert None == 'fixed'
```

**Restore.** Restored effective resolution:

```python
    effective = (
        _effective_certification_finding(finding, by_key)
        if by_key is not None
        else finding
    )
```

**Raw green:** same as BP-2f-e green (`11 passed`).

---

## BP-2f-h — write-run execution-only binding

**Neutralization** (`round_certification.py`, `_hand_landed_evidence_qualifies`):

```python
        pass  # bite neutralized BP-2f-h
```

(replaced `return True, EXECUTION_ONLY_BINDING`)

**Tests.** `test_write_run_stamp_qualifies_execution_only_despite_digest_mismatch`, `test_bite_bp2f_h_write_run_execution_only`.

**Raw red** (excerpt from combined run):

```
FAILED ... test_write_run_stamp_qualifies_execution_only_despite_digest_mismatch
FAILED ... test_bite_bp2f_h_write_run_execution_only
E       assert False is True
```

**Restore.** Restored early return:

```python
        return True, EXECUTION_ONLY_BINDING
```

**Raw green:** same as BP-2f-e green (`11 passed`).

---

## BP-2f-r — ledger-owned merge preserves identity from ledger seat

**Neutralization** (`round_certification.py`, ledger-owned merge loop):

```python
            if False:  # bite neutralized BP-2f-r
                for field in (
                    session_contract.FINDING_KEY_FIELD,
                    session_contract.RAISED_ROUND_FIELD,
                ):
                    if field in ledger_entry:
                        merged[field] = ledger_entry[field]
```

**Tests.** `test_ledger_owned_merge_preserves_identity_from_ledger_seat`,
`test_receipt_row_carries_identity_through_merge_path`,
`test_bite_bp2f_r_ledger_identity_survives_merge`.

**Raw red:**

```
..........FFF.                                                           [100%]
=================================== FAILURES ===================================
_________ test_ledger_owned_merge_preserves_identity_from_ledger_seat __________

>       assert merged[SC.FINDING_KEY_FIELD] == key
E       KeyError: 'findingKey'

_____________ test_receipt_row_carries_identity_through_merge_path _____________

>       assert row[SC.FINDING_KEY_FIELD] == key
E       KeyError: 'findingKey'

_______________ test_bite_bp2f_r_ledger_identity_survives_merge ________________

>       assert merged.get(SC.RAISED_ROUND_FIELD) == raised
E       AssertionError: assert None == 5
3 failed, 11 passed in 0.20s
```

**Restore.** Removed `if False:` wrapper — restored lines:

```python
            for field in (
                session_contract.FINDING_KEY_FIELD,
                session_contract.RAISED_ROUND_FIELD,
            ):
                if field in ledger_entry:
                    merged[field] = ledger_entry[field]
```

**Raw green:**

```
..............                                                           [100%]
14 passed in 0.18s
```

---

## BP-2f-r2-a — family reader bites (mergedInto without ledger seat)

**Guarded element.** `round_certification._certification_findings_by_key` no-ledger-seat refusal.

**Axis.** Any disposition-family member on a live finding without its own ledger seat refuses — not only `disposition`.

**Detector.** `test_live_merged_into_without_ledger_seat_refuses`.

**Neutralization** (`round_certification.py`):

```python
            if live.get("disposition") is not None:
```

(replaced `session_contract.has_disposition_family(live)`)

**Raw red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
______________ test_live_merged_into_without_ledger_seat_refuses _______________

>       assert by_key == {}
E       AssertionError: assert {'member-key'...ep-key', ...}} == {}
1 failed in 0.18s
EXIT:1
```

**Restore.** Restored line:

```python
            if session_contract.has_disposition_family(live):
```

**Raw green:**

```
.                                                                        [100%]
1 passed in 0.18s
EXIT:0
```

---

## BP-2f-r2-b — census bites stray member presence read

**Guarded element.** `test_disposition_family_single_home_census` AST census matcher.

**Axis.** No production module may test disposition-family member presence by naming a member.

**Detector.** `test_disposition_family_single_home_census`.

**Neutralization** (`round_certification.py`, beside chokepoint):

```python
            if live.get("mergedInto") is not None:
                pass
```

**Raw red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
__________________ test_disposition_family_single_home_census __________________

E       AssertionError: disposition-family member presence outside session_contract:
E         round_certification.py:405: if live.get("mergedInto") is not None:
1 failed in 0.42s
EXIT:1
```

**Restore.** Removed the two neutralization lines.

**Raw green:**

```
.                                                                        [100%]
1 passed in 0.41s
EXIT:0
```

---

## BP-2f-r2-f — the census no longer falls open on a variable's name

**Produced by the orchestrator at verification** — WO-R1b's dispatch landed its code change but
not this record; the probe below was run by the orchestrator against the committed head
`5f530af7`, with the mutation applied as a targeted edit and reverted by the inverse edit.

**Guarded element.** `test_disposition_family_home_1272._flag_disposition_family_presence_reads` —
the subscript-assignment class, after its name-keyed exemption (`_ASSIGNMENT_EXEMPT_BASES`,
`census_mode`) was deleted in WO-R1b.

**Axis.** A disposition-family member write cannot hide behind the spelling of its local. Before
WO-R1b this same neutralization was **green**, because the base was named `row`; it is red now for
no other reason.

**Detector.** `test_disposition_family_single_home_census`.

**Neutralization** (`round_certification.py`, in `_project_finding`):

```python
        row["dispositionReceipt"] = proof
```

(replaced `row = dict(row, dispositionReceipt=proof)`)

**Raw red** (1 failed):

```
E       AssertionError: disposition-family member presence outside session_contract:
E         round_certification.py:1933: row["dispositionReceipt"] = proof
E       assert not ['round_certification.py:1933: row["dispositionReceipt"] = proof']

plugins/superheroes/lib/tests/test_disposition_family_home_1272.py:212: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_disposition_family_home_1272.py::test_disposition_family_single_home_census
1 failed, 1 passed in 0.85s
```

**Restore.** Restored `row = dict(row, dispositionReceipt=proof)`.

**Raw green** (all detectors at the final head, tree clean):

```
....................................                                     [100%]
36 passed in 2.88s
```
