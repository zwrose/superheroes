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

Establish the **running version** from the first source that resolves, in order: a
`plugin version taken up: <from> -> <to>` line this seat itself wrote in its durable state
(the running root is the host cache directory plus **to**); the bootstrap's resolved plugin root in context; the
plugin root in this seat's own recent commands; on Claude Code, the SessionStart injection
recorded in the session transcript. If none resolves, do not guess — carry the gap to step 8
and stop after the brief.

### After compaction

Compaction and SessionStart recovery do **not** read this skill, and checkpoint's compact
command does not restate this procedure. On Claude Code 2.1.283, a seat that took up a newer
version in place and then compacted received a SessionStart bootstrap that named the newly
installed plugin root and a charter-recovery path under it. That behaviour was observed on
that harness version and is not guaranteed.

After any compaction, this seat's **first** act is to check the injected plugin root against
its `plugin version taken up` line (present when checkpoint Step 4 part 3 preserved it). The
root matches when it is the host cache directory plus the **to** version in that line. When
it matches, continue on it. Only when it does not match, re-run `/superheroes:adopt-version`
before acting, retarget every command to **toRoot**, and re-read the charter from **toRoot**,
not from a recovery path that names another root.

Name the **host-provided plugin root** — the bootstrap's resolved plugin root in context, or
on Claude Code the SessionStart injection when the bootstrap block is absent. Before anything
runs from `NEW_ROOT`, `CACHE_DIR` must equal the parent directory of that host-provided root.
If `$(dirname "$RUNNING_ROOT")` disagrees, stop and carry the mismatch to step 8 — do not
trust a root copied from an issue or PR record for this check.

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
new root (`toRoot`).

Read `unresolvedGaps` from `plan`. Every entry is **unresolved** and holds adoption before
step 5. An entry with reason `changelog-unreadable` means `CHANGELOG.md` at `toRoot` is missing
or unreadable, so no crossed version has recorded evidence. An entry with reason `no-section`
names a crossed version that has neither a TRANSITION section nor a CHANGELOG section. Take
each entry to the owner as a numbered input at step 8.

For each version in `missingTransitionSections` that `changelogSections` lists, read that
version's section in `CHANGELOG.md` at `toRoot`. When the section names a removal, rename,
breaking change, or newly required argument, result key, result shape, or step, mark that
version **unresolved** too. Otherwise record **no TRANSITION section (no consumer-visible
change recorded)**, which does not hold. TRANSITION adds a section only when a release drops,
renames, or newly requires an argument, a result key, or a result shape, so a readable
CHANGELOG section that names none of these is the evidence that nothing changed.

**Output:** from, to, the in-between versions, TRANSITION sections read, every `unresolvedGaps`
entry, and each `missingTransitionSections` version that `changelogSections` lists as either
**no TRANSITION section (no consumer-visible change recorded)** or **unresolved** (why).

**Gate before step 2:** Do not run steps 2–7 until every version in
`missingTransitionSections` has a disposition: an `unresolvedGaps` entry, **unresolved** from
its CHANGELOG section, or **no TRANSITION section (no consumer-visible change recorded)**.
Any **unresolved** version or `unresolvedGaps` entry holds adoption before step 5.

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
write one line `adopted <version>: what changed in my duties` into this seat's durable state
(the showrunner advisor's resume point; a workhorse builder's PR build record, or an issue
comment before the PR exists; a detective seat keeps it in-session and carries it in the
diagnosis receipt when it posts one — never as a separate tracker write).

When `rubric/covenant.md` changed: re-read it — the copy injected at session start is stale
and the file on disk governs. When `hooks/` changed: tell the owner at step 8 and treat new
hook behaviour as absent until a restarted session proves it present.

