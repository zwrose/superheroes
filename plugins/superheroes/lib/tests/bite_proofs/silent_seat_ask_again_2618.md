# Bite-proof record: silent_seat_ask_again_2618

Detector: `plugins/superheroes/lib/tests/test_second_test_ask_again_2618.py` (29 tests), plus section G of
`plugins/superheroes/lib/tests/test_order_shape_grading_2609.py` (the two new rows) and the updated
`plugins/superheroes/lib/tests/test_silent_seat_fold_2617.py`.
Invariant: in the driver's fold for the two logical second-test phases (`second-test`, `second-test-correction`), the
first answer in a round that names none of the items its order gave is not folded: the round's one-shot latch for that
logical phase is spent, `second-test-asked-again` / `break-it-correction-asked-again` is decided, the step and the
held findings / pending correction stay as they were, and the same order goes out once more with one added line
naming the ids not answered. A second silence in the round folds as the empty answer always did (its `silentSeats`
row now carries `askedAgain: true`), so the review reaches a terminal.

Every run below is from the worktree root:
`scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest "<exact node id>" -q -p no:cacheprovider --tb=short`

Each element was neutralized by one targeted edit at its production site (the Edit tool), shown red on the one node
named, restored by the inverse edit (never `git checkout`, `git restore`, `git reset` or `git stash`) and shown green on
the same node. Each neutralization was restored before the next. Nothing here is a secret, token, private URL or PII;
no redaction was needed. The worktree's absolute path appears in tracebacks as printed.

Guarded-element set (declared in the order): G1 to G5 below. No element is grouped. Order defect found at G5 (below).

## G1: the latch check in `_ask_again_once` (`round_driver.py`, `if _latch_spent(state, phase):`)

Axis: a spent latch never re-asks, so a seat that is silent forever reaches a terminal and never the `run_loop` guard trip.

Neutralization: `    if _latch_spent(state, phase):` -> `    if False and _latch_spent(state, phase):`

Node: `plugins/superheroes/lib/tests/test_second_test_ask_again_2618.py::test_t5_held_a_seat_that_is_silent_forever_reaches_a_terminal_that_is_not_the_guard_trip`

Raw red (exit status 1; the `where` lines of the traceback elided, about 0.6 KiB):
```
F                                                                        [100%]
/Users/zwrose/.superheroes-worktrees/superheroes/issue-2618-27d7d58d648fb7ca/plugins/superheroes/lib/tests/test_second_test_ask_again_2618.py:357: in test_t5_held_a_seat_that_is_silent_forever_reaches_a_terminal_that_is_not_the_guard_trip
    assert (state.get("certification") or {}).get("reason") != GUARD_REASON, state.get("certification")
E   AssertionError: {'shape': None, 'reason': 'run_loop guard tripped — fail closed'}
E   assert 'run_loop guard tripped — fail closed' != 'run_loop guard tripped — fail closed'
FAILED plugins/superheroes/lib/tests/test_second_test_ask_again_2618.py::test_t5_held_a_seat_that_is_silent_forever_reaches_a_terminal_that_is_not_the_guard_trip
1 failed in 104.79s (0:01:44)
```

Restore: the inverse edit. Restore receipt (restored line quoted back, `round_driver.py:4616`): `    if _latch_spent(state, phase):`

Raw green (exit status 0): `1 passed in 10.49s`

## G2: the silence gate in `_ask_again_once` (`round_driver.py`, `if not _answer_is_silent(item_ids, answered_ids):`)

Axis: only a silent answer re-asks (a partial answer, a held id answered twice and an order with no items never do).

Neutralization: `    if not _answer_is_silent(item_ids, answered_ids):` -> `    if False and not _answer_is_silent(item_ids, answered_ids):`

Node: `plugins/superheroes/lib/tests/test_second_test_ask_again_2618.py::test_t3_held_an_answer_that_is_not_silent_is_never_asked_again` (the function id, its three cases)

Raw red (exit status 1; the `in` lines of the three tracebacks elided, about 0.5 KiB):
```
FFF                                                                      [100%]
___ test_t3_held_an_answer_that_is_not_silent_is_never_asked_again[partial] ____
E   AssertionError: assert 'askedAgain' not in {'askedAgain': ['second-test']}
_ test_t3_held_an_answer_that_is_not_silent_is_never_asked_again[a-held-id-answered-twice] _
E   AssertionError: assert 'askedAgain' not in {'askedAgain': ['second-test']}
_ test_t3_held_an_answer_that_is_not_silent_is_never_asked_again[an-order-with-no-items] _
E   AssertionError: assert 'askedAgain' not in {'askedAgain': ['second-test']}
3 failed in 1.75s
```

Restore: the inverse edit. Restore receipt (restored line quoted back, `round_driver.py:4613`): `    if not _answer_is_silent(item_ids, answered_ids):`

Raw green (exit status 0): `3 passed in 1.50s`

## G3: the logical-phase key of the correction fold (`round_driver.py`, the `_ask_again_once` call in `_fold_test_correction`)

Axis: the two forms have independent latches, each keyed on its own logical phase.

Neutralization: `    if _ask_again_once(state, "second-test-correction", "break-it-correction-asked-again",` -> `    if _ask_again_once(state, "second-test", "break-it-correction-asked-again",`

Node: `plugins/superheroes/lib/tests/test_second_test_ask_again_2618.py::test_t6_a_spent_correction_latch_never_spends_the_held_findings_latch_in_the_same_round`

