# WO-E2 (#1340 layer 2d) bite-proof — `store_core.repo_root` env memo bypass

Per-guard bite proof for `plugins/superheroes/lib/store_core.py`: an
environment-carrying `repo_root` call must not read or write the `cwd`-keyed
memo. The guard is neutralized in source, the proving test goes red alone,
then the guard is restored and the test goes green.

**Provenance:** cursor / composer-2.5.

**Command** (referred to as *the command* below):

```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_store_core.py::test_repo_root_with_env_bypasses_cwd_keyed_memo -q -n auto
```

## Summary table

| ID | Guarded element (file:line) | Axis | Proving test | Verdict |
|---|---|---|---|---|
| E1 | store_core.py:152-153 | environment-carrying `repo_root` bypasses cwd-keyed memo | `test_repo_root_with_env_bypasses_cwd_keyed_memo` | proven |

---

## E1 — environment-carrying `repo_root` bypasses cwd-keyed memo

**Guarded element:** `store_core.py` `repo_root` — axis: when `env` is
present, resolution runs uncached and neither reads nor writes the
`cwd`-keyed memo entry.

**Neutralization** (`plugins/superheroes/lib/store_core.py`):
```python
    if env is not None:
        return _repo_root_uncached(cwd, env=env)
```
→ removed (env-carrying calls fall through to the memo path).

**Proving test:** `test_repo_root_with_env_bypasses_cwd_keyed_memo`

**command:** the command (see top).

**raw red:**
```
bringing up nodes...
bringing up nodes...

F                                                                        [100%]
=================================== FAILURES ===================================
_______________ test_repo_root_with_env_bypasses_cwd_keyed_memo ________________
[gw0] darwin -- Python 3.9.6 /Library/Developer/CommandLineTools/usr/bin/python3

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-2961/popen-gw0/test_repo_root_with_env_bypass0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x1063818e0>

    def test_repo_root_with_env_bypasses_cwd_keyed_memo(tmp_path, monkeypatch):
        cwd = str(tmp_path / "work")
        os.makedirs(cwd)
        memo_root = str(tmp_path / "memo-root")
        env_root = str(tmp_path / "env-root")
        os.makedirs(memo_root)
        os.makedirs(env_root)
        calls = []

        def fake_run_git(cwd_arg, *args, env=None):
            if args == ("rev-parse", "--show-toplevel"):
                calls.append(env)
                if env is not None and env.get("GIT_DIR") == "routed":
                    return sc.GitResult(env_root, sc.GIT_OK, None)
                return sc.GitResult(memo_root, sc.GIT_OK, None)
            return sc.run_git_result(cwd_arg, *args, env=env)

        monkeypatch.setattr(sc, "run_git_result", fake_run_git)
        routed_env = dict(os.environ)
        routed_env["GIT_DIR"] = "routed"
        with sc.repo_identity_memo():
            first = sc.repo_root(cwd)
            assert first == os.path.realpath(memo_root)
            assert len(calls) == 1
            memo = sc._active_repo_identity_memo()
            assert memo["root"][cwd] == first
            second = sc.repo_root(cwd, env=routed_env)
>           assert second == os.path.realpath(env_root)
E           AssertionError: assert '/private/var...ss0/memo-root' == '/private/var...ass0/env-root'
E             
E             Skipping 149 identical leading characters in diff, use -v to show
E             - v_bypass0/env-root
E             ?            ^^
E             + v_bypass0/memo-root
E             ?           + ^^

plugins/superheroes/lib/tests/test_store_core.py:1215: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_store_core.py::test_repo_root_with_env_bypasses_cwd_keyed_memo
1 failed in 1.66s
```

**Restore:** reinstated the `if env is not None: return _repo_root_uncached(cwd, env=env)` early return.

**Restore receipt:**
```python
    if env is not None:
        return _repo_root_uncached(cwd, env=env)
```

**raw green:**
```
bringing up nodes...
bringing up nodes...

.                                                                        [100%]
1 passed in 2.44s
```
