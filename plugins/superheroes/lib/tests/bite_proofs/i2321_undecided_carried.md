# Bite-proof record — `carriedChecks` settles an undecided carried finding by the same chain as a left-for-owner one (#2321)

Detector file: `plugins/superheroes/lib/tests/test_review_record_carried_undecided_2321.py`, unedited between each red and its green. Every entry is a targeted, reversible edit to one production file, `plugins/superheroes/lib/review_record.py` (`_recheck_carried`), made and undone with the edit tool (no `git checkout`, `restore`, `reset` or `stash`). Runs: `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-2321 -m pytest '<exact node id>' -q`, one test node each, output captured whole; the `UV_NATIVE_TLS` deprecation warning that `uv` prints first is the only line left out of each capture (no secret, token, URL or personal data appears in any capture, so nothing else is redacted). The four guarded elements are the four the order declared; none is grouped. Each target occurred exactly once in the edit's `old_string` (the edit tool refuses a non-unique match). After the last restore, `git diff --stat` of `review_record.py` against the build head `b78bc553` was empty, and against the base `41d208b1` read `5 insertions(+), 3 deletions(-)` — the intended change only.

The detectors the entries name are the tests that carry a `# bite-proof:` line. The other tests in the file carry an `# axis:` line only; their elements are listed under *Not proven* below.

## 1. Undecided is admitted to the chain (`_recheck_carried`, the outcome test)

- **Axis:** an undecided carried finding (`outcome` null or absent) enters the same re-check chain as a left-for-owner one, so a `fixed` entry on the final head can settle it.
- **Detector:** `test_review_record_carried_undecided_2321.py::test_t1_a_fixed_check_at_the_final_head_settles_an_undecided_carried_finding[outcome-null]`.
- **Neutralization:** `        if f.get("outcome") != _LEFT_FOR_OWNER and not undecided:` became `        if f.get("outcome") != _LEFT_FOR_OWNER:`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_t1_a_fixed_check_at_the_final_head_settles_an_undecided_carried_finding[outcome-null] _

finding = {'id': 'f-1', 'title': 'Unchecked index', 'severity': 'Important', 'file': 'a.py', ...}

    @pytest.mark.parametrize("finding", [
        pytest.param(U, id="outcome-null"),
        pytest.param({k: v for k, v in U.items() if k != "outcome"}, id="outcome-absent"),
    ])
    def test_t1_a_fixed_check_at_the_final_head_settles_an_undecided_carried_finding(finding):
        # axis: an undecided carried finding moves to fixed through the same chain as a left-for-owner one
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2321_undecided_carried.md
        calls = []
        rec = build_u([entry()], finding=finding, calls=calls)
        f = the_one(rec)
>       assert f["outcome"] == "fixed"
E       AssertionError: assert None == 'fixed'

/home/user/wt-2321/plugins/superheroes/lib/tests/test_review_record_carried_undecided_2321.py:49: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_carried_undecided_2321.py::test_t1_a_fixed_check_at_the_final_head_settles_an_undecided_carried_finding[outcome-null]
1 failed in 0.52s
```

**Restore:** the inverse edit put `and not undecided` back.
**Restore receipt** (the restored line, quoted from `review_record.py:1482`): `        if f.get("outcome") != _LEFT_FOR_OWNER and not undecided:`

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 0.62s
```

## 2. Undecided rides the same final-commit check (`_recheck_carried`, the `seen != head` branch)

- **Axis:** a check made on a commit other than the record's final commit never settles an undecided finding, exactly as for a left-for-owner one.
- **Detector:** `test_review_record_carried_undecided_2321.py::test_t3_every_other_case_keeps_an_undecided_finding_open[head-moved-after-the-check]`.
- **Neutralization:** `        elif seen != head:` became `        elif seen != head and f.get("outcome") is not None:`, so an undecided finding skips the final-commit check.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_t3_every_other_case_keeps_an_undecided_finding_open[head-moved-after-the-check] _

