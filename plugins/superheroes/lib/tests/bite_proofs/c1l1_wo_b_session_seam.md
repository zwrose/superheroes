# C1 L1 WO-B bite-proof record: the session adapter carries the record's new parts and loses no finding

Four entries, one per guarded element the order declared (BP-B1 to BP-B4). None is grouped. Every red and green below
is the raw output of the single test node run alone (`scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc
-m pytest "<node>" -q`, run from the worktree root); nothing is filtered. Each neutralization was one targeted `Edit`
to `plugins/superheroes/lib/review_record_session.py`, restored by the inverse `Edit`; the restored line is quoted
back by a `grep -n` over the file in each entry (the restore receipt). The captures are unredacted: they hold no
secret, token or private URL. The `warning: The UV_NATIVE_TLS ...` line is the launcher's, not the test's.

Node file for every entry: `plugins/superheroes/lib/tests/test_review_record_session_c1l1.py`.

What the reds do and do not show, stated once:

- BP-B1 neutralizes the fallback for all four finding parts together (`grade`, `repeatOf`, `breakItRuns`,
  `kindOfMistake`) because they share one loop in `_finding_parts`; the node asserts all four, so the red names the
  first part the assertion reads (`grade`). The other three parts are not each neutralized on their own.
- BP-B4 neutralizes the whole fill step; the node asserts the grade, repeat mark and kind of mistake fill and the
  runs order, and the red names the first assertion that fails (`grade`). The break-it merge order and the
  no-duplicate rule inside `_fill` are not each neutralized on their own; the no-duplicate rule is also read by
  `test_e12_a_break_it_run_both_sides_hold_is_kept_once`.
- BP-B2 neutralizes the whole open-row list for an abandoned session; the dedupe rules inside `_unfolded` (account
  key, earlier unfolded row) are read by `test_e6_` and `test_e7_` and were not neutralized on their own.

## BP-B1. a newer row never erases a finding part an older row held

- Axis: per-field preservation, the live row's value, else the ledger row's, else absent (E1).
- Neutralization (`review_record_session.py`, `_finding_parts`): `for src in (row, older):` became `for src in (row,):`.
- Node: `test_e1_a_live_row_without_a_part_keeps_the_ledger_rows`

Red:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
___________ test_e1_a_live_row_without_a_part_keeps_the_ledger_rows ____________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-41/test_e1_a_live_row_without_a_p0')

    def test_e1_a_live_row_without_a_part_keeps_the_ledger_rows(tmp_path):
        # axis: a newer row never erases a finding part an older row held, for each of the four parts — see bite-proof record c1l1_wo_b_session_seam
        session = Session(tmp_path, findings=[LIVE], dispositionLedger=[ledger_row(**VALUES)]).seat("code-reviewer").save()
        (row,) = _account(session)["findings"]
>       assert {p: row[p] for p in PARTS} == VALUES
                   ^^^^^^
E       KeyError: 'grade'

/home/user/wt/build/plugins/superheroes/lib/tests/test_review_record_session_c1l1.py:84: KeyError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_session_c1l1.py::test_e1_a_live_row_without_a_part_keeps_the_ledger_rows
1 failed in 1.98s
```

Restore: the inverse edit. Restored line quoted back (`grep -n "for src in (row, older)"`):

```
469:        for src in (row, older):
```

Green:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 0.73s
```

## BP-B2. an abandoned session lists the unfolded findings open

- Axis: a finding recorded in a stored seat result and never taken into the loop is listed open, with the unfolded reason.
- Neutralization (`review_record_session.py`, `account_from_session`): `findings += _unfolded(session_dir, rows, rounds, findings)` became `findings += _unfolded(session_dir, rows, rounds, findings)[:0]`.
- Node: `test_crash_before_the_fold_lists_the_unfolded_finding_open`

Red:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
__________ test_crash_before_the_fold_lists_the_unfolded_finding_open __________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-43/test_crash_before_the_fold_lis0')

    def test_crash_before_the_fold_lists_the_unfolded_finding_open(tmp_path):
        # axis: an abandoned session lists a finding recorded in a stored seat result and never folded, open, with its reviewer — see bite-proof record c1l1_wo_b_session_seam
        account = _account(_abandoned(tmp_path), REASON)
>       (row,) = account["findings"]
        ^^^^^^
E       ValueError: not enough values to unpack (expected 1, got 0)

/home/user/wt/build/plugins/superheroes/lib/tests/test_review_record_session_c1l1.py:161: ValueError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_session_c1l1.py::test_crash_before_the_fold_lists_the_unfolded_finding_open
1 failed in 0.57s
```

Restore: the inverse edit. Restored line quoted back (`grep -n "findings += _unfolded"`):

```
655:        findings += _unfolded(session_dir, rows, rounds, findings)
```

Green:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 0.59s
```

