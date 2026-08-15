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
result says so plainly. Every part of the system that needs the answer works it out for itself, by
reading the shape of whatever came back and drawing a conclusion. Three separate builds hit the same
wall doing this, and the machinery that exists to compensate — the planted-defect control probe —
costs a whole extra engine dispatch every time we want an honest answer.

This design makes that answer **a stated fact carried in the result**, rather than something each
consumer reconstructs. It is a change to how the answer is *represented and read*, not a change to
what we require of a seat: no new refusal, no new gate, no seat held to a higher bar than today.

The value is narrow and concrete: **the same question stops getting four different answers.** Today
one result object can simultaneously say the seat acted and say the seat never ran — and both
statements ship, to different readers, from the same dispatch. That is the specific thing this design
ends.

## Who it's for

- **The owner**, who reads a build's disclosures and needs "this seat never ran" to mean what it says.
  Today that phrase is sometimes an overstatement of what we actually observed.
- **The advisor**, who vets builds from their artifacts and must be able to tell a seat that did
  nothing from a seat whose work our transport dropped — a distinction that changes whether a review
  happened.
- **The builder session**, which today must know which of several inference rules applies to whichever
  surface it is reading, and gets it wrong in ways that survive into review.
- **The maintainer of the dispatch machinery**, for whom every new outcome token is currently a
  fall-open risk across a scattered set of consumers.

## What is true today

This section is the grounded analysis the rest of the design rests on. Everything in it was read from
the code, not inferred from the issue.

### Engagement is already a first-party primitive — it is just not carried, and not read

There is a single, well-reasoned home for the question. It is action-based: a finding returned, an
accepted investigated path, or a tool call observed. It deliberately refuses to conclude inaction from
absence of evidence
[cite: plugins/superheroes/lib/engine_adapter.py § NEVER returns "inert"], and it deliberately
excludes token spend and wall time, on measured grounds — a genuinely engaged clean review spent 2,460
tokens while a known-vacuous seat spent roughly ten times more
[cite: plugins/superheroes/lib/engine_adapter.py § Token spend cannot separate engaged from vacuous].
That reasoning is sound and this design keeps all of it.

The problem is everything around it. Five defects, stated precisely.

**D1 — the attestation is not carried on every terminal result.** It is *absent* on an `unrunnable`
refusal and *present with the value `null`* on timeout, refusal, and nonzero-exit forfeits — a shape
the reference documents as a trap for consumers
[cite: plugins/superheroes/skills/workhorse/reference/dispatch-mechanics.md § is **unsafe**]. A
consumer that cannot read the field uniformly must fall back to reasoning about `reason` tokens. That
fallback is the payload archaeology this work exists to retire.

**D2 — the specimen: one result, two contradictory answers.** This is the sharpest statement of the
defect, and it reproduces from the code alone. On the vacuous branch, the runner attaches an
engagement block whose `read` is computed over `{findings: [], investigated: None, engagement:
<telemetry>}` [cite: plugins/superheroes/lib/engine_dispatch.py § _engagement_with_read]. A seat with
at least one observed tool call therefore ships `reason: "vacuous"` **and** `engagement.read:
"engaged"` **in the same object**. The panel then reads neither: it classifies the seat from `vacuous`
or a not-run reason token, and discloses it as
[cite: plugins/superheroes/lib/round_driver.py § classed as never-ran]. So the system observed the
seat acting, recorded that observation, and then told the owner it never ran.

The defect is **not** that we lack a third value for "provably inert". It is that **the consumer
ignores the attestation entirely and lets outcome tokens overwrite it.**

**D3 — the inference is spread across five sites, not one.** Beyond the panel fold, the durable-record
boundary independently decides ran-vs-not-ran from the same reason tokens
[cite: plugins/superheroes/lib/round_adapters.py § _apply_predicate]; the ledger derives its own
engaged and delivered values by a third rule
[cite: plugins/superheroes/lib/engine_dispatch.py § _ledger_stages]; the control probe computes its
verdict from the outcome token first and only then consults the shared classifier
[cite: plugins/superheroes/lib/seat_canary.py § Fail-closed: artifact engaged but delivery failed];
and a separate residue-shape heuristic carries its own independent `engaged` flag whose own contract
admits a long error dump can score positive
[cite: plugins/superheroes/lib/engine_adapter.py § a long engine error dump]. Five mechanisms, one
word.

