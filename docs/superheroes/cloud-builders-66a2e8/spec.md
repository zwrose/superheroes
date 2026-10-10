---
superheroes: doc
schemaVersion: 1
docType: spec
workItem: cloud-builders-66a2e8
issue: null
size: large
status: draft
gates: {review: pending}
producedBy: "the-architect@0.42.0"
created: "2026-10-10"
updated: "2026-10-10"
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
version in step. (source: journeys; Canon 2026-10-10-ca3e7e0d-18)

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

**FR-1.** When the owner asks for cloud builds on a project, the plugin shall list the hand steps the owner does once and give the owner the setup text to paste. (source: board · 1 Setup; Canon 2026-10-10-ca3e7e0d-1)
  - *Acceptance (Given-When-Then):* Given a project with no cloud setup, when the owner asks to set up cloud builds, then the advisor's message names three hand steps (make a cloud environment, paste the setup text, paste the reviewer pass) and carries the setup text. (source: board · 1 Setup)
  - *Acceptance (rule):* The message tells the owner to run the pass command on the owner's machine, which puts the reviewer pass on the owner's clipboard. (source: board · 1 Setup)

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

**FR-21.** When a cloud builder needs the advisor, the builder shall post its question as a comment on its issue. (source: craft, for your veto; board · 4 While a cloud build runs)
  - *Acceptance (rule):* The comment is headed as a builder note for the advisor and says the builder is waiting. (source: board · 4 While a cloud build runs)
  - *Acceptance (rule):* On a public repository the comment is public, as builder comments already are. (source: board · 4 While a cloud build runs)

**FR-22.** When a cloud builder posts a question, the advisor shall answer the builder directly. (source: journeys; board · 4 While a cloud build runs)
  - *Acceptance (Given-When-Then):* Given the advisor is watching the wave, when a cloud builder posts a builder note, then the advisor's answer reaches the builder with no step from the owner. (source: journeys)

**FR-23.** While a cloud build runs, the plugin shall keep it running when the owner's machine is asleep or off. (source: craft, for your veto; board · 4 While a cloud build runs)
  - *Acceptance (Given-When-Then):* Given a cloud build in progress, when the owner's machine sleeps, then the build carries on to its next point of needing the advisor. (source: board · 4 While a cloud build runs)

**FR-24.** While a cloud builder builds, it shall push its work to the repository often. (source: journeys)
  - *Acceptance (rule):* A builder that stops mid-build has pushed work for the advisor to recover the lane from. (source: journeys; board · 5 Mid-build trouble)
  - *Acceptance (rule):* At handback, the review record and the receipts are on the PR, and nothing the vet needs exists only on the cloud machine. (source: journeys)

**FR-25.** The independent reviewer of a cloud build shall run through the reviewer pass. (source: Canon 2026-10-10-ca3e7e0d-2; journeys)
  - *Acceptance (rule):* The plugin does not drop the review of a cloud build and does not treat it as second class. (source: Canon 2026-10-10-ca3e7e0d-2)

**FR-26.** A cloud builder shall not merge. (source: framing; journeys)
  - *Acceptance (rule):* A cloud build's PR merges only on the owner's merge word, as any build's does. (source: journeys)

**FR-27.** A cloud builder shall read the project's outside-the-repository calibration from the copy the setup placed, and shall not change calibration. (source: Canon 2026-10-10-ca3e7e0d-1; craft, for your veto)
  - *Acceptance (rule):* Nothing a cloud builder does alters the calibration on the owner's machine. (source: craft, for your veto)

The guardian's skill says a cloud session cannot reach the project store kept outside the repository [cite: plugins/superheroes/skills/guardian/SKILL.md § store a cloud session cannot reach]. That stays true: a cloud builder reads the placed copy and not the store itself. (source: craft, for your veto)

### Part D: cleaning up a finished cloud builder

**FR-28.** When a cloud builder's PR is merged, the advisor shall ask that builder to archive its own session. (source: Canon 2026-10-10-ca3e7e0d-11; board · 6 Cleanup)
  - *Acceptance (Given-When-Then):* Given a merged cloud build, when the advisor has asked the builder to archive itself, then the owner sees the platform's one prompt for that session. (source: board · 6 Cleanup)

