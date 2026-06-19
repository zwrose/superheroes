# Changelog — the-architect

All notable changes to the `the-architect` plugin. Versions follow
[SemVer](https://semver.org); entries follow
[Keep a Changelog](https://keepachangelog.com).

## [Unreleased]

## [0.4.0] — 2026-06-19

### Added

- **Codex host support:** `.codex-plugin` manifest, `hosts/` tool maps, neutral-language skills + design-capture peer.

### Fixed

- **Gate-integrity — Plan/Tasks no longer self-certify an unrecorded review.** The `plan` and
  `tasks` self-certify branches now distinguish "review tool not installed" (genuine degraded
  mode → self-certify) from "review tool ran but could not record its verdict" (gate left
  `pending` by a failed `gate_write` → STOP, do not self-certify). The branch keys off whether
  `review-(plan|tasks)` actually ran, not the gate value alone — closing a hole where a
  silently-failed review write could be laundered into a `passed` gate.

## [0.3.1] — 2026-06-19

### Changed

- `escalation.SAFETY_MACHINERY` now protects the two workhorse resume-hook scripts
  (`precompact.py`, `session_start.py`) — resilience self-protection.

## [0.3.0] — 2026-06-18

### Added

- **Band-wide model-tier knob.** `lib/model_tier.py` — the shared, pure, fail-OPEN
  role→model-tier policy core (the cost/perf knob). review-crew wraps it and
  workhorse is the first consumer.

### Changed

- **`SAFETY_MACHINERY` extended (F3 self-protection).** Added `enforcer.py`,
  `band_lib.py`, `model_tier.py`, and `hooks.json` so the workhorse action-boundary
  enforcer, its resolver, the model-tier core, and the hook registration are
  protected from auto-edits — the CI fixer can't disable the floor.

## [0.2.0] — 2026-06-16

### Added

- **Escalation rubric (F5).** `lib/escalation.py` (deterministic floor action-classifier + pure
  `route()` + fixer file-scope guard) and `rubric/escalation-base.md` (the shared PROCEED/NOTIFY/GATE
  policy — the escalation analogue of `review-base.md`). `plan` and `tasks` now instantiate the
  shared rubric and gain the NOTIFY tier (owner-relevant-but-reversible decisions surface as undoable
  heads-ups instead of silent record-only).

## [0.1.0] — 2026-06-16

### Added

- Initial release — **the requirements-first front half of the superheroes loop**
  (Discovery → Plan → Tasks). Four skills:
  - **`discovery`** — turns a fuzzy idea into an owner-approved `spec` definition-doc
    (plain-language requirements in EARS, an unhappy-path coverage checklist, no tech
    leak), runs it through `review-spec`, and ends at the owner's explicit approval.
  - **`writing-specs`** — authors the `spec` from the approved requirements (invoked
    by `discovery`); the coverage-checklist disposition lives in a dedicated
    `## Coverage` section, not inline in the requirements.
  - **`plan`** — turns the approved spec into a `plan` definition-doc (the technical
    *how*); self-certifies its review gate only when no reviewer ran.
  - **`tasks`** — wraps superpowers `writing-plans` via capture-at-seam into a `tasks`
    definition-doc with a build contract; stops at a reviewed, gated doc ready for the
    producer's Build.
- **`lib/definition_doc.py`** — the §3.1 definition-doc frontmatter/gate writer (the
  single frontmatter owner) and work-item slug minting, with a CLI
  (`mint` / `path` / `dir` / `frontmatter` / `set-gate` / `read-gate`).
- Templates for `spec` / `plan` / `tasks`.
