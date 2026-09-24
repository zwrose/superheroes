# WO-B (#1340 layer 2c) bite-proof — register-check verification sentence drift pin

Per-guard bite proof for `test_register_check_verification_sentence_pinned_across_copy_holders`:
the load-bearing `registerCopy`/`registerRef` clause is neutralized in one copy-holder, the proving
test goes red alone, then the clause is restored and the test goes green again.

**Provenance:** cursor / composer-2.5.

**Command** (referred to as *the command* below):

```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-woB -m pytest plugins/superheroes/lib/tests/test_ssot_drift.py::test_register_check_verification_sentence_pinned_across_copy_holders -q
```

## Summary table

| ID | Guarded element (file:line) | Axis | Proving test | Verdict |
|---|---|---|---|---|
| E1 | workhorse/SKILL.md:159 | pass evidence must name register copy read | `test_register_check_verification_sentence_pinned_across_copy_holders` | proven |

---

## E1 — pass evidence must name register copy read

**neutralization** (`plugins/superheroes/skills/workhorse/SKILL.md`):
```
with `requiredEntries` and `registerCopy`/`registerRef` — not merely a claim that it ran.
```
→
```
with `requiredEntries` — not merely a claim that it ran.
```

**command:** the command (see top).

**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_____ test_register_check_verification_sentence_pinned_across_copy_holders _____

    def test_register_check_verification_sentence_pinned_across_copy_holders():
        """Register-check pass evidence sentence is identical in every enumerated copy-holder."""
        pinned_norm = _anchor_whitespace_normalize(
            _REGISTER_CHECK_VERIFICATION_SENTENCE_CLAUSE
        )
        for rel, expected_count in _REGISTER_CHECK_VERIFICATION_SENTENCE_COPY_HOLDERS.items():
            path = os.path.normpath(os.path.join(PLUGIN, rel))
            assert os.path.isfile(path), (
                "%s: copy-holder missing or unreadable — expected file at %s"
                % (rel, path)
            )
            text = _read(rel)
            matches = _register_check_verification_sentence_occurrences(text)
            assert len(matches) == expected_count, (
                "%s: expected exactly %d verification-sentence occurrence(s), found %d"
                % (rel, expected_count, len(matches))
            )
            for match in matches:
                clause = match.group(0)
                clause_norm = _anchor_whitespace_normalize(clause)
>               assert clause_norm == pinned_norm, (
                    "%s: verification-sentence clause drift — expected %r, found %r"
                    % (rel, pinned_norm, clause_norm)
                )
E               AssertionError: skills/workhorse/SKILL.md: verification-sentence clause drift — expected 'the `result` line, or `pass` together with `requiredEntries` and `registerCopy`/`registerRef` — not merely a claim that it ran.', found 'the `result` line, or `pass` together with `requiredEntries` — not merely a claim that it ran.'
E               assert 'the `result`... that it ran.' == 'the `result`... that it ran.'
E                 
E                 Skipping 51 identical leading characters in diff, use -v to show
E                 - dEntries` and `registerCopy`/`registerRef` — not merely a claim that it ran.
E                 + dEntries` — not merely a claim that it ran.

plugins/superheroes/lib/tests/test_ssot_drift.py:3576: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_ssot_drift.py::test_register_check_verification_sentence_pinned_across_copy_holders
1 failed in 0.19s
```

**restore:** reverted the neutralization (quoted left-hand side under **neutralization**).

**raw green** after restore:
```
.                                                                        [100%]
1 passed in 0.17s
```
