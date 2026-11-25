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
