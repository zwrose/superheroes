# C14 layer 3b review round 5 — bite proofs (#1273 WO-R5B)

| ID | Guarded element | Axis | Detector |
|----|-----------------|------|----------|
| BP-R5B-1 | `seat_map.main` unknown-host narrative family | claude-host fallback for narrative | `test_cli_compose_host_model_unknown_cursor_impl_degrades` |
| BP-R5B-2 | `seat_map.main` liveness_pin_scoped | seat pins only scope liveness | `test_compose_role_pin_without_seat_pins_liveness_not_scoped` |
| BP-R5B-3 | `seat_map.main` invalidCodexModels read | load-time refusal disclosed | `test_compose_invalid_codex_role_pin_disclosed` |
| BP-R5B-4 | `test_ssot_drift` registry-independent id pattern | retired id in doc fails drift | `test_complete_codex_policy_single_sourced` |

## BP-R5B-1

- **neutralization:** `narrative_family = host_fam` (removed `or claude_host_fam` fallback).
- **red:** `test_cli_compose_host_model_unknown_cursor_impl_degrades` — `AssertionError: assert None == 'anthropic'`.
- **restore:** `narrative_family = host_fam or claude_host_fam`.
- **green:** `1 passed in 0.46s`.

## BP-R5B-2

- **neutralization:** `liveness_pin_scoped = needed_override is not None`.
- **red:** `test_compose_role_pin_without_seat_pins_liveness_not_scoped` — `assert True is False`.
- **restore:** `liveness_pin_scoped = bool(pins)`.
- **green:** `1 passed in 62.23s`.

## BP-R5B-3

- **neutralization:** removed `invalidCodexModels` read block in compose.
- **red:** `test_compose_invalid_codex_role_pin_disclosed` — `assert 0 == 1`.
- **restore:** invalidCodexModels block re-added after `codex_role_pins` load.
- **green:** `1 passed in 6.89s`.

## BP-R5B-4

- **neutralization:** appended `gpt-5.5-luna` to `view-and-tune.md` Codex tier paragraph.
- **red:** `test_complete_codex_policy_single_sourced` — `Extra items in the left set: 'gpt-5.5-luna'`.
- **restore:** removed `gpt-5.5-luna` from paragraph.
- **green:** `1 passed in 2.17s`.
