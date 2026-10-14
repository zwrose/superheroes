# Bite-proof record: cloud builders start headless with the standing push sentence

Detectors: `plugins/superheroes/lib/tests/test_launcher_cloud.py` (`T1`), `plugins/superheroes/lib/tests/test_launch_doctrine.py` (`T2`),
`plugins/superheroes/lib/tests/test_cloud_check.py` (`T3`).
Guarded elements (declared by the order): (G1) the `--disallowedTools` addition in `engine_adapter.claude_cloud_builder_argv`;
(G2) the cloud-only insertion of the standing-permission paragraph in `launcher.compose_launch`; (G3) the text-mismatch refusal in
`launch_doctrine.parse`; (G4) `cloud_check.start`'s opt-out of the disallowed-tools flag.
Each was neutralized by a targeted edit in the production file, the detector run alone as one test node, then restored by the
inverse edit. No test file was edited during the proofs. After all four restores, `git diff f11061ff` over `engine_adapter.py`,
`launcher.py`, `launch_doctrine.py` and `cloud_check.py` is empty.

Every command was run from the repository root as `scripts/pinned-python -B -m pytest <file>::<test> -q -p no:cacheprovider`.
The `UV_NATIVE_TLS` deprecation warning that heads every run is omitted below.

Pinned condition: `T1`'s autouse fixture `_isolated` sets `GIT_CONFIG_GLOBAL=/dev/null` and `GIT_CONFIG_NOSYSTEM=1`, because this
machine's global git config signs every commit through a signer the sandbox cannot reach. What that pin makes unobservable: a
developer's own git configuration (signing, hooks, aliases) acting on the fixture repositories.

## 1. G1: the `--disallowedTools` addition

Axis: a cloud builder's argv carries the question-dialog flag exactly once, with `AskUserQuestion` as its only value, before `-n`.

- Neutralization (`engine_adapter.py:805`, `claude_cloud_builder_argv`): `if disallowed_tools:` became `if False and disallowed_tools:`.
- Node: `T1::test_cloud_argv_starts_with_the_question_dialog_off_once_and_before_the_name`.
- Red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_cloud_argv_starts_with_the_question_dialog_off_once_and_before_the_name _

    def test_cloud_argv_starts_with_the_question_dialog_off_once_and_before_the_name():
        # The flag takes a variadic value, so the tool is its only value and `-n` follows at once.
        argv = EA.claude_cloud_builder_argv("opus", "medium", "p", ENV_ID, "n")["argv"]
>       assert argv.count("--disallowedTools") == 1
E       assert 0 == 1
E        +  where 0 = <built-in method count of list object at 0x7f5e19876300>('--disallowedTools')
E        +    where <built-in method count of list object at 0x7f5e19876300> = ['claude', '--cloud', 'p', '--settings', '{"remote":{"defaultEnvironmentId":"env_01AbCdEf"}}', '--model', ...].count

/home/user/wo-b/plugins/superheroes/lib/tests/test_launcher_cloud.py:224: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher_cloud.py::test_cloud_argv_starts_with_the_question_dialog_off_once_and_before_the_name
1 failed in 0.29s
```

- Restore: the inverse edit; `engine_adapter.py:805-806` read `    if disallowed_tools:` then `        argv += ["--disallowedTools", *disallowed_tools]`.
- Green: `1 passed in 0.19s`.

## 2. G2: the standing-permission paragraph in the cloud prompt

Axis: every cloud prompt carries `CLOUD_LAUNCH_TEXT` exactly once, on its own line, between the base commit and the rulings.

- Neutralization (`launcher.py:1365-1368`, `compose_launch`, cloud branch): the format string lost its `\n\n%s` for the paragraph and `cloud_launch_line,` was dropped from the argument tuple, so the prompt is composed without the paragraph.
- Node: `T1::test_compose_cloud_prompt_carries_the_standing_permission_once_between_base_and_rulings`.
- Red: the last lines of the capture follow. The assertion line and the `where` lines are the test's own; the text is shortened by pytest.

```
>       assert prompt.count(text) == 1
E       AssertionError: assert 0 == 1
FAILED plugins/superheroes/lib/tests/test_launcher_cloud.py::test_compose_cloud_prompt_carries_the_standing_permission_once_between_base_and_rulings
1 failed in 1.89s
```

  (These lines are an excerpt I quote from the full capture, which also held the pytest traceback header, the shortened `where` lines and the `tmp_path` line; the excerpt is labelled for what it is, not the whole output.)
- Restore: the inverse edit; `launcher.py:1365-1368` read `        prompt = "%s\n\nIssue: #%s\n\n%s\n%s\n%s\n%s\n\n%s\n\n%s" % (`, `            _WORKHORSE_CMD, issue, place_line, version_line, environment_line, base_line,`, `            cloud_launch_line, rulings_block,`, `        )`.
- Green: `1 passed in 0.32s`.

## 3. G3: the text-mismatch refusal

Axis: a cloud-launch block whose one line is not `CLOUD_LAUNCH_TEXT` is refused as `doctrine-cloud-launch-text-mismatch`.

- Neutralization (`launch_doctrine.py:260`, `_parse_cloud_launch_block`): `if lines[0] != CLOUD_LAUNCH_TEXT:` became `if False and lines[0] != CLOUD_LAUNCH_TEXT:`.
- Node: `T2::test_doctrine_cloud_launch_text_drift_refuses`.
- Red: the parse accepted the drifted text, so the refusal never appeared.

```
F                                                                        [100%]
=================================== FAILURES ===================================
________________ test_doctrine_cloud_launch_text_drift_refuses _________________

    def test_doctrine_cloud_launch_text_drift_refuses():
        text = _mutate_once(_read_doctrine(), "never a force-push, never `main`.", "never `main`.")
