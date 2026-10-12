---
superheroes: doc
schemaVersion: 1
docType: spec
workItem: workhorse-build-phase-native-sdd-orchestration-cf9f53
issue: 87
size: large
status: approved
gates: {review: passed}
producedBy: "the-architect@0.2.0"
created: "2026-06-22"
updated: "2026-06-25"
---
# Workhorse build phase — native SDD orchestration

## Purpose

The showrunner's build phase today is a thin proof slice: it makes one throwaway
change just to prove the pipeline's shape. This work turns it into the real thing —
a build phase that takes an approved tasks doc and actually *builds* it, task by
task, test-first, with reviews — and settles what becomes of Workhorse.

Workhorse is not retired; it is **re-expressed**. Its build job, its libraries, and
its reviewers move into the showrunner as the **"workhorse" phase**, run as
deterministic pipeline control flow instead of step-by-step prose. The orchestration
role Workhorse's prose used to play moves up to the showrunner, and the canonical
path becomes: *discovery → spec → approve → the showrunner runs to a green-CI PR*.
This delivers the heaviest single phase of that engine.

## Who it's for

- **The project owner/operator.** You want to point the engine at one approved
  work-item and have it genuinely build it — not just simulate the pipeline's shape —
  and you want it to make honest, recoverable progress when left alone.
- **The showrunner pipeline itself.** Downstream phases (the specialist review panel,
  behavioral testing, PR + CI + ship) consume this phase's output: a reviewed,
  committed branch plus the evidence that the build genuinely ran.

## Functional requirements

**FR-1.** When the workhorse phase begins for a work-item whose tasks-doc review gate
reads `passed`, the workhorse phase shall execute every task in that approved tasks
doc, producing committed changes on the build branch.
  - *Acceptance (Given-When-Then):* Given an approved tasks doc of N tasks, when the
    workhorse phase runs to completion, then the build branch carries commits
    implementing all N tasks and no task is left unbuilt.

**FR-2.** Before executing the first task, the workhorse phase shall set up a dedicated
build worktree and a build branch unique to this work-item and its approved tasks.
  - *Acceptance:* Given a fresh approved tasks doc, when the workhorse phase starts,
    then a dedicated worktree and a branch named for the work-item and the approved
    tasks exist and carry every build commit.

**FR-3.** For each task, the workhorse phase shall implement the task test-first via a
single build worker — the task's tests written and observed failing before the change that
makes them pass.
  - *Acceptance:* Given a task, when its build worker completes, then the build record for
    that task shows its test(s) were written and observed failing before the implementing
    change and passing after, and the tests pass once that change lands.

**FR-4.** After a task's build worker completes, the workhorse phase shall have a
separate reviewer assess that task before any later task begins.
  - *Acceptance:* Given a completed task, when its worker reports done, then a reviewer
    evaluates that task and no later task starts until this review concludes.

**FR-5.** The per-task reviewer shall return two verdicts — spec compliance (the task
met its brief, with nothing extra) and code quality — and the workhorse phase shall
treat a task as reviewed only when both verdicts are present.
  - *Acceptance:* Given a reviewer report, when either verdict is missing, then the
    task is not marked complete and the review is re-requested.

**FR-6.** When a per-task review raises a Critical or Important finding, the workhorse
phase shall fix the finding and re-review the task, repeating up to a fixed maximum
number of fix-and-re-review attempts, after which it parks (UFR-4).
  - *Acceptance:* Given a task with a Critical finding, when a fix is applied, then the
    task is re-reviewed and a clean re-review marks it complete. Given a task with an
    Important finding, the same fix-and-re-review applies. Given findings that persist
    to the fixed maximum, then the phase parks (UFR-4) rather than continuing to loop.

**FR-7.** When a per-task review raises only Minor findings, the workhorse phase shall
record those findings and carry them forward to the end-of-build review rather than
block the task.
  - *Acceptance:* Given a task whose only findings are Minor, when its review concludes,
    then the task is marked complete and the Minor findings are recorded for the final
    review.

