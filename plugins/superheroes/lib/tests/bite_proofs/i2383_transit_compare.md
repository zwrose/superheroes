# #2383 bite-proof — the transit read-back of `cloud_builder` and `pr_comment` writes

**Provenance:** implementer work order A2 / `lib/cloud_builder.py`, `lib/pr_comment.py`, `lib/tests/test_transit_readback_2383.py`

Declared guarded elements (from the order): E1 `transit_compare`'s difference detection; E2 the one-footer allowance; E3 the trailing-only normalization; E4 `not-checked` on a missing read-back; E5 `post_comment`'s read-back wiring; E6 `edit_comment`'s read-back wiring; E7 `pr_comment.upsert`'s read-back wiring; E8 the `readback` verb's comparison wiring. Each was neutralized with one targeted Edit, run alone against its named detector (a single test node, unedited), and restored with the inverse Edit (never `git checkout`, `restore`, `reset` or `stash`); the same command then ran green. Every run was `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest <node> -q -p no:cacheprovider --tb=line` from the worktree root. The captures are unfiltered except that the launcher's one-line `UV_NATIVE_TLS` deprecation warning was dropped (it is the first line of every real run). They hold no secrets, tokens, private URLs or PII; the only paths are pytest's own.

The restore receipt for every element is `git diff -- plugins/superheroes/lib/cloud_builder.py plugins/superheroes/lib/pr_comment.py` printing nothing (exit 0) after the inverse Edit; the commit HEAD (`0b8e7f73`) holds both production files. After E8, `git status --porcelain plugins/superheroes/lib/cloud_builder.py plugins/superheroes/lib/pr_comment.py` also printed nothing (exit 0).

| ID | Guarded element | Axis | Detector (all in `test_transit_readback_2383.py`) |
|---|---|---|---|
| E1 | `cloud_builder.py` `transit_compare`, the opcode loop that builds `changes` | a body that differs reads `changed`, not `matched` | `test_a_dropped_bang_reads_changed_through_post_comment` |
| E2 | `cloud_builder.py` `transit_compare`, `if b.endswith(tail):` | exactly one trailing footer is tolerated; a second is a change | `test_a_second_footer_reads_changed` |
| E3 | `cloud_builder.py` `transit_compare`, the `.rstrip()` on `sent` and `found` | only trailing whitespace is normalized; a lost leading indent is a change | `test_a_lost_leading_indent_reads_changed` |
| E4 | `cloud_builder.py` `transit_compare`, the `not isinstance(found, str)` branch | a read-back that could not be made is `not-checked`, never `matched` | `test_a_failed_read_back_is_not_checked_never_matched` |
| E5 | `cloud_builder.py` `post_comment`, the `_with_transit` return | the write is read back and the result carries `transit` | `test_a_dropped_bang_reads_changed_through_post_comment` |
| E6 | `cloud_builder.py` `edit_comment`, the `_with_transit` return | the rewrite is read back and the result carries `transit` | `test_edit_comment_reports_a_changed_read_back` |
| E7 | `pr_comment.py` `upsert`, `found = held.get("body") ...` | the final body sent is compared with what GitHub holds, not with itself | `test_upsert_create_reports_a_changed_read_back` |
| E8 | `cloud_builder.py` `readback`, the `_with_transit` call | the verb compares the held text with the sent file, not the file with itself | `test_readback_by_comment_id_changed` |
| E9 | `cloud_builder.py` `transit_compare`, the `elif session_footer:` branch over `_SESSION_FOOTER_RE` | one trailing session-form footer (the one the egress appends to a pull request body) is tolerated; a second is a change | `test_one_trailing_session_footer_is_tolerated`, `test_a_second_session_footer_reads_changed` |

Not separately neutralized, so unproven by this record: the `transit_compare` branch for a non-string `sent`, the `except Exception` branch (`the comparison failed`), the `\r\n` normalization, the cap on `changes` and the excerpt length, `transit_line`'s own branches, `read_pr_body`'s null-as-empty rule and the `--pr` path of `readback`, and `upsert`'s `except Exception` fall-through to `found = None` (each is asserted by a test in the suite but was not run against a mutation).

