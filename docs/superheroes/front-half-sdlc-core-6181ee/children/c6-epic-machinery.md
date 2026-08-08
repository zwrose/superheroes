# C6 — feat(superheroes): decomposition + the epic contract — coverage map, register, package read, verbatim injection

**Anchor:** spec `front-half-sdlc-core-6181ee` §Spec handoff, decomposition, and the epic contract (FR-26..FR-36) + UFR-3, UFR-4, UFR-6, UFR-7 — owner-approved 2026-08-07, as-of amendment #3.

**What:** The advisor's decomposition machinery as charter + tooling: the spec-handoff vet
and fixed sequence with dated approval (FR-26); the acceptance-level coverage map (FR-27,
UFR-3); the contract register with decide-bys and the no-product-opinion rule (FR-28,
FR-29); seam-first sequencing (FR-30); verbatim register injection behavior around C9's landed invocations (R3: C9 owns the
whole FR-31 criterion; this child is a dependent); the WHOLE amendment machinery — FR-22
classification, the R4 log contract, and UFR-4 propagation, one behavior one owner
(round-2 consolidation); the
adversarial package read with scoped rounds, convergence rule, verification pass, audit
trail, and ceiling park (FR-32, UFR-7, using R5's weight vocabulary); post-approval-only
decomposition + substantive-amendment re-entry (FR-33, UFR-4 — reading R4's classes);
reciprocal cross-epic seams (FR-34); the child-PR register vet row (FR-35, UFR-6); the
single-issue fast path (FR-36).

**DoD:**
- Showrunner charter: FR-26's vet shape + fixed sequence; FR-27/28/29/30 duties; FR-33's
  post-approval rule and re-entry; FR-34 reciprocity; FR-35's vet row; FR-36 fast path.
- Filing and verification behavior built around C9's landed invocations (dependent — owns
  no FR-31 criterion).
- FR-22 whole: classification (wording vs substantive, fail-closed default), the R4 log
  contract (entry fields + positional numbering), and the wording path's bounded ceremony
  — with the RECORDED classification of one exercised amendment in the handback.
- FR-32's read protocol in the charter: five lenses, seat composition per the
  review-discipline independence rules (maker-family exclusion; advisor-as-author counts as
  the maker — spec amendment 2026-08-08), scoped rounds, the convergence rule
  (mechanical-only round ends it; authorship extends, re-flagging does not), the
  verification pass, the audit-trail element list, UFR-7's park per R7.
- FR-33's contradiction dispositions as charter text: a package-read spec contradiction
  resolves as a package fix, an owner-stamped spec amendment, or a recorded refutation in
  the audit trail — with an explicit no-silent-spec-edit vet rule.
- UFR-4 propagation duty, ALL elements: amended artifact + log first; unstarted children
  mechanically re-injected (register text) or re-checked against the coverage map (spec
  text); building children explicitly notified; a RECORDED coverage-map re-check after
  every affected spec amendment (exactly-once allocation re-verified); reciprocal-seam
  amendments propagate through BOTH homes (both registers, or register + stand-in issue
  body per FR-36) and both sides' affected children; substantive class triggers the
  touched-parts re-read. This child owns ALL propagation machinery — including the wording
  path's mechanical half (R4's consumer split; C5 owns classification and the log).
- One recorded end-to-end package rehearsal IN THIS CHILD'S HANDBACK (round-1 finding
  C14): a decomposition run producing map + register + quoted children, a package-read
  audit trail, exact-text check results, and a graded register vet row — artifacts
  included, not described.

**Register text consumed (verbatim):**

> **R3 — The exact-text check.** Register-to-child text agreement is checked by byte-exact comparison of each consumer artifact's quoted register block against the register file it names — an epic child's body against its epic's register, and a single-issue child's body standing in for a register (FR-36's shared-seam rule) against the epic register its quote header names; the check is machine work (a script with a stable invocation and a pass/fail result naming the first differing line), never model judgment; it runs at three points — child filing, child build intake, and the package read's verification pass. **C9 owns FR-31's acceptance criterion whole**: the script AND all three invocation points (the workhorse-intake line and the showrunner filing and verification lines are C9's charter edits); C2 and C6 are dependents that build behavior around the already-landed invocations, owning none of them. **Bootstrap (one-time, disclosed):** until C9 ships, the advisor performs the same byte-exact comparison with a recorded ad-hoc invocation — this package's own filings run under that bootstrap, with the invocation and results preserved in the package-read audit trail.

> **R4 — Amendment classes.** Every post-approval spec amendment is classified `wording` (changes phrasing; decides nothing a builder could build differently against) or `substantive` (anything else — the default when ambiguous, failing closed), and every Amendments-log entry carries: date, owner stamp, class, and the section names it touched; entries are ordered in the log and numbered by order of addition (oldest = 1) — the number is positional, not a new field — and R1's anchor cursor reads that order; a wording amendment's total ceremony is the body edit, the log entry, and mechanical propagation; a substantive amendment additionally triggers the touched-parts re-read (UFR-4) before injection.

> **R5 — The weight vocabulary.** A weight call names `light` or `full`, states its measurables (gradable-line count for a spec draft; child count and register-entry count for a package read), names a round ceiling when it governs a read loop, and may be overridden in either direction by one stated sentence; the numeric bars are guidelines, never gates.

> **R7 — The park surface.** A park lands the full park note — what was elicited or found so far, explicitly marked unapproved — on the owner's reading surface at park time: in the advisor's delivery message when the owner is present, else as the opening item of the advisor's next delivery message; a durable copy lands as a comment on the parked item's issue or PR, and the durable copy is for the record — it is never required owner reading.

> **R8 — Closure receipt elements.** The closure receipt enumerates exactly: coverage map complete; all other children merged with green vets; amendments reconciled — meaning the Amendments log is valid against R4's format AND UFR-4's propagation is verified: every affected child carried the amended text or an explicit notice, and the coverage map still allocates every acceptance criterion; one end-to-end validation run against the current spec body with its result stated; aggregated Show-it items; delivered versus deferred/declined named; and NFR conformance checked across the delivery (owner reading load, plain language, guidelines never hardened into gates) — an absent element is named with why.
