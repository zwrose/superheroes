# layer4a auditor seat time bite-proof (issue #1272, WO-B2)

Re-taken at head a210126c plus WO-B2 emission-guard changes.

| ID | guarded element | proving test |
|---|---|---|
| B1 | runner-only candidate filter in `independent_auditor` | `test_t1_edge1_runner_only_claude_codex_fixer_cursor` |
| B2 | durable-path emission guard in `_emit_orders_manifest` | `test_t2_cmd_next_refuses_claude_auditor` |

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

plugins/superheroes/lib/tests/test_layer4a_auditor_seat_time_1272.py:81: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_layer4a_auditor_seat_time_1272.py::test_t1_edge1_runner_only_claude_codex_fixer_cursor
1 failed in 0.28s
```

**Restore (quoted restored lines):**

```python
        if runner_only and not session_contract.runner_channel_vendor(v):
            continue
```

**Green:**

```
.                                                                        [100%]
1 passed in 0.29s
```

## B2 — durable-path emission guard in `_emit_orders_manifest`

**Axis:** durable-path dispatch-audits emission refuses when a target explicitly seats a non-runner auditor.

**Guarded code:** `round_driver._emit_orders_manifest` (P_AUDITS guard)

**Neutralization:**

```python
    if False and phase == P_AUDITS and not state.get("_submitUsed"):
```

**Detector:** `test_t2_cmd_next_refuses_claude_auditor`

**Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
___________________ test_t2_cmd_next_refuses_claude_auditor ____________________

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-5374/test_t2_cmd_next_refuses_claud0')

    def test_t2_cmd_next_refuses_claude_auditor(tmp_path):
        session_dir, _state_obj, _target = _audits_emit_fixture(tmp_path)
        manifest_path = _orders_manifest_path(session_dir, 1, 0)
        out = round_driver.cmd_next(session_dir)
        assert out["ok"] is False
>       assert out["reason"] == round_driver.AUDITOR_UNSEATABLE_CAUSE
E       AssertionError: assert 'order-render-refused' == 'auditor-unseatable'
E         
E         - auditor-unseatable
E         + order-render-refused

plugins/superheroes/lib/tests/test_layer4a_auditor_seat_time_1272.py:143: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_layer4a_auditor_seat_time_1272.py::test_t2_cmd_next_refuses_claude_auditor
1 failed in 6.25s
```

**Restore (quoted restored lines):**

```python
    if phase == P_AUDITS and not state.get("_submitUsed"):
```

**Green:**

```
.                                                                        [100%]
1 passed in 5.90s
```
