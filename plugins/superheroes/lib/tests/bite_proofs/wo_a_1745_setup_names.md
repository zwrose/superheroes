# #1745 WO-A bite-proof: calibration file names read from their owners, and the pass block's environment line

> Note (2026-10-31, #2296): owner-machine paths and the name of a consuming project in this record were replaced with neutral placeholders after capture; nothing else changed.

Bite-proof record for `plugins/superheroes/lib/cloud_setup_text.py` (`_calibration`, `_store_files`) and `plugins/superheroes/lib/cloud_pass.py` (`make`), detectors in `plugins/superheroes/lib/tests/test_cloud_setup_text.py` (`TS`) and `plugins/superheroes/lib/tests/test_cloud_pass.py` (`TP`).

**Status.** The implementer ran every proof (A1 to A5): each neutralization is a targeted Edit in the source file, the red is the single named test function run alone, the restore is the inverse Edit, and the green is the same function. Reds and greens below are the pytest output of each run unless a line says otherwise; absolute `tmp_path` prefixes and the worktree path are as printed. No fixture holds a real secret, so nothing is redacted.

- **Run command.** `scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest "<T>::<node>" -q`.
- **Restore receipt, every element.** The restored line is quoted back, and a final search of the two source files found none of the neutralizations present.
- **One extra run, disclosed.**
  - A4: the first red run printed through the tool's output limit, which cut 1570 characters from the middle of it. It was re-run with the neutralization still in place, written whole to a file outside the repository (`/private/tmp/claude-501/-Users-zwrose--superheroes-worktrees-superheroes-issue-1745-035dde805e265dbb/03e82f96-2b1e-4b19-95d8-b51d1e1e6e3e/scratchpad/a4_red.txt`, 11559 bytes). Only that complete run is quoted below, with the repeated failure blocks elided as the line says.
- **Function-level nodes.** A4's node is a parametrized function; its thirteen cases run together. A5's red names an existing test, which passes no environment, so it is the discriminating detector for the unconditional-line neutralization.
- **Pinned condition.** `TS` builds its stores, homes and Claude config directories under `tmp_path`; `TP` passes an explicit `now` (`1_800_000_000`) and an explicit `env` mapping with `HOME` under `tmp_path`, and a clipboard recorder in place of the real clipboard command. The pin makes unobservable: the real home directory, the process environment, the real clipboard and the real wall clock.

## Declared guarded-element set

A1 the writer reads the registry file's name from `mode_registry`; A2 the writer reads the core file's name and the config directory's name from their owners; A3 the writer reads the policy file's name from `architect_config.policy_path` in the outside-the-repository branch; A4 `make` refuses a malformed environment id; A5 `make` adds the environment line only when given an id.

The meta file's name (`mode_registry.META_FILENAME`) is read in the same line as the registry file's name and is checked by `TS::test_writer_follows_a_renamed_meta_file`; it has no neutralization of its own here and is unproven by a run in this record (A1 is its class's representative for the shared use site, which is the same tuple).

## Per-element receipts

### A1: the registry file's name follows its owner. Axis: name follows its owner

- **Neutralization applied.** In `_calibration`, `mode_registry.REGISTRY_FILENAME` in the `top` tuple replaced with the literal `"registry.json"`.
- **Node.** `TS::test_writer_follows_a_renamed_registry_file`
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_________________ test_writer_follows_a_renamed_registry_file __________________

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1019/test_writer_follows_a_renamed_0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x1090c8470>

    def test_writer_follows_a_renamed_registry_file(tmp_path, monkeypatch):
        w = _outside(tmp_path)
        monkeypatch.setattr(mode_registry, "REGISTRY_FILENAME", "renamed-registry.json")
        _put(w, "renamed-registry.json", b"{}\n")
        files = CS.calibration_files(w.cwd, w.root)
>       assert "renamed-registry.json" in files and "registry.json" not in files
E       assert ('renamed-registry.json' in {'config/core.md': b'# Core\nline two\n', 'config/review-crew.md': b'# Crew\nsecond\n', 'doc-policy.json': b'{"docs": "x"}\n', 'meta.json': b'{"schemaVersion": 1}\n', ...})

/path/to/home/.superheroes-worktrees/superheroes/issue-1745-035dde805e265dbb/plugins/superheroes/lib/tests/test_cloud_setup_text.py:822: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_setup_text.py::test_writer_follows_a_renamed_registry_file
1 failed in 0.68s
```

- **Restore.** The inverse Edit; quoted from `cloud_setup_text.py:222`: `    top = (mode_registry.REGISTRY_FILENAME, mode_registry.META_FILENAME, _policy_name(cwd, root))`.
- **Green.**

```
.                                                                        [100%]
1 passed in 1.14s
```

### A2: the core file's name and the config directory's name follow their owners. Axis: name follows its owner

- **Neutralization applied.** In `_store_files`, `config_dir_name = mode_registry.CONFIG_DIRNAME` replaced with `config_dir_name = "config"`. The directory name is the part neutralized; the core file's name is read through `_core_rel` and is checked by the same test's `stamped_files` assertions.
- **Node.** `TS::test_writer_follows_a_renamed_core_file_and_config_directory`
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_________ test_writer_follows_a_renamed_core_file_and_config_directory __________

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1021/test_writer_follows_a_renamed_0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x10b5105f0>

    def test_writer_follows_a_renamed_core_file_and_config_directory(tmp_path, monkeypatch):
        w = _outside(tmp_path)
        monkeypatch.setattr(core_md, "CORE_FILENAME", "renamed-core.md")
        monkeypatch.setattr(mode_registry, "CONFIG_DIRNAME", "renamed-config")
        _put(w, "renamed-config/renamed-core.md", _core(True))
        files = CS.calibration_files(w.cwd, w.root)
>       assert list(files) == ["doc-policy.json", "meta.json", "permission/rules.json",
                               "registry.json", "renamed-config/renamed-core.md"]
E       AssertionError: assert ['config/core...egistry.json'] == ['doc-policy....amed-core.md']
E         
E         At index 0 diff: 'config/core.md' != 'doc-policy.json'
E         Left contains one more item: 'registry.json'
E         Use -v to get more diff

/path/to/home/.superheroes-worktrees/superheroes/issue-1745-035dde805e265dbb/plugins/superheroes/lib/tests/test_cloud_setup_text.py:839: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_setup_text.py::test_writer_follows_a_renamed_core_file_and_config_directory
1 failed in 0.51s
```

- **Restore.** The inverse Edit; quoted from `cloud_setup_text.py:183`: `    config_dir_name = mode_registry.CONFIG_DIRNAME`.
- **Green.**

```
.                                                                        [100%]
1 passed in 0.55s
```

### A3: the policy file's name follows `architect_config.policy_path` outside the repository. Axis: name follows its owner

- **Neutralization applied.** In `_calibration`, `_policy_name(cwd, root)` in the `top` tuple replaced with the literal `"doc-policy.json"`.
- **Node.** `TS::test_writer_follows_a_renamed_policy_file_outside_the_repository`
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_______ test_writer_follows_a_renamed_policy_file_outside_the_repository _______

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1023/test_writer_follows_a_renamed_0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x109308dd0>

    def test_writer_follows_a_renamed_policy_file_outside_the_repository(tmp_path, monkeypatch):
        w = _outside(tmp_path)
        _put(w, "moved-policy.json", b"{}\n")
        monkeypatch.setattr(architect_config, "policy_path",
                            lambda cwd, root=None: os.path.join(w.store, "moved-policy.json"))
        files = CS.calibration_files(w.cwd, w.root)
>       assert "moved-policy.json" in files and "doc-policy.json" not in files
E       assert ('moved-policy.json' in {'config/core.md': b'# Core\nline two\n', 'config/review-crew.md': b'# Crew\nsecond\n', 'doc-policy.json': b'{"docs": "x"}\n', 'meta.json': b'{"schemaVersion": 1}\n', ...})

/path/to/home/.superheroes-worktrees/superheroes/issue-1745-035dde805e265dbb/plugins/superheroes/lib/tests/test_cloud_setup_text.py:853: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_setup_text.py::test_writer_follows_a_renamed_policy_file_outside_the_repository
1 failed in 0.45s
```

- **Restore.** The inverse Edit; quoted from `cloud_setup_text.py:222`: `    top = (mode_registry.REGISTRY_FILENAME, mode_registry.META_FILENAME, _policy_name(cwd, root))`.
- **Green.**

```
.                                                                        [100%]
1 passed in 0.46s
```

### A4: `make` refuses a malformed environment id. Axis: refusal (nothing copied)

- **Neutralization applied.** In `make`, the condition `not (isinstance(environment, str) and engine_adapter.CLOUD_ENVIRONMENT_ID_RE.fullmatch(environment))` replaced with `not isinstance(environment, str)`.
- **Node.** `TP::test_make_refuses_a_malformed_environment` (thirteen cases: ten malformed strings, an integer, a bytes value, a list).
- **Red** (from the complete file run; the first failure block in full, then the closing summary in full; the other nine failure blocks are the same assertion with `bad` set to each of the other malformed strings, and the integer, bytes and list cases pass under this neutralization because they are not strings):

```
FFFFFFFFFF...                                                            [100%]
=================================== FAILURES ===================================
_________________ test_make_refuses_a_malformed_environment[] __________________

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1025/test_make_refuses_a_malformed_0')
bad = ''

    @pytest.mark.parametrize("bad", ["", "env", "env_", "env_ab cd", "env_ab\ncd", "env_ab\n",
                                     "env_a=b", "ENV_abc", " env_abc", "env_abc ", 7, b"env_abc",
                                     ["env_abc"]])
    def test_make_refuses_a_malformed_environment(tmp_path, bad):
        _write(_separate(tmp_path), _signin())
        calls = []
        result = CP.make(env=_env(tmp_path), clipboard=calls.append, now=NOW, environment=bad)
>       assert result["action"] == "refused" and result["reason"] == "environment-invalid"
E       AssertionError: assert ('copied' == 'refused'
E         
E         - refused
E         + copied)

/path/to/home/.superheroes-worktrees/superheroes/issue-1745-035dde805e265dbb/plugins/superheroes/lib/tests/test_cloud_pass.py:353: AssertionError
[... nine more failure blocks, same assertion, elided ...]
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_pass.py::test_make_refuses_a_malformed_environment[]
FAILED plugins/superheroes/lib/tests/test_cloud_pass.py::test_make_refuses_a_malformed_environment[env]
FAILED plugins/superheroes/lib/tests/test_cloud_pass.py::test_make_refuses_a_malformed_environment[env_]
FAILED plugins/superheroes/lib/tests/test_cloud_pass.py::test_make_refuses_a_malformed_environment[env_ab cd]
FAILED plugins/superheroes/lib/tests/test_cloud_pass.py::test_make_refuses_a_malformed_environment[env_ab\ncd]
FAILED plugins/superheroes/lib/tests/test_cloud_pass.py::test_make_refuses_a_malformed_environment[env_ab\n]
FAILED plugins/superheroes/lib/tests/test_cloud_pass.py::test_make_refuses_a_malformed_environment[env_a=b]
FAILED plugins/superheroes/lib/tests/test_cloud_pass.py::test_make_refuses_a_malformed_environment[ENV_abc]
FAILED plugins/superheroes/lib/tests/test_cloud_pass.py::test_make_refuses_a_malformed_environment[ env_abc]
FAILED plugins/superheroes/lib/tests/test_cloud_pass.py::test_make_refuses_a_malformed_environment[env_abc ]
10 failed, 3 passed in 0.25s
```

- **Restore.** The inverse Edit; quoted from `cloud_pass.py:190-191`: `        if not (isinstance(environment, str)` / `                and engine_adapter.CLOUD_ENVIRONMENT_ID_RE.fullmatch(environment)):`.
- **Green.**

```
.............                                                            [100%]
13 passed in 0.17s
```

### A5: `make` adds the environment line only when given an id. Axis: block content

- **Neutralization applied.** In `make`, `if environment is not None:` before the `lines.append("%s=%s" % (ENVIRONMENT_ENV, environment))` line replaced with `if True:`, so the line is always appended and `None` renders as the text `None`.
- **Node.** `TP::test_make_puts_four_line_block_on_clipboard` (an existing test; it passes no environment).
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_________________ test_make_puts_four_line_block_on_clipboard __________________

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1028/test_make_puts_four_line_block0')

    def test_make_puts_four_line_block_on_clipboard(tmp_path):
        result, calls = _make_with(tmp_path, _signin())
        assert len(calls) == 1
        block = calls[0]
        assert block.endswith("\n")
        lines = block.splitlines()
>       assert len(lines) == 4
E       AssertionError: assert 5 == 4
E        +  where 5 = len(['SUPERHEROES_REVIEWER_PASS=eyJhdXRoX21vZGUiOiAiY2hhdGdwdCIsICJPUEVOQUlfQVBJX0tFWSI6IG51bGwsICJ0b2tlbnMiOiB7ImlkX3Rva2...RIDE=http://127.0.0.1:9/', 'CODEX_REVOKE_TOKEN_URL_OVERRIDE=http://127.0.0.1:9/', 'SUPERHEROES_CLOUD_ENVIRONMENT=None'])

/path/to/home/.superheroes-worktrees/superheroes/issue-1745-035dde805e265dbb/plugins/superheroes/lib/tests/test_cloud_pass.py:311: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_pass.py::test_make_puts_four_line_block_on_clipboard
1 failed in 0.15s
```

(The `...` inside the list is pytest's own repr elision of the long first line, not a cut of this record.)

- **Restore.** The inverse Edit; quoted from `cloud_pass.py:240`: `    if environment is not None:`. A search of the file for `if True:` found none.
- **Green.**

```
.                                                                        [100%]
1 passed in 0.13s
```
