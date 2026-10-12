---
superheroes: doc
schemaVersion: 1
docType: spec
workItem: unattended-safe-permission-posture-for-showrunner-7ff048
issue: 149
size: medium
status: approved
gates: {review: passed}
approved: "2026-07-03"
producedBy: "the-architect@0.5.0"
created: "2026-07-03"
updated: "2026-07-03"
---
# Unattended-safe permission posture for showrunner runs

## Purpose

Live showrunner runs stall for hours when a leaf's action trips a permission prompt while
the owner is away — most recently a 7h33m overnight hold on a single improvised verification
probe. The safety behavior is correct (unrecognized actions ask the owner), but the cost is
wrong: an unanswered question should cost minutes of visible quality degradation, not hours
of wall-clock. This work defines a curated permission posture for showrunner runs so that
routine, known-safe leaf actions never prompt at all, an improvised action that does prompt
resolves itself within a bounded time, and the owner-role safety floor keeps hard-blocking
throughout.

## Who it's for

- **The owner** (the repo's single operator), who launches showrunner runs and walks away —
  overnight or during the day — and needs them to finish without babysitting, while keeping
  the guarantee that nothing merges, releases, or rewrites shared history without their
  live approval.

## Functional requirements

**FR-1.** While a showrunner run is active, when a leaf's action awaits owner permission and
receives no response for 15 minutes, the system shall deny that action and let the leaf
continue its work.
  - *Acceptance (Given-When-Then):* Given an active showrunner run with the owner absent,
    when a leaf's action sits awaiting permission for 15 minutes, then the action is denied,
    the leaf proceeds without it, and the run spends no further wall-clock waiting on that
    request.
  - *Acceptance (rule):* the timeout denial is scoped per run — with two runs active at
    once, a denial in one run affects only that run's own leaf actions.
  - *Acceptance (rule):* a denial is final for the denied step — the leaf whose action was
    denied does not re-attempt it into a new permission wait, in any rewording, and the step
    concludes per FR-2/UFR-6 (FR-2's single deeper retry for a verification check is the one
    exception). A later, distinct step that independently needs a similar action may ask
    afresh; each such ask is itself bounded by this requirement and falls within the accepted
    several-prompts residual (see Assumptions). Step identity follows the work assigned, not
    the agent instance — re-dispatching the same denied work under a fresh leaf is a
    re-attempt, not a distinct step.

**FR-2.** When a verification check's action is denied under FR-1, the system shall record
that check as low-confidence in the run's existing quality records, so the review loop
schedules a deeper retry or reports the affected dimension as degraded.
  - *Acceptance (Given-When-Then):* Given a reviewer leaf whose verification probe was
    denied by the 15-minute timeout, when the review round completes, then the run's quality
    records show that check at reduced confidence and the loop's existing degraded-check
    response (deep retry or a flagged dimension) is triggered — the cost is a visible quality
    note, not a stalled run.
  - *Acceptance (rule):* the degraded-check response is itself bounded — a check whose
    deeper retry is also denied is reported as a degraded dimension (the main clause's
    outcome) and not retried again; a single check never cycles through repeated
    retry-and-deny rounds.

**FR-3.** While no showrunner run is active, the system shall leave permission prompting
unchanged — no timeout denial applies in interactive sessions.
  - *Acceptance (rule):* a permission prompt raised in an ordinary interactive session with
    no showrunner run active waits indefinitely for the owner, exactly as today.

**FR-4.** Reviewer-leaf instructions shall direct verification probes onto the already-allowed
route: write a throwaway test file inside the managed build worktree and run it via the
allowed test-run family, instead of improvised inline interpreter code.
  - *Acceptance (rule):* the reviewer-leaf instructions name the throwaway-test-file route as
    the required probe shape and explicitly discourage inline interpreter code as a probe.

**FR-5.** When a command's working directory resolves to a managed build worktree under
`~/.superheroes-worktrees/`, the system shall run interpreter invocations without prompting.
  - *Acceptance (Given-When-Then):* Given a showrunner leaf in a managed build worktree,
    when it runs an improvised interpreter invocation (for example inline script text) with
    that worktree as its working directory, then the invocation runs without a permission
    prompt.
  - *Note (deliberate pairing with FR-4):* FR-4 sets the norm and FR-5 is the safety net for
    the same action — reviewer instructions steer probes onto the test-file route so fewer
    improvised invocations happen at all, and when a leaf improvises one anyway, FR-5 keeps
    it from stalling the run. The two requirements point opposite directions on purpose.

**FR-6.** The project shall carry an owner-curated set of permission rules — stored with the
project's out-of-repo configuration, leaving no artifact in the repository — that allow the
routine command families a showrunner run uses (test runs, the repo's three validators,
version-control operations confined to managed build worktrees, and draft pull-request
creation and editing) without prompting.
  - *Acceptance (Given-When-Then):* Given the configured rules, when a full showrunner run
    executes commands from the enumerated routine families, then none of those commands
    raises a permission prompt.
  - *Acceptance (rule):* the rules take effect in every session and managed build worktree
    of this project without requiring any file in the repository or its checkouts.
  - *Acceptance (rule):* the allowed version-control family excludes the owner-role gated
    set (merge, release, workflow run, force-push, push to the default branch), which keeps
    its UFR-1 behavior in full.
  - *Acceptance (rule):* the pull-request family covers creating a draft pull request,
    editing its title, body, and metadata, and the pipeline's draft-to-ready promotion (an
    intended pipeline step); changing a pull request's base branch is not in the family and
    follows the normal permission path.

