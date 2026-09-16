# WO-1 (#1269) bite-proofs — dispatch entry chokepoint

**Provenance:** cursor-agent / composer-2.5

## Guarded elements

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| BP-1 | `resolve_entry` mode/role coherence leg | `--mode brief-check` with a `reviewer` seat refuses before allowlist | `test_brief_check_mode_reviewer_seat_refused` |
| BP-2 | `_normalize_allowlist_verdict` semantic success gate | empty `allowlist_pairs` on `ok: True` refuses | `test_semantic_allowlist_verdict_empty_pairs_refused` |
| BP-3 | `_parse_entry_dict` required `role` key | missing `role` key refuses | `test_role_key_absent_refused` |
| BP-4 | `_spawn_allowlist_verdict` resolver call | off-allowlist journal seat refuses at spawn | `test_run_child_spawn_gate_refuses_off_allowlist_snapshot` |

---

## BP-1 — mode/role coherence

- **axis:** `--mode brief-check` with a `reviewer` seat refuses before allowlist

**neutralization** (removed mode/role leg in `resolve_entry`):
```python
    if mode == _MODE_BRIEF_CHECK and role != "brief-check":
        return _mode_role_coherence_refusal(role)
```

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_seat_bundle.py::test_brief_check_mode_reviewer_seat_refused -q
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_________________ test_brief_check_mode_reviewer_seat_refused __________________

    def test_brief_check_mode_reviewer_seat_refused():
        resolved = SB.resolve_entry(
            _seat_json("codex", "gpt-5.6-sol", "xhigh", _REVIEW_ROLE),
            verb="dispatch-review",
            mode="brief-check",
        )
>       assert resolved["ok"] is False
E       assert True is False

plugins/superheroes/lib/tests/test_seat_bundle.py:324: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seat_bundle.py::test_brief_check_mode_reviewer_seat_refused
1 failed in 0.11s
```

**restore:** reinstated the mode/role coherence block in `resolve_entry`.

**restore receipt:**
```python
    if mode == _MODE_BRIEF_CHECK and role != "brief-check":
        return _mode_role_coherence_refusal(role)
```

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.10s
```

---

## BP-2 — semantic success verdict

- **axis:** empty `allowlist_pairs` on `ok: True` refuses

**neutralization** (`_normalize_allowlist_verdict` accepts any `ok: True`):
```python
    if verdict.get("ok") is True:
        return {"ok": True, "allowlistVerdict": verdict}
```

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_seat_bundle.py::test_semantic_allowlist_verdict_empty_pairs_refused -q
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_____________ test_semantic_allowlist_verdict_empty_pairs_refused ______________

    def test_semantic_allowlist_verdict_empty_pairs_refused(monkeypatch):
        def _fake_validate(role, vendor, model, effort):
            return {"ok": True, "reason": None, "allowlist": [], "allowlist_pairs": []}

        monkeypatch.setattr(DG, "validate", _fake_validate)
        resolved = SB.resolve_entry(
            _seat_json("codex", "gpt-5.6-sol", "high"),
            verb="guard-check",
        )
>       assert resolved["ok"] is False
E       assert True is False

plugins/superheroes/lib/tests/test_seat_bundle.py:338: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seat_bundle.py::test_semantic_allowlist_verdict_empty_pairs_refused
1 failed in 0.11s
```

**restore:** removed the early `ok: True` accept; semantic field checks restored.

**restore receipt:** `_normalize_allowlist_verdict` again requires echoed role/vendor, model_id/resolved_model, effort, non-empty `allowlist_pairs`, and membership of the resolved pair.

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.10s
```

---

## BP-3 — role required in seat

- **axis:** missing `role` key refuses

**neutralization** (`_parse_entry_dict` defaults missing role):
```python
    if "role" not in obj:
        obj = dict(obj)
        obj["role"] = "reviewer"
```

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_seat_bundle.py::test_role_key_absent_refused -q
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_________________________ test_role_key_absent_refused _________________________

    def test_role_key_absent_refused():
        raw = json.dumps({"vendor": "cursor", "model": "composer-2.5", "effort": None})
        resolved = SB.resolve_entry(raw, verb="guard-check")
        assert resolved["ok"] is False
>       assert resolved["reason"] == "role-key-absent"
E       AssertionError: assert 'allowlist-refused' == 'role-key-absent'

plugins/superheroes/lib/tests/test_seat_bundle.py:289: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seat_bundle.py::test_role_key_absent_refused
1 failed in 0.11s
```

**restore:** reinstated the `role-key-absent` refusal block in `_parse_entry_dict`.

**restore receipt:**
```python
    if "role" not in obj:
        return _entry_refusal(
            "role-key-absent",
            (
                'JSON seat must include the "role" key; '
                f"accepted: {_ACCEPTED_SEAT}; {accepted_role_detail()}"
            ),
        )
```

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.10s
```

---

## BP-4 — snapshot-fed spawn gate

- **axis:** off-allowlist journal seat refuses at spawn before engine Popen

**neutralization** (`_spawn_allowlist_verdict` bypasses `resolve_entry`):
```python
    resolved = {"ok": True, "allowlistVerdict": {"ok": True, "reason": None, "allowlist": [], "allowlist_pairs": [["gpt-5.6-sol", "high"]]}}
```

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_engine_dispatch.py::test_run_child_spawn_gate_refuses_off_allowlist_snapshot -q
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
___________ test_run_child_spawn_gate_refuses_off_allowlist_snapshot ___________

>       assert ended.get("exit") == 127
E       AssertionError: assert 0 == 127

plugins/superheroes/lib/tests/test_engine_dispatch.py:8574: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_run_child_spawn_gate_refuses_off_allowlist_snapshot
1 failed in 22.13s
```

**restore:** removed the bypass; `_spawn_allowlist_verdict` calls `seat_bundle.resolve_entry` on the reconstructed four-key seat again.

**restore receipt:**
```python
    resolved = seat_bundle.resolve_entry(seat_raw, verb=verb, mode=mode)
```

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.43s
```
