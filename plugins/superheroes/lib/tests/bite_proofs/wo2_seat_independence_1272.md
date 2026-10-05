# Bite-proof record — #1272 WO-2c (seat independence, runner bypass closed)

Contract: `rubric/bite-proof.md`. Every proof below ran with the **detector unedited**; the
neutralization was applied as a targeted, reversible edit to the **production call site**, and
reverted by its exact inverse.

| # | Guarded element | Axis |
|---|---|---|
| G1 | `check_seat_independence` same-family branch | a runner-recorded same-family audit seat refuses |
| G2 | `check_seat_independence` fixer-contradiction branch | the runner record overrides the declaration |
| G3 | `round_driver.new_state` `independenceDegraded` seed | degraded only when no family-independent live vendor exists for the declared fixer |
| G4 | `_runner_recorded_vendor_status` (no `"runner"` bypass) | audit seat `source: "runner"` is not a vendor — refuses with detail naming `'runner'` |

---

## G1 — same-family audit seat refusal

**Neutralization** (`round_certification.py`):

```python
-        if fam == fixer_fam:
+        if False:
```

**Raw red** — `test_audit_seat_same_family_per_runner_record_refuses`:

```
F                                                                        [100%]
=================================== FAILURES ===================================
____________ test_audit_seat_same_family_per_runner_record_refuses _____________

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-249/test_audit_seat_same_family_pe0')

    def test_audit_seat_same_family_per_runner_record_refuses(tmp_path):
        session_dir = _independence_session(
            tmp_path,
            state={"config": {"fixerVendor": "claude", "baseGuard": RC.BASE_GUARD_CHECKED, "headSha": HEAD_SHA}},
            journal_lines=[
                _journal_row("code-reviewer", RC.PANEL_PHASE, source="codex"),
                _journal_row(FIXER_SEAT, FIXER_PHASE, source="claude"),
                _journal_row(AUDIT_SEAT, AUDIT_PHASE, source="claude"),
            ],
            envelopes=[
                _envelope_spec("code-reviewer", RC.PANEL_PHASE, source="codex"),
                _envelope_spec(FIXER_SEAT, FIXER_PHASE, source="claude"),
                _envelope_spec(AUDIT_SEAT, AUDIT_PHASE, source="claude"),
            ],
        )
        receipt, refusal = RC.certify(session_dir)
>       assert receipt is None
E       AssertionError: assert {'baseGuard': 'checked-stat-bound', 'certification': {'base': 'fetched', 'fullPanel': True, 'independence': 'independe...tificationShape': 'full-panel-confirmed', 'decisions': [{'detail': 'certified', 'kind': 'converged', 'round': 1}], ...} is None

plugins/superheroes/lib/tests/test_seat_independence_1272.py:206: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seat_independence_1272.py::test_audit_seat_same_family_per_runner_record_refuses
1 failed in 0.28s
```

**Restore:** changed `False` back to `fam == fixer_fam`.

**Restore receipt (quoted lines):**

```python
        if fam == fixer_fam:
```

**Raw green:**

```
.                                                                        [100%]
1 passed in 0.28s
```

---

## G2 — fixer vendor contradiction refusal

**Neutralization** (`round_certification.py`):

```python
-            if isinstance(source, str) and source and source != fixer:
+            if isinstance(source, str) and source and False:
```

**Raw red** — `test_fixer_seat_contradicting_declaration_refuses`:

