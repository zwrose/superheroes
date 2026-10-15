---
superheroes: doc
schemaVersion: 1
docType: plan
workItem: test-pilot-native-workflow-phase-2ab475
issue: 90
size: medium
status: approved
gates: {review: passed}
producedBy: "the-architect@0.2.0"
created: "2026-06-26"
updated: "2026-06-26"
---
# Showrunner Test-pilot Verification - Plan

## Overview

Add a first-class `test-pilot` phase to the showrunner Workflow between
`draft-PR` and `mark-ready`. The phase is the workflow-owned pre-ready browser
verification gate: it classifies whether browser verification applies to the
built PR branch, derives or refreshes the branch test plan when it applies,
creates or updates the existing test-pilot manifest and plan-record artifacts,
seeds through the existing engine, runs the browser plan with a bounded
fix-and-retry loop, publishes plan and result artifacts, restores the planned
seed data to a fresh spot-check baseline, and records a current verification
status before the PR may be marked ready.

The design keeps the showrunner spine in control and uses leaf agents only for
coarse, human-like work: one plan-derivation leaf for the branch, one browser
execution pass leaf for a set of plan steps, and up to three browser fix-batch
leaves.
When a plan is too large for the MVP caps, the phase parks rather than spawning
per-step subagents; split browser-pass batching is a fast-follow. All gating,
state, artifact routing, privacy scrubbing, branch-head freshness, PR-head
publication, review-code coverage after test-pilot fixes, seed application, MVP
resource caps, and retry decisions live in deterministic helpers with tests.
This follows the now-merged showrunner shape: the JS phase sequences work, pure
Python helpers make fail-closed decisions, and durable checkpoint/journal records
make resume behavior honest.

## Goals & non-goals

**Goals:**

- Run pre-ready browser verification inside showrunner, after draft PR creation
  and before `mark-ready`, with no maintainer-invoked standalone test-pilot run.
- Distinguish branches where browser verification is applicable from branches
  where it is genuinely not applicable, and record the rationale.
- For applicable branches, create or update the test plan, scenarios,
  manifests, plan records, seed state, browser results, fix-batch history, and
  fresh seeded spot-check baseline before readiness.
- Park before mark-ready on missing setup, invalid plans, unsafe or unverifiable
  seed operations, failed browser steps, stale results, incomplete artifacts, or
  baseline restoration failures.
- Avoid token-inefficient per-step subagents by grouping browser failures and
  fixes into coarse passes.
- Reuse the existing test-pilot engine, store, manifest, plan-record, PR-comment,
  browser-origin, managed-server, and protected-target policies.

**Non-goals:**

- Replacing the standalone `test-pilot-plan` or `test-pilot-execute` skills.
  They remain valid entry points outside the showrunner Workflow.
- Changing scenario block semantics, protected-target authorization, browser
  origin limits, or human ownership of spot-check checklist boxes.
- Making non-browser branches produce browser plans. A documented not-applicable
  result is a successful pre-ready resolution for those branches.
- Merging PRs, changing the ship phase, or adding the multi-issue controller.

## MVP boundary & fast-follow

Day one implements the spec for the common safe path and parks for the narrower
edge cases that need more hardening. No spec requirement moves out of scope: the
MVP satisfies FR-1 through FR-18 and UFR-1 through UFR-10 for branches whose
test-pilot artifacts resolve to machine-local/global storage, whose server setup
is already ready or uses an argv-array `devCommand`, and whose plan fits simple
unattended caps. For the cases below, day-one behavior is a scrubbed park before
mark-ready rather than a false ready signal.

- **Shared-spine cursor guard:** day one lands the minimal shared checkpoint /
  `recordCursor` / `recover_entry` guard before inserting `test-pilot` into
  `PHASES`. Broader checkpoint migration/version-hash machinery is deferred
  unless a later phase-list change creates a concrete need.
- **In-repo test-pilot writes:** day one parks before writing generated
  manifests, plan records, or blocks into an in-repo store. A fast-follow may add
  quarantine, privacy certification, commit/fence, and revalidation for those
  in-repo artifacts.
- **Managed dev-server hardening:** day one accepts argv-array commands and
  already-ready servers; legacy string `devCommand` values and package-derived
  string commands either normalize to explicit argv without shell interpretation
  or park with a setup readout before launch. Exact string authorization or
  profile migration is a fast-follow.
- **Budgets:** day one enforces simple caps for plan records, browser steps,
  browser passes, total browser fix batches, unique seed scenarios, planned
  seed clean/apply/reapply operations, and total phase elapsed time. Fine-grained
  runtime/state-size budgets and split-batch optimization are fast-follow
  refinements.

## Architecture

The showrunner phase list becomes:

`plan -> review-plan -> tasks -> review-tasks -> workhorse -> review-code -> draft-PR -> test-pilot -> mark-ready -> ship`

`showrunner.js` stays the spine. It delegates the new phase to
`test_pilot_phase.js`, records its phase result through the existing
`appendPhaseRecord` and `phaseStep` path, then advances only when the phase
returns high confidence. The existing cursor semantics continue to apply:
completed phase side effects are recorded before the loop advances. The
test-pilot readiness status is not stored as a checkpoint cursor side effect;
it is stored in its own sidecar and summarized in the journal/readout because
the current checkpoint side-effect path only owns `pr` and `ready`.

Because adding `test-pilot` changes the meaning of the numeric phase cursor, the
checkpoint cursor change is a shared-spine slice, not a test-pilot-local helper.
Before inserting the phase, `showrunner.recordCursor`, `checkpoint_entry.py`,
`checkpoint.py`, and `recover_entry.py` must preserve the completed phase name
beside the existing numeric `lastGoodStep`. Resume verifies
`PHASES[lastGoodStep] === storedPhaseName` before advancing; a mismatch parks
before any phase side effect with a readout that names the cursor/phase mismatch.
This MVP does not need a phase-list hash or migration framework for ephemeral
pre-release dogfood checkpoints. Unknown or newer checkpoint schema remains a
distinct read failure, not `None`/no-checkpoint: recover-on-entry must preserve
that reason and park before phase selection rather than `world_derive`.

The new phase runs against the build branch recorded in `checkpoint.json`, not
the showrunner checkout. It resolves the current branch head the same way
`pr_entry.py` does: from the checkpoint branch. Every durable verification
record is tied to that branch and head.

The phase has two terminal success shapes:

- **Applicable and verified:** at least one browser-backed plan record exists;
  every plan record has passing browser results for the current final branch
  head; both plan and results artifacts are available; the planned seed data has
  been restored and verified as a fresh baseline.
- **Not applicable:** the phase records a current branch-head rationale showing
  that the PR has no runnable browser surface. No browser plan, results, or
  seed baseline is required in this path.

Everything else parks before mark-ready. A failed or empty test-plan derivation
is never reclassified as not applicable by itself.

