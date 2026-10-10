# #1744 WO-A bite-proof: the reviewer pass module (`cloud_pass.py`)

Bite-proof record for `plugins/superheroes/lib/cloud_pass.py` (`place`, `make`, `confirm`), detectors in `plugins/superheroes/lib/tests/test_cloud_pass.py` (`T`).

**Status.** The implementer ran every proof (A1 to A6): each neutralization is a targeted Edit in `cloud_pass.py`, the red is the single named node run alone, the restore is the inverse Edit, and the green is the same node. Reds and greens below are the full pytest output of each run unless a line says otherwise; absolute `tmp_path` prefixes and the worktree path are as printed. No fixture holds a real secret (every token is built at run time), so nothing is redacted.

- **Run command.** `scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest "<T>::<node>" -q`.
- **Restore receipt, every element.** The restored line is quoted back, and a final search of `cloud_pass.py` for `if False:`, a bare `return True` and `store_core` found none of the neutralizations present.
- **Two extra runs, disclosed.**
  - A2: the first red run was piped through `grep -v` and `tail -40`, which is a filtered capture. It was re-run unfiltered (to a scratch file) with the neutralization still in place; only the unfiltered run is quoted below.
  - A3: the first red run failed on the wrong axis. `result["action"]` was `refused`, not the extra-path assertion, because the test's own write-recorder called `os.fspath` on the integer descriptor that `os.fdopen` passes to `io.open`. The recorder in `_recording_opens` was fixed to skip integer paths, and the red was re-run with the neutralization still in place. Only the corrected run is quoted. The fix is to the recorder, not to the assertion `set(opened) == {destination}`.
- **Pinned condition.** The tests pass an explicit `now` (`1_800_000_000`) and an explicit `env` mapping with `HOME` under `tmp_path`. The pin makes unobservable: the real wall clock (a real pass lapses on the real calendar), and the process environment's `HOME`, `CODEX_HOME`, `PATH`. The fake reviewer is a callable returning a `SimpleNamespace`; the real reviewer tool is never run.

## Declared guarded-element set

A1 `place`'s renewal-key refusal (P4); A2 `place`'s cloud-session condition (P1); A3 `place`'s single-path write; A4 `make`'s main-sign-in refusal (M2); A5 `confirm`'s placed-pass comparison (C3); A6 `confirm`'s exact-answer check (C8).

## Per-element receipts

### A1: `place`'s renewal-key refusal (P4). Axis: refusal

- **Neutralization applied.** `if not (isinstance(tokens, dict) and tokens.get("refresh_token") == ""):` replaced with `if not isinstance(tokens, dict):`, so any `refresh_token` is accepted.
- **Node.** `T::test_place_refuses_a_pass_that_can_renew`
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
___________________ test_place_refuses_a_pass_that_can_renew ___________________

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-600/test_place_refuses_a_pass_that0')

    def test_place_refuses_a_pass_that_can_renew(tmp_path):
        no_key = _pass_obj()
        del no_key["tokens"]["refresh_token"]
        no_tokens = _pass_obj()
        del no_tokens["tokens"]
        for bad in (RENEWABLE_PASS, _encode(no_key), _encode(no_tokens),
                    _encode(_pass_obj(refresh=None))):
>           result = _refusal_leaves_sign_in_alone(
                tmp_path, _cloud_env(tmp_path, pass_value=bad),
                {"action": "refused", "reason": "pass-can-renew"})

/Users/zwrose/.superheroes-worktrees/superheroes/issue-1744-9d9043901276fccf/plugins/superheroes/lib/tests/test_cloud_pass.py:581: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-600/test_place_refuses_a_pass_that0')
env = {'HOME': '/private/tmp/claude-501/pytest-of-zwrose/pytest-600/test_place_refuses_a_pass_that0/home', 'CLAUDE_CODE_REMO...hWGgwZFhKbExXdGxlUSIsICJhY2NvdW50X2lkIjogImFjY3QtZml4dHVyZSJ9LCAibGFzdF9yZWZyZXNoIjogIjIwMjYtMTAtMTBUMTI6MDA6MDBaIn0='}
expect = {'action': 'refused', 'reason': 'pass-can-renew'}

    def _refusal_leaves_sign_in_alone(tmp_path, env, expect):
        dest = _write(_default(tmp_path), _signin(access=OLD_ACCESS))
        before = dest.read_bytes()
        result = CP.place(env=env)
