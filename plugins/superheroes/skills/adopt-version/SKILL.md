---
name: adopt-version
description: "Use in a live showrunner, workhorse, or detective seat after a newer superheroes version is installed — adopt it in place, no handoff and resume. Diffs the versions, re-reads what changed, runs TRANSITION's checklist, and briefs the owner. Not checkpoint or resume."
user-invocable: true
---

This skill speaks in host-neutral actions. Resolve them to your runtime's tools by reading the host tool map at `${CLAUDE_PLUGIN_ROOT}/hosts/<your-host>-tools.md` (the leading variable is this plugin's root directory) — `claude-tools.md` on Claude Code, `codex-tools.md` on Codex.

# adopt-version — take up a new plugin version in the live seat

On Claude Code, the host already reloads skills and agents into a live session when a newer plugin
installs. What goes stale is what **this seat** still holds: charter and reference text
already read into context, absolute plugin-root paths baked into commands and launches, and
results or processes tied to the old version directory. This skill adopts the new version
**in place** — no deliberate handoff and no resume pick-up. A fresh seat is the exception
step 3 names when re-reading cannot safely retarget the live context.

## Invocation

| Form | Behavior |
| --- | --- |
| `/superheroes:adopt-version` | Runs the nine steps below and ends with an owner brief. Optional argument: a target version (default: newest installed). |

## Step 1 — Find the versions

Name this seat's **charter** — the one it loaded when it became a showrunner, workhorse, or
detective seat (`adopt-version` is not a charter and does not change which charter this seat
runs). On Claude Code, call `charter_detect.detect_charter` over the session transcript as
checkpoint Step 1 does — a cross-check only. Where the host names no transcript, the seat
names its own charter from how it was invoked.

Establish the **running version** from the first source that resolves, in order: the
bootstrap's resolved plugin root in context; the plugin root in this seat's own recent
commands; a root recorded in the seat's durable state; on Claude Code, the SessionStart
injection recorded in the session transcript. If none resolves, do not guess — carry the gap
to step 8 and stop after the brief.

