# C13 layer 2c (#1272) bite-proof — disposition ledger is the one owner

**Provenance:** cherry-picks `35d4f485` + `684c6996` onto head `af9ed8f2`, plus layer-2d carry
adaptation `_backfill_fixed_disposition_verify_receipts` (audits-before-verify ordering). Neutralize
through a targeted edit of the quoted production text; restore by exact inverse (never `git checkout`).
Command prefix for every run:

```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc
```

## BP-2c-a — E4 unresolvable `mergedInto` refuses (not graded undisposed)

**Guarded element.** `round_certification.check_disposition_without_receipt`, the
`if _resolve_merged_into_entry(finding, by_key) is None:` refusal at the `mergedInto` resolution arm.
**Axis.** A broken merge chain must refuse `disposition-without-receipt`, not fall through to grade
the member as undisposed.
**Detector.** `test_L2_merged_away_member_resolves_through_representative` (second half).

**Neutralization.**

```python
        if finding.get(session_contract.MERGED_INTO_FIELD):
            if _resolve_merged_into_entry(finding, by_key) is None:
```
→
```python
        if finding.get(session_contract.MERGED_INTO_FIELD):
            if False:
```

**Raw red** (exit 1):

```
        refusal = RC.check_disposition_without_receipt(ctx)
        assert refusal is not None
        assert refusal["class"] == "disposition-without-receipt"
>       assert refusal["detail"] == "merged-into chain does not resolve", refusal
E       AssertionError: {'artifact': 'root b', 'bindingFailure': None, 'class': 'disposition-without-receipt', 'detail': 'finding has no disposition recorded'}
E         - merged-into chain does not resolve
E         + finding has no disposition recorded
FAILED plugins/superheroes/lib/tests/test_disposition_ledger_1272.py::test_L2_merged_away_member_resolves_through_representative
1 failed in 0.36s
```

**Restore.** Exact inverse (`if False:` → `if _resolve_merged_into_entry(finding, by_key) is None:`).

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 0.35s
```

**History (2026-09-20, C13 layer 2f).** The inherited record quoted `if resolved is None:` →
`if False:` in `_effective_certification_finding`; at this head that neutralization is vacuous because
the detector's assertion is reached through the earlier `mergedInto` arm above — corrected here in
place rather than in a separate note.

## BP-2c-b — E2 disposition-family strip at seeding

**Guarded element.** `round_driver._strip_disposition_family` / the `else: entry = _strip_disposition_family(entry)` arm in `_stage_findings`.
**Axis.** A self-declared disposition on a compiled candidate is stripped at seeding; only an existing ledger entry's disposition survives.
**Detector.** `test_L2_stage_findings_strips_seat_supplied_disposition_family`.

**Neutralization.** `_strip_disposition_family` body → `return dict(entry)` (skip strip).

**Raw red** (exit 1):

```
AssertionError: {'file': 'a.py', 'line': 1, 'title': 'bug', 'severity': 'Important', 'disposition': 'fixed', ...}
```

**Restore.** reinstate the `for field in _DISPOSITION_FAMILY_FIELDS: copy.pop(field, None)` loop.

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 0.14s
```

## BP-2c-c — E3 archive every departure through `_set_findings`

**Guarded element.** `round_driver._archive_departures`, invoked from `_set_findings` when a keyed finding leaves the live list.
**Axis.** Departures through the chokepoint are archived whether or not they carry a disposition.
**Detector.** `test_L7_archive_departure_without_prior_staging`.

**Neutralization.** Insert `return` immediately after the `_archive_departures` docstring (no-op the archiver).

**Raw red** (exit 1):

```
AssertionError: departed finding not archived to ledger
```

**Restore.** remove the inserted `return`.

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 0.14s
```

## BP-2c-d — flipped seam test certifying assertion

**Guarded element.** `round_driver._fold_audits` discharge loop that calls `_record_disposition` for discharged targets.
**Axis.** A converged loop with a raised finding records `fixed` on the ledger with a verify receipt.
**Detector.** `test_real_loop_with_finding_refuses_disposition_without_receipt_until_loop_records_dispositions`.

**Neutralization.** `for tid in outcome.get("discharged") or []:` → `for tid in ():`.

**Raw red** (exit 1):

```
>       assert entry["disposition"] == "fixed"
E       KeyError: 'disposition'
FAILED ...test_real_loop_with_finding_refuses_disposition_without_receipt_until_loop_records_dispositions
1 failed in 3.47s
```

**Restore.** `for tid in ():` → `for tid in outcome.get("discharged") or []:`.

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 3.46s
```

