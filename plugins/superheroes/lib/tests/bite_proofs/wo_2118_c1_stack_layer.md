# Bite-proof record — a stack-layer closing PR counts in the REST activity read (#2118, work order C1)

Detector file: `plugins/superheroes/lib/tests/test_wave_watch_cloud_rest.py`, unedited between each red and its green. Each entry is a targeted, reversible edit to one production file (`plugins/superheroes/lib/wave_watch.py`), applied and undone with the Edit tool (no `git checkout`, `restore`, `reset` or `stash`). Runs: `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-2118 -m pytest plugins/superheroes/lib/tests/test_wave_watch_cloud_rest.py -q` (whole file, no `-k`). The `UV_NATIVE_TLS` deprecation warning that `uv` prints first is the only line left out of each capture. The two guarded elements are the two the order declared; none is grouped. No secret, token or private URL appears in any capture; nothing is redacted.

Every restore receipt is the restored lines quoted back after the inverse Edit.

## 1. Stack layer counts

- **Axis:** stack-layer membership — a closing-keyword PR whose base is not the default branch is a closing node when the REST stack read says it is a native-stack layer.
- **Detector:** `test_a_stack_layer_closing_pr_counts_the_same_on_both_transports[rest]` (issue 2103, PR #2105, base `claude/workhorse-2102-f6neo7`, stack 2106 position 2 of 2).
- **Neutralization:** the default-branch-only filter put back ahead of the classification: two lines `if base_ref != default_branch:` / `continue` inserted directly above the line `if base_ref != default_branch:` that opens the classification.

**Raw red** (whole test file, exit 1). The malformed-stack cases also go red here, as they should: with the filter back, a malformed stack is skipped instead of making the read unavailable.

```
...............................FFFFF.......................              [100%]
=================================== FAILURES ===================================
____ test_a_stack_layer_closing_pr_counts_the_same_on_both_transports[rest] ____

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-21/test_a_stack_layer_closing_pr_1')
clock = <test_wave_watch_cloud_rest._Clock object at 0x7f9f0b657650>
transport = 'rest'

    @pytest.mark.parametrize("transport", ["graphql", "rest"])
    def test_a_stack_layer_closing_pr_counts_the_same_on_both_transports(tmp_path, clock, transport):
        assert not any("2103" in row["name"] for row in _branch_rows())
        pull = _json("pulls_2105.json")
        assert pull["base"]["ref"] != "main" and pull["stack"]["number"] == 2106
        graphql = (0, json.dumps(_graphql_2103()), "") if transport == "graphql" else _GRAPHQL_REFUSED
        gh = _gh_2103(graphql)
>       assert _fetch(gh, tmp_path, issues=(2103,), clock=clock) == {2103: _epoch(pull["updated_at"])}
E       assert {2103: 1792798487.0} == {2103: 1792798539.0}
E         
E         Differing items:
E         {2103: 1792798487.0} != {2103: 1792798539.0}
E         Use -v to get more diff

/home/user/wt-2118/plugins/superheroes/lib/tests/test_wave_watch_cloud_rest.py:477: AssertionError
_ test_a_stack_layer_whose_stack_is_malformed_makes_the_whole_read_unavailable[bad-number] _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-21/test_a_stack_layer_whose_stack0')
clock = <test_wave_watch_cloud_rest._Clock object at 0x7f9f0b654470>
stack = {'number': 'x'}

    @pytest.mark.parametrize("stack", [{"number": "x"}, "not-an-object", 7, []],
                             ids=["bad-number", "string", "integer", "list"])
    def test_a_stack_layer_whose_stack_is_malformed_makes_the_whole_read_unavailable(
        tmp_path, clock, stack,
    ):
        pull = _json("pulls_2105.json")
        pull["stack"] = stack
        gh = _gh_2103(_GRAPHQL_REFUSED, pull=pull)
>       assert _fetch(gh, tmp_path, issues=(2103,), clock=clock) == {2103: None}
E       assert {2103: 1792798487.0} == {2103: None}
E         
E         Differing items:
E         {2103: 1792798487.0} != {2103: None}
E         Use -v to get more diff

/home/user/wt-2118/plugins/superheroes/lib/tests/test_wave_watch_cloud_rest.py:491: AssertionError
_ test_a_stack_layer_whose_stack_is_malformed_makes_the_whole_read_unavailable[string] _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-21/test_a_stack_layer_whose_stack1')
clock = <test_wave_watch_cloud_rest._Clock object at 0x7f9f0b73fef0>
stack = 'not-an-object'

    @pytest.mark.parametrize("stack", [{"number": "x"}, "not-an-object", 7, []],
                             ids=["bad-number", "string", "integer", "list"])
    def test_a_stack_layer_whose_stack_is_malformed_makes_the_whole_read_unavailable(
        tmp_path, clock, stack,
    ):
        pull = _json("pulls_2105.json")
        pull["stack"] = stack
        gh = _gh_2103(_GRAPHQL_REFUSED, pull=pull)
>       assert _fetch(gh, tmp_path, issues=(2103,), clock=clock) == {2103: None}
E       assert {2103: 1792798487.0} == {2103: None}
E         
E         Differing items:
E         {2103: 1792798487.0} != {2103: None}
E         Use -v to get more diff

/home/user/wt-2118/plugins/superheroes/lib/tests/test_wave_watch_cloud_rest.py:491: AssertionError
_ test_a_stack_layer_whose_stack_is_malformed_makes_the_whole_read_unavailable[integer] _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-21/test_a_stack_layer_whose_stack2')
clock = <test_wave_watch_cloud_rest._Clock object at 0x7f9f0b6544d0>, stack = 7

    @pytest.mark.parametrize("stack", [{"number": "x"}, "not-an-object", 7, []],
                             ids=["bad-number", "string", "integer", "list"])
    def test_a_stack_layer_whose_stack_is_malformed_makes_the_whole_read_unavailable(
        tmp_path, clock, stack,
    ):
        pull = _json("pulls_2105.json")
        pull["stack"] = stack
        gh = _gh_2103(_GRAPHQL_REFUSED, pull=pull)
>       assert _fetch(gh, tmp_path, issues=(2103,), clock=clock) == {2103: None}
E       assert {2103: 1792798487.0} == {2103: None}
E         
E         Differing items:
E         {2103: 1792798487.0} != {2103: None}
E         Use -v to get more diff

/home/user/wt-2118/plugins/superheroes/lib/tests/test_wave_watch_cloud_rest.py:491: AssertionError
_ test_a_stack_layer_whose_stack_is_malformed_makes_the_whole_read_unavailable[list] _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-21/test_a_stack_layer_whose_stack3')
clock = <test_wave_watch_cloud_rest._Clock object at 0x7f9f0b6a2cf0>, stack = []

    @pytest.mark.parametrize("stack", [{"number": "x"}, "not-an-object", 7, []],
                             ids=["bad-number", "string", "integer", "list"])
    def test_a_stack_layer_whose_stack_is_malformed_makes_the_whole_read_unavailable(
        tmp_path, clock, stack,
    ):
        pull = _json("pulls_2105.json")
        pull["stack"] = stack
        gh = _gh_2103(_GRAPHQL_REFUSED, pull=pull)
>       assert _fetch(gh, tmp_path, issues=(2103,), clock=clock) == {2103: None}
E       assert {2103: 1792798487.0} == {2103: None}
E         
E         Differing items:
E         {2103: 1792798487.0} != {2103: None}
E         Use -v to get more diff

/home/user/wt-2118/plugins/superheroes/lib/tests/test_wave_watch_cloud_rest.py:491: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch_cloud_rest.py::test_a_stack_layer_closing_pr_counts_the_same_on_both_transports[rest]
FAILED plugins/superheroes/lib/tests/test_wave_watch_cloud_rest.py::test_a_stack_layer_whose_stack_is_malformed_makes_the_whole_read_unavailable[bad-number]
FAILED plugins/superheroes/lib/tests/test_wave_watch_cloud_rest.py::test_a_stack_layer_whose_stack_is_malformed_makes_the_whole_read_unavailable[string]
FAILED plugins/superheroes/lib/tests/test_wave_watch_cloud_rest.py::test_a_stack_layer_whose_stack_is_malformed_makes_the_whole_read_unavailable[integer]
FAILED plugins/superheroes/lib/tests/test_wave_watch_cloud_rest.py::test_a_stack_layer_whose_stack_is_malformed_makes_the_whole_read_unavailable[list]
5 failed, 54 passed in 0.65s
```

The red is on the axis: the REST half returns the issue's own age (`1792798487.0`, the issue's `updated_at`) instead of the stack-layer PR's (`1792798539.0`), the older age the defect describes.

