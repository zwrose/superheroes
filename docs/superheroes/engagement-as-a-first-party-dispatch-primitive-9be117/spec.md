---
superheroes: doc
schemaVersion: 1
docType: spec
workItem: engagement-as-a-first-party-dispatch-primitive-9be117
issue: 1004
parent: null
size: medium
status: draft
approved: null
gates: {review: pending}
producedBy: "workhorse@0.27.0"
created: "2026-08-14"
updated: "2026-08-14"
---
# Engagement as a first-party dispatch primitive

## Purpose

When we send work to an outside engine — a review seat, an implementer, an auditor — we need to know
one thing before we trust what comes back: **did it actually do the work?** Today nothing in the
result says so plainly. Several parts of the system work it out for themselves, from the shape of
whatever came back. The machinery that exists to compensate — the planted-defect control probe — costs
a whole extra engine dispatch each time we want an honest answer.

This design makes that answer **a stated fact carried in the result**, wherever a consumer can
actually receive it. It is a change to how the answer is *represented and read*: no new refusal, no new
gate, no seat held to a higher bar than today.

**The round's most important finding is a limit, not a mechanism.** The issue asks for a signal
"consumed uniformly by parse, round driver, canary, and forfeit accounting." Three of those four can
read it directly. The **round driver cannot receive it per-seat** — a seat envelope's own fields are a
claimant-controlled advisory echo that authenticates nothing
[cite: plugins/superheroes/lib/round_adapters.py § claimant-controlled ADVISORY ECHO]. Reaching it
means routing the attestation through an authenticated out-of-band channel, which is a materially
larger change than the rest of this work and is scoped separately here rather than assumed.

## Who it's for

- **The owner**, who reads a build's disclosures and needs "this seat never ran" to mean what it says.
  Today that phrase is sometimes an overstatement of what we actually observed.
- **The advisor**, who vets builds from their artifacts and must be able to tell a seat that did
  nothing from a seat whose work our transport dropped.
- **The builder session**, which today must know which inference rule applies to whichever surface it
  is reading.
- **The maintainer of the dispatch machinery**, for whom the same question currently has several
  answers in several places.

## What is true today

Everything in this section was read from the code. Where a claim is load-bearing it carries a citation.

### The classifier is sound; what surrounds it is not

There is a single, well-reasoned home for the question. It is action-based, refuses to conclude
inaction from absence of evidence
[cite: plugins/superheroes/lib/engine_adapter.py § NEVER returns "inert"], and excludes token spend and
wall time on measured grounds
[cite: plugins/superheroes/lib/engine_adapter.py § Token spend cannot separate engaged from vacuous].
This design keeps all of that reasoning. The defects are around it.

**D1 — the attestation is not carried on every terminal result.** It is *absent* on `unrunnable`
refusals and *present with the value `null`* on timeout, refusal, nonzero-exit, and **missing-stdout**
forfeits — a shape the reference documents as a trap
[cite: plugins/superheroes/skills/workhorse/reference/dispatch-mechanics.md § is **unsafe**]. A
consumer that cannot read the field uniformly falls back to reasoning about outcome tokens. That
fallback is the archaeology this work retires.

**D2 — the specimen: one result, two contradictory answers.** On the vacuous branch the runner attaches
an engagement block whose verdict is computed over `{findings: [], investigated: None, engagement:
<telemetry>}` [cite: plugins/superheroes/lib/engine_dispatch.py § _engagement_with_read]. A seat with
an observed tool call therefore ships `reason: "vacuous"` **and** a verdict of engaged **in the same
object** — and that same object also carries a disclosure string asserting the seat never ran, before
any consumer sees it. The panel then reads neither, classifying from the outcome token and disclosing
[cite: plugins/superheroes/lib/round_driver.py § classed as never-ran].

The defect is **not** a missing third value. It is that **the consumers ignore the attestation and let
outcome tokens overwrite it.**

**D3 — the derivation is spread across at least eight sites.** Enumerated rather than counted, because
the migration set must not depend on anyone's recall:

