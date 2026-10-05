# WO-1273-l3b-B bite-proof — codex role pins and host-model families

**Provenance:** cursor / composer-2.5 (implementer).

## Guarded elements

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| BP-B1 | `_cell` role-pin branch | honored pin seats codex at pinned model | `test_codex_role_pin_astra_registered_seats_at_high` |
| BP-B2 | `_resolve_at_tier` not-live fallback | pin not live falls back to matrix | `test_codex_role_pin_astra_not_live_falls_back_to_matrix` |
| BP-B3 | `main` host-model-unknown | unknown host → None family + degradation | `test_cli_compose_host_model_unknown_degrades` |

---

## BP-B1 — role-pin branch in `_cell`

- **axis:** honored codex role pin replaces matrix cell for seating

**neutralization** (`plugins/superheroes/lib/seat_map.py`, `_cell`): always return the matrix cell (ignore role pins).

```python
    cell = matrix_config(tier, vendor)
    if cell is None:
        return None, None, None
    return cell[0], cell[1], None
```

**command:** `plugins/superheroes/lib/tests/test_seat_map.py::test_codex_role_pin_astra_registered_seats_at_high`

**raw red** (exit 1): FAILED `test_codex_role_pin_astra_registered_seats_at_high`

**restore:** reinstate the role-pin branch at the top of `_cell`.

**raw green** (exit 0): 1 passed

---

## BP-B2 — not-live fallback in `_resolve_at_tier`

- **axis:** role-pinned cell not live falls back to matrix with disclosure

**neutralization** (`plugins/superheroes/lib/seat_map.py`, `_resolve_at_tier`): seat the pin even when not live (skip fallback).

```python
        if pin_info and pin_info.get("honored"):
            source = "role-pinned"
```

(remove the not-live fallback block)

**command:** `plugins/superheroes/lib/tests/test_seat_map.py::test_codex_role_pin_astra_not_live_falls_back_to_matrix`

**raw red** (exit 1): FAILED `test_codex_role_pin_astra_not_live_falls_back_to_matrix`

**restore:** reinstate the not-live fallback block.

**raw green** (exit 0): 1 passed

---

## BP-B3 — host-model-unknown degradation

- **axis:** unknown host model → None families + one degradation (not anthropic default)

**neutralization** (`plugins/superheroes/lib/seat_map.py`, `main`): default unknown host family to `"anthropic"`.

```python
            host_fam = model_registry.host_family(host_model) or "anthropic"
```

**command:** `plugins/superheroes/lib/tests/test_seat_map.py::test_cli_compose_host_model_unknown_degrades`

**raw red** (exit 1): FAILED `test_cli_compose_host_model_unknown_degrades`

**restore:** `host_fam = model_registry.host_family(host_model)` without the `or "anthropic"` fallback.

**raw green** (exit 0): 1 passed
