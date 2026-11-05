# Bite-proof record: i2364_calibration_disclosure (#2364) a calibration disclosure is checked against the review record

Detector under proof: `plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py`.
Guarded code: `plugins/superheroes/lib/calibration_disclosure.py` (`contradicted`, `_contradicted_row`, `_mentions`,
`_hit_rows`) and the call in `plugins/superheroes/lib/vet_slot.py` (`_run_verb`, `handback` branch).
Base: `c7444483ecf21893c3a4237685c1fe3339df36a6`. Every neutralization was one targeted edit made with the Edit tool,
undone by the inverse Edit before the next element. No `git checkout`, `restore`, `reset` or `stash` was used.
Command prefix for every run below (worktree root), with `-k` as named per entry:
`timeout 600 scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py -q -p no:cacheprovider --tb=short -k <selector>`.
Captures are verbatim, minus uv's one deprecation-warning line (`UV_NATIVE_TLS`) and, in the red captures, the
`^^^^` caret line pytest prints under a `with` statement. Nothing else was filtered or redacted; each is far under 32 KiB
unless the entry says otherwise.
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
- **The claim word moved from a lack-word list to negation after vet 825.** A clause that names calibration and holds
  any negation or removal word is a claim, after Markdown emphasis characters and typographic apostrophes are
  normalised. Entry 6 (re-run on the new selectors) and entry 8 (the normalisation) prove it. Entry 6 and entry 8 ran
  over both test files; entry 8's red ran with `--tb=line` to keep the capture small. Entry 8's no-break-space case
  stays green under its neutralization (U+00A0 is not a word character, so `\b` already holds around it) and is
  recorded as green, not as a red.
- **Lens-word narrowing and the `rest` fallback were removed on the advisor's 2026-11-05 04:50Z ruling** (a claim clause
  that names no full seat name or row name covers every seat that ran; a lens word such as "test" or "code" never
  narrows a claim). Entry 9 (new) and entry 7 (re-run with the new `_hit_rows(rows, clause, labels)` call) prove the
  result. Entries 3 and 4 were re-run after the change, with their recorded neutralizations; both still go red, and
  their captures below are the post-change ones (the line numbers moved). Entry 9's red shows three of the four
  selected cases red; the first wording of the runner-alias case ("...reviewers. The integration test runner was
  unavailable.") stays green under it, because the claim is the first sentence alone and names no seat at all.
- **Seat terms and the text share one normal form, on the advisor's 06:04Z ruling.** `_normalise` also collapses every
  whitespace run to one space, and `_terms` stores each seat term through the same function. Entry 10 proves the
  collapse, entry 11 the term normalisation, and entry 8 was re-run on the final body. **Entry 11 did not go red and is
  recorded as unproven** (see it below); the order's fixtures were not changed to force a red.
- The claim word also holds `uncalibrat(e|es|ed|ing|ion|ions)`, which the order's word list did not name: "ran
  uncalibrated" holds no other negation or removal word, and the order's text list expects it to refuse.

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
/home/user/wt-2364/plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py:217: in test_f3_an_explicit_seat_that_did_not_run_never_widens_to_the_seats_of_its_lens
    assert cd.contradicted(record, bullet("code-reviewer (round 1) lacked review-crew.md")) == []
E   AssertionError: assert [{'degradatio...CLAUDE.md'}]}] == []
E     
E     Left contains one more item: {'degradation': 'code-reviewer (round 1) lacked review-crew.md', 'seats': [{'name': 'code-reviewer (round 2)', 'line': 'code-reviewer (round 2): read its calibration: core.md, review-crew.md, CLAUDE.md'}]}
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py::test_f3_an_explicit_seat_that_did_not_run_never_widens_to_the_seats_of_its_lens
1 failed, 2 passed, 93 deselected in 0.34s
```

- **Restore:** inverse Edit, `text = text` back to `text = pattern.sub(lambda m: " " * len(m.group(0)), text)`.
- **Restore receipt:** the restored line reads `                text = pattern.sub(lambda m: " " * len(m.group(0)), text)`.
- **Raw green** (`-k test_f3`):

```
...                                                                      [100%]
3 passed, 93 deselected in 0.27s
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
/home/user/wt-2364/plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py:199: in test_f2_a_claim_naming_no_seat_covers_every_seat_and_names_the_contradicted_ones
    assert seats(hits) == [[CODE1]]
