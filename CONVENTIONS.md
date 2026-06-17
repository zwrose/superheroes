# superheroes — cross-plugin conventions

These are the **contracts the superheroes plugins share**: artifact formats, storage
rules, and the coordination primitives that let a band of independent plugins
(today review-crew + test-pilot; soon producer, the-architect, coordinator) run a project's
development loop together without stepping on each other.

**Status.** This document *locks* conventions — it decides and records the schema so
later work builds against a fixed target. A plugin implements a convention when it
first needs it; the convention does not require all plugins to implement it at once.
Where an existing plugin already implements (or diverges from) a convention, this doc
says so. Conventions not yet specified are named in **§7**, bound to the plugin and
roadmap phase that will own them — so deferral is explicit, not silent.

**Scope.** This file is the authoritative contract. The broader product vision lives
elsewhere; this doc is deliberately narrow — *interfaces*, not roadmap. (For the phases
referenced in §7, see [ROADMAP.md](ROADMAP.md).)

**Band posture — designed to be used together.** The heroes ship as *separately installable
plugins* but form a *cohesively designed band*: within the loop they **assume each other's
presence** and **cross-reference freely by qualified name** (`the-architect:plan`,
`review-crew:review-plan`). We **design for the integrated band and do not compromise that
design — or add machinery — to guarantee standalone-equivalence**; a hero used outside the
band carries **no warranty** (an individual hero may still have standalone utility — e.g.
review-crew's `review-code`, test-pilot's browser runs — but that is not a contract). A
missing band member **degrades, it does not crash**: e.g. an absent `review-plan` /
`review-tasks` gate falls back to the **producing skill's self-certification** (plan and
tasks are autonomous), while an absent `review-spec` simply leaves the spec for the **owner**
to approve — the spec is **owner-gated and never self-certified** (the deliberate asymmetry,
§3.1). That is "degrade-not-crash," **not** "degrade gracefully to full standalone" — we
don't carry dual-mode complexity to keep the apart-case whole. This is the superheroes-internal analog
of "superpowers is an assumed dependency." *(How many install-units the band ships as —
**packaging** — is a separate question from this posture and from the cast of characters;
deferred, §7.)*

---

## 1. Vocabulary: the loop and its artifacts

The development loop:

```
Discovery → Plan → Tasks → Build → Verify → Integrate
```

Each of the first three phases emits one **definition-doc**, and each definition-doc gets one
review (review-crew owns all three review gates):

| Phase | Emits | Is | Reviewed by | Spec-Kit twin |
| --- | --- | --- | --- | --- |
| **Discovery** | `spec` | requirements / the *what* (no tech) | `review-spec` | `spec.md` |
| **Plan** | `plan` | technical approach & architecture / the *how* | `review-plan` | `plan.md` |
| **Tasks** | `tasks` | bite-sized executable steps (TDD) | `review-tasks` | `tasks.md` |

