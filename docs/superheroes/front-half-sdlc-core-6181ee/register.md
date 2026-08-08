# Contract register — front-half-sdlc-core-6181ee

Cross-child technical decisions for the epic decomposition (FR-28). Numbered entries; each a
plain binding sentence with its consuming children named; owner rulings embedded as dated
copies pointing at their home; amendments dated. The advisor owns edits; a builder never
amends the register it is graded against. Children quote entry text **verbatim** (FR-31).

Children: C1 issue-contract seam · C2 anchor invariant · C3 routing + builder boundary ·
C4 discovery · C5 spec content + amendments · C6 epic machinery · C7 closure · C8 adoption ·
C9 exact-text checker.

---

**R1 — The Anchor slot.** An issue's Anchor slot is a body section headed `Anchor:` carrying exactly one of the three anchor kinds — a spec section (work-item + section heading + the anchor's as-of date: the date of the spec's newest Amendments entry at citation time, or the spec's approval date when the log is empty), a receipt (a live link to a review finding, incident record, bug report, or gate result), or a dated owner ruling (date + where it was made) — and each kind resolves by its own test: a spec-section anchor resolves when the spec's owner approval is recorded (`status: approved` with its `approved:` date), the cited section exists in the current body, and no substantive-class Amendments entry dated after the anchor's as-of date names the cited section among its touched sections (wording-class entries never stale an anchor); a receipt anchor resolves when the link is live; a ruling anchor resolves when the dated, owner-attributed record is reachable where the ruling was made and no later owner decision supersedes it.
*Owner ruling embedded:* the three anchor kinds and per-kind resolution tests are FR-1/FR-3 of the owner-approved spec (approved 2026-08-07, recorded in frontmatter); supersession readable from touched-section history is FR-3's own rule — the as-of-date mechanism operationalizes it using only what R4's log format records.
*Consumers:* C1 (mints the slot in templates), C2 (grades it at filing, intake, and vet), C8 (re-anchors pre-doctrine issues against it).

**R2 — The issue skeleton.** Every routed issue body carries exactly three required sections in order — `Anchor:`, `What:`, `DoD:` — and nothing else is required; micro-route work is exempt; a routed issue missing a section is a vet finding, and an empty Anchor blocks build-ready marking while empty What/DoD do not block filing.
*Consumers:* C1 (owns the template and the build-ready block), C2 (Anchor grading), C3 (routing fills the skeleton), C6 (epic children use the same skeleton plus the register-quote block), C8 (adoption pass grades pre-doctrine issues against it).

