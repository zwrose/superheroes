# Bite-proof record — the wave watch's PR-list and cloud-activity reads through REST (#2118, work order B)

Detector file: `plugins/superheroes/lib/tests/test_wave_watch_cloud_rest.py`, unedited between each red and its green. Every entry is a targeted, reversible edit to one production file (`plugins/superheroes/lib/wave_watch.py`), applied and undone with the Edit tool (no `git checkout`, `restore`, `reset` or `stash`). Runs: `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-2118 -m pytest plugins/superheroes/lib/tests/test_wave_watch_cloud_rest.py -q`, with `-k <name>` on the red and green of entries 3, 4 and 5 (the order allowed `-k`; the `-k` selection was seen to select tests in each red, so none is a vacuous empty selection). The `UV_NATIVE_TLS` deprecation warning that `uv` prints first is the only line left out of each capture. The five guarded elements are the five the order declared; none is grouped. No secret, token or private URL appears in any capture; the only redaction is none.

Every restore receipt is a post-restore `git status --porcelain plugins/superheroes/lib/wave_watch.py` that printed nothing (the file is clean against HEAD), plus the restored lines quoted back.

## 1. The PR-list REST fallback (`_poll_open_pr_numbers`)

- **Axis:** fallback presence — a refused `gh pr list` is re-read through REST.
- **Detectors:** `test_w2_refused_pr_list_reads_the_numbers_through_rest` and `test_a_pr_list_equivalence_same_numbers_on_both_transports[rest]`.
- **Neutralization:** in the `sc.list_open_prs(("number",), …)` call, `run=gh_run,` became `run=lambda argv, **kw: gh_run(argv, **kw) if argv[:3] == ["gh", "pr", "list"] else (_ for _ in ()).throw(OSError("no rest")),`, so every REST call raises and the list can only come from GraphQL.

**Raw red** (whole test file, exit 1):

```
..F.......F..................................                            [100%]
=================================== FAILURES ===================================
____________ test_w2_refused_pr_list_reads_the_numbers_through_rest ____________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-10/test_w2_refused_pr_list_reads_0')
clock = <test_wave_watch_cloud_rest._Clock object at 0x7f1955fa85c0>

    def test_w2_refused_pr_list_reads_the_numbers_through_rest(tmp_path, clock):
        gh = _Gh({
            "pr-list": _PR_LIST_REFUSED,
            _PR_LIST_REST: (0, _text(_CLOUD / "pulls_open_page1.json"), ""),
        })
        result, degraded, sampled = _poll(gh, tmp_path, clock)
>       assert result == (sorted(_PR_NUMBERS), True)
E       assert (None, False) == ([2029, 2111, 2113], True)
E         
E         At index 0 diff: None != [2029, 2111, 2113]
E         Use -v to get more diff

/home/user/wt-2118/plugins/superheroes/lib/tests/test_wave_watch_cloud_rest.py:263: AssertionError
_______ test_a_pr_list_equivalence_same_numbers_on_both_transports[rest] _______

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-10/test_a_pr_list_equivalence_sam1')
clock = <test_wave_watch_cloud_rest._Clock object at 0x7f1955fab0e0>
transport = 'rest'

    @pytest.mark.parametrize("transport", ["graphql", "rest"])
    def test_a_pr_list_equivalence_same_numbers_on_both_transports(tmp_path, clock, transport):
        if transport == "graphql":
            gh = _Gh({"pr-list": (0, json.dumps([{"number": n} for n in _PR_NUMBERS]), "")})
        else:
            gh = _Gh({
                "pr-list": _PR_LIST_REFUSED,
                _PR_LIST_REST: (0, _text(_CLOUD / "pulls_open_page1.json"), ""),
            })
        result, degraded, _sampled = _poll(gh, tmp_path, clock)
>       assert result == (sorted(_PR_NUMBERS), True)
E       assert (None, False) == ([2029, 2111, 2113], True)
E         
E         At index 0 diff: None != [2029, 2111, 2113]
E         Use -v to get more diff

/home/user/wt-2118/plugins/superheroes/lib/tests/test_wave_watch_cloud_rest.py:312: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch_cloud_rest.py::test_w2_refused_pr_list_reads_the_numbers_through_rest
FAILED plugins/superheroes/lib/tests/test_wave_watch_cloud_rest.py::test_a_pr_list_equivalence_same_numbers_on_both_transports[rest]
2 failed, 43 passed in 0.70s
```

- **Restore:** inverse edit (the `run=lambda …` line put back as `run=gh_run,`).
- **Restore receipt:** `git status --porcelain plugins/superheroes/lib/wave_watch.py` printed nothing. Restored lines (as written back by the inverse edit):

