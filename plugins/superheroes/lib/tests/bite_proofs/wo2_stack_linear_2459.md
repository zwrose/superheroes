# WO-2 (#2459) bite-proof — `stack_linear.py` guards

Per-guard bite proof for `plugins/superheroes/lib/stack_linear.py`: each `# axis:` clause is neutralized in source by a targeted `Edit`, the proving tests must go red, the clause is restored by the inverse edit, and the whole file goes green again.

**Register:** 66 guards, one per `# axis:` line in the file (the order declared no set, so this is the enumeration of every independently neutralizable clause; the order gap is flagged in the return). Line numbers are those of the restored file.

**Provenance:** claude (Claude Sonnet 5.5).

**Commands.**

*Green* (after each batch's restore, the whole file; the order's named command):

```
scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-wo2 -m pytest plugins/superheroes/lib/tests/test_stack_linear.py -q -p no:cacheprovider --tb=short
```

*Red*: the same command plus `-k "<expr>"` (or the whole file) and `--tb=line` or `--tb=no` instead of `--tb=short`. `--tb` only changes how much traceback pytest prints; it filters nothing. The sandbox accepted `-X pycache_prefix`.

**How the reds were run (disclosure).** To fit the 70-command budget the guards were neutralized in **batches** of independent clauses (nine batches below), one red run per batch, then every neutralization in the batch restored by its inverse edit, then one whole-file green. Each element is attributed to the failing test ids that only it can turn red; where two clauses in one batch could both turn the same test red, they were split into separate batches or the discriminating test ids are named. Every neutralization is a one-line edit; the batch's red run is the detector's own output, and the whole-file green after the batch is shown.

**Abbreviation.** In the captures below the path prefix `plugins/superheroes/lib/tests/test_stack_linear.py::` is written `T::`. Nothing else is abbreviated; the leading uv `UV_NATIVE_TLS` warning line is omitted. Batch 4's red run was truncated by the tool in the middle of the `--tb=line` section ("[2629 characters truncated]"); its `FAILED` summary and the count line are intact and are what is quoted. Batch 2 needed two red runs (the second ran the row-shape tests); batch 9 needed a third run for the `exactly one form` clause because `return 0` masks the exit-code asserts.

**Tests added during the proof** (disclosed): `test_rest_gh_exiting_non_zero_is_unreadable_even_with_rows_on_stdout` (the first run showed D3 was not discriminated, since an exit-1 call with empty stdout is unreadable anyway); the `unresolvable ref` test was split in three so Y3/Y4/Y5 are attributed separately; `test_prove_run_raising_on_a_resolve_is_git_failed` gained a detail assertion so a downstream guard can no longer mask Y5. Green counts: 175 before the first addition, 178 after.

## Summary table

