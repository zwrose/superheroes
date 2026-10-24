# Bite-proof record — the open-PR list seam and the launcher's base-layer lookup through REST (#2118, work order A)

Detector file: `plugins/superheroes/lib/tests/test_open_prs_rest.py`, unedited between each red and its green. Every entry is a targeted, reversible edit to one production file (`plugins/superheroes/lib/stack_check.py`), applied and undone with the Edit tool (no `git checkout`, `restore`, `reset` or `stash`). Runs: `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-2118 -m pytest '<exact node id>' -q -n 0`, output captured whole after `echo "exit=$?"`; the `UV_NATIVE_TLS` deprecation warning that `uv` prints first is the only line left out of each capture. The three guarded elements are the three the order declared; none is grouped. The "Full output truncated (12 lines hidden)" line inside red 1 is pytest's own, not an edit of this record.

## 1. The launcher's REST fallback in `list_open_prs` (`lib/stack_check.py`)

- **Axis:** fallback presence — only the proxy's GraphQL refusal re-reads the list through REST.
- **Detector:** `test_open_prs_rest.py::test_the_launcher_resolves_the_same_entry_pr_on_both_transports` (the equivalence test, REST path).
- **Neutralization:** in `list_open_prs`, directly above `pulls, refusal = read_rest_list(`, inserted `return None, _read_refusal(REASON_STACK_UNREADABLE, "gh pr list failed: " + _proc_output(proc))`, so the proxy refusal comes back as the GraphQL refusal and REST is never called.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_______ test_the_launcher_resolves_the_same_entry_pr_on_both_transports ________

    def test_the_launcher_resolves_the_same_entry_pr_on_both_transports():
        base = _PULLS_PAGE1[1]["head"]["sha"]
        graphql = _lookup(FakeGh(_PULLS_PAGE1, list_mode="ok"), base)
        rest_gh = FakeGh(_PULLS_PAGE1, list_mode="refused")
        rest = _lookup(rest_gh, base)
>       assert graphql == rest == {"ok": True, "pr": 2111, "repo": "zwrose/superheroes"}
E       AssertionError: assert {'ok': True, .../superheroes'} == {'ok': False,...com/graphql)'}
E         
E         Differing items:
E         {'ok': True} != {'ok': False}
E         Left contains 2 more items:
E         {'pr': 2111, 'repo': 'zwrose/superheroes'}
E         Right contains 2 more items:
E         {'detail': 'gh pr list failed: HTTP 403: GitHub GraphQL is not available from '...
E         
E         ...Full output truncated (12 lines hidden), use '-vv' to show

/home/user/wt-2118/plugins/superheroes/lib/tests/test_open_prs_rest.py:144: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_open_prs_rest.py::test_the_launcher_resolves_the_same_entry_pr_on_both_transports
1 failed in 0.65s
exit=1
```

- **Restore:** inverse edit (the inserted `return None, _read_refusal(...)` line removed).
- **Restore receipt** (the restored lines, read back by `grep -n -B1 -A3 "pulls, refusal = read_rest_list"`):

```
1071-    # The cloud proxy refused GraphQL: re-read the same list through REST; gh fills {owner}/{repo} from the cwd.
1072:    pulls, refusal = read_rest_list(
1073-        _OPEN_PRS_REST_PATH, run=run, timeout=timeout, deadline_at=deadline_at, run_kwargs=kwargs,
1074-        limit=OPEN_PRS_LIMIT)
1075-    if refusal is not None:
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 0.69s
exit=0
```

## 2. A REST failure stays a refusal in `list_open_prs` (`lib/stack_check.py`)

- **Axis:** no rows from a failed read — a REST refusal after the GraphQL refusal returns a refusal, never rows.
- **Detectors:** `test_e4_a_rest_page_that_exits_non_zero_after_the_refusal_is_a_prefixed_refusal` and `test_e9_a_rest_refusal_after_the_graphql_refusal_is_stack_read_unavailable_not_base_not_layer_head`, run together as two node ids.
- **Neutralization:** in `list_open_prs`, directly after `limit=OPEN_PRS_LIMIT)` / `if refusal is not None:`, `return None, _graphql_refused_rest_refusal(refusal)` became `return [], None`.

**Raw red** (exit 1):

```
FF                                                                       [100%]
=================================== FAILURES ===================================
_ test_e4_a_rest_page_that_exits_non_zero_after_the_refusal_is_a_prefixed_refusal _

    def test_e4_a_rest_page_that_exits_non_zero_after_the_refusal_is_a_prefixed_refusal():
        gh = FakeGh(_PULLS_PAGE1, fail_pages=(1,))
        rows, refusal = _list(gh)
