# Bite-proof record — #1272 layer 2i-b (`re-emit`, the superseded-attempt close, and the relocation fence)

Contract: `rubric/bite-proof.md`. Every proof below ran with the **detector unedited**. Each neutralization was one targeted, reversible edit to a production line, applied with the edit tool and restored by its exact inverse edit — never `git checkout` and never a whole-file rewrite. After every restore, `git diff --quiet` on the neutralized file printed `0`.

**The declared guarded set — 27 elements.** It was declared in work orders c13-2ib-r3-woD2a/b/c before any proof ran:

- **G1** — `record_paths.landing_entry_present`
- **G2a–G2c** — the superseded-attempt close in `round_certification._journal_open_seats`
- **G3a, G3b, G4** — `re-emit`'s result blockers and attempt allocation
- **G5–G11**, including **G8a–G8c** — the relocation-evidence reader: `read_journal`, `_relocation_lookup` and `_relocation_after_emission`
- **G12a–G12c** — the hand-submit fence
- **G13a–G17b** — the record-result, sweep, advance and `re-emit` fence callers, and the `round_records.validate_landing` chokepoint

The set is WO-D1's eight axis-lined guards, re-derived at the final head. The ruled round-6 re-plan made two changes:
- It folded the single-seat record-result site into the `round_records` chokepoint (G13, G17).
- It added the evidence-reader guards (G5–G11, G15, G16).

Every guard with more than one independently neutralizable operand or branch is split into one element per operand or branch.

**Who ran these, and where.**
- **Implementer proofs:** cursor `composer-2.5`, three orders in three dedicated probe worktrees (`issue-1272-2ib-r3-bpa`, `-bpb`, `-bpc`), each at the final head `0506c2fc`. Their entries follow verbatim in parts a, b and c.
- **Orchestrator re-run:** the workhorse orchestrator re-ran every element itself in a fourth detached probe tree (`issue-1272-2ib-r3-probe`) at `0506c2fc`. Where the two disagree, the table at the end records the disposition. **The orchestrator's re-run is the authoritative receipt.**

Every command had this shape: `/usr/bin/python3 -B -X pycache_prefix=<scratch> -m pytest <node-id> -q -p no:randomly`. Detectors were selected by exact node id, never by `-k`. Nothing was redacted; the captures hold only temp paths.

---

**Implementer record, part a** (WO-D2a, worktree `issue-1272-2ib-r3-bpa`, verbatim):

## G1 — `landing_entry_present`, `except OSError:` branch

**Guarded element.** `plugins/superheroes/lib/record_paths.py`, `landing_entry_present`, the `except OSError:` branch (`return True`). **Axis:** an lstat error other than not-found counts as present.

**Neutralization:** keep comment line; `return True` → `return False`

**Detector.** `plugins/superheroes/lib/tests/test_round_driver_re_emit.py::test_landing_entry_present_lstat_outcomes`.

**Red** (EXIT=1):

```
>       assert record_paths.landing_entry_present(str(denied)) is True
E       AssertionError: assert False is True
FAILED plugins/superheroes/lib/tests/test_round_driver_re_emit.py::test_landing_entry_present_lstat_outcomes
1 failed in 0.50s
```

**Restore.** Inverse edit. **Restore receipt:** `git diff --quiet -- plugins/superheroes/lib/record_paths.py; echo $?` → `0`.

**Green** (EXIT=0): `1 passed in 0.48s`.

## G2a — `_journal_open_seats`, superseded-close landing operand

**Guarded element.** `plugins/superheroes/lib/round_certification.py`, `_journal_open_seats`, `if (not record_paths.landing_entry_present(landing)`. **Axis:** a superseded seat stays open while its landing entry exists.

**Neutralization:** `if (not record_paths.landing_entry_present(landing)` → `if (True`

**Detector.** `plugins/superheroes/lib/tests/test_round_driver_re_emit.py::test_certification_late_attempt0_landing_keeps_seat_open` (failed parameter id: `[envelope-file]`).

**Red** (EXIT=1):

```
>       assert len(late_keys) == 1
E       assert 0 == 1
FAILED plugins/superheroes/lib/tests/test_round_driver_re_emit.py::test_certification_late_attempt0_landing_keeps_seat_open[envelope-file]
1 failed, 2 passed in 24.05s
```

**Restore.** Inverse edit. **Restore receipt:** `git diff --quiet -- plugins/superheroes/lib/round_certification.py; echo $?` → `0`.

**Green** (EXIT=0): `3 passed in 28.82s`.

## G2b — `_journal_open_seats`, superseded-close bare-payload operand

**Guarded element.** `plugins/superheroes/lib/round_certification.py`, `_journal_open_seats`, `and not record_paths.landing_entry_present(bare))`. **Axis:** a superseded seat stays open while its bare-payload entry exists.

**Neutralization:** `and not record_paths.landing_entry_present(bare)):` → `and True):`

**Detector.** `plugins/superheroes/lib/tests/test_round_driver_re_emit.py::test_certification_late_attempt0_landing_keeps_seat_open` (failed parameter ids: `[bare-file]`, `[bare-dangling_symlink]`).

**Red** (EXIT=1):

```
>       assert len(late_keys) == 1
E       assert 0 == 1
FAILED plugins/superheroes/lib/tests/test_round_driver_re_emit.py::test_certification_late_attempt0_landing_keeps_seat_open[bare-file]
FAILED plugins/superheroes/lib/tests/test_round_driver_re_emit.py::test_certification_late_attempt0_landing_keeps_seat_open[bare-dangling_symlink]
2 failed, 1 passed in 28.28s
```