| ID | file:line | Axis | Neutralization | Proving tests (red) | Batch |
|---|---|---|---|---|---|
| W1 | 166 | unreadable layer wins over a merge commit | `if problems:` → `if problems and not any(entry["mergeCommits"] for entry in layers):` | `test_local_unreadable_layer_wins_over_a_merge_commit`, `test_rest_unreadable_layer_wins_over_a_merge_commit` | 4 |
| W2 | 172 | any merge commit makes the stack not linear | `if named:` → `if False:` | `test_rest_measured_row_shape_two_parent_row_is_not_linear`, `test_rest_three_parent_row_is_a_merge_commit_in_its_layer_only`, `test_cli_check_rest_linear_and_not_linear` | 4 |
| R1 | 186 | repo not owner/name | `if False:` | `test_rest_bad_argument_runs_nothing[kwargs0-3]` | 1 |
| R2 | 190 | prs not a non-empty list | `if False:` | `[kwargs4-7]` (`[]`, `None`, `"12"`, tuple) | 1 |
| R3 | 194 | a pr not a positive int (bool excluded) | `if False:` | `[kwargs8-12]` (0, -3, True, "5", 5.0) | 1 |
| R4 | 198 | duplicate pr | `if False:` | `[kwargs13]` | 1 |
| R5 | 202 | timeout not a positive finite number | `if False:` | `[kwargs14-18]` | 1 |
| R6 | 206 | deadline_at not None / finite number | `if False:` | `[kwargs19-21]` | 1 |
| Q1 | 218 | row not an object | `if False:` | `test_rest_unreadable_row_makes_the_layer_unreadable[row-string/row-null/row-list]` | 3 |
| Q2 | 222 | row sha not a non-empty string | `if False:` | `[sha-missing/sha-int/sha-empty]` | 3 |
| Q3 | 226 | row parents not a list | `if False:` | `[parents-missing/parents-null/parents-empty-dict/parents-empty-string]` | 3 |
| Q4 | 229 | parent not an object with a string sha | `if False:` | `[parent-string/parent-sha-int/parent-sha-missing]` | 3 |
| Q5 | 232 | REST merge decision (two or more parents) | `if False:` | `test_rest_measured_row_shape_two_parent_row_is_not_linear`, `test_rest_three_parent_row_is_a_merge_commit_in_its_layer_only` | 3 |
| G1 | 248 | gh not on PATH | `if False:` | `test_rest_gh_not_on_path_is_unreadable_and_runs_nothing` | 1 |
| D1 | 258 | no time left: no call | `if False:` | `test_rest_deadline_already_passed_makes_no_call`, `test_rest_deadline_that_passes_between_layers_stops_the_calls` | 2 |
| D2 | 265 | gh run raises OSError/TimeoutExpired | handler body → `raise` | `test_rest_run_raising_is_unreadable_not_raised[oserror/filenotfound/timeout]` | 2 |
| D3 | 268 | gh exits non-zero | `if False:` | `test_rest_gh_exiting_non_zero_is_unreadable_even_with_rows_on_stdout` | 2 |
| P1 | 281 | unreadable/non-list page → unreadable layer | `if False:` | `test_rest_unreadable_page_is_unreadable_never_linear[*]` (6 ids), `test_rest_second_page_unreadable_is_not_a_partial_list` | 2 |
| P2 | 286 | layer at the 250 cap is unreadable | `if False:` | `test_rest_249_commits_is_read_and_250_is_at_the_cap` | 2 |
| P3 | 292 | call-site: a row scan that returned None is unreadable | `if False:` | `test_rest_unreadable_row_makes_the_layer_unreadable[*]` (13 ids) | 2 |
| H1 | 313 | git run raises | handler body → `raise` | `test_local_*_oserror/timeout`, `test_prove_shallow_probe..[oserror/timeout]`, `test_prove_containment_check_raising_is_git_failed`, `test_prove_run_raising_on_a_resolve_is_git_failed`, `test_prove_merge_scan_raising_is_git_failed` | 4 |
| H2 | 329 | shallow probe exits non-zero / prints neither true nor false | `if False:` | `test_local_shallow_probe..[exit-128/exit-1-says-false/prints-maybe/prints-nothing]`, `test_prove_shallow_probe..[exit-128/exit-1-says-false/prints-maybe]` | 4 |
| H3 | 344 | rev-parse exits non-zero / prints no object id | `if False:` | `test_local_resolve_that_prints_no_object_id..[exit-1/empty]`, `test_prove_resolve_that_prints_no_object_id..[exit-1/not-a-sha/empty]`, `test_prove_tree_read_that_prints_no_object_id_is_git_failed` | 4 |
| H4 | 359 | exit 1 is the only "not an ancestor" | `if proc.returncode == 1:` → `if True:` | `test_prove_containment_check_failing_is_git_failed_not_base_not_contained`, `test_prove_layer_below_check_failing_is_git_failed_not_not_on_layer_below` | 4 |
| L1 | 371 | local: repo_root not a non-empty string | `if False:` | `test_local_bad_argument_runs_nothing[kwargs0-1]` | 5 |
| L2 | 375 | local: base not a usable ref | `if False:` | `[kwargs2-5]` | 5 |
| L3 | 379 | local: layers not a non-empty list | `if False:` | `[kwargs6-9]` | 5 |
| L4 | 383 | local: a layer not a usable ref | `if False:` | `[kwargs10-13]` | 5 |
| L5 | 402 | local: shallow probe unanswered → unreadable | `if False:` | `test_local_shallow_probe..[exit-128/exit-1-says-false/prints-maybe/prints-nothing/oserror/timeout]` | 5 |
| L6 | 405 | local: shallow repo → unreadable | `if False:` | `test_local_shallow_clone_is_unreadable`, `test_local_shallow_true_is_unreadable_and_nothing_else_runs` | 5 |
| L7 | 413 | local: a ref that does not resolve | `if False:` | `test_local_ref_that_does_not_resolve_is_unreadable_and_no_range_is_read`, `test_local_resolve_that_prints_no_object_id..`, `test_local_run_raising_on_resolve_is_unreadable` | 5 |
| L8 | 426 | local: rev-list could not run | `if False:` | `test_local_run_raising_on_rev_list_is_unreadable[oserror/timeout]` | 5 |
| L9 | 430 | local: rev-list exits non-zero | `if False:` | `test_local_rev_list_failure_is_unreadable_not_linear` | 5 |
| L10 | 437 | local merge decision (three or more tokens) | `>= 3` → `>= 99` | `test_local_no_ff_stack_is_not_linear`, `test_local_a_merge_in_only_the_top_layer_is_still_not_linear`, `test_cli_check_local_non_linear_exits_one` | 5 |
| X1 | 448 | prove: repo_root | `if False:` | `test_prove_bad_argument_runs_nothing[kwargs0-1]` | 6 |
| X2 | 452 | prove: base | `if False:` | `[kwargs2-5]` | 6 |
| X3 | 456 | prove: layers not a non-empty list | `if False:` | `[kwargs6-8]` | 6 |
| X4 | 461 | prove: a layer not a (branch, vetted, new) triple | `if False:` | `[kwargs9-11]` | 6 |
| X5 | 467 | prove: branch not a plain name | `if False:` | `[kwargs12-17]` | 6 |
| X6 | 472 | prove: duplicate branch | `if False:` | `[kwargs18]` | 6 |
| X7 | 476 | prove: vetted/new head not a usable ref | `if False:` | `[kwargs19-22]` | 6 |
| X8 | 480 | prove: remote | `if False:` | `[kwargs23-26]` | 6 |
| X9 | 484 | prove: today neither None nor a date | `if False:` | `[kwargs27]` | 6 |
| M1 | 496 | merge scan: rev-list exits non-zero | `if False:` | `test_prove_merge_scan_failing_is_git_failed_and_never_proven` | 9 |
| Y1 | 513 | prove: shallow probe unanswered → git-failed | `if False:` | `test_prove_shallow_probe..[exit-128/exit-1-says-false/prints-maybe/oserror/timeout]` | 7 |
| Y2 | 516 | prove: shallow → history-shallow | `if False:` | `test_prove_shallow_clone_is_history_shallow`, `test_prove_shallow_true_stops_before_any_other_git_call` | 7 |
| Y3 | 523 | prove: base does not resolve | `if False:` | `test_prove_unresolvable_base_is_git_failed_naming_the_ref` | 7 |
| Y4 | 530 | prove: vetted head does not resolve | `if False:` | `test_prove_unresolvable_vetted_head_is_git_failed_naming_the_ref` | 7 |
| Y5 | 535 | prove: new head does not resolve | `if False:` | `test_prove_unresolvable_new_head_is_git_failed_naming_the_ref` | 7 |
| Y6 | 542 | prove: containment unanswered → git-failed | `if False:` | `test_prove_containment_check_failing_is_git_failed_not_base_not_contained`, `test_prove_containment_check_raising_is_git_failed` | 7 |
| Y7 | 545 | prove: base-not-contained | `if False:` | `test_prove_base_not_contained_in_the_vetted_bottom` | 7 |
| Y8 | 560 | prove: new tree unreadable → git-failed | `if False:` | `test_prove_unreadable_tree_is_git_failed[new]` | 7 |
| Y9 | 565 | prove: vetted tree unreadable → git-failed | `if False:` | `test_prove_unreadable_tree_is_git_failed[vetted]` | 7 |
| Y10 | 571 | prove: tree-changed | `if False:` | `test_prove_changed_file_is_tree_changed_naming_the_layer`, `test_prove_changed_bottom_layer_stops_at_the_bottom` | 7 |
| Y11 | 579 | prove: merge scan failed → git-failed | `if False:` | `test_prove_merge_scan_failing_is_git_failed_and_never_proven`, `test_prove_merge_scan_raising_is_git_failed` | 8 |
| Y12 | 584 | prove: merge-commit-remains | `if False:` | `test_prove_merge_commit_left_in_a_new_head`, `test_prove_merge_commit_left_in_a_middle_layer`, `test_cli_prove_refusal_exits_one` | 8 |
| Y13 | 591 | prove: layer-below check unanswered → git-failed | `if False:` | `test_prove_layer_below_check_failing_is_git_failed_not_not_on_layer_below` | 8 |
| Y14 | 596 | prove: not-on-layer-below | `if False:` | `test_prove_new_head_not_on_the_layer_below`, `test_prove_bottom_that_does_not_descend_from_the_base_is_not_on_layer_below` | 8 |
| C1 | 655 | CLI parse boundary | `except (_ParseError, SystemExit):` → `except ZeroDivisionError:` | `test_cli_malformed_is_bad_argument_json_exit_one[argv0-8]` | 9 |
| C2 | 671 | CLI exactly one check form | `if False:` | `test_cli_check_needs_exactly_one_form[both/mixed]` | 9b |
| C3 | 681 | CLI exit 0 only when ok | `return 0 if result["ok"] else 1` → `return 0` | `test_cli_check_local_non_linear_exits_one`, `test_cli_check_rest_unreadable_exits_one`, `test_cli_prove_refusal_exits_one`, `test_cli_exit_code_is_zero_only_when_ok`, `test_cli_check_needs_exactly_one_form[*]` | 9 |

