# wo_a_1796_reading-independence — the review record enforces the reading and maker independence

Declared guarded-element set (from the work order): **N1** the reading rule's engine-record branch; **N2** the reading
rule's session-reported branch; **N3** the run-identity check (row vs engine record); **N4** the empty-makers
not-reviewed line; **N5** the maker-family not-run branch; **N6** the owner's-word completeness check; **N7**
`reading_next`'s unfilled-seat park; **N8** `reading_next`'s maker-family-seat park.

Each element was neutralized in production code (`plugins/superheroes/lib/review_record.py`) one at a time, its detector
node run alone (red), restored by the inverse edit, and the same node re-run (green) before the next element was touched.
So no red below was captured with another neutralization still applied. Detector tests are in
`plugins/superheroes/lib/tests/test_review_record.py` and were not edited during the proofs. Redaction: the outputs below
carry no temp paths (no test here uses `tmp_path`); the worktree path in traceback lines is as pytest printed it and nothing
else was secret, so nothing was redacted. Nodes given without a parameter id run all of their parameters.

## N1 — the engine-record branch of the reading rule

**Guarded element:** `_reviewer`, the `if not isinstance(obs, dict) or obs.get("read") != "engaged":` line under
`if lane_value != "full":` / `if out["ran"] == "engine-record":`. Axis: outside the full lane an engine record whose
reading is `unknown`, absent or malformed does not credit the reviewer.

**Detector:** `test_review_record.py::test_a_light_lane_reading_that_is_not_engaged_is_not_run`

**Neutralization:** `            if not isinstance(obs, dict) or obs.get("read") != "engaged":` →
`            if False and (not isinstance(obs, dict) or obs.get("read") != "engaged"):`

