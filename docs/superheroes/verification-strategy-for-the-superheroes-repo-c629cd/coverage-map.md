# Coverage map — verification-strategy package (spec #1105)

**What this is.** The decomposition's ownership record: every acceptance criterion of
[spec.md](spec.md) owned by **exactly one** child — none unowned, none owned twice — with
consumers listed where a criterion's output is read by other children. Authored by the advisor
(2026-08-28) under the owner's walk-11 ruling 5-a; revised after package-read round 1 (45 findings
across five non-Anthropic lenses — see [package-read.md](package-read.md)); verified by the read's
verification pass. Contracts between children live in
[contract-register.md](contract-register.md) (cited as R-numbers); this file allocates, the
register binds.

**Children (Lane 2 — the spec's own package).** From [adoption-plan.md](adoption-plan.md), with the
P3 seam split applied:

| Child | Short name |
| --- | --- |
| P1 | One Python pin, drift-guarded |
| P2 | Catch/escape ledger + flake machinery + the nightly no-vet-lane fallback checks |
| P3a | Lane classification + guard + named-edit conformance (the seam child — lands before P3b) |
| P3b | Gate driver: selection, observation emission, receipts, the nightly full-run tier |
| P4 | Tripwire censuses |
| P5 | Test-lens calibration + vet-checks encoding |
| P6 | Nightly instruments (mutation sweep, flake differential, vitals) |
| P7 | First cut list + rail inventory (the named-edit record's first shipping home) |
| P8 | Bulk-removal checkpoint — **decision row, not a build**; owns exactly FR-17, including its Show-it named item |

Lane-1 items (F1–F3, PA–PD, LP) are **not children of this spec** — its Out-of-scope excludes the
plugin-harvest track; they anchor to the dated adoption rulings and appear here where a cross-lane
seam touches a criterion (R4, R11).

**Reading the table.** One row per FR/UFR; where a requirement's acceptance bullets split ownership,
the row says so bullet-by-bullet. "Consumers" are readers, never co-owners — **a spec bullet that
requires a child to build or check something is owned by that child**, never listed as consumption
(package-read round 1's largest defect class was exactly that conflation, now repaired).

## Functional requirements

| Criterion | Owner | Consumers / notes |
| --- | --- | --- |
| FR-1 — removal only on cannot-bite evidence (all four bullets) | **P7** — the cut list is where the policy first executes; every cut carries its evidence | P5 (FR-18a classes; UFR-5 re-run encoding). **FR-26 removals are FR-1's stated exception, not a consumer** — owner-authorized coverage obligations on diagnosis evidence, outside the cannot-bite bar (R17 carve-out). Shared vocabulary bound as R17 |
| FR-2 — rail definition: **recognition** (the lens flags an undeclared or uninventoried rail by what it tests — FR-18c's arm; the definition itself is spec-resident vocabulary, since a rail *absent from* the inventory must still be recognizable) | **P5** | corrected rounds 1–3: recognition, membership, and lane-derivation are three singly-owned rows |
| FR-2 — rail definition: **membership** (the inventory, seeded from `rail-census-v3`, is the operational rail set) | **P7** | R3 |
| FR-2 — rail definition: **lane derivation** (rail lane = the inventory) | **P3a** | R3 |
| FR-2 — rails exempt from failure-frequency retention | **P7** | vet |
| FR-3 — inventory seeded (53), advisor corrections cover additions and entry metadata only — never a removal or re-laning | **P7** | P3a (R3), P5 (FR-18c lens arm), P2 (FR-26 rail exclusion) |
| FR-3 — entry-removal / de-laning bar | **P7** | vet |
| FR-3 — named-edit machine-checkable record form | **P7** carries the form's first shipping home; the form itself is **decided in R2** (no open decide-by) | P3a, P2, P5, P6 — every named-edit surface (R2) |
| FR-3 — the PR-body naming duty (a PR editing the inventory or classification names the edit and reason in its body) | **P7** for inventory-editing PRs; **P3a** for classification-editing PRs — each child's guard documentation states it | vet reads the body; the committed record (R2) is the mechanical half |
| FR-3 — the guard, two-phase | **P7** owns phase 1 (entry-disappearance arm, lands with or before any cut); **P3a** owns phase 2 (the re-laning arm — inexpressible before the lane classification exists) | R3 |
| FR-4 — lanes and classification: every file in exactly one lane; classification versioned + guarded; the rail lane is the always-run set's definition | **P3a** | P3b, P2 (records version-in-force), P5 (R1) |
| FR-4 — tier execution: the always-run set and the four validators actually run on every Local-tier invocation (validators-not-a-lane) | **P3b** — execution is the gate's, not the classifier's (round-3 correction) | R1 |
| FR-4b — risk profile + depth grading + named-edit bar on the table | **P5** | vet; table edits use R2's form (P5 is an R2 consumer) |
| FR-5 — selection semantics for `.py`-only changes, **operative only after FR-10's enablement flip** | **P3b** — including the duty to read the enablement state and skip nothing unless a recorded enablement is read **true** (an absent or unreadable record is not-enabled — R6) | P2 records the flip |
| FR-6 — fail-open to full on any non-`.py` touch | **P3b** | — |
| FR-7 — merge tier runs full; nothing reduces CI | **P3b** — verified as a no-change constraint on the gate-driver diff | package read re-checks at verification |
| FR-8 — nightly tier runs every lane in full; the receipt lists every lane and instrument as executed | **P3b** — the spec's own change-set row places FR-8 in P3 (the tier runner is the gate driver's nightly mode); **P6 extends the same nightly with the instruments** and is a consumer of its receipt structure | corrected from round-1 finding grounding-006 — the map's first draft assigned P6 against the spec's delivery table without saying why |
| FR-9 — machine-written gate receipt, field set, unreceipted conditions | **P3b** | P5 (UFR-2 vet check), R4 |
| FR-9 — receipts travel in the PR body; **the ledger reads handed-back receipts at its nightly refresh** | first half **P3b** (the receipt lands in the body at handback); ingestion half **P2** — a build, not a read | corrected: round-1 ALLOCATION-002 |
| FR-10 — observation mode counted at CI; immutable would-have-skipped sets; thresholds, reset, 30-day decision; **owner enablement recorded in the ledger** | **P2** | **P3b consumes the enablement state through R6** and must not skip before it (its own FR-5 bullet above); advisor brings the decisions |
| FR-11 — false-negative detection (ledger set **or** the change's handed-back receipt), replay record, lift authority, second-strike | **P2** | R5, R6 |
| FR-11 — the gate's behavior under suspension (runs full; the pinned phrase; **the suspended receipt is the Show-it surface**), and after a lift, **the receipt cites the lifting record** | **P3b** | R15, R16; P2 records the lift (previous row) |
| FR-12 — one pinned Python; provisioning; the pin home and drift validator | **P1** | P3b, P6, P4, R7 |
| FR-12 — the gate's two refusal arms: refuse to run when the out-of-repo calibration home disagrees with the pin, and refuse (never fall back) when the pinned interpreter cannot be provisioned — with the park route | **P3b** — bound in R7 (round-3 addition) | P1's pin is the input |
| FR-13 ch. 1 + ch. 2's dissolution-by-pin | **P1** | — |
| FR-13 ch. 2 — **the gate command carries the bytecode-safety flags** (the production half) | **P3b** — R8's producer duty | P4's census is the check, not the flags |
| FR-13 ch. 2's census arm + ch. 3 + ch. 4 + the traceability bullet | **P4** | R8 |
| FR-13 ch. 5–6 — the two practice rules and their named vet-graded fields | **P5** | vet |
| FR-13 ch. 5–6 — **the no-vet-lane presence check at the nightly refresh** ("either channel's named field absent … the ledger's nightly refresh performs the presence check") | **P2** — a build | corrected: round-1 ALLOCATION-003 |
| FR-14 — deletion-evidence bar + independent re-run encoding | **P5** (UFR-5's check); the cut list itself → **P7** | R17 |
| FR-15 / FR-16 — burndown-when-touched, mechanical exemption, freeze suspension | **P5** (FR-18f; whole-file check vet-carried until F1 — R11) | vet |
| FR-17 — bulk-removal checkpoint, decision-only, ≥45 ledger days, **its Show-it named item ("first line states the number of complete ledger days")** | **P8** | P2 (day count); R16 carries P8's presentation duty |
| FR-18a–f — the six authoring rules (a–d and f name an example finding; **e is a prohibition and names the finding it bars**) | **P5** | — |
| FR-18c — **the no-vet-lane body check at the nightly refresh** | **P2** — a build | corrected: round-1 ALLOCATION-004 |
| FR-18g — the calibration-side integrity rules: stage rule, rule-set versioning + drift check, the lens rules' named example findings | **P5** | P2 (nightly reads the version, UFR-7 fallback), R11 |
| FR-18g — **detector bite-proof specimens**: every guard, census, drift test, and the classifier this policy introduces carries its seeded-violation specimen **in the build that ships the detector** | each detector's owner — **P3a** (classification guard), **P1** (pin drift check), **P4** (censuses), **P2** (classifier, per class and per disjunction branch), **P7** (inventory guard), **P5** (its own rule-set drift check — itself a detector) | bound as R20; corrected rounds 2 and 4 — no child's specimen stands in for another's |
| FR-19 — the ledger core: classes, per (run × item), overrides, dispatch audit, unlinked fixes, H4 | **P2** | R10, R12, R13 |
| FR-19 — protected-artifact edits: **the vet-check encoding** (replay record checked at a vetted lane) | **P5**; the artifacts, replay records, and nightly re-check → **P2** | corrected: round-1 ALLOCATION-005; R12 |
| FR-20 — mutation sweep (budgeted via an R2 named edit, advisory, partial-marked) | **P6** | P1; P6 is an R2 consumer |
| FR-21 — the nightly differential run and its published differing-set | **P6** | **R18 binds the published set as P2's candidate-ingest feed** |
| FR-21 — candidate lifecycle in the ledger (recorded-at, dispositions, overdue escalation, no-double-count) | **P2** | advisor (confirmation dispatch) |
| FR-22 — vitals trend nightly | **P6** | — |
| FR-23 — flake listed at the moment seen (instrument paths) | **P2** | R4/R9 |
| FR-23 — **the vet-as-recorder encoding** (the vet reading receipts and runs is a recorder; never the builder) | **P5** — the vet-checks section is where that duty is encoded | corrected: round-1 ALLOCATION-006 |
| FR-24 — ledger records, exception audit, violation detection, identity cross-check, merge-time re-check records | **P2** | R9 |
| FR-24 — the vet-check encoding (listing read, exception-scope check, vetted-lane requirement) | **P5** | R9's interim: the advisor's vet performs the read directly from the spec until P5's encoding lands |
| FR-24 — "no quarantine lane and no retry-on-failure setting at any tier": **the retry-flag census arm** | **P4** (the same census as FR-13's closing bullet, R8); the policy prose and finding on weakening → P5 | corrected: round-1 ALLOCATION-007 |
| FR-24b — advisor-next-dispatch audit trail + precedence | **P2** | advisor process |
| FR-25 — 0.5% tripwire, population rule | **P2** | advisor |
| FR-26 — escalation, removal bounds, coverage obligation, re-runnable evidence | **P2** | R3 (rail exclusion) |

## Unhappy paths

| Criterion | Owner | Consumers / notes |
| --- | --- | --- |
| UFR-1 — unclassifiable → full, phrase | **P3b** | P3a input |
| UFR-2 — receiptless claim = no receipt; vet-check encoding → **P5**; nightly fallback → **P2** | split as stated | — |
| UFR-3 — **instrument-failure recording + owner notification** (the tracking item carries the dated record and the sent notification) | **P2** — the plan's own row places UFR-3 in P2; the ledger's tracking item is the recording surface | corrected round 1 (was P6) |
| UFR-3 — **failure emission**: each nightly participant must surface its own failure or partial completion into P2's record | **P6** for the instruments; **P3b** for the nightly tier runner itself | corrected round 2 (both vendors) — emission is an owned build in each participant, never consumption |
| UFR-3 — ledger-refresh isolation from sweeps; three-stale-nights rule | **P2** (isolation contract R14 with P6); the gate's stale-instruments behavior + phrase → **P3b** | R6, R14 |
| UFR-4 — lens+vet encoding → **P5**; nightly fallback + block record → **P2** | split as stated | — |
| UFR-5 — finding + no-vet-lane bar + independent re-run | **P5** (encoding; the vet performs the re-run) | P7 (primary subject), R17 |
| UFR-6 — rate, sample floor, provisional-window exclusion, **and the merge-time re-check's ledger cross-check** | **P2** | R19 binds the freeze mechanics |
| UFR-6 — the vet-park encoding | **P5** | R19 |
| UFR-6 — the P7 warm-up carve-out (cannot-bite deletions proceed during warm-up on the owner's 2026-08-28 ruling) | **P7** — its issue states the carve-out and its bound | R19 |
| UFR-7 — vet encoding → **P5**; nightly resolution → **P2** | split as stated | R11 |
| UFR-8 — CI validator-step drift check | **P1** | — |
| UFR-9 — trust state unreadable → full, naming which — the spec's **three** named states (suspension, staleness, calibration home), exactly as UFR-9 enumerates them | **P3b** | R6. The enablement state is deliberately **not** a UFR-9 state: an unreadable enablement record resolves through FR-5/FR-10 (selection simply stays off), not through UFR-9's phrase — corrected round 2 |

## Non-functional requirements, risk profile, presentation

| Criterion | Owner | Notes |
| --- | --- | --- |
| NFR local-loop <2 min median | **P3b** delivers the bar; **the measurement is the ledger's** (trailing-20 median over handed-back `.py`-only receipts, published with R13's numbers, computable only after FR-10 enablement) — P3b's PR is graded on the mechanism (selection works, receipts carry wall time), never on a median no single PR can carry | corrected: round-1 gradability-009 |
| NFR nothing degrades invisibly | **P3b** (the receipt surface) | instrument lines fed by P2 (R6); re-graded at every child vet |
| NFR escape rate not raised | **P2** | UFR-6/R19 |
| NFR reproducibility | **P3b** | P1, P3a inputs |
| Risk profile (normative table + deepest-row rule) | **P5** (grading); the spec stays the table's home; table edits = R2 named edits | — |
| Coverage-table Show-it rows | **each owning child carries its own Show-it as a DoD bullet (R16)**: first receipt, the suspended receipt, the stale-instruments receipt, and the fixed phrases → **P3b**; the FR-10 threshold record and FR-25 breach delivery → **P2**; **the FR-17 checkpoint's named item → P8**; wording row (the six phrases) → **P3b** (R15) | corrected: round-1 findings ALLOCATION-009, grounding-005/007, premortem-007, gradability-005/006, register-011 |

## Unallocated criteria

None, after the round-1 repair pass: 45 round-1 findings dispositioned (see
[package-read.md](package-read.md)) — the systematic repairs were (1) P2's nightly no-vet-lane
fallback duties converted from consumer-reads to owned bullets; (2) Show-it surfaces reassigned to
their producing children including P8; (3) FR-8 and UFR-3 realigned to the spec's and plan's own
delivery rows; (4) the FR-10 enablement seam split and bound in R6; (5) the FR-2 definition made
spec-resident vocabulary with three singly-owned arms. Round 2 (both vendors, 22 findings, one
refuted) drove the further repairs annotated "corrected round 2" above and in the register.
The read's verification pass re-checks this claim in both directions.
