# Contract register — a-review-loop-that-converges-in-few-rounds-and-sta-3f628c

Cross-child technical decisions for the epic (#2185) that lands the spec the owner approved on
2026-10-27, `a-review-loop-that-converges-in-few-rounds-and-sta-3f628c` (committed beside this file,
`spec.md`). The entries are numbered, and each is a plain binding sentence with its consuming
children named. Every entry is either decided now or names the child that decides the detail
(**decide-by**). The advisor owns edits; a builder never amends the register it is graded against.
Children quote each entry's first paragraph **verbatim**. The `*Source:*`, `*Status:*` and
`*Consumers:*` lines are trailer and are not quoted. C1 is a native stack: its register entries
stay quoted on C1's feature issue, its layer bodies name the entries that bind them, and a layer's
register check runs on C1's body with the token `C1` (`skills/showrunner/reference/register-check.md`
§ Stack layer inputs).

No entry adds product opinion. Where a decision comes from the spec, the `*Source:*` line names the
spec text and the Canon entry ids the spec cites (`docs/superheroes/canon.md`). Where the spec is
silent, the entry marks the gap **decide-by**, and the named child records its choice for the
owner's veto. If the choice would change what the owner sees, is asked or keeps, the child raises it
as an owner call instead.

Two entries are cross-epic seams with single issues outside this epic: R9 and R10 with #2189 (the
gardening-pass measure) and R11 with #2190 (the escape logging). Each of those issues stands in for
the missing register on its side: the advisor appends the quote blocks in [`seams/`](seams/) to its
body when this package files (`skills/showrunner/reference/decomposition.md` § Reciprocal cross-epic
seams and § The single-issue fast path).

Children: C1 the core loop (a native stack of thirteen layers, C1-L1 to C1-L13) · C2 big changes ·
C3 findings outside the PR · C4 copies of a bug.

---

**R1 — One stack and one release for the core loop; each add-on whole.** The core loop, C1, is one native stack of thirteen layers that merges with one `gh stack merge` only once every layer is vetted, and the plugin release that first carries any part of C1 carries all of it, FR-6's line count included. Each add-on, C2 (big changes), C3 (findings outside the PR) and C4 (copies of a bug), merges whole as one PR, never before C1's stack has merged unless it is built as a layer above C1's top layer and merges with that stack, and C4 merges only with or after C3. No child ships behind a switch, a flag or a trial mode, and no child cuts a release or asks for one. Until an add-on merges, the behavior it replaces keeps working as it ships today: big changes are split as today's splitting does, findings on lines the PR did not touch are handled as they are today, and findings carry no kind of mistake. Each child's consumer-visible change gets its `plugins/superheroes/TRANSITION.md` note in the unreleased section of the release that carries it.
*Source:* Definition of done, first bullet ("The core loop ships first, in one plugin release, and includes the line count of FR-6. The three add-ons may ship in a later release … Copies of a bug ships with or after findings outside the PR"); Constraints ("No trial mode: the core loop ships in one release, and each add-on ships whole in its release"); Canon 2026-10-28-5692f27d-1; `rubric/native-stacks.md` § How a stack merges and § Each layer is a sub-issue (an add-on whose only blocker is C1's READY top layer launches as a layer above it).
*Status:* decided. The sentence on what keeps working until an add-on merges is read from the Definition of done's "may ship in a later release"; the spec does not state the interim; the advisor confirmed this reading on 2026-10-28 (craft, open to the owner's veto at the merge word).
*Consumers:* C1, C2, C3, C4.

**R2 — The review record.** Every part this spec adds to the review record goes into the one record the plugin already writes (`plugins/superheroes/lib/review_record.py`, filled from a full-lane session by `plugins/superheroes/lib/review_record_session.py`), never into a second record. C1 adds: the round count out of 4, with the extra audit round labelled as one (R8); per round-1 reviewer, the parts of the change it read (R4); on each finding, its grade and the reason (R6), its repeat mark naming the earlier finding it matches, and the output of each run of its break-it tests on the unfixed code (R7); and, for a test run that failed once on code the round did not change and was run again, both results. Three parts are filled by the add-ons and show only once the child that produces them has merged, with no empty placeholder before then: the kind of mistake and the places it was found, on each finding (C4); the "Outside this PR" list (C3, R12); and how much of a sliced change the slice reviewers left unread (C2). Every finding raised, in every round and every session, stays in the record with its recorded outcome or is shown open, a crashed or dropped run included. The field names and shapes are decide-by: C1, in its record layer, before the layers and children that fill them build.
*Source:* FR-51 and its two acceptances; FR-4; FR-14; FR-19; FR-22; FR-37; UFR-3; UFR-6; Non-functional requirements (No silent loss; Canon 2026-10-10-d6064e1d-6); board · panel 7.
*Status:* decided; **decide-by: C1** (layer C1-L1) for the field names and shapes.
*Consumers:* C1, C2, C3, C4.

