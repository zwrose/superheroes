# Bite-proof record — layer 3B certification writer (#1272)

| Element | Guarded code | Detector |
| --- | --- | --- |
| B1 | `round_certification._hand_landed_evidence_qualifies` write-stamp phase gate | `test_l3_b1_write_stamp_out_of_phase_refused` |
| B2 | `round_certification.check_disposition_without_receipt` non-blocking disclosure branch | `test_l3_b2_nonblocking_survivor_disclosed_not_refused` |
| B3 | `round_certification.check_disposition_without_receipt` Critical non-blocking prohibition | `test_l3_b3_critical_may_not_take_the_nonblocking_path` |

## B1 — write-run stamp admissible only on fixer phase

**Neutralization** (`round_certification.py`, `_hand_landed_evidence_qualifies`):

```python
        if False and not session_contract.execution_only_admissible_for_phase(phase):
            return False, "execution-evidence-write-stamp-out-of-phase"
```

**Red** (`test_l3_b1_write_stamp_out_of_phase_refused`):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_________________ test_l3_b1_write_stamp_out_of_phase_refused __________________

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-4488/test_l3_b1_write_stamp_out_of_0')

    def test_l3_b1_write_stamp_out_of_phase_refused(tmp_path):
        for phase in (RC.PANEL_PHASE, RC.AUDITS_PHASE):
            ctx, _ = RC._load_context(_write_stamp_session(tmp_path / phase, phase))
            refusal = RC.check_unrun_review(ctx)
>           assert refusal is not None
E           assert None is not None

plugins/superheroes/lib/tests/test_layer3_certification_writer_1272.py:126: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_layer3_certification_writer_1272.py::test_l3_b1_write_stamp_out_of_phase_refused
1 failed in 0.23s
```

**Restore.** Replaced `if False and not session_contract.execution_only_admissible_for_phase(phase):` with `if not session_contract.execution_only_admissible_for_phase(phase):`.

**Green** (`test_l3_b1_write_stamp_out_of_phase_refused`):

```
.                                                                        [100%]
1 passed in 0.13s
```

## B2 — non-blocking survivor disclosed, not refused

**Neutralization** (`round_certification.py`, `check_disposition_without_receipt`):

```python
            if False:
                nonblocking_disclosures.append(
                    {
                        "id": finding.get("id"),
                        "title": finding.get("title"),
                        "severity": severity,
                    }
                )
                continue
            return _refusal(
                "disposition-without-receipt",
                fid,
                "finding has no disposition recorded",
            )
```

(replacing the live `nonblocking_disclosures.append` / `continue` pair)

**Red** (`test_l3_b2_nonblocking_survivor_disclosed_not_refused`):

```
F                                                                        [100%]
=================================== FAILURES ===================================
____________ test_l3_b2_nonblocking_survivor_disclosed_not_refused _____________

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-4489/test_l3_b2_nonblocking_survivo0')

    def test_l3_b2_nonblocking_survivor_disclosed_not_refused(tmp_path):
        ...
        receipt, refusal = RC.certify(session_dir)
>       assert refusal is None
E       AssertionError: assert {'artifact': 'M1', 'bindingFailure': None, 'class': 'disposition-without-receipt', 'detail': 'finding has no disposition recorded'} is None

plugins/superheroes/lib/tests/test_layer3_certification_writer_1272.py:233: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_layer3_certification_writer_1272.py::test_l3_b2_nonblocking_survivor_disclosed_not_refused
1 failed in 0.17s
```

**Restore.** Restored the live `nonblocking_disclosures.append` / `continue` pair and removed the fallback `return _refusal(...)`.

**Green** (`test_l3_b2_nonblocking_survivor_disclosed_not_refused`):

```
.                                                                        [100%]
1 passed in 0.14s
```

## B3 — Critical may not take the non-blocking path

**Neutralization** (`round_certification.py`, `check_disposition_without_receipt`):

```python
            if False and severity_rank == _severity_rank("Critical"):
                return _refusal(
                    "disposition-without-receipt",
                    fid,
                    "Critical finding may not take the non-blocking path",
                )
            if severity_rank == _severity_rank("Important"):
```

(changed `<= _severity_rank("Important")` to `==` so neutralized Critical falls through to disclosure)

**Red** (`test_l3_b3_critical_may_not_take_the_nonblocking_path`):

```
F                                                                        [100%]
=================================== FAILURES ===================================
____________ test_l3_b3_critical_may_not_take_the_nonblocking_path _____________

    def test_l3_b3_critical_may_not_take_the_nonblocking_path(tmp_path):
        ...
        refusal = RC.check_disposition_without_receipt(ctx)
>       assert refusal is not None
E       assert None is not None

plugins/superheroes/lib/tests/test_layer3_certification_writer_1272.py:247: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_layer3_certification_writer_1272.py::test_l3_b3_critical_may_not_take_the_nonblocking_path
1 failed in 0.13s
```

**Restore.** Restored `if severity_rank == _severity_rank("Critical"): return _refusal(...)` and `if severity_rank <= _severity_rank("Important"):`.

**Green** (`test_l3_b3_critical_may_not_take_the_nonblocking_path`):

```
.                                                                        [100%]
1 passed in 0.12s
```
