# Contents

- [What it is](#what-it-is)
- [The arming pattern](#the-arming-pattern)
- [`--ignore-launch` and re-arming](#--ignore-launch-and-re-arming)
- [What it tells you](#what-it-tells-you)
- [The boundary the owner accepted](#the-boundary-the-owner-accepted)
- [How it relates to the heartbeat sweep](#how-it-relates-to-the-heartbeat-sweep)

# Wave watch

## What it is

`lib/wave_watch.py` is a ledger-driven **single-shot** watcher over one launch batch: it watches
until the first thing worth knowing about, prints one JSON line, and exits. **The advisor's re-arm
is the loop** — there is no daemon, so there is nothing to orphan. It replaces hand-rolled
per-session watch loops that kept failing quietly: a double-backgrounded loop that orphaned, a
hand-typed PID list that went stale the moment an unpark launched a new builder, a ten-hour
dead-watcher hole — and each failure looked like a calm wave.

## The arming pattern

Arm **one harness background task per batch** at wave launch — a **`loop` invocation** that re-arms
internally until the first actionable event or a refusal. The advisor is never blind between turns:
when the background task exits, the harness re-invokes the advisor with the result.

Assign the portable root seam once, then arm `loop` as a **background task** (give the Bash call an
explicit timeout above the foreground-conversion boundary so the host converts it to background —
do not await it in the foreground):

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
python3 -B "$ROOT_DIR/lib/wave_watch.py" loop \
  --repo-root "$REPO_ROOT" --batch "$BATCH_ID" \
  --max-seconds 2400 --interval-seconds 60 \
  --ignore-launch "$ALREADY_HANDLED_LAUNCH_ID"  # omit on first arm
```

`$REPO_ROOT` and `$BATCH_ID` are session variables you supply. On a **first arm**, omit
`--ignore-launch` — there are no handled lanes yet.

`--max-seconds` is the **per-arm** evaluation window — how long each internal `run()` arm watches
before a `timer` event forces re-arm. It is **not** the advisor's session commitment; `loop`
re-arms until an actionable event or refusal. **By default** `loop` is **unbounded** (omit
`--max-total-seconds`): timer arms chain until something actionable happens. `--max-total-seconds`
caps how long the whole loop may keep re-arming (see the boundary section for overrun honesty).
`--log PATH` appends one JSON line per timer arm to `PATH` for post-mortem review.

**Turn survival depends on session kind.** On Claude Code, Bash timeout has two layers
(`hooks/bash_timeout.py`, `skills/workhorse/reference/dispatch-mechanics.md`): an **omitted**
timeout is rewritten to 600000 ms (600 s), and an **explicit** timeout above ~600 s converts the
call to background. In an **interactive** session, a harness background task **survives across
turns and re-invokes the advisor on exit** — which is precisely what makes the background arm of
`loop` work. In a **headless** session (`claude -p`), the session **exits when its turn ends**, and
converted or harness-tracked background work **dies when the turn ends** — size per-arm windows
accordingly or accept that a longer watch needs a continuation mechanism this tool does not
provide.

### One-off `run` check

For "is anything happening right now?" — **not** the arming shape — use foreground **`run`**:

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
python3 -B "$ROOT_DIR/lib/wave_watch.py" run \
  --repo-root "$REPO_ROOT" --batch "$BATCH_ID" \
  --max-seconds 2400 --interval-seconds 60
```

`run` blocks until one event or the per-arm deadline and exits; it does not re-arm. Use it for a
spot check, not wave orchestration.

## `--ignore-launch` and re-arming

`--ignore-launch` is what makes re-arming work. It is repeatable, and it excludes a launch id from
lane enumeration. Without it, a lane you have already handled but cannot terminalize re-fires on
every arm and the loop spins on the same event. It applies to **`loop`'s internal arms** as well as
to separate invocations and to bare `run`.

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
siblings.

`lane-stale` is a **wedged builder**: alive but frozen past its own `staleAfterSeconds` promise. It
fires only when the builder's pid is positively alive — an uncertain probe is not a wedge, and a
dead builder is `builder-exited` instead.

**Refusals** (exit 1, `ok=False`):

- `batch-invalid`
- `interval-invalid`
- `max-seconds-invalid`
- `max-total-seconds-invalid`
- `repo-root-invalid`
- `store-unresolvable`
- `ledger-unreadable`
- `internal-error`

The pre-loop validations (`batch-invalid`, `interval-invalid`, `max-seconds-invalid`,
`max-total-seconds-invalid`, `repo-root-invalid`, `store-unresolvable`) refuse immediately —
re-arming without fixing the cause just refuses again. `ledger-unreadable` can also arrive on the
deadline path after the full `--max-seconds` window. `internal-error` comes from the top-level
exception handler wrapping all of `run()` — including the pre-loop validations — so it can fire
before the watch loop ever runs; neither `ledger-unreadable` on the deadline path nor
`internal-error` is guaranteed at arm time.

**Non-fatal degradations** that ride on a result:

- `ledger-torn-tail`
- `ledger-unreadable`
- `heartbeat-unreadable`
- `pid-probe-uncertain`
- `pr-signal-unavailable`
- `lane-never-stamped`
- `log-unwritable`

A degradation token is a disclosure that the reading is partial, not a clean sheet — e.g. a lane
whose heartbeat is unreadable can be reported by a lower-precedence event than its true state.

## The boundary the owner accepted

- The watcher's usefulness is **in-session**: it watches while the advisor's session is alive and
  re-arms. It is not a background service and does not survive the session.
- **PR-set gap is closed within a `loop` arm-chain** — `loop` threads one PR baseline across its
  internal re-arms, so changes between internal timer arms are reported. The gap remains **open
  between separate invocations** and for bare `run`, where the PR baseline is rebuilt on each call.
- **`--max-total-seconds` is a re-arm bound, not a hard kill** — the loop will not start a new arm
  past the total, and may overrun it by the final arm's rounding plus one evaluation pass.
- **A mistyped batch id is indistinguishable from a quiet batch** — it produces a calm `timer`, not
  a refusal.
- **A started lane that has never stamped a heartbeat is invisible to the heartbeat-derived signal
  classes** (`lane-terminal`, `lane-blocked`, `lane-stale`) — but `builder-exited` still surfaces
  it when its recorded pid dies.

## How it relates to the heartbeat sweep

The heartbeat sweep (`lib/heartbeat.py`) and `wave_watch` are complementary, not substitutes: the
sweep is a scheduled, whole-wave read the advisor runs and acts on; the watcher is a single-shot
block that returns the moment one lane does something. Neither asserts a lane is dead.