**FR-29.** When the advisor has asked a cloud builder to archive itself, the advisor shall tell the owner to expect one prompt and to tap Allow once. (source: board · 6 Cleanup)
  - *Acceptance (rule):* The advisor's message names the merged build and the one tap. (source: board · 6 Cleanup)

**FR-30.** When a cloud build's PR is merged, the plugin shall leave nothing behind for that build except its session: no branch on the repository and no files on the owner's machine. (source: Canon 2026-10-10-ca3e7e0d-9; board · 6 Cleanup)
  - *Acceptance (rule):* The archive prompt is the only step left to the owner. (source: Canon 2026-10-10-ca3e7e0d-11)

**FR-31.** While a cloud build's PR is neither merged nor closed, the plugin shall keep the build's pushed branch. (source: craft, for your veto)
  - *Acceptance (rule):* The plugin does not clean up a builder that hands back or parks. The builder's pushed work stays for the vet, a renewed review or a recovery. (source: craft, for your veto; board · 5 Mid-build trouble)

**FR-32.** When a cloud build's PR is closed unmerged, the plugin shall run the same cleanup as after a merge. (source: craft, for your veto)
  - *Acceptance (Given-When-Then):* Given a cloud build whose PR is closed unmerged, when the advisor closes out the build, then the advisor asks the builder to archive itself, and nothing else is left behind, as FR-30 says. (source: craft, for your veto)

### Part E: keeping the reviewer pass alive

The gardening pass's duties are a closed list [cite: plugins/superheroes/skills/showrunner/reference/owner-decisions.md § The seven duties, a closed list]. This spec adds one duty to that list, for projects that have a cloud setup. (source: Canon 2026-10-10-ca3e7e0d-12)

**FR-33.** When a gardening pass runs in a project that has a cloud setup, the advisor shall report how many days the reviewer pass has left and the date it lapses. (source: Canon 2026-10-10-ca3e7e0d-12; board · 7 The gardening pass)
  - *Acceptance (rule):* The line reads as the board draws it, with the days left and the date. (source: board · 7 The gardening pass)

**FR-34.** When the reviewer pass will lapse before the next gardening pass is owed, the advisor shall tell the owner to renew it at this pass and say how. (source: Canon 2026-10-10-ca3e7e0d-12; board · 7 The gardening pass)
  - *Acceptance (Given-When-Then):* Given a pass with three days left and a gardening pass owed every seven days, when the gardening pass runs, then the line is marked "Renew now" and names the two hand steps: run the pass command, and paste the new pass into the cloud environment. (source: board · 7 The gardening pass)

**FR-35.** The plugin shall give no warning ahead of the reviewer pass lapsing between gardening passes. (source: Canon 2026-10-10-ca3e7e0d-12; board · 7 The gardening pass)
  - *Acceptance (rule):* Between passes, nothing tells the owner the pass is about to lapse. Once it has lapsed, the launch report's reason, the line UFR-6 repeats and a parked PR's notice under UFR-8 still appear. (source: board · 7 The gardening pass; board · 3 The launch report; board · 5 Mid-build trouble)

**FR-36.** When the reviewer pass is renewed, the advisor shall send each PR that UFR-7 parked and that is still open back for review. (source: board · 5 Mid-build trouble)
  - *Acceptance (Given-When-Then):* Given a PR parked because its review could not run, when the owner renews the pass, then the advisor sends that PR back for its review with no further word from the owner. (source: board · 5 Mid-build trouble)
  - *Acceptance (rule):* The advisor does not send back a parked PR that was closed before the renewal. (source: craft, for your veto)

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
  - *Acceptance (rule):* No reviewer from the builder's own model family stands in. (source: Canon 2026-10-10-ca3e7e0d-2)

The approved review spec already treats a review as not run when no reviewer from a different model family can run [cite: docs/superheroes/risk-calibrated-review-that-learns-dec0af/spec.md § UFR-4]. UFR-7 applies that rule to a review that a lapsed pass stops from running. (source: craft, for your veto)

