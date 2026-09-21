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
   `rubric/native-stacks.md` § *How membership is verified*. `gh stack view` reads local tracking
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
   at click-list time: the point of it is the window between them.

4. **One command merges the stack, in order** — `gh stack merge <stack-or-pr> --yes --squash`; every
   member up to and including the chosen pull request. A **direct** merge is atomic (all or nothing);
   a **merge-queue** merge is ordered and best-effort and can leave a merged prefix on the trunk.
   **Never pull request by pull request**: serial merges are the anti-pattern
   (`rubric/native-stacks.md` § *Anti-patterns*), and they leave the trunk holding intermediate
   layers if one member fails. Merge semantics, the bare-number ambiguity, per-pull-request
   branch-protection evaluation, the history condition each layer must satisfy, and merge-queue
   behaviour live in `rubric/native-stacks.md` § *How a stack merges*.

5. **A stack is brought current by merge, bottom-up** — `gh pr update-branch` on each affected
   layer starting just above the change, which keeps every layer's own commits; each moved head then
   takes a fresh remote-head check, CI on the new sha, and a receipt naming that sha
   (`rubric/native-stacks.md` § *How a stack stays current*). GitHub's cascading rebase (the
   server-side **Rebase stack** action for a lane; `gh stack rebase` + `gh stack push` only for a
   local tracked stack an operator owns end to end) is the disclosed alternative when a merge
   cannot resolve the conflict; it rewrites every commit of every affected layer, so those layers'
   review and CI receipts are re-taken in full. Never a hand-rebase or force-push of a layer under
   review, which the doctrine names as an anti-pattern (`rubric/native-stacks.md` § *Anti-patterns*).

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
