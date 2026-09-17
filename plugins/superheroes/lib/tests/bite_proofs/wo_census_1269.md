# WO-CENSUS (#1269) bite-proof — entry-refusal reason census

**Provenance:** cursor / composer-2.5 (implementer). **All three elements were re-run by the
orchestrator on 2026-09-17** in a detached probe worktree (`/private/tmp/wh1269o5-bp` at
`e79c7aa8`), red and green, with the neutralization applied and reverted through targeted edits.
BP-CENSUS-1 and BP-CENSUS-2 reproduced as the implementer recorded them. **BP-CENSUS-3 did not** —
its first record was vacuous and was rejected and re-taken; see the note in that section.

## Guarded elements

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| BP-CENSUS-1 | `ENTRY_REFUSAL_REASONS` in `seat_bundle.py` | closed vocabulary includes `unrunnable` | `test_entry_refusal_reason_census_provenance_by_declared_set` |
| BP-CENSUS-2 | `_entry_refusal_terminal` undeclared-reason refusal | planted reason becomes `entry-reason-undeclared` | `test_entry_refusal_chokepoint_rejects_undeclared_reason` |
| BP-CENSUS-3 | behavioural census opened-run provenance | opened run echoes `runOpened: true` | `test_entry_refusal_reason_census_provenance_by_declared_set` |

---

## BP-CENSUS-1 — declaration includes unrunnable

- **axis:** closed vocabulary includes `unrunnable`

**neutralization** (`plugins/superheroes/lib/seat_bundle.py`, `ENTRY_REFUSAL_REASONS`):
```python
    # "unrunnable",  # bite-proof neutralization
```
(replaces `"unrunnable",`)

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_engine_dispatch.py::test_entry_refusal_reason_census_provenance_by_declared_set -q
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_________ test_entry_refusal_reason_census_provenance_by_declared_set __________

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/pytest-of-zwrose/pytest-874/test_entry_refusal_reason_cens0')

    def test_entry_refusal_reason_census_provenance_by_declared_set(tmp_path):
        """Every declared entry-refusal reason carries run provenance at the chokepoint."""
>       assert ED.dispatch_outcome.REASON_UNRUNNABLE in ED.seat_bundle.ENTRY_REFUSAL_REASONS
E       AssertionError: assert 'unrunnable' in frozenset({'allowlist-malformed', 'allowlist-raised', 'allowlist-refused', 'effort-invalid', 'effort-key-absent', 'effort-token-conflict', ...})
E        +  where 'unrunnable' = <module 'dispatch_outcome' from '/Users/zwrose/.superheroes-worktrees/superheroes/issue-1269-b8b9f9e4d3861fcf/plugins/superheroes/lib/dispatch_outcome.py'>.REASON_UNRUNNABLE
E        +    where <module 'dispatch_outcome' from '/Users/zwrose/.superheroes-worktrees/superheroes/issue-1269-b8b9f9e4d3861fcf/plugins/superheroes/lib/dispatch_outcome.py'> = ED.dispatch_outcome
E        +  and   frozenset({'allowlist-malformed', 'allowlist-raised', 'allowlist-refused', 'effort-invalid', 'effort-key-absent', 'effort-token-conflict', ...}) = <module 'seat_bundle' from '/Users/zwrose/.superheroes-worktrees/superheroes/issue-1269-b8b9f9e4d3861fcf/plugins/superheroes/lib/seat_bundle.py'>.ENTRY_REFUSAL_REASONS
E        +    where <module 'seat_bundle' from '/Users/zwrose/.superheroes-worktrees/superheroes/issue-1269-b8b9f9e4d3861fcf/plugins/superheroes/lib/seat_bundle.py'> = ED.seat_bundle

plugins/superheroes/lib/tests/test_engine_dispatch.py:9086: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_entry_refusal_reason_census_provenance_by_declared_set
1 failed in 0.53s
```

**restore** (`plugins/superheroes/lib/seat_bundle.py`, `ENTRY_REFUSAL_REASONS`):
```python
    "unrunnable",
```

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.47s
```

---

## BP-CENSUS-2 — chokepoint refuses undeclared reason

- **axis:** planted reason becomes `entry-reason-undeclared`

