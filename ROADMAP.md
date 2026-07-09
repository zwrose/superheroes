# superheroes — roadmap

superheroes is a single Claude Code plugin — a team of heroes that runs a project's
development loop — **Discovery → Plan → Tasks → Build → Verify → Ship** — on the owner's
behalf, so a product-minded owner can live in the *what* while the heroes handle the
*how*. The team fields **the-architect** (spec → plan → tasks), **review-crew** (the
review panels), **test-pilot** (behavioral proof in a real browser), **workhorse** (the
producer — never merges), and the **showrunner** (the full pipeline, end to end).

**Why this roadmap looks the way it does:** [PHILOSOPHY.md](PHILOSOPHY.md) — the
promises and bets this train exists to deliver. Issue-level status lives on the
[GitHub Project](https://github.com/users/zwrose/projects/1); per-release detail lives
in each release's **epic issue**. This file carries the train itself: what ships
together, in what order, and what each release must prove before it cuts.

## When we cut a release

1. **Receipts decide, not calendars.** A release cuts when its headline claims each
   have a receipt or a loud, stated deferral. No date-driven releases; no claim-free
   waiting either — a bundle that's ready, ships.
2. **Small and frequent beats big and rare.** Every release's first real run must
   surface zero fidelity-class surprises (PHILOSOPHY B5); small bundles keep that test
   cheap and its failures attributable.
3. **The first real run is part of the release.** A release isn't "good" until one
   real work-item run on it is diagnosed clean (#293 protocol). The next bundle doesn't
   build on an undiagnosed release.
4. **The hotfix lane is always open.** A guardrail or honesty defect ships alone as a
   patch, immediately.
5. **Repo-root work cuts no release** — docs, ledgers, board changes land ahead of and
   between releases.

## The release train

Each release has an **epic issue** (off the Project board) carrying its full scope,
its claims → receipts table, and the at-cut assessment prompt. Status here is
coarse: *planned → in window → cut → first-run-clean*.

| Release | Theme | Core scope | Must prove before cut | Status |
|---|---|---|---|---|
| **0.12.0** | Engines tell the truth | #307 #308 #309 #310 #311 + small disclosure fixes | codex review genuinely runs (≥1 `ok` external dispatch in acceptance); readout model rows match dispatched reality; acceptance FAILs on an all-fallback run | planned |
| **0.13.0** | Nothing degrades invisibly | degradation tallies + degraded-flag consumers; owner-declared degradation policy; sanitized-posture acceptance leg; #257; #299; harness architecture per its discovery | an all-Claude run cannot look like an external-engine run; acceptance tests the permission posture real users ship | planned |
| **0.14.0** | Built what you meant | terminal spec-fidelity instrument (discovery first); #230 #229 #189 #175 | "ready" is backed by a spec-vs-build receipt, used by the release-eval itself | planned |
| **0.15.0** | Judgment and readable runs | trap-taxonomy review classes; agent read-back + plain-language park reasons; #219 #137 #32; guardrail edges (publish scope, checker-not-outmatched, gate provenance) | each new rubric class demonstrated firing; park reasons owner-readable; the never-publishes guarantee matches its prose | planned |

**The build lane alongside the train** (mechanisms that mostly cut no version but are
scheduled work): the **0.12 window** also builds the orientation review + ledgers
(first memo before the 0.13 cut); the **0.13 window** builds claim-based release eval
(ships in 0.13, first mechanical use at the 0.14 cut) and extends the review benchmark
(#131, unblocked once reviews are genuinely dual-vendor); the **0.14–0.15 windows**
absorb the telemetry-checkpoint decisions (#184 #34 #250), the tuning loop (#35), and
the task-granularity research recommendation.

## How work is tracked

- **Epics, off-board:** one epic issue per release — scope checklist, claims→receipts,
  an at-cut assessment prompt a fresh agent can execute, blocked-by links to every
  constituent. The epic closes only when the post-release first-run diagnosis is clean.
- **Dependencies:** issues carry GitHub's native blocked-by/blocking links; an epic's
  dependency graph is its bundle's completion state.
- **Discovery first where it's earned:** fuzzy items file as discovery issues (problem
  + evidence + open questions, no prescribed solution) and build only after an
  owner-approved spec. Currently: the spec-fidelity instrument and the
  acceptance-harness architecture rethink (full); publish-guardrail width and the agent
  read-back experience (quick route).

## Unscheduled (deliberately)

The growth backlog — backlog/TPM hero (#27 #28 #29 #31), greenfield/productionize
onramps (#39 #40), maintainability guardian (#41), queue controller (#22) — waits
behind the stability gate: **two consecutive releases whose first real runs diagnose
clean.** The train above is engineered to produce exactly that. PHILOSOPHY B7 governs:
evidence before machinery.

## Keeping this file honest

Update this file when — and only when — a release cuts or reorders, an epic opens or
closes, a cut rule changes, or the build lane reschedules. Issue-level status never
lives here (that's the Project and the epics). If this file needs edits more than
release-ish often, it has drifted into being a status board — stop and fix the process
instead.
