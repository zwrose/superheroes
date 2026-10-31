# Work order A (#2284) bite-proof: a break-it test damaged by transit redaction is reported not run

**Provenance:** claude / sonnet-5.5 (implementer, work order WO-A), maker family anthropic. Production under proof: `plugins/superheroes/lib/engine_adapter.py` (`_scrub_findings`), `plugins/superheroes/lib/break_it.py` (`intercept`, `transit_not_run`), `plugins/superheroes/lib/round_driver.py` (`_fold_second_test`, `_fold_test_correction`, `_cmd_break_it_change_locked`), `plugins/superheroes/lib/review_record.py` (`_run_result`). Tests: `plugins/superheroes/lib/tests/test_break_it_transit_redacted_2284.py`.

Declared guarded-element set (from the order): **G1** the adapter's `TRANSIT_FIELD` stamping, **G2** `intercept`'s `transit-redacted` branch, **G3** the `break-it-change` guard, **G4** the second-test carry, **G5** the correction-fold reason, **G6** `_run_result`'s rendering.

Each element was neutralized by one targeted edit to the PRODUCTION consumer (the Edit tool, exact-text match; never the test), only its proving nodes were run by exact node id, the inverse edit was applied, and the same nodes were run again. No `git checkout`, `git restore`, `git reset` or `git stash` was used. The command shape is `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest -p no:cacheprovider -q <node ids> | grep -v UV_NATIVE`, followed by `echo "pytest exit: ${PIPESTATUS[0]}"`; the one filtered line is the `UV_NATIVE_TLS` deprecation warning that `scripts/pinned-python` prints, and everything else is verbatim (default `--tb`).

**Redaction:** none needed. No secret appears: every credential-like or placeholder-shaped value in the test file is built from pieces at run time (`"[" + "REDACTED]"`, `"sk-" + "a" * 48`). Local `/tmp/...` paths are kept as printed.

**Restore receipt:** after each inverse edit the restored line is quoted below (printed by `grep -n` over the restored file), and after G6 a `grep -rn 'False and'` over the four production files printed nothing, with no `record = None or` left in `round_driver.py`. A whole-worktree `git diff --stat` after G6 showed only the intended production, doc and test edits, no neutralization.

All captures are under 32 KiB each and under 128 KiB together; none is written off-repo.

## Guarded elements

| ID | Guarded element | Axis | Proving nodes (all in `test_break_it_transit_redacted_2284.py`) |
|---|---|---|---|
| G1 | `engine_adapter.py` `_scrub_findings`: `if break_it.transit_redacted(original):` sets `g[break_it.TRANSIT_FIELD]` | a block whose original text (header or content) carries a placeholder is stamped at the chokepoint, off the original, never off the scrubbed text | `::test_a1_a_placeholder_in_the_content_is_stamped_and_the_test_is_never_run`, `::test_a1_a_placeholder_in_the_run_header_is_stamped_and_the_test_is_never_run`, `::test_c1_a_placeholder_bearing_second_test_is_not_run_with_the_reason`, `::test_e5_the_change_alias_is_stamped_like_the_suggestion`, `::test_a_placeholder_on_an_attached_block_is_stamped_and_never_run` |
| G2 | `break_it.py` `intercept`: `transit = not refusal and copy.get(TRANSIT_FIELD) is True` and its `transit-redacted` stamp | a stamped block is never handed to the runner, and wins over `suggestion-redacted` (a seat-supplied stamp stays, fail-closed) | `::test_b1_transit_redacted_wins_when_both_stamps_are_set`, `::test_e2_a_seat_supplied_transit_field_stays_and_the_test_is_not_run`, `::test_a1_a_placeholder_in_the_content_is_stamped_and_the_test_is_never_run` |
| G3 | `round_driver.py` `_cmd_break_it_change_locked`: `break_it.transit_not_run(head, changed) or break_it.run_one(...)` | a changed block that still carries a placeholder is recorded not-run and `run_one` is never called | `::test_c3_a_changed_test_still_carrying_a_placeholder_is_recorded_not_run_and_never_run` |
| G4 | `round_driver.py` `_fold_second_test`: the `TRANSIT_FIELD` carry from the result onto `copy_` | a placeholder-bearing second test is not run with the reason (the stamp reaches `intercept`) | `::test_c1_a_placeholder_bearing_second_test_is_not_run_with_the_reason` |
| G5 | `round_driver.py` `_fold_test_correction`: `elif result.get(break_it.TRANSIT_FIELD) is True: reason = break_it.REASON_TRANSIT_REDACTED`, checked before `"redacted"` | a correction carrying a placeholder is no correction and the reason is named, ahead of `redacted` | `::test_c2_a_correction_carrying_a_placeholder_is_no_correction_and_names_transit_redacted`, `::test_c2_transit_redacted_wins_over_redacted_in_the_correction_fold` |
| G6 | `review_record.py` `_run_result`: the `not-started` + `transit-redacted` branch | the review record reads `not run: transit-redacted`, never `did not start`, for the stamped run | `::test_d1_a_transit_redacted_run_reads_not_run_transit_redacted` |

