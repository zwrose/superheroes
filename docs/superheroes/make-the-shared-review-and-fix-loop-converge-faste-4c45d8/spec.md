---
superheroes: doc
schemaVersion: 1
docType: spec
workItem: make-the-shared-review-and-fix-loop-converge-faste-4c45d8
issue: 125
size: large
status: approved
gates: {review: passed}
approved: "2026-06-30"
producedBy: "the-architect@0.3.0"
created: "2026-06-30"
updated: "2026-06-30"
delivered: "2026-07-02"
deliveryReceipt: "https://github.com/zwrose/superheroes/pull/129"
livesIn: ["plugins/superheroes/skills/review-code/reference/auto-fix-loop.md", "plugins/superheroes/skills/review-code/reference/round-driver.md", "plugins/superheroes/skills/review-code/reference/synthesis-pass.md"]
supersededInPart: [{"date": "2026-10-31", "sections": ["FR-3"], "ruling": "The owner's approval (2026-10-27, spec PR #2199) of the review-loop spec a-review-loop-that-converges-in-few-rounds-and-sta-3f628c. It replaces FR-3 (a first-time finding gets one local fix) with its FR-23, which lands with C4 (copies of a bug, #2220), not yet built on 2026-10-31; until C4 merges, the shipped behavior is still FR-3's."}]
---
# Make the shared review-and-fix loop converge faster and cost less

## Purpose

The shared review-and-fix loop — the engine behind the plan, tasks, and code reviews, and the
same panel the manual spec review drives — burns an unsustainable amount of tokens on
review-heavy documents. Two causes compound: it takes too many rounds (it grinds one finding at
a time and never makes the move a human reviewer makes — noticing a recurring *class* and
stating a rule that closes the whole tail), and each round is too expensive (it re-runs the full
panel of specialists, cold, over the whole document, every round). On one real work-item the
loop ran twice, spent roughly nine million tokens across about 148 specialist dispatches, and
still produced no approved plan. This work makes the loop converge in far fewer rounds and cost
far less per round — uniformly across every review — without weakening the safety the loop
exists to provide.

## Who it's for

- **The operator running the pipeline** (launching the showrunner, the producer, or a manual
  review) — they wait on these reviews and pay for the tokens they burn; they want a review that
  reaches a clean result quickly instead of grinding to a stop.
- **Anyone whose work-item passes a review gate** — their plan, tasks, or code clears review
  sooner and at lower cost, with the same correctness bar.

## Functional requirements

**FR-1.** When a blocking finding of the same class recurs in two or more review rounds (the
current round and at least one earlier round, not necessarily consecutive), the
reviser shall resolve it by stating a principle that closes the whole class — recorded as an
explicit, labeled coverage decision — instead of patching the single instance.
  - *Acceptance (Given-When-Then):* Given work under review (a document or a code change) where
    the same class of finding (for example, "a requirement is missing its acceptance test") was
    raised in two or more rounds (the current round and at least one earlier round), when the
    reviser runs the next round, then it records one
    class-covering principle in the review's durable record rather than another single-instance
    edit, and that class of finding is not raised again in the following round.

**FR-2.** When the reviser runs in any round after the first, the loop shall give it the findings
from the prior rounds so it can recognize a recurring class.
  - *Acceptance (Given-When-Then):* Given the second or a later round, when the reviser begins,
    then its working context includes the compiled findings from every prior round of this
    review.

**FR-3.** While a finding's class has not yet appeared in two or more rounds, the reviser shall
apply a single, targeted, minimal fix (a local edit) and shall not state a class-covering principle.
  - *Acceptance (rule):* a first-time finding is resolved by a local edit; the generalize move is
    withheld until that class of finding has appeared in two or more rounds (the FR-1 trigger).

**FR-4.** When the reviser states a class-covering principle, it shall record that principle in
the review's durable record as a labeled coverage decision — inside the document under review for
the document reviews (plan, tasks, spec), and in the code review's recorded review decisions for
the code review — so that the final independent reviewer can see the principle on every review
leg, and so that intermediate reviewers are not handed the prior findings.
  - *Acceptance (Given-When-Then):* Given a recorded principle, when the final independent reviewer
    reviews the revised work, then the principle is visible to it through the review's durable
    record (the document for a document review, the recorded review decisions for the code
    review), and no prior-round finding list is placed in an intermediate reviewer's context.

