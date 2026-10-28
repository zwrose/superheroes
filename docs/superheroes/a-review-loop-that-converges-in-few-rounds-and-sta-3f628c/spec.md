---
superheroes: doc
schemaVersion: 1
docType: spec
workItem: a-review-loop-that-converges-in-few-rounds-and-sta-3f628c
issue: 2185
size: large
status: draft
gates: {review: pending}
producedBy: "the-architect0.46.2"
created: "2026-10-27"
updated: "2026-10-27"
---
# A review loop that converges in few rounds and stays simple

## How to read this spec

Every statement ends with its source in plain text. The sources are:

- **board · panel N**: the approved build board, saved in `board/` beside this spec, at
  https://claude.ai/artifact/VSbmFZk1oeHRLrVB4Znuw8, version 4, approved by the owner on
  2026-10-27.
- **Canon <entry id>**: an owner ruling recorded in the project's Canon.
- **framing**: the framing the owner approved on 2026-10-26.
- **assessment**: the post-0.43 review-loop assessment the owner read and commented on,
  https://claude.ai/artifact/52LE5cg8Xd7HuKUJEvgf3v (2026-10-26).
- **registry · item N**: item N's row in the revisit registry on #695.
- **craft, for your veto**: a choice the author made, recorded for the owner's veto.

"The review loop" in this spec is the code review that runs on a full-lane build, unless a
requirement names the light or micro lane. "The build session" is the session that built the
change. "An independent reviewer" is a reviewer from a different model family than every maker of
the change. (source: framing)

## Purpose

Code review finds real problems, but it does not finish. Between 2026-10-17 and 2026-10-26 one PR
in ten needed 9 or more review rounds and the worst needed about 30, PRs reviewed in more than one
session held 81 to 83% of review tokens, and 21 merged PRs fixed the loop stalling or losing a
session. (source: assessment) This work makes a review finish in a few rounds, find what it will find in round 1, and have fewer moving parts that can stall, without
giving up the independent checks that make a review worth trusting. (source: framing)

## Who it's for

- As the owner, I want reviews to finish in a few rounds, so builds hand back sooner and use fewer
  tokens and CI minutes. (source: framing)
- As the owner, I want review to keep catching real bugs, so the speed doesn't come from missing
  things. (source: framing)
- As the advisor, I want bugs found outside a PR to reach me as follow-ups, so they aren't
  silently dropped. (source: framing)

## Functional requirements

### Who applies the fixes

**FR-1.** When the review confirms a finding, the build session shall apply the fix itself, the
same way it built the change. (source: Canon 2026-10-26-5692f27d-4)
  - *Acceptance (rule):* No separate fixer agent, fix order or locked-down fixer sandbox takes part
    in a review. (source: Canon 2026-10-26-5692f27d-4; board · panel 2)

**FR-2.** The review loop shall let only the independent verifier close a finding as wrong.
(source: Canon 2026-10-27-5692f27d-3; board · panel 2)
  - *Acceptance (rule):* No finding in a review record is closed as wrong by the build session or by
    any reviewer other than the verifier. (source: Canon 2026-10-27-5692f27d-3; board · panel 2)

### Round 1: the panel

**FR-3.** The round-1 panel shall be a code reviewer and a test reviewer, joined by both the
security and the premortem reviewer whenever the change touches any declared risk area.
(source: Canon 2026-10-27-5692f27d-5)
  - *Acceptance (rule):* A change that touches one risk area seats both specialists; a change that
    touches none seats neither. (source: Canon 2026-10-27-5692f27d-5)

**FR-4.** Each round-1 reviewer shall record which parts of the change it actually read.
(source: Canon 2026-10-27-5692f27d-4)
  - *Acceptance (rule):* The review record shows, per reviewer, the parts read.
    (source: board · panel 1)

### Round 1: big changes

**FR-5.** When a change is over about 1,000 countable lines, the review loop shall cut it into
slices by size and give each slice its own code and test reviewer. (source: Canon
2026-10-27-5692f27d-4; Canon 2026-10-27-5692f27d-7)
  - *Acceptance (Given-When-Then):* Given a 3,000-line change whose files all sit under one
    top-level folder, when round 1 starts, then it is reviewed as more than one slice.
    (source: Canon 2026-10-27-5692f27d-7)
  - *Acceptance (rule):* Splitting a big change into separate PRs stays the usual first answer;
    slicing is for a PR that is not practical to split. (source: Canon 2026-10-27-5692f27d-4;
    board · panel 1)

