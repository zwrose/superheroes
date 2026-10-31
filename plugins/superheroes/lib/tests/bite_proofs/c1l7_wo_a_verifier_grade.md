# Bite-proof record: c1l7_wo_a_verifier_grade

#2211 (C1-L7): the review record closes a finding as wrong only on the verifier's grade. Tests:
`plugins/superheroes/lib/tests/test_review_record_verifier_grade_c1l7.py`. Guards:
`plugins/superheroes/lib/review_record_session.py` and `plugins/superheroes/lib/review_record.py`.

Every run below is `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-wo-a -m pytest <node> -q -n 4` from the
worktree root, on one test node of the new file. Each neutralization is a targeted edit, reverted by the inverse edit.
The guards were committed at `b8cf36a8` before the proof, so after each restore `git status --porcelain <file>` and
`git diff --stat -- <file>` print nothing: the file equals the commit. The restored lines are quoted back as well.
Nothing is redacted: the captures hold no secrets, tokens, private URLs or PII. The `UV_NATIVE_TLS` warning line the
launcher prints is kept as it came.

The order declared four guarded elements (G1 to G4), one entry each. No equivalence classes are used.

## G1: `_decide`'s wrong-grade condition

- **Guarded element and axis:** `review_record_session.py:420`. A refuted row reads `shown-wrong` only on the
  verifier's own `wrong` grade, never on the refuted disposition alone.
- **Neutralization:** in `_decide`'s `if disp == "refuted":` branch, the condition
  `if isinstance(grade, dict) and grade.get("verdict") == "wrong":` became `if True:`, so every refuted row returns
  `shown-wrong`.
- **Detector:** `test_a_refuted_row_with_no_grade_reads_open`.

Raw red:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
bringing up nodes...
bringing up nodes...

F                                                                        [100%]
=================================== FAILURES ===================================
_________________ test_a_refuted_row_with_no_grade_reads_open __________________
[gw0] linux -- Python 3.12.13 /root/.cache/uv/builds-v0/.tmpeefz4a/bin/python

    def test_a_refuted_row_with_no_grade_reads_open():
        # axis: G1 the wrong-grade condition; the refuted disposition alone closes nothing
>       assert decide(ledger_row(**REFUTED)) == (None, rs.REFUTED_UNGRADED)
E       AssertionError: assert ('shown-wrong...es not exist') == (None, 'refut...; still open')
E         
E         At index 0 diff: 'shown-wrong' != None
E         Use -v to get more diff

/home/user/wt-2211-a/plugins/superheroes/lib/tests/test_review_record_verifier_grade_c1l7.py:39: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_verifier_grade_c1l7.py::test_a_refuted_row_with_no_grade_reads_open
1 failed in 0.65s
```

- **Restore:** the inverse edit, `if True:` back to `if isinstance(grade, dict) and grade.get("verdict") == "wrong":`.
- **Restore receipt:** `git status --porcelain plugins/superheroes/lib/review_record_session.py` and
  `git diff --stat -- plugins/superheroes/lib/review_record_session.py` both printed nothing. Restored lines
  (`sed -n 418,424p`):

```
        grade = rep.get("grade")
        # axis: a refuted row reads shown-wrong only on the verifier's own wrong grade, never on the disposition alone — see bite-proof record c1l7_wo_a_verifier_grade
        if isinstance(grade, dict) and grade.get("verdict") == "wrong":
            return _SHOWN_WRONG, why, rep
        if (why or "").startswith("author-justified"):
            return _LEFT_FOR_OWNER, why, rep
        return None, REFUTED_UNGRADED, rep
```

Raw green:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
bringing up nodes...
bringing up nodes...

.                                                                        [100%]
1 passed in 2.78s
```

## G2: the writer gate in `review_record.write`

- **Guarded element and axis:** `review_record.py:2404` (the loop over `_wrong_ungraded`). A `shown-wrong` finding
  with a well-formed `wrong` grade that the driver never set (not in `verifier_closed`, not carried) is refused.
- **Neutralization:** `for i in _wrong_ungraded(a["findings"], prior, verifier_closed):` became `for i in []:`, which
  skips the check.
- **Detector:** `test_a_direct_account_with_a_forged_wrong_grade_is_refused`.

Raw red:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
bringing up nodes...
bringing up nodes...

F                                                                        [100%]
=================================== FAILURES ===================================
__________ test_a_direct_account_with_a_forged_wrong_grade_is_refused __________
[gw0] linux -- Python 3.12.13 /root/.cache/uv/builds-v0/.tmpLWCk1P/bin/python

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-7/popen-gw0/test_a_direct_account_with_a_f0')

    def test_a_direct_account_with_a_forged_wrong_grade_is_refused(tmp_path):
        fake = Fake()
        forged = wrong("a-1", reason="not a bug")
        out = write(tmp_path, fake, [forged])
        # axis: G2 the writer gate; a well-formed wrong grade the driver never set is not the verifier's close
