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
  conjunction. "Then the builder parks with its work pushed" is **C6b**'s (moved from C6 at the
  2026-10-11 size split), because the builder's wait and park are the builder's path and C6b's
  recorded live run grades them. "And the advisor answers and resumes the lane when it is
  back" is **C7**'s, because answering and resuming are the advisor's. The statement (the question
  waits on the issue) is C6b's: the builder posts it there. Register entry R6 binds both.
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
- **FR-17** (a cloud build follows the same order, review, vet and merge rules) is **C1b**'s (moved from C1 at the 2026-10-10 size split): the
  launch carries the same composed order, and nothing in the vet or the merge rules changes with
  the place (R2). The PR's half of its bullet, the same review record and receipts, is produced by
  the builder's cloud path (C6 and C6b) and bound by R7.
- **FR-25** (every review seat runs through the reviewer pass) is **C6b**'s (moved from C6 at the
  2026-10-11 size split), graded by its recorded live run. The step that writes the pass into the
  reviewer's sign-in at the start of a cloud session is C3's, and C6's runner keeps the pass out of
  the processes it spawns; both are bound by R4.
- **FR-30** (nothing left behind after a merge: no branch, no checkout or worktree on the owner's
  machine) is **C8**'s. That a cloud launch makes no local worktree and pushes no launch branch is
  C1's, bound by R1.
- **FR-36** (the advisor sends parked PRs back after the pass is renewed) is **C7**'s. The renewal
  is read from the setup record's lapse date, which moves only when a cloud session confirms the new pass (C3, R3; the record itself is C2's).
- **UFR-5** (a version mismatch runs the build on the owner's machine and names both versions) is
  **C5**'s: its readiness check keeps such a build off the cloud, and its launch report names both
  versions. Where a mismatch reaches a cloud builder anyway, C6's builder stops before building and
  ends with `refusal`, and C7b (moved from C7 at the 2026-10-12 size split) relaunches the build
  routed as a launch, so it runs on the owner's machine with both versions named; R2 binds C5, C6
  and C7b. No bullet moves, so this is not a split.
- **UFR-9** (a stopped cloud builder is recovered at once, routed as a launch is) is **C7b**'s
  (moved from C7 at the 2026-10-12 size split). The
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
merge**, against the stack's head, meaning the plugin as the whole stack has it: the plugin's automated conformance checks run on that head, and the children's recorded runs are collected and graded against the spec's success bullets as far as they reach: a project set up in one sitting and its check session (C4), cloud builds switched on and builds routed (C5), cloud builds launched, listed and answered (C1, C7), a cloud build reaching a ready PR with its independent review run through the pass (C6b), and cleanup (C8). No real wave and no full-size build is required before the merge: the spec's Definition of done says the work ships once the build has tested what it can, with nothing shown in a real wave first (Canon 2026-10-10-ca3e7e0d-15), so what the recorded runs do not reach, a real multi-build wave and a full-size cloud build among them, is recorded in the closure receipt as left to be learned in use. The run also collects the children's recorded runs for the spec's other five tested cases (several cloud builders at once: C1; a project that
keeps its calibration outside the repository: C4; a lapsed pass sending builds to the owner's
machine: C5; a builder's question answered mid-build: C7; a stopped builder recovered: C7b). Its
result goes with C8's handback, in the closure receipt, presented to the owner with the delivery
decision in one sitting before the stack merges. Its five rows are the last rows of the table.

**Spec sections that are not criteria but have a builder home.** These carry no acceptance
criterion under the rule above and are not in the counts; each is named so nothing in the spec
falls between children.

| Section | What it asks | Home |
| --- | --- | --- |
| Part D's lead-in (the guardian's store a cloud session cannot reach) | a cloud builder reads the placed calibration copy, never the store | C6 (FR-27) and C3 (which places the copy) |
| Part E's lead-in | the new gardening duty is appended as duty 8, the seven keep their numbers, the list stays closed at eight | C8 |
| UI / UX | the approved build board (`board/build-board.html`) is the design, and its wording is the product's wording | each child's What names its artboards: C4 "1 Setup", C2 and C4 "2 The setting"; C5 "3 The launch report"; C1 and C6 "4 While a cloud build runs"; C6, C7 and C7b "5 Mid-build trouble"; C8 "6 Cleanup" and "7 The gardening pass" |
| Glossary | cloud build, builder and lane; cloud environment; cloud setup; setup text; reviewer pass; check session; launch report; launch word | the child that first ships each term (R10) |
| Constraints | no dependence on several accounts; the pass from the owner's ordinary sign-in, business tokens ruled out; no ceiling on cloud builders; no recovery machinery beyond what the requirements name; project and plugin rules only; one tap per cleanup | R9 (no dependence on several accounts); R4 (the pass); C1 (no ceiling: the launcher adds none); C7b and R1 (recovery kept to what is named); C4 (the setup message says it) and C6 (the builder runs on them); C8 (one tap) |
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

