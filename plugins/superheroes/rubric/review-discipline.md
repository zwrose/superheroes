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

**Salvage valve (`forfeit-with-engaged-artifact`).** A `forfeit-with-engaged-artifact` is a
**forfeit** — the three-case rule above runs exactly as written; this outcome does not add a fourth
case and does not license a stand-in that the existing rules do not already license. **Findings only,
never the seat** — the seat is not credited toward panel composition; each claim taken from the
salvaged artifact is **independently verified** by the session that accepts it, and the degradation
is disclosed in the PR body, because a timeout can truncate stdout so you can verify what an artifact
contains but never what it never reached. **Salvage usage trending to zero is the success metric** — a
high salvage rate **indicts our caps and our transport; it does not vindicate salvage.**

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
on each re-review, until no blocking findings remain — or the change **parks**. When the
contract under review is **prose**, the bounded acceptance bar in
`### Bounded acceptance — prose-contract DoDs` below is the scoped exception to this paragraph.

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

**And one independent read *after* handback: the advisor's vet.** Review-before-handback checks the
**code**; the vet checks the **PR** — the last independent read before the owner's one irreversible
act. It is not a mood: it has a **shape** — an always-present spine, plus fields the PR's own artifacts
trigger, with every spine field **filled or written `None`**, because an absence nobody wrote down
cannot be told apart from something forgotten
(`skills/showrunner/reference/vet-receipt.md`). The **micro** lane has no vet at all — see the lane
table above and *Micro — owner authorization*.

## Review bars and recorded residuals

When a review seat runs, **ratified residuals** are part of its bar — quoted data in the emitted
order, not an instruction the orchestrator hand-inlines at dispatch time.

**Where a project records them.** Optional `## Ratified residuals` prose in the project's
`core.md` (`.claude/superheroes/core.md` in-repo), owner-editable through `configure`.

**How seats receive them.** On each `next` for a `dispatch-*` phase, `round_orders.resolve_order_residuals`
reads that section from `core.md` at the review's **pinned base commit** when the project is
in-repo (`resolve_base_residuals` / `git cat-file` on `meta.baseRef` — never the worktree or
branch under review); out-of-repo sessions read the calibration store instead.
`round_orders.render_order` appends the residual block to every review seat's order. An empty or missing section renders an explicit
**"No ratified residuals are recorded for this project at the review base."** line — a missing list
and an empty one are different facts, so the block is never omitted.

**What they mean for findings.** A finding that reduces wholly to a recorded residual is a
**non-blocking restatement** — recorded, not blocking. A residual the owner has already accepted is
a **decision**; a review round cannot un-decide it by finding it again.

Three things this does **not** license. A finding is **still blocking** when it shows the change
**worsens** the residual, **widens its blast radius**, or reaches a surface the residual's stated
**bound never covered** — the bound is the whole content of the acceptance, so anything outside it was
never accepted. And the residual must be **recorded** — an owner-ratified entry in the project's own
residual list, which a reviewer can be pointed at and a reader can check. An unwritten *"we know about
that"* is not a residual; it is a hidden defect, which is exactly why residuals get written down.

**Read the residual from the base, never from the branch under review.** A residual list is ordinary
versioned content, so a change that adds or widens its own residual row could otherwise lower the bar
it is about to be judged against — a branch marking its own homework. Only a residual already recorded
on the **base the review is diffed against** may move a bar; a row this change introduces or broadens
is **part of the change**, reviewed like anything else, and the owner ratifies it at merge rather than
the reviewer honouring it in advance. The order renderer quotes the base-resolved text between
`-----` fences so the seat sees data, not direction.

The cost of skipping this is measured, not theoretical: one change's four review rounds produced
roughly **47 Critical findings**, a majority of them restatements of a single already-ratified
residual. That is not a review finding defects — it is a **bar mis-set**, and it burns the rounds the
real findings need.

### Bounded acceptance — prose-contract DoDs

