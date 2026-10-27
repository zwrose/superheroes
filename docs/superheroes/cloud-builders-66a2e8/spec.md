---
superheroes: doc
schemaVersion: 1
docType: spec
workItem: cloud-builders-66a2e8
issue: null
size: large
status: approved
approved: "2026-10-10"
gates: {review: passed}
producedBy: "the-architect@0.42.0"
created: "2026-10-10"
updated: "2026-10-16"
delivered: "2026-10-16"
deliveryReceipt: "https://github.com/zwrose/superheroes/pull/1880#issuecomment-6205923097"
livesIn: ["plugins/superheroes/skills/configure/reference/set-up.md", "plugins/superheroes/skills/showrunner/reference/orchestration.md", "plugins/superheroes/skills/workhorse/reference/cloud.md", "plugins/superheroes/lib/cloud_builder.py", "plugins/superheroes/lib/cloud_check.py"]
supersededInPart: [{"date": "2026-10-26", "sections": ["UFR-1", "FR-6"], "ruling": "owner's ruling 392 a, 2026-10-26, https://github.com/zwrose/superheroes/issues/695#issuecomment-6416654081 (delivered by #2181): a failed check pauses cloud launches on that account until a check passes; it no longer switches cloud builds off"}]
---
# Cloud builders

## How to read this spec

Every statement ends with its source in plain text. The sources are:

- **board · <artboard>**: the approved build board, saved as `board/build-board.html` beside this
  spec, https://claude.ai/artifact/KB6uNAzk5Ujoa6WzCN8xBy, approved by the owner on 2026-10-10. Its
  artboards are "1 Setup", "2 The setting", "3 The launch report", "4 While a cloud build runs",
  "5 Mid-build trouble", "6 Cleanup" and "7 The gardening pass".
- **journeys**: the journeys board the owner approved on 2026-10-10, saved as `board/journeys.html`
  beside this spec, https://claude.ai/artifact/DZ8VeQQdoFyLYVswRsg5MY.
- **Canon <entry id>**: an owner ruling recorded in the project's Canon.
- **framing**: the framing the owner approved on 2026-10-10.
- **craft, for your veto**: a choice the author made, recorded for the owner's veto.

The requirements are grouped in six parts, A to F, in the order an owner meets them: setup, where
a build runs, a cloud build's life, cleanup, keeping the reviewer pass alive, and keeping the plugin
version in step. (source: craft, for your veto) Parts A to E follow the journeys board. (source: journeys)
Part F follows the owner's ruling on picking up a new plugin version. (source: Canon 2026-10-10-ca3e7e0d-18)

## Purpose

An owner who runs several builds at once is limited by the compute on their own machines. (source: Canon 2026-10-10-ca3e7e0d-4)
This work lets a project's builds run in cloud sessions instead, under the same review, vet and
merge rules as a build on the owner's machine. (source: framing) A single build may run slower in
the cloud, and that is acceptable because more builders can run side by side. (source: Canon 2026-10-10-ca3e7e0d-5)
This is the first of two pieces. (source: Canon 2026-10-10-ca3e7e0d-1) In this piece the owner puts
the reviewer pass and any calibration kept outside the repository in place by hand. (source: Canon 2026-10-10-ca3e7e0d-1)
Hands-off upkeep comes later with its own spec. (source: Canon 2026-10-10-ca3e7e0d-1)

## Who it's for

- As an owner running several builds at once, I want them to run on cloud machines, so my own
  machine stays free and I can run more in parallel. (source: framing)
- As an owner, I want a cloud build held to the same rules as a local one, so moving to the cloud
  costs me nothing in trust. (source: framing)
- As an advisor, I want to launch, watch, answer and clean up a cloud builder the way I do a local
  one, so a wave runs the same wherever its builders are. (source: framing)

## Functional requirements

### Part A: setting a project up for the cloud

**FR-1.** When the owner asks for cloud builds on a project, the plugin shall list the hand steps the owner does once and give the owner the setup text to paste. (source: board · 1 Setup; Canon 2026-10-10-ca3e7e0d-1) The owner picks the new cloud environment by name with Claude Code's environment picker, on the account the builds run on, and the plugin reads the picked environment's id from Claude Code's settings, because no session and no web page shows the id; the check session and every later launch name the environment by that id, so each project keeps its own environment whatever the account's default is. (source: Canon 2026-10-11-dcc2b5e5-5)
  - *Acceptance (Given-When-Then):* Given a project with no cloud setup, when the owner asks to set up cloud builds, then the advisor's message names the hand steps in this order (make a cloud environment and pick it in Claude Code's environment picker, paste the setup text, sign in once to the independent reviewer with a sign-in kept apart from the owner's main one, paste the reviewer pass) and carries the setup text. The sign-in is done once per machine the pass command runs on, before the pass command first works, and the advisor walks the owner through it. (source: board · 1 Setup; Canon 2026-10-11-dcc2b5e5-5; Canon 2026-10-11-dcc2b5e5-1; owner's correction, 2026-10-14)
  - *Acceptance (rule):* The message tells the owner to run the pass command on the owner's machine, which puts the reviewer pass on the owner's clipboard. The plugin never asks the owner to type or paste the environment's id; a pick it cannot confirm is asked for again. (source: board · 1 Setup; Canon 2026-10-11-dcc2b5e5-5)

**FR-2.** The setup text shall carry the plugin at the advisor's version, the tools a build needs, and the project's calibration where the project keeps its calibration outside the repository. (source: journeys; Canon 2026-10-10-ca3e7e0d-1)
  - *Acceptance (rule):* The setup text holds no reviewer pass and no other secret. (source: board · 1 Setup)

