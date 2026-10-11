# #1771 WO-A bite-proof: the reader for the environment the owner picked

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

/Users/zwrose/.superheroes-worktrees/superheroes/issue-1771-9596bd8e72803b62/plugins/superheroes/lib/tests/test_cloud_environment.py:47: AssertionError
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

/Users/zwrose/.superheroes-worktrees/superheroes/issue-1771-9596bd8e72803b62/plugins/superheroes/lib/tests/test_cloud_environment.py:73: AssertionError
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

/Users/zwrose/.superheroes-worktrees/superheroes/issue-1771-9596bd8e72803b62/plugins/superheroes/lib/tests/test_cloud_environment.py:73: AssertionError
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
