# WO 1273-l3b-D bite-proofs — Astra registration probe

**Provenance:** cursor / composer-2.5 (implementer).

**Summary:** WO-D probe wiring and grader bite-proofs (BP-D1–D4). The fixture severity-scale defect (prompt omitted Critical) is fixed by WO-P (BP-P1). R4 (2026-09-22): every entry was checked at `8aaa809c`; entries whose code or selector no longer exists are marked superseded, the rest were re-run or rewritten at that head.

## Guarded elements

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| BP-D1 | `_write_astra_claim` / claim `runDir` gate | second invocation with different run dir must refuse | `test_astra_probe_refuses_second_run_dir_same_wave` |
| BP-D2 | `_match_astra_finding` line check | string `line` must not match | `test_astra_probe_miss_string_line_not_matched` |
| BP-D3 | `_match_astra_finding` severity check | Important at plant location must miss | `test_astra_probe_miss_wrong_severity` |
| BP-D4 | `_settle_orphan_astra_claims` | orphan claim recorded as incomplete miss | `test_astra_probe_orphan_claim_recorded_as_miss` |

---

## BP-D1 — O_EXCL claim run-dir gate

> **Re-run at `8aaa809c` (2026-09-22).**

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
1 failed in 1.64s
```

**restore** (`plugins/superheroes/lib/conformance_probe.py`, `astra_probe`):
```python
        if claimed_real != run_dir_real:
            return _astra_probe_refusal(wave, claim)
```

**raw green** (exit 0): `1 passed in 1.26s`

---

## BP-D2 — location grade (line)

> **Re-run at `8aaa809c` (2026-09-22).**

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
1 failed in 1.48s
```

**restore** (`plugins/superheroes/lib/conformance_probe.py`, `_match_astra_finding`):
```python
    line_ok = isinstance(line, int) and line in PLANT_LINES
```

**raw green** (exit 0): `1 passed in 1.21s`

---

## BP-D3 — severity grade

> **Re-run at `8aaa809c` (2026-09-22).**

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
1 failed in 1.38s
```

**restore** (`plugins/superheroes/lib/conformance_probe.py`, `_match_astra_finding`):
```python
    sev_ok = isinstance(severity, str) and severity.lower() == PLANT_SEVERITY.lower()
```

**raw green** (exit 0): `1 passed in 1.18s`

---

## BP-D4 — orphan-claim record

> **Rewritten against `8aaa809c` (2026-09-22).** `_read_astra_attempts` now returns a pair and the orphan-scan body follows the error check.

- **axis:** claim without attempt must be settled as incomplete on a new wave

**neutralization** (`plugins/superheroes/lib/conformance_probe.py`, `_settle_orphan_astra_claims`):
```python
    attempts, err = _read_astra_attempts(ledger_dir)
    if err:
        return None, err
    return attempts, None  # bite-proof BP-D4 neutralization
```

**command:** `plugins/superheroes/lib/tests/test_conformance_probe.py::test_astra_probe_orphan_claim_recorded_as_miss`

**raw red** (exit 1):
```
FAILED plugins/superheroes/lib/tests/test_conformance_probe.py::test_astra_probe_orphan_claim_recorded_as_miss
>       orphan = next(a for a in attempts if a.get("wave") == old_wave)
E       StopIteration
1 failed in 0.93s
```

**restore** (`plugins/superheroes/lib/conformance_probe.py`, `_settle_orphan_astra_claims`):
```python
    return attempts, None  # bite-proof BP-D4 neutralization
```
(deleted line — orphan-scan body follows the error check.)

**raw green** (exit 0): `1 passed in 0.79s`

---

## BP-R2-1 — scale fail-closed

> **Superseded at `8aaa809c` (2026-09-22) by BP-R3-1.** `_EXPECTED_SEVERITY_LEVELS` and selector `test_astra_probe_refuses_when_rubric_scale_unreadable` no longer exist at this head. The body below is kept as history; it does not reproduce at this head.

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

> **Re-run at `8aaa809c` (2026-09-22).**

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
>           assert "`%s` — %s" % (level, definition) in text
E           assert ('`%s` — %s' % ('Critical', 'Corrupts data, leaks data across a trust boundary, or breaks production. NEVER for tests or style.')) in 'Perform a one-shot security review of the following unified diff for a production admin console.\n\nReport each findi... "admin"}\n     if claims.get("role") != "admin":\n         raise Forbidden("not an admin")\n     return claims\n```\n'
1 failed in 1.78s
```

**restore** (`plugins/superheroes/lib/conformance_probe.py`, `_severity_scale`):
```python
    return lines, None
