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

# WO-E additions

Four entries, one per guarded element the WO-E order declared (BP-E1 to BP-E4). None is grouped. Same method as
above: each red and green is the raw output of the single node run alone, nothing filtered; each neutralization was
one targeted `Edit` to `plugins/superheroes/lib/review_record_session.py`, restored by the inverse `Edit`, with the
restored lines quoted back by a `grep -n` over the file. The captures are unredacted: they hold no secret, token or
private URL (the secret-shaped value in BP-E3's test is built from pieces at runtime, so no whole credential-like
literal appears).

The order asked for each regression's red run on the code before the change. For M2 and M3 that run was made before
the code was changed (one pytest call over the four new nodes: 2 failed, 2 passed; the two failures are the M2
no-file node and the M3 scrub node, and their failure text matches BP-E2's and BP-E3's reds below). The two nodes
that passed there are the edge nodes (E1, E2), which pin behaviour the change keeps. For M4 the M4 code edit was
made before any run, so there is no run on the unchanged code; BP-E4's neutralization restores exactly the
pre-change condition (`r.get("outcome") == "recorded"`), and its red stands in for that run.

## BP-E1. a boolean synthesis round is not counted

- Axis: `_synthesis_rounds` counts only rows whose `round` is an int and not a bool (`_int`); the boolean row now sits in a case of its own, so `True == 1` can no longer collapse it into a real round-1 row.
- Neutralization (`review_record_session.py`, `_synthesis_rounds`): `_int(r.get("round"))` became `isinstance(r.get("round"), int)`.
- Node: `plugins/superheroes/lib/tests/test_review_record_session_c1l1.py::test_e5_only_a_recorded_synthesis_row_with_an_int_round_counts`

Red:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
________ test_e5_only_a_recorded_synthesis_row_with_an_int_round_counts ________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-61/test_e5_only_a_recorded_synthe0')

    def test_e5_only_a_recorded_synthesis_row_with_an_int_round_counts(tmp_path):
        # axis: synthesisRounds lists the sorted distinct rounds of recorded synthesis rows with an int round
        s = Session(tmp_path, rounds={"1": {}, "2": {}, "3": {}}).seat("code-reviewer")
        s.rows += [dict(SYNTHESIS, round=2), dict(SYNTHESIS, round=1), dict(SYNTHESIS, round=1, attempt=1),
                   dict(SYNTHESIS, round=3, outcome="rejected"), dict(SYNTHESIS, round="3"), dict(SYNTHESIS, round=None)]
        assert _account(s.save())["synthesisRounds"] == [1, 2]
        bare = Session(_sub(tmp_path, "b")).seat("code-reviewer")
        bare.rows.append(dict(SYNTHESIS, round=1, outcome="rejected"))
        assert "synthesisRounds" not in _account(bare.save())
        # a boolean round alone: True == 1, so beside a real round-1 row it would collapse into it and hide an accepted bool
        boolean = Session(_sub(tmp_path, "c")).seat("code-reviewer")
        boolean.rows.append(dict(SYNTHESIS, round=True))
>       assert "synthesisRounds" not in _account(boolean.save())
E       AssertionError: assert 'synthesisRounds' not in {'schema': 'review-account/1', 'pr': 7, 'repo': None, 'lane': 'full', ...}
E        +  where {'schema': 'review-account/1', 'pr': 7, 'repo': None, 'lane': 'full', ...} = _account('/tmp/claude-0/pytest-of-root/pytest-61/test_e5_only_a_recorded_synthe0/c/session')
E        +    where '/tmp/claude-0/pytest-of-root/pytest-61/test_e5_only_a_recorded_synthe0/c/session' = save()
E        +      where save = <test_review_record_session.Session object at 0x7f21295d0ef0>.save

/home/user/wt/build/plugins/superheroes/lib/tests/test_review_record_session_c1l1.py:128: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_session_c1l1.py::test_e5_only_a_recorded_synthesis_row_with_an_int_round_counts
1 failed in 0.67s
```

(The axis comment line in the red output is the one before it was extended with the record pointer; the test body is the same.)

Restore: the inverse edit. Restored lines quoted back (`grep -n -B3 '_int(r.get("round"))})'`, the `_synthesis_rounds` hit):

```
575:    return sorted({r["round"] for r in rows if r.get("outcome") in ("recorded", "accepted")
576-                   and r.get("phase") == round_phases.P_SYNTHESIS
577:                   and r.get("cmd") != "record-missing" and _int(r.get("round"))})
```

Green:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 0.66s
```

## BP-E2. a compile drop with no string file is matched without its line

- Axis: `_drop_key` leaves the line out of the key when the file is not a string (the drop was recorded without its line); a string-file drop stays line-exact (null against null only).
- Neutralization (`review_record_session.py`, `_drop_key`): `_line_key(line) if isinstance(file, str) else None` became `_line_key(line)`.
- Node: `plugins/superheroes/lib/tests/test_review_record_abandoned_2137.py::test_a_compile_drop_with_no_file_and_no_line_matches_its_finding_on_round_and_title_in_an_abandoned_session`

Red:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_compile_drop_with_no_file_and_no_line_matches_its_finding_on_round_and_title_in_an_abandoned_session _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-63/test_a_compile_drop_with_no_fi0')

    def test_a_compile_drop_with_no_file_and_no_line_matches_its_finding_on_round_and_title_in_an_abandoned_session(tmp_path):
        """axis: a drop whose file is not a string lost its line, so it is matched on round, title and file alone; a drop with a
        string file stays line-exact — see bite-proof record c1l1_wo_b_session_seam"""
        drop = {"title": "Same title", "file": None, "line": None, "reason": "no file to cite"}
        got = _abandoned_titles(tmp_path, {"1": {"compileDrops": [drop]}}, [
            {"title": "Same title", "file": None, "line": 7, "severity": "Important", "consequence": "c"},
            {"title": "Same title", "file": "a.py", "line": 9, "severity": "Important", "consequence": "c"}])
