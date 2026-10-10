---
superheroes: doc
schemaVersion: 1
docType: spec
workItem: risk-calibrated-review-that-learns-dec0af
issue: null
size: large
status: approved
approved: "2026-10-10"
gates: {review: passed}
producedBy: "the-architect@0.42.0"
created: "2026-10-09"
updated: "2026-10-10"
---
# Risk-calibrated review that learns

## How to read this spec

Every statement ends with its source in plain text. The sources are:

- **board · <artboard>**: the approved build board, saved as `board/build-board.html` beside this
  spec, https://claude.ai/artifact/J1c4SduWJVf2CZkrWSNncH, approved by the owner on 2026-10-09. Its
  artboards are "1 The index", "2 Small sheet and stack sheet", "3 Big PR sheet", "4 Risk and
  trust" and "5 A learning proposal".
- **journeys**: the journeys board the owner approved on 2026-10-09, saved as `board/journeys.html`
  beside this spec, https://claude.ai/artifact/VGc2XjMUJZsXAfMubVtrLW.
- **Canon <entry id>**: an owner ruling recorded in the project's Canon.
- **framing**: the framing the owner approved on 2026-10-09.
- **vet round 1**: a finding in the advisor's first vet record on this spec's pull request, carried
  into the spec. It names an existing part of the plugin or an approved spec. It decides no new
  behaviour.
- **craft, for your veto**: a choice the author made, recorded for the owner's veto.

The requirements are grouped in six parts, A to F. Parts A to E follow the order the work is
built in. (source: Canon 2026-10-09-d6064e1d-1) All six parts ship in one release. (source: Canon 2026-10-10-d6064e1d-3)

## Purpose

The owner cannot review code, so the plugin owns code review. (source: Canon 2026-10-08-d6064e1d-1)
This work replaces the certificate-centred review loop with one that reviews each change as
strictly as the project's risk calls for, keeps a plain record of what happened, brings the owner
only the leftovers that have real consequences, and learns from what escaped. (source: framing)
The balance it aims for is code quality without reviewing forever. (source: Canon 2026-10-08-d6064e1d-1)

## Who it's for

- As an owner who can't review code, I want every change reviewed as strictly as my project's risk
  calls for, so I can ship without reading code. (source: framing)
- As that owner, I want to see only leftovers with real consequences, in plain words, so my time
  goes where the risk is. (source: framing)
- As that owner, I want the review to get better calibrated from what actually escaped, so the
  balance improves without me tuning it. (source: framing)
- As the advisor, I want one plain review record per PR, so I can vet what ran without re-deriving
  proof. (source: framing)

## Functional requirements

### Part A · What "reviewed" means, the review record, and what retires

**FR-1.** The plugin shall report a change as reviewed only when the checks its lane requires passed on the final commit and every finding with a real consequence was fixed, shown wrong, or left under an owner decision. (source: Canon 2026-10-08-d6064e1d-8)
  - *Acceptance (rule):* A change that has a finding with a real consequence that is not fixed, not shown wrong and not covered by an owner decision is not reported as reviewed. (source: Canon 2026-10-08-d6064e1d-8)
  - *Acceptance (rule):* "The checks ran on the final code" is true only when CI is green on the PR's final commit. (source: Canon 2026-10-10-d6064e1d-14)

**FR-2.** The plugin shall describe a reviewed change by what was checked and what is left, and shall not describe it as free of bugs. (source: Canon 2026-10-08-d6064e1d-8)
  - *Acceptance (rule):* No review record, PR sheet or PR text produced by the review says that a change has no bugs. (source: Canon 2026-10-08-d6064e1d-8)

**FR-3.** When a review ends, the plugin shall write one review record for the PR. (source: Canon 2026-10-08-d6064e1d-8)
  - *Acceptance (rule):* The record states the lane and why the change got it, which reviewers ran, each finding and what happened to it, the CI result on the final commit, what is left, the number of rounds and the cost. (source: journeys; board · 3 Big PR sheet)
  - *Acceptance (rule):* A review on any of the three lanes writes a record. (source: craft, for your veto)

**FR-4.** The plugin shall take the record's facts from code wherever code holds them: the lane, the final commit, the check results, and, for each reviewer an engine ran, that the reviewer ran. (source: journeys; framing)
  - *Acceptance (Given-When-Then):* Given a review in which a planned reviewer did not run, when the record is written, then the record does not list that reviewer as having run. (source: framing)
  - *Acceptance (rule):* Where the session that ran the review reports a reviewer's run, and no engine's own record does, the record says so beside that reviewer. (source: vet round 1; craft, for your veto)

**FR-5.** The plugin shall retire these five parts in the same release that first writes the review record: the certificate gate, the planted-bug review control [cite: plugins/superheroes/lib/seat_canary.py], moving a review session by relocate and re-emit [cite: plugins/superheroes/skills/review-code/reference/round-driver.md § relocate and re-emit], starting a review from an old saved session's records, and the exact-head evidence chain. (source: Canon 2026-10-09-d6064e1d-1)
  - *Acceptance (rule):* From that release on, no review is refused, parked or marked incomplete for lacking a certificate. (source: Canon 2026-10-08-d6064e1d-8)
  - *Acceptance (rule):* From that release on, no lane's review runs a planted-bug probe. (source: Canon 2026-10-08-d6064e1d-19)
  - *Acceptance (rule):* No release retires any of the five without writing the review record, and none writes the record while keeping any of the five. (source: Canon 2026-10-09-d6064e1d-1)
  - *Acceptance (rule):* The certificate gate retires in each of its three homes: the part that writes the certification receipt [cite: plugins/superheroes/lib/round_certification.py], the handback check that refuses a PR without a receipt [cite: plugins/superheroes/lib/handback_gate.py § handback-no-receipt], and the certified-loop check in the advisor's vet [cite: plugins/superheroes/skills/showrunner/reference/vet-receipt.md § certified-loop check]. (source: vet round 1)
  - *Acceptance (rule):* Starting a review from an old saved session's records is the part that retires [cite: plugins/superheroes/lib/round_driver.py § _seed_resume]. Picking the same session back up after an interruption or damage stays, as UFR-5 says. (source: vet round 1)
  - *Acceptance (rule):* The exact-head evidence chain is the set of checks that tie each piece of review evidence to one exact commit: the stale-head and head-unbound evidence checks [cite: plugins/superheroes/lib/round_certification.py § execution-evidence-head-unbound], the verified-head field [cite: plugins/superheroes/lib/session_contract.py § verifiedHead], and the saved record of file contents at that commit [cite: docs/superheroes/KEEP-OR-RETIRE.md § Head-content producer]. (source: vet round 1)
  - *Acceptance (rule):* Each of the four kinds of escape the certificate guarded against keeps a guard in this spec: a review that did not run (FR-4 and UFR-3), a reviewer from a maker's family (FR-19 and UFR-4), findings raised and never taken in (FR-36), and a loop that reports it is finished when it is not (FR-1, FR-34 and FR-36). (source: vet round 1)

