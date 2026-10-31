# Bite-proof record: a detective lane can be composed for the cloud (#2230, launch side)

Detectors: `plugins/superheroes/lib/tests/test_launch_doctrine.py` (`T1`), `plugins/superheroes/lib/tests/test_launcher_detective_1097.py` (`T2`).
Guarded elements (declared by the order): (B1) the detective block's presence in `launch_doctrine.parse`; (B2) the detective
invariant check in `launch_doctrine._parse_one_line_block`; (B3) the charter choice in `launcher.compose_launch`; (B4) the detective
absent-line refusal in `launcher.compose_launch`; (B5) the workhorse branch keeping the builder's sentence.
Each was neutralized by a targeted edit in the production file, the detector run alone as one test node, then restored by the
inverse edit. No test file was edited during the proofs.

Every command was run from `<worktree>` as `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-2230 -m pytest <file>::<test> -q -p no:cacheprovider`.
The `UV_NATIVE_TLS` deprecation warning that heads every run is omitted below. Long `where` lines and the `text = ...` fixture dump are
shown as pytest printed them (pytest itself shortens them); nothing else is elided.

## 1. B1: the detective block must be present

Axis: a doctrine with no `cloud-detective` block is refused as `doctrine-missing-block:cloud-detective`, and no result carries `detectiveCloudLine`.

- Neutralization (`launch_doctrine.py:353-354`, `parse`): `return _refuse(reason)` after the detective `_extract_block` became
  `return _ok(rulings, checks, rulings_block, hashlib.sha256(text.encode("utf-8")).hexdigest(), cloud_launch_line, None)`.
- Node: `T1::test_doctrine_missing_detective_cloud_block`.
- Red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
_________________ test_doctrine_missing_detective_cloud_block __________________

    def test_doctrine_missing_detective_cloud_block():
>       _assert_detective_refusal(
            _read_doctrine().replace(_DETECTIVE_BEGIN, ""), "doctrine-missing-block:cloud-detective"
        )

<worktree>/plugins/superheroes/lib/tests/test_launch_doctrine.py:197: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

text = "# Launch doctrine\n\nThis document is the standing doctrine for headless builder launches and recovery: the eight rul...unner's\n[wave-watch reference](../skills/showrunner/reference/wave-watch.md#before-treating-lane-stale-as-a-wedge).\n"
reason = 'doctrine-missing-block:cloud-detective'

    def _assert_detective_refusal(text, reason):
        result = LD.parse(text)
>       assert result["ok"] is False
E       assert True is False

<worktree>/plugins/superheroes/lib/tests/test_launch_doctrine.py:188: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launch_doctrine.py::test_doctrine_missing_detective_cloud_block
1 failed in 3.10s
```

- Restore: the inverse edit.
- Restore receipt (`launch_doctrine.py:352-354`, read back after the restore): `        text, _DETECTIVE_CLOUD_BEGIN, _DETECTIVE_CLOUD_END, "cloud-detective")` / `    if reason is not None:` / `        return _refuse(reason)`.
- Green:

```
.                                                                        [100%]
1 passed in 3.56s
```

## 2. B2: the detective invariant check (class: a phrase missing; representative `push no branch`, covers `cloud_builder.py intake`, `disposable copies live only inside this cloud session` and `push no branch`)

Axis: a detective block whose one line lacks a required phrase is refused as `doctrine-cloud-detective-invariant-missing:<phrase>`.
The three phrases fail the same way (one shared `if phrase not in lines[0]:` in the loop), so one representative stands for the class.
The other two phrases' nodes were not run red.

- Neutralization (`launch_doctrine.py:291`, `_parse_one_line_block`): `if phrase not in lines[0]:` became `if stem != "cloud-detective" and phrase not in lines[0]:`, which disables the check for the detective block only (the same effect as `if False and ...` in the detective path; the cloud-launch block's check is untouched).
- Node: `T1::test_doctrine_detective_cloud_missing_invariant_refuses[push no branch]`.
- Red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
___ test_doctrine_detective_cloud_missing_invariant_refuses[push no branch] ____

phrase = 'push no branch'

    @pytest.mark.parametrize("phrase", LD.DETECTIVE_CLOUD_INVARIANTS)
    def test_doctrine_detective_cloud_missing_invariant_refuses(phrase):
        line = _detective_line()
        assert phrase in line
        text = _mutate_once(_read_doctrine(), line, line.replace(phrase, "nothing at all"))
>       _assert_detective_refusal(text, f"doctrine-cloud-detective-invariant-missing:{phrase}")

<worktree>/plugins/superheroes/lib/tests/test_launch_doctrine.py:225: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

text = "# Launch doctrine\n\nThis document is the standing doctrine for headless builder launches and recovery: the eight rul...unner's\n[wave-watch reference](../skills/showrunner/reference/wave-watch.md#before-treating-lane-stale-as-a-wedge).\n"
reason = 'doctrine-cloud-detective-invariant-missing:push no branch'

    def _assert_detective_refusal(text, reason):
        result = LD.parse(text)
>       assert result["ok"] is False
E       assert True is False

<worktree>/plugins/superheroes/lib/tests/test_launch_doctrine.py:188: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launch_doctrine.py::test_doctrine_detective_cloud_missing_invariant_refuses[push no branch]
1 failed in 5.40s
```

