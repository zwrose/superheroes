---
superheroes: doc
schemaVersion: 1
docType: spec
workItem: verification-strategy-for-the-superheroes-repo-c629cd
issue: 1105
size: medium
status: approved
approved: "2026-08-28"
gates: {review: passed}
producedBy: "the-architect@0.31.0"
created: "2026-08-23"
updated: "2026-10-02"
---
# Verification strategy for the superheroes repo: can-bite retention, delete on contact, one Python, review-carried authoring rules

## Purpose

The superheroes repo is written almost entirely by builder agents, and its test suite has grown to about 12,500 cases and 1.8 lines of test per line of product code. The CI gate went from 20 seconds to over 5 minutes in ten weeks, and builders run the whole suite locally on top of that — several times per change.

The investigation for [#1105](https://github.com/zwrose/superheroes/issues/1105) (frozen record: `investigation-record.md` beside this file) found that in the repo's entire history only four pre-existing test files ever caught a change they did not author at CI, and all four were consistency rails; that most CI reds are a builder's own new test failing on first push; that real defects are found in the field, not by tests; that three different Python versions are in play with nothing checking they agree; and that six known ways a local pass can lie have no mechanical alarm.

This spec sets the owner's verification policy for this repo: what a test must do to stay, when a red test is deleted or kept, how flakes and interpreter drift are handled, what the review crew enforces on new tests, and how the gardening pass's hand count measures whether the policy works. What runs where (tiers, lanes, selection) is held on the declined registry until weekly-eats' lessons are in — see [Held and declined](#held-and-declined). It changes no code and deletes no test by itself — every change rides a proposed derived change that a later session routes to an issue on the owner's word.

## Who it's for

- **The owner** — waits on the gate before merging and carries the escape risk; wants the wait and the risk both smaller without trading one for the other.
- **Builder agents** — run the local gate several times per build and author the tests; need one rule for what to write and one rule for a test that goes red.
- **Reviewers and vets** — need findings they can grade, so the practice changes at review time rather than in prose.
- **The advisor** — needs the gardening pass's hand count to know whether the policy raised or lowered escapes.

## Functional requirements

### Retention — a test earns its keep

**FR-1.** The verification policy shall remove a test only on one of four bases: (1) evidence that the test is incapable of failing on a defect in what it claims to prove ("cannot bite"); (2) obsolete-expectation deletion on contact — the shipped rule, bounded by the keep list and the classification step (the obsolete-expectation bullet below); (3) removal of a test whose subject was retired on purpose (the retired-subject bullet below); (4) an owner-authorized flake removal under FR-26, which is recorded as an open coverage obligation, not a cut.
  - *Acceptance (rule):* a test is **shown to bite** by a recorded bite-proof (the thing it claims to prove is deliberately broken and the test goes red) or a recorded mutation kill; the bite-proof discipline is the repo's existing one [cite: plugins/superheroes/rubric/bite-proof.md § The obligation].
  - *Acceptance (rule):* a test is **cannot-bite** (deletion evidence) when it stays green with its subject deliberately broken, or when it is structurally incapable of going red: no assertion about behavior, an assertion whose expected value is computed by the code under test, an assertion only on the call shape of a stub of an internal collaborator, or a mock of the unit under test itself.
  - *Acceptance (rule):* a test that only checks "does not raise" is **suspect, not structural** — it is cannot-bite only when a break-stays-green proof shows it.
  - *Acceptance (rule):* **unassessed tests are retained.** "Unassessed" is never deletion evidence on the cannot-bite basis; bases (2)–(4) carry their own bars.
  - *Acceptance (rule):* a test whose **subject was retired on purpose** — a drift pin whose mirrored copy is deleted under the one-home-per-rule doctrine (the reset's Spec A FR-B7; the reset register's R2 and R3) — is removed together with its subject; the removal carries the owner's recorded approval, named in the PR body (with the `Rail removed: <entry id>` line when the test is an inventoried rail), and cannot-bite evidence does not apply to it.
  - *Acceptance (rule):* **obsolete-expectation deletion on contact** — when a behavior test goes red under a builder's change, the builder classifies it before touching it. A genuine regression in the behavior the test claims to prove: the behavior is fixed and the test is kept. An obsolete expectation (the behavior changed on purpose): the test is deleted rather than having its expectation rewritten, unless the keep list names the file. Either way, the classification and its reason go in the PR body. The rule activates only once the owner has stamped the keep list; before that, nothing is deleted under it, and an obsolete expectation is rewritten as before, with the classification and its reason in the PR body [cite: plugins/superheroes/rubric/review-discipline.md § A behavior test that goes red].
  - *Acceptance (rule):* the **keep list** ([glossary](../../../plugins/superheroes/rubric/glossary.md#keep-list)) is the stamped file listing the test files delete-on-contact never deletes, and the only record that rule reads — no per-file record of catches or kills exists or is built. It is **seeded by P7** with three kinds of test file: the rails' own tests (their birth bite-proofs), every test file with a recorded foreign catch, and the hard-shell guards' own tests (the four review checks, the worktree guard, `source_guard`, the dispatch boundary). The **owner stamps the seed**. The advisor adds a file at the next gardening pass when a test went red on a genuine regression, when a real catch is credited to it at a pass (owner-decisions duty 7), or when a mutation run records a kill for it (FR-20); removals are the owner's edits. A catch ledger or per-file credit store is declined at the door.

**FR-2.** The verification policy shall exempt rails from any retention decision based on how often they have failed.
  - *Acceptance (rule):* a **rail** is a test whose subject is the checked-in tree rather than a tmp fixture — a doc↔code drift test, a census over source files, a manifest/registry consistency check, a guard over a declared invariant, or a test that reads repository configuration and asserts on it.
  - *Acceptance (rule):* a rail is never removed on a "has not failed" basis; a rail must still satisfy FR-1.

**FR-3.** The verification policy shall keep a **rail inventory** — a plain file listing the rails by id — and the "rails intact" measure shall be that inventory, never a file count.
  - *Acceptance (rule):* the first inventory is seeded from the investigation's pinned rail set (`rail-census-v3` in the evidence bundle, 53 files) and corrected by the advisor or the owner where a reader disagrees — additions and entry metadata only, recorded with why; a rail's entry lands in the PR that adds the rail; an inventoried file removed from the suite is a defect unless the removal carries FR-1 cannot-bite evidence and the owner's recorded approval — or, for a subject retired on purpose (FR-1), the owner's recorded approval.
  - *Acceptance (rule):* removing an inventory **entry** carries the same bar as removing the file — FR-1 cannot-bite evidence and the owner's recorded approval, or for a subject retired on purpose the owner's recorded approval; de-listing is never a lighter path to the same end. The PR body carries a `Rail removed: <entry id>` line — a convention the vet checks when the inventory is in the diff, never a CI rule (Spec A FR-B1).

### Proof depth and receipts

**FR-4b.** The verification policy shall carry a written risk profile that names, per area of the product, the depth of proof required, and the review crew shall grade a change's proof depth against it.
  - *Acceptance (rule):* the risk profile in this spec (§ Risk profile) is the normative table of areas; every area names a depth from the depth vocabulary.
  - *Acceptance (rule):* a change in a Full- or Medium-depth area whose pull request adds or changes behavior without proof at that row's depth — including the refusal, failure, or seam arm the row names — is a review finding; a Light-depth area is never held to a higher bar; an area no row names is graded at Medium until a row is added by amendment to this spec.
  - *Acceptance (rule):* this rule rides the test-lens calibration with a named example finding; the calibration's delivery (P5's test-lens slice) is parked under the owner's review hold (ruled 2026-10-02, @373-8).
  - *Acceptance (rule):* the risk-profile table changes like the rail inventory (FR-3): this spec is its one home, an edit is an amendment to this spec, and lowering any row's depth carries the owner's recorded approval. Any edit that reduces what the table demands — removing a row, blanking or lowering its depth cell, or narrowing its Area text so it no longer covers what it covered — carries the same bar as lowering: the owner's recorded approval; no edit shape is a lighter path to the same end. A change editing the risk-profile table is never eligible for a lane without a vet (UFR-5's guarantee, applied identically), and the vet checks the owner approval behind any reducing edit.

**FR-9.** Every builder handback shall carry, in the pull request body, a hand-written receipt: what ran, what was skipped and why, the source state (the commit), the interpreter, the attempt number and whether the prior attempt was red, and the elapsed time. The vet reads it; nothing checks it mechanically.
  - *Acceptance (rule):* the attempt-number and prior-red fields make a flake visible at merge (FR-23); elapsed time is what the held selection trigger reads (Held and declined).
  - *Acceptance (rule):* the plugin's `gate-receipt/1` format shipped 2026-09-30 (`plugins/superheroes/reference/gate-receipt.md`) and is **optional** — a project may emit it; nothing in this policy requires a gate to emit or meet it.
  - *Acceptance (rule):* a "local gate passed" claim is held to today's practice — the commands and their quoted output named in the PR body (this absorbs UFR-2's live arm; Held and declined).

