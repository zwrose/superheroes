**STATE:** route build-ready · filed 2026-10-11 by the advisor's size-split ruling on cloud C4 (#1745; the 600 bar, `rubric/review-discipline.md` § Size; craft, owner veto open) · layer 6 of 16 in the cloud-builders stack (a direct sub-issue of the epic), on C4 · build wave 1, once C4 has handed back · not launched · merges only with the whole stack

**Order (advisor-launched):**
- Launched on **claude-two**, per the owner's standing instruction (2026-10-11: "switch everything to claude-two now", claude-three's weekly usage being at 100%). Message the advisor session **"superheroes advisor"** (seat `~/.claude`) for size, scope or premise questions, and post any ruling you receive on this issue.
- Review panels are codex-only (owner, 2026-10-07).
- Do not merge. This child merges only with the whole cloud-builders unit, by one `gh stack merge` once every layer is vetted (R8). Do not cut a release or ask for one.
- Branch from the pushed head of C4 and open the PR with its base set to C4's branch; bring the layers below forward with a local `--no-ff` merge pushed plainly, never a rebase or a force-push, and link the stack as `rubric/native-stacks.md` § Each layer is a sub-issue says.
- Owner capability: the recorded setup sitting in this DoD needs the owner's hand steps in a cloud environment on the launching account (the `/remote-env` pick and the reviewer sign-in); the advisor clears it with the owner at dispatch and walks the owner through it.
- This PR's own build and review follow the plugin version your session runs; nothing this epic builds governs a build until the release.

Anchor (spec-section): cloud-builders-66a2e8 · § Part A · Setting a project up for the cloud (FR-1) · as-of amendment #5 (owner-approved 2026-10-10; amendments 1 to 5 reshape FR-1's hand steps)

What: The setup sitting reaches the owner, and the plugin learns which environment the owner picked. Cloud C4 (#1745) builds the setup sitting's library: the setup message, the check session started by the environment's id, the check's judgment, the setup record write and the result messages. This layer is the text that makes the advisor use it:
- a section in configure's set-up reference (`plugins/superheroes/skills/configure/reference/set-up.md`) for the setup sitting: when the owner asks for cloud builds, the advisor gives the setup message C4 renders, walks the one-time reviewer sign-in before the pass command and confirms it is done, has the owner pick the new environment with `/remote-env` and reads its id with the reader below, starts the check session through C4's start function naming that id, and reports C4's result messages; "check again" and "setup text" on request;
- a reader in `plugins/superheroes/lib/`, beside C4's setup sitting, that returns the cloud environment id the owner picked with `/remote-env`, from the user settings of the account the builds run on (`remote.defaultEnvironmentId` in that account's Claude Code settings), read before and after the pick: a missing or unchanged value is no pick, and the advisor asks the owner to pick again; the advisor never asks the owner to type or paste an id (ruling 37 b, Canon 2026-10-11-dcc2b5e5-5); on a machine where several accounts share one settings file, the reader reads right after the pick;
- the routing paragraph in configure's charter that sends "set up cloud builds" there, and one pointer line in the showrunner charter (`plugins/superheroes/skills/showrunner/SKILL.md`, R11);
- the note in `plugins/superheroes/TRANSITION.md`'s unreleased section on how a project is set up for cloud builds (R8).

DoD:
- A recorded setup sitting (the transcript in the PR body), driven through the skill text, for a fixture account that has not yet signed in to the separate reviewer sign-in: the advisor's message lists the `/remote-env` pick step, walks the one-time sign-in before the pass command and confirms it is done, reads the picked id with the before-and-after check, and launches the check session naming that id (FR-1, the Given-When-Then acceptance as amended by amendment 4; Canon 2026-10-11-dcc2b5e5-5 and 2026-10-11-dcc2b5e5-1). Tests on the reader: a fixture whose setting does not change across the pick, and one with no setting, each give the ask-again message and no id; a changed setting returns the new id. A test fails if the set-up reference tells the advisor to ask the owner to type or paste an id, or to start the check session without naming the id.
- `plugins/superheroes/TRANSITION.md` carries the note (R8). The charter gains pointer lines only (R11). A search of the changed shipped files for requirement numbers, Canon entry ids, environment ids and project names returns nothing (R9).
- The PR's first line is `Closes #<this issue>`, it names the epic only as `part of #<epic>`, its base is C4's branch. The register-quote check passes for `C4b` on the epic's body. The four validators pass and CI is green on its head. The PR carries its pre-handback review receipt under the review discipline its session runs.

**Epic:** #1741 (artifacts in `docs/superheroes/cloud-builders-66a2e8/`, `children/C4b.md`); the epic is the stack's feature issue. **Child:** C4b, the setup sitting's skill text, split from C4 at the 600 bar. **Sequencing:** layer 6 of the cloud-builders stack, on C4, with C5 above it.

**Lane call:** full. Prose that tells the advisor how to run the sitting decides what the owner is asked and which environment the check runs in; a wrong instruction there is quiet until a setup fails.

**Presentation call:** say it. The owner reads the setup sitting's messages, already worded by the board; the PR shows the recorded sitting.

**Size-consideration slot:** about 140 non-test lines: the reader about 40 (added by ruling 37 b), the set-up reference section about 80, the routing paragraph, the pointer line and the TRANSITION note about 20. One pull request, one surface (the sitting's skill text).

**Kind:** `kind:product` (owner ruling 2026-10-11, walk item 30).

**Consequence:** none for a consuming project until it adopts the release that carries the whole stack; after that the owner meets the setup sitting only on asking for cloud builds.

**Register check:** register entries stay quoted on the epic's body, the stack's feature issue (`rubric/native-stacks.md` § Each layer is a sub-issue). This child's check runs on the epic's body with the token `C4b` (`skills/showrunner/reference/register-check.md` § Stack layer inputs). The entries that bind this child: R3, R8, R9 and R11. Until docs PR #1770 merges, the register naming C4b is on its branch (`advisor/cloud-spec-amend-2`): run the check with `--register-copy worktree` there.


