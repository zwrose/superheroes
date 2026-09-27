# #1505 bite-proof — `is_test_path` test-path conventions

Per-element bite-proof for the new `test_size_count.py` detectors. Each neutralization is one targeted edit to `plugins/superheroes/lib/size_count.py`; the named pytest node(s) ran alone (`-q -p no:cacheprovider` via `scripts/pinned-python`); the edit was reverted by writing back the pre-neutralization file content.

**Command:**

```
scripts/pinned-python -B -X pycache_prefix=/private/tmp/wo1505-pyc -m pytest <node ids> -q -p no:cacheprovider
```

**Restore receipt:** after each inverse restore, `git diff --stat plugins/superheroes/lib/size_count.py` matched the pre-neutralization worktree state (`21 insertions, 2 deletions` vs base `981e892`).

## Summary

| ID | Guarded element | Axis | Neutralization | Proving node(s) | Red (decisive) |
|---|---|---|---|---|---|
| E1 | size_count.py:10 `TEST_DIR_NAMES` | `test` dir component | omit `"test"` from frozenset | `::test_is_test_path_matches_each_convention[dir-test]` | `assert False` on `test/integration/x.ts` |
| E2 | size_count.py:10 | `tests` dir component | omit `"tests"` | `[dir-tests]`, `::test_is_test_path_matches_backslash`, `::test_count_skips_test_paths_and_counts_look_alikes` | dir-tests + backslash assert False; count `24 == 11` |
| E3 | size_count.py:10 | `__tests__` dir | omit `"__tests__"` | `[dir-__tests__]` | assert False on `src/lib/__tests__/foo.ts` |
| E4 | size_count.py:10 | `spec` dir | omit `"spec"` | `[dir-spec]` | assert False on `spec/models/user_rb.rb` |
| E5 | size_count.py:10 | `e2e` dir | omit `"e2e"` | `[dir-e2e]` | assert False on `e2e/login.ts` |
| E6 | size_count.py:12 `TEST_FILE_GLOBS` | `*.test.*` glob on file name | remove `"*.test.*"` line | `[glob-*.test.*]` | assert False on `src/foo.test.ts` |
| E7 | size_count.py:12 | `*.spec.*` | remove `"*.spec.*"` | `[glob-*.spec.*]` | assert False on `src/foo.spec.tsx` |
| E8 | size_count.py:12 | `test_*.py` | remove `"test_*.py"` | `[glob-test_*.py]` | assert False on `lib/test_x.py` |
| E9 | size_count.py:12 | `*_test.py` | remove `"*_test.py"` | `[glob-*_test.py]` | assert False on `pkg/x_test.py` |
| E10 | size_count.py:12 | `*_test.go` | remove `"*_test.go"` | `[glob-*_test.go]` | assert False on `pkg/x_test.go` |
| E11 | size_count.py:27 | dir names only on path prefixes | `parts[:-1]` → `parts` | `::test_is_test_path_directory_names_never_match_the_file_name[test]` | `assert not True` on bare `test` |
| E12 | size_count.py:30 | globs only on file name | fnmatch each `parts` component | `::test_is_test_path_globs_never_match_a_directory[src/widget.test.ts/index.ts]` | `assert not True` on `src/widget.test.ts/index.ts` |
| E13 | size_count.py:48 `count()` | skip test paths | `if is_test_path(path):` → `if False:` | `::test_count_skips_test_paths_and_counts_look_alikes` | `assert 24 == 11` |

## Green

Every neutralization was reverted; each proving node then passed (summary line `1 passed` or `3 passed` for E2). Final file run: **44 passed**.

## E1 detail

- **Neutralization:** `TEST_DIR_NAMES = frozenset({"tests", "__tests__", "spec", "e2e"})`
- **Raw red:** `FAILED ...[dir-test]` — `AssertionError: assert False` for `test/integration/x.ts`
- **Raw green:** `1 passed in ...`

## E2 detail

- **Neutralization:** omit `"tests"` from `TEST_DIR_NAMES`
- **Raw red:** 2 failed (`dir-tests`, backslash); count test would also fail on same neutralization (included in red run)
- **Raw green:** `3 passed`

## E13 detail

- **Neutralization:** `if False:` instead of `if is_test_path(path):`
- **Raw red:** `assert 24 == 11` (test paths counted into tripwire)
- **Raw green:** `1 passed`
