---
name: showrunner-resume
description: "First action in a new, restarted, or compacted showrunner advisor seat — no arguments; with or without handoff. Reads durable state only, pins this seat's config on launches, classifies each lane from one decision table, records outcomes, arms watches. Not checkpoint or handoff."
user-invocable: true
---

This skill speaks in host-neutral actions. Resolve them to your runtime's tools by reading the host tool map at `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/hosts/<your-host>-tools.md` (the leading variable is this plugin's root directory) — `claude-tools.md` on Claude Code, `codex-tools.md` on Codex.

# showrunner-resume — pick the advisor seat back up

Run this as the **first action** of any new, restarted, or compacted showrunner advisor seat. It takes **no arguments**. It works **with or without a deliberate handoff** — seat death is the common case, and that is why this is the primary command of the pair.

It reads durable state and **never asks the owner to paste anything**.

## Invocation

| Form | Behavior |
| --- | --- |
| `/superheroes:showrunner-resume` | Load the showrunner charter, pin this seat's configuration directory on every launch, read durable state, classify each lane, record terminal outcomes where needed, arm batch watches, and report in three lines. |

## Step 1 — load the charter

Load the showrunner charter itself (`skills/showrunner/SKILL.md` under this plugin's root) so this seat is the advisor before it acts as one.

## Step 2 — pin the instance you are running in

Every launcher, watch, and canary call this seat makes carries **this** session's own configuration directory, never the previous seat's.

1. **The rule:** each launch pins the calling seat's own `CLAUDE_CONFIG_DIR` (or the host's equivalent configuration root) on the child it spawns and on the ledger record.
2. **The backstop:** the launcher refuses a launch whose pinned configuration directory is not the calling seat's own, naming both directories in the refusal. Read `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/lib/launcher.py` for the refusal tokens (`launch-foreign-instance-pin`, `launch-seat-instance-undetermined`, `premise-stack-fields-incomplete`, `premise-stack-field-invalid`, `base-not-layer-head`, `stack-read-unavailable`) and the deliberate-override flag (`--allow-foreign-instance`). Do not re-implement the check in this skill.
3. **The override rule:** pass `--allow-foreign-instance` **only on the owner's instruction, naming the instance — never on the advisor's own judgment.**

On a host that does not expose the calling session's own process identity, the launcher cannot make that comparison and does not run the pin gate — on such a host the rule is the advisor's alone.

## Step 3 — read durable state, and only these sources

Read **no other source when choosing a row**, and in particular read **no handed-over text as fact**:

1. the resume point at the top of this session's ledger, if one exists;
2. the launch ledger — the live launches, and a batch's tallies;
3. the builder-liveness heartbeat sweep;
4. each lane's recorded leader process, probed for liveness;
5. each lane's issue and pull request: any **park record** on either, with its stated blocker and any owner or advisor ruling to resume; whether the pull request exists, whether it is still a draft, whether a durable review receipt stands on it (the receipt `skills/workhorse/SKILL.md` § 10. Review before handback requires — that section is the term's one definition, and every later use here means that receipt), the **remote** head commit, and the continuous integration conclusion for **that exact commit**, selected by workflow name **plus** head commit — never by "the newest run";
6. each lane's own session transcript — the one named by the **session identifier recorded on that lane's own launch record**, looked up under **the configuration root that launch record itself recorded** — never the seat's own root, and never "the newest transcript"; exactly one file may match. Whether the transcript resolved is evidence for the decision table's row 2; the table decides. The reader **stats the file only** and never reads its contents.

When row 4 is the candidate for a lane, also read that lane's dead worktrees, local branches, and pushed tip — **only** as the unpushed-work sweep `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/rubric/launch-doctrine.md` § Sweep for unpushed work before adopting defines. Do not re-describe that sweep here.

