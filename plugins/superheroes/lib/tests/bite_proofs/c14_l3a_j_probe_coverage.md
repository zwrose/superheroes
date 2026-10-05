# WO-L3A-J (#1273) bite-proof — conformance-probe coverage gaps

**Provenance:** cursor / composer-2.5 (implementer).

## Guarded elements

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| BP-J-a | `_execute_injected_attempt` delivery-kind completion stamping | transcript delivery reaches the same admission verdict as the real path; all-green claude both-mode case is expressible | `test_claude_probe_all_green_both_modes` |
| BP-J-b | claude all-mode run-dir preflight in `probe` | zero engine invocations when any mode directory is reused | `test_claude_probe_refuses_reused_background_before_any_mode_dispatches` |

---

## BP-J-a — injected seam stamps transcript completion fields

- **axis:** `_execute_injected_attempt` records `transcriptResult` / `transcriptToolCalls` for `RESULT_DELIVERY_TRANSCRIPT` instead of always stamping `stdoutResult`

**neutralization** (`plugins/superheroes/lib/engine_dispatch.py`, `_execute_injected_attempt`):
```python
    if stdout_result is not None:
        ended["stdoutResult"] = stdout_result
```

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_conformance_probe.py -q
```

**raw red** (exit 1):
```
........FF.............................F................................ [ 90%]
........                                                                 [100%]
=================================== FAILURES ===================================
________ test_claude_probe_green_as_far_as_the_injected_seam_can_reach _________
...
>       assert payload["modeLegs"]["background"]["resultProduction"]["ok"] is True
E       assert False is True
...
____________________ test_claude_probe_all_green_both_modes ____________________
...
>               assert payload["modeLegs"][mode][leg_name]["ok"] is True, (mode, leg_name)
E               AssertionError: ('background', 'resultProduction')
...
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_conformance_probe.py::test_claude_probe_green_as_far_as_the_injected_seam_can_reach
FAILED plugins/superheroes/lib/tests/test_conformance_probe.py::test_claude_probe_all_green_both_modes
2 failed, 78 passed in 3.55s
```

**restore** (`plugins/superheroes/lib/engine_dispatch.py`, `_execute_injected_attempt`):
```python
    if stdout_result is not None:
        try:
            delivery = engine_result_channel.result_delivery(
                opened.get("engine"), opened.get("claudeMode"),
            )
        except (engine_result_channel.UnknownEngineError, ValueError):
            delivery = None
        if delivery == engine_result_channel.RESULT_DELIVERY_TRANSCRIPT:
            ended["transcriptResult"] = stdout_result
            rows = _read_transcript_rows(stdout_path)
            if rows is not None and engine_adapter.claude_transcript_turn_ended(rows):
                tool_calls = engine_adapter.claude_transcript_tool_calls(rows)
                if tool_calls is not None:
                    ended["transcriptToolCalls"] = tool_calls
        else:
            ended["stdoutResult"] = stdout_result
```

**raw green** (exit 0):
```
........................................................................ [ 90%]
........                                                                 [100%]
80 passed in 3.22s
```

---

## BP-J-b — all-mode preflight blocks dispatch before any mode runs

- **axis:** a reused `background/` journal refuses the whole claude probe with zero `run_engine` calls, including when `print/` is empty and never probed

**neutralization** (`plugins/superheroes/lib/conformance_probe.py`, `probe` all-mode reuse branch):
```python
    elif any_reused:
        for mode in modes:
            _, reused, _ = _ensure_mode_run_dir(_mode_run_dir(parent_run_dir, mode))
            if reused:
                mode_legs[mode] = _stamp_mode_run_dir(_all_legs_failed("run-dir-reused"), mode_dirs[mode])
            else:
                mode_legs[mode] = _probe_one_mode(
                    engine, mode, seat, repo_real, parent_run_dir, prompt_path, timeout,
                    run_engine, build_view, order_suffix)
```

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_conformance_probe.py -q
```

**raw red** (exit 1):
```
.......................................F................................ [ 90%]
........                                                                 [100%]
=================================== FAILURES ===================================
____ test_claude_probe_refuses_reused_background_before_any_mode_dispatches ____
...
>       assert len(fake.calls) == 0
E       AssertionError: assert 1 == 0
E        +  where 1 = len([{'argv': ['claude', '-p', '--model', 'opus', '--effort', 'xhigh', ...], 'cwd': '.../view-1', 'timeout': 30}])
...
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_conformance_probe.py::test_claude_probe_refuses_reused_background_before_any_mode_dispatches
1 failed, 79 passed in 4.82s
```

**restore** (`plugins/superheroes/lib/conformance_probe.py`, `probe` all-mode reuse branch):
```python
    elif any_reused:
        for mode in modes:
            mode_legs[mode] = _stamp_mode_run_dir(_all_legs_failed("run-dir-reused"), mode_dirs[mode])
```

**raw green** (exit 0):
```
........................................................................ [ 90%]
........                                                                 [100%]
80 passed in 1.45s
```
