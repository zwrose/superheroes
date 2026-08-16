# Contents

- [The merge train](#the-merge-train)
- [A merge train's "green" includes post-merge `main` CI](#a-merge-trains-green-includes-post-merge-main-ci)
- [Union fixes ride the last *open* PR, disclosed](#union-fixes-ride-the-last-open-pr-disclosed)
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

Typing it is advisor **build** work, so it stays inside duty 6's boundary: the owner authorizes **that
edit**, it stays the size of an integration fix — anything larger routes to a builder like any other
change — and it carries micro's review floor on the final head (one cross-vendor reviewer plus an
**engaged** control probe). What it does **not** do is reclassify the PR: the containing lane keeps
its own route, its DoD, and its advisor vet.

**Field case:** a test green on the identical tree pre-merge went **deterministically** red post-merge
in CI only (coverage-instrumented runners lose an assertion race); a disclosed integration commit on
the last open PR's branch is what closed it.

## Selecting the run to watch

Both rules above turn on watching the right run, so select it by **workflow name plus head sha** —
never `gh run list --limit 1`, which returns whichever workflow ran latest on that branch and has
already produced a false green. The canonical statement is field 1 of the vet receipt's spine, in
`skills/showrunner/reference/vet-receipt.md`.
