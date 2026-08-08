# Contract register — front-half-sdlc-core-6181ee

Cross-child technical decisions for the epic decomposition (FR-28). Numbered entries; each a
plain binding sentence with its consuming children named; owner rulings embedded as dated
copies pointing at their home; amendments dated. The advisor owns edits; a builder never
amends the register it is graded against. Children quote entry text **verbatim** (FR-31).

Children: C1 issue-contract seam · C2 anchor invariant · C3 routing + builder boundary ·
C4 discovery · C5 spec content + amendments · C6 epic machinery · C7 closure · C8 adoption.

---

**R1 — The Anchor slot.** An issue's Anchor slot is a body section headed `Anchor:` carrying exactly one of the three anchor kinds — a spec section (work-item + section heading), a receipt (a live link to a review finding, incident record, bug report, or gate result), or a dated owner ruling (date + where it was made) — and each kind resolves by its own test: a spec-section anchor resolves when the spec's frontmatter reads `status: approved` and no Amendments-log entry names the cited section as superseded; a receipt anchor resolves when the link is live; a ruling anchor resolves when the dated, owner-attributed record is reachable where the ruling was made and no later owner decision supersedes it.
*Owner ruling embedded:* the three anchor kinds and per-kind resolution tests are FR-1/FR-3 of the owner-approved spec (approved 2026-08-07; recorded in the spec's frontmatter).
*Consumers:* C1 (mints the slot in templates), C2 (grades it at filing, intake, and vet), C8 (re-anchors pre-doctrine issues against it).

**R2 — The issue skeleton.** Every routed issue body carries exactly three required sections in order — `Anchor:`, `What:`, `DoD:` — and nothing else is required; micro-route work is exempt; a routed issue missing a section is a vet finding, and an empty Anchor blocks build-ready marking while empty What/DoD do not block filing.
*Consumers:* C1 (owns the template), C2 (Anchor grading), C3 (routing fills the skeleton), C6 (child issues of epics use the same skeleton with the register-quote block added), C8 (adoption pass grades pre-doctrine issues against it).

**R3 — The exact-text check.** Register-to-child text agreement is checked by byte-exact comparison of each child's quoted register block against the register file, and the check runs at three points: child filing, child build intake, and the package read's verification pass; the check is machine work (a script), never model judgment.
*Decide-by:* **C6 owns** where the checker lives (lib module vs script) and its invocation surface; C2 consumes its intake invocation; C6's package-read verification consumes it directly.
*Consumers:* C6 (owns + package read), C2 (build intake).

**R4 — Amendment classes.** Every post-approval spec amendment is classified `wording` (changes phrasing; decides nothing a builder could build differently against) or `substantive` (anything else — the default when ambiguous, failing closed), and every Amendments-log entry carries: date, owner stamp, class, and the section names it touched; a wording amendment's total ceremony is the body edit, the log entry, and mechanical propagation; a substantive amendment additionally triggers the touched-parts re-read (UFR-4) before injection.
*Owner ruling embedded:* classes ratified in the 2026-08-07 sitting (spec FR-22); first exercised by the 2026-08-08 approval-date wording amendment (log entries in both specs).
*Consumers:* C5 (owns the classification machinery + log format), C6 (UFR-4 propagation reads the class), C7 (closure's amendments-reconciled element reads the log).

**R5 — The weight vocabulary.** A weight call names `light` or `full`, states its measurables (gradable-line count for a spec draft; child count and register-entry count for a package read), names a round ceiling when it governs a read loop, and may be overridden in either direction by one stated sentence; the numeric bars are guidelines, never gates.
*Consumers:* C4 (owns — FR-16's spec-draft call), C6 (FR-32's package-read call reuses the vocabulary and adds the ceiling).

**R6 — Route names and the spec-trigger test.** The four intake routes are named `discovery`, `detective`, `build-ready`, `micro`, and the routing test is the sentence: *will this work produce sentences a vet could grade a PR against that no approved artifact contains yet?* — yes routes to discovery; "why did Y break" work meeting the detective spec's fire condition routes to detective; a repair of ratified behavior with a receipt anchor, or work under a recorded ruling, routes build-ready; a tiny owner-present item routes micro, and micro work that turns out to need probing re-routes.
*Consumers:* C3 (owns), C8 (adoption pass re-routes against these names). *(Cross-spec note, not a consumer: the detective spec's FR-1 owns the fire condition this test applies.)*

**R7 — The park surface.** A park note lands as a comment on the parked item's issue (or PR) **and** is named in the advisor's next delivery message to the owner; a park that reaches only one of the two is not an exit. Park notes carry what was elicited or found so far, explicitly marked unapproved.
*Consumers:* C4 (discovery exits, UFR-10a), C6 (UFR-7 package-read park), C7 (UFR-10b abandoned-child park).

**R8 — Closure receipt elements.** The closure receipt enumerates exactly: coverage map complete; all other children merged with green vets; amendments reconciled (log read against R4's format); one end-to-end validation run against the current spec body with its result stated; aggregated Show-it items; delivered versus deferred/declined named — and an absent element is named with why.
*Consumers:* C7 (owns — FR-37), C6 (FR-36's single-issue path folds the applicable elements into that PR's vet).

---

## Amendments

None yet — register drafted 2026-08-08, ahead of the package read.
