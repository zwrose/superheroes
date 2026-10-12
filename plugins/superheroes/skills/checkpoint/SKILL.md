---
name: checkpoint
description: "Use before compaction in a showrunner, workhorse, or detective charter session, a discovery session, or any session with no charter — freshen live state and emit a ready-to-paste `/compact` command, and save the checkpoint notes. `/compact` is not reachable from a skill; one paste is the floor on hosts without mods. Not configure, review, or discovery work itself."
user-invocable: true
---

This skill speaks in host-neutral actions. Resolve them to your runtime's tools by reading the host tool map at `${CLAUDE_PLUGIN_ROOT}/hosts/<your-host>-tools.md` (the leading variable is this plugin's root directory) — `claude-tools.md` on Claude Code, `codex-tools.md` on Codex.

# checkpoint

Prepare **any session** for context compaction: a Showrunner advisor, a Workhorse builder,
a Detective diagnostician, a Discovery interview, or a **generic** session with no charter at
all. This skill does **not** compact by itself — `/compact` is not reachable from a skill.
It does two things: it saves **checkpoint notes** (the live state a summary would otherwise
lose) and it prints the **ready-to-paste `/compact` line**.

- **Where the superheroes mod is present** (Claude Code with mods), the mod saves the notes
  from this reply and applies the session's directive plus those notes on **every**
  compaction, manual or automatic — no paste needed.
- **Where it is not**, the floor is: **run checkpoint, paste the emitted command once.** The
  PreCompact hook still prints the session's directive (charter or generic) plus the
  checkpoint notes, unless the mod already delivered, and after compaction the SessionStart
  recovery hook re-injects a pointer to re-read the charter skill from disk, so the owner
  does **not** need to re-invoke `/superheroes:showrunner`, `/superheroes:workhorse`, or
  `/superheroes:detective` by hand.

## Invocation

| Form | Behavior |
| --- | --- |
| `/superheroes:checkpoint` | Resolve the session's mode, freshen the notes, save them (the mod, or you), print a ready-to-paste `/compact` line. Works in every session; a session with no charter is `generic`. |

## Step 1 — Resolve this session's mode

Resolve the session's **transcript path** first — the absolute path to this session's
JSONL transcript. On Claude Code, hook payloads name it in the common field
`transcript_path` (see the host hooks reference); if this session pinned that path earlier,
use the pin — never re-discover by newest file (`rubric/launch-doctrine.md` § Pin the
transcript). Resolving a session transcript path is a Claude-host mechanical floor; on a
host that does not name one, this step has no equivalent and the mode is `generic`.

Then ask the plugin lib for the mode:

```bash
python3 -B "${CLAUDE_PLUGIN_ROOT}/lib/compaction_directive.py" mode --transcript "<absolute path to this session's transcript>"
```

It prints one JSON object: `{"ok": true, "mode": "<mode>"}` with `<mode>` one of
`showrunner`, `workhorse`, `detective`, `discovery`, or `generic` (no charter detected).
**Never refuse:** if the command fails or prints `"ok": false`, continue as `generic` and
say so in one line.

## Step 2 — Find the notes file

The checkpoint notes live in one file per session. The session bootstrap's
`Checkpoint file` line names it — use that path. If the bootstrap carries no such line, ask
the lib for it, with the session id: the transcript file's name without its extension on
Claude Code, or the host's own session id where it names one (a host with a transcript path
or session id has no other source here — never guess one):

```bash
python3 -B "${CLAUDE_PLUGIN_ROOT}/lib/compaction_directive.py" path --session-id "<session id>"
```

It prints `{"ok": true, "path": "<notes file>", "markerPath": "<delivered marker>"}`. Read the
notes file if it exists — it is what the last checkpoint saved. Do not invent a path or
filename.

**No resolvable notes path** (no bootstrap `Checkpoint file` line and no session id — a host
without a transcript path or a SessionStart bootstrap): say so in one line, skip the save in
step 4, and still end the reply with the checkpoint block and the `/compact` line so the
notes live in the conversation itself; they are not persisted for automatic compaction.

## Step 3 — Freshen the live state (per mode)

Confirm each item from durable artifacts and the session ledger, not from memory.

**Showrunner** — confirm:

- live build lanes and their states;
- outstanding PR vets;
- open owner decisions.