**FR-5.** Every adjudication the loop makes shall be recorded legibly as a challengeable coverage
decision (FR-4) — an out-of-scope entry, a coverage note, or a principle — visible to every
reviewer including the final confirmation round; the loop shall not hand any reviewer a hidden
"do-not-raise" list. If a concern genuinely cannot be recorded legibly and a reviewer keeps raising
it, the loop shall surface it to the operator (UFR-8) rather than silently suppress it or certify
around it.
  - *Acceptance (Given-When-Then):* Given a dismissed concern, when it is recorded, then it appears
    as a legible coverage decision that every reviewer — including the final round — can read and
    challenge, and no reviewer is handed a hidden do-not-raise list; and given a concern that cannot
    be recorded legibly and keeps recurring, when the round budget is reached, then the loop reports
    it to the operator (UFR-8) and does not certify around it.

**FR-6.** When a review reaches its second or a later round, the loop shall re-run a reviewer
dimension whenever it reported a finding in the previous round or the latest revision changed
content within that dimension's subject area, and may skip a dimension only when its most recent
result was a high-confidence clean result (it reported nothing and was not low-confidence) and the
latest revision is confined to content outside its subject area; when it is uncertain whether the
revision touches a dimension's subject area, the loop shall re-run that dimension (skipping is
fail-closed).
  - *Acceptance (Given-When-Then):* Given the test dimension reported a finding last round, when
    the next round runs, then the test dimension is re-run; and given the security dimension's most
    recent result was a high-confidence clean result and the latest revision changed only wording
    with no access, privacy, or data-exposure content, when the round runs, then the security
    dimension is skipped; and given any uncertainty about whether the revision touches a
    dimension's subject area, when the round runs, then that dimension is re-run.

**FR-7.** When the loop runs a reviewer dimension in an intermediate round, it shall run the
less-capable reviewer tier first and escalate that dimension to the most-capable reviewer tier
whenever the less-capable reviewer's result for that dimension is not high-confidence.
  - *Acceptance (Given-When-Then):* Given the less-capable reviewer returns a not-high-confidence
    result for a dimension (it reports low confidence, or a blocking finding it is not certain of),
    when the round is tallied, then that dimension is re-run by the most-capable reviewer before
    that dimension's result is treated as final; and given a high-confidence result (a confident
    clean or a confident blocking finding), when the round is tallied, then it is used as-is without
    escalation.

**FR-8.** Before the loop certifies a review as passed, the round immediately preceding
certification shall be a full confirmation round in which every reviewer dimension runs on the
most-capable reviewer tier, treats any recorded coverage decision as a claim open to challenge
rather than a settled exclusion, and finds nothing blocking at high
confidence — with no fix applied after it. If that round surfaces a blocking finding or returns a
not-high-confidence result, the loop shall resolve the gap and run another full confirmation round,
and shall never certify off an earlier or partial round.
  - *Acceptance (Given-When-Then):* Given all blocking findings appear resolved, when the loop is
    about to certify passed, then the most recent round is a full-panel, most-capable-tier round
    that treated recorded coverage decisions as challengeable, found nothing blocking at high
    confidence, and had no fix applied after it; and given that
    round instead surfaces a blocking finding or returns a not-high-confidence result, then the
    loop resolves the gap and runs another full confirmation round before it may certify.

**FR-9.** When a review run completes, the loop shall report its round count, the per-dimension
count of rounds run versus skipped, and the run's token usage — both in the run's readout and as
a saved telemetry record.
  - *Acceptance (Given-When-Then):* Given a completed review run, when its readout is produced,
    then the readout shows the round count, the per-dimension run-versus-skipped tally, and the
    token usage, and a matching telemetry record is saved as a durable artifact (not a transient
    log line) for later cross-run comparison.

**FR-10.** The improvement shall reach every review — the plan review, the tasks review, the code
review, and the manually-driven spec review panel — through the one shared loop.
  - *Acceptance (rule):* the four reviews share the single loop; a change to convergence,
    dispatch, or telemetry behavior is observable in all four without per-review duplication.