**Restore.** Inverse edit. **Restore receipt:** `git diff --quiet -- plugins/superheroes/lib/round_certification.py; echo $?` → `0`.

**Green** (EXIT=0): `3 passed in 28.82s`.

## G2c — `_journal_open_seats`, unknown-session-dir leg

**Guarded element.** `plugins/superheroes/lib/round_certification.py`, `_journal_open_seats`, `if session_dir is not None:` (superseded block). **Axis:** with no session dir, a superseded seat stays open.

**Neutralization:** insert `if session_dir is None:` / `continue` above the original `if session_dir is not None:`

**Detector.** `plugins/superheroes/lib/tests/test_round_driver_re_emit.py::test_certification_legacy_emitted_row_stays_open_without_session_dir`.

**Red** (EXIT=1):

```
>       assert ("dispatch-panel", 1, 0, "code-reviewer", 0) in [k for k, _ in unclosed]
E       AssertionError: assert ('dispatch-panel', 1, 0, 'code-reviewer', 0) in []
FAILED plugins/superheroes/lib/tests/test_round_driver_re_emit.py::test_certification_legacy_emitted_row_stays_open_without_session_dir
1 failed in 0.69s
```

**Restore.** Inverse edit (remove inserted two lines). **Restore receipt:** `git diff --quiet -- plugins/superheroes/lib/round_certification.py; echo $?` → `0`.

**Green** (EXIT=0): `1 passed in 0.59s`.

## G3a — `_re_emit_blocking_result_names`, landing leg

**Guarded element.** `plugins/superheroes/lib/round_driver.py`, `_re_emit_blocking_result_names`, `if record_paths.landing_entry_present(landing):`. **Axis:** an unrecorded old-attempt slot's landing entry blocks re-emit.

**Neutralization:** `if record_paths.landing_entry_present(landing):` → `if False:`

**Detector.** `plugins/superheroes/lib/tests/test_round_driver_re_emit.py::test_re_emit_refusal_tokens[re-emit-attempt-has-results-results_landing]`.

**Red** (EXIT=1):

```
>       assert rc == 1
E       assert 0 == 1
FAILED plugins/superheroes/lib/tests/test_round_driver_re_emit.py::test_re_emit_refusal_tokens[re-emit-attempt-has-results-results_landing]
1 failed in 11.17s
```

**Restore.** Inverse edit. **Restore receipt:** `git diff --quiet -- plugins/superheroes/lib/round_driver.py; echo $?` → `0`.

**Green** (EXIT=0): `1 passed in 7.27s`.

## G3b — `_re_emit_blocking_result_names`, bare leg

**Guarded element.** `plugins/superheroes/lib/round_driver.py`, `_re_emit_blocking_result_names`, `if record_paths.landing_entry_present(bare):`. **Axis:** an unrecorded old-attempt slot's bare-payload entry blocks re-emit.

**Neutralization:** `if record_paths.landing_entry_present(bare):` → `if False:`

**Detector.** `plugins/superheroes/lib/tests/test_round_driver_re_emit.py::test_re_emit_refusal_tokens[re-emit-attempt-has-results-results_bare]`.

**Red** (EXIT=1):

```
>       assert rc == 1
E       assert 0 == 1
FAILED plugins/superheroes/lib/tests/test_round_driver_re_emit.py::test_re_emit_refusal_tokens[re-emit-attempt-has-results-results_bare]
1 failed in 11.88s
```

**Restore.** Inverse edit. **Restore receipt:** `git diff --quiet -- plugins/superheroes/lib/round_driver.py; echo $?` → `0`.

**Green** (EXIT=0): `1 passed in 5.11s`.

## G4 — `_cmd_re_emit_locked`, new-attempt allocation

**Guarded element.** `plugins/superheroes/lib/round_driver.py`, `_cmd_re_emit_locked`, `new_attempt = max(_next_dispatch_attempt(session_dir, rnd, phase, state), old_attempt + 1)`. **Axis:** the new attempt is above the pending one even when nothing was accepted.

**Neutralization:** `new_attempt = max(_next_dispatch_attempt(session_dir, rnd, phase, state), old_attempt + 1)` → `new_attempt = _next_dispatch_attempt(session_dir, rnd, phase, state)`

**Detector.** `plugins/superheroes/lib/tests/test_round_driver_re_emit.py::test_re_emit_positive_after_relocate`, then `plugins/superheroes/lib/tests/test_round_driver_re_emit.py::test_re_emit_cli_success_json`.

**Red** — NOT RED — `test_re_emit_positive_after_relocate`, EXIT=1 (source_guard teardown; test body passed: `1 passed, 1 error in 8.47s`); `test_re_emit_cli_success_json`, EXIT=0 (`1 passed in 6.77s`). The relocate fixture's journal already drives `_next_dispatch_attempt` to `old_attempt + 1`, so removing the `max(..., old_attempt + 1)` floor does not change the allocated attempt.

**Restore.** Inverse edit. **Restore receipt:** `git diff --quiet -- plugins/superheroes/lib/round_driver.py; echo $?` → `0`.

**Green** (EXIT=0): not run separately; production code restored to head `0506c2fc`.

## G12a — hand-submit fence predates branch

**Guarded element.** `plugins/superheroes/lib/round_driver.py`, hand-submit fence, `if relocation is not None:` (predates branch). **Axis:** a hand submit of a dispatch phase emitted before the move is refused.

**Neutralization:** keep `"detail": RELOCATION_EVIDENCE_INDETERMINATE_DETAIL}` line; `if relocation is not None:` → `if False:`

**Detector.** `plugins/superheroes/lib/tests/test_round_driver_re_emit.py::test_relocation_fence_hand_submit_refused_after_relocate`.

