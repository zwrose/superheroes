---
name: checkpoint
description: "Use before compaction in a showrunner or workhorse charter session — freshen live state and emit a ready-to-paste `/compact` command. `/compact` has no programmatic trigger; one paste is the floor. Not configure, review, or discovery."
user-invocable: true
---

This skill speaks in host-neutral actions. Resolve them to your runtime's tools by reading the host tool map at `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/hosts/<your-host>-tools.md` (the leading variable is this plugin's root directory) — `claude-tools.md` on Claude Code, `codex-tools.md` on Codex.

# checkpoint

Prepare a **long-lived charter session** (Showrunner advisor or Workhorse builder) for
context compaction. This skill does **not** compact by itself — `/compact` has no
programmatic trigger on any host, so the floor is: **run checkpoint, paste the emitted
command once.** After compaction, the SessionStart recovery hook re-injects a pointer to
re-read the charter skill from disk, so the owner does **not** need to re-invoke
`/superheroes:showrunner` or `/superheroes:workhorse` by hand.

## Invocation

| Form | Behavior |
| --- | --- |
| `/superheroes:checkpoint` | Detect the charter, freshen the resume point, verify live state, emit a ready-to-paste `/compact` line. Refuse plainly when this is not a charter session. |

## Step 1 — Detect this session's charter

Resolve the session's **transcript path** first — the absolute path to this session's
JSONL transcript. On Claude Code, hook payloads name it in the common field
`transcript_path` (see the host hooks reference); if this session pinned that path earlier,
use the pin — never re-discover by newest file (`rubric/launch-doctrine.md` § Pin the
transcript). On Codex, follow `codex-tools.md` for the equivalent session record path.

Then call `charter_detect.detect_charter(transcript_path)` from the plugin lib. The
function scans the transcript forward from the start (up to 200 MB), matches user records
whose message content contains `<command-name>/superheroes:showrunner</command-name>` or
`<command-name>/superheroes:workhorse</command-name>`, ignores sidechain records, and
returns the **last** charter name it finds (`"showrunner"`, `"workhorse"`, or `None`). It
never raises — a missing file, bad JSON line, or any internal error returns `None`.

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
TRANSCRIPT_PATH="<absolute path to this session's transcript>"
python3 -B -c "
import sys, os
sys.path.insert(0, os.path.join('$ROOT_DIR', 'lib'))
import charter_detect
print(charter_detect.detect_charter('$TRANSCRIPT_PATH'))
"
```

**If the result is `None`** → refuse with a plain, friendly message: `checkpoint` is for
charter sessions (`/superheroes:showrunner` or `/superheroes:workhorse`); this session is
not one. Stop — no error traceback, no partial `/compact` output.

## Step 2 — Freshen and validate the resume point

**If** this session keeps a resume point at the top of its ledger, bring it up to date and
confirm it reflects current reality. **If** it does not keep one, say so plainly and
continue. Do not invent a storage format, path, or filename for the resume point, and do
not fail when there is none.

## Step 3 — Verify live state (per charter)

**Showrunner** — confirm from durable artifacts and the session ledger:

- live build lanes and their states;
- outstanding PR vets;
- open owner decisions.

**Workhorse** — confirm from the issue, PR, and session ledger:

- the issue being built;
- the current work order;
- the build worktree and branch;
- which receipts are earned versus owed.

## Step 4 — Emit the ready-to-paste `/compact` command

Build `/compact` followed by summarization instructions with **five parts, in order**:

1. **Identity** — which charter this session is (Showrunner advisor or Workhorse builder).
2. **Resume-point pointer** — where the resume point lives (the pointer, not its contents).
3. **Live-state one-liner** — the current truth in one sentence.
4. **Open owner decisions** — unresolved owner choices (or state plainly when none).
5. **Drop-list** — verbatim tool output, file diffs, probe transcripts, and command stdout
   (recoverable from GitHub or the ledger; must not consume summary budget).

Present the finished line in a fenced code block clearly marked as the thing to copy.

### Worked examples (filled-in lines a session would really emit)

**Showrunner:**

```text
/compact Preserve this as a Showrunner (advisor) charter session for the superheroes repo. Resume pointer: top-of-ledger block under "## Resume point". Live: #911 compaction wave — WO4 checkpoint skill in flight on wh911-wo4; PR #908 vet queued; release-please PR open. Open owner decisions: whether #911 cuts 0.25.0 or queues behind 0.24.1. Drop verbatim tool receipts, file diffs, probe transcripts, and command stdout — recoverable from GitHub and the ledger.
```

**Workhorse:**

```text
/compact Preserve this as a Workhorse (builder) charter session. Resume pointer: first fenced block at the top of this session's ledger. Live: building issue #911 — WO4 checkpoint skill on branch wh911-wo4 in worktree /private/tmp/sh911-wo4; parallel orders own hooks and session_context. Receipts earned: charter_detect green on base; owed: validate_skills, validate_hosts, validate_marketplace, pytest for this WO. Open owner decisions: none in this build (advisor-routed full lane). Drop verbatim tool receipts, file diffs, probe transcripts, and command stdout — recoverable from GitHub and the ledger.
```

## What happens after you paste

Compaction runs on the host. On the next SessionStart with `source: compact`, the
SessionStart recovery hook re-injects a pointer to re-read the charter skill from disk —
that was step 5 of the old five-step dance and this feature removes it. You still paste
`/compact` once; nothing in this skill triggers compaction programmatically.

## Common mistakes

| Mistake | Fix |
| --- | --- |
| Emitting `/compact` for a non-charter session | Step 1 must return `showrunner` or `workhorse`; otherwise refuse with no partial output. |
| Inventing a resume-point path or format | Only freshen a resume point the session already keeps; if none, say so and continue. |
| Pasting charter prose into the `/compact` line | The line carries pointers and live state; the charter reloads from disk after compaction. |
| Claiming checkpoint compacts by itself | Emit the line; the owner pastes `/compact` once — that is the floor. |
