# Changelog — the-architect

All notable changes to the `the-architect` plugin. Versions follow
[SemVer](https://semver.org); entries follow
[Keep a Changelog](https://keepachangelog.com).

## [Unreleased]

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
