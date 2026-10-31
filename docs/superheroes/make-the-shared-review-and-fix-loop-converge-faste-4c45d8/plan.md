---
superheroes: doc
schemaVersion: 1
docType: plan
workItem: make-the-shared-review-and-fix-loop-converge-faste-4c45d8
issue: 125
size: large
status: approved
gates: {review: passed}
producedBy: "the-architect@0.3.0"
created: "2026-07-01"
updated: "2026-06-30"
---
# Make the shared review-and-fix loop converge faster and cost less - Plan

## Overview

The shared review loop already has the right safety skeleton: `review_panel_shell.js` owns the
single branch through the loop, `panel_tally.py` / `panel_tally.js`, `loop_synthesis.py`,
`circuit_breaker.py`, and `loop_state.py` own the deterministic decisions, and the showrunner
front-half/code-review paths route through that shell (`plugins/superheroes/lib/review_panel_shell.js`,
`plugins/superheroes/lib/showrunner.js`). The problem is that the loop still treats every
round as "run everything again, fix a single instance, then ask the same full panel again."
That preserves safety, but it wastes rounds and tokens on review-heavy documents.

This plan keeps the existing control-flow posture and extends the shared loop rather than
creating review-specific variants. The loop gains four central capabilities: durable
cross-round memory for the reviser, challengeable coverage decisions, policy-driven
intermediate-round dispatch, and an explicit final confirmation round. Round 1 remains a full
most-capable panel. If round 1 is clean at high confidence, the review certifies immediately.
After a non-clean round, the reviser sees prior findings and may generalize a recurring class
into a labeled coverage decision; intermediate rounds run only dimensions that need another
look, with a cheap-first tier cascade; and certification is allowed only after a full
most-capable confirmation round finds no blocking issue at high confidence.

The same loop record also becomes the source for the readout and telemetry: each run reports
round count, per-dimension run/skip counts, tier escalations, and token usage when the runtime
exposes it. If usage is unavailable, the review outcome remains unchanged and the telemetry
records the gap; benchmark runs are stricter because the cost target cannot be measured without
usage.

## Goals & non-goals

**Goals:**
- Make recurring classes of findings converge by giving the reviser prior-round findings and
  having it record labeled, challengeable coverage decisions instead of applying endless
  single-instance edits (FR-1 through FR-5, UFR-1, UFR-6).
- Reduce intermediate-round cost by skipping high-confidence clean dimensions untouched by the
  latest revision, and by running cheap reviewer tiers first with fail-closed escalation to the
  strongest tier (FR-6, FR-7, UFR-2, UFR-3, UFR-5).
- Preserve the correctness floor: round 1 is always full panel on the strongest tier; any
  multi-round review certifies only after a full strongest-tier confirmation round with no
  fix applied after it (FR-8, FR-11, UFR-1, UFR-2).
- Surface telemetry in the run readout and as a durable artifact: total rounds,
  per-dimension run/skipped counts, tier escalations, and token usage where available (FR-9,
  UFR-7).
- Route the plan review, tasks review, code review, and manual spec-review panel through the
  same central loop behavior, not four copied implementations (FR-10).
- Add benchmark/probe coverage proving the #120 plan and a differently shaped code-review
  benchmark improve while wrong-principle and skipped-regression probes fail closed.

**Non-goals:**
- Changing the review severity rubric, reviewer dimensions, or what counts as blocking. The
  existing five dimensions and `Critical` / `Important` blocking semantics remain the source of
  truth (`plugins/superheroes/rubric/review-base.md`, `plugins/superheroes/lib/panel_tally.py`).
- Certifying reviews with a known blocking tail. The existing `clean-with-skips` terminal is no
  longer a certification terminal for definition-doc gates or ship gates when the skip is a
  blocking finding; a recorded coverage decision must be challengeable and survive final
  confirmation instead.
- Replacing reviewer methodology or rewriting agents. Reviewer prompts gain a result-level
  confidence contract, but the five existing reviewer agents remain the dimensions.
- Introducing an external telemetry service or new paid dependency. Telemetry is local JSON
  beside the run artifacts.
