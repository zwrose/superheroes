---
name: plan
description: Use after a `spec` is approved, to turn it into the technical `plan` (the *how*) for a work-item — overall approach, architecture, components & interfaces, data flow, key decisions, risks. This is superheroes' Plan phase: it runs LARGELY AUTONOMOUSLY (the owner lives in the *what*; the *how* is automated away), pausing ONLY to escalate genuinely consequential decisions in plain-language pros/cons. Produces the `plan` definition-doc and runs review-plan. Not for requirements (that is `discovery`) or step-by-step tasks (that is `tasks`).
---

# Plan

Turn the approved **`spec`** into the **`plan`** definition-doc: the technical *how* —
approach, architecture, components, data flow, the key decisions and their alternatives.
This is the middle of the superheroes loop (Discovery → **Plan** → Tasks → Build →
Verify → Integrate).

**Plan runs autonomously.** Discovery is owner-co-authored (the *what*); Plan is the
opposite — you decide the *how* on the owner's behalf and **automate it away**, pausing
**only** to escalate the genuinely consequential decisions (the rubric in step 3). There
is **no mandatory owner approval gate**: the escalations are the owner's touchpoints, and
the PR is the final human gate later. The plan doc's audience is the **build** (agents /
engineers), so it may use technical language — unlike the spec.

**Precondition:** an approved `spec` exists for the work-item. Plan builds on it; do not
plan from an unapproved or absent spec.

## Checklist

Create a TodoWrite item for each step:

1. **Load the approved spec + ground in the codebase & calibration**
2. **Design the technical approach** (autonomous)
3. **Apply the escalation rubric** — escalate the consequential calls, record the rest
4. **Author the plan** via the template
5. **Self-review**
6. **review-plan** (automated gate; graceful degradation)
7. **Ready for Tasks**

## The steps

### 1. Load the approved spec + ground

- The spec is at `docs/superheroes/<work-item>/spec.md` (the **work-item slug is the
  directory name**). Read it fully: purpose, who it's for, the functional requirements,
  the significant unhappy paths, non-functional requirements, constraints, the UI/UX
  handoff, `size`, and the definition of done.
- **Confirm it's approved** (the owner signed off / `gates.review` passed). If it isn't,
  stop — Plan builds on an approved spec.
