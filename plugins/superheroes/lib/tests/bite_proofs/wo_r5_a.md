# WO-R5-A bite-proofs — probe git-fake fixture teardown guards (BP29–BP32)

## BP29 → G1 — fixture teardown aggregator (`line 5995`)

**Guarded element:** `test_engine_dispatch.py:_probe_git_fake_route_registry` teardown — axis: **any arm that appended to `teardown_errors` causes fixture teardown to fail**.

**Neutralization:** line 5995 `raise AssertionError("\n".join(teardown_errors))` → `pass`.

**Raw red** (all three new end-to-end detectors):

```
FFF                                                                      [100%]
=================================== FAILURES ===================================
______ test_probe_git_fake_teardown_raises_on_undeclared_route_end_to_end ______
...
>       assert child.returncode != 0, msg
E       assert 0 != 0
...
__ test_probe_git_fake_teardown_raises_on_declared_route_mismatch_end_to_end ___
...
>       assert child.returncode != 0, msg
E       assert 0 != 0
...
_ test_probe_git_fake_teardown_raises_on_unregistered_helper_value_end_to_end __
...
>       assert child.returncode != 0, msg
E       assert 0 != 0
...
3 failed in 1.20s
```

**Restore:** inverse edit — restored `raise AssertionError("\n".join(teardown_errors))`.

**Restore receipt:** `git status --porcelain` showed only expected modified paths (`test_engine_dispatch.py`, `wo_l_1122.md`).

**Raw green:**

```
...                                                                      [100%]
3 passed in 1.18s
```

---

## BP30 → G2a — declared route mismatch (`line 5896`)

**Guarded element:** `_finish_probe_git_fake_route_check` declared-key branch — axis: **observed routes must equal declared table entry when test name is a key**.

**Neutralization:** line 5896 `raise AssertionError(...)` → `pass` inside the `installed != declared` branch.

**Raw red** (node `test_probe_git_fake_teardown_raises_on_declared_route_mismatch_end_to_end`):

```
F                                                                        [100%]
=================================== FAILURES ===================================
__ test_probe_git_fake_teardown_raises_on_declared_route_mismatch_end_to_end ___
...
>       assert child.returncode != 0, msg
E       assert 0 != 0
...
1 failed in 0.74s
```

**Restore:** inverse edit — restored the `raise AssertionError(...)` at line 5896.

**Restore receipt:** `git status --porcelain` showed only expected modified paths.

**Raw green:**

```
.                                                                        [100%]
1 passed in 0.73s
```

---

## BP31 → G2b — undeclared route install (`line 5902`)

**Guarded element:** `_finish_probe_git_fake_route_check` non-key branch — axis: **non-empty observed routes fail when test name is absent from `PROBE_GIT_FAKE_ROUTES`**.

**Neutralization:** line 5902 `raise AssertionError(...)` → `pass` inside the `if installed:` branch.

**Raw red** (node `test_probe_git_fake_teardown_raises_on_undeclared_route_end_to_end`):

```
F                                                                        [100%]
=================================== FAILURES ===================================
______ test_probe_git_fake_teardown_raises_on_undeclared_route_end_to_end ______
...
>       assert child.returncode != 0, msg
E       assert 0 != 0
...
1 failed in 0.81s
```

**Restore:** inverse edit — restored the `raise AssertionError(...)` at line 5902.

**Restore receipt:** `git status --porcelain` showed only expected modified paths.

**Raw green:**

```
.                                                                        [100%]
1 passed in 0.74s
```

---

## BP32 → G3 — unregistered helper value (`line 5920`)

**Guarded element:** `_finish_probe_git_fake_identity_check` — axis: **helper attribute must still be snapshot or registered wrapper at teardown**.

**Neutralization:** line 5920 `raise AssertionError("; ".join(errors))` → `pass`.

**Raw red** (node `test_probe_git_fake_teardown_raises_on_unregistered_helper_value_end_to_end`):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_probe_git_fake_teardown_raises_on_unregistered_helper_value_end_to_end __
...
>       assert child.returncode != 0, msg
E       assert 0 != 0
...
1 failed in 0.75s
```

**Restore:** inverse edit — restored `raise AssertionError("; ".join(errors))`.

**Restore receipt:** `git status --porcelain` showed only expected modified paths.

**Raw green:**

```
.                                                                        [100%]
1 passed in 1.34s
```
