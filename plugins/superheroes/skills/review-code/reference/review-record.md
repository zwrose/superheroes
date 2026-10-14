The review record: the plain account of one PR's review. This file is the one home of the rule for how a review writes it. The full lane, the light lane, the micro lane, and `--review-only` each point here.

## Contents

- [What the record is](#what-the-record-is)
- [Write the account](#write-the-account)
- [Write it, read it](#write-it-read-it)
- [The full lane writes it from the session](#the-full-lane-writes-it-from-the-session)
- [When it refuses](#when-it-refuses)
- [What "reviewed" means](#what-reviewed-means)
- [Map each exit's results to outcomes](#map-each-exits-results-to-outcomes)

## What the record is

Each review session adds one new PR comment whose first line is `<!-- superheroes:review-record -->`.
Earlier ones are never edited; the latest is the current record, and it links the one before it under
`previousRecord`. Each raw output file named in the account gets its own comment
(`<!-- superheroes:review-raw-output -->`), verbatim unless withheld (below), and the record links it
under `rawOutputs`. Each review ends by writing it. A raw output that holds a credential-shaped assignment (a secret-named field followed by `:` or `=`) or a private-key block is withheld: its comment says so and gives the line count, and its findings stay in the record. Any record text holding one reads `[REDACTED FIELD]`, and secret-named structured fields read `[REDACTED]`.

A record that does not fit one comment posts as a head comment plus part comments (`<!-- superheroes:review-record-part -->`), each under GitHub's limit. The parts go up first, then the head, which names them by comment id and carries a hash and a length that check them. `read`, and the next write's look at the earlier record, join the parts back into the whole record. A part that is missing, altered or cut short makes the record unreadable (`review-record-unreadable`); a part comment is never a record by itself, and a write that stops part-way leaves parts no head names, never a half record. When even the head would be too long, its summary shows a count (listed in the full record) in place of the long lists; the full lists stay in the record.

Each finding carries the sheet part its outcome lands in (`sheetPart`; none while the outcome is undecided). The writer re-checks every cited decision against what is on record when it writes: a `ruling` whose cited decision is not on record becomes `left-for-owner`, and a finding left for the owner whose cited decision is on record becomes a `ruling`. Each change is listed under `decisionRechecks`, and the finding's reason says why. A ruling that cites no decision names its basis in prose and is left as it is. The summary says how many rounds ran against which cap (the round cap or the round ceiling) and whether the loop stopped at it, and lists findings that were not taken into the review, with their reasons, under `refused`.

Across sessions the account must relist every finding the latest earlier record listed (matched by identity
key; an unresolved one stays pending, null), or the write refuses `review-record-unaccounted`.

The writer holds some facts in code: the lane, the final commit, CI on it, and whether an engine-run
reviewer ran. Those win over your account. A reviewer run counts as run by code only when its engine's
run record covers the final commit. A run only you report is marked "reported by the session", and so is
every reviewer's findings coverage: the code holds no reviewer's findings, only the account and its raw files.

## Write the account

Write a JSON file with `"schema": "review-account/1"` and these keys:

- `pr`: the PR number. `sessionId`: this review session. `lane` and `laneReason`: the lane and why.
  The record carries `laneBasis`, the lane rule run over the PR's changed files (`rubric/review-discipline.md` § The lane floor says when its floor is full).
  A lane below that floor makes the record read not reviewed.
- `finalCommit`: the commit the review ended on. `ci`: CI on it, as you saw it.
- `reviewers`: each `{name, vendor, model, planned, ran, runDir}` plus optional `notIndependent` (bool; accepted and ignored, the record computes it),
  `ownerWord` (`{words, where}`), `commit` (the commit that reviewer reviewed, when it is not the final commit; a row that names none is judged against the final commit). List every planned reviewer, ran or not. `runDir`: its run directory, or empty.
- `findings`: each as `{id, title, severity, file, line, body, consequence, outcome, reason,
  reviewer, findingKey}`; `consequence`, `findingKey` may be null. Optional `decidedBy`: null, or the decision the outcome rests on, `{kind: "canon" | "residual" | "sheet-answer", ref}` (`ref` is a string, or `{pr, card}` for a sheet answer). The writer checks it against what is on record. `id` is the reviewer's own (never
  a staged `v0`) and never the identity: `session_contract.finding_identity_key` is.
- `rawFindingsFiles`, `rounds` as `{count, cap, stoppedAtCap}` plus optional `capKind` (`"rounds"`, the default, when the cap is the round cap; `"ceiling"` when the stop was the round ceiling), `checked` (what was checked), optional `makers` (each `{family, source}`).
- Optional `refused`: findings a reviewer raised that were not taken into the review, each `{title, reason}` plus optional `file`, `line`, `round`. They are listed, never counted as findings. Optional `sheetAnswers`: the PR sheet store's saved answers, which a sheet-answer `decidedBy` is checked against. Optional `baseRef`: the commit the recorded residuals are read at.
- `goAheads`: the owner's word to go on without a planned review. Either
  `{reviewer, kind: "standing-ruling", canonId}` or `{reviewer, kind: "owner-words", words, where}`. Each of `canonId`, `words` and `where` is a non-empty string; a go-ahead missing one, or carrying anything else there, does not count and the PR stays parked. A standing ruling counts only while its Canon entry is on record; if it is not, the go-ahead is incomplete and the PR stays parked. A reviewer's `ownerWord` is a separate channel: the owner's word that let a same-family reviewer run.

Every finding gets a reason and an outcome (`null` while undecided): fixed, shown wrong, a craft call,
left for the owner, or settled by an owner ruling. Exact spellings: `review_findings_schema.OUTCOMES`.
When a review loop ends, every finding it took in is settled by its consequence, never its severity
([how the loop settles what is left](round-driver.md#how-the-loop-settles-what-is-left)). A finding with
a real consequence that is left unfixed with no on-record decision is a [leftover](../../../rubric/glossary.md#leftover)
and takes the outcome `left-for-owner`.

```json
{"schema": "review-account/1", "pr": 12, "sessionId": "s1", "lane": "light",
 "laneReason": "one file, no contract change", "finalCommit": "abc1234", "ci": "green",
 "reviewers": [{"name": "r1",
   "vendor": "codex", "model": "m", "planned": true, "ran": true, "runDir": "runs/r1"}],
 "findings": [{"id": "f1", "title": "Unchecked index", "severity": "Important",
   "file": "a.py", "line": 9, "body": "...", "consequence": null, "outcome": "fixed",
   "reason": "bounds check added, re-reviewed", "reviewer": "r1"}],
 "rawFindingsFiles": [], "rounds": {"count": 1, "cap": 3, "stoppedAtCap": false},
 "goAheads": [], "checked": ["the diff", "the tests it touches"]}
```

## Write it, read it

```bash
python3 -B "$ROOT_DIR/lib/review_record.py" write --account <account.json> --repo-root <repo root>
python3 -B "$ROOT_DIR/lib/review_record.py" read --pr <n>
```

Each prints one JSON object (exit 0 ok, 1 refusal); `read` returns the latest record and `earlierRecords`
(the older URLs). `$ROOT_DIR` is `${CLAUDE_PLUGIN_ROOT}`. Put the record's URL in the PR body's build record.

## The full lane writes it from the session

```bash
python3 -B "$ROOT_DIR/lib/review_record_session.py" write --session-dir "$SESSION_DIR" --extras <extras.json> --repo-root <repo root>
```

In PR mode, run it on every terminal verdict of a session driven by the loop's seat commands or by hand `submit`: one that ended on a certified verdict and recorded at least one seat result or one round's seat status. Any other session is refused `review-session-unsupported`. It prints one JSON object (exit 0 ok, 1 refusal), reads the finished session directory, builds the account itself, and hands it to the writer; nothing else posts. Do not retype what the session already holds. Push any fixes before writing the record, because the record is judged against the PR's final commit.

The extras file holds only what the driver never does: `{"schema": "review-session-extras/1", "pr": <int>, "repo": <"owner/name" or null>, "laneReason": <string or null>, "ci": <string or null>, "runDirs": [<run directory>, ...], "goAheads": [...], "makers": [{family, source}, ...], "checked": [<string>, ...], "sheetAnswers": <object or null>, "baseRef": <non-empty string or null>}`. Only `schema` and `pr` are required. `goAheads`, `makers`, `checked`, `sheetAnswers` (the PR sheet store's `answers` object) and `baseRef` (the commit or ref the residuals are read at) pass to the account unchanged; a `sheetAnswers` that is not an object or a `baseRef` that is not a non-empty string is refused `review-session-extras-invalid`. A go-ahead's `reviewer` is the reviewer row's name exactly as the adapter builds it: `<seat> (round <n>)` for a panel seat, `<phase without the dispatch- prefix> <seat> (round <n>)` for any other review phase, for example `security-reviewer (round 1)`.

What comes from the session:

- `rounds`: the count of rounds, the cap, and whether the loop stopped at it. The cap is the configured round cap; when the loop stopped at the round ceiling instead, the cap named is that ceiling and `capKind` reads `ceiling`.
- `reviewers`: one row per recorded review seat, with the commit that seat cited as the one it covered. A superseded attempt is left out and the highest attempt of a slot counts. A seat recorded missing is a reviewer that did not run, unless a later round ran the same seat. A seat the seat map marks same-family carries `notIndependent`. A session driven by hand `submit` journals no seat, so its reviewers are read from each panel round's seat status: a seat that ran is a reviewer that ran, a seat marked missing is one that did not (unless a later round ran it), and each reads "reported by the session" with no run directory. Its reviewers' raw outputs were not stored, so the account carries no raw findings files and its `checked` list says so.
- `runDir`: a directory in `runDirs` is bound to the one seat whose recorded runner nonce equals the nonce in that directory's engine record. A directory that matches no seat or several, or cannot be read, is not used. A seat with no run directory reads "reported by the session".
- `makers`: the extras' makers, plus the fixer's family (source `review loop fixer`) when a round ran a fixer.
- `finalCommit`: the fix-fold head when the session holds one, else the session's head.
- `findings` and outcomes, from the disposition ledger and the live findings; `rawFindingsFiles`, each panel, gap-sweep and scoped-finder seat's findings payload, posted without the runner's telemetry.
- `refused`: every finding a reviewer raised that the loop did not take in (the round's compile drops), each with its round, in round order.
- `decidedBy`: on each finding, the decision its outcome rests on. It is the settled disposition's own, else the newest ruling logged against the finding (or against one merged into it) when that ruling came after the finding's latest raise, else `null`. The writer re-checks it against what is on record; the adapter only carries it.
- A later session's account relists the latest earlier record's findings that this session did not raise, each with the outcome and reason it had.

Outcomes:

- A fixed finding becomes `fixed`, with the round it was audited in; a fix a later full panel did not raise again reads `fixed; the full panel in round <n> did not raise it again`.
- A finding refuted by verification becomes `shown-wrong`, with the refuted reason; a refutation whose reason starts `author-justified` becomes `left-for-owner`.
- When the loop ends, every finding it took in that is not fixed or shown wrong is settled by its consequence ([how the loop settles what is left](round-driver.md#how-the-loop-settles-what-is-left) says how). The adapter reads a settled disposition `craft`, `left-for-owner` or `ruling` as the outcome of the same name, with the recorded `settledReason` as its reason.
- An out-of-scope finding is settled like any other open one: it becomes `ruling` only when a decision on record settles it, and otherwise `left-for-owner`, a leftover.
- A finding merged into another takes the representative's outcome, and its reason names the representative. A ruling logged against any finding merged into the representative counts as a ruling on it; the newest one stands.
- A finding with no disposition newer than the finding, or whose merge cannot be followed, stays undecided (`null`, "still open when the review loop ended"), so the record reads not reviewed.

Refusals, before anything is posted:

- `review-session-unreadable`: a session file the account needs is missing or malformed; the detail names it (the loop state, the journal or its fault file, `meta.json`'s `sessionId`, the disposition ledger). Restore the session directory and write again; never edit the files by hand.
- `review-session-not-terminal`: the loop has not ended. Finish the loop, then write.
- `review-session-unsupported`: the session recorded no seat result and no round's seat status, or ended on a terminal that is not a certified verdict (the attested manual terminal, or an unknown one). Write the account by hand per "Write the account".
- `review-session-extras-invalid`: the extras file is missing, unparseable or malformed; the detail names the key. Fix it and write again.

## When it refuses

- `review-record-unreadable`: the latest record could not be parsed; park and report. Never delete or
  overwrite a record by hand.
- `review-record-unaccounted`: relist each named earlier finding in the account and write again.
- `review-account-invalid`: the account is wrong. Fix it and write again.
- `review-record-too-large`: a raw output file is over GitHub's limit (split it), or the summary alone cannot fit one comment (shorten the account's long names or lists); then write again. A long record is not refused for its length: it posts in parts.
- `review-record-forbidden-claim`: rewrite the account text the writer quotes in its summary.
- `review-record-gh-failed`: GitHub could not be read or written. Retry; else park and report.
- `review-record-internal-error`: park the PR and report it.
- `review-record-missing`: on `read`, no record has been written for that PR.

## What "reviewed" means

The record says reviewed only when all five hold: CI is green on the PR's final commit; every
finding in the account has an outcome and a reason; no planned review is missing and a planned
reviewer ran; no raw output file is unread; and the final commit was read from the PR.
At least one planned reviewer's run must cover the final commit. A reviewer listed for an earlier
commit counts as run only for that commit, and the record shows which commit it covered; a head that
moves after the last review round still reads not reviewed. A session whose final commit differs from the PR's final commit also reads not reviewed, because its outcomes belong to the other commit.
Any finding short of that is listed in what is left.

Reading and independence are computed by the record, never taken from the session's account:

- **Reading.** When the lane is not `full` (including an unknown lane), a reviewer counts as run only when the engine's own record of its run reads `observation.read == "engaged"`. A reviewer the session only reports, or whose engine record shows no reading or an unknown one, does not count; its row says so, and each row on such a lane shows `reading` as `engaged` or `not-shown`. The `full` lane is unchanged.
- **Which reviewer.** A reviewer credited from an engine record must be the reviewer that record names: the record's vendor and model must match the row, and the row's family is read from the record. A record that names no vendor or model, or a different one, does not count.
- **Independence.** A reviewer from a maker's family counts only with the owner's word for the change (`ownerWord`, with non-empty `words` and `where`), and is then shown "not independent". A reviewer whose family cannot be read does not count while makers are named. A `notIndependent` value in the account is ignored. No named maker means not reviewed, because independence cannot be shown.
- **`reading-next`.** `review_record.py reading-next --run-dir A [--run-dir B] [--seat-map FILE] --maker-family F [--maker-family F ...]` prints one JSON object `{"next": ..., "reason": ...}` for a review whose reading is not shown. It makes no model call and writes nothing. Its four answers: `accept` when any run's record shows a reading; `rerun` when exactly one run was made and it shows none; `move-up` when two runs show none and the seat map allows it; `park` otherwise, including when no run is given. Move-up needs all of these: the seat map has a roster, a seat entry for every roster seat, every seat filled and naming a family, no seat in a maker's family, and at least one maker family given. A missing, unreadable or non-JSON seat map is `park`. More than two runs are read as two.

- A planned review that did not run, with no owner go-ahead: the PR stays parked.
- With a go-ahead: the record names the missing review and the go-ahead, and is still not reviewed. A standing-ruling go-ahead counts only when the writer finds its Canon entry on record at write time; an owner's-words go-ahead needs no such check.
- A finding whose ruling cites a decision that is not on record when the record is written is listed as left for the owner, so the record reads not reviewed until the owner decides.
- The record and the PR text never say a change has no bugs; they say what was checked and what
  is left.

## Map each exit's results to outcomes

**`--review-only` exit.** Branch mode has no PR, so no record is written.
- A REFUTED drop becomes `shown-wrong`, with the drop reason as the reason.
- A finding the session decided is code-quality only becomes `craft`, with the reason.
- A finding put to a human (the undecided set) becomes `left-for-owner`.
- An approved-to-fix finding has no outcome until it is fixed.
- `rawFindingsFiles`: the round's `findings-*.json`, plus a file per stdout reviewer (codex, cursor)
  holding its original output, saved before compilation.

**Light and micro lanes.**
- A finding fixed and re-reviewed becomes `fixed`.
- A finding argued wrong becomes `shown-wrong`, with the argument as the reason.
- A finding covered by a standing ruling, or a recorded residual under the review discipline's
  review bars, becomes `ruling`, naming which.
- Anything the owner must decide becomes `left-for-owner`.
- The one reviewer's `runDir` is its `dispatch-review` run directory; the engine's run record, covering the final commit, proves it ran.
