# #2501 bite-proof — a misread lizard span reads unmeasured, never a number

**Provenance:** implementer work order WO-1 (issue 2501) / `lib/guardian_lens_hotspots.py` (`_span_rules`, `_check_file_spans`, `_run_lizard`, `HotspotsLens._collect_complexity`, `HotspotsLens._collect`), `lib/tests/test_guardian_lens_hotspots.py` (section `# #2501: a misread lizard span reads unmeasured, never a number`). Worktree base `ae07e1e3a5db4dbf9f8fd951195e52251f807e31`, working tree uncommitted.

Declared guarded elements (from the order): G1 to G10 below. Each was neutralized with one targeted Edit, run alone against its named detector by exact node id (unedited, never `-k`; G2 named two node ids and ran both in one call), restored with the inverse Edit (never `git checkout`, `restore`, `reset` or `stash`), and the same node id or ids then ran green. Every run was `scripts/pinned-python -B -X pycache_prefix=/tmp/wo1-pyc -m pytest "<node id>" -q` from the worktree root (the sandbox accepted the `-X pycache_prefix` flag). The captures are unfiltered except that the launcher's one-line `UV_NATIVE_TLS` deprecation warning (the first line of every real run) was dropped. They hold no secrets, tokens, private URLs or PII; the only paths are repository paths and pytest temp-directory paths; nothing was redacted. Every capture is far under the 32 KiB per-element ceiling, so nothing went to scratch. Each neutralized target was asserted to occur exactly once before the edit (the edit tool requires a unique match) and, after the restore, a content search returned the restored line once at the line number quoted. All node ids are in `plugins/superheroes/lib/tests/test_guardian_lens_hotspots.py`, written below without that prefix.

| ID | Guarded element (`guardian_lens_hotspots.py`) | Axis | Detector (exact node id) |
|---|---|---|---|
| G1 | `_span_rules`, the crossing leg (line 701) | a row that starts inside another row and ends after it is a misread, and only the earlier row is | `test_overlapping_span_marks_only_the_crossing_row_and_the_max_ignores_it` |
| G2 | `_span_rules`, the declaration match (line 687) | a declaration line inside a row's span, at or above its start indentation, makes it a misread (including semicolon-terminated one-line siblings) | `test_swallowed_declaration_reads_unmeasured_with_no_red_line` and `test_swallowed_semicolon_terminated_siblings_read_unmeasured` |
| G3 | `_span_rules`, the `e > n` clause of span-invalid (line 696) | an end line past the file's last line is an impossible span | `test_span_invalid_edges_read_unmeasured[e5-end-past-end-of-file]` |
| G4 | `_span_rules`, the strict interior (`last = bisect_left(decl_nums, e)`, line 706) | the end line itself is excluded from the declaration scan, so the measured TypeScript overrun onto the next declaration is not a misread | `test_healthy_typescript_overrun_onto_the_next_declaration_stays_measured` |
| G5 | `_span_rules`, the `e < e2` clause of crossing (line 701) | one row inside another is nesting, not a crossing | `test_nested_functions_are_nesting_not_a_misread` |
| G6 | `_collect_complexity`, the unreadable line goes to `other_gaps` (line 1181) | an unreadable source is a per-file error and never a permanent boundary | `test_unreadable_source_is_a_per_file_error_and_never_a_permanent_boundary` |
| G7 | `_collect_complexity`, the span line's count (line 1175) | the note counts misread functions, not files | `test_the_note_counts_functions_not_files` |
| G8 | `_span_rules`, the `e < s` clause of span-invalid (line 696) | a reversed span is an impossible span | `test_span_invalid_edges_read_unmeasured[e3-end-before-start]` |
| G9 | `_run_lizard`, the orphan gate `if rel in requested` (line 789) | only a requested operand's rows are span-checked, so an orphan key still reaches `_join_anomaly` | `test_join_anomaly_per_language_radon_error_does_not_mask_js` (the existing `OTHER.js` test, test file line 514) |
| G10 | `_check_file_spans`, sound rows only (line 725) | a misread row contributes nothing to its file's max | `test_overlapping_span_marks_only_the_crossing_row_and_the_max_ignores_it` |

