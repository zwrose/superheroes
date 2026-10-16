# WO-4b bite-proof (C7 L1) — end-of-loop settle

**Provenance:** claude / sonnet-5.5 (implementer). Run from `/home/user/c7-wt`; every red and green is the detector node run alone (`scripts/pinned-python -B -m pytest "<node>" -q -p no:cacheprovider`). Restores are inverse edits only (no `git checkout`/`restore`/`stash`/`reset`). Captures are unredacted: they carry no secrets, tokens, private URLs or PII — only sandbox temp paths.

## Guarded elements (the set WO-4 declared)

| ID | Guarded element | Axis | Detector |
|---|---|---|---|
| G7 | the settle call inside `_set_terminal` (`plugins/superheroes/lib/round_driver.py`) | every terminal write also gives every finding an outcome | T5: `plugins/superheroes/lib/tests/test_outcome_settle_c7.py::test_t5_a_loop_run_to_its_terminal_leaves_no_finding_undecided` |
| G8 | the code-quality condition in `_nit_cap` (`plugins/superheroes/lib/round_driver.py`) | only a Nit whose consequenceKind is exactly "code-quality" collapses into the readout summary | T8: `plugins/superheroes/lib/tests/test_outcome_settle_c7.py::test_t8_nit_cap_collapses_only_code_quality_nits_into_craft` |
| G9 | the merge drop rows in `mechanical_compile` (`plugins/superheroes/lib/round_driver.py`) | a same-place-and-title merge is recorded as a drop row, not lost silently | T9: `plugins/superheroes/lib/tests/test_outcome_settle_c7.py::test_t9_same_place_duplicates_merge_and_record_the_merge` |
| G10 | the `decidedBy` shape check in `_validate_ruling_entries` (`plugins/superheroes/lib/round_driver.py`) | a malformed `decidedBy` is refused with `ruling-decided-by-malformed` | T10: `plugins/superheroes/lib/tests/test_outcome_settle_c7.py::test_t10_a_malformed_decided_by_is_refused_and_state_is_unchanged` |
| G11 | the `severityChange` stamp in `apply_verdicts` (`plugins/superheroes/lib/verification.py`) | a verdict that lowers a finding's severity leaves a `severityChange` row; a raise or no change leaves none | T6: `plugins/superheroes/lib/tests/test_outcome_settle_c7.py::test_t6_severity_change_defaults_its_reason_and_ignores_a_raise` |
| G12 | one converted terminal site, `_park_capped` (`plugins/superheroes/lib/round_driver.py`) | no function other than `_set_terminal` writes `state["terminal"]` | T7: `plugins/superheroes/lib/tests/test_outcome_settle_c7.py::test_t7_one_writer_of_the_terminal_and_it_is_set_terminal` |

No grouping: six elements, six neutralizations, six reds. No element is unproven.

---

## G7 — the settle call inside `_set_terminal`

- **axis:** every terminal write also gives every finding an outcome
- **file:** `plugins/superheroes/lib/round_driver.py`
- **detector:** `plugins/superheroes/lib/tests/test_outcome_settle_c7.py::test_t5_a_loop_run_to_its_terminal_leaves_no_finding_undecided` (T5)
- **sha256 before:** `b11cd9956f1ce9c0a63d0639e36f94755c0cd52202cdd0045c0c516a80f2d334`
- **sha256 neutralized:** `bcf294ef9d3f95eacdbbf440c10249ebf15b4df90fea99b719ce276a4276734d`
- **sha256 after restore:** `b11cd9956f1ce9c0a63d0639e36f94755c0cd52202cdd0045c0c516a80f2d334` (equals "before")

**neutralization** (one line, targeted):
```diff
-    _settle_open_findings(state, cap=cap)
+    pass  # NEUTRALIZED G7: _settle_open_findings(state, cap=cap)
```

**raw red** (`G7` neutralized):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
________ test_t5_a_loop_run_to_its_terminal_leaves_no_finding_undecided ________