**FR-6.** The review loop shall count as countable lines every changed line except those in files
moved without change, in generated and lock files, and in whole-file deletions. (source: Canon
2026-10-27-5692f27d-7)
  - *Acceptance (rule):* Changed test lines and changed doc lines count. (source: Canon
    2026-10-27-5692f27d-7)

**FR-7.** Where it is unclear whether a line counts or where to cut, the review loop shall cut
smaller slices. (source: Canon 2026-10-27-5692f27d-7)
  - *Acceptance (rule):* A borderline cut never produces a slice above the bar. (source: Canon
    2026-10-27-5692f27d-7)

**FR-8.** When round-1 reviewers of a sliced change leave a part unread, the review loop shall
review that part as a new slice with the same reviewers any slice gets. (source: Canon
2026-10-27-5692f27d-12)
  - *Acceptance (rule):* An unread part touching a risk area gets a code, a test, a security and a
    premortem reviewer. (source: Canon 2026-10-27-5692f27d-12; board · panel 1)

**FR-9.** When a change is sliced, one reviewer reading the whole change shall check the seams
between slices. (source: Canon 2026-10-27-5692f27d-12)
  - *Acceptance (rule):* The seams check runs once per sliced change, in round 1 only. (source:
    board · panel 1)

**FR-10.** The premortem reviewer shall read the whole change, never a slice. (source: Canon
2026-10-27-5692f27d-12)
  - *Acceptance (rule):* On a sliced change, the premortem reviewer's read list covers the whole
    change. (source: Canon 2026-10-27-5692f27d-12)

### Round 1: break-it tests and the verifier

**FR-11.** The test reviewer shall attach a break-it test to each finding it can prove that way.
(source: Canon 2026-10-27-5692f27d-3; board · panel 1)
  - *Acceptance (rule):* A break-it test is written by the test reviewer, never by the build
    session. (source: Canon 2026-10-27-5692f27d-3)

**FR-12.** The test reviewer shall keep checking changed tests for tests that pass by chance,
flaky tests and fixes with no test that would fail, and shall count test bloat against the change.
(source: Canon 2026-10-27-5692f27d-3)
  - *Acceptance (rule):* The test reviewer asks for no coverage in low-risk code and flags no test
    style preference. (source: Canon 2026-10-27-5692f27d-3)

**FR-13.** Before the verifier grades findings, the build session shall run each attached
break-it test on the unfixed code, exactly as written, and save its output without judging it.
(source: Canon 2026-10-27-5692f27d-3; board · panel 1)
  - *Acceptance (Given-When-Then):* Given a finding with a break-it test, when the verifier grades
    it, then the test's output on the unfixed code is in the verifier's hands. (source: board ·
    panel 1)

**FR-14.** The verifier shall grade each finding on its own, using the break-it test's output
where there is one. (source: Canon 2026-10-27-5692f27d-3)
  - *Acceptance (rule):* Each finding carries a grade (confirmed, plausible or wrong) and the
    reason. (source: board · panel 1)

**FR-15.** When a break-it test passes on the unfixed code and reaches the path its finding
describes, the verifier shall close the finding as wrong. (source: board · panel 1; Canon
2026-10-27-5692f27d-3)
  - *Acceptance (Given-When-Then):* Given a break-it test that passes on the unfixed code down the
    finding's own path, when the verifier grades the finding, then it is closed as wrong and goes to
    no fix. (source: board · panel 1)

**FR-16.** When a break-it test passes on the unfixed code without reaching the path its finding
describes, the review loop shall give a fresh run of the test reviewer one chance to write a
better test. (source: Canon 2026-10-27-5692f27d-3)
  - *Acceptance (Given-When-Then):* Given the verifier judges that a test missed the finding's
    path, when the review continues, then a fresh test-reviewer run receives the finding, the
    first test, its output and the verifier's note, and writes one more test. (source: board ·
    panel 1; craft, for your veto)

