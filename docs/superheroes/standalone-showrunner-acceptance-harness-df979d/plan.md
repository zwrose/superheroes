---
superheroes: doc
schemaVersion: 1
docType: plan
workItem: standalone-showrunner-acceptance-harness-df979d
issue: null
size: medium
status: approved
gates: {review: passed}
producedBy: "the-architect@0.3.0"
created: "2026-07-02"
updated: "2026-07-02"
---
# Standalone showrunner acceptance harness — Plan

## Overview

This durabilizes the one-shot manual acceptance run that `eval/showrunner_live_acceptance.md`
describes ("Durable repeatable acceptance is #112") into a single owner-invoked command: launch
the real showrunner on a canned throwaway fixture work-item in the real repo, let it run its
whole pipeline to a ready-for-review PR, judge the terminal outcome against machine-checkable
facts, tear down every artifact the run created, and hand back one plain-language pass/fail
verdict — unattended.

The strategy is a thin **orchestrator that runs the showrunner in a separately killable child
process** plus a set of **pure Python deciders** (verdict, readout-consistency, ceiling-breach,
retry-classification, cleanup-plan), mirroring the band's established split: scripts orchestrate,
judgments are pure and unit-testable (CONVENTIONS §10.1). The child is a **headless host
session** — the `claude` CLI in non-interactive mode driving the `superheroes:showrunner` skill,
which invokes the Workflow tool on the committed bundle exactly as production does. (The bundle
is *not* a standalone Node program: its `agent` dispatch and `args` binding exist only inside the
Workflow-tool runtime, so the launch vehicle must be a host session; the harness spawns it as its
own process group so it can be hard-killed.) The harness performs **no model-driven judgment**
(NFR: cost) — every assertion is a plain lookup against the run's already-shipped
machine-readable run-outcome projection (`run_readout.run_outcome`, the "#112 consumer contract"
that already exists) and against live `gh` facts; the headless driver session is the one
model-touching piece, a bounded launch vehicle whose spend the invocation ceilings themselves
govern. It reuses the existing launch contract (`lib/preflight.py` + the `showrunner` skill's
Workflow-tool invocation of `lib/showrunner.bundle.js`) and the existing artifact-lifecycle libs
(`lib/buildtree.py` teardown/reap, `lib/control_plane.py` store, `lib/fence_cli.py` /
`ref_lock` lease) rather than inventing parallel machinery. The one genuinely new structural
piece is running the showrunner **out-of-process** so a ceiling breach can be enforced — and the
child's whole process group killed — from outside the run it is testing.

## Goals & non-goals

**Goals** (from the spec):
- One owner command that launches a full showrunner run on a canned fixture work-item, stamped
  with a run identifier unique and recognizable as the harness's (FR-1, FR-2).
- A deterministic pass/fail verdict computed only from machine-checkable facts, including a
  readout-vs-reality consistency check (FR-3, FR-4, UFR-9).
- Exactly one durable result record and exactly one plain-language verdict report per invocation
  (FR-5, FR-6).
- Teardown of every harness-created artifact on every exit path, idempotent, touching only what
  the harness created (FR-7, UFR-1, UFR-3).
- Invocation-scoped elapsed/spend ceilings enforced from outside the run, killing it on breach
  (FR-8, UFR-2).
- At most one automatic retry, environmental-only, sharing the invocation's remaining budget
  (FR-9).
- Structural refusals for the guard cases: concurrent run, nested invocation, missing/drifted
  prerequisites, unconfirmable-liveness reclaim (UFR-4, UFR-5, UFR-7, UFR-8), and structural
  never-merge protection of real state (UFR-6).