`markReadyPhase` also gets a cheap final guard before it calls `pr_entry.py`: it
asks the test-pilot status helper whether the current branch head is covered by
a successful applicable result or a successful not-applicable rationale, whether
any test-pilot or post-browser review-code fix commits are covered by a clean
`review-code` result and verify pass for that same head, whether browser results
are current after the last branch mutation, and whether the remote PR head
matches the locally tested head. This complements the #104 ship-gate boundary:
build provenance stays anchored to the original workhorse build commit `X`,
while review coverage and verify evidence must cover the final head after any
test-pilot or review-code fixes. If
the status is missing, stale, incomplete, low confidence, unreviewed, or not
published to the PR head, `mark-ready` parks instead of flipping the PR. This
covers resume or outside-branch-drift windows after the `test-pilot` phase
cursor has already advanced.

## Components & interfaces

**`lib/test_pilot_phase.js`**

- Responsibility: workflow control flow for the `test-pilot` phase.
- Inputs: `workItem`, checkpoint branch/PR, optional injected dependencies for
  tests.
- Output: the existing phase result contract,
  `{confidence: "high"|"low", assumptions: [...]}`. The latest status summary is
  written to `test-pilot-status.json` and the journal/readout, not to the
  checkpoint cursor.
- Error contract: any uncertain state returns low confidence with a scrubbed
  assumption so `phaseStep` parks before mark-ready.

**`lib/test_pilot_status.py` and CLI wrapper**

- Responsibility: read/write/assert the durable pre-ready verification status
  for a work item.
- Stores a small sidecar in the work-item control-plane directory, for example
  `test-pilot-status.json`.
- Records: branch, head, applicability verdict, rationale, plan keys/slots,
  artifact availability, execution verdict, fix-batch count, baseline verdict,
  remote PR head, review-code coverage head and verify-pass head when fixes were
  committed, and freshness metadata.
- `assert-current` returns proceed only when the status covers the current
  branch head and satisfies either the applicable-ready shape or the
  not-applicable shape. For applicable results with fix commits, it also
  requires clean review-code coverage, verify pass, and remote PR-head
  reconciliation for the final tested head.

**Shared checkpoint cursor extension**

- Responsibility: make showrunner cursor resume safe across phase-list changes.
- Scope: shared-spine code, specifically `showrunner.recordCursor`,
  `checkpoint_entry.py`, `checkpoint.py`, `recover_entry.py`, and the associated
  resume tests.
- Contract: checkpoint writes include the completed phase name beside the
  existing numeric `lastGoodStep`. Resume checks that the stored phase name
  equals `PHASES[lastGoodStep]`; if not, it parks before any side effect with a
  readout that names the cursor/phase mismatch. The checkpoint reader must
  distinguish unknown/newer schema from an absent checkpoint and return an
  incompatibility park reason; it must not collapse schema mismatch to `None`
  and let `recover.reconcile` `world_derive`.
- Non-goal for MVP: no phase-list hash, schema bump solely for the phase-name
  field, or checkpoint migration framework. If a schema bump becomes necessary,
  it lands as its own small shared-spine slice before the test-pilot phase body.

**`lib/test_pilot_applicability.py` and CLI wrapper**

- Responsibility: decide `applicable`, `not_applicable`, or `park`.
- Inputs: branch diff summary, repo detector signals, test-pilot profile/config
  if present, package/dev-server signals, and the plan-derivation result when
  applicable.
- Contract: `not_applicable` requires positive evidence that the branch has no
  runnable browser surface, such as docs-only, CLI-only, library-only, or
  internal workflow changes with no browser-reachable behavior. `applicable`
  is used for user-facing or runnable browser behavior. `park` is used for
  uncertainty, missing required setup on an applicable branch, or applicable
  branches with no usable browser-backed test plan.

**Plan/scenario preparation leaf**

- Responsibility: derive the branch test plan and create or update the existing
  test-pilot manifest and plan-record artifacts.
- Shape: one leaf per branch/head, not one leaf per step. It follows the
  existing `test-pilot-plan` flow inside the showrunner phase: resolve store,
  read the block catalog, analyze the branch diff, pick or create blocks when
  allowed, write or merge manifests, dry-run the engine, and write
  `<key>.plan.json` records.
- Artifact storage policy: branch-specific workflow-generated manifests, plan
  records, and generated blocks must not leave uncommitted files in the managed
  build worktree while readiness is recorded for the clean branch head. Prefer
  machine-local/global test-pilot storage for workflow-generated branch artifacts.
  In the MVP, if the resolved test-pilot store is in-repo and the phase would
  need to write manifests, plan records, or blocks there, it parks before
  writing and asks for machine-local/global storage or a later in-repo-artifact
  fast-follow. The deferred in-repo path may add quarantine outside the build
  worktree, allowlist/scrub plus secret-scan, owner authorization for any
  sensitive PR-visible value, commit/fence of certified artifact writes, and the
  same review-code/browser revalidation required for other branch mutations.
- Output: structured JSON with plan keys/slots, scenario ids, browser step
  count, created/updated artifact paths, and any setup or plan error.
- Boundary: it does not run browser steps and does not check human checklist
  boxes.

**`lib/test_pilot_seed.py` and CLI wrapper**

- Responsibility: seed and restore planned scenarios through `engine.py`.
- Uses `engine.py validate-plan`, `apply --dry-run`, `apply`, `clean`, `status`,
  and `unlock` exactly as the standalone test-pilot and existing reset helpers
  do.
- Initial seeding: validate every plan record, dry-run, then apply before any
  browser step for that record. The dry run feeds the aggregate seed-operation
  budget before apply. Partial, failed, protected-target, over-budget, or
  unverifiable seeding returns `park`.
- Fresh baseline restoration: after passing browser execution, clean each
  planned branch/slot and re-apply the same planned scenarios, then verify the
  engine status has the expected branch/slot entries with no drift. The restore
  dry run must pass the same aggregate operation budget before mutation. This is
  intentionally not the older "clean to empty" reset behavior.

**Browser execution pass leaf**

- Responsibility: exercise browser steps from one or more validated plan
  records with a configured browser tool.
- Shape: one leaf per bounded execution pass. In the MVP, the initial pass
  covers every planned browser step or parks if the plan exceeds the plan,
  browser, seed-operation, or elapsed-time caps.
  A fast-follow may split oversized-but-reasonable plans into bounded pass
  batches. Retry passes cover either the whole plan or the failed steps plus all
  affected steps selected by the retry decider.
- Output: structured JSON per step with pass/fail, byte-capped scrubbed notes,
  sanitized evidence reference/source, byte-capped redacted console/network
  summary, and classification
  (`app_bug`, `plan_or_seed_bug`, `environment`, `blocked`).
- Boundary: non-browser checks cannot satisfy browser steps. Navigation remains
  constrained to the profile `baseUrl` plus `allowedOrigins`.
