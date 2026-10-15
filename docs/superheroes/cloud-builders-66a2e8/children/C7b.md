**STATE:** route build-ready · filed 2026-10-12 by the advisor's size-split ruling on cloud C7 (#1748; the builder's measured estimate of about 700 before code, against the 600 bar, `rubric/review-discipline.md` § Size; craft, owner veto open) · layer 14 of 16 in the cloud-builders stack (a direct sub-issue of the epic), on C7p (C7 was split again on 2026-10-12 into C7, C7r and C7p) · launches on C7p's pushed head once C7p hands back (C7's launch word covers the layers a size split adds) · not launched · merges only with the whole stack

**Order (advisor-launched):**
- Launched on **claude-two**, per the owner's standing instruction (2026-10-11: "switch everything to claude-two now"); usage-limit fallback claude-four (owner 2026-10-12). Message the advisor session **"superheroes advisor"** (seat `~/.claude`) for size, scope or premise questions, and post any ruling you receive on this issue.
- Review panels are codex-only (owner, 2026-10-07).
- Do not merge. This child merges only with the whole cloud-builders unit, by one `gh stack merge` once every layer is vetted (R8). Do not cut a release or ask for one.
- Branch from C7p's pushed head and open the PR with its base set to C7p's branch. Bring the layers below forward with a local `--no-ff` merge pushed plainly, never a rebase or a force-push, and link the stack as `rubric/native-stacks.md` § Each layer is a sub-issue says.
- Owner capability: any recorded run that needs a real cloud session uses claude-two's environment `env_018Z3fRJ8xTmagd714DyNHrE` with setup text pinned to this layer's head. Message the advisor first, and the advisor walks the owner through the re-paste. Recorded dry runs against fixtures meet every row below that doesn't name a live session.
- This PR's own build and review follow the plugin version your session runs. Nothing this epic builds governs a build until the release.

Anchor (spec-section): cloud-builders-66a2e8 · § When things go wrong (UFR-5, UFR-9, UFR-10, UFR-13) · as-of amendment #5 (owner-approved 2026-10-10; amendment 5, the relay, merged in #1770)

