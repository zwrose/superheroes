# #1505 bite-proof — `is_test_path` test-path conventions

Per-element bite-proof for the new `test_size_count.py` detectors guarding `plugins/superheroes/lib/size_count.py` (`TEST_DIR_NAMES`, `TEST_FILE_GLOBS`, `is_test_path`, `count()` skip). Each neutralization is one targeted edit to production `size_count.py`; tests were unedited throughout.

**Command (every run):**

```
scripts/pinned-python -B -X pycache_prefix=/private/tmp/wo1505-pyc -m pytest <node ids> -q -p no:cacheprovider
```

**Full raw captures:** `/private/tmp/wo1505-scratch-cmp/bite_outputs.txt` (orchestrator-local scratch from implementer dispatch).

## Summary

| ID | Guarded element | Axis | Neutralization | Proving node(s) | Red (decisive) |
|---|---|---|---|---|---|
| E1 | size_count.py:10 `TEST_DIR_NAMES` | `test` dir component | remove `"test"` from frozenset | `::test_is_test_path_matches_each_convention[dir-test]` | `assert False` on `test/integration/x.ts` |
| E2 | size_count.py:10 `TEST_DIR_NAMES` | `tests` dir component | remove `"tests"` | `[dir-tests]`, `test_is_test_path_backslash`, `test_count_skips_test_paths_and_counts_look_alikes` | dir-tests + backslash fail; **count test stayed green** (no `COUNT_ROWS` row excluded only via `tests/`) |
| E3 | size_count.py:10 | `__tests__` dir | remove `"__tests__"` | `[dir-__tests__]` | `assert False` on `src/lib/__tests__/foo.ts` |
| E4 | size_count.py:10 | `spec` dir | remove `"spec"` | `[dir-spec]` | `assert False` on `spec/models/user_rb.rb` |
| E5 | size_count.py:10 | `e2e` dir | remove `"e2e"` | `[dir-e2e]` | `assert False` on `e2e/login.ts` |
| E6 | size_count.py:11 `TEST_FILE_GLOBS` | `*.test.*` | drop first glob | `[glob-*.test.*]` | `assert False` on `src/foo.test.ts` |
| E7 | size_count.py:11 | `*.spec.*` | drop second glob | `[glob-*.spec.*]` | `assert False` on `src/foo.spec.tsx` |
| E8 | size_count.py:11 | `test_*.py` | drop third glob | `[glob-test_*.py]` | `assert False` on `lib/test_x.py` |
| E9 | size_count.py:11 | `*_test.py` | drop fourth glob | `[glob-*_test.py]` | `assert False` on `pkg/x_test.py` |
| E10 | size_count.py:11 | `*_test.go` | drop fifth glob | `[glob-*_test.go]` | `assert False` on `pkg/x_test.go` |
| E11 | size_count.py:19 | dir check excludes file name | `parts[:-1]` → `parts` | `test_is_test_path_directory_names_never_match_the_file_name` (6 cases) | `assert not True` on bare `test`, `tests`, … |
| E12 | size_count.py:22–23 | globs on file name only | glob loop over all `parts` | `test_is_test_path_globs_never_match_a_directory` (3 cases) | `assert not True` on `src/widget.test.ts/index.ts`, … |
| E13 | size_count.py:40 | `count` skips test paths | `if is_test_path(path):` → `if False:` | `test_count_skips_test_paths_and_counts_look_alikes` | `assert 24 == 11` on `tripwireCount` |

## Per-element records

### E1 — `TEST_DIR_NAMES` without `test`

- **Neutralization:** `TEST_DIR_NAMES = frozenset({"tests", "__tests__", "spec", "e2e"})`
- **Raw red:** `FAILED ...[dir-test]` — `AssertionError: assert False` for `test/integration/x.ts`
- **Restore:** restore `"test"` in frozenset literal
- **Restore receipt:** `git diff --stat plugins/superheroes/lib/size_count.py` → `1 file changed, 14 insertions(+), 2 deletions(-)` (matches pre-neutralization WO diff)
- **Raw green:** `1 passed in 0.27s`