**FR-11.** The first round of a review shall run the full panel — every reviewer dimension — on the
most-capable reviewer tier (the baseline hunt), and a review that finds nothing blocking at high
confidence in that first round shall certify at the first round with no additional confirmation
round. The cheaper-tier-first cascade (FR-7) and dimension-skipping (FR-6) apply only to
intermediate rounds — those after the first round and before the final confirmation round.
  - *Acceptance (Given-When-Then):* Given a review whose first full-panel, most-capable-tier round
    finds nothing blocking at high confidence, when the loop tallies that round, then the review
    certifies at the first round with no additional round; and given a first round that finds a
    blocking finding, then the cheaper-tier cascade and dimension-skipping become available on the
    following intermediate rounds.

## When things go wrong (significant unhappy paths)

**UFR-1.** If a recorded principle closes off a finding that is in fact real, then the final
confirmation round — whose reviewers treat every recorded coverage decision as a claim open to
challenge, not a settled exclusion — shall raise that finding again and the loop shall not certify
the review as passed.
  - *Acceptance:* Given a recorded principle that wrongly forecloses a real issue, when the final
    confirmation round runs, then a reviewer challenges the principle and raises the real finding,
    and the loop resolves it and runs another confirmation round rather than certifying passed.

**UFR-2.** If a fix made in an intermediate round introduces a new problem in a dimension that was
skipped that round, then the final full-panel confirmation round shall catch it before the review
is certified.
  - *Acceptance:* Given an intermediate-round fix that introduces a regression in a
    previously-skipped dimension, when the final confirmation round runs, then that dimension
    flags the regression and the review is not certified passed.

**UFR-3.** If a cheaper reviewer is not confident about a dimension, then the loop shall escalate
that dimension to the most capable reviewer rather than certify on the cheaper result.
  - *Acceptance:* Given a low-confidence cheaper result, when the round is decided, then the
    dimension is escalated and the cheaper result alone never decides a clean outcome.

**UFR-4.** If a review run is interrupted and resumes partway through, then the loop shall rebuild
the reviser's cross-round memory — the prior findings and any recorded principles — so the
generalize move still works after the resume.
  - *Acceptance:* Given a run that resumes at a mid-loop round, when the reviser runs after the
    resume, then it still sees the prior rounds' findings and the recorded principles.

**UFR-5.** While dimensions are being skipped in intermediate rounds, the loop's stuck-detection
(its recurring-finding and no-progress checks) shall stay accurate — a skipped dimension shall
carry its most recent verdict forward, whether clean or blocking, and shall never read as a newly
changed result.
  - *Acceptance:* Given a dimension skipped this round, when stuck-detection evaluates the round,
    then that dimension contributes its most recent verdict (clean or blocking) and does not
    distort the recurrence or progress accounting.

**UFR-6.** If the reviser records a principle, then it shall do so as a bounded, labeled
coverage-decision addition and shall not otherwise rewrite or re-architect the owner's document.
  - *Acceptance:* Given a principle being recorded, when the document is revised, then the change
    is a contained, labeled coverage-decision entry and the rest of the document is left intact.

**UFR-7.** If telemetry cannot be recorded or the token usage is unavailable, then the review's
outcome and certification shall be unchanged and the run shall continue, saving whatever
telemetry is available.
  - *Acceptance:* Given a telemetry write failure, when the run finishes, then the pass-or-stop
    decision is identical to what it would have been and the failure does not halt the run.

**UFR-8.** If the loop cannot reach a clean confirmation within its round budget, then it shall
stop and report the still-open findings to the operator — it shall neither certify the review as
passed nor keep looping indefinitely.
  - *Acceptance:* Given the round budget is reached without a clean high-confidence confirmation
    (blocking findings still open, or a result that stays not-high-confidence), when the loop
    stops, then it reports the open findings and the round context to the operator and does not
    certify the review as passed.

## Non-functional requirements

- **Convergence (measurable):** re-run through the updated loop, the benchmark — the work-item
  #120 plan (the partial-failure-heavy native back-half plan that, on the pre-change loop, stopped
  after 7 rounds without an approved result) — reaches a clean certification in 3 rounds or fewer.
- **Cost (measurable):** on that same #120-plan benchmark, the post-change run's token usage is
  lower than a single baseline figure. The baseline is captured once from the pre-change run's
  run-level token usage (already observable per Assumptions), recorded as a durable figure stored
  with the benchmark, and frozen as the comparison point (the prior recorded runs were roughly 3.5
  and 5.45 million tokens; the comparison uses one freshly recorded baseline, not that range). The
  post-change run's figure comes from the telemetry of FR-9 — which ships in this work-item
  precisely because it is the instrument this target is measured by — and the comparison is between
  the two recorded figures. UFR-7's tolerance for missing telemetry protects the pass-or-stop
  decision during an incidental failure and does not waive measurement when deliberately
  benchmarking.
