# Bite-proof record — a fixed carried finding reads fixed, and the test-lens line counts only this round (#2338)

Detector file: `plugins/superheroes/lib/tests/test_review_record_carried_2338.py`, unedited between each red and its green. Every entry is a targeted, reversible edit to one production file, `plugins/superheroes/lib/review_record.py`, made and undone with the edit tool (no `git checkout`, `restore`, `reset` or `stash`). Runs: `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-2338 -m pytest '<exact node id>' -q`, one test node each (entry 2 runs the one function whose three parameter cases all guard the same line), output captured whole; the `UV_NATIVE_TLS` deprecation warning that `uv` prints first is the only line left out of each capture. No secret, token, URL or personal data appears in any capture, so nothing else is redacted. Entries 1 to 8 are the eight guarded elements the order declared, none grouped; entry 7b is one extra the author added (the not-listed part's key, which entry 7's neutralization does not touch). The restore receipt of each entry is the restored line, quoted from a `grep -n` run in the same command as the green run.

The detectors the entries name are the tests that carry a `# bite-proof:` line. Tests T6, T9, T13 and T14 carry an `# axis:` line only and are not part of any proof (see *Not proven*).

## 1. A shown-wrong finding is admitted to the carried chain (`_recheck_carried`, the outcome test)

- **Axis:** a shown-wrong carried finding enters the same chain as a left-for-owner one, so a `fixed` entry on the final head can move it.
- **Detector:** `test_review_record_carried_2338.py::test_t1_a_fixed_check_moves_a_finding_the_verifier_graded_wrong_to_fixed[carried-left-for-owner]`.
- **Neutralization:** `        if f.get("outcome") != _LEFT_FOR_OWNER and not undecided and not shown_wrong:` became `        if f.get("outcome") != _LEFT_FOR_OWNER and not undecided:`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_t1_a_fixed_check_moves_a_finding_the_verifier_graded_wrong_to_fixed[carried-left-for-owner] _

prior = {'findings': [{'id': 'f-1', 'title': 'Unchecked index', 'severity': 'Important', 'file': 'a.py', ...}]}

    @pytest.mark.parametrize("prior", [
        pytest.param(PRIOR, id="carried-left-for-owner"),
        pytest.param(record("s-0", U), id="carried-undecided"),
    ])
    def test_t1_a_fixed_check_moves_a_finding_the_verifier_graded_wrong_to_fixed(prior):
        # axis: a shown-wrong finding with its own wrong grade enters the carried chain and a fixed check at the head overrules the grade
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2338_carried_record.md
        assert rr._key(W) == X_KEY
        calls = []
        rec = build_w([entry()], prior=prior, calls=calls)
        f = the_one(rec)
>       assert f["outcome"] == "fixed"
E       AssertionError: assert 'shown-wrong' == 'fixed'
E         
E         - fixed
E         + shown-wrong

/home/user/wt-2338/plugins/superheroes/lib/tests/test_review_record_carried_2338.py:57: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_carried_2338.py::test_t1_a_fixed_check_moves_a_finding_the_verifier_graded_wrong_to_fixed[carried-left-for-owner]
1 failed in 0.36s
```

**Restore:** the inverse edit put `and not shown_wrong` back.
**Restore receipt** (quoted from `review_record.py:1618`): `        if f.get("outcome") != _LEFT_FOR_OWNER and not undecided and not shown_wrong:`

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 0.39s
```

## 2. Own wrong-grade requirement (`_recheck_carried`, the grade test)

- **Axis:** a shown-wrong finding moves only with this session's own verifier wrong grade; a repeat that inherited the outcome (no `grade`) or a grade whose verdict is not `wrong` (`plausible`, `confirmed`) stays. The prior lists the key left-for-owner, so the other-session exclusion (entry 3) does not hide this one.
- **Detector:** `test_review_record_carried_2338.py::test_t5_a_shown_wrong_finding_without_its_own_wrong_grade_is_not_moved`, the one function; its three cases (`repeat-with-no-grade`, `grade-not-wrong`, `grade-confirmed`) all run and all go red.
- **Neutralization:** `        elif shown_wrong and not (isinstance(grade, dict) and grade.get("verdict") == "wrong"):` became `        elif False and shown_wrong and not (isinstance(grade, dict) and grade.get("verdict") == "wrong"):`.

