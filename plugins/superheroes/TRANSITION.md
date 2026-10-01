# Transition notes

This file records consumer-visible shape changes across superheroes releases. Read it before you
upgrade a caller that invokes dispatch CLIs, reads dispatch results, or depends on a result key.

Add a section when a release drops, renames, or newly requires an argument, a result key, or a
result shape a consumer depends on. Put the newest release first. Each section names the release it
belongs to and lists every change with its replacement.

## Unreleased

### Claude write channel: implementers can run their own tests

- Sandboxed Claude implementers now run every command shape the sandbox confines. Before, python `-X` flags (including the pinned gate command `scripts/pinned-python -B -X pycache_prefix=… -m pytest …`), env-var prefixes such as `FOO=1 cmd`, and `; echo "exit=$?"` were refused with "This command requires approval", and implementers handed back untested work. The sandbox still denies the network, writes outside the build roots, and writes to the git hooks and config.
- Exception: on a host with managed Claude Code policy on disk (`managed-settings.json`, a non-empty `managed-settings.d`, or on macOS the managed-preferences plist), the channel keeps the old behaviour, and those shapes are still refused. Managed policy can exclude commands from the sandbox, and the channel never approves such a command unattended. The run-opened record gains `claudeWriteSandbox.managedPolicyPresent`. A run opened by 0.38.0 has no such field and continues with the old behaviour.
- The channel no longer leaves empty `.claude/.cc-writes` directories in the build worktree. They are swept when the run folds, and the folded result gains `ccWritesSweep`. A run that is abandoned rather than folded can still leave them.

### Claude write sandbox: four access options, offline by default

- The sandbox is still offline by default. A project without `sandboxAccess` sees byte-identical sandbox settings.
- A new top-level key, `sandboxAccess`, in `core.md`'s `superheroes-core` JSON block opens access. It has four optional fields: `allowedDomains` (a list of hostnames), `localPorts` (true or false), `localSockets` (true or false), and `extraWritePaths` (a list of absolute paths). A missing key, a missing field, or an absent `core.md` is all off. Set it through configure's view-and-tune; `configure_view.render` shows a `### Sandbox access` block.
- The run-opened record gains `claudeWriteSandbox.access`, the resolved values read once at open. Continuations and spawns reuse it, so a calibration edit does not change a running run. A run opened by 0.38.0 has no such field and continues as all off.
- Two new open-time refusals, each opening nothing: `engine-config:sandbox-access-malformed`, and `engine-config:sandbox-access-unreadable` for a `core.md` that exists but cannot be read, parsed, or resolved. An absent `core.md` is all off, not a refusal.
- Malformed values are refused when the calibration is read, each item naming its field, its reason, and the accepted shape. The reason tokens are `sandbox-access-not-an-object`, `sandbox-access-unknown-field` (a misspelled key is refused, never ignored), `sandbox-access-not-a-list`, `sandbox-access-domain-invalid`, `sandbox-access-not-a-bool`, `sandbox-access-path-not-absolute`, and `sandbox-access-path-is-root`.
- The profile schema version is unchanged, so an older plugin that re-calibrates from scratch can drop the `sandboxAccess` key.

## 0.38.0

### Before you upgrade

- **A project with no implementer setting now gets the sandboxed Claude implementer.** `enginePreferences.implementation` unset (or `claude`) now runs implementer orders through the sandboxed Claude write channel: no network, offline uv, `ps` blocked. Orders whose verification needs the network, uncached Python dependencies or `ps` fail or are refused up front. To use another engine, set `implementation` to `cursor` or `codex` before upgrading.
- **Rename `sonnet-5` pins to `sonnet-5.5`.** A pin or config naming `sonnet-5` is refused as unregistered.
- **Finish or abandon in-flight claude write runs first.** A claude write run opened by an older plugin, or one journaled under `sonnet-5`, cannot be continued; open a fresh dispatch.

### Wave watch: a missing launch ledger refuses

- An arm against a resolved ledger root whose ledger file does not exist now refuses `ledger-unreadable` instead of returning a clean `timer`. A ledger file that exists but holds no records stays clean.
- Every `ledger-unreadable` refusal from `run`, `watch_arm` and `loop` now carries `ledgerPath`, the path the watcher read.

### Claude write channel: a sandboxed shell

- The claude write argv is now `claude -p --model <tok> --effort <effort> --output-format stream-json --verbose --permission-mode acceptEdits --restricted --tools Bash,Edit,Write,Read,Grep,Glob --strict-mcp-config --settings <inline JSON>`, then `--json-schema` at run-open. It replaces the edit-only argv with no shell. The review argv is unchanged.
- The run-opened record gains `claudeWriteSandbox`, the writable roots resolved once at open. Read it there; continuations and spawns reuse it.
- Four new refusals: `engine-config:sandbox-roots-missing`, `engine-config:sandbox-roots-unresolvable`, `engine-config:sandbox-uv-cache-unresolvable`, and `engine-config:sandbox-process-listing-unavailable`. The two `-unresolvable` refusals open nothing.
- `dispatch-write` gains `--requires-process-listing`. Pass it when the order's verification lists processes; a claude write then refuses `engine-config:sandbox-process-listing-unavailable` before any run opens. Codex and cursor ignore it.
- A claude write run opened by an older plugin cannot be continued: it refuses `engine-config:sandbox-roots-missing`. Open a fresh dispatch.
- Sandbox limits: the network is off, uv runs offline (`UV_OFFLINE=1`, so dependencies must already be in the uv cache), `ps` is blocked, and the sandbox's per-user temp dir stays writable (`/tmp/claude-<uid>`), where other Claude sessions' scratch can live.

### Registry: the sonnet row is sonnet-5.5

- The registry id `sonnet-5` is now `sonnet-5.5`, and the alias record reads `sonnet → claude-sonnet-5-5` (harness 2.1.284).
- A pin or config naming `sonnet-5` is refused as unregistered. Name `sonnet-5.5`.
- A run journaled under `sonnet-5` is refused at continuation (`run-dir-seat-mismatch`). Open a fresh dispatch, the same rule the earlier `opus-5` to `opus-5.5` rename followed.
- The `sonnet` dispatch token is unchanged.

