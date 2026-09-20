# C14 L1 WO-A bite-proofs — claude dispatch channel, adapter, config_dir

## A1 — claude native channel

**Guarded element:** `engine_result_channel.py:47` `_CHANNEL_BY_ENGINE["claude"] = CHANNEL_NATIVE` — axis: claude is native-channel like codex/cursor.

**Neutralization:** `"claude": CHANNEL_NATIVE` → `"claude": CHANNEL_MARKER`.

**Raw red:**
```
FAILED ...::test_every_dispatchable_vendor_has_channel_delivery_pin_and_argv
>           assert ERC.channel_for(vendor) == ERC.CHANNEL_NATIVE
E           AssertionError: assert 'marker' == 'native'
1 failed in 0.33s
```

**Restore:** `"claude": CHANNEL_MARKER` → `"claude": CHANNEL_NATIVE`.

**Raw green:** `1 passed in 0.35s` (`test_every_dispatchable_vendor_has_channel_delivery_pin_and_argv`).

---

## A2 — BUILD_ARGV_VENDORS includes claude

**Guarded element:** `engine_adapter.py:257` `BUILD_ARGV_VENDORS = ("codex", "cursor", "claude")` — axis: claude opens the dispatch argv entry.

**Neutralization:** removed `"claude"` from tuple.

**Raw red:**
```
FAILED ...::test_claude_vendor_passes_dispatch_chokepoint_for_on_allowlist_cell[dispatch-review]
FAILED ...::test_claude_vendor_passes_dispatch_chokepoint_for_on_allowlist_cell[dispatch-write]
2 failed, 1 passed in 0.46s
```

**Restore:** re-added `"claude"` to `BUILD_ARGV_VENDORS`.

**Raw green:** see final suite receipt (797 passed).

---

## A3 — claude result delivery stdout

**Guarded element:** `engine_result_channel.py:56` `_RESULT_DELIVERY_BY_ENGINE["claude"]` — axis: native claude has stdout delivery.

**Neutralization:** removed `"claude": RESULT_DELIVERY_STDOUT,` from `_RESULT_DELIVERY_BY_ENGINE`.

**Raw red:**
```
FAILED ...::test_result_delivery_registered_engines
E           ValueError: native engine 'claude' has no result delivery entry
1 failed in 0.34s
```

**Restore:** re-added `"claude": RESULT_DELIVERY_STDOUT,`.

**Raw green:** `test_result_delivery_registered_engines` passes in final suite.

---

## A4 — review argv --restricted

**Guarded element:** claude review branch `argv += ["--restricted"]` — axis: review shape is restricted.

**Neutralization:** `argv += ["--restricted"]` → `argv += []`.

**Raw red:**
```
FAILED ...::test_build_argv_claude_review_exact_shape
E       Right contains one more item: '--restricted'
1 failed in 0.67s
```

**Restore:** `argv += ["--restricted"]`.

**Raw green:** `test_build_argv_claude_review_exact_shape` passes in final suite.

---

## A5 — write argv permission-mode

**Guarded element:** claude write branch `--permission-mode acceptEdits` — axis: write shape grants Bash.

**Neutralization:** removed the `argv += ["--permission-mode", "acceptEdits", "--allowedTools", "Bash"]` append.

**Raw red:**
```
FAILED ...::test_build_argv_claude_write_exact_shape
E       Right contains 4 more items, first extra item: '--permission-mode'
1 failed in 0.60s
```

**Restore:** reinstated permission-mode argv tail.

**Raw green:** `test_build_argv_claude_write_exact_shape` passes in final suite.

---

## A6 — StructuredOutput exclusion in claude_tool_calls

**Guarded element:** `if name == "StructuredOutput": continue` in `claude_tool_calls` — axis: result tool is not telemetry.

**Neutralization:** `if name == "StructuredOutput":` → `if False and name == "StructuredOutput":`.

**Raw red:**
```
FAILED ...::test_claude_tool_calls_fail_closed_edges
>       assert EA.claude_tool_calls(stream) == 0
E       assert 1 == 0
1 failed in 1.55s
```

**Restore:** restored `if name == "StructuredOutput":`.

**Raw green:** `test_claude_tool_calls_fail_closed_edges` passes in final suite.

---

## A7 — claude_result_envelope last result wins

**Guarded element:** `last = obj` in `claude_result_envelope` — axis: last result line is authoritative.

**Neutralization:** `last = obj` → `last = last or obj` (first wins).

**Raw red:**
```
FAILED ...::test_claude_result_envelope_fail_closed_edges
E       AssertionError: assert {'a': 1} == {'b': 2}
1 failed in 0.59s
```

**Restore:** `last = last or obj` → `last = obj`.

**Raw green:** `test_claude_result_envelope_fail_closed_edges` passes in final suite.

---

## A8 — fable-unrunnable refusal

**Guarded element:** `if engine_model == "fable-5": return _refuse("fable-unrunnable", ...)` — axis: fable-5 never dispatches.

**Neutralization:** prefixed condition with `False and`.

**Raw red:**
```
FAILED ...::test_build_argv_claude_fail_closed_edges
>       assert res["reason"] == "fable-unrunnable"
E       AssertionError: assert 'invalid-model-effort' == 'fable-unrunnable'
1 failed in 1.24s
```

**Restore:** removed `False and` prefix.

**Raw green:** edge-2 assertions pass in final suite.

---

## A9 — effort required for claude

**Guarded element:** `model_registry.validate_config("claude", engine_model, effort)` — axis: None effort is refused.

**Neutralization:** replaced call with `(True, None)`.

**Raw red:**
```
FAILED ...::test_build_argv_claude_fail_closed_edges
>       assert res["reason"] == "invalid-model-effort"
E       AssertionError: assert None == 'invalid-model-effort'
1 failed in 0.60s
```

**Restore:** restored `model_registry.validate_config("claude", engine_model, effort)`.

**Raw green:** edge-4 assertions pass in final suite.

---

## A10 — config_dir relative override without cwd

**Guarded element:** `config_dir.py:50` `return None` on relative override without absolute cwd — axis: omit rather than guess.

**Neutralization:** `return None` → `return path # neutralized`.

**Raw red:**
```
FAILED ...::test_resolve_relative_override_without_absolute_cwd_returns_none
E       AssertionError: assert 'relative/config' is None
1 failed in 0.12s
```

**Restore:** `return path # neutralized` → `return None`.

**Raw green:** `test_config_dir.py` (6 passed) in final suite.
