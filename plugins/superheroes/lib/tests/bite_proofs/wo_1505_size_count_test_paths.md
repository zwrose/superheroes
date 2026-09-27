# #1505 bite-proof — `is_test_path` test-path conventions

Per-element bite-proof for the `test_size_count.py` detectors over `plugins/superheroes/lib/size_count.py`. For each element the production code was neutralized with one targeted edit, the whole test file ran, and then the edit was reverted by the inverse edit. The detectors were unedited throughout.

**Head proven:** `2127ae9b`, in a detached probe worktree at that commit. After each restore `git status --porcelain plugins/superheroes/lib/size_count.py` was empty.

**Provenance:** the orchestrator ran these proofs (workhorse, Claude Opus 5.5). The implementer's first record (cursor `composer-2.5`) was replaced by this one: it attributed the `count()` test's red to E2, where the runs show it comes from E3, E6, E11 and E12.

**Command** (whole file, so the red set per element is visible, not only the named node):

```
scripts/pinned-python -B -X pycache_prefix=/private/tmp/wo1505-bp-pyc -m pytest plugins/superheroes/lib/tests/test_size_count.py -q -p no:cacheprovider -rf
```

Node prefix `C` = `test_is_test_path_matches_each_convention`.

| ID | Guarded element (`size_count.py` at `2127ae9b`) | Axis | Neutralization | Red set (exact) | Decisive red line |
|---|---|---|---|---|---|
| E1 | :10 `TEST_DIR_NAMES` member `test` | `test` as a directory | `{"test", "tests",` → `{"tests",` | `C[dir-test]` — 1 failed, 43 passed | `assert False` … `is_test_path('test/integration/x.ts')` |
| E2 | :10 member `tests` | `tests` as a directory | drop `"tests", ` | `C[dir-tests]`, `test_is_test_path_matches_backslash` — 2 failed | `is_test_path('a/tests/b.py')` → False |
| E3 | :10 member `__tests__` | `__tests__` as a directory | drop `"__tests__", ` | `C[dir-__tests__]`, `test_count_skips_test_paths_and_counts_look_alikes` — 2 failed | `is_test_path('src/lib/__tests__/foo.ts')` → False |
| E4 | :10 member `spec` | `spec` as a directory | drop `"spec", ` | `C[dir-spec]` — 1 failed | `is_test_path('spec/models/user_rb.rb')` → False |
| E5 | :10 member `e2e` | `e2e` as a directory | drop `, "e2e"` | `C[dir-e2e]` — 1 failed | `is_test_path('e2e/login.ts')` → False |
| E6 | :12 glob `*.test.*` | test-named file | delete the `"*.test.*",` line | `C[glob-*.test.*]`, the `count()` test — 2 failed | `is_test_path('src/foo.test.ts')` → False |
| E7 | :13 glob `*.spec.*` | spec-named file | delete the `"*.spec.*",` line | `C[glob-*.spec.*]` — 1 failed | `is_test_path('src/foo.spec.tsx')` → False |
| E8 | :14 glob `test_*.py` | pytest-named file | delete the `"test_*.py",` line | `C[glob-test_*.py]` — 1 failed | `is_test_path('lib/test_x.py')` → False |
| E9 | :15 glob `*_test.py` | pytest-named file | delete the `"*_test.py",` line | `C[glob-*_test.py]` — 1 failed | `is_test_path('pkg/x_test.py')` → False |
| E10 | :16 glob `*_test.go` | Go test file | delete the `"*_test.go",` line | `C[glob-*_test.go]` — 1 failed | `is_test_path('pkg/x_test.go')` → False |
| E11 | :27 `parts[:-1]` | directory names never match the file name | `for component in parts[:-1]:` → `for component in parts:` | all six `test_is_test_path_directory_names_never_match_the_file_name[...]` + the `count()` test — 7 failed | `assert not True` … `is_test_path('test')` |
| E12 | :30 glob on `name` only | globs never match a directory | `fnmatchcase(name, pattern) for pattern in …` → `fnmatchcase(c, pattern) for c in parts for pattern in …` | all three `test_is_test_path_globs_never_match_a_directory[...]` + the `count()` test — 4 failed | `assert not True` … `is_test_path('src/widget.test.ts/index.ts')` |
| E13 | :47 `count()` skips test paths (the consumer) | test lines stay out of both counts | `if is_test_path(path):` → `if False:` | `test_count_skips_test_paths_and_counts_look_alikes`, `test_test_paths_are_excluded` — 2 failed | `assert 24 == 11`; `Left contains one more item: {'path': 'pkg/tests/t_test.py', 'lines': 5}` |