**FR-17.** When the second break-it test also passes on the unfixed code, the verifier shall
decide the finding on the evidence it has. (source: craft, for your veto)
  - *Acceptance (rule):* The finding is closed as wrong or kept as a judgment call without a
    test; no third test is written. (source: craft, for your veto)

### Round 1: synthesis and repeats

**FR-18.** Synthesis shall group findings that share a root cause. (source: board · panel 1)
  - *Acceptance (rule):* Grouped findings get one fix. (source: board · panel 1)

**FR-19.** Synthesis shall mark each new finding that repeats one of the PR's earlier findings in
its review record. (source: Canon 2026-10-26-5692f27d-9)
  - *Acceptance (rule):* A repeat names the earlier finding it matches. (source: board · panel 7)

**FR-20.** When a repeat matches an earlier fixed finding, the verifier shall judge whether the
earlier fix still holds. (source: Canon 2026-10-26-5692f27d-9)
  - *Acceptance (Given-When-Then):* Given a repeat of a fixed finding, when the old fix still
    holds, then the repeat keeps the earlier outcome; when it no longer holds, then the repeat is
    treated as a new finding. (source: Canon 2026-10-26-5692f27d-9)

**FR-21.** A marked repeat shall keep its earlier outcome and stay visible in the review record.
(source: Canon 2026-10-26-5692f27d-9)
  - *Acceptance (rule):* Unless FR-20 finds the earlier fix no longer holds, a repeat never goes to
    the fix and never becomes an owner card, and it is never dropped from the record. (source:
    Canon 2026-10-26-5692f27d-9)

### Round 1: copies of a bug

**FR-22.** Each finding shall name its kind of mistake and every place in the PR that has it.
(source: Canon 2026-10-26-5692f27d-7)
  - *Acceptance (rule):* The fix for a finding covers every place it names. (source: Canon
    2026-10-26-5692f27d-7)

**FR-23.** When an Important or Critical finding is confirmed, the independent reviewer that
raised it shall write what to look for: the kind of mistake, what it looks like, and examples.
(source: Canon 2026-10-27-5692f27d-9)
  - *Acceptance (rule):* The search description comes from the reviewer, never from the build
    session. (source: Canon 2026-10-27-5692f27d-9)

**FR-24.** When a search description is written, the build session shall search the whole
repository for the same mistake once, with cheap parallel subagents. (source: Canon
2026-10-27-5692f27d-9)
  - *Acceptance (rule):* One search per confirmed Important or Critical finding. (source: Canon
    2026-10-26-5692f27d-7)

**FR-25.** When the search finds the mistake inside the PR, the review loop shall treat each hit
as a finding that goes through the verifier. (source: Canon 2026-10-27-5692f27d-9)
  - *Acceptance (rule):* A search hit is never fixed without a verifier grade. (source: Canon
    2026-10-27-5692f27d-9)

**FR-26.** When the search finds the mistake outside the PR, the review loop shall add each hit to
the review record's "Outside this PR" list. (source: Canon 2026-10-27-5692f27d-9)
  - *Acceptance (rule):* An outside hit names its file and line and the mistake. (source: board ·
    panel 7)

### Findings outside the PR

**FR-27.** The review record shall carry an "Outside this PR" list for findings on lines the PR
did not touch, capped at about 3 per reviewer. (source: Canon 2026-10-26-5692f27d-8)
  - *Acceptance (rule):* An outside finding never goes to the fix, never blocks the merge and
    never becomes an owner card. (source: Canon 2026-10-26-5692f27d-8)
  - *Acceptance (rule):* The cap limits how many outside findings each reviewer raises from its own
    reading; every outside finding raised is kept. A sweep's outside hits are not counted against
    the cap and are kept together under that sweep's entry. (source: craft, for your veto)

**FR-28.** At the vet, the advisor shall sort each outside finding into a proposed follow-up filing
or a dismissal with a reason. (source: Canon 2026-10-26-5692f27d-8)
  - *Acceptance (rule):* A follow-up filing still waits on the owner's word. (source: Canon
    2026-10-26-5692f27d-8)

### Fixing

**FR-29.** The build session shall commit each fix together with its break-it test. (source:
board · panel 2)
  - *Acceptance (rule):* A fix with a break-it test never lands without the test. (source: board ·
    panel 2)