### Implementer routing: claude means the sandboxed channel

- `enginePreferences.implementation: claude`, which is also the default when it is unset, now sends implementer orders through `dispatch-write --engine claude`, the sandboxed channel. Before, `claude` meant a native Claude subagent.
- What changes for an unconfigured project: implementers move from native subagents with network access to a sandboxed Claude CLI with no network, offline uv, and `ps` blocked, and every order now leaves a runner journal and `--expect-item` grading.
- To keep cursor or codex as the implementer, set `implementation` to that engine; nothing else changes for those projects.
- `seat_map compose --implementation-engine claude` now reads author family `anthropic` whatever the host model; before, it took the host's family.
- On a known non-Claude host with a claude implementer, the host's family is also excluded from the lens and grounding seats, because review-code's native fixer writes as the host family (degradation `maker-family-split`; `secondary-maker-seated` when no other family is live). Two known limits ship open, owner-accepted: the diversity check still counts the excluded host family as available, so a correct single-family panel is flagged `critical-diversity` (F1); and certification does not refuse a `secondary-maker-seated` seat (F2). Claude hosts are unaffected.

## 0.37.0

### Before you upgrade

- **Update the Codex CLI to 0.159.0 or later.** The codex default is now `gpt-6.1-sol` (GPT-6.1
  Sol) in every codex seat, at each seat's existing effort. An older CLI is refused at preflight
  with `codex-cli-too-old`, before any codex seat runs; Codex CLI 0.158.0 and older cannot dispatch
  `gpt-6.1-sol` under a ChatGPT account.
- **A `gpt-6-sol` pin keeps working.** `gpt-6-sol` is now pin-only, like `gpt-5.6-sol`: a pin runs
  it at the pinned role's own effort, and no default names it. A `gpt-5.6-terra` pin is still
  refused, and the refusal now names `gpt-6.1-sol` as the replacement.

### Control probe: plant detection

- The planted-defect control probe counts a Critical finding on the planted file at a line inside the planted hunk as catching the plant, alongside a finding that names `verify_submission`; a finding on another file, outside the hunk, or below Critical does not count.

### Engine dispatch: result rewrites, dirtied paths, attempt telemetry

- A native result file rewritten with different valid content before the deadline is now admitted. The completion stamp follows the latest content observed at or before the deadline. Content first seen after the deadline still forfeits `result-completion-payload-mismatch`.
- A `worktree-dirtied-by-attempt` forfeit now carries `dirtiedPaths`: `status`, `paths`, `headMoved` and `truncated`, or `status: indeterminate` with a `reason`. It lists paths whose git status changed plus paths the attempt committed. An edit to a file already dirty at open whose status did not change is not listed.
- Every `attempt-ended` journal record now carries `hostLoadAtOpen`, `hostLoadAtEnd` (1/5/15-minute load, or `null`) and `commandTime` (cursor stream tool and shell seconds, or `null`), and `engine-started` carries `hostLoadAtOpen`. The 900 s default timeout is unchanged.

### Size counter: test-support directories

- The size counter (`lib/size_count.py`) now treats files under a `test-utils`, `test_utils`, `testutils`, `test-helpers`, `test_helpers` or `test-support` directory (any case) as test code, so hand-written test doubles there no longer count toward the non-test size.

## 0.36.0

### Cursor dash-free native result handoff

- Cursor attempts whose canonical native result path contains a run of two or more dashes (`--`)
  now name a dash-free symlink path to that file in the prompt's result line (the bytes still land
  in the run directory at the canonical path).
- The `engine-started` journal record may carry `nativeResultHandoffPath` alongside
  `nativeResultPath` when that handoff is used.
- A new pre-spawn refusal token `native-result-path-unsafe` may appear on cursor attempts when the
  runner cannot create a safe handoff path.
- A killed or interrupted attempt can leave a dangling `superheroes-result-*` symlink in the temp
  directory; deleting it is safe.

## 0.35.1

### Claude background dispatch mode retired

Upgrading from 0.35.0 changes how claude dispatch modes work:

- **Print is the only claude dispatch mode.** Omit `--claude-mode` or pass `--claude-mode print`.
  `--claude-mode` still accepts the retired value `background` only so callers receive a named
  refusal: on `dispatch-review` and `dispatch-write` it refuses before anything spawns with
  `entryReason: claude-mode-retired`, `detail: claude-mode-retired:background`, `attempts: 0` —
  it never falls back to print.
- **Continuing a run opened in background mode is refused.** Re-invoking either dispatch verb on a
  run directory whose journal was opened with `claudeMode: background` refuses with
  `detail: run-dir-claude-mode-retired`, `attempts: 0`; nothing re-opens or spawns.
- **The conformance probe probes only print for claude** (`probedModes: ["print"]`).

Removed with no replacement — print mode has none of them:

- The `claude --bg` launch path and transcript-based result delivery.
- Session suspend, re-attach, and stop-and-confirm of background sessions.
- The `claude-mode-background-write` refusal and the seven `background-*` attempt refusals
  (`lib/background_outcome.py` is deleted).
- Result and journal fields `bgStop`, `backgroundStopUnconfirmed`, `transcriptResult`, and
  `transcriptToolCalls`.
- `dispatch-abandon` stopping a claude session (the runner no longer stops detached background
  sessions).

#### Before you upgrade

- **Re-run the conformance probe for claude into a fresh run directory after upgrading.** A saved
  0.35.0 claude probe result that lists both modes is refused by the preflight entry as
  `probe-result-malformed:<path>`; a caller-supplied probe run directory that still holds a
  `background/` subdirectory refuses `run-dir-not-empty-unopened`.
