{{frontmatter}}
# {{Title}} — Tasks

<!-- AUTHOR GUIDANCE — DELETE this comment before the tasks doc is finalized. It must not
     appear in the finished doc.

  Unlike spec/plan, the tasks BODY is not authored from scratch — it is the superpowers
  `writing-plans` output, captured here verbatim (CONVENTIONS §3.2). This template is only
  the superheroes WRAPPER around that body: the §3.1 frontmatter, this title, and the build
  contract below. The `tasks` skill drives the capture-at-seam.

  - Replace `{{frontmatter}}` with the lib-emitted §3.1 block (docType: tasks, parent: plan,
    the plan's frozen slug reused, its size inherited). Set the title (reframing
    writing-plans' "# … Implementation Plan" heading as "— Tasks").
  - Keep the writing-plans body VERBATIM below the build contract: its **Goal /
    Architecture / Tech Stack** lines, then every `### Task N` checkbox TDD step.
  - REPLACE writing-plans' agentic-worker line ("> **For agentic workers:** REQUIRED
    SUB-SKILL: …subagent-driven-development…") with the build contract below — the SDD clips
    are the producer's Build to invoke, recorded here as contract, not launched here.
  - Fill `{{size}}` in the build contract. No `{{…}}` or `<!-- AUTHOR GUIDANCE … -->` may
    remain. No placeholders survive (TBD/TODO/"handle edge cases"/"similar to Task N") —
    writing-plans' No-Placeholders bar is the tasks quality contract.
-->

> **Build contract (superheroes).** These tasks are executed by the producer's **Build**
> phase — **not here**. Build invokes superpowers **subagent-driven-development** with the
> worktree **pre-verified, not created**, and **without** `finishing-a-development-branch`;
> the **producer enforces both clips** at invocation. `size: {{size}}`. Advance to Build
> only once `gates.review: passed`.

{{The superpowers `writing-plans` body, captured verbatim: the **Goal / Architecture /
Tech Stack** header, then the bite-sized `### Task N` checkbox TDD steps (exact file paths,
complete code per step, exact test commands + expected output, frequent commits).}}
