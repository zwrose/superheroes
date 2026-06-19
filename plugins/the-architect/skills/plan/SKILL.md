---
name: plan
description: Use after a `spec` is approved, to turn it into the technical `plan` (the *how*) for a work-item — overall approach, architecture, components & interfaces, data flow, key decisions, risks. This is superheroes' Plan phase: it runs LARGELY AUTONOMOUSLY (the owner lives in the *what*; the *how* is automated away), pausing ONLY to escalate genuinely consequential decisions in plain-language pros/cons. Produces the `plan` definition-doc and runs review-plan. Not for requirements (that is `discovery`) or step-by-step tasks (that is `tasks`).
---

This skill speaks in host-neutral actions. Resolve them to your runtime's tools via `hosts/<your-host>-tools.md` in this plugin — `claude-tools.md` on Claude Code, `codex-tools.md` on Codex.

# Plan

Turn the approved **`spec`** into the **`plan`** definition-doc: the technical *how* —
approach, architecture, components, data flow, the key decisions and their alternatives.
This is the middle of the superheroes loop (Discovery → **Plan** → Tasks → Build →
Verify → Ship).

**Plan runs autonomously.** Discovery is owner-co-authored (the *what*); Plan is the
opposite — you decide the *how* on the owner's behalf and **automate it away**, pausing
**only** to escalate the genuinely consequential decisions (the rubric in step 3). There
is **no mandatory owner approval gate**: the escalations are the owner's touchpoints, and
the PR is the final human gate later. The plan doc's audience is the **build** (agents /
engineers), so it may use technical language — unlike the spec.

