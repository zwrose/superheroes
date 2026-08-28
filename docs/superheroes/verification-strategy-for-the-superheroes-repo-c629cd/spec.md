---
superheroes: doc
schemaVersion: 1
docType: spec
workItem: verification-strategy-for-the-superheroes-repo-c629cd
issue: 1105
size: medium
status: approved
gates: {review: passed}
producedBy: "the-architect@0.31.0"
created: "2026-08-23"
updated: "2026-08-28"
---
# Verification strategy for the superheroes repo: can-bite retention, path-placed tiers, one Python, review-carried authoring rules

## Purpose

The superheroes repo is written almost entirely by builder agents, and its test suite has grown to about 12,500 cases and 1.8 lines of test per line of product code. The CI gate went from 20 seconds to over 5 minutes in ten weeks, and builders run the whole suite locally on top of that — several times per change.

The investigation for [#1105](https://github.com/zwrose/superheroes/issues/1105) (frozen record: `investigation-record.md` beside this file) found that in the repo's entire history only four pre-existing test files ever caught a change they did not author at CI, and all four were consistency rails; that most CI reds are a builder's own new test failing on first push; that real defects are found in the field, not by tests; that three different Python versions are in play with nothing checking they agree; and that six known ways a local pass can lie have no mechanical alarm.

This spec sets the owner's verification policy for this repo: what a test must do to stay, where and when each kind of test runs, how flakes and interpreter drift are handled, what the review crew enforces on new tests, and the instruments that measure whether the policy is working. It changes no code and deletes no test by itself — every change rides a proposed derived change that a later session routes to an issue on the owner's word.

## Who it's for

- **The owner** — waits on the gate before merging and carries the escape risk; wants the wait and the risk both smaller without trading one for the other.
- **Builder agents** — run the local gate several times per build and author the tests; need one rule for what to write and one command that says "ready to push".
- **Reviewers and vets** — need findings they can grade, so the practice changes at review time rather than in prose.
- **The advisor** — needs a standing measurement to know whether the policy raised or lowered escapes, and a ledger every cut must name.

## Functional requirements

### Retention — a test earns its keep

**FR-1.** The verification policy shall remove a test only on evidence that the test is incapable of failing on a defect in what it claims to prove ("cannot bite") — with one exception, an owner-authorized flake removal under FR-26, which is recorded as an open coverage obligation, not a cut.
  - *Acceptance (rule):* a test is **shown to bite** by a recorded bite-proof (the thing it claims to prove is deliberately broken and the test goes red) or a recorded mutation kill; the bite-proof discipline is the repo's existing one [cite: plugins/superheroes/rubric/bite-proof.md § The obligation].
  - *Acceptance (rule):* a test is **cannot-bite** (deletion evidence) when it stays green with its subject deliberately broken, or when it is structurally incapable of going red: no assertion about behavior, an assertion whose expected value is computed by the code under test, an assertion only on the call shape of a stub of an internal collaborator, or a mock of the unit under test itself.
  - *Acceptance (rule):* a test that only checks "does not raise" is **suspect, not structural** — it is cannot-bite only when a break-stays-green proof shows it.
  - *Acceptance (rule):* **unassessed tests are retained.** "Unassessed" is never deletion evidence.

**FR-2.** The verification policy shall exempt rails from any retention decision based on how often they have failed.
  - *Acceptance (rule):* a **rail** is a test whose subject is the checked-in tree rather than a tmp fixture — a doc↔code drift test, a census over source files, a manifest/registry consistency check, a guard over a declared invariant, or a test that reads repository configuration and asserts on it.
  - *Acceptance (rule):* a rail is never removed on a "has not failed" basis; a rail must still satisfy FR-1.

**FR-3.** The verification policy shall keep a named **rail inventory** listing every rail by file, and the "rails intact" measure shall be that inventory, never a file count.
  - *Acceptance (rule):* the first inventory is seeded from the investigation's pinned rail set (`rail-census-v3` in the evidence bundle, 53 files) and corrected by the advisor or the owner where a reader disagrees; an inventoried file removed from the suite is a defect unless the removal carries FR-1 cannot-bite evidence and the owner's recorded approval.
  - *Acceptance (rule):* removing an inventory **entry** carries the same bar as removing the file — FR-1 cannot-bite evidence and the owner's recorded approval; moving a rail to the behavior lane carries the owner's recorded approval (cannot-bite evidence does not apply to a file that stays). De-listing is never a lighter path to the same end. Advisor corrections to the seed inventory cover additions and entry metadata only — never a removal or re-laning — and are recorded with why.
  - *Acceptance (rule):* a named edit takes a machine-checkable form — a structured record naming the entry, the reason, and what FR-3's bar requires for that change — for a removal, the cannot-bite evidence and the owner's approval; for a re-laning, the owner's approval — so the guard's green path is "every inventory change matches a well-formed named-edit record", not free prose. The record is committed with the change (beside the inventory), so the guard re-verifies it on every run — a body-only justification that can be edited after CI goes green is not the record.
  - *Acceptance (rule):* the rail inventory and the lane classification (FR-4) change only deliberately: a pull request that edits either names the edit and its reason in its body, and a guard fails when an inventory entry disappears or a rail moves to the behavior lane without such a named edit.

### Tiers — where and when tests run

**FR-4.** The verification policy shall define three tiers and two lanes plus an always-run set:
  - **Local** tier — the pre-push command a builder runs on their own machine.
  - **Merge** tier — the pull-request CI run that must be green before merge.
  - **Nightly** tier — a scheduled run that blocks nothing.
  - **Rail lane** — the rail inventory (FR-3); the rail lane is the **always-run set**: it runs on every Local-tier run regardless of what changed. A rail's surface is the checked-in tree, so rails carry no owned-paths record.
  - **Behavior lane** — every other test file, each carrying its **owned paths**: the product files it imports, reads, or exercises.
  - *Acceptance (rule):* every test file is in exactly one lane; a test file in no lane or in two lanes is a defect. The lane classification is versioned and under a guard that fails when a file is unassigned, doubly assigned, or is a behavior-lane file lacking its owned paths.
  - *Acceptance (rule):* an edit that narrows a behavior-lane file's recorded owned paths is a named edit (FR-3's machine-checkable form) — it may not ride unnamed in the pull request whose change it would exempt, and the classification guard fails on an unnamed narrowing.
  - *Acceptance (rule):* the four validators are not a lane — they run on every Local-tier run, whatever the lanes do.

