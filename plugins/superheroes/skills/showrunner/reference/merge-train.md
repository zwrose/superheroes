# Contents

- [The merge train](#the-merge-train)
- [A merge train's "green" includes post-merge `main` CI](#a-merge-trains-green-includes-post-merge-main-ci)
- [Union fixes ride the last *open* PR, disclosed](#union-fixes-ride-the-last-open-pr-disclosed)
- [Merging a stack](#merging-a-stack)
- [Merging a spec PR](#merging-a-spec-pr)
- [Selecting the run to watch](#selecting-the-run-to-watch)
- [Cleaning up a finished cloud lane](#cleaning-up-a-finished-cloud-lane)
- [When the repository refuses a cloud-built merge](#when-the-repository-refuses-a-cloud-built-merge)

# The merge train

What "green" means for a train of parallel lanes, where a union fix lands, and how a stack merges.
Read this when you drive a train. The merge policy — what the owner's word covers, who may merge,
and the rules for force-push and release — is stated once, in duty 6 of
`skills/showrunner/SKILL.md` ("Coordinate releases and drive the merge train"); this file carries
only the recipes for executing inside it.

## A merge train's "green" includes post-merge `main` CI

Per-lane green on the original parallel heads does not test their union — two PRs that are each
green alone can go red together, at typecheck or anywhere else. Keeping each remaining lane
**branch-current** exposes much of that before its merge (its own CI then builds current `main` plus
its change), and is still not a substitute: a tree that is green pre-merge can go red post-merge on
the identical content, as the next rule's post-merge-only case shows. The train is green when **`main`'s own post-merge run** is green on the
merged head — watched the way the vet watches any run, selected by **workflow name plus head sha**,
never `--limit 1`.
That post-merge run stays the union check whatever the base branch's protection says. Where the
branch does not require pull requests to be up to date before merging, it is also what catches a
union break between PRs whose files do not overlap, so a train does not re-sync and re-test a
remaining PR after every unrelated merge: a PR whose files nothing merged since its last sync
touched, with no conflict, is already current (duty 6). Where the branch does require it, GitHub
refuses a PR that is behind, so every remaining PR is brought current before its merge, never
skipped with an admin bypass, and that saving does not apply. The saving never covers a stack: a
stack whose base moved is brought current bottom-up as `rubric/native-stacks.md` § How a stack
stays current says, whatever the base branch requires.
Read the requirement before the train's first merge, for the base branch (`main` here):
`gh api --paginate repos/<owner>/<repo>/rules/branches/main --jq '.[] | select(.type=="required_status_checks") | .parameters.strict_required_status_checks_policy'`
(rulesets, every page) and `gh api repos/<owner>/<repo>/branches/main/protection --jq '.required_status_checks.strict'`
(classic protection; a 404 "Branch not protected" answers "none"). Either one reporting `true`
means the branch requires it. Any other failure of either read counts as requiring it.
A third read, apart from those two, asks whether the base has a merge queue:
`python3 -B <plugin root>/lib/merge_queue.py read --repo <owner/name> --branch <base>`. A stack's
straightening depends on it (§ Merging a stack, item 4).

**When a merge is reported done without waiting.** The advisor reports a merge done, and goes on
with the train, without waiting for `main`'s post-merge run only when both of these hold:

1. **The base branch requires pull requests to be up to date, and both reads answered.** One of the
   two reads above reports `true`, and neither read failed: the classic read may answer with its 404
   "Branch not protected", but any other 404, a 403, or any other failure of either read is a failed
   read. A failed read still counts as requiring up-to-date PRs when you bring PRs current; here it
   keeps the wait.
2. **The merged commit's tree is the tree CI passed.** After `git fetch origin main`,
   `git rev-parse --verify <merged sha>^{tree}` and `git rev-parse --verify <head sha>^{tree}` both
   succeed and print the same tree. The head is the merged PR's head whose green the merge relied
   on, its run selected by workflow name plus head sha ([Selecting the run to
   watch](#selecting-the-run-to-watch)); for a stack, its top layer's head. Because the branch
   requires up-to-date PRs, that head already held the base, so its `pull_request` run's test merge
   built the head's own tree. Either command failing, or two different trees, keeps the wait. A
   merge through a merge queue keeps the wait too: its run tests the queue's own commit.

The post-merge run still runs, and the train is still green only when it is green: a red one is a
red train, fixed by the recipe below, the post-merge-only red included. The advisor reads its result
at its next pass, selected the same way, instead of blocking on it. The pre-merge green is still
not a substitute for that run, as above and as the post-merge-only red below shows: the exception
changes only when the merge is reported, never what makes the train green. In every other case the
wait stays as it is.

## Union fixes ride the last *open* PR, disclosed

While a lane is still open, the fix lands on **that** branch as a disclosed integration commit — never
a silent push to `main`, never a merged lane re-opened. That absorber exists only while a lane is
open, and an earlier merged head's `main` run can still be pending when the last one merges — so once
the last lane has merged there is nothing left to absorb into, and a red `main` takes a **disclosed
follow-up PR** from the failing head through the same preconditions.

Typing the fix is advisor build work of the micro kind, the charter's one build exception, so it
stays inside duty 6's boundary. An integration fix stays the size of an integration fix. Anything larger routes to a builder like any other change.
The fix carries micro's review floor on the final head: one cross-vendor reviewer, whose reading the
review record shows. It does not reclassify the PR. The containing lane keeps its own route, its DoD, and
its advisor vet.

A red on the train is a per-lane green that goes red on the union or on `main`'s post-merge run.
Land its fix as the disclosed integration commit on the last open PR, or as the disclosed
follow-up PR once the last lane has merged. Either way the merge rides a saved "Merge" verdict on
its current sheet together with "done" (duty 6). A moved head keeps the word when the fix is not
material (duty 6 and `owner-decisions.md` say how it is judged and republished), and a new
follow-up PR gets its own sheet and asks through it. Report it in the thread like any merge.

**The post-merge-only red.** A test green on the identical tree pre-merge can go
**deterministically** red post-merge in CI only — coverage-instrumented runners, for one, can lose
an assertion race. While a lane is still open, close it with a disclosed integration commit on the
last open PR's branch; once the last lane has merged, there is nothing left to absorb into, so
close it with a disclosed follow-up PR from the failing head instead.

## Merging a stack

**The invariant:** the owner's word is a saved "Merge" verdict plus "done" on the stack's sheet,
which lists the stack's pull requests, and the merge acts on exactly those pull requests. A stack is
a **mutable container** — a layer can be linked onto it after the word is given — so a merge issued
against a stack **number** can act on a pull request the owner never saw. Nothing in the tooling closes that gap; this rule does.

1. **Membership is read from GitHub before any PR sheet is built** — GitHub's own membership read
   (GraphQL, or REST in a cloud session through the same `lib/stack_check.py` invocation) in
   `rubric/native-stacks.md` § *How membership is verified*. That read is performed by
   `lib/stack_check.py` as `python3 -B <plugin-root>/lib/stack_check.py list --pr <a member pull
   request> --repo <owner/name>` — the entry point is **a member pull request** because GitHub's
   GraphQL schema has no stack-by-number entry point, and `--stack <n>` is available only as a
   **cross-check** against the stack the read actually enters. `gh stack view` reads local tracking
   state only and is never evidence (see `rubric/native-stacks.md` § *Anti-patterns*). A base-branch chain that was never
   linked is **not** a stack and cannot be merged as one.

2. **The word covers exactly the pull requests the stack's sheet lists**, the sheet that carries the
   saved "Merge" verdict: the whole stack, in order (the showrunner charter's **The word** in duty
   6). There is no prefix word, and no word narrows a stack. A layer linked onto the stack **after**
   its sheet was published is **outside** the word, and its arrival changes the stack, so the sheet
   is replaced by an unsigned one. This is not a head move: a head move is judged by the
   material-consequence line, while a newly linked layer is always outside the word.

3. **Immediately before the irreversible command, re-read remote membership** and compare **the
   sheet's list**, the whole stack, to the remote entries. Mismatch — a different order, a missing
   member, an unexpected layer, a member no longer open or now draft, or a head sha that no longer
   matches the recorded evidence — **refuses**, and the advisor asks the owner again rather than
   merging a container whose contents changed. Full-stack equality with the sheet's list is always
   required, whether the merge is invoked by pull request number or by stack number. This re-read is
   not optional and is not satisfied by the earlier read when the sheet was built: the point of it is
   the window between them. The re-read is the same
   `lib/stack_check.py` invocation again; a non-zero exit **refuses** and stops the merge, returning
   the refusal `reason` from `lib/stack_check.py` (`REASON_*` constants).

4. **Straighten the stack once, when its base has a merge queue.** Builders keep merging to stay
   current and never force-push, so a stack's layers carry merge commits. A direct merge accepts
   them and a merge queue drops them (`rubric/native-stacks.md` § *How a stack merges*). This item
   runs after review, the vet and the stack's merge word, and after item 3's re-read. It is the
   advisor's work, in a clean clone the advisor owns, never a builder's worktree. The steps, in order:

   (a) **Read the base for a queue.** `python3 -B <plugin root>/lib/merge_queue.py read --repo
   <owner/name> --branch <the stack's baseRefName>`. It makes two reads: the rulesets read
   (`repos/{owner}/{repo}/rules/branches/{branch}`, every page, a row of type `merge_queue`) and the
   GraphQL cross-check (`repository.mergeQueue(branch:)`, which catches a queue set in classic
   branch protection). `queue: false` → skip this item; the merge-commit stack merges as today,
   at item 5. `queue: true` (a rules row, a GraphQL queue, or a failed read) → straighten. A cloud
   session's GraphQL refusal is a failed read, so a cloud advisor always straightens a stack whose
   layers carry merge commits.

   (b) **Check.** `python3 -B <plugin root>/lib/stack_linear.py check --repo <owner/name> --pr
   <bottom> ... --pr <top>`, bottom to top. Exit 0 → the stack is already linear; go to item 5.
   `stack-not-linear` → straighten. `linearity-unreadable` → stop and report; never merge on an
   unreadable read.

   (c) **Rebase on pinned shas.** Fetch the stack's branches. `<base>` is the main commit the vetted
   bottom already contains: the newest main commit its history holds, never a newer main. Bottom:
   `git rebase --no-rebase-merges --onto <base> <base> <vetted bottom head>`. Each layer above: `git
   rebase --no-rebase-merges --onto <new head of the layer below> <vetted head of the layer below>
   <vetted head of this layer>`. The flag is explicit because a clone with git's
   `rebase.rebaseMerges` setting on would otherwise keep the merge commits. Every
   rebase runs on a detached head, so no branch moves. Do not use `gh stack rebase` or `gh stack
   push`: `gh stack rebase` fetches and rebases onto the newest trunk, and `gh stack push`
   re-fetches and leases against the refreshed tracking refs, so a head that moved after the proof
   could be overwritten. Both also need a locally tracked stack, which a lane-built stack is not.

   (d) **A rebase conflict** aborts: `git rebase --abort`. Nothing was moved and every branch stays at
   its vetted head. Such a conflict is one the vetted layer already resolved in a bring-current merge,
   so a fix leg cannot clear it: its merge would find main already in the layer and do nothing. Never
   send it to a fix leg, and never resolve it by hand. Rebuild that layer as one commit carrying its
   vetted tree: `git commit-tree <vetted head>^{tree} -p <new head of the layer below> -m "<the layer's
   PR title>"` (for the bottom layer, `-p <base>`), on no branch. The sha it prints is the layer's new
   head. The layers above rebase onto it as in (c), and step (e)'s `prove` covers it as any layer.

   (e) **Prove before pushing.** `python3 -B <plugin root>/lib/stack_linear.py prove --repo-root
   <clone> --base <base> --layer <branch> <vetted head> <new head> <pr> ... --pr-body <pr> <file>
   ...`, one `--layer` and one `--pr-body` per layer, bottom to top. Save each layer's current PR
   body to a file first (`gh api repos/<o>/<r>/pulls/<n> --jq .body`). Any refusal stops, and
   nothing is pushed. `tree-changed` means the rebase changed a
   file: treat it as a content change, which falls to the "content changed" branch (the
   unequal-digest branch of `skills/showrunner/reference/vet-receipt.md` spine field 1), never a push.
   On `fixed-above-stale`, edit each named line in that layer's PR body to the `replacement` `prove`
   printed (the rewritten head, whose files `prove` showed unchanged), record the swap with the
   dated re-pin line, save the bodies again and re-run `prove`; nothing is pushed until it passes.
   `fixed-above-unknown-layer` stops the straightening: the line names a PR outside this stack.

   (f) **Push once.** Run the `push` argv that `prove` printed, as it is: one atomic push, every
   lease pinned to the vetted head. It rides the owner's standing grant, recorded in the project's
   Canon, for this straightening (`skills/showrunner/SKILL.md` duty 6), with the reason stated on
   the stack's sheet. Without that Canon entry the push asks its own word, as any force-push does. A
   refused lease (a head moved since the vet) fails the whole push: re-read and start over.

   (g) **Re-pin and merge.** Re-pin each layer's receipt with the `repin` line `prove` printed
   (old head, new head, equal tree hash). Wait for CI green on every new head, selected by workflow
   name plus head sha. Republish the stack's sheet carrying its verdict forward
   (`carriedForward.fromSheet`, `heads` the new heads): a tree-proven straightening is not a
   material move. Then **re-read membership again** (item 3's re-read, repeated after the push). The
   straightening moved every head, so the merge's `--sha` and the sheet comparison take the new
   heads from this second re-read. Then merge with item 5's command: `gh stack merge`, since `gh pr
   merge` refuses a stacked pull request, or `stack_merge.py merge` in a cloud session, which
   re-checks linearity itself.

   (h) **When the harness refuses `gh stack merge`** (a permission or classifier refusal, not a
   GitHub refusal), hand over to the owner. Tell the owner in chat the exact command, the stack
   number and the top layer's head sha, and that the stack is straightened and CI is green. The
   owner runs it. Never retry in another form.

5. **One command merges the stack, in order** — `gh stack merge <stack-or-pr> --yes --squash`; the
   command merges the whole stack the sheet lists, and the target is its top layer. The argument is `[<stack-number> |
   <pr-number>]` per `gh stack merge --help` — with no argument the stack of the current branch is
   used — and a bare number is read first as a stack number, then as a pull request number, so
   verify that number against the sheet's list in item 3 immediately before the command runs. A
   **direct** merge is atomic (all or nothing);
   a **merge-queue** merge is ordered and best-effort and can leave a merged prefix on the trunk.
   **Never pull request by pull request**: serial merges are the anti-pattern
   (`rubric/native-stacks.md` § *Anti-patterns*), and they leave the trunk holding intermediate
   layers if one member fails. Merge semantics, the bare-number ambiguity, per-pull-request
   branch-protection evaluation, the history condition each layer must satisfy, and merge-queue
   behaviour live in `rubric/native-stacks.md` § *How a stack merges*.
   In a cloud session the equivalent is `python3 -B <plugin-root>/lib/stack_merge.py merge --repo
   <owner/name> --top <top layer> --sha <its head from item 3's re-read>`. A non-zero exit is not
   merged, and the train reports the result's `reason`. The default wait is 420 seconds in all,
   the PUT included, so a `poll-timeout` result and its `uuid` print before the 600-second host
   cap. `merge-enqueued` is read back later as a
   queued merge: it is not merged, and a queued stack is not atomic, as `rubric/native-stacks.md`
   says.

   **The PR sheets name whole stacks.** A stack merges when its **feature** is complete — every
   layer the issue's plan names, vetted — and never when a vetted prefix exists. **A vetted prefix is
   never a click.** A stack's sheet names the whole stack with its remaining layers, and an incomplete
   stack gets no sheet. New scope that a tripwire or a vet discovers **on that feature** joins the
   stack as a layer rather than becoming a follow-on, while a finding outside the feature's
   owner-ratified scope stays a follow-up under the existing scope rule. The doctrine home is `rubric/native-stacks.md` § *How a stack merges*.

   This rule and items 2 and 3 govern different moments, so do not read one against the other. This
   rule governs what the advisor puts in front of the owner, and an incomplete stack never goes
   there. Items 2 and 3 govern how the word, once given, is checked against the remote, and that word
   covers the whole stack the sheet lists. Neither licenses building a sheet on a prefix.

6. **A stack is brought current by merge, bottom-up** — merge the layer below into each affected
   layer locally with `--no-ff` and push that merge plainly, starting just above the change, which
   keeps every layer's own commits (`rubric/native-stacks.md` § *How a stack stays current*, the home
   of the mechanism). Never bring current a layer whose review loop is still open: the merge breaks
   that review session with `view-head-anchor-mismatch`, so wait for the loop to end. Do not use `gh pr update-branch`. The REST endpoint behind it was **observed**
   to refuse a stacked pull request with a **403**, which is a field observation on a public-preview
   feature rather than a documented GitHub rule. The merge commits this leaves are removed once, at
   merge time, by item 4's straightening when the base has a merge queue.

   A bring-current is a **mechanical operation**. Each moved head takes a fresh remote-head check, CI
   on the new sha, and a receipt re-pinned to that sha **and to the digest of the pull request's
   diff** — `skills/showrunner/reference/vet-receipt.md` spine field 1 owns the digest and the command
   that takes it. **Equal digest.** Re-pin the sha in place with a dated line, let CI run on the new
   head, and re-review nothing. **Unequal, or `digest-unavailable`.** Run `git range-diff --remerge-diff
   <base-before>..<head-before> <base-after>..<head-after>` to name the changed commits, where
   **base-before** and **base-after** are the tip of the layer below before and after the
   bring-current and **head-before** and **head-after** are the layer's head before and after. A
   changed hunk takes the **mechanical non-semantic** path — CI and a disclosure
   line, no reviewer — only when the change is mechanically non-semantic: whitespace, pure
   formatting, a comment, or a line re-wrap that leaves the rule unchanged. A changed hunk takes this
   file's existing union-fix floor — [Union fixes ride the last *open* PR,
   disclosed](#union-fixes-ride-the-last-open-pr-disclosed) plus micro's review floor of one
   cross-vendor reviewer, whose reading the review record shows — and not a new loop whenever it changes
   **behavior-bearing content**: product code; a test's assertions or fixtures' expected values; or any
   prose that states a rule a session or a gate follows. When it is **not clear** which side a hunk
   falls on, it takes the reviewer floor.

   Every bring-current, conflict-free or not, is judged by the material-consequence line before the
   word is carried: a clean textual merge can still change the approved feature's behavior, for
   instance when a lower layer changes a shared default an upper layer relies on without touching
   that layer's diff, and the digest and review checks above do not establish that the owner
   approved that consequence. Only when the judgment finds no material consequence is the stack's
   single sheet republished carrying its verdict forward, with `carriedForward.fromSheet` naming its
   previous revision and `heads` giving the new head of every PR the sheet covers, and the stack's
   word stands. A move that is material, or in doubt, is republished unsigned, and doubt counts as
   material.

   GitHub's cascading rebase (the server-side **Rebase stack** action for a lane; `gh stack rebase`
   + `gh stack push` only for a local tracked stack an operator owns end to end) is the disclosed
   alternative when a merge cannot resolve the conflict; it rewrites every commit of every affected
   layer, so every affected layer's head moves. What each moved head then owes is decided by the
   content pin: recompute the digest, and an **equal digest** re-pins the sha with a dated line and
   lets CI run on the new head with nothing re-reviewed, while an **unequal digest or
   `digest-unavailable`** takes the branch the pin defines
   (`skills/showrunner/reference/vet-receipt.md` spine field 1). Never a hand-rebase or force-push of
   a layer under review, which the doctrine names as an anti-pattern (`rubric/native-stacks.md`
   § *Anti-patterns*). Item 4's merge-time straightening is not that path: it runs after the
   vet, in the advisor's own clone, and is tree-proven.

7. **After the merge, report what merged** — each pull request number with the head sha that landed
   — and then this file's existing rules apply unchanged: the train is green when **`main`'s own
   post-merge run** is green on the merged head, selected by workflow name plus head sha ([A merge
   train's "green" includes post-merge `main` CI](#a-merge-trains-green-includes-post-merge-main-ci),
   [Selecting the run to watch](#selecting-the-run-to-watch); that section says when the merge is
   reported done without waiting for that run). Reading back each landed layer's
   sub-issue and closing the feature issue follow [Each layer is a
   sub-issue](../../../rubric/native-stacks.md#each-layer-is-a-sub-issue), item 6.

   A merged pull request that a cloud lane built is then cleaned up as [Cleaning up a finished cloud
   lane](#cleaning-up-a-finished-cloud-lane) says.

8. **What a vet checks per layer, and what it checks once per stack.** **Per layer:** its own DoD
   rows (the layer's DoD and order live in its own sub-issue — [Each layer is a
   sub-issue](../../../rubric/native-stacks.md#each-layer-is-a-sub-issue)), its own review
   dispositions and receipts, its own CI on its own head, its base — for each
   non-bottom layer, the layer below's branch; for the bottom layer, the stack's base
   (`baseRefName`) — and its membership read back. **Once per stack, at the top:** that the ordered
   entries of the whole stack equal the layers the advisor planned and the stack's sheet lists, that
   no member is unexpected, and that the stack's `baseRefName` matches the planned or owner-approved
   base.

## Merging a spec PR

The rule is not here. One merge word covers a spec and its breakdown, and the approval is never the
merge word: that is duty 1 and duty 6 of `skills/showrunner/SKILL.md`.

The word you execute under is the owner's saved Merge verdict on the spec PR's sheet, then "done". Build
that sheet with `lib/pr_sheet.py build` in its spec-PR mode, with no code review record (its review is its spec checks, duty 6)
(`theme/review-template.md` § A PR sheet and a stack sheet). Its breakdown card lists every issue body the
filing creates, so accepting it and saving Merge covers the spec and its breakdown together. The build
refuses a pin that no longer hashes to its pinned value, which is item 2 below, checked again when the
sheet is built.

Before you execute, confirm four things:

1. The approval is recorded with its date.
2. The breakdown's vet record is clean, and every file it pins still hashes to the pinned value
   ([spec-vet.md](spec-vet.md#vetting-the-breakdown)). This check also runs where the stored spec
   stands in for the PR.
3. Where the package read applies, its verification pass and filing dry-run are recorded in the
   audit trail, and the only change between the head they ran against and this head is that record
   itself. With a spec PR, `git diff --stat <that head> HEAD` lists only the audit-trail file; for a
   stored spec outside Git there is no head, so the pinned file hashes in item 2 are the freshness
   check, and they bind the verification only when the audit trail's verification and dry-run
   entries name the content hash of each body they ran against and those hashes equal the pins. A
   body changed after those entries means the affected checks run again, and the entries are
   rewritten with the new hashes, before the breakdown is vetted and pinned.
4. With a spec PR, duty 6's three preconditions hold. A stored spec has no PR, so the PR-lane
   review evidence, the recorded-head CI and the branch-current check do not apply to it; items 1
   to 3 are its whole gate.

Then merge the PR, and file the issues from the merged breakdown at once, under the same word. Wire
each issue as duty 2 says. For an epic's breakdown, title each child `<Tag> Cn — …` and each layer
`<Tag> Cn layer k — …`, with the epic's short tag ([decomposition.md](decomposition.md#the-epics-short-tag)).

If filing fails partway, report it in the thread that gave the word and finish filing. Never re-merge
or revert to retry. If the merge does not happen, nothing files.

Where the stored spec stands in for the PR, there is nothing to merge and no PR-specific
precondition to meet: once items 1 to 3 hold, the owner's word at that step files the issues.

## Selecting the run to watch

Both rules above turn on watching the right run, so select it by **workflow name plus head sha** —
never `gh run list --limit 1`, which returns whichever workflow ran latest on that branch, so it can
report another workflow's green as the one you are watching. The canonical statement is field 1 of the vet receipt's spine, in
`skills/showrunner/reference/vet-receipt.md`.

## Cleaning up a finished cloud lane

A cloud lane leaves a session on the owner's account and a pushed branch, and no checkout or worktree
on the owner's machine. This section is the one home of how they are cleaned up.

1. **When.** Once the lane's pull request has merged, or has closed unmerged; the steps are the same
   for both. Never while the pull request is open, whether the builder handed back or parked: the
   pushed branch stays for the vet, a renewed review or a recovery.
2. **Plan, then ask.** Run `python3 -B <plugin root>/lib/cloud_cleanup.py plan --repo-root <root>
   --repo <owner/name> --pr <number>`. On `none`, stop. On `cleanup` with `alreadyDelivered`, send
   nothing and go to the branch step. On `cleanup` with `archiveHeld: "stack-open"` (a stack whose layers are not all closed), send nothing and go to the branch step; the plan of the stack's last layer to close carries the archive text. On `archiveHeld: "stack-unreadable"` (the stack could not be read), send nothing and go to the branch step; the archive request is still owed, so re-run `plan` for the same PR later, and until a plan carries the archive text, tell the owner that the session stays listed. On any other `cleanup`, first persist the attempt under the
   message id the send will carry. For another account, run the relay's `ensure`, `compose` (with the
   plan's `archiveText` written to a file as the text file), the post of the composed file and `point`
   first (`skills/showrunner/reference/wave-watch.md` § Answering a builder note has how each is done),
   because `compose` mints the message id itself: take its `msgId`. An attempt
   interrupted before the reservation below leaves nothing recorded, and a later run composes afresh.
   For the same account by `SendMessage` there is no relay
   id, so make one unique to this attempt, `same-account-<pr number>-<UTC timestamp>`, and keep it for
   this attempt's `pending` and final writes (a settlement carrying an older attempt's id then never matches a newer reservation). Then run `cloud_cleanup.py record --repo-root <root> --repo
   <owner/name> --pr <number> --msg-id <id> --outcome pending --launch-id <the plan's launchId>`. That write is the
   reservation to send: when it is refused (`request-in-progress`, `request-uncertain` or
   `request-delivered`), another caller holds or has settled the request, so send nothing and go on. Only when it succeeds, send the plan's
   `archiveText` to the lane's session: on the same account by `SendMessage`, on another account
   by sending the printed `relayMessage` and then `check`, as that section says. Then run
   `record` with the same message id and the outcome. On another account it is settled by that section's
   one rule: `delivered`
   when `check` reads `delivered: true`, `failed` when it reads `nothingReached: true`, otherwise
   `uncertain`. On the same account it is settled by the `SendMessage` result: `delivered` on
   `success: true`, `failed` on `success: false`, and `uncertain` when the call returned no result. Pass the plan's `launchId` as `--launch-id` to every `record`
   and to `branch`, so each settles the lane that was planned. A plan whose `request` is already `pending` or
   `uncertain` is a resume after an unconfirmed send: send nothing. When that message id came from the relay (another
   account), first run `cloud_relay.py check --repo-root <root> --msg-id <id>` (as `wave-watch.md` § Answering a
   builder note describes) and record `delivered` when it reads `delivered: true`, `failed` when it reads `nothingReached: true` (nothing reached the
   builder, so a later run of this procedure may send again), otherwise `uncertain`. A
   same-account id has no check, so record `uncertain`. Then go on. A `pending` or `uncertain` request is never sent a second time.
   A `check` that reads `delivered: true` on either basis (`relay-report` or `comment-and-activity`) settles the
   request `delivered`, a request recorded `uncertain` earlier and re-checked included: the `uncertain` receipt is
   replaced, and the plan then carries no archive text. A builder that archives itself without posting anything
   shows no activity, so its request stays `uncertain`.
3. **Tell the owner.** On `delivered`, tell the owner the `ownerMessage` as it is. On any other
   outcome, tell the owner that the archive request to that build's session could not be confirmed
   and that its session stays listed. Ask nothing more of the owner than the `ownerMessage` asks.
4. **The branch.** Run `cloud_cleanup.py branch --repo-root <root> --repo <owner/name> --pr <number>
   --launch-id <the plan's launchId>`.
   GitHub deletes the pull request's branch when the repository deletes merged branches; otherwise
   this step deletes it through GitHub, only while it still points at the pull request's head. It reports `deleted: false` with
   `already: "absent"` when the branch was already gone. The step reports what a re-read of the branch shows, never
   what the delete call returned. A refusal (`branch-moved`, `branch-in-use`, `default-branch`,
   `head-repo-foreign`, `delete-unconfirmed`, `delete-outcome-unknown`) is reported to the owner, never worked around.
5. **What is left.** The session, until it is archived as the `ownerMessage` says, and the lane's record. The branch is
   gone, and a cloud launch made no checkout or worktree to remove.

A stack launched once on its parent issue cleans up as one lane: each layer's plan names the parent issue's lane and
carries `viaParent` (a layer whose PR links both its sub-issue and the parent issue counts as a layer), the archive
request goes once for the lane and only once every sub-issue of the lane's issue is closed, and a later layer's plan
carries that request (its `pr` names the layer it was recorded on, so a `pending` or `uncertain` one is settled with
`record --pr <that pr>`); the branch step runs for each layer's own branch.

If the owner never answers the archive prompt, the session stays listed and the advisor carries on; nothing reminds the owner.

## When the repository refuses a cloud-built merge

A cloud builder's commits carry the cloud's own author, not the owner's. A default-branch ruleset
with **`require_extra_approval_for_unattributed_changes`** on has refused such a pull request's
merge with "the base branch policy prohibits the merge" even though the vet was READY, CI was green
and the owner's word was given; turning that one option off cleared it. Read the option with
`gh api repos/<owner>/<name>/rules/branches/<default branch>`. The advisor cannot supply the
approval the rule asks for: it acts as the owner's account, a cloud-built pull request is opened
under the owner's name, and GitHub never lets an author approve their own pull request.

Tell the owner at once. Turning that option off is their setting, and the vet, the word and CI stay
the gate. Any other route is the owner's to choose and to carry out. Never use `gh pr merge
--admin`, and never add a commit only to change the pull request's attribution, without the owner's
word for that act.