**R3 — The exact-text check.** Register-to-child text agreement is checked by byte-exact comparison of each consumer artifact's quoted register block against the register file it names — an epic child's body against its epic's register, and a single-issue child's body standing in for a register (FR-36's shared-seam rule) against the epic register its quote header names; the check is machine work (a script with a stable invocation and a pass/fail result naming the first differing line), never model judgment; it runs at three points — child filing, child build intake, and the package read's verification pass.
*Ownership split (decided):* **C9 owns and ships the checker** (the script, its invocation, its result contract); **C2 owns only the build-intake invocation** (workhorse charter); **C6 owns the filing and package-read-verification invocations** (showrunner charter). Each child's DoD grades only its own boundary.
*Consumers:* C9 (owns), C2 (intake integration), C6 (filing + verification integrations).

**R4 — Amendment classes.** Every post-approval spec amendment is classified `wording` (changes phrasing; decides nothing a builder could build differently against) or `substantive` (anything else — the default when ambiguous, failing closed), and every Amendments-log entry carries: date, owner stamp, class, and the section names it touched; a wording amendment's total ceremony is the body edit, the log entry, and mechanical propagation; a substantive amendment additionally triggers the touched-parts re-read (UFR-4) before injection.
*Owner ruling embedded:* classes ratified in the 2026-08-07 sitting (spec FR-22); first exercised by the 2026-08-08 approval-date wording amendment (log entries in both specs).
*Consumers:* C5 (owns the classification machinery + log format), C6 (UFR-4 propagation reads the class; implements all propagation, including the wording path's mechanical half), C7 (closure's amendments-reconciled element reads the log), C2 (anchor resolution reads entry dates, classes, and touched sections per R1).

**R5 — The weight vocabulary.** A weight call names `light` or `full`, states its measurables (gradable-line count for a spec draft; child count and register-entry count for a package read), names a round ceiling when it governs a read loop, and may be overridden in either direction by one stated sentence; the numeric bars are guidelines, never gates.
*Consumers:* C4 (owns — FR-16's spec-draft call), C6 (FR-32's package-read call reuses the vocabulary and adds the ceiling).

**R6 — Route names and the routing order.** The four intake routes are named `discovery`, `detective`, `build-ready`, `micro`, and the advisor decides exactly one by taking the FIRST matching case in this order: (1) a tiny owner-present item routes `micro` — and micro work that turns out to need probing re-routes through this order again with owner presence no longer deciding; (2) "why did Y break" work meeting the detective spec's fire condition routes `detective`; (3) work already covered by an approved artifact or a recorded owner ruling — including a repair of ratified behavior carrying a receipt anchor — routes `build-ready`; (4) work for which the spec-trigger test answers yes — *will this work produce sentences a vet could grade a PR against that no approved artifact contains yet?* — routes `discovery`. The order is the disambiguation: a case reached only when every earlier case declined.
*Consumers:* C3 (owns route selection, including the recorded-ruling and receipt-anchor build-ready outcomes), C8 (adoption pass re-routes against these names). *(Cross-spec note, not a consumer: the detective spec's FR-1 owns the fire condition case 2 applies.)*

**R7 — The park surface.** A park lands the full park note — what was elicited or found so far, explicitly marked unapproved — on the owner's reading surface at park time: in the advisor's delivery message when the owner is present, else as the opening item of the advisor's next delivery message; a durable copy lands as a comment on the parked item's issue or PR, and the durable copy is for the record — it is never required owner reading.
*Consumers:* C4 (discovery exits, UFR-10a), C6 (UFR-7 package-read park), C7 (UFR-10b abandoned-child park).

**R8 — Closure receipt elements.** The closure receipt enumerates exactly: coverage map complete; all other children merged with green vets; amendments reconciled — meaning the Amendments log is valid against R4's format AND UFR-4's propagation is verified: every affected child carried the amended text or an explicit notice, and the coverage map still allocates every acceptance criterion; one end-to-end validation run against the current spec body with its result stated; aggregated Show-it items; delivered versus deferred/declined named; and NFR conformance checked across the delivery (owner reading load, plain language, guidelines never hardened into gates) — an absent element is named with why.
*Consumers:* C7 (owns — FR-37), C6 (FR-36's single-issue path folds the applicable elements into that PR's vet).

**R9 — The detective seam.** Cross-epic seam with the single-issue spec `the-detective-16c561`, recorded here under FR-36's shared-seam rule (the detective child's issue body quotes this entry verbatim and stands in for that side's register): the workhorse charter's diagnosis/fix boundary line (the workhorse never produces a diagnosis receipt) and the showrunner charter's five-check diagnosis-vet duty are the detective child's to land; C2 (vet duties) and C3 (workhorse front door) write around those lines, never over them; landing order is free, but the later-landing PR rebases over the earlier and re-verifies the earlier's seam lines survive; until the detective ships, "why did Y break" work routes `build-ready` (the detective spec's own assumption, quoted not invented).
*Owner ruling embedded:* FR-36 shared-seam amendment, owner-ruled 2026-08-08 in the advisor channel (option (a)); recorded in the spec's Amendments log.
*Consumers:* C2, C3 (write around the seam lines), the detective child (quotes this entry; its side's register home).

---

## Amendments

- **2026-08-08 (round-1 fold):** R1 rewritten (faithful FR-3 semantics + as-of-date supersession — findings A1/B3); R3 rewritten (checker extracted to new child C9; ownership split — finding B2); R6 rewritten (first-match order restores exactly-one — finding A2); R7 rewritten (full note on the owner surface at park time — finding A3); R8 strengthened (reconciliation = propagation verified; NFR element added — findings A4/C13); R4 consumers extended (C2 per R1; C6 owns all propagation per finding C10); R9 added (detective seam under the FR-36 amendment — finding B1).
