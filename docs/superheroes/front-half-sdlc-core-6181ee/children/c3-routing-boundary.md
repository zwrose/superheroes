# C3 — feat(superheroes): four-route intake + the builder's side of the discovery boundary

**Anchor:** spec `front-half-sdlc-core-6181ee` §Routing at intake (FR-5, FR-6) + §The builder's side of the line (FR-39) — owner-approved 2026-08-07.

**What:** The advisor's intake becomes four named routes decided by the spec-trigger test
(R6), recording route + anchor and nothing more at routing time (no size, lane, or review
weight — FR-6); and the workhorse's needs-discovery inline elicitation is removed (FR-39):
the build entry point takes only routed, anchored issues and routes discovery-needing work
back rather than eliciting in-session. One boundary, both charters, one child.

**DoD:**
- Showrunner charter: the four routes with R6's test verbatim; micro re-route rule stated.
- Routing records route + anchor only (FR-6's rule as charter text; review weight first
  appears on the spec draft).
- Workhorse charter: needs-discovery inline elicitation removed; discovery-needing work at
  the build entry is routed back (FR-39's bullet as the acceptance).
- The detective route names the detective spec's fire condition as the test it applies
  (cross-spec pointer, no restatement).

**Register text consumed (verbatim):**

> **R2 — The issue skeleton.** Every routed issue body carries exactly three required sections in order — `Anchor:`, `What:`, `DoD:` — and nothing else is required; micro-route work is exempt; a routed issue missing a section is a vet finding, and an empty Anchor blocks build-ready marking while empty What/DoD do not block filing.

> **R6 — Route names and the spec-trigger test.** The four intake routes are named `discovery`, `detective`, `build-ready`, `micro`, and the routing test is the sentence: *will this work produce sentences a vet could grade a PR against that no approved artifact contains yet?* — yes routes to discovery; "why did Y break" work meeting the detective spec's fire condition routes to detective; a repair of ratified behavior with a receipt anchor, or work under a recorded ruling, routes build-ready; a tiny owner-present item routes micro, and micro work that turns out to need probing re-routes.