**FR-6.** The plugin shall keep the engine wiring check [cite: plugins/superheroes/lib/conformance_probe.py] and the new-model admission check [cite: plugins/superheroes/lib/conformance_probe.py § registration-probe], as jobs separate from review. (source: Canon 2026-10-08-d6064e1d-19)
  - *Acceptance (rule):* Both checks still run after the release in FR-5. (source: Canon 2026-10-08-d6064e1d-19)
  - *Acceptance (rule):* The admission check holds a new model back until the model passes it [cite: plugins/superheroes/lib/model_registry.py § probe-pending], and it keeps its own planted example. FR-5 retires only the planted-bug control that ran inside reviews. (source: vet round 1)

**FR-7.** Every plugin rule that requires a certified review loop [cite: plugins/superheroes/rubric/review-discipline.md § The driver mandate] shall require the review record instead. (source: Canon 2026-10-08-d6064e1d-8)
  - *Acceptance (Given-When-Then):* Given a full-lane PR with no review record, when it is handed back, then it is parked. (source: Canon 2026-10-08-d6064e1d-8)

**FR-8.** When the advisor vets a PR, the advisor shall check three things from the review record: that the record exists, that the checks ran on the final commit, and that no leftover skipped the owner's review. (source: Canon 2026-10-08-d6064e1d-18)
  - *Acceptance (Given-When-Then):* Given a PR whose record is missing, or whose checks ran on an earlier commit, or that has a leftover the owner was never shown, when the advisor vets it, then the vet does not return it as ready. (source: Canon 2026-10-08-d6064e1d-18)

### Part B · Risk and trust, the lanes, and the panel

**FR-9.** Configure shall hold one item named "Risk and trust", made of the project's threat model [cite: plugins/superheroes/lib/project_config.py § threatModel] and a list of risk areas. (source: Canon 2026-10-09-d6064e1d-2; board · 4 Risk and trust)
  - *Acceptance (rule):* Viewing the item shows the threat model under "What we defend against" and the risk areas under "Risk areas". (source: board · 4 Risk and trust)

**FR-10.** Each risk area shall say which parts of the project it covers, why it is risky, and how hard a mistake there is to undo. (source: Canon 2026-10-09-d6064e1d-2)
  - *Acceptance (rule):* The review loop decides whether a change touches a risk area from the risk area itself, with no model judgment needed for a change that plainly sits inside one. (source: Canon 2026-10-09-d6064e1d-2)
  - *Acceptance (rule):* A risk area may cover a part of the project where a mistake costs money, customer data, safety, access, or something that cannot be undone. (source: Canon 2026-10-08-d6064e1d-2; board · 4 Risk and trust)

**FR-11.** The advisor shall set up Risk and trust with the owner in one sitting, in product terms. (source: Canon 2026-10-08-d6064e1d-5; journeys)
  - *Acceptance (rule):* The sitting asks, in this order: who the product is for and what it is for, where money, customer data, access and irreversible actions live, which outcomes are unacceptable, how quickly a bad change can be undone, and what can be run to try the product. (source: board · 4 Risk and trust; Canon 2026-10-05-3dbeb858-46)

**FR-12.** Where who the product is for is already set, the sitting shall offer to read that answer back and shall not ask it again. (source: Canon 2026-10-09-d6064e1d-13)
  - *Acceptance (Given-When-Then):* Given a project whose who-it's-for answer is set, when the sitting starts, then the advisor offers to read it back and moves to the risk questions. (source: Canon 2026-10-09-d6064e1d-13)

**FR-13.** The plugin shall keep the light, full and micro lanes [cite: plugins/superheroes/rubric/review-discipline.md § Review lanes] and shall add no other tier of review. (source: Canon 2026-10-08-d6064e1d-12)
  - *Acceptance (rule):* Every change is reviewed on exactly one of the three lanes. (source: Canon 2026-10-08-d6064e1d-12)

**FR-14.** When a change touches a risk area, the plugin shall give it the full lane, whatever its size. (source: Canon 2026-10-08-d6064e1d-2; journeys; board · 4 Risk and trust)
  - *Acceptance (Given-When-Then):* Given a risk area that covers payments, when a two-line change to payment code is routed, then it gets the full lane. (source: board · 4 Risk and trust)

**FR-15.** A model may raise a change's lane, and shall never lower it below what the risk areas require. (source: Canon 2026-10-08-d6064e1d-8)
  - *Acceptance (Given-When-Then):* Given a change that touches a risk area, when a model judges the change trivial, then the change still gets the full lane. (source: Canon 2026-10-08-d6064e1d-8)

**FR-16.** The full lane's panel shall be a generalist code reviewer, the test role, and the specialists that the touched risk areas call for. (source: Canon 2026-10-08-d6064e1d-16)
  - *Acceptance (Given-When-Then):* Given a full-lane change that touches payments, when it is reviewed, then the review record lists a generalist, the test role and a specialist chosen for that risk area. (source: board · 3 Big PR sheet)

**FR-17.** The light lane's review shall be one independent reviewer. (source: Canon 2026-10-08-d6064e1d-16)
  - *Acceptance (rule):* A light-lane review record lists exactly one reviewer. (source: board · 2 Small sheet and stack sheet)

**FR-18.** On the light and micro lanes, the review record shall show, from the engine's own record, that the one reviewer read the change. (source: craft, for your veto)
  - *Acceptance (Given-When-Then):* Given a reviewer whose engine record does not show that it read the change, when the review ends, then the review counts as not run: the plugin runs the reviewer once more, and if the record still does not show a reading, the change moves up to the full lane or parks. (source: craft, for your veto)
  - *Acceptance (rule):* A record that is missing, or that cannot tell whether the reviewer read the change, counts as not showing it. (source: craft, for your veto)
  - *Acceptance (rule):* This takes the place of the planted-bug probe those two lanes carry today [cite: plugins/superheroes/rubric/review-discipline.md § mandatory planted-defect control probe]. (source: Canon 2026-10-08-d6064e1d-19; vet round 1)

**FR-19.** Every reviewer shall come from a different model family than every maker of the change. (source: Canon 2026-10-10-d6064e1d-12)
  - *Acceptance (Given-When-Then):* Given a change built by one model family, when its reviewers are picked, then none of them is from that family. (source: Canon 2026-10-10-d6064e1d-12)
  - *Acceptance (rule):* A reviewer that writes break-it tests for a change is not a maker of that change. (source: Canon 2026-10-10-d6064e1d-5)

**FR-20.** Every reviewer that confirms, audits, fixes or grades a finding shall be given the project's threat model. (source: Canon 2026-10-10-d6064e1d-13)
  - *Acceptance (rule):* No such reviewer runs without the threat model in what it is given. (source: Canon 2026-10-10-d6064e1d-13)

**FR-21.** The test role shall replace today's test reviewer [cite: plugins/superheroes/agents/test-reviewer.md]. (source: Canon 2026-10-08-d6064e1d-17)
  - *Acceptance (rule):* No review runs both a test reviewer and the test role. (source: Canon 2026-10-08-d6064e1d-17)

