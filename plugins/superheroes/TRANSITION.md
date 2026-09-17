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

Every dispatch result carries `runOpened`. When `runOpened` is true the result also carries a
`resolvedInputs` snapshot (with a `resolvedInputsStatus` of `pre-upgrade` or `journal-corrupt` when
the snapshot could not be read from the journal). Each snapshot value is paired with a source marker
that says whether the run took the value from the caller, a default, a clamp, or the registry.
Refusals raised before the run opened carry `runOpened: false` and no snapshot.

Results no longer carry a `ledger` key. Preflight refusals return to the caller in the result body
like every other refusal.

Entry refusals now carry an additive `entryReason` key naming which entry check refused, from the
dispatch shell's closed entry vocabulary, with `entry-reason-undeclared` as its fall-back when a
refusal's own token was outside that vocabulary. **`reason` is unchanged for entry refusals** — it
stays `unrunnable`, and the outcome vocabulary gains no member, so no consumer comparing `reason`
against a hard-coded set needs to change. The presence of `entryReason` marks a refusal raised at
the entry surface; a later preflight refusal carries `reason: unrunnable` and no `entryReason`.

An `engine_adapter build-argv` invocation that refuses now **exits non-zero**; it previously wrote
its refusal payload and exited 0. A caller that read the exit code as success must now read it as
the refusal it always was.

### Composition-liveness cache

The default lifetime for a composition-liveness receipt is 3600 seconds. Set
`SUPERHEROES_LIVENESS_TTL_SECONDS` to configure the lifetime ceiling; a receipt expires at the
shorter of its stamped TTL and that value.

### Registered consumers

**weekly-eats write dispatches** omit effort today. After this release they must pass `--seat` as the
four-key JSON object on every write dispatch, with vendor, model, effort, and role supplied inside
the seat bundle.
