# Changelog — test-pilot

All notable changes to the `test-pilot` plugin. Versions follow
[SemVer](https://semver.org); entries follow
[Keep a Changelog](https://keepachangelog.com).

## [0.2.1](https://github.com/zwrose/superheroes/compare/test-pilot-v0.2.0...test-pilot-v0.2.1) (2026-06-20)


### Bug Fixes

* host-map pointer resolution, CLAUDE.md context enforcement, and discovery size/slug autonomy ([#66](https://github.com/zwrose/superheroes/issues/66)) ([7f346cc](https://github.com/zwrose/superheroes/commit/7f346cc18646f2c0112d6d70d7f7f4b594855585))

## [Unreleased]

## [0.2.0] — 2026-06-19

### Added

- Codex host support: `.codex-plugin` manifest, `hosts/` tool maps, neutral-language skills.

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