>       assert {k: result[k] for k in expect} == expect
E       AssertionError: assert {'action': 'p...reason': None} == {'action': 'r...ss-can-renew'}
E         
E         Differing items:
E         {'reason': None} != {'reason': 'pass-can-renew'}
E         {'action': 'placed'} != {'action': 'refused'}
E         Use -v to get more diff

/Users/zwrose/.superheroes-worktrees/superheroes/issue-1744-9d9043901276fccf/plugins/superheroes/lib/tests/test_cloud_pass.py:554: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_pass.py::test_place_refuses_a_pass_that_can_renew
1 failed in 1.62s
```

- **Restore.** The inverse Edit put the check back; quoted from `cloud_pass.py:256`: `    if not (isinstance(tokens, dict) and tokens.get("refresh_token") == ""):`.
- **Green.**

```
.                                                                        [100%]
1 passed in 0.46s
```

### A2: `place`'s cloud-session condition (P1). Axis: skip (nothing opened for writing)

- **Neutralization applied.** `_is_cloud` body `return env.get(CLOUD_ENV) == "true"` replaced with `return True`.
- **Node.** `T::test_place_outside_cloud_session_opens_nothing_for_writing` (five parametrized cases: variable unset, `1`, `True`, `false`, empty).
- **Red** (unfiltered run; the first failure block in full, the other four are the same assertion with `cloud_value` `'1'`, `'True'`, `'false'`, `''`; the closing summary lines are in full):

```
FFFFF                                                                    [100%]
=================================== FAILURES ===================================
_______ test_place_outside_cloud_session_opens_nothing_for_writing[None] _______

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-603/test_place_outside_cloud_sessi0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x108e5c9e0>
cloud_value = None

    @pytest.mark.parametrize("cloud_value", [None, "1", "True", "false", ""])
    def test_place_outside_cloud_session_opens_nothing_for_writing(tmp_path, monkeypatch, cloud_value):
        env = _cloud_env(tmp_path)
        del env[CP.CLOUD_ENV]
        if cloud_value is not None:
            env[CP.CLOUD_ENV] = cloud_value
        dest = _write(_default(tmp_path), _signin(access=OLD_ACCESS))
        before = dest.read_bytes()
        opened = _recording_opens(monkeypatch)
        result = CP.place(env=env)
        monkeypatch.undo()
>       assert result == {"action": "skipped", "reason": "not-a-cloud-session"}
E       AssertionError: assert {'action': 'p... '2027-01-25'} == {'action': 's...loud-session'}
E         
E         Differing items:
E         {'action': 'placed'} != {'action': 'skipped'}
E         {'reason': None} != {'reason': 'not-a-cloud-session'}
E         Left contains 1 more item:
E         {'passLapses': '2027-01-25'}
E         Use -v to get more diff

plugins/superheroes/lib/tests/test_cloud_pass.py:545: AssertionError
[... four more failure blocks, same assertion, elided: about 6 KiB of the 7.5 KiB run ...]
plugins/superheroes/lib/tests/test_cloud_pass.py:545: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_pass.py::test_place_outside_cloud_session_opens_nothing_for_writing[None]
FAILED plugins/superheroes/lib/tests/test_cloud_pass.py::test_place_outside_cloud_session_opens_nothing_for_writing[1]
FAILED plugins/superheroes/lib/tests/test_cloud_pass.py::test_place_outside_cloud_session_opens_nothing_for_writing[True]
FAILED plugins/superheroes/lib/tests/test_cloud_pass.py::test_place_outside_cloud_session_opens_nothing_for_writing[false]
FAILED plugins/superheroes/lib/tests/test_cloud_pass.py::test_place_outside_cloud_session_opens_nothing_for_writing[]
5 failed in 0.38s
```

- **Restore.** The inverse Edit; quoted from `cloud_pass.py:46-47`: `def _is_cloud(env):` / `    return env.get(CLOUD_ENV) == "true"`.
- **Green.**

```
.....                                                                    [100%]
5 passed in 0.40s
```

### A3: `place`'s single-path write. Axis: the set of paths opened for writing is exactly the destination

- **Neutralization applied.** In `place`, the line `_write_signin(path, raw)` replaced with three lines: `sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))`, `import store_core`, `store_core.atomic_write(path, raw.decode("utf-8"))`.
- **Node.** `T::test_place_writes_only_the_destination`
- **Red** (the corrected-recorder run; the extra path is `atomic_write`'s temporary file, which `place` must never create):

```
F                                                                        [100%]
=================================== FAILURES ===================================
____________________ test_place_writes_only_the_destination ____________________

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-606/test_place_writes_only_the_des0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x109270950>

    def test_place_writes_only_the_destination(tmp_path, monkeypatch):
        env = _cloud_env(tmp_path)
        opened = _recording_opens(monkeypatch)
        result = CP.place(env=env)
        monkeypatch.undo()
        assert result["action"] == "placed"
