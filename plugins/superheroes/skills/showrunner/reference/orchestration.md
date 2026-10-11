# Contents

- [Orchestration — launcher, ledger, and wave mechanics](#orchestration--launcher-ledger-and-wave-mechanics)
- [Batches and terminal outcomes](#batches-and-terminal-outcomes)
- [Reading `count`](#reading-count)
- [Amending a lane's record](#amending-a-lanes-record)
- [The ledger is version-coupled](#the-ledger-is-version-coupled)
- [The launcher provisions each build's worktree](#the-launcher-provisions-each-builds-worktree)
- [iPhone lanes: launching and reaping their phones](#iphone-lanes-launching-and-reaping-their-phones)
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

A [cloud lane](../../../rubric/glossary.md#cloud-lane) belongs to its batch like any lane and takes
the same four terminal outcomes. It has no child process to wait out, so `record-outcome` on a cloud
lane never refuses `terminal-child-live`, and `--await-exit` adds nothing.

## Reading `count`

**After a batch, run `count`** and read it honestly.

- **`indeterminate` means the record cannot see the whole batch** and must be resolved, not waved
  through.
- **A fully-resolved batch with zero parks and zero refusals is a signal to inspect**, never a clean
  sheet.
- **`count` reads lanes** — a build intent keyed by issue number, so retried attempts belong to one
  lane — with **`attempts`** beside the terminal tallies and **`laneDetail`** per lane. Overlapping
  same-lane launches still refuse.
- **`laneDetail` marks each lane's `place`**, `cloud` or `local`, and `lanes.cloud` is the number of
  cloud lanes.
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

**Cloud launch.** A launch can start the builder in a
[cloud session](../../../rubric/glossary.md#cloud-builder). `launch` and `compose` take
`--place cloud --cloud-environment <id>`, and `preflight` takes `--place`. Without `--place`, or with
`--place local`, the launch is a local launch. A cloud launch runs every gate a local launch runs:
preflight, premise, the stack and dependency gates, compose, and reservation. It then runs the
platform's command once, reads the session's identity from what the command prints, writes the
lane's `started` record, and returns once the session exists. It does not wait for the build.

- It provisions no worktree, leaves no process on the owner's machine, and pushes no branch.
- The session starts under the launching account's config dir, at the builder tier and effort the
  launch resolved.
- The session starts from the commit of the checkout the launcher ran in. When the checkout's
  remote-tracking branches hold no branch that contains that commit, the launch refuses with
  `launch-cloud-head-not-on-remote`. The launcher never pushes to make it so. The builder branches
  from the base its order names.
- The launcher runs the command from its checkout, which must be a folder the platform's command line
  already trusts. In an untrusted folder the command waits on its trust question until the launch's
  time limit, and the launch reads `cloud-session-unconfirmed`.
- The launch prompt is the composed order of a local launch, with the standing rulings verbatim, plus
  two lines between the issue pointer and the rulings: `Place: cloud session` and
  `Advisor plugin version: <version>`.
- The session is named `issue-<issue number>-<the launch id without its launch- prefix>`. The host
  lists it under that name.
- These refuse before anything is written to the ledger, each with its own reason: a slot, a
  generation, or a boundary given with `--place cloud` (`launch-cloud-with-slot`); a premise asking
  for the iPhone check (`launch-cloud-with-iphone-check`); an environment id that is not `env_`
  followed by letters and digits (`launch-cloud-environment-invalid`); an issue that is not a whole
  number above zero (`launch-cloud-issue-invalid`); a plugin version the launcher cannot read from
  its own manifest (`launch-cloud-plugin-version-unreadable`).
- When the command could not be started at all, the launch refuses and ends the lane, as a local
  launch does when it cannot spawn.
- Once the command has run, the launcher never ends the lane. The launch returns one of three
  results.
  - Success. The result and the lane's `started` record carry `cloudSessionName`, `cloudSessionId`,
    and, when the command printed one, `cloudSessionUrl`.
  - `cloud-session-unconfirmed`. The launcher could not read a creation receipt for the session it
    asked for, because a time limit was reached, the command exited non-zero, or its output names
    some other session. A session may exist. The lane has a `started` record that carries
    `cloudSessionUnconfirmed` in place of the id, so `record-outcome` works on it. The lane stays
    live, so the issue cannot be launched a second time. The steps to take are in **Cloud lanes**
    below.
  - `cloud-started-append-failed`. A session exists and is working, and its `started` record could
    not be written. The result names the session (`cloudSessionId`, `cloudSessionName`) and why the
    write failed (`startedAppend`). The lane stays live on its `reserved` record alone, and
    `record-outcome` refuses it (`outcome-without-started`). Keep the session's identity from the
    result and reach the session by it.

**Cloud lanes.** A [cloud lane](../../../rubric/glossary.md#cloud-lane) has no worktree: its
`reserved` record carries `place: "cloud"` and no `worktree`. Its `started` record names the session:
the name the host lists it under (`cloudSessionName`), its id (`cloudSessionId`) and its URL
(`cloudSessionUrl`). To reach a running cloud builder, message the session the lane record names. A
message wakes an idle session. A `started` record that carries `cloudSessionUnconfirmed` in place of
the id means a session may exist that was never confirmed. The lane stays live. Look in the host's
session listing for a session of the recorded name; when there is none, record the lane's outcome as
`died`. Before the first cloud lane enters a batch, every watch loop and sweep reading that ledger must run on a build that knows cloud lanes: an older build reads the lane as a local one and reports `builder-exited` for a session still working.

## iPhone lanes: launching and reaping their phones

**Launching.** Put `"iphoneCheck": true` in the premise when the issue's done-definition names an
iPhone check (a check on a simulated iPhone, a phone the Mac imitates in software). Absent or false
means no phone. The launcher records `iphoneCheck` on the launch record and, when it made a phone,
the phone's ID as `iphoneId`. The premise names no place to check.

**Reaping.** When the lane is finished (every launch for the issue has a terminal outcome
recorded), run
`python3 -B <plugin root>/lib/iphone_reap.py reap --repo-root <repo> --issue <n>`.
Record the outcome first: the reap refuses, deleting nothing, while any launch for the issue is
still live (`reap-lane-not-terminal:<launchId>`). It deletes every phone the lane's launch records
name, relaunched and failed launches included. A phone already gone reads `already-gone` and counts
as gone. The `phones` verb, with the same flags, lists them first (`phones[].launchId`,
`phones[].iphoneId`, `liveLaunches`).

**What it never touches.** It deletes only the phones the lane's records name. `xcrun simctl delete`
removes a booted phone without shutting it down. The reap never quits Device Hub, never shuts down
or erases a phone, and leaves every other phone running. A phone a launcher crash left unrecorded
(named `superheroes-<launchId>`) is on no record, so the reap cannot find it. A person removes it by
hand.

**The reap record.** The reap writes one `evidence` amendment with value `reap` on each launch that
names a phone: `reap: phone <udid> deleted | already gone | left running: <detail>`. That is where
the lane's outcome already lives. Its output lists `leftRunning`. It exits 0 only when every phone
is gone and recorded.

**When it is not clean.**

- For `leftRunning`, the phone stays recorded as left running. Name it in the lane's vet or
  close-out note.
- For `recordFailures` (the ledger refused an amendment), re-run the reap. It is safe, because
  deleted phones then read as already gone. If the ledger stays unwritable, post each phone ID and
  result on the lane's issue, and park.

## Liveness sweep and wave watch

**Scheduled liveness sweep.** An advisor orchestrating a wave owes a scheduled two-read sweep — not a
one-off rescue when something feels wrong.

- **Liveness:** run
  `python3 -B <plugin root>/lib/wave_watch.py run --repo-root <repo-root> --batch <id>` per live
  batch. `lane-stale` means the pid is live and the session transcript is quiet past
  `LIVENESS_QUIET_WINDOW_SECONDS`, or could not be resolved: investigate or resume. That is a local
  lane. A [cloud lane](../../../rubric/glossary.md#cloud-lane) has no pid and no transcript, so the
  watch reads its activity on GitHub instead (below).
- **Endings:** run `python3 -B <plugin root>/lib/heartbeat.py sweep --repo-root <repo-root>` and read
  the classes.
  - `terminal` on a launch the ledger still reports live is **actionable pending `record-outcome`**,
    never a resolved lane.
  - `unknown` means the signal could not be read. It is **actionable, not clean**.
  - `nonterminal` says nothing about liveness. A cloud lane reads `nonterminal` with reason
    `cloud-lane-no-heartbeat`, because it has no heartbeat.

The sweep **reports; it never asserts a lane is dead** — a heartbeat cannot prove death — and it
never resumes anything on its own. You act on what it reports.

**A cloud lane's liveness is its activity on GitHub**, not a pid, transcript, or heartbeat, and the
sweep reports it `nonterminal` for want of a heartbeat. The watch reads that activity and raises
`lane-stale` when it goes quiet; the procedure, and what to check before treating that as a wedge, is
in [Before treating `lane-stale` as a wedge](wave-watch.md#before-treating-lane-stale-as-a-wedge).
`canary` refuses a cloud lane with `canary-cloud-lane`, because a cloud lane has no local transcript
for it to read.

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