>       assert rows is None
E       assert [] is None

/home/user/wt-2118/plugins/superheroes/lib/tests/test_open_prs_rest.py:224: AssertionError
_ test_e9_a_rest_refusal_after_the_graphql_refusal_is_stack_read_unavailable_not_base_not_layer_head _

    def test_e9_a_rest_refusal_after_the_graphql_refusal_is_stack_read_unavailable_not_base_not_layer_head():
        base = _PULLS_PAGE1[0]["head"]["sha"]
        result = _lookup(FakeGh(_PULLS_PAGE1, fail_pages=(1,)), base)
>       assert result["ok"] is False and result["reason"] == "stack-read-unavailable"
E       AssertionError: assert (False is False and 'base-not-layer-head' == 'stack-read-unavailable'
E         
E         - stack-read-unavailable
E         + base-not-layer-head)

/home/user/wt-2118/plugins/superheroes/lib/tests/test_open_prs_rest.py:373: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_open_prs_rest.py::test_e4_a_rest_page_that_exits_non_zero_after_the_refusal_is_a_prefixed_refusal
FAILED plugins/superheroes/lib/tests/test_open_prs_rest.py::test_e9_a_rest_refusal_after_the_graphql_refusal_is_stack_read_unavailable_not_base_not_layer_head
2 failed in 8.28s
exit=1
```

- **Restore:** inverse edit (`return [], None` back to `return None, _graphql_refused_rest_refusal(refusal)`).
- **Restore receipt** (read back by `grep -n -A3 "limit=OPEN_PRS_LIMIT)"`):

```
1074:        limit=OPEN_PRS_LIMIT)
1075-    if refusal is not None:
1076-        return None, _graphql_refused_rest_refusal(refusal)
1077-    rows = []
```

**Raw green** (exit 0):

```
..                                                                       [100%]
2 passed in 0.64s
exit=0
```

## 3. The 1000-row limit on the REST read in `list_open_prs` (`lib/stack_check.py`)

- **Axis:** limit parity — the REST read returns exactly the first `OPEN_PRS_LIMIT` rows, as `gh pr list --limit 1000` does.
- **Detector:** `test_e8_1001_open_prs_read_exactly_the_first_1000_and_never_ask_for_page_11`.
- **Neutralization:** in `list_open_prs`, the `read_rest_list(` call lost its `limit=OPEN_PRS_LIMIT` argument (`run_kwargs=kwargs,` / `limit=OPEN_PRS_LIMIT)` became `run_kwargs=kwargs)`).

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_e8_1001_open_prs_read_exactly_the_first_1000_and_never_ask_for_page_11 __

    def test_e8_1001_open_prs_read_exactly_the_first_1000_and_never_ask_for_page_11():
        pulls = _many(1001)
        gh = FakeGh(pulls)
        rows, refusal = _list(gh)
        assert refusal is None
>       assert rows == _graphql_rows(pulls[:1000])
E       AssertionError: assert [{'number': 1... 'OPEN'}, ...] == [{'number': 1... 'OPEN'}, ...]
E         
E         Left contains one more item: {'number': 9000, 'headRefOid': '0000000000000000000000000000000000002328', 'state': 'OPEN'}
E         Use -v to get more diff

/home/user/wt-2118/plugins/superheroes/lib/tests/test_open_prs_rest.py:343: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_open_prs_rest.py::test_e8_1001_open_prs_read_exactly_the_first_1000_and_never_ask_for_page_11
1 failed in 0.66s
exit=1
```

- **Restore:** inverse edit (`limit=OPEN_PRS_LIMIT)` put back on its own continuation line).
- **Restore receipt** (read back by `grep -n -B2 -A2 "limit=OPEN_PRS_LIMIT)"`):

```
1072-    pulls, refusal = read_rest_list(
1073-        _OPEN_PRS_REST_PATH, run=run, timeout=timeout, deadline_at=deadline_at, run_kwargs=kwargs,
1074:        limit=OPEN_PRS_LIMIT)
1075-    if refusal is not None:
1076-        return None, _graphql_refused_rest_refusal(refusal)
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 0.66s
exit=0
```

## Not proven

The order declared three guarded elements. These other guards carry an `# axis:` line and are exercised by tests in the same file, but no neutralization was run for them: the `limit` stop in `gh_pages.read` (E10 tests), the `deadline is None` budget message in `_transport_rest` (E7), the `expect_list` check, the non-proxy GraphQL failure branch (E2), the REST row mapping refusals (E6) and `read_rest_list`'s first-failing-page detail.
