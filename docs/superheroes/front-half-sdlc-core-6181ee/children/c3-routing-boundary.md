# C3 — feat(superheroes): four-route intake + the builder's side of the discovery boundary

**Anchor:** spec `front-half-sdlc-core-6181ee` §Routing at intake (FR-5, FR-6) + FR-11's routing acceptance + §The builder's side of the line (FR-39) — owner-approved 2026-08-07.

**What:** The advisor's intake becomes four named routes decided by R6's first-match order
— this child owns route selection EXCLUSIVELY, including FR-11's routing outcomes (a
recorded-ruling follow-up routes build-ready with no discovery step; a product question no
approved artifact answers routes discovery) — recording route + anchor and nothing more
at routing time (no size, lane, or review weight — FR-6); and the workhorse's needs-discovery inline elicitation is removed (FR-39):
the build entry point takes only routed, anchored issues and routes discovery-needing work
back rather than eliciting in-session. One boundary, both charters, one child.

**DoD:**
- Showrunner charter: the four routes with R6's first-match order verbatim; micro re-route
  rule stated; FR-11's two routing outcomes exercised once each (ruled follow-up →
  build-ready; unanswered product question → discovery).
- Routing records route + anchor only (FR-6's rule as charter text; review weight first
  appears on the spec draft).
- Workhorse charter: needs-discovery inline elicitation removed; discovery-needing work at
  the build entry is routed back (FR-39's bullet as the acceptance).
- The detective route names the detective spec's fire condition as the test it applies
  (cross-spec pointer, no restatement).
- C3's workhorse front-door edits write around R9's detective seam lines, never over them
  (R9's rule).

**Register text consumed (verbatim):**

> **R2 — The issue skeleton.** Every routed issue body carries exactly three required sections in order — `Anchor:`, `What:`, `DoD:` — and nothing else is required; micro-route work is exempt; a routed issue missing a section is a vet finding, and an empty Anchor blocks build-ready marking while empty What/DoD do not block filing.

> **R6 — Route names and the routing order.** The four intake routes are named `discovery`, `detective`, `build-ready`, `micro`, and the advisor decides exactly one by taking the FIRST matching case in this order: (1) a tiny owner-present item routes `micro` — and micro work that turns out to need probing re-routes through this order again with owner presence no longer deciding; (2) "why did Y break" work meeting the detective spec's fire condition routes `detective`; (3) work already covered by an approved artifact or a recorded owner ruling — including a repair of ratified behavior carrying a receipt anchor — routes `build-ready`; (4) work for which the spec-trigger test answers yes — *will this work produce sentences a vet could grade a PR against that no approved artifact contains yet?* — routes `discovery`. The order is the disambiguation: a case reached only when every earlier case declined.

> **R9 — The detective seam.** Cross-epic seam with the single-issue spec `the-detective-16c561`, recorded here under FR-36's shared-seam rule (the detective child's issue body quotes this entry verbatim and stands in for that side's register): the workhorse charter's diagnosis/fix boundary line (the workhorse never produces a diagnosis receipt) and the showrunner charter's five-check diagnosis-vet duty are the detective child's to land; C2 (vet duties) and C3 (workhorse front door) write around those lines, never over them; landing order is free, but the later-landing PR rebases over the earlier and re-verifies the earlier's seam lines survive; until the detective ships, "why did Y break" work routes `build-ready` (the detective spec's own assumption, quoted not invented).
