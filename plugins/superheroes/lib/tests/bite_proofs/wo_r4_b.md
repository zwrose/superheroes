# WO-R4-B bite-proof record

## BP-R4-B1 — malformed audit id validation

**Guarded element:** `_audit_ruling_payload_valid` / `_matches_review_ruling` id validation via `round_adapters.P_AUDITS`.

**Neutralization:** set `_audit_ruling_payload_valid` to `return True` and revert `_matches_review_ruling` to presence-only id check.

**Red run** (`test_parse_result_review_ruling_invalid_id_unreadable`):
```
FFFFF                                                                    [100%]
=================================== FAILURES ===================================
_________ test_parse_result_review_ruling_invalid_id_unreadable[None] __________

bad_id = None

    @pytest.mark.parametrize("bad_id", [None, "", "   ", 42, {}])
    def test_parse_result_review_ruling_invalid_id_unreadable(bad_id):
        stdout = json.dumps({"id": bad_id, "ruling": "discharged", "reason": "ok"})
>       assert EA.parse_result("codex", "review", stdout) == {"ok": False, "reason": "unreadable"}
E       AssertionError: assert {'investigate...'discharged'}} == {'ok': False,... 'unreadable'}
E         
E         Differing items:
E         {'ok': True} != {'ok': False}
E         Left contains 3 more items:
E         {'investigated': [],
E          'resultKind': 'ruling',
E          'ruling': {'id': None, 'reason': 'ok', 'ruling': 'discharged'}}...
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_adapter.py::test_parse_result_review_ruling_invalid_id_unreadable[None]
FAILED plugins/superheroes/lib/tests/test_engine_adapter.py::test_parse_result_review_ruling_invalid_id_unreadable[]
FAILED plugins/superheroes/lib/tests/test_engine_adapter.py::test_parse_result_review_ruling_invalid_id_unreadable[   ]
FAILED plugins/superheroes/lib/tests/test_engine_adapter.py::test_parse_result_review_ruling_invalid_id_unreadable[42]
FAILED plugins/superheroes/lib/tests/test_engine_adapter.py::test_parse_result_review_ruling_invalid_id_unreadable[bad_id4]
5 failed in 0.23s
```

**Restore:** reinstate `audit_id.strip()` guard and `round_adapters.payload_fault(P_AUDITS, obj, "")`; restore `_matches_review_ruling` delegation.

**Restore confirmation (`git status --porcelain` for `engine_adapter.py`):** only the three owned files modified (no stray neutralization left in `engine_adapter.py`).

**Green run:**
```
.....                                                                    [100%]
5 passed in 0.23s
```

---

## BP-R4-B2 — grouping contract delegation

**Guarded element:** `_grouping_payload_valid` delegation to `round_adapters.P_SYNTHESIS`.

**Neutralization:** restore hand-written `member_ids` loop in `_grouping_payload_valid`.

**Red run** (`test_grouping_payload_valid_delegates_to_round_adapters_not_hand_copy`):
```
F                                                                        [100%]
=================================== FAILURES ===================================
____ test_grouping_payload_valid_delegates_to_round_adapters_not_hand_copy _____

    def test_grouping_payload_valid_delegates_to_round_adapters_not_hand_copy():
        """§11: engine_adapter._grouping_payload_valid must delegate to round_adapters P_SYNTHESIS."""
        text = _read("lib/engine_adapter.py")
        assert "round_adapters.payload_fault" in text
>       assert "round_adapters.P_SYNTHESIS" in text
E       assert 'round_adapters.P_SYNTHESIS' in '...engine_adapter.py...'
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_ssot_drift.py::test_grouping_payload_valid_delegates_to_round_adapters_not_hand_copy
1 failed in 0.23s
```

**Restore:** replace hand copy with `round_adapters.payload_fault(round_adapters.P_SYNTHESIS, {"grouping": grouping}, round_adapters.SEAT_SYNTHESIS)`.

**Green run:**
```
.                                                                        [100%]
1 passed in 0.13s
```

---

## BP-R4-B3 — grouping envelope gate payload

**Guarded element:** `_parse_review_grouping_object` passes parsed `grouping` to `_outer_envelope_error_makes_unreadable`.

**Neutralization:** change envelope call to `_outer_envelope_error_makes_unreadable(outer_envelope_error, [])`.

**Red run** (`test_review_result_kind_populated_survives_outer_envelope_error[grouping]`):
```
F                                                                        [100%]
=================================== FAILURES ===================================
__ test_review_result_kind_populated_survives_outer_envelope_error[grouping] ___

kind = 'grouping'

    @pytest.mark.parametrize("kind", EA.REVIEW_RESULT_KINDS)
    def test_review_result_kind_populated_survives_outer_envelope_error(kind):
        """Populated payloads survive the #949 outer-envelope gate for every registered kind."""
        inner = json.dumps(_REVIEW_KIND_POPULATED_ENVELOPE_PAYLOADS[kind])
        stream = _envelope(inner, subtype="error", is_error=True)
        res = EA.parse_result("cursor", "review", stream)
>       assert res["ok"] is True
E       assert False is True
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_adapter.py::test_review_result_kind_populated_survives_outer_envelope_error[grouping]
1 failed in 0.24s
```

**Restore:** `_outer_envelope_error_makes_unreadable(outer_envelope_error, grouping)`.

**Green run:**
```
.                                                                        [100%]
1 passed in 0.21s
```

---

## BP-R4-B4 — grouping secret scrub

**Guarded element:** `_scrub_grouping` applied before returning grouping payload.

**Neutralization:** return raw `grouping` instead of `grouping_scrubbed`.

**Red run** (`test_review_result_kinds_scrub_known_secret[grouping]`):
```
F                                                                        [100%]
=================================== FAILURES ===================================
____________ test_review_result_kinds_scrub_known_secret[grouping] _____________

kind = 'grouping'

    @pytest.mark.parametrize("kind", EA.REVIEW_RESULT_KINDS)
    def test_review_result_kinds_scrub_known_secret(kind):
        """Every registered review kind routes payload strings through the scrub seam."""
        res = EA.parse_result("codex", "review", json.dumps(_REVIEW_KIND_SECRET_PAYLOADS[kind]))
        assert res["ok"] is True
>       assert _REVIEW_SECRET not in json.dumps(res)
E       assert 'sk-EXAMPLEf...arealsecret0' not in '{"ok": true...igated": []}'
E         
E         'sk-EXAMPLEfakenotarealsecret0' is contained here:
E           n: Bearer sk-EXAMPLEfakenotarealsecret0"}], "investigated": []}
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_adapter.py::test_review_result_kinds_scrub_known_secret[grouping]
1 failed in 0.24s
```

**Restore:** `grouping`: `grouping_scrubbed` in result dict.

**Green run:**
```
.                                                                        [100%]
1 passed in 0.23s
```
