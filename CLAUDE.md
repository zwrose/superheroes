# CLAUDE.md

Guidance for working in this repo. This is a **Claude Code plugin marketplace** —
a catalog (`.claude-plugin/marketplace.json`) listing plugins under `plugins/`.

## Layout

- `.claude-plugin/marketplace.json` — the catalog. Lists the `superheroes` plugin + its `source`.
- `plugins/superheroes/.claude-plugin/plugin.json` — the plugin manifest (name, version).
- `plugins/superheroes/` — the plugin's components (`agents/`, `skills/`, `rubric/`, `eval/`).
- `.github/workflows/ci.yml` — validation (manifest checks + pytest).
- `.github/scripts/validate_marketplace.py` — catalog/manifest validator.
- `docs/` — internal design docs and plans. **Gitignored**, kept local only — **except
  `docs/superheroes/`**, the committed home of definition-docs (specs and their work-item
  folders: coverage maps, contract registers, package-read audit trails; doc-policy
  confirmed 2026-08-08, owner-ruled: visibility `committed`, calibration stays out-of-repo).

## Keeping the docs fresh

When a change alters the **cast, commands, or cross-plugin contracts**, update the docs in
the same PR:

- **README.md** — the hero sections + their command tables.
- **CONVENTIONS.md** — the cross-plugin contracts (§1–§14).

**ROADMAP.md carries the coarse train** (owner-ratified 2026-07-09; simplified to
areas-of-focus 2026-07-22, owner call): the cut rules, the cut record, and the areas
of focus — grounded in [PHILOSOPHY.md](PHILOSOPHY.md). Update it **at train-level
events only**: a release cuts, an area of focus opens or closes, a cut rule changes.
A PR that cuts a release updates ROADMAP.md in the same PR. Issue-level status stays
in the [GitHub Project](https://github.com/users/zwrose/projects/1) and the
**milestones** (one per area; epic issues are reserved for decomposing one sizable
piece of work into native sub-issues) — never in ROADMAP.md, and no individual work
item is ever named in an area entry.

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

Every PR and push to `main` runs `.github/workflows/ci.yml` (Python **3.12** on
`ubuntu-latest`), on `opened`/`synchronize`/`reopened` only — a title or body edit
does not re-run code checks. Title re-validation lives in its own workflow
(`pr-title.yml`, which does fire on `edited`), and superseded runs on a PR ref are
cancelled by the concurrency group.

**Job `validate`**

1. `validate_marketplace.py` — manifests parse, sources exist, versions are valid
   SemVer, no duplicate-version trap.
2. `check_catalog_membership.py` — catalog membership / `metadata.version`
   consistency against the PR base ref (**pull-request events only**).
3. `validate_hosts.py` — dual-host manifests and tool maps are consistent.
4. `validate_skills.py` — skill token-shape (line counts, description sizes,
   required phrases, reference links, CONVENTIONS citations) and, per CONVENTIONS
   §11.4, that every plugin-relative citation in the docs dispatched consumers read
   (`agents/`, `rubric/`, the `reference/` trees) resolves from the plugin root.
5. `validate_stubs.py` — STUB markers carry an issue reference.
6. Install `uv` — test-pilot block-execution tests depend on it.
7. Install `jscpd@5.0.12` via npm — guardian duplication real-channel tests
   depend on it.
8. `pytest` over plugin lib/eval tests + the band-level eval harness — scripts
   (`.github/scripts/tests/`), `plugins/superheroes/` (`lib/`, `eval/`), and
   `eval/lib/` (identifier reference-impl conformance, artifact schemas, and the
   activation-result CI gate). Schema tests
   need `jsonschema`. Runs under `pytest-xdist` (`-n auto`; adopted on #897's
   measured parity A/B) with `--durations=25` so the slow tail stays visible as
   the suite grows. A parallel-run failure of the #806/#809/#882 names is the
   known load-flake class — check those issues before treating it as a regression.

**Job `pr-title`** (**pull-request events only**)

1. `check_conventional_commit.py` — PR title is a Conventional Commit.

Run all locally-runnable steps before pushing:

```bash
/usr/bin/python3 .github/scripts/validate_marketplace.py
/usr/bin/python3 .github/scripts/validate_hosts.py
/usr/bin/python3 .github/scripts/validate_skills.py
/usr/bin/python3 .github/scripts/validate_stubs.py
/usr/bin/python3 -m pytest .github/scripts/tests/ plugins/superheroes/lib/tests/ plugins/superheroes/eval/tests/ eval/lib/tests/ -q
```

Use `/usr/bin/python3` for local gates: that interpreter carries both pytest and
PyYAML, which the validators and test suite require. CI runs the gates on Python
**3.12** while `/usr/bin/python3` on macOS is **3.9.6**, so a green local run is
strong but not conclusive evidence for CI — version-sensitive syntax or stdlib
behavior can pass one and fail the other. The catalog-membership check and the
PR-title check are CI-side only (they need a base ref or a PR title).

## Review discipline — no unreviewed PRs

Every PR that touches `plugins/superheroes/**` gets a real review before handback,
no matter how small the diff or how it was built (direct build, external engine,
fix PR, fast-follow):

- Work driven through the review skills reviews itself — the cross-vendor review panels (review-code, the spec panel) are the review.
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
