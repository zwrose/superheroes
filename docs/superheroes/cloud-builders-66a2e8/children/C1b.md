**STATE:** route build-ready · filed 2026-10-10 by the advisor's size-split ruling on cloud C1 (#1742: its projection reached 1,097 non-test lines, past the 900 bound; the owner's launch word covers layers a size split adds, Canon 2026-10-10-dcc2b5e5-4) · layer 2 of 9 in the cloud-builders stack (a direct sub-issue of the epic), on cloud C1's pushed head · not launched · merges only with the whole stack

Anchor (spec-section): cloud-builders-66a2e8 · § Part C · A cloud build's life (FR-17, FR-23, FR-26) · as-of amendment #0 (owner-approved 2026-10-10)

What: The launcher's cloud spawn, split out of cloud C1 (#1742), which keeps the lane record, the readers and their doctrine. Today `launch` (`plugins/superheroes/lib/launcher.py`) starts every builder as a detached local `claude -p` process in a worktree it provisions. After this layer, `launch`:
- gives `launch` a cloud path: it starts the builder as an ordinary cloud session through the platform's command line, in the cloud environment the launch names, on the launching account's config dir (the spawn already pins it), with the launch's builder tier and effort, and returns once the session exists. The discovery's pilot did this by running `claude --cloud "<prompt>"` under a pseudo-terminal from plain Bash (the command refuses to run without one, and refuses `-p`), naming the environment with `--settings '{"remote":{"defaultEnvironmentId":"<id>"}}'` and the tier with `--model opus --effort medium`; the command printed the session id and returned at once, and the session was listed as a cloud session that a direct message reached (R1, R6);
- records the cloud lane on the ledger with its place and the session's identity, and creates no worktree, leaves no local process the build depends on, and pushes no launch branch: the cloud session starts from a commit the repository already has, which the pilot showed, and the pilot's hand-made launch branch was the leftover a plugin launch should not leave (R1; FR-23);
- carries the same composed order as a local launch, the standing rulings verbatim, plus the two things a cloud builder needs: that it runs in a cloud session and the advisor's plugin version (R2; FR-17, FR-26);
- carries the doctrine lines that name the launch's cloud flags and behaviour (moved here from cloud C1, so each layer's doctrine says only what its own code makes true).

The work in progress is already pushed: branch `build/1742-wo-b` at e95e9467 holds the launcher order's code and tests (174 new tests; 894 existing pass on the cloud C1 builder's re-run). Its dispatch forfeited at the timeout after writing the code, and its bite-proofs are still owed. Adopt that branch: bring cloud C1's pushed head (build/1742-cloud-lane) forward into it with a `--no-ff` merge, and finish it.

DoD:
- Tests with a fixture spawn: a cloud `launch` records one lane carrying its place and the session's id and name (R1), creates no worktree (`git worktree list` unchanged), leaves no local child process, and pushes nothing to the remote; a batch of three cloud launches reads as three lanes in `count` and `laneDetail`, each marked cloud (FR-19; the spec's "several cloud builders at once"). The PR body lists R1's decide-by choices (the field names, how the watch reads a cloud lane's activity, how its terminal outcome is recorded) for the advisor to record in the register.
- A test shows the composed order for one fixture issue is the same for a local and a cloud launch except the lines that state the place and the plugin version, with the standing rulings block byte-identical (FR-17; R2); a search of `plugins/superheroes/skills/showrunner/reference/vet-receipt.md` and duty 6's merge rules finds no step that depends on a build's place (FR-17, FR-26).
- A recorded live run: one cloud launch through `launch` on a fixture issue, showing the session id and name on the ledger, the session in the host's session listing marked cloud, a direct message from the advisor's session answered by the cloud session, no worktree or process left on the machine (FR-23: the launching side holds nothing the build waits on), and no new branch on the remote from the launch; the session is then asked to archive itself. The run's output is in the PR body.
- The bite-proofs owed by the forfeited dispatch are run on the final head, each named by its exact test, with output in the PR body.
- The PR's first line is `Closes #<this issue>`, it names the epic only as `part of #1741`, and its base is cloud C1's branch (`build/1742-cloud-lane`). The register-quote check passes for `C1b` on the epic's body. The four validators pass and CI is green on the PR head. The PR carries its pre-handback review receipt under the review discipline its session runs.

**Epic:** #1741, cloud builders. **Child:** cloud C1b, the launcher's cloud spawn. **Sequencing:** layer 2 of the cloud-builders stack, on cloud C1 (#1742), below cloud C2 (#1743). It launches now, in wave 0, adopting the pushed work in progress.

**Lane call:** full. A spawn that leaves a local process or a launch branch behind, or a composed order that differs from a local launch's, fails quietly.

**Presentation call:** say it. The owner meets this only through the launch report and the lane listing, both worded by the board.

**Size-consideration slot:** about 553 non-test lines are already written (the launcher order), plus the moved doctrine lines and the bite-proofs. One pull request, one surface (the launcher's cloud spawn).

**Kind:** `kind:machinery`.

**Consequence:** none for a consuming project until it adopts the release that carries the whole stack.

**Order (advisor-launched):**
- Launched on claude-three (owner, 2026-10-10: builds run on claude-three until its usage runs out, then claude-four, then claude-two). Every spawned claude call pins CLAUDE_CONFIG_DIR to /Users/zwrose/.claude-three. Message the advisor session **"superheroes advisor"** (seat `~/.claude`) for size, scope or premise questions, and post any ruling you receive on this issue.
- Review panels are codex-only (owner, 2026-10-07).
- Do not merge. This child is layer 2 of the cloud-builders stack and merges only with the whole unit, by one `gh stack merge` once every layer is vetted (R8). Do not cut a release or ask for one.
- Open the PR with its base on `build/1742-cloud-lane`. Link the stack as `rubric/native-stacks.md` § Each layer is a sub-issue says.
- Owner capability: the live run in this DoD needs a cloud environment on the launching account with the plugin set up in it; the advisor clears it with the owner at dispatch and names the environment in the launch. Cleared at dispatch (2026-10-10): use account Three's cloud environment `superheroes-probe` (env_01X18oaoJWCiMDUXHNRHpTtc), set up in the discovery's pilot with plugin 0.42.0 and a reviewer pass valid to 2026-10-19. Anything that must be pasted into an environment is the owner's hand step: ask the advisor, who relays it, and wait in-turn per the size rule's wait, or park with your work pushed.
- This PR's own build and review follow the plugin version your session runs; nothing this epic builds governs a build until the release.

**Register check:** register entries stay quoted on the epic's body, the stack's feature issue (`rubric/native-stacks.md` § Each layer is a sub-issue). This child's check runs on the epic's body with the token `C1b` (`skills/showrunner/reference/register-check.md` § Stack layer inputs). The entries that bind this child: R1, R2, R6, R8, R9 and R11.