- Durability boundary: the leaf or receiving status helper applies the
  fail-closed scrub/allowlist policy before any run-log, status-sidecar,
  fallback, or PR artifact write. Raw headers, cookies, API keys, credentials,
  protected values, personal values, and raw seed configs are not persisted; if
  scrubbing fails, the diagnostic is dropped or the phase parks rather than
  storing it. Each per-step diagnostic field has a configured byte cap and
  truncates with an omitted-byte marker after scrubbing/allowlisting. The status
  helper enforces actual rendered-size limits for run logs, `test-pilot-status.json`,
  fallback bodies, and PR bodies before writing; if capped output still exceeds
  budget, the phase parks instead of writing an oversized artifact.

**`lib/test_pilot_budget.py` and CLI wrapper**

- Responsibility: enforce finite unattended browser and seed work before seed
  apply/restore operations, browser leaves, and artifact rendering.
- MVP inputs: plan-record count, browser-step count, browser-pass count, and
  total browser fix-batch count; unique scenario count and planned
  clean/apply/reapply operation counts from the seed dry run for both initial
  apply and final baseline restore; monotonic elapsed seconds since test-pilot
  phase start; and rendered status/artifact byte budgets supplied by the status
  and artifact helpers.
- MVP outputs: `within_budget` or `park_budget_exceeded`.
- MVP contract: the workflow parks when a plan exceeds configured/default caps
  for plan records, browser steps, browser passes, the three total browser fix
  batches, unique seed scenarios, planned seed operations, total phase elapsed
  time, or rendered status/artifact sizes. It checks the dry-run-derived seed
  operation vector before the first apply, before final baseline restore, and
  again inside the engine lock immediately before clean/apply/reapply work so
  resumed or drifted state cannot bypass the aggregate cap. It does not split
  over-budget plans in day one.
- Fast-follow contract: add split-batch optimization and multi-dimensional
  budgets for per-pass runtime estimates, aggregate seed state size, per-step
  diagnostic bytes, and richer fallback/PR body sizing.

**`lib/test_pilot_retry.py` and CLI wrapper**

- Responsibility: decide fix-batch continuation.
- Inputs: execution results, prior fix batches, changed files from the fix
  batch, and the plan-step dependency map.
- Outputs: `fix_batch`, `rerun_all`, `rerun_subset`, `park_no_progress`, or
  `park_cap_reached`.
- Rules: collect all app-bug failures from a pass before fixing; allow one fix
  batch to address multiple steps; stop after three total browser fix batches;
  rerun the whole plan when affected coverage cannot be determined. Reuse
  `circuit_breaker.py` through a browser retry adapter, not by feeding raw failed
  steps into the review-code recurrence rule. The adapter stores each fix
  batch's scrubbed failure summary plus failed/affected step outcome deltas,
  computes FR-13's no-progress predicate first, and emits a single synthetic
  blocking finding such as `park_no_progress` only when two consecutive fix
  batches have the same scrubbed summary and no failed or affected step changed
  from fail to pass. A recurring individual failure does not park while another
  failed or affected step is making progress.

**Fix-batch leaf**

- Responsibility: diagnose and fix the collected app-bug failures for one
  batch.
- Shape: one leaf per batch, up to three total. It stages only touched files,
  refuses to commit on the default branch, commits to the build branch with a
  short batch description, and returns commit SHA or SHAs plus changed files.
- Success contract: a fix batch is not accepted until commit SHA(s) are recorded
  and the managed build worktree is clean. On phase entry after a failed or
  interrupted fix attempt, and before any browser rerun, review-code rerun,
  status write, or publish following a fix attempt, the phase gathers build
  worktree cleanliness. If uncommitted or untracked changes remain, it
  renews/fences the work-item lease and resets only uncommitted/untracked state,
  or parks with a readout if reset is unsafe or fails. Browser evidence is never
  recorded for dirty local files that are not part of the branch head.
- Reconciliation contract: before any browser rerun, review-code rerun, status
  write, publish, or mark-ready assertion after a fix attempt, every commit after
  the last recorded tested head must map to either a recorded browser fix batch
  or a recorded review-code stabilization cycle. A clean committed mutation with
  no matching status record is reconciled only when a write-ahead batch intent or
  returned commit SHA makes the batch identity deterministic; otherwise the phase
  parks fail-closed with a readout. Reconciled fix commits count against the
  three browser-fix-batch cap and appear in the results artifact.
- Output feeds `test_pilot_retry.py` so rerun coverage is chosen by policy,
  not by the leaf improvising.

**`lib/test_pilot_publish.py` and CLI wrapper**

- Responsibility: after any fix-batch commit, publish and reconcile the final
  tested branch head before readiness.
- Contract: renew/fence the work-item lease before pushing, push the build
  branch without force to its existing PR branch, read the remote PR head SHA,
  and require it to equal the final locally tested head. If there is no safe
  tracking target, the lease is lost, push fails, or the PR head cannot be read
  or does not match, park with a readout.

**Conditional review-code rerun**

- Responsibility: preserve the existing reviewed-HEAD invariant when test-pilot
  fixes commit app code after the normal `review-code` phase.
- Contract: if no fix-batch commit was made, the earlier `review-code` result
  still covers the head only when no later branch mutation occurred. If one or
  more fix-batch commits were made, the test-pilot phase invokes an extended,
  targetable form of the merged `reviewCodePhase` over the final tested
  branch/worktree/head after browser reruns pass and before writing ready
  status. Do not fork a parallel review-code implementation.
- Fresh loop state: each stabilization cycle gets its own run directory keyed by
  purpose, cycle, and expected head, for example
  `/tmp/showrunner-${workItem}-review-code-test-pilot-${cycle}-${head12}`. It
  never reuses the pre-draft-PR review-code run directory, because
  `review_panel_shell.resumeRound(runDir)` resumes from disk.
- Target binding: reviewer, fixer, verify, and provenance leaves receive the
  managed build worktree path, checkpoint branch, and expected head. Before each
  leaf or verify command, the wrapper confirms the worktree/branch resolves to
  that expected head; a mismatch parks rather than reviewing the wrong tree.
- Coverage write: on a pure `clean` terminal only, `prov_entry --step review`
  restamps `review.covers` to the final tested head through its existing
  read-modify-write upsert, preserving `build` provenance and replacing the
  earlier `covers = X'`. `clean-with-skips` advances the review-code phase but
  records no covers stamp, so test-pilot status is not ready and the
  `mark-ready`/ship gate parks.
- Stabilization: because the #104 panel can commit fixes, test-pilot tracks a
  separate `reviewStabilizationCycle` counter capped at 2. Review-code-induced
  commits do not count against the three browser fix-batch cap; browser app-bug
  fixes discovered after those commits still count against the same three total
  browser fix batches for the whole test-pilot run. The finite worst case is
  three browser fix batches, then at most two targetable review-code
  stabilization cycles, each with the #104 panel's seven-round cap; any further
  review-code mutation, unresolved blocker, clean-with-skips, stale worktree,
  or browser failure after the browser cap parks with a readout.
  Readiness requires `review.covers == browser-tested-head == remote-PR-head`
  and a review-code clean/verify-passed result for that head.