**FR-3.** Before the owner starts the hand steps, the plugin shall state where the reviewer pass will sit, that any session started in that cloud environment can read it, that it is a separate sign-in from the owner's main one, that it cannot renew itself, and how long it lasts. (source: board · 1 Setup; craft, for your veto)
  - *Acceptance (rule):* The setup message carries all five facts in the board's wording. (source: board · 1 Setup)

**FR-4.** Before the owner starts the hand steps, the plugin shall state that cloud builders do not receive the owner's personal instructions or personal permission rules. (source: Canon 2026-10-10-ca3e7e0d-14; board · 1 Setup)
  - *Acceptance (rule):* The setup message says cloud builders follow the project's rules and the plugin's rules and nothing else. (source: board · 1 Setup)

**FR-5.** When the owner says the hand steps are done, the plugin shall run one check session in the cloud environment. (source: craft, for your veto; board · 1 Setup)
  - *Acceptance (Given-When-Then):* Given the hand steps are done, when the check session ends, then the advisor reports three results: whether the cloud's plugin version equals the advisor's, whether the cloud's calibration matches the owner's machine, and whether the independent reviewer answered. (source: board · 1 Setup)

**FR-6.** When the check session passes, the plugin shall tell the owner that cloud builds are ready for the project and still switched off. (source: board · 1 Setup)
  - *Acceptance (rule):* The message says how to switch cloud builds on. (source: board · 1 Setup)

**FR-7.** The plugin shall keep, per project, a setting for whether builds run in the cloud by default. (source: Canon 2026-10-10-ca3e7e0d-7)
  - *Acceptance (rule):* The setting is off for every project until the owner switches it on. (source: Canon 2026-10-10-ca3e7e0d-7; board · 2 The setting)

**FR-8.** When the owner switches cloud builds on, the plugin shall confirm it and say how to keep a single build on the owner's machine. (source: board · 2 The setting)
  - *Acceptance (Given-When-Then):* Given a passed check, when the owner says to turn cloud builds on, then the advisor confirms that every build that can run in the cloud will from the next launch, and names the launch word that keeps one build local. (source: board · 2 The setting)

**FR-9.** When the owner switches cloud builds off, the plugin shall run the project's builds on the owner's machine and keep the cloud setup. (source: board · 2 The setting)
  - *Acceptance (rule):* Switching back on needs no new setup. (source: board · 2 The setting)

**FR-10.** The plugin shall treat a project's cloud setup as belonging to the one Claude account it was made on. (source: craft, for your veto; journeys)
  - *Acceptance (Given-When-Then):* Given a project set up on one Claude account, when a build is launched from a different account, then the cloud counts as not ready for that launch. (source: craft, for your veto; board · 3 The launch report)

### Part B: where a build runs

**FR-11.** When a build is launched and the owner's launch word names where it runs, the plugin shall follow the launch word over the project's setting. (source: Canon 2026-10-10-ca3e7e0d-7)
  - *Acceptance (Given-When-Then):* Given cloud builds switched on, when the owner says "this one local" at a launch, then that build runs on the owner's machine and the launch report gives the owner's word as the reason. (source: board · 3 The launch report)

**FR-12.** When a build is launched in a project with cloud builds switched on and no launch word names a place, the plugin shall run the build in the cloud if the build can run there and the cloud is ready. (source: Canon 2026-10-10-ca3e7e0d-7; journeys)
  - *Acceptance (Given-When-Then):* Given cloud builds switched on and the cloud ready, when five builds are launched and three need nothing from the owner's machine, then those three run in the cloud. (source: board · 3 The launch report)

**FR-13.** The advisor shall judge, from a build's order, whether the build needs something only the owner's machine has. (source: craft, for your veto; journeys)
  - *Acceptance (rule):* The advisor judges a build that needs a phone simulator or the owner's signed-in browser as not able to run in the cloud. (source: journeys; Canon 2026-10-10-ca3e7e0d-16)
  - *Acceptance (rule):* The advisor judges every build of a project that keeps its Canon or its specs outside the repository as not able to run in the cloud, and the launch report says that the build needs those files, which only the owner's machine has. (source: Canon 2026-10-10-ca3e7e0d-22)

**FR-14.** The plugin shall count the cloud as ready for a launch only when the reviewer pass is live, the project has a cloud setup on the launching Claude account, the cloud's plugin version equals the advisor's, the cloud's calibration matches the owner's machine, and the cloud platform can be reached. (source: Canon 2026-10-10-ca3e7e0d-8; Canon 2026-10-10-ca3e7e0d-13; craft, for your veto; journeys)
  - *Acceptance (rule):* A launch with any one of the five conditions false is a launch with the cloud not ready. (source: journeys)

**FR-15.** When a launch happens in a project with cloud builds switched on, or sends any build to the cloud, the plugin shall report which builds went to the cloud and which went to the owner's machine. (source: Canon 2026-10-10-ca3e7e0d-7; journeys; board · 3 The launch report)
  - *Acceptance (rule):* The launch report names every launched build under one of the two places. (source: board · 3 The launch report)

**FR-16.** For each build that ran on the owner's machine although the project's setting or the owner's launch word pointed it at the cloud, the launch report shall state the reason in the board's wording. (source: board · 3 The launch report; journeys)
  - *Acceptance (rule):* The reason is one of the eight on the board's list of reasons. (source: board · 3 The launch report)

