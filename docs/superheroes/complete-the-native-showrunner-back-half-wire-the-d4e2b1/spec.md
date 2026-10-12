---
superheroes: doc
schemaVersion: 1
docType: spec
workItem: complete-the-native-showrunner-back-half-wire-the-d4e2b1
issue: 120
size: large
status: approved
gates: {review: passed}
producedBy: "the-architect@0.3.0"
created: "2026-06-29"
updated: "2026-06-29"
---
# Complete the native showrunner back-half — wire the deferred remediation (CI-fix loop, freshen, fence)

## Purpose

The native showrunner's back-half (the steps that take a built branch to a ready-for-review
pull request) shipped as a happy-path slice. When it meets the first obstacle it **parks** instead
of fixing it: a branch that has fallen behind its base, or a single failing check, stops the run
even though the behavior to recover already exists in the manual producer. Its pull-request-changing
steps also run **unguarded** — and the recovery this work adds introduces *new* autonomous pushes
(catching up to base, fixing checks), so a second run started on the same work-item could create a
duplicate pull request or undo the first run's work. The concurrency guard therefore ships together with
the recovery wiring: those new pushes are exactly the branch-mutating boundaries that must be guarded. This work wires the already-specified recovery behavior into
the native back-half so an autonomous run reaches a clean hand-back — or a safe, clearly-explained
hand-back to the owner — on its own, and so two runs on the same work-item can never corrupt each
other. It changes no decision logic; it connects behavior the manual producer already defines.

## Who it's for

- **The showrunner run itself** — the autonomous pipeline that drives an approved work-item all the
  way to a ready-for-review pull request without a person babysitting each step.
- **The repo owner** — the person who receives the hand-back and decides the merge. Today they get a
  premature "parked" the moment anything is imperfect; they should instead get a remediated pull
  request with a clear "your turn" summary, or an honest explanation of exactly what blocked it.

## Functional requirements

**FR-1.** When a ready pull request's branch is behind its base, the showrunner shall bring the base
into the branch before it judges the checks, so the checks run on the code the owner will actually merge.
  - *Acceptance (Given-When-Then):* Given a ready pull request whose branch is behind its base with no
    conflicting changes, when the back-half reaches the ship step, then the base is brought into the branch,
    the pull request's head is updated to include the base, and the checks are judged on that integrated
    head — not on the pre-integration branch.

**FR-2.** When the base keeps advancing past a set number of catch-up attempts, the showrunner shall
stop chasing it and hand back with an explicit note that the branch is behind its base, instead of
catching up forever.
  - *Acceptance (Given-When-Then):* Given the base advances again on every catch-up attempt, when the
    attempts reach their limit, then the showrunner stops catching up and the hand-back states the branch
    is behind the base and should be updated before merge.
  - *Note (crash safety):* on a resume the behind-base state is re-derived from the branch's actual
    relationship to its base, not from a stored counter, so a crash cannot make catch-up exceed its
    purpose — each catch-up moves the branch monotonically toward containing the base.

**FR-3.** When a ready pull request has failing checks, the showrunner shall attempt to fix the failing
checks and re-check, up to a set number of rounds, instead of handing back on the first failure.
  - *Acceptance (Given-When-Then):* Given a ready pull request with at least one failing check, when the
    ship step runs, then the showrunner makes at least one fix-and-re-check attempt before any hand-back.

**FR-4.** When the checks cannot be made to pass within the round limit, or the same checks keep failing
with no progress, the showrunner shall return the pull request to draft and hand back to the owner,
instead of looping or leaving a ready pull request with broken checks.
  - *Acceptance (Given-When-Then):* Given the same set of failing checks recurs across consecutive rounds,
    or the round limit is reached, when the loop ends, then the pull request is set back to draft and the
    hand-back explains the checks could not be made to pass. ("Same set" = the same collection of failing
    check identities.)

