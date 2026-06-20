# CLAUDE.md

Guidance for working in this repo. This is a **Claude Code plugin marketplace** —
a catalog (`.claude-plugin/marketplace.json`) listing plugins under `plugins/`.

## Layout

- `.claude-plugin/marketplace.json` — the catalog. Lists each plugin + its `source`.
- `plugins/<name>/.claude-plugin/plugin.json` — per-plugin manifest (name, version).
- `plugins/<name>/` — the plugin's components (`agents/`, `skills/`, `rubric/`, `eval/`).
- `.github/workflows/ci.yml` — validation (manifest checks + pytest).
- `.github/scripts/validate_marketplace.py` — catalog/manifest validator.
- `docs/` — internal design docs and plans. **Gitignored**, kept local only.

## Keeping the docs fresh

When a change alters the **cast, commands, or cross-plugin contracts**, update the docs in
the same PR:

- **README.md** — the hero sections + their command tables.
- **CONVENTIONS.md** — the cross-plugin contracts (§1–§7).

**ROADMAP.md is just a pointer** to the [GitHub Project](https://github.com/users/zwrose/projects/1)
(the live plan). Keep it a short vision + pointer — **do not re-add a phase list or status
table**; the Project is the source of truth for what's planned and in flight.

## Versioning (per-plugin SemVer)

Each plugin owns its version in its own `plugins/<name>/.claude-plugin/plugin.json`.
This is the version Claude Code uses for update detection.

Rules (enforced by `validate_marketplace.py`):

- **Version bumps are automated** (release-please derives them from Conventional Commits and
  writes them into both `plugin.json` files via the release PR). Do not hand-edit a plugin's
  `version` in a feature change — it advances only through that plugin's release PR.
- **Never put `version` in a plugin's `marketplace.json` entry.** `plugin.json`
  wins silently, so a duplicate masks the real value. plugin.json is the single
  source of truth for plugin version.
- `marketplace.json` `metadata.version` is the catalog version — independent of
  plugin versions, low-churn, does not drive plugin updates.
- Plugins version **independently**; don't lockstep-bump untouched plugins (it
  churns users' caches for no change).

## Releasing

Automated via release-please (see [RELEASING.md](RELEASING.md)). Merge plugin-scoped
Conventional-Commit work to `main`; release-please maintains a per-plugin release PR that
bumps both `plugin.json` files + `version.txt` and regenerates the CHANGELOG. **Merging that
release PR** cuts the `<plugin>-vX.Y.Z` tag + GitHub Release. Do not hand-edit a plugin's
version or hand-cut a release.

## Commits — Conventional Commits

Use [Conventional Commits](https://www.conventionalcommits.org/). Scope by plugin.

- `feat(review-crew): add audit-debt command`
- `fix(review-crew): correct severity gate in score.py`
- `feat(review-crew)!: ...` or a `BREAKING CHANGE:` footer for breaking changes.
- Repo-wide changes (CI, license, governance): `chore:`, `ci:`, `docs:` with no
  scope or a `repo` scope.

Commit-type → SemVer intent: `fix:` → patch, `feat:` → minor, `!`/breaking → major.

## CI

Every PR and push to `main` runs `.github/workflows/ci.yml`:

1. `validate_marketplace.py` — manifests parse, sources exist, versions are valid
   SemVer, no duplicate-version trap.
2. `validate_hosts.py` — dual-host manifests and tool maps are consistent.
3. `validate_skills.py` — skill token-shape (line counts, description sizes,
   required phrases, reference links, CONVENTIONS citations).
4. `pytest` over plugin lib/eval tests + the band-level eval harness — scripts
   (`.github/scripts/tests/`), review-crew (`lib/`, `eval/`), test-pilot (`lib/`),
   the-architect (`lib/`), workhorse (`lib/`), and the cross-plugin `eval/lib/`
   (identifier reference impls, artifact schemas, and the activation-result CI
   gate). Schema tests need `jsonschema`.

Run all steps locally before pushing. Each pytest suite runs in its **own pytest
process** — plugins load in isolation at runtime, and two plugins may share a
module basename (e.g. workhorse and test-pilot both have a `lock.py`), which
would collide on `sys.path` in a single shared process. Test each suite
separately to mirror runtime:

```bash
python3 .github/scripts/validate_marketplace.py
python3 .github/scripts/validate_hosts.py
python3 .github/scripts/validate_skills.py
fail=0
for suite in .github/scripts/tests/ \
             plugins/review-crew/lib/tests/ plugins/review-crew/eval/tests/ \
             plugins/test-pilot/lib/tests/ plugins/the-architect/lib/tests/ \
             plugins/workhorse/lib/tests/ eval/lib/tests/; do
  python3 -m pytest "$suite" -q || fail=1
done
exit $fail
```

## Branch protection

`main` requires a PR with passing CI. The repo owner may bypass when needed —
prefer PRs anyway.