### Rounds 2 to 4

**FR-30.** In every round after the first, a fix auditor shall check each fix: that it is right,
that it broke nothing next to it, and that a test would fail if the fix were wrong. (source:
Canon 2026-10-27-5692f27d-2)
  - *Acceptance (rule):* The audit of each fix records an answer to all three checks. (source:
    board · panel 3)

**FR-31.** In every round after the first, a scoped finder shall look for new problems in the code
each fix touched. (source: board · panel 3)
  - *Acceptance (rule):* The scoped finder reads only code the fixes touched. (source: board ·
    panel 3)

**FR-32.** The fix auditor shall check that each committed break-it test matches what the test
reviewer wrote. (source: Canon 2026-10-27-5692f27d-3)
  - *Acceptance (rule):* A changed test carries the build session's explanation; a change that
    weakens the test is a blocking finding on the fix. (source: Canon 2026-10-27-5692f27d-3;
    craft, for your veto)

**FR-33.** The review loop shall run no separate review pass on the final commit. (source: Canon
2026-10-27-5692f27d-2)
  - *Acceptance (rule):* A converged review that needed fixes ends on a round's audit and scoped
    finder. (source: Canon 2026-10-27-5692f27d-2)

**FR-34.** When the same fix fails its audit in two rounds in a row, the review loop shall make one
automatic recovery attempt and, if the fix still fails, offer the owner the stall menu, as today.
[cite: plugins/superheroes/skills/review-code/reference/round-driver.md § reached only after one invisible self-recovery]
(source: board · panel 3; craft, for your veto)
  - *Acceptance (rule):* The stall menu's choices are unchanged. (source: board · panel 3)
  - *Acceptance (rule):* The recovery attempt and the stall menu run only inside the 4 rounds. A
    stall that reaches round 4 is handed back at the cap like any other open finding, and no menu
    choice takes a session past round 4. (source: framing; board · panel 4)

### How a session stops

**FR-35.** When a round leaves nothing blocking, the review loop shall hand the PR back, round 1
included. (source: board · panel 4)
  - *Acceptance (Given-When-Then):* Given a round-1 panel whose findings are all wrong or
    non-blocking, when the round ends, then the PR is handed back with no second round. (source:
    board · panel 4)

**FR-36.** A review session shall stop at 4 rounds. (source: Canon 2026-10-27-5692f27d-8)
  - *Acceptance (rule):* No session's review record shows a fifth round, except the one extra
    audit round the advisor may order at the vet (FR-39), which the record labels as that.
    (source: Canon 2026-10-27-5692f27d-8; Canon 2026-10-27-5692f27d-11)

**FR-37.** When a session ends round 4 with a finding still open, the review loop shall hand the PR
back with what is open, Important and Critical alike. (source: Canon 2026-10-27-5692f27d-8)
  - *Acceptance (rule):* There is no automatic extra round, no separate park state at the cap and
    no new review session started to keep going. (source: Canon 2026-10-27-5692f27d-11; board ·
    panel 8)

**FR-38.** When a PR is handed back at the cap, the advisor shall decide each open finding whose
only consequence is code quality and list it for the owner's veto. (source: Canon
2026-10-27-5692f27d-10)
  - *Acceptance (rule):* No code-quality finding reaches the owner as a question. (source: Canon
    2026-10-27-5692f27d-10)

**FR-39.** When a PR is handed back at the cap with a finding that has a real owner consequence,
the advisor shall choose one of three next steps: one extra round that only audits the last
round's fixes, a leftover for the owner, or a send-back to the builder to rethink the approach.
(source: Canon 2026-10-27-5692f27d-11)
  - *Acceptance (rule):* The extra audit round runs no panel and no new search. (source: Canon
    2026-10-27-5692f27d-11)

**FR-40.** The review loop shall allow the extra audit round at most once per PR. (source: Canon
2026-10-27-5692f27d-11)
  - *Acceptance (Given-When-Then):* Given a PR that already had its extra audit round, when it is
    handed back at the cap again, then the advisor's choices are a leftover or a rethink.
    (source: Canon 2026-10-27-5692f27d-11)

