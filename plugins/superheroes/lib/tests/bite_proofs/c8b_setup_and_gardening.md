# Bite-proof record: set-up sitting fixes, the gardening Renew line, ledger rows, launch go-ahead wording, TRANSITION

Detectors: `plugins/superheroes/lib/tests/test_cloud_setup_sitting_text.py` (one new test),
`plugins/superheroes/lib/tests/test_cloud_setup_gardening.py` (one new test, plus the existing threshold test re-recorded as entry 8),
`plugins/superheroes/lib/tests/test_c8b_doctrine_wording.py` (five new tests).
Guarded elements (declared by the order, D2.1 to D2.7, plus the moved gardening threshold as 8): (1) step 8's null-snapshot `--before` rule in `set-up.md`;
(2) step 7's failed-check sentence; (3) the picker-reader row in `LEDGERS.md`; (4) the setup-sitting note's `compare --environment` clause in `TRANSITION.md`;
(5) the "launch go-ahead" wording in `owner-decisions.md`; (6) the parked-build row in `LEDGERS.md`; (7) the Renew line's sign-in sentence in `cloud_setup.py`;
(8) the `days <= next_pass_days` threshold in `_lapse_line`.
Each was neutralized by a targeted edit in the shipped file, the detector run alone as one test node, then restored by the inverse edit
(an edit, never a checkout/restore/reset/stash). Greens are the same node after the restore, run in the same command as a quote of the restored text.

Run command, each time, from the worktree root: `scripts/pinned-python -B -m pytest <node> -q -p no:cacheprovider --tb=short`.
`--tb=short` was added to every single-node run to keep the red captures short; no output was filtered.
The `UV_NATIVE_TLS` deprecation warning that heads every run is omitted from the captures below.
Redaction: none needed; the captures hold no secrets, tokens, URLs or personal data.

Not proven separately: `test_c8b_doctrine_wording.py` tests whose assertions are several independent clauses (step 7's three
assertions, the picker row's `make`/`start`/`judge` names, the parked row's `sent back twice` clause, the four launch go-ahead
occurrences in `owner-decisions.md`) were each proven through one representative clause, named in its entry. The other clauses share that
test's failure mode (a text search for the old or the new wording) and were not neutralized one by one, to stay inside the order's command budget.

## 1. Step 8's null-snapshot `--before` rule

Axis: both pick commands that pass a snapshot value say to leave `--before` out when it was null (exactly two such lines, one before the plain pick, one between the judge and recovery lines).

