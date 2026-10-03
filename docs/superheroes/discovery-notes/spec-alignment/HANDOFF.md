# Discovery handoff — reimagining how we define and align on work

**Status: discovery in progress. Nothing here is approved.** These are elicitation notes and
research outputs from a web session on 2026-09-21, written so the discovery can continue in a
local session with the owner's transcript archive available. No work-item has been minted, no
spec drafted, no framing approved. Nothing downstream may anchor to this file.

This folder is a temporary home on the feature branch `claude/dazzling-hypatia-awbs3k`. When the
discovery mints a work-item, move what survives into that work-item's folder and delete this one.

## The idea, in the owner's words (paraphrased closely)

Specs as written today are a challenging medium to consume reliably. They carry a lot of detail,
which is good ("if the details aren't specified, builders will assume"), but they are so dense
that the owner cannot afford the attention to read them in detail. Text is a slow, expensive
medium. The owner wants a new way to define and align on work. Hunches at the start: it will be
more visual (especially for UI, probably always), and it will break definition into smaller
components.

Owner corrections during the session (binding on how the problem is framed):

- Do **not** plan for "an owner who can't afford attention." All humans can hold only so much
  context at once; that is the constraint, not the owner's budget.
- The hard problem: **alignment on what to build is now the bottleneck**, because agents can run
  the build and its verification effectively *if the up-front definition is sufficiently
  detailed*. (Owner flagged this as an assumption worth testing; research below tests it.)

## What was elicited

1. **What the spec read is for.** All three of: checking it captured what the owner said;
   catching decisions made on their behalf they'd disagree with; spotting things nobody asked.
   The second and third matter most. By the end of the review-spec loop the owner is not
   confident that something didn't get lost from original intent through the edits.
2. **Shape of the loss.** Both kinds occur: individual sentences still true but the gestalt
   drifted (definitely happens), and the actual words of a decision changed (owner worries about
   it). Not sure which dominates.
3. **Where confidence has felt real.** In weekly-eats: reviewing design boards. But the pipeline
   boards → spec words → implementation has been "full of unhappy surprises." Grounding in
   specific use cases (via an "eli5" skill) has helped. On the superheroes project (no UI) the
   owner has never felt very confident in what is being aligned on up front, and it gets worse as
   development progresses.
4. **Non-UI instance form.** Owner is not sure what will work; said it probably needs research
   and experimentation. Research consented and run (below).
5. **The framing gate (discovery step 5) is fine as is.** In practice it is a single-digit
   percentage of the reviewed spec. Not where the pain is.
6. **Visual is not dropped.** After the research readout the owner is "not quite ready to let the
   visual vs text thing go": one problem to solve is speed/density of *many things at once*. The
   studies did not test that case (see research).
7. **More "why".** Owner asked whether giving agents more of the why (target user, purpose, the
   things humans use to align with each other) would help them make the right decisions. A light
   research pass was consented and run (see `rationale_grounding_for_builders.md` if present).
8. **New data source.** The owner's local machine holds many session transcripts of working with
   specs and advisors on both superheroes and weekly-eats. The owner wants to use that data in
   this discovery. That is the reason for the handoff.

## Provenance idea (raised by the assistant, owner pushed back, still open)