| # | Site | What it derives |
| --- | --- | --- |
| 1 | `round_driver._fold_panel` | ran-vs-not-ran, from `vacuous` / not-run tokens; reads no attestation |
| 2 | `round_adapters._apply_predicate` | whether a seat owes a findings field, from the same two keys [cite: plugins/superheroes/lib/round_adapters.py § _apply_predicate] |
| 3 | `engine_dispatch._ledger_stages` | ledger engaged/delivered — the residue scan takes **precedence** over the classifier, which is consulted only as a fallback [cite: plugins/superheroes/lib/engine_dispatch.py § _ledger_stages] |
| 4 | `seat_canary.run_canary` | the probe's own verdict, outcome-token-first [cite: plugins/superheroes/lib/seat_canary.py § Fail-closed: artifact engaged but delivery failed] |
| 5 | `engine_adapter.review_artifact_shape` | an independent resemblance score whose own contract admits an error dump can pass [cite: plugins/superheroes/lib/engine_adapter.py § a long engine error dump] |
| 6 | `round_driver.canary_liveness` | per-vendor proven/dead/unproven, from probe flags plus its own payload check |
| 7 | `forfeit_ledger` attribution | engaged-but-not-delivered, from the delivery stage plus exit code and stdout size |
| 8 | the disclosure emitters | `engine_dispatch._review_terminal_forfeit` and the receipt summary each render a never-ran claim in owner-facing text |
| 9 | `engine_dispatch._maybe_upgrade_review_terminal_forfeit` | mints the engaged-artifact token from the residue scan — the **producer** of the token sites 1, 4 and 8 then read |
| 10 | `dispatch_outcome.counts_as_run` | derives ran-vs-not-ran from the not-run token set; currently **uncalled** |

Three are **not** migration targets, listed so a build that meets them knows why: **2** is a schema
check on claimant input that predates any attestation; **5** stays confined to salvage; **10** is dead
code and a deletion target in step 6, not a consumer to migrate. **9** is a migration target — it is
where FR-9's artifact-recovered fact is produced.

**D4 — the two axes exist in name only.** The vocabulary module declares stage names
[cite: plugins/superheroes/lib/dispatch_outcome.py § STAGE_ENGAGED] and the reference states they are
two variables
[cite: plugins/superheroes/skills/workhorse/reference/dispatch-mechanics.md § Engaged vs delivered are two variables],
but no producer or consumer references those constants, and two neighbouring helpers in the module
have no call sites at all.

**D5 — the write path has no attestation.** Write dispatches build no engagement block
[cite: plugins/superheroes/lib/engine_dispatch.py § _grade_write_attempt]; their ledger stage is
derived from success or the presence of a salvage block.

**D6 — the instrument is vendor-asymmetric.** A tool-call observation exists only for the cursor
stream [cite: plugins/superheroes/lib/engine_adapter.py § cursor_tool_calls]; the codex path yields
only a token count, which is a magnitude and must not count
[cite: plugins/superheroes/lib/engine_adapter.py § Token spend cannot separate engaged from vacuous].
For a codex seat, "we did not
observe action" therefore often means **we had no instrument**, not that nothing happened. Any honest
contract has to say so rather than let the two look alike.

### The trust boundary — the finding that reshaped this design

The round driver receives **no per-seat dispatch result**. It consumes a seat envelope whose fields are
a claimant-controlled advisory echo, with dispatch provenance arriving only out-of-band through the
dispatch manifest [cite: plugins/superheroes/lib/round_adapters.py § claimant-controlled ADVISORY ECHO].
This is the same rule the audit leg enforces when it refuses a seat's self-reported vendor
[cite: plugins/superheroes/lib/audits.py § apply_audit_results].

**One dispatch-derived record does already cross that boundary, and it is the model to build on rather
than a counter-example.** The control-probe landing is read out-of-band from the session store by the
orchestrator and passed into the fold as its own argument
[cite: plugins/superheroes/lib/round_records.py § canary_path], never through a seat payload. So the
channel this design needs is not unprecedented — but that slot is **per-vendor**, written once per
probe, while an attestation is **per-seat, per-attempt**. Step 5 below is scoped against that real
difference, not against an absolute.

So "the panel fold reads the attestation" is not a small migration — **widening the seat payload to
carry it would make a wrapper observation relayable by the claimant**, which is precisely the
self-attestation this design rejects. Reaching the round driver honestly means routing the attestation
through the authenticated provenance channel. That is a real change to a trust-bearing surface, and it
is scoped as its own deliverable below rather than folded in.

### What must survive unchanged

- **Audit-collection provenance is authorization, not engagement.** An engaged but misrouted auditor
  must still fail to discharge.
