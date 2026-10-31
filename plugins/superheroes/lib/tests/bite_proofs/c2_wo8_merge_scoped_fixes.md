# Bite-proof record: c2_wo8_merge_scoped_fixes

Three findings from the scoped review of the main merge (issue 2218, C2). Every run used

    scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-wo -m pytest plugins/superheroes/lib/tests/test_c3_outside_findings.py plugins/superheroes/lib/tests/test_review_record_session.py plugins/superheroes/lib/tests/test_ruling_window_c7.py plugins/superheroes/lib/tests/test_unread_waves_c2.py plugins/superheroes/lib/tests/test_sliced_panel_c2.py plugins/superheroes/lib/tests/test_break_it_loop.py -q -n auto -p no:cacheprovider -k <test>

Tests were unedited between each red and its green. Neutralizations and restores were targeted `Edit`s; no
`git stash`, `git checkout` or `git restore` was used. Captures are short and are quoted in full except for the
`UV_NATIVE_TLS` warning line and the `bringing up nodes...` lines, which are elided. Nothing needed redaction.

## E1: `review_record_session.py:914`, axis: a sliced test seat is the test role for the break-it scope exemption

Detector: `test_c3_outside_findings.py::test_t9_a_sliced_test_seats_unfolded_break_it_proposal_stays_open_like_the_whole_change_seats`
(`-k test_t9_a_sliced_test_seats_unfolded_break_it_proposal`), both parameters (`test-role:s1`, `test-role:w2u1`).

Neutralization: `exempt = phase == round_phases.P_PANEL and seat == break_it.ROLE and break_it.scope_exempt(f)`

Raw red (excerpt; the failing assertion is identical for both parameters):

    FF                                                                       [100%]
    >       assert [f["title"] for f in account["findings"]] == [valid["title"]] and "outsideThisPR" not in account
    E       AssertionError: assert ([] == ['Break-it: a...e runs twice']
    E         Right contains one more item: 'Break-it: a retried charge runs twice'
    FAILED plugins/superheroes/lib/tests/test_c3_outside_findings.py::test_t9_a_sliced_test_seats_unfolded_break_it_proposal_stays_open_like_the_whole_change_seats[test-role:w2u1]
    FAILED plugins/superheroes/lib/tests/test_c3_outside_findings.py::test_t9_a_sliced_test_seats_unfolded_break_it_proposal_stays_open_like_the_whole_change_seats[test-role:s1]
    2 failed in 1.48s

Restore (inverse edit), line quoted back (`review_record_session.py:914`):

    exempt = phase == round_phases.P_PANEL and round_phases.seat_lens(seat) == break_it.ROLE and break_it.scope_exempt(f)

Raw green:

    ..                                                                       [100%]
    2 passed in 5.25s

## E2: `round_driver.py:3897`, axis: an intercepted copy keeps its original finding's roster-key source

Detector: `test_unread_waves_c2.py::test_a_sliced_test_seats_outside_hit_keeps_its_seat_key_so_abandoned_recovery_does_not_add_it_twice`
(`-k test_a_sliced_test_seats_outside_hit_keeps_its_seat_key`). It folds a sliced round with an outside finding from
`test-role:s1`, asserts the hit sits under `test-role:s1`, then builds an abandoned session holding that list and the stored
report and asserts recovery adds nothing (the hit appears exactly once, under `test-role:s1`).

Neutralization: `seat_sources[id(g)] = break_it.ROLE  # the copies are new dicts: they came from the original's seat`
(was `seat_sources.get(id(original), break_it.ROLE)`).

Raw red (excerpt):

    F                                                                        [100%]
    >       assert names == [("test-role:s1", ["Outside the change"])]
    E       AssertionError: assert [('test-role'...the change'])] == [('test-role:...the change'])]
    E         At index 0 diff: ('test-role', ['Outside the change']) != ('test-role:s1', ['Outside the change'])
    FAILED plugins/superheroes/lib/tests/test_unread_waves_c2.py::test_a_sliced_test_seats_outside_hit_keeps_its_seat_key_so_abandoned_recovery_does_not_add_it_twice
    1 failed in 3.46s

The red stops at the fold-side assertion, so the recovery half (the duplicate) is not reached under this neutralization; it is
the second assertion block of the same test and is guarded by the first.

Restore (inverse edit), line quoted back (`round_driver.py:3897`):

    seat_sources[id(g)] = seat_sources.get(id(original), break_it.ROLE)  # the copies are new dicts: they came from the original's seat

Raw green:

    .                                                                        [100%]
    1 passed in 1.59s

## E3: `round_driver.py:4833`, axis: the real synthesis fold writes `mergedInto`, with no manual ledger link in the test fixture

Detector: `test_ruling_window_c7.py::test_a_ruling_on_a_member_merged_into_another_reaches_the_one_live_row`
(`-k test_a_ruling_on_a_member_merged_into_another_reaches_the_one_live_row`), with the manual
`_record_merged_into` / `_set_findings` block removed from `_merged_into_session`. The fixture's synthesis grouping already puts
both findings in one group, so no fixture change was needed.

Neutralization: in the synthesis fold's merge recording, `_record_merged_into(state, key, kept_key)` replaced by `pass`.

Raw red (excerpt):

    F                                                                        [100%]
    >       assert len(members) == 1
    E       assert 0 == 1
    E        +  where 0 = len([])
    FAILED plugins/superheroes/lib/tests/test_ruling_window_c7.py::test_a_ruling_on_a_member_merged_into_another_reaches_the_one_live_row
    1 failed in 3.55s

Restore (inverse edit), line quoted back (`round_driver.py:4833`):

    _record_merged_into(state, key, kept_key)

Raw green:

    .                                                                        [100%]
    1 passed in 3.49s
