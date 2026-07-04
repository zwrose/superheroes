# superheroes — band conventions

These are the **contracts the superheroes band shares**: artifact formats, storage
rules, and the coordination primitives that let the band's heroes
(the-architect, review-crew, test-pilot, workhorse) run a project's
development loop together without stepping on each other.

**Status.** This document *locks* conventions — it decides and records the schema so
later work builds against a fixed target. A hero implements a convention when it
first needs it; the convention does not require all heroes to implement it at once.
Where an existing hero already implements (or diverges from) a convention, this doc
says so. Conventions not yet specified are named in **§8**, bound to the hero and the
GitHub issue/milestone that will own them — so deferral is explicit, not silent.

**Scope.** This file is the authoritative contract. The broader product vision lives
elsewhere; this doc is deliberately narrow — *interfaces*, not roadmap. (§8's deferred conventions are
bound to GitHub issues/milestones — see the [roadmap Project](https://github.com/users/zwrose/projects/1).)

**Band posture — designed to be used together.** The heroes ship as **one plugin** and form a
*cohesively designed band*: within the loop they **assume each other's
presence** and **cross-reference freely by qualified name** (`superheroes:architect-plan`,
`superheroes:review-plan`). We **design for the integrated band and do not compromise that
design — or add machinery — to guarantee standalone-equivalence**; a hero used outside the
band carries **no warranty** (an individual hero may still have standalone utility — e.g.
review-crew's `review-code`, test-pilot's browser runs — but that is not a contract). A
missing band member **degrades, it does not crash**: e.g. an absent `review-plan` /
`review-tasks` gate falls back to the **producing skill's self-certification** (plan and
tasks are autonomous), while an absent `review-spec` simply leaves the spec for the **owner**
to approve — the spec is **owner-gated and never self-certified** (the deliberate asymmetry,
§3.1). That is "degrade-not-crash," **not** "degrade gracefully to full standalone" — we
don't carry dual-mode complexity to keep the apart-case whole. This is the superheroes-internal analog
of "superpowers is an assumed dependency."

---

## 1. Vocabulary: the loop and its artifacts

The development loop:

```
Discovery → Plan → Tasks → Build → Verify → Ship
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

The **cast** referenced below: **producer** (the per-issue back-half loop driver —
**Workhorse**), **the-architect** (produces the definition-docs — spec/plan/tasks),
**review-crew** (all review gates + code review), **test-pilot** (behavioral/browser
verification), and the **showrunner** (the run engine that drives one approved work-item
end-to-end to a ready-for-review PR — the live single-issue launch, §10.4). These five are
**shipped today** (and run on both Claude Code and Codex, §7).
**Upcoming heroes:** the showrunner's **queue/controller layer** (driving a *queue* of
work-items, §10.3), a **backlog/TPM** (owns all GitHub-issue writes — triage,
decomposition), and a **maintainability guardian** — see the
[roadmap Project](https://github.com/users/zwrose/projects/1). (The "coordinator" of earlier
drafts split into the showrunner + the backlog/TPM.) (The spec/plan/tasks artifact family is
called **definition-docs** — the docs that *define* a work item — independent of the producing
plugin's name.)

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
  machine-local lock distinct from the per-clone runtime lease refs; the "applied only on
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

- **One shared resolver, two key derivations.** The band ships a single in-tree library,
  `store_core` (`lib/store_core.py`), that all heroes use for storage resolution. It
  exposes **two distinct key derivations**, because config and runtime have opposite
  sharing needs (see §4.2 and §6.2):
  - **Config key = per-project** (`<config-key>`, §6.2), with self-healing pointers —
    deliberately unifies a project's clones/worktrees so they share calibration.
  - **Control-plane key = per-clone** (`<common-dir-key>`, §6.2), **without** the
    remote-keyed self-healing — shared identically across a clone's worktrees so the
    one-live-run-per-work-item lease coordinates them, never unified across clones (§4.2, #170).
- **No-remote repositories.** When `git remote get-url origin` is empty (common for the
  owner *before the first push*, while Discovery is already producing definition-docs), the
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
  **verbatim** (its Goal/Architecture/Tech-Stack header, the **Global Constraints**
  block, and the checkbox TDD tasks — each with a per-task **Interfaces** block where
  `writing-plans` emits one). Our header adds the **build contract**: `size`, `gates`,
  and the SDD clips — subagent-driven-development is invoked with the worktree
  **pre-verified, not created**, and **without** `finishing-a-development-branch`; the
  **producer enforces** both clips at invocation.
  We target **superpowers ≥ 6.0** (6.0
  added the Global Constraints / per-task Interfaces blocks to `writing-plans` and the
  single-`task-reviewer` SDD flow); the wrap captures the body verbatim, so a newer
  `writing-plans` body flows through unchanged.
  The build worktree the SDD clip pre-verifies is the **managed** worktree
  (`lib/buildtree.py`, issue #77): a deterministic home under `~/.superheroes-worktrees/`,
  reuse-on-entry, a durable record, and tiered fail-closed teardown — the producer owns its
  create/reclaim/reap, replacing the prior ad-hoc "establish a clean worktree".

### 3.3 Location and convertibility

- **Location follows the storage mode (§2.3):** in-repo →
  `docs/superheroes/<work-item>/{spec,plan,tasks}.md` in the repo (committed, diffable);
  global → `projects/<config-key>/docs/<work-item>/…` in the **git-initialized project
  store** (§4.2), so global-mode definition-docs are versioned and diffable too. One file
  per doc-type per work-item.
  the-architect now implements this: the prior in-repo-only hardcode is closed, and
  the in-repo location plus committed/gitignored choice is the doc-policy established
  via `superheroes:configure` (which drives the-architect's doc-policy; the standalone
  `architect-init` is now an internal helper reached only from `configure`).
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
deferred; see §8.)

### 4.2 Two stores and their keying

Superheroes uses **two kinds of git-initialized store**, split along the
config-vs-state line, because the two have opposite sharing needs:

- **Project store = per-project**, keyed by `<config-key>` (§6.2) — shared across all of
  a project's worktrees and clones on a machine (same project ⇒ same
  threat-model/patterns, one mode record). Holds calibration, global-mode definition-docs,
  the authoritative `registry.json`, and the config lock.
- **Control-plane store = per-clone**, keyed by `<common-dir-key>` (§6.2) — **shared
  identically across a clone's main checkout and every linked worktree**, distinct across
  clones. Holds the runtime: checkpoints, per-issue state, and the work-item lease refs.

> **Implemented by the resilience slice** (workhorse `control_plane.py`). Coordination MUST be shared across a clone's worktrees: the one-live-run-per-work-item lease refs (§4.4) live in this store, so keying it to the git **common dir** (`--path-format=absolute --git-common-dir`, identical from all of a clone's worktrees) is what refuses a duplicate launch of the same work item from any worktree — a per-worktree `--absolute-git-dir` key would let it run twice = split-brain on one branch/PR (#170). State isolation is per-work-item WITHIN the store (`issues/<work-item>/…`), not per-worktree. The resolver still does **not** route through the remote-keyed self-healing pointer (that unifies distinct clones — right for config, wrong for machine-local runtime). Zero-migration: for the main checkout the common dir IS the absolute git dir, so existing stores keep their key.

```
<global-store>/
  projects/<config-key>/                # PROJECT STORE — a git repo; per-project, shared across this project's checkouts
    .git/
    registry.json                       # AUTHORITATIVE: { schemaVersion, storageMode, remoteKey | null, createdAt }
    meta.json                           # { schemaVersion, sourcePath }  mint-time provenance; never rewritten (store_sweep's orphan signal)
    config.lock                         # the project-scoped config-write lock (§4.4)
    config/                             # core.md, <plugin>.md, patterns.md, review-decisions.json   (global mode only; in-repo → in the repo)
    docs/<work-item>/{spec,plan,tasks}.md   # definition-docs                          (global mode only; in-repo → in the repo)
  checkouts/<common-dir-key>/           # CONTROL-PLANE STORE — a git repo; ONE per clone, shared across its worktrees
    .git/
    meta.json                           # { schemaVersion, sourcePath }  (mode lives in registry.json, not here — §6.3)
    queue.json                          # producer-owned ordered work-list (schema in §4.3)
    issues/<work-item>/
      checkpoint.json
      resume-brief.md
      patterns-pin.md                   # the per-run snapshot of patterns.md (§2.1)
      events.jsonl                      # append-only audit log
      devserver.json                    # managed dev-server sidecar (pid/pgid/port/command/bootId) for orphan reclaim
```

The project store exists in **both** modes (it is the machine-local home of
`registry.json` and `config.lock`); in in-repo mode its `config/` and `docs/` content
lives in the repo instead. (`<config-key>` and `<common-dir-key>` derivations are
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
  "phase": "discovery | plan | tasks | build | verify | ship",
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

(`resume-brief.md` and `events.jsonl` have schemas of their own — **now specified in §4.6**, authored by the resilience slice.)

### 4.4 Coordination = git refs and a config lock, not file polling

**Work-item lock — a leased git ref**, `refs/superheroes/locks/<work-item>`, valued
`{ holder, host, acquiredAt, generation }`, in the per-clone control-plane store (so the
lease is visible identically from every worktree of the clone, §4.2):

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
  anchor below; issue writes (no anchor until §8's coordinator schema) rely on the fence
  alone. (TTL + CAS *without* fencing would be outright unsound — a live-but-slow holder,
  or a slept laptop, would be stolen from while still holding live state.)
- **TTL** is an implementation parameter chosen against the longest expected phase (a
  full build/verify) with heartbeat ≪ TTL; default on the order of tens of minutes.
- **Implemented by the resilience slice.** The ref-lease above is the cross-session / cross-host primitive (`lib/ref_lock.py`) and the **sole** work-item mutex — the old §4.5 per-checkout `startup.lock` was removed in #170 (it never serialized anything: its holder pid was the ephemeral acquiring leaf, dead seconds after acquire). The file-based `lib/file_lock.py` — a *narrower, same-host* engine lock — carries TTL + host-boot-id staleness in `acquire()`, superseding the old pid-only `is_stale()`.

**Project-scoped config lock.** Calibration (`core.md`/`<plugin>.md`/`patterns.md`) is
shared across a project's checkouts (§4.2), so it is **not** guarded by the per-clone
lease refs above. Config writes acquire an advisory **`flock` on `projects/<config-key>/config.lock`**
in the machine-local project store (present in both modes), which serializes them across
the project's checkouts on that machine. In in-repo mode, cross-machine config writes are
additionally mediated by git (config is committed). Config write cadence is owner-driven
and low.

**Exactly-once — the remote work branch is the idempotency anchor**, with an explicit
resume recovery procedure (not just a happy path):

1. On entering Ship (or resuming into it): does the remote branch
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

### 4.5 Concurrency model (two layers)

- **Per-clone coordination (local).** A clone's worktrees **share** one common-dir
  control-plane store and its lock refs (§4.2). The hard rule is **one live run per work
  item per clone**, enforced by the per-work-item ref-lease (§4.4): a duplicate launch of an
  in-flight work item — from *any* worktree — is refused with the lease reason. (The old
  per-checkout `startup.lock` was removed in #170: its holder pid was an ephemeral leaf, so
  it never serialized anything — the lease is the real mutex.) Read-modify-write of the shared
  `worktrees.json` build-registry is guarded by an `fcntl.flock` sidecar (atomic writes prevent
  torn files; the flock prevents lost updates). **Parallelism = more worktrees running
  different work items.**
- **Cross-loop backstop = the target repo's remote.** The genuinely shared write targets
  are: the target code repo on GitHub (guarded by the exactly-once machinery, §4.4) and the
  shared **config store** (serialized by the project-scoped config lock, §4.4, and
  git-mediated cross-machine in in-repo mode). The exactly-once
  machinery lives on the target remote, so it is inherently cross-process and
  cross-machine.

**Residual edge (named, not fixed now):** the common-dir lease coordinates a clone's
worktrees, but two *different clones* (or machines) of one repo won't see each other's
per-work-item lease if the same work item is launched in both. Worst case is **wasted
duplicate work, not corruption** — the target-remote backstop (§4.4) still prevents a
double-merge, and shared config writes are serialized by the config lock. If cross-clone
overlap ever becomes a real pattern, the escalation is to host the work-item lock ref on
the *shared target remote* (a network round-trip per lock — so not the default).
Cross-machine coordination is explicitly out of scope for #170.

### 4.6 `events.jsonl` and `resume-brief.md` schemas (authored — resilience slice)

**`events.jsonl`** — the per-issue append-only audit log (workhorse `journal.py`), one
JSON object per line, written under the single-writer model (§4.5) via an atomic
`O_APPEND` + `fsync`. Each line carries:

- `ts` — UTC `YYYY-MM-DDTHH:MM:SSZ`.
- `seq` — monotonic, 1-based.
- `type` — one of `run_started`, `step_entered`, `step_completed`, `notify`, `gate`,
  `error`, `resumed`, `lease_acquired`, `lease_reclaimed`, `ci_fix_attempt`, `parked`,
  `run_completed`, `phase_record`, `external_dispatch`, `phase_cost`.
- optional `step` — the step number (0–9) the event belongs to.
- optional `detail` — free-text, **scrubbed fail-closed** (`readout.scrub`) before write.
- optional `world` — a dict of reality facts; string values scrubbed fail-closed.
- optional `payload` — structured non-secret data (e.g. `ci_fix_attempt` →
  `{round, failing: [signatures]}`), written as-is.

Readers tolerate a single torn trailing line (a crash mid-append). The step 8 CI-fix bound
is reconstructed by replaying `ci_fix_attempt` events, written **write-ahead** (before
the fix push); a torn trailing line counts **+1** — a conservative over-count, so the
bound trips earlier and is never bypassed by a crash-loop (it never under-counts). A
failed durable append raises `DurableWriteError` and the orchestrator parks (fail-closed).

**Token telemetry** (`phase_cost`, #130) — an additive extension of this vocabulary (no
schemaVersion; the schema is versionless). Each `phase_cost` `payload` carries one phase's
`{phase, dispatches: {total, byModel}, tokens: {output, input, measured, source}}`: the
dispatch count × resolved model tier is the always-exact **proxy**; `tokens.output` is the
budget-derived (`budget.spent()`) output-token delta over the phase, present only when the
runtime surfaced it (`measured: true`) and **never fabricated**. It is written best-effort,
**folded into the phase's existing durable write** — the per-phase `phase_progress_entry.py`
save leaf, and `readout_post.py` for the terminal `ship` phase — so it rides no new courier
leaf (§ the #118 one-leaf-per-phase budget). A ready hand-back journals `run_completed`;
a park journals `parked` — including a mid-phase park, which folds the `parked` marker into
its journal-only save (`parkFromPhases` itself journals nothing), so `token_trend`/`run_watch`
classify it as parked rather than `other`. `cost_report.py` projects the run total + top
phases into the readout, and `token_trend.py` renders tokens-per-completed-work-item and
tokens-per-park across runs.

Two counts are **excluded by design** (both inherent to the no-new-leaf fold, not bugs): (a) a
phase's own persist leaf — dispatched after the snapshot, so its tokens fall between the phase's
delta endpoint and the next phase's baseline; and (b) the pre-loop startup leaves — recorded
under a `startup` bucket that is never snapshotted. So the per-phase counts run slightly below a
raw `/workflows` agent count; don't reconcile them one-to-one.

**`resume-brief.md`** — the rehydration brief (workhorse `journal.render_brief`),
refreshed at the compaction boundary (the PreCompact hook) and on every park. Required
sections:

- `## Run` — work-item, branch, PR, started timestamp, resume count.
- `## Where it was` — phase (build/verify/ship) + last good step.
- `## Confirmed done` — reality reads: PR state, CI, dev server, seeded baseline.
- `## Next` — the step to resume from (after `lastGoodStep`).
- `## Notices` — the `notify` / `gate` / `parked` events (scrubbed).

### 4.7 Loop failure / retry / cascade contract (authored — resilience slice)

The producer's back-half loop (workhorse steps 0–9) is **reality-wins, reconcile-on-entry**
(`recover.py`). On every entry (first run or resume):

- **Reconcile against reality.** The durable `checkpoint.json` only *speeds* a resume;
  it never authorizes an action. A read the loop would act on that **cannot be
  determined** (a transient/unknown PR or seeded-state read) → **GATE**, never treated
  as "absent" (which under auto-continue could redo a mutating step). A lost/unparseable
  checkpoint → **world-derive**. A **wedged control-plane store or unacquirable lock →
  park-GATE** (fail-closed; never run lockless — the lock lives in the store).
- **Floor re-arm.** Every entry re-arms the step 0 enforcer self-check + per-matcher canaries;
  a transient miss retries (bounded, `recover.rearm_action`, ≤3) then **parks** (visible,
  never resume unguarded, never silent-wedge).
- **`changes-requested` / failed review.** review-crew owns its internal auto-fix loop;
  the producer reads the terminal review action and, on a non-pass, **parks-GATE** (PR
  left draft, live resources torn down).
- **Failed build / verify.** Park safely — draft PR, dev-server teardown, GATE to the owner.
- **step 8 CI bound (bounded fix loop).** `ci_loop.decide` halts after `max_rounds` or on a
  **recurring failing set** (`revert_and_gate`). The bound **survives restarts** via the
  write-ahead `ci_fix_attempt` events — a crash-loop cannot reset it.
- **step 8 base-freshness gate.** Handback requires the branch **up to date with its PR
  base**, so CI is evaluated on the integrated HEAD (not a stale branch). The producer
  freshens by **merging the base in** (non-force feature-branch push — never a rebase /
  force-push, which is owner-authority), bounded by `freshness.decide` (`DEFAULT_MAX_SYNCS`).
  A **merge conflict** is confidence-gated (F5): a trivially-correct resolution may proceed
  (CI re-vets), anything uncertain → **GATE** (the owner resolves; never a guessed merge).
  An unreadable freshness read → **GATE** (fail-closed). If the base keeps advancing past the
  bound, the loop stops chasing and hands back with an explicit **NOTIFY** — freshness is
  promised only *as of* handback (post-handback drift is the owner's). The sync counter is
  in-session: a resume re-derives freshness from reality and re-bounds (a merge converges, so
  no crash-loop). **The freshness read is on the *local* HEAD, but CI runs on — and the owner
  merges — the *remote* PR head**, so the producer reconciles them before the CI wait (push the
  local HEAD when it is ahead of the PR head; idempotent). This closes the partial-failure
  window where a crash *between* the local merge commit and its push would otherwise read
  `up_to_date` locally while the PR still points at the stale pre-merge commit, and CI is then
  evaluated on the reconciled HEAD SHA (a just-pushed-but-unregistered SHA reads as "no checks
  yet", never an older commit's green). The freshen merge advances HEAD past the step-3
  ship-gate's reviewed commit by design (the merge integrates already-reviewed base code; CI
  re-vets it, review is not re-run) — so a post-review merge/conflict-resolution is **NOTIFY**ed
  in the readout, never silently presented as review-covered.
- **Stale-spec cascade (§6.3).** When the approved `tasks` doc changes under an in-flight
  branch (the recorded `<content-hash>` no longer matches the recomputed one), the resume
  **GATEs** — a downstream run is invalidated when its upstream definition-doc changes.
- **Escalation to the owner** follows the F5 policy (`escalation-base.md`): act
  autonomously on agent-verifiable / reversible decisions; escalate on owner-authority or
  high-stakes-irreversible ones. The **owner-role / repo-shaping** actions — **merge,
  release, run-workflow, force-push, push-to-default** — are gated on the owner's **live,
  in-turn approval** (a real prompt the owner answers, never an agent-set token) and are
  enforced deterministically by the producer's PreToolUse hook (which overrides an
  allowlist-allow and fires even under bypassPermissions — the guarantee the harness's own
  prompt can't give): the producer never does them unattended (no approver → it **parks**),
  but performs them on explicit go-ahead. Generic high-stakes operations the host harness
  *already* contemplates — **deploy, destructive data ops, `rm -rf`** — stay on the
  **cooperative F5 layer** (the model GATEs them via `escalation_resolve`; the harness's own
  permission prompt + `rm -rf /|~` circuit breaker is the backstop), deliberately off the
  deterministic hook so it doesn't false-positive on routine build commands. **PR-create
  stays autonomous.** (The live-approval gate — [#14](https://github.com/zwrose/superheroes/issues/14).)

(The fuller walk-away approval-gate contract — defer-vs-block, where approvals are
recorded — remains deferred to §7, Phase 2a-plus.)

---

## 5. Quick reference: what lives where

| Thing | in-repo mode | global mode | Keyed per |
| --- | --- | --- | --- |
| Calibration (`core`/`<plugin>`/`patterns`) | `.claude/superheroes/` (committed) | project store `config/` | project (`<config-key>`) |
| Definition-docs (`spec`/`plan`/`tasks`) | `docs/superheroes/<work-item>/` (committed) | project store `docs/` | project (`<config-key>`) |
| `registry.json` + `config.lock` | machine-local project store | machine-local project store | project (`<config-key>`) |
| Runtime (checkpoints, briefs, events, lease refs) | machine-local control-plane store | machine-local control-plane store | clone (`<common-dir-key>`) |
| Work items + rendered index | GitHub issues | GitHub issues | — |

---

## 6. Identifiers and schema versioning

The cross-cutting values **all heroes** must compute identically.

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

The normative spec is implemented in `lib/store_core.py`. **Hash:** `sha256(...)` truncated to **16 hex** (`short_hash`).

- **`<remote-key>`** = `short_hash(normalize_remote(origin))`, where `normalize_remote`
  lowercases the host and strips scheme/userinfo/port and a trailing `.git`.
- **`<common-dir-key>`** = `short_hash(realpath(git rev-parse --path-format=absolute --git-common-dir))`
  — shared across a clone's linked worktrees. Serves as **both** the no-remote config
  fallback (§2.4) **and** the control-plane key (§4.2, #170). `--path-format=absolute` is
  required: a bare `--git-common-dir` is a relative `.git` from the main checkout, which
  `realpath` would resolve against the process cwd; the fallback for git < 2.31 joins the
  relative result onto the target cwd, else `--absolute-git-dir`, else `realpath(cwd)`.
- **`<config-key>`** (the project-store key) = `<remote-key>` when a remote exists,
  else `<common-dir-key>`. On first push, `init` rebinds `<common-dir-key>` →
  `<remote-key>` (§2.4).
- **`<absolute-git-dir-key>`** = `short_hash(realpath(git rev-parse --absolute-git-dir))` —
  distinct per linked worktree. **Retired as the control-plane key in #170** (the control
  plane now uses `<common-dir-key>` so a clone's worktrees coordinate); still the identity a
  per-worktree derivation would produce, kept here for reference. For the **main checkout**
  it equals `<common-dir-key>` (common dir == absolute git dir) — the zero-migration hinge.

### 6.3 `<content-hash>` — the exactly-once key

`<content-hash>` makes the work branch content-addressed. It is computed **once at branch
creation** from the **approved `tasks` doc**, and **must be byte-identical across hosts and sessions** (`the-architect` recomputes it to detect a material change; `producer`
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
  `spec` is approved (the discovery skill infers it from scope, not the owner), frozen there, and
  inherited by `plan`/`tasks` and mirrored into `checkpoint.json`. It is currently
  **descriptive** — consumers must accept it; no control-flow keys off it yet. (The
  word "tier" is reserved for the §4 state substrates and durability tiers.)
- **`schemaVersion`** is stamped independently on each artifact family (`core.md`,
  definition-docs, runtime files). Bump on a **breaking** change (additive changes do not
  bump). A reader that encounters an **unknown** version **fails closed** with a
  "update the plugin or migrate the file" message — the precedent set by
  `lib/engine.py`/`lib/state.py`. Migration logic lives in the hero that owns the
  artifact. A breaking change to the §6.3 `<content-hash>` canonicalization is **likewise
  a definition-doc `schemaVersion` bump** (so old and new hashes never silently collide);
  whether to *also* embed an explicit canon-version in the stored branch key is deferred
  to the first consumer (an entry-gate, tracked in `eval/gate.md`). The band ships as one
  plugin — one version — so cross-plugin version skew is not a concern; artifact
  `schemaVersion` skew (files written by an older build) is covered by the fail-closed
  behavior above.

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

A session started **directly from a slash command** (e.g. `/superheroes:architect-discovery`
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

It is **fail-soft**: each source is gathered independently; a missing/erroring one is omitted
with a one-line stderr breadcrumb (never the file contents) and the hook always exits 0, never
breaking a session. The post-compaction workhorse resume-brief is **additive** — appended to
the same `additionalContext` only on `compact` with a current work-item; it never gates the
bootstrap. **Codex** wires no `SessionStart` hook, so it gets no bootstrap (out of scope).

Scope boundary: this fixes the host-map **Read** (model-resolved, so an injected absolute path
is the lever). The `lib/` **bash** seam of §7.1 — skills shelling out to `lib/` helpers through
`${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}`, which the Bash tool does not expand — is a *different*
layer that context injection cannot fix; it is tracked separately
([#93](https://github.com/zwrose/superheroes/issues/93)) and the seam form here is unchanged.

### 7.5 Cross-engine contract (host-run-on vs engine-dispatched-to)

The **host** is the harness the plugin *runs on* (§7.1–§7.2 — Claude Code or Codex). The **engine** is
the agent a working role is *dispatched to* — `claude` (the default, unchanged), `codex`, or `cursor` —
chosen per role (reviewer engine, implementation engine, **planAuthor engine**) by the owner in `configure`. These are
orthogonal axes: the host is where the plugin executes; the engine is which model family does a role's
work. An engine is selected *below* the host, at the dispatch leaf.

Two postures are held strictly separate, mirroring `model_tier`:
- **Engine *selection* fails open.** An unknown / unavailable / unauthorized / stalled engine silently
  degrades to Claude — the same posture `model_tier` documents for a bad tier ("a wrong/absent tier is a
  cost concern, never a safety one"). No run hangs or hard-fails on engine choice.
- **A completed external *result* fails closed.** A build or fix that fails or can't run verify stops the
  run; an unauditable run stops; an unreadable or incomplete review is re-run on Claude, never accepted
  as green. This reuses the existing gates — no new safety logic.

**Build-engine contract.** The native build leg (`build_phase.js`) is now an *engine* consumer: its
worker, fixer, and final-review-fix leaves route to the implementation engine, and its whole-branch
review leaf routes to the reviewer engine, via `engine_dispatch.js` → `engine_adapter.py`. The engine
axis is orthogonal to the model tier: `model_tier` still governs *which Claude model* runs when the
engine is `claude`; when the engine is external, `engine_pref.resolve_effort` governs the engine's depth.

**Plan-author contract.** Showrunner's produce phase routes ONLY the **plan** doc through
`enginePreferences.planAuthor` (the **`author-plan`** role kind). Tasks authoring always stays native
(`claude`). The split **`author-plan` model tier** (in `## Model tiers`) lets plan authoring alone move
to a stronger model (e.g. `author-plan: fable`) without moving tasks authoring; unset, it resolves exactly
as `author`. A failed external author-plan dispatch falls open to the native author after UFR-2 cleanup
(clear the completion marker and discard the external draft) within the same attempt.

**Confinement + hygiene.** External reviewers run read-only; external implementers run workspace-write,
confined to the managed build worktree, with **no remote authority** — the band owns every push / PR /
merge through its `enforcer.py`-gated path (an external producer can never autonomously merge, force-push,
or push to the default branch). All external free-text is secret-scrubbed at the adapter boundary
(`engine_adapter.parse_result` → `readout.scrub`) so every downstream surface — including the standalone
`/review-code --post` PR comment — is clean. The build authorization is the owner's to grant; the band
shows it and never applies it.

---

## 8. Deferred conventions

Real conventions the band will need that are **intentionally not specified yet**, because
the hero that owns each does not exist — specifying them blind would be guesswork.
**Each is an entry-gate for its owning hero / milestone** (tracked in the
[roadmap Project](https://github.com/users/zwrose/projects/1)): building that hero means
specifying its conventions here first. (Surfaced by the reviews of 2026-06-14.)

| Deferred convention | What it must define | Owner · tracking |
| --- | --- | --- |
| **GitHub issue ↔ work-item schema** | issue body / labels / state conventions; `<work-item>`→issue mapping; the "rendered index/summary" format; how producer & coordinator coordinate writes to one issue | **backlog/TPM** · [#30](https://github.com/zwrose/superheroes/issues/30) · **now specified in §9** |
| **Owner-interaction / approval-gate contract** | how the owner is prompted (and in approachable pros/cons); where approvals/decisions are recorded; how a walk-away run defers vs. blocks on a needed human decision | **showrunner** · partly defined by the live-approval gate [#14](https://github.com/zwrose/superheroes/issues/14); the batch/defer contract is TBD |
| **Cleanup / retention / GC** | when merged work branches, finished `issues/<work-item>/` dirs, lock refs, abandoned checkouts, and state-remote branches are reaped (ties to the "without a trace" promise) | [#42](https://github.com/zwrose/superheroes/issues/42) |
| **Auth / credentials / scopes** | required `gh` token scopes and push rights; credential handling; graceful behavior when auth is missing or insufficient (a routine state for the non-technical owner) | **showrunner** · [#26](https://github.com/zwrose/superheroes/issues/26) |

---

## 9. GitHub issue ↔ work-item schema

The data contract mapping a **GitHub issue ↔ a band work-item** — the Human tier of §4.1.
The **showrunner** reads issues as runnable work-items; the **backlog/TPM** (#28) writes
them. Authoritative state lives in git (definition-doc `gates.review`, §3.1) and the
control-plane (`checkpoint.json`, §4.3); **the issue is a rendered projection of that
state, never its source** — no control flow reads from the issue. (Promoted from §8 ahead
of its owning hero because the showrunner's read-path makes it a root dependency, #30.)

### 9.1 Mapping (1:1, slug-anchored)

- One work-item ↔ one GitHub issue. The join key is the **frozen `<work-item>` slug**
  (§6.1); the **issue number is a linked attribute** (`issue:` in the definition-doc
  frontmatter §3.1, the queue item §4.3, and `checkpoint.json`), **not** the path segment.
- A work-item may exist **pre-issue** (`issue: null`, §6.1); the TPM later files the issue
  and back-links the number — **nothing is renamed**. An owner-filed issue becomes a
  work-item when discovery/TPM mints its slug.

### 9.2 Body = owner/TPM prose + one managed block

- **Prose** (title, description, acceptance) — human-authored.
- **One machine-managed block**, HTML-comment-fenced (the §2.2 provenance-comment
  pattern), the only region a resolver parses deterministically:

  ```
  <!-- superheroes-workitem: schemaVersion=1 workItem=<slug> size=<s|m|l> phase=<discovery|plan|tasks|build|verify|ship> -->
  ```

  followed by a human-readable rendered roll-up (per-doc gate states, linked PR
  `{number,url,state}`, latest-readout pointer). The prose around the block is free.

### 9.3 Write coordination = partition by surface (no lock)

- The **backlog/TPM is the sole writer of the issue body** (issue-write authority, #28),
  including the managed block.
- The **showrunner/producer never writes the body**; it surfaces run state by **posting
  comments** (the parked-PR handoff readout, NOTIFYs) and **best-effort labels** (§9.4).
- Single-writer body + append-only comments ⇒ **no clobber** — the §8 "how producer &
  coordinator coordinate writes to one issue" question, answered by partitioning the
  surface rather than locking it.

### 9.4 Labels = owner-facing lane, best-effort

Beyond the taxonomy (`area:*`, `enhancement`/`chore`, `spike`, milestone), a small
**`state:` lane** projects where a work-item is for the owner — `state:queued`,
`state:running`, `state:parked`, `state:blocked`, `state:merged` — plus a `size:` mirror
of §6.4. Labels are a **projection reconciled from authoritative state, never trusted for
control flow** (a stale label is cosmetic). The TPM sets labels; the showrunner may set its
own work-item's `state:running`/`state:parked`, reconciled on entry.

### 9.5 Issue open/closed ↔ lifecycle

The issue stays **open** across the work-item's life. It is **closed on merge** (the
owner's action — merge is owner authority, §4.7) or when the owner drops the work-item.
**The showrunner never closes an issue** (closing implies done = merge). Reopening
reactivates the work-item.

### 9.6 Schema versioning + reference impl

The managed block carries `schemaVersion`; an unknown version **fails closed** (§6.4). The
render/parse is a small library built by the **first consumer** (the showrunner's read-path
needs parse; the TPM's write-path needs render) — proportionate, not gold-plated.

---

## 10. Orchestration model (the showrunner-era contract)

Decided by the engine spike (#37): the band's outer loop runs on **native Workflows over
the existing durable substrate (§4)**. Three contracts follow that constrain every hero's
orchestration going forward.

### 10.1 Scripts orchestrate; leaf agents do single-purpose work

A Workflow **worker (an `agent()` step) is a leaf** — it has **no Agent/Task tool** and
**cannot dispatch its own subagents** (verified empirically, including with a full-tool
agent type). Therefore **all fan-out lives in the Workflow script**, never inside a worker:
a panel of reviewers is `parallel([…])` in the script; a producer's build/review/verify
phases are script steps. A hero that fans out (review-code's panel, the spec/plan/tasks
review trio, test-pilot, subagent-driven-development) is **re-expressed as Workflow control
flow that reuses the hero's libraries and leaf agents** — never wrapped as one opaque worker
(which could not launch its fan-out). The hero's pure decision functions
(`ci_loop.decide`, `freshness.decide`, `ship_gate.decide`, `recover.reconcile`, …) and
substrate libraries carry over **unchanged**.

The showrunner back half includes a native `test-pilot` phase after draft-PR and before
mark-ready. A branch that has positive no-browser evidence records a current-head
`not_applicable` rationale and may proceed; an applicable branch must publish/update the
human checklist, seed through test-pilot's engine, run browser-derived checks, fix and rerun
within the browser-fix cap, restore fresh seed data for spot-checking, re-cover any
post-browser fixes with targetable `review-code`, non-force-push the final tested head to
the PR branch, and write a current status sidecar before mark-ready. The human checklist is
never auto-checked by the workflow.

### 10.2 Durability is the substrate's, not the engine's

A Workflow's native resume (`resumeFromRunId`) is **same-session only** and **not
load-bearing**. Cross-crash / cross-session / post-compaction durability is owned by the
**engine-agnostic substrate** (§4): the per-issue Workflow is a **relaunch-and-reconcile
driver** — on every entry it reads disk-state, recomputes gates from definition-doc
frontmatter, and **skips completed steps** (`recover.reconcile`; the reality-wins rule
§4.7). It takes **no load-bearing launch arguments** — it reconciles its inputs from the
control-plane store keyed by `<work-item>`.

### 10.3 Two layers: a controller session around the per-issue Workflow

A background Workflow **cannot take live owner input mid-run**. So owner interaction lives
in a **controller layer** (a session): it owns the queue, self-paces across context/usage
limits, launches/relaunches the per-issue Workflow, and holds the **live owner-approval
gate** (#14) — unattended, the run **parks** and never ships. The per-issue Workflow is the
deterministic, gated, background chain that parks at every gate. **Auditability is
structural:** each step is a validated, logged record (gate / confidence / assumptions)
appended durably (`events.jsonl`, §4.6); a step that surfaces a **material assumption or
low confidence parks rather than proceeds** — where an "assumption" is a *genuine
unverified premise*, not a status note.

### 10.4 The live launch contract (showrunner skill, single work-item)

**Courier stretch contract (#118).** Deterministic showrunner stretches use **at most one
courier leaf by default**; genuine model work (authoring, review panels, fixers) remains
separate leaves. The lease/reconcile **world snapshot** at startup is the named exception —
it may batch multiple reads in one courier call.

**Lean courier agent (#194).** Every dumb-pipe courier leaf dispatches on the restricted
`superheroes:courier` agent (`tools: Bash` only), not the default full-surface worker. A
Bash-only agent has neither ToolSearch nor the Skill tool, so it carries **no
`deferred_tools_delta` / `skill_listing` attachments** (~13.9k tokens/leaf, measured) and only
a tiny tool-schema prefix — cutting the fixed per-leaf context ~2.6× (≈33k → ≈13k tokens).
This is orthogonal to the cheapest-model pin (§ the model wrapper). A **prompt-drop guard**
covers the known plugin-subagent failure where a dispatch starts without the task prompt: for
a command that echoes `__SR_EXIT`, an answer missing the marker triggers one retry on the
courier agent, then a fall-back to the default dispatch — so a courier-agent dispatch bug
degrades to today's cost instead of parking the run. Every **advancing durable write** must be
**idempotent** and **read-back confirmed** before the run advances past that step; a failed
read-back parks fail-closed. **Best-effort** writes (round-state snapshots, deferred-finding
backups, readout posting) must be explicitly named and must **not** gate advancement on their
delivery alone.

The `superheroes:showrunner` skill turns the merged spine **on** for one approved work-item.
The launch path is **pre-flight → bundle → Workflow tool**:

- **Deterministic pre-flight gate (fail-closed).** `lib/preflight.py` runs a pure `decide()`
  over a probes dict — spec approved (`gates.review == passed`), `gh` write access, no
  *conflicting* live run (a stale/absent lease lets a relaunch proceed; only a live lease for
  another work-item blocks), repo/base/remote ready, the verify command resolvable, and the
  profile/storage config resolvable. A check that errors or cannot be evaluated is treated as
  **not-passing**; an advisory `ci-visibility` note fires when no required CI gates the PR.
  The skill prints each blocking check's cause + remediation and **STOPs** on `ok:false`.
- **The committed bundle is the runtime.** `lib/showrunner.bundle.js` is a generated,
  self-contained Workflow-tool script (module-registry bundler, `lib/bundle_showrunner.js`;
  a drift guard keeps the committed bundle == a fresh emit). The skill reads the bundle and
  invokes the **Workflow tool** with `args: {workItem: <work-item>}` — it never re-bundles or
  edits the spine. The bundle injects a leaf-bash `io` so the spine's filesystem touches run
  in command-runner leaves (no `fs`/`path`/`os` in the sandbox), and sets full-run mode so the
  pipeline proceeds past the front-half boundary into Build → Ship (vs. the env-driven
  front-half-only mode, which keeps the boundary park).
- **Idempotent, re-invocable.** The launch takes no load-bearing arguments beyond the
  work-item; on every entry the spine `reconcile`s from the control-plane store, skips
  completed phases, and reuses the existing PR — so the same skill entry covers a fresh start,
  a resume after a park/crash/compaction, and a status read.
- **Codified readout (FR-10).** At run end the skill assembles the readout via the deciders
  (`run_readout.assemble` → `readout.build_readout`): PR link, CI status, built-vs-acceptance,
  test-pilot result, the secret-scrubbed merge reminder. `run_readout.run_outcome` is the
  machine-readable projection ([#112](https://github.com/zwrose/superheroes/issues/112)
  consumes it). **The skill never instructs merging** — merge is owner authority (§4.7).

### 10.5 Post-approval path choice (Discovery presents, showrunner executes)

After Discovery records the spec's approval gate, `architect-discovery` presents a two-option
choice with **no default** — **run the showrunner (recommended)** or the **manual bridged
path**. The hand-off partitions cleanly: **Discovery presents the choice; the showrunner skill
executes the run** (Discovery never starts `plan` itself on either branch). On the showrunner
pick it records the advisory choice (`lib/path_choice.py`) and invokes the `showrunner` skill;
on the manual pick it records the choice and falls through to the **existing manual hand-off,
byte-unchanged**. The recorded choice is **advisory** — the run state is authoritative, so a
never-started showrunner pick simply re-enters via the showrunner skill.

### 10.6 The showrunner path is superpowers-free

No phase on the **showrunner path** may invoke a superpowers skill — it authors natively (the
`produce-leaf` names the tasks-doc format only as a quality bar, not a superpowers dependency).
This is **CI-enforced, impossible-by-construction**: a structural invariant
(`test_safety_invariants.py::test_showrunner_path_is_superpowers_free`) fails loudly if the
authoring leaf or the generated live bundle names the superpowers toolkit, and the bundle build
greps clean of `superpowers`/`writing-plans`/`subagent-driven`. (The **manual bridged path**
keeps its superpowers dependency, untouched.) Full superpowers removal across the band is
tracked by [#111](https://github.com/zwrose/superheroes/issues/111); the durable repeatable
agentic acceptance of the live run by
[#112](https://github.com/zwrose/superheroes/issues/112).
