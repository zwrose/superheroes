# Contents

1. [Dispatch mechanics — long dispatches you own](#dispatch-mechanics--long-dispatches-you-own)
2. [Awaiting a dispatch — the in-turn contract](#awaiting-a-dispatch--the-in-turn-contract)
3. [Turn survival — the harness evidence](#turn-survival--the-harness-evidence)
4. [Process cleanup — kill by the PID you recorded](#process-cleanup--kill-by-the-pid-you-recorded)
5. [Mutation probes — own detached worktree](#mutation-probes--own-detached-worktree)
6. [Launch slice vs continuation slice](#launch-slice-vs-continuation-slice)
7. [Supervised review dispatch](#supervised-review-dispatch)
   - [Result channels](#result-channels)
   - [The conformance probe](#the-conformance-probe)
8. [Brief-check dispatch (`--mode brief-check`)](#brief-check-dispatch---mode-brief-check)
9. [Supervised write dispatch](#supervised-write-dispatch)
10. [Declared items](#declared-items)
11. [Refusal streak — shell health](#refusal-streak--shell-health)
12. [Engine forfeits and order shape](#engine-forfeits-and-order-shape)
13. [Check-runner — a plain shell task](#check-runner--a-plain-shell-task)

---

# Dispatch mechanics — long dispatches you own

Read this at dispatch time, before you invoke a long dispatch. How you wait for a dispatch, and what
survives the end of your turn, is § Awaiting a dispatch — the in-turn contract. This section covers
what bounds each dispatch kind and how you tell a live run from a stuck one. Give a long dispatch
room to finish and a stuck or runaway monitor, never a borderline limit you expect to just barely
clear.

A dispatch-shell entry point exits **1** when it refuses (returns without doing the work it was
asked to do), **0** otherwise. Exit **0** still never means success: the JSON `ok` and `terminal`
fields stay authoritative. Mechanics by dispatch kind:

- **A shell/CLI run** (an engine CLI invoked through the host's run action) is bounded by the host's
  Bash timeout. On the Claude host (harness **2.1.219**) that is **ten minutes (600 s) — a
  foreground-conversion boundary, not a ceiling you lift by passing a bigger `timeout`**: the plugin's
  `bash_timeout` hook injects 600 s **only when a call omits its own `timeout`** (an explicit one is
  never touched), and the host **converts** a foreground call whose `timeout` exceeds 600 s to
  background — it does **not** clamp-and-kill at 600 s. What kills a converted run is **the turn
  ending**. Give the dispatch that room through the `--max-wait` slice loop in § Awaiting a
  dispatch, never by trying to raise a foreground timeout. On **`dispatch-write`**, an abbreviated
  `--base-sha` refuses with nothing opened. Watch the run's **output or transcript file growing as
  your primary stall signal**: a growing file is live. Use the process's **CPU-time column only as
  corroboration**. An engine CLI can sit at ~0% CPU for minutes and still be live, so CPU alone
  can't separate idle-but-live from stuck. Treat **elapsed time as your *runaway* bound, not a
  liveness signal**. A quiet run may still be live, but one that has far outrun any plausible
  dispatch time is a runaway to kill even while its file grows. If the in-turn poll cannot fit the
  turn, park (§ Awaiting a dispatch). The output-file stall signals above still apply to the
  detached child.
- **A native subagent dispatch** has a **harness-managed lifecycle**: no `bash_timeout` floor and no
  CPU column of your own to watch. The shell mechanics above don't apply, and there is **no
  caller-set ceiling to invent**. The harness returns when the subagent completes. How to await it,
  and what to do when it cannot fit the turn, is § Awaiting a dispatch.

## Awaiting a dispatch — the in-turn contract

This section is the home of how you wait for a dispatch you launch, and of what survives the end of
your turn. The physics behind it, pinned to the harness versions it was observed on, is § Turn
survival.

### The turn's final act

A headless session (`claude -p`) **exits when its turn ends**. Until the durable handback comment,
or a durable park, is posted on the issue or the PR, end every turn with a tool call. Narration
rides alongside a tool call in the same message. A standalone narrative message ends the turn, and
for a headless session that is a session exit, not a pause. **`Monitor`, harness background-run
completion, and wakeup scheduling cannot wake a headless session**, so none of them is a turn's
exit plan. Their tool descriptions and success messages promise a re-wake that does not fire
headless. The rule is about the turn's final act, not about whether work is in flight: a session
with nothing running exits the same way.

The rule covers every outcome that resolves outside the turn, not only dispatches. A full-suite
run, a build, a long script, a CI watch, and a background waiter are each awaited in-turn. Poll
synchronously until the outcome resolves, or park durably.

### Channel and wait

Channel and wait are two choices. The **channel** is where the dispatch runs and what survives a
session exit. The **wait** is how you stay in the turn until the dispatch resolves. Detaching a
dispatch does not license ending a turn without a tool call.

- **Two physics.** Harness-tracked background work dies when the turn ends. A shell-detached child
  with durable on-disk output survives the exit, keeps working, and is recoverable when the session
  resumes.
- **A wake notification is an optimization**, never the mechanism you depend on, so never
  arm-and-sleep as your only wait. The load-bearing wait is a bounded poll on artifact files: the
  runner's structured terminal result, progress captures, and heartbeat records.

### The native shape

A long-running external dispatch you invoke directly from a headless session is an engine CLI: the
implementer, the brief-check reviewer, or any engine CLI you hand-roll. Await it in-turn through the
authorized entrypoint, `dispatch-review` or `dispatch-write` with `--max-wait`.

- **The slice.** `--max-wait` takes 0 to 540 seconds. The runner refuses a value past the cap and
  never clamps it. An over-cap or negative value comes back `unrunnable` with detail
  `max-wait-out-of-range:<value>:allowed=0..540`, with nothing opened and nothing spawned. To wait
  longer than the cap, re-invoke. Never pass a bigger number.
- **A zero slice.** On `dispatch-review`, a zero slice opens the run and returns `running` without
  starting an attempt. On `dispatch-write`, `--max-wait` also bounds git preflight, so a zero or
  too-short slice can return terminal `git-preflight-timeout` with nothing opened. A continuation
  cannot recover a run that never opened. § Launch slice vs continuation slice sizes both slices. A
  `running` result whose attempt count is zero means nothing has launched yet. Re-invoke the same
  verb on the same `--run-dir` with a positive slice.
- **No wrapper.** Invoke the entrypoint as itself, never wrapped in `setsid` or `nohup`. The host
  grant matches a command prefix, and a wrapped command no longer matches it.
- **Files, never pipes.** Redirect stdout and stderr to files, never to a pipe or `| tail`. A pipe
  dies with its reader and makes a stall look like progress.
- **Continuation.** When a slice expires, the call returns non-terminal
  `{"ok": false, "terminal": false, "reason": "running", …}` and the engine keeps working. The run
  child is its own session leader (`start_new_session=True`) and survives the caller's death.
  Re-invoke the originating verb (`dispatch-review` for a review run, `dispatch-write` for a write
  run) on the same `--run-dir` until the structured result is terminal. That structured result is
  the only completion signal.
- **No exit-code sentinels.** A done-sentinel that records a wrapper's exit code is forbidden. A
  sentinel can read `EXIT=0` while the runner's own result is `ok:false, reason:forfeited`, so it is
  a false completion signal, not a receipt.
- **`dispatch-poll` observes.** `dispatch-poll --run-dir` reads the journal and returns the folded
  result only if a supervisor already folded it. It never spawns, never advances a run, never folds
  one, and is never the continuation path.
- **Lock reclaim.** A slice that expired normally has released `run.lock`, so the next
  originating-verb call re-attaches at once. A caller killed mid-slice leaves `run.lock` held. The
  next call takes it over as soon as that holder's pid is confirmed dead, with no TTL wait. A live
  holder is never taken over, so a second caller racing a live one still gets `running` or
  `run-locked`.

### Concurrent batches

A batch is independent when its members share no result dependency, no writable worktree, and no
output path. Independent work orders, a review panel's dimensions, a round's verifier clusters, and
a round's audit targets are such batches. Send an independent batch out concurrently. That is the
shape, not a permission.

1. Give every member its own `--run-dir`.
2. Launch each member with a short positive slice. A zero slice launches nothing on
   `dispatch-review` and risks `git-preflight-timeout` on `dispatch-write`.
3. Re-invoke the originating verb on every non-terminal run in rotation until each returns
   terminal, and fold each result as it lands.

The concurrency comes from the engines working while you poll the others, not from issuing the
calls in one message. Run-action calls serialize, and a launch call blocks for its whole slice
(§ Launch slice vs continuation slice). A native-subagent batch is the other channel. The harness
runs subagent dispatches issued in one message concurrently and owns their lifecycle, so send that
batch out together in one message. A batch then costs its slowest member, not the sum of its
members.

Concurrency changes a batch's shape, never its invariant. Every run is awaited in-turn, with no
`&`, `setsid`, or `nohup`, and no run-dir left unwatched at turn end. The one exception is a durable
park. Anything that fails the independence test stays sequenced: a dependent order, or two
dispatches that would write the same worktree.

### Native subagents

A native subagent has no detach, because the harness owns its lifecycle. Await it in-turn. If it
cannot fit the turn, do not dispatch it. Park durably with the work order ready, or split the work
so each dispatch fits one turn.

### Skill-owned seats

The native shape binds the dispatches you invoke directly. Seats a skill owns and dispatches
itself, `review-code`'s panel and its fixer, keep that skill's own dispatch contract, and you do not
wrap or re-channel them. `review-code` owns their bounds: slice size, structural timeout, retry
ladder, and the rule that the caller composes no per-dispatch watchdog
(`skills/review-code/reference/auto-fix-loop.md`). Its codex and cursor seats run the native shape,
and its claude seats are native subagents. A build whose review seats ran either way owes no
native-shape disclosure for them. The skill's hand-rolled engine fallback does not follow the
native shape and still owes the disclosure when used. The in-place fixer stays a foreground Bash
dispatch, because `dispatch-write` refuses a primary checkout (`cwd-primary-checkout`).

### Park when the poll cannot fit

When the in-turn poll cannot fit the turn, end with a durable park on the issue or the PR, where
the advisor finds it without being told to look. The park says what is running, where its output
is, and what the advisor must do. A session transcript or a scratch file is not a park. An outcome
that outruns any plausible resolution time is a park, not an unbounded poll. A need for the owner's
capability mid-run parks the same way: a running headless session is deaf, so never improvise a
notification channel.

## Turn survival — the harness evidence

The physics behind § Awaiting a dispatch — the in-turn contract, pinned to the harness versions it
was observed on. The rules live in that section.

- **Harness-tracked background work dies when the turn ends** (harness 2.1.219, three runs): a probe
  wrote a start marker at t+8s, the session exited at t+15s, and the completion marker never
  appeared — no completion, no orphan process. Treating tracked-background work as durable is how
  builds orphan.
- **Shell-detached children with durable on-disk output survive the exit**, keep working, and are
  recoverable when the session resumes. The session exited, the detached child completed to disk,
  and the resumed session recovered with zero work lost.
- **Wake notifications never fire for a dormant builder.** Background-run, wakeup scheduling, and
  their success messages all promise a re-wake that never fires headless. On 2.1.219, with the
  spawning agent dormant, a background task's completion notification reaches the **root session**,
  not the builder. The builder is never woken, and the advisor becomes an accidental message broker.
- **The induction trap.** Wake-on-completion **does** work early in a session while the parent still
  holds an active task — so a builder that verified a re-wake once has evidence about the
  **active-task regime only**, and **none at all** about the **dormant-parent regime** where it
  fails. Trusting "re-wake proven earlier this session" into the dormant-parent regime is the trap;
  both halves were observed on 2.1.219.

## Process cleanup — kill by the PID you recorded

Tearing down what you started is where a wave kills its own siblings. **The kill target is a PID you
recorded when you started the process** — read back out of the dispatch's run dir, the launch record,
or the note you wrote at spawn time — and never a match on the process's command text. Record the PID
at spawn precisely so this is available later; a teardown that has to go looking has already lost the
argument.

**A command-text match is a cross-session kill, not a cleanup.** Sibling sessions in the same wave run
*identical* commands — the same dev server, the same test invocation, the same engine CLI — so
`pkill -f dev-server.js` or a `pkill -f` on a test command matches **their** process as readily as
yours, and the process that dies is whichever the pattern happens to reach.

**If you did not record the PID, identify the process by something your own run owns** — the **cwd**
of the worktree you dispatched into, or the **port** your own server bound — and kill *that* PID.
Two properties make that safe, and establishing both is on you. **Read kernel-reported process
metadata, never the command line** — a process's *actual* working directory is ownership evidence,
while a worktree path matched inside its *command line* is command-text matching wearing a different
hat. And **ownership has to still hold now**: a port is evidence only while your process is the one
holding it, since a sibling can rebind it the moment yours exits, and a port query not restricted to
the **listener** also returns every client connected to it — so corroborate a port candidate against
the run's own cwd or launch record before killing anything. **Zero verified candidates,
or more than one, means you have no kill target** — stop there and say so rather than widening the
match (charter §7).

## Mutation probes — own detached worktree

A bite-proof mutation probe runs in a **detached worktree of its own**, pinned to the commit under
proof — never in a tree where **live read-only seats are reading** the paths the probe mutates.
Review seats, auditors, and any concurrent reader dispatched against that path share the same
prohibition: a reader that sees the tree mid-probe grades a state that never shipped, and the symptom
— a seat reporting an inexplicable revert, or a file that disagrees with the diff — does not name its
cause.

**This composes with, and does not replace, the charter's two standing rules:** commit the landed
implementer work before probing (charter §8), and neutralize/restore by **targeted, reversible
edits through the host's edit action** — never `git checkout --`, `git restore`, `git reset`, or
`git stash`. A separate worktree is **where** the probe runs, not licence to revert by discarding.

**The rule is unconditional** — it holds even when no seats are running right now. A seat can be
dispatched while a probe is open, and the builder does not always control the timing.

**When a probe cannot run in a separate tree** — the detector under proof is bound to a specific
path or checkout — **disclose it and hold the seats off that tree**; never probe silently under live
readers.

**When the probe finishes**, remove the probe worktree with `git worktree` verbs — never `rm`.

## Launch slice vs continuation slice

<!-- WORKAROUND: 540 s continuation and short launch slice recipes for turn-end survival
     delete-when: a re-run of the background-session trial observes its "the turn-end doctrine
     and its slice recipes" condition met; the condition is restated in the keep-or-retire
     record's marker inventory -->

Every `dispatch-review` / `dispatch-write` call names a `--max-wait` **slice** on that `--run-dir`.
The slice you choose depends on whether the run is a **launch** or a **continuation**:

- **LAUNCH** — the **first** call on a fresh `--run-dir`. Use a **short** positive slice for
  **`dispatch-review`** and for **`dispatch-write`** on repositories whose git preflight is fast.
  On **`dispatch-write`**, `--max-wait` is also the **git-preflight timeout** (`preflight_timeout`
  in `engine_dispatch.py`), bounding worktree validation, repository discovery, `rev-parse HEAD`, and
  the baseline `git status`, plus the **sibling-worktree baseline snapshot** at run open (HEAD sha,
  porcelain sha256, and reflog count on every other registered worktree — bounded by
  `sibling_worktree_probe.DEFAULT_DEADLINE_SECONDS` with a floor of `MIN_DEADLINE_SECONDS`). The launch
  slice **must therefore exceed the repository's git-preflight
  cost** (which depends on repository size and disk speed and must be sized locally), or the call
  returns terminal **`git-preflight-timeout`** with nothing launched — and a continuation **cannot**
  recover a run that never opened. Run-action calls serialize and a launch call blocks for its whole
  slice, so a launch phase over N run-dirs costs about **N × the launch slice** — that estimate
  **omits** this serial preflight work on each `dispatch-write`, so a real launch phase costs
  somewhat more than the multiplication suggests. With a short launch slice a concurrent batch
  costs about its slowest member. A long launch slice pushes the cost toward the serial sum.
- **CONTINUATION** — a re-invocation on an already-launched `--run-dir` while `.terminal` is false.
  The engine is already working, so use the **full slice up to 540 s** — a longer slice simply means
  fewer re-invocations.

The `--max-wait 540` values in the recipes below are **continuation** slices and remain correct for
every re-invocation after launch. On the first call for each `--run-dir`, substitute a short launch
slice (12–45 s is a workable range).

## Supervised review dispatch

The sanctioned way to dispatch a long-running **external reviewer** seat is `dispatch-review`. The
seat's delivery contract is in `rubric/review-base.md` ("Findings output format"); `auto-fix-loop.md`
documents the runner's result mechanics — read both before authoring seat prompts; this subsection is
the at-dispatch-time summary only. For the full CLI argument surface — including the
`--session-dir`/`--pr-body-path` pairing and its refusal token — read
`skills/workhorse/reference/dispatch-entry.md`.

### Result channels

All three dispatchable engines — **codex**, **cursor**, and **claude** — use the **native** channel.

**Codex** receives the result path as `-o <run-dir>/native-result-<n>.json` with `--output-schema
<run-dir>/native-schema.json`. **Cursor** receives it in a per-attempt prompt file
`<run-dir>/prompt-attempt-<n>.md` — the staged prompt plus the typed-file contract (the prefix line
`Result file (write exactly this path; nothing else is graded): <path>` and the declared schema
quoted in a fenced block) — under the argv `cursor-agent --model <tok> -p --trust -f --sandbox
enabled --output-format stream-json` for both roles (`--mode plan` is gone: plan mode cannot write
the file). Builder lanes are not dispatched through this runner — the launcher starts them as
`claude -p` sessions whose command comes from `engine_adapter.claude_builder_argv`; background mode
is for review seats only. **Claude** receives `--json-schema <declared schema JSON>` on argv at
run-open and the prompt on stdin under `claude -p --model <tok> --effort <effort> --output-format stream-json
--verbose`, plus `--restricted` for review or `--permission-mode acceptEdits --restricted`
for write; a claude write dispatch is edit-only inside the run cwd because no OS sandbox is
available through this CLI, so an order needing to run commands does not route to claude today.
The runner materializes the `structured_output` from the last `{"type":"result"}` event
on stdout to `<run-dir>/native-result-<n>.json` at attempt end. `attempt-ended.stdoutResult`
records `materialized`, `absent`, `error`, or `occupied` — only `materialized` is loaded;
`occupied` forfeits `native-result-path-occupied`; `absent` and `error` forfeit
`native-result-missing`. **Print mode** is the default: omit `--claude-mode` or pass
`--claude-mode print`. **Background mode** is selected with `--claude-mode background` on
`dispatch-review` only — a write dispatch in background mode refuses before anything spawns
(`claude-mode-background-write`, `attempts: 0`), because a detached session outlives the
process whose liveness the worktree lease is keyed on, so the lease could be reclaimed while
the session may still be editing. A run's mode is fixed when the run opens; a continuation
that supplies a disagreeing `--claude-mode` refuses `run-dir-claude-mode-mismatch` with
`attempts: 0`. In background mode the launch child acknowledges and exits; the runner resolves
the session through the per-account agent listing, polls the session transcript until the turn
ends, and materializes the last structured-output payload to the same
`<run-dir>/native-result-<n>.json` path print mode uses, where the same admission gate loads
it — a launch acknowledgement alone is not a result. A background session does not end when
its turn does; it stays live until stopped, so every terminal path stops it and confirms the
stop (`bgStop` records `stopped`, `already-ended`, or `stop-unconfirmed` — an unconfirmed stop
is recorded, not assumed). When a slice expires before the turn ends, the attempt is suspended
with the launch and session ids and a transcript cursor; a continuation re-attaches to that
session rather than launching a second one. Background telemetry comes from the session
transcript's tool calls (`attempt-ended.transcriptToolCalls`), not from stdout — the background
argv carries no event stream. At run-open the shell resolves `CLAUDE_CONFIG_DIR` through
`lib/config_dir.resolve(env, cwd)`, records it as `run-opened.configDir`, and refuses at open with
`config-dir-unusable:<why>` when it is not an existing directory; at spawn the same value is injected
with `CLAUDE_CODE_EFFORT_LEVEL=<seat effort>` (`engine-started.env` records both pins). Telemetry
uses `engagement.source: "claude-stream"`, `telemetry: "tool-calls"`; distinct `tool_use` block
ids across `assistant` events are counted, excluding the `StructuredOutput` call.

On the native channel, the output adapter reads a typed result file validated against the declared
schema at `<run-dir>/native-schema.json`. Admission is engine-neutral: the schema on disk must equal
the declared one (`native-schema-unreadable` otherwise); the file must be a regular file within the
size cap that decodes as JSON (`native-result-missing`, `native-result-oversized`,
`native-result-malformed`); it must validate against the declared schema
(`native-result-schema-invalid`); on a write, its `report` must be non-blank
(`native-result-report-blank`); on a write, a result admitted although the process had to be stopped
at the wall cap is marked `admittedAfterTimeout: true` rather than reading as a clean exit; and an
entry already at the result path when an attempt would spawn
refuses that attempt (`native-result-path-occupied`); every native attempt requires a usable
completion stamp (`result-completion-unrecorded` when missing or unusable, and when a deadline is
present its epoch must match the stamp's); every attempt-ended record also carries the wall-cap
deadline on the same clock (`deadlineMono`/`deadlineEpoch` stamped from `start + timeout` at attempt
end), and a timed-out attempt refuses when those deadline fields are missing or unusable
(`timeout-deadline-unrecorded`), then `result-completion-after-deadline`
when completion is strictly after the cap — exactly at the cap admits,
`result-completion-payload-mismatch` when the admitted payload is not the one the stamp was taken
over). Cursor adds attempt-prompt refusals:
`attempt-prompt-occupied` (any pre-existing entry at the attempt-prompt path — file, symlink,
dangling symlink, directory — the engine learns the run dir from the result path, so a first attempt
could plant the second's), `attempt-prompt-unwritable`, and `prompt-tampered` (the staged source
prompt's bytes no longer match the digest bound at run-open). For **codex and cursor**, every
refusal is a forfeit or an attempt refusal — the runner never scans stdout for a result and never
repairs a malformed file. **Claude print mode** is the exception on the first half: the runner
incrementally reads stdout for complete `{"type":"result"}` lines and holds the last one, stamping
it when it is admissible; it observes once more before terminating the process group and drains any
trailing bytes once after the group is reaped; the typed file is materialized from that held event,
so stdout is read once for the result and never re-read or re-split; if the final read fails, or
the file shrinks below what was already read, nothing is materialized and the dropped result is
reported as `stdout-result-dropped` with its cause (`final-read-failed`, `shrunk-below-read`,
`bytes-changed`); just before a held result is saved, the bytes it was parsed from are re-checked
by digest and a mismatch drops it the same way; it still never repairs a malformed file. **Claude
background mode** never reads stdout
for a result — the transcript path above. Claude adds `config-dir-unusable:<why>` at run-open and
the adapter refusals `unregistered-engine-model`,
`fable-unrunnable`, `invalid-model-effort`, `untokenizable`.

Completion is engine-owned and recorded as a monotonic instant, not inferred from process exit or
file mtime: each attempt-ended record carries `resultCompleteAt`, `resultCompleteEpoch`, and
`resultCompleteSha256` (a digest of the payload complete at that instant). **Codex and cursor**
stamp the first moment the result file parses as complete JSON; **claude print** stamps when the
poll loop first observes a complete `{"type":"result"}` line on stdout — each poll advances an
incremental read, with one final drain after the process is reaped — and later materialization to
the result path is not the completion time; a final line with no trailing newline is complete only
at end of file, so it is stamped at that final drain; **claude background** stamps the supervisor's record of the result's arrival
in the transcript rows; the in-process seam stamps its own capture. Every attempt-ended record also
carries `deadlineMono` and `deadlineEpoch` (the wall cap on that clock, stamped unconditionally at
attempt end; `timeoutAt` remains for display only on timed-out attempts). Admission compares only
those stamped fields in one loader every native
path passes through: it recomputes the payload digest and requires it to match the recorded one, so
a result rewritten after its stamp cannot be admitted on the earlier stamp. For claude print the
completion instant is the runner's observation, lagging by up to one attempt poll interval (0.2 s)
plus the time to process that poll — a result completing inside that final window before the cap
may be stamped just after it and forfeit; that is the safe direction. Write forfeits name
`nonzero-exit` when the engine exited non-zero before the cap, and `timeout-no-admission` when the
cap was hit with nothing admitted.
Progress and engagement telemetry come from codex's JSONL event stream on `--json`
(`engagement.source: "codex-events"`); cursor's stream-json event stream (`engagement.source:
"cursor-stream"`, `tool_call` events counted by distinct call id); claude's stream-json event stream
(`engagement.source: "claude-stream"`, `tool_use` blocks counted by distinct id, excluding
`StructuredOutput`). Stdout is telemetry for codex and cursor, never a result; on claude stdout
carries telemetry and the final `{"type":"result"}` envelope from which the runner materializes the
typed file. The `--output-format json` envelope emits one object at exit and carries no tool-call
events — codex and cursor never use it; claude reads the identical envelope as the last line of
`stream-json --verbose`, not through the `json` single-object mode.

Every run the shell opens never receives marker-channel recoveries: no `salvage` block, no
`forfeit-with-engaged-artifact`, no `stdout-capped-by-attempt` forfeit, and no
`report-missing-items-delivered` reclassification or `itemCheck` on a forfeit. A run whose opened
record is marker — a persisted pre-upgrade journal — never spawns again: the spawn-side
check runs before argv coherence, so a stale argv is not what refuses it; its attempt ends
`marker-channel-retired`. The execution record's `promptSha256` binds the bytes the engine received
— the attempt prompt for cursor (`attemptPromptSha256`/`attemptPromptPath` on `engine-started`), the
staged prompt for codex; `orderPromptSha256` is the caller's order in both.

The journal writes two `engine-launching` records per attempt: the first (from the run child's
entry) carries `argv`, the opened argv; the second carries `spawnArgv`, the argv the engine actually
received. A reader trusts `spawnArgv`.

On an engine on its native channel, a second schema or adapter fix after landing — a `fix` commit touching that engine's
declared schema or its output or completion adapter — proposes dropping the engine or accepting the
cost in the record. The fix commits are read by their `fix` type and touched paths; no new
instrument; the proposal is the owner's judgment at the pass. The readout the pass reads is the
result-channel-per-engine rows of the project's values annex, which lives outside the repository.

Cursor delivers its result as a typed file, never through the `json` envelope: the envelope's
`result` string joins every assistant text turn, so it is never the result. The stdout capture cap
(`MAX_STDOUT_CAPTURE`, 8 MiB) stays an operating parameter — it bounds the telemetry capture; the
`stdout-capped-by-attempt` forfeit no longer runs for any engine.

### The conformance probe

Wave preflight runs one real review dispatch per dispatchable engine before any builder launches.
Resolve `ROOT_DIR` as in every other recipe here, then run `python3 -B
"$ROOT_DIR/lib/conformance_probe.py" run --engine <codex|cursor|claude>` — optional `--repo-root`,
`--run-dir`, `--timeout`, and `--wave <id>` (the launcher's wave id, recorded on the result); only
the engine name is required. Each invocation allocates a unique dispatch order id; a `--run-dir` that
already holds a folded terminal result refuses `run-dir-reused` with nothing launched. It dispatches through the shell's own
library entry on the engine's declared native channel (the typed file for codex and cursor, the
materialized structured output for claude), using that
engine's `reviewer-deep` cell, and grades three legs **separately**:
`resultProduction` (the folded result is a typed, validated result), `completionDetection` (the
attempt ended by natural exit 0 inside the wait and the run folded terminal), and
`progressTelemetry` (runner-observed tool-call telemetry with a named source and a last-activity
stamp). Failure is loud: exit **1** and one stderr line `CONFORMANCE PROBE FAILED engine=<e>
failed=<legs> dependent lanes: <…>`; the JSON result carries `legs`, `failed`, `dependentRoles` /
`dependentLanes` (derived from the project's dispatch calibration — the roles routed to that engine),
`probedCell`, `repoRoot`, `completedAt`, and a `preflightCheck` member shaped as the launcher's
`engine-auth` check entry. Per-leg failure vocabulary: `result-did-not-validate` or the shell's own
`native-result-*` / parser detail; `no-response-within-wait`, `attempt-ended-missing`, or
`auth-or-config-refusal`; `telemetry-absent`. The engine set is the adapter's dispatchable vendors
intersected with the channel map — `codex`, `cursor`, and `claude` — by construction, with no
separate list.

Before launch, compose the walked `engine-auth` check from one probe result per **dispatchable**
engine (`codex`, `cursor`, and `claude` — not merely the engines the calibration routes to):

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"
python3 -B "$ROOT_DIR/lib/conformance_probe.py" preflight-entry --repo-root <abs> --result <probe.json>… \
  [--wave <id>] [--launch-without <engine> --owner-word "<text>"]… [--max-age-seconds N]
```

Without `--wave`, binding is repository path plus age only and the entry records
`waveBinding: none`. With `--wave`, each result's `wave` must match or the entry refuses
`probe-wave-mismatch:<e>`. Each result's `probedCell` must match the engine's current
`reviewer-deep` matrix cell or the entry refuses `probe-cell-mismatch:<e>`.

It refuses `probe-missing:<e>`, `probe-duplicate:<e>`, `probe-foreign-repo:<e>`,
`probe-stale:<e>` (default max age 86400 s, one day; future `completedAt` timestamps count as stale),
`probe-result-malformed:<path>`, `probe-channel-mismatch:<e>` (the record's channel is not the channel the engine dispatches on today — a probe taken before a channel move proves nothing about the new channel), `calibration-unreadable`, `author-family-unresolved`,
`owner-word-missing`, and `seat-map-failed:<type>`. A failed engine with no owner word → `state: fail` (hold;
the launcher's `walk_preflight` refuses `preflight-failed:engine-auth`, so nothing launches). With the
owner's word → `state: pass` whose evidence names the substitute family per seat, computed by the seat
map from the **probed cells only** (`live_cells_source: "probed"`) with the maker family derived from
the calibrated implementer — or `state: fail` with **PARK** when the seat map reports a
`same-family` degradation. A `preflight-failed:<id>` refusal carries the walked `checks` including
the failing entry, so the refusal record in the launch ledger keeps the probe's evidence.

A drift or auth failure that arrives **mid-wave** forfeits that dispatch with no salvage; nothing
re-probes mid-wave.

### Findings-only review prompts

A review prompt that constrains the seat's stdout to a **single JSON object** must also require a
**populated `investigated` array** and tell the seat that an **empty `findings` array alongside a
real investigation record is a valid, welcome answer**. Without it, the runner's investigation floor
(`engine_adapter.spot_check_investigated`) forfeits an empty payload as **vacuous** — a
findings-only prompt that omits the requirement guarantees that forfeit whenever the honest answer
is no findings. An entry survives the floor only when it is a **repo-relative path to an existing
regular file** inside the reviewed view; directories, absolute paths, and generated artifacts
(including the staged diff patch) do not count. Seat-side wording lives in `rubric/review-base.md`
("Findings output format").

Every `dispatch-review` result is a **top-level** object. **Always present:** `ok`, `terminal`,
`runDir`, and `argv`; on a failure, `reason` (and usually `detail`). On success: **`resultKind`**
(one of `findings`, `verdicts`, `grouping`, `ruling`) naming the payload, plus **exactly one**
payload key of that name.
**`investigated`** is present only when at least one claimed path survives spot-checking; a normal
`{"verdicts": [...]}` reply omits it. **Outcome-dependent:** `engagement` and `sanitizedView` — do **not** read an
absent `findings` as "zero findings"; an absent `findings` may mean a different `resultKind`
instead. An object carrying **more than one** payload key from `REVIEW_RESULT_KINDS` is refused as
`unreadable`. An item
whose `id` is exactly `<agent-name>-001` or whose `severity` is exactly
`Critical | Important | Minor | Nit` — the `review-base.md` template literals — is refused as
`unreadable` (field-exact; an honest finding that *quotes* those literals in its prose survives). An
`unrunnable` refusal carries no `findings` / `investigated` / `engagement`; it carries
`sanitizedView` **only when raised after the sanitized view was built** — the early refusals
(`repo-root-*`, `prompt-*`, `run-dir-*`, `schema-*`) precede the view and carry none. A terminal
forfeit carries no `findings`/`investigated`. There is no `result` wrapper; `result.findings` reads
nothing. Optional **`--mode {review,brief-check}`** (default `review`) — full contract in
`auto-fix-loop.md` (mode refusals, continuation rules, top-level `mode` on every result). On
continuation, `--diff-base` is accepted but ignored — the live run's view is not rebuilt — except
when this invocation also asserts `--mode brief-check` explicitly, which refuses
`mode-brief-check-with-diff-base` before the journal is read.

Optional **`--diff-base <commit-oid>`** stages the reviewed change as
`SUPERHEROES_REVIEW_DIFF.patch` inside the gitless sanitized view — the machinery external seats need
because `git diff <ref>` and `git log` cannot work there; the `sanitizedView` receipt then also
carries `diffBase`, `diffPath`, `diffBytes`, `diffWithheldCount`, `configDiffPath`, and
`configDiffBytes` (all `null` when the flag is omitted, or under `--mode brief-check`). On a
continuation (`--run-dir` naming an existing run),
`--diff-base` is accepted but ignored — the live run's view is not rebuilt — except when this
invocation also asserts `--mode brief-check` explicitly, which refuses
`mode-brief-check-with-diff-base` before the journal is read. Full contract — refusals,
withheld stripped-config paths, investigation-floor rejection — is in `auto-fix-loop.md`.
The runner accepts **four** result kinds on stdout (`REVIEW_RESULT_KINDS`: `findings`, `verdicts`,
`grouping`, `ruling`). Every `ok: true` review result carries **`resultKind`** naming exactly one
payload key of that name; **`investigated`** is attached only when at least one claimed path
survives spot-checking. **Recognition is not gradeability** — widening what the transport can read
changes nothing about what it will certify: the investigation floor still forfeits an empty
payload with no surviving `investigated` path for **every** kind including `grouping`, and an
`--expected-result-kind` mismatch still forfeits. Callers may pin the expected kind via
**`--expected-result-kind {findings,verdicts,grouping,ruling}`**; a mismatch refuses with
`detail: result-kind-mismatch`. The pin is journaled when the run is **opened**; on a
continuation an omitted pin inherits the journaled value, while a supplied pin that disagrees —
including on a run opened without one — refuses `run-dir-result-kind-mismatch` (`attempts: 0`, no
spawn); a run's identity is fixed at open. **Panel** seats pass the **`findings`** pin; the **verify
phase** passes the **`verdicts`** pin; synthesis judges emit `{"grouping": [...]}`; fix auditors
emit `{id, ruling, reason}`. When unset, all four kinds are accepted. Per-id audit rulings still
do not travel through this verb. A non-terminal `{"reason": "running", "terminal": false}` is **not**
a forfeit. It carries a **`graded`** list describing each attempt that has already ended — each entry
names `resultKind` and its payload when that attempt graded `ok`. Re-invoke **`dispatch-review`**
(never `dispatch-poll`) on the same `--run-dir` with `--max-wait 540` while `.terminal` is false.

When the result carries an **`engagement`** block with a non-`null` value (present only when the
attempt produced stdout that was graded), `engagement.read` is `"engaged"` when the seat
demonstrably acted (a finding or `engagement.toolCalls >= 1`); a seat's `investigated` list is
**disclosure**, not engagement evidence; the runner still spot-checks it. Otherwise
`"unknown"`. On a timeout, refusal, nonzero-exit, or missing-stdout forfeit the
`engagement` key is **present with the value `null`** (there was no graded stdout to measure), so
`engagement.read` is unavailable — `result.get("engagement", {})` is **unsafe** because the key may
carry `null`, not merely be missing; consumers must handle a `null` value. The runner **never**
asserts `"inert"` — absence of positive evidence is not proof of inaction, and only `seat_canary
probe` can justify calling a seat inert. Token spend does not measure engagement: a small dispatch
can be engaged and clean while a dispatch several times its size produces a Critical finding.

**`reason: "forfeit-with-engaged-artifact"`** — a marker-channel outcome. No run mints it: it names a
marker-channel recovery, and no engine is on the marker channel. It stays in the outcome vocabulary
because a persisted result can carry it. Read one as a terminal forfeit: every rule about a terminal
forfeit applies, including the three-case reviewer-loss rule in `rubric/review-discipline.md`.

**Per-attempt telemetry** (each ledger row's `attempts[]` entry, one per spawned attempt):

| Field | Meaning |
|---|---|
| `exit` | Process return code |
| `signal` | Signal number when exit was signal-terminated |
| `signalSource` | Who delivered the signal — see below |
| `timedOut` | Runner cap fired |
| `capSeconds` | The cap that applied |
| `wallSeconds` | Wall time for the attempt |
| `lastActivityAt` | Epoch of last observed output growth |
| `silenceSeconds` | Seconds between last activity and kill/exit |
| `activityStream` | Which stream (`stdout` or `stderr`) last grew |
| `stdoutBytes` / `stderrBytes` | Byte sizes at kill (pre-cap snapshot) |
| `promptBytes` | Fed prompt size |
| `dispatchPath` | Which spawn path ran (`subprocess` vs injected seam) |

The spawned command is on the result as top-level **`argv`**. That field reports the argv of the
last attempt that actually reached the engine; an attempt that did not reach the engine —
whether refused by the spawn gate before invocation or because spawn itself failed — does not
contribute. When no attempt reached the engine, the field carries the
canonical argv the run was opened with. **Silence against the cap** carries the most diagnostic weight: killed at the cap while
`silenceSeconds` is small (output was still moving) means *our cap was short*; killed after long
silence is a genuine stall. `lastActivityAt` and `silenceSeconds` are accurate to the runner's poll
interval (10 s), not to the byte. **`signalSource`** — the runner terminates the process group on
every path, so without this field a runner-inflicted `SIGTERM` (`runner-timeout`) is indistinguishable
from an engine crash (`engine`).

**Entry refusals** — terminal, not-run outcomes: the dispatch never ran and the result is final.
They carry `reason: unrunnable` plus an additive `entryReason` naming which entry check refused,
from the shell's closed entry vocabulary, with `entry-reason-undeclared` as that key's fall-back
when a refusal's own token was outside the declared entry vocabulary. The producer's own reason
is preserved in `detail`.

**Engaged vs delivered are two variables** — a seat can burn hundreds of thousands of tokens, reach
real findings in its stdout, and deliver nothing gradeable through our transport (engaged but not
delivered). Other terminal outcome reasons: `forfeited`, `vacuous`, `forfeit-with-engaged-artifact`,
and `unrunnable`.

### Brief-check dispatch (`--mode brief-check`)

The workhorse charter §5 names *who* reviews the brief; this subsection carries the standing lens the
check always applies, and the mechanics for *how* it is dispatched. The sanctioned channel is
`dispatch-review --mode brief-check` — not a hand-rolled `codex exec`, which is permitted **only when
the runner itself is unavailable** (disclosed degradation in the PR body, never the normal path).

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"
# Resolve brief-check cell from dispatch calibration + registry matrix (model/effort)
read -r BRIEF_ENGINE BRIEF_ENGINE_MODEL BRIEF_EFFORT <<<"$(python3 -B -c "
import sys
sys.path.insert(0, sys.argv[1] + '/lib')
import model_registry as mr
import preflight_probe as pp
row = next(r for r in pp.dispatch_calibration() if r.get('role') == 'brief-check')
cell = mr.matrix_config('brief-check', row['engine'])
model, effort = cell
effort_s = '' if effort is None else effort
print(row['engine'], model, effort_s)
" "$ROOT_DIR")"
if [ -z "${BRIEF_EFFORT}" ]; then BRIEF_EFFORT_JSON=null; else BRIEF_EFFORT_JSON="\"$BRIEF_EFFORT\""; fi
BRIEF_SEAT='{"vendor":"'"$BRIEF_ENGINE"'","model":"'"$BRIEF_ENGINE_MODEL"'","effort":'"$BRIEF_EFFORT_JSON"',"role":"brief-check"}'
# $BRIEF_PATH is reviewer instructions + the brief — it is fed verbatim as the whole prompt, so
# the standing lens below must be inside it (see "The standing lens", after this recipe)
# Keep $BRIEF_PROGRESS outside $RUN_DIR — non-empty run-dir → run-dir-not-empty-unopened
# Gate first — four-key seat carries role inside --seat
python3 -B "$ROOT_DIR/lib/dispatch_guard.py" check --seat "$BRIEF_SEAT"
# LAUNCH — fresh --run-dir outside the repo; no --diff-base
python3 -B "$ROOT_DIR/lib/engine_dispatch.py" dispatch-review \
  --mode brief-check \
  --seat "$BRIEF_SEAT" \
  --prompt-path "$BRIEF_PATH" --repo-root "$REPO_ROOT" \
  --order-id "$ORDER_ID" \
  --run-dir "$RUN_DIR" --max-wait 12 \
  --progress-file "$BRIEF_PROGRESS"
# CONTINUATION — re-invoke while .terminal is false
python3 -B "$ROOT_DIR/lib/engine_dispatch.py" dispatch-review \
  --mode brief-check \
  --seat "$BRIEF_SEAT" \
  --prompt-path "$BRIEF_PATH" --repo-root "$REPO_ROOT" \
  --order-id "$ORDER_ID" \
  --run-dir "$RUN_DIR" --max-wait 540 \
  --progress-file "$BRIEF_PROGRESS"
```

For the full `dispatch-review` argument surface, read `skills/workhorse/reference/dispatch-entry.md`.

Continuation rules — full contract in `auto-fix-loop.md`: omitting `--mode` inherits the opened mode;
supplying a disagreeing `--mode` is `run-dir-mode-mismatch`, `attempts: 0`. Explicit
`--mode brief-check` together with `--diff-base` always refuses `mode-brief-check-with-diff-base`
(continuation included); `--diff-base` is accepted-and-ignored only when brief-check mode is
inherited from the journal and `--mode` is omitted. The terminal journaled result — `mode:
brief-check`, `attempts ≥ 1`, engagement read, `sanitizedView` with all six diff keys `null` — is
the receipt that the brief check happened.

**The standing lens: the foreign-contract round-trip.** Whatever else the brief prompt asks, the
check always applies this one — and applying it is an obligation on **`$BRIEF_PATH`**, not on this
file. Nothing here reaches the reviewer on its own: the delivered prompt is the anti-hijack preamble,
the sanitized-view notice, and `$BRIEF_PATH` verbatim, so **`$BRIEF_PATH` is reviewer instructions
*plus* the brief, never the bare brief** — and it carries the lens below **quoted verbatim, never
paraphrased**, alongside a citation of this home
(`skills/workhorse/reference/dispatch-mechanics.md` § *The standing lens*), on every brief check.
A brief-check prompt that omits it has not dispatched this lens. **This is a declared, narrow
exception to CONVENTIONS §11.4** — that rule says orders, agent prompts, and dispatch prompts cite
the path and never paste the body, and it binds everywhere else. It is excepted **here only**, and
for one reason: §11.4's own fail-loud half turns an unresolvable citation into a halt, and this
seat's working directory is a sanitized export of *the repository under review* — which in a
consuming project does not contain this plugin, so a bare plugin-relative citation is a **guaranteed**
dangling pointer and every brief check in every consuming project would halt. §11.4's worked
consumers (the implementer, the pilot) read the build worktree, where the path does resolve; this one
does not. The exception is bounded to this prompt: the citation still rides alongside, so the single
home stays nameable and the copy checkable, and **a builder's own re-wording is never acceptable** —
a paraphrase is how the obligations soften without anyone deciding to soften them. Widening this
exception, or retiring it if the seat ever gains a way to read the plugin, is the advisor's call, not
a builder's.
**A brief that touches an external API, CLI, or service contract owes
the round-trip answer** — evidence that the *far side* accepts what we intend to send, established
before code rather than after. Exactly one of three satisfies it: **(a)** local validation against
the foreign contract's own rules (the vendor's schema dialect and its strict-mode restrictions, its
required/optional shape, its argv grammar) — not against our own idea of well-formedness; **(b)** a
live smoke against the real endpoint or binary; or **(c)** a stated reason neither is available, so
the risk is accepted knowingly instead of by omission. A brief that describes in detail what we will
send, and never says how we established the far side takes it, has **not** answered — and the check
says so. The failure this catches is not a bug in our code: our code is exactly what we designed,
and the contract we designed against was never real. *Teaching example.* A codex **review** role's
`codex exec --output-schema` was handed a schema that is valid JSON Schema but invalid under OpenAI
strict mode. Every codex review dispatch failed at request time with a 400, and none ever
succeeded. A silent fallback to **the host model** made the loss read as a working cross-vendor
panel. The same class returns whenever a hand-rolled schema meets a vendor's rules: request-time
400s, and re-dispatches of a review that had already come back clean. One local validation of the
foreign contract's rules at brief time would have cost minutes.

## Supervised write dispatch

The sanctioned way to dispatch a long-running **external implementer** is the supervised runner. For
the full CLI argument surface, read `skills/workhorse/reference/dispatch-entry.md`.

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"
# Resolve implementer cell from dispatch calibration + registry (honor configured model pin)
read -r IMPL_ENGINE IMPL_ENGINE_MODEL IMPL_EFFORT <<<"$(python3 -B -c "
import sys
sys.path.insert(0, sys.argv[1] + '/lib')
import model_registry as mr
import preflight_probe as pp
row = next(r for r in pp.dispatch_calibration() if r.get('role') == 'implementer')
resolved = mr.resolve_dispatch('implementer', row['engine'], row['model'])
model = resolved['model_id']
effort = resolved['effort']
effort_s = '' if effort is None else effort
print(row['engine'], model, effort_s)
" "$ROOT_DIR")"
if [ -z "${IMPL_EFFORT}" ]; then IMPL_EFFORT_JSON=null; else IMPL_EFFORT_JSON="\"$IMPL_EFFORT\""; fi
IMPL_SEAT='{"vendor":"'"$IMPL_ENGINE"'","model":"'"$IMPL_ENGINE_MODEL"'","effort":'"$IMPL_EFFORT_JSON"',"role":"implementer"}'
# LAUNCH — first call on a fresh --run-dir; on dispatch-write --max-wait is also the git-preflight
# timeout, so size this slice to the repository's preflight cost, not just rotation headroom
python3 -B "$ROOT_DIR/lib/engine_dispatch.py" dispatch-write \
  --seat "$IMPL_SEAT" \
  --prompt-path "$ORDER_PROMPT" --cwd "$BUILD_WORKTREE" --order-id "$ORDER_ID" \
  --expect-item "<path-from-order>" \
  --run-dir "$RUN_DIR" --max-wait 45
# CONTINUATION — re-invoke while .terminal is false: full slice up to 540 s
python3 -B "$ROOT_DIR/lib/engine_dispatch.py" dispatch-write \
  --seat "$IMPL_SEAT" \
  --prompt-path "$ORDER_PROMPT" --cwd "$BUILD_WORKTREE" --order-id "$ORDER_ID" \
  --expect-item "<path-from-order>" \
  --run-dir "$RUN_DIR" --max-wait 540
```

`~/.cursor/cli-config.json` is **one global mutable permission file shared by every cursor
invocation on the machine** — not per-project and not per-run. Several sessions can write it at
once. A **`-f` write dispatch is immune** to whatever
that file contains; **any invocation without `-f` inherits whatever the last writer left**, which
may be another session's settings.

### Declared items

Repeat `--expect-item` for every file the order must deliver (or use `--expect-items-file` instead).
See `skills/workhorse/reference/dispatch-entry.md` for every flag on `dispatch-write`.

`$IMPL_ENGINE`, `$IMPL_ENGINE_MODEL`, and `$IMPL_EFFORT` come from the project's dispatch
calibration for the **implementer** role and the registry matrix cell for that engine — never
hardcode effort to one vendor's shape. Re-invoke the **originating verb** (`dispatch-write`, never `dispatch-poll`)
with the same `--run-dir` and `--max-wait 540` while `.terminal` is false. A non-terminal
`{"reason": "running", "terminal": false}` is **not** a forfeit. `dispatch-poll` is observational
and never spawns; `dispatch-abandon` abandons a run directory. Omitting `--max-wait` loops until
terminal in 540 s slices (below the 600 s foreground-conversion boundary on harness 2.1.219). The
runner owns the bound — its per-attempt timeout, journal, and bounded slice — so **do not compose a
separate per-dispatch watchdog** on top of it. **`cwd` must be a linked build worktree** — a primary
checkout is refused (`cwd-primary-checkout`) — which is exactly why this is the workhorse's
implementer path and not review-code's in-place fixer path.

### Write-report contract

This contract is the **marker channel's**; on the native channel the runner appends a contract
derived from the declared write schema instead and the sentinel plays no part.

On every `dispatch-write` call, the runner **appends** a write-report contract to the caller's
prompt — the caller does not author it and cannot opt out. It is **additional to** the prose receipts
the order asks for, never a replacement: the engine still returns those receipts, then ends with a
sentinel line (`<<<SUPERHEROES-WRITE-REPORT>>>`) followed by exactly one JSON object, then nothing
but whitespace.

**Field semantics.** `ok: true` means the engine ran the order to completion **as specified** — it
is **not** an acceptance verdict, and the implementer never marks its own work done. `ok: false`
carries `signal` of `"plan_wrong"` (the order's premise is wrong) or `"needs_context"` (anything
else). `evidence.testFailed` / `evidence.testPassed` report whether a test was **observed** failing
/ passing during that attempt.

**Grading is strict, and keyed to the prompt.** When the runner contracted the prompt, a report is
recognised only as a final tail matching this grammar: a line whose trimmed content is the sentinel,
then one JSON object (which may be pretty-printed across multiple lines), then nothing but whitespace
to the end. Leading whitespace on the sentinel line and blank lines before the object are accepted;
trailing prose after the object is not. No such report means `unreadable`; the runner does **not**
fall back to scanning the whole stream for any JSON object, because that scan is what produced the
false `needs_context` refusals. Prompted contracted-ness is keyed on the sentinel token (stable),
not the contract prose (expected to be edited). Prompts the runner did not contract keep the old
behaviour.

**Declared items (`--expect-item`, `--expect-items-file`).** Repeatable flags union with the file
(one path per line; `#` comments and blank lines ignored). At open time the runner normalizes paths,
captures a per-path `baselineDirty` identity map for any pre-existing dirty files, and persists
`expectedItems` in the journal. At collection time — only on the grade-ok success branch — a
membership check compares the declared set against the final diff; it can **downgrade** a success to
a forfeit but never upgrade or relabel a failure. When nothing was declared, behaviour is unchanged:
no `baselineDirty` capture, no `itemCheck` key. When declared, a passing result includes
`itemCheck` (`declared`, `expected`, `delivered`, `missing`). Terminal detail tokens:
`items-undelivered` (one or more paths missing; this forfeit **does** carry `itemCheck`); and
`item-evidence-unavailable:<cause>` (git
evidence could not be collected — causes include `falsy-base-sha`, `diff-timeout`, `diff-failed`,
`status-timeout`, `status-failed`). Open-time `unrunnable` detail `base-sha-unresolvable` refuses
when a declared run's `--base-sha` does not resolve. Other forfeits, `unrunnable`, and
`worktree-dirtied-by-attempt` never carry `itemCheck`. On marker-channel runs, when engine stdout
exceeds the **8 MiB capture cap**, the terminal forfeit carries a **stdout-capture-cap** reason class
of its own (`stdout-capped-by-attempt`) with an explicit truncation marker in
the captured stdout — it no longer surfaces under `worktree-dirtied-by-attempt`. Every forfeit detail above remains `ok: false`,
`forfeited: true`.

Evidence is the union of `git diff --name-status -z -M <baseSha>` against the **working tree**
(not `HEAD`, so a path committed and then reverted is not credited) plus on-disk paths from
`git status --porcelain=v1 -z -uall --ignored=traditional` that git cannot express in that diff.
Rename/copy records contribute both the old and new paths.

This is **final-diff membership, not proof of engine authorship**: it cannot distinguish created from
modified; a create-then-delete leaves no evidence and reads as missing; a concurrent writer could
supply a path. A file that was already dirty before the run and unchanged afterward is not credited
as delivered.

### Sibling worktree observation (`siblingWorktrees`)

On every **terminal** `dispatch-write` fold, the runner attaches a top-level `siblingWorktrees`
block recording an **unattributed observed delta**: whether any **other** registered worktree in the
same repository changed while this write run was open. It cannot say who changed a sibling worktree,
and it is **not** an escape claim. Concurrent authorized write dispatches in different worktrees
routinely produce deltas here — that is expected, legitimate concurrency, not a signal that
something went wrong. The block never affects `ok`, `terminal`, or `reason`.

| Case | `siblingWorktrees` |
|---|---|
| write run, baseline captured, second snapshot succeeded | `{"status": "observed", "deltas": [...], "truncated": <bool>, "coverage": {...}}` — `deltas` is `[]` when nothing changed; `coverage.signals.*.measuredBefore/After/compared` shows how much was actually observed (unmeasured signals are never reported as unchanged) |
| write run, baseline captured, one or more siblings unreadable | `observed` with `deltas` containing `{"kind": "unreadable", "reason": ...}` for those paths while other siblings still compare normally |
| write run, baseline missing (a run opened before this change) | `{"status": "indeterminate", "reason": "no-baseline"}` |
| write run, baseline not a dict | `{"status": "indeterminate", "reason": "baseline-invalid"}` |
| write run, either snapshot indeterminate | `{"status": "indeterminate", "reason": "<why>"}` |
| **preflight-terminal** result (refused before the run opened, never reaches fold) | **key absent** — there was no run to observe |
| review run | **key absent** |

## Refusal streak — shell health

Three refusal round-trips in a row on one caller's dispatch invocations is the shell's health
condition. A refusal that cost the caller a round counts, and a refusing continuation call counts too.
You observe the streak at a vet or a consuming project reports it. The streak **proposes** at the
next gardening pass and never executes anything. There is no counter, no instrument, and no journal
field — this is a sentence people read, not machinery.

Read the streak honestly. The streak is the observation. "The shell is bouncing callers" is the
inferred cause. "One caller's bad script" is the alternative reading that sits beside it.

## Engine forfeits and order shape

**Run-dir caller traps** — read these before you compose a dispatch:

- **Trap 1 — a leaf symlink `--run-dir` is refused.** The refusal token is `run-dir-is-symlink`.
  Only the **leaf** path component must not be a symlink; symlinked ancestors (e.g. macOS `/tmp` →
  `/private/tmp`) are physicalized and accepted.
- **Trap 2 — `attempts: 0` means a caller error, not an engine forfeit.** An `unrunnable` result
  carrying `attempts: 0` means **nothing was ever spawned** — the runner refused the call. **Read the
  reason before blaming the engine.** This matters because the reflex on a failed dispatch is to
  escalate or re-dispatch against a different engine, and neither fixes a caller error.

An external engine can forfeit *after* writing files — characteristically with cursor's
**`NonRetriableError "Agent Looping Detected"`** while the engine is producing a long report, with
on-disk work already complete and correct.

**Long cursor write dispatches.** A long cursor `dispatch-write` run can forfeit after its work lands
(`worktree-dirtied-by-attempt`): no admissible result is graded — `attemptDetail` names why (for
example `native-result-missing`) — and a partial landing can lack its tests. Split long write
orders into smaller ones. After any write forfeit, verify the declared paths yourself — that each
is present and that its tests exist and run — before you re-order. Never retry a forfeit blind.

**Inspect the worktree before discarding or re-dispatching** — "inspect the diff" alone is not a
decision rule:

- **What the tree inspection establishes.** Before dispatching, the build worktree must be **clean** —
  `git status --porcelain` empty, with landed work already committed. This reference makes that
  baseline explicit and strengthens it; related charter obligations are §6 (commit before the next
  order against a worktree) and §8 (commit before a mutation probe). Capture the baseline with the
  probe in § Check-runner — a plain shell task: `git rev-parse HEAD`, that empty `git status --porcelain`, and
  `git reflog --date=iso HEAD | wc -l`. If the
  tree cannot be made clean, use a **fresh worktree** or **park** — never dispatch against a dirty
  baseline, and never treat a delta measured from one as authorship evidence. Against a clean baseline,
  spanning committed/staged/unstaged/untracked: whether **this dispatch** wrote anything at all (**no
  delta = it wrote nothing the probe can see** — ignored paths are outside it; see **default to a
  fresh worktree** below when they could matter — authorship evidence only), and whether what it wrote
  is **inside the order's scope**. For an **INDETERMINATE** dispatch — timeout or child never joined —
  the delta test yields no conclusion: **no delta** does not establish that it wrote nothing.
  The delta test is an
  **authorship and scope** check — each named target must **differ from that baseline**, not merely
  exist.
- **What it does not establish.** A delta on every named target proves each was **touched**, not that
  the order was **finished** — a partial edit to every target passes it. **Completeness and correctness
  are established only by the orchestrator's own verification against the order's acceptance items**,
  plus standing in for the three evidence channels the forfeit destroyed: the **per-edge fail-closed
  dispositions** (validity rule 2), the **order-validity findings** the implementer would have raised,
  and any **test change** (was it order-authorized, and does it match the named assertion?). Gate-green
  does not re-derive any of the three. **All three are the orchestrator's to reconstruct**, not just the
  fail-closed edges.
- **The default when you cannot establish it.** If the orchestrator cannot establish completeness and
  correctness itself, **re-dispatch is the default, not recovery** — and a re-dispatch must not ride
  the abandoned attempt. **Before any same-worktree reset**, the supervised runner
  (`engine_dispatch.py`) must report that the dispatch's process group is **dead** — not merely that
  the run is terminal. A terminal receipt alone is insufficient: `dispatch_abandon` can return
  `terminal: true` with `abandonDetail: engine-death-unconfirmed`; `engine-launch-uncertain` and
  `journal-corrupt` are likewise terminal without establishing death. Those states — and any other
  terminal outcome the runner does not treat as confirmed death — route to a **fresh worktree** or
  **park**, never a reset. **Default to a fresh worktree** whenever ignored state could matter. Narrow
  recovery — only when the runner has confirmed death and ignored state demonstrably cannot matter —
  is `git -C <build worktree> reset --hard <baseline SHA>` plus `git -C <build worktree> clean -fd`.
  That recipe restores tracked content to the baseline SHA and removes untracked, **non-ignored** files
  and directories; git will **not** remove an untracked nested repository with `-fd` alone (it requires
  `-ff`), so a nested repo the implementer created survives this step and leaves the worktree dirty —
  use a **fresh worktree** for that case too. It does **not** restore ignored paths,
  which survive both commands and are invisible to `git status --porcelain` (`docs/`, `__pycache__/`,
  `.pytest_cache/`, `.coverage`, `htmlcov/`, `.venv/`, and the rest of the repository's `.gitignore`), so
  a re-dispatch on that worktree can inherit leftover ignored state. **Do not** use `-fdx`: it would
  sweep gitignored local-only content such as `docs/` that no baseline SHA restores and that are not
  dispatch output — and `-fd` is not safer for every local file: it protects only **ignored** paths;
  an untracked-but-not-ignored file at the worktree root is removed by `-fd` exactly as `-fdx` would
  remove it. Park when neither a fresh worktree nor confirmed narrow recovery is available.
  Re-dispatching without looking re-does correct work and re-runs the very report that forfeited.

Author orders so the forfeit does not fire: keep in-dispatch verification targeted and returns short
and structured. The implementer template `agents/implementer.md` states this to the implementer
directly, so an order that additionally demands a full-suite run, a pasted diff, or a long verbatim
report is **overriding the template against its own purpose**.

An external engine's shell availability is set **outside your build** — **never assume the
implementer can run anything**; the engine CLI consults its own permission surface, not your order. It is
normally available on the sanctioned write path (so a blocked shell is not the expected state). But
a whole build can have **every** implementer shell call rejected, for a cause not yet known, so
availability cannot be inferred from a previous build. Write every external order to be correct when the
implementer can run nothing; the orchestrator's own re-run is the verification either way, and a
corrective round is worth budgeting.

## Check-runner — a plain shell task

A `check-runner` seat runs commands you author and writes their raw output to disk. It is a plain
shell task: judgment-free, and it certifies nothing, so what it produces is evidence, never a
verdict. Use it when a run's volume, noise, or duration is the problem. It buys context relief, not
trust, so treat its output exactly as you treat an implementer's. The seat's side of the contract
is `agents/check-runner.md`.

1. **Author the command list.** Write the exact commands, with a byte ceiling per command and an
   order-wide ceiling. Nothing else bounds the sum. For each command, name the paths outside the
   repository where the seat writes its stdout, stderr, and exit code.
2. **Resolve the model.** Run `lib/dispatch_guard.py` with a `--seat` naming role `"mechanical"`,
   the host's own vendor, and a null `model`. The call is a query that resolves the seat default
   (`effort_source: "default"`).
   - Exit 1 with `reason: "allowlist-refused"` and a `seat_detail` naming no sanctioned model for
     the role on this vendor means the route is unavailable. Run the commands yourself and disclose
     the fallback.
   - Exit 1 with any other `reason` or `seat_detail` (a mistyped `--seat`, an off-allowlist model,
     any other refusal) parks.
   - Exit 0 dispatches the seat as a host subagent (`Agent` on Claude, `spawn_agent` on Codex),
     never to an external engine. Record the resolved `model_id` and `effort`. The seat renders no
     judgment, so no independence or maker-family constraint applies.
3. **Probe the tree before.** Commit the landed work first, so the baseline is clean. Then capture
   `git rev-parse HEAD`, the full `git status --porcelain`, and
   `git reflog --date=iso HEAD | wc -l`. Use the full status, never `-uno` or its long form
   `--untracked-files=no`: a run's untracked output is exactly what you want to see.
4. **Dispatch the seat.** Await it in-turn (§ Awaiting a dispatch — the in-turn contract).
5. **Probe the tree after.** Capture the same three signals. Any delta is a failed verification,
   not a warning. A dispatch that timed out, or whose child you never joined, is **INDETERMINATE**,
   never clean. Ignored repository state (bytecode, test caches, coverage artifacts) is outside the
   probe. Disclose what the probe cannot see as a residual, never as covered.
6. **Read the captures off disk.** The seat's return prose is never the receipt. For each command
   you authored, read the first line of the capture at the path you named for that command. That
   line opens `# ran: <command>`. Compare it with that command. A `# ran:` line anywhere else in a
   body is output, not a receipt.
7. **Quote, then remove.** The captures are working artifacts, and the PR record is the durable
   receipt. Quote what matters into the PR record, redacted of secrets, tokens, private URLs, and
   personal data. Remove the captures once verification closes. An interrupted order leaves its
   captures in session scratch until someone clears them.

If the seat needs a stronger model to do its job, your command list was under-enumerated. Rewrite
the list, or run the commands yourself.