### E2 — `TEST_DIR_NAMES` without `tests`

- **Neutralization:** `frozenset({"test", "__tests__", "spec", "e2e"})`
- **Raw red:** `2 failed, 1 passed` — `[dir-tests]` and `test_is_test_path_backslash` failed; count test **passed** (see summary)
- **Restore / receipt / green:** same stat as E1; green `3 passed in 0.31s`

### E3 — without `__tests__`

- **Neutralization:** `frozenset({"test", "tests", "spec", "e2e"})`
- **Raw red:** `FAILED ...[dir-__tests__]`
- **Raw green:** `1 passed in 0.30s`

### E4 — without `spec`

- **Neutralization:** `frozenset({"test", "tests", "__tests__", "e2e"})`
- **Raw red:** `FAILED ...[dir-spec]`
- **Raw green:** `1 passed in 0.34s`

### E5 — without `e2e`

- **Neutralization:** `frozenset({"test", "tests", "__tests__", "spec"})`
- **Raw red:** `FAILED ...[dir-e2e]`
- **Raw green:** `1 passed in 0.27s`

### E6 — without `*.test.*`

- **Neutralization:** `TEST_FILE_GLOBS = ("*.spec.*", "test_*.py", "*_test.py", "*_test.go")`
- **Raw red:** `FAILED ...[glob-*.test.*]`
- **Raw green:** `1 passed in 0.39s`

### E7 — without `*.spec.*`

- **Neutralization:** `TEST_FILE_GLOBS = ("*.test.*", "test_*.py", "*_test.py", "*_test.go")`
- **Raw red:** `FAILED ...[glob-*.spec.*]`
- **Raw green:** `1 passed in 0.29s`

### E8 — without `test_*.py`

- **Neutralization:** `TEST_FILE_GLOBS = ("*.test.*", "*.spec.*", "*_test.py", "*_test.go")`
- **Raw red:** `FAILED ...[glob-test_*.py]`
- **Raw green:** `1 passed in 0.23s`

### E9 — without `*_test.py`

- **Neutralization:** `TEST_FILE_GLOBS = ("*.test.*", "*.spec.*", "test_*.py", "*_test.go")`
- **Raw red:** `FAILED ...[glob-*_test.py]`
- **Raw green:** `1 passed in 0.35s`

### E10 — without `*_test.go`

- **Neutralization:** `TEST_FILE_GLOBS = ("*.test.*", "*.spec.*", "test_*.py", "*_test.py")`
- **Raw red:** `FAILED ...[glob-*_test.go]`
- **Raw green:** `1 passed in 0.40s`

### E11 — directory check includes file name

- **Neutralization:** `for component in parts:` (was `parts[:-1]`)
- **Raw red:** `6 failed` — all `test_is_test_path_directory_names_never_match_the_file_name` cases
- **Restore:** `for component in parts[:-1]:`
- **Raw green:** `6 passed in 0.35s`

### E12 — globs on every component

- **Neutralization:** replace file-name-only glob return with loop over all `parts`
- **Raw red:** `3 failed` — all `test_is_test_path_globs_never_match_a_directory` cases
- **Restore:** inverse block swap
- **Raw green:** `3 passed in 0.28s`

### E13 — `count()` never skips test paths

- **Neutralization:** `if False:` instead of `if is_test_path(path):`
- **Raw red:** `assert 24 == 11` on `tripwireCount`
- **Restore:** `if is_test_path(path):`
- **Raw green:** `1 passed in 0.34s`

## Combined green

After all restores, full file run: **44 passed** (`plugins/superheroes/lib/tests/test_size_count.py`). `validate_skills.py`: **✓ skills meet token-shape rules**.

## Disclosures

- **E2 vs count test:** Order text expects the count test to redden when `tests` is removed from `TEST_DIR_NAMES`; with the order's fixed `COUNT_ROWS`, skipped rows use `__tests__` or `*.test.*`, not a `tests/` directory segment, so the count test remains green. Dir-tests and backslash proofs still redden.