E   AssertionError: assert [] == [['code-reviewer (round 1)']]
E     
E     Right contains one more item: ['code-reviewer (round 1)']
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py::test_f2_a_claim_naming_no_seat_covers_every_seat_and_names_the_contradicted_ones
1 failed, 95 deselected in 0.29s
```

- **Restore:** inverse Edit, back to `return [r for r in ran if _contradicted_row(r, labels)]`.
- **Restore receipt:** the restored line reads `        return [r for r in ran if _contradicted_row(r, labels)]`.
- **Raw green** (`-k test_f2`):

```
.                                                                        [100%]
1 passed, 95 deselected in 0.42s
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

- **Axis:** a clause that names calibration (a `_NOUNS` pattern or `_GENERIC`) and holds any negation or removal word
  (`_LACK`) is a claim, with no judgment of which subject the word belongs to; a mixed clause is refused with the
  split-it fix sentence.
- **Neutralization:** `if (specific or _GENERIC.search(clause)) and _LACK.search(clause):` became
  `if (specific or _GENERIC.search(clause)) and False:` (the `and _LACK.search(clause)` operand became `and False`).
- **Raw red** (`-k "dod_headline or vet_825"`, run over both test files; the clause-scope file had no match). The full
  capture is 74504 bytes, over the 32 KiB ceiling, so it was written outside the repository to
  `/tmp/claude-0/-home-user-wt-2364/d18d83ae-01cc-4c43-99d3-350a392c2076/scratchpad/red6.txt` (scratch, not a receipt
  once the session ends). Its first lines and its last lines are quoted here; the 38 failure blocks between them
  (the other `test_vet_825_sentences_refuse` cases, each with a long `where` line) and the first 36 lines of the
  short test summary are elided, about 70 KB:

```
FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF                                 [100%]
=================================== FAILURES ===================================
___ test_dod_headline_stripped_calibration_the_record_grades_read_is_refused ___
/home/user/wt-2364/plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py:114: in test_dod_headline_stripped_calibration_the_record_grades_read_is_refused
    assert result["ok"] is False and result["reason"] == "calibration-disclosure-contradicted"
E   assert (True is False)
___ test_vet_825_sentences_refuse[The code reviewer could not read core.md.] ___
/home/user/wt-2364/plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py:333: in test_vet_825_sentences_refuse
    assert cd.contradicted(rec([row(CODE1), row(SEC1)]), bullet(text))
E   assert []
[... 38 further failure blocks and the first 36 summary lines elided ...]
FAILED plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py::test_vet_825_sentences_refuse[The reviewers lack core.md.]
FAILED plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py::test_vet_825_sentences_refuse[The sanitized view will strip core.md from the reviewers.]
FAILED plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py::test_vet_825_sentences_refuse[The view will withhold core.md from the reviewers.]
FAILED plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py::test_vet_825_sentences_refuse[core.md was not\xa0available to the reviewers.]
40 failed, 54 deselected in 0.84s
```

- **Restore:** inverse Edit, `and False:` back to `and _LACK.search(clause):`.
- **Restore receipt:** the restored line reads `        if (specific or _GENERIC.search(clause)) and _LACK.search(clause):`.
- **Raw green** (`-k "dod_headline or vet_825"`):

```
........................................                                 [100%]
40 passed, 54 deselected in 0.57s
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
  `        hit = {id(r) for clause, labels in claims for r in _hit_rows(rows, clause, labels)}` became
  `        hit = {id(r) for clause, labels in claims for r in _hit_rows(rows, " ".join(c for c, _l in claims), labels)}`
  (every claim clause's text feeds each clause's seat search, so one clause's seats leak into another's). The call
  carries no `rest` argument after the 04:50Z ruling removed the fallback; this entry was re-run with that call line.
- **Raw red** (`-k seat_named_in_one_clause`):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_seat_named_in_one_clause_is_not_checked_against_another_clauses_files _
/home/user/wt-2364/plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py:251: in test_a_seat_named_in_one_clause_is_not_checked_against_another_clauses_files
    assert seats(cd.contradicted(record, bullet(text))) == [[CODE1]]
E   AssertionError: assert [['code-revie...r (round 1)']] == [['code-reviewer (round 1)']]
E     
E     At index 0 diff: ['code-reviewer (round 1)', 'security-reviewer (round 1)'] != ['code-reviewer (round 1)']
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py::test_a_seat_named_in_one_clause_is_not_checked_against_another_clauses_files
1 failed, 95 deselected in 0.30s
```