- Restore: the inverse edit.
- Restore receipt (`launch_doctrine.py:291-292`, read back after the restore): `        if phrase not in lines[0]:` / `            return None, f"doctrine-{stem}-invariant-missing:{phrase}"`.
- Green:

```
.                                                                        [100%]
1 passed in 0.23s
```

## 3. B3: the charter choice

Axis: a detective cloud prompt carries the doctrine's detective sentence exactly once and never the builder's push permission.

- Neutralization (`launcher.py:1434`, `compose_launch`, detective branch): `launch_sentence = doctrine.get("detectiveCloudLine")` became `launch_sentence = doctrine.get("cloudLaunchLine")`.
- Node: `T2::test_compose_composes_a_cloud_detective_with_the_detective_sentence`.
- Red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
_____ test_compose_composes_a_cloud_detective_with_the_detective_sentence ______

    def test_compose_composes_a_cloud_detective_with_the_detective_sentence():
        # axis: a cloud detective composes the builder's cloud prompt with its own launch sentence in the builder's place
        detective = _cloud({"baseCommit": SHA, "charter": "detective", "budget": BUDGET})
        workhorse = _cloud({"baseCommit": SHA})
        assert detective["ok"] is True, detective
        assert detective["charter"] == "detective"
        prompt = detective["prompt"]
        assert prompt.startswith(DETECTIVE_HEAD % (1747, BUDGET))
        lines = (
            "Place: cloud session\nAdvisor plugin version: %s\nCloud environment: %s\nBase commit: %s\n\n"
            % (L.plugin_version(), ENV_ID, SHA)
        )
        assert lines in prompt
        assert lines in workhorse["prompt"]
        doctrine = LD.load()
>       assert prompt.count(doctrine["detectiveCloudLine"]) == 1
E       AssertionError: assert 0 == 1
E        +  where 0 = <built-in method count of str object at 0x1068aab0>('Detective in a cloud session: before anything else run `<plugin root>/lib/cloud_builder.py intake` with this launch p...is, and your only writes are the diagnosis receipt and your intake, progress and terminal notes on the incident issue.')
E        +    where <built-in method count of str object at 0x1068aab0> = '/superheroes:detective\n\nIssue: #1747\nBudget: until 18:00 local, no more than 3 hours of builder time\n\nPlace: clo...ermission classifier sees it; staging a gated command in a file and executing the file to dodge the gate is forbidden.'.count

