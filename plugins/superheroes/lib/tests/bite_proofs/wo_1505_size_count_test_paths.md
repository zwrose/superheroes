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

**Head:** `f20ea569` plus uncommitted order work (WO-1505-B, cursor `composer-2.5` order dispatched by workhorse; carried out in a session with no shell).

**Unrunnable here.** The implementer session had no shell tool (`Bash` rejected as "No such tool available"), so no pytest run was made: no red, no green, no restore receipt exists for E14–E19. The table below records only the declared guarded elements and the neutralizations the order names, each **not run**. The orchestrator's own re-run of the bite-proof supplies the red and green halves.

**Command** (not run; whole file each time):

```
scripts/pinned-python -B -X pycache_prefix=/private/tmp/wo1505b-pyc -m pytest plugins/superheroes/lib/tests/test_size_count.py -q -p no:cacheprovider -rf
```

Node prefix `C` = `test_is_test_path_matches_each_convention`; `L` = `test_is_test_path_rejects_look_alikes`.

| ID | Guarded element (`size_count.py`) | Axis | Neutralization (not run) | Expected red set | Red / restore / green |
|---|---|---|---|---|---|
| E14 | `TEST_DIR_NAMES` member `testdata` | `testdata` as a directory | drop `"testdata", ` | `C[dir-testdata]` | not run |
| E15 | member `__mocks__` | `__mocks__` as a directory | drop `"__mocks__", ` | `C[dir-__mocks__]`, `C[dir-case-__Mocks__]` | not run |
| E16 | member `__fixtures__` | `__fixtures__` as a directory | drop `, "__fixtures__"` | `C[dir-__fixtures__]` | not run |
| E17 | glob `conftest.py` | pytest conftest file | delete the `"conftest.py",` line | `C[glob-conftest.py]` | not run |
| E18 | `component.lower()` | directory names match case-insensitively | `component.lower() in TEST_DIR_NAMES` → `component in TEST_DIR_NAMES` | `C[dir-case-Tests]`, `C[dir-case-__Mocks__]`, `C[dir-case-E2E]` | not run |
| E19 | `fnmatchcase(name, pattern)` | file-name globs stay case-sensitive | `fnmatchcase(name, pattern)` → `fnmatchcase(name.lower(), pattern)` | `L[src/Foo.Test.ts]`, `L[Conftest.py]` | not run |

**Restore receipts:** none; no neutralization was applied, so `size_count.py` was never edited beyond the order's implementation.