- **The engaged-artifact forfeit is never credited**
  [cite: plugins/superheroes/rubric/review-discipline.md § Salvage valve].
- **Credit has more axes than engagement and delivery.** A seat is also marked missing on a missing or
  stale receipt, and a zero-finding cross-vendor seat additionally requires an engaged vendor probe. A
  contract that says "delivery and outcome govern credit" is **false as an exhaustive statement**, and
  the matrix below is qualified accordingly.

## Functional requirements

Vocabulary note: this design uses **action** (not "engagement") for the verdict, **observation** (not
"evidence") for its entries, and **gradeable** (not "delivered") for the second axis, because each of
the obvious words is already taken by something else in this repo — see the Glossary.

**FR-1.** The system shall carry an action attestation on every **terminal** review-dispatch result,
with no exceptions for refusals or forfeits.
  - *Acceptance (rule):* for every terminal reason the runner can return — including `unrunnable` and
    the missing-stdout forfeit — the result carries an attestation that is neither absent nor `null`.

**FR-2.** The system shall express the verdict as exactly two values — `observed` and `not-observed` —
and shall never express a value asserting proven inaction.
  - *Acceptance (rule):* `not-observed` means *we did not observe action*, never *the seat did nothing*.

**FR-3.** The system shall record the **observations** that produced the verdict as a list of entries,
each naming what was seen, where it was seen, and whether it was **wrapper-minted** or
**engine-asserted**.
  - *Acceptance (rule):* the wrapper-minted kinds are findings parsed at the wrapper's own parse
    boundary and investigated paths that survive the spot-check. The tool-call stream count is
    **engine-asserted**: it is parsed from the engine's own stdout, and today from *raw* stdout before
    the prompt-echo strip, so text inside a reviewed diff can produce it. The entry says so.

**FR-4.** The system shall make the verdict a function of the recorded observations alone: an empty
list yields `not-observed`; a list with at least one **schema-valid** entry yields `observed`.
  - *Acceptance (rule):* any reader can recompute the verdict from the list and always agrees with the
    recorded one.

**FR-5.** The system shall never allow a telemetry **magnitude** — tokens, bytes, seconds — to produce
or change the verdict.
  - *Acceptance (rule):* no magnitude is an observation. Magnitudes ride alongside for diagnosis. A
    tool-call *observation* is an entry; its *count* is a magnitude reported beside it.

**FR-6.** The system shall carry a **gradeable** answer beside the action verdict, defined by the
following exhaustive truth table for review dispatches, and never inferred from the outcome token.

| Terminal case | `gradeable` |
| --- | --- |
| Findings parsed and accepted | true |
| Empty findings with an accepted investigation record | true |
| Empty findings, investigation floor failed | false |
| Parse failed / unreadable payload | false |
| Timeout, nonzero exit, missing stdout, or refusal | false |
| Artifact recovered by salvage after a forfeit | false |
| No attempt spawned | false |
| Run abandoned, or the terminal record unreadable — the `unrunnable` outcomes that occur **with** attempts already spawned | false |

  - *Acceptance (rule):* the write path is out of scope (see Out of scope), so item-check delivery —
    which is a *count of declared paths*, an unrelated meaning of the same word — is not in this table.

**FR-7.** The system shall carry the attestation on **non-terminal** results too, marked explicitly
**provisional**, and shall not permit omission.
  - *Acceptance (rule):* a `running` result carries a provisional attestation. No consumer ever
    interprets absence, because absence does not occur. A provisional attestation is never read for a
    credit or disclosure decision.

**FR-8.** The system shall record observations **monotonically across attempts**: an observation made
on any attempt of a run stands for the run, even if a later attempt times out.
  - *Acceptance (Given-When-Then):* Given a first attempt with an observed tool call and a second that
    times out, when the run folds, then the verdict is `observed` and `gradeable` is false — the
    failure-with-action case, distinct from failure-without.

**FR-9.** The system shall carry a **third fact** distinguishing a forfeit that recovered an artifact
from one that recovered nothing, kept on the **gradeable/outcome side** rather than the action side.
  - *Acceptance (rule):* the artifact-recovered fact is what a consumer keys on to apply the
    salvage valve's independent-verification obligation. It is **not** an observation and does not move
    the verdict, because the only thing that mints it is a resemblance heuristic.