## Batch 1 — R1-R6, G1

Neutralized: lines 186, 190, 194, 198, 202, 206 and 248, each to `if False:  # bite-proof`.

**red** (`-k "test_rest_bad_argument_runs_nothing or test_rest_gh_not_on_path"`, `--tb=line`; the 23 `E ...` lines are omitted here, the summary is exact):
```
FFFFFFFFFFFFFFFFFFFFFFF                                                  [100%]
FAILED T::test_rest_gh_not_on_path_is_unreadable_and_runs_nothing
FAILED T::test_rest_bad_argument_runs_nothing[kwargs0]
... (the same line for kwargs1 through kwargs20, every one listed as FAILED in the run)
FAILED T::test_rest_bad_argument_runs_nothing[kwargs21]
23 failed, 155 deselected in 0.44s
```
(All 22 `kwargs` ids and the gh test failed: 23 failed. Failure modes seen: `KeyError`, `unexpected endpoint`, `TypeError: %d format`, `TypeError: '<=' not supported`, `assert (True is False)`, `'linearity-unreadable' == 'bad-argument'`.)

**restore:** the seven inverse edits (each old `if False:  # bite-proof` line + its following line → the original). **restored lines:**
```python
    if not isinstance(repo, str) or not _REPO_RE.match(repo):
    if not isinstance(prs, list) or not prs:
    if not all(_is_int(pr) and pr >= 1 for pr in prs):
    if len(set(prs)) != len(prs):
    if not _is_positive_finite(timeout):
    if deadline_at is not None and not _is_finite_number(deadline_at):
    if not shutil.which("gh"):
```
**green:**
```
........................................................................ [ 40%]
........................................................................ [ 80%]
..................................                                       [100%]
178 passed in 2.50s
```