The assistant proposed that the spec distinguish which lines came from the owner versus were
inferred by the author or changed by review, so the owner reads only the inferred lines. The
owner's reaction: "that sounds like even more information to parse." The assistant's reply: it is a
filter, not a layer. The research (Volere's Originator field; example mapping's "Is that how I
would have written it?") supports the mechanism. **Unresolved; owner has not accepted it.**

## Research run and its headline

Five-researcher deep pass (Opus researchers, Fable writer), report at `Aligning on what to
build.md` beside this file. Notes are gitignored under `docs/research/` on the web container and
did not travel; the report carries an evidence-tier ledger.

Headlines that changed the assistant's thinking:

- The "visuals are denser" premise does **not** hold in general: untrained readers do as well or
  better with text than with process diagrams (three studies). Visuals help as a
  semantically-transparent map integrated with text, used for structure and search. The "many
  things at once" case was not tested by any study; Larkin & Simon's theory predicts diagrams
  help exactly there. Boards lose *behavior*, not appearance; visual review passes builds that
  look right and behave wrong.
- Instance-first techniques (example mapping, domain storytelling, spec-by-example) converge on
  one mechanism: **re-present the derived artifact to the originator as something concrete and
  ask for disagreement.** No controlled study compares instances to prose.
- The owner's assumption: first half holds with "detailed" corrected to "structurally redundant"
  (prose + examples + check; volume can hurt). Second half contradicted: agents do not choose
  appropriate validation unprompted and, given a check, build to it and shed the rest.
  Independent review of the built thing is load-bearing. Reframe: *someone is the oracle; how
  much of it is executable?*
- Granularity: the unit is one sitting, not a count. Keep a coarse map in view; derive small
  pieces from it, never replace it with pieces. Agent-era workflows converge on a two-level
  artifact (durable "what and why" + generated disposable steps).
- Biggest gap and opportunity: nobody has evaluated **agent-generated worked instances from a
  definition so the owner checks instances instead of rules.** Caveat: instances of what was
  *built* must come from running the system, not agent narration.

## Light pass on "why" grounding (headline)

Notes at `rationale_grounding_for_builders.md` beside this file. A product-level grounding doc
is a reasonable bet with a plausible mechanism and no direct disconfirming evidence, but nobody
has measured it independently. One controlled study on human builders (Falessi et al. 2006,
unverified raw read) found design rationale improved decision correctness when requirements
changed. Personas measurably change designers' beliefs, not demonstrably what gets built. For
agents, the rigorous study (context files on SWE-bench-style tasks) found no resolution gain and
20%+ cost, but its tasks were precisely specified, the opposite of the case here; its actionable
finding is that **specific instructions in context files are followed and narrative overviews
are not**. The one study that tests the hypothesis directly is vendor-authored with no spec-only
baseline. Design constraint that falls out: a grounding doc written as decisions, constraints and
non-goals lands; one written as narrative background is the failure mode. Nobody has run the
obvious natural experiment (same specs, grounding on vs off, scored on choices the spec left
open); this workflow could run a cheap version of it.

## Current direction (assistant's proposal, not owner-approved)

The first piece is an **experiment, not a new spec format**: add an instance-based check at the
**spec approval gate** (discovery step 8) on one real spec, and see whether it catches things
the prose read missed. Cheap test: generate instances from an already-approved spec (e.g. the
730-line front-half SDLC core spec) and see whether the owner disagrees with any.

Candidate requirements surfaced but not yet elicited or approved:

- A first-class "needs clarification" object the author must write instead of choosing a default.
- A product-level grounding doc (purpose, target user, principles, non-goals) routed to every
  builder and reviewer. This repo has PHILOSOPHY.md but the builder skill never references it;
  weekly-eats likely has nothing.
- A provenance filter (see above; owner has not accepted).
- A coarse visual map of the spec, integrated with the text, for the many-things-at-once case.

## Repo facts gathered

- Spec template: `plugins/superheroes/templates/spec.md` (EARS rules + acceptance criteria,
  unhappy paths, non-functionals, UI section pointing at Claude Design output, 15-row coverage
  table with Disposition and Show-it? columns). Real specs run 201, 356, 730 lines.
- Discovery skill: `plugins/superheroes/skills/architect-discovery/SKILL.md` (interview-style
  elicitation, step-5 decision brief, step-8 full read).
- PHILOSOPHY.md bet B2: "plain language can carry the contract," re-check condition = builds
  where the spec was followed and the owner still didn't get what they meant. This discovery is
  partly a B2 re-check.

## Next steps when resumed locally

1. Read this file and the report.
2. Read the owner's local transcripts of spec/advisor sessions (superheroes and weekly-eats) with
   the owner's consent on scope, looking for: where drift entered, what the owner pushed back on
   at step 8, what defaults were chosen silently, what the "unhappy surprises" in weekly-eats
   were.
3. Resume the requirements dialogue (one question at a time) toward a framing for the experiment.
4. Run the discovery's coverage checklist before the framing gate.

## Session 2 (2026-09-21, local, desktop app, instance -four) — transcript mining and the line

**Owner corrections to the transcript-mining readout (binding):**
- The owner DOES approve specs without meaningfully reading them: "most of the last few specs
  i've approved i did not meaningfully read, i trusted the review loop process and the starting
  point of the design boards, because they were too dense to read thoroughly." The readers'
  "no rubber-stamps" finding was a method error (they looked for short replies; the approvals
  look engaged in transcript because discussion is present, but the reading was not).
- Spec text draws fewer pushbacks probably because advisor chat presents a few concerns at a
  time, not because specs are better.
- The split the owner wants is owner decisions vs craft, but "with specs it is much less clear
  to me what this line actually is" and he cannot articulate it from whole cloth.
- The Sep 6–7 before/after-by-feature-area format "felt ok at best"; he has no sense of how well
  those artifacts track the dense underlying specs, and by definition does not know what is
  lurking in them that he disagrees with. Unlike weekly-eats, on superheroes he has less ability
  to notice and call foul because of subject matter vs expertise.
- Too-terse is a real limit but the rare direction; the "one word" complaints were about zero
  context.
- Jargon and requirement numbers hurt as much as length: agreed.
- Instances help only when they look real: agreed.
- Design-intent-lost-in-build is real but a different issue from spec amendments.
- The "three shapes" of missing context read as superheroes-only.

**Amendment volume (checked):** weekly-eats verification-strategy spec: 18 numbered amendments
plus two full re-reads since Aug 28 approval (mostly process churn; the "guards guarding guards"
spec). Four weekly-eats product specs approved Sep 6: 7, 7, 4, 4 amendments each, nearly all
ruled "during the owner's walk of the preview". Superheroes front-half core: 7. The approval gate
is the wrong place to expect disagreements to surface; they surface at first contact with the
running thing, and the amendments log is the receipt.

**Derived line:** see `OWNER-VS-CRAFT-LINE.md` beside this file (unratified; owner to keep /
strike / reword). Corpus and labels are local under
`docs/research/spec-alignment-transcript-mining/line/`.

**Practitioner signal the owner flagged:** a Claude Code team member's post, "I now type 'use
big pictures and few words' several times a day" (Sep 21). Matches the mixed-media finding.

**Local-only research outputs (gitignored, this Mac, any instance can read):**
- `docs/research/spec-alignment-transcript-mining/SYNTHESIS.md` (needs the corrections above
  applied; the rubber-stamp finding there is wrong)
- `docs/research/spec-alignment-transcript-mining/findings/b0..b10.md` (per-bundle moments with
  verbatim quotes, session ids, timestamps)
- `docs/research/spec-alignment-transcript-mining/{BRIEF.md,index.py,extract.py}` (re-runnable)
- `docs/research/spec-alignment-transcript-mining/line/` (the 234-item corpus and labels)
- `docs/research/research_notes/Aligning on what to build/` was on the WEB container only and
  did not travel; the report did (beside this file).

## Next steps (updated)

1. Owner rules on `OWNER-VS-CRAFT-LINE.md`: keep / strike / reword categories, in chat prose.
2. Then resume the requirements dialogue toward a framing for the first experiment, which now
   looks like: at the approval gate, an owner-decisions-only walk grouped by area, one concrete
   instance per decision, craft collapsed, plain words, "not sure" allowed; plus a way to find
   what is lurking in dense specs the owner did not read (candidate: generate instances from the
   approved spec and let the owner disagree).
3. Candidate requirement carried forward: a product-level grounding doc written as decisions,
   constraints and non-goals (not narrative), routed to builders and reviewers.
4. Run the discovery coverage checklist before the framing gate.

## Session 3 (2026-09-21 to 2026-09-28, local, instance -three)

**The owner-vs-craft line is ratified** item by item in chat; see `OWNER-VS-CRAFT-LINE.md` (clean
version plus the full rulings log). Binding frame from that walk: this ships in the superheroes
plugin for any adopting project, and it strengthens the plugin's existing material-consequence
line rather than adding a second one. "Doubt goes to the owner" stays.

**Direction question left open when the owner went to bed (09-28):** make the spec itself
reviewable, or stop needing the owner to read it? The owner's worry: a walk written about the
spec is a translation, and things get lost in translation.

**New input the owner asked to be studied: two weekly-eats discoveries** run in parallel,
09-25 to 09-28 (#1798 "Need beyond Plans"; #1419 legal terms, Specs A and C), plus the
advisor seats that vetted their spec PRs. Both converged, independently, on the same practice:

1. Rulings one at a time in chat, then **design before spec**: most product rulings made by
   looking at drawn frames; the board approved before any spec text is written.
2. **The board is the owner's truth; the spec is a second copy.** The owner's framing, the same
   in both sessions: confidence the spec doesn't contradict the board, plus a look at only what
   the board can't show.
3. **A tap sheet, not a document:** Aligned / Discuss, a note, a verdict, on a phone. Each round
   carries only what is unruled or changed, and rounds shrank fast.
4. **Draw everything drawable.** Drawing the rules the board didn't show caught gaps that two
   text-only review loops had missed.
5. **A traceability audit before approval** (the owner asked the same first-principles question
   in both sessions): every spec statement traced to a frame, a ruling, a confirmed default or a
   review answer; untraced statements split into owner decisions and craft; only the owner
   decisions go to the owner. Rules now carry their source tag. This is the provenance filter
   from session 1, working as a filter the owner never reads.
6. **The owner applied the ratified line to review itself:** checking that each ruling was
   written down correctly is agent craft; only the unruled remainder is his.
7. **Adversarial review rounds added product rules nobody ruled on**; the owner cut most of them
   when they were shown plainly.
8. **The advisor's vet** (against the repo and decisions ratified in other specs) found a class
   of conflict the discovery's own checks could not; both sessions concluded the vet should come
   before the owner's approval.
9. Failure modes worth requirements: the spec contradicting the approved board after its own
   review converged; summary cards silently covering detail; stale cards repeating overturned
   rulings; rulings recorded only in chat; "approved" ambiguous between board and spec.

**Private records (quote owner sessions; never commit):**
`~/.claude/wave-logs/spec-alignment-discovery/sessions-study-SYNTHESIS.md` (the synthesis and
open questions) and `sessions-study-NOTES.md` beside it; the two discoveries' own records at
`~/.claude/wave-logs/discovery-1798/` and `~/.claude/wave-logs/discovery-1419-record/`.

## Next steps (updated 2026-09-28)

1. Readout of the two-session study to the owner, then resume the one-question-at-a-time
   dialogue toward a framing. The first question: what the "board" is for a project with no UI.
2. Remaining open questions, in the synthesis file: the order of vet and approval; what
   adversarial review may add; the scope of the first work item; cost per spec.
3. Still owed before the framing gate: the discovery coverage checklist.

## Session 3 elicitation (2026-09-28, unapproved notes)

1. **What the "board" is when there's no UI** (owner): any visualization that helps communicate
   the concept. Storyboards of what the user experiences, flow charts and other diagrams all
   count. Open: whether Claude Design is needed for these, or plain HTML artifacts do.
2. **Medium** (owner): every board is drawn and reviewed as an HTML artifact, carrying the design
   system files along. Claude Design is a review repository only: the design system still comes
   from it, and approved boards sync to it once, at approval.
3. **What the plugin ships** (owner, "perfect"): the approved board's permanent record is a file the
   project controls, kept with its specs. Syncing to Claude Design is optional, for projects that
   have it (Codex hosts and other owners may not); the owner's projects turn it on.
4. **Vet before approval** (owner): yes, but the workflow must feel natural. Discovery drives toward
   the owner agreeing the spec is *ready for vet*, not toward approval.
5. **Candidate requirement, raised by the owner:** discovery sessions don't understand the whole
   SDLC; they often assume they will decompose issues and wire the board, which is the advisor's
   work. Fix it as part of this discovery: discovery should know where it hands off.
6. **The tail end** (owner): ready for vet, then the advisor's vet (craft fixed by the advisor,
   owner calls sent back), then one last tap sheet holding any vet owner calls with approval as
   its final card. Approval and the merge word stay separate acts, as today.
7. **What adversarial review may add** (owner): the reviewer finds gaps and contradictions but does
   not add product behaviour. A fix that would add behaviour goes on the owner's remainder sheet
   with a recommendation. The recommendation is NOT biased toward cutting: each finding is weighed
   on its merits and against the project's context. Fixes that change no behaviour (wording,
   consistency) are applied as craft.
