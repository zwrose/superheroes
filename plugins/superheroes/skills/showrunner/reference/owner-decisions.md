# Contents

- [The owner-decisions delivery contract](#the-owner-decisions-delivery-contract)
- [The filter — what is the owner's, and on what grounds](#the-filter--what-is-the-owners-and-on-what-grounds)
- [The per-item spine](#the-per-item-spine)
- [Follow-up economics](#follow-up-economics)
- [Delivery mechanics](#delivery-mechanics)
- [Formatting — one block per spine section](#formatting--one-block-per-spine-section)
- [Where the items come from, and the bound on that sweep](#where-the-items-come-from-and-the-bound-on-that-sweep)
- [What batch-1 execution may and may not do](#what-batch-1-execution-may-and-may-not-do)
- [The collector preamble — canonical snippet](#the-collector-preamble--canonical-snippet)

# The owner-decisions delivery contract

Open owner decisions have been dispositioned inconsistently session to session — the owner has had to
course-correct repeatedly. Across advisor sessions 2026-07 → 2026-08 the full-rigor format (context,
options, a recommendation for each) was **requested by the owner ~10+ times** rather than delivered
by default. The sharpest corrections, verbatim: *"you didn't give me nearly enough context"*; *"stop
with this 'one word' stuff, I'm not a rubber stamp"*; *"only recommend high value actions — we don't
need to file and fix every tiny bug ever"*; *"pressure test them for actual impact... make sure they
earn their keep"*; *"walk me through them in chat, do not use ask user question."* The inverse failure
also appeared — over-filtering: *"I'm a bit concerned that the collector is empty given that there
seem to be unfiled followups."* The sentence this file exists to prevent: **the owner becomes the
backstop for delivery quality on exactly the surface — decisions that are theirs to make — where the
covenant says they should never be the backstop.**

Read this file **when you are about to deliver open decisions to the owner** — it is the **shape of
that delivery**, never reconstructed from memory. Two consumers carry it: the advisor's standing duty
(showrunner duty 5 in `skills/showrunner/SKILL.md`) and the on-demand skill
`/superheroes:discuss-open-decisions`. **Nothing mechanical can gate a chat message**, so this
contract rides two read paths — the charter pointer and the collector preamble — and the honest
residual is that it is prose plus placement.

**The template is a floor, never a ceiling — most of all for context.** The per-item spine is where
a delivery's value actually lives. A batch whose context blocks read like a form has hollowed out
the one field the owner corrections named first. If the shape ever makes a walkthrough shorter than
the advisor's actual thinking, the shape is wrong and the thinking wins.

## The filter — what is the owner's, and on what grounds

Each delivered item **names why it is the owner's** — a **taste, trade, or commitment** call, never a
craft call a review lens already owns. The two tests that discriminate owner calls from craft calls
are showrunner duty 5's; cite that duty rather than restating the tests here.

**List filtered items with a one-line reason** — never swallow them. The recorded inverse failure is
over-filtering — *"I'm a bit concerned that the collector is empty given that there seem to be
unfiled followups"* — and a filter nobody can see is indistinguishable from a quiet week.

**State grounds per item, not once per batch.** A single preamble that says "these are all taste
calls" does not substitute for naming the ground on each item.

## The per-item spine

Five parts, in this order, on every item that passes the filter:

1. **Why it is yours** — the ground from the filter: which taste, trade, or commitment call this is,
   stated for this item alone.
2. **Context** — what happened, in plain language, enough that the owner does not have to reconstruct
   anything. The recorded failure here is *not nearly enough context*; the floor is that the owner can
   rule without opening another artifact.
3. **Options with consequences** — real options, one bullet each, lettered **`a`, `b`, `c`…** in
   delivery order, each carrying what it costs and what accepting it means. Two options where one is a
   straw man is one option.
4. **Cost of inaction** — what breaks or is lost if we defer this long-term, or never file it at all.
5. **Recommendation, with the why and the cost named** — name the choice by key:
   **`Recommendation: b — …`**. *"Only recommend high value actions"* is not a separate filter; it is
   how the recommendation is written.

**State empty spine sections with the reason** — never drop them. The same discipline
`skills/showrunner/reference/vet-receipt.md` insists on for an explicit `None` applies here. An
omitted section is exactly what a reader cannot interpret.

## Follow-up economics

Every proposed **filing** answers: *what breaks or is lost if we defer this long-term, or never file
it at all?* An item that cannot answer that has not earned its keep — *"pressure test them for actual
impact... make sure they earn their keep"* is the floor, not decoration.

**Decline-to-file is a first-class recommendation**, not a failure to find work. Recommend it by name
when the answer to the question above is *nothing much* — *"we don't need to file and fix every tiny
bug ever"* is permission to say no, not an excuse to omit the recommendation.

**A declined owner-named risk carries a mechanical tripwire** — when the owner has named a risk and
the recommendation is to decline, the decline ships with a mechanical trigger that would surface it
if the risk materialises, set at a threshold no looser than twice the worst observed instance. A
decline without a tripwire is a bet nobody is watching.

## Delivery mechanics

**Chat prose. Never a structured-question tool** — recorded owner instruction: *walk me through them
in chat, do not use ask user question.* The owner rules in conversation; routing that through a
question widget is the failure mode this contract names.

**Stable item numbers and option letters that never re-shuffle** across a session — item numbers and
option letters together are the ruling vocabulary: the owner rules tersely as **`1 - a, 2 - b`**. A
re-number or re-letter silently re-targets a ruling already given. Assign numbers and letters once;
carry them forward unchanged.

**Deliver batch 1 first and alone.** **Batch 1 is only what blocks the advisor's own next action**,
and **explicitly excludes new-issue filings, which are never blocking**. **Batch 2 is everything else.**
Between them the advisor **executes what batch 1 unblocked** while the owner rules on batch 2 — that
between-batch execution is the point of splitting at all, bounded by the section below.

## Formatting — one block per spine section

Separate the why-it's-yours, the context, each option, the cost of inaction, and the recommendation as
**visually distinct blocks — their own line or paragraph** — never one run-on paragraph. **A
walkthrough the owner has to re-read is the failure this whole contract exists to prevent.** (Owner
correction, 2026-08-07.)

## Where the items come from, and the bound on that sweep

**Authoritative:** the project's **standing proposals collector** — one open issue per project. Its
entries are the register; each carries what it is, the recommendation, and the proposing vet's
ordinal (see `skills/showrunner/reference/vet-receipt.md`).

**Best-effort:** open **parks** and anything pending in the session. A park is free-form prose on an
issue or PR with **no marker, label, or index**, so parks cannot be enumerated exhaustively. Reach
them from the advisor's own durable pointer and from open issues and PRs in the project.

**Say the bound in the delivered message**: the park sweep is **not exhaustive**, and the collector
is the only authoritative register. An unbounded promise reads as covered when it is not.

**Dedup rule:** an item appearing in more than one source is delivered **once**, keyed to its
collector entry where it has one.

## What batch-1 execution may and may not do

Executing what a ruling unblocked is **advisor-side work only**: writes, filings, routings, board
wiring, dispatches. It **never** includes the acts the covenant's first promise and showrunner duty
6 reserve — **merge, release, publish, force-push**. A ruling that authorizes one of those is
executed by the **owner**; the advisor's job is to make it one click, not to take the click. Read
showrunner duty 6 in `skills/showrunner/SKILL.md` for the checkpoint conditions rather than
restating them here.

## The collector preamble — canonical snippet

Place a distilled copy of this contract at the **top of the collector issue body, above the items** —
**collector reconciliation is already a mandatory vet-time step**, so the advisor cannot enumerate
items without the contract in front of them. The precedent is honest: the vet-receipt contract drifted
until it gained mechanical observability (`skills/showrunner/reference/vet-receipt.md`), and this is
the analogous move for a surface with no artifact to stamp.

Copy the snippet below verbatim into the collector issue body. Refresh it when this file changes —
the region to replace is **everything from the opening marker through the closing marker, inclusive**;
nothing below the closing marker is touched. If **both** markers are not present in the collector body,
the refresh does **not** guess a boundary — it installs a fresh preamble above the items and says so,
or reports the malformed region, rather than deleting anything.

```markdown
<!-- superheroes:owner-decisions-contract -->
**Owner-decisions delivery** — full contract: `skills/showrunner/reference/owner-decisions.md`

**Read trigger:** about to deliver open decisions → read that file first.

**Filter (duty 5):** each item names why it is the owner's (taste, trade, or commitment). Filtered,
never swallowed — failed items listed with a one-line reason; grounds per item, not per batch.

**Spine per item:** (1) why it is yours, (2) context — rule without another artifact, (3) options with
consequences (lettered a, b, c…), (4) cost of inaction, (5) recommendation by key — Recommendation: b — ….
Empty sections stated empty, never dropped.

**Follow-up economics:** filings earn their keep or get decline-to-file; declined owner-named risks
ship with a mechanical tripwire (≥2× worst observed).

**Delivery:** chat prose only — never structured-question tools; stable item numbers and option letters
(1 - a, 2 - b); batch 1 = blocks advisor next action (never new-issue filings), alone first; execute
what it unblocked; then batch 2.

**Formatting:** one block per spine section — never one run-on paragraph.
<!-- /superheroes:owner-decisions-contract -->
```
