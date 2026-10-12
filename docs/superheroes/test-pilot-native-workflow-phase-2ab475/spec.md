---
superheroes: doc
schemaVersion: 1
docType: spec
workItem: test-pilot-native-workflow-phase-2ab475
issue: 90
size: medium
status: approved
gates: {review: passed}
producedBy: "the-architect@0.2.0"
created: "2026-06-25"
updated: "2026-06-26"
---
# Showrunner Test-pilot Verification

## Purpose

Showrunner should be able to take a built work item and prove it is ready for human spot-check without requiring a separate manual test-pilot run. This work makes showrunner responsible for deciding whether browser-based verification applies before mark-ready. When it applies, showrunner owns the whole test-pilot verification job: derive the branch test plan, create or update the test-pilot scenarios and plan records, seed the planned data, drive the browser checks, fix and retry app bugs when possible, publish the plan and results, reset the seed data to a fresh spot-check baseline, and only then allow the PR to be marked ready. When it does not apply, showrunner records why and continues through the remaining non-browser gates.

## Who it's for

This is for maintainers using showrunner to move one approved work item to a PR that is genuinely ready for review. It is also for the human reviewer who opens that PR and expects either the manual spot-check plan, browser execution evidence, and seeded test state to be ready without extra setup, or a clear note that browser-based verification did not apply to this branch.

## Functional requirements

**FR-1.** After showrunner creates a draft PR for a built work item, showrunner shall own browser-applicability and any required test-pilot verification before mark-ready.
  - *Acceptance (Given-When-Then):* Given a built work item with a draft PR, when showrunner reaches the pre-ready verification point, then showrunner either records browser-based verification as not applicable or completes or parks the applicable work defined in FR-2 through FR-18 before the PR can be marked ready.

**FR-2.** Showrunner shall determine whether the current PR branch has browser-verifiable behavior before requiring a browser test plan.
  - *Acceptance (Given-When-Then):* Given the branch changes user-facing or runnable behavior that can be exercised in a browser, when showrunner starts test-pilot verification, then browser-based verification is classified as applicable.
  - *Acceptance (Given-When-Then):* Given the branch has no runnable browser surface, such as library, CLI, docs, or internal-only work, when showrunner starts test-pilot verification, then browser-based verification is classified as not applicable, the readout records the rationale, and showrunner may continue toward mark-ready through the remaining non-browser gates.
  - *Acceptance (rule):* A failed attempt to derive a browser test plan cannot by itself be treated as not applicable.

**FR-3.** When browser-based verification applies, showrunner shall derive a branch test plan from the current PR branch and the repo's test-pilot setup.
  - *Acceptance (Given-When-Then):* Given a draft PR branch with browser-verifiable behavior and available test-pilot setup, when showrunner starts test-pilot verification, then it records the test plan it derived for that exact branch state before creating spot-check artifacts, seeding data, or running browser steps.

**FR-4.** When browser-based verification applies, showrunner shall create or update test-pilot scenarios for the derived test plan.
  - *Acceptance (Given-When-Then):* Given the derived test plan includes browser-executed checks, when showrunner prepares those checks, then each check has planned scenarios available before any seed operation or browser step runs.

**FR-5.** When browser-based verification applies, showrunner shall create or update test-pilot plan records for every browser-executed part of the derived test plan.
  - *Acceptance (Given-When-Then):* Given the branch has no current plan record for part of the test plan, when showrunner prepares test-pilot verification, then it creates the missing plan record before browser execution begins.
  - *Acceptance (Given-When-Then):* Given the branch already has a plan record, when showrunner prepares test-pilot verification, then it updates or confirms that plan record against the current branch state before browser execution begins.
  - *Acceptance (rule):* A ready browser-verification outcome requires at least one browser-executed plan record for the branch.

**FR-6.** When browser-based verification applies, showrunner shall make the branch spot-check plan artifact available before browser execution begins.
  - *Acceptance (Given-When-Then):* Given the test plan and plan records are prepared, when showrunner is ready to run browser checks, then the reviewer can find the spot-check plan as a PR comment or named local fallback artifact.

