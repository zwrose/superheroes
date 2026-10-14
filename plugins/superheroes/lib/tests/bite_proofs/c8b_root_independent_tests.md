# Bite-proof record: root-independent refusal tests

Detectors: `TE` = `plugins/superheroes/lib/tests/test_engine_dispatch.py`, `TL` = `plugins/superheroes/lib/tests/test_launcher.py`.
Guarded elements (declared by the order): (G1) the `except OSError:` after the `os.open` of the attempt prompt in `_stage_attempt_prompt`;
(G2) the `except OSError:` around the schema read in `_native_channel_suffix`; (G3) the `except OSError:` around
`os.makedirs(log_dir, ...)` in `launch_build`.

The three tests were made independent of the user (root ignores mode bits, so each injects the failure instead of using chmod) in WO-C (`9c309f0a`).
The git-config pin was added here, in `test_log_dir_parent_readonly_refuses_and_terminalizes` only: `GIT_CONFIG_GLOBAL=/dev/null` and
`GIT_CONFIG_NOSYSTEM=1` are set through `monkeypatch` before `_init_repo`, because this machine's global git config sets `commit.gpgsign=true`
and the signer is not reachable from the sandbox. What the pin makes unobservable: a developer's own git configuration (signing) acting on the fixture repository.

Every command was run from the repository root as `scripts/pinned-python -B -m pytest <file> -q -p no:cacheprovider -k <test>`.
Each red is the detector run alone as one `-k` selection; the red captures below are the failure summary lines, not the full traceback,
and all of them end in the `FAILED` line and the count line quoted. Each restore is the inverse edit, with the restored lines quoted back from the file;
each green is the same command. The `UV_NATIVE_TLS` deprecation warning that heads every run is omitted from the captures.
Before any neutralization, the three-node command passed: `3 passed, 1238 deselected in 3.58s`.

## 1. G1: the attempt prompt that cannot be created is refused

Axis: a run directory whose prompt file cannot be created refuses the attempt as `attempt-prompt-unwritable` (refusal side).

- Neutralization (`engine_dispatch._stage_attempt_prompt`): the handler after the `os.open(..., O_EXCL | O_NOFOLLOW, 0o600)` call, `return _refuse("attempt-prompt-unwritable")`, became `raise`.
- Node: `TE -k test_stage_attempt_prompt_refusal_readonly_run_dir`.
- Red: the injected `PermissionError` escaped `_stage_attempt_prompt` (`engine_dispatch.py:718`), through `_execute_injected_attempt` and `_spawn_attempt`, into the test.
  `E           PermissionError: [Errno 13] Permission denied: '.../readonly-run/prompt-attempt-1.md'`,
  `FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_stage_attempt_prompt_refusal_readonly_run_dir`, `1 failed, 841 deselected in 2.84s`.
- Restore: the inverse edit; `engine_dispatch.py:721-722` read `    except OSError:` then `        return _refuse("attempt-prompt-unwritable")`.
- Green: `1 passed, 841 deselected in 2.32s`.

## 2. G2: an unreadable schema yields the empty suffix

Axis: a native schema that cannot be read gives the empty argv suffix, which the coherence check then refuses.

- Neutralization (`engine_dispatch._native_channel_suffix`): the handler around the schema read, `return ()`, became `raise`.
- Node: `TE -k test_claude_native_channel_suffix_unreadable_schema_refuses_coherence`.
- Red: the injected `PermissionError` escaped `_native_channel_suffix` (`engine_dispatch.py:547`) into the test's `assert ED._native_channel_suffix(opened) == ()`.
  `E           PermissionError: [Errno 13] Permission denied: '.../unreadable-schema/native-schema.json'`,
  `FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_claude_native_channel_suffix_unreadable_schema_refuses_coherence`, `1 failed, 841 deselected in 3.06s`.
- Restore: the inverse edit; `engine_dispatch.py:549-550` read `        except OSError:` then `            return ()`.
- Green: `1 passed, 841 deselected in 2.35s`.
- Not separately neutralized: the coherence refusal that follows the empty suffix; this red shows only the handler, so the refusal itself is unproven by a red run here.

## 3. G3: a log directory that cannot be created terminalizes the launch

Axis: a failed `os.makedirs` of the log directory terminalizes the launch as `log-dir-create-failed` and returns the refusal.

- Neutralization (`launcher.launch_build`): `except OSError:` became `except ZeroDivisionError:` (the module stays importable and the `OSError` is no longer caught).
- Node: `TL -k test_log_dir_parent_readonly_refuses_and_terminalizes`.
- Red: the injected `PermissionError` escaped `launch_build` (`launcher.py:3058`) into the test's `L.launch_build(...)` call.
  `E           PermissionError: [Errno 13] Permission denied: '.../readonly-parent/logs'`,
  `FAILED plugins/superheroes/lib/tests/test_launcher.py::test_log_dir_parent_readonly_refuses_and_terminalizes`, `1 failed, 398 deselected in 1.52s`.
  The red came after the test's setup (`_init_repo` with the git-config pin) had passed.
- Restore: the inverse edit; `launcher.py:3058-3059` read `        os.makedirs(log_dir, mode=0o700, exist_ok=True)` then `    except OSError:`.
- Green: `1 passed, 398 deselected in 1.50s`.

## Production files after the proofs

`git diff --stat 9c309f0a -- plugins/superheroes/lib/engine_dispatch.py plugins/superheroes/lib/launcher.py` printed nothing (exit 0).