**Per child.** C1 1 row · C1b 3 (FR-17, FR-23 and FR-26 moved from C1 at the 2026-10-10 size split) · C2 4 · C3 2 · C4 6 · C4b 1 (FR-1's Given-When-Then, moved from C4 at the 2026-10-11 size split) · C5 12 · C5b 3 (FR-15, FR-16 and UFR-6, moved from C5 at the 2026-10-11 size split) · C6 5 · C6b 8 (FR-18, FR-20, FR-21, FR-24, FR-25 and UFR-12's builder's half, moved from C6 at the 2026-10-11 size split) · C7 8 · C7b 6 (UFR-9, UFR-10 and UFR-13, moved from C7 at the 2026-10-12 size split) ·
C8 9 · closure validation run 5. Total 73 rows: 68 bullet rows (66 bullets, two of them split in
two) and 5 Definition of done rows.

| Ref | Bullet | Kind | Criterion (opening words) | Owner |
| --- | --- | --- | --- | --- |
| FR-1 | 1 | GWT | Given a project with no cloud setup, when the owner asks to set up cloud builds, then the advisor's message… | **C4b** |
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
| FR-15 | 1 | rule | The launch report names every launched build under one of the two places. | **C5b** |
| FR-16 | 1 | rule | The reason is one of the eight on the board's list of reasons. | **C5b** |
| FR-17 | 1 | GWT | Given a build-ready issue, when it is built in the cloud, then its PR carries the same review record and… | **C1b** |
| FR-18 | 1 | GWT | Given the cloud is ready, when a build that needs no owner decision is launched in the cloud, then it reaches… | **C6b** |
| FR-19 | 1 | rule | Wherever the advisor lists lanes, a cloud lane appears with the word "cloud" beside it. | **C1** |
| FR-20 | 1 | rule | The intake comment carries those three facts. | **C6b** |
| FR-21 | 1 | rule | The comment is headed as a builder note for the advisor and says the builder is waiting. | **C6b** |
| FR-21 | 2 | rule | On a public repository the comment is public, as builder comments already are. | **C6b** |
| FR-22 | 1 | GWT | Given the advisor is watching the wave, when a cloud builder posts a builder note, then the advisor's answer… | **C7** |
| FR-23 | 1 | GWT | Given a cloud build in progress, when the owner's machine sleeps, then the build carries on to its next point… | **C1b** |
| FR-24 | 1 | rule | A builder that stops mid-build has pushed work for the advisor to recover the lane from. | **C6b** |
| FR-24 | 2 | rule | At handback, the review record and the receipts are on the PR, and nothing the vet needs exists only on the… | **C6b** |
| FR-25 | 1 | rule | The plugin does not drop the review of a cloud build and does not treat it as second class. | **C6b** |
| FR-26 | 1 | rule | A cloud build's PR merges only on the owner's merge word, as any build's does. | **C1b** |
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
| UFR-6 | 1 | GWT | Given a version mismatch reported at launch, when the advisor next writes to the owner, then the message… | **C5b** |
| UFR-7 | 1 | GWT | Given a cloud build whose pass lapses before its review, when the builder reaches the review, then the… | **C6** |
| UFR-7 | 2 | rule | A review that finished before the pass lapsed stays as it was recorded. | **C6** |
| UFR-7 | 3 | rule | A PR parked this way follows the approved review spec's rules for a review that did not run, the owner's own… | **C6** |
| UFR-7 | 4 | rule | The cloud is not stricter than a build on the owner's machine here. | **C6** |
| UFR-8 | 1 | GWT | Given a PR parked by UFR-7, when the advisor next writes to the owner, then the message names the PR, the… | **C7** |
| UFR-8 | 2 | rule | The advisor reports a review that did not run for any other reason as the review rules already say, with no… | **C7** |
| UFR-9 | 1 | GWT | Given a stopped cloud builder and the cloud ready, when the advisor recovers the lane, then the new builder… | **C7b** |
| UFR-9 | 2 | rule | A recovery never leaves two builders working one issue. | **C7b** |
| UFR-10 | 1 | rule | The work redone is the work since the builder's last push that could not be saved. | **C7b** |
| UFR-11 | 1 | rule | The plugin sends no reminder about an unanswered archive prompt. | **C8** |
| UFR-12 | 1a | GWT | then the builder parks with its work pushed | **C6b** |
| UFR-12 | 1b | GWT | and the advisor answers and resumes the lane when it is back | **C7** |
| UFR-13 | 1 | GWT | Given a stalled cloud builder that still answers, when the advisor recovers the lane, then the advisor asks… | **C7b** |
| UFR-13 | 2 | rule | Work that cannot be saved is redone, and the advisor says how much. | **C7b** |
| UFR-13 | 3 | rule | A build that never pushed starts again from the beginning. | **C7b** |
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

**Coverage re-check after spec amendments 1 and 2 (advisor, 2026-10-11; owner rulings "25 c" and "27 a").** FR-1's statement and both acceptances changed wording and gained two hand steps, but no acceptance criterion was added or removed: the map still holds its bullets and rows, FR-1's rows stay C4's, and every criterion is still owned exactly once. Register R3 now records how the setup learns the environment as the owner's ruling, not a C2 decide-by. Package read invocation 2 (package-read-audit.md) re-read the touched parts and verified both fixes.

**Coverage re-check after spec amendments 4 and 5 (advisor, 2026-10-11; owner rulings "35 a" and "33 a").** Amendment 4 rewrote FR-1's statement, its hand-step list and its rule (the owner copies the environment's id; the default-environment step is retired); amendment 5 rewrote the messaging assumption (a relay session on the builders' account). No acceptance criterion was added or removed: FR-1's rows stay C4's, FR-22's stay C7's, and every criterion is still owned exactly once. Register R3 records the new source of the environment's id; R6 gains the relay, with how it is started, kept alive and checked as decide-by C7. The touched parts go through package read invocation 4 (package-read-audit.md).

**Coverage re-check after the C4 size split (advisor, 2026-10-11, at the 600 bar; craft, owner veto open).** Cloud C4 split into C4 (the setup sitting's library, #1745) and C4b (its skill text, #1771). FR-1's Given-When-Then acceptance (the sitting as the owner meets it: the hand steps, the sign-in walked, the id asked once) moved to C4b, whose recorded setup sitting grades it; C4 keeps FR-1's rule, FR-3 to FR-6 and UFR-1. No criterion was added or removed, and every criterion is still owned exactly once. Register R8 names C4b in the stack's order; R8, R9 and R11 name it as a consumer.

**Coverage re-check after ruling 37 b (advisor, 2026-10-11).** Amendment 4 now records rulings "35 a" and "37 b" together: the owner picks the environment in Claude Code's picker and the plugin reads its id. FR-1's statement, its Given-When-Then (C4b) and its rule (C4) changed wording; no acceptance criterion was added or removed, and every criterion is still owned exactly once. Register R3 records the new source and names C4b as a consumer (C4b holds the reader).

**Coverage re-check after the C5 size split (advisor, 2026-10-11, at the 600 bar; craft, owner veto open).** Cloud C5 split into C5 (where a build runs: the readiness reader, the routing step, the launcher wiring, #1746) and C5b (the launch report, the still line and the doctrine, #1775). FR-15, FR-16 and UFR-6 moved to C5b; C5 keeps FR-10 to FR-14, FR-37's second acceptance, UFR-3, UFR-4 and UFR-5, its routing result carrying each reason and fix that C5b renders. No criterion was added or removed, and every criterion is still owned exactly once. Register R8 names C5b in the stack's order; R2, R3, R5, R8, R9, R10 and R11 name it as a consumer.

**Coverage re-check after the C6 size split (advisor, 2026-10-11, at the 600 bar; craft, owner veto open).** Cloud C6 split into C6 (the builder's cloud path, machine side: the cloud builder module, the calibration guard, the runner's pass scrub, the history fetch, the GitHub probe over REST and the bootstrap's marker fix, #1747) and C6b (the builder's cloud doctrine and live run, #1777). The criteria the recorded live run grades moved to C6b: FR-18, FR-20, both of FR-21's acceptances, both of FR-24's, FR-25 and UFR-12's builder's half (with UFR-12's statement). C6 keeps FR-27 and UFR-7's four acceptances, which its tests grade, and the version-mismatch refusal that UFR-5's note names. No criterion was added or removed, and every criterion is still owned exactly once. Register R8 names C6b in the stack's order; R4, R6, R7, R8, R9 and R11 name it as a consumer, and R11 gives it the workhorse charter and the review-discipline line.

**Coverage re-check after the C7 size split (advisor, 2026-10-12, at the 600 bar; craft, owner veto open).** Cloud C7 split into C7 (answering a cloud builder: the builder-note watch event, the relay session and its exact-text check, the advisor's return, the lapsed-pass parked notice and the send-back after renewal, #1748) and C7b (recovering a cloud builder: the adoption routed through C5's routing step, the push ask, the recovery message, the successor launch naming the pushed branch, the version-mismatch relaunch and the recovery folds, #1784). The recovery criteria moved to C7b: both of UFR-9's acceptances, UFR-10, and UFR-13's three. C7 keeps FR-22, FR-35's second sentence, FR-36's three, UFR-8's two and UFR-12's advisor's half. UFR-5's row stays C5's; the relaunch its note names is now C7b's. No criterion was added or removed, and every criterion is still owned exactly once. Register R8 names C7b in the stack's order; R1, R2, R5, R6, R8, R9 and R11 name it as a consumer, and R11 gives it the recovery parts of the files it shares with C7.
