# Bite-proof record: i2640_owner_choice_settled

Detector: the settled leg of the withheld-certificate line in `plugins/superheroes/lib/review_record.py`:
`_owner_choices_settled` (true when every finding the session left for the owner now reads `ruling` through an
owner-ruling citation, at least one did, and every other finding keeps the outcome the session gave it), the `settled`
branch of `owner_choice_only`, and the `settled=` argument `build_record` passes to `_status`.

Guarding tests: `plugins/superheroes/lib/tests/test_review_record_owner_choice_settled_2640.py`. Each element below was
neutralized by a targeted edit to `review_record.py`, its one guarding test was run alone (red), the line was restored by
the inverse edit and read back from the file, and the same test was run again (green). Command for every run:
`scripts/pinned-python -B -X pycache_prefix=/tmp/claude-i2640-pyc -m pytest plugins/superheroes/lib/tests/test_review_record_owner_choice_settled_2640.py -q -k <test name>`
(the `--timeout` option the order named is not an option of this pytest; it was dropped).

Raw captures are trimmed to the assertion line(s) and the summary line; the `UV_NATIVE_TLS` deprecation warning that opens
each run and the pytest traceback framing (test source echoed back, the temp path) are elided. Nothing in them is a
secret, token, private URL or personal detail; the one URL in a capture is the fixture link `https://github.com/o/r/...`.

Guarded-element set: (S-branch), (S-ruled), (S-kept), (S-some), (S-wire). No equivalence class is used; each element has
its own neutralization and its own red.

## (S-branch) the settled leg of `owner_choice_only`

- Guarded element and axis: `settled is True or` in `owner_choice_only`. Axis: once the owner has ruled on every finding the
  session left for them, the line stays out and the record can read reviewed.
- Neutralization: `return settled is True or any(waits_for_owner(f, findings) for f in findings)` became
  `return False or any(waits_for_owner(f, findings) for f in findings)`.
- Guarding test: `test_t1_a_fully_ruled_owner_choice_session_reads_reviewed`.
- Raw red:

```
>       assert rec["status"] == "reviewed" and rec["whatIsMissing"] == [], (rec["status"], rec["whatIsMissing"])
E       AssertionError: ('not-reviewed', ["the review session ended handed-back, not converged, so its certificate was withheld: 1 finding(s) need the owner's choice and are still open: widen the API"])
FAILED plugins/superheroes/lib/tests/test_review_record_owner_choice_settled_2640.py::test_t1_a_fully_ruled_owner_choice_session_reads_reviewed
1 failed, 32 deselected in 2.33s
```

- Restore: inverse edit, `False or` back to `settled is True or`.
- Restore receipt (the restored line, read back from the file, `review_record.py:1981`):

```
    return settled is True or any(waits_for_owner(f, findings) for f in findings)
```

- Raw green:

```
.                                                                        [100%]
1 passed, 32 deselected in 2.30s
```

## (S-ruled) a once-waiting finding counts only as an owner-ruling ruling

- Guarded element and axis: the `if not (f.get("outcome") == _RULING and ... by.get("kind") == finding_outcomes.OWNER_RULING):`
  condition inside `_owner_choices_settled`. Axis: a once-waiting finding is settled only as a ruling through an owner-ruling
  citation, never a write-time fix, a scope ruling or an uncited ruling.
- Neutralization: that `if not (...)` line became `if False:`.
- Guarding test: `test_t8_once_waiting_now_fixed_is_not_settled`.
- Raw red:

```
>       assert rr._owner_choices_settled([_waiting()], [{"id": "f-1", "outcome": "fixed"}]) is False
E       AssertionError: assert True is False
FAILED plugins/superheroes/lib/tests/test_review_record_owner_choice_settled_2640.py::test_t8_once_waiting_now_fixed_is_not_settled
1 failed, 32 deselected in 2.19s
```

- Restore: inverse edit, `if False:` back to the `if not (...)` condition.
- Restore receipt (the restored line, read back from the file, `review_record.py:1959`):

```
            if not (f.get("outcome") == _RULING and isinstance(by, dict) and by.get("kind") == finding_outcomes.OWNER_RULING):
```

- Raw green:

```
.                                                                        [100%]
1 passed, 32 deselected in 2.29s
```

## (S-kept) every other finding keeps the outcome the session gave it

