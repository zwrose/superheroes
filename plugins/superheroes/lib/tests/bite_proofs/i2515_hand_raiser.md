# Bite-proof record — a hand-written account names its raiser (#2515)

Detector file: `plugins/superheroes/lib/tests/test_review_record_hand_raiser_2515.py`, unedited between each red and its green. Every entry is a targeted, reversible edit to `plugins/superheroes/lib/review_record.py` (`_derive_raisers`, `write`) or `plugins/superheroes/lib/review_record_session.py` (`write_from_session`), made and undone with the edit tool (no `git checkout`, `restore`, `reset` or `stash`). Runs: `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-2515 -m pytest plugins/superheroes/lib/tests/test_review_record_hand_raiser_2515.py -q -p no:cacheprovider -k "<fragment>"`. Each capture is the whole output of the run (no filter, no `tail`); the `UV_NATIVE_TLS` deprecation warning that `uv` prints first is the only line left out. No secret, token, URL or personal data appears in any capture, so nothing is redacted. The five guarded elements are the five the order declared (R1 to R5); none is grouped. R4 has a second entry, R4b, for the caller half of the same element.

## R1. The exactly-one count (`lib/review_record.py:2061`, `_derive_raisers`)

- **Axis:** two or more reviewers that ran leave the raiser unstated; the writer never guesses between them.
- **Detector:** `test_two_reviewers_ran_so_the_raiser_stays_unstated` (`-k two_reviewers`).
- **Neutralization:** `sole = ran[0] if len(ran) == 1 else None` became `sole = ran[0] if len(ran) >= 1 else None`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_____________ test_two_reviewers_ran_so_the_raiser_stays_unstated ______________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-2/test_two_reviewers_ran_so_the_0')

    def test_two_reviewers_ran_so_the_raiser_stays_unstated(tmp_path):
        # axis: E1, no guess between two reviewers that ran
        fake = Fake()
        hand(tmp_path, fake, reviewers=[reviewer(CODE), reviewer(SEC)], findings=[finding("f-1")])
>       assert raisers(fake) == {"f-1": None}
E       AssertionError: assert {'f-1': 'code-reviewer'} == {'f-1': None}
E         
E         Differing items:
E         {'f-1': 'code-reviewer'} != {'f-1': None}
E         Use -v to get more diff

/home/user/superheroes-wt-2515/plugins/superheroes/lib/tests/test_review_record_hand_raiser_2515.py:50: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_hand_raiser_2515.py::test_two_reviewers_ran_so_the_raiser_stays_unstated
1 failed, 7 deselected in 0.69s
```

**Restore:** the inverse edit put `== 1` back.
**Restore receipt** (the restored line, from a search of the file): `2061:    sole = ran[0] if len(ran) == 1 else None`

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed, 7 deselected in 0.97s
```

## R2. The held-by-earlier-record copy (`lib/review_record.py:2073`, `_derive_raisers`)

- **Axis:** a finding an earlier readable record holds takes that record's raiser, or stays without one; a relist is never credited to the reviewer that relisted it.
- **Detectors:** `test_a_relist_keeps_the_earlier_raiser_and_never_credits_the_relister` (cases e, both halves) and `test_one_write_with_a_relisted_and_a_new_finding_credits_each_its_own` (case f), selected together with `-k relist`.
- **Neutralization:** `if held is not None:` became `if False and held is not None:`, so a held finding is treated as new.

**Raw red** (exit 1):