**FR-22.** The test role shall keep the test reviewer's duties that this spec does not drop. (source: vet round 1; craft, for your veto)
  - *Acceptance (rule):* The test role asks, of each changed test, whether the test would fail if the code under test were wrong [cite: plugins/superheroes/agents/test-reviewer.md § Mutation-survival lens]. (source: vet round 1)
  - *Acceptance (rule):* When an intentional edit leaves a test file holding tests that cannot fail, the test role raises a finding that names them [cite: docs/superheroes/verification-strategy-for-the-superheroes-repo-c629cd/spec.md § FR-18f]. (source: vet round 1)
  - *Acceptance (rule):* FR-29 names the two duties this spec drops. (source: Canon 2026-10-08-d6064e1d-17)

**FR-23.** Where a change touches a risk area, the test role shall write and run break-it tests on that area. (source: Canon 2026-10-08-d6064e1d-17; board · 4 Risk and trust)
  - *Acceptance (Given-When-Then):* Given a full-lane change that touches a risk area, when the test role reviews it, then the role runs at least one test it wrote that tries to break the change on a named risky scenario. (source: Canon 2026-10-08-d6064e1d-15; craft, for your veto)

**FR-24.** When a break-it test fails, the plugin shall treat the failure as a finding and keep the test with the change once the finding is fixed. (source: board · 3 Big PR sheet)
  - *Acceptance (Given-When-Then):* Given a break-it test that catches a double charge, when the fix lands, then the test stays in the change and passes. (source: board · 3 Big PR sheet)
  - *Acceptance (rule):* The generalist code reviewer reads the break-it tests for bloat and for tests that pass without checking anything. (source: Canon 2026-10-10-d6064e1d-5)

**FR-25.** The test role shall report a test that passes without checking the behaviour it claims to check. (source: Canon 2026-10-08-d6064e1d-17)
  - *Acceptance (rule):* Such a test is reported as a finding with its consequence. (source: Canon 2026-10-08-d6064e1d-17)

**FR-26.** The test role shall report a test that can fail or pass by chance. (source: Canon 2026-10-08-d6064e1d-17)
  - *Acceptance (rule):* Such a test is reported as a finding with its consequence. (source: Canon 2026-10-08-d6064e1d-17)

**FR-27.** The test role shall report a change to a check that comes with no proof that the check catches what it is for. (source: Canon 2026-10-08-d6064e1d-17)
  - *Acceptance (rule):* Such a change is reported as a finding with its consequence. (source: Canon 2026-10-08-d6064e1d-17)

**FR-28.** The test role shall count test bloat against a change. (source: Canon 2026-10-08-d6064e1d-17)
  - *Acceptance (rule):* A test that is brittle, that duplicates another test, or that only pins wording is reported as a finding. (source: craft, for your veto)
  - *Acceptance (rule):* No finding rests only on how much of a change is test code [cite: docs/superheroes/verification-strategy-for-the-superheroes-repo-c629cd/spec.md § FR-18e]. (source: vet round 1)

**FR-29.** The test role shall not ask for more test coverage in code outside the risk areas, and shall not raise test-style preferences. (source: Canon 2026-10-08-d6064e1d-17)
  - *Acceptance (rule):* No finding from the test role asks for coverage in code outside every risk area, or for a change of test style alone. (source: Canon 2026-10-08-d6064e1d-17)

### Part C · Findings and the fix loop

**FR-30.** Every finding shall state its consequence if it is left unfixed. (source: Canon 2026-10-09-d6064e1d-4)
  - *Acceptance (rule):* A finding with no stated consequence is not accepted into the review. (source: Canon 2026-10-09-d6064e1d-4)

**FR-31.** When a finding has no consequence beyond code quality, the loop shall decide it as craft and record the decision for the owner's veto. (source: Canon 2026-10-09-d6064e1d-4)
  - *Acceptance (Given-When-Then):* Given a finding about naming with no effect on what the product does, when the review ends, then the finding appears under "Decided as craft, for your veto" and not under "What you're accepting". (source: board · 3 Big PR sheet)
  - *Acceptance (rule):* A finding with no consequence beyond code quality is craft inside a risk area too. (source: Canon 2026-10-10-d6064e1d-16)

**FR-32.** When a finding with a real consequence is left unfixed, the plugin shall bring it to the owner as a leftover, unless a standing ruling of the project clearly decides it. (source: Canon 2026-10-09-d6064e1d-4; Canon 2026-10-08-d6064e1d-26)
  - *Acceptance (Given-When-Then):* Given a project with no standing ruling that covers a leftover, when the PR's sheet is built, then the leftover is on the sheet under "What you're accepting". (source: Canon 2026-10-08-d6064e1d-26)
  - *Acceptance (Given-When-Then):* Given a standing ruling that clearly decides a leftover, when the PR's sheet is built, then the leftover appears under "Already decided" with that ruling named. (source: board · 3 Big PR sheet; Canon 2026-10-09-d6064e1d-4)
  - *Acceptance (rule):* A leftover that one of the project's recorded residuals already covers [cite: plugins/superheroes/rubric/review-discipline.md § Review bars and recorded residuals] also appears under "Already decided". Recorded residuals stay as they are, and a standing ruling is a second way a leftover is already decided. (source: vet round 1; craft, for your veto)

**FR-33.** Severity shall only order the work, and shall not decide whether a finding reaches the owner. (source: Canon 2026-10-09-d6064e1d-4)
  - *Acceptance (Given-When-Then):* Given a low-severity finding with a real consequence, left unfixed, when the sheet is built, then the finding reaches the owner as in FR-32. (source: Canon 2026-10-09-d6064e1d-4)

**FR-34.** The loop shall run fix rounds until every finding has an outcome, within its round caps. (source: Canon 2026-10-08-d6064e1d-14; journeys)
  - *Acceptance (rule):* The loop ends when every finding is fixed, shown wrong, decided as craft, left for the owner, or decided by a named ruling. (source: Canon 2026-10-09-d6064e1d-4; Canon 2026-10-10-d6064e1d-6)

**FR-35.** When a fix lands, the next review round shall focus on that fix. (source: journeys)
  - *Acceptance (Given-When-Then):* Given a round that fixed two findings, when the next round runs, then its reviewers are asked about those two fixes. (source: journeys)
  - *Acceptance (rule):* When a round looks wider than the fixes, the review record says why. (source: craft, for your veto)

**FR-36.** The plugin shall give every finding a recorded outcome, and shall not drop a finding or lower it without recording why. (source: Canon 2026-10-10-d6064e1d-6)
  - *Acceptance (rule):* The number of findings with a recorded outcome equals the number of findings the reviewers raised. (source: Canon 2026-10-10-d6064e1d-6)

**FR-37.** When the owner rules on a finding, the next fix for that finding shall follow the ruling. (source: Canon 2026-10-10-d6064e1d-7)
  - *Acceptance (Given-When-Then):* Given an owner ruling on a finding, when the finding is reworded in a later round, then the ruling still applies to it. (source: Canon 2026-10-10-d6064e1d-7)
  - *Acceptance (rule):* No round runs on guidance that a later ruling replaced. (source: Canon 2026-10-10-d6064e1d-7)

