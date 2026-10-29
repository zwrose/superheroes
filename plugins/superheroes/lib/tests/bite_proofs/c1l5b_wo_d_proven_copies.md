# C1-L5b (#2243 WO-D) bite-proof — proven copies end to end in the review driver and the record

**Provenance:** implementer WO-D / `lib/countable_lines.py`, `lib/round_driver.py`, `lib/review_record.py`, `lib/tests/test_proven_copies_c1l5b.py`

Declared guarded elements (from the order): E1 `_ensure_round_diff` writing the reviewer view, E2 the section-digest comparison in `still_proven`, E3 the leave-out file contents, E4 the risk-area filter, E5 `review_record`'s `provenCopies` validation (representative: the sha256 shape). Each was neutralized with one targeted edit and restored with the inverse edit; no `git checkout`, `restore`, `reset` or `stash` was used. Run from `/home/user/wt-2243-d`. The captures are the runner's whole output for each run apart from the `UV_NATIVE_TLS` deprecation warning line, which is left out; nothing is redacted (no secrets, tokens or URLs appear). E5's red capture elides four failures that repeat the shape of the first (said where it happens).

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| E1 | `round_driver.py` `_ensure_round_diff`, the `expected` line | the round's `diff.txt` is the reviewer view, with the copies still proven left out | `test_a_fresh_next_with_a_proof_gives_no_seat_the_proven_copy` |
| E2 | `countable_lines.py` `still_proven`, the `section_digest(...) == entry["section"]` test | a copy stays out of a diff only while its section is the one the proof was checked against | `test_a_copy_whose_section_changed_is_not_still_proven` |
| E3 | `round_driver.py` `_left_out_files`, the returned list | the leave-out file names the copies still proven, and nothing else | `test_the_leave_out_file_names_exactly_the_proven_copy` |
| E4 | `round_driver.py` `_risk_areas_text`, the `paths` filter | a proven copy no seat is given is not named as touching a risk area | `test_the_test_role_risk_clause_does_not_name_the_proven_copy` |
| E5 | `review_record.py` `_proven_copies_fault`, the sha256 shape test | a proven copy's checksum is 64 lowercase hex | `test_a_proven_copy_checksum_that_is_not_64_lowercase_hex_refuses` |

E5 stands for the validation's other shape tests (the exact key set, non-blank `file` and `source`, each file once); those are covered by `test_a_malformed_proven_copies_list_refuses` and were not separately neutralized, so they are the one unproven part of the validation's failure modes.

---

## E1 — `_ensure_round_diff` writes the reviewer view

**neutralization** (`round_driver.py`, `_ensure_round_diff`):
```python
-    expected = countable_lines.reviewer_diff(diff_text, _left_out(state, diff_text)).encode("utf-8")
+    expected = diff_text.encode("utf-8")
```

**raw red:** `scripts/pinned-python -B -X pycache_prefix=/tmp/c1l5b-pyc-d -m pytest plugins/superheroes/lib/tests/test_proven_copies_c1l5b.py -q -k test_a_fresh_next_with_a_proof_gives_no_seat_the_proven_copy`
```
F                                                                        [100%]
=================================== FAILURES ===================================
_________ test_a_fresh_next_with_a_proof_gives_no_seat_the_proven_copy _________

started = <test_proven_copies_c1l5b.Fx object at 0x7fadda3bfe90>

    def test_a_fresh_next_with_a_proof_gives_no_seat_the_proven_copy(started):
        # axis: the round's diff.txt leaves out the proven copy and keeps the uncovered file and the mismatched copy
        text = _read(os.path.join(started.dir, "round-1", "diff.txt"))
>       assert sorted(_files(text)) == [MISMATCH, OTHER]
E       AssertionError: assert ['src/mismatc...ents/copy.py'] == ['src/mismatc...src/other.py']
E         
E         Left contains one more item: 'src/payments/copy.py'
E         Use -v to get more diff

/home/user/wt-2243-d/plugins/superheroes/lib/tests/test_proven_copies_c1l5b.py:158: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_proven_copies_c1l5b.py::test_a_fresh_next_with_a_proof_gives_no_seat_the_proven_copy
1 failed, 41 deselected in 2.05s
```

**restore:** the inverse edit, the `expected` line back to the reviewer view.

**restore receipt:** the restored line quoted from the file after the edit (`grep -n`, round_driver.py:10685):
```
10685:    expected = countable_lines.reviewer_diff(diff_text, _left_out(state, diff_text)).encode("utf-8")
```