**Red** (EXIT=1):

```
>       assert out["reason"] == RD.RECORD_ATTEMPT_PREDATES_RELOCATION_CAUSE
E       AssertionError: assert 'state-hash m... stale submit' == 'record-attem...es-relocation'
FAILED plugins/superheroes/lib/tests/test_round_driver_re_emit.py::test_relocation_fence_hand_submit_refused_after_relocate
1 failed in 3.44s
```

**Restore.** Inverse edit. **Restore receipt:** `git diff --quiet -- plugins/superheroes/lib/round_driver.py; echo $?` → `0`.

**Green** (EXIT=0): `1 passed in 2.72s`.

## G12b — hand-submit fence indeterminate branch

**Guarded element.** `plugins/superheroes/lib/round_driver.py`, hand-submit fence, `if relocation is _RELOCATION_EVIDENCE_INDETERMINATE:`. **Axis:** indeterminate relocation evidence refuses a hand submit as indeterminate.

**Neutralization:** keep `relocation = _relocation_lookup(...)` line; `if relocation is _RELOCATION_EVIDENCE_INDETERMINATE:` → `if False:`

**Detector.** `plugins/superheroes/lib/tests/test_round_driver_re_emit.py::test_relocation_evidence_faults_refuse_all_callers` (failed hand-submit parameter ids: `null`, `list`, `number`, `string`, `unparseable`, `invalid-utf8`, `fault-marker`, `bad-relocated-roots`).

**Red** (EXIT=1):

```
>       assert out["reason"] == RD.RELOCATION_EVIDENCE_INDETERMINATE_CAUSE
E       AssertionError: assert 'record-attem...es-relocation' == 'relocation-e...indeterminate'
FAILED plugins/superheroes/lib/tests/test_round_driver_re_emit.py::test_relocation_evidence_faults_refuse_all_callers[hand-submit-null]
(... 7 more hand-submit ids with the same assertion failure ...)
8 failed, 32 passed in 83.69s
```

**Restore.** Inverse edit. **Restore receipt:** `git diff --quiet -- plugins/superheroes/lib/round_driver.py; echo $?` → `0`.

**Green** (EXIT=0): `40 passed in 81.69s`.

## G12c — hand-submit fence advance exemption

**Guarded element.** `plugins/superheroes/lib/round_driver.py`, hand-submit fence, `if (not _via_advance and isinstance(phase, str) and phase.startswith("dispatch-")):`. **Axis:** the advance-driven fold is not fenced.

**Neutralization:** `if (not _via_advance and isinstance(phase, str) and phase.startswith("dispatch-")):` → `if (isinstance(phase, str) and phase.startswith("dispatch-")):`

**Detector.** `plugins/superheroes/lib/tests/test_round_driver_re_emit.py::test_relocation_fence_advance_folds_seats_recorded_before_relocate`.

**Red** (EXIT=1):

```
>       assert not any(
E       assert not True
FAILED plugins/superheroes/lib/tests/test_round_driver_re_emit.py::test_relocation_fence_advance_folds_seats_recorded_before_relocate
1 failed in 2.88s
```

**Restore.** Inverse edit. **Restore receipt:** `git diff --quiet -- plugins/superheroes/lib/round_driver.py; echo $?` → `0`.

**Green** (EXIT=0): `1 passed in 2.83s`.


**Implementer record, part b** (WO-D2b, worktree `issue-1272-2ib-r3-bpb`, verbatim):

## G5 — `read_journal`, the ValueError branch

**Guarded element.** `read_journal`, `if report_lossy:` / `lossy = True` under `except ValueError:`. **Axis:** a lossy journal read flags unparseable lines for relocation evidence.

**Neutralization:** `if report_lossy:` / `lossy = True` → `if report_lossy:` / `lossy = False`

**Detector.** `plugins/superheroes/lib/tests/test_round_driver_re_emit.py::test_relocation_evidence_faults_refuse_all_callers` (unparseable parameters).

**Red** (EXIT=1):

```
>       assert out["reason"] == RD.RELOCATION_EVIDENCE_INDETERMINATE_CAUSE
E       AssertionError: assert 're-emit-attempt-has-results' == 'relocation-e...indeterminate'
FAILED .../test_round_driver_re_emit.py::test_relocation_evidence_faults_refuse_all_callers[re-emit-unparseable]
FAILED .../test_round_driver_re_emit.py::test_relocation_evidence_faults_refuse_all_callers[hand-submit-unparseable]
FAILED .../test_round_driver_re_emit.py::test_relocation_evidence_faults_refuse_all_callers[record-result-unparseable]
FAILED .../test_round_driver_re_emit.py::test_relocation_evidence_faults_refuse_all_callers[record-sweep-unparseable]
FAILED .../test_round_driver_re_emit.py::test_relocation_evidence_faults_refuse_all_callers[advance-unparseable]
5 failed, 35 passed in 199.85s
```

**Restore.** Inverse edit (`lossy = False` → `lossy = True`). **Restore receipt:** `git diff --quiet -- plugins/superheroes/lib/round_driver.py; echo $?` → `0`.

**Green** (EXIT=0): `40 passed in 87.15s`.

## G6 — `read_journal`, the UnicodeError branch

**Guarded element.** `read_journal`, `except UnicodeError:` / `if report_lossy:` / `lossy = True`. **Axis:** an undecodable journal flags the read lossy.

**Neutralization:** keep first two lines, change third to `lossy = False`

**Detector.** `plugins/superheroes/lib/tests/test_round_driver_re_emit.py::test_relocation_evidence_faults_refuse_all_callers` (invalid-utf8 parameters).

