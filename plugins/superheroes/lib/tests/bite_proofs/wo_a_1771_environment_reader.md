# #1771 WO-A bite-proof: the reader for the environment the owner picked

> Note (2026-10-31, #2296): owner-machine paths and the name of a consuming project in this record were replaced with neutral placeholders after capture; nothing else changed.

Bite-proof record for `plugins/superheroes/lib/cloud_environment.py` (`pick`, `_is_id`), detectors in `plugins/superheroes/lib/tests/test_cloud_environment.py` (`T`).

**Status.** The implementer ran every proof (R1 to R3): each neutralization is a targeted Edit in `cloud_environment.py`, the red is the single named test function run alone, the restore is the inverse Edit, and the green is the same function. Reds and greens below are the pytest output of each run unless a line says otherwise; absolute `tmp_path` prefixes and the worktree path are as printed. No fixture holds a real secret, so nothing is redacted.

- **Run command.** `scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest "<T>::<node>" -q`.
- **Restore receipt, every element.** The restored line is quoted back, and a final search of the module found none of the neutralizations present.
- **Two extra runs, disclosed.**
  - R2: the first red run printed through the tool's output limit, which cut 9084 characters from the middle of it. It was re-run with the neutralization still in place, written whole to a file outside the repository (`/private/tmp/claude-501/-Users-zwrose--superheroes-worktrees-superheroes-issue-1771-9596bd8e72803b62/f3edae54-f13a-43ef-a4df-596a97f031cd/scratchpad/r2_red.txt`, 19073 bytes). Only that complete run is quoted below, with the repeated failure blocks elided as the line says.
  - R3: the red run was written to a file outside the repository too (`.../scratchpad/r3_red.txt`, 6664 bytes) so it could be read whole; it is quoted in full below apart from the elided repeats.
- **Function-level nodes.** R2's and R3's node is a parametrized function; its eighteen cases (nine stored contents, each with `before` None and with `env_01ABCdef`) run together. R3's discriminating cases are the malformed-value ones: `env_ab-cd`, `env_` and ` env_abc` are non-empty strings that do not fully match the grammar.
- **Pinned condition.** `T` builds its Claude config directories under `tmp_path` and passes an explicit `env` mapping with `HOME` under `tmp_path`. The pin makes unobservable: the real home directory, the real `~/.claude*` directories and the process environment.

## Declared guarded-element set

R1 an unchanged value is no pick; R2 a missing value is no pick; R3 only a grammar-valid value is an id.

## Per-element receipts

### R1: an unchanged value is no pick. Axis: refusal (no id returned)

- **Neutralization applied.** In `pick`, the `if value == before:` block (the comparison and its `pick-unchanged` return) deleted, so an unchanged valid value falls through to `picked`.
- **Node.** `T::test_pick_unchanged_setting_asks_again_with_no_id`
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
______________ test_pick_unchanged_setting_asks_again_with_no_id _______________

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1093/test_pick_unchanged_setting_as0')

    def test_pick_unchanged_setting_asks_again_with_no_id(tmp_path):
        env = _env(tmp_path)
        _write(env, _with_value(ENV_ID))
        result = CE.pick(before=ENV_ID, env=env)
>       assert result["action"] == "not-picked"
E       AssertionError: assert 'picked' == 'not-picked'
E         
E         - not-picked
E         ? ----
E         + picked

/path/to/home/.superheroes-worktrees/superheroes/issue-1771-9596bd8e72803b62/plugins/superheroes/lib/tests/test_cloud_environment.py:47: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_environment.py::test_pick_unchanged_setting_asks_again_with_no_id
1 failed in 2.62s
```

- **Restore.** The inverse Edit; quoted from `cloud_environment.py:108`: `        if value == before:`.
- **Green.**

```
.                                                                        [100%]
1 passed in 0.33s
```

### R2: a missing value is no pick. Axis: refusal (no id returned)

- **Neutralization applied.** In `pick`, the `pick-missing` return replaced with `return {"action": "picked", "reason": None, "environment": before, "message": _PICKED}`, so a read that finds no valid value reports the `before` value as picked.
- **Node.** `T::test_pick_missing_setting_asks_again_with_no_id` (eighteen cases).
- **Red** (from the complete file run; the first failure block in full, then the closing summary in full; the other seventeen failure blocks are the same assertion with `content` and `before` set to each of the other cases):

```
FFFFFFFFFFFFFFFFFF                                                       [100%]
=================================== FAILURES ===================================
________ test_pick_missing_setting_asks_again_with_no_id[no-file-None] _________

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1096/test_pick_missing_setting_asks0')
content = None, before = None

    @pytest.mark.parametrize("before", [None, ENV_ID])
    @pytest.mark.parametrize("content", _MISSING)
    def test_pick_missing_setting_asks_again_with_no_id(tmp_path, content, before):
        env = _env(tmp_path)
        if content is not None:
            _write(env, content)
        result = CE.pick(before=before, env=env)
>       assert result["action"] == "not-picked"
E       AssertionError: assert 'picked' == 'not-picked'
E         
E         - not-picked
E         ? ----
E         + picked

/path/to/home/.superheroes-worktrees/superheroes/issue-1771-9596bd8e72803b62/plugins/superheroes/lib/tests/test_cloud_environment.py:73: AssertionError
[... seventeen more failure blocks, same assertion, elided ...]
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_environment.py::test_pick_missing_setting_asks_again_with_no_id[no-file-None]
FAILED plugins/superheroes/lib/tests/test_cloud_environment.py::test_pick_missing_setting_asks_again_with_no_id[no-file-env_01ABCdef]
FAILED plugins/superheroes/lib/tests/test_cloud_environment.py::test_pick_missing_setting_asks_again_with_no_id[empty-object-None]
FAILED plugins/superheroes/lib/tests/test_cloud_environment.py::test_pick_missing_setting_asks_again_with_no_id[empty-object-env_01ABCdef]
FAILED plugins/superheroes/lib/tests/test_cloud_environment.py::test_pick_missing_setting_asks_again_with_no_id[remote-empty-None]
FAILED plugins/superheroes/lib/tests/test_cloud_environment.py::test_pick_missing_setting_asks_again_with_no_id[remote-empty-env_01ABCdef]
FAILED plugins/superheroes/lib/tests/test_cloud_environment.py::test_pick_missing_setting_asks_again_with_no_id[remote-not-object-None]
FAILED plugins/superheroes/lib/tests/test_cloud_environment.py::test_pick_missing_setting_asks_again_with_no_id[remote-not-object-env_01ABCdef]
FAILED plugins/superheroes/lib/tests/test_cloud_environment.py::test_pick_missing_setting_asks_again_with_no_id[malformed-value-None]
FAILED plugins/superheroes/lib/tests/test_cloud_environment.py::test_pick_missing_setting_asks_again_with_no_id[malformed-value-env_01ABCdef]
FAILED plugins/superheroes/lib/tests/test_cloud_environment.py::test_pick_missing_setting_asks_again_with_no_id[bare-prefix-None]
FAILED plugins/superheroes/lib/tests/test_cloud_environment.py::test_pick_missing_setting_asks_again_with_no_id[bare-prefix-env_01ABCdef]
FAILED plugins/superheroes/lib/tests/test_cloud_environment.py::test_pick_missing_setting_asks_again_with_no_id[leading-space-None]
FAILED plugins/superheroes/lib/tests/test_cloud_environment.py::test_pick_missing_setting_asks_again_with_no_id[leading-space-env_01ABCdef]
FAILED plugins/superheroes/lib/tests/test_cloud_environment.py::test_pick_missing_setting_asks_again_with_no_id[number-None]
FAILED plugins/superheroes/lib/tests/test_cloud_environment.py::test_pick_missing_setting_asks_again_with_no_id[number-env_01ABCdef]
FAILED plugins/superheroes/lib/tests/test_cloud_environment.py::test_pick_missing_setting_asks_again_with_no_id[null-None]
FAILED plugins/superheroes/lib/tests/test_cloud_environment.py::test_pick_missing_setting_asks_again_with_no_id[null-env_01ABCdef]
18 failed in 0.43s
```

(The case list above is as printed by the first red run, whose middle the tool cut and whose end it kept whole. The re-run to the file lists the same eighteen cases and closes `18 failed in 0.43s`; its first failure block is the one quoted, with `pytest-1096` as the `tmp_path` number.)

- **Restore.** The inverse Edit; quoted from `cloud_environment.py`: `            return {"action": "not-picked", "reason": "pick-missing", "environment": None,` / `                    "message": _ASK_AGAIN}`.
- **Green.**

```
..................                                                       [100%]
18 passed in 0.28s
```

### R3: only a grammar-valid value is an id. Axis: validation (grammar)

- **Neutralization applied.** In `_is_id`, the `fullmatch` check replaced: `return isinstance(value, str) and len(value) > 0`, so any non-empty string counts as an id.
- **Node.** `T::test_pick_missing_setting_asks_again_with_no_id` (eighteen cases; the malformed-value cases are the discriminating ones).
- **Red** (from `r3_red.txt`; the first failure block in full, then the closing summary in full; the other five failure blocks are the same assertion):

```
........FFFFFF....                                                       [100%]
=================================== FAILURES ===================================
____ test_pick_missing_setting_asks_again_with_no_id[malformed-value-None] _____

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1098/test_pick_missing_setting_asks8')
content = {'remote': {'defaultEnvironmentId': 'env_ab-cd'}}, before = None

    @pytest.mark.parametrize("before", [None, ENV_ID])
    @pytest.mark.parametrize("content", _MISSING)
    def test_pick_missing_setting_asks_again_with_no_id(tmp_path, content, before):
        env = _env(tmp_path)
        if content is not None:
            _write(env, content)
        result = CE.pick(before=before, env=env)
>       assert result["action"] == "not-picked"
E       AssertionError: assert 'picked' == 'not-picked'
E         
E         - not-picked
E         ? ----
E         + picked

/path/to/home/.superheroes-worktrees/superheroes/issue-1771-9596bd8e72803b62/plugins/superheroes/lib/tests/test_cloud_environment.py:73: AssertionError
[... five more failure blocks, same assertion, elided ...]
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_environment.py::test_pick_missing_setting_asks_again_with_no_id[malformed-value-None]
FAILED plugins/superheroes/lib/tests/test_cloud_environment.py::test_pick_missing_setting_asks_again_with_no_id[malformed-value-env_01ABCdef]
FAILED plugins/superheroes/lib/tests/test_cloud_environment.py::test_pick_missing_setting_asks_again_with_no_id[bare-prefix-None]
FAILED plugins/superheroes/lib/tests/test_cloud_environment.py::test_pick_missing_setting_asks_again_with_no_id[bare-prefix-env_01ABCdef]
FAILED plugins/superheroes/lib/tests/test_cloud_environment.py::test_pick_missing_setting_asks_again_with_no_id[leading-space-None]
FAILED plugins/superheroes/lib/tests/test_cloud_environment.py::test_pick_missing_setting_asks_again_with_no_id[leading-space-env_01ABCdef]
6 failed, 12 passed in 0.38s
```

- **Restore.** The inverse Edit; quoted from `cloud_environment.py:37`: `    return isinstance(value, str) and engine_adapter.CLOUD_ENVIRONMENT_ID_RE.fullmatch(value) is not None`. (After the proofs, that one line was wrapped over two lines for length, with the same condition: `    return (isinstance(value, str)` / `            and engine_adapter.CLOUD_ENVIRONMENT_ID_RE.fullmatch(value) is not None)`; the whole test file was run green after the wrap.)
- **Green.**

```
..................                                                       [100%]
18 passed in 0.27s
```

A final search of `cloud_environment.py` for `len(value) > 0`, `"environment": before` and a bare `return {"action": "picked"` without the `value` id found only the real `"environment": value` return, the `if value == before:` comparison and the `fullmatch` check: no neutralization remains.

## WO-C / WO-C2: an unchanged first pick asks to confirm by name

Declared guarded-element set: R6 and D5. Each was re-run on the finished tree (WO-C2, round 2), after the one authorized test change: in `test_pick_unchanged_setting_asks_again_with_no_id` the last assertion became `assert result["message"] == CE._ALREADY_PICKED`.

### R6: an unchanged first pick asks to confirm by name. Axis: refusal (the message that asks for the name)

- **Neutralization applied.** In `pick`, `_ALREADY_PICKED if confirmed is None else _ASK_AGAIN` changed to `_ASK_AGAIN if confirmed is None else _ASK_AGAIN`, so the no-`confirmed` branch gives the generic ask-again message.
- **Node.** `plugins/superheroes/lib/tests/test_cloud_environment.py::test_first_pick_unchanged_asks_to_confirm_by_name`
- **Red.**

```
F                                                                        [100%]
=================================== FAILURES ===================================
______________ test_first_pick_unchanged_asks_to_confirm_by_name _______________

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1260/test_first_pick_unchanged_asks0')

    def test_first_pick_unchanged_asks_to_confirm_by_name(tmp_path):
        env = _env(tmp_path)
        _write(env, _with_value(ENV_ID))
        result = CE.pick(before=ENV_ID, env=env)
        assert result["action"] == "not-picked"
        assert result["reason"] == "pick-unchanged"
        assert result["environment"] is None
>       assert result["message"] == CE._ALREADY_PICKED
E       assert "I can't see ...en it's done." == 'Claude Code ... and tell me.'
E         
E         - Claude Code already had an environment picked, and it's still the same one. If the environment shown as picked in /remote-env is the one you made for this project, say it's that one and I'll use it. Otherwise pick this project's environment and tell me.
E         + I can't see a new pick yet. In Claude Code on this account, run /remote-env, choose the environment you made for this project by its name, and tell me when it's done.

/path/to/home/.superheroes-worktrees/superheroes/issue-1771-9596bd8e72803b62/plugins/superheroes/lib/tests/test_cloud_environment.py:50: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_environment.py::test_first_pick_unchanged_asks_to_confirm_by_name
1 failed in 9.72s
```

- **Restore.** The inverse Edit; quoted from `cloud_environment.py:125`: `                    "message": _ALREADY_PICKED if confirmed is None else _ASK_AGAIN}`.
- **Green.**

```
.                                                                        [100%]
1 passed in 0.27s
```

### D5: step 3 carries the confirm-by-name re-read. Axis: instruction (the command line the skill gives)

- **Neutralization applied.** In `set-up.md` § 6 step 3, the second command line (the re-read, line 449) lost ` --confirmed <the value step 1 kept>`, leaving `pick --cwd . --before <the value step 1 kept>`. The first command line (line 440) never carried it and was not touched.
- **Node.** `plugins/superheroes/lib/tests/test_cloud_setup_sitting_text.py::test_first_pick_unchanged_is_confirmed_by_name_in_step_three`
- **Red.**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_________ test_first_pick_unchanged_is_confirmed_by_name_in_step_three _________

    def test_first_pick_unchanged_is_confirmed_by_name_in_step_three():
        section = _section_six()
        assert section, "section 6 of set-up.md was not found"
        needle = ('cloud_environment.py" pick --cwd . --before <the value step 1 kept> '
                  '--confirmed <the value step 1 kept>')
        confirm = _first(section, needle)
>       assert confirm is not None, "section 6 has no line containing %r" % needle
E       AssertionError: section 6 has no line containing 'cloud_environment.py" pick --cwd . --before <the value step 1 kept> --confirmed <the value step 1 kept>'
E       assert None is not None

/path/to/home/.superheroes-worktrees/superheroes/issue-1771-9596bd8e72803b62/plugins/superheroes/lib/tests/test_cloud_setup_sitting_text.py:120: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_setup_sitting_text.py::test_first_pick_unchanged_is_confirmed_by_name_in_step_three
1 failed in 0.28s
```

- **Restore.** The inverse Edit (the first try matched both command lines and was refused; the second was anchored on the line above, so only line 449 changed); quoted from `set-up.md:449`: `   python3 -B "$ROOT_DIR/lib/cloud_environment.py" pick --cwd . --before <the value step 1 kept> --confirmed <the value step 1 kept>`. A later `git diff --stat` listed only `test_cloud_environment.py`, so `set-up.md` and `cloud_environment.py` are byte-identical to the commit.
- **Green.**

```
.                                                                        [100%]
1 passed in 0.56s
```
