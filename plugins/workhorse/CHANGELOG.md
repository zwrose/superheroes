# Changelog — workhorse

All notable changes to the `workhorse` plugin. Versions follow
[SemVer](https://semver.org); entries follow
[Keep a Changelog](https://keepachangelog.com).

## [0.5.0](https://github.com/zwrose/superheroes/compare/workhorse-v0.4.0...workhorse-v0.5.0) (2026-06-20)


### Features

* finish wiring the model-tier knob across all dispatch points ([#15](https://github.com/zwrose/superheroes/issues/15)) ([#48](https://github.com/zwrose/superheroes/issues/48)) ([e946c31](https://github.com/zwrose/superheroes/commit/e946c315c0d6f27bb659d68f9db466e62278ed87))
* trigger-eval-gated skill token efficiency ([#49](https://github.com/zwrose/superheroes/issues/49)) ([8b5d0ec](https://github.com/zwrose/superheroes/commit/8b5d0ec02a966d235c509a38f34fdffbdd66b6f0))
* **workhorse:** non-substitutable build & review ship-gate (③) ([#55](https://github.com/zwrose/superheroes/issues/55)) ([9fab148](https://github.com/zwrose/superheroes/commit/9fab148ace04af44ad1b9ab3348dc0f40c551137))


### Bug Fixes

* **workhorse:** don't pin the manifest version in the scaffold test ([#54](https://github.com/zwrose/superheroes/issues/54)) ([32b77b8](https://github.com/zwrose/superheroes/commit/32b77b8063ff3772c4b28ae6b2132071084b1087))
* **workhorse:** key Bash safety-write guard off the redirect/exec target ([#61](https://github.com/zwrose/superheroes/issues/61)) ([2350a3c](https://github.com/zwrose/superheroes/commit/2350a3c5fcae24ebb4eeda7d42cd75369f93af70))

## [Unreleased]

## [0.4.0] — 2026-06-19

### Changed

- **Producer-enforcer is now a live owner-approval GATE, not a hard-deny floor**
  (issue #14). Owner-authority / irreversible actions — merge / release / deploy /
  force-push / push-to-default / `gh workflow run` / destructive — are gated on the
  owner's live, in-turn approval instead of being unconditionally denied, and only
  **inside a superheroes repo** (a `docs/superheroes/` tree). Outside one the gate
  does not fire, so installing workhorse no longer subjects unrelated interactive
  sessions to the floor.
  - **Host-aware mechanism, same functionality** (approve → proceed; no owner →
    park): on **Claude Code** the hook emits `permissionDecision: ask` (a native
    prompt the agent cannot answer itself); on **Codex** (honors only `deny`) the
    hook denies + issues a one-time nonce, and on the owner's approval the agent mints
    a single-use, command-scoped, 90s-TTL **allowance** (`lib/allowance.py`) that the
    next matching call consumes. The host capability is passed by the hook wiring
    (`hook --host claude`); an unknown/missing host fails safe to the deny path.
  - Allowances are namespaced **per checkout** and consumed via an atomic claim, so
    concurrent producer loops can never cross-consume an approval; `PreCompact` wipes
    pending allowances so none survives a context compaction.

### Fixed

- The enforcer hook now dispatches the **Codex tool names** (`shell`, `apply_patch`)
  in addition to the Claude ones (`Bash`, `Edit`/`Write`/`MultiEdit`) — previously a
  Codex `shell` command and `apply_patch` edit fell through to *allow*, so the command
  gate and the safety-machinery edit-guard were inert on Codex. `apply_patch` edits to
  band safety-machinery are now refused (the target is parsed from the patch body).
- Safety-machinery self-protection stays an **unconditional** deny on both hosts and
  is held out of the allowance flow even for a compound command that is both a
  safety-write and a gated action.

## [0.3.0] — 2026-06-19

### Added

- Codex host support: `.codex-plugin` manifest (with hooks pointer), `hosts/` tool maps, neutral-language skill, and a fail-closed `PreToolUse` enforcer hook (`hooks-codex.json`).

## [0.2.0] — 2026-06-19

### Added

- Resilience slice: the producer now survives crash / kill / context-compaction and
  resumes a single work-item with full fidelity (CONVENTIONS §4).
  - Durable per-checkout control-plane store (`control_plane.py`, §4.2), keyed by
    `<absolute-git-dir-key>` so linked worktrees stay isolated.
  - Leased git-ref work-item lock with CAS reclaim + a `generation` fence
    (`lock.py`, §4.4) and the §4.5 startup per-checkout lock; portable per-boot id
    (`hostinfo.py`).
  - The §4.3 `checkpoint.json` writer/reader (`checkpoint.py`), fail-closed on an
    unknown schemaVersion.
  - `events.jsonl` audit log + `resume-brief.md` (`journal.py`, §4.6) — durable,
    scrub-fail-closed, with the ⑧ CI-fix bound reconstructed write-ahead so it
    survives restarts (conservative over-count, never under-counts).
  - Reconcile-on-entry (`recover.py`, §4.7): reality-wins recovery, the
    transient-read GATE rule, the §6.3 content-hash stale-spec cascade GATE, and the
    bounded floor re-arm → parked-GATE.
  - PreCompact / SessionStart resume hooks (`hooks/precompact.py`,
    `hooks/session_start.py`), self-protected as band safety-machinery.
  - Dev-server corroborated orphan reclaim (pid + port + command + boot id) and a
    bounded health-poll (`devserver.py`).
  - Subprocess timeouts on workhorse's three subprocess seams
    (`enforcer.classify_path` → deny, `reset.engine_json` → gate, `readout.scrub` →
    drop); the fourth band seam, review-crew's `model_tier_resolve`, lands in
    review-crew `0.6.1`.
- The ⓪–⑨ SKILL spine is wired to the substrate (reconcile, ref-lease + fence,
  write-ahead CI bound, durable-write fail-closed park-GATE).

## [0.1.0] — 2026-06-18

### Added

- Initial release: the `workhorse` orchestrator skill (the per-issue
  back-half producer) and its stdlib-only `lib/` — the action-boundary
  enforcer (PreToolUse hook), the CI-fix loop bound, project detectors,
  the dev-server lifecycle manager, the test-pilot reset orchestrator, and
  the "your turn" readout with a secret-scrub seam.