- Neutralization (`set-up.md`, § 6 step 8): the line `   Leave \`--before\` out when the snapshot value was null.` deleted.
- Node: `test_cloud_setup_sitting_text.py::test_a_null_snapshot_leaves_before_out_of_both_pick_commands`.
- Red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
_________ test_a_null_snapshot_leaves_before_out_of_both_pick_commands _________
/home/user/wo-d2/plugins/superheroes/lib/tests/test_cloud_setup_sitting_text.py:187: in test_a_null_snapshot_leaves_before_out_of_both_pick_commands
    assert len(said) == 2, "section 6 has %d lines saying to leave --before out on a null value, not 2: %r" % (
E   AssertionError: section 6 has 1 lines saying to leave --before out on a null value, not 2: [36]
E   assert 1 == 2
E    +  where 1 = len([36])
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_setup_sitting_text.py::test_a_null_snapshot_leaves_before_out_of_both_pick_commands
1 failed in 0.14s
```

- Restore: the inverse edit. `set-up.md:549` reads `   Leave \`--before\` out when the snapshot value was null.`
- Green:

```
.                                                                        [100%]
1 passed in 0.23s
```

## 2. Step 7's failed-check sentence

Axis: step 7 no longer says a failed check "has written nothing" and names the failed-check marker. Representative clause: `"has written nothing" not in section`.

- Neutralization (`set-up.md`, § 6 step 7): `A failed check never leaves cloud builds ready to switch on, because its failed-check\n   marker blocks them; when` became `A failed check, or a result that could not be read, has written nothing; when`.
- Node: `test_c8b_doctrine_wording.py::test_step_seven_matches_what_judge_does_on_a_failed_check`.
- Red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
__________ test_step_seven_matches_what_judge_does_on_a_failed_check ___________
/home/user/wo-d2/plugins/superheroes/lib/tests/test_c8b_doctrine_wording.py:50: in test_step_seven_matches_what_judge_does_on_a_failed_check
    assert "has written nothing" not in section
E   assert 'has written nothing' not in '## 6 — Clou...s that name.'
E     
E     'has written nothing' is contained here:
E        be read, has written nothing; when cloud builds were on, it has switched them off and the message says so. Never write the setup record any other way, and never tell the owner a check passed without a `passed` result. 8. **"Check again"** repeats steps 6 and 7 with a new check session, naming the environment now in use (the id step 3 returned, the one the latest recovery pick returned, or the one the latest `mismatched` check returned, whichever came last). When the failed part was the environment, run `snapshot` (step 1's command) be...
E     
E     ...Full output truncated (2 lines hidden), use '-vv' to show
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c8b_doctrine_wording.py::test_step_seven_matches_what_judge_does_on_a_failed_check
1 failed in 0.19s
```

- Restore: the inverse edit. `set-up.md:537-538` read `setting. A failed check never leaves cloud builds ready to switch on, because its failed-check` / `   marker blocks them; when cloud builds were on, it has switched them off and the message says so.`
- Green:

```
.                                                                        [100%]
1 passed in 0.11s
```

## 3. The picker-reader ledger row

Axis: the row says the compare comes before `make`, `start` and `judge`, not after a passed check. Representative clause: `"after a passed check" not in row`.

- Neutralization (`LEDGERS.md`, the Cloud environment picker reader row): `and compares it with the environment the setup record names before \`make\`, before \`start\` and before \`judge\`.` became `and after a passed check compares it with the environment the setup record names.`
- Node: `test_c8b_doctrine_wording.py::test_the_picker_row_compares_before_make_start_and_judge`.
- Red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
___________ test_the_picker_row_compares_before_make_start_and_judge ___________
/home/user/wo-d2/plugins/superheroes/lib/tests/test_c8b_doctrine_wording.py:58: in test_the_picker_row_compares_before_make_start_and_judge
    assert "after a passed check" not in row
E   AssertionError: assert 'after a passed check' not in '| **Cloud e...started in |'
E     
E     'after a passed check' is contained here:
E     ?           ^^^^^^^^^^^^
E       try), and after a passed check compares it with the environment the setup record names. Named consumer: the cloud setup sitting in `configure` (`set-up.md` § 6) | Claude Code's `/remote-env` picker and its settings file | The picker prints nothing a plugin can read back and the model would otherwise carry the id by retyping it; a deterministic read of the settings file takes the id from the picker's own result, and refuses a missing, unchanged, malformed or unreadable value, so no id is ever typed, copied or p...
E     
E     ...Full output truncated (2 lines hidden), use '-vv' to show
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c8b_doctrine_wording.py::test_the_picker_row_compares_before_make_start_and_judge
1 failed in 7.07s
```

- Restore: the inverse edit. The row reads `and compares it with the environment the setup record names before \`make\`, before \`start\` and before \`judge\`.`
- Green:

```
.                                                                        [100%]
1 passed in 0.13s
```

## 4. The setup-sitting note's `compare --environment` clause

Axis: the transition note for the setup sitting names `compare --environment`.

- Neutralization (`TRANSITION.md`, § Cloud builds: the setup sitting): the clause ` \`compare --environment <id>\` checks the picked environment against the one in use before the pass is made, before the check starts, and before it is judged.` deleted.
- Node: `test_c8b_doctrine_wording.py::test_the_setup_sitting_note_names_the_compare_command`.
- Red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
____________ test_the_setup_sitting_note_names_the_compare_command _____________
/home/user/wo-d2/plugins/superheroes/lib/tests/test_c8b_doctrine_wording.py:80: in test_the_setup_sitting_note_names_the_compare_command
    assert "compare --environment" in _transition_section("Cloud builds: the setup sitting")
E   assert 'compare --environment' in "- A project is set up for cloud builds by asking the advisor to set up cloud builds. The advisor lists four hand step... its tool-steps marker line, a log line and `exit 0`. A project's own install steps go directly under the marker line."
E    +  where "- A project is set up for cloud builds by asking the advisor to set up cloud builds. The advisor lists four hand step... its tool-steps marker line, a log line and `exit 0`. A project's own install steps go directly under the marker line." = _transition_section('Cloud builds: the setup sitting')
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c8b_doctrine_wording.py::test_the_setup_sitting_note_names_the_compare_command
1 failed in 0.11s
```

- Restore: the inverse edit, re-inserted after `is kept, not asked again).`. The note reads `not asked again). \`compare --environment <id>\` checks the picked environment against the one in use before the pass is made, before the check starts, and before it is judged. A missing`
- Green:

