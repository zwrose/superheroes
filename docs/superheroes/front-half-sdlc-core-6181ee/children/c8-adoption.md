# C8 — feat(superheroes): the adoption pass — pre-doctrine issues decided case by case

**Anchor:** spec `front-half-sdlc-core-6181ee` §Adoption (FR-40) — owner-approved 2026-08-07, as-of amendment #4.

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

> **R1 — The Anchor slot.** An issue's Anchor slot is a body section headed `Anchor (<kind>):` where `<kind>` is exactly one of `spec-section`, `receipt`, or `ruling` — the kind is declared in the header and is never inferred from the citation's prose — carrying exactly one anchor of the declared kind: a spec section (work-item + section heading + the anchor's as-of cursor: `as-of amendment #N`, where N is the count of entries in the spec's Amendments log at citation time, 0 when the log is empty), a receipt (a live link to a review finding, incident record, bug report, or gate result), or a dated owner ruling (date + where it was made) — and each kind resolves by its own test: a spec-section anchor resolves when the spec's owner approval is recorded (`status: approved` with its `approved:` date), the cited section exists in the current body, and no substantive-class Amendments entry numbered greater than the anchor's N names the cited section among its touched sections (wording-class entries never stale an anchor; entries are numbered by their order of addition to the log, oldest = 1, so same-day amendments stay ordered); a receipt anchor resolves when the link is live; a ruling anchor resolves when the dated, owner-attributed record is reachable where the ruling was made and no later owner decision supersedes it. A header that declares no kind, an unknown kind, or more than one kind is a malformed Anchor and blocks build-ready marking exactly as an empty Anchor does.

> **R2 — The issue skeleton.** Every routed issue body carries exactly three required sections in order — `Anchor (<kind>):` (the kind declared per R1), `What:`, `DoD:` — and nothing else is required; micro-route work is exempt; a routed issue missing a section is a vet finding, and an empty or malformed Anchor blocks build-ready marking while empty What/DoD do not block filing.

> **R6 — Route names and routing inputs.** The four intake routes are named `discovery`, `detective`, `build-ready`, `micro`, and their tests are FR-5's cases as amended: new product opinion or a genuine unknown (the spec-trigger test: *will this work produce sentences a vet could grade a PR against that no approved artifact contains yet?*) → `discovery`; "why did Y break" work meeting the detective spec's fire condition → `detective`; a repair of ratified behavior with a receipt anchor, or work under a recorded owner ruling → `build-ready`; a tiny owner-present item → `micro`, with probing-worthy micro work re-routing. These are JUDGMENT INPUTS, not a decision procedure: where more than one case matches, the route is the advisor's judgment call, recorded with the route and anchor at routing time (FR-5's overlap-resolution rule, owner-stamped amendment #4) — this register decides no precedence.
