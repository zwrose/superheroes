# Coverage map — cloud-builders-66a2e8

Acceptance-level allocation of every criterion of the spec the owner approved on 2026-10-10,
`cloud-builders-66a2e8` (`spec.md`, beside this file), each owned by exactly one child, or, for the
spec's Definition of done, by the epic's closure validation run.

**What counts as one criterion.** Each acceptance bullet of an FR or UFR is one criterion, at the
spec's own bullet granularity: 66 bullets across FR-1 to FR-37 and UFR-1 to UFR-13. Every FR and
UFR in this spec carries at least one acceptance bullet, so no statement is counted on its own;
where an FR carries bullets, its statement is owned by the child that owns its bullets, and the
FRs and UFRs whose bullets are split name the statement's owner below. The spec has no
non-functional section. Each of the five Definition of done bullets is one criterion, owned by the
closure validation run. That makes 71 criteria. The table has 73 rows, because two bullets are
split at their own wording into two rows each (declared below).

**Declared splits.** Three requirements span two children. Each split follows the spec's own
bullets, or, where one bullet spans two surfaces, the bullet's own conjunction or sentences, the
way the decomposition doctrine's worked example splits one:

- **FR-37** (the cloud picks up the advisor's plugin version) is split at its bullets. The
  statement and bullet 1 (where the platform allows the pickup, the cloud builder runs the
  advisor's version and the owner pastes nothing) are **C3**'s, because the setup
  text is what makes the cloud pick the version up. Bullet 2 (where the platform does not allow it,
  UFR-5 applies and the launch report tells the owner to paste new setup text) is **C5**'s, because
  it is a launch-report reason. Register entries R3 (the record says whether the cloud picks the
  version up by itself) and R5 (the reason and its fix) bind both.
- **UFR-12** (a question waits on the issue while the advisor is away) is split at its one bullet's
  conjunction. "Then the builder parks with its work pushed" is **C6**'s, because the builder's
  wait and park are the builder's path. "And the advisor answers and resumes the lane when it is
  back" is **C7**'s, because answering and resuming are the advisor's. The statement (the question
  waits on the issue) is C6's: the builder posts it there. Register entry R6 binds both.
- **FR-35** (no warning between gardening passes) is split at its one bullet's two sentences.
  "Between passes, nothing tells the owner the pass is about to lapse" is **C8**'s, with the
  statement, because the gardening pass's duty is C8's. "Once it has lapsed, the launch report's
  reason, the line UFR-6 repeats and a parked PR's notice under UFR-8 still appear" is **C7**'s:
  C7 builds the parked PR's notice and, sitting above C5 in the stack, is the first layer that can
  show all three together on a lapsed-pass fixture. Register entries R5 and R7 bind it.

No other criterion is split.

**Criteria owned whole where another child also touches the behaviour.** These are not splits;
each names the one owner and the register entry that binds the other child:

- **FR-10** (a cloud setup belongs to the one Claude account it was made on) is **C5**'s, its only
  bullet being the readiness check that counts a launch from another account as not ready. C2
  writes the account into the setup record the check reads (R3).
- **FR-17** (a cloud build follows the same order, review, vet and merge rules) is **C1**'s: the
  launch carries the same composed order, and nothing in the vet or the merge rules changes with
  the place (R2). The PR's half of its bullet, the same review record and receipts, is produced by
  C6's builder path and bound by R7.
- **FR-25** (every review seat runs through the reviewer pass) is **C6**'s. The step that writes the
  pass into the reviewer's sign-in at the start of a cloud session is C3's, bound by
  R4.
- **FR-30** (nothing left behind after a merge: no branch, no checkout or worktree on the owner's
  machine) is **C8**'s. That a cloud launch makes no local worktree and pushes no launch branch is
  C1's, bound by R1.
- **FR-36** (the advisor sends parked PRs back after the pass is renewed) is **C7**'s. The renewal
  is read from the setup record's lapse date, which moves only when a cloud session confirms the new pass (C3, R3; the record itself is C2's).