```
F                                                                        [100%]
=================================== FAILURES ===================================
______________ test_fixer_seat_contradicting_declaration_refuses _______________

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-251/test_fixer_seat_contradicting_0')

    def test_fixer_seat_contradicting_declaration_refuses(tmp_path):
        session_dir = _independence_session(
            tmp_path,
            journal_lines=[
                _journal_row("code-reviewer", RC.PANEL_PHASE, source="codex"),
                _journal_row(FIXER_SEAT, FIXER_PHASE, source="claude"),
                _journal_row(AUDIT_SEAT, AUDIT_PHASE, source="codex"),
            ],
            envelopes=[
                _envelope_spec("code-reviewer", RC.PANEL_PHASE, source="codex"),
                _envelope_spec(FIXER_SEAT, FIXER_PHASE, source="claude"),
                _envelope_spec(AUDIT_SEAT, AUDIT_PHASE, source="codex"),
            ],
        )
        receipt, refusal = RC.certify(session_dir)
>       assert receipt is None
E       AssertionError: assert {'baseGuard': 'checked-stat-bound', 'certification': {'base': 'fetched', 'fullPanel': True, 'independence': 'independe...tificationShape': 'full-panel-confirmed', 'decisions': [{'detail': 'certified', 'kind': 'converged', 'round': 1}], ...} is None

plugins/superheroes/lib/tests/test_seat_independence_1272.py:185: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seat_independence_1272.py::test_fixer_seat_contradicting_declaration_refuses
1 failed in 0.30s
```

**Restore:** changed `False` back to `source != fixer`.

**Restore receipt (quoted lines):**

```python
            if isinstance(source, str) and source and source != fixer:
```

**Raw green:**

```
.                                                                        [100%]
1 passed in 0.28s
```

---

## G3 — `independenceDegraded` seed predicate

**Neutralization** (`round_driver.py`):

```python
-        "independenceDegraded": (
-            len(_live_vendors(cfg)) < 2
-            and not receipt_disclosures.independent_auditor_available(cfg)[0]
-        ),
+        "independenceDegraded": len(_live_vendors(cfg)) < 2,
```

**Raw red** — `test_driver_seed_single_vendor_cross_family_fixer_is_independent`:

```
F                                                                        [100%]
=================================== FAILURES ===================================
_______ test_driver_seed_single_vendor_cross_family_fixer_is_independent _______

    def test_driver_seed_single_vendor_cross_family_fixer_is_independent():
>       assert (
            RD.new_state(RD._default_config({"vendors": ["claude"], "fixerVendor": "cursor"}))[
                "independenceDegraded"
            ]
            is False
        )
E       assert True is False

plugins/superheroes/lib/tests/test_seat_independence_1272.py:296: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seat_independence_1272.py::test_driver_seed_single_vendor_cross_family_fixer_is_independent
1 failed in 0.31s
```

**Restore:** restored the `and not receipt_disclosures.independent_auditor_available(cfg)[0]` conjunct.

**Restore receipt (quoted lines):**

```python
        "independenceDegraded": (
            len(_live_vendors(cfg)) < 2
            and not receipt_disclosures.independent_auditor_available(cfg)[0]
        ),
```

**Raw green:**

```
.                                                                        [100%]
1 passed in 0.30s
```

---

## G4 — `"runner"` is not a vendor (bypass removed)

**Neutralization** (`round_certification.py`, top of `_runner_recorded_vendor_status`):

```python
     vendor = obs.get("source") if isinstance(obs, dict) else None
+    if vendor == "runner":
+        return "skip"
     if isinstance(vendor, str) and vendor:
```

**Raw red** — `test_audit_seat_source_runner_is_not_a_vendor_refuses`:

