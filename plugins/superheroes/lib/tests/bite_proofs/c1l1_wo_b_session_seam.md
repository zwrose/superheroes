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

# WO-D additions

Three entries, one per guarded element the WO-D order declared (BP-D1 to BP-D3). None is grouped. Same method as
above: each red and green is the raw output of the single node run alone, nothing filtered; each neutralization was
one targeted `Edit` to `plugins/superheroes/lib/review_record_session.py`, restored by the inverse `Edit`, with the
restored lines quoted back by a `grep -n` over the file. The captures are unredacted: they hold no secret, token or
private URL.

What the reds do and do not show, stated once: BP-D2 removes the phase, seat and taxonomy restriction together
(one `settled` expression), and its node (a gap-sweep finding) is red for the phase part. The seat and taxonomy
parts are not each neutralized on their own; the cases they guard are read by the parametrized node
`test_a_finding_the_passed_rule_does_not_cover_is_listed_open` (E1 to E4) and by
`test_a_code_reviewer_finding_sharing_a_passed_proposals_title_and_file_is_listed_open`, which were not run red.

## BP-D1. the line in the compile-drop key

- Axis: the compile-drop skip matches round, title, file and line, so a same-titled finding at another line stays listed.
- Neutralization (`review_record_session.py`, `_unfolded`): `_line_key(...)` was dropped from both tuples: `dropped = {(d["round"], d["title"], d["file"], _line_key(d["line"])) for ...}` became `dropped = {(d["round"], d["title"], d["file"]) for ...}`, and `(rnd, f["title"], f.get("file"), _line_key(f.get("line"))) in dropped` became `(rnd, f["title"], f.get("file")) in dropped`.
- Node: `plugins/superheroes/lib/tests/test_review_record_abandoned_2137.py::test_a_same_titled_finding_at_another_line_survives_a_compile_drop_in_an_abandoned_session`

Red:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_same_titled_finding_at_another_line_survives_a_compile_drop_in_an_abandoned_session _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-53/test_a_same_titled_finding_at_0')

    def test_a_same_titled_finding_at_another_line_survives_a_compile_drop_in_an_abandoned_session(tmp_path):
        """axis: the compile-drop match includes the line, so only the dropped location is left out of the unfolded rows."""
        drop = {"title": "Same title", "file": "a.py", "line": 10, "reason": "out of scope"}
        got = _abandoned_titles(tmp_path, {"1": {"compileDrops": [drop]}}, [
            {"title": "Same title", "file": "a.py", "line": 10, "severity": "Important", "consequence": "c"},
            {"title": "Same title", "file": "a.py", "line": 20, "severity": "Important", "consequence": "c"}])
>       assert got == [("Same title", 20)]
E       AssertionError: assert [] == [('Same title', 20)]
E         
E         Right contains one more item: ('Same title', 20)
E         Use -v to get more diff

/home/user/wt/build/plugins/superheroes/lib/tests/test_review_record_abandoned_2137.py:177: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_abandoned_2137.py::test_a_same_titled_finding_at_another_line_survives_a_compile_drop_in_an_abandoned_session
1 failed in 0.72s
```

Restore: the inverse edit on both lines. Restored lines quoted back (`grep -n "dropped = \|in dropped"`):

```
602:    dropped = {(d["round"], d["title"], d["file"], _line_key(d["line"])) for d in _refused(rounds)}
620:            if fkey in listed or (rnd, f["title"], f.get("file"), _line_key(f.get("line"))) in dropped or settled:
```

Green:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 0.52s
```

## BP-D2. the passed-proposal skip covers only the test role's panel proposal