**FR-38.** When a finding is outside the change's scope, the loop shall take it off the fix list or bring it to the owner. (source: Canon 2026-10-10-d6064e1d-8)
  - *Acceptance (rule):* An out-of-scope finding is not sent to a fixer in more than one round. (source: Canon 2026-10-10-d6064e1d-8)
  - *Acceptance (rule):* An out-of-scope finding with a real consequence still reaches the owner as a leftover under FR-32, whatever its severity. (source: Canon 2026-10-09-d6064e1d-4; vet round 1)

**FR-39.** A fix shall change only what its finding needs. (source: Canon 2026-10-10-d6064e1d-9)
  - *Acceptance (Given-When-Then):* Given a fix that would change behaviour its finding does not name, when no owner ruling allows that change, then the fix is not accepted. (source: Canon 2026-10-10-d6064e1d-9)

**FR-40.** The review record shall say the owner decided something only when that decision is on record. (source: Canon 2026-10-10-d6064e1d-10)
  - *Acceptance (rule):* A decision about one PR is on record in that PR's saved sheet answers. (source: Canon 2026-10-10-d6064e1d-10)
  - *Acceptance (rule):* A decision that sets a rule for later work is on record in Canon. (source: Canon 2026-10-10-d6064e1d-10)

**FR-41.** The plugin shall keep everything the review did not show the owner retrievable. (source: Canon 2026-10-10-d6064e1d-16)
  - *Acceptance (Given-When-Then):* Given a bug found after merge, when the advisor looks up the PR's review, then every craft decision and every finding shown wrong is still readable. (source: Canon 2026-10-10-d6064e1d-16)

### Part D · The owner's decisions: the index, the PR sheets and the walk

**FR-42.** The plugin shall bring the owner's decisions in three batches, in order. (source: Canon 2026-10-09-d6064e1d-6)
  - *Acceptance (rule):* Batch 1 holds what blocks work. Batch 2 holds decisions not tied to one PR. Batch 3 holds one sheet per PR. (source: Canon 2026-10-09-d6064e1d-6)

**FR-43.** The plugin shall put each batch-1 question both in the chat and at the top of the index, with the chat linking to the index. (source: Canon 2026-10-09-d6064e1d-6; board · 1 The index)
  - *Acceptance (rule):* The first answer given, in either place, is the answer. (source: Canon 2026-10-09-d6064e1d-6)
  - *Acceptance (rule):* Where pictures bear on a batch-1 question, the index shows them with the question. (source: Canon 2026-10-09-d6064e1d-6; Canon 2026-10-05-3dbeb858-24)

**FR-44.** When a batch-1 question is answered, the plugin shall remove it from the index. (source: Canon 2026-10-09-d6064e1d-9)
  - *Acceptance (Given-When-Then):* Given the only batch-1 question is answered, when the index is next shown, then its "Blocks work" part reads "Nothing is blocking work right now." (source: board · 1 The index)

**FR-45.** The plugin shall bring batch 2 in the chat. (source: Canon 2026-10-09-d6064e1d-6)
  - *Acceptance (rule):* No batch-2 item concerns one specific PR. (source: Canon 2026-10-09-d6064e1d-6)

**FR-46.** The plugin shall build the PR sheets only after the batch-1 and batch-2 rulings have been carried out. (source: Canon 2026-10-09-d6064e1d-6)
  - *Acceptance (Given-When-Then):* Given a batch-1 ruling that sends a PR back, when batch 3 is built, then that PR has no sheet waiting for answers. (source: Canon 2026-10-09-d6064e1d-6)

**FR-47.** The index shall list every PR with a sheet under one of three headings: "Needs you", "Being fixed" or "Ready". (source: Canon 2026-10-09-d6064e1d-16; board · 1 The index)
  - *Acceptance (rule):* Each row names the PR, shows how many items are accepted and how many walk stops are walked, and opens that PR's sheet. (source: board · 1 The index)
  - *Acceptance (rule):* A row under "Needs you" says where the PR falls in the merge order, for example "merges first". The advisor sets that order. (source: board · 1 The index; Canon 2026-10-09-d6064e1d-16)

**FR-48.** A PR's sheet shall be one scrolling page whose parts come in this order: what changed, the walk, what you're accepting, the three folded parts, the merge verdict. (source: Canon 2026-10-09-d6064e1d-15; board · 3 Big PR sheet)
  - *Acceptance (rule):* A part with nothing in it is left out, except "What you're accepting", which then reads "Nothing. The review left nothing for you." (source: board · 2 Small sheet and stack sheet)

**FR-49.** A stack of PRs that merges whole shall get one sheet. (source: Canon 2026-10-09-d6064e1d-7; board · 2 Small sheet and stack sheet)
  - *Acceptance (rule):* The stack's sheet has one walk, one list of what the owner is accepting, one merge verdict for the whole stack, and a folded list of the stack's PRs. (source: board · 2 Small sheet and stack sheet)
  - *Acceptance (rule):* Each walk stop on a stack's sheet names the PR it comes from. (source: board · 2 Small sheet and stack sheet)

**FR-50.** The "What changed" part shall say, in plain words, what changed, who reviewed it, what the review caught, how many rounds ran, the CI result, the lane and why, and the commit the sheet describes. (source: board · 3 Big PR sheet)
  - *Acceptance (rule):* Every fact in the part matches the PR's review record. (source: craft, for your veto)

**FR-51.** "What you're accepting" shall list every leftover and anything else on the PR that needs the owner, each answered on its own. (source: Canon 2026-10-09-d6064e1d-7)
  - *Acceptance (rule):* Each item shows, in this order: its kind, its title, what happens if it is left, its options with what each means, the recommendation, the answer buttons, and a note box. (source: board · 3 Big PR sheet)
  - *Acceptance (rule):* When the PR's merge closes the last open piece of a spec, that spec's closure receipt is one of the items, for the owner to accept [cite: docs/superheroes/front-half-sdlc-core-6181ee/spec.md § FR-38]. (source: vet round 1; Canon 2026-10-09-d6064e1d-7)

**FR-52.** Where an item has a real choice, the sheet shall offer its options and "Something else". (source: Canon 2026-10-09-d6064e1d-7; board · 3 Big PR sheet)
  - *Acceptance (rule):* A leftover's options are "Keep it", "Fix in a follow-up" and "Fix before merge" unless the item calls for different ones. (source: board · 3 Big PR sheet)

**FR-53.** Where an item has no real choice, the sheet shall offer "Accept" and "Discuss". (source: Canon 2026-10-09-d6064e1d-17)
  - *Acceptance (rule):* Such an item shows no options list. (source: board · 3 Big PR sheet)

**FR-54.** Every question the plugin puts to the owner, on a sheet or on the index, shall offer an optional note box beside its answers. (source: Canon 2026-10-09-d6064e1d-18)
  - *Acceptance (rule):* A question can be answered with the note left empty. (source: Canon 2026-10-09-d6064e1d-18)

