## Contents

- One lens, two ecosystems
- Findings bar (owner-deferred vocabulary / check-the-check)
- Tool seam (`run_tool` / `guardian_tools`)
- Invocation hardening (why `--` and absolute operands)
- Ecosystem detection and status outcomes
- Collapse tripwires (TypeScript ≥6 compensating control)
- Flat-repo honesty (Python)
- Non-mutating collection
- Identity
- Graduation path
- Declared cost
- Digest counters and known gaps

# Coupling lens

The coupling lens is a **pure data-gatherer with a high findings bar** — deliberately demoted from centerpiece. Both hands-on boundary candidates in this project's history died in adjudication as conventionally-sanctioned code. Loud-but-sanctioned edges are **data, not findings**: they land in the digest and can never reach `candidates`. The lens never runs or enforces a project's checks; it collects matrix, counters, collapse tripwires, and flat-repo honesty — and surfaces nothing while declared-vocabulary reading is deferred.

Implementation lives in `guardian_lens_coupling.py` (lens logic, eligibility, census, collapse tripwires, digest) and `guardian_coupling_adapters.py` (depcruise argv construction + JSON parsers + closed outcome table). The single lens object exports through `guardian_lens_coupling.LENSES = (LENS,)` and registers via `guardian_lens.load_production_lenses()` under the name `coupling`.

## One lens, two ecosystems

| Side | Tool | How |
| --- | --- | --- |
| JavaScript / TypeScript | dependency-cruiser (`guardian_coupling_adapters.DEPCRUISE_TOOL`) | Spawned via `guardian_collect.run_tool` |
| Python | **stdlib AST import census** (identity token `IMPORT_LINTER_TOOL`; import-linter spawn deferred with config-reading) | In-process; no spawn |

Both sides run inside one `collect()`. Per-ecosystem status lives in `digest.ecosystems`; the whole-lens status follows main's three-state contract:

- **collected** — a healthy matrix was measured for either or both ecosystems (`candidates` stay `[]` while vocabulary is deferred; the digest records the deferral).
- **partial** — one ecosystem degraded while the other collected; the reason names what degraded; the digest is kept for the measured side.
- **not-collected** (`digest=None`) — nothing collectable: no JS/TS and no Python sources (reason text keeps that case distinct), or collapse / cliff / byte-cap / tool-broken / flat-not-analyzable on every present side.

**Python is an AST census, not import-linter.** While declared-vocabulary / repo-config reading is owner-deferred, import-linter has nothing safe to run: the Python side builds the folder-level matrix from a stdlib AST import walk (`parseMode` = `ast-census-only`). Never spawn `lint-imports` from this lens.

## Findings bar

The bar is **structural**, not advisory. `exclusion_reason()` in `guardian_lens_coupling.py` routes every non-qualifying edge to the digest; only edges that pass the filter *and* match a declared rule violation can become candidates — and declared-rule matching is currently deferred (below).

Exclusion reasons the filter can emit (constants in `guardian_lens_coupling.EXCLUSION_REASONS`, first match wins — read the constant values from the module, do not restate them here):

| Reason constant | Meaning |
| --- | --- |
| `EXCLUSION_DECLARATION` | `.d.ts` declaration import |
| `EXCLUSION_TYPE_ONLY` | type-only dependency |
| `EXCLUSION_TEST_PLUMBING` | test/fixture/mock path or filename |
| `EXCLUSION_GENERATED` | generated, vendored, or build-output path |
| `EXCLUSION_WRAPPER` | conventionally-sanctioned shared plumbing target |
| `EXCLUSION_INTRA_CLUSTER` | same cluster on both sides |

**Owner-deferred: no repo-config reading.** After four confirmed remote-code-execution escapes on the config-reading surface, declared-vocabulary surfacing and check-the-check liveness verification are **deferred by owner decision pending a dedicated security design** (follow-up issue; advisor files the number). This lens never discovers, parses, sanitizes, or passes repository configuration to any collector. `deferred_vocabulary()` always returns `declared: false` with `deferred: true` and `VOCABULARY_DEFERRED_NOTE` — that is an honest deferral, **not** a claim that the repo was checked and declared nothing. Guessing walls from folder names is exactly the plausible-but-wrong rule derivation this project rejected. Until vocabulary returns, the lens surfaces **nothing** and collects data only. Every successful digest carries `declaredVocabulary` and `deferredCapabilities` (via `deferred_capabilities_list()`) so a zero-candidate collect is never indistinguishable from a fully verified clean measurement. Human-report / funnel surfacing of those digest fields is a deferred follow-up — do not expect a `funnel.deferredCapabilities` report section from this lens today.

