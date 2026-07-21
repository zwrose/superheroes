# Guardian lens contract

A **lens** is a registered module that implements the five contract parts below. The authoritative part slugs live in `guardian_lens.LENS_CONTRACT_PARTS`. Real lenses register in `guardian_lens.REGISTRY` via `register()` after `validate_lens()` passes.

**Hard rule:** a lens PR must carry **hands-on receipts from a real repo** — measured collector output, a baseline diff, and a validated consequence on that repo. A lens proposed from a tool's README is not a lens.

## Protocol shape

Each lens object provides:

| Field / method | Purpose |
| --- | --- |
| `name`, `collector_version` | Stable lens identity and collector semver |
| `cost` | Declared collection cost, e.g. `{"collectorSeconds": 1.2, "note": "…"}` |
| `required_facts` | Subset of `FACTS` (`verify-command`, `recorded-coverage`, `stack-tags`, `paths`) |
| `validation_guidance` | Non-empty text guiding the model validation pass |
| `consequence_template` | Non-empty text guiding plain-sentence consequences |
| `collect(ctx)` | `{"candidates": [{"id": str, …}], "digest": <json>}` |
| `diff(prev_digest, cur_digest)` | `{"new": [ids], "worsened": [ids], "resolved": [ids]}` |
| `red_lines(candidates)` | `[{"kind": <RED_LINE_KINDS>, "id": str, "detail": str}]` |
| `degrade(reason)` | `{"lens": name, "degraded": True, "reason": reason}` |

## collector

The lens runs a **standard OSS tool** (or equivalent deterministic probe) plus a **thin normalization** layer that emits stable candidate records and a JSON digest the sweep can store. No model calls in collect — it must be reproducible from the repo state and declared config. Declare `collector_version` when the normalization shape changes.

## baseline-diff

The lens owns **stable candidate identity** (`id` strings that survive across sweeps) and a **per-lens diff** over its digest. `diff()` returns only `new`, `worsened`, and `resolved` ids — the sweep merges these into drift-over-baseline surfacing. Identity stability is the lens author's responsibility; unstable ids create false churn.

## validation

Candidates reach the model only after deterministic surfacing. The model checks each against `CLAUDE.md`, `CONVENTIONS`, calibration, and spec'd designs using the lens's `validation_guidance`. Unactionable candidates are rejected before anyone sees a consequence. The lens does not run validation — it supplies guidance; the sweep's one model pass executes it.

## consequence

For each validated survivor, output **one plain sentence**, its **receipt** (the measured evidence), and an **effort** estimate — priced from that evidence, **never** from rule-catalog severity tiers. Use `consequence_template` to keep phrasing consistent within the lens. Consequences are advisor-facing, not matrix scores.

## cost

Declare collection cost honestly in the `cost` dict so the advisor can reason about sweep expense. Include at least `collectorSeconds` (measured or bounded) and a short `note` when the collector has preconditions (missing manifest, skipped paths, etc.). A lens that cannot collect must call `degrade()` with a clear reason rather than emitting empty candidates silently.

## Tool invocation

Every external tool invocation by a lens **must** go through `guardian_tools.invoke` (or `guardian_tools.resolve` / `guardian_tools.version` for probe-only paths). Direct use of `subprocess`, `os.system`, `os.popen`, or `subprocess.Popen` inside a lens module is a **contract violation**.

The seam (`plugins/superheroes/lib/guardian_tools.py`) provides these guarantees by construction:

1. **Neutral child cwd** — collectors never run with the swept repo as their working directory.
2. **Absolute repo operands** — repo-relative targets are absolutized and placed after a `--` end-of-options sentinel.
3. **Identity-based executable rejection** — resolved binaries are validated with `os.path.samefile`, never string containment.
4. **Environment allowlist** — code-loading variables are stripped; `PATH` and `NODE_PATH` are sanitized.
5. **No fetch at sweep time** — absent tools degrade with a message quoting `guardian_tools.INSTALL_COMMANDS`; the seam never installs or fetches.

Install guidance for collectors lives only in `guardian_tools.INSTALL_COMMANDS`.

## Collection honesty

Every registered lens must satisfy the honesty invariants (enforced by the per-lens conformance suite).

`collect()` returns a **status** from `COLLECT_STATUSES`: `collected`, `partial`, or `not-collected` (default `collected` when omitted). A lens that could not collect returns `not-collected` with a non-empty `reason` — never an empty candidate list that reads as clean.

- **`not-collected`** — the sweep records a `degradedLenses` entry, surfaces nothing, does not set `funnel["raised"]` for that lens, and preserves the prior snapshot digest (or omits the lens when there is no prior entry).
- **`partial`** — the sweep records degradation **and** processes the candidates and digest the lens did collect. The lens owns merging `ctx["prevDigest"]` for the portions it could not collect this run. When the collector version changed, a `partial` result does not advance the baseline digest until a full `collected` result lands.

The production loader degrades a broken lens **visibly by name** (stand-in with the expected lens name) — never silent omission, never fatal to the sweep.

Tool-running and status-builder helpers live in `guardian_collect.py` — the single home for that behavior (CONVENTIONS §11). Lenses use `run_tool`, `collected()`, `partial()`, and `not_collected()` rather than re-implementing subprocess handling.