```
FF                                                                       [100%]
=================================== FAILURES ===================================
____ test_a_relist_keeps_the_earlier_raiser_and_never_credits_the_relister _____

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-4/test_a_relist_keeps_the_earlie0')

    def test_a_relist_keeps_the_earlier_raiser_and_never_credits_the_relister(tmp_path):
        # axis: a finding an earlier record holds takes that record's raiser, or none, never the reviewer that relisted it
        fake = Fake()
        hand(tmp_path, fake, sid="s1", reviewers=[reviewer(SEC)], findings=[finding("f-1", raisedBy=SEC)])
        hand(tmp_path, fake, sid="s2", reviewers=[reviewer(CODE)], findings=[finding("f-1")])
>       assert raisers(fake) == {"f-1": SEC}
E       AssertionError: assert {'f-1': 'code-reviewer'} == {'f-1': 'security-reviewer'}
E         
E         Differing items:
E         {'f-1': 'code-reviewer'} != {'f-1': 'security-reviewer'}
E         Use -v to get more diff

/home/user/superheroes-wt-2515/plugins/superheroes/lib/tests/test_review_record_hand_raiser_2515.py:79: AssertionError
____ test_one_write_with_a_relisted_and_a_new_finding_credits_each_its_own _____

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-4/test_one_write_with_a_relisted0')

    def test_one_write_with_a_relisted_and_a_new_finding_credits_each_its_own(tmp_path):
        # axis: the relisted finding keeps its earlier raiser while the new one in the same write takes the sole reviewer
        fake = Fake()
        hand(tmp_path, fake, sid="s1", reviewers=[reviewer(SEC)], findings=[finding("f-1", raisedBy=SEC)])
        hand(tmp_path, fake, sid="s2", reviewers=[reviewer(CODE)], findings=[finding("f-1"), finding("f-2", line=9)])
>       assert raisers(fake) == {"f-1": SEC, "f-2": CODE}
E       AssertionError: assert {'f-1': 'code...ode-reviewer'} == {'f-1': 'secu...ode-reviewer'}
E         
E         Omitting 1 identical items, use -vv to show
E         Differing items:
E         {'f-1': 'code-reviewer'} != {'f-1': 'security-reviewer'}
E         Use -v to get more diff

/home/user/superheroes-wt-2515/plugins/superheroes/lib/tests/test_review_record_hand_raiser_2515.py:92: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_hand_raiser_2515.py::test_a_relist_keeps_the_earlier_raiser_and_never_credits_the_relister
FAILED plugins/superheroes/lib/tests/test_review_record_hand_raiser_2515.py::test_one_write_with_a_relisted_and_a_new_finding_credits_each_its_own
2 failed, 6 deselected in 2.81s
```

**Restore:** the inverse edit put `if held is not None:` back.
**Restore receipt** (the restored line, from a search of the file): `2073:        if held is not None:`

**Raw green** (exit 0):

```
..                                                                       [100%]
2 passed, 6 deselected in 0.81s
```

## R3. The unreadable-earlier stop (`lib/review_record.py:3601`, `write`)

- **Axis:** when any earlier record of the PR could not be read, no raiser is derived for any finding on that write, while a raiser held by a readable earlier record is still copied.
- **Detector:** `test_an_unreadable_earlier_record_stops_the_derivation_but_not_the_copy` (case g, `-k unreadable`).
- **Neutralization:** `earlier_unreadable = any(n["why"] == "unreadable" for n in not_checked)` became `earlier_unreadable = False`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
___ test_an_unreadable_earlier_record_stops_the_derivation_but_not_the_copy ____

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-6/test_an_unreadable_earlier_rec0')

    def test_an_unreadable_earlier_record_stops_the_derivation_but_not_the_copy(tmp_path):
        # axis: E4, an unreadable earlier record might hold the finding, so a new finding gets no raiser
        fake = Fake()
        hand(tmp_path, fake, sid="s1", reviewers=[reviewer(SEC)], findings=[finding("f-1", raisedBy=SEC)])
        fake.comments.append({"id": len(fake.comments) + 1, "author": "a", "body": rr.MARKER + "\nhand edited", "url": "u-broken"})
        hand(tmp_path, fake, sid="s2", reviewers=[reviewer(CODE)], findings=[finding("f-1"), finding("f-2", line=9)])
        rec = rr.read(7, readers=fake.readers())
        assert rec["earlierRecordsNotChecked"][0]["why"] == "unreadable"
