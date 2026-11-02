# Bite-proof record: WO-B (#2311), the review record shows each reviewer's calibration read

Detector: `plugins/superheroes/lib/tests/test_review_record_calibration_2311.py` (23 tests), run
against `plugins/superheroes/lib/review_record.py`.

Declared guarded-element set (from the order): E1 to E7, one neutralization and one red each.
Every neutralization is a targeted Edit and was undone by the inverse Edit. Every red and green ran
the detector unedited, by exact test node id, under
`scripts/pinned-python -B -X pycache_prefix=/tmp/claude-0/shpyc -m pytest <node> -q`.
The whole file ran once before any neutralization (`23 passed in 0.98s`) and once at the end (see the
last section). Captures below are the pytest output as seen, with the `UV_NATIVE_TLS` warning line
and the `FAILED ...` summary line dropped from each (the summary line repeats the test node id).
Where a long `where ...` or `+ where` trace line was elided it is said in the entry. Nothing in them
is a credential or a private URL; no redaction was needed. The restore receipt for each element is
the restored lines quoted back from the file after the inverse Edit.

## E1: unmeasured for a credited row without the fact

- Guarded element: `review_record.py` `_calibration_words`, line 1989. Axis: an engine-record row
  whose record carries no calibration fact reads `calibration read: unmeasured`, never "did not read".
- Neutralization: `return "calibration read: unmeasured"` became `return "did not read its calibration"`.
- Detector: `test_an_engine_record_row_with_no_calibration_reads_unmeasured_not_did_not_read`.
- Raw red (the two `where` trace lines after the assertion are elided):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_an_engine_record_row_with_no_calibration_reads_unmeasured_not_did_not_read _

    def test_an_engine_record_row_with_no_calibration_reads_unmeasured_not_did_not_read():
        # axis: F1; a credited row whose engine record carries no calibration fact is unmeasured, never "did not read"
        rec = rec_of([reviewer("code-reviewer")], {"/run/code-reviewer": run()})
        assert "calibrationRead" not in rec["reviewers"][0]
        line = bullet(rr.render(rec), "code-reviewer")
>       assert line.endswith("; calibration read: unmeasured") and "did not read" not in line
E       AssertionError: assert (False)
E        +  where False = <built-in method endswith of str object at 0x7fcb51b12af0>('; calibration read: unmeasured')
...
E        +    where <built-in method endswith of str object at 0x7fcb51b12af0> = '- code-reviewer: ran (engine record); findings: reported by the session; did not read its calibration'.endswith

/home/user/wt-2311/plugins/superheroes/lib/tests/test_review_record_calibration_2311.py:101: AssertionError
1 failed in 21.01s
```

- Restore: inverse Edit. Restore receipt (Grep after): `1988:    if files is None:` / `1989:        return "calibration read: unmeasured"` / `1990:    if not files:`
- Raw green: `.   [100%]` / `1 passed in 0.78s`

## E2: the not-read words

- Guarded element: `review_record.py` `_calibration_words`, the loop tuple at lines 1993 to 1994.
  Axis: a file whose state is `not-read` appears in the line as `did not read <file>`, not shown as
  read and not left off.
- Neutralization: dropped `("not-read", "did not read "),` from the tuple, leaving
  `(("read", "read its calibration: "), ("unknown", "calibration read unknown for "))`.
- Detector: `test_a_not_read_entry_shows_did_not_read_for_that_file`.
- Raw red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
____________ test_a_not_read_entry_shows_did_not_read_for_that_file ____________

    def test_a_not_read_entry_shows_did_not_read_for_that_file():
        # axis: the not-read words; an entry that reads not-read shown as read, or left off the line
        rec = rec_of([reviewer("code-reviewer")], {"/run/code-reviewer": run(cal(crew="not-read"))})
        line = bullet(rr.render(rec), "code-reviewer")
>       assert line.endswith(f"; read its calibration: core.md, CLAUDE.md; did not read review-crew.md (policy {POLICY})")
E       AssertionError: assert False
E        +  where False = <built-in method endswith of str object at 0x7f43fe655a70>('; read its calibration: core.md, CLAUDE.md; did not read review-crew.md (policy 2026-10-27.942777056682)')
E        +    where <built-in method endswith of str object at 0x7f43fe655a70> = '- code-reviewer: ran (engine record); findings: reported by the session; read its calibration: core.md, CLAUDE.md (policy 2026-10-27.942777056682)'.endswith

/home/user/wt-2311/plugins/superheroes/lib/tests/test_review_record_calibration_2311.py:66: AssertionError
1 failed in 1.11s
```

