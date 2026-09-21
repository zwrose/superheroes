# WO-G (#1340 layer 2c) bite-proof — register-check main-copy read invariant

Per-guard bite proof for the three guarded elements in `register_check._read_register_lines_from_main`:
path containment, branch-only ref resolution, and ambient git-routing isolation.

**Provenance:** cursor / composer-2.5.

**Command** (referred to as *the command* below):

```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-woG -m pytest plugins/superheroes/lib/tests/test_register_check.py::<TEST> -q
```

## Summary table

| ID | Guarded element (file:line) | Axis | Proving test | Verdict |
|---|---|---|---|---|
| E1 | register_check.py `_rel_path_in_repo` realpath | symlinked ancestor must not read as outside repo | `test_main_copy_symlinked_ancestor_matches_real_path` | proven |
| E2 | register_check.py `_resolve_main_ref` fq branch refs | branch `main` must win over tag `main` | `test_main_copy_grades_branch_not_tag_when_both_named_main` | proven |
| E3 | register_check.py `_isolated_git_routing_env` + `_git_env` | ambient GIT_* must not re-route main read | `test_main_copy_unaffected_by_ambient_git_routing` | proven |

---

## E1 — symlinked ancestor must not read as outside repo

**neutralization** (`plugins/superheroes/lib/register_check.py` `_rel_path_in_repo`):
```
    abs_path = os.path.realpath(register_path)
```
→
```
    abs_path = os.path.abspath(register_path)
```

**command:** `...::test_main_copy_symlinked_ancestor_matches_real_path -q`

**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_____________ test_main_copy_symlinked_ancestor_matches_real_path ______________

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-2739/test_main_copy_symlinked_ances0')

    def test_main_copy_symlinked_ancestor_matches_real_path(tmp_path):
        real = tmp_path / "real"
        real.mkdir()
        link = tmp_path / "link"
        link.symlink_to(real, target_is_directory=True)
        _init_git_repo(real)
        register = real / "register.md"
        register.write_text(_tiny_register_text("Main copy."), encoding="utf-8")
        _git_commit_all(real, "main copy")
        body = real / "body.md"
        body.write_text("> **R1 — Main copy.**\n", encoding="utf-8")
        result_real = _check(
            register, body, "C1", register_copy=rc.REGISTER_COPY_MAIN,
        )
        result_link = _check(
            link / "register.md",
            link / "body.md",
            "C1",
            register_copy=rc.REGISTER_COPY_MAIN,
        )
        assert result_real["result"] == rc.RESULT_PASS
>       assert result_link["result"] == result_real["result"]
E       AssertionError: assert 'undecided' == 'pass'
E         
E         - pass
E         + undecided

plugins/superheroes/lib/tests/test_register_check.py:1145: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_register_check.py::test_main_copy_symlinked_ancestor_matches_real_path
1 failed in 0.44s
```

**restore:** reverted the neutralization (quoted left-hand side under **neutralization**).

**raw green** after restore:
```
.                                                                        [100%]
1 passed in 0.54s
```

---

## E2 — branch `main` must win over tag `main`

**neutralization** (`plugins/superheroes/lib/register_check.py` `_resolve_main_ref`):
```
        fq_ref = _MAIN_BRANCH_FQ_REFS[short_ref]
        # bite-axis: only branch refs may satisfy the main copy — never a tag named main.
        res = store_core.run_git_result(repo_root, "rev-parse", "--verify", fq_ref)
        if res.status == store_core.GIT_UNAVAILABLE:
            return None, None, res.detail
        if res.status == store_core.GIT_OK:
            return short_ref, fq_ref, None
```
→
```
        # bite-axis: only branch refs may satisfy the main copy — never a tag named main.
        res = store_core.run_git_result(repo_root, "rev-parse", "--verify", short_ref)
        if res.status == store_core.GIT_UNAVAILABLE:
            return None, None, res.detail
        if res.status == store_core.GIT_OK:
            return short_ref, short_ref, None
