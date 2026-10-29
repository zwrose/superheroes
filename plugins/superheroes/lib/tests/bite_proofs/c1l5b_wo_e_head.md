# C1-L5b (#2243 WO-E) bite-proof — the counter reads the reviewed head, not the checkout

**Provenance:** implementer WO-E / `lib/countable_lines.py`, `lib/tests/test_countable_lines_c1l5.py`

Declared guarded elements (from the order): E1 the section-binding check (`indexNew` prefix of the head oid), E2 the head-blob checksum comparison, E3 `--source <head>` on `check-attr`. Each was neutralized with one targeted edit and restored with the inverse edit; no `git checkout`, `restore`, `reset` or `stash` was used. Run from `/home/user/wt-2243-e`, under `-X pycache_prefix=/tmp/c1l5b-pyc-e`. The captures below are the runner's whole output for each run apart from the `UV_NATIVE_TLS` deprecation warning line, which is left out; nothing is redacted (no secrets, tokens or URLs appear).

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| E1 | `countable_lines.py:352` `new is None or len(new) < _BINDING_MIN_HEX or not oid.startswith(new)` | a proof copy counts only when every diff section shown for it is bound to the head blob | `test_diff_of_one_commit_with_head_at_another_is_section_unbound` |
| E2 | `countable_lines.py:358` `hashlib.sha256(data).hexdigest() != copy["sha256"]` | a proof copy counts only when the head blob's bytes hash to the proof's checksum | `test_proof_matching_only_the_working_tree_is_a_checksum_mismatch` |
| E3 | `countable_lines.py:420` `"--source", head` in the `check-attr` argv | the attribute is read from the head commit's tree, never from the checkout's `.gitattributes` | `test_generated_attribute_comes_from_head_not_from_the_dirty_gitattributes` |

---

## E1 — the section-binding check

- **axis:** `proven_copies` rejects (`section-unbound`) a copy whose diff section's `index` new id is not a prefix of the head oid, even when the head bytes hash to the proof.

**neutralization** (`countable_lines.py`, `_reject_reason`):
```python
-        if new is None or len(new) < _BINDING_MIN_HEX or not oid.startswith(new):
+        if False:
             return "section-unbound"
```

**raw red:** `scripts/pinned-python -B -X pycache_prefix=/tmp/c1l5b-pyc-e -m pytest plugins/superheroes/lib/tests/test_countable_lines_c1l5.py -q -k test_diff_of_one_commit_with_head_at_another_is_section_unbound`
```
F                                                                        [100%]
=================================== FAILURES ===================================
_______ test_diff_of_one_commit_with_head_at_another_is_section_unbound ________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-1/test_diff_of_one_commit_with_h0')

    def test_diff_of_one_commit_with_head_at_another_is_section_unbound(tmp_path):
        root = _repo(tmp_path)
        _write(root, "seed.txt", "s\n")
        base = _commit(root, "base")
        _write(root, "f.txt", "aaaa\n")
        _commit(root, "A")
        diff_a = _diff(root, base)
        _write(root, "f.txt", "bbbb\n")
        _commit(root, "B")
        diff_b = _diff(root, base)
        proof = _proof(_copy("f.txt", b"bbbb\n"))
        proven, rejected = cl.proven_copies(diff_a, root, proof)
>       assert proven == [] and rejected == [{"file": "f.txt", "reason": "section-unbound"}]
E       AssertionError: assert ([{'file': 'f....7b3aa0a5a48'}] == []
E         
E         Left contains one more item: {'file': 'f.txt', 'source': 'src/orig.txt', 'sha256': '4551db5fd4d56e27be71a8a943070cfaa4342b8e960a326e2d6427b3aa0a5a48'}
E         Use -v to get more diff)

/home/user/wt-2243-e/plugins/superheroes/lib/tests/test_countable_lines_c1l5.py:418: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_countable_lines_c1l5.py::test_diff_of_one_commit_with_head_at_another_is_section_unbound
1 failed, 83 deselected in 0.34s
```

**restore:** the inverse edit, `if False:` back to the original condition.

**restore receipt:** the restored lines quoted back from the file (`Grep -n -B1 -A1 'oid.startswith\(new\)'`):
```
351-        new = section["indexNew"]
352:        if new is None or len(new) < _BINDING_MIN_HEX or not oid.startswith(new):
353-            return "section-unbound"
```

**raw green:** same command after the restore
```
.                                                                        [100%]
1 passed, 83 deselected in 0.28s
```

---

## E2 — the head-blob checksum comparison

- **axis:** `proven_copies` rejects (`checksum-mismatch`) a copy whose proof checksum matches the edited working-tree file but not the bytes at head.