```

**raw green** (exit 0): `1 passed in 1.60s`

---

## BP-R2-3 — seat from the cell

> **Re-run at `8aaa809c` (2026-09-22).**

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
E         
1 failed in 1.42s
```

**restore** (`plugins/superheroes/lib/conformance_probe.py`, `astra_probe`):
```python
    resolved = model_registry.resolve_dispatch(
        ASTRA_PROBE_ROLE, "codex", None, None)
```

**raw green** (exit 0): `1 passed in 1.28s`

---

## BP-R2-4 — claim refresh

> **Re-run at `8aaa809c` (2026-09-22).**

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
E        +  where None = <built-in method get of dict object at 0x10723bb00>('lastSeenAt')
1 failed in 1.25s
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

**raw green** (exit 0): `1 passed in 1.01s`

---

## BP-P1 — the prompt names the scale

> **Rewritten against `8aaa809c` (2026-09-22).** The prompt is built by `_astra_probe_prompt` from `_severity_scale`; `ASTRA_PROBE_FIXTURE` no longer exists.

- **axis:** the prompt must name every severity level the grader can pass on, including Critical

**neutralization** (`plugins/superheroes/lib/conformance_probe.py`, `_astra_probe_prompt`):
```python
        + "\n".join(line for line in scale_lines if not line.startswith("- `Critical`")) + "\n"  # bite-proof BP-P1 neutralization
```
(replaces the `scale_lines` join in the prompt text.)

**command:** `plugins/superheroes/lib/tests/test_conformance_probe.py::test_astra_probe_fixture_states_the_full_severity_scale`

**raw red** (exit 1):
```
FAILED plugins/superheroes/lib/tests/test_conformance_probe.py::test_astra_probe_fixture_states_the_full_severity_scale
>           assert "`%s` — %s" % (level, definition) in text
E           assert ('`%s` — %s' % ('Critical', 'Corrupts data, leaks data across a trust boundary, or breaks production. NEVER for tests or style.')) in 'Perform a one-shot security review of the following unified diff for a production admin console.\n\nReport each findi... "admin"}\n     if claims.get("role") != "admin":\n         raise Forbidden("not an admin")\n     return claims\n```\n'
1 failed in 0.85s
```

**restore** (`plugins/superheroes/lib/conformance_probe.py`, `_astra_probe_prompt`):
```python
        + "\n".join(scale_lines) + "\n"
```

**raw green** (exit 0): `1 passed in 0.74s`

---

## BP-R1-1 — seat unresolved refusal

> **Re-run at `8aaa809c` (2026-09-22).**

- **axis:** unresolvable registry cell must refuse before claim or dispatch

**neutralization** (`plugins/superheroes/lib/conformance_probe.py`, `astra_probe`):
```python
    if False and not resolved.get("ok"):  # bite-proof BP-R1-1
```

**command:** `plugins/superheroes/lib/tests/test_conformance_probe.py::test_astra_probe_refuses_when_registry_cell_unresolvable`

**raw red** (exit 1):
```
FAILED plugins/superheroes/lib/tests/test_conformance_probe.py::test_astra_probe_refuses_when_registry_cell_unresolvable
>       out, code = CP.astra_probe(repo, "wave-seat", run_dir, dispatch=dispatch)
>           "model": resolved["model_id"],
E       KeyError: 'model_id'
1 failed in 1.23s
```

**restore** (`plugins/superheroes/lib/conformance_probe.py`, `astra_probe`):
```python
    if not resolved.get("ok"):
```

**raw green** (exit 0): `1 passed in 1.01s`

---

## BP-R1-2 — pending slice

> **Re-run at `8aaa809c` (2026-09-22).**

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
E         
1 failed in 1.06s
```

**restore** (`plugins/superheroes/lib/conformance_probe.py`, `astra_probe`): pending branch returns `outcome: "pending"` without calling `_build_astra_output`.

**raw green** (exit 0): `1 passed in 0.77s`

---

## BP-R1-3 — abandon bound

> **Re-run at `8aaa809c` (2026-09-22).**

- **axis:** a recent other-wave claim must not be settled as abandoned

**neutralization** (`plugins/superheroes/lib/conformance_probe.py`, `_settle_orphan_astra_claims`): removed the `if not _claim_is_abandoned(claim, now): continue` guard.

