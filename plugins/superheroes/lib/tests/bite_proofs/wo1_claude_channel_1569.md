# #1569 WO-1 bite-proof: the claude write channel allow, managed-policy presence, and the `.cc-writes` sweep

Detectors live in `plugins/superheroes/lib/tests/test_claude_write_channel_1569.py` (`T`). Guarded code: `claude_write_sandbox_settings` in `plugins/superheroes/lib/engine_adapter.py` (`A`), and `_managed_policy_location_present`, `_sweep_claude_dir`, `_sweep_cc_writes`, `_fold_cc_writes_sweep`, `_fold_run` in `plugins/superheroes/lib/engine_dispatch.py` (`D`).

Every neutralization was a targeted Edit by the implementer, restored by the inverse Edit (quoted below). Each red is the single test node run alone, unedited, with `scripts/pinned-python -m pytest <node> -q -p no:cacheprovider`. Each green is the same command after the restore. Captures are verbatim; the only elision is the traceback body of the red, where it repeats the test source (marked `[...]`). Nothing in the captures needed redaction.

Declared guarded-element set: P1 to P11, one entry each, no equivalence classes.

## P1: allow gate (axis: the allow is emitted only for the literal `managedPolicyPresent is False`)

- Neutralization in `A`: `if sandbox.get("managedPolicyPresent") is False:` became `if True:`.
- Node: `T::test_settings_no_allow_unless_literal_false[true]`
- Red:
```
F                                                                        [100%]
[...]
E       AssertionError: assert 'allow' not in {'allow': ['Bash'], 'deny': ['WebFetch', 'WebSearch']}
FAILED plugins/superheroes/lib/tests/test_claude_write_channel_1569.py::test_settings_no_allow_unless_literal_false[true]
1 failed in 0.45s
```
- Restore: inverse Edit, `if True:` back to `if sandbox.get("managedPolicyPresent") is False:`.
- Restore receipt, lines quoted back from `A`: `    if sandbox.get("managedPolicyPresent") is False:` then `        permissions["allow"] = ["Bash"]`.
- Green:
```
.                                                                        [100%]
1 passed in 0.29s
```

## P2: allow emission (axis: a False flag emits exactly `["Bash"]`, the literal spelled out in the test)

- Neutralization in `A`: the same line became `if False:`.
- Node: `T::test_settings_allow_bash_when_managed_policy_absent`
- Red:
```
F                                                                        [100%]
[...]
E       AssertionError: assert {'deny': ['We... 'WebSearch']} == {'allow': ['B... 'WebSearch']}
E         Right contains 1 more item:
E         {'allow': ['Bash']}
FAILED plugins/superheroes/lib/tests/test_claude_write_channel_1569.py::test_settings_allow_bash_when_managed_policy_absent
1 failed in 0.48s
```
- Restore: inverse Edit, `if False:` back to `if sandbox.get("managedPolicyPresent") is False:`.
- Restore receipt, lines quoted back from `A`: `    if sandbox.get("managedPolicyPresent") is False:` then `        permissions["allow"] = ["Bash"]`.
- Green:
```
.                                                                        [100%]
1 passed in 0.28s
```

## P3: E2 fail-closed (axis: an lstat error other than not-found counts as present)

- Neutralization in `D`, `_managed_policy_location_present`: the bare `except OSError:` after the not-found handler returned `False` instead of `True`.
- Node: `T::test_presence_lstat_permission_error_is_present`
- Red:
```
F                                                                        [100%]
[...]
>       assert ED._managed_policy_present() is True
E       assert False is True
FAILED plugins/superheroes/lib/tests/test_claude_write_channel_1569.py::test_presence_lstat_permission_error_is_present
1 failed in 0.28s
```
- Restore: inverse Edit, that `return False` back to `return True`.
- Restore receipt, lines quoted back from `D`: `    except OSError:` then `        return True` then `    if kind == "file":`.
- Green:
```
.                                                                        [100%]
1 passed in 0.25s
```

