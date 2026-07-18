# Path forward v2: the discipline layer (working plan, 2026-07-17)

**Status: DRAFT v2 — reshaped per owner direction (2026-07-17 evening); converging 2026-07-18.
Logistics (§6–§7) deliberately parked until shape settles.**

## 0. The v2 vision — standalone (what the README will say)

**Superheroes is a discipline layer for building software with AI sessions.** It does not run
your builds — your sessions do. Superheroes makes them trustworthy: it is the set of roles,
artifacts, and review structures that let a technical owner delegate real work to AI sessions
and ship the result on evidence instead of vibes.

It's built for the moderately technical builder — someone who can describe what they want,
tell whether the result works, and read code a little. **No part of the system depends on the
owner recognizing good engineering** (owner-ratified persona correction, 2026-07-18): the
engineering judgment lives in the structure — brief checks, cross-vendor review, advisor
vets — and every decision that does route to the owner arrives translated into plain
consequences (what it costs, what it risks, what accepting it means), never as a craft call.
Every claim traces to a receipt the owner's advisor session can check from the PR alone.

**Two heroes run your sessions:**
- **Showrunner** — one long-lived session per project that thinks at project altitude: it
  keeps the roadmap and issue board truthful, sizes and routes incoming work (build-ready vs.
  needs-discovery), decomposes big asks into small mergeable steps, vets every PR from
  artifacts against its issue and its stated approach, watches cost and bottlenecks, and
  coordinates releases. It never merges; merging is always the owner's act.
- **Workhorse** — a disposable session per issue: it takes a routed issue, writes a short
  **build brief** (shape, contracts & state, reuse plan, hard seams, rejected alternatives,
  consequential flags), gets the brief checked pre-code by a fresh reviewer a tier up and from
  another vendor, then builds test-first in its own worktree with tiered subagents — small
  diffs by design — verifies UI work in a real browser (test-pilot), runs multi-model review
  with findings dispositioned in the PR body, and hands back a ready PR. Consequential
  decisions go to the owner before build; everything else proceeds autonomously.

**What holds it together:**
- **Specs carry intent.** Fuzzy ideas go through discovery to a plain-language, owner-approved
  spec — the what, never the how. The spec is the contract the PR is held accountable to.
- **The how stays the builder's** — made explicit in the brief, checked once before code,
  and vetted against at the PR. No plan documents, no doc-review treadmills.
