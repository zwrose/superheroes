# Contents

- [What it is](#what-it-is)
- [The arming pattern](#the-arming-pattern)
- [One-off check (`run`)](#one-off-check-run)
- [`--ignore-launch` and re-arming](#--ignore-launch-and-re-arming)
- [`--ignore-event` and re-arming](#--ignore-event-and-re-arming)
- [Before treating `lane-stale` as a wedge](#before-treating-lane-stale-as-a-wedge)
- [The default promise, and the number behind it](#the-default-promise-and-the-number-behind-it)
- [Timing flags](#timing-flags)
- [What it tells you](#what-it-tells-you)
- [The boundary the owner accepted](#the-boundary-the-owner-accepted)
- [How it relates to the heartbeat sweep](#how-it-relates-to-the-heartbeat-sweep)

# Wave watch

## What it is

`lib/wave_watch.py` is a ledger-driven watcher over one launch batch. It has two verbs:

- **`loop`** — the arming shape. Re-arms internally until the first actionable event or a refusal,
  then prints one JSON line and exits. Arm as **one harness background task per batch** at wave
  launch.
- **`run`** — a one-off foreground spot check. It watches once, prints one JSON line, and exits. It
  does **not** re-arm.

**The re-arm lives inside `loop`** — there is no daemon, so there is nothing to orphan. It replaces
hand-rolled per-session watch loops that kept failing quietly: a double-backgrounded loop that
orphaned, a hand-typed PID list that went stale the moment an unpark launched a new builder, a
ten-hour dead-watcher hole — and each failure looked like a calm wave.

## The arming pattern

Assign the portable root seam once, then arm one harness **background task per batch**:

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
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
returns immediately and shows whether the batch resolves to any lanes at all — the cheap way to catch
a mistyped batch id before you go blind in a long `loop`.

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
message) and `--log PATH` (each timer arm is recorded, so you can see the loop is alive and which
batch it is watching). Without them, a mistyped or quiet batch under `loop` produces **no stdout at
all** until something actionable happens — indistinguishable from a healthy quiet wave for as long as
you leave it running.

In an **interactive** session, a harness background task survives across turns and re-invokes the
advisor when it exits — that is what keeps you from going blind between turns while `loop` runs.
In a **headless** session (`claude -p`), the session exits when its turn ends, so a background task
dies with the turn; do not arm `loop` there unless you have a continuation mechanism outside this
tool.

Bash timeout on Claude Code has two layers (`hooks/bash_timeout.py`,
`skills/workhorse/reference/dispatch-mechanics.md`): an **omitted** timeout is rewritten to 600000 ms
(600 s), so a foreground call with no explicit timeout is killed at ~600 s; an **explicit** timeout
above ~600 s converts the call to background. For the arming pattern, use the harness background-task
primitive so `loop` survives across turns — do not rely on a foreground arm outliving the turn.

## One-off check (`run`)

Use `run` for a **single foreground spot check** — "is anything happening right now?" — not for wave
arming:

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
python3 -B "$ROOT_DIR/lib/wave_watch.py" run \
  --repo-root "$REPO_ROOT" --batch "$BATCH_ID" \
  --max-seconds 2400 --interval-seconds 60
```

`run` takes the same flags as `loop` except `--max-total-seconds` and `--log`. It does not re-arm.

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
a long arm chain. Only the four **lane-keyed** events are suppressible: `lane-terminal`,
`lane-blocked`, `builder-exited`, `lane-stale`.
`pr-set-changed` and `timer` are not lane-keyed; naming them is a refusal (`ignore-event-invalid`).
A malformed pair is a refusal (`ignore-event-invalid`), never a silent drop.

**Pattern — the exception, not the routine:** when `loop` wakes you on an event you have **verified**
benign (for `lane-stale`: pid live **and** transcript fresh — the watcher now checks the transcript
itself, so a `lane-stale` that still fires is one it could not vouch for), re-arm with
`--ignore-event <launchId>:<event>` so that exact pair stops waking you **while that lane's other
events still do**. Within a single `loop` invocation, the first unsuppressed actionable event exits
the loop; persistence across invocations is **your** job — pass `--ignore-event` on re-arm. The tool
does not dedupe suppressed pairs across invocations by itself. **Do not pre-arm `--ignore-event` for
`lane-stale` as a matter of course**: an arm that ignores every lane's stale signal has quietly
reduced the watcher to `pr-set-changed`, and the wave's wedges arrive as surprises. If you find
yourself suppressing the same event on most lanes of a wave, that is a field observation to record
(the promise or the second chance is wrong), not a pattern to keep.

## Before treating `lane-stale` as a wedge

A stale lane whose transcript is **fresh** is the **benign long-dispatch shape** — a builder alive
inside a long engine dispatch whose heartbeat promise lapsed between stamps. **The watcher now reads
that pair for you.** Before emitting `lane-stale` it resolves the lane's session transcript from
the **session id the launcher recorded on the launch record**, and a transcript written **inside
that lane's own `staleAfterSeconds` window** suppresses the event.

So `lane-stale` now means three things at once: the heartbeat outran the promise, the pid is
positively live, **and** the transcript is cold. That is the wedge.

A suppressed lane is not silently dropped — it rides the arm's result under **`staleSuppressed`**,
each entry carrying the note `stale-suppressed-transcript-fresh`, the lane's heartbeat age, its
promise, and how old the transcript actually was. The note rides **every** result of that arm
including `timer`, which is what puts it in the `--log` line, so a long quiet arm still shows which
lanes it judged to be working.

**The check fails toward the alert, never toward silence.** Every way the transcript read can fail to
prove work — no session id on the lane's ledger record, no transcript on disk, two-or-more
transcripts with the same id, an unreadable projects directory, a transcript dated into the future
by any amount — leaves the lane stale and the event fires. Ambiguity additionally records
`transcript-ambiguous`.

**A lookup that could not complete says so.** When the watcher could not *resolve* the transcript at
all — the projects root or a bucket was unreadable, a candidate's `stat` failed for any reason other
than the file being absent, or the lane recorded a config root the watcher cannot use — the lane
alerts **and** records `transcript-unresolved`. Read it as *the watcher could not vouch either way*,
not as *the transcript is cold*: without it, an I/O failure and a genuinely wedged builder produce
the same alert with the same silence behind it. **Absence is not unresolved** — a missing projects
root, a missing bucket, or a missing transcript means the transcript is not there, which is the wedge
signal `lane-stale` exists to report, so those alert with **no** token. A pre-#1029 record carrying
no session id gets no second chance and no token either — that is the documented no-identity class,
not a failed reading.

**Only the lane's own transcript may vouch for it.** The launch record's session id names exactly one
file: `<sessionId>.jsonl` under a config root's `projects` tree. Exactly one config root is searched,
never both — because a same-named file under any other root belongs to a different session. **The
lane's own recorded root wins:** the launcher records on the launch record the `configDir` its
builder was spawned under, and the watcher searches *that* root, so a lane launched under another
Claude instance (`.claude-two`, a per-launch exception) still gets its second chance instead of
alerting because the watcher looked in its own root. A record carrying no `configDir` — every
pre-#1036 launch — resolves under the watcher's own env root as before (`CLAUDE_CONFIG_DIR` outright
when set, otherwise `~/.claude`). A symlinked entry is never followed; and the watcher **stat's
only** — it never reads transcript contents.

Launches without a recorded session id get **no second chance** — pre-change ledger records still
alert. The concurrent-foreign-session-in-the-same-worktree residual is **closed** by recorded
identity: a different session carries a different id and cannot vouch for this lane.

A transcript-suppressed lane is **not** the same as an `--ignore-event` suppression: `--ignore-event`
silences an event the watcher still believes, so the lane keeps showing up under `alsoObserved`; a
transcript-suppressed lane is one the watcher judged to be *working*, so it drops out of
`alsoObserved` too. A lane found still stale on a later tick of the same arm loses its earlier
suppression note, so the note can never contradict the event it rides on.

Field specimen the fix was built from: heartbeat age 1835 s against an 1800 s promise, transcript
mtime 2.5 minutes — benign, and before this it terminated an arm anyway.

## The default promise, and the number behind it

A builder states its own `staleAfterSeconds` when it stamps (`--stale-after`), and that promise is
what `lane-stale` measures against. A caller that states **no** promise gets the default in
`lib/heartbeat.py` — `DEFAULT_STALE_AFTER_SECONDS`, **24000 s** (6 h 40 m).

That floor is derived, not chosen: it is **2× the worst benign inter-stamp gap measured on this
host, 11960 s**. The measurement pooled **45** inter-stamp gaps across **10** builder lanes, read
from the session transcripts, and counted a gap as *benign* only when the transcript never went
colder than **600** s anywhere inside it — 600 s being the host's foreground-Bash ceiling — so the
lane was demonstrably working the whole way through. **44** of the 45 gaps were benign.

Those numbers live in one place, `heartbeat.STALE_AFTER_MEASUREMENT`; this paragraph and
CONVENTIONS §15 are drift-checked against it, so correcting the measurement cannot leave a stale
derivation behind.

The previous default was 300 s, which no real build has ever met: a caller that omitted the flag was
guaranteed to read `stale` within five minutes. The floor moves only that fallback — a builder that
states its own promise is unaffected, and `builder-exited` still surfaces a lane whose pid dies
regardless of any promise.

## Timing flags

Under `loop`, `--max-seconds` is the **per-arm** watch window (default 2400) — how long each internal
arm watches before a `timer` forces a re-arm. It is **not** how long the advisor's session is
committed.

`--interval-seconds` (default 60) is the polling interval within each arm.

`--max-total-seconds` is optional; **absent means the loop is unbounded**. It is a **re-arm bound,
not a hard kill**: the loop will not *start* a new arm once the total is reached, and may overrun
the total by the final arm's rounding plus one evaluation pass.

`--log PATH` appends one JSON line per timer arm — `{"arm": N, "elapsedSeconds": E, "result": {…}}`
— for post-mortem review. A failing log write never terminates the loop; it discloses
`log-unwritable`. `run` does not accept `--log` or `--max-total-seconds`.

## What it tells you

The watcher prints **one JSON line on stdout**; **exit 0 on an event, exit 1 on a refusal**.

**Events** (`ok=True`):

- `lane-terminal`
- `lane-blocked`
- `builder-exited`
- `pr-set-changed`
- `lane-stale`
- `timer`

**Precedence**, highest first:

`lane-terminal` > `lane-blocked` > `builder-exited` > `pr-set-changed` > `lane-stale` > `timer`

When an event fires, co-occurring lower-precedence lane signals from the same interval ride along
under `alsoObserved` (launch ids only) — read it, or you will act on one lane and miss its
siblings. A `timer` result has no `alsoObserved`.

When **`pr-set-changed`** sends you to read a lane's CI, select the run by **workflow name and head
sha** — never `gh run list --limit 1`. The newest run on a branch is whatever workflow happened to
fire last, which is not necessarily the one whose green you are claiming: a watcher taking
`--limit 1` read a preview-anchor sync and wrongly called CI green. The canonical statement lives in
`skills/showrunner/reference/vet-receipt.md`.

`loop` results — both ok and refusal — carry `arms`, the number of internal arms run in that
invocation. `run` results never carry `arms`.

`lane-stale` is a **wedged builder**: alive but frozen past its own `staleAfterSeconds` promise. It
fires only when the builder's pid is positively alive — an uncertain probe is not a wedge, and a
dead builder is `builder-exited` instead — **and** only when the lane's session transcript is cold.
See [Before treating `lane-stale` as a wedge](#before-treating-lane-stale-as-a-wedge) for the
transcript second chance, the `staleSuppressed` note it emits instead, and why an unresolvable
transcript still alerts.

`staleSuppressed` rides any result — `timer` included — when the transcript second chance held a
lane back from `lane-stale` during that arm. It is a **note about what the watcher saw**, not an
event: a result carrying only `staleSuppressed` is a result where nothing actionable happened.

**Refusals** (exit 1, `ok=False`):

- `batch-invalid`
- `interval-invalid`
- `max-seconds-invalid`
- `max-total-seconds-invalid`
- `ignore-event-invalid`
- `repo-root-invalid`
- `store-unresolvable`
- `ledger-unreadable`
- `internal-error`

The pre-loop validations (`batch-invalid`, `interval-invalid`, `max-seconds-invalid`,
`max-total-seconds-invalid`, `ignore-event-invalid`, `repo-root-invalid`, `store-unresolvable`)
refuse immediately — re-arming without fixing the cause just refuses again. `ledger-unreadable` can
also arrive on the deadline path after the full `--max-seconds` window. `internal-error` comes from
the top-level exception handler wrapping all of `run()` — including the pre-loop validations — so
it can fire before the watch loop ever runs; neither `ledger-unreadable` on the deadline path nor
`internal-error` is guaranteed at arm time.

**Non-fatal degradations** that ride on a result:

- `ledger-torn-tail`
- `ledger-unreadable`
- `heartbeat-unreadable`
- `pid-probe-uncertain`
- `pr-signal-unavailable`
- `lane-never-stamped`
- `pr-signal-never-sampled`
- `log-unwritable`
- `transcript-ambiguous` — two or more transcripts carry the lane's session id, so identity is
  ambiguous and the lane alerts rather than being suppressed
- `transcript-unresolved` — the transcript lookup could not complete (unreadable projects root or
  bucket, a candidate `stat` failing for anything but absence, an unusable recorded config root), so
  the lane alerts without the watcher being able to tell a cold transcript from an unread one

A degradation token is a disclosure that the reading is partial, not a clean sheet — e.g. a lane
whose heartbeat is unreadable can be reported by a lower-precedence event than its true state.

## The boundary the owner accepted

- The watcher's usefulness is **in-session**: it watches while the advisor's session is alive and
  re-arms. It is not a background service and does not survive the app closing.
- **After a resume, re-arm** — the watcher does not persist across compaction or session recovery on
  its own.
- **PR-set baseline:** within one `loop` invocation, the PR baseline threads across internal arms,
  so a PR change landing between timer arms **is** reported. The gap remains **open between separate
  invocations** and for bare `run`, where the baseline is rebuilt per call.
- **A mistyped batch id is indistinguishable from a quiet batch** — but the verb matters. Bare
  `run` produces a calm `timer`, not a refusal. `loop` treats every `timer` as non-terminal and
  re-arms; with no `--max-total-seconds` bound it produces **nothing on stdout** until something
  actionable happens, so a mistyped batch id under `loop` looks exactly like a healthy quiet wave for
  as long as you leave it running.
- **A started lane that has never stamped a heartbeat across the full watch window
  is reported as a `lane-never-stamped` degradation at the deadline** — but
  `builder-exited` still surfaces it when its recorded pid dies.

## How it relates to the heartbeat sweep

The heartbeat sweep (`lib/heartbeat.py`) and `wave_watch` are complementary, not substitutes: the
sweep is a scheduled, whole-wave read the advisor runs and acts on; the watcher is a blocking arm
(`loop` at wave launch, or a one-off `run`) that returns the moment one lane does something.
Neither asserts a lane is dead.
