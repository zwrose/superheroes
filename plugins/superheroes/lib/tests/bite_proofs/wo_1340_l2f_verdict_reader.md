# WO-A (#1340 layer 2f) bite-proof — read_vet_verdict in stack_check.py

Per-guard bite proof for `read_vet_verdict` allowlist guards added in layer 2f.

**Register:** 5 guards — start anchor, single-token, sha-equality, 40-hex shape, duplicated-marker mapping.

**Provenance:** cursor / composer-2.5.

**Head:** `a394fc2ba355933e27ddde9ae0baabb7115c5ebc`

**Method:** the mutation is the smallest possible edit to the **guarded code** (never to the test),
applied through the host's edit action and reverted by the inverse edit. Each proving test is selected
by its **exact node id**, never `-k`.

**Command** (referred to as *the command* below, with `<node-id>` replaced per guard):

```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest "<node-id>" -q
```

## Summary table

| ID | Guarded element (file:line) | Axis | Proving test | Verdict |
|---|---|---|---|---|
| G1 | stack_check.py:846 | start anchor on token match | `test_l2f_v17_token_not_at_line_start` | proven |
| G2 | stack_check.py:854-856 | single-token rule | `test_l2f_v6_two_tokens_on_line` | proven |
| G3 | stack_check.py:873-874 | sha-equality rule | `test_l2f_v11_sha_differs_from_head` | proven |
| G4 | stack_check.py:862-871 | 40-hex shape rule | `test_l2f_v9_sha_41_hex_chars` | proven |
| G5 | stack_check.py:900-906 | duplicated-marker → VET_NOT_READY | `test_l2f_v12_duplicated_marker` | proven |

---

## G1 — start anchor on token match

**neutralization** (`plugins/superheroes/lib/stack_check.py` `_parse_vet_verdict_line`):
```python
    for token, verdict in tokens:
        if line.startswith(token):
            matched_verdict = verdict
            matched_token = token
            break
...
    rest = line[len(matched_token):]
```
→
```python
    for token, verdict in tokens:
        pos = line.find(token)
        if pos >= 0:
            matched_verdict = verdict
            matched_token = token
            token_pos = pos
            break
...
    rest = line[token_pos + len(matched_token):]
```

**node id:** `plugins/superheroes/lib/tests/test_stack_check.py::test_l2f_v17_token_not_at_line_start`

**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_____________________ test_l2f_v17_token_not_at_line_start _____________________

    def test_l2f_v17_token_not_at_line_start():
        # axis: token preceded by other text on the same line
>       _assert_vet_not_ready(_vet_body("Vetted: **Verdict: READY** · %s" % HEAD_SHA))

plugins/superheroes/lib/tests/test_stack_check.py:1489: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

body = '<!-- superheroes:advisor-vet -->\nVetted: **Verdict: READY** · abcdef0123456789abcdef0123456789abcdef01'
head_sha = 'abcdef0123456789abcdef0123456789abcdef01'

    def _assert_vet_not_ready(body, head_sha=HEAD_SHA):
        verdict, refusal = sc.read_vet_verdict(body, head_sha)
>       assert verdict == sc.VET_NOT_READY
E       AssertionError: assert 'READY' == 'vet-not-ready'
E         
E         - vet-not-ready
E         + READY

plugins/superheroes/lib/tests/test_stack_check.py:1361: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stack_check.py::test_l2f_v17_token_not_at_line_start
1 failed in 0.12s
```

**raw green** after restore:
```
.                                                                        [100%]
1 passed in 0.10s
```

**restored lines:**
```python
    for token, verdict in tokens:
        if line.startswith(token):
            matched_verdict = verdict
            matched_token = token
            break
...
    rest = line[len(matched_token):]
```

---

## G2 — single-token rule

**neutralization** (`plugins/superheroes/lib/stack_check.py` `_parse_vet_verdict_line`):
```python
    for token, _verdict in tokens:
        if token in rest:
            return VET_NOT_READY
```
→
```python
    # single-token rule removed
```

**node id:** `plugins/superheroes/lib/tests/test_stack_check.py::test_l2f_v6_two_tokens_on_line`

**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
________________________ test_l2f_v6_two_tokens_on_line ________________________

    def test_l2f_v6_two_tokens_on_line():
        # axis: more than one token on the line
>       _assert_vet_not_ready(
            _vet_body("**Verdict: READY** · %s **Verdict: PARKED**" % HEAD_SHA)
        )

plugins/superheroes/lib/tests/test_stack_check.py:1404: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

body = '<!-- superheroes:advisor-vet -->\n**Verdict: READY** · abcdef0123456789abcdef0123456789abcdef01 **Verdict: PARKED**'
head_sha = 'abcdef0123456789abcdef0123456789abcdef01'

    def _assert_vet_not_ready(body, head_sha=HEAD_SHA):
        verdict, refusal = sc.read_vet_verdict(body, head_sha)
>       assert verdict == sc.VET_NOT_READY
E       AssertionError: assert 'READY' == 'vet-not-ready'
E         
E         - vet-not-ready
E         + READY

plugins/superheroes/lib/tests/test_stack_check.py:1361: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stack_check.py::test_l2f_v6_two_tokens_on_line
1 failed in 0.13s
```

**raw green** after restore:
```
.                                                                        [100%]
1 passed in 0.10s
```

**restored lines:**
```python
    for token, _verdict in tokens:
        if token in rest:
            return VET_NOT_READY
```

---

## G3 — sha-equality rule

**neutralization** (`plugins/superheroes/lib/stack_check.py` `_parse_vet_verdict_line`):
```python
    if sha_part.lower() != head_sha.lower():
        return VET_NOT_READY
```
→
```python
    # sha-equality rule removed
```

