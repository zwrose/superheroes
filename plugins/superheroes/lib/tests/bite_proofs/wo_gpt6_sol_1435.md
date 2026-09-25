# #1435 bite-proof — the gpt-6-sol default, the retired Terra refusal, the pin-only 5.6 Sol, and the Codex CLI floor

Per-element bite-proof for the detectors this change adds (`plugins/superheroes/lib/model_registry.py`, `plugins/superheroes/lib/engine_pref.py`, `plugins/superheroes/lib/preflight_probe.py`). For each element, the production code was neutralized with one targeted edit through the host's edit action. The named test ran alone and went red on the guarded axis, then the edit was reverted with the inverse edit. The detectors were unedited throughout.

**Guarded-element set (declared in the build brief):** (1) a Terra pin or config refuses `model-retired` naming `gpt-6-sol`; (2) no default cell, rung or peer names Terra or 5.6 Sol; (3) a 5.6 Sol pin resolves (reviewer-deep at xhigh); (4) the pin-only append stays off the ladder and the defaults; (5) a Codex CLI below the registry floor refuses `codex-cli-too-old` at the preflight and at composition. Element 1 has four independently neutralizable sites (E1a–E1d). Element 5 has four (E5a–E5d).

**Head proven:** `2f775ace`, the final head. The proofs ran in a detached probe worktree at that commit, separate from the build worktree. After the last revert, `git status --porcelain` was empty and HEAD read `2f775ace`.

**Provenance:** the orchestrator ran these proofs (workhorse, Claude Opus 5.5), not an implementer.

**Command:** each red run used the exact node id below, never `-k`:

```
scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc-bite -m pytest <node id> -q -p no:xdist
```

Test files: `R` = `plugins/superheroes/lib/tests/test_model_registry.py`, `E` = `plugins/superheroes/lib/tests/test_engine_pref.py`, `P` = `plugins/superheroes/lib/tests/test_preflight_probe.py`.

## Summary

| ID | Guarded element (file:line at `2f775ace`) | Neutralization | Proving node(s) | Exact red |
|---|---|---|---|---|
| E1a | model_registry.py:453 `validate_config` retired check | `retired_reason = None` | `R::test_i2_retired_terra_refused_by_validate_config_and_pin_verdict` | `- model-retired: gpt-5.6-terra is retired; use gpt-6-sol` / `+ model 'gpt-5.6-terra' is not registered for vendor 'codex'` |
| E1b | model_registry.py:613 `codex_pin_verdict` retired check | `retired_reason = None` | `R::test_i2_retired_terra_refused_by_validate_config_and_pin_verdict` | `- model-retired: gpt-5.6-terra is retired; use gpt-6-sol` / `+ unknown model 'gpt-5.6-terra' rejected` |
| E1c | model_registry.py:916 `resolve_dispatch` explicit-model retired check | `retired_reason = None` | `R::test_i2_retired_terra_direct_dispatch_named_not_generic_park`, `R::test_i2_retired_terra_named_even_on_a_role_with_no_sanctioned_model` | `+ model 'gpt-5.6-terra' is not on the reviewer/codex allowlist [...]`; `+ role 'pilot' has no sanctioned model on vendor 'codex'` (both against `- model-retired: ...`) |
| E1d | engine_pref.py:205 `normalize_seat_pin_map` codex retired check | `retired_reason = None` | `E::test_normalize_seat_pin_map_refuses_retired_codex_model` | `Left contains 1 more item: {'security-reviewer': {'model': 'gpt-5.6-terra', 'vendor': 'codex'}}` |
| E2 | model_registry.py:101 a default codex cell | `code-fixer` codex cell → `("gpt-5.6-sol", "high")` | `R::test_i1_no_default_surface_names_a_retired_or_pin_only_model` | `AssertionError: ('code-fixer', 'codex', ('gpt-5.6-sol', 'high'))` / `assert 'gpt-5.6-sol' not in {'gpt-5.6-sol', 'gpt-5.6-terra'}` |
| E3 | model_registry.py:720 `_append_codex_pin_only` | `return` as the first statement | `R::test_i3_reviewer_deep_pin_sol_resolves_xhigh_others_resolve_high` | `assert (False, 'pin-...stra, high)]') == (True, None)` |
| E4 | model_registry.py `_LADDERS["codex"]` | added rung `("gpt-5.6-sol", "high")` | `R::test_i3_pin_only_absent_from_ladder_matrix_cells_and_escalate` | `assert False` / `where False = all(<generator ...>)` |
| E5a | preflight_probe.py:167 floor comparison | `return None` before the comparison | `P::test_codex_cli_floor_probe_below_floor_refused` | `assert None is not None` |
| E5b | preflight_probe.py:209 preflight seat (`cross_vendor_cli_probe`) | `floor_refusal = None` | `P::test_cross_vendor_cli_probe_codex_below_floor_refuses_without_exec` | `'the exec no-op must not run when the floor gate refuses'.startswith('codex-cli-too-old:')` → `False` |
| E5c | preflight_probe.py:544 composition seat (`composition_liveness`) | floor observation → `None` | `P::test_composition_liveness_codex_below_floor_all_cells_refused_without_per_cell_probe` | `assert True is False` |
| E5d | preflight_probe.py:606 cache seat (`live_vendors_for_composition`) | `codex_floor_refusal = None` | `P::test_live_vendors_for_composition_cache_bypassed_when_codex_cli_drops_below_floor` | `assert 'codex' not in ['claude', 'codex']` |

