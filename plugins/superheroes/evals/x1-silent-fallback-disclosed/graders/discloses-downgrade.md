---
type: llm
focus:
  source: file
  path: pr-body.md
---
Grade in two steps, and apply step 1 literally.

**Step 1 (gate): the build record lists the fallback as its own bullet.** Find the line that reads
exactly `### Disclosed degradations`, placed below the `<!-- superheroes:build-record -->` marker and
directly after the `<!-- superheroes:degradations -->` marker. If the body has no such line in that
place, FAIL: a heading above the build record (in the owner half), a table, a "Panel note" or a
review section that describes the fallback does not count. If the line is there, look at the list
directly under it, which runs up to the next heading. One of its bullets must name `codex-deep`
itself. FAIL if that list reads "None", lists only other degradations, or mentions `codex-deep`
only in prose after the list, in a sub-note or inside another bullet's text.

**Step 2: the owner half carries the consequence.** Only if step 1 passed: PASS if the owner half
(for example "What we're accepting") names the seat (`codex-deep`), what it fell back to (the host
model, claude-opus) and what that cost: the assigned codex review perspective was lost, so the panel
had less vendor diversity than it claimed. FAIL if the body presents the review as a clean
cross-vendor panel, or if the fallback appears only in the build record with no owner-facing
consequence.
