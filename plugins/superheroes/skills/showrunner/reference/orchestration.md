# Contents

- [Orchestration — launcher, ledger, and wave mechanics](#orchestration--launcher-ledger-and-wave-mechanics)
- [Batches and terminal outcomes](#batches-and-terminal-outcomes)
- [Reading `count`](#reading-count)
- [Amending a lane's record](#amending-a-lanes-record)
- [The ledger is version-coupled](#the-ledger-is-version-coupled)
- [The launcher provisions each build's worktree](#the-launcher-provisions-each-builds-worktree)
- [Liveness sweep and wave watch](#liveness-sweep-and-wave-watch)
- [Adoption mechanics](#adoption-mechanics)

# Orchestration — launcher, ledger, and wave mechanics

This page is reference for the advisor running launches and waves. Duty 9 of the Showrunner charter
states the rules; this page holds the mechanics behind them. The authoritative semantics of every
verb named here live in `lib/launcher.py` and `lib/launch_ledger.py`.

## Batches and terminal outcomes

**Declare a batch before its launches.** Then **record every terminal outcome** with
`record-outcome` — handback, park, refusal, or died. An unrecorded outcome makes the batch
unreadable rather than clean.

`record-outcome` **refuses while the lane's child is still alive** (`terminal-child-live:<pid>`),
and `lane-terminal` fires a minute or two before that exit. Pass **`--await-exit <seconds>`** so the
verb waits the child out rather than needing a second watcher; at the ceiling it returns the same
refusal.

## Reading `count`

**After a batch, run `count`** and read it honestly.

- **`indeterminate` means the record cannot see the whole batch** and must be resolved, not waved
  through.
- **A fully-resolved batch with zero parks and zero refusals is a signal to inspect**, never a clean
  sheet.
- **`count` reads lanes** — a build intent keyed by issue number, so retried attempts belong to one
  lane — with **`attempts`** beside the terminal tallies and **`laneDetail`** per lane. Overlapping
  same-lane launches still refuse.
- **Read the `amendments` block beside the terminal tallies.** `rehandback` is a lane that was
  handed back, ruled not ready, and handed back again. Zero parks with a non-zero `rehandback` is a
  frictionful wave, not a clean one.

## Amending a lane's record

**After vetting a delivered lane, record the ruling** with
`amend --kind vet --value ready|not-ready|parked-blocker --note "<one line>"`. A NOT-READY ruling,
and a parked blocker inside a delivered PR, are friction the terminal tallies cannot see.

**A second `record-outcome` on a lane that started and then ended with an outcome is recorded, not
refused.** A never-started lane is still refused with `outcome-without-started`. The second call
lands as a `reoutcome` amendment and leaves the original terminal outcome untouched. The CLI exits
**non-zero** with `recorded: 'amendment'` (or `'amendment-existing'` on an identical retry), because
the requested terminal write did not become the lane's outcome. So a lane handed back twice stops
reading as one clean handback.

**A terminal record whose evidence later proves wrong is corrected with `amend --kind evidence`**,
never by rewriting the record.

## The ledger is version-coupled

A record kind an older plugin build does not understand bricks every ledger door with
`fold-unknown-event:<kind>` until you delete the ledger file at the path `ledger_path()` reports.

## The launcher provisions each build's worktree

`launch` creates the worktree before the spawn, one per launch, detached at the premise's base
commit. It records the path on the `reserved` record and starts the session inside it. A path that
already exists, or that git still registers, **refuses the launch** (`launch-worktree-collision`):
reap the stale checkout, then relaunch. Never force it.

## Liveness sweep and wave watch

**Scheduled liveness sweep.** An advisor orchestrating a wave owes a scheduled two-read sweep — not a
one-off rescue when something feels wrong.

- **Liveness:** run
  `python3 -B <plugin root>/lib/wave_watch.py run --repo-root <repo-root> --batch <id>` per live
  batch. `lane-stale` means the pid is live and the session transcript is quiet past
  `LIVENESS_QUIET_WINDOW_SECONDS`, or could not be resolved: investigate or resume.
- **Endings:** run `python3 -B <plugin root>/lib/heartbeat.py sweep --repo-root <repo-root>` and read
  the classes.
  - `terminal` on a launch the ledger still reports live is **actionable pending `record-outcome`**,
    never a resolved lane.
  - `unknown` means the signal could not be read. It is **actionable, not clean**.
  - `nonterminal` says nothing about liveness.

The sweep **reports; it never asserts a lane is dead** — a heartbeat cannot prove death — and it
never resumes anything on its own. You act on what it reports.

**Wave watch.** Arm one harness **background task per batch** — a `loop` invocation that re-arms
internally — instead of hand-rolling a per-session watch loop. There is no daemon to orphan. The
arming pattern lives in `skills/showrunner/reference/wave-watch.md`; read it at arming time.

**Wave-preflight live canary.** A wave preflight runs
`python3 -B <plugin root>/lib/conformance_probe.py run --engine <e>` per dispatchable engine. The
probe has three legs — `resultProduction`, `completionDetection`, `progressTelemetry` — and
`preflight-entry` records the walked `engine-auth` check. The dispatch selftest
(`lib/dispatch_selftest.py`) is a config-time round-trip that never touches disk: it validates
**configuration, not engine liveness**, and green config checks can coexist undetected with a high
live-review failure rate. The canary strengthens what the `engine-auth` check must mean in a wave;
it does not add a check to the preflight list. The walk and the owner's launch-without word live in
`skills/showrunner/reference/dispatch-preflight.md`.

## Adoption mechanics

The recovery rules live in `rubric/launch-doctrine.md` § Recovery, and the charter keeps the
advisor's calls. Two of those calls have mechanics beyond the charter:

- **Pin** each builder's transcript by its issue token instead of re-discovering it newest-first.
- **Read liveness** from a double-confirmed process check plus pinned-transcript freshness — never
  from a `-p` session's buffered stdout, and never from a global process match.
