# Verification-strategy adoption plan — superheroes lanes (plugin + project)

**Status:** advisor-reviewed and owner-ruled (2026-08-28, walk-11): the advisor's five findings and
the weekly-eats consumer read were folded into this text (review record on the carrying PR), and the
owner ruled the P-lane gets the full epic decomposition machinery (coverage map + contract register
+ light-weight non-Anthropic package read). **Amended 2026-10-02** with the spec's amendment #5
(the owner's rulings "8 a"–"11 a", record:
https://github.com/zwrose/superheroes/issues/695#issuecomment-5951960566): the "new verification
strategy" milestone is retired; the surviving items sit in **Backlog as machinery under the dial**;
the waves below are dependency order, not a milestone schedule. The issues are filed
(#1228–#1242) and their dispositions are in the coverage map's
[child-disposition table](coverage-map.md#child-dispositions-2026-10-02).

**Anchors:** the approved spec beside this file
([spec.md](spec.md), `status: approved`, owner approval 2026-08-28 recorded in its Amendments and
gate, amended 2026-10-02); the weekly-eats spec
(`weekly-eats-hq/weekly-eats` → `docs/superheroes/verification-strategy-for-an-ai-first-codebase-ear-f47285/spec.md`,
approved the same sitting); the owner's six adoption rulings (2026-08-27) and acceptance sitting
(2026-08-28), receipts on
[#1105](https://github.com/zwrose/superheroes/issues/1105) and
[weekly-eats-hq/weekly-eats#1109](https://github.com/weekly-eats-hq/weekly-eats/issues/1109); and
the 2026-10-02 ruling record on
[#695](https://github.com/zwrose/superheroes/issues/695#issuecomment-5951960566).
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

Since 2026-10-02: ruling 5's machine-written receipts stay held with the gate driver (the receipt fields are hand-written, spec FR-9), and F1 (ruling 6) is parked under the owner's review hold.

## Lane 1 — plugin work items (ship to every consumer)

| # | Item | What it is | Size | Needs | Status (2026-10-02) |
| --- | --- | --- | --- | --- | --- |
| F1 | Binding project rules | A review-calibration section carrying rules reviewers **must** enforce — seat-keyed, severity floors within the existing closed enum, and per-named-rule **scope-override**. The keystone: without it, both projects' review-carried rules (FR-18 families) land as soft focus hints. | small–medium | rulings 1/3/6 (recorded) | parked (review hold) |
| F2 | Gate-receipt schema | An optional structured receipt (`gate-receipt/1`) a project's `verifyCommand` can emit — run id, source state, lanes run/skipped with reasons, result, **plus attempt history, wall time, and machine/runner identity** (required by weekly-eats D1's FR-11/FR-24a ten-field receipt and read by its D2 ledger; this repo's FR-9 receipt carries the same data — named optional fields). Lanes are opaque strings, so both projects' different lane sets fit. | small | — | shipped (#1237, PR #1551); `gate-receipt/1` is optional |
| F3 | Vet-checks section | A calibration section enumerating checks the advisor's vet must run and record — the enforcement home for every rule whose evidence lives in the PR body, which review seats structurally cannot read. | small | — | shipped (#1238) |
| PA | Rail concept | The retention exemption + bite-proof obligation, concept only (ruling 1). | small | — | parked (review hold) |
| PB | Deletion evidence | A deletion on the cannot-bite basis carries its evidence (structural or demonstrated); FR-1's other bases — obsolete expectation under a stamped keep list, retired subject, owner-authorized flake removal — carry their own bars; the shipped test lens has no deletion rule today. | small | — | parked (review hold) |
| PC | Flake integrity | Never weaken/skip a flaky test for green. | small | — | parked (review hold) |
| PD | Fixes name what they fix | The unbounded naming duty with the vet-checked pre-dates arm (ruling 3). | small | — | parked (review hold) |
| LP | Ledger into the plugin? | **Deferred decision, not a build**: whether the catch/escape ledger becomes a shipped framework — decided only after weekly-eats' ledger shows ~60 days of validated operation (weekly-eats is the named consumer proving the shape). | decision | weekly-eats D2 + ~60 days | withdrawn — the ledger it would have moved into the plugin is declined (Spec A FR-F6 change 1) |

PA–PD are parked under the owner's review hold; they land in base surfaces (test-reviewer agent,
review-base, bite-proof rubric) and are independent of F1 when they unpark. F1 is parked under the
same hold; it is the only Lane-1 item touching the calibration contract's semantics and gets its
own small spec round before build. F2 and F3 shipped.

## Lane 2 — superheroes-as-project (P1–P9, from the approved spec)

| # | Item | Size | Needs | Status (2026-10-02) |
| --- | --- | --- | --- | --- |
| P1 | One Python pin, drift-guarded (FR-12, UFR-8) | small | — | shipped (#1228) |
| P2 | Catch/escape ledger + flake machinery (FR-19, FR-23–26, UFR-3/6) | — | — | closed (declined, #1229) |
| P3 | Lane classification + observation mode + selection + gate driver (P3a #1230, P3b #1231) | — | — | closed (held on the registry) |
| P4 | Tripwire censuses (FR-13) | — | — | closed (declined, #1232) |
| P5 | Test-lens calibration (FR-18a–g, FR-4b depth grading) and vet checks | small | F3 (shipped) | rewritten (#1233): the vet-checks slice live; the test-lens slice parked (review hold) |
| P6 | Nightly instruments: mutation sweep, flake differential, vitals | — | — | closed (declined, #1234); the mutation run moves to P9 |
| P7 | First cut list (32 no-raise tests per the ruling's count, the one golden-fixture file), the plain rail inventory (FR-3), and the keep-list seed for the owner's stamp (FR-1, FR-14) | small | — | rewritten (#1235): the inventory guard and named-edit record are gone |
| P8 | Bulk-removal checkpoint (FR-17) | — | — | withdrawn (bulk removal is an owner decision on hand counts) |
| P9 (new, unfiled) | On-demand instruments — the mutation run (FR-20) and the red-then-green script | small–medium | P1 (shipped) | filed on the owner's word |

## Sequencing

- **Now:** P7 (its keep-list seed goes to the owner's stamp, which activates delete-on-contact; its
  cut list and plain inventory) and P5's vet-checks slice (F3 shipped; no dependency).
- **On the owner's word:** P9 (P1 shipped).
- **Parked under the review hold:** P5's test-lens slice, F1, PA–PD — until the review overhaul
  takes shape.
- Cross-repo: weekly-eats adopts `gate-receipt/1` at its own pace (optional; nothing here waits on it).
- Board note: survivors in Backlog as machinery under the dial; ROADMAP drops the milestone row in
  its own PR.

## Costs, stated plainly

No nightly compute and no gate driver; the mutation run is budgeted and on demand; the rest is
rubric and vet-check text plus P7's cuts. Nothing here alters what CI runs on a PR (spec constraint).

## Propagation

The advisor carries this amendment to the child bodies after merge (amendments.md § Propagation:
the amended artifact first, children after); closing, rewriting and parking the issues is the
advisor's, not this file's.

## Issues

Filed 2026-08-28 as #1228–#1242; their 2026-10-02 dispositions are the coverage map's
[child-disposition table](coverage-map.md#child-dispositions-2026-10-02); the new P9 is filed on the
owner's word into Backlog. **Anchors by lane** (history): Lane-2 issues anchor to the approved
spec's sections; Lane-1 issues anchor to the six dated owner adoption rulings, never to this
repo's spec, whose Out-of-scope excludes the plugin-harvest track.
