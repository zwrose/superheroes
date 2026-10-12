---
superheroes: doc
schemaVersion: 1
docType: spec
workItem: showrunner-preflight-readout-f7c1e0
issue: null
size: large
status: approved
gates: {review: passed}
producedBy: "the-architect@0.5.0"
created: "2026-07-03"
updated: "2026-07-03"
---
# Showrunner preflight readout

## Purpose

When an owner kicks off a showrunner run today, they cannot see what the run will
actually do — which agent engine, model, and effort level runs at each phase; whether
the external engines they configured are actually authorized; whether the verify
command and storage are set the way they expect. The only way to know is to read
through several source files by hand. That is how a silent bug was found — a review
phase quietly running on whatever model happened to be in session instead of the one
policy intended (#160).

This work adds a plain-language **readout the showrunner prints at launch, before any
agent runs**, describing exactly what the run will do and with what settings. The owner
reads it, can **adjust the per-run dispatch settings** (which engine, model, or effort a
role uses) right there, and confirms before the run proceeds. It turns "what will this run
actually do?" from an archaeology exercise into something the owner sees — and can steer —
for free before committing their time and tokens.

## Who it's for

The owner launching a showrunner run from their terminal — a product-minded person who
wants to confirm "this run will do what I expect" at a glance, without reverse-engineering
it from code. They are present and interactive at the moment of launch.

## Functional requirements

**FR-1.** When the owner launches the showrunner and the deterministic preflight gate
passes, the system shall render the readout and wait for the owner's explicit confirmation
before dispatching any agent.
  - *Acceptance (Given-When-Then):* Given an approved work-item whose preflight gate
    passes, when the owner launches the showrunner, then the readout is printed and the
    run waits — no agent has been dispatched — until the owner confirms.

**FR-2.** The readout shall show, for each phase of the run and each distinct role that
phase dispatches an agent for, the engine, the model, and the effort level that will be
used.
  - *Acceptance (Given-When-Then):* Given a run whose build phase dispatches a builder, a
    per-task reviewer, a fixer, and a final reviewer, when the readout renders, then each of
    those roles appears with its own engine, model, and effort; a phase that dispatches a
    single role shows a single line; no phase or role that will dispatch is omitted.

**FR-3.** Where a role is designed to inherit the session model (the orchestration role),
the readout shall show it as inheriting the session model and mark it as expected.
  - *Acceptance (rule):* The orchestration role's line reads as inheriting the session model
    and is marked "expected"; every other role's line shows a concrete named model, not an
    inherit.

**FR-4.** The readout shall state, for each external engine the run would use — whether from the
project configuration or a per-run override (FR-10) — whether it is currently authorized, and shall
note when a role falls back to Claude because authorization is not granted.
  - *Acceptance (Given-When-Then):* Given a project that configures the reviewer role to use
    Codex but Codex authorization is not currently granted, when the readout renders, then it
    shows the reviewer role falling back to Claude and flags that Codex authorization is not
    granted.
  - *Acceptance (Given-When-Then):* Given the owner overrides a role's engine to Cursor but Cursor
    authorization is not granted, when the readout re-renders, then it shows that role falling back to
    Claude and flags that Cursor authorization is not granted (an override does not bypass authorization).

**FR-5.** The readout shall mark each setting it shows as either explicitly configured for
the project or a provisional default, and shall flag when the project's calibration as a
whole is provisional rather than owner-confirmed.
  - *Acceptance (Given-When-Then):* Given a project whose calibration is provisional (not
    owner-confirmed), when the readout renders, then it carries a "provisional calibration"
    flag; and given a setting that is not configured for the project and falls back to a
    built-in default, then that line is labeled as a default.

**FR-6.** The readout shall show the verify command that will gate the run's fixes, or state
plainly that the project is unverified.
  - *Acceptance (rule):* When a verify command is configured, the readout shows that command;
    when the project is explicitly unverified, the readout says the run is unverified.

**FR-7.** The readout shall show the storage mode in effect and where the run reads and writes
its definition docs.
  - *Acceptance (Given-When-Then):* Given a project in global (out-of-repo) storage mode, when
    the readout renders, then it names the storage mode and the location its definition docs are
    read from and written to.

**FR-8.** When the owner confirms the readout, the system shall dispatch the run using the exact
settings the confirmed readout displayed with a concrete value — a snapshot of that final render (the
configuration plus any per-run overrides in effect), frozen at confirmation — regardless of any change
to the project's configuration after the readout was shown. A setting the readout could not determine
(shown as "unavailable" per UFR-2) has no snapshot value; the run resolves that phase normally at
dispatch.
  - *Acceptance (Given-When-Then):* Given the owner confirms the readout, when the run proceeds, then
    each phase dispatches with the engine, model, and effort the readout displayed for it.
  - *Acceptance (Given-When-Then):* Given the project's configuration is edited after the readout is
    shown but before the owner confirms, when the run proceeds, then it still dispatches with the
    settings the readout displayed — never a value the owner did not see; changing a run's settings
    instead requires relaunching, which re-renders the readout (FR-9).

**FR-9.** When the owner relaunches or resumes a run, the system shall render the readout again
and wait for confirmation before dispatching.
  - *Acceptance (Given-When-Then):* Given a parked run being relaunched, when the owner launches
    it, then the readout renders again with current settings and the run waits for the owner's
    confirmation.

**FR-10.** When the readout is shown, the system shall let the owner set a per-run override for any
overridable role's engine, model, or effort before confirming; overridable roles are every role except
the by-design orchestration role, which stays session-inherited (FR-3).
  - *Acceptance (Given-When-Then):* Given the readout is shown, when the owner sets an override for an
    overridable role's engine, model, or effort, then the override is accepted and no agent has been
    dispatched.
  - *Acceptance (Given-When-Then):* Given the readout is shown, when the owner sets overrides on two
    different roles before confirming, then both are accepted and both show marked "overridden for this
    run."
  - *Acceptance (Given-When-Then):* Given the by-design orchestration role, when the owner reviews what
    can be overridden, then that role is not an override target and stays session-inherited.
  - *Acceptance (Given-When-Then):* Given a role the readout showed as "unavailable" (UFR-2) or
    "unrecognized" (UFR-5), when the owner sets a valid override on it, then that role takes the concrete
    overridden value and is marked "overridden for this run."

**FR-11.** When the owner sets an override, the system shall re-render the readout with the overridden
line marked as overridden for this run and every non-overridden line unchanged from the snapshot, and
shall require confirmation of the updated readout before dispatching.
  - *Acceptance (Given-When-Then):* Given the owner overrides one role's model, when the readout
    re-renders, then that role's line shows the new model marked "overridden for this run," every other
    line is unchanged from the original snapshot, and the run still waits for the owner's confirmation.

**FR-12.** When the owner confirms a readout that includes overrides, the system shall dispatch the run
using those overrides in place of the configured settings for this run only.
  - *Acceptance (Given-When-Then):* Given the owner overrides the reviewer role's engine to Codex (which
    is authorized) and confirms, when the run proceeds, then the reviewer role dispatches on Codex; and
    after the run, the project's saved calibration still shows its prior reviewer engine.

