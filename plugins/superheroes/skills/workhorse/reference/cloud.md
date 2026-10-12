# Contents

- [Building in a cloud session](#building-in-a-cloud-session)
  - [When this file applies](#when-this-file-applies)
  - [Intake](#intake)
  - [Workspace](#workspace)
  - [Preflight](#preflight)
  - [GitHub reads, without GraphQL](#github-reads-without-graphql)
  - [Asking the advisor: the builder note](#asking-the-advisor-the-builder-note)
  - [Review](#review)
  - [Verify: cloud-only failures](#verify-cloud-only-failures)
  - [Handback](#handback)
  - [The gh calls on a cloud build's path](#the-gh-calls-on-a-cloud-builds-path)

# Building in a cloud session

This page is reference for the builder running in a cloud session. The charter's §1, §2, §3, §10,
§11 and §12 each point here. Every step below names a `cloud_builder.py` verb the CLI accepts, or a
plain `git` or `gh api` command. In a cloud session, `<plugin root>` is the plugin directory the
session loaded.

## When this file applies

The launch prompt carries `Place: cloud session`, then `Advisor plugin version: <version>`,
`Cloud environment: <id>` and `Base commit: <sha>`. Everything else in the charter still holds; this
page says only what differs.

A cloud builder never merges and never changes calibration. The calibration it reads is the copy the
setup placed, and the plugin refuses a calibration write. It has no owner to ask. When it needs an
answer from the advisor before it can go on, it asks through the builder note (§ Asking the
advisor). Its other comments report state and ask nothing: a refusal, a park, a lapsed-review
notice, a review receipt.

## Intake

1. Write the launch prompt text to a file.
2. Run `python3 -B <plugin root>/lib/cloud_builder.py intake --repo-root <root> --launch-file <file>`.
3. On `ok: false` (exit 1) the result's `outcome` is `refusal`. Post the result's `comment` on the
   issue and end the lane. Build nothing; the advisor relaunches on the owner's machine. At intake,
   before the preflight, post with `gh api` or the session's GitHub tools, whichever works.
4. On `ok: true`, the clone is checked out detached at the launch's base commit. Create the build
   branch there, and post the result's `comment` as the first comment on the issue. It states three
   facts: a cloud build, the plugin version, and that commits carry the cloud's author name while the
   PR is under the owner's name. Never re-word it.

## Workspace

The cloud clone may be shallow. `python3 -B <plugin root>/lib/cloud_builder.py ensure-history --repo-root <root>`
makes history complete. Intake already ran it; re-run it before any review if a later step needs
history. There is no app to bring up on the owner's machine and no slot.

**Push after every commit.** Use `git push -u origin <branch>` the first time and plain `git push`
after. The pushed branch is the only work the advisor can recover if the session stops. Never
force-push.

## Preflight

No owner prompt is possible, so every probe must pass on its own.

1. Run the `gh` probe. When it reports `channel: "rest"`, a REST read passed and `gh auth status`
   did not.
2. On `channel: "rest"`, the write check goes through the session's built-in GitHub tools: post the
   throwaway comment and delete it through those tools.
3. Run `python3 -B <plugin root>/lib/cloud_builder.py github-channel --gh-probe-file <probe json> --tools-write ok`
   (or `failed`). Its result names the channel for the rest of the build: `gh` or `tools`.
4. `cloud_builder.py post` writes through `gh` and is for a `gh`-channel session only.

No channel at all (`no-github-channel`) is a park the builder cannot post. End the lane; the advisor
reads the stopped lane. The reviewer pass's state is `python3 -B <plugin root>/lib/cloud_builder.py pass-state`.

## GitHub reads, without GraphQL

In a cloud session `gh pr view`, `gh pr list`, `gh issue view` and `gh repo view` fail, because they
go through GraphQL. Use these in their place:

| Instead of | Use |
|---|---|
| `gh pr list --head` and `gh pr view --json …` | `cloud_builder.py pr-json --repo <o>/<r> --branch <b> --out <file>` (same field names) |
| `gh repo view --json nameWithOwner` | `cloud_builder.py repo-json --repo <o>/<r>` |
| a PR body | `gh api repos/<o>/<r>/pulls/<n> --jq .body` |
| an issue and its comments | `gh api repos/<o>/<r>/issues/<n>` and `gh api repos/<o>/<r>/issues/<n>/comments` |

Writes go one per call: one comment, one edit.

**Stack link and stack check** read GraphQL too. A cloud builder of a stack layer does not link or
check its stack. It says in its handback that the link is owed to the advisor.

## Asking the advisor: the builder note

1. Write the question to a file.
2. Run `python3 -B <plugin root>/lib/cloud_builder.py note --question-file <file>`. It returns the
   comment text, headed as a builder note for the advisor and ending that the builder is waiting.
3. Post that text on the build's issue.
4. Wait in-turn, up to **15 minutes**. Poll the issue's comments (§ GitHub reads) and watch for an
   incoming message. An answer that arrives either way is the advisor's.
5. With no answer in that time, **park**. Commit and push what is done, post a park comment on the
   issue, and end the turn. The comment says what is done and pushed with its head SHA, what is
   blocked, and what the builder needs.

A cloud session stays listed while parked, and the advisor's message resumes it. On resume, re-read
the issue, then carry on from the pushed head.

## Review

Every independent review seat runs through the reviewer pass. The runner removes the pass from what
its children can see; there is nothing to do by hand. Run the review exactly as the charter's §10
says.

If the pass has lapsed before the review runs, do not substitute a reviewer. Post the `comment` from
`python3 -B <plugin root>/lib/cloud_builder.py review-lapsed` on the PR, leave the PR not ready, and
park. A review that already finished before the lapse stays recorded as it was.

If the review record writer refuses because it cannot read GitHub (`review-record-gh-failed`), post
the review receipt on the PR as a comment naming the head it reviewed. Name the review record as owed
to the advisor in the handback.

## Verify: cloud-only failures

A test that fails only because of the cloud environment is not a product defect and is never
silenced. An example is a permission test that cannot fail when the session runs as root.
Establish the cause, keep the failing command and its output in the build record, and disclose it.
Claim verification only with green CI on the same PR head.

## Handback

Everything the vet needs is on the PR before handback: the review record or receipt, the receipts,
the dispositions. Nothing lives only on the cloud machine. Open the PR through the GitHub channel
from § Preflight. Verify the remote head through `cloud_builder.py pr-json`, not `gh pr view`.

## The gh calls on a cloud build's path

Each `gh pr`, `gh issue` or `gh repo` call that the charter, its reference files and the libraries
they call make at intake, preflight, review and handback, with its cloud stand-in or the reason it is
off a cloud build's path:

| Where | Call | On a cloud build |
|---|---|---|
| `skills/review-code/SKILL.md`, PR mode setup | `gh pr list --head`, `gh pr view --json`, `gh repo view --json nameWithOwner` | the stand-ins in § GitHub reads |
| `skills/workhorse/reference/handback.md`, § The build record | `gh pr view --json body` | `gh api repos/<o>/<r>/pulls/<n> --jq .body` |
| `lib/review_record.py`, repo, PR and issue reads | `gh repo view`, `gh pr view`, `gh issue view` | no stand-in yet: the receipt-and-owed rule in § Review |
| `lib/stack_check.py` | `gh repo view`, `gh pr view` | the advisor's: § GitHub reads |
| `lib/pr_comment.py`, `lib/cloud_builder.py` | `gh api` (REST) | works |
| `lib/preflight_probe.py`, `gh_auth_probe` REST fallback | `gh api repos/<o>/<r>` | works |
| `lib/launcher.py`, `lib/wave_watch.py`, `lib/vet_slot.py` | `gh pr list`, `gh pr view` | the advisor's, not a builder's path |
| `lib/guardian_sweep.py` | `gh issue view` | the guardian's, not a builder's path |

This page adds `gh api` reads only: the pull request, the issue and its comments, and the
repository.
