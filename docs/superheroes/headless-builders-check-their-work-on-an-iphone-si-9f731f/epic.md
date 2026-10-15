Anchor (spec-section): headless-builders-check-their-work-on-an-iphone-si-9f731f · the whole spec (Purpose, Functional requirements FR-1 to FR-21, When things go wrong UFR-1 to UFR-10, Definition of done / success) · as-of amendment #0 (owner-approved 2026-10-08, recorded in the spec's `approved:` field; discovery issue #1638)

What: The landing epic for headless builders checking their own work on a simulated iPhone. Four children land it:
- **C1, the launcher's phone (the seam).** A launch that asks for the iPhone check gets its own new phone, named on its launch record, handed to the builder, with Device Hub kept running.
- **C2, the pilot's iPhone check.** The builder drives that phone with AXe in Mobile Safari or the installed web app, takes screenshots and page readings, and posts evidence labelled with phone, model, iOS version, page, browser-or-installed and Simulator, plus honest "did not run" lines.
- **C3, the advisor's launch, vet and reap.** The advisor turns the check on when an issue asks for it, rules invalid evidence invalid, checks by hand when the evidence is incomplete, and deletes a finished lane's phones.
- **C4, the reporting-script guidance.** It says how a project adds its development-only reporting script, and keeps it out of real users' hands.

Consuming projects stay on today's behaviour until they adopt the release that carries the children, and even then only lanes launched with the iPhone check get a phone.

The decomposition artifacts live beside the stored spec in the project store (`docs/headless-builders-check-their-work-on-an-iphone-si-9f731f/`):
- `coverage-map.md`: 47 rows, each owned once (C1 8, C2 31, C3 6, C4 1, and the success definition as the closure's validation run);
- `register.md`: 7 entries the children quote verbatim;
- the child bodies as filed (`children/`);
- `package-read-audit.md`, written by the independent package read before the children file;
- `vet-record.md`, the advisor's breakdown vet with its file pins.

Sequencing (seam first; launches are the owner's word): wave 0 is C1; wave 1 is C2 and C3 in parallel, after C1; wave 2 is C4, after C2. The success definition (a real launched lane passing the 14 px test in Mobile Safari and then the installed app, then a reap that removes its phone and leaves other phones alone) runs as the epic's closure validation run, after the last child merges.

Owner capability: the owner installs AXe, the driver tool, on this Mac once, before C2 launches. It is not installed today.

DoD:
- Every child issue (C1 to C4) is closed by a merged PR with a green vet.
- The coverage map is complete: every row is owned by a closed child or by the closure validation run, re-checked after any amendment to the spec.
- Every register decide-by is resolved and recorded in the register with a dated note naming where it was decided: R1, R2 and R3 by C1; R5's layout and R6 by C2.
- The closure receipt (`skills/showrunner/reference/closure.md`) is posted on this issue. It carries coverage complete, children merged, amendments reconciled, the validation run's result (the success definition run live in a launched lane, then reaped), and the owner's delivery decision, presented with the last child's handback.

Routing: milestone **Test-pilot evidence you can act on** (the discovery issue #1638's milestone). Kind: `kind:product`. Area labels on the epic: `area:test-pilot`, `area:showrunner`. Each child carries the label that matches its surface: C1 and C3 `area:showrunner`, C2 and C4 `area:test-pilot`. Lane: full, per child. The children are native sub-issues of this epic, and each body carries its Anchor, What, DoD, sequencing, lane and presentation calls, size, and the register entries it consumes.
