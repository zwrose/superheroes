# WO-1 (#2445) open-at-end repeats bite-proof

Detector: `plugins/superheroes/lib/tests/test_open_at_end_repeats_2445.py` (45 tests). Eight guarded elements, B1 to B8,
declared by the order. One neutralization, one red and one green per element, each by a targeted edit undone by the
inverse edit, detector unedited (one test, `test_f_a_record_built_from_a_marked_finding_an_owner_ruling_cites_is_written_without_the_marker`,
was added after B1 to B5 had run, to cover B6's call site; B1 to B5 are additive-unaffected, B6 was re-run with it, and
the B8 green run is the whole 45-test file). Every run used this command from the worktree root:

```
scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-2445 -m pytest plugins/superheroes/lib/tests/test_open_at_end_repeats_2445.py -q -p no:cacheprovider
```

Redaction: none needed; the captures hold no secrets, tokens or private URLs. The `UV_NATIVE_TLS` warning line is
omitted from the captures below. Each red capture keeps the progress line, the `FAILED` lines and the count line as
printed; the per-test traceback bodies between them are dropped (the failing test ids and the decisive assertion are named
in the line after each capture).

Restore receipt shape: each neutralized file also carries this order's other uncommitted changes, so `git status
--porcelain` reads ` M` before and after and cannot show the restore. The receipt is the restored lines quoted back from
the file, plus a green run of the whole detector.

## B1 — `repeat_marks.decision_outcome` reads the marker

**Guarded element:** `plugins/superheroes/lib/repeat_marks.py:55`, `decision_outcome`. Axis: an entry marked
`openAtLoopEnd` exactly `True` reads as open (None) to the decision table, whatever its pooled `outcome`.

**Neutralization:** `if session_contract.open_at_loop_end(entry):` became
`if False and session_contract.open_at_loop_end(entry):` (the function returns `entry.get("outcome")` unconditionally).

**Raw red** (6 failed, 38 passed):

```
.FF.............FFF.......F.................                             [100%]
FAILED ...::test_b_c_a_repeat_of_a_record_finding_left_open_at_loop_end_is_new_without_changing_the_pooled_outcome[judge]
FAILED ...::test_b_c_a_repeat_of_a_record_finding_left_open_at_loop_end_is_new_without_changing_the_pooled_outcome[exact]
FAILED ...::test_d_the_one_reader_is_an_identity_check_on_true
FAILED ...::test_e_a_row_settled_open_when_the_loop_ended_carries_the_marker_and_its_repeat_is_new[judge]
FAILED ...::test_e_a_row_settled_open_when_the_loop_ended_carries_the_marker_and_its_repeat_is_new[exact]
FAILED ...::test_e_a_merged_member_reads_its_representatives_marker
6 failed, 38 passed in 2.75s
```

Decisive assertions: `assert (True, None) == (False, None)` (a repeat kept instead of new) in the b/c tests, and
`'left-for-owner' != None` for `decision_outcome` in the d and e tests. (The `...::` prefix stands for
`plugins/superheroes/lib/tests/test_open_at_end_repeats_2445.py`; the same shortening is used below.)

**Restore:** inverse edit, removed `False and `.

**Restore receipt:** restored lines, `repeat_marks.py:55-56`:

```python
    if session_contract.open_at_loop_end(entry):
        return None
```

**Raw green:**

```
............................................                             [100%]
44 passed in 2.89s
```

## B2 — `record_entry` copies the marker

**Guarded element:** `plugins/superheroes/lib/repeat_marks.py:172`, `record_entry`. Axis: a record finding that is
`left-for-owner`, cites no decision and carries the marker exactly `True` is pooled with `openAtLoopEnd: True`
(its `outcome` stays `left-for-owner`).

**Neutralization:** `... if _open_at_end(finding, outcome) else {}` became `... if False and _open_at_end(finding, outcome) else {}`.

**Raw red** (2 failed, 42 passed):

```
.FF.........................................                             [100%]
FAILED ...::test_b_c_a_repeat_of_a_record_finding_left_open_at_loop_end_is_new_without_changing_the_pooled_outcome[judge]
FAILED ...::test_b_c_a_repeat_of_a_record_finding_left_open_at_loop_end_is_new_without_changing_the_pooled_outcome[exact]
2 failed, 42 passed in 2.87s
```

Decisive assertion: `KeyError: 'openAtLoopEnd'` reading the pooled entry (`pool[0][MARK]`).

**Restore:** inverse edit, removed `False and `.

**Restore receipt:** restored line, `repeat_marks.py:172`:

```python
    marked = {session_contract.OPEN_AT_LOOP_END_FIELD: True} if _open_at_end(finding, outcome) else {}
