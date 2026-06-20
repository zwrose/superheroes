---
name: tasks
description: Use after a `plan` is approved, to turn it into the bite-sized, test-first executable `tasks` for a work-item — the checkbox TDD steps the build follows. It WRAPS superpowers `writing-plans` and owns the superheroes definition-doc around it; route plan-decomposition here in a superheroes project (not `writing-plans` standalone). Runs LARGELY AUTONOMOUSLY and produces the `tasks` definition-doc, then runs review-tasks. Not for requirements (that is `discovery`) or technical approach (that is `plan`); it does NOT execute the steps (that is Build).
---

This skill speaks in host-neutral actions. Resolve them to your runtime's tools by reading the host tool map at `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/hosts/<your-host>-tools.md` (the leading variable is this plugin's root directory) — `claude-tools.md` on Claude Code, `codex-tools.md` on Codex.

# Tasks

Turn the approved **`plan`** into the **`tasks`** definition-doc: the bite-sized,
test-first, executable steps the build follows. This is the last of the loop's front half
(Discovery → Plan → **Tasks** → Build → Verify → Ship).

**Tasks wraps superpowers `writing-plans`.** That skill is the engine that decomposes a
plan into checkbox TDD tasks; this skill owns the superheroes **definition-doc** around it
— the §3.1 frontmatter, the build contract, the review gate — and the **capture-at-seam**
so the output lands as `docs/superheroes/<work-item>/tasks.md`, not an orphan
`docs/superpowers/plans/` file. *Own the interface, delegate the labor.*

**Tasks runs autonomously**, like Plan. Discovery is owner-co-authored (the *what*); Plan
and Tasks are the autonomous *how*. There is **no owner-approval gate** — the escalations
happened in Plan, and the PR is the final human gate later. Tasks does **not** execute the
steps: execution is the **producer's Build** phase, governed by the build contract. Tasks
stops at a reviewed, gated tasks doc that is ready for Build.

Any judgment call during decomposition follows the shared rubric
`the-architect/rubric/escalation-base.md` (modes PROCEED/NOTIFY/GATE) — like Plan, Tasks runs
autonomously and escalates only a genuine GATE; tasks decisions are almost always PROCEED.

**The loop resolves; it does not park.** A finished tasks doc carries **no placeholders** —
no "TBD", no "add error handling", no "similar to Task N". Every step is concrete and
executable, or it isn't done. A gap in the plan surfaces as a loop-back to `plan`, never as
a vague task.

<HARD-GATE>
**Precondition: the plan is approved.** Tasks builds on an approved `plan`; never decompose
an unapproved or absent one. **Verify it programmatically** (step 1), don't just assert it:
`gates.review: passed` on the plan is the machine-readable signal (set by `review-plan`, or
by the plan self-certifying its autonomous review when review-plan is absent); a `pending`
or `changes-requested` plan is **not** approved — stop.

**And do NOT execute the tasks** — no code, no worktree, no `subagent-driven-development`,
no `finishing-a-development-branch`. That is the producer's **Build**. Tasks produces the
doc and hands off.
</HARD-GATE>

## Checklist

Create a TodoWrite item for each step:

1. **Load the approved plan + verify its gate + ground**
2. **Generate the bite-sized tasks** via superpowers `writing-plans` (the engine)
3. **Capture-at-seam → author the `tasks` definition-doc** (frontmatter + build contract + body)
4. **Self-review**
5. **review-tasks** (automated gate; graceful degradation)
6. **Record the tasks gate → ready for Build**

## The steps

### 1. Load the approved plan + verify its gate + ground

- **Read the plan** at `docs/superheroes/<work-item>/plan.md` (the **work-item slug is the
  directory name**): approach, architecture, components & interfaces, data flow, key
  decisions, risks. **Read the spec too** (the plan's parent,
  `docs/superheroes/<work-item>/spec.md`) — the functional requirements, significant unhappy
  paths, NFRs, and definition of done are what the tasks must ultimately satisfy.