- **Review is structurally independent**: models that didn't write the code review it
  (cross-vendor panels composed per the builder's vendor), the advisor vets with fresh
  context, and the owner merges. Maker and checker are never the same mind.
- **configure calibrates each project once**: models per role, review engines, test-pilot,
  storage, boundary rules — then every session inherits the calibration.
- **A dreaming routine keeps the system honest over time**: an independent scheduled pass
  over the period's sessions and PRs proposes evidence-backed improvements to the project's
  memory, charters, and conventions — the owner accepts or rejects each.
- **The philosophy rides along**: every session starts with a compact covenant — never merge,
  never claim more than verified, disclose degradation, park rather than presume — distilled
  from PHILOSOPHY.md, which remains the project's constitution.

**What v2 deliberately is not:** not an execution pipeline, not an orchestration engine, no
couriers or workflow spines, no gates between an approved issue and a ready PR beyond the ones
above. The platform runs the agents; superheroes supplies the judgment structure around them.

## 0.5 The cast of v2 (owner-ratified 2026-07-18 — precedes ALL Step-1 filings)

Naming style: bare names, no "The" — with the single grandfathered exception of The Architect.

| Hero | v2 identity | Fate |
|---|---|---|
| **Showrunner** | The advisor session — runs the show at project altitude (board, routing, vetting, releases, investigations). | Name REUSED from the retired spine (owner call: "lets us move on without losing a good name"); the machinery dies, the name ascends to the role that replaced it. |
| **Workhorse** | The builder session — takes a routed issue, rips it with discipline (brief → check → small diffs → review → ready PR), hands back. | Survives, evolved: same identity, new discipline. |
| **The Architect** | Turns fuzzy intent into owner-approved specs (discovery → spec → review-spec). | Survives, narrowed to the *what* — loses plan/tasks. |
| **Review Crew** | The multi-model review layer: spec panel, build-brief check, review-code v2. Cross-vendor by composition. | Survives, strengthened (a crew of different vendors is finally a real crew). |
| **Test-Pilot** | Browser-evidence verification: plans derived from the spec/issue, executed for real. | Survives unchanged (cleanest record of the whole reckoning). |
| *(unnamed, S2/M7)* | Maintainability guardian (#41) — periodic inward sweeps: codebase health (audit-debt lineage, drift metrics) AND practice health (the dreaming loop, §2-E). | #41 remains valid in v2; rescoped at build time to absorb dreaming; hero name deferred to that build. |

Two heroes run your sessions; three serve inside them; one more arrives when its job does.
All Step-1 issue bodies, epic text, and close-out comments speak in these names.

## 1. Owner direction (ratified points)

1. **Spec-writing stays and keeps getting investment** — the *what*, plain language, never the
   how. (Bake-off evidence: the-architect's spec carried a 40/43-fidelity build across a total
   change of executor — B2's strongest data point.)
2. **Plan + tasks docs retire.** The orchestrating agent owns its own how. Open design need:
   assurance that the approach is architecturally sound + sustainable (see §2).
3. **Cross-vendor review survives** — a different model from a different vendor reviews what
   another implemented (B3; re-validated by leg B's two self-review escapes).
4. **configure + run preflights remain a thing.**
5. **review-code KEEPS + EVOLVES into a multi-model review orchestrator** (owner reconsidered
   2026-07-17 after the cross-vendor tension surfaced) — rebuilt on the public Anthropic
   code-review skeleton, see §2-B.
6. **Two canonical session types** — advisor + builder — formalized (§3, the discussion core).
7. **PHILOSOPHY woven into every session** — e.g. a SessionStart hook injecting a distilled
   version (§5).
8. **Test-pilot plans tie directly/comprehensively back to the spec** (or the issue when no
   spec) — pre-existing issue #362 graduates to the top of the new lane.
9. Retirements: everything in v1's RETIRE rows, "and likely more" — spine, couriers, workflow
   driver, allowance/enforcer, journal/readout, acceptance harness, release-evidence gate,
   preflight readout machinery, PLUS plan/tasks + review-plan/review-tasks + (pending §2)
   review-code.
10. **External-guidance alignment pass done 2026-07-18** (Cherny "Steps of AI Adoption";
   Mukta "beyond memory to dreaming" DevCon talk): v2 confirmed directionally aligned — the
   session types map to the ladder's step-2/3 roles, the retirement matches "codify determinism
   only after signal," our markdown memory practice is their stated state of the art. Owner
   ratified factoring in TWO additions (§2-E dreaming loop; advisor cost-watch duty) and
   explicitly declined hard-framing the new ROADMAP in the steps ladder. NOT adopted (B6
   discipline): fleet-scale memory machinery (hashing/concurrency/permission tiers); the
   Managed Agents memory+dreaming API goes on the orientation-review watchlist instead.

## 2. Two design resolutions under discussion

**A. Soundness without doc gates — THE BUILD BRIEF (owner-ratified 2026-07-18, replaces
plan/tasks).** Evidence base: leg B planned unprompted but its biggest architecture finding
(scattered stage machine) was exactly what leg A's *reviewed* plan had specified away; the
2026-07-18 research sweep found the entire industry concentrates architectural enforcement at
the plan-approval boundary ("plan review is the new linter") while LLM diff-reviewers reliably
miss system-level decisions. Design:

*The artifact.* After triage/exploration and before writing code, the builder writes a **build
brief** — ~20–40 lines in the issue (carried into the PR description) with a six-item contract:
1. **Shape** — what gets built where (new modules vs. extensions, layer per piece, expected
   diff size — the §2-C scope tripwire's input: an oversized shape triggers the split proposal
   here, before code).
2. **Contracts & state** — new/changed interfaces and data shapes; where state lives and who
   mutates it. (Every important leg-B architecture finding was a contracts-and-state question.)
3. **Reuse plan** — what existing code it builds on; what it checked for before writing new.
   (Duplication-instead-of-reuse is the one MEASURED AI drift pattern — GitClear.)
4. **Hard seams** — the 2–3 riskiest spots and how each is handled; conscious deferrals stated.
5. **Rejected alternatives** — one line each (what makes reviewing the brief meaningful).
6. **Consequential flags** — irreversible/expensive items (migrations, new dependencies,
   auth/data-model, external contracts) that go to the OWNER before build; unflagged work
   proceeds autonomously; the owner can pre-authorize categories in the issue.

*The check — synchronous, in-session, pre-code.* The builder dispatches ONE fresh-context
reviewer subagent over the brief against the repo. **The check reviewer runs a model tier UP
from the builder's implementation tier, and by default a different vendor** (owner-ratified:
"a tier up and probably another model") — resolved via configure's model/engine knobs (§2-D).
One pass, findings folded in or disputed-with-reason; no rounds, no caps, no cross-session
choreography. Fresh context = B3's minimum rung, at the altitude where an error is cheapest.

*Living artifact.* If the approach materially changes mid-build, the brief is updated with a
one-line change log (drift visible, never silent). The advisor's PR vet judges the code
AGAINST the brief — brief-vs-code divergence is a first-class finding even when the code is
good. The owner enters only at consequential flags (tenet 3, mechanically placed).

*Builder subagent depth rule (harness reality, 3x observed):* background agents that spawn
background agents lose their notification chain — builders run subagents synchronously or
flat (one level deep). Goes in the builder charter verbatim.

*Companion mechanisms from the research sweep (owner-reviewed 2026-07-18):*
- **Named spike: mechanical boundary enforcement, per project** — mature import/dependency
  linters (dependency-cruiser / eslint-plugin-boundaries / import-linter) as CI gates. Boundary
  definition does NOT ask the owner for architecture judgment (persona rule, §0): the system
  derives proposed boundaries from the codebase and presents each as one plain sentence ("the
  picker shouldn't know pantry exists"); the owner blesses or vetoes consequences, never
  drafts rules. The only surveyed mechanism that catches what both panels AND self-review
  provably missed (the leg-B `CreateStage`→`pantry-utils` coupling is a one-line boundaries
  rule). Per-repo config → lives in `configure`. Optional second phase: feed violations back
  to builders via a hook (tsarch pattern — nascent, evaluate in-spike).
- **Steering-file investment stays capped**: the only controlled study (ETH Zurich 2026) found
  repo context files marginal-to-negative on task success at +20% cost ("instruction obedience
  paradox"); all drift-reduction claims are anecdotal. Covenant stays short/imperative (§5);
  no constitution-style expansion.
- **Drift metrics feed the dreaming loop** (§2-E): duplicate rate, follow-up-fix rate,
  boundary-violation trend (the OpenAI harness-engineering prescription, GitClear-style
  signals at repo scale).

**B. review-code evolves — HOW deferred to a future spike (owner call 2026-07-17 late).**
Ratified now: review-code stays, keeps cross-vendor multi-model review as its identity, and gets
evolved rather than retired. The concrete design is NOT pre-committed — a dedicated spike
decides it. Spike inputs recorded for that day:
1. Anthropic's code-review exists in two studyable forms — a PUBLIC plugin
   (`anthropics/claude-code` → `plugins/code-review/commands/code-review.md`, 109 lines,
   source-available, © all rights reserved / Commercial Terms — patterns adoptable, prose not
   copyable) and the richer BUILT-IN `/code-review` skill embedded in the CLI binary
   (extractable locally, diffable across CLI updates). Neither is OSS.
2. Patterns observed there worth evaluating (not adopting sight-unseen): tiered parallel
   narrow-lens finders; per-finding independent validation replacing rounds; an explicit
   high-signal / do-not-flag bar.
3. Tracking duty regardless of design (→ orientation review #318): watch upstream
   `plugins/code-review` commits; on CLI updates diff the extracted built-in skill vs a stored
   snapshot — B6 ledger discipline on our biggest remaining bespoke piece.

**C. Small-scope discipline (owner requirement, 2026-07-17 late): v2 is really good at NOT
doing big diffs.** Hypothesis (supported by the bake-off): small diffs reduce architectural
drift and bug escapes. Evidence: leg B's +10,056/−934 63-file PR carried both Important escapes
past four layers of review, and the architecture panel independently flagged its scope-bundling;
this week's small single-issue superheroes PRs vet-clean in one pass each. Coverage collapses
nonlinearly with diff size; drift accrues invisibly inside one big unreviewed change.

Where it lives:
1. **Advisor = decomposer.** Sizing is a charter duty: before an issue reaches a builder, the
   advisor splits too-big work into a small epic of narrowly-scoped, independently mergeable
   issues with an explicit sequence (the proven wave pattern, promoted to charter). (Old #29
   "decomposition spillover" graduates into this duty.)
2. **Builder scope tripwire.** An approach note implying a multi-concern/oversized diff →
   propose a split BEFORE building; a genuinely irreducible big diff ships with an explicit
   scope disclosure (why it couldn't split). Norm + disclosure valve, not a hard gate.
3. **Specs slice into increments.** Spec stays feature-altitude; delivery is walking-skeleton +
   muscles. Worked example: #161 as ~6 PRs (extractions → data-layer uniqueness+migration →
   search-only picker on pantry pilot → beat/unit stages → create stage → dev harness) — each an
   afternoon review, inter-PR drift visible to the advisor as a trajectory.
4. Numeric anchor: RESOLVED 2026-07-18 — **starts qualitative** ("a PR the reviewer holds in
   one sitting"); revisit numbers only if the qualitative norm visibly drifts.

**D. Model configuration + review-panel composition (owner-ratified 2026-07-18).**
1. **v2 configures models for BOTH implementation and review** — builder subagents never
   silently inherit the session model (the #407 build spent Fable on a 1k-line migration; the
   cautionary example). Tiering is configured (configure owns the knobs) or explicitly
   judged-and-disclosed in the PR.
2. **Vendor-complementary review panels**: panel composition adapts to the builder's vendor so
   the maker's vendor never dominates its own checking — e.g. a cursor builder gets a mixed
   Claude+codex panel; a Claude builder gets codex-weighted review.
3. **Durable review receipts** (owner-ratified): the PR dispositions table links to posted
   panel output (PR comment or equivalent durable artifact) — advisor vets never need
   transcript access. This is the tenet-6 boundary without a journal.
4. **Spec-panel asymmetry (the D3 thread, resolution path):** v2 leaves the spec as the only
   doc gate, currently Claude-authored AND Claude-only-reviewed (same-vendor maker/checker at
   the most load-bearing altitude; the owner-approval step is the existing non-Claude check).
   Experiment: add ONE codex lens (adversarial-reader/premortem seat — "what does this spec
   fail to specify") for the next 3-4 specs; keep the seat only if its findings are
   non-duplicative at a useful rate. Evidence decides, per B3's re-check discipline.

**E. The dreaming loop (owner-ratified 2026-07-18): an out-of-band learning pass so the
discipline layer doesn't go stale.** In-band memory upkeep has a ceiling (split focus mid-task;
one session's visibility) — the exact gap Mukta's talk names, and v2's charters/covenant/
CLAUDE.mds/memory would otherwise only improve via ad-hoc owner feedback. Design (lineage: the
orientation review #318 + the retired #293 observatory, unified):
1. An **independent scheduled dreaming routine** (owner-ratified 2026-07-18: NOT an advisor
   duty — assigning it to the advisor would recreate the in-band split-focus problem one level
   up) — its own session/schedule and budget, out-of-band from any task and any standing role.
2. Reviews the period's material fleet-wide: session transcripts, PRs + dispositions, vet notes,
   filed issues — scrutinizing what actually happened (tool calls and outcomes, not narratives).
3. Proposes changes to the memory store, charters, covenant, and project CLAUDE.mds — every
   proposal carrying **evidence: concrete examples + prevalence + why** — as a batch the owner
   accepts/rejects item-by-item. Nothing self-applies.
4. Light memory guardrails adopted with it: a provenance line on memory writes (session/date/
   evidence pointer); owner remains the gate on substantive memory rewrites. No hashing/
   concurrency/permission machinery at this scale.
5. Cadence + exact scope = open thread (§4); candidate: biweekly or post-release, folded into
   the orientation review so one routine walks both the outward (platform) and inward
   (practice) sweeps.
6. **Eventual home (owner-ratified 2026-07-18): the maintainability guardian (#41)** — dreaming
   is the practice-health half of that hero's inward sweep (codebase health being the other);
   #41 stays open, rescoped to absorb this at build time; hero naming deferred to then.

## 3. The two canonical session types (the formalization core)

**Showrunner (the advisor session)** — project-level, long-lived, typically one per project:
1. Thinks about the project broadly: roadmap, priorities, what to build/simplify next.
2. Vets PRs **from artifacts, never narratives** — byte-level against issue/spec and the build
   brief. Vet-time execution posture (owner-ratified 2026-07-18): **trust CI-green as the
   receipt for "the suite passes" — never re-run green suites; spend vet time on adversarial
   probes the suite doesn't contain** (does the guard actually fire when its target breaks,
   does the test assert what its name claims, does the behavior actually behave). Local runs
   only when CI hasn't run (freshens, conflicts) or a specific claim needs a new probe.
3. Owns board hygiene: files+wires issues at discovery, keeps epics/milestones truthful, edits
   owner-authored bodies in place, closes with receipts.
3b. **Decomposes and routes** (owner-ratified 2026-07-18: routing is an advisor function):
   sizes every issue before it reaches a builder; splits too-big work into small epics of
   narrowly-scoped, independently mergeable issues with a sequence (§2-C); and marks each
   issue's route — **build-ready** (rip directly) vs. **needs-discovery** (spec with the owner
   first). The builder keeps one honesty backstop: a "ready" issue that turns out fuzzy →
   stop and report, never guess or self-launch discovery.
4. Diagnoses anomalies from artifacts (runs, regressions, suspicious claims).
5. Drafts handback prompts for builders; merge trains only under explicit per-batch grants;
   **never merges by default**; grants are spent immediately.
6. Keeps durable memory: decisions, gotchas, owner rulings (with provenance lines per §2-E).
7. **Watches cost and bottlenecks** (owner-ratified 2026-07-18): tracks spend shape across
   builder sessions, flags runaway patterns and model-tier waste (the #464 lesson and the
   "didn't need all the Fable it used" lesson, generalized as a charter duty — a watching
   advisor, not a deterministic enforcer), and names the current bottleneck when advising what
   to build next.
8. **Consumes the dreaming loop's output** (§2-E — owner-ratified 2026-07-18: dreaming runs as
   an INDEPENDENT scheduled routine, not an advisor duty, preserving its dedicated-capacity
   rationale): reacts to accepted proposals (board/memory/charter updates), and feeds it
   material (vet notes, filed issues) by doing its normal work durably.

**Workhorse (the builder session)** — issue-scoped, disposable, parallelizable:
1. Takes an issue; triages: **well-specified → rip directly** (own worktree, build brief +
   pre-code check per §2-A, tiered subagents run flat/synchronous, test-first, browser evidence
   for UI); **fuzzy → discovery/spec with the owner first**, then rip. **Scope tripwire**
   (§2-C): a build brief implying an oversized or multi-concern diff → propose a split before
   building; irreducible big diffs carry an explicit scope disclosure.
2. Ends with review-before-handback: **review-code v2** (the multi-model orchestrator, §2-B);
   findings resolved or explicitly disclosed in a **dispositions table** in the PR body.
3. Ships a ready PR with honest disclosures; **never merges**; hands back.

**The loop:** issue → builder rips → PR (approach note + dispositions) → advisor vets
independently → owner merges. Every arrow is a context boundary — independence by construction.

**Mechanics:** two charter skills (`superheroes:advise`, `superheroes:build`) invoked at session
kickoff (owner names the role, or the session infers from the ask and confirms). SessionStart
hook injects the shared core (§5) + a one-line pointer to both charters.

**Session-type questions — ALL RESOLVED (owner, 2026-07-18):**
- Advisor scope: **per-project**; owner's memory carries any cross-project thread.
- Advisor **owns release coordination** explicitly in the charter.
- Handoff medium: **issues + PRs only** — durable, no new machinery.
- Investigator: **advisor duty for now**, eventually supported by a dedicated skill (the
  systematic-debugging shape: a repeatable forensics protocol the advisor invokes).

## 4. Open threads (settle before Phase-2 build)

1. ~~§2-A ratify~~ RESOLVED 2026-07-18 (build brief + tier-up cross-vendor pre-code check);
   remaining from it: the mechanical-boundary-enforcement spike (per-repo, via configure).
2. review-code evolution spike (§2-B) — design the multi-model orchestrator; scheduled after
   the shape settles, not blocking the path-forward PR (v2 ships with review-code as-is or
   minimally trimmed; the spike then evolves it).
2b. §2-C numeric anchor: guidance numbers vs purely qualitative (owner call).
3. Session-type charters: answer §3 open questions, then charters get drafted for review.
4. configure + preflight scope in the new shape: what a "run preflight" checks when there is no
   spine run (candidate: engine/model availability + auth for the cross-vendor lens, test-pilot
   readiness, worktree hygiene, board wiring for the issue being ripped).
5. Test-pilot ↔ spec binding (#362 rescope): plan derives from spec acceptance criteria (or
   issue body), coverage read back against it comprehensively.
6. PHILOSOPHY.md amendment shape (§5) + the distilled injected covenant.
7. What "sustainable architecture" assurance means over time (beyond per-build): candidate = a
   periodic advisor architecture sweep (audit-debt lineage) instead of per-build gates —
   possibly a lens WITHIN the dreaming loop rather than its own routine.
8. Dreaming loop mechanics (§2-E): cadence (biweekly vs post-release vs both), material scope,
   whether it folds into the orientation review as one combined sweep, and its budget posture.

## 5. PHILOSOPHY in every session

- **PHILOSOPHY.md** amended honestly per its own re-check clauses: B1 (staged pipeline) rewritten
  — checkpoints/judgment survive, deterministic execution spine retired on bake-off + defect-
  ledger evidence; B6 recorded as fired-and-applied. Tenets 1–6 unchanged. **§1 persona
  amendment (owner-ratified 2026-07-18):** drop "many know good engineering when they see it" —
  the prototypical owner reports even recognition can't be assumed; the persona line becomes
  "can describe what they want, tell whether it works, read code a little," and the system's
  corresponding obligation is stated: decisions routed to the owner arrive as plain
  consequences, never craft calls.
- **Injection**: SessionStart hook injects a distilled covenant (~50 lines): the six promise
  tenets in operational form, never-merge, review-before-handback, claims-need-receipts,
  disclose-degradation, plus the session-type pointer. Full doc stays in-repo as reference.
- Skills cite the covenant, not long rubric files, where possible.

## 6. Dispositions (PARKED — owner: "important but not urgent")

v1's tables (issue bulk-close list, survivors + new milestones S1/S2/S3+M7, epic closures, PR
closures #461/#462, release PR #456 handling, board overhaul steps) carry forward as the working
draft, now extended by the additional retirements in §1.9 (plan/tasks/review-plan/review-tasks/
review-code issues join the close list; #401 folds into §2 design; #111 closes — superpowers
severance moot; #362 graduates). Final tables get re-derived AFTER §3–§4 settle.

## 7. Execution sequence (unchanged in spirit, re-derived after shape settles)

Phase 0 align (this doc) → Phase 1 dispositions → Phase 2 one `feat(superheroes)!` path-forward
PR (retirements + charters + hook + PHILOSOPHY/ROADMAP/README/CONVENTIONS rewrite + CI prune) →
Phase 3 review + owner merge + release cut → Phase 4 first-run evidence (next weekly-eats
feature through builder+advisor shape).

## 8. Risks / honest caveats (carried from v1, updated)

1. n=1 bake-off; hedged by keeping owner checkpoints, spec discipline, and two independent
   review layers.
2. Losing mechanical forensics with the journal — accepted; revisit-trigger: the second time a
   "what happened" question can't be answered from PRs/issues/transcripts, reopen a light
   record mechanism.
3. Charters could bloat back into a spine. Guard: charters are prompts + conventions; any new
   deterministic machinery needs a named consumer + a B6-style ledger entry (rule goes to
   CONVENTIONS).
4. Merged-but-unreleased spine work dies unshipped — sunk cost acknowledged; lessons persist in
   history + memory.
