---
superheroes: doc
schemaVersion: 1
docType: spec
workItem: aligning-on-what-to-build-6da1ee
issue: null
size: large
status: draft
gates: {review: pending}
producedBy: "the-architect@0.33.0"
created: "2026-10-03"
updated: "2026-10-03"
---
# Aligning on what to build

## How to read this spec

Every statement ends with its source in plain text. The sources are:

- **ruling N**: the owner's numbered rulings in the discovery handoff,
  `docs/superheroes/discovery-notes/spec-alignment/HANDOFF.md`, items 1 to 61 under "Session 3",
  the board rounds that follow it, "Remainder sheet 1 rulings" and "Final sheet rulings". The decisions among them move into Canon once Canon exists; go-words stay here. (source: rulings 41, 55)
- **the line**: the ratified owner-vs-craft line, `OWNER-VS-CRAFT-LINE.md` beside the handoff, as
  amended by rulings 21 and 22. (source: ruling 22)
- **board · <artboard>**: the approved board, https://claude.ai/artifact/FDiMfa95mWjEPCaT64d5pf,
  round 3 plus ruling 38, approved 2026-10-03. (source: ruling 39)
- **framing**: the framing brief approved 2026-09-28, with its defaults. (source: ruling 18)
- **craft**: a choice made by the author, recorded for the owner's veto.

The look of tap sheets, the shared review template and the plugin's visual theme are a sibling
spec, `the-review-surface-d59417`. This spec relies on that one and does not restate it.
(source: ruling 40)

## What this spec amends

Accepting this spec amends these approved or shipped rules; each change is recorded as an
owner-stamped amendment where it lives, at this spec's approval. (source: advisor vet round 1, F1)

- **front-half-sdlc-core-6181ee, FR-16 and FR-17:** the advisor's light-or-full weight call no
  longer decides how a spec is reviewed; every spec gets the three checks (FR-49a). (source: ruling
  43) [cite: docs/superheroes/front-half-sdlc-core-6181ee/spec.md § **FR-16.**]
- **The advisor's spec vet (showrunner duty 1):** the advisor's vet sends findings back to
  discovery, and discovery's final sheet, not the advisor, asks the owner for approval (FR-37,
  FR-38). (source: rulings 25, 29) [cite: plugins/superheroes/skills/showrunner/SKILL.md § ready for your approval]
- **review-spec:** retires (FR-49, FR-49b). (source: ruling 11)
- **The issue contract's anchor resolution:** a `ruling` anchor may point to a Canon entry, which
  counts as reachable where the ruling was made; the contract's attribution, date and supersession
  checks still apply. (source: ruling 55) [cite: plugins/superheroes/skills/showrunner/reference/issue-contract.md § Anchor resolution]

## Purpose

What an owner agrees with an agent and what gets written down drift apart, and owners get asked
about the wrong things: consulted on craft, skipped on real product calls. This work gives every project that uses superheroes one clear line between the owner's
decisions and craft, a durable record of every ruling, and a discovery flow in which the owner
decides by looking at drawn boards, reviews only what nobody has ruled on yet, and never has to
read a spec end to end to trust it. (source: ruling 8; framing)

## Who it's for

- As the owner of a project that uses superheroes, I want to be asked only about decisions that
  are mine, so I can spend my time on the product instead of on craft. (source: the line)
- As that owner, I want to decide by looking at drawn boards, so I can see what I'm agreeing to
  before any spec is written. (source: ruling 8)
- As that owner, I want to review only what I haven't already ruled on, so I can trust a spec
  without reading all of it. (source: ruling 8)
- As a discovery, advisor or builder session, I want every past ruling in one place, so I never
  ask the same question twice or contradict an earlier answer. (source: board · Source tags and Canon)

## Functional requirements

### The owner-vs-craft line

