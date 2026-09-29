---
name: adopt-version
description: "Use in a live showrunner, workhorse, or detective seat after a newer superheroes version is installed — adopt it in place, no handoff and resume. Diffs the versions, re-reads what changed, runs TRANSITION's checklist, and briefs the owner. Not checkpoint or resume."
user-invocable: true
---

This skill speaks in host-neutral actions. Resolve them to your runtime's tools by reading the host tool map at `${CLAUDE_PLUGIN_ROOT}/hosts/<your-host>-tools.md` (the leading variable is this plugin's root directory) — `claude-tools.md` on Claude Code, `codex-tools.md` on Codex.

# adopt-version — take up a new plugin version in the live seat

The harness already reloads skills and agents into a live session when a new version installs. What goes stale is what the seat holds: the charter and reference text it already read, the absolute plugin root in its commands, and any result or process tied to the old version. So the seat adopts the new version in place. A fresh seat is the exception, and step 3 names when.

## Invocation

| Form | Behavior |
| --- | --- |
| `/superheroes:adopt-version` | Runs the nine steps in order and ends with the owner brief. Optional argument: a target version (default: the newest installed). |

## Step 1 — Find the versions

1. Name this seat's charter: the one it loaded, showrunner, workhorse, or detective. `adopt-version` is not a charter and does not change which one this seat runs. On Claude Code, `charter_detect.detect_charter` over the session transcript is a cross-check, called as checkpoint Step 1 calls it. Where the host names no transcript, the seat names its own charter.
2. Establish the running version from the first source that resolves, in this order:
   - the bootstrap's resolved plugin root in context;
   - the plugin root in this seat's own recent commands;
   - a root recorded in the seat's durable state;
   - on Claude Code, the SessionStart injection recorded in the session transcript.

   If none resolves, do not guess. Ask the owner at step 8 and stop after the brief.
3. Run `plan` with the running root as `--from-root`. Add `--to <X.Y.Z>` when the owner named a target. When the running root is only a version number, pass `--from <X.Y.Z> --cache-dir <cache dir>` instead.

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"
python3 -B "$ROOT_DIR/lib/adopt_version.py" plan --role <showrunner|workhorse|detective> \
  --from-root "<running version directory>" [--to <X.Y.Z>]
```

A refusal ends the procedure. Report its `reason` token to the owner (`cache-dir-missing`, `from-not-installed`, `to-not-installed`, `to-older-than-from`, or `transition-unreadable`). When `upToDate` is `true`, end with a one-line report.

4. Read TRANSITION's section for every version in `transitionSections`, from the new root. A skipped patch version still counts. Name each entry of `missingTransitionSections` in the owner brief.

**Output:** the from and to versions, the versions in between, and the TRANSITION sections read.

## Step 2 — Sort the changes

Use the `buckets` from `plan`: `charter`, `covenantHooks`, `libs`, and `other`, each split into added, removed, and changed files.

1. Count the files in each bucket.
2. Within `libs`, mark the libraries this seat calls. Its charter's commands name them.
3. Read the rest only when a TRANSITION section says their behavior changed.

**Output:** the four buckets with their counts, and the libraries this seat calls.

## Step 3 — Re-read, scaled to what changed

1. When the `charter` bucket is not empty, re-read the whole charter from disk, from the new root, in one read. Do not read only the changed hunks: a duty triggered by an event can sit in text that looks unchanged. Then read every changed reference page the charter points to.
2. After that re-read, write one line into the seat's durable state: "adopted <version>: what changed in my duties". The advisor writes it at the top of its resume point. A builder or detective writes it to its issue or PR record.
3. When `rubric/covenant.md` changed, re-read it. The copy injected at session start is stale, and the file on disk governs.
4. When `hooks/` changed, tell the owner at step 8. Treat the new hook behavior as absent until a restarted session proves it present.
5. When only `libs` or `other` changed, read the TRANSITION sections and only the changed doctrine pages this seat uses.

A fresh seat is right in two cases. The charter was restructured so heavily that the copy in context would keep steering, meaning whole duties moved or were renamed. Or context is nearly full. In either case, recommend `/superheroes:checkpoint` and a fresh seat, say why, and stop after the brief. An advisor seat resumes with `/superheroes:showrunner-resume`.

**Output:** the list of pages re-read and the durable-state line, or the fresh-seat recommendation with its reason.

## Step 4 — Take the live-process inventory, then run the adoption checklist

1. List every live process and run tied to the old root: builders launched on it, dispatch run directories it opened, and watch loops armed from it.
2. Run each item of TRANSITION's "Before you upgrade" section and its one-time steps, for every version in range. Mark each item done, or not applicable with the reason.
3. Check any item that stops, folds, or cleans up a process or run against the inventory first. **Defer** it for anything that belongs to a live old-root lane. Step 7 decides when it runs.
4. Send any item that needs the owner to step 8: a sign-in, a configure choice, a permission, or a waiver. Never skip one silently.

**Output:** the inventory, and one disposition per checklist item: done, not applicable (why), deferred (which lane), or owner input.

## Step 5 — Switch the plugin root

Do this once step 4 is complete. From here on, every absolute path in this seat's commands uses the new version directory, `toRoot` from `plan`. The bootstrap's resolved-roots block in context still names the old root. Treat that block as stale.

**Output:** the new root, stated once.

## Step 6 — Re-run the version-coupled checks

1. Run the conformance probe for each dispatchable engine on the new root, into a fresh run directory. It is the command the wave preflight uses.

```bash
ROOT_DIR="<the new root>"
python3 -B "$ROOT_DIR/lib/conformance_probe.py" run --engine <codex|cursor|claude> --run-dir "<fresh empty directory>"
```

2. Retire an owner word that existed only because of an old-version defect once the fresh probe passes. Name each retirement in the brief.
3. When TRANSITION names new ledger record kinds, do not write them while old-root lanes are live. Readers on the old version cannot fold a kind they do not know.

**Output:** one probe result per engine, any retired owner words, and any held ledger kinds.

## Step 7 — Handle old-root processes

1. Let live builders finish on the old root. Vet each one against the doctrine it ran under.
2. Launch new lanes on the new root.
3. Re-arm each watch loop armed from the old root on the new root after its lanes end. Never kill one.
4. Run step 4's deferred items as each lane ends.
5. While long old-root lanes run, name the cleanup risk to the owner. The old version directory is marked `.orphaned_at`, and the host can remove it under a running builder.
6. For a lane that stops, follow `rubric/launch-doctrine.md` § Recovery — taking over a build that stopped.

**Output:** one disposition per inventory entry, and the cleanup risk named, or "none live".

## Step 8 — Brief the owner

Brief the owner in chat, in plain language:

1. What changed that the owner will notice.
2. What this seat changed in its own practice.
3. The checklist items done.
4. The inputs needed. Give each as a numbered decision with its context, options, consequences, and a recommendation, as `skills/showrunner/reference/owner-decisions.md` sets out.
5. The residuals: old-root lanes still running, hooks awaiting a restart, and missing TRANSITION sections.

**Output:** the brief.

## Step 9 — Relay to consumer projects (showrunner only)

Skip this step in a workhorse or detective seat. After the release is cut and installed, relay adoption notes to each consumer project's advisor. Their memory is separate from this seat's, so the relay carries the steps themselves, not a pointer to this seat's notes.

**Output:** one relay per consumer project, or "no consumers".
