# Coverage map — risk-calibrated-review-that-learns-dec0af

Acceptance-level allocation of every criterion of the spec the owner approved on 2026-10-10,
`risk-calibrated-review-that-learns-dec0af` (`spec.md`, beside this file), each owned by exactly one
child, or, for the spec's Definition of done, by the epic's closure validation run.

**What counts as one criterion.** Each acceptance bullet of an FR or UFR is one criterion, at the
spec's own bullet granularity: 141 bullets across FR-1 to FR-81 and UFR-1 to UFR-10. Every FR and
UFR in this spec carries at least one acceptance bullet, so no statement is counted on its own;
where an FR carries bullets, its statement is owned by the child that owns its bullets, and the
FRs whose bullets are split name the statement's owner below. Each of the four non-functional lines
(Reach, Privacy, Reliability, Time) is one criterion. Each of the three Definition of done bullets is
one criterion, owned by the closure validation run. That makes 148 criteria. The table has 150
rows, because two bullets are split at their own wording into two rows each (declared below).

**Declared splits.** Six FRs or UFRs span two children. Each split follows the spec's own bullets,
or, where one bullet spans two surfaces, the bullet's own conjunction or list, the way the
decomposition doctrine's worked example splits one:

- **FR-43** (a batch-1 question both in the chat and on the index) is split at its bullets. The
  statement (the question goes in the chat and at the top of the index, the chat linking to the
  index) and bullet 1 (the first answer given, in either place, is the answer) are **C8**'s: they are
  the advisor's acts of asking and reading. Bullet 2 (where pictures bear on the question, the index
  shows them with it) is **C9**'s, because the index draws it. Register entries R7 and R10 bind both.
- **FR-58** (the advisor walks a sheet's stops before sending it) is split at its bullets. The
  statement and bullet 2 (a stop a pilot run already walked, with its evidence, counts as walked and
  is not repeated by hand) are **C8**'s, because walking is the advisor's act. Bullet 1 (the walk part
  says the advisor walked it first and where its pictures come from) is **C9**'s, because the sheet
  shows it. Register entry R10 binds both: the advisor's input carries which stops were walked and
  how, and the sheet shows what the input says.
- **FR-55** (a PR sheet follows the approved review surface spec) is split at its bullets, by the
  advisor's ruling of 2026-10-10. Its two Given-When-Then bullets describe the advisor's behaviour
  when it reads a PR sheet, so they are **C8**'s: bullet 2 (with saved answers and no "done" yet,
  nothing is merged, sent back, filed or recorded in Canon) and bullet 3 (a "Keep it" whose note says
  to fix it first is treated as open, the PR is not merged, and the advisor asks which one stands).
  The statement and the six rule bullets (1 and 4 to 8: drafts and the last tap as the template
  already carries them, the failed-save, missing-picture and shared-sheet behaviour, the four answer
  patterns, and the four differences) are **C9**'s (layer 1), because the sheet and its usage doc
  carry them. Register entries R7 and R8 bind both.
- **FR-68** (the owner's answers and verdict written back to the PR) is split at its bullets. The
  statement and bullet 1 (after the merge, the PR shows each answer and the verdict) are **C8**'s,
  because the advisor writes the receipt back at merge. Bullet 2 (the walk's results are saved with
  the sheet) is **C9**'s, because the sheet's own answer store saves them (R10).
- **FR-5**, bullet 4 (the certificate gate retires in each of its three homes) is split at its list.
  The first two homes, the part that writes the certification receipt and the handback check that
  refuses a PR without one, are **C2**'s (layer 1), which retires the code. The third home, the
  certified-loop check in the advisor's vet, is **C3**'s, because C3 alone edits the vet receipt
  (R13) and replaces that check with the review record's checks in one edit, so two children never
  rewrite the same row. Every other FR-5 bullet, and the statement, is C2's.
- **UFR-3**, bullet 1 (a full-lane review whose specialist did not run) is split at its conjunction.
  "Then the record shows the gap" is **C1**'s, because the record writer records it. "And the vet
  does not return the PR as ready" is **C3**'s, because it is a vet check. The statement and bullets
  2 and 3 are C1's. Register entry R1 binds both.

No other criterion is split.

**Criteria owned whole where another child also touches the behaviour.** These are not splits; each
names the one owner and the register entry that binds the other child:

- **FR-44** (an answered batch-1 question leaves the index) is **C9**'s whole, statement included:
  its only bullet is what the index shows once the question is answered. The advisor's reading of the
  answer is FR-43's first bullet (C8).
- **UFR-9** (the advisor could not walk a stop) is **C9**'s whole: its statement and bullet are what
  the stop says on the sheet. The fact that a stop was not walked, and why, reaches the sheet in the
  advisor's input (R10), which C8's doctrine fills.
- **FR-2** (no record, sheet or PR text says a change has no bugs) is **C1**'s. The sheet's half is
  held by R10: the sheet builder states only what the record holds.
- **The Part C sheet headings** (FR-31's first bullet, FR-32's three bullets, FR-33 and UFR-2) are
  **C7**'s: the loop decides which part of the sheet each finding lands in and writes that outcome
  into the review record (R4). C9 draws the record's parts without re-deriving them (R10).
- **FR-79**'s first bullet (a project keeps working before the sitting, on UFR-1's default) is
  **C2**'s, because it is a promise the release notes make. The behaviour it promises is UFR-1's,
  which C5 owns and tests.
