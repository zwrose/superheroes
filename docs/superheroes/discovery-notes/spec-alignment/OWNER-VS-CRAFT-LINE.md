# The owner-decision vs craft line

**Status: owner-ratified in chat 2026-09-21 to 2026-09-27, item by item, as an input to the
spec-alignment discovery. Not shipped, not a spec, no work-item minted.** It strengthens the
plugin's existing material-consequence line (glossary, and the showrunner issue contract's
"Craft calls, owner calls, and the material-consequence line"); it is not a second line. The
earlier derived draft is in git history. The owner's rulings, in order, are logged at the end.

Derived from 234 real cases where a decision turned out to be the owner's (51 post-approval
spec amendments across two repos, 183 transcript moments). The corpus is selected for owner
interventions, so it under-samples craft; the craft list was filled out by owner ruling.

## The line

A decision is the owner's when getting it right needs something only the owner has: who the
product is for and what it is for, what it means to a person, what they see at a given moment,
whether it should exist at all, how much risk and cost to carry, the owner's own time and
habits, a case no stated principle settles, the quality bar, the words users read, and
priority. How it gets built, tested and cleaned up is craft, and so is anything an approved
decision or rule already answers. A craft choice never becomes the owner's, but an owner
consequence it carries is raised as its own decision. When in doubt, it goes to the owner.
Each owner ruling becomes a standing rule, so over time more of a project's calls become craft.
Mistakes are not decisions; review catches them.

## Scope

- One line for the whole plugin and every adopting project: discovery, the advisor, merges,
  post-approval fixes, deviations, follow-ups.
- Categories and tests are generic. Examples illustrate; an owner's specific preferences are
  that project's rulings, not part of the line.
- The line is fixed. A project adjusts it only through the owner's rulings (a handed-back kind
  of call becomes craft by test 4), recorded where agents read them. No per-project setting.
- Doubt resolves to an owner call. Over-consultation is fixed by a fuller craft list and by
  better presentation, never by moving the default.

## Four tests (apply in order)

1. **Derivable?** Could the answer come from an approved artifact, a standing rule, the code, or
   a checkable fact? Then craft.
2. **Experience-dependent?** Does it depend on how a person will experience the product, what a
   word will mean to them, or what real usage looks like? Then owner.
3. **Tolerance-dependent?** Does it depend on how much risk or cost the owner is willing to
   carry, or on a principle the owner has stated? Then owner.
4. **Already handed back?** Was the owner asked, and did they defer it? Then craft, and a later
   disagreement is an amendment, not a defect.

## Owner categories (initial list; expected to grow as real cases show gaps)

1. **Who the product is for and what it is for.** The root the others hang from. Needs a formal,
   expected place to be documented (candidate requirement; owner leans toward configure).
2. **What the product means to a person.** The idea behind a feature.
3. **What a person sees or can do at a given moment.** Behavior on the screen. Kept separate from
   2: an idea fits one sentence, a moment needs a concrete instance to look at.
4. **Whether a thing should exist at all.** Scope, cost versus value, retiring built things.
5. **Risk tolerance and trust.** What is defended against, who may bypass, what is stored,
   privacy defaults.
6. **The owner's own time, attention, and habits.** What reaches them, how and when, and what
   agents may commit them to.
7. **A case that tests or creates a principle.** If a stated principle plainly decides it,
   craft; if the case seems to conflict with one, or no principle covers it, owner.
8. **The quality bar and what counts as proof.** Thresholds, evidence before spend, whether a
   known residual defect ships.
9. **All user-facing copy.** Agents draft; the owner approves. "User-facing" means what the
   product says to its users (for this plugin: session messages, prompts, reports, README,
   command descriptions). Instruction text agents read stays craft under the prose standard.
10. **Priority and timing.** What ships when, when to decide, how much to invest now. The shape of
    a breakdown is craft.

## Craft (always craft; agents decide, record for the owner's veto)

- Matching an approved design, or reusing an existing product pattern. If nothing approved
  covers the case, it falls back to owner category 3.
- Applying an owner-set rule to a new case (bounded by category 7).
- Bookkeeping: status or label changes when a fact changes, with no rule change.
- Pulling implementation detail out of a requirement (the remaining "what" stays owner).
- Routine size splits and the shape of a breakdown.
- How it is built: code structure and architecture.
- How it is tested. The owner keeps the right to ask pointed questions at any time; a question
  does not reclassify testing.
- Tools and libraries.
- Internal names in code.
- How errors are handled inside.
- How a speed or size target is met.
- Cleanup that changes no behavior.

**The consequence rule.** A craft choice that carries an owner consequence raises that
consequence to the owner as its own decision (a tool is craft; the new cost or outside service
it brings is a separate owner decision). The craft choice itself never flips.

## Not decisions

Misreads, self-contradiction, wrong facts, jargon in owner-facing text, and gaps a review should
have caught are errors, not decisions. They are not on the line; review catches them.

## How it interacts with what ships today

- The plugin default text for "material" (issue contract) is what this line strengthens: the
  categories, tests and craft list replace the looser "anything a plausible product preference
  could distinguish."
- Configure item 13, "Material consequence line," stays the per-project home for the owner's
  rulings (examples mined from the ruling record, both directions). That matches the fixed-line
  ruling: the line is shipped, the project's rulings accumulate beside it.
- Configure item 10, "Threat model," already documents category 5 per project. Category 1 (who
  it is for, what it is for) would be its sibling.

## What the corpus says about how these go wrong

- The failure is usually a decision never framed as one, not a wrong answer. The remedy is
  surfacing, not better guessing.
- Category 3 surfaces at the preview walk, not the spec read. The approval gate cannot catch
  these without concrete instances.