**R3 — Countable lines and the 1,000-line bar.** One counter in `plugins/superheroes/lib/` gives a change's countable lines: every changed line, test lines and doc lines included, except lines in files moved without change, in generated files, in lock files, in files deleted whole, and in files the change proves byte-for-byte identical to a named source by a checksum proof that covers each such file; it checks each such file against the proof, counts any file the proof does not cover or match, and also returns the files whose countability it could not settle. No reviewer in any round (a round-1 reviewer or slice, the fix auditor, the scoped finder, or a returning PR's panel) is given a proven copy to read: every seat takes the files it may be given from one driver list that leaves them out. C2 does not count a proven copy as an unread part, and the review record lists the proven copies with the proof for the advisor's vet (R2). One constant holds the bar of 1,000 countable lines, read by C1's choice of a full panel for a PR that comes back for review and by C2's slicing. Each consumer applies its own rule to a file the counter could not settle; C2 cuts smaller. The plugin's non-test size count for builds (`plugins/superheroes/lib/size_count.py`) stays as it is. Where the counter lives (a new helper or a separate mode of `size_count.py`), what marks a file as generated, and the shape of the copy proof are decide-by: C1.
*Source:* FR-6 and its three acceptances (two added by amendment 1, 2026-10-28; Canon 2026-10-28-0b372f49-1); FR-5; FR-7 and its acceptance; FR-45 and its first acceptance.
*Status:* decided; **decide-by: C1** (layer C1-L5) for the counter's home, the generated-file rule and the copy proof's shape.
*Consumers:* C1, C2.

**R4 — What a round-1 reviewer read.** Every round-1 reviewer returns, with its findings, the list of the parts of the change it actually read, by file and line range, and the review record shows each list (R2). A reviewer that returns no list counts as having read nothing, never as having read the whole change. C2 reads these lists to find the parts of a sliced change left unread and the unread share the record shows. The list's exact shape is decide-by: C1.
*Source:* FR-4 and its acceptance; FR-8 and its acceptance; FR-51.
*Status:* decided; **decide-by: C1** (layer C1-L5) for the list's shape. That a missing list counts as nothing read is the safe reading of FR-8 (an unread part gets its own slice), for the owner's veto.
*Consumers:* C1, C2.

**R5 — Independence.** Every reviewer, verifier, fix auditor, scoped finder and test-reviewer run, and the author of every search description, comes from a different model family than every maker of the change. The build session is a maker of every fix it applies, and a reviewer's own break-it tests do not make that reviewer a maker. When no seat from a different family than every maker can run, that seat counts as not run, as today, and no session stands in for it or seats a reviewer from a maker's family.
*Source:* Non-functional requirements (Independence; Canon 2026-10-10-d6064e1d-12; Canon 2026-10-27-5692f27d-9); FR-1; FR-11's first acceptance; FR-24; the risk-calibrated review package's register R5 (`docs/superheroes/risk-calibrated-review-that-learns-dec0af/register.md`), unchanged.
*Status:* decided.
*Consumers:* C1, C2, C4.

**R6 — A finding's grade, and who closes it as wrong.** Only the independent verifier closes a finding as wrong, recorded as the outcome `shown-wrong` (`plugins/superheroes/lib/review_findings_schema.py`, `OUTCOMES`); the build session and every other reviewer never do. The verifier grades each finding on its own as confirmed, plausible or wrong, with its reason, using the output of the finding's break-it tests on the unfixed code where there are any (R7). A finding raised in a slice or in a slice of unread parts (C2), and a search hit inside the PR (C4), take a grade from the same verifier before any fix.
*Source:* FR-2 and its acceptance; FR-14; FR-15; FR-17; FR-8; FR-26 and its acceptance; Canon 2026-10-27-5692f27d-3.
*Status:* decided.
*Consumers:* C1, C2, C4.

**R7 — Break-it tests.** Only the test reviewer writes a break-it test, and a fresh run of the test reviewer writes the one second test a missed path allows. The build session runs each attached break-it test in its own working copy, on the unfixed code, exactly as written, and saves its output without judging it before the verifier grades; nothing in code review runs project tests in a throwaway copy of the repository. The build session may make the small change a test needs to run, and records why. A fix is committed together with its break-it test, and the fix auditor checks that the committed test matches what the test reviewer wrote: a change that weakens it is a blocking finding on the fix, the reviewer's version is restored, and the test reviewer gets one chance to correct it.
*Source:* FR-11 to FR-17; FR-30; FR-33; FR-50; UFR-4; UFR-5; Canon 2026-10-27-5692f27d-3; board · panels 1, 2, 3 and 6.
*Status:* decided.
*Consumers:* C1, C2.

