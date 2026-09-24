# WO-B (#1340 layer 2f) bite-proof — the dependency gate in launcher.py

Per-guard bite proof for `_apply_dependency_gate`, the refusal `dependency-open-ready-pr` and its
read-failure sibling `dependency-read-unavailable`.

**Register:** 4 guards — base-equality, READY-only, merged-not-gated, verdict-refusal-refuses.

**Provenance:** the guarded code is cursor / composer-2.5 (WO-B). This record was re-run at the
current head after the gate gained MERGED/CLOSED/draft/lifecycle-fallback arms (FIX-H1).

**Head:** `a394fc2ba355933e27ddde9ae0baabb7115c5ebc`

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
| D1 | launcher.py:1605 | the resolved base must equal the dependency's current head | `test_dependency_gate_ready_base_mismatch_refuses` | proven |
| D2 | launcher.py:1598 | only `VERDICT_READY` gates; every other verdict passes | `test_dependency_gate_not_ready_passes` | proven |
| D3 | launcher.py:1563 | merged dependency passes without applying gate | `test_dependency_gate_merged_passes_not_gated` | proven |
| D4 | launcher.py:1591 | an unreadable verdict **refuses**, never passes as absent | `test_dependency_gate_vet_refusal_refuses` | proven |

---

## D1 — the resolved base must equal the dependency's current head

**neutralization** (`plugins/superheroes/lib/launcher.py`):

```python
    if resolved_base_commit == head_sha:
```
→
```python
    if True:
```

**node id:** `plugins/superheroes/lib/tests/test_launcher.py::test_dependency_gate_ready_base_mismatch_refuses`

**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_______________ test_dependency_gate_ready_base_mismatch_refuses _______________

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-3698/test_dependency_gate_ready_bas0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x102c337c0>

    def test_dependency_gate_ready_base_mismatch_refuses(tmp_path, monkeypatch):
      # axis: READY dependency with wrong base refuses dependency-open-ready-pr
        repo = _init_repo(tmp_path / "repo")
        _ledger_env(tmp_path, monkeypatch)
        log_dir = str(tmp_path / "logs")
        head = _head_sha(repo)
        dep_head = "a" * 40

        def reader(pr, repo_name, **kwargs):
            return _pr_vet_state_ok(dep_head, _ready_vet_body(dep_head)), None

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

plugins/superheroes/lib/tests/test_launcher.py:7253: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher.py::test_dependency_gate_ready_base_mismatch_refuses
1 failed in 21.21s
```

**raw green** after the inverse edit:
```
.                                                                        [100%]
1 passed in 0.74s
```

**restored lines:**
```python
    if resolved_base_commit == head_sha:
```

## D2 — only `VERDICT_READY` gates

**neutralization:**

```python
    if verdict != stack_check.VERDICT_READY:
```
→
```python
    if False:
```

**node id:** `plugins/superheroes/lib/tests/test_launcher.py::test_dependency_gate_not_ready_passes`

**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
____________________ test_dependency_gate_not_ready_passes _____________________

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-3705/test_dependency_gate_not_ready0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x104059730>

    def test_dependency_gate_not_ready_passes(tmp_path, monkeypatch):
      # axis: VET_NOT_READY passes as dependency-not-ready
        repo = _init_repo(tmp_path / "repo")
        _ledger_env(tmp_path, monkeypatch)
        log_dir = str(tmp_path / "logs")
        head = _head_sha(repo)

        def reader(pr, repo_name, **kwargs):
            return _pr_vet_state_ok(head, body="no vet marker"), None

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
            spawn_fn=_make_spawn_fn("sleep"),
            settle_seconds=0.2,
            pr_vet_reader=reader,
        )
        assert result["ok"] is True
>       assert result["dependencyGate"] == {
            "applied": False,
            "reason": "dependency-not-ready",
        }
E       AssertionError: assert {'applied': T...et-not-ready'} == {'applied': F...cy-not-ready'}
E         
E         Differing items:
E         {'applied': True} != {'applied': False}
E         Left contains 3 more items:
E         {'dependency': 701,
E          'dependencyHead': '798465ccf902a70e25cbd47beccb9881c3571dc8',
E          'verdict': 'vet-not-ready'}...
E         
E         ...Full output truncated (3 lines hidden), use '-vv' to show

plugins/superheroes/lib/tests/test_launcher.py:7181: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher.py::test_dependency_gate_not_ready_passes
1 failed in 1.33s
```

