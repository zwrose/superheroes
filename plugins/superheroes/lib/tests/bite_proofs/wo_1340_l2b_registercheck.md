# WO-D (#1340 layer 2b) bite-proof — `register_check.py` fail-closed main read

Per-guard bite proof for `plugins/superheroes/lib/register_check.py`: the load-bearing
fail-closed clause is neutralized in source, the proving test goes red alone, then the clause is
restored and the test goes green again.

**Provenance:** cursor / composer-2.5.

**Command** (referred to as *the command* below):

```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-woD -m pytest plugins/superheroes/lib/tests/test_register_check.py::test_main_selected_path_not_tracked_undecided -q
```

## Summary table

| ID | Guarded element (file:line) | Axis | Proving test | Verdict |
|---|---|---|---|---|
| E1 | register_check.py:399 | failed main read must not fall back to worktree | `test_main_selected_path_not_tracked_undecided` | proven |

---

## E1 — failed main read must not fall back to worktree

**neutralization** (`plugins/superheroes/lib/register_check.py`):
```python
    if lines is None:
        # axis: failed main read must not fall back to worktree — register fail-closed.
        return (
            None,
            UNDECIDED_REGISTER_UNREADABLE,
            None,
            unreadable_detail,
            REGISTER_COPY_MAIN,
            main_ref,
        )
```
→
```python
    if lines is None:
        # axis: failed main read must not fall back to worktree — register fail-closed.
        lines = _read_lines(register_path)  # bite-proof
        main_ref = None
    if lines is None:
        return (
            None,
            UNDECIDED_REGISTER_UNREADABLE,
            None,
            unreadable_detail,
            REGISTER_COPY_MAIN,
            main_ref,
        )
```

**command:** the command (see top).

**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
________________ test_main_selected_path_not_tracked_undecided _________________

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-2418/test_main_selected_path_not_tr0')

    def test_main_selected_path_not_tracked_undecided(tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        _init_git_repo(repo)
        readme = repo / "README.md"
        readme.write_text("seed\n", encoding="utf-8")
        _git_commit_all(repo, "seed")
        register = repo / "register.md"
        register.write_text(_tiny_register_text(), encoding="utf-8")
        body = repo / "body.md"
        body.write_text("> **R1 — One line entry.**\n", encoding="utf-8")
        result = _check(register, body, "C1", register_copy=rc.REGISTER_COPY_MAIN)
>       assert result["result"] == rc.RESULT_UNDECIDED
E       AssertionError: assert 'pass' == 'undecided'
E         
E         - undecided
E         + pass

plugins/superheroes/lib/tests/test_register_check.py:1094: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_register_check.py::test_main_selected_path_not_tracked_undecided
1 failed in 0.74s
```

**restore:** reverted the neutralization block to the original `return` on failed main read (quoted above under **neutralization** left-hand side).

**raw green** after restore:
```
.                                                                        [100%]
1 passed in 0.30s
```
