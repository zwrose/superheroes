# WO-11 (#1269) bite-proof — spawn sandbox derived from runKind, not journal roleKind

**Provenance:** cursor-agent / composer-2.5

## Guarded elements

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| BP-11-1 | `_canonical_spawn_argv` runKind/roleKind coherence | review run with journal roleKind build must not reach write-capable sandbox | `test_spawn_sandbox_role_kind_follows_run_kind_not_journal` |

---

## BP-11-1 — sandbox selector follows validated runKind

- **axis:** runKind review with journal roleKind build must not reach write-capable sandbox

**neutralization** (`plugins/superheroes/lib/engine_dispatch.py`, `_canonical_spawn_argv` — restore journal roleKind as sandbox selector):
```python
    run_kind = opened.get("runKind", RUN_KIND_REVIEW)
    role_kind = opened.get("roleKind")  # bite-proof neutralization — journal roleKind selects sandbox
    if not isinstance(role_kind, str):
        role_kind = RUN_KIND_REVIEW if run_kind == RUN_KIND_REVIEW else "build"
```
(replaces the runKind-derived expected_role_kind check and refusal)

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-wo -m pytest plugins/superheroes/lib/tests/test_engine_dispatch.py::test_spawn_sandbox_role_kind_follows_run_kind_not_journal -q
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
__________ test_spawn_sandbox_role_kind_follows_run_kind_not_journal ___________

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/pytest-of-zwrose/pytest-708/test_spawn_sandbox_role_kind_f0')

    def test_spawn_sandbox_role_kind_follows_run_kind_not_journal(tmp_path):
        # axis: runKind review with journal roleKind build must not reach write-capable sandbox
        run_dir = str(tmp_path / "spawn-sandbox-role-kind")
        os.makedirs(run_dir, exist_ok=True)
        seat = _codex_seat()
        opened = {
            "kind": "run-opened",
            "runKind": ED.RUN_KIND_REVIEW,
            "roleKind": "build",
            "engine": "codex",
            "argv": _codex_argv_for_run(seat, "review", run_dir),
            "cwd": run_dir,
            "resolvedInputs": _spawn_gate_resolved_inputs(seat),
        }
        canonical, err = ED._canonical_spawn_argv(opened)
>       assert canonical is None
E       AssertionError: assert ['codex', 'exec', '--sandbox', 'workspace-write', '-m', 'gpt-5.6-sol', ...] is None

plugins/superheroes/lib/tests/test_engine_dispatch.py:8786: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_spawn_sandbox_role_kind_follows_run_kind_not_journal
1 failed in 0.62s
```

**restore:** reinstated runKind-derived `expected_role_kind` with disagreement refusal before `build_argv_result`.

**restore receipt:** `_canonical_spawn_argv` derives `expected_role_kind` from `runKind`, refuses when journal `roleKind` disagrees, and passes only `expected_role_kind` to `build_argv_result`.

**raw green:**
```
.                                                                        [100%]
1 passed in 0.52s
```