**Non-goals** (deliberately excluded here — the spec's Out-of-scope plus scope discipline):
- **No modality seam through test-pilot.** Standalone skill + small lib now; fold into
  test-pilot only if a second agentic-workflow consumer appears (the discovery reshape;
  [[named-consumer-before-producer]]).
- **No scheduled / per-change cadence** and **no best-of-N confidence modes** — on-demand,
  k=1 with one environmental retry only.
- **No sandbox repo** — runs happen in the real repo, protected structurally.
- **No LLM-judge** of any readout prose — every verdict input is a plain lookup.
- **No repair of the showrunner** — the harness detects regressions; it does not fix them.
- **No new persistent daemon / scheduler** — the ceiling watch lives only for the invocation.

## Architecture

Two layers, matching the band posture (CONVENTIONS §10.1: "scripts orchestrate; leaf agents /
pure deciders do single-purpose work"), plus one owner-facing skill front door.

1. **`superheroes:acceptance` skill (the front door).** An owner-invoked skill that is a thin
   control-flow shell: it resolves the fixture, runs the pre-launch guards, invokes the
   orchestrator, and renders the verdict report. It performs **no** judgment itself — it forwards
   to the deciders. It refuses when invoked from inside a showrunner run (UFR-5) by reading an
   **ambient execution-context signal** — an environment marker the launcher sets on the child
   host session (propagated into its subagents) that means "you are running *inside* an
   acceptance/showrunner run." This is deliberately **distinct** from `preflight.decide`'s
   `active_run` signal: `active_run` is on-disk run *state* (whether some work-item holds the
   current-marker/lease — UFR-4's concurrent-run condition, derived from
   `control_plane.get_current`), which is not a reliable proxy for *execution-context* nesting
   (it reads `none` if the nested call resolves a different store root or the marker is unset at
   that moment, and the UFR-5 refusal would then fail open). UFR-5 therefore has its own named
   signal; UFR-4's `active_run` is not reused to satisfy it.

2. **The orchestrator (`lib/acceptance_run.py`, control-flow).** Owns the invocation lifecycle:
   acquire the harness lease → pre-launch reconcile (UFR-8 reclaim / UFR-4 refuse) → materialize
   the fixture work-item into a stamped throwaway work-item → **launch the showrunner in a child
   process group** — a headless host session (`claude` CLI, non-interactive) that drives the
   `superheroes:showrunner` skill on the stamped fixture, i.e. the same Workflow-tool-on-bundle
   path production uses. (A plain `node lib/showrunner.bundle.js` child is infeasible: the
   bundle's `agent`/`args` bindings exist only inside the Workflow-tool runtime, and the spine
   has no headless entry.) → sample elapsed/spend and act on `acceptance_ceiling.decide`,
   killing the child's whole process group on breach (FR-8, UFR-2) → on child exit, read the
   terminal run-outcome from the run's durable records (the control-plane run record /
   `run_readout.run_outcome` — never a return value from the session) and hand it to the
   deciders → run teardown → write the result record → release the harness lease (only after
   the record is durably written) → emit the verdict report. It never itself
   decides pass/fail, consistency, ceiling breach, retry-eligibility, or what to reap — it calls
   the pure twins for each and acts on the returned decision.

3. **The pure deciders (the judgment, one module per concern, all unit-testable).** Faithful to
   the band's "pure decide() over a dict" precedent in `lib/preflight.py` (module names pinned
   here — the `acceptance_*` file names in Components are the same modules):
   - `acceptance_verdict.decide(facts)` — FR-3/FR-4/UFR-9: computes pass only when every listed
     fact is present, true, and readable; else fail naming the false/unreadable fact. Includes
     the readout-vs-reality consistency comparison.
   - `acceptance_ceiling.decide({elapsed_sec, spend_sampled, spend_readable, ceilings, attempt,
     budget_consumed})` — FR-8/FR-9/UFR-2: returns `continue` | `kill(elapsed)` | `kill(spend)`
     and computes the remaining budget a retry inherits; when spend is unreadable it governs on
     elapsed alone and says so (fail-closed on the readable ceiling). The launcher only samples
     and acts — which ceiling tripped is this decider's call, unit-tested with no live run.
   - `acceptance_retry.classify(failure_facts)` — FR-9/UFR-9: environmental vs behavioral vs
     unconfirmable (fail-closed → behavioral → no retry).
   - `acceptance_cleanup.plan(discovered_artifacts, run_stamp)` — FR-7/UFR-3/UFR-8: the set of
     reaps to run, restricted to artifacts whose names **parse to a valid full harness stamp**
     (never a bare prefix/substring match); idempotent (empty plan on already-clean). Anything
     matching the reserved harness prefix but failing the full-stamp parse is routed to the
     UFR-3 reported-left-behind path — never deleted.
   - `acceptance_reclaim.decide(recorded_state, liveness)` — UFR-4/UFR-8: reclaim only on
     confirmed death; refuse on unconfirmable; refuse (in-flight) on confirmed-alive.

The orchestrator runs **outside** the pipeline it tests: the showrunner child gets the fixture
work-item and the normal store; the harness's own lease + result record live under the harness's
own namespace in the control-plane store (`lib/control_plane.py`), never touching a real
work-item's records (UFR-6). Structural never-merge is enforced by the enforcer's **deny-only
mode**: the launcher sets an **enforcement environment marker** on the child (inherited by every
subagent, independent of cwd/worktree/store resolution), and the band's claude-host PreToolUse
wiring (`hooks/hooks.json` → `lib/enforcer.py` — the hook file whose matchers actually fire in a
`claude` child) honors it, so every owner-authority action — merge-pr / merge-api /
merge-graphql / release / run-workflow / force-push / push-to-default — is **denied by
structure** (allowance overlays not honored under the marker), not routed to the live `ask` the
unmarked interactive posture returns (an `ask` that, with no human at the root of a
non-interactive session, would either hang or — under a broad pre-approval — fail open into a
real-repo merge).
The showrunner itself never merges, and the harness adds nothing that could; the deny-only host
is the structural floor that keeps a *regressed* showrunner's merge/push attempt from succeeding
against real state — the exact regression this harness exists to catch.

## Components & interfaces

- **`skills/acceptance/SKILL.md`** — owner front door. Inputs: none (canned fixture, no
  free-form input — closes the UFR-7 "no free-form input" surface). Outputs: the verdict report
  (stdout) and side-effect: exactly one result record on disk. Resolves host-neutral actions via
  the host tool map like every other skill (CONVENTIONS §7). Contract: refuses (before any launch
  or create) on nested invocation, and otherwise delegates the whole invocation to the
  orchestrator.

