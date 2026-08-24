# WO-R4-C bite-proofs

## BP-R4-C1 — legacy baseline compatibility (`test_legacy_worktree_baseline_unchanged_tree_not_dirty`)

**Guarded element:** `engine_dispatch.py:_worktree_dirt_verdict` — axis: a pre-mode baseline (no `mode` key) on an unchanged tree is graded by the legacy dynamic porcelain algorithm, not refused as unreadable.

**Neutralization:** removed the `if mode is None:` legacy replay block so missing `mode` falls through to `if mode not in ("plain", "filtered"): return None`.

**Raw red:**

```
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_legacy_worktree_baseline_unchanged_tree_not_dirty
...
>       assert ED._worktree_dirt_verdict(legacy, cwd, timeout=5) is False
E       AssertionError: assert None is False
1 failed in 0.45s
```

**Restore:** re-inserted the `if mode is None:` block calling `_legacy_worktree_porcelain_sha256`.

**Restore receipt:** legacy block restored at `_worktree_dirt_verdict`; `git status --porcelain` for `plugins/superheroes/lib/engine_dispatch.py` shows only the intended WO diff after all proofs completed.

**Raw green:**

```
.                                                                        [100%]
1 passed in 0.38s
```

## BP-R4-C2 — final-attempt stdout cap naming (`test_truncated_final_attempt_stdout_capped_forfeit`)

**Guarded element:** `engine_dispatch.py:_supervise` — axis: truncated stdout on the final attempt names `stdout-capped-by-attempt`, not a generic double-forfeit.

**Neutralization:** moved `_attempt_stdout_truncated` back inside `if latest < MAX_ATTEMPTS:` so the final attempt skips cap naming.

**Raw red:**

```
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_truncated_final_attempt_stdout_capped_forfeit
...
>       assert res["detail"].startswith("%s:" % ED.ITEM_DETAIL_STDOUT_CAPPED)
E       KeyError: 'detail'
1 failed in 3.25s
```

**Restore:** moved the truncation check above the retry gate so every attempt reaches `_stdout_capped_forfeit` first.

**Restore receipt:** truncation check precedes `if latest < MAX_ATTEMPTS:` again.

**Raw green:**

```
.                                                                        [100%]
1 passed in 3.05s
```

## BP-R4-C3 — plain baseline sibling exclusion (`test_worktree_dirt_invariant_unchanged_tree_cross_product[appeared-none-True-False]`)

**Guarded element:** `engine_dispatch.py:_worktree_dirt_verdict` + `_worktree_porcelain_snapshot` — axis: a foreign-leased sibling whose paths appear in plain porcelain mid-attempt is filtered at verdict time without switching algorithms.

**Neutralization:** reverted live-exclusion union to `mode == "filtered"` only and reverted porcelain filtering to `mode == "filtered" and excluded_roots`.

**Raw red:**

```
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_worktree_dirt_invariant_unchanged_tree_cross_product[appeared-none-True-False]
...
>       assert verdict is False, {
E       AssertionError: {'baseline': {'excludedRoots': None, 'headSha': '...', 'mode': 'plain', ...}, 'forfeit_enum_ok': True, 'forfeit_lease': 'appeared', 'open_enum_ok': False, ...}
E       assert True is False
1 failed in 0.43s
```

**Restore:** union live excluded roots for every mode; filter `excluded_roots` in `_worktree_porcelain_snapshot` regardless of mode.

**Restore receipt:** `excluded_roots |= live_excluded` unconditional; `if excluded_roots:` filter in snapshot.

**Raw green:**

```
.                                                                        [100%]
1 passed in 0.38s
```

## BP-R4-C4 — runner-owned truncation marker (`test_engine_stdout_marker_prefix_under_cap_not_truncated`)

**Guarded element:** `engine_dispatch.py:_stdout_capture_truncated` — axis: engine-forged marker prefix in body text under the byte cap is not treated as runner truncation.

**Neutralization:** reverted to substring containment:

```python
def _stdout_capture_truncated(text):
    return bool(text) and STDOUT_TRUNCATION_MARKER_PREFIX in text
```

**Raw red:**

```
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_engine_stdout_marker_prefix_under_cap_not_truncated
...
>       assert not ED._stdout_capture_truncated(forged)
E       AssertionError: assert not True
1 failed in 0.36s
```

**Restore:** restored anchored `_STDOUT_TRUNCATION_MARKER_RE.match(text)` at capture head.

**Restore receipt:** `_STDOUT_TRUNCATION_MARKER_RE` + head-anchored `_stdout_capture_truncated` body restored.

**Raw green:**

```
..                                                                       [100%]
2 passed in 0.31s
```

(test node also includes `test_genuine_truncation_detected_without_stdout_bytes` as adjacent green coverage for real truncation with `stdoutBytes` absent.)
