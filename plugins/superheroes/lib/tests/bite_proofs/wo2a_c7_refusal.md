# WO-2a2 (C7 L1) bite-proof — the consequence refusal in `mechanical_compile`

Produced by the implementer of work order WO-2a2; the orchestrator re-runs it at verification.
Nothing here is marked accepted.

**Declared guarded-element set (from the order):** `G6` only — the refusal step in
`mechanical_compile`, `plugins/superheroes/lib/round_driver.py:973`
(`if not finding_outcomes.has_stated_consequence(f):` → drop row, reason
`COMPILE_DROP_NO_CONSEQUENCE = "no stated consequence"`).

**Axis claimed:** refusal at the compile step — the unstated-consequence finding is absent from
`compiled` and its drop row is in `drops`. The red below is on that axis (the finding survives
compile), not on the helper `has_stated_consequence`, which the earlier tests already assert as a
precondition.

**Detector:** `plugins/superheroes/lib/tests/test_finding_outcomes_c7.py::test_compile_drops_a_finding_that_states_no_consequence`
(test (a); six parametrized cases: missing, none, empty, whitespace, int, list). The node id
selects all six cases; they are one test function. The detector was unedited between the red and
green runs. The axis comment line was added to the test file after this proof ran (a comment only).
Tests (b) and (c) in the same file are not part of the declared set and carry no neutralization
in this record.

**Normalization:** every run used `scripts/pinned-python -B -m pytest ... -p no:cacheprovider`
(`-B` writes no bytecode, so no stale compiled file can serve the unedited module). Nothing was
pinned beyond that.

## G6 — the refusal step

**Neutralization** (one targeted edit through the host's edit action; the target occurred exactly
once — `grep -c 'has_stated_consequence(f)'` = 1 before the edit):

```
-        if not finding_outcomes.has_stated_consequence(f):
+        if False and not finding_outcomes.has_stated_consequence(f):
```

The drop row under it is left in place and unreachable, so the proof measures the condition, not a
deleted body.

**sha256 of `plugins/superheroes/lib/round_driver.py`:**

| state | sha256 |
|---|---|
| before | `fe7738b40f74c901d673e4243d606c3e80a1b85639e5aa21e93b2757fbc3476c` |
| neutralized | `1da7f7a244bf5b36cd2eb6e8b87001b684504382f77c30d666220c80369677fc` |
| after (restored) | `fe7738b40f74c901d673e4243d606c3e80a1b85639e5aa21e93b2757fbc3476c` |

**Raw red** — `scripts/pinned-python -B -m pytest "plugins/superheroes/lib/tests/test_finding_outcomes_c7.py::test_compile_drops_a_finding_that_states_no_consequence" -q -p no:cacheprovider`
(exit 1). Quoted in full, apart from the leading `UV_NATIVE_TLS` deprecation warning line the
launcher prints, and the line numbers: the test file's axis comment was added after this run, so
the assertion line reads 393 in the run and 394 in the final file.

