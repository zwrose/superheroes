# #1569 WO-1 bite-proof: the claude write channel allow, managed-policy presence, and the `.cc-writes` sweep

Detectors live in `plugins/superheroes/lib/tests/test_claude_write_channel_1569.py` (`T`). Guarded code: `claude_write_sandbox_settings` in `plugins/superheroes/lib/engine_adapter.py` (`A`), and `_managed_policy_location_present`, `_sweep_claude_dir`, `_sweep_cc_writes`, `_fold_cc_writes_sweep`, `_fold_run` in `plugins/superheroes/lib/engine_dispatch.py` (`D`).

Every neutralization was a targeted Edit by the implementer, restored by the inverse Edit (quoted below). Each red is the single test node run alone, unedited, with `scripts/pinned-python -m pytest <node> -q -p no:cacheprovider`. Each green is the same command after the restore. Captures are verbatim; the only elision is the traceback body of the red, where it repeats the test source (marked `[...]`). Nothing in the captures needed redaction.

Declared guarded-element set: P1 to P4 (layer 1 of the split; P5 to P11 land with layer 2), one entry each, no equivalence classes.

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