### One Python

**FR-12.** The verification policy shall pin exactly one Python version in exactly one home, and every place that runs Python for this repo — CI, the calibrated local verify command, the calibration environment, dispatched work orders, and the documented local gate — shall read that pin rather than name a version or an interpreter path.
  - *Acceptance (rule):* today three versions are in play — `/usr/bin/python3` at 3.9.6 in the documented gate and 3.12 in CI [cite: CLAUDE.md § The full suite is CI's receipt], plus 3.14.6 in the project's out-of-repo calibration environment (investigation record §0.7); after this policy, a validator-step check at CI — running before any test, per UFR-8 — fails when any in-repo home names a version that differs from the pin or names an interpreter by absolute path; the out-of-repo calibration home comes into line by calling `scripts/pinned-python`, and the gate-side refusal when it disagrees is held with the gate driver (Held and declined).
  - *Acceptance (rule):* a single documented provisioning step — whatever tool implements it — provisions the pinned interpreter everywhere; the local gate never runs on the operating system's Python.
  - *Acceptance (rule):* if the pinned interpreter cannot be provisioned on a machine, then the local gate refuses to run and says so — it never falls back to another interpreter. The refusal has a route: the builder parks with the refusal receipt, and the advisor routes it — fix the provisioning, or the owner records acceptance of CI as the sole gate for that change; the refusal is never a silent dead end and never a silent fallback.
  - *Acceptance (rule):* shipped by P1 (#1228); `scripts/pinned-python` already refuses rather than falls back — it runs `uv run` with `--managed-python --python <pin>`.

**FR-13.** The verification policy shall disposition all six known false-green channels, each by name:
  1. **Interpreter skew** — removed by FR-12 (one pinned Python everywhere).
  2. **Stale bytecode** — dissolved by FR-12: the gate never runs on the operating system's Python, whose out-of-tree cache created the channel; additionally, the documented gate command carries the bytecode-safety flags (`-B -X pycache_prefix=…`, CLAUDE.md).
  3. **Git identity in temp repos** — no standing census (Spec A FR-B1). The CI runner carries no global git identity, so a fixture commit without inline identity goes red at CI before merge; CI at merge is its handler and a site is fixed at contact. The investigation counted these reds as infrastructure, not merged bugs (investigation record, the classes table: runner git identity).
  4. **Engine binaries assumed on `PATH`** — no standing census (Spec A FR-B1). The CI runner installs the `claude` CLI but no other engine binary, so a test that assumes `codex` or `cursor` on `PATH` goes red at CI before merge; a test that assumes `claude` is not caught there, and the review rule on a pre-satisfied precondition carries it (a binary already on `PATH` is one; `plugins/superheroes/agents/test-reviewer.md`). The investigation counted these as build-loop cost, not merged bugs (investigation record, the engine-binaries note).
  5. **A harness that pre-satisfies a gate** — carried by the practice rule already in the review surfaces: a test whose harness pre-satisfies the condition under test is a finding (`plugins/superheroes/agents/test-reviewer.md`).
  6. **A sanitized view that strips a file a seat needs** — carried by the practice rule already in the review surfaces: the dispatch prompt names the paths the sanitized view stripped (`plugins/superheroes/skills/review-code/reference/auto-fix-loop.md`).
  - *Acceptance (rule):* each channel above is traceable to at least one named handler — a requirement of this policy or a review-surface rule; a seventh channel discovered later gets the same treatment before it is relied on as "handled".
  - *Acceptance (rule):* there is no retry or rerun setting at any gate (FR-24).

### Deletion and burndown

**FR-14.** The verification policy shall proactively delete only cannot-bite tests (FR-1), each deletion carrying its evidence — except a retired-subject removal under FR-1's retired-subject bullet, which carries the owner's recorded approval instead.
  - *Acceptance (rule):* a first cut list is produced by P7 — the no-raise tests assessed (32 per the 2026-10-02 ruling's count; the investigation pinned 33), the one golden-fixture file; a deletion that rests on none of FR-1's four bases is a finding (UFR-5).
  - *Acceptance (rule):* cannot-bite evidence is verified the way bite-proofs are: independently re-run at verification, never accepted from the deleting party's own assertion [cite: plugins/superheroes/rubric/bite-proof.md § Who owes what].
  - *Acceptance (rule):* surviving mutants from the mutation run (FR-20) are cut-list candidates, still re-run under the previous bullet's bar.

**FR-15.** When a builder makes an intentional edit to a test file that is not mechanical-only, the builder shall bring that whole file to standard in the same pull request: no cannot-bite case remains, and no count pin or byte-pinned prose assertion re-states a fact a rail already guards (each such pin is replaced with a read of the authoritative home).
  - *Acceptance (Given-When-Then):* Given a builder edits a test file to add a behavior test, when the pull request is reviewed, then no cannot-bite case remains anywhere in that file and no pin duplicates a rail-guarded fact; the whole touched file is in review scope, not only the changed lines.
  - *Acceptance (rule):* while a removal halt is in force (UFR-6), this obligation is suspended: the builder records the file as burndown debt instead of removing, and no FR-18f finding is raised.

**FR-16.** Where a pull request's only changes to a test file are mechanical — a rename, a formatter's output, a codemod, a dependency update — FR-15 shall not apply to that file, and the pull request shall list the file as burndown debt.
  - *Acceptance (rule):* the reviewer verifies mechanical status from the diff; a builder that later edits the file intentionally pays its debt then.

**FR-17.** The verification policy shall treat bulk removal of **bite-capable** tests — a change whose primary purpose is removing bite-capable tests from files it does not otherwise touch — as an owner decision on the gardening pass's hand counts; there is no day count and no checkpoint item. Cannot-bite cuts carrying FR-14's evidence, retired-subject removals under FR-1's retired-subject bullet, and obsolete-expectation deletions on contact are not bulk removal.
  - *Acceptance (rule):* re-opening bulk removal is an owner decision that amends FR-1; until such an amendment, FR-1's four bases are the only removal paths.

### Authoring rules — carried by review

The review crew's test lens is the enforcement point for the rules below; each finding names the test and the rule, and a builder resolves every finding before handback. The lens already exercises a mutation-survival judgment on changed tests [cite: plugins/superheroes/agents/test-reviewer.md § Mutation-survival lens]. The integrity rules below govern the enforcement point itself, and they apply at each review lane's own enforcement point as review-discipline defines it — the panel plus the advisor's vet in the full lane; the one independent cross-vendor reviewer's receipt in the light and micro lanes, which have no panel (and micro no vet):

- **Where each rule is checked follows where its evidence lives.** A rule whose evidence is in the diff is the test lens's; a rule whose evidence lives outside the diff (a receipt in the PR body, a flake note on the collector) is checked by the advisor's vet, and the calibration names, per rule, which stage carries it. The review seat never asserts a receipt is missing — the body is not among its inputs [cite: plugins/superheroes/rubric/bite-proof.md § Who owes what].
- **The policy's own detectors are bite-proofed.** Every detector this policy introduces carries its birth bite-proof before it is relied on (a guard's own diet, Spec A FR-B1); the only one shipped so far is P1's pin check. Each findings-raising rule below (FR-18a–d, FR-18f) names, in the calibration that carries it, one concrete example finding it would raise. FR-18e is a prohibition and instead names the finding it bars.

These integrity rules (the stage rule, birth bite-proofs, named example findings) are jointly **FR-18g**; P5's test-lens slice carries them — parked under the owner's review hold.

**FR-18a (no cannot-bite tests).** When a pull request adds a cannot-bite test (FR-1), the test lens shall raise a finding.
  - *Acceptance (rule):* the finding names the structural class — assertion-free, tautological, mock-shape-only, or mocks-the-unit.

**FR-18b (no duplicate pins).** When a pull request adds a count pin or a byte-pinned prose assertion for a fact that a rail already guards, the test lens shall raise a finding naming the rail.
  - *Acceptance (rule):* a pin of a fact no rail guards is not a finding under this rule.

**FR-18c (rails are declared).** When a pull request adds a rail (FR-2) that is not declared as such in its name or top-level description, or is absent from the rail inventory (FR-3), the test lens shall raise a finding.
  - *Acceptance (rule):* the pull request body carries the rail's bite-proof receipt; the **vet** — not the lens — returns a pull request whose body lacks it (the preamble's stage rule).

**FR-18d (fixes name what they fix).** When a pull request whose purpose is a fix or revert of behavior that landed on the main branch does not name the change it corrects, the review crew shall raise a finding at the stage the calibration assigns (the naming is visible in the PR itself).
  - *Acceptance (rule):* "fix" here means a correction to merged behavior, not mid-build design tightening; a fix PR names the merged change or states that the defect pre-dates any single change — and a pre-dates claim is checked by the vet against the history before it discharges this rule.

**FR-18e (no proof-mass ratio).** The verification policy shall not impose a numeric ceiling on the share of a pull request's added lines that are test code.
  - *Acceptance (rule):* no review seat raises a finding on test share alone.

**FR-18f (burndown when touched).** When a pull request makes an intentional edit to a test file that still contains cannot-bite cases or rail-duplicating pins after the edit, the test lens shall raise a finding (FR-15), except where this pull request's own changes to that file are mechanical-only (FR-16) or a removal halt is in force (UFR-6) — a prior wave's debt listing never exempts an intentional edit, which pays the debt (FR-16).
  - *Acceptance (rule):* the finding names the remaining case or pin.
  - *Acceptance (rule):* the halt exception's evidence (whether UFR-6's halt is in force) lives outside the diff, so per the stage rule the **vet** applies it: the lens raises the finding regardless, and the vet dispositions it as halt-suspended when a halt is in force.