**Raw red:**
```
FFFFF                                                                    [100%]
=================================== FAILURES ===================================
____ test_a_light_lane_reading_that_is_not_engaged_is_not_run[observation0] ____

observation = {'tokens': 1, 'read': 'unknown'}

    @pytest.mark.parametrize("observation", [
        {"tokens": 1, "read": "unknown"}, {"tokens": 1}, None, "engaged", ["engaged"]])
    def test_a_light_lane_reading_that_is_not_engaged_is_not_run(observation):
        # axis: the engine-record branch of the reading rule; an unknown, absent or malformed reading being credited
        fake = Fake(runs={"/run/code-reviewer": (_run_with(observation), None)})
        rec = build(account(**LIGHT), fake)
        v = rec["reviewers"][0]
>       assert v["ran"] == "not-run" and v["reading"] == "not-shown" and "observation" not in v
E       AssertionError: assert ('engine-record' == 'not-run'
E         
E         - not-run
E         + engine-record)

/home/user/wt-1796-a/plugins/superheroes/lib/tests/test_review_record.py:2079: AssertionError
____ test_a_light_lane_reading_that_is_not_engaged_is_not_run[observation1] ____

observation = {'tokens': 1}

    @pytest.mark.parametrize("observation", [
        {"tokens": 1, "read": "unknown"}, {"tokens": 1}, None, "engaged", ["engaged"]])
    def test_a_light_lane_reading_that_is_not_engaged_is_not_run(observation):
        # axis: the engine-record branch of the reading rule; an unknown, absent or malformed reading being credited
        fake = Fake(runs={"/run/code-reviewer": (_run_with(observation), None)})
        rec = build(account(**LIGHT), fake)
        v = rec["reviewers"][0]
>       assert v["ran"] == "not-run" and v["reading"] == "not-shown" and "observation" not in v
E       AssertionError: assert ('engine-record' == 'not-run'
E         
E         - not-run
E         + engine-record)

/home/user/wt-1796-a/plugins/superheroes/lib/tests/test_review_record.py:2079: AssertionError
________ test_a_light_lane_reading_that_is_not_engaged_is_not_run[None] ________

observation = None

    @pytest.mark.parametrize("observation", [
        {"tokens": 1, "read": "unknown"}, {"tokens": 1}, None, "engaged", ["engaged"]])
    def test_a_light_lane_reading_that_is_not_engaged_is_not_run(observation):
        # axis: the engine-record branch of the reading rule; an unknown, absent or malformed reading being credited
        fake = Fake(runs={"/run/code-reviewer": (_run_with(observation), None)})
        rec = build(account(**LIGHT), fake)
        v = rec["reviewers"][0]
>       assert v["ran"] == "not-run" and v["reading"] == "not-shown" and "observation" not in v
E       AssertionError: assert ('engine-record' == 'not-run'
E         
E         - not-run
E         + engine-record)

/home/user/wt-1796-a/plugins/superheroes/lib/tests/test_review_record.py:2079: AssertionError
_______ test_a_light_lane_reading_that_is_not_engaged_is_not_run[engaged] _______

observation = 'engaged'

    @pytest.mark.parametrize("observation", [
        {"tokens": 1, "read": "unknown"}, {"tokens": 1}, None, "engaged", ["engaged"]])
    def test_a_light_lane_reading_that_is_not_engaged_is_not_run(observation):
        # axis: the engine-record branch of the reading rule; an unknown, absent or malformed reading being credited
        fake = Fake(runs={"/run/code-reviewer": (_run_with(observation), None)})
        rec = build(account(**LIGHT), fake)
        v = rec["reviewers"][0]
>       assert v["ran"] == "not-run" and v["reading"] == "not-shown" and "observation" not in v
E       AssertionError: assert ('engine-record' == 'not-run'
E         
E         - not-run
E         + engine-record)

/home/user/wt-1796-a/plugins/superheroes/lib/tests/test_review_record.py:2079: AssertionError
____ test_a_light_lane_reading_that_is_not_engaged_is_not_run[observation4] ____

observation = ['engaged']

    @pytest.mark.parametrize("observation", [
        {"tokens": 1, "read": "unknown"}, {"tokens": 1}, None, "engaged", ["engaged"]])
    def test_a_light_lane_reading_that_is_not_engaged_is_not_run(observation):
        # axis: the engine-record branch of the reading rule; an unknown, absent or malformed reading being credited
        fake = Fake(runs={"/run/code-reviewer": (_run_with(observation), None)})
        rec = build(account(**LIGHT), fake)
        v = rec["reviewers"][0]
>       assert v["ran"] == "not-run" and v["reading"] == "not-shown" and "observation" not in v
E       AssertionError: assert ('engine-record' == 'not-run'
E         
E         - not-run
E         + engine-record)

/home/user/wt-1796-a/plugins/superheroes/lib/tests/test_review_record.py:2079: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record.py::test_a_light_lane_reading_that_is_not_engaged_is_not_run[observation0]
FAILED plugins/superheroes/lib/tests/test_review_record.py::test_a_light_lane_reading_that_is_not_engaged_is_not_run[observation1]
FAILED plugins/superheroes/lib/tests/test_review_record.py::test_a_light_lane_reading_that_is_not_engaged_is_not_run[None]
FAILED plugins/superheroes/lib/tests/test_review_record.py::test_a_light_lane_reading_that_is_not_engaged_is_not_run[engaged]
FAILED plugins/superheroes/lib/tests/test_review_record.py::test_a_light_lane_reading_that_is_not_engaged_is_not_run[observation4]
5 failed in 0.50s
```
The red is on the claimed axis: every non-engaged reading (unknown, absent, `None`, a string, a list) is credited as
`engine-record` with the branch dead.

**Restore:** inverse edit, `            if False and (not isinstance(obs, dict) or obs.get("read") != "engaged"):` →
`            if not isinstance(obs, dict) or obs.get("read") != "engaged":`

**Restore receipt** (restored line, quoted from `review_record.py:498`):
```
            if not isinstance(obs, dict) or obs.get("read") != "engaged":
```

**Raw green:**
```
.....                                                                    [100%]
5 passed in 2.16s
```

## N2 — the session-reported branch of the reading rule

**Guarded element:** `_reviewer`, the `elif out["ran"] == "reported-by-session":` branch under `if lane_value != "full":`.
Axis: outside the full lane a reviewer the session only reports (no engine record) does not count.

**Detector:** `test_review_record.py::test_a_session_only_light_lane_reviewer_is_not_run`

**Neutralization:** `        elif out["ran"] == "reported-by-session":` → `        elif False and out["ran"] == "reported-by-session":`

**Raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
______________ test_a_session_only_light_lane_reviewer_is_not_run ______________

    def test_a_session_only_light_lane_reviewer_is_not_run():
        # axis: the session-reported branch of the reading rule; a reviewer with no run directory credited on a light lane
        rec = build(account(**LIGHT, reviewers=[reviewer(runDir="")]))
        v = rec["reviewers"][0]
>       assert v["ran"] == "not-run" and v["reading"] == "not-shown"
E       AssertionError: assert ('reported-by-session' == 'not-run'
E         
E         - not-run
E         + reported-by-session)

/home/user/wt-1796-a/plugins/superheroes/lib/tests/test_review_record.py:2090: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record.py::test_a_session_only_light_lane_reviewer_is_not_run
1 failed in 2.22s
```

**Restore:** inverse edit, `        elif False and out["ran"] == "reported-by-session":` → `        elif out["ran"] == "reported-by-session":`

**Restore receipt** (restored line, quoted from `review_record.py:500`):
```
        elif out["ran"] == "reported-by-session":
```

**Raw green:**
```
.                                                                        [100%]
1 passed in 0.33s
```

## N3 — the run-identity check (row vs engine record)

**Guarded element:** `_reviewer`, the `if credited.get("source") != r["vendor"] or credited.get("engineModel") != r["model"]:`
line. Axis: a run record that names a different vendor or model than the account row does not credit the row.

**Detector:** `test_review_record.py::test_a_mislabelled_engine_run_is_not_run` (a codex run record against a claude row)

**Neutralization:** `        if credited.get("source") != r["vendor"] or credited.get("engineModel") != r["model"]:` →
`        if False and (credited.get("source") != r["vendor"] or credited.get("engineModel") != r["model"]):`

**Raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
___________________ test_a_mislabelled_engine_run_is_not_run ___________________

    def test_a_mislabelled_engine_run_is_not_run():
        # axis: the run-identity check; a codex run record credited to a row that names a claude reviewer
        fake = Fake(runs={"/run/code-reviewer": (copy.deepcopy(GOOD_RUN), None)})
        rec = build(account(makers=[{"family": "someone-else"}], reviewers=[maker_family_reviewer()]), fake)
        v = rec["reviewers"][0]
>       assert v["ran"] == "not-run" and v["runNote"] == "the run record names a different reviewer than the account row"
E       AssertionError: assert ('engine-record' == 'not-run'
E         
E         - not-run
E         + engine-record)

/home/user/wt-1796-a/plugins/superheroes/lib/tests/test_review_record.py:2115: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record.py::test_a_mislabelled_engine_run_is_not_run
1 failed in 0.36s
```

**Restore:** inverse edit, `        if False and (credited.get("source") != r["vendor"] or credited.get("engineModel") != r["model"]):` →
`        if credited.get("source") != r["vendor"] or credited.get("engineModel") != r["model"]:`

**Restore receipt** (restored line, quoted from `review_record.py:490`):
```
        if credited.get("source") != r["vendor"] or credited.get("engineModel") != r["model"]:
```

**Raw green:**
```
.                                                                        [100%]
1 passed in 0.32s
```

## N4 — the empty-makers not-reviewed line

**Guarded element:** `_status`, the `if not rec["makers"]:` branch that adds `"no maker is named, so independence cannot be shown"`.
Axis: a record that names no maker reads `not-reviewed` and says why in fixed prose, never `reviewed`.

**Detector:** `test_review_record.py::test_empty_or_omitted_makers_is_not_reviewed_with_the_fixed_line` (makers omitted, `[]` and `None`)

**Neutralization:** `    if not rec["makers"]:` → `    if False and not rec["makers"]:`

**Raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_______ test_empty_or_omitted_makers_is_not_reviewed_with_the_fixed_line _______

    def test_empty_or_omitted_makers_is_not_reviewed_with_the_fixed_line():
        # axis: the no-maker line; a record with no named maker reading reviewed
        line = "no maker is named, so independence cannot be shown"
        omitted = {k: v for k, v in account().items() if k != "makers"}
        for acct in (omitted, account(makers=[]), account(makers=None)):
            rec = build(acct)