- **UFR-5** (a version mismatch runs the build on the owner's machine and names both versions) is
  **C5**'s: its readiness check keeps such a build off the cloud, and its launch report names both
  versions. Where a mismatch reaches a cloud builder anyway, C6's builder stops before building and
  ends with `refusal`, and C7 relaunches the build routed as a launch, so it runs on the owner's
  machine with both versions named; R2 binds C5, C6 and C7. No bullet moves, so this is not a
  split.
- **UFR-9** (a stopped cloud builder is recovered at once, routed as a launch is) is **C7**'s. The
  routing it reuses is C5's one routing step (R5), and the liveness that shows the builder stopped
  is C1's (R1).

**Definition of done.** The spec's Definition of done is the success definition: an owner sets a
project up in one sitting, switches cloud builds on and launches a wave in which every build that
can run in the cloud does; those builds reach ready PRs with real independent reviews and no build
work on the owner's machine; the work ships once the build has tested what it can; the build tests
six named cases where a test can reach them; and what no test reaches is learned in use. No child
can show the first two alone, because they need every layer of the stack together. They
are the epic's **closure validation run** (`skills/showrunner/reference/closure.md` § The validation
run). Because the whole epic is one native stack, closure follows that file's stacked-feature case
(§ When closure fires): the receipt rides the top layer's vet, C8's, the last vet before the stack's
one merge, when every other layer already has a green vet. So the validation run runs **before the
merge**, against the stack's head, meaning the plugin as the whole stack has it: the plugin's automated conformance checks run on that head, and the children's recorded runs are collected and graded against the spec's success bullets as far as they reach: a project set up in one sitting and its check session (C4), cloud builds switched on and builds routed (C5), cloud builds launched, listed and answered (C1, C7), a cloud build reaching a ready PR with its independent review run through the pass (C6), and cleanup (C8). No real wave and no full-size build is required before the merge: the spec's Definition of done says the work ships once the build has tested what it can, with nothing shown in a real wave first (Canon 2026-10-10-ca3e7e0d-15), so what the recorded runs do not reach, a real multi-build wave and a full-size cloud build among them, is recorded in the closure receipt as left to be learned in use. The run also collects the children's recorded runs for the spec's other five tested cases (several cloud builders at once: C1; a project that
keeps its calibration outside the repository: C4; a lapsed pass sending builds to the owner's
machine: C5; a builder's question answered mid-build and a stopped builder recovered: C7). Its
result goes with C8's handback, in the closure receipt, presented to the owner with the delivery
decision in one sitting before the stack merges. Its five rows are the last rows of the table.

**Spec sections that are not criteria but have a builder home.** These carry no acceptance
criterion under the rule above and are not in the counts; each is named so nothing in the spec
falls between children.

| Section | What it asks | Home |
| --- | --- | --- |
| Part D's lead-in (the guardian's store a cloud session cannot reach) | a cloud builder reads the placed calibration copy, never the store | C6 (FR-27) and C3 (which places the copy) |
| Part E's lead-in | the new gardening duty is appended as duty 8, the seven keep their numbers, the list stays closed at eight | C8 |
| UI / UX | the approved build board (`board/build-board.html`) is the design, and its wording is the product's wording | each child's What names its artboards: C4 "1 Setup", C2 and C4 "2 The setting"; C5 "3 The launch report"; C1 and C6 "4 While a cloud build runs"; C6 and C7 "5 Mid-build trouble"; C8 "6 Cleanup" and "7 The gardening pass" |
| Glossary | cloud build, builder and lane; cloud environment; cloud setup; setup text; reviewer pass; check session; launch report; launch word | the child that first ships each term (R10) |
| Constraints | no dependence on several accounts; the pass from the owner's ordinary sign-in, business tokens ruled out; no ceiling on cloud builders; no recovery machinery beyond what the requirements name; project and plugin rules only; one tap per cleanup | R9 (no dependence on several accounts); R4 (the pass); C1 (no ceiling: the launcher adds none); C7 and R1 (recovery kept to what is named); C4 (the setup message says it) and C6 (the builder runs on them); C8 (one tap) |
| Assumptions & dependencies | cloud sessions on the owner's plan; a reviewer sign-in that can be placed as a pass; self-archive only on a person's approval; one-way messaging; the review spec's release; the version pickup not yet proven | the owner's setup (C2 to C4); R4; C8; R6; R7 and R8; C3 and C5 (FR-37) |
| Out of scope | hands-off upkeep of the pass and calibration; the advisor, discovery and detective in the cloud; checks needing a phone or the signed-in browser; cleanup with no tap; an owner-hosted build machine; carrying Canon or specs outside the repository to the cloud | none; C5 judges the last three kinds of build as needing the owner's machine (R5) |

