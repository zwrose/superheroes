---
superheroes: doc
schemaVersion: 1
docType: tasks
workItem: test-pilot-native-workflow-phase-2ab475
issue: 90
size: medium
status: approved
gates: {review: passed}
producedBy: "the-architect@0.2.0"
created: "2026-06-26"
updated: "2026-06-26"
---
# Showrunner Test-pilot Verification - Tasks

> **Build contract (superheroes).** These tasks are executed by the producer's **Build**
> phase - **not here**. Build invokes superpowers **subagent-driven-development** with the
> worktree **pre-verified, not created**, and **without** `finishing-a-development-branch`;
> the **producer enforces both clips** at invocation. `size: medium`. Advance to Build
> only once `gates.review: passed`.

**Goal:** Add a native showrunner `test-pilot` phase that resolves browser verification before
`mark-ready`: not-applicable branches proceed with a recorded rationale; applicable branches
derive/update the test plan, seed, run browser checks, fix/retry app bugs within caps, publish
plan/results artifacts, restore fresh seed data, re-cover post-browser fixes with review-code,
and only then allow the PR to become ready.

**Architecture:** Keep `showrunner.js` as the control-flow spine and put deterministic judgement
in small Python helpers with CLI seams. Land the shared checkpoint cursor guard first, then add
test-pilot helpers, a JS `test_pilot_phase.js`, targeted review-code support, a `mark-ready`
status guard, and CI-enforced smoke coverage.

**Tech Stack:** Python 3 stdlib helpers and pytest; Node.js showrunner orchestration and smoke
tests; existing superheroes test-pilot engine/store/comment helpers; no new third-party runtime
dependency.

## Global Constraints

- Preserve standalone `test-pilot-plan` and `test-pilot-execute`; this work adds workflow
  ownership, not replacement.
- Do not hand-edit plugin versions. Use Conventional Commit messages scoped to `superheroes`.
- Every branch-mutating or readiness-changing path fails closed on unknown, missing, stale, or
  garbled durable state.
- The workflow never marks ready from a skipped browser step, stale browser result, stale review
  coverage, dirty/unpublished branch head, missing artifact, or unverified seed baseline.
- Generated test-pilot manifests, plan records, and blocks use machine-local/global storage in the
  MVP; if an applicable run would need generated in-repo writes, it parks before writing.
- Dev-server commands launched unattended must be argv arrays passed with `shell=False`; legacy
  strings and unsafe package-derived strings park before launch.
- The human spot-check checklist remains human-owned. The workflow may publish/update it, but never
  checks boxes.
- CI/local verification must include the repository validators, pytest suite, and the new
  showrunner Node smoke coverage through an enforced step.

---

### Task 1: Shared checkpoint cursor guard

**Files:**
- Modify: `plugins/superheroes/lib/checkpoint.py`
- Modify: `plugins/superheroes/lib/checkpoint_entry.py`
- Modify: `plugins/superheroes/lib/recover_entry.py`
- Modify: `plugins/superheroes/lib/recover.py`
- Modify: `plugins/superheroes/lib/showrunner.js`
- Modify: `eval/lib/schemas/checkpoint.schema.json`
- Modify: `eval/lib/tests/test_schemas.py`
- Modify: `plugins/superheroes/lib/tests/test_checkpoint.py`
- Modify: `plugins/superheroes/lib/tests/test_recover.py`
- Modify: `plugins/superheroes/lib/tests/showrunner_resume_smoke.js`

**Interfaces:**
- Produces: checkpoint records with both `lastGoodStep` and `lastGoodPhase`.
- Produces: a resume guard that parks before phase selection when `PHASES[lastGoodStep]` does not
  equal the stored `lastGoodPhase`.
- Produces: unknown/newer checkpoint schema reads that preserve an incompatibility reason instead
  of becoming ordinary no-checkpoint `world_derive`.

- [ ] **Step 1: Write failing cursor/schema tests**

Add tests that assert:
- `checkpoint.new("wi", "branch")` includes `lastGoodPhase: None`.
- `checkpoint.write(path, checkpoint, completed_phase="draft-PR")` or equivalent writer input persists
  `lastGoodPhase`.
- `showrunner.recordCursor(workItem, step, phase, sideEffect)` passes the phase name to
  `checkpoint_entry.py --phase <name>` before any resume guard can reject missing phase names.
- `recover.reconcile` returns a parking/gate action when the world supplies
  `phase_name_mismatch=True` or a checkpoint read supplies an incompatibility reason.
- The checkpoint JSON schema valid sample includes `lastGoodPhase`.
- Schema tests reject malformed `lastGoodPhase` values such as numbers or empty objects.

Run:
`python3 -m pytest plugins/superheroes/lib/tests/test_checkpoint.py plugins/superheroes/lib/tests/test_recover.py eval/lib/tests/test_schemas.py -q`

Expected: FAIL on missing `lastGoodPhase` behavior/schema support.

- [ ] **Step 2: Implement the cursor data model and reader result**

Update `checkpoint.py` so the public contract is:

```python
SCHEMA_VERSION = 1


def new(work_item, branch, pr=None, last_good_step=None, last_good_phase=None, updated_at=None):
    return {
        "schemaVersion": SCHEMA_VERSION,
        "workItem": work_item,
        "branch": branch,
        "pr": pr,
        "lastGoodStep": last_good_step,
        "lastGoodPhase": last_good_phase,
        "updatedAt": updated_at,
    }


def read(path):
    # Return a checkpoint dict on compatible schema.
    # Return {"_incompatible": True, "reason": "checkpoint schema is newer than this runner"} for unknown/newer schema or malformed
    # durable checkpoint shapes that must park instead of world-deriving.
    # Return None only when no checkpoint exists.
```

Keep existing callers compatible by accepting checkpoints that lack `lastGoodPhase` only when
`lastGoodStep` is `None`; once a numeric step exists, missing phase name is an incompatibility.

- [ ] **Step 3: Thread phase names through cursor writes and resume**

