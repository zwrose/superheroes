# superheroes — roadmap

superheroes is a **discipline layer** for building software with AI sessions — not a system
that runs the build for you. Your sessions do the work; superheroes supplies the roles,
artifacts, and review structure that let a technical owner delegate real work to them and ship
on evidence instead of vibes. Two heroes run your sessions: **Showrunner** (the advisor — one
long-lived session per project that keeps the board truthful, routes and sizes work, vets every
PR from artifacts, and coordinates releases) and **Workhorse** (the builder — a disposable
session per issue that briefs its approach, gets the brief checked cross-vendor before code,
builds test-first in its own worktree, and hands back a reviewed PR). Four more serve inside
them: **The Architect** (turns fuzzy intent into an owner-approved spec), **Review Crew** (the
cross-vendor review panels), **Test-Pilot** (browser-evidence verification), and **Guardian**
(the maintainability guardian — read-only repo-health sweeps that turn drift into plain-language
consequences with receipts). Neither hero merges — that act stays the owner's, always.

**Why this roadmap looks the way it does:** [PHILOSOPHY.md](PHILOSOPHY.md) — the promises and
bets this train exists to deliver. Issue-level status lives on the
[GitHub Project](https://github.com/users/zwrose/projects/1); an area's constituents live in
that area's **milestone**. This file carries only the coarse train: the cut rules, the cut
record, and the areas of focus.

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

## The cut record

Releases already cut, with what each proved. Historical receipts — rows are append-only.
Status vocabulary: *cut → first-run-clean*.

| Release | Theme | Epic | Core scope | Must prove before cut | Status |
|---|---|---|---|---|---|
| **0.15.0** | The discipline layer (superheroes v2) | #467 | The reframe itself: the v1 orchestration machinery and plan/tasks retired; two-charter session model (Showrunner advisor / Workhorse builder); the covenant + SessionStart injection; the minimal owner-authority gate; test-pilot observe-only; configure trim + per-role model×engine knobs + live-exercise preflight; PHILOSOPHY/README/CONVENTIONS/ROADMAP rewrite. | The reframe holds under its own first real run — the next real feature built through Workhorse+Showrunner surfaces zero fidelity-class surprises. | **cut 2026-07-19** (superheroes-v0.15.0) · **first-run-clean 2026-07-20** — two real builds diagnosed clean (the weekly-eats households data core, then the onboarding doorway on 0.16.0), and the blind qualification credited on the second: non-default configured knobs consumed and honestly recorded in PR provenance, and preflight surfaced an unauthorized browser tool pre-autonomy (receipts on epic #467, closed). Wave evidence: #486 (test-pilot-execute becomes observe-and-report), #487 (the minimal owner-authority gate), #488 (configure trim + v2 knobs) all merged. #488 was the first real run of the merged Workhorse charter — the delegated-implementation pattern field-validated (eight sonnet implementer work orders, orchestrator receipt re-runs), and a cross-vendor codex pass caught a provenance bug a single Claude review round missed. The charter friction the wave hit — no running app, test-pilot N/A on a plugin repo — is folded back into the charter as an explicit N/A branch. |
| **0.16.0** | Post-S1 hardening (cut early — versions float, see below) | — | Four post-S1 smalls with receipts in hand: review-spec durable round receipts + front-half prose pass (#493), RELEASING.md v2 (#494), the DoD disposition-table mandate (#495), the launch-mismatch guard (#496). | (cut on receipts — each item advisor-vetted and merged) | **cut 2026-07-19** (superheroes-v0.16.0) |
| **0.17.0** | First S2 tranche (cut on receipts — versions float) | — | Eight S2-lane items merged with vetted receipts: panel-level confidence escalation retired (#505), the role/vendor taxonomy foundation — vendor registry, config ladders, role×vendor matrix (#509), lens enrichment — deleted-line audit, caller tracing, do-not-flag bar, grounding seat, focus flags (#511), the B6 upstream-review-surfaces ledger entry (#513), the doc lens recast — six doc-native review-spec lenses + roster guard (#515), the provenance pincer — citation rule + validator (#517), doc-loop cap reconciliation (#518), and launch-prompt discipline (#520). | (cut on receipts — each item advisor-vetted and merged; the 2026-07-21 merge train ran under an explicit one-time owner grant) | **cut 2026-07-21** (superheroes-v0.17.0) |
| **0.18.0** | The guardian ships (G1 build tranche + S2 riders) | — | The guardian hero end-to-end: core sweep shell + lens contract + drift-over-baseline (#535), duplication + complexity×churn-hotspot lenses (#536), dependency-freshness + doc-freshness + dead-code lenses (#537), coupling lens (#538), guardian memory — dispositions ledger, report card, storage, vitals (#539), the invocation-safety + collection-honesty seams (#557/#558) and their composition fix (#561), and the census-fidelity fix (#564). S2 riders: per-finding verification (#506), delta rounds + one-entrypoint round driver + audit-keyed breaker (#507), the high-noise review-eval fixture (#546), the implementer-escalation policy charter (#547), parity-twin retry reconciliation (#525). | (cut on receipts — every PR advisor-vetted; the qualifying receipt was an advisor-run inaugural sweep of this repo. Run 1 caught a real fidelity bug pre-cut — #564, cut rule 2 doing its job — and the official run after the fix came back clean with a junk-on-disk negative control.) | **cut 2026-07-22** (superheroes-v0.18.0) |

## Areas of focus

The active work organizes into a few **areas of focus**, each carried by a **milestone** — an
issue's milestone is its area, and the milestone's progress is the area's state. This file
names each area and what it is about — nothing finer. If you want to know what's in an area
right now, read its milestone, not this file. A few one-off issues deliberately float with no
milestone; a milestone is a grouping, not a mandate.

- **Review quality** — the review layer: the code-review loop and the doc/spec review leg —
  loop mechanics, panel composition, durable receipts, reviewer-seat reliability, eval growth.
  *Status:* active — tranches cut in 0.17.0 and 0.18.0.
- **Front-half depth** — Architect + Test-Pilot depth: test plans derive from the spec; a
  documented-command surface so CLI/library projects get exercised too. *Status:* queued.
- **Maintainability guardian** — the Guardian hero: read-only repo-health sweeps that turn
  drift into plain-language consequences with receipts. *Status:* **build-complete
  2026-07-22** — the hero shipped in 0.18.0, and the inaugural sweep was the cut's qualifying
  receipt (it caught a real fidelity bug pre-cut — cut rule 2 doing its job). Standing
  commitment before this area winds down: a sweep on ≥1 real calibrated project beyond this
  repo, and one full loop (sweep finding → blessed issue → build → merge).
- **Build dispatch & orchestration** — who launches and watches builder sessions; the
  advisor's operational surface. *Status:* discovery-first — the build-dispatch discovery is
  the anchor; build items land here after the owner ratifies its outcome.
- **Growth** — the post-stabilization backlog; see Unscheduled below.

Areas are **largely seam-independent** and interleave freely where their builders don't
collide. This is deliberately **not a step ladder**: per cut rule 1, receipts decide the
actual cut order, not the order the areas are listed in. **Version numbers float free of the
areas** — a release cuts whenever merged receipts justify one (the 0.16.0 cut on hardening
smalls is the standing precedent), and an area's work lands in whatever minor is next when its
receipts arrive. An area closes when its work runs dry — an owner judgment, not a formal gate.

## How work is tracked

- **Milestones carry the areas:** each area of focus is a GitHub milestone, and an issue's
  milestone is its area. One-off issues may float with no milestone.
- **Epics decompose big pieces:** an epic is an ordinary issue that breaks one sizable piece
  of work into GitHub **native sub-issues** — short-lived, closing when its piece ships. An
  epic and its sub-issues live in the same milestone. Epics are never area containers.
  (The guardian build arc is the house example of the shape; the retired area epics each
  closed with a conversion receipt, 2026-07-22.)
- **Dependencies:** real technical dependencies between work items carry GitHub's native
  blocked-by/blocking links — nothing else is serialized. (The v2 reframe was mechanically
  serialized behind 0.15.0's release epic until it closed clean; that boundary is history.)
- **Discovery first where it's earned:** fuzzy items file as discovery issues (problem +
  evidence + open questions, no prescribed solution) and build only after an owner-approved
  spec. Discovery runs in parallel with build work and takes no dependency wiring. Live
  discoveries sit on the Project board, marked as such.

## Unscheduled (deliberately)

The growth backlog — the greenfield and productionize-a-prototype onramps — waits behind the
stability gate: **two consecutive releases whose first real runs diagnose clean.** The train
above is engineered to produce exactly that. PHILOSOPHY B7 governs: evidence before machinery.
*(The maintainability guardian left this list 2026-07-20, pulled forward by owner call into its
own area; the backlog/TPM-hero cluster and queue controller left 2026-07-21, superseded by
owner ruling — the advisor absorbed the TPM role, and the launcher question became the
build-dispatch discovery.)*

## Keeping this file honest

Update this file when — and only when — a release cuts, an area of focus opens or closes, or
a cut rule changes. Issue-level status never lives here (that's the Project and the
milestones), and **no individual work item is ever named in an area entry** — the moment one
appears, this file has drifted into being a status board; stop and fix the process instead.
