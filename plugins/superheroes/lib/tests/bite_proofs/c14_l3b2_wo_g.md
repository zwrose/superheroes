# WO 1273-l3b2-G bite-proofs — probe-pending gate machinery

**Provenance:** cursor / composer-2.5 (implementer).

## Guarded elements

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| BP-G1 | `codex_pin_verdict` probe-pending leg | planted probe-pending model refused as pin | `test_codex_pin_verdict_planted_pending_astra_on_reviewer_deep` |
| BP-G2 | `ladder()` probe-pending skip | planted probe-pending model hidden from ladder | `test_planted_probe_pending_astra_hidden_from_ladder_and_allowlist` |

---

## BP-G1 — the pin verdict's probe-pending leg

- **axis:** planted probe-pending model refused as pin with `pin-probe-pending:`

**neutralization** (`plugins/superheroes/lib/model_registry.py`, `codex_pin_verdict`):
```python
    if False and rec.get("registration") == "probe-pending":  # bite-proof BP-G1
```

**command:** `plugins/superheroes/lib/tests/test_model_registry.py::test_codex_pin_verdict_planted_pending_astra_on_reviewer_deep`

**raw red** (exit 1):
```
>       assert reason.startswith("pin-probe-pending:")
E       AssertionError: assert False
E        +  where False = <built-in method startswith of str object at 0x106adcf30>('pin-probe-pending:')
E        +    where <built-in method startswith of str object at 0x106adcf30> = 'pin-not-on-allowlist: gpt-6-astra is not on the reviewer-deep codex allowlist [(gpt-5.6-sol, xhigh)]'.startswith
```

**restore** (`plugins/superheroes/lib/model_registry.py`, `codex_pin_verdict`):
```python
    if rec.get("registration") == "probe-pending":
```

**raw green** (exit 0): `1 passed`

---

## BP-G2 — the ladder's probe-pending skip

- **axis:** planted probe-pending model absent from `ladder("codex")`

**neutralization** (`plugins/superheroes/lib/model_registry.py`, `ladder`):
```python
        if False and rec.get("registration") == "probe-pending":  # bite-proof BP-G2
```

**command:** `plugins/superheroes/lib/tests/test_model_registry.py::test_planted_probe_pending_astra_hidden_from_ladder_and_allowlist`

**raw red** (exit 1):
```
>       assert ("gpt-6-astra", "high") not in MR.ladder("codex")
E       AssertionError: assert ('gpt-6-astra', 'high') not in (('gpt-5.6-terra', 'high'), ('gpt-5.6-sol', 'high'), ('gpt-5.6-sol', 'xhigh'), ('gpt-6-astra', 'high'))
```

**restore** (`plugins/superheroes/lib/model_registry.py`, `ladder`):
```python
        if rec.get("registration") == "probe-pending":
```

**raw green** (exit 0): `1 passed`
