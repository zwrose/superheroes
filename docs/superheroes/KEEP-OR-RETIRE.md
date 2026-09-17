# Keep-or-retire list and workaround-marker inventory

## Framing

You read this file at a [gardening pass](../../plugins/superheroes/rubric/glossary.md#gardening-pass).
Nothing checks it mechanically and it gets no guard. Its vocabulary is the shipped glossary at
[plugins/superheroes/rubric/glossary.md](../../plugins/superheroes/rubric/glossary.md); this file defines
no term of its own and points there once. This file is the project's own record, the same class
of document as `LEDGERS.md`, and it lives with the project's definition-docs wherever the project's
doc-policy keeps them: `docs/superheroes/` in this repository, and the out-of-repo store in a project
whose doc-policy keeps its docs there. The rules it applies ship in the glossary and the rubric.

Strategic-assessment evidence cited as `the assessment record` lives in a record kept beside this
repository, outside the repository; entries cite it by name rather than by path.

## How an entry is built

A [keep-or-retire entry](../../plugins/superheroes/rubric/glossary.md#keep-or-retire-entry) has six
fields, in this fixed order:

1. **Component** — the census row, by its stable id and name, and the cost or annoyance that makes
   reconsidering it worthwhile.
2. **Condition** — one of the three shapes, its window in calendar days, and the one action on
   firing.
3. **Last demonstrated benefit** — what the component did, described, with its locator in
   parentheses; or `unknown`.
4. **Consumer evidence** — a consuming project's or external user's report, described, with its
   locator in parentheses; or `unmeasured`.
5. **Decision** — the owner's latest decision. Every non-foundational entry reads
   `keep-until-condition-fires`.
6. **Notes** — the tag, its one-line reason, and, where the component guards a model behaviour, the
   engine family the evidence was observed on.

**Condition shapes and default windows.** The three shapes are
[catch-based](../../plugins/superheroes/rubric/glossary.md#catch-based) (45 days),
[citation-based](../../plugins/superheroes/rubric/glossary.md#citation-based) (45 days), and
[usage-based](../../plugins/superheroes/rubric/glossary.md#usage-based) (60 days). You choose one shape
per component. When you use a window other than the default, state it with its reason.

**What a condition must name.** A well-formed condition names its signal, its window, and its
action. The only valid action is a proposal to the owner at a gardening pass. The most aggressive
outcome of a condition firing is a conversation.

**Deterrent and by-construction-silent components.** Deterrent and by-construction-silent components
take citation-based or usage-based conditions, never catch counts. A fail-closed gate's zero catches
may mean it is working. Write every entry against this rule.

**Unmeasured is not zero.** A component with no signal of any shape is
[unmeasured](../../plugins/superheroes/rubric/glossary.md#unmeasured); a consumer that has not reported on
a component is unmeasured for it. An absent, unreadable, or short-of-window record reads unmeasured.
Silence never counts as a clean window.

**Tags and the decision rubric.** The tag is one of the glossary's four:
[structural](../../plugins/superheroes/rubric/glossary.md#tag-structural),
[capability-gap](../../plugins/superheroes/rubric/glossary.md#tag-capability-gap),
[harness-limit](../../plugins/superheroes/rubric/glossary.md#tag-harness-limit), or
[mixed](../../plugins/superheroes/rubric/glossary.md#tag-mixed). A zero count means keep for structural,
probably outgrown for capability-gap, wait for the host to change for harness-limit, or split the
line for mixed. Apply this rubric: **structural** where the component guards a property of how this
system is built and no change of host or model would remove the need; **capability-gap** where it
compensates for something a model cannot yet do reliably; **harness-limit** where it works around
something the host does not offer; **mixed** where two of those apply to different parts of the same
component, in which case the entry names which part is which.

**Landed vs plain keep.** A component whose entry has not landed is a plain keep. A landed
non-foundational entry is keep-until-condition-fires from the moment it lands.

**Birth duty.** A new component ships with its entry, its condition, and its tag at birth.

## The foundational set

A [foundational component](../../plugins/superheroes/rubric/glossary.md#foundational-component) has no
condition and is never queued. Changing one is a spec amendment. The foundational set as it stands
at landing is the covenant's hard lines, read from
[plugins/superheroes/rubric/covenant.md](../../plugins/superheroes/rubric/covenant.md), plus the
two authority surfaces the owner set to foundational at the landing look, the worktree guard (A2)
and model governance (F2). The hard lines:

- **Never merge, release, or publish on your own authority.**
- **Review before handback.**
- **Receipts before claims.**
- **Disclose degradation** where the owner reads — the PR body, not a buried log.
- **Park, don't presume.**

Every foundational component is structural, and most structural components are not foundational.

### The authority surfaces

Five [authority surfaces](../../plugins/superheroes/rubric/glossary.md#authority-surface) implement owner
hard lines: the worktree guard, the circuit breaker and its escalation, model governance, the verify
gate, and the vet-receipt spine with its owner half. The owner sets each to a condition or to
foundational. A condition on a component implementing an owner hard line is never a standing licence
on that surface.

**Worktree guard.** Owner's look at landing: foundational. Its success is silence, and a citation window over a silent deterrent produces a firing that means nothing.

**Circuit breaker and its escalation.** Owner's look at landing: a condition, catch-based over 45 days as drafted. Its catches are recorded, so a quiet window is real evidence.

**Model governance.** Owner's look at landing: foundational. Which model runs which role is an owner hard line, and a usage count over every dispatch could never fire.

**Verify gate.** Owner's look at landing: a condition, citation-based over 45 days as amended by the review. It carries a real per-run cost worth weighing periodically.

**Vet-receipt spine with its owner half.** Owner's look at landing: a condition, usage-based over 60 days as drafted, counting vets that post a complete receipt with distinct probes.

## The consumer-report lifecycle

- A consumer report is an issue on this repository carrying the `consumer-report` label and the
  shipped template: the project and plugin version, the component, what was expected and what
  happened, and a pointer to the lane, dispatch, journal, or receipt that evidences it.
- Anyone may file one. A consuming project's advisor files them as a matter of course. A report
  delivered by any other channel is filed as that issue on receipt, so a message queue never defers
  a firing past the next gardening pass after delivery.
- Each open report is linked from its component's entry as a receipt, and is closed when a gardening
  pass has read it or a proposal it fed has been ruled.
- A consumer with no report on a component is unmeasured for it, never a count. Every proposal names
  the consumers it could not measure.
- Before a retirement proposal on a component a known consumer uses, the advisor asks through an
  existing channel and waits at most one gardening window. No answer is recorded as unmeasured,
  never as consent, and the proposal proceeds saying so.
- The evidence bar is the record pointer. A report with no record behind it is a conversation, not a
  firing.

### A worked example

This illustration uses a fictional component named `example-guard` that appears nowhere else in this
file or the repository.

1. A consumer files an open report linked from the entry.

```
- **Consumer evidence.** Open consumer report (issue #0).
```

2. A gardening pass reads the report and closes it.

```
- **Consumer evidence.** Closed consumer report (issue #0).
```

3. A second consumer never reported; the same field shows that consumer as `unmeasured` alongside
   the closed report — not a zero and never a clean window.

```
- **Consumer evidence.** Closed consumer report (issue #0); second consumer unmeasured.
```

## The keep-or-retire list

The list's units are the census rows, and each entry is keyed to its census id.

### A. Session gates & hooks

#### A1 — Owner-authority gate

- **Component.** PreToolUse(Bash) gate and classifier that ask before enumerated owner-authority
  actions on calibrated projects; it costs a stdin parse and command inspection on every Bash call.
- **Condition.** Citation-based, 45 days: vet, forfeit-dispute, or incident receipts citing an
  owner-authority gate `ask` that blocked an unauthorized merge, release, force-push, default-branch
  push, or workflow dispatch. On firing, a proposal to the owner at a gardening pass.
- **Last demonstrated benefit.** Re-derived tool-to-subcommand matching to close a silent
  classification bypass in workflow dispatch (#989).
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** structural — implements the never-merge-on-agent-authority hard line; a zero citation
  count means the floor is holding, not that the bypass class is gone.

#### A2 — Worktree guard

- **Component.** PreToolUse(Bash) gate and classifier that deny destructive git discard on dirty
  calibrated worktrees; it costs a git status probe on matching commands.
- **Condition.** None. Foundational by the owner's look at landing; it is never queued, and
  changing it is a spec amendment.
- **Last demonstrated benefit.** Refuses destructive `git` discard when uncommitted work would be
  lost, guarding the checkout-revert wipe class (#682); fired twice during the build that landed
  this document.
- **Consumer evidence.** unmeasured.
- **Decision.** foundational.
- **Notes.** structural — guards unrecoverable worktree loss; a zero citation count means agents are
  not attempting the wipe, not that the defect class vanished, which is why no window sits on it.

#### A3 — Handback receipt gate (hook)

- **Component.** PreToolUse(Bash) handback-receipt hook shipped dark and unwired from the live hook
  chain, with zero shipped consumers ever; K1 retires it with `handback_gate.py` (#954).
- **Condition.** Citation-based, 45 days: vet, forfeit-dispute, or incident receipts citing a live
  handback-receipt refusal (none possible while dark and unwired). On firing, a retirement proposal
  to the owner at a gardening pass. An absent, unreadable, or short-of-window record reads
  unmeasured, never zero.
- **Last demonstrated benefit.** unknown.
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** harness-limit — the host PreToolUse chain does not arm this hook;
  review-before-handback is held in charter prose until K1 lands.

#### A4 — Bash timeout hook

- **Component.** PreToolUse(Bash) input rewrite that floors omitted Bash tool timeouts to 600s; it
  costs a stdin parse on every Bash call and works around the host's 120s default.
- **Condition.** Citation-based, 45 days: vet, forfeit-dispute, or incident receipts in which the
  injected timeout floor is what let a command finish. On firing, a proposal to the owner at a
  gardening pass. The hook's firing record is a corroborating join source, not the citation itself;
  the citation is the vet, forfeit-dispute, or incident receipt, and the record's session and
  timestamp tie that receipt to a firing. An absent, unreadable, or short-of-window record reads
  unmeasured, never zero.
- **Last demonstrated benefit.** Probe-verified that injected timeout takes effect and that plugin
  PreToolUse hooks fire inside subagent leaves (hooks/bash_timeout.py docstring, 2026-07-04).
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** harness-limit — leaf models omit `timeout` stochastically and the host default kills
  long spine commands; explicit model-passed timeouts are never touched.

#### A5 — Session bootstrap (covenant inject, compaction recovery, skew notice)

- **Component.** SessionStart bootstrap and PreCompact charter-aware compaction skeleton; the row is
  process prose machinery loaded on every spawn and compact, and it costs context tokens per
  session.
- **Condition.** Usage-based, 60 days: calibrated sessions where bootstrap or compaction context
  fired (startup, resume, clear, or compact sources). On firing, a proposal to the owner at a
  gardening pass.
- **Last demonstrated benefit.** Probe-verified that native harness context loads on all spawn paths
  while bootstrap still supplies plugin roots and the distilled covenant (#627).
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** mixed — covenant and plugin-root inject are structural; charter-aware compaction
  preserve directives are capability-gap until the host offers native charter steering.

#### A6 — source_guard

- **Component.** A pytest guard that blocks writes to shipped Python source during test runs; it
  costs session setup and parallel-run overhead on every suite invocation.
- **Condition.** Citation-based, 45 days: vet, forfeit-dispute, or incident receipts citing
  `source_guard` catching a shipped-source mutation under parallel test execution. On firing, a
  proposal to the owner at a gardening pass.
- **Last demonstrated benefit.** Caught a shipped-source mutation race under pytest-xdist parallel
  execution (#1153).
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** structural — a zero catch count means the guard is doing its job, not that the race is
  gone.

#### A7 — Version-skew guard

- **Component.** Plugin-version skew detector appended to seat-map degradations; K2 retires it with
  trigger to rebuild at the front door when a real skew incident recurs.
- **Condition.** Citation-based, 45 days: real skew-incident receipts (the K2 rebuild trigger). On
  firing, a rebuild proposal to the owner at a gardening pass.
- **Last demonstrated benefit.** unknown.
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** capability-gap — detection-only record with zero recorded firings; the motivating
  incident (#675) predates the module and was fixed by other means.

### B. Launch & wave machinery

#### B1 — Launcher + launch ledger (declare-batch/launch/record-outcome/amend)

- **Component.** Headless launcher, launch ledger, doctrine, and build-lane stamp that walk
  preflight, reserve, spawn, and outcome recording for unattended waves; it costs ledger I/O and
  detached-spawn plumbing on every batch.
- **Condition.** Usage-based, 60 days: unattended launch batches that reach a stamped ledger outcome
  via launcher verbs. On firing, a proposal to the owner at a gardening pass.
- **Last demonstrated benefit.** unknown.
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** structural — load-bearing spine for declare-batch, launch, record-outcome, and amend;
  wave_watch and heartbeat read the ledger it writes.

#### B2 — wave_watch (loop watcher + re-arm doctrine)

- **Component.** Ledger-driven batch watcher and loop re-arm doctrine with its reference doc; it
  costs polling, gh child spawns, and advisor attention per armed batch.
- **Condition.** Citation-based, 45 days: vet, forfeit-dispute, or incident receipts citing a
  wave_watch qualifying event that drove advisor action. On firing, a proposal to the owner at a
  gardening pass.
- **Last demonstrated benefit.** unknown.
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** harness-limit — the host offers no native batch watcher; auto-re-arm redesign is queued
  at the front door while the silent-death class it targets still recurs in field evidence.

#### B3 — Heartbeat

- **Component.** Semantic builder heartbeat stamp and advisor sweep classifier; a false `fresh`
  answer is the dangerous failure mode, and every lane carries periodic stamp overhead.
- **Condition.** Citation-based, 45 days: vet, forfeit-dispute, or incident receipts citing
  heartbeat sweep classifications of `stale` or `terminal` that drove advisor or wave_watch action.
  On firing, a proposal to the owner at a gardening pass.
- **Last demonstrated benefit.** Classified six stalled lanes in one advisor sweep
  (the assessment record).
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** structural — fail-closed liveness signal for unattended builders; a low catch count
  means builders are finishing, not that wedged lanes stopped happening.

#### B4 — Seat canary (planted-defect control probe)

- **Component.** Planted-defect control probe that dispatches a known-bad fixture through the real
  seat path and scores engagement and plant detection; each run costs a full seat dispatch.
- **Condition.** Catch-based, 45 days: canary runs where engagement or plant-detection axes scored a
  miss. On firing, a proposal to the owner at a gardening pass.
- **Last demonstrated benefit.** Tripwire scored seven correct fires in one wave (the assessment
  record).
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** capability-gap — measures whether review seats investigate and name planted defects;
  evidence observed on the real dispatch path (#668).

#### B5 — Environment probes

- **Component.** Scaffold probes that detect harness and worktree environment faults before
  dispatch; the row covers `harness_probe`, `sibling_worktree_probe`, and `hostinfo`, which differ
  in wiring and retirement posture.
- **Condition.** Citation-based, 45 days: vet, forfeit-dispute, or incident receipts that cite the
  probe rule's substance for `sibling_worktree_probe`. On firing, a proposal to the owner at a
  gardening pass. `hostinfo` has no separate condition; `harness_probe` is retired and is not
  counted.
- **Last demonstrated benefit.** `sibling_worktree_probe` guards false worktree-dirtied forfeits
  with a wired reader on every terminal dispatch fold (wired reader, zero recorded catches).
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** harness-limit for `sibling_worktree_probe` — the host offers no native
  worktree-liveness signal; structural for `hostinfo` — load-bearing file-lock consumer with a real
  defect class behind it.

#### B6 — File lock + store family

- **Component.** Substrate row: `file_lock`, `store_core`, `store_sweep`, and test-pilot-only
  `store.py` guard concurrent engine applies and project-store writes; proposals on this row are
  shrink or split, not row deletion.
- **Condition.** Usage-based, 60 days: consuming acts that acquire `file_lock` or write through the
  store family (engine dispatch, calibration, test-pilot). On firing, a shrink proposal to the owner
  at a gardening pass.
- **Last demonstrated benefit.** Foreign-host reclaim and tri-state `same_boot` doctrine settled a
  permanent-wedge defect class (#953).
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** structural — load-bearing substrate for parallel worktree agents and store I/O; shrink
  targets members, not the row's existence.

### C. Engine dispatch stack

#### C1 — Dispatch core

- **Component.** This row is substrate — a proposal on it is a shrink proposal, not a deletion. The
  cross-vendor dispatch stack (`engine_dispatch.py`, adapters, authz, prefs) costs ongoing contract
  maintenance and measured caller-facing refusal churn; CP2 directs a shrink of the entry/argument
  shell while the parse/scrub/forfeit-grading boundary stays tight.
- **Condition.** Usage-based, 60 days: the signal is terminal `dispatch-write` and `dispatch-review`
  runs graded through the core. On firing, a shrink proposal to the owner at a gardening pass.
- **Last demonstrated benefit.** Blocked silent inference of load-bearing dispatch params — the #839
  specimen — and closed fail-open grading on malformed engine output at the parse boundary (#1010
  empty-object class) (the assessment record).
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** mixed — the parse/scrub/forfeit shell is structural; the caller-facing refusal surface
  is capability-gap until tolerant reading pairs with deterministic echo.

#### C2 — Dispatch grading & self-test

- **Component.** Pre-dispatch model allowlist grading and dispatch self-test guards
  (`dispatch_guard.py`, `dispatch_outcome.py`, `dispatch_selftest.py`); they cost a CLI round-trip
  on every external dispatch and block unlisted models before spawn.
- **Condition.** Citation-based, 45 days: vet, forfeit-dispute, or incident receipts citing
  `dispatch_guard.py check` blocking an unlisted or misconfigured engine/model before spawn. On
  firing, a proposal to the owner at a gardening pass.
- **Last demonstrated benefit.** Refused an unlisted model pick with a park-not-pick outcome (#600
  class, wired in `dispatch_guard.py` refusal tail).
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** structural — registry allowlisting guards how dispatch is authorized, not a model
  quirk.

#### C3 — Preflight probe

- **Component.** The v2 run preflight aggregator and dispatch-calibration readout
  (`preflight_probe.py`); it costs probe subprocesses and orchestrator browser exercise before a
  wave opens, and fails loud when auth, CLI, or calibration prerequisites are missing.
- **Condition.** Citation-based, 45 days: vet, forfeit-dispute, or incident receipts citing
  preflight `aggregate` outcomes that blocked a go/no-go with `ok: false` on a probe the build
  would otherwise have launched against. On firing, a proposal to the owner at a gardening pass.
- **Last demonstrated benefit.** unknown.
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** structural — fail-loud go/no-go before dispatch is load-bearing wave hygiene.

#### C5 — Payload/findings contracts

- **Component.** Declared per-seat payload contracts and the review-findings schema guards
  (`payload_contracts.py`, `review_findings_schema.py`); they cost layering maintenance at the seam
  between round phases and engine transport, and refuse unreadable or schema-drifting seat output.
- **Condition.** Citation-based, 45 days: vet, forfeit-dispute, or incident receipts citing
  terminal dispatch refusals graded `unreadable` or schema-blocked on review payload shape. On
  firing, a proposal to the owner at a gardening pass.
- **Last demonstrated benefit.** Closed the #949 outer-envelope fail-open class where empty or
  control-wrapped findings could certify clean (`engine_adapter.py` gate, #1145 hardening).
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** structural — the contract guards transport gradeability independent of seat honesty.

#### C6 — Sanitized view

- **Component.** The disposable git export review seats run in (`sanitized_view.py`), shrunk to
  the trusted-repository posture: the neutral-cwd export, the exclusion of the twelve configuration
  files and six directories, the containment family (outward-symlink refusal, repo-root validation,
  PR-body session pairing, run-dir symlink refusal), and the review-only file that carries stripped
  configuration hunks as data under review. Two correctness guards stay with it that are not
  defenses: the argv budget against the host's argument limit, and the shallow-clone refusal. The
  hostile-repository defense set is retired. It costs export time and temp disk on every sanitized
  review dispatch.
- **Condition.** Citation-based, 45 days: vet, forfeit-dispute, or incident receipts citing a
  containment refusal, a withheld-path receipt, or a review that read the review-only configuration
  file as its subject. On firing, a proposal to the owner at a gardening pass.
- **Last demonstrated benefit.** The ten containment fixtures still fire after the shrink, and a
  live review seat read a stripped `CLAUDE.md` change from the review-only file and cited it by
  name (the sanitized-view shrink's build record).
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** structural — keeping one project's agent configuration from becoming another session's
  instructions is a boundary no model strength removes; the retired defenses assumed an untrusted
  repository, which the plugin no longer reviews.

### D. Certified review loop

#### D1 — Round driver core

- **Component.** The certified review loop's round driver substrate and gate; it costs ongoing
  contract maintenance and is the hub where certification drop-off is measured.
- **Condition.** Usage-based:
  - **Signal.** Post-shrink full lanes reaching certified completion, against full lanes run, read
    from the loop records the driver already writes. A full lane is a launched build lane routed to
    the full review lane whose review loop left loop records, selected by the presence of those
    records for the lane's PR. That is the unit every window and firing here counts.
  - **Window.** The first 10 post-shrink full lanes, counting this repository's lanes only.
  - **The main firing.** Completion at or below the recorded pre-shrink baseline.
  - **Companion firing, abandonment.** Fewer than 10 full lanes run within 60 calendar days
    post-shrink. It is recorded as the observation it is — lanes expected against lanes run — with
    both readings named beside it: callers routing around the loop, or no build activity in the
    window. This leg exists because a lane-counted window alone can never see a route-around.
  - **Companion firing, consumer report.** A consuming project's recorded certified-loop drop-off
    report counts as a firing at the next gardening pass. That population is excluded from the
    denominator, never from the signal.
  - **Action.** All three firings drive the same action: a retirement-or-indictment proposal to the
    owner. A companion firing is never triaged below owner visibility.
  - **Fail direction.** If the records cannot produce the number, the comparison fails toward
    alerting: any post-shrink silent certified-loop drop-off — a full lane whose handback states
    review completion with no certified receipt present — observed at any vet of a driver-surface PR
    counts as a firing.
- **Last demonstrated benefit.** unknown.
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** mixed — the parse and refusal shell is structural; the exact-token certification
  contract is capability-gap until the re-spec lands.

#### D2 — Seat map + liveness + tally

- **Component.** Deterministic panel seat-map composition, liveness cache, and tally plumbing
  (`seat_map.py`, `seat_map_receipts.py`, `liveness_cache.py`, `panel_tally.py`); it costs registry
  coupling and panel-composition CPU, and refuses same-family or unreachable seat mixes.
- **Condition.** Citation-based, 45 days: vet, forfeit-dispute, or incident receipts citing
  seat-map or liveness refusals for same-family conformance or unreachable panel cells. On firing,
  a proposal to the owner at a gardening pass.
- **Last demonstrated benefit.** Measured ~1% same-family conformance violations from the review
  corpus; fix-#787-inside-the-guard is the one queued item (the assessment record).
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** structural — deterministic composition from `model_registry` guards a build property,
  not a single vendor.

#### D3 — Loop plan/state/memory

- **Component.** This row is substrate — a proposal on it is a shrink proposal, not a deletion. The
  certified-loop plan, state, memory, and policy store (`review_loop_plan.py`, `loop_state.py`,
  `review_memory.py`, and siblings) costs contract surface and over-records relative to what the
  driver shell demands.
- **Condition.** Usage-based, 60 days: the signal is full review lanes that reach certified
  completion against full lanes run. On firing, a shrink proposal to the owner at a gardening pass.
- **Last demonstrated benefit.** unknown.
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** mixed — halt-integrity storage is structural; the 52% fix-share over-storage signature
  is capability-gap until D1's contract shrink lands.

#### D4 — Grounding seat/stage

- **Component.** The grounding-stage PR-body stager and grounding-seat charter
  (`grounding_stage.py`, `agents/grounding-seat.md`); it costs staging machinery and a seat slot,
  and is meant to grade implementer self-claims against the repo before panel review trusts them.
- **Condition.** Catch-based, 45 days: grounding-stage or grounding-seat findings that block or park
  on unsupported self-claims in a PR body or dispatch receipt. On firing, a proposal to the owner at
  a gardening pass.
- **Last demonstrated benefit.** unknown.
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** capability-gap — the stage ships without a wired caller yet; evidence is on the held
  verification set (Cursor-family orchestrators observed on weekly-eats lanes).

#### D5 — Circuit breaker + escalation

- **Component.** The review auto-fix loop circuit breaker and its escalation resolver
  (`circuit_breaker.py`, `escalation.py`, `escalation_resolve.py`); it costs recurrence tracking on
  every round and halts stuck loops that stop making progress.
- **Condition.** Citation-based, 45 days: vet, forfeit-dispute, or incident receipts citing
  circuit-breaker trips or escalation halts on a review loop that would otherwise have continued
  without progress. On firing, a proposal to the owner at a gardening pass.
- **Last demonstrated benefit.** Seven correct stuck-loop fires in one wave without blocking normal
  two-to-three-round convergence (the assessment record, keeps receipts).
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** structural — stuck-loop detection guards loop integrity independent of vendor.

#### D6 — Handback gate

- **Component.** `handback_gate.py` is on the CP2 kill list (K1) with zero shipped consumers ever;
  the row is shipped dark and collides with held PR #1254. The gate and its tests cost ~2,771 lines
  of maintenance on machinery nothing invokes.
- **Condition.** Citation-based, 45 days: vet, forfeit-dispute, or incident receipts that cite
  `handback_gate.py` or the handback refusal class after K1 retires. On firing, a proposal to the
  owner at a gardening pass.
- **Last demonstrated benefit.** unknown.
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** harness-limit — a Claude-host Bash tripwire with no wired reader; #954 audit recommends
  retire and the driver mandate (#1095) already holds the same line.

#### D7 — Verify gate

- **Component.** The code-leg verify gate that runs the project's configured verify command before a
  loop may declare clean terminal (`verify_gate.py`, `verification.py`); it costs bounded subprocess
  time on every code leg and fail-closes on fail, timeout, or execution error.
- **Condition.** Citation-based, 45 days: vet, forfeit-dispute, or incident receipts citing
  verify-gate outcomes classified `fail` or `timeout` that blocked a clean terminal the loop would
  otherwise have declared. On firing, a proposal to the owner at a gardening pass.
- **Last demonstrated benefit.** unknown.
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** structural — receipts-before-claims on the verify command is load-bearing regardless of
  host.

#### D8 — Gate-write + decisions plumbing

- **Component.** This row is substrate — a proposal on it is a shrink proposal, not a deletion. The
  gate-write handshake and decisions plumbing (`gate_write.py`, `decisions.py`,
  `coverage_decisions.py`) costs duplicated-skill maintenance; CP2 retires `gate_write.py` `certify`
  mode while `reset` and the decisions helpers keep.
- **Condition.** Usage-based, 60 days: the signal is `gate_write.py` invocations in live review-crew
  flows (`reset` mode and decisions readers). On firing, a shrink proposal to the owner at a
  gardening pass scoped to surviving members.
- **Last demonstrated benefit.** unknown.
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** mixed — `reset` and decisions plumbing are structural; legacy `certify` is
  capability-gap baggage from plan/tasks legs retired in #469.

#### D9 — Review support

- **Component.** This row is substrate — a proposal on it is a shrink proposal, not a deletion.
  Review-support helpers (`finding_identity.py`, `delta_surface.py`, `diff_scope.py`, `md_fence.py`,
  `review_code_config.py`) cost import-closure maintenance and underpin finding identity, diff
  scope, and review-code configuration across the loop.
- **Condition.** Usage-based, 60 days: the signal is review-loop modules importing or calling D9
  helpers on live lanes. On firing, a shrink proposal to the owner at a gardening pass.
- **Last demonstrated benefit.** unknown.
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** structural — finding identity and diff scope are load-bearing substrate, not optional
  polish.

#### D10 — Review lens agents

- **Component.** The machinery embedded in the review-lens product row: five lens agents plus spine
  docs (`agents/*-reviewer.md`, `review-base.md`, review-code reference tree). The row costs charter
  mass and panel dispatch time; CP2 keeps the lenses untouched and indicts routing and triage around
  them.
- **Condition.** Catch-based, 45 days: CONFIRMED review findings from a lens seat that fixed a
  defect or blocked a park. On firing, a proposal to the owner at a gardening pass.
- **Last demonstrated benefit.** Six CONFIRMED findings fixed in the 0.18.0 wave (#1247); each #1099
  lens carries a regression check against its origin escape (the assessment record).
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** mixed — lens detection is structural; deferral-heavy routing around the lenses is
  capability-gap (Cursor-family false forfeits observed on weekly-eats lanes).

### E. Board & process machinery

#### E1 — Issue contract checker (three-slot skeleton, anchor, DoD bar)

- **Component.** The advisory build-ready anchor-shape checker (`lib/issue_contract.py`) and its
  reference spine (`issue-contract.md`); it costs charter maintenance and an extra read at filing
  and vet time.
- **Condition.** Citation-based, 45 days: vet, forfeit-dispute, or incident receipts that cite the
  issue-contract anchor-shape rule — advisory, always exit 0, so zero catches are not evidence the
  shape class is gone. On firing, a proposal to the owner at a gardening pass.
- **Last demonstrated benefit.** Shipped deterministic anchor-kind checking for build-ready marking
  (#932).
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** structural — guards routed-issue body shape; no host offers build-ready marking-time
  validation.

#### E2 — register_check (epic contract quotes)

- **Component.** The register-to-child byte-exact quote guard (`lib/register_check.py`); it costs
  maintenance on the closed register grammar and runs at every child filing and package-read
  verification.
- **Condition.** Citation-based, 45 days: vet, forfeit-dispute, or incident receipts citing
  `register_check` catching register-quote text drift, missing quotes, or unknown-entry at charter
  filing or package-read verification. On firing, a proposal to the owner at a gardening pass.
- **Last demonstrated benefit.** Caught register parsing that would have blocked every child filing
  in the verification-strategy package read (#1227).
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** structural — guards byte-exact register agreement; no platform primitive compares
  quoted issue blocks to repo files.

#### E3 — package_read_audit

- **Component.** The machine-record trail convention and its completeness-and-shape checker
  (`lib/package_read_audit.py`); CP2 splits the row — the trail convention keeps, the checker
  retires on a real trail-integrity incident — and the checker costs ~2,815 LOC against a circular
  trust chain.
- **Condition.** Usage-based, 60 days: spec-package reads that write machine-record blocks per the
  trail convention — scoped to the keeping member. On firing, a shrink proposal to the owner at a
  gardening pass (not a row deletion).
- **Last demonstrated benefit.** Verification-strategy package read produced conforming machine
  records and a checked trail (#1227/ca515aa6).
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** mixed — trail convention is structural; checker is harness-limit (advisor writes,
  advisor runs check, owner reads conforming in a title per CP2 sitting).

#### E4 — Citation/exact-text validators

- **Component.** The dangling-citation detector (`lib/citation_validator.py` and its exact-text
  checker script); it is cheap, wired in review-spec compile, and guards the #205 fabricated-fact
  class with zero live catches recorded.
- **Condition.** Citation-based, 45 days: vet, forfeit-dispute, or incident receipts that cite the
  citation-validator rule's substance — zero catches mean the class may still be live, not that the
  detector is idle. On firing, a proposal to the owner at a gardening pass.
- **Last demonstrated benefit.** Made dangling spec citations mechanically catchable in review-spec
  compile (#517).
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** structural — guards spec provenance existence; no platform doc-citation validator
  exists.

#### E5 — Collector + revisit-trigger registry

- **Component.** The Tier-2 collector on issue #695 and the revisit-trigger registry pinned there,
  plus the append-always and registry rules in `owner-decisions.md`; it costs pinned-comment hygiene
  and unconditional vet-time appends.
- **Condition.** Usage-based, 60 days: Tier-2 residuals appended to the collector and
  revisit-registry rows written at vet time per the owner-decisions delivery contract. On firing, a
  proposal to the owner at a gardening pass.
- **Last demonstrated benefit.** Append-always closed the empty-collector over-filtering failure
  (owner-decisions.md, issue #695).
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** structural — complete register by construction; no mechanical gate on chat delivery.

#### E6 — Vet spine + vet-receipt contract

- **Component.** The vet-receipt shape and showrunner vet duty (`vet-receipt.md`, showrunner duty
  4); CP2 queued a simplify to trim confirmatory probe mass that drifts from the contract.
- **Condition.** Usage-based, 60 days: child PR vets that post a spine-complete vet receipt per
  `vet-receipt.md` — distinct probes, not re-run green suites. On firing, a proposal to the owner at
  a gardening pass.
- **Last demonstrated benefit.** Explicit `None` made vet absences readable instead of
  presence-by-grep (`vet-receipt.md`).
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** mixed — spine shape is structural; confirmatory probe drift is capability-gap (71%
  confirmatory mass per CP2, contract already forbids it at line 42).

#### E7 — Owner-decisions walk contract

- **Component.** The open-decisions delivery contract (`owner-decisions.md`) and the
  `/superheroes:discuss-open-decisions` skill; it costs loaded prose on every owner walk and
  enforces the per-item spine the owner corrected into existence.
- **Condition.** Usage-based, 60 days: open-decision deliveries that follow the per-item spine,
  worth-it gate, and venue ladder in `owner-decisions.md`. On firing, a proposal to the owner at a
  gardening pass.
- **Last demonstrated benefit.** Unified residual-triage vocabulary ended inconsistent disposition
  across advisor sessions (#1118).
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** structural — owner-present delivery shape; nothing mechanical gates a chat message.

#### E8 — Worth-it gate + venue ladder

- **Component.** The residual-triage prose in `owner-decisions.md` §worth-it gate and venue ladder;
  CP2 kill K6 records it superseded by the package-landing front door — real catches, zero LOC,
  registry rows inherit at ratification rather than retiring on absence evidence.
- **Condition.** Usage-based, 60 days: residual dispositions that cite the worth-it gate and venue
  ladder vocabulary until the front door ratifies and inherits the registry rows. On firing, a
  proposal to the owner at a gardening pass.
- **Last demonstrated benefit.** Unified residual triage across review, vet, and owner-decision
  surfaces (#1118).
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** structural — triage vocabulary promoted to the front door at Part B landing, not
  retired on zero catches.

#### E9 — Bite-proof doctrine + probe discipline

- **Component.** The bite-proof rule (`rubric/bite-proof.md`) and its probe-discipline records; it
  costs neutralize-red-restore-green work on every new or changed detector.
- **Condition.** Usage-based, 60 days: new or changed detectors shipped with a recorded bite-proof
  per `rubric/bite-proof.md`. On firing, a proposal to the owner at a gardening pass.
- **Last demonstrated benefit.** Red-run requirement distinguished verified detectors from
  green-only claims (bite-proof.md, PR #1159 vet 181).
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** structural — covenant fourth promise (receipts before claims) applied to detectors.

#### E10 — Charters + covenant + launch/dispatch doctrine (loaded prose mass)

- **Component.** The loaded charter and doctrine prose mass (showrunner, workhorse, detective
  SKILL.md files, covenant, launch-doctrine, dispatch-mechanics, review-discipline); CP2 queued a
  third diet pass against a 3,826-line baseline — context load on every dispatched session.
- **Condition.** Usage-based, 60 days: build, review, and advisor sessions that load the charter and
  doctrine prose. On firing, a proposal to the owner at a gardening pass.
- **Last demonstrated benefit.** unknown.
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** mixed — covenant hard lines are structural; charter mass size is capability-gap (Change
  6 meter baseline, 3,826 loaded lines per CP2).

#### E11 — Orders templates (shipped data)

- **Component.** The orders substrate row — `rubric/orders/` templates and `round_orders` renderers;
  this row is substrate, so a proposal is a shrink or split, not a deletion; it costs template and
  placeholder-contract maintenance on every certified round.
- **Condition.** Usage-based, 60 days: certified review rounds that render seat orders through
  `round_orders` from `rubric/orders/` templates. On firing, a shrink proposal to the owner at a
  gardening pass.
- **Last demonstrated benefit.** Shipped per-seat order rendering from templates with
  refuse-on-unfilled-placeholder (#723).
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** structural — load-bearing dispatch text substrate wired through `round_driver`.

### F. Config & calibration

#### F1 — Configure + calibration + modes

- **Component.** The configure-hero embedded machinery (not the skill front door): the configure
  skill, calibration routing, mode registry, and session-mode resolution across a dozen lib modules.
  It costs vocabulary maintenance every time mode semantics shift.
- **Condition.** Usage-based, 60 days: owner-invoked configure or calibration-fix runs whose
  reconcile signals still reference pre-#1151 mode vocabulary outside the single-owner pattern. On
  firing, a shrink proposal to the owner at a gardening pass.
- **Last demonstrated benefit.** Routed incomplete calibrations to fix and healthy-but-drifted
  projects to view via configure_route state sense (#1151).
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** mixed — session-mode SSOT (#1151) is structural; duplicated vocabulary across modules
  is capability-gap until consolidation lands.

#### F2 — Model governance (tiers, registry, overrides)

- **Component.** Model governance: the tier registry, override resolution, and skill-facing
  resolver. It costs table maintenance whenever a dispatch role or host model set changes.
- **Condition.** None. Foundational by the owner's look at landing; it is never queued, and
  changing it is a spec amendment. Its table-maintenance cost is weighed at a walk, not by a window.
- **Last demonstrated benefit.** unknown.
- **Consumer evidence.** unmeasured.
- **Decision.** foundational.
- **Notes.** structural — owner authority over which model runs which role; the fail-open degrade
  path is deliberate cost control.

#### F3 — Doctor/readout/CLI support

- **Component.** F3 is substrate: doctor, readout, CLI contract, identifiers, catalog, core_md, and
  hostinfo helpers, so a proposal on it is a shrink or split, not row deletion. The identifiers.py
  content_hash half and the cli_contract census pair are already slated to retire (K4, sitting
  ruling).
- **Condition.** Usage-based, 60 days: live imports of the retiring members (identifiers
  content_hash, cli_contract census helpers) after their retirement lands. On firing, a shrink
  proposal to chase stragglers at a gardening pass.
- **Last demonstrated benefit.** core_md carried five real calibration hardenings with eighteen live
  consumers (the assessment record, F3 split verdict).
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** mixed — core_md is structural substrate; the census-pair and content_hash vestige are
  capability-gap machinery scheduled for deletion.

### G. CI validators & the test estate

#### G1 — CI validators (7 scripts)

- **Component.** The seven CI validator scripts under `.github/scripts/` (validate_* and check_*).
  They cost a few CI seconds each run. check_release_bump is best-evidenced; validate_marketplace
  and the other never-fired members are keep-cheap with attached conditions.
- **Condition.** Citation-based, 45 days: vet, forfeit-dispute, or incident receipts citing real
  catches from the never-fired members (validate_marketplace, validate_hosts, validate_skills,
  check_conventional_commit, check_catalog_membership; check_release_bump excluded because it has a
  100% incident record). On zero citations for the full window across all never-fired members, a
  retirement proposal for those members at a gardening pass.
- **Last demonstrated benefit.** check_release_bump caught release-please silent version drops
  across three incidents (investigation-record.md / the assessment record).
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** mixed — check_release_bump is structural (release-blocking-quiet class); never-fired
  validators are harness-limit guards on cheap static checks.

#### G2 — Rail lane (doc↔code drift tests, censuses, drift pins)

- **Component.** The rail-lane detector: test_ssot_drift.py and the rail-census-v3 pinned set (53
  files). It costs suite mass and drift-pin maintenance whenever a doc↔code mirror moves.
- **Condition.** Citation-based, 45 days: a named-edit record removing a rail inventory entry
  without cannot-bite evidence and owner approval (the retention-doctrine bar for rails). On firing,
  a proposal to enforce the bar at a gardening pass; zero violations means the rails are holding.
- **Last demonstrated benefit.** The four rails are the suite's recorded foreign-regression provers
  (the assessment record, G2 ruling (a)).
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** structural — rails prove doc↔code SSOT; natural shrink expected as Change 7 deletes
  mirrors.

#### G3 — Behavior-lane test suite (~14k cases)

- **Component.** The behavior-lane test mass: everything under `*/tests/` outside the rail lane
  (~14k cases, ~230k LOC). It costs 18.6× CI wall-time growth and ongoing pin maintenance; scored by
  retention-doctrine class, not by individual case.
- **Condition.** Catch-based, 45 days: per retention-doctrine class (cannot-bite, birth-red,
  regression-catch, count-pin, byte-pin, and the remainder), count CI regression-catches
  attributable to that class. On a class accumulating zero regression-catches for the full window, a
  trim proposal for that class at a gardening pass.
- **Last demonstrated benefit.** Birth-red catches on every PR that ships broken tests; bulk-removal
  classes start with 33 named cannot-bite tests (the assessment record, G3 simplify / #1105).
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** mixed — birth-red and cannot-bite trimming are structural suite hygiene; count-pin and
  byte-pin conversion is capability-gap debt from over-pinning.

#### G4 — Stub-marker validation

- **Component.** Stub-marker validation: stub_markers.py and validate_stubs.py. It costs a full-tree
  scan on every CI run to keep deliberately unwired seams tracked to issues.
- **Condition.** Usage-based, 60 days: count of live `STUB(#NNN)` markers in the tree
  (validate_stubs.py find_violations surface). On zero live markers for the full window, a
  retirement proposal at a gardening pass.
- **Last demonstrated benefit.** Enforces the no-silent-stubs convention so every placeholder names
  a tracked issue (#228 / stub_markers.py module docstring).
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** structural — tracked stubs are the contract for deliberate unwiring; the validator
  retires when nothing remains to validate.

### H. Product heroes

#### H1 — Guardian (audit hero; has real catch receipts)

- **Component.** The Guardian hero's embedded machinery (not the skill front door): seventeen
  guardian_*.py modules, lenses, sweep pipeline, store, and report. It costs collector maintenance
  and lens registration sync; the hero milestone is held until one sweep produces a consumed output.
- **Condition.** Usage-based, 60 days: a completed sweep→validate→file cycle whose report card or
  filed issue is recorded as consumed (not merely generated). On zero consumed outputs for the full
  window, a proposal to shrink hardening scope at a gardening pass.
- **Last demonstrated benefit.** unknown.
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** capability-gap — readers exist by design but recorded consumption is zero
  (the assessment record, H1 posture, one sweep with zero validated findings).

#### H2 — Test-pilot (framework A1–D11)

- **Component.** The test-pilot hero's embedded machinery (not the skill front door): ~30 pilot_*.py
  modules, the seeding engine, and pilot-contract guards. It costs the highest August fix share
  among dispatch surfaces.
- **Condition.** Citation-based, 45 days: vet, forfeit-dispute, or incident receipts citing real
  pilot-framework catches in CI or dispatch receipts (contract refusal, block-execution failure,
  plan or schema mismatch). On firing, a proposal to the owner at a gardening pass.
- **Last demonstrated benefit.** unknown.
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** structural — the A1–D11 contract is load-bearing orchestration machinery; churn
  evidence observed on engine-7-class dispatches at weekly-eats (the assessment record, C1/H2).

#### H3 — Other heroes (architect, discovery, detective, review-spec, audit-debt, checkpoint…)

- **Component.** The other-heroes embedded machinery (not their skill front doors): architect,
  discovery, detective, review-spec, audit-debt, and checkpoint skills plus supporting lib hooks. It
  costs loaded prose mass across the skill tree.
- **Condition.** Citation-based, 45 days: vet, forfeit-dispute, or incident receipts citing a
  specific other-hero skill dispatch failure (routing, charter drift, missing reference). On firing,
  a proposal to the owner at a gardening pass; zero citations means the heroes are holding.
- **Last demonstrated benefit.** unknown.
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** mixed — review-spec and architect discovery are structural product surfaces;
  thin-evidence members (#541 landed) wait on Change-3 conditions per member.

#### H4 — Eval harness

- **Component.** The eval-harness embedded machinery (not a scored product): eval/,
  plugins/superheroes/eval/, and band-level activation gates. It costs fixture and golden
  maintenance; the defect is missing operating structure, not unwanted evals.
- **Condition.** Usage-based, 60 days: recorded benchmark or activation-gate runs whose results
  attach as release evidence (reader = owner at release click). On zero recorded runs for the full
  window, an operating-structure proposal at a gardening pass.
- **Last demonstrated benefit.** v1 A/B harness produced a green improved≥baseline gate at the
  0.14.0-era baseline (plugins/superheroes/eval/RESULTS.md).
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** harness-limit — release evidence wants benchmarks but no cadence has run since 0.14.0
  against 0.32.0 current (the assessment record, H4 reframing).

### Supplemental entries

#### S1 — Dispatch stdout cap

- **Component.** Not a census row. The engine write dispatch stdout capture cap in
  `engine_dispatch.py` (`MAX_STDOUT_CAPTURE`, 8 MiB): when engine stdout exceeds the budget, the
  terminal forfeit carries `stdout-capped-by-attempt` and declared-item grading never runs on work
  that already landed.
- **Condition.** Citation-based, 45 days: vet, forfeit-dispute, or incident receipts that cite the
  stdout capture cap or `stdout-capped-by-attempt` as the loss mechanism — a zero count means long
  dispatches are staying inside the budget, not that the cap is gone. On firing, a proposal to the
  owner at a gardening pass.
- **Last demonstrated benefit.** Separated stdout-cap truncation from `worktree-dirtied-by-attempt`
  so a long implementer report forfeits with an explicit cap reason instead of a dirtied-worktree
  misread (dispatch hardening class, `dispatch-mechanics.md`).
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** harness-limit — external engines paste long receipts; the cap bounds what the runner
  can grade (Cursor-family implementers observed on weekly-eats dispatches).

#### S2 — Dispatch salvage paths

- **Component.** Not a census row. The salvage recoveries when a dispatch ends in a forfeit but left
  a readable artifact: review `forfeit-with-engaged-artifact` salvage, write-report salvage
  (structured tail and prose tier), and `report-missing-items-delivered` work-on-disk doctrine
  (`engine_dispatch.py`, `engine_adapter.py`, `dispatch-mechanics.md`).
- **Condition.** Citation-based, 45 days: vet, forfeit-dispute, or incident receipts that cite a
  salvage block or manual artifact read recovering work from a terminal forfeit. On firing, a
  proposal to the owner at a gardening pass.
- **Last demonstrated benefit.** Recovered engaged review stdout and on-disk implementer work when
  transport grading forfeited after files landed (field record in `dispatch-mechanics.md`: three
  builds in one wave, four of six dispatches with correct files on disk).
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** harness-limit — salvage exists because engine stdout and host turn limits destroy
  gradeable reports while work survives on disk (Cursor `NonRetriableError` class).

#### S3 — Dirty-tree probe

- **Component.** Not a census row. The sibling-worktree baseline snapshot at `dispatch-write` open
  and the terminal `siblingWorktrees` fold (`sibling_worktree_probe.py`, `engine_dispatch.py`): an
  unattributed observed delta on other registered worktrees while a write run is open, not an escape
  claim.
- **Condition.** Citation-based, 45 days: vet, forfeit-dispute, or incident receipts that cite the
  sibling-worktree observation or its baseline when disambiguating a worktree-dirtied forfeit — a
  zero count means no dispute needed the observation, not that concurrent worktrees stopped
  existing. On firing, a proposal to the owner at a gardening pass.
- **Last demonstrated benefit.** Guards false worktree-dirtied forfeits with a wired reader on every
  terminal dispatch fold (the assessment record, B5 qualified-keep record; zero recorded catches).
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** harness-limit — the host offers no native worktree-liveness signal; the observation is
  advisory only and never changes `ok`.

#### S4 — Project configuration registry and view

- **Component.** Not a census row. The closed registry of the thirteen configuration items, their
  plugin defaults and fail directions, the four declared dependencies, and the configure view's
  project-configuration block (`project_config.py`, `configure_view.py`, the two surgical writers in
  `core_md.py`). It costs registry maintenance whenever an item, a default, or a dependency changes.
- **Condition.** Usage-based, 60 days: configure-view runs and item writes that reach the registry,
  read from the profile's edit history and the configure receipts. On firing, a proposal to the
  owner at a gardening pass. The detectors this component carries keep their recorded bite-proofs
  (`lib/tests/bite_proofs/wo_*_1276_*.md`), which are their birth receipts.
- **Last demonstrated benefit.** Every item written to its one home with every sibling field
  byte-identical, and the exactly-five-defaults count held by a test proved red (the
  configuration-items child's build record).
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** structural — one home per item is what stops a second copy of a default drifting; the
  registry's closed enumeration is the coverage.

#### S5 — Front-door helper

- **Component.** Not a census row. The grading helper that refuses a P0 or P1 claim, and queues a
  cleared P2 instead of filing, when the project has no stamped severity ladder
  (`front_door.py`). It costs one profile read per graded claim.
- **Condition.** Citation-based, 45 days: vet, walk, or incident receipts citing a door refusal
  (`ladder-unstamped`, `band-unknown`, `evidence-argued`, `p0-band-excluded`) that stopped a filing
  from expanding its own authority. On firing, a proposal to the owner at a gardening pass. A zero
  citation count means no filing tried to claim a band it could not cite, not that the door can go.
- **Last demonstrated benefit.** Recorded refusals on a throwaway profile with no ladder, and the
  advisor's own probe at vet reproducing every refusal (the configuration-items child's build
  record and its vet receipt).
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** structural — a door that falls open is the quiet class; the fail direction is a
  property of how the front door is built, not of any model.

#### S6 — Kind labels at calibration

- **Component.** Not a census row. Idempotent creation of the two `kind:` labels on a repository
  that lacks them (`kind_labels.py`). It costs one label list and at most two label creates per
  calibration.
- **Condition.** Usage-based, 60 days: calibrations on repositories that lacked a label, read from
  the configure receipts. On firing, a proposal to the owner at a gardening pass. Once every
  calibrated repository carries both labels, a zero count is expected and reads as done, not as
  retire.
- **Last demonstrated benefit.** Both labels created on this repository through the helper's own
  argv, with an existing label's colour and description never reconciled away (the
  configuration-items child's build record).
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** capability-gap — a person could create two labels by hand; the helper exists so the
  routing vocabulary is present before the first issue is routed.

#### S8 — Seat-bundle entry chokepoint

- **Component.** Not a census row. `seat_bundle.resolve_entry` in `plugins/superheroes/lib/seat_bundle.py`:
  the one resolver every dispatch entry path routes through (`dispatch-review`, `dispatch-write`,
  brief-check mode, `dispatch_guard check`, and the command-builder CLI). It validates a caller's
  seat bundle in a fixed leg order — the role is real, the role agrees with the mode, the role
  agrees with the verb, the model and effort are valid for that vendor, and only then the
  allowlist — and refuses with text naming what would have been accepted. Its cost is that every
  new entry path must route through it rather than reading seat fields itself. Open PR #1286 takes
  S7; whichever of the two PRs lands second renumbers.
- **Condition.** Citation-based, 45 days: vet, forfeit-dispute, or incident receipts citing a
  chokepoint refusal (`legacy-seat-args`, `seat-token-dropped`, `unknown-role`, `mode-role-mismatch`,
  `verb-role-mismatch`, `invalid-model-effort`, `allowlist-refused`) that stopped a dispatch from
  running a seat it was not entitled to. On firing, a proposal to the owner at a gardening pass. A
  zero citation count means no dispatch tried an unauthorized seat past the chokepoint, not that the
  gate can go.
- **Last demonstrated benefit.** Before the chokepoint, the seat's registry role was a separate
  argument every caller decided independently and four of them decided wrong; the chokepoint made
  one function the only place that decides (this child's build record on PR #1283 and the bite-proof
  record `plugins/superheroes/lib/tests/bite_proofs/wo_1269_chokepoint.md`).
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** structural — a single entry resolver guards how dispatch seats are authorized; a zero
  citation count means callers are not attempting unauthorized seats, not that bypass paths vanished.

#### S9 — Spawn-time allowlist gate

- **Component.** Not a census row. The spawn-time allowlist re-validation in
  `plugins/superheroes/lib/engine_dispatch.py`: `_spawn_allowlist_verdict` re-validates the seat
  from the journal's stored `resolvedInputs` snapshot before any engine process starts, and the
  argv that runs is derived from that validated snapshot rather than stored separately alongside
  it. A safety refusal at this gate folds as a terminal refusal returned to the caller, not as an
  engine forfeit. Its cost is that a journal written before the snapshot existed refuses rather
  than spawning.
- **Condition.** Citation-based, 45 days: vet, forfeit-dispute, or incident receipts citing a
  spawn-gate refusal (`run seat cannot be established`, `spawn argv does not match resolvedInputs
  snapshot`, or an allowlist refusal replayed from the journal seat snapshot) or an argv/snapshot
  divergence caught at spawn. On firing, a proposal to the owner at a gardening pass. A zero
  citation count means no continuation, retry, or run-child re-entry slipped the entry gate, not
  that the spawn gate can go.
- **Last demonstrated benefit.** It closed the paths that had slipped the entry gate — the
  continuation spawn, the retry attempt, and the run-child re-entry all re-read the journal seat
  instead of trusting caller argv (this child's build record on PR #1283 and
  `plugins/superheroes/lib/tests/bite_proofs/wo_10_1269_spawn_gate.md`).
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** structural — spawn-time re-validation guards argv coherence independent of which
  engine family runs the seat.

#### S10 — Entry-doc determinism guard

- **Component.** Not a census row. `plugins/superheroes/lib/dispatch_entry_doc.py --check`, which
  regenerates the entry doc from the dispatch shell's own argparse declarations and refuses when
  the committed `plugins/superheroes/skills/workhorse/reference/dispatch-entry.md` differs from a
  fresh generation, plus the cross-process determinism test that guards it. Its cost is that any
  change to a dispatch flag's declaration requires regenerating the doc in the same change.
- **Condition.** Citation-based, 45 days: vet, forfeit-dispute, or incident receipts citing the
  `--check` refusal (`is stale` or `is missing`) catching a doc that had drifted from the
  declarations. On firing, a proposal to the owner at a gardening pass. A zero citation count
  means the doc and the declarations have stayed together, not that the guard can go.
- **Last demonstrated benefit.** The generated doc had embedded a Python object address, so it
  could not be regenerated identically; the sentinel now renders in the doc's own vocabulary and a
  cross-process determinism test guards it (this child's build record on PR #1283 and
  `plugins/superheroes/lib/tests/bite_proofs/wo_9_1269_doc_determinism.md`).
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** structural — doc generated from argparse declarations guards declaration drift by
  construction; a zero citation count means no drift reached commit, not that drift is impossible.

#### S11 — Entry-refusal reason census

- **Component.** Not a census row. The closed `ENTRY_REFUSAL_REASONS` vocabulary in
  `plugins/superheroes/lib/seat_bundle.py` and the behavioural census in
  `plugins/superheroes/lib/tests/test_engine_dispatch.py` that iterates it against
  `_entry_refusal_terminal` with and without an opened run, plus the chokepoint refusal for
  undeclared reasons (`entry-reason-undeclared`). Its cost is that every new outward entry-refusal
  reason must be added to the declared set before it can pass the chokepoint.
- **Condition.** Citation-based, 45 days: vet, forfeit-dispute, or incident receipts citing an
  `entry-reason-undeclared` refusal that caught a reason outside the declared vocabulary before
  dispatch ran. On firing, a proposal to the owner at a gardening pass. A zero citation count
  means no undeclared reason reached the chokepoint, not that the census can go.
- **Last demonstrated benefit.** The hand-maintained audited-functions list in the syntactic census
  could not see a new refusal path; the declared set plus chokepoint refusal closed that gap (this
  child's build record and `plugins/superheroes/lib/tests/bite_proofs/wo_census_1269.md`).
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** structural — a closed reason vocabulary with chokepoint enforcement guards entry-refusal
  completeness by construction; a zero citation count means callers are not hitting undeclared
  reasons, not that new paths cannot forget to declare. Retired the syntactic AST call-graph census
  (`test_entry_refusal_chokepoint_invariant_returns_trace_to_approved_producers` and helpers) because
  its hand-maintained audited-functions list was invisible to new refusal paths.


## The workaround-marker inventory

A platform workaround in this tree carries the marker `WORKAROUND:` in a comment, immediately
followed by a `delete-when:` line naming the [delete-when
condition](../../plugins/superheroes/rubric/glossary.md#delete-when-condition) that makes it removable.
When the condition comes true, the workaround is promoted into a real fix or removed, never left as
unmarked ritual. A gardening pass reports the markers whose condition has come true. The inventory
below lists every marked site in the tree, and a grep for the tag over the tree, excluding this
file, returns exactly that set.

- `.github/scripts/validate_hosts.py` — portable plugin-root seam and host-map lint for dual-host
  skill prose. **delete-when:** every host resolves plugin root through one variable without this
  fallback seam.
- `.github/scripts/validate_skills.py` — CI lint enforces the portable plugin-root seam on skill
  reference paths. **delete-when:** every host resolves plugin root through one variable without
  this fallback seam.
- `plugins/superheroes/hooks/bash_timeout.py` — PreToolUse Bash timeout floor when the model omits
  an explicit timeout. **delete-when:** the host Bash tool defaults to at least 600 s without a
  PreToolUse rewrite hook.
- `plugins/superheroes/lib/build_lane.py` — build-lane sidecar marker so the receipt gate can arm
  before review starts. **delete-when:** the host session carries build scope without a
  build-lane.json sidecar file.
- `plugins/superheroes/lib/core_md.py` — the profile schema stays at 2 while it carries the
  project-configuration keys an older build does not know, so an older build re-calibrating from
  scratch can drop them. **delete-when:** the keep list is stamped and a release carrying the
  configuration items has shipped; then the version is raised with the new literal pinned in the
  tests rather than referenced from the constant. (Lands with the configuration-items child; the
  tree carries this marker once that child merges.)
- `plugins/superheroes/lib/harness_probe.py` — tripwire that native project-context injection still
  holds on every spawn path. **delete-when:** every spawn path is confirmed and recorded without
  this probe, or the probe retires.
- `plugins/superheroes/lib/hostinfo.py` — OS-specific boot-id reads to corroborate a recorded pid
  belongs to this boot. **delete-when:** the host exposes a stable per-boot identity without
  OS-specific parsing.
- `plugins/superheroes/lib/launch_doctrine.py` — machine parser for launch doctrine prose the host
  does not supply natively. **delete-when:** the host injects launch rulings and preflight checks
  without a parsed artifact.
- `plugins/superheroes/lib/launch_ledger.py` — file-backed launch batch ledger when the host has no
  durable batch accounting. **delete-when:** the host records launch batches durably without this
  ledger module.
- `plugins/superheroes/lib/launcher.py` — headless builders must survive parent session exit via
  detached spawn. **delete-when:** the background-session trial receipt marks detached spawn not
  needed.
- `plugins/superheroes/lib/launcher.py` — launcher refuses spawn when cwd is the primary checkout
  (own-worktree). **delete-when:** the background-session trial receipt marks launcher worktree
  enforcement not needed.
- `plugins/superheroes/lib/pilot_conformance_runtime.py` — env-var transport of connection detail
  across multi-account ownership probes. **delete-when:** the background-session trial receipt marks
  multi-account provisioning transport not needed.
- `plugins/superheroes/lib/sibling_worktree_probe.py` — sibling worktree snapshot probe when
  dispatch fold cannot attribute dirt. **delete-when:** dispatch fold attributes sibling worktree
  changes without a snapshot probe.
- `plugins/superheroes/lib/wave_watch.py` — loop re-arms wave_watch run because there is no durable
  batch watcher daemon. **delete-when:** the background-session trial receipt marks wave-watch
  arming not needed.
- `plugins/superheroes/lib/wave_watch.py` — transcript file mtime as lane liveness when idle signals
  are unreliable. **delete-when:** the background-session trial receipt marks transcript-mtime
  liveness not needed.
- `plugins/superheroes/skills/showrunner/reference/wave-watch.md` — harness background-task arming
  pattern with manual re-arm after each event. **delete-when:** the background-session trial receipt
  marks wave-watch arming not needed.
- `plugins/superheroes/skills/workhorse/reference/dispatch-mechanics.md` — 540 s continuation and
  short launch slice recipes for turn-end survival. **delete-when:** the background-session trial
  receipt marks turn-end slice recipes not needed.
