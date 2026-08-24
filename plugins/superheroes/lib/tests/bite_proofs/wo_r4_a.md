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
