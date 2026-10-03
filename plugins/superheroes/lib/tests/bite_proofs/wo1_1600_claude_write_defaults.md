# WO-1 (#1600) — claude write sandbox toolchains and defaults: bite-proof record

Implementer-run record. Method: a targeted Edit on the guarded element, the detector run alone by its exact node id (red), the inverse Edit, the detector again (green), and the restored lines quoted back. Declared guarded-element set: E1, E2, E3, E4. **4 elements, 4 RED→GREEN.** Receipts are unredacted: they carry no secrets, tokens, URLs or PII. Pytest invocation for every run: `scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest <node id> -q -p no:cacheprovider`. The red runs predate the one-line `# axis:` comments added to three detectors, so the traceback line numbers in the red captures are from before those comments.

## E1 — dropping a command family

- **site:** `plugins/superheroes/lib/engine_adapter.py`, `CLAUDE_WRITE_BASH_ALLOW`
- **axis:** the emitted allow list is exactly the eleven targeted rules, in order
- **detector:** `plugins/superheroes/lib/tests/test_claude_write_defaults_1600.py::test_allow_list_is_the_eleven_literal_rules`
- **neutralization:** delete the line `    "Bash(node:*)",` from the tuple.
- **raw red (rc 1):** the `AssertionError` is on the `allow` list.

```
F                                                                        [100%]
=================================== FAILURES ===================================
_________________ test_allow_list_is_the_eleven_literal_rules __________________

    def test_allow_list_is_the_eleven_literal_rules():
>       assert _settings(_SANDBOX)["permissions"] == {
            "allow": [
                "Bash(python:*)", "Bash(python3:*)", "Bash(pytest:*)",
                "Bash(scripts/pinned-python:*)", "Bash(echo:*)",
                "Bash(npm:*)", "Bash(npx:*)", "Bash(node:*)", "Bash(pnpm:*)",
                "Bash(yarn:*)", "Bash(ps:*)",
            ],
            "deny": ["WebFetch", "WebSearch"],
        }
E       AssertionError: assert {'allow': ['B... 'WebSearch']} == {'allow': ['B... 'WebSearch']}
E         
E         Omitting 1 identical items, use -vv to get more diff
E         Differing items:
E         {'allow': ['Bash(python:*)', 'Bash(python3:*)', 'Bash(pytest:*)', 'Bash(scripts/pinned-python:*)', 'Bash(echo:*)', 'Bash(npm:*)', ...]} != {'allow': ['Bash(python:*)', 'Bash(python3:*)', 'Bash(pytest:*)', 'Bash(scripts/pinned-python:*)', 'Bash(echo:*)', 'Bash(npm:*)', ...]}
E         Use -v to get more diff

/Users/zwrose/.superheroes-worktrees/superheroes/issue-1600-4c4462399c4eff62/plugins/superheroes/lib/tests/test_claude_write_defaults_1600.py:53: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_claude_write_defaults_1600.py::test_allow_list_is_the_eleven_literal_rules
1 failed in 0.51s
```

- **restore:** the inverse Edit (`    "Bash(node:*)",` put back between `npx` and `pnpm`).
- **raw green (rc 0):**

```
.                                                                        [100%]
1 passed in 0.46s
```

- **restored lines quoted back:**

```
CLAUDE_WRITE_BASH_ALLOW = (
    "Bash(python:*)",
    "Bash(python3:*)",
    "Bash(pytest:*)",
    "Bash(scripts/pinned-python:*)",
    "Bash(echo:*)",
    "Bash(npm:*)",
    "Bash(npx:*)",
    "Bash(node:*)",
    "Bash(pnpm:*)",
    "Bash(yarn:*)",
    "Bash(ps:*)",
)
```

- **verdict:** RED->GREEN

## E2 — flipping the localBinding default

- **site:** `plugins/superheroes/lib/engine_dispatch.py`, `_resolve_claude_write_sandbox`
- **axis:** the open journals `localBinding` true on macOS
- **detector:** `plugins/superheroes/lib/tests/test_claude_write_defaults_1600.py::test_open_journals_the_defaults_on_macos`
- **neutralization:** change `"localBinding": _host_platform() == _LOCAL_ACCESS_PLATFORM,` to `"localBinding": False,`.
- **raw red (rc 1):**

```
F                                                                        [100%]
=================================== FAILURES ===================================
___________________ test_open_journals_the_defaults_on_macos ___________________

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-213/test_open_journals_the_default0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x106c10860>

    def test_open_journals_the_defaults_on_macos(tmp_path, monkeypatch):
        monkeypatch.setattr(ED, "_host_platform", lambda: "darwin")
        wt, run_dir, _res, fake = _open_with_core(tmp_path, monkeypatch, _core_text())
        opened = _write_opened_record(run_dir)
        journaled = opened["claudeWriteSandbox"]
        expected = ["/tmp"] if os.path.realpath("/tmp") == "/tmp" else ["/tmp", os.path.realpath("/tmp")]
        assert journaled["tmpWriteRoots"] == expected
>       assert journaled["localBinding"] is True
E       assert False is True

/Users/zwrose/.superheroes-worktrees/superheroes/issue-1600-4c4462399c4eff62/plugins/superheroes/lib/tests/test_claude_write_defaults_1600.py:116: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_claude_write_defaults_1600.py::test_open_journals_the_defaults_on_macos
1 failed in 0.67s
```

