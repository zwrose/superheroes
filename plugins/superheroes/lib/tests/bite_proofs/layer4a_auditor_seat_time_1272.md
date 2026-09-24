# layer4a auditor seat time bite-proof (issue #1272, WO-B3)

Re-taken at head d0ff2866 plus WO-B3 latch and absent-auditor guard fixes.

| ID | guarded element | proving test |
|---|---|---|
| B1 | runner-only candidate filter in `independent_auditor` | `test_t1_edge1_runner_only_claude_codex_fixer_cursor` |
| B2 | durable-path emission guard in `_emit_orders_manifest` | `test_t2_cmd_next_refuses_claude_auditor` |
| B3 | absent-auditor clause in emission guard | `test_t2b_emit_orders_manifest_refuses_missing_auditor_vendor` |
| B4 | `_advanceUsed` latch in `_audit_targets` | `test_explicit_cross_family_fixer_still_independent_two_vendor` |

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
1 failed in 0.22s
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

## B2 — durable-path emission guard in `_emit_orders_manifest`

**Axis:** durable-path dispatch-audits emission refuses when a target explicitly seats a non-runner auditor.

**Guarded code:** `round_driver._emit_orders_manifest` (P_AUDITS guard)

**Neutralization:**

```python
    if False and phase == P_AUDITS and state.get("_advanceUsed"):
```

**Detector:** `test_t2_cmd_next_refuses_claude_auditor`

**Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
___________________ test_t2_cmd_next_refuses_claude_auditor ____________________

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-5500/test_t2_cmd_next_refuses_claud0')

    def test_t2_cmd_next_refuses_claude_auditor(tmp_path):
        session_dir, _state_obj, _target = _audits_emit_fixture(tmp_path, advance_used=True)
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
1 failed in 4.41s
```

**Restore (quoted restored lines):**

```python
    if phase == P_AUDITS and state.get("_advanceUsed"):
```

**Green:**

```
.                                                                        [100%]
1 passed in 3.68s
```

## B3 — absent-auditor clause in emission guard

**Axis:** durable-path dispatch-audits emission refuses when a target omits `auditorVendor`.

**Guarded code:** `round_driver._emit_orders_manifest` (key-presence clause)

**Neutralization:**

```python
            if ("auditorVendor" in target
                    and not session_contract.runner_channel_vendor(target.get("auditorVendor"))):
```

**Detector:** `test_t2b_emit_orders_manifest_refuses_missing_auditor_vendor`

**Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_________ test_t2b_emit_orders_manifest_refuses_missing_auditor_vendor _________

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-5502/test_t2b_emit_orders_manifest_0')

    def test_t2b_emit_orders_manifest_refuses_missing_auditor_vendor(tmp_path):
        session_dir, state, target = _audits_emit_fixture(tmp_path, advance_used=True)
        target_no_vendor = {k: v for k, v in target.items() if k != "auditorVendor"}
        state["_auditTargets"] = [target_no_vendor]
        round_driver.save_state(session_dir, state)
        manifest_path = _orders_manifest_path(session_dir, 1, 0)
        assert not os.path.exists(manifest_path)
        with pytest.raises(round_driver.AuditorUnseatable):
>           round_driver._emit_orders_manifest(
                session_dir, state, 1, P_AUDITS, 0, [target_no_vendor["id"]],
                journal_cmd="next", pending_payload=_audits_payload([target_no_vendor]))

plugins/superheroes/lib/tests/test_layer4a_auditor_seat_time_1272.py:157: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
plugins/superheroes/lib/round_driver.py:9116: in _emit_orders_manifest
    context, paths = _build_order_render_context(session_dir, state, rnd, phase, attempt,
plugins/superheroes/lib/round_driver.py:8954: in _build_order_render_context
    "placeholders": _order_placeholders(phase, seat_key, occurrence, state,
plugins/superheroes/lib/round_driver.py:8841: in _order_placeholders
    head_diff_path = ROUND_MATERIALIZER_REGISTRY["round_head_diff"](session_dir, rnd, state)
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

session_dir = '/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-5502/test_t2b_emit_orders_manifest_0/s'
rnd = 1
state = {'_advanceUsed': True, '_auditTargets': [{'file': 'src/f00.py', 'id': 'finding::src/f00.py::2', 'identity': 'unchecked index', 'line': 2, ...}], '_changedSubjectsSincePanel': [], '_coverage': [], ...}

    def _ensure_round_head_diff(session_dir, rnd, state):
        """Write `round-<N>/head.diff` from state when absent or untrusted."""
        head_text = state.get("headDiff")
        if not isinstance(head_text, str):
>           raise ValueError("order-render-refused:head-diff-unavailable")
E           ValueError: order-render-refused:head-diff-unavailable

plugins/superheroes/lib/round_driver.py:8576: ValueError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_layer4a_auditor_seat_time_1272.py::test_t2b_emit_orders_manifest_refuses_missing_auditor_vendor
1 failed in 4.41s
```

**Restore (quoted restored lines):**

```python
            if not session_contract.runner_channel_vendor(target.get("auditorVendor")):
```

**Green:**

```
.                                                                        [100%]
1 passed in 6.89s
```

## B4 — `_advanceUsed` latch in `_audit_targets`

**Axis:** runner-only auditor selection applies only when `_advanceUsed` is set, not for `run_loop` harness sessions.

**Guarded code:** `round_driver._audit_targets` (`runner_only` latch)

**Neutralization:**

```python
    runner_only = True
```

**Detector:** `test_explicit_cross_family_fixer_still_independent_two_vendor`

**Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
________ test_explicit_cross_family_fixer_still_independent_two_vendor _________

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-5505/test_explicit_cross_family_fix0')

    def test_explicit_cross_family_fixer_still_independent_two_vendor(tmp_path):
        """#608 contrast: known codex fixer with two vendors still yields independent audit."""
        captured = {"targets": None}

        def auditor(targets, rnd):
            captured["targets"] = [dict(t) for t in (targets or [])]
            return [{"id": t["id"], "ruling": "discharged", "reason": "ok", "evidence": "e",
                     "auditorVendor": t.get("auditorVendor")} for t in (targets or [])]

        cfg = {"leg": "code", "vendors": ["claude", "codex"], "diff": DIFF, "fixerVendor": "codex",
               "baseGuard": RD.BASE_GUARD_CHECKED}
        receipt = RD.run_loop(_seams(
                reviewer=lambda dim, tier, rnd, ctx:
                    ({"findings": [{"title": "bug", "severity": "Important", "file": "f.py", "line": 1}]}
                     if rnd == 1 and dim == "code-reviewer" else []),
                auditor=auditor, fixer_vendor="codex"), cfg)
        assert receipt["loopTerminal"] == "converged"
        t = captured["targets"][0]
>       assert t["independence"] == "independent"
E       AssertionError: assert 'degraded' == 'independent'
E         
E         - independent
E         + degraded

plugins/superheroes/lib/tests/test_round_driver.py:2278: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_round_driver.py::test_explicit_cross_family_fixer_still_independent_two_vendor
1 failed in 1.42s
```

**Restore (quoted restored lines):**

```python
    runner_only = bool(state.get("_advanceUsed"))
```

**Green:**

```
.                                                                        [100%]
1 passed in 1.16s
```