**D4 — the two axes exist in name only.** The vocabulary module declares stage names for the two
questions [cite: plugins/superheroes/lib/dispatch_outcome.py § STAGE_ENGAGED], and the reference
states plainly that they are two variables
[cite: plugins/superheroes/skills/workhorse/reference/dispatch-mechanics.md § Engaged vs delivered are two variables].
But no producer or consumer references those constants — every site uses raw string keys — and two
neighbouring helpers in the same module have no call sites at all. The names exist as if they were a
contract seam; they are not wired to anything.

**D5 — the write path has no attestation at all.** Write dispatches build no engagement block
[cite: plugins/superheroes/lib/engine_dispatch.py § _grade_write_attempt]. Their ledger stage is
derived from whether the run succeeded or produced a salvage block — a structurally different
measurement wearing the same name as the review path's.

### What is *not* a defect, and must survive

Two things resemble the above and are not instances of it.

- **Audit-collection provenance is authorization, not engagement.** The audit fold authenticates a
  clearing ruling against the vendor the orchestrator recorded dispatching
  [cite: plugins/superheroes/lib/audits.py § apply_audit_results]. It answers *which seat was this*,
  never *did it act*. An engagement attestation must not absorb or weaken it: an engaged but
  misrouted auditor must still fail to discharge a finding.
- **The engaged-artifact forfeit is deliberately never credited.** A seat that demonstrably produced a
  review our transport could not carry is a forfeit, its findings usable only under independent
  verification, and the seat itself is not counted toward panel composition. That rule is doctrine
  [cite: plugins/superheroes/rubric/review-discipline.md § Salvage valve], and a naive "consumers read
  engagement uniformly" migration would break it by turning an engaged forfeit into a run.

## Functional requirements

**FR-1.** The system shall carry an engagement attestation on every **terminal** review-dispatch
result, with no exceptions for refusals or forfeits.
  - *Acceptance (rule):* for every terminal reason the runner can return, the result carries an
    `engagement` object that is neither absent nor `null`.

**FR-2.** The system shall express the attestation's verdict as exactly two values — `engaged` and
`unknown` — and shall never express a third value asserting proven inaction.
  - *Acceptance (rule):* `unknown` means *we did not observe action*, never *the seat did nothing*.
    No code path produces any other value for this field.

**FR-3.** The system shall record, alongside the verdict, the **evidence that produced it** as a list
of named entries, each naming both what was observed and where it was observed.
  - *Acceptance (Given-When-Then):* Given a seat that returned findings and had tool calls observed in
    its stream, when the result is folded, then the evidence list carries one entry naming the
    findings (observed by the wrapper) and one naming the tool calls (observed in the engine stream) —
    not a single scalar source.

**FR-4.** The system shall make the verdict a function of the recorded evidence alone: when the
evidence list is empty the verdict is `unknown`, and when it is non-empty the verdict is `engaged`.
  - *Acceptance (rule):* the verdict can be recomputed from the evidence list by any reader and always
    agrees with the recorded verdict.

**FR-5.** The system shall never allow a telemetry **magnitude** — tokens spent, bytes of output,
seconds elapsed — to produce or change the verdict.
  - *Acceptance (rule):* no magnitude appears as an evidence entry. Magnitudes are carried for human
    diagnosis only. A tool call *observation* is evidence; the tool-call *count* is a magnitude
    reported beside it.

**FR-6.** The system shall carry a **delivery** answer beside the engagement answer, stating whether a
gradeable result reached us, and shall define it independently of the outcome token.
  - *Acceptance (rule):* delivery is stated normatively for each case — a graded success, a parsed
    result that failed the investigation floor, a structured engine refusal, an item-check failure,
    and a salvaged artifact — rather than inferred from what `reason` happens to say.

**FR-7.** The system shall state, for a **non-terminal** result, that the attestation is a snapshot
and not a final answer.
  - *Acceptance (rule):* a `running` result either omits the attestation entirely or marks it
    explicitly as provisional; a reader can never mistake a partial snapshot for a settled verdict, and
    absence is never something a consumer must interpret.

