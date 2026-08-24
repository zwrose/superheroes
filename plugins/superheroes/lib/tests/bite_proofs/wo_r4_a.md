# WO-R4-A bite-proofs

## BP-R4-A1 — bounded stdout cap read (`test_bounded_stdout_cap_read_never_exceeds_budget`)

**Guarded element:** `engine_dispatch.py:_bounded_stdout_cap_from_file` — axis: never reads more than byte budget from oversized files.

**Neutralization:** replaced bounded seek/read with full-file read:

```python
        data = fh.read()
        capped, truncated = _bytes_with_stdout_cap(data, max_bytes, len(data))
        return capped, truncated, len(data)
```

**Raw red:**

```
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_bounded_stdout_cap_read_never_exceeds_budget
...
>       assert max(read_sizes) <= byte_budget
E       assert 32768 <= 4137
E        +  where 32768 = max([32768])
1 failed in 0.35s
```

**Restore:** reverted `_bounded_stdout_cap_from_file` to seek/tail bounded read (inverse of neutralization).

**Restore receipt:** `git status --porcelain` for `plugins/superheroes/lib/engine_dispatch.py` empty after restore.

**Raw green:**

```
.                                                                        [100%]
1 passed in 0.28s
```

## BP-R4-A2 — like-with-like dirt comparison (`test_worktree_dirt_invariant_unchanged_tree_cross_product`)

**Superseded by BP-R4-A2b.** This proof used a mode-insensitive `fake_git` stub that returned
identical porcelain for `git status --porcelain=v1` and `git status --porcelain=v1 -uall`, so the
red run failed on a metadata/lease flip rather than on the porcelain algorithm asymmetry the
production fix guards.

**Guarded element:** `engine_dispatch.py:_worktree_dirt_verdict` — axis: unchanged tree with enumeration/lease flip does not dirt-forfeit.

**Neutralization:** replaced chokepoint with raw baseline re-capture and dict inequality:

```python
    current = _worktree_baseline(cwd_real, timeout=timeout)
    if baseline is None or current is None:
        return None
    if current != baseline:
        return True
    return False
```

**Raw red** (node `test_worktree_dirt_invariant_unchanged_tree_cross_product[none-live-True-False]`):

```
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_worktree_dirt_invariant_unchanged_tree_cross_product[none-live-True-False]
...
>       assert verdict is False, {
E       AssertionError: assert True is False
1 failed
```

**Restore:** restored `_worktree_dirt_verdict` frozen-mode/monotone-exclusion implementation.

**Restore receipt:** `git status --porcelain` for `plugins/superheroes/lib/engine_dispatch.py` empty after restore.

**Raw green:**

```
.                                                                        [100%]
1 passed in 0.34s
```

## BP-R4-A2b — porcelain mode replay (`test_worktree_dirt_invariant_unchanged_tree_cross_product`)

**Guarded element:** `engine_dispatch.py:_worktree_dirt_verdict` — axis: verdict replays baseline porcelain mode so plain vs `-uall` asymmetry on an unchanged tree does not false-positive.

**Neutralization:** re-derive mode from live enumeration instead of replaying `baseline["mode"]`:

```python
    excluded = _foreign_leased_worktree_roots(cwd_real, timeout=timeout)
    if excluded is None:
        mode = "plain"
    else:
        mode = "filtered"
    if mode not in ("plain", "filtered"):
        return None
```

(replaces `mode = baseline.get("mode")` and its guard.)

**Raw red** (node `test_worktree_dirt_invariant_unchanged_tree_cross_product[live-none-False-True]`):

```
bringing up nodes...
bringing up nodes...

.........FFFFFFFFFFF...F...FF...FFFF.F...FF..FFF                         [100%]
=================================== FAILURES ===================================
_ test_worktree_dirt_invariant_unchanged_tree_cross_product[live-none-False-True] _
...
>       assert verdict is False, {
E       AssertionError: {'baseline': {'excludedRoots': [], 'headSha': '...', 'mode': 'filtered', ...}, 'forfeit_enum_ok': False, 'forfeit_lease': 'live', 'open_enum_ok': True, ...}
E       assert True is False

plugins/superheroes/lib/tests/test_engine_dispatch.py:5613: AssertionError
...
24 failed, 24 passed in 1.81s
```

**Restore:** inverse edit — restored `mode = baseline.get("mode")` and its guard.

**Restore receipt:** `mode = baseline.get("mode")` / `if mode not in ("plain", "filtered"):` lines back in `_worktree_dirt_verdict`; `git status --porcelain` for `plugins/superheroes/lib/engine_dispatch.py` empty after restore.

**Raw green:**

```
bringing up nodes...
bringing up nodes...

................................................                         [100%]
48 passed in 1.79s
```