sources_calls = []

    def test_t5_a_loop_run_to_its_terminal_leaves_no_finding_undecided(sources_calls):
        result, state = _run_once([
            _finding("Null deref", 1, "Important", "real"),
            _finding("Naming", 2, "Minor", "code-quality"),
            _finding("Docs lie", 2, "Nit", "real"),
            _finding("Null deref", 1, "Important", "real"),  # the same place and title twice
        ])
        assert state["terminal"]
>       _assert_all_settled(state)

/home/user/c7-wt/plugins/superheroes/lib/tests/test_outcome_settle_c7.py:265: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

state = {'schemaVersion': 5, 'sessionGeneration': 4, 'config': {'leg': 'code', 'panel': False, 'code': True, 'vendors': ['claude', 'codex'], ...}, 'round': 2, ...}

    def _assert_all_settled(state):
        ledger = _ledger(state)
        assert ledger
        for key, row in ledger.items():
            if row.get("summaryEntry") or row.get(SC.MERGED_INTO_FIELD):
                continue
>           assert row.get("disposition") in SC.DISPOSITIONS, (key, row)
E           AssertionError: ('f.py::naming@L2', {'file': 'f.py', 'line': 2, 'title': 'Naming', 'severity': 'Minor', ...})
E           assert None in ('fixed', 'refuted', 'out-of-scope', 'craft', 'left-for-owner', 'ruling')
E            +  where None = <built-in method get of dict object at 0x7faf1bf17140>('disposition')
E            +    where <built-in method get of dict object at 0x7faf1bf17140> = {'file': 'f.py', 'line': 2, 'title': 'Naming', 'severity': 'Minor', ...}.get
E            +  and   ('fixed', 'refuted', 'out-of-scope', 'craft', 'left-for-owner', 'ruling') = SC.DISPOSITIONS

/home/user/c7-wt/plugins/superheroes/lib/tests/test_outcome_settle_c7.py:252: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_outcome_settle_c7.py::test_t5_a_loop_run_to_its_terminal_leaves_no_finding_undecided
1 failed in 0.36s
```

**restore:** the inverse edit of the line above (the `NEUTRALIZED` text replaced by the original).

**restore receipt** (restored lines quoted back by `grep -n`):
```
1808-    state["terminal"] = verdict
1809:    _settle_open_findings(state, cap=cap)
```

**raw green** (after restore):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 3.63s
```

---

## G8 — the code-quality condition in `_nit_cap`

- **axis:** only a Nit whose consequenceKind is exactly "code-quality" collapses into the readout summary
- **file:** `plugins/superheroes/lib/round_driver.py`
- **detector:** `plugins/superheroes/lib/tests/test_outcome_settle_c7.py::test_t8_nit_cap_collapses_only_code_quality_nits_into_craft` (T8)
- **sha256 before:** `b11cd9956f1ce9c0a63d0639e36f94755c0cd52202cdd0045c0c516a80f2d334`
- **sha256 neutralized:** `03de2bf1605af55afa8ae2e254aa37a3b3996f7349a036ca1b2c927de47a5236`
- **sha256 after restore:** `b11cd9956f1ce9c0a63d0639e36f94755c0cd52202cdd0045c0c516a80f2d334` (equals "before")

**neutralization** (one line, targeted):
```diff
-        if nit.get(review_findings_schema.CONSEQUENCE_KIND_KEY) == review_findings_schema.CODE_QUALITY:
+        if True:  # NEUTRALIZED G8: nit.get(review_findings_schema.CONSEQUENCE_KIND_KEY) == review_findings_schema.CODE_QUALITY
```

**raw red** (`G8` neutralized):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_________ test_t8_nit_cap_collapses_only_code_quality_nits_into_craft __________

sources_calls = []

    def test_t8_nit_cap_collapses_only_code_quality_nits_into_craft(sources_calls):
        findings = ([_finding("Quality %d" % i, i, "Nit", "code-quality") for i in range(1, 7)]
                    + [_finding("Real one", 7, "Nit", "real"), _finding("Real two", 8, "Nit", "real")])
        compiled, drops = RD.mechanical_compile(findings, None)
        titles = [f["title"] for f in compiled if not f.get("summaryEntry")]