Then **freshen the resume point** at the top of this session's ledger — it is where
`skills/showrunner-handoff/SKILL.md` and `skills/showrunner-resume/SKILL.md` read the
advisor's state, and the notes file of step 2 is not a substitute for it. **If** the
session keeps one, bring it up to date and confirm it reflects current reality (the items
above); **if** it keeps none, say so in one line and continue — invent no format, path, or
filename. This is in addition to the per-session notes file, which the compaction
instructions still use.

**Workhorse** — confirm:

- the issue being built;
- the PR and its build record;
- the current work order;
- the build worktree and branch;
- which receipts are earned versus owed.

**Detective** — confirm:

- the incident and its issue;
- the hypotheses ruled out and what ruled each;
- the demonstration state and which disposable copy holds it;
- the named budget and how much is spent.

**Discovery** — confirm:

- the work item's slug;
- the spec draft's path;
- the requirements the owner has agreed;
- the open questions;
- the approval state (framing approved? spec approved?).

**Generic** — write down, from the conversation:

- this session's role and responsibilities;
- the task and where it stands;
- the decisions made so far;
- what is waiting on the owner.

## Step 4 — Write the notes and the compaction instructions as one block

First read the block's info string from its one definition, the `CHECKPOINT_INFO` constant in
`hooks/mod/checkpoint-block.ts` (the one parser), and use the value it prints — `<CHECKPOINT_INFO>` below:

```bash
sed -n "s/^export const CHECKPOINT_INFO = '\(.*\)'.*/\1/p" "${CLAUDE_PLUGIN_ROOT}/hooks/mod/checkpoint-block.ts"
```

End the reply with **one** fenced block whose info string is exactly `<CHECKPOINT_INFO>`.
Its body is the freshened notes (step 3) followed by the compaction instructions (the five
parts of step 5, as prose). Rules:

- it is the **last thing in the reply** — nothing after the closing fence;
- **no other fence inside it** (no code blocks, no nested fences) — plain text and lists only;
- it is the only `<CHECKPOINT_INFO>` block in the reply.

Then check how the notes get saved. The mod sets a presence variable to the id of the session it
runs in; its name is defined by the `$.env.set` call in `hooks/mod/register.ts`. Read the name
(`<MOD_VAR>` below), then print that variable's value:

```bash
sed -n "s/.*\$\.env\.set('\([^']*\)'.*/\1/p" "${CLAUDE_PLUGIN_ROOT}/hooks/mod/register.ts"
printenv <MOD_VAR>
```

- **Prints this session's id** (the one in the step 2 notes file name): the mod saves the block to the notes
  file when the reply ends. Do **not** write the file yourself.
- **Anything else** (nothing, or a different id inherited from another session): no mod in this
  session. Write the **same block body** (without the
  fences) to the notes file from step 2 with the host's file-write action, creating its
  directory if needed (skip this when step 2 found no notes path).

An example of the block, shown inside a longer fence so it stays inert here:

````text
```<CHECKPOINT_INFO>
## Checkpoint notes
Mode: workhorse
Issue #911, PR #918; build record: the PR body's "Build record" section.
Work order WO4 in flight on branch wh911-wo4, worktree /private/tmp/sh911-wo4.
Receipts earned: charter_detect green. Owed: validate_skills, validate_hosts, pytest.
Waiting on the owner: nothing.

## Compaction instructions
Preserve this as a Workhorse (builder) charter session. Resume pointer: this notes file. Live: building issue #911, WO4. Open owner decisions: none. Drop verbatim tool receipts, file diffs, probe transcripts, and command stdout.
```
````

## Step 5 — Print the ready-to-paste `/compact` line

Print this **before** the step 4 block, so the block stays last. Build `/compact` followed
by summarization instructions with **five parts, in order**:

1. **Identity** — which mode this session is (Showrunner advisor, Workhorse builder,
   Detective diagnostician, Discovery interviewer, or the generic role in one phrase).
2. **Resume-point pointer** — where the notes live (the notes file path; the pointer, not
   its contents).
3. **Live-state one-liner** — the current truth in one sentence.
4. **Open owner decisions** — unresolved owner choices (or state plainly when none).
5. **Drop-list** — verbatim tool output, file diffs, probe transcripts, and command stdout
   (recoverable from GitHub or the ledger; must not consume summary budget).

