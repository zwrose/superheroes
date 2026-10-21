# Bite-proof record: a cloud launch grants `add_repo` through its `--settings` if and only if the premise carries extra repositories

Detectors: `plugins/superheroes/lib/tests/test_launcher_cloud.py` (`T1`) and `plugins/superheroes/lib/tests/test_issue_contract.py` (`T2`).
Guarded elements (declared by the order): (G1) the `permissions` insertion in `engine_adapter.claude_cloud_builder_argv`;
(G2) the no-grant path of that function staying exact; (G3) `launcher.compose_launch` passing the grant when the premise carries
`extraRepositories`; (G4) `compose_launch` passing none without it; (G5) `launcher.validate_premise`'s not-a-non-empty-list predicate;
(G6) its name-shape predicate; (G7) its case-insensitive distinctness predicate; (G8) `launcher._place_refusal`'s not-cloud refusal;
(G9) `issue_contract.extra_repositories`'s live-line gating by fence kind; (G10) its indent gate; (G11) its line-repeated refusal;
(G12) its empty refusal; (G13) its name-invalid refusal; (G14) its name-repeated refusal.
Each was neutralized by a targeted edit in the production file, the detector run alone as one test node (a parametrized function is
run whole, and G8 once per parametrized node), then restored by the inverse edit. No test file was edited during the proofs. After all
fourteen restores, `git diff 10fef46a` over `engine_adapter.py`, `launcher.py` and `issue_contract.py` is empty.

Every command was run from the worktree root as `timeout 300 scripts/pinned-python -B -m pytest <file>::<test> -q -p no:cacheprovider`.
The `UV_NATIVE_TLS` deprecation warning that heads every run is omitted below.

Pinned condition: none beyond the sandbox. What the sandbox makes unobservable: the two G8 red runs took about 21 seconds each and the
harness reported ten denied outbound connections to `api.anthropic.com:443` for each, because with the refusal removed the launch went on
past the place gate; the denial changed nothing the test reads, which fails on `result["ok"]` before any later step matters.

Reading the red captures: where a function is parametrized and every node fails the same way, the capture below keeps the first
node's traceback and the full `short test summary info` block, and says so. The omitted tracebacks differ only in the parameter.

## 1. G1: the `permissions` insertion

Axis: a non-empty `allow_tools` puts a `permissions.allow` list after `remote` in the `--settings` JSON.

- Neutralization (`engine_adapter.py:824`, `claude_cloud_builder_argv`): `if allow_tools:` became `if False and allow_tools:`.
- Node: `T1::test_cloud_argv_grants_the_attach_tool_through_its_settings`.
- Red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
_________ test_cloud_argv_grants_the_attach_tool_through_its_settings __________

    def test_cloud_argv_grants_the_attach_tool_through_its_settings():
        # axis: a non-empty allow_tools puts a permissions.allow list after `remote` in the --settings JSON — see bite-proof record wo_a_1948_add_repo_grant
        built = EA.claude_cloud_builder_argv(
            "opus", "medium", "the prompt", ENV_ID, "issue-1-ab", allow_tools=(EA.CLOUD_ATTACH_TOOL,),
        )
>       assert built == {
            "argv": [
                "claude", "--cloud", "the prompt",
                "--settings",
                '{"remote":{"defaultEnvironmentId":"env_01AbCdEf"},"permissions":{"allow":["mcp__claude-code-remote__add_repo"]}}',
                "--model", "opus", "--effort", "medium", "--permission-mode", "auto",
                "--disallowedTools", "AskUserQuestion", "-n", "issue-1-ab",
            ],
            "reason": None,
        }
