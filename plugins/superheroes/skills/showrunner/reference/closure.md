# Contents

- [When closure fires](#when-closure-fires)
- [The closure receipt](#the-closure-receipt)
- [The validation run](#the-validation-run)
- [The owner's delivery decision](#the-owners-delivery-decision)
- [When the validation run fails](#when-the-validation-run-fails)
- [An abandoned child](#an-abandoned-child)
- [The single-issue case](#the-single-issue-case)

# Spec closure

This file is the **single plugin home** of the spec-closure contract: the closure receipt's
element list is enumerated **here and nowhere else in the plugin**, and every rule the showrunner
charter states about closure exists here in full detail with the charter carrying only the pinned
one-sentence form.

## When closure fires

Closure is **never a separate process or a separate trigger**: it rides the vet of the child PR
whose merge closes the spec's last open child.

The present-tense test is a test of **the moment**, not of the plan. A child added after the plan
was drawn moves the final vet — the advisor re-applies the test at each candidate moment, not once
when decomposition was filed. "Already merged or closed" is read at vet time: a child still open
when the vet starts is not "already merged," even if the plan assumed it would be done first.

**The vet that carries the closure receipt is the one whose merge closes the spec's last open child, and it knows it is the final vet by the present-tense test: every other child is already merged or closed at the moment of this vet.**

Candidate closure moments look like two final vets running concurrently, or a vet racing a sibling's
no-PR close. In the concurrent case, both PRs may look "final" until one merges — the advisor holds
the receipt on the vet that will actually close the last child, and the other vet carries a
non-closure handback until sequencing resolves. In the no-PR race, the advisor presents the receipt
with the close, not with a PR merge that never comes. **Where more than one candidate closure moment is live — concurrent final vets, or a vet racing a sibling's no-PR close — the advisor sequences them so exactly one carries the receipt.** The advisor's job is to sequence them so **exactly one** carries the receipt — never zero, never two.

**Where the last open child closes without a PR — declined scope — the closure receipt is presented to the owner with that close, in the same sitting, and there is still no separate closure trigger.**

## The closure receipt

The element list's pinned home of record is R8:

> **R8 — Closure receipt elements.** The closure receipt enumerates exactly: coverage map complete; all other children merged with green vets; amendments reconciled — meaning the Amendments log is valid against R4's format AND UFR-4's propagation is verified: every affected child carried the amended text or an explicit notice, and the coverage map still allocates every acceptance criterion; one end-to-end validation run against the current spec body with its result stated; aggregated Show-it items; delivered versus deferred/declined named; and NFR conformance checked across the delivery (owner reading load, plain language, guidelines never hardened into gates) — an absent element is named with why.

Reading the entry element by element, the advisor checks:

- **coverage map complete** — every acceptance criterion is still allocated to exactly one child.
- **all other children merged with green vets** — each named, with its vet named.
- **amendments reconciled** — the Amendments log is valid against **R4**'s format (date, owner
  stamp, class, touched section names, positional numbering) **and** propagation is verified: every
  affected child carried the amended text or an explicit notice, and the coverage map still
  allocates every acceptance criterion. The amendment machinery lives in
  `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/skills/showrunner/reference/amendments.md`.
- **one end-to-end validation run against the current spec body, with its result stated** —
  detailed in [The validation run](#the-validation-run).
- **aggregated Show-it items** — the package's Show-it surface gathered across children, so the
  owner judges the delivery, not nine separate diffs. Aggregation is presentation, not a new gate:
  each child's Show-it still exists; the receipt collects what the owner needs in one sitting.
- **delivered versus deferred/declined named** — the input to the delivery decision. Deferred means
  still intended; declined means the owner ruled it out — both must be named, not folded into silence.
- **NFR conformance checked across the delivery** — owner reading load, plain language, guidelines
  never hardened into gates.

**Absent-element rule:** an element the receipt cannot carry is **named with why** — the receipt is
complete or it says exactly where it is not; a silently missing element is a defective receipt, not
a shorter one.

## The validation run

One end-to-end run against the **current** spec body — **current** meaning as amended, not as
originally approved.

Two surface kinds:

- **App surfaces** — an **executed** test-pilot run derived from the spec's DoD and acceptance
  criteria.
- **Plugin or doctrine surfaces** — the plugin's automated conformance checks exercising the shipped
  behaviour, **supplemented by one recorded rehearsal** where an element needs a live run that no
  automated check performs.

In both cases the receipt carries the run's **result**, not merely that a run happened. "Passed" or
"failed" (or an equivalent stated outcome) belongs on the receipt; "we ran validation" without a
result is incomplete.

**FR-37 acceptance edge:** a receipt whose validation run is **absent** can close only by the
owner's explicit acceptance with the absence disclosed — never as an ordinary full delivery. This is
not the same as [When the validation run fails](#when-the-validation-run-fails), which is about a run
that **ran and failed**.

## The owner's delivery decision

The owner accepts delivery **on the closure receipt**, presented with the final child PR's handback
— or with the no-PR close — in **one sitting**, never a separate process.

**No spec closes without either full delivery accepted or an explicit owner acceptance of partial delivery, named as such on the closure receipt with delivered, deferred, and declined each named; nothing closes silently incomplete.**

**Explicit** means named, not inferred. An explicit partial acceptance names delivered, deferred, and
declined; a merge click is not an acceptance unless the handback names it as one **in so many words**.
Full delivery acceptance is also explicit — the receipt states that the owner accepted the whole
delivery, not that merge happened without a delivery decision.
The advisor's job is to make the decision presentable, never to make it: the verdict is advisory,
the acceptance is the owner's.

## When the validation run fails

Both outcomes are the design — a failing run does not mean the process is broken; it means the
default and the alternative both have a sanctioned path.

**A failing end-to-end validation run keeps the spec open by default and mints one repair issue per failure, each anchored to the failing run's record and naming the unmet acceptance criterion it restores; the owner may instead explicitly accept delivery with the failing run disclosed, and either way the cycle ends at an owner decision.**

### The default — the spec stays open

The spec does **not** close. Each failure produces a **repair issue**, and each repair issue carries
**both**: a receipt anchor pointing at the **failing run's record**, and the **unmet acceptance
criterion it restores**. The repair issues become children of the spec, so closure re-rides the vet
of whichever PR closes the **new** last open child — [When closure fires](#when-closure-fires)'s
present-tense test re-runs on the new set.

### The alternative — the owner accepts with the failing run disclosed

The owner may instead explicitly accept delivery with the failing run disclosed. This is a real,
sanctioned outcome, not an escape hatch: what makes it legitimate is that the failure is
**disclosed on the receipt** the owner accepts.

Each repair cycle ends at an **owner decision**, so the loop cannot cycle without the owner.

## An abandoned child

**A spec whose child is abandoned — closed unmerged, orphaned, or displaced — is re-planned or parked by the advisor rather than left waiting for a closure moment that cannot come; silence is not a disposition.**

Two branches:

- **re-plan** — the remaining acceptance criteria are re-allocated: the coverage map is repaired and
  a replacement child is filed, so a closure moment exists again. Re-plan is not a silent scope cut:
  deferred or declined items are named on the receipt that records the re-plan decision.
- **park** — the spec is parked to the owner. When the branch is **park**, R7's park surface
  governs:

> **R7 — The park surface.** A park lands the full park note — what was elicited or found so far, explicitly marked unapproved — on the owner's reading surface at park time: in the advisor's delivery message when the owner is present, else as the opening item of the advisor's next delivery message; a durable copy lands as a comment on the parked item's issue or PR, and the durable copy is for the record — it is never required owner reading.

**Silence is not a disposition.**

## The single-issue case

A single-issue spec skips epic machinery; closure folds into that one PR's vet, where the
**applicable** elements of [The closure receipt](#the-closure-receipt) are graded. The owner's merge
decision doubles as delivery acceptance **only when the handback names it as such in so many words —
an explicit line, never an inference**, and a single-issue spec still ends with an explicit owner
delivery decision. Point at
`${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/skills/showrunner/reference/decomposition.md` §
*The single-issue fast path* for the rest of that path.