**FR-4b.** The verification policy shall carry a written risk profile that names, per area of the product, the depth of proof required, and the review crew shall grade a change's proof depth against it.
  - *Acceptance (rule):* the risk profile in this spec (§ Risk profile) is the normative table of areas; every area names a depth from the depth vocabulary.
  - *Acceptance (rule):* a change in a Full- or Medium-depth area whose pull request adds or changes behavior without proof at that row's depth — including the refusal, failure, or seam arm the row names — is a review finding; a Light-depth area is never held to a higher bar; an area no row names is graded at Medium until a row is added by named edit.
  - *Acceptance (rule):* this rule rides the same enforcement machinery as FR-18a–f: the calibration carries it with a named example finding, the rule-set drift check (FR-18g) covers it alongside the six, and the P5 change delivers it.
  - *Acceptance (rule):* the risk-profile table changes like the rail inventory (FR-3): this spec is its one home, an edit is a named edit, and lowering any row's depth carries the owner's recorded approval. Any edit that reduces what the table demands — removing a row, blanking or lowering its depth cell, or narrowing its Area text so it no longer covers what it covered — carries the same bar as lowering: the owner's recorded approval; no edit shape is a lighter path to the same end. A change editing the risk-profile table is never eligible for a lane without a vet (UFR-5's guarantee, applied identically), and the vet checks the owner approval behind any reducing edit.

**FR-5.** Once selection is enabled (FR-10), the Local tier shall run, for a change touching only `.py` files: the four validators, the always-run set, every changed test file itself, and every behavior-lane test whose owned paths intersect the change.
  - *Acceptance (Given-When-Then):* Given a change touching only `.py` product files, when the builder runs the local gate, then the four validators run, every rail runs, every behavior test owning a touched path runs, and the receipt names the behavior tests that were skipped with the reason "no owned path changed".
  - *Acceptance (Given-When-Then):* Given a change that edits a behavior-lane test file, when the builder runs the local gate, then that test file itself runs, whatever its owned paths say.

**FR-6.** When a change touches any file that is not a `.py` file — a skill, rubric, agent, reference or other markdown file, a JSON manifest, a workflow — the Local tier shall run every lane in full ("fail-open to full").
  - *Acceptance (Given-When-Then):* Given a change touching `plugins/superheroes/skills/x/SKILL.md` and one Python file, when the builder runs the local gate, then the full suite runs and the receipt reads "full — non-Python change".
  - *Acceptance (rule):* the trigger is by file extension, not location: a `.py` script under `.github/scripts/` selects by owned paths like any other Python file; its accompanying workflow `.yml` triggers fail-open.

**FR-7.** The Merge tier shall run every lane in full on every pull request, as CI does today [cite: .github/workflows/ci.yml § Run plugin + band-eval tests].
  - *Acceptance (rule):* a green pull-request CI run is the merge receipt for that commit; nothing in this policy reduces what CI runs.

**FR-8.** The Nightly tier shall run every lane in full and the advisory instruments (FR-19–FR-22, the vitals record running nightly per FR-22).
  - *Acceptance (rule):* the nightly receipt lists every lane and instrument as executed with its result; a nightly that did not complete is reported as such (UFR-3), never as a pass.

**FR-9.** Every local-gate receipt shall be written by the gate run itself — never typed by a builder — and shall carry: a run-log identifier traceable independently of the receipt, the exact source state verified (a commit identity when clean, else a tree identity that never equals a commit), the lanes that ran, the lanes and tests skipped with reasons, what selection would have skipped while observation mode is on (FR-10), the lane-classification version, the interpreter version the run actually executed on, the result, the attempt number and — when an earlier attempt of the same source state was red — which tests failed in it, and the wall time.
  - *Acceptance (rule):* this obligation attaches when the P3 gate driver ships — the receipt is that driver's own output, never a standalone build; until then the four-validator gate and today's hand-typed practice continue.
  - *Acceptance (rule):* a "local gate passed" claim missing any field, whose source identity differs from the pushed commit, whose run-log identifier does not resolve to a run producing that receipt, whose executed interpreter differs from the pin (FR-12), or whose named lane-classification version is not the version in force for that source state, is unreceipted (UFR-2).
  - *Acceptance (rule):* a receipt travels in the pull request body at handback — there is no live receipt feed to the ledger; the ledger reads handed-back receipts at its nightly refresh. Local flake visibility (FR-23) is therefore computed over **handed-back** local-gate receipts, and local runs that never reach a handback are an accepted invisible floor, as the investigation's catch numbers already are. The observation count (FR-10) and the false-negative record (FR-11) are computed at CI per FR-10 — handed-back receipts corroborate them, never count. The attempt-number and prior-red fields are derived from the gate's own run log for the same source state.

### Selection safety

**FR-10.** Before Local-tier selection is first used to skip anything, the policy shall run it in **observation mode**, counted where every run is visible red or green: for each pull-request CI run (which always runs full, FR-7), the ledger computes — under the classification version in force when the run executed, never a later one — what Local-tier selection *would* have skipped for the run's changed files, and records that set immutably with the run, until at least 30 such runs in which selection would have skipped at least one test have completed with zero failures falling in a would-have-been-skipped test.
  - *Acceptance (Given-When-Then):* Given observation mode is on, when a pull-request CI run fails in a test selection would have skipped for that change, then the clean-observation count resets to zero and the classification is corrected before counting resumes; a run in which nothing would have been skipped does not count.
  - *Acceptance (rule):* the observation count and the false-negative record (FR-11) are computed by the ledger's nightly refresh (FR-19) — the named artifact both thresholds count against; local receipts' would-have-skipped fields (FR-9) are corroborating evidence, never the counted population (a red local run is fixed before handback and never observed, which is why the count lives at CI).
  - *Acceptance (rule):* if 30 clean observations are not reached within 30 calendar days of observation mode starting (the day count does not reset when the observation count resets), the advisor brings the owner a decision: enable on the evidence so far, extend, or abandon selection.
  - *Acceptance (rule):* selection is enabled — observation mode to live — by the owner's recorded approval on the advisor's presentation of the 30-clean-run record; the enablement date and approver land in the ledger.

**FR-11.** If the Merge or Nightly tier reddens in a test the Local tier skipped for that change (a **false negative**), then the Local tier shall run every lane in full until the classification is corrected and replayed against the missed change.
  - *Acceptance (rule):* a false negative is detected mechanically — a Merge or Nightly red in a test the ledger's recorded would-have-skipped set (FR-10) or the change's own handed-back receipt shows the Local tier skipped for that change.
  - *Acceptance (rule):* the correction is **replayed** by running the corrected classification against the missed change's file set and showing it now selects the reddened test; the ledger records the replay (change, classification version, selected test). The suspension is lifted by the advisor or the owner recording that evidence — never by the author of the misclassified change — and the receipt cites the lifting record.
  - *Acceptance (rule):* a second false negative within 30 days keeps selection suspended until the owner decides; the receipt reads "full — selection suspended (false negative on <change>)".

### One Python