>           assert rec["status"] == "not-reviewed" and line in rec["whatIsMissing"]
E           AssertionError: assert ('reviewed' == 'not-reviewed'
E             
E             - not-reviewed
E             ? ----
E             + reviewed)

/home/user/wt-1796-a/plugins/superheroes/lib/tests/test_review_record.py:2146: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record.py::test_empty_or_omitted_makers_is_not_reviewed_with_the_fixed_line
1 failed in 0.36s
```

**Restore:** inverse edit, `    if False and not rec["makers"]:` → `    if not rec["makers"]:`

**Restore receipt** (restored line, quoted from `review_record.py:593`):
```
    if not rec["makers"]:
```

**Raw green:**
```
.                                                                        [100%]
1 passed in 0.35s
```

## N5 — the maker-family not-run branch

**Guarded element:** `_reviewer`, the `elif out["family"] in maker_families:` branch. Axis: a reviewer from a maker's family
with no owner's word does not count as run.

**Detector:** `test_review_record.py::test_a_same_family_reviewer_without_the_owners_word_is_not_run`

**Neutralization:** `        elif out["family"] in maker_families:` → `        elif False and out["family"] in maker_families:`

**Raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
________ test_a_same_family_reviewer_without_the_owners_word_is_not_run ________

    def test_a_same_family_reviewer_without_the_owners_word_is_not_run():
        # axis: the maker-family branch; a reviewer from a maker's family credited with no owner's word
        fake = Fake(runs={"/run/code-reviewer": (copy.deepcopy(CLAUDE_RUN), None)})
        rec = build(account(reviewers=[maker_family_reviewer(notIndependent=False)]), fake)
        v = rec["reviewers"][0]
>       assert v["ran"] == "not-run" and "notIndependent" not in v
E       AssertionError: assert ('engine-record' == 'not-run'
E         
E         - not-run
E         + engine-record)

/home/user/wt-1796-a/plugins/superheroes/lib/tests/test_review_record.py:2168: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record.py::test_a_same_family_reviewer_without_the_owners_word_is_not_run
1 failed in 0.36s
```

**Restore:** inverse edit, `        elif False and out["family"] in maker_families:` → `        elif out["family"] in maker_families:`

**Restore receipt** (restored line, quoted from `review_record.py:507`):
```
        elif out["family"] in maker_families:
```

**Raw green:**
```
.                                                                        [100%]
1 passed in 0.32s
```

## N6 — the owner's-word completeness check

**Guarded element:** `_reviewer`, the `if _own_word_ok(r.get("ownerWord")):` line inside the maker-family branch. Axis: an
owner's word that is missing, or has a missing, blank or non-text `words` or `where`, does not admit a same-family reviewer.

**Detector:** `test_review_record.py::test_an_incomplete_owners_word_does_not_admit_a_same_family_reviewer` (seven words)

**Neutralization:** `            if _own_word_ok(r.get("ownerWord")):` → `            if True or _own_word_ok(r.get("ownerWord")):`