When the contract under review is **prose** — a definition-of-done written as *"no new uncovered
state"* — the general re-review bar in `**Re-review to convergence.**` above is unterminating,
and this section is the **scoped exception** to that paragraph. Five review rounds on one PR
produced different, narrower findings every round and never zero — the bar kept moving because
the contract had no fixed stopping point. The ratified bounded form is: no new Critical or Important finding in a review round on the final head, after a stated number of rounds, with Minor residuals disclosed. The **advisor at vet** (or the **owner**, when they set the bound before review
begins) states that number of rounds, and it is recorded in the **PR body** or the **vet receipt**.
That is the written rule rather than a per-build improvisation; it is the bar already applied in
practice; an unterminating bar can only be abandoned — which is what *accept the residual at merge*
keeps meaning: you name what you are shipping with, not pretend the bar was met when it was not.

### The third-rework tripwire

After two reworks of the same surface in one build, **a third rework of the same surface is the tripwire**: that third rework is not dispatched, so the fourth patch on that surface never happens.
What the tripwire demands is that the design signal is named, not that the build goes idle. On a
lane the builder can affirmatively call converged, **stopping and handing the design signal up satisfies it** — refuse the fourth patch, name what the seam problem looks like in the handback, and
ship the remaining minors as disclosed follow-ups; the handback must **state that the third-rework
tripwire fired** and name the seam problem, so the advisor is grading a declared event rather than
inferring it from provenance. Where the builder cannot say with confidence that the lane has
converged, the park branch binds — the permissive branch is available only on a lane the builder can
affirmatively call converged. Where the build cannot truthfully hand back, **a formal park binds when the lane has not converged** — stop with receipts; lifting the park is owner- or advisor-ruled
rather than the builder's own call. Two field specimens deviated from the letter while honouring
the substance, which is what prompted the ruling.

## Prose-driven review (`--post`, `--review-only`)

A **prose-driven review** is a sanctioned lane on the read-only paths — not a shortcut, not a
degradation, and **not** something the auto-fix loop may do. The orchestrator compiles findings in
main context (`SKILL.md` § Compile + Dedupe) instead of obeying the driver's fold, but it still owes
a **named substitute receipt** standing in for `round-receipt.json` and the driver journal:

1. **Dispositions table** — how each finding was handled (the workhorse charter's table in the PR
   body on PR paths).
2. **Durable linked receipt** — review results posted on the PR as a comment or similar, not
   something that only lives in session context (`skills/workhorse/SKILL.md` §10).

**Branch mode has no PR.** The durable home is `$SESSION_DIR/dispositions.md` — write the
dispositions table and receipt link there; when the branch later becomes a PR, that file's content
is what the PR body carries. (The workhorse charter names the same substitute-receipt shape for
light-lane handback.)

The auto-fix loop's "never plan continuation by eye" rule
(`skills/review-code/reference/round-driver.md` § The one
entrypoint) applies only inside `next`/`submit`; it does not forbid this lane.

## Presentation standard (show it / say it / nothing to see)

Three **presentation calls** name how much the owner must *see* before merge — not how much ceremony
the build carried:

| old name | call | means |
|---|---|---|
| tier 1 | **show it** | the owner looks at the after-state before merging |
| tier 2 | **say it** | the PR states it plainly; no spot-check |
| tier 3 | **nothing to see** | nothing perceivable changed |

The **advisor** makes the call **when the issue is routed**, not at handback. For **show it**, the
issue's Definition of Done carries the presentation obligation as a bullet like any other requirement —
a duty that first appears at handback is a duty nobody was resourced to discharge. The routing-time call
is **revisable during the build**: a builder who discovers a perceivable surface mid-build **upgrades
it with a disclosure line** — never a park, and never a silent skip.

**The show-it duty is wayfinding, not media** — **no screenshots and no recordings**. The duty is to
remove the friction of putting hands on the build.

**(a) An entry point, ranked** — take the **highest level the project supports**; **disclose whenever
it is `command` or below.** An absent project declaration means **`none`**.