**FR-12.** The verification policy shall pin exactly one Python version in exactly one home, and every place that runs Python for this repo — CI, the calibrated local verify command, the calibration environment, dispatched work orders, and the documented local gate — shall read that pin rather than name a version or an interpreter path.
  - *Acceptance (rule):* today three versions are in play — `/usr/bin/python3` at 3.9.6 in the documented gate and 3.12 in CI [cite: CLAUDE.md § The full suite is CI's receipt], plus 3.14.6 in the project's out-of-repo calibration environment (investigation record §0.7); after this policy, a validator-step check at CI — running before any test, per UFR-8 — fails when any in-repo home names a version that differs from the pin or names an interpreter by absolute path, and the local gate itself refuses to run when the out-of-repo calibration home disagrees with the pin — the check runs where the home is reachable.
  - *Acceptance (rule):* a single documented provisioning step — whatever tool implements it — provisions the pinned interpreter everywhere; the local gate never runs on the operating system's Python.
  - *Acceptance (rule):* if the pinned interpreter cannot be provisioned on a machine, then the local gate refuses to run and says so — it never falls back to another interpreter. The refusal has a route: the builder parks with the refusal receipt, and the advisor routes it — fix the provisioning, or the owner records acceptance of CI as the sole gate for that change; the refusal is never a silent dead end and never a silent fallback.

**FR-13.** The verification policy shall disposition all six known false-green channels, each by name:
  1. **Interpreter skew** — removed by FR-12 (one pinned Python everywhere).
  2. **Stale bytecode** — dissolved by FR-12: the gate never runs on the operating system's Python, whose out-of-tree cache created the channel; additionally, the machine-owned gate command (FR-9) carries the bytecode-safety flags, and the gate-command census fails when those bytecode-safety flags are **absent** — the same census that, per this rule's closing bullet, fails when a retry flag is **present** — one handler may serve more than one concern, and a channel may have more than one handler; each pairing is named.
  3. **Git identity in temp repos** — a census test fails when any test shells `git commit` in a fixture repository without inline identity.
  4. **Engine binaries assumed on `PATH`** — a census test fails when a test invokes an engine binary without a declared skip condition.
  5. **A harness that pre-satisfies a gate** — becomes a written practice rule in the review rubric via the proposed change P5: the rule requires that at least one verification path exercise the real entry point without the gate pre-satisfied, and the pull request body names that path (the command and its run reference) — the named field the vet grades. (No such rule exists today; the investigation found all six channels living only in memory notes or a documented flag.)
  6. **A sanitized view that strips a file a seat needs** — becomes a written practice rule the same way: the rule requires reading the view's stripped-file list before dispatch and disclosing any missing input to the seat, and the dispatch's record (or the pull request body) carries an affirmative entry either way — "stripped-file list read; no needed input missing" when nothing relevant was stripped, or the missing-input disclosure when something was — so a skipped check is distinguishable from a clean one; that entry is the named field the vet grades. Either channel's named field absent from the handback is treated as no receipt — the vet returns it (UFR-2's rule); in a lane with no vet, the ledger's nightly refresh performs the presence check and records an absence as a policy violation (UFR-2's fallback).
  - *Acceptance (rule):* each channel above is traceable to at least one named handler — a requirement of this policy, a census test, or a rubric rule the change-set delivers; a seventh channel discovered later gets the same treatment before it is relied on as "handled".
  - *Acceptance (rule):* the census also fails when a retry or rerun flag appears in any gate command — the gate-weakening channel FR-24 forbids.

### Deletion and burndown

**FR-14.** The verification policy shall proactively delete only cannot-bite tests (FR-1), each deletion carrying its evidence.
  - *Acceptance (rule):* a first cut list is produced by the proposed change P7; a deletion without structural or demonstrated cannot-bite evidence is a finding (UFR-5).
  - *Acceptance (rule):* cannot-bite evidence is verified the way bite-proofs are: independently re-run at verification, never accepted from the deleting party's own assertion [cite: plugins/superheroes/rubric/bite-proof.md § Who owes what].

**FR-15.** When a builder makes an intentional edit to a test file that is not mechanical-only, the builder shall bring that whole file to standard in the same pull request: no cannot-bite case remains, and no count pin or byte-pinned prose assertion re-states a fact a rail already guards (each such pin is replaced with a read of the authoritative home).
  - *Acceptance (Given-When-Then):* Given a builder edits a test file to add a behavior test, when the pull request is reviewed, then no cannot-bite case remains anywhere in that file and no pin duplicates a rail-guarded fact; the whole touched file is in review scope, not only the changed lines.
  - *Acceptance (rule):* while a removal freeze is in force (UFR-6), this obligation is suspended: the builder records the file as burndown debt instead of removing, and no FR-18f finding is raised.

**FR-16.** Where a pull request's only changes to a test file are mechanical — a rename, a formatter's output, a codemod, a dependency update — FR-15 shall not apply to that file, and the pull request shall list the file as burndown debt.
  - *Acceptance (rule):* the reviewer verifies mechanical status from the diff; a builder that later edits the file intentionally pays its debt then.

**FR-17.** The verification policy shall defer any bulk removal of **bite-capable** tests — a change whose primary purpose is removing bite-capable tests from files it does not otherwise touch — until the ledger (FR-19) has at least 45 complete ledger days. Cannot-bite deletions carrying FR-14's evidence (the P7 cut list) are not bulk removal and are not deferred by this rule.
  - *Acceptance (rule):* a complete ledger day is a calendar day the nightly ledger recorded in full; no proposed change carries bulk removal before that checkpoint; the checkpoint is a named item whose first line states the number of complete ledger days available.
  - *Acceptance (rule):* the checkpoint is decision-only: re-opening bulk removal of bite-capable tests is an owner decision that amends FR-1 by named edit — until such an amendment, FR-1's two grounds remain the only removal paths.

### Authoring rules — carried by review

The review crew's test lens is the enforcement point for the rules below; each finding names the test and the rule, and a builder resolves every finding before handback. The lens already exercises a mutation-survival judgment on changed tests [cite: plugins/superheroes/agents/test-reviewer.md § Mutation-survival lens]. Three integrity rules govern the enforcement point itself, and they apply at each review lane's own enforcement point as review-discipline defines it — the panel plus the advisor's vet in the full lane; the one independent cross-vendor reviewer's receipt in the light and micro lanes, which have no panel (and micro no vet):

- **Where each rule is checked follows where its evidence lives.** A rule whose evidence is in the diff is the test lens's; a rule whose evidence lives outside the diff (a receipt in the PR body, a ledger listing) is checked by the advisor's vet, and the calibration names, per rule, which stage carries it. The review seat never asserts a receipt is missing — the body is not among its inputs [cite: plugins/superheroes/rubric/bite-proof.md § Who owes what].
- **The policy's own detectors are bite-proofed.** Every guard, census, and drift test this policy introduces (FR-3, FR-4, FR-12, FR-13), and the ledger's classifier (FR-19) — whose classification rules and infra-signature list are themselves versioned in the nightly record and change only by named edit, and whose bite-proofing is per class: one seeded specimen per FR-19 class, each classified correctly — and one per branch where a class's rule is a disjunction, whichever class that is (the flake class's four observation paths, FR-23, and validator-catch's two arms alike) — carries a bite-proof specimen — a seeded violation it demonstrably flags — before it is relied on; each findings-raising rule below (FR-18a–d, FR-18f) names, in the calibration that carries it, one concrete example finding it would raise. FR-18e is a prohibition and instead names the finding it bars.
- **The rule set is versioned, drift-guarded, and named in the receipt.** The test-lens calibration carrying these rules bears a version; a review receipt names that version, and a receipt naming a stale version — or none — does not satisfy UFR-7. A version bump is not the guard: a drift check, itself bite-proofed, fails when the calibration no longer carries every rule FR-18a–f names, FR-4b's depth-grading rule, or the two practice rules FR-13 channels 5–6 name (which are vet-carried, per the stage rule) — so a weakened rule set is red however its version reads.