### Part C: a cloud build's life

**FR-17.** A cloud build shall follow the same order, review rules, advisor's vet and merge rules as a build on the owner's machine. (source: framing; journeys)
  - *Acceptance (Given-When-Then):* Given a build-ready issue, when it is built in the cloud, then its PR carries the same review record and receipts a local build's PR carries, and the advisor vets it by the same steps. (source: journeys)

**FR-18.** A cloud build shall need no step from the owner between its launch and its ready PR. (source: craft, for your veto)
  - *Acceptance (Given-When-Then):* Given the cloud is ready, when a build that needs no owner decision is launched in the cloud, then it reaches a ready PR with no prompt, sign-in or other action from the owner. (source: craft, for your veto)

**FR-19.** The plugin shall record and count a cloud lane as it records and counts any lane. (source: journeys; board · 4 While a cloud build runs)
  - *Acceptance (rule):* Wherever the advisor lists lanes, a cloud lane appears with the word "cloud" beside it. (source: board · 4 While a cloud build runs)

**FR-20.** The cloud builder's first comment on its issue shall state that it is a cloud build, the plugin version it runs, and that its commits carry the cloud's own author name while the PR is under the owner's name. (source: board · 4 While a cloud build runs; craft, for your veto)
  - *Acceptance (rule):* The intake comment carries those three facts. (source: board · 4 While a cloud build runs)

**FR-21.** When a cloud builder needs the advisor, the builder shall post its question as a comment on its issue. (source: Canon 2026-10-13-dcc2b5e5-1; board · 4 While a cloud build runs)
  - *Acceptance (rule):* The comment is headed as a builder note for the advisor and says the builder is waiting. (source: board · 4 While a cloud build runs)
  - *Acceptance (rule):* On a public repository the comment is public, as builder comments already are. (source: board · 4 While a cloud build runs)

**FR-22.** When a cloud builder posts a question, the advisor shall answer the builder directly. (source: journeys; board · 4 While a cloud build runs)
  - *Acceptance (Given-When-Then):* Given the advisor is watching the wave, when a cloud builder posts a builder note, then the advisor's answer reaches the builder with no step from the owner. (source: journeys)

**FR-23.** While a cloud build runs, the plugin shall keep it running when the owner's machine is asleep or off. (source: craft, for your veto; board · 4 While a cloud build runs)
  - *Acceptance (Given-When-Then):* Given a cloud build in progress, when the owner's machine sleeps, then the build carries on to its next point of needing the advisor. (source: board · 4 While a cloud build runs)

**FR-24.** While a cloud builder builds, it shall push its work to the repository often. (source: journeys)
  - *Acceptance (rule):* A builder that stops mid-build has pushed work for the advisor to recover the lane from. (source: journeys; board · 5 Mid-build trouble)
  - *Acceptance (rule):* At handback, the review record and the receipts are on the PR, and nothing the vet needs exists only on the cloud machine. (source: journeys)

**FR-25.** Every independent review seat of a cloud build, on every lane, shall run through the reviewer pass. (source: Canon 2026-10-10-ca3e7e0d-2; journeys)
  - *Acceptance (rule):* The plugin does not drop the review of a cloud build and does not treat it as second class. (source: Canon 2026-10-10-ca3e7e0d-2)

**FR-26.** A cloud builder shall not merge. (source: framing; journeys)
  - *Acceptance (rule):* A cloud build's PR merges only on the owner's merge word, as any build's does. (source: journeys)

**FR-27.** A cloud builder shall read the project's outside-the-repository calibration from the copy the setup placed, and shall not change calibration. (source: Canon 2026-10-10-ca3e7e0d-1; craft, for your veto)
  - *Acceptance (rule):* Nothing a cloud builder does alters the calibration on the owner's machine. (source: craft, for your veto)

The guardian's skill says a cloud session cannot reach the project store kept outside the repository [cite: plugins/superheroes/skills/guardian/SKILL.md § store a cloud session cannot reach]. That stays true: a cloud builder reads the placed copy and not the store itself. (source: craft, for your veto)

### Part D: cleaning up a finished cloud builder

**FR-28.** When a cloud builder's PR is merged, the advisor shall ask that builder to archive its own session. (source: Canon 2026-10-15-dcc2b5e5-1; board · 6 Cleanup)
  - *Acceptance (Given-When-Then):* Given a merged cloud build, when the advisor has asked the builder to archive itself, then the owner sees the platform's one prompt for that session when the builder's session can archive itself; otherwise the builder says so on its issue. (source: board · 6 Cleanup; owner's ruling "125 a", 2026-10-15)

**FR-29.** When the advisor has asked a cloud builder to archive itself, the advisor shall tell the owner to expect one prompt and to tap Allow once if the builder's session has a tool to archive itself, and otherwise that the builder will say so on its issue and the session stays listed until the owner archives it by hand. (source: board · 6 Cleanup; owner's ruling "124 a", 2026-10-14)
  - *Acceptance (rule):* The advisor's message names the merged build, the one tap when the builder can archive itself, and the hand archive when it cannot. (source: board · 6 Cleanup; owner's ruling "124 a", 2026-10-14)

