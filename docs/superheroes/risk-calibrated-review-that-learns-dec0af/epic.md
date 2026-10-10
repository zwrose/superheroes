Anchor (spec-section): risk-calibrated-review-that-learns-dec0af · the whole spec (Purpose; Parts A to F, FR-1 to FR-81; When things go wrong, UFR-1 to UFR-10; Non-functional requirements; UI / UX; Definition of done / success) · as-of amendment #0 (owner-approved 2026-10-10, recorded in the spec's `approved:` field; discovery issue #1472; spec PR #1702)

What: The landing epic for risk-calibrated review that learns. Today a change counts as reviewed when the review loop produces a certificate. After this epic, each change is reviewed as strictly as the project's risk calls for, one plain review record says what happened, the owner sees only the leftovers with real consequences, on one sheet per PR, and the review learns from what escaped. Ten children land it:
- **C1, the review record (the seam).** Every review, on every lane, writes one plain record of what ran, what was found and what happened to each finding, and what is left.
- **C2, retire the certificate parts.** The certificate gate, the planted-bug check inside reviews, two ways of moving a review session, and the exact-commit evidence chain retire; the engine wiring check and the new-model admission check stay. It is a stack of five layers.
- **C3, the advisor's vet reads the review record.** The vet checks that the record exists, that the checks ran on the final commit, and that no leftover skipped the owner.
- **C4, Risk and trust.** One configure item holding the threat model and the project's risk areas, one sitting with the owner to fill it in, and an existing project's threat model carried over unchanged.
- **C5, lanes and the panel follow Risk and trust.** A change that touches a risk area always gets the full lane, the full panel is a generalist, the test role and the right specialists, and no reviewer is from a maker's model family.
- **C6, the test role replaces the test reviewer.** It writes break-it tests on risky code, flags tests that check nothing, and stops asking for coverage elsewhere.
- **C7, findings and the fix loop.** Every finding states its consequence and ends with one recorded outcome; craft is decided without the owner and listed for veto; leftovers with a real consequence come to the owner.
- **C8, the owner's decisions (the advisor's side).** Decisions arrive in three batches, the advisor walks a sheet before sending it, and the merge word is a saved "Merge" plus "done".
- **C9, the PR sheet and the index.** The page the owner answers and merges from, with its walk and pictures, and the index of what is waiting. It is a stack of three layers.
- **C10, learning from escapes.** Bugs traced to reviewed PRs are logged, reviewer seats are judged on what they caught, and calibration changes come to the owner as proposals at the gardening pass.

Consuming projects stay on today's behaviour until they adopt the release that carries all ten children.

The decomposition artifacts live beside the spec in `docs/superheroes/risk-calibrated-review-that-learns-dec0af/` (PR #1702):
- `coverage-map.md`: 150 rows, every acceptance criterion of the spec owned once (C1 10, C2 13, C3 3, C4 6, C5 16, C6 14, C7 21, C8 14, C9 39, C10 11), and the Definition of done as the closure's validation run (3);
- `register.md`: 13 entries the children quote verbatim;
- the child and layer bodies as drafted for filing (`children/`);
- the package-read audit trail, written by the independent package read before the children file.

Sequencing (seam first; launches are the owner's word, one wave at a time; this is the owner's build order, Part A, then Part B, then the owner's leftover review, then Part E):
- wave 0 is C1;
- wave 1 is C2 and C3, in parallel, after C1;
- wave 2 is C4 first, then C5 and C6 in parallel once C4 has merged;
- wave 3 is C7, C8 and C9, after waves 0 to 2;
- wave 4 is C10, after C8.

The spec's success definition (an owner shipping a risk-area change without reading code; no review held for a certificate; an escape reaching the owner as a proposal at a gardening pass) runs as the epic's closure validation run after the last child merges.

One release: nothing in this epic releases on its own. Every child merges before the plugin release that carries any of it, and that one release carries all of it; no child cuts or asks for a release, and the advisor holds the release pull request until the last child has merged (register R2; owner ruling, Canon 2026-10-10-d6064e1d-3). No date is set for the release.

What this spec changes elsewhere: the spec's section of that name lists amendments to five owner-approved specs (the certification contract spec, the forward doctrine spec, the review surface spec, the verification strategy spec and the converge-faster spec). Recording those amendments is the advisor's amendment work and no child's scope. The same section's "Shipped rules" are child scope; the coverage map's table names the child for each.

DoD:
- Every child issue (C1 to C10) is closed by a merged PR with a green vet, and every layer sub-issue of C2 and C9 is closed by its own merged PR, each stack having merged as one unit.
- The coverage map is complete: every row is owned by a closed child or by the closure validation run, re-checked after any amendment to the spec.
- Every register decide-by is resolved and recorded in the register with a dated note naming where it was decided: R1 and R4 by C1; R3 by C4 (the item's number and slug, a risk area's shape, the matching form, the reader's interface) and by C5 (what counts as unclear with no risk areas set); R6 by C5; R10 by C9.
- The closure receipt (`skills/showrunner/reference/closure.md`) is posted on this issue: coverage complete, children merged, amendments reconciled (including the five amended specs' entries the advisor records), the validation run's result for each of the spec's three success bullets, and the owner's delivery decision, presented with the last child's handback.
- One plugin release carries every child, cut only after the last child has merged (R2).

Routing: milestone **The reset lands**, because the discovery issue this spec came from, #1472, sits there, and this work replaces the certificate that milestone's reset defined (the certification contract spec). That milestone's exit condition names only epic #1259's children, so placing this epic there needs its description amended to name this epic too, a train-level edit the owner rules on; if the owner prefers, the epic goes to Backlog until a walk places it. Kind: `kind:machinery` (its subject is the review process). Area labels on the epic: `area:review-crew`, `area:showrunner`. Each child carries the label that matches its surface: C1, C2, C4, C5, C6, C7 and C9 `area:review-crew`; C3, C8 and C10 `area:showrunner`. Each layer copies its feature's milestone, project and labels. Lane: full, per child and per layer. The children are native sub-issues of this epic and the layers native sub-issues of their child; each body carries its Anchor, What, DoD, sequencing, lane and presentation calls, size, order, and the register entries it consumes.
