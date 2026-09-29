# #1505 bite-proof — the size counter's test-path list

Per-element bite-proof for `is_test_path` in `plugins/superheroes/lib/size_count.py` (the two constants `TEST_DIR_NAMES` and `TEST_FILE_GLOBS`, the directory/file-name split, and the `count()` chokepoint). For each of the 13 declared guarded elements, `size_count.py` (production, never the tests) was neutralized with one targeted edit, the named node ids ran alone and went red, the edit was reverted by the inverse edit, and the same nodes were re-run green. The detectors (`plugins/superheroes/lib/tests/test_size_count.py`) were unedited throughout.

**Provenance:** produced by the implementer (cursor `composer-2.5` order, run by a Claude implementer subagent) in the build worktree at base `981e892b` plus the uncommitted build; the orchestrator regrades. The neutralize/restore edits were applied by a scratch script doing one exact string replace (asserted to match exactly once) and its inverse (the file content was asserted byte-equal to the pre-neutralization content before the restore receipt). Nothing to redact: no secrets, tokens or URLs in these captures.

**Command** (every run, exact node ids, never `-k`):

```
scripts/pinned-python -B -X pycache_prefix=/private/tmp/wo1505-pyc -m pytest <node ids> -q -p no:cacheprovider
```

`T` = `plugins/superheroes/lib/tests/test_size_count.py`; `M` = `T::test_is_test_path_matches_each_convention`.