**FR-5.** The showrunner shall judge the checks on the ready, integrated head of the pull request, never
on a stale or draft version of the branch.
  - *Acceptance (rule):* a passing result is accepted only when it belongs to the same commit that is the
    pull request's head after any base integration; a pass recorded for an earlier commit is not accepted.

**FR-6.** When the back-half finishes — whether ready or parked — the showrunner shall hand back a
structured "your turn" summary that includes the pull-request link, what was built versus what was asked,
the test results, the check status, a spot-check list (a short checklist of items for the owner to
manually confirm before merging), and a clear statement that the merge is the owner's, instead of a
one-line status.
  - *Acceptance (Given-When-Then):* Given a completed run, when the hand-back is produced, then it contains
    the pull-request link, a built-versus-asked summary, the test results, the check status, a spot-check
    list, and the statement that the showrunner never merges.
  - *Acceptance (delivery is durable):* Given a run that has already finished its work (for example the pull
    request was flipped to ready) but crashed before the hand-back was delivered, when it resumes, then it
    delivers the hand-back rather than ending silently; and a hand-back that reaches neither the pull request
    nor the run's own record is surfaced as a warning, never dropped without trace.

**FR-7.** When bringing in the base (or resolving a conflict) changes the branch after the code review,
the showrunner shall note in the hand-back that the final commit carries integration done after review,
so the owner knows the merged-in base code was check-vetted rather than re-reviewed.
  - *Acceptance (Given-When-Then):* Given the ship step added an integration commit after the code review,
    when the hand-back is produced, then it carries a note that the final head differs from the reviewed
    commit because of base integration.

**FR-8.** The showrunner shall never merge the pull request; it only signals that the pull request is
ready and hands the merge to the owner. ("Merge" here means merging the pull request into its base — the
owner-only action; bringing the base *into* the branch under FR-1 and FR-7 is ordinary integration, not a
merge of the pull request.)
  - *Acceptance (rule):* on no path does a run perform the merge — a passing, up-to-date pull request is
    handed back as "ready for your merge," never merged.

**FR-9.** When catching up to base or fixing checks, the showrunner shall make only ordinary pushes to the
work-item's own branch; it shall never force-push and never push to the default branch on its own.
  - *Acceptance (rule):* every push a run makes goes to the work-item's own branch and is not a force-push;
    a force-push, or a push to the default branch, is never performed autonomously.

## When things go wrong (significant unhappy paths)

**UFR-1.** If bringing in the base produces a conflict, then the showrunner shall auto-resolve it only
when it is highly confident the resolution is trivially correct, and otherwise undo the integration and
hand back to the owner — it never hands back a guessed or half-integrated branch.
  - *Acceptance:* Given a base integration the showrunner is not highly confident it can resolve trivially,
    when it evaluates the conflict, then it undoes the integration (leaving the branch at the exact commit
    it was before) and hands back asking the owner to resolve it.
  - *Fit-criterion (the checkable face of the confidence judgment):* the spec makes two observable
    guarantees around the cooperative-layer confidence call — (a) an aborted integration leaves the branch
    head unchanged, and (b) any auto-resolved integration is pushed and re-checked before the run can report
    ready, so a wrong resolution surfaces as a failing check rather than shipping as "ready."
  - *Plan note:* the precise class of conflicts simple enough to auto-resolve with high confidence is a
    plan decision; at the spec level the only promises are the fail-closed default (uncertain → abort + hand
    back) and the two observable guarantees above.

**UFR-2.** If the showrunner cannot determine whether the branch is up to date, or cannot read the pull
request's check results, then it shall hand back without claiming the pull request is ready — it never
reports an up-to-date or passing state it could not confirm.
  - *Acceptance:* Given a freshness check or a check read that fails or is ambiguous, when the ship step
    runs, then the outcome is a park (not "ready"), and the hand-back says the state could not be confirmed.

