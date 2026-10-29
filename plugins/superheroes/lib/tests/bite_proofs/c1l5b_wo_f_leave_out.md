# C1-L5b (#2243 WO-F) bite-proof — engine reviewers get the patch without proven copies

**Provenance:** implementer WO-F / `lib/sanitized_view.py`, `lib/engine_dispatch.py`, `lib/tests/test_sanitized_view_leave_out_c1l5b.py`

Declared guarded elements (from the order): E1 the survivors filter that drops left-out paths, E2 the leave-out loader's shape check (the `..` segment check is the representative; the other shape faults — non-JSON, wrong schema, extra key, non-list `files`, non-string, blank, absolute, backslash, duplicate — are one class, "loader accepts a malformed file", each pinned by its own `MALFORMED` case in `test_loader_refuses_each_malformed_shape` but not individually neutralized here), E3 the launch-path threading of `leave_out` into `build_view`. Each was neutralized with one targeted edit and restored with the inverse edit; no `git checkout`, `restore`, `reset` or `stash` was used. Run from `/home/user/wt-2243-f`. Each capture is the runner's whole output for the run apart from the `UV_NATIVE_TLS` deprecation warning line, which is left out; nothing is redacted (no secrets, tokens or URLs appear).

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| E1 | `sanitized_view.py:1910` `p not in left_out_set and (...)` in the `survivors` comprehension of `_stage_review_diff` | a path the leave-out names is not a survivor, so git is never asked for its section | `test_leave_out_drops_only_the_named_section` |
| E2 | `sanitized_view.py:1873` `".." in entry.split("/")` in `load_leave_out_file` | a leave-out entry with a `..` segment makes the file invalid | `test_loader_refuses_a_dotdot_segment` |
| E3 | `engine_dispatch.py:6350` `**({} if leave_out is None else {"leave_out": leave_out})` in the `build_view(...)` call of `_dispatch_review_impl` | on a launch the loaded leave-out reaches the view build | `test_dispatch_review_threads_the_leave_out_file_into_the_view` |

---

## E1 — the survivors filter

- **axis:** a left-out path never reaches the patch: it is dropped from `survivors`, so the `git diff` pathspec batch does not name it.

**neutralization** (`sanitized_view.py`, `_stage_review_diff`):
```python
-        if p not in left_out_set and (p in shown or not _rel_path_would_be_stripped(p))
+        if (p in shown or not _rel_path_would_be_stripped(p))
```

**raw red:** `scripts/pinned-python -B -X pycache_prefix=/tmp/c1l5b-pyc-f -m pytest plugins/superheroes/lib/tests/test_sanitized_view_leave_out_c1l5b.py -q -k test_leave_out_drops_only_the_named_section`
```
F                                                                        [100%]
=================================== FAILURES ===================================
_________________ test_leave_out_drops_only_the_named_section __________________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-9/test_leave_out_drops_only_the_0')

    def test_leave_out_drops_only_the_named_section(tmp_path):
        repo, base = _three_files(tmp_path)
        full = _build(repo, base)
        left = _build(repo, base, leave_out=frozenset({"b.txt"}))
        full_patch, left_patch = _patch(full), _patch(left)
        assert _section_paths(full_patch) == ["a.txt", "b.txt", "c.txt"]
>       assert _section_paths(left_patch) == ["a.txt", "c.txt"]
E       AssertionError: assert ['a.txt', 'b.txt', 'c.txt'] == ['a.txt', 'c.txt']
E         
E         At index 1 diff: 'b.txt' != 'c.txt'
E         Left contains one more item: 'c.txt'
E         Use -v to get more diff

/home/user/wt-2243-f/plugins/superheroes/lib/tests/test_sanitized_view_leave_out_c1l5b.py:123: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_sanitized_view_leave_out_c1l5b.py::test_leave_out_drops_only_the_named_section
1 failed, 37 deselected in 2.62s
```

**restore:** the inverse edit, `if (p in shown or not _rel_path_would_be_stripped(p))` back to `if p not in left_out_set and (p in shown or not _rel_path_would_be_stripped(p))`.