```
F                                                                        [100%]
=================================== FAILURES ===================================
____________ test_audit_seat_source_runner_is_not_a_vendor_refuses _____________

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-256/test_audit_seat_source_runner_0')

    def test_audit_seat_source_runner_is_not_a_vendor_refuses(tmp_path):
        session_dir = _independence_session(
            tmp_path,
            journal_lines=[
                _journal_row("code-reviewer", RC.PANEL_PHASE, source="codex"),
                _journal_row(FIXER_SEAT, FIXER_PHASE, source="cursor"),
                _journal_row(AUDIT_SEAT, AUDIT_PHASE, source="runner"),
            ],
            envelopes=[
                _envelope_spec("code-reviewer", RC.PANEL_PHASE, source="codex"),
                _envelope_spec(FIXER_SEAT, FIXER_PHASE, source="cursor"),
                _envelope_spec(AUDIT_SEAT, AUDIT_PHASE, source="runner"),
            ],
        )
        receipt, refusal = RC.certify(session_dir)
        assert receipt is None
        assert refusal["class"] == "unfetched-findings"
>       assert "runner" in refusal["detail"]
E       assert 'runner' in "audit seat audit-target-01 vendor 'skip' has no registry family"

plugins/superheroes/lib/tests/test_seat_independence_1272.py:227: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seat_independence_1272.py::test_audit_seat_source_runner_is_not_a_vendor_refuses
1 failed in 0.32s
```

**Restore:** removed the `if vendor == "runner": return "skip"` lines.

**Restore receipt (quoted lines):**

```python
    vendor = obs.get("source") if isinstance(obs, dict) else None
    if isinstance(vendor, str) and vendor:
        return vendor
```

**Raw green:**

```
.                                                                        [100%]
1 passed in 0.31s
```

---

## Review round 1 (WO-R1)

| # | Guarded element | Axis |
|---|---|---|
| R1 | `live_vendors` dedupe | duplicate vendor entries never count twice |
| R2 | `_auditor_vendor` leaf call | `_auditor_vendor` and the seed share one rule |
| R3 | echo-mismatch renderer key | the trusted vendor renders in degraded prose |
| R4 | `session_contract` phase tokens | tokens equal `round_phases` |
| R5 | `_independence_block` same-family branch (G1 rewrite) | same-family audit per record reads degraded |

### R1 — duplicate vendors deduped

**Neutralization** (`receipt_disclosures.py`): removed order-preserving dedupe from `live_vendors`.

**Raw red** — `test_duplicate_vendor_entries_do_not_read_independent`:

```
F                                                                        [100%]
=================================== FAILURES ===================================
____________ test_duplicate_vendor_entries_do_not_read_independent _____________

    def test_duplicate_vendor_entries_do_not_read_independent():
>       assert (
            RD.new_state(RD._default_config({"vendors": ["claude", "claude"]}))["independenceDegraded"]
            is True
        )
E       assert False is True

plugins/superheroes/lib/tests/test_seat_independence_1272.py:343: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seat_independence_1272.py::test_duplicate_vendor_entries_do_not_read_independent
1 failed in 0.15s
```

**Restore:** restored order-preserving dedupe loop in `live_vendors`.

**Restore receipt (quoted lines):**

```python
    seen = set()
    out = []
    for v in vendors:
        if isinstance(v, str) and v and v not in seen:
            seen.add(v)
            out.append(v)
    return out
```

**Raw green:**

```
.                                                                        [100%]
1 passed in 0.13s
```

### R2 — one rule for auditor seating and seed

**Neutralization** (`round_driver.py` `_auditor_vendor`): return `(fixer_vendor, "independent")` unconditionally.

**Raw red** — `test_auditor_vendor_and_seed_share_one_rule`:

```
F                                                                        [100%]
=================================== FAILURES ===================================
_________________ test_auditor_vendor_and_seed_share_one_rule __________________

    def test_auditor_vendor_and_seed_share_one_rule():
        ...
>           assert RD._auditor_vendor(full_cfg, fixer)[1] == expected
E           AssertionError: assert 'independent' == 'degraded'
E             
E             - degraded
E             + independent

plugins/superheroes/lib/tests/test_seat_independence_1272.py:367: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seat_independence_1272.py::test_auditor_vendor_and_seed_share_one_rule
1 failed in 0.15s
```

**Restore:** restored leaf call through `receipt_disclosures.independent_auditor`.

**Restore receipt (quoted lines):**

```python
    vendor, _fam = receipt_disclosures.independent_auditor(config, fixer_vendor)
    if vendor is not None:
        return vendor, "independent"
    live = _live_vendors(config)
    return (live[0] if live else fixer_vendor), "degraded"
```