**UFR-8.** If UFR-7 parks a cloud build's PR, then the advisor shall tell the owner that the PR is parked and that renewing the pass lets it go back for review. (source: board · 5 Mid-build trouble)
  - *Acceptance:* Given a PR parked by UFR-7, when the advisor next writes to the owner, then the message names the PR, the reason and the renewal. (source: board · 5 Mid-build trouble)
  - *Acceptance (rule):* The advisor reports a review that did not run for any other reason as the review rules already say, with no advice to renew the pass. (source: craft, for your veto)

**UFR-9.** If a cloud builder stops or stalls, then the advisor shall recover the lane at once from its pushed work, routing the recovery as a launch is routed. (source: craft, for your veto; board · 5 Mid-build trouble)
  - *Acceptance:* Given a stopped cloud builder and the cloud ready, when the advisor recovers the lane, then the new builder runs in the cloud and starts from the pushed work. (source: board · 5 Mid-build trouble)
  - *Acceptance (rule):* A recovery never leaves two builders working one issue. (source: craft, for your veto)

**UFR-10.** If a cloud builder is recovered, then the advisor shall tell the owner when the builder stopped, where the lane was recovered, and how much work is being redone. (source: board · 5 Mid-build trouble)
  - *Acceptance (rule):* The work redone is the work since the builder's last push that could not be saved. (source: board · 5 Mid-build trouble; Canon 2026-10-10-ca3e7e0d-17)

**UFR-11.** If the owner does not answer the archive prompt, then the plugin shall leave the session listed and carry on. (source: Canon 2026-10-10-ca3e7e0d-11; board · 6 Cleanup)
  - *Acceptance (rule):* The plugin sends no reminder about an unanswered archive prompt. (source: board · 6 Cleanup)

**UFR-12.** If a cloud builder posts a question while the advisor is away, then the question shall wait on the issue until the advisor is back. (source: craft, for your veto; board · 4 While a cloud build runs)
  - *Acceptance:* Given the advisor is not running, when a cloud builder's question gets no answer, then the builder parks with its work pushed, and the advisor answers and resumes the lane when it is back. (source: craft, for your veto)

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
is the platform's own wording and is drawn as it appears. (source: board · 6 Cleanup)

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
  owner's machine. What a test cannot reach is learned in use and fixed as it comes up. (source: Canon 2026-10-10-ca3e7e0d-15)

## Assumptions & dependencies

- The owner's Claude plan offers cloud sessions, and the project's repository is connected to
  them. (source: framing)
- The owner has a sign-in for an independent reviewer that can be placed in the cloud as a pass.
  The pass used in the discovery's pilot lasts 10 days. (source: board · 1 Setup; journeys)
- The platform lets a session archive itself only when a person approves the prompt. (source: journeys; board · 6 Cleanup)
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
- Cleanup of a finished cloud builder takes one tap from the owner, for now. (source: Canon 2026-10-10-ca3e7e0d-11)

## Out of scope

- Hands-off upkeep of the reviewer pass and of the calibration copy: renewing and delivering them
  with no hand step. It is the later piece. (source: Canon 2026-10-10-ca3e7e0d-1; Canon 2026-10-10-ca3e7e0d-18)
- The advisor, discovery and the detective in the cloud. They stay on the owner's machine. (source: Canon 2026-10-10-ca3e7e0d-16)
- Any check that needs a phone or the owner's signed-in browser. (source: Canon 2026-10-10-ca3e7e0d-16)
- Cleanup with no tap from the owner. (source: Canon 2026-10-10-ca3e7e0d-11)
- A build machine the owner hosts. (source: Canon 2026-10-10-ca3e7e0d-6)

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

_No amendments since the last full approval._

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
| Workflow shape | Specify | No | The journeys board; parts A to E follow it |
| Placement & prominence | Specify | Yes | FR-15, FR-19, UFR-6: the launch report, the cloud mark, the line at the top of later messages |
| Limits & defaults | Specify | No | FR-7: off until switched on; FR-12: the cloud is the default once on |
| Tier & access boundaries | N-A | — | Works the same for every owner whose plan offers cloud sessions |
| Visibility & disclosure | Specify | Yes | FR-3, FR-4, FR-20, FR-21: the pass, personal rules, the cloud's author name, public builder notes |
