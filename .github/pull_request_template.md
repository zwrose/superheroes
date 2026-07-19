## What & why

<!-- What does this change, and why? Link any related issue (e.g. "Closes #12"). -->

## Checklist

- [ ] Commits follow [Conventional Commits](https://www.conventionalcommits.org/), scoped by plugin
- [ ] `python3 .github/scripts/validate_marketplace.py` passes
- [ ] `python3 -m pytest plugins/superheroes/eval/tests/ -q` passes (and lib tests if touched)
- [ ] Added an `## [Unreleased]` CHANGELOG entry if the change is user-facing
- [ ] **Docs still accurate** — if this changed the cast, commands, or cross-plugin contracts, updated **README** (hero sections) + **CONVENTIONS** (§1–§13). *(ROADMAP carries the release train — update it at train-level events: a release cuts/reorders, an epic opens/closes, a cut rule changes.)*
- [ ] Did **not** bump plugin versions (maintainer-owned — see RELEASING.md)
