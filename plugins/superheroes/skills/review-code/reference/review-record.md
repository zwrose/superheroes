The review record: the plain account of one PR's review. This file is the one home of the rule for how a review writes it. The light lane, the micro lane, and `--review-only` each point here.

## What the record is

Each review session adds one new PR comment whose first line is `<!-- superheroes:review-record -->`.
Earlier ones are never edited; the latest is the current record, and it links the one before it under
`previousRecord`. Each raw output file named in the account gets its own comment
(`<!-- superheroes:review-raw-output -->`), verbatim with secrets redacted, and the record links it
under `rawOutputs`. Each review ends by writing it.

Across sessions the account must relist every finding the latest earlier record listed (matched by identity
key; an unresolved one stays pending, null), or the write refuses `review-record-unaccounted`.

The writer holds some facts in code: the lane, the final commit, CI on it, and whether an engine-run
reviewer ran. Those win over your account. A reviewer run counts as run by code only when its engine's
run record covers the final commit. A run only you report is marked "reported by the session", and so is
every reviewer's findings coverage: the code holds no reviewer's findings, only the account and its raw files.

## Write the account

Write a JSON file with `"schema": "review-account/1"` and these keys:

- `pr`: the PR number. `sessionId`: this review session. `lane` and `laneReason`: the lane and why.
- `finalCommit`: the commit the review ended on. `ci`: CI on it, as you saw it.
- `reviewers`: each `{name, vendor, model, planned, ran, runDir}` plus optional `notIndependent` (bool),
  `ownerWord` (`{words, where}`). List every planned reviewer, ran or not. `runDir`: its run directory, or empty.
- `findings`: each as `{id, title, severity, file, line, body, consequence, outcome, reason,
  reviewer, findingKey}`; `consequence`, `findingKey` may be null. `id` is the reviewer's own (never
  a staged `v0`) and never the identity: `session_contract.finding_identity_key` is.
- `rawFindingsFiles`, `rounds` as `{count, cap, stoppedAtCap}`, `checked` (what was checked), optional `makers` (each `{family, source}`).
- `goAheads`: the owner's word to go on without a planned review. Either
  `{reviewer, kind: "standing-ruling", canonId}` or `{reviewer, kind: "owner-words", words, where}`. A reviewer's `ownerWord` is a separate channel: the owner's word that let a same-family reviewer run.

Every finding gets a reason and an outcome (`null` while undecided): fixed, shown wrong, a craft call,
left for the owner, or settled by an owner ruling. Exact spellings: `review_findings_schema.OUTCOMES`.

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

## When it refuses

- `review-record-unreadable`: the latest record could not be parsed; park and report. Never delete or
  overwrite a record by hand.
- `review-record-unaccounted`: relist each named earlier finding in the account and write again.
- `review-account-invalid`: the account is wrong. Fix it and write again.
- `review-record-too-large`: shorten the account's long text (or split the raw output file) and write again.
- `review-record-forbidden-claim`: rewrite the account text the writer quotes in its summary.
- `review-record-gh-failed`: GitHub could not be read or written. Retry; else park and report.
- `review-record-internal-error`: park the PR and report it.
- `review-record-missing`: on `read`, no record has been written for that PR.

## What "reviewed" means

The record says reviewed only when all five hold: CI is green on the PR's final commit; every
finding in the account has an outcome and a reason; no planned review is missing and a planned
reviewer ran; no raw output file is unread; and the final commit was read from the PR.
Any finding short of that is listed in what is left. `makers`, `notIndependent` and `ownerWord` are shown as given, never checked, and never change "reviewed".

- A planned review that did not run, with no owner go-ahead: the PR stays parked.
- With a go-ahead: the record names the missing review and the go-ahead, and is still not reviewed.
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