Raw red (exit status 1; the `E` lines are complete). The neutralized key shows at the first latch assertion of T6 (the correction's latch holds the held phase's name), before the later assertion that the held findings are still asked once:
```
F                                                                        [100%]
/Users/zwrose/.superheroes-worktrees/superheroes/issue-2618-27d7d58d648fb7ca/plugins/superheroes/lib/tests/test_second_test_ask_again_2618.py:399: in test_t6_a_spent_correction_latch_never_spends_the_held_findings_latch_in_the_same_round
    assert _latch(w.state, "2") == [CORRECTION]
E   AssertionError: assert ['second-test'] == ['second-test-correction']
E     At index 0 diff: 'second-test' != 'second-test-correction'
FAILED plugins/superheroes/lib/tests/test_second_test_ask_again_2618.py::test_t6_a_spent_correction_latch_never_spends_the_held_findings_latch_in_the_same_round
1 failed in 3.13s
```
Not shown by this run: that the held findings' first silence is then NOT asked again (the later T6 assertions); the run stopped at the first.

Restore: the inverse edit. Restore receipt (restored line quoted back, `round_driver.py:7775`): `    if _ask_again_once(state, "second-test-correction", "break-it-correction-asked-again",`

Raw green (exit status 0): `1 passed in 3.15s`

## G4: the added order line (`round_orders.py`, `_derived_placeholders`, the `second-test` branch)

Axis: a re-sent order names the unanswered ids exactly once, on the `file` and the `stdout` channel, in the held and the correction form.

Neutralization: `            if isinstance(asked_again, list) and asked_again:` -> `            if False and isinstance(asked_again, list) and asked_again:`

Node: `plugins/superheroes/lib/tests/test_second_test_ask_again_2618.py::test_t7_a_re_sent_order_names_the_unanswered_ids_once_and_nothing_else_changes` (the function id, its four cases)

Raw red (exit status 1). INCOMPLETE: the runner's output was truncated by the tool (19980 characters elided mid-way) because
the first version of the assertion carried the whole rendered order as its message (the message has since been removed,
a message-only edit; the node's other assertions are unchanged). What the tool returned: the progress line `FFFF`, the
first traceback line `assert again.count(line) == 1, again` for `[held-file]`, and, from the last case's tail, the closing
lines
```
E   assert 0 == 1
E    +  where 0 = <built-in method count of str object at 0x7cc7554000>('- This order is sent once more: your earlier answer named none of these items: v0, v1. Return each of them, by its id.')
```
The `4 failed` count line and the FAILED summary lines were in the truncated part and are NOT quoted here.

Restore: the inverse edit. Restore receipt (restored line quoted back, `round_orders.py:613`): `            if isinstance(asked_again, list) and asked_again:`

Raw green (exit status 0): `4 passed in 1.21s`

## G5: the two new `ORDER_SHAPES` rows (`round_orders.py`)

Axis: every payload shape `_advance` can emit is declared: the payload the real driver emits after a real silent fold is classified as exactly one row.

ORDER DEFECT (the order's named detector does not bite). The order names `test_order_shape_grading_2609.py::test_c_source_keys_match_the_declared_keys[dispatch-second-test]` as the expected red for deleting the `second-test-asked-again` row. It does not: that test compares the union of the phase's declared keys with the keys `_advance` writes, and the `second-test-correction-asked-again` row also declares `askedAgain`, so the union is unchanged. Run with the neutralization applied (exit status 0):
```
.                                                                        [100%]
1 passed in 1.77s
```
So the named detector stays green under the named neutralization. The element is guarded instead by an assertion added to the first T1 test (the payload `_advance` emits after the real silent fold is `matching_order_shapes(...) == ["second-test-asked-again"]`, and likewise `["second-test-correction-asked-again"]` in the correction T1 test), and by the A1 tests of the 2609 file (a fixture or a census state with no row). The red below is that added assertion; the correction row's own deletion was not run (the same assertion, in `test_t1_correction_a_silent_answer_is_asked_again_and_the_second_answer_is_used`, is its detector, unrun).

Neutralization: the `_shape("second-test-asked-again", ...)` call (three lines, between the `# axis:` comment and the `second-test-correction` row's comment) deleted.

Node: `plugins/superheroes/lib/tests/test_second_test_ask_again_2618.py::test_t1_held_a_silent_answer_is_asked_again_and_the_second_answer_is_used`

Raw red (exit status 1; complete):
```
F                                                                        [100%]
/Users/zwrose/.superheroes-worktrees/superheroes/issue-2618-27d7d58d648fb7ca/plugins/superheroes/lib/tests/test_second_test_ask_again_2618.py:113: in test_t1_held_a_silent_answer_is_asked_again_and_the_second_answer_is_used
    assert RO.matching_order_shapes(RD.P_SECOND_TEST, again["payload"]) == ["second-test-asked-again"]
E   AssertionError: assert [] == ['second-test-asked-again']
E     Right contains one more item: 'second-test-asked-again'
FAILED plugins/superheroes/lib/tests/test_second_test_ask_again_2618.py::test_t1_held_a_silent_answer_is_asked_again_and_the_second_answer_is_used
1 failed in 1.33s
```

Restore: the inverse edit (the three lines put back under the `# axis:` comment). Restore receipt (restored line quoted back, `round_orders.py:903`): `    _shape("second-test-asked-again", round_phases.P_SECOND_TEST, CHANNEL_RUNNER, ("findings", "askedAgain"),`

Raw green (exit status 0): `1 passed in 1.32s`

## Disclosures

- T6 builds the same-round sequence from two real parts: the correction's latch is spent by the real folds of two silent correction answers (`World` from `test_c1l10b_test_restore.py`), and the held findings are then staged in the same round with `_held_state`'s rows (the state the hold leaves), because a held-finding hold in the round that took a correction needs the verifier pass and a real break-it run to be driven by hand. The held findings' own folds are the real `_fold`. The reverse order (held latch spent, then a correction in the same round) is not covered.
- G3's red shows at T6's first latch assertion; the later assertion that the held findings are still asked once did not run in that red.