**raw green:**
```
.                                                                        [100%]
1 passed in 1.23s
```

**restored lines:**
```python
    if verdict != stack_check.VERDICT_READY:
```

## D3 — merged dependency passes without applying gate

At this head the old `pr_state["state"] != "OPEN"` guard is gone; the merged arm at line 1563
carries the same axis — a merged dependency is not gated.

**neutralization:**

```python
    if pr_lifecycle == "MERGED":
```
→
```python
    if False:
```

**node id:** `plugins/superheroes/lib/tests/test_launcher.py::test_dependency_gate_merged_passes_not_gated`

**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_________________ test_dependency_gate_merged_passes_not_gated _________________

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-3707/test_dependency_gate_merged_pa0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x106845670>

    def test_dependency_gate_merged_passes_not_gated(tmp_path, monkeypatch):
      # axis: merged dependency passes without applying gate
        repo = _init_repo(tmp_path / "repo")
        _ledger_env(tmp_path, monkeypatch)
        log_dir = str(tmp_path / "logs")
        head = _head_sha(repo)

        def reader(pr, repo_name, **kwargs):
            return _pr_vet_state_ok(head, state="MERGED"), None

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
            spawn_fn=_make_spawn_fn("sleep"),
            settle_seconds=0.2,
            pr_vet_reader=reader,
        )
>       assert result["ok"] is True
E       assert False is True

plugins/superheroes/lib/tests/test_launcher.py:7067: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher.py::test_dependency_gate_merged_passes_not_gated
1 failed in 0.72s
```

**raw green:**
```
.                                                                        [100%]
1 passed in 1.29s
```

**restored lines:**
```python
    if pr_lifecycle == "MERGED":
```

## D4 — an unreadable verdict refuses

**neutralization:**

```python
    if vet_refusal is not None:
```
→
```python
    if False:
```

**node id:** `plugins/superheroes/lib/tests/test_launcher.py::test_dependency_gate_vet_refusal_refuses`

**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
___________________ test_dependency_gate_vet_refusal_refuses ___________________

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-3709/test_dependency_gate_vet_refus0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x1015a2be0>

    def test_dependency_gate_vet_refusal_refuses(tmp_path, monkeypatch):
      # axis: unreadable vet refuses dependency-read-unavailable
        repo = _init_repo(tmp_path / "repo")
        _ledger_env(tmp_path, monkeypatch)
        log_dir = str(tmp_path / "logs")
        head = _head_sha(repo)

        def reader(pr, repo_name, **kwargs):
            return _pr_vet_state_ok(head, body="no vet marker"), None

        def refusing_vet(body, head_sha):
            return None, {
                "reason": L.stack_check.REASON_VET_UNREADABLE,
                "detail": "vet unreadable",
            }

        monkeypatch.setattr(
            L.stack_check, "resolve_repo_slug",
            lambda *a, **k: ("owner/repo", None),
        )
        monkeypatch.setattr(L.stack_check, "read_vet_verdict", refusing_vet)

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

plugins/superheroes/lib/tests/test_launcher.py:7150: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher.py::test_dependency_gate_vet_refusal_refuses
1 failed in 21.12s
```

**raw green:**
```
.                                                                        [100%]
1 passed in 0.73s
```

**restored lines:**
```python
    if vet_refusal is not None:
```

## Restore receipt

All four proofs were run at head `a394fc2ba355933e27ddde9ae0baabb7115c5ebc` with targeted
neutralizations applied and reverted by inverse edit. Confirmation run:
319 passed (`test_launcher.py -q -n auto`).

**`git status --porcelain` after all restores:**
```
 M plugins/superheroes/lib/tests/bite_proofs/wo_1340_l2f_dependency_gate.md
 M plugins/superheroes/lib/tests/bite_proofs/wo_1340_l2f_verdict_reader.md
```