**raw green:** same command after the restore
```
.                                                                        [100%]
1 passed, 41 deselected in 4.80s
```

---

## E2 — the section-digest comparison in `still_proven`

**neutralization** (`countable_lines.py`, `still_proven`):
```python
-        if section_digest(diff_text, entry["file"]) == entry["section"]:
+        if True:
```

**raw red:** `scripts/pinned-python -B -X pycache_prefix=/tmp/c1l5b-pyc-d -m pytest plugins/superheroes/lib/tests/test_proven_copies_c1l5b.py -q -k test_a_copy_whose_section_changed_is_not_still_proven`
```
F                                                                        [100%]
=================================== FAILURES ===================================
____________ test_a_copy_whose_section_changed_is_not_still_proven _____________

    def test_a_copy_whose_section_changed_is_not_still_proven():
        # axis: still_proven keeps a copy only while its file's section digest equals the stored one
        one = ("diff --git a/c.py b/c.py\nnew file mode 100644\nindex 0000000..1111111\n--- /dev/null\n+++ b/c.py\n"
               "@@ -0,0 +1 @@\n+x\n")
        two = ("diff --git a/d.py b/d.py\nnew file mode 100644\nindex 0000000..2222222\n--- /dev/null\n+++ b/d.py\n"
               "@@ -0,0 +1 @@\n+y\n")
        edited = one.replace("+x", "+z")
        entries = [{"file": "c.py", "source": "s.py", "sha256": HEX, "section": cl.section_digest(one + two, "c.py")},
                   {"file": "d.py", "source": "t.py", "sha256": "b" * 64, "section": cl.section_digest(one + two, "d.py")}]
        both = [{"file": "c.py", "source": "s.py", "sha256": HEX}, {"file": "d.py", "source": "t.py", "sha256": "b" * 64}]
        assert cl.still_proven(entries, one + two) == both
>       assert cl.still_proven(entries, edited + two) == both[1:]
E       AssertionError: assert [{'file': 'c....bbbbbbbbbbb'}] == [{'file': 'd....bbbbbbbbbbb'}]
E         
E         At index 0 diff: {'file': 'c.py', 'source': 's.py', 'sha256': 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'} != {'file': 'd.py', 'source': 't.py', 'sha256': 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'}
E         Left contains one more item: {'file': 'd.py', 'source': 't.py', 'sha256': 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'}
E         Use -v to get more diff

/home/user/wt-2243-d/plugins/superheroes/lib/tests/test_proven_copies_c1l5b.py:318: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_proven_copies_c1l5b.py::test_a_copy_whose_section_changed_is_not_still_proven
1 failed, 41 deselected in 1.40s
```

**restore:** the inverse edit, `if True:` back to the comparison.

**restore receipt:** the restored line quoted from the file after the edit (`grep -n`, countable_lines.py:574):
```
574:        if section_digest(diff_text, entry["file"]) == entry["section"]:
```

**raw green:** same command after the restore
```
.                                                                        [100%]
1 passed, 41 deselected in 0.96s
```

---

## E3 — the leave-out file contents

**neutralization** (`round_driver.py`, `_left_out_files`):
```python
-    return [copy["file"] for copy in _left_out(state, diff_text)]
+    return []
```

**raw red:** `scripts/pinned-python -B -X pycache_prefix=/tmp/c1l5b-pyc-d -m pytest plugins/superheroes/lib/tests/test_proven_copies_c1l5b.py -q -k test_the_leave_out_file_names_exactly_the_proven_copy`
```
F                                                                        [100%]
=================================== FAILURES ===================================
____________ test_the_leave_out_file_names_exactly_the_proven_copy _____________

started = <test_proven_copies_c1l5b.Fx object at 0x7ff682146f00>

    def test_the_leave_out_file_names_exactly_the_proven_copy(started):
        # axis: the engine reviewer's leave-out file holds the proven copies and nothing else
        leave_out = json.loads(_read(os.path.join(started.dir, "reviewer-leave-out.json")))
>       assert leave_out == {"schema": "leave-out/1", "files": [COPY]}
E       AssertionError: assert {'files': [],...'leave-out/1'} == {'schema': 'l...nts/copy.py']}
E         
E         Omitting 1 identical items, use -vv to show
E         Differing items:
E         {'files': []} != {'files': ['src/payments/copy.py']}
E         Use -v to get more diff

/home/user/wt-2243-d/plugins/superheroes/lib/tests/test_proven_copies_c1l5b.py:166: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_proven_copies_c1l5b.py::test_the_leave_out_file_names_exactly_the_proven_copy
1 failed, 41 deselected in 1.36s
```