>       assert got == [("Same title", 9)]
E       AssertionError: assert [('Same title...me title', 9)] == [('Same title', 9)]
E         
E         At index 0 diff: ('Same title', 7) != ('Same title', 9)
E         Left contains one more item: ('Same title', 9)
E         Use -v to get more diff

/home/user/wt/build/plugins/superheroes/lib/tests/test_review_record_abandoned_2137.py:187: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_abandoned_2137.py::test_a_compile_drop_with_no_file_and_no_line_matches_its_finding_on_round_and_title_in_an_abandoned_session
1 failed in 1.12s
```

Restore: the inverse edit. Restored line quoted back (`grep -n 'return (rnd, title'`):

```
595:    return (rnd, title, _file_key(file), _line_key(line) if isinstance(file, str) else None)
```

Green:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 0.60s
```

## BP-E3. a current break-it run is compared in its scrubbed form

- Axis: `_fill` compares each current run, through `review_record._scrubbed`, against the earlier runs (which come from the scrubbed posted record), so a run the scrub changed is not appended again on a rewrite.
- Neutralization (`review_record_session.py`, `_fill`): `if (review_record._scrubbed(run) if isinstance(run, dict) else run) not in runs:` became `if run not in runs:`.
- Node: `plugins/superheroes/lib/tests/test_review_record_session_c1l1.py::test_fill_a_current_run_the_scrub_changed_is_not_appended_again_beside_its_scrubbed_earlier_form`

Red:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_fill_a_current_run_the_scrub_changed_is_not_appended_again_beside_its_scrubbed_earlier_form _

    def test_fill_a_current_run_the_scrub_changed_is_not_appended_again_beside_its_scrubbed_earlier_form():
        # axis: the earlier runs come from the scrubbed posted record, so a current run is compared in its scrubbed form — see bite-proof record c1l1_wo_b_session_seam
        raw = dict(RUN_1, output="setup ok " + "pass" + "word=" + "x" * 12)
        scrubbed = rr._scrubbed(raw)
        assert scrubbed != raw  # the premise: the writer's scrub changes this run
        account = {"findings": [dict(LIVE, breakItRuns=[raw])]}
        rs._fill(account, [dict(LIVE, breakItRuns=[scrubbed])])
>       assert account["findings"][0]["breakItRuns"] == [scrubbed]
E       AssertionError: assert [{'test': 'te...ode': 1, ...}] == [{'test': 'te...ode': 1, ...}]
E         
E         Left contains one more item: {'test': 'tests/test_a.py::test_t', 'commit': 'abc1234', 'status': 'ran', 'exitCode': 1, ...}
E         Use -v to get more diff

/home/user/wt/build/plugins/superheroes/lib/tests/test_review_record_session_c1l1.py:287: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_session_c1l1.py::test_fill_a_current_run_the_scrub_changed_is_not_appended_again_beside_its_scrubbed_earlier_form
1 failed in 0.72s
```

Restore: the inverse edit. Restored lines quoted back (`grep -n -A1 '_scrubbed(run)'`):

```
894:                if (review_record._scrubbed(run) if isinstance(run, dict) else run) not in runs:
895-                    runs.append(run)
```

Green:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 0.69s
```

## BP-E4. a hand submit's accepted synthesis row is counted

- Axis: `_synthesis_rounds` counts a synthesis-phase row whose `outcome` is `recorded` or `accepted` (a successful hand `submit` journals `accepted`), and never one whose `cmd` is `record-missing`.
- Neutralization (`review_record_session.py`, `_synthesis_rounds`): `r.get("outcome") in ("recorded", "accepted")` became `r.get("outcome") == "recorded"`.
- Node: `plugins/superheroes/lib/tests/test_review_record_session_c1l1.py::test_an_accepted_synthesis_row_counts_as_a_synthesis_round`

Red:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
__________ test_an_accepted_synthesis_row_counts_as_a_synthesis_round __________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-67/test_an_accepted_synthesis_row0')

    def test_an_accepted_synthesis_row_counts_as_a_synthesis_round(tmp_path):
        # axis: a hand submit journals outcome "accepted" and counts like "recorded"; record-missing never does — see bite-proof record c1l1_wo_b_session_seam
        s = Session(tmp_path, rounds={"1": {}, "2": {}, "3": {}}).seat("code-reviewer")
        s.rows += [dict(SYNTHESIS, round=1, outcome="accepted", cmd="submit"), dict(SYNTHESIS, round=3, outcome="accepted",
                                                                                     cmd="record-missing")]
>       assert _account(s.save())["synthesisRounds"] == [1]
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       KeyError: 'synthesisRounds'

/home/user/wt/build/plugins/superheroes/lib/tests/test_review_record_session_c1l1.py:136: KeyError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_session_c1l1.py::test_an_accepted_synthesis_row_counts_as_a_synthesis_round
1 failed in 0.71s
```

Restore: the inverse edit. Restored lines quoted back (`grep -n -B1 -A2 '"recorded", "accepted"'`):

```
574-    # axis: a hand submit journals "accepted" and counts as "recorded" does — see bite-proof record c1l1_wo_b_session_seam
575:    return sorted({r["round"] for r in rows if r.get("outcome") in ("recorded", "accepted")
576-                   and r.get("phase") == round_phases.P_SYNTHESIS
577-                   and r.get("cmd") != "record-missing" and _int(r.get("round"))})
```

Green:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 0.67s
```