**R8 — The rounds and the cap.** Round 1 runs the panel (on a sliced change, the slices and the seams check, C2), the break-it runs, the verifier and synthesis, and then the build session applies the fixes. Every later round runs the fix auditor over each fix and the scoped finder over the code the fixes touched, never a full panel, a slice or a seams check, and no separate pass runs on the final commit. A session stops at the first round that leaves nothing blocking, round 1 included, and at 4 rounds at most; at the cap it hands the PR back with every open finding, Important and Critical alike, with no park state and no new session started to keep going. The only round past 4 is the one extra audit round the advisor may order at the vet, at most once per PR, which audits the last round's fixes only, runs no panel and no new search, and is labelled in the record as an extra audit round. When the same fix fails its audit in two rounds in a row, the loop makes one automatic recovery attempt, and none when the second failure is in round 4; if the fix still fails, it hands back as at the cap. Nothing from the review reaches the owner mid-review: there is no stall menu and no mid-review owner gate. Three details are decide-by: C1: how the advisor's order for the extra audit round reaches the session; whether a finding the scoped finder raises in rounds 2 to 4 is graded by the verifier, and with break-it tests, as in round 1; and what the loop does with an open blocking finding that only the owner's choice can settle. A choice among these that changes what the owner is asked is raised as an owner call.
*Source:* FR-31 to FR-41 and their acceptances; FR-9's acceptance (seams check in round 1 only); FR-36; FR-40's acceptance; Canon 2026-10-27-5692f27d-2; Canon 2026-10-27-5692f27d-8; Canon 2026-10-27-5692f27d-11; Canon 2026-10-28-5692f27d-3; board · panels 3 and 4.
*Status:* decided; **decide-by: C1** (layers C1-L4 and C1-L10) for the three details named.
*Consumers:* C1, C2, C3, C4.

**R9 — The cap choices #2189 counts.** When a PR is handed back with an open finding that has a real owner consequence, the advisor's vet receipt records the one next step chosen for that finding, an extra audit round, a leftover for the owner, or a send-back to the builder to rethink the approach, in one fixed field that #2189's gardening-pass measure counts; the review record labels the extra audit round (R2), and the record of the PR's next review session shows whether a rethink converged. This epic builds the recording and nothing of the count; #2189 builds the count and reads a window from before this work ships as unmeasured. The field's name and its three spellings are decide-by: C1, recorded in this entry before C1's vet layer merges, and #2189 reads them as recorded here.
*Source:* FR-40 and its acceptance; FR-41; FR-53 and its two acceptances; Assumptions & dependencies (first bullet); #2189's body (the cap-choice measure).
*Status:* decided; **decide-by: C1** (layer C1-L12) for the field and spellings. Cross-epic seam with #2189, recorded on both sides: #2189's issue body quotes this entry verbatim ([`seams/2189.md`](seams/2189.md)).
*Consumers:* C1, #2189.

**R10 — The seating check reads #2189's row.** At each gardening pass after this work ships, the advisor's check on the security and premortem reviewers' seating reads, from #2189's row for the window, those two reviewers' finding outcomes by lens and their tokens and minutes per seat, and records the numbers beside its judgment; a number #2189 reads as unmeasured is recorded as unmeasured, never as zero. Whether the review record already carries each seat's tokens and minutes for #2189 to read, and the field it gains if not, are decide-by: C1, agreed with #2189 before either side builds that field.
*Source:* FR-54 and its third acceptance; Assumptions & dependencies (last bullet: "#2189 adds for this check"); #2189's body (per-seat tokens and minutes, folded 2026-10-28).
*Status:* decided; **decide-by: C1** (layer C1-L1) for the record field, if one is needed. Cross-epic seam with #2189, recorded on both sides ([`seams/2189.md`](seams/2189.md)).
*Consumers:* C1, #2189.

**R11 — False PR claims logged beside review escapes.** A false PR claim found after merge (a claim in a PR description that did not hold: that tests ran, a row of its definition-of-done table, or that the verify command passed) is appended to the misses log by the act that finds it, in the same entry shape as a review escape, #2190's line naming what would have caught it included, and is marked as a false PR claim naming the PR, the claim and what showed it false. Each gardening pass shows the count of false PR claims in its window, zero included, apart from the escape tallies. The marker's spelling is decide-by: C1; whichever of C1 and #2190 lands second conforms to the entry shape the first one shipped.
*Source:* FR-54, its second acceptance; FR-46; FR-47; #2190's body (the escape line).
*Status:* decided; the marker is decided in C1-L13: the misses-log line `false PR claim: <the claim> — shown false by <what showed it false>` and `"marker": "false-pr-claim"` in the tally input. Cross-epic seam with #2190, recorded on both sides: #2190's issue body quotes this entry verbatim ([`seams/2190.md`](seams/2190.md)).
*Consumers:* C1, #2190.

