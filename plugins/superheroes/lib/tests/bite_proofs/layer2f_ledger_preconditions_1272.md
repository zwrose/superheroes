# Bite-proof record — #1272 layer 2f ledger preconditions

Contract: `rubric/bite-proof.md`. Every proof below ran with the **detector unedited**; each
neutralization was a targeted, reversible edit to the guarded production site, restored by its exact
inverse (never `git checkout`).

**Who ran these.** Dispatched implementer (`l2f-wo-a`).

| # | Guarded element | Axis |
|---|---|---|
| BP-2f-a | `round_certification._certification_findings_by_key` unrecognized-marker refusal | unrecognized `dispositionLedgerOwner` refuses — never legacy `_records` merge |
| BP-2f-b | `round_driver._cmd_submit_prepare` submit preflight | unrecognized marker refuses submit before fold — `loop-state.json` byte-unchanged |
| BP-2f-c | `round_driver._apply_disposition_family` via `_record_disposition` | re-staged family byte-equal on ledger and live; stale members popped |
| BP-2f-d | `round_driver._apply_disposition_family` via `_record_merged_into` | merge family is only `mergedInto` on ledger and live |

---

## BP-2f-a — certification marker refusal

**Neutralization** (`round_certification.py`):

```python
    if False and classification == "unrecognized":  # bite neutralized BP-2f-a
```

**Test.** `test_bite_bp2f_a_certification_marker_refusal` (+ three certification entry-point tests).

**Raw red:**

```
FFFF......F...                                                           [100%]
5 failed, 9 passed in 4.28s
```

**Restore.** Removed `False and` prefix — restored line:

```python
    if classification == "unrecognized":
```

**Raw green:**

```
..............                                                           [100%]
14 passed in 4.15s
```

---

## BP-2f-b — driver submit preflight

**Neutralization** (`round_driver.py`):

```python
    if False and session_contract.disposition_ledger_owner_classification(state) == "unrecognized":  # bite neutralized BP-2f-b
```

**Test.** `test_bite_bp2f_b_driver_submit_preflight_refusal`.

**Raw red:**

```
F                                                                        [100%]
FAILED ... test_bite_bp2f_b_driver_submit_preflight_refusal
E       assert True is False
1 failed in 3.24s
```

**Restore.** Removed `False and` prefix — restored line:

```python
    if session_contract.disposition_ledger_owner_classification(state) == "unrecognized":
```

**Raw green:** same as BP-2f-a green (`14 passed`).

---

## BP-2f-c — disposition family sync in `_record_disposition`

**Neutralization** (`round_driver._apply_disposition_family`):

```python
        if field in family:
            target[field] = family[field]
        # bite neutralized BP-2f-c: pop omitted family members
```

(The `else: target.pop(field, None)` branch removed.)

**Test.** `test_bite_bp2f_c_record_disposition_family_sync`.

**Raw red:**

```
F                                                                        [100%]
FAILED ... test_bite_bp2f_c_record_disposition_family_sync
E       AssertionError: assert 'refutedReason' not in {...}
1 failed in 0.19s
```

**Restore.** Restored pop branch:

```python
        else:
            target.pop(field, None)
```

**Raw green:** same as BP-2f-a green (`14 passed`).

---

## BP-2f-d — disposition family sync in `_record_merged_into`

**Neutralization** (`round_driver._record_merged_into`):

```python
    entry[session_contract.MERGED_INTO_FIELD] = into_key  # bite neutralized BP-2f-d
    ...
    if live is not None:
        live[session_contract.MERGED_INTO_FIELD] = into_key
```

(replaced `_apply_disposition_family` calls)

**Test.** `test_bite_bp2f_d_record_merged_into_family_sync`.

**Raw red:**

```
F                                                                        [100%]
FAILED ... test_bite_bp2f_d_record_merged_into_family_sync
E       AssertionError: assert {'disposition'... 'mergedInto'} == {'mergedInto'}
1 failed in 0.20s
```

**Restore.** Restored `_apply_disposition_family` calls for entry and live.

**Raw green:** same as BP-2f-a green (`14 passed`).