>       assert set(opened) == {os.path.realpath(str(_default(tmp_path)))}
E       AssertionError: assert {'/private/tm...sjmkxw9b.tmp'} == {'/private/tm...ex/auth.json'}
E         
E         Extra items in the left set:
E         '/private/tmp/claude-501/pytest-of-zwrose/pytest-606/test_place_writes_only_the_des0/home/.codex/.store-core.sjmkxw9b.tmp'
E         Extra items in the right set:
E         '/private/tmp/claude-501/pytest-of-zwrose/pytest-606/test_place_writes_only_the_des0/home/.codex/auth.json'
E         Use -v to get more diff

plugins/superheroes/lib/tests/test_cloud_pass.py:511: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_pass.py::test_place_writes_only_the_destination
1 failed in 0.24s
```

- **Restore.** The inverse Edit; quoted from `cloud_pass.py:275`: `            _write_signin(path, raw)`. A search of the file for `store_core` finds nothing.
- **Green.**

```
.                                                                        [100%]
1 passed in 0.21s
```

### A4: `make`'s main-sign-in refusal (M2). Axis: refusal (nothing on the clipboard)

- **Neutralization applied.** `if os.path.realpath(path) == os.path.realpath(_default_signin_path(env)):` replaced with `if False:`.
- **Node.** `T::test_make_refuses_when_separate_sign_in_is_the_main_one` (two cases: the default directory is a symlink to the separate one, and `CODEX_HOME` points at the separate directory).
- **Red:**

```
FF                                                                       [100%]
=================================== FAILURES ===================================
_______ test_make_refuses_when_separate_sign_in_is_the_main_one[symlink] _______

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-608/test_make_refuses_when_separat0')
variant = 'symlink'

    @pytest.mark.parametrize("variant", ["symlink", "codex-home-points-at-separate"])
    def test_make_refuses_when_separate_sign_in_is_the_main_one(tmp_path, variant):
        _write(_separate(tmp_path), _signin())
        env = _env(tmp_path)
        if variant == "symlink":
            os.symlink(_separate(tmp_path).parent, _default(tmp_path).parent)
        else:
            env["CODEX_HOME"] = str(_separate(tmp_path).parent)
        calls = []
        result = CP.make(env=env, clipboard=calls.append, now=NOW)
>       assert result["action"] == "refused" and result["reason"] == "separate-sign-in-is-main"
E       AssertionError: assert ('copied' == 'refused'
E         
E         - refused
E         + copied)

/Users/zwrose/.superheroes-worktrees/superheroes/issue-1744-9d9043901276fccf/plugins/superheroes/lib/tests/test_cloud_pass.py:352: AssertionError
_ test_make_refuses_when_separate_sign_in_is_the_main_one[codex-home-points-at-separate] _

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-608/test_make_refuses_when_separat1')
variant = 'codex-home-points-at-separate'

    @pytest.mark.parametrize("variant", ["symlink", "codex-home-points-at-separate"])
    def test_make_refuses_when_separate_sign_in_is_the_main_one(tmp_path, variant):
        _write(_separate(tmp_path), _signin())
        env = _env(tmp_path)
        if variant == "symlink":
            os.symlink(_separate(tmp_path).parent, _default(tmp_path).parent)
        else:
            env["CODEX_HOME"] = str(_separate(tmp_path).parent)
        calls = []
        result = CP.make(env=env, clipboard=calls.append, now=NOW)