**FR-1.** The plugin shall apply one owner-vs-craft line everywhere it makes or routes a decision:
discovery, the advisor, merges, fixes after approval, deviations and follow-ups. (source: the line)
  - *Acceptance (rule):* no skill or reference in the plugin states a second, different line. (source: as its requirement)
  - *Acceptance (rule):* each place that states a version of the line today is rewritten to point
    to this one: showrunner duty 5's two tests and `perceivability.md`; `owner-decisions.md` §
    "Craft calls and owner calls"; the glossary's craft-call and owner-call entries; the issue
    contract's material-consequence default. (source: advisor vet round 1, F2) [cite: plugins/superheroes/skills/showrunner/reference/owner-decisions.md § Craft calls and owner calls]
  - *Acceptance (rule):* the advisor's existing door rules stay as they are, as cases of the line:
    a new filing waits on the owner's word at every tier (category 6), except the layer sub-issues
    of a stack (whether the owner approved its shape or the advisor ruled a size split, recorded
    for veto; a layer carrying unapproved scope still waits) and what an approved spec's word
    already covers, and a scope change waits on the owner (category 4). (source: board · The owner-vs-craft line, in full; advisor vet round
    2, F15) [cite: plugins/superheroes/skills/showrunner/reference/owner-decisions.md § The tiers and the filing rule]

**FR-2.** The line shall strengthen the plugin's existing material-consequence line rather than
add a second one [cite: plugins/superheroes/rubric/glossary.md § Material consequence].
(source: the line)
  - *Acceptance (rule):* the glossary's material-consequence entry and the issue contract's
    craft-call section point to the line's ten categories and its sorting rule; FR-1 lists the
    other places. (source: as its requirement)

**FR-3.** The line shall name ten owner categories (source: the line; rulings 21, 30):
  1. Who the product is for and what it's for, kept once per project.
  2. Who this piece of work is for and what they're trying to do, captured per piece as user
     stories.
  3. What a person sees or can do at a given moment.
  4. Whether a thing should exist at all.
  5. Risk tolerance and trust.
  6. The owner's own time, attention and habits.
  7. A case that tests or creates a principle.
  8. The quality bar, and what counts as proof.
  9. All user-facing copy: agents draft it, the owner approves it.
  10. Priority and timing.
  - *Acceptance (rule):* each category carries a description, at least one real example, and a
    "not yours when" note, as drawn on the board. (source: board · The owner-vs-craft line, in full)

**FR-4.** When any session meets a call, it shall sort the call this way: if an approved
artifact, a standing ruling in Canon, the code or a checkable fact already answers it, or the
owner has ceded that kind of call, it is craft; otherwise, if it touches any of the ten
categories, it is the owner's; if the session is sure it touches none, it is craft; if the session
is unsure, it is the owner's. (source: ruling 22; board · The owner-vs-craft line, in full)
  - *Acceptance (Given-When-Then):* Given a call the session cannot place with confidence, when
    it sorts the call, then the call goes to the owner. (source: as its requirement)

**FR-5.** The line shall list what is always craft, decided by agents and recorded for the
owner's veto: matching an approved board or reusing an existing pattern; applying a set rule to a
new case; bookkeeping when only a fact changed; pulling implementation detail out of a
requirement; routine size splits and the shape of a breakdown; how it's built and tested; tools
and libraries; internal names and internal error handling; how a speed or size target is met;
cleanup that changes no behaviour. (source: the line)
  - *Acceptance (rule):* the owner keeps the right to ask pointed questions about testing at any
    time, and a question does not make testing an owner category. (source: the line)
  - *Acceptance (rule):* grading an item into a P0, P1 or P2 tier with the advisor's grid stays
    craft (applying a set rule); the tier words don't change. (source: the line; advisor vet round
    1, F13; craft, for your veto)

**FR-6.** When a craft choice carries an owner consequence, the session shall raise that
consequence to the owner as its own decision, and the craft choice itself shall stay craft.
(source: the line)
  - *Acceptance (Given-When-Then):* Given a build that picks a new outside service, when the
    service adds a monthly cost, then the cost goes to the owner and the choice of service does not. (source: as its requirement)

