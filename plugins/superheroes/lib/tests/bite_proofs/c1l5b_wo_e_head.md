# C1-L5b (#2243 WO-E) bite-proof — the counter reads the reviewed head, not the checkout

**Provenance:** implementer WO-E / `lib/countable_lines.py`, `lib/tests/test_countable_lines_c1l5.py`

Declared guarded elements (from the order): E1 the section-binding check (`indexNew` prefix of the head oid), E2 the head-blob checksum comparison, E3 `--source <head>` on `check-attr`. Each was neutralized with one targeted edit and restored with the inverse edit; no `git checkout`, `restore`, `reset` or `stash` was used. Run from `/home/user/wt-2243-e`, under `-X pycache_prefix=/tmp/c1l5b-pyc-e`. The captures below are the runner's whole output for each run apart from the `UV_NATIVE_TLS` deprecation warning line, which is left out; nothing is redacted (no secrets, tokens or URLs appear).

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| E1 | `countable_lines.py:352` `new is None or len(new) < _BINDING_MIN_HEX or not oid.startswith(new)` | a proof copy counts only when every diff section shown for it is bound to the head blob | `test_diff_of_one_commit_with_head_at_another_is_section_unbound` |
| E2 | `countable_lines.py:358` `hashlib.sha256(data).hexdigest() != copy["sha256"]` | a proof copy counts only when the head blob's bytes hash to the proof's checksum | `test_proof_matching_only_the_working_tree_is_a_checksum_mismatch` |
| E3 | `countable_lines.py:420` `"--source", head` in the `check-attr` argv | the attribute is read from the head commit's tree, never from the checkout's `.gitattributes` | `test_generated_attribute_comes_from_head_not_from_the_dirty_gitattributes` |
| E4 | `countable_lines.py` `_moved_pairs`, the `(lines, final-newline flag)` comparison | a delete and an add pair as a move only when lines and final-newline status are equal | `test_a_move_that_adds_a_final_newline_counts` |
| E5 | `countable_lines.py` `_lexically_unsafe`, the `"\\" in file` test | a proof path holding a backslash is rejected `path-unsafe` | `test_a_proof_path_with_a_backslash_is_rejected_path_unsafe` |

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

---

## E4 — the final-newline comparison in `_moved_pairs`

Added in the rework (WO-H), run from `/home/user/wt-2243-h` under `-X pycache_prefix=/tmp/c1l5b-pyc-h`; the `UV_NATIVE_TLS` warning line is left out of the captures, and nothing is redacted.

- **axis:** a deleted section and an added section pair as a move only when their lines and their final-newline status are equal; a file of `x` deleted and a file of `x\n` added is a change that counts.

**neutralization** (`countable_lines.py`, `_moved_pairs`):
```python
-            if removed == (section["addedLines"], section["addedNoEol"]):
+            if removed[0] == section["addedLines"]:
```

**raw red:** `scripts/pinned-python -B -X pycache_prefix=/tmp/c1l5b-pyc-h -m pytest plugins/superheroes/lib/tests/test_countable_lines_c1l5.py -q -k test_a_move_that_adds_a_final_newline_counts`
```
F                                                                        [100%]
=================================== FAILURES ===================================
_________________ test_a_move_that_adds_a_final_newline_counts _________________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-39/test_a_move_that_adds_a_final_0')

    def test_a_move_that_adds_a_final_newline_counts(tmp_path):
        # axis: a delete and an add whose lines match but whose final-newline status differs is a change, not a move
        root, diff = _move_pair_diff(tmp_path, b"x", b"x\n")
        result = cl.count(diff, root)
        rows = _rows(result)
>       assert rows["new.txt"]["counted"] is True and rows["new.txt"]["lines"] == 1
E       assert (False is True)

/home/user/wt-2243-h/plugins/superheroes/lib/tests/test_countable_lines_c1l5.py:161: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_countable_lines_c1l5.py::test_a_move_that_adds_a_final_newline_counts
1 failed, 88 deselected in 2.40s
```

**restore:** the inverse edit, the tuple comparison back.