>       assert result["action"] == "refused" and result["reason"] == "separate-sign-in-is-main"
E       AssertionError: assert ('copied' == 'refused'
E         
E         - refused
E         + copied)

/Users/zwrose/.superheroes-worktrees/superheroes/issue-1744-9d9043901276fccf/plugins/superheroes/lib/tests/test_cloud_pass.py:352: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_pass.py::test_make_refuses_when_separate_sign_in_is_the_main_one[symlink]
FAILED plugins/superheroes/lib/tests/test_cloud_pass.py::test_make_refuses_when_separate_sign_in_is_the_main_one[codex-home-points-at-separate]
2 failed in 0.27s
```

- **Restore.** The inverse Edit; quoted from `cloud_pass.py:166`: `    if os.path.realpath(path) == os.path.realpath(_default_signin_path(env)):`.
- **Green.**

```
..                                                                       [100%]
2 passed in 0.20s
```

### A5: `confirm`'s placed-pass comparison (C3). Axis: the sign-in on disk must equal the pass in the environment

- **Neutralization applied.** `if signin is None or signin != expected:` replaced with `if signin is None:`.
- **Node.** `T::test_confirm_pass_not_placed_when_older_sign_in_on_disk` (an older, different, valid sign-in on disk, the fake reviewer answering `READY`).
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
___________ test_confirm_pass_not_placed_when_older_sign_in_on_disk ____________

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-610/test_confirm_pass_not_placed_w0')

    def test_confirm_pass_not_placed_when_older_sign_in_on_disk(tmp_path):
        calls = []
        older = _pass_obj(access=OLD_ACCESS)
        env = _placed_env(tmp_path, signin_obj=older)
        result = CP.confirm(env=env, run=_fake_run(calls=calls), now=NOW)
>       _assert_no(result, "pass-not-placed")

/Users/zwrose/.superheroes-worktrees/superheroes/issue-1744-9d9043901276fccf/plugins/superheroes/lib/tests/test_cloud_pass.py:657: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

result = {'schema': 'cloud-pass-confirmation/1', 'reviewerAnswered': True, 'passLapses': '2027-01-26', 'reason': None}
reason = 'pass-not-placed', lapses = None

    def _assert_no(result, reason, lapses=None):
        assert result["schema"] == CP.CONFIRMATION_SCHEMA
>       assert result["reviewerAnswered"] is False
E       assert True is False

/Users/zwrose/.superheroes-worktrees/superheroes/issue-1744-9d9043901276fccf/plugins/superheroes/lib/tests/test_cloud_pass.py:626: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_pass.py::test_confirm_pass_not_placed_when_older_sign_in_on_disk
1 failed in 0.35s
```

- **Restore.** The inverse Edit; quoted from `cloud_pass.py:302`: `    if signin is None or signin != expected:`.
- **Green.**

```
.                                                                        [100%]
1 passed in 0.26s
```

### A6: `confirm`'s exact-answer check (C8). Axis: the answer must be exactly `READY` on standard output

- **Neutralization applied.** `if not (isinstance(stdout, str) and stdout.strip() == _ANSWER):` replaced with `if False:`, so exit zero alone counts as an answer.
- **Node.** `T::test_confirm_unexpected_answer` (three cases: empty standard output, `READY` on standard error only, a different word on standard output).
- **Red** (all three cases, in full):