These three integrity rules are jointly **FR-18g**: P5 delivers them with FR-18a–f, and the encoding and drift check cover them by that number.

**FR-18a (no cannot-bite tests).** When a pull request adds a cannot-bite test (FR-1), the test lens shall raise a finding.
  - *Acceptance (rule):* the finding names the structural class — assertion-free, tautological, mock-shape-only, or mocks-the-unit.

**FR-18b (no duplicate pins).** When a pull request adds a count pin or a byte-pinned prose assertion for a fact that a rail already guards, the test lens shall raise a finding naming the rail.
  - *Acceptance (rule):* a pin of a fact no rail guards is not a finding under this rule.

**FR-18c (rails are declared).** When a pull request adds a rail (FR-2) that is not declared as such in its name or top-level description, or is absent from the rail inventory (FR-3), the test lens shall raise a finding.
  - *Acceptance (rule):* the pull request body carries the rail's bite-proof receipt; the **vet** — not the lens — returns a pull request whose body lacks it (the preamble's stage rule). In a lane with no vet, the ledger's nightly refresh checks the merged change's body for the receipt (UFR-2's fallback), recording its absence as a policy violation.

**FR-18d (fixes name what they fix).** When a pull request whose purpose is a fix or revert of behavior that landed on the main branch does not name the change it corrects, the review crew shall raise a finding at the stage the calibration assigns (the naming is visible in the PR itself).
  - *Acceptance (rule):* "fix" here means a correction to merged behavior, not mid-build design tightening; a fix PR names the merged change or states that the defect pre-dates any single change — and a pre-dates claim is checked by the vet against the history before it discharges this rule (it still counts as unlinked in the ledger, FR-19).

**FR-18e (no proof-mass ratio).** The verification policy shall not impose a numeric ceiling on the share of a pull request's added lines that are test code.
  - *Acceptance (rule):* no review seat raises a finding on test share alone.

**FR-18f (burndown when touched).** When a pull request makes an intentional edit to a test file that still contains cannot-bite cases or rail-duplicating pins after the edit, the test lens shall raise a finding (FR-15), except where this pull request's own changes to that file are mechanical-only (FR-16) or a removal freeze is in force (UFR-6) — a prior wave's debt listing never exempts an intentional edit, which pays the debt (FR-16).
  - *Acceptance (rule):* the finding names the remaining case or pin.
  - *Acceptance (rule):* the freeze exception's evidence (whether UFR-6's freeze is in force) lives outside the diff, so per the stage rule the **vet** applies it: the lens raises the finding regardless, and the vet dispositions it as freeze-suspended when a freeze is in force.

### Instruments — measuring whether the policy works

**FR-19 (the ledger).** The Nightly tier shall maintain a standing catch/escape ledger that assigns every red CI run to exactly one class per failing item — an **item** being a failing test file for a test-step red, else the failing step — by **deterministic rules applied first-match in this order**, so no class is ever assigned by the party whose change went red: **infra** (a non-test failing step with a named infrastructure signature), **cancelled-superseded** (cancelled by the concurrency group when a newer run superseded it), **release-gate-expected** (a red of the pre-merge release-bump gate on a release branch still accumulating commits — deterministic by construction), **flake** (FR-23's definition), **validator-catch** (a validator or non-pytest gate step exited non-zero and no named infrastructure signature matches the failure text), **birth-red** (the change touched the failing test file), **regression-catch** (it did not), **unattributable** (no rule above matched — kept, never silently dropped). It also records as an **escape candidate** each fix or revert commit on the main branch that references a change merged within the previous seven days — the same mechanical rule the investigation measured the baseline with.
  - *Acceptance (rule):* the ledger's numbers are published in a tracking item's body, refreshed nightly; a regression-catch names the pre-existing test file and the change it caught.
  - *Acceptance (rule):* classification is per (run × item): a run with both its own red test and a genuine regression-catch records both rows, and birth-red never absorbs a catch. **Infra requires a non-test failing step with a named infrastructure signature in the failure text (matching the class rule above) — a builder cannot declare their own red run infra.** A hand override of any class may be made only by the advisor or the owner — never by the author of the change the row concerns — and is recorded with who and why. An override never clears a flake listing or lifts FR-24's block; only FR-24's dispositions do.
  - *Acceptance (rule):* the infra-signature list and the classification rules — the class predicates above **and** the escape-candidate detection rule — are protected artifacts: they change only by a named edit authored by the advisor or the owner — never by the author of a change whose red runs (or whose fixes) the edit would reclass. Each such edit is accompanied by a recorded replay over the trailing 60 days — **including** the provisional most-recent-seven-days (unlike UFR-6's rate, which excludes them: the freshest rows are exactly the ones a self-serving edit would target), and over the whole available history while the ledger is younger than 60 days — which existing rows the edit would reclass, and whose changes those rows concern — like FR-11's replay record; the edit's own replay record is the artifact the author-exclusion is checked against. Such an edit is never eligible for a lane without a vet (UFR-5's guarantee, applied identically): the vet checks the replay record, and the ledger's nightly refresh re-checks it after merge (UFR-2's fallback).
  - *Acceptance (rule):* the ledger also records each advisor dispatch (what, when), so FR-24b's no-other-dispatch audit is checkable against it. Flake listings arriving from non-CI observation paths (FR-23) enter the ledger as listings, not as run classifications — the classifier's domain stays red CI runs.
  - *Acceptance (rule):* the ledger also counts and publishes **unlinked fixes** — fix/revert commits referencing no merged change; when unlinked fixes outnumber linked escape candidates in the window, the escape rate is published as low-confidence and UFR-6 treats the window as insufficient sample. The most recent seven days are marked provisional.
  - *Acceptance (rule):* the reference FR-18d requires and the reference this rule detects are the same thing — a named merged change in the fix's commit subject or body — so a fix that satisfies FR-18d by naming the merged change is by construction a linked fix; a fix that instead states the defect pre-dates any single change names nothing and is counted as unlinked.
  - *Acceptance (rule):* the ledger is the **H4 validation** every proposed cut names: a proposed change that removes tests names UFR-6's escape-candidate **rate** as the bar it must not raise — the rate, never a raw count, is the measure everywhere in this policy.

