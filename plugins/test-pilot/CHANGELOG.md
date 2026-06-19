# Changelog — test-pilot

All notable changes to the `test-pilot` plugin. Versions follow
[SemVer](https://semver.org); entries follow
[Keep a Changelog](https://keepachangelog.com).

## [Unreleased]

## [0.1.1] — 2026-06-19

### Fixed

- Durable engine-lock staleness: `acquire()` now reclaims a stale holder (expired by
  TTL **and** pid dead-on-this-boot, or a boot-id mismatch) instead of always
  raising; a live holder still raises `LockHeld`. Hardened `boot_id` against a
  malformed `/proc/stat` line (CONVENTIONS §4.4).

## [0.1.0] — 2026-06-11

### Added

- Initial release: `test-pilot-init` / `test-pilot-plan` /
  `test-pilot-execute` skills.
- Stdlib-only Python engine (`lib/`): dual-location store with always-global
  state, injective artifact keys, diff-aware transactional apply/clean,
  protected-target gate with declared block targets, subprocess block
  contract with PEP-723/`uv` routing, PR-comment management with checkbox
  preservation and diagnostic scrubbing, CATALOG generation.
- Templates for the profile, starter blocks, and both PR comments.
