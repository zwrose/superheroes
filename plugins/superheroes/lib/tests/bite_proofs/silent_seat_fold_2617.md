# Bite-proof record: silent_seat_fold_2617

Detector: `plugins/superheroes/lib/tests/test_silent_seat_fold_2617.py` (59 tests).
Invariant: a verifier, second-test or second-test-correction answer that reaches the fold for an order that named items,
and names none of them, gets one `silentSeats` row and one decision, whichever entry path delivered it.

Every run below is from the worktree root:
`scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_silent_seat_fold_2617.py -q -n auto`

Each element was neutralized by one targeted edit at its production site, shown red, restored by the inverse edit
(never `git checkout`, `git restore`, `git reset` or `git stash`), and shown green. Each neutralization was restored
before the next. Nothing here is a secret, token, private URL or PII; no redaction was needed. Captures are the
runner's progress line, the failing-test summary lines and the count line, as printed; the per-test tracebacks
(each an `AssertionError` or `TypeError` on the `silentSeats` row, 1-3 KiB each) are elided to stay inside the
record's ceilings, and the elided volume is named per element. Axis for all six: the silent answer is recorded
(or named) at the fold, never dropped and never confused with a seat that did not run.

Guarded-element set (declared in the order): E1 to E6 below. No element is grouped; none is unproven.

## E1: the `_record_silent_seat` call in `_fold_second_test` (`round_driver.py`, the call under the "second-test answer that names none of the held ids" axis comment)

Axis: a second-test answer naming none of the held ids is recorded `second-test-silent`.

