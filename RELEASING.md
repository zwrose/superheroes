# Releasing

Releases are **automated** with [release-please](https://github.com/googleapis/release-please).
The `superheroes` plugin versions as a single package. release-please keeps three version
files in lockstep: the plugin's `version.txt` (the `simple` strategy's canonical file) and
both manifest copies — `.claude-plugin/plugin.json` (the version Claude Code reads for
auto-update) and `.codex-plugin/plugin.json` — via the `extra-files` map in
[`release-please-config.json`](release-please-config.json).

## The normal flow

1. Merge ordinary work to `main` with Conventional-Commit messages scoped to `superheroes`
   (e.g. `feat(superheroes): …`). A required CI check rejects a non-Conventional-Commit PR
   title before merge. Every such PR has already been **vetted by the advisor and reviewed by
   the review crew** on its way in (see [below](#pre-release-verification--the-advisor-vet)).
2. release-please maintains an **open release PR** that proposes the next version
   (`chore`→patch, `fix`→patch, `feat`→minor, `!`/`BREAKING CHANGE`→major) and regenerates
   `plugins/superheroes/CHANGELOG.md`. It bumps `version.txt` and both `plugin.json` files.
   (`chore` is a releasing type via the `changelog-sections` config — a `chore` touching plugin
   files cuts a patch and shows under a "Chores" heading.)
3. **Review the release PR — confirm it ships only already-vetted work — then merge it.** The
   owner merges (e.g. the 0.15.0 cut, PR #456); merging is the owner's act, never the advisor's
   (covenant). Merging makes the workflow create the `superheroes-vX.Y.Z` tag and publish the
   matching GitHub Release. No hand-cut release.

A change that touches **no** plugin files (repo-root `ci:`, `docs:`, `chore:`) triggers no
release, whatever its type.

## Pre-release verification — the advisor vet

**There is no release-time harness, benchmark, or `release-evidence` check to discharge.** The
v1 spine — and the acceptance-run / release-eval machinery that guarded it — was retired in the
v2 pivot (PR #478/#479). No live model runs in CI, and none needs to at the cut, because the
verification already happened upstream, one PR at a time.

The pre-release evidence **is the advisor's per-PR vet, accumulated**. In the v2 loop every PR
that lands on `main` has passed two independent checks before it merged:

- **Review crew** — the cross-vendor `review-code` build review (and, for spec'd work, the
  `review-spec` panel), composed to complement the builder's vendor.
- **Advisor vet** — the Showrunner vets every PR from its artifacts against the issue/spec and
  the build brief, and posts a **durable vet receipt** on the PR (verdict plus what it probed).

So by the time release-please's PR is ready, the queue since the last `superheroes-v*` tag is
work that was *already* verified as it went in. Merging the release PR ships exactly that queue
and nothing new — the version bumps and regenerated CHANGELOG are the only diff. The release
review is therefore a **confirmation, not a re-verification**: skim the CHANGELOG against the
merged PRs, confirm each carries its vet receipt, and confirm nothing unvetted slipped in. Then
merge.

If a queued change ever looks under-vetted, the fix is upstream: vet or re-review *that PR* (or
revert it) before cutting — not a special release-time instrument.

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
- **The `main protection` ruleset** (Settings → Rules → Rulesets; classic branch protection is
  retired — the ruleset is the single home for these rules) requires a pull request and the
  status checks `validate` and `pr-title` (both pinned to the GitHub Actions app), with
  branches required to be **up to date** before merging, plus no-force-push and no-deletion.
  **Repository admins are the ruleset's bypass actors** — the owner may bypass when genuinely
  needed (prefer a PR anyway). The release App is *not* a bypass actor, so every rule applies to
  it.
- **Tag-protection rules for `*-v*`** so published tags can't be moved.

## Before the first release (one-time verification)

Before merging the first real release PR, run release-please in **dry-run** with the App
token and confirm two things against an existing release:

- the tag it proposes matches the retained scheme **`superheroes-vX.Y.Z`** (e.g.
  `superheroes-v0.7.1`, not `v0.7.1` or `superheroes/0.7.1`) — if it renders differently,
  set `include-component-in-tag` / `include-v-in-tag` / `tag-separator` explicitly in
  `release-please-config.json` before the first release; and
- the regenerated `CHANGELOG.md` renders cleanly when prepended to the existing
  hand-written entries.

Verify the tag + GitHub Release appear as expected before relying on the automation.

## Recovery

A failed release run is visible in the Actions tab and is safely re-runnable; re-running
completes the Release for an already-created tag (the tag is the idempotency anchor, so a
re-run never double-releases). If the Action cannot finish, cut the missing Release by hand
for the existing tag with `gh release create superheroes-vX.Y.Z`.