**Red** (EXIT=1):

```
E       UnicodeDecodeError: 'utf-8' codec can't decode byte 0xff in position 1486: invalid start byte
FAILED .../test_round_driver_re_emit.py::test_relocation_evidence_faults_refuse_all_callers[re-emit-invalid-utf8]
FAILED .../test_round_driver_re_emit.py::test_relocation_evidence_faults_refuse_all_callers[hand-submit-invalid-utf8]
FAILED .../test_round_driver_re_emit.py::test_relocation_evidence_faults_refuse_all_callers[record-result-invalid-utf8]
FAILED .../test_round_driver_re_emit.py::test_relocation_evidence_faults_refuse_all_callers[record-sweep-invalid-utf8]
FAILED .../test_round_driver_re_emit.py::test_relocation_evidence_faults_refuse_all_callers[advance-invalid-utf8]
5 failed, 35 passed in 94.53s
```

**Restore.** Inverse edit (`lossy = False` → `lossy = True`). **Restore receipt:** `git diff --quiet -- plugins/superheroes/lib/round_driver.py; echo $?` → `0`.

**Green** (EXIT=0): `40 passed in 87.15s`.

## G7 — `_relocation_lookup`, the lossy check

**Guarded element.** `_relocation_lookup`, `if lossy:`. **Axis:** a lossy read makes relocation evidence indeterminate.

**Neutralization:** `if lossy:` → `if False:`

**Detector.** `plugins/superheroes/lib/tests/test_round_driver_re_emit.py::test_relocation_evidence_faults_refuse_all_callers`.

**Red** (EXIT=1):

```
FAILED .../test_round_driver_re_emit.py::test_relocation_evidence_faults_refuse_all_callers[re-emit-unparseable]
FAILED .../test_round_driver_re_emit.py::test_relocation_evidence_faults_refuse_all_callers[re-emit-invalid-utf8]
FAILED .../test_round_driver_re_emit.py::test_relocation_evidence_faults_refuse_all_callers[hand-submit-unparseable]
FAILED .../test_round_driver_re_emit.py::test_relocation_evidence_faults_refuse_all_callers[hand-submit-invalid-utf8]
FAILED .../test_round_driver_re_emit.py::test_relocation_evidence_faults_refuse_all_callers[record-result-unparseable]
FAILED .../test_round_driver_re_emit.py::test_relocation_evidence_faults_refuse_all_callers[record-result-invalid-utf8]
FAILED .../test_round_driver_re_emit.py::test_relocation_evidence_faults_refuse_all_callers[record-sweep-unparseable]
FAILED .../test_round_driver_re_emit.py::test_relocation_evidence_faults_refuse_all_callers[record-sweep-invalid-utf8]
FAILED .../test_round_driver_re_emit.py::test_relocation_evidence_faults_refuse_all_callers[advance-unparseable]
FAILED .../test_round_driver_re_emit.py::test_relocation_evidence_faults_refuse_all_callers[advance-invalid-utf8]
10 failed, 30 passed in 83.19s
```

**Restore.** Inverse edit (`if False:` → `if lossy:`). **Restore receipt:** `git diff --quiet -- plugins/superheroes/lib/round_driver.py; echo $?` → `0`.

**Green** (EXIT=0): `40 passed in 87.15s`.

## G8a — `_relocation_lookup`, the non-object pre-scan

**Guarded element.** `_relocation_lookup`, `for row in journal:` / `if not isinstance(row, dict):` / `return _RELOCATION_EVIDENCE_INDETERMINATE`. **Axis:** a non-object journal row makes relocation evidence indeterminate.

**Neutralization:** keep first two lines, change third to `continue`

**Detector.** `plugins/superheroes/lib/tests/test_round_driver_re_emit.py::test_relocation_evidence_faults_refuse_all_callers`.

**Red:** NOT RED — `test_relocation_evidence_faults_refuse_all_callers`, EXIT=0, `40 passed in 88.97s`. `_relocation_after_emission`'s first-loop non-object check (G8b) returns indeterminate on the same row before this pre-scan's neutralization can change the outcome through the listed detector path.

**Restore.** Inverse edit (`continue` → `return _RELOCATION_EVIDENCE_INDETERMINATE`). **Restore receipt:** `git diff --quiet -- plugins/superheroes/lib/round_driver.py; echo $?` → `0`.

**Green** (EXIT=0): `40 passed in 87.15s`.

## G8b — `_relocation_after_emission`, the first loop's non-object check

**Guarded element.** `_relocation_after_emission`, `if not isinstance(event, dict):` / `return _RELOCATION_EVIDENCE_INDETERMINATE` (first loop). **Axis:** a non-object journal row makes relocation evidence indeterminate.

**Neutralization:** keep lines 1 and 3, change line 2 to `continue`

**Detector.** `plugins/superheroes/lib/tests/test_round_driver_re_emit.py::test_relocation_after_emission_predicate`, then `test_relocation_evidence_faults_refuse_all_callers`.

**Red:** NOT RED — predicate EXIT=0 (`1 passed in 0.32s`); faults EXIT=0 (`40 passed in 78.57s`). No listed candidate passes a non-object row directly into `_relocation_after_emission`; `_relocation_lookup`'s pre-scan (G8a at full strength) catches non-object rows before the function is called.

**Restore.** Inverse edit (`continue` → `return _RELOCATION_EVIDENCE_INDETERMINATE`). **Restore receipt:** `git diff --quiet -- plugins/superheroes/lib/round_driver.py; echo $?` → `0`.

**Green** (EXIT=0): `1 passed in 0.34s` (predicate).