When `libs` changed: for **each** changed module in the `libs` bucket that step 2 marked as
called by this seat, read that module from disk under the new root (or its diff against the
old root) so you know what changed in behaviour you invoke — not only what TRANSITION says
about interfaces. When `libs` or `other` changed — even when the charter bucket also changed:
read every TRANSITION section in `transitionSections` (step 1 already dispositioned each
`missingTransitionSections` version via `CHANGELOG.md` at `toRoot` — do not treat this re-read
as a substitute for that review) and every changed doctrine page in `other` this seat uses
(charter re-read above already covers that seat's reference tree).

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
(a sign-in, a configure choice, a permission, a waiver) is **owner input** — never silently
skipped. When any checklist item is owner input, stop after step 4: brief the owner at
step 8 with those items as numbered decisions, and do not run steps 5–7 until each is
resolved; then resume adoption from step 5.

**Output:** the inventory, and one disposition per checklist item — done, not applicable
(why), deferred (which lane), or owner input.

## Step 5 — Switch the plugin root

Skip this step while step 4 left any owner-input checklist item unresolved, or step 1 left
any `unresolvedGaps` entry or CHANGELOG-derived **unresolved** version. **No TRANSITION section
(no consumer-visible change recorded)** is not a gap when the CHANGELOG section for that
version was readable and named no consumer-visible change. It does not hold step 5 once
step 4 is clear. When step 1 left any **unresolved** entry or version, stop after step 4: brief
the owner at step 8 with each as a numbered decision, and do not run steps 5–7 until each is
resolved (release supplies a section or the owner accepts no action); then resume adoption
from step 5.

Every absolute path in this seat's commands and launches now uses the new version directory
(`toRoot` from `plan`), **except** commands that continue a live dispatch run the inventory
named: keep each such run pinned to its old-root dispatcher and run directory until that run
reaches a terminal result — never retarget continuation to the new root mid-run. The
bootstrap's resolved-roots block in context still names the old root — treat it as stale.

Do **not** write `plugin version taken up` yet — step 6 must pass first. Until that line
exists, treat adoption as **pending**: do not open new dispatch lanes on the new root (step 7
waits).

**Output:** the new root, stated once, and that adoption is pending probe success.

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

When **any** required probe fails: stop after step 8 — brief the owner with the failing engine
and output, leave adoption **pending** (no `plugin version taken up` line), and do not run
step 7's new-root lanes until probes pass or the owner rules otherwise.

When **every** required probe passes, write one line
`plugin version taken up: <from> -> <to>` (versions only — never absolute cache paths) into
this seat's durable state (the showrunner advisor's resume point; a workhorse builder's PR
build record, or an issue comment before the PR exists; a detective seat keeps it in-session
and carries it in the diagnosis receipt when it posts one — never as a separate tracker write).
When a detective seat may run `/superheroes:checkpoint` before that receipt, put this same
`plugin version taken up` line in checkpoint Step 4's **live-state one-liner** (part 3) so
compaction preserves it — checkpoint's five parts do not require it on their own. That line
decides only when it disagrees with the bootstrap block or SessionStart injection, on the
next adoption and after compaction.

**Output:** one probe result per engine, any retired owner words, any held ledger kinds, and
confirmation the taken-up line was written — or the failure that blocked it.

## Step 7 — Handle old-root processes

Live builders finish on the old root and are vetted against the doctrine they ran under. New
lanes launch on the new root. Watch loops armed from the old root are re-armed on the new
root after their lanes end — never killed. Run step 4's deferred items as each lane ends.

While long old-root lanes run, name the cleanup risk: the old version directory may be marked
`.orphaned_at` and removed under a running builder. For a lane that stops, read
`rubric/launch-doctrine.md` § Recovery.

**Output:** one disposition per inventory entry, and the cleanup risk named or `none live`.

## Step 8 — Brief the owner

In chat, plain language: what changed that the owner will notice; what this seat changed in
its own practice; checklist items done; **inputs needed** — each as a numbered decision with
its context, options, consequences, and a recommendation per
`skills/showrunner/reference/owner-decisions.md` (read that page; do not restate its spine);
and residuals (old-root lanes still running, hooks awaiting a restart, **unresolved**
TRANSITION gaps from step 1, and any **no TRANSITION section (no consumer-visible change
recorded)** entries named for awareness).

**Output:** the brief.

## Step 9 — Relay to consumer projects (showrunner only)

When this seat is the showrunner charter and the release is cut and installed, relay adoption
notes to each consumer project's advisor. Their memory is separate from this seat's — the
relay carries the steps themselves, not a pointer to this seat's notes.

**Output:** one relay per consumer project, or `no consumers`.