**`lib/test_pilot_server_config.py` and CLI wrapper**

- Responsibility: normalize app-server configuration before `detect.py` and
  `devserver.py` are reused by the workflow.
- MVP contract: accept an already-ready server (`mayManageServer: false`) or an
  argv-array `devCommand`, and return one canonical command form plus port,
  readiness URL, and allowed origins. Argv-array commands stay argv arrays all
  the way into the server launcher and run with `shell=False`; they are never
  flattened into a shell string. Legacy string commands remain readable for
  diagnostics but park before launch with a setup readout that asks for an
  argv-array profile or a later authorization/migration fast-follow. Invalid or
  empty values park on applicable branches. Package.json detections from
  `detect.py` are treated as branch-controlled command sources: day one either
  extends the detector/config helper to expose a safe script name and launches
  it as argv, for example `["npm", "run", "dev"]`, or parks before launch. A
  package-derived string such as `npm run dev` must never reach the
  shell-string `devserver.start` path.
- Lifecycle contract: if the workflow starts a managed server, it records only
  its own handle and tears it down through `devserver.teardown` on every success,
  park, exception, timeout, retry-loop terminal, and readiness-failure path.
  Already-ready external servers are never killed. On resume, an orphaned handle
  owned by the current work item may be reclaimed and torn down before retrying;
  an unknown process on the port parks with the existing setup readout.
- Fast-follow contract: exact owner authorization for a legacy command string
  may be added later, but unauthorized strings must never reach the existing
  shell-string launcher in unattended showrunner runs.

**`lib/test_pilot_artifacts.py` and CLI wrapper**

- Responsibility: render and route the plan and results artifacts.
- Reuses `pr_comment.py` markers, checkbox preservation, and scrubbing. Plan
  comments remain human-owned: the workflow never checks boxes.
- If GitHub posting succeeds for both plan and results, local fallback artifacts
  are not required. If posting fails for either artifact, this helper writes
  both equivalent fallback files under the test-pilot plans directory and records
  both paths before readiness can proceed.
- Artifacts are allowlist-rendered: scenario ids, step ids, instructions,
  expected outcomes, pass/fail, scrubbed notes, fix SHAs, and coverage rationale.
  Raw seed configs, credentials, auth headers, cookies, protected target values,
  and personal data values are omitted unless explicitly authorized for the
  current run and intended audience.

**Reused existing components**

- `showrunner.js`, `phase_step_cli.py`, `checkpoint_entry.py`, `journal_entry.py`
  for phase sequencing, parking, cursoring, and readouts.
- `engine.py`, `store.py`, `state.py`, `blocks.py`, `reset.py` for manifests,
  plan-record validation, seeding, protected-target gates, locks, and status.
- `pr_comment.py` for marker-managed plan/results comments and baseline secret
  scrubbing.
- `circuit_breaker.py` for terminal retry decisions after the browser retry
  adapter has applied FR-13 progress semantics.
- `detect.py` and `devserver.py` for runnable app and server management signals.
- `test-pilot` profile config for `baseUrl`, `allowedOrigins`,
  `mayManageServer`, `devCommand`, browser tool preference, and protected
  targets.

## Data flow & data model

1. `draft-PR` records the PR in the checkpoint.
2. On every resume, showrunner validates the cursor's stored phase name against
   `PHASES[lastGoodStep]` before advancing. Unknown/newer checkpoint schema or a
   phase-name mismatch parks before phase selection.
3. `test-pilot` resolves the build branch, PR, and current branch head from the
   checkpoint.
4. Applicability is classified and written to `test-pilot-status.json` with the
   branch head.
5. If not applicable, the status contains the rationale and the phase returns
   high confidence.
6. If applicable, the plan leaf writes or updates the existing test-pilot
   manifest files and plan records under the resolved test-pilot store. These
   remain the source of truth for planned scenarios and steps. Workflow-generated
   branch artifacts are machine-local/global by default; MVP parks before any
   required in-repo store write rather than dirtying the build worktree.
7. The artifact helper renders and posts or writes the plan artifact. If the PR
   comment cannot be posted, the named local plan fallback must be written before
   seeding or browser execution begins.
8. The seed helper validates plan records, dry-runs, applies the planned
   scenarios, and verifies seeded state before browser execution begins.
9. The browser leaf records per-step results under the test-pilot run directory.
   The phase aggregates those results into the workflow status sidecar and the
   results artifact after scrubbing/allowlist filtering.
10. If app bugs are found, the retry decider groups them into a fix batch. The
   fix leaf commits fixes to the build branch. The branch head changes, so the
   phase updates the current head and reruns the whole plan or failed+affected
   coverage until passing, exceeding the fix-batch/elapsed budget, or hitting
   FR-13 no-progress.
11. After any failed, interrupted, or completed fix attempt, the phase verifies
    the managed build worktree is clean before any rerun/status/publish step; it
    resets only uncommitted/untracked state behind a lease fence or parks if that
    cannot be done safely. It also reconciles clean commits above the last tested
    head against recorded fix-batch or review-code stabilization history before
    accepting the branch head as current.
12. If any post-browser fix commits changed the branch, the phase runs the
    stabilization loop through the targetable merged review-code phase: review
    the explicit build worktree/head in a fresh run directory for that cycle; if
    review-code changes the branch, revalidate the plan and browser results for
    the new head, then repeat until the same head is browser-passing,
    verify-passed, and review-code-covered or the loop parks.
13. The phase publishes the build branch without force and verifies that the
    remote PR head equals the locally tested and reviewed head.
14. After all plan records pass for the final branch head, the baseline helper
   dry-runs the restore operation vector against the aggregate seed budget,
   cleans and re-applies the planned scenarios, then verifies a fresh seeded
   baseline.
15. The artifact helper posts or writes the results artifact. If either the plan
    or results PR comment failed, both local fallback artifacts must exist before
    readiness. The final status
    records artifact locations, final branch head, pass verdict, fix-batch
    history, baseline verdict, review coverage head, verify-pass head, and PR
    head.
16. Any managed server started by the phase is torn down on success, park, error,
    timeout, and retry-loop terminal paths; externally provided already-ready
    servers are left running.
17. `mark-ready` asserts the status is current for the branch head before
    calling `pr_entry.py --step mark-ready`.

The only new durable data model is the workflow status sidecar. Existing
test-pilot manifest and plan-record schemas remain backward-compatible; any
extra metadata the plan leaf writes is optional and ignored by the current
engine validators. If the sidecar is absent or unreadable, the phase recomputes
from existing artifacts where safe or parks fail-closed.

## How the requirements are met