Line numbers are those at HEAD `0b8e7f73`; the neutralization of each is a one-line change shown below.

---

## E1 — difference detection

**neutralization** (`cloud_builder.py`, `transit_compare`, a line inserted before `changes = []` so a differing body returns `matched`):
```python
+        return {"transit": TRANSIT_MATCHED}  # BITE-PROOF NEUTRALIZED
         changes = []
```

**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
E   AssertionError: assert 'matched' == 'changed'
      
      - changed
      + matched
/home/user/wt-2383/plugins/superheroes/lib/tests/test_transit_readback_2383.py:77: AssertionError: assert 'matched' == 'changed'
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_transit_readback_2383.py::test_a_dropped_bang_reads_changed_through_post_comment
1 failed in 0.33s
```

**restore:** the inverse Edit removed the added `return {"transit": TRANSIT_MATCHED}  # BITE-PROOF NEUTRALIZED` line.

**restore receipt:** `git diff -- plugins/superheroes/lib/cloud_builder.py plugins/superheroes/lib/pr_comment.py` printed nothing (exit 0).

**raw green:**
```
.                                                                        [100%]
1 passed in 0.30s
```

---

## E2 — the one-footer allowance

**neutralization** (`cloud_builder.py`, `transit_compare`, so every trailing footer is removed):
```python
-        if b.endswith(tail):
+        while b.endswith(tail):  # BITE-PROOF NEUTRALIZED
```

**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
E   AssertionError: assert 'matched' == 'changed'
      
      - changed
      + matched
/home/user/wt-2383/plugins/superheroes/lib/tests/test_transit_readback_2383.py:132: AssertionError: assert 'matched' == 'changed'
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_transit_readback_2383.py::test_a_second_footer_reads_changed
1 failed in 0.33s
```

**restore:** the inverse Edit put `if b.endswith(tail):` back.

**restore receipt:** `git diff -- plugins/superheroes/lib/cloud_builder.py plugins/superheroes/lib/pr_comment.py` printed nothing (exit 0).

**raw green:**
```
.                                                                        [100%]
1 passed in 0.26s
```

---

## E3 — trailing-only normalization

**neutralization** (`cloud_builder.py`, `transit_compare`, `.rstrip()` to `.strip()` on both sides):
```python
-        a = sent.replace("\r\n", "\n").rstrip()
-        b = found.replace("\r\n", "\n").rstrip()
+        a = sent.replace("\r\n", "\n").strip()  # BITE-PROOF NEUTRALIZED
+        b = found.replace("\r\n", "\n").strip()  # BITE-PROOF NEUTRALIZED
```

**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
E   AssertionError: assert 'matched' == 'changed'
      
      - changed
      + matched
/home/user/wt-2383/plugins/superheroes/lib/tests/test_transit_readback_2383.py:123: AssertionError: assert 'matched' == 'changed'
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_transit_readback_2383.py::test_a_lost_leading_indent_reads_changed
1 failed in 0.27s
```

**restore:** the inverse Edit put the two `.rstrip()` lines back.

**restore receipt:** `git diff -- plugins/superheroes/lib/cloud_builder.py plugins/superheroes/lib/pr_comment.py` printed nothing (exit 0).

**raw green:**
```
.                                                                        [100%]
1 passed in 0.27s
```

---

## E4 — `not-checked` on a missing read-back

**neutralization** (`cloud_builder.py`, `transit_compare`, a non-string `found` is treated as `""`; the return line is replaced):
```python
-        return _transit_not_checked("the text could not be read back")  # axis: a missing read-back is not-checked, never matched — see bite-proof record i2383_transit_compare
+        found = ""  # BITE-PROOF NEUTRALIZED
```

**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
E   AssertionError: assert 'changed' == 'not-checked'
      
      - not-checked
      + changed