- Restore: inverse Edit. Restore receipt (Grep after):
  `1993:    for state, lead in (("read", "read its calibration: "), ("not-read", "did not read "),` / `1994:                        ("unknown", "calibration read unknown for ")):`
- Raw green: `.   [100%]` / `1 passed in 1.01s`

## E3: the unknown words

- Guarded element: `review_record.py` `_calibration_words`, the unknown tuple at line 1994. Axis: a
  file whose state is `unknown` appears as `calibration read unknown for <file>`, never as a file
  that went unread.
- Neutralization: `("unknown", "calibration read unknown for ")` became `("unknown", "did not read ")`.
- Detector: `test_an_unknown_entry_shows_unknown_and_never_did_not_read`.
- Raw red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
__________ test_an_unknown_entry_shows_unknown_and_never_did_not_read __________

    def test_an_unknown_entry_shows_unknown_and_never_did_not_read():
        # axis: the unknown words; a stream that could not tell shown as a file that went unread
        rec = rec_of([reviewer("code-reviewer")], {"/run/code-reviewer": run(cal("unknown", "unknown", "unknown"))})
        line = bullet(rr.render(rec), "code-reviewer")
>       assert line.endswith(f"; calibration read unknown for core.md, review-crew.md, CLAUDE.md (policy {POLICY})")
E       AssertionError: assert False
E        +  where False = <built-in method endswith of str object at 0x7f8f3e71b0f0>('; calibration read unknown for core.md, review-crew.md, CLAUDE.md (policy 2026-10-27.942777056682)')
E        +    where <built-in method endswith of str object at 0x7f8f3e71b0f0> = '- code-reviewer: ran (engine record); findings: reported by the session; did not read core.md, review-crew.md, CLAUDE.md (policy 2026-10-27.942777056682)'.endswith

/home/user/wt-2311/plugins/superheroes/lib/tests/test_review_record_calibration_2311.py:73: AssertionError
1 failed in 0.79s
```

- Restore: inverse Edit. Restore receipt (Grep after):
  `1993:    for state, lead in (("read", "read its calibration: "), ("not-read", "did not read "),` / `1994:                        ("unknown", "calibration read unknown for ")):`
- Raw green: `.   [100%]` / `1 passed in 1.12s`

## E4: the chosen-row rule

- Guarded element: `review_record.py` `_test_lens`, line 1314. Axis: the chosen test-lens row is
  the last ran row that covers the final commit (else the last ran one), not the first row that ran.
- Neutralization: `chosen = (covering or ran)[-1] if ran else None` became `chosen = ran[0] if ran else None`.
- Detector: `test_the_chosen_row_is_the_last_one_covering_the_final_commit_not_the_first_that_ran`.
- Raw red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_the_chosen_row_is_the_last_one_covering_the_final_commit_not_the_first_that_ran _

    def test_the_chosen_row_is_the_last_one_covering_the_final_commit_not_the_first_that_ran():
        # axis: the chosen-row rule; an earlier-commit row that ran first, or a later one that does not cover, taking the part
        early_first = [reviewer("test-role (round 1)", commit=EARLIER), reviewer("test-role (round 2)")]
        runs = {"/run/test-role (round 1)": run(cal("not-read", "not-read", "not-read"), viewHeadSha=EARLIER),
                "/run/test-role (round 2)": run(cal())}
        part = rec_of(early_first, runs)["testLens"]
>       assert (part["row"], part["commit"], part["coversFinalCommit"]) == ("test-role (round 2)", HEAD, True)
E       AssertionError: assert ('test-role (...aaaaa', False) == ('test-role (...bbbbbb', True)
E         
E         At index 0 diff: 'test-role (round 1)' != 'test-role (round 2)'
E         Use -v to get more diff

/home/user/wt-2311/plugins/superheroes/lib/tests/test_review_record_calibration_2311.py:214: AssertionError
1 failed in 0.80s
```