8. **The end-to-end flow** (owner: "im aligned to this flow"): A start (intake; ground in the
   who-it's-for home, the ruling ledger, sibling specs and their boards, the as-built product;
   scope check; consented investigation) → B understand (one question at a time, owner-category
   only, craft recorded for veto, each ruling into the ledger; framing) → C visualize (journeys or
   flows first, then open choices side by side, in HTML artifacts; build board approved) → D write
   and check, agents only (spec from board and rulings with source tags; reviewer finds but does
   not add; spec-vs-board conformance, board wins; traceability sorting untraced statements into
   owner vs craft; writing standard) → E tap sheets of the unruled remainder until empty, then
   "ready for vet" → F spec PR, advisor vet, final tap sheet with approval as its last card, merge
   word separate → G advisor decomposes, files, wires the board; discovery never does.
9. **Shape of the work** (owner): durable artifacts for all four pieces (the line, the who-it's-for
   home, the discovery flow, the ruling ledger) in ONE new-style spec.
10. **Framing feedback** (owner, 09-28):
    - A project with no "who it's for / what it's for" yet: discovery strongly recommends setting it
      up with the advisor before proceeding (a strong recommendation, not a silent default).
    - The ruling ledger and source tags + traceability: agreed in concept, with a binding
      constraint: no complex or overbuilt machinery.
    - Asked: what is the future of review-spec in this flow? (open)