## BP-2c-e — C13 head-equality on prior-round verify carry

**Guarded element.** `round_driver._verify_result_for_disposition`, the `prior_head == bound_head`
check before returning a prior round's `verifyResult`.
**Axis.** A prior round's pass is carried onto a fixed receipt only when that round's recorded
`fixFoldHead` matches the head the receipt binds.
**Detector.** `test_C13_two_round_moving_head_verify_never_passes_refuses`.

**Neutralization.** Drop the head-equality gate — return `val` whenever a prior round has any
`verifyResult`:

```python
        val = prior_rec.get("verifyResult")
        if val is not None:
            return val
```

**Raw red** (exit 1):

```
FAILED plugins/superheroes/lib/tests/test_disposition_ledger_1272.py::test_C13_two_round_moving_head_verify_never_passes_refuses
...
>       assert receipt2.get("verifyResult") is None
E       AssertionError: assert 'pass' is None
E        +  where 'pass' = {'headSha': 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb', 'verifyResult': 'pass'}.get
1 failed in 0.16s
```

**Restore.** Reinstate the `fixFoldHead` presence and `prior_head == bound_head` guard.

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 0.17s
```

## BP-2c-f — C13 `fixFoldHead` round recording at fix fold

**Guarded element.** `round_driver._fold_fixer`, `_record_round(state, "fixFoldHead", head)` on the
successful `_resolve_fix_fold_head_sha` branch.
**Axis.** Each fix fold records the resolved head on the round record so later disposition receipts
can match prior verify verdicts head-for-head.
**Detector.** `test_C13_fix_fold_records_fix_fold_head`.

**Neutralization.** Remove the `_record_round(state, "fixFoldHead", head)` line (leave
`_record_fix_content_on_findings` and blob persistence intact).

**Raw red** (exit 1):

```
FAILED plugins/superheroes/lib/tests/test_disposition_ledger_1272.py::test_C13_fix_fold_records_fix_fold_head
...
>       assert state["rounds"]["2"]["fixFoldHead"] == head
E       KeyError: 'fixFoldHead'
1 failed in 0.16s
```

**Restore.** Reinstate `_record_round(state, "fixFoldHead", head)` before
`_record_fix_content_on_findings`.

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 0.15s
```

## BP-2c-g — dispositionRound guard on disposition-family carry

**Guarded element.** `round_driver._stage_findings` and `_archive_departures`, the
`_DISPOSITION_FAMILY_FIELDS` carry guarded by `existing.get("dispositionRound") == round_no`
(staging) and `prior.get("dispositionRound") == raised_round` (archive).
**Axis.** A finding re-raised in a later round must not inherit an earlier round's disposition
family; only a same-round re-stage may carry it forward.
**Detector.** `test_L2_restaged_finding_strips_prior_round_disposition` and
`test_L2_same_round_restage_keeps_disposition`.

**Neutralization.** Drop the `dispositionRound` equality guard in `_stage_findings` (restore the
pre-guard `existing.get("disposition") is not None` test only).

**Raw red** (exit 1):

```
FAILED plugins/superheroes/lib/tests/test_disposition_ledger_1272.py::test_L2_restaged_finding_strips_prior_round_disposition
...
>       assert "disposition" not in entry
E       AssertionError: assert 'disposition' not in {'disposition': 'fixed', ...}
1 failed in 0.16s
```

**Restore.** Reinstate the `dispositionRound == round_no` guard in `_stage_findings` and the
matching guard in `_archive_departures`.

**Raw green** (exit 0):

```
..                                                                       [100%]
2 passed in 0.17s
```

---

# Round-5 additions and the orchestrator's re-run at the final head

