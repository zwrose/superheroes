<!-- spec-content-version: 1 -->

# Contents

- [What this file is](#what-this-file-is)
- [Consolidation re-read](#consolidation-re-read)
- [Annexes](#annexes)
- [Rulings live where they were made](#rulings-live-where-they-were-made)
- [The Amendments section is never deleted](#the-amendments-section-is-never-deleted)
- [The spec lifecycle](#the-spec-lifecycle)

# Spec content and how it changes

## What this file is

This file is the one home for **what a spec may contain and how it changes** — the consolidation
re-read obligation, the annex rule, where rulings live and when they get absorbed, and why the
Amendments section is always kept. The writing-specs skill points here when you author a body; the
showrunner charter points here when the advisor schedules consolidation or absorption. Doctrine
written only where nobody stands is doctrine nobody reads — pointers at those surfaces stay short;
this file carries the behavior.

## Consolidation re-read

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

## Annexes

An **annex** elaborates decisions its core spec **already makes**. It **never introduces a new
opinion**. Post-approval opinion **amends the core** — that is what amendments are for.

Annexes are an attractive place to smuggle a decision the owner never made, because annex prose
reads as detail rather than as a decision. That is exactly why the rule is absolute rather than a
matter of degree.

An annex introducing a new opinion is a finding the spec checks raise — this file carries the
rule.

**Elaboration, not decision.** Examples, edge-case walkthroughs, and worked scenarios that follow
from a decision the core already states are annex material. A sentence that would change what a
builder could build differently against the core is a new opinion — it belongs in the core body
via an amendment, not in an annex.

## Rulings live where they were made

**A spec holds the requirements it was approved with; the owner rulings themselves are recorded in the project's Canon** (`../../../rubric/canon-contract.md`), and a ruling is cited from where it is recorded. The Anchor citation stays the reverse index for affected work.

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

## The spec lifecycle

A spec is amended in place while it is approved and its work is building, freezes when the owner
accepts its delivery, and after that takes only superseded-in-part lines: a later owner ruling that
changes delivered behavior is marked on the spec, never amended into its body.

This is how a long-lived written decision stays honest elsewhere: a published IETF RFC never
changes and is marked updated or obsoleted by later ones, a Final Python PEP is a historical
document while the language reference is the living authority, and an architecture decision record
is immutable except for its status. A delivered spec is the record of what the owner asked for and
accepted; the shipped docs and references it points at own the behavior from then on.

- **Approved and building.** Amendments edit the body in place and log an entry
  (`../../showrunner/reference/amendments.md`).
- **Delivered.** At the owner's delivery decision the advisor marks the spec delivered: the date,
  the closure receipt's link, and `livesIn`, the shipped docs or references that now own the
  delivered behavior (`../../showrunner/reference/closure.md` § The owner's delivery decision;
  the fields are CONVENTIONS §3.1). The body is never rewritten after that. A partial delivery's
  deferred items keep the amendment path while they remain open. When a `livesIn` path moves,
  the PR that moves it updates the pointer in place, checked with `definition_doc.py
  lifecycle-check`: the pointer is metadata, not an amendment.
- **Superseded in part.** When a later owner ruling changes behavior a delivered spec describes, the
  advisor adds one dated `supersededInPart` entry naming the sections it covers and the ruling
  (`definition_doc.py mark-superseded`). Each section is named at the granularity anchors cite
  and must occur in the spec body as a whole token, so a typo is refused rather than leaving an
  anchor uncovered. The entry is metadata, not an amendment: it carries no
  owner stamp, because the ruling is already the decision. A `spec-section` anchor on a covered
  section no longer resolves, and the issue anchors on the superseding ruling instead
  (`../../showrunner/reference/issue-contract.md` § Anchor resolution).

Specs delivered before this lifecycle existed are marked when next touched, not all at once. Until
then, a reader of such a spec still checks its Amendments log and the collector for later rulings.
