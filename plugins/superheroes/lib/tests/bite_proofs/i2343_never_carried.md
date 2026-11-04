# Bite-proof record — a never-carried finding is never moved, for every outcome (#2343)

Detector file: `plugins/superheroes/lib/tests/test_review_record_carried_2343.py`, unedited between each red and its green. Every entry is a targeted, reversible edit to one production file, `plugins/superheroes/lib/review_record.py`, made and undone with the edit tool (no `git checkout`, `restore`, `reset` or `stash`). Runs: `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-2343 -m pytest '<exact node id>' -q`, one test node each, output captured whole; the `UV_NATIVE_TLS` deprecation warning that `uv` prints first is the only line left out of each capture. No secret, token, URL or personal data appears in any capture, so nothing else is redacted. Entries 1 and 2 are the two guarded elements the order declared, none grouped. The restore receipt of each entry is the restored line, quoted from a `grep -n` run in the same command as the green run.

The detectors the entries name are the tests that carry a `# bite-proof:` line (T1, T2, T3, T4, T5, T6, T7). The extra case `test_e_a_no_earlier_record_at_all_keeps_the_finding` carries an `# axis:` line only and is not part of any proof.

## 1. A finding only this session's own record lists is not carried (left-for-owner and undecided)

- **Axis:** a finding counts as carried only when the earlier record of another session lists it, for every outcome, never on this session's own earlier record.
- **Detector:** `test_review_record_carried_2343.py::test_t1_a_same_session_rewrite_with_nothing_carried_keeps_the_finding[left-for-owner]`.
- **Neutralization:** in `build_record`, the last argument of the `_recheck_carried` call, `                                              earlier_other)`, became `                                              prior)`, so the check reads this session's own earlier record again.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_t1_a_same_session_rewrite_with_nothing_carried_keeps_the_finding[left-for-owner] _

finding = {'id': 'f-1', 'title': 'Unchecked index', 'severity': 'Important', 'file': 'a.py', ...}

    @pytest.mark.parametrize("finding", CASES)
    def test_t1_a_same_session_rewrite_with_nothing_carried_keeps_the_finding(finding):
        # axis: a finding only this session's own earlier record lists is not carried, for left-for-owner and undecided
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2343_never_carried.md
        calls = []
        rec = build_f(finding, record("s-1", finding), history=[], calls=calls)
>       assert_kept(rec, finding, calls)

/home/user/wt-2343/plugins/superheroes/lib/tests/test_review_record_carried_2343.py:71: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

