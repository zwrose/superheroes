# Bite-proof record: i2638_owner_choice_only

Detector: the `ownerChoiceOnly` / `ownerChoiceGap` stamp on the owner-choice hand-back in
`_terminal_converged` (`plugins/superheroes/lib/round_driver.py`). The stamp is a gate: it says nothing but the
owner's choices stands between the session and a converge.

Guarding tests: `plugins/superheroes/lib/tests/test_owner_choice_only_2638.py`. Each element below was
neutralized by a targeted edit to `round_driver.py`, its one guarding test was run alone (red), the line was
restored by the inverse edit, and the same test was run again (green). Command for every run:
`scripts/pinned-python -B -m pytest plugins/superheroes/lib/tests/test_owner_choice_only_2638.py -q -k <test>`
(the `--timeout` option the order named is not an option of this pytest; it was dropped).

Raw captures are trimmed to the assertion and the summary line; the `UV_NATIVE_TLS` deprecation warning that opens
each run is elided. No secrets or private values appear in them.

Guarded-element set: (P), (I), (K). Each fails by a different mode (a wrong gap string versus no gap at all),
so no equivalence class is used.

## (P) the pending-ruling leg

- Guarded element and axis: the `if pending:` leg that sets `gap = "owner ruling(s) recorded but never sent to a fixer: ..."`
  in `_terminal_converged`. Axis: an owner fix or guidance ruling still unsent to a fixer withholds `ownerChoiceOnly`.
- Neutralization: `if pending:` became `if pending and False:`.
- Guarding test: `test_e1_a_pending_owner_ruling_leaves_the_gap_and_no_stamp`.
- Raw red:

```
>       assert "ownerChoiceOnly" not in cert, cert
E       AssertionError: {'shape': None, 'reason': "1 finding(s) need the owner's choice and are still open: widen the API", 'ownerChoiceOnly': True}
FAILED plugins/superheroes/lib/tests/test_owner_choice_only_2638.py::test_e1_a_pending_owner_ruling_leaves_the_gap_and_no_stamp
1 failed, 4 deselected in 1.34s
```

- Restore: inverse edit, `if pending and False:` back to `if pending:`.
- Restore receipt (the restored lines, read back from the file):

```
        pending = _pending_owner_rulings(state)
        if pending:
            gap = "owner ruling(s) recorded but never sent to a fixer: " + "; ".join(pending)
```

- Raw green:

```
.                                                                        [100%]
1 passed, 4 deselected in 1.41s
```

## (I) the incomplete-panel leg

- Guarded element and axis: the `elif state.get("_incompletePanel"):` leg that sets the `panel incomplete: ...` gap.
  Axis: an outstanding incomplete panel withholds `ownerChoiceOnly`.
- Neutralization: `elif state.get("_incompletePanel"):` became `elif False and state.get("_incompletePanel"):`.
- Guarding test: `test_e2_an_outstanding_incomplete_panel_leaves_the_gap_and_no_stamp`.
- Raw red:

```
>       assert "ownerChoiceOnly" not in cert, cert
E       AssertionError: {'shape': None, 'reason': "1 finding(s) need the owner's choice and are still open: widen the API", 'ownerChoiceOnly': True}
FAILED plugins/superheroes/lib/tests/test_owner_choice_only_2638.py::test_e2_an_outstanding_incomplete_panel_leaves_the_gap_and_no_stamp
1 failed, 4 deselected in 1.59s
```

- Restore: inverse edit, `elif False and state.get("_incompletePanel"):` back to `elif state.get("_incompletePanel"):`.
- Restore receipt (the restored lines, read back from the file):

```
        elif state.get("_incompletePanel"):
            gap = ("panel incomplete: a configured lens never ran and no complete panel has since "
```

- Raw green:

```
.                                                                        [100%]
1 passed, 4 deselected in 1.44s
```

## (K) the post-settle kept-check leg

- Guarded element and axis: the `gap = _break_it_kept_gap(state, config, session_dir=session_dir, record=False)` line
  that runs after `_hand_back`'s settle when no earlier leg set a gap. Axis: a break-it test not kept (here a carried
  finding whose test was lost) withholds `ownerChoiceOnly`, and the read records nothing.