### Instruments — measuring whether the policy works

The escape rate this policy reads is the **gardening pass's hand count** (owner-decisions duty 7, Spec A FR-A10): the window's red CI runs and fix PRs classified by hand (own broken test, real catch, infrastructure, flake, escape), each real catch credited to the file that caught it. It is not restated here (one home), and no instrument stores it.

**FR-20 (the mutation run).** The verification policy shall run a mutation run over the Python product code — the product `.py` trees the four CI suites test — bought, not built (mutmut or cosmic-ray), on the pinned interpreter, and publish, per planted defect, its subject file and whether any test detected it. It is scoped, budgeted (the budget sits in the run's own configuration; changing it is an ordinary reviewed edit), and sharded from day one; it runs weekly or on demand, never per PR and never nightly; it is advisory.
  - *Acceptance (rule):* results are consumed at gardening passes: duty 7 records survivors and kills per covered file; a file no run covered reads as unmeasured, never as no kills; a kill earns the file a keep-list line (FR-1); a survivor is a cut-list candidate (FR-14).
  - *Acceptance (rule):* an incremental run marks defects it did not re-evaluate as "not evaluated", never as detected; a run that exhausts its budget publishes a partial result marked as such.

**The red-then-green script.** One on-demand script reads a window of CI runs and lists red-then-green pairs on the same source state, with no storage of its own; it is a reference the owner or advisor reads, never a gate (Spec A FR-F6 change 1).

### Flakes

**FR-23 (a flake is recorded when it is seen).** When a flake is seen — the same source state red then green with no change, at a CI re-run, an identical re-push, or a receipt whose prior-red field (FR-9) shows red-then-green — the vet or advisor, reading runs and receipts, shall record it by hand on the collector when it is seen, never the builder.
  - *Acceptance (rule):* the note names the test, the run, and the date; that note is the **advisory flake listing**; no CI fold, data branch, or workflow is built for it; no disposition relabels a red run green.

**FR-24 (a listed flake is a vet finding).** A listed flake shall be a vet finding on any PR that touches that test, and shall block nothing repo-wide.
  - *Acceptance (rule):* the accepted dispositions are: a fix at the cause with red-under-cause and green-after evidence; a cannot-bite removal (FR-14); or an advisor withdrawal naming a non-test cause (FR-26).
  - *Acceptance (rule):* loosening or skipping a listed test is a review finding whatever the PR's purpose (UFR-4); there is no quarantine and no retry-to-green at any gate.
  - *Acceptance (rule):* the flake rate is a reference measured on demand, never a gate.

**FR-26 (the withdrawal and the owner path).** The advisor may withdraw a flake listing by naming a non-test cause, recorded on the collector note; a second withdrawal of the same test inside thirty days shall go to the owner as a decision among: keep the listing as a finding; fix the cause by a stated route; or authorize removal — offered only for a test outside the rail inventory (FR-3), and only when the advisor's diagnosis evidence shows the nondeterminism lives in the test or its harness.
  - *Acceptance (rule):* an owner-authorized removal is recorded on the collector as an open coverage obligation with a restore-by date the owner sets in the same decision, at most 30 days out; the advisor surfaces an overdue restore at the next gardening pass.
  - *Acceptance (rule):* a red-then-green whose cause is in the product is a product defect: removal is not offered, and the product fix is the disposition. For an inventoried rail the removal option does not exist.
  - *Acceptance (rule):* the decision, its date, and the diagnosis evidence are recorded on the flake's item — the evidence in re-runnable form; a removal executed on evidence that does not reproduce is recorded as a policy violation.

## When things go wrong (significant unhappy paths)

**UFR-4.** If a builder weakens an assertion in, or adds a skip to, a test the collector lists as flaky, then the review crew shall raise a finding — the lens flags the weakening it sees in the diff; the vet checks the collector listing (the FR-18 stage rule) — and the weakening shall not merge.
  - *Acceptance:* Given `test_x` is listed on the collector, when a PR loosens its assertion, then the finding names the listing and the PR is returned.

**UFR-5.** If a builder deletes a test with none of FR-1's four bases' evidence — cannot-bite evidence; for an obsolete-expectation deletion, the classification and reason in the PR body and the file absent from the stamped keep list; for a retired subject, the owner's recorded approval; for a flake removal, the owner's FR-26 authorization — or removes a rail-inventory entry without what FR-3's bar requires (cannot-bite evidence plus owner approval for a removal, or for a subject retired on purpose the owner's recorded approval), then the review crew shall raise a finding — the lens flags the deletion or de-listing in the diff; the vet checks the body's evidence, the owner's approval where FR-1 or FR-3 requires it, and independently re-runs the cannot-bite evidence when that bar applies (FR-14) — and the change shall not merge.
  - *Acceptance (rule):* a change that removes a test or edits the rail inventory is never eligible for a review lane without a vet — whatever its diff size, it takes at least the lane whose vet performs this check, so the independent re-run always has a stage to run at.
  - *Acceptance:* Given a PR removes a test with none of FR-1's four bases' evidence, when reviewed, then the finding names the test and asks for the evidence.