**FR-7.** The routine-family allow set shall be grounded in an audit of which permission
prompts actually fire during a full showrunner run.
  - *Acceptance (rule):* an audit record — kept with the project's out-of-repo
    configuration — lists the prompt-provoking commands observed in a full run, and every
    routine command family in it maps to either an allow rule or a recorded decision to
    keep prompting.

**FR-8.** When the spine composes a command for a leaf, the system shall run that exact
command without prompting.
  - *Acceptance (Given-When-Then):* Given a command the spine composed for a leaf in the
    current run, when the leaf runs it exactly as composed, then it runs without a permission
    prompt.
  - *Acceptance (rule):* a command differing in any character from what the spine composed is
    not covered by this allowance and follows the normal permission path.
  - *Acceptance (rule):* the allowance applies only within the run that composed the command —
    a composed command from one run confers no allowance in another session or run.

**FR-9.** The owner shall be able to view and change the project's permission rules through
the band's configuration front door (the configure command).
  - *Acceptance (Given-When-Then):* Given a project with the posture set up, when the owner
    opens the configuration front door, then the full allow set is visible in one place and
    each rule can be changed or removed there.
  - *Acceptance (rule):* the configuration front door is the sanctioned path for changing
    the rules (UFR-9 governs what a change outside it can and cannot do).

## When things go wrong (significant unhappy paths)

**UFR-1.** If an action falls in the owner-role gated set (merge, release, workflow run,
force-push, push to the default branch), then the system shall block it pending live owner
approval regardless of any allowance introduced by this work.
  - *Acceptance (Given-When-Then):* Given every allowance from FR-5/FR-6/FR-8 in place, when
    a leaf attempts an owner-role action by any covered route, then the action is blocked for
    live owner approval exactly as before this work — and the FR-1 timeout denies it rather
    than approving it if the owner does not respond.

**UFR-2.** If any part of the new allowance machinery fails — including an unreadable or
corrupt rules store — or cannot evaluate a command, then the system shall fall back to
asking the owner — never to allowing.
  - *Acceptance (Given-When-Then):* Given a command that would normally be auto-allowed, when
    the allowance machinery errors or cannot reach a decision, then the command follows the
    normal permission-prompt path (and the FR-1 timeout still bounds the wait during a run).

**UFR-3.** If an action is denied by the FR-1 timeout, then the run's readout shall state the
denial — what was denied and which step or check it affected.
  - *Acceptance (rule):* a run in which one or more timeout denials occurred produces a
    readout naming each denied action and the affected step or check; a timeout denial never
    appears as a silent skip or a pass.

**UFR-4.** If the owner responds to a permission request after the 15-minute denial has
already fired, then the system shall not apply that response to the already-denied action.
  - *Acceptance (Given-When-Then):* Given an action denied at the 15-minute mark, when the
    owner approves it afterward, then the denied action is not retroactively run and the late
    response causes no error; the run's state reflects the denial.

**UFR-5.** If a command is dressed up to look managed-worktree-scoped through path tricks
(symbolic links, parent-directory segments, or similar), then the system shall not grant it
any worktree-scoped allowance — neither FR-5's interpreter allowance nor FR-6's
worktree-confined version-control allowance.
  - *Acceptance (Given-When-Then):* Given a command whose stated working directory or target
    only appears to be a managed build worktree via a symbolic link or parent-directory hop,
    when it is evaluated, then it is not auto-allowed and follows the normal permission path.

