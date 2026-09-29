# #1540 bite-proof — GPT-6.1 Sol registration, effort list and Codex CLI floor

Per-element bite-proof for the detectors WO-1 adds in `plugins/superheroes/lib/tests/test_model_registry.py` (N1, N2) and `plugins/superheroes/lib/tests/test_preflight_probe.py` (N3). Each element was neutralized by one targeted edit in `plugins/superheroes/lib/model_registry.py`; the named node ran alone (`scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest <node id> -q -p no:xdist -p no:cacheprovider`), then the edit was reverted by the inverse edit and the node re-run green. The detectors were unedited throughout.

## WO-1

### B1 — the `efforts` tuple refuses `none`

- Guarded element and axis: the `gpt-6.1-sol` `efforts` tuple in `_MODELS["codex"]`; an effort outside the published list is refused.
- Node: `plugins/superheroes/lib/tests/test_model_registry.py::test_gpt61_sol_refuses_effort_none_and_accepts_its_published_efforts` (N2).
- Neutralization: `"efforts": ("low", "medium", "high", "xhigh", "max"),` -> `"efforts": ("none", "low", "medium", "high", "xhigh", "max"),`
- Red:
```
    def test_gpt61_sol_refuses_effort_none_and_accepts_its_published_efforts():
        ok, reason = MR.validate_config("codex", "gpt-6.1-sol", "none")
>       assert ok is False
E       assert True is False
1 failed in 1.48s
```
- Restore: inverse edit. Restore receipt (line 38): `            "efforts": ("low", "medium", "high", "xhigh", "max"),`
- Green: `.  [100%]` / `1 passed in 0.22s`

### B2 — the floor literal

- Guarded element and axis: `gpt-6.1-sol` `min_cli`; a 0.158.0 CLI must be refused.
- Node: `plugins/superheroes/lib/tests/test_preflight_probe.py::test_codex_cli_floor_probe_gpt61_sol_floor_literal` (N3).
- Neutralization: `"min_cli": "0.159.0",` -> `"min_cli": "0.158.0",`
- Red:
```
>       assert pp.codex_cli_floor_probe(run=_run_below)["detail"] == (
E       TypeError: 'NoneType' object is not subscriptable
1 failed in 0.32s
```
- Restore: inverse edit. Restore receipt (line 37): `            "min_cli": "0.159.0",`
- Green: `.  [100%]` / `1 passed in 0.26s`

### B3 — the at-floor acceptance

- Guarded element and axis: `gpt-6.1-sol` `min_cli`; the floor value itself, spelled as the literal `0.159.0` in the refusal detail.
- Node: same as B2 (N3).
- Neutralization: `"min_cli": "0.159.0",` -> `"min_cli": "0.159.1",`
- Red (disclosure: it fires on the first assertion, the refusal-detail literal, not on the `codex-cli 0.159.0` at-floor leg, which is never reached):
```
E       AssertionError: assert 'codex-cli-to...59.1 or later' == 'codex-cli-to...59.0 or later'
E         - han 0.159.0, the minimum for gpt-6.1-sol; upgrade the Codex CLI to 0.159.0 or later
E         + han 0.159.1, the minimum for gpt-6.1-sol; upgrade the Codex CLI to 0.159.1 or later
1 failed in 0.28s
```
- Restore: inverse edit. Restore receipt (line 37): `            "min_cli": "0.159.0",`
- Green: `.  [100%]` / `1 passed in 0.26s`

### B4 — the probe-pending gate

- Guarded element and axis: the `"registration": "probe-pending",` line on the `gpt-6.1-sol` row; the pin path must refuse with `pin-probe-pending:`.
- Node: `plugins/superheroes/lib/tests/test_model_registry.py::test_gpt61_sol_probe_pending_reaches_only_the_registration_probe_role` (N1).
- Neutralization: delete `            "registration": "probe-pending",`
- Red:
```
>       assert reason.startswith("pin-probe-pending:")
E        +    where False = <built-in method startswith of str object at 0x105b40850>('pin-probe-pending:')
E        +    where <built-in method startswith of str object at 0x105b40850> = 'pin-not-on-allowlist: gpt-6.1-sol is not on the reviewer codex allowlist [(gpt-6-sol, high), (gpt-6-sol, xhigh), (gpt-6-astra, high), (gpt-5.6-sol, high)]'.startswith
1 failed in 0.18s
```
- Restore: inverse edit. Restore receipt (line 39): `            "registration": "probe-pending",`
- Green: `.  [100%]` / `1 passed in 0.18s`

## WO-2

Same procedure as WO-1 (single node, `-p no:xdist -p no:cacheprovider`, targeted edit in `model_registry.py`, inverse edit, re-run green). Detectors unedited throughout.

### G1 — A9 on matrix cells