## Batch 2 — D1, D2, D3, P1, P2, P3

Neutralized: 258 `if left <= 0:` → `if False:`; 265 the handler body (`why.append(...)`/`return None`) → `raise`; 268 `if proc.returncode != 0:` → `if False:`; 281 `if rows is None:` → `if False:`; 286 `if len(rows) >= PR_COMMITS_CAP:` → `if False:`; 292 `if merges is None:` → `if False:`.

**red 1** (`-k "test_rest_ and not bad_argument and not gh_not_on_path and not unreadable_row"`, `--tb=line`):
```
....FFFFFFFFFFFFFF.F                                                     [100%]
FAILED T::test_rest_249_commits_is_read_and_250_is_at_the_cap
FAILED T::test_rest_unreadable_layer_wins_over_a_merge_commit
FAILED T::test_rest_unreadable_page_is_unreadable_never_linear[exit-1]
FAILED T::test_rest_unreadable_page_is_unreadable_never_linear[not-json]
FAILED T::test_rest_unreadable_page_is_unreadable_never_linear[empty]
FAILED T::test_rest_unreadable_page_is_unreadable_never_linear[page-is-object]
FAILED T::test_rest_unreadable_page_is_unreadable_never_linear[page-is-string]
FAILED T::test_rest_unreadable_page_is_unreadable_never_linear[page-is-null]
FAILED T::test_rest_gh_exiting_non_zero_is_unreadable_even_with_rows_on_stdout
FAILED T::test_rest_second_page_unreadable_is_not_a_partial_list
FAILED T::test_rest_run_raising_is_unreadable_not_raised[oserror]
FAILED T::test_rest_run_raising_is_unreadable_not_raised[filenotfound]
FAILED T::test_rest_run_raising_is_unreadable_not_raised[timeout]
FAILED T::test_rest_deadline_already_passed_makes_no_call
FAILED T::test_rest_deadline_that_passes_between_layers_stops_the_calls
15 failed, 5 passed, 158 deselected in 0.39s
```
**red 2** (the call-site clause P3, `-k test_rest_unreadable_row_makes_the_layer_unreadable`, `--tb=line`): `13 failed, 165 deselected in 0.44s`, one `FAILED` for each of the 13 ids `row-string, row-null, row-list, sha-missing, sha-int, sha-empty, parents-missing, parents-null, parents-empty-dict, parents-empty-string, parent-string, parent-sha-int, parent-sha-missing`.

**restore:** inverse edits for all six (the first inverse edit for 258 was refused by the Edit tool as ambiguous while 268 was still neutralized and was re-issued after 268 was restored). **restored lines:**
```python
        if left <= 0:
            why.append("the deadline passed before the read finished")
            why.append("gh call failed: %s" % (exc or type(exc).__name__))
            return None
        if proc.returncode != 0:
        if rows is None:
        if len(rows) >= PR_COMMITS_CAP:
        if merges is None:
```
A grep for `bite-proof` over `stack_linear.py` after this restore returned no matches. **green:**
```
........................................................................ [ 40%]
........................................................................ [ 80%]
..................................                                       [100%]
178 passed in 2.35s
```

## Batch 3 — Q1-Q5

Neutralized: 218, 222, 226, 229, 232, each `if ...:` → `if False:  # bite-proof`.

**red** (`-k "test_rest_unreadable_row or test_rest_measured or test_rest_three_parent or test_cli_check_rest"`, `--tb=line`):
```
FFFFFFFFFFFFFFFF.                                                        [100%]
FAILED T::test_rest_measured_row_shape_two_parent_row_is_not_linear
FAILED T::test_rest_three_parent_row_is_a_merge_commit_in_its_layer_only
FAILED T::test_rest_unreadable_row_makes_the_layer_unreadable[row-string]
FAILED T::test_rest_unreadable_row_makes_the_layer_unreadable[row-null]
FAILED T::test_rest_unreadable_row_makes_the_layer_unreadable[row-list]
FAILED T::test_rest_unreadable_row_makes_the_layer_unreadable[sha-missing]
FAILED T::test_rest_unreadable_row_makes_the_layer_unreadable[sha-int]
FAILED T::test_rest_unreadable_row_makes_the_layer_unreadable[sha-empty]
FAILED T::test_rest_unreadable_row_makes_the_layer_unreadable[parents-missing]
FAILED T::test_rest_unreadable_row_makes_the_layer_unreadable[parents-null]
FAILED T::test_rest_unreadable_row_makes_the_layer_unreadable[parents-empty-dict]
FAILED T::test_rest_unreadable_row_makes_the_layer_unreadable[parents-empty-string]
FAILED T::test_rest_unreadable_row_makes_the_layer_unreadable[parent-string]
FAILED T::test_rest_unreadable_row_makes_the_layer_unreadable[parent-sha-int]
FAILED T::test_rest_unreadable_row_makes_the_layer_unreadable[parent-sha-missing]
FAILED T::test_cli_check_rest_linear_and_not_linear
16 failed, 1 passed, 161 deselected in 0.42s
```
(The `row-*` ids fail by `AttributeError: '<type>' object has no attribute 'get'`; the `parents-empty-dict/-string` ids are the ones a vacuous `all(...)` would accept — they bite Q3 alone.)

