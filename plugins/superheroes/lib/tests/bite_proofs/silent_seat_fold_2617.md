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

## WO2

Detector: section G of `plugins/superheroes/lib/tests/test_order_shape_grading_2609.py` (G1 `test_g_rows_whose_empty_answer_the_order_forbids_declare_the_fold`, G2 `test_g_empty_answer_to_the_emitted_ids_folds_silent` over the three rows the table derives, G3 `test_g_minimal_answer_to_the_emitted_ids_is_not_silent`, G4 `test_g_second_test_delivery_never_invites_an_empty_list_and_seams_and_scoped_do_not_change`), plus the golden `dispatch-second-test.txt` read by `test_round_orders.py::test_golden_render_matches_fixture`.
Invariant: every order shape whose empty answer the runner grades ok although the order asks for one answer per item (`emptyAnswerValid` True, `orderAllowsEmpty` False; derived from the table, today `verifiers`, `second-test`, `second-test-correction`) declares the fold as its handler with a real decision kind, and the real `_advance` + real `_fold` record its empty answer to the emitted ids as silent while the minimal answer is not.

Guarded-element set (declared in the order): E7, E8, E9; then the two earlier-record reverts R1 (#2475) and R2 (#2527). No element is grouped; none is unproven. Each neutralization is one targeted edit with the Edit tool at its production site, shown red on the one node (or `-k` selection) named, restored by the inverse edit (never `git checkout`, `git restore`, `git reset` or `git stash`) and shown green on the same selection. Captures are complete runner output except that E8's per-test tracebacks are shown once for the first row and the other two keep their headline line and `AssertionError` line (elided about 1 KiB). Nothing here is a secret, token, private URL or PII; no redaction needed; the worktree's absolute path appears in the R1/R2 tracebacks as printed.

### E7: the `empty_handled_by` of a forbidden-empty row (`round_orders.py`, the `second-test` row)

Axis: a row of the forbidden-empty kind with no fold handler fails G1 (and a handler is read off the table, never a typed list).

Neutralization: on the `second-test` row, `empty_handled_by=HANDLED_BY_FOLD, empty_fold_decision="second-test-silent"),` -> `empty_fold_decision="second-test-silent"),`

Command: `scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_order_shape_grading_2609.py::test_g_rows_whose_empty_answer_the_order_forbids_declare_the_fold -q`

Raw red (exit status 1; the traceback's `where` lines elided, about 0.5 KiB):
```
F                                                                        [100%]
______ test_g_rows_whose_empty_answer_the_order_forbids_declare_the_fold _______
>               assert row.get("emptyHandledBy") == RO.HANDLED_BY_FOLD, row["id"]
E               AssertionError: second-test
E               assert None == 'fold'
FAILED plugins/superheroes/lib/tests/test_order_shape_grading_2609.py::test_g_rows_whose_empty_answer_the_order_forbids_declare_the_fold
1 failed in 3.25s
```

Restore: the inverse edit. Restore receipt (restored line quoted back): `           empty_handled_by=HANDLED_BY_FOLD, empty_fold_decision="second-test-silent"),`

Raw green (exit status 0): `1 passed in 1.81s`

### E8: the fold's silence helper (`round_driver.py`, `_record_silent_seat`)

Axis: the empty answer to the emitted ids is recorded silent (one `silentSeats` row, one decision of the row's `emptyFoldDecision`) by the real `_fold`, for all three rows.

Neutralization: a `return False` line added as the first statement of `_record_silent_seat`'s body (after the docstring, before `if seats is not None:`), so it records nothing.

Command: `scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_order_shape_grading_2609.py -k test_g_empty_answer_to_the_emitted_ids_folds_silent -q -n auto`

Raw red (exit status 1; the `where` lines of each traceback elided):
```
FFF                                                                      [100%]
_ test_g_empty_answer_to_the_emitted_ids_folds_silent[second-test-correction] __
>       assert state["rounds"]["1"].get("silentSeats") == [{"phase": row["id"], "grain": "answer", "items": len(ids)}]
E       AssertionError: assert None == [{'phase': 'second-test-correction', 'grain': 'answer', 'items': 1}]
_______ test_g_empty_answer_to_the_emitted_ids_folds_silent[second-test] _______
E       AssertionError: assert None == [{'phase': 'second-test', 'grain': 'answer', 'items': 1}]
________ test_g_empty_answer_to_the_emitted_ids_folds_silent[verifiers] ________
E       AssertionError: assert None == [{'phase': 'verifiers', 'grain': 'answer', 'items': 1}]
FAILED plugins/superheroes/lib/tests/test_order_shape_grading_2609.py::test_g_empty_answer_to_the_emitted_ids_folds_silent[second-test-correction]
FAILED plugins/superheroes/lib/tests/test_order_shape_grading_2609.py::test_g_empty_answer_to_the_emitted_ids_folds_silent[second-test]
FAILED plugins/superheroes/lib/tests/test_order_shape_grading_2609.py::test_g_empty_answer_to_the_emitted_ids_folds_silent[verifiers]
3 failed in 5.55s
```
(each: the round carries the fold's other rows, `testCorrection` / `secondTest` / `verify`, and no `silentSeats`)

Restore: the inverse edit (the `return False` line removed). Restore receipt (the lines as they stand): `    goes on exactly as it would, the items are recorded as unanswered, and nothing is re-asked."""` followed by `    if seats is not None:`

Raw green (exit status 0): `3 passed in 5.04s`

### E9: the second-test delivery text (`round_orders.py`, `_channel_derived_placeholders`)

Axis: the second-test file-channel text tells the seat to return every finding it was given and never an empty list; the shared sentence is the one that invited the silence.

Neutralization (the shared sentence restored, in two edits at the one site): `elif phase == round_phases.P_SECOND_TEST:` -> `elif False and phase == round_phases.P_SECOND_TEST:`, and `elif phase in (round_phases.P_SEAMS, round_phases.P_SCOPED):` -> `elif phase in (round_phases.P_SEAMS, round_phases.P_SECOND_TEST, round_phases.P_SCOPED):`

Command: `scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_order_shape_grading_2609.py::test_g_second_test_delivery_never_invites_an_empty_list_and_seams_and_scoped_do_not_change -q`

Raw red (exit status 1):
```
F                                                                        [100%]
>       assert _file_delivery(RP.P_SECOND_TEST) == (_FILE_DELIVERY_HEAD % "/landing/x.payload.json") + _SECOND_TEST_DELIVERY_TAIL
E       AssertionError: assert 'Deliver per ...hing to flag.' == 'Deliver per ...indings list.'
E         - ad.json — return each finding you were given exactly once, with its staged id. For a finding you write no new test for, return it with its staged id and its other fields as received and no block in suggestion; never return an empty findings list.
E         + ad.json — write an empty findings list rather than skipping the file when you have nothing to flag.
FAILED plugins/superheroes/lib/tests/test_order_shape_grading_2609.py::test_g_second_test_delivery_never_invites_an_empty_list_and_seams_and_scoped_do_not_change
1 failed in 1.57s
```

Restore: the two inverse edits. Restore receipt (the lines as they stand): `    elif phase == round_phases.P_SECOND_TEST:` and `    elif phase in (round_phases.P_SEAMS, round_phases.P_SCOPED):`

Raw green (exit status 0): `1 passed in 1.52s`

### R1 and R2: the two reverts recorded in `order_shape_grading_2609.md`, re-run exactly as that record describes them

Both neutralize `plugins/superheroes/lib/engine_dispatch.py` (`_finish_review_grade_from_parse`), the same edits, the same detector selection (`test_order_shape_grading_2609.py::test_d_minimal_answer_grades_ok`, flags `-q -p no:cacheprovider --tb=short`, with this order's `-X pycache_prefix=/private/tmp/superheroes-pyc`). Axis for both: the grade of the minimal answer still goes through the real grader after section G was added to the file.

R1 (#2475), neutralization `and kind != engine_adapter.review_payload_key("grouping")):` -> `and True):`. Raw red (exit status 1; the `where` lines elided): the two cases that record names, `synthesis-survivors-earlier-pr-body-staged` and `synthesis-survivors-pr-body-staged`, each `AssertionError: {'forfeit': True, 'reason': 'vacuous', ...}` and `assert None is True`; `2 failed, 22 passed in 2.27s`. Restore: the inverse edit; restored line quoted back: `            and kind != engine_adapter.review_payload_key("grouping")):`. Raw green (exit status 0): `24 passed in 2.24s`.

R2 (#2527), neutralization `if (opened.get("nothingToGroup") is True and kind == "grouping" and has_payload` -> `if (False and opened.get("nothingToGroup") is True and kind == "grouping" and has_payload`. Raw red (exit status 1; the `where` lines elided): the four cases that record names, `synthesis-repeat-only` and `synthesis-repeat-none` in both modes, each `AssertionError: {'forfeit': True, 'reason': 'vacuous', ...}` and `assert None is True`; `4 failed, 20 passed in 2.54s`. Restore: the inverse edit; restored line quoted back: `    if (opened.get("nothingToGroup") is True and kind == "grouping" and has_payload`. Raw green (exit status 0): `24 passed in 2.27s`.

After the last restore `git status --short` listed only this order's files (`round_orders.py`, the golden `dispatch-second-test.txt`, `test_order_shape_grading_2609.py`, `test_round_driver.py`, `verification-pass.md`, and this record once written); `round_driver.py` and `engine_dispatch.py` carry no diff.