**Raw red** (exit 1):

```
FFF                                                                      [100%]
=================================== FAILURES ===================================
_ test_t5_a_shown_wrong_finding_without_its_own_wrong_grade_is_not_moved[repeat-with-no-grade] _

finding = {'id': 'f-1', 'title': 'Unchecked index', 'severity': 'Important', 'file': 'a.py', ...}

    @pytest.mark.parametrize("finding", [
        pytest.param({**{k: v for k, v in W.items() if k != "grade"},
                      "repeatOf": {"findingKey": X_KEY, "id": "f-0", "fixHolds": True}}, id="repeat-with-no-grade"),
        pytest.param(dict(W, grade={"verdict": "plausible", "reason": "could not show it"}), id="grade-not-wrong"),
        pytest.param(dict(W, grade={"verdict": "confirmed", "reason": "it holds"}), id="grade-confirmed"),
    ])
    def test_t5_a_shown_wrong_finding_without_its_own_wrong_grade_is_not_moved(finding):
        # axis: a shown-wrong finding moves only with this session's own verifier wrong grade, never one inherited by repeat or graded otherwise
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2338_carried_record.md
        rec = build_w([entry()], prior=PRIOR, finding=finding)
        f = the_one(rec)
>       assert f["outcome"] == "shown-wrong" and f["reason"] == OLD
E       AssertionError: assert ('fixed' == 'shown-wrong'
E         
E         - shown-wrong
E         + fixed)

/home/user/wt-2338/plugins/superheroes/lib/tests/test_review_record_carried_2338.py:133: AssertionError
_ test_t5_a_shown_wrong_finding_without_its_own_wrong_grade_is_not_moved[grade-not-wrong] _

finding = {'id': 'f-1', 'title': 'Unchecked index', 'severity': 'Important', 'file': 'a.py', ...}

    @pytest.mark.parametrize("finding", [
        pytest.param({**{k: v for k, v in W.items() if k != "grade"},
                      "repeatOf": {"findingKey": X_KEY, "id": "f-0", "fixHolds": True}}, id="repeat-with-no-grade"),
        pytest.param(dict(W, grade={"verdict": "plausible", "reason": "could not show it"}), id="grade-not-wrong"),
        pytest.param(dict(W, grade={"verdict": "confirmed", "reason": "it holds"}), id="grade-confirmed"),
    ])
    def test_t5_a_shown_wrong_finding_without_its_own_wrong_grade_is_not_moved(finding):
        # axis: a shown-wrong finding moves only with this session's own verifier wrong grade, never one inherited by repeat or graded otherwise
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2338_carried_record.md
        rec = build_w([entry()], prior=PRIOR, finding=finding)
        f = the_one(rec)
>       assert f["outcome"] == "shown-wrong" and f["reason"] == OLD
E       AssertionError: assert ('fixed' == 'shown-wrong'
E         
E         - shown-wrong
E         + fixed)

/home/user/wt-2338/plugins/superheroes/lib/tests/test_review_record_carried_2338.py:133: AssertionError
_ test_t5_a_shown_wrong_finding_without_its_own_wrong_grade_is_not_moved[grade-confirmed] _

finding = {'id': 'f-1', 'title': 'Unchecked index', 'severity': 'Important', 'file': 'a.py', ...}

    @pytest.mark.parametrize("finding", [
        pytest.param({**{k: v for k, v in W.items() if k != "grade"},
                      "repeatOf": {"findingKey": X_KEY, "id": "f-0", "fixHolds": True}}, id="repeat-with-no-grade"),
        pytest.param(dict(W, grade={"verdict": "plausible", "reason": "could not show it"}), id="grade-not-wrong"),
        pytest.param(dict(W, grade={"verdict": "confirmed", "reason": "it holds"}), id="grade-confirmed"),
    ])
    def test_t5_a_shown_wrong_finding_without_its_own_wrong_grade_is_not_moved(finding):
        # axis: a shown-wrong finding moves only with this session's own verifier wrong grade, never one inherited by repeat or graded otherwise
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2338_carried_record.md
        rec = build_w([entry()], prior=PRIOR, finding=finding)
        f = the_one(rec)
>       assert f["outcome"] == "shown-wrong" and f["reason"] == OLD
E       AssertionError: assert ('fixed' == 'shown-wrong'
E         
E         - shown-wrong
E         + fixed)

/home/user/wt-2338/plugins/superheroes/lib/tests/test_review_record_carried_2338.py:133: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_carried_2338.py::test_t5_a_shown_wrong_finding_without_its_own_wrong_grade_is_not_moved[repeat-with-no-grade]
FAILED plugins/superheroes/lib/tests/test_review_record_carried_2338.py::test_t5_a_shown_wrong_finding_without_its_own_wrong_grade_is_not_moved[grade-not-wrong]
FAILED plugins/superheroes/lib/tests/test_review_record_carried_2338.py::test_t5_a_shown_wrong_finding_without_its_own_wrong_grade_is_not_moved[grade-confirmed]
3 failed in 0.41s
```

