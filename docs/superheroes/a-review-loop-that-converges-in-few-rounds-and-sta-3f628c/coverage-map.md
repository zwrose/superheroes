# Coverage map — a-review-loop-that-converges-in-few-rounds-and-sta-3f628c

Acceptance-level allocation of every criterion of the spec the owner approved on 2026-10-27,
`a-review-loop-that-converges-in-few-rounds-and-sta-3f628c` (`spec.md`, beside this file). Each
criterion is owned by exactly one child of epic #2185, by #2189 for the one requirement the spec
gives it, or, for the spec's Definition of done, by the epic's closure. Drafted 2026-10-28 (UTC),
after the approval.

**What counts as one criterion.** Each acceptance bullet of an FR or UFR is one criterion, at the
spec's own bullet granularity: 76 bullets across FR-1 to FR-54 and UFR-1 to UFR-8. Every FR and UFR
carries at least one acceptance bullet, so no statement is counted on its own; an FR's statement is
owned by the child that owns its bullets. Each of the three non-functional lines (No silent loss,
Independence, No target number) is one criterion. Each of the two Definition of done bullets is one
criterion, owned by the epic's closure. That makes 81 criteria. The table has 82 rows, because one
bullet is split at its own sentences into two rows (declared below).

**Children and layers.** C1, the core loop, is a native stack of thirteen layers (C1-L1 to C1-L13);
a C1 row names the layer that builds it, and every C1 row is owned by C1, the child. C2 (big
changes), C3 (findings outside the PR) and C4 (copies of a bug) are single-PR children.

**Owned outside this epic.** FR-53 (the gardening-pass measure counts the advisor's choices at the
cap) is built by **#2189**, as the spec's Definition of done and FR-53's second acceptance say: "#2189
builds this count. This work depends on it and builds nothing for it." Both FR-53 bullets are
#2189's. What this epic owes that count is the recording it reads, register entry R9, which C1-L12
builds; #2189's body quotes R9 (`seams/2189.md`).

**Declared split.** One bullet is split, inside C1, at its own sentences:

- **FR-48**'s acceptance ("Review always runs as the one loop. A vet's narrow doubt goes to one
  independent reviewer given the doubt."). The first sentence is **C1-L3**'s, which removes the
  read-only mode so review runs only as the loop. The second is **C1-L12**'s, because it is the
  advisor's act at the vet (today's vet doctrine sends a narrow doubt to a read-only review). Both rows
  are C1's; the split only names the layer.

No other criterion is split, and no criterion spans two children.

**Criteria owned whole where another child also touches the behaviour.** These are not splits;
each names its one owner and the register entry that binds the other child:

- **FR-51** (what the review record shows) is **C1-L1**'s, both bullets: the record layer builds the
  parts C1 produces and the rule that a part shows only once its producer has merged. The three parts
  the add-ons produce, the kind of mistake (C4), the "Outside this PR" list (C3) and the unread share
  of a sliced change (C2), are each built by that child into the record shape R2 fixes; each add-on's
  DoD carries its part.
- **FR-4** (each round-1 reviewer records the parts it read) is **C1-L5**'s. C2 reads those lists for
  FR-8 and FR-10 (R4).
- **FR-6** (countable lines) is **C1-L5**'s, its two acceptances added by amendment 1 (2026-10-28: proven copies are not counted or read and are listed in the record) included. C1-L11 reads it for FR-45, and C2 for FR-5, FR-7 and FR-8 (R3).
- **FR-26** (a search hit inside the PR goes through the verifier) is **C4**'s; the verifier it goes
  through is C1-L7's (R6).
- **FR-27** (outside search hits go on the "Outside this PR" list) is **C4**'s; the list is C3's (R12).
- **FR-41** (one extra audit round per PR) is **C1-L4**'s: the loop refuses a second one, which is
  what leaves the advisor only a leftover or a rethink. C1-L12 carries the advisor's side of FR-40.
- **FR-35** is **C1-L4**'s whole, its second acceptance included ("the advisor chooses the next step
  at the vet, as at the cap"): the layer builds the handback; the choice itself is FR-40's, in C1-L12.
- **FR-54**'s second and third acceptances are **C1-L13**'s; the misses-log entry shape it shares
  with #2190 and the row it reads from #2189 are register entries R11 and R10.