**FR-7.** Showrunner shall seed the planned scenarios for each plan record before that plan record's browser execution.
  - *Acceptance (Given-When-Then):* Given a valid plan record with planned scenarios, when showrunner starts browser execution for that record, then the planned seed data is present before the first browser step runs.

**FR-8.** Showrunner shall execute every planned browser step in every plan record with a browser tool.
  - *Acceptance (Given-When-Then):* Given a seeded plan record, when showrunner executes that record, then each planned browser step has a browser-derived pass or fail result.
  - *Acceptance (rule):* A non-browser substitute cannot satisfy a planned browser step.

**FR-9.** Showrunner shall complete every plan record before the PR can be marked ready.
  - *Acceptance (Given-When-Then):* Given the branch has one or more browser-executed plan records, when showrunner evaluates readiness, then every plan record has a final passed result before the workflow can continue to mark-ready.

**FR-10.** If a browser execution pass reveals app bugs, showrunner shall collect the app-bug failures from that pass before starting fix work.
  - *Acceptance (Given-When-Then):* Given one or more browser steps fail because of app bugs, when showrunner starts fix work, then the results artifact records the failed steps and failure summaries being considered together.

**FR-11.** Showrunner shall attempt fixes for collected app-bug failures in bounded fix batches inside the same workflow run.
  - *Acceptance (Given-When-Then):* Given collected app-bug failures from a browser execution pass, when showrunner records a fix batch, then the results artifact names the app bug or failure symptoms the batch attempts to fix.
  - *Acceptance (rule):* A recorded fix batch includes a short description and the commit SHA or SHAs in the results artifact.
  - *Acceptance (rule):* A single fix batch may address more than one failed browser step.

**FR-12.** After applying a fix batch, showrunner shall rerun enough browser coverage to prove the test plan is current and passing.
  - *Acceptance (Given-When-Then):* Given a fix batch addresses failed browser steps, when showrunner retries browser execution, then it reruns either the whole test plan or the failed steps plus any other planned steps the fix could affect.
  - *Acceptance (Given-When-Then):* Given a rerun does not cover the whole test plan, when showrunner records the rerun, then the results artifact identifies which steps were rerun and why that coverage was enough.
  - *Acceptance (rule):* A planned step counts as affected when it uses behavior, screens, data, or seeded state changed by the fix batch.
  - *Acceptance (Given-When-Then):* Given showrunner cannot determine which planned steps a fix batch could affect, when showrunner retries browser execution, then it reruns the whole test plan.

**FR-13.** Showrunner shall stop browser fix-and-retry work after three total fix batches in one browser-verification run or earlier no-progress detection.
  - *Acceptance (Given-When-Then):* Given the third total fix batch in the browser-verification run still leaves any planned browser step failing, when showrunner records the retry result, then showrunner parks before mark-ready with a scrubbed diagnosis.
  - *Acceptance (rule):* A newly exposed app bug after a fix batch counts against the same three-batch run limit.
  - *Acceptance (Given-When-Then):* Given two consecutive fix batches produce the same scrubbed failure summary and no failed or affected step changes from fail to pass, when showrunner detects no progress, then showrunner parks before mark-ready with that scrubbed failure summary.

**FR-14.** After the branch changes following test-plan preparation or browser execution, showrunner shall revalidate the test plan, plan records, and browser results against the final branch state before mark-ready.
  - *Acceptance (Given-When-Then):* Given the PR branch changes after showrunner prepares the test plan, plan records, or browser results, when it prepares to mark the PR ready, then the test plan, plan records, and browser results are confirmed current for the final branch state or showrunner parks with a stale-plan readout.

**FR-15.** After all plan records pass, showrunner shall restore the planned seed data to a fresh baseline state for human spot-checking.
  - *Acceptance (Given-When-Then):* Given browser execution or app-bug retry work changed seeded data, when showrunner prepares the PR for review, then the original planned scenarios are present again in their initial spot-check state.