>       assert "Real one" in titles and "Real two" in titles
E       AssertionError: assert ('Real one' in ['Quality 1', 'Quality 2', 'Quality 3', 'Quality 4', 'Quality 5'])

/home/user/c7-wt/plugins/superheroes/lib/tests/test_outcome_settle_c7.py:403: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_outcome_settle_c7.py::test_t8_nit_cap_collapses_only_code_quality_nits_into_craft
1 failed in 3.24s
```

**restore:** the inverse edit of the line above (the `NEUTRALIZED` text replaced by the original).

**restore receipt** (restored lines quoted back by `grep -n`):
```
889:        if nit.get(review_findings_schema.CONSEQUENCE_KIND_KEY) == review_findings_schema.CODE_QUALITY:
890-            quality_seen += 1
```

**raw green** (after restore):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 0.27s
```

---

## G9 — the merge drop rows in `mechanical_compile`

- **axis:** a same-place-and-title merge is recorded as a drop row, not lost silently
- **file:** `plugins/superheroes/lib/round_driver.py`
- **detector:** `plugins/superheroes/lib/tests/test_outcome_settle_c7.py::test_t9_same_place_duplicates_merge_and_record_the_merge` (T9)
- **sha256 before:** `b11cd9956f1ce9c0a63d0639e36f94755c0cd52202cdd0045c0c516a80f2d334`
- **sha256 neutralized:** `269a1d2da7d2d31b4c16dd57c84358ff8687f508480f1fc6fc0575beea56074b`
- **sha256 after restore:** `b11cd9956f1ce9c0a63d0639e36f94755c0cd52202cdd0045c0c516a80f2d334` (equals "before")

**neutralization** (one line, targeted):
```diff
-    drops.extend(_merge_drops(kept))
+    pass  # NEUTRALIZED G9: drops.extend(_merge_drops(kept))
```

**raw red** (`G9` neutralized):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
___________ test_t9_same_place_duplicates_merge_and_record_the_merge ___________

    def test_t9_same_place_duplicates_merge_and_record_the_merge():
        first = _finding("Off by one", 1, "Important", "real")
        second = dict(first, severity="Minor")
        compiled, drops = RD.mechanical_compile([first, second], None)
        assert len(compiled) == 1
>       assert [d for d in drops if d["reason"] == "merged with a finding at the same place and title"] == [
            {"file": "f.py", "line": 1, "title": "Off by one",
             "reason": "merged with a finding at the same place and title"}]
E       AssertionError: assert [] == [{'file': 'f....e and title'}]
E         
E         Right contains one more item: {'file': 'f.py', 'line': 1, 'title': 'Off by one', 'reason': 'merged with a finding at the same place and title'}
E         Use -v to get more diff

/home/user/c7-wt/plugins/superheroes/lib/tests/test_outcome_settle_c7.py:436: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_outcome_settle_c7.py::test_t9_same_place_duplicates_merge_and_record_the_merge
1 failed in 0.30s
```

**restore:** the inverse edit of the line above (the `NEUTRALIZED` text replaced by the original).

**restore receipt** (restored lines quoted back by `grep -n`):
```
1017-    compiled = _compile_by_anchor(kept)
1018:    drops.extend(_merge_drops(kept))
```

**raw green** (after restore):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 0.24s
```

---

## G10 — the `decidedBy` shape check in `_validate_ruling_entries`

- **axis:** a malformed `decidedBy` is refused with `ruling-decided-by-malformed`
- **file:** `plugins/superheroes/lib/round_driver.py`
- **detector:** `plugins/superheroes/lib/tests/test_outcome_settle_c7.py::test_t10_a_malformed_decided_by_is_refused_and_state_is_unchanged` (T10)
- **sha256 before:** `b11cd9956f1ce9c0a63d0639e36f94755c0cd52202cdd0045c0c516a80f2d334`
- **sha256 neutralized:** `34011a3e72c739fce70c37370561709ac836f9bec53ca7d3e4655f251825a487`
- **sha256 after restore:** `b11cd9956f1ce9c0a63d0639e36f94755c0cd52202cdd0045c0c516a80f2d334` (equals "before")