## BP-B3. a finding the round's compile dropped is not listed a second time

- Axis: the compile-drop skip, same round, same title, same file (`None` matching `None`); the finding stays under `refused` (E8).
- Neutralization (`review_record_session.py`, `_unfolded`): `if fkey in listed or (rnd, f["title"], f.get("file")) in dropped:` became `if fkey in listed:`.
- Node: `test_e8_an_unfolded_finding_the_compile_dropped_stays_under_refused`

Red:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_____ test_e8_an_unfolded_finding_the_compile_dropped_stays_under_refused ______

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-45/test_e8_an_unfolded_finding_th0')

    def test_e8_an_unfolded_finding_the_compile_dropped_stays_under_refused(tmp_path):
        # axis: a finding the round's compile dropped is accounted for under refused and not listed a second time — see bite-proof record c1l1_wo_b_session_seam
        drops = [{"title": "Dropped", "file": "a.py", "line": 1, "reason": "no consequence named"},
                 {"title": "No file", "file": None, "line": None, "reason": "no place named"}]
        found = [{"title": "Dropped", "file": "a.py", "line": 1}, {"title": "Dropped", "file": "b.py", "line": 1},
                 {"title": "Dropped", "file": None, "line": 1}, {"title": "No file"}]
        account = _account(_abandoned(tmp_path, seats=(("code-reviewer", found),), rounds={"1": {"compileDrops": drops}}), REASON)
>       assert [(f["title"], f["file"]) for f in account["findings"]] == [("Dropped", "b.py"), ("Dropped", None)]
E       AssertionError: assert [('Dropped', ... file', None)] == [('Dropped', ...opped', None)]
E         
E         At index 0 diff: ('Dropped', 'a.py') != ('Dropped', 'b.py')
E         Left contains 2 more items, first extra item: ('Dropped', None)
E         Use -v to get more diff

/home/user/wt/build/plugins/superheroes/lib/tests/test_review_record_session_c1l1.py:203: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_session_c1l1.py::test_e8_an_unfolded_finding_the_compile_dropped_stays_under_refused
1 failed in 0.67s
```

Restore: the inverse edit. Restored line quoted back (`grep -n 'if fkey in listed'`):

```
595:            if fkey in listed or (rnd, f["title"], f.get("file")) in dropped:
```

Green:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 0.67s
```

## BP-B4. the fill from the earlier record

- Axis: a row lacking `grade`, `repeatOf` or `kindOfMistake` takes the earlier record's; the earlier `breakItRuns` lead, this session's new run follows.
- Neutralization (`review_record_session.py`, `write_from_session`): the line `_fill(account, earlier)` was removed.
- Node: `test_fill_the_earlier_grade_and_runs_survive_a_later_session_that_lacks_them`

Red:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_fill_the_earlier_grade_and_runs_survive_a_later_session_that_lacks_them _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-47/test_fill_the_earlier_grade_an0')

    def test_fill_the_earlier_grade_and_runs_survive_a_later_session_that_lacks_them(tmp_path):
        # axis: a later row without a grade gets the earlier one, and the earlier runs come before the new run — see bite-proof record c1l1_wo_b_session_seam
        fake = Fake()
        first = Session(tmp_path, dispositionLedger=[ledger_row(grade=GRADE, repeatOf=REPEAT, breakItRuns=[RUN_1])]).seat("code-reviewer").save()
        assert send(tmp_path, first, fake)["ok"]
        second = _later(tmp_path, "b", dispositionLedger=[ledger_row(breakItRuns=[RUN_2], kindOfMistake=KIND)])
        assert send(tmp_path, second, fake)["ok"]
        (row,) = _record(fake)["findings"]
>       assert row["grade"] == GRADE and row["repeatOf"] == REPEAT and row["kindOfMistake"] == KIND
               ^^^^^^^^^^^^
E       KeyError: 'grade'

/home/user/wt/build/plugins/superheroes/lib/tests/test_review_record_session_c1l1.py:259: KeyError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_session_c1l1.py::test_fill_the_earlier_grade_and_runs_survive_a_later_session_that_lacks_them
1 failed in 0.77s
```

Restore: the inverse edit. Restored lines quoted back (`grep -n -B1 -A1 '_fill(account, earlier)'`, the `write_from_session` hit):

```
816-        earlier = _earlier(account, extras, repo_root, readers)
817:        _fill(account, earlier)
818-        account["findings"] += _carried(account, earlier)
```

Green:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 0.65s
```