**FR-16.** When browser-based verification applies, showrunner shall make both the spot-check plan artifact and the browser execution results artifact available before mark-ready.
  - *Acceptance (Given-When-Then):* Given browser execution passed and the fresh seeded baseline is restored, when showrunner evaluates readiness, then the reviewer can find both the spot-check plan and execution results either as PR comments or as named local fallback artifacts.
  - *Acceptance (rule):* The results artifact includes each planned browser step's final result, the browser-run evidence or source for that result, retry and fix-batch history where applicable, any scrubbed failure summaries, and any valid plan-removal reason for a previously planned step.

**FR-17.** Showrunner shall leave spot-check checklist boxes for the human reviewer.
  - *Acceptance (rule):* Where a spot-check checklist exists, showrunner may publish or update the checklist, but it does not check off the human spot-check boxes.

**FR-18.** Showrunner shall allow mark-ready only after pre-ready verification is resolved.
  - *Acceptance (Given-When-Then):* Given browser-based verification applies, at least one browser-executed plan record exists, every plan record passed, any required final plan revalidation passed, the fresh seeded baseline is verified, and both plan and results artifacts are available, when showrunner completes test-pilot verification, then showrunner may proceed to mark-ready.
  - *Acceptance (Given-When-Then):* Given browser-based verification is not applicable and the not-applicable rationale is recorded, when the remaining non-browser gates pass, then showrunner may proceed to mark-ready without a browser test plan, browser results artifact, or seeded spot-check baseline.

## When things go wrong (significant unhappy paths)

**UFR-1.** If planned seeding cannot be safely completed and verified, then showrunner shall park before browser execution.
  - *Acceptance:* Given a planned scenario touches a protected target without explicit authorization for the current run, when showrunner prepares to seed, then no seed data is applied and the readout explains what authorization is needed.
  - *Acceptance:* Given a planned scenario cannot be seeded, seeding only partially applies, or the seeded state cannot be verified before browser execution, when showrunner prepares that plan record, then browser execution does not begin for that record and the readout names the affected scenario or seed failure.

**UFR-2.** If restoring the fresh spot-check baseline would require protected-target authorization, then showrunner shall park before mark-ready.
  - *Acceptance:* Given browser execution has completed and restoring the baseline would touch a protected target without explicit authorization for the current run, when showrunner prepares the spot-check state, then the PR is not marked ready and the readout explains what authorization is needed.

**UFR-3.** If browser-based verification applies and test-pilot calibration, browser tooling, or required server setup is missing, then showrunner shall park before mark-ready with a setup readout.
  - *Acceptance:* Given browser-based verification applies and test-pilot calibration is missing, when showrunner starts test-pilot verification, then showrunner parks before mark-ready and the readout names the missing calibration.
  - *Acceptance:* Given browser-based verification applies and the branch has no usable browser tool configured, when showrunner reaches browser execution, then showrunner parks and tells the maintainer what setup is missing.
  - *Acceptance:* Given browser-based verification applies and required server setup is unavailable, when showrunner prepares browser execution, then showrunner parks before mark-ready and the readout names the missing server setup.

**UFR-4.** If browser-based verification applies but showrunner cannot derive a usable browser-backed test plan for the branch, then showrunner shall park before mark-ready with a no-test-plan readout.
  - *Acceptance:* Given browser-based verification applies and the current PR branch and test-pilot setup produce no test plan, when showrunner summarizes test-pilot verification, then the PR is not marked ready and the readout says no test-pilot plan was available for the branch.
  - *Acceptance:* Given browser-based verification applies and the derived test plan produces no browser-executed plan records, when showrunner summarizes test-pilot verification, then the PR is not marked ready and the readout says no browser-backed test-pilot plan was available for the branch.

**UFR-5.** If a test-pilot plan record has malformed or invalid plan details, then showrunner shall park before browser execution for that record.
  - *Acceptance:* Given a plan record contains malformed or invalid plan details, when showrunner validates the plan record, then browser execution does not begin for that plan record and the readout names the invalid plan detail that must be corrected.

