**STATE:** route build-ready · filed 2026-10-12 on the owner's word (walk item 41 = a; collector #695 item 107) · layer 15 of 16 in the cloud-builders stack (a direct sub-issue of the epic), on C7b, with C8 above it · launches on C7b's pushed head once C7b hands back (the cloud stack's launch word) · not launched · merges only with the whole stack

**Order (advisor-launched):**
- Launched on **claude-two**, per the owner's standing instruction; usage-limit fallback claude-four (owner 2026-10-12). Message the advisor session **"superheroes advisor"** (seat `~/.claude`) for size, scope or premise questions, and post any ruling you receive on this issue.
- Review panels are codex-only (owner, 2026-10-07).
- Do not merge. This child merges only with the whole cloud-builders unit, by one `gh stack merge` once every layer is vetted (R8). Do not cut a release or ask for one.
- Branch from C7b's pushed head and open the PR with its base set to C7b's branch. Bring the layers below forward with a local `--no-ff` merge pushed plainly, never a rebase or a force-push, and link the stack as `rubric/native-stacks.md` § Each layer is a sub-issue says.
- **Size discipline (advisor, 2026-10-12):** build only what the DoD rows need. A CLI, option or fail-closed branch no row needs is a candidate to cut.
- Owner capability: the live run needs claude-two's environment `env_018Z3fRJ8xTmagd714DyNHrE` with setup text pinned to this layer's head, and three fixture issues the advisor files on the owner's word. Message the advisor first, and the advisor walks the owner through the re-paste.
- This PR's own build and review follow the plugin version your session runs. Nothing this epic builds governs a build until the release.

Anchor (ruling): 2026-10-12 · owner ruling, walk item 41 = a (collector #695 item 107). The owner's words: "the entire reason we're doing this is because of machine capacity … We can't ship this if we don't have a solve for stacks, and the proof issue should actually simulate a stack to confirm." This vetoes C5's craft call that every stack layer runs on the owner's machine (cloud C5 PR #1783, FU1), under the spec's Purpose ("An owner who runs several builds at once is limited by the compute on their own machines") and FR-12/FR-13 (cloud-builders-66a2e8, as-of amendment #5).

What: Stack layers build in the cloud. Today C5's routing step gives every launch that carries a `stack` premise the need "GitHub's stack interface, which only your machine has", so no stack layer ever runs in the cloud. Most of this project's work is built as stacks, so cloud builds would barely relieve the owner's machine. The reason was that the cloud blocks GitHub's GraphQL interface, which stack-membership reads use. But none of a stack layer's steps needs that interface inside the cloud session:
- **The base check** (the layer branches from the layer below's current head) runs in the launcher on the owner's machine before launch (`base-not-layer-head`), so it is unchanged.
- **Bringing the layers below forward** is plain git, which works in the cloud.
- **Opening the PR with its base set to the layer below's branch** works through REST (`gh api` POST pulls), which works in the cloud.
- **Linking the stack** (`gh stack link`, GraphQL) moves to the advisor on the owner's machine at handback. C6b's doctrine already hands it there (cloud C6 FU2). The builder records in its handback that the link is owed, and the advisor links on receipt.

This layer:
- removes the stack rule from C5's routing step, so a stack layer routes like any other build (cloud when ready, by FR-12), while the phone simulator, files outside the repository and the other needs keep their rules;
- makes the cloud builder's stack steps work with no GraphQL: bring the layers below forward, open the PR through REST with the right base, and record the owed link (C6b's doctrine; extend it only where a step is missing);
- makes the advisor link a cloud-built layer on handback (duty 9 pointer, `orchestration.md`);
- updates the launch report and doctrine so no text still says stack layers stay local (the eight reasons drop the stack reason if no other need uses it).

DoD:
- A routing test: a launch carrying a `stack` premise, with the cloud ready and no other need, routes to the cloud. A stack launch that also needs the phone simulator still routes locally with that reason.
- A census of the cloud builder's path (workhorse charter, its cloud reference, and the libraries it calls) shows no GraphQL call for stack work. The PR body lists each stack step and the channel it uses.
- **A recorded live run on a three-issue fixture stack** (the owner's "the proof issue should actually simulate a stack"). A stack exists on GitHub only once its first two PRs are linked, and the first upper layer launches without a stack premise (`rubric/native-stacks.md`), so the proof needs a third layer:
  - the advisor files three fixture layers (three issues, each a one-line change; the advisor files and closes them, PRs never merge);
  - layers 1 and 2 build (locally or in the cloud; layer 2 launches without a stack premise, as the doctrine says for a first pair), and the advisor links their two PRs as a stack from the owner's machine;
  - layer 3 launches with the stack premise (`stack`, `layerPosition: 3`), passes the launcher's base gate, routes to the cloud, branches from layer 2's head, opens its PR with layer 2's branch as base, and hands back as a ready PR;
  - the advisor links layer 3 into the stack, and `stack_check list` shows all three members in order.

  The run's output and links go in the PR body.
- `plugins/superheroes/TRANSITION.md` carries a note in its unreleased section that stack layers now build in the cloud and the advisor links them (R8). A search of the changed shipped files for requirement numbers, Canon entry ids, issue numbers and project names returns nothing (R9).
- The PR's first line is `Closes #<this issue>`, it names the epic only as `part of #1741`, and its base is C7b's branch. The register-quote check passes for `C7s` on the epic's body. The four validators pass and CI is green on the PR head. The PR carries its pre-handback review receipt under the review discipline its session runs.

**Epic:** #1741 (artifacts in `docs/superheroes/cloud-builders-66a2e8/`, `children/C7s.md` once the docs PR that adds it merges); the epic is the stack's feature issue. **Child:** C7s, stack layers build in the cloud, added on the owner's word. **Sequencing:** layer 15 of the cloud-builders stack, on C7b, with C8 above it.

**Lane call:** full. A stack layer routed to the cloud that can't link, or that branches from the wrong base, collides on the stack and fails quietly until the merge.

**Presentation call:** say it. The owner sees stack layers listed "In the cloud" in the launch report. The PR shows the live run.

**Size-consideration slot:** about 150–250 non-test lines: routing about 30, the builder's stack steps and census about 60, advisor-side linking about 60, doctrine and TRANSITION about 50. Report at 300; stop at 600.

**Kind:** `kind:product` (owner ruling 2026-10-11, walk item 30).

**Consequence:** none for a consuming project until it adopts the release that carries the whole stack. After adoption, stack layers build in the cloud when it's ready, where today's stack would have kept them local.

**Register check:** register entries stay quoted on the epic's body. This child's check runs on the epic's body with the token `C7s`. The entries that bind this child: R5, R6, R8, R9 and R11. Until the docs PR adding C7s merges, run the check with `--register-copy worktree` on that PR's branch (`advisor/cloud-c7-split`).


