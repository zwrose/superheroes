# WO-A (#1340 layer 2f) bite-proof — read_vet_verdict in stack_check.py

Per-guard bite proof for `read_vet_verdict` allowlist guards added in layer 2f.

**Register:** 5 guards — start anchor, single-token, sha-equality, 40-hex shape, duplicated-marker mapping.

**Provenance:** cursor / composer-2.5.

**Command** (referred to as *the command* below):

```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_stack_check.py -q
```

## Summary table

| ID | Guarded element (file:line) | Axis | Proving test | Verdict |
|---|---|---|---|---|
| G1 | stack_check.py:643 | start anchor on token match | `test_l2f_v17_token_not_at_line_start` | proven |
| G2 | stack_check.py:652 | single-token rule | `test_l2f_v6_two_tokens_on_line` | proven |
| G3 | stack_check.py:670 | sha-equality rule | `test_l2f_v11_sha_differs_from_head` | proven |
| G4 | stack_check.py:659-664 | 40-hex shape rule | `test_l2f_v9_sha_41_hex_chars` | proven |
| G5 | stack_check.py:695 | duplicated-marker → VET_NOT_READY | `test_l2f_v12_duplicated_marker` | proven |

---

## G1 — start anchor on token match

**neutralization** (`plugins/superheroes/lib/stack_check.py`):
```python
        if line.startswith(token):
```
→
```python
        pos = line.find(token)
        if pos >= 0:
            matched_verdict = verdict
            matched_token = token
            token_pos = pos
            break
...
    rest = line[token_pos + len(matched_token):]
```

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_stack_check.py::test_l2f_v17_token_not_at_line_start -q
```

**raw red** (traceback body elided):
```
FAILED plugins/superheroes/lib/tests/test_stack_check.py::test_l2f_v17_token_not_at_line_start
1 failed in 0.25s
```

**raw green** after restore:
```
1 passed in 0.21s
```

**restored lines:**
```python
        if line.startswith(token):
...
    rest = line[len(matched_token):]
```

---

## G2 — single-token rule

**neutralization** (`plugins/superheroes/lib/stack_check.py`):
```python
    for token, _verdict in _VET_VERDICT_TOKENS:
        if token in rest:
            return VET_NOT_READY
```
→
```python
    # single-token rule removed
```

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_stack_check.py::test_l2f_v6_two_tokens_on_line -q
```

**raw red** (traceback body elided):
```
FAILED plugins/superheroes/lib/tests/test_stack_check.py::test_l2f_v6_two_tokens_on_line
1 failed in 0.65s
```

**raw green** after restore:
```
1 passed in 0.45s
```

**restored lines:**
```python
    for token, _verdict in _VET_VERDICT_TOKENS:
        if token in rest:
            return VET_NOT_READY
```

---

## G3 — sha-equality rule

**neutralization** (`plugins/superheroes/lib/stack_check.py`):
```python
    if sha_part.lower() != head_sha.lower():
        return VET_NOT_READY
```
→
```python
    # sha-equality rule removed
```

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_stack_check.py::test_l2f_v11_sha_differs_from_head -q
```

**raw red** (traceback body elided):
```
FAILED plugins/superheroes/lib/tests/test_stack_check.py::test_l2f_v11_sha_differs_from_head
1 failed in 0.62s
```

**raw green** after restore:
```
1 passed in 0.32s
```

**restored lines:**
```python
    if sha_part.lower() != head_sha.lower():
        return VET_NOT_READY
```

---

## G4 — 40-hex shape rule

**neutralization** (`plugins/superheroes/lib/stack_check.py`):
```python
    if len(after_sep) < 40:
        return VET_NOT_READY

    sha_part = after_sep[:40]
    after_sha = after_sep[40:]
    if not _SHA40_RE.match(sha_part):
        return VET_NOT_READY

    if after_sha and not after_sha.startswith(" "):
        return VET_NOT_READY
```
→
```python
    sha_part = after_sep[:40]
```

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_stack_check.py::test_l2f_v9_sha_41_hex_chars -q
```

**raw red** (traceback body elided):
```
FAILED plugins/superheroes/lib/tests/test_stack_check.py::test_l2f_v9_sha_41_hex_chars
1 failed in 0.49s
```

**raw green** after restore:
```
1 passed in 0.39s
```

**restored lines:**
```python
    if len(after_sep) < 40:
        return VET_NOT_READY

    sha_part = after_sep[:40]
    after_sha = after_sep[40:]
    if not _SHA40_RE.match(sha_part):
        return VET_NOT_READY

    if after_sha and not after_sha.startswith(" "):
        return VET_NOT_READY
```

---

## G5 — duplicated-marker → VET_NOT_READY

**neutralization** (`plugins/superheroes/lib/stack_check.py`):
```python
    try:
        region_text, _line_count, _region_start_line = grounding_stage._extract_region(
            body, marker, scan, "advisor-vet",
        )
    except grounding_stage._BodyRefusal:
        # axis: more than one live advisor-vet marker
        return VET_NOT_READY, None
```
→
```python
    region_text, _line_count, _region_start_line = grounding_stage._extract_region(
        body, marker, scan, "advisor-vet",
    )
```

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_stack_check.py::test_l2f_v12_duplicated_marker -q
```

**raw red** (traceback body elided):
```
FAILED plugins/superheroes/lib/tests/test_stack_check.py::test_l2f_v12_duplicated_marker
1 failed in 0.53s
```

**raw green** after restore:
```
1 passed in 0.25s
```

**restored lines:**
```python
    try:
        region_text, _line_count, _region_start_line = grounding_stage._extract_region(
            body, marker, scan, "advisor-vet",
        )
    except grounding_stage._BodyRefusal:
        # axis: more than one live advisor-vet marker
        return VET_NOT_READY, None
```

---

## Restore receipt

All five proofs were run in the WO-A worktree with targeted neutralizations applied and reverted
by inverse edit. Final full-suite run: 111 passed.

**`git status --porcelain` after all restores:**
```
 M plugins/superheroes/lib/stack_check.py
 M plugins/superheroes/lib/tests/test_stack_check.py
?? plugins/superheroes/lib/tests/bite_proofs/wo_1340_l2f_verdict_reader.md
```