11. **review-spec** (owner): fine to retire the separate callable skill. The shape of the review
    cycle is to be defined with the owner up front, in this discovery.
12. **Review cycle, part 1 (checks)** (owner): gap review is one check; board match, traceability
    and faithfulness combine into one source check run in both directions (spec statement to
    source; ruling or frame to spec). Pending: whether the retired skill's other lenses are covered.
13. **Candidate requirement, raised by the owner:** avoid very long specs. Length is a trigger to
    split a spec, with a heuristic for splitting specs the way the plugin now splits work into
    stacks.
14. **Review cycle, part 1 (lenses), locked** (owner, "lock those three in"): three checks.
    - **Gap review:** clarity, testability, failure modes, contradictions, plus safety and access.
    - **Source check, both directions:** board match, traceability, faithfulness, plus scope (is it
      one piece; is anything in it not this piece's, or not sourced).
    - **Grounding:** claims about the repo checked against the repo, as its own third lens in
      discovery (not left to the advisor's vet); the existing citation script keeps running.
    The advisor's vet can lean on the grounding check and focus on conflicts with other approved
    specs.
15. **Review cycle, part 2 (who reviews)** (owner): each check is an independent reviewer from a
    different model family than the author, the three in parallel, the same reviewer continuing
    across rounds (confirms last round's fixes, then looks for new problems). The spec reviewer
    is its own configurable tier, separate from the code-review tiers (the owner's setup: Astra
    for specs, Sol still the deep-tier code reviewer). No model is hardcoded in the plugin.
16. **Review cycle, parts 3-4 (rounds; who fixes)** (owner: the walkthrough "generally seems ok";
    declines "that works"): rounds run automatically, no owner go-ahead between rounds, until all
    three checks are clean apart from items already in the owner's queue, or a cap of 4 rounds;
    findings still open at the cap join the owner's queue marked unsettled. Each finding goes to
    one of three piles: craft (discovery fixes it); the owner's (a fix that adds behaviour, an
    unsourced product decision, two conflicting rulings; left open and queued); or declined.
    A decline is allowed only for five reasons, each citing its proof: the finding is wrong
    (spec line), outside the threat model (entry), asks for implementation, belongs to another
    spec, or duplicates a queued item. A decline the reviewer still contests next round goes to
    the owner's queue. Every decline is listed, folded away, on the final sheet. After each set
    of owner rulings the three checks re-run on the changed parts.
17. **Review cycle, part 5 (progress visibility):** handed back to the build as craft (owner: "do we
    even need to specify anything here?"). The owner-relevant parts are already settled.
18. **FRAMING APPROVED** (owner, 2026-09-28: "approved, start the board"). The framing brief as
    presented, plus the changes in items 10-17. Cost note given: three reviewers for up to four
    rounds plus drawing agents per spec, traded for less owner time and fewer late vet findings.
    Next: this work's own board, drawn per the new flow (HTML artifact), then the spec from it.
19. **This work's board, drawn** (2026-09-28): https://claude.ai/artifact/FDiMfa95mWjEPCaT64d5pf
    (Design-type HTML artifact on the -three account). Eight artboards: start here, the flow,
    the review cycle, the owner-vs-craft line, two tap-sheet mocks, source tags and the ledger,
    and the plugin's moments drawn as conversation. Not yet approved. Local source:
    this session's scratchpad `board/project/` (copy it into the record at approval).
    Open for the owner: the spec-split trigger.

## Board round 1 comments (2026-09-29) and rulings (2026-10-03)

Owner comments on the board: the flow should be a real flow chart; the review cycle should
illustrate the process; "drawn as the conversation" wasn't useful; the line artboard was a
*less* detailed view than chat ("visuals should never be"), needs real descriptions, examples
and applied examples; tap sheets should be drawn as a light web app; a superheroes visual theme
should ship with the plugin for these artifacts.

Rulings (owner agreed with every recommendation, 2026-10-03):
20. Draw two or three superheroes theme directions; the owner picks one; the plugin ships it.
21. Category 1 stays project level (who the product is for and what it's for). Category 2
    becomes the per-piece user context: who this feature is for and what they're trying to do,
    captured in each discovery.
22. The separate four tests go. The line reads: if something approved, a standing rule, the
    code or a checkable fact already answers it, or the owner handed it back, it's craft; if it
    touches any of the ten categories, it's the owner's; in doubt, the owner's.
23. Scope: a light check at intake for obvious bundles; the real split check when the spec is
    written (the length trigger and the source check's "is this one piece").
24. The writing standard runs as a late pass, after the review rounds converge and before the
    owner's sheet, followed by a check that no meaning shifted.
25. The advisor's vet never fixes: it sends everything back to the discovery session, which
    fixes, then the advisor re-vets.
26. One PR: after approval the advisor adds the breakdown to the same spec PR and vets it; one
    merge word covers both; issues are filed, with the owner's word, as it merges.

Owner feedback on the round (binding on method): "none of those were really rulings or
recommendations." When an owner's comment already states the direction and the recommendation
only agrees, act on it and report; ask only about real choices.
27. **Board round 2 published** (2026-10-03, same link): flow as a four-lane flow chart; review
    cycle drawn as the process; the line in full (descriptions, real examples, sorting diagram,
    worked examples, how a project adjusts it); tap sheets as a light web app on phone and
    desktop; three theme directions (A field notes, B mission control, C comic panel); the
    conversation artboard removed. Durable source copy: `~/.claude/wave-logs/spec-alignment-discovery/board-v2/`.
    Open for the owner: the theme pick, and the spec-split trigger.

## Board round 2 comments (2026-10-03)

Owner: "really happy with this iteration ... converging." Directions taken from the comments:
28. **Theme: C, comic panel** ("let's start bold"; another theme can be added later).
29. **The final sheet comes from the discovery session**, not the advisor: the vet's findings go
    back to discovery, and discovery sends the owner's final sheet.
30. **Category 2 is written as user stories** ("As a X, I want to Y, so I can Z"), evocative of
    the core need, not comprehensive; the requirements carry the detail. Examples lead with a
    core story (#1798), not an edge case (#1419 account deletion was a poor example).
31. **Tap sheets are a reusable review template.** Spec review uses it, built in. Any plugin
    session can use it for another review (a PR walk, a merge review) when the owner asks; no
    other standing use is built in. Standing rule: when a decision has relevant images, the card
    includes them, and they can be tapped to zoom, especially on a phone.

    Amended (owner): not limited to when the owner asks; any session may reach for it. What is
    not formalized yet is any other case where it is *expected* to be used, beyond specs and
    discovery.
32. **Principles live in the ledger** as standing rulings (a ruling marked to apply to future
    work). The threat model is not migrated now; the downstream review-overhaul discovery
    should consider moving some of review's inputs into the ledger. **The ledger gets a new,
    more evocative name** (open).
33. **Source tags cite no transcript lines.** A ledger entry carries the owner's exact words plus
    the session id and time as a lookup pointer (owner: "ok").
34. **One card shape for every review** using the template: context, images, options,
    recommendation, note; Aligned and Discuss always; a direct pick when the card has options; no
    per-review buttons (owner: "ok").

35. **The ledger is named Canon** (owner: "i like canon"; plain "Canon" approved with "go"): one
    per project, `canon.md` at the project's superheroes root; docs say "the project's canon" where needed.
36. **Spec-split trigger** (owner): the main trigger is one piece the owner could approve and ship
    on its own (roughly one cluster of user stories); a second piece found while writing →
    discovery proposes the split, the owner rules. Length is not a hard stop: around 300-400
    lines, discovery raises a conversation about splitting.

Board round 3 under way (owner: "go").
37. **Board round 3 published** (2026-10-03, same link): everything restyled in theme C; the theme
    artboard is now the theme spec (colours with one job each, type, parts, readability rules);
    new artboards: one review template (card anatomy, who uses it, a PR-walk example) and image
    zoom on a phone; discovery sends the final sheet; category 2 told as #1798 user stories;
    Canon replaces the ledger (standing vs this-piece entries, exact words, session pointer;
    threat model stays in configure); split trigger on the flow. Craft call recorded for veto:
    hand-backs live in Canon and configure item 13 points there. Durable source copy:
    `~/.claude/wave-logs/spec-alignment-discovery/board-v3/`. Next: the owner approves the board
    (or comments), then the spec is written from it.
38. **No image carousel** (owner, board comment): the zoom view has no swipe-to-next; sideways
    swipes could conflict with dragging a zoomed image. Each image opens on its own; Close returns
    to the card.
39. **BOARD APPROVED** (owner, 2026-10-03: "ok i think i'm aligned to the board!"), round 3 as
    published plus ruling 38, including the craft call shown on its start page (hand-backs in
    Canon, configure item 13 points there). The spec is written from this board and rulings 1-39.
40. **Two specs** (owner: "good with the split"): (a) the alignment flow: the owner-vs-craft line,
    who-it's-for, Canon, the discovery flow and the review cycle; (b) the review surface: the
    comic-panel theme, the shared review template, image zoom. (a) references (b).
41. **Consent for the review rounds** (owner: "yep, go"): the three checks run automatically, up
    to 4 rounds per spec, by Astra called directly (the configure seat doesn't exist yet), on
    the owner's Codex usage. Source tags cite this file's ruling numbers until Canon exists.

## Spec writing (2026-10-03)

- Specs drafted from the approved board and rulings 1-41, at the paths the resolver gives (this
  project stores specs out of repo): `aligning-on-what-to-build-6da1ee` (large, ~400 lines) and
  `the-review-surface-d59417` (medium, ~210 lines), both `status: draft`. Citation check clean.
- Review round 1 launched: three Astra checks (gap, source both directions, grounding), each
  reviewing both specs. Prompts and results: `~/.claude/wave-logs/spec-alignment-discovery/review/`.
- Author's open items for the owner, carried in the specs: no cross-family spec reviewer
  configured; the fate of the weight call; review-surface UFR-2 (failed save) and UFR-3 (missing
  image).
- Review rounds (Astra, same three sessions resumed each round): round 1, 29 findings (9 gap,
  18 source, 2 grounding), 21 fixed as craft and 7 queued for the owner; round 2, 10 findings, all
  craft; round 3, 4 findings, all craft; round 4, all three checks clean. No declines.
- Writing pass (prose standard): 5 word-level edits; independent meaning check found 0 shifts.
- Owner's remainder queue (each spec's "Open questions"): A: no cross-family reviewer; the weight
  call; final-sheet answers that change the spec; a later ruling vs the approved board; the round
  cap after owner rulings; specs stored out of repo. B: what each answer means; changing an
  answer; who may open a sheet; UFR-2 failed save and UFR-3 missing image (author-added).
- Remainder sheet 1 sent (2026-10-03): https://claude.ai/artifact/9F53AdK2FdPpaTddgEkpXn, 11
  cards (A: a1-a6, B: b1-b5), answers saved to the sheet's store collection `answers`, one doc per
  card. Source: scratchpad `remainder-sheet-1.html`.
