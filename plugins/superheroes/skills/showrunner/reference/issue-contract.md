# Contents

- [What this file is](#what-this-file-is)
- [The three-slot skeleton](#the-three-slot-skeleton)
- [The Anchor slot](#the-anchor-slot)
- [The build-ready block](#the-build-ready-block)
- [Anchor resolution](#anchor-resolution)
- [Pre-doctrine issues](#pre-doctrine-issues)
- [The standing anchor-coverage vet row](#the-standing-anchor-coverage-vet-row)
- [The DoD bar](#the-dod-bar)
- [Currency](#currency)
- [The standing NFR vet row](#the-standing-nfr-vet-row)
- [Vocabulary (drift-tested)](#vocabulary-drift-tested)

# Issue contract

## What this file is

This file is the one home for the **issue contract** — the shape every routed issue body owes,
the DoD bar its bullets must meet, the currency duty that keeps bodies current, and the
standing NFR vet row graded at every child PR vet in a spec package. **The advisor reads it
when filing, routing, and vetting** — not from memory. The showrunner charter points here; this
file carries the detail.

## The three-slot skeleton

Every routed issue body carries exactly three required sections, **in order** — `Anchor
(<kind>):`, `What:`, `DoD:` — where `<kind>` is exactly one of `spec-section`, `receipt`,
`ruling` — and nothing else is required. The smallest conforming issue is **three filled
lines**; the skeleton adds no further required ceremony.

```markdown
Anchor (spec-section): <one anchor of the declared kind>
What: <plain-language scope and why>
DoD:
- <observable outcome a vet can grade from the handback's artifacts alone>
```

**Micro-route work is exempt.** Micro's safety is the owner's presence — the owner types the
fix or dictates the ruling — so it never carries this skeleton and never reaches the
build-ready check below.

A routed issue **missing a skeleton slot** is a **named vet finding** at vet time, not a
filing-time block (except the empty-Anchor rule at build-ready marking).

## The Anchor slot

The Anchor slot names the owner-approved decision the issue is downstream of. The kind is
**declared in the header** and **never inferred from the citation's prose**. Exactly one kind
per Anchor: a header declaring no kind, an unknown kind, or more than one kind is a
**malformed Anchor** and blocks build-ready marking exactly as an empty Anchor does.

The three recognized kinds:

1. **Spec section** — work-item slug + section heading + the anchor's as-of cursor
   `as-of amendment #N` (N is the count of entries in the spec's Amendments log at citation
   time; 0 when the log is empty).

   *Example:* `Anchor (spec-section): front-half-sdlc-core-6181ee · § The issue contract · as-of amendment #4`

2. **Receipt** — a live link to a review finding, incident record, bug report, or gate result.

   *Example:* `Anchor (receipt): https://github.com/zwrose/superheroes/pull/581#issuecomment-1234567890`

3. **Ruling** — an ISO date together with where the ruling was made.

   *Example:* `Anchor (ruling): 2026-08-07 · owner ruling · advisor channel, discovery sitting`

The citation text is **never read to decide a kind** — a bare receipt URL whose path happens
to contain `ruling` or a date is a perfectly good `Anchor (receipt):`. Declared kind tokens
are matched **exactly** — `Anchor (RECEIPT):` is `anchor-kind-unrecognized`, not a receipt
anchor.

A slot header inside a fenced code block is not a slot header — so a body that only shows the
skeleton in an example does not accidentally satisfy it. A slot header indented four or more
columns is not a slot header — CommonMark renders it as an indented code block, so a body whose
only `Anchor` line sits at indent 4 reports the anchor slot missing. Indentation is measured
in columns; a tab advances to the next multiple of four. A fence closes only on a matching
marker of the same character and at least the opening length, so a nested example inside a
longer fence stays fenced.

### Shape, not resolution

What is checked at **build-ready marking** is that the header **declares** exactly one recognized
kind. Whether that anchor **resolves** is a **different, later check** — it runs at build intake,
and its home is [Anchor resolution](#anchor-resolution) below.

## The build-ready block

Before marking an issue **build-ready**, run the issue-contract check against the issue body.
The advisor **declines the marking** when the check reports a refusal — naming the reason
token below. Micro work never reaches this check.

**Refusal reasons** (build-ready marking declined):

| Token | Meaning |
| --- | --- |
| `anchor-slot-missing` | The body has no Anchor slot header line |
| `anchor-slot-empty` | The Anchor header is present but the citation body has no word character |
| `anchor-kind-missing` | The Anchor header declares zero kind tokens (`Anchor:`, `Anchor ():`) |
| `anchor-kind-unrecognized` | The Anchor header declares exactly one token that is not an anchor kind |
| `anchor-kind-multiple` | The Anchor header declares two or more kind tokens |
| `body-unreadable` | The body file could not be read (path typo, permission error, or invalid encoding) |

Header-form refusals are reported before emptiness — when both a malformed header and an empty
Anchor hold, the reported token is the header-form refusal.

> This check is **advisory**. It computes the refusal and its reason and prints them; it never
> exits non-zero, never intercepts a command, and enforces nothing on its own. **The advisor's
> charter duty is what declines the marking.** It is not a mechanical enforcement boundary and is
> not claimed as one.

**Invocation:** write the issue body to a file, then run (from a plugin-cache install,
`ROOT_DIR` is `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}`):

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
python3 -B "$ROOT_DIR/lib/issue_contract.py" check-build-ready --body-file <path>
```

reading the JSON result from stdout.

**Empty What or DoD** are **reported but never blocking** at filing — they are graded at vet,
not refused at build-ready marking.

## Anchor resolution

Recording an anchor and **resolving** one are two different acts at two different times. The
build-ready block above grades the Anchor's **shape** at filing. This section is the **resolution**
test the **builder** applies at **build intake**, before any spend — the second of the three
layers. Its failure face is a **stop**, and the advisor's repair is the other half of that path.

**The three per-kind tests.** An Anchor carries exactly one anchor of its declared kind, and each
kind resolves by its own test:

- **Spec-section anchor.** It resolves when the spec's owner approval is recorded (`status: approved` with its `approved:` date), the cited section exists in the current body, and no substantive-class Amendments entry numbered greater than the anchor's `as-of amendment #N` names the cited section among its touched sections. Wording-class entries never stale an anchor. Entries are numbered by their order of addition to the log, oldest = 1 — the number is positional, not a field — so same-day amendments stay ordered, and the cursor test compares entry numbers, never dates.
- **Receipt anchor.** It resolves when the link is live.
- **Ruling anchor.** It resolves when the dated, owner-attributed record is reachable where the ruling was made and no later owner decision supersedes it.

A malformed Anchor — a header that declares no kind, an unknown kind, or more than one kind — and
an empty Anchor **do not resolve**: they stop intake exactly as a failed per-kind test does.

**The log side fails closed too.** The cursor leg reads as *no* substantive entry numbered greater
than N — a sentence that is trivially satisfied when there is nothing to read. So it does not pass
by default. If the spec carries no Amendments log at all, if the log cannot be read, if an entry is
missing its class or its touched-section list, or if the anchor's `#N` is greater than the number of
entries the log holds, the cursor leg **does not resolve** — it stops intake exactly as a named
substantive entry would. A leg you cannot complete never resolves an anchor.

**Why the cursor is a number and not a date.** The `as-of amendment #N` cursor names *how many*
entries the Amendments log held when the anchor was cited, so the entries that could have staled it
are exactly the ones added since — the ones **numbered greater than N**. Numbering is positional,
by order of addition, which is what keeps two amendments made on the same day ordered with respect
to each other. A reader who reaches for the dates instead gets the same answer most of the time and
the wrong answer on exactly the day it matters, silently. **The comparison is on entry numbers.**

**A `ruling` anchor never cites a conversational venue** — "the advisor channel," "a live
sitting" — because a venue name is not a record: a builder reading it has nothing to follow, and
the claim is a paraphrase nobody downstream can check. The ruling is captured where a builder can
read it: quoted verbatim with its date in the Anchor block or an owner comment on the issue itself,
or cited by exact permalink where a dated echo already exists on another durable surface. The
captured text *is* the record the anchor resolves to.

**Stop, report, repair — one path.** When a test fails, the **builder stops before any spend** —
no file in the repository changes — and reports on the issue which per-kind test failed and what
failed to resolve. The **builder never repairs its own anchor**. The **advisor repairs the route**:
**re-anchor** on a decision that does resolve, **re-route** the work, or **park it to the owner**;
the repair is recorded in the issue body, and the build resumes **only** on the advisor's word. A stop with
no repair is an abandoned issue, not a safeguard working; a build that resumed without the repair
is a process defect.

**What this layer does not do.** It grades the **issue**, never the diff — the layer that inspects
the diff is [the standing anchor-coverage vet row](#the-standing-anchor-coverage-vet-row). It adds
**no machinery over the Amendments log**: it reads that log's entry numbers, classes, and touched
sections as they already stand, and the log's own contract lives with the amendment machinery, not
here.

## Pre-doctrine issues

A **pre-doctrine issue** is one filed before this contract shipped: it carries no `Anchor (<kind>):`
slot, so [Anchor resolution](#anchor-resolution) stops the build at intake. A project adopting the
doctrine meets this across its open backlog at once, and the stop is working as designed — what
follows is how the advisor clears it. Both patterns below are field-proven; pick by how many issues
are in front of you.

**First: check for a prior ratified arrangement.** A project may already carry an adoption
arrangement its **owner ratified before this doctrine** — a **closed list** of issues, recorded with
that project's advisor seat, where that ruling was made; that seat's record is where a consuming
advisor reads the list back. What that list **keeps** is the owner's **decision**: the issues on it
are not re-litigated, not re-decided, and not re-surfaced to the owner. It does **not** keep them
out of the slot. **There is no grandfather exemption at the gate** — [Anchor
resolution](#anchor-resolution) refuses an Anchor-less body whatever ruled it, so a kept issue with
no Anchor would never build. Each kept issue therefore still **materializes** its resolving Anchor
when it comes up for a build, by the Pattern 1 retrofit below, with the ratified arrangement
supplying the Anchor's citation in place of a fresh owner sitting. The arrangement spares the
issue the *re-decision*, not the *slot*. Everything else takes the pass — so run the board pass
below only over the **remaining** open pre-doctrine issues. Where no such arrangement is recorded,
that remainder is the whole open backlog.

### Pattern 1 — the per-issue retrofit

Use it when **one** issue is about to be built. The advisor edits the issue body: the three slots go
**above** the original filing, which is preserved **verbatim** below a dated separator, so nothing
is lost and a later reader can tell the advisor's words from the filer's.

```markdown
**Anchor (ruling):** <ISO date> · owner ruling · <where the ruling is reachable>. Not superseded.

**What:** <plain-language scope and why, carried up from the original filing>

**DoD:**
- <observable outcome a vet can grade from the handback's artifacts alone>

---
*Original filing (<filing-date>), preserved verbatim below; skeleton slots retrofitted
<retrofit-date> during pre-doctrine repair (advisor edit, content unchanged).*

<the original body, byte-for-byte unchanged>
```

A `receipt` anchor substitutes for the `ruling` line wherever a live link — a review finding, an
incident record, a gate result — is the decision the issue is downstream of; the kind token in the
header changes with it.

Four things make it a retrofit rather than a rewrite:

- **The Anchor cites a decision that already exists.** Retrofitting is not the moment to invent an
  approval. Where no decision covers the issue, the repair is to route it to the owner — not to
  write an anchor for it.
- **The original body is preserved verbatim.** The separator carries both dates — when it was filed,
  when the slots were added — and states that the content is unchanged.
- **What and DoD are filled, to the bar.** Carry them up from the original filing; every DoD bullet
  still owes what [The DoD bar](#the-dod-bar) asks — an observable outcome, not an activity.
- **The check is green afterward, read from the JSON.** Run the build-ready check ([The build-ready
  block](#the-build-ready-block)) against the edited body and read `ok: true` with `reason: null`
  **out of the result**. Do not read the exit status: the check is advisory and **always exits
  zero**, and its refusal set covers the Anchor only — it reports an empty What or DoD without
  refusing. A body that passes the check with an empty DoD has moved the stop to vet, not cleared
  it.

**When the original filing yields no gradable DoD.** This is common on old issues, and it is not the
builder's to fix: the builder names the gap and stops, inventing no requirements. The advisor gets
the missing outcome from the owner, re-routes the issue, or parks it. A DoD written to make a check
pass is worse than an empty one — it looks graded and grades nothing.

### Pattern 2 — the board-pass grandfathering

Use it when the **whole backlog** needs clearing. In **one owner sitting**, walk the open issues and
rule on each — keep it, re-route it, or close it. That ruling is the decision each surviving issue
is downstream of. The steps:

1. **Make the sitting's record reachable before it is cited.** The ruling test in [Anchor
   resolution](#anchor-resolution) asks for a dated, owner-attributed record *reachable where the
   ruling was made* — so each ruling **stays at the surface the owner made it on**; the advisor
   channel is such a surface, and the issue carries an **exact permalink** into it, per issue.
   Copying a ruling onto the issue does not move where it was made. Only where that surface cannot
   yield a durably reachable record does the **owner re-rule on the issue itself** — and that new
   ruling, with its own date, is what the Anchor then cites. A date stamped on an issue whose ruling
   lives nowhere does not resolve.
2. **Give each surviving issue its resolving Anchor**, in the Pattern 1 shape — the Anchor header
   above a dated separator, the original filing preserved verbatim below it. The Anchor line names
   the sitting's date, the owner attribution, and the permalink from step 1. **A ruling yields the
   Anchor, not the What and DoD** — see the pickup step below for how those two arrive.

   **At pickup — completing a board-passed body.** When such an issue is actually taken up for a
   build, edit the body that is already there: insert **only** the `What` and `DoD` slots, in the
   canonical slot order, under the Anchor the sitting wrote. **No second Anchor, no second dated
   separator, and no re-preserving a filing this step already preserved verbatim** — a body may
   carry the Anchor slot exactly once, and a duplicate makes the last one win. This is the **pickup
   counterpart** to Pattern 1, not a second application of it: Pattern 1 is the *full* retrofit for
   a body carrying **no** Anchor, and re-running it here would produce exactly the duplicates just
   ruled out. Everything else Pattern 1 asks still holds — the two slots are carried up from the
   preserved filing and owe [The DoD bar](#the-dod-bar), Pattern 1's no-gradable-DoD branch governs
   when the filing yields none, and the build-ready check is re-read out of its JSON afterward.
3. **Confirm nothing later supersedes it.** The ruling test's last leg. A backlog issue whose scope
   a newer owner decision has since overtaken is re-ruled in the sitting, not grandfathered on the
   old date.
4. **Write the pass down where the sitting's rulings live.** Add the advisor's own dated note to the
   same durable surface step 1 made reachable, carrying the **sitting's date** and the **scope it
   covered** — which issues were walked — so a later reader can tell a grandfathered issue from one
   nobody has looked at. That dated note is the record: the approved spec's companion leg — a
   pass-done marker written into the project's calibration — was **owner-declined and never
   implemented**, so there is no such store operation to call and the note carries the pass alone.

The pass is cheaper than it sounds, because the ruling and the triage are the same act: an owner
walking a backlog is already deciding what survives. What the pass adds is writing each decision
down, dated, where it can be reached.

**Which to use.** A board pass first, then per-issue retrofits as builds come up — one lifecycle,
two moments. The sitting's ruling is what every surviving issue's **Anchor** cites, backlog-wide, in
one pass. Pattern 2's pickup step fills that issue's `What` and `DoD` later, when it is actually
picked up for a build — those two slots inserted into the body the sitting already anchored, never a
second Anchor. Pattern 1's full retrofit stays for the issue that reaches a build with **no** Anchor
at all. Where the original filing yields no gradable DoD, Pattern 1's branch above governs either
way — the gap is named, the build stops, and the advisor gets the outcome from the owner, re-routes,
or parks.

## The standing anchor-coverage vet row

At **every** PR vet — the third and last anchor layer, and the **only one that inspects the diff** —
grade whether the diff introduces **owner-perceivable new behavior that no approved decision
covers**: no spec section and no dated owner ruling, or a citation whose **scope does not reach**
the behavior. **The standing anchor-coverage row** is graded on every PR, exactly like the standing
NFR row below, so a PR with no flag means the row was graded and did not fire — never that nobody
asked.

When it fires, the flag is written **in plain language** — what the new behavior is, and that no
approved decision covers it — and it **reaches the owner in the owner half** of the PR body, not
only in the advisor's own receipt. What the owner is being asked to accept is precisely that they
are about to merge behavior they never approved; a flag that stops at the receipt has not reached
the person the rule exists for.

## The DoD bar

Every DoD bullet names an **observable outcome a vet can grade pass/fail from the handback's
artifacts alone**. A bullet describing an **activity** rather than an outcome does not
qualify — grading it would require asking a person or re-running the build, so it is a **vet
finding against the issue**.

**Bad** (activity — not gradable from artifacts):

```markdown
- Run the full test suite and fix any failures
```

**Good** (outcome — gradable from the handback):

```markdown
- `pytest` over `plugins/superheroes/lib/tests/` exits 0 on the PR head; the receipt names the command and its output
```

The bad bullet names work to do; the good bullet names what a vet can verify without re-running
the build or asking anyone.

## Currency

The advisor keeps every issue body current. The **spot-check** has **both halves** — a reader
who remembers only one half is the failure mode this section guards against:

1. **Whole-body match** — the **whole issue body matches the work's current state** (What and
   DoD included).
2. **One-hop anchor** — once the issue is build-ready, its **Anchor link resolves to the
   approved decision in one hop**.

**A stale What or DoD fails the spot-check even when the anchor link resolves** — passing (b)
does not excuse failing (a).

## The standing NFR vet row

At **every** child PR vet in a spec package, grade the three package-wide non-functional
requirements **by name with their fit criteria**:

- **Owner reading load** — every owner gate consumes only artifacts from the spec's named
  list; *fit criterion:* no gate requires reading an issue, brief, work order, or review
  internals.
- **Plain language** — every owner-facing artifact reads in plain language, ratified vocabulary
  glossed at first use; *fit criterion:* an owner-facing artifact that needs plugin-internal
  vocabulary to parse is a review finding.
- **Guidelines over trip-lines** — the two numbers (10 gradable lines; 5 amendments) are
  positioned everywhere as guidelines with disclosed overrides; *fit criterion:* no charter or
  gate turns either number into a hard block.

## Vocabulary (drift-tested)

The Python module `issue_contract.py` is the authoritative home for these tokens; this list is
checked against it.

**Slots** (in order):

- `Anchor`
- `What`
- `DoD`

The Anchor slot's rendered header form is `Anchor (<kind>):`.

**Anchor kinds** (exactly one per Anchor):

- `spec-section`
- `receipt`
- `ruling`

**Refusal reasons** (build-ready marking declined):

- `anchor-slot-missing`
- `anchor-slot-empty`
- `anchor-kind-missing`
- `anchor-kind-unrecognized`
- `anchor-kind-multiple`
- `body-unreadable`

**Slot statuses** (per-slot reporting in the JSON result):

- `missing` — the slot header is not present in the body
- `empty` — the slot header is present but has no content
- `filled` — the slot header is present and has content
- `unknown` — the body could not be read (`body-unreadable`); no slot reading was taken
