# Verification-strategy adoption plan — superheroes lanes (plugin + project)

**Status:** proposed — awaiting this repo's advisor-seat review on the carrying PR. Issues below are
proposed, **not filed**; filing happens on the owner's word after that review.

**Anchors:** the approved spec beside this file
([spec.md](spec.md), `status: approved`, owner approval 2026-08-28 recorded in its Amendments and
gate); the weekly-eats spec
(`weekly-eats-hq/weekly-eats` → `docs/superheroes/verification-strategy-for-an-ai-first-codebase-ear-f47285/spec.md`,
approved the same sitting); the owner's six adoption rulings (2026-08-27) and acceptance sitting
(2026-08-28), receipts on
[#1105](https://github.com/zwrose/superheroes/issues/1105) and
[weekly-eats-hq/weekly-eats#1109](https://github.com/weekly-eats-hq/weekly-eats/issues/1109).
The weekly-eats lane's plan lives in that repo (same folder as its spec); it cites this file for
every plugin dependency. This file is the canonical home of the plugin work items.

## The six owner rulings this plan encodes

1. **Rails:** the plugin ships the rail *concept* (exempt from delete-because-it-never-fired, never
   exempt from bite-proofing); each project keeps its own classifier.
2. **CI posture:** weekly-eats skips its tooling lane at PR CI (measured ~12-min CI); superheroes
   never reduces CI (~5-min CI; the win is local). Both blessed as deliberate — neither is to be
   "harmonized" toward the other.
3. **Fix-naming:** the plugin ships the unbounded shape (name the merged change, or state the defect
   pre-dates any single change, vet-checked); a 7-day window is only ever a ledger measurement
   heuristic, project-side.
4. **Weekly-eats flake block:** gained its merge exceptions before approval (encoded in its spec).
5. **Machine-written receipts:** a weekly-eats follow-on after its D1, not a spec requirement now.
6. **Framework F1 includes scope-override** — the capability that lets a named binding project rule
   widen review scope (e.g. whole-touched-file), which the base rubric's diff-scope rule otherwise
   forbids calibration from doing.

## Lane 1 — plugin work items (ship to every consumer)

| # | Item | What it is | Size | Needs |
| --- | --- | --- | --- | --- |
| F1 | Binding project rules | A review-calibration section carrying rules reviewers **must** enforce — seat-keyed, severity floors within the existing closed enum, and per-named-rule **scope-override**. The keystone: without it, both projects' review-carried rules (FR-18 families) land as soft focus hints. | small–medium | rulings 1/3/6 (recorded) |
| F2 | Gate-receipt schema | An optional structured receipt (`gate-receipt/1`) a project's `verifyCommand` can emit — run id, source state, lanes run/skipped with reasons, result. Lanes are opaque strings, so both projects' different lane sets fit. | small | — |
| F3 | Vet-checks section | A calibration section enumerating checks the advisor's vet must run and record — the enforcement home for every rule whose evidence lives in the PR body, which review seats structurally cannot read. | small | — |
| PA | Rail concept | The retention exemption + bite-proof obligation, concept only (ruling 1). | small | — |
| PB | Deletion evidence | Any test deletion needs cannot-bite evidence (structural or demonstrated); the shipped test lens has zero deletion rules today. | small | — |
| PC | Flake integrity | Never weaken/skip a flaky test for green; builders cannot self-declare infra. | small | — |
| PD | Fixes name what they fix | The unbounded naming duty with the vet-checked pre-dates arm (ruling 3). | small | — |
| LP | Ledger into the plugin? | **Deferred decision, not a build**: whether the catch/escape ledger becomes a shipped framework — decided only after weekly-eats' ledger shows ~60 days of validated operation (weekly-eats is the named consumer proving the shape). | decision | weekly-eats D2 + ~60 days |

PA–PD land in base surfaces (test-reviewer agent, review-base, bite-proof rubric) and are
independent of F1. F1/F2/F3 are contract-surface work; F1 is the only one touching the calibration
contract's semantics and should get its own small spec round before build.

## Lane 2 — superheroes-as-project (P1–P8, from the approved spec)

| # | Item | Size | Needs |
| --- | --- | --- | --- |
| P1 | One Python pin, drift-guarded (FR-12, UFR-8) | small | — |
| P2 | Catch/escape ledger + flake machinery (FR-19, FR-23–26, UFR-3/6) | small–medium | — |
| P4 | Tripwire censuses (FR-13; gate-command census lands with or after P3) | small | — (census: P3) |
| P3 | Lane classification + observation mode + selection + gate driver (FR-4–11 exc. FR-4b) | medium | P2; adopts F2 |
| P5 | Test-lens calibration: FR-18a–g, FR-4b depth grading, vet checks | small | F1, F3 |
| P6 | Nightly instruments: mutation sweep, flake differential, vitals (FR-20–22) | medium | P1 |
| P7 | First cut list (33 no-raise tests) + 53-rail inventory (FR-3, FR-14) | small | P2 for the standing bar; proceeds during warm-up per the owner's UFR-6 carve-out |
| P8 | Bulk-removal checkpoint (FR-17) | decision | ≥45 complete ledger days |

## Sequencing

- **Wave 1 (parallel, no dependencies):** F1, F2, F3, PA–PD, P1, P2, P4 (the two standalone censuses).
- **Wave 2:** P3 (after P2, emitting F2's receipt from day one), P5 (after F1+F3), P6 (after P1), P7.
- **Calendar-gated:** P8 (≥45 ledger days); LP (weekly-eats D2 + ~60 days).
- Cross-repo: weekly-eats' D1 adopts F2 the same way P3 does, and its policy-copy encoding waits on
  F1+F3 (or encodes twice) — named in its own plan.

## Costs, stated plainly

Plugin items are each small (rubric/agent text + drift tests); F1 is the one contract change and the
only one warranting its own spec. The expensive project build is P3 (the gate driver). P2 and P6 add
a standing nightly compute cost. Nothing here alters what CI runs on a PR (spec constraint).

## What the advisor seat is asked to review

Whether the lane split matches the plugin/project boundary (plugin-level = true for any AI-first
project + enforceable without project facts), whether the dependencies above are right and complete,
whether any proposed item should split or merge, and whether the issue set below is the right
decomposition. Findings land on the carrying PR; the plan is edited in place.

## Proposed issues (filed only on the owner's word, after advisor review)

One issue per row above except LP and P8 (decisions, tracked in the collector when their conditions
near). Each issue carries the three-slot skeleton anchored to the approved spec, its FR references,
its size, its dependency edges from this plan, and — for every test-removing item — its named H4
validation per the spec.