**FR-7.** The plugin shall treat misreads, wrong facts, contradictions, jargon in owner-facing
text and gaps a review should catch as errors for review to fix, never as decisions.
(source: the line)

**FR-8.** The line's categories shall be the same in every project; a project adjusts how many
calls are already answered only through the owner's rulings in Canon. (source: the line; board ·
The owner-vs-craft line, in full)
  - *Acceptance (rule):* the plugin has no per-project setting that moves the line. (source: as its requirement)

**FR-9.** When the owner cedes a kind of call ("you decide these from now on"), the session
shall record it in Canon as a standing ruling with an example, called a ceded call, and later calls of that kind are
craft. (source: board · The owner-vs-craft line, in full; rulings 39, 60)

**FR-10.** When the owner takes a ceded call back, the session shall record that in
Canon, and later calls of that kind return to the owner. (source: board · The owner-vs-craft
line, in full)

### Who it's for

**FR-11.** Configure shall offer a project-level item, "Who it's for and what it's for", holding
owner category 1, beside the threat model item [cite: plugins/superheroes/lib/project_config.py § Threat model]. (source: board · The owner-vs-craft line, in full; the line)

**FR-12.** When a discovery starts and the project has no "who it's for and what it's for" yet,
discovery shall strongly recommend setting it up with the advisor before going on. (source:
ruling 10)
  - *Acceptance (Given-When-Then):* Given a project with that item empty, when discovery grounds
    itself, then it recommends the advisor setup in plain words before its first question; if the
    owner chooses to go on without it, discovery goes on. (source: ruling 10)

**FR-13.** Each discovery shall capture who the piece is for as one or more user stories, "As a
…, I want …, so I can …", that evoke the core need without listing every detail. (source:
ruling 30)
  - *Acceptance (rule):* edge cases appear as requirements, not as user stories. (source: as its requirement)

### Canon: the record of the owner's decisions

**FR-14.** Each project shall keep Canon: one plain file, `canon.md`, where the project keeps its
definition-docs, holding the owner's decisions: answers to owner calls, principles and ceded calls.
(source: rulings 32, 35, 55, 61)
  - *Acceptance (rule):* go-words (merge, launch, release, tier) stay where the owner gives them,
    and walk records and the declined-items registry carry on as they are; an issue's ruling anchor
    may point to a Canon entry. (source: ruling 55) [cite: plugins/superheroes/skills/showrunner/reference/issue-contract.md § Anchor resolution]

**FR-15.** When the owner makes a ruling that decides something (FR-14) in any session, that
session shall add the ruling to Canon and commit it at once to the branch it is working on; the ruling reaches the default branch
when that branch merges. (source: board · Source tags and Canon; ruling 61)
  - *Acceptance (Given-When-Then):* Given a ruling made in chat, when the session moves on to its
    next step, then the ruling is already committed in Canon on that session's branch. (source:
    as its requirement)
  - *Acceptance (rule):* Canon never gets a PR of its own; a spec's rulings ride the spec PR and
    the advisor's ride the PRs it already opens; a ruling the advisor receives outside any open PR
    is committed to the branch of the next PR the advisor opens, and until then only that branch
    sees it. (source: ruling 61; advisor vet round 4, F16; craft, for your veto)
  - *Acceptance (rule):* a ruling binds every session working on the branch that holds it at once,
    and sessions on other branches once it reaches the default branch; until then, they may not
    see it. (source: ruling 61, the
    trade-off the owner accepted)
  - *Acceptance (rule):* the branch-and-merge mechanics apply where definition-docs live in the
    repo; where a project keeps them out of the repo, Canon lives in its project store and each
    ruling is committed there at once, binding at once every session that shares that store on
    the machine. (source: ruling 61, applied to the project store; advisor vet round 4, F18; craft,
    for your veto) [cite: CONVENTIONS.md § 2.3 Storage mode]