**Definition of done.** The spec's first DoD bullet (everything built and released except FR-53, the
core loop first in one release with FR-6's count, the add-ons whole, copies of a bug with or after
findings outside the PR) is the epic's closure: it is graded from the release record after the last
child merges (R1). The second (whether this work lost real catches is read after it ships, from
#2189's measure and #2190's escape logging) is also the epic's closure: the closure receipt names the
first gardening pass after release as where it is read, and C1-L13's revisit checks are the doctrine
that reads it.

## The table

| Req | Bullet | Kind | Criterion (excerpt) | Owner |
| --- | --- | --- | --- | --- |
| FR-1 | 1 | rule | No separate fixer agent, fix order or locked-down fixer sandbox takes part in a review. | **C1** (C1-L9) |
| FR-2 | 1 | rule | No finding in a review record is closed as wrong by the build session or by any reviewer other than the… | **C1** (C1-L7) |
| FR-3 | 1 | rule | A change that touches one risk area seats both specialists. So does a change whose risk is unclear, which,… | **C1** (C1-L5) |
| FR-4 | 1 | rule | The review record shows, per reviewer, the parts read. | **C1** (C1-L5) |
| FR-5 | 1 | GWT | Given a 3,000-line change whose files all sit under one top-level folder, when round 1 starts, then it is… | **C2** |
| FR-5 | 2 | rule | Splitting a big change into separate PRs stays the usual first answer. Slicing is for a PR that is not… | **C2** |
| FR-6 | 1 | rule | Changed test lines and changed doc lines count. | **C1** (C1-L5) |
| FR-6 | 2 | rule | A file the proof covers and matches is given to no reviewer to read, is not an unread part of the change… | **C1** (C1-L5) |
| FR-6 | 3 | GWT | Given a changed file the proof does not cover, or whose content in the change does not match the proof's… | **C1** (C1-L5) |
| FR-7 | 1 | rule | A borderline cut never produces a slice above the bar. | **C2** |
| FR-8 | 1 | rule | An unread part touching a risk area gets a code, a test, a security and a premortem reviewer. | **C2** |
| FR-9 | 1 | rule | The seams check runs once per sliced change, in round 1 only. | **C2** |
| FR-10 | 1 | rule | On a sliced change, the premortem reviewer's read list covers the whole change. | **C2** |
| FR-11 | 1 | rule | A break-it test is written by the test reviewer, never by the build session. | **C1** (C1-L6) |
| FR-11 | 2 | rule | Where a change touches a risk area, the test reviewer also writes break-it tests on the touched areas, as… | **C1** (C1-L6) |
| FR-12 | 1 | rule | The test reviewer asks for no coverage in low-risk code and flags no test style preference. | **C1** (C1-L6) |
| FR-13 | 1 | GWT | Given a finding with a break-it test, when the verifier grades it, then the test's output on the unfixed… | **C1** (C1-L6) |
| FR-14 | 1 | rule | Each finding carries a grade (confirmed, plausible or wrong) and the reason. | **C1** (C1-L7) |
| FR-15 | 1 | GWT | Given a break-it test that passes on the unfixed code down the finding's own path, when the verifier… | **C1** (C1-L7) |
| FR-16 | 1 | GWT | Given the verifier judges that a test missed the finding's path, when the review continues, then a fresh… | **C1** (C1-L7) |
| FR-17 | 1 | rule | The finding is closed as wrong or kept as a judgment call without a test. No third test is written. | **C1** (C1-L7) |
| FR-18 | 1 | rule | Grouped findings get one fix. | **C1** (C1-L8) |
| FR-19 | 1 | rule | A repeat names the earlier finding it matches. | **C1** (C1-L8) |
| FR-20 | 1 | GWT | Given a repeat of a fixed finding, when the old fix still holds, then the repeat keeps the earlier… | **C1** (C1-L8) |
| FR-21 | 1 | GWT | Given a finding closed as wrong because a guard existed, and a later fix that removed the guard, when the… | **C1** (C1-L8) |
| FR-22 | 1 | rule | Unless FR-20 or FR-21 finds its earlier outcome no longer holds, a repeat never goes to the fix and never… | **C1** (C1-L8) |
| FR-23 | 1 | rule | The fix for a finding covers every place it names. | **C4** |
| FR-24 | 1 | rule | The search description comes from the reviewer, never from the build session. | **C4** |
| FR-25 | 1 | rule | One search per confirmed Important or Critical finding. | **C4** |
| FR-26 | 1 | rule | A search hit is never fixed without a verifier grade. | **C4** |
| FR-27 | 1 | rule | An outside hit names its file and line and the mistake. | **C4** |
| FR-28 | 1 | rule | An outside finding never goes to the fix, never blocks the merge and never becomes an owner card. | **C3** |
| FR-28 | 2 | rule | The cap limits how many outside findings each reviewer raises from its own reading. Every outside finding… | **C3** |
| FR-29 | 1 | rule | A follow-up filing still waits on the owner's word. | **C3** |
| FR-30 | 1 | rule | A fix with a break-it test never lands without the test. | **C1** (C1-L9) |
| FR-31 | 1 | rule | The audit of each fix records an answer to all three checks. | **C1** (C1-L10) |
| FR-32 | 1 | rule | The scoped finder reads only code the fixes touched. | **C1** (C1-L10) |
| FR-33 | 1 | rule | A changed test carries the build session's explanation. A change that weakens the test is a blocking… | **C1** (C1-L10) |
| FR-34 | 1 | rule | A converged review that needed fixes ends on a round's audit and scoped finder. | **C1** (C1-L10) |
| FR-35 | 1 | rule | There is no stall menu. Nothing from the review reaches the owner mid-review. | **C1** (C1-L4) |
| FR-35 | 2 | GWT | Given a fix that fails its audit in rounds 2 and 3 and again after the recovery attempt, when that… | **C1** (C1-L4) |
| FR-35 | 3 | GWT | Given a fix that fails its audit in rounds 3 and 4, when round 4 ends, then no recovery attempt runs and… | **C1** (C1-L4) |
| FR-36 | 1 | GWT | Given a round-1 panel whose findings are all wrong or non-blocking, when the round ends, then the PR is… | **C1** (C1-L4) |
| FR-37 | 1 | rule | No session's review record shows a fifth round, except the one extra audit round the advisor may order at… | **C1** (C1-L4) |
| FR-38 | 1 | rule | There is no automatic extra round, no separate park state at the cap and no new review session started to… | **C1** (C1-L4) |
| FR-39 | 1 | rule | No code-quality finding reaches the owner as a question. | **C1** (C1-L12) |
| FR-40 | 1 | rule | The extra audit round runs no panel and no new search. | **C1** (C1-L12) |
| FR-41 | 1 | GWT | Given a PR that already had its extra audit round, when it is handed back at the cap again, then the… | **C1** (C1-L4) |
| FR-42 | 1 | rule | An open Critical leaves the cap only by an extra audit round or a rethink. | **C1** (C1-L12) |
| FR-43 | 1 | rule | A leftover never asks the owner to pick between code fixes. | **C1** (C1-L12) |
| FR-44 | 1 | GWT | Given a PR reviewed once and sent back for a 40-line fix, when it is reviewed again, then no full panel… | **C1** (C1-L11) |
| FR-45 | 1 | rule | "Countable lines" here is the count of FR-6. | **C1** (C1-L11) |
| FR-45 | 2 | rule | A change whose risk is unclear counts as touching a risk area, as in FR-3. It starts a full panel unless… | **C1** (C1-L11) |
| FR-46 | 1 | rule | The vet receipt lists each such claim with its result, holds or does not hold, and the evidence for it. A… | **C1** (C1-L12) |
| FR-47 | 1 | rule | No review record or merge sheet carries a "grounding seat not run" line. | **C1** (C1-L2) |
| FR-48 | 1a | rule | Review always runs as the one loop. | **C1** (C1-L3) |
| FR-48 | 1b | rule | A vet's narrow doubt goes to one independent reviewer given the doubt. | **C1** (C1-L12) |
| FR-49 | 1 | rule | A request to review someone else's PR is told plainly it is not supported. | **C1** (C1-L3) |
| FR-50 | 1 | rule | Every break-it test runs in the build session's own working copy. | **C1** (C1-L6) |
| FR-51 | 1 | rule | A record reads like the sample on board panel 7. | **C1** (C1-L1) |
| FR-51 | 2 | rule | Each part of the record shows once the requirement that produces it has shipped: the "Outside this PR"… | **C1** (C1-L1) |
| FR-52 | 1 | rule | A light-lane review record never shows a fifth round in one session, except the one extra audit round of… | **C1** (C1-L11) |
| FR-53 | 1 | rule | Each pass shows, per choice: how often it was made, whether an extra audit round settled what was open,… | **#2189** (out-of-epic owner) |
| FR-53 | 2 | rule | #2189 builds this count. This work depends on it and builds nothing for it. | **#2189** (out-of-epic owner) |
| FR-54 | 1 | rule | Each gardening pass records whether each condition was met and, when one was, that it went to the owner. | **C1** (C1-L13) |
| FR-54 | 2 | rule | A false PR claim found after merge is logged by the act that finds it, the way a review escape is logged,… | **C1** (C1-L13) |
| FR-54 | 3 | rule | For the seating condition, each pass records beside its judgment the numbers it read: the security and… | **C1** (C1-L13) |
| UFR-1 | 1 | GWT | Given a carried finding with no outcome and a later fix for it, when the next review runs, then the record… | **C1** (C1-L11) |
| UFR-2 | 1 | GWT | Given an upper layer whose lower layer moved before or during its review session, when it hands back,… | **C1** (C1-L11e; amendment #2) |
| UFR-2 | 2 | GWT | Given a catch-up that changed none of the upper layer's own lines, when it is reviewed, then the review… | **C1** (C1-L11e; amendment #2) |
| UFR-3 | 1 | GWT | Given one flaky failure, when the re-run passes, then the round goes on and the record shows both runs.… | **C1** (C1-L9) |
| UFR-4 | 1 | GWT | Given a break-it test that fails to compile, when the build session fixes the compile error, then the… | **C1** (C1-L6) |
| UFR-5 | 1 | GWT | Given a weakened test, when the auditor flags it, then the weakened version is never kept, and a… | **C1** (C1-L10) |
| UFR-6 | 1 | GWT | Given a dropped run, when the review resumes or restarts, then every earlier finding is in the record with… | **C1** (C1-L1) |
| UFR-7 | 1 | GWT | Given a project with no verify command, when setup runs, then the owner reads that code review is not… | **C1** (C1-L3) |
| UFR-8 | 1 | GWT | Given an in-flight review at adoption, when it ends, then its record is complete under the rules it… | **C1** (C1-L4) |
| UFR-8 | 2 | GWT | Given an in-flight review at adoption whose saved state the new rules cannot finish, it is handed back to start a fresh review… | **C1** (C1-L10a) |
| NFR | No silent loss | NFR | nothing a reviewer finds is dropped from the review record. Every finding ends with a recorded outcome or… | **C1** (C1-L1) |
| NFR | Independence | NFR | every reviewer, verifier, auditor and search description comes from a different model family than every… | **C1** (C1-L5) |
| NFR | No target number | NFR | the measure is read as a trend at each gardening pass; this work sets no target for rounds, tokens or… | **C1** (C1-L13) |
| DoD | 1 | success | Every requirement above is built and released, except FR-53, which #2189 delivers. The core loop ships… | **epic closure** |
| DoD | 2 | success | Whether this work lost real catches is read, after it ships, from the gardening-pass measure (#2189) and… | **epic closure** |

## Shipped rules the spec retires, and where each goes

The spec's section "What this spec changes elsewhere" lists shipped rules that change. Each is child
scope, removed by the layer named here; the advisor's marking of the two other specs is register R16,
no child's.

| Shipped rule | Where it lives today | Removed or replaced by |
| --- | --- | --- |
| The round driver's cap of 7 and ceiling of 10 | `lib/round_driver.py`, `lib/circuit_breaker.py`, `skills/review-code/reference/round-driver.md` (`maxRoundsAbsolute`), `skills/review-code/SKILL.md` (`--max-rounds 7`), `rubric/review-discipline.md` | C1-L4 |
| The stall menu | `lib/round_phases.py` (`present-stall-menu`), `lib/round_driver.py`, `skills/review-code/SKILL.md` | C1-L4 |
| The separate fixer and its fix orders | `rubric/orders/dispatch-fixer.md`, `lib/round_orders.py`, `lib/round_driver.py` (`dispatch-fixer`), `lib/engine_adapter.py`'s fix path, `skills/review-code/reference/auto-fix-loop.md` § Fixer Subagent Prompt | C1-L9 |
| The grounding seat | `agents/grounding-seat.md`, `lib/grounding_stage.py`, `skills/review-code/reference/grounding-seat.md`, `lib/seat_map.py`, the record's `seatsNotRun` line, `skills/showrunner/reference/vet-receipt.md`, `skills/workhorse/reference/handback.md` | C1-L2 |
| Read-only review mode | `skills/review-code/SKILL.md` § Read-Only Path, `skills/review-code/reference/headless-presentation.md`, the verify story's `mode: review-only`, `skills/showrunner/reference/vetting.md` | C1-L3 (the vet's narrow doubt: C1-L12) |
| The test role's rule that the loop runs its break-it tests in a throwaway copy | `agents/test-role.md`, `lib/break_it.py` | C1-L6 |

Two shipped rules outside that list also change, because the spec's requirements reach them:

| Shipped rule | Where it lives today | Changed by |
| --- | --- | --- |
| A stack layer is not brought current while its review loop is open | `rubric/native-stacks.md` § How a stack stays current | C1-L11e (UFR-2, amendment #2: the rule holds during the session, and the layer catches up once at handback; C1-L11a's stop-and-restart wording is replaced) |
| After handback, new surface or behaviour gets the full review loop again | `skills/workhorse/SKILL.md` § 12, its delta table | C1-L11 (FR-44, FR-45) |

## Spec sections that are not criteria but have a builder home

These carry no acceptance criterion under the rule above and are not in the counts; each is named so
nothing in the spec falls between children.

| Section | What it asks | Home |
| --- | --- | --- |
| UI / UX | the approved build board (`board/build-board.html`, version 7) is the design | each body names its panels: C1-L1 panel 7; C1-L4 panels 4 and 8; C1-L6 and C1-L7 panel 1; C1-L9 panels 2 and 6; C1-L10 panel 3; C1-L11 panels 5 and 6; C1-L12 panels 4 and 5; C1-L2, C1-L3 panel 8; C2 panel 1; C3 and C4 panel 7 |
| Assumptions & dependencies | #2189 and #2190 exist and carry the proof; today's splitting, cap and grounding facts; #2189 adds the seating check's numbers | R9, R10, R11; R1 (today's splitting until C2); R8 and R13 |
| What this spec changes elsewhere | the advisor marks the two other specs and the shipped rules | R16 (the specs); the shipped-rules tables above |
| Constraints | no trial mode; keep the three lanes, add none | R1; R14 |
| Out of scope | merging without a sheet; seating by risk area; a replay before release; building #2189 and #2190; review with no verify command or of someone else's PR; #2186's fix | none builds them; #2186 is made unnecessary by C1-L9, and the advisor proposes its close at C1's merge |
| Coverage | the spec's own coverage table | its show-it rows drive the presentation calls: C1 (with C1-L1, C1-L4, C1-L6, C1-L7, C1-L10 and C1-L12) show it |

## Mechanical check

A script (kept out of the repo, in the drafting session's scratchpad) parsed every acceptance bullet
of `spec.md` (`grep -c '^  - \*Acceptance' spec.md` gives 74), keyed by its FR or UFR and its
position, plus the three non-functional lines and the two Definition of done bullets, and every row of
the table above. Its result: each of the 74 bullets appears exactly once, the one split bullet appears
as exactly its two declared rows, no row names a bullet the spec lacks, each NFR line and each DoD
bullet appears once, and every row names exactly one owner. Owners: C1 62 rows (L1 4, L2 1, L3 3,
L4 8, L5 6, L6 6, L7 5, L8 5, L9 3, L10 5, L11 6, L12 6, L13 4), C2 6, C3 3, C4 5, #2189 2, epic
closure 2; 80 rows in all.

**Re-checked after amendment 1 (2026-10-28).** The spec's FR-6 gained two acceptances (proven copies are not counted or read and are listed in the record; an uncovered or unmatched file counts and is read). Both are C1-L5's. The same script re-ran on the amended spec: 74 bullets, 80 rows, each owned exactly once, errors none.
