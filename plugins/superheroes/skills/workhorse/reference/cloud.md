# Contents

- [Building in a cloud session](#building-in-a-cloud-session)
  - [When this file applies](#when-this-file-applies)
  - [A headless session](#a-headless-session)
  - [Intake](#intake)
  - [Workspace](#workspace)
  - [Preflight](#preflight)
  - [GitHub reads, without GraphQL](#github-reads-without-graphql)
  - [Asking the advisor: the builder note](#asking-the-advisor-the-builder-note)
  - [The progress comment](#the-progress-comment)
  - [When the advisor asks you to push](#when-the-advisor-asks-you-to-push)
  - [When the advisor asks you to archive your session](#when-the-advisor-asks-you-to-archive-your-session)
  - [Review](#review)
  - [The cloud container](#the-cloud-container)
  - [Verify: cloud-only failures](#verify-cloud-only-failures)
  - [Terminal comments: handback, stop, park](#terminal-comments-handback-stop-park)
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

## A headless session

The cloud builder runs headless. It starts in auto permission mode with the question dialog off
(its launch argv disallows the question tool through `--disallowedTools`), so it never asks a
question in a dialog. Every question is a builder note on the issue (§ Asking the advisor). With no answer in the reply window it parks with
its work pushed.

Its launch prompt carries the owner's standing permission sentence. The cloud-launch block of
`rubric/launch-doctrine.md` is the one home of that permission; follow the sentence in your launch
prompt and the block, and read the limits from there.

A launch with no such sentence: push only to the session's own branch, and ask by builder note
before any other.

## Intake

1. Write the launch prompt text to a file.
2. Run `python3 -B <plugin root>/lib/cloud_builder.py intake --repo-root <root> --launch-file <file>`.
3. On `ok: false` (exit 1) the result's `outcome` is `refusal`. Post the result's `comment` on the
   issue and end the lane. Build nothing; the advisor relaunches on the owner's machine. At intake,
   before the preflight, post with `gh api` or the session's GitHub tools, whichever works.
4. On `ok: true` for a launch with no `Adopts branch:` line, the clone is checked out detached at
   the launch's base commit. Create the build branch there, its name carrying the issue number as a whole
   number (for example `<prefix>-<issue>-<suffix>`), because recovery finds pushed work by that number, and post the result's `comment` as the
   first comment on the issue. It states three facts: a cloud build, the plugin version, and that
   commits carry the cloud's author name while the PR is under the owner's name. Never re-word it.
5. When the launch carries `Adopts branch: <name> at <sha>`, the result's `branch` names it and the
   clone is on that branch at the adopted head `<sha>`, the branch's pushed head, which descends
   from the launch's base commit (for a stack layer the base is the layer below's head, so the two
   differ), with its upstream set. Continue that branch: do not create a build branch, push to it
   with plain `git push`, and post the result's `comment` as the first comment, as above. Beyond
   the refusals every launch can get (step 3), the adopt steps add six, each naming what failed:
   `adopted-branch-moved` (the branch moved past the head the launch named, so another builder
   may be on it), `adopted-head-not-on-base` (the adopted head does not descend from the base
   commit), `adopted-branch-unfetchable`, `base-checkout-failed`, `adopted-branch-upstream-failed`
   or `adopts-branch-invalid`. Post it and end the lane as in step 3.

## Workspace

The cloud clone may be shallow. `python3 -B <plugin root>/lib/cloud_builder.py ensure-history --repo-root <root>`
makes history complete. Intake already ran it; re-run it before any review if a later step needs
history. There is no app to bring up on the owner's machine and no slot.

**Push after every commit.** Use `git push -u origin <branch>` the first time and plain `git push`
after. The pushed branch is the only work the advisor can recover if the session stops. Never
force-push.

**At intake, at every wake, and before every push, check for a newer launch.** Run
`python3 -B <plugin root>/lib/cloud_builder.py superseded --repo <o>/<r> --issue <n> --launch-id <your launch id>`.
On `superseded: true`, push nothing, post its `comment` on the issue as it is, and end the turn; do
not post a park or handback. On a refusal, push nothing and end the turn. A wake is any turn that
begins after an earlier turn ended: a message, PR activity, or a session that came back after a
usage limit. Your launch id comes from your own session name: read the name with the session-describing
tool called with no id (or from your session listing); it is `issue-<n>-<hash>`, and your launch id is
`launch-<hash>`. A newer launch is shown only by a supersession notice that names exactly your launch
id, whatever its time, so a builder whose intake came late after a usage limit still finds a notice
posted before it. A notice naming another launch never supersedes you, and an intake comment never
orders launches.

**A stack layer.** A layer of a stack builds in a cloud session like any other build, and none of
its steps uses GitHub's GraphQL interface. The launch's base commit is the head of the layer below,
which the launcher checked on the owner's machine before launch. The order names the layer below's
branch.

1. **Branch.** On a launch with no `Adopts branch:` line, intake leaves the clone at the base
   commit: create the build branch there. On an adoption, intake leaves the clone on the adopted
   branch: continue it and create no branch (§ Intake, step 5). Then run
   `git fetch origin <lower branch>` and check that `git rev-parse FETCH_HEAD` equals the base
   commit. This needs no pull request on the layer below. When the two differ, the layer below moved
   after the launch: bring it forward as step 2 says.
2. **Bring the layers below forward.** Run `git fetch origin <lower branch>`, merge with
   `git merge --no-ff FETCH_HEAD`, and push plainly. Never rebase and never force-push. Before
   handback, fetch again and run `git merge-base --is-ancestor FETCH_HEAD HEAD`, which confirms the
   build holds the layer below's current head.
3. **Open the pull request with the layer below's branch as its base**, through REST:
   `gh api -X POST repos/<o>/<r>/pulls -f head=<branch> -f base=<lower branch> -f title=<title> -F body=@<body.md>`,
   or through the session's GitHub tools with the same base. Check `base.ref` in the result. An
   adopted layer that already has an open pull request keeps it: find it with
   `cloud_builder.py pr-json --repo <o>/<r> --branch <branch> --out <file>`, and open none.
4. **Leave the link to the advisor.** `gh stack link` reads GraphQL, and `lib/stack_check.py` reads
   through REST where GraphQL is refused. The builder neither links, runs a stack check, nor quotes its
   `stackEntry` position; the advisor does all three. Its build record lists the link as a
   follow-up for the advisor, keyed like the rest, with the stack number and position the order
   claims, marked unverified. The advisor links at handback
   (`skills/showrunner/reference/orchestration.md` § Cloud lanes).

The same steps hold for an upper layer launched before its stack exists, with no `stack` in its
premise. Its link waits until every layer from the bottom through it has a pull request
(`rubric/native-stacks.md` § Each layer is a sub-issue, item 4).

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
| a PR body | `gh api repos/<o>/<r>/pulls/<n> --jq .body`; `lib/vet_slot.py` reads it this way |
| an issue and its comments | `gh api repos/<o>/<r>/issues/<n>` and `gh api "repos/<o>/<r>/issues/<n>/comments?per_page=100&page=<N>"` for N = 1, 2, … until a page holds fewer than 100 rows (an empty page ends it); a page that fails fails the read (every page, so a late advisor reply is seen) |

Writes go one per call: one comment, one edit.

**Stack link** reads GraphQL too, and **stack check** (`lib/stack_check.py`) reads through REST where GraphQL
is refused. A cloud builder of a stack layer does neither;
§ Workspace, "A stack layer", says what it does in their place.

## Asking the advisor: the builder note

1. Write the question to a file.
2. Run `python3 -B <plugin root>/lib/cloud_builder.py note --question-file <file>`. It returns the
   comment text, headed as a builder note for the advisor and ending that the builder is waiting.
3. Post that text on the build's issue.
4. Wait in-turn for the advisor-reply window that `rubric/review-discipline.md` § Size sets. Poll the issue's comments (§ GitHub reads) and watch for an
   incoming message. The advisor answers by message and may post the same answer on the issue as the
   durable record: act on either copy inside the reply window, the message or the issue comment
   carrying the advisor's answer.
5. With no answer in that time, **park**. Commit and push what is done, post a park comment on the
   issue (composed with `terminal --kind park`, § Terminal comments), and end the turn. The comment says what is done and pushed with its head SHA, what is
   blocked, and what the builder needs. Edit the progress comment (§ The progress comment) before
   posting the park, never after it while still parked.

A cloud session stays listed while parked, and the advisor's message resumes it. On resume, edit the
progress comment first with a phase that says you resumed (for example `resumed: …`); the advisor's
watch reads a progress edit as a resume only when its phase does not read parked or stopped and it
lands more than five minutes after the park. Then re-read the issue and carry on from the pushed head.

## The progress comment

Keep **one** progress comment on the build's issue and edit it in place. Post it right after the
intake comment (§ Intake), then edit that same comment. A new session posts its own: the watch reads
only a comment created at or after the lane's start. It is not a terminal comment (§ Terminal
comments).

Compose it with
`python3 -B <plugin root>/lib/cloud_builder.py progress --phase <text> --running <text> --started <UTC time, …Z> --expected-minutes <N> [--lost <text>]`.
Post its `comment` the first time. Edit after that: on a `gh`-channel session with
`python3 -B <plugin root>/lib/cloud_builder.py edit --repo <o>/<r> --comment-id <id> --body-file <file>`,
on a `tools`-channel session through the session's GitHub tools' comment edit.

Its first line is the fixed header `Builder progress (cloud build).` The lines after it are `Phase:`,
`Now running:`, `Started:` and `Expected: <N> minutes`, then `Lost work:` when there is lost work. The
expected time is your own estimate for what is running now, from 1 to 240 minutes
(`PROGRESS_EXPECTED_MAX_MINUTES`). Take `Started:` from `date -u +%Y-%m-%dT%H:%M:%SZ`, never from memory.

**When to update it.** At each phase change: intake, brief, each order, verify, each review round,
handback. Also before any step you expect to run past ten minutes (a full check, a review round, an
integration run), stating that step's expected time. Edit it **before** you post a park, never after
it while still parked. On resume, edit it first with a phase that says you resumed (for example
`resumed: …`); the advisor's watch reads a progress edit as a resume only when its phase does not
read parked or stopped and it lands more than five minutes after the park.

**Lost work after a restart.** When you resume and find in-flight work you dispatched is gone (a
container restart killed a subagent, a run dir is missing), say so in `Lost work:`. Post a builder
note too (§ Asking the advisor) when the loss changes the plan.

**A status ping.** The advisor's first check on a quiet cloud lane is a relayed status ping by
message. Answer it by updating the progress comment, and reply when the message asks. The advisor
starts a helper session to read a lane only after about 15 minutes with no answer.

The watch reads the comment as `skills/showrunner/reference/wave-watch.md` § Before treating
`lane-stale` as a wedge says: while the comment's last edit is within its expected time plus the
quiet window the lane is not stale; past that it is. A watch tick whose comments read made no request
reuses the last progress snapshot it read.

## When the advisor asks you to push

A message from the advisor can ask you to push your work and hand the issue over, because another
builder is about to take it. Do exactly that, once: commit and push your in-progress work, including any untracked files it needs, so nothing is left in the working tree; if any of it cannot be committed or pushed, say so in a comment on the issue and do not post the handover; run
`python3 -B <plugin root>/lib/cloud_builder.py handover --head <your pushed head sha>`; post its
`comment` on the issue as it is; then stop working on the issue and end your turn. Never post a
handover for a head you did not push. If the verb answers `head-invalid`, the head you gave is not a
full 40-character lowercase commit sha: give your pushed head's full sha, as `git rev-parse HEAD`
prints it.

## When the advisor asks you to archive your session

After your pull request has merged or closed, the advisor may send you a message asking you to
archive your own session. The request is legitimate only then. Read your pull request through REST
(§ GitHub reads) and act only after its `state` is `closed`. While it is open, do nothing and say so
in one comment on the issue.

Archive your own session with the session tool you have: for example a session-archiving tool that
takes a session id, where a session-describing tool called with no id names your own session. The
platform then shows the owner one prompt. That prompt is the owner's, so do not wait for it.

If you have no tool that archives a session, post one line on your issue naming the session tools
you do have, and stop.

Never delete a session, and archive no session but your own.

Then end your turn. Do not push, comment further, or remind anyone about the prompt.

## Review

Every independent review seat runs through the reviewer pass. The runner removes the pass from what
its children can see; there is nothing to do by hand. Run the review exactly as the charter's §10
says.

If the pass has lapsed before the review runs, do not substitute a reviewer. Post the `comment` from
`python3 -B <plugin root>/lib/cloud_builder.py review-lapsed` on the PR, leave the PR not ready, and
park. Post the park on the issue too, with `terminal --kind park` (§ Terminal comments). A review that already finished before the lapse stays recorded as it was.

A cloud build hands back only with its review record written, as the charter's §11 and
`rubric/review-discipline.md` (the driver mandate) say; there is no cloud exception. In a cloud session
the record writer reads the repository, the PR and its issue through REST, and takes the issue the
PR closes from the body's first line, so write the close link there. The record is not written when the writer refuses with `review-record-gh-failed`, or when it returns `ok` but its
final commit was reported by the session rather than read from the PR (`whatIsMissing` names an
unreadable PR). In either case the builder does not hand back. It posts the review receipt on the PR
as a comment naming the head it reviewed, leaves the PR not ready, and parks, naming the review
record as missing. The park is also posted on the issue with `terminal --kind park` (§ Terminal
comments). A record that was written and reads `not-reviewed` or `awaits-owner` for any other reason, such as
an owner-authorized go-ahead covering a missing review, is a written record: handback follows
`skills/review-code/reference/review-record.md`.

After each review round, render that round's whole raw findings file through `render_raw` in
`lib/review_record.py` (the credential check runs on the whole file) and post it as one comment on
the build's pull request when one exists, otherwise on the build's issue, naming the round and the
head it reviewed, before starting the next round. For a round with no findings, post a short "no
findings" line. If `render_raw` refuses the file as too large, post instead a short list of that
round's findings (severity, title, file:line), rendered through `render_raw` before it is posted, and
say the full text was too large. The review
session's own directory lives only on the container and is lost when the session ends.

A cloud session's GitHub writes (`gh api` and the session's GitHub tools alike) pass through an egress
that appends a host footer and wraps each bare `http(s)://` run in backticks, up to the next
whitespace, fenced code included. The record writer's JSON is unaffected because it escapes `/`. A
raw-output comment or the record's summary prose can still show a URL in backticks; nothing parses
those.

When the record writer refuses, follow `skills/review-code/reference/review-record.md` § When it
refuses.

## The cloud container

- The setup text installs `bubblewrap` and `socat` (the Claude write sandbox needs both on Linux;
  without them every claude implementer dispatch fails at start) and the project's pinned
  interpreter. When any of them is missing, install it with the package manager (or
  `uv python install`) before the first dispatch and disclose it in the build record. The setup
  text also fills the dependency caches the project's Python launcher needs; when the setup log
  shows `dependency fill FAILED` (or no fill line for a project that should have one), run the
  launcher once from the builder's own shell before the first dispatch and disclose it in the build
  record.
- The write sandbox has no network. An implementer order inlines or cites only what is in the
  worktree.
- The commit signer is not reachable from inside the write sandbox, so implementers never commit.
  The builder commits their work from its own shell. A test whose fixture makes a git commit fails
  there for the same reason, so the test pins its own git config (`GIT_CONFIG_GLOBAL` set to
  `os.devnull`, `GIT_CONFIG_NOSYSTEM` set to `1`, the fixture passing its commit identity inline)
  and does not depend on the developer's. An order that runs such tests authorizes that pin or
  leaves the run to the builder's own shell.
- A gate command keeps `-B -X pycache_prefix=…`: the write channel's allow rules cover
  `scripts/pinned-python` with any flags. If a sandbox refuses the flag, drop it and keep `-B`,
  because the flag guards a macOS bytecode cache, not this container.
- The size count, run as `python3 -B <plugin root>/lib/size_count.py count --base <sha> --worktree`,
  can fail inside the sandbox on stray dotfiles in the home directory
  (`git-failed: ./.bash_profile`). Run it from the builder's own shell.
- **Credential-like text is redacted.** A cloud session replaces credential-like text (API keys,
  tokens, private keys), for example with a bare `[REDACTED]`, before a file is written or a comment
  posted; the redactor's exact patterns are not known, so this is best effort. Build a test value of
  that kind at runtime from pieces (for example `"sk-" + "a" * 48`) rather than writing it whole, and
  describe such text in a finding or a comment rather than quote it. An order that seeds a
  credential-like test value spells it as pieces too. Implementers get the rule from
  `agents/implementer.md` and review seats from `rubric/review-base.md` and the dispatch preamble. A
  review record field that arrives redacted is flagged as `transitDamage.redactedFields` with a
  `Transit damage:` summary line (`skills/review-code/reference/review-record.md`).

## Verify: cloud-only failures

A test that fails only because of the cloud environment is not a product defect and is never
silenced. A failure counts as environment-only only when both hold:

1. The same test fails the same way on the base commit in the same container.
2. Its output shows a named limitation of the container: the session runs as root (a read or write
   that a mode bit should have stopped succeeds), or the interpreter is not the project's pin.

Anything else that is red on the base too is an unresolved base failure. Report it as that, never
as environment-only.

Keep the failing command and its output in the build record, and disclose it. Claim verification
only with green CI on the same PR head. Where the project owns the test, the preferred remedy is a
test made independent of the user, which is the durable fix.

## Terminal comments: handback, stop, park

A cloud builder posts its handback, every stop and every park **on the build's issue**. Each is a
comment whose first line is one fixed header. The headers are defined once, in `lib/cloud_builder.py`
(`TERMINAL_HEADERS`). They are:

- `Builder handback (cloud build).` The PR is ready and handed back (charter §11).
- `Builder stop (cloud build).` The build stopped before any spend and built nothing: a route-back,
  an Anchor stop report, any intake stop report (charter §1).
- `Builder park (cloud build).` A park with work pushed: a builder note with no answer in the reply
  window, a review that did not run, a missing review record, any other park.

Write the comment's text to a file. Run
`python3 -B <plugin root>/lib/cloud_builder.py terminal --kind handback|stop|park --text-file <file>`.
Post the result's `comment` on the issue as it is. The cloud harness adds its own footer; the readers
allow it.

A park on the PR (the lapsed-review comment, the review receipt) is still posted where § Review says.
The builder also posts a park comment on the issue, because the watch and recovery read the issue.

The refusal at intake keeps its own header (§ Intake). It is not one of these.

What the advisor does with them is the advisor's: `skills/showrunner/reference/wave-watch.md` and
`skills/showrunner/reference/orchestration.md`.

## Handback

Everything the vet needs is on the PR before handback: the review record, the receipts,
the dispositions. Nothing lives only on the cloud machine. Open the PR through the GitHub channel
from § Preflight. Verify the remote head through `cloud_builder.py pr-json`, not `gh pr view`.
A stack layer's build record lists the stack link owed to the advisor (§ Workspace).
The handback comment on the issue is composed with `terminal --kind handback` (§ Terminal comments).

## The gh calls on a cloud build's path

Each `gh pr`, `gh issue` or `gh repo` call that the charter, its reference files and the libraries
they call make at intake, preflight, review and handback, with its cloud stand-in or the reason it is
off a cloud build's path:

| Where | Call | On a cloud build |
|---|---|---|
| `skills/review-code/SKILL.md`, PR mode setup | `gh pr list --head`, `gh pr view --json`, `gh repo view --json nameWithOwner` | the stand-ins in § GitHub reads |
| `skills/workhorse/reference/handback.md`, § The build record | `gh pr view --json body` | `gh api repos/<o>/<r>/pulls/<n> --jq .body` |
| `lib/vet_slot.py`, `--pr <n> --repo <owner/name>` | the PR body through `gh api repos/<o>/<r>/pulls/<n>` (REST); `write` also edits it with `gh pr edit` | the body read works; `write` is the advisor's, not a builder's path |
| `lib/review_record.py`, repo, PR and issue reads | `gh repo view`, `gh pr view`, `gh issue view` | `gh api` (REST) in a cloud session; the closing issue comes from the PR body's first line |
| `lib/pr_body_stage.py publish` (review-code, after a `converged` terminal) | `gh api repos/{owner}/{repo}/pulls/<n>` (REST) to read the body, `gh api -X PATCH repos/{owner}/{repo}/pulls/<n>` to edit it | works |
| `lib/stack_check.py` | `gh repo view`, `gh pr view` | the advisor's: § GitHub reads |
| `rubric/native-stacks.md`, linking a layer | `gh stack link` | the advisor's, at handback: § Workspace, "A stack layer" |
| `lib/pr_comment.py`, `lib/cloud_builder.py` | `gh api` (REST) | works |
| `lib/preflight_probe.py`, `gh_auth_probe` REST fallback | `gh api repos/<o>/<r>` | works |
| `lib/launcher.py`, `lib/wave_watch.py` | `gh pr list`, `gh pr view` | the advisor's, not a builder's path |
| `lib/guardian_sweep.py` | `gh issue view` | the guardian's, not a builder's path |

This page adds `gh api` reads only: the pull request, the issue and its comments, and the
repository.
