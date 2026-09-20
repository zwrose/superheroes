# Contents

- [The merge train](#the-merge-train)
- [A merge train's "green" includes post-merge `main` CI](#a-merge-trains-green-includes-post-merge-main-ci)
- [Union fixes ride the last *open* PR, disclosed](#union-fixes-ride-the-last-open-pr-disclosed)
- [Merging a stack](#merging-a-stack)
- [Selecting the run to watch](#selecting-the-run-to-watch)

# The merge train

What "green" means for a train of parallel lanes, and where a union fix lands. Read this when you
drive a train. The **showrunner** charter's duty 6 carries the delegation boundary and the
preconditions that never waive; this file carries the train's own two rules.

## A merge train's "green" includes post-merge `main` CI

Per-lane green on the original parallel heads does not test their union — two per-lane-green PRs went
red on the union at typecheck. Keeping each remaining lane **branch-current** exposes much of that
before its merge (its own CI then builds current `main` plus its change), and is still not a
substitute: a tree that is green pre-merge can go red post-merge on the identical content, as the
next rule's field case shows. The train is green when **`main`'s own post-merge run** is green on the
merged head — watched the way the vet watches any run, selected by **workflow name plus head sha**,
never `--limit 1`.

## Union fixes ride the last *open* PR, disclosed

While a lane is still open, the fix lands on **that** branch as a disclosed integration commit — never
a silent push to `main`, never a merged lane re-opened. That absorber exists only while a lane is
open, and an earlier merged head's `main` run can still be pending when the last one merges — so once
the last lane has merged there is nothing left to absorb into, and a red `main` takes a **disclosed
follow-up PR** from the failing head through the same preconditions.

Typing the fix is advisor build work of the micro kind, the charter's one build exception, so it
stays inside duty 6's boundary. An integration fix stays the size of an integration fix. Anything larger routes to a builder like any other change.
The fix carries micro's review floor on the final head: one cross-vendor reviewer plus an engaged
control probe. It does not reclassify the PR. The containing lane keeps its own route, its DoD, and
its advisor vet.

A red on the train is a per-lane green that goes red on the union or on `main`'s post-merge run.
When the fix is craft with no
[material consequence](../../../rubric/glossary.md#material-consequence), fix it under the word
already given: the
disclosed integration commit on the last open PR, or the disclosed follow-up PR once the last lane
has merged, rides the scope and is reported in the thread like any merge. That follow-up PR is the
one exception to the rule that a PR opened after the word asks again, and it holds only while the
fix is craft with no material consequence. A fix with a material consequence asks.

**Field case:** a test green on the identical tree pre-merge went **deterministically** red post-merge
in CI only (coverage-instrumented runners lose an assertion race); a disclosed integration commit on
the last open PR's branch is what closed it.

## Merging a stack

**The invariant:** the owner's word names pull requests, and the merge acts on exactly those pull
requests. A stack is a **mutable container** — a layer can be linked onto it after the word is
given — so a merge issued against a stack **number** can act on a pull request the owner never
saw. Nothing in the tooling closes that gap; this rule does.

1. **Membership is read from GitHub before any click list is drafted** — the GraphQL read in
   `rubric/native-stacks.md` § *How membership is verified*. That read is performed by
   `lib/stack_check.py` as `python3 -B <plugin-root>/lib/stack_check.py list --pr <a member pull
   request> --repo <owner/name>` — the entry point is **a member pull request** because GitHub's
   GraphQL schema has no stack-by-number entry point, and `--stack <n>` is available only as a
   **cross-check** against the stack the read actually enters. `gh stack view` reads local tracking
   state only and is never evidence (see `rubric/native-stacks.md` § *Anti-patterns*). A base-branch chain that was never
   linked is **not** a stack and cannot be merged as one.

2. **The word enumerates every pull request in the intended merge prefix**, by number and in order —
   the showrunner charter's **The word** in duty 6; a layer linked onto the stack **after** the
   word is **outside** that word.

3. **Immediately before the irreversible command, re-read remote membership** and compare the owner's
   enumeration to the remote entries **through the chosen target pull request** — not the whole
   stack when the word names a prefix. Mismatch — a different order, a missing member, an unexpected
   layer **within that prefix**, a member no longer open or now draft, or a head sha that no longer
   matches the recorded evidence — **refuses**, and the advisor asks the owner again rather than
   merging a container whose contents changed. Layers **above** the chosen target are outside this
   operation and are not a mismatch. **Full-stack** equality is required only when the merge is
   invoked by **stack number**. This re-read is not optional and is not satisfied by the earlier read
   at click-list time: the point of it is the window between them. The re-read is the same
   `lib/stack_check.py` invocation again; a non-zero exit **refuses** and stops the merge, returning
   the refusal `reason` from `lib/stack_check.py` (`REASON_*` constants).

4. **One command merges the stack, in order** — `gh stack merge <stack-or-pr> --yes --squash`; every
   member up to and including the chosen pull request. The argument is `[<stack-number> |
   <pr-number>]` per `gh stack merge --help` — with no argument the stack of the current branch is
   used — and a bare number is read first as a stack number, then as a pull request number, so
   verify that number against the enumeration in item 3 immediately before the command runs. A
   **direct** merge is atomic (all or nothing);
   a **merge-queue** merge is ordered and best-effort and can leave a merged prefix on the trunk.
   **Never pull request by pull request**: serial merges are the anti-pattern
   (`rubric/native-stacks.md` § *Anti-patterns*), and they leave the trunk holding intermediate
   layers if one member fails. Merge semantics, the bare-number ambiguity, per-pull-request
   branch-protection evaluation, the history condition each layer must satisfy, and merge-queue
   behaviour live in `rubric/native-stacks.md` § *How a stack merges*.

   **The click list names whole stacks.** A stack merges when its **feature** is complete — every
   layer the issue's plan names, vetted — and never when a vetted prefix exists. **A vetted prefix is
   never a click.** The click list names whole stacks with their remaining layers, and an incomplete
   stack is never listed. New scope that a tripwire or a vet discovers **on that feature** joins the
   stack as a layer rather than becoming a follow-on, while a finding outside the feature's
   owner-ratified scope stays a follow-up under the existing scope rule. The owner's standing rule is
   "keep stacks stacks". The doctrine home is `rubric/native-stacks.md` § *How a stack merges*.

   This rule and items 2 and 3 govern different moments, so do not read one against the other. This
   rule governs what the advisor puts in front of the owner, and an incomplete stack never goes
   there. Items 2 and 3 govern how a word, once given, is checked against the remote, and that word
   may still name a prefix because the owner may narrow what the advisor listed. Neither licenses
   drafting a click list on a prefix.

5. **A stack is brought current by merge, bottom-up** — merge the layer below into each affected
   layer locally with `--no-ff` and push that merge plainly, starting just above the change, which
   keeps every layer's own commits (`rubric/native-stacks.md` § *How a stack stays current*, the home
   of the mechanism). Do not use `gh pr update-branch`. The REST endpoint behind it was **observed**
   to refuse a stacked pull request with a **403**, which is a field observation on a public-preview
   feature rather than a documented GitHub rule.

   A bring-current is a **mechanical operation**. Each moved head takes a fresh remote-head check, CI
   on the new sha, and a receipt re-pinned to that sha **and to the digest of the pull request's
   diff** — `skills/showrunner/reference/vet-receipt.md` spine field 1 owns the digest and the command
   that takes it. **Equal digest.** Re-pin the sha in place with a dated line, let CI run on the new
   head, and re-review nothing. **Unequal, or `digest-unavailable`.** Run `git range-diff
   <base-before>..<head-before> <base-after>..<head-after>` to name the changed commits, where
   **base-before** and **base-after** are the tip of the layer below before and after the
   bring-current and **head-before** and **head-after** are the layer's head before and after. A
   changed hunk takes the **mechanical non-semantic** path — CI and a disclosure
   line, no reviewer — only when the change is mechanically non-semantic: whitespace, pure
   formatting, a comment, or a line re-wrap that leaves the rule unchanged. A changed hunk takes this
   file's existing union-fix floor — [Union fixes ride the last *open* PR,
   disclosed](#union-fixes-ride-the-last-open-pr-disclosed) plus micro's review floor of one
   cross-vendor reviewer and an engaged control probe — and not a new loop whenever it changes
   **behavior-bearing content**: product code; a test's assertions or fixtures' expected values; or any
   prose that states a rule a session or a gate follows. When it is **not clear** which side a hunk
   falls on, it takes the reviewer floor.

   GitHub's cascading rebase (the server-side **Rebase stack** action for a lane; `gh stack rebase`
   + `gh stack push` only for a local tracked stack an operator owns end to end) is the disclosed
   alternative when a merge cannot resolve the conflict; it rewrites every commit of every affected
   layer, so every affected layer's head moves. What each moved head then owes is decided by the
   content pin: recompute the digest, and an **equal digest** re-pins the sha with a dated line and
   lets CI run on the new head with nothing re-reviewed, while an **unequal digest or
   `digest-unavailable`** takes the branch the pin defines
   (`skills/showrunner/reference/vet-receipt.md` spine field 1). Never a hand-rebase or force-push of
   a layer under review, which the doctrine names as an anti-pattern (`rubric/native-stacks.md`
   § *Anti-patterns*).

6. **After the merge, report what merged** — each pull request number with the head sha that landed
   — and then this file's existing rules apply unchanged: the train is green when **`main`'s own
   post-merge run** is green on the merged head, selected by workflow name plus head sha ([A merge
   train's "green" includes post-merge `main` CI](#a-merge-trains-green-includes-post-merge-main-ci),
   [Selecting the run to watch](#selecting-the-run-to-watch)).

7. **What a vet checks per layer, and what it checks once per stack.** **Per layer:** its own DoD
   rows, its own review dispositions and receipts, its own CI on its own head, its base — for each
   non-bottom layer, the layer below's branch; for the bottom layer, the stack's base
   (`baseRefName`) — and its membership read back. **Once per stack, at the top:** that the ordered
   entries **through the chosen target pull request** equal the layers the advisor planned and the
   owner enumerated (full-stack equality only when merging by stack number), that no member within
   that scope is unexpected, and that the stack's `baseRefName` matches the planned or owner-approved
   base.

## Selecting the run to watch

Both rules above turn on watching the right run, so select it by **workflow name plus head sha** —
never `gh run list --limit 1`, which returns whichever workflow ran latest on that branch and has
already produced a false green. The canonical statement is field 1 of the vet receipt's spine, in
`skills/showrunner/reference/vet-receipt.md`.