**restore:** inverse edits keyed by each clause's axis comment. **restored lines:**
```python
        if not isinstance(row, dict):
        if not isinstance(sha, str) or not sha:
        if not isinstance(parents, list):
        if not all(isinstance(p, dict) and isinstance(p.get("sha"), str) for p in parents):
        if len(parents) >= 2:
```
**green:** `178 passed in 2.41s` (dots: 72 + 72 + 34).

## Batch 4 — W1, W2, H1, H2, H3, H4

Neutralized: 166 `if problems:` → `if problems and not any(entry["mergeCommits"] for entry in layers):` (the targeted form: a merge commit would win over an unreadable layer, so only the "wins over" tests can bite); 172 `if named:` → `if False:`; 313 the handler return → `raise`; 329 → `if False:`; 344 → `if False:`; 359 `if proc.returncode == 1:` → `if True:`. (L10, line 437, was first included and then taken out again before the run because W2 and L10 would both turn the local merge tests red.)

**red** (whole file, `--tb=line`; the tool truncated the middle of the traceback section, the dot lines and the `FAILED` summary are intact and verbatim apart from the `T::` prefix):
```
FF....FFFFFFFF.F.FFFF..............F..F.F............................... [ 40%]
................................FFFFFFFFFFFFFFFFF.FF.................... [ 80%]
..........F.F....................F                                       [100%]
FAILED T::test_local_no_ff_stack_is_not_linear
FAILED T::test_local_a_merge_in_only_the_top_layer_is_still_not_linear
FAILED T::test_local_shallow_probe_that_cannot_answer_is_unreadable[exit-128]
FAILED T::test_local_shallow_probe_that_cannot_answer_is_unreadable[exit-1-says-false]
FAILED T::test_local_shallow_probe_that_cannot_answer_is_unreadable[prints-maybe]
FAILED T::test_local_shallow_probe_that_cannot_answer_is_unreadable[prints-nothing]
FAILED T::test_local_shallow_probe_that_cannot_answer_is_unreadable[oserror]
FAILED T::test_local_shallow_probe_that_cannot_answer_is_unreadable[timeout]
FAILED T::test_local_ref_that_does_not_resolve_is_unreadable_and_no_range_is_read
FAILED T::test_local_resolve_that_prints_no_object_id_is_unreadable[exit-1]
FAILED T::test_local_resolve_that_prints_no_object_id_is_unreadable[empty]
FAILED T::test_local_run_raising_on_rev_list_is_unreadable[oserror]
FAILED T::test_local_run_raising_on_rev_list_is_unreadable[timeout]
FAILED T::test_local_unreadable_layer_wins_over_a_merge_commit
FAILED T::test_local_run_raising_on_resolve_is_unreadable
FAILED T::test_rest_measured_row_shape_two_parent_row_is_not_linear
FAILED T::test_rest_three_parent_row_is_a_merge_commit_in_its_layer_only
FAILED T::test_rest_unreadable_layer_wins_over_a_merge_commit
FAILED T::test_prove_shallow_probe_that_cannot_answer_is_git_failed[exit-128]
FAILED T::test_prove_shallow_probe_that_cannot_answer_is_git_failed[exit-1-says-false]
FAILED T::test_prove_shallow_probe_that_cannot_answer_is_git_failed[prints-maybe]
FAILED T::test_prove_shallow_probe_that_cannot_answer_is_git_failed[oserror]
FAILED T::test_prove_shallow_probe_that_cannot_answer_is_git_failed[timeout]
FAILED T::test_prove_unresolvable_base_is_git_failed_naming_the_ref
FAILED T::test_prove_unresolvable_vetted_head_is_git_failed_naming_the_ref
FAILED T::test_prove_unresolvable_new_head_is_git_failed_naming_the_ref
FAILED T::test_prove_resolve_that_prints_no_object_id_is_git_failed[exit-1]
FAILED T::test_prove_resolve_that_prints_no_object_id_is_git_failed[not-a-sha]
FAILED T::test_prove_resolve_that_prints_no_object_id_is_git_failed[empty]
FAILED T::test_prove_run_raising_on_a_resolve_is_git_failed
FAILED T::test_prove_containment_check_failing_is_git_failed_not_base_not_contained
FAILED T::test_prove_containment_check_raising_is_git_failed
FAILED T::test_prove_unreadable_tree_is_git_failed[new]
FAILED T::test_prove_unreadable_tree_is_git_failed[vetted]
FAILED T::test_prove_tree_read_that_prints_no_object_id_is_git_failed
FAILED T::test_prove_merge_scan_raising_is_git_failed
FAILED T::test_prove_layer_below_check_failing_is_git_failed_not_not_on_layer_below
FAILED T::test_cli_check_local_non_linear_exits_one
FAILED T::test_cli_check_rest_linear_and_not_linear
FAILED T::test_cli_exit_code_is_zero_only_when_ok
40 failed, 138 passed in 2.82s
```
Attribution: W1 only turns the two `*_wins_over_a_merge_commit` tests (the plain unreadable tests stay green); W2 the REST merge tests; H1 the `oserror`/`timeout` ids and the raising tests; H2 the `exit-128`/`exit-1-says-false`/`prints-maybe` ids; H3 the `exit-1`/`empty`/`not-a-sha` resolve ids; H4 the two `git-failed-not-...` tests. **Not discriminating, disclosed:** the local `...resolve_that_prints_no_object_id_is_unreadable[not-a-sha]` id stayed green under H3 (a bogus sha makes the later `rev-list` fail and the answer is unreadable anyway); H3 is proven by the other ids.

