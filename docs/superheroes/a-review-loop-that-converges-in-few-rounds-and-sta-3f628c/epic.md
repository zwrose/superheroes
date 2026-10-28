**STATE:** spec approved 2026-10-27; breakdown drafted on the spec PR #2199 · this body replaces the discovery body of #2185 in place at filing · children file with the owner's merge word · not launched

Anchor (spec-section): a-review-loop-that-converges-in-few-rounds-and-sta-3f628c · the whole spec (Purpose; Functional requirements, FR-1 to FR-54; Significant unhappy paths, UFR-1 to UFR-8; Non-functional requirements; UI / UX; Definition of done / success) · as-of amendment #0 (owner-approved 2026-10-27, recorded in the spec's `approved:` field; spec PR #2199)

What: The landing epic for a review loop that converges in few rounds and stays simple. Today one PR in ten needs 9 or more review rounds, PRs reviewed in more than one session hold most review tokens, and the loop keeps stalling or losing sessions. After this epic, a full-lane review finds in round 1 what it will find, finishes in at most 4 rounds, has fewer moving parts that can stall, and keeps every independent check that makes it worth trusting. Four children land it:
- **C1, the core loop.** A native stack of thirteen layers, seam first: the review record; the grounding seat and the read-only and verify-less modes removed; the round driver's stops (a cap of 4, a handback with what is open, one extra audit round at the advisor's word, no stall menu); round 1's panel with read lists and the countable-line count; break-it tests the build session runs on the unfixed code; the verifier as the only judge of "wrong"; synthesis with repeat marks; the build session applying fixes itself; rounds 2 to 4 as fix audits and a scoped finder; a returning PR reviewed for what changed, on every lane; the vet's claim-by-claim check and its three choices at the cap; and the gardening pass's two revisit checks.
- **C2, big changes.** Slices by size instead of by folder, every unread part reviewed, one seams check, the premortem reviewer on the whole change.
- **C3, findings outside the PR.** Bugs on untouched lines go on the record's "Outside this PR" list, never block, and the advisor sorts them at the vet.
- **C4, copies of a bug.** Each finding names its kind of mistake and every place in the PR; a confirmed Important or Critical finding sets off one repository-wide search, inside hits graded by the verifier and outside hits listed.

The gardening-pass measure's count of the advisor's choices at the cap (the spec's FR-53) is built by #2189, not here; this epic records the choices it counts (register R9). The escape logging is #2190's; this epic logs false PR claims beside escapes (R11). Consuming projects stay on today's loop until they adopt the release that carries C1.

The decomposition artifacts live beside the spec in `docs/superheroes/a-review-loop-that-converges-in-few-rounds-and-sta-3f628c/` (PR #2199):
- `coverage-map.md`: 78 rows, every acceptance criterion of the spec owned once (C1 60, across its thirteen layers; C2 6; C3 3; C4 5; #2189 2, FR-53; the epic's closure 2, the Definition of done);
- `register.md`: 16 entries the children quote verbatim, three of them cross-epic seams with #2189 (R9, R10) and #2190 (R11), whose bodies quote them (`seams/`);
- the child and layer bodies as drafted for filing (`children/`);
- the package-read audit trail, written by the independent package read before the children file.

Sequencing (seam first; launches are the owner's word, one wave at a time):
- wave 1 is C1, its thirteen layers bottom-up, C1-L12 and C1-L13 free to build in parallel with the layers below;
- wave 2 is C2 and C3, in parallel, after C1's stack merges or as layers above its top layer once that layer's vet is READY;
- wave 3 is C4, after C3 the same way.

Release (R1): C1's stack merges whole, and the plugin release that first carries any of it carries all of it, FR-6's line count included. Each add-on merges whole, in that release or a later one; C4 ships with or after C3. Nothing ships behind a switch or a trial mode, and no child cuts or asks for a release. No date is set.

What this spec changes elsewhere: the advisor marks the superseded requirements of the risk-calibrated review spec and the converge-faster spec, each when the child that lands its replacement merges (R16); the shipped rules that section lists are child scope, each named in the coverage map. #2186 (letting today's restricted fixer read its order) is made unnecessary by C1-L9; the advisor proposes its close at C1's merge.

DoD:
- Every child issue (C1 to C4) is closed by a merged PR with a green vet, and every layer sub-issue of C1 by its own merged PR, C1's thirteen having merged as one native stack.
- The coverage map is complete: every row owned by a closed child or by this closure, and FR-53's two rows delivered by #2189, re-checked after any amendment to the spec.
- Every register decide-by is resolved and recorded in the register with a dated note naming where it was decided: R2, R3, R4, R8, R9, R10 and R11 by C1 (in the layers each names); R12 by C3. The cross-epic entries R9, R10 and R11 are quoted on #2189's and #2190's bodies.
- The spec's first Definition of done bullet holds, read from the release record: C1 shipped whole in one plugin release with FR-6's count; each add-on shipped whole, C4 with or after C3; FR-53 delivered by #2189.
- The closure receipt (`skills/showrunner/reference/closure.md`) is posted on this issue: coverage complete, children merged, the two other specs marked (R16), the first gardening pass after release named as where the spec's second Definition of done bullet is read (#2189's measure and #2190's escape logging), and the owner's delivery decision, presented with the last child's handback.

Routing: milestone stays where #2185 sits, **Backlog**, until the owner places the epic in an outcome milestone, a train-level call. Kind: `kind:machinery` (its subject is the review process), as #2185 already carries. Area labels on the epic: `area:review-crew` (already on #2185) and `area:showrunner` (added at filing, for C1-L12, C1-L13 and C3's vet rows). C1 carries both area labels, and its layers copy C1's milestone, project and labels; C3 carries both; C2 and C4 carry `area:review-crew`. Lane: full, per child and per layer. The children are native sub-issues of this epic and the layers native sub-issues of C1; each body carries its Anchor, What, DoD, sequencing, lane and presentation calls, size, order, and the register entries it consumes.
