# Review record cloud REST bite-proof — `test_review_record.py`

**Provenance:** claude write channel.

## Summary

| Class | Representative element | Axis | Proving test | Verdict |
|---|---|---|---|---|
| C-select | the cloud condition in `_readers` | a cloud session on the old `gh pr`/`gh issue`/`gh repo` readers | `test_cloud_cli_write_reads_through_rest_only_and_takes_the_issue_from_the_body_first_line` | proven |
| L-first-line | the first-line cut in `_closing_issues` | a closing keyword on a later line read as the PR's closing issue | `test_closing_issues_reads_only_the_first_line_and_fails_closed[not-on-the-first-line]` | proven |

Unproven (no neutralization run, inside the order's six-command budget): the other
`_closing_issues` rows (non-closing verb, whole-word keyword, whole-number, other-repo qualified
reference, CRLF, duplicates, one issue per keyword); `test_the_default_readers_are_the_rest_set_only_when_the_cloud_variable_is_true`
(the `"true"`-only comparison and the override-wins leg); `test_rest_pr_and_issue_readers_fail_closed_on_a_missing_or_malformed_answer`;
the argv-log leg of the cloud round trip (that no `pr`/`issue`/`repo` argv is logged) was not run apart from the condition proof above.

---

## C-select — the cloud condition in `_readers`

**guarded element:** the line `cloud = os.environ.get(cloud_pass.CLOUD_ENV) == "true"` in
`_readers`. **axis:** in a cloud session the defaults for `pr_meta`, `issue_body` and `repo_name` are
the REST readers, so no `gh pr`, `gh issue` or `gh repo` call is made.

**neutralization:** in `plugins/superheroes/lib/review_record.py`, `_readers`:
`cloud = os.environ.get(cloud_pass.CLOUD_ENV) == "true"` became
`cloud = False and os.environ.get(cloud_pass.CLOUD_ENV) == "true"`.

**raw red:** (run of
`test_review_record.py::test_cloud_cli_write_reads_through_rest_only_and_takes_the_issue_from_the_body_first_line`;
the pytest source dump of the test body is elided here, the failure lines are verbatim)
```
F                                                                        [100%]
>       assert proc.returncode == 0 and out["ok"] and out["action"] == "created", (proc.stdout, proc.stderr)
E       AssertionError: ('{"ok": false, "reason": "review-record-gh-failed", "detail": "the repository could not be resolved from the repo root"}
E         ', '')
E       assert (1 == 0)
FAILED plugins/superheroes/lib/tests/test_review_record.py::test_cloud_cli_write_reads_through_rest_only_and_takes_the_issue_from_the_body_first_line
1 failed in 4.90s
EXIT=1
```

**restore:** the inverse edit, `cloud = False and os.environ.get(...)` back to
`cloud = os.environ.get(...)`.

**restore receipt:** `grep -n 'cloud = ' review_record.py` printed
`217:    cloud = os.environ.get(cloud_pass.CLOUD_ENV) == "true"`.

**raw green:**
```
.                                                                        [100%]
1 passed in 5.86s
EXIT=0
```

## L-first-line — only the first line of the PR body counts

**guarded element:** the first-line cut in `_closing_issues`. **axis:** a `Closes #N` on any line
after the first is ignored.

**neutralization:** in `_closing_issues`,
`first = body.split("\n", 1)[0].removesuffix("\r")` became `first = body`.

**raw red:** (run of
`test_review_record.py::test_closing_issues_reads_only_the_first_line_and_fails_closed[not-on-the-first-line]`;
the pytest parameter list dump is elided here, the failure lines are verbatim)
```
F                                                                        [100%]
body = 'Intro\nCloses #3.', repo = 'o/r', expected = []
>       assert rr._closing_issues(body, repo) == expected
E       assert [3] == []
E         
E         Left contains one more item: 3
E         Use -v to get more diff
FAILED plugins/superheroes/lib/tests/test_review_record.py::test_closing_issues_reads_only_the_first_line_and_fails_closed[not-on-the-first-line]
1 failed in 2.41s
EXIT=1
```

**restore:** the inverse edit, `first = body` back to
`first = body.split("\n", 1)[0].removesuffix("\r")`.

**restore receipt:** `grep -n 'first = ' review_record.py` printed
`138:    first = body.split("\n", 1)[0].removesuffix("\r")`.

**raw green:** not run apart from the full post-restore state: the order's six-command budget was spent
(baseline, post-edit suite, red 1, green 1, red 2, validator), so this element has no separate green
capture. The restored line is quoted above; the orchestrator's re-run closes it.
