# Contents

- [What this file is](#what-this-file-is)
- [The three-slot skeleton](#the-three-slot-skeleton)
- [The Anchor slot](#the-anchor-slot)
- [The build-ready block](#the-build-ready-block)
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
to contain `ruling` or a date is a perfectly good `Anchor (receipt):`.

A slot header inside a fenced code block is not a slot header — so a body that only shows the
skeleton in an example does not accidentally satisfy it.

### Shape, not resolution

What is checked at **build-ready marking** is that the header **declares** exactly one
recognized kind; whether that anchor **resolves** is a **different, later check owned by
another work item**.

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