- **Where the savings come from (outcome):** the cost win rides primarily on convergence (FR-1's
  generalize-the-class move → fewer rounds) and dimension-skipping (FR-6). The cheaper-tier cascade
  (FR-7) is a secondary saving that can net-cost more for a dimension — cheap then strong — whenever
  the cheaper tier is not confident, so on hard docs it may wash out. A systematically over-confident
  cheaper tier degrades to cost, not safety: its wrong skips are caught by the final full-panel round
  (UFR-2), forcing extra confirmation rounds. The benchmark shall attribute its measured savings by
  source (convergence, skips, tier-split) so a marginal tier-split is not over-credited.
- **Correctness floor (outcome):** no review is ever certified passed without a final full-panel,
  most-capable-tier confirmation round; the intermediate-round savings never weaken that gate.
- **Uniformity (outcome):** the four reviews show the same convergence, dispatch, and telemetry
  behavior; none of them regresses.
- **No regression (outcome):** the project's existing validation and test suites remain green after
  the change; in particular, a review that is already clean still certifies in a single round
  (FR-11), so the common fast case does not regress in rounds or cost.

## Definition of done / success

The work-item #120 plan, re-run through the updated loop, certifies clean in 3 rounds or fewer
using fewer tokens than the single frozen baseline figure (captured once from the pre-change run's
run-level token usage and stored with the benchmark), with a comparison record showing both the
frozen baseline and the post-change run's telemetry figure. Two deliberately constructed probes each fail
closed — the loop never certifies either as passed: (1) a scenario in which a recorded principle
is deliberately wrong (it forecloses a finding that is in fact real), and (2) a scenario in which
an intermediate-round fix introduces a regression in a dimension that was skipped that round. All
four reviews run on the updated shared loop with the project's tests and validators green, and
every run's readout shows the round count, the per-dimension run-versus-skipped tally, and the
token usage. (How each probe is constructed is the plan's to specify.) To guard against tuning to a
single artifact, the convergence and cost targets are validated on the #120 plan and on at least
one second, differently-shaped benchmark — a code review, not a plan — whose own frozen pre-change
baseline and targets are established the same way (construction the plan's to specify); if only the
#120 plan is used, the single-benchmark over-fit risk is stated and accepted at plan time.

## Assumptions & dependencies

- Builds on the existing shared review-and-fix loop and the native run spine it runs inside.
- Relies on the loop already keeping a durable per-round record of findings. It also needs a
  confidence signal per reviewer result — load-bearing for the skip (FR-6), escalate (FR-7), and
  certify (FR-8) decisions. That signal must be elicited in a defined way and calibrated so that a
  cheaper-tier "confident clean" is rarely wrong; where the loop does not already expose such a
  calibrated per-dimension-and-tier signal, defining and calibrating it is part of this work, and
  how it is elicited and calibrated is the plan's to specify.
- Assumes the per-run token usage is observable at the run level (the same source the benchmark's
  token figures came from).
- The benchmark plan remains available to re-run as the measuring stick.

## Constraints

- What counts as a blocking finding (Critical and Important) is unchanged — convergence comes from
  resolving the tail faster, not from accepting more of it.
- The final full-panel confirmation round is non-negotiable; the savings apply to intermediate
  rounds only.
- Reviewers stay independent — no reviewer is ever shown prior findings or a hidden do-not-raise
  list; every dismissal is a legible, challengeable coverage decision (FR-4/FR-5) that the final
  confirmation round sees and can challenge.
- When it is uncertain whether a revision touches a dimension's subject area, the loop runs that
  dimension — skipping is fail-closed.
- The conservative, minimal-edit behavior stays the default for any finding that has not recurred.

## Out of scope

- Accepting a review as "good enough" while a smaller, non-critical tail of findings is still
  open (graceful-degrade certification) — explicitly excluded; what counts as blocking is
  unchanged.
- Changing the number or composition of reviewer dimensions on the panel — running fewer than the
  full dimension set on a trivial change (right-sizing panel *composition*, #34). Round 1 runs the
  full dimension set by design (FR-11).
- Changing the per-finding severity rubric.
- Reusing one review's clean dimensions to skip another review (carrying results across the
  spec, plan, and tasks reviews of a work-item).

## Open questions

None.

## Glossary

- **Round:** one pass of the loop — the reviewers run, the findings are tallied, the reviser
  fixes, and the loop decides whether to repeat.
- **Dimension (reviewer):** one specialist review angle — for example security, architecture, or
  tests. The panel runs several together.
- **Blocking finding:** a Critical or Important finding that must be resolved before a review can
  pass.
- **Reviser:** the actor that applies fixes to resolve a round's blocking findings — the loop's
  automated revise step on the plan, tasks, and code reviews, and the orchestrator running the
  manual spec review on the spec leg. The generalize-and-record move (FR-1, FR-4) applies on every
  leg.
- **Local edit (targeted fix):** a change confined to the single instance a finding cites — not a
  labeled coverage decision and not a broad rewrite (the default response under FR-3).
- **Principle (coverage decision):** a stated rule that resolves a whole recurring class of
  findings at once, recorded as a deliberate, labeled decision.
- **Final full-panel confirmation round:** the mandatory last round — every dimension present, each
  on the most capable reviewer — that gates certification.
- **Intermediate round:** a round after the first and before the final confirmation round — where
  the cheaper-tier cascade (FR-7) and dimension-skipping (FR-6) apply. The first round (a full-panel
  baseline hunt on the most-capable tier, FR-11) and the final confirmation round are not intermediate.
- **Review (leg):** one use of the shared loop — the plan review, the tasks review, the code
  review, or the spec review panel.
- **Class (of finding):** a set of findings that share one underlying gap — for example "a
  requirement is missing its acceptance test", raised against several different requirements, is
  one class. Two findings are the same class when one stated principle would resolve both.
- **Less-capable / most-capable reviewer tier:** the two model tiers the loop runs reviewers on — a
  cheaper, less-capable tier tried first in intermediate rounds, and the strongest tier used for the
  first baseline round (FR-11), for escalation, and for the final confirmation round.
- **High-confidence result:** a reviewer result the reviewer is sure of — whether a confident clean
  (nothing to flag) or a confident finding. A result that is not high-confidence (low-confidence or
  uncertain) is never skip-eligible (FR-6), is escalated when it comes from the cheaper tier (FR-7),
  and cannot certify in the final round (FR-8).
- **Round budget:** the fixed maximum number of rounds a single review may run before UFR-8 forces
  it to stop and report — the loop's existing cap (seven rounds).
- **Subject area (of a dimension):** the kinds of content a reviewer dimension is responsible for —
  the security dimension's subject area is access, privacy, and data-exposure content; the test
  dimension's is tests and verifiability; and so on.
- **Benchmark plan (the #120 plan):** the partial-failure-heavy work-item #120 native back-half
  plan that, on the pre-change loop, stopped after 7 rounds without an approved result — re-run as
  the measuring stick for this change.

## Coverage

| Area | Disposition | Where / why |
| --- | --- | --- |
| Empty & first-run | N-A | The loop always runs against an already-produced document or change; there is no empty or first-run state. |
| Invalid & malformed input | Specify | UFR-1 (a wrong principle is caught by the final pass) and UFR-6 (a principle is a bounded edit, not a rewrite). |
| Boundaries & limits | Specify | FR-3 (the generalize move triggers only after a class appears in two or more rounds), UFR-5 (skip accounting stays accurate at the round boundary), and UFR-8 (the round budget is bounded; on non-convergence the loop stops and reports rather than looping forever). |
| Errors & failures | Specify | UFR-2 (a skipped-dimension regression is caught), UFR-4 (resume rebuilds cross-round memory), UFR-7 (telemetry failure never changes the outcome). |
| Access & permissions | N-A | Internal pipeline machinery; it runs inside the operator's own review and has no separate user-facing access control. |
| Duplicates & double-actions | Specify | UFR-5 (a recurring or repeated finding is handled by stuck-detection); wire-level duplicate dispatch is deferred to the plan as existing loop behavior. |
| Conflicting / simultaneous use | N-A | A single review run is sequential over one document; there are no concurrent editors of the same document within a run. |
| Misuse & abuse | Specify | UFR-6 (the reviser may not over-reach on the owner's document) and UFR-3 (a cheaper reviewer cannot quietly hide a real issue). |
| Reach (i18n / a11y) | N-A | Internal developer tooling with no end-user interface, locale, or accessibility surface; the only owner-visible output is the run readout (FR-9). |