**The loop resolves; it does not park.** A finished plan carries **no open questions**.
Every question routes to a resolution: an owner call → **escalate** (step 3); a genuine
unknown → a **Risk with a contingency**, de-risked first; a detail that's only clear
in-code → deferred to **Tasks**; a true blocker (the spec can't be met as-is) → **escalate
or loop back** to the owner/spec. You do not hand off a plan with a decision left open.

<HARD-GATE>
**Precondition: the spec is approved.** Plan builds on an approved `spec`; never plan from
an unapproved or absent one — it's the only guarantee an approved requirements baseline
exists before an autonomous build. **Verify it programmatically** (step 1), don't just
assert it: `gates.review: passed` is the machine-readable signal (set by `review-spec`, or
by discovery recording the owner's terminal approval when review-spec is absent); a
`pending` or `changes-requested` spec is **not** approved — stop.
</HARD-GATE>

## Design principles (the durable ones — apply throughout)

1. **State the trade-off, not just the choice.** Every non-trivial decision names what it
   optimizes for, the alternative it beat (including "use what's already here"), and the
   **downside being accepted**. A decision with no named downside is unexamined.
2. **Calibrate rigor to reversibility.** One-way doors (data model, public contracts, auth
   model, persistence) get deliberate care; two-way doors get a fast reasonable pick.
   Actively turn one-way doors into two-way ones (a seam, an adapter, a flag).
3. **Boring by default; novelty must earn its place.** Prefer proven tech and existing
   repo patterns. No microservices / event-sourcing / CQRS / queue / heavy framework
   unless a *present* constraint forces it. New tech states its failure modes.
4. **Deep modules, low coupling.** Simple interfaces over powerful implementations; high
   cohesion; push complexity down rather than out to callers.
5. **Reliability, scalability, maintainability are explicit** — never just "does it work."
   Name the likely faults and how they're tolerated; the load and the target; how it's
   operated, observed, and rolled back.
6. **Separate essential from accidental complexity.** Justify every layer. Where you can,
   design an error *out of existence* (idempotent delete, empty-not-error) instead of
   handling it.
7. **Grow it; don't big-bang it.** Validate the riskiest, most-irreversible parts earliest.

## Checklist

Create a TodoWrite item for each step:

1. **Load the approved spec + ground in the codebase & calibration**
2. **Design the technical approach** (the 9-move method, autonomous)
3. **Apply the escalation rubric** — escalate the consequential calls, record the rest
4. **Author the plan** via the template (right-sized)
5. **Self-review** (design quality + the failure-mode checklist)
6. **review-plan** (automated gate; graceful degradation)
7. **Record the plan gate → ready for Tasks**

## The steps

### 1. Load the approved spec + ground

Ground before you design — **bake in the durable, look up the volatile.**

- **Read the spec** at `docs/superheroes/<work-item>/spec.md` (the **work-item slug is the
  directory name**): purpose, who it's for, functional requirements, significant unhappy
  paths, non-functional requirements, constraints, the UI/UX handoff, `size`, definition
  of done.
- **Verify the spec is approved — programmatically, not by eye** (the HARD GATE above; an
  executing agent skips a prose check). Read `gates.review` and stop unless it is `passed`:

  ```bash
  set -euo pipefail
  ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
  ROOT=$(git rev-parse --show-toplevel) || { echo "not in a git repo" >&2; exit 1; }
  WORK_ITEM="<the work-item directory name>"
  # read-gate parses gates.review from the spec frontmatter via the lib (robust to
  # formatting; errors clearly if the spec is missing or malformed)
  REVIEW=$(python3 "$ROOT_DIR/lib/definition_doc.py" read-gate \
    --doc spec --work-item "$WORK_ITEM" --root "$ROOT") \
    || { echo "no readable spec for $WORK_ITEM — run discovery first" >&2; exit 1; }
  [ "$REVIEW" = passed ] || { echo "spec not approved (gates.review=$REVIEW) — stop; it needs the owner's approval (or review-spec) first" >&2; exit 1; }
  ```

  `gates.review: passed` is written by review-crew's `review-spec` when it runs, and —
  when review-spec isn't wired yet — by discovery recording the **owner's** terminal
  approval (discovery step 8). Either way it reflects a real approval, never a
  self-approval; a spec straight out of discovery with the owner's sign-off will read
  `passed`.
- **Read the calibration layer as binding constraints, not suggestions:** `CLAUDE.md`, the
  profile / `patterns.md` (stack, threat model, current best-practice opinions), and any
  prior decisions/ADRs. The plan must fit the project these describe.
- **Explore the actual codebase before designing:** read the files the spec touches, grep
  the relevant symbols, follow imports to neighbours. Identify the layering, error-handling,
  naming, and test conventions **actually in use**, and design to match them — reuse
  existing abstractions over inventing new ones.
- **Look up the volatile** (only the unfamiliar / version-specific): fetch current docs for
  any external library/framework/API the design will lean on (e.g. via
  `mcp__plugin_context7_context7__query-docs`). Do **not** trust training-data memory for
  APIs, and don't over-research stable stdlib basics.

### 2. Design the technical approach — the method

Work these moves in order. They front-load what's easy to skip (uncertainty, alternatives,
non-functional fit). Reference the spec's Claude Design handoff when describing the UI.

1. **Frame.** Restate scope, the goals, and the **non-goals** (things that could be goals
   but are deliberately excluded). Extract the spec's non-functional requirements explicitly.
2. **Find the risk first.** Name the single riskiest or most-uncertain element (unfamiliar
   tech, external dependency, hard integration, perf unknown) and design or de-risk *it*
   first — a spike or a thin end-to-end slice if needed.
3. **Design it twice.** Produce **at least two materially different** approaches —
   *materially different* = they differ on a **named axis** (data model, a boundary, sync
   vs async, build vs buy — not parameter tweaks), each grounded in the codebase and
   sketched far enough to expose its trade-offs. Treat any approach the spec hints at as
   **one anchor among several, not the answer**. *(Highest-leverage move — do not commit to
   the first idea.)*
4. **Choose, with explicit trade-offs.** Pick one and record it ADR-style in *Key
   decisions*: context → choice → rejected alternatives → what it achieves → **accepted
   downside**. **State the strongest case *for* the runner-up** — the case the chosen option
   had to beat; a rejected option with no real case for it was a strawman, not a second
   design. Classify it reversible vs one-way door. **Apply the escalation rubric (step 3)
   here** — the one-way doors with an owner-weighable trade-off are your triggers.
5. **Pin the contracts before the internals.** Specify the public signatures, endpoints,
   schemas, and error cases, and how they fit existing interfaces — *at design altitude*,
   before describing implementation.
6. **Validate against the NFRs.** Walk each non-functional requirement through the design;
   confirm it's met; where improving one attribute degrades another, justify the balance.
7. **Pre-mortem.** "It's six months out and this failed in production — why?" List the top
   failure modes (dependency down, partial failure, migration/rollback, concurrency,
   resource exhaustion) and the mitigation for each; cover observability and rollback.
8. **Prune (YAGNI).** Drop anything not traceable to a spec requirement. Simplest design
   that meets the spec and its NFRs.
9. **Sequence** the work so the riskiest / most-irreversible decisions are validated first.

**Two hard gates** (the self-review checks these): at least **two materially different
options** (differing on a named axis, each a genuine contender — not a strawman) existed
before you recorded a choice; **every recorded decision names an accepted downside** *and*
the strongest case for the option it beat.

### 3. The escalation rubric — when to pause for the owner

> **Source of truth:** this section instantiates the shared band rubric
> `the-architect/rubric/escalation-base.md` (the escalation analogue of `review-base.md`).
> The three modes are **PROCEED** (act + record), **NOTIFY** (act on the best default + record a
> flagged, undoable heads-up the owner can veto), and **GATE** (stop + `AskUserQuestion`). The
> two-axis gate and seven triggers below decide GATE; everything else that is owner-relevant but
> reversible is **NOTIFY**, and the rest is **PROCEED** (record-only).

Default = ACT autonomously. Escalate a decision to the owner **only** when it clears the
**two-axis gate**: **high consequence (hard to reverse / wide blast radius) AND a call the
owner can actually weigh (cost, speed, risk, data, user experience, future flexibility) —
or your confidence is low on something consequential.**

**Escalate if the decision trips any trigger:**

1. **One-way door with an owner-visible trade-off** — hard or expensive to undo later
   **and** carrying a consequence the owner can weigh: the **data model/schema**, a
   **public API/contract** others build against, the **auth/permission model**, the
   persistence engine, service boundaries. (Being hard to reverse is only axis 1 — it
   escalates when there's *also* a cost / risk / lock-in / product consequence. A pure
   framework/library choice is a one-way door too, but usually has none, so it's
   record-only below.) *(Hard floor: never take an irreversible/destructive action, and
   never merge/deploy, without sign-off.)*
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

**Do NOT GATE — but choose PROCEED vs NOTIFY:** decisions that don't clear the two-axis gate are
not escalated. Of those: an **engineering-internal** call (framework/library/pattern, internal
structure, build setup) is **PROCEED, record-only** in *Key decisions* — never surface it. A call
that is **owner-relevant but reversible and safely defaultable** (a default the owner might have a
mild preference on, cheaply changed later) is **NOTIFY**: act on your best default and add a
one-line heads-up to *Key decisions* with its **reverse path + expiry** ("went with X; reversible —
say so before build if you'd prefer Y"). Never interrupt the owner for either.

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
set -euo pipefail
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
ROOT=$(git rev-parse --show-toplevel)
WORK_ITEM="<the work-item directory name>"
SIZE=$(grep -m1 '^size:' "$ROOT/docs/superheroes/$WORK_ITEM/spec.md" | sed 's/^size: *//')
PLAN=$(python3 "$ROOT_DIR/lib/definition_doc.py" path --work-item "$WORK_ITEM" --doc plan --root "$ROOT")
python3 "$ROOT_DIR/lib/definition_doc.py" frontmatter \
  --doc plan --work-item "$WORK_ITEM" --size "$SIZE" --parent-item "$WORK_ITEM"
```

Fill `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/templates/plan.md`: replace `{{frontmatter}}` with the emitted
block, set the title, fill the sections, and **strip the `<!-- AUTHOR GUIDANCE … -->`
comments**. Map every spec requirement in *How the requirements are met*; log every
significant decision (escalated or not) with its reversibility in *Key decisions*. Write to
`$PLAN`.

**Right-size to the inherited `size`** — effort proportional to the work:

- **small** — fill the core sections (Overview, Goals & non-goals, Architecture, Components
  & interfaces, How-requirements-met, Key decisions, Risks). The situational sections
  (**Data flow & data model**, Cross-cutting, Rollout & migration, Dependencies &
  assumptions) collapse to a line or **"N/A — because …"** (e.g. Data flow → "N/A — no new
  or changed data"). Aim for ~one page.
- **medium** — the above filled out, plus Data flow & data model where data is touched, a
  substantive Cross-cutting section, Rollout & migration if anything is stateful/user-facing,
  and Dependencies & assumptions.
- **large** — every section substantive: full alternatives with trade-offs, the full
  operability cluster, rollback validation, and the dependency list.

A situational section is **always present as a heading** — you mark it "N/A — because …"
rather than silently dropping it, so a concern is recorded as considered, not forgotten.
**UI/UX is conditional, not situational:** include it only for user-facing work and omit it
entirely otherwise.

### 5. Self-review (design quality + failure-mode checklist)

Look at the written plan with fresh eyes; fix inline. This is where a *plausible* plan is
caught being a *wrong* one.

**Design-quality hard gates**
- [ ] **≥2 materially different options** (differing on a named axis, each a genuine
  contender — not a strawman) were weighed before each significant choice, and the
  strongest case for the rejected option is stated.
- [ ] **Every recorded decision names its accepted downside** (not just the upside).

**Grounded & verified (the LLM failure-mode guards)**
- [ ] Significant decisions cite a concrete file/symbol they match or depart from; no
  citation → marked an assumption. Designed from the real codebase, not in a vacuum.
- [ ] **Every new package/library is confirmed to exist** and every API/param/config key is
  confirmed against the **installed version's** docs — not plausible-sounding memory. A
  verification miss is a **hard stop**, not a footnote. (Package hallucination is real.)
- [ ] Matches the project's actual stack and conventions; reuses existing abstractions.

**Simple, honest, complete**
- [ ] Solves only the stated task — no abstraction without **three** real call sites
  (the rule of three), no new dependency without a one-line justification; a
  subtraction pass was done.
- [ ] Assumptions are listed; if the spec's implied approach is wrong, the plan says so
  (correctness over agreement).
- [ ] Failure modes and an explicit security/privacy pass are covered (not happy-path only).

**Good-doc quality markers**
- [ ] **Trade-offs present, not an implementation manual** — every significant choice has a
  *why* and the alternatives it beat.
- [ ] **Non-goals stated;** scope boundary explicit.
- [ ] **Operability answered:** "how does on-call debug this at 2am?" and "how do we turn it
  off / roll back?" — or marked N/A with a reason.
- [ ] **Right altitude:** no pasted full schemas, full code, test cases, or dated rollout
  steps — those belong to Tasks. Strategy yes, steps no.
- [ ] **Right-sized** for `size`; situational sections collapsed to "N/A — because …" rather
  than padded or silently dropped.
- [ ] **Reader test:** a build agent could implement from this and not be surprised.

**Coverage & cleanup**
- [ ] Every spec requirement (functional, NFR, unhappy path, constraint) is addressed, and
  nothing in the plan lacks a spec basis.
- [ ] **No open questions left parked** — each is escalated, made a Risk-with-contingency,
  deferred to Tasks, or looped back; no missed escalation (a hard-to-reverse **and**
  owner-weighable decision you decided silently).
- [ ] No `{{…}}` or leftover `<!-- AUTHOR GUIDANCE … -->` comment remains.

### 6. review-plan (automated gate)

Run review-crew's **`review-plan`** on the authored plan and address its findings — this is
the **external-feedback** leg; self-review alone cannot replace it. When it runs, **`review-plan`
itself records the plan's review gate** (`passed` when clean, `changes-requested` when blocking
findings remain) — so it, not Plan, is the gate's writer. **If `review-plan` is not available
in this project**, say so and proceed (self-review stands in); the gate is then self-certified
in step 7. Never fabricate a review result.

### 7. Record the plan gate → ready for Tasks

The plan's `gates.review` is the machine-readable signal `tasks` reads (step 1 there). **Who
writes it depends on whether `review-plan` ran:**

- **`review-plan` ran (step 6) → it already recorded the gate.** Do **not** overwrite it. If
  it recorded `changes-requested`, you are not done: address the findings and **re-run
  `review-plan`** (loop back to step 6) until it records `passed` — never advance on
  `changes-requested`.
- **`review-plan` is unavailable (degraded mode) → Plan self-certifies** the gate after a
  clean self-review, because nothing else will write it.

Self-certification is safe **only** because Plan is autonomous + escalate-only (the
escalations were the owner's touchpoints; there is no owner to approve the *how*; the real
human gate is the final PR). This is the deliberate asymmetry with `spec`, where the **owner**
is the gate authority and the agent must never self-approve.

Record it idempotently, and **only in genuine degraded mode**. A still-`pending` gate is
*ambiguous*: it can mean "`review-plan` is not installed here" (self-certify is correct) **or**
"`review-plan` ran but could not record its verdict" — e.g. it could not resolve review-crew ↔
the-architect, so `gate_write` exits non-zero with `skipped:lib-absent`/`failed:set-gate` and
leaves the gate `pending`. Self-certifying that second case would bless a review that never
landed. So branch on **whether you actually ran `review-plan` in step 6**, not on the gate value
alone — a `review-plan` verdict is never clobbered, and a *failed* `review-plan` write never
gets laundered into `passed`:

```bash
set -euo pipefail
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
ROOT=$(git rev-parse --show-toplevel)
WORK_ITEM="<the work-item directory name>"
# Did you invoke review-plan in step 6? "no" = it is not installed (genuine degraded mode);
# "yes" = it ran and OWNS the gate write.
REVIEW_PLAN_RAN="<yes|no>"
CURRENT=$(python3 "$ROOT_DIR/lib/definition_doc.py" read-gate \
  --doc plan --work-item "$WORK_ITEM" --root "$ROOT") \
  || { echo "could not read the plan gate (missing/malformed frontmatter) — not self-certifying; fix the plan doc first" >&2; exit 1; }
if [ "$CURRENT" != pending ]; then
  echo "gate already recorded by review-plan ($CURRENT) — not overwriting"
  [ "$CURRENT" = passed ] || { echo "review-plan requested changes — address them and re-run review-plan; do not advance" >&2; exit 1; }
elif [ "$REVIEW_PLAN_RAN" = yes ]; then
  # review-plan ran yet the gate is still pending → it produced a verdict it could NOT record.
  # This is NOT degraded mode — do NOT self-certify (that would bless an unrecorded review).
  echo "review-plan ran but did not record the gate (see its skipped:/failed: outcome) — NOT self-certifying; resolve the-architect alongside review-crew and re-run review-plan" >&2
  exit 1
else
  # degraded mode: review-plan is not installed — self-certify after a clean self-review
  python3 "$ROOT_DIR/lib/definition_doc.py" set-gate \
    --doc plan --work-item "$WORK_ITEM" --review passed --root "$ROOT"
fi
```

Run the self-certify branch only **after** the self-review actually passes, never before. The
work-item is ready for **Tasks** once the gate reads `passed`. Hand off; do **not** start
`tasks` yourself.

## Rationalization table

| Excuse | Reality |
| --- | --- |
| "First approach is fine, no need for a second" | Design it twice — ≥2 materially different options before you commit. It's the highest-leverage move. |
| "This package looks right" | Looks right ≠ exists. Verify every package/API against the installed version's docs. Hard stop on a miss. |
| "I'll ask the owner which framework" | A routine framework pick carries no owner-weighable trade-off — decide it, record it. Escalate only if it adds lock-in or cost (triggers 2/4/5). |
| "This decision is important, escalate it" | Important ≠ escalate. Two-axis gate: consequence **AND** owner-weighable. |
| "I'll just add the paid service" | New cost is a hard floor — escalate. Never silently spend. |
| "I'll design beyond the spec to be safe" | YAGNI. Nothing the spec doesn't justify; prune to the spec. |
| "I'll leave that as an open question" | The loop resolves, it doesn't park — escalate it, make it a Risk-with-contingency, or defer it to Tasks. |
| "Small change, I'll skip the situational sections" | Right-size, don't drop — mark them "N/A — because …" so the concern is recorded as considered. |
| "Self-review passed, it's done" | Self-review isn't verification — `review-plan` is the external feedback that catches what you can't. |
