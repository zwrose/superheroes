# WO-cont-A (#1247) bite-proof — distinct canary non-pass channels per round

**Provenance:** cursor-agent / composer-2.5

## Guarded elements

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| BP-cont-A1 | `test_canary_dead_and_outcome_failed_same_round_both_disclosed` | two distinct canary non-pass conditions in one round are both disclosed (neither overwrites the other) | `test_canary_dead_and_outcome_failed_same_round_both_disclosed` |

---

## BP-cont-A1 — separate `canaryOutcomeFailed` channel

- **axis:** two distinct canary non-pass conditions in one round are both disclosed (neither overwrites the other)

**neutralization** (revert step 2 — point outcome-failed `_record_round` back at `canaryFailed`):
```python
        _record_round(state, "canaryFailed", cof_rec)
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
________ test_canary_dead_and_outcome_failed_same_round_both_disclosed _________

    def test_canary_dead_and_outcome_failed_same_round_both_disclosed():
        # axis: two distinct canary non-pass conditions in one round are both disclosed
        """One vendor dead and another outcome-failed record separate per-round channels."""
        state = RD.new_state(_cfg(leg="panel"))
        seats = {d: {"findings": []} for d in RD.DIMENSIONS}
        seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
        seat_map["seats"]["code-reviewer"] = {"vendor": "codex"}
        seat_map["seats"]["security-reviewer"] = {"vendor": "cursor"}
        canary = [
            {
                "engine": "codex", "model": "gpt", "outcome": "vacuous", "engaged": False,
                "evidence": {"tokens": 0}, "detectedPlant": False, "detail": "no engagement",
            },
            {
                "engine": "cursor", "model": "c", "outcome": "vacuous", "engaged": True,
                "evidence": {"tokens": 50000, "toolCalls": 30}, "detectedPlant": False,
                "detail": "vacuous seat",
            },
        ]
        RD._fold_panel(state, state["config"], {
            "seats": seats, "seatMap": seat_map, "canaryResult": canary,
        })
        r1 = state["rounds"]["1"]
        assert "canaryFailed" in r1
>       assert "canaryOutcomeFailed" in r1
E       AssertionError: assert 'canaryOutcomeFailed' in {'canaryFailed': {'detail': 'vacuous seat', 'engagedFailure': True, 'evidence': {'tokens': 50000, 'toolCalls': 30}, 's... [], 'fellOpenProvenanceMissing': ['security-reviewer'], 'lensCoverage': {'expected': 5, 'floor': True, 'ran': 4}, ...}

plugins/superheroes/lib/tests/test_round_driver.py:6400: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_round_driver.py::test_canary_dead_and_outcome_failed_same_round_both_disclosed
1 failed, 456 deselected in 1.19s
```

**restore:** reinstate `_record_round(state, "canaryOutcomeFailed", cof_rec)`.

**restore receipt:**
```
 M plugins/superheroes/lib/round_driver.py
```

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed, 456 deselected in 1.05s
```
