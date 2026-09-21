# WO FIX-A (#1340 layer 2f r2) bite-proof — dependency gate CLOSED and draft arms

Per-guard bite proof for `_apply_dependency_gate`, the refusal `dependency-closed-unmerged` and the
draft `dependency-not-ready` arm.

**Register:** 3 guards — closed-unmerged refuses, draft skips verdict, lifecycle fallback refuses.

**Method:** the mutation is the smallest possible edit to the **guarded code** (never to the test),
applied through the host's edit action and reverted by the inverse edit. Each proving test is selected
by its **exact node id**, never `-k`.

**Command** (referred to as *the command* below, with `<node-id>` replaced per guard):

```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest "<node-id>" -q
```

## Summary table

| ID | Guarded element (file:line) | Axis | Proving test | Verdict |
|---|---|---|---|---|
| F1 | launcher.py:1569 | closed-unmerged dependency refuses | `test_dependency_gate_closed_unmerged_refuses` | proven |
| F2 | launcher.py:1583 | draft dependency passes not-ready without consulting verdict | `test_dependency_gate_draft_not_ready_passes` | proven |
| F3 | launcher.py:1576 | unrecognised lifecycle from injected reader refuses | `test_dependency_gate_launcher_lifecycle_fallback_refuses` | proven |

---

## F1 — closed-unmerged dependency refuses

**neutralization** (`plugins/superheroes/lib/launcher.py`):

```python
    if pr_lifecycle == "CLOSED":
```
→
```python
    if False:
```

**node id:** `plugins/superheroes/lib/tests/test_launcher.py::test_dependency_gate_closed_unmerged_refuses`

**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_________________ test_dependency_gate_closed_unmerged_refuses _________________

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-3644/test_dependency_gate_closed_un0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x106210730>

    def test_dependency_gate_closed_unmerged_refuses(tmp_path, monkeypatch):
      # axis: closed-unmerged dependency refuses dependency-closed-unmerged
        repo = _init_repo(tmp_path / "repo")
        _ledger_env(tmp_path, monkeypatch)
        log_dir = str(tmp_path / "logs")
        head = _head_sha(repo)

        def reader(pr, repo_name, **kwargs):
            return _pr_vet_state_ok(head, state="CLOSED"), None

        monkeypatch.setattr(
            L.stack_check, "resolve_repo_slug",
            lambda *a, **k: ("owner/repo", None),
        )

        result = L.launch_build(
            repo,
            656,
            _dependency_premise(repo, 701),
            _all_checks(),
            log_dir,
            pr_vet_reader=reader,
        )
        assert result["ok"] is False
>       assert result["reason"] == "dependency-closed-unmerged"
E       AssertionError: assert 'dependency-read-unavailable' == 'dependency-closed-unmerged'
E         
E         - dependency-closed-unmerged
E         + dependency-read-unavailable

plugins/superheroes/lib/tests/test_launcher.py:7008: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher.py::test_dependency_gate_closed_unmerged_refuses
1 failed in 0.58s
```

**raw green** after the inverse edit:
```
.                                                                        [100%]
1 passed in 0.55s
```

## F2 — draft dependency passes not-ready without consulting verdict

**neutralization:**

```python
    if pr_state.get("isDraft"):
```
→
```python
    if False:
```

**node id:** `plugins/superheroes/lib/tests/test_launcher.py::test_dependency_gate_draft_not_ready_passes`

**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_________________ test_dependency_gate_draft_not_ready_passes __________________

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-3646/test_dependency_gate_draft_not0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x10252e730>

    def test_dependency_gate_draft_not_ready_passes(tmp_path, monkeypatch):
      # axis: OPEN draft with READY verdict passes dependency-not-ready, not applied
        repo = _init_repo(tmp_path / "repo")
        _ledger_env(tmp_path, monkeypatch)
        log_dir = str(tmp_path / "logs")
        head = _head_sha(repo)

        def reader(pr, repo_name, **kwargs):
            return _pr_vet_state_ok(
                head, _ready_vet_body(head), state="OPEN", is_draft=True,
            ), None

        def refusing_vet(*args, **kwargs):
            raise AssertionError("draft dependency must not consult verdict")

        monkeypatch.setattr(
            L.stack_check, "resolve_repo_slug",
            lambda *a, **k: ("owner/repo", None),
        )
        monkeypatch.setattr(L.stack_check, "read_vet_verdict", refusing_vet)

>       result = L.launch_build(
            repo,
            656,
            _dependency_premise(repo, 701),
            _all_checks(),
            log_dir,
            spawn_fn=_make_spawn_fn("sleep"),
            settle_seconds=0.2,
            pr_vet_reader=reader,
        )

plugins/superheroes/lib/tests/test_launcher.py:7071: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
plugins/superheroes/lib/launcher.py:1761: in launch_build
    gate_result = _apply_dependency_gate(
plugins/superheroes/lib/launcher.py:1588: in _apply_dependency_gate
    verdict, vet_refusal = stack_check.read_vet_verdict(
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

args = ('<!-- superheroes:advisor-vet -->\n**Verdict: READY** · ce537c26820ea2de3339ac4823a8415570609d7a', 'ce537c26820ea2de3339ac4823a8415570609d7a')
kwargs = {}

    def refusing_vet(*args, **kwargs):
>       raise AssertionError("draft dependency must not consult verdict")
E       AssertionError: draft dependency must not consult verdict

plugins/superheroes/lib/tests/test_launcher.py:7063: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher.py::test_dependency_gate_draft_not_ready_passes
1 failed in 0.46s
```

**raw green:**
```
.                                                                        [100%]
1 passed in 0.98s
```

## F3 — unrecognised lifecycle from injected reader refuses

**neutralization** (`plugins/superheroes/lib/launcher.py`):

```python
    if pr_lifecycle != "OPEN":
```
→
```python
    if False:
```

**node id:** `plugins/superheroes/lib/tests/test_launcher.py::test_dependency_gate_launcher_lifecycle_fallback_refuses`

**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
___________ test_dependency_gate_launcher_lifecycle_fallback_refuses ___________

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-3683/test_dependency_gate_launcher_0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x104823b80>

    def test_dependency_gate_launcher_lifecycle_fallback_refuses(tmp_path, monkeypatch):
      # axis: launcher fallback refuses unrecognised lifecycle from injected reader
        repo = _init_repo(tmp_path / "repo")
        _ledger_env(tmp_path, monkeypatch)
        log_dir = str(tmp_path / "logs")
        head = _head_sha(repo)

        def reader(pr, repo_name, **kwargs):
            return _pr_vet_state_ok(head, state="UNKNOWN"), None

        monkeypatch.setattr(
            L.stack_check, "resolve_repo_slug",
            lambda *a, **k: ("owner/repo", None),
        )

        result = L.launch_build(
            repo,
            656,
            _dependency_premise(repo, 701),
            _all_checks(),
            log_dir,
            pr_vet_reader=reader,
        )
>       assert result["ok"] is False
E       assert True is False

plugins/superheroes/lib/tests/test_launcher.py:6965: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher.py::test_dependency_gate_launcher_lifecycle_fallback_refuses
1 failed in 21.06s
```

**raw green** after the inverse edit:
```
.                                                                        [100%]
1 passed in 0.58s
```

## Restore receipt

Restored lines quoted above in `_apply_dependency_gate` after each guard (`if pr_lifecycle == "CLOSED":`,
`if pr_state.get("isDraft"):`, and `if pr_lifecycle != "OPEN":`).
