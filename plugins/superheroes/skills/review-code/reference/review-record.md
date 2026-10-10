The review record: the plain account of one PR's review. This file is the one home of the rule for
how a review writes it. The light lane, the micro lane, and `--review-only` each point here and
restate none of it.

## What the record is

One PR comment whose first line is `<!-- superheroes:review-record -->`. A PR has exactly one. When
a review is written again, the comment is edited in place, and earlier sessions' findings stay in
it. Each review ends by writing it.

The record writer holds some facts in code: the lane, the final commit, CI on that commit, and
whether an engine-run reviewer ran. Those win over your account. A reviewer whose run only you
report is marked "reported by the session".

## Write the account

Write a JSON file with `"schema": "review-account/1"` and these keys:

- `pr`: the PR number. `sessionId`: this review session. `lane` and `laneReason`: the lane and why.
- `finalCommit`: the commit the review ended on. `ci`: CI on that commit, as you saw it.
- `makers`: each maker family, as `{family, source}`.
- `reviewers`: each as `{name, vendor, model, planned, ran, runDir, ownerWord}`. List every
  reviewer that was planned, whether or not it ran. `runDir` is the reviewer's run directory.
  With no run directory, leave it empty. The record then says the run is reported by the session.
- `findings`: each as `{id, title, severity, file, line, body, consequence, outcome, reason,
  reviewer}`. `consequence` may be null.
- `rawFindingsFiles`, `rounds` as `{count, cap, stoppedAtCap}`, and `checked`: what was checked.
- `goAheads`: the owner's word to go on without a planned review. Either
  `{reviewer, kind: "standing-ruling", canonId}` or `{reviewer, kind: "owner-words", words, where}`.

Every finding gets one of five outcomes, spelled exactly, and a reason: `fixed`, `shown-wrong`,
`craft`, `left-for-owner`, `ruling`.

```json
{"schema": "review-account/1", "pr": 12, "sessionId": "s1", "lane": "light",
 "laneReason": "one file, no contract change", "finalCommit": "abc1234", "ci": "green",
 "makers": [{"family": "claude", "source": "dispatch"}],
 "reviewers": [{"name": "r1", "vendor": "codex", "model": "m", "planned": true, "ran": true,
   "runDir": "runs/r1", "ownerWord": null}],
 "findings": [{"id": "f1", "title": "Unchecked index", "severity": "Important",
   "file": "a.py", "line": 9, "body": "...", "consequence": null, "outcome": "fixed",
   "reason": "bounds check added, re-reviewed", "reviewer": "r1"}],
 "rawFindingsFiles": [], "rounds": {"count": 1, "cap": 3, "stoppedAtCap": false},
 "goAheads": [], "checked": "the diff, the tests it touches"}
```

## Write it, read it

```bash
python3 -B "$ROOT_DIR/lib/review_record.py" write --account <account.json> --repo-root <repo root>
python3 -B "$ROOT_DIR/lib/review_record.py" read --pr <n>
```

Each prints one JSON object and exits 0 on ok, 1 on a refusal.
`$ROOT_DIR` is `${CLAUDE_PLUGIN_ROOT}`. Put the record's URL in the PR
body's build record. A PR names its record by that comment, and `read` finds it again.

## When it refuses

- `review-record-duplicate` or `review-record-unreadable`: park the PR and report it on the PR.
  Never delete or overwrite a record by hand.
- `review-account-invalid`: the account is wrong. Fix it and write again.
- `review-record-too-large`: shorten the account's long text and write again. Do not split the
  record into a second comment.
- `review-record-missing`: on `read`, no record has been written for that PR.

## What "reviewed" means

The record says reviewed only when all three hold: CI is green on the PR's final commit, every
finding has one of the five outcomes with its reason, and no planned review is missing.

- A planned review that did not run, with no owner go-ahead: the PR stays parked.
- With a go-ahead: the record names the missing review and the go-ahead. It still does not say
  reviewed.
- A reviewer from a maker's family counts as not run, unless the owner said so for that change.
  Then the record says the review was not independent.
- The record and the PR text never say a change has no bugs. They say what was checked and what
  is left.

## Map each exit's results to outcomes

**`--review-only` exit.** Branch mode has no PR, so no record is written.
- A REFUTED drop becomes `shown-wrong`, with the drop reason as the reason.
- A finding the session decided is code-quality only becomes `craft`, with the reason.
- A finding put to a human (the undecided set) becomes `left-for-owner`.
- An approved-to-fix finding has no outcome until it is fixed. The record says what is missing.
- `rawFindingsFiles` are the round's `findings-*.json` files.

**Light and micro lanes.**
- A finding fixed and re-reviewed becomes `fixed`.
- A finding argued wrong becomes `shown-wrong`, with the argument as the reason.
- A finding covered by a standing ruling becomes `ruling`, naming the ruling.
- Anything the owner must decide becomes `left-for-owner`.
- The one reviewer's `runDir` is its `dispatch-review` run directory, so the engine's own record
  proves it ran.