**UFR-6.** If the gardening pass's escape rate (owner-decisions duty 7) exceeds the investigation's baseline of 17.4% of merged changes (87 escape candidates over 499 merges), then the advisor shall bring the owner the hand counts for a decision at that walk, and until the owner rules, **proactive removal halts**: FR-14 cuts, FR-15 burndown (suspended into debt), and any bulk-removal decision (FR-17). An owner-authorized FR-26 removal is exempt (a coverage obligation, not a cut). Obsolete-expectation deletion on contact is not halted — the stamped keep list bounds it.
  - *Acceptance:* Given the pass's rate reads above the baseline, when the advisor next vets a change that makes a proactive removal (FR-14, FR-15), then the vet parks it pending the owner's decision.
  - *Acceptance (rule):* a halt lifts only by the owner's recorded decision.

**UFR-7.** If any pull request reaches handback without a review receipt showing the test lens ran on the handed-back source state, then the vet shall treat the pull request as unreviewed under the existing rule [cite: plugins/superheroes/rubric/review-discipline.md § The rule — no unreviewed PRs].
  - *Acceptance:* Given a PR body with no test-lens receipt, when vetted, then it is returned.
  - *Acceptance (rule):* a review receipt is written by the review run itself and names the reviewed source state — a hand-typed body line never satisfies this rule.

