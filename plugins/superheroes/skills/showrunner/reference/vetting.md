# Contents

- [Vetting — the mechanism behind duty 4](#vetting--the-mechanism-behind-duty-4)
- [Order-quality accounting](#order-quality-accounting)
- [Dispatch provenance against engine doctrine](#dispatch-provenance-against-engine-doctrine)
- [The collector — pointer, ordinals, and age](#the-collector--pointer-ordinals-and-age)
- [The merged-PR backstop](#the-merged-pr-backstop)
- [The collector preamble](#the-collector-preamble)
- [The owner-half slot — states you will meet](#the-owner-half-slot--states-you-will-meet)
- [A gate needs its unlock citation](#a-gate-needs-its-unlock-citation)
- [Sequential orders need a commit between them](#sequential-orders-need-a-commit-between-them)
- [Vet-time escalation](#vet-time-escalation)
- [Timing follows the show-it level](#timing-follows-the-show-it-level)

# Vetting — the mechanism behind duty 4

This page is reference for the advisor at vet time. Duty 4 of the Showrunner charter states the
rules; this page holds the mechanism that fires only while you vet. The receipt's shape lives in
`skills/showrunner/reference/vet-receipt.md`, and the owner-call contract lives in
`skills/showrunner/reference/owner-decisions.md`.

## Order-quality accounting

**Record it from the PR's dispatch-provenance at every vet.** Record **orders dispatched, rework
orders, and each blocking review finding's attribution** — order quality, implementer execution, or
the orchestrator's own integration or assembly (external or unknown where none fits). Track the
**order-vs-implementer subset** against a baseline of about 5:1.

Also record:

- **Park/refusal rate** — how often builders parked or refused, and whether each was correct.
- **Vet receipt-integrity catches** — how often the vet caught a claim that did not reproduce when
  re-run against the world.

Each accounting record **names its window**. **Zero of either is a signal to inspect, never a clean
sheet.** Both guards are prose: if a future model is more agreeable, either rate can fall to zero
and read as a clean batch. The accounting lives in the **durable batch record**, not session memory.
**Inspect** means re-reading a sample of that batch's park and vet receipts, not merely noticing the
zero. It is standing accounting you keep, not a machine count.

Why these two and not the panel: **review panels check the diff against the brief, never the brief
against the world**, so a bad advisor premise is invisible to them. A third guard, the **panel
confirmation-rate line**, inspects the verifiers' agreeableness the same way and lives in
`skills/showrunner/reference/vet-receipt.md`.

Standing accounting makes the work-order authoring rules' effect measurable over time, and tells
you when a build's defects point at order quality rather than the engine. An **owner-half omission
caught at vet** attributes to the **orchestrator's own integration/assembly**, so systematic
under-statement surfaces as a rate rather than an anecdote.

## Dispatch provenance against engine doctrine

Vet dispatch provenance against engine doctrine (CONVENTIONS §7.5). A provenance row showing a
non-first-party model dispatched through the cursor CLI, or a fable tier on an external engine, is
a **defect to catch at vet** — not a builder judgment call to accept.

## The collector — pointer, ordinals, and age

**Locating the collector is part of the duty.** Record its issue pointer in durable memory the first
time you open or find it. If you cannot resolve it, the pending field says so as a **disclosed
degradation**, never a bare `None`, which is indistinguishable from an empty collector. Ask the
owner for the number rather than opening a second collector: a duplicate orphans everything the
first one holds.

**An unresolved pointer loses nothing.** When the owner cannot supply the pointer, record the item
and the disclosed degradation in the vet receipt; **no duplicate collector is opened**. Every
pending item also lives in the receipt of the vet that proposed it. An item recorded in a receipt
this way **carries the ordinal of the vet that proposed it**. When the pointer is later resolved,
the deferred append **preserves that original proposing ordinal** and never re-stamps it with the
later vet's ordinal, so the item's age keeps counting from when it was proposed and the age-2
escalation still fires on time.

**Each entry carries three things:** **what it is**, **your recommendation**, and **the proposing
vet's ordinal, stamped on it immutably**. It is **struck when the owner rules** — closing or
declining an item removes it from the collector — and nothing re-numbers what remains.

**Age is a subtraction over ordinals, never a count of artifacts.** Receipts are edited in place,
so they are neither a monotonic register nor one-per-vet, and every counting rule fails on that.
Every vet has a **monotonic ordinal** — one integer per vet, per project — kept in durable memory
beside the collector pointer and **also written into each receipt**, so the sequence survives a
lost memory. The next ordinal is **one more than the highest appearing in the collector or the
receipts**. Carrying an item forward never re-stamps it. Age is `this vet's ordinal − the item's
ordinal`. **The escalation is owed at 2 or more:** an item that old is evidence the owner batch is
not happening, and the receipt says so plainly rather than re-listing as though carrying were
normal. **An item the reconciliation surfaces means the primary path failed for that item** — not
routine throughput.

## The merged-PR backstop

**At vet, grep merged-PR bodies for the Follow-ups for the advisor heading** and reconcile against
the board. The workhorse charter standardizes the heading; `<!-- superheroes:build-record -->` is
its grep anchor. You may run `vet_slot.py check --pr <n> --repo <owner/name>` per PR. It compares
the build record's followups marker with the receipt's dispositions marker, and it flags a PR
**closed** unmerged whose followups marker is not `none` and that has no vet receipt. Those
follow-ups carry into the superseding PR's build record in the carry format the workhorse charter's
§11 defines; that section is the one home for the bullet shape.

## The collector preamble

**Install the contract's distilled preamble at the top of the collector issue body, above the
items, and refresh it when it has drifted or is missing.** The canonical snippet, its markers, why
placement matters, and the replace-region and malformed-marker rules live in
`skills/showrunner/reference/owner-decisions.md` § The collector preamble — canonical snippet. When
the collector pointer cannot be resolved, record the preamble duty as a **disclosed degradation** in
the vet receipt — never a silent skip, and never a second collector.

## The owner-half slot — states you will meet

**A heading without its marker is a failed stamp.** A body that carries the `## Advisor vet`
heading without the advisor-vet marker is a current-contract builder that failed to stamp. Re-stamp
the marker and write into the existing slot; that is **not** retroactive creation.

**A missing heading is ambiguous — resolve it against your own receipt comment.** A missing heading
may be a genuine pre-contract PR or a current-contract body rewrite that dropped the whole slot.

- **A receipt exists** → the slot was dropped. Restore it as a dropped write, per the check below.
- **No receipt comment** → a genuine pre-contract PR. **Create the slot at vet**: the
  `## Advisor vet` heading plus the advisor-vet marker, then write into it.

Retroactive creation applies **only** to pre-contract PRs, never as a way to re-seed a slot whose
advisor write was dropped.

**The reminder is the one builder text you remove.** It is not an exception to "never the
builder's prose". If you find your verdict and the reminder both present, the verdict wins: delete
the reminder on that read.

**Check the slot whenever you next read the PR's body** — a re-vet, a re-review, or the read before
handing it back, not only a formal re-vet. Compare its text against your **most recent** vet receipt
comment, your canonical copy, not merely whether the marker is there. A rewrite can:

- drop your text and re-seed the builder's reminder (marker present, reminder back — which reads
  exactly like a vet that has not happened yet);
- drop the marker with your text (marker gone);
- carry an older copy forward over a newer one (marker present, text stale — invisible to a marker
  check);
- drop your text and the marker together (no marker at all — which a pre-contract body also looks
  like; a receipt already posted means this is a dropped write).

Re-write your text when any of those holds, and **re-stamp the marker only when it is actually
gone**. Hand edits before `vet_slot.py write` — re-stamping, pre-contract slot creation, legacy
follow-up keying — are ruled in the register in `skills/showrunner/reference/vet-receipt.md`.

## A gate needs its unlock citation

A PR that adds a **gate, hook, or enforcement mechanism** must name, in its brief, the ratified
precondition that unlocks it and the evidence it is met. **A missing citation is a finding in its
own right**, in any project. When the project being vetted is the superheroes source repository
itself, cite the unlock condition in the anti-opportunities ledger (`LEDGERS.md` §2).

## Sequential orders need a commit between them

A build that ran sequential orders against one worktree should show a commit between them in its
artifacts. Uncommitted work a later order could have wiped is a finding.

## Vet-time escalation

**You may escalate a full or light PR to a full panel before merge.** This turns a wrong lane call
from a shipped defect into a late review, and it covers a known blind spot: thin tests on large,
visibly-working code are invisible at routing and obvious at vet.

**Triggers:**

- the diff touches quiet-failure surfaces the issue did not reveal;
- it came in much larger than assumed;
- the stated reasoning does not hold against the diff;
- the tests look thin for the size;
- it moved a line the issue implied it would sit inside.

**Proportionality:** where the doubt is narrow, a **focused read-only panel** is proportionate
against a full panel's 15–23 — for example, `/superheroes:review-code --review-only --focus
<notes>` passes the doubt to every specialist without the fix loop. Or dispatch a **single-seat
reviewer** with the doubt stated. **The vet is the backstop for lane calls in both directions.**

## Timing follows the show-it level

**The vet is async by default; what binds you is the show-it level, not attendance.** The
presentation call (duty 5) already says when the owner must *see* something, so the vet's timing
follows from it.

- **say it** and **nothing to see** are fully async.
- **show it @ `link`** is fully async — the environment outlives the session.
- **show it @ `running`** means your window is this session's. Say so in the receipt **and** in the
  owner half: a spot-check surface that dies at session end is a disclosed **degradation**.
- **show it @ `command`** is async, but **you must have run the command yourself** and written the
  exact drive-to-state path. Instructions nobody executed are reconstruction with extra steps.
- **attended** and **none** remain the honest floor.