- **FR-1, FR-18:** the new `test-pilot` phase sits before `mark-ready`, and
  `mark-ready` asserts the final status before flipping the PR.
- **FR-2:** `test_pilot_applicability.py` distinguishes applicable,
  not-applicable, and park. Not-applicable requires a recorded rationale and
  current branch head; failed plan derivation cannot produce not-applicable.
- **FR-3 through FR-6:** the plan leaf derives the branch test plan, writes or
  updates manifests and plan records, validates them, and publishes or locally
  records the plan artifact before seeding or browser execution. Day-one support
  covers machine-local/global test-pilot stores; required writes to an in-repo
  store park with a setup/readiness readout until the in-repo-artifact
  fast-follow lands.
- **FR-7, UFR-1, UFR-5:** the seed helper validates and applies through
  `engine.py` before browser execution. Invalid plan records, partial seed, live
  locks, protected-target refusals, and unverified seed state park before the
  browser leaf runs.
- **FR-8, FR-9, UFR-6, UFR-7:** the browser leaf must produce a browser-derived
  pass/fail for every planned step in every plan record. Failed, skipped, or
  incomplete records park unless a re-derived current test plan removes the step
  and the results preserve the removal rationale.
- **FR-10 through FR-13:** browser failures are collected per pass, fixed in
  batches, rerun under deterministic coverage rules, and capped at three total
  browser fix batches. A browser retry adapter applies the FR-13
  same-summary/no-step-progress predicate before sending terminal decisions to
  `circuit_breaker.py`, so repeated failures that coexist with real step
  progress do not park early. MVP caps plan records, steps, passes, browser fix
  batches, aggregate seed operations, and phase elapsed time so a single
  verification run cannot create unbounded browser or seed work; fine-grained
  runtime/state-size/artifact optimization budgets are fast-follow.
- **FR-14:** all plan/results/status records carry branch-head metadata. The
  phase updates it after fix batches, loops when review-code fixes change the
  branch after browser execution, reconciles the remote PR head, and `mark-ready`
  refuses stale, unreviewed, unverified, browser-untested, or unpublished status.
- **FR-15, UFR-2, UFR-8:** the baseline helper restores by clean plus re-apply
  and verifies the planned seed state. Protected-target or verification failure
  parks before mark-ready.
- **FR-16, UFR-9:** the artifact helper requires both plan and results before
  readiness. If GitHub posting fails for either, both local fallback files must
  exist and be recorded.
- **FR-17:** the artifact helper uses `pr_comment.py` plan behavior and never
  checks human checklist boxes.
- **UFR-3:** missing test-pilot calibration, browser tooling, unsafe legacy
  string `devCommand`, unsafe package-derived server command, or required server
  setup on an applicable branch parks with a setup readout. Day-one server
  management supports argv-array commands, safe argv-normalized package script
  detections, and already-ready servers; exact authorization/migration for
  arbitrary string commands is fast-follow.
- **UFR-4:** applicable branches with no usable browser-backed plan or no
  browser-executed plan record park with a no-test-plan readout. Non-browser
  branches use the not-applicable path instead.
- **UFR-10:** status records, marker-managed PR comments, stable artifact keys,
  and existing manifest merge behavior let a resumed run update or reuse prior
  work without duplicates.
- **Non-functional requirements:** truthful readiness is enforced by phase order
  and the mark-ready guard; privacy is enforced by allowlist rendering plus the
  central scrubber; bounded unattended work is enforced by `test_pilot_budget.py`
  plus `test_pilot_retry.py`; recoverability is enforced by durable status and
  marker/fallback reuse.

## Key decisions & alternatives

- **Decision:** Add a first-class `test-pilot` showrunner phase before
  `mark-ready`. **Options weighed:** first-class phase; embed everything in
  `mark-ready`; keep standalone test-pilot as manual outside-workflow activity.
  **Choice + why:** first-class phase, because it makes pre-ready verification
  visible, resumable, testable, and ordered by the same phase loop as build,
  review, draft PR, and ship. A cheap `mark-ready` guard remains for branch
  drift after cursor advance. **Accepted downside:** one more phase and status
  artifact to maintain. **Reversible?** two-way door. **Mode:** PROCEED.
  **Reverse path:** remove the phase and keep the mark-ready guard or route to
  standalone skills. **Expiry:** before Tasks harden the phase interface.
  **Escalated?** no.

- **Decision:** Guard phase-cursor compatibility when the phase list changes.
  **Options weighed:** keep the numeric cursor unchanged; store phase names or a
  phase-list version/hash beside the number; bump checkpoint schema so older
  code fails closed. **Choice + why:** store the completed phase name beside the
  existing numeric cursor in the shared spine and park when
  `PHASES[lastGoodStep]` no longer matches. This is enough for ephemeral
  pre-release dogfood checkpoints and avoids a migration framework with no
  concrete current consumer. **Accepted downside:** rolled-back old code may
  ignore the extra phase-name field, so rollback instructions must retain or
  backport the guard rather than relying on a schema rejection. **Reversible?**
  two-way door. **Mode:** PROCEED. **Reverse path:** add a schema bump and
  phase-list hash as a separate shared-spine slice if future phase-list changes
  need stronger compatibility. The reader must preserve unknown-schema as an
  incompatibility reason and park, not collapse it to no-checkpoint/world-derive.
  **Expiry:** before adding `test-pilot` to `PHASES`. **Escalated?** no.

- **Decision:** Use coarse leaf agents under a deterministic workflow
  controller. **Options weighed:** one monolithic agent to plan/run/fix/rerun;
  per-step browser and fix agents; coarse plan, browser-pass, and fix-batch
  leaves. **Choice + why:** coarse leaves keep token overhead bounded while
  still giving the workflow deterministic gates between plan creation, seeding,
  execution, fixing, rerunning, artifacts, and baseline restoration. **Accepted
  downside:** the controller has to define structured JSON contracts for each
  leaf. **Reversible?** two-way door. **Mode:** PROCEED. **Reverse path:** merge
  leaves later if overhead is still too high, or split browser passes later if
  a specific repo needs finer isolation. **Expiry:** until the first workflow
  implementation lands. **Escalated?** no; the owner accepted the batching
  direction during discovery.

- **Decision:** Preserve reviewed-HEAD and PR-head invariants after test-pilot
  fixes. **Options weighed:** forbid test-pilot from committing fixes; move
  test-pilot before the first review-code gate; allow fix commits but rerun
  review-code and reconcile the remote PR head before readiness, with a
  stabilization loop if review-code itself mutates the branch. **Choice + why:**
  keep test-pilot after draft PR as the spec requires, but require conditional
  review-code coverage by extending the merged `reviewCodePhase` to accept an
  explicit worktree/head and fresh run directory per stabilization cycle,
  browser-result revalidation after any review-code fixes, non-force push, and
  PR-head match after any post-browser branch mutation. `prov_entry --step
  review` is an idempotent read-modify-write upsert: it preserves the original
  build evidence at workhorse build commit `X` and restamps `review.covers` to
  the final tested head. **Accepted downside:** a fix-batch path can pay for
  multiple review/browser stabilization cycles and needs a small targetability
  extension to the merged review-code phase, and can park late on push, PR-head
  read failure, `clean-with-skips`, or repeated review-code fixes. **Reversible?**
  two-way door. **Mode:** PROCEED. **Reverse path:**
  disable fix commits in test-pilot or move the phase if the workflow contract
  changes. **Expiry:** before implementation of the test-pilot phase. **Escalated?**
  no.

