**STATE:** route build-ready · filed 2026-10-11 by the advisor's size-split ruling on cloud C5 (#1746; the 600 bar, `rubric/review-discipline.md` § Size; craft, owner veto open) · layer 8 of 15 in the cloud-builders stack (a direct sub-issue of the epic), on C5 · build wave 1, once C5 has pushed · not launched · merges only with the whole stack

**Order (advisor-launched):**
- Launched on **claude-two**, per the owner's standing instruction (2026-10-11: "switch everything to claude-two now"). Message the advisor session **"superheroes advisor"** (seat `~/.claude`) for size, scope or premise questions, and post any ruling you receive on this issue.
- Review panels are codex-only (owner, 2026-10-07).
- Do not merge. This child merges only with the whole cloud-builders unit, by one `gh stack merge` once every layer is vetted (R8). Do not cut a release or ask for one.
- Start from `build/c5b-seed`: C5's builder pushed the launch report and still-state code it had already written there, on top of C5's head; adopt it, re-run its receipts, and finish. Open the PR with its base set to C5's branch; bring the layers below forward with a local `--no-ff` merge pushed plainly, never a rebase or a force-push, and link the stack as `rubric/native-stacks.md` § Each layer is a sub-issue says.
- This PR's own build and review follow the plugin version your session runs; nothing this epic builds governs a build until the release.

Anchor (spec-section): cloud-builders-66a2e8 · § Part B · Where a build runs (FR-15, FR-16); § When things go wrong (UFR-6) · as-of amendment #5 (owner-approved 2026-10-10; amendments 1 to 5 changed only FR-1 in Part A, the Assumptions and the board's "1 Setup" step)

What: The launch report and the "Still on your machine" line, as the approved board's artboard "3 The launch report" draws them, with the board's wording as the product's wording, plus the doctrine for where a build runs. Cloud C5 (#1746) builds the routing step and the readiness reader, which decide each build's place and its reason; this layer says it to the owner:
- the launch report: every launched build under "In the cloud" or "On your machine", and each build that ran on the owner's machine although the setting or a launch word pointed it at the cloud with exactly one of the board's eight reasons in its words and its fix (FR-15, FR-16; R5), from C5's routing result; a version mismatch naming both versions (UFR-5, the wording); the fix telling the owner to paste the new setup text when C5's routing result says so (FR-37, the wording);
- the "Still on your machine" line: while builds run on the owner's machine because the cloud is not ready, the advisor opens each later message with the reason and its fix until it is fixed (UFR-6). How the advisor knows it is fixed is this child's call, recorded in the PR body;
- the launcher's report and still verbs;
- the doctrine: duty 9 points at the place call and the launch report (`plugins/superheroes/skills/showrunner/SKILL.md`, pointer lines only, R11), and `dispatch-preflight.md` carries the place call, the needs the advisor checks for and how each existing check reads for a cloud launch, including the cloud's blocked GitHub GraphQL interface (the discovery's pilot: `gh pr` and `gh issue` fail there, REST calls work), which a stack layer's stack-membership reads use.

DoD:
- A recorded dry run in the PR body renders the board's two launch reports from fixtures (a normal launch of five, and four launched with a version mismatch) and the "Still on your machine" line at the top of the next message, matching the board's words (FR-15, FR-16, UFR-6); a test asserts every reason the report can print is one of the board's eight (FR-16). Tests on the rendering, from C5's routing results: the phone-simulator reason and the outside-the-repository files reason each print in the board's words (FR-13's report half; UFR-3), a version mismatch prints both versions (UFR-5), and the pickup-flag-false fix tells the owner to paste the new setup text (FR-37, its second acceptance's wording).
- `dispatch-preflight.md` and duty 9 carry the place call and the needs list; the PR body states the call on stack layers and GraphQL, with the pilot fact it rests on, for the owner's veto.
- The glossary carries "Launch report" and "Launch word" entries, each under its own heading (R10). `plugins/superheroes/TRANSITION.md` carries a note in its unreleased section on where builds run once cloud builds are switched on (R8). A search of the changed shipped files for requirement numbers, Canon entry ids, issue numbers and project names returns nothing (R9).
- The PR's first line is `Closes #<this issue>`, it names the epic only as `part of #<epic>`, and its base is C5's branch. The register-quote check passes for `C5b` on the epic's body. The four validators pass and CI is green on the PR head. The PR carries its pre-handback review receipt under the review discipline its session runs.

**Epic:** #1741 (artifacts in `docs/superheroes/cloud-builders-66a2e8/`, `children/C5b.md`); the epic is the stack's feature issue. **Child:** C5b, the launch report and the still line, split from C5 at the 600 bar. **Sequencing:** layer 8 of the cloud-builders stack, on C5, with C6 above it.

**Lane call:** full. The launch report is the owner's only view of where builds went and why; a wrong reason or a missing still line sends the owner to fix the wrong thing.

**Presentation call:** say it. The owner reads the launch report and the still line, already worded by the board; the PR shows them rendered.

**Size-consideration slot:** about 380 non-test lines (C5's builder's measure): the report and still state about 290, doctrine about 90. One pull request, one surface (what the owner reads about where builds ran).

**Kind:** `kind:product` (owner ruling 2026-10-11, walk item 30).

**Consequence:** none for a consuming project until it adopts the release that carries the whole stack.

**Register check:** register entries stay quoted on the epic's body, the stack's feature issue (`rubric/native-stacks.md` § Each layer is a sub-issue). This child's check runs on the epic's body with the token `C5b` (`skills/showrunner/reference/register-check.md` § Stack layer inputs). The entries that bind this child: R2, R3, R5, R8, R9, R10 and R11. Until the advisor's docs PR naming C5b merges, run the check with `--register-copy worktree` on that PR's branch.
