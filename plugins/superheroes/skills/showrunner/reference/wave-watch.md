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

Assign the portable root seam once, then invoke the watcher:

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
python3 -B "$ROOT_DIR/lib/wave_watch.py" run \
  --repo-root "$REPO_ROOT" --batch "$BATCH_ID" \
  --max-seconds 2400 --interval-seconds 60 \
  --ignore-launch "$ALREADY_HANDLED_LAUNCH_ID"  # re-arm only — omit on first arm
```

`$REPO_ROOT` and `$BATCH_ID` are session variables you supply. On a **first arm**, omit
`--ignore-launch` — there are no handled lanes yet. On **re-arm**, repeat `--ignore-launch` for
each launch id already handled on that arm.

The call **blocks** until an event or the deadline, so `--max-seconds` is also how long the
advisor's session is committed to this arm. On Claude Code, Bash timeout has two layers
(`hooks/bash_timeout.py`, `skills/workhorse/reference/dispatch-mechanics.md`): an **omitted**
timeout is rewritten to 600000 ms (600 s), so a foreground arm with no explicit timeout — this
snippet supplies none — is killed at ~600 s regardless of `--max-seconds`; an **explicit**
timeout above ~600 s converts the call to background, where it dies when the turn ends. Size
`--max-seconds` to what the session can await inside that in-turn window and re-arm as the loop,
or accept that a longer arm needs a continuation mechanism this tool does not provide.

## `--ignore-launch` and re-arming

`--ignore-launch` is what makes re-arming work. It is repeatable, and it excludes a launch id from
lane enumeration. Without it, a lane you have already handled but cannot terminalize re-fires on
every arm and the loop spins on the same event.

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
- `repo-root-invalid`
- `store-unresolvable`
- `ledger-unreadable`
- `internal-error`

The pre-loop validations (`batch-invalid`, `interval-invalid`, `max-seconds-invalid`,
`repo-root-invalid`, `store-unresolvable`) refuse immediately — re-arming without fixing the cause
just refuses again. `ledger-unreadable` can also arrive on the deadline path after the full
`--max-seconds` window. `internal-error` comes from the top-level exception handler wrapping all
of `run()` — including the pre-loop validations — so it can fire before the watch loop ever runs;
neither `ledger-unreadable` on the deadline path nor `internal-error` is guaranteed at arm time.

**Non-fatal degradations** that ride on a result:

- `ledger-torn-tail`
- `ledger-unreadable`
- `heartbeat-unreadable`
- `pid-probe-uncertain`
- `pr-signal-unavailable`
- `lane-never-stamped`
- `pr-signal-never-sampled`

A degradation token is a disclosure that the reading is partial, not a clean sheet — e.g. a lane
whose heartbeat is unreadable can be reported by a lower-precedence event than its true state.

## The boundary the owner accepted

- The watcher's usefulness is **in-session**: it watches while the advisor's session is alive and
  re-arms. It is not a background service and does not survive the session.
- **PR changes in the gap between one exit and the next arm are not reported** — the PR baseline is
  rebuilt on each arm.
- **A mistyped batch id is indistinguishable from a quiet batch** — it produces a calm `timer`, not
  a refusal.
- **A started lane that has never stamped a heartbeat across the full watch window
  is reported as a `lane-never-stamped` degradation at the deadline** — but
  `builder-exited` still surfaces it when its recorded pid dies.

## How it relates to the heartbeat sweep

The heartbeat sweep (`lib/heartbeat.py`) and `wave_watch` are complementary, not substitutes: the
sweep is a scheduled, whole-wave read the advisor runs and acts on; the watcher is a single-shot
block that returns the moment one lane does something. Neither asserts a lane is dead.
