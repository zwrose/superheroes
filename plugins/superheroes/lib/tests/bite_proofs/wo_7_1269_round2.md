# WO-7 (#1269 round-2) bite-proofs — defaultable seats and envelope stamping

**Provenance:** cursor / composer-2.5

## Guarded elements

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| BP-7-1 | `_resolve_entry_model_effort` ambiguous null-model refusal | null model with effort matching multiple allowlist models refuses naming candidates | `test_edge3_null_model_ambiguous_effort_refuses_naming_models` |
| BP-7-2 | `resolve_entry` mode/role coherence leg | `--mode brief-check` with a `reviewer` seat refuses before allowlist | `test_edge6_brief_check_mode_reviewer_refused_before_allowlist` |

---

## BP-7-1 — ambiguous null-model refusal

- **axis:** null model with effort matching multiple allowlist models refuses naming candidates

**neutralization** (`plugins/superheroes/lib/seat_bundle.py`, `_resolve_entry_model_effort`):
```python
        if len(distinct) > 1:
            model = distinct[0]  # bite-proof BP-7-1 neutralization
```

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_seat_bundle.py::test_edge3_null_model_ambiguous_effort_refuses_naming_models -q
```

**raw red** (exit 1):
```
FF                                                                       [100%]
=================================== FAILURES ===================================
__ test_edge3_null_model_ambiguous_effort_refuses_naming_models[guard-check] ___

    @pytest.mark.parametrize("verb", ["guard-check", "dispatch-review"])
    def test_edge3_null_model_ambiguous_effort_refuses_naming_models(verb):
        resolved = SB.resolve_entry(
            _seat_json("codex", None, "high", _REVIEW_ROLE),
            verb=verb,
        )
>       assert resolved["ok"] is False
E       assert True is False

plugins/superheroes/lib/tests/test_seat_bundle.py:508: AssertionError
_ test_edge3_null_model_ambiguous_effort_refuses_naming_models[dispatch-review] _

    @pytest.mark.parametrize("verb", ["guard-check", "dispatch-review"])
    def test_edge3_null_model_ambiguous_effort_refuses_naming_models(verb):
        resolved = SB.resolve_entry(
            _seat_json("codex", None, "high", _REVIEW_ROLE),
            verb=verb,
        )
>       assert resolved["ok"] is False
E       assert True is False

plugins/superheroes/lib/tests/test_seat_bundle.py:508: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seat_bundle.py::test_edge3_null_model_ambiguous_effort_refuses_naming_models[guard-check]
FAILED plugins/superheroes/lib/tests/test_seat_bundle.py::test_edge3_null_model_ambiguous_effort_refuses_naming_models[dispatch-review]
2 failed in 0.36s
```

**restore:** reinstated ambiguous refusal:
```python
        if len(distinct) > 1:
            return _ambiguous_null_model_refusal(role, vendor, effort, tuple(distinct))
```

**raw green** (exit 0):
```
..                                                                       [100%]
2 passed in 0.26s
```

---

## BP-7-2 — leg order (mode/role before allowlist)

- **axis:** `--mode brief-check` with a `reviewer` seat refuses before allowlist

**neutralization** (moved mode/role coherence leg after allowlist consult in `resolve_entry`):
```python
    if not normalized.get("ok"):
        return normalized
    if mode == _MODE_BRIEF_CHECK and role != "brief-check":
        return _mode_role_coherence_refusal(role)
    return {
```

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_seat_bundle.py::test_edge6_brief_check_mode_reviewer_refused_before_allowlist -q
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
________ test_edge6_brief_check_mode_reviewer_refused_before_allowlist _________

    def test_edge6_brief_check_mode_reviewer_refused_before_allowlist(monkeypatch):
        def _boom(*_a, **_k):
            raise RuntimeError("allowlist reached")

        monkeypatch.setattr(DG, "validate", _boom)
        resolved = SB.resolve_entry(
            _seat_json("codex", "gpt-5.6-sol", "high", _REVIEW_ROLE),
            verb="dispatch-review",
            mode="brief-check",
        )
        assert resolved["ok"] is False
>       assert resolved["reason"] == "mode-role-mismatch"
E       AssertionError: assert 'allowlist-raised' == 'mode-role-mismatch'

plugins/superheroes/lib/tests/test_seat_bundle.py:536: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seat_bundle.py::test_edge6_brief_check_mode_reviewer_refused_before_allowlist
1 failed in 0.45s
```

**restore:** reinstated mode/role coherence before model/effort and allowlist legs:
```python
    if mode == _MODE_BRIEF_CHECK and role != "brief-check":
        return _mode_role_coherence_refusal(role)
```

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.30s
```
