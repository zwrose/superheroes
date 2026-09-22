# WO 1273-l3b-D bite-proofs — Astra registration probe

**Provenance:** cursor / composer-2.5 (implementer).

**Summary:** WO-D probe wiring and grader bite-proofs (BP-D1–D4). The fixture severity-scale defect (prompt omitted Critical) is fixed by WO-P (BP-P1).

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
def _settle_orphan_astra_claims(ledger_dir, current_wave, now=None, seat=None):
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

**raw green** (exit 0): `1 passed in 0.26s`

---

## BP-R2-1 — scale fail-closed

- **axis:** unreadable rubric scale must refuse before claim or dispatch

**neutralization** (`plugins/superheroes/lib/conformance_probe.py`, `_severity_scale`):
```python
    if False and levels != list(_EXPECTED_SEVERITY_LEVELS):  # bite-proof BP-R2-1 neutralization
        return None, "astra-probe-scale-unreadable"
```

**command:** `plugins/superheroes/lib/tests/test_conformance_probe.py::test_astra_probe_refuses_when_rubric_scale_unreadable`

**raw red** (exit 1):
```
FAILED plugins/superheroes/lib/tests/test_conformance_probe.py::test_astra_probe_refuses_when_rubric_scale_unreadable
>       assert out["reason"] == "astra-probe-scale-unreadable"
E       KeyError: 'reason'
1 failed in 0.27s
```

**restore** (`plugins/superheroes/lib/conformance_probe.py`, `_severity_scale`):
```python
    if levels != list(_EXPECTED_SEVERITY_LEVELS):
        return None, "astra-probe-scale-unreadable"
```

**raw green** (exit 0): `1 passed in 0.24s`

---

## BP-R2-2 — scale rendered from the rubric

- **axis:** severity scale lines must match the rubric table definitions at call time

**neutralization** (`plugins/superheroes/lib/conformance_probe.py`, `_severity_scale`):
```python
    return [
        "- `Critical` — corrupts data, leaks data across a trust boundary, or breaks production. NEVER for tests or style.",
        "- `Important` — Likely bug in normal use, OR a security/correctness issue warranting a fix before merge",
        "- `Minor` — bite-proof changed definition",  # bite-proof BP-R2-2 neutralization
        "- `Nit` — Style/naming/cleanup; take-it-or-leave-it",
    ], None
```
(replaces the `return lines, None` at the end of `_severity_scale`)

**command:** `plugins/superheroes/lib/tests/test_conformance_probe.py::test_astra_probe_scale_is_rendered_from_the_rubric`

**raw red** (exit 1):
```
FAILED plugins/superheroes/lib/tests/test_conformance_probe.py::test_astra_probe_scale_is_rendered_from_the_rubric
>           assert "`%s` — %s" % (level, rows[level]) in text
E           assert ('`%s` — %s' % ('Critical', 'Corrupts data, leaks data across a trust boundary, or breaks production. NEVER for tests or style.')) in 'Perform a one-shot security review...
1 failed in 0.33s
```

**restore** (`plugins/superheroes/lib/conformance_probe.py`, `_severity_scale`):
```python
    return lines, None
```

**raw green** (exit 0): `1 passed in 0.24s`

---

## BP-R2-3 — seat from the cell

- **axis:** the probe must resolve the registry cell with no model argument

**neutralization** (`plugins/superheroes/lib/conformance_probe.py`, `astra_probe`):
```python
    resolved = model_registry.resolve_dispatch(
        ASTRA_PROBE_ROLE, "codex", "gpt-6-astra", None)  # bite-proof BP-R2-3 neutralization
```

**command:** `plugins/superheroes/lib/tests/test_conformance_probe.py::test_astra_probe_seat_is_the_registry_cell`

**raw red** (exit 1):
```
FAILED plugins/superheroes/lib/tests/test_conformance_probe.py::test_astra_probe_seat_is_the_registry_cell
>       assert resolve_calls == [("registration-probe", "codex", None, None)]
E       AssertionError: assert [('registrati...astra', None)] == [('registrati..., None, None)]
1 failed in 0.33s
```

**restore** (`plugins/superheroes/lib/conformance_probe.py`, `astra_probe`):
```python
    resolved = model_registry.resolve_dispatch(
        ASTRA_PROBE_ROLE, "codex", None, None)
```

**raw green** (exit 0): `1 passed in 0.26s`

---

## BP-R2-4 — claim refresh