**Restore:** the inverse edit removed `False and `.
**Restore receipt** (quoted from `review_record.py:1621`): `        elif shown_wrong and not (isinstance(grade, dict) and grade.get("verdict") == "wrong"):`

**Raw green** (exit 0):

```
...                                                                      [100%]
3 passed in 0.35s
```

## 3. The other-session earlier-shown-wrong exclusion (`_recheck_carried`, the `shown_before` test)

- **Axis:** a finding the earlier record of another session already lists `shown-wrong` is not moved by a fixed check, even when it holds its own wrong grade.
- **Detector:** `test_review_record_carried_2338.py::test_t3_a_finding_the_earlier_record_of_another_session_lists_shown_wrong_is_not_moved`.
- **Neutralization:** `        elif shown_wrong and _key(f) in shown_before:` became `        elif False and shown_wrong and _key(f) in shown_before:`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_t3_a_finding_the_earlier_record_of_another_session_lists_shown_wrong_is_not_moved _

    def test_t3_a_finding_the_earlier_record_of_another_session_lists_shown_wrong_is_not_moved():
        # axis: the earlier record of another session already lists the finding shown-wrong, so a fixed check does not move it
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2338_carried_record.md
        rec = build_w([entry()], prior=record("s-0", W))
        f = the_one(rec)
>       assert f["outcome"] == "shown-wrong" and f["reason"] == OLD
E       AssertionError: assert ('fixed' == 'shown-wrong'
E         
E         - shown-wrong
E         + fixed)

/home/user/wt-2338/plugins/superheroes/lib/tests/test_review_record_carried_2338.py:102: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_carried_2338.py::test_t3_a_finding_the_earlier_record_of_another_session_lists_shown_wrong_is_not_moved
1 failed in 0.37s
```

**Restore:** the inverse edit removed `False and `.
**Restore receipt** (quoted from `review_record.py:1624`): `        elif shown_wrong and _key(f) in shown_before:`

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 0.36s
```

## 4. The helper looks past this session's own record (`_earlier_session_record`)

- **Axis:** when `prior` is this session's own record, the earlier record of another session is the next one in `history`, so a rewrite is judged against the other session's facts and not its own.
- **Detector:** `test_review_record_carried_2338.py::test_t4_a_same_session_rewrite_looks_past_its_own_record_to_the_other_sessions`.
- **Neutralization:** `        if isinstance(rec, dict) and rec.get("sessionId") != session_id:` became `        if isinstance(rec, dict):`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_t4_a_same_session_rewrite_looks_past_its_own_record_to_the_other_sessions _

    def test_t4_a_same_session_rewrite_looks_past_its_own_record_to_the_other_sessions():
        # axis: the earlier record is the latest of ANOTHER session, so a rewrite whose prior is this session's own record reads the older one
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2338_carried_record.md
        own = record("s-1", W)
        older = record("s-0", U)
        rec = build_w([entry()], prior=own, history=[older])
        f = the_one(rec)
>       assert f["outcome"] == "fixed" and f["reason"].endswith(f"{OVERRULED}; earlier: {OLD}")
E       AssertionError: assert ('shown-wrong' == 'fixed'
E         
E         - fixed
E         + shown-wrong)