**FR-13.** The system shall record per-run overrides durably with the run, so they outlive a single
launch.
  - *Acceptance (Given-When-Then):* Given the owner sets a per-run override and the run parks, when the
    run's record is read back, then the override is present in it (it is not lost with the launch).

**FR-14.** When the owner relaunches or resumes a run that had overrides, the system shall reapply those
recorded overrides, re-validate each against the current option set and authorization, and show them in
the re-rendered readout — marking any override that is no longer valid or authorized so the owner sees it
before confirming.
  - *Acceptance (Given-When-Then):* Given a parked run with a per-run model override, when the owner
    relaunches it, then the readout re-renders showing that override marked "overridden for this run" and
    reapplies it once the owner confirms.
  - *Acceptance (Given-When-Then):* Given a parked run whose per-run override is no longer a valid option
    (or whose overridden engine is no longer authorized), when the owner relaunches it, then the readout
    shows that override flagged rather than silently applying it, and the run waits for the owner to
    adjust or confirm.

## When things go wrong (significant unhappy paths)

**UFR-1.** If the owner declines at the readout confirmation, then the system shall abort the
launch without dispatching any agent and without changing any branch or pull request.
  - *Acceptance:* Given the readout is shown, when the owner declines, then no agent runs, no
    branch or PR is created or modified, and the run is not marked as started.

**UFR-2.** If the system cannot resolve one or more of the settings the readout would show, then
the system shall render the rest of the readout, mark each unresolved item as unavailable, and
still require the owner's explicit confirmation.
  - *Acceptance:* Given one field errors while the readout is assembled, when the readout renders,
    then that field reads "unavailable" (with the reason when known), every other line is shown,
    and the run still waits for confirmation rather than proceeding automatically.
  - *Acceptance:* Given a phase whose setting the readout marked "unavailable," when the owner
    confirms and the run reaches that phase, then the run resolves that phase with its normal
    resolution (the capable default when the setting cannot be determined), not a frozen "unavailable."

**UFR-3.** If the system cannot assemble any of the readout, then the system shall not launch the
run and shall show why, with a plain-language remediation.
  - *Acceptance:* Given readout assembly fails entirely, when the owner launches, then no agent is
    dispatched and the owner sees a plain reason plus how to fix it (fail-closed — no run on a
    readout it could not produce).