- **restore:** the inverse Edit (the platform comparison put back).
- **raw green (rc 0):**

```
.                                                                        [100%]
1 passed in 0.58s
```

- **restored lines quoted back:**

```
        "localBinding": _host_platform() == _LOCAL_ACCESS_PLATFORM,
```

- **verdict:** RED->GREEN

## E3 — flipping the tmp default

- **site:** `plugins/superheroes/lib/engine_dispatch.py`, `_resolve_claude_write_sandbox`
- **axis:** the open journals the existing `/tmp` roots
- **detector:** `plugins/superheroes/lib/tests/test_claude_write_defaults_1600.py::test_open_journals_the_defaults_on_macos`
- **neutralization:** change `"tmpWriteRoots": tmp_write_roots,` to `"tmpWriteRoots": [],`.
- **raw red (rc 1):**

```
F                                                                        [100%]
=================================== FAILURES ===================================
___________________ test_open_journals_the_defaults_on_macos ___________________

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-215/test_open_journals_the_default0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x106be2510>

    def test_open_journals_the_defaults_on_macos(tmp_path, monkeypatch):
        monkeypatch.setattr(ED, "_host_platform", lambda: "darwin")
        wt, run_dir, _res, fake = _open_with_core(tmp_path, monkeypatch, _core_text())
        opened = _write_opened_record(run_dir)
        journaled = opened["claudeWriteSandbox"]
        expected = ["/tmp"] if os.path.realpath("/tmp") == "/tmp" else ["/tmp", os.path.realpath("/tmp")]
>       assert journaled["tmpWriteRoots"] == expected
E       AssertionError: assert [] == ['/tmp', '/private/tmp']
E         
E         Right contains 2 more items, first extra item: '/tmp'
E         Use -v to get more diff

/Users/zwrose/.superheroes-worktrees/superheroes/issue-1600-4c4462399c4eff62/plugins/superheroes/lib/tests/test_claude_write_defaults_1600.py:115: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_claude_write_defaults_1600.py::test_open_journals_the_defaults_on_macos
1 failed in 0.60s
```

- **restore:** the inverse Edit (`tmp_write_roots` put back).
- **raw green (rc 0):**

```
.                                                                        [100%]
1 passed in 0.59s
```

- **restored lines quoted back:**

```
    tmp_write_roots = []
    for tmp_root in ("/tmp", os.path.realpath("/tmp")):
        if os.path.isdir(tmp_root) and tmp_root not in tmp_write_roots:
            tmp_write_roots.append(tmp_root)
    sandbox = {
        "writeRoots": write_roots,
        "denyWrite": deny_write,
        "uvCacheDir": uv_cache_dir,
        # the owner-ruled defaults (#1600), frozen at open like the roots
        "tmpWriteRoots": tmp_write_roots,
        "localBinding": _host_platform() == _LOCAL_ACCESS_PLATFORM,
```

- **verdict:** RED->GREEN

## E4 — the settings mapping

- **site:** `plugins/superheroes/lib/engine_adapter.py`, `claude_write_sandbox_settings`
- **axis:** `tmpWriteRoots` extend `allowWrite` after the uv cache and before `extraWritePaths`
- **detector:** `plugins/superheroes/lib/tests/test_claude_write_defaults_1600.py::test_tmp_defaults_reach_allow_write_in_order`
- **neutralization:** delete the line `    allow_write.extend(sandbox.get("tmpWriteRoots") or [])`.
- **raw red (rc 1):**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_________________ test_tmp_defaults_reach_allow_write_in_order _________________

    def test_tmp_defaults_reach_allow_write_in_order():
        sandbox = dict(
            _SANDBOX,
            uvCacheDir="/cache/uv",
            tmpWriteRoots=["/tmp", "/private/tmp"],
            access={
                "allowedDomains": [], "localPorts": False, "localSocketDirs": [],
                "extraWritePaths": ["/x/extra"],
            },
        )
        fs = _settings(sandbox)["sandbox"]["filesystem"]
>       assert fs["allowWrite"] == [
            "/work/wt", "/work/main/.git/worktrees/wt", "/work/main/.git",
            "/cache/uv", "/tmp", "/private/tmp", "/x/extra",
        ]
E       AssertionError: assert ['/work/wt', ...', '/x/extra'] == ['/work/wt', ...ate/tmp', ...]
E         
E         At index 4 diff: '/x/extra' != '/tmp'
E         Right contains 2 more items, first extra item: '/private/tmp'
E         Use -v to get more diff

/Users/zwrose/.superheroes-worktrees/superheroes/issue-1600-4c4462399c4eff62/plugins/superheroes/lib/tests/test_claude_write_defaults_1600.py:75: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_claude_write_defaults_1600.py::test_tmp_defaults_reach_allow_write_in_order
1 failed in 0.28s
```

- **restore:** the inverse Edit (the line put back between the uv-cache append and `extra_paths`).
- **raw green (rc 0):**

```
.                                                                        [100%]
1 passed in 0.28s
```

- **restored lines quoted back:**

```
    allow_write = list(sandbox["writeRoots"])
    if uv_cache is not None:
        env["UV_CACHE_DIR"] = uv_cache
        allow_write.append(uv_cache)
    allow_write.extend(sandbox.get("tmpWriteRoots") or [])
    allow_write.extend(extra_paths)
```

- **verdict:** RED->GREEN
