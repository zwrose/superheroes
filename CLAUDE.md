# CLAUDE.md

Guidance for working in this repo. This is a **Claude Code plugin marketplace** —
a catalog (`.claude-plugin/marketplace.json`) listing plugins under `plugins/`.

## Layout

- `.claude-plugin/marketplace.json` — the catalog. Lists the `superheroes` plugin + its `source`.
- `plugins/superheroes/.claude-plugin/plugin.json` — the plugin manifest (name, version).
- `plugins/superheroes/` — the plugin's components (`agents/`, `skills/`, `rubric/`, `eval/`).
- `.github/workflows/ci.yml` — validation (manifest checks + pytest).
- `.github/scripts/validate_marketplace.py` — catalog/manifest validator.
- `docs/` — internal design docs and plans. **Gitignored**, kept local only.

## Keeping the docs fresh

When a change alters the **cast, commands, or cross-plugin contracts**, update the docs in
the same PR:

- **README.md** — the hero sections + their command tables.
- **CONVENTIONS.md** — the cross-plugin contracts (§1–§7).

**ROADMAP.md carries the release train** (owner-ratified 2026-07-09, superseding the
older pointer-only rule): the cut rules, the release bundles with what each must prove
before it cuts, the build lane, and the tracking mechanics — grounded in
[PHILOSOPHY.md](PHILOSOPHY.md). Update it **at train-level events only**: a release
cuts or reorders, an epic opens/closes, a cut rule changes, the build lane reschedules.
A PR that cuts or re-scopes a release updates ROADMAP.md in the same PR. Issue-level
status stays in the [GitHub Project](https://github.com/users/zwrose/projects/1) and
the release epics — never in ROADMAP.md.

## Versioning (SemVer)

The `superheroes` plugin owns its version in `plugins/superheroes/.claude-plugin/plugin.json`.
This is the version Claude Code uses for update detection.

Rules (enforced by `validate_marketplace.py`):

- **Version bumps are automated** (release-please derives them from Conventional Commits and
  writes them into both `plugin.json` files via the release PR). Do not hand-edit the
  `version` in a feature change — it advances only through the release PR.
- **Never put `version` in the plugin's `marketplace.json` entry.** `plugin.json`
  wins silently, so a duplicate masks the real value. plugin.json is the single
  source of truth for plugin version.
- `marketplace.json` `metadata.version` is the catalog version — independent of
  the plugin version, low-churn, does not drive plugin updates.

## Releasing

Automated via release-please (see [RELEASING.md](RELEASING.md)). Merge
Conventional-Commit work to `main`; release-please maintains an open release PR that
bumps both `plugin.json` files + `version.txt` and regenerates the CHANGELOG. **Merging that
release PR** cuts the `superheroes-vX.Y.Z` tag + GitHub Release. Do not hand-edit the
version or hand-cut a release.

## Commits — Conventional Commits

Use [Conventional Commits](https://www.conventionalcommits.org/). Scope to `superheroes`.

- `feat(superheroes): add audit-debt command`
- `fix(superheroes): correct severity gate in score.py`
- `feat(superheroes)!: ...` or a `BREAKING CHANGE:` footer for breaking changes.
- Repo-wide changes (CI, license, governance): `chore:`, `ci:`, `docs:` with no
  scope or a `repo` scope. These touch no plugin's files, so they cut no release.

Commit-type → SemVer intent: `chore:`/`fix:` → patch, `feat:` → minor, `!`/breaking
→ major. `chore` is a **releasing** type here (the `changelog-sections` config makes
it visible): a `chore` that touches a plugin's files bumps that plugin's patch version
and lands under a "Chores" changelog heading. Reserve `chore` for plugin changes that
ship but aren't a user-facing feature or bugfix; use `fix`/`feat` when they are. A
`chore` scoped to no plugin (repo-root files) still cuts no plugin release.

## CI

Every PR and push to `main` runs `.github/workflows/ci.yml`:

1. `validate_marketplace.py` — manifests parse, sources exist, versions are valid
   SemVer, no duplicate-version trap.
2. `validate_hosts.py` — dual-host manifests and tool maps are consistent.
3. `validate_skills.py` — skill token-shape (line counts, description sizes,
   required phrases, reference links, CONVENTIONS citations).
4. `pytest` over plugin lib/eval tests + the band-level eval harness — scripts
   (`.github/scripts/tests/`), `plugins/superheroes/` (`lib/`, `eval/`), and
   `eval/lib/` (identifier reference impls, artifact schemas, and the
   activation-result CI gate). The plugin lib tests include a pytest wrapper that
   runs the showrunner Node smoke tests. Schema tests need `jsonschema`.

Run all steps locally before pushing:

```bash
python3 .github/scripts/validate_marketplace.py
python3 .github/scripts/validate_hosts.py
python3 .github/scripts/validate_skills.py
python3 -m pytest .github/scripts/tests/ plugins/superheroes/lib/tests/ plugins/superheroes/eval/tests/ eval/lib/tests/ -q
```

## Review discipline — no unreviewed PRs

Every PR that touches `plugins/superheroes/**` gets a real review before handback,
no matter how small the diff or how it was built (direct build, external engine,
fix PR, fast-follow):

- Work driven through the pipeline reviews itself (the spine's panels).
- **A direct build ends with `/superheroes:review-code`** (or an explicit
  owner/owner-agent review) before the PR is handed back. The loop is cheap on
  small diffs (scoped rounds, capped confirmations) — "too small to review" is
  exactly how past escapes shipped (see issue #183: the worst defects in this
  repo's history came from the handful of PRs that skipped review).
- A review that **halts with an open blocker** (circuit breaker, park) is resolved
  or explicitly owner-accepted in the PR body — never quietly merged.

The convention also ships to plugin users: the canonical statement lives in
`plugins/superheroes/rubric/review-discipline.md`, the SessionStart bootstrap injects the
distilled covenant (`plugins/superheroes/rubric/covenant.md`, which subsumes the note —
its review-before-handback hard line still points at the canonical statement) into every
session on a superheroes-calibrated project (both storage modes, zero repo traces), and
`configure` offers an in-repo project a durable `CLAUDE.md` copy (see CONVENTIONS §7.4).

## Branch protection

`main` requires a PR with passing CI. The repo owner may bypass when needed —
prefer PRs anyway.