**neutralization** (`countable_lines.py`, `_reject_reason`):
```python
-    if hashlib.sha256(data).hexdigest() != copy["sha256"]:
+    if False:
         return "checksum-mismatch"
```

**raw red:** `scripts/pinned-python -B -X pycache_prefix=/tmp/c1l5b-pyc-e -m pytest plugins/superheroes/lib/tests/test_countable_lines_c1l5.py -q -k test_proof_matching_only_the_working_tree_is_a_checksum_mismatch`
```
F                                                                        [100%]
=================================== FAILURES ===================================
_______ test_proof_matching_only_the_working_tree_is_a_checksum_mismatch _______

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-3/test_proof_matching_only_the_w0')

    def test_proof_matching_only_the_working_tree_is_a_checksum_mismatch(tmp_path):
        root, diff = _copy_fixture(tmp_path)
        (root / "copies/a.txt").write_bytes(b"edited after the commit\n")
        proven, rejected = cl.proven_copies(diff, root, _proof(_copy("copies/a.txt", b"edited after the commit\n")))
>       assert proven == []
E       AssertionError: assert [{'file': 'co...5a2fa0b177d'}] == []
E         
E         Left contains one more item: {'file': 'copies/a.txt', 'source': 'src/orig.txt', 'sha256': '87dab0abb860d181d62689529d40be1aa69d4181ac655ee9e8e825a2fa0b177d'}
E         Use -v to get more diff

/home/user/wt-2243-e/plugins/superheroes/lib/tests/test_countable_lines_c1l5.py:394: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_countable_lines_c1l5.py::test_proof_matching_only_the_working_tree_is_a_checksum_mismatch
1 failed, 83 deselected in 0.71s
```

**restore:** the inverse edit, `if False:` back to the original comparison.

**restore receipt:** the restored lines quoted back from the file (`Grep -n -B1 -A1 'hexdigest\(\) != copy'`):
```
357-    # Axis: a proof copy counts only when the head blob's bytes hash to the proof's checksum.
358-    if hashlib.sha256(data).hexdigest() != copy["sha256"]:
359-        return "checksum-mismatch"
```

**raw green:** same command after the restore
```
.                                                                        [100%]
1 passed, 83 deselected in 0.37s
```

---

## E3 — `--source <head>` on `check-attr`

- **axis:** the `linguist-generated` attribute is read from the head commit's `.gitattributes`; a committed attribute still excludes the file when the checkout's `.gitattributes` no longer carries it.

**neutralization** (`countable_lines.py`, `_attribute_flags`, the argv):
```python
-            ["git", "-C", os.fspath(repo_root), "check-attr", "--source", head, "-z", "linguist-generated", "--stdin"],
+            ["git", "-C", os.fspath(repo_root), "check-attr", "-z", "linguist-generated", "--stdin"],
```

**raw red:** `scripts/pinned-python -B -X pycache_prefix=/tmp/c1l5b-pyc-e -m pytest plugins/superheroes/lib/tests/test_countable_lines_c1l5.py -q -k test_generated_attribute_comes_from_head_not_from_the_dirty_gitattributes`
```
F                                                                        [100%]
=================================== FAILURES ===================================
__ test_generated_attribute_comes_from_head_not_from_the_dirty_gitattributes ___

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-5/test_generated_attribute_comes0')

    def test_generated_attribute_comes_from_head_not_from_the_dirty_gitattributes(tmp_path):
        root = _repo(tmp_path)
        _write(root, ".gitattributes", "by_attr.txt linguist-generated\n")
        base = _commit(root, "base")
        _write(root, "by_attr.txt", "a\nb\nc\n")
        _commit(root, "feature")
        diff = _diff(root, base)
        _write(root, ".gitattributes", "# nothing is generated here\n")
        rows = _rows(cl.count(diff, root))
>       assert rows["by_attr.txt"]["counted"] is False and rows["by_attr.txt"]["why"] == "generated"
E       assert (True is False)

/home/user/wt-2243-e/plugins/superheroes/lib/tests/test_countable_lines_c1l5.py:530: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_countable_lines_c1l5.py::test_generated_attribute_comes_from_head_not_from_the_dirty_gitattributes
1 failed, 83 deselected in 0.36s
```

**restore:** the inverse edit, `"--source", head,` put back after `"check-attr",`.

**restore receipt:** the restored line quoted back from the file (`Grep -n -B1 -A1 '"check-attr"'`):
```
419-        proc = subprocess.run(
420:            ["git", "-C", os.fspath(repo_root), "check-attr", "--source", head, "-z", "linguist-generated", "--stdin"],
421-            input=stdin, capture_output=True, timeout=ATTR_TIMEOUT, env=_git_env(),
```

**raw green:** same command after the restore
```
.                                                                        [100%]
1 passed, 83 deselected in 0.35s
```