```

**Raw green:**

```
............................................                             [100%]
44 passed in 2.75s
```

## B3 — `session_entry` copies the marker from the representative

**Guarded element:** `plugins/superheroes/lib/repeat_marks.py:148-149`, `session_entry`. Axis: the pool entry of a
ledger row carries the marker of the row the decision stands on (`rep`, so a merged member reads its
representative's), only for a `left-for-owner` outcome and a `rep` with no `repeatKept`.

**Neutralization:** `if isinstance(rep, dict) and "repeatKept" not in rep and ...` became
`if False and isinstance(rep, dict) and "repeatKept" not in rep and ...`.

**Raw red** (4 failed, 40 passed):

```
.................FF.......F.F...............                             [100%]
FAILED ...::test_e_a_row_settled_open_when_the_loop_ended_carries_the_marker_and_its_repeat_is_new[judge]
FAILED ...::test_e_a_row_settled_open_when_the_loop_ended_carries_the_marker_and_its_repeat_is_new[exact]
FAILED ...::test_e_a_merged_member_reads_its_representatives_marker
FAILED ...::test_e_session_entry_reads_the_marker_only_from_a_bare_left_for_owner_row_that_is_not_a_kept_repeat
4 failed, 40 passed in 2.94s
```

Decisive assertions: `KeyError: 'openAtLoopEnd'` on the entry, and `{'Rep': None, 'Member': None} != {'Rep': True, 'Member': True}`.

**Restore:** inverse edit, removed `False and `.

**Restore receipt:** restored lines, `repeat_marks.py:148-149`:

```python
    marked = {session_contract.OPEN_AT_LOOP_END_FIELD: True} \
        if isinstance(rep, dict) and "repeatKept" not in rep and _open_at_end(rep, outcome) else {}
```

**Raw green:**

```
............................................                             [100%]
44 passed in 2.66s
```

## B4 — `_settle_open_findings` passes `open_at_end` and writes the marker on the ledger

**Guarded element:** `plugins/superheroes/lib/round_driver.py:3187-3190` (the `open_at_end=` argument of
`finding_outcomes.settle`), with the write at `round_driver.py:3202-3203`. Axis: a finding settled `left-for-owner`
only because it was still open carries the marker on its ledger row; an out-of-scope deferral the branch settled and a
pending ruling never do; a bound decision that overrode the skip marks unless it cites one; the ungraded reason swap
changes neither.

**Neutralization:** `open_at_end=not deferred_out_of_scope and pending is None)` became `open_at_end=False)`.

**Raw red** (7 failed, 37 passed):

```
.................FF..F..F.FF..............F.                             [100%]
FAILED ...::test_e_a_row_settled_open_when_the_loop_ended_carries_the_marker_and_its_repeat_is_new[judge]
FAILED ...::test_e_a_row_settled_open_when_the_loop_ended_carries_the_marker_and_its_repeat_is_new[exact]
FAILED ...::test_e_an_out_of_scope_row_a_newer_bound_decision_overrode_is_marked_unless_that_decision_cites_one[uncited]
FAILED ...::test_e_the_ungraded_sweep_reason_swap_never_adds_or_removes_the_marker[open]
FAILED ...::test_e_a_merged_member_reads_its_representatives_marker
FAILED ...::test_e_a_newer_disposition_replaces_the_settle_and_the_marker_with_it
FAILED ...::test_g_re_raising_a_row_settled_open_at_loop_end_keeps_its_real_consequence
7 failed, 37 passed in 2.68s
```

Decisive assertion: `KeyError: 'openAtLoopEnd'` on the settled ledger row.

**Restore:** inverse edit, `open_at_end=False)` back to the expression.

**Restore receipt:** restored line, `round_driver.py:3190`:

```python
            open_at_end=not deferred_out_of_scope and pending is None)