- **Restore:** inverse Edit, back to the original `_hit_rows(rows, clause, labels)` call.
- **Restore receipt:** the restored line reads
  `        hit = {id(r) for clause, labels in claims for r in _hit_rows(rows, clause, labels)}`.
- **Raw green** (`-k seat_named_in_one_clause`):

```
.                                                                        [100%]
1 passed, 95 deselected in 0.30s
```

## 8. Normalisation (`_normalise`)

- **Axis:** Markdown emphasis characters (underscore, asterisk, tilde, backtick) and typographic apostrophes are
  normalised before the claim test, so formatting cannot hide a claim word or a calibration noun; the bullet is quoted
  as written in the refusal.
- **Neutralization:** the body of `_normalise`, `return re.sub(r"\s+", " ", text.translate(_FORMATTING))` (after the
  06:04Z change; it was `return text.translate(_FORMATTING)` before), became `return text`. Re-run on the final body.
- **Raw red** (`-k vet_825`, run over both test files, with `--tb=line` in place of `--tb=short` to keep the capture
  small; each long `where` line is cut here to its first 160 characters and the cut is marked `[...]`, and the
  failure blocks of the six cases are kept in order). Six cases went red: the two curly-apostrophe cases and the four
  emphasis cases. The no-break-space case stayed green (see the result line, 33 passed), as expected:

```
.......................FF..FFFF........                                  [100%]
=================================== FAILURES ===================================
E   assert []
     +  where [] = <function contradicted at 0x7fd4e0d79580>({'ok': True, 'url': 'https://x/c/900', 'reviewers': [{'name': 'code-reviewer (round 1)', 'ran': 'engine-record', 'cali [...]
     +    and   "Closes #1.\n\n[...]- [costly] The code reviewer didn’t have core.md.\n\n<!-- superheroes:followups none -->\n</details>\n" = bullet('The code reviewer didn’t have core.md.')
/home/user/wt-2364/plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py:382: assert []
E   assert []
     +  [...]- [costly] The code reviewer didn’t get its calibration.[...] = bullet('The code reviewer didn’t get its calibration.')
/home/user/wt-2364/plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py:382: assert []
E   assert []
     +  [...]- [costly] core.md was _stripped_ from the code reviewer.[...] = bullet('core.md was _stripped_ from the code reviewer.')
/home/user/wt-2364/plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py:382: assert []
E   assert []
     +  [...]- [costly] _core.md_ was stripped from the code reviewer.[...] = bullet('_core.md_ was stripped from the code reviewer.')
/home/user/wt-2364/plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py:382: assert []
E   assert []
     +  [...]- [costly] __Calibration__ was stripped from every seat.[...] = bullet('__Calibration__ was stripped from every seat.')
/home/user/wt-2364/plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py:382: assert []
E   assert []
     +  [...]- [costly] core.md was __missing__ for every seat.[...] = bullet('core.md was __missing__ for every seat.')
/home/user/wt-2364/plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py:382: assert []
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py::test_vet_825_sentences_refuse[The code reviewer didn’t have core.md.]
FAILED plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py::test_vet_825_sentences_refuse[The code reviewer didn’t get its calibration.]
FAILED plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py::test_vet_825_sentences_refuse[core.md was _stripped_ from the code reviewer.]
FAILED plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py::test_vet_825_sentences_refuse[_core.md_ was stripped from the code reviewer.]
FAILED plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py::test_vet_825_sentences_refuse[__Calibration__ was stripped from every seat.]
FAILED plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py::test_vet_825_sentences_refuse[core.md was __missing__ for every seat.]
6 failed, 33 passed, 66 deselected in 0.67s
```

- **Restore:** inverse Edit, `return text` back to `return re.sub(r"\s+", " ", text.translate(_FORMATTING))`.
- **Restore receipt:** the restored line reads `    return re.sub(r"\s+", " ", text.translate(_FORMATTING))`.
- **Raw green** (`-k vet_825`):

```
.......................................                                  [100%]
39 passed, 66 deselected in 0.73s
```

## 9. Lens words never narrow a claim (`_NARROWING_LEVELS`, `_mentions`, `_hit_rows`)

- **Axis:** a claim clause narrows to a seat only when it names the seat in full (row name, name without the round,
  seat key or lens name, levels 0 to 3 of `_terms`); a short lens word such as "test" or "code" (level 4) never narrows
  it. Entry 9 is added to the five declared elements by the 04:50Z ruling.