- **`lib/acceptance_run.py`** — the orchestrator + JSON CLI (`--fixture`, `--root`; ceilings from
  config with built-in defaults). Contract: on any exit it has written exactly one result record
  and printed exactly one verdict report. Error cases: its own internal error is caught, still
  runs teardown, and produces a fail verdict naming the harness error (FR-7) — a harness error
  never yields pass. Depends on: the deciders, the launcher, `buildtree`, `control_plane`,
  `ref_lock`, `run_readout`, `gh`.

- **`lib/acceptance_launch.py`** — the child-process launcher + ceiling watch, kept mechanical
  (sampling + process control only; breach judgment lives in `acceptance_ceiling`). Inputs: the
  stamped work-item, the resolved ceilings. Behavior: spawns the headless host-session child as
  the leader of its **own process group** (`start_new_session=True`), setting an
  **execution-context environment marker** on the child (inherited by its subagents) that the
  `acceptance` skill reads to refuse a nested invocation (UFR-5) — a signal independent of the
  on-disk `active_run` state, so nesting is caught by execution context rather than by run-state
  proxy. **Permission posture
  (stated):** the child session runs non-interactive under a **harness-scoped permission
  profile** passed at spawn (a settings/allowlist profile that pre-approves the pipeline's known
  *non-owner* tool surface — there is no human at the root of a non-interactive session to answer
  a gated `ask`) with the **enforcement environment marker** set on the child, switching the
  band's claude-host enforcer (`hooks/hooks.json` → `lib/enforcer.py`, the wiring that actually
  fires in a `claude` child) into **deny-only mode**. This is the UFR-6 structural
  floor and it is deliberate: unmarked, an owner-authority action returns `ask` (a live
  human prompt) which, in a headless session with a broad pre-approval, could **fail open** into a
  real-repo merge/push; under the marker the same enforcer returns **`deny`**, so
  merge-pr / merge-api / merge-graphql / release / run-workflow / force-push / push-to-default are
  structurally blocked regardless of the allowlist — single-use allowance overlays are **not
  honored** in deny-only mode, so the child cannot mint its way past the floor — and the
  pre-approval profile explicitly
  **excludes** the owner-authority set (it can never widen a gated action back to allow). If a gate
  still fires (a denied call, or a session that stops progressing on one), the launcher detects it
  and the invocation is reported as a **launch-environment failure, not a pipeline failure** — the
  same discipline as the UFR-7 drift rule; a denied *owner-authority* call specifically is the
  UFR-6 structural block having fired, recorded as such and never a pass. It samples elapsed time and
  cumulative spend, feeds each sample to `acceptance_ceiling.decide`, and on a kill decision
  signals the **whole group** (`killpg` SIGTERM→SIGKILL escalation), returning a `killed` outcome
  carrying which ceiling tripped; on natural exit returns the child's terminal run-outcome
  location. Spend source (named): the child session's own machine-readable usage/cost output
  (the headless CLI reports per-message usage and total cost) aggregated by the launcher — the
  showrunner spine tracks per-leaf token usage inside its review telemetry but journals no
  cost/dollar spend and no cross-phase spend total, so the session's reporting is the only real
  spend source.
  **Scope (disclosed, never silent):** that sample covers the claude session's own spend only —
  leaves the pipeline dispatches to an external engine CLI (Codex/Cursor, per the project's
  `enginePreferences`) consume outside the session's usage stream and are invisible to it, and
  the sample still *reads* cleanly, so this is not the "cannot be sampled" case. Whenever the
  run's engine preferences resolve any leaf role to an external engine, the launcher therefore
  marks the record's spend as **partial** (the FR-5 spend element is never reported as complete
  when it is not) and the elapsed ceiling is the disclosed backstop bounding engine-side spend.
  Separately, when spend cannot be sampled at all, only the elapsed ceiling governs and that gap
  is noted in the result (fail-closed on the readable ceiling). Contract: "confirmed dead" — the UFR-2
  precondition for cleanup — means the process **group** has no surviving members (not merely
  that the direct child exited), so orphaned `git`/`gh`/engine-CLI grandchildren cannot keep
  spending or mutating repo state after the kill; if group membership cannot be enumerated, the
  launcher refuses to start teardown and surfaces it on the UFR-3 leftover path (a descendant
  that double-forked out of the group is the residual case, swept by UFR-8's next-invocation
  reclaim). Testability: the child handle, clock, and spend-sample source are injectable, so the
  SIGTERM→SIGKILL escalation, the group-death gate, and the cleanup-only-after-confirmed-death
  ordering are proven against a scripted fake child in unit tests — no live run required (and
  the orchestrator's one-record/one-report exit contract gets the same stubbed-launcher test
  path).

