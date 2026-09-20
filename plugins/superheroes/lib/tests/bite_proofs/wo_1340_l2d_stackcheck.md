# WO-A (#1340 layer 2d) bite-proof — shared read seam in stack_check.py

Per-guard bite proof for `resolve_repo_slug` and `read_vet_verdict` classification guards added in layer 2d.

**Register:** 9 guards — reminder-present check, negated-READY refusal, whole-word READY, slot-boundary extraction, verdict-region mechanism exclusion, repo-slug `_REPO_RE` validation, exhausted-deadline refusal-without-calling, head-pinning on READY, and refusal/not-ready separation.

**Provenance:** cursor / composer-2.5.

**Command** (referred to as *the command* below):

```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_stack_check.py -q
```

## Summary table

| ID | Guarded element (file:line) | Axis | Proving test | Verdict |
|---|---|---|---|---|
| E1 | stack_check.py:671 | reminder prefix present → not-ready | `test_l2d_read_vet_verdict_reminder_present_is_not_ready` | proven |
| E2 | stack_check.py:678 | negated READY phrasing → not-ready | `test_l2d_read_vet_verdict_not_ready_is_not_ready` | proven |
| E2b | stack_check.py:696 | whole-word READY requirement | `test_l2d_read_vet_verdict_already_word_is_not_ready` | proven |
| E3 | stack_check.py:688 | slot-boundary extraction | `test_l2d_read_vet_verdict_later_ready_section_is_not_ready` | proven |
| E3b | stack_check.py:660 | verdict-region mechanism exclusion | `test_l2d_read_vet_verdict_fenced_ready_is_not_ready`, `test_l2d_read_vet_verdict_details_ready_is_not_ready`, `test_l2d_read_vet_verdict_parked_with_quoted_ready_for_pr_is_not_ready` | proven |
| E4 | stack_check.py:586 | `_REPO_RE` validation of returned slug | `test_l2d_resolve_repo_slug_name_with_owner_bad_pattern` | proven |
| E5 | stack_check.py:611 | exhausted deadline refuses without calling gh | `test_l2d_resolve_repo_slug_deadline_exhausted` | proven |
| E6 | stack_check.py:697 | head-pinning on READY verdict | `test_l2d_read_vet_verdict_stale_head_is_not_ready` | proven |
| E7 | stack_check.py:760 | unreadable read returns refusal, not not-ready | `test_l2d_read_vet_verdict_unreadable_returns_refusal` | proven |

---

## E1 — reminder prefix present → not-ready

**neutralization** (`plugins/superheroes/lib/stack_check.py`):
```python
    if ADVISOR_VET_REMINDER_PREFIX in body:
        return VET_NOT_READY
```
→
```python
    # reminder check removed
```

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_stack_check.py::test_l2d_read_vet_verdict_reminder_present_is_not_ready -q
```

**raw red** (traceback body elided):
```
FAILED plugins/superheroes/lib/tests/test_stack_check.py::test_l2d_read_vet_verdict_reminder_present_is_not_ready
1 failed in 0.32s
```

**raw green** after restore:
```
1 passed in 0.32s
```

**restored lines:**
```python
    if ADVISOR_VET_REMINDER_PREFIX in body:
        return VET_NOT_READY
```

---

## E2 — negated READY phrasing → not-ready

Proving tests (all four go red under neutralization): `test_l2d_read_vet_verdict_not_ready_is_not_ready`, `test_l2d_read_vet_verdict_not_yet_ready_is_not_ready`, `test_l2d_read_vet_verdict_no_ready_is_not_ready`, `test_l2d_read_vet_verdict_never_ready_is_not_ready`.

**neutralization** (`plugins/superheroes/lib/stack_check.py`):
```python
    if _slot_has_negated_ready_verdict(slot_text):
        return VET_NOT_READY
```
→
```python
    if False and _slot_has_negated_ready_verdict(slot_text):
        return VET_NOT_READY
```

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_stack_check.py::test_l2d_read_vet_verdict_not_ready_is_not_ready plugins/superheroes/lib/tests/test_stack_check.py::test_l2d_read_vet_verdict_not_yet_ready_is_not_ready plugins/superheroes/lib/tests/test_stack_check.py::test_l2d_read_vet_verdict_no_ready_is_not_ready plugins/superheroes/lib/tests/test_stack_check.py::test_l2d_read_vet_verdict_never_ready_is_not_ready -q
```

**raw red** (traceback body elided):
```
FFFF                                                                     [100%]
FAILED plugins/superheroes/lib/tests/test_stack_check.py::test_l2d_read_vet_verdict_not_ready_is_not_ready
FAILED plugins/superheroes/lib/tests/test_stack_check.py::test_l2d_read_vet_verdict_not_yet_ready_is_not_ready
FAILED plugins/superheroes/lib/tests/test_stack_check.py::test_l2d_read_vet_verdict_no_ready_is_not_ready
FAILED plugins/superheroes/lib/tests/test_stack_check.py::test_l2d_read_vet_verdict_never_ready_is_not_ready
4 failed in 0.50s
```

**raw green** after restore:
```
....                                                                     [100%]
4 passed in 0.22s
```

**restored lines:**
```python
    if _slot_has_negated_ready_verdict(slot_text):
        return VET_NOT_READY
```

---

## E2b — whole-word READY requirement