**command:** `plugins/superheroes/lib/tests/test_conformance_probe.py::test_astra_probe_live_other_wave_claim_not_settled`

**raw red** (exit 1):
```
FAILED plugins/superheroes/lib/tests/test_conformance_probe.py::test_astra_probe_live_other_wave_claim_not_settled
>       assert not any(a.get("wave") == "wave-a" for a in attempts)
E       assert not True
E        +  where True = any(<generator object test_astra_probe_live_other_wave_claim_not_settled.<locals>.<genexpr> at 0x1040a6970>)
1 failed in 1.06s
```

**restore** (`plugins/superheroes/lib/conformance_probe.py`, `_settle_orphan_astra_claims`):
```python
        if not _claim_is_abandoned(claim, now):
            continue
```

**raw green** (exit 0): `1 passed in 0.92s`

---

## BP-R1-4 — project-store refusal

> **Superseded at `2ad99e4e` (2026-09-23)** by BP-E1 and BP-E2 in `c14_l3b2_wo_e.md`: order E replaced the legacy lookup this entry neutralizes; the project-store refusal is now the resolver's `os.path.isdir(project_store)` guard (BP-E2) and its store lookup (BP-E1). The test named below still runs and passes at the head.

> **Re-run at `8aaa809c` (2026-09-22).**

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
1 failed in 1.00s
```

**restore** (`plugins/superheroes/lib/conformance_probe.py`, `_conformance_record_dir`):
```python
    if entry is None:
        return None, "conformance-record-dir-unresolved"
```

**raw green** (exit 0): `1 passed in 1.08s`

---

## BP-R1-5 — plant-line derivation test

> **Re-run at `8aaa809c` (2026-09-22).**

- **axis:** `PLANT_LINES` must match diff-derived new-file line numbers

**neutralization** (`plugins/superheroes/lib/conformance_probe.py`):
```python
PLANT_LINES = (25, 26)  # bite-proof BP-R1-5
```

**command:** `plugins/superheroes/lib/tests/test_conformance_probe.py::test_astra_probe_fixture_plant_lines_are_second_hunk_plus_lines`

**raw red** (exit 1):
```
FAILED plugins/superheroes/lib/tests/test_conformance_probe.py::test_astra_probe_fixture_plant_lines_are_second_hunk_plus_lines
>       assert tuple(nums) == CP.PLANT_LINES == (24, 25)
E       assert (24, 25) == (25, 26)
E         
1 failed in 1.15s
```

**restore** (`plugins/superheroes/lib/conformance_probe.py`):
```python
PLANT_LINES = (24, 25)
```

**raw green** (exit 0): `1 passed in 0.86s`

---

## BP-R1-6 — rubric drift test

> **Superseded at `8aaa809c` (2026-09-22) by BP-R2-2, BP-R3-2, and BP-R3-3.** `ASTRA_PROBE_FIXTURE` and selector `test_astra_probe_fixture_scale_matches_rubric_table` no longer exist at this head. The body below is kept as history; it does not reproduce at this head.

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

---

## BP-R3-1 — PLANT_SEVERITY membership check

- **axis:** rubric tier table without PLANT_SEVERITY must refuse before claim or dispatch (also covers the empty-table case via `PLANT_SEVERITY not in levels`)

**neutralization** (`plugins/superheroes/lib/conformance_probe.py`, `_severity_scale`):
```python
    # deleted:
    if PLANT_SEVERITY not in levels:
        return None, "astra-probe-scale-unreadable"
```

**command:** `plugins/superheroes/lib/tests/test_conformance_probe.py::test_astra_probe_refuses_when_rubric_scale_unreadable_table_lacks_the_plant_level`

**raw red** (exit 1):
```
FAILED plugins/superheroes/lib/tests/test_conformance_probe.py::test_astra_probe_refuses_when_rubric_scale_unreadable_table_lacks_the_plant_level
>       assert out["reason"] == "astra-probe-scale-unreadable"
E       KeyError: 'reason'
1 failed in 0.34s
```

**restore** (`plugins/superheroes/lib/conformance_probe.py`, `_severity_scale`):
```python
    if PLANT_SEVERITY not in levels:
        return None, "astra-probe-scale-unreadable"
```

**raw green** (exit 0): `1 passed in 0.78s`

---

## BP-R3-2 — heading stop

- **axis:** parsing must stop at the next markdown heading after the tier table

**neutralization** (`plugins/superheroes/lib/conformance_probe.py`, `_severity_scale`):
```python
    # deleted:
        if row.startswith("#"):
            break
