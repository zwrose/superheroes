---
superheroes: doc
schemaVersion: 1
docType: spec
workItem: codex-and-cursor-as-review-and-build-engines-5b60ca
issue: 38
size: large
status: approved
gates: {review: passed}
producedBy: "the-architect@0.3.0"
created: "2026-06-29"
updated: "2026-06-30"
---
# Codex and Cursor as review and build engines

## Purpose

Today the band runs every role on a single engine (Claude). The #38 spike proved
two things by experiment: a review pass from a **different model family** is a real
safety net — it caught a Critical path-traversal bug the band's standard reviewer
missed — and external engines (**Codex** and **Cursor**) are capable implementers.
This work makes the band's two working roles — **reviewing** code and **building**
it — *engine-aware*, so an owner can choose Codex or Cursor (alongside Claude) for
each role, independently. The payoff: a cross-family review surfaces bugs a single
family misses, and the owner gains a real choice of engine — for cost, capability, or
diversity — when building.

## Who it's for

- **The band maintainer**, running superheroes on this and other repos, who wants a
  different-family review safety net and the option to build on an external engine.
- **Any superheroes user** who has Codex and/or Cursor installed and signed in and
  wants to bring one or both into the development loop, while leaving Claude as the
  default for anyone who doesn't.

## Functional requirements

**FR-1.** Where the owner sets an engine preference, the system shall record a
**reviewer engine** and an **implementation engine** independently, each chosen from
Claude, Codex, or Cursor.
  - *Acceptance (Given-When-Then):* Given a project, when the owner sets the reviewer
    engine to Codex and the implementation engine to Cursor, then both are saved and a
    later read returns exactly those two values, each independent of the other.

**FR-2.** Where no engine preference is set for a role, the system shall use Claude
for that role.
  - *Acceptance (rule):* a project with no engine preference runs both review and
    build on Claude.

