# layer4a ruling evidence bite-proof (issue #1272, WO-D2)

Re-taken at head 018f5240.

| ID | guarded element | proving test |
|---|---|---|
| D1 | `_assemble_dispatch_evidence` adoption block | `test_edge1_stub_ruling_landing_adopts_runner_payload` |
| D2 | `_validate_execution_evidence` optional-field allowlist | `test_edge2_matching_scrubbed_payload_binds_with_model` |
| D3 | `_validate_execution_evidence` model type check | `test_edge9_bad_model_value_refuses_malformed[]` |
| D4 | `_independence_block` receipt model | `test_receipt_audit_seat_model_equals_runner_engine_model` |

## D1 — `_assemble_dispatch_evidence` adoption block

**Axis:** stub landing with no envelope payload adopts runner graded `resultContent`.

**Guarded code:** `round_driver._assemble_dispatch_evidence`

**Neutralization:**

```python
    if False:
```

**Detector:** `test_edge1_stub_ruling_landing_adopts_runner_payload`

**Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_____________ test_edge1_stub_ruling_landing_adopts_runner_payload _____________

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-5344/test_edge1_stub_ruling_landing0')

    def test_edge1_stub_ruling_landing_adopts_runner_payload(tmp_path):
        """Edge 1 — stub landing adopts runner graded record and records model."""
        session_dir, _gitdir, _head_path = _drive_to_audits(tmp_path, name="edge1-adopt")
        seat = _audit_roster(session_dir)[0]
        pend = _pending(session_dir)
        order_path = RR.order_prompt_path(
            session_dir, pend["round"], pend["phase"], RR.storage_key(seat), pend["attempt"])
        anchor_head = _anchor_head_sha(session_dir) or "abc123fake"
        run_dir = _audit_execution_run_dir(tmp_path, order_path, seat, view_head_sha=anchor_head)
        _patch_run_opened_engine_model(run_dir, "gpt-5.6-sol-medium")
        record, err = engine_dispatch.run_execution_record(run_dir)
        assert err is None, err
        assert isinstance(record.get("resultContent"), dict)
        state = _state(session_dir)
        _stub_dispatch_observed_land(session_dir, state, pend, seat, payload=None)
        out = RD.cmd_record_result(session_dir, seat, evidence_run_dir=run_dir)
>       assert out["ok"] is True, out
E       AssertionError: {'expectedPayloadSha256': '35960e668b7f1d6d23551afed1c6b048469b8e260d75d80a4c2bfedbefb589bf', 'ok': False, 'reason': 'evidence-result-mismatch', 'resultDigest': '35960e668b7f1d6d23551afed1c6b048469b8e260d75d80a4c2bfedbefb589bf', ...}
E       assert False is True

plugins/superheroes/lib/tests/test_layer4a_ruling_evidence_1272.py:113: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_layer4a_ruling_evidence_1272.py::test_edge1_stub_ruling_landing_adopts_runner_payload
1 failed in 8.15s
```

**Restore (quoted restored lines):**

```python
    if (result_kind in session_contract.RECORD_RESULT_KINDS
            and envelope_payload is None):
```

**Green:**

```
.                                                                        [100%]
1 passed in 6.74s
```

## D2 — `_validate_execution_evidence` optional-field allowlist

**Axis:** `model` is an allowed optional execution-evidence field.

**Guarded code:** `round_records._validate_execution_evidence`

**Neutralization:**

```python
    allowed = set(EXECUTION_EVIDENCE_FIELDS)
```

**Detector:** `test_edge2_matching_scrubbed_payload_binds_with_model`

**Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
____________ test_edge2_matching_scrubbed_payload_binds_with_model _____________

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-5353/test_edge2_matching_scrubbed_p0')

    def test_edge2_matching_scrubbed_payload_binds_with_model(tmp_path):
        """Edge 2 — landing payload equals runner scrubbed record; model in evidence."""
        session_dir, _gitdir, _head_path = _drive_to_audits(tmp_path, name="edge2-match")
        seat = _audit_roster(session_dir)[0]
        pend = _pending(session_dir)
        order_path = RR.order_prompt_path(
            session_dir, pend["round"], pend["phase"], RR.storage_key(seat), pend["attempt"])
        anchor_head = _anchor_head_sha(session_dir) or "abc123fake"
        run_dir = _audit_execution_run_dir(tmp_path, order_path, seat, view_head_sha=anchor_head)
        _patch_run_opened_engine_model(run_dir, "claude-opus-5-5-medium")
        record, err = engine_dispatch.run_execution_record(run_dir)
        assert err is None, err
        ruling_payload = record["resultContent"]
        state = _state(session_dir)
        TRI._dispatch_observed_land(session_dir, state, pend, seat, ruling_payload)
        out = RD.cmd_record_result(session_dir, seat, evidence_run_dir=run_dir)
>       assert out["ok"] is True, out
E       AssertionError: {'detail': None, 'ok': False, 'reason': 'execution-evidence-unknown-field', 'seat': 'src/f00.py::unchecked index@L2'}
E       assert False is True

plugins/superheroes/lib/tests/test_layer4a_ruling_evidence_1272.py:137: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_layer4a_ruling_evidence_1272.py::test_edge2_matching_scrubbed_payload_binds_with_model
1 failed in 7.64s
```