**restore:** the six inverse edits. **restored lines:**
```python
    if problems:
    if named:
        return None, "git %s could not run: %s" % (args[0], exc or type(exc).__name__)
    if proc.returncode != 0 or out not in ("true", "false"):
    if proc.returncode != 0 or not _OBJECT_ID_RE.match(out):
    if proc.returncode == 1:
```
**green:** `178 passed in 2.28s`.

## Batch 5 — L1-L10

Neutralized: 371, 375, 379, 383 (local validators), 402, 405, 413, 426, 430 → `if False:  # bite-proof`; 437 `len(tokens) >= 3` → `len(tokens) >= 99`.

**red** (`-k "test_local or test_cli_check_local"`, `--tb=no`):
```
FF..FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF.                                    [100%]
FAILED T::test_local_no_ff_stack_is_not_linear
FAILED T::test_local_a_merge_in_only_the_top_layer_is_still_not_linear
FAILED T::test_local_shallow_clone_is_unreadable
FAILED T::test_local_shallow_true_is_unreadable_and_nothing_else_runs
FAILED T::test_local_shallow_probe_that_cannot_answer_is_unreadable[exit-128]
FAILED T::test_local_shallow_probe_that_cannot_answer_is_unreadable[exit-1-says-false]
FAILED T::test_local_shallow_probe_that_cannot_answer_is_unreadable[prints-maybe]
FAILED T::test_local_shallow_probe_that_cannot_answer_is_unreadable[prints-nothing]
FAILED T::test_local_shallow_probe_that_cannot_answer_is_unreadable[oserror]
FAILED T::test_local_shallow_probe_that_cannot_answer_is_unreadable[timeout]
FAILED T::test_local_ref_that_does_not_resolve_is_unreadable_and_no_range_is_read
FAILED T::test_local_resolve_that_prints_no_object_id_is_unreadable[exit-1]
FAILED T::test_local_resolve_that_prints_no_object_id_is_unreadable[not-a-sha]
FAILED T::test_local_resolve_that_prints_no_object_id_is_unreadable[empty]
FAILED T::test_local_rev_list_failure_is_unreadable_not_linear
FAILED T::test_local_run_raising_on_rev_list_is_unreadable[oserror]
FAILED T::test_local_run_raising_on_rev_list_is_unreadable[timeout]
FAILED T::test_local_unreadable_layer_wins_over_a_merge_commit
FAILED T::test_local_run_raising_on_resolve_is_unreadable
FAILED T::test_local_bad_argument_runs_nothing[kwargs0]
... (kwargs1 through kwargs12, each listed FAILED in the run)
FAILED T::test_local_bad_argument_runs_nothing[kwargs13]
FAILED T::test_cli_check_local_non_linear_exits_one
34 failed, 3 passed, 141 deselected in 1.14s
```
(All 14 `test_local_bad_argument_runs_nothing` ids failed.) The 3 passes are `test_local_rebased_stack_is_linear`, `test_local_ranges_run_layer_below_to_layer` and `test_cli_check_local_linear_exits_zero`: the linear cases, which no neutralized clause changes.

**restore:** the ten inverse edits. **restored lines:**
```python
    if not isinstance(repo_root, str) or not repo_root:
    if not _valid_ref(base):
    if not isinstance(layers, list) or not layers:
    if not all(_valid_ref(layer) for layer in layers):
    if shallow is None:
    if shallow:
        if sha is None:
        if proc is None:
        if proc.returncode != 0:
        entry["mergeCommits"] = [tokens[0] for tokens in lines if len(tokens) >= 3]
```
**green:** `178 passed in 2.48s`.

## Batch 6 — X1-X9

Neutralized: the nine `prove` argument clauses (448, 452, 456, 461, 467 (two-line condition), 472, 476, 480, 484) → `if False:  # bite-proof`.

**red** (`-k test_prove_bad_argument`, `--tb=no`): `FFFFFFFFFFFFFFFFFFFFFFFFFFFF`, then `FAILED T::test_prove_bad_argument_runs_nothing[kwargs0]` through `[kwargs27]` (28 lines, none missing), and
```
28 failed, 150 deselected in 0.47s
```
Each id is caught by exactly one clause in the unedited code (checked for each by hand: ids 0-1 X1, 2-5 X2, 6-8 X3, 9-11 X4, 12-17 X5, 18 X6, 19-22 X7, 23-26 X8, 27 X9), so the 28 reds attribute as in the table.

