# Native stacks

The `gh stack` verbs come from the **`github/gh-stack` extension**, a separately installed
public-preview extension rather than part of `gh` itself. Run `gh extension list` to confirm the
extension is installed before you use a stack verb; install it with `gh extension install
github/gh-stack` and upgrade with `gh extension upgrade gh-stack`. A missing verb means the
extension is absent, not that stacks do not exist on GitHub. When the extension is unavailable or
the repository's server-side stacked-pull-request feature is not enabled, **stop and report** — do
not fall back to an unlinked base-branch chain or serial merges.

## What the object is

A stack is a **GitHub-side object**, not a local convention. It has a **number** of its own (distinct
from any pull request number), a **base branch** (`baseRefName`), a **size**, and an **ordered set
of entries**. Each entry carries a **position** (1 at the bottom) and one **pull request**. Stack
numbers and pull request numbers never overlap, so a bare number is unambiguous to the CLI.

A stack holds **two or more pull requests in one repository**. A stack across forks is not a thing.
The **bottom** pull request's base is the stack's base branch (normally `main`). **Every higher**
pull request's base is the **head branch of the layer below it**. A layer's review diff is against
the branch below, which is what makes each layer reviewable on its own.

## What a layer is

A [layer](glossary.md#layer) is one pull request in a stack: one position, one head branch, with its
base set to the branch of the layer below (or the stack base, at the bottom). The lane lifecycle —
how a builder branches, links, and hands one back — lives in the workhorse charter §2.

## How a stack comes to exist

Two routes exist. You must be able to tell which one you are in.

**Remote-only linking** is the route a superheroes lane uses, because each layer is built by its own
session with its own worktree and the pull requests already exist by handback time:

```bash
gh stack link <bottom> <top> [<more>...]
```

Arguments run **bottom to top**. Each argument is a branch name, pull request number, or pull
request URL. The command does not rely on `gh-stack` local tracking state. Branch arguments are
pushed and get pull requests created with the correct base chaining. **Existing pull requests are
reused**; **existing members are never removed**. Passing a **stack number first** appends the
remaining arguments to the top of that stack. An argument that belongs to a **different** stack is
**rejected**. `--base` sets the bottom's base branch. The command is **idempotent in the sense that
matters** — re-linking existing members skips them. Linking **pushes branch arguments** (creating
or updating those remote branches and opening pull requests for branches that have none), and it
**neither rewrites history nor re-points an existing pull request's head**.

**A local tracked stack** uses `gh stack init`, `add`, and `submit`, with `checkout`, `modify`,
`push`, `sync`, `rebase`, and `unstack` around them. The CLI tracks the branch chain locally and
creates or updates the pull requests from it. A superheroes lane does **not** run this way.

## How membership is verified

The **only** honest read of membership is GitHub's own, by GraphQL:

```graphql
query($owner:String!,$repo:String!,$pr:Int!,$after:String){
  repository(owner:$owner,name:$repo){
    pullRequest(number:$pr){
      number baseRefName headRefName headRefOid
      stackEntry{
        position
        stack{
          number size baseRefName
          entries(first:50, after:$after){
            pageInfo{ hasNextPage endCursor }
            nodes{ position pullRequest{ number state isDraft headRefName headRefOid baseRefName } }
          }
        }
      }
    }
  }
}
```

`entries` is a connection and needs its sub-selection. An abbreviated `stack { number size entries }`
does not run. A **null `stackEntry` means the pull request is in no stack**. That is the refusal a
caller must handle, never "probably fine."

**Paginate `entries` to exhaustion** — follow `pageInfo.hasNextPage` with `after` until every page
is collected. The collected node count **must equal `size`**; any missing page or count mismatch
**refuses** before owner enumeration or merge. Each entry carries its position and its pull
request's number, state, draft status, head branch, head sha, and base branch. Together with the
queried pull request's own `position`, `headRefOid`, and the stack's `number`, `size`, and
`baseRefName`, these fields are the whole membership claim, read from GitHub.

**`gh stack view` is not verification.** It reads **local tracking state only**. Run in a worktree
whose branch is simply not locally tracked, it answers that the current branch is not part of a
stack whenever the branch is merely not **locally tracked** — including when that branch is a
perfectly good member of a stack on GitHub. A green or a red `gh stack view` says nothing about the
remote stack. When `gh stack view` disagrees with GraphQL, GraphQL wins.

## How a stack merges

```bash
gh stack merge [<stack-number> | <pr-number>] --yes --squash
```

Use `--merge`, `--rebase`, or `--merge-method` instead of `--squash` when that is what the repository
requires.

Every member **up to and including** the chosen pull request is merged into the base branch in **one
direct, atomic, all-or-nothing operation — if any pull request cannot be merged, none are**. With no
argument the command uses the stack of the current branch. **A bare number is read first as a stack
number, then as a pull request number.** `--yes` is required when nothing is interactive. Only
**basic pull request state** (open, not draft) is checked client-side, while **GitHub evaluates
branch protection and repository rules when the merge runs** and reports failures back. A **merge
queue** on the base branch is honoured: the stack is queued and merges when the queue processes it.
**A queued stack is not atomic** — GitHub may land members across consecutive merge groups, and a
later failure can leave a merged prefix on the trunk while ejecting the failing member and its
descendants ([GitHub's stacked-pull-request troubleshooting
guide](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-stacked-pull-requests)).
**Bypassing merge requirements is not supported for stacks.**

The stack must have a **fully linear history** between layers — a merge requirement GitHub enforces
before any member can land ([GitHub's stacked-pull-request
overview](https://docs.github.com/en/pull-requests/reference/stacked-pull-requests)).

**One command merges the stack; never one PR at a time.**

Merging up to a middle pull request merges everything below it and leaves the pull requests above
**open**. GitHub **automatically rebases** the remaining branches onto the new base, changing their
head shas. That behaviour is GitHub's documented behaviour; we have not smoke-tested it. Every
remaining layer needs a fresh remote-head check and qualifying review and CI receipts on the new
head before it is considered mergeable.

## How a stack stays current

When the stack's base branch or a lower layer has moved, bring the stack current with a **cascading
rebase** — the sanctioned mechanism GitHub documents for restoring the fully linear history a
stack merge requires ([GitHub's stacked-pull-request
overview](https://docs.github.com/en/pull-requests/reference/stacked-pull-requests);
[troubleshooting guide](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-stacked-pull-requests)):

- **Server-side** — trigger the **Rebase stack** action from a pull request in the stack.
- **Locally** — `gh stack rebase` followed by `gh stack push`.

A merge commit from the base into a layer — what `gh pr update-branch` does by default — **breaks
the linear history** the stack merge requires, so **`gh pr update-branch` in its default merge mode
is not how a stack is brought current**.

For a **local tracked** stack, `gh stack sync` and `gh stack rebase` are the native verbs and they
do move local branches. That is why they belong to that route and not to a lane whose layer is under
review.

When a **lower layer changes under it**, bring the lower layer current first, then rebase the layer
above from it, bottom-up. The builder discloses the conflict round. Every layer whose head sha
changes needs fresh remote-head checks and qualifying review and CI receipts on the new head.

## Anti-patterns

**An unlinked base-branch chain** — pull requests based on each other that were never linked. It
looks like a stack in the pull request list and is not one: no stack number, no entries, and no
atomic merge. `gh stack view` will not catch it; the GraphQL read will.

**Serial merges** — merging a stack pull request by pull request. It is not how a native stack
merges; it defeats the all-or-nothing guarantee and can leave the trunk in an intermediate state.

**`gh stack view` as verification** — see above. It reads local tracking state, not GitHub
membership.

**Hand-rewriting a layer's history** — a rebase or force-push a builder improvises on a layer under
review. It breaks review continuity on that pull request and moves a head other layers are based
on. This is not GitHub's **own cascading rebase** (server-side or via `gh stack rebase`/`gh stack
push`), and it is not `gh stack sync` or `rebase` on a **local tracked** stack the builder owns end
to end.

**Reading the stack's copy of a register from inside a layer** — a layer's worktree carries whatever
the layers below it wrote, which can be a stale or amended copy. The copy that grades a child is
**main's**.