```
            ("number",),
            run=gh_run,
            timeout=timeout,
```

**Raw green** (whole test file, exit 0):

```
.............................................                            [100%]
45 passed in 0.80s
```

## 2. The cloud-activity REST fallback (`_fetch_cloud_activity`)

- **Axis:** fallback presence — a GraphQL proxy refusal re-reads the activity through REST.
- **Detectors:** the activity tests in the file that need the REST read to answer (12 went red; see below).
- **Neutralization:** in the proxy-refusal branch of `_fetch_cloud_activity`, a `return unreadable` line inserted directly above `repository = _cloud_activity_repository_rest(`, so `_cloud_activity_repository_rest` is never called.

**Raw red** (whole test file, exit 1). **This capture is incomplete:** the tool that ran the command cut 3845 characters out of the middle of its output (the cut is marked by the tool as `... [3845 characters truncated] ...`, and it falls inside the failure of `test_w8_a_keyword_pr_to_another_branch_is_not_a_closing_node`). What is quoted is exactly the output received: the progress line, the failures before the cut for the first four tests, and the summary. The failures after the cut are not reconstructed; their names are in the short test summary.

```
............FFF..F...........FF.F.F.FFFF.....                            [100%]
=================================== FAILURES ===================================
_______ test_b_activity_equivalence_same_epoch_on_both_transports[rest] ________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-12/test_b_activity_equivalence_sa1')
clock = <test_wave_watch_cloud_rest._Clock object at 0x7f302215b950>
transport = 'rest'

    @pytest.mark.parametrize("transport", ["graphql", "rest"])
    def test_b_activity_equivalence_same_epoch_on_both_transports(tmp_path, clock, transport):
        graphql = _graphql_ok() if transport == "graphql" else _GRAPHQL_REFUSED
        gh = _activity_gh(graphql)
>       assert _fetch(gh, tmp_path, clock=clock) == {2110: _epoch(_ISSUE_AT)}
E       assert {2110: None} == {2110: 1792811789.0}
E         
E         Differing items:
E         {2110: None} != {2110: 1792811789.0}
E         Use -v to get more diff

/home/user/wt-2118/plugins/superheroes/lib/tests/test_wave_watch_cloud_rest.py:323: AssertionError
_____ test_b_activity_evaluation_reports_the_same_on_both_transports[6300] _____
(…assertion: ([{'launchId': '2110', … 'activityAgeSeconds': 6300.0, …}], set()) == ([], {'cloud-activity-unavailable'}) — the output of the failure body is cut in this record to its assertion line; the tool delivered it whole)
_____________ test_two_issues_read_when_every_get_answers ______________________
(…assertion: {2110: None, 2111: None} == {2110: 1792811789.0, 2111: 1792454400.0})
... [3845 characters truncated by the tool that ran the command] ...
______ test_w13_the_budget_spent_mid_rest_is_unreadable_and_never_raises _______

        assert _fetch(gh, tmp_path, clock=clock) == {2110: None}
>       assert len(gh.rest_calls()) == 1
E       assert 0 == 1
E        +  where 0 = len([])

/home/user/wt-2118/plugins/superheroes/lib/tests/test_wave_watch_cloud_rest.py:511: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch_cloud_rest.py::test_b_activity_equivalence_same_epoch_on_both_transports[rest]
FAILED plugins/superheroes/lib/tests/test_wave_watch_cloud_rest.py::test_b_activity_evaluation_reports_the_same_on_both_transports[6300]
FAILED plugins/superheroes/lib/tests/test_wave_watch_cloud_rest.py::test_b_activity_evaluation_reports_the_same_on_both_transports[60]
FAILED plugins/superheroes/lib/tests/test_wave_watch_cloud_rest.py::test_two_issues_read_when_every_get_answers
FAILED plugins/superheroes/lib/tests/test_wave_watch_cloud_rest.py::test_w8_a_keyword_pr_to_another_branch_is_not_a_closing_node
FAILED plugins/superheroes/lib/tests/test_wave_watch_cloud_rest.py::test_w8_control_the_same_pr_to_the_default_branch_counts
FAILED plugins/superheroes/lib/tests/test_wave_watch_cloud_rest.py::test_w9_more_than_ten_keyword_prs_on_the_default_branch_is_unreadable[10-True]
FAILED plugins/superheroes/lib/tests/test_wave_watch_cloud_rest.py::test_w10_more_than_fifty_substring_branches_is_unreadable[49-True]
FAILED plugins/superheroes/lib/tests/test_wave_watch_cloud_rest.py::test_w11_control_a_bare_number_in_another_repositorys_pr_names_that_repositorys_issue
FAILED plugins/superheroes/lib/tests/test_wave_watch_cloud_rest.py::test_a_qualified_keyword_for_another_issue_is_not_a_closing_node
FAILED plugins/superheroes/lib/tests/test_wave_watch_cloud_rest.py::test_w12_a_branch_carrying_a_longer_number_contributes_nothing
FAILED plugins/superheroes/lib/tests/test_wave_watch_cloud_rest.py::test_w13_the_budget_spent_mid_rest_is_unreadable_and_never_raises
12 failed, 33 passed in 7.27s
```