Not separately neutralized, so tested but unproven by this record: E1 (a row with fewer than 11 columns; cases `e1-ten-columns`, `e1-nine-columns`), E2 (a non-integer start or end; cases `e2-start-not-integer`, `e2-end-not-integer`), E4 (`s < 1`; case `e4-start-below-one`), the `s > n` clause of E5 (case `e5-start-past-end-of-file`), E8 (an empty file; case `e8-empty-file`), E11 (the pre-existing empty-output and reported-nonzero-parsed-zero guards, unchanged and covered by the existing `test_run_lizard_nonempty_parsed_zero_degrades_js`), and E14 (CRLF; `test_crlf_source_counts_lines_and_compares_indentation_the_same`). Those span-invalid clauses share one `or` chain with G3 and G8; a clause dropped from it was not run alone. Also not neutralized: the declaration regex's individual alternatives (G2 neutralizes the match as a whole), the `s is None or e is None` clause, the JSX-plus-misread boundary case, the failed-language-plus-misread case, the drift test, and `parse_lizard_csv` staying span-free. Those have tests but no recorded red.

Fenced captures below carry pytest's own multi-space alignment (`E   `, indented source); that is the tool's output, not an edit.

---

## G1 — the crossing leg

**neutralization** (`guardian_lens_hotspots.py:701`; the crossing comparison never fires):
```python
-        if any(spans[k][1] > e for k in range(lo, hi)):
+        if False and any(spans[k][1] > e for k in range(lo, hi)):
```

**raw red** (axis check: the red is on the missing crossing entry for `a`, not on a count or a max):
```
F                                                                        [100%]
=================================== FAILURES ===================================
___ test_overlapping_span_marks_only_the_crossing_row_and_the_max_ignores_it ___

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-2/test_overlapping_span_marks_on0')

    def test_overlapping_span_marks_only_the_crossing_row_and_the_max_ignores_it(tmp_path):
        # a@1-10 and b@5-20 cross (1 < 5 < 10 < 20); only `a` is the misread, and `b` (CCN 12) is
        # the file's max — a max that counts `a` reads 40.
        run = _span_run(
            tmp_path, {"over.ts": "  step();\n" * 20},
            _span_row("over.ts", "a", 40, 1, 10) + _span_row("over.ts", "b", 12, 5, 20))
        out = hot.HotspotsLens().collect(_ctx(tmp_path, run))
    
>       assert _span_errors(out) == [_misread_entry("over.ts", "a", 1, 10, "crossing")]
E       AssertionError: assert [] == [{'collector'...n': 'a', ...}]
E         
E         Right contains one more item: {'collector': 'lizard', 'path': 'over.ts', 'kind': 'span-misread', 'function': 'a', ...}
E         Use -v to get more diff

/home/user/wt-2501/plugins/superheroes/lib/tests/test_guardian_lens_hotspots.py:1808: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_guardian_lens_hotspots.py::test_overlapping_span_marks_only_the_crossing_row_and_the_max_ignores_it
1 failed in 0.39s
```

**restore:** the inverse Edit removed `False and `.

**restore receipt** (restored content, `guardian_lens_hotspots.py:701`, found once by content search):
```python
        if any(spans[k][1] > e for k in range(lo, hi)):
```

**raw green:**
```
.                                                                        [100%]
1 passed in 0.43s
```

---

## G2 — the declaration match

**neutralization** (`guardian_lens_hotspots.py:687`; no line is ever a declaration):
```python
-        if _DECL_RE.match(stripped):
+        if False and _DECL_RE.match(stripped):
```

