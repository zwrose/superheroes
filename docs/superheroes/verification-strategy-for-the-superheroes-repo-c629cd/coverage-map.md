# Coverage map — verification-strategy package (spec #1105)

**What this is.** The decomposition's ownership record: every acceptance criterion of
[spec.md](spec.md) owned by **exactly one** child — none unowned, none owned twice — with
consumers listed where a criterion's output is read by other children. Authored by the advisor
(2026-08-28) under the owner's walk-11 ruling 5-a; verified by the package read whose audit trail
sits beside this file. Contracts between children live in [contract-register.md](contract-register.md)
(cited as R-numbers); this file allocates, the register binds.

**Children (Lane 2 — the spec's own package).** From [adoption-plan.md](adoption-plan.md), with the
P3 seam split applied:

| Child | Short name |
| --- | --- |
| P1 | One Python pin, drift-guarded |
| P2 | Catch/escape ledger + flake machinery |
| P3a | Lane classification + guard + named-edit record (the seam child — lands before P3b) |
| P3b | Gate driver: selection, observation emission, receipts |
| P4 | Tripwire censuses |
| P5 | Test-lens calibration + vet checks |
| P6 | Nightly instruments |
| P7 | First cut list + rail inventory |
| P8 | Bulk-removal checkpoint — **decision row, not a build**; owns exactly FR-17 |

Lane-1 items (F1–F3, PA–PD, LP) are **not children of this spec** — its Out-of-scope excludes the
plugin-harvest track; they anchor to the dated adoption rulings and appear here only where a
cross-lane seam touches a criterion (R4).

**Reading the table.** One row per FR/UFR; where a requirement's acceptance bullets split ownership,
the row says so bullet-by-bullet. "Consumers" are readers, never co-owners.

## Functional requirements

| Criterion | Owner | Consumers / notes |
| --- | --- | --- |
| FR-1 — removal only on cannot-bite evidence (all four bullets: shown-to-bite, cannot-bite classes, no-raise-is-suspect, unassessed-retained) | **P7** — the cut list is where the policy first executes; every cut carries its evidence | P5 (FR-18a lens class), P2 (FR-26 exemption reads FR-1's grounds) |
| FR-2 — rail definition | **P3a** — the lane classifier operationalizes "subject is the checked-in tree"; the definition must be mechanical there | P7 (inventory membership must agree with the classifier's rail lane) |
| FR-2 — rails exempt from failure-frequency retention | **P7** — enforced at the inventory (a rail is never cut on has-not-failed) | vet |
| FR-3 — rail inventory seeded from rail-census-v3 (53), advisor corrections additions-only | **P7** | P3a (rail lane = the inventory, R3), P5 (FR-18c), P2 (FR-26 excludes inventoried rails) |
| FR-3 — entry-removal / de-laning bar (evidence + owner approval; de-listing never lighter) | **P7** | vet |
| FR-3 — named-edit machine-checkable record form | **P7** delivers the first shipping form (R2 decides the sentence; serialization decide-by P7) | P3a (classification edits use the same form), P2 (FR-19 protected-artifact edits use it) |
| FR-3 — the guard: inventory entry disappears / rail re-laned without a named edit → red | **P7** owns phase 1 (entry-disappearance arm, lands with or before any cut); **P3a** owns phase 2 (the re-laning arm activates when the lane classification exists — inexpressible before it) | two-phase activation stated in R3 |
| FR-4 — tiers, lanes, always-run set; every file in exactly one lane; classification versioned + guarded; validators-not-a-lane | **P3a** | P3b (selects under it), P2 (records version-in-force per run), P4 (census subject), P5 |
| FR-4b — risk profile + depth grading + named-edit bar on the table | **P5** — rides the FR-18 machinery by the spec's own acceptance | vet (reducing edits need owner approval; the spec is the table's one home) |
| FR-5 — selection semantics for `.py`-only changes | **P3b** | — |
| FR-6 — fail-open to full on any non-`.py` touch (extension-keyed) | **P3b** | — |
| FR-7 — merge tier runs full; nothing reduces CI | **P3b** — verified as a no-change constraint on the gate-driver diff | package read re-checks at verification |
| FR-8 — nightly runs full + instruments, receipt lists each as executed | **P6** | P2 (UFR-3 record shape) |
| FR-9 — machine-written gate receipt with the full field set; unreceipted conditions; receipts travel in the PR body | **P3b** | P2 (FR-23 local arm + corroboration), P5 (UFR-2 vet check), R4 |
| FR-10 — observation mode counted at CI, immutable would-have-skipped sets, 30-clean threshold, reset rule, 30-day decision, owner enablement recorded | **P2** — the ledger computes, records, and counts | P3b (receipt's would-have-skipped field is corroborating only, R5), advisor (brings the decision) |
| FR-11 — false-negative detection + full-until-corrected + replay record + lift authority + second-strike rule | detection, replay record, lift recording → **P2**; the gate's behavior under suspension (runs full, receipt phrase) → **P3b** | R6 carries the flag read |
| FR-12 — one pinned Python, one home, all runners read it; provisioning step; refusal-not-fallback with park route | **P1** | P3b (refusal + interpreter echo), P6 (pinned interpreter), P4 (census reads the gate command), R7 |
| FR-13 ch. 1 (interpreter skew) + ch. 2's dissolution-by-pin | **P1** | — |
| FR-13 ch. 2's census arm (bytecode flags present, retry flags absent) + ch. 3 (git identity) + ch. 4 (engine binaries) + the each-channel-has-a-named-handler traceability bullet | **P4** — the census home; gate-command census lands with or after P3b (R8) | — |
| FR-13 ch. 5 (real entry point exercised) + ch. 6 (stripped-file list read) — the two practice rules with named vet-graded fields | **P5** | vet; P2 (no-vet-lane fallback) |
| FR-14 — proactive deletion with independently re-run evidence; the P7 cut list | evidence bar + re-run rule encoding → **P5** (UFR-5's check); the cut list itself → **P7** | — |
| FR-15 / FR-16 — burndown-when-touched, mechanical-only exemption, freeze suspension | **P5** — FR-18f is the enforcement; whole-touched-file check rides the advisor's vet until F1 (encode-twice, R11 note) | vet |
| FR-17 — bulk-removal checkpoint, decision-only, ≥45 ledger days | **P8** (decision row) | P2 (complete-ledger-day count) |
| FR-18a–f — the six authoring rules with named example findings | **P5** | — |
| FR-18g — stage rule + detector bite-proofing + rule-set versioning + drift check | **P5** | P2 (nightly reads receipt's rule-set version, UFR-7 fallback), R11 |
| FR-19 — the ledger: eight classes first-match, per (run × item), overrides, protected artifacts + replay, dispatch audit, unlinked fixes, H4 | **P2** | R10, R12, R13; P5 (FR-18d shares the escape-candidate reference, R10) |
| FR-20 — mutation sweep (budgeted, advisory, partial-marked) | **P6** | P1 (pinned interpreter) |
| FR-21 — flake differential | the nightly run + published differential → **P6**; candidate lifecycle in the ledger (recorded-at, disposition, overdue escalation, no-double-count) → **P2** | advisor (confirmation dispatch) |
| FR-22 — vitals trend nightly | **P6** | — |
| FR-23 — flake listed at the moment seen, all four observation paths; recorder never the builder | **P2** | P3b (receipt attempt/prior-red fields are the local eyes, R4/R9), P5 (vet reading) |
| FR-24 — recorded flake blocks; two exceptions; dispositions; enforcement points + merge-time re-check records + nightly cross-check + violation detector; no quarantine/retry | ledger records, exception audit, violation detection, identity cross-check → **P2**; the vet-check encoding (vet-time listing read, exception-scope check, vetted-lane requirement) → **P5** | R9 |
| FR-24b — blocking flake is the advisor's next dispatch; precedence order | **P2** — the ledger shows recorded-at, fix owner, and the no-other-dispatch audit | advisor process |
| FR-25 — 0.5% trailing-30-day tripwire, population rule | **P2** | advisor |
| FR-26 — one-working-day escalation, removal offer bounds, coverage obligation + restore-by, evidence in re-runnable form | **P2** | P7/rail exclusion via R3 |

## Unhappy paths

| Criterion | Owner | Consumers / notes |
| --- | --- | --- |
| UFR-1 — unclassifiable → full, receipt phrase | **P3b** | P3a (classification is the input) |
| UFR-2 — receiptless local-gate claim = no receipt (post-P3b); today's-practice bar before then | vet-check encoding → **P5**; nightly no-vet-lane fallback → **P2** | — |
| UFR-3 — instrument failure recorded + owner notified by next working day; ledger refresh isolated; three stale ledger nights → local full | failure record + notification → **P6**; refresh isolation → **P2**; the gate's stale-instruments behavior + phrase → **P3b** | R6, R14 |
| UFR-4 — weakening/skipping a listed flake → finding + block | lens+vet encoding → **P5**; nightly fallback + block record → **P2** | — |
| UFR-5 — unevidenced deletion / rail de-listing → finding, no lane without a vet, independent re-run | **P5** (encoding; the vet performs the re-run) | P7 (its PRs are the primary subject) |
| UFR-6 — escape-rate freeze, insufficient-sample park, P7 warm-up carve-out, merge-time re-check | rate computation, sample floor, provisional-window exclusion → **P2**; vet-park encoding → **P5** | P7 (carve-out consumer), P8 |
| UFR-7 — no test-lens receipt / stale rule-set version → unreviewed; run-identifier resolution; nightly fallback | vet encoding → **P5**; nightly resolution → **P2** | R11 |
| UFR-8 — CI validator-step drift check before any test | **P1** | — |
| UFR-9 — trust state unreadable → full, naming which | **P3b** | R6 |

## Non-functional requirements, risk profile, presentation

| Criterion | Owner | Notes |
| --- | --- | --- |
| NFR local-loop <2 min median (trailing 20 receipts) | **P3b** delivers the bar | P2 measures from handed-back receipts |
| NFR nothing degrades invisibly | **P3b** — the receipt is the surface every skip/fail-open/suspension/staleness line reaches | instrument staleness lines fed by P2/P6 (R6); graded again at every child vet (standing NFR row) |
| NFR escape rate not raised | **P2** | UFR-6 is the mechanism |
| NFR reproducibility (interpreter + classification version named) | **P3b** | P1, P3a inputs |
| Risk profile (normative table + deepest-row rule) | **P5** (grading); the spec stays the table's one home | — |
| Coverage-table Show-it rows | the child producing each shown surface: first receipt → **P3b**; threshold breaches (FR-10/FR-17/FR-25) + suspension → **P2**; stale-instrument receipt → **P3b**; receipt wording (fixed phrases) → **P3b** | each lands as a show-it DoD bullet in that child's issue (R16) |

## Unallocated criteria

None. Every FR/UFR row above names one owner; the two deliberately split rows (FR-11, FR-13,
FR-14, FR-21, FR-24, UFR-2/3/4/6/7) split at the bullet level with each bullet singly owned.
The package read's verification pass re-checks this claim in both directions.
