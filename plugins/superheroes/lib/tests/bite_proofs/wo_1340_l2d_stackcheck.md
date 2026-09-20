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
| E4 | stack_check.py:553 | `_REPO_RE` validation of returned slug | `test_l2d_resolve_repo_slug_name_with_owner_bad_pattern` | proven |
| E5 | stack_check.py:578 | exhausted deadline refuses without calling gh | `test_l2d_resolve_repo_slug_deadline_exhausted` | proven |

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
1 failed in 0.24s
```

**raw green** after restore:
```
1 passed in 0.22s
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
1 failed in 0.34s
```

**raw green** after restore:
```
1 passed in 0.15s
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

Both proofs above were re-run by the orchestrator against the guarded source as it stands at
`87182e6bfe062b10db6501891a1d480979e0b1aa`, in a dedicated detached worktree, after layer 2d's
vet-verdict read was removed. That commit is the last one to touch `lib/stack_check.py` on this
branch: every later commit leaves the guarded file byte-identical, so these runs are the proofs at
the branch's final head as well. Each neutralization was applied as a targeted edit and reverted by
its inverse edit; the line numbers in the summary table are re-pinned to that head.

**`git status --porcelain` in the probe worktree after both restores — empty:**
```
```

**`git rev-parse HEAD` in the probe worktree:**
```
87182e6bfe062b10db6501891a1d480979e0b1aa
```