checks = [{'key': 'rr1:71df46e158ff0278476bc8e3c9417b66', 'settled': 'fixed', 'commit': 'dddddddddddddddddddddddddddddddddddddddd', 'checkedHead': 'cccccccccccccccccccccccccccccccccccccccc', ...}]
prior = {'findings': [{'id': 'f-1', 'title': 'Unchecked index', 'severity': 'Important', 'file': 'a.py', ...}]}
kw = {}, why = 'checked on ccccccc, not the final commit bbbbbbb'
opening = 'a check'

    @pytest.mark.parametrize("checks, prior, kw, why, opening", [
        pytest.param([entry(checkedHead=THIRD)], PRIOR_U, {}, f"checked on {THIRD[:7]}, not the final commit {HEAD[:7]}",
                     "a check", id="head-moved-after-the-check"),
        pytest.param([entry()], PRIOR_U, {"ancestor": False}, f"its fix commit {FIX[:7]} is not in the final commit's history",
                     "a check against the final commit", id="fix-commit-not-in-history"),
        pytest.param([entry()], PRIOR_U, {"ancestor": None}, "its fix commit's place in the history could not be read",
                     "a check against the final commit", id="history-unreadable"),
        pytest.param([entry()], PRIOR_U, {"ancestor": 1}, "its fix commit's place in the history could not be read",
                     "a check against the final commit", id="ancestor-truthy-not-true"),
        pytest.param([entry()], {"findings": []}, {}, "not carried from an earlier record",
                     "a check against the final commit", id="not-carried"),
        pytest.param([entry()], None, {}, "not carried from an earlier record",
                     "a check against the final commit", id="no-earlier-record"),
        pytest.param([entry(settled="applies")], PRIOR_U, {}, "the check found it still applies: ran the test; it passes",
                     "a check against the final commit", id="applies"),
        pytest.param([entry(settled="unsettled")], PRIOR_U, {}, "the check could not settle it: ran the test; it passes",
                     "a check against the final commit", id="unsettled"),
    ])
    def test_t3_every_other_case_keeps_an_undecided_finding_open(checks, prior, kw, why, opening):
        # axis: fail closed, an undecided finding stays undecided unless every condition of the chain holds
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2321_undecided_carried.md
        rec = build_u(checks, prior, **kw)
        f = the_one(rec)
>       assert f["outcome"] is None
E       AssertionError: assert 'fixed' is None

/home/user/wt-2321/plugins/superheroes/lib/tests/test_review_record_carried_undecided_2321.py:81: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_carried_undecided_2321.py::test_t3_every_other_case_keeps_an_undecided_finding_open[head-moved-after-the-check]
1 failed in 0.48s
```

**Restore:** the inverse edit removed `and f.get("outcome") is not None`.
**Restore receipt** (the restored line, quoted from `review_record.py:1492`): `        elif seen != head:`

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 0.52s
```

## 3. Exactly-True ancestry for an undecided finding (`_recheck_carried`, the `in_history` test)

- **Axis:** an undecided finding settles only when `is_ancestor` returns exactly `True`; a truthy non-`True` read (here `1`) keeps it open.
- **Detector:** `test_review_record_carried_undecided_2321.py::test_t3_every_other_case_keeps_an_undecided_finding_open[ancestor-truthy-not-true]`.
- **Neutralization:** `            elif in_history is not True:` became `            elif not in_history:`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_t3_every_other_case_keeps_an_undecided_finding_open[ancestor-truthy-not-true] _