**UFR-4.** If a phase whose settings the readout can determine would dispatch with a session-inherited
model where that is not the by-design orchestration role, then the system shall still show that phase's
line, flagged as an unexpected inherit, rather than omitting it.
  - *Acceptance:* Given a phase resolves to a session-inherited model outside the orchestration
    role, when the readout renders, then that phase appears flagged as an unexpected inherit and is
    never silently dropped from the readout.

**UFR-5.** If a setting resolves to a value the readout does not know how to display (for example an
engine name or effort level added to the configuration that the readout has no display rule for), then
the system shall show the value as-is, marked as unrecognized, rather than omitting the line or failing,
and shall still require the owner's confirmation.
  - *Acceptance:* Given a configuration value outside the set the readout knows how to render, when the
    readout renders, then the affected phase line shows the raw value marked "unrecognized," no line is
    dropped, and the run waits for the owner's confirmation.

**UFR-6.** If the owner enters an override value the setting does not accept (not a valid engine,
model, or effort option), then the system shall reject it, show the values the setting does accept,
and leave that setting at its currently-effective value (the existing override if one is in place,
otherwise the configured default), rather than applying an invalid value or dispatching.
  - *Acceptance:* Given the owner enters a model that is not a valid option, when they submit it, then
    the readout rejects the value, lists the values the setting accepts, keeps the currently-effective
    value, and the run does not proceed on the invalid value.

## Non-functional requirements

- **Accuracy (no drift):** The readout shows the same settings the run actually dispatches with —
  including any per-run overrides the owner set — and there is no separately maintained description
  that could disagree. *Fit-criterion:* changing a model, engine, or effort setting (by configuration
  or by a per-run override) changes both the readout and the dispatch together, with no other edit;
  the readout is never a hand-maintained copy of the dispatch picture. This guarantee
  covers settings the readout determined and displayed with a concrete value; a setting shown
  "unavailable" (UFR-2) is explicitly outside it — the owner confirms through it as a known-unknown,
  and its dispatch value is not preflight-verified.
- **Cost:** Rendering the readout consumes no model tokens. *Fit-criterion:* assembling and printing
  the readout dispatches no agent (it is produced deterministically, like the existing preflight gate
  and the zero-token live watcher).
- **Determinism:** The same configuration produces the same readout. *Fit-criterion:* two renders
  against unchanged configuration are identical.
- **Scannability:** The readout is short enough for the owner to take in without scrolling.
  *Fit-criterion:* the readout shows one line per phase/role the showrunner's default pipeline
  dispatches (the exact roster is the pipeline's, enumerated by the plan); for that default pipeline
  with one external engine configured, the rendered readout — that table plus the
  external-engine-authorization, calibration, verify, and storage lines — is no more than 40 lines.
- **Privacy (local-only):** The readout is shown only in the owner's terminal. *Fit-criterion:* no
  readout content is written to a pull request, a comment, or a shared run log in this version. The
  readout may echo owner-supplied configuration (such as the verify command or storage paths) verbatim,
  without redaction, because it is shown only to the owner who authored that configuration on their own
  terminal; any future version that routes readout content to a shared destination must revisit
  redaction before doing so.

## UI / UX

The readout is terminal text (no separate design surface). This work was scoped text-first, so the
key "screen" is described here as a plain-language sketch rather than a Claude Design handoff:

```
Showrunner preflight — <work-item>

Phases & dispatch
  plan             claude · opus                  (author)
  review-plan      codex · gpt-5.5 · high         (reviewer)
  tasks            claude · opus                  (author)
  review-tasks     codex · gpt-5.5 · high         (reviewer)
  build            cursor · composer              (builder)
                   claude · sonnet                (per-task reviewer)
                   claude · sonnet                (fixer)
                   codex · gpt-5.5 · xhigh        (final reviewer)
  review-code      claude · opus                  (deep reviewer) — overridden for this run
  test-pilot       claude · opus                  (orchestration — inherits session model, expected)
  ship             claude · sonnet                (fixer, on CI failure)

External engines   codex: authorized   ·   cursor: NOT authorized → review falls back to Claude
Calibration        provisional (not owner-confirmed) ⚠
Verify             npm test
Storage            global · docs at <path-to-docs>

Confirm to launch  ·  override a role's engine/model/effort for this run  ·  decline (aborts, no changes)
```

The exact columns, ordering, and wording are the plan's to finalize; the requirement is that every
listed element above is present, scannable, accurate to what will dispatch (including any per-run
override, shown marked as above), gated behind an explicit confirm, and lets the owner override a
role's engine/model/effort before confirming. The illustrative engine/model values above are examples,
not fixed defaults.

## Definition of done / success

An owner launching the showrunner sees, before any agent runs, a one-screen plain-language readout of
every phase's engine, model, and effort, plus whether external engines are authorized, whether the
calibration is provisional, the verify command, and the storage mode and doc locations — accurate
to what the run will actually do for every setting the readout could determine (a setting shown
"unavailable" is an accepted known-unknown, not a verified value) — and the run proceeds only after
the owner confirms, or aborts cleanly if they decline. The owner can also adjust a role's engine,
model, or effort for the run before confirming (every role except the session-inherited orchestration
role); those adjustments persist across restarts, are re-validated on relaunch, and never change the
saved project calibration. An owner who previously had to read source to answer "what runs
where?" can now answer it — and steer it for the run — from the readout alone.

## Assumptions & dependencies

- **Depends on #160 (session-model inheritance audit/fix), which has landed** (PR #163, merged to
  `main` 2026-07-03). The readout describes each phase from the run's configured settings; #160 is what
  makes every phase actually honor its configured setting, so the readout — read from those settings —
  matches what actually runs. (Before #160, the per-task reviewer bypassed its configured setting and
  silently inherited the session model — distinct from an unexpected inherit the readout can flag per
  UFR-4, because a readout reading the configured setting could not detect the bypass.) This work-item's
  base is `main` at or after #163.