**neutralization** (one line, targeted):
```diff
-            if not _decided_by_well_formed(spec["decidedBy"]):
+            if False:  # NEUTRALIZED G10: not _decided_by_well_formed(spec["decidedBy"])
```

**raw red** — the whole parametrized function (16 params) was run; all 16 failed. The full capture is 33,479 bytes, over the 32 KiB ceiling, so it was written to `/tmp/wo4b_g10_red.txt` (outside the repository; scratch, so quoted here before removal). First 30 lines, then the decisive tail:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
FFFFFFFFFFFFFFFF                                                         [100%]
=================================== FAILURES ===================================
___ test_t10_a_malformed_decided_by_is_refused_and_state_is_unchanged[None] ____

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-41/test_t10_a_malformed_decided_b0')
decided_by = None

    @pytest.mark.parametrize("decided_by", [
        None, "canon", ["canon", "x"], {}, {"kind": "canon"}, {"kind": "canon", "ref": "  "},
        {"kind": "canon", "ref": 5}, {"kind": "residual", "ref": ""}, {"kind": "other", "ref": "x"},
        {"kind": "canon", "ref": "x", "extra": 1}, {"kind": "sheet-answer", "ref": "card-1"},
        {"kind": "sheet-answer", "ref": {"pr": "7", "card": "c1"}},
        {"kind": "sheet-answer", "ref": {"pr": True, "card": "c1"}},
        {"kind": "sheet-answer", "ref": {"pr": 7, "card": " "}},
        {"kind": "sheet-answer", "ref": {"pr": 7}},
        {"kind": "sheet-answer", "ref": {"pr": 7, "card": "c1", "x": 1}},
    ])
    def test_t10_a_malformed_decided_by_is_refused_and_state_is_unchanged(tmp_path, decided_by):
        session_dir, (key,) = _rule_session(tmp_path, [_finding("Canon call", 1, "Important", "real")])
        before = _state_bytes(session_dir)
        path = _write_rulings(tmp_path / "rulings.json", [_ruling(key, decided_by)])
        out = RD.cmd_rule(session_dir, path, "owner")
>       assert out.get("ok") is False and out.get("reason") == "ruling-decided-by-malformed", out
E       AssertionError: {'ok': True, 'recorded': 1, 'rulingFileSha256': '933bf69c698c15e50c28ffde49dc213eb9336720a81f37edfce6a060a074c4ca'}
E       assert (True is False)
E        +  where True = <built-in method get of dict object at 0x7f3a0a4b1f80>('ok')
E        +    where <built-in method get of dict object at 0x7f3a0a4b1f80> = {'ok': True, 'recorded': 1, 'rulingFileSha256': '933bf69c698c15e50c28ffde49dc213eb9336720a81f37edfce6a060a074c4ca'}.get