**Raw green:**

```
.                                                                        [100%]
1 passed in 0.13s
```

### R3 — trusted vendor renders from `recorded` key

**Neutralization** (`receipt_disclosures.py` renderer): read only `row.get("manifest")`.

**Raw red** — `test_vendor_echo_mismatch_discloses_recorded_source`:

```
F                                                                        [100%]
=================================== FAILURES ===================================
_____________ test_vendor_echo_mismatch_discloses_recorded_source ______________

>       assert "trusted='codex'" in degraded_text
E       assert "trusted='codex'" in "independence: a single live vendor — the fix's auditor is the fixer's vendor; independence degraded and named in the certification shape\nadapter-provenance (round 1, dispatch-audits): vendor echo mismatch on seat(s): src/f00.py::unchecked index@L2 echo='claude' trusted=None"

plugins/superheroes/lib/tests/test_seat_provenance_1272.py:338: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seat_provenance_1272.py::test_vendor_echo_mismatch_discloses_recorded_source
1 failed in 3.50s
```

**Restore:** restored `row.get("recorded", row.get("manifest"))`.

**Restore receipt (quoted lines):**

```python
                parts = ["%s echo=%r trusted=%r" % (row.get("seat"), row.get("echo"),
                                                     row.get("recorded", row.get("manifest")))
```

**Raw green:**

```
.                                                                        [100%]
1 passed in 3.40s
```

### R4 — phase tokens drift-pinned

**Neutralization** (`session_contract.py`): `FIXER_PHASE = "dispatch-fixers"`.

**Raw red** — `test_phase_tokens_match_round_phases`:

```
F                                                                        [100%]
=================================== FAILURES ===================================
_____________________ test_phase_tokens_match_round_phases _____________________

>       assert session_contract.FIXER_PHASE == round_phases.P_FIXER
E       AssertionError: assert 'dispatch-fixers' == 'dispatch-fixer'
E         
E         - dispatch-fixer
E         + dispatch-fixers
E         ?               +

plugins/superheroes/lib/tests/test_round_certification_drift.py:86: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_round_certification_drift.py::test_phase_tokens_match_round_phases
1 failed in 0.14s
```

**Restore:** `FIXER_PHASE = "dispatch-fixer"`.

**Restore receipt (quoted lines):**

```python
FIXER_PHASE = "dispatch-fixer"
```

**Raw green:**

```
.                                                                        [100%]
1 passed in 0.13s
```

### R5 — same-family audit reads degraded (G1 rewrite)

**Neutralization** (`round_certification.py` `_independence_block`): same-family branch reports `independent` / `runner-recorded-audit-seats`.

**Raw red** — `test_audit_seat_same_family_per_runner_record_reads_degraded`:

```
F                                                                        [100%]
=================================== FAILURES ===================================
_________ test_audit_seat_same_family_per_runner_record_reads_degraded _________

>       assert receipt["independence"] == {
            "status": "degraded",
            "basis": "auditor-same-family",
            ...
        }
E       AssertionError: assert {'auditSeats'...thropic', ...} == {'auditSeats'...thropic', ...}
E         Differing items:
E         {'basis': 'runner-recorded-audit-seats'} != {'basis': 'auditor-same-family'}
E         {'status': 'independent'} != {'status': 'degraded'}

plugins/superheroes/lib/tests/test_seat_independence_1272.py:208: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seat_independence_1272.py::test_audit_seat_same_family_per_runner_record_reads_degraded
1 failed in 0.16s
```

**Restore:** restored `status = "degraded"` / `basis = "auditor-same-family"` for same-family seats.

**Restore receipt (quoted lines):**

```python
    if same_family_seats:
        status = "degraded"
        basis = "auditor-same-family"
```

**Raw green:**

```
.                                                                        [100%]
1 passed in 0.16s
```