**UFR-8.** If the pinned Python version and any **in-repo** home that should read it disagree (FR-12), then CI shall fail at the validator step before any test runs; the out-of-repo calibration home is not CI's to check — it comes into line by calling `scripts/pinned-python` (FR-12). Shipped by P1.
  - *Acceptance:* Given a PR edits the documented local gate to name a version, when CI runs, then the drift validator fails with the two disagreeing values.

## Non-functional requirements

- **Nothing degrades invisibly:** every skip and every failure appears in the hand-written receipt (FR-9) the owner reads; a silent fallback is a defect.
- **Escape rate not raised:** the gardening pass's escape rate stays at or below UFR-6's baseline.
- **Reproducibility:** a handback names the interpreter it ran on, which matches the pin (FR-12).

## Definition of done / success

The policy is done when the same Python runs everywhere and a mismatch fails CI (shipped); when builders write the FR-9 receipt fields by hand in every PR body; when the keep list is seeded and owner-stamped, so delete-on-contact is live; when the first cut list has run with its evidence; when the review crew enforces the authoring rules and grades proof depth against the risk profile (FR-4b; delivery parked under the review hold); when the mutation run and the red-then-green script exist on demand; and when the gardening pass's escape rate shows the policy did not raise escapes.

## Risk profile (normative)

Depth vocabulary: **Full** = behavior tests including every refusal and failure arm, plus a rail or guard where the row names an invariant, each guard bite-proofed; **Medium** = behavior tests in the layer that owns the behavior, including the stated failure paths; **Light** = the fastest check that can observe the behavior; **Vet-graded** = the advisor's vet receipt grades the recorded artifact; no test depth applies (used where the guarded thing is a recorded owner act, not code).

When a change maps to more than one row, the deepest applicable row governs. Row 5 covers presentation only — a surface this policy itself reads as evidence (a receipt, a gate result) is never graded Light.

| # | Area | Consequence if broken | Depth of proof |
| --- | --- | --- | --- |
| 1 | Destructive filesystem and git operations — worktree add/remove/reap, cleanup, anything that deletes or rewrites files outside its own scratch | an agent's or the owner's uncommitted work is destroyed | Full — every refusal path proven, including the guard's own refusal arms |
| 2 | Merge approval as a recorded scoped word (PHILOSOPHY promise 1): the word beside the PR number, the owner half, the advisor's execution inside the word | something merges without the owner's word, or outside its scope | Vet-graded — the vet receipt grades the recorded word and its scope; no refusal arms (the owner-authority gate is retired) |
| 3 | Engine dispatch and transport — dispatch, couriers, report channels, salvage | delivered work is lost, truncated, or misattributed; a forfeit reads as a result (a recurring class in the escape ledger, record §4.7) | Medium, plus a round-trip or contract test at every transport seam |
| 4 | Calibration and configuration resolution — calibration, storage modes, seat and model maps | a session silently runs against the wrong configuration, or a refusal masquerades as an uncalibrated result | Medium, including the unreadable and fail-closed paths |
| 5 | Reporting and display — views, summaries, status output | a human reads something stale or mislabeled; recoverable on sight | Light |

