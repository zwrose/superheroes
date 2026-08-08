# C8 — feat(superheroes): the adoption pass — pre-doctrine issues decided case by case

**Anchor:** spec `front-half-sdlc-core-6181ee` §Adoption (FR-40) — owner-approved 2026-08-07.

**What:** The one-time-per-project pass that brings a board under the doctrine: the advisor
surfaces every open pre-doctrine issue to the owner and each is decided case by case —
re-anchored (per R1's kinds), re-routed (per R6's names), or closed — with each decision
recorded on the issue as a dated ruling; completion recorded with the project's
calibration. Ratified prior adoption arrangements (closed lists recorded with that
project's advisor seat) are kept; everything else takes the pass. No automatic conversion
(owner-ruled 2026-08-07, recorded in zwrose/superheroes#873).

**DoD:**
- Showrunner charter (or configure surface — builder's call, disclosed): the adoption-pass
  duty with the three per-issue outcomes and the dated-ruling record on each issue.
- Completion recorded with the project's calibration (the store carries the pass-done
  marker; both storage modes honored).
- The grandfather rule stated: prior ratified arrangements keep; the pass governs the rest.

**Non-goals:** this project's own adoption pass — the child ships the machinery; running
the pass here is an advisor action after the epic merges.

**Register text consumed (verbatim):**

> **R1 — The Anchor slot.** An issue's Anchor slot is a body section headed `Anchor:` carrying exactly one of the three anchor kinds — a spec section (work-item + section heading + the anchor's as-of date: the date of the spec's newest Amendments entry at citation time, or the spec's approval date when the log is empty), a receipt (a live link to a review finding, incident record, bug report, or gate result), or a dated owner ruling (date + where it was made) — and each kind resolves by its own test: a spec-section anchor resolves when the spec's owner approval is recorded (`status: approved` with its `approved:` date), the cited section exists in the current body, and no substantive-class Amendments entry dated after the anchor's as-of date names the cited section among its touched sections (wording-class entries never stale an anchor); a receipt anchor resolves when the link is live; a ruling anchor resolves when the dated, owner-attributed record is reachable where the ruling was made and no later owner decision supersedes it.

> **R2 — The issue skeleton.** Every routed issue body carries exactly three required sections in order — `Anchor:`, `What:`, `DoD:` — and nothing else is required; micro-route work is exempt; a routed issue missing a section is a vet finding, and an empty Anchor blocks build-ready marking while empty What/DoD do not block filing.

> **R6 — Route names and the routing order.** The four intake routes are named `discovery`, `detective`, `build-ready`, `micro`, and the advisor decides exactly one by taking the FIRST matching case in this order: (1) a tiny owner-present item routes `micro` — and micro work that turns out to need probing re-routes through this order again with owner presence no longer deciding; (2) "why did Y break" work meeting the detective spec's fire condition routes `detective`; (3) work already covered by an approved artifact or a recorded owner ruling — including a repair of ratified behavior carrying a receipt anchor — routes `build-ready`; (4) work for which the spec-trigger test answers yes — *will this work produce sentences a vet could grade a PR against that no approved artifact contains yet?* — routes `discovery`. The order is the disambiguation: a case reached only when every earlier case declined.
