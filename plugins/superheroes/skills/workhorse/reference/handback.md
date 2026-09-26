# Contents

- [Handback: the ready PR's body](#handback-the-ready-prs-body)
  - [The owner half](#the-owner-half)
  - [The advisor-vet slot](#the-advisor-vet-slot)
  - [The build record](#the-build-record)
  - [Follow-ups for the advisor](#follow-ups-for-the-advisor)
  - [The size tripwire row](#the-size-tripwire-row)
  - [The DoD disposition table](#the-dod-disposition-table)
  - [Disclosed degradations](#disclosed-degradations)
  - [Issue linking](#issue-linking)
  - [Verifying the remote head](#verifying-the-remote-head)

# Handback: the ready PR's body

This page is reference for the builder composing or rewriting a ready PR's body. The charter's §11
states the handback rule and keeps the parts a pin guards: the close-link line, the owner half's
omission floor, the `## Advisor vet` slot's exact emission with its reminder comment, and the two
build-record markers. This page carries the rest.

The body has two addressees and one home per fact. The owner half states consequences. The build
record carries mechanism.

## The owner half

The owner half is the close line, then three fixed headings in this order, then `## Advisor vet`.

- **`## What's changing, and why`.** Present on every PR, whether or not the change is perceivable.
- **`## What we're accepting`.** The risks and trades merging commits the owner to: parked residual
  risks, disclosed degradations, deferred DoD rows, and any direct question the builder has for the
  owner. The omission floor's three rows are keyed on severity, not on the disposition label. When
  there are genuinely none, write exactly **None**, the same word *Follow-ups for the advisor* uses.
- **`## How to see it`.** On a show-it PR, read the project's `## Show-it surface` declaration in
  `core.md` for the level and shape, then carry the concrete instance here. An absent declaration
  means level `none`, disclosed. The section carries the entry point (the URL or the command) and
  the drive-to-state instructions: the shortest exact path from the entry point to the thing being
  judged, transient states included.

An honest entry point of `command`, `attended`, or `none`, or a `core.md` with no `## Show-it
surface`, is a disclosed degradation. It gets one bullet under the degradations marker and a
matching consequence under `## What we're accepting`, never a silent **None** on the floor's third
row. The ranked entry-point levels and the presentation standard live in
`rubric/review-discipline.md` § Presentation standard (show it / say it / nothing to see).

## The advisor-vet slot

You stamp the `<!-- superheroes:advisor-vet -->` marker so the advisor does not have to on the
normal first write. The advisor still re-stamps it when a body rewrite dropped it, and stamps it
itself on a body that predates this contract. The advisor's write replaces the reminder comment,
which makes the slot's state readable from the body alone:

| The slot shows | It means |
|---|---|
| Marker and reminder | The owner-half write is owed. The receipt may already exist, because the advisor posts it before writing the body, so check for an existing vet-receipt comment before posting another. |
| Marker and verdict, no reminder | Vetted. |
| Marker, with neither reminder nor verdict | An advisor write that a body rewrite dropped. |
| No marker, and no vet-receipt comment on the PR | A body that predates this contract. Not yet vetted. |
| No marker, and a vet-receipt comment exists | A rewrite dropped the verdict and the marker together. |

One limit the body cannot resolve: a rewrite that drops a written verdict and re-seeds the reminder
lands back on marker and reminder, which reads like a vet that has not happened. The advisor's own
backstop, comparing the slot with its most recent vet-receipt comment (showrunner charter duty 4),
separates the two.

The shape and contents of what the advisor writes, the owner-half register, live in
`skills/showrunner/reference/vet-receipt.md` (CONVENTIONS `§10.7` names that home). When it is
written is the showrunner charter's own duty.

**Carry the slot forward byte-for-byte on every body rewrite.** Advisor-authored content is never
yours to edit, reflow, summarize, shorten, or drop. Re-creating the heading over an advisor write you
deleted is the defect, not compliance. The reminder is the only signal that tells a silently emptied
slot from one not yet written, so re-seeding it over a deleted advisor write destroys the evidence
as well as the verdict. Re-read the slot immediately before you submit a rewrite. Afterwards,
confirm it still carries the advisor's actual text, not merely that something is there. If the
advisor wrote or extended the slot while you were editing, the newer advisor text wins.

## The build record

Place `<!-- superheroes:build-record -->` immediately above the build record, then wrap the record in
`<details><summary>Build record</summary>…</details>`. The `<details>` wrapper changes nothing for an
agent: `gh pr view --json body` returns identical raw markdown.

The build record holds, below the marker:

- **In the full lane**, the build brief, the review dispositions table, and the receipts.
- **In the light lane**, the review dispositions table and the receipts. There is no brief.
- **In both lanes**, bite-proof records for every detector the build added or changed, or the line
  `None — this build added or changed no detector` when there are none, plus disclosures.
- **In both lanes**, a dispatch provenance section: each dispatch with the engine and model it ran
  on, validated against the registry allowlist, so the advisor can vet what ran without your
  context. Per order it also records whether the order was a rework, and for any blocking review
  finding, whether it is attributed to order quality, implementer execution, or your own
  integration and assembly (external or unknown where none fits). The advisor tracks that
  attribution as a standing accounting duty.
- **In both lanes**, the *Follow-ups for the advisor* section, the size tripwire row, and the
  disclosed degradations section, each described below.

## Follow-ups for the advisor

List out-of-scope discoveries, deferred work, and issues you noticed but cannot file yourself (you
never wire the board) under that exact heading. Write **None** when there are none, so the advisor's
triage backstop can grep the section.

- Key every item as one top-level bullet, `- FU<n> [<class>] <text>`, with the class one of
  `owner-call`, `defect`, `craft`, `flake`, or `info`. Indented sub-bullets may add detail.
- An optional first line counts them: `Follow-ups: <n> (<m> owner-call)`. The handback comment
  states the same count line.
- Below the list, write one marker line with the same ids from the same list:
  `<!-- superheroes:followups FU1 FU2 -->`, or `<!-- superheroes:followups none -->` when the section
  says None.

The advisor's slot writer compares this marker, not the prose, with the receipt's dispositions
marker. It trusts the marker as your declaration, and the vet reads both.

When a PR closes or is superseded before its vet, carry its follow-ups into the superseding build
record, each under the next unused FU number (in the marker too), with its origin as text:
`- FU<n> [<class>] (from #N FU<m>) <text>`.

## The size tripwire row

§4's size step fills this row. It takes one of these forms:

- `not crossed (N of estimate M)`
- `crossed at <commit>; messaged <time>; advisor ruled <split|continue|park> (<issue comment link>)`
- `crossed at <commit>; messaged <time>; parked, no reply (<issue comment link>)`
- `crossed at <commit>; messaging unavailable on this host; parked (<issue comment link>)`
- `crossed at <commit>; disclosed to the owner in session`
- `crossed at <commit>; disclosed to the owner in session; parked at 600 (<issue comment link>)`,
  when that commit also crossed 600

Every form is followed by `; deleted files: <path> (<N> lines), …` or `; deleted files: none`. Whole
deleted non-test files are reported, not counted (`rubric/review-discipline.md` § Size).

## The DoD disposition table

The PR body carries a DoD disposition table, marked `<!-- superheroes:dod-table -->`, against the
issue or spec. It has one row per Definition-of-Done bullet, each **done** with an evidence pointer,
or **deferred** with a filed issue and a one-line reason. It differs from the review dispositions
table: that one grades review findings, and this one grades every specified claim as shipped,
deferred, or dropped. It is the honesty marker the review seat verifies (CONVENTIONS `§10.7`,
`rubric/review-discipline.md`).

## Disclosed degradations

Inside the build record, `<!-- superheroes:degradations -->` is immediately followed by
`### Disclosed degradations`. Under it goes one bullet per degradation, saying what was promised,
what was delivered instead, and why, or the single word **None**. The list gives the omission
floor's third row a mechanism instead of a judgment call: the review seat enumerates the
degradations and checks that each has a consequence line in the owner half.

## Issue linking

GitHub's closing-keyword parser is negation-blind. `Resolves #NNN`, `Closes #NNN`, and `Fixes #NNN`
close the issue on merge even inside a sentence that says they do not. For an issue the PR must not
close (a parent epic, a tracking issue, a "part of" link), use a non-closing verb: "addresses",
"part of", or "relates to". Reserve the closing keywords for the issue this PR genuinely closes. A
stack layer names its own sub-issue with a non-closing verb until the stack merges
(`rubric/native-stacks.md` § Each layer is a sub-issue).

## Verifying the remote head

"PR ready" requires the remote branch head to contain every commit your receipts claim. After your
final `git push`, run `git fetch`, then `git merge-base --is-ancestor HEAD origin/<branch>`. The
review-fix commit is the usual straggler. A PR that claims a fix its pushed branch does not contain
is a claim without a receipt.