Update `checkpoint_entry.py` to accept `--phase <name>` and write the completed phase name beside
`--step`. Update `showrunner.recordCursor(workItem, step, phase, sideEffect)` and all current call
sites in this same task so every cursor write includes the completed phase name. Update
`recover_entry.py` to compare `checkpoint.lastGoodPhase` with the current phase list before
calling `recover.reconcile`; on mismatch, emit a gate/park action with a human-readable reason.

- [ ] **Step 4: Run checkpoint and schema tests**

Run:
`python3 -m pytest plugins/superheroes/lib/tests/test_checkpoint.py plugins/superheroes/lib/tests/test_recover.py eval/lib/tests/test_schemas.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add plugins/superheroes/lib/checkpoint.py plugins/superheroes/lib/checkpoint_entry.py plugins/superheroes/lib/recover_entry.py plugins/superheroes/lib/recover.py plugins/superheroes/lib/showrunner.js eval/lib/schemas/checkpoint.schema.json eval/lib/tests/test_schemas.py plugins/superheroes/lib/tests/test_checkpoint.py plugins/superheroes/lib/tests/test_recover.py plugins/superheroes/lib/tests/showrunner_resume_smoke.js
git commit -m "feat(superheroes): guard showrunner phase cursor names"
```

---

### Task 2: Test-pilot applicability and status helpers

**Files:**
- Create: `plugins/superheroes/lib/test_pilot_applicability.py`
- Create: `plugins/superheroes/lib/test_pilot_applicability_cli.py`
- Create: `plugins/superheroes/lib/test_pilot_status.py`
- Create: `plugins/superheroes/lib/test_pilot_status_cli.py`
- Create: `plugins/superheroes/lib/tests/test_test_pilot_applicability.py`
- Create: `plugins/superheroes/lib/tests/test_test_pilot_status.py`
- Modify: `plugins/superheroes/lib/pr_entry.py`
- Modify: `plugins/superheroes/lib/tests/test_pr_phase.py`

**Interfaces:**
- Produces: `test_pilot_applicability.decide(diff, detectors, profile, plan_result=None)`.
- Produces: `test_pilot_applicability_cli.py decide --diff-json <path> --detectors-json <path>
  --profile-json <path> [--plan-result-json <path>]` returning verdict JSON.
- Produces: `test_pilot_status.write(path, status)`, `read(path)`, and `assert_current(status, head)`.
- Produces: `test_pilot_status_cli.py assert-current --work-item <slug> --head <sha>` returning
  JSON `{"ok": true}` or `{"ok": false, "reason": "stale test-pilot status"}`.
- Produces: `test_pilot_status_cli.py write --work-item <slug> --status-json <path>` for the Node
  phase to durably write milestone and ready status through the same schema validator.
- Consumes: `checkpoint.branch` and PR head/current head information from existing control-plane
  paths.

- [ ] **Step 1: Write failing applicability tests**

Cover:
- docs-only, CLI-only, library-only, and internal workflow-only branch summaries return
  `{"verdict": "not_applicable", "rationale": "no browser-verifiable workflow changed"}`.
- user-facing/runnable/browser behavior returns `{"verdict": "applicable"}`.
- uncertain signals return `{"verdict": "park", "reason": "cannot determine browser applicability"}`.
- applicable branches with failed or empty plan derivation remain `park`; they never become
  `not_applicable`.

Run:
`python3 -m pytest plugins/superheroes/lib/tests/test_test_pilot_applicability.py -q`

Expected: FAIL because the helper does not exist.

- [ ] **Step 2: Implement `test_pilot_applicability.py`**

Implement a pure function that classifies from explicit structured inputs:

```python
def decide(diff=None, detectors=None, profile=None, plan_result=None):
    """Return {"verdict": "applicable"|"not_applicable"|"park", "rationale"|"reason": str}."""
```

Rules:
- `not_applicable` requires positive no-browser evidence: docs-only, CLI-only, library-only, or
  internal-only with no runnable/browser/user-facing signal.
- `applicable` wins when the diff/detectors/profile indicate user-facing, browser, route/page,
  frontend, baseUrl, dev-server, or runnable web behavior.
- `park` wins on uncertainty, missing required setup for applicable work, failed plan derivation,
  empty applicable plan derivation, or malformed inputs.

- [ ] **Step 3: Write failing status and mark-ready guard tests**

Cover:
- applicable-ready status proceeds only when every plan record passed, artifacts are available,
  baseline is verified, `reviewCoverageHead == head` and `verifyPassedHead == head` when fixes
  exist, `remotePrHead == head`, and at least one browser-executed plan record exists.
- not-applicable-ready proceeds with current `head` and a rationale without requiring plan/results.
- missing status, malformed JSON, non-object JSON, missing/wrong `schemaVersion`, missing branch/head
  fields, stale head, incomplete records, low confidence, skipped steps, missing fallback artifacts,
  unreviewed fix commits, unverified fix commits, unpublished local head, and stale plan records park.

Run:
`python3 -m pytest plugins/superheroes/lib/tests/test_test_pilot_status.py plugins/superheroes/lib/tests/test_pr_phase.py -q`

Expected: FAIL because the helper/guard is absent.

- [ ] **Step 4: Implement status helper and guard seam**

Implement schema version 1:

```python
SCHEMA_VERSION = 1


def ready_applicable(head, records, artifacts, baseline, **meta):
    """Return {"ok": True, "kind": "applicable"} only after all required checks pass."""


def ready_not_applicable(head, rationale, **meta):
    """Return {"ok": True, "kind": "not_applicable"} only when the current head has a rationale."""


def read(path):
    # Return {"ok": False, "reason": "missing test-pilot status"} for missing/unreadable/malformed/newer schema.


def assert_current(status, head):
    # Return {"ok": True, "kind": "applicable"|"not_applicable"} or {"ok": False, "reason": str}.
```