## G8c — `_relocation_after_emission`, the second loop's non-object check

**Guarded element.** `_relocation_after_emission`, `for event in journal[start:]:` / `if not isinstance(event, dict):` / `return _RELOCATION_EVIDENCE_INDETERMINATE`. **Axis:** a non-object journal row makes relocation evidence indeterminate.

**Neutralization:** keep lines 1–2, change line 3 to `continue`

**Detector.** `plugins/superheroes/lib/tests/test_round_driver_re_emit.py::test_relocation_after_emission_predicate`.

**Red:** NOT RED — `test_relocation_after_emission_predicate`, EXIT=0, `1 passed in 0.33s`. The first loop's non-object check (G8b at full strength) returns indeterminate before the second loop is reached.

**Restore.** Inverse edit (`continue` → `return _RELOCATION_EVIDENCE_INDETERMINATE`). **Restore receipt:** `git diff --quiet -- plugins/superheroes/lib/round_driver.py; echo $?` → `0`.

**Green** (EXIT=0): `1 passed in 0.34s` (predicate).

## G9 — `_relocation_after_emission`, the relocated-row roots check

**Guarded element.** `_relocation_after_emission`, `if not isinstance(old_root, str) or not isinstance(new_root, str):` / `return _RELOCATION_EVIDENCE_INDETERMINATE`. **Axis:** a relocated row without string roots makes relocation evidence indeterminate.

**Neutralization:** keep line 1, change line 2 to `continue`

**Detector.** `plugins/superheroes/lib/tests/test_round_driver_re_emit.py::test_relocation_evidence_faults_refuse_all_callers` (bad-relocated-roots parameters).

**Red** (EXIT=1):

```
>       assert out["reason"] == RD.RELOCATION_EVIDENCE_INDETERMINATE_CAUSE
E       AssertionError: assert 're-emit-not-stale' == 'relocation-e...indeterminate'
FAILED .../test_round_driver_re_emit.py::test_relocation_evidence_faults_refuse_all_callers[re-emit-bad-relocated-roots]
FAILED .../test_round_driver_re_emit.py::test_relocation_evidence_faults_refuse_all_callers[hand-submit-bad-relocated-roots]
FAILED .../test_round_driver_re_emit.py::test_relocation_evidence_faults_refuse_all_callers[record-result-bad-relocated-roots]
FAILED .../test_round_driver_re_emit.py::test_relocation_evidence_faults_refuse_all_callers[record-sweep-bad-relocated-roots]
FAILED .../test_round_driver_re_emit.py::test_relocation_evidence_faults_refuse_all_callers[advance-bad-relocated-roots]
5 failed, 35 passed in 86.53s
```

**Restore.** Inverse edit (`continue` → `return _RELOCATION_EVIDENCE_INDETERMINATE`). **Restore receipt:** `git diff --quiet -- plugins/superheroes/lib/round_driver.py; echo $?` → `0`.

**Green** (EXIT=0): `40 passed in 87.15s`.

## G10 — `_relocation_after_emission`, the fail-closed start

**Guarded element.** `_relocation_after_emission`, `start = 0 if last_emit_idx is None else last_emit_idx + 1`. **Axis:** a dispatch attempt with no emission row counts as stale when any move exists.

**Neutralization:** `start = 0 if last_emit_idx is None else last_emit_idx + 1` → `start = len(journal) if last_emit_idx is None else last_emit_idx + 1`

**Detector.** `plugins/superheroes/lib/tests/test_round_driver_re_emit.py::test_relocation_after_emission_predicate`.

**Red** (EXIT=1):

```
>       assert RD._relocation_after_emission([moved], rnd, phase, attempt) == moved
E       AssertionError: assert None == {'newRoot': '...', 'oldRoot': '...', 'outcome': 'relocated'}
FAILED .../test_round_driver_re_emit.py::test_relocation_after_emission_predicate
1 failed in 0.36s
```

**Restore.** Inverse edit (`start = len(journal)` → `start = 0`). **Restore receipt:** `git diff --quiet -- plugins/superheroes/lib/round_driver.py; echo $?` → `0`.

**Green** (EXIT=0): `1 passed in 0.34s`.

## G11 — `_relocation_lookup`, the journal-fault-marker rule

**Guarded element.** `_relocation_lookup`, `if _journal_faulted(session_dir) and _journal_has_relocated_row(journal):`. **Axis:** a journal-fault marker makes relocation evidence indeterminate when a move was recorded.

**Neutralization:** `if _journal_faulted(session_dir) and _journal_has_relocated_row(journal):` → `if False and _journal_faulted(session_dir) and _journal_has_relocated_row(journal):`

**Detector.** `plugins/superheroes/lib/tests/test_round_driver_re_emit.py::test_relocation_evidence_faults_refuse_all_callers` (fault-marker parameters).

**Red** (EXIT=1):

```
>       assert out["reason"] == RD.RELOCATION_EVIDENCE_INDETERMINATE_CAUSE
E       AssertionError: assert 're-emit-attempt-has-results' == 'relocation-e...indeterminate'
FAILED .../test_round_driver_re_emit.py::test_relocation_evidence_faults_refuse_all_callers[re-emit-fault-marker]
FAILED .../test_round_driver_re_emit.py::test_relocation_evidence_faults_refuse_all_callers[hand-submit-fault-marker]
FAILED .../test_round_driver_re_emit.py::test_relocation_evidence_faults_refuse_all_callers[record-result-fault-marker]
FAILED .../test_round_driver_re_emit.py::test_relocation_evidence_faults_refuse_all_callers[record-sweep-fault-marker]
FAILED .../test_round_driver_re_emit.py::test_relocation_evidence_faults_refuse_all_callers[advance-fault-marker]
5 failed, 35 passed in 87.77s
```

