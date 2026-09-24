# layer4a uncertified seats bite-proof (issue #1272, WO-C2)

Re-taken at head 3b1ee864 (plus this order's changes).

| ID | guarded element | proving test |
|---|---|---|
| C1 | channel condition (`channel == "file"`) | `test_l4a_edge4_engine_stdout_without_telemetry_refuses` |
| C2 | manifest-sha verification in `_verified_orders_manifest` | `test_l4a_edge6_tampered_manifest_sha_refuses` |
| C3 | post-loop exclusion floor (`_exclusion_floor_refusal`) | `test_l4a_exclusion_floor_census[no_panel_verifiers-phase_specs0-True]` |
| C4 | `uncertifiedSeats` list check in `_validate_receipt_additions` | `test_l4a_edge11_absent_uncertified_seats_refuses` |
| C5 | `certifiedPanel` bool check | `test_l4a_edge11_non_bool_certified_panel_refuses` |
| C6 | `auditSeats[].model` check | `test_l4a_edge11_bad_audit_model_refuses` |
| C7 | hand-landed `qualified.append` (defect-1 fix) | `test_l4a_t_floor_hand_landed_qualifying_panel_plus_host_uncertified_no_refusal` |
| C8 | copied seat-map rows (defect-2 fix) | `test_l4a_t_nomutate_build_receipt_does_not_mutate_state_seat_map_rows` |
| C9 | `certifiedPanel` provenance label | `test_l4a_seat_map_injected_keys_provenance_census` |
| C10 | binding condition (`binding == "execution-evidence-absent"`) | `test_l4a_edge10b_host_present_evidence_wrong_head_refuses` |

## C1 — channel condition

**Axis:** only `file` channel seats without telemetry are named uncertified; `stdout` must refuse.

**Guarded code:** `round_certification.check_unrun_review`

**Neutralization:**

```python
if phase not in (P_AUDITS, P_FIXER) and channel in ("file", "stdout"):
```

**Detector:** `test_l4a_edge4_engine_stdout_without_telemetry_refuses`

**Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
____________ test_l4a_edge4_engine_stdout_without_telemetry_refuses ____________

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-5345/test_l4a_edge4_engine_stdout_w0')

    def test_l4a_edge4_engine_stdout_without_telemetry_refuses(tmp_path):
        seat = "code-reviewer"
        row = _dispatch_observed_no_telemetry_row(seat, RP.P_PANEL)
        session_dir, _ = _session_with_manifest(
            tmp_path,
            seat=seat,
            phase=RP.P_PANEL,
            channel="stdout",
            vendor="codex",
            journal_lines=[row],
            envelopes=[{"seat": seat, "payloadSha256": DEFAULT_PANEL_PAYLOAD_SHA}],
        )
        ctx, err = RC._load_context(session_dir)
        assert err is None
        refusal = RC.check_unrun_review(ctx)
        assert refusal is not None
        assert refusal["class"] == "unrun-review"
>       assert refusal["artifact"] == seat
E       AssertionError: assert 'driver-journal.jsonl' == 'code-reviewer'
E         
E         - code-reviewer
E         + driver-journal.jsonl

plugins/superheroes/lib/tests/test_layer4a_uncertified_seats_1272.py:252: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_layer4a_uncertified_seats_1272.py::test_l4a_edge4_engine_stdout_without_telemetry_refuses
1 failed in 0.18s
```

**Restore (quoted restored lines):**

```python
if phase not in (P_AUDITS, P_FIXER) and channel == "file":
```

**Green:**

```
.                                                                        [100%]
1 passed in 0.16s
```

## C2 — manifest-sha verification

**Axis:** tampered manifest sha must refuse before channel classification.

**Guarded code:** `round_certification._verified_orders_manifest`

**Neutralization:**

```python
if False:
```

**Detector:** `test_l4a_edge6_tampered_manifest_sha_refuses`

**Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_________________ test_l4a_edge6_tampered_manifest_sha_refuses _________________

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-5348/test_l4a_edge6_tampered_manife0')

    def test_l4a_edge6_tampered_manifest_sha_refuses(tmp_path):
        seat = "code-reviewer"
        row = _dispatch_observed_no_telemetry_row(seat, RP.P_PANEL)
        session_dir, manifest = _session_with_manifest(
            tmp_path,
            seat=seat,
            phase=RP.P_PANEL,
            channel="file",
            vendor="claude",
            journal_lines=[row],
            envelopes=[{"seat": seat, "payloadSha256": DEFAULT_PANEL_PAYLOAD_SHA}],
        )
        manifest["seats"][record_paths.storage_key(seat, 0)]["vendor"] = "tampered"
        _write_orders_manifest(session_dir, manifest)
        ctx, err = RC._load_context(session_dir)
        assert err is None
        refusal = RC.check_unrun_review(ctx)
        assert refusal is not None
        assert refusal["class"] == "unrun-review"
>       assert refusal["artifact"] == seat
E       AssertionError: assert 'driver-journal.jsonl' == 'code-reviewer'
E         
E         - code-reviewer
E         + driver-journal.jsonl

plugins/superheroes/lib/tests/test_layer4a_uncertified_seats_1272.py:312: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_layer4a_uncertified_seats_1272.py::test_l4a_edge6_tampered_manifest_sha_refuses
1 failed in 0.19s
```

**Restore (quoted restored lines):**

```python
if computed_sha != manifest_sha:
```

**Green:**

```
.                                                                        [100%]
1 passed in 0.17s
```

## C3 — post-loop exclusion floor

**Axis:** when exclusions exist but no runner-evidenced panel seat qualified, floor refuses.

**Guarded code:** `round_certification._exclusion_floor_refusal` (branch 2: no qualified panel seat)

**Neutralization:**

```python
if False and not any(q.get("phase") == PANEL_PHASE for q in qualified):
```

**Detector:** `test_l4a_exclusion_floor_census[no_panel_verifiers-phase_specs0-True]`

**Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
____ test_l4a_exclusion_floor_census[no_panel_verifiers-phase_specs0-True] _____

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-5639/test_l4a_exclusion_floor_censu0')
case_id = 'no_panel_verifiers'
phase_specs = {'dispatch-verifiers': [{'channel': 'file', 'row': {'attempt': 0, 'cmd': 'record-result', 'occurrence': 0, 'outcome': 'recorded', ...}, 'seat': 'verifier-seat', 'vendor': 'claude'}]}
expect_refusal = True

    def test_l4a_exclusion_floor_census(tmp_path, case_id, phase_specs, expect_refusal):
        session_dir = _multi_phase_session(tmp_path, phase_specs)
        ctx, err = RC._load_context(session_dir)
        assert err is None
        refusal = RC.check_unrun_review(ctx)
        if expect_refusal:
>           assert refusal is not None
E           assert None is not None

plugins/superheroes/lib/tests/test_layer4a_uncertified_seats_1272.py:602: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_layer4a_uncertified_seats_1272.py::test_l4a_exclusion_floor_census[no_panel_verifiers-phase_specs0-True]
1 failed in 1.29s
```

**Restore (quoted restored lines):**

```python
if not any(q.get("phase") == PANEL_PHASE for q in qualified):
```

**Green:**

```
.                                                                        [100%]
1 passed in 1.20s
```

## C4 — uncertifiedSeats list check

**Axis:** absent `uncertifiedSeats` field must refuse.

**Guarded code:** `round_certification._validate_receipt_additions`

**Neutralization:**

```python
if False and not isinstance(uncertified, list):
```

**Detector:** `test_l4a_edge11_absent_uncertified_seats_refuses`

**Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_______________ test_l4a_edge11_absent_uncertified_seats_refuses _______________

    def test_l4a_edge11_absent_uncertified_seats_refuses():
        receipt = _minimal_valid_receipt()
        receipt["disclosures"].pop("uncertifiedSeats")
>       refusal = RC._validate_receipt_additions(receipt)

plugins/superheroes/lib/tests/test_layer4a_uncertified_seats_1272.py:540: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

receipt = {'disclosures': {'importantOutOfScope': []}, 'independence': {'auditSeats': []}, 'seatMap': {'seats': {'code-reviewer': {'vendor': 'claude'}}}}

    def _validate_receipt_additions(receipt):
        disclosures = receipt.get("disclosures")
        if not isinstance(disclosures, dict):
            return _refusal(
                "unfetched-findings",
                STATE_FILE,
                "certified receipt disclosures must be an object",
            )
        uncertified = disclosures.get("uncertifiedSeats")
        if False and not isinstance(uncertified, list):
            return _refusal(
                "unfetched-findings",
                STATE_FILE,
                "certified receipt disclosures.uncertifiedSeats must be a list",
            )
>       for row in uncertified:
E       TypeError: 'NoneType' object is not iterable

plugins/superheroes/lib/round_certification.py:2050: TypeError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_layer4a_uncertified_seats_1272.py::test_l4a_edge11_absent_uncertified_seats_refuses
1 failed in 0.19s
```

**Restore (quoted restored lines):**

```python
if not isinstance(uncertified, list):
```

**Green:**

```
.                                                                        [100%]
1 passed in 0.15s
```

## C5 — certifiedPanel bool check

**Axis:** non-bool `certifiedPanel` must refuse.

**Guarded code:** `round_certification._validate_receipt_additions`

**Neutralization:**

```python
if False and certified_panel is not None and not isinstance(certified_panel, bool):
```

**Detector:** `test_l4a_edge11_non_bool_certified_panel_refuses`

**Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_______________ test_l4a_edge11_non_bool_certified_panel_refuses _______________

    def test_l4a_edge11_non_bool_certified_panel_refuses():
        receipt = _minimal_valid_receipt()
        receipt["seatMap"]["seats"]["code-reviewer"]["certifiedPanel"] = "yes"
        refusal = RC._validate_receipt_additions(receipt)
>       assert refusal is not None
E       assert None is not None

plugins/superheroes/lib/tests/test_layer4a_uncertified_seats_1272.py:549: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_layer4a_uncertified_seats_1272.py::test_l4a_edge11_non_bool_certified_panel_refuses
1 failed in 0.18s
```

**Restore (quoted restored lines):**

```python
if certified_panel is not None and not isinstance(certified_panel, bool):
```

**Green:**

```
.                                                                        [100%]
1 passed in 0.16s
```

## C6 — auditSeats model check

**Axis:** empty-string audit model must refuse.

**Guarded code:** `round_certification._validate_receipt_additions`

**Neutralization:**

```python
if False and (not isinstance(model, str) or not model):
```

**Detector:** `test_l4a_edge11_bad_audit_model_refuses`

**Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
___________________ test_l4a_edge11_bad_audit_model_refuses ____________________

    def test_l4a_edge11_bad_audit_model_refuses():
        receipt = _minimal_valid_receipt()
        receipt["independence"]["auditSeats"] = [{"seat": "t1", "model": ""}]
        refusal = RC._validate_receipt_additions(receipt)
>       assert refusal is not None
E       assert None is not None

plugins/superheroes/lib/tests/test_layer4a_uncertified_seats_1272.py:557: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_layer4a_uncertified_seats_1272.py::test_l4a_edge11_bad_audit_model_refuses
1 failed in 0.20s
```

**Restore (quoted restored lines):**

```python
if not isinstance(model, str) or not model:
```

**Green:**

```
.                                                                        [100%]
1 passed in 0.17s
```

## C7 — hand-landed qualified.append (defect-1 fix)

**Axis:** qualifying hand-landed panel seat satisfies the panel floor.

**Guarded code:** `round_certification.check_unrun_review` (hand-landed arm)

**Neutralization:**

```python
pass  # C7 neutralized — skip qualified.append
```

**Detector:** `test_l4a_t_floor_hand_landed_qualifying_panel_plus_host_uncertified_no_refusal`

**Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_l4a_t_floor_hand_landed_qualifying_panel_plus_host_uncertified_no_refusal _

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-5363/test_l4a_t_floor_hand_landed_q0')

    def test_l4a_t_floor_hand_landed_qualifying_panel_plus_host_uncertified_no_refusal(tmp_path):
        session_dir, host_seat = _panel_hand_landed_plus_host_uncertified_session(tmp_path)
        ctx, err = RC._load_context(session_dir)
        assert err is None
        refusal = RC.check_unrun_review(ctx)
>       assert refusal is None
E       AssertionError: assert {'artifact': 'driver-journal.jsonl', 'bindingFailure': None, 'class': 'unrun-review', 'detail': 'no recorded dispatch-panel seat carries runner evidence; every panel seat was host-channel'} is None

plugins/superheroes/lib/tests/test_layer4a_uncertified_seats_1272.py:482: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_layer4a_uncertified_seats_1272.py::test_l4a_t_floor_hand_landed_qualifying_panel_plus_host_uncertified_no_refusal
1 failed in 0.26s
```

**Restore (quoted restored lines):**

```python
qualified.append(seat_entry)
```

**Green:**

```
.                                                                        [100%]
1 passed in 0.22s
```

## C8 — copied seat-map rows (defect-2 fix)

**Axis:** `_build_receipt` must not mutate state seat-map receipt rows.

**Guarded code:** `round_certification._build_receipt`

**Neutralization:**

```python
for seat_name, row in seat_map_seats.items():
    if isinstance(row, dict):
        row["certifiedPanel"] = seat_name not in uncertified_panel_seats
```

**Detector:** `test_l4a_t_nomutate_build_receipt_does_not_mutate_state_seat_map_rows`

**Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
____ test_l4a_t_nomutate_build_receipt_does_not_mutate_state_seat_map_rows _____

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-5368/test_l4a_t_nomutate_build_rece0')

    def test_l4a_t_nomutate_build_receipt_does_not_mutate_state_seat_map_rows(tmp_path):
        session_dir = _panel_host_uncertified_session(tmp_path)
        ctx, err = RC._load_context(session_dir)
        assert err is None
        state = ctx["state"]
        state["seatMapReceipts"] = [{
            "round": "1",
            "map": {
                "seats": {
                    "code-reviewer": {"vendor": "claude", "model": "sonnet"},
                    "security-reviewer": {"vendor": "codex", "model": "gpt"},
                },
            },
        }]
        assert RC.check_unrun_review(ctx) is None
        receipt, refusal = RC._build_receipt(ctx, "certified", None)
        assert refusal is None
        assert receipt is not None
        for entry in state.get("seatMapReceipts") or []:
            seats = (entry.get("map") or {}).get("seats") or {}
            for row in seats.values():
                if isinstance(row, dict):
>                   assert "certifiedPanel" not in row
E                   AssertionError: assert 'certifiedPanel' not in {'certifiedPanel': False, 'model': 'sonnet', 'vendor': 'claude'}

plugins/superheroes/lib/tests/test_layer4a_uncertified_seats_1272.py:515: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_layer4a_uncertified_seats_1272.py::test_l4a_t_nomutate_build_receipt_does_not_mutate_state_seat_map_rows
1 failed in 0.25s
```

**Restore (quoted restored lines):**

```python
receipt["seatMap"]["seats"] = {
    seat_name: (
        dict(row, certifiedPanel=seat_name not in uncertified_panel_seats)
        if isinstance(row, dict)
        else row
    )
    for seat_name, row in seat_map_seats.items()
}
```

**Green:**

```
.                                                                        [100%]
1 passed in 0.21s
```

## C9 — certifiedPanel provenance label

**Axis:** every key the writer injects into a seat-map row must be named in `provenanceLabels.derived` as `seatMap.seats.*.<key>`.

**Guarded code:** `round_certification._build_receipt` (`provenanceLabels.derived` includes `CERTIFIED_PANEL_LABEL`)

**Neutralization:**

```python
                "independence",
            ],
```

(removes `CERTIFIED_PANEL_LABEL` from the `derived` list)

**Detector:** `test_l4a_seat_map_injected_keys_provenance_census`

**Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
______________ test_l4a_seat_map_injected_keys_provenance_census _______________

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-5671/test_l4a_seat_map_injected_key0')

    def test_l4a_seat_map_injected_keys_provenance_census(tmp_path):
        session_dir = _panel_host_uncertified_session(tmp_path)
        ctx, err = RC._load_context(session_dir)
        assert err is None
        state = ctx["state"]
        state["seatMapReceipts"] = [{
            "round": "1",
            "map": {
                "seats": {
                    "code-reviewer": {"vendor": "claude", "model": "sonnet"},
                    "security-reviewer": {"vendor": "codex", "model": "gpt"},
                },
            },
        }]
        source_seats = {}
        for entry in state["seatMapReceipts"]:
            seats = (entry.get("map") or {}).get("seats") or {}
            source_seats.update(seats)
        receipt, refusal = RC._build_receipt(ctx, "certified", None)
        assert refusal is None
        derived = receipt["provenanceLabels"]["derived"]
>       assert RC.CERTIFIED_PANEL_LABEL in derived
E       AssertionError: assert 'seatMap.seats.*.certifiedPanel' in ['schemaVersion', 'scriptRan', 'terminalState', 'terminalCause', 'seats', 'disclosures', ...]
E        +  where 'seatMap.seats.*.certifiedPanel' = RC.CERTIFIED_PANEL_LABEL

tests/test_layer4a_uncertified_seats_1272.py:329: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_layer4a_uncertified_seats_1272.py::test_l4a_seat_map_injected_keys_provenance_census
1 failed in 0.25s
```

**Restore (quoted restored lines):**

```python
                "independence",
                CERTIFIED_PANEL_LABEL,
            ],
```

**Green:**

```
.                                                                        [100%]
1 passed in 0.33s
```
