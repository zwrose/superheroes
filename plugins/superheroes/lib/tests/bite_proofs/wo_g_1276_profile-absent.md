# WO-G profile-absent bite-proof

## profile-absent

**Guarded element:** `test_edge2_profile_unreadable` — axis: absent-versus-unreadable distinction.

**Neutralization:** in `gate_config_profile_is_absent`, replaced `return cls.status == CONFIG_ABSENT` with `return True`.

**Command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_core_md_profile_absent.py::test_edge2_profile_unreadable -q
```

**Red run:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
________________________ test_edge2_profile_unreadable _________________________

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-277/test_edge2_profile_unreadable0')

    def test_edge2_profile_unreadable(tmp_path):
        # axis: absent-versus-unreadable — wo_g_1276_profile-absent
        repo, store = _setup_repo(tmp_path)
        open(CM.core_path(repo, store), "w").write("not core\n")
>       assert CM.gate_config_profile_is_absent(repo, root=store) is False
E       AssertionError: assert True is False
E        +  where True = <function gate_config_profile_is_absent at 0x10635e160>('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-277/test_edge2_profile_unreadable0', root='/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-277/test_edge2_profile_unreadable0/store')
E        +    where <function gate_config_profile_is_absent at 0x10635e160> = CM.gate_config_profile_is_absent

plugins/superheroes/lib/tests/test_core_md_profile_absent.py:54: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_core_md_profile_absent.py::test_edge2_profile_unreadable
1 failed in 1.25s
```

**Restore:** restored `return cls.status == CONFIG_ABSENT` in `gate_config_profile_is_absent`.

**Restore receipt:** `return cls.status == CONFIG_ABSENT`

**Green run:**
```
.                                                                        [100%]
1 passed in 1.49s
```
