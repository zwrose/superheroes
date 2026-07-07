# Releasing

Releases are **automated** with [release-please](https://github.com/googleapis/release-please).
The `superheroes` plugin versions as a single package; the version Claude Code reads for
auto-update is in `plugins/superheroes/.claude-plugin/plugin.json` (kept in sync with
`.codex-plugin/plugin.json` by the automation).

## The normal flow

1. Merge ordinary work to `main` with Conventional-Commit messages scoped to `superheroes`
   (e.g. `feat(superheroes): …`). A required CI check rejects a non-Conventional-Commit PR
   title before merge.
2. release-please maintains an **open release PR** that proposes the next version
   (`chore`→patch, `fix`→patch, `feat`→minor, `!`/`BREAKING CHANGE`→major) and regenerates
   `CHANGELOG.md`. It bumps both `plugin.json` files and `version.txt`. (`chore` is a
   releasing type via the `changelog-sections` config — a `chore` touching plugin files cuts
   a patch and shows under a "Chores" heading.)
3. **Review the release PR, clear the evidence gate ([below](#pre-release-verification--the-evidence-gate)), then merge it.**
   Merging makes the workflow create the `superheroes-vX.Y.Z` tag and publish the matching
   GitHub Release. No hand-cut release.

A change that touches **no** plugin files (repo-root `ci:`, `docs:`, `chore:`) triggers no
release, whatever its type.

## Pre-release verification — the evidence gate

Merging the release PR is the one-click act that ships everything queued since the last tag —
and the **only** moment spine changes and reviewer-prompt edits reach users. The band's live
verification instruments exist to catch exactly that drift, but no live model runs in CI, so
each one runs only when someone decides to. This gate ties that decision to the cut: it fires
precisely when drift ships and can't be forgotten because it lives in the release ritual.

Between **review** and **merge**, the **`release-evidence`** commit status must be green (or
explicitly bypassed). The ritual is **classify → run → record → merge**:

1. **Classify** — you don't; the `release-evidence` check does, deterministically, from the
   commit range since the last `superheroes-v*` tag, and posts a sticky **owed-summary** comment
   (release class + which instruments are owed + the exact commands). That comment/output is the
   single authority on what the release owes — nothing re-derives it. Preview locally any time:
   `python3 .github/scripts/classify_release.py`.
   - **spine-carrying** — the showrunner spine the acceptance harness exercises changed. Any
     `lib/*.py` decider is spine by default (fail closed — a new decider owes an acceptance run
     unless it is explicitly non-runtime), and the committed `showrunner.bundle.js` is drift-locked
     to its JS source modules → owes the **acceptance** run.
   - **reviewer-touching** — a reviewer seat's methodology or the shared rubric changed → owes
     the **benchmark** (review A/B eval).
   - **neither** — docs-only / repo-plumbing → owes nothing; the check is trivially green, merge
     freely.

   The exact classification rules live in exactly one place —
   [`classify_release.py`](.github/scripts/classify_release.py) — and are never restated
   elsewhere; the owed-summary is what tells you which class this release is.
2. **Run** the owed instrument(s). The one-session path is the repo-local **`release-eval`**
   skill (`/release-eval`): it reads the check's owed-summary, dispatches only the owed
   instruments (the live acceptance run via the repo-local `acceptance` skill; the benchmark
   dual-dispatch per `plugins/superheroes/eval/README.md`), posts the evidence, watches the check
   flip green, and stops before merge (merging stays yours). By hand: run the commands the
   owed-summary prints.

   *Machine prerequisite (one-time):* the acceptance harness's headless child invokes the
   showrunner **Workflow** orchestrator, and the auto-mode permission classifier
   non-deterministically blocks that call (it pattern-matches a self-authorizing prompt
   running a non-cached bundle — indistinguishable from injection from where it sits; found
   live in the 0.10.0 qualification). Make the ritual deterministic with a project-local
   allow rule on the machine that runs it: add `"Workflow"` to `permissions.allow` in
   `.claude/settings.local.json` (machine-local, gitignored). Subagent-level permission
   checks still apply — this only stops re-litigating "may the harness start its own
   orchestrator" on every run. Note the rule's breadth honestly: it auto-allows EVERY
   Workflow invocation in this project on this machine, not just the ritual's — remove
   it from `settings.local.json` between releases if that bothers you.
3. **Record** — evidence is a fenced ` ```release-eval-evidence ` JSON block posted as a PR
   comment (the skill posts it; the check fetches comments and parses it). It is **SHA-bound**:
   the acceptance leg's `bundleSha256` must equal the released `showrunner.bundle.js` hash and
   every leg's `releaseSha` must equal the release head — so stale or copied evidence fails the
   binding (best-effort per #56, not cryptographic; the check verifies evidence, it never runs a
   live model). Append the dated verdict to `plugins/superheroes/eval/RESULTS.md` too: the
   comment is what gates, the ledger is what remembers.
4. **Merge** — once `release-evidence` is green.

> **If `main` moves while you're discharging** (release-please regenerates its PR on every push
> to `main`), the release head SHA changes and the just-posted evidence — bound to the old SHA —
> no longer matches. The check re-arms to red and the owed-summary shows the new `releaseSha`;
> that is the SHA-binding working, not a bug. Just re-run `/release-eval` against the refreshed
> owed-summary. (The acceptance content binding usually still holds, since a version-bump commit
> doesn't touch the spine bundle — only the ref binding re-arms.)

**Override.** `release-evidence` is a required status. If you must merge without it (the evidence
is genuinely inapplicable, or an instrument is broken), use the owner's **admin bypass** at merge
**and** leave a one-line why-comment on the PR. The bypass is deliberate and attributed in the
merge record, and the red ✗ stays permanently visible on the merged PR — louder than a label that
would turn things green. Tradeoff: the bypass is **wholesale** — it skips *all* required checks —
so eyeball the rest of the checks before using it. A scoped `release-verify-exempt` label is the
documented fallback if this repo ever gains co-maintainers.

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
  status checks `validate`, `pr-title` (both pinned to the GitHub Actions app), and
  `release-evidence` (the pre-release evidence gate above; trivially green on non-release and
  docs-only PRs; deliberately unpinned — posting a status already requires write access), with
  branches required to be **up to date** before merging, plus no-force-push and no-deletion.
  **Repository admins are the ruleset's bypass actors** — that is the deliberate override path
  (see Override above). The release App is *not* a bypass actor, so every rule applies to it.
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

Verify the tag + GitHub Release appear as expected before relying on the pipeline.

## Recovery

A failed release run is visible in the Actions tab and is safely re-runnable; re-running
completes the Release for an already-created tag (the tag is the idempotency anchor, so a
re-run never double-releases). If the Action cannot finish, cut the missing Release by hand
for the existing tag with `gh release create superheroes-vX.Y.Z`.
