# WO 1273-l3b2-V bite-proofs — one pin design (registry verdict + composer)

**Provenance:** cursor / composer-2.5 (implementer).

## Guarded elements

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| BP-V1 | `codex_pin_verdict` allowlist leg | judge must refuse pins off the role allowlist | `test_pin_judges_agree_writer_guard_and_composer[today]` |
| BP-V2 | `seat_map._cell` verdict gate | composer must ask the judge before honoring a pin | `test_pin_judges_agree_writer_guard_and_composer[post-pass]` |
| BP-V3 | `dispatch_allowlist.validate` model resolution | guard must judge the caller's model, not the seat default | `test_pin_judges_agree_writer_guard_and_composer[today]` |

---

## BP-V1 — registry judge's allowlist leg

- **axis:** Terra on `reviewer-deep` accepted by the judge, refused by the guard

**neutralization** (`plugins/superheroes/lib/model_registry.py`, `codex_pin_verdict`):
```python
    if False and not resolved.get("ok"):  # bite-proof BP-V1
```

**command:** `plugins/superheroes/lib/tests/test_model_registry.py::test_pin_judges_agree_writer_guard_and_composer` (both params)

**raw red** (exit 1):
```
FAILED plugins/superheroes/lib/tests/test_model_registry.py::test_pin_judges_agree_writer_guard_and_composer[today]
>                   assert ok == guard_accepts
E                   assert True == False
FAILED plugins/superheroes/lib/tests/test_model_registry.py::test_pin_judges_agree_writer_guard_and_composer[post-pass]
>                   assert ok == guard_accepts
E                   assert True == False
2 failed in 0.15s
```

**restore** (`plugins/superheroes/lib/model_registry.py`, `codex_pin_verdict`):
```python
    if not resolved.get("ok"):
```

**raw green** (exit 0): `2 passed in 0.12s`

---

## BP-V2 — composer asks the judge

- **axis:** post-pass — Astra on `reviewer` honored by `_cell` while the judge refuses it (`pin-role-not-eligible`)

**neutralization** (`plugins/superheroes/lib/seat_map.py`, `_cell`):
```python
        ok, _reason = True, None  # bite-proof BP-V2
```

**command:** `plugins/superheroes/lib/tests/test_model_registry.py::test_pin_judges_agree_writer_guard_and_composer` (both params)

**raw red** (exit 1):
```
FAILED plugins/superheroes/lib/tests/test_model_registry.py::test_pin_judges_agree_writer_guard_and_composer[post-pass]
>                   assert info["honored"] == ok
E                   assert True == False
1 failed, 1 passed in 0.13s
```

**restore** (`plugins/superheroes/lib/seat_map.py`, `_cell`):
```python
        ok, _reason = model_registry.codex_pin_verdict(tier, pin)
```

**raw green** (exit 0): `2 passed in 0.12s`

---

## BP-V3 — the guard judges the caller's model

- **axis:** today — the guard accepts Terra on `reviewer-deep` while the judge refuses it

**neutralization** (`plugins/superheroes/lib/dispatch_allowlist.py`, `validate`):
```python
    resolved = model_registry.resolve_dispatch(role, vendor, None, None)  # bite-proof BP-V3
```

**command:** `plugins/superheroes/lib/tests/test_model_registry.py::test_pin_judges_agree_writer_guard_and_composer[today]`

**raw red** (exit 1):
```
FAILED plugins/superheroes/lib/tests/test_model_registry.py::test_pin_judges_agree_writer_guard_and_composer[today]
>                   assert ok == guard_accepts
E                   assert False == True
1 failed in 0.13s
```

**restore** (`plugins/superheroes/lib/dispatch_allowlist.py`, `validate`):
```python
    resolved = model_registry.resolve_dispatch(role, vendor, model, effort)
```

**raw green** (exit 0): `2 passed in 0.12s`
