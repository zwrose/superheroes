# review-discipline

The canonical statement of the band's review convention for **any project calibrated
with superheroes**. One copy lives here in the plugin; the SessionStart bootstrap
injects a compact pointer to it in calibrated projects, and `configure` can write a
durable copy into an in-repo project's `CLAUDE.md` (owner-gated; never in out-of-repo
storage mode — that mode exists to keep the repo free of superheroes traces).

## Review lanes

Rigor scales with a change's **weight**, not its size — and the review itself never
disappears. Three lanes name how much ceremony wraps the same non-negotiables; everything
not listed in the table below is the same as the **full** lane.

| | **Full** | **Light** | **Micro** |
|---|---|---|---|
| Who builds | a build session | a build session | the advisor, in-session |
| Starts from | a routed issue | a routed issue | a diagnosis; no issue |
| Brief + pre-code check | yes | no | no |
| Implementation | delegated work orders | typed by the orchestrator | typed by the advisor |
| Review before handback | full panel, fix loop | one independent cross-vendor reviewer | one independent cross-vendor reviewer, in-session |
| Test-pilot | where there is an app | where there is an app | no — *if you think you need it, it isn't micro* |
| Preflight | yes | yes | no |
| Definition-of-done table | yes | yes | no — nothing to disposition against |
| Authorized by | the route | the route | the owner, per change |
| Size | — | ~100–400 lines | ~100 lines or fewer |
| Typical cost | 33–108 min | ~5 min | ~5 min |

**Micro skips preflight** because preflight proves tools before a session goes
*autonomous*, and micro never does — it runs inside a long-lived advisor session with
the owner present.

**The light lane keeps preflight and needs it more than the full lane**: the full lane's
first write to the issue tracker is the brief post, so a blocked permission costs almost
nothing; the light lane has no brief, so its first such write may be creating the PR —
and the failure then surfaces *after all the work is done*.

### What never changes in any lane

- **Its own worktree** — two sessions sharing a tree destroyed uncommitted work twice in
  one day.
- **A real independent review before handback** — the *shape* of review scales; its
  existence does not.
- **Receipts before claims**, **disclosed degradations**, **CI**, **owner-only merges**.

**Single-reviewer lanes (light and micro).** The one reviewer must **cross vendors**:
once the orchestrator (light) or the advisor (micro) types the change, that session is
the *author*, so a same-family reviewer is not independent. For **micro**, the reviewer
must additionally be **non-Anthropic** — the maker-family rule applied to the advisor's
own family, because in micro the advisor *is* the maker. That one reviewer carries a
**mandatory control on every such review**: a planted-defect control probe, or an
investigation-record floor that makes an empty result prove it actually investigated. A
single-seat review inherits undiluted the risk that an external seat silently returns a
well-formed empty pass — deliberately stronger than running such a probe only when a whole
panel comes back empty. This is doctrine in prose only; lane assignment has no mechanical
check.

### The spine

**Default to the full lane; anything unclear resolves upward.**

If this were wrong, what would break, who would notice, and how soon? **Quiet** failure
means **the full lane at any size**.

**Lanes change up, never down without saying so.**

This default does not bend. The thoughts that precede a bad light call — *it's just a
wording fix*, *I know this area* — are exactly the ones this convention exists to
override.

### Provisional guidance

Lane guidance here is **provisional pending accumulated recorded lane calls**. Field
alignment with practice is **in-sample** — fitted to the same changes it validates against
— so it is a fit, not a test.

### Micro — owner authorization

In micro the advisor is the maker, so the advisor's independent vet-from-artifacts does
not exist for that PR; the whole independent check is the one non-Anthropic reviewer
plus the owner's per-change authorization.

**Resolution:** per-change owner authorization means the owner reads the owner-facing
half of the change before authorizing, and the owner is independent of the maker.

**Limitation:** that owner is **not** comparing the change against a build record they
have read.

## The rule — no unreviewed PRs

Every PR gets a real review before it is handed back to the owner, no matter how
small the diff or how it was built (direct build, external engine, fix PR,
fast-follow):

- **Work driven through the review skills reviews itself** — the cross-vendor review
  panels (review-code, and the spec panel) are the review.
- **The full lane** ends a direct build with `/superheroes:review-code` (the full panel
  and fix loop) or an explicit owner-directed review before handback. **The light and
  micro lanes** run **one** independent cross-vendor reviewer instead, carrying the
  mandatory control on every such review (see above). The loop is cheap on small diffs —
  scoped rounds, capped confirmations — so "too small to review" is never a reason to
  skip. The evidence behind this rule: the worst defects in the plugin's own history
  shipped in exactly the handful of PRs that skipped review, not in the large reviewed
  ones.
- **A review that halts with an open blocker** (circuit breaker, park) is resolved
  or explicitly owner-accepted in the PR body — never quietly merged.

## Ship-phase honesty (CONVENTIONS §10.7)

On **full** and **light** lane PRs, a green, branch-current PR can still be silently
incomplete. Two fail-closed gates operate on the PR body — a review seat flags a PR
missing either:

- **Definition of done disposition table** (`superheroes:dod-table`): one row per spec
  DoD bullet, each `done` (with an evidence pointer) or `deferred` (with a filed issue
  `#NNN` and a one-line reason). The **review seat** flags a PR whose table is missing,
  or a row whose evidence or deferral is empty or hollow. **Micro has no DoD table** —
  nothing to disposition against; it starts from a diagnosis, not a spec'd issue.
- **Stubbed seams** (`superheroes:stubbed-seams`, generated): every deliberately-unwired
  seam carries a `# STUB(#NNN): <what is unwired and the live effect>` marker (issue
  mandatory, CI-validated) and surfaces in this generated section. A seam disclosed only
  in a docstring is a finding.

## Why it is stated this strongly

The convention's audience includes autonomous sessions building without a human
watching. A session about to hand back an unreviewed PR is the failure mode; the
thoughts that precede it — "it's a one-line fix", "the loop is overkill here",
"CI is green, that's enough" — are exactly the rationalizations the rule exists to
override. Review coverage is a property of the process, not of any single change's
apparent riskiness.
