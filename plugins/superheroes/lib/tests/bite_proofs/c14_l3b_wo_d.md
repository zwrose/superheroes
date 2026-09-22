# WO 1273-l3b-D bite-proofs — Astra registration probe

**Provenance:** cursor / composer-2.5 (implementer).

## Guarded elements

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| BP-D1 | `_write_astra_claim` / claim `runDir` gate | second invocation with different run dir must refuse | `test_astra_probe_refuses_second_run_dir_same_wave` |
| BP-D2 | `_match_astra_finding` line check | string `line` must not match | `test_astra_probe_miss_string_line_not_matched` |
| BP-D3 | `_match_astra_finding` severity check | Important at plant location must miss | `test_astra_probe_miss_wrong_severity` |
| BP-D4 | `_settle_orphan_astra_claims` | orphan claim recorded as incomplete miss | `test_astra_probe_orphan_claim_recorded_as_miss` |

---

## BP-D1 — O_EXCL claim run-dir gate

- **axis:** different `runDir` for the same wave must refuse before dispatch

**neutralization** (`plugins/superheroes/lib/conformance_probe.py`, `astra_probe`):
```python
        if False and claimed_real != run_dir_real:  # bite-proof BP-D1 neutralization
            return _astra_probe_refusal(wave, claim)
```

**command:** `plugins/superheroes/lib/tests/test_conformance_probe.py::test_astra_probe_refuses_second_run_dir_same_wave`

**raw red** (exit 1):
```
FAILED plugins/superheroes/lib/tests/test_conformance_probe.py::test_astra_probe_refuses_second_run_dir_same_wave
>       assert code == 1
E       assert 0 == 1
1 failed in 1.28s
```

**restore** (`plugins/superheroes/lib/conformance_probe.py`, `astra_probe`):
```python
        if claimed_real != run_dir_real:
            return _astra_probe_refusal(wave, claim)
```

**raw green** (exit 0): `1 passed in 0.93s`

---

## BP-D2 — location grade (line)

- **axis:** non-int `line` must not pass location grading

**neutralization** (`plugins/superheroes/lib/conformance_probe.py`, `_match_astra_finding`):
```python
    line_ok = True  # bite-proof BP-D2 neutralization
```

**command:** `plugins/superheroes/lib/tests/test_conformance_probe.py::test_astra_probe_miss_string_line_not_matched`

**raw red** (exit 1):
```
FAILED plugins/superheroes/lib/tests/test_conformance_probe.py::test_astra_probe_miss_string_line_not_matched
>       assert code == 1
E       assert 0 == 1
1 failed in 1.30s
```

**restore** (`plugins/superheroes/lib/conformance_probe.py`, `_match_astra_finding`):
```python
    line_ok = isinstance(line, int) and line in PLANT_LINES
```

**raw green** (exit 0): `1 passed in 0.97s`

---

## BP-D3 — severity grade

- **axis:** right location at Important severity must miss

**neutralization** (`plugins/superheroes/lib/conformance_probe.py`, `_match_astra_finding`):
```python
    sev_ok = True  # bite-proof BP-D3 neutralization
```

**command:** `plugins/superheroes/lib/tests/test_conformance_probe.py::test_astra_probe_miss_wrong_severity`

**raw red** (exit 1):
```
FAILED plugins/superheroes/lib/tests/test_conformance_probe.py::test_astra_probe_miss_wrong_severity
>       assert code == 1
E       assert 0 == 1
1 failed in 0.93s
```

**restore** (`plugins/superheroes/lib/conformance_probe.py`, `_match_astra_finding`):
```python
    sev_ok = isinstance(severity, str) and severity.lower() == PLANT_SEVERITY.lower()
```

**raw green** (exit 0): `1 passed in 0.98s`

---

## BP-D4 — orphan-claim record

- **axis:** claim without attempt must be settled as incomplete on a new wave

**neutralization** (`plugins/superheroes/lib/conformance_probe.py`, `_settle_orphan_astra_claims`):
```python
def _settle_orphan_astra_claims(ledger_dir, current_wave):
    attempts = _read_astra_attempts(ledger_dir)
    return attempts  # bite-proof BP-D4 neutralization
```

**command:** `plugins/superheroes/lib/tests/test_conformance_probe.py::test_astra_probe_orphan_claim_recorded_as_miss`

**raw red** (exit 1):
```
FAILED plugins/superheroes/lib/tests/test_conformance_probe.py::test_astra_probe_orphan_claim_recorded_as_miss
>       orphan = next(a for a in attempts if a.get("wave") == old_wave)
E       StopIteration
1 failed in 0.97s
```

**restore** (`plugins/superheroes/lib/conformance_probe.py`, `_settle_orphan_astra_claims`): removed early `return attempts` neutralization; full orphan-scan body restored.

**raw green** (exit 0): `1 passed in 0.96s`