**Provenance (this section only):** every proof below was run by the **orchestrator**, not by an
implementer dispatch, in a dedicated detached probe worktree
(`issue-1272-r5-probe`) cut at the final head **`8128ca43`** — never in a tree a live seat was
reading. Each neutralization is a targeted revertible edit through the host's edit action; each
restore is its exact inverse (never `git checkout` / `git restore`). The probe worktree was
confirmed **byte-clean** (`git status --porcelain` empty) after the last restore, and the closing
run over the whole detector file plus the byte-pin detector was green: `31 passed in 0.30s`, exit 0.

Command prefix for every run in this section:

```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-probe
```

## BP-2c-h — the backfill merges a pre-existing key rather than skipping it

**Guarded element.** `round_driver._backfill_ledger_from_records` — the absence of a
`if key in preexisting: continue` short-circuit, so a pre-existing key's **non-disposition** fields
take the newest `_records` value.
**Axis.** A finding recorded `Critical` in `_records` must reach the ledger as `Critical`, so the
`"Critical finding may not take out-of-scope disposition"` gate can fire. A stale `Minor` frozen by a
skip turns a refusal into a certification — a fail-direction inversion.
**Detector.** `test_C13_backfill_merges_record_severity_preserves_disposition_family`.

**Neutralization.** Reinstate the skip — replace

```python
            entry = _strip_disposition_family(dict(finding))
            if key in preexisting:
                entry.update(family_snapshots.get(key, {}))
```

with

```python
            if key in preexisting:
                continue
            entry = _strip_disposition_family(dict(finding))
```

**Raw red** (exit 1):

```
.F                                                                       [100%]
____ test_C13_backfill_merges_record_severity_preserves_disposition_family _____
        state["_records"] = [{"findings": [record_finding]}]
        RD._stage_findings(state, compiled)
        ledger = _ledger_by_key(state)
        entry = ledger[key]
>       assert entry["severity"] == "Critical"
E       AssertionError: assert 'Minor' == 'Critical'
E         - Critical
E         + Minor
FAILED plugins/superheroes/lib/tests/test_disposition_ledger_1272.py::test_C13_backfill_merges_record_severity_preserves_disposition_family
1 failed, 1 passed in 0.35s
```

**Restore.** Exact inverse of the edit above.

**Raw green** (exit 0): `1 failed, 2 passed in 0.36s` — this element's detector is among the **2
passed**; the single failure in that run is BP-2c-i's own red, which was neutralized at the time.
Confirmed again unconditionally in the closing whole-file run: `31 passed in 0.30s`, exit 0.

## BP-2c-h2 — the merge preserves the pre-existing disposition family rather than overwriting it

**Guarded element.** `round_driver._backfill_ledger_from_records` — the
`entry.update(family_snapshots.get(key, {}))` re-application of the snapshotted disposition family.
**Axis.** The *other* direction of the same merge rule: a legacy ledger entry's durable disposition
must survive first ledger-owner activation. Without it the merge becomes the overwrite that finding
R3-2 closed.
**Detector.** `test_C13_backfill_preserves_preexisting_ledger_disposition`.

**Neutralization.** Delete the two-line family re-application (`if key in preexisting:` /
`entry.update(family_snapshots.get(key, {}))`), leaving the snapshot built and unused.

**Raw red** (exit 1):

```
F                                                                        [100%]
__________ test_C13_backfill_preserves_preexisting_ledger_disposition __________
        state["dispositionLedger"] = [preexisting_entry]
        state["_records"] = [{"findings": [record_finding]}]
        RD._stage_findings(state, compiled)
        ledger = _ledger_by_key(state)
>       assert ledger[key]["disposition"] == "refuted"
E       KeyError: 'disposition'
FAILED plugins/superheroes/lib/tests/test_disposition_ledger_1272.py::test_C13_backfill_preserves_preexisting_ledger_disposition
1 failed in 0.34s
```

**Restore.** Reinstate the two deleted lines.

**Raw green** (exit 0): among the **2 passed** of `1 failed, 2 passed in 0.36s`, and again in the
closing whole-file run.

**Why both halves are proved.** One neutralization per direction. BP-2c-h proves the skip cannot
return; BP-2c-h2 proves the overwrite cannot return. A single proof would have left the merge rule
half-guarded, which is exactly how this surface produced a new defect in four consecutive rounds.

## BP-2c-i — an out-of-scope disposition with no recorded reason refuses