**Restore (quoted restored lines):**

```python
    allowed = set(EXECUTION_EVIDENCE_FIELDS) | set(EXECUTION_EVIDENCE_OPTIONAL_FIELDS)
```

**Green:**

```
.                                                                        [100%]
1 passed in 7.86s
```

## D3 — `_validate_execution_evidence` model type check

**Axis:** empty-string `model` refuses `execution-evidence-malformed`.

**Guarded code:** `round_records._validate_execution_evidence`

**Neutralization:**

```python
        if False:
```

**Detector:** `test_edge9_bad_model_value_refuses_malformed[]`

**Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
________________ test_edge9_bad_model_value_refuses_malformed[] ________________

bad_model = ''

    @pytest.mark.parametrize("bad_model", ["", 42, ["list"]])
    def test_edge9_bad_model_value_refuses_malformed(bad_model):
        """Edge 9 — model present but empty, numeric, or list refuses malformed."""
        evidence = {
            "source": "codex",
            "runnerNonce": "nonce-edge9",
            "recordDigest": "d" * 64,
            "resultDigest": "e" * 64,
            "resultKind": "ruling",
            "model": bad_model,
            "observation": {
                "tokens": None,
                "toolCalls": 1,
                "stdoutBytes": 10,
                "wallSeconds": 1.0,
                "source": "codex",
                "read": "engaged",
                "telemetry": "tool-calls",
            },
        }
>       reason, extra = RR._validate_execution_evidence(evidence)
E       TypeError: cannot unpack non-iterable NoneType object

plugins/superheroes/lib/tests/test_layer4a_ruling_evidence_1272.py:301: TypeError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_layer4a_ruling_evidence_1272.py::test_edge9_bad_model_value_refuses_malformed[]
1 failed in 0.68s
```

**Restore (quoted restored lines):**

```python
        if model is not None and (not isinstance(model, str) or not model):
```

**Green:**

```
.                                                                        [100%]
1 passed in 0.39s
```

## D4 — `_independence_block` receipt model

**Axis:** receipt `independence.auditSeats[0].model` equals runner `engineModel`.

**Guarded code:** `round_certification._independence_block`

**Neutralization:**

```python
        model = None