```
.                                                                        [100%]
1 passed in 0.13s
```

## 5. The launch go-ahead wording in `owner-decisions.md`

Axis: the owner's go-ahead to launch is never called the launch word (the place word's name). Representative occurrence: the plural at the decisions-asked count.

- Neutralization (`owner-decisions.md:625`): `P1 words, launch go-aheads, retirement` became `P1 words, launch words, retirement`.
- Node: `test_c8b_doctrine_wording.py::test_owner_decisions_never_calls_the_go_ahead_a_launch_word`.
- Red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
_________ test_owner_decisions_never_calls_the_go_ahead_a_launch_word __________
/home/user/wo-d2/plugins/superheroes/lib/tests/test_c8b_doctrine_wording.py:66: in test_owner_decisions_never_calls_the_go_ahead_a_launch_word
    assert "launch word" not in _read(OWNER_DECISIONS)
E   AssertionError: assert 'launch word' not in '# Contents\...t -->\n```\n'
E     
E     'launch word' is contained here:
E       P1 words, launch words, retirement rulings, and recalibration stamps. **Nothing
E     ?           +++++++++++
E       compares it to anything yet.** The window's misses are **not** a second count, because the record's
E       misses-log line already lists the entries appended. The escape rate is a different measure recorded
E       beside it. **No instrument is built for the count**. It is an advisor's read over board data....
E     
E     ...Full output truncated (145 lines hidden), use '-vv' to show
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c8b_doctrine_wording.py::test_owner_decisions_never_calls_the_go_ahead_a_launch_word
1 failed in 0.11s
```

- Restore: the inverse edit. `owner-decisions.md:625` reads `P0 rulings, batched P1 words, launch go-aheads, retirement rulings, and recalibration stamps. **Nothing`
- Green:

```
.                                                                        [100%]
1 passed in 0.09s
```

## 6. The parked-build ledger row

Axis: the row names where `send-back` runs (gardening included) and allows one duplicate message, not a watch cycle or "sent back twice". Representative clause: `"watch cycle" not in row`.

- Neutralization (`LEDGERS.md`, the Parked cloud build recovery row): `which runs \`send-back\` after a confirmation of a renewed pass, after a passed check and at each gardening pass |` became `which runs \`send-back\` on its watch cycle |`. The second clause (`sent back twice`) was left as shipped.
- Node: `test_c8b_doctrine_wording.py::test_the_parked_build_row_names_the_three_runs_and_the_duplicate_window`.
- Red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
___ test_the_parked_build_row_names_the_three_runs_and_the_duplicate_window ____
/home/user/wo-d2/plugins/superheroes/lib/tests/test_c8b_doctrine_wording.py:73: in test_the_parked_build_row_names_the_three_runs_and_the_duplicate_window
    assert "watch cycle" not in row