- **Decision:** Treat not-applicable as a first-class success state, but treat
  applicable-with-no-plan as a park. **Options weighed:** always require a
  browser plan; allow no-plan to mean not-applicable; classify applicability
  separately from plan derivation. **Choice + why:** separate classification
  matches the spec: docs/CLI/library work should not park just because no
  browser plan exists, while browser-relevant work cannot escape by failing to
  derive a plan. **Accepted downside:** conservative false positives may park
  for owner setup instead of proceeding. **Reversible?** two-way door. **Mode:**
  PROCEED. **Reverse path:** loosen classifier rules after real runs show a
  noisy category. **Expiry:** after classifier unit tests and initial smoke
  runs. **Escalated?** no.

- **Decision:** Reuse test-pilot manifests and plan records, and add a small
  workflow status sidecar instead of inventing a new test-plan store. **Options
  weighed:** new workflow-owned schema for all plan data; only PR comments as
  state; existing engine artifacts plus workflow status sidecar. **Choice + why:**
  existing manifests and plan records already validate scenarios, branch/slot
  identity, and protected-target gates; the sidecar only records workflow
  readiness facts the engine does not own. **Accepted downside:** two sources
  must be cross-checked on resume. **Reversible?** mostly two-way; sidecar
  schema can be migrated or replaced. **Mode:** PROCEED. **Reverse path:** fold
  sidecar fields into plan records later if they become generally useful.
  **Expiry:** after one schema version is released. **Escalated?** no.

- **Decision:** Keep workflow-generated test-pilot artifacts from invisibly
  dirtying the verified branch. **Options weighed:** always force global
  machine-local storage; allow resolved in-repo storage but leave changes
  uncommitted; prefer machine-local storage and park when in-repo writes would
  be required. **Choice + why:** MVP prefers machine-local/global storage for
  branch-specific workflow artifacts and parks before any generated in-repo
  manifest, plan-record, or block write. This keeps browser evidence tied to a
  clean PR head without adding quarantine/commit/revalidation machinery to the
  first slice. **Accepted downside:** repos configured for in-repo test-pilot
  storage may park until they switch storage mode or the fast-follow lands.
  **Reversible?** two-way door. **Mode:** PROCEED. **Reverse path:** add the
  deferred quarantine, privacy certification, commit/fence, and revalidation
  path for in-repo artifacts if this park is too common. **Expiry:** before
  plan/scenario preparation writes artifacts. **Escalated?** no.

- **Decision:** Restore the final spot-check state by cleaning and re-applying
  planned scenarios, not by cleaning to empty. **Options weighed:** leave
  browser-mutated seed state as-is; clean all seed data; clean then re-apply the
  planned scenarios. **Choice + why:** the owner wants the final branch left
  ready for spot-check with fresh seed data present. Clean plus re-apply gives
  a deterministic baseline. **Accepted downside:** readiness can park late if
  clean or re-apply needs protected-target authorization. **Reversible?**
  two-way door at implementation level, but owner requirement fixes the product
  behavior. **Mode:** PROCEED. **Reverse path:** change the helper if the spec
  changes. **Expiry:** n/a. **Escalated?** yes - owner chose fresh seeded
  baseline in discovery.

- **Decision:** If either PR artifact post fails, require both local fallback
  artifacts. **Options weighed:** fallback only for the failed artifact; fallback
  for both artifacts when any post fails; park on any GitHub failure. **Choice +
  why:** requiring both local files gives the reviewer one complete fallback
  location set while still allowing GitHub outages to degrade locally. **Accepted
  downside:** one successful PR comment may also have a redundant local copy.
  **Reversible?** two-way door. **Mode:** PROCEED. **Reverse path:** relax to
  per-artifact fallback if reviewers find duplication noisy. **Expiry:** after
  artifact broker tests land. **Escalated?** yes - owner chose local fallback
  and both artifacts in discovery.

- **Decision:** Enforce browser verification with simple MVP caps first.
  **Options weighed:** no browser/seed budget beyond the three fix-batch cap;
  hard park on any plan above one-pass limits; split into coarse bounded browser
  batches up to a total unattended budget and gate seed work with dry-run-derived
  operation limits plus in-lock operation-vector rechecks, then park. **Choice +
  why:** MVP uses simple caps for plan records, browser steps, browser passes,
  total browser fix batches, unique seed scenarios, planned seed operations, and
  phase elapsed time, parking above those caps rather than splitting or
  estimating fine-grained runtime/state size. The dry-run operation vector is
  rechecked inside the engine lock before seed apply/restore work, which bounds
  unattended seed work without building the full fast-follow budget subsystem.
  **Accepted downside:** legitimate large or seed-heavy PRs may park earlier
  than necessary until split batching and richer runtime/state-size/artifact
  optimization budgets land. **Reversible?** two-way door. **Mode:** PROCEED.
  **Reverse path:** add split batching and multi-dimensional budget helpers if
  real runs show the simple caps are too coarse. **Expiry:** after MVP budget
  helper tests and first real workflow runs. **Escalated?** no.

- **Decision:** Normalize dev-server profile commands at the test-pilot workflow
  boundary. **Options weighed:** require profiles to use a string command before
  this work lands; update `detect.py` and all templates to a new canonical type;
  add a workflow normalization helper that accepts current string and argv-array
  profile shapes plus package.json detections and feeds the server launcher a
  safe canonical command.
  **Choice + why:** normalize at the workflow boundary so existing test-pilot
  profiles with argv-array commands remain usable while avoiding shell
  interpretation; legacy string commands park in the MVP before the shell-string
  launcher, and package.json detections either normalize to argv from a safe
  script name or park. **Accepted downside:** legacy string profiles or package
  detections without safe script metadata may park until migrated or until an
  exact-authorization fast-follow lands. **Reversible?** two-way door. **Mode:**
  PROCEED. **Reverse path:** fold the adapter into `detect.py`/profile schema if
  a later migration standardizes the command type, or add exact string
  authorization if needed. **Expiry:** after implementation and compatibility
  tests. **Escalated?** no.

## Cross-cutting concerns