## P4: E5 listdir fail-closed (axis: a listdir error on an existing dir location counts as present)

- Neutralization in `D`: the `except OSError:` after `return bool(os.listdir(path))` returned `False` instead of `True`.
- Node: `T::test_presence_listdir_permission_error_is_present`
- Red:
```
F                                                                        [100%]
[...]
>       assert ED._managed_policy_present() is True
E       assert False is True
FAILED plugins/superheroes/lib/tests/test_claude_write_channel_1569.py::test_presence_listdir_permission_error_is_present
1 failed in 0.29s
```
- Restore: inverse Edit, that `return False` back to `return True`.
- Restore receipt, lines quoted back from `D`: `        return bool(os.listdir(path))` then `    except OSError:` then `        return True`.
- Green:
```
.                                                                        [100%]
1 passed in 0.28s
```

## P5: S3 no-follow (axis: a symlinked `.claude` is never opened, so a symlink target is never touched)

- Neutralization in `D`, `_sweep_claude_dir`: `os.O_NOFOLLOW` dropped, leaving `os.O_RDONLY | os.O_DIRECTORY`.
- Node: `T::test_sweep_does_not_follow_symlinked_claude`
- Red:
```
F                                                                        [100%]
[...]
>       assert out["removed"] == []
E       AssertionError: assert ['.claude/.cc-writes'] == []
FAILED plugins/superheroes/lib/tests/test_claude_write_channel_1569.py::test_sweep_does_not_follow_symlinked_claude
1 failed in 0.29s
```
- Restore: inverse Edit, `O_NOFOLLOW` back into the flags.
- Restore receipt, line quoted back from `D`: `            ".claude", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=dirfd)`.
- Green:
```
.                                                                        [100%]
1 passed in 0.28s
```

## P6: S2 `.git` prune (axis: nothing under `.git` is walked)

- Neutralization in `D`, `_sweep_cc_writes`: `if name == ".git":` became `if False:`.
- Node: `T::test_sweep_prunes_git`
- Red:
```
F                                                                        [100%]
[...]
>       assert out["removed"] == []
E       AssertionError: assert ['.git/.claud....git/.claude'] == []
E         Left contains 2 more items, first extra item: '.git/.claude/.cc-writes'
FAILED plugins/superheroes/lib/tests/test_claude_write_channel_1569.py::test_sweep_prunes_git
1 failed in 0.30s
```
- Restore: inverse Edit, `if False:` back to `if name == ".git":`.
- Restore receipt, lines quoted back from `D`: `                if name == ".git":` then `                    continue`.
- Green:
```
.                                                                        [100%]
1 passed in 0.29s
```

## P7: S2 device prune (axis: a subdirectory on another device is never entered)

- Neutralization in `D`: `if dev != root_dev:` became `if False:`.
- Node: `T::test_sweep_does_not_cross_devices`
- Red:
```
F                                                                        [100%]
[...]
>       assert out["removed"] == ["plain/.claude/.cc-writes", "plain/.claude"]
E       AssertionError: assert ['plain/.clau...ount/.claude'] == ['plain/.clau...lain/.claude']
E         Left contains 2 more items, first extra item: 'mount/.claude/.cc-writes'
FAILED plugins/superheroes/lib/tests/test_claude_write_channel_1569.py::test_sweep_does_not_cross_devices
1 failed in 0.28s
```
- Restore: inverse Edit, `if False:` back to `if dev != root_dev:`.
- Restore receipt, lines quoted back from `D`: `                if dev != root_dev:` then `                    continue`.
- Green:
```
.                                                                        [100%]
1 passed in 0.26s
```
- Fixture note: the test's `os.stat` patch matches on inode rather than name, so the walker's own descent check (`samestat` of the entry stat against the fd stat) sees a consistent forged device and still descends. Only the sweep's device prune stops the walk, which is what the red above shows.

