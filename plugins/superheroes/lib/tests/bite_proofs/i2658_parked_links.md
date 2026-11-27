# Bite-proof record: i2658_parked_links

Issue 2658 (work order B). The advisor's park and cleanup verbs read a PR's issues only from what GitHub records.
Detector: `plugins/superheroes/lib/tests/test_cloud_parked_links_2658.py` (edges P1-P14). Guarded code:
`plugins/superheroes/lib/cloud_parked.py` (`_linked_issues`, `notice`, `send_back`) and
`plugins/superheroes/lib/cloud_cleanup.py` (`_plan`).

The guarded-element set is the seven elements the order declared (H1-H7). Every neutralization is one targeted edit,
undone by the inverse edit (no `git checkout`, `restore`, `reset` or `stash`). Each red is the single `-k` run of the
unedited detector. The shared green (after all seven restores) is one run, quoted once at the end; the wide green
follows it. Nothing in the captures is a secret, token or private URL; the temp paths are the sandbox's own.
Command for every run: `scripts/pinned-python -B -X pycache_prefix=/tmp/sh-pyc-2658 -m pytest plugins/superheroes/lib/tests/test_cloud_parked_links_2658.py -q [-k <edge>]`.
Every red below also carried the harness's one-line `UV_NATIVE_TLS` deprecation warning, omitted from the quotes.
The red quotes are excerpts of the raw pytest output, not the whole of it: each omits the `w = namespace(...)` / `cw = namespace(...)`
fixture-repr lines, the `Use -v to get more diff` hints, and the `[gwN]`-free blank lines, and nothing else; the failing
assertion lines, the pass/fail counts and the summary lines are verbatim.

## H1. The removal of the first-line fallback (the DoD break-it proof)

- **Guarded element:** `cloud_parked.py:370-371`, `return found, "github"` for a default-base PR.
- **Axis:** a description mention alone is never a link; only GitHub's closing list links a default-base PR (P1, through the function, `notice` and `cleanup.plan`).
- **Neutralization:** `return found, "github"` became `return found or _first_line_candidates(pull.get("body"), repo), "github"`.
- **Raw red** (`-k test_p1`; it also selects P10-P14, which stay green):

```
FF.....                                                                  [100%]
=================================== FAILURES ===================================
_ test_p1_a_default_base_pr_whose_first_line_names_an_issue_githubs_list_lacks_is_not_linked _
>       assert _links(w, 10) == ([], "github")
E       AssertionError: assert ([101], 'github') == ([], 'github')
E         At index 0 diff: [101] != []
/home/user/superheroes/.claude/worktrees/issue-2658/plugins/superheroes/lib/tests/test_cloud_parked_links_2658.py:64: AssertionError
_ test_p1_a_default_base_pr_whose_first_line_names_an_issue_githubs_list_lacks_is_unlinked_to_cleanup _
>       assert CC.plan(cw.repo, REPO, TCC.PR, env=cw.env, run=cw.gh) == want
E       assert {'ok': True, ...er/name', ...} == {'ok': False,...'pr-unlinked'}
E         Differing items:
E         {'ok': True} != {'ok': False}
/home/user/superheroes/.claude/worktrees/issue-2658/plugins/superheroes/lib/tests/test_cloud_parked_links_2658.py:76: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_parked_links_2658.py::test_p1_a_default_base_pr_whose_first_line_names_an_issue_githubs_list_lacks_is_not_linked
FAILED plugins/superheroes/lib/tests/test_cloud_parked_links_2658.py::test_p1_a_default_base_pr_whose_first_line_names_an_issue_githubs_list_lacks_is_unlinked_to_cleanup
2 failed, 5 passed, 8 deselected in 2.45s
```

- **Restore:** the inverse edit, `return found or _first_line_candidates(pull.get("body"), repo), "github"` back to `return found, "github"`.
- **Restore receipt** (`cloud_parked.py:370-371` read back after the restore):

```
        # axis: the description's first line never links a default-base PR, only GitHub's list does — see bite-proof record i2658_parked_links
        return found, "github"
```

- **Raw green:** the shared green run below.

## H2. The repository leg

