# WO-L (#1340 layer 2g) bite-proof — seat runtime classification and case-insensitive commit compare

Per-guard bite proof for `_is_claude_code_runtime`, `_same_commit`, and the Part-3 hermetic test fixes.

**Register:** 4 guards — G-B8a (versioned layout arm), G-B8b (fail-closed classification), G-CASE (`.lower()` normalization), G-HERM (gh-less PATH hermeticity).

**Provenance:** cursor / composer-2.5 (WO-L).

**Method:** targeted neutralization applied through the edit tool and reverted by inverse edit; each proving test selected by exact node id.

**Command** (referred to as *the command* below, with `<node-id>` replaced per guard):

```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest "<node-id>" -q -p no:cacheprovider
```

## Summary table

| ID | Guarded element (file:line) | Axis | Proving test | Verdict |
|---|---|---|---|---|
| G-B8a | launcher.py:347 | versioned `…/claude/versions/<semver>` layout arm | `test_seat_config_dir_reads_versioned_binary_instance` | proven |
| G-B8b | launcher.py:338 | fail-closed non-runtime classification | `test_seat_config_dir_reports_seat_not_claude_for_non_runtime_exec` | proven |
| G-CASE | stack_check.py:829 | `.lower()` normalization in `same_commit` | `test_dependency_gate_passes_when_github_head_is_uppercase`, `test_stack_gate_passes_when_github_heads_are_uppercase`, `test_same_commit_mixed_case_equal` | proven |
| G-HERM | test_launcher.py (Part 3) | tests pass with `gh` absent from PATH | three Part-3 node ids under gh-less PATH | proven (change proof, not a product guard) |

---

## G-B8a — versioned layout arm

**neutralization** (`plugins/superheroes/lib/launcher.py`):

```python
    if parent == "versions" and grandparent == "claude":
```
→
```python
    if False:
```

**node id:** `plugins/superheroes/lib/tests/test_launcher.py::test_seat_config_dir_reads_versioned_binary_instance`

**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_____________ test_seat_config_dir_reads_versioned_binary_instance _____________

    def test_seat_config_dir_reads_versioned_binary_instance(
        monkeypatch, unpatched_seat_config_dir,
    ):
        ...
        result = L.seat_config_dir()
>       assert result == {
            "instance": os.path.normpath("/Users/u/.claude-four"),
            "reason": None,
        }
E       AssertionError: assert {'instance': ...t-not-claude'} == {'instance': ...reason': None}
```

**raw green:**
```
.                                                                        [100%]
1 passed in 0.50s
```

**restored lines:**
```python
    if parent == "versions" and grandparent == "claude":
```

## G-B8b — fail-closed classification

**neutralization:**

```python
def _is_claude_code_runtime(snapshot):
    exec_path = snapshot.get("exec_path") if isinstance(snapshot, dict) else None
    ...
```
→
```python
def _is_claude_code_runtime(snapshot):
    return True
```

**node id:** `plugins/superheroes/lib/tests/test_launcher.py::test_seat_config_dir_reports_seat_not_claude_for_non_runtime_exec`

**raw red:**
```
FFFFFF                                                                   [100%]
=================================== FAILURES ===================================
___ test_seat_config_dir_reports_seat_not_claude_for_non_runtime_exec[None] ____
        result = L.seat_config_dir()
>       assert result["instance"] is None
E       AssertionError: assert '/Users/u/.claude-four' is None
...
6 failed in 1.31s
```

**raw green:**
```
......                                                                   [100%]
6 passed in 0.75s
```

**restored lines:** full `_is_claude_code_runtime` body with structural checks.

## G-CASE — `.lower()` normalization

Re-run after the rule moved to stack_check.same_commit (FIX-A).

**neutralization** (`plugins/superheroes/lib/stack_check.py` `same_commit`):

```python
    return isinstance(a, str) and isinstance(b, str) and a.lower() == b.lower()
```
→
```python
    return isinstance(a, str) and isinstance(b, str) and a == b
```

**node ids:** `test_dependency_gate_passes_when_github_head_is_uppercase`, `test_stack_gate_passes_when_github_heads_are_uppercase`, `test_same_commit_mixed_case_equal`

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_launcher.py::test_dependency_gate_passes_when_github_head_is_uppercase plugins/superheroes/lib/tests/test_launcher.py::test_stack_gate_passes_when_github_heads_are_uppercase plugins/superheroes/lib/tests/test_stack_check.py::test_same_commit_mixed_case_equal -q -p no:cacheprovider
```

**raw red:**
```
FFF                                                                      [100%]
=================================== FAILURES ===================================
__________ test_dependency_gate_passes_when_github_head_is_uppercase ___________

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/pytest-of-zwrose/pytest-572/test_dependency_gate_passes_wh0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x10561eaf0>

    def test_dependency_gate_passes_when_github_head_is_uppercase(tmp_path, monkeypatch):
      # axis: dependency gate compares commit ids case-insensitively (T-CASE-DEP)
        ...
>       assert result["ok"] is True
E       assert False is True

plugins/superheroes/lib/tests/test_launcher.py:7419: AssertionError
____________ test_stack_gate_passes_when_github_heads_are_uppercase ____________

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/pytest-of-zwrose/pytest-572/test_stack_gate_passes_when_gi0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x1055de490>

    def test_stack_gate_passes_when_github_heads_are_uppercase(tmp_path, monkeypatch):
      # axis: stack gate compares commit ids case-insensitively (T-CASE-STACK)
        ...
>       assert result["ok"] is True
E       assert False is True

plugins/superheroes/lib/tests/test_launcher.py:6879: AssertionError
______________________ test_same_commit_mixed_case_equal _______________________

    def test_same_commit_mixed_case_equal():
        sha = "abcdef0123456789abcdef0123456789abcdef01"
>       assert sc.same_commit(sha, sha.upper()) is True
E       AssertionError: assert False is True

plugins/superheroes/lib/tests/test_stack_check.py:1350: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher.py::test_dependency_gate_passes_when_github_head_is_uppercase
FAILED plugins/superheroes/lib/tests/test_launcher.py::test_stack_gate_passes_when_github_heads_are_uppercase
FAILED plugins/superheroes/lib/tests/test_stack_check.py::test_same_commit_mixed_case_equal
3 failed in 2.26s
```

**raw green:**
```
...                                                                      [100%]
3 passed in 2.74s
```

**restored lines:**
```python
    return isinstance(a, str) and isinstance(b, str) and a.lower() == b.lower()
```

## G-HERM — gh-less PATH hermeticity (change proof, not a product guard)

**neutralization:** none — the red run is the three Part-3 node ids under gh-less PATH **before** the test-side `shutil.which` monkeypatch.

**command:**
```
env PATH=/usr/bin:/bin:/usr/sbin:/sbin /usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_launcher.py::test_stack_gate_zero_entry_candidates_refuses plugins/superheroes/lib/tests/test_launcher.py::test_stack_gate_two_entry_candidates_refuses plugins/superheroes/lib/tests/test_launcher.py::test_dependency_gate_unrecognised_pr_state_refuses -q -p no:cacheprovider
```

**raw red:**
```
FFF                                                                      [100%]
...
E       AssertionError: assert 'stack-read-unavailable' == 'base-not-layer-head'
...
E       AssertionError: assert 'detail' not in {'detail': 'gh not on PATH', ...}
...
E       AssertionError: assert 'UNKNOWN' in 'gh not on PATH'
3 failed in 1.19s
```

**raw green** (same command after test-side `shutil.which` monkeypatch):
```
...                                                                      [100%]
3 passed in 3.57s
```
