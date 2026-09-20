# WO-A (#1340 layer 2d) bite-proof — resolve_repo_slug in stack_check.py

Per-guard bite proof for `resolve_repo_slug` guards added in layer 2d.

**Register:** 2 guards — repo-slug `_REPO_RE` validation and exhausted-deadline refusal-without-calling.

**Provenance:** cursor / composer-2.5.

**Command** (referred to as *the command* below):

```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_stack_check.py -q
```

## Summary table

| ID | Guarded element (file:line) | Axis | Proving test | Verdict |
|---|---|---|---|---|
| E4 | stack_check.py:586 | `_REPO_RE` validation of returned slug | `test_l2d_resolve_repo_slug_name_with_owner_bad_pattern` | proven |
| E5 | stack_check.py:611 | exhausted deadline refuses without calling gh | `test_l2d_resolve_repo_slug_deadline_exhausted` | proven |

---

## E4 — `_REPO_RE` validation of returned slug

**neutralization** (`plugins/superheroes/lib/stack_check.py`):
```python
    if not _REPO_RE.match(name):
        return None, _read_refusal(
            REASON_STACK_UNREADABLE, "nameWithOwner is not a valid owner/name slug")
```
→
```python
    # _REPO_RE validation removed
```

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_stack_check.py::test_l2d_resolve_repo_slug_name_with_owner_bad_pattern -q
```

**raw red** (traceback body elided):
```
FAILED plugins/superheroes/lib/tests/test_stack_check.py::test_l2d_resolve_repo_slug_name_with_owner_bad_pattern
1 failed in 0.35s
```

**raw green** after restore:
```
1 passed in 0.27s
```

**restored lines:**
```python
    if not _REPO_RE.match(name):
        return None, _read_refusal(
            REASON_STACK_UNREADABLE, "nameWithOwner is not a valid owner/name slug")
```

---

## E5 — exhausted deadline refuses without calling gh

**neutralization** (`plugins/superheroes/lib/stack_check.py`):
```python
    if deadline_at is not None and time.monotonic() >= deadline_at:
        return None, _read_refusal(
            REASON_STACK_UNREADABLE,
            "read budget of %g seconds exhausted before gh repo view" % deadline)
```
→
```python
    # exhausted-deadline preflight removed
```

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_stack_check.py::test_l2d_resolve_repo_slug_deadline_exhausted -q
```

**raw red** (traceback body elided):
```
FAILED plugins/superheroes/lib/tests/test_stack_check.py::test_l2d_resolve_repo_slug_deadline_exhausted
1 failed in 0.39s
```

**raw green** after restore:
```
1 passed in 0.27s
```

**restored lines:**
```python
    if deadline_at is not None and time.monotonic() >= deadline_at:
        return None, _read_refusal(
            REASON_STACK_UNREADABLE,
            "read budget of %g seconds exhausted before gh repo view" % deadline)
```

---

## Restore receipt

**`git status --porcelain` (mutated files):**
```
 M plugins/superheroes/lib/stack_check.py
 M plugins/superheroes/lib/tests/test_stack_check.py
?? plugins/superheroes/lib/tests/bite_proofs/wo_1340_l2d_stackcheck.md
```
