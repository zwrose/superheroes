---
superheroes: doc
schemaVersion: 1
docType: spec
workItem: the-detective-16c561
issue: null
size: small
status: approved
approved: "2026-08-07"
gates: {review: passed}
producedBy: "the-architect@0.24.0"
created: "2026-08-07"
updated: "2026-08-07"
---
# The detective

## Purpose

When something breaks and the *cause* is the valuable thing — not the fix — the plugin
today has no owner for that work: builders debug in service of a fix, and diagnosis quality
rides along uninspected. The detective is a dedicated observe-only role whose deliverable
is a demonstrated diagnosis, following the plugin's existing observe-only precedent
(test-pilot: a bug it finds is a finding, never an edit
[cite: plugins/superheroes/skills/test-pilot-execute/SKILL.md § a bug it finds is a finding];
guardian: it recommends; the advisor triages
[cite: plugins/superheroes/skills/guardian/SKILL.md § it recommends; the advisor triages]).
Ratified in the 2026-08-03 walkthrough (the map's detective section, with the name closed
in ledger ruling 9); this spec is its consolidation.

## Who it's for

- **The owner**, who gets a confirmed cause before money is spent on fixes aimed at
  symptoms.
- **The advisor**, who routes incidents and needs a vetted diagnosis before filing fix
  issues.

## Functional requirements

**FR-1.** The detective shall accept work meeting its fire condition — the diagnosis is
separately valuable: the cause is unknown, the blast radius is cross-cutting, or a first
fix already failed. An ordinary bug stays build-ready. (This spec owns the fire condition;
the advisor's four-route intake lives in the core spec, whose detective route applies this
test.)
  - *Acceptance:* Given a routine bug with an obvious receipt, when routed, then it goes
    build-ready and the detective is not involved; given a failed first fix, when the
    failure returns, then the rework routes to the detective.
  - *Acceptance (rule):* cause unknown = no receipt names the failing component;
    cross-cutting = the symptom appears on more than one surface, or the fix's scope cannot
    be named without investigation.
  - *Acceptance (rule):* the detective takes work from two front doors — the owner directly
    ("diagnose this") and advisor dispatch — and never routes through discovery.
  - *Acceptance (rule):* every dispatch through either front door names a budget for the
    diagnosis, in time or usage terms (UFR-3 stops the session when it is reached).

**FR-2.** The detective shall make no change to the surface under diagnosis — no edit to
its code, configuration, or data. Where demonstration requires toggling the suspected
factor, the toggle runs on a disposable copy the detective creates and discards.
  - *Acceptance (rule):* the examined surface is unchanged when the session ends, and any
    probe copies are discarded; a diagnosis session's contribution is information.

**FR-3.** The detective shall demonstrate a cause by reproduction or by A/B comparison,
never by inference from error text alone.
  - *Acceptance:* Given a hypothesis formed from an error message, when the receipt is
    written, then it carries the repro or A/B that confirmed the hypothesis — or says
    plainly that demonstration failed (UFR-1).

**FR-4.** When a diagnosis completes, the detective shall deliver a diagnosis receipt as a
comment on the incident issue, creating the incident issue if none exists; the receipt
states what happened (with receipts), the demonstrated root cause, the blast radius, and
recommended follow-ups.
  - *Acceptance (rule):* all four elements present, or the missing one is named with why.

**FR-5.** Before any fix is routed, the advisor shall vet the diagnosis: cause demonstrated
by repro or A/B; the recommended fix targets the cause, not the symptom; blast radius
stated; each follow-up carries the right anchor; no smuggled product opinion.
  - *Acceptance:* Given a diagnosis receipt, when vetted, then each of the five checks is
    graded and the verdict is recorded in plain language on the incident issue. When the
    owner asked for the diagnosis directly, the verdict also returns to them in-channel;
    an advisor-dispatched diagnosis adds no owner reading traffic (the owner-absent route).

**FR-6.** When the diagnosis vet passes, the advisor shall update the incident issue's body
to the confirmed cause and routing; comments remain the log.
  - *Acceptance:* Given a passed vet, when the body is read, then it states the confirmed
    cause top-to-bottom without needing the comment thread.

**FR-7.** Fix issues arising from a diagnosis shall cite the vetted diagnosis as their
receipt anchor.
  - *Acceptance (rule):* a fix issue filed from an unvetted diagnosis is a routing defect.

**FR-8.** The diagnosis/fix boundary shall hold on both sides: debugging in service of a
fix stays inside builds — this spec assigns that duty, and the workhorse charter gains the
matching boundary line (it never produces a diagnosis receipt) — and the detective never
produces a fix.
  - *Acceptance (rule):* no artifact exists that is both a diagnosis receipt and a fix.
  - *Acceptance (rule):* neither charter offers a flag, option, or mode that turns one role
    into the other.

**FR-9.** The detective shall never mint requirements: if a diagnosis surfaces new product
opinion, the advisor routes that opinion to discovery; it does not land in the receipt as a
requirement.
  - *Acceptance (rule):* a receipt sentence a vet could grade a PR against, contained in no
    approved artifact, is a smuggled-opinion vet finding (FR-5).

## When things go wrong (significant unhappy paths)

**UFR-1.** If the detective cannot demonstrate a cause — no reproduction and no A/B
distinguishes the hypotheses — then the receipt shall say so plainly, and the advisor shall
not route fix issues on an undemonstrated cause.
  - *Acceptance:* Given a failed demonstration, when the receipt is vetted, then the honest
    "not demonstrated" outcome passes the truthfulness check and no fix is routed on it.

