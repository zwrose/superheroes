# #1590 WO-C bite-proof: working-tree pins, deadline-order pin, fold carries the exclusion lists

Bite-proof record for `plugins/superheroes/lib/size_count.py` (`collect`) and `plugins/superheroes/lib/engine_dispatch.py` (`_fold_size_tripwire`). Detectors: `plugins/superheroes/lib/tests/test_size_count_exclusions_1583.py` (`T`) and `plugins/superheroes/lib/tests/test_size_tripwire_fold_1582.py` (`F`).

**Status.** The implementer ran every proof (C1 to C4): each neutralization is a targeted Edit, the red is the named node run alone, the restore is the inverse Edit, and the green is the same node. Captures are the decisive lines of each run; the full assertion line is in every one.

- **Run command.** `scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest "<path>::<node>" -q`.
- **Restore receipt, every element.** The restored lines are quoted back; `git diff --stat d066da0d -- plugins/superheroes/lib/size_count.py` is empty after C3's restore is corrected (see the disclosure).
- **Disclosure, C3 restore.** The C3 restore Edit first re-inserted the deadline check but dropped the space after `read =` (`read =core_md.read_size_exclude(...)`, valid Python). The C3 green run below ran against that line. The space was put back by a second Edit and C3's node was re-run green on the clean file (second green below).
- **C1 and C2 share one neutralization cycle**, same failure mode (untracked rows bypass `count()`'s exclusions): one red run with both nodes, one green run with both nodes.

## Declared guarded-element set

C1 untracked rows reach `count()`'s exclusions (lockfile); C2 the same (glob path); C3 the deadline check before the calibration read; C4 the fold copies the two exclusion lists.

## Per-element receipts

### C1 and C2: untracked rows reach `count()`'s exclusions (exclusion)

- **Neutralization applied.** In `collect`, the line `        rows = rows + untracked` deleted; after `result = count(...)`, added `if worktree:` / `result["tripwireCount"] += sum(a + d for a, d, _ in untracked)` / `result["barCount"] += sum(a for a, _d, _p in untracked)`. Untracked lines then reach the counts without passing through `count()`.
- **Nodes.** `T::test_worktree_untracked_lockfile_excluded` (C1), `T::test_worktree_untracked_glob_path_excluded` (C2)
- **Red** (`43` is `package.json` +3 and `package-lock.json` +40; `17` is `src/a.py` +5 and `docs/plans/plan-a` +12):

```
FF                                                                       [100%]
E         Differing items:
E         {'tripwireCount': 43} != {'tripwireCount': 3}
E         {'barCount': 43} != {'barCount': 3}
E         Right contains 1 more item:
E         {'lockfilesExcluded': [{'lines': 40, 'path': 'package-lock.json'}]}
E         Differing items:
E         {'tripwireCount': 17} != {'tripwireCount': 5}
E         {'pathsExcluded': []} != {'pathsExcluded': [{'path': 'docs/plans/plan-a', 'lines': 12, 'glob': 'docs/plans/**'}]}
E         {'barCount': 17} != {'barCount': 5}
FAILED plugins/superheroes/lib/tests/test_size_count_exclusions_1583.py::test_worktree_untracked_lockfile_excluded
FAILED plugins/superheroes/lib/tests/test_size_count_exclusions_1583.py::test_worktree_untracked_glob_path_excluded
2 failed in 1.65s
```

- **Restore.** The `if worktree:` block removed and `rows = rows + untracked` put back inside `if worktree:`; quoted from `size_count.py:281`: `        rows = rows + untracked`.
- **Green.**

```
..                                                                       [100%]
2 passed in 3.08s
```

### C3: deadline check before the calibration read (refusal)

- **Neutralization applied.** The two lines `    if deadline is not None and deadline - time.monotonic() <= 0:` / `        return {"ok": False, "reason": "git-timeout"}` deleted from `collect`, ahead of the `try:` around `core_md.read_size_exclude`.
- **Node.** `T::test_calibration_read_never_past_deadline`
- **Red:**

```
E       AssertionError: assert {'ok': False,...the deadline'} == {'ok': False,...'git-timeout'}
E         Differing items:
E         {'reason': 'size-exclude-unreadable'} != {'reason': 'git-timeout'}
E         Left contains 1 more item:
E         {'detail': 'AssertionError: calibration read past the deadline'}
FAILED plugins/superheroes/lib/tests/test_size_count_exclusions_1583.py::test_calibration_read_never_past_deadline
1 failed in 0.72s
```

- **Restore.** The inverse Edit put the two lines back; quoted from `size_count.py:283-284`: `    if deadline is not None and deadline - time.monotonic() <= 0:` / `        return {"ok": False, "reason": "git-timeout"}`.
- **Green** (first, against the `read =core_md` line described above):

```
.                                                                        [100%]
1 passed in 0.89s
```

- **Green** (second, after the space was restored):

```
.                                                                        [100%]
1 passed in 0.30s
```

### C4: fold copies the lists (preservation of what the count left out)

- **Neutralization applied.** In `_fold_size_tripwire`, the four lines `if "lockfilesExcluded" in counted:` / `field["lockfilesExcluded"] = counted["lockfilesExcluded"]` / `if "pathsExcluded" in counted:` / `field["pathsExcluded"] = counted["pathsExcluded"]` deleted.
- **Node.** `F::test_fold_lists_excluded_paths`
- **Red:**

```
E         Omitting 9 identical items, use -vv to show
E         Right contains 2 more items:
E         {'lockfilesExcluded': [{'lines': 40, 'path': 'package-lock.json'}],
E          'pathsExcluded': [{'glob': 'docs/plans/**',
E                             'lines': 12,
E                             'path': 'docs/plans/plan-a'}]}
FAILED plugins/superheroes/lib/tests/test_size_tripwire_fold_1582.py::test_fold_lists_excluded_paths
1 failed in 0.60s
```

- **Restore.** The inverse Edit; quoted from `engine_dispatch.py:3159-3162`: `        if "lockfilesExcluded" in counted:` / `            field["lockfilesExcluded"] = counted["lockfilesExcluded"]` / `        if "pathsExcluded" in counted:` / `            field["pathsExcluded"] = counted["pathsExcluded"]`.
- **Green.**

```
.                                                                        [100%]
1 passed in 0.50s
```