- Neutralization: that line became `gap = None`.
- Guarding test: `test_e3_a_fixed_finding_whose_test_is_not_kept_leaves_the_gap_and_the_hand_back_alone`.
- Raw red:

```
>       assert "ownerChoiceOnly" not in cert, cert
E       AssertionError: {'shape': None, 'reason': "1 finding(s) need the owner's choice and are still open: widen the API", 'ownerChoiceOnly': True}
FAILED plugins/superheroes/lib/tests/test_owner_choice_only_2638.py::test_e3_a_fixed_finding_whose_test_is_not_kept_leaves_the_gap_and_the_hand_back_alone
1 failed, 4 deselected in 1.46s
```

- Restore: inverse edit, `gap = None` back to `gap = _break_it_kept_gap(state, config, session_dir=session_dir, record=False)`.
- Restore receipt (the restored lines, read back from the file):

```
        if gap is None:
            # the settle inside the hand-back gave a held owner choice its left-for-owner disposition, so its attached test reads not-required
            gap = _break_it_kept_gap(state, config, session_dir=session_dir, record=False)
```

- Raw green:

```
.                                                                        [100%]
1 passed, 4 deselected in 4.70s
```

## Not covered by a neutralization here

The post-settle ordering (the kept check reading a held choice's attached test as `not-required`, not `no-disposition`)
is guarded by `test_e4_...`, which asserts both the unsettled read (`no-disposition`) and the stamped result; it has
no separate neutralization in this record. It sits inside element (K)'s line, so it is listed as unproven by a
dedicated red run.

## (C) the kept-head census reads the gap

- Guarded element: `test_t6_census_a_the_kept_step_and_the_certified_head_read_through_the_resolver` in
  `plugins/superheroes/lib/tests/test_kept_head_resolver_2393.py`, now reading `_break_it_kept_gap` (the function
  that holds the session-head read) instead of `_break_it_kept_step`. Axis: the kept check's body reads the session
  head through `_session_head` and never through `headSha` or `FIX_FOLD_HEAD_KEY`.
- Neutralization: in `_break_it_kept_gap` of `plugins/superheroes/lib/round_driver.py`, `head = _session_head(session_dir, config)`
  replaced with `head = config.get("headSha")`.
- Raw red (trimmed to the assertion and summary line; the long set repr is elided):

```
>       assert "headSha" not in _string_constants(kept)
E       assert 'headSha' not in {'', '%d checked: %d kept, ...
FAILED plugins/superheroes/lib/tests/test_kept_head_resolver_2393.py::test_t6_census_a_the_kept_step_and_the_certified_head_read_through_the_resolver
1 failed, 7 deselected in 0.38s
```

- Restore: inverse edit, `head = config.get("headSha")` back to `head = _session_head(session_dir, config)`.
- Restore receipt (the restored line, read back from the file):

```
    head = _session_head(session_dir, config)
```

- Raw green (whole file, after restore):

```
........                                                                 [100%]
8 passed in 4.27s
```

- The `CHAIN` addition (`"_break_it_kept_gap"`) carries no bite-proof of its own. It only makes `census_b` and
  `census_c` demand that `_break_it_kept_gap` is reached by a call and takes a `session_dir`; it was not neutralized
  separately.

# The record side: the withheld-certificate line and the session writer's stamp

Detector: `owner_choice_only` in `plugins/superheroes/lib/review_record.py` (the one predicate `_status` asks before it
adds the withheld-certificate line), the validator's `ownerChoiceOnly` rule in `_validate`, and the stamp in
`account_from_session` (`plugins/superheroes/lib/review_record_session.py`).

Guarding tests: `plugins/superheroes/lib/tests/test_review_record_owner_choice_only_2638.py`. Each element below was
neutralized by a targeted edit, its one guarding test was run alone (red), the line was restored by the inverse edit and
read back, and the same test was run again (green). Command for every run:
`scripts/pinned-python -B -X pycache_prefix=/tmp/wo-b-pyc -m pytest plugins/superheroes/lib/tests/test_review_record_owner_choice_only_2638.py -q -k <test>`.
Raw captures are trimmed to the assertion and the summary line; the `UV_NATIVE_TLS` deprecation warning that opens each
run and the long fixture reprs are elided. Nothing in them is a secret or a private value.

Guarded-element set for the record side: (R-pred), (R-out), (R-src), (R-stamp). Each fails by a different mode (the line
never lifted, the line lifted over a finding with no outcome, the line lifted for a hand-written entry, the stamp
reaching another hand-back kind), so no equivalence class is used. Not neutralized here: the `waits_for_owner` leg of
the predicate (R5 holds it by its fixed-finding record, with no dedicated red run), the `terminal == "handed-back"` leg
(its only other source of a true is the validator, which R7 covers), and the validator's key-set and identity checks
(R7's refusals hold them, with no dedicated red run); all three are listed as unproven by a dedicated red run.

## (R-pred) the predicate lifts the line

- Guarded element and axis: `owner_choice_only` in `review_record.py`. Axis: a `handed-back` entry the session wrote,
  carrying `ownerChoiceOnly`, with every finding decided and one waiting for the owner, leaves the line out and reads
  `awaits-owner`.
- Neutralization: a line `return False` inserted straight after `u, findings = rec.get("uncertified"), rec.get("findings")`.
- Guarding test: `test_r1_a_driver_ended_owner_choice_only_session_reads_awaits_owner_with_no_withheld_line`.
- Raw red:

```
>       assert out["status"] == rec["status"] == "awaits-owner", (out, rec["whatIsMissing"])
E       AssertionError: ({'ok': True, 'action': 'created', 'url': 'http://c/2', 'parts': 0, ...}, ["finding f.py::widen the api@L2 waits for t...t converged, so its certificate was withheld: 1 finding(s) need the owner's choice and are still open: widen the API"])
E       assert 'not-reviewed' == 'awaits-owner'
FAILED plugins/superheroes/lib/tests/test_review_record_owner_choice_only_2638.py::test_r1_a_driver_ended_owner_choice_only_session_reads_awaits_owner_with_no_withheld_line
1 failed, 20 deselected in 2.43s
```

- Restore: inverse edit, the inserted `return False` line removed.
- Restore receipt (the restored lines, read back from the file):

```
    u, findings = rec.get("uncertified"), rec.get("findings")
    if not (isinstance(u, dict) and u.get("ownerChoiceOnly") is True and u.get("terminal") == "handed-back"
```

- Raw green:

```
.                                                                        [100%]
1 passed, 20 deselected in 2.36s
```

## (R-out) every finding must have an outcome

- Guarded element and axis: the `all(isinstance(f, dict) and f.get("outcome") in rfs.OUTCOMES for f in findings)` leg of
  `owner_choice_only`. Axis: a finding with no outcome keeps the withheld-certificate line.
- Neutralization: that `all(...)` expression replaced with `True`.
- Guarding test: `test_r3_an_important_finding_with_no_outcome_keeps_the_withheld_line`.
- Raw red:

```
>       assert _line(rec) in rec["whatIsMissing"]
E       assert "the review session ended handed-back, not converged, so its certificate was withheld: 1 finding(s) need the owner's choice and are still open: widen the API" in ["finding f.py::widen the api@L2 waits for the owner's decision", 'finding f-9 has no outcome']
FAILED plugins/superheroes/lib/tests/test_review_record_owner_choice_only_2638.py::test_r3_an_important_finding_with_no_outcome_keeps_the_withheld_line
1 failed, 20 deselected in 2.30s
```

- Restore: inverse edit, `True` back to the `all(...)` expression.
- Restore receipt (the restored lines, read back from the file):

```
    return (all(isinstance(f, dict) and f.get("outcome") in rfs.OUTCOMES for f in findings)
            and any(waits_for_owner(f, findings) for f in findings))
```

- Raw green:

```
.                                                                        [100%]
1 passed, 20 deselected in 2.13s
```

## (R-src) only the session's own entry lifts the line

- Guarded element and axis: the `u.get("source") == "session"` leg of `owner_choice_only`. Axis: a hand-written
  account's entry carrying `ownerChoiceOnly` (source `account`) keeps the line.
- Neutralization: `and u.get("source") == "session"` removed from the condition.
- Guarding test: `test_r6_a_hand_written_entry_with_the_flag_keeps_the_line_and_the_sessions_own_does_not`.
- Raw red:

```
>       assert hand["status"] == "not-reviewed" and _line(hand) in hand["whatIsMissing"]
E       AssertionError: assert ('awaits-owner' == 'not-reviewed'
FAILED plugins/superheroes/lib/tests/test_review_record_owner_choice_only_2638.py::test_r6_a_hand_written_entry_with_the_flag_keeps_the_line_and_the_sessions_own_does_not
1 failed, 20 deselected in 2.21s
```

- Restore: inverse edit, `and u.get("source") == "session"` put back before `and isinstance(findings, list)`.
- Restore receipt (the restored lines, read back from the file):

```
    if not (isinstance(u, dict) and u.get("ownerChoiceOnly") is True and u.get("terminal") == "handed-back"
            and u.get("source") == "session" and isinstance(findings, list)):
```

- Raw green:

```
.                                                                        [100%]
1 passed, 20 deselected in 2.32s
```

## (R-stamp) the writer stamps only the owner-choice hand-back

- Guarded element and axis: the condition in `account_from_session` that adds `ownerChoiceOnly` to the entry. Axis: no
  other hand-back kind, even with a certification wrongly carrying the flag, gets the key, so each keeps the line.
- Neutralization: `if (state["terminal"] == _HANDED_BACK and ...` became `if (True or state["terminal"] == _HANDED_BACK and ...`,
  so the key is added whenever the branch runs.
- Guarding test: `test_r8_every_other_hand_back_kind_never_takes_the_stamp_and_keeps_the_line` (seven parametrized
  cases, all red; one is quoted, the others read the same).
- Raw red:

```
>       assert "ownerChoiceOnly" not in rs.account_from_session(session, extras(**body), fake.readers())["uncertified"]
E       assert 'ownerChoiceOnly' not in {'terminal': 'handed-back', 'reason': "the owner's choices are all that is left", 'ownerChoiceOnly': True}
FAILED ...::test_r8_every_other_hand_back_kind_never_takes_the_stamp_and_keeps_the_line[round-cap]
FAILED ...::test_r8_every_other_hand_back_kind_never_takes_the_stamp_and_keeps_the_line[later-round-panel-retired]
7 failed, 14 deselected in 2.31s
```

- Restore: inverse edit, `True or ` removed.
- Restore receipt (the restored lines, read back from the file):

```
        if (state["terminal"] == _HANDED_BACK and last.get("kind") == "owner-choice-open"
                and isinstance(cert, dict) and cert.get("ownerChoiceOnly") is True):
            uncertified["ownerChoiceOnly"] = True
```

- Raw green:

```
.......                                                                  [100%]
7 passed, 14 deselected in 2.58s
```

## (K-run) the kept check's run record never stands in for the write flag

Guarded element: in `_break_it_kept_gap` of `plugins/superheroes/lib/round_driver.py`, the run record the kept check
runs is named `run_record`, so the `record` parameter a caller passed (`record=False` on the owner-choice hand-back)
still decides whether the check writes the `breakItKept` rows and the `break-it-kept` decision. Guarding tests:
`test_k1_a_kept_test_at_the_final_commit_is_checked_and_still_stamps` and
`test_k2_a_test_missing_at_the_final_commit_leaves_the_gap` in `test_owner_choice_only_2638.py`, which reach
`break_it.check_kept` through a real repository (the `World` fixture of `test_kept_head_resolver_2393.py`).

- Neutralization (targeted edit, then the inverse edit): `run_record = _restored_run_record(...)` became
  `run_record = record = _restored_run_record(...)`, the shadowing a review round found.
- Raw red, `-k "k1 or k2"`, trimmed to the assertions:

```
E       AssertionError: ['break-it-run', 'owner-choice-open', 'break-it-kept']
E       assert 'break-it-kept' == 'owner-choice-open'
```

- Raw green after the inverse edit, the six kept-check and owner-choice suites together: `130 passed in 9.02s`.
