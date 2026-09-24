# C14 L2b WO-3 bite-proof — non-print claude mode capability/delivery SSOT

**Provenance:** cursor CLI / composer-2.5

## Guarded element

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| BP-1 | adapter `_NON_PRINT_CLAUDE_MODE_ENGINES` vs derived `_RESULT_DELIVERY_BY_ENGINE_MODE` | every declared (engine, mode) has delivery and no ghost delivery keys | `test_non_print_claude_mode_capability_delivery_agree` |

## BP-1 — capability/delivery bidirectional lockstep

**neutralization** (`plugins/superheroes/lib/engine_adapter.py`, `_NON_PRINT_CLAUDE_MODE_ENGINES`):
```python
_NON_PRINT_CLAUDE_MODE_ENGINES = {
    MODE_BACKGROUND: frozenset({"claude"}),
    "c14-biteproof-orphan-mode": frozenset({"claude"}),
}
```

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-wo3 -m pytest plugins/superheroes/lib/tests/test_engine_result_channel.py::test_non_print_claude_mode_capability_delivery_agree -q
```

**raw red** (exit 4 — construction-time detector fires before the drift test can load `engine_result_channel`):
```
ERROR: found no collectors for /private/tmp/claude-501/-Users-zwrose--superheroes-worktrees-superheroes-issue-1273-29f83ecdc925daa1/6b3c4743-84e0-42b3-be92-310220c6d517/scratchpad/wo3/plugins/superheroes/lib/tests/test_engine_result_channel.py::test_non_print_claude_mode_capability_delivery_agree


==================================== ERRORS ====================================
_ ERROR collecting plugins/superheroes/lib/tests/test_engine_result_channel.py _
plugins/superheroes/lib/tests/test_engine_result_channel.py:28: in <module>
    ERC = _load("engine_result_channel")
plugins/superheroes/lib/tests/test_engine_result_channel.py:24: in _load
    spec.loader.exec_module(mod)
<frozen importlib._bootstrap_external>:850: in exec_module
    ???
<frozen importlib._bootstrap>:228: in _call_with_frames_removed
    ???
plugins/superheroes/lib/engine_result_channel.py:91: in <module>
    _RESULT_DELIVERY_BY_ENGINE_MODE = _derive_result_delivery_by_engine_mode()
plugins/superheroes/lib/engine_result_channel.py:81: in _derive_result_delivery_by_engine_mode
    raise ValueError(
E   ValueError: non-print claude mode 'c14-biteproof-orphan-mode' declared in engine_adapter has no result delivery entry in _RESULT_DELIVERY_BY_MODE
=========================== short test summary info ============================
ERROR plugins/superheroes/lib/tests/test_engine_result_channel.py - ValueErro...
1 error in 0.49s
```

**restore:** removed the `"c14-biteproof-orphan-mode": frozenset({"claude"})` entry from `_NON_PRINT_CLAUDE_MODE_ENGINES`.

**restored lines quoted back:**
```python
_NON_PRINT_CLAUDE_MODE_ENGINES = {
    MODE_BACKGROUND: frozenset({"claude"}),
}
```

**raw green:**
```
.                                                                        [100%]
1 passed in 0.34s
```
