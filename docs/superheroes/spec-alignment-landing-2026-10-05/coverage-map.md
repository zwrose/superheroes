# Coverage map — spec-alignment-landing-2026-10-05

Acceptance-level allocation of every criterion of the two specs the owner approved on 2026-10-04,
`aligning-on-what-to-build-6da1ee` (Spec A) and `the-review-surface-d59417` (Spec B), each owned by
exactly one child.

**What counts as one criterion.** Each acceptance bullet of an FR or UFR is one criterion, at the
spec's own bullet granularity. An FR or UFR with no acceptance bullet is one criterion (its
statement). Each non-functional requirement is one criterion. Each item of Spec A's "What this spec
amends" is one criterion. Where an FR carries acceptance bullets, its statement is owned by the child
that owns its bullets; the one FR whose bullets are split names the statement's owner below. One
further rule, following the precedent package's treatment of numbered lists: Spec A FR-41's three
named checks are list items of its statement that each define a separate check, so each counts as a
criterion beside the FR's own acceptance bullet; FR-3's ten categories are one list graded by its
single acceptance bullet and are not counted separately.

**Declared split.** Spec A FR-15 is split at its bullets: the statement and bullets 1, 3 and 4 are
C1's (Canon's write procedure, when a ruling binds, the out-of-repo store); bullet 2 (Canon never
gets a PR of its own; the advisor's rulings ride its PRs, a ruling received outside any open PR riding
the next one) is C6's, because it is the advisor's own write path and C6 owns the advisor's doctrine.
Register entry R5 binds both. No other criterion is split.

**Moves from the starting sketch** (reasons in the README): FR-12 is C4's (it is a step of
discovery's grounding, and discovery's skill has one owner); FR-18 and the item-13 migration are
C3's (every configure change in one child, sequenced after C1 so the migration writes C1's entry
shape); FR-15's second bullet is C6's (above).

**"What this spec amends".** Spec A says each amendment "is recorded as
an owner-stamped amendment where it lives, at this spec's approval". Item 1 (front-half-sdlc-core-6181ee
FR-16 and FR-17) lives in another spec's Amendments log; the advisor recorded it there in PR #1614 at
approval, and **C5** owns the row: its second layer confirms the entry is in place and that the
retirement it builds matches it. Items 2 (showrunner duty 1) and 3 (review-spec) amend shipped plugin text, so they land when
C6 and C5 build them; item 4 (the anchor resolution) lands with C1.

Children: C1 Canon (the seam) · C2 the owner-vs-craft line · C3 configuration items · C4 the
discovery flow · C5 the three checks and the review-spec retirement · C6 the advisor's vet and the
approval handoff · C7 the theme and the template shell · C8 cards, sheets, images and answers.

**Sequencing.** Wave 0: C1 (Spec A's seam) and C7 (Spec B's seam), in parallel; they share no
surface. Wave 1: C3 after C1; C8 after C7. Wave 2: C2 after C1 and C3; C5 after C1 and C3. Wave 3: C6
after C5 and C2. Wave 4: C4, which consumes every other child; its layers may start as their own
dependencies land (layer 1 after C1, C2 and C3; layer 2 after C7; layer 3 after C5; layer 4 after C6
and C8).