> **Spec-Kit** is GitHub's spec-driven-development toolkit
> (<https://github.com/github/spec-kit>), which standardizes `spec.md` / `plan.md` /
> `tasks.md`. We adopt its nouns wholesale, for convertibility (§3.3) and to avoid
> inventing vocabulary.

> **Naming note.** We do **not** name any definition-doc "design": **"design" means UI/UX**
> here, never a technical-approach doc (that is `plan`). **Claude Design** (Anthropic's
> UI/UX design tool — a separate surface) is a first-class **Discovery** activity:
> Discovery hands the owner a design prompt built from the requirements, the owner creates
> the design there, and its **handoff output** (not a reinterpretation) is referenced in
> the `spec`; the `plan` only references that outcome when describing how the UI gets
> built. (Inline `mcp__visualize__show_widget` mockups are a graphical-client convenience
> only — they do not render in a terminal — so never the sole path.)

The **cast** referenced below: **producer** (the controller / loop driver),
**the-architect** (produces the definition-docs — spec/plan/tasks), **review-crew** (all
review gates + code review), **test-pilot** (behavioral/browser verification),
**coordinator** (owns all GitHub-issue writes). review-crew and test-pilot are
complete today; the-architect is in progress (Phase 1). (The spec/plan/tasks
artifact family is called **definition-docs** — the docs that *define* a work item —
independent of the producing plugin's name.)

Load-bearing identifiers used throughout (`<work-item>`, `<content-hash>`, the storage
keys) and the schema-versioning policy are defined once in **§6**.

---

## 2. Calibration profiles

Superheroes are *configured to your project and evolve with it*. Calibration is a
**shared core + per-plugin layers**, stored under one directory, governed by **one
band-wide storage mode**.

### 2.1 Layout (decision: core file + per-plugin files)

```
.claude/superheroes/        # in-repo mode; in global mode this content lives in the project store (§4.2)
  core.md            # the shared brain — read by every hero
  <plugin>.md        # one per plugin: review-crew.md, test-pilot.md, …
  patterns.md        # research-derived "current best-practice" layer (own lifecycle)
```

- **`core.md`** carries band-wide project facts: stack, the canonical *verify* command,
  threat model, canonical patterns. Its **single writer** is the calibration owner
  (`init` / the profile-management skill) — not `the-architect` (which owns definition-docs).
  Because `core.md` is project-keyed and shared across a project's checkouts (§4.2), the
  writer **serializes its writes under the project-scoped config lock** (§4.4) — a
  machine-local lock distinct from the per-checkout runtime locks; the "applied only on
  confirmation" rule (§2.4) gates *intent*, not concurrent physical writes. (In in-repo
  mode, cross-machine config writes are additionally git-mediated, since config is
  committed.)
- **`<plugin>.md`** is a layer **owned and versioned by that plugin**. Each plugin
  writes only its own layer — no plugin co-edits another's file.
- **`patterns.md`** is the research-derived opinion layer. It lives in its own file
  because it has a distinct lifecycle: refreshed on a research cadence and **pinned per
  run** — at loop start a snapshot is frozen into durable runtime state
  (`patternsPin`, §4.3), and the run reads the pin, never the live file.

Runtime state (queue, checkpoints, run records) is **never** stored here — see §4.

### 2.2 File format

Every file begins with a one-line **provenance comment**:

```
<!-- superheroes-core: schemaVersion=1 status=provisional created=2026-06-14 updated=2026-06-14 -->
<!-- test-pilot: plugin-version=0.1.0 schemaVersion=1 status=confirmed created=… updated=… nudge-ack={} -->
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
  top. (Both existing plugins already follow this.)

### 2.3 Storage mode (one band-wide toggle)

The whole band is either **in-repo** or **global**, decided once by `init` and never
per-plugin:

| | **in-repo** | **global ("without a trace")** |
| --- | --- | --- |
| Calibration (`core.md`, layers, `patterns.md`) | `.claude/superheroes/` committed with the repo | the project store (§4.2) |
| Effect | calibration is **shared with collaborators** | the repo stays **pristine** — zero superheroes footprint |
| Definition-docs (§3) | `docs/superheroes/<work-item>/` in the repo | the project store (§4.2) |
| Runtime state (§4) | always machine-local | always machine-local |

"in-repo" shares *calibration*; it does not promise zero global footprint — runtime
state, plus the per-project registry, are always machine-local (§4.2). Both modes keep
the *repo* clean of run state.

**Mode is set once and is sticky.** `init` is idempotent: on an already-initialized
project it reconciles content but does **not** silently re-decide the mode. The
authoritative mode record is `registry.json` in the project store (§4.2/§6.3). A mode
flip (in-repo↔global) is an **explicit migration** that moves calibration *and* every
definition-doc to the new location and updates `registry.json`; absent that migration,
`init` refuses to re-decide once the registry records a mode. (Without this rule a flip
would strand every already-written calibration file and definition-doc.)

### 2.4 Resolution and evolution

- **One shared resolver, two key derivations.** Both existing plugins already ship
  near-identical dual-keyed resolvers with self-healing pointers —
  [`test-pilot/lib/store.py`](plugins/test-pilot/lib/store.py) and
  [`review-crew/lib/review_store.py`](plugins/review-crew/lib/review_store.py) (store.py
  even comments "Same algorithm as review_store"). Convergence means **unifying those
  two near-duplicate libs into one shared resolver** — not grafting a lib onto a
  lib-less plugin. That resolver exposes **two distinct key derivations**, because
  config and runtime have opposite sharing needs (see §4.2 and §6.2):
  - **Config key = per-project** (`<config-key>`, §6.2), with self-healing pointers —
    deliberately unifies a project's clones/worktrees so they share calibration.
  - **Control-plane key = per-checkout** (`<absolute-git-dir-key>`, §6.2), **without**
    the remote-keyed self-healing — so parallel loops stay isolated (§4.2).
- **No-remote repositories.** When `git remote get-url origin` is empty (common for the
  owner *before the first push*, while Discovery is already producing definition-docs), the
  config key is `<common-dir-key>` rather than `<remote-key>` (§6.2), which makes config
  **per-checkout-clone, not shared-across-clones** — the "shared across clones"
  guarantee is impossible until a remote exists. On the first push, `init` **rebinds**
  the project store to the new `<remote-key>` (and merges the fallback entry) so
  calibration does not fork.
- **Living profiles.** Lift review-crew's mechanisms band-wide: a *staleness nudge*,
  a *learning-loop proposal* (any hero may **propose** a calibration edit, applied only
  on confirmation), and a **`nudge-ack` map** so a dismissed signal does not re-fire
  until it changes.
- **Rendered single view.** Although calibration is stored as several files, `init`
  (and a future `superheroes:profile` view) renders core + layers + the pinned patterns
  as **one screen**, so the owner sees "one profile" while the disk stays coordinated.

---

## 3. Definition-docs (spec / plan / tasks)

The three artifacts of the loop's front half. A superset of Spec-Kit's
`spec`/`plan`/`tasks`, convertible to/from it.

### 3.1 Shared additive header (YAML frontmatter)

Every definition-doc opens with the metadata superheroes owns:

```yaml
---
superheroes: doc
schemaVersion: 1
docType: spec | plan | tasks
workItem: <work-item>                 # the frozen identity from §6.1
issue: <github-issue-number | null>   # linked once an issue exists; NOT the path segment
parent: { workItem: <id>, docType: spec | plan }   # plan→spec, tasks→plan; null for spec
size: small | medium | large          # work-item sizing (see §6.4); "tier" is reserved for state substrates
status: draft | in-review | approved  # DERIVED, human-facing: approved iff gates.review == passed
gates: { review: pending | passed | changes-requested }   # AUTHORITATIVE review state for THIS doc
producedBy: the-architect@<version>
created: <date>
updated: <date>
---
```

- **`gates.review` is the authoritative review outcome** for this doc;
  **`status` is derived** from it (`approved` iff `gates.review == passed`) and is for
  humans. Code reads `gates.review`.
- **`parent`** is a resolver-relative reference (`{workItem, docType}`), **not** a file
  path — paths differ between storage modes (§2.3), so a path-based link would break on
  a mode switch. The referent is fixed: `plan`→`spec`, `tasks`→`plan`, `null` for `spec`.
- The per-doc `gates.review` here is **aggregated** by `checkpoint.json` into a
  doc-type-keyed roll-up (§4.3); the frontmatter is the source of truth, the checkpoint
  is the projection.

> **Why YAML frontmatter here but an HTML-comment in §2.2?** Intentional, not drift.
> Calibration files are prose config read mostly by agents, with a minimal embedded
> block for the few code-parsed fields. Definition-docs are structured artifacts with rich
> machine-read linkage (`docType`, `parent`, `gates`), for which standard frontmatter is
> the right tool.

### 3.2 Bodies

- **`spec`** — plain-language requirements, owner co-authors, **no tech**. Sections:
  purpose; who it's for; functional requirements; significant unhappy paths;
  non-functional requirements; UI/UX; definition of done; assumptions & dependencies;
  constraints; out-of-scope; open questions; glossary. **Functional requirements are
  written in EARS** (Easy Approach to Requirements Syntax — `When`/`While`/`Where`/`If-Then`
  + "the system shall …"), one behavior each, every requirement carrying **≥1 acceptance
  criterion** (Given-When-Then for flows, a rule for simple constraints). **Depth = the
  happy path *plus the significant unhappy paths*** (the unwanted-behavior `If-Then` EARS),
  elicited via a coverage checklist (empty/first-run, invalid input, boundaries, errors,
  access, duplicates, concurrency, abuse, reach) and tagged Specify/Defer-to-plan/N-A —
  **not** an exhaustive enumeration, and **not** the technical *how* (that is the `plan`).
  Non-functional requirements are stated as **outcomes with a fit-criterion**. UI/UX
  **references the Claude Design handoff output** (§1), not a reinterpretation. This is the
  anti-slop core.
- **`plan`** — approach and architecture; components and interfaces; data flow; risks;
  alternatives considered. References the spec's UI/UX outcome when describing how it
  is built.
- **`tasks`** — the frontmatter above, then the superpowers `writing-plans` body
  **verbatim** (its Goal/Architecture/Tech-Stack header + checkbox TDD tasks). Our
  header adds the **build contract**: `size`, `gates`, and the SDD clips —
  subagent-driven-development is invoked with the worktree **pre-verified, not created**,
  and **without** `finishing-a-development-branch`; the **producer enforces** both clips
  at invocation.

### 3.3 Location and convertibility

- **Location follows the storage mode (§2.3):** in-repo →
  `docs/superheroes/<work-item>/{spec,plan,tasks}.md` in the repo (committed, diffable);
  global → `projects/<config-key>/docs/<work-item>/…` in the **git-initialized project
  store** (§4.2), so global-mode definition-docs are versioned and diffable too. One file
  per doc-type per work-item.
- **Convertibility** to Spec-Kit is a documented field-mapping (`spec↔spec.md`,
  `plan↔plan.md`, `tasks↔tasks.md`); an actual converter is built only if something
  needs it.

---

## 4. State tiers and the disk-state layout

### 4.1 Three tiers, three substrates

| Tier | Substrate | Holds | For |
| --- | --- | --- | --- |
| **Human** | **GitHub issues** | work items + a rendered index/summary (coordinator-owned) | the **owner** to see and steer |
| **Handoff** | a **git "control-plane" repo** | issue queue, per-issue checkpoints, resume-briefs | passing work **between sessions** |
| **Live** | **ephemeral** | the running loop + a working copy | the **current** session only |

The rule: **git moves state between sessions; GitHub issues surface work to the human;
live state stays ephemeral.** GitHub issues never hold live machine state. Live state is
checkpointed *into* the control-plane repo, never into an issue. The source of truth for
the definition-docs is the **files in git**; the issue is the rendered human index. (The
GitHub-issue schema itself — body, labels, index format, write coordination — is
deferred; see §7.)

### 4.2 Two stores and their keying

Superheroes uses **two kinds of git-initialized store**, split along the
config-vs-state line, because the two have opposite sharing needs:

- **Project store = per-project**, keyed by `<config-key>` (§6.2) — shared across all of
  a project's worktrees and clones on a machine (same project ⇒ same
  threat-model/patterns, one mode record). Holds calibration, global-mode definition-docs,
  the authoritative `registry.json`, and the config lock.
- **Control-plane store = per-checkout**, keyed by `<absolute-git-dir-key>` (§6.2) —
  **distinct per linked worktree and per clone**. Holds the runtime: queue, checkpoints,
  per-issue state. Each checkout gets its **own** control-plane store.

> **Divergence note — this is NEW code, like the lock.py and resolver-unification notes.**
> The cited `store.py get_gitdir()` today prefers `--git-common-dir`, which is *shared*
> across a clone's linked worktrees — so two worktrees resolve to the **same** entry
> (confirmed empirically). That is correct for the *config* key and **wrong** for the
> control-plane key. The control-plane resolver must therefore (a) derive its key from
> raw `--absolute-git-dir`, and (b) **not** route through the remote-keyed self-healing
> pointer — remote-key healing deliberately unifies a project's checkouts (right for
> config), which would funnel two parallel loops onto one queue/state dir: exactly the
> uncoordinated-write hazard the vision forbids.

```
<global-store>/
  projects/<config-key>/                # PROJECT STORE — a git repo; per-project, shared across this project's checkouts
    .git/
    registry.json                       # AUTHORITATIVE: { schemaVersion, storageMode, remoteKey | null, createdAt }
    config.lock                         # the project-scoped config-write lock (§4.4)
    config/                             # core.md, <plugin>.md, patterns.md       (global mode only; in-repo → in the repo)
    docs/<work-item>/{spec,plan,tasks}.md   # definition-docs                          (global mode only; in-repo → in the repo)
  checkouts/<absolute-git-dir-key>/     # CONTROL-PLANE STORE — a git repo; ONE per worktree/clone
    .git/
    meta.json                           # { schemaVersion, createdAt }   (mode lives in registry.json, not here — §6.3)
    queue.json                          # producer-owned ordered work-list (schema in §4.3)
    issues/<work-item>/
      checkpoint.json
      resume-brief.md
      patterns-pin.md                   # the per-run snapshot of patterns.md (§2.1)
      events.jsonl                      # append-only audit log
```

The project store exists in **both** modes (it is the machine-local home of
`registry.json` and `config.lock`); in in-repo mode its `config/` and `docs/` content
lives in the repo instead. (`<config-key>` and `<absolute-git-dir-key>` derivations are
in §6.2.)

### 4.3 Runtime schemas

**`queue.json`** — producer-owned, single-writer (enforced per §4.5):

```json
{
  "schemaVersion": 1,
  "items": [
    { "workItem": "...", "issue": 42, "state": "queued | claimed | done | failed", "order": 0 }
  ]
}
```

`issue` is the linked GitHub issue number (or `null` pre-issue, §6.1). Ordering is
explicit (`order`), not array position. Item lifecycle is
`queued → claimed → done | failed`.

**`checkpoint.json`** — the sole source of truth for resuming an issue:

```json
{
  "schemaVersion": 1,
  "workItem": "...",
  "issue": 42,
  "size": "medium",
  "phase": "discovery | plan | tasks | build | verify | integrate",
  "gates": { "spec": "passed", "plan": "passed", "tasks": "pending | changes-requested" },
  "patternsPin": "<content-hash of the frozen patterns-pin.md>",
  "branch": "superheroes/<work-item>-<content-hash>",
  "lockGeneration": 7,
  "pr": { "number": 42, "url": "..." },
  "lastGoodStep": "...",
  "updatedAt": "..."
}
```

- `gates` here is the **aggregation** of each definition-doc's per-doc `gates.review` (§3.1),
  keyed by doc-type; it can hold `changes-requested`.
- `branch` is content-addressed (§6.3) and **is** the idempotency anchor (§4.4).
- `lockGeneration` is the fencing token (§4.4).
- `patternsPin` ties the run to its frozen patterns snapshot, so a resume reads the same
  opinions it started with.

(`resume-brief.md` and `events.jsonl` have schemas of their own — deferred to §7, since
the producer that reads/writes them does not exist yet.)

### 4.4 Coordination = git refs and a config lock, not file polling

**Work-item lock — a leased git ref**, `refs/superheroes/locks/<work-item>`, valued
`{ holder, host, acquiredAt, generation }`, in the per-checkout control-plane store:

- The holder **renews** the ref (bumps `acquiredAt`) on a heartbeat interval **≪ TTL**
  while it works.
- A contender may **reclaim** only when `now - acquiredAt > TTL`, via **compare-and-swap**
  on the ref (atomic), **incrementing `generation`**.
- **Fencing:** the current `generation` is written into `checkpoint.json`
  (`lockGeneration`); before any external write (push / PR / issue), the holder
  re-reads the lock ref and **aborts if its generation is stale**. This makes a stale
  holder **very unlikely** to complete a write — and it is a check-then-act, not atomic
  with the remote, so it *narrows* rather than fully closes the woken-stale-holder
  window. Any write that does land on the target remote is caught by the exactly-once
  anchor below; issue writes (no anchor until §7's coordinator schema) rely on the fence
  alone. (TTL + CAS *without* fencing would be outright unsound — a live-but-slow holder,
  or a slept laptop, would be stolen from while still holding live state.)
- **TTL** is an implementation parameter chosen against the longest expected phase (a
  full build/verify) with heartbeat ≪ TTL; default on the order of tens of minutes.
- The existing file-based [`lock.py`](plugins/test-pilot/lib/lock.py) is a *narrower,
  same-host* lock; its `is_stale()` already exists but is pid-only (unsound under
  reboot/pid-recycle) and never wired into `acquire()`. The **ref-lease above is the
  cross-session / cross-host primitive**; where the file lock is retained it gets a
  TTL fallback + host-boot-id check, otherwise it is superseded by the ref-lease.

**Project-scoped config lock.** Calibration (`core.md`/`<plugin>.md`/`patterns.md`) is
shared across a project's checkouts (§4.2), so it is **not** guarded by the per-checkout
locks above. Config writes acquire an advisory **`flock` on `projects/<config-key>/config.lock`**
in the machine-local project store (present in both modes), which serializes them across
the project's checkouts on that machine. In in-repo mode, cross-machine config writes are
additionally mediated by git (config is committed). Config write cadence is owner-driven
and low.

**Exactly-once — the remote work branch is the idempotency anchor**, with an explicit
resume recovery procedure (not just a happy path):

1. On entering Integrate (or resuming into it): does the remote branch
   `superheroes/<work-item>-<content-hash>` exist?
2. If it exists, **always query for an open PR by head branch** (never trust only the
   local checkpoint) → if one exists, **adopt** it (record `pr` in checkpoint); else
   `gh pr create`.
3. If it does not exist, push, then `gh pr create`.

A `git push` that **fails closed** (branch already exists) is therefore **not** read as
"someone else owns it" — it routes into step 2. This relies on GitHub **rejecting a
second open PR for the same head→base**, and the lock lease further serializes so only
one resumer reaches `gh` at a time. (Pre-search "check-then-act" is explicitly rejected:
it is only at-least-once under `gh` eventual consistency.)

### 4.5 Concurrency model (three layers)

- **Per-checkout isolation (local).** Each worktree/clone loop has its own control-plane
  store, queue, and lock refs. **`init`/the producer acquires a per-checkout lock at
  startup**, so a second loop launched in the *same* checkout **fails closed** — turning
  "one active loop per checkout" from an assumption into an enforced gate. (atomic file
  writes prevent torn files, not lost updates; the startup lock is what prevents the
  within-checkout read-modify-write race on `queue.json`/`checkpoint.json`.) **Parallelism
  = more checkouts.**
- **Per-project state remote (durability, optional, off by default).** A private
  `<owner>/superheroes-state-<project>` repo, **one branch per checkout-loop**, that the
  producer pushes resume-briefs/checkpoints to at gates — for walk-away and cross-machine
  durability. Local git is the baseline; the remote is the walk-away tier. (Any
  always-on / machine-off execution would be a **separate product, not a tier of this
  loop** — it cannot run on subscription-billed Claude Code mechanics, so it is out of
  contract here.)
- **Cross-loop backstop = the target repo's remote.** The genuinely shared write targets
  are: the target code repo on GitHub (guarded by the exactly-once machinery, §4.4); the
  shared **config store** (serialized by the project-scoped config lock, §4.4, and
  git-mediated cross-machine in in-repo mode); and the **state remote** (whose
  branch-per-checkout isolation depends on the §4.2 keying fix). The exactly-once
  machinery lives on the target remote, so it is inherently cross-process and
  cross-machine.

**Residual edge (named, not fixed now):** per-checkout work-item locks won't stop two
*different* checkout-loops from both grabbing the *same* work-item if it is mis-queued
into both. Worst case is **wasted duplicate work, not corruption** — the target-remote
backstop (§4.4) still prevents a double-merge, and shared config writes are serialized by
the config lock. If cross-loop work-item overlap ever becomes a real pattern, the
escalation is to host the work-item lock ref on the *shared target remote* instead of
the per-checkout store (correct, but a network round-trip per lock — so not the default).

---

## 5. Quick reference: what lives where

| Thing | in-repo mode | global mode | Keyed per |
| --- | --- | --- | --- |
| Calibration (`core`/`<plugin>`/`patterns`) | `.claude/superheroes/` (committed) | project store `config/` | project (`<config-key>`) |
| Definition-docs (`spec`/`plan`/`tasks`) | `docs/superheroes/<work-item>/` (committed) | project store `docs/` | project (`<config-key>`) |
| `registry.json` + `config.lock` | machine-local project store | machine-local project store | project (`<config-key>`) |
| Runtime (queue, checkpoints, briefs, events) | machine-local control-plane store | machine-local control-plane store | checkout (`<absolute-git-dir-key>`) |
| Work items + rendered index | GitHub issues | GitHub issues | — |
| Walk-away durability | `superheroes-state-<project>` remote, branch per checkout | same | checkout (branch) |

---

## 6. Identifiers and schema versioning

The cross-cutting values every plugin must compute identically.

### 6.1 `<work-item>` — the join key

`<work-item>` is a **frozen slug**, chosen **once** at work-item creation and **never
re-derived** (a title edit does not change it). It is the stable segment interpolated
into every path, lock ref, and branch (`docs/superheroes/<work-item>/`,
`projects/<config-key>/docs/<work-item>/`, `issues/<work-item>/`,
`refs/superheroes/locks/<work-item>`, `superheroes/<work-item>-<hash>`).

- Slug = the title **NFC-normalized**, lowercased, non-`[a-z0-9]` runs collapsed to `-`,
  trimmed, capped at 50 chars (then trimmed again, so the cap can't leave a trailing
  `-`), **plus a short disambiguating suffix** (`-` + first 6 hex of
  `sha256(NFC-title + creation-nonce)`) so two similar titles **never** collide into one
  dir/lock/branch. (NFC normalization makes canonically-equivalent Unicode — e.g.
  macOS-NFD vs Linux-NFC — yield the same slug.)
- The **GitHub issue number is a linked attribute** — the `issue:` field in the
  definition-doc frontmatter (§3.1), the queue item, and `checkpoint.json` (§4.3) — **not**
  the path segment, so nothing has to be renamed when an issue is later filed for a
  work-item that began as a pre-issue draft.

### 6.2 Storage keys

Reuse the existing resolver's derivation (`store.py` / `review_store.py`) as the
normative spec. **Hash:** `sha256(...)` truncated to **16 hex** (`short_hash`).

- **`<remote-key>`** = `short_hash(normalize_remote(origin))`, where `normalize_remote`
  lowercases the host and strips scheme/userinfo/port and a trailing `.git`.
- **`<common-dir-key>`** = `short_hash(realpath(git rev-parse --path-format=absolute --git-common-dir))`
  — shared across a clone's linked worktrees; the no-remote fallback (§2.4).
- **`<config-key>`** (the project-store key) = `<remote-key>` when a remote exists,
  else `<common-dir-key>`. On first push, `init` rebinds `<common-dir-key>` →
  `<remote-key>` (§2.4).
- **`<absolute-git-dir-key>`** (the control-plane key) =
  `short_hash(realpath(git rev-parse --absolute-git-dir))` — distinct per linked
  worktree and per clone (§4.2). Note `--absolute-git-dir` ≠ `--git-common-dir` for a
  linked worktree, so this is **never** equal to `<common-dir-key>`.

### 6.3 `<content-hash>` — the exactly-once key

`<content-hash>` makes the work branch content-addressed. It is computed **once at branch
creation** from the **approved `tasks` doc**, and **must be byte-identical across plugins,
hosts, and sessions** (`the-architect` recomputes it to detect a material change; `producer`
computes it to create the branch — they must agree, or every metadata touch spuriously
reads as a new attempt). Canonical serialization, in this exact order:

1. Take the **stable** frontmatter fields only — `workItem`, `docType`, `parent`, `size`
   — and serialize as **JSON with sorted keys** (so `parent` is
   `{"docType":"...","workItem":"..."}`). Volatile fields are excluded (`updated`,
   `created`, `status`, `gates`, `issue`, `producedBy`, provenance timestamps).
2. Take the doc **body**, **NFC-normalize it**, normalize line endings to `\n`, and strip
   trailing whitespace **per line**. (NFC is what makes the across-hosts guarantee hold
   for non-ASCII text — macOS-NFD and Linux-NFC of the same text hash identically.)
3. Concatenate `frontmatter-json` + `"\n"` + `body`.
4. `sha256` of the UTF-8 bytes, first **16 hex**.

A re-approval that materially changes the `tasks` body or stable frontmatter yields a
**new** hash → a new attempt branch (the prior PR is closed by the loop). A pure
metadata touch does not. (A normal resume reads `branch` verbatim from `checkpoint.json`,
§4.3 — it does not recompute the hash.)

`storageMode` is recorded **authoritatively in `registry.json`** (§4.2); `meta.json`
does not duplicate it.

### 6.4 `size` and schema versioning

- **`size`** (`small | medium | large`, §3.1) sizes a work-item. It is set when the
  `spec` is approved (owner-chosen or inferred from spec scope), frozen there, and
  inherited by `plan`/`tasks` and mirrored into `checkpoint.json`. It is currently
  **descriptive** — consumers must accept it; no control-flow keys off it yet. (The
  word "tier" is reserved for the §4 state substrates and durability tiers.)
- **`schemaVersion`** is stamped independently on each artifact family (`core.md`,
  definition-docs, runtime files). Bump on a **breaking** change (additive changes do not
  bump). A reader that encounters an **unknown** version **fails closed** with a
  "update the plugin or migrate the file" message — the precedent test-pilot's
  `engine.py`/`state.py` already set. Migration logic lives in the plugin that owns the
  artifact. A breaking change to the §6.3 `<content-hash>` canonicalization is **likewise
  a definition-doc `schemaVersion` bump** (so old and new hashes never silently collide);
  whether to *also* embed an explicit canon-version in the stored branch key is deferred
  to the first consumer (an entry-gate, tracked in `eval/gate.md`). (The fuller
  cross-plugin version-skew / band-compatibility story is deferred; §7.)

---

## 7. Deferred conventions

Real conventions the band will need that are **intentionally not specified yet**, because
the plugin that owns each does not exist — specifying them blind would be guesswork.
**Each is an entry-gate for its owning phase** (see [ROADMAP.md](ROADMAP.md)): building
that plugin means specifying its conventions here first. (Surfaced by the reviews of
2026-06-14.)

| Deferred convention | What it must define | Owner · phase |
| --- | --- | --- |
| **Loop failure / retry / cascade semantics** | the central control-flow contract: what happens on `changes-requested`, a failed build, a failed verify; who re-runs which phase; how downstream gates are invalidated when an upstream doc changes; retry/backoff limits; when to escalate to the owner | **producer · Phase 2a** |
| **GitHub issue ↔ work-item schema** | issue body / labels / state conventions; `<work-item>`→issue mapping; the "rendered index/summary" format; how producer & coordinator coordinate writes to one issue | **coordinator · Phase 2a-plus** |
| **Owner-interaction / approval-gate contract** | how the owner is prompted (and in approachable pros/cons); where approvals/decisions are recorded; how a walk-away run defers vs. blocks on a needed human decision | **producer + coordinator · Phase 2a-plus** |
| **`resume-brief.md` + `events.jsonl` schemas** | required sections of the resume brief (what a resumer reads to rehydrate); event types/fields of the audit log | **producer · Phase 2a-core** |
| **Cleanup / retention / GC** | when merged work branches, finished `issues/<work-item>/` dirs, lock refs, abandoned checkouts, and state-remote branches are reaped (ties to the "without a trace" promise) | **producer / coordinator · Phase 2a-plus / 4** |
| **Auth / credentials / scopes** | required `gh` token scopes and push rights; credential handling; graceful behavior when auth is missing or insufficient (a routine state for the non-technical owner) | **producer · Phase 2a-plus** |
| **Plugin-version / band-compatibility** | cross-plugin `schemaVersion` skew handling; whether a minimum-compatible-band matrix exists (minimal fail-closed-on-unknown is already specified in §6.4) | **band-wide · later** |
| **Plugin packaging / bundling** | how many install-units the band ships as. Lean: review-crew & test-pilot stay separate (genuine standalone value + already published). Open: whether to bundle the tightly-coupled, band-only orchestration (the-architect / producer / coordinator) into fewer plugins once their version-coupling is concrete. Decide with real coupling info, not blind. (Packaging ≠ the cast — see Band posture above; the brand is fixed.) | **band-wide · revisit when producer/coordinator land (~Phase 2a)** |