**restore receipt:** the restored lines quoted back from the file (`Grep -n -B1 -A1 'addedNoEol"\]\):'`):
```
421-            # Axis: a move keeps the bytes, so the final-newline status must match as well as the lines.
422:            if removed == (section["addedLines"], section["addedNoEol"]):
423-                moved.add(i)
```

**raw green:** same command after the restore
```
.                                                                        [100%]
1 passed, 88 deselected in 0.33s
```

---

## E5 — the backslash check in `_lexically_unsafe`

Added in the rework (WO-H), same environment as E4.

- **axis:** a proof path holding a backslash is rejected `path-unsafe`, so it is never proven and never reaches the leave-out file, which the loader would refuse.

**neutralization** (`countable_lines.py`, `_lexically_unsafe`):
```python
-    if os.path.isabs(file) or file.startswith("/") or "\\" in file:
+    if os.path.isabs(file) or file.startswith("/"):
```

**raw red:** `scripts/pinned-python -B -X pycache_prefix=/tmp/c1l5b-pyc-h -m pytest plugins/superheroes/lib/tests/test_countable_lines_c1l5.py -q -k test_a_proof_path_with_a_backslash_is_rejected_path_unsafe`
```
F                                                                        [100%]
=================================== FAILURES ===================================
__________ test_a_proof_path_with_a_backslash_is_rejected_path_unsafe __________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-41/test_a_proof_path_with_a_backs0')

    def test_a_proof_path_with_a_backslash_is_rejected_path_unsafe(tmp_path):
        # axis: a committed file name holding a backslash is never proven, because the leave-out loader would refuse it
        root = _repo(tmp_path)
        _write(root, "seed.txt", "s\n")
        base = _commit(root, "base")
        (root / "a\\b.txt").write_bytes(b"data\n")
        _commit(root, "feature")
        diff = _diff(root, base)
        proven, rejected = cl.proven_copies(diff, root, _proof(_copy("a\\b.txt", b"data\n")))
>       assert proven == [] and rejected == [{"file": "a\\b.txt", "reason": "path-unsafe"}]
E       AssertionError: assert ([{'file': 'a\...57b3e8f6e5f'}] == []
E         
E         Left contains one more item: {'file': 'a\\b.txt', 'source': 'src/orig.txt', 'sha256': '6667b2d1aab6a00caa5aee5af8ad9f1465e567abf1c209d15727d57b3e8f6e5f'}
E         Use -v to get more diff)

/home/user/wt-2243-h/plugins/superheroes/lib/tests/test_countable_lines_c1l5.py:638: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_countable_lines_c1l5.py::test_a_proof_path_with_a_backslash_is_rejected_path_unsafe
1 failed, 88 deselected in 0.46s
```

**restore:** the inverse edit, `or "\\" in file` put back.

**restore receipt:** the restored lines quoted back from the file (`Grep -n -A5 'def _lexically_unsafe'`):
```
254:def _lexically_unsafe(file):
255-    # Axis: any backslash makes a path unsafe, because the leave-out loader refuses an entry holding one.
256:    if os.path.isabs(file) or file.startswith("/") or "\\" in file:
257-        return True
258-    return ".." in file.split("/")
```

**raw green:** same command after the restore
```
.                                                                        [100%]
1 passed, 88 deselected in 0.29s
```

---

# WO-K (#2243) additions — copy sections, trailing deletions, physical marker lines

**Provenance:** implementer WO-K / `lib/countable_lines.py`, `lib/tests/test_countable_lines_c1l5.py`. Declared guarded elements (from the order): E6 the copy-section line count, E7 the deletion clamp, E8 the physical-line split. Each was neutralized with one targeted edit and restored with the inverse edit; no `git checkout`, `restore`, `reset` or `stash` was used. Run from `/home/user/wt-2243-k`, under `-X pycache_prefix=/tmp/c1l5b-pyc-k`. Each capture is the runner's whole output apart from the `UV_NATIVE_TLS` deprecation warning line, which is left out; nothing is redacted (no secrets, tokens or URLs appear). The restored lines are quoted from a read of the file after the inverse edit; no `git status --porcelain` was run.

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| E6 | `countable_lines.py:547` `if section["copied"] and decision not in _HUNKS_STAND:` (the whole-file count for a copy) | an unproven copy counts the whole head file, not its hunks | `test_an_unproven_copy_counts_the_whole_file` |
| E7 | `countable_lines.py:117` `at = new_no if hunk_last is None else min(new_no, hunk_last)` (the deletion clamp) | a deletion is recorded no further than the last head line its hunk's new side reaches | `test_a_trailing_deletion_stays_inside_the_head_file` |
| E8 | `countable_lines.py:493` the `data.split(b"\n", GENERATED_MARKER_LINES)[:GENERATED_MARKER_LINES]` scan | the marker scan covers five physical lines, however long the first one is | `test_a_marker_on_physical_line_five_after_a_long_line_is_generated` |