**FR-10.** The system shall have consumers **read** the attestation rather than re-derive it, while
credit remains governed by the full set of credit axes — gradeable, outcome, receipt validity, and the
applicable vendor probe ruling.
  - *Acceptance (rule):* the consumer matrix below is normative, and its credit column is proven
    unchanged against today's behaviour for every row.

**FR-11.** The system shall express a control probe's result as a **vendor-scoped ruling** bound to the
probe invocation, and a consumer shall bind a ruling to seats by **vendor and engine model**.
  - *Acceptance (rule):* a ruling a consumer cannot bind resolves to the **strict** side, not the
    permissive one — because the permissive branch today is what an unbindable probe would fall into.
  - *Acceptance (rule):* **model binding requires trusted model provenance the round driver does not
    have today** — the out-of-band manifest projects vendor only, and a seat envelope's model is
    claimant-controlled. So this FR carries a prerequisite: a trusted `(vendor, model)` projection and
    pair-keyed probe storage, or the binding is vendor-only and says so. It is not satisfiable by
    reading a model the claimant supplied.

**FR-12.** The system shall keep audit-collection provenance as a separate authorization axis,
unchanged.

**FR-13.** The system shall correct the owner-facing disclosures so a seat we did not observe acting is
described as **action not observed**, not as one that never ran — at **every** emitter, including the
two inside the dispatch result and receipt summary, not only the panel fold.

**FR-14.** The system shall read results produced before this contract through a normalizer, whose
precondition is a **terminal** result.
  - *Acceptance (Given-When-Then):* Given a stored result carrying a legacy scalar verdict and no
    observation list — the dominant stored shape — when a consumer reads it, then the normalizer
    synthesizes one entry naming the legacy scalar and its source, so the recorded and recomputed
    verdicts agree by construction, the entry is marked reconstructed, and a legacy `observed` is
    never silently downgraded.

## When things go wrong (significant unhappy paths)

**UFR-1.** If a dispatch never spawns an engine, then the attestation shall be `not-observed` with an
empty list — never proven inaction.

**UFR-2.** If a seat forfeits and a review-shaped artifact is recovered from its stdout, then the
attestation shall read **`not-observed`** unless an independent observation exists, and the
artifact-recovered fact (FR-9) shall carry the salvage obligation.
  - *Acceptance:* Given a codex seat that times out having written a review-shaped artifact, when the
    run folds, then the verdict is `not-observed` — because the only thing that saw the artifact is the
    resemblance heuristic — while the artifact-recovered fact is true, credit is false, and the salvage
    findings still require independent verification. **This is the corrected form of a rule the first
    draft got backwards.**

**UFR-3.** If a control probe returns not-engaged, then it shall be recorded as a **vendor ruling** with
its own provenance, and shall not become a factual claim about any individual seat.
  - *Acceptance:* the record names the probe invocation, vendor, model, and failure class — because a
    negative probe cannot separate no-spawn from transport failure from delivery failure from absence
    of evidence.

**UFR-4.** If the observations and the outcome token disagree — the D2 specimen — then both shall be
recorded and the disclosure shall state the **weaker, accurate** claim.

**UFR-5.** If a stored result predates this contract, then its attestation shall be visibly
reconstructed and shall not stand in for an observed one in any accounting.

**UFR-6.** If a consumer encounters an observation entry whose kind it does not recognise, then the
entry shall be **retained as an opaque diagnostic and shall not count toward the verdict** until its
kind and provenance are understood.
  - *Acceptance:* Given a result carrying only an unrecognised entry, when the verdict is recomputed,
    then it reads `not-observed`. **This is the corrected form of the first draft's rule**, which
    counted unknown entries and thereby let a malformed or claimant-influenced entry manufacture
    action — a fail-open the review caught.

**UFR-7.** If the run's terminal record cannot be made durable, then the durable accounting row shall
not present the run as folded.
  - *Acceptance:* the ledger row is written after — or is reconcilable with — the terminal record, so a
    run that was abandoned after a failed fold cannot leave a folded-looking row that a later, correct
    row is deduplicated against.

## The consumer matrix

Normative for FR-10. **Action records what we saw. Credit is governed by gradeability, outcome,
receipt validity, and the vendor probe ruling — all four.**

