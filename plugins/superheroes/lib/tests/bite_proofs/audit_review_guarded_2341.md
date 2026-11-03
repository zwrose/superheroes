# Bite-proof record — a prose-only fix clears its audit on a `review-guarded` answer (#2341)

Detector file: `plugins/superheroes/lib/tests/test_audit_review_guarded_2341.py`, unedited between each red and its green. Every entry is a targeted, reversible Edit-tool edit to one production file (`plugins/superheroes/lib/audits.py`), restored by the inverse edit (no `git checkout`, `restore`, `reset` or `stash`). Runs: `scripts/pinned-python -B -X pycache_prefix=/tmp/claude-0/pyc -m pytest '<exact node id>' -q -n 0`, one test node each (G4, G5 and G6 name the test function, so its parametrized cases run together), output captured whole, followed by the `exit=` line the command printed. The `UV_NATIVE_TLS` deprecation warning that `uv` prints first is the only line left out of each capture. The thirteen guarded elements are the ones the orders declared (G1-G7, then G8 and G9 from the #2345 fix order, then G10 and G11 from the vet 806 fix order, then G12 and G13 from the #2341 seam fix, whose neutralizations are in `round_driver.py`); none is grouped. Each `old_string` occurred exactly once (the Edit tool refuses a non-unique match). No secrets, tokens, private URLs or PII appear in any capture; nothing was redacted.

The detectors are the tests that carry a `# bite-proof:` line.

## G1. The clear arm for a prose-only `review-guarded` result (`audits.apply_audit_results`)

- **Axis:** a clearing ruling whose `testWouldFail` answers `review-guarded` stands when the target's driver-built `fixerDelta` is prose only.
- **Detector:** `test_audit_review_guarded_2341.py::test_t1_a_prose_only_delta_clears_on_a_review_guarded_answer`.
- **Neutralization:** `prose, others = prose_only_delta(f)` became `prose, others = False, []`, so the arm refuses unconditionally.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_________ test_t1_a_prose_only_delta_clears_on_a_review_guarded_answer _________

    def test_t1_a_prose_only_delta_clears_on_a_review_guarded_answer():
        # axis: G1 — the clear arm for a prose-only `review-guarded` result
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/audit_review_guarded_2341.md
        outcome = _fold([_guarded()], _target(RUBRIC_MD, ROOT_MD))
        entry = _only(outcome)
>       assert outcome["discharged"] == ["t0"] and outcome["notDischarged"] == []
E       AssertionError: assert ([] == ['t0']
E         
E         Right contains one more item: 't0'
E         Use -v to get more diff)

/home/user/wt-2341/plugins/superheroes/lib/tests/test_audit_review_guarded_2341.py:96: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_audit_review_guarded_2341.py::test_t1_a_prose_only_delta_clears_on_a_review_guarded_answer
1 failed in 0.24s
exit=1
```

- **Restore:** inverse edit (`prose, others = False, []` back to `prose, others = prose_only_delta(f)`).
- **Restore receipt** (read back by the Grep tool, `prose, others = `):

```
715:            prose, others = prose_only_delta(f)
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 0.21s
exit=0
```

## G2. The `.md` extension test (`audits._is_prose_path`)

- **Axis:** only a Markdown file is prose; any other extension makes the delta not prose-only.
- **Detector:** `test_audit_review_guarded_2341.py::test_t2_a_delta_that_touches_code_is_refused_naming_the_file`.
- **Neutralization:** `if not normalized.lower().endswith(".md"):` became `if False:`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_________ test_t2_a_delta_that_touches_code_is_refused_naming_the_file _________

    def test_t2_a_delta_that_touches_code_is_refused_naming_the_file():
        # axis: G2 — the `.md` extension test
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/audit_review_guarded_2341.md
>       reason = _refused(_fold([_guarded()], _target(RUBRIC_MD, LIB_PY)))
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

/home/user/wt-2341/plugins/superheroes/lib/tests/test_audit_review_guarded_2341.py:130: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

outcome = {'audits': [{'id': 't0', 'identity': 'f.py::t', 'file': 'f.py', 'line': 1, ...}], 'discharged': ['t0'], 'notDischarged': [], 'newIssues': [], ...}

    def _refused(outcome):
        entry = _only(outcome)
>       assert outcome["discharged"] == [] and outcome["notDischarged"] == ["t0"]
E       AssertionError: assert (['t0'] == []
E         
E         Left contains one more item: 't0'
E         Use -v to get more diff)

/home/user/wt-2341/plugins/superheroes/lib/tests/test_audit_review_guarded_2341.py:80: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_audit_review_guarded_2341.py::test_t2_a_delta_that_touches_code_is_refused_naming_the_file
1 failed in 0.23s
exit=1
```

- **Restore:** inverse edit (`if False:` back to `if not normalized.lower().endswith(".md"):`, keyed on the `return False` and comment lines after it).
- **Restore receipt** (Grep, `endswith\("\.md"\)`):

```
115:    if not normalized.lower().endswith(".md"):
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 0.22s
exit=0
```

## G3. The test-tree test (`audits._is_prose_path`, `size_count.is_test_path`)

- **Axis:** a Markdown file under a test tree is test material, not doctrine.
- **Detector:** `test_audit_review_guarded_2341.py::test_t3_a_markdown_file_under_a_test_tree_is_not_prose`.
- **Neutralization:** `if _is_test_path(normalized):` became `if False:`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
____________ test_t3_a_markdown_file_under_a_test_tree_is_not_prose ____________

    def test_t3_a_markdown_file_under_a_test_tree_is_not_prose():
        # axis: G3 — the test-tree test
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/audit_review_guarded_2341.md
>       reason = _refused(_fold([_guarded()], _target(TEST_TREE_MD)))
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

/home/user/wt-2341/plugins/superheroes/lib/tests/test_audit_review_guarded_2341.py:146: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

outcome = {'audits': [{'id': 't0', 'identity': 'f.py::t', 'file': 'f.py', 'line': 1, ...}], 'discharged': ['t0'], 'notDischarged': [], 'newIssues': [], ...}

    def _refused(outcome):
        entry = _only(outcome)
>       assert outcome["discharged"] == [] and outcome["notDischarged"] == ["t0"]
E       AssertionError: assert (['t0'] == []
E         
E         Left contains one more item: 't0'
E         Use -v to get more diff)

/home/user/wt-2341/plugins/superheroes/lib/tests/test_audit_review_guarded_2341.py:80: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_audit_review_guarded_2341.py::test_t3_a_markdown_file_under_a_test_tree_is_not_prose
1 failed in 0.21s
exit=1
```

- **Restore:** inverse edit (`if False:` back to `if _is_test_path(normalized):`; `if False:` occurred once at that moment, after G2's restore).
- **Restore receipt** (Grep, `_is_test_path\(normalized\)|if False:`; the one match, no `if False:` left):

```
118:    if _is_test_path(normalized):
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 0.21s
exit=0
```

## G4. The non-prose component set (`audits.NON_PROSE_DIR_NAMES`)

- **Axis:** a Markdown file under an eval, grader, fixture or golden tree is a scored or pinned artifact, not doctrine.
- **Detector:** `test_audit_review_guarded_2341.py::test_t4_a_markdown_file_under_a_non_prose_tree_is_not_prose` (both parametrized cases: an eval grader, and a fixtures file outside any test tree).
- **Neutralization:** the whole `frozenset({"eval", "evals", "graders", "fixtures", "fixture", "golden", "goldens", "snapshots", "__snapshots__", "testdata"})` became `frozenset()`.

**Raw red** (exit 1):

```
FF                                                                       [100%]
=================================== FAILURES ===================================
___ test_t4_a_markdown_file_under_a_non_prose_tree_is_not_prose[eval-grader] ___

path = 'plugins/superheroes/evals/s9-some-scenario/graders/some-grader.md'

    @pytest.mark.parametrize("path", [GRADER_MD, FIXTURE_MD], ids=["eval-grader", "fixtures"])
    def test_t4_a_markdown_file_under_a_non_prose_tree_is_not_prose(path):
        # axis: G4 — the non-prose component set
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/audit_review_guarded_2341.md
        assert path.endswith(".md") and not audits._is_test_path(path)
>       reason = _refused(_fold([_guarded()], _target(path)))
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

/home/user/wt-2341/plugins/superheroes/lib/tests/test_audit_review_guarded_2341.py:157: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

outcome = {'audits': [{'id': 't0', 'identity': 'f.py::t', 'file': 'f.py', 'line': 1, ...}], 'discharged': ['t0'], 'notDischarged': [], 'newIssues': [], ...}

    def _refused(outcome):
        entry = _only(outcome)
>       assert outcome["discharged"] == [] and outcome["notDischarged"] == ["t0"]
E       AssertionError: assert (['t0'] == []
E         
E         Left contains one more item: 't0'
E         Use -v to get more diff)

/home/user/wt-2341/plugins/superheroes/lib/tests/test_audit_review_guarded_2341.py:80: AssertionError
____ test_t4_a_markdown_file_under_a_non_prose_tree_is_not_prose[fixtures] _____

path = 'plugins/superheroes/lib/fixtures/orders/some-fixture-2341.md'

    @pytest.mark.parametrize("path", [GRADER_MD, FIXTURE_MD], ids=["eval-grader", "fixtures"])
    def test_t4_a_markdown_file_under_a_non_prose_tree_is_not_prose(path):
        # axis: G4 — the non-prose component set
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/audit_review_guarded_2341.md
        assert path.endswith(".md") and not audits._is_test_path(path)
>       reason = _refused(_fold([_guarded()], _target(path)))
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

/home/user/wt-2341/plugins/superheroes/lib/tests/test_audit_review_guarded_2341.py:157: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

outcome = {'audits': [{'id': 't0', 'identity': 'f.py::t', 'file': 'f.py', 'line': 1, ...}], 'discharged': ['t0'], 'notDischarged': [], 'newIssues': [], ...}

    def _refused(outcome):
        entry = _only(outcome)
>       assert outcome["discharged"] == [] and outcome["notDischarged"] == ["t0"]
E       AssertionError: assert (['t0'] == []
E         
E         Left contains one more item: 't0'
E         Use -v to get more diff)

/home/user/wt-2341/plugins/superheroes/lib/tests/test_audit_review_guarded_2341.py:80: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_audit_review_guarded_2341.py::test_t4_a_markdown_file_under_a_non_prose_tree_is_not_prose[eval-grader]
FAILED plugins/superheroes/lib/tests/test_audit_review_guarded_2341.py::test_t4_a_markdown_file_under_a_non_prose_tree_is_not_prose[fixtures]
2 failed in 0.23s
exit=1
```

- **Restore:** inverse edit (`frozenset()` back to the ten-name set).
- **Restore receipt** (Grep, `NON_PROSE_DIR_NAMES = ` with three lines after):

```
83:NON_PROSE_DIR_NAMES = frozenset({
84-    "eval", "evals", "graders", "fixtures", "fixture", "golden", "goldens", "snapshots",
85-    "__snapshots__", "testdata",
86-})
```

**Raw green** (exit 0):

```
..                                                                       [100%]
2 passed in 0.22s
exit=0
```

## G5. The per-check answer set (`audits.check_answers`)

- **Axis:** only `testWouldFail` accepts `review-guarded`; `right` and `brokeNothing` answer `yes` or `no`.
- **Detector:** `test_audit_review_guarded_2341.py::test_t6_review_guarded_is_a_fault_on_any_check_but_test_would_fail` (cases `right` and `brokeNothing`).
- **Neutralization:** `if name == "testWouldFail":` became `if True:`, so every check gets the widened set.

**Raw red** (exit 1):

```
FF                                                                       [100%]
=================================== FAILURES ===================================
__ test_t6_review_guarded_is_a_fault_on_any_check_but_test_would_fail[right] ___

name = 'right'

    @pytest.mark.parametrize("name", ["right", "brokeNothing"])
    def test_t6_review_guarded_is_a_fault_on_any_check_but_test_would_fail(name):
        # axis: G5 — the per-check answer set
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/audit_review_guarded_2341.md
        result = _guarded(checks=_checks(**{name: audits.REVIEW_GUARDED}))
        fault = audits.audit_checks_fault(result)
>       assert fault is not None and "checks.%s" % name in fault and "review-guarded" in fault, fault
E       AssertionError: None
E       assert (None is not None)

/home/user/wt-2341/plugins/superheroes/lib/tests/test_audit_review_guarded_2341.py:202: AssertionError
_ test_t6_review_guarded_is_a_fault_on_any_check_but_test_would_fail[brokeNothing] _

name = 'brokeNothing'

    @pytest.mark.parametrize("name", ["right", "brokeNothing"])
    def test_t6_review_guarded_is_a_fault_on_any_check_but_test_would_fail(name):
        # axis: G5 — the per-check answer set
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/audit_review_guarded_2341.md
        result = _guarded(checks=_checks(**{name: audits.REVIEW_GUARDED}))
        fault = audits.audit_checks_fault(result)
>       assert fault is not None and "checks.%s" % name in fault and "review-guarded" in fault, fault
E       AssertionError: None
E       assert (None is not None)

/home/user/wt-2341/plugins/superheroes/lib/tests/test_audit_review_guarded_2341.py:202: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_audit_review_guarded_2341.py::test_t6_review_guarded_is_a_fault_on_any_check_but_test_would_fail[right]
FAILED plugins/superheroes/lib/tests/test_audit_review_guarded_2341.py::test_t6_review_guarded_is_a_fault_on_any_check_but_test_would_fail[brokeNothing]
2 failed in 0.21s
exit=1
```

- **Restore:** inverse edit (`if True:` back to `if name == "testWouldFail":`).
- **Restore receipt** (Grep, `if name == "testWouldFail"|if True:`; the one match, no `if True:` left):

```
76:    if name == "testWouldFail":
```

**Raw green** (exit 0):

```
..                                                                       [100%]
2 passed in 0.20s
exit=0
```

## G6. The empty or absent delta refusal (`audits.prose_only_delta`)

- **Axis:** a delta naming no file (absent, empty, or with no header line) is never prose-only.
- **Detector:** `test_audit_review_guarded_2341.py::test_t5_an_absent_or_empty_delta_is_refused_as_no_recorded_delta` (cases no key, empty list, no header lines).
- **Neutralization:** `if not files:` became `if files is None:`, so an empty file list reads prose-only (an absent delta still refuses, as `_delta_files` returns None for it).

**Raw red** (exit 1):

```
.FF                                                                      [100%]
=================================== FAILURES ===================================
_ test_t5_an_absent_or_empty_delta_is_refused_as_no_recorded_delta[empty-list] _

target = {'id': 't0', 'title': 'T', 'file': 'f.py', 'line': 1, ...}

    @pytest.mark.parametrize("target", [
        pytest.param(_target(), id="no-fixerDelta-key"),
        pytest.param(_target(fixerDelta=[]), id="empty-list"),
        pytest.param(_target(fixerDelta=["+ a line with no header"]), id="no-header-lines"),
    ])
    def test_t5_an_absent_or_empty_delta_is_refused_as_no_recorded_delta(target):
        # axis: G6 — the empty/absent delta refusal
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/audit_review_guarded_2341.md
>       reason = _refused(_fold([_guarded()], target))
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

/home/user/wt-2341/plugins/superheroes/lib/tests/test_audit_review_guarded_2341.py:176: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

outcome = {'audits': [{'id': 't0', 'identity': 'f.py::t', 'file': 'f.py', 'line': 1, ...}], 'discharged': ['t0'], 'notDischarged': [], 'newIssues': [], ...}

    def _refused(outcome):
        entry = _only(outcome)
>       assert outcome["discharged"] == [] and outcome["notDischarged"] == ["t0"]
E       AssertionError: assert (['t0'] == []
E         
E         Left contains one more item: 't0'
E         Use -v to get more diff)

/home/user/wt-2341/plugins/superheroes/lib/tests/test_audit_review_guarded_2341.py:80: AssertionError
_ test_t5_an_absent_or_empty_delta_is_refused_as_no_recorded_delta[no-header-lines] _

target = {'id': 't0', 'identity': 'f.py::t', 'file': 'f.py', 'line': 1, ...}

    @pytest.mark.parametrize("target", [
        pytest.param(_target(), id="no-fixerDelta-key"),
        pytest.param(_target(fixerDelta=[]), id="empty-list"),
        pytest.param(_target(fixerDelta=["+ a line with no header"]), id="no-header-lines"),
    ])
    def test_t5_an_absent_or_empty_delta_is_refused_as_no_recorded_delta(target):
        # axis: G6 — the empty/absent delta refusal
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/audit_review_guarded_2341.md
>       reason = _refused(_fold([_guarded()], target))
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

/home/user/wt-2341/plugins/superheroes/lib/tests/test_audit_review_guarded_2341.py:176: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

outcome = {'audits': [{'id': 't0', 'identity': 'f.py::t', 'file': 'f.py', 'line': 1, ...}], 'discharged': ['t0'], 'notDischarged': [], 'newIssues': [], ...}

    def _refused(outcome):
        entry = _only(outcome)
>       assert outcome["discharged"] == [] and outcome["notDischarged"] == ["t0"]
E       AssertionError: assert (['t0'] == []
E         
E         Left contains one more item: 't0'
E         Use -v to get more diff)

/home/user/wt-2341/plugins/superheroes/lib/tests/test_audit_review_guarded_2341.py:80: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_audit_review_guarded_2341.py::test_t5_an_absent_or_empty_delta_is_refused_as_no_recorded_delta[empty-list]
FAILED plugins/superheroes/lib/tests/test_audit_review_guarded_2341.py::test_t5_an_absent_or_empty_delta_is_refused_as_no_recorded_delta[no-header-lines]
2 failed, 1 passed in 0.24s
exit=1
```

- **Restore:** inverse edit (`if files is None:` back to `if not files:`).
- **Restore receipt** (Grep, `if not files:|if files is None:`; the one match, no `if files is None:` left):

```
132:    if not files:
```

**Raw green** (exit 0):

```
...                                                                      [100%]
3 passed in 0.22s
exit=0
```

## G7. The `reviewGuarded` listing only on a final clear (`audits.apply_audit_results`)

- **Axis:** an id is listed in `reviewGuarded` only once its entry ends `discharged` or `discharged-but-new-issue`; a later refusal in the same pass (unnamed change, malformed field) never leaves it listed.
- **Detector:** `test_audit_review_guarded_2341.py::test_t10_an_id_refused_later_in_the_same_pass_is_not_listed_as_review_guarded`.
- **Neutralization:** two lines added right after the `guarded = {...}` assignment at the gate: `if fid is not None:` / `review_guarded.append(fid)`, so the id is listed before the later refusals run.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_t10_an_id_refused_later_in_the_same_pass_is_not_listed_as_review_guarded _

    def test_t10_an_id_refused_later_in_the_same_pass_is_not_listed_as_review_guarded():
        # axis: G7 — the `reviewGuarded` listing only on a final clear
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/audit_review_guarded_2341.md
        outcome = _fold([_guarded(unnamedChange="also reworks the retry policy")], _target(RUBRIC_MD))
        entry = _only(outcome)
        assert outcome["unnamedChange"] == ["t0"] and outcome["notDischarged"] == ["t0"]
>       assert outcome["discharged"] == [] and outcome["reviewGuarded"] == []
E       AssertionError: assert ([] == []
E         
E         Use -v to get more diff and ['t0'] == []
E         
E         Left contains one more item: 't0'
E         Use -v to get more diff)

/home/user/wt-2341/plugins/superheroes/lib/tests/test_audit_review_guarded_2341.py:262: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_audit_review_guarded_2341.py::test_t10_an_id_refused_later_in_the_same_pass_is_not_listed_as_review_guarded
1 failed in 0.22s
exit=1
```

- **Restore:** inverse edit (the two added lines removed).
- **Restore receipt** (Grep, `review_guarded\.append|guarded = \{`; only the two final-clear appends and the assignment remain):

```
730:            guarded = {"answer": REVIEW_GUARDED, "why": r["checks"]["testWouldFail"]["why"].strip()}
795:                        review_guarded.append(fid)
829:                        review_guarded.append(fid)
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 0.22s
exit=0
```

## G8. The space-preserving header read (`audits._delta_files`)

- **Axis:** a `diff --git a/<f> b/<f>` header whose Markdown path `<f>` contains a space is read as the one file `<f>`, so a prose-only fix to such a file still clears (code-001 on PR #2345).
- **Detector:** `test_audit_review_guarded_2341.py::test_t11_a_header_for_a_markdown_path_with_a_space_is_read_and_clears`.
- **Neutralization:** the length-based read in `_delta_files` (`rest = line[len(_DIFF_HEADER):]` through `files.append(path)`) was put back to the base split-on-space form: `parts = line[len(_DIFF_HEADER):].split(" ")` with its two-token check, the `a/`/`b/` prefix check, the equal-and-non-empty check and `files.append(parts[0][2:])`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
____ test_t11_a_header_for_a_markdown_path_with_a_space_is_read_and_clears _____

    def test_t11_a_header_for_a_markdown_path_with_a_space_is_read_and_clears():
        # axis: G8 — the space-preserving header read
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/audit_review_guarded_2341.md
        target = _target(SPACED_MD)
        assert target["fixerDelta"][0] == "diff --git a/%s b/%s" % (SPACED_MD, SPACED_MD)
        outcome = _fold([_guarded()], target)
        entry = _only(outcome)
>       assert outcome["discharged"] == ["t0"] and outcome["notDischarged"] == []
E       AssertionError: assert ([] == ['t0']
E         
E         Right contains one more item: 't0'
E         Use -v to get more diff)

/home/user/wt-2341/plugins/superheroes/lib/tests/test_audit_review_guarded_2341.py:287: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_audit_review_guarded_2341.py::test_t11_a_header_for_a_markdown_path_with_a_space_is_read_and_clears
1 failed in 0.58s
exit=1
```

- **Restore:** inverse edit (the split-on-space block replaced by the length-based read again).
- **Restore receipt** (Grep, `rest = |span|path = rest|rest != |split\(" "\)`; the length-based lines are back, no `split(" ")` left):

```
101:        rest = line[len(_DIFF_HEADER):]
104:        span = len(rest) - 5
105:        if span <= 0 or span % 2:
107:        path = rest[2:2 + span // 2]
108:        if rest != "a/" + path + " b/" + path:
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 0.90s
exit=0
```

## G9. The whole-string equality check (`audits._delta_files`)

- **Axis:** a header is read only when the whole text after `diff --git ` equals `"a/" + <f> + " b/" + <f>`; any other header makes the delta unreadable (fail closed).
- **Detector:** `test_audit_review_guarded_2341.py::test_t12_a_header_that_is_not_one_path_twice_refuses_as_no_readable_delta` (four cases).
- **Neutralization:** `if rest != "a/" + path + " b/" + path:` became `if False:`, so any header of the right length whose first half parses is accepted.
- **Cases that go red:** `different-paths-both-with-spaces`, `space-on-one-side-only`, `b-separator-missing`. **`empty-path` stays green** under this neutralization: `diff --git a/ b/` leaves five characters, so the earlier `span <= 0` test (E-4) refuses it before the comparison runs. That case is guarded by the `span <= 0` line, which this entry does not neutralize.

**Raw red** (exit 1; the three failure bodies differ only in the header, so the first is quoted whole and the other two are cut to their header and assertion lines, about 1.5 KiB elided):

```
FFF.                                                                     [100%]
=================================== FAILURES ===================================
_ test_t12_a_header_that_is_not_one_path_twice_refuses_as_no_readable_delta[different-paths-both-with-spaces] _

header = 'diff --git a/my doc.md b/my dox.md'

    @pytest.mark.parametrize("header", [
        pytest.param("diff --git a/my doc.md b/my dox.md", id="different-paths-both-with-spaces"),
        pytest.param("diff --git a/my doc.md b/my_doc.md", id="space-on-one-side-only"),
        pytest.param("diff --git a/my doc.md c/my doc.md", id="b-separator-missing"),
        pytest.param("diff --git a/ b/", id="empty-path"),
    ])
    def test_t12_a_header_that_is_not_one_path_twice_refuses_as_no_readable_delta(header):
        # axis: G9 — the whole-string equality check
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/audit_review_guarded_2341.md
        target = _target(fixerDelta=[header])
>       assert audits.prose_only_delta(target) == (False, [])
E       assert (True, []) == (False, [])
E         
E         At index 0 diff: True != False
E         Use -v to get more diff

/home/user/wt-2341/plugins/superheroes/lib/tests/test_audit_review_guarded_2341.py:304: AssertionError
_ ...[space-on-one-side-only] _   header = 'diff --git a/my doc.md b/my_doc.md'
>       assert audits.prose_only_delta(target) == (False, [])
E       assert (True, []) == (False, [])
_ ...[b-separator-missing] _   header = 'diff --git a/my doc.md c/my doc.md'
>       assert audits.prose_only_delta(target) == (False, [])
E       assert (True, []) == (False, [])
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_audit_review_guarded_2341.py::test_t12_a_header_that_is_not_one_path_twice_refuses_as_no_readable_delta[different-paths-both-with-spaces]
FAILED plugins/superheroes/lib/tests/test_audit_review_guarded_2341.py::test_t12_a_header_that_is_not_one_path_twice_refuses_as_no_readable_delta[space-on-one-side-only]
FAILED plugins/superheroes/lib/tests/test_audit_review_guarded_2341.py::test_t12_a_header_that_is_not_one_path_twice_refuses_as_no_readable_delta[b-separator-missing]
3 failed, 1 passed in 0.24s
exit=1
```

- **Restore:** inverse edit (`if False:` back to `if rest != "a/" + path + " b/" + path:`).
- **Restore receipt** (Grep, `if False:|rest != `; the one match, no `if False:` left):

```
108:        if rest != "a/" + path + " b/" + path:
```

**Raw green** (exit 0):

```
....                                                                     [100%]
4 passed in 0.23s
exit=0
```

## G10. Two-path (rename) section emission (`round_driver._attempt_fixer_delta`)

- **Axis:** a section whose header names two paths (what `git diff -M` writes for a rename) is emitted under its own `diff --git` header line, so `audits._delta_files` refuses the delta and a code rename beside a Markdown edit never clears on `review-guarded`.
- **Detector:** `test_audit_review_guarded_2341.py::test_t13_a_fix_that_renames_a_code_file_is_refused_though_it_also_edits_a_guide`. T14 (`test_t14_...`) is the positive control, not a guarded element.
- **Neutralization:** two lines inserted in `_attempt_fixer_delta` right before `if named and named.group(2) in leave_out:`: `if named:` / `            continue`, so a header that parses as `a/… b/…` but is not one path is skipped. Production file: `plugins/superheroes/lib/round_driver.py`. Run as above (`-q -n 0`, one node, `exit=` line appended), `UV_NATIVE_TLS` warning left out.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_t13_a_fix_that_renames_a_code_file_is_refused_though_it_also_edits_a_guide _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-27/test_t13_a_fix_that_renames_a_0')

    def test_t13_a_fix_that_renames_a_code_file_is_refused_though_it_also_edits_a_guide(tmp_path):
        # axis: G10 — a two-path (rename) section is emitted under its own header
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/audit_review_guarded_2341.md
        def fix(repo):
            _git(repo, "mv", MOD, RENAMED)
            _write(repo, RENAMED, MOD_BODY.replace("return 3", "return 33"))
            _reword_guide(repo)
    
        reviewed_diff, head_diff, delta = _built_delta(tmp_path, fix)
        assert "rename from %s" % MOD in head_diff and "rename to %s" % RENAMED in head_diff
        renamed = [h for h in _headers(delta) if RENAMED in h]
>       assert renamed == ["diff --git a/%s b/%s" % (MOD, RENAMED)]
E       AssertionError: assert [] == ['diff --git ...e_renamed.py']
E         
E         Right contains one more item: 'diff --git a/pkg/module.py b/pkg/module_renamed.py'
E         Use -v to get more diff

/home/user/wt-2341/plugins/superheroes/lib/tests/test_audit_review_guarded_2341.py:395: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_audit_review_guarded_2341.py::test_t13_a_fix_that_renames_a_code_file_is_refused_though_it_also_edits_a_guide
1 failed in 0.42s
exit=1
```

- **Restore:** inverse edit (the two inserted lines removed).
- **Restore receipt** (Grep, `^        (named = re|if not named|if named)`; the two original lines, no inserted `if named:` / `if not named:` left):

```
8486:        named = re.match(r"diff --git a/(.+) b/(.+)$", header)
8487:        if named and named.group(2) in leave_out:
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 0.36s
exit=0
```

## G11. Quoted-header section emission (`round_driver._attempt_fixer_delta`)

- **Axis:** a section whose header does not parse as `a/… b/…` at all (git quotes a path with a non-ASCII or control character: `diff --git "a/…" "b/…"`) is emitted under its own header line, so the delta is refused and the auditor sees the file. G10 and G11 do not share one neutralization: they are the two sides of the `named` test, so each has its own.
- **Detector:** `test_audit_review_guarded_2341.py::test_t15_a_fix_that_adds_a_code_file_with_a_quoted_name_is_refused`. The fixture's git quoted the name as observed (`diff --git "a/pkg/caf\303\251.py" "b/pkg/caf\303\251.py"`), so the quoted-header case is the one under test.
- **Neutralization:** two lines inserted in `_attempt_fixer_delta` right before `if named and named.group(2) in leave_out:`: `if not named:` / `            continue`, so a header that does not parse is skipped.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
______ test_t15_a_fix_that_adds_a_code_file_with_a_quoted_name_is_refused ______

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-29/test_t15_a_fix_that_adds_a_cod0')

    def test_t15_a_fix_that_adds_a_code_file_with_a_quoted_name_is_refused(tmp_path):
        # axis: G11 — a header that does not read `a/<f> b/<f>` (git-quoted path) is emitted under its own header
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/audit_review_guarded_2341.md
        quoted = "pkg/café.py"
    
        def fix(repo):
            _write(repo, quoted, "def cafe():\n    return 1\n")
            _reword_guide(repo)
    
        _, head_diff, delta = _built_delta(tmp_path, fix)
        observed = [h for h in _headers(head_diff.splitlines()) if "caf" in h]
        assert len(observed) == 1, head_diff
        assert '"' in observed[0], observed  # git quotes the non-ASCII name under the default core.quotePath
>       assert observed[0] in delta
E       assert 'diff --git "a/pkg/caf\\303\\251.py" "b/pkg/caf\\303\\251.py"' in ['diff --git a/docs/guide.md b/docs/guide.md', '@@ -1,0 +1,9 @@', '+diff --git a/docs/guide.md b/docs/guide.md', '+index 4a3fa27..ce0a2f8 100644', '+--- a/docs/guide.md', '++++ b/docs/guide.md', ...]

/home/user/wt-2341/plugins/superheroes/lib/tests/test_audit_review_guarded_2341.py:427: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_audit_review_guarded_2341.py::test_t15_a_fix_that_adds_a_code_file_with_a_quoted_name_is_refused
1 failed in 0.38s
exit=1
```

- **Restore:** inverse edit (the two inserted lines removed).
- **Restore receipt** (Grep, same pattern; the two original lines, no inserted line left):

```
8486:        named = re.match(r"diff --git a/(.+) b/(.+)$", header)
8487:        if named and named.group(2) in leave_out:
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 0.28s
exit=0
```

## G12. The leave-out check for a header's destination (`round_driver._attempt_fixer_delta`, `_diff_header_sides`)

- **Axis:** a left-out proven copy stays out of the fixer delta whatever its header's form; the destination comes from the one canonical reader (`_diff_header_sides`, git C-quoting undone), which the driver delegates to rather than carrying its own decoder (#2341 seam ruling).
- **Detector:** `test_audit_review_guarded_2341.py::test_t16_a_left_out_proven_copy_with_a_quoted_name_stays_out_of_the_delta`.
- **Neutralization:** in `_attempt_fixer_delta`, `if sides is not None and sides[1] in leave_out:` became `if False:`, so no two-path or quoted header is ever left out. The `sides = _diff_header_sides(header)` line above it stayed.
- **Note:** G10 and G11 above quote the neutralizations against the WO-4 form (`named = re.match(...)`), which no longer exists; their detectors (T13, T15) still pass on the current head (neighbour run, 161 passed) but were not re-neutralized in this dispatch.

**Raw red** (exit 1; run from `/home/user/wt-2341`, `UV_NATIVE_TLS` warning left out):

```
F                                                                        [100%]
=================================== FAILURES ===================================
__ test_t16_a_left_out_proven_copy_with_a_quoted_name_stays_out_of_the_delta ___

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-34/test_t16_a_left_out_proven_cop0')

    def test_t16_a_left_out_proven_copy_with_a_quoted_name_stays_out_of_the_delta(tmp_path):
        # axis: G12 — `leave_out` is honoured for a git-quoted header, so a proven copy never enters the delta
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/audit_review_guarded_2341.md
        quoted = "pkg/café.py"
    
        def fix(repo):
            _write(repo, quoted, "def cafe():\n    return 1\n")
            _reword_guide(repo)
    
        reviewed_diff, head_diff, _ = _built_delta(tmp_path, fix)
        delta = RD._attempt_fixer_delta(reviewed_diff, head_diff, leave_out=(quoted,))
>       assert _headers(delta) == ["diff --git a/%s b/%s" % (GUIDE, GUIDE)]
E       assert ['diff --git ...303\\251.py"'] == ['diff --git ...ocs/guide.md']
E         
E         Left contains one more item: 'diff --git "a/pkg/caf\\303\\251.py" "b/pkg/caf\\303\\251.py"'
E         Use -v to get more diff

/home/user/wt-2341/plugins/superheroes/lib/tests/test_audit_review_guarded_2341.py:463: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_audit_review_guarded_2341.py::test_t16_a_left_out_proven_copy_with_a_quoted_name_stays_out_of_the_delta
1 failed in 1.54s
exit=1
```

- **Restore:** inverse edit (`if False:` back to `if sides is not None and sides[1] in leave_out:`).
- **Restore receipt** (Grep, `sides = _diff_header_sides\(header\)|in leave_out`; the original two lines, no `if False:` left):

```
8487:        sides = _diff_header_sides(header)
8488:        if sides is not None and sides[1] in leave_out:
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 0.34s
exit=0
```

## G13. The exact-bytes comparison at the leave-out check (`round_driver._attempt_fixer_delta`)

- **Axis:** two destinations whose names differ only in one invalid UTF-8 byte stay distinct keys, so a left-out proven copy never hides a different changed code file (audit-001 on the #2341 fix; `_diff_header_sides` keeps an invalid byte as a surrogate escape, so `leave_out` names compare exactly).
- **Detector:** `test_audit_review_guarded_2341.py::test_t17_a_left_out_copy_never_hides_a_changed_file_whose_name_differs_in_one_invalid_byte` (the fix adds `pkg/bad<0xff>.py` and `pkg/bad<0xfe>.py`; `leave_out` names the first).
- **Neutralization:** `if sides is not None and sides[1] in leave_out:` became a check that decodes both the destination and each `leave_out` name lossily, the old `errors="replace"` behaviour: `if sides is not None and sides[1].encode("utf-8", "surrogateescape").decode("utf-8", "replace") in tuple(os.fsdecode(os.fsencode(p)).encode("utf-8", "surrogateescape").decode("utf-8", "replace") for p in leave_out):`. Both sides are made lossy because a lossy destination against an exact `leave_out` name would simply leave nothing out; the collision the audit found needs both keys lossy.

**Raw red** (exit 1; `UV_NATIVE_TLS` warning left out):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_t17_a_left_out_copy_never_hides_a_changed_file_whose_name_differs_in_one_invalid_byte _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-36/test_t17_a_left_out_copy_never0')

    def test_t17_a_left_out_copy_never_hides_a_changed_file_whose_name_differs_in_one_invalid_byte(tmp_path):
        # axis: G13 — `leave_out` compares the exact destination, so two names that differ in one invalid byte stay distinct
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/audit_review_guarded_2341.md
        left_out_bytes, changed_bytes = b"pkg/bad\xff.py", b"pkg/bad\xfe.py"
        left_out, changed = os.fsdecode(left_out_bytes), os.fsdecode(changed_bytes)
    
        def fix(repo):
            for name in (left_out_bytes, changed_bytes):
                path = os.fsencode(str(repo)) + b"/" + name
                with open(path, "wb") as handle:
                    handle.write(b"def f():\n    return 1\n")
            _reword_guide(repo)
    
        reviewed_diff, head_diff, _ = _built_delta(tmp_path, fix)
        header_left_out = [h for h in _headers(head_diff.splitlines()) if "\\377" in h]
        header_changed = [h for h in _headers(head_diff.splitlines()) if "\\376" in h]
        assert len(header_left_out) == 1 and len(header_changed) == 1, head_diff
        delta = RD._attempt_fixer_delta(reviewed_diff, head_diff, leave_out=(left_out,))
>       assert header_changed[0] in delta
E       assert 'diff --git "a/pkg/bad\\376.py" "b/pkg/bad\\376.py"' in ['diff --git a/docs/guide.md b/docs/guide.md', '@@ -1,0 +1,9 @@', '+diff --git a/docs/guide.md b/docs/guide.md', '+index 4a3fa27..ce0a2f8 100644', '+--- a/docs/guide.md', '++++ b/docs/guide.md', ...]

/home/user/wt-2341/plugins/superheroes/lib/tests/test_audit_review_guarded_2341.py:486: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_audit_review_guarded_2341.py::test_t17_a_left_out_copy_never_hides_a_changed_file_whose_name_differs_in_one_invalid_byte
1 failed in 0.49s
exit=1
```

- **Restore:** inverse edit (the lossy line back to `if sides is not None and sides[1] in leave_out:`).
- **Restore receipt** (Grep, `sides = _diff_header_sides\(header\)|in leave_out|replace"` over `round_driver.py`; lines 8487 and 8488 are the restored pair, the other matches are unrelated `decode(..., "replace")` calls elsewhere in the file):

```
8479:            if file in leave_out:
8487:        sides = _diff_header_sides(header)
8488:        if sides is not None and sides[1] in leave_out:
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 0.36s
exit=0
```

## Not proven

Elements outside the declared set have tests with `# axis:` lines or plain asserts but no neutralization and no red recorded here, so their protection is **unverified by a bite-proof**: the `span <= 0 or span % 2` length guard in `_delta_files` (E-1, E-2, E-4; asserted by `test_t5_an_unreadable_delta_is_never_prose_only` and the `empty-path` case of `test_t12_...`, neither neutralized); the `no`-wins ordering over `review-guarded` (E-i, `test_t6_a_no_on_another_check_wins_over_review_guarded`); the case-insensitive component match; the schema enum (T8); the order's answer token (T9); `yes` answers staying untouched by the new arm (T7).