**Restore.** Inverse edit (`if False and` → `if`). **Restore receipt:** `git diff --quiet -- plugins/superheroes/lib/round_driver.py; echo $?` → `0`.

**Green** (EXIT=0): `40 passed in 87.15s`.


**Implementer record, part c** (WO-D2c, worktree `issue-1272-2ib-r3-bpc`, verbatim):

## G13a — `cmd_record_result`, single-seat fence

**Guarded element.** `plugins/superheroes/lib/round_driver.py`, `cmd_record_result`, `relocation_fenced = relocation is not None`. **Axis:** an order-anchor result for an attempt emitted before the move is refused.

**Neutralization:** `relocation_fenced = relocation is not None` → `relocation_fenced = False`

**Detector.** `plugins/superheroes/lib/tests/test_round_driver_re_emit.py::test_relocation_fence_hand_record_refused_after_relocate`

**Red** (EXIT=1):

```
>       assert out["ok"] is False
E       assert True is False
FAILED plugins/superheroes/lib/tests/test_round_driver_re_emit.py::test_relocation_fence_hand_record_refused_after_relocate
1 failed in 5.83s
```

**Restore.** Inverse edit. **Restore receipt:** `git diff --quiet -- plugins/superheroes/lib/round_driver.py; echo $?` → `0`.

**Green** (EXIT=0): `1 passed in 5.87s`.

## G13b — `cmd_record_result`, indeterminate branch

**Guarded element.** `plugins/superheroes/lib/round_driver.py`, `cmd_record_result`, `if relocation is _RELOCATION_EVIDENCE_INDETERMINATE:`. **Axis:** indeterminate relocation evidence refuses a record-result as indeterminate.

**Neutralization:** `if relocation is _RELOCATION_EVIDENCE_INDETERMINATE:` → `if False:` (lookup line kept)

**Detector.** `plugins/superheroes/lib/tests/test_round_driver_re_emit.py::test_relocation_evidence_faults_refuse_all_callers` (record-result parameter ids)

**Red** — NOT RED — whole function, EXIT=1, `8 failed, 32 passed in 161.61s`. All eight `[record-result-*]` cases failed on the reason assertion with `record-attempt-predates-relocation` instead of `relocation-evidence-indeterminate`; bypassing the indeterminate branch leaves `relocation_fenced = relocation is not None` true for the indeterminate sentinel, so the single-seat fence (G13a / validate_landing G17a) refuses first on a different axis.

**Restore.** Inverse edit. **Restore receipt:** `git diff --quiet -- plugins/superheroes/lib/round_driver.py; echo $?` → `0`.

**Green** (EXIT=0): `40 passed in 88.70s`.

## G14a — `_sweep_record`, fenced refusal

**Guarded element.** `plugins/superheroes/lib/round_driver.py`, `_sweep_record`, `fenced = relocation_fence is not None`. **Axis:** a sweep or advance that would ingest a landing for an attempt emitted before the move is refused.

**Neutralization:** `fenced = relocation_fence is not None` → `fenced = False`

**Detector.** `plugins/superheroes/lib/tests/test_round_driver_re_emit.py::test_relocation_fence_sweep_refuses_unclaimed_attempt0_landing`

**Red** (EXIT=1):

```
>       assert out["ok"] is False
E       assert True is False
FAILED plugins/superheroes/lib/tests/test_round_driver_re_emit.py::test_relocation_fence_sweep_refuses_unclaimed_attempt0_landing
1 failed in 2.43s
```

**Restore.** Inverse edit. **Restore receipt:** `git diff --quiet -- plugins/superheroes/lib/round_driver.py; echo $?` → `0`.

**Green** (EXIT=0): `1 passed in 2.37s`.

## G14b — `_sweep_record`, indeterminate branch

**Guarded element.** `plugins/superheroes/lib/round_driver.py`, `_sweep_record`, `if relocation_fence is _RELOCATION_EVIDENCE_INDETERMINATE:`. **Axis:** indeterminate relocation evidence refuses a sweep as indeterminate.

**Neutralization:** `if relocation_fence is _RELOCATION_EVIDENCE_INDETERMINATE:` → `if False:`

**Detector.** `plugins/superheroes/lib/tests/test_round_driver_re_emit.py::test_relocation_evidence_faults_refuse_all_callers` (record-sweep parameter ids)

**Red** — NOT RED — whole function, EXIT=1, `8 failed, 32 passed in 83.20s`. All eight `[record-sweep-*]` cases failed on the reason assertion with `record-attempt-predates-relocation` instead of `relocation-evidence-indeterminate`; with the indeterminate branch bypassed, `fenced = relocation_fence is not None` stays true for the indeterminate sentinel and the sweep fence (G14a) refuses first on a different axis.

**Restore.** Inverse edit. **Restore receipt:** `git diff --quiet -- plugins/superheroes/lib/round_driver.py; echo $?` → `0`.

**Green** (EXIT=0): `40 passed in 78.03s`.

## G15 — `advance`, indeterminate check

**Guarded element.** `plugins/superheroes/lib/round_driver.py`, `advance`, `if relocation is _RELOCATION_EVIDENCE_INDETERMINATE:`. **Axis:** indeterminate relocation evidence refuses an advance as indeterminate.

**Neutralization:** `if relocation is _RELOCATION_EVIDENCE_INDETERMINATE:` → `if False:` (lookup line kept)

**Detector.** `plugins/superheroes/lib/tests/test_round_driver_re_emit.py::test_relocation_evidence_faults_refuse_all_callers` (advance parameter ids)