- Guarded element and axis: `_MATRIX["reviewer"]["codex"]`; no default matrix cell names a pin-only model.
- Node: `plugins/superheroes/lib/tests/test_model_registry.py::test_i1_no_default_surface_names_a_retired_or_pin_only_model`
- Neutralization: `"codex": ("gpt-6.1-sol", "high"),` (reviewer) -> `"codex": ("gpt-6-sol", "high"),`
- Red:
```
>                   assert cell[0] not in banned, (role, vendor, cell)
E                   AssertionError: ('reviewer', 'codex', ('gpt-6-sol', 'high'))
E                   assert 'gpt-6-sol' not in {'gpt-5.6-sol', 'gpt-5.6-terra', 'gpt-6-sol'}
1 failed in 0.61s
```
- Restore: inverse edit. Restore receipt (line 119): `        "codex": ("gpt-6.1-sol", "high"),`
- Green: `.  [100%]` / `1 passed in 26.35s`

### G2 — A9 on ladder rungs

- Guarded element and axis: first `_LADDERS["codex"]` rung; no raw ladder rung names a pin-only model.
- Node: same as G1.
- Neutralization: `("gpt-6.1-sol", "high"),` (first codex rung) -> `("gpt-6-sol", "high"),`
- Red:
```
>           assert model_id not in banned, model_id
E           AssertionError: gpt-6-sol
E           assert 'gpt-6-sol' not in {'gpt-5.6-sol', 'gpt-5.6-terra', 'gpt-6-sol'}
1 failed in 1.57s
```
- Restore: inverse edit. Restore receipt (line 91): `        ("gpt-6.1-sol", "high"),`
- Green: `.  [100%]` / `1 passed in 0.34s`

### G3 — A9 on peers

- Guarded element and axis: `_CODEX_PEER_BY_CLAUDE["opus"]`; no peer value names a pin-only model.
- Node: same as G1.
- Neutralization: `"opus": "gpt-6.1-sol",` -> `"opus": "gpt-6-sol",`
- Red:
```
>           assert peer not in banned, peer
E           AssertionError: gpt-6-sol
E           assert 'gpt-6-sol' not in {'gpt-5.6-sol', 'gpt-5.6-terra', 'gpt-6-sol'}
1 failed in 0.51s
```
- Restore: inverse edit. Restore receipt (line 322): `    "opus": "gpt-6.1-sol",`
- Green: `.  [100%]` / `1 passed in 0.36s`

### G4 — the `gpt-6-sol` pin (R2)

- Guarded element and axis: the `"pin_only": True,` line on the `gpt-6-sol` row; a `gpt-6-sol` pin stays resolvable.
- Node: `plugins/superheroes/lib/tests/test_model_registry.py::test_gpt6_sol_pin_resolves_at_each_codex_pin_roles_cell_effort` (N4).
- Neutralization: delete `            "pin_only": True,` from the `gpt-6-sol` row.
- Red:
```
>       assert MR.pin_only_models("codex") == ("gpt-5.6-sol", "gpt-6-sol")
E       AssertionError: assert ('gpt-5.6-sol',) == ('gpt-5.6-sol', 'gpt-6-sol')
E         Right contains one more item: 'gpt-6-sol'
1 failed in 0.43s
```
- Restore: inverse edit (line re-inserted after `min_cli`). Restore receipt (lines 31-32): `            "min_cli": "0.157.0",` / `            "pin_only": True,`
- Green: `.  [100%]` / `1 passed in 0.31s`

### G5 — the at-floor acceptance

- Guarded element and axis: `gpt-6.1-sol` `min_cli`; a `codex-cli 0.159.0` CLI is accepted.
- Node: `plugins/superheroes/lib/tests/test_preflight_probe.py::test_codex_cli_floor_probe_accepts_0_159_0_at_the_gpt61_sol_floor` (A16).
- Neutralization: `"min_cli": "0.159.0",` -> `"min_cli": "0.159.1",`
- Red:
```
>       assert pp.codex_cli_floor_probe(run=_run_at) is None
E       AssertionError: assert {'tool': 'cross-vendor-cli:codex', 'ok': False, 'exit': 0, 'detail': 'codex-cli-too-old: codex-cli 0.159.0 is older than 0.159.1, the minimum for gpt-6.1-sol; upgrade the Codex CLI to 0.159.1 or later'} is None
1 failed in 0.64s
```
- Restore: inverse edit. Restore receipt (line 38): `            "min_cli": "0.159.0",`
- Green: `.  [100%]` / `1 passed in 0.50s`

### G6 — the Terra replacement (R6)

- Guarded element and axis: the `_RETIRED_MODELS` replacement value; the retired refusal names `gpt-6.1-sol`.
- Node: `plugins/superheroes/lib/tests/test_model_registry.py::test_i2_retired_terra_refused_by_validate_config_and_pin_verdict`
- Neutralization: `{"codex": {"gpt-5.6-terra": "gpt-6.1-sol"}}` -> `{"codex": {"gpt-5.6-terra": "gpt-6-sol"}}`
- Red:
```
>           assert reason == _RETIRED_TERRA_REASON
E           AssertionError: assert 'model-retire...use gpt-6-sol' == 'model-retire...e gpt-6.1-sol'
E             -  use gpt-6.1-sol
E             +  use gpt-6-sol
1 failed in 0.40s
```
- Restore: inverse edit. Restore receipt (line 74): `_RETIRED_MODELS: dict[str, dict[str, str]] = {"codex": {"gpt-5.6-terra": "gpt-6.1-sol"}}`
- Green: `.  [100%]` / `1 passed in 0.38s`