checks = [{'key': 'rr1:71df46e158ff0278476bc8e3c9417b66', 'settled': 'fixed', 'commit': 'dddddddddddddddddddddddddddddddddddddddd', 'checkedHead': 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb', ...}]
prior = {'findings': [{'id': 'f-1', 'title': 'Unchecked index', 'severity': 'Important', 'file': 'a.py', ...}]}
kw = {'ancestor': 1}
why = "its fix commit's place in the history could not be read"
opening = 'a check against the final commit'

    @pytest.mark.parametrize("checks, prior, kw, why, opening", [
        pytest.param([entry(checkedHead=THIRD)], PRIOR_U, {}, f"checked on {THIRD[:7]}, not the final commit {HEAD[:7]}",
                     "a check", id="head-moved-after-the-check"),
        pytest.param([entry()], PRIOR_U, {"ancestor": False}, f"its fix commit {FIX[:7]} is not in the final commit's history",
                     "a check against the final commit", id="fix-commit-not-in-history"),
        pytest.param([entry()], PRIOR_U, {"ancestor": None}, "its fix commit's place in the history could not be read",
                     "a check against the final commit", id="history-unreadable"),
        pytest.param([entry()], PRIOR_U, {"ancestor": 1}, "its fix commit's place in the history could not be read",
                     "a check against the final commit", id="ancestor-truthy-not-true"),
        pytest.param([entry()], {"findings": []}, {}, "not carried from an earlier record",
                     "a check against the final commit", id="not-carried"),
        pytest.param([entry()], None, {}, "not carried from an earlier record",
                     "a check against the final commit", id="no-earlier-record"),
        pytest.param([entry(settled="applies")], PRIOR_U, {}, "the check found it still applies: ran the test; it passes",
                     "a check against the final commit", id="applies"),
        pytest.param([entry(settled="unsettled")], PRIOR_U, {}, "the check could not settle it: ran the test; it passes",
                     "a check against the final commit", id="unsettled"),
    ])
    def test_t3_every_other_case_keeps_an_undecided_finding_open(checks, prior, kw, why, opening):
        # axis: fail closed, an undecided finding stays undecided unless every condition of the chain holds
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2321_undecided_carried.md
        rec = build_u(checks, prior, **kw)
        f = the_one(rec)
>       assert f["outcome"] is None
E       AssertionError: assert 'fixed' is None

/home/user/wt-2321/plugins/superheroes/lib/tests/test_review_record_carried_undecided_2321.py:81: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_carried_undecided_2321.py::test_t3_every_other_case_keeps_an_undecided_finding_open[ancestor-truthy-not-true]
1 failed in 0.54s
```

**Restore:** the inverse edit put `in_history is not True` back.
**Restore receipt** (the restored line, quoted from `review_record.py:1499`): `            elif in_history is not True:`

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 0.47s
```

## 4. An undecided kept finding stays undecided (`_recheck_carried`, the kept append)

- **Axis:** a kept undecided finding keeps `outcome: None`; the re-check never turns it into `left-for-owner` or any other outcome.
- **Detector:** `test_review_record_carried_undecided_2321.py::test_t3_every_other_case_keeps_an_undecided_finding_open[applies]`.
- **Neutralization:** `            out.append(dict(f, reason=f"{old}; {kept}" if old else kept))` became `            out.append(dict(f, outcome=_LEFT_FOR_OWNER if undecided else f.get("outcome"), reason=f"{old}; {kept}" if old else kept))`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
______ test_t3_every_other_case_keeps_an_undecided_finding_open[applies] _______

checks = [{'key': 'rr1:71df46e158ff0278476bc8e3c9417b66', 'settled': 'applies', 'commit': 'dddddddddddddddddddddddddddddddddddddddd', 'checkedHead': 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb', ...}]
prior = {'findings': [{'id': 'f-1', 'title': 'Unchecked index', 'severity': 'Important', 'file': 'a.py', ...}]}
kw = {}, why = 'the check found it still applies: ran the test; it passes'
opening = 'a check against the final commit'

    @pytest.mark.parametrize("checks, prior, kw, why, opening", [
        pytest.param([entry(checkedHead=THIRD)], PRIOR_U, {}, f"checked on {THIRD[:7]}, not the final commit {HEAD[:7]}",
                     "a check", id="head-moved-after-the-check"),
        pytest.param([entry()], PRIOR_U, {"ancestor": False}, f"its fix commit {FIX[:7]} is not in the final commit's history",
                     "a check against the final commit", id="fix-commit-not-in-history"),
        pytest.param([entry()], PRIOR_U, {"ancestor": None}, "its fix commit's place in the history could not be read",
                     "a check against the final commit", id="history-unreadable"),
        pytest.param([entry()], PRIOR_U, {"ancestor": 1}, "its fix commit's place in the history could not be read",
                     "a check against the final commit", id="ancestor-truthy-not-true"),
        pytest.param([entry()], {"findings": []}, {}, "not carried from an earlier record",
                     "a check against the final commit", id="not-carried"),
        pytest.param([entry()], None, {}, "not carried from an earlier record",
                     "a check against the final commit", id="no-earlier-record"),
        pytest.param([entry(settled="applies")], PRIOR_U, {}, "the check found it still applies: ran the test; it passes",
                     "a check against the final commit", id="applies"),
        pytest.param([entry(settled="unsettled")], PRIOR_U, {}, "the check could not settle it: ran the test; it passes",
                     "a check against the final commit", id="unsettled"),
    ])
    def test_t3_every_other_case_keeps_an_undecided_finding_open(checks, prior, kw, why, opening):
        # axis: fail closed, an undecided finding stays undecided unless every condition of the chain holds
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2321_undecided_carried.md
        rec = build_u(checks, prior, **kw)
        f = the_one(rec)
>       assert f["outcome"] is None
E       AssertionError: assert 'left-for-owner' is None

/home/user/wt-2321/plugins/superheroes/lib/tests/test_review_record_carried_undecided_2321.py:81: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_carried_undecided_2321.py::test_t3_every_other_case_keeps_an_undecided_finding_open[applies]
1 failed in 0.55s
```

**Restore:** the inverse edit put the original `out.append(dict(f, reason=...))` back.
**Restore receipt** (the restored line, quoted from `review_record.py:1512`): `            out.append(dict(f, reason=f"{old}; {kept}" if old else kept))`

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 0.48s
```

## Not proven (outside the declared set)

These tests carry no neutralization of their own; they are listed so nobody reads them as covered by this record: the T3 cases other than the three named above (`fix-commit-not-in-history`, `history-unreadable`, `not-carried`, `no-earlier-record`, `unsettled`), the T1 `outcome-absent` case, the no-entry case, the T5 left-for-owner byte-identity tests, and the T2, T4 and T6 end-to-end tests, T7, and the T5 other-outcome test. None of these carries a `# bite-proof:` line, because the order declared no neutralization for them.
