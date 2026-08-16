# C2 — feat(superheroes): the anchor invariant at all three layers — filing, build intake, vet

**Anchor:** spec `front-half-sdlc-core-6181ee` §The anchor invariant (FR-1..FR-4) + UFR-1, UFR-2, UFR-9 — owner-approved 2026-08-07, as-of amendment #4.

**What:** Make every build downstream of a decision the owner actually made, enforced at
three independent layers: the advisor records the anchor at filing (FR-1/FR-2, showrunner
charter); the builder confirms the anchor resolves before any spend, per-kind resolution
tests, stop-and-report on failure plus the advisor's repair half — re-anchor, re-route, or park
to the owner (FR-3/UFR-1, both charters); the vet flags
owner-perceivable new behavior no approved decision covers (FR-4/UFR-2, the one layer that
inspects the diff — a standing vet row). Plus the superseded-ruling notice duty (UFR-9):
when recording a superseding ruling the advisor notifies in-flight builds located by their
Anchor slots, checking open epics' registers for embedded copies.

**DoD:**
- Showrunner charter: anchor recorded at filing (FR-2's given/when/then as duty text).
- Workhorse charter: intake resolution with the three per-kind tests quoted from R1 —
  including the ordered as-of-amendment-number cursor test (entries numbered greater
  than the anchor's N, per R1/R4 — never date comparison); stop-and-report
  exercised once against a stale anchor with the RECORDED run in the handback (transcript
  or fixture + observed report — spec DoD's intake-stop leg): no file changed, report
  names what failed.
- Showrunner charter: the advisor's UFR-1 repair duty (re-anchor, re-route, or park to the
  owner) — the stop-report-repair flow graded as one path.
- Showrunner vet duty: the FR-4 standing row + UFR-2's plain-language flag, exercised once
  with the RECORDED verdict in the handback (spec DoD's vet-flag leg).
- UFR-9 notice duty in the showrunner charter (locate by Anchor slot; registers checked).
- Intake BEHAVIOR builds around C9's already-landed intake invocation (R3: C9 owns the
  whole FR-31 criterion; this child is a dependent and owns none of it).
- C2's charter edits write around R9's detective seam lines, never over them (R9's rule).

**Register text consumed (verbatim):**

> **R1 — The Anchor slot.** An issue's Anchor slot is a body section headed `Anchor (<kind>):` where `<kind>` is exactly one of `spec-section`, `receipt`, or `ruling` — the kind is declared in the header and is never inferred from the citation's prose — carrying exactly one anchor of the declared kind: a spec section (work-item + section heading + the anchor's as-of cursor: `as-of amendment #N`, where N is the count of entries in the spec's Amendments log at citation time, 0 when the log is empty), a receipt (a live link to a review finding, incident record, bug report, or gate result), or a dated owner ruling (date + where it was made) — and each kind resolves by its own test: a spec-section anchor resolves when the spec's owner approval is recorded (`status: approved` with its `approved:` date), the cited section exists in the current body, and no substantive-class Amendments entry numbered greater than the anchor's N names the cited section among its touched sections (wording-class entries never stale an anchor; entries are numbered by their order of addition to the log, oldest = 1, so same-day amendments stay ordered); a receipt anchor resolves when the link is live; a ruling anchor resolves when the dated, owner-attributed record is reachable where the ruling was made and no later owner decision supersedes it. A header that declares no kind, an unknown kind, or more than one kind is a malformed Anchor and blocks build-ready marking exactly as an empty Anchor does.

> **R2 — The issue skeleton.** Every routed issue body carries exactly three required sections in order — `Anchor (<kind>):` (the kind declared per R1), `What:`, `DoD:` — and nothing else is required; micro-route work is exempt; a routed issue missing a section is a vet finding, and an empty or malformed Anchor blocks build-ready marking while empty What/DoD do not block filing.

> **R3 — The exact-text check.** Register-to-child text agreement is checked by byte-exact comparison of each consumer artifact's quoted register block against the register file it names — an epic child's body against its epic's register, and a single-issue child's body standing in for a register (FR-36's shared-seam rule) against the epic register its quote header names; the check is machine work (a script with a stable invocation and a pass/fail result naming the first differing line), never model judgment; it runs at three points — child filing, child build intake, and the package read's verification pass — and it checks BOTH directions: every quoted block matches byte-exactly, and every entry whose Consumers line names the child is present in that child's body (a missing required quote fails the check the same as a drifted one). **C9 owns FR-31's acceptance criterion whole**: the script AND all three invocation points (the workhorse-intake line and the showrunner filing and verification lines are C9's charter edits); C2 and C6 are dependents that build behavior around the already-landed invocations, owning none of them. **Bootstrap (one-time, disclosed):** until C9 ships, the advisor performs the same byte-exact comparison with a recorded ad-hoc invocation — this package's own filings run under that bootstrap, with the invocation and results preserved in the package-read audit trail.

> **R4 — Amendment classes.** Every post-approval spec amendment is classified `wording` (changes phrasing; decides nothing a builder could build differently against) or `substantive` (anything else — the default when ambiguous, failing closed), and every Amendments-log entry carries: date, owner stamp, class, and the section names it touched; entries are ordered in the log and numbered by order of addition (oldest = 1) — the number is positional, not a new field — and R1's anchor cursor reads that order; a wording amendment's total ceremony is the body edit, the log entry, and mechanical propagation; a substantive amendment additionally triggers the touched-parts re-read (UFR-4) before injection.

> **R9 — The detective seam.** Cross-epic seam with the single-issue spec `the-detective-16c561`, recorded here under FR-36's shared-seam rule (the detective child's issue body quotes this entry verbatim and stands in for that side's register): the workhorse charter's diagnosis/fix boundary line (the workhorse never produces a diagnosis receipt) and the showrunner charter's five-check diagnosis-vet duty are the detective child's to land; C2, C3, and C6 (each an editor of those charter surfaces) write around the seam lines, never over them; landing order is free, but the later-landing PR rebases over the earlier and re-verifies the earlier's seam lines survive. The pre-ship routing transition lives where it was made: the detective spec's Assumptions section — this entry and R6 carry only this pointer, no transition semantics.