| Case | Action | Gradeable | Artifact recovered | Credit (given a valid receipt and a probe ruling that does not bar it) | Owner-facing description |
| --- | --- | --- | --- | --- | --- |
| Findings returned | `observed` | true | — | Yes | reviewed, with findings |
| Empty findings, investigation record accepted | `observed` | true | — | Yes | reviewed, clean |
| Empty findings, floor failed, no observation | `not-observed` | false | no | **No** | nothing gradeable; action not observed |
| Empty findings, floor failed, tool call observed | `observed` | false | no | **No** | nothing gradeable; the seat was observed acting |
| Forfeit, artifact recovered, no observation | `not-observed` | false | **yes** | **No** | produced something we could not carry; findings need independent verification |
| Forfeit, artifact recovered, observation exists | `observed` | false | **yes** | **No** | as above, and the seat was observed acting |
| Timeout / nonzero exit / refusal, observation exists | `observed` | false | no | **No** | no gradeable result; the seat was observed acting |
| Timeout / nonzero exit / refusal, no observation | `not-observed` | false | no | **No** | no gradeable result; action not observed |
| No attempt spawned | `not-observed` | false | no | **No** | never dispatched |

**Two independent credit axes are deliberately outside this table**, because they are not derivable
from it and a build must not read the table as exhaustive: a **missing or stale receipt** marks a seat
missing regardless of everything above, and a **zero-finding cross-vendor seat** additionally requires
an engaged vendor probe ruling. The parenthetical in the credit heading is load-bearing, not a caveat.

## Before and after — what actually changes

Required so that "this adds no new refusal" is demonstrable rather than asserted, against the standing
bars [cite: LEDGERS.md § No new honesty/grounding gates without a named escape] and
[cite: LEDGERS.md § No fail-closed hardening beyond the last observed incident].

| Decision | Today | After | Changed? |
| --- | --- | --- | --- |
| Vacuous seat counts toward certification? | No | No | No |
| Engaged-artifact seat counts? | No | No | No |
| Clean seat with accepted investigation record counts? | Yes | Yes | No |
| Missing/stale receipt still marks a seat missing? | Yes | Yes | No |
| Not-engaged probe still downgrades that vendor's empty seats? | Yes | Yes | No |
| Light/micro control probe still mandatory on every review? | Yes | Yes | No |
| Investigation floor still forfeits an unproven empty seat? | Yes | Yes | No |
| Unauthenticated auditor still fails to discharge? | Yes | Yes | No |
| Salvage findings still require independent verification? | Yes | Yes | No |
| Ledger's **salvage-tracking** value for an artifact-recovered forfeit | `stages.engaged: true`, from the residue scan | preserved, **under its own name** — it tracks artifact recovery, not action | No |
| Ledger's **action-facing** value | same field, same residue-first rule — a second answer | derived from observations, agreeing with the attestation | **Yes — the second answer goes away** |
| How a not-observed seat is *described* | "classed as never-ran" | "action not observed" | **Yes — wording** |
| How a consumer *learns* a seat's status | Re-derives per surface | Reads the attestation | **Yes — mechanism** |
| Can two readers of one result disagree? | Yes (D2) | No — **once the migration completes** | **Yes — the defect closes** |

**No row adds a refusal, tightens a bar, or withholds a certification granted today.**

Two rows carry qualifications that a build must not read past. **The ledger split is deliberate**: the
residue scan's value is real information — an artifact was recovered — and it is kept, but it is not an
answer to *did the seat act*, and today one field carries both. Splitting the field is what lets the
action-facing value agree with the attestation without discarding the salvage signal; simply
"preserving the precedence" would have kept two answers to one question forever, which is the defect
this design exists to close.

**And the last row is true only at the end.** The migration has a mixed-mode window — see the
decomposition — during which the attestation exists and some readers still infer. That window is
named, versioned, and bounded rather than claimed away.

## The owner-gate dead end (the folded rider)

A session that has taken one advance-driven fold, arriving at an owner gate the calibration cannot
authorize, can neither advance (the gate parks without folding) nor hand-submit (the session-mode
fence refuses). Both moves are closed.

**This design does not fix it, and saying so is the useful contribution.** None of the three paths
reads an engine result or an attestation; the collision is between a session-wide interleave fence and
an owner-only phase. It belongs to the same *class* — a condition inferred from latches rather than
represented — which is why it was folded here, but the attestation cannot make it unrepresentable. It
needs a state-machine resolution: an owner-gate transition legal for advance-driven sessions, so an
authorization failure leaves at least one move available. Scoped as an independent issue below.

