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