**FR-8.** The system shall express a control probe's result as a **separate verdict about a vendor**,
bound to the probe invocation that produced it, and shall never write a probe's conclusion into
another dispatch's attestation.
  - *Acceptance (Given-When-Then):* Given a probe run against a vendor, when a panel seat of that
    vendor is folded, then the probe's verdict is consumed as a vendor-scoped signal carrying its own
    provenance, and the seat's own attestation still reports only what that seat's dispatch showed.

**FR-9.** The system shall have consumers **read** the attestation rather than re-derive it, while
leaving credit decisions — certification, panel composition, fallback, discharge — governed by
delivery and outcome.
  - *Acceptance (rule):* every consumer named in the migration inventory reads the attestation for
    activity and consults delivery/outcome for credit; the consumer decision matrix below is the
    normative statement, and no consumer re-implements the classifier.

**FR-10.** The system shall keep the audit leg's collection provenance as a **separate authorization
axis**, unchanged by this work.
  - *Acceptance (rule):* an engaged auditor whose vendor does not match the recorded independent
    auditor still fails to discharge its target.

**FR-11.** The system shall correct the disclosure wording so that a seat we did not observe acting is
described as **unproven**, not as one that never ran.
  - *Acceptance (rule):* no owner-facing disclosure claims a seat never ran on the strength of absent
    evidence alone. A probe-backed vendor verdict may still say more, and says so with its provenance.

**FR-12.** The system shall tolerate results produced before this contract existed, reading them
through a normalizer rather than failing or silently mis-reading them.
  - *Acceptance (Given-When-Then):* Given a stored terminal result from an older run with no
    attestation, when a consumer reads it, then it receives a well-formed attestation marked as
    reconstructed-from-legacy, and no consumer sees an absent or `null` field.

## When things go wrong (significant unhappy paths)

**UFR-1.** If a dispatch never spawns an engine at all, then the system shall report the attestation as
`unknown` with empty evidence — and shall not report it as proven inaction.
  - *Acceptance:* Given a refusal raised before any attempt, when the result is folded, then the
    verdict is `unknown`, the evidence list is empty, and delivery is false.

**UFR-2.** If a seat demonstrably produced a review that our transport could not carry, then the
system shall record the attestation as `engaged` with delivery false, and the consumer shall still
not credit the seat.
  - *Acceptance:* Given an engaged-artifact forfeit, when the panel folds it, then the seat is not
    counted toward panel composition and its salvaged findings require independent verification —
    identical to today's behaviour, now reached by reading two fields instead of matching a token.

**UFR-3.** If a control probe comes back not-engaged, then the system shall treat that as a **policy**
verdict about the vendor with its own provenance, and shall not convert it into a factual claim of
inaction about any individual seat.
  - *Acceptance:* Given a probe that returns not-engaged, when the round records it, then the record
    names the probe invocation, the vendor, and the failure class — because a negative probe cannot
    distinguish no-spawn from transport failure from delivery failure from absence of evidence, and a
    verdict that cannot separate those must not be stated as a fact about a seat.

**UFR-4.** If the evidence and the outcome token disagree — the specimen in D2 — then the system shall
record both and shall resolve the disclosure in favour of the **weaker, accurate** claim.
  - *Acceptance:* Given a result carrying evidence of action and a vacuous outcome, when it is
    disclosed, then it is described as delivering nothing gradeable, not as never having run.

**UFR-5.** If a stored result predates this contract, then the system shall present it through the
normalizer with its reconstructed status visible, and shall not let a reconstructed attestation stand
in for an observed one in any accounting.
  - *Acceptance:* Given a legacy row, when accounting reads it, then it is distinguishable from an
    observed attestation.

**UFR-6.** If a consumer encounters an evidence entry it does not recognise, then the system shall
treat the entry as valid evidence rather than discarding it.
  - *Acceptance:* Given an unknown evidence name, when the verdict is recomputed, then it still reads
    `engaged` — an unrecognised observation is still an observation, and this is what keeps a future
    evidence kind from silently reclassifying seats.

## The consumer decision matrix

This is the normative answer to *what changes when a consumer reads the attestation*. It is the
section that prevents "consumers read the field uniformly" from breaking the salvage rule.

**Engagement records activity. Delivery and outcome govern credit.** The two are read together; neither
is read alone.