Run `plan` on the new install (role = this seat's charter). The helper, `lib/adopt_version.py`,
runs from the new version's directory because the running version may predate it.

```bash
RUNNING_ROOT="<absolute path to the running version directory>"
ROLE="<showrunner|workhorse|detective>"
CACHE_DIR="$(dirname "$RUNNING_ROOT")"
NEW_ROOT="<CACHE_DIR/the target version: the highest version directory listed in CACHE_DIR, or the version the owner named>"
python3 -B "$NEW_ROOT/lib/adopt_version.py" plan --role "$ROLE" \
  --from-root "$RUNNING_ROOT" --to "$(basename "$NEW_ROOT")"
```

A refusal (exit 1, `{"ok":false,"reason":...}`) stops the procedure — report the reason token
to the owner. When `upToDate: true`, end with a one-line report. Read TRANSITION's section
for **every** version listed in `transitionSections` (each patch in range counts) from the
new root (`toRoot`). Name any `missingTransitionSections` entries in the owner brief.

**Output:** from, to, the in-between versions, and the TRANSITION sections read.

## Step 2 — Sort the changes

Use the `plan` JSON buckets: `charter`, `covenantHooks`, `libs`, and `other`. Within
`libs`, mark which modules this seat actually calls — its charter's commands and reference
pages name them; treat the rest as read-only unless a TRANSITION section says their behaviour
changed.

**Output:** the four buckets with counts, and the libs this seat calls.

## Step 3 — Re-read, scaled to what changed

When the **charter** bucket is non-empty: re-read the **whole** charter for this seat from
disk under the new root in one read (not diff hunks — duties triggered by events hide in
text that looks unchanged), then every changed reference page the charter points to, and
write one line `adopted <version>: what changed in my duties` into the seat's durable state
(the advisor's resume point; a builder's or detective's issue or PR record).

When `rubric/covenant.md` changed: re-read it — the copy injected at session start is stale
and the file on disk governs. When `hooks/` changed: tell the owner at step 8 and treat new
hook behaviour as absent until a restarted session proves it present.

Whatever the charter bucket holds, when `libs` or `other` changed: read the TRANSITION
sections and every changed doctrine page this seat uses (a shared rubric page counts) — a
charter change never excuses skipping a changed rubric page.

**When a fresh seat is right:** the charter was restructured so heavily that context would
keep steering on old duty boundaries (whole duties moved or renamed), or context is nearly
full — then recommend `/superheroes:checkpoint` and a fresh seat (an advisor seat resumes
with `/superheroes:showrunner-resume`), say why, and stop after the brief.

**Output:** the re-read list, the durable-state line, or the fresh-seat recommendation with
its reason.

## Step 4 — Take the live-process inventory, then run the adoption checklist

First list every live process and run still tied to the **old** root: builders launched on
it, dispatch run directories it opened, watch loops armed from it.

Then run each item of TRANSITION's "Before you upgrade" and one-time steps for every
version in range — done, or not applicable with the reason. An item that stops, folds, or
cleans up a process or run is checked against the inventory first and **deferred** when it
belongs to a live old-root lane (step 7 decides when it runs). An item that needs the owner
(a sign-in, a configure choice, a permission, a waiver) goes to step 8 — never silently
skipped. While any item is awaiting owner input, **stop before step 5**: brief the owner now
(step 8's shape, inputs needed first) and resume at step 5 once the item is resolved — the
root does not switch, and no new lane launches, on an unmet prerequisite.

**Output:** the inventory, and one disposition per checklist item — done, not applicable
(why), deferred (which lane), or owner input (adoption stopped here until resolved).

## Step 5 — Switch the plugin root

Every absolute path in this seat's new commands and launches now uses the new version directory
(`toRoot` from `plan`). The one exception: a command that continues a live old-root dispatch
run (`dispatch-review`, `dispatch-write`) stays on the old root's command, on the same run
directory, until that run reaches a terminal result — the new dispatcher can refuse a run the
old one opened (for example `run-dir-claude-mode-retired`). The bootstrap's resolved-roots
block in context still names the old root — treat it as stale.

**Output:** the new root, stated once.

## Step 6 — Re-run the version-coupled checks

On the new root, run the conformance probe for each dispatchable engine the wave preflight
uses:

```bash
ROOT_DIR="<toRoot from plan>"
ENGINE="<engine>"
RUN_DIR="<fresh empty directory, one per engine>"
python3 -B "$ROOT_DIR/lib/conformance_probe.py" run --engine "$ENGINE" --run-dir "$RUN_DIR"
```

Run it once for each engine this seat dispatches through; an advisor seat runs it for every
dispatchable engine (`codex`, `cursor`, `claude`), as the wave preflight does. An owner word that existed only because of an
old-version defect retires once its fresh probe passes — name each retirement in the brief.
If TRANSITION names new ledger record kinds, do not write them while old-root lanes are live
(readers on the old version cannot fold a kind they do not know).

**Output:** one probe result per engine, any retired owner words, any held ledger kinds.

## Step 7 — Handle old-root processes

Live builders finish on the old root and are vetted against the doctrine they ran under. New
lanes launch on the new root. Watch loops armed from the old root are re-armed on the new
root after their lanes end — never killed. Live dispatch runs finish through their old-root
command (step 5's exception), never migrated mid-run. Run step 4's deferred items as each
lane ends.

While long old-root lanes run, name the cleanup risk: the old version directory may be marked
`.orphaned_at` and removed under a running builder. For a lane that stops, read
`rubric/launch-doctrine.md` § Recovery.

**Output:** one disposition per inventory entry, and the cleanup risk named or `none live`.

## Step 8 — Brief the owner

In chat, plain language: what changed that the owner will notice; what this seat changed in
its own practice; checklist items done; **inputs needed** — each as a numbered decision with
its context, options, consequences, and a recommendation per
`skills/showrunner/reference/owner-decisions.md` (read that page; do not restate its spine);
and residuals (old-root lanes still running, hooks awaiting a restart, missing TRANSITION
sections).

**Output:** the brief.

## Step 9 — Relay to consumer projects (showrunner only)

When this seat is the showrunner charter and the release is cut and installed, relay adoption
notes to each consumer project's advisor. Their memory is separate from this seat's — the
relay carries the steps themselves, not a pointer to this seat's notes.

**Output:** one relay per consumer project, or `no consumers`.