`ready_applicable` must explicitly reject missing or stale values for: head/branch, at least one
browser-executed plan record, every record passed or preserved as an allowed re-derived skipped
step, plan artifact, results artifact, fallback artifacts when PR posting failed, fresh baseline
verified at `head`, review coverage at `head`, verify-pass at `head` when fixes exist, and remote PR
head equal to `head`.

Update `pr_entry.py --step mark-ready` so it calls the CLI before `gh pr ready`; non-ok status parks
with the returned reason.

- [ ] **Step 5: Run status and applicability tests**

Run:
`python3 -m pytest plugins/superheroes/lib/tests/test_test_pilot_applicability.py plugins/superheroes/lib/tests/test_test_pilot_status.py plugins/superheroes/lib/tests/test_pr_phase.py -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add plugins/superheroes/lib/test_pilot_applicability.py plugins/superheroes/lib/test_pilot_applicability_cli.py plugins/superheroes/lib/test_pilot_status.py plugins/superheroes/lib/test_pilot_status_cli.py plugins/superheroes/lib/pr_entry.py plugins/superheroes/lib/tests/test_test_pilot_applicability.py plugins/superheroes/lib/tests/test_test_pilot_status.py plugins/superheroes/lib/tests/test_pr_phase.py
git commit -m "feat(superheroes): add test-pilot readiness status guard"
```

---

### Task 3: Budget and retry deciders

**Files:**
- Create: `plugins/superheroes/lib/test_pilot_budget.py`
- Create: `plugins/superheroes/lib/test_pilot_retry.py`
- Create: `plugins/superheroes/lib/test_pilot_budget_cli.py`
- Create: `plugins/superheroes/lib/test_pilot_retry_cli.py`
- Create: `plugins/superheroes/lib/tests/test_test_pilot_budget.py`
- Create: `plugins/superheroes/lib/tests/test_test_pilot_retry.py`

**Interfaces:**
- Produces: finite work decisions for plan records, browser steps, browser passes, fix batches,
  unique seed scenarios, planned seed operations, elapsed time, and rendered artifact/status sizes.
- Produces: retry decisions `fix_batch`, `rerun_all`, `rerun_subset`, `park_no_progress`,
  `park_cap_reached`.
- Consumes: `circuit_breaker.py` only after the browser adapter has applied FR-13 progress semantics.

- [ ] **Step 1: Write failing budget tests**

Cover:
- within-simple-caps returns `within_budget`.
- cap parks for plan records, browser steps, browser passes, browser fix batches, unique seed
  scenarios, planned seed operations for initial apply and baseline restore, elapsed time, and
  rendered artifact/status size.
- in-lock operation-vector recheck parks if resumed state adds seed operations after the dry run.

Run:
`python3 -m pytest plugins/superheroes/lib/tests/test_test_pilot_budget.py -q`

Expected: FAIL because the helper does not exist.

- [ ] **Step 2: Implement `test_pilot_budget.py` and CLI**

Implement:

```python
DEFAULT_LIMITS = {
    "planRecords": 20,
    "browserSteps": 80,
    "browserPasses": 4,
    "browserFixBatches": 3,
    "uniqueScenarios": 40,
    "seedOperations": 120,
    "elapsedSeconds": 3600,
    "renderedBytes": 200_000,
}


def decide(counts, limits=None):
    """Return {"action": "within_budget"} or {"action": "park_budget_exceeded", "reason": str}."""
```

Normalize missing counts to zero only for optional dimensions; malformed numeric values park.

- [ ] **Step 3: Write failing retry tests**

Cover:
- app-bug failures are collected into one fix batch before fixing.
- one batch may address multiple failures.
- after three total fix batches, any remaining failed step returns `park_cap_reached`.
- two consecutive fix batches with the same scrubbed summary and no failed/affected step moving from
  fail to pass returns `park_no_progress`.
- a recurring individual failure does not park when another failed or affected step made progress.
- unknown affected coverage returns `rerun_all`; known coverage returns `rerun_subset` with failed and
  affected step ids.

Run:
`python3 -m pytest plugins/superheroes/lib/tests/test_test_pilot_retry.py -q`

Expected: FAIL because the helper does not exist.

- [ ] **Step 4: Implement `test_pilot_retry.py` and CLI**

Implement:

```python
def decide(pass_result, history, changed_files=None, dependency_map=None):
    """Return retry action JSON for browser fix-and-rerun control."""
```

Use stable failure identity fields: plan-record id, step id, failure class, and scrubbed summary.
Compute FR-13 no-progress before calling the shared circuit breaker. Emit a single synthetic
breaker finding only after the FR-13 no-progress predicate is true.

- [ ] **Step 5: Run budget/retry tests**

Run:
`python3 -m pytest plugins/superheroes/lib/tests/test_test_pilot_budget.py plugins/superheroes/lib/tests/test_test_pilot_retry.py -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add plugins/superheroes/lib/test_pilot_budget.py plugins/superheroes/lib/test_pilot_budget_cli.py plugins/superheroes/lib/test_pilot_retry.py plugins/superheroes/lib/test_pilot_retry_cli.py plugins/superheroes/lib/tests/test_test_pilot_budget.py plugins/superheroes/lib/tests/test_test_pilot_retry.py
git commit -m "feat(superheroes): add test-pilot budget and retry deciders"
```

---

### Task 4: Server configuration and branch publication helpers

**Files:**
- Create: `plugins/superheroes/lib/test_pilot_server_config.py`
- Create: `plugins/superheroes/lib/test_pilot_server_config_cli.py`
- Create: `plugins/superheroes/lib/test_pilot_publish.py`
- Create: `plugins/superheroes/lib/test_pilot_publish_cli.py`
- Create: `plugins/superheroes/lib/tests/test_test_pilot_server_config.py`
- Create: `plugins/superheroes/lib/tests/test_test_pilot_publish.py`
- Modify: `plugins/superheroes/lib/devserver.py`
- Modify: `plugins/superheroes/lib/detect.py`
- Modify: `plugins/superheroes/lib/tests/test_devserver.py`
- Modify: `plugins/superheroes/lib/tests/test_detect.py`

