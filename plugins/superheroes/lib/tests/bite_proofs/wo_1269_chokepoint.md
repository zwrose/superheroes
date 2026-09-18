# WO-1 (#1269) bite-proofs — dispatch entry chokepoint

**Provenance:** cursor-agent / composer-2.5

## Guarded elements

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| BP-1 | `resolve_entry` mode/role coherence leg | `--mode brief-check` with a `reviewer` seat refuses before allowlist | `test_brief_check_mode_reviewer_seat_refused` |
| BP-2 | `_normalize_allowlist_verdict` semantic success gate | empty `allowlist_pairs` on `ok: True` refuses | `test_semantic_allowlist_verdict_empty_pairs_refused` |
| BP-3 | `_parse_entry_dict` required `role` key | missing `role` key refuses | `test_role_key_absent_refused` |
| BP-4 | `_spawn_allowlist_verdict` resolver call | off-allowlist journal seat refuses at spawn | `test_run_child_spawn_gate_refuses_off_allowlist_snapshot` |
| BP-5 | `_dispatch_review_mode_role_refusal` inverse leg | `brief-check` role with normal/omitted mode refused after allowlist | `test_brief_check_role_normal_review_mode_refused` |
| BP-6 | `_verb_role_coherence_refusal` unclassified-role leg | unclassified write roles refused for dispatch verbs | `test_unclassified_role_refused_for_dispatch_verbs` |

---

## BP-1 — mode/role coherence

- **axis:** `--mode brief-check` with a `reviewer` seat refuses before allowlist

**neutralization** (removed early `--mode brief-check` leg in `resolve_entry`):
```python
    if verb == "dispatch-review" and mode == _MODE_BRIEF_CHECK and role != "brief-check":
        return _mode_role_coherence_refusal(role)
    elif mode == _MODE_BRIEF_CHECK and role != "brief-check":
        return _mode_role_coherence_refusal(role)
```
(delete the `if verb == "dispatch-review" and mode == _MODE_BRIEF_CHECK ...` block only)

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

plugins/superheroes/lib/tests/test_seat_bundle.py:361: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seat_bundle.py::test_brief_check_mode_reviewer_seat_refused
1 failed in 1.19s
```

**restore:** reinstated the early `--mode brief-check` / role coherence block in `resolve_entry`.

**restore receipt:**
```python
    if verb == "dispatch-review" and mode == _MODE_BRIEF_CHECK and role != "brief-check":
        return _mode_role_coherence_refusal(role)
    elif mode == _MODE_BRIEF_CHECK and role != "brief-check":
        return _mode_role_coherence_refusal(role)
```

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.99s
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

        monkeypatch.setattr(SB.dispatch_allowlist, "validate", _fake_validate)
        resolved = SB.resolve_entry(
            _seat_json("codex", "gpt-5.6-sol", "high"),
            verb="guard-check",
        )
>       assert resolved["ok"] is False
E       assert True is False

plugins/superheroes/lib/tests/test_seat_bundle.py:463: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seat_bundle.py::test_semantic_allowlist_verdict_empty_pairs_refused
1 failed in 0.73s
```

**restore:** removed the early `ok: True` accept; semantic field checks restored.

**restore receipt:** `_normalize_allowlist_verdict` again requires echoed role/vendor, model_id/resolved_model, effort, non-empty `allowlist_pairs`, and membership of the resolved pair.

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.91s
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

plugins/superheroes/lib/tests/test_seat_bundle.py:325: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seat_bundle.py::test_role_key_absent_refused
1 failed in 0.64s
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
1 passed in 1.03s
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
1 passed in 2.27s
```

---

## BP-5 — brief-check role requires brief-check mode (inverse leg)

- **axis:** `brief-check` role with `--mode review` refused after allowlist on `dispatch-review`

**neutralization** (removed inverse branch in `_dispatch_review_mode_role_refusal`):
```python
    if role == "brief-check" and effective != _MODE_BRIEF_CHECK:
        return _brief_check_role_mode_refusal(effective)
```

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_seat_bundle.py::test_brief_check_role_normal_review_mode_refused plugins/superheroes/lib/tests/test_seat_bundle.py::test_brief_check_role_omitted_mode_refused_on_dispatch_review -q
```

**raw red** (exit 1):
```
FF                                                                       [100%]
=================================== FAILURES ===================================
_______________ test_brief_check_role_normal_review_mode_refused _______________

    def test_brief_check_role_normal_review_mode_refused():
        resolved = SB.resolve_entry(
            _seat_json("codex", "gpt-5.6-sol", "xhigh", _BRIEF_ROLE),
            verb="dispatch-review",
            mode="review",
        )
>       assert resolved["ok"] is False
E       assert True is False

plugins/superheroes/lib/tests/test_seat_bundle.py:372: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seat_bundle.py::test_brief_check_role_normal_review_mode_refused
FAILED plugins/superheroes/lib/tests/test_seat_bundle.py::test_brief_check_role_omitted_mode_refused_on_dispatch_review
2 failed in 0.64s
```

**restore:** reinstated the inverse branch in `_dispatch_review_mode_role_refusal`.

**raw green** (exit 0):
```
..                                                                       [100%]
2 passed in 0.58s
```

---

## BP-6 — unclassified roles refused for dispatch verbs

- **axis:** mechanical/synthesis/pilot seats refused for `dispatch-review` / `dispatch-write`

**neutralization** (removed unclassified-role branch in `_verb_role_coherence_refusal`):
```python
    if verb in ("dispatch-review", "dispatch-write") and rw is None:
        return _entry_refusal(
            "verb-role-mismatch",
            (
                f"role {role!r} has no read_write classification; "
                f"{verb} requires a classified read or write role; "
                f"accepted: {_ACCEPTED_SEAT}; {accepted_role_detail()}"
            ),
        )
```

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_seat_bundle.py::test_unclassified_role_refused_for_dispatch_verbs -q
```

**raw red** (exit 1):
```
FFFFFF                                                                   [100%]
=================================== FAILURES ===================================
_ test_unclassified_role_refused_for_dispatch_verbs[mechanical-dispatch-review] _

    def test_unclassified_role_refused_for_dispatch_verbs(role, verb):
        resolved = SB.resolve_entry(
            _seat_json("claude", "haiku-4.5", "medium", role),
            verb=verb,
        )
>       assert resolved["ok"] is False
E       assert True is False

plugins/superheroes/lib/tests/test_seat_bundle.py:402: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seat_bundle.py::test_unclassified_role_refused_for_dispatch_verbs[mechanical-dispatch-review]
FAILED plugins/superheroes/lib/tests/test_seat_bundle.py::test_unclassified_role_refused_for_dispatch_verbs[mechanical-dispatch-write]
FAILED plugins/superheroes/lib/tests/test_seat_bundle.py::test_unclassified_role_refused_for_dispatch_verbs[synthesis-dispatch-review]
FAILED plugins/superheroes/lib/tests/test_seat_bundle.py::test_unclassified_role_refused_for_dispatch_verbs[synthesis-dispatch-write]
FAILED plugins/superheroes/lib/tests/test_seat_bundle.py::test_unclassified_role_refused_for_dispatch_verbs[pilot-dispatch-review]
FAILED plugins/superheroes/lib/tests/test_seat_bundle.py::test_unclassified_role_refused_for_dispatch_verbs[pilot-dispatch-write]
6 failed in 0.71s
```

**restore:** reinstated the unclassified-role refusal branch in `_verb_role_coherence_refusal`.

**raw green** (exit 0):
```
......                                                                   [100%]
6 passed in 0.62s
```