Shell forms for 1–4:

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
REPO_ROOT="<absolute path to the project repository>"
```

Read the resume point from this session's ledger when one exists at the top — the same pointer checkpoint names, not its contents copied here.

```bash
python3 -B "$ROOT_DIR/lib/launcher.py" count --repo-root "$REPO_ROOT" --batch "$BATCH_ID"
```

```bash
python3 -B "$ROOT_DIR/lib/heartbeat.py" sweep --repo-root "$REPO_ROOT"
```

Probe each lane's recorded leader pid from the ledger's `started` record — a double-confirmed process check, never a global process match. Detail: `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/rubric/launch-doctrine.md` § Recovery.

For 5, read each lane's issue and pull request through the host-neutral actions your forge exposes — park records, existence, draft state, durable review receipt, remote head sha, and the integration run for that workflow name on that sha. Do not pin a particular forge's command syntax here.

## Step 4 — choose per lane from the decision table

Read rows **top to bottom**; the **first row whose required evidence holds** decides the lane. **A read that failed, was ambiguous, or was not made satisfies no row's requirement** — a failed read can only push a lane down the table, never select a row that needed that read. The "evidence required" column is **required**, not indicative.

| Row | Evidence required | Action |
| --- | --- | --- |
| **1. parked** | A park record on the lane's issue or pull request (read completed) whose stated blocker is **not** cleared, and no owner or advisor ruling to resume it. This row needs no process, heartbeat, or transcript read — which is why a park record outranks a failed transcript read. | Report the lane as parked, awaiting a decision; nothing is relaunched, armed, or recorded. |
| **2. re-arm** | **All** of: the recorded leader process is **positively live** (the double-confirmed probe in Step 3); the lane's heartbeat classifies **`fresh`** in the heartbeat sweep — the sweep's `fresh` class, the lane's age inside its own `staleAfterSeconds` promise, as CONVENTIONS §15 defines it; and the lane's session transcript **resolved** (Step 3, source 6: exactly one file found by the identity rule, not dated into the future). **A transcript alone never re-arms.** | Nothing is relaunched and no outcome recorded; the lane's batch is a candidate for Step 6 arming. |
| **3. vet** | **All** of: the pull request exists, is **not** a draft, carries a durable review receipt, its **remote** head is the commit that receipt names, and CI concluded success on that exact commit (selected by workflow name plus head commit). | If the ledger carries no terminal outcome, record `handback` first (Step 5); **never relaunched**. |
| **4. adopt** | **All** of: the recorded leader process is **positively not live** (the probe completed and found it dead); the pull-request read (Step 3, source 5) completed and found the lane's pull request **absent or a draft** — a ready (non-draft) pull request never satisfies this row; the park-record read completed and found either no park record, or a park whose stated blocker is cleared or which the owner or advisor has ruled should resume; and the unpushed-work sweep of `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/rubric/launch-doctrine.md` § Sweep for unpushed work before adopting has run for this lane and its residue is durable. | Record the lane's terminal outcome first (Step 5), then adopt by that section's procedure (cite `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/rubric/launch-doctrine.md` § Sweep for unpushed work before adopting). |
| **5. unresolved** | None — the last row, for any lane no earlier row could establish. | The lane is named in the report with the read that failed or the evidence that is missing; nothing is relaunched, armed, or recorded. |

A finished lane is never spent again as a fresh launch, and an unreadable lane is never treated as a dead one.

## Step 5 — record terminal outcomes

Applies to lanes the decision table sent to **row 3** (when the ledger lacks an outcome) and **row 4**.

Before its successor launches, record the lane's terminal outcome using the vocabulary the ledger spells exactly: **`handback`**, **`park`**, **`refusal`**, **`died`**.

In the foreground, call the outcome verb **only with a zero wait for the child to exit** (`--await-exit 0`). Any positive wait is a background task — a live child is a legitimate refusal to be re-attempted later, never something to wait out in the foreground.

```bash
python3 -B "$ROOT_DIR/lib/launcher.py" record-outcome \
  --repo-root "$REPO_ROOT" --launch-id "$LAUNCH_ID" \
  --outcome died --evidence "<one line>" --await-exit 0