Children, numbered by their position in the stack: C1 the cloud lane (the seam) · C2 the setting
and the setup record · C3 the setup text and the pass command · C4 the setup sitting and the check
session · C5 where a build runs · C6 the builder's cloud path · C7 the advisor's side of a running
cloud build · C8 cleanup and the reviewer pass's upkeep.

**Sequencing.** One native stack, the unit of merge (R8): C1 at the bottom on `main`, then C2,
C3, C4, C5, C6, C7 and C8. Build wave 0, now: C1, C2 and C3 in parallel. Wave 1: C4
once C1, C2 and C3 have handed back; C5 once C1 and C2 have; C6 once C1 and C3 have handed back and epic
#1708's review record (#1709 and #1710) is on main; C8 once C1 and C2 have handed back and epic
#1708's #1716 and #1718 are on main. Wave 2: C7, once C5 and C6 have handed back. The stack merges with
one `gh stack merge` when every layer is vetted.

**Per child.** C1 4 rows · C2 4 · C3 2 · C4 7 · C5 15 · C6 13 · C7 14 ·
C8 9 · closure validation run 5. Total 73 rows: 68 bullet rows (66 bullets, two of them split in
two) and 5 Definition of done rows.

| Ref | Bullet | Kind | Criterion (opening words) | Owner |
| --- | --- | --- | --- | --- |
| FR-1 | 1 | GWT | Given a project with no cloud setup, when the owner asks to set up cloud builds, then the advisor's message… | **C4** |
| FR-1 | 2 | rule | The message tells the owner to run the pass command on the owner's machine, which puts the reviewer pass on… | **C4** |
| FR-2 | 1 | rule | The setup text holds no reviewer pass and no other secret. | **C3** |
| FR-3 | 1 | rule | The setup message carries all five facts in the board's wording. | **C4** |
| FR-4 | 1 | rule | The setup message says cloud builders follow the project's rules and the plugin's rules and nothing else. | **C4** |
| FR-5 | 1 | GWT | Given the hand steps are done, when the check session ends, then the advisor reports three results: whether… | **C4** |
| FR-6 | 1 | rule | The message says how to switch cloud builds on. | **C4** |
| FR-7 | 1 | rule | The setting is off for every project until the owner switches it on. | **C2** |
| FR-8 | 1 | GWT | Given a passed check, when the owner says to turn cloud builds on, then the advisor confirms that every build… | **C2** |
| FR-9 | 1 | rule | Switching back on needs no new setup. | **C2** |
| FR-10 | 1 | GWT | Given a project set up on one Claude account, when a build is launched from a different account, then the… | **C5** |
| FR-11 | 1 | GWT | Given cloud builds switched on, when the owner says "this one local" at a launch, then that build runs on the… | **C5** |
| FR-12 | 1 | GWT | Given cloud builds switched on and the cloud ready, when five builds are launched and three need nothing from… | **C5** |
| FR-13 | 1 | rule | The advisor judges a build that needs a phone simulator or the owner's signed-in browser as not able to run… | **C5** |
| FR-13 | 2 | rule | The advisor judges every build of a project that keeps its Canon or its specs outside the repository as not… | **C5** |
| FR-14 | 1 | rule | A launch with any one of the five conditions false is a launch with the cloud not ready. | **C5** |
| FR-15 | 1 | rule | The launch report names every launched build under one of the two places. | **C5** |
| FR-16 | 1 | rule | The reason is one of the eight on the board's list of reasons. | **C5** |
| FR-17 | 1 | GWT | Given a build-ready issue, when it is built in the cloud, then its PR carries the same review record and… | **C1** |
| FR-18 | 1 | GWT | Given the cloud is ready, when a build that needs no owner decision is launched in the cloud, then it reaches… | **C6** |
| FR-19 | 1 | rule | Wherever the advisor lists lanes, a cloud lane appears with the word "cloud" beside it. | **C1** |
| FR-20 | 1 | rule | The intake comment carries those three facts. | **C6** |
| FR-21 | 1 | rule | The comment is headed as a builder note for the advisor and says the builder is waiting. | **C6** |
| FR-21 | 2 | rule | On a public repository the comment is public, as builder comments already are. | **C6** |
| FR-22 | 1 | GWT | Given the advisor is watching the wave, when a cloud builder posts a builder note, then the advisor's answer… | **C7** |
| FR-23 | 1 | GWT | Given a cloud build in progress, when the owner's machine sleeps, then the build carries on to its next point… | **C1** |
| FR-24 | 1 | rule | A builder that stops mid-build has pushed work for the advisor to recover the lane from. | **C6** |
| FR-24 | 2 | rule | At handback, the review record and the receipts are on the PR, and nothing the vet needs exists only on the… | **C6** |
| FR-25 | 1 | rule | The plugin does not drop the review of a cloud build and does not treat it as second class. | **C6** |
| FR-26 | 1 | rule | A cloud build's PR merges only on the owner's merge word, as any build's does. | **C1** |
| FR-27 | 1 | rule | Nothing a cloud builder does alters the calibration on the owner's machine. | **C6** |
| FR-28 | 1 | GWT | Given a merged cloud build, when the advisor has asked the builder to archive itself, then the owner sees the… | **C8** |
| FR-29 | 1 | rule | The advisor's message names the merged build and the one tap. | **C8** |
| FR-30 | 1 | rule | The archive prompt is the only step left to the owner. | **C8** |
| FR-31 | 1 | rule | The plugin does not clean up a builder that hands back or parks. The builder's pushed work stays for the vet,… | **C8** |
| FR-32 | 1 | GWT | Given a cloud build whose PR is closed unmerged, when the advisor closes out the build, then the advisor asks… | **C8** |
| FR-33 | 1 | rule | The line reads as the board draws it, with the days left and the date. | **C8** |
| FR-34 | 1 | GWT | Given a pass with three days left and a gardening pass owed every seven days, when the gardening pass runs,… | **C8** |
| FR-35 | 1a | rule | Between passes, nothing tells the owner the pass is about to lapse. | **C8** |
| FR-35 | 1b | rule | Once it has lapsed, the launch report's reason, the line UFR-6 repeats and a parked PR's notice under UFR-8 still appear. | **C7** |
| FR-36 | 1 | GWT | Given a PR parked because its review could not run, when the owner renews the pass, then the advisor sends… | **C7** |
| FR-36 | 2 | rule | The advisor does not send back a parked PR that was closed before the renewal. | **C7** |
| FR-36 | 3 | rule | The advisor does not send back a parked PR that the owner has already let through by the review spec's own… | **C7** |
| FR-37 | 1 | GWT | Given a cloud setup made on an earlier plugin version and a platform that allows the pickup, when a build is… | **C3** |
| FR-37 | 2 | rule | Where the platform does not allow the pickup, UFR-5 applies and the launch report tells the owner to paste… | **C5** |
| UFR-1 | 1 | GWT | Given a reviewer pass that was pasted wrong, when the check session ends, then the advisor says the reviewer… | **C4** |
| UFR-2 | 1 | GWT | Given no cloud setup on this account, when the owner says to turn cloud builds on, then the advisor says they… | **C2** |
| UFR-3 | 1 | GWT | Given a build that needs the phone simulator, when it is launched, then it runs on the owner's machine and… | **C5** |
| UFR-3 | 2 | rule | A launch word that names the cloud overrides the project's setting and does not override what the build needs. | **C5** |
| UFR-4 | 1 | GWT | Given a lapsed reviewer pass, when four builds are launched, then all four run on the owner's machine and the… | **C5** |
| UFR-4 | 2 | rule | The plugin never holds a build and never drops a build because the cloud is not ready. | **C5** |
| UFR-5 | 1 | rule | A cloud builder never runs on an older copy of the plugin than the advisor's. | **C5** |
| UFR-6 | 1 | GWT | Given a version mismatch reported at launch, when the advisor next writes to the owner, then the message… | **C5** |
| UFR-7 | 1 | GWT | Given a cloud build whose pass lapses before its review, when the builder reaches the review, then the… | **C6** |
| UFR-7 | 2 | rule | A review that finished before the pass lapsed stays as it was recorded. | **C6** |
| UFR-7 | 3 | rule | A PR parked this way follows the approved review spec's rules for a review that did not run, the owner's own… | **C6** |
| UFR-7 | 4 | rule | The cloud is not stricter than a build on the owner's machine here. | **C6** |
| UFR-8 | 1 | GWT | Given a PR parked by UFR-7, when the advisor next writes to the owner, then the message names the PR, the… | **C7** |
| UFR-8 | 2 | rule | The advisor reports a review that did not run for any other reason as the review rules already say, with no… | **C7** |
| UFR-9 | 1 | GWT | Given a stopped cloud builder and the cloud ready, when the advisor recovers the lane, then the new builder… | **C7** |
| UFR-9 | 2 | rule | A recovery never leaves two builders working one issue. | **C7** |
| UFR-10 | 1 | rule | The work redone is the work since the builder's last push that could not be saved. | **C7** |
| UFR-11 | 1 | rule | The plugin sends no reminder about an unanswered archive prompt. | **C8** |
| UFR-12 | 1a | GWT | then the builder parks with its work pushed | **C6** |
| UFR-12 | 1b | GWT | and the advisor answers and resumes the lane when it is back | **C7** |
| UFR-13 | 1 | GWT | Given a stalled cloud builder that still answers, when the advisor recovers the lane, then the advisor asks… | **C7** |
| UFR-13 | 2 | rule | Work that cannot be saved is redone, and the advisor says how much. | **C7** |
| UFR-13 | 3 | rule | A build that never pushed starts again from the beginning. | **C7** |
| DoD | 1 | success | An owner can set a project up for the cloud in one sitting, switch cloud builds on, and launch a wave in which every build that can run in the cloud does. | **closure validation run** |
| DoD | 2 | success | Those builds reach ready PRs with real independent reviews, and the owner's machine does none of their build work. | **closure validation run** |
| DoD | 3 | success | The work ships once the build has tested what it can test. Nothing has to be shown in a real wave first. | **closure validation run** |
| DoD | 4 | success | The build tests each of these where a test can reach it: several cloud builders at once, a full-size build, a builder's question answered mid-build… | **closure validation run** |
| DoD | 5 | success | What a test cannot reach is learned in use and fixed as it comes up. | **closure validation run** |

**Mechanical check.** `spec.md` has 66 acceptance bullets (`grep -c '^  - \*Acceptance' spec.md`)
and 5 Definition of done bullets. A script parsed every bullet of the spec, keyed by its FR or UFR
and its position, and every bullet row of the table above: each of the 66 bullets appears exactly
once, the two split bullets each appear as exactly their two declared parts, no row names a bullet
the spec lacks, each Definition of done bullet appears once, and every row names exactly one owner.