>       assert raisers(fake) == {"f-1": SEC, "f-2": None}
E       AssertionError: assert {'f-1': 'secu...ode-reviewer'} == {'f-1': 'secu..., 'f-2': None}
E         
E         Omitting 1 identical items, use -vv to show
E         Differing items:
E         {'f-2': 'code-reviewer'} != {'f-2': None}
E         Use -v to get more diff

/home/user/superheroes-wt-2515/plugins/superheroes/lib/tests/test_review_record_hand_raiser_2515.py:103: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_hand_raiser_2515.py::test_an_unreadable_earlier_record_stops_the_derivation_but_not_the_copy
1 failed, 7 deselected in 0.93s
```

**Restore:** the inverse edit put the `any(...)` expression back.
**Restore receipt** (the restored line, from a search of the file): `3601:        earlier_unreadable = any(n["why"] == "unreadable" for n in not_checked)`

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed, 7 deselected in 1.21s
```

## R4. The session flag, at the writer (`lib/review_record.py:3603`, `write`)

- **Axis:** the full-lane session writer's records are never touched: a write that comes from the session derives no raiser, so absence stays absence.
- **Detector:** `test_the_session_writers_write_derives_nothing` (case h, `-k session_writers`).
- **Neutralization:** `derive_raiser=not from_session,` became `derive_raiser=True,`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
________________ test_the_session_writers_write_derives_nothing ________________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-8/test_the_session_writers_write0')

    def test_the_session_writers_write_derives_nothing(tmp_path):
        # axis: E5, the full-lane session writer's records are never touched, so absence stays absence
        fake = Fake()
        path = put(tmp_path, account(findings=[finding("f-1")]))
        assert rr.write(path, str(tmp_path), fake.readers(), from_session=True)["ok"]
>       assert raisers(fake) == {"f-1": None}
E       AssertionError: assert {'f-1': 'code-reviewer'} == {'f-1': None}
E         
E         Differing items:
E         {'f-1': 'code-reviewer'} != {'f-1': None}
E         Use -v to get more diff

/home/user/superheroes-wt-2515/plugins/superheroes/lib/tests/test_review_record_hand_raiser_2515.py:111: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_hand_raiser_2515.py::test_the_session_writers_write_derives_nothing
1 failed, 7 deselected in 0.70s
```

**Restore:** the inverse edit put `derive_raiser=not from_session,` back.
**Restore receipt** (the restored line, from a search of the file): `3603:                              derive_raiser=not from_session, earlier=earlier, earlier_unreadable=earlier_unreadable)`

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed, 7 deselected in 0.86s
```

## R4b. The session flag, at the caller (`lib/review_record_session.py:1968`, `write_from_session`)

- **Axis:** `write_from_session` marks its write as the session's. The R4 detector calls `rr.write` directly, so it cannot see this call site; this entry's detector spies on the kwargs `write_from_session` hands `rr.write`.
- **Detector:** `test_the_session_writer_hands_the_writer_the_session_flag` (`-k session_flag`). It asserts the kwarg, not a record, so it proves the pass and nothing about a derived raiser.
- **Neutralization:** `session_uncertified=account.get("uncertified"), from_session=True)` became `session_uncertified=account.get("uncertified"))`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
__________ test_the_session_writer_hands_the_writer_the_session_flag ___________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-19/test_the_session_writer_hands_0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7f11f76e94f0>

    def test_the_session_writer_hands_the_writer_the_session_flag(tmp_path, monkeypatch):
        # axis: E5 at the caller, `write_from_session` marks its write as the session's so no raiser is derived
        seen = {}
        real = rr.write

        def spy(*args, **kwargs):
            seen.update(kwargs)
            return real(*args, **kwargs)
        monkeypatch.setattr(rr, "write", spy)
        session = Session(tmp_path, terminal=None).save()
        out = rs.write_from_session(session, put_extras(tmp_path, extras(ci="green")), str(tmp_path),
                                    SessionFake().readers(), abandoned="stopped before any seat ran")
        assert out["ok"], out