**FR-55.** A PR sheet shall follow the approved review surface spec [cite: docs/superheroes/the-review-surface-d59417/spec.md § FR-4a] wherever this spec states no difference. (source: Canon 2026-10-08-d6064e1d-25; vet round 1)
  - *Acceptance (rule):* Taps save as drafts, the last tap is the answer, and the plugin reads a sheet's answers together only after the owner says "done" in the chat, as that spec's FR-4 and FR-4a say. (source: Canon 2026-10-05-3dbeb858-39)
  - *Acceptance (Given-When-Then):* Given a PR sheet with saved answers and no "done" yet, when the advisor looks at it, then nothing is merged, sent back, filed or recorded in Canon from it. (source: Canon 2026-10-05-3dbeb858-39)
  - *Acceptance (Given-When-Then):* Given "Keep it" on a leftover with a note that says to fix it first, when the advisor reads the sheet after "done", then the advisor treats that item as open, does not merge the PR, and asks the owner which one stands, as that spec's FR-6 says. (source: Canon 2026-10-05-3dbeb858-38)
  - *Acceptance (rule):* A save that fails, a picture that cannot load and a sheet the owner shared behave as that spec's UFR-2, UFR-3 and UFR-4 say. (source: Canon 2026-10-05-3dbeb858-40; vet round 1)
  - *Acceptance (rule):* Every question on a PR sheet and the index uses one of the four accepted answer patterns: pick, for a batch-1 question and for an item with a real choice (FR-43 and FR-52); agree, with "Accept" as its yes-word, for an item with no real choice (FR-53); check, for a walk stop (FR-56, FR-57 and FR-59); and sign-off, for the merge verdict (FR-62 to FR-66). (source: Canon 2026-10-10-d6064e1d-17)
  - *Acceptance (rule):* No PR sheet and no index offers an answer button outside those four patterns. (source: Canon 2026-10-10-d6064e1d-17)
  - *Acceptance (rule):* The four patterns are a standing rule for every sheet, and a sheet's author picks the pattern that fits each question. Discovery's sheets already use three of them, agree with "Aligned" as the yes-word, pick, and sign-off with "Approve", and this spec changes nothing on them. This spec builds the rule for PR sheets and the index. (source: Canon 2026-10-10-d6064e1d-17)
  - *Acceptance (rule):* Four things differ on a PR sheet and the index from that spec as it stands today: the answer buttons (FR-52, FR-53, FR-56, FR-57 and FR-59), the merge verdict (FR-62 to FR-66), the zoom buttons on an opened picture (FR-61), and a batch-1 question, whose first answer counts at once (FR-43). (source: board · 3 Big PR sheet; Canon 2026-10-09-d6064e1d-6)

**FR-56.** Where a PR has something the owner can try, its sheet shall carry a "Walk it" part. (source: Canon 2026-10-09-d6064e1d-19; board · 3 Big PR sheet)
  - *Acceptance (rule):* The part shows a way to open the product, how many stops are walked, and the stops in named groups. (source: board · 3 Big PR sheet)
  - *Acceptance (rule):* Each stop shows its numbered steps, an "Expect" line, its pictures where it has any, the answers "Works", "Problem" and "Skip", and a note box. (source: board · 3 Big PR sheet)

**FR-57.** Where a screen cannot be reached by hand, the walk shall show it as a look-only stop. (source: board · 3 Big PR sheet)
  - *Acceptance (rule):* A look-only stop has no steps, a "Look for" line, its pictures, and the answers "Looks right", "Problem" and "Skip". (source: board · 3 Big PR sheet)

**FR-58.** Before a sheet with a walk is sent, the advisor shall walk its stops. (source: board · 3 Big PR sheet)
  - *Acceptance (rule):* The walk part says that the advisor walked it first and where its pictures come from. (source: board · 3 Big PR sheet)
  - *Acceptance (rule):* A stop that a pilot run already walked, with its evidence, counts as walked, and the advisor does not repeat it by hand. (source: vet round 1; craft, for your veto)

**FR-59.** When the owner marks a stop "Problem", the sheet shall ask whether to fix it before merge or in a follow-up. (source: Canon 2026-10-09-d6064e1d-21)
  - *Acceptance (rule):* The stop then offers "Fix before merge", "Fix in a follow-up", "Add a screenshot", and a note box labelled "What did you see?". (source: board · 3 Big PR sheet)

**FR-60.** The sheet shall show its pictures on the sheet itself. (source: Canon 2026-10-09-d6064e1d-20)
  - *Acceptance (Given-When-Then):* Given a picture a builder made on an account the owner cannot open, when the sheet is published, then the picture is on the sheet and the sheet links to no other page for it. (source: Canon 2026-10-09-d6064e1d-20)

**FR-61.** When the owner opens a picture on a PR sheet, the sheet shall offer "−", "+" and "Fit" buttons to zoom it. (source: Canon 2026-10-09-d6064e1d-23; board · 3 Big PR sheet)
  - *Acceptance (rule):* Everything else about an opened picture is as the review surface spec says: it opens large with a Close control, zooms by pinch or double-tap, moves by dragging, and does not move to another picture by swiping sideways [cite: docs/superheroes/the-review-surface-d59417/spec.md § FR-11]. (source: vet round 1)

**FR-62.** The sheet shall keep the merge verdict locked until every item is accepted and every walk problem has a choice. (source: Canon 2026-10-09-d6064e1d-8; Canon 2026-10-09-d6064e1d-21)
  - *Acceptance (rule):* While locked, the merge button reads "Merge #<number> · locked" and cannot be tapped, and the sheet says what still unlocks it. (source: board · 3 Big PR sheet)
  - *Acceptance (rule):* An answer that sends the PR back does not count as accepted. (source: board · 3 Big PR sheet)

**FR-63.** When the owner chooses "Fix before merge" on an item or a walk problem, the sheet shall replace the merge verdict with a message that the PR goes back for that fix. (source: Canon 2026-10-09-d6064e1d-21; board · 3 Big PR sheet)
  - *Acceptance (Given-When-Then):* Given that choice, when the index is next shown, then the PR is under "Being fixed", and it returns with a new sheet after the fix. (source: board · 1 The index)

**FR-64.** Walk stops the owner has not walked shall not lock the merge verdict. (source: Canon 2026-10-09-d6064e1d-22)
  - *Acceptance (rule):* The verdict says how many stops are not walked, and optional stops are not counted. (source: board · 3 Big PR sheet)

**FR-65.** When the owner un-accepts an item or marks a new walk problem after giving a merge verdict, the sheet shall clear that verdict. (source: board · 3 Big PR sheet)
  - *Acceptance (Given-When-Then):* Given a saved merge verdict, when the owner changes an item from accepted to "Discuss", then the sheet shows no merge verdict and the index no longer lists the PR under "Ready". (source: board · 3 Big PR sheet)

**FR-66.** The plugin shall take a saved "Merge" verdict together with the owner saying "done" in the chat as the owner's word to merge that PR. (source: Canon 2026-10-09-d6064e1d-8)
  - *Acceptance (rule):* Neither a saved "Merge" verdict alone nor "done" alone is taken as that word. (source: Canon 2026-10-09-d6064e1d-8)
  - *Acceptance (rule):* A saved "Not yet", or no saved verdict, together with "done" is not that word. (source: board · 3 Big PR sheet)