**Raw red:**
```
FFFFFFF                                                                  [100%]
=================================== FAILURES ===================================
__ test_an_incomplete_owners_word_does_not_admit_a_same_family_reviewer[None] __

word = None

    @pytest.mark.parametrize("word", [
        None, {}, {"words": "go ahead"}, {"where": "http://c/9"}, {"words": "", "where": "http://c/9"},
        {"words": "go ahead", "where": "  "}, {"words": 3, "where": "http://c/9"}])
    def test_an_incomplete_owners_word_does_not_admit_a_same_family_reviewer(word):
        # axis: the owner's-word completeness check; a missing, blank or non-text words or where admitting the reviewer
        fake = Fake(runs={"/run/code-reviewer": (copy.deepcopy(CLAUDE_RUN), None)})
        rec = build(account(reviewers=[maker_family_reviewer(ownerWord=word)]), fake)
>       assert rec["reviewers"][0]["ran"] == "not-run" and "notIndependent" not in rec["reviewers"][0]
E       AssertionError: assert ('engine-record' == 'not-run'
E         
E         - not-run
E         + engine-record)

/home/user/wt-1796-a/plugins/superheroes/lib/tests/test_review_record.py:2191: AssertionError
_ test_an_incomplete_owners_word_does_not_admit_a_same_family_reviewer[word1] __

word = {}

    @pytest.mark.parametrize("word", [
        None, {}, {"words": "go ahead"}, {"where": "http://c/9"}, {"words": "", "where": "http://c/9"},
        {"words": "go ahead", "where": "  "}, {"words": 3, "where": "http://c/9"}])
    def test_an_incomplete_owners_word_does_not_admit_a_same_family_reviewer(word):
        # axis: the owner's-word completeness check; a missing, blank or non-text words or where admitting the reviewer
        fake = Fake(runs={"/run/code-reviewer": (copy.deepcopy(CLAUDE_RUN), None)})
        rec = build(account(reviewers=[maker_family_reviewer(ownerWord=word)]), fake)
>       assert rec["reviewers"][0]["ran"] == "not-run" and "notIndependent" not in rec["reviewers"][0]
E       AssertionError: assert ('engine-record' == 'not-run'
E         
E         - not-run
E         + engine-record)

/home/user/wt-1796-a/plugins/superheroes/lib/tests/test_review_record.py:2191: AssertionError
_ test_an_incomplete_owners_word_does_not_admit_a_same_family_reviewer[word2] __

word = {'words': 'go ahead'}

    @pytest.mark.parametrize("word", [
        None, {}, {"words": "go ahead"}, {"where": "http://c/9"}, {"words": "", "where": "http://c/9"},
        {"words": "go ahead", "where": "  "}, {"words": 3, "where": "http://c/9"}])
    def test_an_incomplete_owners_word_does_not_admit_a_same_family_reviewer(word):
        # axis: the owner's-word completeness check; a missing, blank or non-text words or where admitting the reviewer
        fake = Fake(runs={"/run/code-reviewer": (copy.deepcopy(CLAUDE_RUN), None)})
        rec = build(account(reviewers=[maker_family_reviewer(ownerWord=word)]), fake)
>       assert rec["reviewers"][0]["ran"] == "not-run" and "notIndependent" not in rec["reviewers"][0]
E       AssertionError: assert ('engine-record' == 'not-run'
E         
E         - not-run
E         + engine-record)

/home/user/wt-1796-a/plugins/superheroes/lib/tests/test_review_record.py:2191: AssertionError
_ test_an_incomplete_owners_word_does_not_admit_a_same_family_reviewer[word3] __

word = {'where': 'http://c/9'}

    @pytest.mark.parametrize("word", [
        None, {}, {"words": "go ahead"}, {"where": "http://c/9"}, {"words": "", "where": "http://c/9"},
        {"words": "go ahead", "where": "  "}, {"words": 3, "where": "http://c/9"}])
    def test_an_incomplete_owners_word_does_not_admit_a_same_family_reviewer(word):
        # axis: the owner's-word completeness check; a missing, blank or non-text words or where admitting the reviewer
        fake = Fake(runs={"/run/code-reviewer": (copy.deepcopy(CLAUDE_RUN), None)})
        rec = build(account(reviewers=[maker_family_reviewer(ownerWord=word)]), fake)
>       assert rec["reviewers"][0]["ran"] == "not-run" and "notIndependent" not in rec["reviewers"][0]
E       AssertionError: assert ('engine-record' == 'not-run'
E         
E         - not-run
E         + engine-record)

/home/user/wt-1796-a/plugins/superheroes/lib/tests/test_review_record.py:2191: AssertionError
_ test_an_incomplete_owners_word_does_not_admit_a_same_family_reviewer[word4] __

word = {'words': '', 'where': 'http://c/9'}

    @pytest.mark.parametrize("word", [
        None, {}, {"words": "go ahead"}, {"where": "http://c/9"}, {"words": "", "where": "http://c/9"},
        {"words": "go ahead", "where": "  "}, {"words": 3, "where": "http://c/9"}])
    def test_an_incomplete_owners_word_does_not_admit_a_same_family_reviewer(word):
        # axis: the owner's-word completeness check; a missing, blank or non-text words or where admitting the reviewer
        fake = Fake(runs={"/run/code-reviewer": (copy.deepcopy(CLAUDE_RUN), None)})
        rec = build(account(reviewers=[maker_family_reviewer(ownerWord=word)]), fake)
>       assert rec["reviewers"][0]["ran"] == "not-run" and "notIndependent" not in rec["reviewers"][0]
E       AssertionError: assert ('engine-record' == 'not-run'
E         
E         - not-run
E         + engine-record)

/home/user/wt-1796-a/plugins/superheroes/lib/tests/test_review_record.py:2191: AssertionError
_ test_an_incomplete_owners_word_does_not_admit_a_same_family_reviewer[word5] __

word = {'words': 'go ahead', 'where': '  '}

    @pytest.mark.parametrize("word", [
        None, {}, {"words": "go ahead"}, {"where": "http://c/9"}, {"words": "", "where": "http://c/9"},
        {"words": "go ahead", "where": "  "}, {"words": 3, "where": "http://c/9"}])
    def test_an_incomplete_owners_word_does_not_admit_a_same_family_reviewer(word):
        # axis: the owner's-word completeness check; a missing, blank or non-text words or where admitting the reviewer
        fake = Fake(runs={"/run/code-reviewer": (copy.deepcopy(CLAUDE_RUN), None)})
        rec = build(account(reviewers=[maker_family_reviewer(ownerWord=word)]), fake)
>       assert rec["reviewers"][0]["ran"] == "not-run" and "notIndependent" not in rec["reviewers"][0]
E       AssertionError: assert ('engine-record' == 'not-run'
E         
E         - not-run
E         + engine-record)

/home/user/wt-1796-a/plugins/superheroes/lib/tests/test_review_record.py:2191: AssertionError
_ test_an_incomplete_owners_word_does_not_admit_a_same_family_reviewer[word6] __

word = {'words': 3, 'where': 'http://c/9'}

    @pytest.mark.parametrize("word", [
        None, {}, {"words": "go ahead"}, {"where": "http://c/9"}, {"words": "", "where": "http://c/9"},
        {"words": "go ahead", "where": "  "}, {"words": 3, "where": "http://c/9"}])
    def test_an_incomplete_owners_word_does_not_admit_a_same_family_reviewer(word):
        # axis: the owner's-word completeness check; a missing, blank or non-text words or where admitting the reviewer
        fake = Fake(runs={"/run/code-reviewer": (copy.deepcopy(CLAUDE_RUN), None)})
        rec = build(account(reviewers=[maker_family_reviewer(ownerWord=word)]), fake)
>       assert rec["reviewers"][0]["ran"] == "not-run" and "notIndependent" not in rec["reviewers"][0]
E       AssertionError: assert ('engine-record' == 'not-run'
E         
E         - not-run
E         + engine-record)

/home/user/wt-1796-a/plugins/superheroes/lib/tests/test_review_record.py:2191: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record.py::test_an_incomplete_owners_word_does_not_admit_a_same_family_reviewer[None]
FAILED plugins/superheroes/lib/tests/test_review_record.py::test_an_incomplete_owners_word_does_not_admit_a_same_family_reviewer[word1]
FAILED plugins/superheroes/lib/tests/test_review_record.py::test_an_incomplete_owners_word_does_not_admit_a_same_family_reviewer[word2]
FAILED plugins/superheroes/lib/tests/test_review_record.py::test_an_incomplete_owners_word_does_not_admit_a_same_family_reviewer[word3]
FAILED plugins/superheroes/lib/tests/test_review_record.py::test_an_incomplete_owners_word_does_not_admit_a_same_family_reviewer[word4]
FAILED plugins/superheroes/lib/tests/test_review_record.py::test_an_incomplete_owners_word_does_not_admit_a_same_family_reviewer[word5]
FAILED plugins/superheroes/lib/tests/test_review_record.py::test_an_incomplete_owners_word_does_not_admit_a_same_family_reviewer[word6]
7 failed in 0.59s
```