**Interfaces:**
- Produces: canonical server config with already-ready external server or argv managed command.
- Produces: `test_pilot_server_config_cli.py resolve --profile-json <path> --detection-json <path>
  --work-item <slug>` returning the canonical server context consumed by `test_pilot_phase.js`.
- Produces: managed server lifecycle rules: teardown on every terminal path; never kill external
  already-ready servers.
- Produces: publication helper that non-force pushes the final tested head and requires remote PR
  head equality before readiness.
- Produces: `test_pilot_publish_cli.py publish --work-item <slug> --head <sha> --status-json <path>`
  returning PR-head equality JSON and writing no ready status on failure.

- [ ] **Step 1: Write failing server config tests**

Cover:
- argv-array profile commands remain arrays and are launched with `shell=False`.
- empty argv, non-string argv members, and unsafe argv elements park before launch.
- legacy string `devCommand` parks before launch.
- package.json detections normalize to `["npm", "run", "<script>"]` when the detector exposes a
  safe script name, or park before launch when only an unsafe string is available.
- package script content containing shell metacharacters never reaches `devserver.start(command, shell=True)`.
- `mayManageServer: false` requires an already-ready server and never starts or tears down it.
- managed server teardown is invoked after browser failure, setup/readiness park after launch,
  timeout, exception, retry-loop terminal, and normal completion.

Run:
`python3 -m pytest plugins/superheroes/lib/tests/test_test_pilot_server_config.py plugins/superheroes/lib/tests/test_devserver.py plugins/superheroes/lib/tests/test_detect.py -q`

Expected: FAIL on missing config helper and current string shell path.

- [ ] **Step 2: Implement safe server command normalization**

Update `detect.detect_dev_server` to include structured package detection metadata without breaking
existing callers:

```python
{"command": "npm run dev", "source": "package.json", "script": "dev", "argv": ["npm", "run", "dev"], "note": ""}
```

Update `devserver.start` to accept list commands with `shell=False` and preserve existing string
behavior only for callers that are not the new unattended workflow. Implement
`test_pilot_server_config.normalize(profile, detection, port_in_use, readiness)` returning
`{"action": "ready_external", "baseUrl": str, "allowedOrigins": [str], "teardown": None}`,
`{"action": "managed", "argv": [str], "cwd": str, "baseUrl": str, "allowedOrigins": [str]}`, or
`{"action": "park", "reason": str}`.

- [ ] **Step 3: Write failing publication tests**

Cover:
- safe tracking-target push without force records matching remote PR head.
- no tracking target, lost lease, push failure, unreadable PR head, and mismatched PR head return
  park/readout and do not write ready status.

Run:
`python3 -m pytest plugins/superheroes/lib/tests/test_test_pilot_publish.py -q`

Expected: FAIL because the helper does not exist.

- [ ] **Step 4: Implement `test_pilot_publish.py`**

Implement a seam-friendly helper with injectable `renew`, `fence_ok`, `push`, `read_pr_head`, and
`write_status` callables. The pure decision path must require:
- lease renewed and fenced before push,
- non-force push to the existing PR branch,
- remote PR head equals the final locally tested head,
- ready status is written only after all checks pass.

- [ ] **Step 5: Run server/publish tests**

Run:
`python3 -m pytest plugins/superheroes/lib/tests/test_test_pilot_server_config.py plugins/superheroes/lib/tests/test_test_pilot_publish.py plugins/superheroes/lib/tests/test_devserver.py plugins/superheroes/lib/tests/test_detect.py -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add plugins/superheroes/lib/test_pilot_server_config.py plugins/superheroes/lib/test_pilot_server_config_cli.py plugins/superheroes/lib/test_pilot_publish.py plugins/superheroes/lib/test_pilot_publish_cli.py plugins/superheroes/lib/devserver.py plugins/superheroes/lib/detect.py plugins/superheroes/lib/tests/test_test_pilot_server_config.py plugins/superheroes/lib/tests/test_test_pilot_publish.py plugins/superheroes/lib/tests/test_devserver.py plugins/superheroes/lib/tests/test_detect.py
git commit -m "feat(superheroes): harden test-pilot server and publish gates"
```

---

### Task 5: Seed, artifact, and browser-result helpers

**Files:**
- Create: `plugins/superheroes/lib/test_pilot_seed.py`
- Create: `plugins/superheroes/lib/test_pilot_seed_cli.py`
- Create: `plugins/superheroes/lib/test_pilot_artifacts.py`
- Create: `plugins/superheroes/lib/test_pilot_artifacts_cli.py`
- Create: `plugins/superheroes/lib/test_pilot_results.py`
- Create: `plugins/superheroes/lib/test_pilot_results_cli.py`
- Create: `plugins/superheroes/lib/tests/test_test_pilot_seed.py`
- Create: `plugins/superheroes/lib/tests/test_test_pilot_artifacts.py`
- Create: `plugins/superheroes/lib/tests/test_test_pilot_results.py`

**Interfaces:**
- Produces: seed apply and fresh-baseline restore through existing `engine.py` semantics.
- Produces: `test_pilot_seed_cli.py prepare --records-json <path>` and `restore-baseline
  --records-json <path>` for the Node phase.
- Produces: artifact renderer/upserter that preserves human checkboxes and requires both fallback
  artifacts when either PR comment post fails.
- Produces: `test_pilot_artifacts_cli.py ensure --plan-json <path> --results-json <path>
  --pr <number>` returning PR comment URLs or fallback paths.
- Produces: result aggregation that accepts only browser-derived evidence/source and scrubbed,
  byte-capped diagnostics.
- Produces: `test_pilot_results_cli.py aggregate --raw-json <path>` returning normalized record
  verdicts, diagnostics, and pass/fail totals.

- [ ] **Step 1: Write failing seed tests**

