---
name: adopt-version
description: "Use in a live showrunner, workhorse, or detective seat after a newer superheroes version is installed — adopt it in place, no handoff and resume. Diffs the versions, re-reads what changed, runs TRANSITION's checklist, and briefs the owner. Not checkpoint or resume."
user-invocable: true
---

This skill speaks in host-neutral actions. Resolve them to your runtime's tools by reading the host tool map at `${CLAUDE_PLUGIN_ROOT}/hosts/<your-host>-tools.md` (the leading variable is this plugin's root directory) — `claude-tools.md` on Claude Code, `codex-tools.md` on Codex.

# adopt-version — take up a new plugin version in the live seat

The harness already reloads skills and agents into a live session when a new version installs. What goes stale is what this seat holds: the charter and reference text it already read, the absolute plugin root in its commands, and results or processes tied to the old version. This skill adopts the new version in place. A fresh seat is the exception, and step 3 names when.

`adopt-version` is not a charter. The seat keeps running the charter it loaded.

## Invocation

| Form | Behavior |
| --- | --- |
| `/superheroes:adopt-version` | Runs the nine steps and ends with the owner brief. Optional argument: a target version (default: newest installed). |

## Step 1 — Find the versions

1. Name this seat's charter: the one it loaded, showrunner, workhorse, or detective. On Claude Code, cross-check with `charter_detect.detect_charter` over the session transcript, called as Step 1 of `skills/checkpoint/SKILL.md` calls it. Where the host names no transcript, the seat names its own charter.
2. Establish the running version from the first source that resolves, in this order:
   - the plugin root the bootstrap resolved, in context.
   - the plugin root in this seat's own recent commands.
   - a root recorded in the seat's durable state.
   - on Claude Code, the SessionStart injection recorded in the session transcript.

   If none resolves, do not guess. Ask the owner at step 8 and stop after the brief.
3. Run `plan` with the seat's charter as the role:

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"
python3 -B "$ROOT_DIR/lib/adopt_version.py" plan --role "<showrunner|workhorse|detective>" \
  --from-root "<running version directory>" [--to "<X.Y.Z>"]
```

4. Where only the running version number is known, pass `--from <X.Y.Z> --cache-dir <cache dir>` in place of `--from-root`.
5. Read the result. A refusal exits 1 with a `reason` token: `cache-dir-missing`, `from-not-installed`, `to-not-installed`, `to-older-than-from`, or `transition-unreadable`. Stop, and report the token to the owner. When `upToDate` is `true`, end with a one-line report.
6. Read TRANSITION's section for every version in `transitionSections` from the new root. A skipped patch version still counts. Name each entry in `missingTransitionSections` in the owner brief.

**Output:** the from and to versions, the in-between versions, and the TRANSITION sections read.

## Step 2 — Sort the changes

Use the `plan` buckets: `charter`, `covenantHooks`, `libs`, and `other`, each with added, removed, and changed files.

Within `libs`, mark the ones this seat calls. Its charter's commands name them. Read the rest only when a TRANSITION section says their behavior changed.

**Output:** the four buckets with their counts, and the libs this seat calls.

## Step 3 — Re-read, scaled to what changed

1. When the `charter` bucket is not empty, re-read the whole charter from the new root in one read. Do not read the diff hunks, because a duty that fires on an event hides in text that looks unchanged. Then re-read every changed reference page the charter points to.
2. After that re-read, write one line into the seat's durable state: "adopted <version>: what changed in my duties". The durable state is the advisor's resume point, or a builder's or detective's issue or PR record.
3. When `rubric/covenant.md` changed, re-read it. The copy injected at session start is stale, and the file on disk governs.
4. When `hooks/` changed, tell the owner at step 8. Treat the new hook behavior as absent until a restarted session proves it present.
5. When only `libs` or `other` changed, read the TRANSITION sections and only the changed doctrine pages this seat uses.

A fresh seat is right when the charter was restructured so heavily that the copy in context would keep steering, meaning whole duties moved or were renamed. It is also right when context is nearly full. Then recommend `/superheroes:checkpoint` and a fresh seat, say why, and stop after the brief. An advisor seat resumes with `/superheroes:showrunner-resume`.

**Output:** the re-read list and the durable-state line, or the fresh-seat recommendation with its reason.

## Step 4 — Take the live-process inventory, then run the adoption checklist

1. List every live process and run tied to the old root. Include builders launched on it, dispatch run directories it opened, and watch loops armed from it.
2. Run each item of TRANSITION's "Before you upgrade" and its one-time steps, for every version in range. Mark each one done, or not applicable with the reason.
3. Check any item that stops, folds, or cleans up a process or run against the inventory first. Defer it for anything that belongs to a live old-root lane. Step 7 decides when it runs.
4. Send any item that needs the owner to step 8. A sign-in, a configure choice, a permission, and a waiver all count. Never skip one silently.

**Output:** the inventory, and one disposition per checklist item: done, not applicable (why), deferred (which lane), or owner input.

## Step 5 — Switch the plugin root

1. Use the new version directory, the `toRoot` from `plan`, in every absolute path this seat's commands build from here on.
2. Re-derive from `toRoot` any path this seat holds in a variable or a note.
3. Treat the bootstrap's resolved-roots block in context as stale, because it still names the old root.

**Output:** the new root, stated once.

## Step 6 — Re-run the version-coupled checks

1. Run the conformance probe for each dispatchable engine on the new root, into a fresh run directory. The command is `lib/conformance_probe.py` with `run --engine <e>`, the one the wave preflight uses.
2. Retire an owner word that existed only because of an old-version defect once its fresh probe passes. Name each retirement in the brief.
3. When TRANSITION names a new ledger record kind, hold it. Do not write it while old-root lanes are live, because a reader on the old version cannot fold a kind it does not know.

**Output:** one probe result per engine, any retired owner words, and any held ledger kinds.

## Step 7 — Handle old-root processes

1. Let live builders finish on the old root. Vet them against the doctrine they ran under.
2. Launch new lanes on the new root.
3. Re-arm each watch loop armed from the old root on the new root, after its lanes end. Never kill one.
4. Run step 4's deferred items as each lane ends.
5. While a long old-root lane runs, name the cleanup risk: the old version directory is marked `.orphaned_at` and can be removed under a running builder.

For a lane that stops, follow `rubric/launch-doctrine.md` § Recovery.

**Output:** one disposition per inventory entry, and the cleanup risk named or "none live".

## Step 8 — Brief the owner

Write the brief in chat, in plain language. Cover:

1. What changed that the owner will notice.
2. What this seat changed in its own practice.
3. The checklist items done.
4. The inputs needed. State each as a numbered decision with its context, options, consequences, and a recommendation, as `skills/showrunner/reference/owner-decisions.md` sets out.
5. The residuals: old-root lanes still running, hooks awaiting a restart, and missing TRANSITION sections.

**Output:** the brief.

## Step 9 — Relay to consumer projects (showrunner only)

Run this step only in a showrunner seat. After the release is cut and installed, relay adoption notes to each consumer project's advisor. Their memory is separate from this seat's, so the relay carries the steps themselves, not a pointer to this seat's notes.

Each relay holds:

1. The from and to versions.
2. The TRANSITION items that apply to that project, written out as steps.
3. The owner inputs still open for that project.

**Output:** one relay per consumer project, or "no consumers".
