# Bite-proof record: c1l7_wo_f_held_record (C1-L7, #2211, WO-F)

Two guarded elements, each with its own neutralization, red and green. Each neutralization is a targeted edit,
reverted by the inverse edit. Captures are the full pytest output (small; no redaction needed, no secrets in them).

## G1: the `held` key in the round's verify record

**Guarded element:** `plugins/superheroes/lib/round_driver.py:3873`, `"held": applied["held"]}` in `_fold_verifiers`.
**Axis:** the findings a passing test missed the path of are listed in the verify record's `held`, where the docs promise them.
**Detector:** `test_second_test_c1l7.py::test_the_verify_record_lists_the_held_findings_and_pass_two_keeps_the_first_passes_list` (both params).

**Neutralization:** the line `                     "held": applied["held"]}` became `                     }`, so the record has no `held`.

**Raw red** (command: `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-wo-f -m pytest plugins/superheroes/lib/tests/test_second_test_c1l7.py -q -k "test_the_verify_record_lists_the_held_findings" -p no:cacheprovider`):

```
FF                                                                       [100%]
=================================== FAILURES ===================================
_ test_the_verify_record_lists_the_held_findings_and_pass_two_keeps_the_first_passes_list[pass-two-confirms] _
    r = Round(tmp_path, second=second)
    r.to_second_test()
>       (held,) = r.state()["rounds"]["1"]["verify"]["held"]
                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       KeyError: 'held'

/home/user/wt-2211-f/plugins/superheroes/lib/tests/test_second_test_c1l7.py:409: KeyError
_ test_the_verify_record_lists_the_held_findings_and_pass_two_keeps_the_first_passes_list[pass-two-holds-again] _
>       (held,) = r.state()["rounds"]["1"]["verify"]["held"]
E       KeyError: 'held'

/home/user/wt-2211-f/plugins/superheroes/lib/tests/test_second_test_c1l7.py:409: KeyError
FAILED ...::test_the_verify_record_lists_the_held_findings_and_pass_two_keeps_the_first_passes_list[pass-two-confirms]
FAILED ...::test_the_verify_record_lists_the_held_findings_and_pass_two_keeps_the_first_passes_list[pass-two-holds-again]
2 failed, 58 deselected in 11.93s
```

(Elided from the capture: the parametrize decorator and test body echo that pytest prints, and the `tmp_path` lines.)

**Restore:** the inverse edit, `                     }` back to `                     "held": applied["held"]}`.
**Restore receipt** (grep of the restored line): `3873:                     "held": applied["held"]}`

**Raw green** (same command):

```
..                                                                       [100%]
2 passed, 58 deselected in 5.74s
```

## G2: the `held` clause in `_nothing_to_verify`

**Guarded element:** `plugins/superheroes/lib/review_record_session.py:276`, `and not (_int(p.get("held")) and p["held"] > 0)`.
**Axis:** a pass whose findings were all held ran a verifier, so it never reads as nothing to verify. An absent `held`, or one that is
not an int (a string, a bool), reads as zero.
**Detector:** `test_second_test_c1l7.py::test_an_all_held_pass_is_a_verifier_that_ran` (the `all-held` param bites; the other four pin the zero reads).

**Neutralization:** the clause line `        and not (_int(p.get("held")) and p["held"] > 0) for p in passes)` was dropped, leaving
`        isinstance(p, dict) and all(_int(p.get(k)) and p[k] == 0 for k in _VERIFY_COUNTS) for p in passes)`.

**Raw red** (command: `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-wo-f -m pytest plugins/superheroes/lib/tests/test_second_test_c1l7.py -q -k "test_an_all_held_pass_is_a_verifier_that_ran" -p no:cacheprovider`):

```
F....                                                                    [100%]
=================================== FAILURES ===================================
____________ test_an_all_held_pass_is_a_verifier_that_ran[all-held] ____________
>       assert rs._nothing_to_verify(state, 1) is nothing
E       AssertionError: assert True is False
/home/user/wt-2211-f/plugins/superheroes/lib/tests/test_second_test_c1l7.py:451: AssertionError
FAILED plugins/superheroes/lib/tests/test_second_test_c1l7.py::test_an_all_held_pass_is_a_verifier_that_ran[all-held]
1 failed, 4 passed, 55 deselected in 2.49s
```

(Elided: the parametrize decorator echo and the `where` lines of the assertion.)

**Restore:** the inverse edit, re-adding the clause line.
**Restore receipt** (grep of the restored line): `276:        and not (_int(p.get("held")) and p["held"] > 0) for p in passes)`

**Raw green** (same command):

```
.....                                                                    [100%]
5 passed, 55 deselected in 1.44s
```