- **axis:** a non-terminal slice must refresh `lastSeenAt` on the wave claim

**neutralization** (`plugins/superheroes/lib/conformance_probe.py`, `astra_probe`):
```python
        if False and claim is not None:  # bite-proof BP-R2-4 neutralization
            refreshed = dict(claim)
            refreshed["lastSeenAt"] = _iso_from_utc(now)
            store_core.atomic_write(
                claim_path,
                json.dumps(refreshed, separators=(",", ":")) + "\n",
            )
```

**command:** `plugins/superheroes/lib/tests/test_conformance_probe.py::test_astra_probe_running_wave_claim_refreshed_is_not_settled`

**raw red** (exit 1):
```
FAILED plugins/superheroes/lib/tests/test_conformance_probe.py::test_astra_probe_running_wave_claim_refreshed_is_not_settled
>       assert claim.get("lastSeenAt") is not None
E       AssertionError: assert None is not None
1 failed in 0.30s
```

**restore** (`plugins/superheroes/lib/conformance_probe.py`, `astra_probe`):
```python
        if claim is not None:
            refreshed = dict(claim)
            refreshed["lastSeenAt"] = _iso_from_utc(now)
            store_core.atomic_write(
                claim_path,
                json.dumps(refreshed, separators=(",", ":")) + "\n",
            )
```

**raw green** (exit 0): `1 passed in 0.27s`

---

## BP-P1 — the prompt names the scale

- **axis:** the prompt must name every severity level the grader can pass on, including Critical

**neutralization** (`plugins/superheroes/lib/conformance_probe.py`, `ASTRA_PROBE_FIXTURE`):
```python
    "- `Important` — a likely bug in normal use, or a security or correctness issue warranting a fix before merge;\n"
```
(replaces the `Critical` scale line)

**command:** `plugins/superheroes/lib/tests/test_conformance_probe.py::test_astra_probe_fixture_states_the_full_severity_scale`

**raw red** (exit 1):
```
FAILED plugins/superheroes/lib/tests/test_conformance_probe.py::test_astra_probe_fixture_states_the_full_severity_scale
>       assert level in fixture
E       AssertionError: assert 'Critical' in 'Perform a one-shot security review of the following unified diff for a production admin console.\n\nReport each findi... "admin"}\n     if claims.get("role") != "admin":\n         raise Forbidden("not an admin")\n     return claims\n```\n'
1 failed in 0.28s
```

**restore** (`plugins/superheroes/lib/conformance_probe.py`, `ASTRA_PROBE_FIXTURE`):
```python
    "- `Critical` — corrupts data, leaks data across a trust boundary, or breaks production;\n"
```

**raw green** (exit 0): `1 passed in 0.29s`

---

## BP-R1-1 — seat unresolved refusal

- **axis:** unresolvable registry cell must refuse before claim or dispatch

**neutralization** (`plugins/superheroes/lib/conformance_probe.py`, `astra_probe`):
```python
    if False and not resolved.get("ok"):  # bite-proof BP-R1-1
```

**command:** `plugins/superheroes/lib/tests/test_conformance_probe.py::test_astra_probe_refuses_when_registry_cell_unresolvable`

**raw red** (exit 1):
```
FAILED plugins/superheroes/lib/tests/test_conformance_probe.py::test_astra_probe_refuses_when_registry_cell_unresolvable
E       KeyError: 'model_id'
1 failed in 0.27s
```

**restore** (`plugins/superheroes/lib/conformance_probe.py`, `astra_probe`):
```python
    if not resolved.get("ok"):
```

**raw green** (exit 0): `1 passed in 0.23s`

---

## BP-R1-2 — pending slice

- **axis:** a non-terminal dispatch is pending, not graded as a miss

**neutralization** (`plugins/superheroes/lib/conformance_probe.py`, `astra_probe`):
```python
    if not terminal.get("terminal"):
        out = _build_astra_output(wave, run_dir_real, terminal, [], attempts, seat)  # bite-proof BP-R1-2
        out["continue"] = True
        return out, 0