/home/user/wt-2338/plugins/superheroes/lib/tests/test_review_record_carried_2338.py:114: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_carried_2338.py::test_t4_a_same_session_rewrite_looks_past_its_own_record_to_the_other_sessions
1 failed in 0.44s
```

**Restore:** the inverse edit put `and rec.get("sessionId") != session_id` back.
**Restore receipt** (quoted from `review_record.py:1585`): `        if isinstance(rec, dict) and rec.get("sessionId") != session_id:`

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 0.36s
```

## 5. The own test-lens count leaves out carried keys (`_test_lens`, `split`)

- **Axis:** `testLens.findings` counts only the findings raised in this record's own rounds; a carried one is counted in `carriedFindings` and never in `findings`.
- **Detector:** `test_review_record_carried_2338.py::test_t7_a_round_that_raised_nothing_reads_zero_and_the_carried_ones_are_counted_apart`.
- **Neutralization:** `        return len(mine) - len(carried), len(carried)` became `        return len(mine), len(carried)`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_t7_a_round_that_raised_nothing_reads_zero_and_the_carried_ones_are_counted_apart _

    def test_t7_a_round_that_raised_nothing_reads_zero_and_the_carried_ones_are_counted_apart():
        # axis: the own count leaves out every carried finding, and the ran line says both counts in words that cannot be added
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2338_carried_record.md
        found = [lens_finding(1), lens_finding(2)]
        rec = lens_build(found, prior=earlier("s-0", *found))
        part = rec["testLens"]
>       assert part["findings"] == 0 and part["carriedFindings"] == 2
E       assert (2 == 0)

/home/user/wt-2338/plugins/superheroes/lib/tests/test_review_record_carried_2338.py:184: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_carried_2338.py::test_t7_a_round_that_raised_nothing_reads_zero_and_the_carried_ones_are_counted_apart
1 failed in 0.39s
```

**Restore:** the inverse edit put `- len(carried)` back.
**Restore receipt** (quoted from `review_record.py:1330`): `        return len(mine) - len(carried), len(carried)`

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 0.40s
```

## 6. The carried clause on the ran line (`_test_lens_line`)

- **Axis:** the ran line ends `; <n> finding(s) raised in this round, <m> finding(s) carried over from an earlier review.` when `carriedFindings` is positive.
- **Detector:** `test_review_record_carried_2338.py::test_t8_new_and_carried_findings_are_two_counts_and_never_a_sum` (its line assertion; the part assertion before it passes under this neutralization).
- **Neutralization:** `                  if carried_n else "")` (the ran branch's carried clause) became `                  if False else "")`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_______ test_t8_new_and_carried_findings_are_two_counts_and_never_a_sum ________

    def test_t8_new_and_carried_findings_are_two_counts_and_never_a_sum():
        # axis: one new and two carried findings read 1 and 2, and no number in the line is their sum
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2338_carried_record.md
        found = [lens_finding(1), lens_finding(2), lens_finding(3)]
        rec = lens_build(found, prior=earlier("s-0", found[1], found[2]))
        assert (rec["testLens"]["findings"], rec["testLens"]["carriedFindings"]) == (1, 2)
        line = lens_line(rec)
>       assert line.endswith("; 1 finding raised in this round, 2 findings carried over from an earlier review.")
E       AssertionError: assert False
E        +  where False = <built-in method endswith of str object at 0x7f1b5ec64330>('; 1 finding raised in this round, 2 findings carried over from an earlier review.')
E        +    where <built-in method endswith of str object at 0x7f1b5ec64330> = 'Test lens: ran on bbbbbbb (reported by the session), the final commit; calibration read: not shown (no engine record); 1 finding raised.'.endswith

/home/user/wt-2338/plugins/superheroes/lib/tests/test_review_record_carried_2338.py:195: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_carried_2338.py::test_t8_new_and_carried_findings_are_two_counts_and_never_a_sum
1 failed in 0.39s
```

**Restore:** the inverse edit put `if carried_n else ""` back.
**Restore receipt** (quoted from `review_record.py:2443`): `                  if carried_n else "")`

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 0.37s
```

## 7. The carried clause on the not-listed and did-not-run lines (`_test_lens_line`, `tail`)