**UFR-3.** If a checks provider exists but no checks run on the ready, integrated head, then the
showrunner shall hand back honestly that the checks did not run on the ready pull request, never a false
"all clear."
  - *Acceptance:* Given a provider is configured but the ready head has no checks, when the ship step
    judges the checks, then the hand-back states the checks did not run on the ready pull request (confirm
    before merge), not that everything passed.

**UFR-4.** If a second run begins changing the same work-item's pull request or branch while an earlier
run still holds that work-item, or if the showrunner cannot confirm it still holds the work-item, then it
shall stop before changing anything — no duplicate pull request, no undone ready-flip, no push from a
superseded or unconfirmed run.
  - *Acceptance:* Given two runs active on one work-item, when the superseded run reaches a step that would
    create the pull request, flip it to ready, return it to draft, or push, then that step does not run and
    the superseded run parks.
  - *Acceptance (fail-closed guard read):* Given the ownership-guard read fails or is ambiguous at a
    pull-request-changing step, when the showrunner evaluates it, then it treats the guard as lost and parks
    rather than proceeding — an unreadable guard never reads as held.

**UFR-5.** If a run crashes and resumes during the fix-the-checks loop, then the showrunner shall keep
counting fix rounds from where it left off so the round limit still holds across the restart — a crash
never resets the fix-the-checks loop to zero. (The catch-up loop needs no such stored count: its bound is
re-derived from the branch's actual relationship to its base on resume — see FR-2.)
  - *Acceptance:* Given some fix rounds were already attempted before a crash, when the run resumes, then
    the next fix round respects the same limit — a resume that ignored the prior count would attempt more
    rounds than the limit allows — and does not start counting from one again.

**UFR-6.** If a pull-request- or branch-mutating step (a catch-up or fix push, the integration, the
pull-request creation, or the ready/draft flip) fails or is interrupted partway, then the showrunner shall
not report the pull request ready; before it proceeds — on retry or on resume — it reconciles its local
state with the actual remote pull-request head, so a failed step never yields a false "ready" or a
silently-diverged branch.
  - *Acceptance:* Given a push fails after a fix commit is formed locally (the local branch is now ahead of
    the remote pull-request head), when the run next proceeds or resumes, then it brings the remote head
    into agreement with the reconciled local head before judging readiness, and never reports "ready" while
    the two heads differ. The same guarantee — reconcile before proceeding, never a false ready — holds when
    the step that failed is a pull-request creation or a ready/draft flip rather than a push.
  - *Plan note:* the exact recovery on a failed step (retry-then-park, or park immediately) is a plan
    decision; the spec fixes only the owner-visible promise — no false ready, no silent divergence.
  - *Acceptance (idempotent on resume):* Given a pull-request-mutating step (create, ready-flip, draft-flip)
    already succeeded but the run crashed before recording it, when it resumes, then re-issuing that step is
    a no-op rather than a duplicate or an error — the resume converges on the already-correct state.

## Non-functional requirements

- **Safety (no false ready):** the showrunner never reports "ready" on an unconfirmed pass, an
  un-integrated branch, or after a guessed merge. *Fit-criterion:* every "ready" outcome is backed by a
  confirmed-passing check result on the current pull-request head and a branch that already contains its
  base.
- **Concurrency safety:** a second run on the same work-item cannot corrupt the first run's pull request
  or branch. *Fit-criterion:* across two concurrent runs there is no duplicate pull request, no undone
  ready-flip, and no push from a superseded run.
- **Bounded autonomy:** neither the catch-up nor the fix-the-checks loop runs without limit, and a single
  wait for checks to reach a conclusion is itself bounded. *Fit-criterion:* catch-up stops at its limit, the
  fix loop stops at its round limit, and a wait on checks that never conclude ends in an honest hand-back
  ("checks did not complete") rather than an unbounded wait — each ending in an owner hand-back rather than
  continuing. (The exact wait bound is a plan decision.)
- **Secret hygiene in the hand-back:** any check-log text included in the hand-back is scrubbed; anything
  that cannot be scrubbed is dropped, not shown. *Fit-criterion:* no raw secret appears in a posted
  hand-back; a scrub failure produces a redaction note, not the raw text.
- **Behavior parity with the manual producer:** a given catch-up or failing-check situation reaches the
  same disposition the manual producer would reach. *Fit-criterion:* for the same inputs, the
  catch-up and fix-the-checks decisions match the manual producer's recovery behavior.

## Definition of done / success

The native back-half remediates instead of stopping at the first obstacle: a behind-base branch is
caught up (within a limit), failing checks are fixed (within a round limit, returning the pull request to
draft on terminal failure), every pull-request-changing step is guarded against a concurrent run, and the
run ends in a structured "your turn" hand-back — all matching the manual producer's recovery behavior. The
owner no longer sees a premature park where the manual producer would have recovered.

Verified by automated smoke tests — every functional and unhappy-path requirement (FR-1–FR-9, UFR-1–UFR-6)
has a smoke case or assertion; the exhaustive per-requirement test matrix is the tasks layer's to lay out.
The paths whose smoke shape is worth naming here: catch-up; the fix-the-checks loop; return-to-draft on
terminal failure; the conflict-abort path; the concurrency guard and its fail-closed guard-read; the
stale-pass rejection — a pass recorded for a pre-integration commit is not accepted (FR-5); the unreadable
freshness/check read parking (UFR-2); the no-checks-on-the-ready-head honest hand-back (UFR-3); the bounded
check-wait ("checks did not complete"); the fix-loop round count surviving a crash/resume (UFR-5); the
partial-failure reconcile, the resume-idempotency, and the hand-back re-delivery on resume; the
post-review-integration note in the hand-back (FR-7); and the structured hand-back, including that its
check-log content is scrubbed (no raw secret in the posted hand-back). The catch-up and fix-the-checks decisions are held to their reference behavior by the existing
parity fixtures (the decision-makers are parity-locked); the concurrency guard and the conflict-abort path
are exercised as their own smoke cases, not merely asserted via a flag. Plus a forged-ship walkthrough that
exercises catch-up, the fix-the-checks loop, return-to-draft, and the structured hand-back end-to-end.
Confirming the behavior against fully live runs to a real passing ship is handled through ongoing
dogfooding and is not a gate of this work-item.

## Assumptions & dependencies

- The shared catch-up and fix-the-checks decision-makers already exist and are the behavioral source of
  truth — the manual producer already uses them. This work connects them to the native back-half; it does
  not redesign them.
- The same ownership guard the build step already uses to protect against concurrent runs is available to
  extend to the back-half's pull-request-changing steps.
- The structured-hand-back builder already exists; this work calls it.
- The existing owner-authority guard already permits an ordinary feature-branch push and a return-to-draft,
  and gates the owner-only actions (merge, force-push, pushing to the default branch). This work relies on
  that existing behavior unchanged.
- **Sequencing with #118 (sibling — courier-surface collapse).** This work-item lands **before** #118, which
  folds and relabels the same back-half leaves *after* this surface settles. This work-item therefore leaves
  clean per-stretch seams but does **not** fold couriers or relabel leaves — that is #118's job (see Out of
  scope).