/home/user/c7-wt/plugins/superheroes/lib/tests/test_outcome_settle_c7.py:459: AssertionError
...
FAILED plugins/superheroes/lib/tests/test_outcome_settle_c7.py::test_t10_a_malformed_decided_by_is_refused_and_state_is_unchanged[None]
FAILED plugins/superheroes/lib/tests/test_outcome_settle_c7.py::test_t10_a_malformed_decided_by_is_refused_and_state_is_unchanged[canon]
FAILED plugins/superheroes/lib/tests/test_outcome_settle_c7.py::test_t10_a_malformed_decided_by_is_refused_and_state_is_unchanged[decided_by2]
FAILED plugins/superheroes/lib/tests/test_outcome_settle_c7.py::test_t10_a_malformed_decided_by_is_refused_and_state_is_unchanged[decided_by3]
FAILED plugins/superheroes/lib/tests/test_outcome_settle_c7.py::test_t10_a_malformed_decided_by_is_refused_and_state_is_unchanged[decided_by4]
FAILED plugins/superheroes/lib/tests/test_outcome_settle_c7.py::test_t10_a_malformed_decided_by_is_refused_and_state_is_unchanged[decided_by5]
FAILED plugins/superheroes/lib/tests/test_outcome_settle_c7.py::test_t10_a_malformed_decided_by_is_refused_and_state_is_unchanged[decided_by6]
FAILED plugins/superheroes/lib/tests/test_outcome_settle_c7.py::test_t10_a_malformed_decided_by_is_refused_and_state_is_unchanged[decided_by7]
FAILED plugins/superheroes/lib/tests/test_outcome_settle_c7.py::test_t10_a_malformed_decided_by_is_refused_and_state_is_unchanged[decided_by8]
FAILED plugins/superheroes/lib/tests/test_outcome_settle_c7.py::test_t10_a_malformed_decided_by_is_refused_and_state_is_unchanged[decided_by9]
FAILED plugins/superheroes/lib/tests/test_outcome_settle_c7.py::test_t10_a_malformed_decided_by_is_refused_and_state_is_unchanged[decided_by10]
FAILED plugins/superheroes/lib/tests/test_outcome_settle_c7.py::test_t10_a_malformed_decided_by_is_refused_and_state_is_unchanged[decided_by11]
FAILED plugins/superheroes/lib/tests/test_outcome_settle_c7.py::test_t10_a_malformed_decided_by_is_refused_and_state_is_unchanged[decided_by12]
FAILED plugins/superheroes/lib/tests/test_outcome_settle_c7.py::test_t10_a_malformed_decided_by_is_refused_and_state_is_unchanged[decided_by13]
FAILED plugins/superheroes/lib/tests/test_outcome_settle_c7.py::test_t10_a_malformed_decided_by_is_refused_and_state_is_unchanged[decided_by14]
FAILED plugins/superheroes/lib/tests/test_outcome_settle_c7.py::test_t10_a_malformed_decided_by_is_refused_and_state_is_unchanged[decided_by15]
16 failed in 0.76s
```

**restore:** the inverse edit of the line above (the `NEUTRALIZED` text replaced by the original).

**restore receipt** (restored lines quoted back by `grep -n`):
```
6824-        if "decidedBy" in spec:
6825:            if not _decided_by_well_formed(spec["decidedBy"]):
```

**raw green** (after restore):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
................                                                         [100%]
16 passed in 0.38s
```

---

## G11 — the `severityChange` stamp in `apply_verdicts`

- **axis:** a verdict that lowers a finding's severity leaves a `severityChange` row; a raise or no change leaves none
- **file:** `plugins/superheroes/lib/verification.py`
- **detector:** `plugins/superheroes/lib/tests/test_outcome_settle_c7.py::test_t6_severity_change_defaults_its_reason_and_ignores_a_raise` (T6)
- **sha256 before:** `ef76c1668215a0cc230594a4ce3a153a43baf8c5c8b9e8402a8cd09ddf13f423`
- **sha256 neutralized:** `39726d5efdc2270bb2c44d6a33fd6a3578fafd0e56343e5453cd2cc4880cb790`
- **sha256 after restore:** `ef76c1668215a0cc230594a4ce3a153a43baf8c5c8b9e8402a8cd09ddf13f423` (equals "before")

**neutralization** (one line, targeted):
```diff
-        if circuit_breaker.severity_rank(kept["severity"]) > circuit_breaker.severity_rank(f.get("severity")):
+        if False:  # NEUTRALIZED G11: circuit_breaker.severity_rank(kept["severity"]) > circuit_breaker.severity_rank(f.get("severity"))
```

**raw red** (`G11` neutralized):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_______ test_t6_severity_change_defaults_its_reason_and_ignores_a_raise ________

    def test_t6_severity_change_defaults_its_reason_and_ignores_a_raise():
        findings = [{"id": "a", "severity": "Important", "title": "a", "file": "f.py", "line": 1},
                    {"id": "b", "severity": "Minor", "title": "b", "file": "f.py", "line": 2},
                    {"id": "c", "severity": "Important", "title": "c", "file": "f.py", "line": 3}]
        verdicts = [{"id": "a", "verdict": "PLAUSIBLE", "severity": "Nit"},
                    {"id": "b", "verdict": "PLAUSIBLE", "severity": "Critical", "reason": "worse"},
                    {"id": "c", "verdict": "PLAUSIBLE", "severity": "Important", "reason": "same"}]
        kept = {f["id"]: f for f in verification.apply_verdicts(findings, verdicts)["findings"]}