E   AssertionError: assert 'watch cycle' not in '| **Parked ...n an event |'
E     
E     'watch cycle' is contained here:
E       k` on its watch cycle | A cloud build session and its pull request | No platform primitive resumes a specific cloud session for a review its pass lapsed under; the decision is a deterministic read of the pull request, the launch ledger and the setup record, so no parked build is lost, and the accepted delivery window allows one duplicate message | The platform gains a way to hold a cloud build open across a reviewer pass renewal, or to resume a named cloud session on an event |
E     ?           +++++++++++
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c8b_doctrine_wording.py::test_the_parked_build_row_names_the_three_runs_and_the_duplicate_window
1 failed in 0.14s
```

- Restore: the inverse edit. The row reads `which runs \`send-back\` after a confirmation of a renewed pass, after a passed check and at each gardening pass |`
- Green:

```
.                                                                        [100%]
1 passed in 0.13s
```

## 7. The Renew line's sign-in sentence

Axis: every `Renew now` line `gardening_lines` returns (lapsed, today, within the next pass, failed reviewer check) carries `Sign the reviewer in again if the date does not move.` The first line checked is the lapsed one, so the red names it; the other three share the one constant.

- Neutralization (`cloud_setup.py:357-358`): the two-line `_RENEW` became `_RENEW = "Run the pass command and paste the new pass into the environment."`
- Node: `test_cloud_setup_gardening.py::test_every_renew_now_line_tells_the_owner_to_sign_the_reviewer_in_again`.
- Red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
___ test_every_renew_now_line_tells_the_owner_to_sign_the_reviewer_in_again ____
/home/user/wo-d2/plugins/superheroes/lib/tests/test_cloud_setup_gardening.py:207: in test_every_renew_now_line_tells_the_owner_to_sign_the_reviewer_in_again
    assert sentence in got["line"], got
E   AssertionError: {'account': 'acct-fixture-one', 'mark': 'Renew now', 'line': 'Cloud reviewer pass: lapsed 12 Oct. Run the pass command and paste the new pass into the environment.'}
E   assert 'Sign the reviewer in again if the date does not move.' in 'Cloud reviewer pass: lapsed 12 Oct. Run the pass command and paste the new pass into the environment.'
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_setup_gardening.py::test_every_renew_now_line_tells_the_owner_to_sign_the_reviewer_in_again
1 failed in 1.26s
```

- Restore: the inverse edit. `cloud_setup.py:357-358` read `_RENEW = ("Run the pass command and paste the new pass into the environment. "` / `          "Sign the reviewer in again if the date does not move.")`
- Green:

```
.                                                                        [100%]
1 passed in 1.04s
```

## 8. The gardening threshold (moved here with the gardening half)

Axis: a pass that will not last to the next gardening pass is marked `Renew now`, inclusive at `next_pass_days` (`days <= next_pass_days`).

- Neutralization (`cloud_setup.py`, `_lapse_line`): `if days <= next_pass_days:` became `if days < next_pass_days:`.
- Node: `test_cloud_setup_gardening.py -k test_the_threshold_is_the_next_pass_days_inclusive`.
- Red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
______________ test_the_threshold_is_the_next_pass_days_inclusive ______________
/home/user/wo-d2/plugins/superheroes/lib/tests/test_cloud_setup_gardening.py:66: in test_the_threshold_is_the_next_pass_days_inclusive
    assert _lines(w)[0]["mark"] == "Renew now"
E   AssertionError: assert None == 'Renew now'
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_setup_gardening.py::test_the_threshold_is_the_next_pass_days_inclusive
1 failed, 15 deselected in 0.50s
```

- Restore: the inverse edit. `cloud_setup.py:371` reads `    if days <= next_pass_days:`
- Green:

```
.                                                                        [100%]
1 passed, 15 deselected in 0.77s
```