**UFR-6.** If a leaf action that is not a verification check (for example a builder step) is
denied by the FR-1 timeout, then the system shall report the affected step as incomplete —
never as successfully completed.
  - *Acceptance (Given-When-Then):* Given a builder leaf whose substantive action was denied
    by the 15-minute timeout, when that leaf's step concludes, then the run's records show
    the step as incomplete or failed (with the denial named per UFR-3), and nothing downstream
    treats the step as done.

**UFR-7.** If the run's machinery is interrupted (a crash or a machine restart) while a
permission request is pending, then on resumption the system shall treat that pending
request as denied — an interruption shall never convert a pending request into an
allowance, and never into additional waiting.
  - *Acceptance (Given-When-Then):* Given a permission request pending when the run's
    machinery stops, when the run resumes, then the affected action has not silently
    executed and is treated as denied (disclosed per UFR-3, absorbed per FR-2 or UFR-6);
    no new wait window opens for that request.

**UFR-8.** If a run concludes with any step reported incomplete under UFR-6, then the
system shall not present the run's pull request as ready for review.
  - *Acceptance (Given-When-Then):* Given a run in which a builder step was denied and
    reported incomplete, when the run hands back, then the pull request remains a draft and
    the readout names the incomplete step(s) as the reason. (Degraded verification checks
    under FR-2 do not block the handback — they remain disclosure-plus-retry.)

**UFR-9.** If the project's permission rules are modified during a run, then the
modification shall have no effect on that run's allowances.
  - *Acceptance (Given-When-Then):* Given the rules change mid-run, when subsequent commands
    in that run are evaluated, then they are judged against the rules as they stood at run
    start, unaffected by the change.
  - *Acceptance (rule):* an allowance-rule change becomes effective only through the owner's
    configuration front door (FR-9) — rule state that cannot be traced to a front-door
    change is ignored, and evaluation the ignored rules would have covered falls back to
    prompting, never to allowing.
  - *Acceptance (rule):* a direct edit to the rules — whether refused outright or landed on
    disk — therefore never changes the effective rules of any run; it can become effective
    only if the owner later adopts it through the front door themselves.

## Non-functional requirements

- **Unattended completion (the headline outcome):** a full showrunner run with the owner
  absent throughout never waits more than 15 minutes on any single permission request; a
  longer wait on one request is a defect. The bound is per request — a run's total
  permission-wait is deliberately not separately capped (see Assumptions: the owner accepts
  the residual repeated-prompt risk).
- **Safety (unchanged bar):** no owner-role action taken through the run's own command
  machinery executes without the owner's live approval — before, during, and after this
  work. Code executing *inside* an already-allowed invocation sits outside this floor's
  reach; that residual is owner-accepted and disclosed (see Assumptions).
- **Auditability:** the standing allowed surface is inspectable in one place through the
  configuration front door (FR-9), and every automatic allowance or timeout denial made
  during a run is visible in that run's records.

## Definition of done / success

An overnight, owner-absent showrunner run (the kind that previously sat 7+ hours on one
prompt) completes end-to-end: routine and spine-composed commands never prompt; reviewer
instructions steer probes onto the allowed test-file route (FR-4); any prompt that does fire
self-resolves within 15 minutes into a visible incomplete-step or low-confidence note the
run absorbs; the readout discloses every timeout denial; and the owner-role floor blocked
nothing less — and nothing more — than before.

## Assumptions & dependencies

- The owner-role enforcement floor (the deny/gate set for merge, release, workflow run,
  force-push, push-to-default) is in place and stays authoritative — this work's allowances
  are acceptable *because* that floor exists.
- The review loop's existing receipt handling can absorb a denied verification probe as a
  low-confidence result and respond with a deeper retry or a degraded-dimension report
  (FR-2 relies on it).
- Spine-composed commands are deterministic and stable in form for a given run, making
  exact-match allowance (FR-8) meaningful.
- An auto-allowed improvised invocation (FR-5) is not confined by its working directory — it
  can reach the network and paths outside the worktree, exactly like an allowed test run.
  The owner accepts that reach knowingly (decided at discovery); the enforced boundary is the
  owner-role floor (UFR-1), not the working directory.
- Owner notification needs no new work: the Claude app's existing push notifications already
  reach the owner when a run is waiting on permission.
- There is no separate cap on a run's total permission-wait: with the allow rules in place,
  prompts are expected to be rare, and the owner accepts the residual risk that several
  distinct prompts in one run each cost up to 15 minutes (decided at review). Every such
  denial stays visible in the readout (UFR-3), so a run that prompts repeatedly is a posture
  gap to fix by extending the allow rules — not a silent failure.