Edges E1 (non-string), E3 (unparseable block), E4 (prose-only placeholder), E5 (`change` alias) and the no-false-positive bare word `REDACTED` are guarded by their own nodes in the same file (`test_e1_*`, `test_e3_*`, `test_e4_*`, `test_e5_*`, `test_a1_the_bare_word_*`); they are not separate guarded elements of the six declared above and carry no separate neutralization. They are listed here as **unproven by neutralization** (they passed on the unneutralized code; no red was produced for them).

---

## G1: the adapter's stamping

**neutralization** (`plugins/superheroes/lib/engine_adapter.py`):
```diff
-            if break_it.transit_redacted(original):
+            if False and break_it.transit_redacted(original):
```

**raw red** (exit 1; the five nodes of the G1 row):
```
FFFFF                                                                    [100%]
=================================== FAILURES ===================================
__ test_a1_a_placeholder_in_the_content_is_stamped_and_the_test_is_never_run ___

world = <test_break_it_loop.World object at 0x7f0e44d51af0>

    def test_a1_a_placeholder_in_the_content_is_stamped_and_the_test_is_never_run(world):
        content = _TEST_FAILING + "# the token was " + PLACEHOLDER + "\n"
        got = _scrub_one(_break_it_finding(content))
>       assert got[break_it.TRANSIT_FIELD] is True
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       KeyError: 'suggestionTransitRedacted'

/home/user/superheroes/.worktrees/b2284/plugins/superheroes/lib/tests/test_break_it_transit_redacted_2284.py:143: KeyError
_ test_a1_a_placeholder_in_the_run_header_is_stamped_and_the_test_is_never_run _

world = <test_break_it_loop.World object at 0x7f0e44d4f4d0>

    def test_a1_a_placeholder_in_the_run_header_is_stamped_and_the_test_is_never_run(world):
        raw = _break_it_finding()
        raw["suggestion"] = "break-it-test v1\npath: %s\nrun: %s %s --opt %s\n---\n%s" % (
            TEST_PATH, PY, TEST_PATH, PLACEHOLDER, _TEST_FAILING)
        got = _scrub_one(raw)
>       assert got[break_it.TRANSIT_FIELD] is True
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       KeyError: 'suggestionTransitRedacted'

/home/user/superheroes/.worktrees/b2284/plugins/superheroes/lib/tests/test_break_it_transit_redacted_2284.py:160: KeyError
_____ test_c1_a_placeholder_bearing_second_test_is_not_run_with_the_reason _____

world = <test_break_it_loop.World object at 0x7f0e44d52270>

    def test_c1_a_placeholder_bearing_second_test_is_not_run_with_the_reason(world):
        held = _break_it_finding(id="F1")
        result = _scrub_one(dict(_break_it_finding(_TEST_FAILING + "# " + PLACEHOLDER + "\n"), id="F1"))
>       assert result[break_it.TRANSIT_FIELD] is True
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       KeyError: 'suggestionTransitRedacted'

/home/user/superheroes/.worktrees/b2284/plugins/superheroes/lib/tests/test_break_it_transit_redacted_2284.py:305: KeyError
___________ test_e5_the_change_alias_is_stamped_like_the_suggestion ____________

    def test_e5_the_change_alias_is_stamped_like_the_suggestion():
        clean = _break_it_finding()
        clean["change"] = clean.pop("suggestion")
        got = _scrub_one(clean)
        assert break_it.TRANSIT_FIELD not in got and break_it.REDACTED_FIELD not in got
        damaged = _break_it_finding(_TEST_FAILING + "# " + PLACEHOLDER + "\n")
        damaged["change"] = damaged.pop("suggestion")
        got = _scrub_one(damaged)
>       assert got[break_it.TRANSIT_FIELD] is True and break_it.REDACTED_FIELD not in got
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       KeyError: 'suggestionTransitRedacted'

/home/user/superheroes/.worktrees/b2284/plugins/superheroes/lib/tests/test_break_it_transit_redacted_2284.py:212: KeyError
_______ test_a_placeholder_on_an_attached_block_is_stamped_and_never_run _______

fx = <test_break_it_attached_2210.Fixture object at 0x7f0e4502dd60>

    def test_a_placeholder_on_an_attached_block_is_stamped_and_never_run(fx):
        got = _scrub_one(AT._attached(_TEST_FAILING + "# " + PLACEHOLDER + "\n"))
>       assert got[break_it.TRANSIT_FIELD] is True
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       KeyError: 'suggestionTransitRedacted'

/home/user/superheroes/.worktrees/b2284/plugins/superheroes/lib/tests/test_break_it_transit_redacted_2284.py:219: KeyError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_break_it_transit_redacted_2284.py::test_a1_a_placeholder_in_the_content_is_stamped_and_the_test_is_never_run
FAILED plugins/superheroes/lib/tests/test_break_it_transit_redacted_2284.py::test_a1_a_placeholder_in_the_run_header_is_stamped_and_the_test_is_never_run
FAILED plugins/superheroes/lib/tests/test_break_it_transit_redacted_2284.py::test_c1_a_placeholder_bearing_second_test_is_not_run_with_the_reason
FAILED plugins/superheroes/lib/tests/test_break_it_transit_redacted_2284.py::test_e5_the_change_alias_is_stamped_like_the_suggestion
FAILED plugins/superheroes/lib/tests/test_break_it_transit_redacted_2284.py::test_a_placeholder_on_an_attached_block_is_stamped_and_never_run
5 failed in 2.30s
pytest exit: 1
```
(The red is on the axis: the field is missing, `KeyError: 'suggestionTransitRedacted'`.)

