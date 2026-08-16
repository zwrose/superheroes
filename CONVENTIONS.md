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
14. [Owner involvement before the merge click](#14-owner-involvement-before-the-merge-click)
15. [Builder liveness heartbeat](#15-builder-liveness-heartbeat)

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
  big asks into small mergeable issues, drafts the builder's launch prompt (command + issue
  pointer; durable build context lives in the issue), vets every PR from its artifacts against the
  issue/spec and the build brief, owns board hygiene and release coordination, keeps
  durable memory. **Never builds.** The never-delegable act is the **approval** — the gate
  click, the release cut, the publish decision. **Merge-command execution** is delegable, but
  **only where a mechanical per-merge approval checkpoint exists on that host or path**; where
  none exists, execution stays in the owner's hands. **Release PRs and anything needing a
  force-push are never delegated.**
- **Workhorse** — the builder session: issue-scoped, disposable, parallelizable. Takes a
  routed issue, writes and gets the build brief checked, delegates all implementation to
  tiered subagents or engines, verifies every receipt itself, runs test-pilot and
  multi-model review, hands back a ready PR with dispositions and receipts. **Never
  merges, releases, bumps versions, or wires the board.**
- **The Architect** — turns fuzzy intent into an owner-approved `spec` (discovery → spec
  → `review-spec`). Narrowed in v2: it produces the `spec` only — no `plan`, no `tasks`
  (retired, #479).
- **Review Crew** — the multi-model review layer: the spec panel (`review-spec`) and
  `review-code`'s cross-vendor build review. The **spec panel runs six doc-native lenses**
  (Clarity, Verifiability, Failure-Mode, Coherence, Safety & access, Grounding) while
  `review-code` runs its five code reviewers — the honest doc-native identities that
  replaced the "five code costumes" (#514 D1). (#34 proposed merging the code and test seats
  as the weakest, on ~70% zero-finding early small-N data; at N=37 those are the two
  strongest seats — Verifiability has the most blocking findings of any seat — and the
  genuinely weak seat was architecture, since recast as Coherence.) Panel composition is
  **composed to complement** the builder's vendor so the maker's vendor never dominates its
  own checking.
- **Test-Pilot** — browser-evidence verification: plans derived from the spec/issue,
  executed for real. Observe-and-report only — a bug it finds becomes a work order, it
  never fixes.
- **Guardian** — the maintainability guardian: periodic read-only sweeps of repo health;
  findings reach the owner as consequences; never edits code, never files issues itself,
  never runs or owns enforcement. (Its authoritative definition lives in `skills/guardian/SKILL.md`.)

Two heroes run sessions; four serve inside them. The band posture above (degrade, not
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

**Guardian artifact subtree.** The Guardian hero (§1) adds a `guardian.md` calibration layer
(a per-plugin layer like any other) plus a `guardian/` artifact subtree beside `core.md`,
holding its sweep outputs: a report, a drift-baseline snapshot, a dispositions ledger (with
its per-lens report card), and an append-only vitals trend file. In in-repo mode these are
committed with the repo (findings are visible to collaborators; the artifacts dirty the working
tree until committed); in global mode they live in the project store. The advisor is the
sole automated writer of `guardian/ledger.md` (closures and the per-lens report card),
written at consult/triage via `commit-ledger`; the deterministic sweep `finalize` is
**read-only** on the ledger and writes only the report, the baseline snapshot
(`latest.json`), and the vitals trend append (`vitals.jsonl`). The sweep **never commits,
pushes, edits code, or files issues.**

The dispositions ledger record shape (authoritative home: `guardian_ledger.LEDGER_RECORD_FIELDS`)
carries `id`, `disposition`, `date`, `issue`, `metricAtDisposition`, `reason`, and
`reraiseWhen`. The report card grades each lens from adjudicated outcomes: `filed`,
`verified-fixed`, `accepted`, and `reopened` count for; `triaged-out` and `declined` count
against (authoritative home: `guardian_ledger.OUTCOMES_FOR` / `OUTCOMES_AGAINST`). Vitals
tracked each sweep (`locTotal`, `fileCount`, `duplicationPercent`, `todoCount`, `majorsBehind`,
`vulnCount`, `couplingEdges`, `suiteRuntimeSeconds`, `suiteTestCount`, `suiteSkipped`; authoritative home:
`guardian_vitals.VITALS`) each carry a drift threshold (authoritative home:
`guardian_vitals.DRIFT_THRESHOLDS`).

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
  `json test-pilot-config` block moves into `test-pilot.md` verbatim). That block may
  carry an optional nested `pilot` key whose normative field table, refusal tokens, and
  probe vocabulary live in `plugins/superheroes/reference/pilot-contract.md`.
- **`guardian/vitals.jsonl` provenance (deliberate §2.2 reading).** The vitals trend file
  must both carry provenance and stay valid JSONL — an HTML comment would not parse. Its
  first line is therefore a JSON provenance object (not an HTML comment), written once at
  creation; readers validate and skip it.
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

**Provenance / citations (#517, owner-ratified #514 D3).** A load-bearing **mirror-fact** — a
spec sentence asserting something about the *existing repo* that the repo could contradict
("reuses/extends the existing X", "the current limit is N", "today the system does Y") — carries
an inline **citation** naming its repo source. A **definition** (a new behavior the spec itself
defines — the owner's *what*) carries none: it is the source of truth and mirrors nothing. The
**mirror-vs-definition test** decides — "could today's repo contradict this sentence?" YES →
mirror-fact → cite; NO → definition → no cite. A **noise budget** keeps citations rare: only
load-bearing mirror-facts (ones the build relies on being true) get one, and a citation-dense
spec is usually leaking the build's *how* (itself a finding). The citation grammar's one
authoritative machine home is `plugins/superheroes/lib/citation_validator.py`
(`CITATION_RE`); `templates/spec.md` carries the canonical example as the §11 drift witness, and
this section describes the rule rather than restating a second machine-parseable literal. A
deterministic **dangling-citation validator** (existence + anchor resolution, fail-closed) runs in
`review-spec`'s compile step and is **advisory** — review-spec is owner-gated, so the validator
produces findings the owner adjudicates and never blocks or writes `passed`. **Content-match** —
whether the cited source actually *says* what the spec claims — stays the Grounding verifier's
judgment, not the deterministic check's.

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
- **`<common-dir-key>`** = `short_hash(realpath(git-common-dir))` — shared across a clone's
  linked worktrees. Serves as the **no-remote config-key fallback** (§2.4). Resolution is
  fail-closed in `store_core.get_gitdir`: `--path-format=absolute --git-common-dir` first;
  for git < 2.31 the bare `--git-common-dir` result is joined onto the target `cwd` (never
  `realpath`'d against the process cwd); then `--absolute-git-dir`. A nonexistent joined
  path raises `RepoRootUnavailable` (never hashed). Genuine greenfield (no `.git` ancestor,
  no `GIT_DIR`/`GIT_WORK_TREE`) alone returns `realpath(cwd)`; broken or indeterminate
  shapes raise `RepoRootUnavailable`.
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

The Artifact paths in this table are relative to the **plugin root**
(`plugins/superheroes/`), not the repo root.

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
  on Claude, never accepted as green. A review seat that returns a well-formed empty result
  **without a verifiable investigation record** is incomplete, not clean — a named **vacuous**
  forfeit on the same fall-open path (`review-code` reference: `auto-fix-loop.md`, `round-driver.md`).
  Engine telemetry corroborates engagement but never substitutes for that record. This reuses the
  existing gates — no new safety logic.

A **configuration gate** is a third, distinct control: an invalid engine×tier combination
is refused at configure/calibration time and cannot be saved — not an engine-selection
degrade and not a post-hoc result check.

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
client-side effort validation), rejecting an unknown effort fail-loud. An
anthropic-only `fable` tier configured onto a role whose engine preference routes
external (codex or cursor) is **refused at configuration time** — a loud validation
error at configure/calibration time, named `fable-on-external-engine`, raised by the preflight's
`dispatch-vocab` probe (which reads the project's configuration), by `dispatch_selftest.run` when
a caller supplies that configuration, and by both configure-facing write paths (the tier writer
and the engine-preference writer), so an invalid combination cannot be saved in the first place; there is **no cross-family
substitution** (this replaces the old silent `fable→gpt-5.6-sol` remap). Fable's
long-term availability on Max plans removes the reason a graceful degrade ever existed.
The dispatch-time named refusal (`fable-unrunnable`) **remains as defensive depth** for
callers that bypass configuration, but is unreachable from a valid configuration.
`core_md`'s engine-preference write gate, `model_tier_overrides`' tier-writer gate, and the
preflight `dispatch-vocab` probe read the project's `core.md`
through a single accessor that reports `absent`, `ok`, or `unreadable`. A **present but
unreadable** `core.md` — a non-regular file, a dangling symlink, a file with unreadable
permissions, or a corrupt file — is **refused at configuration time** by name as
`core-md-unreadable` rather than treated as absent; `dispatch_selftest.run`
refuses the same condition when the configuration bundle carries `read_error`.
When git cannot be run and the repository root is unknown, the accessor reports
`root-unavailable` as `repo-root-unavailable` rather than `core-md-unreadable` or
`legacy-profile-unsupported`. A genuinely absent `core.md` (with a known repo root)
remains a clean create. A gate that treats an unreadable config as "no config"
**fails open**, which is the failure this closes. The
GPT-5.6 tier requires a sufficiently
new Codex CLI; an unavailable model follows the observable fall-open path to
Claude, never a guessed version gate. Dispatch provenance — the concrete engine,
model, and effort actually used — is recorded in the PR body (the Workhorse
charter's "dispatch provenance" section), not a separate journal.

**Cursor is the token-efficiency engine** (owner-ratified 2026-07-09): Cursor is a
**gateway CLI, not a single vendor** — the same `cursor-agent` account can also reach
Anthropic/OpenAI models. But its **two first-party models — the token-efficient
`composer-2.5` and `cursor-grok-4.6` — are ONE family, `xai`** (owner-ratified
2026-07-26, #651; **post-acquisition, Cursor was acquired by SpaceX/xAI, closing
2026-08-14** — cursor and xAI now sit under one corporate roof as fact, not merely
proximity; correlated errors from one roof get harder to detect over time, and
claude/codex are at least as likely to catch what grok catches). The `xai` key is an
**independence-accounting label**, not a dispatch input and not vendor-attribution
machinery — **panel behaviour is unchanged** by this affiliation update. So
**independence is never satisfied between two cursor first-party models** — a
cursor-grok reviewer is NOT independent of a cursor-composer fix, and the
composer→grok audit lane is closed. Because a gateway CLI still spans
families, **panel independence keys on a model's family, not on
the dispatch CLI** (consumed by the seat map, `lib/seat_map.py`, #510; owners supply
per-seat pins via `enginePreferences.seatPins`, which the seat map reads). The seat map
**bars the maker's model family from rotation onto every panel seat** — all five lens seats and the
`grounding-seat` (#670, owner-ratified 2026-07-26), including seats that are neither
strong-tier nor critical (closing the `test-reviewer` hole after #651 unified cursor's
first-party models under one `xai` family). An owner pin can still seat the maker family on a
panel seat; `verify()` then flags a `maker-family` violation and records a
`pin-breaks-constraint` degradation naming the seat. Where an alternative family is live, the maker
family simply never seats through rotation. Where **no** alternative family is live, the seat still fills
with the maker family and the map records a disclosed `same-family` degradation, which
rides the certification shape (`-degraded`) alongside `independenceDegraded` and
`baseDegraded` — a single-vendor panel still certifies degraded, it does not halt.
`verify()` treats a maker-family seat as a **violation** when an alternative family was
reachable, and as **not** a violation when unavoidable (the degradation path); unusable
liveness evidence — missing recorded `liveVendors`, synthesized liveness defaults,
pin-scoped probes, malformed vendor names — **fails closed to violation**, and only a
well-formed, registry-resolvable receipt authorizes the degradation branch. When neither
narrative nor maker can seat the grounding seat independently, **maker exclusion outranks
narrative independence**: the fallback prefers the narrative family over the maker's own.
The cursor CLI's only sanctioned use is the models Cursor bills as **first-party** — today
`composer-2.5` and `cursor-grok-4.6`, and nothing else, ever. Claude, GPT, or any
other third-party model is **never** routed through cursor. The registry
(`lib/model_registry.py`) is the **enforcing surface**: it admits only those two cursor
models, so this is doctrine backed by a gate rather than a convention on trust. The
registry also pins the judge model to a single sanctioned effort (`xhigh`); an
off-calibration or `-fast` variant is **refused at the dispatch boundary**
(`validate_config`, `dispatch_token`, `parse_dispatch_token`) rather than merely
absent from the ladder. This codifies standing owner policy — the cursor fable channel
is retired in code and fable-via-cursor is dead. The default cursor dispatch stays `composer-2.5`. Each
dispatch carries a role-appropriate timeout
ceiling and idle-stall watchdog (`engine_pref.resolve_timeout` / `resolve_idle`)
so a stalled external CLI is killed well before the ceiling; the ceiling is never
disabled, and these limits are not owner-configurable through `enginePreferences`
(that channel was retired as dead surface).

**Seat-map preflight economics** (#610): the composition preflight that decides which vendors are
live for the panel is **gated, cached, and pin-scoped**. It runs only on panel-dispatching entries —
`--post` and any receipt-only path reuse a fresh **short-TTL machine-readable liveness receipt** or
fall open to Claude, never re-probing; a compose within the TTL rides the receipt (the workhorse
intake preflight can seed it); and only **pin-reachable** models are probed. The **fail-direction is
unchanged**: a probe failure still drops the vendor loudly (disclosed degradation); the cache only
ever skips re-proving recent liveness, and never converts a failure into a pass.

**Confinement + hygiene.** External reviewers run read-only; external implementers run
workspace-write, confined to the builder's own worktree, with **no remote authority** —
the band owns every push / PR / merge, mechanically backstopped by the owner-authority
gate (a minimal PreToolUse hook, `LEDGERS.md` §1.1) that prompts the owner before any
merge/release/force-push shape, and never bypassed by an external engine. The
never-merge floor (`lib/owner_authority.py`) is another name for this owner-authority
gate; the owner-approval rule (`PHILOSOPHY.md` §4, ruling #706) is the doctrine the gate
backstops — where the gate does not fire, the rule still governs. A second
Claude Code hook (`LEDGERS.md` §1.1) denies git commands that would irrecoverably
discard uncommitted worktree content — the checkout-revert wipe class every implementer
and mutation-probe path can trigger. All external
free-text is secret-scrubbed at the adapter boundary (`engine_adapter.parse_result`) so
every downstream surface — including a `/review-code --post` PR comment — is clean. The
merge authorization is the owner's to grant; the band shows it and never applies it.

**Headless builder launch contract.** A headless builder launch is composed through
`lib/launcher.py` from the versioned doctrine artifact (`rubric/launch-doctrine.md`, parsed
fail-closed by `lib/launch_doctrine.py`) — never reconstructed from session memory
(LEDGERS.md §4 seat ruling B). The launcher stamps the premise durably at dispatch in
`lib/launch_ledger.py`: base commit, surfaces, enumerated grant scope, owner-capability
preconditions with a stated horizon, and the standing exclusions it applies itself (release
PRs excluded, force-push never). **The launcher also provisions the build worktree** (#974):
`launch` creates it before spawning — one per launch, detached at the premise's base commit,
under `SUPERHEROES_WORKTREES_ROOT` when set and `~/.superheroes-worktrees` otherwise — records
its path and the builder's session id on the `reserved` record, and starts the session with that
worktree as its working directory, never the primary checkout. A target path that already exists on disk, or that git
still registers, is a **collision**: the launch refuses (`launch-worktree-collision`) rather than
reuse a checkout another build may be holding. The `own-worktree` standing ruling stays in the
composed prompt as defense in depth — a builder that never sees the primary checkout cannot
violate it. That record carries R1's mechanical park/refusal accounting
— it reports **indeterminate** rather than a rate whenever it cannot see the whole batch; zero
parks is a signal to inspect, never a clean sheet. The same record also carries **post-terminal
amendments** — a second terminal-outcome write, an advisor vet ruling, or an evidence correction —
recorded without mutating the terminal outcome and surfaced by `count` beside the terminal tallies.
`count` reads **lanes** (a build intent keyed by issue number — retried attempts belong to one lane)
with an `attempts` tally beside the terminal ones and per-lane `laneDetail`; overlapping same-lane
launches still refuse — see `lib/launch_ledger.py` for the authoritative semantics. The ledger's event grammar is version-coupled: a record kind an older build does not understand makes
every door fail closed with `fold-unknown-event:<kind>` until the ledger file is deleted (the path
`ledger_path()` reports). The
Showrunner advisor invokes the launcher
per launch; the eight dispatch-preflight checks live in
`skills/showrunner/reference/dispatch-preflight.md` and the artifact, bound by a drift test — cite
those homes, do not duplicate them here. The recovery half —
adopt-rather-than-resume across instances or accounts, the unpushed-work sweep, transcript
pinning, liveness reads, and quota-death suspicion — lives in `rubric/launch-doctrine.md` §
Recovery, with the two session charters as enumerated copy-holders guarded by a drift test.

**Sanitized review view (#684).** External **review** seats (codex/cursor via `dispatch-review`)
run against a disposable sanitized export of the named repo root — machinery inside the runner, not
orchestrator discipline. The runner can stage the reviewed change as a patch inside the view via
optional `--diff-base <commit-oid>` (a pinned commit object id) (merge-base→head in the source repo, written to
`SUPERHEROES_REVIEW_DIFF.patch` before the view's synthetic commit); paths matching the stripped-config
predicate are withheld from that patch by the same rule that strips the tree. The staged patch does
not satisfy the #666 investigation floor — citing only that artifact forfeits vacuously. A view that
cannot be built is a named refusal with `attempts: 0` and no spawn; there is no fallback to the raw
checkout. The census of changed paths is authoritative: it comes from direct two-tree enumeration,
not from `git diff` output or rendered patch text, and every changed recursively enumerated
non-tree entry — blob/file, symlink or gitlink — must be rendered, policy-withheld, or refused
before spawn. The merge-base is resolved outside the reviewed repository's git directory (scratch
repository linked only through the object store, with every inherited `GIT_*` variable dropped), so
git-directory ancestry overlays — grafts, replace refs, shallow metadata, config — cannot shrink the
changed set. **Commit-graph data is the stated exception**: it lives in the object directory the
alternate exposes and is excluded instead by the documented `-c core.commitGraph=false` reader-wide pin
on every commit-peeling source-repository command, so that half of the guarantee is conditional on
the git executable honoring it. Dispatch refuses when
authoritative ancestry cannot be established, and any shallow-state answer other than exact
`true`/`false` is itself a refusal; empty directory additions and removals are tree-only and outside
this contract. Repo-local config overrides remain defence in depth, not the proof of authority. Until a follow-up issue lands, opaque or unaccounted patch content refuses
with `sanitized-view-diff-opaque`, `sanitized-view-diff-unaccounted`, or (for git command failure)
`sanitized-view-diff-failed`; that result is never a clean review and there is no automatic fallback.

**Dispatch vocabulary contract.** Three token shapes stay distinct:

1. **Registry ids + a separate effort** — what the registry APIs and `engine_model` accept
   (e.g. `cursor-grok-4.6` with `xhigh`).
2. **Composed dispatch tokens** — what `dispatch_token` emits and the engine CLI argv carries
   (e.g. `cursor-grok-4.6-xhigh`).
3. **Family keys** — independence accounting only (`anthropic` / `openai` / `xai`);
   not a dispatch input.

`model_registry.resolve_dispatch` is the single seam that converts a registry id, a composed
token, or the seat default into a concrete `(model_id, effort, dispatch_token)` triple;
`parse_dispatch_token` is the inverse of `dispatch_token`. A dispatch token only encodes
effort where the vendor's CLI does — cursor's grok token does; claude and codex tokens do
not — so effort travels alongside the token, never inferred from a token that does not
encode it. Every refusal at the dispatch boundary is **named**
(`engine_adapter.build_argv_result` → `engine_dispatch` `detail: "engine-config:<reason>"`);
a nameless fall-open is a defect. The round-trip self-test (`lib/dispatch_selftest.py`
`run()` / its preflight probe) keeps the three shapes honest.

---

## 10. Ship-phase honesty gates

The deterministic per-phase gates (§10.1–10.6) that used to seed and park on these
markers as part of the v1 build/ship legs retired with the execution spine (#478) — only
the PR-body convention below survives, and only as a review-seat check, not a code gate.

### 10.7 PR-body honesty markers (survive as a review-seat convention)

PR-body markers from the retired execution spine survive independently of it:

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
- **Build-record boundary** (`<!-- superheroes:build-record -->`) — everything **above**
  this marker in the PR body is the *owner half*; everything **below** it is the *build
  record*. The marker sits immediately above the opening `<details>` that wraps the build
  record — a pure owner-side gain: an agent reading `gh pr view --json body` gets
  identical raw markdown. It gives **#609** a clean staging boundary for live grounding
  dispatch and gives the advisor's follow-ups backstop a **grep anchor**.
- **Disclosed degradations** (`<!-- superheroes:degradations -->`) — immediately followed
  by `### Disclosed degradations` and a list of bullets (one per degradation: what was
  promised, what was delivered instead, and why), or the single word **None** when there
  are none. Ratification amendment F2: disclosed degradations are **prose** in every PR
  examined, so without a marker the omission floor's third row would be a judgment call
  rather than a mechanism.
- **Vet-receipt markers** — three markers ratified from #672, **written at vet, after handback** —
  except the one the builder pre-stamps (below). Two of them live in the vet-receipt **comment**, not
  the PR body, so this bullet names a
  **PR-artifact** family rather than extending the body-marker family above; each marker's home and
  lifecycle is part of the contract:
  - `<!-- superheroes:vet-receipt -->` — the **first line of the vet-receipt comment**.
  - `<!-- superheroes:pending-proposals -->` — **inside that same comment**, immediately above the
    pending disposition set, whose body is either the items or the literal **None**.
  - `<!-- superheroes:advisor-vet -->` — the only one in the **PR body**: the **append-only** boundary
    of the advisor's write inside the `## Advisor vet` owner-half slot. Unlike its two siblings it is
    **builder-emitted at handback** — the workhorse charter's §11 skeleton stamps it into the empty
    slot, together with an advisor-facing reminder comment beneath it that the advisor's write
    replaces — and the advisor writes **beneath** it, re-stamping it only when a body rewrite dropped it.

  Receipt shape and the owner-half register live in
  `plugins/superheroes/skills/showrunner/reference/vet-receipt.md` — the authoritative home;
  **when** the vet runs and what else it does are the **showrunner** charter's duty 4. This bullet
  names the literals and their locations, and does not restate the receipt's shape.

  **Lifecycle — and why nothing flags their absence.** `advisor-vet` **is** a builder obligation
  (the §11 skeleton stamps it); the other two are not, and **none of the three is a review-seat
  check**: a build's pre-handback `review-code` runs in
  **branch mode**, before any PR body or vet exists, so a missing vet-receipt marker at review time is
  the **normal** state and must never be emitted as a finding. (The §11 drift test enumerates this
  section's marker inventory and holds this family **out** of the copy-holders for exactly that reason —
  a docs-consistency check, not a consumer of these markers at review time.) Their absence becomes meaningful only
  **at vet or re-vet**, and only to the advisor. They exist as grep anchors for the **advisor's own**
  backstops: `pending-proposals` is what makes a carried item's age inspectable (an item proposed two
  or more vets ago owes an escalation line), and the **reminder comment** the builder seeds beneath
  `advisor-vet` is how a body rewrite that re-created the slot heading while dropping the advisor's
  write gets noticed: a slot still carrying the reminder is a vet not yet written, while a slot
  carrying neither reminder nor verdict is a write that was dropped. Marker-presence no longer
  separates those two states, because the builder stamps the marker.
  A slot with **no marker at all** is read against the advisor's own receipt: with no receipt comment it is a body predating the contract (*not yet vetted*); with a receipt already posted it is a rewrite that dropped the verdict and marker together.
  Because the receipt is posted before the body write, a standing reminder means the **owner-half write** is owed — the receipt may already exist, so the advisor checks for its own existing receipt comment before posting another.

**Omission floor (owner half).** Anything the owner still **carries after merging** appears
in the PR's owner half, **stated as a consequence**. The checkable floor beneath that
principle — because a model judging *"is this a consequence?"* is not a tripwire — is three
rows that must appear under `## What we're accepting`:

1. every **deferred** DoD row;
2. every **blocking or important** review finding that was **not fixed**, whatever its
   disposition is called;
3. every **disclosed degradation**.

A **missing** `<!-- superheroes:build-record -->` boundary marker or a **missing**
`<!-- superheroes:degradations -->` section is **itself** a review finding — same
**Important** / `tradeoff` / author-resolved shape as the DoD-table check, not a silent
pass. An empty degradation list is only clean when the section body is the literal word
**None**; marker absence and **None** are different states. Every copy-holder of this
floor — `rubric/review-discipline.md` (Ship-phase honesty), `skills/workhorse/SKILL.md`
§11, and `skills/review-code/SKILL.md` step 8 — restates it as an inline enumerated
triple in order after the omission-floor anchor, using one accepted marker shape across
all three rows (the accepted shapes are defined in
`plugins/superheroes/lib/tests/test_ssot_drift.py`); that enumerated shape is what makes per-row drift
mechanically detectable rather than a judgment call, because a copy that merges the three
rows into prose can silently lose one.

The hook is **severity, not disposition status**: keying on "parked" misses a genuine
**Important**-severity race dispositioned "Deferred — follow-up"; severity is already
carried by every dispositions table, and keying on it keeps craft nits below the bar.

No new machinery, and no waiting: the home is `skills/review-code/SKILL.md` step 8, the
existing *PR-body honesty check (PR mode only)* — already PR-gated, already reads the
`superheroes:dod-table` marker, already emits an **Important** / `tradeoff` /
author-resolved finding. The floor is the **same check emitting the same finding shape**.
Step 8 catches the floor on any review of an **existing** PR; a build's pre-handback
`review-code` run happens **before** the PR is opened, so it runs in **branch mode** and
skips step 8 — the **advisor's vet** is the ratified independent checker for the
principle in every case (do not re-order the build or add a new body-aware pass here).

The principle-level checker is the **advisor's vet**, not step 8 — step 8 runs in the same
session that wrote the body, so it is the author checking whether the author forgot: fine
for presence-matching, weak for judgment. Adopted for the vet: scoped to the **principle
only** (the vet does not re-run the floor's presence match); lands as a **mandatory receipt
field with an explicit `None`**; **#609 does not retire it** — when the dispatched grounding
seat lands, the vet becomes the backstop for that seat being absent, vacuous, or
misconfigured, so **the principle is not sequenced behind #609**. `agents/grounding-seat.md`
is deliberately narrow (beyond pointer fixes elsewhere); that narrowness is what makes the
seat reliable.

This self-claims / DoD-grounding check is formalized as the **grounding seat**
(`plugins/superheroes/agents/grounding-seat.md`, `reviewer` tier — never `mechanical`,
since a false "claims check out" is a silence nothing downstream re-checks); it is
currently instantiated by the **review-code** orchestrator inline (the interim
mechanism — the PR-body honesty check above), with live dispatch owned by #609.

Markers and the omission floor are cited by `rubric/review-discipline.md`, the canonical
statement of the band's review convention (no unreviewed PRs, §7.4).

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

**Concrete model ids — roles in authored prose.** Charters, agents, rubric, and skills
reference **roles**, never concrete model ids; only `skills/configure/` may name them.
Enforced by `lib/tests/test_ssot_drift.py::test_no_concrete_model_id_in_charters_or_skills`.

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

*Worked example 1 — the cross-charter boundary line and cross-lane invariants.* Both session
charters state the identical two-sided fact — "Workhorse never merges/releases/bumps versions/wires
the board/re-scopes silently; Showrunner never builds — except the **micro** lane, a named
hard-line edit defined in the showrunner charter." Neither charter is authoritative over the other,
so `lib/tests/test_charter_boundary_sync.py` keeps a **symmetric** byte-identical equality check on
that boundary line between `skills/showrunner/SKILL.md` and `skills/workhorse/SKILL.md`. The same
file now also carries **asymmetric** rows for named cross-lane invariants — **resolve-upward**, the
**not-engaged-never-passes** probe rule, and the **waiver bounds** — where
`rubric/review-discipline.md` is the authoritative home and the charters hold deliberate
paraphrases. Those rows are **clause-presence sentinels**, not byte-equality or semantic equality.
Each shared clause is checked in **exactly one** named home section; each copy-holder is checked in
**exactly one** named section in that file. Shared clauses are **first verified present in the home**
(§11.3); `holder_clauses` pins holder-specific wording where the home states the same bound in
different words — a narrower, holder-specific guarantee, not home-derived. The guard fails closed if
a declared heading is missing **or duplicated**. **Residual blind spots:** (1) the home gaining a new
qualifier, scope, or exception the copies do not mirror; (2) a copy keeping every clause verbatim
while adding a contradicting exception nearby; (3) matches spanning a boundary after normalization;
(4) `holder_clauses` being holder-specific, not home-derived; (5) same-section, different-paragraph
satisfaction — a clause pinned to a section can still be satisfied by a different paragraph in that
section; (6) the spine's own waiver sentence is not separately pinned. The waiver row's
copy-holders are the **showrunner** charter only, because micro is the showrunner's lane.

*Worked example 2 — the reviewer roster (sanctioned-subset invariant).* The set of
`agents/*-reviewer` files is the single home of the **sanctioned reviewer universe** — now
six, including `grounding-reviewer`. The two dispatching legs each run a **sanctioned
subset** of that universe, not the whole of it: the **code leg** (`code_loop_plan.DIMENSIONS`)
is the five code reviewers, and the **spec leg** (`spec_loop_plan.DIMENSIONS`) is all six
(`grounding-reviewer` is **spec-leg-only** — the doc-provenance seat with no review-code
agent). `lib/tests/test_dispatch_tables.py::test_code_reviewer_rosters_match_bundled_agents`
reads the `agents/` directory listing, derives each leg's sanctioned roster from it
(`universe − grounding-reviewer` for the code leg, `universe` for the spec leg), and asserts
**exact per-leg equality** against each hand-maintained copy — `code_loop_plan.DIMENSIONS`,
`spec_loop_plan.DIMENSIONS`, and the same rosters re-keyed as `AGENT_SUFFIX` in both modules.
The check is fail-closed and duplicate-sensitive (a copy that duplicates one slug while
dropping another cannot pass by set-collapsing), and a partition guard pins the spec leg as
exactly the code leg plus the spec-only `grounding-reviewer` seat (`spec_roster − code_roster
== {grounding-reviewer}`). Adding, removing, renaming, or mis-legging a reviewer agent breaks CI in
the affected copy until it is updated to match. Separately, the runtime
`spec_loop_plan.sanction_dimensions` guard enforces the same invariant at dispatch time: a
leg may run a subset, but only of sanctioned seats — an unsanctioned `--dimensions` input is
dropped, never widening or corrupting the roster.

*Worked example 3 — the issue-contract vocabulary.* The three slot names and their order
(`Anchor:`, `What:`, `DoD:`), the three anchor-kind tokens, and the five build-ready
refusal-reason tokens (`anchor-slot-missing`, `anchor-slot-empty`, `anchor-kind-unrecognized`,
`anchor-kind-ambiguous`, `body-unreadable`) are a cross-boundary fact: they are stated in
`plugins/superheroes/lib/issue_contract.py` and restated in
`plugins/superheroes/skills/showrunner/reference/issue-contract.md`. The authoritative home
is the Python module — exactly as `citation_validator.py`'s `CITATION_RE` is the home for
the citation grammar. The reference doc's `## Vocabulary (drift-tested)` section is
drift-tested against the module by `lib/tests/test_ssot_drift.py`; that reader **fails
closed** — if it parses nothing (heading renamed, block reformatted) it raises rather than
passing vacuously.

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

### 11.4 Pattern 3 — pointable step-body (the dispatched consumer cites, never copies)

The fact is a **step-body** — an ordered procedure that produces an artifact — and one of its
consumers is a **dispatched subagent or external engine, which has no Skill tool and cannot reach
a skill at all**. Patterns 1 and 2 both assume the consumer can read the home or that a test can
compare two copies; a work order handed to an implementer can do neither, so the step list gets
**inlined verbatim into the order**, and the inline copy drifts.

**The rule.** A write-path skill's step-body lives at a **pointable reference path** — a file under
that skill's `reference/` — and the `SKILL.md` step section **points at that file rather than being
its sole home**. Orders, agent prompts, and dispatch prompts then **cite the path**; they never
paste the body. One home, one edit.

*Worked example — test-pilot's execution steps.* The eight steps live at
`skills/test-pilot-execute/reference/execution-steps.md`; `skills/test-pilot-execute/SKILL.md`
points there, and `agents/pilot.md` — a dispatched subagent with no Skill tool — cites the same
path instead of restating the interaction-calibration and failure-classification rules, which it
previously kept as a condensed second copy. (`skills/review-code/reference/setup.md` is the same
shape arrived at independently.)

**Fail direction — a cited path that does not resolve fails loudly, never silently.** That
loudness is the whole reason a pointer beats an inline copy: an inline copy that has gone stale
still reads as authoritative, whereas a dangling pointer is visibly broken. It is enforced on two
sides. **At order-read time**, the consumer stops and reports rather than substituting memory or a
guess (`agents/implementer.md`, `agents/pilot.md`). **In CI**, `validate_skills.py`'s
`check_citations` scans those same trees for path-like inline-code citations and fails the build when
one does not resolve from the plugin root. That check found three dangling citations already in the
tree when it was introduced.

**Citations are self-contained.** Write the **full plugin-relative path**
(`skills/guardian/reference/calibration.md`), not a fragment whose meaning depends on the
surrounding prose ("the guardian skill's `reference/calibration.md`"). A sibling-relative citation
resolves only for a reader who already knows which directory it was written in — which a dispatched
consumer, reading the path out of a work order, does not.

**Reference depth — a named exception, owner-ratified 2026-08-12.** A pointable step-body may
itself cite **one hop onward**: its operational contract and its output templates (test-pilot's
`skills/test-pilot-execute/reference/execution-steps.md` cites `reference/pilot-contract.md` and
`templates/results-comment.md`). A step list that inlined its contract to stay one hop deep would
recreate the copy-drift problem one level down — the exact failure this pattern exists to remove.
This is a deliberate exception to the one-hop reference-depth expectation for skill bodies;
teaching the depth check this citation syntax is #966's scope.

---

## 12. Verification contracts (fix-ships-its-detector, real-seam tests)

> **Repo-specific convention for us as builders of superheroes**, like §11 — not (yet) a
> portable band contract. Provenance: the 2026-07-08 engine-fidelity escape
> ([#307](https://github.com/zwrose/superheroes/issues/307)–[#311](https://github.com/zwrose/superheroes/issues/311)),
> which penetrated every verification layer in place at the time, because every test of
> the seam stubbed the seam. These rules are the layer-independent part of the fix.
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

### 12.3 A structural guarantee ships a test that bites when it is neutralized

**Every structural guarantee carries a test that fails when the guarantee is neutralized — through
the real path.** §12.1 requires a detector for a failure that already happened; this requires a **bite
test** for a guarantee you are *asserting*: disable, bypass, or no-op the mechanism and at least one
test must go red **without being edited**. A guarantee whose neutralization leaves the suite green is a
claim without a receipt (promise 4), however emphatic its prose. It is the review question §12.2 asks,
turned around: not *which test would have failed if this seam broke*, but *which test fails when I
switch this guarantee off*.

**Provenance:** a ratified fold verifier shipped with no such test — **neutralizing it left 141 focused
tests green** — and the gap surfaced only in review, not in CI (the #702 arc's review record on PR
[#710](https://github.com/zwrose/superheroes/pull/710)).

The vacuity traps — when a bite test looks present and is not — live in one home: the plugin's `## Four
ways a bite-proof is vacuous` section in `plugins/superheroes/rubric/bite-proof.md`.

The vacuity traps are §12.2's trap one level up: a suite that stubs the seam verifies the stub, and a
probe aimed at a precondition verifies the precondition. Like §12.1, this rule lives at whichever tier fits — a CI
test where the guarantee is code, a **review-rubric question** where it is not — and is enforced the way
review discipline is: a reviewer citing this § is enough to block a guarantee shipped without its bite
test.

The band-level statement of this rule now ships in the plugin — `plugins/superheroes/rubric/bite-proof.md`
carries the obligation, the vacuity traps, the record shape, and the disclosures owed when the proof
cannot be produced or runs under a normalization — and this § stays the repository's own statement of
the guarantee rather than repeating that procedure. §12.3 is **this repository's structural-guarantee
case** of the band rule, and the band rule's scope is **wider** — every new or changed detector.

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
native permission rules), and carries the trigger that retires it. The worktree guard
(`LEDGERS.md` §1.1 — a minimal PreToolUse hook on Claude Code that denies git commands
that would silently destroy uncommitted work) also satisfies both: its consumer is every
Claude Code build session's revert/mutation-probe path (workhorse charter §8) and every
implementer subagent, since plugin hooks fire inside subagents.

This rule is enforced the same way review discipline is: at review, a reviewer citing
this section is enough to block a hook or gate that skipped either step.

---

## 14. Owner involvement before the merge click

> **Contract framing, not the operative rule.** Repo-root conventions do not ship in the plugin
> package (`plugins/superheroes/**` does). The two tests, the **show it** / **say it** / **nothing
> to see** levels, and the presentation duty live in the **Showrunner charter**
> (`skills/showrunner/SKILL.md`); the perceivability list lives in
> `skills/showrunner/reference/perceivability.md` — all in the plugin package so a consuming
> **advisor** can read them. This section records why the rule keys on what it keys on, what
> standard it holds itself to, what evidence backs it, and what is still unbuilt — it does **not**
> duplicate that list (§11: two hand-maintained copies with no drift test is a review-blocking
> violation).

**Scope.** Whether the **owner** is in the loop *before* the merge click — what the **advisor**
must surface or schedule so the owner can judge the finished work, not merely bless a green CI
run. **Merge approval itself is not on this axis:** every PR gets an owner approval regardless
of content, so approval is a constant, not a property of the work. This section decides only
what must happen *before* that constant fires.

**Key on behavior, not file paths.** File-based heuristics miss most of what owners care about —
copy, defaults, cost, what gets emitted on their behalf, visual surface. The ruling keys on two
behavioral tests instead — **Test 1** (perceivability without reading the diff) and **Test 2**
(owner taste or trade vs. craft judgment the review lenses own). Operative wording, the **show it**
/ **say it** / **nothing to see** levels, and the presentation standard the charter sets — judged by
zero reconstruction, show the after-state — live in the **Showrunner charter**
(`skills/showrunner/SKILL.md`); the default perceivability list lives in
`skills/showrunner/reference/perceivability.md` — cite those homes, do not restate them here.
The shape in which open owner decisions are delivered — the owner-needed filter with stated
grounds, the per-item spine, follow-up economics, and the two-batch delivery mechanics — lives in
`skills/showrunner/reference/owner-decisions.md`; this section cites that home rather than
restating it.

**Why one test is not enough.** Test 1's net is deliberately wide; alone it would catch a large
share of any project's work and spend *more* owner attention, not less. Test 2 discriminates craft
from owner taste. **Fail-direction is not the owner's call** — the premortem and security lenses
own it, and routing it up is a craft call dressed as a consequence. That follows the covenant's
third promise: route decisions to the owner as consequences, never as craft calls.

**Still unbuilt.** (a) **Settled** (issue #661, owner-ratified 2026-07-27): how a PR makes its
after-state inspectable — ranked entry-point levels, drive-to-state instructions, and the
two-half PR body — now lives in `plugins/superheroes/rubric/review-discipline.md` and the
**workhorse** charter's §11; cite those homes, do not restate the ranking here. (b) The generic
perceivability list ships as the **default**;
the **configure profile** is the named eventual home for per-owner taste domains, so a consuming
advisor does not re-derive what "taste" means for their owner. Not built yet.

**Evidence and its limit.** The tiering was back-tested against real merged work and
discriminated correctly across all three levels. **Every show-it visual case is untested** —
the repo the back-test came from has no visual surface, which is exactly why that repo is a
poor sole witness for that half.

**Provenance.** Ratified 2026-07-26 from the build-dispatch discovery (issue #526); the
canonical ruling record is `LEDGERS.md` §4.

---

## 15. Builder liveness heartbeat

> **Cross-boundary contract** (§11). The builder stamps semantic liveness; the advisor's wave sweep
> reads it. `plugins/superheroes/lib/heartbeat.py`'s module constants are **authoritative**; prose
> copies in charters and this section are pinned to them by a drift test.

**Producer:** the workhorse builder (`skills/workhorse/SKILL.md` — stamp duty in §7).
**Consumer:** the showrunner's scheduled heartbeat sweep (`skills/showrunner/SKILL.md` duty 9).

**Path:** `<root>/<repoId>/heartbeats/<launchId>.json`, `0700` directories, `0600` files.

**Root resolution:** `SUPERHEROES_HEARTBEAT_ROOT` (launcher-exported, already resolved), else
`launch_ledger.resolve_root()`.

**Lane identity:** `SUPERHEROES_LAUNCH_ID` (launcher-exported) or `--launch-id`; grammar
`^[A-Za-z0-9_-]{1,64}$`.

**Record fields:** `schema` (`1`), `launchId`, `issue`, `state`, `phase`, `lastDispatch`, `ts`,
`staleAfterSeconds`, `note`.

**`lastDispatch` sub-schema** (optional; `null` when absent): `kind`, `engine`, `model`, `runId`
(non-empty strings), `startedAt` (non-empty ISO-8601 UTC string, e.g. `2026-08-01T14:00:00Z`).

**States:** `working`, `awaiting-dispatch`, `blocked`, `parked`, `handback`. **Terminal:**
`parked`, `handback`.

**Sweep classes:** `fresh`, `stale`, `terminal`, `unknown`.

**Verbs:** `stamp`, `read`, `sweep`.

**Default promise.** A caller that states no `staleAfterSeconds` gets
`heartbeat.DEFAULT_STALE_AFTER_SECONDS` = **24000** seconds — floored at 2× the worst *benign*
inter-stamp gap measured on the reference host (11960 s, over 45 gaps across 10 builder lanes, 44 of
them benign). The prior 300 s default was below every real build's stamping cadence, so an omitting
caller read `stale` within five minutes. A builder that states its own promise is unaffected.

**Semantic core.** The builder stamps `staleAfterSeconds` — its own promise about when it will next
stamp. A lane is late only when it has outrun **the promise it made itself** — semantic liveness, not
another mtime watchdog. A builder inside a nine-minute dispatch is not a false alarm. The corpus holds
**3 watchdog design failures and 3 false alarms** from mtime and process-table signals.

**Fail-closed direction.** A missing, unreadable, corrupt, schema-skewed, non-finite or **future-dated**
heartbeat classifies `unknown`, never `fresh`. A ledger failure makes the sweep **refuse at the top
level** rather than return an empty, healthy-looking result. The sweep **never asserts that a lane is
dead** — a heartbeat cannot prove death.

**Accepted storage bound.** The store keeps **one small JSON file per launch, retained indefinitely**
— nothing reaps them, and the sweep ignores launches the ledger no longer reports live, so those
files have no continuing consumer. This is a knowingly accepted accumulation, not an oversight.