**Restore:** inverse edit, `            if True or _own_word_ok(r.get("ownerWord")):` → `            if _own_word_ok(r.get("ownerWord")):`

**Restore receipt** (restored line, quoted from `review_record.py:508`):
```
            if _own_word_ok(r.get("ownerWord")):
```

**Raw green:**
```
.......                                                                  [100%]
7 passed in 0.33s
```

## N7 — `reading_next`'s unfilled-seat park

**Guarded element:** `_move_up_blocker`, the `if any(seats[n].get("source") == "unfilled" for n in roster):` line. Axis: a seat
map with an unfilled roster seat parks the lane and never moves it up.

**Detector:** `test_review_record.py::test_reading_next_parks_when_a_roster_seat_is_unfilled`

**Neutralization:** `    if any(seats[n].get("source") == "unfilled" for n in roster):` →
`    if False and any(seats[n].get("source") == "unfilled" for n in roster):`

**Raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
____________ test_reading_next_parks_when_a_roster_seat_is_unfilled ____________

    def test_reading_next_parks_when_a_roster_seat_is_unfilled():
        # axis: the unfilled-seat park; a map with an unfilled roster seat letting the lane move up
        seats = {"a": {"source": "unfilled", "family": "openai"}, "b": SEAT_MAP["seats"]["b"]}
        out = rr.reading_next([NO_READING, NO_READING], _seats(seats=seats), ["anthropic"])
