# Bite-proof record: a cloud launch passes `--allowedTools` if and only if `allow_tools` is non-empty

Detector: `plugins/superheroes/lib/tests/test_launcher_cloud.py` (`T1`).
Guarded elements (declared by the order): (G1) the `--allowedTools` insertion in `engine_adapter.claude_cloud_builder_argv`;
(G2) the no-`--allowedTools` path of that function staying exact.
The invariant: `--allowedTools` and the tools in `allow_tools` appear in the cloud argv if and only if `allow_tools` is non-empty.
Census: the block at `engine_adapter.py:833-834` is the only production argv site of `--allowedTools`. `grep -rn allowedTools plugins/superheroes/lib --include=*.py`
also lists the function's docstring (line 803), the tests, and `engine_adapter.py:836`, the `--disallowedTools` argv line (a different flag that contains the
substring); none of those builds a `--allowedTools` argv.
Each element was neutralized by a targeted edit in the production file, anchored on the two-line pair `if allow_tools:` + `argv += ["--allowedTools", *allow_tools]`
(the line `if allow_tools:` also opens the `--settings` block at line 825, which no edit touched), the detector nodes run together in one command
(a parametrized function is run whole), then restored by the inverse edit. No test file was edited during the proofs. After both restores,
`git diff HEAD` prints nothing.

Every command was run from the worktree root as `timeout 300 scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest <nodes> -q -p no:cacheprovider`,
where `<nodes>` are the `T1::` nodes named in each section. The `UV_NATIVE_TLS` deprecation warning that heads every run is omitted below.

Pinned condition: none beyond the sandbox.

## 1. G1: the `--allowedTools` insertion

Axis: a non-empty `allow_tools` adds one `--allowedTools` followed by every tool in order, after `--permission-mode` and before `--disallowedTools`.

- Neutralization (`engine_adapter.py:833`, `claude_cloud_builder_argv`): the pair became `    if False and allow_tools:` then `        argv += ["--allowedTools", *allow_tools]`.
- Nodes, in one command:
  - `T1::test_cloud_argv_grants_the_attach_tool_through_its_settings_and_allowed_tools`
  - `T1::test_cloud_argv_passes_every_allowed_tool_in_order_before_the_disallowed_tools`
  - `T1::test_compose_cloud_with_extra_repositories_grants_the_attach_tool_and_leaves_the_prompt_alone`
- Red (all three failed):

```
FFF                                                                      [100%]
=================================== FAILURES ===================================
_ test_cloud_argv_grants_the_attach_tool_through_its_settings_and_allowed_tools _

    def test_cloud_argv_grants_the_attach_tool_through_its_settings_and_allowed_tools():
        # axis: a non-empty allow_tools puts a permissions.allow list after `remote` in the --settings JSON, and the grant also adds --allowedTools before --disallowedTools — see bite-proof record wo_a_1948_add_repo_grant and wo_a2_1948_allowed_tools
        built = EA.claude_cloud_builder_argv(
            "opus", "medium", "the prompt", ENV_ID, "issue-1-ab", allow_tools=(EA.CLOUD_ATTACH_TOOL,),
        )
>       assert built == {
            "argv": [
                "claude", "--cloud", "the prompt",
                "--settings",
                '{"remote":{"defaultEnvironmentId":"env_01AbCdEf"},"permissions":{"allow":["mcp__claude-code-remote__add_repo"]}}',
                "--model", "opus", "--effort", "medium", "--permission-mode", "auto",
                "--allowedTools", "mcp__claude-code-remote__add_repo",
                "--disallowedTools", "AskUserQuestion", "-n", "issue-1-ab",
            ],
            "reason": None,
        }
E       assert {'argv': ['cl...reason': None} == {'argv': ['cl...reason': None}
E         
E         Omitting 1 identical items, use -vv to show
E         Differing items:
E         {'argv': ['claude', '--cloud', 'the prompt', '--settings', '{"remote":{"defaultEnvironmentId":"env_01AbCdEf"},"permissions":{"allow":["mcp__claude-code-remote__add_repo"]}}', '--model', ...]} != {'argv': ['claude', '--cloud', 'the prompt', '--settings', '{"remote":{"defaultEnvironmentId":"env_01AbCdEf"},"permissions":{"allow":["mcp__claude-code-remote__add_repo"]}}', '--model', ...]}
E         Use -v to get more diff

/home/user/wt-1948/plugins/superheroes/lib/tests/test_launcher_cloud.py:305: AssertionError
_ test_cloud_argv_passes_every_allowed_tool_in_order_before_the_disallowed_tools _

    def test_cloud_argv_passes_every_allowed_tool_in_order_before_the_disallowed_tools():
        # axis: every tool in allow_tools follows one --allowedTools, in order, before --disallowedTools (or straight before -n when none) — see bite-proof record wo_a2_1948_allowed_tools
        argv = EA.claude_cloud_builder_argv("opus", None, "p", ENV_ID, "n", allow_tools=("t1", "t2"))["argv"]
>       assert argv[argv.index("--allowedTools"):] == [
                    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
            "--allowedTools", "t1", "t2", "--disallowedTools", "AskUserQuestion", "-n", "n",
        ]
E       ValueError: '--allowedTools' is not in list

/home/user/wt-1948/plugins/superheroes/lib/tests/test_launcher_cloud.py:321: ValueError
_ test_compose_cloud_with_extra_repositories_grants_the_attach_tool_and_leaves_the_prompt_alone _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-0/test_compose_cloud_with_extra_0')

    def test_compose_cloud_with_extra_repositories_grants_the_attach_tool_and_leaves_the_prompt_alone(tmp_path):
        # axis: a stamped premise carrying extraRepositories makes the cloud launch's --settings allow the attach tool, and only the --settings and --allowedTools change — see bite-proof record wo_a_1948_add_repo_grant and wo_a2_1948_allowed_tools
        repo = _init_repo(tmp_path / "repo")
        plain = _compose_cloud_with(repo, _stamped(repo))
        granted = _compose_cloud_with(repo, _stamped_with_extras(repo, EXTRAS))
        assert plain["ok"] is True and granted["ok"] is True
        settings = json.loads(_settings_of(granted["argv"]))
        assert settings["permissions"]["allow"] == [EA.CLOUD_ATTACH_TOOL]
        assert settings["remote"] == {"defaultEnvironmentId": ENV_ID}
>       assert granted["argv"].count("--allowedTools") == 1
E       assert 0 == 1
E        +  where 0 = <built-in method count of list object at 0x7f00526af680>('--allowedTools')
E        +    where <built-in method count of list object at 0x7f00526af680> = ['claude', '--cloud', '/superheroes:workhorse\n\nIssue: #656\n\nPlace: cloud session\nAdvisor plugin version: 0.45.0\n..."defaultEnvironmentId":"env_01AbCdEf"},"permissions":{"allow":["mcp__claude-code-remote__add_repo"]}}', '--model', ...].count

/home/user/wt-1948/plugins/superheroes/lib/tests/test_launcher_cloud.py:588: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher_cloud.py::test_cloud_argv_grants_the_attach_tool_through_its_settings_and_allowed_tools
FAILED plugins/superheroes/lib/tests/test_launcher_cloud.py::test_cloud_argv_passes_every_allowed_tool_in_order_before_the_disallowed_tools
FAILED plugins/superheroes/lib/tests/test_launcher_cloud.py::test_compose_cloud_with_extra_repositories_grants_the_attach_tool_and_leaves_the_prompt_alone
3 failed in 1.63s
```