- **Axis:** the "no test-role reviewer was listed" and "did not run" lines gain `; <m> finding(s) carried over from an earlier review` before the final period when `carriedFindings` is positive.
- **Detector:** `test_review_record_carried_2338.py::test_t10_a_carried_count_rides_the_not_listed_and_the_did_not_run_lines` (fails at the not-listed line, the first line assertion; the did-not-run line assertion behind it is reached only after a restore, and so is covered by the green half, not by a red of its own).
- **Neutralization:** `    tail = f"; {_plural(carried_n, 'finding', 'findings')} carried over from an earlier review" if carried_n else ""` became `    tail = ""`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
___ test_t10_a_carried_count_rides_the_not_listed_and_the_did_not_run_lines ____

    def test_t10_a_carried_count_rides_the_not_listed_and_the_did_not_run_lines():
        # axis: with no test-role reviewer listed, or one that did not run, the carried count still shows and reads as carried
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2338_carried_record.md
        found = [lens_finding(1), lens_finding(2)]
        rec = lens_build(found, prior=earlier("s-0", *found), row=None)
        assert rec["testLens"] == {"listed": False, "carriedFindings": 2}
>       assert lens_line(rec) == "Test lens: no test-role reviewer was listed; 2 findings carried over from an earlier review."
E       AssertionError: assert 'Test lens: n...r was listed.' == 'Test lens: n...rlier review.'
E         
E         Skipping 33 identical leading characters in diff, use -v to show
E         - was listed; 2 findings carried over from an earlier review.
E         + was listed.

/home/user/wt-2338/plugins/superheroes/lib/tests/test_review_record_carried_2338.py:220: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_carried_2338.py::test_t10_a_carried_count_rides_the_not_listed_and_the_did_not_run_lines
1 failed in 0.41s
```

**Restore:** the inverse edit put the `tail` expression back.
**Restore receipt** (quoted from `review_record.py:2419`): `    tail = f"; {_plural(carried_n, 'finding', 'findings')} carried over from an earlier review" if carried_n else ""`

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 0.38s
```

## 7b. The `carriedFindings` key on the not-listed part (`_test_lens`, extra entry)

- **Axis:** a record whose lens listed no test-role row still carries `carriedFindings` when test-lens findings are carried.
- **Detector:** the same node as entry 7 (its first assertion, on the part).
- **Neutralization:** `        return {"listed": False, **({"carriedFindings": carried} if carried else {})}` became `        return {"listed": False}`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
___ test_t10_a_carried_count_rides_the_not_listed_and_the_did_not_run_lines ____

    def test_t10_a_carried_count_rides_the_not_listed_and_the_did_not_run_lines():
        # axis: with no test-role reviewer listed, or one that did not run, the carried count still shows and reads as carried
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2338_carried_record.md
        found = [lens_finding(1), lens_finding(2)]
        rec = lens_build(found, prior=earlier("s-0", *found), row=None)
