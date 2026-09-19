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