**FR-41.** The advisor shall never take an open Critical to the owner as a leftover. (source:
Canon 2026-10-27-5692f27d-8)
  - *Acceptance (rule):* An open Critical leaves the cap only by an extra audit round or a rethink.
    (source: Canon 2026-10-27-5692f27d-8)

**FR-42.** When a finding reaches the owner as a leftover, the advisor shall frame it in owner
terms: what accepting it means, what it costs and what it risks. (source: Canon
2026-10-27-5692f27d-10)
  - *Acceptance (rule):* A leftover never asks the owner to pick between code fixes. (source:
    Canon 2026-10-27-5692f27d-10)

### After handback

**FR-43.** When a PR comes back for review (after a vet send-back, a fix leg, a catch-up with its
base or a hand fix), the new session shall review only what changed since the last reviewed
commit, with the fix audit and scoped finder of a later round. (source: Canon
2026-10-26-5692f27d-5)
  - *Acceptance (Given-When-Then):* Given a PR reviewed once and sent back for a 40-line fix, when
    it is reviewed again, then no full panel runs and the review reads only those 40 lines and
    what they touch. (source: Canon 2026-10-26-5692f27d-5)

**FR-44.** A new session shall run a full panel only when the change since the last reviewed
commit is over about 1,000 countable lines or touches a risk area the PR had not touched before.
(source: Canon 2026-10-26-5692f27d-5; craft, for your veto)
  - *Acceptance (rule):* "Countable lines" here is the count of FR-6. (source: craft, for your veto)

**FR-45.** At the vet, the advisor shall check the PR description's claims against the change.
(source: Canon 2026-10-27-5692f27d-1)
  - *Acceptance (rule):* Every vet receipt records the claims check. (source: Canon
    2026-10-27-5692f27d-1)

### Removed

**FR-46.** The review loop shall have no grounding reviewer. (source: Canon 2026-10-27-5692f27d-1)
  - *Acceptance (rule):* No review record or merge sheet carries a "grounding seat not run" line.
    (source: Canon 2026-10-27-5692f27d-1; board · panel 5)

**FR-47.** Code review shall have no read-only mode. (source: Canon 2026-10-26-5692f27d-10)
  - *Acceptance (rule):* Review always runs as the one loop; a vet's narrow doubt goes to one
    independent reviewer given the doubt. (source: Canon 2026-10-26-5692f27d-10)

**FR-48.** Code review shall review only PRs built in the project it serves. (source: Canon
2026-10-26-5692f27d-10)
  - *Acceptance (rule):* A request to review someone else's PR is told plainly it is not
    supported. (source: Canon 2026-10-26-5692f27d-10; craft, for your veto)

**FR-49.** Code review shall run no project tests in throwaway copies of the repository.
(source: board · panel 8)
  - *Acceptance (rule):* Every break-it test runs in the build session's own working copy.
    (source: board · panel 8; Canon 2026-10-27-5692f27d-3)

### The review record

**FR-50.** The review record shall show the round count out of 4, the kind of mistake on each
finding, each repeat mark, the "Outside this PR" list, and how much of a sliced change the slice
reviewers left unread. (source: board · panel 7)
  - *Acceptance (rule):* A record reads like the sample on board panel 7. (source: board · panel 7)

### Lanes

**FR-51.** The light and micro lanes shall follow the same 4-round cap and the same
only-what-changed rule for a PR that comes back. (source: craft, for your veto)
  - *Acceptance (rule):* A light-lane review record never shows a fifth round in one session.
    (source: craft, for your veto)

### Knowing it worked

**FR-52.** The gardening-pass measure shall count each choice the advisor made at the cap and what
happened next. (source: board · panel 4; board · panel 9)
  - *Acceptance (rule):* Each pass shows, per choice: how often it was made, whether an extra
    audit round settled what was open, whether an accepted leftover later became an escape, and
    whether a rethink converged. (source: board · panel 4)

**FR-53.** At each gardening pass after this work ships, the advisor shall check two revisit
conditions and bring any that is met to the owner: a false PR claim reached merge past the vet,
which reopens the grounding reviewer's removal (FR-46); or the security and premortem reviewers
still look expensive for what they find, which reopens their seating (FR-3). (source: Canon
2026-10-27-5692f27d-1; Canon 2026-10-27-5692f27d-5)
  - *Acceptance (rule):* Each gardening pass records whether each condition was met and, when
    one was, that it went to the owner. (source: craft, for your veto)