**restore:** nine inverse edits. **restored lines:**
```python
    if not isinstance(repo_root, str) or not repo_root:
    if not _valid_ref(base):
    if not isinstance(layers, list) or not layers:
    if not all(isinstance(layer, (tuple, list)) and len(layer) == 3 for layer in layers):
    if not all(isinstance(b, str) and b != "" and not b.startswith("-")
               and _BRANCH_BAD_RE.search(b) is None for b in branches):
    if len(set(branches)) != len(branches):
    if not all(_valid_ref(layer[1]) and _valid_ref(layer[2]) for layer in layers):
    if not _valid_ref(remote):
    if today is not None and not isinstance(today, datetime.date):
```
**green:** `178 passed in 2.26s`.

## Batch 7 — Y1-Y10

Neutralized: 513, 516, 523, 530, 535, 542, 545, 560, 565, 571 → `if False:  # bite-proof`.

**red** (`-k "(test_prove or test_cli_prove or test_cli_exit) and not bad_argument"`, `--tb=no`):
```
....FF....FFFFFFFFFFFFFF.FFFFF.......F                                   [100%]
FAILED T::test_prove_changed_file_is_tree_changed_naming_the_layer
FAILED T::test_prove_changed_bottom_layer_stops_at_the_bottom
FAILED T::test_prove_base_not_contained_in_the_vetted_bottom
FAILED T::test_prove_shallow_clone_is_history_shallow
FAILED T::test_prove_shallow_true_stops_before_any_other_git_call
FAILED T::test_prove_shallow_probe_that_cannot_answer_is_git_failed[exit-128]
FAILED T::test_prove_shallow_probe_that_cannot_answer_is_git_failed[exit-1-says-false]
FAILED T::test_prove_shallow_probe_that_cannot_answer_is_git_failed[prints-maybe]
FAILED T::test_prove_shallow_probe_that_cannot_answer_is_git_failed[oserror]
FAILED T::test_prove_shallow_probe_that_cannot_answer_is_git_failed[timeout]
FAILED T::test_prove_unresolvable_base_is_git_failed_naming_the_ref
FAILED T::test_prove_unresolvable_vetted_head_is_git_failed_naming_the_ref
FAILED T::test_prove_unresolvable_new_head_is_git_failed_naming_the_ref
FAILED T::test_prove_resolve_that_prints_no_object_id_is_git_failed[exit-1]
FAILED T::test_prove_resolve_that_prints_no_object_id_is_git_failed[not-a-sha]
FAILED T::test_prove_resolve_that_prints_no_object_id_is_git_failed[empty]
FAILED T::test_prove_containment_check_failing_is_git_failed_not_base_not_contained
FAILED T::test_prove_containment_check_raising_is_git_failed
FAILED T::test_prove_unreadable_tree_is_git_failed[new]
FAILED T::test_prove_unreadable_tree_is_git_failed[vetted]
FAILED T::test_prove_tree_read_that_prints_no_object_id_is_git_failed
FAILED T::test_cli_exit_code_is_zero_only_when_ok
22 failed, 16 passed, 140 deselected in 2.20s
```
**Not discriminating, disclosed (fixed after this run):** `test_prove_run_raising_on_a_resolve_is_git_failed` stayed green because, with Y5 neutralized, the downstream tree and merge-scan clauses (still intact) also answer git-failed. The test now also asserts the detail names `layer l2 new head` and the OSError text; Y5 is proven by `test_prove_unresolvable_new_head_..._naming_the_ref` (detail must say `new head`).

**restore:** ten inverse edits. **restored lines:**
```python
    if shallow is None:
    if shallow:
    if base_sha is None:
        if vetted_sha is None:
        if new_sha is None:
    if contained is None:
    if not contained:
        if new_tree is None:
        if vetted_tree is None:
        if not entry["treeEqual"]:
```
**green:** `178 passed in 2.34s` (after the one detail assertion was added to the raising test).

## Batch 8 — Y11-Y14

Neutralized: 579 `if merges is None:`, 584 `if merges:`, 591 `if below is None:`, 596 `if not below:` → `if False:  # bite-proof`.

**red** (`-k "(test_prove or test_cli_prove) and not bad_argument"`, `--tb=no`):
```
......FFFF....................FFF...F                                    [100%]
FAILED T::test_prove_merge_commit_left_in_a_new_head
FAILED T::test_prove_merge_commit_left_in_a_middle_layer
FAILED T::test_prove_new_head_not_on_the_layer_below
FAILED T::test_prove_bottom_that_does_not_descend_from_the_base_is_not_on_layer_below
FAILED T::test_prove_merge_scan_failing_is_git_failed_and_never_proven
FAILED T::test_prove_merge_scan_raising_is_git_failed
FAILED T::test_prove_layer_below_check_failing_is_git_failed_not_not_on_layer_below
FAILED T::test_cli_prove_refusal_exits_one
8 failed, 29 passed, 141 deselected in 1.74s
```
**restore / restored lines:**
```python
        if merges is None:
        if merges:
        if below is None:
        if not below:
```
**green:** `178 passed in 2.45s`.

## Batch 9 — M1, C1, C2, C3