- **`lib/enforcer.py` deny-only mode (additive, built with this work-item)** — when the
  launcher-set **enforcement environment marker** is present, owner-authority classifications on
  the claude host that would return `ask` are returned as **`deny`**, and single-use allowance
  overlays are **not honored** (the child cannot mint its way past the floor). The marker rides
  the process environment — inherited by every subagent and grandchild wherever it executes
  (build worktrees, out-of-repo storage, any cwd) — so the floor never depends on repo-relative
  or store-resolved state and cannot fail open on a resolution miss. `hooks/hooks.json` (the
  claude-host hook file whose `Bash`/`Edit|Write|MultiEdit` matchers actually fire in a `claude`
  child; the band's hooks fire inside subagents) needs no matcher change — the mode lives inside
  `enforcer.py`. **Scope (stated):** claude-host PreToolUse hooks do not fire inside
  external-engine (Codex/Cursor) CLI children, so this floor covers claude-host leaves only; the
  harness closes that gap by launching the fixture run with every role's engine preference
  resolved to `claude` (a harness run dispatches no engine leaves), and engine-side enforcement
  remains the engine-authz seam's concern (#128), outside this floor.

- **`lib/acceptance_fixture.py` + `eval/fixtures/acceptance/`** — the canned fixture definition
  (an approved spec/plan/tasks pair for a one-task, one-file change with no open choice) and a
  materializer that stamps it into a fresh throwaway work-item slug per launch (FR-1, FR-2). It
  also exposes a **drift check** (UFR-7): the fixture's expected phase list must equal the
  pipeline's current phase list, and its single target file must still exist. Contract: two
  consecutive materializations never collide. The stamp is a **full, structurally-parseable
  token** — the reserved harness prefix plus a per-launch unique id — embedded whole in a
  defined name position of every artifact it marks (slug, branch, PR title); the reserved prefix
  is a harness-owned namespace, and discovery/cleanup match the complete token shape, never a
  bare prefix or substring (see `acceptance_cleanup`).

- **The five pure deciders** (`lib/acceptance_verdict.py`, `lib/acceptance_ceiling.py`,
  `lib/acceptance_retry.py`, `lib/acceptance_cleanup.py`, `lib/acceptance_reclaim.py`) — each a
  pure `decide()`/`classify()`/`plan()` over a plain dict, no I/O, mirroring `preflight.decide`.
  Outputs are plain verdict/plan dicts.

- **`lib/acceptance_result.py`** — the durable result-record writer/reader (one schema, one
  record per invocation) and the verdict-report renderer (FR-5/FR-6), modeled on
  `lib/loop_readout.py` (schemaVersion-guarded, never raises). The record covers every attempt
  within the invocation and lists at least: verdict, reason, PR link (if any), phases traversed,
  spend + elapsed, launch + termination timestamps, and whether a retry happened.

Reused unchanged (interface consumers, not producers): `lib/preflight.py` (the same guards, run
against the fixture work-item), `lib/showrunner.bundle.js` (the launch payload — invoked via the
`showrunner` skill's Workflow-tool path inside the headless child session, never as a bare
`node` program),
`run_readout.run_outcome` (the terminal fact projection), `lib/buildtree.reap_one` /
`teardown` (artifact removal), `lib/control_plane.py` (the store), `lib/ref_lock` /
`fence_cli.py` (the harness lease).

## Data flow & data model

Flow of one invocation: skill → `acceptance_run.decide-to-launch` (reclaim/refuse) → fixture
materialize (writes a stamped throwaway work-item into the doc store, `gates.review: passed` so
preflight admits it) → `preflight.decide` on the fixture → spawn the headless-session child in
its own process group → child drives the
pipeline and writes its own `terminal-record.json` + run-outcome under the fixture's run dir →
launcher returns terminal location (or `killed`) → orchestrator reads run-outcome + live `gh`
PR/check facts → `acceptance_verdict.decide` → `acceptance_cleanup.plan` → reaps →
`acceptance_result` writes the record → the harness lease is released → the report is rendered.

**Invocation-end ordering + failure handling (invariant):** the harness lease / in-flight marker
is released **only after** the result record is durably written — the lease is the UFR-8 reclaim
trigger of last resort, so it must outlive teardown and the record write (a crash in the
teardown→record window therefore still leaves the recorded in-flight state for the next
invocation to reclaim). If the record write itself fails, the invocation ends **with the lease
still held** and a report naming the write failure, so the next invocation's UFR-8 path finds
the in-flight marker and writes the missing failed record — no invocation can end both
record-less and lease-less.

Data model — two small new shapes (call-out per the template; both are additive and local to the
harness, so backward-compat is trivial — nothing else reads them):

- **The result record** (`acceptance-result.json`) — versioned (`schemaVersion`), one per
  invocation, under the harness namespace in the control-plane store. Read only by the harness's
  own reader + UFR-8 reclaim (to check "does the orphan already have a record?"). One-way-door
  status: **low** — it is internal, single-reader, additively versionable; treated as reversible.
- **The harness lease / in-flight marker** — a control-plane ref under the harness namespace,
  reusing the existing `ref_lock` generation mechanism (`fence_cli.py`). No new persistence
  engine; it rides the git-ref coordination the band already uses (CONVENTIONS §4.4/§4.5).

The fixture's own docs (spec/plan/tasks) are a **committed, in-repo fixture** under
`eval/fixtures/acceptance/`; each *run* materializes a throwaway *copy* stamped with the run id
into the (gitignored) doc store, which teardown removes. No real work-item's records are ever the
target (UFR-6).

## How the requirements are met

- **FR-1** (launch, unique stamped run id): `acceptance_fixture` materializes a per-launch stamped
  throwaway work-item; the stamp — a full, structurally-parseable token (reserved harness prefix
  + per-launch unique id) — is embedded whole in the slug/branch/PR so two launches never collide
  and every artifact is recognizable as the harness's (used by UFR-8 discovery). The reserved
  prefix is a harness-owned namespace: the pre-launch guard refuses (rather than sweeps) when a
  prefix-matching artifact fails the full-stamp parse.
- **FR-2** (one-task/one-file fixture traversing every phase): the committed fixture is a single
  task touching a single file with no open choice; its expected-phase list equals the pipeline's
  and is drift-checked (UFR-7).
- **FR-3** (verdict from facts): `acceptance_verdict.decide` returns pass only when terminal ==
  ready, PR exists + ready-for-review, checks green, all expected phases traversed, and the
  readout exists with the PR link; otherwise fail naming the false fact. Retried invocation: the
  verdict is computed from the final attempt's terminated run.
- **FR-4** (readout-vs-reality consistency): the verdict decider compares the run readout's
  claimed check status and claimed PR against the live `gh` check status and the PR that actually
  exists; any mismatch → fail with an "inconsistent with reality" reason.
- **FR-5** (one durable result record per invocation): `acceptance_result` writes exactly one
  record covering every attempt, with all listed elements; UFR-8 reclaim writes one for an
  orphan **only if it has none** (never a second). The harness lease is released only after this
  record is durably written; a failed write ends the invocation with the lease held, so the next
  invocation's UFR-8 path writes the missing failed record — the backstop always has a trigger.
- **FR-6** (one verdict report, four elements): the renderer emits exactly one report per
  invocation with verdict, reason, record location, and cleaned-up/left-behind — never one per
  attempt.
- **FR-7** (teardown every exit, only harness artifacts, idempotent): `acceptance_cleanup.plan` +
  `buildtree.reap_one`/`teardown` close the PR, delete the branch, remove the working copy and
  run-state; the plan is scoped to the run stamp so real branches/PRs/records are untouched; a
  second run on a clean state is a no-op success. A harness internal error still runs teardown
  and yields a fail verdict naming the error.
- **FR-8** (invocation-scoped ceilings, external): `acceptance_launch` samples elapsed + spend
  (from the child session's machine-readable usage/cost output) from the parent process and acts
  on `acceptance_ceiling.decide` against config ceilings (built-in defaults when unset); the same
  decider computes the remaining budget a retry shares — all of it unit-tested without a live
  run. The sampled spend ceiling governs claude-session spend; engine-dispatched leaf spend is
  outside that stream, so when engine preferences resolve to an external engine the record marks
  spend **partial** and the elapsed ceiling is the disclosed backstop (see `acceptance_launch`).
- **FR-9** (≤1 environmental retry, budget-shared): `acceptance_retry.classify` gates retry to
  confidently-environmental failures; the retry cleans the first attempt first, relaunches with a
  fresh stamp, and the invocation still yields one record covering both. If pre-retry cleanup
  fails → no retry, end on the UFR-3 cleanup-failure path. If the retried attempt fails for any
  reason → no further retry.
- **UFR-1** (parked run): a non-ready terminal → fail carrying the park reason; teardown still
  runs.
- **UFR-2** (ceiling breach): the launcher kills the child's whole process group
  (`killpg` SIGTERM→SIGKILL) and returns which ceiling tripped (per `acceptance_ceiling.decide`);
  teardown begins only after the group is confirmed empty — "can no longer act" means no
  surviving descendant, not just a dead direct child.
- **UFR-3** (cleanup failure): the cleanup plan reports exactly which artifacts survived; the
  record is still written; the verdict report offers one re-runnable cleanup action (re-invoke
  the orchestrator's reclaim path, which is idempotent).
- **UFR-4** (concurrent second run): `acceptance_reclaim.decide` returns refuse-in-flight when a
  confirmed-alive run holds the lease; the skill refuses naming it, creating nothing.
- **UFR-5** (nested invocation): the skill reads the launcher-set **execution-context environment
  marker** (propagated into subagents) — a signal distinct from `active_run`'s on-disk run state —
  and refuses before launching anything; because the marker rides execution context rather than
  run-state, it does not fail open when `active_run` would read `none` in a nested call.
- **UFR-6** (never mutate real state): structural — the launcher sets the **enforcement
  environment marker** on the child, switching the band's claude-host enforcer
  (`hooks/hooks.json` → `lib/enforcer.py` deny-only mode) so every owner-authority action
  (merge-pr / merge-api / merge-graphql / release / run-workflow / force-push /
  push-to-default) is **denied** — not routed to a live `ask` that a headless run could never
  answer (or could fail-open on) — with allowance overlays not honored under the marker and the
  marker riding execution context (env-inherited by all descendants, valid in build worktrees
  and out-of-repo storage alike); the harness permission profile excludes the
  owner-authority set from pre-approval so the allowlist can never widen it back to allow, and
  the fixture run resolves every role's engine preference to `claude` so no engine-dispatched
  leaf exists outside the hook floor. On top
  of that structural floor, the harness only ever closes the fixture PR, ceilings/records live
  under the harness namespace, and the target is always a stamped throwaway work-item; the default
  branch and real records are unchanged after any run. An acceptance criterion: a showrunner
  attempt to merge / release / push-to-default during a run is structurally **blocked (denied)**,
  not merely un-attempted, and does not depend on an interactive `ask`.
- **UFR-7** (missing/drifted prerequisites): `preflight.decide` (calibration, `gh` access,
  no-active-run, repo-ready, verify/config-resolves) plus the fixture drift check (absent fixture,
  phase-list drift, missing target file) each refuse before launch, naming the missing/drifted
  piece — drift is never reported as a pipeline failure.
- **UFR-8** (reclaim on confirmed death; orphan artifacts): `acceptance_reclaim.decide` +
  stamp-scoped artifact discovery: a confirmed-dead run's leftovers (with or without recorded
  state) are found, reported, and cleaned before the fresh launch; an orphan without a record gets
  one (failed); unconfirmable liveness → refuse (as UFR-4). Record-less discovery matches the
  **complete stamp token shape** in its defined name position — destructive actions
  (close PR / delete branch / remove copy / remove record) are emitted only for artifacts whose
  names parse to a valid full stamp; a prefix match that fails the parse is reported and left
  behind for the owner (UFR-3 path), never swept.
- **UFR-9** (unreadable fact): the verdict decider treats any unreadable required fact as fail
  naming that fact — never pass, never a silent retry; the same fail-closed rule governs
  `acceptance_retry.classify`.
- **NFRs**: *Cost (harness)* — no model-driven judgment; every verdict input is a lookup. The
  headless driver session that carries the run is the one model-touching piece — a disclosed,
  bounded launch overhead governed by the same invocation ceilings and counted in the record. *Cost
  (fixture)* — the cheapest one-task/one-file fixture. *Verdict determinism* — pure deciders over
  a fixed terminal state yield identical verdict + reason every time. *Unattended* — no owner
  input from launch to report; made true structurally by the child session's harness-scoped
  permission profile on the **deny-only enforcer host** (owner-authority actions are denied, not
  turned into a gated `ask` that would wait on an absent human — a gate that still fires is a
  reported launch-environment failure, not a hang). *Privacy* — the record + report stay local; the harness publishes
  no captured text to the code host.

## Key decisions & alternatives

- **Decision:** Run the showrunner **out-of-process as a headless host-session child (own process group), not in-process/in-thread and not a bare `node` child**. · **Options weighed:** (a) a headless host session (`claude` CLI, non-interactive) driving the `showrunner` skill — the Workflow tool on the committed bundle — spawned as a process-group leader the harness supervises + can kill; (b) invoke the showrunner in-process and cooperatively poll a soft budget; (c) `node lib/showrunner.bundle.js` directly. · **Choice + why:** (a) — FR-8/UFR-2 require the ceiling enforced *from outside the run itself* and the run *stopped without waiting for it to finish*; only a separate OS process (group) can be hard-killed mid-phase by the parent. (b) fails that bar: a cooperative poll cannot stop a wedged or runaway run — the exact failure this NFR guards. (c) is infeasible, not merely inferior: the bundle's `agent` dispatch and `args` binding exist only inside the Workflow-tool runtime (there is no headless entry in the spine), so a bare `node` child crashes before dispatching a single leaf. · **Accepted downside:** the driver session adds a bounded slice of model-driven launch overhead (disclosed against the Cost-harness NFR; governed by the same ceilings), plus an IPC/observation boundary — the terminal outcome is read from the run's durable records, and spend is sampled from the child session's machine-readable usage output rather than a shared counter. **Permission posture (stated):** the child session runs non-interactive under a harness-scoped permission profile passed at spawn that pre-approves the pipeline's known *non-owner* tool surface, with the **launcher-set enforcement environment marker** switching the band's claude-host enforcer (`hooks/hooks.json` → `lib/enforcer.py`) into **deny-only mode**. A non-interactive session has no human at the root to answer a gated `ask` (the band's PreToolUse hooks fire inside subagents and bubble to the root), so unmarked, an owner-authority action's `ask` would either hang or, under a broad pre-approval, fail open into a real-repo merge/push; under the marker the enforcer returns **`deny`** for the whole owner-authority set instead (honoring no allowance overlay), making UFR-6 structural rather than dependent on an absent human, and the pre-approval profile excludes that set so the allowlist cannot widen it back. A gate that still fires is detected by the launcher and reported as a launch-environment failure, never a pipeline failure (a denied owner-authority call is the UFR-6 block having fired). · **Reversible?** one-way-ish (the process boundary shapes the launcher API) — mitigated by hiding it behind `acceptance_launch`'s interface. · **Mode:** PROCEED (engineering-internal; the only feasible shape that meets FR-8/UFR-2, with the cost disclosure carried in the NFR section). · **Reverse path:** swap the launcher impl behind its interface. · **Expiry:** n/a. · **Escalated?** no.

- **Decision:** **Reuse `lib/showrunner.bundle.js` + `lib/preflight.py` as the launch path**, rather than a bespoke harness-only launch. · **Options weighed:** (a) reuse the production launch path the `showrunner` skill uses; (b) a dedicated launch path tuned for the harness. · **Choice + why:** (a) — the whole point is to test *the real* pipeline the owner ships; testing a bespoke path would test something other than production. The case for (b) was avoiding fixture-materialization overhead, but that overhead is trivial and (b) sacrifices fidelity. · **Accepted downside:** the harness is coupled to the production launch contract and must track its changes. · **Reversible?** two-way. · **Mode:** PROCEED. · **Reverse path:** re-point the launcher. · **Expiry:** n/a. · **Escalated?** no.

- **Decision:** **Reuse the existing `ref_lock`/`fence_cli` lease + `control_plane` store** for the harness's in-flight marker and result record, under a harness namespace — no new persistence engine. · **Options weighed:** (a) reuse the band's git-ref lease + control-plane store; (b) a new lockfile/DB for the harness. · **Choice + why:** (a) — the band already coordinates by git refs + a config lock (CONVENTIONS §4.4/§4.5), it is proven, and staying on it keeps the concurrency semantics identical to the rest of the band. The case for (b) was isolation, but a namespace under the existing store gives isolation without a new engine (YAGNI). · **Accepted downside:** the harness's records share the store's fate (though under a distinct namespace). · **Reversible?** two-way (additive namespace). · **Mode:** PROCEED. · **Reverse path:** relocate the namespace. · **Expiry:** n/a. · **Escalated?** no.

- **Decision:** **Fixture docs are committed in-repo (`eval/fixtures/acceptance/`); each run materializes a stamped throwaway copy into the doc store.** · **Options weighed:** (a) commit a canonical fixture, copy+stamp per run; (b) generate the fixture fresh each run from a template in code. · **Choice + why:** (a) — a committed fixture is reviewable, drift-checkable against the pipeline's phase list (UFR-7), and version-controlled with the pipeline it exercises; (b) hides the fixture in code and makes the drift check harder to reason about. · **Accepted downside:** the committed fixture must be kept consistent with the pipeline (mitigated by the UFR-7 drift check, which fails loudly on divergence). · **Reversible?** two-way. · **Mode:** PROCEED. · **Reverse path:** switch to code-generation behind `acceptance_fixture`. · **Expiry:** n/a. · **Escalated?** no.

- **Decision:** **Ceilings default to conservative built-in values, overridable via the project's calibration**, not a new config surface. · **Options weighed:** (a) built-in defaults + optional calibration override; (b) required owner configuration before first use. · **Choice + why:** (a) — the spec requires the ceilings in force "without the owner setting anything" (FR-8) and unattended operation; a required-config gate would break both. The case for (b) was forcing the owner to reason about cost, but the conservative default already bounds spend and the owner can tune it. · **Accepted downside:** the built-in default may not fit every owner's budget out of the box (they can override). · **Reversible?** two-way. · **Mode:** NOTIFY — the default ceiling values are a mild owner preference, cheaply changed. · **Reverse path:** set the ceilings in calibration before the next run. · **Expiry:** any time (the ceilings read at each launch). · **Escalated?** no — reversible default, surfaced here for veto.

## Cross-cutting concerns

- **Security & privacy:** Privacy is a first-class NFR — the result record and verdict report stay
  on the owner's machine and the harness publishes no captured failure text to the code host. The
  harness inherits the pipeline's secret-scrubbing (the run's own readout is already scrubbed by
  `build_readout`); the harness copies only the machine-readable run-outcome fields it needs into
  its local record, never round-tripping raw failure text to `gh`. New trust boundary: the harness
  spawns a child process and reads live `gh` facts — both already-trusted surfaces in the band. No
  new PII, no authn/authz change.