/home/user/wt-2383/plugins/superheroes/lib/tests/test_transit_readback_2383.py:114: AssertionError: assert 'changed' == 'not-checked'
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_transit_readback_2383.py::test_a_failed_read_back_is_not_checked_never_matched
1 failed in 0.25s
```

**restore:** the inverse Edit put the `return _transit_not_checked("the text could not be read back")  # axis: …` line back verbatim.

**restore receipt:** `git diff -- plugins/superheroes/lib/cloud_builder.py plugins/superheroes/lib/pr_comment.py` printed nothing (exit 0).

**raw green:**
```
.                                                                        [100%]
1 passed in 0.29s
```

---

## E5 — `post_comment`'s read-back wiring

**neutralization** (`cloud_builder.py`, `post_comment`, the result is returned without `_with_transit`):
```python
-    return _with_transit(result, _read_text(body_path), found)
+    return result  # BITE-PROOF NEUTRALIZED
```

**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
E   KeyError: 'transit'
/home/user/wt-2383/plugins/superheroes/lib/tests/test_transit_readback_2383.py:77: KeyError: 'transit'
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_transit_readback_2383.py::test_a_dropped_bang_reads_changed_through_post_comment
1 failed in 0.27s
```

**restore:** the inverse Edit put `return _with_transit(result, _read_text(body_path), found)` back.

**restore receipt:** `git diff -- plugins/superheroes/lib/cloud_builder.py plugins/superheroes/lib/pr_comment.py` printed nothing (exit 0).

**raw green:**
```
.                                                                        [100%]
1 passed in 0.25s
```

---

## E6 — `edit_comment`'s read-back wiring

**neutralization** (`cloud_builder.py`, `edit_comment`, same shape as E5):
```python
-    return _with_transit(result, _read_text(body_path), found)
+    return result  # BITE-PROOF NEUTRALIZED
```

**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
E   KeyError: 'transit'
/home/user/wt-2383/plugins/superheroes/lib/tests/test_transit_readback_2383.py:246: KeyError: 'transit'
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_transit_readback_2383.py::test_edit_comment_reports_a_changed_read_back
1 failed in 0.25s
```

**restore:** the inverse Edit put `return _with_transit(result, _read_text(body_path), found)` back.

**restore receipt:** `git diff -- plugins/superheroes/lib/cloud_builder.py plugins/superheroes/lib/pr_comment.py` printed nothing (exit 0).

**raw green:**
```
.                                                                        [100%]
1 passed in 0.25s
```

---

## E7 — `pr_comment.upsert`'s read-back wiring

**neutralization** (`pr_comment.py`, `upsert`, so the read-back is the body that was sent):
```python
-        found = held.get("body") if isinstance(held, dict) else None
+        found = body  # BITE-PROOF NEUTRALIZED
```

**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
E   AssertionError: assert 'matched' == 'changed'
      
      - changed
      + matched
/home/user/wt-2383/plugins/superheroes/lib/tests/test_transit_readback_2383.py:421: AssertionError: assert 'matched' == 'changed'
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_transit_readback_2383.py::test_upsert_create_reports_a_changed_read_back
1 failed in 0.32s
```

**restore:** the inverse Edit put `found = held.get("body") if isinstance(held, dict) else None` back.

**restore receipt:** `git diff -- plugins/superheroes/lib/cloud_builder.py plugins/superheroes/lib/pr_comment.py` printed nothing (exit 0).

**raw green:**
```
.                                                                        [100%]
1 passed in 0.26s
```

---

## E8 — the `readback` verb's comparison wiring

**neutralization** (`cloud_builder.py`, `readback`, so the sent text is compared with itself):
```python
-    return _with_transit({"ok": True}, _read_text(sent_path), found)
+    return _with_transit({"ok": True}, _read_text(sent_path), _read_text(sent_path))  # BITE-PROOF NEUTRALIZED
```

**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
E   AssertionError: assert 'matched' == 'changed'
      
      - changed
      + matched
/home/user/wt-2383/plugins/superheroes/lib/tests/test_transit_readback_2383.py:331: AssertionError: assert 'matched' == 'changed'
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_transit_readback_2383.py::test_readback_by_comment_id_changed
1 failed in 0.33s
```