- **Guarded element:** `cloud_parked.py:366`, `review_record.github_closing_issues(out, repo)` and its repository leg (the call site's result is the only thing in this file's surface).
- **Axis:** another repository's issue in GitHub's closing list is never this repository's (P2).
- **Neutralization** (inside this order's surface, at the call site; `review_record.py` was not edited, since it lies outside the order's surface): the line
  `found = _sib("review_record").github_closing_issues(out if code == 0 else None, repo)` became
  `found = [r["number"] for r in json.loads(out)["closingIssuesReferences"]] if code == 0 else None`, which counts `ref["number"]` without the repository.
- **Raw red** (`-k test_p2`):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_p2_githubs_list_naming_another_repositorys_issue_is_not_this_repositorys _
    def test_p2_githubs_list_naming_another_repositorys_issue_is_not_this_repositorys(w):
        w.gh.pulls[10] = _pull()
        w.gh.closing[10] = [_ref(101, "other/repo")]
>       assert _links(w, 10) == ([], "github")
E       AssertionError: assert ([101], 'github') == ([], 'github')
E         At index 0 diff: [101] != []
/home/user/superheroes/.claude/worktrees/issue-2658/plugins/superheroes/lib/tests/test_cloud_parked_links_2658.py:85: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_parked_links_2658.py::test_p2_githubs_list_naming_another_repositorys_issue_is_not_this_repositorys
1 failed, 14 deselected in 1.22s
```

- **Restore:** the inverse edit, the `github_closing_issues` call back in place of the repository-less comprehension.
- **Restore receipt** (`cloud_parked.py:366`):

```
        found = _sib("review_record").github_closing_issues(out if code == 0 else None, repo)
```

- **Raw green:** the shared green run below.
- **Not shown:** the repository leg inside `review_record.github_closing_issues` itself (work order A's file) was not neutralized here; its own tests belong to work order A. This entry proves only that `_linked_issues` depends on a repository-aware reading of GitHub's list.

## H3. The unreadable return on a failed closing read

- **Guarded element:** `cloud_parked.py:368-369`, `if found is None: return [], "unreadable"`.
- **Axis:** a closing-list read that fails reads as unreadable, never as "no link" (P3; P4 shares this branch for a malformed list).
- **Neutralization:** `return [], "unreadable"` became `return [], "github"` in that branch.
- **Raw red** (`-k test_p3`):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_____________ test_p3_a_closing_list_read_that_fails_is_unreadable _____________
    def test_p3_a_closing_list_read_that_fails_is_unreadable(w):
        w.gh.pulls[10] = _pull(101)  # the description says "Closes #101"
        w.gh.closing[10] = None  # gh exits non-zero
>       assert _links(w, 10) == ([], "unreadable")
E       AssertionError: assert ([], 'github') == ([], 'unreadable')
E         At index 1 diff: 'github' != 'unreadable'
/home/user/superheroes/.claude/worktrees/issue-2658/plugins/superheroes/lib/tests/test_cloud_parked_links_2658.py:94: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_parked_links_2658.py::test_p3_a_closing_list_read_that_fails_is_unreadable
1 failed, 14 deselected in 3.23s
```

- **Restore:** the inverse edit, `return [], "github"` back to `return [], "unreadable"`.
- **Restore receipt** (`cloud_parked.py:368-369`):

```
        if found is None:
            return [], "unreadable"
```

- **Raw green:** the shared green run below.

## H4. A non-default base not yet in a native stack is read through the timeline

Re-proved by the builder after review round 1 of PR 2664. That round reversed this element on the builder's ruling, recorded on the PR: an upper layer parked before the advisor links its stack must still bind its launch. The earlier element was a "not in a stack means no link" branch. It is gone, and such a PR now takes the stack layer's timeline confirmation.

