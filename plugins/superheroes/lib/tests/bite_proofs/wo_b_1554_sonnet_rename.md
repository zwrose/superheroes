# WO-B #1554 bite-proof record: registry Sonnet row `sonnet-5` -> `sonnet-5.5`

Each proof ran the single test node (`pytest <file>::<name> -q -p no:xdist`) on claude-code 2.1.284 tooling,
neutralized by a targeted edit and restored by the inverse edit.

## 1. Guarded element: absence of the `sonnet-5` registry row (test_legacy_sonnet_5_label_stays_unregistered)

Neutralization: in `lib/model_registry.py` `_MODELS["claude"]`, added a `"sonnet-5"` row copying the `sonnet-5.5` row.

Red:

```
F                                                                        [100%]
    def test_legacy_sonnet_5_label_stays_unregistered():
>       assert MR.validate_config("claude", "sonnet-5", "high")[0] is False
E       assert True is False
FAILED plugins/superheroes/lib/tests/test_model_registry.py::test_legacy_sonnet_5_label_stays_unregistered
1 failed in 0.28s
```

Restore: removed the added `"sonnet-5"` row; the `"sonnet-5.5": {"family": "anthropic", "dispatch": "sonnet", "override_only": False},` line sits at line 16 again.

Green:

```
.                                                                        [100%]
1 passed in 4.87s
```

## 2. Guarded element: exact compare of the model key in `_continuation_seat_mismatch` (test_continuation_refuses_legacy_sonnet_label)

Neutralization: in `lib/engine_dispatch.py` `_continuation_seat_mismatch`, before the tuple compare, added
`snapshot = dict(snapshot)` and `snapshot["model"] = {"sonnet-5": "sonnet-5.5"}.get(snapshot.get("model"), snapshot.get("model"))`.

Red:

```
>       assert ED._continuation_seat_mismatch(opened, seat) == ED.SEAT_REFUSAL_RUN_DIR_MISMATCH
E       AssertionError: assert None == 'run-dir-seat-mismatch'
FAILED plugins/superheroes/lib/tests/test_model_registry.py::test_continuation_refuses_legacy_sonnet_label
1 failed in 0.47s
```

Restore: removed those two lines; `git diff --stat lib/engine_dispatch.py` is empty.

Green:

```
.                                                                        [100%]
1 passed in 0.41s
```

## 3. Guarded element: the alias record vs the registry id (test_claude_alias_resolution_record_matches_registry_ids)

Neutralization: `CLAUDE_ALIAS_RESOLUTION["resolved"]["sonnet"]` set back to `"claude-sonnet-5"`.

Red:

```
E           AssertionError: ('sonnet-5.5', 'claude-sonnet-5', 'claude-sonnet-5-5')
E           assert None
FAILED plugins/superheroes/lib/tests/test_model_registry.py::test_claude_alias_resolution_record_matches_registry_ids
1 failed in 0.29s
```

Restore: the line reads `"sonnet": "claude-sonnet-5-5",` again.

Green:

```
.                                                                        [100%]
1 passed in 0.27s
```
