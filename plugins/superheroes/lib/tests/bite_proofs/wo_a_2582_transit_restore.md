# Work order A (issue 2582) bite-proof: a transit-redacted break-it test never becomes a restore demand

**Provenance:** claude / sonnet (implementer, work order WO-A), maker family anthropic. Production under proof: `plugins/superheroes/lib/break_it.py` (`test_transit_damaged`, `intercept`, `check_kept`, `_body_search`, `_head_copy_transit_redacted`), `plugins/superheroes/lib/round_driver.py` (the audit fold's damaged split, `_audit_targets`' carry list, `_fold_test_correction`). Tests: `plugins/superheroes/lib/tests/test_transit_restore_2582.py`.

Declared guarded-element set (from the order): **G1** the audit fold's damaged split, **G2** the predicate's `reviewerTest`/`committedTest` extra texts at that call, **G3** the target carry of `TRANSIT_FIELD`, **G4** `intercept`'s text read, **G5** the correction fold's predicate, **G6** the kept check's guard.

Each element was neutralized by one targeted Edit-tool edit to the PRODUCTION line (never the test), only its proving nodes were run by exact node id, the inverse edit was applied, and the same nodes were run again. No `git checkout`, `git restore`, `git reset` or `git stash` was used. The command shape for every run is `scripts/pinned-python -B -X pycache_prefix=/tmp/claude-0/-home-user-superheroes/114caa80-95c2-5c62-a1d5-2937a0b76a9d/scratchpad/pyc -m pytest -p no:cacheprovider -q <node ids>`, unfiltered; the `UV_NATIVE_TLS` warning line is that wrapper's and is dropped from the captures below, everything else is verbatim (default `--tb`).

**Redaction:** none needed. No secret appears: every placeholder-shaped value in the test file is built from pieces at run time (`"[" + "REDACTED]"`), and no credential-like value is used. Local `/tmp/...` paths are kept as printed.

**Restore receipt:** after each inverse edit the restored line is quoted below (printed by `grep -n` over the restored file).

**G6 note:** the kept check guards at two lines (`check_kept`'s exact-path run and `_body_search`'s located-copy run). G6's neutralization is both lines edited together (`if False and (...)`) and its four proving nodes were run together; the two lines were not neutralized one at a time, so which node bites which line is read from the code (a: the exact-path line; the moved-copy node and c: the body-search line), not shown by a separate red.