```
FFFFFF                                                                   [100%]
=================================== FAILURES ===================================
_______ test_compile_drops_a_finding_that_states_no_consequence[missing] _______

extra = {}

    @pytest.mark.parametrize("extra", [
        {}, {"consequence": None}, {"consequence": ""}, {"consequence": "  \n\t "},
        {"consequence": 5}, {"consequence": ["x"]},
    ], ids=["missing", "none", "empty", "whitespace", "int", "list"])
    def test_compile_drops_a_finding_that_states_no_consequence(extra):
        finding = _raised(**extra)
        compiled, drops = round_driver.mechanical_compile([finding], COMPILE_DIFF)
>       assert compiled == []
E       AssertionError: assert [{'file': 'f....ortant', ...}] == []
E         
E         Left contains one more item: {'file': 'f.py', 'line': 1, 'title': 't', 'severity': 'Important', ...}
E         Use -v to get more diff

/home/user/c7-wt/plugins/superheroes/lib/tests/test_finding_outcomes_c7.py:393: AssertionError
________ test_compile_drops_a_finding_that_states_no_consequence[none] _________

extra = {'consequence': None}

    @pytest.mark.parametrize("extra", [
        {}, {"consequence": None}, {"consequence": ""}, {"consequence": "  \n\t "},
        {"consequence": 5}, {"consequence": ["x"]},
    ], ids=["missing", "none", "empty", "whitespace", "int", "list"])
    def test_compile_drops_a_finding_that_states_no_consequence(extra):
        finding = _raised(**extra)
        compiled, drops = round_driver.mechanical_compile([finding], COMPILE_DIFF)
>       assert compiled == []
E       AssertionError: assert [{'file': 'f....ortant', ...}] == []
E         
E         Left contains one more item: {'file': 'f.py', 'line': 1, 'title': 't', 'severity': 'Important', ...}
E         Use -v to get more diff

/home/user/c7-wt/plugins/superheroes/lib/tests/test_finding_outcomes_c7.py:393: AssertionError
________ test_compile_drops_a_finding_that_states_no_consequence[empty] ________

extra = {'consequence': ''}

    @pytest.mark.parametrize("extra", [
        {}, {"consequence": None}, {"consequence": ""}, {"consequence": "  \n\t "},
        {"consequence": 5}, {"consequence": ["x"]},
    ], ids=["missing", "none", "empty", "whitespace", "int", "list"])
    def test_compile_drops_a_finding_that_states_no_consequence(extra):
        finding = _raised(**extra)
        compiled, drops = round_driver.mechanical_compile([finding], COMPILE_DIFF)
>       assert compiled == []
E       AssertionError: assert [{'file': 'f....ortant', ...}] == []
E         
E         Left contains one more item: {'file': 'f.py', 'line': 1, 'title': 't', 'severity': 'Important', ...}
E         Use -v to get more diff

/home/user/c7-wt/plugins/superheroes/lib/tests/test_finding_outcomes_c7.py:393: AssertionError
_____ test_compile_drops_a_finding_that_states_no_consequence[whitespace] ______

extra = {'consequence': '  \n\t '}

    @pytest.mark.parametrize("extra", [
        {}, {"consequence": None}, {"consequence": ""}, {"consequence": "  \n\t "},
        {"consequence": 5}, {"consequence": ["x"]},
    ], ids=["missing", "none", "empty", "whitespace", "int", "list"])
    def test_compile_drops_a_finding_that_states_no_consequence(extra):
        finding = _raised(**extra)
        compiled, drops = round_driver.mechanical_compile([finding], COMPILE_DIFF)
>       assert compiled == []
E       AssertionError: assert [{'file': 'f....ortant', ...}] == []
E         
E         Left contains one more item: {'file': 'f.py', 'line': 1, 'title': 't', 'severity': 'Important', ...}
E         Use -v to get more diff

/home/user/c7-wt/plugins/superheroes/lib/tests/test_finding_outcomes_c7.py:393: AssertionError
_________ test_compile_drops_a_finding_that_states_no_consequence[int] _________

extra = {'consequence': 5}

    @pytest.mark.parametrize("extra", [
        {}, {"consequence": None}, {"consequence": ""}, {"consequence": "  \n\t "},
        {"consequence": 5}, {"consequence": ["x"]},
    ], ids=["missing", "none", "empty", "whitespace", "int", "list"])
    def test_compile_drops_a_finding_that_states_no_consequence(extra):
        finding = _raised(**extra)
        compiled, drops = round_driver.mechanical_compile([finding], COMPILE_DIFF)
>       assert compiled == []
E       AssertionError: assert [{'file': 'f....ortant', ...}] == []
E         
E         Left contains one more item: {'file': 'f.py', 'line': 1, 'title': 't', 'severity': 'Important', ...}
E         Use -v to get more diff

/home/user/c7-wt/plugins/superheroes/lib/tests/test_finding_outcomes_c7.py:393: AssertionError
________ test_compile_drops_a_finding_that_states_no_consequence[list] _________

extra = {'consequence': ['x']}

    @pytest.mark.parametrize("extra", [
        {}, {"consequence": None}, {"consequence": ""}, {"consequence": "  \n\t "},
        {"consequence": 5}, {"consequence": ["x"]},
    ], ids=["missing", "none", "empty", "whitespace", "int", "list"])
    def test_compile_drops_a_finding_that_states_no_consequence(extra):
        finding = _raised(**extra)
        compiled, drops = round_driver.mechanical_compile([finding], COMPILE_DIFF)
>       assert compiled == []
E       AssertionError: assert [{'file': 'f....ortant', ...}] == []
E         
E         Left contains one more item: {'file': 'f.py', 'line': 1, 'title': 't', 'severity': 'Important', ...}
E         Use -v to get more diff

/home/user/c7-wt/plugins/superheroes/lib/tests/test_finding_outcomes_c7.py:393: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_finding_outcomes_c7.py::test_compile_drops_a_finding_that_states_no_consequence[missing]
FAILED plugins/superheroes/lib/tests/test_finding_outcomes_c7.py::test_compile_drops_a_finding_that_states_no_consequence[none]
FAILED plugins/superheroes/lib/tests/test_finding_outcomes_c7.py::test_compile_drops_a_finding_that_states_no_consequence[empty]
FAILED plugins/superheroes/lib/tests/test_finding_outcomes_c7.py::test_compile_drops_a_finding_that_states_no_consequence[whitespace]
FAILED plugins/superheroes/lib/tests/test_finding_outcomes_c7.py::test_compile_drops_a_finding_that_states_no_consequence[int]
FAILED plugins/superheroes/lib/tests/test_finding_outcomes_c7.py::test_compile_drops_a_finding_that_states_no_consequence[list]
6 failed in 3.08s
```

**Restore:** the inverse edit, `if False and not finding_outcomes.has_stated_consequence(f):` →
`if not finding_outcomes.has_stated_consequence(f):`. No `git checkout`, `restore`, `stash` or
`reset` was used.

**Restore receipt:** the restored line, read back by search at `round_driver.py:973`:

```
        if not finding_outcomes.has_stated_consequence(f):
```

and a grep for `if False` over `round_driver.py` matched nothing; the sha256 after the restore
equals the sha256 before the neutralization (table above).

**Raw green** — same node id, after the restore:

```
......                                                                   [100%]
6 passed in 2.73s
```