## P8: S1 budget (axis: an exhausted deadline stops the walk before any directory is processed)

- Neutralization in `D`: `if clock() > deadline:` became `if False:`.
- Node: `T::test_sweep_budget_exhausted_is_incomplete`
- Red:
```
F                                                                        [100%]
[...]
>       assert out == {"removed": [], "incomplete": True, "error": None}
E       AssertionError: assert {'removed': [...'error': None} == {'removed': [...'error': None}
E         {'removed': ['.claude/.cc-writes', '.claude']} != {'removed': []}
E         {'incomplete': False} != {'incomplete': True}
FAILED plugins/superheroes/lib/tests/test_claude_write_channel_1569.py::test_sweep_budget_exhausted_is_incomplete
1 failed in 0.33s
```
- Restore: inverse Edit, `if False:` back to `if clock() > deadline:`.
- Restore receipt, lines quoted back from `D`: `            if clock() > deadline:` then `                return {"removed": removed, "incomplete": True, "error": None}`.
- Green:
```
.                                                                        [100%]
1 passed in 0.29s
```

## P9: S5 parent removal (axis: the `.claude` parent is removed once its staging dir is gone and it is empty)

- Neutralization in `D`, `_sweep_claude_dir`: `os.rmdir(".claude", dir_fd=dirfd)` became `pass`.
- Node: `T::test_sweep_removes_empty_staging_and_parents`
- Red:
```
F                                                                        [100%]
[...]
>       assert not (tmp_path / ".claude").exists()
E       AssertionError: assert not True
FAILED plugins/superheroes/lib/tests/test_claude_write_channel_1569.py::test_sweep_removes_empty_staging_and_parents
1 failed in 0.32s
```
- Restore: inverse Edit, `pass` back to `os.rmdir(".claude", dir_fd=dirfd)`.
- Restore receipt, lines quoted back from `D`: `        os.rmdir(".claude", dir_fd=dirfd)` then `    except OSError:` then `        return False`.
- Green:
```
.                                                                        [100%]
1 passed in 0.28s
```

## P10: wiring (axis: the production fold runs the sweep and journals its result)

- Neutralization in `D`, `_fold_run`: `cc_writes = _fold_cc_writes_sweep(state)` became `cc_writes = None  # _fold_cc_writes_sweep(state)`.
- Node: `T::test_claude_write_fold_sweeps_worktree`
- Red:
```
F                                                                        [100%]
[...]
>       assert not os.path.exists(os.path.join(wt, ".claude"))
E       AssertionError: assert not True
FAILED plugins/superheroes/lib/tests/test_claude_write_channel_1569.py::test_claude_write_fold_sweeps_worktree
1 failed in 0.74s
```
- Restore: inverse Edit, that line back to `cc_writes = _fold_cc_writes_sweep(state)`.
- Restore receipt, lines quoted back from `D`: `    cc_writes = _fold_cc_writes_sweep(state)` then `    if cc_writes is not None:`.
- Green:
```
.                                                                        [100%]
1 passed in 0.76s
```

## P11: engine scope (axis: only claude write runs are swept; a codex write run is left alone and carries no key)

- Neutralization in `D`, `_fold_cc_writes_sweep`: `or opened.get("engine") != "claude"` removed from the guard.
- Node: `T::test_codex_write_fold_does_not_sweep`
- Red:
```
F                                                                        [100%]
[...]
>       assert os.path.isdir(staging)
E       AssertionError: assert False
FAILED plugins/superheroes/lib/tests/test_claude_write_channel_1569.py::test_codex_write_fold_does_not_sweep
1 failed in 0.65s
```
- Restore: inverse Edit, the condition put back.
- Restore receipt, line quoted back from `D`: `        if opened.get("runKind") != RUN_KIND_WRITE or opened.get("engine") != "claude":`.
- Green:
```
.                                                                        [100%]
1 passed in 0.58s
```
