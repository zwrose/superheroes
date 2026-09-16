# WO-E read-only-view bite-proof

## Read-only render

**Guarded element:** `test_render_writes_nothing` — axis: rendering writes nothing to the profile.

**Neutralization:** added `project_config.set_item(cwd, "dial", 25, root=root)` at the start of `render()` in `configure_view.py`.

**Command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_configure_view_project_config.py::test_render_writes_nothing -q
```

**Red run:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
__________________________ test_render_writes_nothing __________________________

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-232/test_render_writes_nothing0')

    def test_render_writes_nothing(tmp_path):
        # axis: rendering writes nothing — wo_e_1276_read-only-view
        repo, store = _setup_repo(tmp_path)
        core_path = CM.core_path(repo, store)
        before = open(core_path, "rb").read()
        CV.render(repo, root=store)
        after = open(core_path, "rb").read()
>       assert before == after
E       AssertionError: assert b'<!-- superh... {}\n}\n```\n' == b'<!-- superh...  }\n}\n```\n'
E         
E         At index 303 diff: b'\n' != b','
E         Use -v to get more diff

plugins/superheroes/lib/tests/test_configure_view_project_config.py:125: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_configure_view_project_config.py::test_render_writes_nothing
1 failed in 14.36s
```

**Restore:** removed the `project_config.set_item(...)` call from `render()`.

**Restore receipt:** `render()` begins with `data = collect(cwd, root)` only; no setter call.

**Green run:**
```
.                                                                        [100%]
1 passed in 14.36s
```