| Case | Engagement | Delivery | Credit toward certification | Owner-facing description |
| --- | --- | --- | --- | --- |
| Findings returned | `engaged` | true | Yes | reviewed, with findings |
| Empty findings, investigation record accepted | `engaged` | true | Yes | reviewed, clean |
| Empty findings, investigation floor failed, no other evidence | `unknown` | false | **No** | delivered nothing gradeable; activity unproven |
| Empty findings, investigation floor failed, tool calls observed | `engaged` | false | **No** | delivered nothing gradeable; the seat was observed acting |
| Engaged artifact our transport could not carry | `engaged` | false | **No** | produced a review we could not carry; findings need independent verification |
| Timeout / nonzero exit / refusal after an attempt | `unknown` | false | **No** | no gradeable result; activity unproven |
| No attempt spawned | `unknown` | false | **No** | never dispatched |

Two rows are the whole point of the table. The fourth row is today's silent contradiction, now stated
honestly: **the credit decision does not change** — the seat still does not count — but the
description stops overclaiming. The fifth row is the doctrine that a naive migration would have
broken: engaged and still not credited.

## Before and after — what actually changes

Required so that "this adds no new refusal" is demonstrable rather than asserted, against the standing
bar on new honesty gates
[cite: LEDGERS.md § No new honesty/grounding gates without a named escape] and on hardening beyond the
incident record [cite: LEDGERS.md § No fail-closed hardening beyond the last observed incident].

| Decision | Today | After | Changed? |
| --- | --- | --- | --- |
| Does a vacuous seat count toward certification? | No | No | **No** |
| Does an engaged-artifact seat count? | No | No | **No** |
| Does a clean seat with an accepted investigation record count? | Yes | Yes | **No** |
| Does a not-engaged probe downgrade that vendor's empty seats? | Yes | Yes | **No** |
| Is the light/micro control probe still mandatory on every review? | Yes | Yes | **No** |
| Does the investigation floor still forfeit an unproven empty seat? | Yes | Yes | **No** |
| Does an unauthenticated auditor still fail to discharge? | Yes | Yes | **No** |
| How is a seat we did not observe acting *described*? | "classed as never-ran" | "activity unproven" | **Yes — wording only** |
| How does a consumer *learn* a seat's status? | Matches outcome tokens, per surface | Reads the attestation and delivery | **Yes — mechanism** |
| Can two readers of one result disagree? | Yes (the D2 specimen) | No | **Yes — the defect closes** |

**No row adds a refusal, tightens a bar, or withholds a certification that is granted today.** The only
behavioural deltas are a wording correction and the removal of an inconsistency. This is a
representation change, and the table is how a reviewer checks that claim rather than taking it.

## The owner-gate dead end (the folded rider) — honestly re-diagnosed

The issue folds in a reachable state with no legal next move: a session that has taken one
advance-driven fold, arriving at an owner gate the calibration cannot authorize, can neither advance
(the gate parks without folding) nor hand-submit (the session-mode fence refuses). The state persists
with no move available from either entry point.

**The rider is real, and this design does not fix it.** None of the three paths involved reads an
engine result or an engagement value; the collision is between a session-wide interleave fence and an
owner-only phase. It belongs to the same *class* — a condition inferred from latches rather than
represented as data — which is why it was folded here, but an engagement attestation cannot make it
unrepresentable.

Stating that plainly is the useful contribution. The resolution it actually needs is a state-machine
one: an owner-gate transition that is legal for advance-driven sessions, so that authorization failure
leaves at least one move available rather than closing both. That is named here as a **separate build
issue**, sized and scoped on its own terms, and deliberately not smuggled into the engagement work
where it would ride on an unrelated migration.

## Non-functional requirements

- **No added dispatch cost.** The attestation is computed from evidence the runner already observes.
  This design adds no engine call. The control probe's cost is unchanged and is stated where it is
  incurred: a probe bounds its first attempt but a retry floors the wait, so worst case is materially
  longer than the nominal timeout — a fact the design records so that any future proposal to change
  the probe's trigger argues against the real number.
- **No weakening of an existing safeguard.** Every row of the before/after table that reads "No" is a
  safeguard preserved; a build that changes one has left this design's scope.
- **Reconstructable accounting.** A reader of a stored result can always tell an observed attestation
  from one reconstructed by the normalizer.

## Definition of done / success

The owner can read a build's disclosures and trust that "this seat never ran" is only said when we
have grounds to say it; the advisor can tell, from a result alone and without the builder's context,
whether a seat acted and whether anything gradeable arrived; and no surface of the dispatch machinery
re-implements that judgment for itself.