Every red names the axis: the retired reason is replaced by a generic one (E1a–E1d), a default surface names a banned model (E2, E4), the pin stops resolving (E3), and a below-floor CLI stops being refused (E5a–E5d).

**External-contract literal:** the refusal reason is pinned as the spelled-out literal `model-retired: gpt-5.6-terra is retired; use gpt-6-sol` in `R` and `E` (never read back through `retired_model_reason`). The floor refusal token is pinned as the literal prefix `codex-cli-too-old:` in `P`.

**Neutralization overlap disclosed:** E1c and E1d were neutralized together, and each was run against its own node. They sit on independent paths (`resolve_dispatch` never calls the seat-pin normalizer, and the normalizer never calls `resolve_dispatch`), so neither red depends on the other edit. All other elements were neutralized alone.

## Restore receipt

After the last inverse edit, `git status --porcelain` in the probe worktree was empty and `git rev-parse --short HEAD` read `2f775ace`.

## Green

All eleven proving nodes, run together after the restore (`-v -p no:xdist`):

```
test_model_registry.py::test_i2_retired_terra_refused_by_validate_config_and_pin_verdict PASSED
test_model_registry.py::test_i2_retired_terra_direct_dispatch_named_not_generic_park PASSED
test_model_registry.py::test_i2_retired_terra_named_even_on_a_role_with_no_sanctioned_model PASSED
test_engine_pref.py::test_normalize_seat_pin_map_refuses_retired_codex_model PASSED
test_model_registry.py::test_i1_no_default_surface_names_a_retired_or_pin_only_model PASSED
test_model_registry.py::test_i3_reviewer_deep_pin_sol_resolves_xhigh_others_resolve_high PASSED
test_model_registry.py::test_i3_pin_only_absent_from_ladder_matrix_cells_and_escalate PASSED
test_preflight_probe.py::test_codex_cli_floor_probe_below_floor_refused PASSED
test_preflight_probe.py::test_cross_vendor_cli_probe_codex_below_floor_refuses_without_exec PASSED
test_preflight_probe.py::test_composition_liveness_codex_below_floor_all_cells_refused_without_per_cell_probe PASSED
test_preflight_probe.py::test_live_vendors_for_composition_cache_bypassed_when_codex_cli_drops_below_floor PASSED
11 passed in 1.32s
```

Nothing was redacted; the captures contain no secrets, tokens, private URLs or personal data.