**FR-67.** The plugin shall take a "Fix in a follow-up" answer as the owner's word to file that follow-up. (source: Canon 2026-10-09-d6064e1d-8; Canon 2026-10-09-d6064e1d-21)
  - *Acceptance (Given-When-Then):* Given that answer and a merged PR, when the advisor finishes the merge, then a follow-up exists that carries the owner's note. (source: board · 3 Big PR sheet)
  - *Acceptance (rule):* A follow-up filed for a leftover carries a date to revisit it. (source: board · 3 Big PR sheet)

**FR-68.** The plugin shall write the owner's answers and verdict back to the PR as its receipt. (source: Canon 2026-10-09-d6064e1d-7)
  - *Acceptance (rule):* After the merge, the PR shows each answer and the verdict. (source: Canon 2026-10-09-d6064e1d-7)
  - *Acceptance (rule):* The walk's results are saved with the sheet. (source: Canon 2026-10-09-d6064e1d-19)

**FR-69.** The sheet shall carry three folded parts above the verdict: "Decided as craft, for your veto", "Already decided" and "How the review went". (source: board · 3 Big PR sheet)
  - *Acceptance (rule):* Each folded part shows how many entries it holds and opens on a tap. (source: board · 3 Big PR sheet)

**FR-70.** When an owner answer sets a rule for later work, the plugin shall record that rule in Canon. (source: Canon 2026-10-08-d6064e1d-27)
  - *Acceptance (rule):* A permanent acceptance, an approved calibration change and a ceded call are each recorded in Canon. (source: Canon 2026-10-08-d6064e1d-27)

### Part E · Learning from escapes

**FR-71.** When a vet of a fix, a detective diagnosis, a field report or the owner's own report traces a bug to a reviewed PR, the plugin shall log a review escape in the misses log [cite: plugins/superheroes/rubric/glossary.md § Misses log]. (source: Canon 2026-10-09-d6064e1d-11; Canon 2026-10-10-d6064e1d-1)
  - *Acceptance (rule):* The entry links to the PR's review record and says whether the review missed the bug, or saw it and left it. (source: journeys)

**FR-72.** Each reviewer seat shall be an entry on the keep-or-retire list [cite: docs/superheroes/KEEP-OR-RETIRE.md § Keep-or-retire list]. (source: Canon 2026-10-10-d6064e1d-1)
  - *Acceptance (rule):* A seat's entry is judged on what the seat caught. (source: framing)
  - *Acceptance (rule):* From the day it is created, a seat's entry carries what every entry on that list carries, its retirement condition and window among them [cite: plugins/superheroes/rubric/glossary.md § Keep-or-retire entry]. (source: vet round 1)
  - *Acceptance (rule):* The part of the plugin that writes the review record has an entry of its own on that list. (source: vet round 1)

**FR-73.** At the gardening pass, the advisor shall read the review escapes and the reviewer seats' entries and propose calibration changes backed by that evidence. (source: Canon 2026-10-08-d6064e1d-9; journeys)
  - *Acceptance (rule):* A proposal names the evidence it rests on, its options, what each costs, and a recommendation. (source: board · 5 A learning proposal)

**FR-74.** The plugin shall bring a learning proposal to the owner in batch 2. (source: board · 5 A learning proposal)
  - *Acceptance (rule):* A proposal to loosen the calibration looks the same as one to tighten it. (source: board · 5 A learning proposal)

**FR-75.** The plugin shall change the calibration only on the owner's yes, whether the change tightens or loosens it. (source: Canon 2026-10-08-d6064e1d-13)
  - *Acceptance (Given-When-Then):* Given a proposal the owner has not answered, when the next review runs, then it runs on the calibration as it was. (source: Canon 2026-10-08-d6064e1d-13)

**FR-76.** When the owner approves a calibration change, the plugin shall apply it from the next review on. (source: board · 5 A learning proposal)
  - *Acceptance (rule):* The approval is recorded in Canon as FR-70 says. (source: Canon 2026-10-08-d6064e1d-27)

**FR-77.** When the owner says a review took too long, the advisor shall answer with whether the calibration is right and whether the loop followed it, and shall not treat the complaint as an instruction to go faster. (source: Canon 2026-10-08-d6064e1d-6)
  - *Acceptance (Given-When-Then):* Given such a complaint, when the advisor replies, then the reply says what the review spent its time on and proposes a calibration change or none. (source: Canon 2026-10-08-d6064e1d-6)

### Part F · A project that already uses the plugin

**FR-78.** When an existing project adopts this work, the plugin shall keep its threat model unchanged as the threat-model half of Risk and trust. (source: Canon 2026-10-09-d6064e1d-14)
  - *Acceptance (rule):* The project's risk areas start empty. (source: Canon 2026-10-09-d6064e1d-14)

**FR-79.** The release notes shall ask the owner of an existing project to do the risk sitting with the advisor. (source: Canon 2026-10-09-d6064e1d-14)
  - *Acceptance (rule):* The project keeps working before the sitting, on the default in UFR-1. (source: Canon 2026-10-09-d6064e1d-14)
  - *Acceptance (rule):* The same release notes tell a project whose own checks look for the certificate's words what replaces them. (source: vet round 1; craft, for your veto)

**FR-80.** The plugin shall carry an existing project's reviewer choices over. (source: Canon 2026-10-09-d6064e1d-14)
  - *Acceptance (rule):* The model chosen for the test reviewer becomes the model for the test role. (source: Canon 2026-10-09-d6064e1d-14)

**FR-81.** The plugin shall start counting review escapes and reviewer seats' records from the day a project adopts this work. (source: Canon 2026-10-09-d6064e1d-14)
  - *Acceptance (rule):* No reviewer seat is judged on reviews from before that day. (source: Canon 2026-10-09-d6064e1d-14)

## When things go wrong (significant unhappy paths)

**UFR-1.** If a project has no risk areas set, then the plugin shall give every change whose risk is unclear the full lane, and shall bring every leftover with a real consequence to the owner. (source: Canon 2026-10-09-d6064e1d-14; board · 4 Risk and trust)
  - *Acceptance:* Given a project with no risk areas, when a change that might touch money is routed, then it gets the full lane. (source: Canon 2026-10-09-d6064e1d-14)
  - *Acceptance:* Given a Risk and trust item the review loop cannot read, when a change is routed, then the plugin treats the risk areas as not set. (source: craft, for your veto)

**UFR-2.** If the fix rounds reach their cap with findings still open, then the loop shall stop and bring those findings out as leftovers. (source: Canon 2026-10-08-d6064e1d-14; Canon 2026-10-10-d6064e1d-6; journeys)
  - *Acceptance:* Given a capped loop with one open finding that has a real consequence, when the sheet is built, then that finding is under "What you're accepting" and "How the review went" says the loop reached its cap. (source: craft, for your veto)