>       assert rec["testLens"] == {"listed": False, "carriedFindings": 2}
E       AssertionError: assert {'listed': False} == {'listed': Fa...dFindings': 2}
E         
E         Omitting 1 identical items, use -vv to show
E         Right contains 1 more item:
E         {'carriedFindings': 2}
E         Use -v to get more diff

/home/user/wt-2338/plugins/superheroes/lib/tests/test_review_record_carried_2338.py:219: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_carried_2338.py::test_t10_a_carried_count_rides_the_not_listed_and_the_did_not_run_lines
1 failed in 0.36s
```

**Restore:** the inverse edit put the `**({"carriedFindings": ...})` spread back.
**Restore receipt** (quoted from `review_record.py:1335`): `        return {"listed": False, **({"carriedFindings": carried} if carried else {})}`

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 0.42s
```

## 8. The lens-level identity is independent of the current rows (`_test_lens`, `test_lens_finding`)

- **Axis:** a finding is a test-lens finding by its own reviewer identity (`test-role (round 2)` against a current row `test-role (round 1)`), not only by the names of the current rows.
- **Detector:** `test_review_record_carried_2338.py::test_t11_a_carried_finding_raised_in_another_round_still_counts_as_a_carried_test_lens_finding`.
- **Neutralization:** `or any(p == lens_label or _is_test_lens_row({"name": p}) for p in parts)` became `or any(False for p in parts)`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_t11_a_carried_finding_raised_in_another_round_still_counts_as_a_carried_test_lens_finding _

    def test_t11_a_carried_finding_raised_in_another_round_still_counts_as_a_carried_test_lens_finding():
        # axis: a finding is a test-lens finding by its own reviewer identity, not only by the current rows' names
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2338_carried_record.md
        other_round = lens_finding(1, reviewer="test-role (round 2)")
        rec = lens_build([other_round], prior=earlier("s-0", other_round), row=dict(TEST_ROW, name="test-role (round 1)"))
>       assert (rec["testLens"]["findings"], rec["testLens"]["carriedFindings"]) == (0, 1)
                                             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       KeyError: 'carriedFindings'

/home/user/wt-2338/plugins/superheroes/lib/tests/test_review_record_carried_2338.py:235: KeyError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_carried_2338.py::test_t11_a_carried_finding_raised_in_another_round_still_counts_as_a_carried_test_lens_finding
1 failed in 0.40s
```

**Restore:** the inverse edit put `p == lens_label or _is_test_lens_row({"name": p})` back.
**Restore receipt** (quoted from `review_record.py:1324`): `        return _raised_by(reviewer, identities) or any(p == lens_label or _is_test_lens_row({"name": p}) for p in parts)`

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 0.37s
```

## 9. A shown-wrong finding is carried only by the earlier record of another session (`_recheck_carried`, the not-carried test)

- **Axis:** a shown-wrong finding counts as carried only when the earlier record of another session lists it; a session's own earlier record never makes it carried.
- **Detector:** `test_review_record_carried_2338.py::test_t15_a_same_session_rewrite_never_moves_a_shown_wrong_finding_no_earlier_session_carried`. Run with `-X pycache_prefix=/tmp/superheroes-pyc-2338b`; the `UV_NATIVE_TLS` warning is the only line left out of each capture, and nothing else needed redaction (no secret, token, URL or personal data appears).
- **Neutralization:** `        elif _key(f) not in (other_keys if shown_wrong else stored):` became `        elif _key(f) not in stored:`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_t15_a_same_session_rewrite_never_moves_a_shown_wrong_finding_no_earlier_session_carried _

    def test_t15_a_same_session_rewrite_never_moves_a_shown_wrong_finding_no_earlier_session_carried():
        # axis: a shown-wrong finding counts as carried only when the earlier record of another session lists it, never on this session's own record
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2338_carried_record.md
        own = record("s-1", U)
        rec = build_w([entry()], prior=own, history=[])
        f = the_one(rec)
>       assert f["outcome"] == "shown-wrong"
E       AssertionError: assert 'fixed' == 'shown-wrong'
E         
E         - shown-wrong
E         + fixed

/home/user/wt-2338/plugins/superheroes/lib/tests/test_review_record_carried_2338.py:128: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_carried_2338.py::test_t15_a_same_session_rewrite_never_moves_a_shown_wrong_finding_no_earlier_session_carried
1 failed in 0.41s
```

**Restore:** the inverse edit put `(other_keys if shown_wrong else stored)` back.
**Restore receipt** (quoted from `review_record.py:1634`): `        elif _key(f) not in (other_keys if shown_wrong else stored):`

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 0.39s
```

## Not proven

- The `Code, Test` label case and the `Testing` non-match inside T11 are asserted but not neutralized one by one; entry 8 neutralizes the whole lens-level clause.
- The reason text of a kept shown-wrong finding (`kept it shown wrong`, T2) and the overrule sentence on the fixed reason (T1, T4) are asserted by their tests but have no neutralization of their own; they are not in the declared set.
- T2's weaker cases (fix commit not in history, unknown, not carried, other head, `applies`, `unsettled`) run through the unchanged #2322 chain and are guarded by the existing carried-recheck tests; T2 shows the chain keeps a shown-wrong finding and was not neutralized here.
- Tests T6, T9, T12, T13 and T14 carry no neutralization: T6 and T9 are regressions for the unchanged paths; T12 shares entry 4's helper neutralization as its second detector but was not run red separately.