**raw red** (both node ids in one call; axis check: both reds are on the digest still holding a score — `ccn` 100 and 14 — where the order wants the span-misread record; the file was scored, not unmeasured):
```
FF                                                                       [100%]
=================================== FAILURES ===================================
_________ test_swallowed_declaration_reads_unmeasured_with_no_red_line _________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-4/test_swallowed_declaration_rea0')

    def test_swallowed_declaration_reads_unmeasured_with_no_red_line(tmp_path):
        # The measured break1.ts: one row for `first` that holds `second` and `third`. Its CCN sits
        # at the red-line threshold, so a lens that scores it raises a red line.
        ccn = gl.RED_LINE_THRESHOLDS["complexity"]
        run = _span_run(tmp_path, {"break1.ts": _BREAK1_TS}, _span_row("break1.ts", "first", ccn, 1, 22))
        lens = hot.HotspotsLens()
        out = lens.collect(_ctx(tmp_path, run))
    
>       assert out["digest"]["files"] == {"hotspots:break1.ts": _MISREAD_DIGEST}
E       AssertionError: assert {'hotspots:br..., 'ccn': 100}} == {'hotspots:br...pan-misread'}}
E         
E         Differing items:
E         {'hotspots:break1.ts': {'score': 90.9091, 'ccn': 100}} != {'hotspots:break1.ts': {'unmeasured': True, 'reason': 'span-misread'}}
E         Use -v to get more diff

/home/user/wt-2501/plugins/superheroes/lib/tests/test_guardian_lens_hotspots.py:1825: AssertionError
_________ test_swallowed_semicolon_terminated_siblings_read_unmeasured _________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-4/test_swallowed_semicolon_termi0')

    def test_swallowed_semicolon_terminated_siblings_read_unmeasured(tmp_path):
        assert len(_SWALLOW2_TS.splitlines()) == 17
        run = _span_run(
            tmp_path, {"swallow2.ts": _SWALLOW2_TS}, _span_row("swallow2.ts", "first", 14, 1, 17))
        out = hot.HotspotsLens().collect(_ctx(tmp_path, run))
    
>       assert out["digest"]["files"] == {"hotspots:swallow2.ts": _MISREAD_DIGEST}
E       AssertionError: assert {'hotspots:sw...6, 'ccn': 14}} == {'hotspots:sw...pan-misread'}}
E         
E         Differing items:
E         {'hotspots:swallow2.ts': {'score': 16.4706, 'ccn': 14}} != {'hotspots:swallow2.ts': {'unmeasured': True, 'reason': 'span-misread'}}
E         Use -v to get more diff

/home/user/wt-2501/plugins/superheroes/lib/tests/test_guardian_lens_hotspots.py:1839: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_guardian_lens_hotspots.py::test_swallowed_declaration_reads_unmeasured_with_no_red_line
FAILED plugins/superheroes/lib/tests/test_guardian_lens_hotspots.py::test_swallowed_semicolon_terminated_siblings_read_unmeasured
2 failed in 0.51s
```

**restore:** the inverse Edit removed `False and `.

**restore receipt** (restored content, `guardian_lens_hotspots.py:687`, found once by content search):
```python
        if _DECL_RE.match(stripped):
```

**raw green** (both node ids):
```
..                                                                       [100%]
2 passed in 0.47s
```

---

## G3 — span-invalid, the `e > n` clause

**neutralization** (`guardian_lens_hotspots.py:696`; only `or e > n` is dropped):
```python
-        if s is None or e is None or s < 1 or e < s or s > n or e > n:
+        if s is None or e is None or s < 1 or e < s or s > n:
```

**raw red** (axis check: the file is 10 lines and the row ends at 11; with the clause gone the row passes every leg and the file reads measured, `ccn` 15):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_______ test_span_invalid_edges_read_unmeasured[e5-end-past-end-of-file] _______

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-6/test_span_invalid_edges_read_u0')
source = '  step();\n  step();\n  step();\n  step();\n  step();\n  step();\n  step();\n  step();\n  step();\n  step();\n'
tail = ',2,11', start = 2, end = 11

    @pytest.mark.parametrize(
        "source, tail, start, end", [c[1:] for c in _SPAN_INVALID_CASES],
        ids=[c[0] for c in _SPAN_INVALID_CASES])
    def test_span_invalid_edges_read_unmeasured(tmp_path, source, tail, start, end):
        row = "20,15,10,1,5,f@1-5@bad.ts,bad.ts,f,f ( a )%s\n" % tail
        run = _span_run(tmp_path, {"bad.ts": source}, row)
        out = hot.HotspotsLens().collect(_ctx(tmp_path, run))
    
