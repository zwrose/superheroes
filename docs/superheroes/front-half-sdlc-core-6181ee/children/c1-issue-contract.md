# C1 — feat(superheroes): the issue contract — three-slot skeleton, anchor block, DoD bar (seam child)

**Anchor:** spec `front-half-sdlc-core-6181ee` §The issue contract (FR-7, FR-8, FR-9, FR-10) + FR-1's acceptance rule — owner-approved 2026-08-07, as-of amendment #4.

**What:** Ship the issue contract every later child builds on: the three-slot skeleton in the
plugin's issue templates and charter text (showrunner duty 2/3 filing rules), the
build-ready block — one gate covering both FR-8's empty-Anchor case and FR-1's
no-anchor-kind case — the artifact-gradable DoD bar as a vet rule, and the currency duty. This is the epic's seam child (FR-30): R1 and R2 become working
template text here before any consumer child builds against them.

**DoD:**
- The issue template(s) carry the three-slot skeleton; a routed issue missing a slot is a
  named vet finding in the showrunner charter's vet duty.
- Build-ready marking is refused for an empty Anchor slot AND for an Anchor citing none of
  the three anchor kinds — one gate, exercised once each way, recorded (the spec DoD's
  filing-refusal leg).
- The DoD bar (outcome, gradable from handback artifacts alone) is charter text with the
  activity-bullet counterexample.
- Currency: charter text names the spot-check as BOTH halves of FR-10's acceptance — the
  whole issue body matches the work's current state, and a build-ready issue's Anchor link
  resolves to the approved decision in one hop; a stale What/DoD fails the spot-check even
  when the anchor link resolves.
- Micro exemption stated where the skeleton is defined.
- The standing NFR vet row ships HERE (seam child — every later child's vet has it):
  charter text grading the three package-wide NFRs (owner reading load, plain language,
  guidelines never hardened into gates) at every child PR's vet.

**Register text consumed (verbatim; R3's check grades this block):**

> **R1 — The Anchor slot.** An issue's Anchor slot is a body section headed `Anchor:` carrying exactly one of the three anchor kinds — a spec section (work-item + section heading + the anchor's as-of cursor: `as-of amendment #N`, where N is the count of entries in the spec's Amendments log at citation time, 0 when the log is empty), a receipt (a live link to a review finding, incident record, bug report, or gate result), or a dated owner ruling (date + where it was made) — and each kind resolves by its own test: a spec-section anchor resolves when the spec's owner approval is recorded (`status: approved` with its `approved:` date), the cited section exists in the current body, and no substantive-class Amendments entry numbered greater than the anchor's N names the cited section among its touched sections (wording-class entries never stale an anchor; entries are numbered by their order of addition to the log, oldest = 1, so same-day amendments stay ordered); a receipt anchor resolves when the link is live; a ruling anchor resolves when the dated, owner-attributed record is reachable where the ruling was made and no later owner decision supersedes it.

> **R2 — The issue skeleton.** Every routed issue body carries exactly three required sections in order — `Anchor:`, `What:`, `DoD:` — and nothing else is required; micro-route work is exempt; a routed issue missing a section is a vet finding, and an empty Anchor blocks build-ready marking while empty What/DoD do not block filing.