| Spec | Ref | Item | Criterion (opening words) | Owner |
| --- | --- | --- | --- | --- |
| A | Amends | 1 (front-half FR-16/17) | front-half-sdlc-core-6181ee, FR-16 and FR-17: the advisor's light-or-full weight call no longer decides… | **C5** |
| A | Amends | 2 (showrunner duty 1) | The advisor's spec vet (showrunner duty 1): the advisor's vet sends findings back to discovery… | **C6** |
| A | Amends | 3 (review-spec) | review-spec: retires (FR-49, FR-49b). | **C5** |
| A | Amends | 4 (anchor resolution) | The issue contract's anchor resolution: a `ruling` anchor may point to a Canon entry… | **C1** |
| A | FR-1 | bullet 1 | no skill or reference in the plugin states a second, different line. | **C9** (moved from C2 on 2026-10-07: C2 met it for the four named terms, PR #1660; the escalation rubric remained, collector #695 item 49 = a, issue #1664) |
| A | FR-1 | bullet 2 | each place that states a version of the line today is rewritten to point to this one… | **C2** |
| A | FR-1 | bullet 3 | the advisor's existing door rules stay as they are, as cases of the line… | **C2** |
| A | FR-2 | bullet 1 | the glossary's material-consequence entry and the issue contract's craft-call section point to… | **C2** |
| A | FR-3 | bullet 1 | each category carries a description, at least one real example, and a "not yours when" note… | **C2** |
| A | FR-4 | bullet 1 (GWT) | Given a call the session cannot place with confidence… then the call goes to the owner. | **C2** |
| A | FR-5 | bullet 1 | the owner keeps the right to ask pointed questions about testing at any time… | **C2** |
| A | FR-5 | bullet 2 | grading an item into a P0, P1 or P2 tier with the advisor's grid stays craft… | **C2** |
| A | FR-6 | bullet 1 (GWT) | Given a build that picks a new outside service… the cost goes to the owner… | **C2** |
| A | FR-7 | statement | The plugin shall treat misreads, wrong facts, contradictions, jargon… as errors for review to fix… | **C2** |
| A | FR-8 | bullet 1 | the plugin has no per-project setting that moves the line. | **C2** |
| A | FR-9 | statement | When the owner cedes a kind of call… record it in Canon as a standing ruling with an example… | **C1** |
| A | FR-10 | statement | When the owner takes a ceded call back, the session shall record that in Canon… | **C1** |
| A | FR-11 | statement | Configure shall offer a project-level item, "Who it's for and what it's for"… | **C3** |
| A | FR-12 | bullet 1 (GWT) | Given a project with that item empty, when discovery grounds itself, then it recommends the advisor setup… | **C4** (moved from the sketch's C3: discovery's grounding step) |
| A | FR-13 | bullet 1 | edge cases appear as requirements, not as user stories. | **C4** |
| A | FR-14 | bullet 1 | go-words (merge, launch, release, tier) stay where the owner gives them… a ruling anchor may point to a Canon entry. | **C1** |
| A | FR-15 | bullet 1 (GWT) | Given a ruling made in chat, when the session moves on… the ruling is already committed in Canon… | **C1** |
| A | FR-15 | bullet 2 | Canon never gets a PR of its own; a spec's rulings ride the spec PR and the advisor's ride the PRs it already opens… | **C6** (split: FR-15's other bullets and its statement are C1's) |
| A | FR-15 | bullet 3 | a ruling binds every session working on the branch that holds it at once… | **C1** |
| A | FR-15 | bullet 4 | the branch-and-merge mechanics apply where definition-docs live in the repo; …project store… | **C1** |
| A | FR-16 | bullet 1 | no entry cites transcript line numbers. | **C1** |
| A | FR-16 | bullet 2 | an entry's id can't collide across branches… the merge keeps both entries. | **C1** |
| A | FR-17 | statement | Canon's standing rulings shall be the project's principles; …category 7… a standing ruling. | **C1** |
| A | FR-18 | bullet 1 | when a project adopts the release, its existing item 13 value is copied into Canon… | **C3** (moved from the sketch's C1: one child per configure surface) |
| A | FR-19 | statement | The threat model shall stay in configure's threat model item, and Canon shall not absorb it. | **C1** |
| A | FR-20 | statement | Discovery, the source check and the advisor's vet shall each read Canon, from the default branch plus their own branch… | **C1** |
| A | FR-21 | statement | Before its first question, discovery shall ground itself in: who the product is for, Canon, sibling specs… | **C4** |
| A | FR-22 | statement | At intake, discovery shall run a light scope check that splits off obvious bundles… | **C4** |
| A | FR-23 | statement | Discovery shall spend on investigation only when an unknown blocks the requirements… | **C4** |
| A | FR-24 | statement | Discovery shall ask the owner one question at a time, and only about owner-category calls… | **C4** |
| A | FR-25 | statement | Discovery shall decide craft calls itself and record each one for the owner's veto. | **C4** |
| A | FR-26 | statement | Discovery shall confirm a short framing with the owner before anything is drawn. | **C4** |
| A | FR-27 | bullet 1 | any visual that communicates counts: screens, storyboards, flow charts, diagrams. | **C4** |
| A | FR-28 | bullet 1 | where the host can't show an HTML artifact (a Codex host), the board is the local HTML file… | **C4** |
| A | FR-29 | statement | When the owner approves the build board, the approved board shall be saved as a file the project controls… | **C4** |
| A | FR-29a | statement | Where a project has turned on syncing to Claude Design, the approved board shall sync to it once… | **C4** |
| A | FR-29b | statement | Where a project uses Claude Design, its boards' design system shall come from Claude Design… | **C4** |
| A | FR-30 | statement | Where a small piece of work has nothing to draw, discovery may skip the board… | **C4** |
| A | FR-31 | bullet 1 | a tag is plain text at the end of a statement; no new script or validator reads tags. | **C4** |
| A | FR-31 | bullet 2 | no tag cites transcript line numbers. | **C4** |
| A | FR-32 | statement | Where the spec and the approved board disagree, the board shall win… | **C4** |
| A | FR-32a | statement | When the owner makes a ruling that changes something an approved board shows, discovery shall redraw… | **C4** |
| A | FR-33 | statement | A spec shall cover one piece the owner could approve and ship on its own… | **C4** |
| A | FR-34 | statement | When the review rounds come back clean, or at round 4… discovery shall run a writing pass… | **C4** |
| A | FR-35 | bullet 1 | "ready for vet" is a separate word from approval. | **C4** |
| A | FR-36 | statement | When the owner agrees the spec is ready for vet, discovery shall open the spec PR… | **C4** |
| A | FR-36a | statement | Where a project keeps its specs outside the repo, or in the repo but gitignored, the flow shall keep that storage choice… | **C4** |
| A | FR-37 | statement | The advisor's vet shall check the spec against the repo and against other approved specs, shall never fix the spec itself… | **C6** |
| A | FR-38 | statement | When the vet is clean, discovery shall send the owner a final sheet… | **C4** |
| A | FR-38a | statement | When an answer on the final sheet changes the spec, approval shall wait… | **C4** |
| A | FR-39 | bullet 1 | approval and the merge word stay separate acts. | **C6** |
| A | FR-39 | bullet 2 | the existing independent package read of the breakdown… still runs where it applies today… | **C6** |
| A | FR-40 | statement | Discovery shall never break a spec into issues, file issues or wire the project board… | **C4** |
| A | FR-41 | check: gap review | Gap review: clarity, testability, missing unhappy paths within the threat model, contradictions, safety and access. | **C5** |
| A | FR-41 | check: source check | Source check, both directions: forward… backward… | **C5** |
| A | FR-41 | check: grounding | Grounding: every claim about the product or the repo, checked against the repo. | **C5** |
| A | FR-41 | bullet 1 | grounding checks against the project's current default branch, never a session's stale branch. | **C5** |
| A | FR-42 | statement | Each check shall be run by an independent reviewer from a different model family than the spec's author… | **C5** |
| A | FR-43 | statement | Configure shall offer a spec-reviewer seat, separate from the code-review seats… | **C3** |
| A | FR-44 | bullet 1 | a recommendation is not biased toward cutting. | **C5** |
| A | FR-45 | statement | Discovery shall sort every finding into one of three piles… | **C5** |
| A | FR-46 | bullet 1 | a decline the reviewer still contests the next round goes to the owner's queue. | **C5** |
| A | FR-47 | statement | Rounds shall run without the owner's go-ahead until all three checks are clean… or until round 4. | **C5** |
| A | FR-48 | statement | After each set of owner rulings, the three checks shall run again on the parts that changed… | **C5** |
| A | FR-49 | statement | The callable `review-spec` skill shall retire, its work taken over by the three checks. | **C5** |
| A | FR-49a | statement | Every spec shall get the three checks; the spec review weight call (light or full) shall no longer decide… | **C5** |
| A | FR-49b | statement | Where review-spec is named today, the plugin shall point to the three checks instead… | **C5** |
| A | FR-50 | statement | The existing citation check on specs shall keep running beside the grounding check. | **C5** |
| A | UFR-1 | acceptance | Given an untraced product rule, when the source check finds it, then it appears on the owner's next remainder sheet… | **C4** |
| A | UFR-2 | acceptance | Given two conflicting rulings… the owner sees both rulings side by side and rules. | **C4** |
| A | UFR-3 | statement | If findings are still open after round 4, then they shall join the owner's queue marked "the review didn't settle this". | **C5** |
| A | UFR-4 | statement | If the host can't show a tap sheet, then discovery shall put the same items to the owner as numbered chat prose… | **C4** |
| A | UFR-5 | statement | If the session running a sheet ends before the owner finishes, then another session shall be able to take the sheet over… | **C4** |
| A | UFR-6 | statement | If the advisor's vet finds a product call the spec doesn't settle, then the call shall reach the owner on the final sheet from discovery… | **C6** |
| A | UFR-7 | statement | If the project has no reviewer from a different model family… a fresh reviewer from the same family… the final sheet shall say so plainly. | **C5** |
| A | NFR | Owner time | the owner never has to read a spec end to end to trust it; everything that needs them arrives as a remainder or final sheet item. | **C4** |
| A | NFR | Simplicity | source tags, Canon and the source check add no new scripts, validators or databases… | **C1** |
| B | FR-1 | statement | The plugin shall ship one review template, a light web app that works on a phone first and on a desktop too. | **C7** |
| B | FR-2 | statement | Discovery's remainder sheets and its final sheet shall use the template, built in. | **C8** |
| B | FR-3 | bullet 1 | the plugin names no expected use beyond discovery's sheets. | **C8** |
| B | FR-4 | bullet 1 (GWT) | Given an owner who answers two cards and closes the sheet, when they reopen it, then both answers are still there. | **C8** |
| B | FR-4a | bullet 1 | no extra submission machinery is built for this; a saved draft plus the owner's word is enough. | **C8** |
| B | FR-4a | bullet 2 | on a final sheet, the owner's "Send verdict" (FR-18) is that word. | **C8** |
| B | FR-5 | statement | Every card except a final sheet's last card (FR-17) shall have the same parts, in this order… | **C8** |
| B | FR-6 | bullet 1 | Aligned agrees with the card's recommendation… a pick chooses that option; Discuss leaves the call open for chat. | **C8** |
| B | FR-6 | bullet 2 | when the owner's note disagrees with their answer, the session treats the card as Discuss and asks. | **C8** |
| B | FR-6 | bullet 3 | no review adds its own answer buttons. | **C8** |
| B | FR-6 | bullet 4 | a final sheet's last card offers Approve and Not yet instead. | **C8** |
| B | FR-7 | statement | A card for a gap the reviewer found, a statement with no source, or a finding the review didn't settle shall carry a red warning badge… | **C8** |
| B | FR-8 | statement | When a call has images that bear on it… its card shall show them, in every review. | **C8** |
| B | FR-9 | statement | When the owner taps an image on a card, the sheet shall open it on its own, large, with a Close control… | **C8** |
| B | FR-10 | statement | While an image is open, the owner shall be able to pinch or double-tap to zoom and drag to look around. | **C8** |
| B | FR-11 | statement | The image view shall not move between images by swiping sideways… | **C8** |
| B | FR-12 | statement | A sheet shall show the review's name in a yellow app bar, and how many items are answered out of the total. | **C8** |
| B | FR-13 | statement | On a phone, a remainder sheet shall fold answered items into one row… | **C8** |
| B | FR-14 | statement | On a desktop, a sheet shall list every item with its state beside the open card, with Previous and Next controls. | **C8** |
| B | FR-15 | statement | A remainder sheet shall say why it holds only these items… | **C8** |
| B | FR-16 | statement | The owner shall be able to leave a sheet unfinished with "Done for now" and come back to it. | **C8** |
| B | FR-17 | bullet 1 | below the last card, the sheet says what happens next: the advisor adds the breakdown to the same PR… | **C8** |
| B | FR-18 | statement | The owner shall send a final sheet's verdict, and with it the sheet's answers, with one "Send verdict" action… | **C8** |
| B | FR-19 | statement | The plugin shall ship one visual theme, Comic panel, for its own pages… | **C7** |
| B | FR-20 | statement | Each theme colour shall have one job… | **C7** |
| B | FR-21 | statement | The theme shall set headings in Bricolage Grotesque 800, body text in Atkinson Hyperlegible 400 and 700… | **C7** |
| B | FR-22 | statement | The theme's parts shall follow its drawn rules: 3px ink outlines… | **C7** |
| B | UFR-1 | statement | If a sheet can't be shown on the owner's host, then the session shall put the same items to the owner as numbered chat prose… | **C8** |
| B | UFR-2 | acceptance | Given a failed save, when the owner looks at the card, then it shows that the answer wasn't saved and lets them try again. | **C8** |
| B | UFR-3 | statement | If an image can't load, then the card shall still show its question, context and answers, and say the image is missing. | **C8** |
| B | UFR-4 | statement | If someone other than the owner opens a sheet the owner shared, then they shall see it but shall not be able to answer. | **C8** |
| B | NFR | Readability | all text meets a 4.5 to 1 contrast ratio; white text sits only on blue, red or ink. | **C7** |
| B | NFR | Privacy | a sheet is private to the owner by default; the owner may share it to show someone. | **C8** |
| B | NFR | Touch | every control is at least 44px tall. | **C7** |
| B | NFR | Telling things apart | colours that must be told apart also differ in lightness. | **C7** |

**Counts.** Spec A: C1: 13, C2: 11, C3: 3, C4: 31, C5: 18, C6: 6; total 82 (4 amends items, 69 FR criteria, 7 UFR criteria, 2 NFRs). Spec B: C7: 8, C8: 27; total 35 (27 FR criteria, 4 UFR criteria, 4 NFRs). Per child, both specs: C1: 13, C2: 11, C3: 3, C4: 31, C5: 18, C6: 6, C7: 8, C8: 27; children 117. **Total criteria: 117. Unallocated: 0. Owned twice: 0.**

**Within stacked children** (for the layer sub-issues; each layer's DoD grades only its rows):

- C4 (31): layer 1, grounding and questions: FR-12, FR-13, FR-21 to FR-26, UFR-2 (9); layer 2,
  boards: FR-27, FR-28, FR-29, FR-29a, FR-29b, FR-30, FR-32, FR-32a (8); layer 3, writing: FR-31 (2),
  FR-33, FR-34, FR-40 (5); layer 4, sheets and the handoff: FR-35, FR-36, FR-36a, FR-38, FR-38a, UFR-1,
  UFR-4, UFR-5, the owner-time NFR (9).
- C5 (18): layer 1, the checks: FR-41 (4), FR-42, FR-44 to FR-48, FR-50, UFR-3, UFR-7 (13); layer 2,
  the retirements: amends items 1 and 3, FR-49, FR-49a, FR-49b (5).
- C7 (8): layer 1, the theme: Spec B FR-19 to FR-22 and the readability, touch and telling-apart
  NFRs (7); layer 2, the template shell: Spec B FR-1 (1).
- C8 (27): layer 1, cards and answers: Spec B FR-3, FR-4, FR-4a (2), FR-5, FR-6 bullets 1 to 3,
  FR-7, UFR-2, UFR-4, the privacy NFR (12); layer 2, sheets: FR-2, FR-12 to FR-16, UFR-1 (7); layer 3,
  the final sheet: FR-6 bullet 4, FR-17, FR-18 (3); layer 4, images: FR-8 to FR-11, UFR-3 (5).

**Spec sections that are not criteria but have a builder home.** These carry no acceptance
criterion under the rule above and are not in the counts; each is named so nothing in either spec
falls between children.

| Spec | Section | What it asks | Home |
| --- | --- | --- | --- |
| A | How to read this spec | the decisions among the handoff's rulings "move into Canon once Canon exists" | C1 (this repository's `docs/superheroes/canon.md` seed) |
| A | Glossary | Canon, ceded call, standing ruling; remainder sheet, ready for vet | C1; C4 (register R24) |
| B | Glossary | card, sheet | C8 (register R24) |
| A | Assumptions & dependencies | one setup sitting with the review-overhaul discovery's risk profile | C3, with the reciprocal seam owed to #1472 (register R12) |
| A | Constraints | no overbuilt machinery; one line for every project | C1, C4, C5 (R23); C2 (FR-8) |
| A, B | UI / UX | the approved board is the design | C2, C4, C6, C7, C8 (each child's launch context names its artboards) |
| A, B | Definition of done / success | the end-to-end outcome | graded at the epic's closure, with the last child's handback (C4) |
| A | Consequences of accepting this spec | what changes for the owner and for each project | each child's consequence line; the README |
| A, B | Out of scope | nothing to build | none |