**Owner-deferred: check-the-check.** `deferred_check_the_check()` records `CHECK_DEFERRED` with `CHECK_THE_CHECK_DEFERRED_NOTE` in the digest. Coupling red-lines stay empty while this surface is deferred — there is no dead-adopted-check kind in `guardian_lens.RED_LINE_KINDS` until that design lands.

## Tool seam (`run_tool` / `guardian_tools`)

dependency-cruiser is invoked **only** through `guardian_collect.run_tool(argv, ctx, cwd=repo, ok_exits=(0,))`. In production that routes to `guardian_tools.invoke` (neutral child cwd, env allowlist, PATH-only identity-checked resolution, output caps, process-group kill). In tests / conformance it routes through the injected `ctx["run"]` stub. `run_tool` passes `targets=()`, so **absolute repo operands must be baked into argv** (via `absolute_repo_operands` → `depcruise_argv`) — mirror the deps lens.

Adapters no longer own a local subprocess / env / cwd stack. Keep in `guardian_coupling_adapters.py`: argv construction (`depcruise_argv`, always `--no-config`), JSON parsers (`parse_depcruise_json`, `depcruise_versions` / `edges` / `parsed_modules` / `violations`), the closed `OUTCOMES` table, and `cache_paths_present`.

## Invocation hardening (why `--` and absolute operands)

A confirmed escape: a repository directory literally named `--config` was appended as a positional operand. dependency-cruiser parsed it as its `--config` flag with no value, fell back to auto-discovering default config names in cwd (the swept repo), and **executed** `.dependency-cruiser.js` — remote code execution from a read-only sweep. Marker file created; empirically confirmed.

Belt and braces in `guardian_coupling_adapters.py` (argv shape) plus the shared seam (cwd/env):

1. `append_repo_operands` inserts an end-of-options `--` separator before any repo-derived operand.
2. `safe_repo_operand` prefixes relative paths with `./` so a leading `-` can never begin the token. Absolute operands (the collect path) pass through — they cannot look like flags on POSIX.
3. dependency-cruiser always passes `--no-config` (`depcruise_argv`) and never `--config`. Repo config reading is owner-deferred; do not re-add it. `--no-config` also suppresses cwd auto-discovery of `.dependency-cruiser.js`.

Env hygiene (allowlist, PATH sanitization, rejection of code-loading names such as `NODE_OPTIONS`) lives in `guardian_tools` — not re-implemented in the coupling adapters.

## Ecosystem detection and status outcomes

Ecosystem detection is lens-owned: a recursive source/manifest census (`census()`), because the sweep's manifest probe is root-only and misses nested workspaces.

An ecosystem with **no sources** is simply absent from `digest.ecosystems` — not a degradation. A repo that legitimately has no Python must never force the whole lens to `not-collected` when JS collected cleanly. Whole-lens `not-collected` with a reason that names **no sources in this repo** is reserved for the case where *neither* side has sources.

Degraded paths (tool absence, parser collapse, flat Python layout, repo writes, malformed collector output, cliffs, byte caps) map to ecosystem `not-collected` and then to whole-lens `partial` or `not-collected` per the rules above — never an empty candidate list that reads as "ran clean".

## Collapse tripwires

A collector that silently collapsed must never be indistinguishable from a repo that is genuinely clean.

**Primary signal** — per-language, per-workspace census (`detect_collapse()`): sources on disk vs modules parsed, separately for each language in each workspace. **Zero parsed modules against any on-disk sources is always a collapse** — the `COLLAPSE_MIN_SOURCES` threshold applies only to nonzero ratio judgments (a partially-engaged parser on a small workspace). Thresholds: `COLLAPSE_MIN_SOURCES` and `COLLAPSE_RATIO` in `guardian_lens_coupling.py`. A repo-wide total is **not** a safe signal — vendored JavaScript parsing fine can mask a fully collapsed TypeScript census inside a healthy-looking total.

**Secondary signal** — prior-digest cliff (`detect_cliff()`): module count fell off a cliff vs the prior sweep while the source census did not follow (`CLIFF_RATIO`). The prior comes from `ctx["prevDigest"]` (sweep-injected), never a store re-read. A genuine repo shrink drops sources too; a broken collector drops only parsed modules.