**restore:** the inverse Edit put `return _with_transit({"ok": True}, _read_text(sent_path), found)` back.

**restore receipt:** `git diff -- plugins/superheroes/lib/cloud_builder.py plugins/superheroes/lib/pr_comment.py` printed nothing (exit 0), and `git status --porcelain plugins/superheroes/lib/cloud_builder.py plugins/superheroes/lib/pr_comment.py` printed nothing (exit 0).

**raw green:**
```
.                                                                        [100%]
1 passed in 0.25s
```

---

## E9 — the session-footer allowance (added by work order A3)

Two neutralizations, each its own red, each restored by the inverse Edit (never `git checkout`, `restore`, `reset` or `stash`) before the next. Run as for E1–E8, with the launcher's one-line `UV_NATIVE_TLS` deprecation warning dropped. The URL in the footer is a placeholder-free public host; the session id used in the tests is the made-up `01ABCxyz`; nothing in the captures is redacted.

### E9a — drop the regex branch (detector: `test_one_trailing_session_footer_is_tolerated`)

**neutralization** (`cloud_builder.py`, `transit_compare`, the `elif` can never fire):
```python
-        elif session_footer:
+        elif False:  # BITE-PROOF NEUTRALIZED
```

**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
E   AssertionError: assert {'transit': '...i/code/ses'}]} == {'transit': 'matched'}
      
      Differing items:
      {'transit': 'changed'} != {'transit': 'matched'}
      Left contains 2 more items:
      {'changeCount': 1,
       'changes': [{'at': 9,
                    'found': '\n'...
      
      ...Full output truncated, use '-vv' to show
/home/user/wt-2383/plugins/superheroes/lib/tests/test_transit_readback_2383.py:146: AssertionError: assert {'transit': '...i/code/ses'}]} == {'transit': 'matched'}
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_transit_readback_2383.py::test_one_trailing_session_footer_is_tolerated
1 failed in 0.29s
```

**restore:** the inverse Edit put `elif session_footer:` back.

**restore receipt:** `git diff -- plugins/superheroes/lib/cloud_builder.py` after the restore showed only the intended change; the restored lines, quoted from it:
```
+        session_footer = _SESSION_FOOTER_RE.search(b)
         if b.endswith(tail):
 ...
+        elif session_footer:
+            b = b[:session_footer.start()].rstrip()
+            if a == b:
+                return {"transit": TRANSIT_MATCHED}
```
(the same diff also holds the added `_SESSION_FOOTER_RE` constant and the extended axis comment; no `BITE-PROOF NEUTRALIZED` text remained).

**raw green:**
```
.                                                                        [100%]
1 passed in 0.27s
```

### E9b — make the regex branch remove every session footer (detector: `test_a_second_session_footer_reads_changed`)

**neutralization** (`cloud_builder.py`, `transit_compare`, the branch loops until no session footer is left):
```python
         elif session_footer:
-            b = b[:session_footer.start()].rstrip()
+            while session_footer:  # BITE-PROOF NEUTRALIZED
+                b = b[:session_footer.start()].rstrip()
+                session_footer = _SESSION_FOOTER_RE.search(b)
```

**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
E   AssertionError: assert 'matched' == 'changed'
      
      - changed
      + matched
/home/user/wt-2383/plugins/superheroes/lib/tests/test_transit_readback_2383.py:153: AssertionError: assert 'matched' == 'changed'
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_transit_readback_2383.py::test_a_second_session_footer_reads_changed
1 failed in 0.59s
```

**restore:** the inverse Edit removed the `while` loop and put `b = b[:session_footer.start()].rstrip()` back.

**restore receipt:** `git diff -- plugins/superheroes/lib/cloud_builder.py` after the restore showed only the intended change; the restored lines, quoted from it:
```
+        elif session_footer:
+            b = b[:session_footer.start()].rstrip()
+            if a == b:
+                return {"transit": TRANSIT_MATCHED}
```

**raw green:**
```
.                                                                        [100%]
1 passed in 0.25s
```