## Non-functional requirements

- **No added dispatch cost.** The attestation is computed from what the runner already observes. The
  control probe's cost is unchanged: it bounds its first attempt but floors its retry wait, so worst
  case is materially longer than the nominal timeout — recorded so any future proposal about the
  probe's trigger argues against the real number.
- **No weakening of an existing safeguard.** Every "No" row above is a safeguard preserved.
- **Reconstructable accounting.** An observed attestation is always distinguishable from a
  reconstructed one, and a durable accounting row never presents a fold that did not happen (UFR-7).

## Definition of done / success

The owner can trust that "this seat never ran" is only said when we have grounds to say it; the advisor
can tell from a result alone whether a seat acted and whether anything gradeable arrived; and the sites
enumerated as migration targets in D3 read the attestation instead of deriving their own.

## Assumptions & dependencies

- The classifier's reasoning — action-based, never magnitude-based, never concluding inaction from
  absence — is kept, not revisited. Its measured basis is in the classifier itself
  [cite: plugins/superheroes/lib/engine_adapter.py § Measured 2026-07-26]; the separate rule that
  telemetry never substitutes for the investigation record is doctrine
  [cite: CONVENTIONS.md § Engine telemetry corroborates engagement but never substitutes for that record].
- The investigation-record floor is unchanged in effect
  [cite: plugins/superheroes/rubric/review-base.md § investigation record is a seat that never ran];
  only its *wording* is in FR-13's scope.
- The control-probe obligation in single-reviewer lanes is unchanged
  [cite: plugins/superheroes/rubric/review-discipline.md § review did not happen].
- **The prose surfaces carrying this contract are eight, enumerated**:
  `skills/workhorse/reference/dispatch-mechanics.md`, `skills/review-code/reference/auto-fix-loop.md`,
  `skills/review-code/reference/round-driver.md`, `rubric/review-discipline.md`,
  `rubric/review-base.md`, **`CONVENTIONS.md` §7.5** (the vacuous-forfeit and telemetry sentences —
  the doctrine home this design cites two bullets above, and the one a "three surfaces" scoping would
  have left stale), and the two charters, whose probe wording is mechanically pinned by a
  clause-presence test that a doctrine change must keep green
  [cite: plugins/superheroes/lib/tests/test_charter_boundary_sync.py § not-engaged-never-passes].

## Constraints

- **No new refusal, gate, or fail-closed path.** The before/after table is the evidence.
- **The engaged-artifact seat is never credited**, and its salvage obligation survives (FR-9).
- **Audit authorization is untouched.**
- **A widened value set is a fall-open vector**, and the existing literal-scan census prevents
  duplicate spellings, not consumer exhaustiveness
  [cite: plugins/superheroes/lib/tests/test_dispatch_outcome_census.py § test_dispatch_outcome_census_clean].
  Keeping the verdict two-valued (FR-2) is what keeps that surface small.
- **The seat payload is not a transport for wrapper observations.** An attestation arriving in a seat
  envelope authenticates nothing.

## Out of scope

- **Write dispatches.** They carry no attestation today, and the evidence that would ground one is a
  genuine open question. Item-check delivery already uses the word "delivered" for a count of declared
  paths — a collision to resolve before any write-side work.
- Terminal-design questions held elsewhere: stall-menu spend semantics, accept-risk eligibility, the
  sticky-breaker criterion.
- Retiring or loosening the control probe.
- The owner-gate dead end, scoped independently.

## Decomposition into build issues

**Restructured on review evidence.** The first draft put a six-step contract train ahead of the one
change with immediate owner-visible value, and one lens argued the whole contract was over-built for a
defect whose only visible symptom is a disclosure string. That argument is partly right, and the
decomposition answers it by **shipping the cheap, high-value correction first and alone**, then earning
the contract in stages that each have an acting consumer.

1. **The disclosure correction (FR-13), alone.** Correct every emitter that claims a seat never ran on
   absent evidence — the panel fold, the dispatch result's own disclosure, and the receipt summary.
   Small, independently valuable, and it discharges the owner-visible harm without any new contract.