- **Ground the approach in reality:** explore the codebase (existing stack, patterns,
  conventions in `CLAUDE.md`) and read the calibration profile / `patterns.md` when
  present (the project's stack, threat model, and current best-practice opinions). The
  plan must fit the **existing** project, not a green-field assumption.

### 2. Design the technical approach (autonomous)

Design: the overall approach; the architecture/shape; components and their interfaces;
data flow and the data model; how each spec requirement (functional **and**
non-functional, plus the unhappy paths) is met; and the risks. Reference the spec's Claude
Design handoff when describing how the UI gets built.

**Default = ACT.** Decide the *how* yourself — this is automated away from the owner. You
do **not** ask about routine technical choices (framework, libraries, file layout,
internal patterns); decide them and record them in *Key decisions*. Prefer the **simplest**
approach that meets the spec (YAGNI — nothing the spec doesn't justify), and prefer
**reversible / standard / swappable** choices (wrap external dependencies behind a clean
boundary) so fewer decisions are one-way doors.

### 3. The escalation rubric — when to pause for the owner

Default = ACT autonomously. Escalate a decision to the owner **only** when it clears the
**two-axis gate**: **high consequence (hard to reverse / wide blast radius) AND a call the
owner can actually weigh (cost, speed, risk, data, user experience, future flexibility) —
or your confidence is low on something consequential.**

**Escalate if the decision trips any trigger:**

1. **One-way door** — hard or expensive to undo later: the **data model/schema**, the
   persistence engine, a **public API/contract** others build against, the **core
   framework**, the **auth/permission model**, service boundaries. *(Hard floor: never
   take an irreversible/destructive action, and never merge/deploy, without sign-off.)*
2. **Spends money or usage** — adds a paid service, an ongoing cost, or materially
   increases usage. *(Hard floor: never silently spend.)*
3. **Security / privacy / data-handling** — decides where personal/user data lives, who
   can access it, or how it's protected (including data residency).
4. **Vendor lock-in** — commits to a vendor/service that would be slow or expensive to
   leave.
5. **Product call in disguise** *(the master filter)* — rephrased as a plain trade-off,
   does the owner have a real preference about cost, speed, quality, UX, or risk? If yes,
   it's theirs even when it looks technical. If the only honest framing is jargon they'd
   have to trust you on, it isn't — decide it.
6. **Surprise / off-intent** — you'd be departing from the spec's stated intent or scope,
   or the owner would be surprised this happened without being asked. *(Principle of least
   astonishment.)*
7. **Low confidence on something consequential** — the input is ambiguous or you're filling
   a gap the spec never specified, **and** the decision is hard to reverse / wide blast
   radius. **Probe first** (read more code, re-read the spec); escalate only if still unsure.

**Do NOT escalate (record-only):** decisions that are architecturally significant but
**engineering-internal** — framework/library/pattern choice, internal structure,
build/deploy setup, internal decomposition — when they're reversible, cost nothing, and
expose no data. The owner has no basis to choose and asking is just noise. **Record them
in *Key decisions*; never interrupt the owner with them.**

**Keep escalation proportionate:**

- **Two-axis gate, not one.** High consequence AND (owner-weighable OR low-confidence). A
  reversible, no-cost, high-confidence pure-tech call is **never** escalated, even if it
  feels important.
- **Probe before pinging.** Resolve uncertainty with one cheap, reversible step before
  escalating.
- **Batch.** Collect escalations and present them at **one moment** (end of planning)
  rather than interrupting serially — escalate mid-flow only when a decision blocks
  further design.
- **Budget.** If you're escalating on most runs, the threshold is too low — recalibrate
  toward ACT.

**How to present an escalation** (use `AskUserQuestion`):

- One decision, stated as a **what**, no jargon.
- Pros/cons in **owner-currency** — money, time, risk, data, user experience — never
  technical detail they'd have to take on faith.
- Give your **recommended** option first (marked) with the reasoning, so the owner can
  confirm in one step but still genuinely choose.
- **Say whether it's reversible:** "we can change this later" vs "this is hard to undo" —
  the single most useful thing for the owner to weigh.

Record every **escalated** decision and the owner's call in *Key decisions & alternatives*.

### 4. Author the plan

The plan **reuses the spec's frozen work-item slug** (never mint a new one) and inherits
its `size`. Resolve the path at the repo root and emit the §3.1 frontmatter via the lib
(`docType: plan`, parent = the spec):

```bash
ROOT=$(git rev-parse --show-toplevel)
WORK_ITEM="<the work-item directory name>"
SIZE=$(grep -m1 '^size:' "$ROOT/docs/superheroes/$WORK_ITEM/spec.md" | sed 's/^size: *//')
PLAN=$(python3 "${CLAUDE_PLUGIN_ROOT}/lib/definition_doc.py" path --work-item "$WORK_ITEM" --doc plan --root "$ROOT")
python3 "${CLAUDE_PLUGIN_ROOT}/lib/definition_doc.py" frontmatter \
  --doc plan --work-item "$WORK_ITEM" --size "$SIZE" --parent-item "$WORK_ITEM"
```

Fill `${CLAUDE_PLUGIN_ROOT}/templates/plan.md`: replace `{{frontmatter}}` with the emitted
block, set the title, fill every section, and **strip the `<!-- AUTHOR GUIDANCE … -->`
comment**. Map every spec requirement in *How the requirements are met*; log every
significant decision (escalated or not) with its reversibility in *Key decisions*. Write to
`$PLAN`.

### 5. Self-review

Look at the written plan with fresh eyes; fix inline:

- **Coverage both ways:** every spec requirement (functional, non-functional, unhappy
  paths, constraints) is addressed, and nothing in the plan lacks a spec basis (no
  gold-plating / scope creep).
- **Sound + minimal:** the simplest approach that meets the spec; reversible/standard
  choices preferred.
- **Decisions recorded:** every significant decision is in *Key decisions* with its
  reversibility; every escalation and its outcome is captured.
- **No missed escalation:** scan for any hard-to-reverse **and** owner-weighable decision
  you decided silently — that's an escalation you missed; go back and escalate it.
- **Placeholders & guidance:** no `{{…}}` or leftover `<!-- AUTHOR GUIDANCE … -->` comment
  remains.

### 6. review-plan (automated gate)

Run review-crew's **`review-plan`** on the authored plan and address its findings. **If
`review-plan` is not available in this project**, say so and proceed — the self-review
(step 5) stands in. Never fabricate a review result.

### 7. Ready for Tasks

Plan authored + review-plan passed → the work-item is ready for the **Tasks** phase.
Plan is autonomous + escalate-only: there is no separate owner-approval gate (the
escalations were the touchpoints). Hand off; do **not** start `tasks` yourself.

## Rationalization table

| Excuse | Reality |
| --- | --- |
| "I'll ask the owner which framework" | Pure-tech and reversible — decide it, record it. Don't nag. |
| "This decision is important, escalate it" | Important ≠ escalate. Two-axis gate: consequence **AND** owner-weighable. |
| "I'll just add the paid service" | New cost is a hard floor — escalate. Never silently spend. |
| "The data model is obvious" | The data model is a one-way door — if there's a real trade-off, escalate it. |
| "I'll escalate each call as I hit it" | Batch them into one moment; serial interrupts erode trust into rubber-stamping. |
| "I'll design beyond the spec to be safe" | YAGNI. Nothing the spec doesn't justify; the plan covers the spec, no more. |
| "Owner approved the spec, get the plan signed off too" | Plan is autonomous + escalate-only — no mandatory gate; escalations are the touchpoint. |