**Restore receipts:** after the E1–E5 restores, after E6–E10 and after E11–E13, the whole file ran `44 passed` with exit 0 and `git status --porcelain` over `size_count.py` printed nothing.

**Green:** `44 passed` (final run, exit 0).

## Continuation — fixture conventions (E14–E19)

Per-element bite-proof for the tests that pin the widened list: the fixture folders, `conftest.py`, and case-insensitive directory matching. The method is the same as above. Each element was neutralized by one targeted edit to production `size_count.py`, the whole test file ran, and the edit was reverted by the inverse edit. The detectors were unedited throughout.

**Head proven:** `fe5dce0d`, in a detached probe worktree at that commit. After each restore `git status --porcelain plugins/superheroes/lib/size_count.py` was empty.

**Provenance:** the orchestrator ran these proofs (workhorse, Claude Opus 5.5). They replace the implementer's section (cursor `composer-2.5`). That section gave the right red sets, but its restore receipt claimed an empty `git diff` over an uncommitted tree.

**Command** (whole file):

```
scripts/pinned-python -B -X pycache_prefix=<scratch> -m pytest plugins/superheroes/lib/tests/test_size_count.py -q -p no:cacheprovider -rf
```

Node prefixes: `C` = `test_is_test_path_matches_each_convention`, `L` = `test_is_test_path_rejects_look_alikes`.

| ID | Guarded element (`size_count.py` at `fe5dce0d`) | Axis | Neutralization | Red set (exact) | Decisive red line |
|---|---|---|---|---|---|
| E14 | :10 `TEST_DIR_NAMES` member `testdata` | `testdata` as a directory | drop `"testdata", ` | `C[dir-testdata]` — 1 failed, 63 passed | `assert False` … `is_test_path('go/pkg/testdata/golden.txt')` |
| E15 | :10 member `__mocks__` | `__mocks__` as a directory | drop `"__mocks__", ` | `C[dir-__mocks__]`, `C[dir-case-__Mocks__]` — 2 failed | `is_test_path('src/__mocks__/api.ts')` → False |
| E16 | :10 member `__fixtures__` | `__fixtures__` as a directory | drop `, "__fixtures__"` | `C[dir-__fixtures__]` — 1 failed | `is_test_path('src/__fixtures__/user.json')` → False |
| E17 | :17 glob `conftest.py` | pytest `conftest.py` by name | delete the `"conftest.py",` line | `C[glob-conftest.py]` — 1 failed | `is_test_path('plugins/x/conftest.py')` → False |
| E18 | :29 `component.lower()` | directory names match case-insensitively | `component.lower() in TEST_DIR_NAMES` → `component in TEST_DIR_NAMES` | `C[dir-case-Tests]`, `C[dir-case-__Mocks__]`, `C[dir-case-E2E]` — 3 failed | `is_test_path('Tests/x.py')` → False |
| E19 | :31 `fnmatchcase(name, …)` | file-name globs stay case-sensitive | `fnmatchcase(name, pattern)` → `fnmatchcase(name.lower(), pattern)` | `L[src/Foo.Test.ts]`, `L[Conftest.py]` — 2 failed | `assert not True` … `is_test_path('src/Foo.Test.ts')` |

**Restore receipts:** after each of the six inverse edits the whole file ran `64 passed` with exit 0, and `git status --porcelain` over `size_count.py` printed nothing.

**Green:** `64 passed` (final run, exit 0).
