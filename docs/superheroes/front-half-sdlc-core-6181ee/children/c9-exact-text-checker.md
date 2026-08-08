# C9 — feat(superheroes): the exact-text checker — one script, three invocation points (seam child 2)

**Anchor:** spec `front-half-sdlc-core-6181ee` §Spec handoff, decomposition, and the epic contract, FR-31's machine-check rule — owner-approved 2026-08-07.

**What:** The standalone machine check R3 defines, extracted to its own small child (round-1
package-read finding B2: the checker was double-owned by C2 and C6). This child ships the
script — stable invocation, byte-exact comparison of a consumer artifact's quoted register
block against the register file its quote header names (epic child bodies, and single-issue
child bodies standing in for a register per FR-36's shared-seam rule), pass/fail result
naming the first differing line — and nothing else: C2 integrates it at build intake; C6
integrates it at filing and at the package read's verification pass. Lands right after C1,
before every integrating child.

**DoD:**
- The checker exists as machine work (script or lib entry point) with a documented
  invocation and result contract; exercised once each way — an agreeing block passes, a
  one-byte drift fails naming the first differing line.
- Handles both consumer shapes: an epic child body against its epic's register, and a
  single-issue child body (register quote with an epic-register header) against that
  register.
- No charter integrations in this child — the two integrating children own their own
  invocation points (R3's ownership split), and this child's script carries no knowledge
  of where it is invoked from.

**Register text consumed (verbatim):**

> **R3 — The exact-text check.** Register-to-child text agreement is checked by byte-exact comparison of each consumer artifact's quoted register block against the register file it names — an epic child's body against its epic's register, and a single-issue child's body standing in for a register (FR-36's shared-seam rule) against the epic register its quote header names; the check is machine work (a script with a stable invocation and a pass/fail result naming the first differing line), never model judgment; it runs at three points — child filing, child build intake, and the package read's verification pass.
