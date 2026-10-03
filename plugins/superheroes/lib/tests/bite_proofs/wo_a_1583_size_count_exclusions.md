# #1583 WO-A bite-proof: the size count's lockfile and `sizeExclude` exclusions

Bite-proof record for `plugins/superheroes/lib/size_count.py` (`LOCKFILE_NAMES`, `is_lockfile`, `count`, `collect`), detectors in `plugins/superheroes/lib/tests/test_size_count_exclusions_1583.py` (`T`).

**Status.** The implementer ran every proof (A1 to A7): each neutralization is a targeted Edit in `size_count.py`, the red is the single named node run alone, the restore is the inverse Edit, and the green is the same node. Captures below are the tail of each run (`| tail -30`), so a long traceback's head is elided; the decisive assertion line is in every one.

- **Run command.** `scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest "<T>::<node>" -q`.
- **Restore receipt, every element.** The restored lines are quoted back; the final `git diff plugins/superheroes/lib/size_count.py` shows none of the neutralizations present.
- **Two wasted runs, disclosed.** After A1 and after A5 the first restore Edit was refused (the old string matched twice), and the run chained after it executed against the still-neutralized file, so it printed a second red, not a green. Each was restored with a longer, unique Edit and re-run green. Those two extra red runs are the only reason the budget shows 18 and not 16 before the closing runs.

## Declared guarded-element set

A1 lockfile branch in `count()`; A2 the lockfile literal set; A3 the glob match; A4 the absent-key identity; A5 the collect-to-count plumbing; A6 the collect malformed refusal; A7 the reader-exception guard.

## Per-element receipts

### A1: lockfile branch in `count()` (exclusion)

- **Neutralization applied.** `is_lockfile` body `return path.replace("\\", "/").split("/")[-1] in LOCKFILE_NAMES` replaced with `return False`.
- **Node.** `T::test_lockfile_left_out_of_both_counts`
- **Red** (the failing assertion; `tripwireCount` 43 is `package.json` +3 and `package-lock.json` +40):

```
>       assert out["tripwireCount"] == 3
E       assert 43 == 3
FAILED plugins/superheroes/lib/tests/test_size_count_exclusions_1583.py::test_lockfile_left_out_of_both_counts
1 failed in 2.22s
```

- **Restore.** The inverse Edit put back `return path.replace("\\", "/").split("/")[-1] in LOCKFILE_NAMES`; quoted from `size_count.py:50`: `    return path.replace("\\", "/").split("/")[-1] in LOCKFILE_NAMES`.
- **Green.**

```
.                                                                        [100%]
1 passed in 0.75s
```

### A2: the lockfile literal set (external contract)

- **Neutralization applied.** The `"go.sum",` line deleted from `LOCKFILE_NAMES`.
- **Node.** `T::test_literal_lockfile_set`
- **Red:**

```
E       AssertionError: assert frozenset({'C...p.json', ...}) == frozenset({'C...go.sum', ...})
E         
E         Extra items in the right set:
E         'go.sum'
FAILED plugins/superheroes/lib/tests/test_size_count_exclusions_1583.py::test_literal_lockfile_set
1 failed in 0.26s
```

- **Restore.** The inverse Edit put the `"go.sum",` line back; quoted: `    "go.sum",` then `})` at `size_count.py:44-45` (as of the final file).
- **Green.**

```
.                                                                        [100%]
1 passed in 0.26s
```

### A3: glob match (exclusion)

- **Neutralization applied.** In the `next(...)` generator, the call `fnmatch.fnmatchcase(normalized, g)` replaced with `False`.
- **Node.** `T::test_glob_left_out_of_both_counts`
- **Red** (`7` is `docs/a/b.md` +5 and `src/x.py` +2):

```
>       assert out["tripwireCount"] == 2
E       assert 7 == 2
FAILED plugins/superheroes/lib/tests/test_size_count_exclusions_1583.py::test_glob_left_out_of_both_counts
1 failed in 1.88s
```