- **Observability:** The result record *is* the observability surface — one durable, readable
  record per invocation with the verdict, reason, PR link, phases, spend/elapsed, and timestamps.
  "How does the owner debug a fail at 2am?" — read the single result record (it names the false
  fact) and, if needed, the child run's own preserved terminal record before teardown removed it;
  a cleanup-failure explicitly lists surviving artifacts and the one re-runnable cleanup action.
- **Reliability & failure modes:** Dependencies: `gh`/code-host (critical for verdict facts and
  cleanup — unreachable → fail-closed verdict per UFR-9, and cleanup surfaces leftovers per
  UFR-3), the child showrunner process (its terminal outcome is the primary fact source; a killed
  or crashed child → fail verdict), and the control-plane store (critical for the lease + record;
  a durable-write failure surfaces as `recordMissing`, mirroring `loop_readout`). The harness
  degrades to a *fail verdict with a named reason* on every readability/liveness failure — it
  never degrades to a false pass.

## Rollout & migration

New capability, additive, off unless the owner invokes it; no existing behavior changes and no
data migration. Rollback = do not invoke the skill (and, if ever needed, remove the skill +
harness lib — nothing else depends on them). The only stateful surfaces are the harness's own
namespaced lease + result record, which are additively versioned (`schemaVersion`) so a future
change expands rather than breaks them; there is no pre-existing harness data to migrate. The
committed fixture ships with the change and is exercised by the DoD's one live acceptance run.

