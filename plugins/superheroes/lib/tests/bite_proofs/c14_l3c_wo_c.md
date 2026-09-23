# C14 layer 3c WO-C — bite-proofs

**Provenance:** cursor / composer-2.5 (implementer).

## Guarded elements

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| BP-C1 | `CLAUDE_ALIAS_RESOLUTION["resolved"]["opus"]` pairing | alias drift guard ties registry id to served harness model | `test_claude_alias_resolution_record_matches_registry_ids` |
| BP-C2 | `round_driver._auditor_vendor` role read | independence follows auditor role family, not verifier | `test_auditor_vendor_reads_auditor_role` |
| BP-C3 | `_MATRIX["auditor"]` derivation | auditor row tracks verifier cells | `test_auditor_cells_track_verifier_cells` |
| BP-C4 | `_PRE_CHILD_HEAD` git-baseline loader | missing commit fails closed with fetch-depth guidance | `test_matrix_cells_reviewer_roles_unchanged_at_base` |
| BP-C5 | absence of translation at continuation/spawn chokepoints | legacy journaled claude label refused at continuation | `test_continuation_refuses_legacy_claude_label_mismatch` |
| BP-C6 | `seat_map.normalize_pins` admission | legacy model ids pass through without rewriting | `test_normalize_pins_preserves_legacy_claude_label` |
| BP-C7 | `validate_config` on legacy ids | legacy ids stay unregistered | `test_legacy_claude_model_ids_stay_unregistered` |

---

## BP-C1

- **axis:** alias drift guard ties registry id to served harness model

**neutralization** (`plugins/superheroes/lib/model_registry.py`):
```python
        "opus": "claude-opus-5",
```

**raw red** (exit 1):
```
E           AssertionError: ('opus-5.5', 'claude-opus-5', 'claude-opus-5-5')
```

**restore:**
```python
        "opus": "claude-opus-5-5",
```

**raw green** (exit 0): `1 passed in 0.12s`

---

## BP-C2

- **axis:** independence follows auditor role family, not verifier

**neutralization** (`plugins/superheroes/lib/round_driver.py`):
```python
            cand_fam = model_registry.family_for("verifier", v)
```

**raw red** (exit 1):
```
E       AssertionError: assert 'degraded' == 'independent'
```

**restore:**
```python
            cand_fam = model_registry.family_for("auditor", v)
```

**raw green** (exit 0): `1 passed in 0.74s`

---

## BP-C3

- **axis:** auditor row tracks verifier cells

**neutralization** (`plugins/superheroes/lib/model_registry.py`):
```python
_MATRIX["auditor"] = {
    "claude": _MATRIX["verifier"]["claude"],
    "codex": ("gpt-5.6-sol", "xhigh"),
    "cursor": _MATRIX["verifier"]["cursor"],
}
```

**raw red** (exit 1):
```
E           AssertionError: assert ('gpt-5.6-sol', 'xhigh') == ('gpt-5.6-sol', 'high')
```

**restore:**
```python
_MATRIX["auditor"] = dict(_MATRIX["verifier"])
```

**raw green** (exit 0): `1 passed in 0.16s`

---

## BP-C4

- **axis:** missing commit fails closed with fetch-depth guidance

**neutralization** (`plugins/superheroes/lib/tests/test_model_registry.py`):
```python
_PRE_CHILD_HEAD = "0000000000000000000000000000000000000000"
```

**raw red** (exit 1):
```
E           AssertionError: commit 0000000000000000000000000000000000000000 is not available in this checkout — fetch full history (fetch-depth: 0) to run the git-baseline test
```

**restore:**
```python
_PRE_CHILD_HEAD = "aaf27b8089159c2ea4020b03ccbddcd263c57e8a"
```

**raw green** (exit 0): baseline test passes with real sha.

---

## BP-C5

- **axis:** legacy journaled claude label refused at continuation (no translation at chokepoints)
- **superseded at `7f548494` by BP-C5** — prior entry proved translation; this entry proves its absence.

**neutralization** (`plugins/superheroes/lib/engine_dispatch.py` — re-add translation in `_continuation_seat_tuple`):
```python
    if isinstance(vendor, str) and isinstance(model, str):
        _LEGACY = {"claude": {"opus-5": "opus-5.5", "fable-5": "fable-5.1"}}
        model = _LEGACY.get(vendor, {}).get(model, model)
```

**raw red** (exit 1):
```
E       AssertionError: assert None == 'run-dir-seat-mismatch'
```

**restore:** removed translation from `_continuation_seat_tuple`.

**raw green** (exit 0): `1 passed in 0.19s`

---

## BP-C6

- **axis:** legacy model ids pass through pin normalization without rewriting

**neutralization** (`plugins/superheroes/lib/seat_map.py` — re-add `current_model_id` in `normalize_pins`)

**raw red** (exit 1):
```
E       AssertionError: assert 'opus-5.5' == 'opus-5'
```

**restore:** removed `current_model_id` translation from `normalize_pins`.

**raw green** (exit 0): `1 passed in 0.19s`

---

## BP-C7

- **axis:** legacy ids stay unregistered (green only)

**raw green** (exit 0): `1 passed in 0.13s`