E       assert {'argv': ['cl...reason': None} == {'argv': ['cl...reason': None}
E         
E         Omitting 1 identical items, use -vv to show
E         Differing items:
E         {'argv': ['claude', '--cloud', 'the prompt', '--settings', '{"remote":{"defaultEnvironmentId":"env_01AbCdEf"}}', '--model', ...]} != {'argv': ['claude', '--cloud', 'the prompt', '--settings', '{"remote":{"defaultEnvironmentId":"env_01AbCdEf"},"permissions":{"allow":["mcp__claude-code-remote__add_repo"]}}', '--model', ...]}
E         Use -v to get more diff

/home/user/wt-1948/plugins/superheroes/lib/tests/test_launcher_cloud.py:305: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher_cloud.py::test_cloud_argv_grants_the_attach_tool_through_its_settings
1 failed in 0.39s
```

- Restore: the inverse edit; `engine_adapter.py:824-825` read `    if allow_tools:` then `        settings_doc["permissions"] = {"allow": list(allow_tools)}`.
- Green: `1 passed in 0.21s`.

## 2. G2: the no-grant path stays exact

Axis: `allow_tools=None` or `()` leaves the `--settings` JSON, and so the whole argv, exactly as the call that never names it.

- Neutralization (`engine_adapter.py:824-825`): the two lines became `    if True:` then `        settings_doc["permissions"] = {"allow": list(allow_tools or ())}`, so `permissions` is always inserted, with an empty list when none is given.
- Node: `T1::test_cloud_argv_without_an_allowed_tool_is_the_argv_of_the_call_without_the_argument`, both parametrized nodes (`none`, `empty`).
- Red (the traceback of the first node and the summary block; the second node's traceback is the same with `allow_tools = ()`):

```
FF                                                                       [100%]
=================================== FAILURES ===================================
_ test_cloud_argv_without_an_allowed_tool_is_the_argv_of_the_call_without_the_argument[none] _

allow_tools = None

    @pytest.mark.parametrize("allow_tools", [None, ()], ids=["none", "empty"])
    def test_cloud_argv_without_an_allowed_tool_is_the_argv_of_the_call_without_the_argument(allow_tools):
        # axis: no allow_tools (None or empty) leaves the --settings JSON and the whole argv exactly as the call that never names it — see bite-proof record wo_a_1948_add_repo_grant
        plain = EA.claude_cloud_builder_argv("opus", "medium", "the prompt", ENV_ID, "issue-1-ab")
        built = EA.claude_cloud_builder_argv(
            "opus", "medium", "the prompt", ENV_ID, "issue-1-ab", allow_tools=allow_tools,
        )
        assert built == plain
>       assert "permissions" not in built["argv"][built["argv"].index("--settings") + 1]
E       assert 'permissions' not in '{"remote":{..."allow":[]}}'
E         
E         'permissions' is contained here:
E           AbCdEf"},"permissions":{"allow":[]}}
E         ?           +++++++++++

/home/user/wt-1948/plugins/superheroes/lib/tests/test_launcher_cloud.py:325: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher_cloud.py::test_cloud_argv_without_an_allowed_tool_is_the_argv_of_the_call_without_the_argument[none]
FAILED plugins/superheroes/lib/tests/test_launcher_cloud.py::test_cloud_argv_without_an_allowed_tool_is_the_argv_of_the_call_without_the_argument[empty]
2 failed in 0.34s
```

  (The `built == plain` line passed, because both calls took the neutralized path; the `permissions` substring assertion is what went red.)
- Restore: the inverse edit; `engine_adapter.py:824-825` read `    if allow_tools:` then `        settings_doc["permissions"] = {"allow": list(allow_tools)}`.
- Green: `2 passed in 0.22s`.

## 3. G3: the compose grant when extras are present

Axis: a stamped premise carrying `extraRepositories` makes the cloud launch's `--settings` allow the attach tool, and only the `--settings` changes.

- Neutralization (`launcher.py:1423`, `compose_launch`, cloud branch): `if isinstance(premise, dict) and "extraRepositories" in premise:` became `if False and isinstance(premise, dict) and "extraRepositories" in premise:`, so `allow_tools` is never passed.
- Node: `T1::test_compose_cloud_with_extra_repositories_grants_the_attach_tool_and_leaves_the_prompt_alone`.
- Red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_compose_cloud_with_extra_repositories_grants_the_attach_tool_and_leaves_the_prompt_alone _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-4/test_compose_cloud_with_extra_0')

    def test_compose_cloud_with_extra_repositories_grants_the_attach_tool_and_leaves_the_prompt_alone(tmp_path):
        # axis: a stamped premise carrying extraRepositories makes the cloud launch's --settings allow the attach tool, and only the --settings changes — see bite-proof record wo_a_1948_add_repo_grant
        repo = _init_repo(tmp_path / "repo")
        plain = _compose_cloud_with(repo, _stamped(repo))
        granted = _compose_cloud_with(repo, _stamped_with_extras(repo, EXTRAS))
        assert plain["ok"] is True and granted["ok"] is True
        settings = json.loads(_settings_of(granted["argv"]))
>       assert settings["permissions"]["allow"] == [EA.CLOUD_ATTACH_TOOL]
               ^^^^^^^^^^^^^^^^^^^^^^^
E       KeyError: 'permissions'

/home/user/wt-1948/plugins/superheroes/lib/tests/test_launcher_cloud.py:570: KeyError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher_cloud.py::test_compose_cloud_with_extra_repositories_grants_the_attach_tool_and_leaves_the_prompt_alone
1 failed in 0.52s
```

- Restore: the inverse edit; `launcher.py:1423-1424` read `        if isinstance(premise, dict) and "extraRepositories" in premise:` then `            grant["allow_tools"] = (engine_adapter.CLOUD_ATTACH_TOOL,)`.
- Green: `1 passed in 0.48s`.

## 4. G4: no compose grant without extras

Axis: a stamped premise without `extraRepositories` composes the argv `claude_cloud_builder_argv` gives for no grant, and its `--settings` is the bare environment.

- Neutralization (`launcher.py:1423`): the condition became `if True or isinstance(premise, dict) and "extraRepositories" in premise:`, so the grant is always passed.
- Node: `T1::test_compose_cloud_without_extra_repositories_composes_the_argv_it_always_did`.
- Red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_compose_cloud_without_extra_repositories_composes_the_argv_it_always_did _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-6/test_compose_cloud_without_ext0')

    def test_compose_cloud_without_extra_repositories_composes_the_argv_it_always_did(tmp_path):
        # axis: a stamped premise without extraRepositories grants nothing — the --settings is the bare environment and the argv is the unchanged builder argv — see bite-proof record wo_a_1948_add_repo_grant
        repo = _init_repo(tmp_path / "repo")
        composed = _compose_cloud_with(repo, _stamped(repo))
        assert composed["ok"] is True
        argv = composed["argv"]
>       assert _settings_of(argv) == '{"remote":{"defaultEnvironmentId":"%s"}}' % ENV_ID
E       assert '{"remote":{"..._add_repo"]}}' == '{"remote":{"...v_01AbCdEf"}}'
E         
E         Skipping 39 identical leading characters in diff, use -v to show
E         - 01AbCdEf"}}
E         + 01AbCdEf"},"permissions":{"allow":["mcp__claude-code-remote__add_repo"]}}

/home/user/wt-1948/plugins/superheroes/lib/tests/test_launcher_cloud.py:582: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher_cloud.py::test_compose_cloud_without_extra_repositories_composes_the_argv_it_always_did
1 failed in 0.42s
```

- Restore: the inverse edit; `launcher.py:1423` read `        if isinstance(premise, dict) and "extraRepositories" in premise:`.
- Green: `1 passed in 0.41s`.

## 5. G5: the not-a-non-empty-list predicate

Axis: `extraRepositories` must be a non-empty list; a bare string or an empty list is refused whole.

- Neutralization (`launcher.py:1299`, `validate_premise`): `if not isinstance(extras_val, list) or not extras_val:` became `if False and (not isinstance(extras_val, list) or not extras_val):`.
- Node: `T1::test_an_extra_repositories_field_that_is_not_a_non_empty_list_is_refused`, run whole so both parametrized nodes show. The `empty-list` node goes red alone. The `string` node (E1, `"a/b"`) stays green, as WO-A found: iterating the string gives `"a"`, which the name-shape predicate still refuses.
- Red:

```
.F                                                                       [100%]
=================================== FAILURES ===================================
_ test_an_extra_repositories_field_that_is_not_a_non_empty_list_is_refused[empty-list] _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-8/test_an_extra_repositories_fie1')
extras = []

    @pytest.mark.parametrize("extras", [
        pytest.param("a/b", id="string"),
        pytest.param([], id="empty-list"),
    ])
    def test_an_extra_repositories_field_that_is_not_a_non_empty_list_is_refused(tmp_path, extras):
        # axis: extraRepositories must be a non-empty list — a bare string or an empty list is refused whole, never read as no grant — see bite-proof record wo_a_1948_add_repo_grant
        repo = _init_repo(tmp_path / "repo")
        result = L.validate_premise(_valid_premise(repo, extraRepositories=extras), repo, issue=656)
>       assert result["ok"] is False
E       assert True is False

/home/user/wt-1948/plugins/superheroes/lib/tests/test_launcher_cloud.py:598: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher_cloud.py::test_an_extra_repositories_field_that_is_not_a_non_empty_list_is_refused[empty-list]
1 failed, 1 passed in 0.41s
```

- Restore: the inverse edit; `launcher.py:1299` read `        if not isinstance(extras_val, list) or not extras_val:`.
- Green: `2 passed in 0.31s`.

## 6. G6: the name-shape predicate

Axis: every member of `extraRepositories` must be a valid `owner/repo` name.

- Neutralization (`launcher.py:1301`): `if not all(issue_contract.valid_repository_name(r) for r in extras_val):` became `if False and not all(issue_contract.valid_repository_name(r) for r in extras_val):`.
- Node: `T1::test_an_extra_repository_that_is_not_an_owner_and_repo_name_is_refused`, all five parametrized nodes (`a`, `a/b/c`, ` a/b`, `-a/b`, `a/..`).
- Red: all five failed on `assert result["ok"] is False` with `E       assert True is False`. The summary block and last line follow; the five tracebacks differ only in the parameter. (Excerpt of the capture, labelled as such.)

```
FFFFF                                                                    [100%]
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher_cloud.py::test_an_extra_repository_that_is_not_an_owner_and_repo_name_is_refused[a]
FAILED plugins/superheroes/lib/tests/test_launcher_cloud.py::test_an_extra_repository_that_is_not_an_owner_and_repo_name_is_refused[a/b/c]
FAILED plugins/superheroes/lib/tests/test_launcher_cloud.py::test_an_extra_repository_that_is_not_an_owner_and_repo_name_is_refused[ a/b]
FAILED plugins/superheroes/lib/tests/test_launcher_cloud.py::test_an_extra_repository_that_is_not_an_owner_and_repo_name_is_refused[-a/b]
FAILED plugins/superheroes/lib/tests/test_launcher_cloud.py::test_an_extra_repository_that_is_not_an_owner_and_repo_name_is_refused[a/..]
5 failed in 0.66s
```

- Restore: the inverse edit; `launcher.py:1301` read `        if not all(issue_contract.valid_repository_name(r) for r in extras_val):`.
- Green: `5 passed in 0.33s`.

## 7. G7: the distinctness predicate

Axis: the members of `extraRepositories` are distinct whatever their case.

- Neutralization (`launcher.py:1303`): `if len({r.lower() for r in extras_val}) != len(extras_val):` became `if False and len({r.lower() for r in extras_val}) != len(extras_val):`.
- Node: `T1::test_an_extra_repository_named_twice_in_different_case_is_refused`.
- Red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
______ test_an_extra_repository_named_twice_in_different_case_is_refused _______

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-12/test_an_extra_repository_named0')

    def test_an_extra_repository_named_twice_in_different_case_is_refused(tmp_path):
        # axis: the members of extraRepositories are distinct whatever their case, since GitHub names are case-insensitive — see bite-proof record wo_a_1948_add_repo_grant
        repo = _init_repo(tmp_path / "repo")
        result = L.validate_premise(
            _valid_premise(repo, extraRepositories=["Weekly-Eats-HQ/weekly-eats", "weekly-eats-hq/Weekly-Eats"]),
            repo, issue=656)
>       assert result["ok"] is False
E       assert True is False

/home/user/wt-1948/plugins/superheroes/lib/tests/test_launcher_cloud.py:618: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher_cloud.py::test_an_extra_repository_named_twice_in_different_case_is_refused
1 failed in 0.41s
```

- Restore: the inverse edit; `launcher.py:1303` read `        if len({r.lower() for r in extras_val}) != len(extras_val):`.
- Green: `1 passed in 0.28s`.

## 8. G8: the not-cloud refusal

Axis: a premise naming extra repositories on a launch not placed in the cloud is refused before any lane is reserved or anything is spawned.

- Neutralization (`launcher.py:2504-2505`, `_place_refusal`): the two lines `if place != PLACE_CLOUD and isinstance(premise, dict) and "extraRepositories" in premise:` and `return _fail("launch-extra-repositories-not-cloud", launchId=launch_id)` were deleted (the `# axis:` comment above them stayed).
- Node A: `T1::test_edge1_extra_repositories_on_a_launch_not_placed_in_the_cloud_writes_nothing[none]`.
- Red A:

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_edge1_extra_repositories_on_a_launch_not_placed_in_the_cloud_writes_nothing[none] _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-14/test_edge1_extra_repositories_0')
place = None

    @pytest.mark.parametrize("place", [None, "local"], ids=["none", "local"])
    def test_edge1_extra_repositories_on_a_launch_not_placed_in_the_cloud_writes_nothing(tmp_path, place):
        # axis: refused before any write — a premise naming extra repositories on a launch not placed in the cloud reserves no lane and spawns nothing — see bite-proof record wo_a_1948_add_repo_grant
        repo = _cloud_repo(tmp_path)
        calls = []
        premise = _valid_premise(repo, extraRepositories=EXTRAS)
        result = _launch(repo, tmp_path, _fake_spawn(calls=calls), premise=premise, place=place)
>       assert result["ok"] is False
E       assert True is False

/home/user/wt-1948/plugins/superheroes/lib/tests/test_launcher_cloud.py:747: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher_cloud.py::test_edge1_extra_repositories_on_a_launch_not_placed_in_the_cloud_writes_nothing[none]
1 failed in 20.78s

<sandbox_violations>
deny network-outbound api.anthropic.com:443 (host is not on the allow list)
(ten such lines in all)
</sandbox_violations>
```

- Node B: `T1::test_edge1_extra_repositories_on_a_launch_not_placed_in_the_cloud_writes_nothing[local]`.
- Red B:

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_edge1_extra_repositories_on_a_launch_not_placed_in_the_cloud_writes_nothing[local] _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-15/test_edge1_extra_repositories_0')
place = 'local'

    @pytest.mark.parametrize("place", [None, "local"], ids=["none", "local"])
    def test_edge1_extra_repositories_on_a_launch_not_placed_in_the_cloud_writes_nothing(tmp_path, place):
        # axis: refused before any write — a premise naming extra repositories on a launch not placed in the cloud reserves no lane and spawns nothing — see bite-proof record wo_a_1948_add_repo_grant
        repo = _cloud_repo(tmp_path)
        calls = []
        premise = _valid_premise(repo, extraRepositories=EXTRAS)
        result = _launch(repo, tmp_path, _fake_spawn(calls=calls), premise=premise, place=place)
>       assert result["ok"] is False
E       assert True is False

/home/user/wt-1948/plugins/superheroes/lib/tests/test_launcher_cloud.py:747: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher_cloud.py::test_edge1_extra_repositories_on_a_launch_not_placed_in_the_cloud_writes_nothing[local]
1 failed in 20.71s

<sandbox_violations>
deny network-outbound api.anthropic.com:443 (host is not on the allow list)
(ten such lines in all)
</sandbox_violations>
```

  (The ten identical `sandbox_violations` lines of each run are abbreviated to one line and a count above.)
- Restore: the inverse edit; `launcher.py:2503-2505` read the `# axis:` comment, `    if place != PLACE_CLOUD and isinstance(premise, dict) and "extraRepositories" in premise:` and `        return _fail("launch-extra-repositories-not-cloud", launchId=launch_id)`. The first restore edit also re-added the comment line, leaving it twice; the stray second copy was removed by one more edit before the green runs.
- Green A: `1 passed in 0.46s`. Green B: `1 passed in 0.45s`.

## 9. G9: live-line gating by fence kind

Axis: a line inside a fenced block is an example, never live.

- Neutralization (`issue_contract.py:113`, `extra_repositories`): `if kind in (md_fence.KIND_OPENER, md_fence.KIND_CLOSER, md_fence.KIND_CONTENT):` lost `md_fence.KIND_CONTENT`, so fence content is no longer skipped.
- Node: `T2::test_extras_a_fenced_only_example_line_is_no_line`.
- Red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
______________ test_extras_a_fenced_only_example_line_is_no_line _______________

    def test_extras_a_fenced_only_example_line_is_no_line():
        # axis: a line inside a fenced block is an example, never live — an example-only body is ok with no repositories — see bite-proof record wo_a_1948_add_repo_grant
        body = (
            "Write it like this:\n"
            "```\n"
            "Extra repositories: owner/repo, owner/other\n"
            "```\n"
        )
>       assert _extras(body) == {"ok": True, "reason": None, "repositories": []}
E       AssertionError: assert {'ok': True, ...owner/other']} == {'ok': True, ...sitories': []}
E         
E         Omitting 2 identical items, use -vv to show
E         Differing items:
E         {'repositories': ['owner/repo', 'owner/other']} != {'repositories': []}
E         Use -v to get more diff

/home/user/wt-1948/plugins/superheroes/lib/tests/test_issue_contract.py:670: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_issue_contract.py::test_extras_a_fenced_only_example_line_is_no_line
1 failed in 0.24s
```

- Restore: the inverse edit; `issue_contract.py:113` read `        if kind in (md_fence.KIND_OPENER, md_fence.KIND_CLOSER, md_fence.KIND_CONTENT):`.
- Green: `1 passed in 0.24s`.

## 10. G10: the indent gate

Axis: a line indented four columns or more is an indented code block, never live.

- Neutralization (`issue_contract.py:116`): `if md_fence.indent_width(line) >= md_fence.INDENT_CODE_BLOCK_COLUMNS:` became `if False and md_fence.indent_width(line) >= md_fence.INDENT_CODE_BLOCK_COLUMNS:`. (The same expression appears at one other place in the file, outside `extra_repositories`; the edit carried the comment line above it for context so only this one changed.)
- Node: `T2::test_extras_a_line_indented_four_columns_is_not_live`, all three parametrized nodes (`four-spaces`, `tab`, `five-spaces`).
- Red (the first node's traceback and the summary block; the other two differ only in the prefix):

```
FFF                                                                      [100%]
=================================== FAILURES ===================================
______ test_extras_a_line_indented_four_columns_is_not_live[four-spaces] _______

prefix = '    '

    @pytest.mark.parametrize("prefix", ["    ", "\t", "     "], ids=["four-spaces", "tab", "five-spaces"])
    def test_extras_a_line_indented_four_columns_is_not_live(prefix):
        # axis: an indented code block (4+ columns) is never a live extra-repositories line — see bite-proof record wo_a_1948_add_repo_grant
>       assert _extras(prefix + "Extra repositories: zwrose/superheroes\n") == {
            "ok": True, "reason": None, "repositories": [],
        }
E       AssertionError: assert {'ok': True, ...superheroes']} == {'ok': True, ...sitories': []}
E         
E         Omitting 2 identical items, use -vv to show
E         Differing items:
E         {'repositories': ['zwrose/superheroes']} != {'repositories': []}
E         Use -v to get more diff

/home/user/wt-1948/plugins/superheroes/lib/tests/test_issue_contract.py:697: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_issue_contract.py::test_extras_a_line_indented_four_columns_is_not_live[four-spaces]
FAILED plugins/superheroes/lib/tests/test_issue_contract.py::test_extras_a_line_indented_four_columns_is_not_live[tab]
FAILED plugins/superheroes/lib/tests/test_issue_contract.py::test_extras_a_line_indented_four_columns_is_not_live[five-spaces]
3 failed in 0.20s
```

- Restore: the inverse edit; `issue_contract.py:116` read `        if md_fence.indent_width(line) >= md_fence.INDENT_CODE_BLOCK_COLUMNS:`.
- Green: `3 passed in 0.15s`.

## 11. G11: the line-repeated refusal

Axis: two live lines are refused as `extra-repositories-line-repeated`, never merged.

- Neutralization (`issue_contract.py:123`): `if len(live) >= 2:` became `if False and len(live) >= 2:`.
- Node: `T2::test_extras_two_live_lines_are_refused_as_repeated`.
- Red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
______________ test_extras_two_live_lines_are_refused_as_repeated ______________

    def test_extras_two_live_lines_are_refused_as_repeated():
        # axis: the line may appear once — two live lines are refused as extra-repositories-line-repeated, never merged — see bite-proof record wo_a_1948_add_repo_grant
        body = "Extra repositories: a/b\nWhat: scope\nExtra repositories: c/d\n"
>       assert _extras(body) == _refused(ic.REFUSAL_EXTRA_REPOSITORIES_LINE_REPEATED)
E       AssertionError: assert {'ok': True, ...ies': ['a/b']} == {'ok': False,...sitories': []}
E         
E         Differing items:
E         {'ok': True} != {'ok': False}
E         {'repositories': ['a/b']} != {'repositories': []}
E         {'reason': None} != {'reason': 'extra-repositories-line-repeated'}
E         Use -v to get more diff

/home/user/wt-1948/plugins/superheroes/lib/tests/test_issue_contract.py:615: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_issue_contract.py::test_extras_two_live_lines_are_refused_as_repeated
1 failed in 0.16s
```

- Restore: the inverse edit; `issue_contract.py:123` read `    if len(live) >= 2:`.
- Green: `1 passed in 0.18s`.

## 12. G12: the empty refusal

Axis: a line with no value, or an empty item between commas, is refused as `extra-repositories-empty`, never read as a shorter list.

- Neutralization (`issue_contract.py:127`): `if not all(items):` became `if False and not all(items):`.
- Node: `T2::test_extras_an_empty_value_or_an_empty_item_is_refused_as_empty`, all five parametrized nodes (`no-value`, `blank-value`, `empty-item`, `trailing-comma`, `leading-comma`).
- Red: all five failed; the empty item then fell through to the name check and was reported as `extra-repositories-name-invalid` instead. The first node's traceback and the summary block follow; the other four differ only in the parameter. (Excerpt of the capture, labelled as such.)

```
FFFFF                                                                    [100%]
=================================== FAILURES ===================================
__ test_extras_an_empty_value_or_an_empty_item_is_refused_as_empty[no-value] ___

line = 'Extra repositories:'

    @pytest.mark.parametrize("line", [
        "Extra repositories:",
        "Extra repositories:    ",
        "Extra repositories: a/b,,c/d",
        "Extra repositories: a/b,",
        "Extra repositories: ,a/b",
    ], ids=["no-value", "blank-value", "empty-item", "trailing-comma", "leading-comma"])
    def test_extras_an_empty_value_or_an_empty_item_is_refused_as_empty(line):
        # axis: a line with no value, or an empty item between commas, is refused as extra-repositories-empty — never read as a shorter list — see bite-proof record wo_a_1948_add_repo_grant
>       assert _extras(line + "\n") == _refused(ic.REFUSAL_EXTRA_REPOSITORIES_EMPTY)
E       AssertionError: assert {'ok': False,...sitories': []} == {'ok': False,...sitories': []}
E         
E         Omitting 2 identical items, use -vv to show
E         Differing items:
E         {'reason': 'extra-repositories-name-invalid'} != {'reason': 'extra-repositories-empty'}
E         Use -v to get more diff

/home/user/wt-1948/plugins/superheroes/lib/tests/test_issue_contract.py:627: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_issue_contract.py::test_extras_an_empty_value_or_an_empty_item_is_refused_as_empty[no-value]
FAILED plugins/superheroes/lib/tests/test_issue_contract.py::test_extras_an_empty_value_or_an_empty_item_is_refused_as_empty[blank-value]
FAILED plugins/superheroes/lib/tests/test_issue_contract.py::test_extras_an_empty_value_or_an_empty_item_is_refused_as_empty[empty-item]
FAILED plugins/superheroes/lib/tests/test_issue_contract.py::test_extras_an_empty_value_or_an_empty_item_is_refused_as_empty[trailing-comma]
FAILED plugins/superheroes/lib/tests/test_issue_contract.py::test_extras_an_empty_value_or_an_empty_item_is_refused_as_empty[leading-comma]
5 failed in 0.23s
```

- Restore: the inverse edit; `issue_contract.py:127` read `    if not all(items):`.
- Green: `5 passed in 0.16s`.

## 13. G13: the name-invalid refusal

Axis: every item must be a valid `owner/repo` name; one bad item beside a good one refuses the whole line.

- Neutralization (`issue_contract.py:130`): `if not all(valid_repository_name(item) for item in items):` became `if False and not all(valid_repository_name(item) for item in items):`.
- Node: `T2::test_extras_an_invalid_name_is_refused_as_name_invalid`, all eleven parametrized nodes.
- Red: **incomplete capture.** The harness cut 6580 characters out of the middle of the run's output, so the middle of the capture, from inside the fourth node's traceback to inside the ninth's, is lost to me and is not reconstructed here. What I have, labelled for what it is: the first node's traceback, the `short test summary info` block with all eleven nodes, and the last line.

```
FFFFFFFFFFF                                                              [100%]
=================================== FAILURES ===================================
_______ test_extras_an_invalid_name_is_refused_as_name_invalid[no-slash] _______

name = 'a'

    @pytest.mark.parametrize("name", [
        "a",
        "a/b/c",
        "-a/b",
        "a_b/c",
        "a/",
        "/b",
        "a/..",
        "a/.",
        "a/b c",
        "o" * 40 + "/r",
        "o/" + "r" * 101,
    ], ids=["no-slash", "three-parts", "leading-hyphen", "underscore-owner", "no-repo", "no-owner",
            "dot-dot", "dot", "inner-space", "owner-40", "repo-101"])
    def test_extras_an_invalid_name_is_refused_as_name_invalid(name):
        # axis: every item must be a valid owner/repo name — one bad item refuses the whole line, beside good ones — see bite-proof record wo_a_1948_add_repo_grant
>       assert _extras("Extra repositories: zwrose/ok, %s\n" % name) == _refused(
            ic.REFUSAL_EXTRA_REPOSITORIES_NAME_INVALID)
E       AssertionError: assert {'ok': True, ...ose/ok', 'a']} == {'ok': False,...sitories': []}
E         
E         Differing items:
E         {'repositories': ['zwrose/ok', 'a']} != {'repositories': []}
E         {'reason': None} != {'reason': 'extra-repositories-name-invalid'}
E         {'ok': True} != {'ok': False}
E         Use -v to get more diff

/home/user/wt-1948/plugins/superheroes/lib/tests/test_issue_contract.py:646: AssertionError

... [6580 characters truncated by the harness; not available] ...

=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_issue_contract.py::test_extras_an_invalid_name_is_refused_as_name_invalid[no-slash]
FAILED plugins/superheroes/lib/tests/test_issue_contract.py::test_extras_an_invalid_name_is_refused_as_name_invalid[three-parts]
FAILED plugins/superheroes/lib/tests/test_issue_contract.py::test_extras_an_invalid_name_is_refused_as_name_invalid[leading-hyphen]
FAILED plugins/superheroes/lib/tests/test_issue_contract.py::test_extras_an_invalid_name_is_refused_as_name_invalid[underscore-owner]
FAILED plugins/superheroes/lib/tests/test_issue_contract.py::test_extras_an_invalid_name_is_refused_as_name_invalid[no-repo]
FAILED plugins/superheroes/lib/tests/test_issue_contract.py::test_extras_an_invalid_name_is_refused_as_name_invalid[no-owner]
FAILED plugins/superheroes/lib/tests/test_issue_contract.py::test_extras_an_invalid_name_is_refused_as_name_invalid[dot-dot]
FAILED plugins/superheroes/lib/tests/test_issue_contract.py::test_extras_an_invalid_name_is_refused_as_name_invalid[dot]
FAILED plugins/superheroes/lib/tests/test_issue_contract.py::test_extras_an_invalid_name_is_refused_as_name_invalid[inner-space]
FAILED plugins/superheroes/lib/tests/test_issue_contract.py::test_extras_an_invalid_name_is_refused_as_name_invalid[owner-40]
FAILED plugins/superheroes/lib/tests/test_issue_contract.py::test_extras_an_invalid_name_is_refused_as_name_invalid[repo-101]
11 failed in 0.32s
```

- Restore: the inverse edit; `issue_contract.py:130` read `    if not all(valid_repository_name(item) for item in items):`.
- Green: `11 passed in 0.21s`.

## 14. G14: the name-repeated refusal

Axis: the same name twice, in any case, is refused as `extra-repositories-name-repeated`.

- Neutralization (`issue_contract.py:133`): `if len({item.lower() for item in items}) != len(items):` became `if False and len({item.lower() for item in items}) != len(items):`.
- Node: `T2::test_extras_a_name_repeated_in_different_case_is_refused_as_name_repeated`.
- Red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
__ test_extras_a_name_repeated_in_different_case_is_refused_as_name_repeated ___

    def test_extras_a_name_repeated_in_different_case_is_refused_as_name_repeated():
        # axis: GitHub names are case-insensitive — the same name twice, in any case, is refused as extra-repositories-name-repeated — see bite-proof record wo_a_1948_add_repo_grant
        body = "Extra repositories: Weekly-Eats-HQ/weekly-eats, weekly-eats-hq/WEEKLY-EATS\n"
>       assert _extras(body) == _refused(ic.REFUSAL_EXTRA_REPOSITORIES_NAME_REPEATED)
E       AssertionError: assert {'ok': True, ...WEEKLY-EATS']} == {'ok': False,...sitories': []}
E         
E         Differing items:
E         {'reason': None} != {'reason': 'extra-repositories-name-repeated'}
E         {'repositories': ['Weekly-Eats-HQ/weekly-eats', 'weekly-eats-hq/WEEKLY-EATS']} != {'repositories': []}
E         {'ok': True} != {'ok': False}
E         Use -v to get more diff

/home/user/wt-1948/plugins/superheroes/lib/tests/test_issue_contract.py:659: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_issue_contract.py::test_extras_a_name_repeated_in_different_case_is_refused_as_name_repeated
1 failed in 0.15s
```

- Restore: the inverse edit; `issue_contract.py:133` read `    if len({item.lower() for item in items}) != len(items):`.
- Green: `1 passed in 0.17s`.