## Risks & mitigations

- **Fixture drift silently masquerading as a pipeline failure.** *(Pre-mortem: six months out,
  the pipeline gains a phase, the fixture's phase list is stale, and the harness reports the
  showrunner "broken.")* Mitigation: the UFR-7 drift check compares the fixture's expected phase
  list to the pipeline's current phases and its target file to reality, refusing *before* launch
  and naming the drift — drift is never reported as a pipeline failure.
- **A killed child leaving half-written artifacts the parent can't fully see.** Mitigation:
  cleanup is stamp-scoped discovery (find everything whose name parses to this run's full stamp),
  runs only after the child's process **group** is confirmed empty (UFR-2 ordering — no orphaned
  `git`/`gh`/engine grandchild can still be writing while teardown runs), and UFR-8 reclaim
  sweeps anything a later invocation finds — so a partial kill is recoverable, not permanent.
- **The harness itself dying mid-invocation, leaving an orphan with no record.** Mitigation: FR-5
  + UFR-8 — the *next* invocation's reclaim writes a failed record for the orphan (only if it has
  none) and cleans it, so no invocation is ever left without a record or the owner locked out.
  The lease-released-last invariant (Data flow) keeps this backstop armed even when death lands
  in the teardown→record window: the in-flight marker survives until the record is durably
  written, so reclaim always has a trigger.