**UFR-3.** If a planned reviewer could not run, or CI is not green on the final commit, then the plugin shall say so in the review record and shall not report the change as reviewed. (source: Canon 2026-10-08-d6064e1d-8; Canon 2026-10-10-d6064e1d-14)
  - *Acceptance:* Given a full-lane review whose specialist did not run, when the advisor vets the PR, then the record shows the gap and the vet does not return the PR as ready. (source: craft, for your veto)
  - *Acceptance:* Given that PR, when the missing review has not run, then the PR stays parked until the review runs, unless a standing ruling of the owner already covers that missing review or the owner says in plain words to go ahead without it. This follows the plugin's rule on a check that is lost [cite: plugins/superheroes/rubric/covenant.md § Disclose every degradation]. (source: vet round 1; craft, for your veto)
  - *Acceptance:* Given the owner's ruling or word to go ahead, when the PR's sheet is built, then "How the review went" names the review that did not run. (source: craft, for your veto)

**UFR-4.** If no reviewer from a different model family than every maker can run, then the plugin shall treat the review as not run, as UFR-3 says. (source: Canon 2026-10-10-d6064e1d-12; vet round 1)
  - *Acceptance:* Given a light-lane change with no such reviewer available, when the review is due, then no session picks a same-family reviewer or stands in for the reviewer on its own. (source: Canon 2026-10-10-d6064e1d-12)
  - *Acceptance:* Given the owner's word, for that change, to use a reviewer from a maker's family, when the review runs, then the review record names that reviewer and says the review was not independent. (source: craft, for your veto)
  - *Acceptance (rule):* The stand-in that today needs no owner decision ends with this work [cite: plugins/superheroes/rubric/review-discipline.md § Single-reviewer lanes]. (source: vet round 1)

**UFR-5.** If a review session is damaged partway, then the plugin shall repair it and carry on, and shall not abandon it. (source: Canon 2026-10-10-d6064e1d-11)
  - *Acceptance:* Given a session damaged after its second round, when the review resumes, then every finding and outcome from the first two rounds is still in the record. (source: Canon 2026-10-10-d6064e1d-11)

**UFR-6.** If the PR's head commit moves after its sheet was published, then the plugin shall replace the sheet with an unsigned one for the new commit. (source: Canon 2026-10-09-d6064e1d-7)
  - *Acceptance:* Given answers saved on the old sheet, when the new sheet opens, then it shows "This PR changed", keeps the answers to unchanged items, and starts the merge verdict over. (source: board · 3 Big PR sheet)

**UFR-7.** If the chat answer and the index answer to one batch-1 question disagree, then the advisor shall ask the owner which one stands. (source: Canon 2026-10-09-d6064e1d-6)
  - *Acceptance:* Given "Keep them visible" on the index and "hide them" in the chat, when the advisor reads both, then the advisor acts on neither until the owner answers. (source: board · 1 The index)

**UFR-8.** If a picture cannot be put on the sheet, then the sheet shall say that the picture is missing and shall show no link to another page for it. (source: Canon 2026-10-09-d6064e1d-20)
  - *Acceptance:* Given a stop whose picture could not be copied, when the sheet opens, then the stop says a picture is missing, and the stop can still be answered. (source: Canon 2026-10-09-d6064e1d-20; vet round 1)

**UFR-9.** If the advisor could not walk a stop before the sheet was sent, then the sheet shall say so on that stop. (source: craft, for your veto)
  - *Acceptance:* Given a stop that needs the owner's own sign-in, when the sheet opens, then that stop says the advisor did not walk it and why. (source: craft, for your veto)

**UFR-10.** If a review is in flight when its project takes the release in FR-5, then the review shall finish on the old version or restart once on the new one. (source: Canon 2026-10-09-d6064e1d-14)
  - *Acceptance:* Given such a review, when it restarts, then it restarts once, and the old certification files stay on disk, unread. (source: Canon 2026-10-09-d6064e1d-14)

## Non-functional requirements

- **Reach:** Every sheet and the index can be read and answered at phone width with no sideways scrolling. (source: craft, for your veto)
- **Privacy:** A sheet and the index are private to the owner until the owner shares them, and only the owner's answers count, as FR-55 takes from the review surface spec. (source: Canon 2026-10-05-3dbeb858-40)
- **Reliability:** Each question holds one answer, and a sheet that cannot save says so on the page, as FR-55 takes from the review surface spec. (source: Canon 2026-10-05-3dbeb858-39; board · 3 Big PR sheet)
- **Time:** The loop spends the time the project's calibration calls for, and a complaint about time is answered as FR-77 says. (source: Canon 2026-10-08-d6064e1d-6)

## UI / UX

The approved build board is the design: `board/build-board.html` beside this spec, also at https://claude.ai/artifact/J1c4SduWJVf2CZkrWSNncH. (source: board · 1 The index)
The wording on the board is the product's wording. (source: board · 3 Big PR sheet)
Each artboard is the design for these requirements. (source: craft, for your veto)

- "1 The index": FR-43 to FR-47. (source: craft, for your veto)
- "2 Small sheet and stack sheet": FR-48 and FR-49. (source: craft, for your veto)
- "3 Big PR sheet": FR-50 to FR-69. (source: craft, for your veto)
- "4 Risk and trust": FR-9 to FR-14. (source: craft, for your veto)
- "5 A learning proposal": FR-73 to FR-76. (source: craft, for your veto)

The sheets and the index are built on the plugin's shared review template [cite: plugins/superheroes/theme/review-template.html]. (source: Canon 2026-10-08-d6064e1d-25)

## Definition of done / success

- An owner ships a change in a risk area without reading code. The full lane's panel reviewed the change, a review record exists, the sheet shows the walk and the leftovers, and the merge happens on the saved "Merge" verdict plus "done". (source: framing)
- No review is held up for lacking a certificate. (source: Canon 2026-10-08-d6064e1d-8)
- A bug traced to a reviewed PR is logged as a review escape, and a proposal that rests on it reaches the owner at a gardening pass. (source: framing)

## Assumptions & dependencies

- All six parts ship in one plugin release. (source: Canon 2026-10-10-d6064e1d-3)
- The parts are built in this order: A first, then B, then the owner's leftover review, then E. (source: Canon 2026-10-09-d6064e1d-1)
- Parts C and D together are the owner's leftover review, and each of Part F's requirements is built with the part it describes. (source: craft, for your veto)
- For a reviewer an engine runs, the engine's own record says the reviewer ran, and the review record relies on that record. (source: Canon 2026-10-08-d6064e1d-14; vet round 1)
- The gardening pass, the misses log and the keep-or-retire list already exist, and Part E adds to them. (source: Canon 2026-10-10-d6064e1d-1)
- Round caps and keep-or-retire windows start at today's values, and the build tunes them. (source: framing; craft, for your veto)
- "Break-it tests" is a working name and may change before release. (source: Canon 2026-10-08-d6064e1d-15)

### What this spec changes elsewhere

The approved requirements and shipped rules below change under this spec. (source: vet round 1)
Scheduling the amendments to the approved specs is the advisor's. (source: Canon 2026-10-08-d6064e1d-8)

