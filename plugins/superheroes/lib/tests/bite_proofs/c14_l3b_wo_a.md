# WO-1273-l3b-A bite-proof — Astra registry and codex pin gate

**Provenance:** cursor / composer-2.5 (implementer).

## Guarded elements

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| BP-A1 | `ladder()` probe-pending filter | pending models hidden from allowlist readers | `test_pending_astra_hidden_from_allowlist_but_probe_role_admits` |
| BP-A2 | `codex_pin_verdict` probe-pending refusal | pending model pin refused before allowlist | `test_codex_pin_verdict_pending_astra_on_reviewer_deep` |
| BP-A3 | `codex_pin_verdict` `pin_roles` refusal | role outside pin_roles refused | `test_codex_pin_verdict_astra_on_reviewer_refused_pin_role` |

---

## BP-A1 — pending filter in `ladder()`

- **axis:** probe-pending models removed from ladder-derived allowlists

**neutralization** (`plugins/superheroes/lib/model_registry.py`, `ladder`):
```python
def ladder(vendor: str) -> tuple[tuple[str, str | None], ...]:
    return _LADDERS.get(vendor, ())  # bite-proof BP-A1 neutralization
```

**command:** `plugins/superheroes/lib/tests/test_model_registry.py::test_pending_astra_hidden_from_allowlist_but_probe_role_admits`

**raw red** (exit 1):
```
FAILED plugins/superheroes/lib/tests/test_model_registry.py::test_pending_astra_hidden_from_allowlist_but_probe_role_admits
1 failed in 2.87s
```

**restore** (`plugins/superheroes/lib/model_registry.py`, `ladder`):
```python
def ladder(vendor: str) -> tuple[tuple[str, str | None], ...]:
    raw = _LADDERS.get(vendor, ())
    out: list[tuple[str, str | None]] = []
    for model_id, effort in raw:
        rec = _MODELS.get(vendor, {}).get(model_id, {})
        if rec.get("registration") == "probe-pending":
            continue
        out.append((model_id, effort))
    return tuple(out)
```

**raw green** (exit 0):
```
1 passed in 2.07s
```

---

## BP-A2 — probe-pending refusal in `codex_pin_verdict`

- **axis:** probe-pending row refused as pin before other checks

**neutralization** (`plugins/superheroes/lib/model_registry.py`, `codex_pin_verdict`): remove the `registration == "probe-pending"` branch.

**command:** `plugins/superheroes/lib/tests/test_model_registry.py::test_codex_pin_verdict_pending_astra_on_reviewer_deep`

**raw red** (exit 1):
```
FAILED plugins/superheroes/lib/tests/test_model_registry.py::test_codex_pin_verdict_pending_astra_on_reviewer_deep
1 failed in 1.44s
```

**restore:** reinstate the `probe-pending` branch in `codex_pin_verdict`.

**raw green** (exit 0):
```
1 passed in 2.38s
```

---

## BP-A3 — `pin_roles` refusal in `codex_pin_verdict`

- **axis:** model pin refused when role not in row `pin_roles`

**neutralization** (`plugins/superheroes/lib/model_registry.py`, `codex_pin_verdict`): remove the `pin_roles` eligibility branch.

**command:** `plugins/superheroes/lib/tests/test_model_registry.py::test_codex_pin_verdict_astra_on_reviewer_refused_pin_role`

**raw red** (exit 1):
```
FAILED plugins/superheroes/lib/tests/test_model_registry.py::test_codex_pin_verdict_astra_on_reviewer_refused_pin_role
1 failed in 2.03s
```

**restore:** reinstate the `pin_roles` eligibility branch in `codex_pin_verdict`.

**raw green** (exit 0):
```
1 passed in 2.09s
```