- **Neutralization:** `_NARROWING_LEVELS = 4` became `_NARROWING_LEVELS = 5`.
- **Raw red** (`-k "naming_no_full_seat or runner_mention"`, over `test_calibration_disclosure_2364.py` and
  `test_calibration_disclosure_runner_alias_2364.py`; the `E   assert 'name the seat in full' in "Disclosed ..."` line
  is cut by pytest itself, as printed):

```
FF.F                                                                     [100%]
=================================== FAILURES ===================================
_ test_a_claim_naming_no_full_seat_covers_every_seat[Calibration was stripped from the reviewers. The integration test runner was unavailable.] _
/home/user/wt-2364/plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py:238: in test_a_claim_naming_no_full_seat_covers_every_seat
    assert "name the seat in full" in result["detail"]
E   assert 'name the seat in full' in "Disclosed degradation 'Calibration was stripped from the reviewers. The integration test runner was unavailable.' con... an unrelated lack (a browser, a tool, a runner) in its own bullet or sentence, apart from any mention of calibration."
_ test_a_claim_naming_no_full_seat_covers_every_seat[Calibration was stripped from the reviewers because the integration test runner was unavailable.] _
/home/user/wt-2364/plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py:235: in test_a_claim_naming_no_full_seat_covers_every_seat
    assert seats(cd.contradicted(record, bullet(text))) == [[CODE1]]
E   AssertionError: assert [] == [['code-reviewer (round 1)']]
E     
E     Right contains one more item: ['code-reviewer (round 1)']
E     Use -v to get more diff
_ test_runner_mention_does_not_narrow_a_calibration_claim[Calibration was stripped from the reviewers because the integration test runner was unavailable.] _
/home/user/wt-2364/plugins/superheroes/lib/tests/test_calibration_disclosure_runner_alias_2364.py:58: in test_runner_mention_does_not_narrow_a_calibration_claim
    assert _names(record, text) == [code]
E   AssertionError: assert [] == ['code-reviewer (round 1)']
E     
E     Right contains one more item: 'code-reviewer (round 1)'
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py::test_a_claim_naming_no_full_seat_covers_every_seat[Calibration was stripped from the reviewers. The integration test runner was unavailable.]
FAILED plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py::test_a_claim_naming_no_full_seat_covers_every_seat[Calibration was stripped from the reviewers because the integration test runner was unavailable.]
FAILED plugins/superheroes/lib/tests/test_calibration_disclosure_runner_alias_2364.py::test_runner_mention_does_not_narrow_a_calibration_claim[Calibration was stripped from the reviewers because the integration test runner was unavailable.]
3 failed, 1 passed, 94 deselected in 0.48s
```

- **Restore:** inverse Edit, `_NARROWING_LEVELS = 5` back to `_NARROWING_LEVELS = 4`.
- **Restore receipt:** the restored line reads `_NARROWING_LEVELS = 4`.
- **Raw green** (`-k "naming_no_full_seat or runner_mention"`):

```
....                                                                     [100%]
4 passed, 94 deselected in 0.54s
```

## 10. Whitespace collapse (`_normalise`)

- **Axis:** after the emphasis characters become spaces, every whitespace run collapses to one space, so a seat name
  written with Markdown emphasis or backticks reads as the plain row name and matches in full (and narrows) exactly as
  the plain text does.
- **Neutralization:** `return re.sub(r"\s+", " ", text.translate(_FORMATTING))` became
  `return text.translate(_FORMATTING)` (the `re.sub` wrapper removed).
- **Raw red** (`-k "formatted_seat_name or named_round_is_never"`, `--tb=short`; verbatim minus the uv warning line):