**FR-16.** Each Canon entry shall carry: an id, the date, the ruling, whether it is standing
(applies to all later work) or for this piece, the owner's exact words where there are any, and
a pointer to where it was said (the session and the time). (source: ruling 33; board · Source
tags and Canon)
  - *Acceptance (rule):* no entry cites transcript line numbers. (source: ruling 33)
  - *Acceptance (rule):* an entry's id can't collide across branches (for example the date, the
    session's short id and a sequence number), and when two branches both add to Canon, the merge
    keeps both entries. (source: advisor vet round 4, F17)

**FR-17.** Canon's standing rulings shall be the project's principles; when the owner answers a
category 7 case, the session shall record the answer as a standing ruling. (source: ruling 32;
board · The owner-vs-craft line, in full)

**FR-18.** Configure's material-consequence item shall point to Canon's standing rulings rather
than hold its own copy [cite: plugins/superheroes/lib/project_config.py § Material consequence line]. (source: ruling 39)
  - *Acceptance (rule):* when a project adopts the release, its existing item 13 value is copied
    into Canon as standing rulings, each marked "migrated from configure item 13 on <date>" and
    carrying the original session and time where known, or saying they are unknown; item 13 then
    points there; until it adopts, the project keeps today's
    behaviour. (source: advisor vet round 1, F5; craft, for your veto)

**FR-19.** The threat model shall stay in configure's threat model item, and Canon shall not
absorb it. (source: ruling 32)

**FR-20.** Discovery, the source check and the advisor's vet shall each read Canon, from the
default branch plus their own branch: discovery
before its first question, the source check to trace tags, the vet to check a spec across every
piece. (source: board · Source tags and Canon; ruling 61)

### The discovery flow

**FR-21.** Before its first question, discovery shall ground itself in: who the product is for,
Canon, sibling specs and their boards, and the product as built. (source: ruling 8)

**FR-22.** At intake, discovery shall run a light scope check that splits off obvious bundles; the
real split check happens when the spec is written (FR-33). (source: ruling 23)

**FR-23.** Discovery shall spend on investigation only when an unknown blocks the requirements,
and only after the owner consents to a named cost. (source: ruling 8)

**FR-24.** Discovery shall ask the owner one question at a time, and only about owner-category
calls; a question that is a real choice carries its options, plain consequences and a
recommendation, and an open question may be asked as it is. (source: ruling 8) [cite: plugins/superheroes/skills/architect-discovery/SKILL.md § Frame every consequential choice as prose]

**FR-25.** Discovery shall decide craft calls itself and record each one for the owner's veto.
(source: ruling 8)

**FR-26.** Discovery shall confirm a short framing with the owner before anything is drawn.
(source: ruling 8)

**FR-27.** Discovery shall draw the work before writing it: journeys or flows first, then open
choices side by side, then a build board holding only the settled design, with everything that can
reasonably be drawn drawn and the real wording in place. (source: ruling 8; board · The flow)
  - *Acceptance (rule):* any visual that communicates counts: screens, storyboards, flow charts,
    diagrams. (source: ruling 1)

**FR-28.** Every board shall be an HTML artifact carrying the project's design system files for
the product it draws (the plugin's own frame, labels and sheets use the Comic panel theme from
the sibling spec), and
shall never be less detailed than the chat it draws from: the board is the higher-resolution
record. (source: ruling 2; board round 1 comments; advisor vet round 1, F10)
  - *Acceptance (rule):* where the host can't show an HTML artifact (a Codex host), the board is
    the local HTML file the project keeps (FR-29), opened in a browser. (source: ruling 3; advisor
    vet round 1, F9; craft, for your veto)

**FR-29.** When the owner approves the build board, the approved board shall be saved as a file
the project controls, kept with its spec. (source: ruling 3)

**FR-29a.** Where a project has turned on syncing to Claude Design, the approved board shall
sync to it once, at approval; syncing stays the project's choice. (source: rulings 2, 3)

**FR-29b.** Where a project uses Claude Design, its boards' design system shall come from Claude
Design, whether or not syncing is turned on. (source: ruling 2)

**FR-30.** Where a small piece of work has nothing to draw, discovery may skip the board; the spec
is then written from the framing and the rulings, and still carries source tags and goes through
the remainder sheet. (source: framing)

**FR-31.** Where the work has a board, discovery shall write the spec only after the build board
is approved, from the board and the rulings, ending every statement with its source tag. (source:
rulings 8, 9; framing)
  - *Acceptance (rule):* a tag is plain text at the end of a statement; no new script or
    validator reads tags. (source: board · Source tags and Canon; ruling 10)
  - *Acceptance (rule):* no tag cites transcript line numbers. (source: ruling 33)

**FR-32.** Where the spec and the approved board disagree, the board shall win and the spec shall
be corrected. (source: ruling 8)

**FR-32a.** When the owner makes a ruling that changes something an approved board shows,
discovery shall redraw the affected part of the board and show it on the owner's next sheet, so the
board stays the truth. (source: ruling 45)

**FR-33.** A spec shall cover one piece the owner could approve and ship on its own. When writing
turns up a second piece, discovery shall propose a split and the owner shall rule; when a spec
passes about 300 to 400 lines, discovery shall raise splitting with the owner, and length alone
shall never stop the work. (source: ruling 36)

**FR-34.** When the review rounds come back clean, or at round 4, and before the owner's sheet,
discovery shall run a writing pass to the plugin's writing standard, followed by a check that no meaning shifted.
(source: ruling 24; board · The review cycle)

**FR-35.** Discovery shall send the owner remainder sheets holding only what no board, ruling or
earlier answer covers, plus findings the review didn't settle and declines the reviewer still
contests, round after round until none is left, and then ask the owner to agree the
spec is ready for vet. (source: rulings 4, 8, 16)
  - *Acceptance (rule):* "ready for vet" is a separate word from approval. (source: ruling 4)

**FR-36.** When the owner agrees the spec is ready for vet, discovery shall open the spec PR for
the advisor's vet. (source: board · The flow)

**FR-36a.** Where a project keeps its specs outside the repo, or in the repo but gitignored, the
flow shall keep that storage choice: the spec where the project keeps it stands in for the PR, with
the same vet, approval and merge-word steps, and issues are filed at the merge word. (source:
ruling 47; craft, for your veto: gitignored specs treated the same way)

**FR-37.** The advisor's vet shall check the spec against the repo and against other approved
specs, shall never fix the spec itself, and shall send every finding back to discovery, which
fixes it; the advisor then vets again. (source: rulings 14, 25)

**FR-38.** When the vet is clean, discovery shall send the owner a final sheet holding the vet's
owner calls and the folded list of declined findings, whose last card asks for approval of the
spec. (source: rulings 6, 16, 29)

**FR-38a.** When an answer on the final sheet changes the spec, approval shall wait: discovery
applies the change, the checks re-run on the changed parts, the advisor vets again, and a new last
card asks for approval. (source: ruling 44)

**FR-39.** After the owner approves, the advisor shall add the breakdown to the same PR and vet
it; one merge word from the owner shall cover both, and issues shall be filed, with the owner's
word, as it merges. (source: ruling 26)
  - *Acceptance (rule):* approval and the merge word stay separate acts. (source: ruling 6)
  - *Acceptance (rule):* the existing independent package read of the breakdown, by seats other
    than the breakdown's author, still runs where it applies today, before an epic's children file; single-issue work keeps its
    fast path. (source: advisor vet round 1, F3; craft, for your veto) [cite: plugins/superheroes/skills/showrunner/reference/decomposition.md § The adversarial package read]

**FR-40.** Discovery shall never break a spec into issues, file issues or wire the project board;
the discovery skill shall say plainly that the advisor does these after approval. (source:
ruling 5; framing)

### The review cycle

**FR-41.** When a spec is written, three checks shall run on it in parallel (source: rulings 14,
15):
  - **Gap review:** clarity, testability, missing unhappy paths within the threat model,
    contradictions, safety and access.
  - **Source check, both directions:** forward, every statement has a source and matches it,
    board first, and nothing in it belongs to another piece; backward, every ruling for this
    piece, every element of the approved board that belongs to this piece, and the framing is in the
    spec and written down
    right. (source: rulings 12, 14)
  - **Grounding:** every claim about the product or the repo, checked against the repo.
  - *Acceptance (rule):* grounding checks against the project's current default branch, never a
    session's stale branch. (source: advisor vet round 2, F15; craft, for your veto)

**FR-42.** Each check shall be run by an independent reviewer from a different model family than
the spec's author, and the same reviewer shall continue across rounds, confirming the last
round's fixes before looking for new problems; UFR-7 covers a project with no such reviewer.
(source: rulings 15, 42)

**FR-43.** Configure shall offer a spec-reviewer seat, separate from the code-review seats; the
plugin shall name no model for it. (source: ruling 15)

**FR-44.** A reviewer shall find problems and never add product behaviour; a fix that would add
behaviour goes to the owner's queue with a recommendation weighed on its merits. (source:
ruling 7)
  - *Acceptance (rule):* a recommendation is not biased toward cutting. (source: ruling 7)

