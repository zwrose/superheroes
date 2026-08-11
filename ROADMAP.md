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
consequences with receipts). The owner's **approval** — every gate click, release cut, and
publish decision — stays theirs always; neither hero takes that decision, and the builder
never merges.

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
| **0.18.0** | The guardian ships (G1 build tranche + S2 riders) | — | The guardian hero end-to-end: core sweep shell + lens contract + drift-over-baseline (#535), duplication + complexity×churn-hotspot lenses (#536), dependency-freshness + doc-freshness + dead-code lenses (#537), coupling lens (#538), guardian memory — dispositions ledger, report card, storage, vitals (#539), the invocation-safety + collection-honesty seams (#557/#558) and their composition fix (#561), and the census-fidelity fix (#564). S2 riders: per-finding verification (#506), delta rounds + one-entrypoint round driver + audit-keyed breaker (#507), the high-noise review-eval fixture (#546), the implementer-escalation policy charter (#547), parity-twin retry reconciliation (#525). | (cut on receipts — every PR advisor-vetted; the qualifying receipt was an advisor-run inaugural sweep of this repo. Run 1 caught a real fidelity bug pre-cut — #564, cut rule 2 doing its job — and the official run after the fix came back clean with a junk-on-disk negative control.) | **cut 2026-07-22** (superheroes-v0.18.0) · **first-run-clean 2026-07-23** — a structured cross-session learning pass over the wave's first real runs (61 sessions across both calibrated projects: deterministic transcript inventory, domain-detector sweep, cross-PR aggregation) surfaced zero fidelity-class surprises. One mechanical defect found live — a list-valued dimension crashed the review driver's delta settle on a weekly-eats run (#583) — was disclosed, hotfixed, upstreamed, and released in 0.19.0; a crash caught and fixed, not a fidelity escape. |
| **0.19.0** | Guardian field hardening (the weekly-eats inaugural-sweep wave) | — | The rated Python advisory source — OSV via osv-scanner, exactly-pinned scope with disclosed gaps, neutral-config invocation hardening; the critical-vuln red line now fires for Python (#569 via PR #581). Guardian integration gaps from the field — vitals wiring, census siblings, shared census (#566 via PR #580). The charter hygiene bundle — eight owner-ratified conventions into the workhorse + showrunner charters (#571 via PR #573). The review-driver crash fix — canonical string `dimension`; a list-valued dimension wedged delta rounds (#583 via PR #586). | (cut on receipts — every PR advisor-vetted with biting mutation probes; #586 ran the first sanctioned direct-build lane: engine-implemented from a tight work order, explicit advisor review in place of the panel, disclosed in the PR) | **cut 2026-07-23** (superheroes-v0.19.0) |
| **0.20.0** | Guardian validation + charter hygiene 2 | — | Guardian inaugural-baseline validation — validate the quiet before it fossilizes (#574 via PR #593). Coupling lens hardening — plugin-pinned TypeScript for dependency-cruiser + real-module path normalization (#575 via PR #595). Rated Python audit depth — lockfile + transitive coverage across poetry/uv/Pipfile (#582 via PR #596). Charter hygiene 2 — the advisor follow-up-disposition duty (two-tier, receipts-before-claims), terminal-forfeit-only reviewer fallback, headless-dispatch discipline (#591 via PR #594). | (cut on receipts — every PR advisor-vetted) | **cut 2026-07-23** (superheroes-v0.20.0) · **first-run-clean 2026-07-24** — the 0.21.0 wave ran entirely on these charters: all seven handbacks showed the #591/#594 text working unprompted (per-edge echo-backs, remote-head receipts, provenance tables), zero fidelity-class surprises. |
| **0.21.0** | Review composition v2 + engine-dispatch hardening (the first advisor-orchestrated wave) | — | Deterministic review-panel composition — family-keyed independence, author-minority + critical-diversity constraints, seeded rotation (#510 via PR #603), owner per-seat pins (#607 via PR #617), unknown-fixer degrade + engine_dispatch pin (#608 via PR #621), preflight economics — panel-path gating, short-TTL liveness cache, pin-reachable probes (#610 via PR #622). The codex adapter arc closing #563 — parse bounds + stdin hardening (PR #602), the reviewer-scoped managed runner with retry/liveness/anti-hijack (PR #606), loud fall-open dispatch provenance (PR #612). The sanctioned-dispatch guard — an unlisted model is a park, not a pick (#600 via PR #611). Guardian cleanup — dead-sentinel removal (#592 via PR #601), transient-marker coarsening out of the drift key (#613 via PR #619), charter cleanup (#567 via PR #605). Workhorse riders incl. the commit-before-probe tripwire (#599 via PR #618). | (cut on receipts — twelve PRs advisor-vetted with biting mutation probes: seven merged in the first advisor-orchestrated headless wave, five parked overnight and merged in a morning train under per-merge owner approval) | **cut 2026-07-24** (superheroes-v0.21.0) |
| **0.21.1** | Context fit — Claude 5 (the assembly, not the rulebook) | — | Grounded in the #626/#627 context-engineering spikes (charter delete-and-measure refuted as unnecessary — 2 of 463 directive lines were model-native restatement; the real defects were in session assembly). SessionStart bootstrap slimmed to its unique payload (resolved roots + covenant) with a fail-closed harness-dependency tripwire — retiring ~4k tokens/session of duplication and a standing false degradation signal (#629 via PR #631). Charter context-fit pass — stale/duplicate prune, dispatch-mechanics relocation to a load-at-need reference, await-rule widened to any pending outcome, host-precedence note, LEDGERS decline records (#630 via PR #633). Charter hygiene 4 — six riders incl. the own-worktree intake assertion (the shared-tree collision's tripwire) and the minimum-validated-harness README note (#620 via PR #634). | (cut on receipts — advisor-vetted with biting probes; PR #633 ran the first unbound certified full-panel review-code protocol) | **cut 2026-07-25** (superheroes-v0.21.1) |
| **0.21.2** | Dispatch vocabulary + review-base pinning | — | One unified dispatch model vocabulary across guard, registry, and adapter — round-tripping tokens, honored pins, named refusals (#636 via PR #643). Review-code's diff base pinned to a fetched remote commit, closing the #637 contamination class in prose (#637 via PR #641). Configure view renders registry-sourced dispatch-calibration columns (#625 via PR #642). Guardian duplication lens takes jscpd input via config file, retiring the 100KB argv ceiling (#640 via PR #644). | (cut on receipts — every PR advisor-vetted with biting mutation probes; PR #644's headline receipt failed to reproduce at vet and was corrected in place with a re-runnable script — the receipt-integrity guard doing its job) | **cut 2026-07-26** (superheroes-v0.21.2) |
| **0.22.0** | Review trust — a seat's "clean" can be believed | — | The release that makes an external review seat's silence auditable. Claude 5 model refresh + cursor's first-party models merged into one `xai` family, so composer work can no longer be grok-audited (#639/#651 via PR #653, release-restated in PR #673). Cursor CLI declared first-party-only, sunsetting the fable-on-external fall-open (#650 via PR #675). The review base guard becomes machinery — `round_driver` enforces resolve-to-commit and non-empty diff, the round-1 diff is bound to the pin, and a degraded base can never certify an unqualified `converged`; the same build found and fixed a zsh history-modifier bug that had silently failed review-code's base fetch on every macOS host since #641 (#648 via PR #667). The maker's model family is barred from **every** panel seat, with a disclosed same-family degradation when no alternative family is live (#670 via PR #679). The review-trust cluster — read seats pinned to the repo, an investigation-proof floor that turns an unsubstantiated empty return into a named `vacuous` forfeit, and a planted-defect canary shipped as standing machinery (#665/#666/#668 via PR #683). External seats now run against a disposable sanitized export, so the reviewed repo can neither steer its reviewer via auto-discovered agent config nor hide tracked source from it (#684 via PR #688). Charter hygiene 5 and 6 — sixteen mechanical riders (#638 via PR #663, #652 via PR #686). | (cut on receipts — every PR advisor-vetted with adversarial probes reproduced independently of the builder; the qualifying evidence is that the release's own machinery caught real defects mid-wave: a control probe exposed the inert-dispatch defect that filed #668, and a live seat's environment audit inside a sanitized view answered "No" to "did any file give you project-specific instructions?") | **cut 2026-07-27** (superheroes-v0.22.0) |
| **0.23.0** | Doctrine consolidation — lanes, receipts, and the PR-body contract | — | The release that writes the operating discipline into shipping surfaces. Three-lane build doctrine (full/light/micro) with the micro hard-line named (#709). The PR-body contract — owner half + build record, show-it wayfinding, omission floor (#661 via PR #715), and the workhorse preserving advisor-authored body content verbatim landing next release. Vet-receipt doctrine — spine + triggered fields, owner-half verdict write, collector reconciliation (#672 via PR #729). Supervised dispatch — write verb, durable journaling, reviewer retrofit (#726 via PR #740, release re-statement). The check-runner seat + "a review seat never changes the repository, and never claims a run it did not make" (#719 via PR #731). Orchestration doctrine — LEDGERS §4 + R1–R5 charter text (#697). seat_map violations drive the certification shape (#680 via PR #700). Config fall-opens become named refusals — the fail-closed (prefs, status) accessor (#701), migrate_on_read deleted for a named refusal (#724 via PR #730), hygiene 8 part A (#699 via PR #741; part B parked at the rework tripwire, #732). Boundary-sync guard extended to the named cross-lane invariants (#721 via PR #727). PHILOSOPHY approval/execution amendment (#708). Test-pilot execution-calibration teeth (#728). Charter hygiene 7 (#685 via PR #698); the orphaned pr-body tier role retired (#692 via PR #696). | (cut on receipts — every PR advisor-vetted; the cut also surfaced release-please silently dropping two commits, re-stated in #739 — the lesson became the #744 release-bump tripwire that now fails CI loud on any silent exclusion) | **cut 2026-07-31** (superheroes-v0.23.0) |
| **0.25.0** | Review durability + concurrent dispatch (the release that reviewed itself honest) | — | The review loop becomes a durable, replayable, truth-telling machine, and independent dispatches stop paying the serial tax. The #723 review-durability stack, merged as one seven-PR atomic click (stack #957): per-seat durable records + advance/record-result/attest (PR #914), the multi-artifact commit protocol with replay (#918 via PR #921), per-location finding identity (#915 via PR #924), order emission with per-order hash binding + templates as shipped data (car 4a, PR #942), gate-policy/1 grammar + advance wiring + caller-contract CLI validation (car 4b, PR #943), per-phase contracts published with the handback-refusal gate **shipped dark** — arming owned by #954 — and LEDGERS stating it truthfully (car 5, PR #955), and concurrent independent-dispatch batches on all three doctrine surfaces with the invariant pinned by detector + load-refusal (#930 via PR #956; the shipped doctrine records the measurement: 427s against a 987s serial sum at the short launch slice, dispatch-mechanics.md). Alongside the stack, **the pilot framework tranche A1→D11a** — contract home (#837), slot lifecycle (#849), reclaim safety (#858), target boundary (#841), attended seeding with no stored credential (#916), per-slot app lifecycle (#856), auth contract exercises (#852), per-slot browser topology (#854), charter integration (#906), cleanup effect receipt + resurrection/reseed (#857), per-slot artifact store + headless conformance run (#923), and the acceptance matrix + mechanical §14 tripwires (#925). Also: the owner-calibrated workflow allowlist for the owner-authority gate (#947 via PR #950), the cursor write-dispatch dead-report-channel diagnosis + declared-item delivery verification (#907 via PR #951), launcher batch accounting (#878) and the unslotted-parallel-launch refusal (#913), the compaction checkpoint command + charter recovery hooks (#917), the owner-approved front-half SDLC core + detective specs (#922 docs), and a broad fix tranche (FR-8 confirmation rule #890, per-location audit ids #915, calibration/cleanup/journal fail-closed hardenings, and more — CHANGELOG carries the full list). | (cut on receipts — every stack PR full-lane advisor-vetted with biting reverted probes, vet ordinals 76–88; #956's review loop hit a diagnosed 0.24.0 driver dead end — the sticky audit-stall breaker, #960 — and merged on explicit owner acceptance recorded in the PR body, with 28 findings raised-confirmed-discharged across two loops standing in for the certificate; the submit-shape guard that would have prevented the dead end's trigger, #899, ships in this very release) | **cut 2026-08-11** (superheroes-v0.25.0) |
| **0.24.0** | Recovery + dispatch truth (the wave that survived its own stops) | — | The runner now says what actually happened, and a dead session's work is recoverable by doctrine. Forfeit observability — per-attempt telemetry, the durable attribution ledger, `forfeit-with-engaged-artifact` + the verified salvage valve (#747 via PR #804). Builder-dispatch model tier — opus default in loaded surfaces, owner knob, launcher pin; fable is never a launch default (#755 via PR #805). Recovery doctrine into plugin surfaces — adopt-never-resume, the unpushed-work sweep, transcript pinning (#775 via PR #788). Semantic liveness heartbeat for headless builds (#657 via PR #791). Launch-shape mechanization — the ledger's grammar has one authority (#656 via PR #758). Bite-proof doctrine — every new detector ships a recorded neutralize→red→restore→green proof (#765 via PR #799). Findings delivery channel-keyed at its source, closing the read-only-sandbox forfeit class (#776 via PR #783). The review-diff merge-base resolved outside the repository's git directory (#748 via PR #761). The charters leaned with no rule loss (#801) and the review-code body diet — 508→363 lines, ceiling 515→400 (#646 via PR #802). Hardening: the file_lock crash window (#733 via PR #759), the fail-closed `_repo_root` chokepoint (#742 via PR #760), the worktree guard on destructive discards (#682 via PR #756), the codex fast-exit pin (#746) and hardened liveness probe (#745). Dispatch contracts: the implementer reporting obligation (#750 via PR #757), the cursor order template (#713 via PR #743), the adopted-build review guard (#769 via PR #780), PR-body verbatim preservation (#734 via PR #779), config hygiene B (#752 via PR #778). | (cut on receipts — every PR advisor-vetted with biting reverted probes, vet ordinals 16–32; the qualifying evidence is the wave itself: it ran through two owner-ordered deterministic stops with every lane adopted from artifacts and re-verified independently — the release's own recovery doctrine field-validated by the builds that shipped it) | **cut 2026-08-02** (superheroes-v0.24.0) |


## Areas of focus

The active work organizes into a few **areas of focus**, each carried by a **milestone** — an
issue's milestone is its area, and the milestone's progress is the area's state. This file
names each area and what it is about — nothing finer. If you want to know what's in an area
right now, read its milestone, not this file. A few one-off issues deliberately float with no
milestone; a milestone is a grouping, not a mandate.

- **Review quality** — the review layer: the code-review loop and the doc/spec review leg —
  loop mechanics, panel composition, durable receipts, reviewer-seat reliability, eval growth.
  *Status:* active — tranches cut in 0.17.0 through 0.19.0.
- **Front-half depth** — Architect + Test-Pilot depth: test plans derive from the spec; a
  documented-command surface so CLI/library projects get exercised too. *Status:* queued.
- **Maintainability guardian** — the Guardian hero: read-only repo-health sweeps that turn
  drift into plain-language consequences with receipts. *Status:* **build-complete
  2026-07-22; standing commitment discharged 2026-07-23** — the hero shipped in 0.18.0 (the
  inaugural sweep was the cut's qualifying receipt, catching a real fidelity bug pre-cut —
  cut rule 2 doing its job), then swept a real calibrated project beyond this repo
  (weekly-eats, 2026-07-22: drift mechanics proven on a second same-SHA sweep, five of six
  lenses live, the docs lens caught two real findings on day one), and the owner ruled the
  full-loop leg satisfied by the census-fidelity cycle (sweep finding → issue → build →
  merge). Field-hardening items keep landing in the milestone.
- **Autonomous orchestration** — advisor-orchestrated build batches as a first-class, safe,
  cheap operation: who launches and watches builder sessions, what makes an unattended
  dispatch safe, and how little owner attention a correct batch should cost. *Status:*
  active — opened 2026-07-27; supersedes **Build dispatch & orchestration** now that
  build-dispatch discovery is ratified and its doctrine is landing.
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