- Guarded element and axis: `elif f.get("outcome") != s.get("outcome"):` in `_owner_choices_settled`. Axis: a finding the
  session did not leave for the owner keeps its outcome, so no write-time promotion lifts the line.
- Neutralization: that line became `elif False:`.
- Guarding test: `test_t8_another_outcome_changed_is_not_settled`.
- Raw red:

```
>       assert rr._owner_choices_settled([_waiting(), _fixed(outcome="shown-wrong")], [_ruled(), _fixed()]) is False
E       AssertionError: assert True is False
FAILED plugins/superheroes/lib/tests/test_review_record_owner_choice_settled_2640.py::test_t8_another_outcome_changed_is_not_settled
1 failed, 32 deselected in 2.28s
```

- Restore: inverse edit, `elif False:` back to `elif f.get("outcome") != s.get("outcome"):`.
- Restore receipt (the restored line, read back from the file, `review_record.py:1962`):

```
        elif f.get("outcome") != s.get("outcome"):
```

- Raw green:

```
.                                                                        [100%]
1 passed, 32 deselected in 2.23s
```

## (S-some) a session that left nothing for the owner settles nothing

- Guarded element and axis: `return waited > 0` in `_owner_choices_settled`. Axis: a stamped session that left nothing for
  the owner settles nothing.
- Neutralization: `return waited > 0` became `return True`.
- Guarding test: `test_t8_no_once_waiting_finding_is_not_settled`.
- Raw red:

```
>       assert rr._owner_choices_settled([_fixed()], [_fixed()]) is False
E       AssertionError: assert True is False
FAILED plugins/superheroes/lib/tests/test_review_record_owner_choice_settled_2640.py::test_t8_no_once_waiting_finding_is_not_settled
1 failed, 32 deselected in 2.13s
```

- Restore: inverse edit, `return True` back to `return waited > 0`.
- Restore receipt (the restored lines, read back from the file, `review_record.py:1964-1965`):

```
    # axis: a stamped session that left nothing for the owner settles nothing — see bite-proof record i2640_owner_choice_settled (S-some)
    return waited > 0
```

- Raw green:

```
.                                                                        [100%]
1 passed, 32 deselected in 2.08s
```

## (S-wire) `build_record` passes the settled reading to `_status`

- Guarded element and axis: the `settled=_owner_choices_settled(a["findings"], findings)` argument of the `_status(` call in
  `build_record`. Axis: the writer reads the session's own outcomes (`a["findings"]`) against the record's findings after
  every write-time step, and hands the result to `_status`.
- Neutralization: `settled=_owner_choices_settled(a["findings"], findings))` became `settled=False)`.
- Guarding test: `test_t1_a_fully_ruled_owner_choice_session_reads_reviewed`.
- Raw red:

```
>       assert rec["status"] == "reviewed" and rec["whatIsMissing"] == [], (rec["status"], rec["whatIsMissing"])
E       AssertionError: ('not-reviewed', ["the review session ended handed-back, not converged, so its certificate was withheld: 1 finding(s) need the owner's choice and are still open: widen the API"])
FAILED plugins/superheroes/lib/tests/test_review_record_owner_choice_settled_2640.py::test_t1_a_fully_ruled_owner_choice_session_reads_reviewed
1 failed, 32 deselected in 2.67s
```

- Restore: inverse edit, `settled=False)` back to `settled=_owner_choices_settled(a["findings"], findings))`.
- Restore receipt (the restored lines, read back from the file, `review_record.py:2536-2537`):

```
        rec, [f"the raw output file {n} could not be read" for n in unread], _finding_lines(findings),
        settled=_owner_choices_settled(a["findings"], findings))
```

- Raw green:

```
.                                                                        [100%]
1 passed, 32 deselected in 2.24s
```

## Not covered by a neutralization here

The `isinstance(...)`/length guard at the top of `_owner_choices_settled`, the `LISTED_SEVERITIES` leg (a Minor or Nit with
no outcome counts as left for the owner), the `settled is True` exactness (a loose truthy value), and the stamp gates in
`owner_choice_only` (unchanged, checked before `settled` is read) have no dedicated red run in this record. They are held
by `test_t8_every_other_shape_is_not_settled`, `test_t8_a_minor_with_no_outcome_that_is_now_ruled_is_settled`,
`test_t9_...` and the #2638 suite respectively, and are listed as unproven by a dedicated red run.
