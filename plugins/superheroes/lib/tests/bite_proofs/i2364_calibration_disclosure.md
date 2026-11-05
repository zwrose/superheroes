# Bite-proof record: i2364_calibration_disclosure (#2364) a calibration disclosure is checked against the review record

Detector under proof: `plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py`.
Guarded code: `plugins/superheroes/lib/calibration_disclosure.py` (`contradicted`, `_contradicted_row`, `_mentions`,
`_hit_rows`) and the call in `plugins/superheroes/lib/vet_slot.py` (`_run_verb`, `handback` branch).
Base: `c7444483ecf21893c3a4237685c1fe3339df36a6`. Every neutralization was one targeted edit made with the Edit tool,
undone by the inverse Edit before the next element. No `git checkout`, `restore`, `reset` or `stash` was used.
Command prefix for every run below (worktree root), with `-k` as named per entry:
`timeout 600 scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py -q -p no:cacheprovider --tb=short -k <selector>`.
Captures are verbatim, minus uv's one deprecation-warning line (`UV_NATIVE_TLS`) and, in the red captures, the
`^^^^` caret line pytest prints under a `with` statement. Nothing else was filtered or redacted; each is far under 32 KiB.
The production sites cite this record with `# axis:` comments. Restore receipts are the restored production line,
quoted; the whole-file `git status --porcelain` is reported in the dispatch return, not here.

The guarded-element set is the five the order declared.

Disclosures:
- **Element 3: the order's named red did not bite, and the red below is a different case.** The order named
  "code-reviewer (round 2) lacked review-crew.md" as the red. Under the neutralization (no blanking) that case stayed
  green (`-k test_f3` under the same neutralization, run before the new test existed, printed
  `..` then `2 passed, 24 deselected in 0.24s`). Reason: an
  explicit mention (`code-reviewer (round 2)`, one row) and its widened mention (`code-reviewer`, two rows) are nested
  row sets, and hits are a union across mentions, so un-blanked widening can only add a hit when the explicit target
  yields no targets while its lens-mates read. The fixture of that case never creates that condition (trap 4, second
  face). The cure was a new fixture, `test_f3_an_explicit_seat_that_did_not_run_never_widens_to_the_seats_of_its_lens`
  (round 1 did not run, round 2 read, the bullet names round 1), not a relaxed assertion; it is the red below.
  The slice case (`code-reviewer:api`) stays green under this neutralization, as the order expected.
- **Element 1: the through-`handback` case (7b) is not a red under this neutralization.** `check_leftovers` runs first
  on the same record and refuses a missing record `review-record-unreadable` before the calibration check is
  reached, so 7b cannot discriminate the guarded raise (unreachable through this entry point). The unit test 7a
  (`calibration_disclosure.contradicted` on `{"ok": False, ...}`) is the proof that bites. Through `handback`, rule 1's
  raise is reachable only for a record that `check_leftovers` accepts but `contradicted` rejects, and no such
  record exists, so no `run_verb` test of rule 1 is possible; 7c reaches the calibration check, but through rule 5's
  `reviewers` raise, not rule 1's.
- The `reviewers`-malformed raise (rule 5's `Unreadable("the record's reviewers list is missing or malformed")`) is a
  sixth, undeclared guarded element and was **not** neutralized (the command budget was spent on the declared five):
  it is pinned by `test_7c_*` but **unproven by a red run**.
- Element 3's selector is `test_f3`, which selects three tests (most specific wins, the not-run explicit seat, the
  slice seat); the red is the not-run test alone.