**FR-45.** Discovery shall sort every finding into one of three piles: craft, which discovery
fixes; the owner's (a fix that adds behaviour, an unsourced product decision, two conflicting
rulings), left unfixed and queued; or declined. (source: ruling 16)

**FR-46.** Discovery shall decline a finding only for one of five reasons, each citing its proof:
the finding is wrong (a spec line), outside the threat model (an entry), asks for
implementation, belongs to another spec, or duplicates a queued item. (source: ruling 16)
  - *Acceptance (rule):* a decline the reviewer still contests the next round goes to the owner's
    queue. (source: ruling 16)

**FR-47.** Rounds shall run without the owner's go-ahead until all three checks are clean apart
from items already queued, or until round 4. (source: ruling 16)

**FR-48.** After each set of owner rulings, the three checks shall run again on the parts that
changed, with up to 4 rounds of their own. (source: rulings 16, 46)

**FR-49.** The callable `review-spec` skill shall retire, its work taken over by the three checks
[cite: plugins/superheroes/skills/review-spec/SKILL.md]. (source: ruling 11)

**FR-49a.** Every spec shall get the three checks; the spec review weight call (light or full)
shall no longer decide how a spec is reviewed, code review's light, full and micro lanes are
unchanged, and the advisor may still size its own vet [cite: plugins/superheroes/skills/architect-discovery/SKILL.md § The weight call, then review at that weight]. (source: ruling 43; advisor vet round 1, F14a)

