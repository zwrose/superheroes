<!-- escalation-version: 5 -->
# escalation-base

How a superheroes skill discloses a call in its autonomous phases: which of three modes it uses,
and how it records or hands back. Shared by every skill's interventions step (the escalation
analogue of `review-base.md`). Stack-neutral and universal.

**Whose call it is comes from the owner-vs-craft line.** Sort every call by
[`owner-vs-craft-line.md` § How a call is sorted](owner-vs-craft-line.md#how-a-call-is-sorted).
This file states no rule of its own for whose call a choice is; it says how each kind of call is
disclosed.

`escalation-version` (top of file) is the staleness signal; bump it on any semantic change.

## The three modes

- **PROCEED** — a [craft call](glossary.md#craft-call): act, and record it in the skill's normal
  place for the owner's veto. The default for a craft call.
- **NOTIFY** — a craft call whose cheap undo closes at a point the run will pass (a merge, a
  deploy, a release): act on it, and surface it as a flagged decision recorded for the owner's
  veto, with an **undo path and an expiry** ("I did X because Y — undo before Z"). NOTIFY
  **discloses without waiting** — the run continues after the disclosure lands in the durable
  artifact.
- **GATE** — an [owner call](glossary.md#owner-call), or any action on the hard floor: stop, write
  the decision down with its full owner-facing framing into the skill's durable artifact, and hand
  back — **never wait for an answer**. GATE **does not act** — that is the one axis on which it
  differs from NOTIFY. Both disclose; neither waits.

A craft choice that carries an owner consequence stays a craft call; the consequence goes to the
owner as its own GATE, per
[`owner-vs-craft-line.md` § A craft choice that carries an owner consequence](owner-vs-craft-line.md#a-craft-choice-that-carries-an-owner-consequence).

## Choosing a mode (apply in order)

1. **Hard floor — unconditional GATE, no judgment.** If the action is on the floor (below), GATE
   regardless of how the call sorts. When unsure whether an action is on the floor, treat it as on
   the floor (coarse and conservative).
2. **Sort the call by the line.** An owner call → **GATE**. A craft call → **PROCEED**, or
   **NOTIFY** when its cheap undo closes at a point the run will pass.
3. **Batch the hand-backs.** Write every GATE of a run in one consolidated write-down at a logical
   boundary, never as a running commentary.

## The hard floor (always-GATE)

The floor is safety that sits beside the line: an action on it GATEs even when the call itself
sorts as craft.

- touches secrets / auth / access-control
- deletes or migrates data
- exfiltrates data or secrets to any external sink (even a free one)
- spends money / hits a paid or rate-limited external API
- irreversible git/infra: push to a protected branch, force-push / history-rewrite, merge, deploy
- crosses a trust boundary (runs external/untrusted code) or degrades security/observability
- changes public-facing behavior / shared resources others depend on
- modifies its own control system at runtime — mutating the live escalation rubric, the floor, or
  the loop-enforcement state that this run is currently executing under: control material the run
  has loaded and will re-read or re-invoke before it finishes. The loop driver resolves its
  resource root from its own module path and is re-invoked from disk each phase, so a mid-run edit
  to loop source or rubric in the build worktree changes what the same run loads on its next phase
  and stays on this floor. No ratified issue, work order, or build-worktree location exempts such an
  edit from this item.

**Global invariant (above the list):** the agent may **never** grant itself authority or bypass a
gate. Skipping or auto-resolving its own GATE is self-granting and is forbidden.

## Recording a decision (NOTIFY and GATE both)

Every NOTIFY and GATE decision is recorded in the skill's existing surface with: **What** (one
line, owner-currency) · **Why** (grounded: "the spec says…", "the tests require…") ·
**Alternatives** (≥ the runner-up) · **Reverse path** (how to undo) · **Expiry** (until when it's
cheaply reversible — "undo before merge / before deploy") · **Confidence** (optional; a
low-confidence NOTIFY stands out).

**Verification trace.** A PROCEED, NOTIFY or skip that rests on "I verified it" cites **what** it
verified against (the spec line, the test, the source).

## Writing a GATE into the durable artifact

A recipe, in order — write all three parts into the skill's durable artifact (the review
presentation, the PR body, the dispatch summary — whichever that surface already owns), not into a
live prompt:
1. **The decision & why it matters** — one plain `what`, no jargon, and the owner-currency stake
   (money / time / risk / data / UX) riding on it.
2. **The options** — 2–3, each with a one-line pro and con in **owner-currency** (never technical
   detail they'd take on faith), and **whether it's reversible** ("we can change this later" vs
   "this is hard to undo").
3. **Your recommendation** — the option you'd pick and why, in one line, marked `(Recommended)`. No
   confident pick? Say so ("close call — your call") rather than feigning neutrality.

Write one consolidated write-down at a logical boundary rather than a running commentary — batch
multiple GATEs into a single artifact section; never interrupt serially across partial writes.

## Scope

This rubric governs the **autonomous phases** (plan → tasks → build → verify → fix). It does **not**
govern **discovery**: discovery is *elicitation*, not escalation — the owner co-authoring the *what*
is the point, and its one-question-at-a-time dialogue is not an escalation to be minimized. That
exclusion is consistent with the owner-presence ruling: discovery is conversation-driven, and the
owner's words in the current turn are the hearing event — not a detected state.