Concretely, the design is done when: the attestation is present and readable on every terminal review
result; the five inference sites named in D3 read it instead of deriving their own; the consumer
decision matrix holds with the credit column unchanged from today; and the disclosure wording no
longer overclaims.

## Assumptions & dependencies

- The existing classifier's reasoning — action-based, never magnitude-based, never concluding inaction
  from absence — is **kept**, not revisited. Its measured basis stands
  [cite: CONVENTIONS.md § Engine telemetry corroborates engagement but never substitutes for that record].
- The investigation-record floor is unchanged and remains the seat's own obligation
  [cite: plugins/superheroes/rubric/review-base.md § investigation record is a seat that never ran].
  Its *wording* is a candidate for the FR-11 correction; its *effect* is not.
- The control-probe obligation in single-reviewer lanes is unchanged by this work
  [cite: plugins/superheroes/rubric/review-discipline.md § review did not happen]. Any
  change to its trigger is a separate owner decision (see Open questions).
- Three prose surfaces carry the contract text today — the two engine references and the rubric — and
  a clause-presence test pins the probe wording across the charters. A doctrine change lands after the
  code, not before, and must keep that test green.

## Constraints

- **No new refusal, gate, or fail-closed path.** The standing ledger bars adding one absent a named
  escape that penetrated every existing layer, and bars hardening beyond the incident record. This
  design is bound by both, and the before/after table is the evidence.
- **The engaged-artifact seat is never credited.** Any migration that turns an engaged forfeit into a
  counted run has failed, regardless of how uniform its reads are.
- **Audit authorization is untouched.**
- **A new outcome value is a fall-open vector.** The existing literal-scan census does not prove
  consumer exhaustiveness; it prevents duplicate spellings. Anything that widens a value set needs a
  read/branch-site inventory and behavioural tests, landed atomically with the producer
  [cite: plugins/superheroes/lib/tests/test_dispatch_outcome_census.py § test_dispatch_outcome_census_clean].
  This design's decision to keep the verdict two-valued (FR-2) is what keeps that surface small.

## Out of scope

- **Write dispatches.** They carry no attestation today, and the evidence that would ground one — an
  accepted write report, declared-items delivery, an observed worktree effect — is a genuine open
  question, not an assumption. Phase one is review dispatches; the write path is decided on its own
  evidence before any write producer changes.
- The terminal-design questions already held elsewhere: stall-menu spend semantics, accept-risk
  eligibility, and the sticky-breaker criterion.
- Retiring or loosening the control probe.
- Fixing the owner-gate dead end, which is named as its own build issue above.

## Decomposition into build issues

Ordered as **expand then contract**, because a producer-first or consumer-first split recreates exactly
the silent seam this work exists to remove: a period where some readers see the attestation and others
still infer.

1. **Normalizer and tolerant readers first.** A single read-time accessor that returns a well-formed
   attestation for any result — new, legacy, or stored — and consumers taught to call it while still
   behaving exactly as they do today. Nothing observable changes. This is the compatibility contract
   (FR-12, UFR-5) and it lands alone.
2. **Producers.** The attestation constructed on every terminal review result, with evidence entries,
   sourced entries, and delivery defined normatively (FR-1, FR-3, FR-4, FR-5, FR-6, FR-7). Still no
   consumer behaviour change: the ledger's derivation becomes a read of the attestation rather than a
   second rule.
3. **Policy consumers.** The five inference sites migrate to reading it — the panel fold, the
   durable-record boundary, the ledger stages, the probe's own computation, and the residue-shape
   signal's confinement to salvage (FR-9), with the consumer decision matrix as the acceptance
   artifact and the credit column proven unchanged.
4. **Probe verdict separation.** The vendor-scoped probe verdict given its own provenance-bound shape,
   no longer folded into a per-result field (FR-8, UFR-3).
5. **Remove the fallbacks.** Delete the reason-token archaeology now that nothing reads it for this
   question; retire or wire the dead stage constants and the uncalled helpers (D4).
6. **Doctrine.** The prose surfaces updated to one contract, with the wording correction (FR-11) and
   the clause-presence test kept green.

Steps 1 and 2 are prerequisites for everything after them. Steps 4 and 5 are independent of each other
once 3 lands. Step 6 lands last, because doctrine that describes a shape the code does not yet have is
the drift this repo already pays for.