- **Restore.** The inverse Edit; quoted from `size_count.py:86`: `            glob = next((g for g in size_exclude if fnmatch.fnmatchcase(normalized, g)), None)`.
- **Green.**

```
.                                                                        [100%]
1 passed in 2.20s
```

### A4: absent-key identity (preservation)

- **Neutralization applied.** `if size_exclude is not None:` guarding `out["pathsExcluded"]` replaced with `if True:`.
- **Node.** `T::test_absent_key_identity`
- **Red:**

```
E       assert '{"barCount":...ireCount": 2}' == '{"barCount":...ireCount": 2}'
E         - ": true, "tripwireCount": 2}
E         + ": true, "pathsExcluded": [], "tripwireCount": 2}
FAILED plugins/superheroes/lib/tests/test_size_count_exclusions_1583.py::test_absent_key_identity
1 failed in 0.75s
```

- **Restore.** The inverse Edit; quoted from `size_count.py:110-111`: `    if size_exclude is not None:` / `        out["pathsExcluded"] = paths_excluded`.
- **Green.**

```
.                                                                        [100%]
1 passed in 0.84s
```

### A5: collect-to-count plumbing (exclusion)

- **Neutralization applied.** `size_exclude=read["globs"]` on the `count(...)` call in `collect` replaced with `size_exclude=None`.
- **Node.** `T::test_glob_left_out_of_both_counts`
- **Red:**

```
>       assert out["tripwireCount"] == 2
E       assert 7 == 2
FAILED plugins/superheroes/lib/tests/test_size_count_exclusions_1583.py::test_glob_left_out_of_both_counts
1 failed in 2.19s
```

- **Restore.** The inverse Edit; quoted from `size_count.py:241`: `    result = count(rows, deleted_paths, bar_exclude=bar_exclude, size_exclude=read["globs"])`.
- **Green.**

```
.                                                                        [100%]
1 passed in 1.86s
```

### A6: collect malformed refusal (refusal)

- **Neutralization applied.** The malformed branch's `return {"ok": False, "reason": "size-exclude-malformed", "malformed": read["malformed"]}` replaced with `read = dict(read, reason=None)`, so a malformed calibration falls through to counting with no globs.
- **Node.** `T::test_collect_malformed_refuses_with_items`
- **Red:**

```
E       AssertionError: assert {'tripwireCou...ary': [], ...} == {'ok': False,... leading /'}]}
E         Differing items:
E         {'ok': True} != {'ok': False}
FAILED plugins/superheroes/lib/tests/test_size_count_exclusions_1583.py::test_collect_malformed_refuses_with_items
1 failed in 1.05s
```

- **Restore.** The inverse Edit; quoted from `size_count.py:183-184`: `    if read["reason"] == "size-exclude-malformed":` / `        return {"ok": False, "reason": "size-exclude-malformed", "malformed": read["malformed"]}`.
- **Green.**

```
.                                                                        [100%]
1 passed in 0.92s
```

### A7: reader-exception guard (refusal)

- **Neutralization applied.** The `try: ... except Exception as exc: return {...}` around `core_md.read_size_exclude(repo_root, root)` removed, leaving the bare call.
- **Node.** `T::test_edge_reader_raises_is_unreadable`
- **Red** (the test's monkeypatched reader raises; the error escapes `collect`):

```
/.../plugins/superheroes/lib/size_count.py:178: in collect
    read = core_md.read_size_exclude(repo_root, root)
...
>       raise RuntimeError("boom")
E       RuntimeError: boom
FAILED plugins/superheroes/lib/tests/test_size_count_exclusions_1583.py::test_edge_reader_raises_is_unreadable
1 failed in 0.21s
```

- **Restore.** The inverse Edit put the `try`/`except` block back; quoted from `size_count.py:178-182`: `    try:` / `        read = core_md.read_size_exclude(repo_root, root)` / `    except Exception as exc:` / `        return {"ok": False, "reason": "size-exclude-unreadable",` / `                "detail": "%s: %s" % (type(exc).__name__, exc)}`.
- **Green.**

```
.                                                                        [100%]
1 passed in 0.22s
```