```

**command:** `...::test_main_copy_grades_branch_not_tag_when_both_named_main -q`

**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
__________ test_main_copy_grades_branch_not_tag_when_both_named_main ___________

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-2743/test_main_copy_grades_branch_n0')

    def test_main_copy_grades_branch_not_tag_when_both_named_main(tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        _init_git_repo(repo)
        register = repo / "register.md"
        register.write_text(_tiny_register_text("Tag copy."), encoding="utf-8")
        _git_commit_all(repo, "tag snapshot")
        subprocess.run(
            ["git", "-C", str(repo), "tag", "main"],
            check=True,
            capture_output=True,
        )
        register.write_text(_tiny_register_text("Branch copy."), encoding="utf-8")
        _git_commit_all(repo, "branch snapshot")
        body = repo / "body.md"
        body.write_text("> **R1 — Branch copy.**\n", encoding="utf-8")
        result = _check(register, body, "C1", register_copy=rc.REGISTER_COPY_MAIN)
>       assert result["result"] == rc.RESULT_PASS
E       AssertionError: assert 'fail' == 'pass'
E         
E         - pass
E         + fail

plugins/superheroes/lib/tests/test_register_check.py:1167: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_register_check.py::test_main_copy_grades_branch_not_tag_when_both_named_main
1 failed in 0.70s
```

**restore:** reverted the neutralization (quoted left-hand side under **neutralization**).

**raw green** after restore:
```
.                                                                        [100%]
1 passed in 0.39s
```

---

## E3 — ambient GIT_* must not re-route main read

**neutralization** (`plugins/superheroes/lib/register_check.py`):
```
    env = launch_ledger._scrub_env(os.environ)
```
→
```
    env = dict(os.environ)
```
and
```
    saved = {}
    for key in launch_ledger._GIT_SCRUB_VARS:
        if key in os.environ:
            saved[key] = os.environ.pop(key)
    try:
        yield
    finally:
        os.environ.update(saved)
```
→
```
    yield
```

**command:** `...::test_main_copy_unaffected_by_ambient_git_routing -q`

**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_______________ test_main_copy_unaffected_by_ambient_git_routing _______________

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-2746/test_main_copy_unaffected_by_a0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x10210d2b0>

    def test_main_copy_unaffected_by_ambient_git_routing(tmp_path, monkeypatch):
        repo = tmp_path / "repo"
        repo.mkdir()
        _init_git_repo(repo)
        register = repo / "register.md"
        register.write_text(_tiny_register_text("Main copy."), encoding="utf-8")
        _git_commit_all(repo, "main copy")
        body = repo / "body.md"
        body.write_text("> **R1 — Main copy.**\n", encoding="utf-8")
        result_clean = _check(
            register, body, "C1", register_copy=rc.REGISTER_COPY_MAIN,
        )
        monkeypatch.setenv("GIT_DIR", "/bogus/nonexistent/.git")
        monkeypatch.setenv("GIT_WORK_TREE", "/bogus/nonexistent")
        result_dirty = _check(
            register, body, "C1", register_copy=rc.REGISTER_COPY_MAIN,
        )
        assert result_clean["result"] == rc.RESULT_PASS
>       assert result_dirty == result_clean
E       AssertionError: assert {'body': Posi...Ids': [], ...} == {'body': Posi...Ids': [], ...}
E         
E         Omitting 9 identical items, use -vv to show
E         Differing items:
E         {'result': 'undecided'} != {'result': 'pass'}
E         {'registerRef': None} != {'registerRef': 'main'}
E         {'requiredEntries': []} != {'requiredEntries': ['R1']}
E         {'ok': False} != {'ok': True}...
E         
E         ...Full output truncated (5 lines hidden), use '-vv' to show

plugins/superheroes/lib/tests/test_register_check.py:1190: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_register_check.py::test_main_copy_unaffected_by_ambient_git_routing
1 failed in 0.39s
```

**restore:** reverted both neutralizations (quoted left-hand sides under **neutralization**).

**raw green** after restore:
```
.                                                                        [100%]
1 passed in 0.38s
```