- Solving right-sized panel composition (#34). Round 1 and final confirmation still run all
  dimensions by design.
- Changing build/test-pilot/ship behavior except where they consume the shared review result.

## Architecture

The change is a central extension of the existing #104 loop:

```text
reviewPanel(...)
  load round-state + coverage decisions + telemetry
  choose round kind and dimension/tier schedule
  dispatch selected dimensions only
  escalate low-confidence cheap-tier results inside the dimension
  merge/tally with carried-forward skipped dimensions
  if blockers remain:
      fixStep(blockers, prior findings, coverage decisions, round policy)
      record local fixes, changed subjects, coverage decisions, telemetry
      continue
  if blockers do not remain and round 1 was clean:
      certify clean
  if blockers do not remain after prior fixes:
      run full strongest-tier confirmation
  if confirmation is clean high-confidence:
      certify clean
  else:
      fix and run another confirmation, bounded by the round budget
```

The shell remains control-flow-only. New judgments live in pure helpers with JS twins where
the showrunner bundle needs in-process parity:

- `review_round_policy.py` / `review_round_policy.js` decides round kind
  (`baseline`, `intermediate`, `confirmation`), which dimensions run or carry forward, which
  tier to use, and whether a cheap-tier result must escalate. It deliberately does not decide
  fix, confirmation, certify, or halt; those terminal decisions stay with the tally/continuation
  deciders.
- `review_memory.py` / `review_memory.js` stores and reads the durable round record and exposes
  pure recurrence helpers: findings by dimension, class keys, changed subjects, coverage
  decisions, carried-forward verdicts, and telemetry. Python owns file I/O; the JS twin owns the
  parity-locked normalization, promotion, and recurrence decisions used by the bundled shell.
- `coverage_decisions.py` records labeled decisions in the right durable surface: the document
  under review for doc legs and the code-review decision record for code review.
- `review_telemetry.py` accumulates run/skipped/tier/token telemetry and renders a compact
  readout block.

The existing deciders stay in place and are extended only where their current contract is the
right owner:

- `panel_tally.py` / `.js` keeps compile, confidence, present-deferred, and terminal
  accounting. It gains per-dimension result inputs so a skipped dimension contributes its
  previous verdict without being mistaken for a newly changed result.
- `circuit_breaker.py` / `.js` stops treating the first recurrence as an immediate halt when
  no class-covering decision has been attempted. Recurrence detection and the
  "generalize this class" signal belong to `review_memory`; the breaker consumes that state only
  to decide no-progress/round-budget halts after a class-covering decision has already been
  attempted and challenged.
- `loop_readout.py` renders the new telemetry and coverage-decision summary from the shared
  terminal record.
- `front_half.py` / `.js` maps only a true clean terminal to a passed review gate; a
  blocking clean-with-skips outcome remains visible but does not advance.
- `showrunner.js`'s native code-review advancement path is updated alongside the shared
  terminal shape: `ADVANCE_TERMINALS`, `reviewCodePhase`, and the code-review smoke expectations
  stop treating a blocking `clean-with-skips` result as `gate: "passed"`.

The callers stay thin:

- Showrunner document reviews already call `runReviewDocPanel` in `showrunner.js`; the doc
  leaf wrappers pass the doc path and doc type and receive the updated loop behavior.
- Showrunner/native code review already calls `runReviewCodePanel`; the code wrappers pass the
  worktree/head, verify command, and tier overrides.
- Manual `review-spec`, `review-plan`, `review-tasks`, and `review-code` skills are updated to
  reference the shared loop contract in `plugins/superheroes/reference/review-loop.md` for the
  converge/dispatch/confirmation/telemetry behavior instead of restating divergent loops. Their
  leg-specific setup, reviewer framing, and gate-write rules remain local to the skill.

This avoids a second orchestration framework. The loop still uses the existing runtime
pattern: genuine LLM leaves for reviewers, synthesis, and revisers; cheap exec leaves for
deterministic file writes; pure helpers for decisions.

## Components & interfaces

- **`review_round_policy.py` / `review_round_policy.js` (new pure helper).** Inputs:
  previous round records, current round number, max rounds, changed subjects, dimension list,
  tier policy, and whether the run has entered confirmation mode. Output:
  `{roundKind, dimensions, escalationPolicy}` where each dimension has
  `{action: "run"|"skip", tier: "reviewer"|"reviewer-deep", reason, carriedFromRound?}`.
  Error cases fail closed to "run every dimension on reviewer-deep." The JS twin is bundled
  because `showrunner.js` must schedule reviewer leaves in-process. The helper never returns a
  terminal verdict; `panel_tally.py` / `.js` and `loop_state.py` / `.js` remain the owners of
  passed, fix-again, confirmation, skipped-blocker, and halt outcomes.

- **Reviewer result contract (extended at the shell boundary).** Reviewer leaves now return
  `{findings: [...], confidence: "high"|"low", verificationReceipt?: {...}, usage?: {...}}`.
  A legacy array return is accepted only as `confidence: "low"` so older or garbled leaves
  escalate rather than certify cheap. High-confidence clean requires both explicit result-level
  confidence and, in final confirmation mode, a checked receipt that names the Chain-of-
  Verification steps completed; malformed or missing final receipts are treated as
  low-confidence. Finding-level `confidence` from `review-base.md` still applies to each
  finding.

- **`review_panel_shell.js` (extended shell).** Still owns only event flow. It loads
  `round-records.json`, asks `review_round_policy` which dimensions to dispatch, calls
  `reviewerAgent(reviewer, context, rubric, runDir, round, {tier, roundKind})`, escalates a
  cheap result when policy says so, passes the current artifact plus recorded coverage decisions
  to every reviewer dispatch after the first coverage decision exists, and passes prior findings
  only to `fixStep`. It never hands prior-round finding lists to intermediate reviewers.

- **`review_memory.py` / `review_memory.js` (new round-record store + pure recurrence helper).**
  Owns `round-records.json` schema version 2:
  each record stores `round`, `kind`, `dimensions`, compiled findings, class keys, changed
  subjects, coverage decisions, and token telemetry. It reads schema version 1 records from the
  current accumulator by promoting them into "all dimensions unknown, run all next round" so
  existing in-flight runs fail closed rather than crash. The recurrence/class-key decision has a
  JS twin and parity fixture because the showrunner shell consumes it in-process. It returns the
  `generalize_required` signals passed to `fixStep`; first occurrences produce no signal.

- **`coverage_decisions.py` (new recorder).** Owns the "legible, challengeable decision"
  surface. For doc legs, it adds or updates a bounded `## Review coverage decisions` section
  at the end of the doc with labeled entries such as `RCD-2-test-acceptance-coverage`; it never
  rewrites unrelated doc content. For code review, it writes the same entries under the
  work-item/run control-plane store and includes them in every subsequent code-review reviewer
  prompt, the final confirmation prompt, and the readout. Manual `review-code` runs that lack a
  work-item issue directory use a run-scoped session record under their review session and pass
  that path through the same shell interface. Entries carry
  `{id, kind, classKey, text, sourceRound, challengedBy?}`.

- **Fix/reviser report contract (extended).** The caller-supplied `fixStep` returns:
  `{fixes, deferred, changedSubjects, coverageDecisions, extras}`. `changedSubjects` is the
  reviser's declared subject-area impact; missing or unreadable values are treated as all
  dimensions touched. `coverageDecisions` are passed to `coverage_decisions.py`; a failed
  coverage-decision write turns the decision into an unresolved blocker rather than a hidden
  suppression.

- **Class-key support in `review_memory.py`.** The initial class key is deterministic:
  `dimension + taxonomy_or_empty + normalized_title`. The reviser may return a stronger
  `classKey` when two findings share an underlying gap but not a title. That stronger key is
  recorded and used for recurrence from then on. If the reviser is unsure, it withholds a
  principle and applies a local fix, matching FR-3.

- **`panel_tally.py` / `.js` (extended).** Accepts dimension result objects instead of only a
  flat findings list. A skipped dimension contributes its carried verdict to the gate and
  telemetry, but its findings are marked `carried: true` with `sourceRound`, so recurrence and
  no-progress checks do not treat the carry-forward as a new reviewer result.

- **`circuit_breaker.py` / `.js` (extended).** Adds class-aware progress without owning class
  detection. It consumes `review_memory`'s recurrence/principle state and returns `halt` only at
  the round budget, after no progress across resolved classes, or when a recorded principle keeps
  being challenged and cannot be revised into a clean confirmation.

- **`review_telemetry.py` (new local telemetry helper).** Writes `review-telemetry.json` under
  the run directory and mirrors the terminal summary into the control-plane issue directory.
  Schema: round count, per-dimension runs/skips/cheap/strong/escalations, expected token-bearing
  leaves by round, per-leaf usage present/missing, completeness status, benchmark labels, and
  telemetry gaps. Benchmark totals are valid only for complete scopes, or for explicitly excluded
  missing scopes recorded in the frozen comparison.

- **`loop_readout.py` (extended renderer).** Renders terminal, reason, fixes, coverage decisions,
  challenged principles, telemetry, skipped dimensions, tier escalations, and token usage. It
  keeps the existing unknown-schema fail-safe.

- **Manual review skill docs (updated, not reimplemented).** `review-spec`, `review-plan`,
  `review-tasks`, and `review-code` keep leg-specific setup and gate writes, but their loop
  sections point at `plugins/superheroes/reference/review-loop.md` for recurrence, skipping,
  tier cascade, confirmation, and telemetry. This is the markdown-side equivalent of the shared
  code path and is covered by `test_loop_gate_wired.py` / skill-shape tests.

## Data flow & data model

The existing per-run `runDir` remains the scratch home. The control-plane issue directory
remains the durable cross-run home. The new data is additive:

- **`round-records.json` schema version 2** in `runDir`. Each round:
  ```json
  {
    "schemaVersion": 2,
    "round": 2,
    "kind": "intermediate",
    "dimensions": {
      "test-reviewer": {
        "dimension": "Test",
        "status": "run",
        "tier": "reviewer",
        "confidence": "high",
        "findings": []
      },
      "security-reviewer": {
        "dimension": "Security",
        "status": "skipped",
        "carriedFromRound": 1,
        "reason": "high-confidence clean and latest revision touched only tests"
      }
    },
    "findings": [],
    "changedSubjects": ["Test"],
    "coverageDecisions": [],
    "tokenUsage": {"available": true, "input": 0, "output": 0, "total": 0}
  }
  ```
  Version 1 records promote to version 2 with every dimension unknown, which schedules a full
  strongest-tier round on resume.

- **Coverage decisions for doc legs** live in the reviewed doc itself, in a bounded final
  section. That is intentionally a content change: final confirmation reviewers can read and
  challenge the decision without a hidden do-not-raise list. The section is appended only by
  `coverage_decisions.py` and contains no prior-round finding dump.

- **Coverage decisions for code review** live under the work-item/run control-plane store, for
  example `issues/<work-item>/review-coverage-decisions.json`, and are included in final
  confirmation context and in `loop_readout`. Once a code-review coverage decision exists, the
  shell also threads that record into every later reviewer dispatch as challengeable context.
  This uses the same machine-local store as `path_choice.py` and `control_plane.py`, not the
  project profile.

- **`review-telemetry.json`** lives under `runDir` and is mirrored to the issue directory when
  the terminal record is written. Missing token usage is tracked per expected token-bearing
  leaf, not just as a run-level boolean. A run can still certify with partial telemetry, but
  benchmark cost comparisons require complete usage for the comparison scope or a recorded
  exclusion that removes the same scope from both baseline and post-change totals.

- **Result-level confidence** is additive to the reviewer result, not to the findings schema.
  Finding-level confidence remains in `review-base.md`; result-level confidence answers the clean
  result question that a finding array cannot express. Final confirmation additionally requires
  a verification receipt so a wrapper cannot certify by returning only
  `{findings: [], confidence: "high"}`.

- **Durable-write fencing** is explicit on every artifact write that can outlive the current
  process: coverage decisions, round records, terminal readouts, telemetry mirrors, and gate
  records. Code-review/showrunner runs reuse the existing control-plane lease generation and
  content hash. Manual doc-review sessions use the session id plus a content-hash or mtime CAS on
  the reviewed artifact. A stale or unreadable fence fails closed as superseded and does not write.
  Any writer that mutates a definition doc or coverage-decision section writes through a
  same-directory temp file, fsyncs, and `os.replace`s after the fence check; a failed replace leaves
  the old doc readable and the blocker unresolved.

Backward compatibility is fail-closed: a missing/old/corrupt round record schedules a full
strongest-tier round; a corrupt coverage-decision record cannot suppress a finding; unreadable
telemetry is omitted from cost accounting but not from correctness decisions.

## How the requirements are met

- **FR-1:** `review_memory.recurrent_classes` (Python and JS parity helper) identifies a blocking class that has appeared in
  two or more rounds. The next `fixStep` receives that signal and must either record a labeled
  class-covering coverage decision or explicitly leave the class unresolved. The loop treats a
  failed coverage-decision write as unresolved.
- **FR-2:** `fixStep` receives prior-round compiled findings and class keys from
  `review_memory.py` / `.js` on every round after the first. Reviewer leaves do not receive this
  list.
- **FR-3:** When a class has appeared only once, `review_memory` produces no
  `generalize_required` signal and the reviser prompt requires a local fix only.
- **FR-4:** `coverage_decisions.py` records principles in the reviewed document for doc legs and
  in the code-review decision record for code review. Every later reviewer dispatch receives the
  visible decisions as challengeable claims; prior-round finding lists remain fixStep-only.
- **FR-5:** There is no hidden do-not-raise list. Dismissals must become a visible coverage
  decision. If a concern cannot be written legibly, cannot pass the stale-run fence, or keeps
  recurring, the round budget path halts and reports it.
- **FR-6:** `review_round_policy` reruns dimensions that reported findings last round, dimensions
  whose subject area was touched by the latest revision, and any dimension where subject impact is
  unknown. Only high-confidence clean, untouched dimensions are skipped.
- **FR-7:** Intermediate rounds start each run dimension at `reviewer`; a low-confidence result
  or missing result immediately reruns that dimension at `reviewer-deep`. High-confidence cheap
  findings are accepted for intermediate fix routing because final confirmation reruns all
  dimensions on the strongest tier.
- **FR-8:** After any review that needed fixes, the shell enters confirmation mode and schedules
  a full `reviewer-deep` panel. Certification happens only from a clean high-confidence
  confirmation whose result receipts pass validation, with no fix applied after it. A failed
  confirmation, low-confidence result, or malformed receipt loops back to fix and then another
  confirmation.
- **FR-9:** `review_telemetry.py` writes round count, per-dimension run/skip/tier counts, and
  per-leaf token usage completeness when available. `loop_readout.py` includes the same values
  in the readout and labels partial telemetry as not benchmark-valid.
- **FR-10:** The runtime path is `reviewPanel` plus shared helpers; the manual skills route their
  repeated-loop instructions through the same `reference/review-loop.md` contract. Per-leg code
  is limited to setup, prompts, and gate semantics, and the native `showrunner.js` code-review
  advancement path consumes the same non-advancing skipped-blocker terminal.
- **FR-11:** Round 1 is always `baseline`: every dimension, `reviewer-deep`, no skipping, no
  cheap-first cascade. A clean high-confidence baseline certifies immediately and does not run a
  separate confirmation.
- **UFR-1:** A wrong principle is visible to every later reviewer and to the full strongest-tier
  confirmation panel as a claim. If challenged with a blocking finding, the shell does not
  certify and the reviser must revise or remove the principle before another confirmation.
- **UFR-2:** Any regression introduced while a dimension was skipped is caught by the final full
  confirmation round because no dimension is skipped there.
- **UFR-3:** Low-confidence cheap-tier results never decide a dimension; policy escalates them to
  `reviewer-deep`.
- **UFR-4:** On resume, `review_memory.py` / `.js` rebuilds prior findings, recorded principles,
  changed subjects, and telemetry from `round-records.json` and coverage-decision artifacts
  before the next fix step runs.
- **UFR-5:** Skipped dimensions carry their most recent verdict with `carried:true` and
  `sourceRound`, so they contribute to the current gate while recurrence/progress logic does not
  count them as new reviewer output.
- **UFR-6:** Doc coverage decisions are bounded additions to a dedicated section. The recorder
  refuses broad rewrites and returns an unresolved-finding signal if it cannot update the section.
- **UFR-7:** Telemetry write failures and missing token usage do not change pass/fail decisions.
  They are named in the readout, saved as partial telemetry when possible, and excluded from
  benchmark cost success unless the missing scope is explicitly excluded on both sides.
- **UFR-8:** The existing seven-round cap remains. At the cap, any unresolved blocker,
  low-confidence final result, or unrecordable recurring concern halts and reports the open
  findings and round context.
- **Convergence NFR:** The #120 plan benchmark exercises recurrence generalization and final
  confirmation. The target is clean certification in three rounds or fewer.
- **Cost NFR:** The benchmark freezes a pre-change baseline and compares post-change telemetry
  from the same run shape. Savings are attributed to fewer rounds, skipped dimensions, and tier
  split only when the telemetry completeness model says the comparison scope is complete.
- **Correctness floor NFR:** Only a full strongest-tier baseline or confirmation can certify.
- **Uniformity NFR:** Tests and benchmarks exercise doc review, tasks/plan review, code review,
  and manual spec-review instructions through the shared contract.
- **No regression NFR:** A clean first round still certifies in one round and runs no extra
  confirmation.

## Key decisions & alternatives

- **Decision:** Extend the central shared loop instead of implementing per-review optimizers.
  **Options weighed:** (a) add round policy, memory, coverage decisions, confirmation, and
  telemetry to `review_panel_shell.js` plus pure helpers; (b) add bespoke convergence logic inside
  `review-plan`, `review-tasks`, `review-spec`, and `review-code`; (c) leave the shell alone and
  tune prompts to ask reviewers/revisers to be cheaper. **Choice + why:** (a), because FR-10
  requires one shared behavior and the existing shell is already the shared runtime in
  `showrunner.js`. The strongest case for (b) is smaller local edits per skill; it loses because
  four copies would drift. The strongest case for (c) is lowest code churn; it loses because
  prompt discipline cannot enforce dispatch skips, tier escalation, or final confirmation.
  **Accepted downside:** the central shell and tally helpers become more complex and need careful
  parity tests. **Reversible?** two-way at module boundary; individual helpers can be reverted.
  **Mode:** PROCEED. **Reverse path:** revert the helper/shell changes and restore the previous
  always-full-panel loop. **Expiry:** n/a. **Escalated?** no, engineering-internal and directly
  required by the spec.

- **Decision:** Represent coverage decisions in the artifact/readout, not as a hidden
  suppression list. **Options weighed:** (a) append bounded labeled coverage decisions to docs
  and code-review decision records; (b) maintain a hidden do-not-raise list in run state; (c)
  place prior-round findings in every reviewer prompt so reviewers can infer what was dismissed.
  **Choice + why:** (a), because FR-4/FR-5 explicitly require challengeable visibility and no
  hidden suppression. The strongest case for (b) is lower prompt/document noise; it loses because
  it weakens the safety model. The strongest case for (c) is maximal context; it loses because
  reviewers stop being independent and token costs rise. **Accepted downside:** docs gain a
  review-owned section that is not part of the owner's original prose. **Reversible?** two-way;
  remove the section/record if the loop changes. **Mode:** PROCEED. **Reverse path:** remove
  coverage decision entries before build or in a cleanup task. **Expiry:** before final merge if
  the format proves noisy. **Escalated?** no; the spec mandates this behavior.

- **Decision:** Add result-level reviewer confidence instead of inferring clean confidence from an
  empty findings array. **Options weighed:** (a) reviewer returns `{findings, confidence}`; (b)
  infer high confidence whenever findings are empty; (c) infer low confidence whenever findings
  are empty and always escalate. **Choice + why:** (a), because FR-6/FR-7/FR-8 need a clean-result
  confidence signal. The strongest case for (b) is backward compatibility; it loses because an
  empty array can mean "not confident enough to flag." The strongest case for (c) is safety; it
  loses because it removes most tier savings. **Accepted downside:** all reviewer wrappers and
  tests must learn the new shape; legacy arrays degrade to low confidence. **Reversible?** two-way
  with schema adapter. **Mode:** PROCEED. **Reverse path:** adapter can treat explicit confidence
  as optional again. **Expiry:** after reviewer wrappers and smokes land. **Escalated?** no.

- **Decision:** Cheap-tier intermediate reviews may decide high-confidence blocking findings, but
  never final certification. **Options weighed:** (a) cheap first, escalate only low-confidence
  results; (b) always run strongest tier; (c) cheap-only intermediate and no escalation. **Choice
  + why:** (a), matching FR-7. The strongest case for (b) is simpler correctness; it loses the
  cost target. The strongest case for (c) is maximum savings; it loses the safety floor. **Accepted
  downside:** a cheap high-confidence false positive can cost an extra fix round, but the final
  strongest confirmation catches false clean results. **Reversible?** two-way via tier policy.
  **Mode:** PROCEED. **Reverse path:** switch policy to strongest-only if benchmark safety or
  false-positive cost is bad. **Expiry:** after benchmark telemetry. **Escalated?** no.

- **Decision:** Let the reviser supply semantic class keys, with deterministic keys as a floor.
  **Options weighed:** (a) deterministic key first, reviser may merge related findings into a
  stronger `classKey`; (b) deterministic title/taxonomy keys only; (c) separate classifier leaf.
  **Choice + why:** (a), because "same class" is partly semantic, and the reviser is already
  seeing prior findings. The strongest case for (b) is repeatability; it misses recurring classes
  with different titles. The strongest case for (c) is more specialized classification; it adds
  dispatch cost and another judgment surface. **Accepted downside:** class merging is a reviser
  judgment, so wrong generalizations must be caught by final confirmation. **Reversible?** two-way.
  **Mode:** PROCEED. **Reverse path:** ignore returned `classKey` and use deterministic keys only.
  **Expiry:** after safety probes. **Escalated?** no.

- **Decision:** Store telemetry locally rather than introduce an external metrics backend.
  **Options weighed:** (a) local JSON in runDir plus control-plane mirror; (b) external service;
  (c) readout-only telemetry with no durable file. **Choice + why:** (a), because FR-9 needs a
  saved artifact and the project is a local single-user tool. The strongest case for (b) is easier
  cross-run charts; it adds cost/vendor surface. The strongest case for (c) is minimal code; it
  cannot support benchmark comparisons. **Accepted downside:** cross-run analysis is file-based
  until a later reporting tool exists. **Reversible?** two-way. **Mode:** PROCEED. **Reverse path:**
  replace local writer with another sink later. **Expiry:** n/a. **Escalated?** no, no cost added.

## Cross-cutting concerns

- **Security & privacy:** No new user data, network service, or auth boundary is introduced. The
  new records can contain review findings and snippets from local code/docs, so they stay in the
  existing machine-local run/control-plane stores. The code-review coverage-decision record must
  go through the same secret-scrub posture as readouts before anything is posted to a PR. Unsafe
  shell remains in scope for security review because helper CLIs and skill snippets are product
  surface in this repo.

- **Observability:** `review-telemetry.json` plus `loop_readout.py` answer "what happened?" at
  2am: which round certified or halted, which dimensions ran/skipped, why a dimension skipped,
  which cheap results escalated, which coverage decisions were recorded/challenged, and where
  token usage was available or missing. The readout names partial telemetry distinctly from
  correctness failure and says when a telemetry record is not valid for benchmark cost proof.

- **Reliability & failure modes:** Every untrusted or unavailable signal fails closed: unknown
  changed subjects run all dimensions; missing reviewer confidence escalates; corrupt round
  memory schedules a full strongest round; failed coverage-decision writes leave the finding
  unresolved; stale-run fences prevent superseded runs from writing durable decisions; telemetry
  failures do not certify or halt the review. Confirmation mode prevents intermediate savings
  from becoming final correctness, and final-confirmation clean results need a verification
  receipt rather than only a self-reported confidence string.

- **Validation & benchmarks:** Acceptance uses six deliberately shaped fixtures:
  (1) the #120 plan replay, with a freshly frozen pre-change run-level token baseline and a
  post-change target of clean certification in three rounds or fewer; (2) a second code-review
  benchmark whose fixture contains a recurring review class across code/test files so convergence,
  skipping, and tier split are measured outside document-review prose; (3) a wrong-principle doc
  fixture where the reviser records a plausible but false coverage decision and final
  confirmation must challenge it; and (4) a skipped-dimension regression fixture where an
  intermediate fix touches a dimension marked clean, proving the final full panel catches the
  regression; and (5) a crash/resume fixture that seeds v2 `round-records.json` plus a
  coverage-decision artifact after round 1, restarts `reviewPanel` from the same `runDir`, and
  asserts the next `fixStep` receives prior compiled findings, class keys, changed subjects, and
  recorded principles. The same resume fixture corrupts the memory/coverage-decision state and
  asserts the policy schedules a full `reviewer-deep` round and cannot certify from the corrupt
  state. It also forces a crash or write error before the atomic `os.replace` for a doc mutation
  and asserts the old definition doc remains readable and unchanged; and (6) a telemetry-failure
  fixture that forces `review_telemetry.py` to fail to write and separately simulates missing
  per-leaf usage. That fixture asserts the review terminal/gate matches the same run without the
  telemetry failure, the readout/artifact marks telemetry as partial or not benchmark-valid, and
  benchmark cost comparison refuses the incomplete scope unless the same scope is explicitly
  excluded on both sides. Each benchmark stores baseline telemetry, post-change telemetry,
  attribution, and completeness status; each fail-closed probe must end in halt/fix-needed, not
  passed.

## Rollout & migration

This is internal pipeline machinery with durable local records, so rollout is by compatibility
and tests rather than a user-visible flag.

- Add schema version 2 readers that can promote existing version 1 `round-records.json` into a
  conservative "run all next" state. No migration command is required.
- Keep old reviewer array returns readable but low-confidence, so any partially updated caller
  escalates rather than certifies from stale shape.
- Land helpers and tests first, then wire `review_panel_shell.js`, then update showrunner callers,
  then update manual skill loop text to reference the shared contract.
- Update code-review advancement at the same time as the shared terminal shape so
  `clean-with-skips` cannot pass through `ADVANCE_TERMINALS` while doc gates are stricter.
- `showrunner.bundle.js` must be regenerated after JS helper changes; `bundle_showrunner.js` is
  the dependency-order source and already includes loop helper ordering.
- Rollback is a normal code revert. Since coverage-decision sections are bounded and labeled,
  cleanup can remove them mechanically if a rollback happens before build.

## Risks & mitigations

- **Risk: a recorded principle hides a real issue.** Mitigation: coverage decisions are visible,
  not hidden; final confirmation reads them as challengeable claims; wrong-principle probes must
  fail closed before acceptance.
- **Risk: dimension skipping misses a regression.** Mitigation: unknown subject impact runs all
  dimensions, skipped dimensions carry reason/source round, and final confirmation runs every
  dimension on the strongest tier.
- **Risk: token usage is not exposed consistently by the host runtime.** Mitigation: telemetry
  records per-leaf missing usage without changing review outcomes; benchmark mode treats partial
  or missing usage as unable to prove the cost NFR unless the missing scope is excluded from both
  compared runs.
- **Risk: result-level confidence is under-specified and reviewers overclaim high confidence.**
  Mitigation: prompts define high confidence in terms of the existing Chain-of-Verification;
  final confirmation requires a receipt-shaped rationale that the shell can validate; cheap-tier
  wrong clean is caught by final confirmation; benchmark attribution calls out when tier split
  costs more than it saves.
- **Risk: central shell complexity creates parity drift between Python and JS helpers.**
  Mitigation: every new or modified pure decision has parity tests alongside `test_parity.py`,
  explicitly including `review_round_policy`, `review_memory`, `panel_tally`, `circuit_breaker`,
  and `front_half`; smoke tests cover shell behavior with stubbed reviewers.
- **Risk: manual skill text drifts from native loop behavior.** Mitigation: move shared loop
  instructions to `plugins/superheroes/reference/review-loop.md` and add skill-shape tests that
  each review skill references the shared contract instead of carrying a private convergence loop.
- **Risk: benchmark overfits to #120.** Mitigation: acceptance includes a second differently
  shaped code-review benchmark with its own frozen baseline, as the spec requires.
- **Risk: a superseded run writes old coverage decisions or telemetry after a newer run.**
  Mitigation: every durable write carries a run/session identity and passes the existing
  lease/content-hash fence or a manual-session CAS; stale or unreadable fences fail closed and
  report the run as superseded.
- **Risk: a crash corrupts a reviewed definition doc during a coverage-decision or gate write.**
  Mitigation: every touched doc mutation path uses same-directory temp-file writes, fsync, and
  atomic `os.replace` after the fence/CAS; failed replace leaves the blocker unresolved and the
  previous doc content intact.

## Dependencies & assumptions

- The approved parent spec is
  `/path/to/home/.claude/workhorse/projects/8fa39520fa839af0/docs/make-the-shared-review-and-fix-loop-converge-faste-4c45d8/spec.md`,
  with `gates.review: passed`.
- The project calibration is single-user, no UI, stdlib-heavy helpers, with the canonical verify
  command from `config/core.md`.
- The existing loop substrate is the starting point: `review_panel_shell.js`, `panel_tally.py`
  / `.js`, `loop_synthesis.py` / `.js`, `circuit_breaker.py` / `.js`, `loop_state.py` / `.js`,
  `front_half.py` / `.js`, `loop_readout.py`, and `showrunner.js`.
- The runtime can expose token usage for benchmark runs or at least report that usage is
  unavailable. If it cannot expose usage for a deliberate benchmark, the cost target is not
  proven.
- The #120 benchmark plan remains available in the project store and can be rerun under a frozen
  baseline and post-change loop.
- No external packages are required; all new helpers stay stdlib-only and JS bundle-compatible.