(The bracketed "(…assertion …)" lines above are this record's own marks standing in for failure bodies that were received whole but are not copied here to keep the record short; the progress line, the `test_b_…[rest]` body, the `test_w13` tail and the summary are verbatim.)

- **Restore:** inverse edit (the inserted `return unreadable` line removed).
- **Restore receipt:** `git status --porcelain plugins/superheroes/lib/wave_watch.py` printed nothing. Restored lines:

```
                return unreadable
            repository = _cloud_activity_repository_rest(
```

**Raw green** (whole test file, exit 0):

```
.............................................                            [100%]
45 passed in 0.73s
```

## 3. A REST failure stays unavailable (`get_list` in `_cloud_activity_repository_rest`)

- **Axis:** nothing from a failed read — a failed page makes the whole read None, never a partial answer.
- **Detector:** `test_w5_any_one_rest_get_failing_makes_every_issue_unreadable` (the three list-read cases).
- **Neutralization:** in `get_list`, `raise _RestUnreadable(path)` under `if refusal is not None:` became `return []`.

**Raw red** (`-k test_w5`, exit 1; the three failure bodies are identical in shape, shown here for the first and the summary — the other two bodies are the same assertion with `failing` = `branches-page-2` and `second-issue-timeline`):

```
..FF..F                                                                  [100%]
=================================== FAILURES ===================================
___ test_w5_any_one_rest_get_failing_makes_every_issue_unreadable[timeline] ____

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-14/test_w5_any_one_rest_get_faili2')
clock = <test_wave_watch_cloud_rest._Clock object at 0x7ff64df5aab0>
failing = 'timeline'

    @pytest.mark.parametrize("failing", [name for name in _TWO if name != "baseline"])
    def test_w5_any_one_rest_get_failing_makes_every_issue_unreadable(tmp_path, clock, failing):
        gh = _activity_gh(_GRAPHQL_REFUSED, extra_issues=(2111,))
        gh.routes[_TWO[failing]] = _BOOM
>       assert _fetch(gh, tmp_path, issues=(2110, 2111), clock=clock) == {2110: None, 2111: None}
E       assert {2110: 179281... 1792454400.0} == {2110: None, 2111: None}
E         
E         Differing items:
E         {2110: 1792811789.0} != {2110: None}
E         {2111: 1792454400.0} != {2111: None}
E         Use -v to get more diff

/home/user/wt-2118/plugins/superheroes/lib/tests/test_wave_watch_cloud_rest.py:400: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch_cloud_rest.py::test_w5_any_one_rest_get_failing_makes_every_issue_unreadable[timeline]
FAILED plugins/superheroes/lib/tests/test_wave_watch_cloud_rest.py::test_w5_any_one_rest_get_failing_makes_every_issue_unreadable[branches-page-2]
FAILED plugins/superheroes/lib/tests/test_wave_watch_cloud_rest.py::test_w5_any_one_rest_get_failing_makes_every_issue_unreadable[second-issue-timeline]
3 failed, 4 passed, 38 deselected in 0.48s
```

- **Restore:** inverse edit (`return []` back to `raise _RestUnreadable(path)`).
- **Restore receipt:** `git status --porcelain plugins/superheroes/lib/wave_watch.py` printed nothing. Restored lines:

```
        if refusal is not None:
            raise _RestUnreadable(path)
        return rows
```

**Raw green** (`-k test_w5`, exit 0):

```
.......                                                                  [100%]
7 passed, 38 deselected in 0.44s
```

## 4. Manual-link fail-closed (`_closing_pr_numbers_rest`)

- **Axis:** completeness REST cannot establish — a manual `connected`/`disconnected` link names no PR in the REST timeline, so the closing set cannot be established.
- **Detector:** `test_w7_a_manual_link_event_is_unreadable` (both events).
- **Neutralization:** `if any(isinstance(row, dict) and row.get("event") in _MANUAL_LINK_EVENTS for row in timeline):` became `if False and any(…same…):`.

**Raw red** (`-k test_w7`, exit 1; the two bodies differ only in `event`, shown for `connected`):

```
FF                                                                       [100%]
=================================== FAILURES ===================================
_____________ test_w7_a_manual_link_event_is_unreadable[connected] _____________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-16/test_w7_a_manual_link_event_is0')
clock = <test_wave_watch_cloud_rest._Clock object at 0x7f08c2bb2150>
event = 'connected'

    @pytest.mark.parametrize("event", ["connected", "disconnected"])
    def test_w7_a_manual_link_event_is_unreadable(tmp_path, clock, event):
        timeline = _json("issues_2110_timeline_page1.json") + [{"event": event}]
        gh = _activity_gh(_GRAPHQL_REFUSED, timeline=timeline)
>       assert _fetch(gh, tmp_path, clock=clock) == {2110: None}
E       assert {2110: 1792811789.0} == {2110: None}
E         
E         Differing items:
E         {2110: 1792811789.0} != {2110: None}
E         Use -v to get more diff

/home/user/wt-2118/plugins/superheroes/lib/tests/test_wave_watch_cloud_rest.py:419: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch_cloud_rest.py::test_w7_a_manual_link_event_is_unreadable[connected]
FAILED plugins/superheroes/lib/tests/test_wave_watch_cloud_rest.py::test_w7_a_manual_link_event_is_unreadable[disconnected]
2 failed, 43 deselected in 0.42s
```

- **Restore:** inverse edit (`if False and any(` back to `if any(`).
- **Restore receipt:** `git status --porcelain plugins/superheroes/lib/wave_watch.py` printed nothing. Restored line:

```
    if any(isinstance(row, dict) and row.get("event") in _MANUAL_LINK_EVENTS for row in timeline):
```

**Raw green** (`-k test_w7`, exit 0):

```
..                                                                       [100%]
2 passed, 43 deselected in 0.32s
```

## 5. Default-branch filter (`_cloud_activity_repository_rest`)

- **Axis:** closing-link eligibility — GitHub ignores a closing keyword on a pull request whose base is not the default branch.
- **Detector:** `test_w8_a_keyword_pr_to_another_branch_is_not_a_closing_node` (its control `test_w8_control_the_same_pr_to_the_default_branch_counts` stays green, as it should).
- **Neutralization:** the two lines `if base_ref != default_branch:` / `continue` were deleted.

**Raw red** (`-k test_w8`, exit 1):

```
F.                                                                       [100%]
=================================== FAILURES ===================================
_________ test_w8_a_keyword_pr_to_another_branch_is_not_a_closing_node _________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-18/test_w8_a_keyword_pr_to_anothe0')
clock = <test_wave_watch_cloud_rest._Clock object at 0x7f5e6615a150>

    def test_w8_a_keyword_pr_to_another_branch_is_not_a_closing_node(tmp_path, clock):
        other = _pull(2113, base="dev", updated=_FRESH_AT)
        gh = _activity_gh(_GRAPHQL_REFUSED, pulls={2113: other})
>       assert _fetch(gh, tmp_path, clock=clock) == {2110: _epoch(_ISSUE_AT)}
E       assert {2110: 1792886400.0} == {2110: 1792811789.0}
E         
E         Differing items:
E         {2110: 1792886400.0} != {2110: 1792811789.0}
E         Use -v to get more diff

/home/user/wt-2118/plugins/superheroes/lib/tests/test_wave_watch_cloud_rest.py:425: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch_cloud_rest.py::test_w8_a_keyword_pr_to_another_branch_is_not_a_closing_node
1 failed, 1 passed, 43 deselected in 0.37s
```

- **Restore:** inverse edit (the two lines put back below the axis comment).
- **Restore receipt:** `git status --porcelain plugins/superheroes/lib/wave_watch.py` printed nothing. Restored lines:

```
                # axis: GitHub ignores a closing keyword on a pull request to another branch
                if base_ref != default_branch:
                    continue
```

**Raw green** (`-k test_w8`, exit 0):

```
..                                                                       [100%]
2 passed, 43 deselected in 0.31s
```

## Not proven

The order declared five guarded elements. These other guards in `wave_watch.py` carry an `# axis:` line and are exercised by tests in the same file, but no neutralization was run for them: the proxy-refusal-only test in `_fetch_cloud_activity` (W4), the pull-request-shaped issue check, the cross-repository closing-link check (W11), the 10-PR and 50-branch limits (W9, W10), the single-GET failure path in `get`, and the `list_open_prs` REST-only-on-refusal path inside `lib/stack_check.py` (proven in `wo_2118_a_open_prs.md`).
