# Work order A (#2460) bite-proof: an attached break-it test that does not load is dropped, never run, committed or restored

**Provenance:** claude / sonnet-5.5 (implementer, work order WO-A), maker family anthropic. Production under proof: `plugins/superheroes/lib/break_it.py` (`load_error`), `plugins/superheroes/lib/round_driver.py` (`_fold_panel`, `_fold_second_test`, `_fold_test_correction`). Tests: `plugins/superheroes/lib/tests/test_break_it_unloadable_2460.py`.

Declared guarded-element set (from the order): **G1** `_fold_panel`'s drop, **G2** `_fold_second_test`'s not-loadable branch, **G3** `_fold_test_correction`'s not-loadable reason, **G4** `break_it.load_error`'s `IndentationError` branch.

Each element was neutralized by one targeted edit to the PRODUCTION consumer (the Edit tool, exact-text match; never the test), only its proving nodes were run by exact node id, the inverse edit was applied, and the same nodes were run again. No `git checkout`, `git restore`, `git reset` or `git stash` was used. The command shape is `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-2460 -m pytest -p no:cacheprovider -q <node ids>`, with no pipe or filter. The captures below are verbatim, except that the `UV_NATIVE_TLS` deprecation warning line `scripts/pinned-python` prints first is left out of each; pytest's own `...` truncations inside the assertion text are pytest's, not edits.

**Redaction:** none needed. No secret appears in the test file or in these captures. Local `/tmp/...` and `/root/.cache/uv/...` paths are kept as printed.

**Restore receipt:** after each inverse edit the restored line is quoted below (printed by `grep -n` over the restored file). After G4, `git -C /home/user/wt-2460 diff --stat` and `grep -rn "False and"` over `break_it.py` and `round_driver.py` are quoted at the end: no neutralization is left.

All captures are under 32 KiB each and under 128 KiB together; none is written off-repo.

## Guarded elements

| ID | Guarded element | Axis | Proving nodes (all in `test_break_it_unloadable_2460.py`) |
|---|---|---|---|
| G1 | `round_driver.py` `_fold_panel`: `if load_error is not None:` then `g["suggestion"] = None` | an attached Python test that does not load is dropped from its finding before `intercept`, so no run, no restore demand and no fix binding follow | `::test_t1_an_unloadable_attached_test_is_dropped_so_no_restore_is_demanded_and_the_loop_goes_on` |
| G2 | `round_driver.py` `_fold_second_test`: `elif load_error is not None:` appending `not-loadable` to `noTest` | a second test that does not load is no new test: the held finding keeps its own test, nothing is run | `::test_t5_a_second_test_that_does_not_load_is_no_new_test_and_the_held_test_stays` |
| G3 | `round_driver.py` `_fold_test_correction`: `elif load_error is not None:` setting `reason = "not-loadable"` | a correction that does not load is no correction (outcome `none`), the restored test stands | `::test_t5_a_correction_that_does_not_load_is_no_correction_and_the_restored_test_stands` |
| G4 | `break_it.py` `load_error`: `except IndentationError as exc:` | only an indentation error is a load failure; the class name, message and line are reported | `::test_u_an_unexpected_indent_names_the_class_the_message_and_the_line`, `::test_t1_an_unloadable_attached_test_is_dropped_so_no_restore_is_demanded_and_the_loop_goes_on` |

The edges E1 (not a block), E2 (per-area), E3 (another syntax error), E4 (another language), E5 (null byte), E6 (stamped blocks), E7 (no runs on a dropped finding) and E8 (two seats) are guarded by their own nodes in the same file (`test_t4_*`, `test_t2_*`, `test_u_*`, `test_t5_e6_*`); they are not separate guarded elements of the four declared above and carry no separate neutralization. They are listed here as **unproven by neutralization** (they passed on the unneutralized code; no red was produced for them).

---

## G1: `_fold_panel`'s drop

**neutralization** (`plugins/superheroes/lib/round_driver.py`):
```diff
-        if load_error is not None:
+        if False and load_error is not None:
             g["suggestion"] = None
```

**raw red** (exit 1; this is the pre-fix story: the restore demanded the unloadable bytes, the session committed its own, and the PR was handed back):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_t1_an_unloadable_attached_test_is_dropped_so_no_restore_is_demanded_and_the_loop_goes_on _

fx = <test_break_it_attached_2210.Fixture object at 0x7f507ba65100>
tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-1/test_t1_an_unloadable_attached0')

    def test_t1_an_unloadable_attached_test_is_dropped_so_no_restore_is_demanded_and_the_loop_goes_on(fx, tmp_path):
        # axis: the whole path — the panel fold drops the test, the fix batch owes no binding, the audit has no test facts, the restore is never entered
        state = fx.fold_panel(test_role=[_finding()])
        staged = fx.staged(HTML_TITLE)
    
        # the loop: before the drop, the audit flagged the test, the restore demanded the unloadable bytes and the
        # session committed other bytes, so the PR was handed back with `break-it-restore-failed`
        final, asked = _loop(_audit_world(tmp_path / "loop", staged), restore_with=lambda item: OWN_REGRESSION)
        kinds = _decision_kinds(final)
