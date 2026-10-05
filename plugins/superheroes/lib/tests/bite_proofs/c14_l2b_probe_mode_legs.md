# C14 layer 2b (#1273 WO-4) bite-proof — conformance probe mode legs

**Provenance:** implementer WO-4 / `lib/conformance_probe.py` `_validate_probe_record` + `_payload`

## Guarded elements

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| G1 | `_validate_probe_record` probedModes vs modeLegs keys | key-set equality | `test_payload_writer_probed_modes_matches_mode_legs_keys` |
| G2 | `_validate_probe_record` modeLegs leg-name set | exactly `_LEG_NAMES` per mode | `test_payload_writer_mode_legs_carry_all_leg_names` |

---

## G1 — probedModes / modeLegs key-set equality

- **axis:** `probedModes` key set must equal `modeLegs` key set

**neutralization** (`conformance_probe.py`, `_payload`):
```python
    probed_modes_out = ["print"]
```
(replaces `"probedModes": list(probed_modes)` with `"probedModes": probed_modes_out` while `modeLegs` still carries both `print` and `background`)

**raw red:** `test_payload_writer_probed_modes_matches_mode_legs_keys`
```
F                                                                        [100%]
=================================== FAILURES ===================================
___________ test_payload_writer_probed_modes_matches_mode_legs_keys ____________

    def test_payload_writer_probed_modes_matches_mode_legs_keys():
        seat = _claude_seat()
        mode_legs = {"print": _ok_legs(), "background": _ok_legs()}
        payload = CP._payload(
            "claude", ERC.channel_for("claude"), seat, "/repo",
            "2026-09-20T00:00:00Z", "2026-09-20T00:00:01Z", 1.0, "/tmp/run",
            mode_legs, ["print", "background"], [], "lanes",
        )
>       assert CP._validate_probe_record(payload, "/tmp/claude.json") is None
E       AssertionError: assert 'probe-result-malformed:/tmp/claude.json' is None
E        +  where 'probe-result-malformed:/tmp/claude.json' = <function _validate_probe_record at 0x105024b80>({'channel': 'native', 'completedAt': '2026-09-20T00:00:01Z', 'dependentLanes': 'lanes', 'dependentRoles': [], ...}, '/tmp/claude.json')
E        +    where <function _validate_probe_record at 0x105024b80> = CP._validate_probe_record

plugins/superheroes/lib/tests/test_conformance_probe.py:1382: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_conformance_probe.py::test_payload_writer_probed_modes_matches_mode_legs_keys
1 failed in 0.35s
```

**restore:** remove `probed_modes_out = ["print"]` and restore `"probedModes": list(probed_modes)`.

**raw green:** `test_payload_writer_probed_modes_matches_mode_legs_keys`
```
.                                                                        [100%]
1 passed in 0.47s
```

---

## G2 — modeLegs carries all three leg names

- **axis:** each `modeLegs` entry must have exactly `resultProduction`, `completionDetection`, `progressTelemetry`

**neutralization** (`conformance_probe.py`, `_payload`):
```python
    mode_legs = {
        mode: {name: legs[name] for name in _LEG_NAMES if name != "progressTelemetry"}
        for mode, legs in mode_legs.items()
    }
```
(inserted before `_derive_flat_legs(mode_legs)`)

**raw red:** `test_payload_writer_mode_legs_carry_all_leg_names`
```
F                                                                        [100%]
=================================== FAILURES ===================================
______________ test_payload_writer_mode_legs_carry_all_leg_names _______________

    def test_payload_writer_mode_legs_carry_all_leg_names():
        seat = _claude_seat()
        mode_legs = {"print": _ok_legs(), "background": _ok_legs()}
        payload = CP._payload(
            "claude", ERC.channel_for("claude"), seat, "/repo",
            "2026-09-20T00:00:00Z", "2026-09-20T00:00:01Z", 1.0, "/tmp/run",
            mode_legs, ["print", "background"], [], "lanes",
        )
        for mode in ("print", "background"):
>           assert set(payload["modeLegs"][mode].keys()) == set(CP._LEG_NAMES)
E           AssertionError: assert {'completionD...ltProduction'} == {'completionD...ltProduction'}
E             
E             Extra items in the right set:
E             'progressTelemetry'
E             Use -v to get more diff

plugins/superheroes/lib/tests/test_conformance_probe.py:1401: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_conformance_probe.py::test_payload_writer_mode_legs_carry_all_leg_names
1 failed in 0.60s
```

**restore:** remove the `mode_legs = { ... if name != "progressTelemetry" ...}` rewrite block.

**raw green:** `test_payload_writer_mode_legs_carry_all_leg_names`
```
.                                                                        [100%]
1 passed in 0.65s
```
