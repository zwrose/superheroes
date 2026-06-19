# Changelog — workhorse

All notable changes to the `workhorse` plugin. Versions follow
[SemVer](https://semver.org); entries follow
[Keep a Changelog](https://keepachangelog.com).

## [Unreleased]

### Added

- Codex host support: `.codex-plugin` manifest (with hooks pointer), `hosts/` tool maps, neutral-language skill, and a fail-closed `PreToolUse` enforcer hook (`hooks-codex.json`).

## [0.1.0] — 2026-06-18

### Added

- Initial release: the `workhorse` orchestrator skill (the per-issue
  back-half producer) and its stdlib-only `lib/` — the action-boundary
  enforcer (PreToolUse hook), the CI-fix loop bound, project detectors,
  the dev-server lifecycle manager, the test-pilot reset orchestrator, and
  the "your turn" readout with a secret-scrub seam.
