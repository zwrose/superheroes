# WO-1 (#2480) bite-proof — `merge_queue.slots` guards

Per-guard bite proof for the `slots` code added to `plugins/superheroes/lib/merge_queue.py`: each added `# axis:` line is neutralized in source by a targeted edit (Edit tool), the proving test(s) must go red alone (`-k`), the line is restored by the inverse edit (Edit tool), and the whole new file plus `test_merge_queue.py` goes green again.

**Register:** 27 guarded elements — the 26 `# axis:` lines this work order added to `merge_queue.py` (R1–R6 in `_read_rules_limit`, G1–G9 in `_read_graphql_slots`, S1–S9 in `slots`, C1 and C3 in `main`) plus C2, the existing parse-boundary line whose body this work order changed (it now picks the error shape). Line numbers are those of the restored file. No element is left unproven; no `Unprovable as placed`, `Unreachable through this entry point` or `Unrunnable here` disclosure applies. Where a neutralization is only partly discriminated by the tests, the entry says which cases and why (R5, G8, G9).

**Not re-neutralized (outside the declared set, said plainly):** the existing axis lines the slots path reuses unchanged — `_validate` (lines 129, 133, 139, 143, E1–E4) and `_Gh.call` (lines 181, 185, 190, 193: the deadline, the timeout cap, `OSError`/`TimeoutExpired`, gh non-zero; E21 and the failing-call half of E11). They were proven through `read` in `bite_proofs/wo1_merge_queue_2459.md`; this record does not re-prove them through `slots`, though the new tests exercise them (S1's neutralization turns every E1–E4 test red; G1's turns the E21 and E11 tests red). The E21 clause "GraphQL is attempted even after a failed rules read" has no branch of its own (the call is unconditional), so it has no axis line and no neutralization; `test_e21_graphql_is_attempted_after_a_failed_rules_read_so_reads_reports_both` pins it and also went red under S4 and G1.

**Provenance:** claude (Claude Sonnet 5.5).

**Commands.** *Red* (one per element, `<expr>` named in each entry):

```
scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-2480 -m pytest plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py -q -p no:cacheprovider --tb=line -k "<expr>"
```