>       assert out == {"next": "park", "reason": "a roster seat in the seat map is unfilled"}
E       AssertionError: assert {'next': 'mov...endent seats'} == {'next': 'par... is unfilled'}
E         
E         Differing items:
E         {'next': 'move-up'} != {'next': 'park'}
E         {'reason': 'two runs do not show a reading and the seat map holds independent seats'} != {'reason': 'a roster seat in the seat map is unfilled'}
E         Use -v to get more diff

/home/user/wt-1796-a/plugins/superheroes/lib/tests/test_review_record.py:2233: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record.py::test_reading_next_parks_when_a_roster_seat_is_unfilled
1 failed in 0.36s
```

**Restore:** inverse edit, `    if False and any(seats[n].get("source") == "unfilled" for n in roster):` →
`    if any(seats[n].get("source") == "unfilled" for n in roster):`

**Restore receipt** (restored line, quoted from `review_record.py:1075`):
```
    if any(seats[n].get("source") == "unfilled" for n in roster):
```

**Raw green:**
```
.                                                                        [100%]
1 passed in 0.32s
```

## N8 — `reading_next`'s maker-family-seat park

**Guarded element:** `_move_up_blocker`, the `if any(seats[n]["family"] in maker_families for n in roster):` line. Axis: a seat
map with a roster seat from a maker's family parks the lane and never moves it up.

**Detector:** `test_review_record.py::test_reading_next_parks_when_a_roster_seat_is_a_makers_family`

**Neutralization:** `    if any(seats[n]["family"] in maker_families for n in roster):` →
`    if False and any(seats[n]["family"] in maker_families for n in roster):`

**Raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
________ test_reading_next_parks_when_a_roster_seat_is_a_makers_family _________

    def test_reading_next_parks_when_a_roster_seat_is_a_makers_family():
        # axis: the maker-family-seat park; a map with a seat from a maker's family letting the lane move up
        seats = {"a": SEAT_MAP["seats"]["a"], "b": {"source": "live", "family": "anthropic"}}
        out = rr.reading_next([NO_READING, NO_READING], _seats(seats=seats), ["anthropic"])
>       assert out == {"next": "park", "reason": "a roster seat in the seat map is from a maker's family"}
E       assert {'next': 'mov...endent seats'} == {'next': 'par...ker's family"}
E         
E         Differing items:
E         {'reason': 'two runs do not show a reading and the seat map holds independent seats'} != {'reason': "a roster seat in the seat map is from a maker's family"}
E         {'next': 'move-up'} != {'next': 'park'}
E         Use -v to get more diff

/home/user/wt-1796-a/plugins/superheroes/lib/tests/test_review_record.py:2240: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record.py::test_reading_next_parks_when_a_roster_seat_is_a_makers_family
1 failed in 0.37s
```

**Restore:** inverse edit, `    if False and any(seats[n]["family"] in maker_families for n in roster):` →
`    if any(seats[n]["family"] in maker_families for n in roster):`

**Restore receipt** (restored line, quoted from `review_record.py:1081`):
```
    if any(seats[n]["family"] in maker_families for n in roster):
```

**Raw green:**
```
.                                                                        [100%]
1 passed in 0.35s
```