**neutralization** (`plugins/superheroes/lib/stack_check.py`):
```python
    return _VET_AFFIRMATIVE_READY_RE.search(_vet_verdict_region(slot_text)) is not None
```
→
```python
    return "ready" in _vet_verdict_region(slot_text).lower()
```

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_stack_check.py::test_l2d_read_vet_verdict_already_word_is_not_ready -q
```

**raw red** (traceback body elided):
```
FAILED plugins/superheroes/lib/tests/test_stack_check.py::test_l2d_read_vet_verdict_already_word_is_not_ready
1 failed in 0.34s
```

**raw green** after restore:
```
1 passed in 0.33s
```

**restored lines:**
```python
    return _VET_AFFIRMATIVE_READY_RE.search(_vet_verdict_region(slot_text)) is not None
```

---

## E3 — slot-boundary extraction

**neutralization** (`plugins/superheroes/lib/stack_check.py`):
```python
        _slot_has_affirmative_ready_verdict(slot_text)
        and _slot_names_head(slot_text, head_ref_oid)
```
→
```python
        _slot_has_affirmative_ready_verdict(body)
        and _slot_names_head(body, head_ref_oid)
```

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_stack_check.py::test_l2d_read_vet_verdict_later_ready_section_is_not_ready -q
```

**raw red** (traceback body elided):
```
FAILED plugins/superheroes/lib/tests/test_stack_check.py::test_l2d_read_vet_verdict_later_ready_section_is_not_ready
1 failed in 0.40s
```

**raw green** after restore:
```
1 passed in 0.24s
```

**restored lines:**
```python
        _slot_has_affirmative_ready_verdict(slot_text)
        and _slot_names_head(slot_text, head_ref_oid)
```

---

## E3b — verdict-region mechanism exclusion

Proving tests: `test_l2d_read_vet_verdict_fenced_ready_is_not_ready`, `test_l2d_read_vet_verdict_details_ready_is_not_ready`, `test_l2d_read_vet_verdict_parked_with_quoted_ready_for_pr_is_not_ready`.

**neutralization** (`plugins/superheroes/lib/stack_check.py`):
```python
def _vet_verdict_region(slot_text):
    region = _VET_FENCED_BLOCK_RE.sub("", slot_text)
    return _VET_DETAILS_BLOCK_RE.sub("", region)
```
→
```python
def _vet_verdict_region(slot_text):
    return slot_text
```

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_stack_check.py::test_l2d_read_vet_verdict_fenced_ready_is_not_ready plugins/superheroes/lib/tests/test_stack_check.py::test_l2d_read_vet_verdict_details_ready_is_not_ready plugins/superheroes/lib/tests/test_stack_check.py::test_l2d_read_vet_verdict_parked_with_quoted_ready_for_pr_is_not_ready -q
```

**raw red** (traceback body elided):
```
.FF                                                                      [100%]
FAILED plugins/superheroes/lib/tests/test_stack_check.py::test_l2d_read_vet_verdict_fenced_ready_is_not_ready
FAILED plugins/superheroes/lib/tests/test_stack_check.py::test_l2d_read_vet_verdict_details_ready_is_not_ready
2 failed, 1 passed in 0.15s
```

**raw green** after restore:
```
...                                                                      [100%]
3 passed in 0.11s
```

**restored lines:**
```python
def _vet_verdict_region(slot_text):
    region = _VET_FENCED_BLOCK_RE.sub("", slot_text)
    return _VET_DETAILS_BLOCK_RE.sub("", region)
```

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

## E6 — head-pinning on READY verdict

**neutralization** (`plugins/superheroes/lib/stack_check.py`):
```python
        _slot_has_affirmative_ready_verdict(slot_text)
        and _slot_names_head(slot_text, head_ref_oid)
```
→
```python
        _slot_has_affirmative_ready_verdict(slot_text)
```

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_stack_check.py::test_l2d_read_vet_verdict_stale_head_is_not_ready -q
```

**raw red** (traceback body elided):
```
FAILED plugins/superheroes/lib/tests/test_stack_check.py::test_l2d_read_vet_verdict_stale_head_is_not_ready
1 failed in 0.36s
```

**raw green** after restore:
```
1 passed in 0.24s
```

**restored lines:**
```python
        _slot_has_affirmative_ready_verdict(slot_text)
        and _slot_names_head(slot_text, head_ref_oid)
```

---

## E7 — unreadable read returns refusal, not not-ready

**neutralization** (`plugins/superheroes/lib/stack_check.py`):
```python
    if proc.returncode != 0:
        return None, _read_refusal(
            REASON_STACK_UNREADABLE, _proc_output(proc) or "gh pr view failed")
```
→
```python
    if proc.returncode != 0:
        return VET_NOT_READY, None
```

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_stack_check.py::test_l2d_read_vet_verdict_unreadable_returns_refusal -q
```

**raw red** (traceback body elided):
```
FAILED plugins/superheroes/lib/tests/test_stack_check.py::test_l2d_read_vet_verdict_unreadable_returns_refusal
1 failed in 0.33s
```

**raw green** after restore:
```
1 passed in 0.30s
```

**restored lines:**
```python
    if proc.returncode != 0:
        return None, _read_refusal(
            REASON_STACK_UNREADABLE, _proc_output(proc) or "gh pr view failed")
```

---

## Restore receipt

**`git status --porcelain` (mutated files):**
```
 M plugins/superheroes/lib/stack_check.py
 M plugins/superheroes/lib/tests/test_stack_check.py
?? plugins/superheroes/lib/tests/bite_proofs/wo_1340_l2d_stackcheck.md
```