**FR-30.** When a cloud build's PR is merged, the plugin shall leave nothing behind for that build except its session and its lane record: no branch on the repository, and no checkout or worktree on the owner's machine. (source: Canon 2026-10-15-dcc2b5e5-2; board · 6 Cleanup)
  - *Acceptance (rule):* The archive prompt, or a hand archive when there is no prompt, is the only step left to the owner. (source: Canon 2026-10-15-dcc2b5e5-1; owner's ruling "125 a", 2026-10-15)

**FR-31.** While a cloud build's PR is neither merged nor closed, the plugin shall keep the build's pushed branch. (source: craft, for your veto)
  - *Acceptance (rule):* The plugin does not clean up a builder that hands back or parks. The builder's pushed work stays for the vet, a renewed review or a recovery. (source: craft, for your veto; board · 5 Mid-build trouble)

**FR-32.** When a cloud build's PR is closed unmerged, the plugin shall run the same cleanup as after a merge. (source: craft, for your veto)
  - *Acceptance (Given-When-Then):* Given a cloud build whose PR is closed unmerged, when the advisor closes out the build, then the advisor asks the builder to archive itself, and nothing else is left behind, as FR-30 says. (source: craft, for your veto)

### Part E: keeping the reviewer pass alive

The gardening pass's duties are a closed list [cite: plugins/superheroes/skills/showrunner/reference/owner-decisions.md § The seven duties, a closed list]. This spec adds one duty to that list, for projects that have a cloud setup. (source: Canon 2026-10-10-ca3e7e0d-12) The new duty is appended as duty 8, so the seven existing duties keep their numbers and the list stays closed at eight. (source: craft, for your veto)

**FR-33.** When a gardening pass runs in a project that has a cloud setup, the advisor shall report how many days the reviewer pass has left and the date it lapses. (source: Canon 2026-10-10-ca3e7e0d-12; board · 7 The gardening pass)
  - *Acceptance (rule):* The line reads as the board draws it, with the days left and the date. (source: board · 7 The gardening pass)

**FR-34.** When the reviewer pass will lapse before the next gardening pass is owed, the advisor shall tell the owner to renew it at this pass and say how. (source: Canon 2026-10-10-ca3e7e0d-12; board · 7 The gardening pass)
  - *Acceptance (Given-When-Then):* Given a pass with three days left and a gardening pass owed every seven days, when the gardening pass runs, then the line is marked "Renew now", names the two hand steps (run the pass command, and paste the new pass into the cloud environment), and says to sign the reviewer in again if the date does not move. (source: board · 7 The gardening pass; owner's ruling "123 a", 2026-10-14)

**FR-35.** The plugin shall give no warning ahead of the reviewer pass lapsing between gardening passes. (source: Canon 2026-10-10-ca3e7e0d-12; board · 7 The gardening pass)
  - *Acceptance (rule):* Between passes, nothing tells the owner the pass is about to lapse. Once it has lapsed, the launch report's reason, the line UFR-6 repeats and a parked PR's notice under UFR-8 still appear. (source: board · 7 The gardening pass; board · 3 The launch report; board · 5 Mid-build trouble)

**FR-36.** When the reviewer pass is renewed, the advisor shall send each PR that UFR-7 parked and that is still open back for review. (source: board · 5 Mid-build trouble)
  - *Acceptance (Given-When-Then):* Given a PR parked because its review could not run, when the owner renews the pass, then the advisor sends that PR back for its review with no further word from the owner. (source: board · 5 Mid-build trouble)
  - *Acceptance (rule):* The advisor does not send back a parked PR that was closed before the renewal. (source: craft, for your veto)
  - *Acceptance (rule):* The advisor does not send back a parked PR that the owner has already let through by the review spec's own rules. (source: craft, for your veto)

### Part F: keeping the plugin version in step

**FR-37.** When the advisor runs a newer plugin version than the cloud setup was made with, the cloud shall pick up the advisor's version with no step from the owner, where the cloud platform allows it. (source: Canon 2026-10-10-ca3e7e0d-18)
  - *Acceptance (Given-When-Then):* Given a cloud setup made on an earlier plugin version and a platform that allows the pickup, when a build is launched, then the cloud builder runs the advisor's version and the owner pastes nothing. (source: Canon 2026-10-10-ca3e7e0d-18)
  - *Acceptance (rule):* Where the platform does not allow the pickup, UFR-5 applies and the launch report tells the owner to paste new setup text. (source: Canon 2026-10-10-ca3e7e0d-18; board · 3 The launch report)

## When things go wrong (significant unhappy paths)

**UFR-1.** If the check session fails, then the plugin shall keep cloud builds switched off and name the part that failed and its fix. (source: board · 1 Setup; craft, for your veto)
  - *Acceptance:* Given a reviewer pass that was pasted wrong, when the check session ends, then the advisor says the reviewer did not answer, says cloud builds stay off, and says to paste a fresh pass and check again. (source: board · 1 Setup)

**UFR-2.** If the owner asks to switch cloud builds on before a check has passed on this Claude account, then the plugin shall refuse and offer the setup. (source: board · 2 The setting; craft, for your veto)
  - *Acceptance:* Given no cloud setup on this account, when the owner says to turn cloud builds on, then the advisor says they can't be switched on yet and how to start setup. (source: board · 2 The setting)

**UFR-3.** If a build that the project's setting or the owner's launch word points at the cloud needs something only the owner's machine has, then the plugin shall run it on the owner's machine and name what it needs in the launch report. (source: Canon 2026-10-10-ca3e7e0d-7; journeys; board · 3 The launch report)
  - *Acceptance:* Given a build that needs the phone simulator, when it is launched, then it runs on the owner's machine and the launch report says it needs the phone simulator. (source: board · 3 The launch report)
  - *Acceptance (rule):* A launch word that names the cloud overrides the project's setting and does not override what the build needs. (source: journeys)

**UFR-4.** If the cloud is not ready at launch, then the plugin shall run the build on the owner's machine and state the reason and its fix in the launch report. (source: Canon 2026-10-10-ca3e7e0d-8; board · 3 The launch report)
  - *Acceptance:* Given a lapsed reviewer pass, when four builds are launched, then all four run on the owner's machine and the launch report says the pass has lapsed and how to renew it. (source: Canon 2026-10-10-ca3e7e0d-8; board · 3 The launch report)
  - *Acceptance (rule):* The plugin never holds a build and never drops a build because the cloud is not ready. (source: journeys)

**UFR-5.** If the cloud's plugin version differs from the advisor's, then the plugin shall run the build on the owner's machine and name both versions in the launch report. (source: Canon 2026-10-10-ca3e7e0d-13; board · 3 The launch report)
  - *Acceptance (rule):* A cloud builder never runs on an older copy of the plugin than the advisor's. (source: Canon 2026-10-10-ca3e7e0d-13)

**UFR-6.** If builds are running on the owner's machine because the cloud is not ready, then the advisor shall repeat the reason and its fix at the top of each later message until it is fixed. (source: Canon 2026-10-10-ca3e7e0d-8; board · 3 The launch report)
  - *Acceptance:* Given a version mismatch reported at launch, when the advisor next writes to the owner, then the message opens with the "Still on your machine" line. (source: board · 3 The launch report)

**UFR-7.** If a cloud build's independent review cannot run because the reviewer pass has lapsed, then the builder shall park the PR with its review recorded as not run. (source: Canon 2026-10-10-ca3e7e0d-2; board · 5 Mid-build trouble)
  - *Acceptance:* Given a cloud build whose pass lapses before its review, when the builder reaches the review, then the builder's comment on the PR says the review did not run, that the work is pushed, and that the PR is not ready. (source: board · 5 Mid-build trouble)
  - *Acceptance (rule):* A review that finished before the pass lapsed stays as it was recorded. (source: craft, for your veto)
  - *Acceptance (rule):* A PR parked this way follows the approved review spec's rules for a review that did not run, the owner's own ways past them included. No session picks a reviewer from a maker's model family on its own. (source: Canon 2026-10-10-ca3e7e0d-21; Canon 2026-10-10-d6064e1d-12)
  - *Acceptance (rule):* The cloud is not stricter than a build on the owner's machine here. (source: Canon 2026-10-10-ca3e7e0d-21)

The approved review spec already says what happens when a planned reviewer could not run [cite: docs/superheroes/risk-calibrated-review-that-learns-dec0af/spec.md § UFR-3], and treats a review as not run when no reviewer from a different model family can run [cite: docs/superheroes/risk-calibrated-review-that-learns-dec0af/spec.md § UFR-4]. UFR-7 applies those rules to a review that a lapsed pass stops from running, and changes neither. (source: craft, for your veto)

**UFR-8.** If UFR-7 parks a cloud build's PR, then the advisor shall tell the owner that the PR is parked and that renewing the pass lets it go back for review. (source: board · 5 Mid-build trouble)
  - *Acceptance:* Given a PR parked by UFR-7, when the advisor next writes to the owner, then the message names the PR, the reason and the renewal. (source: board · 5 Mid-build trouble)
  - *Acceptance (rule):* The advisor reports a review that did not run for any other reason as the review rules already say, with no advice to renew the pass. (source: craft, for your veto)

**UFR-9.** If a cloud builder stops or stalls, then the advisor shall recover the lane at once from its pushed work, routing the recovery as a launch is routed. (source: craft, for your veto; board · 5 Mid-build trouble)
  - *Acceptance:* Given a stopped cloud builder and the cloud ready, when the advisor recovers the lane, then the new builder runs in the cloud and starts from the pushed work. (source: board · 5 Mid-build trouble)
  - *Acceptance (rule):* A recovery never leaves two builders working one issue. (source: craft, for your veto)

**UFR-10.** If a cloud builder is recovered, then the advisor shall tell the owner when the builder stopped, where the lane was recovered, and how much work is being redone. (source: board · 5 Mid-build trouble)
  - *Acceptance (rule):* The work redone is the work since the builder's last push that could not be saved. (source: board · 5 Mid-build trouble; Canon 2026-10-10-ca3e7e0d-17)

**UFR-11.** If the owner does not answer the archive prompt, then the plugin shall leave the session listed and carry on. (source: Canon 2026-10-15-dcc2b5e5-1; board · 6 Cleanup)
  - *Acceptance (rule):* The plugin sends no reminder about an unanswered archive prompt. (source: board · 6 Cleanup)

**UFR-12.** If a cloud builder posts a question while the advisor is away, then the question shall wait on the issue until the advisor is back. (source: Canon 2026-10-13-dcc2b5e5-1; board · 4 While a cloud build runs)
  - *Acceptance:* Given the advisor is not running, when a cloud builder's question gets no answer, then the builder parks with its work pushed, and the advisor answers and resumes the lane when it is back. (source: Canon 2026-10-13-dcc2b5e5-1)

**UFR-13.** If a cloud builder stops with work it has not pushed, then the advisor shall first try to get that work pushed. (source: Canon 2026-10-10-ca3e7e0d-17)
  - *Acceptance:* Given a stalled cloud builder that still answers, when the advisor recovers the lane, then the advisor asks the builder once to push its work, and the new builder starts from what was pushed. (source: Canon 2026-10-10-ca3e7e0d-17; Canon 2026-10-10-ca3e7e0d-20)
  - *Acceptance (rule):* Work that cannot be saved is redone, and the advisor says how much. (source: Canon 2026-10-10-ca3e7e0d-17)
  - *Acceptance (rule):* A build that never pushed starts again from the beginning. (source: Canon 2026-10-10-ca3e7e0d-17)

## UI / UX

The approved build board is the design: `board/build-board.html` beside this spec,
https://claude.ai/artifact/KB6uNAzk5Ujoa6WzCN8xBy. (source: board · 1 Setup) This piece has no
screens of its own. The board draws the wording the owner reads, on seven artboards: "1 Setup",
"2 The setting", "3 The launch report", "4 While a cloud build runs", "5 Mid-build trouble",
"6 Cleanup" and "7 The gardening pass". (source: board · 1 Setup) The archive prompt on "6 Cleanup"
is the platform's own wording and is drawn as it appears. (source: board · 6 Cleanup) The board draws the case where the builder's
session can archive itself; when it cannot, there is no prompt, the builder says so on its issue,
and the owner archives the session by hand, as FR-28 to FR-30 say. Where a later ruling changed the
wording the board draws, this spec's text governs and the approved board is not redrawn: the cleanup
prompt above, the "Renew now" line's sign-in sentence (FR-34) on "7 The gardening pass", and the
reviewer sign-in being once per machine (FR-1) on "1 Setup". (source: owner's rulings "123 a" and "124 a", 2026-10-14; owner's ruling "129 a", 2026-10-15)

## Definition of done / success

- An owner can set a project up for the cloud in one sitting, switch cloud builds on, and launch a
  wave in which every build that can run in the cloud does. (source: framing; journeys)
- Those builds reach ready PRs with real independent reviews, and the owner's machine does none of
  their build work. (source: framing; Canon 2026-10-10-ca3e7e0d-2)
- The work ships once the build has tested what it can test. Nothing has to be shown in a real wave
  first. (source: Canon 2026-10-10-ca3e7e0d-15)
- The build tests each of these where a test can reach it: several cloud builders at once, a
  full-size build, a builder's question answered mid-build, a stopped builder recovered, a project
  that keeps its calibration outside the repository, and a lapsed pass sending builds to the
  owner's machine. (source: craft, for your veto)
- What a test cannot reach is learned in use and fixed as it comes up. (source: Canon 2026-10-10-ca3e7e0d-15)

## Assumptions & dependencies

- The owner's Claude plan offers cloud sessions, and the project's repository is connected to
  them. (source: framing)
- The owner has a sign-in for an independent reviewer that can be placed in the cloud as a pass.
  The pass used in the discovery's pilot lasts 10 days. (source: board · 1 Setup; journeys)
- The platform lets a session archive itself only when a person approves the prompt. (source: journeys; board · 6 Cleanup)
- The platform delivers a message to a running cloud session, waking an idle one, only from a
  session on the same Claude account, and does not deliver one from a cloud session to any session.
  Cloud builders may run on a different account from the advisor, so the advisor's messages reach
  them through a standing relay session on the builders' account: a background session on Haiku 5.5
  that forwards the advisor's text, checked for exact text. FR-22, FR-28 and UFR-13 rely on the
  first, and FR-21 uses a comment because of the second. (source: spike #1769's findings; Canon 2026-10-11-dcc2b5e5-3)
- This work builds on the approved review spec's release, which is not built yet. The review record
  that FR-17, FR-24 and UFR-7 name comes from that release
  [cite: docs/superheroes/risk-calibrated-review-that-learns-dec0af/spec.md § FR-3]. (source: craft, for your veto; Canon 2026-10-10-d6064e1d-3)
- Whether the cloud platform lets the cloud pick up a new plugin version by itself is not yet
  proven. FR-37 states the aim, and the pasted setup text is the fallback. (source: Canon 2026-10-10-ca3e7e0d-18; board · 3 The launch report)

## Constraints

- Nothing in this piece depends on the owner having more than one Claude account. (source: Canon 2026-10-05-3dbeb858-48)
- The reviewer pass comes from the owner's ordinary sign-in to the independent reviewer. Separately
  paid business access tokens are ruled out as the way a cloud builder signs in. (source: Canon 2026-10-10-ca3e7e0d-3)
- The plugin sets no ceiling on how many cloud builders run at once. (source: craft, for your veto)
- This piece adds no recovery machinery beyond what these requirements name. Cloud builders are
  assumed reliable, and more recovery is built only after failures show what shape it needs. (source: Canon 2026-10-10-ca3e7e0d-20)
- A cloud builder runs on the project's rules and the plugin's rules only. (source: Canon 2026-10-10-ca3e7e0d-14)
- Cleanup of a finished cloud builder takes one tap from the owner when the builder's session can archive itself, and otherwise a hand archive of that session, for now. (source: Canon 2026-10-15-dcc2b5e5-1)

## Out of scope

- Hands-off upkeep of the reviewer pass and of the calibration copy: renewing and delivering them
  with no hand step. It is the later piece. (source: Canon 2026-10-10-ca3e7e0d-1; Canon 2026-10-10-ca3e7e0d-18)
  Until that piece ships, a project that keeps its calibration outside the repository meets a hand
  step after every calibration change: the cloud's copy is then out of date, FR-14 counts the cloud
  as not ready, and every build runs on the owner's machine until the owner pastes new setup text.
  That recurs with each calibration update, and with each sitting that changes calibration. (source: craft, for your veto; Canon 2026-10-10-ca3e7e0d-1)
- The advisor, discovery and the detective in the cloud. They stay on the owner's machine. (source: Canon 2026-10-10-ca3e7e0d-16)
- Any check that needs a phone or the owner's signed-in browser. (source: Canon 2026-10-10-ca3e7e0d-16)
- Cleanup with no tap from the owner. (source: Canon 2026-10-15-dcc2b5e5-1)
- A build machine the owner hosts. (source: Canon 2026-10-10-ca3e7e0d-6)
- Carrying a project's Canon or specs to the cloud when the project keeps them outside the
  repository. For now such a project's builds run on the owner's machine. (source: Canon 2026-10-10-ca3e7e0d-22)

## Glossary

- **Cloud build, cloud builder, cloud lane:** a build that runs in a cloud session, the builder
  doing it, and its lane in the advisor's records. (source: framing)
- **Cloud environment:** the place on the cloud platform where the owner pastes the setup text and
  the reviewer pass. (source: board · 1 Setup)
- **Cloud setup:** a project's cloud environment after a check session has passed. (source: board · 1 Setup)
- **Setup text:** the block the plugin writes for the owner to paste into the cloud environment. (source: board · 1 Setup)
- **Reviewer pass:** the sign-in the owner places in the cloud environment so the independent
  reviewer can run there. (source: board · 1 Setup)
- **Check session:** the one short cloud session that proves a cloud setup. (source: board · 1 Setup)
- **Launch report:** the advisor's message after a launch, saying which build went where. (source: board · 3 The launch report)
- **Launch word:** what the owner says at a launch to name where a build runs. (source: Canon 2026-10-10-ca3e7e0d-7)

## Amendments

- **2026-10-10 (owner-stamped, substantive):** cloud setup tells the owner to make the new cloud
  environment the account's default, so the check session lands in it and the plugin reads the
  environment's id from that session instead of asking the owner for it (owner's ruling "25 c",
  Canon 2026-10-10-dcc2b5e5-12). FR-1's statement, its hand-step list and its pass-command rule
  say so, and the build board's "1 Setup" artboard matches. Sections touched: frontmatter, Part A ·
  Setting a project up for the cloud (FR-1), UI / UX (board · 1 Setup), Amendments.
- **2026-10-11 (owner-stamped, substantive):** the reviewer pass is made from a reviewer sign-in
  kept apart from the owner's main one, so the owner signs in to it once, before the pass command
  first works. Cloud setup shows that sign-in as its own hand step before the pass, once per
  account, and the advisor walks the owner through it (owner's ruling "27 a", Canon
  2026-10-11-dcc2b5e5-1). FR-1's hand-step list says so, and the build board's "1 Setup" artboard
  matches. Sections touched: frontmatter, Part A · Setting a project up for the cloud (FR-1),
  UI / UX (board · 1 Setup), Amendments.

- **2026-10-11 (owner-stamped, substantive):** the default-environment step holds for the setup
  only: the check session lands in the default and the plugin reads the environment's id from it,
  and every later launch names its environment by that id, so the owner may switch the default
  back afterwards, and an account with several projects keeps one environment per project
  (owner's word "a" on the advisor's clarification of "25 c", Canon 2026-10-11-dcc2b5e5-2).
  FR-1's statement and hand-step list say so, and the build board's "1 Setup" artboard matches.
  Sections touched: Part A · Setting a project up for the cloud (FR-1), UI / UX (board · 1 Setup),
  Amendments.
- **2026-10-11 (owner-stamped, substantive):** no session can read a cloud environment's id
  (cloud C4's probe sessions, #1745) and no web page shows it, but Claude Code's environment picker
  (`/remote-env`) does, and saves the pick in Claude Code's settings. So the owner picks the new
  environment by name in that picker, on the account the builds run on; the plugin reads the picked
  id from the settings, treating an unchanged setting as no pick and asking again; the check session
  and every later launch name the environment by that id; and the step that made the environment
  the account's default only so the check could find it is retired (owner's rulings "35 a" and "37
  b", Canon 2026-10-11-dcc2b5e5-4 and -5; -5 supersedes -4, which had the owner copy the id from a
  page that does not show it; together they supersede 2026-10-10-dcc2b5e5-12 and
  2026-10-11-dcc2b5e5-2). FR-1's statement, its hand-step list and its
  rule say so, and the build board's "1 Setup" artboard matches. Sections touched: Part A ·
  Setting a project up for the cloud (FR-1), UI / UX (board · 1 Setup), Amendments.
- **2026-10-11 (owner-stamped, substantive):** cloud builders may run on a different Claude account
  from the advisor. A cloud session takes messages only from sessions on its own account, so the
  advisor's messages reach a cloud builder through a standing relay session on the builders'
  account (a background session on Haiku 5.5), checked for exact text; replies still come back as
  comments on the builder's issue (owner's ruling "33 a" on spike #1769's findings, Canon
  2026-10-11-dcc2b5e5-3). The messaging assumption says so. Sections touched: Assumptions &
  dependencies, Amendments.
- **2026-10-14 (owner-stamped, substantive):** the owner's archive prompt is conditional: the
  advisor tells the owner to expect one prompt and tap Allow once only when the builder's session
  has a tool to archive itself; otherwise the builder says so on its issue and the owner archives
  the session by hand (owner's ruling "124 a", collector item 124). FR-29's statement and
  acceptance say so; FR-28 is unchanged. Sections touched: Part D · cleaning up a finished cloud
  builder (FR-29), Amendments.
- **2026-10-15 (owner-stamped, substantive):** FR-28's and FR-30's acceptance follow FR-29's
  conditional form: the owner sees the platform's one prompt only when the builder's session can
  archive itself, otherwise the builder says so on its issue, and the archive prompt, or a hand
  archive when there is no prompt, is the only step left to the owner (owner's ruling "125 a",
  collector item 125). FR-28's and FR-30's statements are unchanged. Sections touched: Part D ·
  cleaning up a finished cloud builder (FR-28, FR-30), Amendments.
- **2026-10-15 (owner-stamped, substantive):** the cleanup assumption follows the same conditional
  form: one tap from the owner when the builder's session can archive itself, otherwise a hand
  archive of that session, for now (owner's ruling "126 a", collector item 126). Its source moves
  from Canon 2026-10-10-ca3e7e0d-11 to 2026-10-15-dcc2b5e5-1, which supersedes it, and
  2026-10-15-dcc2b5e5-2 supersedes 2026-10-10-ca3e7e0d-9 to match; every source citing the
  superseded entries now cites their replacements (FR-28, FR-30, UFR-11, Out of scope). Sections
  touched: Part D · cleaning up a finished cloud builder (FR-28, FR-30 sources), UFR-11's source,
  Constraints, Out of scope, Amendments. Amendments since approval now number more than five:
  the consolidation re-read is outstanding and owed by the advisor, and the owner's re-stamp of the
  consolidated body is outstanding and owed by the owner (collector item 127).
- **2026-10-15 (owner-stamped, substantive):** the consolidation re-read (owner's ruling "2 a",
  collector item 127) is done, and its findings are absorbed (owner's ruling "129 a", collector item
  129). FR-34's acceptance adds the sentence owner's ruling "123 a" put on the "Renew now" line: sign
  the reviewer in again if the date does not move. FR-1's acceptance, set-up.md and the setup message say the
  reviewer sign-in is done once per machine the pass command runs on, not once per account (the
  owner's correction, 2026-10-14). UI/UX says the cleanup board draws the case where the builder can archive itself, that
  the hand archive applies otherwise, and that where a later ruling changed a board's wording the
  spec's text governs and the approved board is not redrawn. FR-21 and UFR-12 now cite the owner's headless ruling
  (Canon 2026-10-13-dcc2b5e5-1) instead of "craft, for your veto". The frontmatter date is current.
  The re-read found nothing else to change: the auto-mode ruling (Canon 2026-10-12-dcc2b5e5-1) is
  consistent with the spec and needs no amendment. The owner's re-stamp of the consolidated body is
  still outstanding and is owed by the owner at the cloud closure sitting. Sections touched:
  frontmatter, Part A · Setting a project up for the cloud (FR-1), Part C (FR-21), Part E (FR-34),
  UFR-12, UI / UX, Amendments.
- **2026-10-16 (owner re-stamp):** the owner re-stamped the consolidated body after the
  consolidation re-read and its amendment (owner's ruling "132 a", collector item 132), so the
  re-stamp the 2026-10-15 entries left outstanding is given. At the same sitting the owner accepted
  full delivery on the closure receipt, with two live checks deferred to their first occurrence: a
  builder archiving itself after a real merge, and a review resuming after the reviewer pass lapses.
  The validation run's self-archive showed no prompt where FR-28, FR-29 and the assumptions
  promise one; the owner ruled to confirm that at the first real archive before amending (owner's
  ruling "131 b", collector item 131). No requirement text changes in this entry. Sections touched:
  frontmatter, Amendments.

## Coverage

| Area | Disposition | Show-it? | Where / why |
| --- | --- | --- | --- |
| Empty & first-run | Specify | Yes | FR-1 to FR-6, UFR-2: the setup sitting and asking before setup is done |
| Invalid & malformed input | Specify | No | UFR-1: a pass pasted wrong fails the check, which names the part and the fix |
| Boundaries & limits | Specify | No | Constraints: no ceiling on cloud builders; FR-33: the pass's remaining life |
| Errors & failures | Specify | Yes | UFR-4 to UFR-10 and UFR-13: the cloud not ready, a lapsed pass mid-build, a stopped builder, unpushed work |
| Access & permissions | Specify | No | FR-3: who can read the reviewer pass; FR-10: one Claude account per cloud setup |
| Duplicates & double-actions | Defer-to-build | No | UFR-9: a recovery never leaves two builders on one issue; the mechanism is the build's |
| Conflicting / simultaneous use | Specify | No | FR-27: a cloud builder does not change calibration |
| Misuse & abuse | N-A | — | The project's stated threat model excludes malicious code; FR-3 discloses who can read the pass |
| Reach (i18n / a11y) | N-A | — | No screens of its own; the wording is plain chat text and comments |
| Wording & tone | Specify | Yes | The build board's wording, all seven artboards |
| Workflow shape | Specify | No | The journeys board; parts A to E follow it, and Part F follows Canon 2026-10-10-ca3e7e0d-18 |
| Placement & prominence | Specify | Yes | FR-15, FR-19, UFR-6: the launch report, the cloud mark, the line at the top of later messages |
| Limits & defaults | Specify | No | FR-7: off until switched on; FR-12: the cloud is the default once on |
| Tier & access boundaries | N-A | — | Works the same for every owner whose plan offers cloud sessions |
| Visibility & disclosure | Specify | Yes | FR-3, FR-4, FR-20, FR-21: the pass, personal rules, the cloud's author name, public builder notes |
