# Contents

- [The vet receipt — shape](#the-vet-receipt--shape)
- [The spine — always present, filled or `None`](#the-spine--always-present-filled-or-none)
- [Triggered fields — the artifacts raise them, not your memory](#triggered-fields--the-artifacts-raise-them-not-your-memory)
- [The `None` convention](#the-none-convention)
- [Markers](#markers)
- [Skeleton](#skeleton)

# The vet receipt — shape

The vet is the **last independent read before the owner's one irreversible act**. This file is the
shape of the receipt that read leaves behind. When it is written, what else the vet does, and where
the verdict also goes are the **showrunner** charter's duty 4 — read this one at vet time, and do not
reconstruct it from memory.

**Why a shape at all.** The spine below was not designed; it is what receipts across two independent
advisor sessions had **already converged on**, ratified rather than invented. What had *not* travelled
were the loads a charter added later — and the reason nobody could measure that is the reason this
file exists: **presence-by-grep cannot tell "not applicable" from "forgotten."** An explicit `None` is
what makes an absence readable.

**The template is a floor, never a ceiling — most of all for field 2.** The probes are where a vet's
value actually lives. A uniform receipt whose probes field reads like a form has hollowed out the one
field that cannot be. If the shape ever makes a receipt shorter than the vet's actual thinking, the
shape is wrong and the thinking wins.

## The spine — always present, filled or `None`

1. **Verdict, and what it is pinned to.** The verdict, plus the **commit sha** you vetted, the **CI
   state** on that sha, and confirmation that the **remote head** contains it. A verdict pinned to
   nothing is a mood; a verdict pinned to a local-only commit is a claim about work the owner cannot
   see.
2. **What I probed.** **Distinct from the builder's own receipts** — re-running a green suite the
   builder already ran is not a probe. Say **what bit**: the mutation that made a named test fail, the
   guard you live-fired, the refusal you provoked. Confirm every **probe residue was reverted**. A
   probe that found nothing is still a probe — record it, including the ones whose premise turned out
   to be yours rather than the code's.
3. **Calls accepted, with reasons.** Every builder judgment call you are letting stand, each with
   why. Silence here reads as *not noticed*, not as *endorsed*.
4. **What the owner still carries that the owner half does not say.** The **principle check**, asked
   **unconditionally**: is there a consequence of merging that this PR's owner half never states? It
   is scoped to the **principle only** — the review seat owns the omission floor's presence match, and
   you do not re-run it. When the answer is not `None`, that consequence goes into the **owner half**
   too, not only here.
5. **Degradations.** Everything that cost something promised — in the build, and in **your own vet**
   (a probe you could not run, a surface you could not reach, a window that closes with your session).
6. **Accounting, with attribution.** Orders dispatched and reworks, each blocking finding attributed
   to **order quality**, **implementer execution**, or **the orchestrator's own integration/assembly**
   (external or unknown where none fits); the **park/refusal** rate with whether each was correct; and
   your own **receipt-integrity catches** — claims that did not reproduce when re-run against the
   world. Each record **names its window**. **Zero of either guard is a signal to inspect, never a
   clean sheet:** both are prose, so an agreeable model drives either rate to zero and it reads as a
   clean batch. Inspecting means re-reading a sample of that batch's park and vet receipts, not
   noticing the zero.
7. **Dispositions — completed, and pending.** **Completed first**, because that is the primary path:
   this PR's follow-ups are dispositioned at *this* vet, before this receipt posts. Then the
   **pending** set under `<!-- superheroes:pending-proposals -->` — only what genuinely could not
   close in this session. Each pending item carries **what it is**, **your recommendation** (so the
   owner's batch pass is one word rather than a re-derivation), and **the vet ordinal it was proposed
   at** — a monotonic integer, one per vet, assigned when the item is appended. **State this vet's own
   ordinal alongside the pending set**, so the sequence is readable from the receipt itself. **An item's
   ordinal is never re-stamped** when it is carried forward: age is `this vet's ordinal − the item's
   ordinal`, a subtraction over written numbers rather than a count of artifacts, which is what makes it
   immune to receipts being edited in place. **Never the future tense** — "I'll file X" is not a
   disposition.
8. **Open owner calls at merge.** What the owner must decide before or at the click, each stated as a
   consequence rather than a craft question.

## Triggered fields — the artifacts raise them, not your memory

Above the spine sit fields that **the PR's own artifacts** raise. The full inventory of loads runs to
about nineteen items: nineteen always-on fields become a form and get hollowed out, while plain
conditional fields reintroduce the silent omission this shape exists to kill. The way out is that
**every trigger below is a fact greppable in the artifacts**, so the artifact raises the field and you
are never holding the inventory in working memory.

| When the artifacts show… | the receipt owes |
|---|---|
| the diff adds a **gate, hook, or enforcement mechanism** | the ratified-precondition citation, and the evidence it is met |
| dispatch provenance shows **sequential orders against one worktree** | the commit-between-orders check |
| provenance names a **seat under a standing counter** this project keeps | that counter's line |
| the body carries **headline before/after numbers** | reproduction, by you, not a restatement |
| the issue carries a **show it** call | the show-it check (and the timing consequence duty 4 sets out) |
| the issue carries a **lane call** | the lane-call backstop, **both directions** |
| a **prior receipt on this PR is being corrected** | a dated correction, **edited in place** — never a superseding comment |
| the collector holds an item whose **proposing ordinal is two or more below this vet's ordinal** | an **escalation line** naming that item and stating plainly that **the owner batch is not happening** |

The last row is the tripwire for this design's own load-bearing risk — the fallback quietly becoming
the path. Each pending item's **proposing ordinal** is what makes its age inspectable — a subtraction
against this vet's ordinal, not a count of anything — so the escalation is raised by a number the
artifacts carry rather than by your memory of having carried the item.

**Known limit, carried knowingly:** a trigger is weaker than a check. A build record that omits a
sequential-order run raises no field. You read the diff too, so the trigger is a second chance rather
than the only one — but it is not a guarantee.

## The `None` convention

**Every spine field is filled or written `None`** — the literal word, the same convention *Follow-ups
for the advisor* already uses. Not blank, not omitted, not a dash. A **spine** field that is absent is
a defect in the receipt, because absence is exactly what a reader cannot interpret.

A **triggered** field that did not trigger is simply **absent** — and that is safe only because its
trigger is greppable in the artifacts, so any reader can re-derive whether it should have fired
without trusting the receipt's author.

## Markers

Three markers, **all written by the advisor at vet time**, after handback:

- `<!-- superheroes:vet-receipt -->` — the **first line** of the receipt.
- `<!-- superheroes:pending-proposals -->` — immediately above spine field 7's **pending** set (its
  body is the items, or the literal `None`).
- `<!-- superheroes:advisor-vet -->` — stamped inside the PR's `## Advisor vet` owner-half slot,
  immediately above what you write there. The slot is **append-only and yours**: you edit your own
  prior text in place, never the builder's prose. **What this marker detects is the hidden case:** a
  body rewrite that **re-creates the heading but drops your text** leaves the slot looking present and
  saying nothing — that is a slot whose text was dropped, distinct from one you have not written yet.
  (A rewrite that drops the heading entirely is visible without it.) The marker alone is **not
  sufficient**: a slot can be marker-present and text-stale. The showrunner charter's **duty 4**
  backstop is where the check and remedy live — follow that, not a marker-keyed rule here.

**No review seat checks these at review time.** A build's pre-handback review runs in branch mode,
before a PR body or a vet exists, so their absence during a review is the normal state and is never a
finding. (A CI drift test *does* read these literals — it pins them to the marker inventory in
`CONVENTIONS.md` §10.7 so the bytes cannot drift between copies — but that is a docs-consistency check,
not a consumer of the markers in a PR.) They exist so *your own* backstops have a grep anchor — above
all the age of a carried item, and the loss of an advisor write.

## Skeleton

```markdown
<!-- superheroes:vet-receipt -->
**Vet — <verdict>** · commit `<sha>` · CI <state> · remote head verified <yes/no>

**What I probed.** <what bit; residue reverted> | `None`
**Calls accepted.** <call — why> | `None`
**What the owner still carries that the owner half does not say.** <consequence> | `None`
**Degradations.** <build's, and my own> | `None`
**Accounting.** orders <n>, reworks <n>, attribution <…>; parks/refusals <…, each correct?>;
receipt-integrity catches <…>; window: <…>
**Dispositions — completed.** <…> | `None`
<!-- superheroes:pending-proposals -->
**Pending.** this vet's ordinal: <n> · <item — recommendation — proposed at ordinal <n>> | `None`
**Open owner calls at merge.** <…> | `None`

<triggered fields, each only when its trigger is present in the artifacts>
```
