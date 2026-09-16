# WO-L2-SM (#1269) bite-proof — entry refusal provenance + canary seat binding

**Provenance:** cursor-agent / composer-2.5

## Guarded elements

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| BP-L2SM-1 | `_entry_allowlist_refusal` run_dir threading | G1 refusal on continuation echoes journal `resolvedInputs` | `test_entry_allowlist_refusal_preserves_existing_run_provenance` |
| BP-L2SM-2 | `_resolve_canary_identity` seat-tier binding | mismatched seat key and tier refuses before dispatch | `test_grounding_seat_rejects_mismatched_tier` |

---

## BP-L2SM-1 — entry refusal preserves run provenance

- **axis:** G1 refusal on continuation echoes journal `resolvedInputs` and `runOpened: true`

**neutralization** (`plugins/superheroes/lib/engine_dispatch.py`, both `dispatch_review` and `dispatch_write` call sites): omit `run_dir=run_dir or ""` when calling `_entry_allowlist_refusal` (restores pre-fix omission at both anchors).

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-wo -m pytest plugins/superheroes/lib/tests/test_engine_dispatch.py::test_entry_allowlist_refusal_preserves_existing_run_provenance -q
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
________ test_entry_allowlist_refusal_preserves_existing_run_provenance ________

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/pytest-of-zwrose/pytest-774/test_entry_allowlist_refusal_p0')

    def test_entry_allowlist_refusal_preserves_existing_run_provenance(tmp_path):
        # axis: G1 refusal on continuation echoes journal provenance from active run
        repo_root = _repo(tmp_path)
        run_dir = str(tmp_path / "active-run")
        fake = FakeRunner([])
        ED.dispatch_review(
            seat=_codex_seat(),
            prompt_path=_valid_prompt(tmp_path),
            repo_root=repo_root,
            run_engine=fake,
            build_view=_fake_build_view(tmp_path),
            run_dir=run_dir,
            max_wait=0,
        )
        snapshot_before = _opened_resolved_inputs(run_dir)
        res = ED.dispatch_review(
            seat=_codex_seat(model=_OFF_ALLOWLIST_CODEX),
            prompt_path=_valid_prompt(tmp_path),
            repo_root=repo_root,
            run_engine=_never_call,
            build_view=_never_build_view,
            run_dir=run_dir,
            max_wait=0,
        )
>       _assert_allowlist_refusal(res, run_opened=True)

plugins/superheroes/lib/tests/test_engine_dispatch.py:8947: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

res = {'allowlistGuard': {'allowlist': ['gpt-5.6-sol', 'gpt-5.6-terra'], 'allowlist_pairs': [['gpt-5.6-terra', 'high'], ['gp...amend lib/model_registry.py.; sanctioned pairs: (gpt-5.6-terra, high), (gpt-5.6-sol, high), (gpt-5.6-sol, xhigh)", ...}

    def _assert_allowlist_refusal(res, *, run_opened=False):
        assert res["ok"] is False
        assert res["terminal"] is True
>       assert res.get("runOpened") is run_opened
E       assert False is True
E        +  where False = <built-in method get of dict object at 0x10a9e2e40>('runOpened')
E        +    where <built-in method get of dict object at 0x10a9e2e40> = {'allowlistGuard': {'allowlist': ['gpt-5.6-sol', 'gpt-5.6-terra'], 'allowlist_pairs': [['gpt-5.6-terra', 'high'], ['gp...amend lib/model_registry.py.; sanctioned pairs: (gpt-5.6-terra, high), (gpt-5.6-sol, high), (gpt-5.6-sol, xhigh)", ...}.get

plugins/superheroes/lib/tests/test_engine_dispatch.py:8477: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_entry_allowlist_refusal_preserves_existing_run_provenance
1 failed in 0.54s
```

**restore:** re-add `run_dir=run_dir or ""` at both `_entry_allowlist_refusal` call sites in `dispatch_review` and `dispatch_write`.

**raw green:**
```
.                                                                        [100%]
1 passed in 0.42s
```

---

## BP-L2SM-2 — canary seat key bound to canonical tier

- **axis:** mismatched seat key and tier refuses before dispatch with accepted shape named

**neutralization** (`plugins/superheroes/lib/seat_canary.py`, `_resolve_canary_identity`):
```python
    if False and tier != canonical_tier:  # bite-proof neutralization
```
(replaces `if tier != canonical_tier:`)

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-wo -m pytest plugins/superheroes/lib/tests/test_seat_canary.py::test_grounding_seat_rejects_mismatched_tier -q
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_________________ test_grounding_seat_rejects_mismatched_tier __________________

    def test_grounding_seat_rejects_mismatched_tier():
        # axis: seat key tier binding — grounding-seat requires reviewer, not reviewer-deep
        out = SC.run_canary(
            "grounding-seat",
            _seat_config("codex", "gpt-5.6-sol", "xhigh", "reviewer-deep"),
            repo_root="/r",
        )
        assert out["outcome"] == "unrunnable"
>       assert "requires tier 'reviewer'" in out["detail"]
E       assert "requires tier 'reviewer'" in 'not-dispatched: repo-root-missing'

plugins/superheroes/lib/tests/test_seat_canary.py:1074: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seat_canary.py::test_grounding_seat_rejects_mismatched_tier
1 failed in 0.17s
```

**restore:**
```python
    if tier != canonical_tier:
```

**raw green:**
```
.                                                                        [100%]
1 passed in 0.12s
```