```

**command:** `plugins/superheroes/lib/tests/test_conformance_probe.py::test_astra_probe_refuses_when_rubric_scale_unreadable_table_empty`

**raw red** (exit 1):
```
FAILED plugins/superheroes/lib/tests/test_conformance_probe.py::test_astra_probe_refuses_when_rubric_scale_unreadable_table_empty
>       assert out["reason"] == "astra-probe-scale-unreadable"
E       KeyError: 'reason'
1 failed in 0.61s
```

**restore** (`plugins/superheroes/lib/conformance_probe.py`, `_severity_scale`):
```python
        if row.startswith("#"):
            break
```

**raw green** (exit 0): `1 passed in 0.61s`

---

## BP-R3-3 — prose stop

- **axis:** parsing must stop at prose after the tier table, before a later unheaded table

**neutralization** (`plugins/superheroes/lib/conformance_probe.py`, `_severity_scale`):
```python
    # deleted:
        elif saw_table_row and row.strip() and not row.startswith("#"):
            break
```

**command:** `plugins/superheroes/lib/tests/test_conformance_probe.py::test_astra_probe_scale_stops_at_the_end_of_the_tier_table`

**raw red** (exit 1):
```
FAILED plugins/superheroes/lib/tests/test_conformance_probe.py::test_astra_probe_scale_stops_at_the_end_of_the_tier_table
>       assert "Unrelated" not in text
E       AssertionError: assert 'Unrelated' not in 'Perform a o...laims\n```\n'
1 failed in 0.67s
```

**restore** (`plugins/superheroes/lib/conformance_probe.py`, `_severity_scale`):
```python
        elif saw_table_row and row.strip() and not row.startswith("#"):
            break
```

**raw green** (exit 0): `1 passed in 0.74s`

---

## BP-R3-4 — ledger read

- **axis:** malformed JSON ledger must refuse before claim or dispatch

**neutralization** (`plugins/superheroes/lib/conformance_probe.py`, `_read_astra_attempts`):
```python
    except ValueError:
        return [], None