Not in the declared set, so not proven here: the sentinel assertion of `test_git_env_is_built_after_isolation_not_at_import` (test-001) and the fail-closed pin `test_a_copy_whose_head_blob_is_unreadable_is_unsettled_not_zero` (the generated test already yields `content-unreadable` for that diff, so it does not isolate the new branch).

## E6 — the copy-section line count

**neutralization** (`countable_lines.py`, `count`):
```python
-        if section["copied"] and decision not in _HUNKS_STAND:
+        if False and decision not in _HUNKS_STAND:
```

**raw red:** `scripts/pinned-python -B -X pycache_prefix=/tmp/c1l5b-pyc-k -m pytest plugins/superheroes/lib/tests/test_countable_lines_c1l5.py -q -k test_an_unproven_copy_counts_the_whole_file`
```
F                                                                        [100%]
=================================== FAILURES ===================================
_________________ test_an_unproven_copy_counts_the_whole_file __________________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-55/test_an_unproven_copy_counts_t0')

    def test_an_unproven_copy_counts_the_whole_file(tmp_path):
        # axis: a copy section's hunks show only its differences from the source, so an unproven copy counts the whole head file
        root, diff = _copy_diff(tmp_path)
        sections = {s["file"]: s for s in cl.parse_sections(diff)}
        assert sections["copies/same.txt"]["copied"] is True and sections["copies/same.txt"]["added"] == 0
        assert sections["copies/edited.txt"]["copied"] is True and sections["copies/edited.txt"]["added"] == 1
        result = cl.count(diff, root)
        rows = _rows(result)
>       assert rows["copies/same.txt"] == {"file": "copies/same.txt", "lines": 12, "counted": True, "why": None}
E       AssertionError: assert {'file': 'cop..., 'why': None} == {'file': 'cop..., 'why': None}
E         
E         Omitting 3 identical items, use -v to get more diff
E         Differing items:
E         {'lines': 0} != {'lines': 12}
E         Use -v to get more diff

/home/user/wt-2243-k/plugins/superheroes/lib/tests/test_countable_lines_c1l5.py:219: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_countable_lines_c1l5.py::test_an_unproven_copy_counts_the_whole_file
1 failed, 92 deselected in 0.37s
```

**restore:** the inverse edit, `section["copied"]` put back in place of `False`.

**restore receipt:** the restored lines quoted back from the file (lines 546-552):
```
        # A copy's hunks show only its differences from the source, so an unproven copy counts the whole file at head.
        if section["copied"] and decision not in _HUNKS_STAND:
            whole = _head_line_count(repo_root, head, section["file"])
            if whole is not None:
                lines = whole
            elif decision == "countable":
                decision = "content-unreadable"
```

**raw green:** same command after the restore
```
.                                                                        [100%]
1 passed, 92 deselected in 0.27s
```

## E7 — the deletion clamp

**neutralization** (`countable_lines.py`, `_parse_section`, the `lead == "-"` branch):
```python
-                at = new_no if hunk_last is None else min(new_no, hunk_last)
+                at = new_no
```