**restore:** the inverse edit (`if False and break_it.transit_redacted(original):` back to the line below).
**restore receipt:** `1694:            if break_it.transit_redacted(original):`

**raw green** (exit 0):
```
.....                                                                    [100%]
5 passed in 2.38s
pytest exit: 0
```

---

## G2: `intercept`'s transit-redacted branch

**neutralization** (`plugins/superheroes/lib/break_it.py`):
```diff
-        transit = not refusal and copy.get(TRANSIT_FIELD) is True
+        transit = False and not refusal and copy.get(TRANSIT_FIELD) is True
```

**raw red** (exit 1):
```
FFF                                                                      [100%]
=================================== FAILURES ===================================
____________ test_b1_transit_redacted_wins_when_both_stamps_are_set ____________

world = <test_break_it_loop.World object at 0x7f52b547a180>

    def test_b1_transit_redacted_wins_when_both_stamps_are_set(world):
        finding = _break_it_finding(**{break_it.TRANSIT_FIELD: True, break_it.REDACTED_FIELD: True})
        calls = []
        kept, runs, exempt, _s = break_it.intercept([finding], world.repo, world.head, runner=_spy_runner(calls))
        assert calls == []
>       assert (runs[0]["outcome"], runs[0]["reason"]) == ("not-run", "transit-redacted")
E       AssertionError: assert ('not-run', '...ion-redacted') == ('not-run', '...sit-redacted')
E         
E         At index 1 diff: 'suggestion-redacted' != 'transit-redacted'
E         Use -v to get more diff

/home/user/superheroes/.worktrees/b2284/plugins/superheroes/lib/tests/test_break_it_transit_redacted_2284.py:272: AssertionError
_____ test_e2_a_seat_supplied_transit_field_stays_and_the_test_is_not_run ______

world = <test_break_it_loop.World object at 0x7f52b5477e60>

    def test_e2_a_seat_supplied_transit_field_stays_and_the_test_is_not_run(world):
        seat = _break_it_finding(**{break_it.TRANSIT_FIELD: True})
        got = _scrub_one(seat)
        assert got[break_it.TRANSIT_FIELD] is True
        calls = []
        _kept, runs, _e, _s = break_it.intercept([got], world.repo, world.head, runner=_spy_runner(calls))
>       assert calls == [] and runs[0]["reason"] == "transit-redacted"
E       AssertionError: assert (['tests/test_charge_once.py'] == []
E         
E         Left contains one more item: 'tests/test_charge_once.py'
E         Use -v to get more diff)

/home/user/superheroes/.worktrees/b2284/plugins/superheroes/lib/tests/test_break_it_transit_redacted_2284.py:283: AssertionError
__ test_a1_a_placeholder_in_the_content_is_stamped_and_the_test_is_never_run ___

world = <test_break_it_loop.World object at 0x7f52b54780b0>

    def test_a1_a_placeholder_in_the_content_is_stamped_and_the_test_is_never_run(world):
        content = _TEST_FAILING + "# the token was " + PLACEHOLDER + "\n"
        got = _scrub_one(_break_it_finding(content))
        assert got[break_it.TRANSIT_FIELD] is True
        assert got["suggestion"] == _break_it_finding(content)["suggestion"] and break_it.REDACTED_FIELD not in got
        calls = []
        kept, runs, _exempt, _stamped = break_it.intercept([got], world.repo, world.head, runner=_spy_runner(calls))
>       assert calls == []
E       AssertionError: assert ['tests/test_charge_once.py'] == []
E         
E         Left contains one more item: 'tests/test_charge_once.py'
E         Use -v to get more diff

/home/user/superheroes/.worktrees/b2284/plugins/superheroes/lib/tests/test_break_it_transit_redacted_2284.py:147: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_break_it_transit_redacted_2284.py::test_b1_transit_redacted_wins_when_both_stamps_are_set
FAILED plugins/superheroes/lib/tests/test_break_it_transit_redacted_2284.py::test_e2_a_seat_supplied_transit_field_stays_and_the_test_is_not_run
FAILED plugins/superheroes/lib/tests/test_break_it_transit_redacted_2284.py::test_a1_a_placeholder_in_the_content_is_stamped_and_the_test_is_never_run
3 failed in 2.25s
pytest exit: 1
```
(On axis: the runner is handed the stamped block, and the `suggestion-redacted` stamp wins over `transit-redacted`.)

