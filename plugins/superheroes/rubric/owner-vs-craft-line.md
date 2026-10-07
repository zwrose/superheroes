# Contents

- [The owner-vs-craft line](#the-owner-vs-craft-line)
  - [The ten owner categories](#the-ten-owner-categories)
  - [How a call is sorted](#how-a-call-is-sorted)
  - [Always craft](#always-craft)
  - [A craft choice that carries an owner consequence](#a-craft-choice-that-carries-an-owner-consequence)
  - [Errors are not decisions](#errors-are-not-decisions)
  - [The same line in every project](#the-same-line-in-every-project)
  - [Worked examples](#worked-examples)

# The owner-vs-craft line

One line sorts every call a session meets, in every project that uses the plugin: discovery, the
advisor, merges, fixes after approval, deviations and follow-ups. When in doubt, the call is the
owner's.

## The ten owner categories

A call that touches any of these is the owner's, unless the sorting rule below sorts it as craft first.

### 1. Who the product is for, and what it's for

The people the product serves and the job it does for them, kept once per project. Every other call
leans on it, so discovery reads it first.

Examples: A build plugin is for a product-minded owner who isn't expected to know engineering craft.
A meal-planning app is for households planning meals and shopping together, and it is headed to a
paid product.

**Not yours when** a spec just restates what is already recorded.

### 2. Who this piece of work is for and what they're trying to do

Told as user stories, "As a …, I want …, so I can …", captured in each discovery. They evoke the core
need, not every detail, and the requirements carry the detail. It is what tells two right-looking
designs apart.

Examples: As a household shopper, I want to add more of something than my meal plans need, so I can
stock up without losing track of what the plans need. As a shopper mid-aisle, I want one number on
each row, so I can put the right amount in the cart without doing the sums.

**Not yours when** the approved board or an agreed story already shows it. Edge cases are
requirements, not stories.

### 3. What a person sees or can do at a given moment

The behaviour of one screen or step: what is shown, what can be tapped, what happens next, and what
happens when it goes wrong.

Examples: Remove on a shopping-list row that meal plans feed refuses, and points to the plans. A row
whose amount is still unknown can't be checked off; tapping it opens its question.

**Not yours when** it matches an approved board or an existing pattern exactly.

### 4. Whether a thing should exist at all

Scope, and whether it is worth what it costs to build and keep, including retiring something already
built.

Examples: There is no "test version" concept in any environment; document versions are just seed
data. No extra controls for a rare case that an existing check already catches.

**Not yours when** it is a routine split of scope already agreed.

### 5. Risk tolerance and trust

What the product defends against, who may bypass what, what is stored and for how long, and the
privacy defaults.

Examples: Account creation is refused from the EEA and the UK. Findings about deliberately malicious
input are outside the threat model: accepted, not fixed.

**Not yours when** the project's stated threat model already decides it.

### 6. The owner's own time, attention and habits

What reaches the owner, how and when, and what an agent may commit the owner to.

Examples: Nothing is filed without the owner's word, Backlog included. Fixes found at the advisor's
vet come to the owner before they are pushed.

**Not yours when** it is only how a message to the owner is worded; plain language is already the rule.

### 7. A case that tests or creates a principle

A case that clashes with a principle the owner has stated, or that no principle covers yet. The
owner's answer becomes the principle, a [standing ruling](glossary.md#standing-ruling) in
[Canon](canon-contract.md), which every later discovery reads.

Examples: Asked whether account deletion gets its own dialog, the owner rules that it shares the
household-deletion dialog: no second implementation of the same thing. A proposed approval gate
clashes with the owner's stated principle of autonomy.

**Not yours when** a standing ruling in Canon plainly decides it.

### 8. The quality bar, and what counts as proof

Thresholds, what evidence comes before spending, and whether a known defect may ship.

Examples: Review rounds stop at four, and anything still open goes to the owner. A merge is held for
one more fix round instead of shipping known leftovers.

**Not yours when** the bar is set and the case clearly meets or misses it.

### 9. All user-facing copy

Every word the product shows its users. Agents draft it and the owner approves it. For a plugin, that
is what the plugin says to its user.

Examples: "Need beyond Plans" replaces "not from a plan". "Keep my account" replaces "Cancel", which
could be misread as cancelling the subscription.

**Not yours when** it is instruction text agents read, under the [prose standard](prose-standard.md).

### 10. Priority and timing

What ships when, when a decision gets made, and how much to invest now.

Examples: One piece of work is held until a related piece is settled. The terms documents wait until
just before go-live.

**Not yours when** it is the order of build pieces inside an agreed stack.

## How a call is sorted

A session sorts every call it meets in this order, and stops at the first step that applies:

1. Already answered: an approved artifact, a standing ruling in Canon, the code, or a checkable fact
   answers it. The call is craft.
2. Ceded: the owner has ceded that kind of call (a [ceded call](canon-contract.md#ceded-calls) in
   Canon). The call is craft.
3. Touches any of the ten categories: the call is the owner's.
4. Sure it touches none: the call is craft.
5. Unsure: the call is the owner's.

A call sorted as the owner's is an [owner call](glossary.md#owner-call) and waits for the owner's
word. A call sorted as craft is a [craft call](glossary.md#craft-call), decided by the agent and
recorded for the owner's veto.

## Always craft

Decided by agents and recorded for the owner's veto:

- Matching an approved board or reusing a pattern the product already has.
- Applying a rule the owner already set to a new case.
- Bookkeeping, when a status changes because a fact changed and no rule does.
- Pulling implementation detail out of a requirement.
- Routine size splits and the shape of a breakdown.
- How it is built and how it is tested.
- Tools and libraries.
- Internal names and internal error handling.
- How a speed or size target is met.
- Cleanup that changes no behaviour.

The owner keeps the right to ask pointed questions about testing at any time. A question does not
make testing an owner category.

Grading an item into a P0, P1 or P2 tier with the advisor's grid stays craft, because it applies a
set rule. The tier words do not change.

## A craft choice that carries an owner consequence

The consequence rule: a craft choice never becomes the owner's, but an owner consequence it carries
goes to the owner as its own decision. Such a consequence is a
[material consequence](glossary.md#material-consequence).

For example, a build picks a new outside service that adds a monthly cost. The cost goes to the
owner, and the choice of service does not.

## Errors are not decisions

Misreads, wrong facts, contradictions, jargon in owner-facing text, and gaps a review should catch
are errors. Review fixes them; they are never decisions, and they are not on the line.

## The same line in every project

The ten categories are the same in every project. What changes, project by project, is how many calls
inside them are already answered, and only through the owner's rulings in the project's Canon. Each
ruling recorded as it is made answers the same question next time. A ceded call makes a kind of call
craft; taking it back returns that kind to the owner. See
[Writing a ruling](canon-contract.md#writing-a-ruling) and [Ceded calls](canon-contract.md#ceded-calls)
for how rulings and ceded calls are recorded.

No configuration value moves the line. A project's own answers live in its Canon's standing rulings
and ceded calls.

## Worked examples

1. A reviewer finds the spec never says what a new person sees before any terms exist. Nothing
   answers it, no ceded call covers it, and it touches categories 3 and 4. It is the owner's.
2. The approved board says phone sheets close by swipe only, but the grab handle must still work for
   a screen reader. An owner ruling and ordinary accessibility answer it. It is craft.
3. Picking the email sending service. The tool is craft, but its monthly cost and a new outside
   service touch categories 4 and 5, so the cost is the owner's.
4. Switching twelve rules from waiting wording to live wording now that the piece they waited on has
   shipped. A checkable fact answers it and no rule changes. It is craft.
5. The advisor wants to file a Backlog issue for a small defect it found. It touches category 6, and
   filing is not a ceded call. It is the owner's.
