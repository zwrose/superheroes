<!-- covers: E1, E2, E3, E4, E5, E6, E7, E8, E9, E10, E11 -->

#### E1 — Issue contract checker (three-slot skeleton, anchor, DoD bar)

- **Component.** The advisory build-ready anchor-shape checker (`lib/issue_contract.py`) and
  its reference spine (`issue-contract.md`); it costs charter maintenance and an extra read at
  filing and vet time.
- **Condition.** Citation-based, 45 days: vet, forfeit-dispute, or incident receipts that cite
  the issue-contract anchor-shape rule — advisory, always exit 0, so zero catches are not evidence
  the shape class is gone. On firing, a proposal to the owner at a gardening pass.
- **Last demonstrated benefit.** Shipped deterministic anchor-kind checking for build-ready
  marking (#932).
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** structural — guards routed-issue body shape; no host offers build-ready marking-time
  validation.

#### E2 — register_check (epic contract quotes)

- **Component.** The register-to-child byte-exact quote guard (`lib/register_check.py`); it costs
  maintenance on the closed register grammar and runs at every child filing and package-read
  verification.
- **Condition.** Catch-based, 45 days: real catches of register-quote text drift, missing quotes,
  or unknown-entry at charter filing or package-read verification. On firing, a proposal to the
  owner at a gardening pass.
- **Last demonstrated benefit.** Caught register parsing that would have blocked every child
  filing in the verification-strategy package read (#1227).
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** structural — guards byte-exact register agreement; no platform primitive compares
  quoted issue blocks to repo files.

#### E3 — package_read_audit

- **Component.** The FR-32 machine-record trail convention and the completeness-and-shape checker
  (`lib/package_read_audit.py`); CP2 splits the row — the trail convention keeps, the checker
  retires on a real trail-integrity incident — and the checker costs ~2,815 LOC against a
  circular trust chain.
- **Condition.** Usage-based, 60 days: spec-package reads that write machine-record blocks per
  the trail convention — scoped to the keeping member. On firing, a shrink proposal to the owner
  at a gardening pass (not a row deletion).
- **Last demonstrated benefit.** Verification-strategy package read produced conforming machine
  records and a checked trail (#1227/ca515aa6).
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** mixed — trail convention is structural; checker is harness-limit (advisor writes,
  advisor runs check, owner reads conforming in a title per CP2 sitting).

#### E4 — Citation/exact-text validators

- **Component.** The dangling-citation detector (`lib/citation_validator.py` and its exact-text
  checker script); it is cheap, wired in review-spec compile, and guards the #205
  fabricated-fact class with zero live catches recorded.
- **Condition.** Citation-based, 45 days: vet, forfeit-dispute, or incident receipts that cite
  the citation-validator rule's substance — zero catches mean the class may still be live, not
  that the detector is idle. On firing, a proposal to the owner at a gardening pass.
- **Last demonstrated benefit.** Made dangling spec citations mechanically catchable in
  review-spec compile (#517).
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** structural — guards spec provenance existence; no platform doc-citation validator
  exists.

#### E5 — Collector + revisit-trigger registry

- **Component.** The Tier-2 collector on issue #695 and the revisit-trigger registry pinned
  there, plus the append-always and registry rules in `owner-decisions.md`; it costs pinned-comment
  hygiene and unconditional vet-time appends.
- **Condition.** Usage-based, 60 days: Tier-2 residuals appended to the collector and
  revisit-registry rows written at vet time per the owner-decisions delivery contract. On firing,
  a proposal to the owner at a gardening pass.
- **Last demonstrated benefit.** Append-always closed the empty-collector over-filtering failure
  (owner-decisions.md, issue #695).
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** structural — complete register by construction; no mechanical gate on chat delivery.

#### E6 — Vet spine + vet-receipt contract

- **Component.** The vet-receipt shape and showrunner vet duty (`vet-receipt.md`, showrunner duty
  4); CP2 queued a simplify to trim confirmatory probe mass that drifts from the contract.
- **Condition.** Usage-based, 60 days: child PR vets that post a spine-complete vet receipt per
  `vet-receipt.md` — distinct probes, not re-run green suites. On firing, a proposal to the owner
  at a gardening pass.
- **Last demonstrated benefit.** Explicit `None` made vet absences readable instead of
  presence-by-grep (`vet-receipt.md`).
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** mixed — spine shape is structural; confirmatory probe drift is capability-gap (71%
  confirmatory mass per CP2, contract already forbids it at line 42).

#### E7 — Owner-decisions walk contract

- **Component.** The open-decisions delivery contract (`owner-decisions.md`) and the
  `/superheroes:discuss-open-decisions` skill; it costs loaded prose on every owner walk and
  enforces the per-item spine the owner corrected into existence.
- **Condition.** Usage-based, 60 days: open-decision deliveries that follow the per-item spine,
  worth-it gate, and venue ladder in `owner-decisions.md`. On firing, a proposal to the owner at
  a gardening pass.
- **Last demonstrated benefit.** Unified residual-triage vocabulary ended inconsistent
  disposition across advisor sessions (#1118).
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** structural — owner-present delivery shape; nothing mechanical gates a chat message.

#### E8 — Worth-it gate + venue ladder

- **Component.** The residual-triage prose in `owner-decisions.md` §worth-it gate and venue
  ladder; CP2 kill K6 records it superseded by the package-landing front door — real catches,
  zero LOC, registry rows inherit at ratification rather than retiring on absence evidence.
- **Condition.** Usage-based, 60 days: residual dispositions that cite the worth-it gate and venue
  ladder vocabulary until the front door ratifies and inherits the registry rows. On firing, a
  proposal to the owner at a gardening pass.
- **Last demonstrated benefit.** Unified residual triage across review, vet, and owner-decision
  surfaces (#1118).
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** structural — triage vocabulary promoted to the front door at Part B landing, not
  retired on zero catches.

#### E9 — Bite-proof doctrine + probe discipline

- **Component.** The bite-proof rule (`rubric/bite-proof.md`) and its probe-discipline records;
  it costs neutralize-red-restore-green work on every new or changed detector.
- **Condition.** Usage-based, 60 days: new or changed detectors shipped with a recorded
  bite-proof per `rubric/bite-proof.md`. On firing, a proposal to the owner at a gardening pass.
- **Last demonstrated benefit.** Red-run requirement distinguished verified detectors from
  green-only claims (bite-proof.md, PR #1159 vet 181).
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** structural — covenant fourth promise (receipts before claims) applied to detectors.

#### E10 — Charters + covenant + launch/dispatch doctrine (loaded prose mass)

- **Component.** The loaded charter and doctrine prose mass (showrunner, workhorse, detective
  SKILL.md files, covenant, launch-doctrine, dispatch-mechanics, review-discipline); CP2 queued a
  third diet pass against a 3,826-line baseline — context load on every dispatched session.
- **Condition.** Usage-based, 60 days: build, review, and advisor sessions that load the charter
  and doctrine prose. On firing, a proposal to the owner at a gardening pass.
- **Last demonstrated benefit.** unknown.
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** mixed — covenant hard lines are structural; charter mass size is capability-gap
  (Change 6 meter baseline, 3,826 loaded lines per CP2).

#### E11 — Orders templates (shipped data)

- **Component.** The orders substrate row — `rubric/orders/` templates and `round_orders`
  renderers; this row is substrate, so a proposal is a shrink or split, not a deletion; it costs
  template and placeholder-contract maintenance on every certified round.
- **Condition.** Usage-based, 60 days: certified review rounds that render seat orders through
  `round_orders` from `rubric/orders/` templates. On firing, a shrink proposal to the owner at a
  gardening pass.
- **Last demonstrated benefit.** Shipped per-seat order rendering from templates with
  refuse-on-unfilled-placeholder (#723).
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** structural — load-bearing dispatch text substrate wired through `round_driver`.