- **Run operator cleanup once for any detached background session a 0.35.0 run may have left.**
  List sessions with `claude agents --json` (per `CLAUDE_CONFIG_DIR`), and stop any row of kind
  `background` whose cwd is a dispatch sanitized view with `claude stop <id>`. The runner no longer
  does this.
- **Fold any run directory that 0.35.0 opened in background mode.** Run
  `dispatch-abandon --run-dir <dir>` once on each such directory. Until you do,
  `dispatch-poll` still reports the run as running, because a continuation now refuses without
  closing it.

## 0.35.0

### Before you upgrade

Check these in a consuming project before it takes 0.35.0:

- **Read liveness from the watcher, not the heartbeat sweep.** `heartbeat.py sweep` now classes a
  record as `terminal`, `nonterminal`, or `unknown`; the old fresh and stale classes are gone, and
  a script matching them must be updated. See [Heartbeat sweep classes](#heartbeat-sweep-classes).
- **Update a script that matches an `astra-probe-*` refusal token.** The registration probe's
  refusal tokens are now `registration-probe-*`, with no alias. See
  [Registration probe tokens](#registration-probe-tokens).
- **An adoption launch passes `adopts` to re-occupy its own stack position.** Without it the launch
  still refuses `layer-position-occupied`; four new refusal tokens come with it. See
  [Launcher adoption premise](#launcher-adoption-premise).
- **Accept `survivingNonBlocking` in a v5 certification receipt, and never hand-edit
  `rulingsLog`.** The certification loop ships through its rulings channel with one disclosed
  fail-open on a malformed `rulingsLog`. See
  [Certification receipt and the rulings channel](#certification-receipt-and-the-rulings-channel).
- **Accept vet receipt spine fields 9 and 10 in a template or reader of your own.** Every vet
  receipt now carries **Lane** and **Misses-log appends**. See
  [Vet receipt spine fields 9 and 10](#vet-receipt-spine-fields-9-and-10).

### Heartbeat sweep classes

`heartbeat.py sweep` classes each record as `terminal` (the builder stamped `parked` or
`handback`), `nonterminal` (a valid record whose state is not terminal — it says nothing about
liveness), or `unknown`. The old fresh and stale classes are removed, because a builder no longer
promises a stamp cadence: `stamp` still accepts its old cadence argument from older callers and
ignores it, and the window a stamped record carries is always `LIVENESS_QUIET_WINDOW_SECONDS`
(2700 seconds). Liveness has one signal: `wave_watch.py` raises `lane-stale` when a lane's process
is live and the watcher cannot establish that its own session transcript was written within that
window. A cold transcript alerts, and so does an ambiguous or unreadable lookup; a transcript that
does not exist yet alerts only once the same window has passed since the lane's recorded start. The
event means no fresh transcript could be established, not proof of inactivity. A consumer that matched
the old fresh or stale class from the sweep must match `nonterminal` for an unended lane and take
liveness from `lane-stale`.

### Registration probe tokens

One entry changes on the surface listed under
[Astra and the codex role pin](#astra-and-the-codex-role-pin):

- `conformance_probe registration-probe` (`astra-probe` still works as a legacy alias of the verb;
  refusal token `registration-probe-wave-already-attempted` when the same wave is re-attempted with
  a different run dir). The probe's refusal tokens were renamed from `astra-probe-*` to
  `registration-probe-*` with no alias: `registration-probe-scale-unreadable`,
  `registration-probe-ledger-unreadable`, `registration-probe-record-write-failed`,
  `registration-probe-wave-already-attempted`, `registration-probe-seat-unresolved`, and
  `registration-probe-claim-unreadable`. A script that matches an old `astra-probe-*` refusal token
  must be updated.

### Launcher adoption premise

A stacked premise (see [Launcher stacked premise](#launcher-stacked-premise)) may now carry
`adopts`: the pull request number of the existing member an adoption takes over at its own
`layerPosition`. `validate_premise` copies it into the stamped premise like every other key.

`launcher.py launch` narrows one refusal and adds four tokens: `layer-position-occupied` when the
claimed `layerPosition` is already held by an existing member (`layerPosition >= 2` only) and the
premise's `adopts` does not name that member on the layer below's branch; `adopts-occupant-missing`
when `adopts` names a pull request but the claimed position is empty;
`premise-adopts-without-stack`, `premise-adopts-invalid`, and `premise-adopts-bottom-layer` when
`adopts` lacks the stack pair, is not a positive integer, or is on the bottom layer.

### Certification receipt and the rulings channel

On success, `certification-receipt.json` (see
[Certification receipt artifact](#certification-receipt-artifact)) carries the `disclosures` block
with `importantOutOfScope` for Important out-of-scope deferrals and, for a session at state schema
v5, `survivingNonBlocking` for surviving Minor or Nit findings without disposition. A receipt from
an earlier schema (v2–v4, still supported) omits `survivingNonBlocking`. A consumer that enumerates
the block's keys strictly must accept the new one when present.

The certification loop ships through layer 4d-2, where rulings reach the round driver as a declared
input through `round_driver.py rule`. One fail-open ships disclosed: when a session's `rulingsLog`
is malformed, the driver reads it as empty, so an out-of-scope ruling does not hold and its finding
can reach the fixer. Only corrupted or hand-edited state reaches it — `rule` itself refuses
`rulings-log-malformed` rather than write to a malformed log. Record rulings through `rule`; never
edit `rulingsLog` by hand.

### The covenant's merge wording

`rubric/covenant.md` keeps its rule and drops its restatement: promise 1 and the first hard line now
say that nothing merges, releases, publishes, or force-pushes without the owner's word, and point
to `skills/showrunner/SKILL.md` duty 6 as the merge policy's one full statement. Every Claude Code
session on a calibrated project gets the new text from the installed plugin through the
SessionStart bootstrap, so nothing is refreshed by hand there. `configure`'s durable `CLAUDE.md`
offer writes the review-discipline section, not the covenant, and that section's source changed by
one pointer line; a project that took it needs no action. A project that pasted the covenant into
its own `CLAUDE.md` by hand (the only carrier on Codex) holds the longer old wording, which states
the same rule; replacing it with the new `rubric/covenant.md` is optional.

### Skill descriptions as pointers

The skill descriptions are shortened toward when-to-load pointers: each leads with when the skill
applies, and most of the mechanism moves to the skill body, though some descriptions still
summarize what the skill does. No skill name, command, or
`user-invocable` flag changed, so a consuming project has nothing to update.

### Charters as maps

The workhorse, showrunner, and detective charters keep their sections and duties, and much of
their mechanism, including the workhorse and detective excuse tables, moves to reference pages the session reads on demand: `skills/workhorse/reference/`
gains `intake.md`, `orders.md`, `handback.md`, and `excuses.md`; `skills/showrunner/reference/`
gains `routing.md`, `vetting.md`, `orchestration.md`, `provisioning.md`, and `excuses.md`;
`skills/detective/reference/` gains `excuses.md`. Nothing was removed or renamed, and no command or
path a consuming project calls changed. This is informational.

### Vet receipt spine fields 9 and 10

The vet receipt's always-present spine (`skills/showrunner/reference/vet-receipt.md`) grows from
eight fields to ten. Field 9, **Lane**, records the lane the PR ran (`full`, `light`, or `micro`),
with a note when the build escalated. Field 10, **Misses-log appends**, records each misses-log
append the vet made and its class, or `None`. Like every spine field, each is filled or written as
`None`. An advisor session reads the new shape from the installed plugin. A project whose own
template, script, or reader expects exactly eight spine fields must add or accept the two new ones.

## 0.34.0

### Before you upgrade

Check these in a consuming project before it takes 0.34.0:

- **Update the Codex CLI to 0.157.0 or later.** The codex default is now `gpt-6-sol`, and the
  preflight otherwise refuses `codex-cli-too-old`. See
  [Astra and the codex role pin](#astra-and-the-codex-role-pin).
- **Move a `gpt-5.6-terra` pin to `gpt-6-sol`.** A pin or config naming `gpt-5.6-terra` now refuses
  `model-retired`; `gpt-5.6-sol` stays a valid pin. See
  [Astra and the codex role pin](#astra-and-the-codex-role-pin).
- **The owner-authority gate is retired.** Merges run on the owner's scoped word under the merge
  covenant; the hook no longer asks. See [Owner-authority gate retired](#owner-authority-gate-retired).
- **Dispatch CLIs take `--seat` as four-key JSON.** The old `--engine`, `--model`, `--effort`,
  `--engine-model`, `--vendor` and `--role` flags refuse. See
  [Dispatch CLI arguments](#dispatch-cli-arguments).

### Launcher stacked premise

`validate_premise` copies every premise key into the stamped premise. A premise may now carry
`stack` (the GitHub native stack's number), `layerPosition` (this PR's 1-based position in that
stack), optionally `layersPlanned` (the stack's planned layer count), and optionally `dependency`
(the pull request number of an open dependency whose READY vet the launch must be based on).
`stack` and `layerPosition` are optional together — one without the other refuses; `layersPlanned`
requires both.

A stacked launch's stamped premise carries `stack` and `layerPosition`, and `layersPlanned` only
when the launch supplied it — keys a pre-existing consumer never saw; strict key enumeration or
fixed-schema round-trips must accept up to three new stack-metadata keys (`stack`, `layerPosition`,
`layersPlanned`); a launch that also names a `dependency` may add a fourth. A launch that names a
`dependency` carries that key in the stamped premise. A non-stacked launch without a dependency is
unchanged.

A successful launch that ran the dependency gate carries `dependencyGate` on its result. Two
variants: when the gate did not apply, `applied` is `false` and `reason` names why (`dependency-not-open`
for a merged dependency, `dependency-not-ready` for an open draft dependency, before the vet is read
at all however that dependency's slot reads, or for an open dependency whose vet is not READY); a
closed, unmerged dependency refuses the launch with `dependency-closed-unmerged` and carries no
`dependencyGate`. When the gate applied, `applied` is `true` and the object carries `dependency`,
`dependencyHead`, and `verdict` with no `reason` field.

`launcher.py launch` adds thirteen refusal tokens (see `lib/launcher.py`; rule in
`rubric/launch-doctrine.md`): `premise-stack-fields-incomplete` when only one of `stack` or
`layerPosition` is supplied; `premise-stack-field-invalid` when either key is present but not a
positive integer (`bool` is not an integer here); `premise-stack-layers-planned-incomplete` when
`layersPlanned` is supplied and **both** `stack` and `layerPosition` are absent — the pair check runs
first, so when exactly one of the pair is present, with or without `layersPlanned`,
`premise-stack-fields-incomplete` refuses first;
`premise-stack-layers-planned-invalid` when `layersPlanned` is present but not a positive integer
(`bool` is not an integer here); `premise-stack-layers-planned-under-position` when `layersPlanned`
is less than `layerPosition`; `base-not-layer-head` when `layerPosition >= 2` and the resolved base
commit is not the current head of the stack member at position `layerPosition - 1`;
`stack-read-unavailable` when the launcher could not read stack membership and the gate could not
run — the launcher's own token, distinct from `stack_check.py`'s `stack-unreadable` (never aliases,
never interchanged); `order-mismatch` when the membership read found the stack's order inconsistent
with the premise (previously folded into `stack-read-unavailable`, so a consumer matching on
`stack-read-unavailable` for this case must now also match `order-mismatch`);
`layer-position-occupied` when the claimed `layerPosition` is already held by an existing member
(`layerPosition >= 2` only); `premise-dependency-invalid` when `dependency` is present but not a
positive integer (`bool` is not an integer here); `dependency-closed-unmerged` when the premise
names a closed, unmerged dependency pull request; `dependency-open-ready-pr` when the premise
names an open dependency pull request with a READY vet and the resolved base commit is not that pull
request's current head; `dependency-read-unavailable` when the launcher could not read the
dependency pull request or its vet and the gate could not run.

### `launch_ledger.fold` lane stack keys

`fold` puts three keys on **every** lane record — `stack`, `layerPosition` and `layersPlanned` —
derived from that launch's stamped premise, so a strict key enumeration over a lane record must
accept them rather than refuse. The value is `None` when the premise is absent, omits the key, or
carries a value that is not a positive integer (`bool` is not an integer here): a non-positive or
non-integer premise value folds to `None` rather than refusing the fold. The documented signal is
**`None`, never a missing key** — a pre-stack record and a malformed premise read alike.

### `wave_watch.py` `pr-set-changed` payload

The `pr-set-changed` event payload gains `stacks` and `ungrouped`. `stack-signal-unavailable`
joins the degradation set. The existing `prs`, `prsAdded`, and `prsRemoved` keys are unchanged, so
a strict key enumeration must accept the two new ones.

### `wave_watch.py` `stack-state-changed` event

`wave_watch.py` gains a new event, `stack-state-changed`, at precedence rank four — immediately
above `pr-set-changed` and below `builder-exited`. Its payload carries `stacks` (one entry per
stack the batch's launches name, each with `stack`, `state`, `layersPlanned`, `missingPositions`,
and `reason`) and `flags` (today only the idle-seat flag — `FLAG_IDLE_SEAT_LAUNCHABLE_CHILD` in
`lib/wave_watch.py` — naming `stack`, `position`, and `flag`). The event is not suppressible per
lane through `--ignore-event`; naming it refuses `ignore-event-invalid`. Within one `loop`
invocation the stack-state baseline threads across timer arms, so a stack that becomes complete
between arms is reported once; each new invocation starts without one, so a watch armed on a batch
whose stack is already complete, or that already carries the idle-seat flag
(`FLAG_IDLE_SEAT_LAUNCHABLE_CHILD` in `lib/wave_watch.py`), reports `stack-state-changed` on its
first arm.

### `wave_watch.py` loop and run

`run` drops `--max-seconds` and `--interval-seconds` (and the Python `run()` loses `max_seconds`,
`interval_seconds`, and `sleep`; the old windowed function is `watch_arm()`). `run` returns at once
— one ledger read and at most one open-PR read, no waiting. `loop` no longer returns on
`pr-set-changed` or `stack-state-changed`; those are benign wakes passed over and reported at exit.
Every `loop` result gains `passedOver` and `passedOverCount`; a `loop-already-live` refusal gains
`liveLoop`. New refusal tokens: `loop-already-live` and `loop-lock-unavailable`.

### Launcher premise `dependency` field

`validate_premise` accepts an optional `dependency` field on the premise — a positive integer pull
request number, independent of the stack fields. When `dependency` is present but not a positive
integer (`bool` is not an integer here), validation refuses `premise-dependency-invalid`. A stamped
premise carries `dependency` only when the launch supplied a valid one.

### Launcher dependency gate refusals

`launcher.py launch` adds two refusal tokens when the premise names a `dependency` and the
dependency gate runs: `dependency-open-ready-pr` when the dependency is an open pull request
carrying a READY vet and the resolved base commit is not that pull request's current head; and
`dependency-read-unavailable` when the dependency pull request, its head, or its vet could not be
read so the gate could not run.

### `register_check.py check`

`register_check check` gains `--register-copy {auto,main,worktree}`. Two new result keys —
`registerCopy` and `registerRef` — are present on **every** result, including every `undecided`.
The default changed: inside a git work tree the register is now read from main's copy
(`origin/main`, else `main`) rather than the file on disk, and a main read that cannot be resolved
is `undecided` / `register-unreadable` rather than a silent fallback to the worktree copy. A caller
that wants the old behaviour passes `--register-copy worktree`.

### Dispatch-shell exit codes

A dispatch-shell command-line entry point exits **1** when it refuses (returns without doing the
work it was asked to do), **0** otherwise; argparse's own argument errors remain exit **2**. Exit
**0** still never means success — the JSON `ok`/`terminal` fields stay authoritative.

**Consumer-visible change:** `dispatch-review` / `dispatch-write` refusals now exit **1** where they
previously exited **0**. A successful `dispatch-poll` / `dispatch-abandon` still exits **0** even
when its JSON carries `reason: unrunnable` (for example after abandon). `dispatch_guard check` and
`engine_adapter build-argv` exit-code behavior is unchanged from the C10 correction documented
below.

### Command-line Claude result channel

Command-line **claude** is now dispatchable through the shell — `dispatch-review` / `dispatch-write`
with `{"vendor":"claude", …}` no longer refuse `undispatchable-vendor`. A consumer that treated
claude as undispatchable must route it through the sanctioned verbs like codex and cursor.

The argv is `claude -p --model <tok> --effort <effort> --output-format stream-json --verbose`,
plus `--restricted` for the review role or `--permission-mode acceptEdits --restricted` for
the write role, with `--json-schema
<declared schema JSON>` appended at run-open; the prompt arrives on stdin. A claude write dispatch
is edit-only inside the run cwd because no OS sandbox is available through this CLI, so an order
needing to run commands does not route to claude today. `<tok>` is the registry's claude dispatch
token (`haiku`, `sonnet`, `opus`); `fable` refuses `fable-unrunnable`.

The typed result is the `structured_output` member of the **last** `{"type":"result"}` event on
stdout — the final response `--json-schema` governs. That same observation records
`resultCompleteAt`, `resultCompleteEpoch`, and `resultCompleteSha256` on the attempt-ended record
before the process is terminated. The runner **materializes** it to
`<run-dir>/native-result-<n>.json` at attempt end; `attempt-ended.stdoutResult` records
`materialized`, `absent`, `error`, or `occupied`. Only a `materialized` attempt is loaded;
`occupied` forfeits `native-result-path-occupied`; `absent` (no `result` event, `is_error: true`,
or no `structured_output`) and `error` forfeit `native-result-missing`. Admission then runs the
engine-neutral native path unchanged (declared schema, scrub, the `native-result-*` forfeits).
`--output-format json` prints the identical envelope object once at exit; `stream-json --verbose`
prints `assistant` events carrying `tool_use` blocks and then that same envelope as the last line.

Telemetry uses `engagement.source: "claude-stream"`, `telemetry: "tool-calls"`; tool calls are counted
by distinct `tool_use` block id across `assistant` events, **excluding** the `StructuredOutput` call
(it is the result, not activity).

At run-open the shell resolves the target `CLAUDE_CONFIG_DIR` through `lib/config_dir.resolve(env,
cwd)` and records it as `run-opened.configDir`; a value that is not an existing directory refuses at
open with `config-dir-unusable:<why>` (`attempts: 0`). At spawn the same value is injected into the
child env together with `CLAUDE_CODE_EFFORT_LEVEL=<seat effort>`, and `engine-started.env` records
both pins.

Two dispatch modes via `--claude-mode {print,background}` (default `print`). **Print** delivers
through stdout: the runner materializes the last `{"type":"result"}` envelope's
`structured_output` to `<run-dir>/native-result-<n>.json`. **Background** delivers through the
session transcript on `dispatch-review` only — a write dispatch in background mode refuses
`claude-mode-background-write` before spawn; a continuation with a disagreeing mode refuses
`run-dir-claude-mode-mismatch`. Background attempt outcomes can carry
the refusal tokens in `lib/background_outcome.py` (`ALL_REFUSALS`).
Background telemetry is read from the session
transcript's tool calls, not from stdout.

Refusal tokens a consumer can meet on claude: `config-dir-unusable:<why>`,
`claude-mode-background-write`, `run-dir-claude-mode-mismatch`, the background attempt refusals
above, plus the shared native family `native-result-missing`, `native-result-oversized`,
`native-result-malformed`, `native-result-schema-invalid`, `native-result-report-blank`,
`native-result-path-occupied`, `result-completion-unrecorded`, `result-completion-after-deadline`,
`result-completion-payload-mismatch`, `timeout-deadline-unrecorded`, `native-schema-unreadable`,
`marker-channel-retired`; the adapter
refusals `unregistered-engine-model`, `fable-unrunnable`, `invalid-model-effort`, `untokenizable`.

### Builder launch

Builders stay on `claude -p`. The launcher builds the builder command through
`engine_adapter.claude_builder_argv(token, session_id, prompt)` — the one home for every claude
command — whose argv is unchanged (`claude --model <tok> --session-id <uuid> -p <prompt>`; effort
remains pinned through `CLAUDE_CODE_EFFORT_LEVEL`). A caller of `claude_builder_argv` meets the
signature without `effort` or `--bg` and the refusal `builder-session-id-invalid`.

`launcher.py canary --repo-root <r> --launch-id <id>` reports whether a builder lane is engaged from
tool calls in that lane's own session transcript. On success the JSON carries `ok`, `reason` (null),
`launchId`, `sessionId`, `configDir`, `transcriptPath`, `toolCalls`, `truncated`, and `engaged`.
Refusal tokens: `canary-ledger-unreadable:<state>`, `canary-ledger-fold-refused:<reason>`,
`canary-lane-unknown`, `canary-session-id-absent`, `canary-config-dir-absent`,
`canary-transcript-missing`, `canary-transcript-ambiguous`, `canary-transcript-unreadable`,
`canary-transcript-truncated`. A running builder is steered by a message to its registered session
name. Background mode remains a review-seat mode only (`--claude-mode background`).

### Astra and the codex role pin

`gpt-6-astra` is registered as the codex top rung and a valid `reviewer-deep` pin at effort `high`.
A consumer meets:

- the `registration-probe` role the registration probe dispatches under — its cell is now
  `gpt-6-sol` at `high`, which has passed; it stays for any model registered
  probe-pending later;
- `conformance_probe astra-probe` (refusal token `astra-probe-wave-already-attempted` when the same
  wave is re-attempted with a different run dir);
- pin refusal tokens `pin-probe-pending` (for a future probe-pending model), `pin-role-not-eligible`,
  and `pin-not-on-allowlist` (a codex role pin must resolve on its role's own codex allowlist — every
  codex `pilot` pin is refused);
- `model-retired`, refused for any pin or config naming a retired codex model (`gpt-5.6-terra`)
  at load, at the configure write, and at dispatch validation;
- `codex-cli-too-old` and `codex-cli-version-unknown`, refused by the preflight and the
  composition-liveness check when the installed Codex CLI falls short of the registry's floor for
  the models the codex defaults use, or when its version can't be parsed;
- `gpt-5.6-sol`, registered pin-only: never a default, ladder rung, peer, or escalation target, but
  a valid pin for any codex pin role that has a codex cell (reviewer, reviewer-deep, code-fixer,
  implementer), at that role's own effort;
- `seat_map compose` flags `--host-model` and `--implementation-engine` and degradations
  `host-model-unknown`, `role-pin-not-live`, `role-pin-not-honorable`;
- `SUPERHEROES_HOST_MODEL`, exported by the session-start hook from the host payload (empty when
  absent or malformed);
- the receipt's per-seat `model` field (read from the dispatch record, `null` when unrecorded) and
  its unprobed-native disclosure line for claude seats with no runner execution evidence.

### Dispatch CLI arguments

On `engine_dispatch dispatch-review`, `engine_dispatch dispatch-write`, `dispatch_guard check`,
and `engine_adapter build-argv`:

**Dropped (no alias window).** Pass a seat bundle and role instead.

| Dropped flag | Replacement |
| --- | --- |
| `--engine` | `--seat` (vendor lives inside the seat bundle) |
| `--model` | `--seat` |
| `--effort` | `--seat` |
| `--engine-model` | `--seat` (model and effort resolve from the bundle) |
| `--vendor` | `--seat` (vendor lives inside the seat bundle) |
| `--role` | `--seat` (role now rides inside the seat bundle `"role"` key) |
| bare composed-token `--seat` (`"<vendor>:<dispatch-token>"`) | `--seat` as a four-key JSON object; the `model` field still accepts the composed dispatch-token spelling inside JSON |

**Newly required.**

- `--seat` — pass as JSON object `{"vendor": "<vendor>", "model": "<id>|null", "effort": <str|null>, "role": "<role>"}` (the `effort` key is required and its value may be null; `role` is required and must be a valid role — see the accepted seat shapes section of `skills/workhorse/reference/dispatch-entry.md`).

If you pass a dropped flag, the dispatch refuses immediately. The refusal names the replacement and
the accepted `--seat` shape. There is no silent fallback and no alias window for dropped forms.

### Dispatch result shape

Every dispatch result carries `runOpened`. When `runOpened` is true the result also carries a
`resolvedInputs` snapshot; `resolvedInputsStatus` is `pre-upgrade` when the journal predates the
seat bundle (the snapshot is synthesized from the legacy run-opened record), or `journal-corrupt`
when the journal could not be read cleanly (the snapshot is the real opened record — what was
corrupt is elsewhere in the journal). Each snapshot field has a paired `<field>Source` marker; see
the resolvedInputs source markers section of `skills/workhorse/reference/dispatch-entry.md`. Refusals raised
before the run opened carry `runOpened: false` and no snapshot. When the shell could not establish
whether a run had opened — an unreadable journal, corruption without an opened record, or an internal
error while reading the run directory — the result carries `runOpened: false` and
`resolvedInputsStatus: "unverifiable"` rather than claiming either opened-or-not.

Results no longer carry a `ledger` key. Preflight refusals return to the caller in the result body
like every other refusal.

Entry refusals now carry an additive `entryReason` key naming which entry check refused, from the
dispatch shell's closed entry vocabulary, with `entry-reason-undeclared` as its fall-back when a
refusal's own token was outside that vocabulary. **`reason` is unchanged for entry refusals** — it
stays `unrunnable`, and the outcome vocabulary gains no member, so no consumer comparing `reason`
against a hard-coded set needs to change. The presence of `entryReason` marks a refusal raised at
the entry surface; a later preflight refusal carries `reason: unrunnable` and no `entryReason`.

An `engine_adapter build-argv` invocation that refuses now **exits non-zero**; it previously wrote
its refusal payload and exited 0. A caller that read the exit code as success must now read it as
the refusal it always was.

### Composition-liveness cache

The default lifetime for a composition-liveness receipt is 3600 seconds. Set
`SUPERHEROES_LIVENESS_TTL_SECONDS` to configure the lifetime ceiling; a receipt expires at the
shorter of its stamped TTL and that value.

### Registered consumers

**weekly-eats write dispatches** omit effort today. After this release they must pass `--seat` as the
four-key JSON object on every write dispatch, with vendor, model, effort, and role supplied inside
the seat bundle.

### `run_loop` never certifies

`round_driver.run_loop` **never returns a certified receipt.** Consumers reading `receipt["verdict"]`
on the library return get a refusal shape instead: class `unrun-review`, artifact
`driver-journal.jsonl`, plus `loopTerminal` / `loopCertificationShape` / `loopRounds` for loop
observability. The loop still runs; only the certification answer is always a refusal.

### Head-content blobs (`head-content-blobs/2`)

`head-content-blobs.json` is now schema **`head-content-blobs/2`**. The keys `present` and
`fixCommits` are gone; the file carries `schema`, `files` (base64 of the raw bytes read at the
head), and `reads` (one row per read, with `contentDigest`, `bytes`, `readAt`, `source`,
`readError`).

A **legacy-shape blob is refused, not reinterpreted.** A session written before this change refuses
certification of its `fixed` dispositions with binding failure `fix-content-schema-unsupported`.
Silently reinterpreting the old shape could flip a resumed session's certification outcome on a
plugin upgrade alone. A resumed pre-upgrade session must be re-run to certify its fixed
dispositions.

### Certification receipt artifact

At a terminal, the driver now writes a **certification artifact** beside `round-receipt.json`:

- **Success** — `certification-receipt.json`: carries `terminalState`, `terminalCause`, per-seat
  provenance in `seats`, the `disclosures` block (`importantOutOfScope`), and each finding's
  disposition plus its disposition proof (`dispositionReceipt` where applicable).
- **Refusal** — `certification-refusal.json`: names one of the four escape classes
  (`unrun-review`, `same-family-seat`, `unfetched-findings`, `disposition-without-receipt`) and the
  artifact that failed.

`round-receipt.json` and `validate_receipt` are **unchanged** — same required keys, same validator,
same handback gate vocabulary. The certification artifact is separate machinery produced by
`round_certification.certify`.

Until the loop records both a finding's disposition and the cited head on a seat's journal row, the
writer certifies nothing a real review loop produces: a review that raised findings terminates in
the `disposition-without-receipt` refusal, and one that raised no findings terminates in
`unrun-review` with `execution-evidence-head-unbound`. This is fail-closed — nothing certifies on
absent evidence — and certification arrives when the loop records those two facts.

**`certificationShape` rule (writer receipt only).** Any hand-landed seat forces
`audited-chain`, never `full-panel-confirmed` (and any `full-panel*` shape in loop state is
downgraded the same way). The driver's `round-receipt.json` still records the loop's own shape;
only the certification receipt applies this override.

### `run_loop` return contract

`round_driver.run_loop` returns the certification writer's **refusal** directly — always class
`unrun-review`, artifact `driver-journal.jsonl` — plus `loopTerminal`, `loopCertificationShape`,
and `loopRounds`. There is no fallback to a legacy `build_receipt`-only dict and no certified
receipt on the library path.

| Outcome | What you get | How to read it |
| --- | --- | --- |
| Library `run_loop` return | Refusal dict with `class: "unrun-review"`, `artifact: "driver-journal.jsonl"`, plus `loopTerminal`, `loopCertificationShape`, `loopRounds` | No `verdict` key — discriminate on `class`, not `receipt["verdict"]`. `loopTerminal` is what the loop reached; it asserts nothing about certification. |
| Writer fault | Refusal dict with `class: "writer-fault"` | Internal writer crash or empty return during materialization; not one of the four escape classes. |

**Migration.** Callers that tested `receipt["verdict"]` on the `run_loop` return must branch on
`class`, not `verdict`:

```python
result = run_loop(seams, config)
if "class" in result:
    # always unrun-review on the library path — use result.get("loopTerminal") for loop observability
    ...
```

### Codex result channel

Codex review and write dispatches now return their result as a **typed JSON file** on
`--output-schema` and `-o`. The spawn argv is the opened argv plus `--json` (inserted once, before
`-o`) and `-o <run-dir>/native-result-<N>.json --output-schema <run-dir>/native-schema.json`, where
`N` is the attempt number. Stdout is telemetry only — the runner never scans it for a result.

The `run-opened` journal record carries `channel` (`"native"` or `"marker"`) and, on native,
`nativeSchemaPath` (`<run-dir>/native-schema.json`, the declared schema written at open). A resumed
run that predates the field reads as marker.

On a successful codex write, the terminal result carries `report` (the scrubbed report text). On
forfeit, it carries `detail` from the native admission vocabulary: `native-schema-unreadable`,
`native-result-missing`, `native-result-oversized`, `native-result-malformed`,
`native-result-schema-invalid`, `native-result-report-blank`, `native-result-path-occupied`,
`result-completion-unrecorded`, `result-completion-after-deadline`,
`result-completion-payload-mismatch`, `timeout-deadline-unrecorded`, or
`marker-channel-retired`. The dirty-tree forfeit keeps `detail: worktree-dirtied-by-attempt` and
carries `attemptDetail`.

A codex consumer will no longer see: a `salvage` block, `forfeit-with-engaged-artifact` (the
terminal stays `forfeited` with its `native-result-*` detail), `stdout-capped-by-attempt`,
`report-missing-items-delivered` reclassification, or `itemCheck` on a forfeit. `--output-last-message`
and the `attempt-N.last-message` file are gone. A codex run whose opened record is marker (a persisted
pre-upgrade run) never spawns again — its attempt ends with `marker-channel-retired` and the run
forfeits.

Every write run now records `echoNonce` at open, so `run_execution_record` returns `runnerNonce` for
a write run (a resumed pre-upgrade write run without it still answers `runner-nonce-missing`).

The verifier verdict contract requires `reason` as a non-blank string on every ingest path
(`payload_contracts` P_VERIFIERS); hand-submitted verifier artifacts are checked against the same
contract. A whitespace-only `id`, `verdict`, or `reason` faults.

Consumers that read codex findings from the last-message file or the event stream read the folded
`dispatch-review` result instead; consumers that relied on a write salvage block on codex reconstruct
from the worktree diff.

### Cursor result channel and the conformance probe

Cursor's results now come home on the typed-file channel — reviews and writes — with the same
declared schema per run kind as codex. A consumer that read cursor's stream-json stdout for a
result, a `WRITE_REPORT_SENTINEL` tail, or a `salvage` block reads the folded `dispatch-review` /
`dispatch-write` result instead.

The argv is `cursor-agent --model <tok> -p --trust -f --sandbox enabled --output-format
stream-json` for both roles; `--mode plan` is gone. Each attempt stages a per-attempt prompt file
`<run-dir>/prompt-attempt-<n>.md` (the order prompt plus the typed-file contract); `engine-started`
carries `attemptPromptPath` and `attemptPromptSha256`, and the execution record's `promptSha256`
binds the attempt prompt for cursor (`orderPromptSha256` is the caller's order in both).

Refusal tokens a consumer can now meet on cursor: `native-result-missing`,
`native-result-oversized`, `native-result-malformed`, `native-result-schema-invalid`,
`native-result-report-blank`, `native-result-path-occupied`, `result-completion-unrecorded`,
`result-completion-after-deadline`, `result-completion-payload-mismatch`,
`timeout-deadline-unrecorded`, `attempt-prompt-occupied`,
`attempt-prompt-unwritable`, `native-schema-unreadable`, `prompt-unreadable`,
`prompt-tampered`,
`marker-channel-retired`. Tokens that
never mint again for any engine: `stdout-capped-by-attempt`, `report-missing-items-delivered`,
`forfeit-with-engaged-artifact`, and the `salvage` block. No engine remains on the marker channel;
the marker parser, the write-report sentinel contract, the salvage tiers, the delivered-items
classifier, and the stdout-cap forfeit are retired from the supervised path and stay in the tree
only until the gardening pass that deletes them (KEEP-OR-RETIRE S1/S2).

- **Codex** — unchanged since layer 2c: native channel, result path on argv (`-o
  <run-dir>/native-result-<n>.json` with `--output-schema <run-dir>/native-schema.json`), JSONL
  telemetry on `--json`.
- **Cursor** — native channel since layer 3c: result path in the per-attempt prompt file, stream-json
  telemetry (`engagement.source: "cursor-stream"`).

Wave preflight runs `lib/conformance_probe.py` once per dispatchable engine; its result is recorded
as the launcher's `engine-auth` check — the liveness check the dispatch selftest is not.

A runner-journal line that is valid JSON but not an object now counts as interior corruption under
the class `journal-line-not-object`. The launcher's `preflight-failed:<id>` refusal now carries the
walked `checks`, including the failing entry, so the launch ledger keeps the probe's evidence on
refusal.

### Owner-authority gate retired

The `PreToolUse` hook `hooks/owner_authority_gate.py` and its classifier `lib/owner_authority.py`
are gone, so a merge, release, publish, force-push, push-to-default or workflow-run command no
longer stops at a gate prompt. A project store's `owner-authority-allow.json` is no longer read;
it can be deleted. Approval is the owner's scoped word in chat, and merges execute inside it under
the merge covenant (`rubric/covenant.md`, the hard lines).