**Guarded element.** `round_certification.check_disposition_without_receipt`, the
`outOfScopeReason` refusal in the `out-of-scope` branch, placed **before** the follow-up checks.
**Axis.** `"reason": null` must not reach a certified Important disclosure by any door; the field
validated is the same field the disclosure later writes.
**Detector.** `test_C13_out_of_scope_reason_required_before_follow_up_checks`.

**Neutralization.** Delete the refusal block:

```python
            reason = graded.get("outOfScopeReason")
            if not isinstance(reason, str) or not reason.strip():
                return _refusal(
                    "disposition-without-receipt",
                    fid,
                    "out-of-scope disposition lacks recorded reason",
                )
```

**Raw red** (exit 1):

```
..F                                                                      [100%]
________ test_C13_out_of_scope_reason_required_before_follow_up_checks _________
        state["findings"] = [dict(base)]
        ctx = _ctx(state, tmp_path)
        refusal = RC.check_disposition_without_receipt(ctx)
>       assert refusal is not None
E       assert None is not None
FAILED plugins/superheroes/lib/tests/test_disposition_ledger_1272.py::test_C13_out_of_scope_reason_required_before_follow_up_checks
1 failed, 2 passed in 0.36s
```

**Restore.** Reinstate the refusal block verbatim, above `follow_up = _out_of_scope_follow_up(graded)`.

**Raw green** (exit 0):

```
.F                                                                       [100%]
1 failed, 1 passed in 0.39s
```

— this element's detector is the **1 passed**; the failure in that run is CENSUS-J's own red,
neutralized at the time. Confirmed unconditionally in the closing whole-file run.

## Re-run of the inherited proofs at the final head `8128ca43`

Every red half below was **re-established by the orchestrator at this head** — none of these is an
implementer's or fixer's inherited claim.

| ID | Detector | Red re-run at `8128ca43` | Green on restore |
|---|---|---|---|
| **BP-2c-a** | `test_L2_merged_away_member_resolves_through_representative` | **yes**, exit 1 | yes |
| **BP-2c-b** | `test_L2_stage_findings_strips_seat_supplied_disposition_family` | **yes**, exit 1 | yes |
| **BP-2c-c** | `test_L7_archive_departure_without_prior_staging` | **yes**, exit 1 | yes |
| **BP-2c-d** | `test_real_loop_with_finding_refuses_disposition_without_receipt_until_loop_records_dispositions` | **yes**, exit 1 | yes |
| **BP-2c-g** | `test_L2_restaged_finding_strips_prior_round_disposition` | **yes**, exit 1 | yes |
| BP-2c-e | `test_C13_two_round_moving_head_verify_never_passes_refuses` | proved at `0451579e`; guarded code untouched since | — |
| BP-2c-f | `test_C13_fix_fold_records_fix_fold_head` | proved at `0451579e`; guarded code untouched since | — |

### The other reds, quoted

**BP-2c-b** (`_strip_disposition_family` → `return dict(entry)`), exit 1:

```
>       assert "disposition" not in entry
E       AssertionError: assert 'disposition' not in {'classification': 'mechanical', 'disposition': 'fixed', 'dispositionReceipt': {'headSha': 'zzzz…'}, 'file': 'a.py', ...}
1 failed, 1 passed in 0.29s
```

**BP-2c-c** (`return` inserted after the `_archive_departures` docstring), exit 1:

```
        RD._set_findings(state, [])
>       assert key in _ledger_by_key(state)
E       AssertionError: assert 'a.py::bug@L1' in {}
1 failed, 1 passed in 0.30s
```

**BP-2c-d** (`for tid in outcome.get("discharged") or []:` → `for tid in ():`), exit 1:

```
        entry = ledger[key]
>       assert entry["disposition"] == "fixed"
E       KeyError: 'disposition'
1 failed, 1 passed in 8.66s
```

**BP-2c-g** (drop the `dispositionRound` equality guard in `_stage_findings`), exit 1:

```
        assert entry["raisedRound"] == 3
>       assert "disposition" not in entry
E       AssertionError: assert 'disposition' not in {'classification': 'mechanical', 'disposition': 'fixed', 'dispositionReceipt': {'headSha': 'bbbb…'}, 'dispositionRound': 2, ...}
1 failed, 2 passed in 8.67s
```