Neutralization (the order's item ids passed as `[]`, so the order names no items):
`[row["finding"].get("id") for row in rows], list(by_id))` -> `[], list(by_id))`

Raw red (exit status 1; tracebacks elided, about 6 KiB):
```
..F.F...............................F.F.............FF....F              [100%]
FAILED test_second_test_an_empty_answer_is_silent
FAILED test_second_test_an_answer_naming_only_unknown_ids_is_silent
FAILED test_second_test_hand_submit_of_only_unknown_ids_is_silent
FAILED test_second_test_hand_submit_of_an_empty_answer_is_silent
FAILED test_second_test_run_loop_an_empty_answer_is_silent
FAILED test_second_test_advance_an_empty_answer_is_silent
FAILED test_second_test_hand_submit_the_fold_after_a_silent_answer_equals_the_fold_after_a_minimal_one
7 failed, 52 passed in 53.51s
```
(each: `assert None == [{'phase': 'second-test', 'grain': 'answer', 'items': N}]`)

Restore: the inverse edit, `[], list(by_id))` -> `[row["finding"].get("id") for row in rows], list(by_id))`.
Restore receipt (restored line quoted back): `                        [row["finding"].get("id") for row in rows], list(by_id))`

Raw green (exit status 0): `59 passed in 56.52s`

## E2: the `_record_silent_seat` call in `_fold_test_correction` (`round_driver.py`)

Axis: a correction answer naming none of its items is recorded `break-it-correction-silent`.

Neutralization: `[item["findingKey"] for item in pending["items"]], list(by_id))` -> `[], list(by_id))`

Raw red (exit status 1; tracebacks elided, about 5 KiB):
```
...........F......F.F..F......................F............              [100%]
FAILED test_correction_an_empty_answer_is_silent_at_the_fold
FAILED test_correction_an_answer_naming_only_unknown_ids_is_silent
FAILED test_correction_run_loop_an_empty_answer_is_silent
FAILED test_correction_hand_submit_of_an_empty_answer_is_silent
FAILED test_correction_advance_an_empty_answer_is_silent
5 failed, 54 passed in 60.25s (0:01:00)
```
(each: `assert None == [{'phase': 'second-test-correction', 'grain': 'answer', 'items': 1}]`)

Restore: the inverse edit.
Restore receipt: `                        [item["findingKey"] for item in pending["items"]], list(by_id))`

Raw green (exit status 0): `59 passed in 58.99s`

## E3: the answer-grain branch of `_record_silent_verifiers` (`round_driver.py`, the last `_record_silent_seat(state, "verifiers", ...)` call)

Axis: the whole verifier answer, judged on the verdicts as received, is recorded `verifiers-silent` when it names none of the staged ids (run loop, hand submit, direct fold).

Neutralization: `_record_silent_seat(state, "verifiers", "verifiers-silent", staged_ids,` -> `_record_silent_seat(state, "verifiers", "verifiers-silent", [],`

Raw red (exit status 1; tracebacks elided, about 8 KiB; the runner's own output was truncated by the tool by 1207 characters mid-way through the failure of `test_verifiers_hand_submit_a_forged_empty_seat_list_cannot_hide_a_silent_answer`, so that traceback is incomplete here, its summary line below is complete):
```
.......F......F.F.....F...FF......................FF.......              [100%]
FAILED test_verifiers_an_empty_answer_is_silent_and_the_items_stay_unverified
FAILED test_verifiers_an_answer_naming_only_unknown_ids_is_silent
FAILED test_verifiers_run_loop_an_empty_answer_is_silent
FAILED test_verifiers_run_loop_an_answer_naming_only_an_unknown_id_is_silent
FAILED test_verifiers_hand_submit_of_an_empty_answer_is_silent
FAILED test_verifiers_hand_submit_a_forged_empty_seat_list_cannot_hide_a_silent_answer
FAILED test_verifiers_hand_submit_of_an_unknown_non_refuted_id_is_silent
FAILED test_verifiers_hand_submit_a_forged_seat_list_does_not_change_the_answer_grain_row
8 failed, 51 passed in 63.52s (0:01:03)
```

Restore: the inverse edit.
Restore receipt: `    _record_silent_seat(state, "verifiers", "verifiers-silent", staged_ids,`

Raw green (exit status 0): `59 passed in 58.16s`

## E4: the assembly's silent-seat detection in `_assemble_verifiers` (`round_adapters.py`)

Axis: a landed seat that names none of the ids its order assigned is put in `verifierSilentClusters` (by seat name) and `silentClusters`, so the `advance` fold takes the seat grain.

Neutralization: `if not answered & set(ordered):` -> `if False and not answered & set(ordered):`

Raw red (exit status 1; tracebacks elided, about 6 KiB):
```
.............................F.F....F.F....F...F......F....              [100%]
FAILED test_assembly_a_landed_seat_naming_none_of_its_ids_is_silent
FAILED test_verifiers_advance_one_silent_seat_is_recorded_by_seat
FAILED test_verifiers_advance_every_seat_silent_names_every_seat_sorted
FAILED test_verifiers_advance_a_seat_naming_only_an_unknown_id_is_silent
FAILED test_verifiers_advance_a_missing_seat_is_never_named_with_a_silent_one
FAILED test_assembly_a_seat_naming_only_an_unknown_id_is_silent
FAILED test_verifiers_advance_a_seat_naming_only_another_seats_id_is_silent
7 failed, 52 passed in 60.66s (0:01:00)
```
(for example: `assert [] == ['verifier:f.py:0']` and `assert None == [{'phase': 'verifiers', 'grain': 'seat', 'items': 1, 'seats': ['verifier:src/f00.py:0']}]`; the seat names are the readable names, not storage keys)

Restore: the inverse edit.
Restore receipt: `        if not answered & set(ordered):`

Raw green (exit status 0): `59 passed in 63.44s (0:01:03)`

## E5: the `cmd_submit` strip of `verifierSilentClusters` / `verifierSilentItems` (`round_driver.py`)

Axis: a hand-submitted artifact cannot carry the assembly's per-seat finding: a forged empty list cannot hide a silent answer, and a forged non-empty list cannot make a partial answer silent or change the answer-grain row.

Neutralization: the tuple `("verifierSeatVendors", "verifierSeatProvenance", "verifierSilentClusters", "verifierSilentItems")` -> `("verifierSeatVendors", "verifierSeatProvenance")`

Raw red (exit status 1; tracebacks elided, about 3.5 KiB):
```
............................F.....................F.....F..              [100%]
FAILED test_verifiers_hand_submit_a_forged_seat_list_cannot_make_a_partial_answer_silent
FAILED test_verifiers_hand_submit_a_forged_seat_list_does_not_change_the_answer_grain_row
FAILED test_verifiers_hand_submit_a_forged_empty_seat_list_cannot_hide_a_silent_answer
3 failed, 56 passed in 58.96s
```
(for example: `At index 0 diff: {'grain': 'seat', 'items': 99, 'phase': 'verifiers', 'seats': ['verifier:forged']} != {'phase': 'verifiers', 'grain': 'answer', 'items': 2}`)

Restore: the inverse edit.
Restore receipt (quoted back):
```
                            if k not in ("verifierSeatVendors", "verifierSeatProvenance",
                                         "verifierSilentClusters", "verifierSilentItems")}
```

Raw green (exit status 0): `59 passed in 61.69s (0:01:01)`

## E6: the `silentSeats` degraded prose line in `receipt_disclosures.py` (`_round_verifier_synthesis_prose`)

Axis: the receipt's `degraded` prose names a silent seat (both grains, and the readable verifier seat name for the seat grain).

Neutralization: `if isinstance(silent, list):` -> `if False and isinstance(silent, list):`

Raw red (exit status 1; tracebacks elided, about 5 KiB):
```
..........................F...F..F...F.....................              [100%]
FAILED test_verifiers_hand_submit_of_an_empty_answer_is_silent
FAILED test_the_degraded_prose_names_each_grain
FAILED test_verifiers_advance_one_silent_seat_is_recorded_by_seat
FAILED test_second_test_hand_submit_of_an_empty_answer_is_silent
4 failed, 55 passed in 64.80s (0:01:04)
```
(for example: `assert [] == ['silent-seat (round 3): the second-test seat answered none of its 2 item(s); ...']`)

Restore: the inverse edit.
Restore receipt: `    if isinstance(silent, list):`

Raw green (exit status 0): `59 passed in 59.12s`

## After the last restore

The first `git diff --stat` after the last restore showed a one-line residue in `round_driver.py`: the E1 restore had
dropped one space (`unmatched =sorted(...)` for `unmatched = sorted(...)`, valid Python, so the E1 green run did not
show it). It was reverted by the inverse edit, and the second `git diff --stat` then listed only the order's changes:
```
 plugins/superheroes/lib/round_adapters.py          |  7 ++--
 .../lib/tests/test_silent_seat_fold_2617.py        | 45 +++++++++++++++++++---
 2 files changed, 44 insertions(+), 8 deletions(-)
```
(plus this record, untracked). `round_driver.py` and `receipt_disclosures.py` carry no diff against `4cb4c22b3`. The suite was
re-run green after that repair: `59 passed in 58.19s`.
