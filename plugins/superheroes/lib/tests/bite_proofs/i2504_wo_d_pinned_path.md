# #2504 bite-proof — WO-D: the pinned-path reader tests and the registry uniqueness assert

Detectors added: `test_reader_given_a_pinned_path_reads_the_pinned_file_not_the_live_one` and `test_reader_given_a_pinned_path_that_does_not_exist_never_falls_back_to_the_live_file` in `plugins/superheroes/lib/tests/test_advisor_issues_2504.py`; the number-uniqueness assertion in `test_registry_has_every_item_in_order` in `plugins/superheroes/lib/tests/test_project_config.py`.

Declared guarded-element set (from the order): **P1**, **P2**, **U1**. Redaction: none needed. Each capture omits only the first line the runner prints (`warning: The UV_NATIVE_TLS environment variable is deprecated ...`); everything else is verbatim. Every command ran from the worktree root as `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-2504d -m pytest <file> -q -p no:cacheprovider -k <name>`.

## P1 — the pinned path is used

Guarded element: `plugins/superheroes/lib/core_md.py:2272`, in `read_project_config_value`. Axis: a reader given a pinned path reads that file, never the live core.md.

Neutralization: `path = path or _size_exclude_core_path(cwd, root)` → `path = _size_exclude_core_path(cwd, root)` (the argument is ignored).

Detector: `-k test_reader_given_a_pinned_path_reads_the_pinned_file_not_the_live_one`

Raw red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
____ test_reader_given_a_pinned_path_reads_the_pinned_file_not_the_live_one ____

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-37/test_reader_given_a_pinned_pat0')

    def test_reader_given_a_pinned_path_reads_the_pinned_file_not_the_live_one(tmp_path):
        # axis: a reader given a pinned path reads that file, never the live core.md
        repo, store, pinned = _live_and_pinned(tmp_path)
        live = CM.read_project_config_value(repo, SLUG, root=store)
        assert live["present"] is True and live["value"] == _LIVE_VALUE  # premise: the live file says collector 7
        got = CM.read_project_config_value(repo, SLUG, root=store, path=pinned)
        assert got["reason"] is None and got["present"] is True
>       assert got["value"] == _PINNED_VALUE and got["value"]["collector"] == 9
E       AssertionError: assert ({'collector':...inboxes': [8]} == {'collector':...'inboxes': []}
E         
E         Differing items:
E         {'collector': 7} != {'collector': 9}
E         {'inboxes': [8]} != {'inboxes': []}
E         Use -v to get more diff)

/home/user/superheroes-wt-2504/plugins/superheroes/lib/tests/test_advisor_issues_2504.py:628: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_advisor_issues_2504.py::test_reader_given_a_pinned_path_reads_the_pinned_file_not_the_live_one
1 failed, 58 deselected in 0.53s
```

Restore: the inverse edit (`path = _size_exclude_core_path(cwd, root)` → `path = path or _size_exclude_core_path(cwd, root)`).

Restore receipt: `core_md.py:2272` reads `            path = path or _size_exclude_core_path(cwd, root)`; `git status --porcelain --untracked-files=no` after the last restore lists no `core_md.py` entry.

Raw green:

```
.                                                                        [100%]
1 passed, 58 deselected in 0.55s
```

## P2 — a missing pinned path never falls back to the live file

Guarded element: `plugins/superheroes/lib/core_md.py:2272` (the same line) together with the `os.path.isfile(path)` check at `core_md.py:2283`. Axis: a missing pinned path reads unreadable, never the live core.md's value.

Neutralization: the same edit as P1, `path = path or _size_exclude_core_path(cwd, root)` → `path = _size_exclude_core_path(cwd, root)`. With the argument ignored, the missing path is swapped for the live file and the `isfile` check never sees it.

Detector: `-k test_reader_given_a_pinned_path_that_does_not_exist_never_falls_back_to_the_live_file`

Raw red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_reader_given_a_pinned_path_that_does_not_exist_never_falls_back_to_the_live_file _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-39/test_reader_given_a_pinned_pat0')

    def test_reader_given_a_pinned_path_that_does_not_exist_never_falls_back_to_the_live_file(tmp_path):
        # axis: a missing pinned path reads unreadable, never the live core.md's value
        repo, store, _pinned = _live_and_pinned(tmp_path)
        missing = str(tmp_path / "pinned-copy" / "gone" / "core.md")
        assert not os.path.exists(missing)
        got = CM.read_project_config_value(repo, SLUG, root=store, path=missing)
>       assert got["reason"] == "project-config-unreadable"
E       AssertionError: assert None == 'project-config-unreadable'

/home/user/superheroes-wt-2504/plugins/superheroes/lib/tests/test_advisor_issues_2504.py:641: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_advisor_issues_2504.py::test_reader_given_a_pinned_path_that_does_not_exist_never_falls_back_to_the_live_file
1 failed, 58 deselected in 1.15s
```

Restore: the inverse edit, as for P1.

Restore receipt: `core_md.py:2272` reads `            path = path or _size_exclude_core_path(cwd, root)`; no `core_md.py` entry in `git status --porcelain --untracked-files=no`.

Raw green:

```
.                                                                        [100%]
1 passed, 58 deselected in 0.52s
```

Not separately neutralized: the `os.path.isfile(path)` line at `core_md.py:2283`. The order's P2 neutralization is the line-2272 edit; whether the test would also bite on removing only the `isfile` check was not run (for a missing path, the later `open` would raise and read as unreadable through `core-md-unreadable`, so this test would probably not tell the two apart).

## U1 — the registry uniqueness assert

Guarded element: the `numbers` / `duplicates` / `assert len(set(numbers)) == len(numbers)` lines in `test_registry_has_every_item_in_order` (`test_project_config.py:113-116`). Axis: no two registry items share a configuration-item number.

Neutralization (`plugins/superheroes/lib/project_config.py:220`, the `advisorIssues` entry): `"number": 21,` → `"number": 20,` (a duplicate of main's `duplicationSkip`).

Detector: `-k test_registry_has_every_item_in_order` in `test_project_config.py`.

Raw red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
____________________ test_registry_has_every_item_in_order _____________________

    def test_registry_has_every_item_in_order():
        assert len(PC.ITEMS) == 19
        # axis: no two registry items share a configuration-item number, so a merge that lands two items on one number fails here
        numbers = [item["number"] for item in PC.ITEMS]
        duplicates = sorted({n for n in numbers if numbers.count(n) > 1})
>       assert len(set(numbers)) == len(numbers), "registry items share a number: %s" % duplicates
E       AssertionError: registry items share a number: [20]
E       assert 18 == 19
E        +  where 18 = len({1, 2, 5, 6, 7, 8, ...})
E        +    where {1, 2, 5, 6, 7, 8, ...} = set([1, 2, 5, 6, 7, 8, ...])
E        +  and   19 = len([1, 2, 5, 6, 7, 8, ...])

/home/user/superheroes-wt-2504/plugins/superheroes/lib/tests/test_project_config.py:116: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_project_config.py::test_registry_has_every_item_in_order
1 failed, 75 deselected in 0.32s
```

Restore: the inverse edit (`"number": 20,` → `"number": 21,` on the `advisorIssues` entry).

Restore receipt: `project_config.py:220` reads `        "number": 21,`; no `project_config.py` entry in `git status --porcelain --untracked-files=no`.

Raw green:

```
.                                                                        [100%]
1 passed, 75 deselected in 0.25s
```
