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

Check these in a consuming project when it adopts this release. Each step names the note it comes from.

- **After switching.** **An advisor launching an adoption (a premise with `adoptsBranch`) on an issue with an earlier cloud lane that started a session passes the builders' account's session listing with `--cloud-sessions-file`; without it the launch refuses `adopt-original-session-unread`, unless every such lane ended as a refusal or was recorded stopped on a handover. Nothing else is owed.** See [Launcher: an adoption onto a live original cloud builder is refused](#launcher-an-adoption-onto-a-live-original-cloud-builder-is-refused).
- **After switching.** **An advisor building a PR or stack sheet for an open PR whose body lists a `[costly]` or unlabelled deviation with no line under What we're accepting gets a refusal naming each one; the PR's builder labels it or carries its text into What we're accepting, then the sheet builds.** A harmless build deviation stays in the PR body's build record and no longer gets its own merge-sheet card; a costly one keeps its card until its fix lands, and doubt sorts costly. See [Build deviations: only costly ones are accepted on the merge sheet](#build-deviations-only-costly-ones-are-accepted-on-the-merge-sheet).
- **After switching.** **Advisors stop hand-building review records to get a merge sheet for a PR that had no review run.** Such a PR, typically an advisor-vetted dependency bump, gets no merge sheet: the advisor posts its vet receipt and owner half on the PR, and the owner merges it with their own click. See [Showrunner: a PR with no review run gets no merge sheet](#showrunner-a-pr-with-no-review-run-gets-no-merge-sheet).
- **After switching.** **An advisor answering a cloud builder on another account prints the whole composed `relayMessage` and sends exactly that text; nothing else is owed.** A changed answer is composed again, and `cloud_relay.py check`'s `say` sentence for `relay-text-mismatch` no longer says the relay changed the text. See [Relay: the advisor sends exactly the text it was shown](#relay-the-advisor-sends-exactly-the-text-it-was-shown).
- **After switching.** **Nothing is owed, except that a consumer that reads a review record's `status` with a closed set of values must accept `awaits-owner` and treat it as `not-reviewed`.** See [Review record: `awaits-owner` when only owner calls are left](#review-record-awaits-owner-when-only-owner-calls-are-left).
- **After switching.** **Nothing is owed.** A cloud build's implementers and review seats are now told that credential-like text is redacted in a cloud session, and a review record flags a recorded field that arrived redacted. See [Cloud builds: credential-like text is redacted, and the review record says so](#cloud-builds-credential-like-text-is-redacted-and-the-review-record-says-so).
- **After switching.** **Nothing is owed.** Every implementer order now tells the implementer to create and edit files only with the host's Write and Edit tools, so fewer orders stop on a refused shell write. See [Implementer orders: the file-write rule rides every order](#implementer-orders-the-file-write-rule-rides-every-order).
- **After switching.** **Nothing is owed.** An orchestrator that knows no fixer was dispatched for a pending fixer order can pass `rule --fixer-not-dispatched`, and a ruling then re-renders that order at the next attempt; without the flag a ruling leaves an emitted order alone, as before. See [Review rulings: a late ruling re-renders a fixer order nobody has picked up](#review-rulings-a-late-ruling-re-renders-a-fixer-order-nobody-has-picked-up).
- **After switching.** **Nothing is owed.** An orchestrator that closes a review session before its loop ends can write the session's record with `review_record_session.py write ... --abandoned "<why>"`; a write without the flag is unchanged. See [Review record: an abandoned session writes its own record](#review-record-an-abandoned-session-writes-its-own-record).
- **After switching.** **Nothing is owed.** A native implementer's isolated worktree now gets a link to the build worktree's installed dependency folders (`node_modules`), so `npx --no-install <bin>` and `npm run <script>` work there; `enroll` reports it under a new `dependencies` key and `close` removes the link before collecting. See [Native implementer: enroll links the installed dependencies](#native-implementer-enroll-links-the-installed-dependencies).
- **After switching.** **Nothing is owed.** `open` prints one more field in its `agent` object, `launchPrompt`, and the native implementer and the native fixer are dispatched with it. See [Native dispatch: open prints a launch prompt](#native-dispatch-open-prints-a-launch-prompt).
- **After switching.** **Nothing is owed.** In a cloud session on Linux whose calibration turns on `localSockets`, the review's host-seat fixer runs as a native fixer subagent in the build worktree. See [Review fixer: the cloud localSockets route](#review-fixer-the-cloud-localsockets-route).
- **After switching.** **Nothing is owed.** A review's staleness check no longer reports a verify command that opens with a shell keyword (`if [ -x … ]; then …`) as "no longer resolves: if"; it checks the first word that names a program, and reports a command it cannot read as not checked rather than stale. See [Review: the verify-command check skips shell keywords](#review-the-verify-command-check-skips-shell-keywords).
- **After switching.** **Nothing is owed.** The wave watch now watches a terminal cloud lane again once the advisor sends it a fix order (`vet not-ready`, or a relayed fix order composed with `--fix-order`), until the lane's next ending; and a partial comments read names the issues it could not read. See [Wave watch: a cloud lane sent a fix order is watched again](#wave-watch-a-cloud-lane-sent-a-fix-order-is-watched-again).
- **After switching.** **Nothing is owed.** A cloud lane's repeat handback or park after a fix order is recorded in the launch ledger even when it reads exactly like the lane's earlier one, so the ledger alone closes the watch the fix order re-opened. See [Launch ledger: a repeat outcome after a fix order is recorded](#launch-ledger-a-repeat-outcome-after-a-fix-order-is-recorded).
- **After switching.** **Nothing is owed.** A builder's scoped single-reviewer pass after a handback now ends with a review record written on the head it reviewed. See [Workhorse: a scoped pass after a handback writes a review record](#workhorse-a-scoped-pass-after-a-handback-writes-a-review-record).
- **After switching.** **Nothing is owed, except that a project whose test files must carry a directive comment in a longer form keeps that rule written where the test lens reads it: CLAUDE.md, the calibration, or a check in the repository.** See [Review: a break-it test is written in the project's own directive form](#review-a-break-it-test-is-written-in-the-projects-own-directive-form).

### Review: a break-it test is written in the project's own directive form

- A break-it test the test lens supplied in JavaScript or TypeScript with a bare directive comment (a marker the project requires to carry more, such as a reason) was extended to the project's required form when the fixer committed it. The committed file then differed from the one the loop ran, the kept check read `changed`, and the review ended `cannot-certify`.
- `break_it.CONTENT_RULES` now states the rule once: the fixer commits the content byte for byte, the review keeps the test only when it is unchanged, so every marker or directive comment the project's own rules require on a test file (in CLAUDE.md, the calibration, or a check the project runs over its tests) is written in its full required form. The test role's panel order renders it after the run rules, and the paragraph added to `agents/test-role.md` § Break-it tests says the same.
- The keep check is unchanged: kept still means byte-unchanged, or for Python, JavaScript and TypeScript the body match. No command, result key or file shape changes.

### Workhorse: a scoped pass after a handback writes a review record

- Workhorse §12 (`skills/workhorse/SKILL.md`) sends a fix inside an already-reviewed surface to a scoped single-reviewer pass. That pass now ends with `review_record.py write` on the head it reviewed, and the new record relists every finding the earlier record listed, with its outcome, plus the scoped pass's own. §12's table says so in the scoped-pass row.
- Before this, the vet row "the checks ran on the final commit", which reads only the latest record, held every fix round that followed §12 to the letter on a missing record.
- No command, result key or file shape changes.

### Launcher: an adoption onto a live original cloud builder is refused

- A fix leg launched onto a PR whose cloud builder had handed back could meet that builder again: the original session can wake on PR activity after its handback is recorded, and then two builders push to one branch.
- `launcher.py launch` now refuses an adoption (a premise with `adoptsBranch`, local or cloud) when an earlier cloud lane in the launch ledger for the same issue started a session that the listing shows live. It refuses `adopt-original-session-live` with `originalSessions` (each with `launchId`, `cloudSessionName`, `cloudSessionId`, `sessionStatus`, `statusBucket`), or `adopt-original-session-unread` when the listing or a read it needs cannot be used, with `failedRead` naming it (`ledger`, `recover-state`, `listing-not-given`, `listing-file`, `listing-json`, `listing-shape`, or `listing-incomplete`, which also carries `launchIds`). Both land before any worktree, cloud command or child exists, are recorded as a refused lane at stage `original-session`, and carry a `remedy`.
- `launch` gains `--cloud-sessions-file <path>`: the builders' account's session listing, recorded at launch time. It accepts a `list_sessions` result (`{"data": [...], "has_more": ...}`), a `get_session` result (one session object, optionally wrapped as `{"ccr": {...}}`), or a JSON array of such results. A row is not live when its session status contains `ARCHIVED`, its `archived` is true, or its `status_bucket` contains `FAILED`; every other listed row is live, unknown states included. A session missing from the listing counts as gone only when the file is exactly one `list_sessions` page with `has_more: false`, read with no cursor, whose rows run newest-created first and which holds a row of the lane's own cloud environment (`environment_id`) created at least 600 seconds after the lane started, to allow for clock skew. A lane whose session id was never confirmed is never proven gone by absence.
- A lane whose latest outcome is `refusal` (its builder refused at intake and built nothing) is skipped, so `cloud_recover.py relaunch-refusal` keeps working, and so is a lane `cloud_recover.py assess` recorded `stopped` on a handover. A plain handback is not a handover. With no earlier cloud lane for the issue, or every one skipped, no listing is needed and the launch proceeds as before.
- A NOT-READY on a PR whose original cloud builder is still listed live goes to that session by message as the fix order (relayed when the builders' account is another), and a new fix leg is launched only when that session is archived, gone from a complete listing, failed, or recorded stopped on a handover. See `skills/showrunner/reference/orchestration.md` § Adoption mechanics.

### Build deviations: only costly ones are accepted on the merge sheet

A deviation is costly when a promised check did not run, or work bypassed its owner engine, whatever caused it; otherwise it is harmless. The grounding seat not running sorts harmless by name, and the prompt-file pointer, the cloud fixer route, an unreadable host model, a classifier stop and cloud platform limits sort harmless only when the costly test does not apply. Cloud platform limits are the cloud session's own channel limits (no session messages, no comment deletion, no GraphQL reads), never a build check that could not run there. Doubt sorts costly. Every deviation, either class, keeps a bullet under `### Disclosed degradations` in the build record, opening with `[costly]` or `[harmless]`; a bullet with no label reads costly. Only a costly one gets a consequence line under `## What we're accepting`. The merge sheet's `lib/pr_sheet.py` reads acceptances only from that section, and stops at the first `<!-- superheroes:build-record -->` marker line at column 0 after that heading, so a harmless deviation listed only in the build record needs no accounting entry and no card. The omission floor's third row, in CONVENTIONS `§10.7` and its three copy-holders, now reads "every **costly disclosed degradation**". The sheet build also reads the body's degradations list (under `<!-- superheroes:degradations -->`) and refuses, naming the bullet, a `[costly]` or unlabelled deviation whose text after its label appears in no What we're accepting line; a `[harmless]` one never needs a line, and a body with no degradations section is not checked. A body written before the labels reads every deviation as costly.

### Showrunner: a PR with no review run gets no merge sheet

- Duty 6 of the showrunner charter (`skills/showrunner/SKILL.md`, the merge policy's one home) gains one rule: a PR that had no review run, typically a dependency bump the advisor vets directly in place of a review-crew run where the project allows that, gets no merge sheet, and the advisor never hand-builds a review record to make one. The advisor posts its vet receipt and owner half on the PR and tells the owner the PR is theirs to merge with their own click; it executes no merge for such a PR on a chat word. `skills/showrunner/reference/owner-decisions.md` § Delivery mechanics (batch 3) and `theme/review-template.md` (beside `pr_sheet.py build`'s `--record` requirement) point to it.
- Review discipline is unchanged: whether a project's dependency PRs may skip review-crew stays that project's owner's call, and a review record the driver mandate owes for a disclosed skip is still written.
- No command, result key or file shape changes.

### Relay: the advisor sends exactly the text it was shown

- `skills/showrunner/reference/wave-watch.md` § "Another account", steps 2 and 3: the answer text never carries a shell-evaluated value the advisor has not seen expanded (a `$(date -u …)` time inside a heredoc is run first and written in as text); the advisor prints the whole composed `relayMessage`, never a truncated view such as `head` or the message id alone, and sends exactly that text; a change after compose means writing a new answer file and composing a new message, never editing the composed one. Step 4 adds that `check` sees only the relay's send against the stored text, so a mismatch does not say which step changed it.
- `cloud_relay.py check`'s `say` for `relay-text-mismatch` names only what it compares: "The relay's send of message `<id>` differs from the stored text (first difference at character `<n>`); this check sees only that send, so it cannot tell which step changed the text; it was not delivered." With `headerDropped: true` it reads "The relay's send of message `<id>` is the stored text with its header line dropped; it was not delivered." Verdicts, result keys and `firstDifference` are unchanged.

### Review record: `awaits-owner` when only owner calls are left

- A review record whose only open lines are findings left for the owner now reads `awaits-owner` instead of `not-reviewed`, and its summary's first line reads "reviewed; N findings wait for your decision" with their ids (a count only, in a compacted summary). For the owner: the review itself is complete, and what is left is their decision on those findings.
- It needs nothing else open: every line of the record's `whatIsMissing` is a finding left for the owner, so the same record without those findings would read `reviewed`. Any other open line (a missing review, CI not green on the final commit, an undecided finding, an unread raw output, no planned reviewer covering the final commit) keeps `not-reviewed`. A withheld path or raw output, or reviewers that covered an earlier commit beside one that covered the final commit, change nothing here, because they do not keep a record from `reviewed` either.
- It never clears a gate. The merge sheet builder, the vet's review-record checks and every other reader treat it exactly as `not-reviewed` until the owner rules; once the findings are ruled (`ownerRulings`) the record reads `reviewed`. `lib/review_record.py` gains `REVIEWED`, `NOT_REVIEWED`, `AWAITS_OWNER`, `STATUSES` and `cleared(status)`, true only for `reviewed`.
- No key, flag, or refusal reason changes.

### Cloud builds: credential-like text is redacted, and the review record says so

- A cloud session replaces credential-like text (API keys, tokens, private keys) before a file is written or a comment posted, so a test fixture holding a whole key failed before it tested anything. The instruction to build such a value at runtime from pieces, and to describe such text in a finding rather than quote it, now lives in the dispatch preamble every engine review dispatch is fed (`CREDENTIAL_TEXT_RULE` in `lib/engine_dispatch.py`), `rubric/review-base.md`, `agents/test-role.md`, `agents/implementer.md` and `skills/workhorse/reference/cloud.md`. It is a request in the prompt text, best effort; nothing enforces it.
- The review record carries `transitDamage.redactedFields` (the path of each recorded field whose text holds `[REDACTED`) and a `Transit damage:` summary line. An earlier record carrying only redacted fields is listed under `earlierRecordsNotChecked` with the reason `redacted text`. A record with no redacted field is unchanged.

### Implementer orders: the file-write rule rides every order

- The review fixer's file-write rule has one home now, `command_refusals.FILE_WRITE_RULE` in `lib/command_refusals.py`. It tells the seat to write files only through the host's own Write and Edit tools, never a shell command that writes a file.
- `dispatch-write` appends it to every staged write prompt, after the refused-command rule (`command_refusals.ORDER_TEXT`) and before the result contract, on every engine.
- The native implementer preamble (`lib/native_engine.py`) carries it as its rule 4; the refused-command rule, the result and the deadline rules move to 5, 6 and 7.
- The fixer order template (`rubric/orders/dispatch-fixer.md`) fills the same sentence from the constant through the `{{FILE_WRITE_RULE}}` placeholder; its rendered text is unchanged apart from line wrapping.
- No key, flag, or refusal reason changes.

### Review rulings: a late ruling re-renders a fixer order nobody has picked up

- `round_driver.py rule` takes a new flag, `--fixer-not-dispatched`. Without it, a ruling on a pending `dispatch-fixer` attempt whose orders are already emitted leaves the order alone: the attempt is never stopped and its batch never reshaped.
- With the flag, and when the driver sees no pickup evidence (no store, landing or bare-payload file for a fixer slot at the attempt, and no commits past the order's emission head), `rule` re-slices the batch through the same ruling filter and re-emits the order at the next attempt in one commit with the ruling. The next `next` hands out that order, and the superseded attempt can no longer be recorded: `record-result` and `record-missing` refuse it `attempt-not-pending`, and a hand `submit` echo for it no longer matches.
- When the re-slice empties the batch, the fixer pending is dropped and the session settles as it does when a ruling empties the batch before emission.
- A render or commit refusal during the re-emission refuses the whole `rule` with state unchanged and `fix-batch.json` restored. If the session process dies between the re-render and its commit, run the same `rule` again.
- Every `rule` on an emitted attempt returns a new result key, `fixerOrder`. Not reshaped: `{reshaped: false, attempt, reason}` with `reason` `dispatch-not-ruled-out`, `fixer-landed` or `fixer-committed`. Reshaped: `{reshaped: true, attempt, supersededAttempt, reason, commitCheck}` with `reason` `reshaped` or `batch-emptied` and `commitCheck` `clean` or `unreadable` (git could not tell, which does not block the re-emission).

### Review record: an abandoned session writes its own record

- `review_record_session.py write` takes a new flag, `--abandoned "<reason>"`, for a session the orchestrator closed before its loop ended. Without it nothing changes.
- Two new refusals: `review-session-not-abandonable` (the session ended; write its record without the flag) and `review-session-abandon-reason-missing` (the reason is blank). `review-session-not-terminal` is still the refusal for an unfinished session written without the flag.
- The record reads `not-reviewed` and can never read `reviewed`. Its `whatIsMissing` carries the line "session abandoned: ...", and a finding still open reads undecided ("still open when the review loop ended").
- `checked` carries the reason and a line that findings in seat results recorded but never folded appear only in the raw findings files.
- A new optional account key, `abandoned: {"reason": ...}`, admits an empty `reviewers` list: a session abandoned before any seat result lists no reviewer. An account without the key still needs at least one reviewer.

### Native implementer: enroll links the installed dependencies

- `native_engine.py enroll` now links each installed dependency folder of the build worktree (`break_it.DEPENDENCY_DIRS`, today `node_modules`) that the base does not track into the isolated worktree, through the one helper `break_it._link_dependencies`. A caller that reads the enroll result finds a new key, `dependencies`, beside `ok` and `head`: `{"linked": [...]}` lists exactly the links that exist.
- `dependencies` carries a `note` when the helper declined or nothing was linked: `dependency-link-unsafe` and `dependency-link-failed` (the helper's reasons, which never refuse enroll), `already-present` (every installed folder is already in the tree because the base tracks it) and `none-installed` (the build worktree has no dependency folder). A link made cleanly has no `note`.
- `close` removes that link before `git add -A`, only when the base does not track the path and the link resolves to the build worktree's own folder; a path the base tracks, or a link resolving elsewhere, is collected as before. An unlink failure forfeits `native-collect-failed`.
- The break-it guard (`_link_dependencies`) gains two checks, which also apply to a break-it run: a dependency folder that is itself a link into another part of the checkout is `dependency-link-unsafe`, and the entries of a `.bin` directory are scanned like package links, so one that links into the checkout outside the dependency folder is `dependency-link-unsafe` too.
- A new result key (`dependencies`, with its `note` tokens). No flag or refusal reason changed; `native-collect-failed` now also covers an unlink failure.

### Native dispatch: open prints a launch prompt

- `native_engine.py open` prints `agent.launchPrompt`: one sentence that points the subagent at `agent.promptPath` ("Read the file `<promptPath>` in full with the Read tool before doing anything else, then follow it exactly: it is your whole work order."). The standard dispatch path for the native implementer, and for the native fixer with the emitted order file's path, is that sentence as the subagent's prompt; the order is never re-emitted inline.
- A new key in the printed `agent` object. No flag or refusal reason changed.

### Review fixer: the cloud localSockets route

- In a cloud session on Linux whose calibration turns on `localSockets`, the claude write channel refuses `engine-config:sandbox-access-unsupported-platform`, so the review's host-seat fixer runs as a native fixer subagent in the build worktree (no worktree isolation), dispatched with the pointer prompt, writing its own payload landing and its own commit as the fixer order says. It is never a native implementer order.
- No key, flag or refusal reason changed; the reason above is the existing one the channel already gave.

### Review: the verify-command check skips shell keywords

- `lib/repo_doctor.py` check 5 resolves the verify command's first word in command position that names a program. It skips shell keywords (`if`, `then`, `!`, `{`, …), builtins with their arguments (`[`, `[[ … ]]`, `test`, `cd`, …), `VAR=value` prefixes and redirections; after `command`, `exec` or `time` and their options it checks the program they run (`command -v` only queries, so it is skipped). A quoted operator such as `";"` is an argument, not a command separator. A program word with a `/` resolves as an executable file under the project root, not the caller's directory.
- When no word can be read as a program (a `case` construct, a program word only the shell can read such as `$PY` or `"python3"`, an unclosed quote), the result's new `unchecked` list says so and the message carries it as a note. It is never drift, so it adds nothing to `signal_hash` and asks for no re-run of review-init. While a note stands, `nudge_acked` reads false so the note is shown, and drift the owner already acknowledged is left out of the message.
- A command whose real program is absent still reports "verify command no longer resolves: <program>". The check fails safe: when the command quotes or escapes a word or carries a comment, or an assignment (`export PATH=…` included) or `cd`, `pushd`, `popd`, `source` or `.` comes before the program, an unresolved program reads as not checked ("… does not resolve here, but …"), never as stale.

### Wave watch: a cloud lane sent a fix order is watched again

- A terminal, started cloud lane whose handback or park is recorded is watched again, exactly like a live cloud lane, from the moment it is sent a fix order until its next ending. A fix order is a `vet not-ready` amendment, or a fix-order relay to the lane's session composed with the new `cloud_relay.py compose --fix-order` and read delivered (or a may-hold-text verdict) by `check`; the window opens at the message's compose time (`sentAfter`), not at the check, so a re-check moves nothing. A `reoutcome` amendment, or a vet `ready` or `parked-blocker`, closes it.
- The window is the fix order to the lane's first handback, stop or park (a superseded park does not count). Endings and notes from before the fix order are not re-reported; the closing ending fires `lane-terminal` as a live lane's does; nothing about the lane surfaces after it. A refused, never-started or local lane is never re-opened, and a lane passed `--ignore-launch` is not re-added.
- A reopened lane's `cloudLanes` entry carries `reopenedAt` and `reopenedBy` (`vet-not-ready` or `fix-order-relay`). Its stale clock starts at the fix order.
- A new degradation token, `fix-order-unavailable`, discloses an unreadable relay state; only `vet not-ready` amendments re-open lanes meanwhile.
- A comments read that was partial adds a result key, `unreadIssues` (`[{"launchId", "issue"}]`, absent when nothing went unread), on `run`, `watch_arm` and `loop` results.
- A not-ready lane whose fix goes to a fresh launch is now passed `--ignore-launch` (or its vet recorded `ready` or `parked-blocker` when done), or the watch keeps waiting on the old lane.
- No ledger record kind changes; `cloud-relay.json` gains one optional key, `fixOrder`.

### Launch ledger: a repeat outcome after a fix order is recorded

- `launch_ledger.record_outcome` on a terminal lane still records a repeat outcome as a `reoutcome` amendment, and still skips one identical (same outcome and evidence) to an amendment already recorded (`recorded: "amendment-existing"`). When the lane holds a `vet not-ready` amendment, only amendments at or after the newest one (by `ts`, ties included) count for that check, so a repeat that answers a fix order is written (`recorded: "amendment"`) and closes the reopening the wave watch reads from the ledger.
- That `reoutcome` is stamped no earlier than the `vet not-ready` it answers, so a clock stepped back cannot record a closer older than the fix order. An amendment whose `ts` is not a finite number is neither a fix order nor a match for this check.
- A lane with no `vet not-ready` amendment, and every other amendment kind, keeps the whole-history check. No key, flag or refusal reason changed.

## 0.46.0

### Before you upgrade

Check these in a consuming project when it adopts 0.46.0. Each step names the note it comes from.

- **After switching.** **Nothing is owed.** An advisor driving a merge train reads the base branch's protection first. Where it requires pull requests to be up to date before merging, every PR is still brought current before its merge, with no admin bypass. Where it does not, a vetted PR outside a stack is no longer re-synced and re-tested after an unrelated merge: it is current when GitHub reports no conflict and nothing merged since its last sync touched its files. `main`'s post-merge run stays the union check in both cases. See [Merge train: what "current with its base" means](#merge-train-what-current-with-its-base-means).
- **After switching.** **Nothing is owed.** An implementer order that names a bite-proof now carries the record format inline, and an order that names one while the plugin's bite-proof rubric cannot be read is refused at open. See [Implementer orders: the bite-proof record format rides inline](#implementer-orders-the-bite-proof-record-format-rides-inline).
- **After switching.** **Nothing is owed.** The certification loop's leftovers are gone: dead helpers in the review-loop libraries (`_write_interim_receipt`, `_pending_step`, `_row_matches_ruling_id`, six re-export aliases in `round_driver.py`, `load_records`, `blocking_findings_from_dimension_results`, and unused constants), with no caller anywhere; the keep-or-retire list's review-loop section stops calling it the certified review loop.
- **After switching.** **Nothing is owed.** An engine call in plugin code that left stdin open now fails CI, and a caller that passes an inherited `stdin=` or `input=None` to the helper gets a `ValueError`. See [Engine CLI calls: one stdin chokepoint](#engine-cli-calls-one-stdin-chokepoint).
- **After switching.** **Re-run the claude conformance probe before the next wave's `preflight-entry`.** A claude probe result taken before the upgrade records no config dir and is refused as `probe-config-dir-unrecorded:claude`. See [Preflight: the claude probe runs under the launch's config dir](#preflight-the-claude-probe-runs-under-the-launchs-config-dir).
- **After switching.** **Nothing is owed.** A caller that reads a `dispatch-write` write forfeit now also finds `dirtiedPaths` on the "forfeited twice" result, and both write-forfeit disclosures say whether the timeout cut the engine off and whether work landed. See [Dispatch: both write forfeits name what landed](#dispatch-both-write-forfeits-name-what-landed).
- **After switching.** **A project whose guardian config file is unreadable or not valid UTF-8 now sweeps as `degraded` and loses benching until the file is fixed; nothing else is owed.** See [Guardian: an unreadable or non-UTF-8 config is degraded](#guardian-an-unreadable-or-non-utf-8-config-is-degraded).
- **After switching.** **Nothing is owed.** Guardian's hotspots lens stops ranking `.tsx`/`.jsx` files on lizard's complexity figures, which lizard mis-measures in JSX. Those files now read unmeasured, so a TSX-heavy project's hotspot list gets shorter and the sweep lists the hotspots lens as degraded with the count of unmeasured files. See [Guardian: TSX/JSX complexity reads unmeasured](#guardian-tsxjsx-complexity-reads-unmeasured).
- **After switching.** **Advisors who build PR or stack sheets put each acceptance the owner would weigh up as its own Accept item, and give the "What you're accepting" fold's `ifLeft` as a list of routine notes; nothing is owed for existing sheets, and a string `ifLeft` builds exactly as before.** See [PR sheet: the fold keeps only routine notes, as a list](#pr-sheet-the-fold-keeps-only-routine-notes-as-a-list).
- **After switching.** **An advisor building a PR or stack sheet passes `--pr-body <number>=<file>` for every covered PR and gives `accounting` for every acceptance those bodies list (item, fold line, leftover or Canon), and the build refuses a sheet that misses one; a sheet built earlier shows the not-checked line where it said nothing to accept.** See [PR sheet: every PR-body acceptance is accounted for](#pr-sheet-every-pr-body-acceptance-is-accounted-for).
- **After switching.** **A project whose calibration names a Python launcher and whose repository root has a lockfile or requirements file writes and pastes new setup text once** (the cloud check reports the setup text out of date, because the stamp gains the fill step). Nothing is owed for any other project. See [Cloud setup: the setup text fills the launcher's dependency caches](#cloud-setup-the-setup-text-fills-the-launchers-dependency-caches).
- **After switching.** **Nothing is owed.** A review finding about a PR body is now fixed in a staged copy and copied onto the PR by the review itself after it converges, and the fixer order forbids every GitHub write. See [Review: a PR-body finding is fixed in a staged copy](#review-a-pr-body-finding-is-fixed-in-a-staged-copy).
- **After switching.** **Nothing is owed.** Every review seat's order, on every engine, now carries one standing rule: a seat reviews by reading and never runs the project's own files, and a fixer runs only the commands its order names. The light-lane reviewer, the grounding seat, the brief check and the spec checks, whose prompts the order renderer does not write, get the review rule through the dispatch preamble every engine review dispatch is fed, and a native host grounding seat through its order. It is a request in the prompt text; nothing enforces or checks it. See [Review seats: one standing rule, review by reading](#review-seats-one-standing-rule-review-by-reading).
- **After switching.** **Nothing is owed.** Two dead pieces of the plugin are gone: `identifiers.py`'s retired content hash and `model_registry.escalate()`'s step to another vendor at the top of a ladder. See [Retired: the identifiers content hash and the cross-vendor escalation step](#retired-the-identifiers-content-hash-and-the-cross-vendor-escalation-step).
- **After switching.** **Nothing is owed.** A fixed Python, JavaScript or TypeScript break-it finding's test now counts as kept when its fixture and assertions appear unchanged in a file the final diff carries, at any path, so a formatter run or a move of the test no longer parks the review with `changed` or `missing`. A `breakItKept` row can now read `kept` with reason `body-match`, or `unresolved` with one of the new reasons below. See [Break-it tests: the keep check matches a test by what it checks](#break-it-tests-the-keep-check-matches-a-test-by-what-it-checks).
- **After switching.** **Nothing is owed.** A break-it finding that the owner or advisor ruled out of scope through the `rule` verb, and that a round's audit then cleared, no longer parks the review for want of a kept test; it reads `ruled-out-of-scope` and the review record lists it as a ruling. An `out-of-scope` disposition with no clearing audit now runs the keep check, where before it read `not-required`. A `run-verify` payload may also carry `via: "ci-exact-head"` with the CI run's evidence when the local verify command cannot run; a payload without `via` folds as before, and `ci` or `reason` without `via: "ci-exact-head"` is refused. See [Break-it tests: a ruled-out test is exempt](#break-it-tests-a-ruled-out-test-is-exempt) and [Verify: CI on the exact head can stand in](#verify-ci-on-the-exact-head-can-stand-in).
- **After switching.** **Nothing is owed, except that a consumer that reads refusals entries with a closed key set must accept `route`.** An implementer may take the one route a hook's own refusal message names, and the entry then carries it. See [Refusals: a hook-named route](#refusals-a-hook-named-route).
- **After switching.** **Nothing is owed.** The worktree guard no longer refuses a `git checkout --ours|--theirs` or `git restore` of paths the merge left unedited because of the merge's staged changes elsewhere. See [Worktree guard: a merge in progress](#worktree-guard-a-merge-in-progress).
- **After switching.** **Nothing is owed.** A heredoc body in a few exact command shapes is no longer scanned for commands. See [Worktree guard: text that only names a command](#worktree-guard-text-that-only-names-a-command).
- **After switching.** **Nothing is owed.** Every worktree guard refusal text now ends with the exact command or tool to use next. See [Worktree guard: every refusal names its next step](#worktree-guard-every-refusal-names-its-next-step).
- **After switching.** **Nothing is owed.** A desktop-started session's automatic checkpoint runs while the session is off screen, and the mod writes `<id>.skip` beside the notes. See [Automatic checkpoint: a desktop-started session counts as attended off screen](#automatic-checkpoint-a-desktop-started-session-counts-as-attended-off-screen).
- **After switching.** **Nothing is owed.** An orchestrator that wants the review loop to cross-check a review fixer's reported refusals against the fixer subagent's transcript passes `--fixer-transcript <path>` on `record-result`, `advance` or `submit`; without it every fixer row journals `refusalCheck: unobserved` and nothing is refused. A fixer that committed and wrote no landing is now refused `fixer-committed-unlanded`: re-dispatch the order so it lands. See [Review fixer: Write/Edit only, every refusal reported, and the landing always written](#review-fixer-writeedit-only-every-refusal-reported-and-the-landing-always-written).
- **After switching.** **Nothing is owed.** The showrunner charter's board duty now says a new issue files only on the owner's word. See [Showrunner: the board duty names the filing rule](#showrunner-the-board-duty-names-the-filing-rule).
- **After switching.** **Nothing is owed.** The wave watch stops reporting a cloud park once the same lane posts a note after it, or edits its progress comment to a resumed phase more than 300 seconds after it, `cloud_relay.py check` reads every send attempt of a relayed answer (a send with the header line dropped reads `relay-text-mismatch` with `headerDropped: true` at the end of the wait unless an exact send succeeded), and one answered note can be ignored by id with `--ignore-event LAUNCHID:builder-note:COMMENTID`. See [Wave watch: a superseded park, the relay check, and one answered note ignored by id](#wave-watch-a-superseded-park-the-relay-check-and-one-answered-note-ignored-by-id).
- **After switching.** **Nothing is owed.** `lib/stack_check.py list` now falls back to GitHub's REST stacks API where a cloud session's proxy refuses GraphQL, a new `lib/stack_merge.py` merges a stack's top layer over REST, and a second pass that sees a changed stack snapshot now refuses `order-mismatch` on both transports. See [Stacks: membership and merge through REST in a cloud session](#stacks-membership-and-merge-through-rest-in-a-cloud-session).
- **After switching.** **Nothing is owed.** A cloud advisor can now launch a build that depends on another pull request, and the wave watch can resolve its repository, where the cloud proxy refuses GraphQL. See [Cloud: the dependency gate and the watch's repository read work through REST](#cloud-the-dependency-gate-and-the-watchs-repository-read-work-through-rest)
- **After switching.** **Nothing is owed.** An advisor in a cloud session gets the wave watch's open-PR list and cloud lanes' activity age, and can launch an upper stack layer, where the proxy refuses GraphQL. See [Cloud: the watch's PR list and activity read, and the upper-layer launch, work through REST](#cloud-the-watchs-pr-list-and-activity-read-and-the-upper-layer-launch-work-through-rest).
- **After switching.** **Nothing is owed.** Owners see fewer already-fixed leftover cards: a finding an audit raised, which the review then fixed and audited under its own key, is recorded fixed and no longer left for the owner. See [Review: a finding an audit raised is audited under its own key](#review-a-finding-an-audit-raised-is-audited-under-its-own-key).
- **After switching.** **Nothing is owed.** An advisor with two or more PRs waiting can draft their vets in parallel with the new `vet-drafter` agent, which runs on the advisor's own model; the advisor still checks each draft, posts the receipt and writes the slot. See [Vetting: the vet-drafter drafts vets in parallel](#vetting-the-vet-drafter-drafts-vets-in-parallel).
- **After switching.** **A project that lists setup commands and declined the dependency hook before this release may have no setup inputs (item 18) stored, so a lockfile change does not make the cloud check report the setup text out of date.** Set item 18 through configure, or run the hook offer again and answer, then write and paste new setup text. See [Configure: the hook offer saves the detected inputs on either answer](#configure-the-hook-offer-saves-the-detected-inputs-on-either-answer).
- **After switching.** **Nothing is owed for a project with the dependency hook (item 19) off.** A project with it on, whose launch branch lacks the committed, registered hook, now launches on the owner's machine with reason `dependency-hook` until the hook files are committed and pushed on that branch. A project with the dependency hook on sets item 17, 18 or 19 again to rewrite the script, then commits and pushes it. See [Cloud readiness: the dependency hook on the launched commit](#cloud-readiness-the-dependency-hook-on-the-launched-commit).
- **After switching.** **Nothing is owed for a project without the plugin pin hook.** Its setup text, stamp, cloud check and readiness read as before. A project that wants a plugin release to reach cloud builds by one pin commit instead of a paste runs `cloud_plugin_pin.py write --cwd .`, commits and pushes the hook script, the settings entry and the pin file, then writes and pastes new setup text once, because the stamp then covers the setup steps and the startup-loaded plugin parts, and then runs the cloud check. See [Cloud setup: the plugin pin hook](#cloud-setup-the-plugin-pin-hook).
- **After switching.** **An advisor that put a PR-tied collector item in a "What you're accepting" item or a leftover's text by number must move it to `collectorItems`, because such a sheet input is now refused when that card has no options.** See [PR sheets: a PR-tied decision rides its PR's sheet](#pr-sheets-a-pr-tied-decision-rides-its-prs-sheet).
- **After switching.** **Nothing is owed.** A review record that read CI red because an older cancelled run of a check was still listed beside a newer run of it now reads the newer run. See [Review record: CI reads each check's latest run](#review-record-ci-reads-each-checks-latest-run).
- **After switching.** **Nothing is owed.** A stack launched once on its parent issue is now cleaned up as one lane; a PR that links an issue holding its own lane is cleaned up exactly as before, unless the PR also links a sub-issue of that issue, in which case it is a layer of the stack. See [Cloud cleanup: a stack launched on its parent issue cleans up as one lane](#cloud-cleanup-a-stack-launched-on-its-parent-issue-cleans-up-as-one-lane).
- **After switching.** **Nothing is owed, and there is no setting to change.** A JavaScript project's break-it tests run when the reviewed checkout has `node_modules` installed; a build worktree with no `npm install` records them not-run. See [Break-it tests: a JavaScript test reaches the installed dependencies](#break-it-tests-a-javascript-test-reaches-the-installed-dependencies).
- **After switching.** **Nothing is owed.** A builder that continues or retries an order can pass the order's original base, and items an earlier attempt already committed then count as delivered instead of forfeiting `items-undelivered`. See [Dispatch: a continuation counts an earlier attempt's delivered items](#dispatch-a-continuation-counts-an-earlier-attempts-delivered-items).
- **After switching.** **Nothing is owed.** A review panel keeps its Claude seats when a session's start event omits the model: compose reads the model from the session's own transcript instead of reading it as unknown. See [Review panel: the host model falls back to the session transcript](#review-panel-the-host-model-falls-back-to-the-session-transcript).

### Review: a finding an audit raised is audited under its own key

- A finding an audit raised (`discharged-but-new-issue`, in `newIssues`) used to settle `left-for-owner` when a later fix round re-raised its parent, fixed both, and the later audit ruled only on the parent. It now rides that later audit as a target of its own: `payload.targets[]` gains a row with the same fields as a batch target plus `spawnedFrom` (the parent's key), and every target's `roundFindings` lists it so the parent's auditor can attribute its repair.
- An audit that discharges the rider records it `fixed` at the audits fold, and the review record reads it `fixed` like any audited fix. Any other ruling, a missing result, an unauthenticated one, no independent auditor or an ambiguous one leaves it with no disposition, and the end-of-loop settle leaves it for the owner as before.
- A rider is never part of the fix list, the audit-stall breaker's outcomes or the PR-body audited check. A round that audited a rider records `spawnedAudits` (`{id, spawnedFrom, ruling}`), and a rider not discharged records a `spawned-audit-not-discharged` decision in place of `not-discharged`.
- `state.auditSpawned` (`{child key: parent key}`) is new and optional; a session without it audits as before. The state version does not change.

### Vetting: the vet-drafter drafts vets in parallel

- New agent `agents/vet-drafter.md` (`superheroes:vet-drafter`), `model: inherit`, tools `Read, Grep, Glob, Edit, Write, Bash`. It writes `draft-receipt<ordinal>.md` and `draft-slot<ordinal>.md` to the draft directory the advisor names and posts nothing.
- `skills/showrunner/reference/vetting.md` § Parallel vets says when to use it, how ordinals are assigned and recorded, the dispatch inputs (the installed plugin root among them, so the drafter reads the vet contract from the installed plugin and never from the PR branch), that the dispatch carries no model override, that the drafter writes every advisor-only act (a misses-log or collector append, a filing) as proposed, for the advisor to make, and that the verdict, the posting and the slot write stay the advisor's. On Codex the advisor vets serially.
- The agent file joins the cloud setup text's plugin inventory (`lib/cloud_setup_text.py` `_plugin_inventory` stamps each agent file), so a project with the plugin pin hook sees the cloud check report its setup text out of date once, as after any release that changes an agent file.

### Stacks: membership and merge through REST in a cloud session

- `lib/stack_check.py list` takes a new flag, `--transport auto|graphql|rest`, default `auto`. `auto` reads by GraphQL and re-runs the whole read through REST (`GET /repos/{o}/{r}/pulls/{pr}` and `GET /repos/{o}/{r}/stacks/{n}`) only when the first GraphQL call is refused by the cloud proxy, a non-zero exit carrying `HTTP 403` and `use the REST API`. Any other GraphQL failure refuses as before, and a read is never mixed across transports.
- New file `lib/stack_merge.py` with verbs `merge --repo <owner/name> --top <top PR> --sha <top head sha> [--poll-timeout S] [--poll-interval S]` and `poll --repo <o/r> --top <n> --uuid <u> --sha <sha>`. `merge` sends `PUT /repos/{o}/{r}/pulls/{top}/merge-async` pinned to the top head's sha and polls the request; it exits 0 only when GitHub reports `status: merged`. Otherwise it returns `merged: false` with a `reason` (`merge-request-refused`, `merge-response-unreadable`, `head-mismatch`, `merge-failed`, `merge-enqueued`, `poll-timeout`, `bad-argument`, `gh-unavailable`); `poll` resumes a `poll-timeout`.
- `rubric/native-stacks.md` names the REST calls that create a stack (`POST repos/{o}/{r}/stacks`) and grow one (`POST repos/{o}/{r}/stacks/{n}/add`) for an advisor in a cloud session, with the read-back through `lib/stack_check.py list`. No helper wraps them.
- The two-pass membership check now also compares the stack snapshot between passes on both transports: a second pass whose stack number, size, base, or the queried pull request's position, head or base changed refuses `order-mismatch`.
- No existing key, flag or refusal reason changes; local steps are unchanged.

### Cloud: the dependency gate and the watch's repository read work through REST

- `lib/stack_check.py`'s `read_pr_vet_state` (the launcher's dependency gate) and `resolve_repo_slug` (the launcher and the wave watch) now re-read through REST (`GET /repos/{o}/{r}/pulls/{pr}`, `GET /repos/{owner}/{repo}`) when `gh pr view`/`gh repo view` is refused by the cloud proxy. Any other failure refuses as before, and a REST failure after the refusal refuses `stack-unreadable` with detail `graphql refused; rest: …`.
- The proxy-refusal test now matches `HTTP 403` with or without parentheses (the `gh pr view` shape has none).
- No key, flag, or refusal reason changes.

### Cloud: the watch's PR list and activity read, and the upper-layer launch, work through REST

- `lib/stack_check.py` gains `list_open_prs`, the one read of the open-PR list: it reads `gh pr list --state open --limit 1000` and re-reads `GET /repos/{owner}/{repo}/pulls?state=open&sort=created&direction=desc` page by page, stopping at the first 1000 rows, only when the proxy refuses GraphQL. The wave watch's open-PR list and the launcher's base-PR lookup for an upper stack layer read through it. `lib/gh_pages.py`'s `read` takes an optional `limit`.
- The wave watch's cloud activity read re-reads through REST on the same refusal: the issue (`GET …/issues/{n}`), its timeline, the pull requests whose body closes it with a closing keyword and that target the default branch or are a layer of a native stack, and the branches whose name carries the issue number with their head commit's committer date.
- The REST activity read reads unavailable where REST cannot establish what GraphQL reads: a manually linked pull request on the issue's timeline, a closing reference from another repository, a pull request whose stack membership cannot be read, more than 10 closing pull requests or more than 50 matching branches, or any failed read. A REST read never reports a list, an age or a base PR from a failed read.
- No key, flag, or refusal reason changes.

### Review fixer: Write/Edit only, every refusal reported, and the landing always written

- The fixer order (`rubric/orders/dispatch-fixer.md`, filled by `lib/round_orders.py`) gains three lines. The fixer creates and edits files only with the host's Write and Edit tools, never a shell command that writes a file. It never rewrites a committed break-it test (a formatter, an autofix, a commit hook), and it reports a commit hook that rewrites one. It writes its landing (a host seat) or its result (an engine seat) last on every ending.
- `lib/observed_refusals.py` reads refused tool calls from a Claude Code subagent transcript, best effort over the closed `MARKERS` list of Claude Code refusal messages. On Claude Code the transcript is `agent-<agentId>.jsonl` under the config dir's `projects/*/*/subagents/`, found by the agent id the subagent dispatch returns.
- `lib/round_driver.py` takes a new flag, `--fixer-transcript <path>`, on `record-result`, `advance` and `submit`. A refusal the transcript shows that the fixer payload's `refusals` leaves out refuses `fixer-refusals-unreported`, carrying `unreported` and, off the hand path, a `correction` command. A transcript that cannot be read refuses `fixer-transcript-unreadable`.
- A new verb, `correct-fixer-refusals --session-dir <dir> --refusals-file <json list> [--fixer-transcript <path>] [--attempt N] [--occurrence N]`, rewrites only the landed payload's `refusals`, journals `fixer-refusals-corrected`, and returns `next`, the exact `record-result` (or `--supersede --expect-sha256`) command to resume. It runs from the session's own repo root and refuses `correction-not-fixer-phase`, `correction-session-repo-unknown`, `correction-outside-session-repo`, `correction-refusals-invalid` and `landing-missing`, besides the two refusals above.
- A fixer slot with no landing while HEAD has commits past the order's emission head refuses `fixer-committed-unlanded` (with `commits`) on `record-result`, `record-result --sweep`, `advance` and `record-missing`. The driver does not rebuild which findings a commit fixed from git, so the recovery is to re-dispatch the order so it lands.
- Every recorded or accepted fixer row journals a new field, `refusalCheck`: `checked` when a transcript was read and showed nothing unreported, `unobserved` when none was passed.
- No existing key or flag changes. A consumer owes nothing, except that an orchestrator that wants the cross-check passes `--fixer-transcript`.

### Merge train: what "current with its base" means

- Showrunner duty 6's merge precondition "a branch current with its base" now follows the base branch's protection. Where the branch requires pull requests to be up to date before merging (a ruleset's `required_status_checks` with `strict_required_status_checks_policy`, or classic protection's `required_status_checks.strict`), the PR is brought current before every merge and the advisor never uses an admin bypass to skip that. Where it does not, a PR outside a stack is current when GitHub reports no conflict and nothing merged into the base since its last sync touched its files; otherwise it is brought current first. A failed read counts as requiring up-to-date PRs.
- `skills/showrunner/reference/merge-train.md` § A merge train's "green" carries the two `gh api` reads (the rulesets read with `--paginate`) and says `main`'s post-merge run stays the union check in both cases; the no-re-sync saving applies only where the branch does not require up-to-date PRs and never covers a stack, which stays current as `rubric/native-stacks.md` § How a stack stays current says.
- The charter eval case `s7-merge-word-scope` now states that its `main` does not require up-to-date PRs; its grader is unchanged.
### Implementer orders: the bite-proof record format rides inline

- `dispatch-write` and the native engine's `open` insert a `## Bite-proof record format` block into the staged prompt when the authored order (every verbatim implementer-template copy masked) names a bite-proof. The block is cut at dispatch time from the plugin's bite-proof rubric: the record's shape and the three disclosures owed when a proof cannot be produced. An order that names none is staged as before.
- New refusal: when an order names a bite-proof and the rubric cannot be read or its format markers are not found exactly once, `dispatch-write` returns terminal `unrunnable` with detail `bite-proof-format-unreadable`, and native `open` refuses with reason `bite-proof-format-unreadable`. Nothing is dispatched.

### Engine CLI calls: one stdin chokepoint

- `engine_adapter.run_engine_cli(argv, run=None, **kwargs)` runs an engine CLI (`codex`, `cursor-agent`, `claude`) with stdin closed. Without `input=` the child's stdin is `subprocess.DEVNULL`; with `input=` (a string, including empty) the text is piped in and stdin is not set. It raises `ValueError` before calling `run` for any `stdin=` other than `subprocess.DEVNULL`, for `input=None`, and for `stdin=` together with `input=`. `run` defaults to `subprocess.run` and its result is returned unchanged.
- `engine_authz.implementation_dispatch_allowed`, `engine_detect.probe`, `cloud_relay._call` and `preflight_probe.probe_command` spawn through it. Each keeps its `run=` seam and its `except Exception`, so a refusal reads as a failed probe.
- `plugins/superheroes/lib/tests/test_engine_cli_stdin_census.py` scans the shipped Python and fails on a spawner call in a file that holds an engine argv source when the call neither starts with a non-engine literal argv nor passes `input=` or a `stdin=` other than `None`, `0` or `sys.stdin`. A call that carries `**kwargs` and no explicit `stdin=` or `input=` fails too. `engine_adapter.py` and `engine_dispatch.py` are exempt by name.

### Preflight: the claude probe runs under the launch's config dir

- `conformance_probe.py run` stamps `configDir` on its result: the `CLAUDE_CONFIG_DIR` the claude child was pinned to, as the dispatch journaled it (a probe whose dispatch never opened records `null`), and `null` for every other engine. The schema stays `conformance-probe/2`; the key is additive.
- `preflight-entry` gained `--config-dir <dir>`, the dir the launch will spawn builders with; omitted, it is this process's own resolved dir. A claude record taken under a different dir is refused as `probe-config-dir-mismatch:claude` (the two paths are compared exactly as written, so a differently spelled path to the same dir is refused too; re-run the probe with the launch's spelling), and one with no `configDir` as `probe-config-dir-unrecorded:claude`. The owner's `--launch-without claude --owner-word` still covers claude, whatever dir it ran under.
- A claude fail reason and the pass evidence name the dir as `configDir=<dir>`.

### Dispatch: both write forfeits name what landed

- The `dispatch-write` "forfeited twice (timeout or unreadable)" result gains `dirtiedPaths`, in the shape the `worktree-dirtied-by-attempt` result already carries (`status`, `paths`, `headMoved`, `truncated`, or `status: indeterminate` with a `reason`). Before, a second attempt that timed out after its edits landed returned no list of what changed.
- Both write-forfeit `disclosure` strings now end with what landed: `The timeout cut the engine off and its report is missing.` when the attempt's detail is a `timeout-*` token, then `Work landed: <n> path(s) changed (see dirtiedPaths); verify them before re-ordering.`, `No paths landed.`, or `Whether work landed could not be read (dirtiedPaths: <reason>); inspect the worktree.` The keys `reason`, `detail`, `attemptDetail` and `attempts` are unchanged.

### Guardian: an unreadable or non-UTF-8 config is degraded

- `guardian_sweep.read_config` returns `configStatus: "degraded"` with a `configNotes` entry `guardian-config unreadable (<error type>)` when the guardian layer exists but cannot be read (a permission error, a directory or a dangling symlink at the path, an I/O error) or is not valid UTF-8. Before, an unreadable layer read as `healthy` with benching authority kept, and a non-UTF-8 layer raised `UnicodeDecodeError` out of the sweep. An absent layer, an empty or provenance-only layer, and a layer with no `guardian-config` fence stay `healthy`.
- The guardian cadence write in `core_md` returns `{"action": "refused", "reason": "guardian-layer-not-utf8"}` (`GUARDIAN_CADENCE_REASON_UNDECODABLE`) on a non-UTF-8 layer instead of raising.

### Guardian: TSX/JSX complexity reads unmeasured

- `lib/guardian_lens_hotspots.py` no longer passes `.tsx`/`.jsx` files to lizard. Each tracked one gets a digest record `{"unmeasured": true, "reason": "jsx-unreliable"}` and a `collectorErrors` entry `{"collector": "lizard", "path": …, "kind": "jsx-unreliable"}`, and `coverageGaps` gains one line counting them. When every JS-family file is `.tsx`/`.jsx`, lizard does not run and `complexityCoverage.javascript` reads `not-collected`.
- When any tracked `.tsx`/`.jsx` file exists, `collect()` returns `partial` with a reason that counts them, so the sweep report shows the gap in `degradedLenses`. When that is the only gap, the result also carries `permanentBoundary: true`, so it can seed a baseline. When a language also failed, the reason names both and `permanentBoundary` is not set.
- A `.tsx`/`.jsx` file measured by an earlier sweep produces no `new`, `worsened` or `resolved` drift and no red line once it reads unmeasured. The collector version is unchanged.
- The lizard install guidance (`guardian_tools.INSTALL_COMMANDS`) pins `pip install lizard==1.24.0`. `.js`, `.ts`, `.mjs` and `.cjs` figures are unchanged.

### Retired: the identifiers content hash and the cross-vendor escalation step

- `identifiers.py` drops `content_hash`, `STABLE_FIELDS` and `_normalize_body` (no non-test caller; `work_item_slug` stays), and `model_registry.escalate()` at the top of a vendor's ladder returns `None` instead of the next vendor's first rung (its one caller already treats `None` as no escalation).

### Cloud setup: the setup text fills the launcher's dependency caches

- `cloud_setup_text._fill_lines(cwd, root, clone)` returns the fill step's script lines, or `[]`. The step exists only when the project's core record names a Python launcher (`breakItInterpreter` when set, invalid meaning none; else the launcher the `verifyCommand` runs) and the repository root has a lockfile or `requirements*.txt`. A verify command carrying an environment assignment or an `env` word, a launcher that is a single bare Python interpreter word (a longer launcher such as `python3 -m uv run python` does get the step), and any read or parse failure each give no step.
- The step runs the launcher once as `<launcher> -c pass` in the project's clone, after the setup commands and before the project's tool steps, and logs exactly one line: `dependency fill ok`, `dependency fill FAILED: <launcher> -c pass exited <code>`, or `dependency fill skipped: no clone in …`.
- The step never changes the setup script's exit status: a failed or skipped fill leaves it what it would have been without the step.
- The stamp gains the entry `setup-dependency-fill`, holding the step's lines, in a project that has the step and a stamp. A project without the step keeps its setup text and stamp byte for byte.

### PR sheet: the fold keeps only routine notes, as a list

- `theme/review-template.md` § The items narrows the fold rule: an acceptance with its own consequence for the owner to weigh (a change near access or identity, a cost or CI-time trade, a shift in what gets tested where, an advisor craft call open to veto) is its own Accept item with a short title and `ifLeft`; only routine notes with nothing to weigh (size against the estimate, tests only, a heads-up about something already ruled) fold into the one "What you're accepting" item, and doubt keeps a disclosure its own item.
- `pr_sheet.py build` takes an item's `ifLeft` as a non-empty string (one paragraph, as before) or a list of at least 1 non-empty strings, shown as a bulleted list, one bullet per note. An empty list, or an empty or blank note, is refused with `items <id>: ifLeft must be a non-empty string or a list of at least 1 non-empty strings`; an empty string `ifLeft` now refuses with that line too, in place of the generic "needs an id ... and non-empty text" line.

### PR sheet: every PR-body acceptance is accounted for

- `pr_sheet.py build` takes `--pr-body <number>=<file>` for every PR the sheet covers (the PR's number on a pr sheet, every `prs[].number` on a stack), the file holding the PR's body as `gh api repos/<owner>/<repo>/pulls/<n> --jq .body` prints it. No acceptance a body lists under its `What we're accepting` heading becomes a card on its own: the advisor keeps its curation, and the build checks that the input accounts for every one.
- A build with no body for a covered PR is refused with `PR #<n> has no body: give --pr-body <n>=<file> with the PR's body (gh api repos/<owner>/<repo>/pulls/<n> --jq .body), so the build can check that the input accounts for its What we're accepting`, and `--pr-body names PR #<n>, which the sheet does not cover` for one the sheet does not cover. A value that is not `<PR number>=<file>`, a PR named twice, and a file that cannot be read as UTF-8 are refused too, and `--pr-body` on `index` is a usage error. The API's `build(..., bodies=None)` reads no body: it makes no accounting check, ignores `accounting` and sets no `nothingListed`.
- Each acceptance has a bullet id, `<PR number>:<10 hex>`, which comes from the PR, the acceptance's text and its place among identical ones. A bullet added above the others leaves every other id as it was, so the ids you have written into `accounting` stay right. A first build with no `accounting` is refused with one line per bullet, each naming the id and the start of the text.
- The input's `accounting` is an object of bullet id to one of four targets, and a bullet takes exactly one: `{"item": "<id>"}` (its own Accept item in `items`), `{"fold": "<id>", "line": <n>}` (line n, counted from 1, of that item's `ifLeft` list), `{"leftover": "<key>"}` (the leftover card it restates; the key names exactly one left-for-owner finding) or `{"canon": "<entry id>"}` (a Canon entry the `summary` cites, written `YYYY-MM-DD-xxxxxxxx-N`). A fold line with no bullet accounted to it is allowed.
- The build refuses, collecting every problem and naming the bullet by id and the first 80 characters of its text:
  - `PR #<pr>'s acceptance <id> ("<text>") is not accounted for: give accounting "<id>" one of item, fold with line, leftover, or canon`
  - `accounting "<id>" (PR #<pr>: "<text>") is accounted for more than once: give exactly one of item, fold, leftover or canon`
  - `accounting "<id>" (PR #<pr>: "<text>") must be an object with exactly one of item, fold with line, leftover or canon`, for a value that is not an object, names none of the four, carries another key, or has `line` without `fold` or `fold` without `line`
  - `accounting "<id>" (PR #<pr>: "<text>") names item "<x>", which is not in items`, `names fold "<x>" line <n>, which is not a line of that item's ifLeft list`, `names leftover "<k>", which names no one left-for-owner finding in leftovers`, and `names canon "<c>", which is not a Canon entry id (YYYY-MM-DD-xxxxxxxx-N) cited in the summary`
  - `accounting key "<id>" names no acceptance in the covered PR bodies`
  - `accounting must be an object of bullet id to where that acceptance is accounted for`
  - `the input repeats key "<key>"`, for a key an `--input` JSON object writes twice (an acceptance written twice under `accounting` would otherwise collapse to one)
- A sheet with no card says one of three things about the covered PR bodies, read from the sheet on the page (the accepting line and the app-bar count), the chat prose and the index row. `prSheet.nothingListed` (true, or absent) records that every body was read and lists no acceptance; only a sheet that carries it says "nothing to accept". `prSheet.canonAccounted` (a non-empty list of Canon entry ids, sorted and distinct, or absent) records that every body was read, they list at least one acceptance and every listed acceptance is accounted to a Canon ruling; the page line and the prose line say it was checked and all covered by Canon rulings, naming the ids, and the app bar and index row say it without them (`pr.acceptingCanon`, `pr.acceptingCanonCount`, `index.acceptingCanon` in `sheet-words.json`). The two fields never appear together, and each id in `canonAccounted` must appear in `whatChanged.summary` (a plain substring check; the build checks the Canon id grammar); both readers refuse a sheet that breaks either. A sheet with neither field says it was not checked against the PR body (`pr.acceptingUnchecked`, `pr.acceptingUncheckedCount`, `index.acceptingUnchecked`).

### Review: a PR-body finding is fixed in a staged copy

- A finding citing `SUPERHEROES_PR_BODY.md` now passes compile without being in the git diff. In PR mode the driver stages the body under `<session>/pr-body/` (`original.md`, `staged.md`), the fixer order names a copy in its round's landing dir, and the audit order names the staged and original files. The fixer order forbids every GitHub write; a refused one rides the fixer's `refusals` into the review record.
- The audit fold records `prBodyAudited` on the audit round when every target of that round cleared. After a `converged` terminal, `pr_body_stage.py publish --session-dir D --pr N` copies the staged body onto the PR only when it equals the audited bytes and the live body is still the original, then reads it back. It writes `pr-body/published.json` for every outcome, refusals included.
- The review record's `checked` list gains one sentence saying whether the fix was copied or why not. Branch mode and sessions without `pr.json` stage nothing.

### Review seats: one standing rule, review by reading

- `round_orders.render_order` adds a `## What you may run` block to every seat order it renders (finder, scoped finder, gap sweep, verifier, synthesis, auditor and fixer), from one home in `round_orders.py`; on the `--review-only` path, a hand-composed verifier or synthesis order ends with the same block, printed from `round_orders.seat_rule_block` (see `skills/review-code/reference/verification-pass.md`). The dispatch preamble (`engine_dispatch.ANTIHIJACK_PREAMBLE`), which every engine review dispatch is fed, carries the review seat's rule from the same home in place of its old "you MAY read files and run read-only commands" sentence, so the light-lane reviewer, the grounding seat (`--pr-body-path`), the brief check (`--mode brief-check`) and the spec checks, whose prompts the renderer does not write, get it too; a rendered review order fed through an engine carries it twice, in the preamble and in its own block, with the same words. A hand-rolled review or brief-check engine call, the fallback for when the runner is unavailable, writes the same preamble to the top of its prompt file with the command `skills/review-code/reference/auto-fix-loop.md` gives. The grounding seat's hand-composed order ends with the rule block printed from `round_orders.seat_rule_block`, so a native host grounding seat, which the preamble never reaches, carries it too (`skills/review-code/reference/grounding-seat.md`). A review seat may read, list and search files, including with read-only inspection commands, never runs the project's own files, scripts or tests, and names a run it needs for the driver, which runs the project's declared verify command. A fixer runs only the commands its order names, plus the reads and searches its work needs and the staging its commit needs.
- The rule names no program or command. Engine argv, tool sets and sandboxes are unchanged, and no record check is added: a seat can still break the rule, and nothing checks afterwards.

### Break-it tests: the keep check matches a test by what it checks

- The keep check (`break_it.check_kept`, `breakItKept`) matches a break-it test by its normalised body, at any path in the final diff, when the committed file at the test's path is missing from the head (`not-in-head`), is not in the final diff (`not-in-diff`) or has other bytes (`sha256-differs`). The body match applies to Python, JavaScript and TypeScript break-it tests only. Python is compared by syntax tree (quotes, line breaks, parentheses, comments and blank lines drop out; decorators, indentation, tuple commas and `# type:`, `# noqa` and similar directive comments stay). JavaScript and TypeScript (`.js`, `.jsx`, `.mjs`, `.cjs`, `.ts`, `.tsx`, `.mts`, `.cts`) are matched by tokens: quotes, semicolons, trailing commas, line wrapping and arrow-function parentheses drop out, comments stay (so an added `// @ts-ignore` or a removed `// @ts-expect-error` reads changed), and statement ends are modelled (a line break after `return`, `throw`, `break`, `continue` or `yield` ends the statement). A test in any other language must still be byte-identical at its own path. The test's title may differ; in JavaScript and TypeScript that is the first string of an `it`, `test` or `describe` call at statement start whose name the file takes from the test framework.
- The test must be found exactly once among the files the final diff carries, at module level, with its imports binding the same way and nothing outside it rebinding its names or adding module-level test setup, and it must pass there. Every comparison the check cannot make reads not kept. Every other `check_kept` outcome reads as before.
- The `break-it-run/1` record gains `content`, the test file's text. A record without it keeps the byte-exact check.
- A `breakItKept` row can read `kept` with reason `body-match`, or `unresolved` with `body-unparseable`, `body-empty`, `match-ambiguous`, `binding-conflict`, `host-setup`, `command-unmapped` or `command-selects-tests`. A test found at its own path runs the command the loop ran, unchanged; a test found at another path runs that command with the path replaced.
### Refusals: a hook-named route

- The refused-command stop rule (`lib/command_refusals.py`, `STOP_RULE`) gains one exception: when the refusing guard's or hook's own refusal message names a route, an exact command or tool to use instead, the agent may take exactly that route, once, and records it as that refusal's `route`. Every other form, and every auto-mode classifier denial, stays a stop.
- A refusals entry gains an optional `route` key: a non-blank string, or null when no route was taken. A non-null `route` is valid only with `refusedBy: hook`; `refusals_fault` refuses any other value with `refusals[i].route` and a non-null `route` on a `permission` or `sandbox` entry with `refusals[i].route needs refusedBy hook`.
- A schema-channel engine (codex, cursor) always emits `route`, null when unused. The marker channel and the native implementer may omit it. A consumer that reads refusals entries with a closed key set must accept `route`; the review record's refusals line shows a taken route beside its refusal.

### Worktree guard: a merge in progress

- During a merge (`MERGE_HEAD` present), `git checkout --ours|--theirs <paths>` and `git restore --ours|--theirs <paths>`, and `git restore --source=<x> <file>` for exact indexed files, are judged only on the paths they name. Each is allowed when every named path is unedited since the merge, meaning its content equals what the merge itself wrote or it matches the index; the merge's staged changes elsewhere no longer count against it. A merge state the guard cannot read still refuses.

### Worktree guard: text that only names a command

- A heredoc body is read as text, not as commands, only when the heredoc is the whole command, its delimiter is quoted (`<<'EOF'`), and it is fed to `cat >`, `cat >>` or `tee` writing a file, to `gh issue|pr ... --body-file -`, or to `git commit -F -`; the same holds for the whole `git commit -m "$(cat <<'EOF'` ... `)"` and `gh issue|pr ... --body "$(cat <<'EOF'` ... `)"` message argument. Any other heredoc, and anything that runs in a shell or an interpreter, is read as commands, so a body line that names a discard is refused.

### Worktree guard: every refusal names its next step

- Each worktree guard refusal text ends with the exact command or tool to use next, which is the route the stop rule's exception lets an agent take.
### Automatic checkpoint: a desktop-started session counts as attended off screen

- The mod runs the automatic checkpoint only in an attended session. A session now also counts as attended when the desktop app started it: at `session.start` the mod reads `CLAUDE_CODE_ENTRYPOINT` (`claude-desktop` or `claude-desktop-3p`) and requires that `CLAUDE_CODE_CHILD_SESSION` is unset or empty. Before, the desktop app's Code tab hosted the session as an SDK host and dropped its surface from the roster when the page stopped showing it, so an off-screen desktop session never checkpointed. An interactive session, or one with the desktop surface on the roster at the check, is attended as before.
- A headless `claude -p` builder that a launcher starts from inside a desktop session inherits the desktop entrypoint, but the harness sets `CLAUDE_CODE_CHILD_SESSION` on every shell child of a session, so the child marker excludes it and it stays unattended. Any other entrypoint (a terminal, a cloud session) does too.
- The check fails closed: an entrypoint that is unset, not a string or outside the two desktop spellings, any non-empty child marker (including `0`), or an environment read that throws all read as not desktop-started, and the session starts normally.
- When the mod declines to run at a fill at or above the heads-up line (the trigger minus the heads-up tokens), it writes `<checkpoint dir>/<session id>.skip` with `at`, `reason` (the decision's reason, such as `headless` or `below-trigger`), `tokens`, `trigger`, `surfaces` (the roster, or `null` when unreadable), `isInteractive` and `isDesktopStarted`. It writes once per change of reason or of which side of the trigger the fill is on, and a run or a fill below the heads-up line clears that memory. A failed write is noted and retried at the next measure. The record is reaped with the notes, after `NOTES_MAX_AGE_DAYS`.
- The compaction CLI (`lib/compaction_directive.py`, vocabulary `lib/compaction_cli.json`) gains a `skip --session-id <id>` verb: the record JSON on stdin, written atomically, answering `{"ok": true, "path": ...}`, or refusing with `session-id-invalid`, `empty-record` or `config-dir-unresolved`.

### Break-it tests: a ruled-out test is exempt

- Before the loop certifies `converged`, a break-it finding whose test the keep check would otherwise demand is exempt when two things hold. The finding's effective decision is an `out-of-scope` ruling from the driver's `rule` verb whose provenance names `ruledBy` and `ruledAt`, and a round's audit cleared the finding (`discharged` or `discharged-but-new-issue`).
- Its `breakItKept` row reads `ruled-out-of-scope`, with `reason`, `ruledBy` and `ruledAt`. The review record lists the finding as a ruling, "ruled out of scope: <reason> (ruled by <who>, <when>)", never as fixed, and the `break-it-kept` decision counts it separately.
- Anything less still requires the test kept: a ruling with no clearing audit, an audit with no ruling, or an unattributed ruling runs the keep check. An `out-of-scope` disposition with no clearing audit runs the keep check too; before, any non-fixed disposition read `not-required`.

### Verify: CI on the exact head can stand in

- A `run-verify` payload may carry `via: "ci-exact-head"` with `ci: {workflow, runId, headSha, conclusion}` and a non-empty `reason` naming why the local verify command cannot run. `result` must be `pass`. A payload with `via` absent or `"local"` folds as before, and `ci` or `reason` without `via: "ci-exact-head"` is refused.
- A malformed claim is refused at the shape guard with a reason starting `ci-verify-shape:`.
- The stand-in must be the project's declared CI workflow (`ciWorkflow` in the project's calibration). With no readable declaration the driver refuses with `ci-verify-workflow-unconfigured` before fetching anything; a claimed `workflow` that is not the declared one is `ci-verify-workflow-mismatch`.
- Before the fold, the driver fetches the run (`gh api repos/{owner}/{repo}/actions/runs/<runId>` in the repository root) and refuses the submit with `ci-verify-run-unreadable` (the head or repository root is unresolved, the fetch failed, or a field is missing), `ci-verify-sha-mismatch` (the run's `head_sha` differs from the claimed `headSha` or from the head the fold verifies, or its `id` differs from `runId`), `ci-verify-workflow-mismatch` (its `name` differs from `workflow` or from the declared `ciWorkflow`) or `ci-verify-conclusion-mismatch` (it is not `completed`, its conclusion differs from the claimed one, or it is not `success`), checked in that order. The refusal is not terminal and the pending step is kept, so a corrected resubmit folds.
- The check sits at the one submit chokepoint, so hand `submit`, the bare-payload `advance` and the durable-seat `advance` all get it. The durable-seat assembly carries `via`, `ci` and `reason`.
- A passing verify fold records the round key `verifyVia`: `{"via": "local", "command"}` for a local run, or the CI evidence with its `reason`. The receipt's disclosures carry a `verify-via-ci (round N): …` line for a CI round, and the review record adds a "Verify in round N: CI workflow … run … on … passed, in place of the local verify command (…)" line to what it checked.

### Review panel: the host model falls back to the session transcript

- The session-start hook now exports two more variables on every start beside `SUPERHEROES_HOST_MODEL`: `SUPERHEROES_SESSION_TRANSCRIPT` (the session transcript's absolute path) and `SUPERHEROES_SESSION_TRANSCRIPT_FROM` (the file's size in bytes at that start). A value the hook cannot vouch for is exported empty. The host-model export is unchanged, including the clear on every start.
- `seat_map.py compose` takes `--session-transcript` and `--session-transcript-from`, which `review-code` passes from those variables. The start event's model wins whenever it names one; only when it names none does compose read the model from the transcript, and `host-model-unknown` fires only when neither names one.
- Only a main-chain assistant turn written at or after the recorded start counts, so a resumed or copied transcript's history, a subagent turn or a `<synthetic>` entry never stands in for the live model.
- The launcher drops all three variables from every child it spawns, so a child session derives its own host model and never inherits a parent's.
- With a Claude host the known `hostFamily` keeps native host seats eligible downstream; maker-family exclusions are unchanged (a `claude` implementation engine still keeps anthropic off the panel). No new receipt key; no consumer owes anything.

### Showrunner: the board duty names the filing rule

- Duty 2 of the showrunner charter (`skills/showrunner/SKILL.md`, "Board hygiene — file and wire") gains one sentence: a new issue files only on the owner's word, at every tier, with the layer sub-issues of a stack the one exception, and the advisor reads `skills/showrunner/reference/owner-decisions.md` § The tiers and the filing rule before filing one. The rule itself is unchanged and still lives in that section; a resumed advisor seat now meets it in the charter it reads.
- No command, result key or file shape changes.

### Wave watch: a superseded park, the relay check, and one answered note ignored by id

- A cloud park no longer fires `lane-terminal` when the same lane has later builder activity in the same comments read: a builder note posted (`created_at`) strictly after the park was posted, whether or not the note is recorded answered, or its progress comment edited (`updated_at`) more than 300 seconds (`PARK_SUPERSESSION_GRACE_SECONDS`) after the park with a phase that reads resumed (no word beginning `park` or `stop`, unless a word begins `resum`). A progress edit seconds after a park, or with a parked or stopped phase, is not a resume. A handback or stop is never superseded, a park at or after the latest activity still fires, and a superseded park does not fall back to an older ending. A builder edits its progress comment before posting a park, and first on resuming with a phase that says it resumed; `note-answered` on the park comment is still how recovery stops reading it as a park.
- `cloud_relay.py check` reads `delivered` when some send of the message's exact text, to the session's name or to `<session name> [<ref>]`, carries `success: true` and no send of this message carries altered text (any altered send reads `relay-text-mismatch`, whatever else succeeded); a failed attempt no longer ends the check early. At the end of the wait it reads `relay-send-unconfirmed` when an exact send still has no result, `relay-send-failed` when every exact send failed, and `relay-silent` when there was none. A header-dropped send (the message's text with its header line removed) reads `relay-text-mismatch` (`headerDropped: true`) at the end of the wait unless an exact send succeeded. Re-running `check` later re-reads the relay's record.
- `--ignore-event LAUNCHID:builder-note:COMMENTID` (a positive decimal id) on `run` and `loop`, or a `(launchId, "builder-note", commentId)` item in `ignore_events`, suppresses that one note on that lane for that invocation. Every other note still fires. Every non-refusal result given a note ignore carries `ignoredNotes`, the sorted comment ids; without one the key is absent. `LAUNCHID:builder-note` with no id is still refused (`ignore-event-invalid`), and `note-answered` is unchanged.

### Cloud readiness: the dependency hook on the launched commit

- Cloud readiness (`lib/cloud_ready.py`) has a seventh condition, `dependencyHook`, placed before `calibration` in `CONDITION_ORDER`. When both fail, the owner is told to bring the hook onto the branch first, because a re-paste cannot finish while the clone lacks the registered hook. Its reason is `dependency-hook`: "The branch this build starts from doesn't carry the dependency hook, or a setup file the build adopts can't be shown unchanged since the hook ran (it changed, or it is a link), so the cloud could build it with out-of-date dependencies."
- With item 19 not exactly `true`, or item 17 empty or unset, nothing changes: the condition is true and git is never read for it.
- With the hook on, the condition is true only when the commit the cloud session starts on carries the hook. The script holds exactly the bytes `cloud_dependency_hook.script_text` writes for the stored commands and inputs (an unset item 18 reads as an empty list), as a regular file. `.claude/settings.json` is a regular file whose JSON registers the hook command as an enabled startup `SessionStart` command hook, by the same rule the script's record mode applies; `disableAllHooks: true` fails it.
- The launch checks `baseCommit`, the commit the session starts on, never `adoptsHead`: an adopted head is checked out only at builder intake, after the start-of-session hook ran. For an adoption, every setup input listed in item 18 must also be identical at `baseCommit` and `adoptsHead`. A commit, file or entry that cannot be read is not ready.
- `cloud_ready.readiness` gains the keywords `commit` (the commit the session starts on; the checkout's `HEAD` when None) and `adopted` (the adopted head). `launch_place.route` passes `premise["baseCommit"]` and `premise["adoptsHead"]` when it calls the real readiness; an injected `readiness_fn` is called as before.
- `cloud_dependency_hook.branch_gap(repo_root, commit, commands, inputs, adopted=None)` returns None or one of `commit-unreadable`, `script-missing`, `script-differs`, `settings-not-registered`, `adopted-inputs-differ` and `adopted-input-not-a-file`; a listed input that is a symlink, or sits under a symlinked folder, returns the last one, and its remedy is to point both the setup command and item 18 at the regular file itself, with no link in between. `cloud_setup_text.branch_hook_gap(cwd, root=None, commit=None, adopted=None)` is the reader readiness calls; it returns None without reading git when the hook is off.
- The `Still on your machine` line re-reads the condition on the checkout's `HEAD`, and for an adoption also compares the listed inputs at `HEAD` with the adopted head, so it clears once the hook, and any adopted dependency change, is on the checked-out branch. The input files stay out of the setup stamp, so a changed lockfile still asks for no re-paste.
- The generated script reads its arguments and `CLAUDE_CODE_REMOTE` with defaults, so an inherited `nounset` (`SHELLOPTS=nounset` or `set -u` in a parent shell) no longer ends it with an unbound-variable error. The script's bytes change, so a project with the dependency hook on rewrites it by setting configure's item 17, 18 or 19 again (any set re-syncs the hook files), then commits and pushes it. Until the branch a cloud build starts from carries the rewritten script, cloud readiness reads `dependency-hook` for that launch, because the branch check compares the script's exact bytes.

### Cloud setup: the plugin pin hook

- A project can commit the plugin pin hook (`lib/cloud_plugin_pin.py`, verbs `write`, `remove` and `status`): a start-of-session script, its settings entry and a pin file naming one plugin commit. The cloud check and readiness then read the plugin the cloud runs from the pin, and a release reaches cloud builds by a new pin commit. A project without the hook keeps every output it had.
- `cloud_check.report` carries an optional `pluginCommit`: the 40-hex commit of the plugin directory the session runs, or None when that directory is not a git checkout or git does not answer. A report that lacks the field is still read.
- `cloud_check.judge` results gain `pinMatches` (None for a project without the hook) and the failed-parts list gains `pin`. With the hook valid, `pin` replaces `version`: it fails unless the report's `pluginCommit` equals the pin's commit and the pin's version is this machine's. With the hook broken, `pin` fails and `pinMatches` is false.
- `cloud_ready.readiness` gains the condition `pluginPin`, placed after `version` in `CONDITION_ORDER`, with the reason `plugin-pin`, and a `pluginPin` result key holding `state` (`absent`, `valid` or `broken`; None where the reader returned before reading it), `reason` and `version`. The pin is read on the commit the cloud session starts on. A version the cloud reported keeps precedence over the pin. With nothing reported, a valid pin makes `version` true and `cloudVersion` the pin's version, and `pluginPin` is true only when that version is this machine's; a broken pin, or one that cannot be read, makes `pluginPin` false. A failed check's `pin` part forces `pluginPin` false.
- `launch_place.REASONS` gains `plugin-pin`, and the launch report and the `Still on your machine` line render it; the line clears once readiness reads `pluginPin` true.
- `cloud_setup_text.compose` results gain `pluginPin` (true when the hook is valid) and refuse a broken hook as `plugin-pin-broken`; an unreadable plugin part is refused as `plugin-inventory-unreadable`. With the hook valid, `stamped_files` gains `setup-steps` (the setup text's fixed install and fetch steps, with the plugin source, commit and subdirectory replaced by placeholders) and `setup-plugin-inventory` (each skill's frontmatter, each agent file and the plugin's hooks file), and the setup text writes a stamp even with no calibration files and no setup commands. A release that changes neither entry leaves the stamp unchanged.

### Configure: the hook offer saves the detected inputs on either answer

- configure's cloud setup sitting (`skills/configure/reference/set-up.md` § 6, the dependency hook offer) and its item 19 tune row (`skills/configure/reference/view-and-tune.md`) save the offer's detected `inputs` as item 18 whether the owner accepts or declines the hook. Before, only a yes saved them, so a decline left item 18 unset and the input files out of the stamp, though the offer says a change to them makes the cloud check ask for a re-paste. Accepting is unchanged. No code or result shape changed.

### PR sheets: a PR-tied decision rides its PR's sheet

- `lib/pr_sheet.py build` takes a new optional input key, `collectorItems`: a list of `{number, title, why, context, options, ifLeft, recommendation}`, all required. `number` is the collector item's number (an integer, 1 or more, unique), `options` is a list of at least 1 option whose ids are `a`, `b`, `c` in order (`"none"` and an empty list are refused), and `recommendation` is `{text, reason, optionId}` with `optionId` required. Each entry is built as one option card after the `items` cards, so the merge verdict covers it like any other card. The sheet's data shape is unchanged.
- `build` now refuses a card that has no options and whose shown text (question, context blocks, recommendation) sends the owner to a list item by number: "decision item 1435" (also "collector item", "list item"), "item 1435 on your list" (also in or from, the list or the collector), and "collector" followed by a hash and the number (also "collector number 1435", "collector entry 1435"). The scan is best effort. A card with its own options is never refused for mentioning a number. The problem names the card's input location, `leftovers <key>`, `items <id>` or `closesSpec`.
- `theme/sheet-words.json` gains three `pr` words, `collectorKind`, `collectorOption` and `collectorRecommendation`, after `closureReceipt`.
- `skills/showrunner/reference/owner-decisions.md` § Delivery mechanics and `theme/review-template.md` § The items now say that a PR-tied collector item is a `collectorItems` card with the per-item spine and its collector number, never only in the chat and never inside a "What you're accepting" card. The recap gets a bare-line rule: a recap, morning or reminder line that names a decision carries its one-line context, never only its number and the recommended letter.

### Review record: CI reads each check's latest run

- A check run that a newer run of the same check superseded no longer reads red. A check is the same name, app, workflow, event, head branch and pull request (two pull requests sharing one head commit never replace each other's checks); a workflow that re-runs on one commit (a cancelled run, then a rerun) leaves its older check runs listed, and only the newest run of each check is read. A check whose newest run is cancelled still reads red, and a different check's success never covers a failed one.
- A check run whose identity cannot be established is not reduced: one with no name, id or app, or a GitHub Actions run whose suite maps to no workflow run on the commit. It is read as it is, so a failure on it still reads red.
- The reduction applies to the whole paged check list, so a superseded run on one page and its replacement on another resolve the same way.

### Cloud cleanup: a stack launched on its parent issue cleans up as one lane

- When a merged or closed PR's linked issues hold no cloud lane, `cloud_cleanup.py plan` reads each linked issue's parent issue and looks for the lane there (`--launch-id` naming a lane on a parent issue is accepted the same way). A parent in another repository is not a parent. A parent link that cannot be read, or is not an issue address, refuses `issue-unreadable` and nothing is sent or deleted; `no-cloud-lane`, `lane-mismatch` and `lane-ambiguous` keep their meanings.
- A plan carries `viaParent: true` when its lane came from a parent issue, and also when the PR links the lane's issue together with one of that issue's sub-issues; the key is absent for any other lane found on a linked issue.
- The archive request goes once per lane across all its layers. A later layer's plan carries the request recorded on an earlier layer (its `request.pr` names that layer), with `archiveText: null` and `alreadyDelivered: true` once delivered, and `record ... --outcome pending` on another layer refuses `request-in-progress`, `request-uncertain` or `request-delivered` while the lane's request is held.
- A `pending` or `uncertain` request is settled with `record --pr <the request's pr>`. The `branch` step is unchanged: it deletes only the PR's own head branch, for each layer.
- The archive request for a stack lane waits until every sub-issue of the lane's issue is closed. Until then the plan carries `archiveText: null` and `archiveHeld`: `stack-open` with `openLayers` (the open sub-issue numbers), or `stack-unreadable` when the sub-issues could not be read or there are none, and a `stack-unreadable` hold is retried by re-running `plan` later. `record ... --outcome pending` then refuses `archive-held`, and a hold never refuses the plan: `branch` still deletes each layer's own branch. The plan of the last layer to close carries the archive text. A PR that links both its sub-issue and the lane's parent issue counts as a layer of the stack (`viaParent: true`) and follows the same rules; a PR that links one issue, or several none of which is a sub-issue of the lane's issue, behaves as before. When a PR's other linked issues cannot be read, the plan never refuses: its archive is held only while the lane's issue has a sub-issue that is not closed, or while its sub-issues cannot be read, and its branch step runs.

### Break-it tests: a JavaScript test reaches the installed dependencies

- A break-it test runs in a copy that holds the tracked files plus a symlink to the reviewed checkout's installed `node_modules` (`DEPENDENCY_DIRS` in `lib/break_it.py`), so an `npm test -- <file>` or `npx vitest run <file>` test resolves the project's dependencies. A head that tracks its own `node_modules` keeps it; nothing replaces it.
- No tracked file of the reviewed checkout is written. A test may write untracked cache files inside the linked directory, such as vite's `node_modules/.vite-temp`; those land in the reviewed checkout's dependency tree. A block path under `node_modules/` is refused `path-escapes`.
- A run whose program is `npm`, `npx`, `pnpm` or `yarn`, whose copy's `package.json` declares dependencies, and whose reviewed checkout has no installed `node_modules`, is recorded not-run (`module-not-found`) and launches nothing, so it never reads `passed` or `failed`. Any other run without `node_modules` runs as written and is read by the run-time setup-failure signature.
- A `node_modules` with a package that links back into the reviewed checkout's tracked files (a workspace or `file:` package) is never linked: the run is recorded not-run (`dependency-link-unsafe`). A link or scan that fails is recorded not-run (`dependency-link-failed`).
- A review seat's sanitized-view notice says the view holds tracked files only, with no installed dependencies, and that the review loop's break-it runner runs JavaScript tests itself.

### Dispatch: a continuation counts an earlier attempt's delivered items

- `dispatch-write` and the native `open` take an optional `--items-base-sha <the order's original base>`. It is journaled as `itemsBaseSha` in the `run-opened` record, only when given.
- The declared-item check (`--expect-item`, `--expect-items-file`) diffs against `itemsBaseSha` when the record has one, and against the attempt's `baseSha` otherwise, so an item an earlier attempt committed counts as delivered and an item no attempt delivered still reads missing.
- The flag is refused at open, with nothing opened, as `items-base-sha-invalid` (not a full lowercase commit id) or `items-base-sha-not-ancestor` (it does not resolve, or it is not an ancestor of the attempt's base); `dispatch-write` also refuses `items-base-sha-mismatch` when a continuation of an opened run passes a different one. Without the flag nothing changes.

## 0.45.0

### Before you upgrade

Check these in a consuming project when it adopts 0.45.0. Each step names the note it comes from.

- **After switching.** **Pass `--landing-dir <the order's landing directory>` on a review fixer's `dispatch-write` on the claude engine.** A run opened before the upgrade continues without it. See [Dispatch: the claude write fixer lands its own payload](#dispatch-the-claude-write-fixer-lands-its-own-payload).
- **Before switching.** **Finish every `dispatch-write` run in flight.** A write run opened before the upgrade and admitted after it forfeits `native-schema-unreadable`, because the declared write schema gained `refusals`. See [Orders: a refused or denied command is a stop](#orders-a-refused-or-denied-command-is-a-stop).
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
- **After switching.** **A project that lists setup commands can add the dependency hook (item 19, `cloudDependencyHook`) through configure, then commits and pushes the two files it writes and writes and pastes new setup text.** Turning the hook on or off changes the stamp, so the cloud check reports the setup text out of date until new setup text is pasted. A project that does not opt in has the same stamp and setup text as before. See [Cloud setup text: the dependency hook](#cloud-setup-text-the-dependency-hook).
- **After switching.** **Nothing is owed.** An attended session that runs subagents now gets its automatic checkpoint at the next idle measurement above the trigger, where a subagent's turn used to hold it off. See [Checkpoint: a subagent's turn never holds the automatic checkpoint](#checkpoint-a-subagents-turn-never-holds-the-automatic-checkpoint).
- **After switching.** **Nothing is owed.** A launch whose premise adopts a branch (`adoptsBranch`, `adoptsHead`) now refuses before launch when the adopted head does not descend from `baseCommit`; bring the adopted branch current with its base and launch again. See [Launcher: an adoption whose head is not on its base is refused before launch](#launcher-an-adoption-whose-head-is-not-on-its-base-is-refused-before-launch).
- **After switching.** **Nothing is owed.** A review orchestrator records its rulings on a round's findings before the `next` call that emits the fixer order. See [Review: rulings land before the fixer order](#review-rulings-land-before-the-fixer-order).
- **After switching.** **Paste new setup text and say "check again" in each project with cloud builds, as after any upgrade.** The check fails a cloud session where git resolves no commit identity, and the `git-identity` launch ruling reads `git var`, so a builder on an environment that sets only the `GIT_AUTHOR_*`/`GIT_COMMITTER_*` variables does not park. See [Cloud check: a commit identity](#cloud-check-a-commit-identity).
- **After switching.** **Nothing is owed.** A cloud builder keeps a progress comment on its issue, and the wave watch reads it before calling a quiet cloud lane stale. See [Wave watch: a cloud builder's progress comment](#wave-watch-a-cloud-builders-progress-comment).

### Wave watch: a cloud builder's progress comment

- A cloud builder keeps one progress comment on its issue and edits it in place. Its first line is `Builder progress (cloud build).` (`PROGRESS_HEADER` in `lib/cloud_builder.py`), then `Phase:`, `Now running:`, `Started:`, `Expected: <N> minutes` and, when there is lost work, `Lost work:`. `cloud_builder.py progress` composes the text and `cloud_builder.py edit` replaces an existing comment's body.
- The wave watch reads that comment from the issue comments it already reads, with no extra request. When a started cloud lane has one (created at or after the lane's start; the most recently edited wins), the comment alone decides `lane-stale`: stale when its last edit is older than its stated expected time plus `LIVENESS_QUIET_WINDOW_SECONDS`, or dated in the future. An expected time over 240 minutes counts as 240, and a missing or malformed one counts as zero.
- A lane with no progress comment keeps the activity rule unchanged. A `lane-stale` entry decided by the comment carries `progressAgeSeconds`, `progressExpectedSeconds` and `phase` in place of `activityAgeSeconds`; a `cloudLanes` entry carries the same three keys when a progress comment was read.
- The first check on a quiet cloud lane is a relayed status ping: a message asking the builder to update its progress comment. The advisor starts a helper session to read the lane only after about 15 minutes with no answer. See `skills/showrunner/reference/wave-watch.md` and `skills/workhorse/reference/cloud.md`.

### Orders: a refused or denied command is a stop

- A command that a permission denial, a hook refusal, a sandbox refusal or the harness's own safety checks stopped, or one held for an approval nobody answers, is a stop for the agent that met it, and the agent reports it instead of retrying it in another form. The rule and the shape of a refusals entry have one home, `lib/command_refusals.py`; no order keeps a copy.
- Four orders carry the rule: the fixer order (both branches), every `dispatch-write` prompt, the native preamble, and `agents/implementer.md`.
- Four result channels accept a `refusals` list and refuse a malformed one: the host-seat fixer payload (optional), the native write result schema (required, may be empty), the foreground report grade, and the native `result.json` (optional). On `dispatch-write` a blank string forfeits `native-result-refusals-invalid`, and a shape or enum fault forfeits `native-result-schema-invalid`. A valid list rides on the terminal `dispatch-write` result and on every native `close` result, forfeits included.
- Refusals are shown in two places: the review record's `commandRefusals` (each entry tagged with its round, with a "Refusals met" line in the summary; absent when there are none) and a refusals column in the build record's dispatch provenance. `commandRefusals` is separate from the record's `refused`, which lists findings the loop did not take in.
- At vet, the advisor reads each refusal and names as a finding any refusal followed by the same act in another form. The vet receipt's triggered-fields table has the row.
- The worktree guard was not taught more spellings of a delete. A list of spellings never closes, so the stop rule is carried by the orders instead.

### Review: rulings land before the fixer order

- `skills/review-code/SKILL.md` (the loop's step 3) and `reference/round-driver.md` § Owner and advisor rulings now tell the orchestrator to record every `rule` on a round's folded findings before its next `next` call, which emits the fixer order. A ruling recorded after the order is out reached only the next order, so the fixer built the old direction once and the next round reworked it.
- No driver change: a late ruling is still accepted and carried into the next order, as the backstop.

### Dispatch: the claude write fixer lands its own payload

- `engine_dispatch.py dispatch-write` takes `--landing-dir`, one review landing directory (`<session>/round-<N>/landing/<phase>`). The claude write child's file tools are confined to the working directory, so a host-seat fixer could not write its payload into the session folder outside it; the flag grants that one directory and nothing else.
- The open refuses `engine-config:sandbox-landing-dir-invalid` for a directory that is not an absolute, glob-free, existing landing-layout directory, and `engine-config:sandbox-landing-dir-denied` for one that overlaps a path the sandbox denies. A continuation that names a different directory refuses `engine-config:sandbox-landing-dir-mismatch`. A run opened without the flag is unchanged, and other engines ignore it.

### Checkpoint: a subagent's turn never holds the automatic checkpoint

- A subagent's `turn.start`, a background agent's especially, left the session marked busy after the main turn ended, so the automatic checkpoint never fired in an attended session that ran subagents, until Claude Code compacted the session itself without fresh notes.
- Only the main turn now marks the session busy or binds the checkpoint turn. The checkpoint fires at the next idle measurement above the trigger whatever subagents are running. Headless builder sessions are unchanged.

### Launcher: an adoption whose head is not on its base is refused before launch

- A premise that adopted a branch whose head was not on its `baseCommit` launched, spent a lane, and only then failed at the cloud intake with `adopted-head-not-on-base`.
- `launcher.py launch` now refuses it first, with `premise-adopts-head-not-on-base`, before any lane, worktree, cloud command or child exists, for cloud and local launches alike. The result carries `ancestry` (`not-descendant`, or `undecidable` when the adopted head is not present in the launching checkout, the checkout is shallow, or git could not answer) and a `remedy` that names the fix; a layer above the bottom is told to bring the adopted branch current with the layer below.
- The cloud intake's `adopted-head-not-on-base` is unchanged and stays as the second line. `compose` and `preflight` do not run the check.

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
- Turning item 19 on, or setting item 17 or 18 while it is on, refuses `setup-input-secret-shaped` when a stored item 18 entry is shaped like a secret (the setup text's own scan), so no hook file carries it. When a set fails after the hook files changed (a refused sync, a failed config write or read-back), the hook files are reconciled to the stored items 17, 18 and 19, never to bytes saved before the set, so a failed set cannot undo another set's stored update; stored commands or inputs a hook-writing sync would refuse get the hook turned off (files removed) instead. The result names it under `dependencyHookResynced`, `dependencyHookResyncFailed` and `dependencyHookRemovedInvalid`.
- Setting item 17 to a non-empty list fills item 18 when item 18 was never stored. The fill is the files directly in the repository root whose names are in the plugin's lockfile list or match `requirements*.txt`, sorted, and the `set` result gains `inputsFilled` with them. It is `[]` when the root holds none, and it never overwrites a stored list, including a stored `[]`. A detected name item 18 would refuse (such as `requirements dev.txt`) is left out of the list. If the fill's write or read-back fails, item 17 stays stored, the result gains `inputsFillFailed` with the reason instead of `inputsFilled`, and item 18 stays unset. When the repository root cannot be resolved (git failing) the fill is skipped, item 17 stays stored, and the result carries `inputsFillFailed: "repo-root-unavailable"` with no `inputsFilled`. When the root resolves but is not itself a git checkout (a configured plain directory), the fill is skipped the same way and the result carries `inputsFillFailed: "not-a-git-checkout"`.
- A project with setup commands and a stored item 18 gets stamp keys `setup-inputs` (the list), `setup-input/<path>` (each listed file's bytes) and `setup-input-missing/<path>` (a listed path that does not exist), so a changed list, a changed file or a deleted file reads as out of date until new setup text is pasted.
- `compose` refuses `setup-inputs-malformed` when the stored list fails validation, and `setup-inputs-unreadable` when a listed path exists but is not a readable regular file, when the repository root cannot be found, or when the project's calibration cannot be read for item 18.
- A project with no setup commands has the same stamp and setup text whatever item 18 holds, and item 18 is not read.
- A project that already lists setup commands has no item 18 until it sets one or lists commands again after clearing them, so its stamp is unchanged until then.

### Cloud setup text: the dependency hook

- Configuration item 19, `cloudDependencyHook`, holds `true` or `false`; only an exact `true` turns the hook on. Item 19 is read only when item 17 lists commands.
- With item 19 `true` and at least one command in item 17, configure writes `.claude/settings.json` with one `SessionStart` entry (a `command` hook with a 600-second timeout) and the script `.claude/hooks/superheroes-cloud-dependencies.sh` (new). Other entries in the settings file are left as they are. Setting item 19 `false`, or clearing item 17, removes the entry (and the settings file when nothing else is in it) and the script. A change to item 17 or 18 while the hook is on rewrites the script. A script left behind by an earlier opt-in is removed by the next set of item 17, 18 or 19.
- The `set` result gains `dependencyHook` (`action`, `reason`, `changed`: the repository-relative paths written or removed) when the hook files were synced. The owner commits and pushes the files, because a cloud session starts from the pushed repository.
- The script keeps a hash of the command list and each listed input's size and bytes in `superheroes-cloud-setup-hash` under the clone's `.git`, and its log in `superheroes-cloud-setup.log` there; neither is in the working tree.
- In a cloud session (`CLAUDE_CODE_REMOTE=true`) the script computes the hash, ends at once when it equals the recorded one, and otherwise runs the commands in order with their output in the log, recording the hash after the last one succeeds. A failed command prints one line and the script ends with exit 0, so the next session tries again. The script never fails the session. Outside a cloud session it does nothing.
- `--record <fingerprint>` is the script's record mode: it records the current hash without running the commands. It works without `CLAUDE_CODE_REMOTE`, because the setup script may run without it. It exits 2 with one line, and records nothing, when the fingerprint is not the one the script was written for, when it cannot name its state file, has no sha256 tool or cannot read an input, or when the state file cannot be written. Every other path exits 0.
- With the hook on, the setup text ends the commands step with a record step that runs only when every command succeeded: it runs the clone's script in record mode with the fingerprint of the commands and inputs and logs `dependency hook recorded` or `dependency hook record FAILED`, or logs `dependency hook not in the clone: commit and push it` when the clone has no script. A missing script or a failed record withholds the stamp and ends the setup non-zero, so the hook files must be committed and pushed before the setup text is pasted, or the setup does not finish.
- With the hook on, the setup text does not carry the check that compares each listed input in the clone with what the text was written for, because the inputs are not in the stamp and the hook reconciles them at session start.
- Stamp exception: the files item 18 lists join the stamp exactly when item 17 is a non-empty list, item 18 is stored and item 19 is not `true`. With the hook on, changing a listed file leaves the stamp and the setup text unchanged. Turning item 19 on or off changes the stamp. With no setup commands, items 18 and 19 change nothing.
- The compose result's `calibration` gains `dependencyHook: true` when the hook is on, and has no such key otherwise.
- `cloud_dependency_hook.py offer --cwd .` prints the question configure asks before the hook is added (`action`, `message`, `commands`, `inputs`, `inputsSource`: `stored` or `detected`). It exits 1 with a refusal on stderr: `no-setup-commands` when item 17 lists none, and also `repo-root-unavailable` and `setup-inputs-malformed`.
- `set` refuses item 17, 18 or 19 with `dependency-hook-unwritable` and a `detail` (`repo-root-unavailable`, `settings-unreadable`, `hook-files-unwritable`, `invalid-arguments`, `settings-hooks-disabled` for `disableAllHooks: true` in `.claude/settings.json`, or `settings-secret-shaped` for a credential already in `.claude/settings.json`) when the hook files cannot be brought to the state the new values call for, and nothing is stored. A project that never opted in, with no root and nothing to sync, still sets item 17 and gets no fill. If a write fails after the files were synced, the files are put back to the state of the stored values; if the write held and only the read-back fails or differs, the synced files stay (they match what was written) and the result carries `dependencyHook`.

### Cloud check: a commit identity

- The cloud check's report gains `identity`, `{"author": bool, "committer": bool}`: whether git in the session's repository resolves an author and a committer identity, read with `user.useConfigOnly` so a guessed identity never counts. The report carries no name or email.
- `judge` gains `results.identityPresent` and the failed part `identity`, reported after `reviewer`. Its fix line names `GIT_AUTHOR_NAME`, `GIT_AUTHOR_EMAIL`, `GIT_COMMITTER_NAME` and `GIT_COMMITTER_EMAIL`, filled in with this machine's name and email (or "your name" and "your email" when none resolves). The values appear only in the returned message, never in the failed-check marker, the setup record or the calibration. A passed check's message gains the line "It has a git identity to commit with." A report that carries no identity (the fallback line, or an older plugin's report) still fails on `identity`, but its message never claims the session has no identity and never prints the variables fix.
- A report without `identity`, from an older cloud plugin, stays readable and fails on `identity` as well as on `version`. `REPORT_FIELDS` is unchanged.
- The `git-identity` launch ruling reads `git var`. Its cascade names the `GIT_AUTHOR_*`/`GIT_COMMITTER_*` variables first, and its missing-identity test is `git -c user.useConfigOnly=true var GIT_AUTHOR_IDENT` or `GIT_COMMITTER_IDENT` failing, never an empty `git config` answer. `launch_doctrine.git_identity(cwd)` is the one implementation, and the cloud check calls it. Every composed launch carries this text.
- The setup text writes no identity step. The platform's own signed identity is the default. A project that wants another author sets the four variables on its cloud environment, and those commits most likely show as Unverified. `git config` inside a cloud session is refused by the session's permission classifier as persistence.
- Recovering a stack in the cloud takes one adoption launch per layer, bottom first, each layer brought current with the one below before its launch (`skills/showrunner/reference/orchestration.md` § Adoption mechanics).

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