- Restore: inverse Edit. Restore receipt (Grep after): `1314:    chosen = (covering or ran)[-1] if ran else None`
- Raw green: `.   [100%]` / `1 passed in 1.12s`

## E5: the old-record branch

- Guarded element: `review_record.py` `_test_lens_line`, the `not isinstance(part, dict)` branch at
  lines 2336 to 2337. Axis: a record written before the test-lens part reads
  `Test lens: unmeasured (...)`, never "did not run" and never "did not read".
- Neutralization: `return "Test lens: unmeasured (the record predates the test-lens part)."` became
  `return "Test lens: did not run."`.
- Detector: `test_a_record_written_before_this_change_reads_unmeasured_and_never_did_not_read`.
- Raw red (the long list and summary text inside the `AssertionError` and `where` lines are
  shortened by hand to the parts shown, marked `...` or `[...]`; see the elision note below the block):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_record_written_before_this_change_reads_unmeasured_and_never_did_not_read _

    def test_a_record_written_before_this_change_reads_unmeasured_and_never_did_not_read():
        # axis: F4; no testLens on the record and no calibrationRead on the rows read unmeasured, not did-not-run, not did-not-read
        rec = rec_of([reviewer("test-role"), reviewer("code-reviewer")],
                     {"/run/test-role": run(cal()), "/run/code-reviewer": run(cal())})
        old = copy.deepcopy(rec)
        del old["testLens"]
        for v in old["reviewers"]:
            v.pop("calibrationRead")
        for level in (0, 1, 2):
            text = rr._summary(old, level)
>           assert "Test lens: unmeasured (the record predates the test-lens part)." in text.split("\n")
E           AssertionError: assert 'Test lens: unmeasured (the record predates the test-lens part).' in ['**Review record: reviewed.** Checked: CI on bbbbbbb: green; Reviewers that ran: test-role, code-reviewer. Left: noth...from reviewers: could not be read; the vet checks every changed agent-config path by hand.', 'Makers: anthropic.', ...]
E            +  where [...] = <built-in method split of str object at 0x3757e9e0>('\n')
...
E            +    where <built-in method split of str object at 0x3757e9e0> = '...eviewer: ran (engine record); findings: reported by the session; calibration read: unmeasured\nTest lens: did not run.'.split