- Axis: the skip for a passing break-it run needs the panel phase, the test-role seat and the break-it taxonomy; a gap-sweep finding of the same title and file at another line stays listed.
- Neutralization (`review_record_session.py`, `_unfolded`): the restriction was removed: `settled = phase == round_phases.P_PANEL and seat == break_it.ROLE and break_it.is_break_it(f) \` followed by `and (rnd, f["title"], f.get("file")) in passed` became `settled = (rnd, f["title"], f.get("file")) in passed`.
- Node: `plugins/superheroes/lib/tests/test_review_record_abandoned_2137.py::test_a_gap_sweep_finding_sharing_a_passed_proposals_title_and_file_is_listed_open`

Red:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_gap_sweep_finding_sharing_a_passed_proposals_title_and_file_is_listed_open _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-55/test_a_gap_sweep_finding_shari0')

    def test_a_gap_sweep_finding_sharing_a_passed_proposals_title_and_file_is_listed_open(tmp_path):
        """axis: the passed-proposal skip settles only the test role's panel proposal; a gap-sweep finding of the same title
        and file at another line stays open — see bite-proof record c1l1_wo_b_session_seam"""
        got = _abandoned_slots(tmp_path, {"1": {"breakItRuns": [PASSED_RUN]}}, [
            ("test-role", PANEL, 1, [PROPOSAL]), ("gap-sweep", GAPSWEEP, 1, [SAME_PLACE])])
>       assert got == [("Break it", 9)]
E       AssertionError: assert [] == [('Break it', 9)]
E         
E         Right contains one more item: ('Break it', 9)
E         Use -v to get more diff

/home/user/wt/build/plugins/superheroes/lib/tests/test_review_record_abandoned_2137.py:199: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_abandoned_2137.py::test_a_gap_sweep_finding_sharing_a_passed_proposals_title_and_file_is_listed_open
1 failed in 3.49s
```

Restore: the inverse edit. Restored lines quoted back (`grep -n -A1 "settled = "`):

```
618:            settled = phase == round_phases.P_PANEL and seat == break_it.ROLE and break_it.is_break_it(f) \
619-                and (rnd, f["title"], f.get("file")) in passed
```

Green:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 0.61s
```

## BP-D3. a synthesis seat recorded missing is not a synthesis round

- Axis: `_synthesis_rounds` skips a journal row whose `cmd` is `record-missing`, though its `outcome` is `recorded`.
- Neutralization (`review_record_session.py`, `_synthesis_rounds`): the condition `r.get("cmd") != "record-missing" and` was removed.
- Node: `plugins/superheroes/lib/tests/test_review_record_session_c1l1.py::test_a_synthesis_seat_recorded_missing_is_not_a_synthesis_round`

Red:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_______ test_a_synthesis_seat_recorded_missing_is_not_a_synthesis_round ________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-57/test_a_synthesis_seat_recorded0')

    def test_a_synthesis_seat_recorded_missing_is_not_a_synthesis_round(tmp_path):
        # axis: a record-missing synthesis row (outcome "recorded") is no result; record-result and a row with no cmd count — see bite-proof record c1l1_wo_b_session_seam
        missing = Session(tmp_path).seat("code-reviewer")
        missing.rows.append(dict(SYNTHESIS, round=1, cmd="record-missing"))
>       assert "synthesisRounds" not in _account(missing.save())
E       AssertionError: assert 'synthesisRounds' not in {'schema': 'review-account/1', 'pr': 7, 'repo': None, 'lane': 'full', ...}
E        +  where {'schema': 'review-account/1', 'pr': 7, 'repo': None, 'lane': 'full', ...} = _account('/tmp/claude-0/pytest-of-root/pytest-57/test_a_synthesis_seat_recorded0/session')
E        +    where '/tmp/claude-0/pytest-of-root/pytest-57/test_a_synthesis_seat_recorded0/session' = save()
E        +      where save = <test_review_record_session.Session object at 0x7f80a28de660>.save

/home/user/wt/build/plugins/superheroes/lib/tests/test_review_record_session_c1l1.py:132: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_session_c1l1.py::test_a_synthesis_seat_recorded_missing_is_not_a_synthesis_round
1 failed in 0.50s
```

Restore: the inverse edit. Restored lines quoted back (`grep -n -B1 -A1 'record-missing'`, the `_synthesis_rounds` hit):

```
572-    return sorted({r["round"] for r in rows if r.get("outcome") == "recorded" and r.get("phase") == round_phases.P_SYNTHESIS
573:                   and r.get("cmd") != "record-missing" and _int(r.get("round"))})
```

Green:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 0.59s
```