- **Guarded element:** `cloud_parked.py`, `_linked_issues`: the condition `if snapshot is None and refusal.get("reason") != sc.REASON_NOT_LINKED:` with no "no link" branch after it.
- **Axis:** a non-default-base PR that is not in a native stack is confirmed through GitHub's issue timeline like a stack layer, and is never read as no link. Its park binds its launch at the first notice (both P5 tests).
- **Neutralization:** the earlier branch was added back after that condition: `    if snapshot is None:` / `        return [], "github"`.
- **Raw red** (`-k test_p5`, the builder's run on the committed fix `0c3bab10`, failure lines verbatim):

```
FF                                                                       [100%]
=================================== FAILURES ===================================
_ test_p5_a_non_default_base_pr_not_yet_in_a_stack_is_linked_only_by_the_timeline _
>           assert _links(w, 10) == ([], "timeline")  # the description alone links nothing
E           AssertionError: assert ([], 'github') == ([], 'timeline')
E             At index 1 diff: 'github' != 'timeline'
________ test_p5_a_park_on_a_layer_not_yet_in_a_stack_binds_its_launch _________
>       assert out["kind"] == "lapsed-pass" and out["linkSource"] == "timeline", out
E         lapsed-pass and 'github' == 'timeline'
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_parked_links_2658.py::test_p5_a_non_default_base_pr_not_yet_in_a_stack_is_linked_only_by_the_timeline
FAILED plugins/superheroes/lib/tests/test_cloud_parked_links_2658.py::test_p5_a_park_on_a_layer_not_yet_in_a_stack_binds_its_launch
2 failed, 14 deselected in 1.34s
```

- **Restore:** the inverse edit, which removes the two added lines.
- **Restore receipt:** `git status --porcelain` printed nothing after the restore (the tree matched commit `0c3bab10`).
- **Raw green:**

```
..                                                                       [100%]
2 passed, 14 deselected in 1.29s
```

## H5. The timeline confirmation for a stack layer

- **Guarded element:** `cloud_parked.py:379-385`, `review_record.recorded_links(...)` and its `confirmed` result.
- **Axis:** a stack layer's first-line candidate is linked only when GitHub's timeline records a cross-reference from this PR (P7).
- **Neutralization:** `return confirmed, "timeline"` became `return _first_line_candidates(pull.get("body"), repo), "timeline"`, so the candidates came back unconfirmed.
- **Raw red** (`-k test_p7`):

```
F                                                                        [100%]
=================================== FAILURES ===================================
__ test_p7_a_stack_layer_whose_candidate_has_no_cross_reference_is_not_linked __
    def test_p7_a_stack_layer_whose_candidate_has_no_cross_reference_is_not_linked(w):
        w.gh.pulls[10] = _layer(10, "Part of #101.\n\nthe work")
>       assert _links(w, 10) == ([], "timeline")
E       AssertionError: assert ([101], 'timeline') == ([], 'timeline')
E         At index 0 diff: [101] != []
/home/user/superheroes/.claude/worktrees/issue-2658/plugins/superheroes/lib/tests/test_cloud_parked_links_2658.py:133: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_parked_links_2658.py::test_p7_a_stack_layer_whose_candidate_has_no_cross_reference_is_not_linked
1 failed, 14 deselected in 1.21s
```

- **Restore:** the inverse edit, back to `return confirmed, "timeline"`.
- **Restore receipt** (`cloud_parked.py:383-385`):

```
    if confirmed is None:
        return [], "unreadable"
    return confirmed, "timeline"
```

- **Raw green:** the shared green run below.

## H6. `notice`'s ungated saved-launch call

- **Guarded element:** `cloud_parked.py:463-465`, the `_lane(...)` call in `notice` gated on `(issues or (old and not rebind))`.
- **Axis:** a saved, unsuperseded launch is looked up whatever the link read says (P12; P11 shares it for an unreadable read).
- **Neutralization:** `if (issues or (old and not rebind)) else (None, {}, None)` became `if issues else (None, {}, None)`, which restores the old `if issues` gate.
- **Raw red** (`-k test_p12`):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_p12_a_newer_park_with_a_saved_launch_and_a_readable_empty_list_keeps_that_launch _
        out = _notice(w, 10)
        assert out["kind"] == "lapsed-pass" and out["linkSource"] == "github", out
        entry = _entries(w)[0]
>       assert entry["launchId"] == "l-a" and entry["parkId"] == 1010 and entry["outcome"] is None
E       AssertionError: assert (None == 'l-a')
/home/user/superheroes/.claude/worktrees/issue-2658/plugins/superheroes/lib/tests/test_cloud_parked_links_2658.py:232: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_parked_links_2658.py::test_p12_a_newer_park_with_a_saved_launch_and_a_readable_empty_list_keeps_that_launch
1 failed, 14 deselected in 1.31s
```

- **Restore:** the inverse edit, the gate back to `(issues or (old and not rebind))`.
- **Restore receipt** (`cloud_parked.py:463-465`):

```
        launch_id, _, ledger_reason = (
            _lane(repo_root, issues, env, None if rebind else old,
                  reserved_by=_park_time(parks[-1])) if (issues or (old and not rebind)) else (None, {}, None))
```

- **Raw green:** the shared green run below.

## H7. The `pr-links-unreadable` refusal in `cloud_cleanup._plan`

- **Guarded element:** `cloud_cleanup.py:293-294`, `if link_source == "unreadable": return _refusal("pr-links-unreadable"), None`.
- **Axis:** an unreadable link read refuses the plan (and so `record` and `branch`), so nothing is sent or deleted (P14).
- **Neutralization:** the two lines were removed, so an unreadable read fell through to `if not issues`.
- **Raw red** (`-k test_p14`):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_p14_a_cleanup_plan_with_unreadable_links_refuses_and_sends_and_deletes_nothing _
        cw.gh.closing[TCC.PR] = None  # GitHub's list cannot be read, though the description says "Closes #101"
>       assert CC.plan(cw.repo, REPO, TCC.PR, env=cw.env, run=cw.gh) == want
E       AssertionError: assert {'ok': False,...'pr-unlinked'} == {'ok': False,...s-unreadable'}
E         Differing items:
E         {'reason': 'pr-unlinked'} != {'reason': 'pr-links-unreadable'}
/home/user/superheroes/.claude/worktrees/issue-2658/plugins/superheroes/lib/tests/test_cloud_parked_links_2658.py:262: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_parked_links_2658.py::test_p14_a_cleanup_plan_with_unreadable_links_refuses_and_sends_and_deletes_nothing
1 failed, 14 deselected in 1.33s
```

- **Restore:** the inverse edit, the two lines put back.
- **Restore receipt** (`cloud_cleanup.py:292-295`):

```
    issues, link_source = cp._linked_issues(pull, repo, pr, env, run)
    if link_source == "unreadable":  # axis: an unreadable link read refuses, never reads as no link — see bite-proof record i2658_parked_links
        return _refusal("pr-links-unreadable"), None
    if not issues:
```

- **Raw green:** the shared green run below.

## H8. Cleanup reads a non-default-base PR outside a native stack as having no link (`require_stack`)

Added by the builder after review round 2 of PR 2664.

- **Guarded element:** `cloud_parked.py`, `_linked_issues`: `if snapshot is None and require_stack: return [], "github"`, which `cloud_cleanup._plan` reaches by passing `require_stack=True`.
- **Axis:** cleanup deletes branches and archives sessions, so it never takes an issue reference alone as a non-stack PR's lane. A park still binds such a PR through the timeline.
- **Neutralization:** `    if snapshot is None and require_stack:` became `    if snapshot is None and require_stack and False:`.
- **Raw red** (`-k test_p5_cleanup_refuses`, the builder's run on commit `6565498f`, failure lines verbatim):

```
F                                                                        [100%]
_________ test_p5_cleanup_refuses_a_non_default_base_pr_not_in_a_stack _________
>       assert CC.plan(cw.repo, REPO, TCC.PR, env=cw.env, run=cw.gh) == want
E       assert {'ok': True, ...er/name', ...} == {'ok': False,...'pr-unlinked'}
E         Differing items:
E         {'ok': True} != {'ok': False}
E         {'action': 'cleanup'}
E         {'archiveText': 'Pull request #412 is merged, so this build is finished. Follow the section "When the advisor asks you to archive your session" in your cloud build reference.'}
FAILED plugins/superheroes/lib/tests/test_cloud_parked_links_2658.py::test_p5_cleanup_refuses_a_non_default_base_pr_not_in_a_stack
1 failed, 16 deselected in 1.23s
```

- **Restore:** the inverse edit.
- **Restore receipt:** `git status --porcelain` printed nothing after both restores of that run (the tree matched commit `6565498f`).
- **Raw green** (with G12 in `i2658_review_record_links.md`, one run):

```
..                                                                       [100%]
2 passed, 73 deselected in 4.26s
```

## The shared green (after all seven restores)

```
...............                                                          [100%]
15 passed in 2.73s
```

Scoped wide run after the restores (`test_cloud_parked`, `test_cloud_parked_links_2658`, `test_cloud_cleanup`, the four cleanup
break-it and doctrine files, `test_review_record_links_2658`; `-n auto`):

```
336 passed in 21.14s
```

A post-restore `grep NEUTRALIZED` over `plugins/superheroes/lib/*.py` finds no marker left in a source file.

## Unproven

None of the seven declared elements is unproven. One bound: H2 neutralizes the repository leg at its call site in `cloud_parked.py`,
not inside `review_record.github_closing_issues` (outside this order's surface), so the leg inside that helper is proven by work
order A's tests, not by this record.