**FR-8.** After the last task is complete, the workhorse phase shall run exactly one
whole-branch review of the entire build through the shared review-and-fix loop — a single
generalist reviewer, supplied with the accumulated Minor-findings record — and shall report
the build complete only on a fully clean result — no open Critical or Important findings
(Minor findings carry forward per FR-7) — parking otherwise (FR-6, UFR-4).
  - *Acceptance:* Given all tasks complete, when the build finishes, then exactly one
    whole-branch review runs over the full branch through the shared loop, receives the
    Minor-findings roll-up, and has its Critical/Important findings fixed and re-reviewed
    (bounded by the same fixed maximum as a task) before the phase reports complete; a
    non-clean result parks (UFR-4) instead of reporting complete.
  - *Acceptance (verify gate):* Given the whole-branch review, when it runs, then the
    project's verify command runs as part of that review.
  - *Acceptance (ordering, #59):* Given a completed build, when the phase runs, then the
    whole-branch final review runs to completion after the last per-task review and before
    the phase hands off — never snipped or skipped — which places it ahead of the downstream
    specialist review panel (#89) that consumes the handoff.

**FR-9.** When the build is complete — after every task fix and every whole-branch
final-review fix — the workhorse phase shall record build provenance exactly once, over
the exact commit X it hands off, and shall not re-anchor it thereafter.
  - *Acceptance:* Given a completed, fully-fixed build whose handed-off commit is X, when
    provenance is recorded, then it names commit X — never an earlier, pre-fix commit — and
    the phase writes that provenance once and does not re-anchor it within this phase.
  - *Note (scope boundary):* build provenance attests the build ran over X; it is not a
    freshness proof over a later shipped commit. A downstream phase (#89) may apply further
    fixes and attests review over the moved tip — it does not re-stamp this build provenance
    (the first half of the ship gate; consistent with #104's ship-gate note).

**FR-10.** When the build completes, the workhorse phase shall hand off only its build
outputs — the reviewed branch, the build-provenance record, and the Minor-findings
record — and shall not create the pull request, run the specialist review panel, merge,
or force-push.
  - *Acceptance:* Given a completed build, when the phase hands off, then its outputs
    are available to the downstream phases and no pull request, panel review, merge, or
    force-push occurred in this phase.

**FR-11.** The workhorse phase shall record its progress as each task is marked complete,
and shall likewise record that it has entered the whole-branch final review and whether
that review has reached a clean, recorded result — so a relaunch can resume from recorded
state rather than from the start, and can tell "all tasks complete" apart from "build
complete."
  - *Acceptance:* Given a build that completes tasks 1..K, when each completes, then a
    durable record marks it complete; given the whole-branch final review has begun but not
    reached a clean result, then the record shows the build is not yet complete; and a
    relaunch reads that record to determine where to resume (see UFR-7).

**FR-12.** Wherever the run surfaces its current phase — run state, logs, the handoff
readout — the workhorse phase shall identify itself as **"workhorse."**
  - *Acceptance:* Given a run in the build phase, when it reports its current phase, then
    the surfaced label reads "workhorse."

## When things go wrong (significant unhappy paths)

**UFR-1.** If the tasks-doc review gate is not `passed`, or the approved tasks doc
cannot be read, then the workhorse phase shall refuse to build and park with a clear
reason, making no branch and no commits.
  - *Acceptance:* Given a tasks doc whose gate is `pending`/missing or is unreadable,
    when the workhorse phase starts, then it parks naming the cause and creates nothing.

**UFR-2.** If the build worktree or branch cannot be set up — for example the target
location is occupied or holds uncommitted work — then the workhorse phase shall park and
surface the obstacle without overwriting or force-removing existing work.
  - *Acceptance:* Given an occupied or dirty target, when setup runs, then the phase
    parks, names the location, and removes or overwrites nothing.

**UFR-3.** If a build worker cannot complete a task, then the workhorse phase shall make
a bounded recovery effort — supplying the missing context, or escalating to a more
capable worker, up to a fixed maximum number of attempts — and, when that maximum is
reached or the task is structurally too large or the plan itself is wrong, park with a
clear reason rather than guess or fake completion.
  - *Acceptance:* Given a worker that reports it needs more context, when the phase
    retries with that context, then it proceeds on success; given a worker still blocked
    at the fixed maximum, or a "the plan is wrong" signal, then the phase parks naming
    the task and the cause.

**UFR-4.** If a review — a per-task review or the whole-branch final review — cannot be
brought to a fully clean result within the fixed maximum number of fix-and-re-review
attempts, or it ends with a blocking (Critical or Important) finding deliberately left
unresolved, then the workhorse phase shall surface the unresolved findings and park rather
than mark the work complete or report a clean build.
  - *Acceptance:* Given a review whose Critical findings persist to the fixed maximum, when
    that maximum is reached, then the phase parks and surfaces the open findings, and the
    task (or the build) is not marked complete. Given a whole-branch final review that ends
    with a blocking finding deliberately skipped or deferred, then the phase surfaces that
    finding and does not report a clean build.

**UFR-5.** If the per-task reviewer flags a requirement it cannot verify from the task's
diff alone — one that spans tasks or lives in unchanged code — then the workhorse phase
shall either confirm the requirement is met (and, if it finds a real gap, send the task
back for a fix and re-review) or park the item, and shall never pass it unexamined.
  - *Acceptance:* Given a "cannot verify from diff" item, when it surfaces, then it is
    either confirmed met, sent back for a fix, or parked with the item named — never
    silently marked complete.

**UFR-6.** If a durable record of build progress or build provenance cannot be written,
then the workhorse phase shall park (fail-closed) and report the partial state honestly,
rather than claim a clean build.
  - *Acceptance:* Given a failed progress or provenance write, when it occurs, then the
    phase parks with a "could not record state" reason and does not advance.

**UFR-7.** If the run is interrupted, then on relaunch the workhorse phase shall reconcile
its progress against what is actually committed on the build branch and resume at the
first task that is not yet complete — re-implementing or duplicating no task whose work is
already committed. A task whose implementation is committed but whose per-task review did
not complete is taken up at its review step (the existing commit kept and reviewed), never
re-implemented and never skipped. If the interruption fell during the whole-branch final
review (after the last task), then on relaunch the phase shall resume that review to a clean
result rather than treat "all tasks complete" as "build complete."
  - *Acceptance:* Given an interruption after task K's work was committed (whether or not
    its per-task review finished), when the run relaunches, then task K is not
    re-implemented and the branch gains no duplicate commits; and if task K's per-task
    review had not completed, its review runs over the existing commit before any later
    task starts. Given an interruption after the last task while the whole-branch final
    review had not reached a clean result, when the run relaunches, then the phase resumes
    the final review and does not report the build complete until that review is clean.

**UFR-8.** If the approved tasks doc contains no executable tasks, then the workhorse
phase shall finish without building and surface that there was nothing to build, rather
than produce an empty or spurious change.
  - *Acceptance:* Given a tasks doc with zero tasks, when the phase runs, then it makes
    no commits and reports "no tasks to build."

**UFR-9.** If a long build exhausts the run's context or hits a usage limit, then the
workhorse phase shall park at the last completed task and resume on relaunch, losing or
duplicating no committed work.
  - *Acceptance:* Given a build that hits a context or usage wall mid-run, when it parks
    and is relaunched, then it resumes at the next unbuilt task. (Graceful in-run
    self-management is out of scope — see Out of scope.)

**UFR-10.** If a second run targets the same work-item while a build is in progress, then
at most one run shall build the work-item at a time and a concurrent run shall never
corrupt the branch.
  - *Acceptance:* Given two runs on one work-item, when both attempt to build, then at
    most one proceeds and the branch is never corrupted by the other.

**UFR-11.** If, on entry or relaunch, the approved tasks doc's content no longer matches
the tasks the build branch was built for, or the tasks doc's approval has been withdrawn,
then the workhorse phase shall park rather than build further from divergent or
no-longer-approved intent. The mismatch is judged against the tasks doc's *content*, so a
content edit that leaves the review gate still reading `passed` is still caught.
  - *Acceptance:* Given a build interrupted after task K, when the tasks doc's content is
    edited (even if its gate still reads `passed`) or its approval is withdrawn before
    relaunch, then on relaunch the phase detects the mismatch and parks — it does not
    build task K+1 against the changed doc.

**UFR-12.** If, on relaunch, the build branch carries *uncommitted* leftover changes from
an interrupted task, then the workhorse phase shall reset only those uncommitted changes
before re-dispatching the task, and shall never discard a commit; a task whose work was
already committed is kept and taken up at its review step (UFR-7), not reset and not marked
complete without its review.
  - *Acceptance:* Given an interruption that left task K with uncommitted working-tree
    changes, when the run relaunches, then the phase clears those uncommitted changes and
    re-dispatches task K cleanly; and given task K's work was already committed, then that
    commit is kept (never discarded), task K is not rebuilt, and it is not marked complete
    until its per-task review has passed.

## Non-functional requirements

- **Auditability (outcome):** for the build phase, a reader of the run record can see,
  at each step, why it proceeded or parked — its gate, its confidence, and any material
  assumption (see Glossary). *Fit-criterion:* every build step appends a durable,
  structured record, and a material assumption or low confidence parks rather than
  proceeds.
- **Resumability (outcome):** an interrupted build resumes correctly from recorded state
  with no human re-sequencing. *Fit-criterion:* a kill-and-relaunch at any task boundary
  lands on the next unbuilt task with no duplicate commits.
- **Honesty (outcome):** the phase never reports a clean or complete build it did not
  achieve. *Fit-criterion:* every park or notice names the real cause; no "built" claim
  is emitted when a task was skipped, a review was unmet, or a write failed.
- **Cost discipline (outcome):** the model used for each reviewer and fixer matches that
  role's difficulty — the most-capable model tier for the whole-branch final reviewer, the
  code-fixer model tier for its fixer — rather than defaulting to the run's most expensive
  model everywhere. The per-task build worker is the deliberate exception: it follows SDD's
  own model heuristic and is **not** driven by the model-tier knob (the whole-branch loop is
  the knob's consumer here, the build worker is not). *Fit-criterion:* the run record names,
  per reviewer/fixer, the model tier it ran at — the whole-branch reviewer at the most-capable
  tier and its fixer at the code-fixer tier — while the build worker's model is recorded as
  SDD's choice, not a model-tier role.

## Definition of done / success

The owner can point the engine at one approved tasks doc and the workhorse phase builds
it end-to-end on its own: every task implemented test-first and reviewed (two verdicts),
a clean whole-branch final review, build provenance recorded over the handed-off commit,
and a reviewed branch handed to the rest of the pipeline — or, where it genuinely cannot
proceed, it parks with a clear, honest reason and resumes correctly on relaunch. The
throwaway-change stub is gone; the build phase does real work.

Success is demonstrated by a **live end-to-end build of a real, small approved tasks
doc** producing a reviewed branch with matching build provenance, plus unit coverage for
every judgement the phase makes (so its decisions — proceed, recover, park — are tested,
not hoped). The exact recovery and review-retry limits are tuned in the plan; the spec
fixes only that they are finite and that reaching them parks.

## Assumptions & dependencies

- An **approved tasks doc** (review gate `passed`) exists for the work-item, produced by
  the existing the-architect plan→tasks flow. The build phase *consumes* it; it does not
  author it.
- The **Workflow run spine (#21)** exists as the orchestrating engine (merged).
- The **managed build-worktree lifecycle (#77)** exists and is reused for the build
  worktree and branch's create–reclaim–reap (merged).
- The build engine's **existing capabilities carry over unchanged** — recording build
  evidence, checking branch freshness, the ship gate, crash-recovery/reconcile, and the
  managed build-worktree lifecycle. (Their internal shape is the plan's concern.)
- The per-task and whole-branch review discipline follows **superpowers
  subagent-driven-development (≥ 6.0, the single-task-reviewer flow)**, re-expressed as
  the run's control flow.
- The **shared review-and-fix loop (#104)** exists (merged) and is reused *as the
  whole-branch final review*; the per-task review reuses only its primitives, not the loop
  itself (see Constraints). The same loop is consumed by the front-half phases (#88) and
  the specialist panel (#89).
- The **specialist review panel (#89)**, **behavioral testing (#90)**, and the **live
  spec→PR integration** are separate work-items that consume this phase's output.

## Constraints

- **Orchestration lives in the run script, not in a worker.** A build worker is a
  single-purpose agent that does not dispatch its own sub-workers (CONVENTIONS §10.1); the
  per-task loop and the final review are the script's control flow, reusing the build
  libraries and the reviewers — never wrapped as one opaque worker.
- **The whole-branch final review reuses the shared review-and-fix loop (#104).** It is
  dispatched *through* that loop (`reviewPanel`) as a single generalist reviewer — a code
  leg (the verify gate runs) with no panel synthesis (one reviewer) — with the loop's round
  bound set equal to a per-task review's fixed maximum, and it parks on a `halted` or
  `cannot-certify` result like every leg of that loop (UFR-4). The generalist reviewer is
  injected at the most-capable model tier (there is no dedicated generalist model-tier role, so
  the model is set on the injected reviewer) and its fixer runs at the code-fixer model tier (see
  Cost discipline).
- **The whole-branch verify runs here and again downstream (#89).** The project's verify
  command is the whole-branch review's code-leg gate and runs again in the specialist panel;
  this double-run is intentional and accepted (per #104) — it is not suppressed.
- **The per-task review does NOT use the shared loop.** It stays the bespoke two-verdict
  (spec-compliance + code-quality) review with its own "cannot verify from the diff"
  handling (UFR-5), its own fixed maximum, and no synthesis. It reuses only the loop's
  primitives — the halt circuit-breaker (`circuit_breaker`), the Critical/Important blocking
  set, and the mandatory-continue gate (`loop_state`) — and is never routed through
  `reviewPanel`.
- **Durability is the substrate's, not the engine's** (§10.2). The phase reconciles its
  progress from recorded state on every entry and skips completed work; it takes no
  load-bearing launch arguments.
- **The phase never merges, never creates the PR, and never force-pushes** — those belong
  to later phases or the owner. The build follows the clipped contract: the worktree is
  pre-made and the phase stops before any branch-finishing step.
- **Auditability is structural** (§10.3): each step appends a durable record, and a
  material assumption or low confidence parks.

## Out of scope

- **Retiring the `/workhorse` command.** Workhorse is re-expressed as this phase; the
  standalone command stays the working producer until the showrunner runs spec→PR live (a
  later work-item). This spec records the *direction*, not the removal.
- **The specialist 5-reviewer review-code panel + auto-fix loop (#89).** This phase runs
  per-task reviews plus one generalist whole-branch final review (through the shared loop,
  ordered before #89) and hands off; the specialist panel is the separate downstream gate.
- **Behavioral testing, PR creation, CI / freshness / ship gating, and the handoff
  readout** — later showrunner phases (#90 and ship).
- **Graceful in-run self-management of context (#23) and usage limits (#24).** A long
  build that hits a wall parks and resumes on relaunch; it does not self-pace or compact
  in place.
- **The owner-facing model-tier knob for build workers.** Workers run on a per-role model
  appropriate to each task (see Cost discipline), but an owner-facing knob to override
  those tiers is not wired here.
- **The exact numeric recovery and review-retry limits.** The spec requires they are
  finite and that reaching them parks; the specific values are tuned in the plan.
- **The multi-issue queue / controller (#22)** and the **front-half phases going native
  (#88)** — unrelated to this single-work-item build phase.

## Glossary

- **Workhorse phase:** the showrunner's build phase — the re-expressed Workhorse; the
  heavy-lifting leg that turns an approved tasks doc into a reviewed, committed branch.
- **The showrunner:** the run engine that drives one approved-spec work-item through the
  whole pipeline (plan → … → build → review → PR → CI) to a parked, merge-ready PR.
- **Task:** one checkbox step in the approved tasks doc — a test-first unit of work.
- **Complete (a task):** a task is *complete* only when its implementation is committed,
  its per-task review has passed (both verdicts), and that is recorded. A
  committed-but-unreviewed task is not complete.
- **Build worker / per-task reviewer:** the single-purpose agents the run script
  dispatches to implement and to review each task.
- **Shared review-and-fix loop:** the reusable review → fix → re-review-to-clean control
  flow #104 shipped (`reviewPanel`), consumed here as the whole-branch final review and
  also by the front-half phases (#88) and the specialist panel (#89). Configured for the
  whole-branch review as a single generalist reviewer (no panel synthesis) running the
  project verify command as its code-leg gate; it parks on a `halted` or `cannot-certify`
  result. The per-task review reuses only this loop's primitives, not the loop itself.
- **Park:** stop and surface for a human, leaving recorded state so a relaunch resumes;
  the engine never proceeds past a material assumption or low confidence.
- **Material assumption:** a genuine unverified premise the phase would have to *assume*
  to proceed — one whose being wrong would change what gets built or shipped — as opposed
  to a routine status note. A material assumption parks; a status note does not.
- **Low confidence:** the phase's own signal that it cannot reach a well-supported
  decision on a step without assuming something it has not verified. Like a material
  assumption, low confidence parks rather than proceeds.
- **Build provenance:** the durable record that the build genuinely ran — the engine used
  and the exact commit X the build handed off. It is the first half of the ship gate: it
  attests the build ran over X, not over whatever commit is eventually shipped. A later
  downstream fix (#89) may move the branch tip past X; that phase attests review over the new
  tip and does not re-stamp this build provenance.

## Coverage

| Area | Disposition | Where / why |
| --- | --- | --- |
| Empty & first-run | Specify | UFR-8 (zero-task doc); FR-2 (first build sets up the worktree/branch) |
| Invalid & malformed input | Specify | UFR-1 (un-gated or unreadable tasks doc); UFR-11 (tasks doc changed / approval withdrawn before resume) |
| Boundaries & limits | Specify | UFR-3 (bounded worker recovery); UFR-4 (bounded review retry — per-task and final); UFR-9 (context/usage wall); FR-11 + UFR-7 (per-task resume). Exact limit values are Defer-to-plan. |
| Errors & failures | Specify | UFR-2 (worktree setup); UFR-3 (stuck worker); UFR-6 (durable-write failure); UFR-12 (partial-commit reconciliation on resume) |
| Access & permissions | N-A | The build phase makes local commits only; GitHub access, PR, and merge belong to later phases and are gated there |
| Duplicates & double-actions | Specify | UFR-7 (no re-dispatch / no duplicate commits on resume); UFR-12 (resets a partially-built task before re-dispatch) |
| Conflicting / simultaneous use | Specify (promise) / Defer-to-plan (mechanism) | UFR-10 states the owner-visible promise (at most one run builds; no branch corruption); the exclusion mechanism (run lease/fence) is the plan's |
| Misuse & abuse | N-A | No money or private-data surface in the build phase |
| Reach (i18n / a11y) | N-A | Non-user-facing infrastructure; the only operator surface is text (run state, logs, readout) |
