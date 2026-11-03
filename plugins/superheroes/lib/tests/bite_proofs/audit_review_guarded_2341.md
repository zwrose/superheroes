# Bite-proof record — a prose-only fix clears its audit on a `review-guarded` answer (#2341)

Detector file: `plugins/superheroes/lib/tests/test_audit_review_guarded_2341.py`, unedited between each red and its green. Every entry is a targeted, reversible Edit-tool edit to one production file (`plugins/superheroes/lib/audits.py`), restored by the inverse edit (no `git checkout`, `restore`, `reset` or `stash`). Runs: `scripts/pinned-python -B -X pycache_prefix=/tmp/claude-0/pyc -m pytest '<exact node id>' -q -n 0`, one test node each (G4, G5 and G6 name the test function, so its parametrized cases run together), output captured whole, followed by the `exit=` line the command printed. The `UV_NATIVE_TLS` deprecation warning that `uv` prints first is the only line left out of each capture. The seven guarded elements are the seven the order declared; none is grouped. Each `old_string` occurred exactly once (the Edit tool refuses a non-unique match). No secrets, tokens, private URLs or PII appear in any capture; nothing was redacted.

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

## Not proven

Elements outside the declared set have tests with `# axis:` lines or plain asserts but no neutralization and no red recorded here, so their protection is **unverified by a bite-proof**: the unreadable-header rejection in `_delta_files` (E-d, asserted by `test_t5_an_unreadable_delta_is_never_prose_only`); the `no`-wins ordering over `review-guarded` (E-i, `test_t6_a_no_on_another_check_wins_over_review_guarded`); the case-insensitive component match; the schema enum (T8); the order's answer token (T9); `yes` answers staying untouched by the new arm (T7).
