# Bite-proof record — #1272 layer 2f citedHeadSource declaration and binder sinks

Contract: `rubric/bite-proof.md`. Every proof below ran with the **detector unedited**; each
neutralization was a targeted, reversible edit to the guarded production site, restored by its exact
inverse (never `git checkout`).

**Who ran these.** Dispatched implementer (`l2f-wo-d`).

| ID | Guarded element | Axis |
|---|---|---|
| BP-2f-n | `round_records.envelope_bind_cited_head_source` refusal at the two rewritten driver sinks | invalid `citedHeadSource` refused at `record-missing` and `_orchestrator_fulfilled_envelope` bind sites |
| BP-2f-o | `test_cited_head_source_envelope_writer_census` | exactly one subscript assign of `citedHeadSource` onto an envelope in shipped lib source |
| BP-2f-p | `test_documented_seat_result_v2_fields_match_authority` | documented `seat-result/2` table matches `SEAT_RESULT_V2_FIELDS` |
| BP-2f-q | `round_driver._assemble_dispatch_evidence` review-on-fixer arm | review run on fixer phase refuses `evidence-run-kind-mismatch` |

Command prefix for every run:

```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc
```

---

## BP-2f-n — binder refusal reaches both rewritten sinks

**Neutralization** (`round_records.py`, inside `envelope_bind_cited_head_source` only):

```python
    if False and cited_head_source not in CITED_HEAD_SOURCES:
```

**Detectors.** `test_record_missing_sink_inherits_binder_refusal`,
`test_orchestrator_fulfilled_sink_inherits_binder_refusal`.

**Raw red** (exit 1):

```
FF                                                                       [100%]
FAILED ...::test_record_missing_sink_inherits_binder_refusal
E           Failed: DID NOT RAISE <class 'round_records.IncompleteRevisionIdentity'>
FAILED ...::test_orchestrator_fulfilled_sink_inherits_binder_refusal
E           Failed: DID NOT RAISE <class 'round_records.IncompleteRevisionIdentity'>
2 failed in 4.15s
```

**Restore.** Removed `False and` prefix — restored line:

```python
    if cited_head_source not in CITED_HEAD_SOURCES:
```

**Raw green** (exit 0):

```
..                                                                       [100%]
2 passed in 4.13s
```

---

## BP-2f-o — direct-assignment census

**Neutralization** (`round_driver.py`, inside `cmd_record_missing` after the bind call):

```python
    envelope["citedHeadSource"] = round_records.CITED_HEAD_SOURCE_ORDER_ANCHOR
```

**Detector.** `test_cited_head_source_envelope_writer_census`.

**Raw red** (exit 1):

```
F                                                                        [100%]
FAILED ...::test_cited_head_source_envelope_writer_census
E       AssertionError: expected exactly one envelope citedHeadSource assign; got [... round_driver.py', 8927, '    envelope["citedHeadSource"] = round_records.CITED_HEAD_SOURCE_ORDER_ANCHOR')]
1 failed in 1.15s
```

**Restore.** Removed the inserted duplicate assign line.

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 1.12s
```

---

## BP-2f-p — doc-rider drift on `citedHeadSource`

**Neutralization.** Removed the `| \`citedHeadSource\` | ... |` row from the documented
`seat-result/2` field table in `round-driver.md` (authority tuple unchanged).

**Detector.** `test_documented_seat_result_v2_fields_match_authority`.

**Raw red** (exit 1):

```
F                                                                        [100%]
FAILED ...::test_documented_seat_result_v2_fields_match_authority
E       AssertionError: documented v2 fields (... 'headSha') != SEAT_RESULT_V2_FIELDS (... 'headSha', 'citedHeadSource')
E         Right contains one more item: 'citedHeadSource'
1 failed in 0.25s
```

**Restore.** Reinstated the `citedHeadSource` table row.

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 0.24s
```

---

## BP-2f-q — review-on-fixer run-kind arm

**Neutralization** (`round_driver.py`, `_assemble_dispatch_evidence`):

```python
        if False and phase == P_FIXER:
```

**Detector.** `test_assemble_refuses_review_run_for_fixer_phase`.

**Raw red** (exit 1):

```
F                                                                        [100%]
FAILED ...::test_assemble_refuses_review_run_for_fixer_phase
E       AssertionError: assert 'evidence-result-mismatch' == 'evidence-run-kind-mismatch'
1 failed in 0.72s
```

**Restore.** Removed `False and` prefix — restored line:

```python
        if phase == P_FIXER:
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 0.71s
```