```

**command:** `plugins/superheroes/lib/tests/test_conformance_probe.py::test_astra_probe_running_slice_is_pending_not_a_miss`

**raw red** (exit 1):
```
FAILED plugins/superheroes/lib/tests/test_conformance_probe.py::test_astra_probe_running_slice_is_pending_not_a_miss
>       assert out["outcome"] == "pending"
E       AssertionError: assert 'miss' == 'pending'
1 failed in 0.29s
```

**restore** (`plugins/superheroes/lib/conformance_probe.py`, `astra_probe`): pending branch returns `outcome: "pending"` without calling `_build_astra_output`.

**raw green** (exit 0): `1 passed in 0.23s`

---

## BP-R1-3 — abandon bound

- **axis:** a recent other-wave claim must not be settled as abandoned

**neutralization** (`plugins/superheroes/lib/conformance_probe.py`, `_settle_orphan_astra_claims`): removed the `if not _claim_is_abandoned(claim, now): continue` guard.

**command:** `plugins/superheroes/lib/tests/test_conformance_probe.py::test_astra_probe_live_other_wave_claim_not_settled`

**raw red** (exit 1):
```
FAILED plugins/superheroes/lib/tests/test_conformance_probe.py::test_astra_probe_live_other_wave_claim_not_settled
>       assert not any(a.get("wave") == "wave-a" for a in attempts)
1 failed in 0.27s
```

**restore** (`plugins/superheroes/lib/conformance_probe.py`, `_settle_orphan_astra_claims`):
```python
        if not _claim_is_abandoned(claim, now):
            continue
```

**raw green** (exit 0): `1 passed in 0.24s`

---

## BP-R1-4 — project-store refusal

- **axis:** no project store entry must refuse before dispatch

**neutralization** (`plugins/superheroes/lib/conformance_probe.py`, `_conformance_record_dir`):
```python
    if entry is None:  # bite-proof BP-R1-4 neutralization
        try:
            return tempfile.mkdtemp(prefix="conformance-probe-"), None
        except OSError:
            return None, "conformance-record-dir-unusable"
```

**command:** `plugins/superheroes/lib/tests/test_conformance_probe.py::test_astra_probe_refuses_without_a_project_store_entry`

**raw red** (exit 1):
```
FAILED plugins/superheroes/lib/tests/test_conformance_probe.py::test_astra_probe_refuses_without_a_project_store_entry
>       assert out["reason"] == "conformance-record-dir-unresolved"
E       KeyError: 'reason'
1 failed in 0.31s
```

**restore** (`plugins/superheroes/lib/conformance_probe.py`, `_conformance_record_dir`):
```python
    if entry is None:
        return None, "conformance-record-dir-unresolved"
```

**raw green** (exit 0): `1 passed in 0.28s`

---

## BP-R1-5 — plant-line derivation test

- **axis:** `PLANT_LINES` must match diff-derived new-file line numbers

**neutralization** (`plugins/superheroes/lib/conformance_probe.py`):
```python
PLANT_LINES = (25, 26)  # bite-proof BP-R1-5
```

**command:** `plugins/superheroes/lib/tests/test_conformance_probe.py::test_astra_probe_fixture_plant_lines_are_second_hunk_plus_lines`

**raw red** (exit 1):
```
FAILED plugins/superheroes/lib/tests/test_conformance_probe.py::test_astra_probe_fixture_plant_lines_are_second_hunk_plus_lines
E       AssertionError: assert (24, 25) == (25, 26)
1 failed in 0.26s
```

**restore** (`plugins/superheroes/lib/conformance_probe.py`):
```python
PLANT_LINES = (24, 25)
```

**raw green** (exit 0): `1 passed in 0.23s`

---

## BP-R1-6 — rubric drift test

- **axis:** fixture severity scale names must match the rubric table

**neutralization** (`plugins/superheroes/lib/conformance_probe.py`, `ASTRA_PROBE_FIXTURE`):
```python
    "- `Small` — a real issue with small impact;\n"
```
(replaces the `Minor` scale line)

**command:** `plugins/superheroes/lib/tests/test_conformance_probe.py::test_astra_probe_fixture_scale_matches_rubric_table`

**raw red** (exit 1):
```
FAILED plugins/superheroes/lib/tests/test_conformance_probe.py::test_astra_probe_fixture_scale_matches_rubric_table
E       AssertionError: assert ['Critical', 'Important', 'Small', 'Nit'] == ['Critical', 'Important', 'Minor', 'Nit']
1 failed in 0.26s
```

**restore** (`plugins/superheroes/lib/conformance_probe.py`, `ASTRA_PROBE_FIXTURE`):
```python
    "- `Minor` — a real issue with small impact;\n"
```

**raw green** (exit 0): `1 passed in 0.23s`
