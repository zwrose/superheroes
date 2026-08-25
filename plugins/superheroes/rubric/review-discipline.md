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
| Size (non-test lines — see below) | — | ~100–400 | ~100 or fewer |
| Typical cost | 33–108 min | ~5 min | ~5 min |

**Size counts non-test lines.** Every size figure in this document and in the charters — the
lane row above, the light lane's measured escalation line, the micro ceiling, and the
"twice the brief's estimate" scope tripwire — is read over **non-test changed lines**:
additions plus deletions in every file *outside* a `tests/` directory (docs, skill and
rubric prose, and code all count; test modules and their fixtures do not). Test volume
scales with rigour here — bite-proofs, truth tables, censuses, drift tests — and a size
line that counted it would push a builder toward fewer tests to stay in-lane, which is
the wrong pressure. Test volume that signals a *design* problem is the third-rework
tripwire's and the vet's to catch, not the lane line's. Estimates carry both numbers
(behaviour + test lines) so the tripwire and the estimate share a basis (owner-ruled
2026-08-16).

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
  and fix loop) before handback. An **explicit owner-directed review** remains a valid
  ending, and it is **recorded as a cited skip of the driver loop with the owner's
  direction as the citation** (owner-ruled 2026-08-23: subordinate, don't remove) — the
  skip accounting stays whole and the owner's hands stay free. The skip rule below names
  this citation class; the flip clause below names its post-flip fate. **The light and
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

**Post-handback merges carry a review expectation only when they author content** (owner-ruled
2026-08-21). A **content-neutral freshening** of the branch — an update-from-main that resolves no
conflicts and authors nothing — carries **no** review expectation; re-panelling it is a race the
branch cannot win. A post-handback commit that **authors content** — a conflict resolution, an
advisor integration fold — keeps the union-fix **micro floor** in
`skills/showrunner/reference/merge-train.md`: one cross-vendor reviewer plus an **engaged** control
probe on the final head.

## The driver mandate — the certified loop, its skips, and the flip

The **full lane's** review is the **certified loop** — the round driver's one entrypoint, which
records what it seated, what each seat returned, and whether the round converged. A hand-driven
panel can read identically in a PR body and carry none of that record. Three field specimens
substituted "panel + hand-driven fix round" on exactly the builds that would have exercised the
loop hardest, each on a stated excuse that does not survive contact with the skill text: no owner
gate exists in the default loop, and the verify step's foreground cap is friction, not a wall. This
section closes the excuses by making a skip **citable** rather than merely disclosable.

**A skip is disclosed, and the disclosure cites a blocker by number.** A full-lane build that does
not run the certified loop **discloses the skip in the PR body, citing a filed `driver-blocker`
issue by number** — or, for the subordinated owner-directed ending above, **citing the owner's
direction as a dated record per the venue-citation convention**
(`skills/showrunner/reference/issue-contract.md` § Anchor resolution — a venue name is never a
record; the citation is an exact permalink to a dated record) — the second and only other
citation class. **A skip citing nothing, and a skip citing a closed issue, are each a vet
finding.** This binds now, on every full-lane PR — it does not wait for the flip below.

**The `driver-blocker` label is the standing view of what still blocks the loop.** Any bug that
prevents proper use of the driver carries the project's `driver-blocker` label, and the label query
— not anyone's memory — is what says whether the blockers are cleared. That is what makes the skip
rule self-feeding: every honest skip either points at a tracked blocker or is a finding, so the
list of things standing between this project and a certified loop maintains itself.

**Seat-provenance parity — a hand-driven panel owes what the build must record.** The driver path
records which vendor **ran** each seat against the vendor that seat's seat map assigns — a mismatch
is disclosed, but neither the driver receipt nor the panel submission contract carries proof that
the assigned vendor was actually attempted. A hand-driven panel owes the **build record**: each seat's
seat-map assignment, plus a recorded attempt or **terminal forfeit** on that assigned vendor. A mixed
panel — different seats on different vendors by design — is normal and is not itself a finding.
**A seat that ran on a vendor other than its seat-map assignment with no recorded forfeit on the
assigned vendor is a vet finding** — the record is the only thing separating an engine that was
tried and failed from one that was never asked, and a panel that records neither is exactly the
silent degradation this lane exists to prevent.

**The flip — a dated conditional that arms itself.** Ruled **2026-08-21**. **When the milestone
*Review panels can't silently degrade* closes, a full-lane review that is not the certified loop
stops being a disclosable degradation and becomes a vet finding**, and the only valve is
**driver-or-park** — never driver-or-improvise. Until that close, the skip rule above governs:
disclose, cite an open `driver-blocker`, and the vet weighs it. After it, a citation is no longer a
pass — the build runs the loop or parks, and the blocker it would have cited is the reason the park
is honest. The **subordinated owner-directed ending survives the flip** — "don't remove" carries no
sunset — but post-flip it is graded as the owner's **recorded override** of driver-or-park (same
dated-direction citation, named as an override in the vet receipt), never as a citation-pass. The arming event is the **milestone's close** — the owner's judgment that its exit
condition is met, read off the receipts, as ROADMAP.md's standing rule already defines closure; the
release cut carrying that milestone's work is how the close is **stamped**, not a second and
separate trigger. It is written as a dated conditional precisely so that nobody has to remember to
arm it: a reader at the close needs no context beyond this paragraph. **The milestone named here
and ROADMAP.md's closure rule are this band's arming record in the superheroes project itself** —
a consuming project inherits the portable **driver-or-park** valve from the sentences above, not an
obligation to evaluate this repository's milestone state. For a consuming project the skip rule
above binds now and continuously; the dated flip conditional is this band's own arming record,
not a second regime they must evaluate.

