**STATE:** route build-ready · filed 2026-10-11 by the advisor's size-split ruling on cloud C6 (#1747; the 600 bar, `rubric/review-discipline.md` § Size; craft, owner veto open) · layer 10 of 13 in the cloud-builders stack (a direct sub-issue of the epic), on C6 · build wave 1, once C6 has handed back · not launched · merges only with the whole stack

**Order (advisor-launched):**
- Launched on **claude-two**, per the owner's standing instruction (2026-10-11: "switch everything to claude-two now"). Message the advisor session **"superheroes advisor"** (seat `~/.claude`) for size, scope or premise questions, and post any ruling you receive on this issue.
- Review panels are codex-only (owner, 2026-10-07).
- Do not merge. This child merges only with the whole cloud-builders unit, by one `gh stack merge` once every layer is vetted (R8). Do not cut a release or ask for one.
- Branch from C6's pushed head and open the PR with its base set to C6's branch; bring the layers below forward with a local `--no-ff` merge pushed plainly, never a rebase or a force-push, and link the stack as `rubric/native-stacks.md` § Each layer is a sub-issue says.
- Owner capability: the live run needs the claude-two cloud environment `superheroes` (id `env_018Z3fRJ8xTmagd714DyNHrE`) holding setup text pinned to this layer's head and a reviewer pass. The owner re-pastes the setup text; the advisor walks it with the owner when you message that you are ready for it. Do not run `/remote-env` or change the account's default environment.
- This PR's own build and review follow the plugin version your session runs; nothing this epic builds governs a build until the release.

Anchor (spec-section): cloud-builders-66a2e8 · § Part C · A cloud build's life (FR-18, FR-20, FR-21, FR-24, FR-25); § When things go wrong (UFR-12, the builder's half of its acceptance) · as-of amendment #5 (owner-approved 2026-10-10; amendments 1 to 5 changed only FR-1 in Part A, the Assumptions and the board's "1 Setup" step)

What: The builder charter's doctrine for the cloud path, and the live cloud run that proves the whole path. Cloud C6 (#1747) builds the machine side: the cloud builder module, the calibration guard, the runner's pass scrub, the history fetch before review, the GitHub probe over REST and the bootstrap's marker fix. This layer makes it the charter's own and runs it for real:
- `plugins/superheroes/skills/workhorse/SKILL.md` carries pointer lines only (§1 Intake, §2 Set up the workspace, §3 Preflight, §10 Review before handback, §11 Hand back, §12 park protocol), and the cloud path's detail sits in one reference file under `skills/workhorse/reference/` (R11);
- `plugins/superheroes/rubric/review-discipline.md` § Size names the builder note as a cloud builder's way to message the advisor (FR-21; R11);
- `plugins/superheroes/TRANSITION.md` carries a note in its unreleased section on how a builder behaves in a cloud session (R8);
- the live run: one cloud session launched through C1's cloud path on a fixture issue, on C6's code and this layer's doctrine. It also measures what the platform does when the launch's start commit is absent on GitHub (folded from cloud C1b PR #1762 FU3, moved here from C6) and records whether the launch should then read the remote directly.

DoD:
- `skills/workhorse/SKILL.md` carries pointer lines only, and the cloud path's detail sits in one reference file under `skills/workhorse/reference/` that §1, §2, §3, §10, §11 and §12 point at (R11); the PR body lists each section touched. `review-discipline.md` § Size names the builder note (R11).
- C6's PR body lists every `gh pr` and `gh issue` call on the builder's path (the workhorse charter, its reference files, and the libraries they call at intake, preflight, review and handback). This PR's body confirms that list against this layer's doctrine: each call either works through REST or the built-in tools in a cloud session or is not on a cloud build's path, and any call this layer's doctrine adds is added to the list.
- A recorded live run in one cloud session, launched through C1's cloud path on a fixture issue: the intake comment with the three facts (FR-20), the preflight passing with no owner prompt (FR-18), a push after each commit (FR-24), one review dispatch through the pass (FR-25), a builder note headed and saying it waits (FR-21, first acceptance) and posted as a comment on the fixture issue in a public repository, readable there without signing in (FR-21, second acceptance), a park with work pushed when no answer comes (UFR-12, builder's half), and a ready PR whose body carries the review record and receipts (FR-24, second acceptance). The run's output and links are in the PR body, with the measured result of a start commit absent on GitHub and the call on reading the remote directly.
- `plugins/superheroes/TRANSITION.md` carries a note in its unreleased section on how a builder behaves in a cloud session (R8). A search of the changed shipped files for requirement numbers, Canon entry ids, issue numbers and project names returns nothing (R9).
- The PR's first line is `Closes #<this issue>`, it names the epic only as `part of #<epic>`, and its base is C6's branch. The register-quote check passes for `C6b` on the epic's body. The four validators pass and CI is green on the PR head. The PR carries its pre-handback review receipt under the review discipline its session runs.

**Epic:** #1741 (artifacts in `docs/superheroes/cloud-builders-66a2e8/`, `children/C6b.md`); the epic is the stack's feature issue. **Child:** C6b, the builder's cloud doctrine and live run, split from C6 at the 600 bar. **Sequencing:** layer 10 of the cloud-builders stack, on C6, with C7 above it.

**Lane call:** full. The doctrine is what every unattended cloud builder reads, and the live run is the only proof the path works with no human step.

**Presentation call:** say it. The owner reads the intake comment, builder notes and park comments, already worded by the board; the PR shows them from the live run.

**Size-consideration slot:** about 170 non-test lines of doctrine (C6's builder's measure), plus the live run. One pull request, one surface (the builder's cloud path as the charter states it).

**Kind:** `kind:product` (owner ruling 2026-10-11, walk item 30).

**Consequence:** none for a consuming project until it adopts the release that carries the whole stack.

**Register check:** register entries stay quoted on the epic's body, the stack's feature issue (`rubric/native-stacks.md` § Each layer is a sub-issue). This child's check runs on the epic's body with the token `C6b` (`skills/showrunner/reference/register-check.md` § Stack layer inputs). The entries that bind this child: R2, R4, R6, R7, R8, R9 and R11. Until the advisor's docs PR naming C6b merges, run the check with `--register-copy worktree` on that PR's branch.