- **Security & privacy:** All data mutation goes through `engine.py` and its
  protected-target gates. The workflow never passes `--allow-protected` unless
  explicitly authorized for the current run. Artifact rendering uses an allowlist
  and `pr_comment.scrub`; it omits raw seed configs, protected target values,
  personal data values, auth headers, cookies, API keys, and secret-bearing
  request details. The same scrub/allowlist rule applies before durable browser
  run-log and status writes, not only before PR or fallback artifacts. Browser
  manifests, plan records, and generated blocks are written to machine-local or
  global storage in the MVP; if an in-repo store would require generated writes,
  the phase parks before writing. The deferred in-repo path must treat those
  files as exposed branch artifacts and pass a privacy gate plus secret scan
  before any commit/push. Browser
  navigation remains limited to configured origins. Argv-form dev-server
  commands are launched without shell interpretation; legacy shell-string
  commands park before launch in the MVP.
- **Observability:** `events.jsonl`, `test-pilot-status.json`, plan/result
  artifacts, and run logs provide the audit trail. A parked readout names the
  phase, branch/head, applicable/not-applicable classification, failing
  scenario or step, fix-batch count, artifact fallback paths, and baseline state
  where relevant.
- **Reliability & failure modes:** Critical dependencies fail closed: engine
  status, plan validation, seed apply, browser tool availability, dev-server
  config normalization/readiness/teardown, branch-head freshness, post-fix
  review-code coverage, browser revalidation after any review-code fix, remote
  PR-head reconciliation, dirty-worktree detection/recovery after fix attempts,
  clean committed fix-batch reconciliation, branch-artifact cleanliness policy,
  phase-cursor compatibility, browser-run caps, artifact availability, and
  baseline verification. GitHub
  comment posting degrades to local fallback only when both fallback artifacts
  are written.

## Verification strategy

The implementation should carry focused tests at the deterministic seams and
small smoke tests at the JS phase boundary. The JS phase-boundary smokes are
part of the enforced verification path: either wrap the Node composition cases in
pytest or add an explicit Node smoke step to both CI and the documented local
verify command, so the required verification catches showrunner orchestration
regressions.

- `test_pilot_applicability`: user-facing/browser-applicable branches,
  docs/CLI/library/internal-only not-applicable branches, uncertain branches,
  and failed or empty plan derivation parking rather than becoming
  not-applicable.
- Plan/scenario preparation leaf: exact-branch-state plan derivation, missing
  plan-record creation, existing plan-record update/confirmation, manifest
  merge, scenario availability before seed/browser work, machine-local artifact
  writes, in-repo store write requirements parking before any generated file is
  written, no dirty worktree after that park, and parking on setup or
  plan-preparation errors. Fast-follow tests cover quarantine, privacy gate,
  secret scan, commit/fence, and revalidation if in-repo writes are later added.
- `test_pilot_seed`: plan-record validation, dry-run before apply,
  apply-before-browser ordering, protected-target refusal, malformed plan
  details, partial apply, live lock, stale lock recovery, and unverified seeded
  state.
- `test_pilot_retry`: collect all app-bug failures before fixing, one batch
  addressing multiple failures, three total browser fix-batch cap, browser retry
  adapter emitting a synthetic breaker finding only after FR-13 no-progress is
  true, recurring individual failure with progress continuing instead of
  parking, affected-step subset reruns, and unknown affected coverage forcing a
  whole-plan rerun.
- `test_pilot_budget`: within-simple-caps pass, plan-record cap park,
  browser-step cap park, browser-pass cap park, browser-fix-batch cap park,
  unique-scenario cap park, seed clean/apply/reapply operation cap park for both
  initial apply and final baseline restore, phase elapsed-time cap park,
  in-lock operation-vector recheck before seed work, and rendered status/artifact
  size parks. Fast-follow tests cover split batches, fine-grained
  runtime/state-size budgets, and richer diagnostic byte budgets.
- `test_pilot_status` plus the `mark-ready` guard: applicable-ready,
  not-applicable-ready, missing status, malformed JSON, non-object JSON, missing
  or wrong `schemaVersion`, missing branch/head fields, stale head, incomplete
  records, low-confidence status, fix commits without refreshed review-code
  coverage, fix commits without verify-pass evidence for the same head,
  review-code fixes that require browser revalidation, stabilization-cycle
  exhaustion, skipped browser steps parking, the allowed re-derived-plan case
  preserving the skipped step/removal reason/updated plan in results, and final
  local head not matching the remote PR head. Browser-result source validation
  covers missing step results, non-browser or synthetic result sources, and the
  evidence/source checks required before a plan record can count as passed.
- Targetable review-code stabilization: fresh runDir per cycle/head, no reuse of
  `/tmp/showrunner-${workItem}-review-code`, reviewer/fixer/verify leaves bound
  to the explicit build worktree and expected head, `prov_entry --step review`
  upserting `review.covers` to the final tested head on pure clean, no covers
  stamp on `clean-with-skips`, review-code-induced commits forcing browser
  revalidation, and the `reviewStabilizationCycle` cap parking after two cycles.
- Phase-cursor compatibility: new cursor writes include phase name beside
  `lastGoodStep`, resume proceeds when numeric index/name match, resume parks
  before side effects when a changed phase list would reinterpret the numeric
  cursor, checkpoint schema valid samples include the phase-name field, malformed
  phase-name values are rejected where applicable, and unknown/newer checkpoint
  schema is tested as an incompatibility park, not as absent checkpoint
  `world_derive`.
- `test_pilot_artifacts`: plan and results posted successfully, one GitHub post
  failure causing both fallback artifacts to be required, missing fallback
  causing a park, plan artifact written before any seed/browser leaf is invoked,
  checkbox preservation, and scrubbed/allowlisted rendering.
- Browser-result/status aggregation: raw auth headers, cookies, API keys,
  protected values, personal values, and raw seed config values are omitted from
  persisted run logs and `test-pilot-status.json`; scrub failure drops the
  diagnostic or parks rather than writing raw values; oversized diagnostics are
  truncated with an omitted-byte marker, and still-oversized status/run-log/PR/
  fallback bodies park before write.
- `test_pilot_server_config`: existing argv-array `devCommand` profiles,
  string `devCommand` profiles parking in the MVP, package.json detections
  normalizing to argv or parking before launch, package script contents with
  shell metacharacters never reaching `devserver.start(..., shell=True)`,
  invalid/empty command values, `mayManageServer` false requiring an
  already-ready server, argv elements containing shell metacharacters passed as
  data or rejected, and normalized commands feeding the server lifecycle helpers
  without accidental shell expansion.
- Managed server lifecycle: teardown after browser failure, setup/readiness park
  after launch, timeout, exception, retry-loop terminal, and normal completion;
  already-ready external servers are not killed; owned orphan handles can be
  reclaimed while unknown port occupants park.
- `test_pilot_publish`: safe tracking-target push without force records a
  matching remote PR head; no tracking target, lost lease, push failure,
  unreadable PR head, and mismatched PR head all park with a readout and do not
  write ready status.
- Setup-path coverage: missing test-pilot calibration/profile and missing browser
  tool configuration or access park applicable branches with the required setup
  readout before mark-ready.