```

**Detector:** `test_receipt_audit_seat_model_equals_runner_engine_model`

**Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
___________ test_receipt_audit_seat_model_equals_runner_engine_model ___________

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-5369/test_receipt_audit_seat_model_0')

    def test_receipt_audit_seat_model_equals_runner_engine_model(tmp_path):
        """Receipt test — independence.auditSeats[0].model equals runner engineModel."""
        from round_certification_fixtures import (
            AUDIT_PHASE,
            DEFAULT_PANEL_PAYLOAD,
            DEFAULT_PANEL_PAYLOAD_SHA,
            HEAD_SHA,
            write_session,
        )

        engine_model = "gemini-3.8-flash-high"
        audit_seat = "audit-target-01"
        audit_payload = {
            "id": audit_seat,
            "ruling": "discharged",
            "reason": "ok",
            "auditorVendor": "claude",
        }
        audit_payload_sha = RR.payload_sha256(audit_payload)
        audit_evidence = {
            "source": "claude",
            "runnerNonce": "nonce-receipt-model",
            "recordDigest": "d" * 64,
            "resultDigest": audit_payload_sha,
            "resultKind": "ruling",
            "model": engine_model,
            "observation": {
                "read": "engaged",
                "source": "claude",
                "telemetry": "tool-calls",
                "stdoutBytes": 10,
                "wallSeconds": 1.0,
                "tokens": None,
                "toolCalls": 1,
            },
        }
        obs_fields = audit_evidence["observation"]
        panel_evidence = {
            "source": "codex",
            "runnerNonce": "nonce-panel",
            "recordDigest": "d" * 64,
            "resultDigest": RR.payload_sha256(DEFAULT_PANEL_PAYLOAD["findings"]),
            "resultKind": "findings",
            "observation": dict(obs_fields, source="codex"),
        }
        fixer_evidence = {
            "source": "cursor",
            "runnerNonce": "nonce-fixer",
            "recordDigest": "d" * 64,
            "resultDigest": RR.payload_sha256(DEFAULT_PANEL_PAYLOAD["findings"]),
            "resultKind": "findings",
            "observation": dict(obs_fields, source="cursor"),
        }
        journal_lines = [
            {
                "cmd": "record-result",
                "outcome": "recorded",
                "phase": RC.PANEL_PHASE,
                "round": 1,
                "attempt": 0,
                "seat": "code-reviewer",
                "occurrence": 0,
                "provenance": RR.PROVENANCE_DISPATCH_OBSERVED,
                "payloadSha256": DEFAULT_PANEL_PAYLOAD_SHA,
                "headSha": HEAD_SHA,
                "citedHead": HEAD_SHA,
                "executionEvidence": panel_evidence,
                "recordIdentity": {
                    "phase": RC.PANEL_PHASE,
                    "seat": "code-reviewer",
                    "occurrence": 0,
                    "attempt": 0,
                },
            },
            {
                "cmd": "record-result",
                "outcome": "recorded",
                "phase": "dispatch-fixer",
                "round": 1,
                "attempt": 0,
                "seat": "dispatch-fixer",
                "occurrence": 0,
                "provenance": RR.PROVENANCE_DISPATCH_OBSERVED,
                "payloadSha256": DEFAULT_PANEL_PAYLOAD_SHA,
                "headSha": HEAD_SHA,
                "citedHead": HEAD_SHA,
                "executionEvidence": fixer_evidence,
                "recordIdentity": {
                    "phase": "dispatch-fixer",
                    "seat": "dispatch-fixer",
                    "occurrence": 0,
                    "attempt": 0,
                },
            },
            {
                "cmd": "record-result",
                "outcome": "recorded",
                "phase": AUDIT_PHASE,
                "round": 1,
                "attempt": 0,
                "seat": audit_seat,
                "occurrence": 0,
                "provenance": RR.PROVENANCE_DISPATCH_OBSERVED,
                "payloadSha256": audit_payload_sha,
                "headSha": HEAD_SHA,
                "citedHead": HEAD_SHA,
                "executionEvidence": audit_evidence,
                "recordIdentity": {
                    "phase": AUDIT_PHASE,
                    "seat": audit_seat,
                    "occurrence": 0,
                    "attempt": 0,
                },
            },
        ]
        envelopes = [
            {
                "seat": "code-reviewer",
                "phase": RC.PANEL_PHASE,
                "round": 1,
                "attempt": 0,
                "occurrence": 0,
                "provenance": RR.PROVENANCE_DISPATCH_OBSERVED,
                "payloadSha256": DEFAULT_PANEL_PAYLOAD_SHA,
                "payload": DEFAULT_PANEL_PAYLOAD,
                "executionEvidence": panel_evidence,
            },
            {
                "seat": "dispatch-fixer",
                "phase": "dispatch-fixer",
                "round": 1,
                "attempt": 0,
                "occurrence": 0,
                "provenance": RR.PROVENANCE_DISPATCH_OBSERVED,
                "payloadSha256": DEFAULT_PANEL_PAYLOAD_SHA,
                "payload": DEFAULT_PANEL_PAYLOAD,
                "executionEvidence": fixer_evidence,
            },
            {
                "seat": audit_seat,
                "phase": AUDIT_PHASE,
                "round": 1,
                "attempt": 0,
                "occurrence": 0,
                "provenance": RR.PROVENANCE_DISPATCH_OBSERVED,
                "payloadSha256": audit_payload_sha,
                "payload": audit_payload,
                "executionEvidence": audit_evidence,
            },
        ]
        session_dir = write_session(
            tmp_path,
            state={
                "config": {
                    "fixerVendor": "cursor",
                    "baseGuard": RC.BASE_GUARD_CHECKED,
                    "headSha": HEAD_SHA,
                },
                "terminal": "converged",
                "step": "terminal",
            },
            journal_lines=journal_lines,
            envelopes=envelopes,
        )
        receipt, refusal = RC.certify(session_dir)
        assert refusal is None, refusal
        audit_seats = receipt["independence"]["auditSeats"]
>       assert audit_seats[0]["model"] == engine_model
E       AssertionError: assert None == 'gemini-3.8-flash-high'

plugins/superheroes/lib/tests/test_layer4a_ruling_evidence_1272.py:513: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_layer4a_ruling_evidence_1272.py::test_receipt_audit_seat_model_equals_runner_engine_model
1 failed in 0.63s
```

**Restore (quoted restored lines):**

```python
        model = _runner_recorded_model(obs, ctx["session_dir"], seat_entry)
```

**Green:**

```
.                                                                        [100%]
1 passed in 0.60s
```