- Rule changes propagate at run boundaries in both directions: just as a mid-run change
  confers nothing on the running run (UFR-9), an owner-applied *narrowing* also takes effect
  at the next run — the owner's immediate lever for a run already in flight is stopping the
  run itself. Accepted as a residual of the frozen-snapshot design.
- The owner-role floor operates on the commands the run itself issues; it is not a sandbox.
  Code running inside an already-allowed invocation (an improvised interpreter run, a test
  file) could in principle take actions the floor would have gated on the command level —
  the owner accepts this residual knowingly (decided at review), noting it is inherent to
  allowing any code execution at all and is not widened in kind by this work.

## Constraints

- No broad skip-permissions mode: the posture is built from scoped allowances plus bounded
  degradation, never from turning permission checking off.
- The permission posture leaves no artifact in the repository: rules and audit records live
  with the project's out-of-repo configuration. The rules apply to this project's sessions
  and managed build worktrees on the owner's machine (per-machine, not travelling with the
  repository — the owner accepts that); the timeout-denial behavior, by contrast, is
  confined to active showrunner runs (FR-3).
- This work must not weaken, narrow, or bypass the owner-role floor in any code path.

## Out of scope

- New notification channels or notification wiring (descoped: the Claude app already pushes).
- Changes to the host harness itself (Claude Code); everything here rides on existing
  extension surfaces.
- Generic dangerous-command detection (destructive-command patterns and similar) — a
  deliberate prior decision keeps that out of the deterministic layer.
- Non-Claude hosts (the Codex-side permission flow is untouched).
- Retrofitting the posture to other repos or a plugin-wide default; this defines it for this
  project's showrunner runs.

## Glossary

- **Run** — one live showrunner execution of one work-item, from launch to handback (or
  stop), with its own durable identity; permission allowances and denials are bookkept
  against the run they belong to.
- **Leaf** — a single delegated agent step inside a showrunner run (a reviewer, builder, or
  courier doing one bounded job).
- **Spine / composed command** — the deterministic orchestration layer of a run; a *composed
  command* is a command the spine writes out verbatim for a leaf to execute.
- **Managed build worktree** — a throwaway working copy the run creates under
  `~/.superheroes-worktrees/` for build and verification work.
- **Owner-role floor** — the standing enforcement that merge, release, workflow-run,
  force-push, and push-to-default actions always require the owner's live approval.
- **Improvised probe** — verification code a reviewer invents on the spot to prove a finding
  (as opposed to a composed command); by design it cannot be known in advance.
- **Readout** — the end-of-run summary the owner reads to judge what the run did and how much
  to trust it.

## Coverage

| Area | Disposition | Where / why |
| --- | --- | --- |
| Empty & first-run | N-A | a project or machine not yet configured simply has no rules — every action follows today's normal permission path (safe by default), at first setup and on any additional machine alike; nothing to design |
| Invalid & malformed input | Specify | UFR-2 — an unevaluable command falls back to prompting, never to allowing |
| Boundaries & limits | Specify | UFR-4 — an owner response landing after the 15-minute boundary is not applied retroactively; the per-request-only bound (no run-total cap) is stated in the NFR and accepted in Assumptions |
| Errors & failures | Specify | UFR-2 (machinery failure fails toward prompting), UFR-3 (denials are disclosed, never silent), UFR-6 (a denied non-verification step is reported incomplete, never successful), UFR-7 (a crash/restart mid-wait resolves to a denial, never an allowance or more waiting), UFR-8 (incomplete steps keep the handback a draft) |
| Access & permissions | Specify | UFR-1 — the owner-role floor overrides every allowance introduced here, scoped to the run's own commands (the transitive-code residual is owner-accepted in Assumptions) |
| Duplicates & double-actions | Specify | FR-8 rule — a composed-command allowance is exact-match and scoped to its own run, so it cannot be replayed |
| Conflicting / simultaneous use | Defer-to-plan | owner-visible promise: one run's allowances and denials never leak into another concurrent run or session (FR-8 rule; FR-1 per-run rule); the isolation mechanism is the plan's |
| Misuse & abuse | Specify | UFR-5 (path tricks do not earn the worktree allowance) and UFR-9 (mid-run rules edits do not broaden the running allowances), with UFR-1 as the backstop |
| Reach (i18n / a11y) | N-A | single-owner internal tooling; no language, currency, or assistive-tech surface |