```
.FF.FF                                                                   [100%]
=================================== FAILURES ===================================
_ test_a_formatted_seat_name_matches_like_plain_text[**code-reviewer** (round 1) lacked core.md.] _
/home/user/wt-2364/plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py:258: in test_a_formatted_seat_name_matches_like_plain_text
    assert seats(cd.contradicted(R1R2, bullet(text))) == [["code-reviewer (round 1)"]]
E   AssertionError: assert [] == [['code-reviewer (round 1)']]
E     
E     Right contains one more item: ['code-reviewer (round 1)']
E     Use -v to get more diff
_ test_a_formatted_seat_name_matches_like_plain_text[`code-reviewer` (round 1) lacked core.md.] _
/home/user/wt-2364/plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py:258: in test_a_formatted_seat_name_matches_like_plain_text
    assert seats(cd.contradicted(R1R2, bullet(text))) == [["code-reviewer (round 1)"]]
E   AssertionError: assert [] == [['code-reviewer (round 1)']]
E     
E     Right contains one more item: ['code-reviewer (round 1)']
E     Use -v to get more diff
_ test_a_named_round_is_never_refused_on_another_rounds_grades[**code-reviewer** (round 1) lacked core.md.] _
/home/user/wt-2364/plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py:266: in test_a_named_round_is_never_refused_on_another_rounds_grades
    assert cd.contradicted(record, bullet(text)) == []
E   AssertionError: assert [{'degradatio...CLAUDE.md'}]}] == []
E     
E     Left contains one more item: {'degradation': '**code-reviewer** (round 1) lacked core.md.', 'seats': [{'name': 'code-reviewer (round 2)', 'line': 'code-reviewer (round 2): read its calibration: core.md, review-crew.md, CLAUDE.md'}]}
E     Use -v to get more diff
_ test_a_named_round_is_never_refused_on_another_rounds_grades[`code-reviewer` (round 1) lacked core.md.] _
/home/user/wt-2364/plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py:266: in test_a_named_round_is_never_refused_on_another_rounds_grades
    assert cd.contradicted(record, bullet(text)) == []
E   AssertionError: assert [{'degradatio...CLAUDE.md'}]}] == []
E     
E     Left contains one more item: {'degradation': '`code-reviewer` (round 1) lacked core.md.', 'seats': [{'name': 'code-reviewer (round 2)', 'line': 'code-reviewer (round 2): read its calibration: core.md, review-crew.md, CLAUDE.md'}]}
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py::test_a_formatted_seat_name_matches_like_plain_text[**code-reviewer** (round 1) lacked core.md.]
FAILED plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py::test_a_formatted_seat_name_matches_like_plain_text[`code-reviewer` (round 1) lacked core.md.]
FAILED plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py::test_a_named_round_is_never_refused_on_another_rounds_grades[**code-reviewer** (round 1) lacked core.md.]
FAILED plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py::test_a_named_round_is_never_refused_on_another_rounds_grades[`code-reviewer` (round 1) lacked core.md.]
4 failed, 2 passed, 98 deselected in 0.43s
```

- **Restore:** inverse Edit, `return text.translate(_FORMATTING)` back to
  `return re.sub(r"\s+", " ", text.translate(_FORMATTING))`.
- **Restore receipt:** the restored line reads `    return re.sub(r"\s+", " ", text.translate(_FORMATTING))`.
- **Raw green** (`-k "formatted_seat_name or named_round_is_never"`):

```
......                                                                   [100%]
6 passed, 98 deselected in 0.47s
```

## 11. Term normalisation (`_terms`)

- **Axis:** every seat term is stored through `_normalise(term).strip().lower()`, the same function as the degradation
  text, so a seat name with an emphasis character inside it (a custom seat name with `_`) still matches in full.
- **Neutralization:** `key = _normalise(term).strip().lower()` became `key = term.lower()` (the stored term is the raw
  lowercased term again).
- **Raw red** (`-k "custom_seat_name or formatted_seat_name"`, verbatim minus the uv warning line): **no red.** The
  detector did not go red under this neutralization:

```
.....                                                                    [100%]
5 passed, 99 deselected in 0.31s
```

- **Disclosure: entry 11 is unproven (the order's red did not bite).** Two reasons, both about the fixtures the order
  named, neither relaxed or replaced. (a) The three `formatted_seat_name` texts use `code-reviewer`, whose raw term has
  no emphasis character; once entry 10's collapse is in place, the normalised text already holds the raw row name, so
  they cannot tell raw terms from normalised ones. (b) In `test_a_custom_seat_name_with_an_underscore_matches` the raw
  term `test_role (round 1)` no longer matches the normalised text `test role (round 1)`, so no seat is named, the claim
  covers every seat that ran, and the only row graded `read` is `test_role (round 1)`: the same `[["test_role (round 1)"]]`
  comes out by the widening path (trap 4, second face: the fixture never creates the condition the assertion
  discriminates on). A fixture that would bite grades the underscore seat `unknown` and the other seat `read`, so a
  named-seat match yields `[]` and the unmatched widening yields the other seat. The order forbids inventing a test to
  force a red, so this is reported, not fixed.
- **Restore:** inverse Edit, `key = term.lower()` back to `key = _normalise(term).strip().lower()`.
- **Restore receipt:** the restored line reads `                key = _normalise(term).strip().lower()`.
- **Raw green** (`-k "custom_seat_name or formatted_seat_name"`):

```
.....                                                                    [100%]
5 passed, 99 deselected in 0.37s
```
