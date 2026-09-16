# Contents

- [The owner-decisions delivery contract](#the-owner-decisions-delivery-contract)
- [The filter — what is the owner's, and on what grounds](#the-filter--what-is-the-owners-and-on-what-grounds)
- [The per-item spine](#the-per-item-spine)
- [The front door](#the-front-door)
- [The grid and its two instruments](#the-grid-and-its-two-instruments)
- [The tiers and the P2 carve-out](#the-tiers-and-the-p2-carve-out)
- [Every grading keeps its scoring, and the misses log](#every-grading-keeps-its-scoring-and-the-misses-log)
- [The declined registry and its triggers](#the-declined-registry-and-its-triggers)
- [The launch door](#the-launch-door)
- [Folding backlog items in](#folding-backlog-items-in)
- [The reader clause](#the-reader-clause)
- [The venue ladder](#the-venue-ladder)
- [Craft calls and owner calls](#craft-calls-and-owner-calls)
- [The revisit-trigger registry](#the-revisit-trigger-registry)
- [The gardening pass](#the-gardening-pass)
- [The gardening record](#the-gardening-record)
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

## The front door

Intake runs through one door for machinery work and product work alike. The door grades every
proposed item before it reaches the board.

**Two branches, one test at entry.** The door classifies every item at entry as machinery or product,
by the same test the [dial](../../../rubric/glossary.md#dial) uses. **Machinery** work takes the
evidence bar below. **Product** work does not. Product work enters by the owner's ratification of a
milestone or an epic, and its discovery needs no reproduced defect. A product item not yet under a
ratified milestone waits on the [collector](../../../rubric/glossary.md#collector) for the owner's
word. The bar bites where maintenance work grows, and a door that made product ideas impersonate
defects would be a funnel for exactly that. The machinery-or-product classification test lives in
[issue-contract.md](issue-contract.md).

**The evidence bar.** The door admits a proposed machinery item to the board only on **executed
evidence**. The failure or the need was **made to happen**, in the field or in the lab, on a
surface that is **live today**.

- "Made to happen" means it broke in the field, or it was reproduced or probed in the lab.
  "Argued it could happen" and "might drift someday" fail the bar.
- **Lab evidence counts by design.** A field-only bar silently declines the hole that no user has
  hit yet and that a lab reproduction found.

**Live and dark surfaces.** A surface is **live** when it has at least one shipped consumer today.
A shipped code path a shipped caller invokes counts. A document a real reader loads counts. A
standing process that actually runs counts. A surface is **dark** when it has zero shipped
consumers. Shipped but never invoked is dark. Gated off is dark. Reachable only from its own tests
is dark. Planned is dark. **Dark and future surfaces fail the bar whatever the evidence quality.**

**No severity thumb on the bar.** Every item needs executed evidence whatever severity is claimed. A
dangerous direction earns its weight in the grid's ranking, and only by citing a named band on the
ladder, never by argument.

**An item that fails the bar is declined with a trigger, never silently dropped.** See [The declined
registry and its triggers](#the-declined-registry-and-its-triggers).

**In-envelope variance is not defect evidence.** A filing must show that the **hard shell** was
breached, or, only where the surface's own declaration states a **quantified bound** on an interior
behavior such as a declared round-count range, that the bound was exceeded. Absent a stated bound,
interior variance is never defect evidence, and a demand for determinism on the soft interior is
declined with a trigger by default.

## The grid and its two instruments

1. Scoring runs on a **two-axis grid**. **Impact** comes from the project's severity ladder.
   **Urgency** comes from the evidence tier. Both axes grade from facts the intake already
   collects.
2. **The impact instrument.** The severity ladder is a closed, owner-stamped list of named bands
   with concrete examples in the project's own words. Claiming a band means citing a named entry
   the ladder actually contains. Prose arguing that something is "kind of critical" claims nothing.
   Adding an entry is the owner's edit. **The ladder is the only scoring instrument for severity.**
3. **The urgency instrument.** Urgency is the **evidence tier**. The tiers are lab-only,
   field-once, or field-recurrent, read directly off the evidence the bar already required. Nothing
   adjusts it.
4. **Two instruments and no third.** The grid stays two axes and a slot count. The failure mode is
   the framework acquiring machinery of its own, so any proposal to instrument the grid routes
   through the door like anything else and starts life suspect.
5. **The regions of the grid.** A project's ladder renames the bands while the region shape is the
   plugin's.

   | Impact, down / evidence, across | lab-only | field, once | field, recurrent |
   |---|---|---|---|
   | Top band, for example users harmed or misled | P1 | P0 | P0 |
   | Middle band, for example users see breakage | P2 | P1 | P1 |
   | Bottom band, for example internal quality | P2 | P2 | P2 |

   The top-band lab-only cell is deliberately **P1**, so a reproduced hole in a dangerous surface
   reaches the owner in the next batch instead of filing silently.
6. What each tier commits to is not stated here. See [issue-contract.md](issue-contract.md).
7. **The door helper.** A session reaches for `lib/front_door.py` and its `front_door.grade` entry
   point when it validates a **claimed** grading — the band, tier, and evidence the caller supplies
   — against the project's stamped severity ladder and its configuration. The helper returns the
   outcome together with the band, tier, and evidence it graded; it never derives the tier from band
   and evidence — that read belongs to the advisor on the grid, which stays an instrument a person
   reads. A session meets refusal tokens at the door that include `ladder-unstamped`, `band-unknown`,
   `evidence-argued`, `p0-band-excluded`, and `profile-absent`, among others; an unstamped ladder
   **queues** a P2 claim rather than refusing it. The helper's own evidence tokens — `field`, `lab`,
   and `argued` — are coarser than the grid's evidence tiers, so the tier a session records on the
   item comes from the grid, not from what the helper was handed.

## The tiers and the P2 carve-out

1. **A P1 or P0 grade waits on the owner's word to hold that tier.** A cleared item may rest at P2
   with no owner involvement. An item graded P1 or P0 whose word has not landed is **tier-proposed**,
   not P2. It is not filed. It waits on the collector as a tier-proposed entry, and it is counted
   in the gardening record's [pending-words line](../../../rubric/glossary.md#pending-words-line). A
   P1 waits for the next walk's batch. **A P0 never waits for a walk**. The advisor raises it to
   the owner at once, through whatever channel reaches them, ahead of any batch. The most severe
   grades must not rest in the least visible state while they wait.
2. **The P2 carve-out.** This amends the standing filing rule in this same file. **A filing whose
   item clears the evidence bar and grades P2 may be filed by the advisor**, with the grading
   record on the item. **The advisor is the only grantee**. Any other session routes through the
   collector exactly as before. Everything else about the standing contract holds. Owner calls above
   P2 still bind. The owner-absent collector still appends. The append-always clause still binds.
   The venue ladder still applies.

   **Venue-3 filings are always owner calls.** A new issue spends board attention, a commitment call by definition, even when its content is craft, except a machinery filing that clears the evidence bar and grades P2, which the advisor may file with the grading record on the item.

3. **The no-ladder rider, stated as a fail direction.** **The carve-out is inactive in a project
   with no stamped severity ladder.** With no ladder there is no band to cite, so no P0 or P1 can
   be claimed and no item can be graded P2 through the door. Cleared items **queue at the door for
   the owner's word** and nothing files. Missing configuration fails closed for anything that would
   expand authority.
4. For the tier vocabulary, see [issue-contract.md](issue-contract.md).

## Every grading keeps its scoring, and the misses log

1. **Every grading records its scoring durably on the item**. The record carries the band cited,
   the evidence tier, and the resulting tier. Whoever graded it writes it, normally the advisor.
2. **The misses log captures three classes**. The classes are declined-then-escaped,
   launched-then-regretted, and mis-tiered. The advisor appends **at the moment the miss is
   observed**, whether that is a vet, a field report, or an incident, and reads the log at every
   [gardening pass](../../../rubric/glossary.md#gardening-pass).
3. **The misses log is what the advisor appends at the moment a miss is observed** and reads at each
   [gardening pass](../../../rubric/glossary.md#gardening-pass), as the item above already states.
   **The gardening record**, not the vet receipt, is where the window's appends are accounted for.
   Nothing outside the pass reads the log, which the [reader clause](#the-reader-clause) already
   states.
4. **A mis-tiered finding re-scores the item itself** at the same gardening pass. The grid re-runs
   with corrected inputs, alongside any recalibration of the instruments. Recalibrations reach the
   owner as proposals to stamp, never as silent re-scores.
5. **Rubber-stamping is watched by judgment, never by count.** No tally of accepts and rejects is
   kept, because agreement can simply mean the proposals were sound. When either the owner or the
   advisor suspects it, the advisor reads a sample of recent decisions back to the owner at a walk.
6. **Homes.** The **misses log** lives as a sibling section of the collector's pinned registry
   comment. One surface, one pin, already read at every vet. The **gardening record** lands as a
   durable comment on the collector at each pass.
7. **The lane is recorded on the routing record today.** The receipt corpus cannot be read by lane
   from the receipts alone — the canonical receipt's field spine carries no lane field. **The grading
   record does not carry it**, because no lane exists at intake.

## The declined registry and its triggers

1. **A declined item becomes a registry line with a named trigger**. The trigger is a concrete
   condition, such as "the first real caller appears", whose firing **re-scores the item onto the
   grid wherever it now lands**, any tier up to P0. Declined is a pre-evidence state, not a
   graveyard.
2. **A trigger gets exactly two detection moments, both existing acts.** At the **door**, every new
   filing is checked against the registry before minting, and a match re-scores the registry line
   instead of minting a duplicate. At each **gardening pass**, the advisor sweeps the registry's
   triggers against current state. **No standing watcher is built for triggers**, and nothing reads
   them between those two moments.
3. **The registry has one home.** The collector's pinned registry comment is the canonical surface.
   See [The revisit-trigger registry](#the-revisit-trigger-registry) for the mechanics.
4. **Rows already in the registry carry over unchanged.** The door is the successor to the test this
   section replaces, and its rows are inherited rather than re-derived.

## The launch door

1. **Filing is cheap. Launching is the guarded act.** The budget is [N](../../../rubric/glossary.md#n)
   machinery lanes in flight at once, counted by the advisor at the launch word. A lane is in flight
   until its outcome is recorded, which the launch doctrine already requires. **That is the whole of
   the slot accounting.**
2. **The dial.** The [dial](../../../rubric/glossary.md#dial) is a ceiling on the machinery share
   of wave capacity over a [gardening window](../../../rubric/glossary.md#gardening-window). The
   counting rule counts lanes launched in the window. Each lane is classified machinery or
   product-forward at routing by its [kind label](../../../rubric/glossary.md#kind-label), so a
   lane routed outside any wave carries the classification too. **The plugin's default ceiling is 20
   to 30 percent, and each project stamps its own value in its configuration.**
3. **N.** N is the dial's per-wave expression. The project's stamped dial value applies to the
   wave's lane count, rounded down. **The dial is a ceiling, so a fraction never rounds into an
   extra machinery lane.** When a non-zero dial against a non-empty wave would round to zero, **N
   floors at one**. A project may pin N explicitly, and an explicit N wins over the derivation.
4. **Which instrument binds.** The dial governs and N is its per-wave planning expression. The
   accounting unit is the **authorized wave**. A wave whose planning sentence passes the dial
   launches its lanes in any order. A lane launched outside any wave gets the same sentence at its
   own word, against the window so far. **N caps concurrency within a wave, the dial caps the
   window's share, and the tighter one binds.** No finer accounting is done. A P0 override changes
   priority, never the launch budget. A larger budget is a change to the dial.
5. **A convention at the launch word, never a check.** At wave planning the advisor writes the share
   as **one sentence beside the owner's word**, in whatever thread carries the word. The sentence
   states machinery lanes over total lanes, across every lane launched in the current window so far
   plus the wave being planned. A lane launched outside a planned wave gets the same sentence
   beside its own word. **There is no separate compliance measure and no breach state**. The pass
   reports the window's forward share and reads it against the dial in one sentence. A wave planned
   without the sentence is a slip the record names, and the advisor writes the missing sentence at
   the pass from the launch ledger. **The dial is never a launcher check, a preflight item, or a
   script**, and a filing to make it one is declined at the door. A checked dial is the grid
   instrumenting itself.
6. **Tiers order entry through the door. The owner's word sits at launch**, where the capacity is
   actually spent.
7. **No exemption for correctness.** Every epic and milestone is product-forward and is labeled so
   by the owner at ratification. **The advisor never makes that call.** Machinery then arrives only
   as a standalone lane through the door under the dial, or as a backlog item folded into a product
   epic and visible on the folded-in list. **A fix to machinery is machinery.** If the ceiling proves
   too slow, the lever is the stamped dial value, never a carve-out. An exemption for "correctness"
   is how a ceiling leaks.

## Folding backlog items in

1. **At epic decomposition**, the backlog and the declined registry are scanned for P1s, P2s, and
   registry lines whose triggers the package's surfaces are about to make true. Pulls ride the
   package's normal machinery as **ratified child scope**.
2. **At standalone routing**, the routing-time fold consideration folds foldable P1s and P2s in
   **before the build-ready marking**. **Foldable** means three things together. The backlog item's
   scope lies within the issue's named surfaces. Its definition of done can be absorbed without
   changing the issue's lane call or presentation call. The fold has no
   [material consequence](../../../rubric/glossary.md#material-consequence).
3. **The fold happens before the build-ready marking**, so whoever authorizes the build reads the
   folded body. **No scope reaches a builder that was not in the body when the build was authorized.**
   Authority is unchanged by the fold.
4. **A P2 folds on the advisor's ordinary routing authority.** **A P1 folds only when its batched
   tier word has already landed**, or with the owner's explicit word covering the fold. **The
   advisor's build-ready marking never stands in for a tier word.**
5. The fold is routing-time scope shaping **before** authorization. It is never a widening after the
   word and never a new authority. That reconciles with the venue ladder's rule that scope changes
   are the owner's.
6. **An issue adopted into an epic counts as product-forward**. It rides the package as ratified
   scope, not against the dial. **Folded-in items are a bonus drain on top of the budget, never a
   substitute for it.** Each gardening record lists the window's
   [folded-in items](../../../rubric/glossary.md#folded-in-items), **one line each**, never a count
   alone, so the owner can see exactly which machinery entered waves through adoption rather than
   through the dial.
7. **Mid-build improvisation stays forbidden**, exactly as it is today.

## The reader clause

1. **Any filing that proposes an instrument, detector, report, or sweep carries a reader clause**.
   The clause names the **named consumer**, the **trigger** that makes the consumer read it, and
   **what absence of output means**. **Without all three the item is not build-ready.**
2. **Each project declares one unconditional digest as the floor**. The digest is the minimum
   standing read that keeps "silent instrument" distinguishable from "healthy instrument". The
   digest's shape is a project configuration item. The
   [configure profile](../../configure/SKILL.md) is its home.
3. **The door's own instruments carry their reader clauses here.** The misses log, the declined
   registry, the scoring records, and the forward-share trend all have the same three. The consumer
   is the **owner and the advisor at the gardening pass**. The trigger is **the gardening pass
   itself**. Absence means **no pass has run**, which the owner can see directly because the pass
   rides their own decision walk.

## The venue ladder

A **residual** is anything a review or a vet leaves behind that is not fixed in the lane, such as a
finding, a follow-up idea, or a hardening proposal.

**A residual that passes only at continuation cost is a ride-along — eligible for the continue and fold venues only, explicitly droppable, and never a ticket.**

**A machinery residual that passes the door's evidence bar descends the venue ladder: continue the PR, then fold into an existing issue by editing its body rather than filing a new ticket, then a new issue, bundled by shared surface before filing. A product residual descends the same ladder on the strength of the owner's ratification rather than the bar.**

**No target disposition mix exists: a walk where every machinery residual passes the door's evidence bar, or every machinery residual fails it, is a signal to inspect the interrogation itself rather than a success in either direction; product residuals enter by ratification, not the bar, and sit outside this mix check.** Inspecting the interrogation means re-reading how the items were questioned — not re-scoring them.

## Craft calls and owner calls

[Craft call](../../../rubric/glossary.md#craft-call) and [owner call](../../../rubric/glossary.md#owner-call) are defined in the glossary, and the line between them, the [material consequence](../../../rubric/glossary.md#material-consequence), has its plugin default in [issue-contract.md](issue-contract.md).

Venue-1 continuations and craft declines are craft calls. The advisor executes and records for veto.
Venue-2 scope changes, product declines (any decline that trades away something a product reading
could want), and items whose door grading is uncertain are owner calls.

**Every owner call is appended to the collector at vet time, unconditionally, so the collector is the complete register by construction; owner attendance governs only when discussion happens — attended, the item is proposed in the vet-delivery message and may be struck minutes after it was appended; absent, it awaits the batch.**

**Each append carries its door grading for a machinery item — the band, the evidence tier, and the resulting tier the front door recorded — and for a product item the classification and the ratification it rides, since no evidence bar applied to it; each append also carries its venue recommendation, so the owner's batch is one word per item.**

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

**The revisit-trigger registry is one pinned, always-current comment on the project's collector issue, one line per declined item — what was declined, how it failed the evidence bar, the revisit trigger, and the date with a pointer to the full record — archiving declines from craft calls and owner calls alike.**

**The collector is the pre-ruling queue and the registry is the post-ruling archive.**

The registry comment is identified by the marker `<!-- superheroes:revisit-registry -->` placed on its
own first line. An advisor updating it **reads that comment, edits it in place, and writes it back**
— finding it by its marker rather than by position, so a project grows exactly one registry. When no
comment on the collector carries the marker, the advisor **creates one and pins it**; when more than
one does, that is a defect to repair by consolidating into the oldest rather than by adding a third.

Each registry row is one line per declined item carrying what was declined, how it failed the
evidence bar, the revisit trigger, and the date with a pointer to the full record. This row shape follows the ledger
family — cite-instead-of-re-arguing, and a named condition that reopens the decision — and it
assumes no `LEDGERS.md` file in a consuming project; a project that keeps a strategic ledger may
graduate rows into it, and that is optional.

Craft-call declines and owner-call declines are both archived here. Craft-call declines land in the
registry too, which is what makes them visible and veto-able. Owner-call declines land after the
owner's word.

Archiving a decline is two writes with no transaction — the registry row and, where the declined
item has a collector entry, its strike (a craft-call decline that never reached the collector has
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

## The gardening pass

The [gardening pass](../../../rubric/glossary.md#gardening-pass) is the periodic sweep the owner and
advisor run together to keep calibration honest.

**The trigger.**

1. **The pass is owed seven days after the last [gardening record](../../../rubric/glossary.md#gardening-record)**,
   and it is done **at an opportune sitting, not the first one**.
2. **The check runs at the start of any [decision walk](../../../rubric/glossary.md#decision-walk)**,
   never on its own and never on an ordinary [ruling](../../../rubric/glossary.md#ruling). When seven
   or more days have passed since the last record and no "gardening pass owed" item is on the
   [collector](../../../rubric/glossary.md#collector), **the advisor appends one, dated, and says so at
   the walk**.
3. The item **stays on the collector until the pass runs and its record lands**, which closes it.
4. **The owner picks the sitting.** The advisor may prepare the sweep beforehand so the sitting is
   short. **A walk opened for one urgent ruling is never turned into a pass by the calendar.**
5. **There is no scheduler.** Until the first gardening record exists, **the project's calibration
   date stands in for "the last gardening record"** everywhere this rule is read, so the first pass
   falls on the first walk a week after calibration.

**The seven duties, a closed list.**

1. **Age the P1s.** Each P1 older than two passes is proposed for promotion, demotion, or decline.
2. **Sweep four things, then draw from the queue.** The four: the declined registry's
   [triggers](../../../rubric/glossary.md#trigger); the [retirement conditions](../../../rubric/glossary.md#retirement-condition)
   whose [condition windows](../../../rubric/glossary.md#condition-window) have elapsed; the tripwires
   the verification doctrine names, **written up as one short outcome account, never as a separate
   readout each**; and the **open consumer reports** since the last pass, which land as receipts in
   the entries' consumer-evidence field.
   - **Keep two distinctions sharp.** An open consumer report is an **observation**, not a firing. A
     consumer report of the class the tripwires name **is** a firing of that condition and generates
     a [proposal](../../../rubric/glossary.md#proposal).
   - **A tripwire firing separates what was observed from what it infers.** Every firing is **a prompt
     for an owner conversation, never a diagnosis**. Its record carries two parts, kept apart: the
     **observation**, the count, the window, and the records it was read from, and the **cause the
     firing proposes, marked as inferred, with the plain alternative reading named beside it**. **A
     proposal that states its inference as fact is a defective firing**, and the owner rules on the
     observation. For example, two fixes to the same defect may be one unresolved defect fixed twice
     rather than a loop that should go.
   - **Tripwires are read here and nowhere else.** Nothing watches a tripwire between passes.
   - **The keep-or-retire record's home.** The sweep of retirement conditions reads the project's
     **[keep-or-retire list](../../../rubric/glossary.md#keep-or-retire-list)**, which is **project
     record kept by a person, living with the project's definition-docs wherever the project's doc
     policy keeps them**. **It is never a shipped reference document and never an issue.** The
     project's doc policy decides it.
   - **The draw.** Then draw the next proposals off the queue, **about five per pass, ordered by lines
     reclaimed**. When the batch is done and the queue is not empty, the advisor **says how many
     remain and asks whether to draw another batch of about five**. Batches continue on the owner's
     word until the queue is empty or the owner stops.
3. **Read the [misses log](../../../rubric/glossary.md#misses-log)** and propose any recalibrations for
   the owner's stamp.
4. **Re-measure the forward share for the window and read it against the [dial](../../../rubric/glossary.md#dial)
   in one sentence**. Record the **decisions-asked count** for the same window. List the
   [folded-in items](../../../rubric/glossary.md#folded-in-items), one line each. List the window's
   declines with their triggers, one per line.
5. **Report the [workaround markers](../../../rubric/glossary.md#workaround-marker)**, whose inventory
   is a section of the same keep-or-retire record, proposing promote-or-retire for any marker whose
   [delete-when condition](../../../rubric/glossary.md#delete-when-condition) has come true.
6. **Read guardian staleness**, merges and days since the project's last triaged sweep, a project
   configuration item with plugin defaults of ten merges and fourteen days, and, **when stale, run the
   sweep in the pass and triage its report in the same sitting**. **Sweep and triage are one duty**. If
   the sitting ends before triage is recorded, the record carries the untriaged report as a pending item
   and **the staleness clock does not reset**. The sweep needs no owner word. **Filing from it goes
   through the front door like anything else**. A P2 files on the advisor's authority. Higher tiers
   wait for a word. **Nothing reads guardian staleness between passes.**
7. **Classify the window's red continuous-integration runs and fix pull requests** by the verification
   policy's classes: own broken test, real catch, infrastructure, flake, and escape. **Credit each real
   catch to the test file that caught it.** **One rate comes out of it: the escape rate**, escapes over
   the window's merged pull requests, and it is the one rate every rule that reads an escape rate
   consumes. **"Flake" is a classification word here**, so a flake is neither an escape nor a catch, and
   **no flake rate is computed at the pass**. A flake rate, if anyone wants one, is measured on demand
   from run receipts as a reference point the owner reads, never a gate and never a trigger. The duty
   also records **the latest mutation run's survivors and kills per test file the run covered**. **A
   file no run covered reads as unmeasured for mutation, never as no kills**.

- **The pass's output is batched words for the owner, delivered in the walk itself.**
- **The decisions-asked count, and the baseline the forward share is read against, come from the
  project's own record**, its configuration profile and its gardening records, **never from a founding
  document**.
- **If the full pass proves overwhelming, the named fallback is a bounded pass**: urgent exceptions
  plus one or two retirement proposals per pass, the rest carried forward on the queue, the guardian
  sweep produced before the sitting. **Moving to the bounded pass is the owner's word at a walk.**

## The gardening record

**The contents, in one place.** A gardening record carries:

- the batched words, each with its full per-item spine;
- the [pending-words line](../../../rubric/glossary.md#pending-words-line);
- **the figures block**: the forward share read against the dial, the **decisions-asked count**, and
  the escape rate;
- **the lists**: the folded-in items, and the declines with their triggers;
- the workaround-marker state;
- the guardian staleness read and any pending triage;
- the open questions the passes carry until settled;
- and **the misses-log appends made**.

**What the decisions-asked count counts.** The decisions that needed the owner's word in the window:
P0 rulings, batched P1 words, launch words, retirement rulings, and recalibration stamps. **Nothing
compares it to anything yet.** The window's misses are **not** a second count, because the record's
misses-log line already lists the entries appended. The escape rate is a different measure recorded
beside it. **No instrument is built for the count**. It is an advisor's read over board data.

**The shape.** **The record has no length cap.** Each batched word carries the full per-item spine
this contract defines. **Length pressure is answered by fewer items per pass, never by thinner
spines.**

**The windows are calendar days.** The [gardening window](../../../rubric/glossary.md#gardening-window)
is the measurement window for the trend counts. **Condition windows are stated in calendar days and
read at the first pass after they elapse, never earlier**. A pass is the reading moment, not the unit.

**The tripwire on the instrument.** When the owner says at any walk that the pass or its keep-or-retire
list is taking too long, **or an issue is filed to automate any part of it**, the response is **fewer
and coarser components on the keep-or-retire list, never automation**. **There is no timing comparison**.
The owner's own judgment is the trigger. **The keep-or-retire list is an instrument read by a person
and never gets a guard.** This section is the one home of that rule.

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

**Residual disposition:** machinery: front door evidence bar (executed evidence on a live surface; dark and future surfaces fail; in-envelope variance is not defect evidence) → venue ladder once past the bar; product: owner ratification, same venue ladder (continue → fold → file, bundled by surface); decline with a revisit trigger when every venue fails the bar.
**Call:** at a craft call the advisor executes and records for veto; at an owner call the owner's word via the collector; a filing whose item clears the evidence bar and grades P2 is the advisor's, and every other filing is an owner call; doubt upward.
**Append-always at vet:** every owner call to the collector with door grading and venue on each
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
