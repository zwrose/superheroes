# Changelog — review-crew

All notable changes to the `review-crew` plugin. Versions follow
[SemVer](https://semver.org); entries follow
[Keep a Changelog](https://keepachangelog.com).

## [Unreleased]

### Added

- **Codex host support.** `.codex-plugin` manifest, `hosts/` tool maps (`claude-tools.md` and `codex-tools.md`), and neutral-language skills — all six `SKILL.md` files swept to remove Claude-specific dispatch tokens (`subagent_type`, "the Agent tool") and replace bare `${CLAUDE_PLUGIN_ROOT}` with the portable seam `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}`. Each skill now includes a host-map pointer and a Codex dispatch note so the plugin runs first-class on both Claude Code and Codex.

### Fixed

- **Gate-integrity — `gate_write.py` certify now fails loud.** A `certify` that produces a
  verdict but cannot record it (`skipped:lib-absent`, `skipped:noncanonical`, `failed:set-gate`)
  now exits **non-zero (3)** instead of 0. Leaving the gate at `pending` is indistinguishable
  from "no review ran", which the-architect's self-certify branch would otherwise upgrade to
  `passed` — a green gate with no real review. `reset` mode is unchanged (advisory revoke-only;
  always exits 0). Regression coverage in `test_gate_write.py`.

## [0.6.0] — 2026-06-18

### Added

- **Model-tier wrapper.** `lib/model_tier_resolve.py` — resolves role→dispatch-model
  via the shared the-architect core (fail-OPEN to an embedded default). review-code
  now dispatches its five specialists, triage, and fixer at the resolved tiers.
- **Machine-readable review terminal state.** `lib/review_result.py` + review-code's
  optional `--result-file` — writes the loop's terminal `loop_state` decision
  (`action`/`round`/`reason`) as JSON so a programmatic caller (e.g. the workhorse
  producer's ② gate) can branch deterministically; the reader fails CLOSED
  (missing/garbled → `halt` → GATE).

### Changed

- **`escalation_resolve` band-roots now include `workhorse`**, so an in-repo dogfood
  anchors the safety-machinery guard against the workhorse plugin dir too.

## [0.5.0] — 2026-06-16

### Changed

- **Escalation now follows the shared `escalation-base.md` rubric (F5), replacing the interim F4
  severity-gate.** review-code and the trio's step-7 present-set GATE only **owner-weighable**
  blockers; everything else is verify-and-proceed. A believed false-positive is a **recorded skip**
  (never silently dropped), so `loop_state`'s arithmetic is preserved — pinned by a
  disposition-pipeline property test. audit-debt issue-filing is now NOTIFY, not a blocking ask.

### Added

- `lib/escalation_resolve.py` — review-crew-local wrapper (resolve via `architect_lib` → subprocess
  the-architect's `escalation.py` → fail-closed-conservative degradation).
- `architect_lib.resolve_target()` — generalized cross-plugin resolution (escalation lib + rubric).
- A **fixer file-scope guard** refusing edits to the safety-machinery set; escalation eval (layer-1
  deterministic gate + layer-2 calibration).

## [0.4.0] — 2026-06-16

### Added

- **The review trio** — `review-spec`, `review-plan`, `review-tasks`: red-team
  the-architect's spec/plan/tasks definition-docs with the same five specialists
  (reframed per artifact), in a single-pass-with-revise loop. `review-plan` /
  `review-tasks` are **certifying** (record `gates.review: passed` /
  `changes-requested` via the-architect's lib); `review-spec` is **advisory** — it
  never grants the gate (the owner approves the spec in Discovery), only resets a
  *stale* approval to `pending`.
- **`lib/architect_lib.py`** — cross-plugin resolver that locates the-architect's
  `definition_doc.py` (in-repo → installed marketplace sibling → fail-closed), so
  the certifying gate is reachable in a shipped band, not only the monorepo.
- **`lib/gate_write.py`** — the trio's gate-write handshake in one tested place
  (certify / reset modes; canonical-path guard; parent-gate precondition;
  degrade-not-crash; stdlib-only) + `test_gate_write.py`.
- **`lib/loop_state.py`** — a deterministic loop-continuation gate, the symmetric
  partner to `circuit_breaker`: from the round's facts it emits the one mandatory
  next action (`review` / `exit_clean` / `exit_skipped` / `halt`), derived from the
  round artifacts so the model can't self-report — closing the long-standing "skip
  the auto-fix loop's mandatory re-review" defect. Wired into `review-code` and the
  trio's revise loops, with `test_loop_state.py` + `test_loop_gate_wired.py`.

### Changed

- **Escalation is now severity-gated.** `review-code` and the trio no longer ask the
  owner to ratify Minor/Nit findings — only blocking (Critical/Important) Skip/Defer
  or judgment-fix decisions are escalated. Minor/Nit are auto-handled per the triage
  recommendation and listed in the end-of-run summary.

## [0.3.0] — 2026-06-11

### Added

- **`premortem-reviewer`** — a fifth bundled agent (dimension `Failure-Mode`)
  using inverse reasoning ("assume it shipped and failed") over a named
  failure-class taxonomy: `concurrency/race`, `partial-failure`,
  `dependency-failure`, `resource-exhaustion`, `migration-rollback`,
  `detectability`, `assumption-violation` (plan-time). Dispatched by
  `review-plan` and `review-code` (always-on, full verdict weight);
  `audit-debt` intentionally stays at the original four.
- review-plan: **Failure-handling statement** plan-content requirement
  (multi-step writes / outbound dependencies / migrations must state their
  mid-failure behavior).
- Eval: two premortem-only single-variant fixtures (`failure-modes` recall,
  `failure-modes-bait` FP-traps) with mechanical bars and liveness smokes;
  scorer windows for the whole-flow Failure-Mode classes; structural
  dispatch-table tests (`lib/tests/test_dispatch_tables.py`).

### Changed

- `security-reviewer`: Critical findings must include a concrete attack
  construction in `evidence` (Low confidence when it cannot be written down).
- `test-reviewer`: mutation-survival findings must propose the specific test
  case that kills the mutant (setup, input, exact assertion).
- `code-reviewer` / `architecture-reviewer`: reciprocal carve-outs deferring
  systemic failure chains to the premortem-reviewer.
- Base rubric: dimension list gains `Failure-Mode`; `rubric-version` 2 → 3
  (existing profiles will see the non-blocking staleness nudge).

## [0.2.0] — 2026-06-07

### Added

- Per-project profile/decisions storage choice: **in-repo** (committed,
  team-shared) or **global** (`~/.claude/review-crew/`, zero working-tree
  footprint, shared across all git worktrees of a repo). Chosen once at first
  use via a halt-and-ask prompt; overridable with `REVIEW_CREW_STORAGE`.
- `lib/review_store.py` resolver: dual-key (origin URL + git-common-dir),
  self-healing per-key pointer store.

### Changed

- Shared Python helpers moved from `skills/review-code/` to `lib/`
  (`repo_doctor.py`, `decisions.py`, `circuit_breaker.py`,
  `resolve_diff_lines.py`); their tests now run in CI.
- The review skills resolve the profile/decisions location instead of assuming
  `.claude/review-profile.md`.

## [0.1.0] — 2026-06-07

### Added

- Initial release. Multi-agent review of code, plans, and tech debt: a panel of
  four specialist reviewers (architecture / code / security / test) driven by a
  shared rubric and calibrated per-project via a generated review profile.
- Commands: `/review-crew:review-code`, `/review-crew:review-plan`,
  `/review-crew:audit-debt`, `/review-crew:review-init`.
- Eval harness (`eval/`) with frozen fixtures, a deterministic golden-eval scorer
  (`score.py`), and its unit tests.