- **FR-10**'s first bullet (the loop decides "touches a risk area" from the area itself, with no model
  judgment for a plain case) is **C4**'s, because C4 builds the one reader that answers it (R3). C5
  and C6 call that reader.

**Definition of done.** The spec's Definition of done is the success definition: an owner shipping a
risk-area change without reading code, no review held up for a certificate, and an escape reaching
the owner as a proposal at a gardening pass. No child can run it, because it needs every child
landed together in one release (R2) and a real PR, a real escape and a real gardening pass. It is the
epic's **closure validation run**, recorded under `skills/showrunner/reference/closure.md` § The
validation run, after the last child merges. Its three rows are the last rows of the table.

**What this spec changes elsewhere.** This section of the spec carries no acceptance criterion and is
not counted. Its first five items amend other owner-approved specs (the certification contract spec,
the forward doctrine spec, the review surface spec, the verification strategy spec and the
converge-faster spec): recording those amendments is the advisor's amendment work, scheduled by the
advisor, and is no child's scope. Its last item, "Shipped rules", changes shipped plugin text, and each
part lands with the child whose surface it is (R13):

| Shipped rule | Child |
| --- | --- |
| The three batches and batch 3's click list in the owner-decisions reference | C8 |
| The advisor's duty on the owner's merge word (showrunner duty 6) | C8 |
| The rows for merge words and the threat model in Canon's contract home table | C8 |
| The glossary's Misses log entry | C10 |
| The driver mandate in the review discipline | C2 (layer 4) |
| The lane rule and the single-reviewer fallbacks in the review discipline | C5 |
| The keep-or-retire entries for the seat canary, the round driver core, the certification receipt writer and its four checks | C2 (layer 5) |

Children: C1 the review record (the seam) · C2 retire the certificate parts · C3 the advisor's vet
reads the review record · C4 Risk and trust · C5 lanes and the panel · C6 the test role · C7 findings
and the fix loop · C8 the owner's decisions (advisor doctrine) · C9 the PR sheet and the index ·
C10 learning from escapes.

