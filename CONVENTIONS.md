# superheroes — band conventions

These are the **contracts the superheroes band shares**: artifact formats, storage
rules, and the coordination primitives that let the band's heroes (Showrunner,
Workhorse, The Architect, Review Crew, Test-Pilot) run a project's development
together without stepping on each other.

**Status.** This document *locks* conventions — it decides and records the schema so
later work builds against a fixed target. A hero implements a convention when it
first needs it; the convention does not require all heroes to implement it at once.
Where an existing hero already implements (or diverges from) a convention, this doc
says so.

**Scope.** This file is the authoritative contract. The broader product vision lives
elsewhere — [PHILOSOPHY.md](PHILOSOPHY.md) (why), [ROADMAP.md](ROADMAP.md) (the
release train) — this doc is deliberately narrow: *interfaces*, not roadmap.

**Band posture — designed to be used together.** The heroes ship as **one plugin** and
form a *cohesively designed band*: within a session they **assume each other's
presence** and **cross-reference freely by qualified name** (e.g. `superheroes:workhorse`,
`superheroes:review-code`). We **design for the integrated band and do not compromise
that design — or add machinery — to guarantee standalone-equivalence**; a hero used
outside the band carries **no warranty** (an individual hero may still have standalone
utility — e.g. `review-code`, test-pilot's browser runs — but that is not a contract).
A missing band member **degrades, it does not crash**: the spec review gate
(`review-spec`) never self-certifies — the `spec` is always **owner-gated** — so its
absence simply leaves the spec for the owner to approve directly, never silently waved
through. This is the superheroes-internal analog of "superpowers is an assumed
dependency."

**Section numbers are stable permalinks**, cited across the codebase (skills, rubric,
`lib/*.py` docstrings, tests, `CLAUDE.md`, the PR template). The gaps below
(§4.1/§4.3/§4.5–4.7, §5, §8–9, and §10.1–10.6) are intentional — they mark contracts
that retired with the v1 execution spine (#478); surviving contracts keep their
original numbers so existing citations stay valid.

## Contents

1. [Vocabulary: the v2 loop and cast](#1-vocabulary-the-v2-loop-and-cast)
2. [Calibration profiles](#2-calibration-profiles)
3. [Definition-docs: the spec](#3-definition-docs-the-spec)
4. [State tiers and stores](#4-state-tiers-and-stores)
6. [Identifiers and schema versioning](#6-identifiers-and-schema-versioning)
7. [Multi-host harness contract](#7-multi-host-harness-contract)
10. [Ship-phase honesty gates](#10-ship-phase-honesty-gates)
11. [One home per cross-boundary fact](#11-one-home-per-cross-boundary-fact-single-source-of-truth)
12. [Verification contracts](#12-verification-contracts-fix-ships-its-detector-real-seam-tests)
13. [New deterministic machinery needs a named consumer and a ledger entry](#13-new-deterministic-machinery-needs-a-named-consumer-and-a-ledger-entry)

---

## 1. Vocabulary: the v2 loop and cast

Superheroes pivoted from a v1 deterministic execution pipeline (the "spine") to a **v2
discipline layer**: two session charters running around ordinary AI build sessions, not
an orchestration engine (PR #478/#479 — retired the spine and the
`plan`/`tasks` definition-docs). The v2 loop:

```
issue → build brief → build → review → ready PR → advisor vet → owner merge
```

A **build brief** is the builder's own architecture note — shape, contracts & state,
reuse plan, hard seams, rejected alternatives, consequential flags — checked once by a
fresh cross-vendor reviewer before code and vetted against at the PR. It is not a
definition-doc: it lives in the issue/PR, not on disk under `docs/`. The one
definition-doc that survives the v1→v2 pivot is the **`spec`** (§3) — still owner-gated,
still produced by The Architect.

**The cast** (authoritative role definitions live in the two session charters —
`skills/showrunner/SKILL.md` and `skills/workhorse/SKILL.md` — this is a pointer, not a
restatement):

- **Showrunner** — the advisor session: project-level, long-lived, typically one per
  project. Sizes and routes incoming work (build-ready vs. needs-discovery), decomposes
  big asks into small mergeable issues, vets every PR from its artifacts against the
  issue/spec and the build brief, owns board hygiene and release coordination, keeps
  durable memory. **Never builds, never merges.**
- **Workhorse** — the builder session: issue-scoped, disposable, parallelizable. Takes a
  routed issue, writes and gets the build brief checked, delegates all implementation to
  tiered subagents or engines, verifies every receipt itself, runs test-pilot and
  multi-model review, hands back a ready PR with dispositions and receipts. **Never
  merges, releases, bumps versions, or wires the board.**
- **The Architect** — turns fuzzy intent into an owner-approved `spec` (discovery → spec
  → `review-spec`). Narrowed in v2: it produces the `spec` only — no `plan`, no `tasks`
  (retired, #479).
- **Review Crew** — the multi-model review layer: the spec panel (`review-spec`) and
  `review-code`'s cross-vendor build review. Panel composition is **composed to
  complement** the builder's vendor so the maker's vendor never dominates its own
  checking.
- **Test-Pilot** — browser-evidence verification: plans derived from the spec/issue,
  executed for real. Observe-and-report only — a bug it finds becomes a work order, it
  never fixes.

Two heroes run sessions; three serve inside them. The band posture above (degrade, not
crash) governs this cast the same as any other.

Load-bearing identifiers used throughout (`<work-item>`, the storage keys) and the
schema-versioning policy are defined once in **§6**.

---

## 2. Calibration profiles

Superheroes are *configured to your project and evolve with it*. Calibration is a
**shared core + per-plugin layers**, stored under one directory, governed by **one
band-wide storage mode**.

### 2.1 Layout (decision: core file + per-plugin files)

```
.claude/superheroes/        # in-repo mode; in global mode this content lives in the project store (§2.3)
  core.md            # the shared brain — read by every hero
  <plugin>.md        # one per plugin: review-crew.md, test-pilot.md, …
  patterns.md        # research-derived "current best-practice" layer (own lifecycle)
```

- **`core.md`** carries band-wide project facts: stack, the canonical *verify* command,
  threat model, canonical patterns. Its **single writer** is the calibration owner
  (`init` / the profile-management skill) — not `the-architect` (which owns the `spec`
  definition-doc). Because `core.md` is project-keyed and shared across a project's
  checkouts (§2.3), the writer **serializes its writes under the project-scoped config
  lock** (§4.4) — a machine-local lock. (In in-repo mode, cross-machine config writes are
  additionally git-mediated, since config is committed.)
- **`<plugin>.md`** is a layer **owned and versioned by that plugin**. Each plugin
  writes only its own layer — no plugin co-edits another's file.
- **`patterns.md`** is the research-derived opinion layer. It lives in its own file
  because it has a distinct lifecycle: refreshed on a research cadence and **pinned per
  run** — a session snapshots the live file at start and reads the pin, never the live
  file, for the rest of its run.

Session-scoped work (a build's worktree, in-progress state) is ephemeral, lives with the
session, and is never stored here.

### 2.2 File format

Every file begins with a one-line **provenance comment**:

```
<!-- superheroes-core: schemaVersion=1 status=provisional created=2026-06-14 updated=2026-06-14 -->
<!-- superheroes: plugin-version=0.1.0 schemaVersion=1 status=confirmed created=… updated=… nudge-ack={} -->
```

- The **leading tag** (`superheroes-core:` / `<plugin>:`) is the canonical encoding of
  identity; there is no separate `plugin=` field. Layer files additionally carry
  `plugin-version` and the `nudge-ack` map.
- **`status`**: `provisional` (auto-generated, e.g. on a headless run) → `confirmed`
  (owner validated via `init`).
- **Prose for agents, a small machine-readable block for code.** Calibration that
  agents read (threat model, patterns) is prose. The handful of fields a resolver or
  engine must parse deterministically live in a fenced block — `core.md`:

  ````
  ```json superheroes-core
  { "schemaVersion": 1, "verifyCommand": "…", "stackTags": ["…"] }
  ```
  ````

  A plugin layer keeps its own block where it has one (e.g. test-pilot's existing
  `json test-pilot-config` block moves into `test-pilot.md` verbatim).
- **CLAUDE.md-aware adder.** A profile carries only what the project's `CLAUDE.md` does
  not already state. Conventions live in `CLAUDE.md`; the profile adds calibration on
  top.

### 2.3 Storage mode (one band-wide toggle)

The whole band is either **in-repo** or **global**, decided once by `init` and never
per-plugin:

| | **in-repo** | **global ("without a trace")** |
| --- | --- | --- |
| Calibration (`core.md`, layers, `patterns.md`) | `.claude/superheroes/` committed with the repo | the project store (below) |
| Effect | calibration is **shared with collaborators** | the repo stays **pristine** — zero superheroes footprint |
| Definition-doc (`spec`, §3) | `docs/superheroes/<work-item>/` in the repo | the project store (below) |

"Global mode" content (calibration and the `spec` definition-doc) lives in a
machine-local, git-initialized **project store** — one per project, keyed by
`<config-key>` (§6.2) — that also holds the authoritative `registry.json` (the
storage-mode record) and a config-write lock. "in-repo" shares *calibration*; it does
not promise zero global footprint — `registry.json` is always machine-local. Both modes
keep the *repo* clean of session-scoped state.

**Mode is set once and is sticky.** `init` is idempotent: on an already-initialized
project it reconciles content but does **not** silently re-decide the mode. The
authoritative mode record is `registry.json` in the project store. A mode flip
(in-repo↔global) is an **explicit migration** that moves calibration *and* the `spec` to
the new location and updates `registry.json`; absent that migration, `init` refuses to
re-decide once the registry records a mode. (Without this rule a flip would strand
every already-written calibration file and definition-doc.)

### 2.4 Resolution and evolution

- **One shared resolver.** The band ships a single in-tree library, `store_core`
  (`lib/store_core.py`), that resolves the project-store key: **`<config-key>`**
  (§6.2, self-healing pointers) — deliberately unifies a project's clones/worktrees so
  they share calibration.
- **No-remote repositories.** When `git remote get-url origin` is empty (common for the
  owner *before the first push*, while discovery is already producing a `spec`), the
  config key is `<common-dir-key>` rather than `<remote-key>` (§6.2), which makes config
  **per-checkout-clone, not shared-across-clones** — the "shared across clones"
  guarantee is impossible until a remote exists. On the first push, `init` **rebinds**
  the project store to the new `<remote-key>` (and merges the fallback entry) so
  calibration does not fork.
- **Living profiles.** A *staleness nudge*, a *learning-loop proposal* (any hero may
  **propose** a calibration edit, applied only on confirmation), and a **`nudge-ack` map**
  so a dismissed signal does not re-fire until it changes.
- **Rendered single view.** Although calibration is stored as several files,
  `superheroes:configure` (the band-wide calibration front door — what "`init`" refers to
  throughout this doc) renders core + layers + the pinned patterns as **one screen**, so the
  owner sees "one profile" while the disk stays coordinated. The per-hero `*-init` skills are
  now reached only from within `configure`, not advertised as their own entry points.

---

## 3. Definition-docs: the spec

The `spec` is the one definition-doc that survives the v1→v2 pivot (`plan` and `tasks`
retired, #479 — the orchestrating session now owns its own approach, checked via the
build brief instead of a reviewed plan doc, §1).

### 3.1 Shared frontmatter (YAML)

The `spec` opens with the metadata superheroes owns:

```yaml
---
superheroes: doc
schemaVersion: 1
docType: spec                          # the only definition-doc in v2; plan/tasks retired (#479)
workItem: <work-item>                  # the frozen identity from §6.1
issue: <github-issue-number | null>    # linked once an issue exists; NOT the path segment
size: small | medium | large           # work-item sizing (see §6.4)
status: draft | in-review | approved   # DERIVED, human-facing: approved iff gates.review == passed
gates: { review: pending | passed | changes-requested }   # AUTHORITATIVE review state for THIS doc
producedBy: the-architect@<version>
created: <date>
updated: <date>
---
```

- **`gates.review` is the authoritative review outcome** for the spec;
  **`status` is derived** from it (`approved` iff `gates.review == passed`) and is for
  humans. Code reads `gates.review`.
- There is no `parent` field: v1's `plan`→`spec`/`tasks`→`plan` chain existed to link
  sibling definition-docs; with only one doc type left, there is nothing to link to.

> **Legacy artifact, intentional.** `eval/lib/schemas/checkpoint.schema.json` still
> enumerates `docType: plan | tasks | spec` — retained deliberately as test-required
> legacy from the retired execution spine (PR #478), not drift. It is not a live
> contract and should not be extended.

> **Why YAML frontmatter here but an HTML-comment in §2.2?** Intentional, not drift.
> Calibration files are prose config read mostly by agents, with a minimal embedded
> block for the few code-parsed fields. The `spec` is a structured artifact with
> machine-read fields (`docType`, `gates`), for which standard frontmatter is the right
> tool.

### 3.2 Body

**`spec`** — plain-language requirements, owner co-authors, **no tech**. Sections:
purpose; who it's for; functional requirements; significant unhappy paths;
non-functional requirements; UI/UX; definition of done; assumptions & dependencies;
constraints; out-of-scope; open questions; glossary. **Functional requirements are
written in EARS** (Easy Approach to Requirements Syntax — `When`/`While`/`Where`/`If-Then`
+ "the system shall …"), one behavior each, every requirement carrying **≥1 acceptance
criterion** (Given-When-Then for flows, a rule for simple constraints). **Depth = the
happy path *plus the significant unhappy paths*** (the unwanted-behavior `If-Then` EARS),
elicited via a coverage checklist (empty/first-run, invalid input, boundaries, errors,
access, duplicates, concurrency, abuse, reach) and tagged Specify/Defer/N-A —
**not** an exhaustive enumeration, and **not** the technical *how* (that is the build
brief, owned by the builder, §1). Non-functional requirements are stated as **outcomes
with a fit-criterion**. UI/UX **references the Claude Design handoff output**, not a
reinterpretation. This is the anti-slop core.

### 3.3 Location and convertibility

- **Location follows the storage mode (§2.3):** in-repo →
  `docs/superheroes/<work-item>/spec.md` in the repo (committed, diffable); global →
  `projects/<config-key>/docs/<work-item>/spec.md` in the **git-initialized project
  store** (§2.3), so global-mode specs are versioned and diffable too.
  The-architect implements this: the in-repo location plus committed/gitignored choice
  is the doc-policy established via `superheroes:configure` (which drives the-architect's
  doc-policy; the standalone `architect-init` is now an internal helper reached only from
  `configure`).
- **Convertibility.** Spec-Kit is GitHub's spec-driven-development toolkit
  (<https://github.com/github/spec-kit>), which standardizes `spec.md`/`plan.md`/
  `tasks.md`; we adopt its `spec` noun for convertibility (`spec↔spec.md` is a
  documented field-mapping). An actual converter is built only if something needs it.

> **Naming note.** We do **not** name the `spec` "design": **"design" means UI/UX**
> here, never a technical-approach doc. **Claude Design** (Anthropic's UI/UX design
> tool) is a first-class Discovery activity: Discovery hands the owner a design prompt
> built from the requirements, the owner creates the design there, and its **handoff
> output** (not a reinterpretation) is referenced in the `spec`.

---

## 4. State tiers and stores

§4.1 (state tiers), §4.3 (runtime schemas), and §4.5–4.7 (concurrency, events/resume-brief,
loop-failure) retired with the execution spine (#478) — the gaps are intentional. The two
subsections below are **live v2 infrastructure**, not spine runtime: `configure_route.py`/
`configure_view.py` still resolve calibration storage through them.

### 4.2 Two stores and their keying

Superheroes uses **two kinds of git-initialized store**, split along the
config-vs-state line, because the two have opposite sharing needs:

- **Project store = per-project**, keyed by `<config-key>` (§6.2) — shared across all of
  a project's worktrees and clones on a machine (same project ⇒ same
  threat-model/patterns, one mode record). Holds calibration, the global-mode `spec`,
  the authoritative `registry.json`, and the config lock (§4.4).
- **Control-plane store = per-clone**, keyed by `<common-dir-key>` (§6.2) — shared
  identically across a clone's main checkout and every linked worktree, distinct across
  clones. Its resolution home is `lib/control_plane.py`.

The per-issue runtime the control-plane store used to hold — checkpoints, the queue, and
per-work-item lease refs — retired with the execution spine (#478); the store and its
keying remain as `lib/control_plane.py`'s resolution home.

The project store exists in **both** modes (it is the machine-local home of
`registry.json` and `config.lock`); in in-repo mode its calibration and `spec` content
lives in the repo instead. (`<config-key>` and `<common-dir-key>` derivations are in §6.2.)

### 4.4 Project-scoped config lock

Calibration (`core.md`/`<plugin>.md`/`patterns.md`) is shared across a project's
checkouts (§4.2). Config writes acquire an advisory **`flock` on
`projects/<config-key>/config.lock`** in the machine-local project store (present in
both modes), which serializes them across the project's checkouts on that machine. In
in-repo mode, cross-machine config writes are additionally mediated by git (config is
committed). Config write cadence is owner-driven and low.

---

## 6. Identifiers and schema versioning

The cross-cutting values **all heroes** must compute identically.

### 6.1 `<work-item>` — the join key

`<work-item>` is a **frozen slug**, chosen **once** at work-item creation and **never
re-derived** (a title edit does not change it). It is the stable segment interpolated
into the `spec`'s path (`docs/superheroes/<work-item>/spec.md`,
`projects/<config-key>/docs/<work-item>/spec.md`).

- Slug = the title **NFC-normalized**, lowercased, non-`[a-z0-9]` runs collapsed to `-`,
  trimmed, capped at 50 chars (then trimmed again, so the cap can't leave a trailing
  `-`), **plus a short disambiguating suffix** (`-` + first 6 hex of
  `sha256(NFC-title + creation-nonce)`) so two similar titles **never** collide into one
  dir. (NFC normalization makes canonically-equivalent Unicode — e.g. macOS-NFD vs
  Linux-NFC — yield the same slug.)
- The **GitHub issue number is a linked attribute** — the `issue:` field in the
  `spec`'s frontmatter (§3.1) — **not** the path segment, so nothing has to be renamed
  when an issue is later filed for a work-item that began as a pre-issue draft.

### 6.2 Storage keys

The normative spec is implemented in `lib/store_core.py`. **Hash:** `sha256(...)`
truncated to **16 hex** (`short_hash`).

- **`<remote-key>`** = `short_hash(normalize_remote(origin))`, where `normalize_remote`
  lowercases the host and strips scheme/userinfo/port and a trailing `.git`.
- **`<common-dir-key>`** = `short_hash(realpath(git rev-parse --path-format=absolute --git-common-dir))`
  — shared across a clone's linked worktrees. Serves as the **no-remote config-key
  fallback** (§2.4). `--path-format=absolute` is required: a bare `--git-common-dir` is
  a relative `.git` from the main checkout, which `realpath` would resolve against the
  process cwd; the fallback for git < 2.31 joins the relative result onto the target
  cwd, else `--absolute-git-dir`, else `realpath(cwd)`.
- **`<config-key>`** (the project-store key) = `<remote-key>` when a remote exists,
  else `<common-dir-key>`. On first push, `init` rebinds `<common-dir-key>` →
  `<remote-key>` (§2.4).

> **No §6.3.** The old content-hash / branch-content-addressing section retired with
> the execution spine (#478) — the gap is intentional, not an omission.

### 6.4 Size and schema versioning

- **`size`** (`small | medium | large`, §3.1) sizes a work-item. It is set when the
  `spec` is approved (The Architect infers it from scope, not the owner) and frozen
  there. It is currently **descriptive** — consumers must accept it; no control-flow
  keys off it yet.
- **`schemaVersion`** is stamped independently on each artifact family (`core.md`,
  the `spec`, calibration layers). Bump on a **breaking** change (additive changes do
  not bump). A reader that encounters an **unknown** version **fails closed** with an
  "update the plugin or migrate the file" message. Migration logic lives in the hero
  that owns the artifact. The band ships as one plugin — one version — so cross-plugin
  version skew is not a concern; artifact `schemaVersion` skew (files written by an
  older build) is covered by the fail-closed behavior above.

---

## 7. Multi-host harness contract

The superheroes plugin runs on both Claude Code and Codex. The harness has **two layers**:

### 7.1 Shared layer (host-neutral)

Everything in the plugin's source tree is shared and host-neutral:

- **`skills/`** — the skill logic. Written in host-neutral *actions* ("read the
  file", "run the verify command", "dispatch the reviewer"). No host tool names here.
- **`lib/`** — Python helpers and tests. Pure Python, no host dependency.
- **`agents/`**, **`rubric/`**, **`eval/`** — likewise shared.

Each `SKILL.md` carries a host-map pointer line:

> This skill speaks in host-neutral actions. Resolve them to your runtime's tools
> by reading the host tool map at `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/hosts/<your-host>-tools.md`
> (the leading variable is this plugin's root directory) — `claude-tools.md` on Claude
> Code, `codex-tools.md` on Codex.

The portable root seam `ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"` (assigned
once per bash block) lets skills reference bundled helpers on both hosts. Bare
`${CLAUDE_PLUGIN_ROOT}` is banned — it fails on Codex. The pointer line above uses
that same seam so it resolves at the plugin **root** (where `hosts/` lives); a bare
relative `hosts/` path would resolve against the skill's own folder, which has none. `validate_hosts.py` enforces the seam form.

### 7.2 Host-adaptation layer (thin, per-host)

The plugin carries one set of thin per-host pieces:

| Artifact | Purpose |
| --- | --- |
| `.claude-plugin/plugin.json` | Claude Code manifest (name, version, description) |
| `.codex-plugin/plugin.json` | Codex manifest — same version, Codex-native description |
| `hosts/claude-tools.md` | Maps host-neutral actions → Claude Code tools |
| `hosts/codex-tools.md` | Maps host-neutral actions → Codex tools (`shell`, `apply_patch`, `spawn_agent`, …) |
| `hooks/hooks-codex.json` | Codex hook config (only where needed) |

Both `plugin.json` versions must be kept in sync — `validate_hosts.py` fails on
version drift between `.claude-plugin/plugin.json` and `.codex-plugin/plugin.json`.

### 7.3 Anti-scope

The harness does **not** introduce:
- Compatibility matrices or minimum-version tables
- Schema migrations between host versions
- A `doctor` or `reconcile` command
- File-locks or coordination between host runtimes

The shared layer is the contract; the host-adaptation layer is a read-only map.
Adding complexity to guarantee cross-host parity for edge cases is explicitly out of
scope — the two hosts load the same skills, and the tool maps are the entire seam.

### 7.4 SessionStart context bootstrap (Claude)

A session started **directly from a slash command** (e.g. `/superheroes:workhorse`
in a fresh worktree — superheroes' usual entry path) does **not** receive the harness's
auto-injected context layer that a plain chat start gets: project `CLAUDE.md`, the
`MEMORY.md` head, and the env block are all absent, and nothing expands the §7.1 host-map
pointer's `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}`. The only channel that survives the spawn
is a `SessionStart` hook's `additionalContext`.

On Claude Code, `hooks/session_start.py` (wired in `hooks.json` with `--host claude`) closes
that gap. On every source — `startup`, `resume`, `clear`, `compact` — it injects a
best-effort bootstrap block assembled by `lib/session_context.py`:

- the **resolved absolute** plugin root + host-tool-map path, so the §7.1 pointer-line *Read*
  lands on the real `hosts/<host>-tools.md` even when no variable expands;
- the project `CLAUDE.md` chain, the user `~/.claude/CLAUDE.md`, an env block (date + git
  email), and the auto-memory `MEMORY.md` head (keyed to the **main** repo, shared across
  worktrees) — parity with a native start.
- the distilled **covenant** (`rubric/covenant.md`) — ONLY when the project is
  superheroes-calibrated (and, like this whole bootstrap, only on Claude Code — Codex wires
  no `SessionStart` hook, so on that host the `configure`-written in-repo CLAUDE.md copy is
  the only carrier) (a storage-mode registry entry or hero calibration evidence; the probe
  is strictly read-only — never `mode_registry.resolve()`, which can backfill-write). The
  covenant is the imperative distillation of PHILOSOPHY.md (the six promises as standing
  orders + the hard lines + the session-charter pointer); it **subsumes** the older
  review-discipline note — its review-before-handback hard line carries the no-unreviewed-PRs
  convention and still points at the canonical `rubric/review-discipline.md`. Read from the
  plugin install, it reaches every session (including ad-hoc direct builds) with zero repo
  traces, in both storage modes. `configure` can additionally write a durable
  review-discipline copy into an **in-repo** project's `CLAUDE.md` (owner-gated, idempotent);
  it never offers that in out-of-repo mode.

It is **fail-soft**: each source is gathered independently; a missing/erroring one is omitted
with a one-line stderr breadcrumb (never the file contents) and the hook always exits 0, never
breaking a session. **Codex** wires no `SessionStart` hook, so it gets no bootstrap (out of
scope).

Scope boundary: this fixes the host-map **Read** (model-resolved, so an injected absolute path
is the lever). The `lib/` **bash** seam of §7.1 — skills shelling out to `lib/` helpers through
`${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}`, which the Bash tool does not expand — is a *different*
layer that context injection cannot fix; it is tracked separately
([#93](https://github.com/zwrose/superheroes/issues/93)) and the seam form here is unchanged.

### 7.5 Cross-engine contract (host-run-on vs engine-dispatched-to)

The **host** is the harness the plugin *runs on* (§7.1–§7.2 — Claude Code or Codex). The
**engine** is the agent a working role is *dispatched to* — `claude` (the default,
unchanged), `codex`, or `cursor` — chosen per role (reviewer engine, implementation
engine) by the owner in `configure`. These are orthogonal axes: the host is where the
plugin executes; the engine is which model family does a role's work. An engine is
selected *below* the host, at the dispatch leaf.

Two postures are held strictly separate, mirroring `model_tier`:
- **Engine *selection* fails open.** An unknown / unavailable / unauthorized / stalled
  engine silently degrades to Claude — the same posture `model_tier` documents for a bad
  tier ("a wrong/absent tier is a cost concern, never a safety one"). No run hangs or
  hard-fails on engine choice.
- **A completed external *result* fails closed.** A build or fix that fails or can't run
  verify stops; an unauditable run stops; an unreadable or incomplete review is re-run
  on Claude, never accepted as green. This reuses the existing gates — no new safety logic.

**Build-engine contract.** A builder's implementer subagents (the Workhorse charter,
`agents/implementer.md`) may run on an external engine instead of a Claude subagent: the
same implementer template is inlined verbatim (minus its frontmatter) into the external
dispatch prompt, so both paths carry identical instructions by construction.
`review-code`'s panel seats route the same way, resolved via `engine_adapter.py`. The
engine axis is orthogonal to the model tier: `model_tier` still governs *which Claude
model* runs when the engine is `claude`; when the engine is external,
`engine_pref.resolve_effort` governs the engine's depth. Every external dispatch also
threads the role's resolved model into the engine argv as a dispatch fact —
`lib/model_registry.py` (the vendor registry + role×vendor matrix) decides what
actually runs; the adapter and `engine_pref` re-derive from it.

Codex tier map: haiku=gpt-5.6-terra, sonnet=gpt-5.6-terra, opus=gpt-5.6-sol.
An optional per-role `enginePreferences.codexModels` pin may select one of those
canonical IDs; a one-run preflight pin wins over the persistent pin, which wins
over tier mapping. The provider-specific pin is carried separately from the shared
tier so a failed Codex dispatch falls directly open to Claude with a valid native
model — never automatically downgrading to another GPT model. Effort stays
orthogonal: existing role defaults remain, and `max` is owner-opt-in only. The
registry validates a codex `(model, effort)` before dispatch (the CLI does no
client-side effort validation), rejecting an unknown effort fail-loud. A tier or
pin the target engine **cannot honor** — e.g. an anthropic-only `fable` tier
routed to codex or cursor — **fails loud** (the role falls open to Claude, where
that model lives); there is **no cross-family substitution** (this replaces the
old silent `fable→gpt-5.6-sol` remap). The GPT-5.6 tier requires a sufficiently
new Codex CLI; an unavailable model follows the observable fall-open path to
Claude, never a guessed version gate. Dispatch provenance — the concrete engine,
model, and effort actually used — is recorded in the PR body (the Workhorse
charter's "dispatch provenance" section), not a separate journal.

**Cursor is the token-efficiency engine** (owner-ratified 2026-07-09): Cursor is a
**gateway CLI, not a single vendor** — the same `cursor-agent` account dispatches
models from different families (the token-efficient `composer-2.5` is the cursor
family; `cursor-grok-4.5` is the xAI family; it can also reach Anthropic/OpenAI
models). Because of that, **panel independence keys on a model's family, not on
the dispatch CLI** (consumed by the review-composition work, #510). The default
cursor dispatch stays `composer-2.5`; premium/Anthropic models are never routed
through cursor by default. Each dispatch carries a role-appropriate timeout
ceiling and idle-stall watchdog (`engine_pref.resolve_timeout` / `resolve_idle`)
so a stalled external CLI is killed well before the ceiling; an owner may
override either limit via `enginePreferences`, and an override never disables the
ceiling.

**Confinement + hygiene.** External reviewers run read-only; external implementers run
workspace-write, confined to the builder's own worktree, with **no remote authority** —
the band owns every push / PR / merge, mechanically backstopped by the owner-authority
gate (a minimal PreToolUse hook, `LEDGERS.md` §1.1) that prompts the owner before any
merge/release/force-push shape, and never bypassed by an external engine. All external
free-text is secret-scrubbed at the adapter boundary (`engine_adapter.parse_result`) so
every downstream surface — including a `/review-code --post` PR comment — is clean. The
merge authorization is the owner's to grant; the band shows it and never applies it.

---

## 10. Ship-phase honesty gates

The deterministic per-phase gates (§10.1–10.6) that used to seed and park on these
markers as part of the v1 build/ship legs retired with the execution spine (#478) — only
the PR-body convention below survives, and only as a review-seat check, not a code gate.

### 10.7 PR-body honesty markers (survive as a review-seat convention)

Two PR-body markers from the retired execution spine survive independently of it:

- **Stub markers** — `# STUB(#NNN): <what is unwired and the live effect>` on any
  deliberately-unwired seam. Still **CI-enforced on source**:
  `.github/scripts/validate_stubs.py` fails any marker missing a valid issue reference
  (it does not hunt unmarked stubs — only under-specified ones already flagged).
- **Definition-of-done disposition table** (`superheroes:dod-table` marker) — one row
  per spec DoD bullet, each `done` (with an evidence pointer) or `deferred` (with a
  filed issue and reason). The **deterministic code gate** that used to seed and park on
  this table (`pr_entry.py`/`dod_gate.py`) retired with the execution spine (#478); the
  table now survives as the convention `rubric/review-discipline.md` documents —
  the **workhorse** charter's ready-PR section (§11) mandates authoring it and
  **review-code**'s review seat verifies it in PR mode (the deterministic gate is not
  reinstated; the mandate and the seat are the enforcement).

Both are cited by `rubric/review-discipline.md`, the canonical statement of the band's
review convention (no unreviewed PRs, §7.4).

---

## 11. One home per cross-boundary fact (single source of truth)

> **This is a repo-specific convention for us as builders of superheroes** — not (yet) a
> portable band contract like §1–§3, §6–§7. It earns its place here because superheroes'
> own source spans two languages (JS + Python libs), skill markdown, and fixtures, so
> the same fact is easy to re-type in four places. If it proves out, it can graduate into
> the portable rubric later, the way `review-discipline.md` did. Provenance: the PR #205
> phase-list defect ([#226](https://github.com/zwrose/superheroes/issues/226)), whose
> structural enabler was exactly this — two hand-maintained copies of a pipeline phase
> list in two languages, with no link between them ([#231](https://github.com/zwrose/superheroes/issues/231)).

**One home per cross-boundary fact.** A fact consumed across a **module or language
boundary** (event/verb names, schema field sets, verdict/reason tokens, path layouts,
reviewer rosters) has **exactly one authoritative definition**. Every other consumer
either **reads that home at runtime**, or keeps a **copy guarded by a drift test**
that reads the authoritative home and asserts equality — so a change to the truth **breaks
CI in every copy-holder**. **Two hand-maintained copies with no drift test is a
review-blocking violation, citable by name (this §).** A reviewer seeing a bare
constant re-typed from another language now has a rule to object with, citable by name.

**Scope — what counts.** The boundary is what matters, not the value. A constant with a
single owner and only same-module callers is not in scope (that is ordinary code). A fact
becomes cross-boundary when a **second language, module, skill doc, or fixture restates it**
so that the two can silently disagree. When in doubt, ask: *if I renamed the authoritative
copy, would anything else keep the old value and still pass CI?* If yes, it needs one of the
two patterns below.

### 11.1 Pattern 1 — shared data file (read the one home at runtime)

The fact lives in a **checked-in data file** that every consumer reads; no consumer
restates it. Best when the fact is plain data (a list, a field set, a map) and every
consumer can load a file at startup. *Illustrative:* a checked-in `reviewers.json` that
every consumer (a skill's doc-generation step, a Python harness) loads directly at
startup — one edit, both move; nothing to drift. Prefer this pattern for any new
cross-boundary fact with several runtime consumers.

### 11.2 Pattern 2 — copy + drift test (fail-closed reader + equality assertion)

A consumer keeps its own copy for ergonomics, but a **drift test parses (or reads) the
authoritative home and asserts equality**. The reader **must fail closed** — if it parses
nothing (literal renamed, moved, duplicated, or malformed) it raises rather than returning
an empty set that would make the equality vacuously pass. A rename of the truth then
**fails the drift test**, not production.

*Worked example 1 — the cross-charter boundary line.* Both session charters state the
identical two-sided fact — "Workhorse never merges/releases/bumps versions/wires the
board/re-scopes silently; Showrunner never builds." Neither charter is authoritative over
the other, so `lib/tests/test_charter_boundary_sync.py` is a **symmetric** Pattern-2
instance: it extracts the marked boundary line from both `skills/showrunner/SKILL.md` and
`skills/workhorse/SKILL.md`, fails closed if either is missing, and asserts the two are
byte-identical — editing one charter's boundary breaks CI until the other matches.

*Worked example 2 — the reviewer roster.* The authoritative home is the set of
`agents/*-reviewer` files. `lib/tests/test_dispatch_tables.py::test_code_reviewer_rosters_match_bundled_agents`
reads that directory listing and asserts it equals each hand-maintained copy —
`code_loop_plan.DIMENSIONS`, `spec_loop_plan.DIMENSIONS`, and the same roster re-keyed as
`AGENT_SUFFIX` in both modules — duplicate-sensitive (a copy that duplicates one slug
while dropping another cannot pass by set-collapsing). Adding, removing, or renaming a
reviewer agent breaks CI in every enumerated copy until it is updated to match.

**Caveat — a copy-list drift test is only as complete as the copies it enumerates.** A
**new** copy someone adds later is invisible until it is added to the test. So the
enumerating drift test must name every known copy-holder (a comment listing them), and
**adding a copy means extending the drift test** — checked at review under this §. When a
single runtime home is cheap to read, Pattern 1 sidesteps this failure mode entirely.

(The phase-list example that originally anchored this pattern retired with the execution
spine, #478 — its files no longer exist; the two worked examples above are its live
successors.)

### 11.3 Test corollary — a contract test must read the home, never restate it

**A test for a cross-boundary contract must not restate the constant** — it **imports or
reads the authoritative home**, or it is merely testing the copy against itself and proves
nothing. This is how #205's 172 green tests locked the defect in: they asserted the wrong
copy against a fixture that restated the *same* wrong copy, so the tautology passed while
the two real homes disagreed. A drift test that reads one copy and asserts against
a hand-typed literal of the same fact is the same tautology; the assertion's right-hand side
must trace back to the authoritative home (directly, or via the fixture the home also feeds).

---

## 12. Verification contracts (fix-ships-its-detector, real-seam tests)

> **Repo-specific convention for us as builders of superheroes**, like §11 — not (yet) a
> portable band contract. Provenance: the 2026-07-08 engine-fidelity escape
> ([#307](https://github.com/zwrose/superheroes/issues/307)–[#311](https://github.com/zwrose/superheroes/issues/311)),
> which penetrated every verification layer in place at the time, because every test of
> the seam stubbed the seam. These two rules are the layer-independent part of the fix.
> Grounding: [PHILOSOPHY.md](PHILOSOPHY.md) promises 2 (judgment the owner isn't
> expected to have) and 4 (never claim more than verified).

### 12.1 A fix ships its detector

**A PR that fixes an observed-in-production failure must ship the assertion that would
have caught the original escape** — at whichever tier fits the escape: a CI test, a
review-rubric question, a contract test. "Fixed" without a detector is a claim without a
receipt (promise 4): the class stays open even when the instance closes. This
generalizes the named-risk-needs-tripwire rule from owner-named risks to every
escape-class fix. A reviewer seeing a production-failure fix with no accompanying
detector now has a rule to object with, citable by name (this §).

### 12.2 At least one test exercises the real seam

**Every feature carries at least one test that runs the production call shape — real
store, real payload, real argv — without monkeypatching the seam under change.**
Monkeypatched-seam-only coverage is how thousands of green tests shipped an inert
feature: a suite that stubs the very boundary being changed verifies the stub, not the
behavior (promise 2's flagship trap — "the test suite that mocks the very thing it
claims to test"). Where the seam's far side is genuinely unreachable in CI (a paid
external engine, a login), the rule is satisfied by a **contract test against the far
side's real rules** (e.g. a validator enforcing the foreign schema dialect) plus a
**live round-trip receipt recorded in the PR** — not by asserting the near side's argv
alone. The review question is: *which test would have failed if this seam were broken
the way it actually broke?*

---

## 13. New deterministic machinery needs a named consumer and a ledger entry

In v2 the heroes are **prompts and conventions** — two session charters (Showrunner,
Workhorse) plus review/spec/test-pilot support — not a deterministic execution engine.
The v1→v2 pivot retired the execution spine precisely because prompts plus independent
review beat a hand-built orchestration layer for this job (PHILOSOPHY.md B1). The guard
against sliding back into one:

**Any new deterministic machinery — a hook, a gate, a decider, a validator — requires,
before it ships, both of:**

1. **A named consumer.** A specific hero or skill that actually uses the machinery
   today, not a future or hypothetical one. No producer without a consumer
   (PHILOSOPHY.md B7): a validator nothing reads, a gate nothing enforces against, is
   dead weight waiting to bit-rot.
2. **A ledger entry** in `LEDGERS.md` §1 (the bespoke-vs-platform ledger, PHILOSOPHY.md
   B6): the platform primitive that could absorb the job, why we still diverge from it,
   and the re-check trigger that retires the divergence when the platform catches up.

Both are load-bearing, not paperwork: a hook without a named consumer is exactly how a
charter re-accumulates the spine's machinery one "just this one small check" at a time;
a hook without a ledger entry is an unexamined divergence with no trigger to retire it.
The restored owner-authority gate (`LEDGERS.md` §1.1 — a minimal PreToolUse hook
mechanically enforcing the never-merge/never-release line) is the live example of a
divergence that earned its entry: it names its consumer (every session, via the
covenant's hardest line), states the platform primitive it awaits (plugin-shippable
native permission rules), and carries the trigger that retires it.

This rule is enforced the same way review discipline is: at review, a reviewer citing
this section is enough to block a hook or gate that skipped either step.