2. **The attestation on every terminal result (FR-1..FR-9, FR-14).** Producers, the observation schema
   with wrapper-minted/engine-asserted marking, the gradeable truth table, monotonic aggregation, the
   artifact-recovered fact (produced at D3 site 9), and the legacy normalizer. Consumers keep behaving
   as today.

   **This step opens a mixed-mode window, and the design states it rather than denying it.** From the
   moment producers ship until step 3 lands, the attestation exists while token-based consumers still
   infer — a vacuous result with an observed tool call can read `observed` on the result and still fold
   as not-run. That is the producer-first shape this design rejects *as a permanent state*, and it is
   unavoidable as a *transitional* one unless producers and readers land in a single commit. The
   window is therefore **explicitly versioned**: the attestation carries a contract version, a
   consumer states which version it honours, and the window is closed by step 3 rather than left to
   drift. A build that cannot close it in the same release should merge steps 2 and 3.
3. **The dispatch-result readers (part of FR-10).** The three consumers that genuinely receive dispatch
   results — the ledger stages, the probe's own computation, and forfeit attribution — read the
   attestation, and the ledger's single overloaded stage field is **split**: an action-facing value
   derived from observations, and a separately named salvage-tracking value that keeps the residue
   scan's answer. The round driver is **not** in this issue.
4. **The probe ruling (FR-11, UFR-3).** Vendor-scoped, invocation-bound, with a named consumer
   inventory: the ruling's producers and both of its readers must move together, and an unbindable
   ruling must land on the strict side.
5. **The round-driver leg (the rest of FR-10) — only if 2 and 3 prove out.** Route the attestation to
   the round driver through the authenticated provenance channel, never the seat payload. The
   record boundary and the panel fold must change **atomically, through one shared accessor**, because
   they spell the same predicate from opposite ends of one durable hop and either order alone breaks:
   one certifies a seat nobody reviewed, the other bricks the panel. This issue also owes an
   accept-both compatibility window for seat records written under either contract, since those records
   outlive the code version that wrote them.
6. **Retire the fallbacks and the dead names.** Remove the token archaeology once nothing reads it for
   this question — gated on FR-9's artifact-recovered fact being read, not merely on the token being
   unread. Wire or delete the unreferenced stage constants and uncalled helpers (D4).
7. **Doctrine.** The seven enumerated prose surfaces, with the clause-presence test kept green. Last,
   because doctrine describing a shape the code lacks is the drift this repo already pays for.

**Ordering:** 1 is independent and ships first. 2 precedes 3, 4, 5, 6. 5 is contingent. 7 is last.
**The owner-gate dead end** is an eighth, wholly independent issue.

**Rollback:** every step must be revertible against records written under the following step. That is
why 5 carries an accept-both window and why 2 preserves precedence rather than inheriting it.

## Open questions

- **Write-path evidence** — blocks write-side work, not this design's ratification. What constitutes
  observed action for a write dispatch? Each candidate is weaker than a tool-call observation, and one
  of them collides with an existing meaning of "delivered".
- **A codex-side action instrument (D6).** Today `not-observed` on a codex seat frequently means *no
  instrument*. Parsing codex's own tool/exec events would close the asymmetry. Worth its own
  assessment; not assumed here.
- **Whether step 5 is worth its cost.** Routing the attestation across the trust boundary is the
  largest piece of this work and the one the round driver's own design argues against. It is
  deliberately contingent, and a decision to stop after step 4 is a legitimate outcome.
- **The control probe's future trigger.** Recorded as visible and deliberately unspent: loosening a
  fail-closed posture is the owner's decision, not a consequence of better plumbing.

## Glossary

Every obvious word for these concepts is already taken in this repo; the renames are deliberate.

| Term | Meaning here | Why not the obvious word |
| --- | --- | --- |
| **Action** (`observed` / `not-observed`) | Whether we observed the seat acting | "engaged"/"unproven"/"activity" are all taken: `unproven` is already the vendor-liveness status meaning *no probe found*, in the same disclosures; and `activity` is the runner's word for byte-motion telemetry (`lastActivityAt`, `activityStream`) — the exact magnitudes FR-5 bars from the verdict |
| **Observation** | One entry supporting the verdict: what was seen, where, and whether wrapper-minted or engine-asserted | "evidence" is already a dict of *counts* on the probe result — the very magnitudes FR-5 bars |
| **Gradeable** | Whether a gradeable result reached us | "delivered" already means a count of declared paths on the write path, and a ledger stage with two derivations |
| **Probe ruling** | A vendor-scoped, invocation-bound conclusion from a control probe | "verdict" is taken by verifier verdicts |
| **Credit** | Whether a seat counts toward certification or panel composition | — |
| **Archaeology** | Reconstructing action by parsing outcome tokens and payload shape | — |

