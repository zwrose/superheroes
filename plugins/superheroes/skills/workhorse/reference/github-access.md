# GitHub access for the producer

Workhorse (and the showrunner that will reuse this check) drives a work-item to a **pull
request**: it pushes a branch, opens/updates the PR, and posts comments. A **fail-closed
preflight** (`lib/gh_preflight.py`) runs at the start of every run and **stops before any
work** when GitHub access isn't ready, printing the exact `gh`/`git` command to fix it.

## What the producer needs

- **The GitHub CLI `gh`**, installed and on `PATH` — <https://cli.github.com>.
- **`gh` signed in** to a GitHub account (`gh auth status` succeeds).
- **A GitHub remote** (`origin`) on the repository.
- **Write access** to that repository for the signed-in account — push branches, open/update
  pull requests, comment. The producer **never merges** (that is the owner's action), so
  merge/admin access is **not** required.

The check is token-type-agnostic: it asks GitHub for the account's **effective access** to
the repo, so it works whether `gh` is signed in via the browser (OAuth) or with a personal
access token.

## Granting the access

The common path is the `gh` sign-in flow with the needed scopes:

```
gh auth login -s repo      # sign in with repo write access
gh auth refresh -s repo    # add the scope to an existing login
gh auth switch             # switch to an account that has access
```

If a work-item changes the repository's own workflow files (`.github/workflows/**`), the
classic-token flow additionally needs the `workflow` scope (`gh auth refresh -s workflow`).
The preflight does not detect this case — GitHub's own push error reports it.

## What the preflight reports on failure

| Cause | Fix |
| --- | --- |
| `gh` not installed | install `gh` (<https://cli.github.com>) |
| not signed in | `gh auth login -s repo` |
| no remote | `git remote add origin <url>` |
| no write access | `gh auth refresh -s repo` (or `gh auth switch`) |
| access undeterminable (GitHub unreachable, etc.) | the underlying error, then retry |
