# The owner-decision vs craft line — derived from evidence (draft, unratified)

**Status: candidate for the owner to keep / strike / reword. Not approved.** Derived 2026-09-21
from 234 real cases where a decision turned out to be the owner's: 51 post-approval spec
amendment entries (both repos) and 183 transcript moments where the owner reversed an agent's
default or raised something nobody asked. Three Sonnet labelers described each case in plain
words and judged who should own that kind of call; synthesis in the main session. Labels and
the corpus are local under `docs/research/spec-alignment-transcript-mining/line/`.

Caveats. The corpus is selected for cases where the owner *did* intervene, so the labelers'
"owner" rate (164 of 234, 70%) is biased upward. Superheroes-shaped decisions dominate by
volume (105 owner-workflow vs 56 end-user-visible), because there were more superheroes
transcripts, not because they matter more. Nothing here is measured against a control.

## The line, in one paragraph

A decision is the owner's when getting it right needs something only the owner has: how the
product should feel or what it should mean to a person using it; a fact about real usage; the
owner's risk tolerance, stated principles, or personal preferences; the owner's own time,
attention, and habits; or a judgment about whether something should exist at all given what it
costs to build and keep. A decision is craft when the right answer is derivable from what
already exists: an approved decision, a design board, a stated rule, the codebase, a checkable
fact, or ordinary correctness, consistency, and hygiene.

## Four tests (apply in order)

1. **Derivable?** Could the agent have got the answer from an approved artifact, a standing rule,
   the code, or a fact it could check? → **craft**. (Matching a board exactly, applying
   review-independence rules to a new context, flipping "awaiting" to "live", a dependency edge
   that was claimed but not wired, a factual error in prose.)
2. **Experience-dependent?** Does the answer depend on how a person will experience the product,
   what a word will mean to them, or what real usage looks like? → **owner**.
3. **Tolerance-dependent?** Does the answer depend on how much risk, cost, machinery, or
   attention the owner is willing to carry, or on a principle the owner has stated? → **owner**.
4. **Already handed back?** Was the owner asked this and did they defer it? → **craft**, and a
   later disagreement is an amendment, not a defect (matches discovery's FR-20/21).

## The owner's categories, with examples from the corpus

1. **What the product means to a person.** The mental model behind a feature.
   - Skipping a week clears its plan rather than suspending it (I174).
   - "Today" is the device's calendar date, not a server clock (I034).
   - The shopping list tracks one week at a time, not a merge of all upcoming weeks (I040).
2. **What a person sees or can do in a situation.** Behavior at the screen, especially at first
   contact. Most of these surfaced only when the owner walked a running preview.
   - A warning about a day appears only where that day is visible (I025, I203).
   - Shortening a week never silently drops a planned meal (I031).
   - Increasing a checked-off item un-checks it and shows one row (I035).
3. **Whether a thing exists at all.** Scope and cost-versus-value, including retiring built
   machinery. The single largest owner category by count.
   - No migration UI; a script, because the user base is two people (I189).
   - Kill the two-tier sharing model; one edit level is enough (I186).
   - Tear out the unused flake instrument; retire the merge-safety gate (I016, I093).
4. **Risk tolerance and trust boundaries.** What is defended against, who may bypass, what is
   stored, privacy defaults.
   - Stop defending against untrusted contributors that never materialized (I097).
   - Store no credentials for automated test waves (I041).
   - Privacy default reversed at merge time to match an earlier ruling (I166).
5. **The owner's own time, attention, and habits.** What reaches them, how, when, and what the
   agent may commit them to.
   - No issue filing without the owner's word (I047).
   - The owner manages usage pacing; never hold a lane for quota (I161, I176).
   - Notifications by email, not ntfy (I216, rejected twice).
6. **Standing principles applied to a new case.** Autonomy, no machinery in place of judgment,
   plain language, the product/craft line itself.
   - Reject a dial for classifying machinery vs product; use judgment (I099).
   - A dispatch-authority gate conflicts with the stated autonomy principle (I123).
   - The real axis is product decisions vs craft decisions, not tiers (I159).
7. **The quality bar and what counts as proof.** Thresholds, evidence before spend, whether a
   residual defect ships.
   - Clean-run threshold lowered from 30 to 10 (I005, I126).
   - Two follow-ups declined for lack of evidence the problem happens (I056).
   - Hold the merge and order a fix round rather than accept residuals (I058).
8. **Words people will read.** Product copy and coined vocabulary that lands on every future
   reader.
   - Age-confirmation copy toned down so the product doesn't feel adult (I076).
   - "Specify / Defer-to-build / Show-it" rejected as unclear names (I134).
   - "Home" overloaded across two approved specs, caught late (I142).
9. **Priority and timing.** What ships when, when to decide, how much to invest now.
   - A feature pulled into the release once its real goal was clear (I043).
   - Defer the terms document until just before go-live (I075).
   - An eight-issue decomposition rejected as too much for now (I051).

## Craft, with examples

Comprehension errors and misread instructions (I070, I205); self-inconsistency and factual
errors in prose (I130, I199, I104); matching an approved board or reusing an existing pattern
(I001, I074); applying an owner-set rule to a new instance (I226); bookkeeping flips (I011,
I017); implementation detail leaking into a requirement (I079); jargon in owner-facing text
(I103, I106; plain language is the default, not a decision); process-completeness gaps the
review should have caught (I208, I223); routine size splits (I059, later ruled the advisor's).

## What the corpus says about *how* these go wrong

- **The failure is usually a decision never framed as one, not a wrong answer.** The dominant
  pattern is a default, scope boundary, or "already ratified" framing that the owner had to
  discover by probing. The remedy is surfacing, not better guessing.
- **Category 2 surfaces at the preview, not the spec.** Nearly every product-behavior amendment
  came from walking the running thing. The approval gate cannot catch these without instances.
- **Categories 3 to 6 recur across sessions.** The same defaults get re-proposed (ntfy twice,
  quota pacing twice, guard-on-guard many times). A grounding doc of decisions and non-goals
  targets these directly.
- **Category 8 is caught late and is expensive.** Coined terms need a pass of their own.

## Open for the owner

- Keep / strike / reword each category. Are any two the same thing? Is anything missing?
- Where does the line sit for *craft calls with product consequences* (I202's line-count
  threshold; I059's split)? The corpus says the advisor owns them and shows them.
- Does the line differ between weekly-eats (product) and superheroes (workflow)? The corpus
  suggests the categories are the same and only the mix differs.