>       assert out["digest"]["files"] == {"hotspots:bad.ts": _MISREAD_DIGEST}
E       AssertionError: assert {'hotspots:ba...0, 'ccn': 15}} == {'hotspots:ba...pan-misread'}}
E         
E         Differing items:
E         {'hotspots:bad.ts': {'score': 30.0, 'ccn': 15}} != {'hotspots:bad.ts': {'unmeasured': True, 'reason': 'span-misread'}}
E         Use -v to get more diff

/home/user/wt-2501/plugins/superheroes/lib/tests/test_guardian_lens_hotspots.py:1914: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_guardian_lens_hotspots.py::test_span_invalid_edges_read_unmeasured[e5-end-past-end-of-file]
1 failed in 0.36s
```

**restore:** the inverse Edit put `or e > n` back.

**restore receipt** (restored content, `guardian_lens_hotspots.py:696`, found once by content search):
```python
        if s is None or e is None or s < 1 or e < s or s > n or e > n:
```

**raw green:**
```
.                                                                        [100%]
1 passed in 0.35s
```

---

## G4 — the strict interior (end line excluded)

**neutralization** (`guardian_lens_hotspots.py:706`; the declaration scan now reaches the end line):
```python
-        last = bisect_left(decl_nums, e)
+        last = bisect_right(decl_nums, e)
```

**raw red** (axis check: the healthy sweep is no longer `collected`; the measured overrun of `a@3-14` onto the `export const b` line is flagged because line 14 is now scanned):
```
F                                                                        [100%]
=================================== FAILURES ===================================
___ test_healthy_typescript_overrun_onto_the_next_declaration_stays_measured ___

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-8/test_healthy_typescript_overru0')

    def test_healthy_typescript_overrun_onto_the_next_declaration_stays_measured(tmp_path):
        run = _span_run(
            tmp_path, {"seps.ts": _SEPS_TS},
            _span_row("seps.ts", "a", 13, 3, 14) + _span_row("seps.ts", "b", 11, 14, 19))
        out = hot.HotspotsLens().collect(_ctx(tmp_path, run))
    
>       assert gl.classify_collect(out) == ("collected", None)
E       AssertionError: assert ('partial', '...s unmeasured') == ('collected', None)
E         
E         At index 0 diff: 'partial' != 'collected'
E         Use -v to get more diff

/home/user/wt-2501/plugins/superheroes/lib/tests/test_guardian_lens_hotspots.py:1851: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_guardian_lens_hotspots.py::test_healthy_typescript_overrun_onto_the_next_declaration_stays_measured
1 failed in 0.39s
```

**restore:** the inverse Edit put `bisect_left` back.

**restore receipt** (restored content, `guardian_lens_hotspots.py:706`, found once by content search):
```python
        last = bisect_left(decl_nums, e)
```

**raw green:**
```
.                                                                        [100%]
1 passed in 0.36s
```

---

## G5 — containment is nesting (the `e < e2` clause)

**neutralization** (`guardian_lens_hotspots.py:701`; the end comparison is removed, so any row starting strictly inside another counts as crossing):
```python
-        if any(spans[k][1] > e for k in range(lo, hi)):
+        if any(True for k in range(lo, hi)):
```

**raw red** (axis check: `outer@1-18` holds `inner@2-7` and `helper@8-11`; with containment read as crossing the healthy file is no longer `collected`):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_______________ test_nested_functions_are_nesting_not_a_misread ________________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-10/test_nested_functions_are_nest0')

    def test_nested_functions_are_nesting_not_a_misread(tmp_path):
        rows = "".join(_span_row("nested.ts", name, ccn, s, e) for name, ccn, s, e in (
            ("outer", 13, 1, 18), ("inner", 11, 2, 7), ("helper", 12, 8, 11), ("second", 10, 18, 23)))
        assert len(_NESTED_TS.splitlines()) == 23
        run = _span_run(tmp_path, {"nested.ts": _NESTED_TS}, rows)
        out = hot.HotspotsLens().collect(_ctx(tmp_path, run))
    
>       assert gl.classify_collect(out) == ("collected", None)
E       AssertionError: assert ('partial', '...s unmeasured') == ('collected', None)
E         
E         At index 0 diff: 'partial' != 'collected'
E         Use -v to get more diff

/home/user/wt-2501/plugins/superheroes/lib/tests/test_guardian_lens_hotspots.py:1886: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_guardian_lens_hotspots.py::test_nested_functions_are_nesting_not_a_misread
1 failed in 0.41s
```

**restore:** the inverse Edit put `spans[k][1] > e` back.

**restore receipt** (restored content, `guardian_lens_hotspots.py:701`, found once by content search):
```python
        if any(spans[k][1] > e for k in range(lo, hi)):
```

**raw green:**
```
.                                                                        [100%]
1 passed in 0.38s
```

---

## G6 — an unreadable source is never a permanent boundary

**neutralization** (`guardian_lens_hotspots.py:1181`; the unreadable line is filed as a boundary gap):
```python
-            other_gaps.append(unreadable_line)
+            boundary_gaps.append(unreadable_line)
```

**raw red** (axis check: the status and the reason text already passed; the red is the single `permanentBoundary` assertion, `True` where `False` is required):
```
F                                                                        [100%]
=================================== FAILURES ===================================
__ test_unreadable_source_is_a_per_file_error_and_never_a_permanent_boundary ___

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-12/test_unreadable_source_is_a_pe0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7eff66af5460>

    def test_unreadable_source_is_a_per_file_error_and_never_a_permanent_boundary(
            tmp_path, monkeypatch):
        sources = {"gone.ts": "x\n" * 20, "ok.ts": "x\n" * 20}
        run = _span_run(
            tmp_path, sources, _lizard_row("gone.ts", 30) + _lizard_row("ok.ts", 12))
        real = hot._read_source
        reads = []
    
        def read(abs_path):
            reads.append(os.path.basename(abs_path))
            if os.path.basename(abs_path) == "gone.ts":
                raise OSError("unreadable")
            return real(abs_path)
    
        monkeypatch.setattr(hot, "_read_source", read)
        out = hot.HotspotsLens().collect(_ctx(tmp_path, run))
    
        status, reason = gl.classify_collect(out)
        assert status == "partial"
        assert "1 file(s) unmeasured — source could not be read" in reason
>       assert gl.permanent_boundary(out) is False
E       AssertionError: assert True is False
E        +  where True = <function permanent_boundary at 0x7eff66cfca40>({'candidates': [{'id': 'hotspots:ok.ts', 'path': 'ok.ts', 'relativeChurn': 1.0, 'hotspotScore': 12.0, ...}], 'digest':...{'collector': 'lizard', 'path': 'gone.ts', 'kind': 'source-unreadable'}], 'minCcn': 10, ...}, 'status': 'partial', ...})
E        +    where <function permanent_boundary at 0x7eff66cfca40> = gl.permanent_boundary

/home/user/wt-2501/plugins/superheroes/lib/tests/test_guardian_lens_hotspots.py:1961: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_guardian_lens_hotspots.py::test_unreadable_source_is_a_per_file_error_and_never_a_permanent_boundary
1 failed in 0.40s
```

**restore:** the inverse Edit put `other_gaps` back.

**restore receipt** (restored content, `guardian_lens_hotspots.py:1181`, found once by content search; the search matched the three `unreadable_line` lines 1179 to 1181):
```python
            other_gaps.append(unreadable_line)
```

**raw green:**
```
.                                                                        [100%]
1 passed in 0.35s
```

---

## G7 — the note counts functions

**neutralization** (`guardian_lens_hotspots.py:1175`; the count is the number of files with a misread):
```python
-            span_line = _span_gap(len(span_report["misreads"]))
+            span_line = _span_gap(len({m["path"] for m in span_report["misreads"]}))
```

**raw red** (axis check: the sweep has three misread functions in two files; the reason reads `2 function(s)`, where `3` is required):
```
F                                                                        [100%]
=================================== FAILURES ===================================
___________________ test_the_note_counts_functions_not_files ___________________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-14/test_the_note_counts_functions0')

    def test_the_note_counts_functions_not_files(tmp_path):
        sources = {"p.ts": _STEP10, "q.ts": _STEP10, "ok.ts": "x\n" * 20}
        lizard = (_span_row("p.ts", "f1", 20, 2, 11) + _span_row("p.ts", "f2", 21, 3, 12)
                  + _span_row("q.ts", "g", 22, 1, 20) + _lizard_row("ok.ts", 12))
        run = _span_run(tmp_path, sources, lizard)
        out = hot.HotspotsLens().collect(_ctx(tmp_path, run))
    
        line = "javascript: 3 function(s) unmeasured — " + hot.SPAN_UNMEASURED_DETAIL
        status, reason = gl.classify_collect(out)
        assert status == "partial"
>       assert line in reason
E       assert "javascript: 3 function(s) unmeasured — lizard's reported span runs over another function or past a declaration no single brace block could hold, so that function's complexity is unmeasured" in "javascript: 2 function(s) unmeasured — lizard's reported span runs over another function or past a declaration no single brace block could hold, so that function's complexity is unmeasured"

/home/user/wt-2501/plugins/superheroes/lib/tests/test_guardian_lens_hotspots.py:1930: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_guardian_lens_hotspots.py::test_the_note_counts_functions_not_files
1 failed in 0.38s
```

**restore:** the inverse Edit put `len(span_report["misreads"])` back.

**restore receipt** (restored content, `guardian_lens_hotspots.py:1175`, found once by content search):
```python
            span_line = _span_gap(len(span_report["misreads"]))
```

**raw green:**
```
.                                                                        [100%]
1 passed in 0.40s
```

---

## G8 — span-invalid, the `e < s` clause

**neutralization** (`guardian_lens_hotspots.py:696`; only `or e < s` is dropped):
```python
-        if s is None or e is None or s < 1 or e < s or s > n or e > n:
+        if s is None or e is None or s < 1 or s > n or e > n:
```

**raw red** (axis check: the row is 8 to 3 in a 10-line file, so no other clause fires; the file reads measured, `ccn` 15):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_________ test_span_invalid_edges_read_unmeasured[e3-end-before-start] _________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-16/test_span_invalid_edges_read_u0')
source = '  step();\n  step();\n  step();\n  step();\n  step();\n  step();\n  step();\n  step();\n  step();\n  step();\n'
tail = ',8,3', start = 8, end = 3

    @pytest.mark.parametrize(
        "source, tail, start, end", [c[1:] for c in _SPAN_INVALID_CASES],
        ids=[c[0] for c in _SPAN_INVALID_CASES])
    def test_span_invalid_edges_read_unmeasured(tmp_path, source, tail, start, end):
        row = "20,15,10,1,5,f@1-5@bad.ts,bad.ts,f,f ( a )%s\n" % tail
        run = _span_run(tmp_path, {"bad.ts": source}, row)
        out = hot.HotspotsLens().collect(_ctx(tmp_path, run))
    
>       assert out["digest"]["files"] == {"hotspots:bad.ts": _MISREAD_DIGEST}
E       AssertionError: assert {'hotspots:ba...0, 'ccn': 15}} == {'hotspots:ba...pan-misread'}}
E         
E         Differing items:
E         {'hotspots:bad.ts': {'score': 30.0, 'ccn': 15}} != {'hotspots:bad.ts': {'unmeasured': True, 'reason': 'span-misread'}}
E         Use -v to get more diff

/home/user/wt-2501/plugins/superheroes/lib/tests/test_guardian_lens_hotspots.py:1914: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_guardian_lens_hotspots.py::test_span_invalid_edges_read_unmeasured[e3-end-before-start]
1 failed in 0.40s
```

**restore:** the inverse Edit put `or e < s` back.

**restore receipt** (restored content, `guardian_lens_hotspots.py:696`, found once by content search):
```python
        if s is None or e is None or s < 1 or e < s or s > n or e > n:
```

**raw green:**
```
.                                                                        [100%]
1 passed in 0.38s
```

---

## G9 — the orphan gate

**neutralization** (`guardian_lens_hotspots.py:789`; every row is span-checked, whether or not its path was an operand):
```python
-            if rel in requested:
+            if True or rel in requested:
```

**raw red** (axis check: lizard's `OTHER.js` row is not a requested operand; checked anyway, its source does not exist, so it reads `source-unreadable`, no real orphan key reaches `_join_anomaly`, and the sweep is `partial` where the existing test requires `not-collected`):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_________ test_join_anomaly_per_language_radon_error_does_not_mask_js __________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-18/test_join_anomaly_per_language0')

    def test_join_anomaly_per_language_radon_error_does_not_mask_js(tmp_path):
        """A (global-suppression bug gone): a radon per-file error must NOT suppress a genuine
        js path-join failure. Python collects (one per-file error recorded); lizard emits a
        key orphaned off every tracked js file → the js anomaly still degrades the sweep."""
        _write(tmp_path, "a.py", 20)   # measured python
        _write(tmp_path, "c.py", 20)   # radon per-file error (1 < threshold, not all files)
        _write(tmp_path, "b.js", 20)   # churned js, but lizard reports OTHER.js (orphan)
        run = _basic_tools(
            tmp_path,
            numstat="20\t0\ta.py\n20\t0\tc.py\n20\t0\tb.js\n",
            lsfiles=["a.py", "c.py", "b.js"],
            radon={"a.py": [{"complexity": 15, "name": "f", "lineno": 1}],
                   "c.py": [{"error": "invalid syntax"}]},
            lizard="20,30,10,0,20,x@1-20@OTHER.js,OTHER.js,x,sig,1,20\n")
        out = hot.HotspotsLens().collect(_ctx(tmp_path, run))
        status, reason = gl.classify_collect(out)
>       assert status == "not-collected"          # OLD bug: read as collected (suppressed)
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AssertionError: assert 'partial' == 'not-collected'
E         
E         - not-collected
E         + partial

/home/user/wt-2501/plugins/superheroes/lib/tests/test_guardian_lens_hotspots.py:530: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_guardian_lens_hotspots.py::test_join_anomaly_per_language_radon_error_does_not_mask_js
1 failed in 0.38s
```

**restore:** the inverse Edit removed `True or `.

**restore receipt** (restored content, `guardian_lens_hotspots.py:789`, found once by content search):
```python
            if rel in requested:
```

**raw green:**
```
.                                                                        [100%]
1 passed in 0.35s
```

---

## G10 — sound rows only

**neutralization** (`guardian_lens_hotspots.py:725`; every row counts toward the file's max):
```python
-    sound = [row for row, rule in zip(rows, rules) if rule is None]
+    sound = list(rows)
```

**raw red** (axis check: the `collectorErrors` assertion before it passed, so `a` is still reported as a crossing misread; the red is on the max, `('over.ts', 40, 'a')` where `('over.ts', 12, 'b')` is required):
```
F                                                                        [100%]
=================================== FAILURES ===================================
___ test_overlapping_span_marks_only_the_crossing_row_and_the_max_ignores_it ___

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-20/test_overlapping_span_marks_on0')

    def test_overlapping_span_marks_only_the_crossing_row_and_the_max_ignores_it(tmp_path):
        # a@1-10 and b@5-20 cross (1 < 5 < 10 < 20); only `a` is the misread, and `b` (CCN 12) is
        # the file's max — a max that counts `a` reads 40.
        run = _span_run(
            tmp_path, {"over.ts": "  step();\n" * 20},
            _span_row("over.ts", "a", 40, 1, 10) + _span_row("over.ts", "b", 12, 5, 20))
        out = hot.HotspotsLens().collect(_ctx(tmp_path, run))
    
        assert _span_errors(out) == [_misread_entry("over.ts", "a", 1, 10, "crossing")]
>       assert [(c["path"], c["maxFunctionCCN"], c["worstFunction"]["name"])
                for c in out["candidates"]] == [("over.ts", 12, "b")]
E       AssertionError: assert [('over.ts', 40, 'a')] == [('over.ts', 12, 'b')]
E         
E         At index 0 diff: ('over.ts', 40, 'a') != ('over.ts', 12, 'b')
E         Use -v to get more diff

/home/user/wt-2501/plugins/superheroes/lib/tests/test_guardian_lens_hotspots.py:1809: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_guardian_lens_hotspots.py::test_overlapping_span_marks_only_the_crossing_row_and_the_max_ignores_it
1 failed in 0.42s
```

**restore:** the inverse Edit put the filtered list back.

**restore receipt** (restored content, `guardian_lens_hotspots.py:725`, found once by content search):
```python
    sound = [row for row, rule in zip(rows, rules) if rule is None]
```

**raw green:**
```
.                                                                        [100%]
1 passed in 0.36s
```

---

G1 and G10 share one detector node; the two reds differ (G1 red on the `collectorErrors` assertion, G10 red on the candidate's max after that assertion passed), so one node tells the two neutralizations apart.