Cover:
- plan-record validation before apply.
- dry-run before apply.
- apply before browser execution.
- protected-target refusal.
- malformed plan details.
- partial apply.
- live lock parks, stale lock unlocks then applies.
- unverified seeded state parks.
- final baseline restore performs clean plus re-apply, verifies expected branch/slot entries, and
  parks on protected-target refusal, clean/apply failure, or drift.

Run:
`python3 -m pytest plugins/superheroes/lib/tests/test_test_pilot_seed.py -q`

Expected: FAIL because the helper does not exist.

- [ ] **Step 2: Implement `test_pilot_seed.py`**

Implement seam-friendly functions:

```python
def prepare_records(records, engine, budget):
    """Validate, dry-run, apply, and verify before browser execution."""


def restore_baseline(records, engine, budget):
    """Dry-run restore, clean each planned branch/slot, re-apply scenarios, verify no drift."""
```

Never pass `--allow-protected` in the workflow helper. Treat unreadable engine status as park.

- [ ] **Step 3: Write failing artifact/result tests**

Cover:
- plan artifact is written before seed/browser leaf is invoked.
- plan PR comment success and results PR comment success need no local fallback.
- one GitHub post failure requires both plan and results fallback artifacts.
- missing fallback artifact parks.
- plan checkbox state is preserved by `pr_comment.merge_checkboxes`.
- artifact rendering includes scenario ids, step ids, instructions, expected outcomes, pass/fail,
  scrubbed notes, fix SHAs, and coverage rationale.
- raw seed configs, credentials, auth headers, cookies, protected values, personal values, and
  secret-bearing request details are omitted or scrubbed.
- scrub failure drops diagnostics or parks; oversized output parks before write.
- non-browser or synthetic result sources never count as passed.

Run:
`python3 -m pytest plugins/superheroes/lib/tests/test_test_pilot_artifacts.py plugins/superheroes/lib/tests/test_test_pilot_results.py -q`

Expected: FAIL because helpers do not exist.

- [ ] **Step 4: Implement artifact and result helpers**

Implement:

```python
def render_plan(records):
    """Return {"ok": True, "body": str, "recordIds": [str]} or {"ok": False, "reason": str}."""


def render_results(status):
    """Return {"ok": True, "body": str, "summary": dict} or {"ok": False, "reason": str}."""


def ensure_artifacts(pr_number, key, plan_body, results_body, poster, fallback_writer):
    """Return {"ok": True, "plan": artifact_ref, "results": artifact_ref}; require both fallback files if either PR post fails."""


def aggregate_browser_results(raw_results, scrubber, byte_limits):
    """Return {"ok": True, "records": list, "totals": dict} only for browser-derived evidence."""
```

Use `pr_comment.upsert`, `pr_comment.merge_checkboxes`, and `pr_comment.scrub`; write fallback paths
under the resolved test-pilot plans directory and return them in status.

- [ ] **Step 5: Run seed/artifact/result tests**

Run:
`python3 -m pytest plugins/superheroes/lib/tests/test_test_pilot_seed.py plugins/superheroes/lib/tests/test_test_pilot_artifacts.py plugins/superheroes/lib/tests/test_test_pilot_results.py -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add plugins/superheroes/lib/test_pilot_seed.py plugins/superheroes/lib/test_pilot_seed_cli.py plugins/superheroes/lib/test_pilot_artifacts.py plugins/superheroes/lib/test_pilot_artifacts_cli.py plugins/superheroes/lib/test_pilot_results.py plugins/superheroes/lib/test_pilot_results_cli.py plugins/superheroes/lib/tests/test_test_pilot_seed.py plugins/superheroes/lib/tests/test_test_pilot_artifacts.py plugins/superheroes/lib/tests/test_test_pilot_results.py
git commit -m "feat(superheroes): add test-pilot seed and artifact helpers"
```

---

### Task 6: Showrunner test-pilot phase skeleton and not-applicable path

**Files:**
- Create: `plugins/superheroes/lib/test_pilot_phase.js`
- Modify: `plugins/superheroes/lib/showrunner.js`
- Create: `plugins/superheroes/lib/tests/showrunner_test_pilot_phase_smoke.js`
- Create: `plugins/superheroes/lib/tests/test_showrunner_node_smokes.py`
- Modify: `.github/workflows/ci.yml`
- Modify: `CLAUDE.md`

**Interfaces:**
- Produces: `testPilotPhase(workItem, generation, deps)` returning the existing phase result
  contract `{confidence, assumptions}`.
- Produces: `PHASES` order `plan -> review-plan -> tasks -> review-tasks -> workhorse ->
  review-code -> draft-PR -> test-pilot -> mark-ready -> ship`.
- Produces: CI-enforced Node smoke coverage via pytest wrapper or explicit CI step.

- [ ] **Step 1: Write failing phase-order and smoke-enforcement tests**

Cover:
- `PHASES` includes `test-pilot` after `draft-PR` and before `mark-ready`.
- `recordCursor` writes both step and phase name.
- `mark-ready` is not reached when test-pilot returns low confidence.
- not-applicable status with current head proceeds.
- uncertain applicability parks.
- failed/empty applicable plan derivation parks and does not become not-applicable.
- applicable branches missing test-pilot calibration/profile park with a setup readout and do not
  run browser checks or mark ready.
- applicable branches with no usable browser MCP/tool park with a setup readout and do not run
  browser checks or mark ready.
- Node smoke files are executed by CI/local verification, either through a pytest wrapper test or an
  explicit CI step.

Run:
`python3 -m pytest plugins/superheroes/lib/tests/test_showrunner_node_smokes.py -q`

Expected: FAIL because the phase/smoke enforcement is absent.

- [ ] **Step 2: Implement phase wiring**

Update `showrunner.js`:
- import `test_pilot_phase.js`,
- insert `test-pilot` into `PHASES`,
- call `deps.testPilot || testPilotPhase` for that phase,
- pass phase name into `recordCursor(workItem, i, phase, sideEffect)`,
- keep existing side-effect semantics unchanged.