Present the finished line in a fenced code block (info string `text`) clearly marked as the
thing to copy. Say that where the mod is present it also applies this directive
automatically on every compaction, so pasting is only needed on hosts without mods.

### Worked examples (filled-in lines a session would really emit)

**Showrunner:**

```text
/compact Preserve this as a Showrunner (advisor) charter session for the superheroes repo. Resume pointer: the checkpoint notes file named in the session bootstrap. Live: #911 compaction wave — WO4 checkpoint skill in flight on wh911-wo4; PR #908 vet queued; release-please PR open. Open owner decisions: whether #911 cuts 0.25.0 or queues behind 0.24.1. Drop verbatim tool receipts, file diffs, probe transcripts, and command stdout — recoverable from GitHub and the ledger.
```

**Workhorse:**

```text
/compact Preserve this as a Workhorse (builder) charter session. Resume pointer: the checkpoint notes file. Live: building issue #911 (PR #918) — WO4 checkpoint skill on branch wh911-wo4 in worktree /private/tmp/sh911-wo4; parallel orders own hooks and session_context. Receipts earned: charter_detect green on base; owed: validate_skills, validate_hosts, validate_marketplace, pytest for this WO. Open owner decisions: none in this build (advisor-routed full lane). Drop verbatim tool receipts, file diffs, probe transcripts, and command stdout — recoverable from GitHub and the ledger.
```

**Detective:**

```text
/compact Preserve this as a Detective (diagnostician) charter session. Resume pointer: the checkpoint notes file. Live: incident #931 — checkpoint skill omits detective charter; ruled out stale transcript path (grep shows correct command); disposable copy at /tmp/sh931-probe holds A/B toggle. Budget: one advisor dispatch, ~40% spent. Open owner decisions: whether detective checkpoint ships in 0.25.0. Drop verbatim tool receipts, file diffs, probe transcripts, and command stdout — recoverable from GitHub and the ledger.
```

**Discovery:**

```text
/compact Preserve this as a Discovery (requirements interview) session. Resume pointer: the checkpoint notes file. Live: slug quiet-hours, spec draft at the work item's spec file; framing approved, three requirements agreed, two open questions on weekend handling. Open owner decisions: whether weekends are in scope; spec approval not yet asked. Drop verbatim tool receipts, file diffs, probe transcripts, and command stdout — recoverable from GitHub and the ledger.
```

**Generic:**

```text
/compact Preserve this as a code-review helper session for the owner. Resume pointer: the checkpoint notes file. Live: reviewing the retry change in the payments client; two findings written up, third pending. Open owner decisions: whether to block the merge on the missing timeout test. Drop verbatim tool receipts, file diffs, probe transcripts, and command stdout — recoverable from GitHub and the ledger.
```

## What happens after

Where the mod is present, the next compaction (manual or automatic) is steered by the
session's directive plus the notes file this skill saved; the owner pastes nothing. On a
host without mods, compaction runs when the owner pastes the `/compact` line; the PreCompact
hook prints the session's directive (charter or generic) plus the checkpoint notes, unless
the mod already delivered, and on the next SessionStart with `source: compact` the
recovery hook re-injects a pointer to re-read the charter skill from disk. Nothing in this
skill triggers compaction programmatically.

## Common mistakes

| Mistake | Fix |
| --- | --- |
| Refusing because the session has no charter | Step 1 returns `generic` for a session with no charter; checkpoint covers every session. |
| Writing the notes file when `<MOD_VAR>` holds this session's id | The mod saves the block from the reply; writing it too races the mod. Write the file whenever the variable is unset or holds another id. |
| Putting anything after the `<CHECKPOINT_INFO>` block, or a second fence inside it | The block must be the last thing in the reply with no inner fence; otherwise the notes are not saved. |
| Using another info string, or fewer than three backticks | The fence's info string is exactly the value read from `CHECKPOINT_INFO` in step 4. |
| Skipping the ledger resume point in a Showrunner session because the notes file was saved | The incoming advisor reads the ledger resume point, not the notes file; freshen both (step 3). |
| Inventing a notes path or filename | Use the bootstrap's `Checkpoint file` line, else the lib's `path` verb. |
| Pasting charter prose into the `/compact` line | The line carries pointers and live state; the charter reloads from disk after compaction. |
| Claiming checkpoint compacts by itself | It saves notes and prints the line; the mod steers compaction, or the owner pastes `/compact` once — that is the floor. |
