# Contents

- [What an amendment is, and when this fires](#what-an-amendment-is-and-when-this-fires)
- [Classifying the amendment](#classifying-the-amendment)
- [The log entry](#the-log-entry)
- [The wording path](#the-wording-path)
- [The substantive path](#the-substantive-path)
- [Propagation — reaching work already in flight](#propagation--reaching-work-already-in-flight)
- [Reciprocal seams — one contract, two homes](#reciprocal-seams--one-contract-two-homes)

# Spec amendments

This file is the one home for **post-approval spec amendments** — how a change is classified,
what the Amendments log entry must carry, which ceremony each class owes, and how the change
reaches work already in flight. The showrunner charter points here; this file carries the detail.

## What an amendment is, and when this fires

A **spec amendment** is a change to a spec **after owner approval**. The spec body is **edited in
place** so it reads correct top to bottom — never a correcting note appended below the body — and
the change adds one entry to the spec's **Amendments** log.

This exists to prevent two failures: a spec whose body and whose history disagree, and in-flight
work built against text that has since moved without anyone noticing.

**An unapproved spec has no amendments.** A spec still in draft is being written; edits land in the
body only, with no log entry and no propagation machinery.

## Classifying the amendment

> Every post-approval spec amendment is classified `wording` — it changes phrasing and decides nothing a builder could build differently against — or `substantive`, which is everything else and the default whenever the call is ambiguous.

The test is operational, not about edit size. Ask: could a builder reading the old text and a
builder reading the new text **build different things**? If yes — even when the diff looks
cosmetic — the class is `substantive`.

**Worked calls:**

- **Obviously `wording`:** a sentence is rewritten for clarity — shorter, plainer, same obligation.
  A vet grading the handback would reach the same pass/fail verdict against either wording.

- **Looks like wording, is `substantive`:** a hedge is removed ("may" becomes "must"), or a
  "should" becomes a "must", or a vague line gains a measurable bar. The sentences are similar
  length, but what a builder must implement — and what a vet must grade — has changed.

**Fail-closed default:** when the call is genuinely ambiguous, classify `substantive`. The cost
of over-classifying is one extra read; the cost of under-classifying is work built against
superseded text.

## The log entry

Every Amendments-log entry carries four things a reader can find in it:

- the **date**;
- the **owner stamp** — an amendment is owner-stamped, which is what makes it a decision rather
  than an editorial edit;
- the **class** (`wording` or `substantive`);
- the **section names it touched**.

**Ordering rule:** entries are ordered in the log and numbered by order of addition (oldest = 1).
The number is **positional, not a stored field** — an entry never carries its own number, so
renumbering cannot drift.

An issue's anchor cursor cites a spec section `as-of amendment #N`; **N is resolved by counting
entries in the log in order** — which is why the ordering rule above matters. The resolution test
itself lives in `skills/showrunner/reference/issue-contract.md`.

**Example entry** (rendered the way an approved spec's Amendments section carries them):

```markdown
- **2026-08-08 (owner-stamped, wording):** recorded the approval date — the owner confirmed in
  the advisor channel that approval was given 2026-08-07 in the discovery sitting; added the
  `approved:` frontmatter field. Sections touched: frontmatter, Amendments. Decides nothing a
  builder could build differently against.
```

## The wording path

A **wording** amendment's total ceremony is the body edit, the dated log entry, and mechanical
propagation (see [Propagation](#propagation--reaching-work-already-in-flight)). **No review round
runs.**

**Conformance rule:** a process that demands more for a wording amendment is **nonconforming**.
That is a ceiling on ceremony, not a floor — cheap amendments are what keep specs current rather
than stale-but-unchallenged.

## The substantive path

A **substantive** amendment does everything the wording path does, **plus** the touched parts of
the package re-enter the read loop **before the amended text is injected** into children. The
re-read's ceiling, cause, and park are the package-read contract's — the read loop, the convergence
rule, and the ceiling park live in `skills/showrunner/reference/decomposition.md`.

**Trigger and ordering only:**

1. **Classification first** — owner-stamped class on the log entry.
2. **Re-read second** — touched parts of the package (register, slice boundaries, affected child
   bodies) pass the package read's lenses before injection.
3. **Injection third** — amended text reaches unstarted children and explicit notices reach
   children already building.

## Propagation — reaching work already in flight

When the spec body or an epic's register changes while children are in flight, the advisor works
through this checklist — every item is load-bearing:

- [ ] **The amended artifact and its dated log come first** — nothing propagates from an unwritten
  change.
- [ ] **Unstarted children** are **mechanically re-injected** where the change is register text,
  or **re-checked against the coverage map** where the change is spec text.
- [ ] **Children already building are explicitly notified** — on that build's issue or PR, where
  the build will actually see it, never only in a channel message a build session cannot read.
- [ ] **A recorded coverage-map re-check runs after every affected spec amendment**, re-verifying
  that every acceptance criterion is still allocated **exactly once**. Recorded means written down
  where the package's readers find it — not a re-check someone remembers doing.
- [ ] **A substantive class triggers the touched-parts re-read** ([The substantive path](#the-substantive-path))
  before injection.
- [ ] **Accountability:** a child that never received an amendment is a **process defect, not a
  builder defect.** A builder that shipped against the text it was given did its job.

## Reciprocal seams — one contract, two homes

A **cross-epic seam** entry is **one contract recorded in two homes**. Therefore:

- **Amending it in either register amends both**, and
- **Both epics' affected children are treated as affected.**

Where one side is a **single-issue spec**, that side's home is **the child's issue body**, which
quotes the entry verbatim and stands in for the missing register — so "both homes" means either
two registers, or one register and one stand-in issue body.

The seam's own recording rules live in `skills/showrunner/reference/decomposition.md`.
