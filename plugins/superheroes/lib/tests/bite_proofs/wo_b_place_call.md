# Place call WO-B bite-proof: the routing step in the launch path and the local fallback

> Note (2026-10-31, #2296): owner-machine paths and the name of a consuming project in this record were replaced with neutral placeholders after capture; nothing else changed.

Bite-proof record for `plugins/superheroes/lib/launcher.py` (`_cli_launch` and `validate_premise`, B1 to B9), detectors in `plugins/superheroes/lib/tests/test_launcher_place.py` (`TP`).

**Status.** The implementer ran every proof (B1 to B9): each neutralization is a targeted Edit in `launcher.py`, the red is the single named test function run alone, the restore is the inverse Edit, and the green is the same function. Reds and greens below are the pytest output of each run; the absolute `tmp_path` prefixes and the worktree path are as printed. No fixture holds a real secret, so nothing is redacted.

- **Run command.** `scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest "<T>::<node>" -q`.
- **Restore receipt, every element.** The restored line is quoted back from `launcher.py` after the inverse Edit, and a closing run of `test_launcher_place.py`, `test_launcher_cloud.py` and `test_launcher.py` with every neutralization undone finished `1 failed, 623 passed, 13 skipped`. The one failure is `test_launcher_cloud.py::test_cli_launch_forwards_place_and_environment_only_when_a_place_is_given`, a test from before this order that asserts the CLI forwards `--place` and `--cloud-environment` as given (the behavior invariants I1 and I5 replace); it is not named by this order, was not edited, and is reported to the orchestrator. The 13 skips are the real-pty variants of the `terminal` fixture, which skip where no pseudo-terminal can be opened.
- **Function-level nodes.** B3 and B4 are parametrized functions; their eight and eleven cases run together. The other seven nodes are plain functions.
- **Pinned condition.** `TP` builds its repository, remote, ledger root, worktree root, store, account file and setup record under `tmp_path`; readiness is given a fixed `today` (`2026-10-11`), a fixed advisor version and a fixed calibration stamp, and the needs reader looks only at the premise; the platform command and the owner's machine are stand-ins injected through the launcher's default spawn functions. The pin makes unobservable: the real home directory, the process environment's account, the real platform command, the network and the real wall clock.

## Declared guarded-element set

B1 the CLI calls `route` (I1); B2 the CLI refuses a caller-set `placeCall` (E1); B3 the `needs` validation (E2); B4 the `reportedCloud` validation (E3); B5 fallback only on the two exact reasons, `cloud-session-unconfirmed` the representative of the no-fallback class (E7, and E8 to E10 by the same condition); B6 no slot is passed to the cloud call (I4); B7 the environment comes from the placeCall (I5); B8 the `--cloud-environment` refusal on `launch` (E4); B9 the fallback stamps `unreachable` (E5).

Not neutralized, and so unproven by a run in this record: the second exact reason (`log-open-failed`, E6) is covered by `TP::test_a_log_that_cannot_be_opened_runs_the_build_locally_the_same_way` but has no neutralization of its own, because B5's condition is one expression over both reasons; the `fallbackResourcesUnused` key for a refused cloud result; the unconfirmed-lane count inside `TP::test_n_launches_give_n_lanes_and_the_batch_counts_them`.

### B1: every launch through the CLI is routed once, before it starts. Axis: presence of the call (invariant I1)

- **Neutralization applied.** In `launcher._cli_launch`, `place_call = launch_place.route(` replaced with `place_call = (lambda *a: launch_place._placement("local", False, None, None, None, None, None, None, None))(`, so the routing step is never consulted and every build is placed locally.
- **Node.** `TP::test_five_launches_put_the_three_that_need_nothing_in_the_cloud`
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_______ test_five_launches_put_the_three_that_need_nothing_in_the_cloud ________

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1148/test_five_launches_put_the_thr0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x10946f7a0>
capsys = <_pytest.capture.CaptureFixture object at 0x10946f710>
machine = <test_launcher_place._Machine object at 0x10946dd90>

    def test_five_launches_put_the_three_that_need_nothing_in_the_cloud(
        tmp_path, monkeypatch, capsys, machine,
    ):
        world = _world(tmp_path, monkeypatch)
        cloud_calls = _cloud(monkeypatch)
        ll.declare_batch(world.repo, BATCH, 5)
        results = {}
        for issue in (201, 202, 203):
            code, results[issue] = _launch(world, capsys, issue)
            assert code == 0, results[issue]
        for issue in (204, 205):
            code, results[issue] = _launch(world, capsys, issue, needs=["a signed-in browser"])
            assert code == 0, results[issue]

>       assert len(cloud_calls) == 3 and len(machine.calls) == 2
E       assert (0 == 3)
E        +  where 0 = len([])

/path/to/home/.superheroes-worktrees/superheroes/issue-1746-9ec121c90cfeb086/plugins/superheroes/lib/tests/test_launcher_place.py:234: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher_place.py::test_five_launches_put_the_three_that_need_nothing_in_the_cloud
1 failed in 9.71s
```

- **Restore.** The inverse Edit; quoted from launcher.py:3280: `    place_call = launch_place.route(`
- **Green.**

```
.                                                                        [100%]
1 passed in 8.87s
```

### B2: a premise file that already carries a `placeCall` is refused (E1). Axis: refusal of a caller-set routing word

- **Neutralization applied.** In `_cli_launch`, `if isinstance(premise, dict) and "placeCall" in premise:` replaced with `if False and isinstance(premise, dict) and "placeCall" in premise:`.
- **Node.** `TP::test_a_premise_file_that_already_carries_a_place_call_is_refused`
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_______ test_a_premise_file_that_already_carries_a_place_call_is_refused _______

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1150/test_a_premise_file_that_alrea0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x108d7e3f0>
capsys = <_pytest.capture.CaptureFixture object at 0x108d7e9c0>
machine = <test_launcher_place._Machine object at 0x108d7c530>

    def test_a_premise_file_that_already_carries_a_place_call_is_refused(
        tmp_path, monkeypatch, capsys, machine,
    ):
        world = _world(tmp_path, monkeypatch)
        cloud_calls = _cloud(monkeypatch)
        premise = _valid_premise(world.repo, issue=371, batchId=BATCH)
        premise["placeCall"] = {"place": "cloud", "environment": ENV_ID}
        code, result = _launch(world, capsys, 371, premise=premise)

>       assert code == 1
E       assert 0 == 1

/path/to/home/.superheroes-worktrees/superheroes/issue-1746-9ec121c90cfeb086/plugins/superheroes/lib/tests/test_launcher_place.py:631: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher_place.py::test_a_premise_file_that_already_carries_a_place_call_is_refused
1 failed in 5.18s
```

- **Restore.** The inverse Edit; quoted from launcher.py:3273: `    if isinstance(premise, dict) and "placeCall" in premise:`
- **Green.**

```
.                                                                        [100%]
1 passed in 1.86s
```

### B3: `validate_premise` refuses a `needs` that is not a list of non-empty strings (E2). Axis: shape validation

- **Neutralization applied.** In `launcher.validate_premise`, `if "needs" in premise:` replaced with `if False and "needs" in premise:`. The first red run was piped through `tail -60` by the implementer, which cut its first lines; it was re-run with the neutralization still in place and written whole to a file, and only that complete run is quoted.
- **Node.** `TP::test_a_needs_field_that_is_not_a_list_of_names_is_refused`
- **Red:**

```
FFFFFFFF                                                                 [100%]
=================================== FAILURES ===================================
_ test_a_needs_field_that_is_not_a_list_of_names_is_refused[a signed-in browser] _

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1153/test_a_needs_field_that_is_not0')
needs = 'a signed-in browser'

    @pytest.mark.parametrize("needs", _NEEDS_INVALID)
    def test_a_needs_field_that_is_not_a_list_of_names_is_refused(tmp_path, needs):
        repo = _init_repo(tmp_path / "repo")
        result = L.validate_premise(_valid_premise(repo, needs=needs), repo)
>       assert result["ok"] is False
E       assert True is False

/path/to/home/.superheroes-worktrees/superheroes/issue-1746-9ec121c90cfeb086/plugins/superheroes/lib/tests/test_launcher_place.py:644: AssertionError
_________ test_a_needs_field_that_is_not_a_list_of_names_is_refused[7] _________

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1153/test_a_needs_field_that_is_not1')
needs = 7

    @pytest.mark.parametrize("needs", _NEEDS_INVALID)
    def test_a_needs_field_that_is_not_a_list_of_names_is_refused(tmp_path, needs):
        repo = _init_repo(tmp_path / "repo")
        result = L.validate_premise(_valid_premise(repo, needs=needs), repo)
>       assert result["ok"] is False
E       assert True is False

/path/to/home/.superheroes-worktrees/superheroes/issue-1746-9ec121c90cfeb086/plugins/superheroes/lib/tests/test_launcher_place.py:644: AssertionError
_______ test_a_needs_field_that_is_not_a_list_of_names_is_refused[None] ________

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1153/test_a_needs_field_that_is_not2')
needs = None

    @pytest.mark.parametrize("needs", _NEEDS_INVALID)
    def test_a_needs_field_that_is_not_a_list_of_names_is_refused(tmp_path, needs):
        repo = _init_repo(tmp_path / "repo")
        result = L.validate_premise(_valid_premise(repo, needs=needs), repo)
>       assert result["ok"] is False
E       assert True is False

/path/to/home/.superheroes-worktrees/superheroes/issue-1746-9ec121c90cfeb086/plugins/superheroes/lib/tests/test_launcher_place.py:644: AssertionError
______ test_a_needs_field_that_is_not_a_list_of_names_is_refused[needs3] _______

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1153/test_a_needs_field_that_is_not3')
needs = {'a': 1}

    @pytest.mark.parametrize("needs", _NEEDS_INVALID)
    def test_a_needs_field_that_is_not_a_list_of_names_is_refused(tmp_path, needs):
        repo = _init_repo(tmp_path / "repo")
        result = L.validate_premise(_valid_premise(repo, needs=needs), repo)
>       assert result["ok"] is False
E       assert True is False

/path/to/home/.superheroes-worktrees/superheroes/issue-1746-9ec121c90cfeb086/plugins/superheroes/lib/tests/test_launcher_place.py:644: AssertionError
______ test_a_needs_field_that_is_not_a_list_of_names_is_refused[needs4] _______

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1153/test_a_needs_field_that_is_not4')
needs = [1]

    @pytest.mark.parametrize("needs", _NEEDS_INVALID)
    def test_a_needs_field_that_is_not_a_list_of_names_is_refused(tmp_path, needs):
        repo = _init_repo(tmp_path / "repo")
        result = L.validate_premise(_valid_premise(repo, needs=needs), repo)
>       assert result["ok"] is False
E       assert True is False

/path/to/home/.superheroes-worktrees/superheroes/issue-1746-9ec121c90cfeb086/plugins/superheroes/lib/tests/test_launcher_place.py:644: AssertionError
______ test_a_needs_field_that_is_not_a_list_of_names_is_refused[needs5] _______

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1153/test_a_needs_field_that_is_not5')
needs = ['']

    @pytest.mark.parametrize("needs", _NEEDS_INVALID)
    def test_a_needs_field_that_is_not_a_list_of_names_is_refused(tmp_path, needs):
        repo = _init_repo(tmp_path / "repo")
        result = L.validate_premise(_valid_premise(repo, needs=needs), repo)
>       assert result["ok"] is False
E       assert True is False

/path/to/home/.superheroes-worktrees/superheroes/issue-1746-9ec121c90cfeb086/plugins/superheroes/lib/tests/test_launcher_place.py:644: AssertionError
______ test_a_needs_field_that_is_not_a_list_of_names_is_refused[needs6] _______

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1153/test_a_needs_field_that_is_not6')
needs = ['  ']

    @pytest.mark.parametrize("needs", _NEEDS_INVALID)
    def test_a_needs_field_that_is_not_a_list_of_names_is_refused(tmp_path, needs):
        repo = _init_repo(tmp_path / "repo")
        result = L.validate_premise(_valid_premise(repo, needs=needs), repo)
>       assert result["ok"] is False
E       assert True is False

/path/to/home/.superheroes-worktrees/superheroes/issue-1746-9ec121c90cfeb086/plugins/superheroes/lib/tests/test_launcher_place.py:644: AssertionError
______ test_a_needs_field_that_is_not_a_list_of_names_is_refused[needs7] _______

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1153/test_a_needs_field_that_is_not7')
needs = ['ok', None]

    @pytest.mark.parametrize("needs", _NEEDS_INVALID)
    def test_a_needs_field_that_is_not_a_list_of_names_is_refused(tmp_path, needs):
        repo = _init_repo(tmp_path / "repo")
        result = L.validate_premise(_valid_premise(repo, needs=needs), repo)
>       assert result["ok"] is False
E       assert True is False

/path/to/home/.superheroes-worktrees/superheroes/issue-1746-9ec121c90cfeb086/plugins/superheroes/lib/tests/test_launcher_place.py:644: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher_place.py::test_a_needs_field_that_is_not_a_list_of_names_is_refused[a signed-in browser]
FAILED plugins/superheroes/lib/tests/test_launcher_place.py::test_a_needs_field_that_is_not_a_list_of_names_is_refused[7]
FAILED plugins/superheroes/lib/tests/test_launcher_place.py::test_a_needs_field_that_is_not_a_list_of_names_is_refused[None]
FAILED plugins/superheroes/lib/tests/test_launcher_place.py::test_a_needs_field_that_is_not_a_list_of_names_is_refused[needs3]
FAILED plugins/superheroes/lib/tests/test_launcher_place.py::test_a_needs_field_that_is_not_a_list_of_names_is_refused[needs4]
FAILED plugins/superheroes/lib/tests/test_launcher_place.py::test_a_needs_field_that_is_not_a_list_of_names_is_refused[needs5]
FAILED plugins/superheroes/lib/tests/test_launcher_place.py::test_a_needs_field_that_is_not_a_list_of_names_is_refused[needs6]
FAILED plugins/superheroes/lib/tests/test_launcher_place.py::test_a_needs_field_that_is_not_a_list_of_names_is_refused[needs7]
8 failed in 1.18s
```

- **Restore.** The inverse Edit; quoted from launcher.py:1195: `    if "needs" in premise:`
- **Green.**

```
........                                                                 [100%]
8 passed in 1.09s
```

### B4: `validate_premise` refuses a `reportedCloud` in an unknown shape (E3). Axis: shape validation

- **Neutralization applied.** In `launcher.validate_premise`, `if "reportedCloud" in premise:` replaced with `if False and "reportedCloud" in premise:`.
- **Node.** `TP::test_a_reported_cloud_in_an_unknown_shape_is_refused`
- **Red:**

```
FFFFFFFFFFF                                                              [100%]
=================================== FAILURES ===================================
_______ test_a_reported_cloud_in_an_unknown_shape_is_refused[reported0] ________

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1155/test_a_reported_cloud_in_an_un0')
reported = []

    @pytest.mark.parametrize("reported", _REPORTED_INVALID)
    def test_a_reported_cloud_in_an_unknown_shape_is_refused(tmp_path, reported):
        repo = _init_repo(tmp_path / "repo")
        result = L.validate_premise(_valid_premise(repo, reportedCloud=reported), repo)
>       assert result["ok"] is False
E       assert True is False

/path/to/home/.superheroes-worktrees/superheroes/issue-1746-9ec121c90cfeb086/plugins/superheroes/lib/tests/test_launcher_place.py:667: AssertionError
___________ test_a_reported_cloud_in_an_unknown_shape_is_refused[x] ____________

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1155/test_a_reported_cloud_in_an_un1')
reported = 'x'

    @pytest.mark.parametrize("reported", _REPORTED_INVALID)
    def test_a_reported_cloud_in_an_unknown_shape_is_refused(tmp_path, reported):
        repo = _init_repo(tmp_path / "repo")
        result = L.validate_premise(_valid_premise(repo, reportedCloud=reported), repo)
>       assert result["ok"] is False
E       assert True is False

/path/to/home/.superheroes-worktrees/superheroes/issue-1746-9ec121c90cfeb086/plugins/superheroes/lib/tests/test_launcher_place.py:667: AssertionError
___________ test_a_reported_cloud_in_an_unknown_shape_is_refused[1] ____________

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1155/test_a_reported_cloud_in_an_un2')
reported = 1

    @pytest.mark.parametrize("reported", _REPORTED_INVALID)
    def test_a_reported_cloud_in_an_unknown_shape_is_refused(tmp_path, reported):
        repo = _init_repo(tmp_path / "repo")
        result = L.validate_premise(_valid_premise(repo, reportedCloud=reported), repo)
>       assert result["ok"] is False
E       assert True is False

/path/to/home/.superheroes-worktrees/superheroes/issue-1746-9ec121c90cfeb086/plugins/superheroes/lib/tests/test_launcher_place.py:667: AssertionError
__________ test_a_reported_cloud_in_an_unknown_shape_is_refused[True] __________

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1155/test_a_reported_cloud_in_an_un3')
reported = True

    @pytest.mark.parametrize("reported", _REPORTED_INVALID)
    def test_a_reported_cloud_in_an_unknown_shape_is_refused(tmp_path, reported):
        repo = _init_repo(tmp_path / "repo")
        result = L.validate_premise(_valid_premise(repo, reportedCloud=reported), repo)
>       assert result["ok"] is False
E       assert True is False

/path/to/home/.superheroes-worktrees/superheroes/issue-1746-9ec121c90cfeb086/plugins/superheroes/lib/tests/test_launcher_place.py:667: AssertionError
_______ test_a_reported_cloud_in_an_unknown_shape_is_refused[reported4] ________

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1155/test_a_reported_cloud_in_an_un4')
reported = {'other': True}

    @pytest.mark.parametrize("reported", _REPORTED_INVALID)
    def test_a_reported_cloud_in_an_unknown_shape_is_refused(tmp_path, reported):
        repo = _init_repo(tmp_path / "repo")
        result = L.validate_premise(_valid_premise(repo, reportedCloud=reported), repo)
>       assert result["ok"] is False
E       assert True is False

/path/to/home/.superheroes-worktrees/superheroes/issue-1746-9ec121c90cfeb086/plugins/superheroes/lib/tests/test_launcher_place.py:667: AssertionError
_______ test_a_reported_cloud_in_an_unknown_shape_is_refused[reported5] ________

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1155/test_a_reported_cloud_in_an_un5')
reported = {'noPass': False}

    @pytest.mark.parametrize("reported", _REPORTED_INVALID)
    def test_a_reported_cloud_in_an_unknown_shape_is_refused(tmp_path, reported):
        repo = _init_repo(tmp_path / "repo")
        result = L.validate_premise(_valid_premise(repo, reportedCloud=reported), repo)
>       assert result["ok"] is False
E       assert True is False

/path/to/home/.superheroes-worktrees/superheroes/issue-1746-9ec121c90cfeb086/plugins/superheroes/lib/tests/test_launcher_place.py:667: AssertionError
_______ test_a_reported_cloud_in_an_unknown_shape_is_refused[reported6] ________

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1155/test_a_reported_cloud_in_an_un6')
reported = {'unreachable': 1}

    @pytest.mark.parametrize("reported", _REPORTED_INVALID)
    def test_a_reported_cloud_in_an_unknown_shape_is_refused(tmp_path, reported):
        repo = _init_repo(tmp_path / "repo")
        result = L.validate_premise(_valid_premise(repo, reportedCloud=reported), repo)
>       assert result["ok"] is False
E       assert True is False

/path/to/home/.superheroes-worktrees/superheroes/issue-1746-9ec121c90cfeb086/plugins/superheroes/lib/tests/test_launcher_place.py:667: AssertionError
_______ test_a_reported_cloud_in_an_unknown_shape_is_refused[reported7] ________

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1155/test_a_reported_cloud_in_an_un7')
reported = {'pluginVersion': 41}

    @pytest.mark.parametrize("reported", _REPORTED_INVALID)
    def test_a_reported_cloud_in_an_unknown_shape_is_refused(tmp_path, reported):
        repo = _init_repo(tmp_path / "repo")
        result = L.validate_premise(_valid_premise(repo, reportedCloud=reported), repo)
>       assert result["ok"] is False
E       assert True is False

/path/to/home/.superheroes-worktrees/superheroes/issue-1746-9ec121c90cfeb086/plugins/superheroes/lib/tests/test_launcher_place.py:667: AssertionError
_______ test_a_reported_cloud_in_an_unknown_shape_is_refused[reported8] ________

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1155/test_a_reported_cloud_in_an_un8')
reported = {'pluginVersion': '0.41'}

    @pytest.mark.parametrize("reported", _REPORTED_INVALID)
    def test_a_reported_cloud_in_an_unknown_shape_is_refused(tmp_path, reported):
        repo = _init_repo(tmp_path / "repo")
        result = L.validate_premise(_valid_premise(repo, reportedCloud=reported), repo)
>       assert result["ok"] is False
E       assert True is False

/path/to/home/.superheroes-worktrees/superheroes/issue-1746-9ec121c90cfeb086/plugins/superheroes/lib/tests/test_launcher_place.py:667: AssertionError
_______ test_a_reported_cloud_in_an_unknown_shape_is_refused[reported9] ________

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1155/test_a_reported_cloud_in_an_un9')
reported = {'pluginVersion': 'v0.41.0'}

    @pytest.mark.parametrize("reported", _REPORTED_INVALID)
    def test_a_reported_cloud_in_an_unknown_shape_is_refused(tmp_path, reported):
        repo = _init_repo(tmp_path / "repo")
        result = L.validate_premise(_valid_premise(repo, reportedCloud=reported), repo)
>       assert result["ok"] is False
E       assert True is False

/path/to/home/.superheroes-worktrees/superheroes/issue-1746-9ec121c90cfeb086/plugins/superheroes/lib/tests/test_launcher_place.py:667: AssertionError
_______ test_a_reported_cloud_in_an_unknown_shape_is_refused[reported10] _______

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1155/test_a_reported_cloud_in_an_un10')
reported = {'noPass': True, 'extra': 1}

    @pytest.mark.parametrize("reported", _REPORTED_INVALID)
    def test_a_reported_cloud_in_an_unknown_shape_is_refused(tmp_path, reported):
        repo = _init_repo(tmp_path / "repo")
        result = L.validate_premise(_valid_premise(repo, reportedCloud=reported), repo)
>       assert result["ok"] is False
E       assert True is False

/path/to/home/.superheroes-worktrees/superheroes/issue-1746-9ec121c90cfeb086/plugins/superheroes/lib/tests/test_launcher_place.py:667: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher_place.py::test_a_reported_cloud_in_an_unknown_shape_is_refused[reported0]
FAILED plugins/superheroes/lib/tests/test_launcher_place.py::test_a_reported_cloud_in_an_unknown_shape_is_refused[x]
FAILED plugins/superheroes/lib/tests/test_launcher_place.py::test_a_reported_cloud_in_an_unknown_shape_is_refused[1]
FAILED plugins/superheroes/lib/tests/test_launcher_place.py::test_a_reported_cloud_in_an_unknown_shape_is_refused[True]
FAILED plugins/superheroes/lib/tests/test_launcher_place.py::test_a_reported_cloud_in_an_unknown_shape_is_refused[reported4]
FAILED plugins/superheroes/lib/tests/test_launcher_place.py::test_a_reported_cloud_in_an_unknown_shape_is_refused[reported5]
FAILED plugins/superheroes/lib/tests/test_launcher_place.py::test_a_reported_cloud_in_an_unknown_shape_is_refused[reported6]
FAILED plugins/superheroes/lib/tests/test_launcher_place.py::test_a_reported_cloud_in_an_unknown_shape_is_refused[reported7]
FAILED plugins/superheroes/lib/tests/test_launcher_place.py::test_a_reported_cloud_in_an_unknown_shape_is_refused[reported8]
FAILED plugins/superheroes/lib/tests/test_launcher_place.py::test_a_reported_cloud_in_an_unknown_shape_is_refused[reported9]
FAILED plugins/superheroes/lib/tests/test_launcher_place.py::test_a_reported_cloud_in_an_unknown_shape_is_refused[reported10]
11 failed in 1.38s
```

- **Restore.** The inverse Edit; quoted from launcher.py:1203: `    if "reportedCloud" in premise:`
- **Green.**

```
...........                                                              [100%]
11 passed in 1.29s
```

### B5: fall back only on the two exact reasons, with `cloud-session-unconfirmed` the representative of the no-fallback class (E7; E8, E9 and E10 are the same class). Axis: exact-match of the fallback condition

- **Neutralization applied.** In `_cli_launch`, `if not result.get("ok") and result.get("reason") in _CLOUD_NEVER_STARTED_REASONS:` replaced with `if not result.get("ok"):`. The first red run failed on the reason assertion (the local relaunch was refused by the ledger for a surface overlap with the live cloud lane); the test was then reordered so its first assertion is the absence of `fellBack`, and the red was re-run with the neutralization still in place. Only the second red is quoted.
- **Node.** `TP::test_cloud_session_unconfirmed_makes_no_local_launch`
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_____________ test_cloud_session_unconfirmed_makes_no_local_launch _____________

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1158/test_cloud_session_unconfirmed0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x10959c890>
capsys = <_pytest.capture.CaptureFixture object at 0x10959ca70>
machine = <test_launcher_place._Machine object at 0x10959c5c0>

    def test_cloud_session_unconfirmed_makes_no_local_launch(
        tmp_path, monkeypatch, capsys, machine,
    ):
        world = _world(tmp_path, monkeypatch)
        cloud_calls = _cloud(monkeypatch, result=_spawned("the command printed no receipt"))
        code, result = _launch(world, capsys, 271)
    
>       assert "fellBack" not in result and "cloudAttempt" not in result
E       AssertionError: assert ('fellBack' not in {'ok': False, 'reason': 'surface-overlap:launch-7f67302c5d4a1bf2', 'launchId': 'launch-2af9c2d68a8702e5', 'placeCall': {'place': 'local', 'pointedAtCloud': True, 'by': 'setting', 'reason': 'unreachable', ...}, ...})

/path/to/home/.superheroes-worktrees/superheroes/issue-1746-9ec121c90cfeb086/plugins/superheroes/lib/tests/test_launcher_place.py:423: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher_place.py::test_cloud_session_unconfirmed_makes_no_local_launch
1 failed in 9.64s
```

- **Restore.** The inverse Edit; quoted from launcher.py:3314: `    if not result.get("ok") and result.get("reason") in _CLOUD_NEVER_STARTED_REASONS:`
- **Green.**

```
.                                                                        [100%]
1 passed in 3.18s
```

### B6: no slot, generation or boundary is passed to the cloud call (I4). Axis: absence of fallback resources in the cloud call

- **Neutralization applied.** In `_cli_launch`, the cloud `launch(...)` call given two more arguments, `slot=args.slot, generation=args.generation,`.
- **Node.** `TP::test_a_cloud_launch_gets_no_slot_and_the_unused_resources_are_handed_back`
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
__ test_a_cloud_launch_gets_no_slot_and_the_unused_resources_are_handed_back ___

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1160/test_a_cloud_launch_gets_no_sl0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x10adf4b90>
capsys = <_pytest.capture.CaptureFixture object at 0x10adf5220>
machine = <test_launcher_place._Machine object at 0x10adf6570>

    def test_a_cloud_launch_gets_no_slot_and_the_unused_resources_are_handed_back(
        tmp_path, monkeypatch, capsys, machine,
    ):
        world = _world(tmp_path, monkeypatch)
        cloud_calls = _cloud(monkeypatch)
        _slot_calibrated(monkeypatch)
        ll.declare_batch(world.repo, BATCH, 2)
        code, result = _launch(world, capsys, 331, "--slot", "slot-a", "--generation", "1")
    
>       assert code == 0, result
E       AssertionError: {'ok': False, 'reason': 'launch-cloud-with-slot', 'launchId': 'launch-8337d7c91dbdb7d5', 'placeCall': {'place': 'cloud', 'pointedAtCloud': True, 'by': 'setting', 'reason': None, ...}, ...}
E       assert 1 == 0

/path/to/home/.superheroes-worktrees/superheroes/issue-1746-9ec121c90cfeb086/plugins/superheroes/lib/tests/test_launcher_place.py:559: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher_place.py::test_a_cloud_launch_gets_no_slot_and_the_unused_resources_are_handed_back
1 failed in 3.72s
```

- **Restore.** The inverse Edit; quoted from launcher.py:3311: `        place_call, place=PLACE_CLOUD, cloud_environment=place_call["environment"],` followed by `    )`
- **Green.**

```
.                                                                        [100%]
1 passed in 10.37s
```

### B7: the cloud environment comes from the placeCall (I5). Axis: source of the environment

- **Neutralization applied.** In `_cli_launch`, `cloud_environment=place_call["environment"],` replaced with `cloud_environment=getattr(args, "cloud_environment", None),`.
- **Node.** `TP::test_the_cloud_environment_comes_from_the_setup_record`
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
____________ test_the_cloud_environment_comes_from_the_setup_record ____________

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1162/test_the_cloud_environment_com0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x10746ef90>
capsys = <_pytest.capture.CaptureFixture object at 0x10746f0b0>
machine = <test_launcher_place._Machine object at 0x10746f140>

    def test_the_cloud_environment_comes_from_the_setup_record(
        tmp_path, monkeypatch, capsys, machine,
    ):
        recorded = "env_01RecordedOne"
        world = _world(tmp_path, monkeypatch, environment=recorded)
        cloud_calls = _cloud(monkeypatch)
        code, result = _launch(world, capsys, 351)
    
>       assert code == 0, result
E       AssertionError: {'ok': False, 'reason': 'launch-cloud-environment-invalid', 'launchId': 'launch-ff5e35a1f829f326', 'placeCall': {'place': 'cloud', 'pointedAtCloud': True, 'by': 'setting', 'reason': None, ...}}
E       assert 1 == 0

/path/to/home/.superheroes-worktrees/superheroes/issue-1746-9ec121c90cfeb086/plugins/superheroes/lib/tests/test_launcher_place.py:600: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher_place.py::test_the_cloud_environment_comes_from_the_setup_record
1 failed in 2.10s
```

- **Restore.** The inverse Edit; quoted from launcher.py:3311: `        place_call, place=PLACE_CLOUD, cloud_environment=place_call["environment"],`
- **Green.**

```
.                                                                        [100%]
1 passed in 3.54s
```

### B8: `--cloud-environment` is refused on `launch` (E4). Axis: refusal

- **Neutralization applied.** In `_cli_launch`, `if getattr(args, "cloud_environment", None) is not None:` replaced with `if False and getattr(args, "cloud_environment", None) is not None:`.
- **Node.** `TP::test_a_cloud_environment_flag_on_launch_is_refused_before_anything_is_decided`
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_cloud_environment_flag_on_launch_is_refused_before_anything_is_decided _

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1164/test_a_cloud_environment_flag_0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x106902ba0>
capsys = <_pytest.capture.CaptureFixture object at 0x106902ed0>
machine = <test_launcher_place._Machine object at 0x106902c60>

    def test_a_cloud_environment_flag_on_launch_is_refused_before_anything_is_decided(
        tmp_path, monkeypatch, capsys, machine,
    ):
        world = _world(tmp_path, monkeypatch)
        cloud_calls = _cloud(monkeypatch)
        code, result = _launch(world, capsys, 361, "--cloud-environment", ENV_ID)
    
>       assert code == 1
E       assert 0 == 1

/path/to/home/.superheroes-worktrees/superheroes/issue-1746-9ec121c90cfeb086/plugins/superheroes/lib/tests/test_launcher_place.py:613: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher_place.py::test_a_cloud_environment_flag_on_launch_is_refused_before_anything_is_decided
1 failed in 6.44s
```

- **Restore.** The inverse Edit; quoted from launcher.py:3276-3277: `    if getattr(args, "cloud_environment", None) is not None:` / `        return _fail("launch-cloud-environment-routed")`
- **Green.**

```
.                                                                        [100%]
1 passed in 6.07s
```

### B9: the fallback stamps `unreachable` (E5). Axis: the reason on the fallback placeCall

- **Neutralization applied.** In `_cli_launch`, `reason="unreachable"` in the `fallback_call` copy replaced with `reason=None`.
- **Node.** `TP::test_a_cloud_spawn_failure_runs_the_build_locally_and_says_unreachable`
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
____ test_a_cloud_spawn_failure_runs_the_build_locally_and_says_unreachable ____

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1166/test_a_cloud_spawn_failure_run0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x106c0c140>
capsys = <_pytest.capture.CaptureFixture object at 0x106c0c260>
machine = <test_launcher_place._Machine object at 0x106c0d070>

    def test_a_cloud_spawn_failure_runs_the_build_locally_and_says_unreachable(
        tmp_path, monkeypatch, capsys, machine,
    ):
        world = _world(tmp_path, monkeypatch)
        cloud_calls = _cloud(monkeypatch, raises=OSError("no platform"))
        ll.declare_batch(world.repo, BATCH, 1)
        code, result = _launch(world, capsys, 231)
    
        assert code == 0, result
        assert result["ok"] is True and result["fellBack"] is True
        assert len(cloud_calls) == 1 and len(machine.calls) == 1
        call = result["placeCall"]
>       assert (call["place"], call["reason"], call["environment"]) == ("local", "unreachable", None)
E       AssertionError: assert ('local', None, None) == ('local', 'unreachable', None)
E         
E         At index 1 diff: None != 'unreachable'
E         Use -v to get more diff

/path/to/home/.superheroes-worktrees/superheroes/issue-1746-9ec121c90cfeb086/plugins/superheroes/lib/tests/test_launcher_place.py:322: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher_place.py::test_a_cloud_spawn_failure_runs_the_build_locally_and_says_unreachable
1 failed in 12.29s
```

- **Restore.** The inverse Edit; quoted from launcher.py:3316: `        fallback_call = dict(place_call, place=PLACE_LOCAL, reason="unreachable", environment=None)`
- **Green.**

```
.                                                                        [100%]
1 passed in 15.36s
```