*Green* (after each restore, the order's named command unmodified):

```
scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-2480 -m pytest plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py plugins/superheroes/lib/tests/test_merge_queue.py -q -p no:cacheprovider --tb=short
```

**Disclosures about the captures.**
- Every capture omits the one leading line `warning: The `UV_NATIVE_TLS` environment variable is deprecated ...`, which is uv's own notice. The sandbox accepted `-X pycache_prefix`.
- Every green is `317 passed` (200 new tests, 117 in `test_merge_queue.py`); the five progress lines are identical every time (`.` x72 `[ 22%]`, x72 `[ 45%]`, x72 `[ 68%]`, x72 `[ 90%]`, x29 `[100%]`) and are shown once, under the first run. Each later green is given as its summary line.
- `--tb=line` prints, per failure, an `E   ...` line and a `file:line: ...` line. Where many failures print the identical pair, the entry shows the progress line, the first pairs, the exact count of the elided identical pairs, and the verbatim summary list and totals. Nothing else is shortened.
- Test file line numbers in the captures (`test_merge_queue_slots_2480.py:136`, `:144`, `:137`) are the shared helpers `_assert_unreadable` (136: `assert result["fits"] is False`; 137: the `reason` assertion) and `_assert_bad_argument` (144: `assert result["fits"] is False`).
- Neutralization style: where a plain `if False:` would crash or be caught by a later redundant guard, the neutralization instead makes the branch return the passing answer (`fits: true` / no-queue), so the red is a wrong answer on the edge's axis, not an unrelated error. Each entry quotes its exact edit.
- Command budget: 58 of 110 invocations — 1 first full green, 27 reds, 27 greens, 1 final green over the finished tree (`317 passed in 1.18s`), `git status --short plugins`, `git diff --stat`. The leftover-marker and stray-space checks used the Grep tool, not the shell.
- Redaction: nothing in these captures is a secret, token or private URL; the only host-like text is the fixture repo `owner/example`. Nothing was redacted.

**First run (before any neutralization):**
```
........................................................................ [ 22%]
........................................................................ [ 45%]
........................................................................ [ 68%]
........................................................................ [ 90%]
.............................                                            [100%]
317 passed in 1.09s
```

## Summary table

| ID | Guarded element (file:line) | Axis | Proving test(s) | Verdict |
|---|---|---|---|---|
| R1 | merge_queue.py:354 | the branch is percent-quoted into the rules path, slashes kept | `test_the_branch_is_percent_quoted_*` | proven (wrong-argv assertion red) |
| R2 | merge_queue.py:362 | a rules page that cannot be read / not a JSON list fails the rules read (E7) | `test_e7_*` | proven (11 wrong-answer reds) |
| R3 | merge_queue.py:367 | a rules row not an object with a string type fails the rules read (E8) | `test_e8_malformed_rules_row_does_not_fit` | proven (9 wrong-answer reds) |
| R4 | merge_queue.py:374 | a rules row of type merge_queue means the branch has a queue | `test_d8_*`, `test_e9_*`, `test_e10_*`, `test_e19_*`, `test_e20_*`, `test_a_rules_row_*` | proven (21 reds; 3 control passes) |
| R5 | merge_queue.py:379 | a merge_queue row whose parameters / max_entries_to_build is unreadable (E9) | `test_e9_unreadable_rules_limit_does_not_fit` | proven (2 wrong-`fits`, 1 wrong-`reason`, 7 wrong-detail reds; see entry) |
| R6 | merge_queue.py:382 | two merge_queue rows with different max_entries_to_build (E10) | `test_e10_*` | proven (2 wrong-`fits`, 2 wrong-detail reds; 1 control pass) |
| G1 | merge_queue.py:398 | the GraphQL call fails (gh non-zero incl. the cloud refusal, OSError, TimeoutExpired, deadline) (E11, E21) | `test_e11_*`, `test_e21_deadline_*`, `test_e21_graphql_is_attempted_*` | proven (9 reds) |
| G2 | merge_queue.py:403 | GraphQL stdout is not a JSON object (E12) | `test_e12_*` | proven (5 wrong-answer reds) |
| G3 | merge_queue.py:407 | GraphQL carries a non-empty errors key (E13) | `test_e13_graphql_errors_do_not_fit_even_beside_a_good_body` | proven (3 reds; 2 control passes) |
| G4 | merge_queue.py:413 | data.repository missing, null or not an object (E14) | `test_e14_*` | proven (7 reds) |
| G5 | merge_queue.py:417 | the mergeQueue key is absent (E15) | `test_e15_mergequeue_key_absent_does_not_fit` | proven |
| G6 | merge_queue.py:422 | a null mergeQueue is a successful no-queue read | `test_d7_*`, `test_e13_an_empty_*`, `test_e19_*`, `test_e21_each_*`, `test_fits_is_answered_*`, `test_d9_cli_no_queue_*`, `test_the_branch_*` | proven (10 reds; 1 control pass) |
| G7 | merge_queue.py:425 | a mergeQueue neither null nor an object is unreadable (E16) | `test_e16_*` | proven (5 reds) |
| G8 | merge_queue.py:434 | a limit that is not a non-negative int is unreadable (E17) | `test_e17_unreadable_graphql_limit_does_not_fit` | proven for present-but-bad values (4 reds); missing/null shapes are subsumed by S7 (7 passes; see entry) |
| G9 | merge_queue.py:436 | an entry count that is not a non-negative int is unreadable (E18) | `test_e18_unreadable_graphql_entry_count_does_not_fit` | proven for present-but-bad values (4 reds); missing/null shapes are subsumed by S7 (6 passes; see entry) |
| S1 | merge_queue.py:451 | bad repo / branch / timeout / deadline_at answer the slots-shaped bad-argument (E1–E4) | `test_e1_*`, `test_e2_*`, `test_e3_*`, `test_e4_*`, `test_bad_argument_comes_*` | proven (33 reds) |
| S2 | merge_queue.py:455 | layers is not an int, is a bool, or is below 1 (E5) | `test_e5_*`, `test_bad_argument_comes_*`, `test_d9_cli_malformed_slots_call_*` | proven (12 reds; 9 control passes) |
| S3 | merge_queue.py:459 | gh is not on PATH (E6) | `test_e6_*`, `test_d10_the_census_covers_*` | proven (2 reds) |
| S4 | merge_queue.py:485 | any failed read answers slots-unreadable (E22 and the failed-read edges) | `test_e22_*`, `test_e7_*`, `test_e11_cloud_*`, `test_e21_*` | proven (9 reds) |
| S5 | merge_queue.py:489 | both reads ok and no queue — the one fit that needs no numbers | `test_d7_*`, `test_d9_cli_no_queue_*`, `test_fits_is_answered_*`, `test_the_branch_*` | proven (4 reds) |
| S6 | merge_queue.py:493 | a rules merge_queue row while GraphQL says null is unreadable (E19) | `test_e19_*`, `test_a_rules_row_*`, `test_fits_is_answered_*` | proven (3 reds) |
| S7 | merge_queue.py:497 | a GraphQL queue without a readable limit and entry count is unreadable (E17, E18) | `test_e17_*`, `test_e18_*` | proven (21 reds) |
| S8 | merge_queue.py:503 | a rules limit that is unreadable or differs from the GraphQL limit is unreadable (E9, E10, E20) | `test_e20_*`, `test_e9_*`, `test_e10_*`, `test_d8_*` | proven (19 reds; 1 control pass) |
| S9 | merge_queue.py:509 | fewer free build slots than layers is slots-short | `test_d2`, `test_d4`, `test_d5`, `test_d6`, `test_d9_cli_short_*` | proven (5 reds; 1 control pass) |
| C1 | merge_queue.py:523 | a malformed slots call is decided by `argv[0]`, so it answers the slots shape | `test_d9_cli_missing_layers_*`, `test_d9_cli_malformed_slots_call_*` | proven (9 reds; 3 control passes) |
| C2 | merge_queue.py:539 | the parse boundary: any other malformed call keeps the read-shaped bad-argument (existing line, body changed) | `test_d9_cli_malformed_call_of_any_other_shape_*`, `test_cli_malformed_is_bad_argument_json_exit_one` | proven (14 reds; 1 control pass) |
| C3 | merge_queue.py:549 | the slots CLI exits 0 only when the stack fits | `test_d9_cli_*` | proven (5 reds) |

---

## R1 — the branch is percent-quoted into the rules path (`_read_rules_limit`)

**neutralization:** `urllib.parse.quote(branch, safe="/")` → `branch  # bite-proof` in `path = "repos/%s/%s/rules/branches/%s" % (owner, name, ...)`.

**red** (`-k "test_the_branch_is_percent_quoted"`):
```
F                                                                        [100%]
=================================== FAILURES ===================================
E   AssertionError: unexpected gh argv: ['gh', 'api', 'repos/owner/example/rules/branches/release/1.0#x?y&per_page=100&page=1']
/home/user/wt-2480/plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py:81: AssertionError: unexpected gh argv: ['gh', 'api', 'repos/owner/example/rules/branches/release/1.0#x?y&per_page=100&page=1']
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_the_branch_is_percent_quoted_into_the_rules_path_slashes_kept
1 failed, 199 deselected in 0.25s
```
(The red is a wrong rules argv reaching the fake gh, the same red the 2459 record accepts for its P1.)

**restore:** inverse Edit. **restored line:**
```python
    path = "repos/%s/%s/rules/branches/%s" % (owner, name, urllib.parse.quote(branch, safe="/"))
```
**green:** `317 passed in 1.09s`

---

## R2 — a rules page that cannot be read, or is not a JSON list (E7)

**neutralization:** `return _FAILED, None, gh.problem or "rules response was not a JSON list"` → `return _NO_QUEUE, None, None  # bite-proof` (the failed page reads as "no queue").

**red** (`-k "test_e7_"`): 11 failures, each the identical pair `E   assert True is False` / `.../test_merge_queue_slots_2480.py:136: assert True is False` (a failed rules read answered `fits: true`); the first pair is shown, 10 identical pairs elided.
```
FFFFFFFFFFF                                                              [100%]
=================================== FAILURES ===================================
E   assert True is False
/home/user/wt-2480/plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py:136: assert True is False
(... 10 further identical pairs elided ...)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e7_rules_exit_nonzero_does_not_fit_even_with_a_list_on_stdout[null-queue]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e7_rules_exit_nonzero_does_not_fit_even_with_a_list_on_stdout[queue]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e7_rules_run_raising_does_not_fit[oserror]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e7_rules_run_raising_does_not_fit[filenotfound]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e7_rules_run_raising_does_not_fit[timeout]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e7_rules_page_not_a_json_list_does_not_fit[not json]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e7_rules_page_not_a_json_list_does_not_fit[]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e7_rules_page_not_a_json_list_does_not_fit[{"message": "x"}]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e7_rules_page_not_a_json_list_does_not_fit[null]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e7_rules_page_not_a_json_list_does_not_fit[5]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e7_a_second_rules_page_that_fails_does_not_fit
11 failed, 189 deselected in 0.39s
```
**restore:** inverse Edit. **restored line:**
```python
        return _FAILED, None, gh.problem or "rules response was not a JSON list"
```
**green:** `317 passed in 1.13s`

---

## R3 — a rules row that is not an object with a string type (E8)

**neutralization:** `return _FAILED, None, "a rules row is not an object with a string type"` → `return _NO_QUEUE, None, None  # bite-proof`.

**red** (`-k "test_e8_"`): 9 failures, each `E   assert True is False` / `...:136: assert True is False`; the first pair is shown, 8 identical pairs elided.
```
FFFFFFFFF                                                                [100%]
=================================== FAILURES ===================================
E   assert True is False
/home/user/wt-2480/plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py:136: assert True is False
(... 8 further identical pairs elided ...)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e8_malformed_rules_row_does_not_fit[rows0]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e8_malformed_rules_row_does_not_fit[rows1]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e8_malformed_rules_row_does_not_fit[rows2]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e8_malformed_rules_row_does_not_fit[rows3]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e8_malformed_rules_row_does_not_fit[rows4]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e8_malformed_rules_row_does_not_fit[rows5]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e8_malformed_rules_row_does_not_fit[rows6]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e8_malformed_rules_row_does_not_fit[rows7]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e8_malformed_rules_row_does_not_fit[rows8]
9 failed, 191 deselected in 0.45s
```
**restore:** inverse Edit. **restored line:**
```python
            return _FAILED, None, "a rules row is not an object with a string type"
```
**green:** `317 passed in 1.15s`

---

## R4 — a rules row of type merge_queue means the branch has a queue

**neutralization:** `if row["type"] == "merge_queue":` → `if False:  # bite-proof` (a queue row is never seen).

**red** (`-k "test_d3 or test_d4 or test_d8 or test_e9 or test_e10 or test_e19 or test_e20 or test_a_rules_row"`): 21 failed, 3 passed. 20 failures are the pair `E   assert True is False` / `...:136: assert True is False` (a queue the rules show answered `fits: true`); one is `E   AssertionError: assert 'slots-short' == 'slots-unreadable'` / `...:137` (`test_e9_*[row8-0]`, `False` read as limit 0). In the run the `:137` block sits after 10 `:136` pairs and before 10 more; the first pair and the `:137` block are shown, 19 identical `:136` pairs elided.
```
..FFFFFFFFFFFFFFFF.FFFFF                                                 [100%]
=================================== FAILURES ===================================
E   assert True is False
/home/user/wt-2480/plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py:136: assert True is False
(... 9 further identical `:136` pairs elided, up to the `:137` block ...)
E   AssertionError: assert 'slots-short' == 'slots-unreadable'
      
      - slots-unreadable
      + slots-short
/home/user/wt-2480/plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py:137: AssertionError: assert 'slots-short' == 'slots-unreadable'
(... 10 further identical `:136` pairs elided after it ...)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_d8_queue_row_on_rules_page_two_is_found_and_its_limit_checked
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_a_rules_row_beside_a_null_graphql_queue_is_not_a_no_queue_answer_on_page_two
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e9_unreadable_rules_limit_does_not_fit[row0-5]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e9_unreadable_rules_limit_does_not_fit[row1-5]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e9_unreadable_rules_limit_does_not_fit[row2-5]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e9_unreadable_rules_limit_does_not_fit[row3-5]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e9_unreadable_rules_limit_does_not_fit[row4-5]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e9_unreadable_rules_limit_does_not_fit[row5-5]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e9_unreadable_rules_limit_does_not_fit[row6-5]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e9_unreadable_rules_limit_does_not_fit[row7-1]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e9_unreadable_rules_limit_does_not_fit[row8-0]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e9_unreadable_rules_limit_does_not_fit[row9-5]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e10_two_rows_with_different_limits_do_not_fit_on_one_page[5-7-7]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e10_two_rows_with_different_limits_do_not_fit_on_one_page[7-5-7]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e10_two_rows_with_different_limits_do_not_fit_on_one_page[5-7-5]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e10_two_rows_with_different_limits_across_pages_do_not_fit
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e19_rules_queue_row_while_graphql_says_null_does_not_fit
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e20_rules_limit_differing_from_graphql_limit_does_not_fit[7-5-0-1]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e20_rules_limit_differing_from_graphql_limit_does_not_fit[3-5-0-3]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e20_rules_limit_differing_from_graphql_limit_does_not_fit[5-7-0-5]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e20_rules_limit_differing_from_graphql_limit_does_not_fit[0-5-0-1]
21 failed, 3 passed, 176 deselected in 0.41s
```
(The progress line, the `:137` block, the summary list and the totals are verbatim. The 3 passes, marked `.`, are `test_d3`, `test_d4` and `test_e10_two_rows_with_the_same_limit_fit`, which do not depend on the row being seen.)

**restore:** inverse Edit. **restored line:**
```python
        if row["type"] == "merge_queue":
```
**green:** `317 passed in 1.24s`

---

## R5 — a merge_queue row whose parameters / max_entries_to_build is unreadable (E9)

**neutralization:** `if not _is_count(raw):` → `if False:  # bite-proof`.

**red** (`-k "test_e9_"`; the `[row7-1]`/`[row6-5]` cases are the wrong-`fits` reds, `[row8-0]` the wrong-`reason` red, the rest wrong-detail reds):
```
FFFFFFFFFF                                                               [100%]
=================================== FAILURES ===================================
E   AssertionError: assert 'no readable max_entries_to_build' in 'rules max_entries_to_build None differs from graphql maximumEntriesToBuild 5'
/home/user/wt-2480/plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py:402: AssertionError: assert 'no readable max_entries_to_build' in 'rules max_entries_to_build None differs from graphql maximumEntriesToBuild 5'
(... 4 further identical pairs elided: rows 1 to 4, same text ...)
E   AssertionError: assert 'no readable max_entries_to_build' in 'rules max_entries_to_build 5 differs from graphql maximumEntriesToBuild 5'
/home/user/wt-2480/plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py:402: AssertionError: assert 'no readable max_entries_to_build' in 'rules max_entries_to_build 5 differs from graphql maximumEntriesToBuild 5'
E   assert True is False
/home/user/wt-2480/plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py:136: assert True is False
E   assert True is False
/home/user/wt-2480/plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py:136: assert True is False
E   AssertionError: assert 'slots-short' == 'slots-unreadable'
      
      - slots-unreadable
      + slots-short
/home/user/wt-2480/plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py:137: AssertionError: assert 'slots-short' == 'slots-unreadable'
E   AssertionError: assert 'no readable max_entries_to_build' in 'rules max_entries_to_build -1 differs from graphql maximumEntriesToBuild 5'
/home/user/wt-2480/plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py:402: AssertionError: assert 'no readable max_entries_to_build' in 'rules max_entries_to_build -1 differs from graphql maximumEntriesToBuild 5'
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e9_unreadable_rules_limit_does_not_fit[row0-5]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e9_unreadable_rules_limit_does_not_fit[row1-5]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e9_unreadable_rules_limit_does_not_fit[row2-5]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e9_unreadable_rules_limit_does_not_fit[row3-5]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e9_unreadable_rules_limit_does_not_fit[row4-5]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e9_unreadable_rules_limit_does_not_fit[row5-5]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e9_unreadable_rules_limit_does_not_fit[row6-5]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e9_unreadable_rules_limit_does_not_fit[row7-1]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e9_unreadable_rules_limit_does_not_fit[row8-0]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e9_unreadable_rules_limit_does_not_fit[row9-5]
10 failed, 190 deselected in 0.34s
```
**Honest limit of this proof:** with this guard neutralized, the unreadable rules limit still cannot make a wrong `fits` unless it compares equal to the GraphQL limit. A missing / `None` / non-object `parameters` / `"5"` / `-1` limit is also caught by the S8 limits-differ check, so those cases go red only on the detail text (`"no readable max_entries_to_build"` expected; `"... differs from ..."` seen), not on `fits`. The cases that go red on the answer are `5.0` (JSON `5.0` equals int `5`) and `True` (equals `1`) — wrong `fits: true` — and `False` against a limit of 0 — wrong `reason` (`slots-short`). The R5 guard is therefore the only defence for those three values.

**restore:** inverse Edit. **restored line:**
```python
            if not _is_count(raw):
```
**green:** `317 passed in 1.06s`

---

## R6 — two merge_queue rows with different max_entries_to_build (E10)

**neutralization:** `if limit is not None and raw != limit:` → `if False:  # bite-proof`.

**red** (`-k "test_e10_"`; the `.` is `test_e10_two_rows_with_the_same_limit_fit`, which must pass both ways; `[5-7-7]` and the across-pages case go red on the answer, because the last row's limit then equals the GraphQL limit):
```
FFFF.                                                                    [100%]
=================================== FAILURES ===================================
E   assert True is False
/home/user/wt-2480/plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py:136: assert True is False
E   AssertionError: assert 'disagree' in 'rules max_entries_to_build 5 differs from graphql maximumEntriesToBuild 7'
/home/user/wt-2480/plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py:412: AssertionError: assert 'disagree' in 'rules max_entries_to_build 5 differs from graphql maximumEntriesToBuild 7'
E   AssertionError: assert 'disagree' in 'rules max_entries_to_build 7 differs from graphql maximumEntriesToBuild 5'
/home/user/wt-2480/plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py:412: AssertionError: assert 'disagree' in 'rules max_entries_to_build 7 differs from graphql maximumEntriesToBuild 5'
E   assert True is False
/home/user/wt-2480/plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py:136: assert True is False
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e10_two_rows_with_different_limits_do_not_fit_on_one_page[5-7-7]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e10_two_rows_with_different_limits_do_not_fit_on_one_page[7-5-7]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e10_two_rows_with_different_limits_do_not_fit_on_one_page[5-7-5]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e10_two_rows_with_different_limits_across_pages_do_not_fit
4 failed, 1 passed, 195 deselected in 0.33s
```
(The `[7-5-7]` and `[5-7-5]` cases are caught by S8 on the answer but differ in detail, so they show the wrong-detail red.)

**restore:** inverse Edit. **restored line:**
```python
            if limit is not None and raw != limit:
```
**green:** `317 passed in 1.17s`

---

## G1 — the GraphQL call fails (E11; also E21)

**neutralization:** `return _FAILED, None, None, gh.problem` → `return _NO_QUEUE, None, None, None  # bite-proof`.

**red** (`-k "test_e11_ or test_e21_deadline or test_e21_graphql"`): 9 failures — 6 are the pair `E   assert True is False` / `...:136`, 3 are the `reads` mismatch shown (`{'graphql': 'ok'} != {'graphql': 'failed'}`, at `:446`, `:618`, `:640`); the first of each kind shown, the other blocks elided.
```
FFFFFFFFF                                                                [100%]
=================================== FAILURES ===================================
E   assert True is False
/home/user/wt-2480/plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py:136: assert True is False
E   AssertionError: assert {'rules': 'ok...raphql': 'ok'} == {'rules': 'ok...ql': 'failed'}
      
      Omitting 1 identical items, use -vv to show
      Differing items:
      {'graphql': 'ok'} != {'graphql': 'failed'}
      Use -v to get more diff
/home/user/wt-2480/plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py:446: AssertionError: assert {'rules': 'ok...raphql': 'ok'} == {'rules': 'ok...ql': 'failed'}
(... 7 further failure blocks of the same two kinds elided: `:136` x5 more, and the `reads` mismatches at `:618` and `:640` ...)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e11_cloud_proxy_graphql_refusal_does_not_fit
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e11_cloud_proxy_graphql_refusal_beside_a_rules_queue_row_reports_queue_true
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e11_graphql_exit_nonzero_with_a_good_body_still_does_not_fit
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e11_graphql_run_raising_does_not_fit[oserror]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e11_graphql_run_raising_does_not_fit[filenotfound]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e11_graphql_run_raising_does_not_fit[timeout]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e21_deadline_already_passed_makes_no_call_and_does_not_fit
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e21_deadline_passing_between_the_reads_makes_no_graphql_call
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e21_graphql_is_attempted_after_a_failed_rules_read_so_reads_reports_both
9 failed, 191 deselected in 0.35s
```
**restore:** inverse Edit. **restored line:**
```python
        return _FAILED, None, None, gh.problem
```
**green:** `317 passed in 1.14s`

---

## G2 — GraphQL stdout is not a JSON object (E12)

**neutralization:** `return _FAILED, None, None, "graphql response is not a JSON object"` → `return _NO_QUEUE, None, None, None  # bite-proof`.

**red** (`-k "test_e12_"`): 5 failures, each `E   assert True is False` / `...:136`; first pair shown, 4 identical pairs elided.
```
FFFFF                                                                    [100%]
=================================== FAILURES ===================================
E   assert True is False
/home/user/wt-2480/plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py:136: assert True is False
(... 4 further identical pairs elided ...)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e12_graphql_stdout_not_a_json_object_does_not_fit[not json]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e12_graphql_stdout_not_a_json_object_does_not_fit[]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e12_graphql_stdout_not_a_json_object_does_not_fit[[]]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e12_graphql_stdout_not_a_json_object_does_not_fit[null]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e12_graphql_stdout_not_a_json_object_does_not_fit[5]
5 failed, 195 deselected in 0.36s
```
**restore:** inverse Edit. **restored line:**
```python
        return _FAILED, None, None, "graphql response is not a JSON object"
```
**green:** `317 passed in 1.42s`

---

## G3 — GraphQL carries a non-empty errors key (E13)

**neutralization:** `return _FAILED, None, None, "graphql response carries errors: %s" % (body.get("errors"),)` → `pass  # bite-proof`.

**red** (`-k "test_e13_"`; the 2 passes are `test_e13_an_empty_or_null_errors_key_does_not_fail_the_read`, which must pass both ways):
```
FFF..                                                                    [100%]
=================================== FAILURES ===================================
E   assert True is False
/home/user/wt-2480/plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py:136: assert True is False
(... 2 further identical pairs elided ...)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e13_graphql_errors_do_not_fit_even_beside_a_good_body[errors0]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e13_graphql_errors_do_not_fit_even_beside_a_good_body[boom]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e13_graphql_errors_do_not_fit_even_beside_a_good_body[errors2]
3 failed, 2 passed, 195 deselected in 0.40s
```
**restore:** inverse Edit. **restored line:**
```python
        return _FAILED, None, None, "graphql response carries errors: %s" % (body.get("errors"),)
```
**green:** `317 passed in 1.09s`

---

## G4 — data.repository missing, null or not an object (E14)

**neutralization:** `return _FAILED, None, None, "graphql response has no data.repository object"` → `return _NO_QUEUE, None, None, None  # bite-proof`.

**red** (`-k "test_e14_"`): 7 failures, each `E   assert True is False` / `...:136`; first pair shown, 6 identical pairs elided.
```
FFFFFFF                                                                  [100%]
=================================== FAILURES ===================================
E   assert True is False
/home/user/wt-2480/plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py:136: assert True is False
(... 6 further identical pairs elided ...)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e14_missing_or_null_repository_does_not_fit[body0]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e14_missing_or_null_repository_does_not_fit[body1]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e14_missing_or_null_repository_does_not_fit[body2]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e14_missing_or_null_repository_does_not_fit[body3]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e14_missing_or_null_repository_does_not_fit[body4]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e14_missing_or_null_repository_does_not_fit[body5]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e14_missing_or_null_repository_does_not_fit[body6]
7 failed, 193 deselected in 0.31s
```
**restore:** inverse Edit. **restored line:**
```python
        return _FAILED, None, None, "graphql response has no data.repository object"
```
**green:** `317 passed in 1.19s`

---

## G5 — the mergeQueue key is absent (E15)

**neutralization:** `return _FAILED, None, None, "graphql repository carries no mergeQueue key"` → `return _NO_QUEUE, None, None, None  # bite-proof`.

**red** (`-k "test_e15_"`):
```
F                                                                        [100%]
=================================== FAILURES ===================================
E   assert True is False
/home/user/wt-2480/plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py:136: assert True is False
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e15_mergequeue_key_absent_does_not_fit
1 failed, 199 deselected in 0.29s
```
**restore:** inverse Edit. **restored line:**
```python
        return _FAILED, None, None, "graphql repository carries no mergeQueue key"
```
**green:** `317 passed in 1.19s`

---

## G6 — a null mergeQueue is a successful no-queue read

**neutralization:** `if merge_queue is None:` → `if False:  # bite-proof` (a null now falls to the "neither null nor an object" failure).

**red** (`-k "test_d7 or test_d9_cli_no_queue or test_e13_an_empty or test_the_branch or test_e19 or test_fits_is_answered or test_e21_each or test_a_rules_row"`; the 1 pass, `.`, is `test_a_rules_row_beside_a_null_graphql_queue_...`, which expects an unreadable answer either way). 10 failures; the `:217` block, the `:588` block and the `:700` block are shown; the identical `:257`, `:491` (x2), `:656` (x3) and `:743` blocks are listed by line and otherwise elided.
```
F.FFFFFFFFF                                                              [100%]
=================================== FAILURES ===================================
E   AssertionError: assert {'ok': True, ...t': None, ...} == {'ok': True, ...t': None, ...}
      
      Omitting 7 identical items, use -vv to show
      Differing items:
      {'queue': None} != {'queue': False}
      {'reason': 'slots-unreadable'} != {'reason': None}
      {'reads': {'rules': 'ok', 'graphql': 'failed'}} != {'reads': {'rules': 'ok', 'graphql': 'ok'}}
      {'fits': False} != {'fits': True}
      {'detail': 'graphql read failed: graphql mergeQueue is neither null nor an object'} != {'detail': None}
      Use -v to get more diff
/home/user/wt-2480/plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py:217: AssertionError: assert {'ok': True, ...t': None, ...} == {'ok': True, ...t': None, ...}
E   assert False is True
/home/user/wt-2480/plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py:257: assert False is True
(... `:491` x2 `assert False is True`; `:588` reads mismatch `{'graphql': 'failed'} != {'graphql': 'ok'}`; `:656` x3 `assert False is True` elided ...)
E   AssertionError: assert [('none', 'qu...ueue-5-of-0')] == [('none', 'nu...ueue-5-of-0')]
      
      At index 0 diff: ('none', 'queue-5-of-0') != ('none', 'null')
      Right contains one more item: ('row-5', 'queue-5-of-0')
      Use -v to get more diff
/home/user/wt-2480/plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py:700: AssertionError: assert [('none', 'qu...ueue-5-of-0')] == [('none', 'nu...ueue-5-of-0')]
E   assert 1 == 0
/home/user/wt-2480/plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py:743: assert 1 == 0
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_d7_both_reads_no_queue_fits_with_no_numbers
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_the_branch_is_percent_quoted_into_the_rules_path_slashes_kept
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e13_an_empty_or_null_errors_key_does_not_fail_the_read[errors0]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e13_an_empty_or_null_errors_key_does_not_fail_the_read[None]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e19_rules_queue_row_while_graphql_says_null_does_not_fit
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e21_each_calls_timeout_is_the_smaller_of_timeout_and_the_time_left[120-10.0-10.0]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e21_each_calls_timeout_is_the_smaller_of_timeout_and_the_time_left[3-10.0-3]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e21_each_calls_timeout_is_the_smaller_of_timeout_and_the_time_left[120-1000.0-120]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_fits_is_answered_only_on_the_two_allowed_paths
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_d9_cli_no_queue_round_trip_exits_zero
10 failed, 1 passed, 189 deselected in 0.37s
```
**restore:** inverse Edit. **restored lines:**
```python
    if merge_queue is None:
        return _NO_QUEUE, None, None, None
```
**green:** `317 passed in 1.29s`

---

## G7 — a mergeQueue neither null nor an object is unreadable (E16)

**neutralization:** `return _FAILED, None, None, "graphql mergeQueue is neither null nor an object"` → `return _NO_QUEUE, None, None, None  # bite-proof`.

**red** (`-k "test_e16_"`): 5 failures, each `E   assert True is False` / `...:136`; first pair shown, 4 identical pairs elided.
```
FFFFF                                                                    [100%]
=================================== FAILURES ===================================
E   assert True is False
/home/user/wt-2480/plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py:136: assert True is False
(... 4 further identical pairs elided ...)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e16_mergequeue_neither_null_nor_object_does_not_fit[MQ_x]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e16_mergequeue_neither_null_nor_object_does_not_fit[value1]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e16_mergequeue_neither_null_nor_object_does_not_fit[5]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e16_mergequeue_neither_null_nor_object_does_not_fit[True]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e16_mergequeue_neither_null_nor_object_does_not_fit[False]
5 failed, 195 deselected in 0.33s
```
**restore:** inverse Edit. **restored line:**
```python
        return _FAILED, None, None, "graphql mergeQueue is neither null nor an object"
```
**green:** `317 passed in 1.18s`

---

## G8 — a limit that is not a non-negative int is unreadable (E17)

**neutralization:** `limit = raw_limit if _is_count(raw_limit) else None` → `limit = raw_limit  # bite-proof`.

**red** (`-k "test_e17_"`; the 7 passes, `.`, are the missing / null / non-object `configuration`, `{}`, and `None` cases, whose `limit` is `None` either way and are caught by S7):
```
......FFFF.                                                              [100%]
=================================== FAILURES ===================================
E   TypeError: unsupported operand type(s) for -: 'str' and 'int'
/home/user/wt-2480/plugins/superheroes/lib/merge_queue.py:474: TypeError: unsupported operand type(s) for -: 'str' and 'int'
E   assert True is False
/home/user/wt-2480/plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py:136: assert True is False
E   assert True is False
/home/user/wt-2480/plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py:136: assert True is False
E   AssertionError: assert 'slots-short' == 'slots-unreadable'
      
      - slots-unreadable
      + slots-short
/home/user/wt-2480/plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py:137: AssertionError: assert 'slots-short' == 'slots-unreadable'
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e17_unreadable_graphql_limit_does_not_fit[merge_queue6]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e17_unreadable_graphql_limit_does_not_fit[merge_queue7]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e17_unreadable_graphql_limit_does_not_fit[merge_queue8]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e17_unreadable_graphql_limit_does_not_fit[merge_queue9]
4 failed, 7 passed, 189 deselected in 0.33s
```
Reds: `"5"` is an exception (`TypeError`, `[merge_queue6]`); `5.0` and `True` are wrong `fits: true` (`[merge_queue7]`, `[merge_queue8]`); `-1` is wrong `reason` `slots-short` (`[merge_queue9]`). **Honest limit:** the missing / null shapes are not discriminated by this line — with it neutralized `limit` is `None` anyway and S7 answers; they are guarded by S7 (which is proven). This line is the only defence for the present-but-bad values.

**restore:** inverse Edit. **restored line:**
```python
    limit = raw_limit if _is_count(raw_limit) else None
```
**green:** `317 passed in 1.22s`

---

## G9 — an entry count that is not a non-negative int is unreadable (E18)

**neutralization:** `queued = raw_queued if _is_count(raw_queued) else None` → `queued = raw_queued  # bite-proof`.

**red** (`-k "test_e18_"`; the 6 passes are the missing / null / non-object `entries`, `{}`, `None` cases, caught by S7):
```
......FFFF                                                               [100%]
=================================== FAILURES ===================================
E   TypeError: unsupported operand type(s) for -: 'int' and 'str'
/home/user/wt-2480/plugins/superheroes/lib/merge_queue.py:474: TypeError: unsupported operand type(s) for -: 'int' and 'str'
E   assert True is False
/home/user/wt-2480/plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py:136: assert True is False
E   assert True is False
/home/user/wt-2480/plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py:136: assert True is False
E   assert True is False
/home/user/wt-2480/plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py:136: assert True is False
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e18_unreadable_graphql_entry_count_does_not_fit[merge_queue6]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e18_unreadable_graphql_entry_count_does_not_fit[merge_queue7]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e18_unreadable_graphql_entry_count_does_not_fit[merge_queue8]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e18_unreadable_graphql_entry_count_does_not_fit[merge_queue9]
4 failed, 6 passed, 190 deselected in 0.34s
```
Reds: `"0"` is an exception (`TypeError`); `0.0`, `True` and `-1` are wrong `fits: true` (limit 5, three layers). Same honest limit as G8 for the missing / null shapes.

**restore:** inverse Edit. **restored line:**
```python
    queued = raw_queued if _is_count(raw_queued) else None
```
**green:** `317 passed in 1.43s`

---

## S1 — bad repo / branch / timeout / deadline_at answer the slots-shaped bad-argument (E1–E4)

**neutralization:** `return _slots_bad_argument(refusal["detail"])` → `return _slots_result(repo, branch, layers, fits=True)  # bite-proof`.

**red** (`-k "test_e1_ or test_e2_ or test_e3_ or test_e4_ or test_bad_argument_comes"`): 33 failures, each the pair `E   assert True is False` / `...:144: assert True is False`; first pair shown, 32 identical pairs elided.
```
FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF                                        [100%]
=================================== FAILURES ===================================
E   assert True is False
/home/user/wt-2480/plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py:144: assert True is False
(... 32 further identical pairs elided ...)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e1_bad_repo[None]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e1_bad_repo[5]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e1_bad_repo[owner]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e1_bad_repo[owner/]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e1_bad_repo[/name]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e1_bad_repo[o/n/x]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e1_bad_repo[own er/name]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e1_bad_repo[o/n\n]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e1_bad_repo[]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e2_bad_branch[None]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e2_bad_branch[5]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e2_bad_branch[]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e2_bad_branch[a b]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e2_bad_branch[a\tb]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e2_bad_branch[a\nb]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e2_bad_branch[main\n]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e2_bad_branch[a\x00b]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e2_bad_branch[a\x7fb]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e2_bad_branch[a\x85b]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e3_bad_timeout[0]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e3_bad_timeout[-3]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e3_bad_timeout[True]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e3_bad_timeout[5]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e3_bad_timeout[None]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e3_bad_timeout[nan]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e3_bad_timeout[inf]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e4_bad_deadline_at[True]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e4_bad_deadline_at[5]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e4_bad_deadline_at[nan]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e4_bad_deadline_at[inf]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e4_bad_deadline_at[-inf]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e4_bad_deadline_at[deadline_at5]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_bad_argument_comes_before_the_gh_check
33 failed, 167 deselected in 0.41s
```
**restore:** inverse Edit. **restored line:**
```python
        return _slots_bad_argument(refusal["detail"])
```
**green:** `317 passed in 1.24s`

---

## S2 — layers is not an int, is a bool, or is below 1 (E5)

**neutralization:** `return _slots_bad_argument("layers must be an integer of at least 1")` → `return _slots_result(repo, branch, layers, fits=True)  # bite-proof`.

**red** (`-k "test_e5_ or test_d9_cli_malformed_slots_call or test_bad_argument_comes"`; the 9 passes are the `test_d9_cli_malformed_slots_call_*` cases that never reach `slots()`):
```
FFFFFFFFFF........FF.                                                    [100%]
=================================== FAILURES ===================================
E   assert True is False
/home/user/wt-2480/plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py:144: assert True is False
(... 9 further identical `:144` pairs elided ...)
E   assert 0 == 1
/home/user/wt-2480/plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py:778: assert 0 == 1
E   assert 0 == 1
/home/user/wt-2480/plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py:778: assert 0 == 1
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e5_bad_layers[None]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e5_bad_layers[3]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e5_bad_layers[3.0]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e5_bad_layers[True]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e5_bad_layers[False]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e5_bad_layers[0]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e5_bad_layers[-1]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e5_bad_layers[layers7]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e5_bad_layers[layers8]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_bad_argument_comes_before_the_gh_check
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_d9_cli_malformed_slots_call_is_the_slots_shaped_bad_argument[argv8]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_d9_cli_malformed_slots_call_is_the_slots_shaped_bad_argument[argv9]
12 failed, 9 passed, 179 deselected in 0.35s
```
**restore:** inverse Edit. **restored line:**
```python
        return _slots_bad_argument("layers must be an integer of at least 1")
```
**green:** `317 passed in 1.18s`

---

## S3 — gh is not on PATH (E6)

**neutralization:** the three-line `return _slots_result(repo, branch, layers, reads={"rules": READ_FAILED, "graphql": READ_FAILED}, reason=REASON_SLOTS_UNREADABLE, detail="gh not on PATH")` → `return _slots_result(repo, branch, layers, fits=True)  # bite-proof`.

**red** (`-k "test_e6_ or test_d10_the_census"`):
```
FF                                                                       [100%]
=================================== FAILURES ===================================
E   assert True is False
/home/user/wt-2480/plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py:136: assert True is False
E   assert True is False
/home/user/wt-2480/plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py:902: assert True is False
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e6_gh_not_on_path_does_not_fit_and_makes_no_call
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_d10_the_census_covers_the_gh_not_on_path_result_too
2 failed, 198 deselected in 0.36s
```
**restore:** inverse Edit. **restored lines:**
```python
        return _slots_result(repo, branch, layers,
                             reads={"rules": READ_FAILED, "graphql": READ_FAILED},
                             reason=REASON_SLOTS_UNREADABLE, detail="gh not on PATH")
```
**green:** `317 passed in 1.41s`

---

## S4 — any failed read answers slots-unreadable (E22 and the failed-read edges)

**neutralization:** `return unreadable(_failed_details(rules_detail, graphql_detail))` → `return fits(queue)  # bite-proof`.

**red** (`-k "test_e22_ or test_e7_rules_exit or test_e11_cloud or test_e21_graphql_is_attempted or test_e21_deadline"`): 9 failures, each `E   assert True is False` / `...:136`; first pair shown, 8 identical pairs elided.
```
FFFFFFFFF                                                                [100%]
=================================== FAILURES ===================================
E   assert True is False
/home/user/wt-2480/plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py:136: assert True is False
(... 8 further identical pairs elided ...)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e7_rules_exit_nonzero_does_not_fit_even_with_a_list_on_stdout[null-queue]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e7_rules_exit_nonzero_does_not_fit_even_with_a_list_on_stdout[queue]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e11_cloud_proxy_graphql_refusal_does_not_fit
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e11_cloud_proxy_graphql_refusal_beside_a_rules_queue_row_reports_queue_true
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e21_deadline_already_passed_makes_no_call_and_does_not_fit
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e21_deadline_passing_between_the_reads_makes_no_graphql_call
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e21_graphql_is_attempted_after_a_failed_rules_read_so_reads_reports_both
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e22_rules_failed_and_graphql_queue_with_room_does_not_fit_but_reports_numbers
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e22_rules_failed_and_graphql_queue_short_is_unreadable_not_short
9 failed, 191 deselected in 0.39s
```
**restore:** inverse Edit. **restored line:**
```python
        return unreadable(_failed_details(rules_detail, graphql_detail))
```
**green:** `317 passed in 1.22s`

---

## S5 — both reads ok and no queue: the one fit that needs no numbers

**neutralization:** `if rules_state == _NO_QUEUE and graphql_state == _NO_QUEUE:` → `if False:  # bite-proof` (the pair then falls to S6 and answers unreadable).

**red** (`-k "test_d7 or test_d9_cli_no_queue or test_fits_is_answered or test_the_branch"`):
```
FFFF                                                                     [100%]
=================================== FAILURES ===================================
E   AssertionError: assert {'ok': True, ...t': None, ...} == {'ok': True, ...t': None, ...}
      
      Omitting 8 identical items, use -vv to show
      Differing items:
      {'queue': None} != {'queue': False}
      {'fits': False} != {'fits': True}
      {'detail': 'rules carry a merge_queue row but graphql reports no merge queue'} != {'detail': None}
      {'reason': 'slots-unreadable'} != {'reason': None}
      Use -v to get more diff
/home/user/wt-2480/plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py:217: AssertionError: assert {'ok': True, ...t': None, ...} == {'ok': True, ...t': None, ...}
E   assert False is True
/home/user/wt-2480/plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py:257: assert False is True
E   AssertionError: assert [('none', 'qu...ueue-5-of-0')] == [('none', 'nu...ueue-5-of-0')]
      
      At index 0 diff: ('none', 'queue-5-of-0') != ('none', 'null')
      Right contains one more item: ('row-5', 'queue-5-of-0')
      Use -v to get more diff
/home/user/wt-2480/plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py:700: AssertionError: assert [('none', 'qu...ueue-5-of-0')] == [('none', 'nu...ueue-5-of-0')]
E   assert 1 == 0
/home/user/wt-2480/plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py:743: assert 1 == 0
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_d7_both_reads_no_queue_fits_with_no_numbers
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_the_branch_is_percent_quoted_into_the_rules_path_slashes_kept
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_fits_is_answered_only_on_the_two_allowed_paths
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_d9_cli_no_queue_round_trip_exits_zero
4 failed, 196 deselected in 0.35s
```
(The reds are the correct no-queue fit answered `fits: false`. The detail text seen in the first block is S6's, which catches the pair once S5 is off; that it is S6 doing so is why the `queue`/`fits`/`reason` differences, not the detail, are the evidence.)

**restore:** inverse Edit. **restored line:**
```python
    if rules_state == _NO_QUEUE and graphql_state == _NO_QUEUE:
```
**green:** `317 passed in 1.39s`

---

## S6 — a rules merge_queue row while GraphQL says null is unreadable (E19)

**neutralization:** `return unreadable("rules carry a merge_queue row but graphql reports no merge queue")` → `return fits(queue)  # bite-proof`.

**red** (`-k "test_e19 or test_a_rules_row or test_fits_is_answered or test_d10_every_result_has_exactly_the_twelve_keys"`; the 23 passes include the census, whose invariants hold for any well-formed result):
```
FFF.......................                                               [100%]
=================================== FAILURES ===================================
E   assert True is False
/home/user/wt-2480/plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py:136: assert True is False
E   assert True is False
/home/user/wt-2480/plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py:136: assert True is False
E   AssertionError: assert [('none', 'nu...bad', 'null')] == [('none', 'nu...ueue-5-of-0')]
      
      At index 3 diff: ('row-5', 'null') != ('row-5', 'queue-5-of-0')
      Left contains 2 more items, first extra item: ('row-5', 'queue-5-of-0')
      Use -v to get more diff
/home/user/wt-2480/plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py:700: AssertionError: assert [('none', 'nu...bad', 'null')] == [('none', 'nu...ueue-5-of-0')]
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_a_rules_row_beside_a_null_graphql_queue_is_not_a_no_queue_answer_on_page_two
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e19_rules_queue_row_while_graphql_says_null_does_not_fit
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_fits_is_answered_only_on_the_two_allowed_paths
3 failed, 23 passed, 174 deselected in 0.37s
```
**restore:** inverse Edit. **restored line:**
```python
        return unreadable("rules carry a merge_queue row but graphql reports no merge queue")
```
**green:** `317 passed in 1.30s`

---

## S7 — a GraphQL queue without a readable limit and entry count is unreadable (E17, E18)

**neutralization:** `return unreadable("graphql mergeQueue has no readable %s" % " or ".join(missing))` → `return fits(queue)  # bite-proof`.

**red** (`-k "test_e17_ or test_e18_"`): 21 failures, each `E   assert True is False` / `...:136`; first pair shown, 20 identical pairs elided.
```
FFFFFFFFFFFFFFFFFFFFF                                                    [100%]
=================================== FAILURES ===================================
E   assert True is False
/home/user/wt-2480/plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py:136: assert True is False
(... 20 further identical pairs elided ...)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e17_unreadable_graphql_limit_does_not_fit[merge_queue0]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e17_unreadable_graphql_limit_does_not_fit[merge_queue1]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e17_unreadable_graphql_limit_does_not_fit[merge_queue2]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e17_unreadable_graphql_limit_does_not_fit[merge_queue3]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e17_unreadable_graphql_limit_does_not_fit[merge_queue4]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e17_unreadable_graphql_limit_does_not_fit[merge_queue5]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e17_unreadable_graphql_limit_does_not_fit[merge_queue6]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e17_unreadable_graphql_limit_does_not_fit[merge_queue7]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e17_unreadable_graphql_limit_does_not_fit[merge_queue8]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e17_unreadable_graphql_limit_does_not_fit[merge_queue9]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e18_unreadable_graphql_entry_count_does_not_fit[merge_queue0]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e18_unreadable_graphql_entry_count_does_not_fit[merge_queue1]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e18_unreadable_graphql_entry_count_does_not_fit[merge_queue2]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e18_unreadable_graphql_entry_count_does_not_fit[merge_queue3]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e18_unreadable_graphql_entry_count_does_not_fit[merge_queue4]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e18_unreadable_graphql_entry_count_does_not_fit[merge_queue5]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e18_unreadable_graphql_entry_count_does_not_fit[merge_queue6]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e18_unreadable_graphql_entry_count_does_not_fit[merge_queue7]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e18_unreadable_graphql_entry_count_does_not_fit[merge_queue8]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e18_unreadable_graphql_entry_count_does_not_fit[merge_queue9]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e17_e18_both_unreadable_names_both
21 failed, 179 deselected in 0.38s
```
**restore:** inverse Edit. **restored line:**
```python
        return unreadable("graphql mergeQueue has no readable %s" % " or ".join(missing))
```
**green:** `317 passed in 1.34s`

---

## S8 — a rules limit that is unreadable or differs from the GraphQL limit is unreadable (E9, E10, E20)

**neutralization:** the three-line `return unreadable(rules_detail or "rules max_entries_to_build %s differs from graphql " "maximumEntriesToBuild %s" % (rules_limit, limit))` → `return fits(queue)  # bite-proof`.

**red** (`-k "test_e20_ or test_e9_ or test_e10_ or test_d8"`; the 1 pass is `test_e10_two_rows_with_the_same_limit_fit`): 19 failures, each `E   assert True is False` / `...:136`; first pair shown, 18 identical pairs elided.
```
FFFFFFFFFFFFFFF.FFFF                                                     [100%]
=================================== FAILURES ===================================
E   assert True is False
/home/user/wt-2480/plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py:136: assert True is False
(... 18 further identical pairs elided ...)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_d8_queue_row_on_rules_page_two_is_found_and_its_limit_checked
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e9_unreadable_rules_limit_does_not_fit[row0-5]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e9_unreadable_rules_limit_does_not_fit[row1-5]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e9_unreadable_rules_limit_does_not_fit[row2-5]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e9_unreadable_rules_limit_does_not_fit[row3-5]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e9_unreadable_rules_limit_does_not_fit[row4-5]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e9_unreadable_rules_limit_does_not_fit[row5-5]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e9_unreadable_rules_limit_does_not_fit[row6-5]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e9_unreadable_rules_limit_does_not_fit[row7-1]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e9_unreadable_rules_limit_does_not_fit[row8-0]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e9_unreadable_rules_limit_does_not_fit[row9-5]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e10_two_rows_with_different_limits_do_not_fit_on_one_page[5-7-7]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e10_two_rows_with_different_limits_do_not_fit_on_one_page[7-5-7]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e10_two_rows_with_different_limits_do_not_fit_on_one_page[5-7-5]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e10_two_rows_with_different_limits_across_pages_do_not_fit
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e20_rules_limit_differing_from_graphql_limit_does_not_fit[7-5-0-1]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e20_rules_limit_differing_from_graphql_limit_does_not_fit[3-5-0-3]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e20_rules_limit_differing_from_graphql_limit_does_not_fit[5-7-0-5]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_e20_rules_limit_differing_from_graphql_limit_does_not_fit[0-5-0-1]
19 failed, 1 passed, 180 deselected in 0.34s
```
**restore:** inverse Edit. **restored lines:**
```python
        return unreadable(rules_detail or
                          "rules max_entries_to_build %s differs from graphql "
                          "maximumEntriesToBuild %s" % (rules_limit, limit))
```
**green:** `317 passed in 1.29s`

---

## S9 — fewer free build slots than layers is slots-short

**neutralization:** `if free < layers:` → `if False:  # bite-proof` (the short queue falls through to the fit answer).

**red** (`-k "test_d2 or test_d4 or test_d5 or test_d6 or test_e22_rules_failed_and_graphql_queue_short or test_d9_cli_short"`; the 1 pass is the `test_e22_...short` test, which expects an unreadable answer either way):
```
FFFF.F                                                                   [100%]
=================================== FAILURES ===================================
E   AssertionError: assert {'ok': True, ...imit': 5, ...} == {'ok': True, ...imit': 5, ...}
      
      Omitting 9 identical items, use -vv to show
      Differing items:
      {'detail': None} != {'detail': 'the queue builds up to 5 entries at a time and holds 3 already, leaving 2 free for 3 layers'}
      {'fits': True} != {'fits': False}
      {'reason': None} != {'reason': 'slots-short'}
      Use -v to get more diff
/home/user/wt-2480/plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py:169: AssertionError: assert {'ok': True, ...imit': 5, ...} == {'ok': True, ...imit': 5, ...}
E   assert True is False
/home/user/wt-2480/plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py:192: assert True is False
E   assert True is False
/home/user/wt-2480/plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py:201: assert True is False
E   assert True is False
/home/user/wt-2480/plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py:209: assert True is False
E   assert 0 == 1
/home/user/wt-2480/plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py:725: assert 0 == 1
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_d2_classic_protection_queue_one_slot_short
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_d4_ruleset_queue_one_entry_inside_the_boundary_is_short
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_d5_limit_zero_leaves_no_slot_for_one_layer
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_d6_queued_above_the_limit_is_short_with_negative_free
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_d9_cli_short_round_trip_exits_one
5 failed, 1 passed, 194 deselected in 0.31s
```
**restore:** inverse Edit. **restored line:**
```python
    if free < layers:
```
**green:** `317 passed in 1.22s`

---

## C1 — a malformed slots call is decided by `argv[0]`, so it answers the slots shape

**neutralization:** `slots_call = bool(argv) and argv[0] == "slots"` → `slots_call = False  # bite-proof`.

**red** (`-k "test_d9_cli_missing_layers or test_d9_cli_malformed_slots_call"`; the 3 passes are `[argv8]`-`[argv10]`, whose arguments parse and reach `slots()`'s own bad-argument path). 9 failures, each the `E   AssertionError: assert {'branch', 'd... 'reads', ...} == {'branch', 'd... 'limit', ...}` block (the read key set where the slots key set was expected: extra `'source'`, `'method'`, missing `'free'`, `'limit'`, ...); the first block is shown, 8 identical blocks elided.
```
FFFFFFFFF...                                                             [100%]
=================================== FAILURES ===================================
E   AssertionError: assert {'branch', 'd... 'reads', ...} == {'branch', 'd... 'limit', ...}
      
      Extra items in the left set:
      'source'
      'method'
      Extra items in the right set:
      'free'
      'limit'...
      
      ...Full output truncated, use '-vv' to show
/home/user/wt-2480/plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py:755: AssertionError: assert {'branch', 'd... 'reads', ...} == {'branch', 'd... 'limit', ...}
(... 8 further blocks of the same text, at `:143`, elided ...)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_d9_cli_missing_layers_prints_the_slots_shaped_bad_argument
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_d9_cli_malformed_slots_call_is_the_slots_shaped_bad_argument[argv0]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_d9_cli_malformed_slots_call_is_the_slots_shaped_bad_argument[argv1]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_d9_cli_malformed_slots_call_is_the_slots_shaped_bad_argument[argv2]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_d9_cli_malformed_slots_call_is_the_slots_shaped_bad_argument[argv3]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_d9_cli_malformed_slots_call_is_the_slots_shaped_bad_argument[argv4]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_d9_cli_malformed_slots_call_is_the_slots_shaped_bad_argument[argv5]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_d9_cli_malformed_slots_call_is_the_slots_shaped_bad_argument[argv6]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_d9_cli_malformed_slots_call_is_the_slots_shaped_bad_argument[argv7]
9 failed, 3 passed, 188 deselected in 0.36s
```
**restore:** inverse Edit. **restored line:**
```python
    slots_call = bool(argv) and argv[0] == "slots"
```
**green:** `317 passed in 1.38s`

---

## C2 — the parse boundary: any other malformed call keeps the read-shaped bad-argument (existing line 539, body changed)

**neutralization:** `refusal = _slots_bad_argument(detail) if slots_call else _bad_argument(detail)` → `refusal = _slots_bad_argument(detail)  # bite-proof` (every malformed call answers the slots shape). This run added `test_merge_queue.py` to the pytest paths so the pre-existing CLI tests were also shown to bite; the order's red command names only the new file, so this one red deviates from it (the green, as everywhere, is the order's command unmodified).

**red** (`plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py plugins/superheroes/lib/tests/test_merge_queue.py -q -p no:cacheprovider --tb=line -k "test_d9_cli_malformed_call_of_any_other_shape or test_cli_malformed or test_cli_bad_argument"`; the 1 pass is `test_cli_bad_argument_value_exits_one`, a bad *value* that reaches `read()`). 14 failures, each the `E   AssertionError: assert {'branch', 'd... 'limit', ...} == {'branch', 'd... 'reads', ...}` block (slots keys where read keys were expected); the first block is shown, 13 identical blocks elided (6 at `test_merge_queue_slots_2480.py:799`, 8 at `test_merge_queue.py:447`, less the one shown).
```
FFFFFF.FFFFFFFF                                                          [100%]
=================================== FAILURES ===================================
E   AssertionError: assert {'branch', 'd... 'limit', ...} == {'branch', 'd... 'reads', ...}
      
      Extra items in the left set:
      'free'
      'layers'
      'limit'
      'fits'
      'queued'...
      
      ...Full output truncated, use '-vv' to show
/home/user/wt-2480/plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py:799: AssertionError: assert {'branch', 'd... 'limit', ...} == {'branch', 'd... 'reads', ...}
(... 13 further identical blocks elided ...)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_d9_cli_malformed_call_of_any_other_shape_keeps_the_read_shaped_bad_argument[argv0]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_d9_cli_malformed_call_of_any_other_shape_keeps_the_read_shaped_bad_argument[argv1]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_d9_cli_malformed_call_of_any_other_shape_keeps_the_read_shaped_bad_argument[argv2]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_d9_cli_malformed_call_of_any_other_shape_keeps_the_read_shaped_bad_argument[argv3]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_d9_cli_malformed_call_of_any_other_shape_keeps_the_read_shaped_bad_argument[argv4]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_d9_cli_malformed_call_of_any_other_shape_keeps_the_read_shaped_bad_argument[argv5]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_cli_malformed_is_bad_argument_json_exit_one[argv0]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_cli_malformed_is_bad_argument_json_exit_one[argv1]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_cli_malformed_is_bad_argument_json_exit_one[argv2]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_cli_malformed_is_bad_argument_json_exit_one[argv3]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_cli_malformed_is_bad_argument_json_exit_one[argv4]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_cli_malformed_is_bad_argument_json_exit_one[argv5]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_cli_malformed_is_bad_argument_json_exit_one[argv6]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_cli_malformed_is_bad_argument_json_exit_one[argv7]
14 failed, 1 passed, 302 deselected in 0.58s
```
**restore:** inverse Edit. **restored line:**
```python
        refusal = _slots_bad_argument(detail) if slots_call else _bad_argument(detail)
```
**green:** `317 passed in 1.24s`

---

## C3 — the slots CLI exits 0 only when the stack fits

**neutralization:** `return 0 if answer["fits"] else 1` → `return 0  # bite-proof`.

**red** (`-k "test_d9_cli"`): 5 failures, each `E   assert 0 == 1` with its location line (`:725`, `:735`, `:778` x3); the first pair is shown, the other four are identical in form and elided (locations in the summary list).
```
.FF..........FFF......                                                   [100%]
=================================== FAILURES ===================================
E   assert 0 == 1
/home/user/wt-2480/plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py:725: assert 0 == 1
(... 4 further pairs elided: `:735`, `:778` x3 ...)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_d9_cli_short_round_trip_exits_one
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_d9_cli_unreadable_round_trip_exits_one
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_d9_cli_malformed_slots_call_is_the_slots_shaped_bad_argument[argv8]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_d9_cli_malformed_slots_call_is_the_slots_shaped_bad_argument[argv9]
FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_d9_cli_malformed_slots_call_is_the_slots_shaped_bad_argument[argv10]
5 failed, 17 passed, 178 deselected in 0.39s
```
**restore:** inverse Edit. **restored line:**
```python
        return 0 if answer["fits"] else 1
```
**green:** `317 passed in 1.21s`

---

## Post-proof receipts

- Leftover-marker check (Grep tool, pattern `bite-proof`): `merge_queue.py` — no matches; `test_merge_queue_slots_2480.py` — no matches. Every neutralization was undone by the inverse Edit; the `# axis:` lines are at the same line numbers as registered above.
- `git status --short plugins` (after the proofs, before this record was written):
```
 M plugins/superheroes/lib/merge_queue.py
?? plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py
```
- `git diff --stat` (tracked files only; the new test file and this record are untracked):
```
 plugins/superheroes/lib/merge_queue.py | 231 ++++++++++++++++++++++++++++++++-
 1 file changed, 228 insertions(+), 3 deletions(-)
```
