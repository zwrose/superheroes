# Orchestrator bite-proofs (#1204) — every proof re-run on the FINAL head

The two work-order records in this directory (`wo_a_1204.md`, `wo_b_1204.md`) are the implementers'
own. This record is the **orchestrator's independent re-run of all ten guarded elements on the head
that ships** — the detector-narrowing staleness rule: a proof taken on an intermediate head is not a
proof of what shipped.

Head: `72772b12`. Every neutralization was applied as a **targeted, revertible edit through the
host's edit action** and reverted with the inverse edit; `git status --porcelain` was **empty before
each probe and empty after each revert**, and the landed work was committed before the first probe.
Tests were selected by **exact node id**, never `-k`. Runner exit codes are the runner's own, never a
pipe's.

---

## The claim this issue exists to invert

#1202 disclosed, and its vet independently reproduced, that **deleting the rounds-ledger arm of
`round_driver._seat_map_unjudgeable` left the whole of `test_round_driver.py` green**. I reproduced
that on this branch's base `7c578075` before writing the brief — **457 passed** across
`test_round_driver.py` + `test_seat_map_receipts.py` with the arm deleted (baseline without the
mutation: 443 in `test_round_driver.py` alone).

The same neutralization on the final head `72772b12`:

```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest \
  plugins/superheroes/lib/tests/test_round_driver.py \
  plugins/superheroes/lib/tests/test_seat_map_receipts.py -q -n auto --tb=no
```

```
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_round_driver.py::test_seat_map_unjudgeable_rounds_ledger_has_reader
FAILED plugins/superheroes/lib/tests/test_round_driver.py::test_seat_map_unjudgeable_rounds_arm_with_judgeable_receipts
2 failed, 467 passed in 99.80s (0:01:39)
```

exit 1. The arm that could be deleted silently is now load-bearing.

---

## BP-B1 — the rounds-ledger arm has a reader

**Guarded element:** the `for rec in (state.get("rounds") or {}).values(): … return True` loop in
`round_driver._seat_map_unjudgeable`. **Axis:** a round record arms the predicate when the receipts
alone would not.

**Neutralization:** delete the loop, leaving only the receipts return.

**Red (exit 1):**
```
FF                                                                       [100%]
test_round_driver.py:5145: AssertionError: assert False is True
test_round_driver.py:5162: AssertionError: assert False is True
FAILED ...::test_seat_map_unjudgeable_rounds_ledger_has_reader
FAILED ...::test_seat_map_unjudgeable_rounds_arm_with_judgeable_receipts
2 failed in 1.50s
```

**Green after the inverse edit:** in the closing all-green run below.

---

## BP-B2 — the G3/G4 control halves are load-bearing

**Guarded element:** the *conditionality* of `_seat_map_unjudgeable` — what the controls exist to
pin. **Axis:** the predicate must **not** fire on a judgeable, violation-free map. A control's
failure mode is a detector that fires when it should not, so the neutralization is **always-fire**,
not deletion.

**Neutralization:** `_seat_map_unjudgeable` returns `True` unconditionally.

**Red (exit 1):**
```
FF                                                                       [100%]
test_round_driver.py:5290: AssertionError: assert True is False
test_round_driver.py:5317: AssertionError: assert True is False
FAILED ...::test_seat_map_unjudgeable_terminal_converged_shape_drivers_consumer
FAILED ...::test_seat_map_unjudgeable_cert_shape_degraded_consumer
2 failed in 1.26s
```

### Correction to `wo_b_1204.md`'s BP-B2 pre-fix comparison — measured, not reasoned

`wo_b_1204.md` states that under the always-fire mutation the **old** controls (`fixerVendor =
"claude"`, assertions `"seat-map-unavailable" not in drivers` / `not shape.endswith("-degraded")`)
"would not fail". That was written as a prediction, not a run. **I ran it**, replicating both old
control bodies against the mutated library:

```
mutation live?  _seat_map_unjudgeable({}) = True
OLD G3 control  drivers=['seat-map-unavailable', 'seat-map-violation']  -> assertion passes? False
OLD G4 control  shape='full-panel-confirmed-constraint-violated'        -> assertion passes? True

PRE-FIX under always-fire: G3 control caught it = True | G4 control caught it = False
```

So the prediction is **half wrong, and the record is corrected here**: the old **G3** control *would*
have caught an always-fire mutation; only the old **G4** control was blind to it. This does not
change either guard's disposition — the old G3 control was still vacuous on the axis that matters,
passing on the shipped code for the wrong reason (`shapeDrivers == ['seat-map-violation']`, not
`[]`), which is exactly what the `shapeDrivers == []` assertion now forbids — but a bite-proof record
that predicts instead of measuring is the thing this rubric exists to stop, so the measurement is
recorded rather than the prediction.

---

## BP-B3 / BP-A5 — the receipts quantifier is universal, not existential

**Guarded element:** `seat_map_receipts.unjudgeable_receipts`'s loop over **every** receipt.
**Axis:** one unjudgeable receipt arms the predicate even when another receipt is `complete`; the
whole-history reader was not narrowed by #1204's round-scoping.

**Neutralization:** return `[]` as soon as any receipt's basis is `COMPLETE` (existential).