**R12 — The "Outside this PR" list.** A finding on lines the PR did not touch goes to the review record's "Outside this PR" list. Each reviewer raises at most about 3 such findings from its own reading, and every one raised is kept; a sweep's outside hits are not counted against that cap and are kept together under the sweep's own entry, each naming its file, its line and the mistake. An outside finding never goes to the fix, never blocks the merge and never becomes an owner card. At the vet the advisor sorts each one into a proposed follow-up filing, which still waits on the owner's word, or a dismissal with its reason. The cap's exact number is decide-by: C3.
*Source:* FR-27 and its acceptance; FR-28 and its two acceptances; FR-29 and its acceptance; Canon 2026-10-26-5692f27d-8; Canon 2026-10-27-5692f27d-9.
*Status:* decided; **decide-by: C3** for the cap's number.
*Consumers:* C3, C4.

**R13 — What is removed stays removed.** No child keeps or brings back, in code, doctrine or a record line: code review's grounding seat (`plugins/superheroes/agents/grounding-seat.md`, `plugins/superheroes/lib/grounding_stage.py`), while the spec checks' grounding reviewer (`plugins/superheroes/agents/grounding-reviewer.md`), which is not part of code review, stays; the read-only review mode; review of a PR not built in the project the plugin serves; review without a verify command; any break-it or project test run in a throwaway copy of the repository; a separate fixer agent, its fix orders and its locked-down sandbox; the stall menu; and the round cap of 7 with its ceiling of 10.
*Source:* FR-1 and its acceptance; FR-35's first acceptance; FR-37; FR-47 to FR-50 and their acceptances; UFR-7; What this spec changes elsewhere (Shipped rules); the spec's definition of "the review loop" (How to read this spec).
*Status:* decided.
*Consumers:* C1, C2, C3, C4.

**R14 — No target, no gate, no new lane.** Nothing this epic ships sets a target or adds a gate on rounds, tokens or minutes; its measures are read as a trend at the gardening pass. The light, full and micro lanes stay and no lane is added; the light and micro lanes keep one independent reviewer and follow the same 4-round cap and the same only-what-changed rule for a PR that comes back for review.
*Source:* Non-functional requirements (No target number); Constraints (keeps the three lanes; Canon 2026-10-08-d6064e1d-12); FR-52 and its acceptance.
*Status:* decided.
*Consumers:* C1, C2, C3, C4.

**R15 — Shipped text and glossary terms.** Plugin text this epic ships states its rules without saying where they were decided (no requirement numbers, Canon entry ids, dated rulings, or issue and PR numbers), per `plugins/superheroes/rubric/prose-standard.md` § Shipped surfaces carry no project provenance, and names nothing specific to one project that uses the plugin. Each new term gets one entry under a stable heading in `plugins/superheroes/rubric/glossary.md`, added by the child that first ships it, and every other surface links that heading: verifier, fix auditor, scoped finder and extra audit round (C1); slice and seams check (C2); outside finding (C3); kind of mistake and search description (C4).
*Source:* `plugins/superheroes/rubric/prose-standard.md` § Shipped surfaces carry no project provenance; the risk-calibrated review package's register R11 and R12, whose rule this repeats for this epic's terms.
*Status:* decided.
*Consumers:* C1, C2, C3, C4.

**R16 — Marking what this spec changes elsewhere.** The advisor, not a child, marks the requirements of the two other approved specs that this spec changes, each at the post-merge step of the child whose merge lands its replacement on main: in the risk-calibrated review spec (`risk-calibrated-review-that-learns-dec0af`), FR-16, FR-23, FR-24, UFR-2 and its Constraints line on the round caps, the stuck-loop stop and the scoped fixer when C1 merges, and FR-38's second acceptance when C3 merges; in the converge-faster spec (`make-the-shared-review-and-fix-loop-converge-faste-4c45d8`), FR-3 when C4 merges. A spec already marked delivered takes one dated `supersededInPart` entry per marking (`plugins/superheroes/lib/definition_doc.py mark-superseded`, naming the sections and this spec's approval as the ruling); a spec not yet marked delivered is first marked delivered from its closure receipt (`definition_doc.py mark-delivered`), and a spec whose work is still open takes an amendment instead (`plugins/superheroes/skills/showrunner/reference/amendments.md`). The shipped rules the same section lists are child scope, each removed by the layer the coverage map names.
*Source:* What this spec changes elsewhere ("The advisor marks them"); `plugins/superheroes/skills/architect-spec/reference/spec-content.md` § the spec lifecycle, as shipped on main by #2187 and #2191 (approved and building, delivered, superseded in part).
*Status:* decided. The timing (at the merge that lands each replacement, so no spec reads superseded before its replacement is on main) is the advisor's craft, for the owner's veto.
*Consumers:* C1, C3, C4.