**restore:** the inverse edit, `return []` back to the list over `_left_out`.

**restore receipt:** the restored line quoted from the file after the edit (`grep -n`, round_driver.py:10715):
```
10715:    return [copy["file"] for copy in _left_out(state, diff_text)]
```

**raw green:** same command after the restore
```
.                                                                        [100%]
1 passed, 41 deselected in 1.63s
```

---

## E4 — the risk-area filter

**neutralization** (`round_driver.py`, `_risk_areas_text`):
```python
-        paths = [path for path in paths if path not in left_out]
+        paths = list(paths)
```

**raw red:** `scripts/pinned-python -B -X pycache_prefix=/tmp/c1l5b-pyc-d -m pytest plugins/superheroes/lib/tests/test_proven_copies_c1l5b.py -q -k test_the_test_role_risk_clause_does_not_name_the_proven_copy`
```
F                                                                        [100%]
=================================== FAILURES ===================================
_________ test_the_test_role_risk_clause_does_not_name_the_proven_copy _________

started = <test_proven_copies_c1l5b.Fx object at 0x7fbea9c53f20>

    def test_the_test_role_risk_clause_does_not_name_the_proven_copy(started):
        # axis: the risk-area clause reads the changed paths less the proven copies, which sit under a declared area
        state = started.state()
        control = RD._risk_areas_text("test-role", str(started.root), started.base, started.head)
        assert control == "Payments (matched: %s)" % COPY
        ph = RD._order_placeholders(RD.P_PANEL, "test-role", 0, state, state["config"], None, started.dir, 1, {},
                                    RD.CHANNEL_FILE)
>       assert ph["RISK_AREAS_TEXT"] == "none of this project's risk areas"
E       assert 'Payments (ma...ents/copy.py)' == "none of this...'s risk areas"
E         
E         - none of this project's risk areas
E         + Payments (matched: src/payments/copy.py)

/home/user/wt-2243-d/plugins/superheroes/lib/tests/test_proven_copies_c1l5b.py:185: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_proven_copies_c1l5b.py::test_the_test_role_risk_clause_does_not_name_the_proven_copy
1 failed, 41 deselected in 1.42s
```

**restore:** the inverse edit, `list(paths)` back to the filter.

**restore receipt:** the restored line quoted from the file after the edit (`grep -n`, round_driver.py:10050):
```
10050:        paths = [path for path in paths if path not in left_out]
```

**raw green:** same command after the restore
```
.                                                                        [100%]
1 passed, 41 deselected in 1.55s
```

---

## E5 — `provenCopies` validation, the sha256 shape (representative of the validation)

**neutralization** (`review_record.py`, `_proven_copies_fault`):
```python
-        if not (isinstance(x["sha256"], str) and _SHA256_RE.fullmatch(x["sha256"])):
+        if not isinstance(x["sha256"], str):
```

**raw red:** `scripts/pinned-python -B -X pycache_prefix=/tmp/c1l5b-pyc-d -m pytest plugins/superheroes/lib/tests/test_proven_copies_c1l5b.py -q -k test_a_proven_copy_checksum_that_is_not_64_lowercase_hex_refuses`