**restore:** the inverse edit (drop the `False and `).
**restore receipt:** `1634:        transit = not refusal and copy.get(TRANSIT_FIELD) is True`

**raw green** (exit 0):
```
...                                                                      [100%]
3 passed in 2.19s
pytest exit: 0
```

---

## G3: the `break-it-change` guard

**neutralization** (`plugins/superheroes/lib/round_driver.py`):
```diff
-    record = break_it.transit_not_run(head, changed) or break_it.run_one(
+    record = None or break_it.run_one(
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_c3_a_changed_test_still_carrying_a_placeholder_is_recorded_not_run_and_never_run _

fx = <test_break_it_attached_2210.Fixture object at 0x7f79bd45ca40>
tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-6/test_c3_a_changed_test_still_c0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7f79bd45df70>

    def test_c3_a_changed_test_still_carrying_a_placeholder_is_recorded_not_run_and_never_run(fx, tmp_path, monkeypatch):
        session = str(fx.session)
        AT._drive_to_verifiers(fx, AT._seats(test_role=[AT._per_area(AT._SYNTAX_ERROR)]))
        calls = []
    
        def stub_run_one(repo_root, head, block, **kwargs):
            calls.append(block["path"])
            return break_it._not_run(head, block, "stub-ran")
    
        monkeypatch.setattr(break_it, "run_one", stub_run_one)
        changed = _TEST_FAILING + "# the token was " + PLACEHOLDER + "\n"
        out = RD.cmd_break_it_change(session, "v0", AT._content_file(tmp_path, changed), AT.WHY)
>       assert out["ok"] is True and calls == []
E       AssertionError: assert (True is True and ['tests/test_...dempotent.py'] == []
E         
E         Left contains one more item: 'tests/test_charge_idempotent.py'
E         Use -v to get more diff)

/home/user/superheroes/.worktrees/b2284/plugins/superheroes/lib/tests/test_break_it_transit_redacted_2284.py:374: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_break_it_transit_redacted_2284.py::test_c3_a_changed_test_still_carrying_a_placeholder_is_recorded_not_run_and_never_run
1 failed in 3.24s
pytest exit: 1
```