**No mechanical enforcement gate ships for any of this:** the skip rule, the parity rule, and the
flip are vet doctrine, and **the advisor at vet is the enforcement**. A guard that parsed PR bodies
to grade a skip is out of class under *Mechanical guards over prose*, below.

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

### Continuation and the advisor-resolution valve

This is **venue 1** of the residual venue ladder; the ladder's canonical home is
`skills/showrunner/reference/owner-decisions.md` — not restated here. Continuation applies when the
residual is off any tripwired seam, its fix shape is settled, and it fits the floor economics of who
types it; ambiguity resolves toward continuing. The third-rework tripwire's builder stop is untouched
and unconditional: the design question it hands up gets the advisor-resolution valve — craft, and the
advisor rules it, records the determination for veto, and the residual becomes settled-shape; product,
and it routes up as consequences; doubt resolves upward. The craft-versus-product test in that valve is
**the same test** as the tier principle in the canonical home, not a second one; and the
advisor-rules-then-vets shape is **disclosed doctrine**, checked by three things — the dated record
of the determination, the cross-vendor review floor, and the owner's click. **Nothing here weakens the
builder's stop**: the builder still refuses the fourth patch and still hands the design signal up, and
the valve governs only what the **advisor** does with that signal once it arrives.

### Standing authorization — venue-1 folds

Post-review folds on an open PR need no per-fold owner word when they are micro-sized at roughly 100
non-test lines or fewer, run under the full micro floor of a cross-vendor seat, the planted-defect
control probe, and the salvage valve, and are disclosed in the PR body and the owner half; the owner's
click remains the gate. The four bounds, checkable one at a time: **micro-sized** at roughly 100
non-test lines or fewer; the **full micro floor** — a cross-vendor seat, the planted-defect control
probe, the salvage valve; **disclosure** in the PR body **and** the owner half; and the **owner's click**
remaining the gate. A residual larger than that bound routes to one bounded builder re-dispatch under
the lane's existing route, and the standalone micro lane's per-change owner word is explicitly unchanged.
The preservation is checkable in place at `### Micro — owner authorization` above.