## Coverage

| Area | Disposition | Where / why |
| --- | --- | --- |
| Empty & first-run | Specify | UFR-1; FR-14 for results predating the contract |
| Invalid & malformed input | Specify | UFR-6 — an unrecognised entry is retained but does not count |
| Boundaries & limits | Specify | FR-5 — the observation/magnitude line; FR-8 — aggregation across attempts |
| Errors & failures | Specify | UFR-1, UFR-2, UFR-7 |
| Access & permissions | Specify | FR-12; and the trust-boundary section — the seat payload authenticates nothing |
| Duplicates & double-actions | Defer-to-build | Repeated probes for one vendor already aggregate fail-closed; the promise is that a repeat can only make a vendor's status stricter |
| Conflicting / simultaneous use | Specify | UFR-4 — observations and outcome disagreeing, resolved toward the weaker accurate claim |
| Misuse & abuse | Specify | FR-3 and the trust boundary — a seat may never self-attest; an engine-asserted entry is marked as such |
| Reach (i18n / a11y) | N-A | Internal machine contract with no human-language or interface surface |

## Rejected alternatives

- **A third verdict value meaning "provably inert".** Unsound: a negative probe cannot separate
  no-spawn from transport failure from delivery failure from absence of evidence, and is explicitly
  fail-closed on an outcome that proves the seat *did* act
  [cite: plugins/superheroes/lib/seat_canary.py § Fail-closed: artifact engaged but delivery failed].
- **Making the residue-shape heuristic an observation kind.** It measures resemblance, not action. It
  stays on the gradeable/outcome side as the artifact-recovered fact (FR-9).
- **Counting unrecognised observation entries** (the first draft's rule) — a fail-open that lets a
  malformed or claimant-influenced entry manufacture action.
- **Carrying the attestation to the round driver in the seat payload.** It would make a wrapper
  observation claimant-relayable, which is the self-attestation this design rejects.
- **A new module owning action.** Another home for a question that already has too many.
- **Shipping the contract before the disclosure correction.** The correction is the owner-visible value
  and needs none of the contract.
- **Producer-first or consumer-first decomposition as a *permanent* shape** — both leave readers
  permanently disagreeing. The transitional window between steps 2 and 3 is the unavoidable minimum,
  and it is versioned and closed rather than denied; what is rejected is treating that state as an
  acceptable resting place.
- **"Preserving the residue-scan precedence" in the ledger** — the first correction to this defect,
  and itself wrong: it would have kept two answers to one question permanently. The field is split
  instead.

## Amendments

**A2 (2026-08-14, round-2 confirmation).** The confirmation round found no Critical, and eight further
defects — six of them in A1's own corrections, which is what a confirmation round is for. The ledger
"preserve the precedence" fix would have kept two answers to one question permanently, so the field is
split instead; the step-2 producer window was denied rather than named, so it is now versioned and
bounded; the `activity` rename collided with the runner's byte-motion telemetry, so the verdict is
`action`; FR-11's model binding turned out to need trusted model provenance the round driver does not
have, which is now a stated prerequisite rather than an assumption; the trust-boundary claim was
overstated (a per-vendor probe landing already crosses it) and is narrowed to per-seat with the
existing channel named as the model; the gradeable table gained the abandoned/unreadable row; the
prose-surface enumeration gained `CONVENTIONS.md`; and D3 gained the token's producer and the dead
helper.

**A1 (2026-08-14, round-1 review).** The first draft proposed a third verdict value, asserted that an
engaged-artifact forfeit reads engaged, counted unrecognised evidence entries, claimed credit was
governed by delivery and outcome alone, and put the contract train ahead of the disclosure correction.
Four independent review seats — three doc-native lenses and one cross-vendor engine — converged on the
engaged-artifact contradiction; the credit-axes error and the trust-boundary limit were each found by
one seat and confirmed against the code. All five are corrected above, and the decomposition is
restructured so the cheap, high-value change ships first.
