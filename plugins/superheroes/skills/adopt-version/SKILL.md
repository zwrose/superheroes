---
name: adopt-version
description: "Use in a live showrunner, workhorse, or detective seat after a newer superheroes version is installed — adopt it in place, no handoff and resume. Diffs the versions, re-reads what changed, runs TRANSITION's checklist, and briefs the owner. Not checkpoint or resume."
user-invocable: true
---

This skill speaks in host-neutral actions. Resolve them to your runtime's tools by reading the host tool map at `${CLAUDE_PLUGIN_ROOT}/hosts/<your-host>-tools.md` (the leading variable is this plugin's root directory) — `claude-tools.md` on Claude Code, `codex-tools.md` on Codex.

# adopt-version — take up a new plugin version in the live seat

The harness already reloads skills and agents into a live session when a newer plugin
version is installed. What goes stale is what **this seat** already holds: charter and
reference text it read earlier, absolute plugin-root paths baked into its commands, and
results or processes tied to the old version. This procedure adopts the new version **in
place** in the same seat. A fresh seat is the exception — step 3 names when that is right.

## Invocation

| Form | Behavior |
| --- | --- |
| `/superheroes:adopt-version` | Runs the nine steps below and ends with the owner brief. Optional argument: a target version (default: newest installed). |

## Step 1 — Find the versions

Name this seat's **charter** — the one it loaded (`showrunner`, `workhorse`, or
`detective`). `adopt-version` is not a charter and does not change which charter this seat
runs.

On Claude Code, call `charter_detect.detect_charter` over the session transcript the same
way checkpoint Step 1 does, as a cross-check. Where the host names no transcript, the seat
names its own charter from what it loaded.

Establish the **running version** from the first source that resolves, in order:

1. the bootstrap's resolved plugin root in context;
2. the plugin root in this seat's own recent commands;
3. a root recorded in the seat's durable state;
4. on Claude Code, the SessionStart injection recorded in the session transcript.

If none resolves, do not guess — ask the owner at step 8 and stop after the brief.

Run `plan` from the new helper (refusal tokens stop the procedure):

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"
ROLE="<showrunner|workhorse|detective>"
RUNNING_ROOT="<absolute path to the running version directory>"
CACHE_DIR="<plugin versions cache directory>"
TARGET="<optional X.Y.Z; omit for newest installed>"

python3 -B "$ROOT_DIR/lib/adopt_version.py" plan --role "$ROLE" \
  --from-root "$RUNNING_ROOT" \
  ${TARGET:+--to "$TARGET"}
# Or: --from <X.Y.Z> --cache-dir "$CACHE_DIR" instead of --from-root
```

A refusal (exit 1, `{"ok":false,"reason":...}`) is reported to the owner with its token.
`upToDate: true` ends with a one-line report.

From `toRoot`, read `TRANSITION.md` for **every** version in `transitionSections` (each
skipped patch still counts). Name any `missingTransitionSections` entry in the owner brief.

**Output:** from, to, the in-between versions, and the TRANSITION sections read.

## Step 2 — Sort the changes

Use the `plan` JSON buckets (`charter`, `covenantHooks`, `libs`, `other`) and their counts.

Within `libs`, mark which paths this seat actually calls — its charter's commands name
them. Treat the rest as read-only unless a TRANSITION section says their behaviour changed.

**Output:** the four buckets with counts, and the libs this seat calls.

## Step 3 — Re-read, scaled to what changed

**Charter bucket non-empty:** re-read the **whole** charter from disk under `toRoot` in one
read (`skills/showrunner/SKILL.md`, `skills/workhorse/SKILL.md`, or
`skills/detective/SKILL.md` — not diff hunks). Then re-read every changed reference page
the charter points to. Write one line `adopted <version>: what changed in my duties` into
the seat's durable state (the advisor's resume point; a builder's or detective's issue or
PR record).

**`rubric/covenant.md` changed:** re-read it. The copy injected at session start is stale;
the file on disk governs.

**`hooks/` changed:** tell the owner at step 8. Treat new hook behaviour as absent until a
restarted session proves it present.

**Only libs or other changed:** read the TRANSITION sections and only the changed doctrine
pages this seat uses.

**When a fresh seat is right:** the charter was restructured so heavily that context would
keep steering (whole duties moved or renamed), or context is nearly full — recommend
`/superheroes:checkpoint` and a fresh seat (an advisor seat resumes with
`/superheroes:showrunner-resume`), say why, and stop after the brief.

**Output:** the re-read list, the durable-state line, or the fresh-seat recommendation with
its reason.

## Step 4 — Take the live-process inventory, then run the adoption checklist

List every live process and run tied to the old root: builders launched on it, dispatch run
directories it opened, watch loops armed from it.

Run each item of TRANSITION's "Before you upgrade" and one-time steps for every version in
range: done, or not applicable with the reason. An item that stops, folds, or cleans up a
process is checked against the inventory first and **deferred** for anything in a live
old-root lane (step 7 decides when it runs). An item that needs the owner (sign-in,
configure choice, permission, waiver) goes to step 8 — never silently skipped.

**Output:** the inventory, and one disposition per checklist item — done, not applicable
(why), deferred (which lane), or owner input.

## Step 5 — Switch the plugin root

Every absolute path in this seat's commands now uses the new version directory (`toRoot`).
The bootstrap's resolved-roots block in context still names the old root; treat it as stale.

**Output:** the new root, stated once.

## Step 6 — Re-run the version-coupled checks

Run the conformance probe for each dispatchable engine on the new root — the command wave
preflight uses:

```bash
ROOT_DIR="<toRoot>"
RUN_DIR="<fresh run directory>"
python3 -B "$ROOT_DIR/lib/conformance_probe.py" run --engine <engine> ...
```

An owner word that existed only because of an old-version defect retires once its fresh
probe passes; name each retirement in the brief. If TRANSITION names new ledger record
kinds, do not write them while old-root lanes are live — readers on the old version cannot
fold a kind they do not know.

**Output:** one probe result per engine, any retired owner words, any held ledger kinds.

## Step 7 — Handle old-root processes

Live builders finish on the old root and are vetted against the doctrine they ran under.
New lanes launch on the new root. Watch loops armed from the old root are re-armed on the
new root after their lanes end — never killed. Run step 4's deferred items as each lane
ends.

While long old-root lanes run, name the cleanup risk: the old version directory is marked
`.orphaned_at` and can be removed under a running builder. For a lane that stops, read
`rubric/launch-doctrine.md` § Recovery.

**Output:** one disposition per inventory entry, and the cleanup risk named or "none live".

## Step 8 — Brief the owner

In chat, plain language: what changed that the owner will notice; what this seat changed in
its own practice; checklist items done; **inputs needed** — each a numbered decision with
context, options, consequences, and a recommendation per
`skills/showrunner/reference/owner-decisions.md` (read that page; do not restate its spine);
and residuals (old-root lanes still running, hooks awaiting a restart, missing TRANSITION
sections).

**Output:** the brief.

## Step 9 — Relay to consumer projects (showrunner only)

After the release is cut and installed, relay adoption notes to each consumer project's
advisor. Their memory is separate from this seat's, so the relay carries the steps
themselves, not a pointer to this seat's notes.

**Output:** one relay per consumer project, or "no consumers".
