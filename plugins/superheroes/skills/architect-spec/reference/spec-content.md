<!-- spec-content-version: 1 -->

# Contents

- [What this file is](#what-this-file-is)
- [Consolidation re-read (FR-23)](#consolidation-re-read-fr-23)
- [Annexes (FR-24)](#annexes-fr-24)
- [Rulings live where they were made (FR-25)](#rulings-live-where-they-were-made-fr-25)
- [The Amendments section is never deleted](#the-amendments-section-is-never-deleted)

# Spec content and how it changes

## What this file is

This file is the one home for **what a spec may contain and how it changes** — the consolidation
re-read obligation, the annex rule, where rulings live and when they get absorbed, and why the
Amendments section is always kept. The writing-specs skill points here when you author a body; the
showrunner charter points here when the advisor schedules consolidation or absorption. Doctrine
written only where nobody stands is doctrine nobody reads — pointers at those surfaces stay short;
this file carries the behavior.

## Consolidation re-read (FR-23)

When a spec reaches **five amendments since its last full approval**, the **next touch** of that
spec carries a **consolidation re-read**: read the spec body end to end as a whole and ask whether
five accumulated amendments have left it saying something none of them individually decided.
That touch also **records the owner's re-stamp** of the consolidated body — affirming the body
as a whole still says what the owner means.

**Nothing blocks at five.** Five is a **guideline, never a trip-line** — no gate, check, or charter
turns it into a hard stop, and reaching five is not an error state. The fifth amendment lands
normally; the obligation attaches to the touch **after** it.

The re-read and the re-stamp are two halves with different owners:

- The **re-read** is reading work. Whoever makes the next touch can do it.
- The **re-stamp is the owner's** and cannot be substituted, delegated, or inferred from silence.

A touch that cannot obtain the re-stamp **records the re-read, states that the re-stamp is
outstanding, and names who owes it** — it does not skip the re-read, and it does not quietly
proceed as though the re-stamp happened.

While a consolidation re-stamp is outstanding, **every subsequent touch restates it** — the debt
rides forward, unchanged, until the owner stamps the consolidated body, and only the owner's stamp
clears it.

Entries are counted **since the last full approval**, not since the spec was created.

The advisor's job on the touch after five is to **schedule the owner's re-stamp** — only the
owner can give it. The re-read itself may be done by whoever makes that touch.

## Annexes (FR-24)

An **annex** elaborates decisions its core spec **already makes**. It **never introduces a new
opinion**. Post-approval opinion **amends the core** — that is what amendments are for.

Annexes are an attractive place to smuggle a decision the owner never made, because annex prose
reads as detail rather than as a decision. That is exactly why the rule is absolute rather than a
matter of degree.

An annex introducing a new opinion is a **named review-spec finding class** — this file carries the
rule; `review-spec/reference/spec-detail.md` carries how a seat applies it.

**Elaboration, not decision.** Examples, edge-case walkthroughs, and worked scenarios that follow
from a decision the core already states are annex material. A sentence that would change what a
builder could build differently against the core is a new opinion — it belongs in the core body
via an amendment, not in an annex.

## Rulings live where they were made (FR-25)

**Specs are the decision store.** A ruling lives at the place it was made and is cited from there.
The plugin maintains **no separate rulings ledger** — the showrunner charter carries why (the
Anchor citation is the reverse index).

**Absorption is a judgment call, never a trigger.** When a surface has accumulated enough rulings
that it has quietly become a decision store of its own, it may be **absorbed into a spec** — and
that absorption is a **recorded advisor judgment**, made and written down when it is made.

There is **no mechanical absorption trigger** — no count of rulings, no age, no size, no threshold
of any kind causes absorption, and none may be introduced. A number here would convert a judgment
into a gate.

A **cited ruling still resolves at its original home** after absorption; absorption adds a decision
store, it does not invalidate the citation.

## The Amendments section is never deleted

Every spec renders a `## Amendments` section. With no post-approval amendments it carries exactly:

`_No amendments since the last full approval._`

Workhorse anchor resolution **fails closed when a spec carries no Amendments log at all** — deleting
the empty section would make every `spec-section` anchor against a freshly approved spec fail intake.
A log that exists and holds zero entries resolves cleanly against an `as-of amendment #0` cursor.

The Dispositions table (`## Coverage`) and the amendment log are separate concerns: the table records
how each coverage area was dispositioned at authoring time; the log records post-approval changes.
Neither replaces the other.

This file does not define how an amendment is classified, what ceremony each class carries, how
amendments propagate to in-flight children, or how the log is validated — that machinery lives
elsewhere. For the log's entry format, see the `## Amendments` section of the spec template
(`templates/spec.md`) — and stop there.