```
FFF                                                                      [100%]
=================================== FAILURES ===================================
_________________ test_confirm_unexpected_answer[empty-stdout] _________________

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-612/test_confirm_unexpected_answer0')
fixture = {'stdout': ''}

    @pytest.mark.parametrize("fixture", [
        {"stdout": ""},
        {"stdout": "", "stderr": "READY\n"},
        {"stdout": "DONE\n"},
    ], ids=["empty-stdout", "ready-on-stderr-only", "different-word"])
    def test_confirm_unexpected_answer(tmp_path, fixture):
>       _assert_no(_confirm(tmp_path, **fixture), "reviewer-answer-unexpected", lapses=EXP_DATE)

/Users/zwrose/.superheroes-worktrees/superheroes/issue-1744-9d9043901276fccf/plugins/superheroes/lib/tests/test_cloud_pass.py:708: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

result = {'schema': 'cloud-pass-confirmation/1', 'reviewerAnswered': True, 'passLapses': '2027-01-25', 'reason': None}
reason = 'reviewer-answer-unexpected', lapses = '2027-01-25'

    def _assert_no(result, reason, lapses=None):
        assert result["schema"] == CP.CONFIRMATION_SCHEMA
>       assert result["reviewerAnswered"] is False
E       assert True is False

/Users/zwrose/.superheroes-worktrees/superheroes/issue-1744-9d9043901276fccf/plugins/superheroes/lib/tests/test_cloud_pass.py:626: AssertionError
_____________ test_confirm_unexpected_answer[ready-on-stderr-only] _____________

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-612/test_confirm_unexpected_answer1')
fixture = {'stdout': '', 'stderr': 'READY\n'}

    @pytest.mark.parametrize("fixture", [
        {"stdout": ""},
        {"stdout": "", "stderr": "READY\n"},
        {"stdout": "DONE\n"},
    ], ids=["empty-stdout", "ready-on-stderr-only", "different-word"])
    def test_confirm_unexpected_answer(tmp_path, fixture):
>       _assert_no(_confirm(tmp_path, **fixture), "reviewer-answer-unexpected", lapses=EXP_DATE)

/Users/zwrose/.superheroes-worktrees/superheroes/issue-1744-9d9043901276fccf/plugins/superheroes/lib/tests/test_cloud_pass.py:708: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

result = {'schema': 'cloud-pass-confirmation/1', 'reviewerAnswered': True, 'passLapses': '2027-01-25', 'reason': None}
reason = 'reviewer-answer-unexpected', lapses = '2027-01-25'

    def _assert_no(result, reason, lapses=None):
        assert result["schema"] == CP.CONFIRMATION_SCHEMA
>       assert result["reviewerAnswered"] is False
E       assert True is False

/Users/zwrose/.superheroes-worktrees/superheroes/issue-1744-9d9043901276fccf/plugins/superheroes/lib/tests/test_cloud_pass.py:626: AssertionError
________________ test_confirm_unexpected_answer[different-word] ________________

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-612/test_confirm_unexpected_answer2')
fixture = {'stdout': 'DONE\n'}

    @pytest.mark.parametrize("fixture", [
        {"stdout": ""},
        {"stdout": "", "stderr": "READY\n"},
        {"stdout": "DONE\n"},
    ], ids=["empty-stdout", "ready-on-stderr-only", "different-word"])
    def test_confirm_unexpected_answer(tmp_path, fixture):
>       _assert_no(_confirm(tmp_path, **fixture), "reviewer-answer-unexpected", lapses=EXP_DATE)

/Users/zwrose/.superheroes-worktrees/superheroes/issue-1744-9d9043901276fccf/plugins/superheroes/lib/tests/test_cloud_pass.py:708: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

result = {'schema': 'cloud-pass-confirmation/1', 'reviewerAnswered': True, 'passLapses': '2027-01-25', 'reason': None}
reason = 'reviewer-answer-unexpected', lapses = '2027-01-25'

    def _assert_no(result, reason, lapses=None):
        assert result["schema"] == CP.CONFIRMATION_SCHEMA
>       assert result["reviewerAnswered"] is False
E       assert True is False

/Users/zwrose/.superheroes-worktrees/superheroes/issue-1744-9d9043901276fccf/plugins/superheroes/lib/tests/test_cloud_pass.py:626: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_pass.py::test_confirm_unexpected_answer[empty-stdout]
FAILED plugins/superheroes/lib/tests/test_cloud_pass.py::test_confirm_unexpected_answer[ready-on-stderr-only]
FAILED plugins/superheroes/lib/tests/test_cloud_pass.py::test_confirm_unexpected_answer[different-word]
3 failed in 0.51s
```

- **Restore.** The inverse Edit; quoted from `cloud_pass.py:339`: `    if not (isinstance(stdout, str) and stdout.strip() == _ANSWER):`.
- **Green.**

```
...                                                                      [100%]
3 passed in 0.49s
```