**restore:** the inverse edit (`None or` back to `break_it.transit_not_run(head, changed) or`).
**restore receipt:** `10776:    record = break_it.transit_not_run(head, changed) or break_it.run_one(`

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 3.09s
pytest exit: 0
```

---

## G4: the second-test carry

**neutralization** (`plugins/superheroes/lib/round_driver.py`):
```diff
-            if result.get(break_it.TRANSIT_FIELD) is True:
+            if False and result.get(break_it.TRANSIT_FIELD) is True:
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_____ test_c1_a_placeholder_bearing_second_test_is_not_run_with_the_reason _____

world = <test_break_it_loop.World object at 0x7fc1b7261910>

    def test_c1_a_placeholder_bearing_second_test_is_not_run_with_the_reason(world):
        held = _break_it_finding(id="F1")
        result = _scrub_one(dict(_break_it_finding(_TEST_FAILING + "# " + PLACEHOLDER + "\n"), id="F1"))
        assert result[break_it.TRANSIT_FIELD] is True
        staged = _second_test(world, held, result)
>       assert (staged[break_it.RUN_FIELD]["outcome"], staged[break_it.RUN_FIELD]["reason"]) == (
            "not-run", "transit-redacted")
E       AssertionError: assert ('failed', None) == ('not-run', '...sit-redacted')
E         
E         At index 0 diff: 'failed' != 'not-run'
E         Use -v to get more diff

/home/user/superheroes/.worktrees/b2284/plugins/superheroes/lib/tests/test_break_it_transit_redacted_2284.py:307: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_break_it_transit_redacted_2284.py::test_c1_a_placeholder_bearing_second_test_is_not_run_with_the_reason
1 failed in 2.81s
pytest exit: 1
```
(On axis: without the carry the placeholder-bearing second test is actually executed, outcome `failed`.)

**restore:** the inverse edit (drop the `False and `).
**restore receipt:** `4287:            if result.get(break_it.TRANSIT_FIELD) is True:`

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 2.20s
pytest exit: 0
```

---

## G5: the correction-fold reason

**neutralization** (`plugins/superheroes/lib/round_driver.py`):
```diff
-        elif result.get(break_it.TRANSIT_FIELD) is True:
+        elif False and result.get(break_it.TRANSIT_FIELD) is True:
```