Implement `test_pilot_phase.js` with a dependency-injected skeleton that:
- resolves checkpoint branch/PR/current head,
- classifies applicability,
- writes not-applicable status and returns high confidence when not applicable,
- returns low confidence with scrubbed assumptions on park/setup errors,
- exports `testPilotPhase` for smokes.

- [ ] **Step 3: Run phase smokes after implementation**

Run:
`node plugins/superheroes/lib/tests/showrunner_test_pilot_phase_smoke.js`

Expected: PASS after implementation.

- [ ] **Step 4: Run enforced smoke wrapper**

Run:
`python3 -m pytest plugins/superheroes/lib/tests/test_showrunner_node_smokes.py -q`

Expected: PASS and include the new `showrunner_test_pilot_phase_smoke.js` in the enforced list.

- [ ] **Step 5: Commit**

```bash
git add plugins/superheroes/lib/test_pilot_phase.js plugins/superheroes/lib/showrunner.js plugins/superheroes/lib/tests/showrunner_test_pilot_phase_smoke.js plugins/superheroes/lib/tests/test_showrunner_node_smokes.py .github/workflows/ci.yml CLAUDE.md
git commit -m "feat(superheroes): wire native test-pilot phase"
```

---

### Task 7: Applicable preparation, seed, browser execution, and artifacts

**Files:**
- Modify: `plugins/superheroes/lib/test_pilot_phase.js`
- Modify: `plugins/superheroes/lib/tests/showrunner_test_pilot_phase_smoke.js`
- Modify: `plugins/superheroes/lib/tests/test_showrunner_node_smokes.py`

**Interfaces:**
- Consumes: helpers from Tasks 2 through 5.
- Produces: applicable path through plan preparation, plan artifact, seed apply, browser execution,
  result aggregation, and status update.

- [ ] **Step 1: Write failing applicable-flow smokes**

Cover:
- applicable branch derives branch-state test plan before artifacts, seed, or browser leaf.
- missing plan records are created before browser execution.
- existing plan records are updated or confirmed without losing human checkbox state.
- invalid plan records park before browser execution.
- generated machine-local/global plan manifests are merged with existing records.
- generated in-repo store writes park before touching the worktree and leave no dirty files.
- resume reuses or updates prior plan records without duplicating scenario or step ids.
- plan artifact is available before seeding/browser execution.
- seed apply happens before first browser step.
- skipped steps in a re-derived plan may proceed only when status preserves the skipped step id,
  removal reason, prior result, and updated plan context.
- skipped steps that disappear without the required preservation fields park before readiness.
- browser leaf receives `baseUrl` and `allowedOrigins` from server resolution.
- off-origin navigation or off-origin results cannot count as browser-derived evidence and park with
  a bounded setup/evidence readout.
- every browser step must have browser-derived pass/fail evidence.
- no browser-executed plan records parks with no-test-plan readout.
- skipped/incomplete/failing records park before readiness.

Run:
`node plugins/superheroes/lib/tests/showrunner_test_pilot_phase_smoke.js`

Expected: FAIL until applicable flow exists.

- [ ] **Step 2: Implement applicable preparation sequence**

In `test_pilot_phase.js`, implement dependency-injected leaves:
- `derivePlan`
- `preparePlanRecords`
- `prepareArtifacts`
- `resolveServer`
- `withManagedServer`
- `seedRecords`
- `runBrowserPass`
- `aggregateResults`
- `writeStatus`

The phase must write a current-head status after each durable milestone and park on low-confidence
helper output. Machine-local/global test-pilot store writes are allowed; required in-repo writes park
before generated files are written.
Before `runBrowserPass`, call `test_pilot_server_config_cli.py resolve`, confirm calibration/browser
tool/baseUrl/allowedOrigins, start any managed server with argv + `shell=False`, pass the resulting
context to the browser leaf, and tear down managed servers in a `finally` path for browser failure,
setup park, retry-loop terminal, exception, or success. Already-ready external servers are never
terminated by this phase.

- [ ] **Step 3: Run applicable-flow smokes and helper tests**

Run:
`node plugins/superheroes/lib/tests/showrunner_test_pilot_phase_smoke.js`

Expected: PASS for not-applicable and applicable no-fix paths.