- **The certification contract spec** (work item `part-b-spec-b-contract-re-derivation`): FR-D1 to FR-D9 and FR-M2. This spec retires the certificate those requirements define. FR-5 says which guard each of its four escape classes keeps. (source: vet round 1) The way back in its FR-D9, the prior plugin version kept runnable for one window after the deletion, is not kept. (source: Canon 2026-10-10-d6064e1d-15)
- **The forward doctrine spec** (work item `part-b-spec-a-forward-doctrine`): FR-A4 and FR-A10, because the misses log and the gardening pass gain review escapes; FR-B3, because reviewer seats join the keep-or-retire list; FR-B4, whose review half this spec designs; FR-E1 item 10, because the threat-model item becomes Risk and trust; FR-F1, because the merge word becomes the saved "Merge" verdict plus "done", and a head move starts the verdict over; and FR-F5 and FR-F8, which describe certification. (source: vet round 1)
- **The review surface spec** (`the-review-surface-d59417`): FR-3 and FR-6, because PR sheets carry their own answers. (source: vet round 1) Its FR-6 is amended to list the four accepted answer patterns, as FR-55 states them. What discovery's sheets offer stays the same. (source: Canon 2026-10-10-d6064e1d-17)
- **The verification strategy spec** (`verification-strategy-for-the-superheroes-repo-c629cd`): FR-18 and its rule on which stage checks what, because the test lens becomes the test role. (source: vet round 1)
- **The converge-faster spec** (`make-the-shared-review-and-fix-loop-converge-faste-4c45d8`): FR-8, FR-11 and its Out of scope. FR-34 and FR-35 replace its full confirmation round before certifying. (source: vet round 1)
- **Shipped rules:** the three batches and batch 3's click list in the owner-decisions reference; the advisor's duty on the owner's merge word; the rows for merge words and the threat model in Canon's contract; the glossary's Misses log entry; the driver mandate, the lane rule and the single-reviewer fallbacks in the review discipline; and the keep-or-retire entries for the seat canary, the round driver core, the certification receipt writer and its four checks. (source: vet round 1)

## Constraints

- No automated gate is added at handback. The advisor's vet carries that check. (source: Canon 2026-10-08-d6064e1d-18)
- That choice is looked at again if vets start sending PRs back for missing review records. (source: Canon 2026-10-08-d6064e1d-18)
- No new review gate runs in a watch-only mode first. (source: Canon 2026-10-08-d6064e1d-10)
- No date is set for the release. (source: Canon 2026-10-10-d6064e1d-3)
- No way back is kept when the parts in FR-5 retire: the prior plugin version is not held runnable afterwards. (source: Canon 2026-10-10-d6064e1d-15)
- The plugin's specs and long-lived records name nothing specific to one project that uses the plugin. (source: Canon 2026-10-09-d6064e1d-10)
- The plugin's default sends every leftover with a real consequence to the owner. (source: Canon 2026-10-08-d6064e1d-26)
- A project's own standing rulings, or a call its owner has ceded, change that default for that project only. (source: Canon 2026-10-09-d6064e1d-4; Canon 2026-10-08-d6064e1d-26)
- The round caps, the stuck-loop stop, the engines' own records and the fixer that works only on its finding are kept. (source: Canon 2026-10-08-d6064e1d-14)

## Out of scope

- A long-running inbox for all the owner's open decisions and merge words. It is its own later piece of work. (source: Canon 2026-10-09-d6064e1d-6)
- Guarding against an agent that deliberately fakes a review record. (source: Canon 2026-10-08-d6064e1d-20)
- A project's error tracker as a source of review escapes. It joins later, where a project has one. (source: Canon 2026-10-09-d6064e1d-11)
- The review of specs. This work changes code review only. (source: craft, for your veto)

## Glossary

- **Review record:** the plain account of one PR's review, written when the review ends. (source: Canon 2026-10-08-d6064e1d-8)
- **Risk area:** a named part of the project where a mistake costs money, customer data, safety, access or something that cannot be undone. (source: Canon 2026-10-09-d6064e1d-2; Canon 2026-10-08-d6064e1d-2)
- **Maker:** any model that built or fixed the product's code under review. A reviewer that writes break-it tests is not a maker. (source: Canon 2026-10-10-d6064e1d-5)
- **Test role:** the full-lane reviewer that writes break-it tests and checks the change's tests. (source: Canon 2026-10-08-d6064e1d-17)
- **Break-it test:** a test a reviewer writes to try to break a change on a named risky scenario. (source: Canon 2026-10-08-d6064e1d-15)
- **Real consequence:** a material consequence, as the plugin's glossary defines it [cite: plugins/superheroes/rubric/glossary.md § Material consequence]. It touches one of the owner categories of the owner-vs-craft line. (source: vet round 1)
- **Craft:** a finding whose only consequence is code quality. Deciding it is a craft call, as the plugin's glossary defines that [cite: plugins/superheroes/rubric/glossary.md § Craft call]. (source: Canon 2026-10-09-d6064e1d-4; vet round 1)
- **Leftover:** a finding with a real consequence that the review left unfixed. It is an owner call [cite: plugins/superheroes/rubric/glossary.md § Owner call] unless a standing ruling already answers it. (source: Canon 2026-10-09-d6064e1d-4; vet round 1)
- **Answer pattern:** one of the four accepted shapes for a question's buttons: agree, pick, check and sign-off. (source: Canon 2026-10-10-d6064e1d-17)
- **Walk:** the part of a PR sheet where the owner tries the change, stop by stop. (source: Canon 2026-10-09-d6064e1d-19)
- **Review escape:** a bug traced to a PR that was reviewed. (source: Canon 2026-10-10-d6064e1d-1)
- **Calibration:** the project's Risk and trust item together with its standing rulings about leftovers. (source: craft, for your veto)

## Amendments

_No amendments since the last full approval._

## Coverage

| Area | Disposition | Show-it? | Where / why |
| --- | --- | --- | --- |
| Empty & first-run | Specify | No | UFR-1: a project with no risk areas set |
| Invalid & malformed input | Specify | No | UFR-1, second acceptance: a Risk and trust item the loop cannot read |
| Boundaries & limits | Specify | No | UFR-2: the round cap. The cap's number is the build's |
| Errors & failures | Specify | Yes | UFR-3, UFR-4, UFR-5, UFR-8 and UFR-9 |
| Access & permissions | Defer-to-build | No | The promise is in the privacy line: only the owner's answers count |
| Duplicates & double-actions | Defer-to-build | No | The promise is in the reliability line: each question holds one answer |
| Conflicting / simultaneous use | Specify | Yes | UFR-6 and UFR-7 |
| Misuse & abuse | N-A | — | Deliberate faking of a review record is out of scope by the owner's ruling |
| Reach (i18n / a11y) | Defer-to-build | Yes | The promise is in the reach line: phone width, no sideways scrolling |
| Wording & tone | Specify | Yes | The board's wording is the product's wording (UI / UX) |
| Workflow shape | Specify | Yes | FR-42 to FR-46 for the batches, FR-48 for the sheet's order |
| Placement & prominence | Specify | Yes | FR-43, FR-47 and FR-69 |
| Limits & defaults | Specify | No | UFR-1, and the default in Constraints that every leftover reaches the owner |
| Tier & access boundaries | N-A | — | One owner per project, and no paid tiers in the plugin |
| Visibility & disclosure | Specify | No | FR-41 and FR-68 |
