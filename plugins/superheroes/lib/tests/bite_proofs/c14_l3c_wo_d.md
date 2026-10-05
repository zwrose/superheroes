# C14 layer 3c WO-D — bite-proofs

**Covers:** WO-1273-l3c-D (codex role pins in family check + receipt; v12 dead-loop removal).

## Guarded elements

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| BP-D1 | `_resolvable_families_for_seat` probed branch `_cell(..., pin_arg)` | probed family check reads codex cells through `codexRolePins` | `test_resolvable_families_reads_codex_role_pin` |
| BP-D2 | `_read_codex_role_pins` validation | malformed `codexRolePins` makes evidence unusable (`None`), never raises | `test_resolvable_families_malformed_role_pins_unusable` |
| BP-D3 | `build()` `codexRolePins` emission | key present only when pins are non-empty | `test_build_records_codex_role_pins_only_when_present` |
| BP-D4 | `to_receipt()` `codexRolePins` copy | compose receipt carries pins for downstream family check | `test_compose_receipt_carries_codex_role_pins` |

**v12:** pure deletion in `round_governing_unjudgeable` — no new detector, no bite-proof owed. Behaviour pinned by:
`test_round_governing_unjudgeable_seeded_round_zero_receipt`,
`test_round_governing_unjudgeable_legacy_prepend_then_empty_seats_receipt`,
`test_round_governing_unjudgeable_config_fallback_without_receipts`,
`test_round_governing_unjudgeable_last_receipt_wins_same_round_label`,
`test_round_governing_unjudgeable_return_shape_complete_vs_one_element`,
`test_round_governing_unjudgeable_own_submission_wins_over_effective_map`.

---

## BP-D1 — probed branch uses role pins

- **axis:** probed family check resolves codex cells through `codexRolePins` on the seat map

**neutralization** (`plugins/superheroes/lib/seat_map.py`, probed-cells loop — the `if cells_source == liveness_cache.LIVE_CELLS_SOURCE_PROBED:` branch, not the synthesized branch below it):

before:
```python
            model, effort, pin_info = _cell(tier, vendor, pin_arg)
```

after:
```python
            model, effort, pin_info = _cell(tier, vendor, None)
```

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-l3c-D -m pytest plugins/superheroes/lib/tests/test_seat_map.py::test_resolvable_families_reads_codex_role_pin -q -p no:xdist
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
________________ test_resolvable_families_reads_codex_role_pin _________________
...
>       assert "openai" in fams
E       AssertionError: assert 'openai' in {'anthropic'}
```

**restore:** reinstate `_cell(tier, vendor, pin_arg)` in the probed-cells loop.

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.18s
```

---

## BP-D2 — malformed pins unusable

- **axis:** malformed `codexRolePins` makes family evidence unusable without raising

**neutralization** (`plugins/superheroes/lib/seat_map.py`, `_read_codex_role_pins` body after absent check):

before: full role/pin validation loop

after:
```python
    return (raw if isinstance(raw, dict) else None, True)
```

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-l3c-D -m pytest plugins/superheroes/lib/tests/test_seat_map.py::test_resolvable_families_malformed_role_pins_unusable -q -p no:xdist
```

**raw red** (exit 1): 4 failed — each case `assert ... is None` failed with returned set `{'anthropic', 'openai', 'xai'}` (non-dict, unknown-role, empty-value, non-string-value).

**restore:** reinstate full validation in `_read_codex_role_pins`.

**raw green** (exit 0):
```
....                                                                     [100%]
4 passed in 0.16s
```

---

## BP-D3 — build omits empty pins key

- **axis:** `build` omits `codexRolePins` when no pins are configured

**neutralization** (`plugins/superheroes/lib/seat_map.py`, `build()` result assembly):

before:
```python
    if role_pins:
        result["codexRolePins"] = dict(role_pins)
```

after:
```python
    result["codexRolePins"] = dict(role_pins)
```

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-l3c-D -m pytest plugins/superheroes/lib/tests/test_seat_map.py::test_build_records_codex_role_pins_only_when_present -q -p no:xdist
```

**raw red** (exit 1):
```
>       assert "codexRolePins" not in without
E       AssertionError: assert 'codexRolePins' not in {..., 'codexRolePins': {}, ...}
```

**restore:** reinstate `if role_pins:` guard.

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.24s
```

---

## BP-D4 — to_receipt carries pins

- **axis:** compose receipt carries `codexRolePins` and family check reads it back

**neutralization** (`plugins/superheroes/lib/seat_map.py`, `to_receipt` tail): remove the `codexRolePins` copy block.

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-l3c-D -m pytest plugins/superheroes/lib/tests/test_seat_map.py::test_compose_receipt_carries_codex_role_pins -q -p no:xdist
```

**raw red** (exit 1):
```
>       assert receipt["codexRolePins"] == {"reviewer-deep": "gpt-6-astra"}
E       KeyError: 'codexRolePins'
```

**restore:** reinstate `role_pins, pins_usable = _read_codex_role_pins(seat_map)` copy block.

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 3.40s
```