## Significant unhappy paths

**UFR-1.** If a finding carried over from an abandoned session has no outcome, then the review
loop shall settle it as fixed when later commits show it fixed, and otherwise send it back to the
reviewers. (source: board · panel 6; craft, for your veto)
  - *Acceptance:* Given a carried finding with no outcome and a later fix for it, when the next
    review runs, then the record shows it as fixed and the PR can read as reviewed. (source: board
    · panel 6)

**UFR-2.** If the layer below a stacked PR is ahead of what the upper layer was last brought current
with, then the review session shall catch up to the lower layer's current head before it reviews.
(source: board · panel 6; craft, for your veto)
  - *Acceptance:* Given an upper layer whose lower layer moved, whether before or during the review
    session, when it is reviewed, then no finding in its record comes from the lower layer's old
    head. (source: board · panel 6)

**UFR-3.** If a test run fails once on code the round did not change, then the review loop shall
re-run the same check once and record both results. (source: board · panel 6; craft, for your
veto)
  - *Acceptance:* Given one flaky failure, when the re-run passes, then the round goes on and the
    record shows both runs; when the re-run fails, then the round stops as today. (source: board ·
    panel 6)

**UFR-4.** If a reviewer's break-it test needs a small change to run, then the build session shall
make the change and say why. (source: board · panel 6; Canon 2026-10-27-5692f27d-3)
  - *Acceptance:* Given a break-it test that fails to compile, when the build session fixes the
    compile error, then the review continues to the verifier and never ends unable to certify
    over it. (source: board · panel 6)

**UFR-5.** If the fix auditor finds that a change to a break-it test weakened it, then the review
loop shall restore the reviewer's test and give the test reviewer one chance to correct it.
(source: board · panel 6; craft, for your veto)
  - *Acceptance:* Given a weakened test, when the auditor flags it, then the weakened version is
    never kept, and a still-open finding at the cap is handed back like any other. (source: board
    · panel 6)

**UFR-6.** If a review run crashes or its connection drops, then the review loop shall keep every
finding raised so far. (source: craft, for your veto)
  - *Acceptance:* Given a dropped run, when the review resumes or restarts, then every earlier
    finding is in the record with its outcome or marked open. (source: craft, for your veto)

**UFR-7.** If a project has no command that verifies its code, then setup shall tell the owner
plainly that code review needs one. (source: Canon 2026-10-26-5692f27d-11)
  - *Acceptance:* Given a project with no verify command, when setup runs, then the owner reads
    that code review is not available until a verify command is set. (source: Canon
    2026-10-26-5692f27d-11)

**UFR-8.** If a review is already running when its project adopts the release carrying this work,
then that review shall finish under the old rules. (source: framing; craft, for your veto)
  - *Acceptance:* Given an in-flight review at adoption, when it ends, then its record is complete
    under the rules it started with. (source: craft, for your veto)

## Non-functional requirements

- **No silent loss:** nothing a reviewer finds is dropped from the review record; every finding
  ends with a recorded outcome or is shown open. (source: Canon 2026-10-10-d6064e1d-6)
- **Independence:** every reviewer, verifier, auditor and search description comes from a
  different model family than every maker of the change. (source: Canon 2026-10-10-d6064e1d-12;
  Canon 2026-10-27-5692f27d-9)
- **No target number:** the measure is read as a trend at each gardening pass; this work sets no
  target for rounds, tokens or minutes, and no gate. (source: framing)

## UI / UX

The approved build board is the design: `board/build-board.html` beside this spec, at
https://claude.ai/artifact/VSbmFZk1oeHRLrVB4Znuw8 (version 4). Panel 1 covers round 1, panels 2
and 3 the fixes and later rounds, panel 4 how a session stops, panel 5 handback, panel 6 failures,
panel 7 the review record, and panel 8 what is removed. (source: board · panel 1 to 9)

## Definition of done / success