**FR-49b.** Where review-spec is named today, the plugin shall point to the three checks instead:
the spec-writing and discovery skills, showrunner duty 1, CONVENTIONS and the keep-or-retire list.
Amendments after approval keep today's path; the three checks don't run on them. (source:
ruling 58) A spec's review gate keeps its states (pending, changes-requested, passed), and it passes only when
the owner approves; when a fix changes content the owner already approved, the gate goes back to
pending, as it does today when a review run revises approved content. (source: ruling 11; advisor vet round
1, F11) [cite: CONVENTIONS.md § changes-requested] [cite: plugins/superheroes/skills/review-spec/SKILL.md § Stale-approval guard]

**FR-50.** The existing citation check on specs shall keep running beside the grounding check.
(source: ruling 14)

## When things go wrong (significant unhappy paths)

**UFR-1.** If a spec statement has no source and decides product behaviour, then discovery shall
put it on the owner's queue rather than keep or cut it on its own. (source: ruling 16)
  - *Acceptance:* Given an untraced product rule, when the source check finds it, then it appears
    on the owner's next remainder sheet with a recommendation. (source: as its requirement)

**UFR-2.** If a new ruling conflicts with an earlier ruling in Canon, then discovery shall put the
conflict to the owner as its own decision. (source: ruling 16)
  - *Acceptance:* Given two conflicting rulings, when either check or discovery notices, then the
    owner sees both rulings side by side and rules. (source: as its requirement)

