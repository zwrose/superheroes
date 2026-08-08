# C7 — feat(superheroes): spec closure — the closure receipt and the owner's delivery decision

**Anchor:** spec `front-half-sdlc-core-6181ee` §Spec closure (FR-37, FR-38) + UFR-5, UFR-8, UFR-10 (second acceptance bullet — abandoned child) — owner-approved 2026-08-07.

**What:** Closure is never a separate process: the final child PR's vet assembles and
carries the closure receipt (R8's elements; the present-tense test; the advisor sequences
candidate closure moments so exactly one carries it; the no-PR-close edge presents it in
the same sitting) (FR-37); the owner accepts delivery on that receipt — full, or explicit
partial acceptance, or the spec stays open (FR-38, UFR-5); a failing validation run keeps
the spec open and mints repair issues anchored to the failing run's record, closure
re-riding the new last child (UFR-8); an abandoned child gets a re-plan or a park per R7,
never silence (UFR-10b).

**DoD:**
- Showrunner charter: the closure-rides-final-vet duty with the present-tense test and the
  sequencing-of-candidate-moments rule; the no-PR-close edge.
- R8's element list verbatim; absent elements named-with-why; the validation-run result
  stated in the receipt (app surfaces: executed test-pilot run; plugin/doctrine surfaces:
  conformance checks + one recorded rehearsal where an element needs a live run).
- FR-38: no silent close; partial delivery = explicit owner acceptance with
  delivered/deferred/declined named (UFR-5's bullet).
- UFR-8: repair issues carry receipt anchors to the failing run; the loop ends only at an
  owner decision.
- UFR-10b: abandoned-child re-plan-or-park duty per R7.

**Register text consumed (verbatim):**

> **R4 — Amendment classes.** Every post-approval spec amendment is classified `wording` (changes phrasing; decides nothing a builder could build differently against) or `substantive` (anything else — the default when ambiguous, failing closed), and every Amendments-log entry carries: date, owner stamp, class, and the section names it touched; a wording amendment's total ceremony is the body edit, the log entry, and mechanical propagation; a substantive amendment additionally triggers the touched-parts re-read (UFR-4) before injection.

> **R7 — The park surface.** A park note lands as a comment on the parked item's issue (or PR) **and** is named in the advisor's next delivery message to the owner; a park that reaches only one of the two is not an exit. Park notes carry what was elicited or found so far, explicitly marked unapproved.

> **R8 — Closure receipt elements.** The closure receipt enumerates exactly: coverage map complete; all other children merged with green vets; amendments reconciled (log read against R4's format); one end-to-end validation run against the current spec body with its result stated; aggregated Show-it items; delivered versus deferred/declined named — and an absent element is named with why.