- Fix-batch worktree recovery: interrupted fix leaves that leave dirty
  uncommitted/untracked files, safe fence-and-reset of those files, reset
  failure parking, clean committed mutations with missing fix-batch/review-code
  records parking or deterministic write-ahead reconciliation, reconciled commits
  counting against the browser fix-batch cap, and refusal to write browser/status
  evidence until the worktree is clean and commit SHAs are recorded.
- Fresh-baseline restoration: clean plus re-apply, protected-target refusal,
  clean/apply failure, drift in engine status, and expected branch/slot entries
  present with no drift.
- Showrunner smoke/composition: phase order includes `test-pilot` before
  `mark-ready`; not-applicable proceeds; applicable-ready proceeds; applicable
  missing/stale/unreviewed/unpublished status parks before `mark-ready`; and a
  fix-batch path reruns targetable review-code on the tested worktree/head
  before ready status. This coverage must run in CI/local verification through
  pytest wrapping or an explicit Node smoke step.
- Resume/re-entry coverage: existing not-applicable status, scenarios, plan
  records, plan comments, results comments, and local fallback artifacts are
  reused or updated for the same branch/head rather than duplicated.

## Rollout & migration

No data migration is required for existing manifests or plan records. The new
status sidecar starts at schema version 1 and is optional on read: absent status
means the phase recomputes or parks; it never grants readiness. Existing
standalone test-pilot artifacts remain compatible because marker keys and
plan-record validation are reused.

Rollout is staged. First land the shared-spine cursor slice: write completed
phase name beside `lastGoodStep`, park on name/index mismatch, and make
unknown/newer checkpoint schema park instead of `world_derive`. Then insert the
`test-pilot` phase and its MVP helpers. Update user-facing workflow docs and
conventions that describe showrunner phase order, the showrunner/test-pilot
ownership boundary, the targetable review-code rerun, and the new status
sidecar. Rollback must retain the cursor name guard or otherwise fail closed for
checkpoints written after `test-pilot` entered `PHASES`; it is not enough to
delete the phase and mark-ready guard while reusing old numeric cursor
semantics. Once that guard is in place, rollback is straightforward: remove the
`test-pilot` phase behavior while leaving standalone test-pilot behavior intact.
The only persistent residue would be ignored status sidecars and local fallback
artifacts.

## Risks & mitigations

- **Applicability false positives park too often.** Mitigation: conservative
  classifier rules, structured rationale, and tests for docs/CLI/library
  not-applicable cases.
- **Applicability false negatives mark browser work ready too early.** Mitigation:
  not-applicable requires positive evidence and a current branch head; uncertain
  cases park rather than proceed.
- **Leaf agents spend too many tokens.** Mitigation: one plan leaf, one browser
  pass leaf per bounded pass, and one fix leaf per batch; no per-step subagents.
- **Large plans exhaust browser/tool time or artifact space.** Mitigation:
  MVP enforces simple caps for plan-record count, browser-step count,
  browser-pass count, total browser fix batches, unique seed scenarios, planned
  seed operations, rendered status/artifact size, and phase elapsed time, then
  parks. Split batching and richer runtime/state-size/artifact optimization
  budgets are fast-follow.
- **Rollback reinterprets a numeric phase cursor.** Mitigation: checkpoint cursor
  writes include the completed phase name beside `lastGoodStep`; resume verifies
  the name matches the current `PHASES` entry and parks on mismatch before
  mark-ready or any other side effect. Unknown-schema reads preserve an
  incompatibility reason and park rather than becoming no-checkpoint recovery.
- **In-repo test-pilot artifacts dirty the verified worktree or expose raw seed
  data.** Mitigation: MVP parks before generated in-repo manifest, plan-record,
  or block writes. A fast-follow may add quarantine, allowlist/scrub, secret
  scan, commit/fence, review-code/browser revalidation, and owner authorization
  for any PR-visible sensitive value.
- **Legacy or package-derived string dev-server commands execute shell
  metacharacters during an unattended run.** Mitigation: argv-array commands are
  the only unattended launch path in the MVP; legacy string commands are parsed
  for diagnostics but park before launch, package.json detections are
  argv-normalized or parked, and tests pin that neither source reaches the
  shell-string launcher.
- **Post-fix review-code accidentally resumes the pre-draft review loop.**
  Mitigation: extend the merged review-code phase to accept explicit worktree,
  head, and runDir targeting; key stabilization run dirs by cycle and head; and
  test that `clean-with-skips` records no covers stamp and parks readiness.
- **Fixes make the test plan stale.** Mitigation: branch-head metadata,
  post-fix validation, affected-step rerun rules, conditional review-code rerun,
  browser revalidation after review-code fixes, PR-head reconciliation, and a
  mark-ready freshness guard.
- **Interrupted fix attempts leave dirty local files.** Mitigation: fix-batch
  success requires recorded commit SHAs and a clean managed worktree; on resume
  or before any rerun/status/publish after a fix attempt, dirty worktree state is
  reset behind a lease fence or parks if it cannot be safely cleaned.
- **Seed reset leaves dirty or missing spot-check data.** Mitigation: clean plus
  re-apply through the engine, then verify expected branch/slot entries with no
  drift before readiness.
- **Artifacts leak sensitive data.** Mitigation: allowlist rendering,
  centralized scrub, no raw scenario configs in comments, and fail-closed
  omission on scrub errors.
- **Comment/fallback duplication on resume.** Mitigation: marker-managed
  `pr_comment.py` upserts, stable artifact keys, and fallback path reuse.

## Dependencies & assumptions

**Dependencies:**

- Existing showrunner workflow phases through `draft-PR` and `mark-ready`.
- The merged review-code phase is extended in place to support explicit
  worktree/head/runDir targeting for stabilization cycles.
- Existing test-pilot engine, store, blocks, plan records, profile resolution,
  PR comment helper, and browser execution conventions.
- A configured test-pilot profile, usable browser tool, and app server setup for
  branches where browser verification applies. Missing setup parks with a
  readout; it is not an outside manual test-pilot run.
- GitHub access for PR comments when available; local fallback artifacts are the
  in-workflow degradation path.

**Assumptions:**

- The build branch in `checkpoint.json` is the branch whose PR will be marked
  ready.
- Existing engine `validate-plan`, `apply`, `clean`, and `status` semantics are
  sufficient to prove seed readiness when combined with an expected branch/slot
  verification helper.
- Browser leaf agents can access the configured browser MCP/tool in the current
  host. If not, the applicable branch parks before mark-ready.
- The workflow's three browser-fix-batch limit is enough unattended repair before
  maintainer intervention is more valuable than continued automated work.
- The two-cycle review-code stabilization cap is enough to catch review-induced
  fixes without letting the nested browser/review loops run indefinitely.

## UI / UX

N/A - this work adds workflow behavior and PR/local artifacts, not application UI.
