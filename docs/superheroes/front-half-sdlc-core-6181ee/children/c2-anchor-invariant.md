# C2 — feat(superheroes): the anchor invariant at all three layers — filing, build intake, vet

**Anchor:** spec `front-half-sdlc-core-6181ee` §The anchor invariant (FR-1..FR-4) + UFR-1, UFR-2, UFR-9 — owner-approved 2026-08-07.

**What:** Make every build downstream of a decision the owner actually made, enforced at
three independent layers: the advisor records the anchor at filing (FR-1/FR-2, showrunner
charter); the builder confirms the anchor resolves before any spend, per-kind resolution
tests, stop-and-report on failure (FR-3/UFR-1, workhorse charter intake); the vet flags
owner-perceivable new behavior no approved decision covers (FR-4/UFR-2, the one layer that
inspects the diff — a standing vet row). Plus the superseded-ruling notice duty (UFR-9):
when recording a superseding ruling the advisor notifies in-flight builds located by their
Anchor slots, checking open epics' registers for embedded copies.

**DoD:**
- Showrunner charter: anchor recorded at filing (FR-2's given/when/then as duty text).
- Workhorse charter: intake resolution with the three per-kind tests quoted from R1;
  stop-and-report exercised once against a stale anchor (spec DoD's intake-stop leg) — no
  file changed, report names what failed.
- Showrunner vet duty: the FR-4 standing row + UFR-2's plain-language flag, exercised once
  (spec DoD's vet-flag leg).
- UFR-9 notice duty in the showrunner charter (locate by Anchor slot; registers checked).
- Intake also invokes R3's exact-text check where a child issue carries a register block.

**Register text consumed (verbatim):**

> **R1 — The Anchor slot.** An issue's Anchor slot is a body section headed `Anchor:` carrying exactly one of the three anchor kinds — a spec section (work-item + section heading), a receipt (a live link to a review finding, incident record, bug report, or gate result), or a dated owner ruling (date + where it was made) — and each kind resolves by its own test: a spec-section anchor resolves when the spec's frontmatter reads `status: approved` and no Amendments-log entry names the cited section as superseded; a receipt anchor resolves when the link is live; a ruling anchor resolves when the dated, owner-attributed record is reachable where the ruling was made and no later owner decision supersedes it.

> **R2 — The issue skeleton.** Every routed issue body carries exactly three required sections in order — `Anchor:`, `What:`, `DoD:` — and nothing else is required; micro-route work is exempt; a routed issue missing a section is a vet finding, and an empty Anchor blocks build-ready marking while empty What/DoD do not block filing.

> **R3 — The exact-text check.** Register-to-child text agreement is checked by byte-exact comparison of each child's quoted register block against the register file, and the check runs at three points: child filing, child build intake, and the package read's verification pass; the check is machine work (a script), never model judgment.