Run:
`python3 -m pytest plugins/superheroes/lib/tests/test_test_pilot_seed.py plugins/superheroes/lib/tests/test_test_pilot_artifacts.py plugins/superheroes/lib/tests/test_test_pilot_results.py -q`

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add plugins/superheroes/lib/test_pilot_phase.js plugins/superheroes/lib/tests/showrunner_test_pilot_phase_smoke.js plugins/superheroes/lib/tests/test_showrunner_node_smokes.py
git commit -m "feat(superheroes): run applicable test-pilot preparation flow"
```

---

### Task 8: Browser fix batches and retry loop

**Files:**
- Modify: `plugins/superheroes/lib/test_pilot_phase.js`
- Modify: `plugins/superheroes/lib/tests/showrunner_test_pilot_phase_smoke.js`
- Modify: `plugins/superheroes/lib/tests/test_showrunner_node_smokes.py`

**Interfaces:**
- Consumes: `test_pilot_retry.py`, `test_pilot_budget.py`, `test_pilot_seed.py`, and
  worktree cleanliness/fence seams.
- Produces: collected app-bug failures, up to three fix batches, affected-step/whole-plan reruns,
  and clean committed mutation reconciliation. Final fresh-baseline restore is intentionally deferred
  to Task 10 after review-code stabilization has finished mutating the branch.

- [ ] **Step 1: Write failing fix/retry smokes**

Cover:
- all app-bug failures in a pass are collected before one fix batch is dispatched.
- one fix batch may address multiple failed steps and records commit SHAs.
- rerun is whole-plan when affected coverage is unknown.
- rerun is failed plus affected steps when dependency map is known.
- three total browser fix batches parks if failures remain.
- no-progress predicate parks only when same scrubbed summary repeats and no failed/affected step
  changes from fail to pass.
- recurring individual failure with progress elsewhere continues.
- dirty uncommitted/untracked fix leftovers are reset behind a lease fence or park.
- clean committed mutations without matching fix-batch/review-code history park unless a
  write-ahead batch intent or returned SHA allows deterministic reconciliation.

Run:
`node plugins/superheroes/lib/tests/showrunner_test_pilot_phase_smoke.js`

Expected: FAIL until retry loop exists.

- [ ] **Step 2: Implement fix/retry orchestration**

In `test_pilot_phase.js`, implement:
- `collectAppBugFailures(passResult)`
- `dispatchFixBatch(failures)`
- `ensureCleanWorktreeAfterFix()`
- `reconcileCommittedMutations()`
- retry decision calls to `test_pilot_retry_cli.py`
- budget checks before each browser pass and before each fix-batch dispatch

Record fix-batch history, commit SHA(s), rerun scope, scrubbed failure summaries, and the current
head that browser evidence covers in status/results.

- [ ] **Step 3: Run retry smokes**

Run:
`node plugins/superheroes/lib/tests/showrunner_test_pilot_phase_smoke.js`

Expected: PASS for fix/retry cases.

- [ ] **Step 4: Commit**

```bash
git add plugins/superheroes/lib/test_pilot_phase.js plugins/superheroes/lib/tests/showrunner_test_pilot_phase_smoke.js
git commit -m "feat(superheroes): add test-pilot fix retry loop"
```

---

### Task 9: Targetable review-code stabilization

**Files:**
- Modify: `plugins/superheroes/lib/showrunner.js`
- Modify: `plugins/superheroes/lib/review_panel_shell.js`
- Modify: `plugins/superheroes/lib/prov_entry.py`
- Modify: `plugins/superheroes/lib/test_pilot_phase.js`
- Modify: `plugins/superheroes/lib/tests/showrunner_reviewcode_smoke.js`
- Modify: `plugins/superheroes/lib/tests/showrunner_reviewcode_loop_smoke.js`
- Modify: `plugins/superheroes/lib/tests/showrunner_test_pilot_phase_smoke.js`
- Modify: `plugins/superheroes/lib/tests/test_ship_gate.py`

**Interfaces:**
- Produces: `reviewCodePhase(workItem, opts)` where opts may include explicit worktree, branch/head,
  runDir suffix, and stabilization purpose.
- Produces: fresh runDir per stabilization cycle/head.
- Produces: review/fixer/verify/provenance leaves bound to explicit build worktree and expected head.
- Produces: `review.covers` restamp to the final tested head only on pure `clean`.

- [ ] **Step 1: Write failing targetability tests**

Cover:
- second review-code call for test-pilot stabilization never reuses
  `/tmp/showrunner-${workItem}-review-code`.
- reviewer/fixer/verify leaves receive explicit build worktree and expected head.
- a worktree/head mismatch parks.
- `prov_entry --step review` upserts `review.covers` to final tested head on pure clean.
- `clean-with-skips` records no covers stamp and readiness parks.
- review-code-induced commits force browser revalidation.
- stabilization cycles park after two cycles.
- review-code-induced fixes do not consume the three browser-fix-batch cap; they consume only the
  two-cycle `reviewStabilizationCycle` cap.
- the combined loop is finite: at most three browser fix batches, at most two review-code
  stabilization cycles, and the existing #104 panel cap inside each review-code call.

Run:
`node plugins/superheroes/lib/tests/showrunner_reviewcode_smoke.js`
`node plugins/superheroes/lib/tests/showrunner_test_pilot_phase_smoke.js`
`python3 -m pytest plugins/superheroes/lib/tests/test_ship_gate.py -q`

Expected: FAIL until targetability and stabilization support exist.

- [ ] **Step 2: Extend review-code in place**

Update the merged review-code implementation, not a copy:
- `reviewCodePhase(workItem, opts = {})`
- `runDir` defaults to current behavior but accepts a caller-provided test-pilot runDir key.
- review leaves include explicit worktree/head context.
- verify command runs in/against the expected worktree/head.
- provenance write resolves the intended build branch/head and upserts covers idempotently.

- [ ] **Step 3: Add stabilization to `test_pilot_phase.js`**

After browser passes and before ready status:
- if fix batches or review-code fixes changed the branch, invoke targetable review-code.
- cap `reviewStabilizationCycle` at 2.
- keep `browserFixBatch` and `reviewStabilizationCycle` as separate counters in status.
- if review-code fixes mutate the branch, rederive/revalidate plan and browser results for the new
  head before another stabilization cycle.
- if post-review-code browser revalidation finds app-bug failures, route them through the Task 8
  retry path: dispatch another browser fix batch only when `browserFixBatch < 3`, apply the same
  no-progress predicate, park on cap/no-progress, and continue stabilization only after the new head
  is browser-passing.
- require `review.covers == browser-tested-head == remote-PR-head`.

- [ ] **Step 4: Run review-code stabilization tests**

Run:
`node plugins/superheroes/lib/tests/showrunner_reviewcode_smoke.js`
`node plugins/superheroes/lib/tests/showrunner_reviewcode_loop_smoke.js`
`node plugins/superheroes/lib/tests/showrunner_test_pilot_phase_smoke.js`
`python3 -m pytest plugins/superheroes/lib/tests/test_ship_gate.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add plugins/superheroes/lib/showrunner.js plugins/superheroes/lib/review_panel_shell.js plugins/superheroes/lib/prov_entry.py plugins/superheroes/lib/test_pilot_phase.js plugins/superheroes/lib/tests/showrunner_reviewcode_smoke.js plugins/superheroes/lib/tests/showrunner_reviewcode_loop_smoke.js plugins/superheroes/lib/tests/showrunner_test_pilot_phase_smoke.js plugins/superheroes/lib/tests/test_ship_gate.py
git commit -m "feat(superheroes): target review-code for test-pilot stabilization"
```

---

### Task 10: Remote PR-head reconciliation and ready guard completion

**Files:**
- Modify: `plugins/superheroes/lib/test_pilot_phase.js`
- Modify: `plugins/superheroes/lib/pr_entry.py`
- Modify: `plugins/superheroes/lib/tests/showrunner_test_pilot_phase_smoke.js`
- Modify: `plugins/superheroes/lib/tests/test_test_pilot_publish.py`
- Modify: `plugins/superheroes/lib/tests/test_test_pilot_status.py`
- Modify: `plugins/superheroes/lib/tests/test_pr_phase.py`

**Interfaces:**
- Consumes: `test_pilot_publish.py`, `test_pilot_status.py`, and `pr_entry.py`.
- Produces: remote PR head equals the locally tested/reviewed head before ready.
- Produces: `mark-ready` guard rejects stale, missing, unreviewed, unverified, browser-untested,
  unpublished, skipped, or low-confidence status.

- [ ] **Step 1: Write failing final-readiness smokes/tests**

Cover:
- publish renews/fences, non-force pushes, reads PR head, and requires equality.
- no safe tracking target, lost lease, push failure, unreadable PR head, and mismatch park.
- `mark-ready` refuses missing/stale/unreviewed/unverified/browser-untested/unpublished status.
- not-applicable-ready status proceeds without browser artifacts.
- applicable-ready status proceeds only with plan/results artifacts and fresh baseline verified.
- final baseline restore happens after review-code stabilization and final browser revalidation.
- if review-code mutated the branch after any earlier baseline restore, the old baseline proof is
  invalidated and `test_pilot_seed_cli.py restore-baseline` reruns for the final head.

Run:
`node plugins/superheroes/lib/tests/showrunner_test_pilot_phase_smoke.js`
`python3 -m pytest plugins/superheroes/lib/tests/test_test_pilot_publish.py plugins/superheroes/lib/tests/test_test_pilot_status.py plugins/superheroes/lib/tests/test_pr_phase.py -q`

Expected: FAIL until final status/publish wiring is complete.

- [ ] **Step 2: Wire publish and final status into the phase**

In `test_pilot_phase.js`, after review-code stabilization and final browser revalidation:
- restore the fresh seed baseline through `test_pilot_seed_cli.py restore-baseline`,
- write the baseline verdict against the final branch head only,
- render and ensure the final results artifact through `test_pilot_artifacts_cli.py ensure` after
  final browser revalidation and baseline restore, preserving fallback paths when either PR comment
  post fails,
- call `test_pilot_publish` before writing ready status,
- write final status with artifact paths, final branch head, pass verdict, fix-batch history,
  baseline verdict, review coverage head, verify-pass head, and PR head,
- ensure `mark-ready` can assert the exact head through `test_pilot_status_cli.py`.

- [ ] **Step 3: Run final-readiness tests**

Run:
`node plugins/superheroes/lib/tests/showrunner_test_pilot_phase_smoke.js`
`python3 -m pytest plugins/superheroes/lib/tests/test_test_pilot_publish.py plugins/superheroes/lib/tests/test_test_pilot_status.py plugins/superheroes/lib/tests/test_pr_phase.py -q`

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add plugins/superheroes/lib/test_pilot_phase.js plugins/superheroes/lib/pr_entry.py plugins/superheroes/lib/tests/showrunner_test_pilot_phase_smoke.js plugins/superheroes/lib/tests/test_test_pilot_publish.py plugins/superheroes/lib/tests/test_test_pilot_status.py plugins/superheroes/lib/tests/test_pr_phase.py
git commit -m "feat(superheroes): reconcile test-pilot readiness before mark-ready"
```

