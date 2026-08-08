# C1 — feat(superheroes): the issue contract — three-slot skeleton, anchor block, DoD bar (seam child)

**Anchor:** spec `front-half-sdlc-core-6181ee` §The issue contract (FR-7, FR-8, FR-9, FR-10) — owner-approved 2026-08-07.

**What:** Ship the issue contract every later child builds on: the three-slot skeleton in the
plugin's issue templates and charter text (showrunner duty 2/3 filing rules), the
build-ready block on an empty Anchor slot, the artifact-gradable DoD bar as a vet rule, and
the one-hop currency duty. This is the epic's seam child (FR-30): R1 and R2 become working
template text here before any consumer child builds against them.

**DoD:**
- The issue template(s) carry the three-slot skeleton; a routed issue missing a slot is a
  named vet finding in the showrunner charter's vet duty.
- Build-ready marking with an empty Anchor slot is refused (exercised once, recorded — the
  spec DoD's filing-refusal leg).
- The DoD bar (outcome, gradable from handback artifacts alone) is charter text with the
  activity-bullet counterexample.
- One-hop currency: charter text names the spot-check (issue body → approved anchor in one hop).
- Micro exemption stated where the skeleton is defined.

**Register text consumed (verbatim; R3's check grades this block):**

> **R1 — The Anchor slot.** An issue's Anchor slot is a body section headed `Anchor:` carrying exactly one of the three anchor kinds — a spec section (work-item + section heading), a receipt (a live link to a review finding, incident record, bug report, or gate result), or a dated owner ruling (date + where it was made) — and each kind resolves by its own test: a spec-section anchor resolves when the spec's frontmatter reads `status: approved` and no Amendments-log entry names the cited section as superseded; a receipt anchor resolves when the link is live; a ruling anchor resolves when the dated, owner-attributed record is reachable where the ruling was made and no later owner decision supersedes it.

> **R2 — The issue skeleton.** Every routed issue body carries exactly three required sections in order — `Anchor:`, `What:`, `DoD:` — and nothing else is required; micro-route work is exempt; a routed issue missing a section is a vet finding, and an empty Anchor blocks build-ready marking while empty What/DoD do not block filing.