**restore receipt:** the restored lines quoted back from the file (Grep `left_out_set` over `sanitized_view.py` after the edit):
```
1901:    left_out_set = frozenset(left_out or ())
1905:        if p not in left_out_set and _rel_path_would_be_stripped(p) and p not in shown
1910:        if p not in left_out_set and (p in shown or not _rel_path_would_be_stripped(p))
1992:        "calibrationShown": sorted(shown - left_out_set),
```

**raw green:** same command after the restore
```
.                                                                        [100%]
1 passed, 37 deselected in 3.02s
```

---

## E2 — the loader's shape check (representative: the `..` segment check)

- **axis:** `load_leave_out_file` refuses an entry with a `..` segment (`sanitized-view-leave-out-invalid`). Class: "the loader accepts a malformed file". Its other members — non-JSON, wrong schema, extra key, non-list `files`, non-string, blank, absolute, backslash, duplicate — share that failure mode; `..` stands for them. They are not individually neutralized, so each is pinned by a test case (`MALFORMED` in `test_loader_refuses_each_malformed_shape`) whose bite is unproven here.

**neutralization** (`sanitized_view.py`, `load_leave_out_file`):
```python
-        if entry.startswith("/") or "\\" in entry or ".." in entry.split("/"):
+        if entry.startswith("/") or "\\" in entry:
```

**raw red:** `scripts/pinned-python -B -X pycache_prefix=/tmp/c1l5b-pyc-f -m pytest plugins/superheroes/lib/tests/test_sanitized_view_leave_out_c1l5b.py -q -k test_loader_refuses_a_dotdot_segment`
```
FFFF                                                                     [100%]
=================================== FAILURES ===================================
___________________ test_loader_refuses_a_dotdot_segment[..] ___________________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-11/test_loader_refuses_a_dotdot_s0')
entry = '..'

    @pytest.mark.parametrize("entry", ["..", "../x.txt", "a/../b.txt", "a/b/.."])
    def test_loader_refuses_a_dotdot_segment(tmp_path, entry):
>       with pytest.raises(sv.SanitizedViewError) as exc:
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       Failed: DID NOT RAISE SanitizedViewError

/home/user/wt-2243-f/plugins/superheroes/lib/tests/test_sanitized_view_leave_out_c1l5b.py:196: Failed
________________ test_loader_refuses_a_dotdot_segment[../x.txt] ________________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-11/test_loader_refuses_a_dotdot_s1')
entry = '../x.txt'

    @pytest.mark.parametrize("entry", ["..", "../x.txt", "a/../b.txt", "a/b/.."])
    def test_loader_refuses_a_dotdot_segment(tmp_path, entry):
>       with pytest.raises(sv.SanitizedViewError) as exc:
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       Failed: DID NOT RAISE SanitizedViewError

/home/user/wt-2243-f/plugins/superheroes/lib/tests/test_sanitized_view_leave_out_c1l5b.py:196: Failed
_______________ test_loader_refuses_a_dotdot_segment[a/../b.txt] _______________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-11/test_loader_refuses_a_dotdot_s2')
entry = 'a/../b.txt'

    @pytest.mark.parametrize("entry", ["..", "../x.txt", "a/../b.txt", "a/b/.."])
    def test_loader_refuses_a_dotdot_segment(tmp_path, entry):
>       with pytest.raises(sv.SanitizedViewError) as exc:
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       Failed: DID NOT RAISE SanitizedViewError

/home/user/wt-2243-f/plugins/superheroes/lib/tests/test_sanitized_view_leave_out_c1l5b.py:196: Failed
_________________ test_loader_refuses_a_dotdot_segment[a/b/..] _________________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-11/test_loader_refuses_a_dotdot_s3')
entry = 'a/b/..'

    @pytest.mark.parametrize("entry", ["..", "../x.txt", "a/../b.txt", "a/b/.."])
    def test_loader_refuses_a_dotdot_segment(tmp_path, entry):
>       with pytest.raises(sv.SanitizedViewError) as exc:
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       Failed: DID NOT RAISE SanitizedViewError

/home/user/wt-2243-f/plugins/superheroes/lib/tests/test_sanitized_view_leave_out_c1l5b.py:196: Failed
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_sanitized_view_leave_out_c1l5b.py::test_loader_refuses_a_dotdot_segment[..]
FAILED plugins/superheroes/lib/tests/test_sanitized_view_leave_out_c1l5b.py::test_loader_refuses_a_dotdot_segment[../x.txt]
FAILED plugins/superheroes/lib/tests/test_sanitized_view_leave_out_c1l5b.py::test_loader_refuses_a_dotdot_segment[a/../b.txt]
FAILED plugins/superheroes/lib/tests/test_sanitized_view_leave_out_c1l5b.py::test_loader_refuses_a_dotdot_segment[a/b/..]
4 failed, 34 deselected in 3.90s
```