---

### Task 11: Documentation and full local verification

**Files:**
- Modify: `README.md`
- Modify: `CONVENTIONS.md`
- Modify: `CLAUDE.md`
- Modify: `.github/workflows/ci.yml`
- Modify: `.github/scripts/tests/` if a CI/local verification test needs updating.

**Interfaces:**
- Produces: user-facing docs that describe the showrunner/test-pilot ownership boundary, phase order,
  targetable review-code rerun, status sidecar, and final ready guard.
- Produces: CI/local verification command that includes enforced Node smoke coverage.

- [ ] **Step 1: Write failing doc/verification checks**

Run existing validators before doc updates:

`python3 .github/scripts/validate_marketplace.py`
`python3 .github/scripts/validate_hosts.py`
`python3 .github/scripts/validate_skills.py`
`python3 -m pytest .github/scripts/tests/ plugins/superheroes/lib/tests/ plugins/superheroes/eval/tests/ eval/lib/tests/ -q`

Expected: any new smoke wrapper or docs expectation added earlier should fail until docs/local verify
references are complete.

- [ ] **Step 2: Update docs**

Document:
- showrunner phase order now includes `test-pilot` before `mark-ready`,
- browser verification is resolved inside showrunner for applicable branches,
- not-applicable is a first-class success state with rationale,
- applicable branches require plan/results artifacts, browser evidence, fresh seed baseline, review-code
  coverage after test-pilot fixes, and remote PR-head reconciliation,
- standalone test-pilot skills remain valid outside the showrunner workflow,
- local verification includes the Node smoke wrapper or explicit Node smoke command.

- [ ] **Step 3: Run full local verification**

Run:
`python3 .github/scripts/validate_marketplace.py`
`python3 .github/scripts/validate_hosts.py`
`python3 .github/scripts/validate_skills.py`
`python3 -m pytest .github/scripts/tests/ plugins/superheroes/lib/tests/ plugins/superheroes/eval/tests/ eval/lib/tests/ -q`

Expected: all commands PASS.

- [ ] **Step 4: Commit**

```bash
git add README.md CONVENTIONS.md CLAUDE.md .github/workflows/ci.yml .github/scripts/tests plugins/superheroes/lib/tests
git commit -m "docs(superheroes): document native test-pilot workflow phase"
```