>       assert (out["ok"], out["reason"], out["detail"]) == (False, "review-account-invalid", REFUSAL)
                           ^^^^^^^^^^^^^
E       KeyError: 'reason'

/home/user/wt-2211-a/plugins/superheroes/lib/tests/test_review_record_verifier_grade_c1l7.py:127: KeyError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_verifier_grade_c1l7.py::test_a_direct_account_with_a_forged_wrong_grade_is_refused
1 failed in 1.09s
```

- **Restore:** the inverse edit, `for i in []:` back to `for i in _wrong_ungraded(a["findings"], prior, verifier_closed):`.
- **Restore receipt:** `git status --porcelain plugins/superheroes/lib/review_record.py` and
  `git diff --stat -- plugins/superheroes/lib/review_record.py` both printed nothing. Restored lines
  (`sed -n 2404,2405p`):

```
        for i in _wrong_ungraded(a["findings"], prior, verifier_closed):
            raise Refusal("review-account-invalid", f"findings[{i}] is shown-wrong without the verifier's grade")
```

Raw green:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
bringing up nodes...
bringing up nodes...

.                                                                        [100%]
1 passed in 0.62s
```

## G3: the carry exception

- **Guarded element and axis:** `review_record.py:2342`. An outcome the latest earlier record already stored as
  `shown-wrong` is carried whatever this account's grade says.
- **Neutralization:** `if not (closed or _key(f) in carried):` became `if not closed:`, which removes the `prior`
  clause.
- **Detector:** `test_a_finding_the_latest_earlier_record_lists_shown_wrong_is_carried` (three parameters: a `wrong`
  grade, no grade, a `plausible` grade).

Raw red:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
bringing up nodes...
bringing up nodes...

FFF                                                                      [100%]
=================================== FAILURES ===================================
_ test_a_finding_the_latest_earlier_record_lists_shown_wrong_is_carried[grade2] _
[gw2] linux -- Python 3.12.13 /root/.cache/uv/builds-v0/.tmpdsvNtc/bin/python

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-9/popen-gw2/test_a_finding_the_latest_earl0')
grade = {'verdict': 'plausible', 'reason': 'the verifier could not settle it'}

    @pytest.mark.parametrize("grade", [WRONG, None, PLAUSIBLE])
    def test_a_finding_the_latest_earlier_record_lists_shown_wrong_is_carried(tmp_path, grade):
        # axis: G3 the carry exception; an outcome the earlier record already stored stands whatever this account's grade says
        fake = Fake()
        first = wrong("a-1", reason="not a bug")
        assert write(tmp_path, fake, [first], verifier_closed=closed(first))["ok"]
        again = finding("a-1", outcome="shown-wrong", reason="not a bug", **({} if grade is None else {"grade": grade}))
        out = write(tmp_path, fake, [again])
>       assert out["ok"], out
E       AssertionError: {'ok': False, 'reason': 'review-account-invalid', 'detail': "findings[0] is shown-wrong without the verifier's grade"}
E       assert False

/home/user/wt-2211-a/plugins/superheroes/lib/tests/test_review_record_verifier_grade_c1l7.py:173: AssertionError
_ test_a_finding_the_latest_earlier_record_lists_shown_wrong_is_carried[grade0] _
[gw0] linux -- Python 3.12.13 /root/.cache/uv/builds-v0/.tmpdsvNtc/bin/python

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-9/popen-gw0/test_a_finding_the_latest_earl0')
grade = {'verdict': 'wrong', 'reason': 'the verifier showed the cited line does not exist'}

    @pytest.mark.parametrize("grade", [WRONG, None, PLAUSIBLE])
    def test_a_finding_the_latest_earlier_record_lists_shown_wrong_is_carried(tmp_path, grade):
        # axis: G3 the carry exception; an outcome the earlier record already stored stands whatever this account's grade says
        fake = Fake()
        first = wrong("a-1", reason="not a bug")
        assert write(tmp_path, fake, [first], verifier_closed=closed(first))["ok"]
        again = finding("a-1", outcome="shown-wrong", reason="not a bug", **({} if grade is None else {"grade": grade}))
        out = write(tmp_path, fake, [again])
>       assert out["ok"], out
E       AssertionError: {'ok': False, 'reason': 'review-account-invalid', 'detail': "findings[0] is shown-wrong without the verifier's grade"}
E       assert False