**Red (exit 1):**
```
test_round_driver.py:5250: AssertionError: assert False is True
test_round_driver.py:5266: AssertionError: assert False is True
test_seat_map_receipts.py:385: assert 0 == 2
FAILED ...::test_seat_map_unjudgeable_quantifier_later_unjudgeable_arms
FAILED ...::test_seat_map_unjudgeable_quantifier_earlier_unjudgeable_arms
FAILED ...::test_unjudgeable_receipts_whole_history_not_round_scoped
3 failed in 1.53s
```

---

## BP-B4 — the `shapeDrivers` consumer

**Guarded element:** `or _seat_map_unjudgeable(state)` in the `shapeDrivers` wiring
(`if _seat_map_unavailable(state) or _seat_map_unjudgeable(state):`). **Axis:** a present-but-
unjudgeable map names a shape driver.

**Neutralization:** drop the `or` arm.

**Red (exit 1):**
```
test_round_driver.py:5284: AssertionError: assert 'seat-map-unavailable' in []
FAILED ...::test_seat_map_unjudgeable_terminal_converged_shape_drivers_consumer
1 failed in 2.07s
```

---

## BP-B5 — the `_cert_shape` consumer

**Guarded element:** `or _seat_map_unjudgeable(state)` in `_cert_shape`'s degradation disjunction.
**Axis:** a present-but-unjudgeable map never certifies unqualified-clean.

**Neutralization:** drop the `or` arm.

**Red (exit 1):**
```
test_round_driver.py:5311: AssertionError: assert False
FAILED ...::test_seat_map_unjudgeable_cert_shape_degraded_consumer
1 failed in 1.86s
```

---

## BP-A1 — the per-round record is round-scoped

**Guarded element:** the `_fold_panel` call site reading `_sm_round_governing_unjudgeable` rather
than the whole-history `_sm_unjudgeable_receipts`. **Axis:** a round whose own map is judgeable is
not stamped unjudgeable because an earlier round's map was not.

**Neutralization:** point the call site back at
`_sm_unjudgeable_receipts(state, _driver_author_family(state))`.

**Red (exit 1):**
```
test_round_driver.py:5341: AssertionError: assert 'seatMapUnjudgeable' not in {...}
test_round_driver.py:5379: AssertionError: assert 'seatMapUnjudgeable' not in {...}
FAILED ...::test_seat_map_unjudgeable_per_round_unjudgeable_then_judgeable
FAILED ...::test_seat_map_unjudgeable_double_fold_bad_then_good_clears_record
2 failed in 1.56s
```

---

## BP-A2 — `_clear_round` settles the channel on every fold

**Guarded element:** the `else: _clear_round(state, "seatMapUnjudgeable")` branch. **Axis:** a
second fold inside one round removes a stale value the first fold wrote — `_record_round` has no
delete path, so without this the channel can only ever be added to.

**Neutralization:** restore the `if _bases:`-only form (no `else`).

**Red (exit 1), and the axis is distinct from BP-A1 — only the double-fold test moves:**
```
F.                                                                       [100%]
test_round_driver.py:5379: AssertionError: assert 'seatMapUnjudgeable' not in {...}
FAILED ...::test_seat_map_unjudgeable_double_fold_bad_then_good_clears_record
1 failed, 1 passed in 1.30s
```

The `1 passed` is `test_seat_map_unjudgeable_per_round_unjudgeable_then_judgeable`, which BP-A1
kills — recorded because it is the evidence that the two elements are **separately** load-bearing
rather than one detector counted twice.

---

## BP-A3 — own-submission-wins

**Guarded element:** the round-label match loop in
`seat_map_receipts.round_governing_unjudgeable`. **Axis:** the round's own last submission is judged,
not whatever `effective_seat_map` resolves to.

**Neutralization:** make the match loop never match (`if False:`), so the fallback always runs.

**Red (exit 1):**
```
test_seat_map_receipts.py:327: AssertionError: assert [] == [{'basis': 'n...round': '10'}]
test_seat_map_receipts.py:296: AssertionError: assert [] == [{'basis': 'n...'round': '1'}]
FAILED ...::test_round_governing_unjudgeable_own_submission_wins_over_effective_map
FAILED ...::test_round_governing_unjudgeable_last_receipt_wins_same_round_label
FAILED ...::test_round_governing_unjudgeable_legacy_prepend_then_empty_seats_receipt
3 failed in 0.32s
```

---

## BP-A4 — the effective-map fallback

**Guarded element:** `selected_map = effective_seat_map(state)` when the round submitted no map of
its own. **Axis:** the per-round record does not go silent while an earlier map still governs — the
under-disclosure that strict round-key equality would have introduced.

**Neutralization:** `return []` when the round submitted nothing.

**Red (exit 1):**
```
test_round_driver.py:5413: KeyError: 'seatMapUnjudgeable'
test_seat_map_receipts.py:309: AssertionError: assert [] == [{'basis': 'n...'round': '2'}]
FAILED ...::test_seat_map_unjudgeable_no_submission_judged_on_effective_map
FAILED ...::test_round_governing_unjudgeable_config_fallback_without_receipts
2 failed in 2.70s
```

---

## Closing state

Every probe reverted; `git status --porcelain` **empty**; `git rev-parse HEAD` =
`72772b1209f42cbfea8ad004de3958a15629f75f`. The closing all-green run is the full-gate run recorded
in the PR body's build record.

**Nothing in this record is UNPROVEN.** All ten guarded elements went red under their own
neutralization and green after its inverse, on the head that ships.
