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
