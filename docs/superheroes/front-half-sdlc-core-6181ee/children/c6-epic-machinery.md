# C6 — feat(superheroes): decomposition + the epic contract — coverage map, register, package read, verbatim injection

**Anchor:** spec `front-half-sdlc-core-6181ee` §Spec handoff, decomposition, and the epic contract (FR-26..FR-36) + UFR-3, UFR-4, UFR-6, UFR-7 — owner-approved 2026-08-07.

**What:** The advisor's decomposition machinery as charter + tooling: the spec-handoff vet
and fixed sequence with dated approval (FR-26); the acceptance-level coverage map (FR-27,
UFR-3); the contract register with decide-bys and the no-product-opinion rule (FR-28,
FR-29); seam-first sequencing (FR-30); verbatim register injection with R3's machine check
— this child **owns and builds the checker** (the register's decide-by) — (FR-31); the
adversarial package read with scoped rounds, convergence rule, verification pass, audit
trail, and ceiling park (FR-32, UFR-7, using R5's weight vocabulary); post-approval-only
decomposition + substantive-amendment re-entry (FR-33, UFR-4 — reading R4's classes);
reciprocal cross-epic seams (FR-34); the child-PR register vet row (FR-35, UFR-6); the
single-issue fast path (FR-36).

**DoD:**
- Showrunner charter: FR-26's vet shape + fixed sequence; FR-27/28/29/30 duties; FR-33's
  post-approval rule and re-entry; FR-34 reciprocity; FR-35's vet row; FR-36 fast path.
- The R3 checker exists as machine work (script or lib), invoked at filing, intake, and
  the verification pass; exercised once each way (agree = pass, one-byte drift = fail).
- FR-32's read protocol in the charter: five lenses, seat composition per the
  review-discipline independence rules (maker-family exclusion; advisor-as-author counts as
  the maker — spec amendment 2026-08-08), scoped rounds, the convergence rule
  (mechanical-only round ends it; authorship extends, re-flagging does not), the
  verification pass, the audit-trail element list, UFR-7's park per R7.
- UFR-4 propagation duty: amended artifact + log first; unstarted children re-injected;
  building children notified; substantive class triggers the touched-parts re-read.

**Register text consumed (verbatim):**

> **R3 — The exact-text check.** Register-to-child text agreement is checked by byte-exact comparison of each child's quoted register block against the register file, and the check runs at three points: child filing, child build intake, and the package read's verification pass; the check is machine work (a script), never model judgment.

> **R4 — Amendment classes.** Every post-approval spec amendment is classified `wording` (changes phrasing; decides nothing a builder could build differently against) or `substantive` (anything else — the default when ambiguous, failing closed), and every Amendments-log entry carries: date, owner stamp, class, and the section names it touched; a wording amendment's total ceremony is the body edit, the log entry, and mechanical propagation; a substantive amendment additionally triggers the touched-parts re-read (UFR-4) before injection.

> **R5 — The weight vocabulary.** A weight call names `light` or `full`, states its measurables (gradable-line count for a spec draft; child count and register-entry count for a package read), names a round ceiling when it governs a read loop, and may be overridden in either direction by one stated sentence; the numeric bars are guidelines, never gates.

> **R7 — The park surface.** A park note lands as a comment on the parked item's issue (or PR) **and** is named in the advisor's next delivery message to the owner; a park that reaches only one of the two is not an exit. Park notes carry what was elicited or found so far, explicitly marked unapproved.

> **R8 — Closure receipt elements.** The closure receipt enumerates exactly: coverage map complete; all other children merged with green vets; amendments reconciled (log read against R4's format); one end-to-end validation run against the current spec body with its result stated; aggregated Show-it items; delivered versus deferred/declined named — and an absent element is named with why.