**node id:** `plugins/superheroes/lib/tests/test_stack_check.py::test_l2f_v11_sha_differs_from_head`

**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
______________________ test_l2f_v11_sha_differs_from_head ______________________

    def test_l2f_v11_sha_differs_from_head():
        # axis: well-formed line whose sha differs from head_sha
>       _assert_vet_not_ready(_vet_body("**Verdict: READY** · %s" % OTHER_SHA))

plugins/superheroes/lib/tests/test_stack_check.py:1432: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

body = '<!-- superheroes:advisor-vet -->\n**Verdict: READY** · 1234567890abcdef1234567890abcdef12345678'
head_sha = 'abcdef0123456789abcdef0123456789abcdef01'

    def _assert_vet_not_ready(body, head_sha=HEAD_SHA):
        verdict, refusal = sc.read_vet_verdict(body, head_sha)
>       assert verdict == sc.VET_NOT_READY
E       AssertionError: assert 'READY' == 'vet-not-ready'
E         
E         - vet-not-ready
E         + READY

plugins/superheroes/lib/tests/test_stack_check.py:1361: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stack_check.py::test_l2f_v11_sha_differs_from_head
1 failed in 0.13s
```

**raw green** after restore:
```
.                                                                        [100%]
1 passed in 0.10s
```

**restored lines:**
```python
    if sha_part.lower() != head_sha.lower():
        return VET_NOT_READY
```

---

## G4 — 40-hex shape rule

**neutralization** (`plugins/superheroes/lib/stack_check.py` `_parse_vet_verdict_line`):
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

**node id:** `plugins/superheroes/lib/tests/test_stack_check.py::test_l2f_v9_sha_41_hex_chars`

**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_________________________ test_l2f_v9_sha_41_hex_chars _________________________

    def test_l2f_v9_sha_41_hex_chars():
        # axis: sha of 41 hex characters
>       _assert_vet_not_ready(_vet_body("**Verdict: READY** · %s0" % HEAD_SHA))

plugins/superheroes/lib/tests/test_stack_check.py:1421: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

body = '<!-- superheroes:advisor-vet -->\n**Verdict: READY** · abcdef0123456789abcdef0123456789abcdef010'
head_sha = 'abcdef0123456789abcdef0123456789abcdef01'

    def _assert_vet_not_ready(body, head_sha=HEAD_SHA):
        verdict, refusal = sc.read_vet_verdict(body, head_sha)
>       assert verdict == sc.VET_NOT_READY
E       AssertionError: assert 'READY' == 'vet-not-ready'
E         
E         - vet-not-ready
E         + READY

plugins/superheroes/lib/tests/test_stack_check.py:1361: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stack_check.py::test_l2f_v9_sha_41_hex_chars
1 failed in 0.12s
```

**raw green** after restore:
```
.                                                                        [100%]
1 passed in 0.11s
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

**neutralization** (`plugins/superheroes/lib/stack_check.py` `read_vet_verdict`):
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

**node id:** `plugins/superheroes/lib/tests/test_stack_check.py::test_l2f_v12_duplicated_marker`

**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
________________________ test_l2f_v12_duplicated_marker ________________________

    def test_l2f_v12_duplicated_marker():
        # axis: two live advisor-vet markers in one body
        body = (
            _vet_body("**Verdict: READY** · %s" % HEAD_SHA)
            + "\n\n"
            + _vet_body("**Verdict: READY** · %s" % HEAD_SHA)
        )
>       _assert_vet_not_ready(body)

plugins/superheroes/lib/tests/test_stack_check.py:1442: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
plugins/superheroes/lib/tests/test_stack_check.py:1360: in _assert_vet_not_ready
    verdict, refusal = sc.read_vet_verdict(body, head_sha)
plugins/superheroes/lib/stack_check.py:900: in read_vet_verdict
    region_text, _line_count, _region_start_line = grounding_stage._extract_region(
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

body = '<!-- superheroes:advisor-vet -->\n**Verdict: READY** · abcdef0123456789abcdef0123456789abcdef01\n\n<!-- superheroes:advisor-vet -->\n**Verdict: READY** · abcdef0123456789abcdef0123456789abcdef01'
marker = '<!-- superheroes:advisor-vet -->'
scan = ContextScan(kinds=('TEXT', 'TEXT', 'TEXT', 'TEXT', 'TEXT'), inert=(False, False, False, False, False), unterminated_opener_line=None, unterminated_html_line=None)
marker_name = 'advisor-vet'

    def _extract_region(body, marker, scan, marker_name):
        # bite-axis: region markers must be standalone comment lines outside code fences.
        offsets = _find_all_standalone_markers(body, marker, scan)
        if len(offsets) >= 2:
>           raise _BodyRefusal(
                "region-marker-duplicated",
                "%s: %d live occurrences" % (marker_name, len(offsets)),
            )
E           grounding_stage._BodyRefusal: region-marker-duplicated

plugins/superheroes/lib/grounding_stage.py:414: _BodyRefusal
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stack_check.py::test_l2f_v12_duplicated_marker
1 failed in 0.15s
```

**raw green** after restore:
```
.                                                                        [100%]
1 passed in 0.10s
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

All five proofs were run at head `a394fc2ba355933e27ddde9ae0baabb7115c5ebc` with targeted
neutralizations applied and reverted by inverse edit. Confirmation run:
128 passed (`test_stack_check.py -q -n auto`).

**`git status --porcelain` after all restores:**
```
 M plugins/superheroes/lib/tests/bite_proofs/wo_1340_l2f_dependency_gate.md
 M plugins/superheroes/lib/tests/bite_proofs/wo_1340_l2f_verdict_reader.md
```