<worktree>/plugins/superheroes/lib/tests/test_launcher_detective_1097.py:177: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher_detective_1097.py::test_compose_composes_a_cloud_detective_with_the_detective_sentence
1 failed in 1.87s
```

- Restore: the inverse edit.
- Restore receipt (`launcher.py:1433-1436`, read back after the restore): `        if charter == "detective":` / `            launch_sentence = doctrine.get("detectiveCloudLine")` / `            if not isinstance(launch_sentence, str) or not launch_sentence.strip():` / `                return _fail("compose-detective-cloud-line-absent")`.
- Green:

```
.                                                                        [100%]
1 passed in 2.36s
```

## 4. B4: the detective absent-line refusal

Axis: a detective cloud compose whose doctrine has no non-blank `detectiveCloudLine` refuses `compose-detective-cloud-line-absent` and composes nothing.

- Neutralization (`launcher.py:1435`, `compose_launch`): `if not isinstance(launch_sentence, str) or not launch_sentence.strip():` became `if False and (not isinstance(launch_sentence, str) or not launch_sentence.strip()):`.
- Node: `T2::test_compose_refuses_a_cloud_detective_when_the_doctrine_has_no_detective_cloud_line`.
- Red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_compose_refuses_a_cloud_detective_when_the_doctrine_has_no_detective_cloud_line _

    def test_compose_refuses_a_cloud_detective_when_the_doctrine_has_no_detective_cloud_line():
        # axis: a cloud detective composes nothing without the doctrine's detective sentence; a builder does not need it
        def without_detective_line():
            return {k: v for k, v in LD.load().items() if k != "detectiveCloudLine"}
    
        def blank_detective_line():
            return dict(LD.load(), detectiveCloudLine="  ")
    
        def without_builder_line():
            return {k: v for k, v in LD.load().items() if k != "cloudLaunchLine"}
    
        premise = {"baseCommit": SHA, "charter": "detective", "budget": BUDGET}
        for loader in (without_detective_line, blank_detective_line):
            refused = L.compose_launch(
                ".", 1747, premise, model="opus", place="cloud", cloud_environment=ENV_ID,
                session_name="issue-1747-probe", doctrine_loader=loader)
>           assert refused["ok"] is False
E           assert True is False

<worktree>/plugins/superheroes/lib/tests/test_launcher_detective_1097.py:208: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher_detective_1097.py::test_compose_refuses_a_cloud_detective_when_the_doctrine_has_no_detective_cloud_line
1 failed in 1.80s
```

  (The red capture shows the blank-value loader literal as it stood at the run, two spaces; the test was afterwards changed to a one-space blank value, `" "`, to keep the stray-double-space check clean. Both are blank strings and fail the same `.strip()` check.)
- Restore: the inverse edit.
- Restore receipt (`launcher.py:1435-1436`, read back after the restore): `            if not isinstance(launch_sentence, str) or not launch_sentence.strip():` / `                return _fail("compose-detective-cloud-line-absent")`.
- Green:

```
.                                                                        [100%]
1 passed in 2.27s
```

## 5. B5: the workhorse sentence is not swapped

Axis: a workhorse cloud prompt carries the builder's push permission exactly once and never the detective sentence.

- Neutralization (`launcher.py:1438`, `compose_launch`, workhorse branch): `launch_sentence = doctrine.get("cloudLaunchLine")` became `launch_sentence = doctrine.get("detectiveCloudLine")`.
- Node: `T2::test_a_workhorse_cloud_prompt_carries_the_builder_sentence_and_not_the_detective_one`.
- Red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_workhorse_cloud_prompt_carries_the_builder_sentence_and_not_the_detective_one _

    def test_a_workhorse_cloud_prompt_carries_the_builder_sentence_and_not_the_detective_one():
        # axis: the workhorse branch keeps the builder's push permission and never takes the detective sentence
        workhorse = _cloud({"baseCommit": SHA})
        assert workhorse["ok"] is True, workhorse
        doctrine = LD.load()
>       assert workhorse["prompt"].count(doctrine["cloudLaunchLine"]) == 1
E       AssertionError: assert 0 == 1
E        +  where 0 = <built-in method count of str object at 0x2b227630>('Standing permission from the owner: push to your own build branch (the one you create at intake, or the branch the la...order gives this session to build; never to a branch the order names only as a base, never a force-push, never `main`.')
E        +    where <built-in method count of str object at 0x2b227630> = '/superheroes:workhorse\n\nIssue: #1747\n\nPlace: cloud session\nAdvisor plugin version: 0.46.2\nCloud environment: en...ermission classifier sees it; staging a gated command in a file and executing the file to dodge the gate is forbidden.'.count

<worktree>/plugins/superheroes/lib/tests/test_launcher_detective_1097.py:188: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher_detective_1097.py::test_a_workhorse_cloud_prompt_carries_the_builder_sentence_and_not_the_detective_one
1 failed in 1.97s
```

- Restore: the inverse edit.
- Restore receipt (`launcher.py:1437-1440`, read back after the restore): `        else:` / `            launch_sentence = doctrine.get("cloudLaunchLine")` / `            if not isinstance(launch_sentence, str) or not launch_sentence.strip():` / `                return _fail("compose-cloud-launch-line-absent")`.
- Green:

```
.                                                                        [100%]
1 passed in 1.84s
```