**Red** — NOT RED — whole function, EXIT=1, `5 failed, 35 passed in 80.14s`. Five `[advance-*]` cases (`null`, `list`, `number`, `string`, `invalid-utf8`) failed on wrong axis (`driver-internal-exception`); three `[advance-unparseable]`, `[advance-fault-marker]`, `[advance-bad-relocated-roots]` stayed green because the sweep-site indeterminate guard (G14b, still intact during this proof) refuses the same call on the indeterminate axis first.

**Restore.** Inverse edit. **Restore receipt:** `git diff --quiet -- plugins/superheroes/lib/round_driver.py; echo $?` → `0`.

**Green** (EXIT=0): `40 passed in 87.58s`.

## G16 — `re-emit`, indeterminate check

**Guarded element.** `plugins/superheroes/lib/round_driver.py`, `re-emit`, `if relocation is _RELOCATION_EVIDENCE_INDETERMINATE:`. **Axis:** indeterminate relocation evidence refuses re-emit as indeterminate.

**Neutralization:** `if relocation is _RELOCATION_EVIDENCE_INDETERMINATE:` → `if False:` (lookup line kept)

**Detector.** `plugins/superheroes/lib/tests/test_round_driver_re_emit.py::test_relocation_evidence_faults_refuse_all_callers` (re-emit parameter ids)

**Red** — NOT RED — whole function, EXIT=1, `8 failed, 32 passed in 88.50s`. All eight `[re-emit-*]` cases failed off-axis: four raised `AttributeError` in `_re_emit_recorded_slots` on corrupted journal entries, one raised `UnicodeDecodeError`, three asserted `re-emit-attempt-has-results` instead of `relocation-evidence-indeterminate`; none exercised the indeterminate refusal this element guards.

**Restore.** Inverse edit. **Restore receipt:** `git diff --quiet -- plugins/superheroes/lib/round_driver.py; echo $?` → `0`.

**Green** (EXIT=0): `40 passed in 76.91s`.

## G17a — `validate_landing`, fenced refusal

**Guarded element.** `plugins/superheroes/lib/round_records.py`, `validate_landing`, `if fenced and not evidence_minted:`. **Axis:** a landing for an attempt emitted before relocation is refused.

**Neutralization:** `if fenced and not evidence_minted:` → `if False:`

**Detector.** `plugins/superheroes/lib/tests/test_round_driver_re_emit.py::test_relocation_fence_hand_record_refused_after_relocate`

**Red** (EXIT=1):

```
>       assert out["ok"] is False
E       assert True is False
FAILED plugins/superheroes/lib/tests/test_round_driver_re_emit.py::test_relocation_fence_hand_record_refused_after_relocate
1 failed in 2.32s
```

**Restore.** Inverse edit. **Restore receipt:** `git diff --quiet -- plugins/superheroes/lib/round_records.py; echo $?` → `0`.

**Green** (EXIT=0): `1 passed in 2.31s`.

## G17b — `validate_landing`, runner-evidence exemption

**Guarded element.** `plugins/superheroes/lib/round_records.py`, `validate_landing`, `if fenced and not evidence_minted:` (runner-evidence exemption half). **Axis:** a result whose runner evidence minted it is not fenced.

**Neutralization:** `if fenced and not evidence_minted:` → `if fenced:`

**Detector.** `plugins/superheroes/lib/tests/test_round_driver_re_emit.py::test_runner_view_record_not_fenced_after_relocate`

**Red** (EXIT=1):

```
>       assert out["ok"] is True, out
E       AssertionError: {'detail': '...', 'ok': False, 'reason': 'record-attempt-predates-relocation', ...}
E       assert False is True
FAILED plugins/superheroes/lib/tests/test_round_driver_re_emit.py::test_runner_view_record_not_fenced_after_relocate
1 failed in 2.38s
```

**Restore.** Inverse edit. **Restore receipt:** `git diff --quiet -- plugins/superheroes/lib/round_records.py; echo $?` → `0`.

**Green** (EXIT=0): `1 passed in 2.32s`.



---

## Orchestrator re-run and dispositions (authoritative)

The workhorse orchestrator ran these in the detached probe tree `issue-1272-2ib-r3-probe` at `0506c2fc`. Each red below was taken with only that element's neutralization in the tree; the tree held nothing else. After the last restore:
- `git status --porcelain` printed nothing.
- `git diff --quiet` printed `0`.
- **Green:** the whole `test_round_driver_re_emit.py` gave `79 passed in 44.95s`, EXIT=0. An identical baseline was taken before the first neutralization (`79 passed in 40.16s`, EXIT=0).

Where a row lists two node ids, both were run in one invocation.

