<!-- quick-route-version: 2 -->

## Contents

Quick discovery — the **spec-less-but-never-review-less** flow the-architect runs for a genuine
chore, once the owner has signed off on the `quick` route at the framing brief (parent SKILL,
`## Route: full or quick` / step 5).
Sections: **Author the tasks doc** · **The alignment probe** · **The owner's direction gate** ·
**Gate write + launch**. Host actions resolve via the host tool map (parent SKILL). On this route
you write the **task list directly** — no spec, no plan — a single-dispatch probe grades it
independently, the owner approves the **direction**, and the showrunner takes it from build.

Resolve the lib dir and the work-item once:

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
ROOT=$(git rev-parse --show-toplevel)
WORK_ITEM=$(python3 "$ROOT_DIR/lib/definition_doc.py" mint --title "<concise chore title>")
```

## Author the tasks doc (with clarifying questions)

Quick is **not** mechanical transcription — an issue is not assumed clear enough to go straight to
tasks. But the **gather + frame** phase already ran before the route was chosen at the framing
brief (parent SKILL, step 5), so most clarifying dialogue has already happened. **Ask only what is
still genuinely ambiguous** — one question at a time — and **never re-ask** something the gather
phase already settled. If nothing is left open, say so and proceed. Never assume the *what*.

Place the doc **exactly where the tasks phase writes it today** (the mode-aware, spec-anchored
resolver — the showrunner's own intake reads that path), so downstream is byte-identical:

```bash
TASKS=$(python3 "$ROOT_DIR/lib/definition_doc.py" resolve-write \
  --work-item "$WORK_ITEM" --doc tasks --root "$ROOT") \
  || { echo "cannot place the tasks doc safely (see message above) — stop." >&2; exit 1; }
# --orphan emits a NULL parent: a quick tasks doc has no plan/spec ancestor (CONVENTIONS §3.1/§3.4).
# Add --issue <n> when a GitHub issue exists.
python3 "$ROOT_DIR/lib/definition_doc.py" frontmatter \
  --doc tasks --work-item "$WORK_ITEM" --size small --orphan > "$TASKS"
```

Then **author the body below the frontmatter, in the normal tasks-doc shape** (CONVENTIONS §3.2)
so every downstream consumer is unchanged:

- A short **Goal / Architecture / Tech-Stack** header, then bite-sized **`### Task N: Title`**
  checkbox TDD steps. The `### Task N:` colon form is how the build enumerates tasks — keep it.
- Each task carries **exact file paths, the complete code for that step, and a verify line** (the
  exact test/command + expected output). The verify line is non-negotiable — the probe checks it.
- **No placeholders** ("TBD", "handle edge cases", "similar to Task N"). Every step is concrete
  and executable, or it is not done. Set `--size` from the chore's scope (usually `small`).

## The alignment probe (single dispatch — one leaf, never a loop)

Before the owner gate, dispatch **ONE fresh-context agent** — independent eyes; the authoring
context never grades its own homework. Conceptually it is review-spec's much simpler sibling (lower
risk ⇒ one leaf, not a loop). Give it the **issue text** + the **authored tasks doc** and have it
check three axes, returning a short findings list (axis · what is wrong · which task/ask):

- **Coverage** — does every ask in the issue map to a task?
- **Scope creep** — does any task exceed what the issue asked?
- **Verifiability** — does each task carry a verify line?

**One leaf — never a loop.** If findings would grow into rounds, that is scope creep on quick
discovery itself: a chore that needs iterative task review is not a chore — **re-route to `full`**.

Resolve findings **conversationally in-session**: fix the tasks doc (add the missing task, trim the
over-reaching one, add the verify line). A seeded coverage gap / scope-creep mismatch **blocks the
gate until resolved** — do not proceed to the owner with open probe findings.

## The owner's direction gate (plain language)

The owner's sign-off is a **direction** check, not a quality review — the audience is a
possibly-non-technical owner. **Task quality is your job (plus the probe), never theirs.**

Present **one sentence per task** — "here's what I'm about to build" — in plain language, plus the
honest **scope line** (chore size + what it touches). Ask: *"Does this look like the right thing to
build? Say go and the showrunner takes it from here."* Don't show frontmatter, code, or verify
commands unless asked. **Proceed only on the owner's explicit approval.**

## Gate write + launch

On approval, record the tasks doc's review gate (the owner's direction sign-off) via the existing
gate machinery — the fenced `set-gate` (content-hash + run-id), computed on the **final** doc:

```bash
HASH=$(python3 "$ROOT_DIR/lib/definition_doc.py" content-hash --path "$TASKS")
python3 "$ROOT_DIR/lib/definition_doc.py" set-gate \
  --doc tasks --work-item "$WORK_ITEM" --review passed --root "$ROOT" \
  --expected-hash "$HASH" --run-id "discovery-$WORK_ITEM"
```

This writes `gates.review: passed` (deriving `status: approved`) — the signal the showrunner's
**route-aware pre-flight** reads on the quick route.

Then **launch the showrunner**: invoke the `showrunner` skill. Its pre-flight derives `quick` from
the on-disk artifact (a tasks doc present, **no** spec), gates on the tasks doc, and the launch
declares `args.route = "quick"` to the spine. You never free-type the route — it is derived and
validated by the pre-flight (only ever `full`/`quick`), so a typo can't slip past intake.

**Honor the PR-1 intake contract** — the spine's `resolveIntake` fails closed:

- quick requires a **tasks doc present and NO spec**; if a spec is also present, a declared `quick`
  **conflicts** and is refused — reconcile the artifact/route before relaunching.
- a **missing or malformed** tasks artifact refuses to launch — it never silently falls back to (or
  past) the full path.

The gate write above therefore must land on a well-formed tasks doc at the resolved path (it does —
the same `resolve-write` resolver placed it, and `set-gate` re-reads it), or the showrunner refuses.

The showrunner then drives **build → review-code panel → verify → back-half → a ready-for-review
PR** with review evidence + the scope line. **Spec-less is never review-less** (CONVENTIONS §3.4).
It **never merges** — that is always the owner's.
