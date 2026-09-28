# #1505 bite-proof — the size counter's test-path list

Per-element bite-proof record for `is_test_path` in `plugins/superheroes/lib/size_count.py` (`TEST_DIR_NAMES`, `TEST_FILE_GLOBS`, the all-but-last directory check, the last-component glob check, and the `count()` consumer). The detectors are the tests in `plugins/superheroes/lib/tests/test_size_count.py`.

**Status: `Unrunnable here`.** The implementer's shell (Bash) was disabled for the whole dispatch, so no neutralization, red run or green run was made. No receipt below is claimed; the table is the order's declared guarded-element set and the neutralization each element owes, with the red and green columns left unproven for the orchestrator to run.

**Command each run owes** (exact node ids, never `-k`; run from the worktree root):

```
scripts/pinned-python -B -X pycache_prefix=/private/tmp/wo1505-pyc -m pytest <node ids> -q -p no:cacheprovider
```

Test file `T` = `plugins/superheroes/lib/tests/test_size_count.py`. Each neutralization is one targeted edit to production `size_count.py`, reverted by the inverse edit, with `git diff --stat plugins/superheroes/lib/size_count.py` compared before and after.

| ID | Guarded element (axis) | Neutralization owed | Node(s) expected red | Raw red | Restore receipt | Raw green |
|---|---|---|---|---|---|---|
| E1 | `TEST_DIR_NAMES` member `test` (directory component) | remove `"test"` from the frozenset | `T::test_is_test_path_matches_each_convention[dir-test]` | not run | not run | not run |
| E2 | `TEST_DIR_NAMES` member `tests` | remove `"tests"` | `T::test_is_test_path_matches_each_convention[dir-tests]`, `[backslash]`; the order also expects the count test to redden, which the fixture rows may not show (`COUNT_ROWS` holds no `tests/` directory row) — record the actual result | not run | not run | not run |
| E3 | `TEST_DIR_NAMES` member `__tests__` | remove `"__tests__"` | `T::test_is_test_path_matches_each_convention[dir-__tests__]`, `T::test_count_skips_test_paths_and_counts_look_alikes` | not run | not run | not run |
| E4 | `TEST_DIR_NAMES` member `spec` | remove `"spec"` | `T::test_is_test_path_matches_each_convention[dir-spec]` | not run | not run | not run |
| E5 | `TEST_DIR_NAMES` member `e2e` | remove `"e2e"` | `T::test_is_test_path_matches_each_convention[dir-e2e]` | not run | not run | not run |
| E6 | `TEST_FILE_GLOBS` glob `*.test.*` (file name) | remove the glob | `T::test_is_test_path_matches_each_convention[glob-*.test.*]` | not run | not run | not run |
| E7 | glob `*.spec.*` | remove the glob | `T::test_is_test_path_matches_each_convention[glob-*.spec.*]` | not run | not run | not run |
| E8 | glob `test_*.py` | remove the glob | `T::test_is_test_path_matches_each_convention[glob-test_*.py]` | not run | not run | not run |
| E9 | glob `*_test.py` | remove the glob | `T::test_is_test_path_matches_each_convention[glob-*_test.py]` | not run | not run | not run |
| E10 | glob `*_test.go` | remove the glob | `T::test_is_test_path_matches_each_convention[glob-*_test.go]` | not run | not run | not run |
| E11 | directory check covers all-but-last components | `parts[:-1]` → `parts` in the directory `any(...)` | `T::test_is_test_path_directory_names_never_match_the_file_name[test]`, `[tests]`, `[__tests__]`, `[spec]`, `[e2e]`, `[lib/tests]` | not run | not run | not run |
| E12 | glob check runs on the file name only | run the glob `any(...)` over every component instead of `parts[-1]` | `T::test_is_test_path_globs_never_match_a_directory[src/widget.test.ts/index.ts]`, `[src/widget.spec.ts/index.ts]`, `[test_dir.py/mod.rb]` | not run | not run | not run |
| E13 | `count()` consumer chokepoint (`size_count.py`, `if is_test_path(path): continue`) | `if is_test_path(path):` → `if False:` | `T::test_count_skips_test_paths_and_counts_look_alikes` | not run | not run | not run |

## Disclosures

- **`Unrunnable here`, all 13 elements.** The tool result for the first shell attempt was: `Error: No such tool available: Bash. Bash is disabled for this session, in subagents as well as here.` Nothing ran; nothing is reconstructed.
- **E2's expected count-test red is unverified and doubtful.** `COUNT_ROWS` (`src/__tests__/a.ts`, `src/foo.test.ts`, `src/app.ts`, `tests`, `src/widget.test.ts/index.ts`) carries no row whose only test signal is a `tests` directory component, so on reading alone E2 reddens only the `dir-tests` and `backslash` cases. The run must show the actual result; if the count test stays green under E2, that is a fixture observation for the orchestrator, not a defect in the other cases.
- **Fixture cases are each matched by their own pattern only** by construction (directory cases use file names no glob matches; glob cases use directories outside `TEST_DIR_NAMES`). Whether each neutralization goes red is exactly what the owed runs establish.