## Proposed derived change-set

Rows marked closed were closed by the owner's 2026-10-02 ruling; the coverage map carries each child's disposition.

A new row is filed as an issue only on the owner's word. Each row carries its size, and every test-removing change names its H4 validation.

| # | Change | Predicted effect | H4 validation |
| --- | --- | --- | --- |
| P1 | One Python, one pin, drift-guarded (FR-12, UFR-8) — shipped (#1228) | removes the interpreter false-green channel; no CI-minute change; small | none needed — no test removed |
| P2 | closed — declined (FR-F6 change 1; registry: the nightly classifier, the flake differential) | — | — |
| P3 (P3a #1230, P3b #1231) | closed — held on the registry (FR-F6 change 5) | — | — |
| P4 | closed — declined (FR-F6 change 6, FR-B1) | — | — |
| P5 (#1233) | Its vet-checks slice is live; its test-lens slice (FR-18a–g, FR-4b grading) is parked under the review hold | small; rubric surface | none needed |
| P6 | closed — declined (FR-F6 change 4: the differential to the registry, vitals to the guardian; the mutation run moves to P9) | — | — |
| P7 (#1235) | First cut list (32 no-raise tests per the ruling's count, the one golden-fixture file), the plain rail inventory (FR-3), and the keep-list seed for the owner's stamp (FR-1, FR-14) | small; removals carry evidence | the gardening pass's escape rate not raised (UFR-6) |
| P8 | withdrawn (no day count; bulk removal is an owner decision on hand counts, FR-17) | — | — |
| P9 (new, unfiled — filed on the owner's word) | On-demand instruments — the mutation run (FR-20) and the red-then-green script | small–medium; no CI change | none needed — no test removed |
| — | Candidate, not derived: skill evals over the markdown half (Anthropic `claude plugin eval`, blind comparator) — real per-case token cost; the owner approves its spend separately | | |

## Assumptions & dependencies

- The investigation record beside this file is the evidence this policy stands on; its numbers are fresh as of 2026-08-23.
- The review crew's test lens is the enforcement point and can be calibrated per project; where a rule needs evidence outside the diff (a bite-proof receipt, a collector flake note), the PR body carries it and the vet checks it.
- The review lens's shipped base rules today confine findings to changed lines, and calibration cannot override that — so FR-15/FR-18f's whole-touched-file check is carried by the advisor's vet until the plugin ships its binding project-rules and scope-override capability (owner-ruled 2026-08-28); the calibration names the vet as that stage, per FR-18g's stage rule.
- The one-home-per-fact convention and its drift tests are the repo's own [cite: CONVENTIONS.md § exactly one authoritative definition]; this policy builds on them, never beside them.
- `uv` (already a CI dependency) is available to builders; the investigation found the viable mutation tooling requires a modern interpreter (record §3 A2), which the FR-12 pin satisfies.
- The gardening pass (owner-decisions duty 7) runs and records the hand count this policy reads.

## Constraints

- Zero code, test, script or workflow changes ship from the discovery that produced this spec; every change rides a proposed derived change.
- Nothing in this policy reduces what CI runs on a pull request.
- The owner approves any instrument's promotion from advisory to blocking, on evidence, later.
- Cross-repo references are repo-qualified links, never bare numbers.

## Out of scope

- Building any proposed change.
- Promoting universal rules into shipped plugin surfaces (the plugin-harvest track) and the consumer-facing frameworks discussed on 2026-08-22.
- The three-way adoption assessment (weekly-eats × superheroes-as-plugin × superheroes-as-project).
- Sharding CI across a runner matrix.
- Skill evals (named as a candidate; not derived).
- What runs where — tiers, lanes, local-tier selection, observation mode, the gate driver — held on the declined registry (see Held and declined).

## Held and declined

Requirements this policy no longer builds, each with where it went. They keep their numbers so citations resolve.

| Item | What it was | Where it went |
| --- | --- | --- |
| FR-3's named-edit record and inventory guard | a machine-checkable named-edit record for rail-inventory changes, and a guard that failed when an entry vanished or a rail moved lanes | dropped, Spec A FR-B1 (guards don't get guards) |
| FR-4 | three tiers and two lanes plus an always-run set, with the lane classification and its guard | held, registry seed "the verification tiers, lanes, and local-tier selection with observation mode" (Spec A FR-F6 change 5); the lane guard dropped, Spec A FR-B1 |
| FR-5, FR-6 | local-tier selection by owned paths, and fail-open to full for a non-Python change | held, same registry seed |
| FR-7 | the merge tier: every lane in full on every pull request | held with the tier structure; its guarantee stays a Constraint — nothing in this policy reduces what CI runs |
| FR-8 | the nightly tier running every lane and the advisory instruments | held, same registry seed |
| FR-9's machine-written form | a receipt written by a gate driver, with a run-log identifier and a classification version | held, same registry seed; FR-9 now carries the hand-written convention |
| FR-10, FR-11 | observation mode before selection is first used, and the false-negative suspension | held, same registry seed |
| FR-12's gate-side calibration-home refusal | the local gate refusing to run when the out-of-repo calibration home disagrees with the pin | held with the gate driver |
| FR-13's census tests | git identity in fixtures, engine binaries on PATH, retry and bytecode flags in gate commands | dropped, Spec A FR-B1 (Spec A FR-F6 change 6) |
| FR-17's 45-ledger-day checkpoint | a day count before bulk removal could be considered | cut, Spec A FR-F6 change 2 |
| FR-18g's rule-set version and drift check | a versioned calibration with a drift check over the rule set | dropped, Spec A FR-B1 |
| FR-19 | the nightly ledger and classifier — the catch/escape ledger | declined, registry seed "the nightly catch-and-escape classifier" (Spec A FR-F6 change 1) |
| FR-21 | the flake differential | declined, registry seed "the flake differential"; trigger: the owner names flakes as a cost at a walk (Spec A FR-F6 change 4) |
| FR-22 | the nightly vitals trend | moved: vitals stay with the guardian sweep (Spec A FR-F6 change 4) |
| FR-24's repo-wide merge block | a block on every merge while a flake was listed and undispositioned, with exceptions and a merge-time re-check | cut, Spec A FR-F6 change 1 |
| FR-24b | the blocking flake as the advisor's next dispatch | cut, Spec A FR-F6 change 1 |
| FR-25 | the flake-rate budget tripwire | cut, Spec A FR-F6 change 1; the flake rate is an on-demand reference |
| UFR-1, UFR-9 | an unclassifiable change, and unreadable trust state, each running everything | held, tiers seed |
| UFR-2 | the driver-written receipt check | held, tiers seed; its live arm is in FR-9 |
| UFR-3 | reporting a failed nightly or advisory instrument | declined with the nightly instruments (Spec A FR-F6 change 1) |
| UFR-6's ledger window, sample floor and warm-up carve-out | a 60-day ledger rate over at least 100 merges, with a warm-up carve-out and a merge-time re-check | cut with the ledger (Spec A FR-F6 change 1) |
| UFR-7's rule-set version and nightly fallback | a stale-version clause and a no-vet fallback check by the nightly refresh | dropped, Spec A FR-B1 (Spec A FR-F6 change 1) |
| The local-loop NFR | the local gate under two minutes at the median, once selection is enabled | held, tiers seed; its trigger reads the elapsed-time receipt field |

The declined registry is the collector's pinned revisit-trigger registry comment; a trigger firing re-scores the item at the door.

## Glossary

- **Can bite / bite-proof / cannot-bite** — a test can bite if it fails when what it guards breaks; a bite-proof is the recorded demonstration; cannot-bite evidence is the recorded failure to fail.
- **Rail** — a test whose subject is the checked-in tree (drift, census, consistency, guard), as opposed to a behavior test over a tmp fixture; listed by id in the plain-file rail inventory (FR-3).
- **Keep list** — the stamped file listing the test files delete-on-contact never deletes, and the only record that rule reads ([glossary](../../../plugins/superheroes/rubric/glossary.md#keep-list)).
- **Obsolete expectation** — a behavior test's expected value that the behavior changed on purpose.
- **Foreign catch** — a pre-existing test going red on a later change that did not touch it ([glossary](../../../plugins/superheroes/rubric/glossary.md#foreign-catch)).
- **Birth-red** — a PR's own new or modified test failing at CI.
- **Escape** — a defect found after merge, classified by hand at the gardening pass (owner-decisions duty 7).
- **Mechanical wave** — a rename, formatter, codemod or dependency update touching test files without changing what they prove.
- **Byte-pinned prose assertion** — a test asserting that an exact literal of six or more words appears in a document or output.
- **Count pin** — a test asserting an exact count (`len(...) == N`) of things whose authoritative home is elsewhere.
- **Non-regression validation (H4)** — the named evidence a proposed cut must carry that the gardening pass's escape rate did not rise; "H4" is the investigation's hypothesis that suite density explains the low escape rate, which could not be refuted.
- **Working day** — a weekday on the owner's local calendar; a "one working day" deadline runs from the triggering event to the same clock time on the next weekday.
- **Owner's recorded approval** — a decision the owner stated themselves, recorded on the artifact it authorizes (the pull request, issue, or inventory record) as the owner's own comment or a quoted, linked owner message; a paraphrase typed by the party the approval benefits, with no traceable owner utterance, is not one.

Long-lived surfaces cite these terms by the plugin glossary's stable slugs (`plugins/superheroes/rubric/glossary.md`), never by this spec's FR numbers; FR numbers here are provenance.

## Amendments

- **2026-08-28** (owner approval): the owner approved this spec at the acceptance sitting — items 1–12 of the acceptance brief owner-read (this spec's observation threshold stays at 30: its selection gates the local tier only, CI unchanged); the craft layer accepted on the review record (receipts on [#1105](https://github.com/zwrose/superheroes/issues/1105)).
- **2026-08-28** (review-spec rounds 2–3): FR-24's exception rule hardened — checked never claimed, positive lane routing (at least the vetted lane), diff-scope check, ledger audit of exception merges; FR-13 channels 5–6 given affirmative named fields; the merge-time re-check record defined with an independent executor; FR-4b bars every reducing edit shape and takes a vetted lane; FR-19's protected set names the escape-candidate rule with a replay record; P3/P4/P5 delivery rows disambiguated.
- **2026-08-28** (review-spec round 1, six-lens panel): FR-24's exceptions generalized to concurrent flakes and flake-listing-instrument repair (the fail-closed park keeps a living repair path); FR-9/FR-10's counted-population contradiction resolved toward CI; FR-17's checkpoint pinned decision-only (FR-1's grounds stay exclusive until an owner amendment); FR-26's product-defect arm rerouted through FR-19's override rule; the validator-catch class given a deterministic predicate; the three preamble integrity rules numbered FR-18g; authority seams closed (risk-row removal, infra-signature edits, owned-paths narrowing, override-vs-listing, no-vet-lane fallbacks for UFR-4/FR-18c, suspension lift, enablement flip); replay and false-negative detection made mechanical; the unprovisionable-interpreter refusal given a park route. Full round history in the review receipt.
- **2026-09-28 (owner-stamped, substantive):** FR-1 gains a third removal basis — a test whose subject was retired on purpose (a drift pin deleted with its mirror under the one-home rule) is removed with its subject, on the owner's recorded approval and a named edit; FR-3's removal bar says the same. Cause: the reset's rule that a drift pin on a mirror is a delete signal (Spec A FR-B7; register R2/R3) collided with FR-1's cannot-bite-only removal basis; the owner ruled the reset governs ("13 a", 2026-09-28; collector #695 entry @347-4; ruling record on #1289). Sections touched: FR-1, FR-3, FR-14, FR-17, UFR-5.
- **2026-10-02 (owner-stamped at merge, substantive):** this spec applies Spec A FR-F6's seven changes and FR-B1, on the owner's "8 a"–"11 a" (collector #695 items @373-5..8; ruling record: https://github.com/zwrose/superheroes/issues/695#issuecomment-5951960566). Change 1: no nightly ledger or classifier — the escape rate is the gardening pass's hand count, and flakes are reshaped (recorded by hand on the collector, a vet finding on a PR touching the test, no merge block, no next-dispatch rule, no budget tripwire, no quarantine or retry-to-green). Change 2: no day count for bulk removal — it is an owner decision on the hand counts. Change 3: delete on contact — FR-1 gains obsolete-expectation deletion as a second named basis beside the flake removal, bounded by the keep list (the only record, seeded by P7 and stamped by the owner) and the classification step. Change 4: mutation testing goes forward as an on-demand run consumed at gardening passes, the flake differential goes to the registry, and vitals stay with the guardian. Change 5: the receipt fields land as a hand-written PR-body convention; tiers, lanes, selection, observation mode and the gate driver are held; `gate-receipt/1` shipped 2026-09-30 and is optional. Change 6: no guards on guards — the named-edit record, lane guard, rule-set version and drift check, and census tests are dropped. Change 7: long-lived surfaces cite the plugin glossary's stable slugs, never FR numbers. Risk-profile row 2 is replaced because it named the retired owner-authority gate (pending fix recorded on #1105, 2026-09-16), and a new section, Held and declined, carries every moved or dropped item under its original number. The stamp is the owner's merge of the carrying PR. Sections touched: frontmatter, title, Purpose, Who it's for, FR-1, FR-3, Tiers section (renamed Proof depth and receipts: FR-4 and FR-5–FR-8 moved; FR-4b, FR-9), Selection safety (removed; FR-10, FR-11 moved), FR-12, FR-13, FR-14, FR-15, FR-17, Authoring rules (stage rule, detector bite-proofing, rule-set rule deleted, FR-18c, FR-18d, FR-18f, FR-18g), Instruments (FR-19, FR-21, FR-22 moved; FR-20 rewritten; red-then-green script added), Flakes (FR-23, FR-24, FR-26 rewritten; FR-24b, FR-25 moved), When things go wrong (UFR-1, UFR-2, UFR-3, UFR-9 moved; UFR-4, UFR-5, UFR-6, UFR-7, UFR-8), Non-functional requirements, Definition of done, Risk profile (vocabulary, row 2, Row 5 sentence), Proposed derived change-set, Assumptions & dependencies, Out of scope, Held and declined (new), Glossary, Amendments, Coverage.

## Coverage

| Area | Disposition | Show-it? | Where / why |
| --- | --- | --- | --- |
| Empty & first-run | Specify | No | keep list unstamped → nothing deleted on contact (FR-1); no flake noted yet |
| Invalid & malformed input | Specify | No | a deletion with no basis (UFR-5); a receipt missing its fields (FR-9) |
| Boundaries & limits | Specify | No | UFR-6's 17.4% baseline; FR-26's thirty-day second withdrawal and 30-day restore-by |
| Errors & failures | Specify | No | a flake seen (FR-23, FR-24); a product-cause red-then-green (FR-26) |
| Access & permissions | Specify | No | owner-only decisions: keep-list stamp and removals (FR-1), bulk removal (FR-17), FR-26's removal, UFR-6's halt lift; instrument promotion (Constraints) |
| Duplicates & double-actions | Specify | No | a flake seen twice is one collector note with two runs |
| Conflicting / simultaneous use | N-A | — | none — no shared state beyond the collector and the keep list, both edited by hand |
| Misuse & abuse | Specify | No | UFR-4 (weakening a flaky test), UFR-5 (unevidenced deletion), UFR-7 (no test-lens receipt) |
| Reach (i18n / a11y) | N-A | — | no user-facing surface |
| Wording & tone | Specify | No | the FR-9 receipt fields and the PR-body classification line are hand-written; no fixed phrases |
| Workflow shape | Specify | No | keep-list stamp before delete-on-contact; cut list's evidence re-run before any cut (FR-14) |
| Placement & prominence | Specify | No | receipts and classifications in the PR body; flake notes and the hand count on the collector |
| Limits & defaults | Specify | No | 17.4% baseline, thirty-day second withdrawal, 30-day restore-by cap |
| Tier & access boundaries | N-A | — | tiers held (Held and declined) |
| Visibility & disclosure | Specify | Yes | every skip and failure is in the hand-written receipt (FR-9) (Non-functional: nothing degrades invisibly) |