```

## Step 6 — arm one watch loop per live batch, after checking none is already running for it

Arming applies to batches holding a **row-2** lane.

**The check comes first.** Its authoritative form is a **read-only process listing** for a wave-watch loop naming that batch. Where the host also offers an inventory of this session's own background tasks, read that too. **Nothing is ever killed on either reading.**

The check is **fail-closed:** a hit, an ambiguous reading, an unavailable listing, or a failed one all mean **do not arm this batch**; name it in the report instead. Arming happens only on a listing that completed and found nothing.

<!-- WORKAROUND: duplicate-loop check via process listing before background arming
     delete-when: a durable batch watcher makes the duplicate-loop check and this arming shape unnecessary -->

**Arming is a background task, always.** Cite `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/skills/showrunner/reference/wave-watch.md` for the arming pattern and its flags rather than restating them.

This skill does **not** take that reference's suggestion of a one-off foreground spot check before arming. The one-off watch verb polls until something actionable happens or its window expires; against a quiet live lane it blocks for the whole window. That is why it is not used here.

**Residual:** the check and the arm are two steps, so two advisor seats resuming the same project at the same moment could both find nothing and both arm. This skill rests on there being one advisor seat per project; do not imply the check is atomic.

## Step 7 — report in three lines

Exactly three lines:

1. **Seat and reads** — which seat this is, which configuration directory it pinned, and what durable sources it read.
2. **Lanes by branch** — counts and lane identifiers grouped by parked, re-arm, vet, adopt, and unresolved.
3. **Watches and owner items** — watches armed, batches not armed and why, and anything owed to the owner.

### Worked example (row 3 vet and row 2 re-arm)

```text
Seat: showrunner advisor, instance ~/.claude. Read resume point, ledger batch wave-a, heartbeat sweep, process probes, PR #220 and #221 CI by workflow+sha, session transcripts (stat only).
Lanes: vet 1 (#220 — PR exists, non-draft, durable review receipt, remote head = receipt commit, CI success on that sha by workflow name); re-arm 1 (#221 — leader positively live, heartbeat sweep class fresh, transcript resolved one file stat only); adopt 0; parked 0; unresolved 0.
Watches: armed loop for wave-a. None skipped. Owner: none.
```

### Worked example (row 5 unresolved, row 2 re-arm, batch not armed)

```text
Seat: showrunner advisor, instance ~/.claude-two. Read ledger batch wave-b; heartbeat sweep; process probes, session transcripts (stat only); PR #305 head read failed.
Lanes: vet 0; re-arm 1 (#306 — leader positively live, heartbeat sweep class fresh, transcript resolved one file stat only); adopt 0; parked 0; unresolved 1 (#305 — row 5: remote head read failed).
Watches: wave-b not armed — process listing ambiguous (two wave_watch.py matches). Owner: re-run resume after clearing duplicate watcher or name which batch is canonical.
```

### Worked example (row 1 parked despite unresolvable transcript)

```text
Seat: showrunner advisor, instance ~/.claude. Read ledger batch wave-c, park record on #330 issue, session transcript lookup for #330 failed (no file).
Lanes: vet 0; re-arm 0; adopt 0; parked 1 (#330 — row 1: park record read completed, blocker not cleared, no advisor ruling to resume); unresolved 0.
Watches: wave-c not armed — no row-2 lane in the batch. Owner: decision on #330 park blocker.
```

### Worked example (row 4 adopt after the unpushed-work sweep)

```text
Seat: showrunner advisor, instance ~/.claude. Read resume point, ledger batch wave-d, heartbeat sweep, process probes, PR #340 (draft), park-record read (none), unpushed-work sweep per launch-doctrine § Sweep for unpushed work before adopting.
Lanes: vet 0; re-arm 0; adopt 1 (#340 — row 4: leader positively not live, pull-request read completed, PR a draft, park-record read completed no park record, unpushed-work sweep ran and residue durable — one unpushed commit pushed to branch wh/340-fix at abc1234; terminal outcome died recorded before adoption); parked 0; unresolved 0.
Watches: wave-d not armed — no row-2 lane in the batch. Owner: none.
```

### Worked example (row 5 for a lane that handed back before the seat died)

```text
Seat: showrunner advisor, instance ~/.claude. Read resume point, ledger batch wave-e, heartbeat sweep, process probes, PR #350 (read completed: ready, non-draft), durable review receipt on #350 (not establishable), CI by workflow+sha.
Lanes: vet 0; re-arm 0; adopt 0; parked 0; unresolved 1 (#350 — row 5: leader positively not live, PR ready (non-draft), durable review receipt not establishable — not relaunched).
Watches: wave-e not armed — no row-2 lane in the batch. Owner: #350 is ready but its durable review receipt could not be established.
```

## No foreground step waits on a live lane

A seat that blocks in the foreground is a seat the owner cannot reach.

Three instances: the one-off watch verb is not used at all; the terminal-outcome verb runs in the foreground only with a zero wait; arming is a background task only.

## Failure modes

| Failure | Outcome |
| --- | --- |
| The ledger is missing or unreadable | Preserve every lane as unresolved. Stop the transition. |
| The ledger fold fails (a live-launch read that cannot fold returns an empty list) | Never read an empty list as "no live lanes." Preserve as unresolved. Stop. |
| A per-lane read fails or is ambiguous (heartbeat not-ok/unknown class, uncertain process probe, pull-request/receipt/head/CI read failure, no session identifier on the launch record, session transcript unresolvable, the unpushed-work sweep for a row-4 candidate cannot be completed) | That read satisfies no row; the decision table decides (Step 4). |
| The process listing for the duplicate check fails or is ambiguous | Do not arm that batch. Name it in the report. |
| The outcome verb or the amendment verb refuses | Stop the transition for that lane and name it in the report. |
| Arming fails | Name the batch in the report. Do not claim the watch is running. |
| The instance pin cannot be determined on this host | The pin rule is yours alone; if you cannot determine the instance, name that in line 1 and do not launch until you can. |

## Common mistakes

| Mistake | Fix |
| --- | --- |
| Skipping this on a restarted or compacted seat | This is the first action — run it before dispatching or vetting. |
| Treating handed-over chat text as fact | Read only the sources Step 3 names. |
| Relaunching a lane whose PR already vets | → the decision table decides; row 3 is never relaunched. |
| Treating a missing heartbeat as a dead builder | → a missing read satisfies no row; see Step 4. |
| Using the newest CI run instead of workflow+sha | Select the run for the remote head commit the receipt names. |
| Killing a duplicate watcher before arming | The duplicate check is read-only; never kill on either reading. |
| Running a foreground one-off watch before arming | Cite wave-watch for arming only; the spot check blocks on quiet lanes. |
| Passing `--allow-foreign-instance` on your own judgment | Only on the owner's instruction, naming the instance. |
| Waiting in the foreground for a live child to exit | Use `--await-exit 0` in the foreground; positive waits are background tasks. |
