# superheroes — roadmap

superheroes is a **discipline layer** for building software with AI sessions — not a system
that runs the build for you. Your sessions do the work; superheroes supplies the roles,
artifacts, and review structure that let a technical owner delegate real work to them and ship
on evidence instead of vibes. Two heroes run your sessions: **Showrunner** (the advisor — one
long-lived session per project that keeps the board truthful, routes and sizes work, vets every
PR from artifacts, and coordinates releases) and **Workhorse** (the builder — a disposable
session per issue that briefs its approach, gets the brief checked cross-vendor before code,
builds test-first in its own worktree, and hands back a reviewed PR). Three more serve inside
them: **The Architect** (turns fuzzy intent into an owner-approved spec), **Review Crew** (the
cross-vendor review panels), and **Test-Pilot** (browser-evidence verification). Neither hero
merges — that act stays the owner's, always.

**Why this roadmap looks the way it does:** [PHILOSOPHY.md](PHILOSOPHY.md) — the promises and
bets this train exists to deliver. Issue-level status lives on the
[GitHub Project](https://github.com/users/zwrose/projects/1); per-release detail lives in each
release's **epic issue**. This file carries the train itself: what ships together, in what
order, and what each release must prove before it cuts.

## When we cut a release

1. **Receipts decide, not calendars.** A release cuts when its headline claims each have a
   receipt or a loud, stated deferral. No date-driven releases; no claim-free waiting either —
   a bundle that's ready, ships.
2. **Small and frequent beats big and rare.** Every release's first real run must surface zero
   fidelity-class surprises (PHILOSOPHY B5); small bundles keep that test cheap and its
   failures attributable.
3. **The first real run is part of the release.** A release isn't "good" until one real
   work-item run on it is diagnosed clean (the first-run-clean protocol). The next bundle
   doesn't build on an undiagnosed release.
4. **The hotfix lane is always open.** A guardrail or honesty defect ships alone as a patch,
   immediately.
5. **Repo-root work cuts no release** — docs, ledgers, board changes land ahead of and between
   releases.

## The release train

Each release has an **epic issue** (off the Project board) carrying its full scope, its
claims → receipts table, and the at-cut assessment prompt. Status here is coarse:
*planned → in window → cut → first-run-clean*.

| Release | Theme | Epic | Core scope | Must prove before cut | Status |
|---|---|---|---|---|---|
| **0.15.0** | The discipline layer (superheroes v2) | #467 | The reframe itself: the v1 orchestration machinery and plan/tasks retired; two-charter session model (Showrunner advisor / Workhorse builder); the covenant + SessionStart injection; the minimal owner-authority gate; test-pilot observe-only; configure trim + per-role model×engine knobs + live-exercise preflight; PHILOSOPHY/README/CONVENTIONS/ROADMAP rewrite. | The reframe holds under its own first real run — the next real feature built through Workhorse+Showrunner surfaces zero fidelity-class surprises. | **cut 2026-07-19** (superheroes-v0.15.0) · **first-run-clean 2026-07-20** — two real builds diagnosed clean (the weekly-eats households data core, then the onboarding doorway on 0.16.0), and the blind qualification credited on the second: non-default configured knobs consumed and honestly recorded in PR provenance, and preflight surfaced an unauthorized browser tool pre-autonomy (receipts on epic #467, closed). Wave evidence: #486 (test-pilot-execute becomes observe-and-report), #487 (the minimal owner-authority gate), #488 (configure trim + v2 knobs) all merged. #488 was the first real run of the merged Workhorse charter — the delegated-implementation pattern field-validated (eight sonnet implementer work orders, orchestrator receipt re-runs), and a cross-vendor codex pass caught a provenance bug a single Claude review round missed. The charter friction the wave hit — no running app, test-pilot N/A on a plugin repo — is folded back into the charter as an explicit N/A branch. |
| **0.16.0** | Post-S1 hardening (cut early — versions float, see below) | — | Four post-S1 smalls with receipts in hand: review-spec durable round receipts + front-half prose pass (#493), RELEASING.md v2 (#494), the DoD disposition-table mandate (#495), the launch-mismatch guard (#496). | (cut on receipts — each item advisor-vetted and merged) | **cut 2026-07-19** (superheroes-v0.16.0) |
| **0.17.0** | First S2 tranche (cut on receipts — versions float) | — | Eight S2-lane items merged with vetted receipts: panel-level confidence escalation retired (#505), the role/vendor taxonomy foundation — vendor registry, config ladders, role×vendor matrix (#509), lens enrichment — deleted-line audit, caller tracing, do-not-flag bar, grounding seat, focus flags (#511), the B6 upstream-review-surfaces ledger entry (#513), the doc lens recast — six doc-native review-spec lenses + roster guard (#515), the provenance pincer — citation rule + validator (#517), doc-loop cap reconciliation (#518), and launch-prompt discipline (#520). | (cut on receipts — each item advisor-vetted and merged; the 2026-07-21 merge train ran under an explicit one-time owner grant) | **cut 2026-07-21** (superheroes-v0.17.0) |
| **S2 lane** | Review quality (Review Crew v2) | #476 | The S2 lane: review-code v2 — design spike #474 ratified 2026-07-20, shipping as its build arc (#505–#513: loop core #505–#508, taxonomy/composition #509–#510, lens/receipt/ledger smalls #511–#513) + the review-spec v2 leg — design spike #514 ratified 2026-07-20, shipping as the doc-side arc #515–#519 (#34 refuted and closed with #229 into its record); the boundary-enforcement spike (#475, resolved — no day-to-day machinery, folded into the G1 lane); review-benchmark growth (#131); trap-taxonomy rubric classes (#316); the orientation-review routine (#318). | review-code v2 ships and one real PR goes through it clean. | **in window** — first tranche cut in 0.17.0; remaining: loop core #506–#508, panel composition #510, receipt convention #512, doc-side #516/#519, parity #525, plus #131/#316/#318 |
| **S3 lane** | Front-half depth (Test-Pilot) | #477 | The S3 lane: test-pilot plans derive from the spec (#362); test-pilot's documented-command surface for CLI/library repos (#363). (Spec-panel right-sizing #34 and spec provenance #229 rolled into the review-spec v2 spike #514, S2 lane — 2026-07-20.) | Each item's headline claim carries a receipt in the epic; the lane closes with a real spec-to-build run diagnosed clean. | planned |
| **G1 lane** | Maintainability guardian (new hero) | #503 | The G1 lane: the guardian design spike (#41 — identity, cadence, lens set, output contract, adjudication memory, artifact storage, cost; boundary analysis from spike #475 is its first candidate lens); implementation issues decompose from the ratified spike outcome. Pulled forward from the growth backlog by owner call 2026-07-20 — the v2 loop it needs already exists. | The guardian hero ships; sweeps run on ≥1 real calibrated project and one full loop (sweep finding → blessed issue → build → merge) completes. | planned |

## Receipts decide cut order, not a ladder

The S2, S3, and G1 lanes above are **largely seam-independent** — S2 sits in the review layer,
S3 sits in the front half (test-pilot), G1 is a new hero of its own — and may
interleave where their builders don't collide. This is deliberately **not a step ladder**: per cut rule 1, receipts decide the
actual cut order, not the order the lanes happen to be listed in. **Version numbers float free of
the lanes** — a release cuts whenever merged receipts justify one (the 0.16.0 cut on post-S1
hardening smalls is the standing precedent), and a lane's work lands in whatever minor is next
when its receipts arrive. Epics are named by lane (S2/S3/G1), never by a promised version.

## How work is tracked

- **Epics, off-board:** one epic issue per release — its constituents attached as GitHub
  **native sub-issues** (the epic's sub-issue progress is the bundle's completion state), the
  claims→receipts table, and an at-cut assessment prompt a fresh agent can execute. The epic
  closes only when the post-release first-run diagnosis is clean.
- **Dependencies:** real technical dependencies between work items carry GitHub's native
  blocked-by/blocking links. The train is serialized through the epics **at the reframe
  boundary**: every S2/S3/G1 build-carrying constituent is blocked-by 0.15.0's epic (#467), so no
  lane formally unblocks until the reframe closes clean (cut rule 3, encoded mechanically). Once
  unblocked, the lanes run independently of each other — see above.
  **Full-discovery issues are exempt** — discovery runs in parallel with the train, so they
  carry no precursor-epic block; only build-carrying issues take it. (Keeping this wiring true
  by hand is toil the build-dispatch discovery may eventually relieve — #526.)
- **Discovery first where it's earned:** fuzzy items file as discovery issues (problem +
  evidence + open questions, no prescribed solution) and build only after an owner-approved
  spec. Currently: the guardian design spike (#41, discovery ahead of the G1 build); the
  build-dispatch discovery (#526, owner-run with the advisor); both S2
  design spikes (#474 code loop, #514 doc loop) ratified and closed 2026-07-20, their build
  arcs filed.

## Unscheduled (deliberately)

The growth backlog — greenfield/productionize onramps (#39 #40) — waits behind the stability
gate: **two consecutive releases whose first real runs diagnose clean.** The train above is
engineered to produce exactly that. PHILOSOPHY B7 governs: evidence before machinery.
*(The maintainability guardian (#41) left this list 2026-07-20 — pulled forward by owner call
into its own G1 lane, epic #503: the v2 loop it needs already exists, and the lane runs
alongside S2/S3. The backlog/TPM-hero cluster (#27 #28 #29 #31) and queue controller (#22) left
too — superseded by owner ruling 2026-07-21: the advisor absorbed the TPM role, and the launcher
question is now the build-dispatch discovery #526.)*

## Keeping this file honest

Update this file when — and only when — a release cuts or reorders, an epic opens or closes, a
cut rule changes, or the build lane reschedules. Issue-level status never lives here (that's the
Project and the epics). If this file needs edits more than release-ish often, it has drifted
into being a status board — stop and fix the process instead.
