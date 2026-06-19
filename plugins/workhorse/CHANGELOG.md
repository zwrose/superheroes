# Changelog — workhorse

All notable changes to the `workhorse` plugin. Versions follow
[SemVer](https://semver.org); entries follow
[Keep a Changelog](https://keepachangelog.com).

## [Unreleased]

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