>       assert "break-it-restore-failed" not in kinds, final["decisions"][-1]
E       AssertionError: {'round': 2, 'kind': 'break-it-restore-failed', 'detail': "The test reviewer's break-it test could not be restored at ..._is_not_a_fence.py:test-bytes-differ). The PR is handed back with its findings still open; certification is withheld."}
E       assert 'break-it-restore-failed' not in ['break-it-test-mismatch', 'not-discharged', 'break-it-restore-failed']

/home/user/wt-2460/plugins/superheroes/lib/tests/test_break_it_unloadable_2460.py:150: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_break_it_unloadable_2460.py::test_t1_an_unloadable_attached_test_is_dropped_so_no_restore_is_demanded_and_the_loop_goes_on
1 failed in 3.29s
```

**restore:** the inverse edit (drop the `False and `).
**restore receipt:** `4172:        if load_error is not None:`

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 2.93s
```

---

## G2: `_fold_second_test`'s not-loadable branch

**neutralization** (`plugins/superheroes/lib/round_driver.py`):
```diff
-        elif load_error is not None:
+        elif False and load_error is not None:
             no_test.append({"findingKey": key, "reason": "not-loadable"})
```

**raw red** (exit 1; on axis: the unloadable result's test replaced the held test and was run, the spy saw the call):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_t5_a_second_test_that_does_not_load_is_no_new_test_and_the_held_test_stays _

fx = <test_break_it_attached_2210.Fixture object at 0x7fa13e2cd490>
spy = namespace(calls=[{'path': 'tests/test_html_comment_is_not_a_fence.py', 'head': 'b303734ae7234844dd4d97861af65b340dc9a5...aude-0/pytest-of-root/pytest-3/test_t5_a_second_test_that_doe0/repo'}], offered=[['A retried charge is posted twice']])

    def test_t5_a_second_test_that_does_not_load_is_no_new_test_and_the_held_test_stays(fx, spy):
        # axis: the second-test fold keeps the held finding's own test and says why
        held = AT._attached(id="F1")
        result = dict(_finding(), id="F1")
        staged = _second_test(fx, held, result)
        key = RD._finding_identity_key(held)
>       assert staged["suggestion"] == held["suggestion"] and staged[RD.SECOND_TEST_FIELD] is True
E       AssertionError: assert ('break-it-tes...lder = None\n' == 'break-it-tes...len(ledger)\n'
E         
E           break-it-test v1
E         - path: tests/test_charge_once.py
E         + path: tests/test_html_comment_is_not_a_fence.py
E         - run: /root/.cache/uv/builds-v0/.tmpG0UYGa/bin/python tests/test_charge_once.py
E         ?                                                                  ^ ^^ --
E         + run: /root/.cache/uv/builds-v0/.tmpG0UYGa/bin/python tests/test_html_comment_is_not_a_fence.py...
E         
E         ...Full output truncated, use '-vv' to show)

/home/user/wt-2460/plugins/superheroes/lib/tests/test_break_it_unloadable_2460.py:299: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_break_it_unloadable_2460.py::test_t5_a_second_test_that_does_not_load_is_no_new_test_and_the_held_test_stays
1 failed in 3.15s
```

**restore:** the inverse edit (drop the `False and `).
**restore receipt:** `4874:        elif load_error is not None:` followed by `4875:            no_test.append({"findingKey": key, "reason": "not-loadable"})`

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 3.10s
```

---

## G3: `_fold_test_correction`'s not-loadable reason

**neutralization** (`plugins/superheroes/lib/round_driver.py`):
```diff
-        elif load_error is not None:
+        elif False and load_error is not None:
             # axis: a correction that does not load (an indentation error) is no correction, ...
```

**raw red** (exit 1; on axis: the unloadable correction landed as `corrected`):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_t5_a_correction_that_does_not_load_is_no_correction_and_the_restored_test_stands _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-5/test_t5_a_correction_that_does0')

    def test_t5_a_correction_that_does_not_load_is_no_correction_and_the_restored_test_stands(tmp_path):
        # axis: the correction fold names `not-loadable` and leaves the restored test in place
        w = _corrected_world(tmp_path)
        assert w.state["step"] == RD.P_SECOND_TEST
        w.fold(RD.P_SECOND_TEST, {"findings": [{"id": w.key, "suggestion": C1._block_text(UNLOADABLE_CORRECTION)}]})
>       assert w.state["rounds"]["2"]["testCorrection"] == [{"findingKey": w.key, "outcome": "none", "reason": "not-loadable"}]
E       AssertionError: assert [{'findingKey... 'corrected'}] == [{'findingKey...ot-loadable'}]
E         
E         At index 0 diff: {'findingKey': 'tests/test_charge.py::retry charges twice@L1', 'outcome': 'corrected'} != {'findingKey': 'tests/test_charge.py::retry charges twice@L1', 'outcome': 'none', 'reason': 'not-loadable'}
E         Use -v to get more diff

/home/user/wt-2460/plugins/superheroes/lib/tests/test_break_it_unloadable_2460.py:340: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_break_it_unloadable_2460.py::test_t5_a_correction_that_does_not_load_is_no_correction_and_the_restored_test_stands
1 failed in 3.25s
```

**restore:** the inverse edit (drop the `False and `).
**restore receipt:** `7632:        elif load_error is not None:` (the second of two `grep -n "elif load_error is not None:"` hits; the first, `4874`, is G2's, also restored).

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 2.80s
```

---

## G4: `load_error`'s `IndentationError` branch

**neutralization** (`plugins/superheroes/lib/break_it.py`):
```diff
-    except IndentationError as exc:
+    except ZeroDivisionError as exc:
```
(an indentation error then falls to the `except Exception` branch and reads as a test that loads)

**raw red** (exit 1; both proving nodes):
```
FF                                                                       [100%]
=================================== FAILURES ===================================
_____ test_u_an_unexpected_indent_names_the_class_the_message_and_the_line _____

    def test_u_an_unexpected_indent_names_the_class_the_message_and_the_line():
>       assert break_it.load_error(_block(content=UNLOADABLE)) == UNLOADABLE_ERROR
E       assert None == 'IndentationError: unexpected indent (line 8)'
E        +  where None = <function load_error at 0x7fc3d3a62ac0>({'path': 'tests/test_x.py', 'run': 'python tests/test_x.py', 'content': '"""Regression: mention_guard must not read an...e."""\nfrom types import SimpleNamespace\n\nimport cloud_builder\nimport mention_guard\n\n\n def_placeholder = None\n'})
E        +    where <function load_error at 0x7fc3d3a62ac0> = break_it.load_error
E        +    and   {'path': 'tests/test_x.py', 'run': 'python tests/test_x.py', 'content': '"""Regression: mention_guard must not read an...e."""\nfrom types import SimpleNamespace\n\nimport cloud_builder\nimport mention_guard\n\n\n def_placeholder = None\n'} = _block(content='"""Regression: mention_guard must not read an HTML comment\'s contents as a fence."""\nfrom types import SimpleNamespace\n\nimport cloud_builder\nimport mention_guard\n\n\n def_placeholder = None\n')

/home/user/wt-2460/plugins/superheroes/lib/tests/test_break_it_unloadable_2460.py:406: AssertionError
_ test_t1_an_unloadable_attached_test_is_dropped_so_no_restore_is_demanded_and_the_loop_goes_on _

fx = <test_break_it_attached_2210.Fixture object at 0x7fc3d34c3440>
tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-7/test_t1_an_unloadable_attached0')

    def test_t1_an_unloadable_attached_test_is_dropped_so_no_restore_is_demanded_and_the_loop_goes_on(fx, tmp_path):
        # axis: the whole path — the panel fold drops the test, the fix batch owes no binding, the audit has no test facts, the restore is never entered
        state = fx.fold_panel(test_role=[_finding()])
        staged = fx.staged(HTML_TITLE)
    
        # the loop: before the drop, the audit flagged the test, the restore demanded the unloadable bytes and the
        # session committed other bytes, so the PR was handed back with `break-it-restore-failed`
        final, asked = _loop(_audit_world(tmp_path / "loop", staged), restore_with=lambda item: OWN_REGRESSION)
        kinds = _decision_kinds(final)
>       assert "break-it-restore-failed" not in kinds, final["decisions"][-1]
E       AssertionError: {'round': 2, 'kind': 'break-it-restore-failed', 'detail': "The test reviewer's break-it test could not be restored at ..._is_not_a_fence.py:test-bytes-differ). The PR is handed back with its findings still open; certification is withheld."}
E       assert 'break-it-restore-failed' not in ['break-it-test-mismatch', 'not-discharged', 'break-it-restore-failed']

/home/user/wt-2460/plugins/superheroes/lib/tests/test_break_it_unloadable_2460.py:150: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_break_it_unloadable_2460.py::test_u_an_unexpected_indent_names_the_class_the_message_and_the_line
FAILED plugins/superheroes/lib/tests/test_break_it_unloadable_2460.py::test_t1_an_unloadable_attached_test_is_dropped_so_no_restore_is_demanded_and_the_loop_goes_on
2 failed in 3.43s
```

**restore:** the inverse edit (`ZeroDivisionError` back to `IndentationError`).
**restore receipt:** `1589:    except IndentationError as exc:`

**raw green** (exit 0):
```
..                                                                       [100%]
2 passed in 2.82s
```

---

## Final restore receipt (after G4, the last element)

`git -C /home/user/wt-2460 diff --stat` (tracked files; the new test file and this record are untracked):
```
 plugins/superheroes/lib/break_it.py              | 23 +++++++++
 plugins/superheroes/lib/decision_kinds.py        |  1 +
 plugins/superheroes/lib/receipt_disclosures.py   |  1 +
 plugins/superheroes/lib/review_record_session.py | 17 +++++++
 plugins/superheroes/lib/round_driver.py          | 65 +++++++++++++++++++++++-
 5 files changed, 105 insertions(+), 2 deletions(-)
```
`grep -rn "False and"` over `break_it.py` and `round_driver.py` printed nothing.