```
(split from the combined `(OSError, ValueError)` refusal handler)

**command:** `plugins/superheroes/lib/tests/test_conformance_probe.py::test_astra_probe_refuses_unreadable_ledger[{]`

**raw red** (exit 1):
```
FAILED plugins/superheroes/lib/tests/test_conformance_probe.py::test_astra_probe_refuses_unreadable_ledger[{]
>       assert out["reason"] == "astra-probe-ledger-unreadable"
E       KeyError: 'reason'
1 failed in 0.67s
```

**restore** (`plugins/superheroes/lib/conformance_probe.py`, `_read_astra_attempts`):
```python
    except (OSError, ValueError):
        return None, "astra-probe-ledger-unreadable"
```

**raw green** (exit 0): `1 passed in 0.79s`

---

## BP-R3-5 — append never overwrites

- **axis:** append on unreadable ledger must not overwrite bytes

**neutralization** (`plugins/superheroes/lib/conformance_probe.py`, `_append_astra_attempt`):
```python
    if err:
        attempts = []
```

**command:** `plugins/superheroes/lib/tests/test_conformance_probe.py::test_append_refuses_unreadable_ledger_without_writing`

**raw red** (exit 1):
```
FAILED plugins/superheroes/lib/tests/test_conformance_probe.py::test_append_refuses_unreadable_ledger_without_writing
>       assert err == "astra-probe-ledger-unreadable"
E       AssertionError: assert None == 'astra-probe-ledger-unreadable'
1 failed in 0.73s
```

**restore** (`plugins/superheroes/lib/conformance_probe.py`, `_append_astra_attempt`):
```python
    if err:
        return err
```

**raw green** (exit 0): `1 passed in 0.57s`

---

## BP-R3-6 — claim unlink

- **axis:** failed claim write must leave no partial claim file

**neutralization** (`plugins/superheroes/lib/conformance_probe.py`, `_write_astra_claim`):
```python
    # deleted unlink-on-failure block after O_EXCL create
```

**command:** `plugins/superheroes/lib/tests/test_conformance_probe.py::test_astra_claim_write_failure_leaves_no_claim`

**raw red** (exit 1):
```
FAILED plugins/superheroes/lib/tests/test_conformance_probe.py::test_astra_claim_write_failure_leaves_no_claim
>       assert not os.path.exists(claim_path)
E       AssertionError: assert not True
1 failed in 0.70s
```

**restore** (`plugins/superheroes/lib/conformance_probe.py`, `_write_astra_claim`):
```python
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass
```

**raw green** (exit 0): `1 passed in 0.69s`

---

## BP-R3-7 — record-write refusal

- **axis:** terminal append OSError must become a named refusal, not a silent success

**neutralization** (`plugins/superheroes/lib/conformance_probe.py`, `astra_probe`):
```python
    _append_astra_attempt(ledger_dir, _ledger_attempt_record(out))
    return out, (0 if out["ok"] else 1)
```
(replaces the `append_err` refusal branch)

**command:** `plugins/superheroes/lib/tests/test_conformance_probe.py::test_astra_probe_record_write_failure_is_a_named_refusal`

**raw red** (exit 1):
```
FAILED plugins/superheroes/lib/tests/test_conformance_probe.py::test_astra_probe_record_write_failure_is_a_named_refusal
>       assert code == 1
E       assert 0 == 1
1 failed in 0.73s
```

**restore** (`plugins/superheroes/lib/conformance_probe.py`, `astra_probe`):
```python
    append_err = _append_astra_attempt(ledger_dir, _ledger_attempt_record(out))
    if append_err:
        refusal = {"ok": False, "reason": append_err, "unrecorded": out}
        return refusal, 1
    return out, (0 if out["ok"] else 1)
```

**raw green** (exit 0): `1 passed in 0.76s`

---

## BP-R3-8 — file leg

- **axis:** right line on wrong file must miss

**neutralization** (`plugins/superheroes/lib/conformance_probe.py`, `_match_astra_finding`):
```python
    file_ok = True
```

**command:** `plugins/superheroes/lib/tests/test_conformance_probe.py::test_astra_probe_miss_right_line_wrong_file`

**raw red** (exit 1):
```
FAILED plugins/superheroes/lib/tests/test_conformance_probe.py::test_astra_probe_miss_right_line_wrong_file
>       assert code == 1
E       assert 0 == 1
1 failed in 1.02s
```

**restore** (`plugins/superheroes/lib/conformance_probe.py`, `_match_astra_finding`):
```python
    file_ok = _normalize_finding_file(finding.get("file")) == PLANT_FILE
```

**raw green** (exit 0): `1 passed in 0.82s`

---

## BP-R3-9 — grade rule

- **axis:** unrelated findings beside a match must not spoil a pass

**neutralization** (`plugins/superheroes/lib/conformance_probe.py`, `_grade_astra_findings`):
```python
    if len(findings or []) != 1:
        return False, None
```

**command:** `plugins/superheroes/lib/tests/test_conformance_probe.py::test_astra_probe_pass_with_an_unrelated_finding_beside_the_match`

**raw red** (exit 1):
```
FAILED plugins/superheroes/lib/tests/test_conformance_probe.py::test_astra_probe_pass_with_an_unrelated_finding_beside_the_match
>       assert code == 0
E       assert 1 == 0
1 failed in 1.22s
```

**restore** (`plugins/superheroes/lib/conformance_probe.py`, `_grade_astra_findings`): removed the `len(findings) != 1` early return.

**raw green** (exit 0): `1 passed in 0.82s`

---

## BP-R3-10 — claim fd closes once

- **axis:** a failed claim write must not call `os.close` on the claim fd after `fdopen`

**neutralization** (`plugins/superheroes/lib/conformance_probe.py`, `_write_astra_claim`):
```python
    except BaseException:
        os.close(fd)  # bite-proof BP-R3-10 neutralization
        try:
            os.unlink(path)
```

**command:** `plugins/superheroes/lib/tests/test_conformance_probe.py::test_astra_claim_write_failure_does_not_close_fd_twice`

**raw red** (exit 1):
```
FAILED plugins/superheroes/lib/tests/test_conformance_probe.py::test_astra_claim_write_failure_does_not_close_fd_twice
>           CP._write_astra_claim(ledger_dir, "wave-claim", str(tmp_path / "run"))
E       OSError: [Errno 9] Bad file descriptor
1 failed in 0.81s
```

**restore** (`plugins/superheroes/lib/conformance_probe.py`, `_write_astra_claim`): removed the `os.close(fd)` line from the write-failure handler.

**raw green** (exit 0): `1 passed in 0.61s`