/home/user/wt-2211-a/plugins/superheroes/lib/tests/test_review_record_verifier_grade_c1l7.py:173: AssertionError
_ test_a_finding_the_latest_earlier_record_lists_shown_wrong_is_carried[None] __
[gw1] linux -- Python 3.12.13 /root/.cache/uv/builds-v0/.tmpdsvNtc/bin/python

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-9/popen-gw1/test_a_finding_the_latest_earl0')
grade = None

    @pytest.mark.parametrize("grade", [WRONG, None, PLAUSIBLE])
    def test_a_finding_the_latest_earlier_record_lists_shown_wrong_is_carried(tmp_path, grade):
        # axis: G3 the carry exception; an outcome the earlier record already stored stands whatever this account's grade says
        fake = Fake()
        first = wrong("a-1", reason="not a bug")
        assert write(tmp_path, fake, [first], verifier_closed=closed(first))["ok"]
        again = finding("a-1", outcome="shown-wrong", reason="not a bug", **({} if grade is None else {"grade": grade}))
        out = write(tmp_path, fake, [again])
>       assert out["ok"], out
E       AssertionError: {'ok': False, 'reason': 'review-account-invalid', 'detail': "findings[0] is shown-wrong without the verifier's grade"}
E       assert False

/home/user/wt-2211-a/plugins/superheroes/lib/tests/test_review_record_verifier_grade_c1l7.py:173: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_verifier_grade_c1l7.py::test_a_finding_the_latest_earlier_record_lists_shown_wrong_is_carried[grade2]
FAILED plugins/superheroes/lib/tests/test_review_record_verifier_grade_c1l7.py::test_a_finding_the_latest_earlier_record_lists_shown_wrong_is_carried[grade0]
FAILED plugins/superheroes/lib/tests/test_review_record_verifier_grade_c1l7.py::test_a_finding_the_latest_earlier_record_lists_shown_wrong_is_carried[None]
3 failed in 0.76s
```

- **Restore:** the inverse edit, `if not closed:` back to `if not (closed or _key(f) in carried):`.
- **Restore receipt:** `git status --porcelain plugins/superheroes/lib/review_record.py` and
  `git diff --stat -- plugins/superheroes/lib/review_record.py` both printed nothing. Restored lines
  (`sed -n 2341,2343p`):

```
        # axis: an outcome the earlier record already stored as shown-wrong is carried whatever this account's grade says — see bite-proof record c1l7_wo_a_verifier_grade
        if not (closed or _key(f) in carried):
            out.append(i)
```

Raw green:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
bringing up nodes...
bringing up nodes...

...                                                                      [100%]
3 passed in 0.71s
```

## G4: the merged member's emitted closing grade

- **Guarded element and axis:** `review_record_session.py:519`. A finding closed as wrong carries the closing
  representative's `wrong` grade, never the grade a merged member holds itself.
- **Neutralization:** `held["grade"] = rep["grade"]` became `held["grade"] = row.get("grade", rep["grade"])`, which
  emits the member's own grade when it has one.
- **Detector:** `test_a_session_written_record_stores_a_merged_group_closed_by_its_representative`. The member holds a
  `plausible` grade, so the write is refused.

Raw red:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
bringing up nodes...
bringing up nodes...

F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_session_written_record_stores_a_merged_group_closed_by_its_representative _
[gw1] linux -- Python 3.12.13 /root/.cache/uv/builds-v0/.tmpMyDxQA/bin/python

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-13/popen-gw1/test_a_session_written_record_0')

    def test_a_session_written_record_stores_a_merged_group_closed_by_its_representative(tmp_path):
        # axis: G4 the merged member's emitted closing grade; the member's own plausible grade would be refused as no wrong grade
        s = Session(tmp_path, dispositionLedger=merged_ledger()).seat("code-reviewer")
        fake = SessionFake()
        out = rs.write_from_session(s.save(), put_extras(tmp_path, extras()), str(tmp_path), fake.readers())
>       assert out["ok"], out
E       AssertionError: {'ok': False, 'reason': 'review-account-invalid', 'detail': "findings[0] is shown-wrong without the verifier's grade"}
E       assert False

/home/user/wt-2211-a/plugins/superheroes/lib/tests/test_review_record_verifier_grade_c1l7.py:235: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_verifier_grade_c1l7.py::test_a_session_written_record_stores_a_merged_group_closed_by_its_representative
1 failed in 1.09s
```

- **Restore:** the inverse edit, `row.get("grade", rep["grade"])` back to `rep["grade"]`.
- **Restore receipt:** `git status --porcelain` over `review_record_session.py` and `review_record.py` and
  `git diff --stat` over both printed nothing. Restored lines (`sed -n 517,519p`):

```
        if outcome == _SHOWN_WRONG:
            # axis: a finding closed as wrong carries the closing representative's wrong grade, never a merged member's own — see bite-proof record c1l7_wo_a_verifier_grade
            held["grade"] = rep["grade"]
```

Raw green:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
bringing up nodes...
bringing up nodes...

.                                                                        [100%]
1 passed in 1.15s
```
