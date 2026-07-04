# review-discipline

The canonical statement of the band's review convention for **any project calibrated
with superheroes**. One copy lives here in the plugin; the SessionStart bootstrap
injects a compact pointer to it in calibrated projects, and `configure` can write a
durable copy into an in-repo project's `CLAUDE.md` (owner-gated; never in out-of-repo
storage mode — that mode exists to keep the repo free of superheroes traces).

## The rule — no unreviewed PRs

Every PR gets a real review before it is handed back to the owner, no matter how
small the diff or how it was built (direct build, external engine, fix PR,
fast-follow):

- **Work driven through the pipeline reviews itself** — the spine's review panels
  (review-code, and the plan/tasks/spec legs where they run) are the review.
- **A direct build ends with `/superheroes:review-code`** (or an explicit
  owner-directed review) before the PR is handed back. The loop is cheap on small
  diffs — scoped rounds, capped confirmations — so "too small to review" is never a
  reason to skip. The evidence behind this rule: the worst defects in the plugin's
  own history shipped in exactly the handful of PRs that skipped review, not in the
  large reviewed ones.
- **A review that halts with an open blocker** (circuit breaker, park) is resolved
  or explicitly owner-accepted in the PR body — never quietly merged.

## Why it is stated this strongly

The convention's audience includes autonomous sessions building without a human
watching. A session about to hand back an unreviewed PR is the failure mode; the
thoughts that precede it — "it's a one-line fix", "the loop is overkill here",
"CI is green, that's enough" — are exactly the rationalizations the rule exists to
override. Review coverage is a property of the process, not of any single change's
apparent riskiness.
