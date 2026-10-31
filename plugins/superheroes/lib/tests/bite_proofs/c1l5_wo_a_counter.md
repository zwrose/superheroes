# C1-L5 (#2209 WO-A) bite-proof — the countable-lines counter

**Provenance:** implementer WO-A / `lib/countable_lines.py`, `lib/tests/test_countable_lines_c1l5.py`

Declared guarded elements (from the order): E1 the sha256 comparison, E2 the not-in-change check, both in `proven_copies` (`_reject_reason`). Each was neutralized with one targeted edit and restored with the inverse edit; no `git checkout`, `restore`, `reset` or `stash` was used. Run from `/home/user/wt-2209-a`. The captures below are the runner's whole output for each run apart from the `UV_NATIVE_TLS` deprecation warning line, which is left out; nothing is redacted (no secrets, tokens or URLs appear).

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| E1 | `countable_lines.py:300` `digest != copy["sha256"]` | a proof copy counts only when the working-tree bytes hash to the proof's checksum | `test_covered_file_with_other_bytes_is_rejected_and_counts` |
| E2 | `countable_lines.py:288` `if not sections:` | a proof copy counts only when its file is a section of the change | `test_proof_naming_a_file_outside_the_change_is_rejected` |

---

## E1 — the sha256 comparison

- **axis:** `proven_copies` rejects a covered file whose bytes differ from the proof (`checksum-mismatch`); the file then counts.

**neutralization** (`countable_lines.py`, `_reject_reason`):
```python
-    if digest != copy["sha256"]:
+    if False:
         return "checksum-mismatch"
```

**raw red:** `scripts/pinned-python -B -m pytest plugins/superheroes/lib/tests/test_countable_lines_c1l5.py -q -k test_covered_file_with_other_bytes_is_rejected_and_counts`
```
F                                                                        [100%]
=================================== FAILURES ===================================
__________ test_covered_file_with_other_bytes_is_rejected_and_counts ___________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-1/test_covered_file_with_other_b0')

    def test_covered_file_with_other_bytes_is_rejected_and_counts(tmp_path):
        root, diff = _copy_fixture(tmp_path)
        proof = _proof(_copy("copies/a.txt", b"not the bytes\n"))
        proven, rejected = cl.proven_copies(diff, root, proof)
>       assert proven == []
E       AssertionError: assert [{'file': 'co...1f449502934'}] == []
E         
E         Left contains one more item: {'file': 'copies/a.txt', 'source': 'src/orig.txt', 'sha256': 'e44646bfb63e92c6cbcffd510c1f5477086dec2a1c69d21c49f951f449502934'}
E         Use -v to get more diff

/home/user/wt-2209-a/plugins/superheroes/lib/tests/test_countable_lines_c1l5.py:327: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_countable_lines_c1l5.py::test_covered_file_with_other_bytes_is_rejected_and_counts
1 failed, 64 deselected in 0.29s
```

**restore:** the inverse edit, `if False:` back to `if digest != copy["sha256"]:`.

**restore receipt:** the restored lines quoted back from the file after the edit (`grep -n -B2 -A2 'digest != copy'`):
```
298-        return "unreadable"
299-    # Axis: a proof copy counts only when the working-tree bytes hash to the proof's checksum.
300:    if digest != copy["sha256"]:
301-        return "checksum-mismatch"
302-    return None
```

**raw green:** same command after the restore
```
.                                                                        [100%]
1 passed, 64 deselected in 0.27s
```

---

## E2 — the not-in-change check

- **axis:** `proven_copies` rejects a proof copy whose file is not a section of the diff (`not-in-change`), however well its bytes hash.

**neutralization** (`countable_lines.py`, `_reject_reason`):
```python
-    if not sections:
+    if False:
         return "not-in-change"
```

**raw red:** `scripts/pinned-python -B -m pytest plugins/superheroes/lib/tests/test_countable_lines_c1l5.py -q -k test_proof_naming_a_file_outside_the_change_is_rejected`
```
F                                                                        [100%]
=================================== FAILURES ===================================
___________ test_proof_naming_a_file_outside_the_change_is_rejected ____________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-3/test_proof_naming_a_file_outsi0')

    def test_proof_naming_a_file_outside_the_change_is_rejected(tmp_path):
        root, diff = _copy_fixture(tmp_path)
        (root / "outside.txt").write_bytes(b"outside\n")
        proof = _proof(_copy("outside.txt", b"outside\n"))
        proven, rejected = cl.proven_copies(diff, root, proof)
>       assert proven == []
E       AssertionError: assert [{'file': 'ou...31b6dc5be43'}] == []
E         
E         Left contains one more item: {'file': 'outside.txt', 'source': 'src/orig.txt', 'sha256': '92a214fa61579091222f97eaf8e9bf11c1a728af5a077a3b5568231b6dc5be43'}
E         Use -v to get more diff

/home/user/wt-2209-a/plugins/superheroes/lib/tests/test_countable_lines_c1l5.py:339: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_countable_lines_c1l5.py::test_proof_naming_a_file_outside_the_change_is_rejected
1 failed, 64 deselected in 0.54s
```

**restore:** the inverse edit, `if False:` back to `if not sections:`.

**restore receipt:** the restored lines quoted back from the file after the edit (`grep -n -B2 -A1 'return "not-in-change"'`); `git status --porcelain -- plugins/superheroes/lib` after the restore lists only the two new untracked files (`countable_lines.py`, `tests/test_countable_lines_c1l5.py`; the record is added after this run):
```
287-    # Axis: a proof copy counts only when its file is a section of the change.
288-    if not sections:
289-        return "not-in-change"
```

**raw green:** same command after the restore
```
.                                                                        [100%]
1 passed, 64 deselected in 0.25s
```