**UFR-2.** If a fix becomes obvious mid-diagnosis, then the detective shall record it as a
recommended follow-up and shall not apply it.
  - *Acceptance:* Given an obvious one-line fix discovered during diagnosis, when the
    session ends, then the fix exists only as a follow-up recommendation in the receipt.

**UFR-3.** If a diagnosis stops converging — hypotheses exhausted, or the budget named at
dispatch reached — then the detective shall stop and deliver the not-demonstrated receipt
(UFR-1) naming what was ruled out, rather than continuing to spend on a route with no owner
present.
  - *Acceptance:* Given a diagnosis at its named budget with no demonstrated cause, when the
    budget is reached, then the session ends with the ruled-out list in the receipt — not
    with continued spend.
  - *Acceptance:* Given hypotheses exhausted before the budget, when none remains testable,
    then the session ends the same way — the ruled-out list in the receipt.

**UFR-4.** If the diagnosis vet fails any of the five checks, then the advisor shall return
the named failures to the detective for another pass — or park the incident — and no fix
issue shall be filed against that diagnosis until a re-vet passes.
  - *Acceptance:* Given a vet that finds the repro does not demonstrate the claimed cause,
    when the vet completes, then the incident holds the named failures (returned or parked)
    and no fix issue cites the failed diagnosis.

## Definition of done / success

- A recorded end-to-end rehearsal against one past incident produces, from artifacts alone:
  a diagnosis receipt carrying all four elements, a five-check vet verdict, an updated
  incident body, and a fix issue citing the diagnosis — with the examined surface untouched
  throughout.
- A recorded rehearsal (the same or a second) exercises one failure branch — a
  not-demonstrated exit (UFR-1) or a failed vet (UFR-4) — with the honest outcome visible
  in the artifacts.
- The shipped detective charter carries no edit affordance for the diagnosed surface, and
  the shipped workhorse charter carries the FR-8 boundary line — both verifiable by reading
  the charters.

## Assumptions & dependencies

- The routing route that sends work here is defined by the front-half SDLC core spec
  (work-item `front-half-sdlc-core-6181ee`), which applies this spec's fire condition; the
  two specs are independently shippable, and until this one ships, "why did Y break" work
  continues to route build-ready.
- The advisor's diagnosis-vet duty lands with this spec's charter work.

## Constraints

- The detective's charter is small: trigger, technique kernel, receipt shape, boundary
  rules, handoff to the advisor's vet — stated in its own words, with no dependency on any
  external skill pack.
- Observe-only is absolute on the surface under diagnosis; demonstration probes run on
  disposable copies (FR-2). The detective's only writes are the diagnosis comment and,
  where none exists, the incident issue (FR-4) — it never edits an issue body.

## Open questions

None — name, boundary, and technique were closed in the 2026-08-03 walkthrough (the map's
detective section; the name in ledger ruling 9).

## Glossary

- **Diagnosis receipt** — the detective's deliverable: what happened (with receipts),
  demonstrated root cause, blast radius, recommended follow-ups.
- **A/B demonstration** — confirming a cause by comparing behavior with and without the
  suspected factor, under otherwise identical conditions (the toggle on a disposable copy,
  per FR-2).
- **Blast radius** — everything the confirmed cause affects, stated so fix scope and
  urgency can be judged.

## Amendments

- **2026-08-08 (owner-stamped, wording):** recorded the approval date — the owner confirmed in the advisor channel that approval was given 2026-08-07 in the discovery sitting; added the `approved:` frontmatter field. Sections touched: frontmatter, Amendments. Decides nothing a builder could build differently against.

## Coverage

| Area | Disposition | Show-it? | Where / why |
| --- | --- | --- | --- |
| Empty & first-run | N-A | — | The role activates per-incident; there is no first-run state. |
| Invalid & malformed input | Specify | No | UFR-1 — an undemonstrable cause is reported honestly, never papered over. |
| Boundaries & limits | Specify | No | FR-1 bounds when the role fires; UFR-3 bounds how long it runs. |
| Errors & failures | Specify | No | UFR-1 (failed demonstration), UFR-4 (failed vet — returned or parked, never routed). |
| Access & permissions | Specify | No | FR-5/FR-6 — only the advisor vets and updates bodies; the detective writes comments only. |
| Duplicates & double-actions | N-A | — | Re-diagnosis of the same incident is ordinary advisor judgment. |
| Conflicting / simultaneous use | N-A | — | One incident, one diagnosis stream; no shared mutable surface. |
| Misuse & abuse | Specify | No | FR-9 — smuggled product opinion is a named vet finding; UFR-2 — fixes never slip in as edits. |
| Reach (i18n / a11y) | N-A | — | Internal role; no end-user surface. |
| Wording & tone | Specify | No | The receipt and verdict read in plain language on the incident issue (FR-4, FR-5). |
| Workflow shape | Specify | No | The FR-1 → FR-7 pipeline is the workflow: fire → observe → demonstrate → receipt → vet → body update → anchored fixes. |
| Placement & prominence | Specify | No | Receipts are comments on the incident issue; the confirmed cause lives in the body (FR-6). |
| Limits & defaults | Specify | No | UFR-3 — the dispatch names the budget; reaching it ends the session honestly. |
| Tier & access boundaries | Specify | No | Two front doors only (owner-direct, advisor dispatch — FR-1); vet authority is the advisor's (FR-5). |
| Visibility & disclosure | Specify | No | FR-5 scopes owner traffic: owner-direct verdicts return in-channel; advisor-dispatched ones add none. |