rec = {'schema': 'review-record/1', 'pr': 7, 'sessionId': 's-1', 'lane': {'value': 'light', 'source': 'reported by the session', 'reason': None}, ...}
finding = {'id': 'f-1', 'title': 'Unchecked index', 'severity': 'Important', 'file': 'a.py', ...}
calls = [(None, 'dddddddddddddddddddddddddddddddddddddddd', 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb')]

    def assert_kept(rec, finding, calls):
        f = the_one(rec)
>       assert f["outcome"] == finding["outcome"]
E       AssertionError: assert 'fixed' == 'left-for-owner'
E         
E         - left-for-owner
E         + fixed

/home/user/wt-2343/plugins/superheroes/lib/tests/test_review_record_carried_2343.py:48: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_carried_2343.py::test_t1_a_same_session_rewrite_with_nothing_carried_keeps_the_finding[left-for-owner]
1 failed in 0.32s
```

**Every other red under the same neutralization** (one extra run over the new file and `test_review_record_carried_2338.py`, its output filtered with `grep -E "^(FAILED|[0-9]+ (passed|failed))|passed|failed"`, so only the summary lines are quoted): `12 failed, 31 passed`. The twelve:

- `test_review_record_carried_2343.py::test_t1_…[left-for-owner]`, `test_t1_…[undecided]`
- `test_t2_…[left-for-owner]`, `test_t2_…[undecided]`
- `test_t3_…[left-for-owner]`, `test_t3_…[undecided]`
- `test_t6_…[left-for-owner]`, `test_t6_…[undecided]`
- `test_t7_two_writes_by_one_session_never_move_the_finding_the_first_listed`
- `test_review_record_carried_2338.py::test_t4_a_same_session_rewrite_looks_past_its_own_record_to_the_other_sessions`
- `test_review_record_carried_2338.py::test_t15_a_same_session_rewrite_never_moves_a_shown_wrong_finding_no_earlier_session_carried`
- `test_review_record_carried_2338.py::test_t16_a_same_session_rewrite_with_another_sessions_record_that_never_listed_it_keeps_shown_wrong`

T4 and T5 (both cases each) stay green under E1, as they should: another session's record is the one read there.

**Restore:** the inverse edit put `earlier_other)` back as the last argument.
**Restore receipt** (quoted from `review_record.py`, `grep -n`, same command as the green run):

```
1747:    findings, carried_rows = _recheck_carried(findings, a["carriedChecks"], fc["sha"],
1749:                                              earlier_other)
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 0.94s
```

## 2. A finding the other-session record lists is still carried

- **Axis:** a finding the earlier record of another session lists is carried, so a `fixed` check at the final head moves it (left-for-owner and undecided), even when this session also rewrites its own record or the latest record is unreadable.
- **Detector:** `test_review_record_carried_2343.py::test_t5_a_same_session_rewrite_whose_other_session_record_lists_it_moves_the_finding[undecided]`.
- **Neutralization:** `        elif _key(f) not in other_keys:` became `        elif _key(f) not in set():`, so the membership test reads an empty set.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_t5_a_same_session_rewrite_whose_other_session_record_lists_it_moves_the_finding[undecided] _

finding = {'id': 'f-1', 'title': 'Unchecked index', 'severity': 'Important', 'file': 'a.py', ...}

    @pytest.mark.parametrize("finding", CASES)
    def test_t5_a_same_session_rewrite_whose_other_session_record_lists_it_moves_the_finding(finding):
        # axis: a finding the earlier record of another session lists is carried even when this session also rewrites its own record
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2343_never_carried.md
        rec = build_f(finding, record("s-1", finding), history=[record("s-0", finding)])
>       assert_moved(rec)

/home/user/wt-2343/plugins/superheroes/lib/tests/test_review_record_carried_2343.py:121: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

rec = {'schema': 'review-record/1', 'pr': 7, 'sessionId': 's-1', 'lane': {'value': 'light', 'source': 'reported by the session', 'reason': None}, ...}

    def assert_moved(rec):
        f = the_one(rec)
>       assert f["outcome"] == "fixed"
E       AssertionError: assert None == 'fixed'

/home/user/wt-2343/plugins/superheroes/lib/tests/test_review_record_carried_2343.py:59: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_carried_2343.py::test_t5_a_same_session_rewrite_whose_other_session_record_lists_it_moves_the_finding[undecided]
1 failed in 0.34s
```

**Every other red under the same neutralization** (one extra run over the new file, its output filtered with `grep -E "^FAILED|passed|failed"`): `8 failed, 9 passed`. The eight:

- `test_t4_a_first_write_over_another_sessions_record_moves_the_finding[another-session-left-for-owner]`, `[another-session-undecided]`, `[no-session-id-left-for-owner]`, `[no-session-id-undecided]`
- `test_t5_…[left-for-owner]`, `test_t5_…[undecided]`
- `test_t6_…[left-for-owner]`, `test_t6_…[undecided]`

The nine that stay green are the kept cases (T1, T2, T3, T7 and the extra E-a case), which expect nothing to move.

**Restore:** the inverse edit put `other_keys` back.
**Restore receipt** (quoted from `review_record.py`, `grep -n`, same command as the green run):

```
1633:        elif _key(f) not in other_keys:
1749:                                              earlier_other)
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 0.31s
```

## Not proven

T6's first assertion arm, that the unreadable comment is listed in `earlierRecordsNotChecked` with `why: "unreadable"`, is production behaviour that predates this change (`write`, the `not_checked` list); neither neutralization touches it, so it is not a guarded element of this record.
