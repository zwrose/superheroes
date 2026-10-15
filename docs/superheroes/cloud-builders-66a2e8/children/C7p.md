**STATE:** route build-ready · filed 2026-10-12 by the advisor's second size-split ruling on cloud C7 (#1748; the three orders measured about 950 non-test lines against the 450 stop line, `rubric/review-discipline.md` § Size; craft, owner veto open) · layer 13 of 16 in the cloud-builders stack (a direct sub-issue of the epic), on C7r · launches on C7r's pushed head once C7r hands back (C7's launch word covers the layers a size split adds) · not launched · merges only with the whole stack

**Order (advisor-launched):**
- Launched on **claude-two**, per the owner's standing instruction (2026-10-11: "switch everything to claude-two now"); usage-limit fallback claude-four (owner 2026-10-12). Message the advisor session **"superheroes advisor"** (seat `~/.claude`) for size, scope or premise questions, and post any ruling you receive on this issue.
- Review panels are codex-only (owner, 2026-10-07).
- Do not merge. This child merges only with the whole cloud-builders unit, by one `gh stack merge` once every layer is vetted (R8). Do not cut a release or ask for one.
- Branch from the layer below's pushed head and open the PR with its base set to that layer's branch. Bring the layers below forward with a local `--no-ff` merge pushed plainly, never a rebase or a force-push, and link the stack as `rubric/native-stacks.md` § Each layer is a sub-issue says.
- **Start from the pushed order branch named below.** C7's builder wrote this layer's code as one of three orders before the split. Adopt that branch: integrate it, review it, and fix it. Don't rewrite it from scratch. Its head sha and contents are on #1748.
- **Size discipline (advisor, 2026-10-12):** the three orders came in about 2.7× over the estimate. Treat any CLI, option or fail-closed branch that no DoD row below needs as a candidate to cut in review, not to keep.
- This PR's own build and review follow the plugin version your session runs. Nothing this epic builds governs a build until the release.
- **Your order branch:** `build/1748-wo-c` (the lapsed-pass notice and send-back), from C7's builder.

Anchor (spec-section): cloud-builders-66a2e8 · § Part E · Keeping the reviewer pass alive (FR-36; FR-35, the second sentence of its acceptance, the first being C8's); § When things go wrong (UFR-8) · as-of amendment #5 (owner-approved 2026-10-10)

What: A PR parked because the lapsed reviewer pass stopped its review, split from C7 (#1748):
- the notice of a PR parked because the lapsed pass stopped its review, in the board's words, naming the PR, the reason and the renewal; a review that did not run for any other reason is reported as the review rules already say, with no renewal advice (UFR-8; R7);
- after the pass is renewed — meaning a cloud session has confirmed the reviewer answers with the new pass and the setup record's lapse date has moved (R3; the pass command alone is not a renewal) — each PR parked that way and still open is sent back for its review, sent through C7r's relay, with no further word from the owner. The exceptions are one closed before the renewal and one the owner already let through by the review rules (FR-36);
- with a lapsed pass, the launch report's reason, the "Still on your machine" line (both C5b's) and the parked notice all still appear (FR-35, its second sentence);
- its doctrine: duty-9 pointer lines, with the detail in a section of `skills/showrunner/reference/orchestration.md` on the lapsed-pass parked notice and the send-back (R11).

DoD:
- Recorded dry runs:
  - the parked notice for a fixture PR parked by a lapsed pass names the PR, the reason and the renewal (UFR-8, first);
  - a fixture PR whose review did not run for another reason gets no renewal advice (UFR-8, second);
  - after a fixture renewal confirmed by a cloud session, the open parked PR is sent back for review, and a closed one and one the owner let through are not (FR-36, all three);
  - a pass the pass command made that no cloud session has confirmed sends nothing back;
  - with a fixture lapsed pass, the launch report's reason, the "Still on your machine" line and the parked notice each appear (FR-35, second sentence).
- `plugins/superheroes/TRANSITION.md` carries a note in its unreleased section on the lapsed-pass notice and send-back (R8). A search of the changed shipped files for requirement numbers, Canon entry ids, issue numbers and project names returns nothing (R9).
- The PR's first line is `Closes #<this issue>`, it names the epic only as `part of #1741`, and its base is C7r's branch. The register-quote check passes for `C7p` on the epic's body. The four validators pass and CI is green on the PR head. The PR carries its pre-handback review receipt under the review discipline its session runs.

**Epic:** #1741 (artifacts in `docs/superheroes/cloud-builders-66a2e8/`, `children/C7p.md` once the split docs PR merges); the epic is the stack's feature issue. **Child:** C7p, the lapsed-pass notice and send-back, split from C7. **Sequencing:** layer 13 of the cloud-builders stack, on C7r, with C7b above it.

**Lane call:** full. A send-back that fires on an unconfirmed pass, or misses a parked PR, either reruns a review that will fail again or leaves a PR parked forever without anyone noticing.

**Presentation call:** say it. The owner reads the parked notice, already worded by the board, and the PR shows it rendered.

**Size-consideration slot:** about 250 non-test lines (C7's builder's measure of order C plus doctrine). Stop line 350. One pull request, one surface (the lapsed-pass park and its recovery).

**Kind:** `kind:product` (owner ruling 2026-10-11, walk item 30).

**Consequence:** none for a consuming project until it adopts the release that carries the whole stack.

**Register check:** register entries stay quoted on the epic's body, the stack's feature issue (`rubric/native-stacks.md` § Each layer is a sub-issue). This child's check runs on the epic's body with the token `C7p` (`skills/showrunner/reference/register-check.md` § Stack layer inputs). The entries that bind this child: R3, R5, R6, R7, R8, R9 and R11. Until the advisor's split docs PR naming C7p merges, run the check with `--register-copy worktree` on that PR's branch.