**UFR-3.** If findings are still open after round 4, then they shall join the owner's queue marked
"the review didn't settle this". (source: ruling 16; board · The review cycle)

**UFR-4.** If the host can't show a tap sheet, then discovery shall put the same items to the owner
as numbered chat prose, each with its context, options and recommendation. (source: framing)

**UFR-5.** If the session running a sheet ends before the owner finishes, then another session
shall be able to take the sheet over, with the answers and any verdict already given, because the
sheet's source and its answers are saved where a later session can read them. The plugin assumes
nothing about an owner having more than one Claude account. (source: framing; ruling 59)

**UFR-6.** If the advisor's vet finds a product call the spec doesn't settle, then the call shall
reach the owner on the final sheet from discovery, never as a fix the advisor made. (source:
rulings 25, 29)

**UFR-7.** If the project has no reviewer from a different model family than the spec's author,
then the checks shall run with a fresh reviewer from the same family, and the owner's final sheet
shall say so plainly. (source: ruling 42)

## Non-functional requirements

- **Owner time:** the owner never has to read a spec end to end to trust it; everything that
  needs them arrives as a remainder or final sheet item. (source: ruling 8)
- **Simplicity:** source tags, Canon and the source check add no new scripts, validators or
  databases; an agent reading plain files does the checking. (source: ruling 10; board · Source
  tags and Canon)

## UI / UX

The approved board is the design: https://claude.ai/artifact/FDiMfa95mWjEPCaT64d5pf, artboards
"Start here", "The flow, as a flow chart", "The review cycle", "Source tags and Canon" and "The
owner-vs-craft line, in full". The tap sheets, the review template and the theme are specified in
`the-review-surface-d59417`. (source: rulings 39, 40)

## Definition of done / success

On a project that uses superheroes, a new discovery runs from intake to handoff as drawn on the
board: the owner rules one question at a time, approves a board where the work has one, sees on
their sheets only unruled items plus findings the review didn't settle, agrees "ready for vet", approves on a final sheet after a clean vet, and gives one merge
word, while every decision lands in Canon and no session asks a question Canon already answers
once that ruling has reached its branch. (source: ruling 8, 16, 55, 61; board · The flow)

## Assumptions & dependencies

- The review surface (`the-review-surface-d59417`) provides the tap sheets this flow sends.
  (source: ruling 40)
- A reviewer from a different model family than the spec's author is usually available; when it
  isn't, UFR-7 applies. (source: rulings 15, 42)
- Setup asks "who it's for and what it's for" and the review-overhaul discovery's risk profile in
  one sitting; where risk-tolerance records live is decided once, together with that discovery.
  (source: ruling 57)

## Constraints

- No complex or overbuilt machinery: plain-text tags, one plain Canon file, checks done by an
  agent reading. (source: ruling 10)
- One line for every adopting project; examples illustrate it, and an owner's specific preferences
  are that project's rulings. (source: the line)

## Out of scope

- The look of sheets, the review template, image zoom and the theme: the sibling spec. (source:
  ruling 40)
- Moving the threat model or other review inputs into Canon: left to the review-overhaul
  discovery. (source: ruling 32)
- How review progress is shown while rounds run: craft for the build. (source: ruling 17)
- Breaking this spec into issues: the advisor's, after approval. (source: ruling 26)

## Consequences of accepting this spec

