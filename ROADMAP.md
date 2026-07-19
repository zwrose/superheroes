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
| **0.15.0** | The discipline layer (superheroes v2) | #467 | The reframe itself: the v1 orchestration machinery and plan/tasks retired; two-charter session model (Showrunner advisor / Workhorse builder); the covenant + SessionStart injection; the minimal owner-authority gate; test-pilot observe-only; configure trim + per-role model×engine knobs + live-exercise preflight; PHILOSOPHY/README/CONVENTIONS/ROADMAP rewrite. | The reframe holds under its own first real run — the next real feature built through Workhorse+Showrunner surfaces zero fidelity-class surprises. | **cut 2026-07-19** (superheroes-v0.15.0) — first-run-clean pending: the weekly-eats households build (the first real feature through Workhorse+Showrunner) is in flight; epic #467 closes on its diagnosis. Wave evidence: #486 (test-pilot-execute becomes observe-and-report), #487 (the minimal owner-authority gate), #488 (configure trim + v2 knobs) all merged. #488 was the first real run of the merged Workhorse charter — the delegated-implementation pattern field-validated (eight sonnet implementer work orders, orchestrator receipt re-runs), and a cross-vendor codex pass caught a provenance bug a single Claude review round missed. The charter friction the wave hit — no running app, test-pilot N/A on a plugin repo — is folded back into the charter as an explicit N/A branch. |
| **0.16.0** | Post-S1 hardening (cut early — versions float, see below) | — | Four post-S1 smalls with receipts in hand: review-spec durable round receipts + front-half prose pass (#493), RELEASING.md v2 (#494), the DoD disposition-table mandate (#495), the launch-mismatch guard (#496). | (cut on receipts — each item advisor-vetted and merged) | **cut 2026-07-19** (superheroes-v0.16.0) |
| **S2 lane** | Review quality (Review Crew v2) | #476 | The S2 lane: review-code v2 multi-model orchestrator — design spike (#474) then build; mechanical boundary enforcement per project via configure (#475); review-benchmark growth (#131); trap-taxonomy rubric classes (#316); the orientation-review routine (#318). | review-code v2 ships and one real PR goes through it clean. | planned |
| **S3 lane** | Front-half depth (The Architect + Test-Pilot) | #477 | The S3 lane: test-pilot plans derive from the spec (#362); test-pilot's documented-command surface for CLI/library repos (#363); right-sizing the spec review panel, including the codex-seat experiment (#34); spec provenance (#229). | Each item's headline claim carries a receipt in the epic; the lane closes with a real spec-to-build run diagnosed clean. | planned |

## Receipts decide cut order, not a ladder

The S2 and S3 lanes above are **largely seam-independent** — S2 sits in the review layer,
S3 sits in the front half (spec and test-pilot) — and may interleave where their builders
don't collide. This is deliberately **not a step ladder**: per cut rule 1, receipts decide the
actual cut order, not the order the lanes happen to be listed in. **Version numbers float free of
the lanes** — a release cuts whenever merged receipts justify one (the 0.16.0 cut on post-S1
hardening smalls is the standing precedent), and a lane's work lands in whatever minor is next
when its receipts arrive. Epics are named by lane (S2/S3), never by a promised version.

## How work is tracked

- **Epics, off-board:** one epic issue per release — its constituents attached as GitHub
  **native sub-issues** (the epic's sub-issue progress is the bundle's completion state), the
  claims→receipts table, and an at-cut assessment prompt a fresh agent can execute. The epic
  closes only when the post-release first-run diagnosis is clean.
- **Dependencies:** real technical dependencies between work items carry GitHub's native
  blocked-by/blocking links. The train is serialized through the epics **at the reframe
  boundary**: every S2/S3 constituent is blocked-by 0.15.0's epic (#467), so neither lane
  formally unblocks until the reframe closes clean (cut rule 3, encoded mechanically). Once
  unblocked, the S2 and S3 lanes run independently of each other — see above.
  **Full-discovery issues are exempt** — discovery runs in parallel with the train, so they
  carry no precursor-epic block; only build-carrying issues take it. (Keeping this wiring true
  by hand is toil a future backlog/TPM hero should own — #28.)
- **Discovery first where it's earned:** fuzzy items file as discovery issues (problem +
  evidence + open questions, no prescribed solution) and build only after an owner-approved
  spec. Currently: review-code v2's design spike (#474, discovery ahead of the S2 build) and
  the spec-panel codex-seat experiment (#34, discovery ahead of the S3 lane's panel work).

## Unscheduled (deliberately)

The growth backlog — backlog/TPM hero (#27 #28 #29 #31), greenfield/productionize onramps
(#39 #40), maintainability guardian (#41), queue controller (#22) — waits behind the stability
gate: **two consecutive releases whose first real runs diagnose clean.** The train above is
engineered to produce exactly that. PHILOSOPHY B7 governs: evidence before machinery.

## Keeping this file honest

Update this file when — and only when — a release cuts or reorders, an epic opens or closes, a
cut rule changes, or the build lane reschedules. Issue-level status never lives here (that's the
Project and the epics). If this file needs edits more than release-ish often, it has drifted
into being a status board — stop and fix the process instead.
