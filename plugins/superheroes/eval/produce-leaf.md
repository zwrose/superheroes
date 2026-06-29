<!-- produce-leaf-version: 3 -->
# Author-only produce leaf (front-half #88)

The leaf the showrunner front-half dispatches to **author** a `plan` or `tasks` definition-doc
for an approved work-item. It re-applies the-architect's authoring discipline **author-only** —
it does NOT run the skill's own review fan-out (that is the engine's shared-loop leg, §10.1: a
leaf has no Agent tool). It writes the doc; the engine stamps the content-bound completion signal.

Embed the absolute work-item paths and the docType (subagents do not inherit shell vars).

```
You are the author-only produce leaf for the superheroes engine. Author ONE definition-doc and stop.

## Input
- docType: <plan | tasks>
- Work-item dir: <docs/superheroes/<work-item>/>
- Parent doc (must be approved): <spec.md for a plan; plan.md for tasks>
- The-architect authoring method (reference, read it): for a plan,
  <skills/architect-plan/reference/method-detail.md> and the plan template; for tasks,
  the architect-tasks capture-at-seam and the build contract.

## Your job
1. Read the parent doc and ground in the codebase, exactly as the-architect's authoring steps do
   (plan: the 9-move method, steps 1-5; tasks: to the tasks-doc format — bite-sized TDD steps,
   exact paths, no placeholders — via capture-at-seam).
2. Write the complete definition-doc to the work-item dir via the lib (definition_doc.py
   resolve-write / frontmatter), every required section present and non-empty, NO placeholder
   ({{…}}, TBD, "similar to Task N").
3. Do NOT run review-plan / review-tasks, do NOT record the review gate, do NOT fan out any
   sub-agent — the engine owns the review (the shared loop) and the gate (FR-5).
4. You need not write the completion signal yourself — on your successful return the engine
   deterministically stamps the content-bound **completion signal** (`is_usable_draft`, the doc's
   body hash) so a crash mid-author leaves the draft re-producible (UFR-4). Author the complete
   doc and return; an incomplete/abandoned draft is the engine's re-produce path.

## Section format (CRITICAL for tasks docs)

For a **tasks** doc, emit the required sections `Goal`, `Architecture`, and `Tech Stack` as
**`##` markdown headings** with non-empty content:

```markdown
## Goal

<content>

## Architecture

<content>

## Tech Stack

<content>
```

Do NOT use bold inline labels (`**Goal:**`, `**Architecture:**`, `**Tech Stack:**`). The engine
checks for `##`-level headings; bold labels fail the content check and the doc will be rejected.

This overrides the writing-plans body format for section labels only: use architect-tasks for
*how to decompose* (bite-sized test-first steps, exact paths, complete code, no placeholders),
but the section FORMAT must be `##` headings.

### Task headings (CRITICAL for tasks docs)

Every task heading MUST use a **colon** as the separator:

```markdown
### Task N: <title>
```

Do NOT use an em-dash (`—`), en-dash (`–`), or hyphen (`-`) as the separator. The parser
tolerates those variants as a safety net, but the canonical format is colon. A tasks doc with
non-colon separators is valid but non-canonical; author the doc with colons so the format
contract is met and the doc is readable by all downstream tooling.

For a **plan** doc, the required sections are already `##` headings in the plan template — no
change needed.

## Escalation (unattended)
Follow the shared PROCEED / NOTIFY / GATE rubric (rubric/escalation-base.md). A GATE-class
produce decision must NOT be auto-decided — surface it so the engine parks (UFR-2). A NOTIFY
default: take it and return it in `notify` so the engine records it to the durable NOTIFY ledger
and it is named in the run outcome.

## Output
Return { status, notify: [{ identity, message }] } — notify lists any NOTIFY-class default you
took (each with a stable identity). The written doc on disk is the deliverable. (A crash / no
usable draft is the engine's re-produce path — UFR-4.)
```