- **Verify the plan is approved — programmatically, not by eye** (the HARD GATE above). Read
  `gates.review` on the **plan** doc and stop unless it is `passed`:

  ```bash
  set -euo pipefail
  ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
  ROOT=$(git rev-parse --show-toplevel) || { echo "not in a git repo" >&2; exit 1; }
  WORK_ITEM="<the work-item directory name>"
  REVIEW=$(python3 "$ROOT_DIR/lib/definition_doc.py" read-gate \
    --doc plan --work-item "$WORK_ITEM" --root "$ROOT") \
    || { echo "no readable plan for $WORK_ITEM — run plan first" >&2; exit 1; }
  [ "$REVIEW" = passed ] || { echo "plan not approved (gates.review=$REVIEW) — stop; it needs review-plan, or the plan's own self-certification, first" >&2; exit 1; }
  ```

  `gates.review: passed` on the plan is written by review-crew's `review-plan` when it runs,
  and — when review-plan isn't wired yet — by the plan **self-certifying** its autonomous
  review (plan skill, final step). Plan is autonomous-by-design, so its gate is a
  self-certification, not an owner approval; either way `passed` means the plan's review
  completed. Tasks builds only on an approved plan.
- **Ground for an accurate decomposition.** `writing-plans` writes exact file paths and
  real code, so the inputs must be real: **`CLAUDE.md` must be in your context (read it
  now if it isn't)** — then read the rest of the calibration layer, and explore the
  actual files the plan touches (grep the symbols, follow imports, note the test
  conventions) so the tasks reference real paths and match existing patterns.

### 2. Generate the bite-sized tasks via superpowers `writing-plans`

Invoke the superpowers **`writing-plans`** skill — it is the engine that turns the plan into
bite-sized, test-first checkbox tasks. **Drive it as a wrapped sub-skill**, with three
overrides so its output becomes a superheroes definition-doc rather than a standalone
superpowers plan:

- **Input = the approved `plan`** (and the spec it satisfies). The plan is the source of
  truth: `writing-plans` decomposes its approach into steps — it does **not** re-decide the
  architecture. If decomposition exposes a real gap or contradiction in the plan, **loop
  back to `plan`**; don't paper over it with a vague task.
- **Save location = our tasks path.** `writing-plans` defaults to
  `docs/superpowers/plans/…`; override it to write at
  `docs/superheroes/<work-item>/tasks.md` (it explicitly allows a location override). This
  is the **capture-at-seam** — no orphan `superpowers/plans` file. Step 3 then reframes the
  file in place.
- **Do NOT perform its Execution Handoff.** `writing-plans` ends by offering to execute
  (subagent-driven-development / executing-plans). **Suppress that.** In superheroes,
  execution is the **producer's Build** phase, governed by the build contract — not
  something Tasks launches. When `writing-plans` reaches that handoff, return here instead.

Honor `writing-plans`' quality bar — it **is** the tasks-doc quality contract: bite-sized
one-action steps; exact file paths; complete code in every code step; exact test commands
with expected output; frequent commits; **no placeholders** (no "TBD", "add validation",
"handle edge cases", "similar to Task N"); the type-consistency self-check across tasks.

### 3. Capture-at-seam → author the `tasks` definition-doc

The tasks doc **reuses the plan's frozen work-item slug** (never mint a new one) and
inherits its `size`. Emit the §3.1 frontmatter via the lib (`docType: tasks`, parent = the
plan) and wrap the captured body:

```bash
set -euo pipefail
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
ROOT=$(git rev-parse --show-toplevel)
WORK_ITEM="<the work-item directory name>"
SIZE=$(grep -m1 '^size:' "$ROOT/docs/superheroes/$WORK_ITEM/plan.md" | sed 's/^size: *//')
TASKS=$(python3 "$ROOT_DIR/lib/definition_doc.py" path --work-item "$WORK_ITEM" --doc tasks --root "$ROOT")
python3 "$ROOT_DIR/lib/definition_doc.py" frontmatter \
  --doc tasks --work-item "$WORK_ITEM" --size "$SIZE" --parent-item "$WORK_ITEM"
```

Assemble `$TASKS` from `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/templates/tasks.md`:

- Replace `{{frontmatter}}` with the emitted block; set the `# {{Title}} — Tasks` title
  (this **reframes** `writing-plans`' `# … Implementation Plan` heading).
- **Keep the `writing-plans` body verbatim** below the build contract: its **Goal /
  Architecture / Tech Stack** lines, then every `### Task N` checkbox step. CONVENTIONS §3.2
  pins the tasks body as the `writing-plans` body verbatim — don't paraphrase the tasks.
- **Replace** `writing-plans`' agentic-worker line (`> **For agentic workers:** REQUIRED
  SUB-SKILL: …subagent-driven-development…`) **with the build contract** from the template.
  The SDD clips (worktree **pre-verified, not created**; **no** `finishing-a-development-branch`)
  are the **producer's Build** to invoke — recorded here as contract, not launched here.
- Fill the build-contract `{{size}}`; **strip every `<!-- AUTHOR GUIDANCE … -->` comment**.

The result is a single `docs/superheroes/<work-item>/tasks.md`: frontmatter + title + build
contract + the verbatim `writing-plans` body. If `writing-plans` left a file anywhere else,
delete it — there is one tasks doc, in the work-item directory.

### 4. Self-review

Look at the written tasks doc with fresh eyes; fix inline (no re-review loop):

- **Placeholders & guidance:** any `{{…}}`, "TBD", "TODO", "add error handling", "similar to
  Task N", or leftover `<!-- AUTHOR GUIDANCE … -->`? Remove it — `writing-plans`'
  No-Placeholders bar is non-negotiable; every code step shows the actual code.
- **Type consistency:** do types, signatures, and names used in later tasks match what
  earlier tasks defined? (`clearLayers()` in Task 3 vs `clearFullLayers()` in Task 7 is a
  bug.)
- **Coverage:** every plan component/interface and every spec requirement (functional, NFR,
  unhappy path) maps to at least one task; nothing in the tasks lacks a plan/spec basis. A
  spec requirement with no task → add the task (or loop back to `plan` if the plan never
  covered it).
- **Frontmatter & seam:** `docType: tasks`, `parent` is the **plan**, the slug is **reused**
  (not re-minted), `size` is **inherited** from the plan; the title is reframed; the
  agentic-worker line is replaced by the build contract; there is **no orphan** file under
  `docs/superpowers/plans/`.
- **Altitude:** these are executable steps (exact paths, commands, code) — not plan-level
  strategy restated. Strategy stayed in the plan.

### 5. review-tasks (automated gate)

Run review-crew's **`review-tasks`** on the authored tasks doc and address its findings —
this is the **external-feedback** leg; self-review alone cannot replace it. When it runs,
**`review-tasks` itself records the tasks review gate** (`passed` when clean,
`changes-requested` when blocking findings remain) — so it, not Tasks, is the gate's writer.
**If `review-tasks` is not available in this project**, say so and proceed (self-review
stands in); the gate is then self-certified in step 6. Never fabricate a review result.

### 6. Record the tasks gate → ready for Build

Tasks is autonomous — like Plan, there is **no owner-approval gate**. The tasks
`gates.review` is the signal the producer's **Build** reads. **Who writes it depends on
whether `review-tasks` ran:**

- **`review-tasks` ran (step 5) → it already recorded the gate.** Do **not** overwrite it.
  If it recorded `changes-requested`, you are not done: address the findings and **re-run
  `review-tasks`** until it records `passed` — never advance on `changes-requested`.
- **`review-tasks` is unavailable (degraded mode) → Tasks self-certifies.** **Certify only a
  complete doc:** first confirm the step-4 self-review actually passed — the capture-at-seam
  is fully applied (heading reframed, the agentic-worker line replaced by the build contract,
  no orphan `docs/superpowers/plans/` file, no leftover `{{…}}` or placeholder) — **before**
  recording the gate. `set-gate` writes `passed` from the **frontmatter alone** and cannot
  see a half-applied body, so certifying before the self-review passes would silently bless a
  broken doc.

Self-certification is safe **only** because Tasks is autonomous (no owner approves the *how*;
the real human gate is the final PR) — the deliberate asymmetry with `spec`. Record it
idempotently, and **only in genuine degraded mode**. A still-`pending` gate is *ambiguous*: it
can mean "`review-tasks` is not installed here" (self-certify is correct) **or** "`review-tasks`
ran but could not record its verdict" — e.g. it could not resolve review-crew ↔ the-architect, so
`gate_write` exits non-zero with `skipped:lib-absent`/`failed:set-gate` and leaves the gate
`pending`. Self-certifying that second case would bless a review that never landed. So branch on
**whether you actually ran `review-tasks` in step 5**, not on the gate value alone — a
`review-tasks` verdict is never clobbered, and a *failed* `review-tasks` write never gets
laundered into `passed`:

```bash
set -euo pipefail
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
ROOT=$(git rev-parse --show-toplevel)
WORK_ITEM="<the work-item directory name>"
# Did you invoke review-tasks in step 5? "no" = it is not installed (genuine degraded mode);
# "yes" = it ran and OWNS the gate write.
REVIEW_TASKS_RAN="<yes|no>"
CURRENT=$(python3 "$ROOT_DIR/lib/definition_doc.py" read-gate \
  --doc tasks --work-item "$WORK_ITEM" --root "$ROOT") \
  || { echo "could not read the tasks gate (missing/malformed frontmatter) — not self-certifying; fix the tasks doc first" >&2; exit 1; }
if [ "$CURRENT" != pending ]; then
  echo "gate already recorded by review-tasks ($CURRENT) — not overwriting"
  [ "$CURRENT" = passed ] || { echo "review-tasks requested changes — address them and re-run review-tasks; do not advance" >&2; exit 1; }
elif [ "$REVIEW_TASKS_RAN" = yes ]; then
  # review-tasks ran yet the gate is still pending → it produced a verdict it could NOT record.
  # This is NOT degraded mode — do NOT self-certify (that would bless an unrecorded review).
  echo "review-tasks ran but did not record the gate (see its skipped:/failed: outcome) — NOT self-certifying; resolve the-architect alongside review-crew and re-run review-tasks" >&2
  exit 1
else
  # degraded mode: review-tasks is not installed — self-certify after a clean self-review
  python3 "$ROOT_DIR/lib/definition_doc.py" set-gate \
    --doc tasks --work-item "$WORK_ITEM" --review passed --root "$ROOT"
fi
```

This writes `gates.review: passed` (and derives `status: approved`) — the machine-readable
signal the producer's Build checks. When review-crew's `review-tasks` is wired, **it** owns
this write; in its absence Tasks records it after a clean self-review, exactly as Plan does
for its own gate.

The work-item is now ready for the **Build** phase. Do **not** start the build or
`subagent-driven-development` yourself — hand off; the producer/owner drives the transition.

## Rationalization table

| Excuse | Reality |
| --- | --- |
| "I'll just use `writing-plans` directly" | In a superheroes project the Tasks phase wraps it — route through `tasks` so the body is captured into the definition-doc and the producer owns execution. |
| "Let me start executing the tasks" | Execution is the producer's **Build** (subagent-driven-development, worktree, finishing-a-branch). Tasks stops at a reviewed, gated doc. |
| "`writing-plans` saved to `docs/superpowers/plans/`" | Override its location to our tasks path (capture-at-seam); leave no orphan file. |
| "I'll re-decide the approach while decomposing" | The plan is the source of truth — Tasks decomposes it, it doesn't re-design. A real plan gap loops back to `plan`. |
| "I'll leave a TBD in this task" | No placeholders — `writing-plans`' hard bar. Every step is concrete and executable, or it's not done. |
| "Plan looks approved to me" | Verify `gates.review: passed` programmatically; a `pending`/`changes-requested` plan is not approved. |
| "Self-review passed, it's done" | `review-tasks` is the external feedback self-review can't replace. |
