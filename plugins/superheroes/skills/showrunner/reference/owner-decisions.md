# Contents

- [The owner-decisions delivery contract](#the-owner-decisions-delivery-contract)
- [The filter — what is the owner's, and on what grounds](#the-filter--what-is-the-owners-and-on-what-grounds)
- [The per-item spine](#the-per-item-spine)
- [The worth-it gate and the venue ladder](#the-worth-it-gate-and-the-venue-ladder)
- [The revisit-trigger registry](#the-revisit-trigger-registry)
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

**List filtered items with a one-line reason** — never swallow them. **Present filtered items in a
separate short list before batch 1** — so the owner sees disposition rather than absence. The
recorded inverse failure is over-filtering — *"I'm a bit concerned that the collector is empty given
that there seem to be unfiled followups"* — and a filter nobody can see is indistinguishable from a
quiet week.

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

## The worth-it gate and the venue ladder

A **residual** is anything a review or vet leaves behind that is not fixed in-lane — a finding, a
follow-up idea, a hardening proposal. Every residual is dispositioned through one vocabulary: the
worth-it gate, then the venue ladder.

**Every residual first passes the worth-it gate: what breaks, for whom, has it ever actually happened, and what ignoring it costs — weighed against the cost of the cheapest available venue, with observed-in-the-field evidence outweighing hypotheticals.** The **cheapest available venue** is the lowest rung of the ladder that could actually carry this item — not the venue you wish existed, but the one that fits.

**A residual that fails the gate at every venue's cost is declined with a revisit trigger — a named, mechanical re-open condition.** A **revisit trigger** is not "revisit someday" — it is a named, mechanical condition that reopens the decision when it fires. When the owner has named a risk and the recommendation is to decline, a declined owner-named risk ships with a mechanical tripwire set at a threshold no looser than twice the worst observed instance, because a decline without a tripwire is a bet nobody is watching.

**A residual that passes only at continuation cost is a ride-along — eligible for the continue and fold venues only, explicitly droppable, and never a ticket.**

**A residual that passes the gate descends the venue ladder: continue the PR, then fold into an existing issue by editing its body rather than filing a new ticket, then a new issue, bundled by shared surface before filing.**

**No target disposition mix exists: a walk where everything passes the gate, or everything fails it, is a signal to inspect the interrogation itself rather than a success in either direction.** Inspecting the interrogation means re-reading how the items were questioned — not re-scoring them.

**Tier 1 is craft — the resolution follows from already-ratified intent and no plausible product preference distinguishes the options — and the advisor executes it now and records the determination dated and reasoned for cheap owner veto; Tier 2 is product — taste, trade, or commitment — and it is the owner's word, via the collector. Doubt resolves upward.**

**Venue-3 filings are always Tier 2 — a new issue spends board attention, a commitment call by definition, even when its content is craft.**

Venue-1 continuations and craft declines are Tier 1 — the advisor executes and records for veto.
Venue-2 scope changes, product declines (any decline that trades away something a product reading
could want), and gate-uncertain items are Tier 2.

**Every Tier-2 item is appended to the collector at vet time, unconditionally, so the collector is the complete register by construction; owner attendance governs only when discussion happens — attended, the item is proposed in the vet-delivery message and may be struck minutes after it was appended; absent, it awaits the batch.**

**Each append carries its gate verdict and its venue recommendation, so the owner's batch is one word per item.**

An append made outside a vet — `/superheroes:discuss-open-decisions`, a park sitting, any non-vet
session applying these primitives — is the non-vet complement of the vet-time clause above, not an
exception to it: append-always still binds at the moment the item arises; only the stamp differs.
Such an append carries the **latest existing vet ordinal, marked non-vet** beside the stamp — that
marked ordinal stands in for the proposing vet's ordinal everywhere this contract reads one — so
age stays a subtraction over ordinals and no phantom vet is minted; before
appending, the session checks the collector for an existing entry covering the same residual and
**updates that entry in place** rather than adding a second (owner ruling 2026-08-24, recorded on
the collector —
[issue #695 comment](https://github.com/zwrose/superheroes/issues/695#issuecomment-5390859217)).
On a project with no vet yet, the append carries ordinal 0, marked non-vet — the first real vet is
ordinal 1 and the age subtraction proceeds unchanged.

Deferring the append is what two independent sessions did on 2026-08-02, and it is the evaporation
class recorded as we#526 and we#527 — items that lived only in individual receipts while the
collector read empty. That history is why append-always is unconditional; it is not a live branching
rule.

## The revisit-trigger registry

**The revisit-trigger registry is one pinned, always-current comment on the project's collector issue, one line per declined item — what was declined, the worth-it verdict, the revisit trigger, and the date with a pointer to the full record — archiving declines from both tiers.**

**The collector is the pre-ruling queue and the registry is the post-ruling archive.**

The registry comment is identified by the marker `<!-- superheroes:revisit-registry -->` placed on its
own first line. An advisor updating it **reads that comment, edits it in place, and writes it back**
— finding it by its marker rather than by position, so a project grows exactly one registry. When no
comment on the collector carries the marker, the advisor **creates one and pins it**; when more than
one does, that is a defect to repair by consolidating into the oldest rather than by adding a third.

Each registry row is one line per declined item carrying what was declined, the worth-it verdict,
the revisit trigger, and the date with a pointer to the full record. This row shape follows the ledger
family — cite-instead-of-re-arguing, and a named condition that reopens the decision — and it
assumes no `LEDGERS.md` file in a consuming project; a project that keeps a strategic ledger may
graduate rows into it, and that is optional.

Both tiers are archived here. Tier-1 craft declines land in the registry too — which is what makes
them visible and veto-able — and Tier-2 declines land after the owner's word.

Archiving a decline is two writes with no transaction — the registry row and, where the declined
item has a collector entry, its strike (a Tier-1 craft decline that never reached the collector has
only the row, which lands at determination time). The order is fixed (owner ruling 2026-08-24,
recorded on the collector —
[issue #695 comment](https://github.com/zwrose/superheroes/issues/695#issuecomment-5390859217)):
the **registry row lands first** — keyed by the item's collector number where one exists (collector
numbers are assigned once at append, written into the entry itself, and never reused, so the key is
durable across sessions), otherwise by the determination record the row points to; a writer finding
its key already in the registry updates that row rather than adding a second, which is what makes a
repeated write idempotent — and **only then
is the item struck**. A strike is an in-place tombstone edit — the entry stays legible in the
collector's record, marked struck with the ruling's date and pointer — never a deletion, which is
what keeps both halves of a half-done pair enumerable; the vet-time reconciliation read completes
the pair when it finds a row without its strike or a struck item without its row. Striking first is the fail-open order: a crash
between the writes leaves the item reading as handled while its revisit trigger is recorded nowhere
— reconciliation can flag the struck-without-row shape, but the trigger must then be re-derived from
the ruling record rather than read from the registry. Row-first fails closed and is the only order
used.

**Any session processing a field report, and any vet whose evidence includes an observed-in-the-field failure, reads the registry.**

**The registry scan is prose-bound and nothing mechanical enforces it; the registry's floor value is that whether we already declined something is one comment away.** This limit is known and carried knowingly — not a defect to be fixed later.

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
**Deliver batch 2 as soon as batch-1 rulings land** — the advisor **executes what batch 1 unblocked
alongside** the owner's batch-2 rulings, not ahead of them. That overlap is why the split exists at
all, bounded by the section below.

**State an empty batch plainly** — so the owner can tell "nothing is waiting on you" from "the sweep
failed."

## Formatting — one block per spine section

Separate the why-it's-yours, the context, each option, the cost of inaction, and the recommendation as
**visually distinct blocks — their own line or paragraph** — never one run-on paragraph. **A
walkthrough the owner has to re-read is the failure this whole contract exists to prevent.** (Owner
correction, 2026-08-07.)

## Where the items come from, and the bound on that sweep

**Authoritative:** the project's **standing proposals collector** — one open issue per project. Its
entries are the register; each carries what it is, the recommendation, and the proposing vet's
ordinal (see `skills/showrunner/reference/vet-receipt.md`).

**Best-effort:** open **parks** and anything **pending in the session** — decisions raised but not yet
delivered, and decisions delivered in a prior turn that are still awaiting a ruling. A park is
free-form prose on an issue or PR with **no marker, label, or index**, so parks cannot be enumerated
exhaustively. Reach them from the advisor's own durable pointer and from open issues and PRs in the
project.

**Say the bound in the delivered message**: state what was actually searched (collector, which open
issues/PRs, durable pointers), and that the park sweep is **not exhaustive** — the collector is the
only authoritative register. An unbounded promise reads as covered when it is not.

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
never swallowed — separate short list before batch 1 with a one-line reason each; grounds per item,
not per batch.

**Spine per item:** (1) why it is yours, (2) context — rule without another artifact, (3) options with
consequences (lettered a, b, c…), (4) cost of inaction, (5) recommendation by key, with the why and
the cost named — Recommendation: b — …. Empty sections stated empty, never dropped.

**Residual disposition:** worth-it gate (what breaks / for whom / has it happened / cost of ignoring,
vs cheapest venue) → venue ladder (continue → fold → file, bundled by surface); decline with a
revisit trigger when every venue fails the gate.
**Tier:** Tier 1 craft — advisor executes and records for veto; Tier 2 product — owner's word;
filings always Tier 2; doubt upward.
**Append-always at vet:** every Tier-2 item to the collector with gate verdict and venue on each
append.
**Registry:** `<!-- superheroes:revisit-registry -->` — one pinned comment, one line per declined
item.

**Delivery:** chat prose only — never structured-question tools; stable item numbers and option letters
(1 - a, 2 - b); batch 1 = blocks advisor next action (never new-issue filings), alone first; as soon
as batch-1 rulings land, deliver batch 2 while executing what batch 1 unblocked alongside; state empty
batches plainly.

**Formatting:** one block per spine section — never one run-on paragraph.
<!-- /superheroes:owner-decisions-contract -->
```