- Relies on the band's existing settings and their readers as the sources of truth: model-tier policy,
  engine preference and effort, verify command, storage mode, and the core calibration (provisional
  vs confirmed). This work reads them as the run's defaults; a per-run override (FR-10–FR-14) changes
  only the current run, never the saved calibration.
- The owner is present and interactive at launch (the confirmation gate assumes an interactive launch;
  this matches how the showrunner is invoked today).
- The deterministic preflight pass/fail gate runs first and has already blocked on unreadable config,
  so the readout assembles over config that at least parses.

## Constraints

- The readout must not itself dispatch an agent — zero model-token cost — consistent with the existing
  deterministic preflight gate and the zero-token live watcher.
- The readout renders **after** the existing deterministic preflight pass/fail gate passes and **before**
  the run's first dispatch. It supplements that gate; it does not replace it or change its checks.
- The showrunner still never merges, deploys, releases, or force-pushes; adding the readout changes none
  of those boundaries.
- A per-run override applies to the current run only and never modifies the project's saved calibration;
  changing the saved calibration remains the job of `configure`.
- An override value is restricted to a value the setting normally accepts (a valid engine, model, or
  effort option); the run never dispatches on a value outside those sets.

## Out of scope

- The threat-model / scope-exclusions section of the readout (deferred; can be added later).
- Surfacing the readout anywhere other than the showrunner launch — no on-demand re-print flag and no
  `configure` view in this work. The phase-enumeration is built so those surfaces can adopt it later,
  but building them is not in scope here.
- Fixing the #160 inheritance bug itself — that landed separately (PR #163); this work-item only reads
  its result.
- Overriding anything other than a role's engine, model, or effort per run — the verify command, build
  authorization, and storage / doc-locations stay read-only in the readout.
- Seeding overrides from launch flags or arguments — in this version overrides are entered at the
  confirmation gate.
- Changing the project's saved calibration — that remains the job of `configure`.
- Any change to the pass/fail preflight gate's checks or its remediations.
- Per-phase token or cost accounting in the readout — that is separate work (#130).

## Coverage

| Area | Disposition | Where / why |
| --- | --- | --- |
| Empty & first-run | Specify | FR-5 — an unconfigured project renders explicit, labeled defaults (never blanks) and a provisional-calibration flag. |
| Invalid & malformed input | Specify | UFR-6 — an invalid per-run override value (bad engine/model/effort) is rejected with the accepted values, and the run keeps its prior setting. (Config-file parse errors remain the preflight gate's job, before the readout renders.) |
| Boundaries & limits | Specify | NFR Scannability — the rendered readout is no more than 40 lines for the default showrunner pipeline with one external engine configured. |
| Errors & failures | Specify | UFR-2 (a setting won't resolve → degrade + flag + still confirm), UFR-3 (nothing assembles → fail-closed, no run), and UFR-5 (a resolved value the readout can't display → show raw, marked unrecognized). |
| Access & permissions | N-A | Single-owner local terminal tool; there is no multi-user access surface to the readout. |
| Duplicates & double-actions | Specify | FR-9 / FR-14 — a relaunch/resume renders the readout again (reapplying any recorded per-run overrides) and re-confirms; re-invocation is expected and safe. |
| Conflicting / simultaneous use | Defer-to-plan | The preflight gate's existing no-active-run check already guards a second concurrent run; the readout adds nothing here. |
| Misuse & abuse | N-A | Local single-owner tool; a per-run override only re-points the owner's own run (bounded to valid options, no saved-config change) — no sensitive or irreversible cross-boundary action. |
| Reach (i18n / a11y) | N-A | Internal terminal tool for the single owner; no localization or broad accessibility surface in scope. |
