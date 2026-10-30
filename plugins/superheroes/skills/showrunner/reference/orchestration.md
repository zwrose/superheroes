# Contents

- [Orchestration — launcher, ledger, and wave mechanics](#orchestration--launcher-ledger-and-wave-mechanics)
- [What the harness does not carry](#what-the-harness-does-not-carry)
- [Batches and terminal outcomes](#batches-and-terminal-outcomes)
- [Reading `count`](#reading-count)
- [Amending a lane's record](#amending-a-lanes-record)
- [The ledger is version-coupled](#the-ledger-is-version-coupled)
- [The launcher provisions each build's worktree](#the-launcher-provisions-each-builds-worktree)
- [iPhone lanes: launching and reaping their phones](#iphone-lanes-launching-and-reaping-their-phones)
- [Liveness sweep and wave watch](#liveness-sweep-and-wave-watch)
- [Lapsed-pass parks and the send-back](#lapsed-pass-parks-and-the-send-back)
- [Acting on the builders' account](#acting-on-the-builders-account)
- [Adoption mechanics](#adoption-mechanics)

# Orchestration — launcher, ledger, and wave mechanics

This page is reference for the advisor running launches and waves. Duty 9 of the Showrunner charter
states the rules; this page holds the mechanics behind them. The authoritative semantics of every
verb named here live in `lib/launcher.py` and `lib/launch_ledger.py`.

## What the harness does not carry

**The orchestration that remains is yours because the harness does not carry it:** the
launcher's detached spawn of headless builders; arming the wave watch and re-arming it; reading
liveness from transcript freshness; the builder's turn-end rule for headless sessions; the
per-account config pin on every spawned session; the launcher-provisioned worktree per build; the
semantic heartbeat; the launch ledger; and the standing rulings block.

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
and a parked blocker inside a delivered PR, are friction the terminal tallies cannot see. A
NOT-READY goes back to a live original cloud builder, not to a new lane (§ Adoption mechanics).

**A second `record-outcome` on a lane that started and then ended with an outcome is recorded, not
refused.** A never-started lane is still refused with `outcome-without-started`. End one with
`launcher.py repair-lane --repo-root <root> --launch-id <id>`: with `--pending-file <file>` holding a
`started` record that fits the lane (a launch result's `pendingStarted`) it restores that record, and
without it, with `--evidence "<one line>"` and `--no-builder "<one line naming what you checked>"`, it
records the lane's terminal event from its `reserved` record. Terminal repair needs `--no-builder`
after you check the host's session listing (cloud) or the worktree (local): a dead launcher does not
prove no builder spawned, and without it the repair refuses `builder-may-exist` and names what to
check. It refuses a lane that already started (end that one with `record-outcome`) or already
ended. The second call lands as a `reoutcome` amendment and leaves the original terminal outcome
untouched. The CLI exits
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

**Before you reap a worktree or a branch**, list everything that still uses it: live lanes, open
PRs and stacks. Remove only paths on that list, one per call, each written out in full, never one a
glob or a variable resolves to.

**Cloud launch.** A launch can start the builder in a
[cloud session](../../../rubric/glossary.md#cloud-builder). On `launch`, `--place` is the owner's
launch word (`local` or `cloud`), and the launcher's routing step decides every launch's place; a
launch routed to the cloud takes its environment from the project's setup record, so `launch`
refuses `--cloud-environment` (`launch-cloud-environment-routed`). The routing step reads the premise's `needs` list (non-empty strings) as everything only the
owner's machine has, such as a locally seeded browser context for an authenticated wave; declare
each such dependency in `needs` before you launch, because a premise with none is free to be
placed in the cloud, where those resources do not reach. `compose` takes
`--place cloud --cloud-environment <id>` and `preflight` takes `--place`, as given. A cloud launch runs every gate a local launch runs:
preflight, premise, the stack and dependency gates, compose, and reservation. It then runs the
platform's command once, reads the session's identity from what the command prints, writes the
lane's `started` record, and returns once the session exists. It does not wait for the build.

- It provisions no worktree, leaves no process on the owner's machine, and pushes no branch.
- The session starts under the launching account's config dir, at the builder tier and effort the
  launch resolved.
- The launch prompt names the base commit, and the launch refuses unless that commit is on the
  remote, read fresh from the remote rather than from local tracking refs
  (`launch-cloud-base-not-on-remote`; `launch-cloud-base-remote-unchecked` when the remote could not
  be asked). The launcher checks it before it reserves the lane and again just before it runs the
  command. When the second check fails, the launcher starts
  nothing and ends the lane. A result whose reason begins `terminalization-failed:` means the launcher
  could not confirm it ended the lane. Read the ledger to see whether the lane is ended or still
  live before you reconcile it or launch the issue again. The launcher never pushes.
- The command cannot be told what to start from, and the platform starts the session from the
  checkout's commit. So the launch also refuses unless the checkout is on a branch whose local head
  and whose tip on the remote are both the base commit. `launch-cloud-checkout-unreadable` fires
  when the branch or the head cannot be read, a detached head included.
  `launch-cloud-checkout-off-base` fires when the local head, or the branch's tip on the remote,
  is not the base. `launch-cloud-checkout-branch-not-on-remote` fires when the remote has no such
  branch, and `launch-cloud-checkout-remote-unchecked` when the remote could not be asked for its
  tip. The refusal names the checkout, its branch, its head and the base, and the launcher never
  changes the checkout. These refusals never fall back to the owner's machine. The advisor tells the
  owner the checkout, branch and base, and launches again once the owner has put the checkout on the
  base and pushed it.
- The launcher runs the command from its checkout, which must be a folder the platform's command line
  already trusts. In an untrusted folder the command waits on its trust question until the launch's
  time limit, and the launch reads `cloud-session-unconfirmed`.
- The launch prompt is the composed order of a local launch, with the standing rulings verbatim, plus
  four lines between the issue pointer and the rulings: `Place: cloud session`,
  `Advisor plugin version: <version>`, `Cloud environment: <id>` and `Base commit: <sha>`.
- The session is named `issue-<issue number>-<the launch id without its launch- prefix>`. The host
  lists it under that name.
- These refuse before anything is written to the ledger, each with its own reason: a slot, a
  generation, or a boundary on a cloud launch (`launch-cloud-with-slot`; on `launch` they are held
  back as the local fallback's resources and never reach the cloud call); a premise asking
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
    asked for, because a time limit was reached, the command exited non-zero, its output names some
    other session, or the launcher was interrupted or told to stop while the command ran. In that
    last case the launcher ends the launch command and every process that command started on the
    owner's machine. A cloud session the command had already created keeps running. A session may
    exist. Ordinarily the lane has a `started` record that carries `cloudSessionUnconfirmed` in place
    of the id, so `record-outcome` works on it. The lane stays live, so the issue cannot be launched a
    second time. The steps to take are in **Cloud lanes** below. When that `started` record could not
    be written either, the result carries `startedAppend` and `pendingStarted`. A reported write
    failure does not prove the record is absent. Read the ledger before restoring `pendingStarted`.
    When the lane already has its `started` record, `record-outcome` works and nothing is restored.
    When the record is really absent, the lane is live on its `reserved` record alone and
    `record-outcome` refuses it (`outcome-without-started`). The advisor still looks in the host's
    session listing for a session of the name in `cloudSessionName`, which the result carries.
    Restore it with `launcher.py repair-lane --pending-file <a file holding pendingStarted>`, then
    record the outcome.
  - `cloud-started-append-failed`. A session exists and is working, and its `started` record could
    not be written. The result names the session (`cloudSessionId`, `cloudSessionName`) and why the
    write failed (`startedAppend`). The launcher tried the write three times. The result also carries
    `pendingStarted`, the complete `started` record, for a later repair. A reported write failure does
    not prove the record is absent. Read the ledger before restoring `pendingStarted`. When the lane
    already has its `started` record, `record-outcome` works and nothing is restored. When the record
    is really absent, the lane stays live on its `reserved` record alone, and `record-outcome` refuses
    it (`outcome-without-started`). Restore it with
    `launcher.py repair-lane --pending-file <a file holding pendingStarted>`. Keep the session's
    identity from the result and reach the session
    by it.

**Detective lanes.** A premise launches a detective lane with `"charter": "detective"` and a
`"budget"`, one line in time or usage terms. The prompt then starts with the detective command and
carries `Budget: <budget>` on the line after the issue pointer. Without a budget the launch refuses
`premise-detective-budget-missing` and composes nothing. The other refusals are `premise-charter-invalid`,
`premise-budget-invalid` and `premise-budget-without-detective`. The `reserved` record names the lane's
`charter`; older records carry none and read as workhorse. Declare-batch, preflight, `record-outcome`,
`amend` and the watch's ledger reads take a detective lane like any other lane. A detective lane's
place is called exactly as a builder's (`skills/showrunner/reference/dispatch-preflight.md` § The place
call). In the cloud its prompt carries the doctrine's detective cloud rule in place of the builder's
standing push permission, and the detective runs the cloud intake first
(`skills/detective/reference/cloud.md`). A `claude -p` session
started by hand with the detective command, the issue pointer and the budget is the fallback only for a
host or plugin version without this launcher support; disclose it on the issue as outside the ledger, never as the norm.

**Cloud lanes.** A [cloud lane](../../../rubric/glossary.md#cloud-lane) has no worktree: its
`reserved` record carries `place: "cloud"` and no `worktree`. Its `started` record names the session:
the name the host lists it under (`cloudSessionName`), its id (`cloudSessionId`) and its URL
(`cloudSessionUrl`). To reach a running cloud builder, message the session the lane record names. A
message wakes an idle session. A cloud builder asks the advisor through a builder note, an issue
comment opening with the builder-note header; the wave watch reports it as `builder-note`
(`skills/showrunner/reference/wave-watch.md`). Answer by message to the lane's session, then record
it answered with the watch's `note-answered` verb. A `started` record that carries `cloudSessionUnconfirmed` in place of
the id means a session may exist that was never confirmed. The lane stays live. Look in the host's
session listing for a session of the recorded name; when there is none, record the lane's outcome as
`died`. Before the first cloud lane enters a batch, every watch loop and sweep reading that ledger must run on a build that knows cloud lanes: an older build reads the lane as a local one and reports `builder-exited` for a session still working.

**A cloud-built stack layer.** A cloud builder does not link its stack; its build record lists
the link as owed. At its handback, before
the vet, link it from this machine with pull request numbers only when every planned layer from the
bottom through it has a pull request and that span holds at least two, since a stack needs two
(`rubric/native-stacks.md` § Each layer is a sub-issue, item 4). Otherwise the link stays owed (the
bottom layer handing back alone, or a lower planned layer with none yet): record it so in the vet
receipt, and make it at the handback of the lane that completes a span of two or more, linking the
whole span. Until then, run no membership check on it.
To link: `gh stack link <each member's pull request, bottom to top> <its pull request>`, which names
every member and then the new layer (for a first pair, the lower and then the upper pull request). An advisor in a cloud session links with
the REST create and add calls (`rubric/native-stacks.md` § How a stack comes to exist) instead.
Then run `python3 -B <plugin root>/lib/stack_check.py list --pr <its pull request> --repo <owner/name>`
and confirm every member, in order, with the layer at its planned position. Record that position in
the vet receipt; it stands in for the `stackEntry` quote the builder could not make. A link that
fails, or a position that disagrees with the plan, is a vet finding, never a pass.

## iPhone lanes: launching and reaping their phones

**Launching.** Put `"iphoneCheck": true` in the premise when the issue's done-definition names an
iPhone check (a check on a simulated iPhone, a phone the Mac imitates in software). Absent or false
means no phone. The launcher records `iphoneCheck` on the launch record and, when it made a phone,
the phone's ID as `iphoneId`. The premise names no place to check.

**Sizes.** Add `"iphoneModels"` beside `"iphoneCheck": true` when the issue names the sizes to check.
It is a non-empty list of distinct simulator device-type names, such as `"iPhone 17"` and
`"iPhone 17e"`. Without `"iphoneCheck": true`, or when it is not such a list, the premise is
invalid (`premise-iphone-models-invalid`). Before it makes anything, the launcher reads
`xcrun simctl list devicetypes -j` and maps each name to that inventory's identifier. A name the
inventory lacks refuses `iphone-model-unknown` (`unknownModels` lists it), and an unreadable
inventory refuses `iphone-models-unreadable`, both at stage `iphone-models`. A refusal leaves no
worktree, no phone and no child. Otherwise the launcher makes one phone per name, in order, named
`superheroes-<launchId>-<n>`. The record keeps `iphoneId` (the first phone) and adds `iphoneIds`
(every phone made). A create that fails is skipped, so that size has no phone. The builder gets
`SUPERHEROES_IPHONE_ID` (the first phone, or `none`) and `SUPERHEROES_IPHONE_IDS` (every phone,
comma-joined, the first being `SUPERHEROES_IPHONE_ID`), the second only when at least one phone was
made. Without `iphoneModels`, the launch makes one iPhone 17 as before.

The plugin's `iphone_allow.py` hook approves the pilot's plain `iphone_check.py` calls, so an iPhone
lane does not park on their permission prompt (Claude Code only).

**Reaping.** When the lane is finished (every launch for the issue has a terminal outcome
recorded), run
`python3 -B <plugin root>/lib/iphone_reap.py reap --repo-root <repo> --issue <n>`.
Record the outcome first: the reap refuses, deleting nothing, while any launch for the issue is
still live (`reap-lane-not-terminal:<launchId>`). It deletes every phone the lane's launch records
name, relaunched and failed launches included. A phone already gone reads `already-gone` and counts
as gone. The `phones` verb, with the same flags, lists them first (one `phones[]` entry per phone:
`phones[].launchId`, `phones[].iphoneId`, `liveLaunches`).

**What it never touches.** It deletes only the phones the lane's records name. `xcrun simctl delete`
removes a booted phone without shutting it down. The reap never quits Device Hub, never shuts down
or erases a phone, and leaves every other phone running. A phone a launcher crash left unrecorded
(named `superheroes-<launchId>`) is on no record, so the reap cannot find it. A person removes it by
hand.

**The reap record.** The reap writes one `evidence` amendment with value `reap` for each phone a
launch names: `reap: phone <udid> deleted | already gone | left running: <detail>`. That is where
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
A cloud lane's handback, stop or park reaches you as `lane-terminal` from its issue comments
(`wave-watch.md`), and `lane-stale` remains the fallback for a builder that posted none.
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

## Lapsed-pass parks and the send-back

A cloud build's PR is parked with the review not run when the reviewer pass lapsed mid-build. The
builder's park comment opens "Parked: the review did not run." `lib/cloud_parked.py` tells that park
from any other and keeps the record, in `cloud-parked.json` beside the launch ledger.

**Tell the owner.** Run `python3 -B <plugin root>/lib/cloud_parked.py notice --repo-root <root> --repo
<owner/name> --pr <n>` when a cloud lane ends parked, and whenever you read a cloud build's PR (a vet,
a sweep, a builder's comment) and see the park. Running it once records the PR; running it again is
harmless.

- `kind: lapsed-pass`: put `text` in your next message to the owner, as it is. It names the PR, the
  reason and the renewal.
- `kind: not-lapsed-pass`: a review that did not run for any other reason is reported as
  `rubric/review-discipline.md` says, with no advice to renew the pass.
- A lapsed pass still shows up in the launch report and the "Still on your machine" line
  (`skills/showrunner/reference/dispatch-preflight.md` § Where a build runs). The parked notice comes
  on top of them, never in place of them.

**Checks after an account's first setup need no `/remote-env` pick.** A renewal or a new check on an
account with a ready setup record names the record's environment, and `cloud_environment.py compare`
matches it without reading the picker, which several accounts on one machine share, and refuses any
other id. Ask for a pick only at an account's first setup or when the owner moves it to another
environment (`skills/configure/reference/set-up.md` § 6, "When the pick is needed").

**Send it back.** Run `python3 -B <plugin root>/lib/cloud_parked.py send-back --repo-root <root>`
after every `cloud_pass.py record-confirmation` that writes, after every passed setup check, and at
each gardening pass while any parked PR is still recorded. The pass command alone renews nothing:
until a cloud session confirms the new pass, `send-back` lists the PR under `notRenewed`. It marks
nothing sent, so a listed PR stays listed until `sent` records it.

For each item under `sendBack`, send `message` to the item's `cloudSessionName` as
`skills/showrunner/reference/wave-watch.md` § Answering a builder note sends an answer. On the same
account that is `SendMessage`. On another account (`configDir`) it is the relay's `ensure`,
`compose`, `SendMessage`, `check`. Then record it:

- After a direct `SendMessage` returns `success: true`, or the relay's `check` returns
  `delivered: true`, run `python3 -B <plugin root>/lib/cloud_parked.py sent --repo-root <root>
  --repo <owner/name> --pr <n> --park-id <the item's parkId>` (omit it when null). A second call is
  `unchanged`; `park-changed` means a newer park replaced it, so record nothing.
- After `relay-silent`, `relay-text-mismatch` or `relay-send-unconfirmed`, run `sent --uncertain`
  (not plain `sent`) with the same `--repo-root`, `--repo`, `--pr` and `--park-id`, and tell the owner. The builder
  may already hold the text, so never resend it automatically. `send-back` never lists the PR for
  sending again, but lists it under `uncertain` every time. A later plain `sent` with its `--park-id` records it.
- After an `ensure` refusal or `relay-send-failed`, do not run `sent`. Nothing reached the builder,
  and the PR stays listed for the next `send-back`.

No further word from the owner is needed for any of this. The message resumes the parked cloud
session, which runs its review and hands back as usual (`skills/workhorse/reference/cloud.md` § Review
has the builder's side).

**The other lists.**

- `skipped`: nothing to do. The PR closed before the renewal, or the owner already let it through.
- `noLane`: the PR has no cloud lane session to send to. Tell the owner which PR it is and that its
  review needs a fresh launch.
- `unread`: a read failed. Run `send-back` again later, and tell the owner if it keeps failing.
- `notRenewed`: wait for the confirmation.
- `uncertain`: a send-back whose delivery was never confirmed. Tell the owner which PR still waits on
  it and that it needs their word before any resend. A newer park comment re-arms it.

## Acting on the builders' account

The builders can run on a different Claude account from the advisor; the launch names it by its
config dir. A session on one account cannot read, message, stop or archive a session on another, so
**an action scoped to the builders' account goes through a session on that account**. Never hand
such a step to the owner first.

- **A message to a cloud session** goes through the relay, as
  `skills/showrunner/reference/wave-watch.md` § Answering a builder note sends one.
- **Archiving a finished cloud lane** is the cleanup in
  `skills/showrunner/reference/merge-train.md` § Cleaning up a finished cloud lane: the relay
  carries the archive request, and the builder archives its own session with the tool it has.
  Confirm the archive from the session list. Never assume it.
- **Reading or archiving a builders'-account session** goes to a one-off cloud helper session on
  that account. Start it as the launcher starts a cloud lane:

      CLAUDE_CONFIG_DIR=<the builders' config dir> claude --cloud "<prompt>" --settings '{"remote":{"defaultEnvironmentId":"<a cloud environment of that account>"}}' --model haiku --permission-mode auto --disallowedTools AskUserQuestion -n <name>

  That is the flag set `engine_adapter.claude_cloud_builder_argv` builds (`--cloud`, `--settings`,
  `--model`, `--permission-mode auto`, `--disallowedTools AskUserQuestion`, then `-n` last); the
  last two keep the unattended helper from stopping on a permission or question prompt. The command needs a pseudo-terminal, for example
  `script -q /dev/null …` on macOS. A cloud session's tools include `get_session`, `list_sessions`
  and `archive_session`; a background helper has none of them. The prompt names the session ids,
  asks for `get_session` on each, and asks the helper to post the raw results as one JSON array on
  the lane's issue in a fenced block, since a cloud session cannot message back. The advisor reads
  that comment through REST, saves the array to a file, and passes it with `--cloud-sessions-file`.
  The posted copy is the helper's transcription of its tool output. A row that clears a lane
  (archived or failed) counts only when a second helper read of that session, posted as its own
  comment, shows the same status, status bucket and archived values for it; on any
  disagreement, or with no second read, keep the unread refusal.
  A `list_sessions` page the helper posts is a transcription too, and a dropped row cannot be
  detected, so it never proves a session gone: a lane missing from a helper-posted page stays
  unproven and the advisor reads it with `get_session` (the two-read agreement rule then applies to
  the row that clears it). Only a complete page the advisor's own session read itself proves a
  session gone, and only when its rows carry `environment_id` and meet the checks in § Adoption
  mechanics; when they do not, read each lane with `get_session`. When a live lane never answers the fix order or the ask-to-push, the same
  helper archives it; an archive is reversible with `unarchive_session`. This is the advisor's own
  step: never hand a session read or this archive to the owner.
- **Anything else** (reading a background session's permission mode, messaging or stopping a
  background session) goes to a one-off background helper: a named background session started on
  that account for this one job. Reading a session's state and listing sessions are not in this
  list: they belong to the cloud helper above, so each read has one helper kind and one result
  channel.

**Starting the background helper.** Start it from the repository root, which that account already
trusts (a session started in a folder it does not trust stops at the trust prompt and never runs).
Pin that account's config dir, and run it on the small model:

    CLAUDE_CONFIG_DIR=<the builders' config dir> claude --bg -n <name> --model haiku --effort low "<prompt>"

Name it for its job, and put the account in the name, as the relay's name does.

**The background helper's prompt** names exactly the sessions it may act on and a never-touch list:
the relay, every live builder, and every session the job does not name. It says which action to
take on each (read the permission mode, message or stop), and that it never deletes a session. It
asks for one result line per named session, sent back to the advisor session by `SendMessage`. When
it cannot do a step, it lists its own tools instead.

When the background helper reports that it cannot do a step, hand that step to the owner, naming
the tools it listed. This covers only the background helper's steps; a session read or an archive
goes to the cloud helper and never to the owner. Deleting a session needs the owner's word every
time.

**What each kind of session can do.** A background helper has no tool that archives a session:
its CLI can stop, attach and delete sessions, but not archive one. A cloud session's own tools
can include one that archives a session by its id; a builder without one says so on its issue, as
the builder's cloud reference says. Confirm every archive from the session list, and
report one that is not confirmed as the cleanup's steps say.

## Adoption mechanics

The recovery rules live in `rubric/launch-doctrine.md` § Recovery, and the charter keeps the
advisor's calls. Six of those calls have mechanics beyond the charter:

Follow the doctrine rather than reconstructing a takeover from memory, which is exactly what this doctrine exists to stop.

- **Pin** each builder's transcript by its issue token instead of re-discovering it newest-first.
- **Read liveness** from a double-confirmed process check plus pinned-transcript freshness — never
  from a `-p` session's buffered stdout, and never from a global process match.
- **Recover a cloud lane** in exactly these steps, each naming a verb or record that exists. The
  verbs are `python3 -B <plugin root>/lib/cloud_recover.py <verb> --repo-root <root> …`.
  1. Read the session's state in the host's session listing, and the lane's activity age from the
     wave watch.
  2. Run `assess`. Its answer is `working`, `unresolved`, `parked`, `awaiting-handover`,
     `ask-to-push` or `stopped`. `working`, `unresolved`, `parked` and `awaiting-handover` never
     recover. `parked` means the lane's issue holds a builder stop or park comment newer than its last
     pushed work, and the answer names that comment (`parkComment`). An alive session that
     never hands over is resolved by the cloud helper archiving it (§ Acting on the builders'
     account), which then reads `archived`.
     On `parked`, act on the named comment as `wave-watch.md` says for a stop or a park (repair a
     stop; answer or route a park); never ask to push and never launch a successor.
  3. On `ask-to-push`, send `ask`'s text to the lane's session: on the same account with
     `SendMessage`, on another account through the relay, as an answer to a builder note is sent.
     Then run `asked`: with `--uncertain` after a relay delivery that was not confirmed, and not at
     all after a definite failure.
  4. On `stopped`, record the lane's outcome `died` with `record-outcome`, run `successor`, then
     launch that premise with `launcher.py launch`. The routing step places it: cloud when cloud is
     ready, the owner's machine otherwise. Until that launch starts, `assess` keeps answering `stopped`, so an
     interrupted recovery is rerun, never lost.
  5. Tell the owner with `message`'s text.

  The state is `cloud-recover.json`, beside the launch ledger. Recovery never leaves two builders on
  one issue: it recovers only on positive stop evidence or a confirmed handover; `successor` refuses
  a lane the ledger has not ended or that has no `stopped` assessment; `send-back` never messages a
  superseded lane; and the successor's intake refuses a branch that moved. A cloud lane that ended
  `refusal` because the cloud runs another plugin version is relaunched at once: run
  `cloud_recover.py relaunch-refusal`, then launch its premise with `launcher.py launch --place cloud`.
  The version the cloud reported stands as the cloud's, so the build runs on the owner's machine
  and the launch report names both versions.
- **Send a NOT-READY back to a live original builder.** A cloud builder can wake on PR activity
  after its handback is recorded, so a recorded handback does not mean no builder. Before launching
  a fix leg onto a cloud-built PR, read the original lane's session in the builders' account's
  session listing. When that session is still listed live, the fix order goes to it and no new lane
  launches: send the vet's NOT-READY findings as the fix order by message to the lane's
  `cloudSessionName` (`SendMessage` on the same account, the relay (`ensure`, `compose --fix-order`,
  `SendMessage`, `check`) on another), as `skills/showrunner/reference/wave-watch.md` § Answering a
  builder note sends an answer. Record the vet `not-ready` first (§ Amending a lane's record), then
  send: the wave watch opens the lane's window at the newest fix order, so a builder note or handback
  posted between the send and a later `not-ready` is not surfaced.
  The builder fixes, pushes and hands back as usual. Launch a new fix
  leg (a premise with `adoptsBranch`/`adoptsHead`) only when that session is archived, gone from the
  listing (shown by a complete listing, as below), its status bucket reads failed,
  or `cloud_recover.py assess` recorded it `stopped` on a handover. A lane whose builder refused at
  intake built nothing and is outside this rule. An alive session that never answers the fix order
  is resolved by the cloud helper archiving it (§ Acting on the builders' account), which then
  reads `archived`. The launcher enforces this: record the session read into a file and pass it
  with `launch --cloud-sessions-file <file>`. The session read comes from the cloud helper
  (§ Acting on the builders' account): one `get_session` result per lane, or an array of them. A
  `get_session` result works only for sessions it returns: it covers an archived or failed session
  it shows, but never a session that is gone. A `list_sessions` page can show a session gone only
  when it is one page read with no cursor and a limit that holds every session (`has_more: false`),
  its rows run newest-created first, and it holds a row of that lane's own cloud environment
  (`environment_id`) created at least 600 seconds after that lane started (the allowance covers
  clock skew between the two machines). When the rows carry no `environment_id`, the page proves
  nothing: read each lane with `get_session`.
  The check counts a lane only when it could still write the adopted branch: a lane bound to the
  adopted branch by its premise (it names the same branch, or the same pull request number), and
  any other lane unless it handed back before the branch's first pull request opened with no fix
  order since (no `vet not-ready` after the handback, and no fix order to its session).
  A handed-back lane had opened its own pull request before its handback, so a pull request on the
  adopted branch opened before then would itself be the branch's first; the lane's pull request was
  on another branch, and with no fix order since it writes only that branch. A bound lane whose
  branch is gone from the remote needs no session listing, but a listing you supply that shows its
  session live still refuses `adopt-original-session-live`: a deleted branch does not stop its
  builder. Every read the launcher makes for this fails closed:
  one that fails or is ambiguous keeps the lane in the check.
  `adopt-original-session-live` means a lane that could still write the branch has a session still
  listed live; `originalSessions` names each one, and the fix order goes to it.
  `adopt-original-session-unread` means the session read could not be used, or a read it needs
  failed, or it is not a complete page, so a missing session cannot count as gone; `failedRead`
  names the read and `launchIds` the lanes still unproven. A lane whose builder refused at
  intake, or that `assess` recorded `stopped` on a handover, needs no session read (a plain
  handback is not a handover and still needs one, unless it is excused as above). No step of this
  check goes to the owner: every refusal's `remedy` names a step the advisor runs itself.
- **Adopt a layer that is behind its base.** Bring the adopted branch current with its base
  first: merge the base in and push, so the premise keeps its base (the usual route, standing
  craft). If that is not possible for an unstacked or bottom-layer adoption, set the premise's
  `baseCommit` to the adopted head and launch with `--repo-root` set to a worktree on the adopted
  branch at that head, with the ledger root from the environment
  (`SUPERHEROES_LAUNCH_LEDGER_ROOT`). A layer above the bottom keeps the layer below's head as its
  base. The launcher refuses an `adoptsHead` that does not descend from `baseCommit`, or whose
  ancestry it cannot decide, with `premise-adopts-head-not-on-base` before anything is spent, and
  its `remedy` names the fix; the cloud intake's `adopted-head-not-on-base` stays as the second
  line.
- **Recover a stack in the cloud one layer per launch.** Give each layer its own adoption launch
  that adopts that layer's branch, bottom layer first, and bring each layer current with the layer
  below before its launch, as the bullet above says. Never have one cloud session work across
  several existing layer branches: its launch authorizes only its own branch, so the session's
  permission classifier refuses its merges and pushes on the others, even after the owner's
  go-ahead.