**FR-20 (mutation sweep).** The Nightly tier shall run a mutation sweep over the Python product code — the product `.py` trees the four CI suites test — on the pinned interpreter, within a per-night budget stated in the nightly run's own configuration (P6 sets the first value; a change to it is a named edit), and publish, per planted defect, its subject file and whether any test detected it.
  - *Acceptance (rule):* the sweep is advisory; a surviving mutant in a file with a test is a candidate finding for the next intentional edit of that test, not a defect.
  - *Acceptance (rule):* an incremental run marks defects it did not re-evaluate as "not evaluated", never as detected; a night that exhausts its budget publishes a partial result marked as such.

**FR-21 (flake differential).** The Nightly tier shall run the suite once serially and once in parallel and publish the set of tests whose result differs.
  - *Acceptance (rule):* the differential is advisory, like every nightly instrument: a test that differs is recorded as a **candidate** flake that morning, its confirmation is the advisor's next dispatch, and it becomes a recorded, blocking flake (FR-23) only by the advisor's confirmation, made on gate-tier evidence — a red of the same test at the Local or Merge tier, or the advisor's own reproduction; a gate red is evidence for that confirmation, never an automatic listing. Promoting the differential itself to auto-blocking is a later owner decision (Constraints).
  - *Acceptance (rule):* candidates live in the ledger with a recorded-at time and exactly one eventual disposition — confirmed (→ FR-23), or withdrawn with the non-reproduction trace; a candidate undispositioned after three complete ledger days appears as overdue in every nightly report until it is dispositioned, and one overdue three further days becomes the advisor's next dispatch (at FR-24b's precedence) and is delivered to the owner as a pending decision. A candidate is never silently dropped.
  - *Acceptance (rule):* a differential-confirmed listing later observed red-then-green at CI joins FR-25's rate at that CI observation, once — the two populations never double-count one test's one incident.

**FR-22 (vitals trend).** The Nightly tier shall record the suite vitals — runtime, test count, skips, the fields the guardian sweep already defines [cite: plugins/superheroes/lib/guardian_vitals.py § suiteRuntimeSeconds] — every night, so a trend exists independent of the guardian sweep's own cadence; the project's history holds a single sweep record today (investigation record §4.9).
  - *Acceptance (rule):* the nightly record appends one entry per night; the guardian sweep keeps recording on its own cadence and reads the same trend; a report shows the delta against the previous entry, never "no movement" on a single sample.

### Flakes

