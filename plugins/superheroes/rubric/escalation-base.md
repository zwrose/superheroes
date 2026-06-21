<!-- escalation-version: 2 -->
# escalation-base

The source of truth for **when a superheroes skill escalates to the owner vs. decides
autonomously**, and **how** it records or asks. Shared by every skill's interventions step
(the escalation analogue of `review-base.md`). Stack-neutral and universal. If a skill's
prose conflicts with this file, this file wins. The deterministic floor + routing table live
in `escalation.py` (paired with this rubric as `loop_state.py` is paired with `review-base.md`).

`escalation-version` (top of file) is the staleness signal; bump it on any semantic change.

## The three modes

- **PROCEED** — act, record it in the skill's normal place. The default. Use when the choice is
  reversible/low-blast, or **verifiable by the agent itself** against spec/types/tests/code.
- **NOTIFY** — act on the best default, but surface a flagged decision the owner can veto, with an
  **undo path and an expiry** ("I did X because Y — undo before Z"). Use when the choice is
  owner-relevant but **reversible and safely defaultable**.
- **GATE** — stop, ask via `AskUserQuestion`, wait. Use only when the choice is the owner's
  value-call that can't be safely defaulted, **or** irreversible-and-unverified, **or** anything on
  the hard floor.

## Routing (apply in order)

1. **Hard floor — unconditional GATE, no judgment.** If the action is on the floor (below), GATE
   regardless of confidence. When unsure whether an action is on the floor, treat it as on the
   floor (coarse and conservative).
2. **Where does the ground truth live?** If the agent can check the answer against artifacts it can
   reach (spec, types, tests, the codebase) → **verify and PROCEED**; asking here is friction, not
   safety. If the truth lives only with the owner (intent, product taste, money/data, authority) →
   go to 3.
3. **Reversibility × confidence × owner-weighable.**
   - Owner-weighable (a real preference about cost/speed/quality/UX/risk) **and** (hard to reverse
     **or** low confidence on something consequential) → **GATE**.
   - Owner-relevant but reversible and high-confidence → **NOTIFY**.
   - Engineering-internal (no trade-off the owner would weigh) → **PROCEED**, record-only.
4. **Interrupt-cost discipline.** Probe before pinging (resolve with one cheap reversible step
   first). Batch GATEs to one moment. If you're GATEing on most runs, the threshold is too low —
   lean PROCEED/NOTIFY. Over-asking is a failure mode: it trains rubber-stamping.

## The hard floor (always-GATE)

- touches secrets / auth / access-control
- deletes or migrates data
- exfiltrates data or secrets to any external sink (even a free one)
- spends money / hits a paid or rate-limited external API
- irreversible git/infra: push to a protected branch, force-push / history-rewrite, merge, deploy
- crosses a trust boundary (runs external/untrusted code) or degrades security/observability
- changes public-facing behavior / shared resources others depend on
- modifies the safety machinery itself at runtime (the escalation rubric, the floor, the
  loop-enforcement state)

**Global invariant (above the list):** the agent may **never** grant itself authority or bypass a
gate. Skipping or auto-resolving its own GATE is self-granting and is forbidden.

## Recording a decision (NOTIFY and GATE both)

Every autonomous (NOTIFY) and escalated (GATE) decision is recorded in the skill's existing surface
with: **What** (one line, owner-currency) · **Why** (grounded: "the spec says…", "the tests
require…") · **Alternatives** (≥ the runner-up) · **Reverse path** (how to undo) · **Expiry**
(until when it's cheaply reversible — "undo before merge / before deploy") · **Confidence**
(optional; a low-confidence NOTIFY stands out).

**Verification trace.** An autonomous PROCEED/NOTIFY/skip that rests on "I verified it" must cite
**what** it verified against (the spec line, the test, the source). A decision with no citable
ground truth is not eligible for autonomy → it GATEs.

## Presenting a GATE (`AskUserQuestion`)

A recipe, in order — the message before the prompt lays out:
1. **The decision & why it matters** — one plain `what`, no jargon, and the owner-currency stake
   (money / time / risk / data / UX) riding on it.
2. **The options** — 2–3, each with a one-line pro and con in **owner-currency** (never technical
   detail they'd take on faith), and **whether it's reversible** ("we can change this later" vs
   "this is hard to undo").
3. **Your recommendation** — the option you'd pick and why, in one line, marked `(Recommended)`. No
   confident pick? Say so ("close call — your call") rather than feigning neutrality.

Keep the `AskUserQuestion` option labels crisp — the framing lives in the message above. Batch
multiple GATEs into one prompt at a logical boundary; never interrupt serially.

## Scope

This rubric governs the **autonomous phases** (plan → tasks → build → verify → fix). It does **not**
govern **discovery**: discovery is *elicitation*, not escalation — the owner co-authoring the *what*
is the point, and its one-question-at-a-time dialogue is not an escalation to be minimized.