- Every requirement above is built and released together in one plugin release. (source: framing)
- Whether this work lost real catches is read, after it ships, from the gardening-pass measure
  (#2189) and the escape logging (#2190). (source: Canon 2026-10-27-5692f27d-6)

## Assumptions & dependencies

- The gardening-pass measure is filed as #2189 and the escape logging as #2190; this work relies
  on both for its proof and adds the cap-choice counts (FR-52) to #2189. (source: Canon
  2026-10-27-5692f27d-6; board · panel 9)
- Splitting big changes exists today, by top-level folder above 1,500 changed lines or 20 files,
  with one gap reviewer over the whole change. This work replaces how it cuts and what it counts.
  [cite: plugins/superheroes/lib/delta_surface.py § DEFAULT_SHARD_MAX_LINES = 1500] (source: board
  · panel 1)
- Today's cap is 7 rounds with a hard ceiling of 10.
  [cite: plugins/superheroes/skills/review-code/reference/round-driver.md § maxRoundsAbsolute]
  (source: framing)
- Today the grounding reviewer never runs inside the loop.
  [cite: plugins/superheroes/skills/review-code/reference/grounding-seat.md § Known limitation]
  (source: Canon 2026-10-27-5692f27d-1)
- The seating check in FR-53 reads the gardening-pass measure's finding outcomes by lens (#2189).
  (source: Canon 2026-10-27-5692f27d-5)

## Constraints

- Ships in one plugin release with no trial mode. (source: framing; craft, for your veto)
- Keeps the light, full and micro lanes; no new lane. (source: Canon 2026-10-08-d6064e1d-12)

## Out of scope

- Merging routine changes without a merge sheet (declined for now as collector item 397).
  (source: registry · item 397)
- Seating security or premortem by risk area. (source: Canon 2026-10-27-5692f27d-5)
- A replay of past cases before release. (source: Canon 2026-10-27-5692f27d-6)
- Building the gardening-pass measure (#2189) and the escape logging (#2190), which are their own
  issues. (source: Canon 2026-10-27-5692f27d-6)
- Code review for a project with no verify command, and for someone else's PR. (source: Canon
  2026-10-26-5692f27d-10; Canon 2026-10-26-5692f27d-11)
- The fix that would let today's restricted fixer read its order (#2186), which this work makes
  unnecessary. (source: Canon 2026-10-26-5692f27d-4)

## Amendments

_No amendments since the last full approval._

## Coverage

| Area | Disposition | Show-it? | Where / why |
| --- | --- | --- | --- |
| Empty & first-run | Specify | No | UFR-7 (no verify command), UFR-8 (in-flight reviews at adoption) |
| Invalid & malformed input | Specify | No | UFR-4 (a break-it test that won't compile), UFR-5 (a weakened test) |
| Boundaries & limits | Specify | No | FR-5 to FR-7 (slicing bar), FR-36 to FR-40 (the cap), FR-27 (outside-list cap) |
| Errors & failures | Specify | No | UFR-1, UFR-3, UFR-6, FR-34 (a fix that keeps failing its audit) |
| Access & permissions | Specify | No | FR-2 (only the verifier closes a finding as wrong), FR-48 |
| Duplicates & double-actions | Specify | No | FR-19 to FR-21 (repeat findings) |
| Conflicting / simultaneous use | Specify | No | UFR-2 (a moved lower layer in a stack) |
| Misuse & abuse | N-A | — | Deliberate faking of review records is outside the trust boundary (Canon 2026-10-08-d6064e1d-20) |
| Reach (i18n / a11y) | N-A | — | No new owner-facing screen; sheets keep today's template |
| Wording & tone | Specify | Yes | FR-42 (leftovers in owner terms), FR-50 and board panel 7 (record wording) |
| Workflow shape | Specify | Yes | FR-13 to FR-17 (break-it before the verifier), FR-35 to FR-40, board panels 1 to 5 |
| Placement & prominence | Specify | No | FR-27 (outside findings in the record, not on the sheet), FR-21 |
| Limits & defaults | Specify | No | FR-36 (4 rounds), FR-40 (one extra audit round per PR), FR-44 |
| Tier & access boundaries | Specify | No | FR-3 (specialists on any risk area), FR-51 (light and micro lanes) |
| Visibility & disclosure | Specify | Yes | FR-50, FR-52, UFR-3 (both test runs recorded) |