>       assert kept["a"]["severityChange"] == {"from": "Important", "to": "Nit", "reason": "no reason given"}
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       KeyError: 'severityChange'

/home/user/c7-wt/plugins/superheroes/lib/tests/test_outcome_settle_c7.py:366: KeyError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_outcome_settle_c7.py::test_t6_severity_change_defaults_its_reason_and_ignores_a_raise
1 failed in 0.29s
```

**restore:** the inverse edit of the line above (the `NEUTRALIZED` text replaced by the original).

**restore receipt** (restored lines quoted back by `grep -n`):
```
159:        if circuit_breaker.severity_rank(kept["severity"]) > circuit_breaker.severity_rank(f.get("severity")):
160-            kept["severityChange"] = {
```

**raw green** (after restore):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 0.37s
```

---

## G12 — one converted terminal site, `_park_capped`

- **axis:** no function other than `_set_terminal` writes `state["terminal"]`
- **file:** `plugins/superheroes/lib/round_driver.py`
- **detector:** `plugins/superheroes/lib/tests/test_outcome_settle_c7.py::test_t7_one_writer_of_the_terminal_and_it_is_set_terminal` (T7)
- **sha256 before:** `b11cd9956f1ce9c0a63d0639e36f94755c0cd52202cdd0045c0c516a80f2d334`
- **sha256 neutralized:** `d536c2cd358af6d0497adb51b476dd3178968a1a8d5dde2a5996af7fd057c8ab`
- **sha256 after restore:** `b11cd9956f1ce9c0a63d0639e36f94755c0cd52202cdd0045c0c516a80f2d334` (equals "before")

**neutralization** (one line, targeted):
```diff
-    _set_terminal(state, "capped-with-open-critical", cap=True)
+    state["terminal"] = "capped-with-open-critical"  # NEUTRALIZED G12: _set_terminal(state, "capped-with-open-critical", cap=True)
```

**raw red** (`G12` neutralized):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
__________ test_t7_one_writer_of_the_terminal_and_it_is_set_terminal ___________

    def test_t7_one_writer_of_the_terminal_and_it_is_set_terminal():
        path = os.path.join(_LIB, "round_driver.py")
        with open(path, encoding="utf-8") as fh:
            source = fh.read()
        tree = ast.parse(source)
        writers = []
        for func in ast.walk(tree):
            if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for node in ast.walk(func):
                targets = node.targets if isinstance(node, ast.Assign) else (
                    [node.target] if isinstance(node, (ast.AugAssign, ast.AnnAssign)) else [])
                for t in targets:
                    if (isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name)
                            and t.value.id == "state" and isinstance(t.slice, ast.Constant)
                            and t.slice.value == "terminal"):
                        writers.append((func.name, node.lineno))
>       assert {name for name, _ in writers} == {"_set_terminal"}, writers
E       AssertionError: [('_set_terminal', 1808), ('_park_capped', 5161)]
E       assert {'_park_cappe...set_terminal'} == {'_set_terminal'}
E         
E         Extra items in the left set:
E         '_park_capped'
E         Use -v to get more diff

/home/user/c7-wt/plugins/superheroes/lib/tests/test_outcome_settle_c7.py:390: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_outcome_settle_c7.py::test_t7_one_writer_of_the_terminal_and_it_is_set_terminal
1 failed in 0.53s
```

**restore:** the inverse edit of the line above (the `NEUTRALIZED` text replaced by the original).

**restore receipt** (restored lines quoted back by `grep -n`):
```
5160:def _park_capped(state, detail):
5161-    _set_terminal(state, "capped-with-open-critical", cap=True)
```

**raw green** (after restore):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 0.54s
```