(source: advisor vet round 1, F12; the summary is craft, for your veto; each line cites what it
summarizes)

- **For the owner:** decisions come one question at a time, then by board; review is a few tap
  sheets of unruled items instead of reading specs; approval comes after the vet, on a final
  sheet. Canon needs no upkeep from the owner; sessions write it. (source: ruling 8; FR-15)
- **For each project using superheroes (weekly-eats too):** nothing changes until it adopts the
  release; at adoption its item 13 value moves into Canon, its next discovery runs the new flow,
  and specs get the three checks instead of review-spec. (source: FR-18, FR-21 to FR-40, FR-49a;
  ruling 43)
- **What retires:** review-spec, the spec review weight call, and the advisor delivering spec
  approval. Code review is untouched. (source: rulings 11, 29, 43; FR-38, FR-49a)
- **Cost:** three reviewers for up to four rounds per spec, plus re-checks after rulings, traded
  for less owner reading and fewer late vet findings. (source: ruling 18)

## Glossary

- **Canon:** the project's record of the owner's decisions (answers to owner calls, principles and
  ceded calls), standing or for one piece; go-words stay where they're given. (source: rulings 35,
  55, 60)
- **Ceded call:** a kind of call the owner has told agents to decide from now on, kept in Canon as a
  standing ruling; not the same as a builder's handback. (source: ruling 60)
- **Standing ruling:** a ruling that applies to all later work; the project's principles are its
  standing rulings. (source: ruling 32)
- **Remainder sheet:** a tap sheet holding only what nothing already rules on, plus findings the
  review didn't settle and declines the reviewer still contests. (source: rulings 8, 16)
- **Ready for vet:** the owner's word that the spec may go to the advisor's vet; not approval.
  (source: ruling 4)

## Amendments

_No amendments since the last full approval._

## Coverage

The author's audit record. Where a row names a requirement, that requirement carries the source;
where it gives a reason instead, the reason is the author's, recorded for the owner's veto.
(source: craft)

| Area | Disposition | Show-it? | Where / why |
| --- | --- | --- | --- |
| Empty & first-run | Specify | Yes | FR-12: a project with no "who it's for" yet (source: as the requirement named) |
| Invalid & malformed input | N-A | — | The flow takes no typed input beyond the owner's words (source: craft) |
| Boundaries & limits | Specify | No | FR-33 split trigger; FR-47 round cap; UFR-3 (source: as the requirement named) |
| Errors & failures | Specify | No | UFR-4 sheet can't show; UFR-5 session ends mid-sheet (source: as the requirement named) |
| Access & permissions | Defer-to-build | No | Who may write Canon follows the project's existing repo access (source: craft) |
| Duplicates & double-actions | Specify | No | FR-20, FR-4: Canon answers a repeated question (source: as the requirement named) |
| Conflicting / simultaneous use | Specify | Yes | UFR-2: conflicting rulings go to the owner (source: as the requirement named) |
| Misuse & abuse | N-A | — | Malicious input is outside the plugin's threat model (source: craft) |
| Reach (i18n / a11y) | Defer-to-build | No | Sheet accessibility is in the sibling spec (source: craft) |
| Wording & tone | Specify | No | FR-34 writing pass; category 9, owner approves user-facing copy (source: as the requirement named) |
| Workflow shape | Specify | Yes | FR-21 to FR-40, as drawn on the flow board (source: as the requirement named) |
| Placement & prominence | N-A | — | No product screen in this spec; see the sibling spec (source: craft) |
| Limits & defaults | Specify | No | FR-47 four rounds; FR-33 300 to 400 lines (source: as the requirement named) |
| Tier & access boundaries | Specify | No | FR-43 spec-reviewer seat separate from code review; UFR-7 when no cross-family reviewer exists (source: as the requirement named) |
| Visibility & disclosure | Specify | Yes | FR-38: declines listed, folded, on the final sheet (source: as the requirement named) |
