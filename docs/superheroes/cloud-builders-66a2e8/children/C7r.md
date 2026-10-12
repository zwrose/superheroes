**STATE:** route build-ready · filed 2026-10-12 by the advisor's second size-split ruling on cloud C7 (#1748; the three orders measured about 950 non-test lines against the 450 stop line, `rubric/review-discipline.md` § Size; craft, owner veto open) · layer 12 of 15 in the cloud-builders stack (a direct sub-issue of the epic), on C7 · launches on C7's pushed head once C7 hands back (C7's launch word covers the layers a size split adds) · not launched · merges only with the whole stack

**Order (advisor-launched):**
- Launched on **claude-two**, per the owner's standing instruction (2026-10-11: "switch everything to claude-two now"); usage-limit fallback claude-four (owner 2026-10-12). Message the advisor session **"superheroes advisor"** (seat `~/.claude`) for size, scope or premise questions, and post any ruling you receive on this issue.
- Review panels are codex-only (owner, 2026-10-07).
- Do not merge. This child merges only with the whole cloud-builders unit, by one `gh stack merge` once every layer is vetted (R8). Do not cut a release or ask for one.
- Branch from the layer below's pushed head and open the PR with its base set to that layer's branch. Bring the layers below forward with a local `--no-ff` merge pushed plainly, never a rebase or a force-push, and link the stack as `rubric/native-stacks.md` § Each layer is a sub-issue says.
- **Start from the pushed order branch named below.** C7's builder wrote this layer's code as one of three orders before the split. Adopt that branch: integrate it, review it, and fix it. Don't rewrite it from scratch. Its head sha and contents are on #1748.
- **Size discipline (advisor, 2026-10-12):** the three orders came in about 2.7× over the estimate. Treat any CLI, option or fail-closed branch that no DoD row below needs as a candidate to cut in review, not to keep.
- This PR's own build and review follow the plugin version your session runs. Nothing this epic builds governs a build until the release.
- **Your order branch:** `build/1748-wo-b` (the relay), from C7's builder.
- Owner capability: this layer's live run needs claude-two's environment `env_018Z3fRJ8xTmagd714DyNHrE` with setup text pinned to this layer's head, and the cross-account relay. Message the advisor first, and the advisor walks the owner through the re-paste.

Anchor (spec-section): cloud-builders-66a2e8 · § Part C · A cloud build's life (FR-22, the advisor's answer reaching the builder; the wake is C7's); § When things go wrong (UFR-12, the advisor's half of its acceptance; the builder's half is C6b's) · as-of amendment #5 (owner-approved 2026-10-10; amendment 5, the relay, merged in #1770)

What: Answering a cloud builder, split from C7 (#1748). C7 builds the builder-note event in the wave watch, which wakes the advisor. This layer delivers the advisor's answer:
- the standing relay session (R6; ruling 33 a, Canon 2026-10-11-dcc2b5e5-3): a background session on Haiku 5.5 on the builders' account, started by the advisor, that forwards the advisor's text unchanged to the cloud session a lane names. A message counts as delivered only when the text the relay reports sending matches the advisor's exactly; a mismatch or a silent relay is reported, and the message is not counted. The relay follows the builders' account through the owner's instance rotation, and the archive request after a merge or close goes the same way. How the relay is started, kept alive and checked is this child's call (R6 decide-by), recorded in the PR body;
- the advisor answers a woken note by direct message to the session the lane names, through the relay when the builders run on a different Claude account, with no step from the owner (FR-22);
- when the advisor is back after being away, it answers each waiting note and resumes each lane parked on one (UFR-12, the advisor's half);
- its doctrine: duty 9 pointer lines and `wave-watch.md` for answering (R11).

DoD:
- Tests on the relay's exact-text check: a relay report that differs from the advisor's text by one character, and a relay that reports nothing within its wait, each leave the message undelivered and say so (R6).
- A recorded live run: a cloud builder launched through C1's path posts a builder note; C7's armed watch surfaces it; the advisor's direct answer, sent from a different Claude account through the relay, reaches the builder, which carries on with no owner step, and the relay's reported text matches exactly (FR-22; R6). A second fixture run with the advisor away shows the note waiting and, on the advisor's return, answered and the parked lane resumed (UFR-12, the advisor's half). Output in the PR body.
- `plugins/superheroes/TRANSITION.md` carries a note in its unreleased section on answering a cloud builder through the relay (R8). A search of the changed shipped files for requirement numbers, Canon entry ids, issue numbers and project names returns nothing (R9).
- The PR's first line is `Closes #<this issue>`, it names the epic only as `part of #1741`, and its base is C7's branch (`build/1748-cloud-advisor-side`). The register-quote check passes for `C7r` on the epic's body. The four validators pass and CI is green on the PR head. The PR carries its pre-handback review receipt under the review discipline its session runs.

**Epic:** #1741 (artifacts in `docs/superheroes/cloud-builders-66a2e8/`, `children/C7r.md` once the split docs PR merges); the epic is the stack's feature issue. **Child:** C7r, answering a cloud builder, split from C7 (C7's size report issuecomment-6120645481). **Sequencing:** layer 12 of the cloud-builders stack, on C7, with C7p above it.

**Lane call:** full. A relay that counts a mangled or undelivered answer as delivered leaves a cloud builder acting on words the advisor never sent, and nobody would notice.

**Presentation call:** say it. The owner sees no new screen; the PR shows the live run's note, answer and relay check.

**Size-consideration slot:** about 430 non-test lines (C7's builder's measure of order B plus the answering doctrine). Stop line 550. One pull request, one surface (delivering the advisor's answer to a cloud builder).

**Kind:** `kind:product` (owner ruling 2026-10-11, walk item 30).

**Consequence:** none for a consuming project until it adopts the release that carries the whole stack.

**Register check:** register entries stay quoted on the epic's body, the stack's feature issue (`rubric/native-stacks.md` § Each layer is a sub-issue). This child's check runs on the epic's body with the token `C7r` (`skills/showrunner/reference/register-check.md` § Stack layer inputs). The entries that bind this child: R1, R6, R8, R9 and R11. Until the advisor's split docs PR naming C7r merges, run the check with `--register-copy worktree` on that PR's branch.