/home/user/wt-2311/plugins/superheroes/lib/tests/test_review_record_calibration_2311.py:289: AssertionError
1 failed in 0.81s
```

  Elided from the red above: the contents of the one list and the one summary text, which in the
  original output ran long (the full summary text, with the `Test lens: did not run.` line at its
  end, is what the test saw). The tail of the second `where` line
  (`... calibration read: unmeasured\nTest lens: did not run.`) is the decisive part and is kept. The
  full lines were not saved to disk; this is a hand-shortened quote of output seen in the session.
- Restore: inverse Edit. Restore receipt (Grep after): `2336:    if not isinstance(part, dict):` / `2337:        return "Test lens: unmeasured (the record predates the test-lens part)."`
- Raw green: `.   [100%]` / `1 passed in 0.88s`

## E6: the reported-by-session guard

- Guarded element: `review_record.py` `_calibration_words`, lines 1985 to 1986. Axis: a row with no
  engine record (reported by the session) says `calibration read: not shown (no engine record)`
  and never claims a read, even when a read is smuggled onto it.
- Neutralization: deleted the two lines
  `if row.get("ran") == "reported-by-session":` / `return "calibration read: not shown (no engine record)"`.
- Detector: `test_a_session_reported_row_never_claims_a_read`. The companion
  `test_a_session_reported_row_that_carries_a_read_is_still_not_shown_as_read` was not run under this
  neutralization (the order's budget gives one red per element).
- Raw red (the nested `where` trace lines after the assertion are elided; the decisive one is the
  rendered bullet, kept below):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_______________ test_a_session_reported_row_never_claims_a_read ________________

    def test_a_session_reported_row_never_claims_a_read():
        # axis: F5; a row with no engine record says the calibration read is not shown, even if a read is smuggled onto it
        rec = rec_of([reviewer("code-reviewer", runDir=None, calibrationRead=cal())], {})
        row = rec["reviewers"][0]
        assert row["ran"] == "reported-by-session" and "calibrationRead" not in row
>       assert bullet(rr.render(rec), "code-reviewer").endswith("; calibration read: not shown (no engine record)")
E       assert False
E        +  where False = <built-in method endswith of str object at 0x7f3638bc1750>('; calibration read: not shown (no engine record)')
E        +    where <built-in method endswith of str object at 0x7f3638bc1750> = '- code-reviewer: ran (reported by the session); findings: reported by the session; calibration read: unmeasured'.endswith
...

/home/user/wt-2311/plugins/superheroes/lib/tests/test_review_record_calibration_2311.py:142: AssertionError
1 failed in 0.97s
```

  Elided from the red above: three further `where` lines that print the whole rendered comment and
  the `render` function repr (about 1 KiB together).
- Restore: inverse Edit (re-inserted the two lines). Restore receipt (Grep after):
  `1983:    if row.get("ran") == "not-run":` / `1984:        return None` / `1985:    if row.get("ran") == "reported-by-session":` / `1986:        return "calibration read: not shown (no engine record)"` / `1987:    files = _valid_calibration(row.get("calibrationRead"))`
- Raw green: `.   [100%]` / `1 passed in 1.00s`

## E7: shed survival

- Guarded element: `review_record.py` `_shed_run_dir`, line 1931. Axis: the reviewer shed steps
  leave each row's `calibrationRead` (and the `testLens` part) alone at the deepest shed level.
- Neutralization: `dict(v, runDir=None)` became
  `{k: x for k, x in dict(v, runDir=None).items() if k != "calibrationRead"}`.
- Detector: `test_the_shed_steps_leave_the_calibration_read_and_the_test_lens_alone`.
- Raw red (the row-0 value on the right of the diff is cut after its first entry, marked `...`):

```
F                                                                        [100%]
=================================== FAILURES ===================================
____ test_the_shed_steps_leave_the_calibration_read_and_the_test_lens_alone ____

monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7f18d27b9fa0>

    def test_the_shed_steps_leave_the_calibration_read_and_the_test_lens_alone(monkeypatch):
        # axis: a trimmed record keeps calibrationRead on every row and the testLens part, at the deepest shed level
        rec = _many()
        shed = rr._shed_run_dir(rr._shed_observation(rec))
>       assert [v.get("calibrationRead") for v in shed["reviewers"]] == [v["calibrationRead"] for v in rec["reviewers"]]
E       AssertionError: assert [None, None, ...ne, None, ...] == [[{'label': '...', ...}], ...]
E         
E         At index 0 diff: None != [{'label': 'core', 'file': 'core.md', 'sha256': '62969b...', 'policyVersion': '2026-10-27.942777056682', 'read': 'read'}, ...]
E         Use -v to get more diff

/home/user/wt-2311/plugins/superheroes/lib/tests/test_review_record_calibration_2311.py:340: AssertionError
1 failed in 0.90s
```

- Restore: inverse Edit. Restore receipt (Grep after):
  `1929:def _shed_run_dir(record):` / `1931:    return dict(record, reviewers=[dict(v, runDir=None) if v.get("runDir") is not None else v`
- Raw green: `.   [100%]` / `1 passed in 0.72s`

## Findings

- All seven named tests went red under their own neutralization, on the axis each claims. No named
  test stayed green, so no "detector cannot fail on this axis" finding arises.
- E6 was proven with the first of the two tests the order allowed; the second was not run.
