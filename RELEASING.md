# Releasing

Releases are **automated** with [release-please](https://github.com/googleapis/release-please).
Each plugin versions independently; the version Claude Code reads for auto-update is the one
in `plugins/<name>/.claude-plugin/plugin.json` (kept in sync with `.codex-plugin/plugin.json`
by the automation).

## The normal flow

1. Merge ordinary work to `main` with Conventional-Commit messages scoped to a plugin
   (e.g. `feat(workhorse): …`). A required CI check rejects a non-Conventional-Commit PR
   title before merge.
2. release-please maintains an **open release PR per plugin** that proposes the next version
   (`chore`→patch, `fix`→patch, `feat`→minor, `!`/`BREAKING CHANGE`→major) and regenerates
   that plugin's `CHANGELOG.md`. It bumps both `plugin.json` files and the plugin's
   `version.txt`. (`chore` is a releasing type via the `changelog-sections` config — a
   `chore` touching a plugin's files cuts a patch and shows under a "Chores" heading.)
3. **Review and merge the plugin's release PR.** Merging it makes the workflow create the
   `<plugin>-vX.Y.Z` tag and publish the matching GitHub Release. No hand-cut release.

A change that touches **no** plugin's files (repo-root `ci:`, `docs:`, `chore:`) triggers no
plugin release, whatever its type.

## Adding or removing a plugin (catalog version)

When you add or remove a plugin from `.claude-plugin/marketplace.json`, bump
`metadata.version` in the **same** change — CI fails closed if the plugin set changed without
it.

## One-time owner setup (already in place once configured)

These are owner actions, performed once via GitHub settings (not by the automation):

- **GitHub App** with `contents: write` + `pull-requests: write`, installed on this repo;
  store its app-id and private key as the repo secrets `RELEASE_APP_ID` and
  `RELEASE_APP_PRIVATE_KEY`. The release workflow uses this App token (so release PRs run CI
  and the App's authority is bounded to releases).
- **Merge method: squash-only** (disable merge-commit and rebase), with the squash subject set
  to the PR title — so the validated PR title is the message release-please reads.
- **Branch protection on `main`** applies to the App with bypass disabled, and requires the
  status checks `validate`, `pr-title`, and any plugin test suites.
- **Tag-protection rules for `*-v*`** so published tags can't be moved.

## Before the first release (one-time verification)

Before merging the first real release PR, run release-please in **dry-run** with the App
token and confirm two things against an existing release:

- the tag it proposes matches the retained scheme **`<plugin>-vX.Y.Z`** (e.g.
  `review-crew-v0.7.1`, not `v0.7.1` or `review-crew/0.7.1`) — if it renders differently,
  set `include-component-in-tag` / `include-v-in-tag` / `tag-separator` explicitly in
  `release-please-config.json` before the first release; and
- the regenerated `CHANGELOG.md` for each plugin renders cleanly when prepended to the
  existing hand-written entries.

Cut one plugin's first automated release and verify the tag + GitHub Release appear as
expected before relying on the pipeline for the rest.

## Recovery

A failed release run is visible in the Actions tab and is safely re-runnable; re-running
completes the Release for an already-created tag (the tag is the idempotency anchor, so a
re-run never double-releases). If the Action cannot finish, cut the missing Release by hand
for the existing tag with `gh release create <plugin>-vX.Y.Z`.
