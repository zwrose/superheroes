# Transition notes

This file records consumer-visible shape changes across superheroes releases. Read it before you
upgrade a caller that invokes dispatch CLIs, reads dispatch results, or depends on a result key.

Add a section when a release drops, renames, or newly requires an argument, a result key, or a
result shape a consumer depends on. Put the newest release first. Each section names the release it
belongs to and lists every change with its replacement.

Open each bullet of a section's `### Before you upgrade` list with a marker: `**Before switching.**`
when the adopting seat must finish it before it switches to the new version, or
`**After switching.**` when it is owed once the seat runs the new version. adopt-version holds the
switch only on before-switching steps, and a bullet with no marker counts as before switching.

## Unreleased

### Before you upgrade

- **Before switching.** **Finish or restart every review session in flight.** A review opened before the upgrade restarts once: its first driver command answers `session-from-earlier-version`, and Setup runs again into a fresh session folder. See [Review: the post-fix diff comes from git](#review-the-post-fix-diff-comes-from-git).
- **After switching.** **Nothing is owed for an existing PR or stack sheet input.** An advisor that wants to keep a craft finding off the owner's sheet now gives it a `craftDeterminations` entry in place of a `leftovers` entry. See [PR sheet: craft determinations and the Decided for you list](#pr-sheet-craft-determinations-and-the-decided-for-you-list).
- **After switching.** **Review seats now get the project's `CLAUDE.md` by absolute path.** A project that pastes `CLAUDE.md` into a review seat's prompt by hand, as a stopgap, can drop the paste. See [Review seats: CLAUDE.md by absolute path](#review-seats-claudemd-by-absolute-path).
- **After switching.** **A project names its CI workflow through configure (item 16, `ciWorkflow`).** Until it does, a review record reads CI green only when at least one GitHub Actions run on the final commit succeeded and no run on it is unfinished. A project whose CI is not GitHub Actions never reads CI `green` on a review record (it reads `none` once its checks finish clean), and naming a workflow in `ciWorkflow` cannot change that. See [Review record: CI green needs the project's CI workflow](#review-record-ci-green-needs-the-projects-ci-workflow).
- **After switching.** **Advisors trim PR and stack sheets by the "judge before you build" rule; nothing is owed for existing sheets.** See [PR sheet: judge before you build](#pr-sheet-judge-before-you-build).
- **After switching.** **Pass `--size-base-ref <base branch>` on every new implementer `dispatch-write` run.** A run opened before the upgrade continues with the flags it opened with: adding the ref to its continuation refuses `size-inputs-mismatch`. Without the flag, a build that merges its base branch in mid-build still reads that branch's lines as its own and can read its tripwire crossed when it is not. See [Dispatch: the size fold counts from the merge base](#dispatch-the-size-fold-counts-from-the-merge-base).
- **After switching.** **Nothing is owed for a check that could not run.** A caller that reads break-it `failed` exit codes or verifier drops sees fewer of them. See [Review: a check that could not run never dismisses a finding](#review-a-check-that-could-not-run-never-dismisses-a-finding).
- **After switching.** **A PR body no longer carries an owner-run database or Keychain command block.** Such a block goes in a committed file on the branch and the body tells the owner to run the file (`bash <path>`) rather than paste its lines; `vet_slot.py handback` refuses a shell block that names a database tool or a Keychain read otherwise. See [Handback: owner-run commands live in a file](#handback-owner-run-commands-live-in-a-file).
- **After switching.** **A project whose cloud builds need its own setup commands lists them through configure (item 17, `cloudSetupCommands`), then writes and pastes new setup text.** A step added by hand under the setup text's marker line is lost the next time setup text is pasted, and a project with no list gets the same setup text as before. See [Cloud setup text: project setup commands](#cloud-setup-text-project-setup-commands).
- **After switching.** **A project that lists setup commands has the files they depend on (item 18, `cloudSetupInputs`) in the setup text's stamp, so changing a lockfile makes the cloud check report the setup text out of date; write and paste new setup text.** A project that already lists commands has no item 18 until it sets one or lists commands again after clearing them, so its stamp is unchanged until then. See [Cloud setup text: setup inputs join the stamp](#cloud-setup-text-setup-inputs-join-the-stamp).
- **After switching.** **Nothing is owed.** An attended session that runs subagents now gets its automatic checkpoint at the next idle measurement above the trigger, where a subagent's turn used to hold it off. See [Checkpoint: a subagent's turn never holds the automatic checkpoint](#checkpoint-a-subagents-turn-never-holds-the-automatic-checkpoint).

### Checkpoint: a subagent's turn never holds the automatic checkpoint

- A subagent's `turn.start`, a background agent's especially, left the session marked busy after the main turn ended, so the automatic checkpoint never fired in an attended session that ran subagents, until Claude Code compacted the session itself without fresh notes.
- Only the main turn now marks the session busy or binds the checkpoint turn. The checkpoint fires at the next idle measurement above the trigger whatever subagents are running. Headless builder sessions are unchanged.

### PR sheet: judge before you build

- `theme/review-template.md` § The items gains the rule: before building a sheet, the advisor reads the project's Canon, settles a leftover as a `craftDetermination` in place of a card only on one of three grounds (another card on the same sheet carries its consequence; a fix in another layer of the same stack, named in the ground, removed it; a Canon entry, cited by id, answers it), keeps doubt as a card, cites a Canon-covered acceptance once in the `summary` in place of an item, puts up an item only for a call that passes Test 2 and names its ground, and folds disclosures with no choice into one item with a single Accept (not a call, so the item bar does not apply). `skills/showrunner/reference/owner-decisions.md` § Delivery mechanics points to it. § Decided for you and the vet receipt's row "No leftover skipped the owner's review" name the same three grounds, so an entry on one of them no longer holds the vet.
- A finding carried from an earlier review record across several later reviews now carries ` (carried from the earlier review record)` once. Before, the suffix repeated once per carry. A reason already written with the suffix repeated keeps it; later carries add no more.

### Review: the post-fix diff comes from git

- The driver derives the post-fix diff itself, from `git diff <pinned baseRef>...<fix-fold head>`. A `headDiff` or `headDiffPath` a fixer submits is a cross-check against that derivation, and submitting none is allowed.
- A supplied diff that differs from git's (line endings aside) stops the round with `head-diff-mismatch`. Git unable to read the head beside a supplied diff stops it with `head-diff-unverifiable`. A `headDiffPath` that cannot be read is recorded as `supplied-unreadable` and git governs on a hand `submit`; on the durable-record path `record-result` refuses `head-diff-unreadable` at record time, and the remedy is to omit the optional `headDiffPath` or replace it with a readable absolute path, then record again.
- Each round and its receipt row gain `headDiffCheck` (`match`, `mismatch`, `none-supplied`, `supplied-unreadable`, `unverifiable` or `no-repository`), and `headDiffSource` reads `git` whenever the driver derived the diff.
- A fix round with no supplied diff audits its fixes instead of running a wider panel.

### PR sheet: craft determinations and the Decided for you list

- A PR or stack sheet input takes the optional key `craftDeterminations`. A key names a left-for-owner finding the way a `leftovers` key does, and a value is `{ground, reason}`, both non-empty strings. The shape is in the docstring of `lib/pr_sheet.py`.
- A sheet takes the optional field `prSheet.decidedForYou`, one entry for each determination. An entry is no card, and the page lists it below the cards with one control, **Make this mine**. A sheet with no determinations is unchanged byte for byte.
- `pr_sheet.py build` refuses a determination with no ground, a key that names no left-for-owner finding or more than one, and a finding that has both a `leftovers` entry and a determination.
- A carried sheet keeps the earlier sheet's entries. `build` refuses a carry that adds a determination, changes one, or turns one back into a `leftovers` card. Make each of those changes on an unsigned republish.
- **Make this mine** stores an ordinary answer at `answers/<entry id>`. Any document stored there other than a well-formed null answer counts as taken back. While an entry is taken back, Merge is locked and a held Merge is cleared, and `pr_state` reads the PR as `needs-you`. A saved take-back beats a saved Merge after "done".

### Review seats: CLAUDE.md by absolute path

- The panel, verifier, synthesis, gap-sweep, audit and scoped-finder orders name the project's `CLAUDE.md` through the new placeholder `CLAUDE_MD_PATH`: the absolute path into the live checkout when the project has a `CLAUDE.md` at its root, or `(this project has no CLAUDE.md at <repo root>)` when it has none. Before, they named it by the bare relative path `CLAUDE.md`, which the sanitized view strips, so external-engine seats rarely read it.
- The sanitized view's notice no longer says only that stripped config's absence is not a finding: it adds that a `CLAUDE.md` or calibration file the instructions name by an absolute path sits outside the view and is readable there, and that such a path is never listed in the investigated array.
- The fixer order is unchanged; it runs in the live checkout, where the relative path opens.

### Review records: an owner ruling counts on an organisation-owned repository

- An `ownerRulings` entry no longer needs its comment to read `author_association: OWNER`. On an organisation-owned repository the owner's own comments read `MEMBER`, so every chat ruling a finding cited stayed a card with the reason `the ruling's comment is not the owner's`, and the owner was asked again. That reason is gone.
- The ruling still counts only when its link is a comment permalink in the PR's own repository, the comment read is that comment on that issue, its body is a standard chat-ruling record, and the words sit in its quoted block. A chat-ruling record posted by any account counts; the vet reads the link.

### Dispatch: the size fold counts from the merge base

- `engine_dispatch.py dispatch-write` takes a new optional flag, `--size-base-ref <ref>`, the branch the build merges from. With it, the fold counts from the newer of `--size-base` and the merge base of `HEAD` and that ref, so a mid-build merge of the base branch adds nothing to `sizeTripwire.tripwireCount`; a ref older than `--size-base` never moves the count back past it.
- A run opened with the flag journals `baseRef` in `sizeTripwireInputs`, and its `sizeTripwire` gains `baseRef` and `countedFrom` (the commit the count ran from). A continuation that passes a different ref refuses `size-inputs-mismatch`.
- `--size-base-ref` without `--size-base` and `--size-line` refuses `size-inputs-incomplete`; a ref that is not a commit refuses `size-base-unresolvable`, as an unresolvable `--size-base` already did. A ref that stops resolving by fold time folds `status: "indeterminate"` with `reason: "size-base-unresolvable"`. A ref that already contains any of the build's own commits (the build's own branch, its pushed `origin/<branch>` even one push behind, `HEAD`, or a base branch that merged one of the build's commits), meaning its merge base with `HEAD` has the oldest commit of `git rev-list --first-parent --reverse <base>..HEAD` in its history, folds `status: "indeterminate"` with `reason: "size-base-ref-contains-head"`, never a short count. A fast-forward of the base branch into a build with no commits of its own reads the same way.
- Without the flag nothing changes.

### Review: a check that could not run never dismisses a finding

- A break-it run whose output shows a missing command or module reads `not-run`, never `failed` or `passed`, at any exit code. The reason `module-not-found` is new, and `command-not-found` now also covers a run that exits 127 or prints `command not found`, even when the signature was printed early in a long output.
- `verification.apply_verdicts` returns a new `notExecuted` list, and the round `verify` record carries it. A REFUTED whose reason or evidence shows a check that did not execute is kept as an unverified PLAUSIBLE finding, not dropped.
- New decision kind `verifier-not-executed`, recorded once per kept finding.

### Review records name a grounding seat the loop did not run

- A review record for an auto-fix loop review whose seat map composes the grounding seat now lists it under `seatsNotRun` as `{name, reason: "no-loop-phase", why}`. Before, the record left it out. A record with no such seat has no `seatsNotRun` key.
- The entry does not park the PR, does not make the record read not reviewed, and does not hold it at vet. The vet reads the PR body's claims against the diff by hand and says so in its receipt.
- A hand-written account of a loop review should carry `notRunReason: "no-loop-phase"` on its `grounding-seat` row (planned, not run, no run directory, no commit). The writer refuses the field anywhere else.

### Handback: owner-run commands live in a file

- `vet_slot.py handback` has a new refusal token, `owner-command-in-body`. It refuses a body that holds a fenced `bash`, `sh`, `zsh`, `shell`, `console`, `shell-session`, `sh-session`, `shellsession`, `terminal`, `shell-script`, `ksh`, `fish`, plain-text (`text`, `txt` or `plaintext`) or no-language block, nested in a list or a blockquote too, whose code names `mongosh`, `mongo`, `mongodump`, `mongorestore`, `psql`, `pg_dump`, `pg_restore`, `mysql`, `mysqldump`, `redis-cli` or `sqlite3`, or names `security find-generic-password` or `security find-internet-password`. The refusal names the block.
- These pass: other fences, inline code, a shell comment (unless it holds a `$(…)` or backtick substitution), and a block wholly inside an HTML comment.
- A shell block that only mentions a tool, such as `pytest -k psql`, `brew install mongosh` or `echo mongosh`, is refused too. Move it into the file or reword it. The check reads what a block names, not how it is run, and over-refusing is the accepted direction.
- The body tells the owner to run the file (`bash <path>`) rather than paste its lines, because a pasted block can run differently in the owner's shell.
- `write` and `check` are unchanged.
- Known residual: a tool reached only through an alias, a function or a variable (`$DB`) passes. The review panel and the vet remain the backstop.

### Review record: CI green needs the project's CI workflow

- The record's `ci` field has two new keys: `workflow` (the declared CI workflow, or `null`) and `read` (one line saying how the state was reached).
- `ci_state` reads `none` where it read `green` from third-party statuses alone, and takes the workflow runs and the declaration as two more arguments.
- `_check_data` returns three parts: the check runs, the combined status and the workflow runs.
- Configuration item 16, `ciWorkflow`, holds the name of the project's CI workflow.
- With no workflow declared, an unfinished workflow run on the commit reads `pending`, and only workflow runs whose `head_sha` is the commit count; `_check_data` keeps only workflow runs whose `head_sha` is the commit read.

### Cloud setup text: project setup commands

- Configuration item 17, `cloudSetupCommands`, holds an ordered list of one-line shell commands. Its refusals on `set` are `setup-commands-not-a-list`, `setup-command-empty`, `setup-command-multi-line` and `setup-command-secret-shaped`. `[]` clears it.
- `setup-command-secret-shaped` is the setup text's own secret scan and no stricter rule: an entry is refused exactly when that scan refuses it. A credential never goes in a listed command; put it in the cloud environment's variables and reference it as `$NAME`. The scan catches obvious pastes and is not a guarantee.
- With the list unset, the setup text, its stamp and every result key are what they were before.
- With the list stored as `[]`, the stamp and every result key are what they were before, and the setup text removes `cloud-setup-stamp` (it already did so when it places calibration files), so a stamp an earlier list left does not survive a re-paste.
- With a list, the setup text runs each command once, in order, in the project's clone, after every other step and before the marker line. It logs `setup command <n> ok` or `setup command <n> FAILED`, and the first failure skips the rest.
- The stamp covers the list under the key `setup-commands`, in both storage modes, so a changed list reads as out of date until new setup text is pasted.
- A project that keeps its calibration in the repository and lists commands now gets a stamp, and its setup text logs `calibration: 0 of 0 files written` when it writes it.
- The compose result's `calibration` gains `setupCommands` (the number of commands) when the list is not empty, and has no such key otherwise.
- `compose` refuses `setup-commands-malformed` when the stored value is not a valid list, and `setup-commands-unreadable` when the project's calibration cannot be read for it.
- The setup message (`cloud_check.py setup-text`) no longer tells the owner to add steps by hand under the marker line; it points to item 17.

### Cloud setup text: setup inputs join the stamp

- Configuration item 18, `cloudSetupInputs`, holds a list of repository-relative file paths the setup commands depend on. Its refusals on `set` are `malformed-value` (the value is not a list) and `setup-input-unsafe-path` (an entry is not a plain repository-relative path). `[]` stores an empty list.
- Setting item 17 to a non-empty list fills item 18 when item 18 was never stored. The fill is the files directly in the repository root whose names are in the plugin's lockfile list or match `requirements*.txt`, sorted, and the `set` result gains `inputsFilled` with them. It is `[]` when the root holds none, and it never overwrites a stored list, including a stored `[]`. A detected name item 18 would refuse (such as `requirements dev.txt`) is left out of the list. If the fill's write or read-back fails, item 17 stays stored, the result gains `inputsFillFailed` with the reason instead of `inputsFilled`, and item 18 stays unset. When the repository root cannot be resolved (outside a git checkout, or git failing) the fill is skipped, item 17 stays stored, and the result carries `inputsFillFailed: "repo-root-unavailable"` with no `inputsFilled`.
- A project with setup commands and a stored item 18 gets stamp keys `setup-inputs` (the list), `setup-input/<path>` (each listed file's bytes) and `setup-input-missing/<path>` (a listed path that does not exist), so a changed list, a changed file or a deleted file reads as out of date until new setup text is pasted.
- `compose` refuses `setup-inputs-malformed` when the stored list fails validation, and `setup-inputs-unreadable` when a listed path exists but is not a readable regular file, when the repository root cannot be found, or when the project's calibration cannot be read for item 18.
- A project with no setup commands has the same stamp and setup text whatever item 18 holds, and item 18 is not read.
- A project that already lists setup commands has no item 18 until it sets one or lists commands again after clearing them, so its stamp is unchanged until then.

## 0.44.0

### Before you upgrade

Check these in a consuming project when it adopts 0.44.0. Each step names the note it comes from.

- **After switching.** **A project with cloud builds on needs new setup text in each cloud environment.** The cloud keeps the plugin version its setup text was made at, so once the advisor's seat runs 0.44.0, every build it sends to the cloud runs on the owner's machine until the owner pastes new setup text for 0.44.0 into each account's environment and the advisor checks again (say "setup text", then "check again"). A project without cloud builds has nothing to do.
- **After switching.** **Before each cloud launch, put the launching checkout on its base, pushed.** A cloud launch now refuses when the checkout is off its base; on `main`, a `git pull --ff-only` right before the launch is enough. See [Launcher: cloud launch](#launcher-cloud-launch).
- **After switching.** **Every leftover in a PR or stack sheet input now needs its spine.** Before building a sheet, give each left-for-owner finding a `leftovers` entry with `why`, `context` and `options` (each leftover option's consequence for this finding, or `"none"`). An input written for the old shape is refused, naming each finding. See [PR sheet: leftovers carry the decision spine](#pr-sheet-leftovers-carry-the-decision-spine).
- **After switching.** **A project that turns on `localSockets` still cannot run claude write dispatches off macOS; `localPorts` now can.** A cloud (Linux) build with `localPorts` on opens; one with `localSockets` on still refuses `engine-config:sandbox-access-unsupported-platform`, though in a cloud session on Linux a builder's implementer orders do not reach that refusal, because they run on the native engine (the channel itself still refuses). See [Claude write sandbox: localPorts opens on Linux](#claude-write-sandbox-localports-opens-on-linux).
- **After switching.** **In a cloud session on Linux, a `localSockets` project's implementer orders run as native subagents through `native_engine.py`, and `route` decides it.** The builder runs `native_engine.py route --cwd <build worktree>` before each implementer order; `native` sends it through the native engine, any other engine keeps `dispatch-write`. See [Native implementer engine](#native-implementer-engine).
- **After switching.** **A project whose verify command names no Python launcher can now set `breakItInterpreter` through configure so its Python break-it tests run.** Without it, a verify command such as `pytest -q`, `uv run pytest`, `make test`, `tox` or `poetry run pytest` leaves those tests not-run, and a review whose fixer fixes a break-it finding parks with certification withheld. See [Break-it tests: a calibrated Python launcher](#break-it-tests-a-calibrated-python-launcher).

### PR sheet: leftovers carry the decision spine

- `pr_sheet.py build` refuses a left-for-owner finding with no `leftovers` entry. An entry is `{why, context, options, ifLeft?, recommendation?}`; `why` and `context` are required non-empty strings, and `ifLeft` replaces the reviewer's consequence text on the card.
- A leftover's `options` is `"none"`, a list of options, or an object giving each of `keep-it`, `fix-in-a-follow-up` and `fix-before-merge` its consequence for this finding. The bare `"leftover"`, which showed the generic consequences, is refused.
- A leftover card's context is now three sections, Why it's yours, What happened and If left, in that order, so its card id changes; sheets already published keep their old cards until republished.

### Claude write sandbox: localPorts opens on Linux

- The unsupported-platform refusal now names only `localSockets` off macOS; the token `engine-config:sandbox-access-unsupported-platform` and the result keys are unchanged.
- A Linux run with `localPorts` journals `access.localPorts: true` and writes `network.allowLocalBinding: true`.

### Native implementer engine

- `native_engine.py` takes five verbs. `route --cwd` returns `ok`, `engine`, `reason` and, for `native`, `why`; `open` returns `ok`, `terminal`, `runDir`, `deadlineAt` and `agent` (`subagent_type`, `model`, `isolation`, `run_in_background`, `promptPath`); `enroll` returns `ok` and `head`; `wait` returns `ok`, `resultPresent`, `deadlinePassed` and `secondsLeft`; `close` returns `ok`, `terminal`, `signal` or `reason`, `forfeited`, `engine`, `bounds`, `servedModel`, and on success `itemCheck` and `collected` (`files`, `patchSha256`).
- A native run's `run-opened` record carries `engine: "native"`, `bounds`, `effectiveEffort` (always null, because the host's subagent dispatch takes no effort), `expectedServedModel` and `deadlineAt`, and no `claudeWriteSandbox`. The run also journals `native-enrolled`, `native-collecting` and `run-closed` records.
- Close tokens, in check order: `native-deadline`, `native-not-enrolled`, `native-binding-mismatch`, `native-worktree-not-isolated`, `native-base-mismatch`, `native-model-unread`, `native-model-mismatch`, `native-result-invalid`; then `items-undelivered`, `item-evidence-unavailable:<cause>`, `native-collect-failed`, `native-collect-incomplete`, `native-collect-interrupted` and `journal-write-failed`. `needs_context` and `blocked` close unforfeited.
- A new PreToolUse hook, `implementer_fence.py`, runs on the `Bash` and `Edit|Write` matchers. It acts only on a `superheroes:implementer` subagent: it records the binding on a native run's enroll command and fences only an implementer enrolled that way (install and network commands, a closed run, a passed deadline). Every other agent, the builder included, is untouched.

### Review record: carried leftovers are re-checked against the head

- A review account (and the full lane's extras file) takes an optional `carriedChecks` list. A left-for-owner finding carried from the earlier record is marked `fixed` only when its check says `fixed`, names the head the record describes as `checkedHead` and a fix commit in that head's history, and gives evidence; every other case keeps it left-for-owner and says why. Each check is listed under the record's new `carriedRechecks`. See `skills/review-code/reference/review-record.md`.

### Break-it tests: a calibrated Python launcher

- `core.md` takes an optional `breakItInterpreter` key: a string naming the launcher break-it tests run under, such as `scripts/pinned-python` or `uv run python`. It is split like a shell would split words and never run through a shell. Absent or `null` means not set, and the launcher is read from the verify command as before.
- `review_code_config.py` output gains `breakItInterpreter`: `null` when not set, the stored string verbatim when it is a string (valid or not), and `""` for any other type, so it fails closed.
- `round_driver.py next` takes `--break-it-interpreter <text>` on a fresh state only; an existing session refuses it `break-it-interpreter-not-fresh-state`. The value, an empty string included, becomes the session's `breakItInterpreter`.
- A break-it run can now be recorded not-run with the new reason `interpreter-key-invalid`: the key is set but is not a valid launcher. It never falls back to the verify command. `interpreter-unavailable` (the launcher failed its readiness probe) and `interpreter-unresolved` (no key, and none found in the verify command) are unchanged.
- A run record's `interpreter`, for a multi-word launcher, is the shell-joined prefix, such as `uv run python`.
- `core_md.py` gains the verbs `break-it-interpreter` (read) and `write-break-it-interpreter` (write, or clear with `--clear`). Read the write result's `action`: only `written` or `noop` means saved. See `skills/configure/reference/view-and-tune.md` and `skills/review-code/reference/auto-fix-loop.md` § Break-it tests.

### Review record: an owner ruling given mid-build reaches the record

- A review account (and the full lane's extras file) takes an optional `ownerRulings` list of `{key, url, words}`, and a decision can now be cited as the new `owner-ruling` kind, with `ref` `{url, words}`.
- A ruling counts only when the writer reads its link as the repository owner's comment, in the PR's own repository, and that comment is a standard chat-ruling record holding the words (see the next bullet). Otherwise the finding stays, or becomes, left-for-owner and the sheet still shows it as a card.
- Only a standard chat-ruling record counts (composed by `lib/canon.py ruling-record`), with the words matched inside its quoted block. A ruling typed as a plain comment, even from the owner's account, is asked again at merge.
- A leftover the owner ruled on during a build no longer comes back on the sheet, provided the ruling's link resolves. See `skills/review-code/reference/review-record.md`.

### Review record: survives the cloud egress, and an unreadable one names where

- The record's JSON writes `/` as `\/`, so a cloud session's URL rewrite cannot change it. Records already posted read as before.
- `read`'s `review-record-unreadable` detail now names the comment and character offset of the break with an excerpt, after the URL it already gave; the reason token and keys are unchanged.

### Fix audit: a same-round fix or a revert is not an unnamed change

- A fix audit that reports a change its finding does not name now clears the fix when the auditor attributes every such change to the review's own record: `unnamedChangeFixes` names findings raised in the same round outside the fix batch (not skipped, ruled out of scope or refuted), and `unnamedChangeReverts` names an unnamed change an earlier audit of the review reported and this fix undoes. The driver checks each id and ref against that record.
- An unnamed change with no claim, or with a claim the record does not bear out, still refuses as before, and an owner ruling that allows the change works as before.
- Audit results take the two optional members `unnamedChangeFixes` and `unnamedChangeReverts` (lists of strings). An audit entry gains `reportedUnnamedChange`, and, when attributed, `attributedChange`, `sameRoundFixes` and `revertedChanges`; the round gains `auditAttributedChange`.
- A review no longer stops at the owner gate when a fix round also fixed a small same-round finding or reverted such an edit.

### Guardian: the coupling lens keeps a baseline past a flat Python layout

- A repo with a flat Python layout (no `__init__.py` under any Python source root) and collectable JS/TS now has its coupling baseline saved on the first sweep. Drift and the JS module-count cliff run against it from the next sweep on. The degraded line naming the Python half still shows on every sweep.
- Any other degradation (a missing tool, a Python file that will not parse, a cliff) is still transient: a transient partial on a first sweep saves nothing, as before.
- The lens's `collectorVersion` is unchanged, so repos that already hold a coupling baseline keep it.

### Launcher: one phone per named iPhone size

- A premise may carry `iphoneModels`, a non-empty list of distinct simulator device-type names (`"iPhone 17"`, `"iPhone 17e"`), valid only beside `"iphoneCheck": true`. Otherwise the launch refuses `premise-iphone-models-invalid`.
- Before it makes anything, the launcher reads `xcrun simctl list devicetypes -j`. A name the inventory lacks refuses `iphone-model-unknown` (with `unknownModels`), and an unreadable inventory refuses `iphone-models-unreadable`. Both refuse at stage `iphone-models`, with no worktree, no phone and no child made.
- It then makes one phone per name, in order, named `superheroes-<launchId>-<n>`. A create that fails is skipped. The launch record keeps `iphoneId` (the first phone) and adds `iphoneIds` (every phone made).
- The builder gets `SUPERHEROES_IPHONE_IDS` (every phone, comma-joined, the first being `SUPERHEROES_IPHONE_ID`) beside `SUPERHEROES_IPHONE_ID`, only when sizes were named and at least one phone was made.
- `iphone_check.py preflight` checks every handed phone, and its `ready` result adds `phones`. `render` refuses a check object whose evidence comes from more than one phone, so the pilot renders one check object per phone.
- The fold's lane view carries `iphoneIds` (a legacy record reads `[iphoneId]`). The reap deletes every one, with one result and one `evidence`/`reap` amendment per phone. A caller that reads the reap's `phones[]` now gets one entry per phone.
- At vet, a piece's `phone` must be among the record's phones, and a launch that named sizes needs a complete check for every size.
- Launches without `iphoneModels` behave exactly as before.

### Hooks: the plugin approves its own iPhone commands

- A third `PreToolUse` command on the `Bash` matcher, `hooks/iphone_allow.py`, runs after the worktree guard. It approves (`permissionDecision: "allow"`) only one plain call, `python3 [-B] <plugin root>/lib/iphone_check.py <verb> …`, where the verb is `preflight`, `boot`, `open`, `drive`, `shot`, `read`, `judge` or `render`. A `drive` call needs an AXe step after `--` that is `tap`, `type`, `button`, `swipe` or `describe-ui`. `judge` may read its step as `judge < <file>`.
- It never denies. Any other command gets no decision from it, so the normal permission flow applies, and the worktree guard still denies what it denies. Direct `axe` calls are not covered.
- It is wired on Claude Code only. The Codex hooks file stays empty.
- A pilot call gets the approval only when it writes the absolute plugin root, one call per command, with no `$ROOT_DIR` variable and no chaining.

### Launcher: cloud launch

- A cloud launch now refuses unless the launching checkout is on a named branch whose local head and whose tip on `origin` are both the premise's `baseCommit`. The new refusal reasons are `launch-cloud-checkout-unreadable`, `launch-cloud-checkout-off-base`, `launch-cloud-checkout-branch-not-on-remote` and `launch-cloud-checkout-remote-unchecked`. Each refusal result carries `checkout`, `checkoutBranch`, `checkoutHead` and `baseCommit`, and `remoteBranchHead` once the remote was asked. These refusals do not fall back to the owner's machine. Put the checkout on the base, pushed, and launch again.

### Adopt-version: before- and after-switching upgrade steps

- `lib/adopt_version.py plan` adds `upgradeSteps` to each `transitionSections` entry: one
  `{line, text, marked, when}` per "Before you upgrade" bullet, `when` being `before-switching` or
  `after-switching`. An unmarked bullet reads `before-switching`. No new refusal.
- adopt-version's step 4 holds only on before-switching owner items. After-switching items are owed:
  step 6 writes an `owed:` line next to the taken-up line, and step 8 names them.

### Canon: a pull request of its own

- Canon may now have a pull request of its own. `rubric/canon-contract.md` § Writing a ruling and
  the showrunner charter's duty 8 used to say Canon never gets one. Now a ruling made inside a
  piece of work still rides that work's pull request. A ruling the advisor holds goes into a
  Canon-only pull request (only Canon's paths change) whenever no pull request of the advisor's own
  is coming soon, and whenever the owner asks for one. It merges on a sheet like any other. The
  held comment (`superheroes:canon-held`) still carries a held ruling until it is committed. No CLI,
  result key or refusal changes.

### Review: a changed calibration file is shown to reviewers, and the record lists what they could not read

- In the cleaned copy a review dispatch builds with `--diff-base`, a changed regular file under exactly `.claude/superheroes/` (a project's calibration, such as `core.md`) is now in full and kept in the review patch. Every other `.claude/` path, a lookalike folder, a case variant, a symlink, and a deleted or renamed-away calibration file stay withheld, as before. A brief check (no `--diff-base`) shows none. The view's result gains `calibrationShown` (the paths shown, or `null` without `--diff-base`); `diffWithheldCount` no longer counts them. The six `sanitizedView` receipt keys are unchanged.
- The review record gains `withheldFromReviewers`: each changed path no outside reviewer could read in full, `[]` when none, `null` when the changed files were not read. It never changes the record's status. The vet reads each listed file by hand (`skills/showrunner/reference/vet-receipt.md`, the review record checks).

### Cloud builders: fixed handback, stop and park comments; recovery can answer `parked`

- A cloud builder posts its handback, stop and park on the issue under one fixed first line each: `Builder handback (cloud build).`, `Builder stop (cloud build).`, `Builder park (cloud build).` (`cloud_builder.py terminal --kind handback|stop|park --text-file <file>`; refusals `kind-invalid`, `text-empty`). The cloud's own footer is tolerated.
- `wave_watch.py` reports `lane-terminal` for a cloud lane as soon as one of those comments is on its issue, not after the quiet window. Several lanes ending together are all reported.
- `cloud_recover.py assess` has a new verdict, `parked` (evidence `builder-stop` or `builder-park`), when the lane's newest terminal comment is an unanswered stop or park newer than anything the builder pushed since. The result gains `parkComment` (the comment's id, url, kind and time) and `parkRead` (`ok`, `failed`, or `null` when not read). A `parked` lane is never recovered: repair a stop, answer a park. Any doubtful read falls back to the answers it gave before.
- Builders on an older plugin still post free-form endings, which the quiet alarm still catches. Builders pick up the headers once the cloud environment runs 0.44.0's setup text (the first step above).

### Publishing a sheet: stage its title

- `lib/sheet_title.py stage --sheet <sheet.json> --project <project> [--slug <slug>] --out <folder>/review-template.html` writes the page with its `<title>` set from the sheet: a PR sheet reads `<project> PR #<number> review sheet`. Publish the staged page and pass no `title`. `theme/review-template.md` § Publishing a sheet adds the step. A sheet published before titles were set keeps "Review sheet" until it is republished.

### Removed: the handback gate and orphaned review code

- `lib/handback_gate.py` and its hook `hooks/handback_receipt_gate.py` (never switched on) are deleted, with about a dozen uncalled functions from the review redesign (some of them in `lib/loop_plan_common.py`, which stays). The gate had allowed every command for several releases. A project that wired the hook in its own settings removes that entry.

### Review-code: a round with nothing left to verify, and break-it runs on the project's interpreter

- A round whose verification leaves no findings now journals the decision kind `synthesis-no-survivors` and sends no `dispatch-synthesis` order; the round folds as if the grouping were empty. Before, it still sent a synthesis order.
- A break-it record's `breakItRun` gains `interpreter`. When `breakItInterpreter` is not set (see [Break-it tests: a calibrated Python launcher](#break-it-tests-a-calibrated-python-launcher)), Python break-it tests now run under the launcher the project's `verifyCommand` names, not a `python` on the PATH. A run that cannot use it ends `outcome: not-run` with the new reason `interpreter-unavailable`, or `interpreter-unresolved` when the verify command names no launcher.
- A fixer order may name a break-it test file that does not exist yet, as long as it resolves inside a root; the fixer runs the record's `run` command with its `interpreter`.
- A verifier phase accepted by hand with nothing to verify no longer adds a planned-reviewer row to the review record.

### Guardian: the ledger records the sweep's decisions

- Each entry in the dispositions JSON may carry a `ledger` object: `disposition` (`filed`, which needs a non-empty `issue`; `accepted` or `declined`, which need a non-empty `reason`; or `triaged-out`), plus optional `issue`, `reason` and `reraiseWhen`. Any other key is refused, and a `degraded` entry cannot carry one.
- With no `ledger`, a `rejected` entry writes a `triaged-out` record with the entry's reason, and a `validated` entry writes nothing.
- `commit-ledger` now writes the sweep's decisions as ledger records, keyed by the surfaced `id` (no longer `ledgerJoin`). Its result gains `decisions` (applied) and `decisionsSkipped` (each with `id`, `from`, `to` and `reason`); an illegal move is skipped and reported, never written.
- `guardian_ledger.write` takes an optional `recompute` callable, with the failure reasons `recompute-failed` and `invalid-records`. `guardian_collect.run_tool` results gain `truncated`, true when the output hit the collector cap. The lenses now also collect on very large repos.

### Cloud checks: an account's recorded environment

- `cloud_environment.py compare` matches an account whose cloud setup record is ready against its recorded environment id, without reading the `/remote-env` picker: `action: matched, reason: recorded`, or `action: mismatched, reason: recorded-differs` with `environment` the recorded id. The new `--moving` flag restores the picker comparison, for when the owner moves an account to another environment.
- So the owner picks an environment only at an account's first setup, or when moving it. A later "check again" reads `cloud_setup.py read` and, when `ready: true`, uses the record's `environment` (`skills/configure/reference/set-up.md` § 6).

## 0.43.0

### Before you upgrade

Check these in a consuming project when it adopts 0.43.0. Each step names the note it comes from.

- **Before switching.** **Finish or abandon every review session opened under 0.42.0.** The certificate machinery retired with this release, and no way back is kept. A review in flight either finishes on 0.42.0 before you upgrade, or restarts once on 0.43.0: its first driver command answers `session-from-earlier-version`, and you run Setup again into a fresh session folder. An engine review run opened before the upgrade reads its result schema as changed, so re-dispatch it. See [Review: what retires](#review-what-retires) and [Review record](#review-record).
- **Before switching.** **The earlier plugin version is not kept runnable after this release.** Downgrading under these changes is not supported. See [Review: what retires](#review-what-retires).
- **After switching.** **After upgrading, run configure once.** `rubric-version` moves from 11 to 13, so each project's review profile reads as behind until configure refreshes it.
- **After switching.** **Do the Risk and trust sitting right after adopting.** The owner of an existing project does the risk sitting with the advisor. It is one conversation that sets how much review each kind of change gets. The project keeps working before the sitting, but until then every change's risk is unclear: every change gets the full lane, the micro lane is unavailable, and every leftover with a real consequence comes to the owner. The sitting lives in configure (view-and-tune's "Set up Risk and trust"). See [Configure: Risk and trust](#configure-risk-and-trust), [Review: the lane follows Risk and trust](#review-the-lane-follows-risk-and-trust) and [Review record](#review-record).
- **After switching.** **After upgrading, record the project's adoption day once:** `lib/review_learning.py adopt --cwd <project> --date <today, UTC>`. Review escapes and the reviewer seats' records count only from that day. See [Review: learning from escapes](#review-learning-from-escapes).
- **After switching.** **Cloud builds are optional.** Nothing changes for a project until the owner opts in through the setup sitting ("set up cloud builds" with the advisor) and switches on configure's Cloud builds item. Once, on each account the builders run on, open Claude Code in the repository root and accept the trust prompt, so the advisor's relay can answer cloud builders. Before the first cloud lane enters a batch, re-arm any watch loop or sweep that was armed from an older build. If the repository's ruleset has extra approval for unattributed changes on, a cloud-built pull request can be refused at merge, and neither the owner nor the advisor can give the approval it asks for, because the pull request is opened under the owner's name. Turning that option off clears it (`skills/showrunner/reference/merge-train.md` § When the repository refuses a cloud-built merge). See [Configure: cloud builds setting](#configure-cloud-builds-setting), [Cloud builds: the setup sitting](#cloud-builds-the-setup-sitting), [Showrunner: answering a cloud builder through the relay](#showrunner-answering-a-cloud-builder-through-the-relay) and [Launch ledger: cloud lanes](#launch-ledger-cloud-lanes).
- **Before switching.** **Update a project's own scripts or checks that call these.** A check that looks for the certificate's files or words now looks for the review record ([Review: what retires](#review-what-retires)). Findings built by hand now carry `consequence` and `consequenceKind`, and a caller that wants an unfixed finding settled as `ruling` supplies `decidedBy` ([Review record](#review-record)). A reader that matches the wave watch's two older event classes now takes `ATTENTION_EVENTS` into account ([Showrunner: builder notes in the wave watch](#showrunner-builder-notes-in-the-wave-watch)). `project_config.py --item threatModel` is now `--item riskAndTrust` ([Configure: Risk and trust](#configure-risk-and-trust)). A `shot` call passing `--page` or `--where` now takes `--run-dir` and `--token` ([Pilot: iPhone screenshot labels](#pilot-iphone-screenshot-labels)).
- **Before switching.** **If the advisor logged go-words or collector dispositions into Canon from a project memory, drop that memory.** The Canon write helper now refuses them and names where each belongs. See [Canon: the write helper and the chat-ruling record](#canon-the-write-helper-and-the-chat-ruling-record).
- **Before switching.** **On an open PR whose body keeps a DoD table or another marked section between the `advisor-vet` and `build-record` markers, move it below the build-record marker.** Until then the advisor's slot write refuses. See [Vet slot: builder content in the slot span refuses](#vet-slot-builder-content-in-the-slot-span-refuses).

### Review record

- Every review on the full, light and micro lanes and review-code's review-only exit now writes one review record, kept as a new marker-tagged comment on the PR for each review session (earlier ones are never edited, and each reviewer's raw output sits in its own linked comment), and read back with the record writer's `read --pr <n>` verb. The full lane builds its account from the review session.
- The findings contract gains a required, nullable `consequence` member, and the record spells the five outcomes as `fixed`, `shown-wrong`, `craft`, `left-for-owner`, `ruling`. Callers that build findings by hand must now emit `consequence` (null is allowed).
- The findings contract gains a required, nullable `consequenceKind` (`code-quality` or `real`). Callers that build findings by hand must now emit it (null is allowed); a finding whose kind is not `code-quality` counts as a real consequence.
- A finding that states no consequence is refused at compile: it is recorded as a compile drop with the reason `no stated consequence` and never enters the review. A caller that sends findings without a `consequence` will see them dropped.
- When a review loop ends, every finding it took in has an outcome. A finding with only a code-quality consequence is decided as `craft`, recorded for the owner's veto. A finding with a real consequence that is left unfixed comes to the owner as `left-for-owner`, unless an on-record decision settles it as `ruling` (an active Canon entry, a recorded residual, or a settled sheet answer). Severity never decides this: a Minor finding with a real consequence comes to the owner, and a code-quality-only Important one is decided as craft.
- The Nit readout cap now collapses only Nits whose kind is `code-quality`, and records each collapsed one as `craft`. A Nit with a real consequence stays in the readout however many there are.
- An out-of-scope ruling no longer settles a finding on its own. With no on-record decision it now comes to the owner as `left-for-owner`; a caller that counted such findings as `ruling` will see them as `left-for-owner`.
- `rule` accepts an optional `decidedBy` (`{kind: canon|residual|sheet-answer, ref}`) to name the decision a ruling rests on, and refuses a malformed one with `ruling-decided-by-malformed`. A caller that wants a ruling to settle a finding as `ruling` must now supply it.
- The advisor's vet now reads the review record. In place of the certified-loop check and the seat-provenance parity check, it checks that the record exists, that the checks ran on the PR's final commit, and that no leftover skipped the owner's review. After a project adopts this release, a full or light PR with no review record is not returned as ready.

A consuming project sees these review-loop changes with the record. A ruling binds the next fix across rewording and replaces earlier guidance. A ruling is always accepted and binds the next fix for its finding: a fix already under way is not stopped, and the next round sends the finding back if the fix went against the ruling. Below-blocking findings are settled when the loop converges, and a finding a guidance or fix ruling names goes to the next fixer. An out-of-scope finding is offered to a fixer at most once. A fix the auditor says changes behaviour its finding does not name is not credited without a ruling that allows it. Each round from 2 on records its focus, either the last round's fixes or wider with the reason, and the review record lists every wider round. An engine review run opened before the upgrade reads its result schema as changed, so re-dispatch it.

### Review: what retires

These retirements ship in the same release as the review record, and never apart from it.

- **The certificate gate.** No review is refused, parked or reported incomplete for lacking a certificate, and the handback gate no longer refuses. The review record replaces the certificate.
- **The planted-bug review control.** No review runs a planted-defect probe. The engine wiring and new-model admission checks stay, and the review record shows which reviewers ran.
- **Moving a review session.** The relocate and re-emit verbs are gone. A session is not moved; a review that needs a new place starts again in a fresh session folder.
- **Starting a review from an earlier session's saved records.** A new review no longer starts from an earlier session's saved records. It starts from round 1 in a fresh session folder, and the next review record accounts for every finding the latest earlier record listed.
- **The exact-head evidence chain.** The head-content blobs and their recomputation check are gone. The review record is judged against the PR's final commit instead.
- A project whose own checks look for the certificate's files or words, namely `certification-receipt.json`, `certification-refusal.json`, a `certified` verdict, or the handback refusal `handback-no-receipt`, now looks for the review record. The review record is a PR comment whose first line is `<!-- superheroes:review-record -->`, read back with `review_record.py read --pr <n>`, with its link in the PR body's build record.
- A review in flight when a project takes this release either finishes on the old version or restarts once on the new one. The first driver command on such a session answers `session-from-earlier-version` and writes `restarted-on-upgrade.json` once. Run Setup again into a fresh session folder; the old folder, with any old certification files, stays on disk, unread.
- A review session open across this upgrade starts again. Sessions from before dispatch history was kept for owner rulings answer `session-from-earlier-version` on the first driver command; run Setup again into a fresh session folder.

### Review: the lane follows Risk and trust

- A change that touches a risk area always gets the full lane. So does any change while a project has set no risk areas, so the micro lane is unavailable for it until the project sets them. The rule's home is `rubric/review-discipline.md` § The lane floor.
- A session or model may raise a change's lane. It may never lower it below that floor.
- A review record whose lane sits below the floor reads not reviewed.

### Review: the full-lane panel follows the lane call

- The full lane's panel is composed from the lane call: the code reviewer, the test role and the grounding seat on every change, plus the security and premortem reviewers when a risk area is touched or risk is unclear. The architecture reviewer leaves the default panel; a seat map can still name it. The seat-map receipt's `roster` is the composed roster, and gains `laneBasis`.
- `seat_map.py compose` gains `--base-ref`. With `--head-sha` it names the change the lane call reads; without them the roster is the full set of five seats.
- Compose reads `enginePreferences.seatPins` from core.md itself. `--pins` overlays them per seat, and a pin that cannot apply is disclosed in the receipt.
- The seat-map compose now runs right after review-code pins the base commit, not in the setup file.

### Review: every reviewer independent of every maker

- A reviewer from a maker's family no longer runs without the owner's word for that change. When the owner gives it, the review record names that reviewer and says "not independent". The light lane's host-model stand-in after a forfeit is gone, and nothing stands in on either single-reviewer lane.
- A panel seat that no reviewer outside the makers' families can fill is recorded `unfilled` and counts as not run. Nothing stands in for it.
- The review loop never seats a fix auditor from a maker's family on its own. With none available, the audit counts as not run. The owner's word for a change admits a same-family reviewer through the review record, not through the loop's auditor seating.
- A light or micro review counts only when the engine's record of the run shows `observation.read == "engaged"`. Otherwise the reviewer runs once more, and a second miss moves the change up to the full lane when an independent full panel can be composed, or parks it.
- A review record that names no maker reads not reviewed.
- A full-lane builder opens its PR as a draft before the review, and marks it ready at handback.
- The seat-map receipt gains `makerFamilies` and `roster`, `seat_map.py compose` gains `--maker-family`, and `review_record.py` gains `reading-next`.

### Review: damaged sessions, long records and the loop's tooling

- A damaged review session repairs itself from its mirror and continues.
- A long review record posts as several comments and reads back whole. A host's attribution footer after a part is ignored. A record whose text changed in transit but still parses is read, and carries `transitDamage`. A record that cannot be parsed no longer blocks the next write. Every new record lists each earlier record that could not be parsed or was changed in transit under `earlierRecordsNotChecked`, and the vet reads those comments directly.
- A session submitted by hand gets a review record too.
- A fix that a later full panel did not raise again reads as fixed.
- The review record re-checks the decisions it cites when it is written, and names the sheet part of each finding.
- A run directory reused with a different prompt now refuses `run-dir-prompt-mismatch` instead of replaying the earlier result.
- A Claude-built PR's grouping pass can sit on codex when the seat map proves that cell live.

### Launcher: cloud launch

- `compose` takes `--place cloud --cloud-environment <id>`, and `preflight` takes `--place`. `launch` takes `--place` as the owner's launch word and refuses a supplied `--cloud-environment` with `launch-cloud-environment-routed`, because the environment comes from the cloud setup record. A `launch` without `--place` runs each build where the project's cloud setting says.
- A cloud launch provisions no worktree, leaves no process on the owner's machine, and pushes no branch. It refuses with `launch-cloud-base-not-on-remote` when the base commit the launch names is not on the remote, read fresh from the remote, and with `launch-cloud-base-remote-unchecked` when the remote could not be asked.
- `canary` refuses a cloud lane with `canary-cloud-lane`, because a cloud lane has no local transcript to read.

### Launch ledger: cloud lanes

- The launch ledger accepts a cloud lane: a `reserved` record with `place: "cloud"`, and a `started` record that names the cloud session. Records without `place` read as before.
- `count`'s `laneDetail` entries gain `place`, and `lanes` gains `cloud`.
- Heartbeat sweep entries gain `place`.
- An older plugin build can still fold a ledger that holds a cloud lane, but it reads the lane as a local one, so its watch reports `builder-exited` for a cloud lane whose session is still working and its sweep reads the lane `unknown`. Before the first cloud lane enters a batch, every watch loop and sweep reading that ledger must run on a build that knows cloud lanes, so re-arm any watch loop armed from an older build first. After a rollback to an older build, treat a `builder-exited` on a cloud lane as unread and check the session in the host's session listing.

### Launcher: repairing a never-started lane

- New verb `repair-lane --repo-root <root> --launch-id <id> [--pending-file <file>] [--evidence <text>] [--no-builder <text>]`. Under the ledger lock it restores a never-started lane's `started` record from a pending record that fits the lane, or, without one, records the lane's terminal event from its `reserved` record, and only when the launch that reserved the lane has stopped (it takes that launch's ownership lock, which the launcher holds from before it writes `reserved` until `launch_build` returns; a live holder refuses whatever the evidence says; a holder confirmed dead, or no lock file, only lets the evidenced assertion proceed). Terminal repair needs `--no-builder <one line naming what you checked>` after checking the host's session listing (cloud) or the worktree (local), because a dead launcher does not prove no builder spawned; without it, and for a local lane whose recorded session transcript exists, it refuses `builder-may-exist` and names what to check. It refuses `builder-may-exist`, `lane-already-started`, `outcome-already-terminal`, `terminal-unknown-launch`, `pending-started-invalid`, `outcome-evidence-empty` and `lane-may-be-launching` (the launch that reserved this lane is still running; wait for it to return, or restore the pending record, which is allowed at any age).
- When the launcher's write of a cloud lane's `started` record reports failure, it re-reads the ledger first: a `started` record that landed (the write succeeded and its sync failed) is never appended a second time, and the failure and `pendingStarted` stand (a visible record does not prove it is durable). The `cloud-started-append-failed` and unconfirmed-append remedies now say to read the ledger and name `repair-lane`.

### Review: the PR sheet builder

- `pr_sheet.py build` makes a PR sheet's data file from the PR's review record and the advisor's input, `pr-sheet-input/1`, whose shape its module docstring defines. A stack that merges whole gets one sheet from all its records.
- `theme/sheet.schema.json` gains the `pr` and `stack` sheet kinds, and on those kinds every option carries `sendsBack`. Discovery's remainder, final and plain sheets are unchanged.
- A PR sheet's walk is answerable: Works (or Looks right on a look-only stop), Problem or Skip. A Problem asks whether to fix before merge or in a follow-up, and keeps the merge locked until it is answered. Its pictures are copied into the sheet's own published files, never linked by URL. The advisor's input `walk` is now an object (its shape is in `lib/pr_sheet.py`), and a PR sheet is published with the `assets` capability as well.
- `pr_sheet.py index` builds the index from the advisor's `index-input/1` and each PR's sheet and store dump; a PR sheet's answer saves carry `revision` and a Merge verdict carries `covers`.

### Pilot: iPhone typing helper

- `drive` now checks the phone's typing helper before every step except `describe-ui`, `list-simulators` and `screenshot`, and restarts it inside the handed phone when it is down. Its result gains `helper`: `up`, `restarted` or `down` (absent when a call never returned).
- When the helper stays down, `drive` sends nothing and returns `ok: false` with `reason: "the phone's typing helper is not running"`; the pilot ends that part with `iPhone check did not run — <part>: the phone's typing helper is not running`. Before, such keystrokes were dropped while `drive` reported `ok: true`.
- A checked step makes up to three extra simulator calls inside its `--timeout` (about 0.25 s when the helper is up).

### Pilot: iPhone screenshot labels

- `shot` no longer takes `--page` or `--where`. It takes `--run-dir` and `--token` (the session `open` returned) and labels `page` and `where` from the page readings posted during the capture. Callers passing `--page` or `--where` now fail with an argument error.
- When `shot` cannot establish a label, that label reads `could not be established`. The result gains a `labelNote` key: `null` when both labels were established, else a sentence saying why. The vet rules such a piece invalid.
- `render` refuses a screenshot whose `where` is not `browser`, `installed` or `could not be established`.

### Discovery: no Claude Design

- Discovery no longer asks the owner whether the project uses Claude Design or whether approved boards sync to it, and it no longer syncs an approved board anywhere. The approved build board is still saved as files with the spec, as before.
- A board's design system now comes from the project's own design-system files (tokens, stylesheets, components). A project whose design system lives only in Claude Design gets the "no design system" board until it keeps its design-system files in the project.
- A project whose Canon holds Claude Design rulings may leave them; nothing reads them any more.

### Configure: cloud builds setting

- New configuration item 15, slug `cloudBuilds` (in `projectConfiguration`), "Cloud builds". It is off by default, and nothing changes for a project while it is off.
- `set --item cloudBuilds` refuses `true` with the reason `cloud-setup-missing` while the project has no cloud setup on the launching Claude account. The result's `message` carries the words to say to the owner. Switching off keeps the setup.
- New `lib/cloud_setup.py`. Its `read` answers the setting and the setup record for an account, and `record-check` and `confirm-pass` are the record's only writers. The record lives in the project's store, outside the repository, and holds no secret.

### Cloud builds: the setup text and the reviewer pass

- New `lib/cloud_setup_text.py`. Its `write` command prints the setup text an owner pastes into a cloud environment's setup-script field: it fetches the plugin at the commit the owner's machine runs, installs the reviewer's command-line tool and the duplication checker, and, for a project whose calibration is outside the repository, writes that calibration and its stamp. It refuses to print text that holds anything secret-shaped. A setup stays at the plugin version its setup text was written for until new setup text is pasted.
- New `lib/cloud_pass.py`, the pass command. `make`, run on the owner's machine, builds a reviewer pass from a reviewer sign-in kept apart from the main one (by default the directory `.codex-cloud` under the home directory), with its renewal switched off, and puts four environment-variable lines on the clipboard for the cloud environment's variables: `SUPERHEROES_REVIEWER_PASS`, `CLAUDE_CODE_PLUGIN_DIRS` and the reviewer's two renewal endpoints. It writes no file and does not change the setup record. The first run needs a one-time sign-in to that separate sign-in, and the command says so.
- In a cloud session the session-start hook writes the pass into the reviewer's default sign-in file before anything else runs, and adds a `### Reviewer pass` section to the session's bootstrap saying whether the pass is in place. Outside a cloud session the hook is unchanged.
- `cloud_pass.py confirm`, run in a cloud session, prints one line saying whether the reviewer answers with the pass in that environment and the date the pass lapses. `cloud_pass.py record-confirmation`, run on the owner's machine with that line, moves the setup record's lapse date; nothing else moves it.

### Cloud builds: the setup sitting

- A project is set up for cloud builds by asking the advisor to set up cloud builds. The advisor lists four hand steps: make a cloud environment and pick it by name with Claude Code's `/remote-env` picker on the account the builds run on, paste the setup text into it, sign in once to the separate reviewer sign-in, and paste the reviewer pass. It then runs one check session in that environment and reports three results: the cloud's plugin version, its calibration, and whether the reviewer answered.
- New `lib/cloud_environment.py` reads the environment the owner picked from Claude Code's user settings (`remote.defaultEnvironmentId` in `settings.json` under the account's config directory): `snapshot` before the pick, `pick --before <value>` after it (a retry adds `--confirmed <id>`, so an unchanged value equal to the confirmed id is kept, not asked again). `compare --environment <id>` checks the picked environment against the one in use before the pass is made, before the check starts, and before it is judged. A missing or unchanged value is no pick, and the owner is asked to pick again; the owner is never asked for the id.
- New `lib/cloud_check.py` holds the sitting: `setup-message`, `sign-in`, `start`, `report`, `judge` and `setup-text`. `start` and `judge` take `--environment <id>`. A passed check writes the setup record and leaves the cloud-builds setting as it was. A failed check writes nothing and switches cloud builds off when they were on.
- `cloud_pass.py make` takes `--environment <id>` and then adds a fifth line to its block, `SUPERHEROES_CLOUD_ENVIRONMENT`, naming the environment. The check passes only when the session reports that same id, because a cloud launch naming an id that matches no environment lands in the account's default environment without an error. A pass block made without `--environment` fails the check.
- The setup text ends with its tool-steps marker line, a log line and `exit 0`. A project's own install steps go directly under the marker line.

### Showrunner: where builds run

- Once cloud builds are switched on, the launcher decides where each build runs: the setting gives the default, and a launch word overrides it for one build.
- A build that needs something only the owner's machine has runs there. So does every build when the cloud is not ready.
- `launcher.py` gains `report --repo-root <path> --batch <id>`, which prints the launch report as JSON fields `report` and `lanes`, and `still --repo-root <path>`, which prints JSON field `line`. The advisor runs `report` after each launch and `still` before each later message. `still` reads the launch ledger and the cloud's readiness each time and saves nothing. When the ledger cannot be read, `still` refuses with `still-ledger-unreadable` (exit 1).

### Stack layers build in the cloud

- A launch premise carrying `stack` no longer adds a need only the owner's machine has. A stack layer goes to the cloud when the cloud is ready and nothing else needs the owner's machine, and the launch report lists it under "In the cloud". The phone simulator, judged needs, and a Canon or specs kept outside the repository still keep a build on the owner's machine.
- A cloud builder of a stack layer branches at the layer below's head, brings the layers below forward with a `--no-ff` merge, and opens its pull request through `gh api` REST with the layer below's branch as its base. It does not link the stack; its build record lists the link as owed (`skills/workhorse/reference/cloud.md` § Workspace).
- The advisor links a cloud-built layer at its handback with `gh stack link` (pull request numbers only), confirms membership with `stack_check.py list`, and records the layer's position in the vet receipt (`skills/showrunner/reference/orchestration.md` § Cloud lanes).

### Workhorse: building in a cloud session

- A builder in a cloud session finds every cloud-path step in the new `skills/workhorse/reference/cloud.md`, reached by a one-line pointer from the charter's sections 1, 2, 3, 10, 11 and 12. Every step names a `cloud_builder.py` verb or a plain `git` or `gh api` command.
- Intake runs `cloud_builder.py intake`: a launch that does not match the session ends the lane as a refusal and builds nothing. The builder pushes after every commit, since the pushed branch is all the advisor can recover.
- When the `gh` probe reports `channel: "rest"`, the preflight write check goes through the session's GitHub tools, and `cloud_builder.py github-channel` names the channel for the rest of the build.
- GitHub reads use the REST stand-ins (`cloud_builder.py pr-json`, `cloud_builder.py repo-json`, `gh api`) in place of `gh pr`, `gh issue` and `gh repo` reads. Stack link and stack check read GraphQL, so a cloud builder of a stack layer leaves them to the advisor and says so in its handback.
- A cloud builder asks the advisor with a builder note on its issue (`cloud_builder.py note`), waits in-turn for the reply window `rubric/review-discipline.md` § Size sets, and with no answer commits, pushes and parks.
- A cloud build hands back only with its review record written. In a cloud session (`CLAUDE_CODE_REMOTE` is `true`), `review_record.py` reads the repository, the pull request and its issue through `gh api` REST, and takes the issue the pull request closes from the body's first line (`Closes #N`) in place of GitHub's closing references. When the writer refuses with `review-record-gh-failed`, or writes a record whose final commit the session reported instead of reading it from the PR, the builder posts a review receipt naming the head it reviewed, leaves the PR not ready, and parks naming the review record as missing.
- `rubric/review-discipline.md` § Size names the builder note as how a cloud builder messages the advisor at the size tripwire.

### Showrunner: builder notes in the wave watch

- The watch reports a cloud builder's note as the event `builder-note`. It ends the `loop` without ending a lane, and it belongs to a third event class, `ATTENTION_EVENTS`, beside `LANE_ENDING_EVENTS` and `BENIGN_EVENTS`. A reader that matches on the two older classes must take the third into account.
- A note keeps firing on every arm until the advisor runs `wave_watch.py note-answered --repo-root <root> --comment-id <id>`, which records it in `builder-notes-answered.json` beside the launch ledger.
- While a batch has a live cloud lane, the watch makes one REST read of the repository's issue comments per tick, conditional on the stored ETag, so an unchanged list costs no rate limit.
- A read that fails is disclosed as `builder-note-unavailable`.

### Showrunner: answering a cloud builder through the relay

- `lib/cloud_relay.py` is new, with three verbs: `ensure` starts the relay, `compose` prepares an answer for it, and `check` reads whether the answer arrived.
- The relay is a background Haiku session per account the builders run on, started from the repository root. One-time setup for the owner: open Claude Code in the repository root once on each builders' account and accept the trust prompt. A refusal with `relay-start-failed` names the untrusted workspace.
- Its state is `cloud-relay.json`, beside the launch ledger.
- A message counts as delivered only when the text the relay sent matches the answer exactly, read from the relay's own session record; the relay's own report of what it sent is not the receipt.
- The advisor runs `note-answered` only after a confirmed delivery, so an undelivered answer leaves the note firing on every arm.

### Showrunner: lapsed-pass parks and the send-back

- `lib/cloud_parked.py` is new, with three verbs: `notice` tells the owner when a cloud build's PR is parked because the reviewer pass lapsed, `send-back` lists the parked PRs that can go back for their review, and `sent` records one sent.
- Its state is `cloud-parked.json`, beside the launch ledger.
- A parked PR goes back only after a cloud session confirms the renewed pass; the pass command alone does not count. It never goes back when it closed first or the owner already let it through.
- The advisor records a PR sent only after the message is delivered. When delivery could not be confirmed it runs `sent --uncertain`: the PR is never resent on its own and is listed under `uncertain` until the owner decides. A send-back that was not delivered keeps being listed.

### Showrunner: recovering a cloud builder

- `lib/cloud_recover.py` is new, with six verbs: `pushed` reads what the lane pushed, `assess` answers whether the lane is `working`, `unresolved`, `awaiting-handover`, `ask-to-push` or `stopped`, `ask` composes the request to push and hand over, `asked` records that the request went out, `successor` composes the replacement launch from the pushed work, and `message` composes the owner's notice.
- Its state is `cloud-recover.json`, beside the launch ledger.
- `cloud_parked.py send-back` has a new `superseded` list: a parked PR whose lane was replaced is listed there and never messaged.
- Recovery needs the session's listed state as input, which is a host action, and it never recovers a lane whose session reads working with recent activity.

### Cloud builds: cleanup and the reviewer pass at the gardening pass

- `lib/cloud_cleanup.py` is new, with three verbs: `plan` says whether a cloud lane's pull request has merged or closed and what to send its session, `record` records how that request went, and `branch` deletes the pull request's branch when the repository kept it.
- The advisor cleans up a cloud lane only after its pull request merges or closes, the same way for both. While the pull request is open, handed back or parked, nothing is cleaned up. The only step it asks of the owner is the archive prompt, and on a request that could not be confirmed it asks nothing; nothing reminds the owner about an unanswered prompt.
- The gardening pass has a new duty 8: it reads the reviewer pass for a project with a cloud setup, through the new `cloud_setup.py gardening` verb, and says the days left and the lapse date, with `Renew now` when the pass would lapse before the next pass is owed. The gardening record carries that line. Nothing reads the lapse date between passes.
- The label of the pass's list is now "The eight duties, a closed list."; duties 1 to 7 are unchanged.

### Cloud builds: lower-layer cleanup

- A cloud session can no longer write calibration through the tier-override writer or the migration movers; they refuse there.
- A reused process id no longer blocks recording a lane's outcome. This holds for lanes launched from now on: their record keeps the child's start time and command, and a process that differs from them is not the lane's child. Older lanes behave as before.
- The relay check no longer crashes on a timestamp with no zone; it skips that record. It also counts a send as an answer's only when the send opens with that answer's own header line, so a send with no header, or one that quotes another answer's id, is ignored.
- A relay name is now at most 64 characters, with odd characters in the account folder's name replaced by `-`, so a long or unusual folder name no longer stops the relay from starting.
- The owner's message about a finished lane's session is now conditional. It says there will be one prompt if the builder's session has a tool to remove itself, and that the session stays listed until the owner removes it by hand if it has none.
- A parked PR that is already closed or let through gets no renewal advice, and a newer park on a PR that was closed is recorded again. A cloud lane now records its account, so the renewal check no longer reads an explicit default config folder as a different account.

### Cloud builds: headless builders and the cloud container

- Cloud builders start in auto permission mode with the question dialog off (`--disallowedTools AskUserQuestion`), and the setup check session keeps neither.
- Every cloud launch prompt carries one standing-permission sentence from `rubric/launch-doctrine.md`'s new cloud-launch block.
- The setup text now installs `bubblewrap` and `socat` and, when the project has a `.python-version`, its pinned interpreter with `uv python install`. Each step logs `ok` or `FAILED` and never stops the script.
- The cloud builder reference now covers the headless rule, the container's limits, environment-only failures by a two-part test, per-round review findings on the PR, and an oversized review record.
- The wave watch's builder-note answer may also be posted on the issue as the durable record.
- The gardening pass's `Renew now` line now tells the owner to sign the reviewer in again if the date does not move.

### Vet slot: builder content in the slot span refuses

- `vet_slot.py write`, `check` and `handback` refuse with the new token `slot-span-foreign-content` when any other `superheroes:` marker line (a `superheroes:dod-table` table, for example) sits between the `advisor-vet` and `build-record` markers. The detail names the marker, and nothing is written. Before, `write` silently deleted that content along with the old slot text.
- A PR body that keeps its DoD table or other marked sections in that span must move them below the build-record marker before the advisor's write will run. The advisor's own slot text and the builder's reminder comment still write as before.

### Canon: the write helper and the chat-ruling record

- A project's advisor, and every other session, now writes Canon through `lib/canon.py`: `hold` for a ruling held on the collector, `append` for a new entry or held lines. Each takes a declared ground (`owner-call`, `principle`, `ceded-call` or `take-back`) and mints the id.
- The helper refuses, with `canon-stays-out` and the record's home, an entry whose declared ground is a go-word (launch, merge, release, tier, filing, force-push), a collector disposition, or filing or phase bookkeeping. It recognizes only a ruling that is a collector disposition, owner's words that are a bare go-word, and a ruling that records filing with an issue reference. An act written as a full ruling sentence under a valid ground is not caught, so the session's own ground and the advisor's vet still have to catch it. A project whose advisor logged those into Canon from a project memory should drop that memory; the refusal names where each belongs.
- A ruling given in chat now gets the standard chat-ruling record: one dated collector comment quoting the owner's words (`canon.py ruling-record --post` returns its permalink). An issue Anchor cites that permalink, so Canon is no longer the only reachable record of a chat ruling.
- Nothing already in Canon changes, and no sweep is owed. Until a project adopts this release, its advisor writes Canon by hand as before.

### The test role

- The review panel's test seat is now the test role. Its agent is `test-role`, and its findings file and the `Test` dimension are unchanged. The `test-reviewer` agent is gone.
- A `seatPins` entry under `test-reviewer` is read as the test role's pin, with nothing to rewrite. An explicit `test-role` pin wins.
- The test role asks for no test coverage outside the project's risk areas and raises no test-style findings.
- For a change that touches a risk area, the test role writes break-it tests. The review loop runs them in a throwaway copy of the change and keeps each one with the change once its finding is fixed.

### Configure: Risk and trust

- Item 10 is renamed "Risk and trust", and its slug `threatModel` is replaced by `riskAndTrust`. Callers of `project_config.py get --item threatModel` or `set --item threatModel` now get `unknown-slug`.
- `set --item riskAndTrust` takes one half per call: `{"threatModel": ...}` or `{"riskAreas": [...]}`. Setting `riskAreas` replaces the whole list. `get --item riskAndTrust` returns `effective.threatModel` and `effective.riskAreas`.
- A new reader, `lib/risk_areas.py touched --cwd . --path <path>`, says which risk areas a change touches. Its `riskAreas` is `set` (with `touched`) or `not-set` (with a `reason`: `missing`, `empty` or `unreadable`).
- An existing project's threat model carries over unchanged as the first half, and its risk areas start empty.
- The setup sitting lives in configure: set-up § 3.5, or view-and-tune's "Set up Risk and trust" for a project that is already configured.

### The owner's decisions: batches, sheets and the merge word

- Decisions come in three batches. Batch 1 holds what blocks work, in the chat and at the top of the index. Batch 2 holds decisions not tied to one PR, in the chat. Batch 3 is one sheet per PR, built after the first two are carried out.
- The click list is gone.
- The owner's word to merge is a saved "Merge" verdict on the PR's current sheet plus "done" in the chat. A chat message naming PRs is not the word.
  - A head that moves after its sheet was published is judged by the material-consequence line, and doubt counts as material. A move with no material consequence (a base update with no conflict, a mechanical bring-current, a craft fix) keeps the word: the sheet is republished carrying the verdict forward, with a dated note saying what moved and why it is not material.
  - A move that is material starts the verdict over: the sheet shows "This PR changed" and is unsigned. A PR opened after the word, or a layer linked onto a stack, is outside the word.
- A "Fix in a follow-up" answer is the word to file that follow-up.
- After the merge, the advisor writes the answers and the verdict back to the PR.
- Until a project upgrades, its advisor keeps the click list and the chat merge word.

### Review: learning from escapes

- The misses log takes a fourth kind of miss, the review escape: a bug traced to a PR that had a review. The act that finds it logs it, links the PR's review record, and marks it missed or seen and left.
- Each reviewer seat and the review record writer gets a keep-or-retire entry. A seat is judged on what it caught.
- The gardening pass brings calibration proposals in batch 2. A loosening is shaped like a tightening. A change is applied only on the owner's yes and is recorded in Canon.
- Counting starts at the adoption day, so no seat is judged on reviews from before it.
- A complaint that a review took too long gets an answer about the calibration, never a faster loop.

## 0.42.0

### Before you upgrade

- Finish or discard any in-flight review session that holds owner guidance over 2000 bytes, or a fix batch whose guidance, as rendered in the fixer order (each finding's header and quoting included), comes to more than 8000 bytes. Four guidances of about 1,900 bytes each are already enough. Under 0.42.0 its next fixer order refuses instead of carrying cut or missing guidance.
- After upgrading, run configure once. `rubric-version` moves from 10 to 11, so each project's review profile reads as behind until configure refreshes it.
- Launches without `iphoneCheck` behave exactly as before. Nothing else needs doing before you upgrade.

### Review: pinning an external identifier

- Review-base rule 6 now excepts a name whose spelling is fixed outside the repository (a config key, an env-var name, a query parameter, a marker another tool reads): one test pins its literal, and a review seat no longer flags that pin as a copy or as restating the constant. CONVENTIONS §11.3 is the one home of the exception and its reason; the bite-proof rubric and the test-reviewer's literal-pin check point there.
- `rubric-version` in `rubric/review-base.md` moves from 10 to 11, so a project's review profile reads as behind until configure refreshes it.

### Canon: what stays out

- Canon's contract has a new section, What stays out, and where it goes, and a test in What Canon holds. Read both before writing an entry.
- An entry has new rules in An entry (one ruling per entry, scope honesty, UTC dates and times, narrowing an earlier decision) and a new subsection, Rulings that approve wording kept elsewhere.
- Append only, and supersession has a new subsection, Retiring a misfiled entry. Entries a project already merged owe no clean-up.
- `migrate-material-line`'s default `--date` is now the UTC date, not the local date.
- Showrunner duty 2's supersession notice also covers a retirement.

### Launcher: the iPhone check

- New optional premise key `iphoneCheck`, a bool. A launch whose premise carries a non-bool value (`"yes"`, `1`) refuses with `premise-iphone-check-invalid` before anything is created. `false` and absent both mean the check is off.
- With `iphoneCheck: true`, the launcher creates exactly one new phone for the launch, named `superheroes-<launchId>`: an iPhone 17 on the newest installed iOS runtime. The phone is created just before the reservation, outside the ledger lock, and its ID is recorded as `iphoneId` on the `reserved` record. A phone that cannot be created, or output that is not a simulator ID, never fails the launch; the lane spawns without a phone.
- The builder's environment gains two variables. `SUPERHEROES_IPHONE_ID` is the phone's UDID, or `none` when no phone was made. `SUPERHEROES_DEVICE_HUB` is `available` or `unavailable`. Both are always scrubbed from the environment the launch inherits, so a launch without the check never passes them on, and a launch issued from inside an iPhone lane never hands its phone to a lane that has none.
- When Device Hub is not running, the launcher opens it with `open -g -b com.apple.dt.Devices`, which does not bring it to the foreground, and waits up to ten seconds for it to appear. If it does not, the variable reads `unavailable` and the lane still spawns. The launcher never quits Device Hub and never shuts down or erases a simulator. The only simulator it ever deletes is the phone its own launch just made, when the reservation refuses before writing the record.
- Phone creation and the Device Hub check together run under their own 90-second ceiling, and the launch's own deadline is extended by exactly the time they took. Turning the check on never makes a launch time out that would have started without it.
- The launch fold gains two keys on every lane: `iphoneCheck` (a bool, false when the premise does not ask) and `iphoneId` (the UDID, or `None`). A `reserved` record whose `iphoneId` is malformed, or is present without `iphoneCheck: true` in its premise, makes the fold refuse with `fold-bad-field:reserved:iphoneId`. An older fold ignores the new field.
- The launch result gains an `iphone` key when the check is on. On success it is `{"id": <udid or None>, "deviceHub": <value>}`. When the reservation is refused before the record is written, it is `{"id": <udid>, "recorded": false, "deleted": <bool>}`. When the reservation's append fails, it is `{"id": <udid>, "recorded": "uncertain"}`, and the phone is kept.

### Pilot: the iPhone check

- The pilot drives the lane's phone through `lib/iphone_check.py`, a stdlib-only CLI. Its verbs are `preflight`, `boot`, `open`, `drive`, `shot`, `read`, `judge` and `render`. Each prints one JSON object and exits 0 when its `ok` is true. The rules live in `skills/test-pilot-execute/reference/execution-steps.md` § The iPhone check.
- The check runs when `SUPERHEROES_IPHONE_ID` or `SUPERHEROES_DEVICE_HUB` is in the lane's environment (the launcher sets both for an iPhone launch), or when the issue's done-definition names an iPhone check. It needs no browser MCP, so a lane without a browser tool still runs and posts it.
- Readings come from the page. A development-only reporting script on the page posts each reading as JSON to the loopback address in the page URL's `superheroes-reading` query parameter, and `read` listens there for one call. A password field's value is never sent.
- A check that cannot run says so in the results with `iPhone check did not run — <part>: <reason>`, where `<part>` is `browser check`, `installed-app check` or `whole check`. A lane with no phone reads `iPhone check did not run — whole check: no phone for this lane`. Every screenshot and reading carries six labels: `phone`, `model`, `iOS`, `page`, `where`, `source`. A check that did not run never holds the PR.
- A project whose page has no reporting script gets `iPhone check did not run — whole check: the app lacks its reporting script`.
- New guidance for a project adding its reporting script: `skills/test-pilot-init/reference/reporting-script.md`, reached from the test-pilot set-up.
- Nothing changes for lanes launched without the check.

### Review driver: oversized owner-gate guidance refuses

- A `fix-with-guidance` disposition whose guidance is over 2000 bytes (stripped UTF-8) is refused at `present-judgment` submit with the new token `gate-guidance-oversize`; nothing folds and the owner resubmits shorter guidance. On the library `run_loop` path, which has no submit, the fold parks `cannot-certify` with the same token.
- The fixer order no longer truncates guidance and no longer carries the `bytes withheld` line. A render that meets guidance over 2000 bytes refuses with `order-render-refused:gate-guidance-oversize`.
- The ruling path (`rule --file`) now measures stripped text, as the gate does, so guidance that is over 2000 bytes only through surrounding whitespace no longer refuses with `ruling-guidance-oversize`.
- The 8000-byte aggregate cap refuses rather than leave any guidance out. A `present-judgment` submit whose fix batch would carry more guidance than one order's 8000 bytes, counting guidance carried from earlier rounds and rulings, is refused with `gate-guidance-aggregate-oversize`; nothing folds and the owner resubmits shorter. On the library `run_loop` path the fold parks `cannot-certify` with the same token. The measure is the whole batch as one order, so it can refuse a batch the fixer would have split across orders. A render that would still overflow refuses with `order-render-refused:gate-guidance-aggregate-oversize` (or `order-render-refused:ruling-guidance-omitted` when the overflow reaches guidance from a ruling), and no order carries the `not rendered in full` line.
- A session that already folded guidance over 2000 bytes now refuses its next fixer order render with `order-render-refused:gate-guidance-oversize`. A session whose fixer order was already emitted under the old driver, with the `bytes withheld` line or the `not rendered in full` line, should be discarded, not replayed.

### Showrunner: iPhone lanes

- The advisor's launch rule: when the issue's done-definition names an iPhone check, the launch premise carries `"iphoneCheck": true`. The premise names no place to check.
- A new vet row, the iPhone-evidence row, grades each piece of iPhone evidence valid or invalid, and whether the check is complete when the issue names it. The vet receipt gains a triggered-fields row for it.
- New helper `lib/iphone_reap.py` with verbs `phones` and `reap`, both taking `--repo-root` and `--issue`. `reap` deletes a finished lane's phones and writes one `evidence` amendment with value `reap` per phone-carrying launch. There is no new record or amendment kind, so older builds read the ledger unchanged.
- Nothing to do before upgrading.

## 0.41.0

### Before you upgrade

- A project gains `canon.md` the first time a session records a ruling, and an in-repository project also gains a one-line `.gitattributes` beside it.
- A caller that invokes `/superheroes:review-spec` or the deleted `spec_loop_plan` module must switch to discovery's spec checks.
- A caller that invokes `/superheroes:audit-debt` must switch to `/superheroes:guardian`, which replaced it; the reviewer agents no longer take a whole-repo audit mode. The guardian's dependency lens scans Node and Python projects only; a Rust or Go project must run `cargo audit` or `govulncheck` itself, which `audit-debt` used to run when installed.
- A caller that imports `lib/escalation.py` or runs `lib/escalation_resolve.py` must stop; both are deleted.
- **Move configure item 13 into Canon** when you adopt this release: run `python3 -B <plugin root>/lib/project_config.py migrate-material-line --cwd .` from the repository, on the branch the change should ride if Canon lives in the repository. Until you run it, item 13 behaves as before.
- A spec already in review when a project adopts this release finishes on the path it started on unless the owner says otherwise.

### Canon: the record of the owner's decisions

- New contract doc `rubric/canon-contract.md`: what Canon holds, how an entry is written, how sessions read, write and merge it.
- New verb `definition_doc.py canon --root <root>`. It prints one JSON line with five keys: `path`, `home`, `gitRoot`, `exists` and `defaultRef`.
- The issue contract's ruling anchor may now cite a Canon entry by its id.
- Owner stamp for the anchor-resolution amendment: the owner's approval of the spec `aligning-on-what-to-build-6da1ee` on 2026-10-04.

### Configure: who it's for, item 13 in Canon, the spec-reviewer seat

- New configuration item 14, slug `whoItsFor` (in `projectConfiguration`), "Who it's for and what it's for". It has no plugin default and is listed after item 10. Set-up asks for it as its own step.
- Item 13 (`materialConsequenceLine`) can hold the marker `{"canon": "standing-rulings", "migratedOn": "<date>"}`. A read of it reports `source: "canon-pointer"`, and `set` on it then refuses `material-line-in-canon`. To record a new example, write a standing ruling in Canon.
- New verb `project_config.py migrate-material-line --cwd . [--root R] [--session ID] [--date YYYY-MM-DD]`. Its result keys are `action` (`migrated`, `already-adopted`, `pending-default-branch`, or `refused`), `reason`, `detail`, `entries`, `skipped`, `canonPath`, `canonHome`, `commit`, `fetch` and `sanitized`. Its refusal reasons are `profile-absent`, `profile-unparseable`, `profile-structurally-ambiguous`, `behind`, `malformed-value`, `session-id-malformed`, `date-malformed`, `canon-lookup-refused`, `canon-git-root-not-a-repo`, `canon-dirty`, `canon-default-probe-failed`, `canon-commit-failed`, `canon-write-failed`, `canon-id-conflict`, `material-line-changed-during-migration`, `material-line-changed-since-migration`, `canon-lock-contended` and `marker-write-failed`. The action `pending-default-branch` has a null `reason`. It means the Canon entries are committed on the current branch and the default branch does not yet hold every ruling, so item 13 keeps its value. When Canon lives in the repository the move always finishes in two steps, wherever the project's calibration lives, unless the entries are already on the default branch; a repository with no origin default branch stays pending until it has one holding them. Run the move again after the branch lands to write the marker; that run commits nothing new. When Canon lives in the project store, the move finishes in one step. Once the first step has run, item 13's examples cannot change until the move finishes: finish the move first, then record any change in Canon as a new ruling.
- New key `enginePreferences.specReviewer` (an engine token, no model) and new verb `core_md.py write-spec-reviewer --cwd .`. The verb refuses a value that is not a known engine with `spec-reviewer-unknown-engine`; its own write failures report `spec-reviewer-round-trip-refused` and `spec-reviewer-write-failed`. `load_engine_prefs` gains `specReviewer` and `invalidSpecReviewer`.
- `core_md` confirm now keeps `enginePreferences` when it confirms a provisional calibration. Before, it dropped them.
- New `core_md.write_project_config_item_if`, a compare-and-swap write of a single item. It refuses with `item-changed` when the item no longer holds the expected value.

### The three spec checks

- New reference doc `skills/architect-discovery/reference/spec-checks.md`: the three checks discovery runs on a written spec, their reviewer seat, their rounds and their running record.
- New verb `core_md.py spec-reviewer-seat --cwd . --author-engine <engine>` (optionally `--root R`). It is read-only and prints one JSON line with the keys `ok`, `engine`, `model`, `effort`, `family`, `authorEngine`, `authorFamily`, `sameFamily`, `source`, `configured`, `configuredState`, `configuredReason` and `seat`. `source` is `configured`, `cross-family-installed` or `same-family-fallback`. `model` and `effort` are the registry's brief-check cell for `engine`, and `seat` is the bundle to pass to `dispatch-review --mode brief-check` as `--seat`. When `--exclude-engine` (repeatable) leaves no usable engine, it prints `{"ok": false, "reason": "no-usable-reviewer", ...}` with no `engine` or `seat` rather than returning an excluded engine. An unknown `--author-engine` is a usage error (exit 2).
- New verb `definition_doc.py grounding-base --root <root> --dest <dir>`. It fetches the project's default branch and adds a detached worktree at its tip in a new directory. Success prints `ok`, `ref`, `sha` and `path` and exits 0. A refusal prints `ok` (false), `reason` and `detail` on stdout, exits 1 and creates nothing. Its seven refusal reasons are `grounding-base-not-a-repo`, `grounding-base-no-origin`, `grounding-base-default-unknown`, `grounding-base-fetch-failed`, `grounding-base-dest-exists`, `grounding-base-dest-inside-repo` and `grounding-base-worktree-failed`. Release the worktree afterwards with plain `git -C <root> worktree remove <dir>`.

### review-spec retires; every spec gets the three spec checks

- `/superheroes:review-spec` is removed. Discovery runs the three spec checks on every spec (`skills/architect-discovery/reference/spec-checks.md`); there is no separate spec-review command to call.
- Removed lib modules, with nothing replacing them as CLIs: `lib/spec_loop_plan.py` (its `plan`, `record` and `decide` verbs) and `lib/doc_focus_flags.py`. Both are deleted.
- The spec review weight call is gone: no light-or-full call decides how a spec is reviewed. Package reads keep their weight call. Code review's light, full and micro lanes are unchanged.
- The spec's review gate keeps `pending`, `changes-requested` and `passed`. Discovery now records `changes-requested` when the owner asks for changes, and the stale-approval reset (`gate_write.py --mode reset`) is called from spec-checks.md § The review gate. Only the owner's approval writes `passed`.
- Owner stamp for this change: the owner's approval of the spec `aligning-on-what-to-build-6da1ee` on 2026-10-04.

### The advisor's spec vet hands findings back; discovery asks for approval

- The advisor no longer tells the owner a spec is "ready for your approval". Its vet checks the spec against the repo, the other approved specs and Canon, never edits the spec, and returns every finding to discovery in a vet record: a comment on the spec PR marked `<!-- superheroes:spec-vet -->`, or `vet-record.md` beside a stored spec. Discovery's final sheet asks for approval.
- Discovery's step 8 now waits for the advisor's newest vet record to be clean for the current spec, as `skills/showrunner/reference/spec-vet.md` § How discovery learns the vet is done says, instead of waiting for "ready for your approval".
- After the owner approves and says the final sheet is done, the advisor adds the breakdown to the same spec PR (or beside the stored spec) and vets it; one merge word covers both, and the issues file as it merges.
- An owner ruling the advisor receives goes to Canon on a pull request it has open; with none open, it is held in a comment marked `<!-- superheroes:canon-held -->` on the project's standing proposals collector until the next pull request the advisor opens.
- Owner stamp for this change: the owner's approval of the spec `aligning-on-what-to-build-6da1ee` on 2026-10-04.

### Review sheets: answers match the card, the context is the sender's, and discovery sends sheets

- A sheet data file's card `context` is now a list of sections, each `{"title": ..., "blocks": [...]}`, where a block is exactly one of `{"paragraph": ...}`, `{"bullets": [...]}` or `{"quote": ...}` (`theme/sheet.schema.json`, `$defs/section` and `$defs/block`). The fixed `now`, `whyOwner` and `exactText` fields are gone, and a data file that still carries them is refused with its card named. The schema id stays `superheroes-sheet/1`.
- A card with options offers one button per option and **Something else**, and nothing more; a card without options offers **Aligned** and **Discuss**. A stored answer (`answers/<card id>`) may now be `"something-else"`, with `optionId` null. A stored Aligned or Discuss on a card that now has options shows as unanswered, with its note kept; a session reading answers treats it as unanswered and asks, and treats Discuss and Something else as open for chat (`theme/review-template.md` § How answers come back).
- The sheet's yellow app bar scrolls away with the page. Its count and the phone's folded row count Aligned and picked options as settled, and Discuss and Something else as open for chat.
- `lib/sheet_prose.py` prints each card's context sections and offers the same answers as the sheet.
- Discovery now reaches the owner through sheets. It sends remainder sheets for the calls its spec checks leave, keeps them in a `sheets/` folder in the work item, asks whether the spec is ready for vet as its own word, and then opens the spec PR (or hands over the stored spec). After a clean vet it sends a final sheet. Approval needs the owner's saved Approve on the published revision, the owner saying in the chat that the sheet is done, and no answer on the sheet that changes the spec. Discovery's step 8 and `skills/architect-discovery/reference/sheets.md` carry the rest.

### audit-debt retires

- The `audit-debt` skill is removed, along with its entry in the Codex manifest's skills list. `/superheroes:guardian` is the repo-health sweep that replaced it.
- The reviewer agents (`code-reviewer`, `security-reviewer`, `architecture-reviewer`, `test-reviewer`) no longer carry an `audit-debt` mode bullet, and `premortem-reviewer` no longer notes that `audit-debt` does not dispatch it. The full dependency CVE and advisory sweep that `security-reviewer` deferred now points to `/superheroes:guardian`, which covers Node and Python dependencies only.
- The `audit-report` decision-point carrier is removed from the carrier registry.

### The escalation rubric defers to the owner-vs-craft line

- `rubric/escalation-base.md` (escalation-version 5) points at `rubric/owner-vs-craft-line.md` for whose call a choice is, and keeps PROCEED / NOTIFY / GATE as how a call is disclosed: PROCEED and NOTIFY are a craft call recorded for the owner's veto (NOTIFY keeps its undo path and expiry); GATE is an owner call or a hard-floor action, written down and handed back. The hard floor list is unchanged.
- The rubric's routing grounds of its own (where the ground truth lives, reversibility × confidence) and its precedence over a skill's prose are removed.
- `lib/escalation.py` and `lib/escalation_resolve.py` are deleted with their tests and the `eval/escalation/` fixtures. A caller of `escalation_resolve.py` must read the rubric instead.

### Guardian dead-code ids are repo-relative

- Dead-code candidate ids and their stored `path` no longer carry the checkout's absolute path, so a sweep from a different checkout no longer reports every carried dead-code hit as new.
- **One transition sweep** for a baseline written with absolute ids: it reports every current dead-code candidate as new, once, and every old absolute-keyed id as resolved. The old checkout folder is not guessed, because a wrong guess could hide a finding. That sweep stores repo-relative ids, and from the next sweep on the dead-code drift is real again, from any checkout. If one ecosystem's tool cannot run on that sweep (a partial sweep), its old absolute ids are carried unchanged and make the same one-time transition on the first sweep where that tool runs.

## 0.40.0

### Before you upgrade

- **Finish or abandon in-flight claude write runs.** A claude write run opened under 0.39.0 refuses its continuation, because its stored sandbox settings lack the new allow rules; open a fresh dispatch. No setting is rewritten.
- **Claude write sandbox defaults widen for every project:** `npm`, `npx`, `node`, `pnpm`, `yarn` and `ps` run without a prompt (`ps` stays blocked by the sandbox itself), writes under `/tmp` are allowed, and on macOS localhost binding is on (it also allows a bind on 0.0.0.0). Unix-domain socket binds under `/tmp` stay denied. There is no switch back.
- **Size count:** every project's count now leaves package-manager lockfiles out (listed, with their line counts). A project that wants other paths left out sets `sizeExclude` through configure; nothing else is excluded until it does.
- **Implementer dispatches:** to get the size tripwire reported at every fold, pass `--size-base` and `--size-line` on each `dispatch-write` (workhorse dispatch doctrine). A run opened without them, including one opened under 0.39.0, folds as before plus `sizeTripwireAbsent`.
- **Stack layers:** stacks opened on 0.39.0 or earlier keep their "part of" layer links until their PR bodies are edited. A project that already ran "a layer PR closes its own sub-issue" as a recorded override can drop the override.
- **Verify command:** if your calibrated verify command is your full gate, consider changing it to your fast iteration check through configure's "Change the verify command". Existing calibrations aren't rewritten.

### dispatch-write reports the size tripwire at fold

- `dispatch-write` takes two new flags, `--size-base <commit>` and `--size-line <non-negative integer>`. Pass both on every implementer dispatch, launch and continuation. The runner counts the worktree against the base at fold: committed, uncommitted, and untracked files, read-only.
- A folded write run gains `sizeTripwire`. Counted: `{"status": "ok", "base", "line", "tripwireCount", "crossed", "barCount", "deletedFiles", "binary", "untrackedRepos"}`, plus `barExcluded`, `lockfilesExcluded` and `pathsExcluded` when reported; `crossed` is `tripwireCount > line`. Not counted: `{"status": "indeterminate", "base", "line", "reason"}`, plus `detail` when given.
- Five new open-time refusals, reason `unrunnable`, each opening nothing: `size-inputs-incomplete`, `size-line-invalid`, `size-base-not-an-object-id`, `size-base-unresolvable`, and `size-inputs-mismatch` (a continuation passing different values than the run opened with).
- A run opened without the flags, including one opened by an older plugin, folds with `sizeTripwireAbsent: "size-inputs-not-supplied"` instead of `sizeTripwire`. Passing the flags on a later continuation of such a run does not refuse; the flags are ignored. A review run carries neither key.
- Commits the orchestrator types itself are not counted by this, so the builder still counts at each commit.

### Configure advice: the verify command is the fast iteration check

- Configure now advises that the calibrated verify command be the project's fast iteration check (lint, types, the tests the change touched), not its full gate. A build re-runs the verify command after every review fix round and on the final head.
- Setup's verify-command detection now prefers a fast-check script the project already defines; when only a full gate is found, it proposes that and discloses that the owner can replace it.
- Workhorse §8 now says the project's full local gate runs at most once per build, at the final head, and not at all when CI already passed that head; CI is the final word on the suite.
- Existing calibrations are not rewritten. A project whose verify command is its full gate keeps paying for it on every run until its owner changes it, through configure's "Change the verify command" tune item (an explicit `verifyCommand` edit).

### Size count: lockfiles and project-listed paths are left out

- The size count (`lib/size_count.py`) now leaves common package-manager lockfiles out of both `tripwireCount` and `barCount` for every project: `package-lock.json`, `npm-shrinkwrap.json`, `yarn.lock`, `pnpm-lock.yaml`, `bun.lockb`, `uv.lock`, `poetry.lock`, `Pipfile.lock`, `Cargo.lock`, `Gemfile.lock`, `composer.lock` and `go.sum`, matched on the file's base name at any depth. They are listed under the new `lockfilesExcluded` result key (`[{"path", "lines"}]`), present only when non-empty.
- New optional `sizeExclude` key in the `superheroes-core` block of `core.md`: a list of repo-relative globs matched with `fnmatch` against the path, where `*` also crosses `/`. Set and viewed through configure. Matching paths are left out of both counts and listed under the new `pathsExcluded` result key (`[{"path", "lines", "glob"}]`, the first matching glob), present only when the key is declared (`[]` when nothing matched).
- Refusals at read and write: `size-exclude-malformed`, with items `size-exclude-not-a-list`, `size-exclude-entry-not-a-nonempty-string` and `size-exclude-entry-absolute`. On write only: `size-exclude-input-unparseable`.
- `size_count` itself now refuses with `ok: false` and `size-exclude-malformed` (with the `malformed` items) or `size-exclude-unreadable` (with a `detail`) when `core.md` holds a bad or unreadable `sizeExclude`, instead of counting.
- Who sees a change: every project whose diffs touch a lockfile. Only projects that set `sizeExclude` see changes in what else counts. A project wanting test-pilot plans excluded lists `.claude/test-pilot/**` itself.
- The profile schema version is unchanged, so an older plugin that re-calibrates from scratch can drop the key.

### Stack layers close their own sub-issues

- A stack-layer pull request now opens with `Closes #<its own layer sub-issue>` and names the feature issue only with "part of". GitHub shows the link natively and closes the layer's sub-issue when the layer lands on the default branch. No layer merge closes the feature issue. The rule's home is `rubric/native-stacks.md` § Each layer is a sub-issue, item 6.
- The advisor's post-merge step changes from closing each layer sub-issue by hand to reading back that each landed layer's sub-issue is `CLOSED`, closing any GitHub did not close. Every landed layer's sub-issue still gets the merge receipt comment. The feature issue's close stays the advisor's manual step, with its receipt.
- Stacks opened on 0.39.0 or earlier keep their "part of" layer links until a builder or the advisor edits those pull request bodies; the advisor's read-back closes any sub-issue GitHub did not close. A project that already runs this shape as a recorded override can drop the override once it adopts this release.

### Claude write sandbox: node toolchains, localhost and /tmp by default

- The claude write channel now allows the `npm`, `npx`, `node`, `pnpm`, `yarn` and `ps` command families by rule. A rule only skips the approval prompt; the sandbox still confines the command.
- Two defaults are on for every project, with no calibration: localhost binding (macOS only; it also allows a bind on 0.0.0.0), and writes under `/tmp` and `/private/tmp`.
- Still denied: the network beyond the calibrated domains, writes outside the worktree, the git dirs and the temp dirs, writes to `.git/hooks`, the git config files and the worktree pointer files, the runner's own state (the run dir, the supervisor journal root, the worktree lease and the launch ledger root, denied at run open so the `/tmp` default cannot reach them), WebFetch and WebSearch, and any unsandboxed fallback.
- Unix-domain socket binds under `/tmp` stay denied: the runtime's socket grant is a path prefix that would also let a sandboxed command connect to any host process's socket there. A tool that binds a socket in `/tmp` needs a project-side setting (for example mongod `--nounixsocket`, or passing `TMPDIR` through).
- `ps` is still blocked by the sandbox itself, and the `--requires-process-listing` refusal is unchanged.
- The run-opened record gains `claudeWriteSandbox.tmpWriteRoots` and `claudeWriteSandbox.localBinding`, resolved once at open. A record without them emits neither default. Its `claudeWriteSandbox.denyWrite` also lists the runner-state paths above; a run dir, journal root, lease path or ledger root whose resolved path carries a glob character refuses `engine-config:sandbox-roots-unresolvable` at open.
- There is no switch back to the stricter posture; none was asked for.
- Codex and Cursor are unchanged.
- **Finish or abandon in-flight claude write runs before upgrading.** A run opened by an older plugin refuses its continuation, because its stored settings lack the new rules.

## 0.39.0

### Before you upgrade

- **Finish or abandon in-flight claude write runs opened under 0.38.0** before upgrading. A 0.39.0 runner refuses their continuation (see the write-channel section below).
- A project without `sandboxAccess` stays offline. The one default change is the write channel's new Python command allowances (below); nothing else needs action.

### Claude write channel: implementers can run their own Python tests

- Sandboxed Claude implementers now run the commands their orders name for Python tests. Before, python `-X` flags (including the pinned gate command `scripts/pinned-python -B -X pycache_prefix=… -m pytest …`) and `; echo "exit=$?"` were refused with "This command requires approval", and implementers handed back untested work. The channel now allows the `python`, `python3`, `pytest`, `scripts/pinned-python` and `echo` command families by rule. The sandbox still denies the network, writes outside the build roots, and writes to the git hooks and config.
- Still refused: an env-var prefix outside the harness's safe list (`FOO=1 cmd`, `export FOO=1 && cmd`). Set the variable inside the test, or use Python's own `PYTHON*` variables.
- Every project's claude write sandbox settings, configured or not, gain these `permissions.allow` rules; nothing else in the default settings changes.
- On a machine whose managed Claude Code policy excludes one of those commands from the sandbox, that command now runs outside the sandbox without a prompt, as the policy says.
- **Finish or abandon in-flight claude write runs before upgrading.** A claude write run opened by an older plugin refuses its continuation (its stored sandbox settings lack the new allow rules, so the spawn argv check fails); open a fresh dispatch.
- The channel no longer leaves empty `.claude/.cc-writes` directories in the build worktree. They are swept when the run folds, and the folded result gains `ccWritesSweep`. A run that is abandoned rather than folded can still leave them.

### Claude write sandbox: four access options, offline by default

- The sandbox is still offline by default. A project without `sandboxAccess` sees byte-identical sandbox settings.
- A new top-level key, `sandboxAccess`, in `core.md`'s `superheroes-core` JSON block opens access. It has four optional fields: `allowedDomains` (a list of hostnames), `localPorts` (true or false), `localSockets` (true or false), and `extraWritePaths` (a list of absolute paths). A missing key, a missing field, or an absent `core.md` is all off. Set it through configure's view-and-tune; `configure_view.render` shows a `### Sandbox access` block.
- The run-opened record gains `claudeWriteSandbox.access`, the resolved values read once at open. Continuations and spawns reuse it, so a calibration edit does not change a running run. A run opened by 0.38.0 has no such field and continues as all off.
- Two new open-time refusals, each opening nothing: `engine-config:sandbox-access-malformed`, and `engine-config:sandbox-access-unreadable` for a `core.md` that exists but cannot be read, parsed, or resolved. An absent `core.md` is all off, not a refusal.
- Malformed values are refused when the calibration is read, each item naming its field, its reason, and the accepted shape. The reason tokens are `sandbox-access-not-an-object`, `sandbox-access-unknown-field` (a misspelled key is refused, never ignored), `sandbox-access-not-a-list`, `sandbox-access-domain-invalid`, `sandbox-access-not-a-bool`, `sandbox-access-path-not-absolute`, and `sandbox-access-path-is-root`.
- The profile schema version is unchanged, so an older plugin that re-calibrates from scratch can drop the `sandboxAccess` key.

### Review panels consider every installed cross-vendor engine

- Review composition now probes every cross-vendor engine whose CLI is installed (`codex`, `cursor-agent`) plus any a calibration role names, not only the role-named ones. An installed engine that fails its probe stays out of the panel.
- A project with cursor or codex installed but named by no role now gets that engine's seats, at its usage cost. To keep an engine off the panel, uninstall its CLI or pin the seats you need held.
- `compose-liveness`'s `crossVendorEngines` now reports that set. `run`'s `crossVendorEngines` is unchanged.
- A liveness receipt written by 0.38.0 that lacks a newly considered engine re-probes once.

## 0.38.0

### Before you upgrade

- **A project with no implementer setting now gets the sandboxed Claude implementer.** `enginePreferences.implementation` unset (or `claude`) now runs implementer orders through the sandboxed Claude write channel: no network, offline uv, `ps` blocked. Orders whose verification needs the network, uncached Python dependencies or `ps` fail or are refused up front. To use another engine, set `implementation` to `cursor` or `codex` before upgrading.
- **Rename `sonnet-5` pins to `sonnet-5.5`.** A pin or config naming `sonnet-5` is refused as unregistered.
- **Finish or abandon in-flight claude write runs first.** A claude write run opened by an older plugin, or one journaled under `sonnet-5`, cannot be continued; open a fresh dispatch.

### Wave watch: a missing launch ledger refuses

- An arm against a resolved ledger root whose ledger file does not exist now refuses `ledger-unreadable` instead of returning a clean `timer`. A ledger file that exists but holds no records stays clean.
- Every `ledger-unreadable` refusal from `run`, `watch_arm` and `loop` now carries `ledgerPath`, the path the watcher read.

### Claude write channel: a sandboxed shell

- The claude write argv is now `claude -p --model <tok> --effort <effort> --output-format stream-json --verbose --permission-mode acceptEdits --restricted --tools Bash,Edit,Write,Read,Grep,Glob --strict-mcp-config --settings <inline JSON>`, then `--json-schema` at run-open. It replaces the edit-only argv with no shell. The review argv is unchanged.
- The run-opened record gains `claudeWriteSandbox`, the writable roots resolved once at open. Read it there; continuations and spawns reuse it.
- Four new refusals: `engine-config:sandbox-roots-missing`, `engine-config:sandbox-roots-unresolvable`, `engine-config:sandbox-uv-cache-unresolvable`, and `engine-config:sandbox-process-listing-unavailable`. The two `-unresolvable` refusals open nothing.
- `dispatch-write` gains `--requires-process-listing`. Pass it when the order's verification lists processes; a claude write then refuses `engine-config:sandbox-process-listing-unavailable` before any run opens. Codex and cursor ignore it.
- A claude write run opened by an older plugin cannot be continued: it refuses `engine-config:sandbox-roots-missing`. Open a fresh dispatch.
- Sandbox limits: the network is off, uv runs offline (`UV_OFFLINE=1`, so dependencies must already be in the uv cache), `ps` is blocked, and the sandbox's per-user temp dir stays writable (`/tmp/claude-<uid>`), where other Claude sessions' scratch can live.

### Registry: the sonnet row is sonnet-5.5

- The registry id `sonnet-5` is now `sonnet-5.5`, and the alias record reads `sonnet → claude-sonnet-5-5` (harness 2.1.284).
- A pin or config naming `sonnet-5` is refused as unregistered. Name `sonnet-5.5`.
- A run journaled under `sonnet-5` is refused at continuation (`run-dir-seat-mismatch`). Open a fresh dispatch, the same rule the earlier `opus-5` to `opus-5.5` rename followed.
- The `sonnet` dispatch token is unchanged.

### Implementer routing: claude means the sandboxed channel

- `enginePreferences.implementation: claude`, which is also the default when it is unset, now sends implementer orders through `dispatch-write --engine claude`, the sandboxed channel. Before, `claude` meant a native Claude subagent.
- What changes for an unconfigured project: implementers move from native subagents with network access to a sandboxed Claude CLI with no network, offline uv, and `ps` blocked, and every order now leaves a runner journal and `--expect-item` grading.
- To keep cursor or codex as the implementer, set `implementation` to that engine; nothing else changes for those projects.
- `seat_map compose --implementation-engine claude` now reads author family `anthropic` whatever the host model; before, it took the host's family.
- On a known non-Claude host with a claude implementer, the host's family is also excluded from the lens and grounding seats, because review-code's native fixer writes as the host family (degradation `maker-family-split`; `secondary-maker-seated` when no other family is live). Two known limits ship open, owner-accepted: the diversity check still counts the excluded host family as available, so a correct single-family panel is flagged `critical-diversity` (F1); and certification does not refuse a `secondary-maker-seated` seat (F2). Claude hosts are unaffected.

## 0.37.0

### Before you upgrade

- **Update the Codex CLI to 0.159.0 or later.** The codex default is now `gpt-6.1-sol` (GPT-6.1
  Sol) in every codex seat, at each seat's existing effort. An older CLI is refused at preflight
  with `codex-cli-too-old`, before any codex seat runs; Codex CLI 0.158.0 and older cannot dispatch
  `gpt-6.1-sol` under a ChatGPT account.
- **A `gpt-6-sol` pin keeps working.** `gpt-6-sol` is now pin-only, like `gpt-5.6-sol`: a pin runs
  it at the pinned role's own effort, and no default names it. A `gpt-5.6-terra` pin is still
  refused, and the refusal now names `gpt-6.1-sol` as the replacement.

### Control probe: plant detection

- The planted-defect control probe counts a Critical finding on the planted file at a line inside the planted hunk as catching the plant, alongside a finding that names `verify_submission`; a finding on another file, outside the hunk, or below Critical does not count.

### Engine dispatch: result rewrites, dirtied paths, attempt telemetry

- A native result file rewritten with different valid content before the deadline is now admitted. The completion stamp follows the latest content observed at or before the deadline. Content first seen after the deadline still forfeits `result-completion-payload-mismatch`.
- A `worktree-dirtied-by-attempt` forfeit now carries `dirtiedPaths`: `status`, `paths`, `headMoved` and `truncated`, or `status: indeterminate` with a `reason`. It lists paths whose git status changed plus paths the attempt committed. An edit to a file already dirty at open whose status did not change is not listed.
- Every `attempt-ended` journal record now carries `hostLoadAtOpen`, `hostLoadAtEnd` (1/5/15-minute load, or `null`) and `commandTime` (cursor stream tool and shell seconds, or `null`), and `engine-started` carries `hostLoadAtOpen`. The 900 s default timeout is unchanged.

### Size counter: test-support directories

- The size counter (`lib/size_count.py`) now treats files under a `test-utils`, `test_utils`, `testutils`, `test-helpers`, `test_helpers` or `test-support` directory (any case) as test code, so hand-written test doubles there no longer count toward the non-test size.

## 0.36.0

### Cursor dash-free native result handoff

- Cursor attempts whose canonical native result path contains a run of two or more dashes (`--`)
  now name a dash-free symlink path to that file in the prompt's result line (the bytes still land
  in the run directory at the canonical path).
- The `engine-started` journal record may carry `nativeResultHandoffPath` alongside
  `nativeResultPath` when that handoff is used.
- A new pre-spawn refusal token `native-result-path-unsafe` may appear on cursor attempts when the
  runner cannot create a safe handoff path.
- A killed or interrupted attempt can leave a dangling `superheroes-result-*` symlink in the temp
  directory; deleting it is safe.

## 0.35.1

### Claude background dispatch mode retired

Upgrading from 0.35.0 changes how claude dispatch modes work:

- **Print is the only claude dispatch mode.** Omit `--claude-mode` or pass `--claude-mode print`.
  `--claude-mode` still accepts the retired value `background` only so callers receive a named
  refusal: on `dispatch-review` and `dispatch-write` it refuses before anything spawns with
  `entryReason: claude-mode-retired`, `detail: claude-mode-retired:background`, `attempts: 0` —
  it never falls back to print.
- **Continuing a run opened in background mode is refused.** Re-invoking either dispatch verb on a
  run directory whose journal was opened with `claudeMode: background` refuses with
  `detail: run-dir-claude-mode-retired`, `attempts: 0`; nothing re-opens or spawns.
- **The conformance probe probes only print for claude** (`probedModes: ["print"]`).

Removed with no replacement — print mode has none of them:

- The `claude --bg` launch path and transcript-based result delivery.
- Session suspend, re-attach, and stop-and-confirm of background sessions.
- The `claude-mode-background-write` refusal and the seven `background-*` attempt refusals
  (`lib/background_outcome.py` is deleted).
- Result and journal fields `bgStop`, `backgroundStopUnconfirmed`, `transcriptResult`, and
  `transcriptToolCalls`.
- `dispatch-abandon` stopping a claude session (the runner no longer stops detached background
  sessions).

#### Before you upgrade

- **Re-run the conformance probe for claude into a fresh run directory after upgrading.** A saved
  0.35.0 claude probe result that lists both modes is refused by the preflight entry as
  `probe-result-malformed:<path>`; a caller-supplied probe run directory that still holds a
  `background/` subdirectory refuses `run-dir-not-empty-unopened`.
- **Run operator cleanup once for any detached background session a 0.35.0 run may have left.**
  List sessions with `claude agents --json` (per `CLAUDE_CONFIG_DIR`), and stop any row of kind
  `background` whose cwd is a dispatch sanitized view with `claude stop <id>`. The runner no longer
  does this.
- **Fold any run directory that 0.35.0 opened in background mode.** Run
  `dispatch-abandon --run-dir <dir>` once on each such directory. Until you do,
  `dispatch-poll` still reports the run as running, because a continuation now refuses without
  closing it.

## 0.35.0

### Before you upgrade

Check these in a consuming project before it takes 0.35.0:

- **Read liveness from the watcher, not the heartbeat sweep.** `heartbeat.py sweep` now classes a
  record as `terminal`, `nonterminal`, or `unknown`; the old fresh and stale classes are gone, and
  a script matching them must be updated. See [Heartbeat sweep classes](#heartbeat-sweep-classes).
- **Update a script that matches an `astra-probe-*` refusal token.** The registration probe's
  refusal tokens are now `registration-probe-*`, with no alias. See
  [Registration probe tokens](#registration-probe-tokens).
- **An adoption launch passes `adopts` to re-occupy its own stack position.** Without it the launch
  still refuses `layer-position-occupied`; four new refusal tokens come with it. See
  [Launcher adoption premise](#launcher-adoption-premise).
- **Accept `survivingNonBlocking` in a v5 certification receipt, and never hand-edit
  `rulingsLog`.** The certification loop ships through its rulings channel with one disclosed
  fail-open on a malformed `rulingsLog`. See
  [Certification receipt and the rulings channel](#certification-receipt-and-the-rulings-channel).
- **Accept vet receipt spine fields 9 and 10 in a template or reader of your own.** Every vet
  receipt now carries **Lane** and **Misses-log appends**. See
  [Vet receipt spine fields 9 and 10](#vet-receipt-spine-fields-9-and-10).

### Heartbeat sweep classes

`heartbeat.py sweep` classes each record as `terminal` (the builder stamped `parked` or
`handback`), `nonterminal` (a valid record whose state is not terminal — it says nothing about
liveness), or `unknown`. The old fresh and stale classes are removed, because a builder no longer
promises a stamp cadence: `stamp` still accepts its old cadence argument from older callers and
ignores it, and the window a stamped record carries is always `LIVENESS_QUIET_WINDOW_SECONDS`
(2700 seconds). Liveness has one signal: `wave_watch.py` raises `lane-stale` when a lane's process
is live and the watcher cannot establish that its own session transcript was written within that
window. A cold transcript alerts, and so does an ambiguous or unreadable lookup; a transcript that
does not exist yet alerts only once the same window has passed since the lane's recorded start. The
event means no fresh transcript could be established, not proof of inactivity. A consumer that matched
the old fresh or stale class from the sweep must match `nonterminal` for an unended lane and take
liveness from `lane-stale`.

### Registration probe tokens

One entry changes on the surface listed under
[Astra and the codex role pin](#astra-and-the-codex-role-pin):

- `conformance_probe registration-probe` (`astra-probe` still works as a legacy alias of the verb;
  refusal token `registration-probe-wave-already-attempted` when the same wave is re-attempted with
  a different run dir). The probe's refusal tokens were renamed from `astra-probe-*` to
  `registration-probe-*` with no alias: `registration-probe-scale-unreadable`,
  `registration-probe-ledger-unreadable`, `registration-probe-record-write-failed`,
  `registration-probe-wave-already-attempted`, `registration-probe-seat-unresolved`, and
  `registration-probe-claim-unreadable`. A script that matches an old `astra-probe-*` refusal token
  must be updated.

### Launcher adoption premise

A stacked premise (see [Launcher stacked premise](#launcher-stacked-premise)) may now carry
`adopts`: the pull request number of the existing member an adoption takes over at its own
`layerPosition`. `validate_premise` copies it into the stamped premise like every other key.

`launcher.py launch` narrows one refusal and adds five tokens: `layer-position-occupied` when the
claimed `layerPosition` is already held by an existing member (`layerPosition >= 2` only) and the
premise's `adopts` does not name that member on the layer below's branch; `adopts-occupant-missing`
when `adopts` names a pull request but the claimed position is empty; `adopts-branch-mismatch`
when the premise's adoption pair differs from that member's own branch or head;
`premise-adopts-without-stack`, `premise-adopts-invalid`, and `premise-adopts-bottom-layer` when
`adopts` lacks the stack pair, is not a positive integer, or is on the bottom layer.

### Certification receipt and the rulings channel

On success, `certification-receipt.json` (see
[Certification receipt artifact](#certification-receipt-artifact)) carries the `disclosures` block
with `importantOutOfScope` for Important out-of-scope deferrals and, for a session at state schema
v5, `survivingNonBlocking` for surviving Minor or Nit findings without disposition. A receipt from
an earlier schema (v2–v4, still supported) omits `survivingNonBlocking`. A consumer that enumerates
the block's keys strictly must accept the new one when present.

The certification loop ships through layer 4d-2, where rulings reach the round driver as a declared
input through `round_driver.py rule`. One fail-open ships disclosed: when a session's `rulingsLog`
is malformed, the driver reads it as empty, so an out-of-scope ruling does not hold and its finding
can reach the fixer. Only corrupted or hand-edited state reaches it — `rule` itself refuses
`rulings-log-malformed` rather than write to a malformed log. Record rulings through `rule`; never
edit `rulingsLog` by hand.

### The covenant's merge wording

`rubric/covenant.md` keeps its rule and drops its restatement: promise 1 and the first hard line now
say that nothing merges, releases, publishes, or force-pushes without the owner's word, and point
to `skills/showrunner/SKILL.md` duty 6 as the merge policy's one full statement. Every Claude Code
session on a calibrated project gets the new text from the installed plugin through the
SessionStart bootstrap, so nothing is refreshed by hand there. `configure`'s durable `CLAUDE.md`
offer writes the review-discipline section, not the covenant, and that section's source changed by
one pointer line; a project that took it needs no action. A project that pasted the covenant into
its own `CLAUDE.md` by hand (the only carrier on Codex) holds the longer old wording, which states
the same rule; replacing it with the new `rubric/covenant.md` is optional.

### Skill descriptions as pointers

The skill descriptions are shortened toward when-to-load pointers: each leads with when the skill
applies, and most of the mechanism moves to the skill body, though some descriptions still
summarize what the skill does. No skill name, command, or
`user-invocable` flag changed, so a consuming project has nothing to update.

### Charters as maps

The workhorse, showrunner, and detective charters keep their sections and duties, and much of
their mechanism, including the workhorse and detective excuse tables, moves to reference pages the session reads on demand: `skills/workhorse/reference/`
gains `intake.md`, `orders.md`, `handback.md`, and `excuses.md`; `skills/showrunner/reference/`
gains `routing.md`, `vetting.md`, `orchestration.md`, `provisioning.md`, and `excuses.md`;
`skills/detective/reference/` gains `excuses.md`. Nothing was removed or renamed, and no command or
path a consuming project calls changed. This is informational.

### Vet receipt spine fields 9 and 10

The vet receipt's always-present spine (`skills/showrunner/reference/vet-receipt.md`) grows from
eight fields to ten. Field 9, **Lane**, records the lane the PR ran (`full`, `light`, or `micro`),
with a note when the build escalated. Field 10, **Misses-log appends**, records each misses-log
append the vet made and its class, or `None`. Like every spine field, each is filled or written as
`None`. An advisor session reads the new shape from the installed plugin. A project whose own
template, script, or reader expects exactly eight spine fields must add or accept the two new ones.

## 0.34.0

### Before you upgrade

Check these in a consuming project before it takes 0.34.0:

- **Update the Codex CLI to 0.157.0 or later.** The codex default is now `gpt-6-sol`, and the
  preflight otherwise refuses `codex-cli-too-old`. See
  [Astra and the codex role pin](#astra-and-the-codex-role-pin).
- **Move a `gpt-5.6-terra` pin to `gpt-6-sol`.** A pin or config naming `gpt-5.6-terra` now refuses
  `model-retired`; `gpt-5.6-sol` stays a valid pin. See
  [Astra and the codex role pin](#astra-and-the-codex-role-pin).
- **The owner-authority gate is retired.** Merges run on the owner's scoped word under the merge
  covenant; the hook no longer asks. See [Owner-authority gate retired](#owner-authority-gate-retired).
- **Dispatch CLIs take `--seat` as four-key JSON.** The old `--engine`, `--model`, `--effort`,
  `--engine-model`, `--vendor` and `--role` flags refuse. See
  [Dispatch CLI arguments](#dispatch-cli-arguments).

### Launcher stacked premise

`validate_premise` copies every premise key into the stamped premise. A premise may now carry
`stack` (the GitHub native stack's number), `layerPosition` (this PR's 1-based position in that
stack), optionally `layersPlanned` (the stack's planned layer count), and optionally `dependency`
(the pull request number of an open dependency whose READY vet the launch must be based on).
`stack` and `layerPosition` are optional together — one without the other refuses; `layersPlanned`
requires both.

A stacked launch's stamped premise carries `stack` and `layerPosition`, and `layersPlanned` only
when the launch supplied it — keys a pre-existing consumer never saw; strict key enumeration or
fixed-schema round-trips must accept up to three new stack-metadata keys (`stack`, `layerPosition`,
`layersPlanned`); a launch that also names a `dependency` may add a fourth. A launch that names a
`dependency` carries that key in the stamped premise. A non-stacked launch without a dependency is
unchanged.

A successful launch that ran the dependency gate carries `dependencyGate` on its result. Two
variants: when the gate did not apply, `applied` is `false` and `reason` names why (`dependency-not-open`
for a merged dependency, `dependency-not-ready` for an open draft dependency, before the vet is read
at all however that dependency's slot reads, or for an open dependency whose vet is not READY); a
closed, unmerged dependency refuses the launch with `dependency-closed-unmerged` and carries no
`dependencyGate`. When the gate applied, `applied` is `true` and the object carries `dependency`,
`dependencyHead`, and `verdict` with no `reason` field.

`launcher.py launch` adds thirteen refusal tokens (see `lib/launcher.py`; rule in
`rubric/launch-doctrine.md`): `premise-stack-fields-incomplete` when only one of `stack` or
`layerPosition` is supplied; `premise-stack-field-invalid` when either key is present but not a
positive integer (`bool` is not an integer here); `premise-stack-layers-planned-incomplete` when
`layersPlanned` is supplied and **both** `stack` and `layerPosition` are absent — the pair check runs
first, so when exactly one of the pair is present, with or without `layersPlanned`,
`premise-stack-fields-incomplete` refuses first;
`premise-stack-layers-planned-invalid` when `layersPlanned` is present but not a positive integer
(`bool` is not an integer here); `premise-stack-layers-planned-under-position` when `layersPlanned`
is less than `layerPosition`; `base-not-layer-head` when `layerPosition >= 2` and the resolved base
commit is not the current head of the stack member at position `layerPosition - 1`;
`stack-read-unavailable` when the launcher could not read stack membership and the gate could not
run — the launcher's own token, distinct from `stack_check.py`'s `stack-unreadable` (never aliases,
never interchanged); `order-mismatch` when the membership read found the stack's order inconsistent
with the premise (previously folded into `stack-read-unavailable`, so a consumer matching on
`stack-read-unavailable` for this case must now also match `order-mismatch`);
`layer-position-occupied` when the claimed `layerPosition` is already held by an existing member
(`layerPosition >= 2` only); `premise-dependency-invalid` when `dependency` is present but not a
positive integer (`bool` is not an integer here); `dependency-closed-unmerged` when the premise
names a closed, unmerged dependency pull request; `dependency-open-ready-pr` when the premise
names an open dependency pull request with a READY vet and the resolved base commit is not that pull
request's current head; `dependency-read-unavailable` when the launcher could not read the
dependency pull request or its vet and the gate could not run.

### `launch_ledger.fold` lane stack keys

`fold` puts three keys on **every** lane record — `stack`, `layerPosition` and `layersPlanned` —
derived from that launch's stamped premise, so a strict key enumeration over a lane record must
accept them rather than refuse. The value is `None` when the premise is absent, omits the key, or
carries a value that is not a positive integer (`bool` is not an integer here): a non-positive or
non-integer premise value folds to `None` rather than refusing the fold. The documented signal is
**`None`, never a missing key** — a pre-stack record and a malformed premise read alike.

### `wave_watch.py` `pr-set-changed` payload

The `pr-set-changed` event payload gains `stacks` and `ungrouped`. `stack-signal-unavailable`
joins the degradation set. The existing `prs`, `prsAdded`, and `prsRemoved` keys are unchanged, so
a strict key enumeration must accept the two new ones.

### `wave_watch.py` `stack-state-changed` event

`wave_watch.py` gains a new event, `stack-state-changed`, at precedence rank four — immediately
above `pr-set-changed` and below `builder-exited`. Its payload carries `stacks` (one entry per
stack the batch's launches name, each with `stack`, `state`, `layersPlanned`, `missingPositions`,
and `reason`) and `flags` (today only the idle-seat flag — `FLAG_IDLE_SEAT_LAUNCHABLE_CHILD` in
`lib/wave_watch.py` — naming `stack`, `position`, and `flag`). The event is not suppressible per
lane through `--ignore-event`; naming it refuses `ignore-event-invalid`. Within one `loop`
invocation the stack-state baseline threads across timer arms, so a stack that becomes complete
between arms is reported once; each new invocation starts without one, so a watch armed on a batch
whose stack is already complete, or that already carries the idle-seat flag
(`FLAG_IDLE_SEAT_LAUNCHABLE_CHILD` in `lib/wave_watch.py`), reports `stack-state-changed` on its
first arm.

### `wave_watch.py` loop and run

`run` drops `--max-seconds` and `--interval-seconds` (and the Python `run()` loses `max_seconds`,
`interval_seconds`, and `sleep`; the old windowed function is `watch_arm()`). `run` returns at once
— one ledger read and at most one open-PR read, no waiting. `loop` no longer returns on
`pr-set-changed` or `stack-state-changed`; those are benign wakes passed over and reported at exit.
Every `loop` result gains `passedOver` and `passedOverCount`; a `loop-already-live` refusal gains
`liveLoop`. New refusal tokens: `loop-already-live` and `loop-lock-unavailable`.

### Launcher premise `dependency` field

`validate_premise` accepts an optional `dependency` field on the premise — a positive integer pull
request number, independent of the stack fields. When `dependency` is present but not a positive
integer (`bool` is not an integer here), validation refuses `premise-dependency-invalid`. A stamped
premise carries `dependency` only when the launch supplied a valid one.

### Launcher dependency gate refusals

`launcher.py launch` adds two refusal tokens when the premise names a `dependency` and the
dependency gate runs: `dependency-open-ready-pr` when the dependency is an open pull request
carrying a READY vet and the resolved base commit is not that pull request's current head; and
`dependency-read-unavailable` when the dependency pull request, its head, or its vet could not be
read so the gate could not run.

### `register_check.py check`

`register_check check` gains `--register-copy {auto,main,worktree}`. Two new result keys —
`registerCopy` and `registerRef` — are present on **every** result, including every `undecided`.
The default changed: inside a git work tree the register is now read from main's copy
(`origin/main`, else `main`) rather than the file on disk, and a main read that cannot be resolved
is `undecided` / `register-unreadable` rather than a silent fallback to the worktree copy. A caller
that wants the old behaviour passes `--register-copy worktree`.

### Dispatch-shell exit codes

A dispatch-shell command-line entry point exits **1** when it refuses (returns without doing the
work it was asked to do), **0** otherwise; argparse's own argument errors remain exit **2**. Exit
**0** still never means success — the JSON `ok`/`terminal` fields stay authoritative.

**Consumer-visible change:** `dispatch-review` / `dispatch-write` refusals now exit **1** where they
previously exited **0**. A successful `dispatch-poll` / `dispatch-abandon` still exits **0** even
when its JSON carries `reason: unrunnable` (for example after abandon). `dispatch_guard check` and
`engine_adapter build-argv` exit-code behavior is unchanged from the C10 correction documented
below.

### Command-line Claude result channel

Command-line **claude** is now dispatchable through the shell — `dispatch-review` / `dispatch-write`
with `{"vendor":"claude", …}` no longer refuse `undispatchable-vendor`. A consumer that treated
claude as undispatchable must route it through the sanctioned verbs like codex and cursor.

The argv is `claude -p --model <tok> --effort <effort> --output-format stream-json --verbose`,
plus `--restricted` for the review role or `--permission-mode acceptEdits --restricted` for
the write role, with `--json-schema
<declared schema JSON>` appended at run-open; the prompt arrives on stdin. A claude write dispatch
is edit-only inside the run cwd because no OS sandbox is available through this CLI, so an order
needing to run commands does not route to claude today. `<tok>` is the registry's claude dispatch
token (`haiku`, `sonnet`, `opus`); `fable` refuses `fable-unrunnable`.

The typed result is the `structured_output` member of the **last** `{"type":"result"}` event on
stdout — the final response `--json-schema` governs. That same observation records
`resultCompleteAt`, `resultCompleteEpoch`, and `resultCompleteSha256` on the attempt-ended record
before the process is terminated. The runner **materializes** it to
`<run-dir>/native-result-<n>.json` at attempt end; `attempt-ended.stdoutResult` records
`materialized`, `absent`, `error`, or `occupied`. Only a `materialized` attempt is loaded;
`occupied` forfeits `native-result-path-occupied`; `absent` (no `result` event, `is_error: true`,
or no `structured_output`) and `error` forfeit `native-result-missing`. Admission then runs the
engine-neutral native path unchanged (declared schema, scrub, the `native-result-*` forfeits).
`--output-format json` prints the identical envelope object once at exit; `stream-json --verbose`
prints `assistant` events carrying `tool_use` blocks and then that same envelope as the last line.

Telemetry uses `engagement.source: "claude-stream"`, `telemetry: "tool-calls"`; tool calls are counted
by distinct `tool_use` block id across `assistant` events, **excluding** the `StructuredOutput` call
(it is the result, not activity).

At run-open the shell resolves the target `CLAUDE_CONFIG_DIR` through `lib/config_dir.resolve(env,
cwd)` and records it as `run-opened.configDir`; a value that is not an existing directory refuses at
open with `config-dir-unusable:<why>` (`attempts: 0`). At spawn the same value is injected into the
child env together with `CLAUDE_CODE_EFFORT_LEVEL=<seat effort>`, and `engine-started.env` records
both pins.

Two dispatch modes via `--claude-mode {print,background}` (default `print`). **Print** delivers
through stdout: the runner materializes the last `{"type":"result"}` envelope's
`structured_output` to `<run-dir>/native-result-<n>.json`. **Background** delivers through the
session transcript on `dispatch-review` only — a write dispatch in background mode refuses
`claude-mode-background-write` before spawn; a continuation with a disagreeing mode refuses
`run-dir-claude-mode-mismatch`. Background attempt outcomes can carry
the refusal tokens in `lib/background_outcome.py` (`ALL_REFUSALS`).
Background telemetry is read from the session
transcript's tool calls, not from stdout.

Refusal tokens a consumer can meet on claude: `config-dir-unusable:<why>`,
`claude-mode-background-write`, `run-dir-claude-mode-mismatch`, the background attempt refusals
above, plus the shared native family `native-result-missing`, `native-result-oversized`,
`native-result-malformed`, `native-result-schema-invalid`, `native-result-report-blank`,
`native-result-path-occupied`, `result-completion-unrecorded`, `result-completion-after-deadline`,
`result-completion-payload-mismatch`, `timeout-deadline-unrecorded`, `native-schema-unreadable`,
`marker-channel-retired`; the adapter
refusals `unregistered-engine-model`, `fable-unrunnable`, `invalid-model-effort`, `untokenizable`.

### Builder launch

Builders stay on `claude -p`. The launcher builds the builder command through
`engine_adapter.claude_builder_argv(token, session_id, prompt)` — the one home for every claude
command — whose argv is unchanged (`claude --model <tok> --session-id <uuid> -p <prompt>`; effort
remains pinned through `CLAUDE_CODE_EFFORT_LEVEL`). A caller of `claude_builder_argv` meets the
signature without `effort` or `--bg` and the refusal `builder-session-id-invalid`.

`launcher.py canary --repo-root <r> --launch-id <id>` reports whether a builder lane is engaged from
tool calls in that lane's own session transcript. On success the JSON carries `ok`, `reason` (null),
`launchId`, `sessionId`, `configDir`, `transcriptPath`, `toolCalls`, `truncated`, and `engaged`.
Refusal tokens: `canary-ledger-unreadable:<state>`, `canary-ledger-fold-refused:<reason>`,
`canary-lane-unknown`, `canary-session-id-absent`, `canary-config-dir-absent`,
`canary-transcript-missing`, `canary-transcript-ambiguous`, `canary-transcript-unreadable`,
`canary-transcript-truncated`. A running builder is steered by a message to its registered session
name. Background mode remains a review-seat mode only (`--claude-mode background`).

### Astra and the codex role pin

`gpt-6-astra` is registered as the codex top rung and a valid `reviewer-deep` pin at effort `high`.
A consumer meets:

- the `registration-probe` role the registration probe dispatches under — its cell is now
  `gpt-6-sol` at `high`, which has passed; it stays for any model registered
  probe-pending later;
- `conformance_probe astra-probe` (refusal token `astra-probe-wave-already-attempted` when the same
  wave is re-attempted with a different run dir);
- pin refusal tokens `pin-probe-pending` (for a future probe-pending model), `pin-role-not-eligible`,
  and `pin-not-on-allowlist` (a codex role pin must resolve on its role's own codex allowlist — every
  codex `pilot` pin is refused);
- `model-retired`, refused for any pin or config naming a retired codex model (`gpt-5.6-terra`)
  at load, at the configure write, and at dispatch validation;
- `codex-cli-too-old` and `codex-cli-version-unknown`, refused by the preflight and the
  composition-liveness check when the installed Codex CLI falls short of the registry's floor for
  the models the codex defaults use, or when its version can't be parsed;
- `gpt-5.6-sol`, registered pin-only: never a default, ladder rung, peer, or escalation target, but
  a valid pin for any codex pin role that has a codex cell (reviewer, reviewer-deep, code-fixer,
  implementer), at that role's own effort;
- `seat_map compose` flags `--host-model` and `--implementation-engine` and degradations
  `host-model-unknown`, `role-pin-not-live`, `role-pin-not-honorable`;
- `SUPERHEROES_HOST_MODEL`, exported by the session-start hook from the host payload (empty when
  absent or malformed);
- the receipt's per-seat `model` field (read from the dispatch record, `null` when unrecorded) and
  its unprobed-native disclosure line for claude seats with no runner execution evidence.

### Dispatch CLI arguments

On `engine_dispatch dispatch-review`, `engine_dispatch dispatch-write`, `dispatch_guard check`,
and `engine_adapter build-argv`:

**Dropped (no alias window).** Pass a seat bundle and role instead.

| Dropped flag | Replacement |
| --- | --- |
| `--engine` | `--seat` (vendor lives inside the seat bundle) |
| `--model` | `--seat` |
| `--effort` | `--seat` |
| `--engine-model` | `--seat` (model and effort resolve from the bundle) |
| `--vendor` | `--seat` (vendor lives inside the seat bundle) |
| `--role` | `--seat` (role now rides inside the seat bundle `"role"` key) |
| bare composed-token `--seat` (`"<vendor>:<dispatch-token>"`) | `--seat` as a four-key JSON object; the `model` field still accepts the composed dispatch-token spelling inside JSON |

**Newly required.**

- `--seat` — pass as JSON object `{"vendor": "<vendor>", "model": "<id>|null", "effort": <str|null>, "role": "<role>"}` (the `effort` key is required and its value may be null; `role` is required and must be a valid role — see the accepted seat shapes section of `skills/workhorse/reference/dispatch-entry.md`).

If you pass a dropped flag, the dispatch refuses immediately. The refusal names the replacement and
the accepted `--seat` shape. There is no silent fallback and no alias window for dropped forms.

### Dispatch result shape

Every dispatch result carries `runOpened`. When `runOpened` is true the result also carries a
`resolvedInputs` snapshot; `resolvedInputsStatus` is `pre-upgrade` when the journal predates the
seat bundle (the snapshot is synthesized from the legacy run-opened record), or `journal-corrupt`
when the journal could not be read cleanly (the snapshot is the real opened record — what was
corrupt is elsewhere in the journal). Each snapshot field has a paired `<field>Source` marker; see
the resolvedInputs source markers section of `skills/workhorse/reference/dispatch-entry.md`. Refusals raised
before the run opened carry `runOpened: false` and no snapshot. When the shell could not establish
whether a run had opened — an unreadable journal, corruption without an opened record, or an internal
error while reading the run directory — the result carries `runOpened: false` and
`resolvedInputsStatus: "unverifiable"` rather than claiming either opened-or-not.

Results no longer carry a `ledger` key. Preflight refusals return to the caller in the result body
like every other refusal.

Entry refusals now carry an additive `entryReason` key naming which entry check refused, from the
dispatch shell's closed entry vocabulary, with `entry-reason-undeclared` as its fall-back when a
refusal's own token was outside that vocabulary. **`reason` is unchanged for entry refusals** — it
stays `unrunnable`, and the outcome vocabulary gains no member, so no consumer comparing `reason`
against a hard-coded set needs to change. The presence of `entryReason` marks a refusal raised at
the entry surface; a later preflight refusal carries `reason: unrunnable` and no `entryReason`.

An `engine_adapter build-argv` invocation that refuses now **exits non-zero**; it previously wrote
its refusal payload and exited 0. A caller that read the exit code as success must now read it as
the refusal it always was.

### Composition-liveness cache

The default lifetime for a composition-liveness receipt is 3600 seconds. Set
`SUPERHEROES_LIVENESS_TTL_SECONDS` to configure the lifetime ceiling; a receipt expires at the
shorter of its stamped TTL and that value.

### Registered consumers

**weekly-eats write dispatches** omit effort today. After this release they must pass `--seat` as the
four-key JSON object on every write dispatch, with vendor, model, effort, and role supplied inside
the seat bundle.

### `run_loop` never certifies

`round_driver.run_loop` **never returns a certified receipt.** Consumers reading `receipt["verdict"]`
on the library return get a refusal shape instead: class `unrun-review`, artifact
`driver-journal.jsonl`, plus `loopTerminal` / `loopCertificationShape` / `loopRounds` for loop
observability. The loop still runs; only the certification answer is always a refusal.

### Head-content blobs (`head-content-blobs/2`)

`head-content-blobs.json` is now schema **`head-content-blobs/2`**. The keys `present` and
`fixCommits` are gone; the file carries `schema`, `files` (base64 of the raw bytes read at the
head), and `reads` (one row per read, with `contentDigest`, `bytes`, `readAt`, `source`,
`readError`).

A **legacy-shape blob is refused, not reinterpreted.** A session written before this change refuses
certification of its `fixed` dispositions with binding failure `fix-content-schema-unsupported`.
Silently reinterpreting the old shape could flip a resumed session's certification outcome on a
plugin upgrade alone. A resumed pre-upgrade session must be re-run to certify its fixed
dispositions.

### Certification receipt artifact

At a terminal, the driver now writes a **certification artifact** beside `round-receipt.json`:

- **Success** — `certification-receipt.json`: carries `terminalState`, `terminalCause`, per-seat
  provenance in `seats`, the `disclosures` block (`importantOutOfScope`), and each finding's
  disposition plus its disposition proof (`dispositionReceipt` where applicable).
- **Refusal** — `certification-refusal.json`: names one of the four escape classes
  (`unrun-review`, `same-family-seat`, `unfetched-findings`, `disposition-without-receipt`) and the
  artifact that failed.

`round-receipt.json` and `validate_receipt` are **unchanged** — same required keys, same validator,
same handback gate vocabulary. The certification artifact is separate machinery produced by
`round_certification.certify`.

Until the loop records both a finding's disposition and the cited head on a seat's journal row, the
writer certifies nothing a real review loop produces: a review that raised findings terminates in
the `disposition-without-receipt` refusal, and one that raised no findings terminates in
`unrun-review` with `execution-evidence-head-unbound`. This is fail-closed — nothing certifies on
absent evidence — and certification arrives when the loop records those two facts.

**`certificationShape` rule (writer receipt only).** Any hand-landed seat forces
`audited-chain`, never `full-panel-confirmed` (and any `full-panel*` shape in loop state is
downgraded the same way). The driver's `round-receipt.json` still records the loop's own shape;
only the certification receipt applies this override.

### `run_loop` return contract

`round_driver.run_loop` returns the certification writer's **refusal** directly — always class
`unrun-review`, artifact `driver-journal.jsonl` — plus `loopTerminal`, `loopCertificationShape`,
and `loopRounds`. There is no fallback to a legacy `build_receipt`-only dict and no certified
receipt on the library path.

| Outcome | What you get | How to read it |
| --- | --- | --- |
| Library `run_loop` return | Refusal dict with `class: "unrun-review"`, `artifact: "driver-journal.jsonl"`, plus `loopTerminal`, `loopCertificationShape`, `loopRounds` | No `verdict` key — discriminate on `class`, not `receipt["verdict"]`. `loopTerminal` is what the loop reached; it asserts nothing about certification. |
| Writer fault | Refusal dict with `class: "writer-fault"` | Internal writer crash or empty return during materialization; not one of the four escape classes. |

**Migration.** Callers that tested `receipt["verdict"]` on the `run_loop` return must branch on
`class`, not `verdict`:

```python
result = run_loop(seams, config)
if "class" in result:
    # always unrun-review on the library path — use result.get("loopTerminal") for loop observability
    ...
```

### Codex result channel

Codex review and write dispatches now return their result as a **typed JSON file** on
`--output-schema` and `-o`. The spawn argv is the opened argv plus `--json` (inserted once, before
`-o`) and `-o <run-dir>/native-result-<N>.json --output-schema <run-dir>/native-schema.json`, where
`N` is the attempt number. Stdout is telemetry only — the runner never scans it for a result.

The `run-opened` journal record carries `channel` (`"native"` or `"marker"`) and, on native,
`nativeSchemaPath` (`<run-dir>/native-schema.json`, the declared schema written at open). A resumed
run that predates the field reads as marker.

On a successful codex write, the terminal result carries `report` (the scrubbed report text). On
forfeit, it carries `detail` from the native admission vocabulary: `native-schema-unreadable`,
`native-result-missing`, `native-result-oversized`, `native-result-malformed`,
`native-result-schema-invalid`, `native-result-report-blank`, `native-result-path-occupied`,
`result-completion-unrecorded`, `result-completion-after-deadline`,
`result-completion-payload-mismatch`, `timeout-deadline-unrecorded`, or
`marker-channel-retired`. The dirty-tree forfeit keeps `detail: worktree-dirtied-by-attempt` and
carries `attemptDetail`.

A codex consumer will no longer see: a `salvage` block, `forfeit-with-engaged-artifact` (the
terminal stays `forfeited` with its `native-result-*` detail), `stdout-capped-by-attempt`,
`report-missing-items-delivered` reclassification, or `itemCheck` on a forfeit. `--output-last-message`
and the `attempt-N.last-message` file are gone. A codex run whose opened record is marker (a persisted
pre-upgrade run) never spawns again — its attempt ends with `marker-channel-retired` and the run
forfeits.

Every write run now records `echoNonce` at open, so `run_execution_record` returns `runnerNonce` for
a write run (a resumed pre-upgrade write run without it still answers `runner-nonce-missing`).

The verifier verdict contract requires `reason` as a non-blank string on every ingest path
(`payload_contracts` P_VERIFIERS); hand-submitted verifier artifacts are checked against the same
contract. A whitespace-only `id`, `verdict`, or `reason` faults.

Consumers that read codex findings from the last-message file or the event stream read the folded
`dispatch-review` result instead; consumers that relied on a write salvage block on codex reconstruct
from the worktree diff.

### Cursor result channel and the conformance probe

Cursor's results now come home on the typed-file channel — reviews and writes — with the same
declared schema per run kind as codex. A consumer that read cursor's stream-json stdout for a
result, a `WRITE_REPORT_SENTINEL` tail, or a `salvage` block reads the folded `dispatch-review` /
`dispatch-write` result instead.

The argv is `cursor-agent --model <tok> -p --trust -f --sandbox enabled --output-format
stream-json` for both roles; `--mode plan` is gone. Each attempt stages a per-attempt prompt file
`<run-dir>/prompt-attempt-<n>.md` (the order prompt plus the typed-file contract); `engine-started`
carries `attemptPromptPath` and `attemptPromptSha256`, and the execution record's `promptSha256`
binds the attempt prompt for cursor (`orderPromptSha256` is the caller's order in both).

Refusal tokens a consumer can now meet on cursor: `native-result-missing`,
`native-result-oversized`, `native-result-malformed`, `native-result-schema-invalid`,
`native-result-report-blank`, `native-result-path-occupied`, `result-completion-unrecorded`,
`result-completion-after-deadline`, `result-completion-payload-mismatch`,
`timeout-deadline-unrecorded`, `attempt-prompt-occupied`,
`attempt-prompt-unwritable`, `native-schema-unreadable`, `prompt-unreadable`,
`prompt-tampered`,
`marker-channel-retired`. Tokens that
never mint again for any engine: `stdout-capped-by-attempt`, `report-missing-items-delivered`,
`forfeit-with-engaged-artifact`, and the `salvage` block. No engine remains on the marker channel;
the marker parser, the write-report sentinel contract, the salvage tiers, the delivered-items
classifier, and the stdout-cap forfeit are retired from the supervised path and stay in the tree
only until the gardening pass that deletes them (KEEP-OR-RETIRE S1/S2).

- **Codex** — unchanged since layer 2c: native channel, result path on argv (`-o
  <run-dir>/native-result-<n>.json` with `--output-schema <run-dir>/native-schema.json`), JSONL
  telemetry on `--json`.
- **Cursor** — native channel since layer 3c: result path in the per-attempt prompt file, stream-json
  telemetry (`engagement.source: "cursor-stream"`).

Wave preflight runs `lib/conformance_probe.py` once per dispatchable engine; its result is recorded
as the launcher's `engine-auth` check — the liveness check the dispatch selftest is not.

A runner-journal line that is valid JSON but not an object now counts as interior corruption under
the class `journal-line-not-object`. The launcher's `preflight-failed:<id>` refusal now carries the
walked `checks`, including the failing entry, so the launch ledger keeps the probe's evidence on
refusal.

### Owner-authority gate retired

The `PreToolUse` hook `hooks/owner_authority_gate.py` and its classifier `lib/owner_authority.py`
are gone, so a merge, release, publish, force-push, push-to-default or workflow-run command no
longer stops at a gate prompt. A project store's `owner-authority-allow.json` is no longer read;
it can be deleted. Approval is the owner's scoped word in chat, and merges execute inside it under
the merge covenant (`rubric/covenant.md`, the hard lines).