**raw red** (exit 1):
```
FF                                                                       [100%]
=================================== FAILURES ===================================
_ test_c2_a_correction_carrying_a_placeholder_is_no_correction_and_names_transit_redacted _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-10/test_c2_a_correction_carrying_0')

    def test_c2_a_correction_carrying_a_placeholder_is_no_correction_and_names_transit_redacted(tmp_path):
        w = TR.World(tmp_path)
        w.audit()
        w.restore()
        w.fold(RD.P_SECOND_TEST, {"findings": [{"id": w.key, "suggestion": C1._block_text(TR.CORRECTED_TEST),
                                                break_it.TRANSIT_FIELD: True}]})
>       assert w.state["rounds"]["2"]["testCorrection"] == [
            {"findingKey": w.key, "outcome": "none", "reason": "transit-redacted"}]
E       AssertionError: assert [{'findingKey... 'corrected'}] == [{'findingKey...it-redacted'}]
E         
E         At index 0 diff: {'findingKey': 'tests/test_charge.py::retry charges twice@L1', 'outcome': 'corrected'} != {'findingKey': 'tests/test_charge.py::retry charges twice@L1', 'outcome': 'none', 'reason': 'transit-redacted'}
E         Use -v to get more diff

/home/user/superheroes/.worktrees/b2284/plugins/superheroes/lib/tests/test_break_it_transit_redacted_2284.py:335: AssertionError
______ test_c2_transit_redacted_wins_over_redacted_in_the_correction_fold ______

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-10/test_c2_transit_redacted_wins_0')

    def test_c2_transit_redacted_wins_over_redacted_in_the_correction_fold(tmp_path):
        w = TR.World(tmp_path)
        w.audit()
        w.restore()
        w.fold(RD.P_SECOND_TEST, {"findings": [{"id": w.key, "suggestion": C1._block_text(TR.CORRECTED_TEST),
                                                break_it.TRANSIT_FIELD: True, break_it.REDACTED_FIELD: True}]})
>       assert w.state["rounds"]["2"]["testCorrection"][0]["reason"] == "transit-redacted"
E       AssertionError: assert 'redacted' == 'transit-redacted'
E         
E         - transit-redacted
E         + redacted
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_break_it_transit_redacted_2284.py::test_c2_a_correction_carrying_a_placeholder_is_no_correction_and_names_transit_redacted
FAILED plugins/superheroes/lib/tests/test_break_it_transit_redacted_2284.py::test_c2_transit_redacted_wins_over_redacted_in_the_correction_fold
2 failed in 2.51s
pytest exit: 1
```
(On axis: a placeholder-bearing correction was landed as `corrected` in the first node, and the reason read `redacted`, not `transit-redacted`, in the second.)

**restore:** the inverse edit (drop the `False and `).
**restore receipt:** `6266:        elif result.get(break_it.TRANSIT_FIELD) is True:`

**raw green** (exit 0):
```
..                                                                       [100%]
2 passed in 2.18s
pytest exit: 0
```

---

## G6: `_run_result`'s rendering

**neutralization** (`plugins/superheroes/lib/review_record.py`):
```diff
-    if run.get("status") == "not-started" and run.get("reason") == _TRANSIT_REDACTED_REASON:
+    if False and run.get("status") == "not-started" and run.get("reason") == _TRANSIT_REDACTED_REASON:
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
________ test_d1_a_transit_redacted_run_reads_not_run_transit_redacted _________

    def test_d1_a_transit_redacted_run_reads_not_run_transit_redacted():
        run = break_it.record_run(break_it._not_run("h1", None, "transit-redacted"))
        assert (run["status"], run["reason"]) == ("not-started", "transit-redacted")
>       assert review_record._run_result(run) == "not run: transit-redacted"
E       AssertionError: assert 'did not start' == 'not run: transit-redacted'
E         
E         - not run: transit-redacted
E         + did not start

/home/user/superheroes/.worktrees/b2284/plugins/superheroes/lib/tests/test_break_it_transit_redacted_2284.py:409: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_break_it_transit_redacted_2284.py::test_d1_a_transit_redacted_run_reads_not_run_transit_redacted
1 failed in 2.05s
pytest exit: 1
```

**restore:** the inverse edit (drop the `False and `).
**restore receipt:** `2027:    if run.get("status") == "not-started" and run.get("reason") == _TRANSIT_REDACTED_REASON:`; then `grep -rn 'False and'` over `break_it.py`, `engine_adapter.py`, `round_driver.py` and `review_record.py` printed nothing.

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 1.95s
pytest exit: 0
```