| Level | What the owner does | Meets zero reconstruction? |
|---|---|---|
| `link` | clicks a link — a per-change environment that already exists | **fully; works from any device** |
| `running` | opens something already up on their own machine | **yes, while it is up, and it is not after the session ends** |
| `command` | runs one command in a workspace already prepared for them | **no; a named, disclosed degradation. Cheap, but it is reconstruction** |
| `attended` | owner present; the build waits | — |
| `none` | disclosed as unpresentable | — |

`command` is **explicitly allowed** — often the honest best a project can do — but never silently
equivalent to `link`. For some projects `link` already exists (per-change environments are default-on
in plenty of stacks); for others it **may be a build**, carrying one-time provisioning and recurring
operational work. **Find out which before recommending it** — a rule that assumes infrastructure gets
ignored. **`link` and `running` do different jobs**: a per-change environment is a *review* surface, a
local server is an *iteration* surface, and a project that reaches `link` does not stop wanting
`running`.

**(b) Drive-to-state instructions** — the shortest exact path from the entry point to the thing being
judged, **including transient states** (e.g. *open the entry point, go to the settings page, start a
save; the control disappears while it is in flight*). The build already knows this path when a pilot has
driven the surface; today it is never written down for the owner.

**(c) When the honest answer is `none`, disclose it** — naming what could not be presented and why,
reaching the owner **before the merge click**.

**Portability — the band states the standard, the project declares the mechanism.** Shipping text names
**no technology** — no port scheme, hosting provider, auth library, or package script. The per-project
answer is the **Show-it surface** declaration: prose in the project's `core.md` under a `## Show-it
surface` heading, carrying **Level**, **What the owner does**, and optional **Notes**. It declares a
**shape**, never an instance; the PR's *How to see it* carries the concrete instance. Two heroes read it
(the builder authoring a PR, the advisor routing and vetting) — one home per fact. **Absent means
`none`** — a project with no declaration cannot have a level claimed on its behalf, so the builder
discloses that none is declared.

**The tripwire is omission, not length.** There is **no size cap** on the owner half; the failure mode
is that the owner half **omits something the owner is being asked to accept**.

## Ship-phase honesty (CONVENTIONS §10.7)

On every lane PR, a green, branch-current PR can still be silently incomplete. Three
fail-closed gates operate on the PR body — a review seat flags a PR missing any:

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
- **Omission floor** (owner half, `## What we're accepting`): three rows that must appear,
  keyed on **severity, not disposition status** — an earlier draft keyed on "parked" and
  missed a genuine Important-severity race dispositioned "Deferred — follow-up"; severity is
  already carried by every dispositions table, and it keeps craft nits below the bar for free:
  (1) every **deferred** DoD row; (2) every **blocking or important** review finding that was
  **not fixed**, whatever its disposition is called; (3) every **disclosed degradation**. A
  **missing** `<!-- superheroes:build-record -->` boundary marker or a **missing**
  `<!-- superheroes:degradations -->` section is **itself** a finding — same **Important** /
  `tradeoff` / author-resolved shape as the DoD-table check, not a silent pass; an empty
  degradation list is only clean when the section says the literal **None** (absence and **None**
  differ). The markers `<!-- superheroes:build-record -->` and `<!-- superheroes:degradations -->`
  join the family this section already names (`superheroes:dod-table`, `superheroes:stubbed-seams`).
  The **review seat** flags a PR whose owner half omits a floor row — same seat, same finding shape
  as the DoD-table check, no new machinery. **Micro** has no DoD table (that gate already excludes
  micro), but the **degradation** and **unfixed-finding** rows apply on **every** lane.

## Why it is stated this strongly

The convention's audience includes autonomous sessions building without a human
watching. A session about to hand back an unreviewed PR is the failure mode; the
thoughts that precede it — "it's a one-line fix", "the loop is overkill here",
"CI is green, that's enough" — are exactly the rationalizations the rule exists to
override. Review coverage is a property of the process, not of any single change's
apparent riskiness.