- **Spend cannot be sampled from a child process.** Mitigation: the named spend source is the
  child session's own machine-readable usage/cost output (the headless CLI reports it), aggregated
  by the launcher — the showrunner spine tracks per-leaf token usage in its review telemetry but
  journals no cost/dollar spend and no cross-phase total (verified), so no phantom spend journal
  is relied on; when the session's reporting is unavailable, the elapsed ceiling still governs
  and the gap is noted in the record — fail-closed on the readable ceiling, never a silent
  unbounded run. The subtler variant — the sample reads cleanly but is **incomplete** because
  engine-dispatched (Codex/Cursor) leaves spend outside the session's stream — is closed by
  disclosure, not detection: whenever engine preferences resolve to an external engine, the
  record's spend is marked partial and the elapsed ceiling is the stated backstop (see
  `acceptance_launch`), so the incompleteness is never silent.
- **Coupling to the production launch contract breaking when the bundle or CLI changes.**
  Mitigation: the launcher drives the *same* launch contract the `showrunner` skill uses (the
  skill's Workflow-tool invocation of the committed bundle, exercised through the headless
  session) plus the headless CLI's non-interactive interface; the band's existing bundle-drift
  guard keeps the bundle entrypoint honest, and any break — bundle or CLI interface — surfaces as
  a launch failure the harness reports, not a false pass.

