<!-- covers: F1, F2, F3, G1, G2, G3, G4, H1, H2, H3, H4 -->

#### F1 — Configure + calibration + modes

- **Component.** The configure-hero embedded machinery (not the skill front door): the configure
  skill, calibration routing, mode registry, and session-mode resolution across a dozen lib
  modules. It costs vocabulary maintenance every time mode semantics shift.
- **Condition.** Usage-based, 60 days: owner-invoked configure or calibration-fix runs whose
  reconcile signals still reference pre-#1151 mode vocabulary outside the single-owner pattern. On
  firing, a shrink proposal to the owner at a gardening pass.
- **Last demonstrated benefit.** Routed incomplete calibrations to fix and healthy-but-drifted
  projects to view via configure_route state sense (#1151).
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** mixed — session-mode SSOT (#1151) is structural; duplicated vocabulary across modules
  is capability-gap until consolidation lands.

#### F2 — Model governance (tiers, registry, overrides)

- **Component.** Model governance: the tier registry, override resolution, and skill-facing
  resolver. It costs table maintenance whenever a dispatch role or host model set changes.
- **Condition.** Citation-based, 45 days: vet, forfeit-dispute, or incident receipts citing a
  model-tier misresolution (wrong band, stale override, fail-open masking a safety tier). On
  firing, a proposal to the owner at a gardening pass; zero citations means the guard is working,
  not that tiers are unnecessary.
- **Last demonstrated benefit.** unknown.
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** structural — owner authority over which model runs which role; the fail-open degrade
  path is deliberate cost control.

#### F3 — Doctor/readout/CLI support

- **Component.** F3 is substrate: doctor, readout, CLI contract, identifiers, catalog, core_md,
  and hostinfo helpers, so a proposal on it is a shrink or split, not row deletion. The
  identifiers.py content_hash half and the cli_contract census pair are already slated to retire
  (K4, sitting ruling).
- **Condition.** Usage-based, 60 days: live imports of the retiring members (identifiers
  content_hash, cli_contract census helpers) after their retirement lands. On firing, a shrink
  proposal to chase stragglers at a gardening pass.
- **Last demonstrated benefit.** core_md carried five real calibration hardenings with eighteen
  live consumers (cp2-scoreboards.md F3 split verdict).
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** mixed — core_md is structural substrate; the census-pair and content_hash vestige are
  capability-gap machinery scheduled for deletion.

#### G1 — CI validators (7 scripts)

- **Component.** The seven CI validator scripts under `.github/scripts/` (validate_* and check_*).
  They cost a few CI seconds each run. check_release_bump is best-evidenced; validate_marketplace
  and the other never-fired members are keep-cheap with attached conditions.
- **Condition.** Catch-based, 45 days: zero real catches from the never-fired members
  (validate_marketplace, validate_hosts, validate_skills, check_conventional_commit,
  check_catalog_membership; check_release_bump excluded because it has a 100% incident record). On
  zero catches for the full window across all never-fired members, a retirement proposal for those
  members at a gardening pass.
- **Last demonstrated benefit.** check_release_bump caught release-please silent version drops
  across three incidents (investigation-record.md / cp2-scoreboards.md).
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** mixed — check_release_bump is structural (release-blocking-quiet class); never-fired
  validators are harness-limit guards on cheap static checks.

#### G2 — Rail lane (doc↔code drift tests, censuses, drift pins)

- **Component.** The rail-lane detector: test_ssot_drift.py and the rail-census-v3 pinned set (53
  files). It costs suite mass and drift-pin maintenance whenever a doc↔code mirror moves.
- **Condition.** Citation-based, 45 days: a named-edit record removing a rail inventory entry
  without cannot-bite evidence and owner approval (the retention-doctrine bar for rails). On
  firing, a proposal to enforce the bar at a gardening pass; zero violations means the rails are
  holding.
- **Last demonstrated benefit.** The four rails are the suite's recorded foreign-regression provers
  (cp2-scoreboards.md G2 ruling (a)).
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** structural — rails prove doc↔code SSOT; natural shrink expected as Change 7 deletes
  mirrors.

#### G3 — Behavior-lane test suite (~14k cases)

- **Component.** The behavior-lane test mass: everything under `*/tests/` outside the rail lane
  (~14k cases, ~230k LOC). It costs 18.6× CI wall-time growth and ongoing pin maintenance;
  scored by retention-doctrine class, not by individual case.
- **Condition.** Catch-based, 45 days: per retention-doctrine class (cannot-bite, birth-red,
  regression-catch, count-pin, byte-pin, and the remainder), count CI regression-catches
  attributable to that class. On a class accumulating zero regression-catches for the full window,
  a trim proposal for that class at a gardening pass.
- **Last demonstrated benefit.** Birth-red catches on every PR that ships broken tests;
  bulk-removal classes start with 33 named cannot-bite tests (cp2-scoreboards.md G3 simplify /
  #1105).
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** mixed — birth-red and cannot-bite trimming are structural suite hygiene; count-pin and
  byte-pin conversion is capability-gap debt from over-pinning.

#### G4 — Stub-marker validation

- **Component.** Stub-marker validation: stub_markers.py and validate_stubs.py. It costs a
  full-tree scan on every CI run to keep deliberately unwired seams tracked to issues.
- **Condition.** Usage-based, 60 days: count of live `STUB(#NNN)` markers in the tree
  (validate_stubs.py find_violations surface). On zero live markers for the full window, a
  retirement proposal at a gardening pass.
- **Last demonstrated benefit.** Enforces the no-silent-stubs convention so every placeholder names
  a tracked issue (#228 / stub_markers.py module docstring).
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** structural — tracked stubs are the contract for deliberate unwiring; the validator
  retires when nothing remains to validate.

#### H1 — Guardian (audit hero; has real catch receipts)

- **Component.** The Guardian hero's embedded machinery (not the skill front door): seventeen
  guardian_*.py modules, lenses, sweep pipeline, store, and report. It costs collector
  maintenance and lens registration sync; the hero milestone is held until one sweep produces a
  consumed output.
- **Condition.** Usage-based, 60 days: a completed sweep→validate→file cycle whose report card or
  filed issue is recorded as consumed (not merely generated). On zero consumed outputs for the full
  window, a proposal to shrink hardening scope at a gardening pass.
- **Last demonstrated benefit.** unknown.
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** capability-gap — readers exist by design but recorded consumption is zero
  (cp2-scoreboards.md H1 posture, one sweep with zero validated findings).

#### H2 — Test-pilot (framework A1–D11)

- **Component.** The test-pilot hero's embedded machinery (not the skill front door): ~30 pilot_*.py
  modules, the seeding engine, and pilot-contract guards. It costs the highest August fix share
  among dispatch surfaces.
- **Condition.** Catch-based, 45 days: real pilot-framework catches in CI or dispatch receipts
  (contract refusal, block-execution failure, plan or schema mismatch). On firing, a proposal to
  the owner at a gardening pass.
- **Last demonstrated benefit.** unknown.
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** structural — the A1–D11 contract is load-bearing orchestration machinery; churn
  evidence observed on engine-7-class dispatches at weekly-eats (cp2-scoreboards.md C1/H2).

#### H3 — Other heroes (architect, discovery, detective, review-spec, audit-debt, checkpoint…)

- **Component.** The other-heroes embedded machinery (not their skill front doors): architect,
  discovery, detective, review-spec, audit-debt, and checkpoint skills plus supporting lib hooks.
  It costs loaded prose mass across the skill tree.
- **Condition.** Citation-based, 45 days: vet, forfeit-dispute, or incident receipts citing a
  specific other-hero skill dispatch failure (routing, charter drift, missing reference). On
  firing, a proposal to the owner at a gardening pass; zero citations means the heroes are
  holding.
- **Last demonstrated benefit.** unknown.
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** mixed — review-spec and architect discovery are structural product surfaces;
  thin-evidence members (#541 landed) wait on Change-3 conditions per member.

#### H4 — Eval harness

- **Component.** The eval-harness embedded machinery (not a scored product): eval/,
  plugins/superheroes/eval/, and band-level activation gates. It costs fixture and golden
  maintenance; the defect is missing operating structure, not unwanted evals.
- **Condition.** Usage-based, 60 days: recorded benchmark or activation-gate runs whose results
  attach as release evidence (reader = owner at release click). On zero recorded runs for the full
  window, an operating-structure proposal at a gardening pass.
- **Last demonstrated benefit.** v1 A/B harness produced a green improved≥baseline gate at the
  0.14.0-era baseline (plugins/superheroes/eval/RESULTS.md).
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** harness-limit — release evidence wants benchmarks but no cadence has run since 0.14.0
  against 0.32.0 current (cp2-scoreboards.md H4 reframing).