**UFR-6.** If any test-pilot plan record fails or remains incomplete, then showrunner shall park before mark-ready.
  - *Acceptance:* Given one plan record passes and another plan record fails, when showrunner summarizes test-pilot verification, then the PR is not marked ready and the readout names the failing or incomplete plan record.

**UFR-7.** If a planned browser step is skipped, then showrunner shall treat the plan record as incomplete before mark-ready.
  - *Acceptance:* Given a planned browser step records a skipped result, when showrunner summarizes the plan record, then the plan record is not recorded as passed and showrunner parks before mark-ready unless the branch test plan is re-derived from the current branch state and the updated test plan no longer includes that step.
  - *Acceptance:* Given a skipped step is removed by a re-derived test plan, when showrunner continues toward readiness, then the results artifact preserves the skipped step, the reason it no longer belongs in the current test plan, and the updated test plan used for readiness.

**UFR-8.** If the fresh seeded spot-check baseline cannot be restored or verified, then showrunner shall park before mark-ready.
  - *Acceptance:* Given browser execution has completed, when showrunner cannot prove that the planned scenarios are back in their baseline state, then the PR remains not ready and the readout says the spot-check state is not ready.

**UFR-9.** If browser-based verification applies and posting the plan or results comment to the PR fails, then showrunner shall require local fallback artifacts for both plan and results before mark-ready.
  - *Acceptance:* Given GitHub comment posting fails for the plan or results, when both equivalent fallback artifacts are written, then the flow may continue and the final readout names the fallback locations.
  - *Acceptance:* Given GitHub comment posting fails and either fallback artifact is missing, when showrunner reaches the handoff point, then showrunner parks before mark-ready.

**UFR-10.** If test-pilot verification is re-entered after an interruption, then showrunner shall not create duplicate artifacts for completed work.
  - *Acceptance:* Given a prior attempt already recorded browser-based verification as not applicable, when showrunner resumes, then that rationale is reused or re-evaluated against the current branch rather than treating the absence of a browser test plan as a failure.
  - *Acceptance:* Given a prior attempt already created scenarios or plan records for the branch, when showrunner resumes, then the existing scenarios and plan records are updated, reused, or confirmed current rather than duplicated.
  - *Acceptance:* Given a prior attempt already produced a plan artifact for the branch, when showrunner resumes, then the existing plan artifact is updated or reused rather than duplicated.
  - *Acceptance:* Given a prior attempt already produced a results artifact for the branch, when showrunner resumes, then the existing results artifact is updated or reused rather than duplicated.
  - *Acceptance:* Given a prior attempt already wrote local fallback artifacts for the branch, when showrunner resumes, then the existing fallback artifacts are updated or reused rather than duplicated.

## Non-functional requirements

- **Truthful readiness:** A PR is marked ready only when browser-based verification is either complete with human spot-check materials and a fresh seeded baseline, or explicitly recorded as not applicable with a rationale.
- **Privacy:** Plan artifacts, results artifacts, browser execution evidence, PR comments, fallback artifacts, and readouts omit or scrub credentials, secrets, protected or personal data values, and secret-bearing request details before they are exposed, unless the owner explicitly authorized those values for the current run and intended audience.
  - *Acceptance (rule):* No exposed test-pilot verification artifact contains an unsanitized credential, secret, authorization header, cookie, API key, protected or personal data value, or secret-bearing request detail unless that exposure is explicitly authorized for the current run and intended audience.
- **Bounded unattended work:** Browser fix-and-retry work has a fixed stop condition of three total fix batches in one browser-verification run or earlier no-progress detection.
- **Recoverability:** A resumed test-pilot verification run preserves completed artifacts and avoids duplicate PR comments or fallback files.

## Definition of done / success

An approved-spec work item can run through showrunner to a PR where browser-based verification is resolved before mark-ready: either test-pilot has derived the test plan, seeded and browser-tested every plan record, fixed retryable app bugs, posted or locally recorded both plan and results artifacts, and restored a fresh seeded baseline; or showrunner has recorded why browser-based verification is not applicable for this branch.

