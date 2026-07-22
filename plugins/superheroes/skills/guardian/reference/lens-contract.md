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

Every external tool invocation by a lens **must** go through `guardian_collect.run_tool` (with `guardian_tools.resolve` / `guardian_tools.version` for probe-only paths). `run_tool` routes the production spawn through `guardian_tools.invoke`'s hardening; the injected `ctx["run"]` callable is the test/conformance seam that stands in for that spawn. Direct use of `subprocess`, `os.system`, `os.popen`, or `subprocess.Popen` inside a lens module is a **contract violation**.

**A lens MUST pass absolute paths in its `run_tool` argv.** Collectors run from a **neutral cwd** (never the swept repo), and `run_tool` calls `invoke(..., targets=())` — it does **not** thread or absolutize repo-relative operands. A repo-relative operand in a `run_tool` argv would run against the neutral cwd, match nothing, and read as a clean (empty) collection. The operand-absolutization channel exists on `guardian_tools.invoke` directly (its `targets=` parameter), **not** through `run_tool`.

The invocation seam (`plugins/superheroes/lib/guardian_tools.py`) provides these guarantees by construction. Guarantees #1, #3, #4, and #5 hold **through `run_tool`** (`invoke` applies them to the resolved `argv[0]` and the spawn). Guarantee #2 is a property of `invoke`'s `targets=` channel and does **not** hold through `run_tool` — see the absolute-argv rule above:

1. **Neutral child cwd** — collectors never run with the swept repo as their working directory. *(Holds through `run_tool`.)*
2. **Absolute repo operands** — repo-relative *targets* passed to `guardian_tools.invoke` directly (via its `targets=` parameter) are absolutized and placed after a `--` end-of-options sentinel. **This does NOT hold through `run_tool`, which passes `targets=()`** — a lens using `run_tool` must itself pass absolute paths in its argv.
3. **Identity-based executable rejection** — resolved binaries are validated with `os.path.samefile`, never string containment. *(Holds through `run_tool`.)*
4. **Environment allowlist** — code-loading variables are stripped; `PATH` and `NODE_PATH` are sanitized. *(Holds through `run_tool`.)*
5. **No fetch at sweep time** — absent tools degrade with a message quoting `guardian_tools.INSTALL_COMMANDS`; the seam never installs or fetches. *(Holds through `run_tool`.)*

Install guidance for collectors lives only in `guardian_tools.INSTALL_COMMANDS`.

## Collection honesty

Every registered lens must satisfy the honesty invariants (enforced by the per-lens conformance suite).

`collect()` returns a **status** from `COLLECT_STATUSES`: `collected`, `partial`, or `not-collected` (default `collected` when omitted). A lens that could not collect returns `not-collected` with a non-empty `reason` — never an empty candidate list that reads as clean.

- **`not-collected`** — the sweep records a `degradedLenses` entry, surfaces nothing, does not set `funnel["raised"]` for that lens, and preserves the prior snapshot digest (or omits the lens when there is no prior entry).
- **`partial`** — the sweep records degradation **and** processes the candidates and digest the lens did collect. The lens owns merging `ctx["prevDigest"]` for the portions it could not collect this run. When the collector version changed, a `partial` result does not advance the baseline digest until a full `collected` result lands.

The production loader degrades a broken lens **visibly by name** (stand-in with the expected lens name) — never silent omission, never fatal to the sweep.

Tool-running and status-builder helpers live in `guardian_collect.py` — the single home for that behavior (CONVENTIONS §11). Lenses use `run_tool`, `collected()`, `partial()`, and `not_collected()` rather than re-implementing subprocess handling. The conformance harness assumes every tool invocation routes through `ctx["run"]` / `guardian_collect.run_tool`; a lens that shells out directly cannot be conformance-verified.

Every production lens MUST implement `conformance_cases()` supplying the tool-specific payload for `reported-nonzero-parsed-zero` (the only lens-supplied scenario — see `guardian_lens.LENS_SUPPLIED_CONFORMANCE_SCENARIOS`). Required case fields are defined in `guardian_lens.CONFORMANCE_CASE_FIELDS`: `stdout` (raw output that reports findings but normalizes to zero candidates), `clean_stdout` (raw output from the same tool with genuinely zero findings), and `exit` (the exit code the tool returns on a successful run — may be non-zero for findings-on-success analyzers). Optional `config` and `prev_digest` keys are forwarded to `collect()`. The harness owns the five tool-agnostic scenarios in `guardian_lens.REQUIRED_CONFORMANCE_SCENARIOS` (`missing-tool`, `timeout`, `nonzero-exit`, `findings-empty-output`, `unparseable`) and injects its own `ctx["run"]` stubs — lenses supply nothing for those. CONVENTIONS §11 — that tuple is the scenario roster's one home. For `reported-nonzero-parsed-zero` the harness runs two probes at the declared exit: a **clean probe** (`clean_stdout`) that must return `collected`, and a **findings probe** (`stdout`) that must degrade (`not-collected` or `partial`) — a tool that reported problems with zero parsed candidates must never read as `collected`. The per-lens conformance suite (`test_guardian_conformance.py`) runs against every registered lens and **fails registration** when `reported-nonzero-parsed-zero` is missing or an honesty invariant breaks: harness-owned degraded tool outcomes (`missing-tool`, `timeout`, `nonzero-exit`, `findings-empty-output`, `unparseable`) must never read as `collected`; a tool that reported problems must never yield `collected` with zero candidates; and when collection stops, `diff()` must never emit `resolved` ids.