**neutralization** (`plugins/superheroes/lib/engine_dispatch.py`, `_entry_refusal_terminal`):
```python
    if False and (not isinstance(reason, str) or reason not in seat_bundle.ENTRY_REFUSAL_REASONS):  # bite-proof neutralization
```
(replaces the undeclared-reason guard condition)

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_engine_dispatch.py::test_entry_refusal_chokepoint_rejects_undeclared_reason -q
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
___________ test_entry_refusal_chokepoint_rejects_undeclared_reason ____________

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/pytest-of-zwrose/pytest-876/test_entry_refusal_chokepoint_0')

    def test_entry_refusal_chokepoint_rejects_undeclared_reason(tmp_path):
        """Undeclared entry-refusal reasons fail closed at both chokepoints."""
        planted_reason = "planted-not-in-vocabulary"
        refusal = {"ok": False, "reason": planted_reason, "detail": "census-probe"}

        terminal = ED._entry_refusal_terminal(refusal, run_dir=None)
>       assert terminal["reason"] == ED.seat_bundle.ENTRY_REASON_UNDECLARED
E       AssertionError: assert 'planted-not-in-vocabulary' == 'entry-reason-undeclared'
E         
E         - entry-reason-undeclared
E         + planted-not-in-vocabulary

plugins/superheroes/lib/tests/test_engine_dispatch.py:9118: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_entry_refusal_chokepoint_rejects_undeclared_reason
1 failed in 0.53s
```

**restore** (`plugins/superheroes/lib/engine_dispatch.py`, `_entry_refusal_terminal`):
```python
    if not isinstance(reason, str) or reason not in seat_bundle.ENTRY_REFUSAL_REASONS:
```

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.47s
```

---

## BP-CENSUS-3 — behavioural census opened-run provenance

- **axis:** opened run echoes `runOpened: true`

**Re-taken by the orchestrator, 2026-09-17.** The implementer's first attempt at this element
neutralized the **test's own assertion** (`assert with_run.get("runOpened") is True` inverted to
`is False`) and showed the test fail. That is a vacuous proof: it demonstrates only that an inverted
assertion fails, and says nothing about the guarded behaviour, because the detector was **edited**
when it was shown red. It was rejected and re-taken below against production code with the detector
unedited. Probe worktree: detached `/private/tmp/wh1269o5-bp` at `e79c7aa8`.

**neutralization** (`plugins/superheroes/lib/engine_dispatch.py`, `_entry_refusal_terminal`):
```python
    run_dir_value = ""  # bite-proof neutralization
```
(replaces `run_dir_value = run_dir or ""`, so an opened run is never looked up and no run
provenance is attached)

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_engine_dispatch.py::test_entry_refusal_reason_census_provenance_by_declared_set -q
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_________ test_entry_refusal_reason_census_provenance_by_declared_set __________

        """Every declared entry-refusal reason carries run provenance at the chokepoint."""
        assert ED.dispatch_outcome.REASON_UNRUNNABLE in ED.seat_bundle.ENTRY_REFUSAL_REASONS
        assert ED.seat_bundle.ENTRY_REASON_UNDECLARED in ED.seat_bundle.ENTRY_REFUSAL_REASONS
    
        run_dir = str(tmp_path / "census-run")
        _manual_open_review_run(tmp_path, run_dir)
        run_dir_real = os.path.realpath(run_dir)
        snapshot = _opened_resolved_inputs(run_dir)
    
        for reason in sorted(ED.seat_bundle.ENTRY_REFUSAL_REASONS):
            refusal = {"ok": False, "reason": reason, "detail": "census-probe"}
    
            no_run = ED._entry_refusal_terminal(refusal, run_dir=None)
            assert no_run["reason"] == reason
            assert no_run.get("runOpened") is False
            assert no_run["runDir"] == ""
            assert no_run.get("resolvedInputsStatus") is None
            assert "resolvedInputs" not in no_run
    
            with_run = ED._entry_refusal_terminal(refusal, run_dir=run_dir)
            assert with_run["reason"] == reason
>           assert with_run.get("runOpened") is True
E           AssertionError: assert False is True
E            +  where False = <built-in method get of dict object at 0x10952be00>('runOpened')
E            +    where <built-in method get of dict object at 0x10952be00> = {'argv': [], 'attempts': 0, 'detail': 'census-probe', 'forfeited': False, ...}.get

plugins/superheroes/lib/tests/test_engine_dispatch.py:9106: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_entry_refusal_reason_census_provenance_by_declared_set
1 failed in 0.53s
```

Note the failing line: `assert with_run.get("runOpened") is True` — **the detector's own
assertion, unedited**. The red comes from production code that stopped attaching run provenance.

**restore** (`plugins/superheroes/lib/engine_dispatch.py`, `_entry_refusal_terminal`):
```python
    run_dir_value = run_dir or ""
```
(`git status --porcelain` in the probe worktree empty after restore)

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.45s
```
