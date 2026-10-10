The review record: the plain account of one PR's review. This file is the one home of the rule for how a review writes it. The light lane, the micro lane, and `--review-only` each point here.

## What the record is

One PR comment whose first line is `<!-- superheroes:review-record -->`. A PR has exactly one. A
later review edits it in place; earlier sessions' findings stay in it (whole, in an archive comment
the record names, if they would not fit). An owner decision an earlier session left stays pending
until a later session, or a rewrite, lists that finding with another outcome. Each review ends by writing it.

The writer holds some facts in code: the lane, the final commit, CI on it, and whether an
engine-run reviewer ran. Those win over your account. A reviewer whose run only you report is
marked "reported by the session".

## Write the account

Write a JSON file with `"schema": "review-account/1"` and these keys:

- `pr`: the PR number. `sessionId`: this review session. `lane` and `laneReason`: the lane and why.
- `finalCommit`: the commit the review ended on. `ci`: CI on it, as you saw it.
- `makers`: each maker family, as `{family, source}`.
- `reviewers`: each as `{name, vendor, model, planned, ran, runDir, ownerWord}`. List every
  planned reviewer, whether or not it ran. `runDir` is its run directory; with none, leave it empty.
- `findings`: each as `{id, title, severity, file, line, body, consequence, outcome, reason,
  reviewer, key}`; `consequence` and `key` may be null. `id` is the reviewer's own id, not a staged
  `v0`. Across sessions a finding is its `key`, else its file plus title.
- `rawFindingsFiles`, `rounds` as `{count, cap, stoppedAtCap}`, `checked` (what was checked).
- `goAheads`: the owner's word to go on without a planned review. Either
  `{reviewer, kind: "standing-ruling", canonId}` or `{reviewer, kind: "owner-words", words, where}`.

Every finding gets a reason and one of five outcomes, spelled exactly: `fixed`, `shown-wrong`,
`craft`, `left-for-owner`, `ruling`.

```json
{"schema": "review-account/1", "pr": 12, "sessionId": "s1", "lane": "light",
 "laneReason": "one file, no contract change", "finalCommit": "abc1234", "ci": "green",
 "makers": [{"family": "anthropic", "source": "dispatch"}], "reviewers": [{"name": "r1",
   "vendor": "codex", "model": "m", "planned": true, "ran": true, "runDir": "runs/r1", "ownerWord": null}],
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

Each prints one JSON object (exit 0 ok, 1 refusal). `$ROOT_DIR` is `${CLAUDE_PLUGIN_ROOT}`. Put the
record's URL in the PR body's build record.

## When it refuses

- `review-record-duplicate` or `review-record-unreadable` (on `read` too, for a missing
  archive): park the PR and report it on the PR. Never delete or overwrite a record by hand.
- `review-account-invalid`: the account is wrong. Fix it and write again.
- `review-record-too-large`: shorten the account's long text and write again. (Earlier sessions
  move whole to an archive comment; `read` returns it as `archivedHistory`.)
- `review-record-forbidden-claim`: rewrite the account text the writer quotes in its summary.
- `review-record-gh-failed`: GitHub could not be read or written. Retry; else park and report.
- `review-record-internal-error`: park the PR and report it.
- `review-record-missing`: on `read`, no record has been written for that PR.

## What "reviewed" means

The record says reviewed only when all five hold: CI is green on the PR's final commit; every
finding, including each one a reviewer raised, has one of the five outcomes with its reason; no
planned review is missing; the final commit was read from the PR; and the makers' model families
are recorded. A finding left for the owner keeps the record at not reviewed until the owner's
decision is recorded as `fixed`, `shown-wrong`, or `ruling`. A reviewer run counts only when the
engine's own record shows it graded as a success; a forfeited run is a missing review.

- A planned review that did not run, with no owner go-ahead: the PR stays parked.
- With a go-ahead: the record names the missing review and the go-ahead, and is still not reviewed.
- A reviewer from a maker's family counts as not run, unless the owner said so for that change;
  then the record says the review was not independent.
- The record and the PR text never say a change has no bugs; they say what was checked and what
  is left.

## Map each exit's results to outcomes

**`--review-only` exit.** Branch mode has no PR, so no record is written.
- A REFUTED drop becomes `shown-wrong`, with the drop reason as the reason.
- A finding the session decided is code-quality only becomes `craft`, with the reason.
- A finding put to a human (the undecided set) becomes `left-for-owner`.
- An approved-to-fix finding has no outcome until it is fixed.
- `rawFindingsFiles`: the round's `findings-*.json`, plus a file per stdout reviewer (codex, cursor)
  holding its original findings, saved before compilation.

**Light and micro lanes.**
- A finding fixed and re-reviewed becomes `fixed`.
- A finding argued wrong becomes `shown-wrong`, with the argument as the reason.
- A finding covered by a standing ruling, or a recorded residual under the review discipline's
  review bars, becomes `ruling`, naming which.
- Anything the owner must decide becomes `left-for-owner`.
- The one reviewer's `runDir` is its `dispatch-review` run directory; the engine's record proves it ran.