- One extra invocation of the budget's `-k` runs was spent on the invalid element-3 attempt above.
- **The claim test was reworked after review, on the advisor's ruling** (the subject judgment was removed: a clause that
  names calibration and holds any lack word is a claim). Entries 6 and 7 below prove the reworked parts; entries 1 to 5
  guard code that rework did not touch. The two reworked entries ran on the selectors named in them, the same command
  prefix plus the clause-scope test file `plugins/superheroes/lib/tests/test_calibration_disclosure_clause_scope_2364.py`
  (entry 7's re-run, below, ran on the main test file alone).
- **Element 7 is proven by a red run.** The first neutralization of entry 7 edited `_hit_rows`'s `rest` fallback, which
  holds only a bullet's non-claim clauses, so it could not leak one claim clause's seats into another and no test could
  bite. Entry 7 was re-run with a neutralization at the call site that does leak, and with the new test
  `test_a_seat_named_in_one_clause_is_not_checked_against_another_clauses_files`; that test goes red under it.

## 1. Record readability (`contradicted`, rule 1)

- **Axis:** a record read that did not succeed (not a dict, or `ok` not `True`) raises `Unreadable`, never passes,
  even when the body carries no calibration disclosure.
- **Neutralization:** `raise Unreadable(detail or "the review record read did not succeed")` became `return []`.
- **Raw red** (`-k "test_7a or test_7b"`):

```
F.                                                                       [100%]
=================================== FAILURES ===================================
_____ test_7a_a_record_read_that_did_not_succeed_raises_even_with_no_claim _____
/home/user/wt-2364/plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py:157: in test_7a_a_record_read_that_did_not_succeed_raises_even_with_no_claim
    with pytest.raises(cd.Unreadable, match="review-record-missing"):
E   Failed: DID NOT RAISE Unreadable
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py::test_7a_a_record_read_that_did_not_succeed_raises_even_with_no_claim
1 failed, 1 passed, 24 deselected in 0.30s
```

- **Restore:** inverse Edit, `return []` back to `raise Unreadable(detail or "the review record read did not succeed")`.
- **Restore receipt:** the restored line reads `        raise Unreadable(detail or "the review record read did not succeed")`.
- **Raw green** (`-k "test_7a or test_7b"`):

```
..                                                                       [100%]
2 passed, 24 deselected in 0.29s
```

## 2. The contradicted predicate (`_contradicted_row`, rule 5)

- **Axis:** a row is contradicted only when it is an engine-record row whose every entry for the claimed labels is
  `read`; the refusal turns on this and on nothing else.
- **Neutralization:** `return bool(held) and all(e["read"] == "read" for e in held)` became `return False`.
- **Raw red** (`-k "dod_headline or incident_wording"`):

```
FF                                                                       [100%]
=================================== FAILURES ===================================
___ test_dod_headline_stripped_calibration_the_record_grades_read_is_refused ___
/home/user/wt-2364/plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py:113: in test_dod_headline_stripped_calibration_the_record_grades_read_is_refused
    assert result["ok"] is False and result["reason"] == "calibration-disclosure-contradicted"
E   assert (True is False)
_________________ test_incident_wording_names_all_three_seats __________________
/home/user/wt-2364/plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py:122: in test_incident_wording_names_all_three_seats
    assert result["ok"] is False and result["reason"] == "calibration-disclosure-contradicted"
E   assert (True is False)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py::test_dod_headline_stripped_calibration_the_record_grades_read_is_refused
FAILED plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py::test_incident_wording_names_all_three_seats
2 failed, 24 deselected in 0.27s
```

- **Restore:** inverse Edit, `return False` (the one directly above the blank line after `_contradicted_row`) back to
  `return bool(held) and all(e["read"] == "read" for e in held)`.
- **Restore receipt:** the restored line reads `    return bool(held) and all(e["read"] == "read" for e in held)`.
- **Raw green** (`-k "dod_headline or incident_wording"`):

```
..                                                                       [100%]
2 passed, 24 deselected in 0.25s
```

## 3. Span blanking (`_mentions`, rule 6)

- **Axis:** a matched seat term's span is blanked before the next term, so an explicit target never widens through a
  less specific term (a seat that did not run, named explicitly, does not reach its lens-mates that read).
- **Neutralization:** `text = pattern.sub(lambda m: " " * len(m.group(0)), text)` became `text = text`.
- **Raw red** (`-k test_f3`, with `test_f3_an_explicit_seat_that_did_not_run_never_widens_to_the_seats_of_its_lens` added):

```
.F.                                                                      [100%]
=================================== FAILURES ===================================
_ test_f3_an_explicit_seat_that_did_not_run_never_widens_to_the_seats_of_its_lens _
/home/user/wt-2364/plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py:214: in test_f3_an_explicit_seat_that_did_not_run_never_widens_to_the_seats_of_its_lens
    assert cd.contradicted(record, bullet("code-reviewer (round 1) lacked review-crew.md")) == []
E   AssertionError: assert [{'degradatio...CLAUDE.md'}]}] == []
E     
E     Left contains one more item: {'degradation': 'code-reviewer (round 1) lacked review-crew.md', 'seats': [{'name': 'code-reviewer (round 2)', 'line': 'code-reviewer (round 2): read its calibration: core.md, review-crew.md, CLAUDE.md'}]}
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py::test_f3_an_explicit_seat_that_did_not_run_never_widens_to_the_seats_of_its_lens
1 failed, 2 passed, 24 deselected in 0.36s
```

- **Restore:** inverse Edit, `text = text` back to `text = pattern.sub(lambda m: " " * len(m.group(0)), text)`.
- **Restore receipt:** the restored line reads `                text = pattern.sub(lambda m: " " * len(m.group(0)), text)`.
- **Raw green** (`-k test_f3`):

```
...                                                                      [100%]
3 passed, 24 deselected in 0.26s
```

## 4. The whole-panel branch (`_hit_rows`, rule 7)

- **Axis:** a claim that names no seat covers every seat, so each contradicted ran row is a hit on its own, not only
  when the whole panel is contradicted.
- **Neutralization:** `return [r for r in ran if _contradicted_row(r, labels)]` became
  `return ran if ran and all(_contradicted_row(r, labels) for r in ran) else []`.
- **Raw red** (`-k test_f2`):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_f2_a_claim_naming_no_seat_covers_every_seat_and_names_the_contradicted_ones _
/home/user/wt-2364/plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py:198: in test_f2_a_claim_naming_no_seat_covers_every_seat_and_names_the_contradicted_ones
    assert seats(hits) == [[CODE1]]
E   AssertionError: assert [] == [['code-reviewer (round 1)']]
E     
E     Right contains one more item: ['code-reviewer (round 1)']
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py::test_f2_a_claim_naming_no_seat_covers_every_seat_and_names_the_contradicted_ones
1 failed, 26 deselected in 0.33s
```

- **Restore:** inverse Edit, back to `return [r for r in ran if _contradicted_row(r, labels)]`.
- **Restore receipt:** the restored line reads `        return [r for r in ran if _contradicted_row(r, labels)]`.
- **Raw green** (`-k test_f2`):

```
.                                                                        [100%]
1 passed, 26 deselected in 0.27s
```

## 5. The handback wiring call (`vet_slot.py` `_run_verb`)

- **Axis:** `vet_slot.py handback --pr` runs the calibration-disclosure check after the leftover check, so a
  contradicted disclosure refuses `calibration-disclosure-contradicted` instead of passing.
- **Neutralization:** `check_calibration_disclosures(pr, repo, body, comments)` became
  `# check_calibration_disclosures(pr, repo, body, comments)` (commented out).
- **Raw red** (`-k dod_headline`):

```
F                                                                        [100%]
=================================== FAILURES ===================================
___ test_dod_headline_stripped_calibration_the_record_grades_read_is_refused ___
/home/user/wt-2364/plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py:113: in test_dod_headline_stripped_calibration_the_record_grades_read_is_refused
    assert result["ok"] is False and result["reason"] == "calibration-disclosure-contradicted"
E   assert (True is False)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py::test_dod_headline_stripped_calibration_the_record_grades_read_is_refused
1 failed, 26 deselected in 0.26s
```

- **Restore:** inverse Edit, `# check_calibration_disclosures(pr, repo, body, comments)` back to
  `check_calibration_disclosures(pr, repo, body, comments)`.
- **Restore receipt:** the restored lines read `            check_leftovers(pr, repo, body, comments)`, the `# axis:` comment, then
  `            check_calibration_disclosures(pr, repo, body, comments)`.
- **Raw green** (`-k dod_headline`):

```
.                                                                        [100%]
1 passed, 26 deselected in 0.27s
```

## 6. The claim test (`_claims`)

- **Axis:** a clause that names calibration (a `_NOUNS` pattern or `_GENERIC`) and holds any lack word is a claim, with
  no judgment of which subject the lack word belongs to; a mixed clause is refused with the split-it fix sentence.
- **Neutralization:** `if (specific or _GENERIC.search(clause)) and _LACK.search(clause):` became
  `if (specific or _GENERIC.search(clause)) and False:` (the `and _LACK.search(clause)` operand became `and False`).
- **Raw red** (`-k "dod_headline or mixed_clause"`, run over both test files; the clause-scope file had no match):

```
FFFFFFFF                                                                 [100%]
=================================== FAILURES ===================================
___ test_dod_headline_stripped_calibration_the_record_grades_read_is_refused ___
/home/user/wt-2364/plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py:114: in test_dod_headline_stripped_calibration_the_record_grades_read_is_refused
    assert result["ok"] is False and result["reason"] == "calibration-disclosure-contradicted"
E   assert (True is False)
_ test_a_mixed_clause_is_refused_by_the_ruling[The code reviewer read core.md and the browser was missing.] _
/home/user/wt-2364/plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py:244: in test_a_mixed_clause_is_refused_by_the_ruling
    assert seats(cd.contradicted(rec([row(CODE1)]), bullet(text))) == [[CODE1]]
E   AssertionError: assert [] == [['code-reviewer (round 1)']]
E     
E     Right contains one more item: ['code-reviewer (round 1)']
E     Use -v to get more diff
_ test_a_mixed_clause_is_refused_by_the_ruling[The code reviewer read core.md because the browser was unavailable.] _
/home/user/wt-2364/plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py:244: in test_a_mixed_clause_is_refused_by_the_ruling
    assert seats(cd.contradicted(rec([row(CODE1)]), bullet(text))) == [[CODE1]]
E   AssertionError: assert [] == [['code-reviewer (round 1)']]
E     
E     Right contains one more item: ['code-reviewer (round 1)']
E     Use -v to get more diff
_____________ test_a_mixed_clause_is_refused_by_the_ruling[text2] ______________
/home/user/wt-2364/plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py:244: in test_a_mixed_clause_is_refused_by_the_ruling
    assert seats(cd.contradicted(rec([row(CODE1)]), bullet(text))) == [[CODE1]]
E   AssertionError: assert [] == [['code-reviewer (round 1)']]
E     
E     Right contains one more item: ['code-reviewer (round 1)']
E     Use -v to get more diff
_ test_a_mixed_clause_is_refused_by_the_ruling[The integration-test runner was unavailable and the code reviewer read core.md instead.] _
/home/user/wt-2364/plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py:244: in test_a_mixed_clause_is_refused_by_the_ruling
    assert seats(cd.contradicted(rec([row(CODE1)]), bullet(text))) == [[CODE1]]
E   AssertionError: assert [] == [['code-reviewer (round 1)']]
E     
E     Right contains one more item: ['code-reviewer (round 1)']
E     Use -v to get more diff
_ test_a_mixed_clause_is_refused_by_the_ruling[No tests ran and the code reviewer consulted core.md.] _
/home/user/wt-2364/plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py:244: in test_a_mixed_clause_is_refused_by_the_ruling
    assert seats(cd.contradicted(rec([row(CODE1)]), bullet(text))) == [[CODE1]]
E   AssertionError: assert [] == [['code-reviewer (round 1)']]
E     
E     Right contains one more item: ['code-reviewer (round 1)']
E     Use -v to get more diff
_ test_a_mixed_clause_is_refused_by_the_ruling[The sanitized view did not remove core.md from the code reviewer.] _
/home/user/wt-2364/plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py:244: in test_a_mixed_clause_is_refused_by_the_ruling
    assert seats(cd.contradicted(rec([row(CODE1)]), bullet(text))) == [[CODE1]]
E   AssertionError: assert [] == [['code-reviewer (round 1)']]
E     
E     Right contains one more item: ['code-reviewer (round 1)']
E     Use -v to get more diff
_ test_a_mixed_clause_is_refused_by_the_ruling[The code reviewer was not only missing core.md but also review-crew.md.] _
/home/user/wt-2364/plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py:244: in test_a_mixed_clause_is_refused_by_the_ruling
    assert seats(cd.contradicted(rec([row(CODE1)]), bullet(text))) == [[CODE1]]
E   AssertionError: assert [] == [['code-reviewer (round 1)']]
E     
E     Right contains one more item: ['code-reviewer (round 1)']
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py::test_dod_headline_stripped_calibration_the_record_grades_read_is_refused
FAILED plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py::test_a_mixed_clause_is_refused_by_the_ruling[The code reviewer read core.md and the browser was missing.]
FAILED plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py::test_a_mixed_clause_is_refused_by_the_ruling[The code reviewer read core.md because the browser was unavailable.]
FAILED plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py::test_a_mixed_clause_is_refused_by_the_ruling[text2]
FAILED plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py::test_a_mixed_clause_is_refused_by_the_ruling[The integration-test runner was unavailable and the code reviewer read core.md instead.]
FAILED plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py::test_a_mixed_clause_is_refused_by_the_ruling[No tests ran and the code reviewer consulted core.md.]
FAILED plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py::test_a_mixed_clause_is_refused_by_the_ruling[The sanitized view did not remove core.md from the code reviewer.]
FAILED plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py::test_a_mixed_clause_is_refused_by_the_ruling[The code reviewer was not only missing core.md but also review-crew.md.]
8 failed, 45 deselected in 0.53s
```

- **Restore:** inverse Edit, `and False:` back to `and _LACK.search(clause):`.
- **Restore receipt:** the restored line reads `        if (specific or _GENERIC.search(clause)) and _LACK.search(clause):`.
- **Raw green** (`-k "dod_headline or mixed_clause"`):

```
........                                                                 [100%]
8 passed, 45 deselected in 3.75s
```

## 7. Per-clause scope (`contradicted`, the `_hit_rows` call)

- **Axis:** a seat named only in one claim clause is never checked against another claim clause's files, so each claim
  clause is searched with its own text alone.
- **Detector:** `test_a_seat_named_in_one_clause_is_not_checked_against_another_clauses_files` (rows: code-reviewer
  reads all three files; security-reviewer reads core.md and CLAUDE.md and grades review-crew.md unknown; text:
  "code-reviewer (round 1) lacked core.md; security-reviewer (round 1) lacked review-crew.md."; expects only the code
  seat). It was run once against the unneutralized code first and passed:
  `1 passed, 52 deselected in 0.29s`.
- **Neutralization:** in `contradicted`, the line
  `        hit = {id(r) for clause, labels in claims for r in _hit_rows(rows, clause, rest, labels)}` became
  `        hit = {id(r) for clause, labels in claims for r in _hit_rows(rows, " ".join(c for c, _l in claims), rest, labels)}`
  (every claim clause's text feeds each clause's seat search, so one clause's seats leak into another's). This replaces
  the earlier neutralization of `_hit_rows`'s `rest` fallback, which could not leak between claim clauses and so could
  not bite.
- **Raw red** (`-k seat_named_in_one_clause`):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_seat_named_in_one_clause_is_not_checked_against_another_clauses_files _
/home/user/wt-2364/plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py:231: in test_a_seat_named_in_one_clause_is_not_checked_against_another_clauses_files
    assert seats(cd.contradicted(record, bullet(text))) == [[CODE1]]
E   AssertionError: assert [['code-revie...r (round 1)']] == [['code-reviewer (round 1)']]
E     
E     At index 0 diff: ['code-reviewer (round 1)', 'security-reviewer (round 1)'] != ['code-reviewer (round 1)']
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py::test_a_seat_named_in_one_clause_is_not_checked_against_another_clauses_files
1 failed, 52 deselected in 0.29s
```

- **Restore:** inverse Edit, back to the original `_hit_rows(rows, clause, rest, labels)` call.
- **Restore receipt:** the restored line reads
  `        hit = {id(r) for clause, labels in claims for r in _hit_rows(rows, clause, rest, labels)}`.
- **Raw green** (`-k seat_named_in_one_clause`):

```
.                                                                        [100%]
1 passed, 52 deselected in 0.39s
```
