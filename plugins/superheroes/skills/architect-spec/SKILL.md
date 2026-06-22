---
name: writing-specs
description: Use to author the on-disk `spec` definition-doc once an owner has APPROVED a set of requirements — normally invoked by the `discovery` skill, not directly by an owner idea. Mints the work-item slug, fills the spec body template, writes `docs/superheroes/<work-item>/spec.md`, and runs a self-review. Does NOT elicit requirements (that is `discovery`) or design the technical approach (that is `plan`).
---

This skill speaks in host-neutral actions. Resolve them to your runtime's tools by reading the host tool map at `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/hosts/<your-host>-tools.md` (the leading variable is this plugin's root directory) — `claude-tools.md` on Claude Code, `codex-tools.md` on Codex.

# writing-specs

Turn an **owner-approved** set of requirements into the on-disk `spec`
definition-doc. This is the spec's analogue of superpowers `writing-plans`: the
dialogue happens in `discovery`; this skill owns the **artifact**. The frontmatter
linkage is machine-read, so it is emitted by the lib — never hand-written.

**Precondition:** the owner has approved the requirements (Discovery's HARD GATE).
If they have not, stop and return to `discovery` — do not author a spec from
un-approved requirements.

## Inputs (from `discovery`)

The approved: **title**, **purpose**, **who it's for**, **functional requirements**
(EARS sentences, each with ≥1 acceptance criterion), **significant unhappy-path
behaviors** (If/Then EARS, from the coverage checklist), **non-functional
requirements** (outcomes + fit-criteria), **UI/UX outcome** (the Claude Design
handoff, if user-facing), **definition of done / success**, **assumptions &
dependencies**, **constraints**, **out-of-scope**, and **`size`**.

## Flow

1. **Mint the work-item** (once; it is then frozen — CONVENTIONS §6.1):

   ```bash
   ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
   WORK_ITEM=$(python3 "$ROOT_DIR/lib/definition_doc.py" mint --title "<title>")
   ```

   Reuse an existing slug if this spec already exists (a revision); never re-mint
   for the same work-item.

2. **Resolve the path at the repo root** (Phase 1 is in-repo). Pin `--root` to the
   repo top level so the spec can't land in a subdirectory regardless of the current
   working directory:

   ```bash
   ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
   ROOT=$(git rev-parse --show-toplevel)
   SPEC=$(python3 "$ROOT_DIR/lib/definition_doc.py" resolve-write \
     --work-item "$WORK_ITEM" --doc spec --root "$ROOT") \
     || { echo "the-architect: cannot place the spec safely (see message above) — not writing." >&2; exit 1; }
   ```

3. **Emit the §3.1 frontmatter** with the lib (a fresh spec is `status: draft`,
   `gates.review: pending`, null parent):

   ```bash
   ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
   python3 "$ROOT_DIR/lib/definition_doc.py" frontmatter \
     --doc spec --work-item "$WORK_ITEM" --size "<size>"
   ```

   Do not hand-write the frontmatter — the lib owns its shape and the
   parent-linkage invariant.

4. **Fill the body** from `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/templates/spec.md`: replace the
   `{{frontmatter}}` line with the emitted block, set the `# {{Title}}`, and fill
   every section from the approved inputs. Honor the template's contract:
   - **Functional requirements in EARS**, numbered, one behavior each, each with ≥1
     acceptance criterion (Given-When-Then for flows, rule bullets for constraints).
   - **Significant unhappy paths as If/Then EARS**, driven by the coverage checklist;
     record each area's disposition (Specify/Defer-to-plan/N-A) in the `## Coverage` table at
     the end — not as an inline tag list inside the unhappy-paths section.
   - **Non-functional requirements as outcomes with a fit-criterion.**
   - **UI/UX references the actual Claude Design handoff output** (not a rewrite).
   - Plain language throughout, **no technical *how***. Delete sections that
     genuinely don't apply (UI/UX for non-user-facing work; Glossary when there are
     no terms). Leave **Open questions** empty (resolve or defer each before approval).
   - **Strip the author-guidance comments.** The template carries `<!-- AUTHOR
     GUIDANCE … -->` blocks (the EARS explainer, the coverage checklist, the
     defer-promise note) — they are for you, not the owner. **Delete every one.** The
     delivered spec contains only owner-facing content.

   Write the assembled file to `$SPEC`.

5. **Self-review** (look at the written file with fresh eyes; fix inline — no
   re-review loop):
   - **Placeholders & guidance:** any `{{…}}`, "TBD", "TODO", or leftover
     `<!-- AUTHOR GUIDANCE … -->` comment? Fill or remove it — the owner sees none of it.
   - **EARS + anti-slop:** does each functional requirement match an EARS pattern,
     state one behavior, avoid vague words, and carry an acceptance criterion? Split
     compound requirements; pin vague ones.
   - **No tech leaked:** any implementation detail (libraries, schemas, APIs) that
     belongs in the `plan`? Move it out — the spec is the *what*.
   - **Coverage:** does the `## Coverage` table disposition every area (Specify/Defer/N-A),
     with each `Specify` backed by a real UFR — and are the significant unhappy paths actually
     addressed, not just the happy path?
   - **Internal consistency:** do acceptance criteria and the definition of done
     match the requirements? Any section contradict another?
   - **Scope:** focused enough for one plan, or does it need decomposition?
   - **Ambiguity:** any requirement readable two ways? Pick one, make it explicit;
     repeat concrete nouns instead of "it/this".

6. **Return to `discovery`** with the path. Discovery owns the `review-spec` gate
   and the owner's final approval; this skill stops at "spec written and
   self-reviewed."

## Rationalization table

| Excuse | Reality |
| --- | --- |
| "I'll hand-write the frontmatter, it's just YAML" | The lib owns the §3.1 shape + parent invariant. Use `definition_doc.py frontmatter`. |
| "I'll resolve the path from the current dir" | Pin `--root "$(git rev-parse --show-toplevel)"` — a subdir cwd would misplace the spec. |
| "I'll re-mint the slug to be safe" | The slug is frozen at creation (§6.1). Reuse it for a revision; never re-mint. |
| "Plain prose is fine for requirements" | Functional requirements are EARS + acceptance criteria. That's the verifiable contract. |
| "A little tech detail clarifies it" | Tech is the `plan`. Keep the spec to the *what*. |
| "Owner approved the idea, I'll author straight off" | Author only from the *approved requirements*. If they weren't approved, back to `discovery`. |