```

**Raw green:**

```
............................................                             [100%]
44 passed in 2.82s
```

## B5 — the validator check on `openAtLoopEnd`

**Guarded element:** `plugins/superheroes/lib/review_record.py:884-886`, account validation of `findings[i]`.
Axis: the marker, when present, is exactly `True`, on a `left-for-owner` finding with no `decidedBy`; the refusal
names `findings[i].openAtLoopEnd`.

**Neutralization:** `chk(session_contract.OPEN_AT_LOOP_END_FIELD not in f or (` became
`chk(True or session_contract.OPEN_AT_LOOP_END_FIELD not in f or (`.

**Raw red** (5 failed, 39 passed):

```
...................................FFFFF....                             [100%]
FAILED ...::test_f_the_validator_refuses_a_marker_that_is_not_true_or_sits_on_another_outcome_or_beside_a_decision[{'openAtLoopEnd': 'yes'}]
FAILED ...::test_f_the_validator_refuses_a_marker_that_is_not_true_or_sits_on_another_outcome_or_beside_a_decision[{'openAtLoopEnd': 1}]
FAILED ...::test_f_the_validator_refuses_a_marker_that_is_not_true_or_sits_on_another_outcome_or_beside_a_decision[{'openAtLoopEnd': None}]
FAILED ...::test_f_the_validator_refuses_a_marker_that_is_not_true_or_sits_on_another_outcome_or_beside_a_decision[{'openAtLoopEnd': True, 'outcome': 'fixed', 'reason': 'fixed in 1a2b3c4'}]
FAILED ...::test_f_the_validator_refuses_a_marker_that_is_not_true_or_sits_on_another_outcome_or_beside_a_decision[{'openAtLoopEnd': True, 'decidedBy': {'kind': 'canon', 'ref': '2026-01-02-abcd1234-1'}}]
5 failed, 39 passed in 2.83s
```

Decisive assertion: `KeyError: 'reason'` (the write succeeded, so no refusal object came back).

**Restore:** inverse edit, removed `True or `.

**Restore receipt:** restored lines, `review_record.py:884-886`:

```python
        chk(session_contract.OPEN_AT_LOOP_END_FIELD not in f or (
            f[session_contract.OPEN_AT_LOOP_END_FIELD] is True and f.get("outcome") == _LEFT_FOR_OWNER
            and decided_by is None), f"findings[{i}].{session_contract.OPEN_AT_LOOP_END_FIELD}")
```

**Raw green:**

```
............................................                             [100%]
44 passed in 2.65s
```

## B6 — the normalisation pass after `_recheck_carried`

**Guarded element:** `plugins/superheroes/lib/review_record.py:1754-1757`, `_drop_stale_open_marker`, called in
`build_record` between `_recheck_carried` and the `sheetPart` line. Axis: a finding whose outcome is not
`left-for-owner`, or whose `decidedBy` is set, leaves the writer without the marker.

**Neutralization:** `stale = (session_contract.OPEN_AT_LOOP_END_FIELD in f` became
`stale = (False and session_contract.OPEN_AT_LOOP_END_FIELD in f`. Run after the pipeline test was added.

**Raw red** (2 failed, 43 passed; an earlier red, before the pipeline test existed, was 1 failed, 43 passed, the
unit test alone):

```
.........................................FF..                            [100%]
FAILED ...::test_f_the_normalisation_pass_drops_the_marker_a_carried_recheck_or_an_owner_ruling_made_stale
FAILED ...::test_f_a_record_built_from_a_marked_finding_an_owner_ruling_cites_is_written_without_the_marker
2 failed, 43 passed in 2.84s
```

Decisive assertions: `'openAtLoopEnd' not in {... 'decidedBy' ...}` on the pass's output, and the same on the record
`build_record` returns for a marked finding an owner ruling cites.

**Restore:** inverse edit, removed `False and `.

**Restore receipt:** restored lines, `review_record.py:1755-1757`:

```python
        stale = (session_contract.OPEN_AT_LOOP_END_FIELD in f
                 and (f.get("outcome") != _LEFT_FOR_OWNER or f.get("decidedBy") is not None))
        out.append({k: v for k, v in f.items() if k != session_contract.OPEN_AT_LOOP_END_FIELD} if stale else f)
```

**Raw green:**

```
.............................................                            [100%]
45 passed in 2.57s
```

Not proven: the carried-recheck half of the pass (`_recheck_carried` moving a marked finding to `fixed`) is proven only
at the pass function (`test_f_the_normalisation_pass_...`, which runs `_recheck_carried` then the pass); the full
`build_record` path is driven only for the owner-ruling half, because a carried check needs a carried-review account
that is heavy to build. Removing the pass's call in `build_record` is caught through the owner-ruling half.

## B7 — the `_seed_ledger_entry` preservation condition

**Guarded element:** `plugins/superheroes/lib/round_driver.py:2296-2300`. Axis: a ledger row settled open at its loop's
end keeps its real consequence and places when it is re-raised with a code-quality consequence.

**Neutralization:** the line `            or session_contract.open_at_loop_end(existing)` was removed from the condition.

**Raw red** (1 failed, 44 passed):

```
...........................................F.                            [100%]
FAILED ...::test_g_re_raising_a_row_settled_open_at_loop_end_keeps_its_real_consequence
1 failed, 44 passed in 2.64s
```

Decisive assertion: `'code-quality' == 'real'` on the re-raised row's `consequenceKind`.

**Restore:** inverse edit, re-inserted the line.

**Restore receipt:** restored lines, `round_driver.py:2298-2300`:

```python
            not _disposition_is_current(existing) or _restaged_after(state, key, existing)
            or session_contract.open_at_loop_end(existing)
            or _undispatched_ruling(state, _live_ruling_by_key(state),
```

**Raw green:**

```
.............................................                            [100%]
45 passed in 2.69s
```

## B8 — the account builder's marker in `_findings_and_merges`

**Guarded element:** `plugins/superheroes/lib/review_record_session.py:876-880`. Axis: the account finding carries
`openAtLoopEnd: true` only when its outcome is `left-for-owner`, its representative is a bare `left-for-owner` row (no
valid `repeatKept`, `decidedBy` None) that carries the marker.

**Neutralization:** `if (outcome == _LEFT_FOR_OWNER and rep is not None and ...` became
`if (False and outcome == _LEFT_FOR_OWNER and rep is not None and ...`.

**Raw red** (1 failed, 44 passed):

```
.............................F...............                            [100%]
FAILED ...::test_f_the_account_carries_the_marker_only_for_a_bare_open_at_loop_end_settle[marked]
1 failed, 44 passed in 2.69s
```

Decisive assertion: `(None is True) == True` (the account finding held no marker).

**Restore:** inverse edit, removed `False and `.

**Restore receipt:** restored lines, `review_record_session.py:876-880`:

```python
        if (outcome == _LEFT_FOR_OWNER and rep is not None and not _valid_repeat_kept(rep)
                and rep.get("disposition") == _LEFT_FOR_OWNER and _decided_by(rep, outcome) is None
                and sc.open_at_loop_end(rep)):
            held[sc.OPEN_AT_LOOP_END_FIELD] = True
```

**Raw green** (the whole 45-test file):

```
.............................................                            [100%]
45 passed in 2.68s
```

## Not in the declared set

`finding_outcomes.settle`'s own gate (`if open_at_end and decided_by is None:`) and the `session_contract.open_at_loop_end`
reader were not in the declared guarded-element set, so no neutralization was run on them. They are exercised by
`test_a_settle_marks_only_a_bare_open_leftover_asked_to_mark_it` and `test_d_the_one_reader_is_an_identity_check_on_true`;
that coverage is unproven by a red run.

## Review round 1 additions (orchestrator-run)

Two more guarded elements came with the review's round-1 fix, and the builder re-ran B1-B8 itself before the review
(same counts as above, plus a reverse probe of B4: `open_at_end=True` unconditionally gave 4 failed, 41 passed, the
deliberate-deferral siblings). Each probe below ran in a detached worktree of the fix commit, by a targeted edit undone
by the inverse edit, detector unedited, with the command above (pycache prefix `/tmp/superheroes-pyc-probe2`); the
restore receipt is an empty `git status --porcelain` in that worktree before it was removed.

### B9 — the exact cross-session repeat keeps the earlier real consequence

**Guarded element:** `plugins/superheroes/lib/round_driver.py` `_apply_repeat_marks`, the call to
`_keep_reopened_consequence`. **Neutralization:** `if not mark["kept"] and mark["source"] == "exact" ...` became
`if False and not mark["kept"] and ...`.

**Raw red** (1 failed, 50 passed):

```
FAILED plugins/superheroes/lib/tests/test_open_at_end_repeats_2445.py::test_i_an_exact_code_quality_repeat_of_a_marked_record_finding_keeps_its_real_consequence_to_the_settle
1 failed, 50 passed in 19.19s
```

### B10 — the driver's keep-or-new call reads `decision_outcome`

**Guarded element:** `plugins/superheroes/lib/round_driver.py` `_repeat_plan`, the `repeat_marks.decide(` argument.
**Neutralization:** `repeat_marks.decision_outcome(entry)` became `entry["outcome"]`.

**Raw red** (3 failed, 48 passed):

```
FAILED plugins/superheroes/lib/tests/test_open_at_end_repeats_2445.py::test_i_the_driver_routes_a_repeat_of_a_marked_record_finding_as_new_and_keeps_an_unmarked_one[marked-judge]
FAILED plugins/superheroes/lib/tests/test_open_at_end_repeats_2445.py::test_i_the_driver_routes_a_repeat_of_a_marked_record_finding_as_new_and_keeps_an_unmarked_one[marked-exact]
FAILED plugins/superheroes/lib/tests/test_open_at_end_repeats_2445.py::test_i_an_exact_code_quality_repeat_of_a_marked_record_finding_keeps_its_real_consequence_to_the_settle
3 failed, 48 passed in 3.54s
```

**Raw green** after both restores: `51 passed in 3.49s` (the fix commit's own run of the whole file).
