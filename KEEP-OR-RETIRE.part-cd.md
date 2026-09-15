<!-- covers: C1, C2, C3, C4, C5, C6, D2, D3, D4, D5, D6, D7, D8, D9, D10, S1, S2, S3 -->

#### C1 — Dispatch core

- **Component.** This row is substrate — a proposal on it is a shrink proposal, not a deletion.
  The cross-vendor dispatch stack (`engine_dispatch.py`, adapters, authz, prefs) costs ongoing
  contract maintenance and measured caller-facing refusal churn; CP2 directs a shrink of the
  entry/argument shell while the parse/scrub/forfeit-grading boundary stays tight.
- **Condition.** Usage-based, 60 days: the signal is terminal `dispatch-write` and
  `dispatch-review` runs graded through the core. On firing, a shrink proposal to the owner at a
  gardening pass.
- **Last demonstrated benefit.** Blocked silent inference of load-bearing dispatch params — the
  #839 specimen — and closed fail-open grading on malformed engine output at the parse boundary
  (#1010 empty-object class) (cp2-scoreboards.md).
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** mixed — the parse/scrub/forfeit shell is structural; the caller-facing refusal
  surface is capability-gap until tolerant reading pairs with deterministic echo.

#### C2 — Dispatch grading & self-test

- **Component.** Pre-dispatch model allowlist grading and dispatch self-test guards
  (`dispatch_guard.py`, `dispatch_outcome.py`, `dispatch_selftest.py`); they cost a CLI round-trip
  on every external dispatch and block unlisted models before spawn.
- **Condition.** Catch-based, 45 days: refusals where `dispatch_guard.py check` blocks an
  unlisted or misconfigured engine/model before spawn. On firing, a proposal to the owner at a
  gardening pass.
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
- **Condition.** Catch-based, 45 days: preflight `aggregate` outcomes that block a go/no-go with
  `ok: false` on a probe the build would otherwise have launched against. On firing, a proposal to
  the owner at a gardening pass.
- **Last demonstrated benefit.** unknown.
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** structural — fail-loud go/no-go before dispatch is load-bearing wave hygiene.

#### C4 — Forfeit ledger

- **Component.** The durable forfeit ledger and attribution decider (`forfeit_ledger.py`); it costs
  disk rows and gardening-pass read time, and records every terminal dispatch with telemetry and
  attribution outside the session that produced it.
- **Condition.** Usage-based, 60 days: the signal is `forfeit_ledger.py report` reads or gardening
  pass rows that cite a ledger path when attributing a dispatch forfeit. On firing, a proposal to
  the owner at a gardening pass.
- **Last demonstrated benefit.** unknown.
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** structural — the ledger is a record, never a control input; absence of reads is not
  proof it is unused.

#### C5 — Payload/findings contracts

- **Component.** Declared per-seat payload contracts and the review-findings schema guards
  (`payload_contracts.py`, `review_findings_schema.py`); they cost layering maintenance at the seam
  between round phases and engine transport, and refuse unreadable or schema-drifting seat output.
- **Condition.** Catch-based, 45 days: terminal dispatch refusals graded `unreadable` or
  schema-blocked on review payload shape. On firing, a proposal to the owner at a gardening pass.
- **Last demonstrated benefit.** Closed the #949 outer-envelope fail-open class where empty or
  control-wrapped findings could certify clean (`engine_adapter.py` gate, #1145 hardening).
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** structural — the contract guards transport gradeability independent of seat honesty.

#### C6 — Sanitized view

- **Component.** The disposable git export that strips agent/IDE config before external review reads
  (`sanitized_view.py`); it costs export time and temp disk on every sanitized review dispatch, and
  blocks config-path exfiltration from untrusted repos.
- **Condition.** Catch-based, 45 days: refusals or withheld-path receipts where sanitized export
  blocked a config leak or export failure. On firing, a proposal to the owner at a gardening pass.
- **Last demonstrated benefit.** Reproduced and blocked a config-path exfiltration attempt during
  sanitized review export (cp2-scoreboards.md keeps receipts).
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** structural — stripping untrusted-repo config is a host-trust boundary, not a model
  behaviour.

#### D2 — Seat map + liveness + tally

- **Component.** Deterministic panel seat-map composition, liveness cache, and tally plumbing
  (`seat_map.py`, `seat_map_receipts.py`, `liveness_cache.py`, `panel_tally.py`); it costs registry
  coupling and panel-composition CPU, and refuses same-family or unreachable seat mixes.
- **Condition.** Catch-based, 45 days: seat-map or liveness refusals for same-family conformance or
  unreachable panel cells. On firing, a proposal to the owner at a gardening pass.
- **Last demonstrated benefit.** Measured ~1% same-family conformance violations from the review
  corpus; fix-#787-inside-the-guard is the one queued item (cp2-scoreboards.md).
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** structural — deterministic composition from `model_registry` guards a build property,
  not a single vendor.

#### D3 — Loop plan/state/memory

- **Component.** This row is substrate — a proposal on it is a shrink proposal, not a deletion.
  The certified-loop plan, state, memory, and policy store (`review_loop_plan.py`, `loop_state.py`,
  `review_memory.py`, and siblings) costs contract surface and over-records relative to what the
  driver shell demands.
- **Condition.** Usage-based, 60 days: the signal is full review lanes that reach certified
  completion against full lanes run. On firing, a shrink proposal to the owner at a gardening pass.
- **Last demonstrated benefit.** unknown.
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** mixed — halt-integrity storage is structural; the 52% fix-share over-storage
  signature is capability-gap until D1's contract shrink lands.

#### D4 — Grounding seat/stage

- **Component.** The grounding-stage PR-body stager and grounding-seat charter
  (`grounding_stage.py`, `agents/grounding-seat.md`); it costs staging machinery and a seat slot,
  and is meant to grade implementer self-claims against the repo before panel review trusts them.
- **Condition.** Catch-based, 45 days: grounding-stage or grounding-seat findings that block or
  park on unsupported self-claims in a PR body or dispatch receipt. On firing, a proposal to the
  owner at a gardening pass.
- **Last demonstrated benefit.** unknown.
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** capability-gap — the stage ships without a wired caller yet; evidence is on the held
  verification set (Cursor-family orchestrators observed on weekly-eats lanes).

#### D5 — Circuit breaker + escalation

- **Component.** The review auto-fix loop circuit breaker and its escalation resolver
  (`circuit_breaker.py`, `escalation.py`, `escalation_resolve.py`); it costs recurrence tracking
  on every round and halts stuck loops that stop making progress.
- **Condition.** Catch-based, 45 days: circuit-breaker trips or escalation halts on a review loop
  that would otherwise continue without progress. On firing, a proposal to the owner at a gardening
  pass.
- **Last demonstrated benefit.** Seven correct stuck-loop fires in one wave without blocking normal
  two-to-three-round convergence (cp2-scoreboards.md keeps receipts).
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
- **Notes.** harness-limit — a Claude-host Bash tripwire with no wired reader; #954 audit
  recommends retire and the driver mandate (#1095) already holds the same line.

#### D7 — Verify gate

- **Component.** The code-leg verify gate that runs the project's configured verify command before a
  loop may declare clean terminal (`verify_gate.py`, `verification.py`); it costs bounded subprocess
  time on every code leg and fail-closes on fail, timeout, or execution error.
- **Condition.** Catch-based, 45 days: verify-gate outcomes classified `fail` or `timeout` that
  block a clean terminal the loop would otherwise have declared. On firing, a proposal to the owner
  at a gardening pass.
- **Last demonstrated benefit.** unknown.
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** structural — receipts-before-claims on the verify command is load-bearing regardless
  of host.

#### D8 — Gate-write + decisions plumbing

- **Component.** This row is substrate — a proposal on it is a shrink proposal, not a deletion.
  The gate-write handshake and decisions plumbing (`gate_write.py`, `decisions.py`,
  `coverage_decisions.py`) costs duplicated-skill maintenance; CP2 retires `gate_write.py`
  `certify` mode while `reset` and the decisions helpers keep.
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
  lens carries a regression check against its origin escape (cp2-scoreboards.md).
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** mixed — lens detection is structural; deferral-heavy routing around the lenses is
  capability-gap (Cursor-family false forfeits observed on weekly-eats lanes).

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
  misread (#1109 hardening class, `dispatch-mechanics.md`).
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
  terminal dispatch fold (cp2-scoreboards.md B5 qualified-keep record; zero recorded catches).
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** harness-limit — the host offers no native worktree-liveness signal; the observation
  is advisory only and never changes `ok`.