- **Shared read-back + per-write idempotency guard — built here as a reusable primitive (for #118).** The
  read-back-confirms-the-write and idempotent-on-resume behavior this spec needs (FR-5 stale-pass rejection;
  UFR-6 reconcile-before-proceeding plus create / ready-flip / draft-flip idempotent on resume) is the same
  bar #118's FR-4 sets for **every** durable write across the spine — and #118 records that the per-write
  idempotency guard *does not exist today*. Because this work-item builds first, it builds that guard as a
  **generic primitive** (a per-write key / append-if-absent / read-back-detects-a-prior-apply), not a one-off
  hardcoded to a single step, so #118 can generalize it across the spine rather than retrofit a second,
  divergent scheme. The plan owns the primitive's design; this cross-reference is the dependency it satisfies.
- **Fence / lease-generation threading — one coherent design (for #118).** This work threads the lease
  generation past the build phase and fences the new back-half pushes (FR-9, UFR-4; the back-half has no
  fence today). The plan lands that fence wiring cleanly and **documents the seam**, so #118's later
  fold/relabel inherits it rather than re-deriving it.
- **Hand-back delivery stays best-effort-but-surfaced (compatible with #118).** FR-6's durable-delivery
  acceptance (re-deliver on resume; warn if it reaches neither the pull request nor the run record) is a
  best-effort write the run does **not** advance or ship-gate on — matching #118's FR-4 carve-out for the
  readout post. The plan must not let the run's advance or ship outcome depend on the hand-back landing.

## Constraints

- The new behavior must operate within the existing showrunner execution model — no new privileged runtime
  capabilities are introduced for it.
- No change to the manual producer's behavior or to the shared decision-makers' logic — they remain the
  source of truth that the native back-half mirrors.
- The showrunner never merges — a hard, non-negotiable boundary that the new recovery behavior must not
  cross.

## Out of scope

- The backstop sweep of stale build worktrees (originally listed as a lower-severity gap) — routed to the
  existing cleanup/retention work-item (#42), not built here.
- Any change to the shared decision-makers' logic, or to the manual producer skill.
- Re-running the code review or the ship gate after a base integration — by design, the merged-in base code
  is already reviewed on its own branch and is check-vetted on the integrated head (FR-5 rejects a pass
  recorded for an earlier commit); the back-half surfaces a note instead (FR-7).
- Pre-checking, before the pull request, the checks that only run on the pull request — the fix-the-checks
  loop (FR-3, FR-4) is the recovery for such a failing check; no separate local pre-check is added.
- A full live run to a real passing ship as an acceptance gate — confirmed through dogfooding instead.
- Folding courier leaves or relabeling dumb-pipe leaves — that is #118's job, which sequences *after* this
  work-item once the back-half surface has settled; this work-item leaves clean per-stretch seams but does
  not fold or relabel.

## Coverage

| Area | Disposition | Where / why |
| --- | --- | --- |
| Empty & first-run | N-A | The back-half always resumes from an existing built branch / pull-request context; there is no empty or first-run state. |
| Invalid & malformed input | Specify | UFR-2 — an unreadable freshness or check read fails closed to a park, never a false "ready." |
| Boundaries & limits | Specify | FR-2 (catch-up limit, reality-derived on resume), FR-4 (fix-the-checks round limit), UFR-5 (fix-loop count honored across a resume), Bounded-autonomy NFR (a single check-wait is bounded). |
| Errors & failures | Specify | UFR-1 (base-integration conflict; the auto-resolvable class is Defer-to-plan), UFR-3 (checks did not run on the ready head), UFR-6 (a push or branch-mutating step fails/interrupts → reconcile, never a false ready), FR-4 (terminal check failure → return to draft). |
| Access & permissions | Specify | FR-8 (never merges the pull request) and FR-9 (only ordinary feature-branch pushes — never force-push, never push to the default branch) bound the new autonomous push surface; the plan confirms these stay on the permitted side of the existing owner-authority guard. |
| Duplicates & double-actions | Specify | UFR-4 (no duplicate pull request or undone ready-flip from a superseded run); UFR-6 (create / ready-flip / draft-flip are idempotent on resume — re-issuing a succeeded step is a no-op). |
| Conflicting / simultaneous use | Specify | UFR-4 — a concurrent run on the same work-item is stopped before it changes anything, and an unreadable ownership-guard fails closed (parks). |
| Misuse & abuse | N-A | Internal engine with no external or untrusted actor; secret leakage in the hand-back is covered as a non-functional outcome (secret hygiene). |
| Reach (i18n / a11y) | N-A | No user-facing interface; the hand-back is a plain-text pull-request comment. |