**Sequencing.** Wave 0: C1, the seam. Wave 1: C2 and C3 in parallel, after C1. Wave 2: C4 first,
then C5 and C6 in parallel once C4 has merged (both call C4's risk-area reader). Wave 3: C7, C8 and
C9, after waves 0 to 2 (C8 and C9 in parallel; C8's doctrine points at the input shape C9 decides).
Wave 4: C10, after C8 (its proposals arrive in C8's batch 2). This is the owner's build order: Part A,
then Part B, then the owner's leftover review (Parts C and D), then Part E, with each Part F
requirement built with the part it describes.

**Per child.** C1 10 rows · C2 13 (layer 1: 3, layer 2: 3, layer 3: 2, layer 4: 1, layer 5: 4) ·
C3 3 · C4 6 · C5 16 · C6 14 · C7 21 · C8 14 · C9 36 bullets plus 3 NFR lines (layer 1: 19 and
Privacy and Reliability; layer 2: 11; layer 3: 6 and Reach; FR-63 and FR-65 are graded in layer 3 because
their acceptances read the index) · C10 10 plus the Time line · closure
validation run 3. Total 150 rows: 143 bullet rows (141 bullets, two of them split in two), 4 NFR
rows, 3 Definition of done rows.

| Ref | Bullet | Kind | Criterion (opening words) | Owner |
| --- | --- | --- | --- | --- |
| FR-1 | 1 | rule | A change that has a finding with a real consequence that is not fixed, not shown wrong and not covered by an… | **C1** |
| FR-1 | 2 | rule | "The checks ran on the final code" is true only when CI is green on the PR's final commit. | **C1** |
| FR-2 | 1 | rule | No review record, PR sheet or PR text produced by the review says that a change has no bugs. | **C1** |
| FR-3 | 1 | rule | The record states the lane and why the change got it, which reviewers ran, each finding and what happened to… | **C1** |
| FR-3 | 2 | rule | A review on any of the three lanes writes a record. | **C1** |
| FR-4 | 1 | GWT | Given a review in which a planned reviewer did not run, when the record is written, then the record does not… | **C1** |
| FR-4 | 2 | rule | Where the session that ran the review reports a reviewer's run, and no engine's own record does, the record… | **C1** |
| FR-5 | 1 | rule | From that release on, no review is refused, parked or marked incomplete for lacking a certificate. | **C2** (C2-L1) |
| FR-5 | 2 | rule | From that release on, no lane's review runs a planted-bug probe. | **C2** (C2-L2) |
| FR-5 | 3 | rule | No release retires any of the five without writing the review record, and none writes the record while… | **C2** (C2-L5) |
| FR-5 | 4a | rule | the part that writes the certification receipt, and the handback check that refuses a PR without a receipt | **C2** (C2-L1) |
| FR-5 | 4b | rule | and the certified-loop check in the advisor's vet | **C3** |
| FR-5 | 5 | rule | Starting a review from an old saved session's records is the part that retires. Picking the same session back… | **C2** (C2-L3) |
| FR-5 | 6 | rule | The exact-head evidence chain is the set of checks that tie each piece of review evidence to one exact… | **C2** (C2-L1) |
| FR-5 | 7 | rule | Each of the four kinds of escape the certificate guarded against keeps a guard in this spec: a review that… | **C2** (C2-L5) |
| FR-6 | 1 | rule | Both checks still run after the release in FR-5. | **C2** (C2-L2) |
| FR-6 | 2 | rule | The admission check holds a new model back until the model passes it, and it keeps its own planted example.… | **C2** (C2-L2) |
| FR-7 | 1 | GWT | Given a full-lane PR with no review record, when it is handed back, then it is parked. | **C2** (C2-L4) |
| FR-8 | 1 | GWT | Given a PR whose record is missing, or whose checks ran on an earlier commit, or that has a leftover the… | **C3** |
| FR-9 | 1 | rule | Viewing the item shows the threat model under "What we defend against" and the risk areas under "Risk areas". | **C4** |
| FR-10 | 1 | rule | The review loop decides whether a change touches a risk area from the risk area itself, with no model… | **C4** |
| FR-10 | 2 | rule | A risk area may cover a part of the project where a mistake costs money, customer data, safety, access, or… | **C4** |
| FR-11 | 1 | rule | The sitting asks, in this order: who the product is for and what it is for, where money, customer data… | **C4** |
| FR-12 | 1 | GWT | Given a project whose who-it's-for answer is set, when the sitting starts, then the advisor offers to read it… | **C4** |
| FR-13 | 1 | rule | Every change is reviewed on exactly one of the three lanes. | **C5** |
| FR-14 | 1 | GWT | Given a risk area that covers payments, when a two-line change to payment code is routed, then it gets the… | **C5** |
| FR-15 | 1 | GWT | Given a change that touches a risk area, when a model judges the change trivial, then the change still gets… | **C5** |
| FR-16 | 1 | GWT | Given a full-lane change that touches payments, when it is reviewed, then the review record lists a… | **C5** |
| FR-17 | 1 | rule | A light-lane review record lists exactly one reviewer. | **C5** |
| FR-18 | 1 | GWT | Given a reviewer whose engine record does not show that it read the change, when the review ends, then the… | **C5** |
| FR-18 | 2 | rule | A record that is missing, or that cannot tell whether the reviewer read the change, counts as not showing it. | **C5** |
| FR-18 | 3 | rule | This takes the place of the planted-bug probe those two lanes carry today. | **C5** |
| FR-19 | 1 | GWT | Given a change built by one model family, when its reviewers are picked, then none of them is from that… | **C5** |
| FR-19 | 2 | rule | A reviewer that writes break-it tests for a change is not a maker of that change. | **C5** |
| FR-20 | 1 | rule | No such reviewer runs without the threat model in what it is given. | **C5** |
| FR-21 | 1 | rule | No review runs both a test reviewer and the test role. | **C6** |
| FR-22 | 1 | rule | The test role asks, of each changed test, whether the test would fail if the code under test were wrong. | **C6** |
| FR-22 | 2 | rule | When an intentional edit leaves a test file holding tests that cannot fail, the test role raises a finding… | **C6** |
| FR-22 | 3 | rule | FR-29 names the two duties this spec drops. | **C6** |
| FR-23 | 1 | GWT | Given a full-lane change that touches a risk area, when the test role reviews it, then the role runs at least… | **C6** |
| FR-24 | 1 | GWT | Given a break-it test that catches a double charge, when the fix lands, then the test stays in the change and… | **C6** |
| FR-24 | 2 | rule | The generalist code reviewer reads the break-it tests for bloat and for tests that pass without checking… | **C6** |
| FR-25 | 1 | rule | Such a test is reported as a finding with its consequence. | **C6** |
| FR-26 | 1 | rule | Such a test is reported as a finding with its consequence. | **C6** |
| FR-27 | 1 | rule | Such a change is reported as a finding with its consequence. | **C6** |
| FR-28 | 1 | rule | A test that is brittle, that duplicates another test, or that only pins wording is reported as a finding. | **C6** |
| FR-28 | 2 | rule | No finding rests only on how much of a change is test code. | **C6** |
| FR-29 | 1 | rule | No finding from the test role asks for coverage in code outside every risk area, or for a change of test… | **C6** |
| FR-30 | 1 | rule | A finding with no stated consequence is not accepted into the review. | **C7** |
| FR-31 | 1 | GWT | Given a finding about naming with no effect on what the product does, when the review ends, then the finding… | **C7** |
| FR-31 | 2 | rule | A finding with no consequence beyond code quality is craft inside a risk area too. | **C7** |
| FR-32 | 1 | GWT | Given a project with no standing ruling that covers a leftover, when the PR's sheet is built, then the… | **C7** |
| FR-32 | 2 | GWT | Given a standing ruling that clearly decides a leftover, when the PR's sheet is built, then the leftover… | **C7** |
| FR-32 | 3 | rule | A leftover that one of the project's recorded residuals already covers also appears under "Already decided".… | **C7** |
| FR-33 | 1 | GWT | Given a low-severity finding with a real consequence, left unfixed, when the sheet is built, then the finding… | **C7** |
| FR-34 | 1 | rule | The loop ends when every finding is fixed, shown wrong, decided as craft, left for the owner, or decided by a… | **C7** |
| FR-35 | 1 | GWT | Given a round that fixed two findings, when the next round runs, then its reviewers are asked about those two… | **C7** |
| FR-35 | 2 | rule | When a round looks wider than the fixes, the review record says why. | **C7** |
| FR-36 | 1 | rule | The number of findings with a recorded outcome equals the number of findings the reviewers raised. | **C7** |
| FR-37 | 1 | GWT | Given an owner ruling on a finding, when the finding is reworded in a later round, then the ruling still… | **C7** |
| FR-37 | 2 | rule | No round runs on guidance that a later ruling replaced. | **C7** |
| FR-38 | 1 | rule | An out-of-scope finding is not sent to a fixer in more than one round. | **C7** |
| FR-38 | 2 | rule | An out-of-scope finding with a real consequence still reaches the owner as a leftover under FR-32, whatever… | **C7** |
| FR-39 | 1 | GWT | Given a fix that would change behaviour its finding does not name, when no owner ruling allows that change… | **C7** |
| FR-40 | 1 | rule | A decision about one PR is on record in that PR's saved sheet answers. | **C7** |
| FR-40 | 2 | rule | A decision that sets a rule for later work is on record in Canon. | **C7** |
| FR-41 | 1 | GWT | Given a bug found after merge, when the advisor looks up the PR's review, then every craft decision and every… | **C7** |
| FR-42 | 1 | rule | Batch 1 holds what blocks work. Batch 2 holds decisions not tied to one PR. Batch 3 holds one sheet per PR. | **C8** |
| FR-43 | 1 | rule | The first answer given, in either place, is the answer. | **C8** |
| FR-43 | 2 | rule | Where pictures bear on a batch-1 question, the index shows them with the question. | **C9** (C9-L3) |
| FR-44 | 1 | GWT | Given the only batch-1 question is answered, when the index is next shown, then its "Blocks work" part reads… | **C9** (C9-L3) |
| FR-45 | 1 | rule | No batch-2 item concerns one specific PR. | **C8** |
| FR-46 | 1 | GWT | Given a batch-1 ruling that sends a PR back, when batch 3 is built, then that PR has no sheet waiting for… | **C8** |
| FR-47 | 1 | rule | Each row names the PR, shows how many items are accepted and how many walk stops are walked, and opens that… | **C9** (C9-L3) |
| FR-47 | 2 | rule | A row under "Needs you" says where the PR falls in the merge order, for example "merges first". The advisor… | **C9** (C9-L3) |
| FR-48 | 1 | rule | A part with nothing in it is left out, except "What you're accepting", which then reads "Nothing. The review… | **C9** (C9-L1) |
| FR-49 | 1 | rule | The stack's sheet has one walk, one list of what the owner is accepting, one merge verdict for the whole… | **C9** (C9-L1) |
| FR-49 | 2 | rule | Each walk stop on a stack's sheet names the PR it comes from. | **C9** (C9-L1) |
| FR-50 | 1 | rule | Every fact in the part matches the PR's review record. | **C9** (C9-L1) |
| FR-51 | 1 | rule | Each item shows, in this order: its kind, its title, what happens if it is left, its options with what each… | **C9** (C9-L1) |
| FR-51 | 2 | rule | When the PR's merge closes the last open piece of a spec, that spec's closure receipt is one of the items… | **C9** (C9-L1) |
| FR-52 | 1 | rule | A leftover's options are "Keep it", "Fix in a follow-up" and "Fix before merge" unless the item calls for… | **C9** (C9-L1) |
| FR-53 | 1 | rule | Such an item shows no options list. | **C9** (C9-L1) |
| FR-54 | 1 | rule | A question can be answered with the note left empty. | **C9** (C9-L1) |
| FR-55 | 1 | rule | Taps save as drafts, the last tap is the answer, and the plugin reads a sheet's answers together only after… | **C9** (C9-L1) |
| FR-55 | 2 | GWT | Given a PR sheet with saved answers and no "done" yet, when the advisor looks at it, then nothing is merged… | **C8** |
| FR-55 | 3 | GWT | Given "Keep it" on a leftover with a note that says to fix it first, when the advisor reads the sheet after… | **C8** |
| FR-55 | 4 | rule | A save that fails, a picture that cannot load and a sheet the owner shared behave as that spec's UFR-2, UFR-3… | **C9** (C9-L1) |
| FR-55 | 5 | rule | Every question on a PR sheet and the index uses one of the four accepted answer patterns: pick, for a batch-1… | **C9** (C9-L1) |
| FR-55 | 6 | rule | No PR sheet and no index offers an answer button outside those four patterns. | **C9** (C9-L1) |
| FR-55 | 7 | rule | The four patterns are a standing rule for every sheet, and a sheet's author picks the pattern that fits each… | **C9** (C9-L1) |
| FR-55 | 8 | rule | Four things differ on a PR sheet and the index from that spec as it stands today: the answer buttons (FR-52… | **C9** (C9-L1) |
| FR-56 | 1 | rule | The part shows a way to open the product, how many stops are walked, and the stops in named groups. | **C9** (C9-L2) |
| FR-56 | 2 | rule | Each stop shows its numbered steps, an "Expect" line, its pictures where it has any, the answers "Works"… | **C9** (C9-L2) |
| FR-57 | 1 | rule | A look-only stop has no steps, a "Look for" line, its pictures, and the answers "Looks right", "Problem" and… | **C9** (C9-L2) |
| FR-58 | 1 | rule | The walk part says that the advisor walked it first and where its pictures come from. | **C9** (C9-L2) |
| FR-58 | 2 | rule | A stop that a pilot run already walked, with its evidence, counts as walked, and the advisor does not repeat… | **C8** |
| FR-59 | 1 | rule | The stop then offers "Fix before merge", "Fix in a follow-up", "Add a screenshot", and a note box labelled… | **C9** (C9-L2) |
| FR-60 | 1 | GWT | Given a picture a builder made on an account the owner cannot open, when the sheet is published, then the… | **C9** (C9-L2) |
| FR-61 | 1 | rule | Everything else about an opened picture is as the review surface spec says: it opens large with a Close… | **C9** (C9-L2) |
| FR-62 | 1 | rule | While locked, the merge button reads "Merge #<number> · locked" and cannot be tapped, and the sheet says what… | **C9** (C9-L1) |
| FR-62 | 2 | rule | An answer that sends the PR back does not count as accepted. | **C9** (C9-L1) |
| FR-63 | 1 | GWT | Given that choice, when the index is next shown, then the PR is under "Being fixed", and it returns with a… | **C9** (C9-L3) |
| FR-64 | 1 | rule | The verdict says how many stops are not walked, and optional stops are not counted. | **C9** (C9-L2) |
| FR-65 | 1 | GWT | Given a saved merge verdict, when the owner changes an item from accepted to "Discuss", then the sheet shows… | **C9** (C9-L3) |
| FR-66 | 1 | rule | Neither a saved "Merge" verdict alone nor "done" alone is taken as that word. | **C8** |
| FR-66 | 2 | rule | A saved "Not yet", or no saved verdict, together with "done" is not that word. | **C8** |
| FR-67 | 1 | GWT | Given that answer and a merged PR, when the advisor finishes the merge, then a follow-up exists that carries… | **C8** |
| FR-67 | 2 | rule | A follow-up filed for a leftover carries a date to revisit it. | **C8** |
| FR-68 | 1 | rule | After the merge, the PR shows each answer and the verdict. | **C8** |
| FR-68 | 2 | rule | The walk's results are saved with the sheet. | **C9** (C9-L2) |
| FR-69 | 1 | rule | Each folded part shows how many entries it holds and opens on a tap. | **C9** (C9-L1) |
| FR-70 | 1 | rule | A permanent acceptance, an approved calibration change and a ceded call are each recorded in Canon. | **C8** |
| FR-71 | 1 | rule | The entry links to the PR's review record and says whether the review missed the bug, or saw it and left it. | **C10** |
| FR-72 | 1 | rule | A seat's entry is judged on what the seat caught. | **C10** |
| FR-72 | 2 | rule | From the day it is created, a seat's entry carries what every entry on that list carries, its retirement… | **C10** |
| FR-72 | 3 | rule | The part of the plugin that writes the review record has an entry of its own on that list. | **C10** |
| FR-73 | 1 | rule | A proposal names the evidence it rests on, its options, what each costs, and a recommendation. | **C10** |
| FR-74 | 1 | rule | A proposal to loosen the calibration looks the same as one to tighten it. | **C10** |
| FR-75 | 1 | GWT | Given a proposal the owner has not answered, when the next review runs, then it runs on the calibration as it… | **C10** |
| FR-76 | 1 | rule | The approval is recorded in Canon as FR-70 says. | **C10** |
| FR-77 | 1 | GWT | Given such a complaint, when the advisor replies, then the reply says what the review spent its time on and… | **C10** |
| FR-78 | 1 | rule | The project's risk areas start empty. | **C4** |
| FR-79 | 1 | rule | The project keeps working before the sitting, on the default in UFR-1. | **C2** (C2-L5) |
| FR-79 | 2 | rule | The same release notes tell a project whose own checks look for the certificate's words what replaces them. | **C2** (C2-L5) |
| FR-80 | 1 | rule | The model chosen for the test reviewer becomes the model for the test role. | **C6** |
| FR-81 | 1 | rule | No reviewer seat is judged on reviews from before that day. | **C10** |
| UFR-1 | 1 | GWT | Given a project with no risk areas, when a change that might touch money is routed, then it gets the full… | **C5** |
| UFR-1 | 2 | GWT | Given a Risk and trust item the review loop cannot read, when a change is routed, then the plugin treats the… | **C5** |
| UFR-2 | 1 | GWT | Given a capped loop with one open finding that has a real consequence, when the sheet is built, then that… | **C7** |
| UFR-3 | 1a | GWT | Given a full-lane review whose specialist did not run… then the record shows the gap | **C1** |
| UFR-3 | 1b | GWT | …and the vet does not return the PR as ready | **C3** |
| UFR-3 | 2 | GWT | Given that PR, when the missing review has not run, then the PR stays parked until the review runs, unless a… | **C1** |
| UFR-3 | 3 | GWT | Given the owner's ruling or word to go ahead, when the PR's sheet is built, then "How the review went" names… | **C1** |
| UFR-4 | 1 | GWT | Given a light-lane change with no such reviewer available, when the review is due, then no session picks a… | **C5** |
| UFR-4 | 2 | GWT | Given the owner's word, for that change, to use a reviewer from a maker's family, when the review runs, then… | **C5** |
| UFR-4 | 3 | rule | The stand-in that today needs no owner decision ends with this work. | **C5** |
| UFR-5 | 1 | GWT | Given a session damaged after its second round, when the review resumes, then every finding and outcome from… | **C7** |
| UFR-6 | 1 | GWT | Given answers saved on the old sheet, when the new sheet opens, then it shows "This PR changed", keeps the… | **C9** (C9-L1) |
| UFR-7 | 1 | GWT | Given "Keep them visible" on the index and "hide them" in the chat, when the advisor reads both, then the… | **C8** |
| UFR-8 | 1 | GWT | Given a stop whose picture could not be copied, when the sheet opens, then the stop says a picture is… | **C9** (C9-L2) |
| UFR-9 | 1 | GWT | Given a stop that needs the owner's own sign-in, when the sheet opens, then that stop says the advisor did… | **C9** (C9-L2) |
| UFR-10 | 1 | GWT | Given such a review, when it restarts, then it restarts once, and the old certification files stay on disk… | **C2** (C2-L3) |
| NFR | Reach | NFR | Every sheet and the index can be read and answered at phone width with no sideways scrolling. | **C9** (C9-L3) |
| NFR | Privacy | NFR | A sheet and the index are private to the owner until the owner shares them, and only the owner's answers count… | **C9** (C9-L1) |
| NFR | Reliability | NFR | Each question holds one answer, and a sheet that cannot save says so on the page… | **C9** (C9-L1) |
| NFR | Time | NFR | The loop spends the time the project's calibration calls for, and a complaint about time is answered as FR-77 says. | **C10** |
| DoD | 1 | success | An owner ships a change in a risk area without reading code. The full lane's panel reviewed the change, a review record exists… | **closure validation run** |
| DoD | 2 | success | No review is held up for lacking a certificate. | **closure validation run** |
| DoD | 3 | success | A bug traced to a reviewed PR is logged as a review escape, and a proposal that rests on it reaches the owner at a gardening pass. | **closure validation run** |

**Spec sections that are not criteria but have a builder home.** These carry no acceptance
criterion under the rule above and are not in the counts; each is named so nothing in the spec falls
between children.

| Section | What it asks | Home |
| --- | --- | --- |
| Glossary | review record, risk area, maker, test role, break-it test, leftover, answer pattern, walk, review escape, calibration | the child that first ships each term (R12) |
| UI / UX | the approved build board (`board/build-board.html`) is the design, and its wording is the product's wording | each child's What names its artboards: C4 and C5 "4 Risk and trust"; C8 "1 The index"; C9 "1 The index", "2 Small sheet and stack sheet" and "3 Big PR sheet"; C7 "3 Big PR sheet" (its sheet parts); C10 "5 A learning proposal" |
| Constraints | no automated gate at handback; no watch-only mode; no date for the release; no way back kept; nothing project-specific; every leftover with a real consequence goes to the owner by default; round caps, the stuck-loop stop, the engines' own records and the scoped fixer kept | C2 and C3 (no handback gate: the vet carries the check); R2 (one release, no date); C2 (no way back kept); R11 (nothing project-specific); C7 (default, caps, stop, scoped fixer) |
| Assumptions & dependencies | one release; build order; engines' own records; Part E adds to existing machinery; caps and windows start at today's values | R2; the sequencing above; R1 and R6; C10; C7 and C10 |
| Out of scope | a long-running decisions inbox; deliberate faking of a record; an error tracker as a source; spec review | none |
| What this spec changes elsewhere | amendments to five approved specs; shipped rules | the advisor's amendment work; the shipped-rules table above |

**Mechanical check.** `spec.md` has 141 acceptance bullets (`grep -c '^  - \*Acceptance' spec.md`),
4 non-functional lines and 3 Definition of done bullets. A script parsed every bullet of the spec,
keyed by its FR or UFR and its position, and every bullet row of the table above: each of the 141
bullets appears exactly once, the two split bullets each appear as exactly their two declared parts,
no row names a bullet the spec lacks, each NFR line and each Definition of done bullet appears once,
and every row names exactly one owner.
