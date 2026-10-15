---
superheroes: doc
schemaVersion: 1
docType: plan
workItem: workhorse-build-phase-native-sdd-orchestration-cf9f53
issue: null
size: large
status: approved
gates: {review: passed}
producedBy: "the-architect@0.2.0"
created: "2026-06-25"
updated: "2026-06-25"
---
# Workhorse build phase — native SDD orchestration — Plan

## Overview

The showrunner's build phase is a thin stub today: `buildPhase(workItem)` in
`lib/showrunner.js` sets up a managed worktree/branch, dispatches **one** throwaway
`agent()` change, records provenance, and returns. This plan replaces that stub with the
real build: a deterministic, resumable per-task loop that implements every task in the
approved tasks doc **test-first**, reviews each task with a bespoke two-verdict reviewer
plus a bounded fix loop, then runs **one** whole-branch final review through the merged
#104 shared loop, records build provenance once over the handed-off commit, and hands off
a reviewed branch — never creating the PR, merging, or force-pushing.

The shape follows the established showrunner-era contract (CONVENTIONS §10): **all
orchestration lives in the Workflow script**, every judgement lives in a **pure, fail-closed
Python decider** with unit tests, and **durability is the substrate's** — on every entry the
phase reconciles its progress from what is actually committed on the branch plus its durable
review records, and skips completed work. We reuse the existing substrate wholesale
(`buildtree`, `control_plane`, `checkpoint`, `journal`, `ship_gate`, `ref_lock`, `recover`,
`model_tier`, and the #104 `reviewPanel` + its deciders). The genuinely new surface is small:
a tasks-doc **enumerator**, a per-task **review decider**, a per-task **progress reconciler**,
a **Minor-findings roll-up**, and the JS control flow that sequences them. This is a
re-composition of proven parts, not a new subsystem — and it introduces **no new skill**
(so no skill eval-gate artifacts), matching the #21 spine and #104 loop precedents.

## Goals & non-goals

**Goals (from the spec):**

- Execute every task in an approved tasks doc test-first, on a dedicated build worktree/branch,
  producing committed changes (FR-1, FR-2, FR-3).
- Per-task: one build worker, then a separate two-verdict reviewer (spec-compliance +
  code-quality) with a bounded Critical/Important fix-and-re-review loop; Minor findings carry
  forward (FR-4–FR-7), with "cannot verify from the diff" never passed unexamined (UFR-5).
- After the last task, exactly one whole-branch final review **through the shared #104 loop**,
  ordered before the downstream specialist panel (#89), reporting complete only on a fully
  clean result (FR-8, #59).
- Record build provenance **once** over the exact handed-off commit X (FR-9); hand off only
  build outputs (FR-10); label the phase **"workhorse"** wherever surfaced (FR-12).
- Honest, recoverable progress: durable per-task + final-review records, reconcile-and-resume,
  fail-closed parking on every blocked/uncertain/unwritable state (FR-11, UFR-1–UFR-12, the
  Auditability/Resumability/Honesty NFRs).
- Cost discipline: the whole-branch reviewer at the most-capable model tier and its fixer at
  the code-fixer tier; the per-task build worker stays on SDD's own heuristic (not the
  model-tier knob).

**Non-goals (deliberately excluded here):**

- Creating the PR, running the specialist #89 panel, behavioral testing (#90), CI/freshness/
  ship gating, merging, force-pushing — later phases / the owner.
- Retiring the `/workhorse` command — it stays the working producer; this plan delivers the
  showrunner's native phase, not the command's removal.
- An owner-facing model-tier knob for build workers; graceful in-run context/usage
  self-management (#23/#24) — a wall parks and resumes.
- Re-deriving or re-authoring the tasks doc — this phase **consumes** an approved one.
- Changing the substrate's contracts (`buildtree`, `ship_gate`, `recover`, `ref_lock`, the
  #104 deciders) — they carry over unchanged.

## Architecture

The build phase is one node in the showrunner's `PHASES` pipeline. The spine
(`showrunner.js` → `runPhases`) already calls the phase through an injectable seam
(`deps.build || buildPhase`). We **extract the workhorse phase into its own module**
(`lib/build_phase.js`) that the spine requires and calls through that seam, keeping the spine
thin and the heaviest phase independently testable (node smokes target it directly).

Within `build_phase.js` the control flow is:

1. **Setup (reuse).** Reconcile/resume entry; resolve the content-addressed branch and
   worktree via the existing `build_entry.py` → `buildtree.reclaim_or_create` path. Refuse and
   park on an un-`passed`/unreadable tasks gate (UFR-1) or an occupied/dirty target (UFR-2).
2. **Enumerate tasks.** A new pure `task_list.py` parses the approved tasks doc into an
   ordered list of executable tasks; zero tasks → finish-without-building (UFR-8).
3. **Reconcile per-task progress.** A new pure `build_progress.py` maps committed commits on
   the branch (each implementing commit carries a `Task-Id` trailer) plus the durable per-task
   review records against the task list, deciding the resume point: the first task not yet
   *complete* (committed **and** reviewed-clean-and-recorded). Distinguishes committed-but-
   unreviewed (take up at review) from uncommitted leftover (reset only the uncommitted work)
   — UFR-7, UFR-12 — and "all tasks complete" from "build complete" (FR-11).
4. **Per-task loop** (script control flow), for each not-yet-complete task:
   - **Build worker** (one leaf `agent()`, SDD's model heuristic): write the task's test(s),
     observe them fail, implement, observe them pass; commit with the `Task-Id` trailer (every
     commit for the task — including fix-loop commits — carries it). Record the test-first
     evidence durably (FR-3). Bounded recovery on a stuck worker (UFR-3) is decided by a new pure
     `worker_recovery.py` (attempt-count → retry-with-context → escalate → park at the fixed
     maximum, or park immediately on a "plan is wrong" signal), a sibling of
     `recover.rearm_action`.
   - **Per-task reviewer** (one leaf `agent()`): returns two verdicts. A new pure
     `task_review.py` validates both verdicts present (FR-5), partitions findings into blocking
     (Critical/Important, the shared `BLOCKING` set) vs Minor (recorded + carried forward,
     FR-7), surfaces "cannot verify from diff" items (UFR-5), and drives continuation via the
     reused `loop_state` + `circuit_breaker` primitives. Blocking → fix leaf → re-review,
     bounded by the fixed maximum, then park (FR-6, UFR-4). Mark the task complete (recorded)
     only on a clean two-verdict review.
5. **Whole-branch final review** (reuse #104).  After the last task, dispatch **one**
   `reviewPanel(...)` configured as a single generalist reviewer, code leg, no synthesis (see
   Components), with the project verify command as its code-leg gate. Park on
   `halted`/`cannot-certify`/`clean-with-skips` (UFR-4); report complete only on a fully clean
   result.
6. **Provenance + handoff.** Once the final review records a clean result, record build
   provenance over the current HEAD = commit X via the idempotent `ship_gate.write_build`
   (read-modify-write; FR-9). Provenance-present is the marker for "build complete," so an
   interruption *between* the clean-final-review record and the provenance write is recoverable:
   on relaunch, `build_progress` sees the clean record with provenance absent and **(re)writes
   provenance idempotently without re-reviewing** — provenance is the single final idempotent
   step, not re-anchored thereafter (a *garbled* provenance, by contrast, parks fail-closed per
   UFR-6 — it is not treated as absent). Hand off the reviewed branch, the provenance record, and the
   Minor-findings roll-up (FR-10). Return the phase result; the spine advances to `review-code`
   (#89), which by phase order runs strictly after this review (FR-8 / #59 ordering).

Every step appends a durable `journal` record (gate / confidence / assumptions); a material
assumption, low confidence, or any failed durable write parks rather than proceeds (§10.3;
UFR-6). Single-run exclusion (UFR-10) builds on the entry `ref_lock` startup + work-item lease
already taken by `recover_entry.py`, but the *mid-build fence is new wiring this plan owns* (the
spec delegates the exclusion mechanism to the plan). The lease `generation` acquired at **this
run's** entry is threaded across the leaf boundary: today `recover_entry.py` discards it (`_gen`),
so it will **emit** the acquired generation, `build_entry.py` will **write** it into
`checkpoint.lockGeneration` on **every entry** — mint *or* reuse — so a legitimate resume that
re-acquires the lease (its predecessor's lease having expired) threads *this* run's generation,
overwriting any stale prior value, and fences against the live lease rather than parking on a
stale generation; `build_phase.js` then **reads** it. Then — **at each branch-mutating boundary**
(immediately before every commit/reset),
matching the proven `/workhorse` precedent, which renews+fences per boundary rather than on a
wall-clock timer the sequential Workflow runtime has no way to fire — `build_phase.js` **`renew`s
the lease, then `fence_ok`-checks as the last gate before the write**, parking on a lost generation
rather than corrupting the branch. (A single leaf that itself outlasts the lease TTL is the same
bounded limitation `/workhorse` carries; the next boundary's `fence_ok` still catches a steal
before any further write.) The `ref_lock` primitives are reused unchanged; the
capture/thread/boundary-renew/fence is the new part.

## Components & interfaces

**New (pure Python deciders — fail-closed, unit-tested; each decider the JS control flow drives
gets the standard `*_cli.py` thin wrapper emitting schema-validated JSON, matching
`phase_step_cli.py`/`journal_entry.py` — here `task_list`, `task_review`, `build_progress`,
`worker_recovery`, and `minor_rollup` are JS-invoked and so each gets a `*_cli.py` bridge):**

- **`task_list.py`** — `parse(tasks_body) -> [{id, title, ...}]`. Enumerates executable tasks
  (checkbox steps) from the approved tasks doc body in document order. Contract: deterministic;
  an empty/zero-task doc returns `[]` (drives UFR-8); malformed input fails closed (raises /
  empty → the caller parks, never invents a task). Reuses `docload.load_doc` for the body.
- **`task_review.py`** — `decide(verdicts, findings, round, max_rounds, history) ->
  {action, blocking, minors, cannot_verify, reason}`. Inputs: the reviewer's two verdicts and
  its findings for this round. Validates **both** verdicts present (else `re-request`, FR-5);
  partitions findings using the shared `circuit_breaker.BLOCKING` set into blocking vs Minor
  (FR-7 carry-forward); flags "cannot verify from diff" items (UFR-5); computes continuation by
  calling `loop_state.decide(...)` and `circuit_breaker.check_circuit_breaker(...)` (reused
  unchanged). Output actions mirror `loop_state`: `review` (blocking fixed → mandatory
  re-review), `complete` (clean), `park` (cap/halt/`exit_skipped`-equivalent → UFR-4). **Never
  routed through `reviewPanel`** (Constraint).
- **`build_progress.py`** — `reconcile(task_list, committed, review_records, worktree_state)
  -> {resume_at, committed_unreviewed, uncommitted_leftover, all_tasks_complete,
  build_complete, reason}`. The per-task analog of `recover.reconcile`, at task granularity:
  reality (commits + records) wins. It maps commits→tasks by the `Task-Id` trailer (a task = the
  *set* of commits carrying its id, so multi-commit tasks from the fix loop reconcile correctly),
  scoped to commits **above the branch's merge-base with the base branch** (pre-existing base
  history is never read as trailer-less); **validates every such on-branch `Task-Id` against the
  current enumeration and parks fail-closed on a trailer-less or unmappable commit** (never
  silently skip or absorb it); treats a clean-final-review record with provenance **absent** as
  "(re)write provenance, do not re-review" (the FR-9 resume window), while a **garbled/unreadable**
  provenance (`ship_gate.ProvenanceError`) parks fail-closed (UFR-6) rather than overwrite. Pure
  decision; the JS supplies the git/world reads.
- **`worker_recovery.py`** — `decide(attempt, signal, max_attempts) -> {action, reason}`, action
  ∈ retry-with-context / escalate / park. The bounded-recovery judgement for a stuck build worker
  (UFR-3), a sibling of `recover.rearm_action`; unit-tested at the boundary the way
  `test_recover.py` pins `rearm_action` (proceed/retry/park).
- **`minor_rollup.py`** — append-and-read of the carried-forward Minor findings
  (`minor-findings.json` in the issue dir), supplied as context to the final review (FR-7 →
  FR-8). Idempotent append; fail-closed read (missing → empty).
- A minimal **`recordDeferred`** writer for the final review's loop (append deferred
  identities to `deferred-set.json`). #87 supplies its own — `record_deferred.py` is a sibling
  #89 artifact **not on `main`**, so this phase does not depend on it.

**New (JS orchestration):**

- **`lib/build_phase.js`** — exports `buildPhase(workItem)` (returns the spine's
  `{confidence, assumptions}` contract) plus the per-task and final-review helpers. Supplies the
  #104 caller leaf wrappers for the final review the way the existing consumer does
  (showrunner.js:13-15): the reviewer + deferred leaves are injected as **`global.reviewerAgent`
  and `global.recordDeferred`** before the `reviewPanel(...)` call (they are *not* parameters),
  while `fixStep` (the code-fixer leaf) *is* a `reviewPanel` parameter. The build worker leaf
  passes **no** model-tier (SDD's heuristic). The spine wires the phase through the existing
  `deps.build` seam.

**Reused unchanged (substrate + #104):** `build_entry.py`/`buildtree.py` (worktree/branch
lifecycle, reclaim/create/reap, content-addressed branch); `control_plane.py` +
`checkpoint.py` + `journal.py`/`journal_entry.py` (store, cursor, append-only audit);
`ship_gate.write_build`/`read_provenance` (provenance, idempotent read-modify-write);
`ref_lock` (lease primitives `acquire`/`renew`/`fence_ok` reused unchanged — though the
generation capture/persist + mid-build renew/fence cadence is new wiring, see Key decisions);
`recover.reconcile` (whole-run entry, already in the spine); `model_tier_resolve.py` +
`model_tier_overrides.py` (tier knob);
`review_panel_shell.js` `reviewPanel(...)` with `panel_tally.py` / `verify_gate.py` deciders
(`loop_synthesis.py` is bypassed — single reviewer, no synthesis).

**The whole-branch final review configuration** (the #104 contract, verbatim to the spec).
`reviewPanel(...)` **parameters**: `reviewerSet` = one generalist reviewer; `legKind =
{panel:false, code:true}` (no synthesis; verify gate runs); `maxRounds` = the per-task review's
fixed maximum; `verifyCommand` = the project verify command (resolved from the calibration
profile's `verify-command` field — absent ⇒ `verify_gate` "skipped", accepted because #89 re-runs
verify, the intentional double-run); `fixStep` = the code-fixer leaf. The reviewer and deferred
leaves are injected as **`global.reviewerAgent` / `global.recordDeferred`** before the call
(showrunner.js:13-15), not as parameters. **Model tiers:** `fixStep` runs at
`resolve_model("fixer", overrides, context="code")` → sonnet; the reviewer leaf runs at
`resolve_model("reviewer-deep", overrides)` → opus — the most-capable reviewer tier, resolved
through the canonical knob (so a profile override still wins) and injected on the leaf, since
there is no dedicated generalist role. Parks on `halted`/`cannot-certify`/`clean-with-skips`.

## Data flow & data model

Inputs: the approved tasks doc (read-only; gate + content via `definition_doc`/`docload`).
Working data lives in two places, both existing locations:

- **The build branch** (content-addressed, `superheroes/<work-item>-<hash>`): the *truth* for
  "implemented." **Every** commit a task produces — its implementing commit and any fix-loop
  commits — carries a **`Task-Id: <id>` trailer**, enforced at *write* time (the commit step adds
  it and a missing trailer is caught immediately, not only at resume). `build_progress` maps the
  *set* of trailered commits **above the branch's merge-base with the base branch** to each task on
  resume; a trailer-less or unmappable commit in that range parks fail-closed (never absorbed). No
  new git data model — just a commit trailer convention.
- **The per-issue control-plane store** (`~/.claude/workhorse/.../issues/<work-item>/`): new
  small JSON artifacts beside the existing `checkpoint.json`/`events.jsonl`/`provenance.json`
  — a per-task review-state record (task complete: both verdicts, clean, recorded), the
  `minor-findings.json` roll-up, the final-review `run-dir` (round-`N`/ layout owned by
  `panel_tally`), and `deferred-set.json`. All are append-or-replace, atomic-write,
  fail-closed on read (the `journal`/`control_plane` conventions).

Provenance (`provenance.json`) is written at build-complete via
`ship_gate.write_build(path, engine=…, head=X)` (path-positional, `engine`/`head` keyword-only) —
additive (read-modify-write, never clobber) and **idempotent**, so a resume that finds a
clean-final-review record but no provenance simply (re)writes it; it is not re-anchored by any
later #89 fix (FR-9; the scope boundary in the spec's Glossary). Forward/backward compatibility: all new records carry a
`schemaVersion` and fail closed on an unknown version, matching `checkpoint`/`buildtree`
records — an old run reading a newer record parks rather than mis-reads.

## How the requirements are met

- **FR-1 / FR-2** — setup reuses `build_entry`/`buildtree` (content-addressed worktree+branch);
  the per-task loop commits all N tasks; `task_list` guarantees every enumerated task is
  attempted.
- **FR-3** — the build-worker leaf is dispatched test-first; the script records durable
  per-task TDD evidence (test written + observed failing, then passing) in the journal/build
  record; tests pass when the change lands.
- **FR-4 / FR-5** — a separate reviewer leaf runs after each worker, before any later task;
  `task_review` treats the task reviewed only when **both** verdicts are present (else
  re-request).
- **FR-6 / FR-7** — `task_review` + `loop_state` + `circuit_breaker`: Critical/Important →
  bounded fix-and-re-review, then park (UFR-4); Minor-only → record + carry forward via
  `minor_rollup`, task complete.
- **FR-8 (+#59)** — exactly one `reviewPanel(...)` whole-branch review (single generalist, code
  leg, no synthesis, round bound = per-task max), fed the Minor roll-up, parking on non-clean;
  by phase order it completes before `review-code` (#89). Verify gate runs (acceptance "verify
  gate"); the double-run with #89 is intentional and not suppressed.
- **FR-9** — `ship_gate.write_build` (idempotent) over HEAD = X after all fixes;
  provenance-present marks "build complete," and a resume in the clean-recorded-but-provenance-
  absent window (re)writes it without re-review; not re-anchored thereafter.
- **FR-10** — the phase returns build outputs only; it makes no PR/panel/merge/force-push (none
  of those calls exist in `build_phase.js`).
- **FR-11 / UFR-7 / UFR-12** — `build_progress` records each task complete and the final-review
  entry/clean state; reconciles committed-vs-recorded by the `Task-Id` trailer (multi-commit tasks
  included), resumes at the first incomplete task, keeps committed work, resets only uncommitted
  leftovers, and parks on a trailer-less/unmappable commit; resumes a mid-final-review interruption
  (and the clean-recorded→provenance-absent window) rather than treating "all tasks complete" as
  "build complete."
- **FR-12** — the phase identifies itself as **"workhorse"** wherever surfaced (see Key
  decisions: the `PHASES` label is renamed `build` → `workhorse`).
- **UFR-1 / UFR-2 / UFR-8** — un-`passed`/unreadable gate, occupied/dirty target, and
  zero-task doc each park or finish-without-building, creating nothing spurious (reuse
  `recover`/`buildtree` outcomes + `task_list`).
- **UFR-3** — bounded worker recovery decided by the pure `worker_recovery.py` (more context →
  escalate → park at the fixed maximum or on a "plan is wrong" signal), unit-tested at the boundary.
- **UFR-4** — every review (per-task and whole-branch) parks on cap-reached or a deliberately-
  left blocking finding (`clean-with-skips`/`exit_skipped`), never reporting clean.
- **UFR-5** — `task_review` surfaces "cannot verify from diff" items: confirm met, send back, or
  park — never silently complete.
- **UFR-6** — any failed durable write parks fail-closed (the `journal.DurableWriteError` →
  park pattern, reused).
- **UFR-9** — a context/usage wall parks at the last completed task; reconcile resumes at the
  next unbuilt task (graceful in-run self-management is out of scope).
- **UFR-10** — entry `ref_lock` startup + work-item lease prevents a second concurrent build; the
  new generation capture/thread + `renew`-then-`fence_ok` at each branch-mutating boundary (matching
  the `/workhorse` precedent) prevents a stale holder corrupting the branch (the mechanism the spec
  delegates to the plan).
- **UFR-11** — the branch is content-addressed; a tasks-doc **content** edit changes the hash →
  branch mismatch → `recover`/`build_progress` park (caught even if the gate still reads
  `passed`; withdrawn approval parks too).
- **NFRs** — Auditability: every step appends a structured record, assumption/low-confidence
  parks. Resumability: reconcile-from-reality lands on the next unbuilt task with no duplicate
  commits. Honesty: no "built/clean" claim without committed work + a passed review + a
  successful record. Cost discipline: the run record names the reviewer's most-capable tier and
  the fixer's code-fixer tier, while the build worker's model is recorded as SDD's choice.

## Key decisions & alternatives

- **Decision:** Source of truth for per-task progress + resume. · **Options weighed:**
  (a) **reality-wins** — committed commits on the branch are the truth for "implemented" (every
  commit a task makes — implementing and fix-loop — carries a `Task-Id` trailer, so a task = the
  set of its trailered commits, and a trailer-less/unmappable commit parks fail-closed), a thin
  durable per-task record carries "reviewed-clean", and resume reconciles both against the task
  list; (b) an **explicit per-task ledger** (`build-progress.json`)
  recording each task's state, read directly on resume. · **Choice + why:** (a). The spec
  mandates reconciling against "what is actually committed on the build branch" (UFR-7) and
  distinguishing committed-vs-uncommitted (UFR-12); §10.2/§4.7 make reality the authority. A
  ledger can drift from reality and would need this reconcile anyway, so it is redundant state.
  · **Accepted downside:** resume reads git state (more reconcile code) and depends on the
  `Task-Id` trailer convention. · **Reversible?** one-way-ish (resume semantics) — de-risked by
  mirroring the proven `recover.reconcile`. · **Mode:** PROCEED (spec-dictated, no owner
  trade-off). · **Escalated?** no.
- **Decision:** Where the workhorse orchestration lives. · **Options weighed:** (a) a dedicated
  `lib/build_phase.js` the spine delegates to via the existing `deps.build` seam; (b) inline the
  per-task loop + final review directly in `showrunner.js`'s `buildPhase`. · **Choice + why:**
  (a). The heaviest phase deserves isolation for direct node-smoke testing and to keep the spine
  thin (deep module, low coupling); the seam already exists. · **Accepted downside:** one extra
  module + a `require`. · **Reversible?** two-way (internal refactor). · **Mode:** PROCEED. ·
  **Escalated?** no.
- **Decision:** Satisfy FR-12 ("workhorse" label) by renaming the `PHASES` entry `build` →
  `workhorse`. · **Options weighed:** (a) rename the phase string (every surface — phase_record,
  parked outcome, readout — reads "workhorse" for free); (b) keep `build` internally and add a
  separate display label mapped at each surface. · **Choice + why:** (a). `lastGoodStep` is an
  index (unchanged by a string rename); only the `phase === 'build'` dispatch branch and the
  smokes reference the literal, both updated locally — least-astonishing, single source. ·
  **Accepted downside:** a one-time touch of the literal in the dispatch + smokes. · **Reversible?**
  two-way. · **Mode:** PROCEED. · **Escalated?** no.
- **Decision:** Per-task / final-review fixed-maximum fix-and-re-review attempts = **3**. ·
  **Options weighed:** 3 (matches review-code and the #104 build's bound) vs a higher bound (more
  autonomous fixing before parking). · **Choice + why:** 3 — consistent with the band's existing
  convergence bound; the spec fixes only that it is finite and that reaching it parks; the
  whole-branch round bound is tied equal to the per-task max by the spec. · **Accepted downside:**
  a genuinely-hard task that would converge in 4 parks at 3 (surfaced to the owner, not lost). ·
  **Reversible?** two-way (a single constant). · **Mode:** **NOTIFY** — **Reverse path:** change
  the constant before the build runs; **Expiry:** until build start. · **Escalated?** no.
- **Decision:** Whole-branch reviewer model resolved via `resolve_model("reviewer-deep", overrides)`
  → opus (the most-capable reviewer tier, profile-overridable) and injected on the reviewer leaf;
  fixer = `resolve_model("fixer", …, context="code")` → sonnet; build worker = SDD's heuristic (no
  model-tier knob). · **Options weighed:** (a) resolve the reviewer tier through the canonical
  `reviewer-deep` role (single source, honors profile overrides) then inject on the leaf; (b) pin a
  literal model on the leaf. · **Choice + why:** (a) — keeps the tier a single source of truth and
  overridable, while still injecting on the leaf as the spec directs (no dedicated generalist role
  added). · **Accepted downside:** the reviewer tier rides the `reviewer-deep` role's meaning
  ("security/architecture review") — acceptable, it *is* the most-capable reviewer tier. ·
  **Reversible?** two-way (profile overrides). · **Mode:** PROCEED. · **Escalated?** no.
- **Decision:** Recover the lease `generation` for the mid-build fence (UFR-10) by capturing it at
  entry and threading it through the checkpoint. · **Options weighed:** (a) `recover_entry.py` stops
  discarding the acquired generation and **emits** it, `build_entry.py` **writes** it into
  `checkpoint.lockGeneration` when it mints the checkpoint, and `build_phase.js` **reads** it; (b)
  `build_phase.js` re-reads the live lease (`ref_lock.read_lease`) each time to get a generation. ·
  **Choice + why:** (a). The fence must compare against the generation captured **at entry** — a
  fresh `read_lease` (b) would always self-match the *current* holder and so could never detect a
  steal, defeating the fence. (a) threads the entry generation durably through the existing
  `checkpoint.lockGeneration` slot. This makes the reuse-vs-touch boundary honest: a small *named*
  cross-leaf touch of `recover_entry.py` (emit) + `build_entry.py` (write), not "reused unchanged."
  · **Accepted downside:** a small substrate change across two leaves, and the generation must be
  (re)written **on every entry** (mint or reuse) so a resume threads this run's freshly-acquired
  generation rather than a stale one. · **Reversible?** two-way. · **Mode:** PROCEED (the spec
  delegates the exclusion mechanism to the plan). · **Escalated?** no.
- **Decision:** No new skill ⇒ no skill eval-gate artifacts. · **Options weighed:** package as a
  skill (would need fixture/activation-result/registry/strict-YAML) vs script+lib only. · **Choice
  + why:** script+lib only, matching the #21 spine and #104 loop precedents (both lib+script, zero
  new skill). · **Accepted downside:** none — the eval is composition proof (node smokes) + unit
  tests (the pure deciders), both CI-gated. · **Reversible?** two-way. · **Mode:** PROCEED. ·
  **Escalated?** no.

## Cross-cutting concerns

- **Security & privacy:** N/A — because the build phase makes local commits only; no PII, no new
  trust boundary, no network/auth surface. GitHub access, PR, and merge belong to gated later
  phases (spec Coverage: Access = N-A).
- **Observability:** every step appends a structured `journal` event (gate / confidence /
  assumptions / phase = "workhorse") to `events.jsonl`, plus per-task TDD evidence, the Minor
  roll-up, the final-review `round-N/` verdicts, and write-once provenance. At 2am the operator
  reads the parked readout + `events.jsonl` to see exactly which task, which review round, and
  why it parked. A park always names the real cause (Honesty NFR).
- **Reliability & failure modes:** critical dependencies — the control-plane store, the build
  branch, and a successful durable write — each fail **closed** (park), never a false "clean."
  Non-critical degradation: an absent project verify command degrades the final review's code leg
  to `skipped` (accepted; #89 re-runs verify). A stuck worker / unconverging review degrades to a
  bounded retry then a park, not an infinite loop (`circuit_breaker`, the fixed maximum).

## Rollout & migration

N/A — because this is an internal infrastructure change with no user-visible surface, no API, and
no persisted data migration. It **replaces** the throwaway-change stub in `buildPhase`; the
`/workhorse` command is untouched and remains the live producer (spec Out-of-scope). There is no
flag/canary: the showrunner that consumes this phase is not yet wired to run spec→PR live (a later
work-item), so the change lands behind that not-yet-live path and is exercised by tests + the
spec's live end-to-end acceptance build. New store records are additive and version-guarded; an
interrupted in-flight run reconciles cleanly because reality (commits) wins.

## Risks & mitigations

- **Pre-mortem — silent false "complete."** A worker fakes a passing test, or a record write
  fails unnoticed, and the phase reports a clean build it didn't achieve. *Mitigation:* TDD
  evidence is recorded by the **script** (observe-fail-then-pass), not self-attested; every
  durable write is checked and a failure parks (UFR-6); the final review's verify gate independently
  runs the project verify command; the clean-final-review record plus the *idempotent* provenance
  write close the interruption window (a resume that finds the clean record but no provenance
  (re)writes provenance, and never reports complete without that clean record); Honesty-NFR unit
  tests assert no "built" claim without committed work + passed review + successful record.
- **Pre-mortem — resume duplicates or skips work.** The reconciler mis-maps commits to tasks and
  re-implements or skips a task. *Mitigation:* every commit a task makes (implementing **and**
  fix-loop) carries the `Task-Id` trailer, so a task = the set of its trailered commits; a
  trailer-less/unmappable commit parks fail-closed (never absorbed); `build_progress` is a pure
  decider whose enumerated unit tests pin each judgement as its own mutant-guard case —
  committed-unreviewed, uncommitted-leftover, multi-commit task, trailer-less leftover **and**
  unmappable-`Task-Id` (both park), merge-base-scoped commit range (base history not read as
  trailer-less), provenance **absent → rewrite** vs **garbled (`ProvenanceError`) → park**,
  stale-generation-on-resume re-thread, all-complete-vs-build-complete, and mid-final-review
  interruption; mirrors the proven `recover.reconcile` shape.
- **Pre-mortem — the per-task review loops forever or parks too eagerly.** *Mitigation:* reuse the
  exact `circuit_breaker` (recurring-finding / no-net-progress / max-iterations) and `loop_state`
  primitives already proven in #104; the fixed maximum (3) bounds every loop; tests cover
  cap-reached → park and clean → complete.
- **Pre-mortem — tasks-doc drift mid-build.** The approved doc is edited after the branch was
  built. *Mitigation:* the content-addressed branch hash changes on any content edit → reconcile
  parks (UFR-11), even when the gate still reads `passed`.
- **Pre-mortem — concurrent runs corrupt the branch.** *Mitigation:* the entry lease blocks a
  second run while live; the generation captured at entry is threaded into `checkpoint.lockGeneration`,
  and at each branch-mutating boundary `build_phase.js` `renew`s the lease then `fence_ok`-checks as
  the last gate before the write, aborting before any write on a lost generation (UFR-10) — the
  proven `/workhorse` per-boundary pattern, not a wall-clock timer the sequential runtime can't fire.
  A node smoke drives fence-lost → abort-before-write → park.
- **Build risk — new deciders' contracts drift from the spec's unhappy paths.** *Mitigation:* each
  new pure module (`task_list`, `task_review`, `build_progress`, `minor_rollup`, `worker_recovery`)
  is built test-first with one test per spec clause it implements; the node smokes assert the
  orchestration's park/proceed branches end-to-end with stubbed leaves — including named cases for
  *the single final `reviewPanel` call receiving the carried-forward Minor roll-up* (FR-7→FR-8), the
  *UFR-10 fence-lost → abort-before-write → park* path, and *worker-stuck → retry-with-context →
  cap-reached → park* plus *"plan is wrong" → immediate park* (UFR-3).

## Dependencies & assumptions

**Dependencies (all merged on `main`, reused unchanged):** the Workflow run spine (#21/#103,
`showrunner.js` + deciders); the managed build-worktree lifecycle (#77, `buildtree.py`); the shared
review-and-fix loop (#104, `review_panel_shell.js` + `panel_tally`/`verify_gate`/`circuit_breaker`/
`loop_state`); the model-tier knob (`model_tier*`). **Not depended on:** `record_deferred.py` (a
sibling #89 artifact not on `main`) — #87 supplies its own minimal deferred writer. The downstream
specialist panel (#89), behavioral testing (#90), and live spec→PR integration consume this phase's
output but are out of scope.

**Assumptions (the build/review can check):** (1) an approved tasks doc (gate `passed`) exists,
produced by the the-architect plan→tasks flow — the phase consumes, never authors it; (2) the
substrate contracts above are stable and reused as-is, with the single *named* exception of the
UFR-10 generation-persistence touch to `recover_entry.py`/`build_entry.py` (see Key decisions); (3) the project verify command is discoverable from
the calibration profile's `verify-command` field, with `skipped` an accepted fallback (the #89
double-run covers it); (4) the per-task SDD discipline follows superpowers subagent-driven-development
(≥ 6.0, single-task-reviewer flow), re-expressed as the script's control flow.
