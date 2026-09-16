# WO-2 (#1269) bite-proof — seat_canary seat-identity refusal

**Provenance:** cursor-agent / composer-2.5

## Guarded elements

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| BP-W2-1 | `_resolve_canary_identity` empty `seat_key` refusal | probe without seat identity refuses before dispatch | `test_probe_without_seat_identity_refuses` |

---

## BP-W2-1 — seat identity absent refuses

- **axis:** probe without seat identity refuses before dispatch

**prerequisite (red arm only):** create a git repository at `/r` so `repo-root-missing` does not mask the guarded refusal when the identity check is neutralized. **Unrunnable here** on the WO-4 dispatch host: `/` is read-only (`mkdir /r` → `Read-only file system`). Red arm recorded below without that prerequisite; failure is still via `repo-root-missing`, not the guarded `seat-identity-absent` path.

**neutralization** (`plugins/superheroes/lib/seat_canary.py`, `_resolve_canary_identity`):
```python
    if False and (not isinstance(seat_key, str) or not seat_key.strip()):  # bite-proof neutralization
```
(replaces `if not isinstance(seat_key, str) or not seat_key.strip():`)

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_seat_canary.py::test_probe_without_seat_identity_refuses -q
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
___________________ test_probe_without_seat_identity_refuses ___________________

    def test_probe_without_seat_identity_refuses():
        out = SC.run_canary(
            "",
            {"vendor": "codex", "model": "gpt-5.6-terra", "effort": "high", "tier": "reviewer"},
            repo_root="/r",
        )
        assert out["outcome"] == "unrunnable"
>       assert "seat-identity-absent" in out["detail"] or "seat-key" in out["detail"]
E       AssertionError: assert ('seat-identity-absent' in 'not-dispatched: repo-root-missing' or 'seat-key' in 'not-dispatched: repo-root-missing')

plugins/superheroes/lib/tests/test_seat_canary.py:1020: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seat_canary.py::test_probe_without_seat_identity_refuses
1 failed in 0.16s
```

**restore:**
```python
    if not isinstance(seat_key, str) or not seat_key.strip():
```

**raw green:**
```
.                                                                        [100%]
1 passed in 0.27s
```
