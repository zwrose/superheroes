# Transition notes

This file records consumer-visible shape changes across superheroes releases. Read it before you
upgrade a caller that invokes dispatch CLIs, reads dispatch results, or depends on a result key.

Add a section when a release drops, renames, or newly requires an argument, a result key, or a
result shape a consumer depends on. Put the newest release first. Each section names the release it
belongs to and lists every change with its replacement.

## Unreleased

### Dispatch CLI arguments

On `engine_dispatch dispatch-review`, `engine_dispatch dispatch-write`, and `dispatch_guard check`:

**Dropped (no alias window).** Pass a seat bundle and role instead.

| Dropped flag | Replacement |
| --- | --- |
| `--engine` | `--seat` (vendor lives inside the seat bundle) |
| `--model` | `--seat` |
| `--effort` | `--seat` |
| `--engine-model` | `--seat` (model and effort resolve from the bundle) |
| `--vendor` | `--seat` (vendor lives inside the seat bundle) |
| `--role` | `--seat` (role now rides inside the seat bundle `"role"` key) |
| bare composed-token `--seat` (`"<vendor>:<dispatch-token>"`) | `--seat` as a four-key JSON object; the `model` field still accepts the composed dispatch-token spelling inside JSON |

**Newly required.**

- `--seat` — pass as JSON object `{"vendor": "<vendor>", "model": "<id>|null", "effort": <str|null>, "role": "<role>"}` (the `effort` key is required and its value may be null; `role` is required and must not be null). Valid roles: implementer, code-fixer, doc-reviser, reviewer, reviewer-deep, verifier, brief-check, synthesis, mechanical, pilot.

If you pass a dropped flag, the dispatch refuses immediately. The refusal names the replacement and
the accepted `--seat` shape. There is no silent fallback and no alias window for dropped forms.

### Dispatch result shape

Every dispatch result now carries a `resolvedInputs` snapshot. Each input value is paired with a
source marker that says whether the run took the value from the caller, a default, a clamp, or the
registry.

Results no longer carry a `ledger` key. Preflight refusals return to the caller in the result body
like every other refusal.

### Composition-liveness cache

The default lifetime for a composition-liveness receipt is 3600 seconds. Override with the
`SUPERHEROES_LIVENESS_TTL_SECONDS` environment variable when you need a different TTL.

### Registered consumers

**weekly-eats write dispatches** omit effort today. After this release they must pass `--seat` as the
four-key JSON object on every write dispatch, with vendor, model, effort, and role supplied inside
the seat bundle.