- **Restore:** inverse Edit (the two inserted lines removed).
- **Restore receipt:** the restored lines, as read back from the file:

```
                if base_ref != default_branch:
                    snapshot, refusal = sc._parse_rest_pull(pull, slug, pr_number, 0)
```

**Raw green** (whole test file, exit 0):

```
...........................................................              [100%]
59 passed in 0.54s
```

## 2. Unreadable stack fails closed

- **Axis:** a stack read that cannot say — any refusal other than `not-linked` makes the whole activity read `None`, never an older or newer age.
- **Detector:** `test_a_stack_layer_whose_stack_is_malformed_makes_the_whole_read_unavailable` (`stack` = `{"number": "x"}`, `"not-an-object"`, `7`, `[]`).
- **Neutralization:** in the classification, the line `return None` that follows the `not-linked` `continue` became `continue`.

**Raw red** (whole test file, exit 1):

```
................................FFFF.......................              [100%]
=================================== FAILURES ===================================
_ test_a_stack_layer_whose_stack_is_malformed_makes_the_whole_read_unavailable[bad-number] _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-23/test_a_stack_layer_whose_stack0')
clock = <test_wave_watch_cloud_rest._Clock object at 0x7f0246488980>
stack = {'number': 'x'}

    @pytest.mark.parametrize("stack", [{"number": "x"}, "not-an-object", 7, []],
                             ids=["bad-number", "string", "integer", "list"])
    def test_a_stack_layer_whose_stack_is_malformed_makes_the_whole_read_unavailable(
        tmp_path, clock, stack,
    ):
        pull = _json("pulls_2105.json")
        pull["stack"] = stack
        gh = _gh_2103(_GRAPHQL_REFUSED, pull=pull)
>       assert _fetch(gh, tmp_path, issues=(2103,), clock=clock) == {2103: None}
E       assert {2103: 1792798487.0} == {2103: None}
E         
E         Differing items:
E         {2103: 1792798487.0} != {2103: None}
E         Use -v to get more diff

/home/user/wt-2118/plugins/superheroes/lib/tests/test_wave_watch_cloud_rest.py:491: AssertionError
_ test_a_stack_layer_whose_stack_is_malformed_makes_the_whole_read_unavailable[string] _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-23/test_a_stack_layer_whose_stack1')
clock = <test_wave_watch_cloud_rest._Clock object at 0x7f0246489a90>
stack = 'not-an-object'

    @pytest.mark.parametrize("stack", [{"number": "x"}, "not-an-object", 7, []],
                             ids=["bad-number", "string", "integer", "list"])
    def test_a_stack_layer_whose_stack_is_malformed_makes_the_whole_read_unavailable(
        tmp_path, clock, stack,
    ):
        pull = _json("pulls_2105.json")
        pull["stack"] = stack
        gh = _gh_2103(_GRAPHQL_REFUSED, pull=pull)
>       assert _fetch(gh, tmp_path, issues=(2103,), clock=clock) == {2103: None}
E       assert {2103: 1792798487.0} == {2103: None}
E         
E         Differing items:
E         {2103: 1792798487.0} != {2103: None}
E         Use -v to get more diff

/home/user/wt-2118/plugins/superheroes/lib/tests/test_wave_watch_cloud_rest.py:491: AssertionError
_ test_a_stack_layer_whose_stack_is_malformed_makes_the_whole_read_unavailable[integer] _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-23/test_a_stack_layer_whose_stack2')
clock = <test_wave_watch_cloud_rest._Clock object at 0x7f0246489d90>, stack = 7

    @pytest.mark.parametrize("stack", [{"number": "x"}, "not-an-object", 7, []],
                             ids=["bad-number", "string", "integer", "list"])
    def test_a_stack_layer_whose_stack_is_malformed_makes_the_whole_read_unavailable(
        tmp_path, clock, stack,
    ):
        pull = _json("pulls_2105.json")
        pull["stack"] = stack
        gh = _gh_2103(_GRAPHQL_REFUSED, pull=pull)
>       assert _fetch(gh, tmp_path, issues=(2103,), clock=clock) == {2103: None}
E       assert {2103: 1792798487.0} == {2103: None}
E         
E         Differing items:
E         {2103: 1792798487.0} != {2103: None}
E         Use -v to get more diff

/home/user/wt-2118/plugins/superheroes/lib/tests/test_wave_watch_cloud_rest.py:491: AssertionError
_ test_a_stack_layer_whose_stack_is_malformed_makes_the_whole_read_unavailable[list] _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-23/test_a_stack_layer_whose_stack3')
clock = <test_wave_watch_cloud_rest._Clock object at 0x7f02462e4650>, stack = []

    @pytest.mark.parametrize("stack", [{"number": "x"}, "not-an-object", 7, []],
                             ids=["bad-number", "string", "integer", "list"])
    def test_a_stack_layer_whose_stack_is_malformed_makes_the_whole_read_unavailable(
        tmp_path, clock, stack,
    ):
        pull = _json("pulls_2105.json")
        pull["stack"] = stack
        gh = _gh_2103(_GRAPHQL_REFUSED, pull=pull)
>       assert _fetch(gh, tmp_path, issues=(2103,), clock=clock) == {2103: None}
E       assert {2103: 1792798487.0} == {2103: None}
E         
E         Differing items:
E         {2103: 1792798487.0} != {2103: None}
E         Use -v to get more diff

/home/user/wt-2118/plugins/superheroes/lib/tests/test_wave_watch_cloud_rest.py:491: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch_cloud_rest.py::test_a_stack_layer_whose_stack_is_malformed_makes_the_whole_read_unavailable[bad-number]
FAILED plugins/superheroes/lib/tests/test_wave_watch_cloud_rest.py::test_a_stack_layer_whose_stack_is_malformed_makes_the_whole_read_unavailable[string]
FAILED plugins/superheroes/lib/tests/test_wave_watch_cloud_rest.py::test_a_stack_layer_whose_stack_is_malformed_makes_the_whole_read_unavailable[integer]
FAILED plugins/superheroes/lib/tests/test_wave_watch_cloud_rest.py::test_a_stack_layer_whose_stack_is_malformed_makes_the_whole_read_unavailable[list]
4 failed, 55 passed in 0.69s
```

The red is on the axis: the read returns an age (`1792798487.0`) where the invariant requires `None`. The stacked-equivalence test stays green here, as it should (its stack is well formed).

- **Restore:** inverse Edit (`continue` back to `return None`).
- **Restore receipt:** the restored lines, as read back from the file:

```
                        if refusal["reason"] == sc.REASON_NOT_LINKED:
                            continue
                        return None
```

**Raw green** (whole test file, exit 0):

```
...........................................................              [100%]
59 passed in 0.64s
```
