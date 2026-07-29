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
the *author*, so a same-family reviewer is not independent. **Three distinct reviewer-loss
events — do not collapse them:**

1. **Cross-vendor reviewer unavailable at kickoff (light only).** The **owner** chooses on
   the spot between a **disclosed** same-family reviewer (a named degradation of
   independence) and taking the **full lane**. Never the builder's or advisor's own call.
2. **The reviewer forfeits mid-run** (the dispatch returns a **terminal forfeit** — its
   structural timeout firing, a nonzero exit, unreadable or unparseable output, or a vacuous
   forfeit — *silence is not forfeit; a terminal forfeit result is*). **Light:** Claude may
   stand in with the **independence loss disclosed** — a disclosed degradation, not an owner
   decision, acceptable because the advisor's vet still runs afterward. **Micro:** no Claude
   stand-in (no advisor vet behind it) — **resolve upward to the full lane or park**.
3. **Micro at kickoff.** The reviewer must be **non-Anthropic** (the advisor *is* the
   maker). No same-family fallback at kickoff and no Claude stand-in mid-run — unavailable
   or forfeited reviewers **resolve upward to the full lane or park** in both cases.

That one reviewer carries a **mandatory planted-defect control probe on every light or
micro review** — the control that makes single-seat review trustworthy. The probe must
come back **engaged**. A probe that returns **not engaged** — for any reason — means **that
review did not happen:** **re-dispatch once**, and if it is still not engaged, **resolve
upward to the full lane or park.** A not-engaged probe is **never** a pass, and exiting
zero is not evidence of engagement. The **investigation-record floor** (an empty external
review seat must prove it actually investigated, or forfeit as vacuous) already applies
automatically to **every external review seat**, single-seat lanes included; it is a
standing safeguard, not something these lanes add. What single-reviewer lanes **add** is
that the planted-defect probe runs on **every** light or micro review, not only when a
vendor's seats all came back empty. This is doctrine in prose only; lane assignment has no
mechanical check.

### The spine

**Default to the full lane; anything unclear resolves upward.**

If this were wrong, what would break, who would notice, and how soon? **Quiet** failure
means **the full lane at any size**. The **one** exception is an explicit **per-change
owner waiver** in **micro** (see Micro — owner authorization below) — owner-only, risk
stated, never a standing grant.

**Lanes change up on their own; moving down a lane is never the builder's or advisor's
call — it requires the owner, per change.** Disclosure alone never authorizes a downgrade.

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

**Quiet-failure waiver (single named exception).** Micro normally must pass the
quiet-failure question like any lane. The owner may **waive that question for one change**
when they state the risk explicitly — **owner-only, per change, never a standing grant**.
The advisor must say what could go wrong before the owner decides.

**Re-review to convergence.** After the advisor resolves reviewer findings, the
**non-Anthropic reviewer re-reviews the final head**, carrying the mandatory control probe
on each re-review, until no blocking findings remain — or the change **parks**.

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

On every lane PR, a green, branch-current PR can still be silently incomplete. Two
fail-closed gates operate on the PR body — a review seat flags a PR missing either:

- **Definition of done disposition table** (`superheroes:dod-table`): one row per spec
  DoD bullet, each `done` (with an evidence pointer) or `deferred` (with a filed issue
  `#NNN` and a one-line reason). The **review seat** flags a PR whose table is missing,
  or a row whose evidence or deferral is empty or hollow. **Micro has no DoD table** —
  nothing to disposition against; it starts from a diagnosis, not a spec'd issue; this
  gate does not apply to micro.
- **Stubbed seams** (`superheroes:stubbed-seams`, generated): every deliberately-unwired
  seam carries a `# STUB(#NNN): <what is unwired and the live effect>` marker (issue
  mandatory, CI-validated) and surfaces in this generated section. A seam disclosed only
  in a docstring is a finding. **Every lane** — including micro; a deliberate unwired seam
  in a micro change is itself a reason to escalate.

## Why it is stated this strongly

The convention's audience includes autonomous sessions building without a human
watching. A session about to hand back an unreviewed PR is the failure mode; the
thoughts that precede it — "it's a one-line fix", "the loop is overkill here",
"CI is green, that's enough" — are exactly the rationalizations the rule exists to
override. Review coverage is a property of the process, not of any single change's
apparent riskiness.