**restore:** the inverse edit, the `or ".." in entry.split("/")` clause put back.

**restore receipt:** the restored lines quoted back from the file (Grep `entry.split("/")` with context):
```
1871-        if not isinstance(entry, str) or not entry.strip():
1872-            raise invalid
1873:        if entry.startswith("/") or "\\" in entry or ".." in entry.split("/"):
1874-            raise invalid
```

**raw green:** same command after the restore
```
....                                                                     [100%]
4 passed, 34 deselected in 3.37s
```

---

## E3 — the launch-path threading of `leave_out` into `build_view`

- **axis:** on a launch the leave-out loaded from `--leave-out-file` reaches `build_view`, so the staged patch actually omits the named sections.

**neutralization** (`engine_dispatch.py`, `_dispatch_review_impl`, the `build_view(...)` call):
```python
                     session_dir=session_dir,
-                    **({} if leave_out is None else {"leave_out": leave_out}),
                 )
```

**raw red:** `scripts/pinned-python -B -X pycache_prefix=/tmp/c1l5b-pyc-f -m pytest plugins/superheroes/lib/tests/test_sanitized_view_leave_out_c1l5b.py -q -k test_dispatch_review_threads_the_leave_out_file_into_the_view`
```
F                                                                        [100%]
=================================== FAILURES ===================================
________ test_dispatch_review_threads_the_leave_out_file_into_the_view _________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-14/test_dispatch_review_threads_t0')

    def test_dispatch_review_threads_the_leave_out_file_into_the_view(tmp_path):
        repo, base = _three_files(tmp_path)
        leave_out_path = _leave_out_file(tmp_path, _doc(["b.txt", "not-in-change.txt"]))
        seen = []
        res = ED.dispatch_review(
            seat=_codex_seat(), prompt_path=_valid_prompt(tmp_path), repo_root=repo,
            run_engine=_clean_review_runner(), build_view=_recording_build_view(seen),
            diff_base=base, leave_out_file=leave_out_path)
        assert res["ok"] is True, res
        assert len(seen) == 1
>       assert seen[0]["kwargs"]["leave_out"] == frozenset({"b.txt", "not-in-change.txt"})
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       KeyError: 'leave_out'

/home/user/wt-2243-f/plugins/superheroes/lib/tests/test_sanitized_view_leave_out_c1l5b.py:309: KeyError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_sanitized_view_leave_out_c1l5b.py::test_dispatch_review_threads_the_leave_out_file_into_the_view
1 failed, 37 deselected in 3.75s
```

Note: the red fires on the first threading assertion (the kwarg the spy sees); the test's later assertions (the staged patch lacks `b.txt`, `diffLeftOut == ["b.txt"]`) would fail on the same neutralization too, but were not reached.

**restore:** the inverse edit, the `**({} if leave_out is None else {"leave_out": leave_out}),` line put back after `session_dir=session_dir,`.

**restore receipt:** the restored line quoted back from the file (Grep `leave_out is None else` with context):
```
engine_dispatch.py-6349-                    session_dir=session_dir,
engine_dispatch.py:6350:                    **({} if leave_out is None else {"leave_out": leave_out}),
engine_dispatch.py-6351-                )
```
`git status --porcelain` after all three restores lists `engine_dispatch.py` and `sanitized_view.py` as modified (the work itself), alongside the other declared deliverables; no residue of a neutralization remains.

**raw green:** same command after the restore
```
.                                                                        [100%]
1 passed, 37 deselected in 2.97s
```
