# layer4a auditor seat time bite-proof (issue #1272, WO-B)

| ID | guarded element | proving test |
|---|---|---|
| B1 | runner-only candidate filter in `independent_auditor` | `test_t1_edge1_runner_only_claude_codex_fixer_cursor` |
| B2 | durable-entry refusal `_auditor_unseatable_refusal` | `test_t2_edge4_record_result_auditor_unseatable` |

## B1 — runner-only candidate filter in `independent_auditor`

**Axis:** durable-path auditor selection must exclude host-channel (claude) vendors.

**Guarded code:** `receipt_disclosures.independent_auditor`

**Neutralization:**

```python
        if False:
            continue
```

**Detector:** `test_t1_edge1_runner_only_claude_codex_fixer_cursor`

**Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_____________ test_t1_edge1_runner_only_claude_codex_fixer_cursor ______________

    def test_t1_edge1_runner_only_claude_codex_fixer_cursor():
        """Edge 1 — durable path picks codex, not claude, when fixer is cursor."""
        cfg = {"vendors": ["claude", "codex"], "fixerVendor": "cursor"}
        vendor, independence = round_driver._auditor_vendor(cfg, "cursor", runner_only=True)
>       assert vendor == "codex"
E       AssertionError: assert 'claude' == 'codex'
E         
E         - codex
E         + claude

plugins/superheroes/lib/tests/test_layer4a_auditor_seat_time_1272.py:48: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_layer4a_auditor_seat_time_1272.py::test_t1_edge1_runner_only_claude_codex_fixer_cursor
1 failed in 0.21s
```

**Restore (quoted restored lines):**

```python
        if runner_only and not session_contract.runner_channel_vendor(v):
            continue
```

**Green:**

```
.                                                                        [100%]
1 passed in 0.20s
```

## B2 — durable-entry refusal `_auditor_unseatable_refusal`

**Axis:** claude-only durable sessions refuse `record-result` at entry with `auditor-unseatable`.

**Guarded code:** `round_driver._auditor_unseatable_refusal`

**Neutralization:**

```python
def _auditor_unseatable_refusal(session_dir, state, cmd):
    return None
```

**Detector:** `test_t2_edge4_record_result_auditor_unseatable`

**Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
________________ test_t2_edge4_record_result_auditor_unseatable ________________

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-5303/test_t2_edge4_record_result_au0')

    def test_t2_edge4_record_result_auditor_unseatable(tmp_path):
        session_dir, _gitdir, _head_path = _claude_only_session(tmp_path)
        out = round_driver.cmd_record_result(session_dir, sweep=True)
>       assert out["ok"] is False
E       assert True is False

plugins/superheroes/lib/tests/test_layer4a_auditor_seat_time_1272.py:97: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_layer4a_auditor_seat_time_1272.py::test_t2_edge4_record_result_auditor_unseatable
1 failed in 3.39s
```

**Restore (quoted restored lines):**

```python
def _auditor_unseatable_refusal(session_dir, state, cmd):
    if state.get("_submitUsed"):
        return None
```

**Green:**

```
.                                                                        [100%]
1 passed in 3.97s
```