**FR-3.** When the reviewer engine is Codex or Cursor, the system shall run the
code-review panel on that engine, producing findings in the same form the Claude panel
produces. (That the review-and-fix loop behaves identically regardless of engine is the
review-parity outcome below.)
  - *Acceptance (each external engine):* Given the reviewer engine is Codex — and,
    separately, Cursor — and a branch seeded with a known path-traversal defect (a file
    path built from unsanitized input that escapes its intended directory — the exact
    fixture is the plan's), when review runs, then on each engine the panel reports that
    defect as a Critical finding in the standard findings form.

**FR-4.** When the implementation engine is Codex or Cursor, the system shall perform
the build role's work — writing the change and making mechanical fixes — on that engine.
  - *Acceptance (build, each external engine):* Given the implementation engine is
    Cursor — and, separately, Codex — when a task is built, then the code changes are
    produced by that engine and land on the work-item's branch.
  - *Acceptance (mechanical fix, each external engine):* Given the implementation engine
    is Cursor — and, separately, Codex — when a mechanical fix is applied during the run,
    then that fix is produced by that engine.

**FR-5.** When an external engine completes an implementation change — a build or a
mechanical fix — the system shall require the result to pass the project's verify command
before the change is accepted.
  - *Acceptance (build):* Given the implementation engine is Codex and a build that
    passes, when the build completes, then the verify command is run on the result and, on
    success, the change is accepted and the run continues.
  - *Acceptance (mechanical fix):* Given the implementation engine is Cursor and an
    external mechanical fix (for example review-code's auto-fix), when the fix is applied,
    then it is accepted only if the result passes the verify command — a fix that would
    leave verify failing is not accepted.

**FR-6.** When an external engine performs an implementation, the system shall record it
in the work-item's audit log — naming the engine, the model or effort setting it ran at,
and the outcome — with an entry for each external implementation action (the build and
each mechanical fix).
  - *Acceptance (rule):* after an external build, the work-item's audit log contains an
    entry for the external implementation step naming the engine, the model/effort it ran
    at, and the result; a mechanical fix made by the engine is recorded the same way.

**FR-7.** While an external engine is reviewing, the system shall not let it modify
the code under review.
  - *Acceptance (Given-When-Then):* Given an external review run, when the review
    completes, then the working tree is unchanged from before the review.

**FR-8.** While an external engine is implementing — building or applying a mechanical
fix — the system shall confine its changes to the work-item's own isolated build
workspace.
  - *Acceptance (build):* Given an external build, when it runs, then its changes appear
    only in the work-item's build workspace and branch, and no other checkout on the
    machine is affected.
  - *Acceptance (mechanical fix):* Given an external mechanical fix, when it runs, then
    its changes appear only in the work-item's build workspace and branch, and no other
    checkout is affected.

**FR-9.** Where an engine exposes more than one depth or effort setting, the system
shall select the setting matched to the work — a heavier setting for the
reasoning-heavy work of reviewing and building, a lighter one for mechanical fixes — by
default, and the owner can override it through configure (alongside the engine preference). For
Codex, the default is a high reasoning-effort
setting for reviewing and building and a low one for mechanical fixes. (The exact model
identifiers behind those settings are the plan's.)
  - *Acceptance (rule):* given Codex is the reviewer engine with no override, a review
    runs Codex at its high-effort default; given Codex is the implementation engine with
    no override, a build runs at the high-effort default and a mechanical fix at the
    low-effort default; in each case the audit log (FR-6) records the effort it ran at,
    and an owner override replaces that default. An engine that exposes only one model
    (Cursor — see FR-10) is exempt and uses that one model throughout.

**FR-10.** Where the chosen engine is Cursor, the system shall use Cursor's composer
model for both roles. (Other Cursor models are out of scope; an owner who wants something
other than composer chooses a different engine via the engine preference, FR-1.)
  - *Acceptance (rule):* with Cursor selected, both the review and the build run on
    Cursor's composer model, and no other Cursor model is selectable.

**FR-11.** When the owner configures the band, the system shall report whether Codex
and Cursor are each installed and signed in.
  - *Acceptance (Given-When-Then):* Given Codex is installed and signed in and Cursor
    is not signed in, when the owner runs configure, then it shows Codex as ready and
    Cursor as not-ready, with what to fix for the not-ready one.

**FR-12.** When the owner configures the band, the system shall record the owner's
per-role engine preference.
  - *Acceptance (Given-When-Then):* Given the owner picks reviewer = Codex and
    implementation = Claude in configure, when configure finishes, then those
    preferences are saved and drive later runs.

**FR-13.** When the owner chooses an external implementation engine that needs the
one-time build authorization — the single grant that lets that engine write autonomously,
for both builds and mechanical fixes — the system shall show the owner the specific
authorization to grant and where, and shall not apply it for them.
  - *Acceptance (Given-When-Then):* Given the owner selects Cursor for implementation
    and the build authorization is not yet granted, when configure runs, then it
    displays the exact authorization the owner must add and its location, and waits for
    the owner to grant it rather than adding it itself.

**FR-14.** After the owner grants the build authorization, the system shall run a test
dispatch to the chosen engine and report whether it succeeded before the engine is
relied on.
  - *Acceptance (success):* Given the owner has just granted the Cursor build
    authorization, when configure continues, then it runs a test dispatch to Cursor and
    shows the owner whether it succeeded.
  - *Acceptance (failure):* Given the test dispatch to Cursor fails, when configure
    reports the result, then it tells the owner Cursor is not yet working and that builds
    and mechanical fixes will fall open to Claude until it is — it does not present Cursor
    as ready.
  - *Acceptance (no response):* Given the test dispatch to Cursor does not complete within
    the same configurable time limit as UFR-5, when the limit is reached, then configure
    stops waiting, reports that Cursor did not respond (distinct from a failed dispatch),
    and leaves Cursor not-ready with a retry instruction.

**FR-15.** When the implementation engine is Codex or Cursor, the mechanical fixes that run
on it (FR-4) shall include the auto-fix review-code applies to address its own findings — so
a review finding is resolved by a fix written on the implementation engine. (The review
itself stays on the reviewer engine, read-only — FR-3, FR-7.)
  - *Acceptance (Given-When-Then):* Given the reviewer engine is Codex and the
    implementation engine is Cursor, when review-code finds an issue and applies its
    auto-fix, then the review is performed by Codex (read-only) and the fix is written by
    Cursor.

## When things go wrong (significant unhappy paths)

**UFR-1.** If a configured engine cannot be used for its role — unknown, not installed,
not signed in, or unable to run as configured (for example a model override the engine
rejects) — then the system shall use Claude for that role and show a single non-blocking
notice naming the cause, without stopping the review or the build.
  - *Acceptance (not installed):* Given the implementation engine is Codex but Codex is
    not installed, when a build runs, then it runs on Claude, one notice is shown, and the
    run completes normally.
  - *Acceptance (rejected model override):* Given the implementation engine is Codex with
    an owner model override that Codex rejects, when a build runs, then it runs on Claude,
    a notice names the rejected override, and the run completes.

**UFR-2.** If a chosen engine fails or stalls part-way through a review, a build, or a
mechanical fix, then the system shall discard any partial work that engine left, fall back
to Claude for that unit of work from a clean starting state, and show a single
non-blocking notice.
  - *Acceptance (build):* Given the implementation engine is Cursor and Cursor fails
    mid-build after leaving partial edits, when the failure occurs, then those partial
    edits are discarded, the build is redone on Claude from the pre-build state, one notice
    is shown, and the loop is not blocked.
  - *Acceptance (review):* Given the reviewer engine is Cursor and Cursor crashes
    mid-review, when the failure occurs, then any partial output is dropped, the review is
    redone on Claude, one notice is shown, and the loop is not blocked.
  - *Acceptance (mechanical fix):* Given the implementation engine is Cursor and Cursor
    fails or stalls part-way through a mechanical fix after leaving partial edits, when the
    failure occurs, then the partial fix is discarded, the fix is redone on Claude from the
    pre-fix state, one notice is shown, and the loop is not blocked.

**UFR-3.** If an external engine's implementation runs the project's verify command and
does not pass it, then the system shall refuse the change and stop the run for the owner
rather than hand back a broken result; and if the verify command cannot be run at all,
the system shall stop the run with a notice that says so, distinct from a failed build.
  - *Acceptance (verify failed):* Given an external build whose result fails verify, when
    verify fails, then no change is accepted, the pull request is left in draft, and the
    owner is notified that the build failed verify.
  - *Acceptance (verify unrunnable):* Given the verify command cannot be executed, when
    the build reaches verification, then the run stops with a notice that the verify
    command could not run — not that the build failed.
  - *Acceptance (mechanical fix):* Given an external mechanical fix whose result fails
    verify, when verify fails, then the fix is not accepted and the run stops for the owner
    with the pull request left in draft — the same fail-closed outcome as a build that
    fails verify. (A fix that instead crashes or stalls before completing is the fall-open
    case — UFR-2.)

**UFR-4.** If the one-time authorization that lets an external engine write autonomously
is not in place, then the system shall make no external implementation write — both builds
and mechanical fixes run on Claude instead — and tell the owner how to enable external
building, without blocking the run.
  - *Acceptance (build):* Given the implementation engine is Cursor but the build
    authorization has not been granted, when an unattended build runs, then it runs on
    Claude, the owner is told what to enable, and the run completes.
  - *Acceptance (mechanical fix):* Given the implementation engine is Cursor but the build
    authorization has not been granted, when a mechanical fix would otherwise run on Cursor,
    then it runs on Claude instead, the owner is told what to enable, and the run completes.

**UFR-5.** If a chosen engine starts but stops responding — neither finishing nor
erroring — for longer than a finite time limit, then the system shall stop waiting on it,
fall back to Claude for that unit of work, and show a single non-blocking notice. The
limit is always finite (a stalled engine is never waited on forever); its exact default is
the plan's, and it is configurable.
  - *Acceptance (test-settable):* Given the reviewer engine is Cursor and the stall time
    limit is set to a short value, when Cursor stalls past that limit, then that work is
    completed on Claude with a notice and the run is never left hanging.
  - *Acceptance (finite default):* Given no configured override, when an engine stalls,
    then it is still abandoned after the finite default limit — the wait is never
    unbounded.

**UFR-6.** If the system cannot record an external implementation run in the work-item's
audit log, then it shall not accept the change and shall stop the run for the owner
rather than proceed unaudited.
  - *Acceptance (Given-When-Then):* Given an external build whose audit-log entry cannot
    be written, when the write fails, then the change is not accepted, the run stops for
    the owner, and the pull request is left in draft.

**UFR-7.** If an external review does not yield complete, readable findings — empty
output, output that cannot be read into the standard findings form, or an incomplete panel
(one or more required review dimensions missing or unreadable) — then the system shall
treat that review as a failure, not a clean pass, and re-run it on Claude, with the Claude
findings driving the review-and-fix loop, and a notice.
  - *Acceptance (unreadable):* Given the reviewer engine is Cursor and Cursor returns
    unreadable review output, when the output cannot be read into the standard findings
    form, then the review is re-run on Claude, the Claude review's findings become the
    authoritative result driving the review-and-fix loop, the original is not recorded as
    "no issues found", and a notice is shown.
  - *Acceptance (partial panel):* Given the reviewer engine is Cursor and one or more
    required review dimensions return missing or garbled output, when the panel is
    incomplete, then that external review is discarded, the review is re-run on Claude, the
    Claude findings drive the loop, and it is not recorded as a clean pass.

## Non-functional requirements

- **Auditability (outcome):** every external implementation run is verify-gated and
  recorded in the audit log, which names the engine, the model/effort, and the verify result
  for each external action (the build and each mechanical fix). Fit-criterion: no external
  implementation action — build or mechanical fix — executes without a recorded engine,
  model/effort, verify result, and outcome; none execute outside that gate.
- **Fail-open posture (outcome):** the *choice* of engine never blocks or crashes a
  run; an unknown, missing, or non-responsive engine degrades to Claude. Fit-criterion:
  no run can hang or hard-fail because of which engine was selected or whether it was
  available. This governs engine selection and availability only. A completed external
  result that is unsound or unverifiable is held to the opposite, fail-closed bar: a build
  or mechanical fix that fails or cannot run the verify command (UFR-3), or a run that
  cannot be audited (UFR-6), stops the run, and a review whose findings are unreadable or
  incomplete (UFR-7) is re-run on Claude rather than accepted. The common rule: no unsound, unverified, unaudited, or unreadable external
  result is ever silently accepted as good.
- **Review parity (outcome):** external review findings are in the same form as
  Claude's and flow through the same review-and-fix loop unchanged. Fit-criterion: an
  external reviewer's findings enter the loop in the identical findings form (FR-3) and
  drive the same compile/triage/auto-fix steps — visible in the run's audit log — as a
  Claude review of the same branch.
- **Configuration determinism (outcome):** an engine's model and depth are set
  explicitly by the band, not read from the developer's personal command-line
  configuration. Fit-criterion: given a personal CLI configuration that would default the
  engine to a different model, the audit log (FR-6) shows the band's explicitly-set model
  and effort were used, not the personal default.
- **Authorization is owner-only (security outcome):** enabling an external engine to
  write autonomously — a build or a mechanical fix — requires an explicit owner action;
  configure surfaces the authorization for the owner to grant and never applies it for them
  (FR-13). Fit-criterion: when an external implementation engine is selected but the build
  authorization has not been granted, no external implementation write happens — builds and
  mechanical fixes both run on Claude (UFR-4) — and external writing proceeds only after the
  owner has granted the authorization.
- **Secret hygiene (security outcome):** any text an external engine emits that the band
  surfaces to the owner or to a pull request (error output, notices, results) is
  secret-scrubbed by the band's existing scrubbing before it is shown — an external
  producer gets no exemption. Fit-criterion: a secret present in external-engine output
  never reaches a pull-request comment or an owner notice in the clear.

## Definition of done / success

The work is done when an owner can, end-to-end:

- Set reviewer = Codex and implementation = Cursor and have both drive live runs; and
  set an unknown or unavailable engine and watch it fall open to Claude with a notice
  while both loops still complete.
- Run review on Codex and on Cursor, each producing the standard findings — and on a
  branch seeded with a known path-traversal defect, see the Codex review pass surface
  that **Critical**, demonstrating the cross-family safety net the spike found.
- Build a task on Codex and on Cursor, isolated to the work-item's build workspace,
  with the result passing the verify command and the run recorded in the audit log naming
  the engine and the model/effort it ran at.
- With reviewer = Codex and implementation = Cursor, run review-code on a branch with a
  fixable finding and see the review performed by Codex (read-only) while the auto-fix is
  written by Cursor — the review on the reviewer engine, the fix on the implementation
  engine.
- See Cursor run its composer model, and Codex run at its high-effort default for review
  and building and a low-effort one for mechanical fixes — each visible in the audit log.
- Use configure to see engine availability, record the per-role preference, be walked
  through the one-time build authorization, and have it verified.
- Find the cross-engine contract note, the build-engine contract, the README, and
  CONVENTIONS all updated in the same change.
- See the band's full validation and test suite pass, including new coverage for:
  per-role preference round-trip; fall-open on unknown/unavailable/stalled engines; review
  findings parity per engine; build-then-verify per engine; the fail-closed paths (an
  external build or mechanical fix that fails verify, a run that cannot be audited, and a
  review that returns unreadable or incomplete findings); the **owner-authority boundary**
  (an external producer cannot autonomously merge, force-push, or push to the default
  branch); **secret-scrubbing** of external-engine output surfaced to a pull request or an
  owner notice; and engine-availability detection.

## Assumptions & dependencies

- The Codex and Cursor command-line tools are **installed and signed in** on the
  machine running the band; when one is not, the role for which it was chosen falls
  open to Claude (UFR-1).
- This builds on the band's existing pieces: the role-to-model dispatch seam, the
  code-review panel, the build (producer) leg, the calibration profile and its
  `configure` front door, and the managed build workspace.
- Running an **external** engine *autonomously* for building depends on the owner
  granting the one-time build authorization (FR-13); reviewing needs no such
  authorization because external reviewers run read-only.
- This coordinates with the usage-telemetry work (#24) as a future input for smarter
  routing but does **not** depend on it.
- The project's verify command is resolvable before a run begins — the band's existing
  pre-flight checks this — so UFR-3's "verify could not run" case is rare in-run
  breakage, not the norm.
- The work-item's pull request is opened as a draft during the run (the band's existing
  build/ship behavior); "left in draft" in the unhappy paths above means it is not
  advanced to ready-for-review, and it is never merged automatically.

## Constraints

- **Claude stays the default**, and turning on an external engine is opt-in: a project
  that sets nothing behaves exactly as it does today.
- **The external-build authorization is the owner's to grant and cannot ship inside
  the repository** — it lives in the owner's own settings and the band must never set
  it automatically. (Security boundary, paired with the owner-only NFR.)
- **External reviewers run without write access** to the code under review;
  **external implementers run isolated** to the work-item's build workspace and behind
  the verify gate.
- **An external implementation engine has no more authority than a Claude build:** it
  never merges, force-pushes, or pushes to the default branch on its own — those stay
  the owner's to trigger. The band's existing owner-authority boundary applies to
  external producers unchanged.

## Out of scope

- **Dynamic, budget/cost/fit-aware engine routing** — choosing an engine automatically
  from live inputs. This work is static, owner-set preference only; routing is its own
  (showrunner-area) work-item.
- **Usage / quota telemetry and self-pacing** (tracked on #24).
- **Cursor models other than composer** — no general Cursor model menu is exposed here;
  composer is the only Cursor model used.
- **Multi-run variance / harness-vs-model isolation rigor** — a measurement follow-up,
  not part of this build.
- **Engines other than Codex and Cursor.**
- **Tightening what repository content is shared with an external engine beyond the
  band's existing controls** — under the single-owner threat model the engines are the
  owner's own signed-in tools; any further data-boundary hardening is a separate concern.
- **test-pilot's in-browser bug-fixing on an external engine** — the implementation engine
  governs the build and the shared code-fixer (including review-code's auto-fix), but not
  test-pilot's browser-driven fixes; making those engine-aware also needs the external
  engine to drive test-pilot's browser tooling, a separate follow-up (`area:test-pilot`).

## Open questions

None — every decision was resolved during discovery (engine set, default, fail-open
posture, per-engine model depth, Cursor's composer default, in-place isolated build,
owner-granted build authorization, and `configure`-owned onboarding).

## Glossary

- **Engine** — the underlying agent that does a role's work: Claude, Codex, or Cursor.
- **Reviewer engine / implementation engine** — the engine chosen for the review role
  (read-only review) and for the implementation role, respectively; set independently. The
  implementation role covers the build and the mechanical fixes (FR-4) — including the
  auto-fix review-code applies to its own findings — so the fix that resolves a review
  finding runs on the implementation engine, not the reviewer engine. (test-pilot's
  in-browser fixes are deferred — see Out of scope.)
- **Fall open** — when a chosen engine can't be used, quietly use Claude instead rather
  than blocking the run.
- **Verify command** — the project's own pass/fail check (its tests/build) that the
  band runs to confirm a change is sound.
- **Build authorization** — the one-time owner-granted permission that lets an external
  engine write autonomously — builds and mechanical fixes alike — without a per-action
  prompt.
- **Mechanical fix** — a small, low-judgment code change made during a run (for example
  applying a reviewer's suggested correction or a lint/format fix), as distinct from the
  heavier reasoning work of building the change itself.
- **Review panel / dimension** — the code-review panel is the set of specialist reviewers
  the band runs; each covers one *dimension* (for example correctness, security, tests). A
  complete panel returns readable findings from every required dimension; a panel missing
  or garbling a required dimension is incomplete (UFR-7).

## Coverage

| Area | Disposition | Where / why |
| --- | --- | --- |
| Empty & first-run | Specify | FR-2 — no preference set → both roles run on Claude. |
| Invalid & malformed input | Specify | UFR-1 — an unknown or garbled engine value, or a model override the engine rejects, falls open to Claude with a notice naming the cause. |
| Boundaries & limits | Specify | FR-9 / FR-10 — the model surface is bounded: depth-tiered per engine, Cursor pinned to composer; UFR-5 bounds the stall wait. |
| Errors & failures | Specify | UFR-2 (engine fails mid-run, clean fallback), UFR-3 (external build fails or can't run verify), UFR-5 (engine stalls), UFR-6 (audit-log write fails), UFR-7 (external review returns unreadable findings). |
| Access & permissions | Specify | FR-13 / FR-14 / UFR-4 — external-build authorization is owner-granted (and the producer never merges/force-pushes/pushes-to-default on its own — see Constraints); absent, the build falls open to Claude. |
| Duplicates & double-actions | N-A | No interactive submit surface; run idempotency is governed by the band's existing run machinery, unchanged here. |
| Conflicting / simultaneous use | Defer-to-plan | Engine choice adds no new shared-write surface; the band's existing concurrency/lock model governs. The plan confirms no new contention is introduced. |
| Misuse & abuse | Specify | An external implementer runs its own loop — bounded by FR-5 (verify gate), FR-6 (audit entry with engine/model), UFR-6 (no unaudited acceptance), FR-8 (isolation), the owner-only authorization (FR-13), the owner-authority boundary in Constraints (no autonomous merge / force-push / push-to-default), and the Secret-hygiene NFR (scrubbing external-engine output). |
| Reach (i18n / a11y) | N-A | Internal developer tooling with no graphical UI or locale surface. |