>       _assert_cloud_refusal(text, "doctrine-cloud-launch-text-mismatch")

/home/user/wo-b/plugins/superheroes/lib/tests/test_launch_doctrine.py:136: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

text = "# Launch doctrine\n\nThis document is the standing doctrine for headless builder launches and recovery: the eight rul...unner's\n[wave-watch reference](../skills/showrunner/reference/wave-watch.md#before-treating-lane-stale-as-a-wedge).\n"
reason = 'doctrine-cloud-launch-text-mismatch'

    def _assert_cloud_refusal(text, reason):
        result = LD.parse(text)
>       assert result["ok"] is False
E       assert True is False

/home/user/wo-b/plugins/superheroes/lib/tests/test_launch_doctrine.py:98: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launch_doctrine.py::test_doctrine_cloud_launch_text_drift_refuses
1 failed in 0.12s
```

- Restore: the inverse edit; `launch_doctrine.py:260-261` read `    if lines[0] != CLOUD_LAUNCH_TEXT:` then `        return None, "doctrine-cloud-launch-text-mismatch"`.
- Green: `1 passed in 0.10s`.

## 4. G4: the check session's opt-out of the disallowed-tools flag

Axis: the cloud setup check's launch carries no `--disallowedTools`, because `start` passes `None` for the keyword.

- Neutralization (`cloud_check.py:679-680`, `start`): the `disallowed_tools=None` argument and its comment were removed, so the default `CLOUD_DISALLOWED_TOOLS` applied; the call ended `permission_mode=None)`.
- Node: `T3::test_start_names_the_environment_in_the_launch`.
- Red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
________________ test_start_names_the_environment_in_the_launch ________________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-58/test_start_names_the_environme0')

    def test_start_names_the_environment_in_the_launch(tmp_path):
        local = _build(tmp_path)
        spawner = Spawner()
        result = _start(local, spawner)
        assert result["action"] == "started" and len(spawner.calls) == 1
        argv = spawner.calls[0]["argv"]
        cell = model_registry.resolve_dispatch("mechanical", "claude", None)
>       assert argv == engine_adapter.claude_cloud_builder_argv(
            cell["dispatch_token"], cell["effort"], _prompt(spawner), ENV_ID,
            "cloud-check-" + NONCE[:8], permission_mode=None, disallowed_tools=None)["argv"]
E       AssertionError: assert ['claude', '-...--model', ...] == ['claude', '-...--model', ...]
E         
E         At index 9 diff: '--disallowedTools' != '-n'
E         Left contains 2 more items, first extra item: '-n'
E         Use -v to get more diff

/home/user/wo-b/plugins/superheroes/lib/tests/test_cloud_check.py:1444: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_check.py::test_start_names_the_environment_in_the_launch
1 failed in 0.40s
```

- Restore: the inverse edit; `cloud_check.py:679-680` read `        permission_mode=None,  # the owner's auto-mode ruling covers builders; the check's model may lack it` then `        disallowed_tools=None)  # the question-dialog ruling covers builders; the check asks nothing`.
- Green: `1 passed in 0.35s`.