## Assumptions & dependencies

- The showrunner Workflow spine exists and can run a work item through build, draft PR creation, mark-ready, and ship stages.
- No separate maintainer-invoked test-pilot plan or execute run is required.
- The workhorse build step exists and produces a built change before test-pilot verification runs.
- The existing test-pilot engine, scenario blocks, plan records, PR comment behavior, browser execution behavior, managed server behavior, and seeded-state reset behavior remain the behavior source for this work.
- Where browser-based verification applies, the branch has or can obtain a test-pilot calibration profile, browser tool, and app server configuration before browser execution.
- GitHub access may be unavailable or comment posting may fail; local fallback artifacts are acceptable only when both plan and results are present.

## Constraints

- The work must run inside showrunner rather than requiring the maintainer to manually invoke standalone test-pilot plan or execute commands.
- The PR must not be marked ready before browser-based verification is resolved as either ready-for-spot-check or not applicable.
- Protected-target writes are not allowed in an unattended run without explicit authorization for that run.
- Where browser-based verification applies, browser execution cannot be replaced by a non-browser check and still count as ready-for-spot-check.
- The human spot-check checklist remains human-owned.

## Out of scope

- Changing the meaning of existing test-pilot scenario blocks, protected-target policy, browser-origin limits, or diagnostic scrubbing.
- Adding the multi-issue controller layer.
- Merging the PR automatically.
- Making the standalone test-pilot plan and execute skills obsolete.

## Open questions

None.

## Glossary

- **Test plan:** The branch-specific browser verification checklist that test-pilot derives from the current PR branch and test-pilot setup.
- **Browser-based verification applies:** The branch changes user-facing or runnable behavior that can be meaningfully exercised in a browser before human review.
- **Browser-based verification not applicable:** The branch has no runnable browser surface, so showrunner records a rationale and continues through the remaining non-browser gates instead of requiring a browser test plan.
- **Plan record:** A test-pilot artifact representing one browser-executed part of the test plan, with planned scenarios and browser steps.
- **Fresh seeded baseline:** The planned seed data is present in its initial spot-check state after browser execution and fixes have finished.
- **Ready for spot-check:** Where browser-based verification applies, the PR is ready for a human reviewer to use the plan checklist against the seeded baseline and compare it with the posted or locally recorded results.
- **Protected target:** A configured data target that test-pilot must not write or clean in an unattended run without explicit owner authorization.

## Coverage

| Area | Disposition | Where / why |
| --- | --- | --- |
| Empty & first-run | Specify | FR-2 covers the no-runnable-browser-surface path; FR-3, FR-4, FR-5, and UFR-4 cover test-plan derivation, plan creation, and the applicable-but-no-usable-plan case. |
| Invalid & malformed input | Specify | UFR-3 covers missing calibration and setup; UFR-5 covers malformed or invalid plan details. |
| Boundaries & limits | Specify | FR-13 covers the three-fix-batch run bound; FR-9 covers multiple plan records. |
| Errors & failures | Specify | UFR-1 and UFR-3 through UFR-9 cover seeding, setup, missing test plans, invalid plan records, execution, skipped steps, baseline restoration, and comment/fallback failures. |
| Access & permissions | Specify | UFR-1 and UFR-2 cover protected-target authorization; the assumptions keep GitHub comment failure separate via fallback artifacts. |
| Duplicates & double-actions | Specify | UFR-10 covers resumed runs and duplicate scenario, plan-record, and artifact prevention. |
| Conflicting / simultaneous use | Defer-to-plan | The owner-visible promise is no duplicate artifacts and no false ready signal; lock and resume mechanics belong in the plan. |
| Misuse & abuse | Specify | UFR-1 and the privacy requirement cover protected data writes and scrubbed diagnostics. |
| Reach (i18n / a11y) | N-A | This is a workflow orchestration change with no new user interface surface. |