**FR-23 (a flake is recorded when it is seen).** When a flake observation occurs — the same source state red and later green with no change, at any gate (a CI re-run, an identical-tree re-push, or a handed-back local-gate receipt whose prior-attempt field (FR-9) shows red-then-green on the same source state), or the advisor confirms a differential candidate (FR-21) — the ledger shall list the test as flaky at the moment the observation is seen: for CI, when the green run completes; for a local receipt, when it reaches handback (the receipt's attempt and prior-red fields are what make a local flake visible at vet time). The recorder is the instrument or the vet reading receipts and runs, never the builder.
  - *Acceptance (rule):* the listing names the test, the run, and the recorded-at time; no disposition relabels a red run green; a CI-observed flake first listed only at a nightly refresh when its green run completed earlier is a defect of the ledger.
  - *Acceptance (rule):* in a lane with no vet, a handed-back receipt showing red-then-green is read by the ledger's nightly refresh (the same fallback stage UFR-7 uses), and the listing made there is timely, not a ledger defect.

**FR-24 (a recorded flake blocks until dispositioned).** While any test is listed as flaky and undispositioned, no pull request shall merge, with exactly two exceptions: a pull request whose purpose is executing a disposition of one or more listed flakes, or repairing the flake-listing instrument (UFR-3) — it may merge while other listings remain open and names in its body each listing it dispositions or the instrument failure it repairs; and an emergency revert of a merged change carrying the owner's recorded approval. The block is repository-wide. A **disposition** is exactly one of: the flake fixed at its cause; the test removed with cannot-bite evidence (FR-14); or an owner-authorized removal under FR-26. An FR-26 decision to keep blocking or to fix by a stated route leaves the flake undispositioned until the fix merges. A later green attempt does not lift the block.
  - *Acceptance (rule):* the block has a named enforcement point: the advisor's vet checks the ledger's flake listing at vet time, and a removing or merging change's clearance is re-checked against the ledger at merge time (as UFR-6 already requires for freezes) — the merge-time re-check has two cases: when the advisor coordinates the merge, the advisor records it in the standing vet receipt on the pull request, the advisor's identity part of the record; when merge execution is delegated, the executor — never the author of the change being merged — records it in their own pull-request comment, their identity part of the record. In both cases the ledger's nightly refresh cross-checks the recorded identity against the change's authorship — identity resolves to the acting account and, where one account serves several principals, the named session or agent; a comparison the record cannot resolve is recorded as unverified, a policy violation to triage, never a satisfied check — and where neither record exists it performs and records the check after the fact (UFR-2's fallback); a merge outside the two exceptions while a listing is open is recorded in the ledger as a policy violation.
  - *Acceptance (rule):* if the flake listing is unreachable, stale, or marked partial (UFR-3) at vet or merge time, the merge parks until a complete listing can be read — the block fails closed, like UFR-6's insufficient-sample park, never open — except for a pull request repairing the listing instrument itself, which is the first exception: the repair path stays alive when the instrument is what broke. (An omission a complete-looking listing cannot show is guarded upstream: the classifier is bite-proofed per class — including the flake class — and its rows are never silently dropped, FR-19.)
  - *Acceptance (rule):* the disposition exception is per-purpose, not per-listing — with several flakes listed at once, each fix pull request merges under the others' open listings.
  - *Acceptance (rule):* a claimed exception is checked, never taken on the claim: an exception-claiming pull request is never eligible for a lane without a vet, whatever its size — it takes at least the lane whose vet performs this check (UFR-5's guarantee, applied identically), so the scope check always has a stage to run at and the block's repair path always has an eligible lane. The vet checks that the diff is scoped to the claimed disposition or repair — unrelated bundled changes are a finding and the exception does not apply. The ledger's nightly report lists every exception-claiming merge for audit, and the ledger's violation detector also fires when an exception-claiming merge's diff includes changes beyond the claimed purpose.
  - *Acceptance (rule):* there is no quarantine lane and no retry-on-failure setting at any tier; a builder that weakens an assertion or adds a skip to a listed flaky test gets a finding (UFR-4).

**FR-24b (a blocking flake is the advisor's next dispatch).** While a recorded flake is blocking merges, the flake fix shall be the advisor's next dispatch — no other build before it.
  - *Acceptance (rule):* the ledger shows, per blocking flake, the recorded-at time and the advisor as fix owner, and shows no other dispatch between record and fix dispatch.
  - *Acceptance (rule):* when more than one rule claims the advisor's next dispatch, blocking-flake fixes outrank overdue coverage restores (FR-26), which outrank differential-candidate confirmations (FR-21); ties break by recorded-at time.

**FR-25 (budget tripwire).** If the flake rate over the trailing 30 days — distinct CI-observed flake listings divided by completed CI executions, the same measure as the investigation's 0.30% — exceeds 0.5%, then the advisor shall bring the owner a decision, informed by the ledger's numbers. (Locally-observed and differential-confirmed flakes block individually under FR-24 but sit outside this rate, whose numerator and denominator must share a population to be reproducible.)
  - *Acceptance (rule):* 0.5% is set above the investigation's measured full-history flake rate (0.30% of executions) with ≈1.7× headroom; a breach is an owner decision, never an automatic relabel or a softened gate.
  - *Acceptance (rule):* an instrument never carries a decision itself — the advisor brings every owner decision this policy names (FR-10, FR-26, UFR-6 likewise).

**FR-26 (escalation).** If a blocking flake's cause is not isolated within one working day, then the advisor shall bring the owner a decision among: keep blocking; fix the cause by a stated route; or authorize removal — offered only for a test outside the rail inventory (FR-3), and only when the advisor's diagnosis evidence shows the nondeterminism lives in the test or its harness, not in the product.
  - *Acceptance (rule):* a red-then-green whose cause is in the product is a product defect — the advisor records a hand override reclassing it regression-catch (FR-19's override rule; never an automatic reclass), the merge block continues until the product defect's fix merges (that fix is the disposition), and removal is not offered. For an inventoried rail the removal option does not exist.
  - *Acceptance (rule):* an owner-authorized removal is recorded in the ledger as an open coverage obligation with a restore-by date the owner sets in the same decision, at most 30 days out; a restore-by date passing unmet is marked overdue nightly, restoring the coverage becomes the advisor's next dispatch, and the advisor brings the owner a decision within one working day.
  - *Acceptance (rule):* the decision, its date, and the diagnosis evidence are recorded on the flake's item — the evidence in re-runnable form; a removal executed on evidence that does not reproduce is recorded as a policy violation.

## When things go wrong (significant unhappy paths)

**UFR-1.** If the Local tier cannot classify a change — a touched path no lane owns, a test file outside the classification, a classification version the receipt cannot name — then the Local tier shall run every lane in full and say so in the receipt.
  - *Acceptance:* Given a new test file not yet in the classification, when the builder runs the local gate, then the full suite runs and the receipt reads "full — unclassifiable (<reason>)".

**UFR-2.** Once FR-9's obligation has attached (the P3 driver shipped), if a builder claims the local gate passed without a receipt carrying FR-9's fields for the handed-back source state, then the vet shall treat the claim as no receipt; before then, the vet holds local-gate claims to today's practice — the commands and their quoted output named in the PR body.
  - *Acceptance (rule):* in a lane with no vet, this check has the same fallback stage as UFR-7's: the ledger's nightly refresh resolves the merged change's gate receipt (identifier, source state, interpreter-vs-pin) and records a failure as a policy violation in the next nightly report.
  - *Acceptance:* Given a PR body says "local gate green" with no receipt or a receipt for a different commit, when the advisor vets, then the PR is returned for a receipt before any other vet step.

**UFR-3.** If the Nightly tier or any advisory instrument fails to run or completes only partially, then it shall record the failure in the tracking item and deliver a notification on the owner's reading surface by the start of the owner's next working day. The **ledger's refresh runs isolated from the sweeps** — a mutation-sweep or differential overrun never stales the ledger — and only three consecutive stale nights **of the ledger itself** revert the Local tier to running every lane in full.
  - *Acceptance:* Given the ledger did not refresh for three nights, when a builder runs the local gate, then the receipt reads "full — instruments stale since <date>".
  - *Acceptance:* Given a nightly failure, when the next working day starts, then the tracking item carries the dated failure record and the sent notification's time and channel — the record is the pass/fail check, independent of whether the advisor was around.

**UFR-9.** If the local gate cannot read any shared trust state it depends on — the selection-suspension flag (FR-11), the instruments' staleness (UFR-3), or the calibration home FR-12 has it check — then the gate shall run every lane in full and say so.
  - *Acceptance:* Given the ledger's record is unreachable from the gate, when the gate runs, then the receipt reads "full — trust state unreadable (<which>)", naming which of the three states could not be read.

**UFR-4.** If a builder weakens an assertion in, or adds a skip to, a test the ledger lists as flaky, then the review crew shall raise a finding — the lens flags the weakening it sees in the diff; the vet checks the ledger listing (the FR-18 stage rule); in a lane with no vet, the ledger's nightly refresh performs the listing check (UFR-2's fallback), recording a failure as a policy violation — and the change shall not merge until the flake is fixed at its cause.
  - *Acceptance:* Given `test_x` is listed, when a PR loosens its assertion, then the finding names the listing and the PR is blocked.

**UFR-5.** If a builder deletes a test as cannot-bite without the FR-1 evidence in the pull request, or removes or re-lanes a rail-inventory entry without what FR-3's bar requires for that change (evidence plus owner approval for a removal; owner approval for a re-laning), then the review crew shall raise a finding — the lens flags the deletion or de-listing in the diff; the vet checks the body's evidence, the owner's approval where FR-3 requires it, and independently re-runs the evidence (FR-14) — and the change shall not merge.
  - *Acceptance (rule):* a change that removes a test or edits the rail inventory is never eligible for a review lane without a vet — whatever its diff size, it takes at least the lane whose vet performs this check, so the independent re-run always has a stage to run at.
  - *Acceptance:* Given a PR removes a test with no bite-proof or structural evidence, when reviewed, then the finding names the test and asks for the evidence.

**UFR-6.** If the ledger's escape-candidate **rate** over the trailing 60 days exceeds the baseline of 17.4% of merged changes (87 candidates over 499 merges in the investigation's full-history window, by the same mechanical rule the ledger uses), measured over at least 100 merged changes, then all test removal shall halt — FR-14 deletions, FR-15 burndown (suspended into debt), and the FR-17 checkpoint — and the advisor shall bring the owner the ledger for a decision. An owner-authorized flake removal under FR-26 is exempt: it is a coverage obligation, not a cut.
  - *Acceptance:* Given the trailing rate reads above the baseline on ≥100 merges, when the advisor next vets a change that removes tests, then the vet parks it pending the owner's decision; a breach freeze lifts only by the owner's recorded decision.
  - *Acceptance:* Given fewer than 100 merged changes in the window (or an unlinked-fix majority, FR-19), then the ledger reads "insufficient sample" and the same park applies — **except** cannot-bite deletions carrying FR-14's independently re-run evidence (the P7 class): their safety argument is structural, not statistical, so they proceed during the ledger's warm-up by the owner's ruling (2026-08-28). That ruling is this carve-out's authority — it amends UFR-6's own insufficient-sample park; FR-17's separate exemption (cannot-bite cuts are not bulk removal) is a different rule and is unchanged by it. Once the window has a readable rate, a breach parks them like everything else.
  - *Acceptance (rule):* the trailing 60-day window excludes the ledger's provisional most-recent-seven-days (FR-19), so the rate is read over settled rows only.
  - *Acceptance:* a removing change's clearance is re-checked against the ledger at merge time, not only at review.

**UFR-7.** If any pull request reaches handback without a review receipt showing the test lens ran on the handed-back source state under the current rule-set version, then the vet shall treat the pull request as unreviewed under the existing rule [cite: plugins/superheroes/rubric/review-discipline.md § The rule — no unreviewed PRs].
  - *Acceptance:* Given a PR body with no test-lens receipt, or a receipt naming a stale or absent rule-set version, when vetted, then it is returned.
  - *Acceptance (rule):* like the gate receipt (FR-9), a review receipt is written by the review run itself and carries a run identifier traceable independently of the receipt; a receipt whose identifier does not resolve to a review run producing it is no receipt — a hand-typed body line never satisfies this rule.
  - *Acceptance (rule):* in a lane with no vet, the check still has a stage: the ledger's nightly refresh resolves every merged change's review-receipt identifier and checks the resolved run's source state and rule-set version against the merged commit (UFR-2's split, applied to review receipts); an identifier that does not resolve, a mismatched source state, or a stale rule-set version is recorded as a policy violation in the next nightly report — detected after merge rather than never.

**UFR-8.** If the pinned Python version and any **in-repo** home that should read it disagree (FR-12), then CI shall fail at the validator step before any test runs; the out-of-repo calibration home is the local gate's own check (FR-12), not CI's.
  - *Acceptance:* Given a PR edits the documented local gate to name a version, when CI runs, then the drift validator fails with the two disagreeing values.

## Non-functional requirements

- **Local loop time:** the local gate completes in under 2 minutes at the median, measured from handed-back receipts over the trailing 20 such receipts for `.py`-only changes, once selection is enabled (today the full pytest step is 308 s at the CI median; the investigation did not measure local runtime).
- **Nothing degrades invisibly:** every skip, every fail-open, every suspended selection, every stale instrument appears in the receipt the owner reads; a silent fallback is a defect.
- **Escape rate not raised:** the ledger's escape-candidate rate stays at or below UFR-6's baseline, on UFR-6's window and sample floor.
- **Reproducibility:** a local-gate receipt names the same interpreter version as the pin CI provisions from (FR-12) and the classification version it selected with.

## Definition of done / success

The policy is done when a builder can run one local command that meets the local-loop bar on a `.py`-only change and says exactly what it ran and skipped and why; when the same Python runs everywhere and a mismatch fails CI; when the review crew enforces the six authoring rules (five raising findings, FR-18e barring one) and grades proof depth against the risk profile (FR-4b); when a nightly ledger, mutation sweep, flake differential and vitals trend exist and publish numbers the owner can read; and when, once UFR-6's window and sample floor are satisfied, the owner can look at the escape-candidate rate and see it did not rise.

## Risk profile (normative)

Depth vocabulary: **Full** = behavior tests including every refusal and failure arm, plus a rail or guard where the row names an invariant, each guard bite-proofed; **Medium** = behavior tests in the layer that owns the behavior, including the stated failure paths; **Light** = the fastest check that can observe the behavior.

When a change maps to more than one row, the deepest applicable row governs. Row 5 covers presentation only — a surface the policy itself reads as trust state (a ledger listing, a receipt, a gate result) is row 2, whatever it looks like.

| # | Area | Consequence if broken | Depth of proof |
| --- | --- | --- | --- |
| 1 | Destructive filesystem and git operations — worktree add/remove/reap, cleanup, anything that deletes or rewrites files outside its own scratch | an agent's or the owner's uncommitted work is destroyed | Full — every refusal path proven, including the guard's own refusal arms |
| 2 | Owner authority and gate integrity — merge/force-push refusals, gate writes and approvals, receipts | something merges, releases, or reads as approved without the owner; a claim passes without its receipt | Full — refusal arms proven |
| 3 | Engine dispatch and transport — dispatch, couriers, report channels, salvage | delivered work is lost, truncated, or misattributed; a forfeit reads as a result (a recurring class in the escape ledger, record §4.7) | Medium, plus a round-trip or contract test at every transport seam |
| 4 | Calibration and configuration resolution — calibration, storage modes, seat and model maps | a session silently runs against the wrong configuration, or a refusal masquerades as an uncalibrated result | Medium, including the unreadable and fail-closed paths |
| 5 | Reporting and display — views, summaries, status output | a human reads something stale or mislabeled; recoverable on sight | Light |

## Proposed derived change-set

Filed as issues only on the owner's word, in a later session. Each row carries its size; a change that alters gate time also carries its predicted effect on **local-gate minutes per build iteration** (only P3 does), and every test-removing change names its H4 validation.

| # | Change | Predicted effect | H4 validation |
| --- | --- | --- | --- |
| P1 | One Python, one pin, drift-guarded (FR-12, UFR-8) | removes the interpreter false-green channel; no CI-minute change; small | none needed — no test removed |
| P2 | Catch/escape ledger and the flake machinery it carries (FR-19, FR-23–FR-26, UFR-3, UFR-6) | advisory instrument + the blocking-flake protocol; small–medium | is the validation |
| P3 | Lane classification + observation mode + local-tier selection + the gate driver and its receipts (FR-4–FR-11 except FR-4b, which P5 delivers; UFR-1, UFR-9) | local gate (full pytest step: 308 s at the CI median; local runtime unmeasured) → <2 min per iteration on Python-only changes; CI unchanged; medium; depends on P2 | no test removed; selection safety carried by FR-10's observation mode and FR-11's false-negative suspension |
| P4 | Tripwire censuses — git identity, engine binaries, gate-command retry/bytecode flags (FR-13) | small; the gate-command census's subject is P3's driver, so that census lands with or after P3 (the git-identity and engine-binary censuses stand alone) | none needed |
| P5 | Test-lens calibration carrying FR-18a–f, the FR-18g integrity rules (stage rule, detector bite-proofing, rule-set versioning + drift check), FR-4b's depth grading, and UFR-2/4/5/7's vet checks, plus the two practice rules FR-13 channels 5–6 name | small; rubric surface | none needed |
| P6 | Nightly instruments — mutation sweep, flake differential, vitals trend (FR-20–22) | nightly workflow; medium | none needed |
| P7 | First cut list + rail inventory (FR-3, FR-14) — the 33 no-raise tests assessed, the one golden-fixture file, the pinned rail set confirmed | small; removals carry evidence | ledger escape rate not raised (UFR-6) |
| P8 | Bulk-removal checkpoint (FR-17) | filed at ≥45 ledger days | ledger |
| — | Candidate, not derived: skill evals over the markdown half (Anthropic `claude plugin eval`, blind comparator) — real per-case token cost; the owner approves its spend separately | | |

## Assumptions & dependencies

- The investigation record beside this file is the evidence this policy stands on; its numbers are fresh as of 2026-08-23.
- The review crew's test lens is the enforcement point and can be calibrated per project; where a rule needs evidence outside the diff (a bite-proof receipt, a ledger listing), the PR body carries it and the vet checks it.
- The review lens's shipped base rules today confine findings to changed lines, and calibration cannot override that — so FR-15/FR-18f's whole-touched-file check is carried by the advisor's vet until the plugin ships its binding project-rules and scope-override capability (owner-ruled 2026-08-28); the calibration names the vet as that stage, per FR-18g's stage rule.
- The one-home-per-fact convention and its drift tests are the repo's own [cite: CONVENTIONS.md § exactly one authoritative definition]; this policy builds on them, never beside them.
- `uv` (already a CI dependency) is available to builders; the investigation found the viable mutation tooling requires a modern interpreter (record §3 A2), which the FR-12 pin satisfies.

## Constraints

- Zero code, test, script or workflow changes ship from the discovery that produced this spec; every change rides a proposed derived change.
- Nothing in this policy reduces what CI runs on a pull request.
- The owner approves any instrument's promotion from advisory to blocking, on evidence, later.
- Cross-repo references are repo-qualified links, never bare numbers.

## Out of scope

- Building any proposed change.
- Promoting universal rules into shipped plugin surfaces (the plugin-harvest track) and the consumer-facing frameworks discussed on 2026-08-22.
- The three-way adoption assessment (weekly-eats × superheroes-as-plugin × superheroes-as-project).
- Sharding CI across a runner matrix (may be revisited if the nightly tier gets heavy).
- Skill evals (named as a candidate; not derived).

## Glossary

- **Can bite / bite-proof / cannot-bite** — a test can bite if it fails when what it guards breaks; a bite-proof is the recorded demonstration; cannot-bite evidence is the recorded failure to fail.
- **Rail** — a test whose subject is the checked-in tree (drift, census, consistency, guard), as opposed to a behavior test over a tmp fixture.
- **Owned paths** — the product files a behavior test imports, reads or exercises; the basis for selection.
- **Fail-open to full** — when selection is unsure, run everything.
- **Observation mode** — selection computes what it would skip but skips nothing, until trusted.
- **Birth-red** — a PR's own new or modified test failing at CI.
- **Escape candidate** — a fix or revert naming a change merged within the previous seven days.
- **Mechanical wave** — a rename, formatter, codemod or dependency update touching test files without changing what they prove.
- **Byte-pinned prose assertion** — a test asserting that an exact literal of six or more words appears in a document or output.
- **Count pin** — a test asserting an exact count (`len(...) == N`) of things whose authoritative home is elsewhere.
- **Non-regression validation (H4)** — the named evidence a proposed cut must carry that the escape-candidate rate did not rise; "H4" is the investigation's hypothesis that suite density explains the low escape rate, which could not be refuted.
- **Complete ledger day** — a calendar day the nightly ledger recorded in full.
- **Working day** — a weekday on the owner's local calendar; a "one working day" deadline runs from the triggering event to the same clock time on the next weekday.
- **Owner's recorded approval** — a decision the owner stated themselves, recorded on the artifact it authorizes (the pull request, issue, or inventory record) as the owner's own comment or a quoted, linked owner message; a paraphrase typed by the party the approval benefits, with no traceable owner utterance, is not one.

## Amendments

- **2026-08-28** (owner approval): the owner approved this spec at the acceptance sitting — items 1–12 of the acceptance brief owner-read (this spec's observation threshold stays at 30: its selection gates the local tier only, CI unchanged); the craft layer accepted on the review record (receipts on [#1105](https://github.com/zwrose/superheroes/issues/1105)).
- **2026-08-28** (review-spec rounds 2–3): FR-24's exception rule hardened — checked never claimed, positive lane routing (at least the vetted lane), diff-scope check, ledger audit of exception merges; FR-13 channels 5–6 given affirmative named fields; the merge-time re-check record defined with an independent executor; FR-4b bars every reducing edit shape and takes a vetted lane; FR-19's protected set names the escape-candidate rule with a replay record; P3/P4/P5 delivery rows disambiguated.
- **2026-08-28** (review-spec round 1, six-lens panel): FR-24's exceptions generalized to concurrent flakes and flake-listing-instrument repair (the fail-closed park keeps a living repair path); FR-9/FR-10's counted-population contradiction resolved toward CI; FR-17's checkpoint pinned decision-only (FR-1's grounds stay exclusive until an owner amendment); FR-26's product-defect arm rerouted through FR-19's override rule; the validator-catch class given a deterministic predicate; the three preamble integrity rules numbered FR-18g; authority seams closed (risk-row removal, infra-signature edits, owned-paths narrowing, override-vs-listing, no-vet-lane fallbacks for UFR-4/FR-18c, suspension lift, enablement flip); replay and false-negative detection made mechanical; the unprovisionable-interpreter refusal given a park route. Full round history in the review receipt.

## Coverage

| Area | Disposition | Show-it? | Where / why |
| --- | --- | --- | --- |
| Empty & first-run | Specify | Yes | UFR-1 (no classification yet → full run); FR-10 observation mode; P3's first receipt is shown |
| Invalid & malformed input | Specify | No | UFR-1 (unclassifiable change), UFR-2 (receipt missing fields) |
| Boundaries & limits | Specify | Yes | FR-10 (30 runs / 30 days), FR-17 (45 ledger days), FR-25 (0.5%) — the first breach of each is shown |
| Errors & failures | Specify | Yes | UFR-3 (instrument stale → full), FR-11 (false negative → suspended) — a suspended receipt is shown |
| Access & permissions | Specify | No | owner-only decisions: FR-10, FR-25, FR-26, UFR-6; instrument promotion (Constraints) |
| Duplicates & double-actions | Defer-to-build | No | a ledger refresh run twice produces one record per run; mechanism is the build's |
| Conflicting / simultaneous use | Defer-to-build | No | builders' local gates share only read-only trust state (UFR-9); each run's own state is per-machine, and the classification is versioned (FR-9) |
| Misuse & abuse | Specify | No | UFR-4 (weakening a flaky test), UFR-5 (unevidenced deletion), UFR-7 (no test-lens receipt) |
| Reach (i18n / a11y) | N-A | — | no user-facing surface |
| Wording & tone | Specify | Yes | receipt phrases are fixed, quoted exactly as their requirements state them: "full — non-Python change", "full — unclassifiable (<reason>)", "full — selection suspended (false negative on <change>)", "full — instruments stale since <date>", "full — trust state unreadable (<which>)", "no owned path changed"; shown on the first receipt |
| Workflow shape | Specify | No | P2 before P3 (selection needs the ledger); observation before selection (FR-10); ledger days before bulk removal (FR-17) |
| Placement & prominence | Specify | No | receipts in the PR body the owner reads; ledger numbers in a tracking item's body; owner decisions delivered directly (UFR-3) |
| Limits & defaults | Specify | No | defaults chosen by discovery: 30 observations / 30 days, 45 ledger days, 0.5% flake tripwire, 7-day escape window, one working day to isolate a flake |
| Tier & access boundaries | Specify | No | FR-4–FR-8 define the tiers; nightly blocks nothing until the owner promotes it |
| Visibility & disclosure | Specify | Yes | every skip, fail-open, suspension and stale instrument is in the receipt (Non-functional: nothing degrades invisibly) |