**dependency-cruiser TypeScript compat.** dependency-cruiser silently degrades to JavaScript-only parsing when the resolved TypeScript major is outside what it supports. Measured on a real Next.js repo: with TypeScript 6.0.3 resolvable it returned **2 modules against 590 TypeScript sources**, exit 0, empty stderr. The coupling lens gives dependency-cruiser a **plugin-controlled, supported-major TypeScript** via an outside-repo `NODE_PATH` entry (`guardian_tools.typescript_toolchain_node_path` — never the swept repo's own `node_modules` TypeScript). When no supported toolchain is available, collection degrades honestly via the **module-count-collapse tripwire**, exactly as before (`not-collected` with a naming reason) rather than writing a false-clean baseline. The digest's `versions` block still records resolved tool/TypeScript versions, `parseMode`, and informational `pinHeld` when the report carries them; the JS ecosystem section records `typescriptToolchainProvided`.

## Flat-repo honesty (Python)

A flat layout with no `__init__.py` under any Python source root (`_python_is_packaged()`) reports via `guardian_coupling_adapters.OUTCOMES["flat-layout"]` — honestly degraded rather than faking a clean result. This repo's own `plugins/superheroes/lib/` is exactly that case. The Python side collects via the stdlib AST census only (`parseMode: ast-census-only`) and does not spawn import-linter.

## Non-mutating collection

dependency-cruiser is invoked without its opt-in `--cache`. `cache_paths_present()` gives a before/after probe (including `.import_linter_cache` as defense-in-depth) — if a cache path appears, that ecosystem degrades with `OUTCOMES["repo-write"]`. A sweep promising "never edits code" must mean it.

## Identity

Candidate ids follow `guardian_lens_coupling.ID_GRAMMAR` (`coupling:<tool>:<rule>:<normalized-location>`) where `<tool>` is the value of `TOOL_TOKEN_JS` or `TOOL_TOKEN_PY`, `<rule>` is the declared rule / contract name that fired, and `<normalized-location>` is `<fromCluster>-><toCluster>`. `make_id()` includes the rule segment when a rule is present.

Cluster keys (`cluster_key()`): forward-slash separator (Windows backslashes folded), lower-cased, workspace-qualified and repo-relative, capped at `CLUSTER_MAX_DEPTH` segments below the workspace root. Rename-stability boundary is explicit in the module docstring — preserved across line edits and intra-cluster file moves; **not** preserved when the cluster directory itself moves or a file crosses a cluster boundary (the wall moved; a ledger disposition against the old wall should not silently transfer).

Wall keys (`make_wall_key()`) are a seam only — recurrence tracking belongs to the dispositions ledger (#539).

## Graduation path

A **recommendation, never a mechanism.** When the same architectural wall keeps being crossed, the lens's `validation_guidance` recommends that the owner adopt the standard tool into their own toolchain — usually best as **one owner-approved line in the conventions file** the coding agents read before writing. Declining never turns detection off.

Declared-vocabulary surfacing and check-the-check liveness are **deferred by owner decision pending a dedicated security design**. Until that follow-up lands, this lens does not read adopted configs and does not emit dead-check advisories or red-lines. The deferral is disclosed on the digest (`declaredVocabulary` / `deferredCapabilities`) — not silently omitted from a clean-looking measurement.

## Declared cost

The lens object's `cost` dict is set on `CouplingLens` (`collectorSeconds`, `note`). Read the numbers and wording from that home — do not restate them here (CONVENTIONS §11). The single `coupling` lens declares an ephemeral collector cost covering both ecosystems and degrades when the tool is absent, an ecosystem is unparseable, or the module census collapses.

## Digest counters and known gaps

The digest counters cover matrix drift (`matrixHash` over the full matrix — truncation via `MAX_MATRIX_CELLS` cannot hide drift) and grandfathered-debt trend via `excludedByReason` and `eligible`. While vocabulary is deferred, the surfaced counter stays 0 even when `eligible` edges exist in the digest — data only.

**Known gap:** suppression count is not derivable from this lens. Ledger suppression happens in the sweep **after** `collect()` returns (`guardian_sweep.py` post-lens ledger filter) and is structurally not observable inside the lens — deferred to the ledger issue ([#539](https://github.com/zwrose/superheroes/issues/539)).