| element | detector (orchestrator run) | red — decisive line | disposition |
|---|---|---|---|
| G1 | `test_landing_entry_present_lstat_outcomes` | `E AssertionError: assert False is True` · `1 failed` | proven |
| G2a | `test_certification_late_attempt0_landing_keeps_seat_open` | `[envelope-file]` `E assert 0 == 1` · `1 failed, 2 passed` | proven |
| G2b | same | `[bare-file]`, `[bare-dangling_symlink]` `E assert 0 == 1` · `2 failed, 1 passed` | proven |
| G2c | `test_certification_legacy_emitted_row_stays_open_without_session_dir` | `E AssertionError: assert ('dispatch-panel', 1, 0, 'code-reviewer', 0) in []` | proven |
| G3a | `test_re_emit_refusal_tokens[re-emit-attempt-has-results-results_landing]` | `E assert 0 == 1` (re-emit exited 0) | proven |
| G3b | `test_re_emit_refusal_tokens[re-emit-attempt-has-results-results_bare]` | `E assert 0 == 1` (re-emit exited 0) | proven |
| G4 | `test_re_emit_positive_after_relocate` | `assert state["pending"]["attempt"] == 1` → `E assert 0 == 1` | **proven — implementer's NOT RED overturned.** With nothing accepted, `_next_dispatch_attempt` returns 0 (no accepted submit, no matching `lastAccepted`), so the floor binds. The implementer's recorded run showed `1 passed, 1 error` (the error was the source-guard teardown), which does not match this neutralization at this head; it is not relied on. |
| G5 | faults `[record-result-unparseable]`, `[advance-unparseable]`, `[re-emit-unparseable]` | `- relocation-evidence-indeterminate / + record-attempt-predates-relocation` (×2), `+ re-emit-attempt-has-results` | proven |
| G6 | faults `[record-result-invalid-utf8]`, `[hand-submit-invalid-utf8]` | `UnicodeDecodeError …`; `+ state-hash mismatch …` · `2 failed` | proven |
| G7 | faults `[record-result-unparseable]`, `[record-sweep-invalid-utf8]` | `+ record-attempt-predates-relocation`; `E assert True is False` · `2 failed` | proven |
| G8a | faults `[record-result-null]`, `[record-result-list]` | alone: `2 passed` (EXIT=0) | **redundant pair — see below** |
| G8b | faults `[record-result-null]` + `test_relocation_after_emission_predicate` | alone: `2 passed` (EXIT=0) | **redundant pair — see below** |
| G8a+G8b | faults `[record-result-null]`, `[record-result-list]`, both neutralized together | `- relocation-evidence-indeterminate / + record-attempt-predates-relocation` · `2 failed` | the pair is proven |
| G8c | — (not re-run) | implementer: `1 passed` | **unreachable as placed — see below** |
| G9 | faults `[record-result-bad-relocated-roots]`, `[re-emit-bad-relocated-roots]` | `E assert True is False`; `+ re-emit-not-stale` · `2 failed` | proven |
| G10 | `test_relocation_after_emission_predicate` | `E AssertionError: assert None == {… 'outcome': 'relocated'}` · `1 failed` | proven |
| G11 | faults `[record-result-fault-marker]`, `[hand-submit-fault-marker]` | `+ record-attempt-predates-relocation` (×2) · `2 failed` | proven |
| G12a | `test_relocation_fence_hand_submit_refused_after_relocate` | `+ state-hash mismatch — the state moved under a stale submit` | proven |
| G12b | faults `[hand-submit-null]`, `[hand-submit-fault-marker]` | `+ record-attempt-predates-relocation` (×2) | proven |
| G12c | `test_relocation_fence_advance_folds_seats_recorded_before_relocate` | `E assert not True` | proven |
| G13a | `test_relocation_fence_hand_record_refused_after_relocate` | `E assert True is False` | proven |
| G13b | faults `[record-result-null]`, `[record-result-fault-marker]` | `+ record-attempt-predates-relocation` (×2) | **proven — implementer's NOT RED overturned.** The detector asserts the indeterminate refusal token. Getting the predates token instead is a red on this element's axis ("refuses … *as indeterminate*"), not off it. |
| G14a | `test_relocation_fence_sweep_refuses_unclaimed_attempt0_landing` | `E assert True is False` · `1 failed` (the advance variant passed: `advance` stays fenced through the chokepoint) | proven |
| G14b | faults `[record-sweep-null]`, `[record-sweep-fault-marker]` | `+ record-attempt-predates-relocation` (×2) | **proven — implementer's NOT RED overturned** (same reading as G13b) |
| G15 | faults `[advance-null]`, `[advance-fault-marker]` | `[advance-null]`: `+ driver-internal-exception` · `1 failed, 1 passed` | **proven — implementer's NOT RED overturned.** Without this check, a non-object row crashes `advance` rather than refusing it; the fault-marker case is still answered by G14b. |
| G16 | faults `[re-emit-fault-marker]`, `[re-emit-null]` | `+ re-emit-attempt-has-results`; `AttributeError: 'NoneType' object has no attribute 'get'` · `2 failed` | **proven — implementer's NOT RED overturned** (a wrong refusal, or a crash, instead of the indeterminate refusal) |
| G17a | `test_relocation_fence_hand_record_refused_after_relocate` | `E assert True is False` · `1 failed, 1 passed` | proven |
| G17b | `test_runner_view_record_not_fenced_after_relocate` | `E AssertionError: {… 'reason': 'record-attempt-predates-relocation' …}` | proven |

**Disclosures (per `rubric/bite-proof.md` § When the proof cannot be produced).**

- **G8a / G8b — redundant as placed.** Both guards bite on the same condition: a non-object journal row. `_relocation_lookup` pre-scans for it, and `_relocation_after_emission`'s first loop checks for it again. Every production caller reaches the second guard through the first. Neutralizing either one alone stays green, because the other answers first. Neutralizing both goes red on every caller parameter tried.
  - **Construction bound:** each guard's individual protection is unverified. The pair's protection is verified.
  - **What would make each provable alone:** delete one copy. That is a product change, which this lane may not make, so it is left as a follow-up.
- **G8c — unreachable as placed.** `_relocation_after_emission`'s first loop scans the whole journal and returns indeterminate on any non-object row. The second loop's identical check therefore never sees one. The proof that does bite for this condition is the G8a+G8b joint row above. This is dead code, and a candidate for removal in the same follow-up.

**Receipt integrity.** The implementer part files above are kept verbatim as their authors' records. Where they say NOT RED, the table above supersedes them.
