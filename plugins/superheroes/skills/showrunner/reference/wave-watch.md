# Contents

- [What it is](#what-it-is)
- [The arming pattern](#the-arming-pattern)
- [The single-loop rule](#the-single-loop-rule)
- [What ends a loop and what it passes over](#what-ends-a-loop-and-what-it-passes-over)
- [One-off check (`run`)](#one-off-check-run)
- [`--ignore-launch` and re-arming](#--ignore-launch-and-re-arming)
- [`--ignore-event` and re-arming](#--ignore-event-and-re-arming)
- [Before treating `lane-stale` as a wedge](#before-treating-lane-stale-as-a-wedge)
- [The quiet window, and the number behind it](#the-quiet-window)
- [Timing flags](#timing-flags)
- [What it tells you](#what-it-tells-you)
- [Answering a builder note](#answering-a-builder-note)
- [The boundary the owner accepted](#the-boundary-the-owner-accepted)
- [How it relates to the heartbeat sweep](#how-it-relates-to-the-heartbeat-sweep)

# Wave watch

## What it is

`lib/wave_watch.py` is a ledger-driven watcher over one launch batch. It has three verbs:

- **`loop`** — the arming shape. Re-arms an internal arm (`watch_arm`) and exits on any successful
  event **not** in **`BENIGN_EVENTS`** in `lib/wave_watch.py` (every lane-ending token and any
  unknown token alike), on a refusal, or at `--max-total-seconds`. Each benign non-timer event is
  passed over, written as a `--log` line in the same `{"arm", "elapsedSeconds", "result"}` shape as
  timer arms, and recorded in the loop result. When it exits it prints one JSON line on stdout and
  exits. Arm as **one harness background task per batch** at wave launch.
- **`run`** — a true one-shot. One ledger read (and at most one open-PR read, for stack state), no
  waiting, then prints one JSON line on stdout and exits. It does **not** re-arm.
- **`note-answered`** — not a watch: `--repo-root` and `--comment-id N` record a builder note's
  **or a cloud terminal comment's** comment as answered, so `builder-note` or a cloud `lane-terminal` stops surfacing it. It prints one JSON line on stdout and
  exits 1 on a refusal: `comment-id-invalid`, `note-answers-unreadable` (the record is never
  overwritten), or `store-unresolvable`.

**The re-arm lives inside `loop`** — there is no daemon, so there is nothing to orphan. It replaces
hand-rolled per-session watch loops that kept failing quietly: a double-backgrounded loop that
orphaned, a hand-typed PID list that went stale the moment an unpark launched a new builder, a
ten-hour dead-watcher hole — and each failure looked like a calm wave.

## The arming pattern

<!-- WORKAROUND: harness background-task arming pattern with manual re-arm after each lane-ending event
     delete-when: a re-run of the background-session trial observes its "wave-watch arming and
     re-arm" condition met; the condition is restated in the keep-or-retire record's marker
     inventory -->

Assign the plugin root once, then arm one harness **background task per batch**:

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"
python3 -B "$ROOT_DIR/lib/wave_watch.py" loop \
  --repo-root "$REPO_ROOT" --batch "$BATCH_ID" \
  --max-seconds 2400 --interval-seconds 60 \
  --ignore-launch "$ALREADY_HANDLED_LAUNCH_ID"  # re-arm only — omit on first arm
```

`$REPO_ROOT` and `$BATCH_ID` are session variables you supply. On a **first arm**, omit
`--ignore-launch` — there are no handled lanes yet. On **re-arm** after you act on an event, repeat
`--ignore-launch` for each launch id already handled on that arm, and add `--ignore-event` pairs for
any benign events you want suppressed (see below).

**Before arming**, run a one-off foreground `run` with the same `--repo-root` and `--batch`. It
returns at once and reports what is due right now, but it cannot tell a mistyped batch id from a quiet
batch (both return `timer`); confirm the batch id from the launch record.

**`loop` is the wave's sole watcher — do not arm a second pid-death watcher beside it.** The one gap
a second watcher used to cover: `lane-terminal` fires from the ledger the moment a builder hands
back, typically a minute or two *before* its session exits, and `record-outcome` refuses while that
child is still alive (`terminal-child-live:<pid>`). Close it on the `lane-terminal` wake with
`launcher record-outcome --await-exit <seconds>`, which re-attempts until the child is gone and at
the ceiling returns that same refusal, so nothing falls open. The ceiling is a **sleep budget spent
from the first live-child refusal onward**, not a whole-call wall-clock bound: each attempt also runs
a liveness probe that settles for a couple of seconds, so a call costs the ceiling plus one probe per
attempt. Pick the number for how long you are willing to wait, not for when you need to be back.
The accepted range is **0..1800 seconds** (30 minutes — sized from the field: builders outlive their
handback by 10–18 minutes); outside it the verb refuses (`await-exit-invalid:<value>`) before
attempting anything. **Foreground callers stay at or under 540 seconds** — a harness with a 10-minute
tool-call cap kills anything longer mid-wait; a longer patience is a **background** call, which is
the shape that makes the verb itself the wait (no second watcher). A builder that outlives even that
is the loop's `builder-exited` event's to report — re-invoke the verb then.

The arming snippet above omits two flags you should **include on every arm**: `--max-total-seconds`
(the loop stops re-arming and emits the last `timer`, so prolonged silence eventually becomes a
message) and `--log PATH` (each timer arm and each passed-over benign event is recorded, so you can
see the loop is alive and which batch it is watching). Without them, a mistyped or quiet batch under
`loop` produces **no stdout at all** until something lane-ending happens or a builder note arrives — indistinguishable from a
healthy quiet wave for as long as you leave it running.

In an **interactive** session, a harness background task survives across turns and re-invokes the
advisor when it exits — that is what keeps you from going blind between turns while `loop` runs.
In a **headless** session (`claude -p`), the session exits when its turn ends, so a background task
dies with the turn; do not arm `loop` there unless you have a continuation mechanism outside this
tool. In the Desktop app's Code tab, a background Bash task is killed at about 10 minutes (observed
on Claude Code CLI 2.1.284), so there arm the watch under a `Monitor` instead, with
`--max-total-seconds 1680` to stay inside its 30-minute cap (same CLI version), and re-arm at each
end.

Bash timeout on Claude Code has two layers (`hooks/bash_timeout.py`,
`skills/workhorse/reference/dispatch-mechanics.md`): an **omitted** timeout is rewritten to 600000 ms
(600 s), so a foreground call with no explicit timeout is killed at ~600 s; an **explicit** timeout
above ~600 s converts the call to background. For the arming pattern, use the harness background-task
primitive so `loop` survives across turns — do not rely on a foreground arm outliving the turn.

## The single-loop rule

At start, before its first arm, `loop` takes an exclusive kernel lock on a per-batch lock file under
the launch ledger's per-repository store directory (`wave-watch-locks/`). If another live `loop`
holds it, the new one refuses **`loop-already-live`** (exit 1, `arms: 0`) and names the live loop in
**`liveLoop`** — `{"pid", "startedAt", "batch", "log"}`, or `null` when the holder's record could not
be read. The kernel drops the lock when its holder process dies, so a dead loop never blocks a new
one and there is no stale lock to clear. If exclusivity cannot be established at all (the store
refuses, the lock file cannot be made or opened or is not a regular file, the lock call fails for
another reason) it refuses **`loop-lock-unavailable`** (exit 1, `arms: 0`) with a `detail` naming the
cause — it never arms without knowing it is alone.

## What ends a loop and what it passes over

The authoritative closed sets **`LANE_ENDING_EVENTS`**, **`BENIGN_EVENTS`** and
**`ATTENTION_EVENTS`** live in `lib/wave_watch.py` (they partition **`EVENTS`**). Read the member
tokens there — do not re-copy them into this reference.

- **`LANE_ENDING_EVENTS`** — membership ends the `loop` invocation (after printing one JSON line).
- **`ATTENTION_EVENTS`** — membership also ends the `loop`, but ends no lane: a builder is waiting
  on you, or the builders' account cannot run anything. Not suppressible, except `account-limited`, per lane.
- **`BENIGN_EVENTS`** — membership never ends the loop. Each benign **non-timer** event is passed
  over: the loop re-arms, appends a `--log` line in the same `{"arm", "elapsedSeconds", "result"}`
  shape as a timer arm (the `result` carries that event), and accumulates **`passedOver`** /
  **`passedOverCount`** on the final line (see below). A `timer` ends only an internal arm, not the
  whole `loop`, unless `--max-total-seconds` has been reached.

A successful arm whose `event` is **not** in **`BENIGN_EVENTS`** ends the loop — see
`_loop_exits_on()` in `lib/wave_watch.py`. That covers every lane-ending token and any unknown token
alike.

A successful `stack-state-changed` result that carries the idle-seat launchable-child flag ends the
loop on that arm.

Every `loop` result carries **`passedOver`** — one entry per benign non-timer event passed over in
that invocation, each `{"arm", "elapsedSeconds", "event", …that event's payload keys}`, keeping the
most recent **`PASSED_OVER_CAP`** entries — and **`passedOverCount`**, the total passed over (it can
exceed the list's length). Both are empty or zero when nothing was passed over. `run` results never
carry them. Within one `loop`, each distinct PR-set change is reported once (the PR baseline advances when
it fires), and a stack-state change is reported once per change.

At `--max-total-seconds`, `loop` returns a `timer` result carrying the report, even when its last arm
ended on a benign event.

## One-off check (`run`)

Use `run` for a **single foreground check** — "what is due right now?" — not for wave arming:

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"
python3 -B "$ROOT_DIR/lib/wave_watch.py" run \
  --repo-root "$REPO_ROOT" --batch "$BATCH_ID"
```

`run` is a true one-shot: one ledger read and at most one open-PR read for stack state, no waiting,
then exit. Flags: `--repo-root`, `--batch`, `--ignore-launch`, `--ignore-event`. It does **not** take
`--max-seconds`, `--interval-seconds`, `--max-total-seconds`, or `--log` — passing `--max-seconds` or
`--interval-seconds` is a usage error. Its reads of GitHub are bounded by a fixed read budget,
`RUN_READ_BUDGET_SECONDS` in `lib/wave_watch.py`. It returns the first event due right now, or `timer` when nothing is
due. It cannot report `pr-set-changed` (a one-shot has no PR baseline to compare against), and it
never reports the window-only degradations `lane-never-stamped` or `pr-signal-never-sampled`.

## `--ignore-launch` and re-arming

`--ignore-launch` is repeatable, and it excludes a launch id from lane enumeration. Without it, a
lane you have already handled but cannot terminalize re-fires on every arm and the loop spins on the
same event.

## `--ignore-event` and re-arming

`--ignore-event LAUNCHID:EVENT` is **event-class-scoped** suppression — the answer when
`--ignore-launch` is too blunt: silencing a lane's benign noise with `--ignore-launch` also loses
that lane's terminal signal.

A suppressed `(launchId, event)` pair is **never actionable**, while **every other event for that
lane still fires** and **that same event for every other lane still fires**. Suppression affects
actionability only. A suppressed lane appears under `alsoObserved` **when some other event fires on
that result** — but a `timer` result carries no `alsoObserved` at all, so a lane whose only signal is
suppressed is invisible in that arm's output. Use `--log` to keep sight of a suppressed lane across
a long arm chain. Only the lane-keyed events in `_SUPPRESSIBLE_EVENTS` (`lib/wave_watch.py`) are
suppressible; naming any other event is a refusal (`ignore-event-invalid`).
A malformed pair is a refusal (`ignore-event-invalid`), never a silent drop.

**One answered note, by id.** `--ignore-event LAUNCHID:builder-note:COMMENTID` (COMMENTID a positive
decimal integer) suppresses that one note, on that lane, for that invocation; every other note still
fires, other ids on the same lane and every note on other lanes. `LAUNCHID:builder-note` with no id
stays a refusal: suppressing the class would hide a later unanswered note. Recording a note answered
before its delivery receipt is in hand would silence it for good. One id, for one invocation, shown on
every result, does neither: every non-refusal result of `run`, `watch_arm` and `loop` given a note
ignore carries `ignoredNotes`, the sorted comment ids you ignored, so a note that is still unanswered
is never invisible. Without a note ignore the key is absent.

Use it after you have answered a note and while its delivery gate is still open (a `check` still to
run or re-run), so the loop can watch the rest of the batch. Drop it, so the note fires again, when
the gate reads not delivered. Run `note-answered` once the gate reads delivered.

**Pattern — the exception, not the routine:** when `loop` wakes you on an event you have **verified**
benign, re-arm with `--ignore-event <launchId>:<event>` so that exact pair stops waking you **while
that lane's other events still do**. Within a single `loop` invocation, the first unsuppressed
**lane-ending** or attention event exits the loop; persistence across invocations is **your** job — pass
`--ignore-event` on re-arm. The tool does not dedupe suppressed pairs across invocations by itself.
**Do not pre-arm `--ignore-event` for `lane-stale` as a matter of course**: an arm that ignores
every lane's stale signal has quietly reduced the watcher's exits to `lane-terminal`,
`lane-blocked`, and `builder-exited`, and the wave's wedges arrive as surprises. If you find
yourself suppressing the same event on most lanes of a wave, that is a field observation to record,
not a pattern to keep.

## Before treating `lane-stale` as a wedge

For a local lane, `lane-stale` is a **wedged builder**: a started lane whose recorded leader pid is
positively live, with no terminal heartbeat (`parked` / `handback`), whose session transcript is
colder than the quiet window **or** cannot be resolved. Only a terminal stamp (`parked` / `handback`) takes a
lane out of this check — a `blocked` lane stays in it, so `lane-blocked` wins precedence and
`lane-stale` surfaces under `alsoObserved` or fires when `lane-blocked` is ignored. That is the wedge. The one-shot `run`
verb applies the same rule, so a scheduled `run` reports a wedged lane even when no watch loop is
armed.

A [cloud lane](../../../rubric/glossary.md#cloud-lane) has no pid to probe and no transcript, so it
takes none of the checks below. The watcher reads its activity on GitHub instead: the newest of its
issue's last update, the last update of a PR that closes the issue, and the last commit on a branch
whose name carries the issue number. It makes one request per tick, no more often than
`CLOUD_ACTIVITY_POLL_SECONDS` in `lib/wave_watch.py` allows, and only
while a cloud lane is live. A cloud lane quiet past `LIVENESS_QUIET_WINDOW_SECONDS`, counted from the
later of its start and its last activity, is `lane-stale`. Its entry carries `place: "cloud"` and
`activityAgeSeconds` in place of `transcriptAgeSeconds`.

The watcher also reads the lane's progress comment from the issue comments it already reads, with no
extra request. That comment's first line is `Builder progress (cloud build).` (`PROGRESS_HEADER` in
`lib/cloud_builder.py`); the most recently edited one created at or after the lane's start is the
lane's. When there is one, it decides alone: the lane is `lane-stale` when the comment's last edit is
older than its stated expected time plus `LIVENESS_QUIET_WINDOW_SECONDS`, or dated in the future;
otherwise the lane is not stale, whatever its activity age. With no progress comment the activity
rule above decides. A tick whose comments read was made but failed decides from what it did read, and
from the activity rule when it read nothing; a tick that made no comments request at all (its time
budget spent, or no watched lane to read) reuses the last progress snapshot it read. A stale entry
decided by the comment carries `progressAgeSeconds`, `progressExpectedSeconds` and `phase` in place
of `activityAgeSeconds`. The `cloudLanes` entry carries `phase`, `progressAgeSeconds` and
`progressExpectedSeconds` when a progress comment was read.

**The first check on a quiet cloud lane is a relayed status ping**: a message to the lane's session
asking it to update its progress comment. Read the comment again. Start a helper session to read the
lane only after about 15 minutes with no answer. A session the platform shows working is not wedged. A
branch whose name omits the issue number is not read until its PR opens, so a builder on such a branch
can read quiet while it works.

For a local lane, before emitting `lane-stale`, the watcher resolves the lane's session transcript
from the **session id the launcher recorded on the launch record** and compares its mtime to
`LIVENESS_QUIET_WINDOW_SECONDS` in `lib/wave_watch.py`. Each `lane-stale` entry carries `launchId`,
`state` (heartbeat state or null), `transcriptAgeSeconds` (null when unresolved), and
`quietWindowSeconds`.

**The check fails toward the alert, never toward silence.** Every way the transcript read can fail to
prove work — no session id on the lane's ledger record, no transcript on disk, two-or-more
transcripts with the same id, an unreadable projects directory, a transcript dated into the future
by any amount — leaves the lane stale and the event fires (a missing transcript, only
after the launch grace in [The quiet window](#the-quiet-window)). Ambiguity additionally records
`transcript-ambiguous`.

**A lookup that could not complete says so.** When the watcher could not *resolve* the transcript at
all — the projects root or a bucket was unreadable, a candidate's `stat` failed for any reason other
than the file being absent, or the lane recorded a config root the watcher cannot use — the lane
alerts **and** records `transcript-unresolved`. Read it as *the watcher could not vouch either way*,
not as *the transcript is cold*: without it, an I/O failure and a genuinely wedged builder produce
the same alert with the same silence behind it. **Absence is not unresolved** — a missing projects
root, a missing bucket, or a missing transcript means the transcript is not there, which is the wedge
signal `lane-stale` exists to report, so those alert with **no** token. A pre-#1029 record carrying
no session id alerts with no token either — that is the documented no-identity class, not a failed
reading.

**Only the lane's own transcript may vouch for it.** The launch record's session id names exactly one
file: `<sessionId>.jsonl` under a config root's `projects` tree. Exactly one config root is searched,
never both — because a same-named file under any other root belongs to a different session. **The
lane's own recorded root wins:** the launcher records on the launch record the `configDir` its
builder was spawned under, and the watcher searches *that* root, so a lane launched under another
Claude instance (`.claude-two`, a per-launch exception) still resolves correctly instead of looking in
the watcher's own root. A record carrying no `configDir` — every pre-#1036 launch — resolves under
the watcher's own env root as before (`CLAUDE_CONFIG_DIR` outright when set, otherwise `~/.claude`).
A symlinked entry is never followed; and the watcher **stat's only** — it never reads transcript
contents.

A lane with no heartbeat file or an unreadable one still gets this check. Launches without a
recorded session id fail toward alert. The concurrent-foreign-session-in-the-same-worktree residual is
**closed** by recorded identity: a different session carries a different id and cannot vouch for this
lane.

## The quiet window

Liveness uses one quiet window for every lane: `LIVENESS_QUIET_WINDOW_SECONDS` in
`lib/heartbeat.py` (bound in `lib/wave_watch.py`). The field-check narrative and measured
counts live in the module comment beside that constant in `lib/heartbeat.py`. No per-lane
promise exists; a lane whose transcript file does not exist yet gets the same window measured
from its recorded start and alerts once that window passes. `builder-exited` still surfaces a
lane whose pid dies regardless of transcript age.

## Timing flags

`run` takes no timing flags.

Under `loop`, `--max-seconds` is the **per-arm** watch window (default 2400) — how long each internal
arm watches before a `timer` forces a re-arm. It is **not** how long the advisor's session is
committed.

`--interval-seconds` (default 60) is the polling interval within each arm.

`--max-total-seconds` is optional; **absent means the loop is unbounded**. It is a **re-arm bound,
not a hard kill**: the loop will not *start* a new arm once the total is reached, and may overrun
the total by the final arm's rounding plus one evaluation pass.

`--log PATH` appends one JSON line per timer arm and per passed-over benign non-timer event —
`{"arm": N, "elapsedSeconds": E, "result": {…}}` — for post-mortem review. A failing log write never
terminates the loop; it discloses `log-unwritable`. `run` does not accept `--log` or
`--max-total-seconds`.

## What it tells you

The watcher prints **one JSON line on stdout**; **exit 0 on an event, exit 1 on a refusal**.

A `loop` exits on the first unsuppressed lane-ending or attention event; a `run` returns the first due
unsuppressed event.

**Events** (`ok=True`): see `EVENTS` in `lib/wave_watch.py`. `run` never reports `pr-set-changed`, and `run` returns `timer` when nothing else is due.

**Precedence**, highest first: see `EVENT_PRECEDENCE` in `lib/wave_watch.py`.

When an event fires, co-occurring lower-precedence lane signals from the same interval ride along
under `alsoObserved` (launch ids only) — read it, or you will act on one lane and miss its
siblings. A `timer` result has no `alsoObserved`.

When **`stack-state-changed`** fires, the payload carries one entry per stack the batch's
launches name, plus a `flags` list:

- `stacks` — one object per distinct stack number stamped on any lane in the batch, sorted by
  `stack`: `stack` (the stack number), `state` (complete — `STACK_STATE_COMPLETE` — or incomplete
  — `STACK_STATE_INCOMPLETE`), `layersPlanned` (the agreed layer count when known, else `null`),
  `missingPositions` (sorted positions still incomplete — empty when the state is complete), and
  `reason` (planned count unknown — `STACK_REASON_LAYERS_PLANNED_UNKNOWN`, planned count disagreed
  — `STACK_REASON_LAYERS_PLANNED_DISAGREED`, or membership unresolved —
  `STACK_REASON_MEMBERSHIP_UNRESOLVED` when the stack could not be evaluated; otherwise `null` — a
  complete stack, or an incomplete one whose `missingPositions` name the layers not yet READY).
- `flags` — observations that ride with the snapshot; today the only flag is the idle-seat flag —
  `FLAG_IDLE_SEAT_LAUNCHABLE_CHILD` — each entry naming `stack`, `position` (the vetted layer),
  and `flag`.

The wire values for `state`, `reason`, and `flag` are the constants in `lib/wave_watch.py` and are
deliberately not restated here.

**Complete** (`STACK_STATE_COMPLETE`) means every position from `1` through `layersPlanned` has a
stack member whose vet reads READY at that pull request's **current** head — the stack gets its
one sheet, whole. Stop watching the batch only when every stack in the payload is complete; while
another stack in it is still incomplete, keep watching as the stack-state baseline limit below
describes. A position the watcher could not read
— its read budget ran out, or a pull-request or verdict read was refused — counts as not READY,
and the result's `degraded` list carries `stack-signal-unavailable`. **Incomplete**
(`STACK_STATE_INCOMPLETE`) with `reason` null means `missingPositions` names the layers not yet
READY — keep watching; those layers are still owed. **Planned count unknown**
(`STACK_REASON_LAYERS_PLANNED_UNKNOWN`) means no lane in the batch recorded `layersPlanned` —
completion cannot be judged; fix the launch premise. **Planned count disagreed**
(`STACK_REASON_LAYERS_PLANNED_DISAGREED`) means the batch's lanes recorded different
`layersPlanned` — reconcile the premises before trusting completion. **Membership unresolved**
(`STACK_REASON_MEMBERSHIP_UNRESOLVED`) means the stack's membership could not be read — verify the
stack link (GraphQL `stackEntry`) before acting. **`FLAG_IDLE_SEAT_LAUNCHABLE_CHILD`** observes a
vetted layer whose next planned position (`position + 1`) is within `layersPlanned` but no launch
in the batch occupies it — a seat the wave could fill now, without waiting for a merge.

When **`pr-set-changed`** fires, the payload carries the open PR set plus what moved:

- `prs` — sorted open PR numbers after the change
- `prsAdded` / `prsRemoved` — sorted numbers that joined or left the open set
- `stacks` — one entry per distinct stack any changed PR belongs to, sorted by stack
  number: `{"stack": <int>, "prs": [<every member in position order>]}`. A member read
  returns the whole stack, so the advisor sees one unit move, not unrelated PRs.
- `ungrouped` — sorted changed PRs that belong to no stack (or whose membership read
  refused). When stack membership is unavailable, `stack-signal-unavailable` rides on the
  result and grouping is partial — the original `prs` / `prsAdded` / `prsRemoved` keys
  are unchanged. Stack membership is read through `lib/stack_check.py`'s `read_membership`
  — the single membership reader, never re-implemented here — and the read is bounded by
  **one** budget covering the whole read, so an unresolvable read degrades to
  `stack-signal-unavailable` rather than returning partial membership.

When **`pr-set-changed`** sends you to read a lane's CI, select the run by **workflow name and head
sha** — never `gh run list --limit 1`. The newest run on a branch is whatever workflow happened to
fire last, which is not necessarily the one whose green you are claiming: a watcher taking
`--limit 1` read a preview-anchor sync and wrongly called CI green. The canonical statement lives in
`skills/showrunner/reference/vet-receipt.md`.

`loop` results — both ok and refusal — carry `arms`, the number of internal arms run in that
invocation. Every `loop` result also carries `passedOver` and `passedOverCount` (empty or zero when
nothing was passed over). `run` results never carry `arms`, `passedOver`, or `passedOverCount`.

`lane-stale` is a **wedged builder** under the quiet-window rule above. For a local lane it fires
only when the builder's pid is positively alive — an uncertain probe is not a wedge, and a dead
builder is `builder-exited` instead. See [Before treating `lane-stale` as a wedge](#before-treating-lane-stale-as-a-wedge)
for resolution, degradation tokens, and why an unresolvable transcript still alerts.

For a [cloud lane](../../../rubric/glossary.md#cloud-lane) the watcher never reports `builder-exited`,
`lane-blocked`, or `lane-never-stamped`, and never reads a transcript. It reports **`lane-terminal`**
for a cloud lane from the lane's issue comments (below). Its ending reaches you through its PR and
its issue. While a batch has a live cloud lane, every result carries
`cloudLanes`, which lists them.

When **`builder-note`** fires, a cloud builder has posted an issue comment opening with
`NOTE_HEADER` (`lib/cloud_builder.py`) on a live lane's issue since that lane started, and no
`note-answered` has recorded it. The payload carries `launchId` (the first note's lane) and `notes`,
by comment id: `{"launchId", "issue", "commentId", "url", "createdAt", "cloudSessionName",
"cloudSessionId", "configDir"}` — `configDir` names the Claude account the lane runs on — plus
`alsoObserved`. Answer the builder as [Answering a builder note](#answering-a-builder-note) says;
until a confirmed delivery is followed by `note-answered`, the note fires again on every arm. A note posted while you were away fires when you are back. It reads
the repository's issue comments once per tick, a `304` re-using the stored list.

When **`account-limited`** fires, the builders' account is at its usage limit, so nothing on it can
run. The payload names every live cloud lane on the account — `launchId` (the first), `launchIds`, and
`accounts`, by account: `{"configDir", "limitType", "resetsAt", "resetsAtIso", "launchIds"}` — plus
`alsoObserved`. Tell the owner which account, which limit and when it resets. Those lanes are stopped
(the account cannot run anything), so recover them at once, as `rubric/launch-doctrine.md` § Recovery
says; `cloud_recover.py assess` reads the same limit as stop evidence. While the limit holds the watch
does not report those lanes `lane-stale`: the limit explains their quiet. Once acted on, suppress it
per lane with `--ignore-event LAUNCHID:account-limited`. The relay writes the limit to its session record only when
it next tries to run, so a status ping through the relay is what makes the reading appear; read an
account by hand with `python3 -B <plugin root>/lib/cloud_relay.py limit --repo-root <root> --config-dir <dir>`.

When **`lane-terminal`** fires for a cloud lane, the newest comment on a live started lane's issue,
created at or after that lane's attempt began, opens with one of the terminal headers
(`TERMINAL_HEADERS` in `lib/cloud_builder.py`: handback, stop, park), and no `note-answered` has
recorded it. Its `launches` entry carries `{"launchId", "state", "kind", "issue", "commentId", "url",
"createdAt", "source": "comment", "cloudSessionName", "cloudSessionId", "configDir"}`, with `state`
`handback`, `stopped` or `parked`; every cloud lane that ended since the last read rides `launches`.
A **park** is superseded, and does not fire, when the same lane has later builder activity in the same
read: a builder note posted after the park was posted (whether or not it is recorded answered), or its
progress comment edited more than 300 seconds (`PARK_SUPERSESSION_GRACE_SECONDS`) after the park with a
phase that reads resumed: no word of the phase begins `park` or `stop`, unless a word begins `resum`.
A progress edit a few seconds after a park, or one whose phase reads parked or stopped, or one with
no phase, does not count: builders edit the progress comment seconds after a park with a parked phase,
and that edit is not a resume. A **handback or stop is never superseded**, and a park at or
after the lane's latest activity fires. A superseded park does not fall back to an older ending.
It reads the same issue-comments request as the builder note, so it costs no extra request. When a
local lane's `lane-terminal`, `lane-blocked` or `builder-exited` is already due, the cloud reads are
skipped that tick, so a cloud ending in the same tick surfaces on the next arm.

A terminal cloud lane **sent a fix order is watched again**, exactly like a live cloud lane, from that
moment until its next ending. The fix order is a `vet not-ready` amendment, or a fix-order relay to the
lane's session (`compose --fix-order`) once its `check` read delivered or a may-hold-text verdict; the relay opens the window at the
message's own compose time (`sentAfter`), never at the check, so a re-check moves nothing. A
`reoutcome` amendment, or a vet `ready` or `parked-blocker`, closes it; the newest opener must be later
than the newest closer. When the fix order is also sent by message, record the vet `not-ready`
before the message goes out: the window opens at the newest fix order, so a builder note or handback
posted between a send and a later `not-ready` is not surfaced.
The window runs from the fix order to the lane's first ending (handback, stop
or park, a superseded park not counting): endings and notes from before the fix order are not
re-reported, the closing ending fires `lane-terminal`, and nothing about the lane surfaces after it.
A refused or never-started lane, and a local lane, are never re-opened. A not-ready lane whose fix
goes to a fresh launch instead is passed `--ignore-launch`, or its vet is recorded `ready` or
`parked-blocker` when done, so the old lane is not watched for an ending that will never come.

What you do on each: on a **handback**, vet the PR. On a **stop**, repair it — an Anchor stop is duty
3's anchor-stop repair, a route-back is a re-route; record the lane's outcome and never relaunch it
unrepaired. On a **park**, answer it or route it; a parked lane is **never recovered**
(`cloud_recover.py assess` answers `parked`). If you answer a park by message and the builder
resumes, the watch stops reporting the park by itself once the builder posts a note, or edits its
progress comment to a resumed phase more than five minutes after the park. Still run `python3 -B <plugin root>/lib/wave_watch.py note-answered --repo-root <root>
--comment-id <the park comment's id>`, so recovery no longer reads it as a park
(`cloud_recover.py assess` still reads the park). A builder that ends with a free-form comment instead is seen only by the `lane-stale`
fallback.

A lane whose `reserved` ledger record names `charter: detective` (an absent `charter` reads as
workhorse) is read the same way, with a different action on each. On a **handback**, run
the diagnosis vet (the showrunner charter's duty to vet diagnosis receipts before routing fixes) on the
receipt the note links. On a **park**, read its text: a park that links a diagnosis receipt is the
detective's honest not-demonstrated exit, so run the diagnosis vet and do not send a receipt that
passes it back for another pass; a park with no receipt is a question that timed out (its text says no
receipt was posted and what the detective awaits), so answer or route it as for a builder park. On a **stop**, the detective declined the work before
spend, so route the incident and never repair a launch. No PR is vetted on a detective lane.

Lanes that launched over a live lane's surfaces carry `surfaceOverlap` (the overlapped launch ids)
on their `reserved` ledger record, and the batch `count` tallies them as `overlapsAccepted`. The
watcher does not act on either — read them when a lane you are watching hits a conflict at landing:
the later lander rebases onto the moved base (the `base-moved` standing ruling) and keeps its lane
branch-current as `merge-train.md` requires. That is the accepted cost, not a wedge.

**Refusals** (exit 1, `ok=False`): see `REFUSALS` in `lib/wave_watch.py`.

The pre-loop validations (`batch-invalid`, `interval-invalid`, `max-seconds-invalid`,
`max-total-seconds-invalid`, `ignore-event-invalid`, `repo-root-invalid`, `store-unresolvable`,
`loop-already-live`, `loop-lock-unavailable`) refuse immediately — re-arming without fixing the cause
just refuses again. A `loop-already-live` refusal carries `liveLoop`. `ledger-unreadable` also
refuses at arm time when the ledger file is absent or unreadable at the resolved root — for example a
takeover seat armed with a different ledger root — and every `ledger-unreadable` refusal carries
`ledgerPath`, the path the watcher read. It can also
arrive on the deadline path after the full `--max-seconds` window. `internal-error` comes from the
top-level exception handler wrapping all of `run()` — including the pre-loop validations — so it can
fire before the watch loop ever runs; neither `ledger-unreadable` on the deadline path nor
`internal-error` is guaranteed at arm time.

**Non-fatal degradations** that ride on a result: see `DEGRADATIONS` in `lib/wave_watch.py`.

Notes beyond the token name:

- `stack-signal-unavailable` — stack membership for one or more changed PRs could not be read before the watcher's deadline; grouping is partial and `ungrouped` carries what could not be resolved
- `lane-never-stamped` (`loop` only — not reported by `run`)
- `pr-signal-never-sampled` (`loop` only — not reported by `run`)
- `transcript-ambiguous` — two or more transcripts carry the lane's session id, so identity is ambiguous and the lane alerts rather than being suppressed
- `transcript-unresolved` — the transcript lookup could not complete (unreadable projects root or bucket, a candidate `stat` failing for anything but absence, an unusable recorded config root), so the lane alerts without the watcher being able to tell a cold transcript from an unread one
- `cloud-activity-unavailable` — the activity read for a cloud lane could not be made, so the lane is neither stale nor clean and the reading is partial
- `builder-note-unavailable` — the comments read could not be made or understood, so a note or a cloud lane's terminal comment may be waiting unseen; an unreadable answered record is not this token, it leaves notes surfacing; when the read was partial, the result's `unreadIssues` (`[{"launchId", "issue"}]`, present only then) names the issues it left unread, and across an arm or a loop a lane named once stays named
- `fix-order-unavailable` — the relay's state file could not be read, so a fix order relayed to a terminal cloud lane may go unseen; only `vet not-ready` amendments re-open lanes meanwhile

A degradation token is a disclosure that the reading is partial, not a clean sheet — e.g. a lane
whose heartbeat is unreadable can be reported by a lower-precedence event than its true state.

**On `builder-note-unavailable`, read the issues by hand at once.** A degraded comments read means a
builder note may be waiting unseen, so read the comments of every issue the event names
(`unreadIssues`; when the event names none, every watched cloud lane's issue) through REST
yourself, now, and answer any builder note there inside the builder's 15-minute reply window
(`rubric/review-discipline.md` § Size). Never wait for the next tick to read them.

## Answering a builder note

Each note names the session to answer (`cloudSessionName`) and the account it runs on (`configDir`).
Compare `configDir` with the account you run on, your resolved config directory (`CLAUDE_CONFIG_DIR`
when set, otherwise `~/.claude`). Answer by message, or through the relay below. The send is still the gate for `note-answered`; posting the same answer on the issue as the durable record is allowed and recommended.

**What the answer says.** Name the chosen option literally, in your own words: the line, value or
step the builder should use, written out in full. Never answer by reference to the note ("go ahead
as your note proposes", "the usual"): a cloud builder cannot message back to ask what you meant, so
an answer it cannot act on costs a second round trip and the gate below still reads it as delivered.

**One-time setup.** Each Claude account the builders run on must have opened Claude Code in the
repository root once and accepted its trust prompt. The owner does this once per account, before the
relay on that account can start.

**Same account.** Send the answer to the session by `SendMessage`. The gate is that call's result
reading `success: true`.

**Another account.** The answer goes through a relay, a background session on that account
(`lib/cloud_relay.py`; `skills/workhorse/reference/cloud.md` has the builder's side). A vet's fix
order relayed to the lane's session is composed with `--fix-order`, and it re-opens the watch only once
`check` reads delivered (or a may-hold-text verdict). In order:

1. `python3 -B <plugin root>/lib/cloud_relay.py ensure --repo-root <root> --config-dir <configDir>`,
   before every relayed answer. It starts the relay if none is listed, which keeps it alive and
   follows the builders to whichever account they run on, one relay per account. It returns `name`.
2. Write the answer to a file, then `compose --repo-root <root> --config-dir <configDir> --session
   <cloudSessionName> --text-file <file>`. It returns `msgId`, `relayMessage` and `forward`. The
   answer text never carries a shell-evaluated value you have not seen expanded, such as a time
   from `$(date -u …)` inside a heredoc: run the command first, read its output, and write the
   value into the answer as text. Then print the whole composed `relayMessage`, never a truncated
   view such as `head` or the message id alone, so the text you send is text you have read.
3. Send exactly the `relayMessage` you printed by `SendMessage` to the relay's `name`, copied from
   that output and never retyped from your own draft. A change after compose, even one word, means
   writing a new answer file and composing a new message; never edit a composed one.
4. `check --repo-root <root> --msg-id <msgId>`. The gate is `delivered: true`. A message counts as
   delivered only when the text the relay sent matches `forward` exactly; the relay's own words about
   what it sent are never the receipt. `check` reads every send of that exact text, to the session's
   name or to `<session name> [<ref>]`: it reads `delivered` when some send of the exact text has
   `success: true` and no send of this message carries altered text, while any altered send reads
   `relay-text-mismatch`, whatever else succeeded. A failed attempt does not end the check early. At
   the end of the wait it reads `relay-send-unconfirmed` when an exact send still has no result,
   `relay-send-failed` when every exact send failed, and `relay-silent` when there was none.
   Re-running `check` later re-reads the relay's record. A send of the message's text with its header
   line dropped reads `relay-text-mismatch` with `headerDropped: true` at the end of the wait, unless an
   exact send succeeded; it was sent, altered, so the builder may hold the text. `check` sees only
   the relay's send compared with the stored text, so a mismatch does not say which step changed
   it: your own send can reach the relay already changed.

**Not delivered, or `ensure` refused.** Do not run `note-answered`; the note keeps surfacing. Tell the
owner the `say` sentence, or the refusal and its `detail`. After `relay-silent` or
`relay-send-unconfirmed`, re-run `check` with a longer `--wait` before concluding. Retry once from
`ensure` only when nothing can have reached the builder: an `ensure` refusal or `relay-send-failed`.
After `relay-silent`, `relay-text-mismatch` or `relay-send-unconfirmed` the builder may hold text:
never resend automatically.
A `relay-start-failed` naming an untrusted workspace means that account lacks the one-time setup step.

**Delivered.** Run `python3 -B <plugin root>/lib/wave_watch.py note-answered --repo-root <root>
--comment-id <id>` for that note, then re-arm.

The message resumes a parked cloud session, which re-reads its issue and carries on, so the answer
reaches a builder that already parked. When you are back after being away, the first arm reports every
note still waiting (`notes`, oldest first). Answer each in turn as above, each with its own gate; that
also resumes each lane that parked on one. There is no separate resume step.

Any other message you send to a cloud session on another account, the archive request after a merge
or close included, goes through the same relay path and gate. The archive request's own steps are in
`skills/showrunner/reference/merge-train.md` § Cleaning up a finished cloud lane.

## The boundary the owner accepted

- The watcher's usefulness is **in-session**: it watches while the advisor's session is alive and
  re-arms. It is not a background service and does not survive the app closing.
- **After a resume, re-arm** — the watcher does not persist across compaction or session recovery on
  its own.
- **PR-set baseline:** within one `loop` invocation, the PR baseline threads across internal arms, so
  a PR change landing between timer arms **is** reported (as a passed-over `pr-set-changed` entry at
  loop exit). The gap remains **open between separate invocations**. Bare `run` never reports a PR
  change — it has no PR baseline to compare against.
- **Stack-state baseline:** within one `loop` invocation, the stack-state baseline threads across
  timer arms, so a stack that becomes complete between arms is reported once (as a passed-over
  `stack-state-changed` entry at loop exit). `loop` no longer ends on `stack-state-changed` — it
  passes over and reports it, so a multi-stack batch no longer loses its wait once any stack is
  complete. Each new invocation still starts without a baseline: a watch armed on a batch whose stack
  is already complete, or that already carries the idle-seat flag
  (`FLAG_IDLE_SEAT_LAUNCHABLE_CHILD`), reports `stack-state-changed` on its first arm — as a
  passed-over entry under `loop`, as the event under `run`.
- **A mistyped batch id is indistinguishable from a quiet batch** — but the verb matters. Bare
  `run` produces a calm `timer`, not a refusal. `loop` treats every `timer` as non-terminal and
  re-arms; with no `--max-total-seconds` bound it produces **nothing on stdout** until something
  lane-ending happens or a builder note arrives, so a mistyped batch id under `loop` looks exactly like a healthy quiet wave for
  as long as you leave it running.
- **A started lane that has never stamped a heartbeat across the full watch window
  is reported as a `lane-never-stamped` degradation at the deadline** — but
  `builder-exited` still surfaces it when its recorded pid dies. A cloud lane has no heartbeat and no
  pid, so the watcher reports neither for it.

## How it relates to the heartbeat sweep

The heartbeat sweep (`lib/heartbeat.py`) reads **endings** — `terminal`, `nonterminal`, and
`unknown` — on a schedule the advisor runs and acts on. **Liveness** lives in `wave_watch`: for a
local lane, pid positively live plus session transcript age against `LIVENESS_QUIET_WINDOW_SECONDS`,
and for a [cloud lane](../../../rubric/glossary.md#cloud-lane), its activity on GitHub against the
same window. The sweep reports a cloud lane `nonterminal` with reason `cloud-lane-no-heartbeat`,
which says nothing about liveness. The watcher is a blocking arm (`loop` at wave launch, or a one-off `run`) — `loop` returns on the first arm its exit
classifier does not pass over — a refusal, a lane-ending event, an attention event, an unknown event, or a
`stack-state-changed` carrying the launchable idle-seat flag — or at its `--max-total-seconds`
ceiling (see "What ends a loop and what it passes over"); `run` returns at once. Neither the sweep
nor the watcher asserts a lane is dead.