- Restore: the inverse edit, anchored on the same pair; `engine_adapter.py:833-834` read `    if allow_tools:` then `        argv += ["--allowedTools", *allow_tools]`.
- Green (same three nodes, one command): `3 passed in 1.45s`.

## 2. G2: the no-`--allowedTools` path stays exact

Axis: `allow_tools=None` or `()` leaves the argv without `--allowedTools`, exactly as the call that never names it.

- Neutralization (`engine_adapter.py:833-834`): the pair became `    if True:` then `        argv += ["--allowedTools", *(allow_tools or ())]`, so a bare `--allowedTools` is always appended, with no tools when none is given.
- Nodes, in one command:
  - `T1::test_cloud_argv_without_an_allowed_tool_is_the_argv_of_the_call_without_the_argument` (both parametrized nodes, `none` and `empty`)
  - `T1::test_compose_cloud_without_extra_repositories_composes_the_argv_it_always_did`
  - `T1::test_cloud_argv_shape_and_order`
- Red (all four failed; in the first test the `built == plain` and `permissions` assertions passed, because both calls took the neutralized path, and the `--allowedTools` assertion is what went red):

```
FFFF                                                                     [100%]
=================================== FAILURES ===================================
_ test_cloud_argv_without_an_allowed_tool_is_the_argv_of_the_call_without_the_argument[none] _

allow_tools = None

    @pytest.mark.parametrize("allow_tools", [None, ()], ids=["none", "empty"])
    def test_cloud_argv_without_an_allowed_tool_is_the_argv_of_the_call_without_the_argument(allow_tools):
        # axis: no allow_tools (None or empty) leaves the --settings JSON and the whole argv exactly as the call that never names it — see bite-proof record wo_a_1948_add_repo_grant and wo_a2_1948_allowed_tools
        plain = EA.claude_cloud_builder_argv("opus", "medium", "the prompt", ENV_ID, "issue-1-ab")
        built = EA.claude_cloud_builder_argv(
            "opus", "medium", "the prompt", ENV_ID, "issue-1-ab", allow_tools=allow_tools,
        )
        assert built == plain
        assert "permissions" not in built["argv"][built["argv"].index("--settings") + 1]
>       assert "--allowedTools" not in built["argv"]
E       assert '--allowedTools' not in ['claude', '--cloud', 'the prompt', '--settings', '{"remote":{"defaultEnvironmentId":"env_01AbCdEf"}}', '--model', ...]

/home/user/wt-1948/plugins/superheroes/lib/tests/test_launcher_cloud.py:341: AssertionError
_ test_cloud_argv_without_an_allowed_tool_is_the_argv_of_the_call_without_the_argument[empty] _

allow_tools = ()

    @pytest.mark.parametrize("allow_tools", [None, ()], ids=["none", "empty"])
    def test_cloud_argv_without_an_allowed_tool_is_the_argv_of_the_call_without_the_argument(allow_tools):
        # axis: no allow_tools (None or empty) leaves the --settings JSON and the whole argv exactly as the call that never names it — see bite-proof record wo_a_1948_add_repo_grant and wo_a2_1948_allowed_tools
        plain = EA.claude_cloud_builder_argv("opus", "medium", "the prompt", ENV_ID, "issue-1-ab")
        built = EA.claude_cloud_builder_argv(
            "opus", "medium", "the prompt", ENV_ID, "issue-1-ab", allow_tools=allow_tools,
        )
        assert built == plain
        assert "permissions" not in built["argv"][built["argv"].index("--settings") + 1]
>       assert "--allowedTools" not in built["argv"]
E       assert '--allowedTools' not in ['claude', '--cloud', 'the prompt', '--settings', '{"remote":{"defaultEnvironmentId":"env_01AbCdEf"}}', '--model', ...]

/home/user/wt-1948/plugins/superheroes/lib/tests/test_launcher_cloud.py:341: AssertionError
_ test_compose_cloud_without_extra_repositories_composes_the_argv_it_always_did _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-2/test_compose_cloud_without_ext0')

    def test_compose_cloud_without_extra_repositories_composes_the_argv_it_always_did(tmp_path):
        # axis: a stamped premise without extraRepositories grants nothing — the --settings is the bare environment and the argv is the unchanged builder argv — see bite-proof record wo_a_1948_add_repo_grant and wo_a2_1948_allowed_tools
        repo = _init_repo(tmp_path / "repo")
        composed = _compose_cloud_with(repo, _stamped(repo))
        assert composed["ok"] is True
        argv = composed["argv"]
        assert _settings_of(argv) == '{"remote":{"defaultEnvironmentId":"%s"}}' % ENV_ID
        assert not any("permissions" in part for part in argv)
>       assert "--allowedTools" not in argv
E       assert '--allowedTools' not in ['claude', '--cloud', '/superheroes:workhorse\n\nIssue: #656\n\nPlace: cloud session\nAdvisor plugin version: 0.45.0\n...e to dodge the gate is forbidden.', '--settings', '{"remote":{"defaultEnvironmentId":"env_01AbCdEf"}}', '--model', ...]

/home/user/wt-1948/plugins/superheroes/lib/tests/test_launcher_cloud.py:604: AssertionError
_______________________ test_cloud_argv_shape_and_order ________________________

    def test_cloud_argv_shape_and_order():
        built = EA.claude_cloud_builder_argv("opus", "medium", "the prompt", ENV_ID, "issue-1-ab")
>       assert built == {
            "argv": [
                "claude", "--cloud", "the prompt",
                "--settings", '{"remote":{"defaultEnvironmentId":"%s"}}' % ENV_ID,
                "--model", "opus", "--effort", "medium", "--permission-mode", "auto",
                "--disallowedTools", "AskUserQuestion", "-n", "issue-1-ab",
            ],
            "reason": None,
        }
E       assert {'argv': ['cl...reason': None} == {'argv': ['cl...reason': None}
E         
E         Omitting 1 identical items, use -vv to show
E         Differing items:
E         {'argv': ['claude', '--cloud', 'the prompt', '--settings', '{"remote":{"defaultEnvironmentId":"env_01AbCdEf"}}', '--model', ...]} != {'argv': ['claude', '--cloud', 'the prompt', '--settings', '{"remote":{"defaultEnvironmentId":"env_01AbCdEf"}}', '--model', ...]}
E         Use -v to get more diff

/home/user/wt-1948/plugins/superheroes/lib/tests/test_launcher_cloud.py:212: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher_cloud.py::test_cloud_argv_without_an_allowed_tool_is_the_argv_of_the_call_without_the_argument[none]
FAILED plugins/superheroes/lib/tests/test_launcher_cloud.py::test_cloud_argv_without_an_allowed_tool_is_the_argv_of_the_call_without_the_argument[empty]
FAILED plugins/superheroes/lib/tests/test_launcher_cloud.py::test_compose_cloud_without_extra_repositories_composes_the_argv_it_always_did
FAILED plugins/superheroes/lib/tests/test_launcher_cloud.py::test_cloud_argv_shape_and_order
4 failed in 1.61s
```

- Restore: the inverse edit, anchored on the same pair; `engine_adapter.py:833-834` read `    if allow_tools:` then `        argv += ["--allowedTools", *allow_tools]`.
- Green (same three nodes, one command): `4 passed in 1.20s`.

## 3. The tree after the restores

`git diff HEAD`, run after both restores, printed nothing (exit status 0):

```
$ git diff HEAD
```

The tree matched HEAD after the restores.