**Not covered by a guarded element (unproven by neutralization):** the same-anchor merge carry list (`round_driver.py` `_merge_same_finding`'s `for field in (..., break_it.TRANSIT_FIELD)`) has no test row in the order and no node here; it was edited as the order's site 4 and is unproven.

## Guarded elements

| ID | Guarded element | Axis | Proving nodes (all in `test_transit_restore_2582.py`) |
|---|---|---|---|
| G1 | `round_driver.py` audit fold: `if target is not None and break_it.test_transit_damaged(` (the damaged split) | a damaged mismatched target is recorded and takes no restore, before both the bounded branch and `_begin_test_restore` | `::test_r1_an_unstamped_test_whose_saved_text_holds_the_placeholder_takes_no_restore`, `::test_r6_a_damaged_target_is_filtered_before_the_bounded_mismatch_in_b1`, `::test_r6_a_damaged_only_mismatch_in_the_final_audit_does_not_hand_back_bounded_pass_open` |
| G2 | the same call's `facts.get("reviewerTest"), facts.get("committedTest")` extra texts | the placeholder only in the test role's version or only in the committed copy still damages the test | `::test_r1b_the_placeholder_only_in_the_saved_reviewer_test_takes_no_restore`, `::test_r1c_the_placeholder_only_in_the_committed_copy_takes_no_restore` |
| G3 | `round_driver.py` `_audit_targets`: `break_it.TRANSIT_FIELD` in the carry tuple | the stamp survives into the audit target | `::test_r2_a_stamped_source_finding_carries_its_stamp_into_the_target_and_takes_no_restore` |
| G4 | `break_it.py` `intercept`: `transit = not refusal and test_transit_damaged(copy)` | an unstamped block whose text holds a placeholder is never run, and is stamped | `::test_r7_intercept_never_runs_an_unstamped_test_whose_block_holds_the_placeholder_and_stamps_it` |
| G5 | `round_driver.py` `_fold_test_correction`: `elif break_it.test_transit_damaged(result):` | an unstamped placeholder-bearing correction is no correction, `transit-redacted` | `::test_r8_an_unstamped_correction_whose_block_holds_the_placeholder_is_no_correction` |
| G6 | `break_it.py` `check_kept` and `_body_search`: the `transit_redacted(...)` guards before `_safe_run` | a damaged test is `unresolved`, `transit-redacted`, and never reaches the runner | `::test_r9a_a_record_whose_content_holds_the_placeholder_is_unresolved_and_never_run`, `::test_r9a_a_clean_copy_found_for_a_record_whose_content_holds_the_placeholder_is_never_run`, `::test_r9b_a_clean_record_whose_committed_blob_holds_the_placeholder_is_unresolved_and_never_run`, `::test_r9c_a_relocated_copy_whose_file_holds_the_placeholder_is_unresolved_and_never_run` |

---

## G1: the audit fold's damaged split

**neutralization** (`round_driver.py`):
```diff
-        if target is not None and break_it.test_transit_damaged(
+        if False and target is not None and break_it.test_transit_damaged(
```

**raw red** (exit 1):
```
FFF                                                                      [100%]
=================================== FAILURES ===================================
_ test_r1_an_unstamped_test_whose_saved_text_holds_the_placeholder_takes_no_restore _
...
>       _assert_no_restore(w)
...
>       assert RD.TEST_RESTORE_FIELD not in w.state
E       AssertionError: assert '_testRestore' not in {'schemaVersion': 5, 'sessionGeneration': 7, 'config': {'leg': 'code', 'panel': False, 'code': True, 'vendors': ['claude', 'codex'], ...}, 'round': 2, ...}
____ test_r6_a_damaged_target_is_filtered_before_the_bounded_mismatch_in_b1 ____
...
>       assert rec["testMismatch"] == [w.key] and rec["breakItTransitRedacted"] == [_entry(w.key)]
E       KeyError: 'breakItTransitRedacted'
_ test_r6_a_damaged_only_mismatch_in_the_final_audit_does_not_hand_back_bounded_pass_open _
...
>       assert "bounded-pass-open" not in kinds and KIND in kinds and "break-it-test-mismatch" in kinds
E       AssertionError: assert ('bounded-pass-open' not in ['break-it-test-mismatch', 'not-discharged', 'bounded-pass-open'])
=========================== short test summary info ============================
FAILED ...::test_r1_an_unstamped_test_whose_saved_text_holds_the_placeholder_takes_no_restore
FAILED ...::test_r6_a_damaged_target_is_filtered_before_the_bounded_mismatch_in_b1
FAILED ...::test_r6_a_damaged_only_mismatch_in_the_final_audit_does_not_hand_back_bounded_pass_open
3 failed in 3.47s
```
(Elided from the capture here: the tracebacks' fixture-setup lines and the long `state` repr; the failing assertion and error lines are verbatim.)

**restore:** the inverse edit (`if False and target is not None` back to `if target is not None`).
**restore receipt** (`grep -n -A1`):
```
10040:        if target is not None and break_it.test_transit_damaged(
10041-                target, facts.get("path"), facts.get("reviewerTest"), facts.get("committedTest")):
```
**raw green** (exit 0):
```
...                                                                      [100%]
3 passed in 3.99s
```

## G2: the extra texts

**neutralization** (`round_driver.py`):
```diff
-                target, facts.get("path"), facts.get("reviewerTest"), facts.get("committedTest")):
+                target, facts.get("path")):
```

**raw red** (exit 1):
```
FF                                                                       [100%]
__ test_r1b_the_placeholder_only_in_the_saved_reviewer_test_takes_no_restore ___
...
>       assert RD.TEST_RESTORE_FIELD not in w.state
E       AssertionError: assert '_testRestore' not in {'schemaVersion': 5, 'sessionGeneration': 7, 'config': {'leg': 'code', 'panel': False, 'code': True, 'vendors': ['claude', 'codex'], ...}, 'round': 2, ...}
_____ test_r1c_the_placeholder_only_in_the_committed_copy_takes_no_restore _____
...
>       assert RD.TEST_RESTORE_FIELD not in w.state
E       AssertionError: assert '_testRestore' not in {'schemaVersion': 5, 'sessionGeneration': 7, 'config': {'leg': 'code', 'panel': False, 'code': True, 'vendors': ['claude', 'codex'], ...}, 'round': 2, ...}
FAILED ...::test_r1b_the_placeholder_only_in_the_saved_reviewer_test_takes_no_restore
FAILED ...::test_r1c_the_placeholder_only_in_the_committed_copy_takes_no_restore
2 failed in 3.59s
```

**restore:** the inverse edit.
**restore receipt** (`grep -n 'target, facts.get("path")'`):
```
10041:                target, facts.get("path"), facts.get("reviewerTest"), facts.get("committedTest")):
```
**raw green** (exit 0):
```
..                                                                       [100%]
2 passed in 3.56s
```

## G3: the target carry

**neutralization** (`round_driver.py`):
```diff
-                            REVIEWER_TEST_FIELD, TEST_CORRECTION_FIELD, break_it.TRANSIT_FIELD):
+                            REVIEWER_TEST_FIELD, TEST_CORRECTION_FIELD):
```

**raw red** (exit 1):
```
F                                                                        [100%]
_ test_r2_a_stamped_source_finding_carries_its_stamp_into_the_target_and_takes_no_restore _
...
>       assert target[break_it.TRANSIT_FIELD] is True
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       KeyError: 'suggestionTransitRedacted'
FAILED ...::test_r2_a_stamped_source_finding_carries_its_stamp_into_the_target_and_takes_no_restore
1 failed in 3.52s
```
(The node fails at its target-carries-the-stamp assertion, ahead of the fold.)

**restore:** the inverse edit.
**restore receipt** (`grep -n "REVIEWER_TEST_FIELD, TEST_CORRECTION_FIELD"`):
```
9494:                            REVIEWER_TEST_FIELD, TEST_CORRECTION_FIELD, break_it.TRANSIT_FIELD):
```
**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 3.72s
```

## G4: intercept's text read

**neutralization** (`break_it.py`):
```diff
-        transit = not refusal and test_transit_damaged(copy)
+        transit = not refusal and copy.get(TRANSIT_FIELD) is True
```

**raw red** (exit 1):
```
F                                                                        [100%]
_ test_r7_intercept_never_runs_an_unstamped_test_whose_block_holds_the_placeholder_and_stamps_it _
...
>       assert calls == []
E       AssertionError: assert ['tests/test_charge.py'] == []
E         
E         Left contains one more item: 'tests/test_charge.py'
E         Use -v to get more diff
FAILED ...::test_r7_intercept_never_runs_an_unstamped_test_whose_block_holds_the_placeholder_and_stamps_it
1 failed in 3.34s
```

**restore:** the inverse edit.
**restore receipt** (`grep -n "transit = not refusal"`):
```
1694:        transit = not refusal and test_transit_damaged(copy)
```
**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 3.81s
```

## G5: the correction fold's predicate

**neutralization** (`round_driver.py`):
```diff
-        elif break_it.test_transit_damaged(result):
+        elif result.get(break_it.TRANSIT_FIELD) is True:
```

**raw red** (exit 1):
```
F                                                                        [100%]
_ test_r8_an_unstamped_correction_whose_block_holds_the_placeholder_is_no_correction _
...
>       assert w.state["rounds"]["2"]["testCorrection"] == [
            {"findingKey": w.key, "outcome": "none", "reason": "transit-redacted"}]
E       AssertionError: assert [{'findingKey... 'corrected'}] == [{'findingKey...it-redacted'}]
E         
E         At index 0 diff: {'findingKey': 'tests/test_charge.py::retry charges twice@L1', 'outcome': 'corrected'} != {'findingKey': 'tests/test_charge.py::retry charges twice@L1', 'outcome': 'none', 'reason': 'transit-redacted'}
E         Use -v to get more diff
FAILED ...::test_r8_an_unstamped_correction_whose_block_holds_the_placeholder_is_no_correction
1 failed in 3.51s
```

**restore:** the inverse edit.
**restore receipt** (`grep -n "elif break_it.test_transit_damaged(result):"`):
```
7692:        elif break_it.test_transit_damaged(result):
```
**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 3.71s
```

## G6: the kept check's guards (both lines together)

**neutralization** (`break_it.py`, two edits):
```diff
-    if transit_redacted(record.get("content")) or transit_redacted(blob.stdout.decode("utf-8", errors="replace")):
+    if False and (transit_redacted(record.get("content")) or transit_redacted(blob.stdout.decode("utf-8", errors="replace"))):
```
```diff
-    if transit_redacted(record.get("content")) or _head_copy_transit_redacted(repo_root, head, found["path"]):
+    if False and (transit_redacted(record.get("content")) or _head_copy_transit_redacted(repo_root, head, found["path"])):
```

**raw red** (exit 1):
```
FFFF                                                                     [100%]
_ test_r9a_a_record_whose_content_holds_the_placeholder_is_unresolved_and_never_run _
...
>       assert _got(result) == UNRESOLVED and result["run"] is None and calls == []
E       AssertionError: assert (('kept', None) == ('unresolved'...sit-redacted')
E         
E         At index 0 diff: 'kept' != 'unresolved'
E         Use -v to get more diff)
_ test_r9a_a_clean_copy_found_for_a_record_whose_content_holds_the_placeholder_is_never_run _
...
E       AssertionError: assert (('kept', 'body-match') == ('unresolved'...sit-redacted')
_ test_r9b_a_clean_record_whose_committed_blob_holds_the_placeholder_is_unresolved_and_never_run _
...
E       AssertionError: assert (('kept', None) == ('unresolved'...sit-redacted')
_ test_r9c_a_relocated_copy_whose_file_holds_the_placeholder_is_unresolved_and_never_run _
...
E       AssertionError: assert (('kept', 'body-match') == ('unresolved'...sit-redacted')
4 failed in 3.72s
```

**restore:** both inverse edits.
**restore receipt** (`grep -n -E "if (False and )?\(?transit_redacted\(record.get"`):
```
1990:    if transit_redacted(record.get("content")) or _head_copy_transit_redacted(repo_root, head, found["path"]):
2045:    if transit_redacted(record.get("content")) or transit_redacted(blob.stdout.decode("utf-8", errors="replace")):
```
**raw green** (exit 0):
```
....                                                                     [100%]
4 passed in 3.94s
```

---

## Open at the time of writing

The scoped suite showed two existing tests going red after the G4 edit (`intercept` reading the text): `test_break_it_transit_redacted_2284.py::test_a2_a_header_line_the_scrub_rewrites_still_sets_the_redacted_field` and `test_break_it_loop.py::test_a_scrub_altered_suggestion_is_refused_not_run`. They pin `suggestion-redacted` for a header the plugin's own scrub rewrote (it sets `suggestionRedacted`, not the transit stamp), and the scrub's own placeholder now reads as a transit one. They were not edited; the implementer's return carries the output and the question for the orchestrator.