**The owner-gate dead end** is a seventh, independent issue, sharing nothing with the six above.

## Open questions

- **Write-path evidence (blocks any write-side work, not this design's ratification).** What
  constitutes observed action for a write dispatch? Candidates: an accepted write report, declared-items
  delivery evidence, or an observed worktree effect. Each is weaker than the review path's tool-call
  observation, and one of them — declared-items delivery — already uses the word "delivered" for a
  different thing, which is a naming collision to resolve before it ships.
- **The control probe's future trigger.** Once activity is legible per-dispatch, a narrower probe
  trigger becomes *arguable* in the full lane. This design does not argue it: the probe's value is that
  it is the only thing that can speak to a vendor's liveness at all, and loosening a fail-closed
  posture is the owner's decision, not a consequence of better plumbing. Recorded so the option is
  visible, and deliberately left unspent.
- **Whether the disclosure wording correction (FR-11) is worth its cost.** It makes some disclosures
  read weaker while being more accurate. That is the one owner-facing trade in this design.

## Glossary

| Term | Meaning here |
| --- | --- |
| **Engagement** | Whether we observed the seat taking action. Never a claim about what it did *not* do. |
| **Evidence entry** | One named observation supporting the verdict, carrying what was seen and where it was seen. |
| **Delivery** | Whether a gradeable result reached us. Independent of engagement in both directions. |
| **Credit** | Whether a seat counts toward certification or panel composition. Governed by delivery and outcome, never by engagement alone. |
| **Unproven** | We did not observe action. Not a claim that none occurred. Replaces "never ran" where only absence of evidence supports it. |
| **Probe verdict** | A vendor-scoped, provenance-bound policy conclusion from a control probe. Not a fact about any individual seat. |
| **Archaeology** | Reconstructing engagement by parsing outcome tokens and payload shape — the practice this design retires. |

## Coverage

| Area | Disposition | Where / why |
| --- | --- | --- |
| Empty & first-run | Specify | UFR-1 — no attempt spawned; and FR-12 for results predating the contract |
| Invalid & malformed input | Specify | UFR-6 — an unrecognised evidence entry is honoured, not discarded |
| Boundaries & limits | Specify | FR-5 — magnitudes may never move the verdict; the boundary is the evidence/magnitude line itself |
| Errors & failures | Specify | UFR-1, UFR-2 — refusals, forfeits, and transport failure each get a defined attestation |
| Access & permissions | Specify | FR-10 — audit authorization stays a separate axis and is not absorbed |
| Duplicates & double-actions | Defer-to-build | Repeated probe invocations against one vendor already have a fail-closed aggregation rule; the promise is that a repeat can only make a vendor's status stricter, never looser |
| Conflicting / simultaneous use | Specify | UFR-4 — the case where evidence and outcome disagree, resolved toward the weaker accurate claim |
| Misuse & abuse | Specify | FR-8 and the rejected alternative below — a seat may never self-attest engagement; attestation is observed, never claimed |
| Reach (i18n / a11y) | N-A | Internal machine contract with no human-language or interface surface |

## Rejected alternatives

- **A third verdict value meaning "provably inert".** Unsound against the only instrument that could
  mint it: a negative probe cannot distinguish no-spawn from transport failure from delivery failure
  from absence of evidence, and it is explicitly fail-closed on an outcome that proves the seat *did*
  act [cite: plugins/superheroes/lib/seat_canary.py § Fail-closed: artifact engaged but delivery failed].
  A value that cannot be honestly minted must not exist.
- **A new module owning engagement.** A sixth home for a word that already has five. The defect is
  dispersion.
- **Engines self-attesting engagement in their output.** Claimant-controlled, and exactly the input the
  audit leg already refuses to trust. Attestation is observed by the wrapper.
- **Making the residue-shape heuristic an evidence kind.** It measures resemblance, not action; its own
  contract admits an error dump can score positive. It stays confined to salvage.
- **Extending the existing literal-scan census to cover the migration.** It proves no consumer
  exhaustiveness. Named as a constraint above rather than relied on.
- **Producer-first or consumer-first decomposition.** Both create a window in which some readers see
  the attestation and others still infer — the seam this work removes.

## Amendments

*(None — initial draft.)*