- Categories 4, 6, 7 and 8 recur across sessions (the same defaults re-proposed). A per-project
  record of rulings targets these.
- Category 9 is caught late and is expensive.

## Owner rulings log (2026-09-21 to 2026-09-27)

- The one-paragraph line: rewrite it last, from whatever survives the walk.
- Four tests: tests 1, 2 and 4 kept. Test 3 reworded: drop "attention"; it reads "depends on
  how much risk or cost the owner is willing to carry, or on a principle the owner has stated."
  Attention lives only in category 5.
- Category 1 (what the product means to a person): kept.
- Category 2 (what a person sees or can do at a given moment): kept, separate from category 1. Owner: "this one is definitely owner."
- Category 3 (whether a thing exists at all): kept.
- Category 4 (risk tolerance and trust boundaries): kept.
- Category 5 (the owner's own time, attention, and habits): kept, tentatively ("keep i think"); revisit at the final read.
- Category 6: reworded to "a case that tests or creates a principle." If a stated principle plainly decides it, craft; if the case seems to conflict with one, or no principle covers it, owner.
- Category 7 (quality bar and what counts as proof): kept, no extra line. The "owner rulings become standing rules, so later cases turn craft via test 1" point applies to every category; it goes once in the summary, not under category 7.
- Category 8: broadened to "all user-facing copy is the owner's to approve" (agents may draft; owner approves), not only coined terms. In superheroes, "user-facing" means what the plugin says to its user (session messages, prompts, reports, README, command descriptions); the instruction text agents read (skills, rubrics) stays craft under the prose standard. Plain words over jargon in owner-facing text stays craft.
- Category 9 (priority and timing): kept; drop the eight-issue decomposition example (I051, superseded by the later ruling that split and decomposition shape are the advisor's call) and state that the shape of a breakdown is craft.
- Craft list split: mistakes are not decisions and leave the line. Misreads (old craft 1), self-inconsistency and factual errors (old craft 2), and process gaps a review should have caught (old craft 8) move to a one-line note: "errors are not decisions; review catches them." The craft list keeps only real decisions the agents make themselves.
- Craft: matching an approved design or reusing an existing product pattern: kept, with the boundary that if nothing approved covers the case, it falls back to category 2 (owner).
- Craft: applying an owner-set rule to a new case: kept (bounded by category 6).
- Craft: bookkeeping (status/label flips when a fact changes, no rule change): kept.
- Craft: pulling implementation detail out of a requirement: kept (the remaining "what" stays owner).
- Jargon in owner-facing text (old craft 7): moved to the "errors are not decisions" note; it is a slip against a standing rule, not a decision.
- Craft: routine size splits: kept as craft.
- Craft calls with visible consequences (e.g. a size threshold): advisor decides, owner is shown, not asked; owner disagreement on seeing it is a new ruling, not a defect. Kept, tentatively ("probably fine"); revisit at the final read.
- Scope reframe (owner, binding): this line ships in the superheroes plugin and must scale to any
  adopting project. One line for all projects; categories and tests written generically; the
  corpus examples are illustrations only; an owner's specific preferences are that project's
  rulings, which test 1 then makes craft. The owner confirmed the recap of the discovery's
  purpose (2026-09-27): the line is groundwork for the first experiment, not the deliverable.
- Per-project adjustment: start with a fixed line; a project adjusts it only through the owner's own rulings (a handed-back kind of call becomes craft by test 4). No per-project setting for now.
- New category (owner): "who the product is for and what it is for" becomes its own category,
  the root the others hang from. Owner also wants a formal, expected place to document it,
  leaning toward configure. Carried forward as a candidate requirement (merges with the
  grounding-doc candidate in HANDOFF.md); not yet elicited or approved.
- Scope and default (owner, binding): the plugin has ONE craft/owner line. It already exists as the
  glossary's "material consequence" line (used by the advisor for merges, post-word fixes,
  deviations, follow-ups; extended per project through rulings in the configure profile). This
  work strengthens that line; it does not create a second one. Craft-by-default is REJECTED: the
  discovery began with the owner not being consulted enough. "Doubt resolves to an owner call"
  stays. Over-consultation is fixed two other ways: a fuller craft list so fewer calls land in
  doubt, and better presentation (the first experiment), not by moving the default.
- Craft list filled out (owner-approved additions): how it is built (code structure,
  architecture); how it is tested; tools and libraries; internal names in code; internal error
  handling; how a speed or size target is met; cleanup that changes no behavior.
- Framing rule (owner): craft items are ALWAYS craft; they never flip to owner. One choice can
  carry two decisions. General rule: "a craft choice that carries an owner consequence raises
  that consequence to the owner as its own decision" (e.g. a tool choice is craft; a new cost or
  outside service it brings is a separate owner decision).
- Tests (owner): craft, and the owner keeps the right to ask pointed questions at any time
  ("AI habits are pretty terrible when it comes to tests"). A question does not reclassify
  testing; what it turns up is an error for review or a quality-bar call (already owner).
- Owner list judged "good for an initial list" (answers the "anything missing?" item).
- Category 5/6 (owner's own time, attention, and habits): tentative keep confirmed as a firm keep.
- "Craft shown to the owner" bucket: DROPPED. Every craft call is already recorded for the owner's veto (glossary craft-call definition), and a real owner consequence is raised as its own decision by the consequence rule. A size threshold like the light-lane line count is a quality-bar call (owner, asked).
- Summary paragraph approved as written in "The line" above (2026-09-27, "I think that's right").
  Numbering note: rulings above use the draft's category numbers; the final list above
  renumbers with "who it is for" as category 1.
