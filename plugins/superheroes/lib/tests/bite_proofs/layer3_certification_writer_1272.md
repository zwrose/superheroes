# Bite-proof record — layer 3B certification writer (#1272)

Re-taken at head cfd2dc04 (plus this order's test-only changes).

| Element | Guarded code | Detector |
| --- | --- | --- |
| B1 | `round_certification._hand_landed_evidence_qualifies` write-stamp phase gate | `test_l3_b1_write_stamp_out_of_phase_refused` |
| B2 | `round_certification.check_disposition_without_receipt` non-blocking disclosure branch | `test_l3_b2_nonblocking_survivor_disclosed_not_refused` |
| B3 | `round_certification.check_disposition_without_receipt` Critical non-blocking prohibition | `test_l3_b3_critical_may_not_take_the_nonblocking_path` |
| B4 | `round_certification.check_disposition_without_receipt` pre-v5 undispositioned Minor refusal | `test_l3_b4_pre_v5_session_refuses_undispositioned_minor` |
| B5 | `round_certification._receipt_disclosures` schema-gated survivingNonBlocking key | `test_l3_b5_pre_v5_receipt_carries_no_surviving_nonblocking` |

## B1 — write-run stamp admissible only on fixer phase

**Guarded code:** `round_certification._hand_landed_evidence_qualifies`

**Neutralization:**

```python
if False and not session_contract.execution_only_admissible_for_phase(phase):
            return False, "execution-evidence-write-stamp-out-of-phase"
```

**Detector:** `test_l3_b1_write_stamp_out_of_phase_refused`

**Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_________________ test_l3_b1_write_stamp_out_of_phase_refused __________________

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-5171/test_l3_b1_write_stamp_out_of_0')

    def test_l3_b1_write_stamp_out_of_phase_refused(tmp_path):
        for phase in (RC.PANEL_PHASE, RC.AUDITS_PHASE):
            ctx, _ = RC._load_context(_write_stamp_session(tmp_path / phase, phase))
            refusal = RC.check_unrun_review(ctx)
>           assert refusal is not None
E           assert None is not None

plugins/superheroes/lib/tests/test_layer3_certification_writer_1272.py:126: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_layer3_certification_writer_1272.py::test_l3_b1_write_stamp_out_of_phase_refused
1 failed in 0.09s
```

**Restore (quoted restored lines):**

```python
if not session_contract.execution_only_admissible_for_phase(phase):
            return False, "execution-evidence-write-stamp-out-of-phase"
```

**Green:**

```
.                                                                        [100%]
1 passed in 0.08s
```

## B2 — non-blocking survivor disclosed, not refused

**Guarded code:** `round_certification.check_disposition_without_receipt`

**Neutralization:**

```python
if False:
                row = {
                    "id": finding.get("id"),
                    "title": finding.get("title"),
                    "severity": severity,
                }
                finding_key = _finding_identity_key(finding)
                if finding_key:
                    row[session_contract.FINDING_KEY_FIELD] = finding_key
                file_loc = finding.get("file")
                if file_loc is not None:
                    row["file"] = file_loc
                line_loc = finding.get("line")
                if line_loc is not None:
                    row["line"] = line_loc
                nonblocking_disclosures.append(row)
                continue
            return _refusal(
                "disposition-without-receipt",
                fid,
                "finding has no disposition recorded",
            )
```

**Detector:** `test_l3_b2_nonblocking_survivor_disclosed_not_refused`

**Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
____________ test_l3_b2_nonblocking_survivor_disclosed_not_refused _____________

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-5173/test_l3_b2_nonblocking_survivo0')

    def test_l3_b2_nonblocking_survivor_disclosed_not_refused(tmp_path):
        state = {
            "findings": [
                {
                    "id": "M1",
                    "file": "a.py",
                    "line": 1,
                    "title": "style nit",
                    "severity": "Minor",
                }
            ],
        }
        session_dir = _certifiable_session(tmp_path, state)
        receipt, refusal = RC.certify(session_dir)
>       assert refusal is None
E       AssertionError: assert {'artifact': 'M1', 'bindingFailure': None, 'class': 'disposition-without-receipt', 'detail': 'finding has no disposition recorded'} is None

plugins/superheroes/lib/tests/test_layer3_certification_writer_1272.py:233: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_layer3_certification_writer_1272.py::test_l3_b2_nonblocking_survivor_disclosed_not_refused
1 failed in 0.09s
```

**Restore (quoted restored lines):**

```python
if not _supports_nonblocking_disclosure(state):
                return _refusal(
                    "disposition-without-receipt",
                    fid,
                    "finding has no disposition recorded",
                )
            row = {
                "id": finding.get("id"),
                "title": finding.get("title"),
                "severity": severity,
            }
            finding_key = _finding_identity_key(finding)
            if finding_key:
                row[session_contract.FINDING_KEY_FIELD] = finding_key
            file_loc = finding.get("file")
            if file_loc is not None:
                row["file"] = file_loc
            line_loc = finding.get("line")
            if line_loc is not None:
                row["line"] = line_loc
            nonblocking_disclosures.append(row)
            continue
```

**Green:**

```
.                                                                        [100%]
1 passed in 0.08s
```

## B3 — Critical may not take the non-blocking path

**Guarded code:** `round_certification.check_disposition_without_receipt`

**Neutralization:**

```python
if False and severity_rank == _severity_rank("Critical"):
                return _refusal(
                    "disposition-without-receipt",
                    fid,
                    "Critical finding may not take the non-blocking path",
                )
            if severity_rank == _severity_rank("Important"):
```

**Detector:** `test_l3_b3_critical_may_not_take_the_nonblocking_path`

**Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
____________ test_l3_b3_critical_may_not_take_the_nonblocking_path _____________

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-5175/test_l3_b3_critical_may_not_ta0')

    def test_l3_b3_critical_may_not_take_the_nonblocking_path(tmp_path):
        ctx = _ctx_for_state(
            {"findings": [{"id": "C1", "severity": "Critical", "title": "blocker"}]},
            tmp_path,
        )
        refusal = RC.check_disposition_without_receipt(ctx)
>       assert refusal is not None
E       assert None is not None

plugins/superheroes/lib/tests/test_layer3_certification_writer_1272.py:309: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_layer3_certification_writer_1272.py::test_l3_b3_critical_may_not_take_the_nonblocking_path
1 failed in 0.09s
```

**Restore (quoted restored lines):**

```python
if severity_rank == _severity_rank("Critical"):
                return _refusal(
                    "disposition-without-receipt",
                    fid,
                    "Critical finding may not take the non-blocking path",
                )
            if severity_rank <= _severity_rank("Important"):
```

**Green:**

```
.                                                                        [100%]
1 passed in 0.08s
```

## B4 — pre-v5 session refuses undispositioned Minor

**Guarded code:** `round_certification.check_disposition_without_receipt`

**Neutralization:**

```python
if False and not _supports_nonblocking_disclosure(state):
                return _refusal(
                    "disposition-without-receipt",
                    fid,
                    "finding has no disposition recorded",
                )
```

**Detector:** `test_l3_b4_pre_v5_session_refuses_undispositioned_minor`

**Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
___________ test_l3_b4_pre_v5_session_refuses_undispositioned_minor ____________

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-5177/test_l3_b4_pre_v5_session_refu0')

    def test_l3_b4_pre_v5_session_refuses_undispositioned_minor(tmp_path):
        state = {
            "schemaVersion": 4,
            "findings": [
                {
                    "id": "M1",
                    "file": "a.py",
                    "line": 1,
                    "title": "style nit",
                    "severity": "Minor",
                }
            ],
        }
        ctx = _ctx_for_state(state, tmp_path)
        refusal = RC.check_disposition_without_receipt(ctx)
>       assert refusal is not None
E       assert None is not None

plugins/superheroes/lib/tests/test_layer3_certification_writer_1272.py:263: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_layer3_certification_writer_1272.py::test_l3_b4_pre_v5_session_refuses_undispositioned_minor
1 failed in 0.09s
```

**Restore (quoted restored lines):**

```python
if not _supports_nonblocking_disclosure(state):
                return _refusal(
                    "disposition-without-receipt",
                    fid,
                    "finding has no disposition recorded",
                )
```

**Green:**

```
.                                                                        [100%]
1 passed in 0.08s
```

## B5 — pre-v5 receipt carries no survivingNonBlocking key

**Guarded code:** `round_certification._receipt_disclosures`

**Neutralization:**

```python
if False and _supports_nonblocking_disclosure(state):
        disclosures["survivingNonBlocking"] = list(ctx.get("nonblocking_disclosures") or [])
```

**Detector:** `test_l3_b5_pre_v5_receipt_carries_no_surviving_nonblocking`

**Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
__________ test_l3_b5_pre_v5_receipt_carries_no_surviving_nonblocking __________

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-5179/test_l3_b5_pre_v5_receipt_carr0')

    def test_l3_b5_pre_v5_receipt_carries_no_surviving_nonblocking(tmp_path):
        state_v4 = {
            "schemaVersion": 4,
            "findings": [
                {
                    "id": "M1",
                    "file": "a.py",
                    "line": 1,
                    "title": "style nit",
                    "severity": "Minor",
                    "disposition": "refuted",
                    "refutedReason": "intentional",
                }
            ],
        }
        ctx_v4 = _ctx_for_state(state_v4, tmp_path / "v4")
        disclosures_v4 = RC._receipt_disclosures(ctx_v4, ctx_v4["state"])
        assert "survivingNonBlocking" not in disclosures_v4
    
        state_v5 = {
            "schemaVersion": 5,
            "findings": [
                {
                    "id": "M1",
                    "file": "a.py",
                    "line": 1,
                    "title": "style nit",
                    "severity": "Minor",
                }
            ],
        }
        ctx_v5 = _ctx_for_state(state_v5, tmp_path / "v5")
        disclosures_v5 = RC._receipt_disclosures(ctx_v5, ctx_v5["state"])
>       assert "survivingNonBlocking" in disclosures_v5
E       AssertionError: assert 'survivingNonBlocking' in {'importantOutOfScope': []}

plugins/superheroes/lib/tests/test_layer3_certification_writer_1272.py:300: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_layer3_certification_writer_1272.py::test_l3_b5_pre_v5_receipt_carries_no_surviving_nonblocking
1 failed in 0.09s
```

**Restore (quoted restored lines):**

```python
if _supports_nonblocking_disclosure(state):
        disclosures["survivingNonBlocking"] = list(ctx.get("nonblocking_disclosures") or [])
```

**Green:**

```
.                                                                        [100%]
1 passed in 0.09s
```

## Unreachable-guard disclosure — `_build_receipt` findings filter

**Guarded code:** `round_certification._build_receipt` — `if (_supports_nonblocking_disclosure(state) and rank > Important): continue`.

**Disclosure shape:** Unreachable through this entry point.

**Reason:** For a pre-v5 session with an undispositioned Minor, `check_disposition_without_receipt` (B4) refuses before `_build_receipt` runs, so the filter is unreachable on that path.
