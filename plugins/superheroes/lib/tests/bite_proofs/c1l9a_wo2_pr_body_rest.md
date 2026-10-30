# C1-L9a WO-2 bite-proof: PR-body publish over REST, and no false "did not copy" line

**Provenance:** `plugins/superheroes/lib/pr_body_stage.py` (`_read_live`, the edit call in `_publish`, `record_line`) with `plugins/superheroes/lib/tests/test_pr_body_stage.py`. Each neutralization was applied as a targeted edit and undone by the inverse edit; no `git checkout`, `restore`, `reset` or `stash` was used. Runner command: `scripts/pinned-python -B -X pycache_prefix=/home/user/superheroes/.git/pyc-wo2 -m pytest <node> -q -p no:cacheprovider`. Captures are the runner's own output with the `UV_NATIVE_TLS` deprecation warning line dropped; nothing else was cut. No secrets, tokens or private URLs appear in them (the temp paths are the sandbox's).

## Guarded elements

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| G1 | `pr_body_stage._read_live` argv | the live body is read through the REST API, never `gh pr view` | `test_publish_copies_the_audited_staged_body_with_exactly_two_reads_and_one_patch` |
| G2 | `pr_body_stage.record_line` no-fix guard (`_has_fix_to_copy`) | a review with no PR-body fix to copy never says it did not copy one, whatever the refusal reason | `test_a_review_with_no_pr_body_fix_never_says_it_did_not_copy_one` |

The PATCH argv in `_publish` is pinned by the same G1 test (`gh.calls[1] == edit_argv(staged)`) but has no neutralization of its own in this order's declared set; it is not claimed as proven here.

### G1 — the REST read

- **site:** `plugins/superheroes/lib/pr_body_stage.py`, `_read_live`
- **neutralization:** replace `    code, out = _run(runner, ["gh", "api", _pull_endpoint(pr)])` with `    code, out = _run(runner, ["gh", "pr", "view", str(pr), "--json", "body"])`
- **raw red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_publish_copies_the_audited_staged_body_with_exactly_two_reads_and_one_patch _
>       assert (out["ok"], out["outcome"], out["reason"]) == (True, "published", None)
E       AssertionError: assert (False, 'refu...e-unreadable') == (True, 'published', None)
E         At index 0 diff: False != True
FAILED plugins/superheroes/lib/tests/test_pr_body_stage.py::test_publish_copies_the_audited_staged_body_with_exactly_two_reads_and_one_patch
1 failed in 2.34s
```

- **restore:** inverse edit. **restore receipt**, the restored line (`grep -n` at line 225): `    code, out = _run(runner, ["gh", "api", _pull_endpoint(pr)])`
- **raw green:** `.  [100%]` / `1 passed in 2.61s`
- **verdict:** RED->GREEN

### G2 — the no-fix guard in `record_line`

- **site:** `plugins/superheroes/lib/pr_body_stage.py`, `record_line`
- **neutralization:** delete the two lines `            if not _has_fix_to_copy(session_dir):` / `                return None`
- **raw red** (run with `-x`, so it stops at the first failing case):

```
F
E       AssertionError: assert 'The review did not copy its PR-body fix onto the PR: the PR body on GitHub could not be read.' is None
FAILED plugins/superheroes/lib/tests/test_pr_body_stage.py::test_a_review_with_no_pr_body_fix_never_says_it_did_not_copy_one[pr-body-live-unreadable-nothing-staged]
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 2.70s
```

- **restore:** inverse edit. **restore receipt**, the restored lines (`grep -n` at lines 340-343):

```
340:        if outcome == OUTCOME_REFUSED and isinstance(reason, str):
341:            if not _has_fix_to_copy(session_dir):
342:                return None
343:            phrase = _REFUSAL_PHRASES.get(reason, "the copy was refused (%s)" % reason)
```

- **raw green:** `45 passed in 2.56s` (the test's full parametrization: 9 reasons by 5 no-fix shapes)
- **verdict:** RED->GREEN