Neutralized: 496 `if proc.returncode != 0:` (in `_merges_between`) → `if False:`; 655 `except (_ParseError, SystemExit):` → `except ZeroDivisionError:`; 671 `if rest_form == local_form:` → `if False:`; 681 `return 0 if result["ok"] else 1` → `return 0`.

**red** (`-k "test_prove_merge_scan or test_cli"`, `--tb=no`):
```
F.F.FFFFFFFFFF.FFFFFFFFFFF                                               [100%]
FAILED T::test_prove_merge_scan_failing_is_git_failed_and_never_proven
FAILED T::test_cli_check_local_non_linear_exits_one
FAILED T::test_cli_check_rest_linear_and_not_linear
FAILED T::test_cli_check_rest_unreadable_exits_one
FAILED T::test_cli_check_needs_exactly_one_form[neither]
FAILED T::test_cli_check_needs_exactly_one_form[both]
FAILED T::test_cli_check_needs_exactly_one_form[mixed]
FAILED T::test_cli_check_needs_exactly_one_form[root-only]
FAILED T::test_cli_check_needs_exactly_one_form[repo-only]
FAILED T::test_cli_check_needs_exactly_one_form[pr-only]
FAILED T::test_cli_check_needs_exactly_one_form[pr-zero]
FAILED T::test_cli_check_needs_exactly_one_form[no-layer]
FAILED T::test_cli_prove_refusal_exits_one
FAILED T::test_cli_malformed_is_bad_argument_json_exit_one[argv0]
FAILED T::test_cli_malformed_is_bad_argument_json_exit_one[argv1]
FAILED T::test_cli_malformed_is_bad_argument_json_exit_one[argv2]
FAILED T::test_cli_malformed_is_bad_argument_json_exit_one[argv3]
FAILED T::test_cli_malformed_is_bad_argument_json_exit_one[argv4]
FAILED T::test_cli_malformed_is_bad_argument_json_exit_one[argv5]
FAILED T::test_cli_malformed_is_bad_argument_json_exit_one[argv6]
FAILED T::test_cli_malformed_is_bad_argument_json_exit_one[argv7]
FAILED T::test_cli_malformed_is_bad_argument_json_exit_one[argv8]
FAILED T::test_cli_exit_code_is_zero_only_when_ok
23 failed, 3 passed, 152 deselected in 0.87s
```
Attribution: M1 turns only `test_prove_merge_scan_failing...` (the *raising* merge-scan test stays green, as it should: that path is Y11). C1 turns the nine `malformed` ids (C3 cannot reach the parse-failure return). C3 turns every test that asserts exit code 1 for a refusal. C2 is masked here by C3 (every `exactly_one_form` id asserts exit code 1), so C2 got its own run:

**red, C2 alone** (671 neutralized, 496/655/681 restored first; `-k test_cli`, `--tb=no`):
```
.....FF.................                                                 [100%]
FAILED T::test_cli_check_needs_exactly_one_form[both]
FAILED T::test_cli_check_needs_exactly_one_form[mixed]
2 failed, 22 passed, 154 deselected in 0.89s
```
(`neither`, `root-only`, `repo-only`, `pr-only`, `pr-zero`, `no-layer` stay green under C2 alone: the check functions' own argument checks answer bad-argument for them. `both` and `mixed` are the ids only C2 can turn red.)

**restore / restored lines:**
```python
    if proc.returncode != 0:
        return None, "git rev-list --merges %s..%s failed: %s" % (
    except (_ParseError, SystemExit):
        if rest_form == local_form:
    return 0 if result["ok"] else 1
```
**final green** (the order's named command, whole file):
```
........................................................................ [ 40%]
........................................................................ [ 80%]
..................................                                       [100%]
178 passed in 2.53s
```

## Elements with no `# axis:` clause of their own (listed as unproven by individual neutralization)

These helpers are exercised through the clauses above, but none was neutralized on its own: `_valid_ref` (the leading-dash and whitespace/control parts are exercised by the ids `-x`, `a b`, `b c`), `_BRANCH_BAD_RE` (the `:`, `~`, whitespace parts by ids `a:b`, `a~1`, `a b`; the `^ ? * [ \` parts have no id), `_is_int`/`_is_positive_finite`/`_is_finite_number` (bool/nan/inf ids exist for `timeout` and `deadline_at`), `_clip`, the `datetime.datetime` to date conversion in `prove` (covered by `test_prove_today_defaults_to_the_utc_date_and_takes_a_datetime`), and `_OBJECT_ID_RE` accepting 64-hex ids (sha256 repositories; no test).

## Restore receipt

A grep for `bite-proof` over `plugins/superheroes/lib/stack_linear.py` after batch 2's restore and again after the last restore returned no matches, so no neutralization is left in the source. Every restore was the inverse edit through the Edit tool; no `git checkout`, `git restore`, `git reset` or `git stash` was used. The final `git status --porcelain` shows the dispatch touched only `plugins/superheroes/lib/stack_linear.py` and `plugins/superheroes/lib/tests/test_stack_linear.py` (and this file); the other untracked entries (`.bash_profile`, `.claude/`, `.gitconfig`, ...) were already in the worktree before this dispatch.