**Restore receipt, every element:** after each inverse edit, `git diff --stat plugins/superheroes/lib/size_count.py` was byte-identical to its pre-neutralization value (the build's uncommitted diff against base, which is nonempty because the build is uncommitted):

```
 plugins/superheroes/lib/size_count.py | 12 ++++++++++--
 1 file changed, 10 insertions(+), 2 deletions(-)
```

The restored production lines, quoted back (identical after every element):

```
TEST_DIR_NAMES = frozenset({"test", "tests", "__tests__", "spec", "e2e"})
TEST_FILE_GLOBS = ("*.test.*", "*.spec.*", "test_*.py", "*_test.py", "*_test.go")
    if any(part in TEST_DIR_NAMES for part in dirs):
    return any(fnmatch.fnmatchcase(name, glob) for glob in TEST_FILE_GLOBS)
        if is_test_path(path):
            continue
```

## Entries

### E1 — remove test from TEST_DIR_NAMES

- **Guarded element:** size_count.py:10 `TEST_DIR_NAMES` member `test`. **Axis:** a `test` directory component is test code.

- **Neutralization:** `{"test", "tests", "__tests__", "spec", "e2e"}` → `{"tests", "__tests__", "spec", "e2e"}`

- **Nodes run:** `T::test_is_test_path_matches_each_convention[dir-test]`

- **Raw red** (decisive lines of the detector's own output; exit code 1):

```
>       assert size_count.is_test_path(path)
E       AssertionError: assert False
E        +  where False = <function is_test_path at 0x1033a65c0>('test/integration/x.ts')
E        +    where <function is_test_path at 0x1033a65c0> = size_count.is_test_path
FAILED plugins/superheroes/lib/tests/test_size_count.py::test_is_test_path_matches_each_convention[dir-test]
```

- **Restore:** inverse edit (`{"tests", "__tests__", "spec", "e2e"}` → `{"test", "tests", "__tests__", "spec", "e2e"}`); restore receipt: `git diff --stat` equal to the pre-neutralization value (verified equal).

- **Raw green:** `1 passed in 0.08s` (exit code 0)

### E2 — remove tests from TEST_DIR_NAMES

- **Guarded element:** size_count.py:10 `TEST_DIR_NAMES` member `tests`. **Axis:** a `tests` directory component (also under `\` separators) is test code.

- **Neutralization:** `{"test", "tests", "__tests__", "spec", "e2e"}` → `{"test", "__tests__", "spec", "e2e"}`

- **Nodes run:** `T::test_is_test_path_matches_each_convention[dir-tests]`, `T::test_is_test_path_matches_each_convention[backslash]`, `T::test_count_skips_test_paths_and_counts_look_alikes`

- **Raw red** (decisive lines of the detector's own output; exit code 1):

```
>       assert size_count.is_test_path(path)
E       AssertionError: assert False
E        +  where False = <function is_test_path at 0x103eb2840>('a/tests/b.py')
E        +    where <function is_test_path at 0x103eb2840> = size_count.is_test_path
>       assert size_count.is_test_path(path)
E       AssertionError: assert False
E        +  where False = <function is_test_path at 0x103eb2840>('a\\tests\\b.py')
E        +    where <function is_test_path at 0x103eb2840> = size_count.is_test_path
FAILED plugins/superheroes/lib/tests/test_size_count.py::test_is_test_path_matches_each_convention[dir-tests]
FAILED plugins/superheroes/lib/tests/test_size_count.py::test_is_test_path_matches_each_convention[backslash]
```

- **Restore:** inverse edit (`{"test", "__tests__", "spec", "e2e"}` → `{"test", "tests", "__tests__", "spec", "e2e"}`); restore receipt: `git diff --stat` equal to the pre-neutralization value (verified equal).

- **Raw green:** `3 passed in 0.08s` (exit code 0)

### E3 — remove __tests__ from TEST_DIR_NAMES

- **Guarded element:** size_count.py:10 `TEST_DIR_NAMES` member `__tests__`. **Axis:** a `__tests__` directory component is test code.

- **Neutralization:** `{"test", "tests", "__tests__", "spec", "e2e"}` → `{"test", "tests", "spec", "e2e"}`

- **Nodes run:** `T::test_is_test_path_matches_each_convention[dir-__tests__]`

- **Raw red** (decisive lines of the detector's own output; exit code 1):

```
>       assert size_count.is_test_path(path)
E       AssertionError: assert False
E        +  where False = <function is_test_path at 0x103b36700>('src/lib/__tests__/foo.ts')
E        +    where <function is_test_path at 0x103b36700> = size_count.is_test_path
FAILED plugins/superheroes/lib/tests/test_size_count.py::test_is_test_path_matches_each_convention[dir-__tests__]
```

- **Restore:** inverse edit (`{"test", "tests", "spec", "e2e"}` → `{"test", "tests", "__tests__", "spec", "e2e"}`); restore receipt: `git diff --stat` equal to the pre-neutralization value (verified equal).

- **Raw green:** `1 passed in 0.07s` (exit code 0)

### E4 — remove spec from TEST_DIR_NAMES

- **Guarded element:** size_count.py:10 `TEST_DIR_NAMES` member `spec`. **Axis:** a `spec` directory component is test code.

- **Neutralization:** `{"test", "tests", "__tests__", "spec", "e2e"}` → `{"test", "tests", "__tests__", "e2e"}`

- **Nodes run:** `T::test_is_test_path_matches_each_convention[dir-spec]`

- **Raw red** (decisive lines of the detector's own output; exit code 1):

```
>       assert size_count.is_test_path(path)
E       AssertionError: assert False
E        +  where False = <function is_test_path at 0x1072be5c0>('spec/models/user_rb.rb')
E        +    where <function is_test_path at 0x1072be5c0> = size_count.is_test_path
FAILED plugins/superheroes/lib/tests/test_size_count.py::test_is_test_path_matches_each_convention[dir-spec]
```

- **Restore:** inverse edit (`{"test", "tests", "__tests__", "e2e"}` → `{"test", "tests", "__tests__", "spec", "e2e"}`); restore receipt: `git diff --stat` equal to the pre-neutralization value (verified equal).

- **Raw green:** `1 passed in 0.07s` (exit code 0)

### E5 — remove e2e from TEST_DIR_NAMES

- **Guarded element:** size_count.py:10 `TEST_DIR_NAMES` member `e2e`. **Axis:** an `e2e` directory component is test code.

- **Neutralization:** `{"test", "tests", "__tests__", "spec", "e2e"}` → `{"test", "tests", "__tests__", "spec"}`

- **Nodes run:** `T::test_is_test_path_matches_each_convention[dir-e2e]`

- **Raw red** (decisive lines of the detector's own output; exit code 1):

```
>       assert size_count.is_test_path(path)
E       AssertionError: assert False
E        +  where False = <function is_test_path at 0x10389e5c0>('e2e/login.ts')
E        +    where <function is_test_path at 0x10389e5c0> = size_count.is_test_path
FAILED plugins/superheroes/lib/tests/test_size_count.py::test_is_test_path_matches_each_convention[dir-e2e]
```

- **Restore:** inverse edit (`{"test", "tests", "__tests__", "spec"}` → `{"test", "tests", "__tests__", "spec", "e2e"}`); restore receipt: `git diff --stat` equal to the pre-neutralization value (verified equal).

- **Raw green:** `1 passed in 0.07s` (exit code 0)

### E6 — remove *.test.* from TEST_FILE_GLOBS

- **Guarded element:** size_count.py:11 `TEST_FILE_GLOBS` glob `*.test.*`. **Axis:** a file name matching `*.test.*` is test code.

- **Neutralization:** `("*.test.*", "*.spec.*", "test_*.py", "*_test.py", "*_test.go")` → `("*.spec.*", "test_*.py", "*_test.py", "*_test.go")`

- **Nodes run:** `T::test_is_test_path_matches_each_convention[glob-*.test.*]`

- **Raw red** (decisive lines of the detector's own output; exit code 1):

```
>       assert size_count.is_test_path(path)
E       AssertionError: assert False
E        +  where False = <function is_test_path at 0x10561e700>('src/foo.test.ts')
E        +    where <function is_test_path at 0x10561e700> = size_count.is_test_path
FAILED plugins/superheroes/lib/tests/test_size_count.py::test_is_test_path_matches_each_convention[glob-*.test.*]
```

- **Restore:** inverse edit (`("*.spec.*", "test_*.py", "*_test.py", "*_test.go")` → `("*.test.*", "*.spec.*", "test_*.py", "*_test.py", "*_test.go")`); restore receipt: `git diff --stat` equal to the pre-neutralization value (verified equal).

- **Raw green:** `1 passed in 0.07s` (exit code 0)

### E7 — remove *.spec.* from TEST_FILE_GLOBS

- **Guarded element:** size_count.py:11 `TEST_FILE_GLOBS` glob `*.spec.*`. **Axis:** a file name matching `*.spec.*` is test code.

- **Neutralization:** `("*.test.*", "*.spec.*", "test_*.py", "*_test.py", "*_test.go")` → `("*.test.*", "test_*.py", "*_test.py", "*_test.go")`

- **Nodes run:** `T::test_is_test_path_matches_each_convention[glob-*.spec.*]`

- **Raw red** (decisive lines of the detector's own output; exit code 1):

```
>       assert size_count.is_test_path(path)
E       AssertionError: assert False
E        +  where False = <function is_test_path at 0x10808e700>('src/foo.spec.tsx')
E        +    where <function is_test_path at 0x10808e700> = size_count.is_test_path
FAILED plugins/superheroes/lib/tests/test_size_count.py::test_is_test_path_matches_each_convention[glob-*.spec.*]
```

- **Restore:** inverse edit (`("*.test.*", "test_*.py", "*_test.py", "*_test.go")` → `("*.test.*", "*.spec.*", "test_*.py", "*_test.py", "*_test.go")`); restore receipt: `git diff --stat` equal to the pre-neutralization value (verified equal).

- **Raw green:** `1 passed in 0.07s` (exit code 0)

### E8 — remove test_*.py from TEST_FILE_GLOBS

- **Guarded element:** size_count.py:11 `TEST_FILE_GLOBS` glob `test_*.py`. **Axis:** a file name matching `test_*.py` is test code.

- **Neutralization:** `("*.test.*", "*.spec.*", "test_*.py", "*_test.py", "*_test.go")` → `("*.test.*", "*.spec.*", "*_test.py", "*_test.go")`

- **Nodes run:** `T::test_is_test_path_matches_each_convention[glob-test_*.py]`

- **Raw red** (decisive lines of the detector's own output; exit code 1):

```
>       assert size_count.is_test_path(path)
E       AssertionError: assert False
E        +  where False = <function is_test_path at 0x1056ba700>('lib/test_x.py')
E        +    where <function is_test_path at 0x1056ba700> = size_count.is_test_path
FAILED plugins/superheroes/lib/tests/test_size_count.py::test_is_test_path_matches_each_convention[glob-test_*.py]
```

- **Restore:** inverse edit (`("*.test.*", "*.spec.*", "*_test.py", "*_test.go")` → `("*.test.*", "*.spec.*", "test_*.py", "*_test.py", "*_test.go")`); restore receipt: `git diff --stat` equal to the pre-neutralization value (verified equal).

- **Raw green:** `1 passed in 0.07s` (exit code 0)

### E9 — remove *_test.py from TEST_FILE_GLOBS

- **Guarded element:** size_count.py:11 `TEST_FILE_GLOBS` glob `*_test.py`. **Axis:** a file name matching `*_test.py` is test code.

- **Neutralization:** `("*.test.*", "*.spec.*", "test_*.py", "*_test.py", "*_test.go")` → `("*.test.*", "*.spec.*", "test_*.py", "*_test.go")`

- **Nodes run:** `T::test_is_test_path_matches_each_convention[glob-*_test.py]`

- **Raw red** (decisive lines of the detector's own output; exit code 1):

```
>       assert size_count.is_test_path(path)
E       AssertionError: assert False
E        +  where False = <function is_test_path at 0x103ca2700>('pkg/x_test.py')
E        +    where <function is_test_path at 0x103ca2700> = size_count.is_test_path
FAILED plugins/superheroes/lib/tests/test_size_count.py::test_is_test_path_matches_each_convention[glob-*_test.py]
```

- **Restore:** inverse edit (`("*.test.*", "*.spec.*", "test_*.py", "*_test.go")` → `("*.test.*", "*.spec.*", "test_*.py", "*_test.py", "*_test.go")`); restore receipt: `git diff --stat` equal to the pre-neutralization value (verified equal).

- **Raw green:** `1 passed in 0.08s` (exit code 0)

### E10 — remove *_test.go from TEST_FILE_GLOBS

- **Guarded element:** size_count.py:11 `TEST_FILE_GLOBS` glob `*_test.go`. **Axis:** a file name matching `*_test.go` is test code.

- **Neutralization:** `("*.test.*", "*.spec.*", "test_*.py", "*_test.py", "*_test.go")` → `("*.test.*", "*.spec.*", "test_*.py", "*_test.py")`

- **Nodes run:** `T::test_is_test_path_matches_each_convention[glob-*_test.go]`

- **Raw red** (decisive lines of the detector's own output; exit code 1):

```
>       assert size_count.is_test_path(path)
E       AssertionError: assert False
E        +  where False = <function is_test_path at 0x1078e6700>('pkg/x_test.go')
E        +    where <function is_test_path at 0x1078e6700> = size_count.is_test_path
FAILED plugins/superheroes/lib/tests/test_size_count.py::test_is_test_path_matches_each_convention[glob-*_test.go]
```

- **Restore:** inverse edit (`("*.test.*", "*.spec.*", "test_*.py", "*_test.py")` → `("*.test.*", "*.spec.*", "test_*.py", "*_test.py", "*_test.go")`); restore receipt: `git diff --stat` equal to the pre-neutralization value (verified equal).

- **Raw green:** `1 passed in 0.08s` (exit code 0)

### E11 — directory check covers every component incl. the file name

- **Guarded element:** size_count.py:17 directory check over `dirs` (all but the last component). **Axis:** directory names are never matched against the file name.

- **Neutralization:** `for part in dirs)` → `for part in [*dirs, name])`

- **Nodes run:** `T::test_is_test_path_directory_names_never_match_the_file_name[test]`, `T::test_is_test_path_directory_names_never_match_the_file_name[tests]`, `T::test_is_test_path_directory_names_never_match_the_file_name[__tests__]`, `T::test_is_test_path_directory_names_never_match_the_file_name[spec]`, `T::test_is_test_path_directory_names_never_match_the_file_name[e2e]`, `T::test_is_test_path_directory_names_never_match_the_file_name[lib/tests]`

- **Raw red** (decisive lines of the detector's own output; exit code 1):

```
>       assert not size_count.is_test_path(path)
E       AssertionError: assert not True
E        +  where True = <function is_test_path at 0x10728b100>('test')
E        +    where <function is_test_path at 0x10728b100> = size_count.is_test_path
>       assert not size_count.is_test_path(path)
E       AssertionError: assert not True
E        +  where True = <function is_test_path at 0x10728b100>('tests')
E        +    where <function is_test_path at 0x10728b100> = size_count.is_test_path
>       assert not size_count.is_test_path(path)
E       AssertionError: assert not True
E        +  where True = <function is_test_path at 0x10728b100>('__tests__')
E        +    where <function is_test_path at 0x10728b100> = size_count.is_test_path
>       assert not size_count.is_test_path(path)
E       AssertionError: assert not True
E        +  where True = <function is_test_path at 0x10728b100>('spec')
E        +    where <function is_test_path at 0x10728b100> = size_count.is_test_path
>       assert not size_count.is_test_path(path)
E       AssertionError: assert not True
E        +  where True = <function is_test_path at 0x10728b100>('e2e')
E        +    where <function is_test_path at 0x10728b100> = size_count.is_test_path
>       assert not size_count.is_test_path(path)
E       AssertionError: assert not True
E        +  where True = <function is_test_path at 0x10728b100>('lib/tests')
E        +    where <function is_test_path at 0x10728b100> = size_count.is_test_path
FAILED plugins/superheroes/lib/tests/test_size_count.py::test_is_test_path_directory_names_never_match_the_file_name[test]
FAILED plugins/superheroes/lib/tests/test_size_count.py::test_is_test_path_directory_names_never_match_the_file_name[tests]
FAILED plugins/superheroes/lib/tests/test_size_count.py::test_is_test_path_directory_names_never_match_the_file_name[__tests__]
FAILED plugins/superheroes/lib/tests/test_size_count.py::test_is_test_path_directory_names_never_match_the_file_name[spec]
FAILED plugins/superheroes/lib/tests/test_size_count.py::test_is_test_path_directory_names_never_match_the_file_name[e2e]
FAILED plugins/superheroes/lib/tests/test_size_count.py::test_is_test_path_directory_names_never_match_the_file_name[lib/tests]
```

- **Restore:** inverse edit (`for part in [*dirs, name])` → `for part in dirs)`); restore receipt: `git diff --stat` equal to the pre-neutralization value (verified equal).

- **Raw green:** `6 passed in 0.08s` (exit code 0)

### E12 — glob check runs against every component, not the last

- **Guarded element:** size_count.py:19 glob check over `name` (the last component only). **Axis:** the globs are never matched against a directory component.

- **Neutralization:** `any(fnmatch.fnmatchcase(name, glob) for glob in TEST_FILE_GLOBS)` → `any(fnmatch.fnmatchcase(c, glob) for c in [*dirs, name] for glob in TEST_FILE_GLOBS)`

- **Nodes run:** `T::test_is_test_path_globs_never_match_a_directory[src/widget.test.ts/index.ts]`, `T::test_is_test_path_globs_never_match_a_directory[src/widget.spec.ts/index.ts]`, `T::test_is_test_path_globs_never_match_a_directory[test_dir.py/mod.rb]`

- **Raw red** (decisive lines of the detector's own output; exit code 1):

```
>       assert not size_count.is_test_path(path)
E       AssertionError: assert not True
E        +  where True = <function is_test_path at 0x1075ce980>('src/widget.test.ts/index.ts')
E        +    where <function is_test_path at 0x1075ce980> = size_count.is_test_path
>       assert not size_count.is_test_path(path)
E       AssertionError: assert not True
E        +  where True = <function is_test_path at 0x1075ce980>('src/widget.spec.ts/index.ts')
E        +    where <function is_test_path at 0x1075ce980> = size_count.is_test_path
>       assert not size_count.is_test_path(path)
E       AssertionError: assert not True
E        +  where True = <function is_test_path at 0x1075ce980>('test_dir.py/mod.rb')
E        +    where <function is_test_path at 0x1075ce980> = size_count.is_test_path
FAILED plugins/superheroes/lib/tests/test_size_count.py::test_is_test_path_globs_never_match_a_directory[src/widget.test.ts/index.ts]
FAILED plugins/superheroes/lib/tests/test_size_count.py::test_is_test_path_globs_never_match_a_directory[src/widget.spec.ts/index.ts]
FAILED plugins/superheroes/lib/tests/test_size_count.py::test_is_test_path_globs_never_match_a_directory[test_dir.py/mod.rb]
```

- **Restore:** inverse edit (`any(fnmatch.fnmatchcase(c, glob) for c in [*dirs, name] for glob in TEST_FILE_GLOBS)` → `any(fnmatch.fnmatchcase(name, glob) for glob in TEST_FILE_GLOBS)`); restore receipt: `git diff --stat` equal to the pre-neutralization value (verified equal).

- **Raw green:** `3 passed in 0.09s` (exit code 0)

### E13 — count(): `if is_test_path(path): continue` -> `if False: continue`

- **Guarded element:** size_count.py:36 `if is_test_path(path): continue` (the one consumer chokepoint). **Axis:** the counter actually drops test paths.

- **Neutralization:** `if is_test_path(path):\n            continue` → `if False:\n            continue`

- **Nodes run:** `T::test_count_skips_test_paths_and_counts_look_alikes`

- **Raw red** (decisive lines of the detector's own output; exit code 1):

```
>       assert out["tripwireCount"] == 11
E       assert 24 == 11
FAILED plugins/superheroes/lib/tests/test_size_count.py::test_count_skips_test_paths_and_counts_look_alikes
```

- **Restore:** inverse edit (`if False:\n            continue` → `if is_test_path(path):\n            continue`); restore receipt: `git diff --stat` equal to the pre-neutralization value (verified equal).

- **Raw green:** `1 passed in 0.07s` (exit code 0)

## Disclosures

- **E2 and the count test.** The order expected E2 (removing `tests`) to also redden `test_count_skips_test_paths_and_counts_look_alikes`. It does not: that test's only `tests`-directory-style row is the bare `tests` file (counted either way under the new rule) and its other test-path rows go through `__tests__` and `*.test.*`, so removing `tests` leaves the count at 11. Run alongside the E2 nodes, the count test stayed green (3 nodes ran, 2 failed: `[dir-tests]` and `[backslash]`). E2 is still proven red by `[dir-tests]` and `[backslash]`; the expectation in the order was a misread of the fixture and no assertion was changed.
- **Backslash case.** The order asked for the backslash case kept inside `test_is_test_path_matches_each_convention`; it is one extra parametrized case with id `backslash` (path `a\\tests\\b.py`), so it reddens under E2 with `[dir-tests]`.
- **E11 and E12 were each one invocation over all of their parametrized cases**, and every case went red (6 of 6 and 3 of 3).
- **E1–E10 are one-case proofs by construction:** each `dir-*` case uses a file name no glob matches, and each `glob-*` case sits in a directory no directory name matches, so exactly one element is load-bearing per case.