What: Recovering a cloud builder: the second half of the advisor's side of a running cloud build, split from C7 (#1748) at the 600 bar. The answering half is C7 (the builder-note event in the wave watch), C7r (the relay and the advisor's return) and C7p (the lapsed-pass notice and the send-back after renewal). Today the advisor recovers a stopped builder by `plugins/superheroes/rubric/launch-doctrine.md` § Recovery and `plugins/superheroes/skills/showrunner/reference/orchestration.md` § Adoption mechanics: an adoption from the pushed branch after sweeping the dead build's local worktree for unpushed work. A cloud builder has no local worktree, and its session isn't a local process. This layer:
- recovers a stopped or stalled cloud builder at once, from its pushed work, as an adoption routed through C5's routing step. It runs in the cloud when the cloud is ready and on the owner's machine otherwise (UFR-9; R5), and never leaves two builders working one issue (UFR-9; the mechanism is this child's call, recorded in the PR body). For a stalled builder that still answers, the advisor first asks it once, through C7r's relay, to push its work, and the new builder starts from what was pushed. A build that never pushed starts from the beginning (UFR-13). The recovery message to the owner uses the board's words: when the builder stopped, where the lane was recovered, and how much work since the last push is being redone (UFR-10). No other recovery machinery is added (Constraints);
- has the successor launch name the pushed branch it adopts (the cloud launch path carries only `Base commit:` today), and has the cloud builder continue that branch;
- relaunches at once a cloud builder that stopped at intake on a plugin-version mismatch (ending with `refusal` and both versions on its issue), routed as a launch with the reported version standing as the cloud's. It then runs on the owner's machine, and the launch report names both versions (R2; UFR-5);
- carries the recovery folds this issue inherits from cloud C7's body: the resume decision table's cloud-lane evidence (vet 443), the never-started repair under the ledger lock (C1b's judgment gate), and recovery reading the ledger's real state before naming a remedy (C1b round 8).

DoD:
- Tests or recorded dry runs:
  - a fixture stopped cloud lane, with pushed work and the cloud ready, is recovered by an adoption launched in the cloud from the pushed branch and sha (UFR-9, first acceptance);
  - with the cloud not ready, the same lane is recovered on the owner's machine;
  - the recovery refuses while the stopped lane could still be working the issue, and the PR body says how (UFR-9, second acceptance);
  - a stalled fixture builder that answers is asked once to push, and the successor starts from that push (UFR-13, first);
  - lost work is named in minutes since the last push (UFR-13, second; UFR-10);
  - a lane that never pushed is relaunched from the base (UFR-13, third).

  The board's recovery message is rendered in the PR body.
- The successor launch names the pushed branch it adopts, and the cloud builder continues that branch.
- A test or recorded dry run: a fixture cloud lane ending `refusal` with a reported version mismatch is relaunched through C5's routing step on the owner's machine, and the launch report names both versions (R2; UFR-5).
- (Fold, vet 443) The showrunner-resume decision table gives a cloud lane its own evidence: its listed cloud session, and its activity on GitHub as C1's watch reads it. A test shows a live cloud lane resumes and a dead one adopts.
- (Fold, C1b's judgment gate) A repair operation under the ledger lock restores a never-started lane's `started` record from the launch result's pending record, or records its terminal outcome from the reserved record. It's tested for both a cloud and a local never-started lane.
- (Fold, C1b round 8) Recovery reads the ledger's real state before naming a remedy: a lane that already has its `started` record is ended normally, and the `cloud-started-append-failed` remedy text matches. A test fails the sync after the write.
- Doctrine:
  - `launch-doctrine.md` § Recovery, outside its machine-parsed blocks (for a cloud lane, the ask to push replaces the sweep);
  - `orchestration.md` § Adoption mechanics;
  - the duty-9 pointer lines;
  - a `TRANSITION.md` unreleased note on cloud recovery.

  A search of the changed shipped files for requirement numbers, Canon entry ids, issue numbers and project names returns nothing (R9).
- The PR's first line is `Closes #<this issue>`, it names the epic only as `part of #1741`, and its base is C7p's branch. The register-quote check passes for `C7b` on the epic's body. The four validators pass and CI is green on the PR head. The PR carries its pre-handback review receipt under the review discipline its session runs.

**Epic:** #1741 (artifacts in `docs/superheroes/cloud-builders-66a2e8/`, `children/C7b.md` once the split docs PR merges); the epic is the stack's feature issue. **Child:** C7b, recovering a cloud builder, split from C7 at the 600 bar (C7's brief issuecomment-6120341858; DoD rows from issuecomment-6120352556). **Sequencing:** layer 14 of the cloud-builders stack, on C7p, with C7s above it.

**Lane call:** full. A recovery that leaves two builders on one issue duplicates work and collides on the branch, and a wrong remedy on a never-started lane leaves the ledger unreadable.

**Presentation call:** say it. The owner reads the recovery message, already worded by the board, and the PR shows it rendered.

**Size-consideration slot:** about 380 non-test lines (C7's builder's measure): recovery and the push ask about 130, the successor branch line about 60, the version-mismatch relaunch about 40, the three folds about 90, doctrine about 60. One pull request, one surface (the advisor's recovery of a cloud lane).

**Kind:** `kind:product` (owner ruling 2026-10-11, walk item 30).

**Consequence:** none for a consuming project until it adopts the release that carries the whole stack.

**Register check:** register entries stay quoted on the epic's body, the stack's feature issue (`rubric/native-stacks.md` § Each layer is a sub-issue). This child's check runs on the epic's body with the token `C7b` (`skills/showrunner/reference/register-check.md` § Stack layer inputs). The entries that bind this child: R1, R2, R5, R6, R8, R9 and R11. Until the advisor's split docs PR naming C7b merges, run the check with `--register-copy worktree` on that PR's branch.