**raw red:** `scripts/pinned-python -B -X pycache_prefix=/tmp/c1l5b-pyc-k -m pytest plugins/superheroes/lib/tests/test_countable_lines_c1l5.py -q -k test_a_trailing_deletion_stays_inside_the_head_file`
```
F                                                                        [100%]
=================================== FAILURES ===================================
_____________ test_a_trailing_deletion_stays_inside_the_head_file ______________

    def test_a_trailing_deletion_stays_inside_the_head_file():
        # axis: a deletion is recorded no further than the last head line its hunk's new side reaches
        diff = "diff --git a/f.py b/f.py\n--- a/f.py\n+++ b/f.py\n@@ -1,3 +1,2 @@\n l1\n l2\n-l3\n"
>       assert cl.changed_parts(diff) == [{"file": "f.py", "lines": [[2, 2]]}]
E       AssertionError: assert [{'file': 'f....s': [[3, 3]]}] == [{'file': 'f....s': [[2, 2]]}]
E         
E         At index 0 diff: {'file': 'f.py', 'lines': [[3, 3]]} != {'file': 'f.py', 'lines': [[2, 2]]}
E         Use -v to get more diff

/home/user/wt-2243-k/plugins/superheroes/lib/tests/test_countable_lines_c1l5.py:802: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_countable_lines_c1l5.py::test_a_trailing_deletion_stays_inside_the_head_file
1 failed, 92 deselected in 0.52s
```

**restore:** the inverse edit, the `min(new_no, hunk_last)` conditional put back.

**restore receipt:** the restored lines quoted back from the file (lines 114-118):
```
            elif lead == "-":
                removed_lines.append(body)
                # A deletion sits where it was removed, but never past the last head line its hunk reaches.
                at = new_no if hunk_last is None else min(new_no, hunk_last)
                head_lines.append(max(at, 1))
```

**raw green:** same command after the restore
```
.                                                                        [100%]
1 passed, 92 deselected in 0.25s
```

## E8 — the physical-line split

**neutralization** (`countable_lines.py`, `_has_generated_marker`; `io` is no longer imported at module level, so the old `readline` form is reached through `__import__("io")` in the same edit):
```python
-    top = [raw[:_MAX_MARKER_LINE] for raw in data.split(b"\n", GENERATED_MARKER_LINES)[:GENERATED_MARKER_LINES]]
+    handle = __import__("io").BytesIO(data)
+    top = [handle.readline(_MAX_MARKER_LINE) for _ in range(GENERATED_MARKER_LINES)]
```

**raw red:** `scripts/pinned-python -B -X pycache_prefix=/tmp/c1l5b-pyc-k -m pytest plugins/superheroes/lib/tests/test_countable_lines_c1l5.py -q -k test_a_marker_on_physical_line_five_after_a_long_line_is_generated`
```
F                                                                        [100%]
=================================== FAILURES ===================================
______ test_a_marker_on_physical_line_five_after_a_long_line_is_generated ______

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-59/test_a_marker_on_physical_line0')

    def test_a_marker_on_physical_line_five_after_a_long_line_is_generated(tmp_path):
        # axis: the marker scan covers five physical lines, however long the first one is
        root = _repo(tmp_path)
        _write(root, "seed.txt", "s\n")
        base = _commit(root, "base")
        long_line = "x" * 70000 + "\n"
        _write(root, "long_five.py", long_line + "2\n3\n4\n# %s\n6\n" % GEN_TAG)
        _write(root, "long_six.py", long_line + "2\n3\n4\n5\n# %s\n" % GEN_TAG)
        _commit(root, "feature")
        result = cl.count(_diff(root, base), root)
        rows = _rows(result)
>       assert rows["long_five.py"]["counted"] is False and rows["long_five.py"]["why"] == "generated"
E       assert (True is False)

/home/user/wt-2243-k/plugins/superheroes/lib/tests/test_countable_lines_c1l5.py:270: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_countable_lines_c1l5.py::test_a_marker_on_physical_line_five_after_a_long_line_is_generated
1 failed, 92 deselected in 0.35s
```

**restore:** the inverse edit, the `split` expression put back in place of the two `readline` lines.

**restore receipt:** the restored lines quoted back from the file (lines 492-493):
```
    # Physical lines split on a newline byte alone; each is cut to ``_MAX_MARKER_LINE`` bytes for the search only.
    top = [raw[:_MAX_MARKER_LINE] for raw in data.split(b"\n", GENERATED_MARKER_LINES)[:GENERATED_MARKER_LINES]]
```

**raw green:** same command after the restore
```
.                                                                        [100%]
1 passed, 92 deselected in 0.30s
```