Within the micro-sized bound above, who types the fold splits by surface (owner ruling 2026-08-24,
recorded on the collector —
[issue #695 comment](https://github.com/zwrose/superheroes/issues/695#issuecomment-5390859217)):
a fold touching **only docs or tests** the advisor types in-session under the full micro floor
above; a fold that touches **non-test code**, or mixes the two sides, routes to one bounded builder
re-dispatch — the same shape as the over-size route — so quiet-failure surfaces keep a maker
independent of the vet. Doubt about which side a surface falls on resolves toward the builder, and
the over-size route is unchanged: a fold past the bound goes to the builder whatever its surface.

### Mechanical guards over prose — the byte-literal floor

Mechanical guards over prose are scoped to the **byte-literal floor** — four kept classes and nothing
beyond them. **Cross-doc literal-agreement pins**, **hard-line sentence pins**, **register-quote
checks**, and **cardinality floors** over those censuses stay in class; they enforce what a
byte-for-byte read can enforce without interpreting meaning. A **literal census** — the presence or
absence of a set of pinned literals — is what a cardinality floor floors; that is the census
"those censuses" names. An **extractor whose only job is bounding one of those pins to its home
block is part of the pin, not a separate class** — it stays, and it is disclosed as such. The same
holds on the **source side**: a derivation whose only output is the literal set a cross-doc pin
agrees on is the pin's **source half**, in class (owner-ruled 2026-08-23). What is
out of class is an extractor that parses document structure or judges what prose means. **Structural
parsers**, **table checks**, and **message/meaning guards** are **out of class** — permanently.
Prose *meaning* and *structure* are review's job, not CI's.

**Prose-executed paths are pinned structurally, not driven end-to-end by an executable harness.**
A skill's prose path is executed by a model reading the prose — there is no process to drive.
What *can* be pinned — within the byte-literal floor above — is the prose file itself through
**the four kept classes** (cross-doc literal-agreement pins, hard-line sentence pins,
register-quote checks, and cardinality floors over those censuses, plus the in-class extractor
that bounds a pin to its home block). "Pinned structurally" means exactly that application to a
shipped prose file — not structural parsers, table checks, or message/meaning guards, which
stay out of class, permanently, per the owner ruling 2026-08-17 recorded on issue #695. This
does **not** reopen those out-of-class guards. This is **not**
bite-proof vacuity mode 4 (*"delivered through a path the guarded input can never take"*) — for a
structural pin the path is real and complete: mutate the shipped prose file, the detector reads
that file, the detector goes red. A structural pin must still satisfy bite-proof **mode 3**: a
detector guarding N elements owes N separate neutralizations and N reds, not one representative
(`rubric/bite-proof.md`).

That line is where the ruling lands: out-of-class guards burned review rounds the real findings needed
(owner ruling 2026-08-17, recorded on issue #695 — [comment
5322427680](https://github.com/zwrose/superheroes/issues/695#issuecomment-5322427680)).

**The bar cap** is a bar being set, so you know the disposition is legitimate when you use it. A
review finding that demands a guard outside the kept classes, or an adversarial-evasion finding
against a guard that is inside them, is **declined as out-of-class by citing this ruling — never
patched.** A declined finding is still recorded in the dispositions table with the citation —
declining is a disposition, never a silent drop. The cap bars **building the out-of-class guard the
finding demands**; it does not bar ordinary maintenance of a guard that is already in class —
repairing a pin whose literal or count has drifted is exactly the upkeep the kept classes exist
for. You are not dodging a finding when you cite the ruling; you are applying a recorded bar.

**Named-failure-first:** no new prose guard ships without a **field failure it would have caught**,
named in its issue. A guard with no named failure is speculation dressed as automation.

### The safety-machinery route — the guard refuses the fixer

Some of this plugin's own files are **safety machinery**. Two files own that fact between them, and
this section quotes them rather than explaining them: `lib/escalation.py` owns the set, its
inclusion criterion — *"any module whose edit could disable a floor / gate / halt / escalation
guarantee"* — and the membership test; `skills/review-code/reference/auto-fix-loop.md` owns the
refusal the auto-fix loop's fixer hits on one of them — *"If `allow` is false, the fixer MUST NOT
edit that file"*. **Read those two for the mechanism; it is deliberately not restated here, so this
section cannot drift from the guard it describes.** What this section owns is only **what happens to
the findings afterwards** — the part that lived in session memory and issue history until it was
written down here, so that each new session re-derived it at the cost of a panel plus a fixer round.

**What the refusal means, and what it does not.** The guard bars the **automated fixer**, not the
change. Safety machinery is edited all the time — under a ratified issue, by a builder or an
implementer under a work order, reviewed like anything else. What may never happen is the review
loop reaching into a guard **on its own authority** mid-round. So when a panel finds real defects in
safety machinery, the fixer is forbidden to act on them, and `review-code`'s auto-fix loop **cannot
converge on that surface — ever**. A loop that stalls there has hit its bound, not a bug: that is the
guard working as designed, and it is not evidence of engine fragility, a bad order, or a transport
defect. Retrying the fixer, re-dispatching at a higher rung, or reading the stall as an escalation
trigger are all wrong reads of the same event.

**Narrowing the guard to converge a loop is never the route.** `escalation-base.md` carries the
invariant above its own floor — *"the agent may never grant itself authority or bypass a gate.
Skipping or auto-resolving its own GATE is self-granting and is forbidden"* — and it applies with
full force to a session that would relax the very control keeping autonomous agents out of the
guards, including the guard that would catch the relaxation.

**The sanctioned path is ordered implementer work orders.** The findings leave the loop and come back
as builder-dispatched work, in this shape:

- **One order per finding cluster** — clustered by the surface and the contract the findings share,
  not one order per finding. The first execution below sent six findings as **one** ordered round
  against two files holding two sides of one contract.
- **The order carries the finding text**, so the implementer fixes a stated defect rather than
  re-deriving it from the file.
- **The orchestrator verifies independently**, re-running every receipt itself, exactly as it does
  for any implementer work order — and re-review below, the full local gates, and CI all still
  apply unchanged. Nothing about the refusal lowers that bar or shifts any part of it onto the
  loop; how the loop's own stages behave around an escalated finding is the driver's business
  (`skills/review-code/reference/round-driver.md`), not this route's.
- **Re-review is unchanged** — the fixed surface goes back through the review loop like any other
  fix, and the loop's convergence bar and the third-rework tripwire both still bind.

**Blocking findings go out on advisor or builder authority.** For a Critical or Important finding on
safety machinery, the ordered implementer round goes out **on the advisor's or the builder's own
authority**; **the owner's mandatory touchpoint is the merge click**, not a per-change
pre-authorization. What that authority costs is **loud disclosure**: **the work order says the round
touches safety machinery and names the files**, and the PR body says the same where the owner reads
it. **Non-blocking** findings on the same surface are **disclosed residuals** — recorded in the
dispositions table, and never auto-fixed either, **because the guard refuses the fixer at every
severity**. A non-blocking finding is never the reason a build reaches into safety machinery it was
not sent to touch.

**The one exception — the owner-authority-gate family.** Three files carry the mechanical
never-merge floor, and a round touching any of them **still needs the owner's word first, per
change**, scoped to the findings' own surfaces and nothing wider — never a standing licence:

- `hooks/owner_authority_gate.py` (the PreToolUse gate hook)
- `lib/owner_authority.py` (its classifier core)
- `reference/owner-authority-allowlist.md` (its allowlist reference)

This family is the mechanical never-merge floor, so a round that could edit it on its own authority
could edit away the control that keeps the merge click the owner's.

**Classification fails closed.** Before the round, put each finding's surface in exactly one of three
classes — ordinary, safety machinery, owner-authority-gate family. **A surface you cannot confidently
classify is treated as gate family** — a path that does not resolve, a renamed file, a dependency you
have not checked — **which means it parks**. That fail direction is deliberate: when classification is
uncertain, the route waits rather than granting authority by mistake.

**When the owner's word is unavailable at the gate family, park.** A headless or owner-absent build
that reaches blocking findings in the owner-authority-gate family **parks with receipts** — what the
panel found, that the guard refused the fixer, and that the remaining findings need the owner's word.
It does not narrow the guard, does not type the fix to get moving, and does not hand back claiming
convergence it did not reach. A builder cannot lift its own park; resumption is the owner's or the
advisor's call. **Outside the gate family there is nothing to wait for**: the ordered round goes out
with its disclosure.

**This is not the runtime self-modification floor.** `escalation-base.md`'s hard floor — *"modifies
the safety machinery itself at runtime"* — is about **a run altering its own control system
mid-flight**, and this route leaves it untouched. An ordered implementer edit in a build worktree,
under a ratified issue or an ordered round, is not that; the two floors **do not overlap**.

**Evidence — the route was executed twice before it was written down.** On #1109, **round 2**'s
five-seat panel left six Important findings in `engine_adapter.py` / `engine_dispatch.py`, verified
the guard's refusal directly, and **parked** rather than improvising ([park
comment](https://github.com/zwrose/superheroes/issues/1109#issuecomment-5390550698)); the owner then
authorized ordered implementer work orders — *"the guard's sanctioned path; the auto-fix loop remains
forbidden on this surface"* — scoped to exactly those six findings' surfaces ([item-78
authorization](https://github.com/zwrose/superheroes/issues/1109#issuecomment-5390711707)). **Round
4** executed that route again under the **same scoped authorization, carried forward unchanged**
across an intervening session death — a scoped authorization survives across rounds on the findings'
own surfaces, which is precisely what keeps it different from a licence to edit safety machinery at
large — and converged; its build record
on [PR #1120](https://github.com/zwrose/superheroes/pull/1120) is what asked for the route to be
written down (*Follow-ups for the advisor*, item 9). Two executions, both successful, neither
reconstructable from the plugin surfaces at the time. The owner pre-authorization this paragraph
records was the rule **at the time** and is **retired for everything outside the
owner-authority-gate family** by the 2026-08-25 ruling — historical evidence, not current procedure.

## Prose-driven review (`--review-only`)

A **prose-driven review** is a sanctioned lane on the read-only path — not a shortcut, not a
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
