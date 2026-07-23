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
| `vitals(digest)` (optional) | `{vital_name: (value \| None, reason \| None)}` — see below |
| `first_baseline_precision` (optional) | `"high"` (always validate first-baseline candidates) or `"volume"` (threshold-gated); default `"high"` |

### Optional vitals hook

Lenses that own digest-sourced vitals MAY implement `vitals(digest)` returning a map of
vital name to a 2-tuple:

- `(value, None)` — **complete**: a full measurement for that vital.
- `(value, reason)` — **partial**: a real number over the portion measured, with
  `reason` naming exactly what is missing.
- `(None, reason)` — **not-collected**: nothing publishable; `reason` says why.

A **partial** reading MAY be a 3-tuple `(value, reason, identity)` where `identity` is a
list of stable `"<ecosystem>/<part>/<cause>"` tokens used for cross-sweep
drift-comparability. The `reason` prose is human-only and may be reworded freely without
affecting comparability. When a partial basis matches no recognized cause marker, the lens
emits the stable `"<ecosystem-or-lens>/<part>/unclassified-partial"` **sentinel** rather than poisoning `identity` to a non-comparable state — an unclassifiable partial over-alerts (stays comparable), it never silences the drift comparison (#592, fail-direction ruling). A 2-tuple partial (no identity) is treated as non-comparable (fail-closed) at the `guardian_vitals` layer, reserved for malformed completeness *entries* — a contract violation, not an unclassified basis.

The lens owns its digest shape; `guardian_vitals` owns vital names, thresholds, and the
completeness rule. Neither reaches into the other. A lens without `vitals()` contributes
no vitals. Extractors must be total and non-raising on malformed digests.

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
- **`partial`** — the sweep records degradation **and** processes the candidates and digest the lens did collect. The lens owns merging `ctx["prevDigest"]` for the portions it could not collect this run. When the collector version changed, a **transient** `partial` result does not advance the baseline digest until a full `collected` result lands. A lens may opt in to `permanentBoundary: true` (fail-closed: only the boolean `true` counts — not `1`, `"yes"`, etc.; the authoritative key is `guardian_lens.PERMANENT_BOUNDARY_KEY`) on a **contract-valid** `partial` result — status exactly `partial`, a non-empty string `reason`, and `permanentBoundary` exactly `true` — to declare that the un-measured remainder is a permanent capability boundary, not a transient failure; such a partial may seed a new-version baseline. The degradation record is **not** suppressed — every `partial`, including a permanent-boundary partial, still appears in `degradedLenses` on every sweep.

The production loader degrades a broken lens **visibly by name** (stand-in with the expected lens name) — never silent omission, never fatal to the sweep.

Tool-running and status-builder helpers live in `guardian_collect.py` — the single home for that behavior (CONVENTIONS §11). Lenses use `run_tool`, `collected()`, `partial()`, and `not_collected()` rather than re-implementing subprocess handling. The conformance harness assumes every tool invocation routes through `ctx["run"]` / `guardian_collect.run_tool`; a lens that shells out directly cannot be conformance-verified.

Every production lens MUST implement `conformance_cases()` supplying the tool-specific payload for `reported-nonzero-parsed-zero` (the only lens-supplied scenario — see `guardian_lens.LENS_SUPPLIED_CONFORMANCE_SCENARIOS`). Required case fields are defined in `guardian_lens.CONFORMANCE_CASE_FIELDS`: `stdout` (raw output that reports findings but normalizes to zero candidates), `clean_stdout` (raw output from the same tool with genuinely zero findings), and `exit` (the exit code the tool returns on a findings run — may be non-zero for findings-on-success analyzers). Optional keys are defined in `guardian_lens.CONFORMANCE_CASE_OPTIONAL_FIELDS`: `clean_exit` (the exit code on a genuinely-clean run when it differs from `exit` — models dual-success-exit tools like `npm audit` where `0` = clean and `1` = findings; declare `exit=1, clean_exit=0`), plus `config` and `prev_digest`, all forwarded to `collect()`; and `stdout_by_tool` / `clean_stdout_by_tool` — per-`argv[0]` stdout maps for a **multi-collector** lens, so the harness hands the findings payload to ONLY the targeted collector (`stdout_by_tool`) and a clean payload to every co-firing collector (`clean_stdout_by_tool`, else `clean_stdout`). That isolation keeps the targeted honesty gate load-bearing: a single shared stdout would degrade the whole lens through a co-firing tool regardless of the gate, letting a deleted gate still pass conformance. Omitting `clean_exit` runs the clean probe at `exit` (the prior single-exit behavior); omitting the per-tool maps keeps the single-stdout behavior. A lens MAY also expose `conformance_prev_digest() -> {"prev", "cleared", "sentinelIds"}` to feed a schema-valid prior digest whose sentinel finding its own `diff()` tracks; the harness first proves the sentinel resolves against a clean re-measure (`diff(prev, cleared)`) so the findings-probe "`resolved` must be empty" check is non-vacuous. The harness owns the five tool-agnostic scenarios in `guardian_lens.REQUIRED_CONFORMANCE_SCENARIOS` (`missing-tool`, `timeout`, `nonzero-exit`, `findings-empty-output`, `unparseable`) and injects its own `ctx["run"]` stubs — lenses supply nothing for those. CONVENTIONS §11 — that tuple is the scenario roster's one home. For `reported-nonzero-parsed-zero` the harness runs two probes: a **clean probe** (`clean_stdout` at `clean_exit`, else `exit`) that must return `collected`, and a **findings probe** (`stdout` at `exit`) that must degrade (`not-collected` or `partial`) — a tool that reported problems with zero parsed candidates must never read as `collected`. A **manifest-gated** lens (one that only reaches its tool when a manifest such as `package.json` / `requirements.txt` is present) may declare an optional `conformance_fixture() -> {relpath: content}`; the harness writes those files into a fresh temp dir per scenario and uses it as both `ctx["cwd"]` and `ctx["root"]` so the tool is reachable under the injected run stub. The per-lens conformance suite (`test_guardian_conformance.py`) runs against every registered lens and **fails registration** when `reported-nonzero-parsed-zero` is missing or an honesty invariant breaks: harness-owned degraded tool outcomes (`missing-tool`, `timeout`, `nonzero-exit`, `findings-empty-output`, `unparseable`) must never read as `collected`; a tool that reported problems must never yield `collected` with zero candidates; and when collection stops, `diff()` must never emit `resolved` ids.

### Tool-free lenses

A **stdlib-only** lens that runs no external tool (and, after its own refactor, no indirect subprocess) opts out of the tool-injection scenarios by setting the class attribute `uses_external_tools = False`. Such a lens supplies `guardian_lens.TOOL_FREE_CONFORMANCE_SCENARIOS` — `unreadable-input`, `all-inputs-unavailable`, and `partial-carry-forward` — via `conformance_cases()` instead. Each tool-free case is `{"fixture": {relpath: content}, "unreadable": [relpath, …], "prev_digest": <json>, "config": <dict | None>}`; the harness builds a fresh temp workspace per scenario, writes `fixture`, materializes each `unreadable` path as an input that cannot be read, runs `collect()` with `cwd == root ==` that workspace and no injected `ctx["run"]`, and asserts the tool-free honesty invariants: an unreadable input must **degrade or carry** (never a false clean), all inputs unavailable must **degrade with a reason**, a `partial` result must **preserve the prior digest** (`diff()` resolves nothing), and a stopped measurement emits no `resolved` ids. The harness additionally **proves** tool-free-ness rather than trusting it: it monkeypatches `guardian_collect.run_tool`, the indirect spawn helpers (`store_core.run_git`, `core_md.read`), and the raw spawn primitives (`subprocess.*`, `os.system`, `os.popen`) to raise, then runs `collect()` over the lens's declared fixture — a lens that reaches any of them is rejected.