## Dependencies & assumptions

**Dependencies:** the already-shipped showrunner and its machine-readable run-outcome
(`run_readout.run_outcome`, the "#112 consumer contract"); the launch path
(`lib/preflight.py` + the `showrunner` skill's Workflow-tool invocation of
`lib/showrunner.bundle.js`, carried by the already-installed `claude` CLI's non-interactive
headless mode — the same host binary running the band, so nothing new is installed); the
artifact-lifecycle libs
(`lib/buildtree.py`, `lib/control_plane.py`, `lib/ref_lock`/`fence_cli.py`); the band's
claude-host enforcer wiring (`hooks/hooks.json` + `lib/enforcer.py`), which this work-item
extends with the additive **deny-only mode** the launcher's enforcement marker switches on so
owner-authority actions are denied in the child (the UFR-6 structural floor — see
Components/`lib/enforcer.py` deny-only mode); a reachable code
host (`gh`) for PR/check facts and cleanup; the project's superheroes calibration present in the
repo. No new external package or paid service is added (so no library-existence verification is
outstanding — every dependency is an existing in-repo module or the already-installed `gh`).

**Assumptions:** the showrunner's run-outcome remains the authoritative terminal summary
(status, PR link, check status, phases, readout location) — a shaky assumption is caught by the
verdict's readout-vs-reality consistency check (FR-4), not parked. The showrunner is operational
(the harness detects its regressions, does not repair them). Acceptance runs happen in the real
repo with no sandbox, and never merge — protected structurally (UFR-6). The GitHub issue #112 is
updated to the standalone shape as part of the DoD.