Elided: the failure blocks of parameters 2 to 5 (65 `a`s, 64 `A`s, 64 `g`s, the empty string) are the same as the first apart from the parameter and the temporary path; the short test summary below lists all five. About 4.5 KiB.
```
FFFFF..                                                                  [100%]
=================================== FAILURES ===================================
_ test_a_proven_copy_checksum_that_is_not_64_lowercase_hex_refuses[aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa] _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-27/test_a_proven_copy_checksum_th0')
digest = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'

    @pytest.mark.parametrize("digest", ["a" * 63, "a" * 65, "A" * 64, "g" * 64, "", None, 7])
    def test_a_proven_copy_checksum_that_is_not_64_lowercase_hex_refuses(tmp_path, digest):
        # axis: a proven copy's checksum is 64 lowercase hex, the form the advisor's vet can check against the source
        fake = RecordFake()
        path = tmp_path / "account.json"
        path.write_text(json.dumps(record_account(provenCopies=[dict(GOOD, sha256=digest)])))
        out = rr.write(str(path), str(tmp_path), fake.readers())
>       assert (out["ok"], out["reason"], out["detail"]) == (False, "review-account-invalid", "provenCopies[0].sha256")
                           ^^^^^^^^^^^^^
E       KeyError: 'reason'

/home/user/wt-2243-d/plugins/superheroes/lib/tests/test_proven_copies_c1l5b.py:394: KeyError
[... four more failure blocks of the same shape elided ...]
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_proven_copies_c1l5b.py::test_a_proven_copy_checksum_that_is_not_64_lowercase_hex_refuses[aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa]
FAILED plugins/superheroes/lib/tests/test_proven_copies_c1l5b.py::test_a_proven_copy_checksum_that_is_not_64_lowercase_hex_refuses[aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa]
FAILED plugins/superheroes/lib/tests/test_proven_copies_c1l5b.py::test_a_proven_copy_checksum_that_is_not_64_lowercase_hex_refuses[AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA]
FAILED plugins/superheroes/lib/tests/test_proven_copies_c1l5b.py::test_a_proven_copy_checksum_that_is_not_64_lowercase_hex_refuses[gggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggg]
FAILED plugins/superheroes/lib/tests/test_proven_copies_c1l5b.py::test_a_proven_copy_checksum_that_is_not_64_lowercase_hex_refuses[]
5 failed, 2 passed, 35 deselected in 1.29s
```

The `KeyError: 'reason'` is the red: with the shape test neutralized the malformed checksum is accepted, so the write succeeds and returns no `reason`.

**restore:** the inverse edit, the `isinstance` test back to the `_SHA256_RE.fullmatch` test.

**restore receipt:** the restored line quoted from the file after the edit (`grep -n`, review_record.py:528):
```
528:        if not (isinstance(x["sha256"], str) and _SHA256_RE.fullmatch(x["sha256"])):
```

**raw green:** same command after the restore
```
.......                                                                  [100%]
7 passed, 35 deselected in 0.90s
```

---

## E6 — the reviewer view passed to `_shard_payload` (the panel's shard lists)

**neutralization** (`round_driver.py`, `_advance`, the `P_PANEL` branch, back to the raw `reviewedDiff`):
```python
-            diff_text = countable_lines.reviewer_diff(diff_text, _left_out(state, diff_text))
+            diff_text = diff_text
```

**raw red:** `scripts/pinned-python -B -X pycache_prefix=/tmp/c1l5b-pyc-d -m pytest plugins/superheroes/lib/tests/test_proven_copies_c1l5b.py -q -k test_a_big_panel_names_the_proven_copy_in_no_lens_shards`
```
F                                                                        [100%]
=================================== FAILURES ===================================
___________ test_a_big_panel_names_the_proven_copy_in_no_lens_shards ___________

started = <test_proven_copies_c1l5b.Fx object at 0x7f2ab8ee5e80>

    def test_a_big_panel_names_the_proven_copy_in_no_lens_shards(started):
        # axis: the panel payload's shard plan is built from the reviewer view, so no lens's shards name a proven copy
        diff = _big_diff()
        assert RD.delta_surface.shard_plan(diff)["big"] is True
        state = _panel_state(started, diff)
        payload = RD._advance(state, state["config"])["payload"]
        assert payload["big"] is True
        named = _lens_shard_files(payload)
        assert named
        for lens, files in named.items():
>           assert COPY not in files, lens
E           AssertionError: code-reviewer
E           assert 'src/payments/copy.py' not in ['docs/guide.md', 'src/mod00.py', 'src/mod01.py', 'src/mod02.py', 'src/mod03.py', 'src/mod04.py', ...]

/home/user/wt-2243-d/plugins/superheroes/lib/tests/test_proven_copies_c1l5b.py:456: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_proven_copies_c1l5b.py::test_a_big_panel_names_the_proven_copy_in_no_lens_shards
1 failed, 45 deselected in 1.53s
```

Redacted: nothing. The pytest `warning: The UV_NATIVE_TLS ...` line the wrapper prints before the output is left out of both captures.

**restore:** the inverse edit, `diff_text = diff_text` back to the `countable_lines.reviewer_diff(...)` call.

**restore receipt:** the restored line quoted from the file after the edit (`grep -n`, round_driver.py:2811):
```
2811:            diff_text = countable_lines.reviewer_diff(diff_text, _left_out(state, diff_text))
```

**raw green:** same command after the restore
```
.                                                                        [100%]
1 passed, 45 deselected in 1.90s
```
