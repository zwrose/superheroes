# Contents

- [Handback: the ready PR's body](#handback-the-ready-prs-body)
  - [The owner half](#the-owner-half)
  - [Commands the owner runs](#commands-the-owner-runs)
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
  risks, costly disclosed degradations (§ Disclosed degradations sorts them), deferred DoD rows, and
  any direct question the builder has for the owner. The omission floor's three rows are keyed on
  severity, not on the disposition label. Each finding the review record leaves for the owner (its
  `leftForOwner` list) gets one line here that carries its record id, byte for byte, and its title, with
  its consequence around them: a paraphrase that drops the id does not name it. Every break-it test the review record shows as
  `not run: transit-redacted` is named here as a missing proof. When there are genuinely none, write exactly **None**, the same word *Follow-ups for the advisor* uses.
- **`## How to see it`.** On a show-it PR, read the project's `## Show-it surface` declaration in
  `core.md` for the level and shape, then carry the concrete instance here. An absent declaration
  means level `none`, disclosed. The section carries the entry point (the URL or the command) and
  the drive-to-state instructions: the shortest exact path from the entry point to the thing being
  judged, transient states included. An entry point that is a database or Keychain command is a file
  on the branch, named by the one command that runs it (§ Commands the owner runs).

An honest entry point of `command`, `attended`, or `none`, or a `core.md` with no `## Show-it
surface`, is a disclosed degradation. It sorts **costly**, because the owner loses the promised
direct look. It gets one bullet under the degradations marker and a matching consequence under
`## What we're accepting`, never a silent **None** on the floor's third row. The ranked entry-point
levels and the presentation standard live in `rubric/review-discipline.md` § Presentation standard
(show it / say it / nothing to see).

## Commands the owner runs

A command block the owner is asked to run that names a database tool or reads a Keychain item lives
only in a committed file on the PR's branch, so the review panel reads it like any other changed
file. The PR body points to that file and tells the owner to run the file (`bash <path>`) rather than
paste its lines, because a pasted block can run differently in the owner's shell. Whether the file
stays after merge (at an existing `ops/` or `scripts/` path) or is removed before merge is the
builder's call per PR, disclosed in the body. No new home is created.

`vet_slot.py handback` refuses a body that holds a fenced shell block (`bash`, `sh`, `zsh`, `shell`,
`console`, `shell-session`, `sh-session`, `shellsession`, `terminal`, `shell-script`, `ksh`, `fish`,
the plain-text labels `text`, `txt` and `plaintext`, or no language, including one nested in a list or
a blockquote) whose code names `mongosh`, `mongo`,
`mongodump`, `mongorestore`, `psql`, `pg_dump`, `pg_restore`, `mysql`, `mysqldump`, `redis-cli` or
`sqlite3`, or a Keychain read (`security find-generic-password`, `security find-internet-password`),
with `owner-command-in-body`, and the refusal names the block. Shell comments are not read, except a
comment that holds a `$(…)` or backtick substitution. Inline code and non-shell fences (`json` or `diff`, say) pass, so "run
this test" stays in the body. A shell block that only mentions a tool (`pytest -k psql`) is refused
too, so move it into the file or reword it. A block wholly inside an HTML comment does not render and
is not read.

## The advisor-vet slot

You stamp the `<!-- superheroes:advisor-vet -->` marker so the advisor does not have to on the
normal first write. The advisor still re-stamps it when a body rewrite dropped it, and stamps it
itself on a body that predates this contract. The advisor's write replaces the reminder comment,
which makes the slot's state readable from the body alone:

**The slot span is the advisor's alone.** Nothing of yours goes between the `advisor-vet` marker and
the `<!-- superheroes:build-record -->` marker except the reminder comment. The advisor's write
replaces that whole span, so the DoD table and every other marked section sit below the build
record. `vet_slot.py` refuses with `slot-span-foreign-content` on a body that has another
`superheroes:` marker line in the span, and its `handback` verb catches it before you hand back.

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
  attribution as a standing accounting duty. Each dispatch row also carries a **refusals** column.
  It lists the refused or denied commands that dispatch reported, taken from the terminal result's
  `refusals` (a `dispatch-write` or native `close` result) or from an implementer's or seat's
  returned refusals list, and a route taken under the stop rule's exception is listed with its
  refusal. The column reads `none` when the dispatch reported none. A build where no
  dispatch reported any may write a single line, `Refusals: none`, in place of the column.
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

**Check the markers before the PR is ready, and after every body rewrite:** run
`python3 -B "${CLAUDE_PLUGIN_ROOT}/lib/vet_slot.py" handback --body-file <body.md>` on the composed
body before you open the ready PR (or `--pr <n> --repo <owner/name>` on an open one). It reads the
body with the advisor's own parser, so a refusal (`markers-invalid`, naming the marker: missing,
hyphenated as `follow-ups`, repeated, or malformed) is a write the advisor's slot tool would refuse
too. `handback` also refuses `owner-command-in-body` (§ Commands the owner runs). Fix the body and
re-run until it prints `"ok": true`; once your lane ends, nobody can.

Before the ready marking, also run `python3 -B "${CLAUDE_PLUGIN_ROOT}/lib/vet_slot.py" handback --pr <n>
--repo <owner/name>` on the pushed PR, after its review record is written. It reads the latest review
record and refuses `leftover-not-accepted`, naming each missing id with its title, while *What we're
accepting* does not name every `leftForOwner` finding by its record id and title in one line, and
`review-record-unreadable` when no record can be read; the advisor's READY slot write runs the same
check (`lib/leftover_accepting.py`, its one home). On a stacked layer it refuses `stack-not-caught-up`, naming the
catch-up step (`rubric/native-stacks.md` § How a stack stays current), while the PR's pushed head is
behind its lower layer's current head, or `stack-lower-unreadable` when that head cannot be read.

A stacked light-lane layer has no draft stage of its own, so it takes one for this check: push, open
the PR as a draft, run `vet_slot.py handback --pr <n> --repo <owner/name>` on it, fix and re-run until
it prints `"ok": true`, then mark it ready.

When a PR closes or is superseded before its vet, carry its follow-ups into the superseding build
record, each under the next unused FU number (in the marker too), with its origin as text:
`- FU<n> [<class>] (from #N FU<m>) <text>`.

## The size tripwire row

§4's size step fills this row. After a mid-build merge of the base branch, `N` counts from the merge
base of the head and that branch (`git merge-base HEAD <base branch>`) only when the fold's
`sizeTripwire` reads `status: "ok"` with `countedFrom`, so the base branch's own lines are not the
build's. When it reads `indeterminate` with `size-base-ref-contains-head`, or the merge base holds
the build's own commits (the oldest commit of `git rev-list --first-parent --reverse <base>..HEAD`
is its ancestor), count from the build's original base instead, which overcounts the merged lines
(the safe direction), and say why in the row. It takes one of these forms:

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
issue or spec. It sits below the build-record marker, never in the advisor-vet slot span. It has one row per Definition-of-Done bullet, each **done** with an evidence pointer,
or **deferred** with a filed issue and a one-line reason. It differs from the review dispositions
table: that one grades review findings, and this one grades every specified claim as shipped,
deferred, or dropped. It is the honesty marker the review seat verifies (CONVENTIONS `§10.7`,
`rubric/review-discipline.md`).

## Disclosed degradations

Inside the build record, `<!-- superheroes:degradations -->` is immediately followed by
`### Disclosed degradations`. Under it goes one bullet per degradation, saying what was promised,
what was delivered instead, and why, or the single word **None**. The list gives the omission
floor's third row a mechanism instead of a judgment call.

Every deviation, harmless or costly, keeps its bullet under `### Disclosed degradations`, and each
bullet opens with `[costly]` or `[harmless]`. A bullet with no label reads costly. Sort each one by
this rule, in this order:

1. A deviation is **costly** when a promised check did not run, or work bypassed its owner
   engine (work the builder typed instead of an implementer is one), whatever caused it, a named
   harmless cause below included.
2. Otherwise it is **harmless**. The named harmless causes are the prompt-file pointer, the cloud
   fixer route, an unreadable host model, a classifier stop, and cloud platform limits; each sorts
   harmless only when step 1 does not apply. Cloud platform limits are the cloud session's own
   channel limits (no session messages, no comment deletion, no GraphQL reads), never a build check
   that could not run there.
3. Doubt sorts costly.

Only a costly bullet gets a consequence line under `## What we're accepting`. That line carries the costly bullet's text after its label, word for word, with its consequence around it; the merge sheet build refuses a body whose `[costly]` or unlabelled bullet has no such line, and names the bullet. On the PR body, a
harmless one stays only in the build record: it is never a body acceptance, so the merge sheet's
accounting never counts it. On the merge sheet, the advisor may mention a harmless one as a line of
the sheet's routine "What you're accepting" fold item; such a fold line is sheet-side, is not a body
acceptance, and needs no accounting entry. A costly one keeps its line, and so its sheet card, until
its fix lands. The review seat checks that each **costly** bullet has a consequence line in the owner
half.

## Issue linking

GitHub's closing-keyword parser is negation-blind. `Resolves #NNN`, `Closes #NNN`, and `Fixes #NNN`
close the issue on merge even inside a sentence that says they do not. For an issue the PR must not
close (a parent epic, a tracking issue, a "part of" link), use a non-closing verb: "addresses",
"part of", or "relates to". Reserve the closing keywords for the issue this PR genuinely closes. A
stack layer's pull request links its own sub-issue and the feature issue as
`rubric/native-stacks.md` § Each layer is a sub-issue, item 6 (Closure), says.

## Verifying the remote head

"PR ready" requires the remote branch head to contain every commit your receipts claim. After your
final `git push`, run `git fetch`, then `git merge-base --is-ancestor HEAD origin/<branch>`. The
review-fix commit is the usual straggler. A PR that claims a fix its pushed branch does not contain
is a claim without a receipt.