>       assert seen.get("from_session") is True
E       AssertionError: assert None is True
E        +  where None = <built-in method get of dict object at 0x7f11f5236980>('from_session')
E        +    where <built-in method get of dict object at 0x7f11f5236980> = {'verifier_closed': set(), 'session_uncertified': None}.get

/home/user/superheroes-wt-2515/plugins/superheroes/lib/tests/test_review_record_hand_raiser_2515.py:131: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_hand_raiser_2515.py::test_the_session_writer_hands_the_writer_the_session_flag
1 failed, 8 deselected in 1.89s
```

**Restore:** the inverse edit put `, from_session=True` back.
**Restore receipt** (the restored line, from a search of the file): `1968:                                   session_uncertified=account.get("uncertified"), from_session=True)`

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed, 8 deselected in 2.02s
```

## R5. The not-run and carried exclusion (`lib/review_record.py:2060`, `_derive_raisers`)

- **Axis:** a reviewer row the writer demotes to not-run neither counts as a second reviewer that ran nor is the one that ran; with none that ran the raiser stays unstated.
- **Detector:** `test_a_row_that_did_not_run_is_not_counted_and_none_ran_is_unstated` (case c, `-k not_counted`).
- **Neutralization:** `ran = [v["name"] for v in reviewers if v["ran"] != RAN_NOT_RUN and "carried" not in v]` became `ran = [v["name"] for v in reviewers]`, so every row counts.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_____ test_a_row_that_did_not_run_is_not_counted_and_none_ran_is_unstated ______

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-10/test_a_row_that_did_not_run_is0')

    def test_a_row_that_did_not_run_is_not_counted_and_none_ran_is_unstated(tmp_path):
        # axis: E2 and the not-run exclusion, a row that did not run neither makes two nor is the one
        # the writer demotes a row whose run record it cannot read to not-run, whatever the account says
        fake = Fake()
        fake.runs["/run/" + SEC] = (None, "no run record")
        hand(tmp_path, fake, reviewers=[reviewer(SEC), reviewer(CODE)], findings=[finding("f-1")])
        assert [v["ran"] for v in rr.read(7, readers=fake.readers())["reviewers"]] == ["not-run", "engine-record"]
>       assert raisers(fake) == {"f-1": CODE}
E       AssertionError: assert {'f-1': None} == {'f-1': 'code-reviewer'}
E         
E         Differing items:
E         {'f-1': None} != {'f-1': 'code-reviewer'}
E         Use -v to get more diff

/home/user/superheroes-wt-2515/plugins/superheroes/lib/tests/test_review_record_hand_raiser_2515.py:60: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_hand_raiser_2515.py::test_a_row_that_did_not_run_is_not_counted_and_none_ran_is_unstated
1 failed, 7 deselected in 0.68s
```

**Restore:** the first inverse edit did not apply (the neutralizing edit had also dropped the space after `sole =` on the next line, so my match text was wrong). The re-run after it was therefore still red, with the same failure as above (`1 failed, 7 deselected in 0.92s`). A second edit restored both lines at once.
**Restore receipt** (the restored lines, from a search of the file): `2060:    ran = [v["name"] for v in reviewers if v["ran"] != RAN_NOT_RUN and "carried" not in v]` and `2061:    sole = ran[0] if len(ran) == 1 else None`

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed, 7 deselected in 0.69s
```

## Not proven (outside what the detectors can tell apart)

- The `"carried" not in v` half of R5's exclusion: the neutralization removed both clauses and the red came from the not-run clause alone. No test builds a carried row (that needs a carried review with its git proof), so a record with a carried row beside one that ran is not discriminated by this file.
- A blank-string `raisedBy` on an account: the account validator refuses it before the writer sees it, so the helper's "non-blank" test on the account's own value is not reachable through `write`; its blank test on an earlier record's `raisedBy` is not exercised either.
- The newest-first order among several older readable records (`reversed(history)`): the tests give at most one older readable record, so a swapped order is not discriminated.
