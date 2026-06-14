---
name: writing-specs
description: Use to author the on-disk `spec` define-doc once an owner has APPROVED a set of requirements — normally invoked by the the-architect `discovery` skill, not directly by an owner idea. Mints the work-item slug, emits the CONVENTIONS §3.1 frontmatter via the lib, fills the spec body template (purpose, functional + significant-unhappy-path requirements, acceptance criteria, out-of-scope), writes `docs/superheroes/<work-item>/spec.md`, and runs a self-review. Does NOT elicit requirements (that is `discovery`) or design the technical approach (that is `plan`).
---

# writing-specs

Turn an **owner-approved** set of requirements into the on-disk `spec`
define-doc. This is the spec's analogue of superpowers `writing-plans`: the
dialogue happens in `discovery`; this skill owns the **artifact**. The frontmatter
linkage is machine-read, so it is emitted by the lib — never hand-written.

**Precondition:** the owner has approved the requirements (Discovery's HARD
GATE). If they have not, stop and return to `discovery` — do not author a spec
from un-approved requirements.

## Inputs (from `discovery`)

The approved: **title**, **purpose**, **functional requirements**, **significant
unhappy-path behaviors** (empty/initial states, errors & failures, edge &
boundary cases, access & permissions, input validation), **non-functional
requirements**, **UI/UX outcome** (if user-facing), **acceptance criteria**,
**out-of-scope**, and **`size`** (`small | medium | large`).

## Flow

1. **Mint the work-item** (once; it is then frozen — CONVENTIONS §6.1):

   ```bash
   WORK_ITEM=$(python3 "${CLAUDE_PLUGIN_ROOT}/lib/define_doc.py" mint --title "<title>")
   ```

   Reuse an existing slug if this spec already exists (a revision); never
   re-mint for the same work-item.

2. **Resolve the path** (Phase 1 is in-repo at the repo root):

   ```bash
   SPEC=$(python3 "${CLAUDE_PLUGIN_ROOT}/lib/define_doc.py" path --work-item "$WORK_ITEM" --doc spec)
   mkdir -p "$(dirname "$SPEC")"
   ```

3. **Emit the §3.1 frontmatter** with the lib (a fresh spec is `status: draft`,
   `gates.review: pending`, null parent):

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/lib/define_doc.py" frontmatter \
     --doc spec --work-item "$WORK_ITEM" --size "<size>"
   ```

   Do not hand-write the frontmatter — the lib owns its shape and the
   parent-linkage invariant.

4. **Fill the body** from `${CLAUDE_PLUGIN_ROOT}/templates/spec.md`: replace the
   `{{frontmatter}}` line with the emitted block, set the `# {{Title}}`, and
   fill every section from the approved inputs. Honor the template's depth
   contract: the happy path **plus** the significant unhappy paths that matter —
   captured as behavioral requirements and acceptance criteria, in plain
   language, **no technical *how***. Delete unhappy-path rows and the UI/UX
   section if they genuinely don't apply; leave **Open questions** empty (resolve
   or defer each before approval). Write the assembled file to `$SPEC`.

5. **Self-review** (look at the written file with fresh eyes; fix inline — no
   re-review loop):
   - **Placeholders:** any `{{…}}`, "TBD", or "TODO" left? Fill them.
   - **No tech leaked:** any implementation detail (libraries, schemas, APIs)
     that belongs in the `plan`? Move it out — the spec is the *what*.
   - **Coverage:** are the significant unhappy paths actually addressed, or only
     the happy path? If a coverage area was skipped, note it explicitly or fill
     it.
   - **Internal consistency:** do acceptance criteria match the requirements?
     Any section contradict another?
   - **Scope:** focused enough for one plan, or does it need decomposition?
   - **Ambiguity:** any requirement readable two ways? Pick one, make it explicit.

6. **Return to `discovery`** with the path. Discovery owns the owner review gate
   and the hand-off to `review-spec`; this skill stops at "spec written and
   self-reviewed."

## Rationalization table

| Excuse | Reality |
| --- | --- |
| "I'll hand-write the frontmatter, it's just YAML" | The lib owns the §3.1 shape + parent invariant. Use `define_doc.py frontmatter`. |
| "I'll re-mint the slug to be safe" | The slug is frozen at creation (§6.1). Reuse it for a revision; never re-mint. |
| "A little tech detail clarifies it" | Tech is the `plan`. Keep the spec to the *what*. |
| "Happy path is written, good enough" | The significant unhappy paths are the point. Check the coverage areas. |
| "Owner approved the idea, I'll author straight off" | Author only from the *approved requirements*. If they weren't approved, back to `discovery`. |
