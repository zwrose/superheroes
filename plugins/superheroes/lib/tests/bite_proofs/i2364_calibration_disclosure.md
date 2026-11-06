# Bite-proof record: i2364_calibration_disclosure (#2364) a calibration disclosure is checked against the review record

Detector under proof: `plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py`.
Guarded code: `plugins/superheroes/lib/calibration_disclosure.py` (`problems`, `_valid_markers`, `_unmarked_text`,
`_mentions_calibration`, `_contradicts`, `_normalise`, `_EXEMPT`) and the call in `plugins/superheroes/lib/vet_slot.py`
(`_run_verb`, `handback` branch, through `check_calibration_disclosures`). At the 02:13Z marker rewrite `contradicted`,
`_contradicted_row`, `_claims`, `_terms`, `_mentions`, `_hit_rows`, `_lens_word_only` and the narrowing levels were
removed; entries 2, 3, 4, 7, 9 and 11 guard that removed code and are retired (see each).
Base: `c7444483ecf21893c3a4237685c1fe3339df36a6`. Every neutralization was one targeted edit made with the Edit tool,
undone by the inverse Edit before the next element. No `git checkout`, `restore`, `reset` or `stash` was used.
Command prefix for every run below (worktree root), with `-k` as named per entry:
`timeout 600 scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py -q -p no:cacheprovider --tb=short -k <selector>`.
Captures are verbatim, minus uv's one deprecation-warning line (`UV_NATIVE_TLS`) and, in the red captures, the
`^^^^` caret line pytest prints under a `with` statement. Nothing else was filtered or redacted; each is far under 32 KiB
unless the entry says otherwise.
The production sites cite this record with `# axis:` comments. Restore receipts are the restored production line,
quoted; the whole-file `git status --porcelain` is reported in the dispatch return, not here.

The guarded-element set is the five the order declared, then the entries added by later rulings (6 to 13), then, at the
02:13Z marker rewrite (owner ruling "31 b"), entries 14 to 19: marker validity (14), the absent row (15), per-file
contradiction (16), the marker masked and only the marker (17), the unmarked refusal (18) and engine-record-only
contradiction (19). Entries 2, 3, 4, 7, 9 and 11 are retired. Entries 1, 5, 6, 8, 10, 12 and 13 were re-run at the
marker rewrite (a dated block at the end of each).

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
  collapse, entry 11 the term normalisation, and entry 8 was re-run on the final body. **Entry 11 is proven by
  `test_a_custom_seat_name_with_an_underscore_narrows_to_that_seat`** (see it below); the first fixture for it did not
  bite, and this test replaced it as the proof.
- **Doctrine-prescribed disclosures are masked before the claim test, on the advisor's 07:15Z vet 826 order.** The
  show-it surface declaration (`core.md has no ## Show-it surface`, `the project's calibration declares no show-it
  surface`, any bare `show-it surface`) and the stock phrases `calibrated verify`, `calibrated model` and `calibrated
  command` are masked by `_EXEMPT` before the nouns and the lack words are read, so the plugin's own required
  disclosure never reads as a claim. Entry 12 proves it. **The model-identifier reading of the second exemption
  (`calibrated` directly followed by one token holding a digit, such as `gpt-6.1-sol`) is the builder's
  interpretation**, needed so the order's fourth text passes; it is not in the advisor's order text.
- **The identifier form of the exemption was narrowed on the advisor's 11:44Z vet 827 order.** The identifier form needs
  "the" before `calibrated` and a letter-led token that holds a digit (`\bthe\s+calibrated\s+[a-z]\S*\d\S*`); the old
  `calibrated` plus any token with a digit also masked lack claims such as "was not calibrated 2 rounds in a row".
  Entry 13 proves it. The same order made the verify/model/command separator `[\s-]+` (so "calibrated-command" is
  exempt) and added `with` to the declaration verbs (so "a core.md with no ## Show-it surface" is exempt); those two
  edits are pinned by `test_more_doctrine_wordings_pass` and carry no separate entry. Two known shapes still pass and
  are the orchestrator's named residuals, not patched and not tested here: "The code reviewer ran without the calibrated
  gpt-6.1-sol." and "The reviewer ran without calibrated-command."
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

**Re-run at the marker rewrite (02:13Z):** selector `-k "test_7a or test_7b"` on `test_calibration_disclosure_2364.py`
(now `test_7a_..._even_with_no_marker`, `test_7b_...`). Neutralization: `raise Unreadable(detail or "the review record
read did not succeed")` in `problems` became `return []`. The red is 7a alone, as before: 7b is the unreachable case
(`check_leftovers` refuses first), see Disclosures. Raw red (verbatim minus the uv warning line):

```
F.                                                                       [100%]
=================================== FAILURES ===================================
____ test_7a_a_record_read_that_did_not_succeed_raises_even_with_no_marker _____
/home/user/wt-2364/plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py:232: in test_7a_a_record_read_that_did_not_succeed_raises_even_with_no_marker
    with pytest.raises(cd.Unreadable, match="review-record-missing"):
         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E   Failed: DID NOT RAISE Unreadable
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py::test_7a_a_record_read_that_did_not_succeed_raises_even_with_no_marker
1 failed, 1 passed, 123 deselected in 0.45s
```

Restore: inverse Edit. Restore receipt: line 152 reads `        raise Unreadable(detail or "the review record read did not succeed")`. Raw green:

```
..                                                                       [100%]
2 passed, 123 deselected in 0.34s
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

**Retired (02:13Z scope order):** the guarded code was removed when the marker replaced free-prose seat narrowing; this entry's runs are history.

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

**Retired (02:13Z scope order):** the guarded code was removed when the marker replaced free-prose seat narrowing; this entry's runs are history.

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

**Retired (02:13Z scope order):** the guarded code was removed when the marker replaced free-prose seat narrowing; this entry's runs are history.

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

**Re-run at the marker rewrite (02:13Z):** selector `-k dod_headline` (now `test_dod_headline_unmarked_is_refused`, two
cases, expecting `calibration-disclosure-unmarked`). Neutralization: in `vet_slot.py`, `check_calibration_disclosures(pr,
repo, body, comments)` became `# check_calibration_disclosures(pr, repo, body, comments)`. Raw red (verbatim minus the
uv warning line):

```
FF                                                                       [100%]
=================================== FAILURES ===================================
_ test_dod_headline_unmarked_is_refused[Calibration was stripped from the reviewers.] _
/home/user/wt-2364/plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py:124: in test_dod_headline_unmarked_is_refused
    assert result["ok"] is False and result["reason"] == "calibration-disclosure-unmarked"
E   assert (True is False)
_ test_dod_headline_unmarked_is_refused[Calibration (CLAUDE.md, .claude) was stripped from the reviewers by the sanitized view.] _
/home/user/wt-2364/plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py:124: in test_dod_headline_unmarked_is_refused
    assert result["ok"] is False and result["reason"] == "calibration-disclosure-unmarked"
E   assert (True is False)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py::test_dod_headline_unmarked_is_refused[Calibration was stripped from the reviewers.]
FAILED plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py::test_dod_headline_unmarked_is_refused[Calibration (CLAUDE.md, .claude) was stripped from the reviewers by the sanitized view.]
2 failed, 123 deselected in 0.33s
```

Restore: inverse Edit. Restore receipt: `vet_slot.py` lines 712 to 714 read `            check_leftovers(pr, repo, body, comments)`, the `# axis:` comment, then
`            check_calibration_disclosures(pr, repo, body, comments)`. Raw green:

```
..                                                                       [100%]
2 passed, 123 deselected in 0.29s
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

**Re-run at the marker rewrite (02:13Z):** the claim test is now `_mentions_calibration`; selector `-k "dod_headline or
vet_825"` (42 selected). Neutralization: in `_mentions_calibration`, `... or _GENERIC.search(masked)) and
_LACK.search(masked):` became `... or _GENERIC.search(masked)) and False:`. Run with `--tb=line`, the output sent to the
scratchpad file `/tmp/claude-0/-home-user-wt-2364/02a0e535-3312-42ee-8c4d-d7309443fd11/scratchpad/red6.txt` (19835
bytes, under the ceiling; scratch, not a receipt once the session ends), so the quote below is the first lines and the
last three lines, with the remaining failure blocks and the earlier summary lines elided (about 18 KB of the 19835
bytes). Raw red:

```
FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF                               [100%]
=================================== FAILURES ===================================
E   assert (True is False)
/home/user/wt-2364/plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py:124: assert (True is False)
E   assert (True is False)
/home/user/wt-2364/plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py:124: assert (True is False)
E   AssertionError: assert [] == ['calibration...ure-unmarked']
      
      Right contains one more item: 'calibration-disclosure-unmarked'
      Use -v to get more diff
/home/user/wt-2364/plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py:425: AssertionError: assert [] == ['calibration...ure-unmarked']
[... further failure blocks and summary lines elided ...]
FAILED plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py::test_vet_825_sentences_refuse[The view will withhold core.md from the reviewers.]
FAILED plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py::test_vet_825_sentences_refuse[core.md was not available to the reviewers.]
FAILED plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py::test_vet_825_sentences_refuse[core.md was left  out of the reviewers' view.]
42 failed, 83 deselected in 0.44s
```

Restore: inverse Edit. Restore receipt: line 129 reads `        if (any(noun.search(masked) for noun in _NOUNS) or _GENERIC.search(masked)) and _LACK.search(masked):`. Raw green:

```
..........................................                               [100%]
42 passed, 83 deselected in 0.47s
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

**Retired (02:13Z scope order):** the guarded code was removed when the marker replaced free-prose seat narrowing; this entry's runs are history.

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

**Re-run at the marker rewrite (02:13Z):** selector `-k vet_825` on the main test file (40 cases; the cases now expect
`calibration-disclosure-unmarked`). Neutralization: the body of `_normalise`, `return re.sub(r"\s+", " ",
text.translate(_FORMATTING))`, became `return text`. Run with `--tb=line` and the lines cut to 200 columns. Seven cases
went red: the two curly-apostrophe cases, the four emphasis cases, and the new `core.md was left  out of the reviewers'
view.` case (two spaces, which only the whitespace collapse reads as `left out`). The no-break-space case stays green
(U+00A0 is not a word character), as in the earlier run. Raw red (verbatim minus the uv warning line; six of the seven
failure blocks, which are identical in shape, are elided):

```
.......................FF..FFFF........F                                 [100%]
=================================== FAILURES ===================================
E   AssertionError: assert [] == ['calibration...ure-unmarked']
      
      Right contains one more item: 'calibration-disclosure-unmarked'
      Use -v to get more diff
/home/user/wt-2364/plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py:425: AssertionError: assert [] == ['calibration...ure-unmarked']
[... the other six failure blocks elided; each is the same four lines plus the location line ...]
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py::test_vet_825_sentences_refuse[The code reviewer didn’t have core.md.]
FAILED plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py::test_vet_825_sentences_refuse[The code reviewer didn’t get its calibration.]
FAILED plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py::test_vet_825_sentences_refuse[core.md was _stripped_ from the code reviewer.]
FAILED plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py::test_vet_825_sentences_refuse[_core.md_ was stripped from the code reviewer.]
FAILED plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py::test_vet_825_sentences_refuse[__Calibration__ was stripped from every seat.]
FAILED plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py::test_vet_825_sentences_refuse[core.md was __missing__ for every seat.]
FAILED plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py::test_vet_825_sentences_refuse[core.md was left  out of the reviewers' view.]
7 failed, 33 passed, 85 deselected in 0.46s
```

Restore: inverse Edit. Restore receipt: line 97 reads `    return re.sub(r"\s+", " ", text.translate(_FORMATTING))`. Raw green:

```
........................................                                 [100%]
40 passed, 85 deselected in 0.43s
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

**Retired (02:13Z scope order):** the guarded code was removed when the marker replaced free-prose seat narrowing; this entry's runs are history.

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

**Re-run at the marker rewrite (02:13Z):** the earlier selector's tests (`formatted_seat_name`, `named_round_is_never`)
were deleted with the seat narrowing, so the proving case is new: `core.md was left  out of the reviewers' view.` (two
spaces) in `test_vet_825_sentences_refuse`, because `_LACK` reads `left out` with one space and only the collapse
produces it. Selector `-k "vet_825 and left"`. Neutralization: `return re.sub(r"\s+", " ", text.translate(_FORMATTING))`
became `return text.translate(_FORMATTING)`. Raw red (verbatim minus the uv warning line):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_vet_825_sentences_refuse[core.md was left  out of the reviewers' view.] _
/home/user/wt-2364/plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py:425: in test_vet_825_sentences_refuse
    assert reasons(cd.problems(rec([row(CODE1), row(SEC1)]), bullet(text))) == [cd.REASON_UNMARKED]
E   AssertionError: assert [] == ['calibration...ure-unmarked']
E     
E     Right contains one more item: 'calibration-disclosure-unmarked'
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py::test_vet_825_sentences_refuse[core.md was left  out of the reviewers' view.]
1 failed, 124 deselected in 0.31s
```

Restore: inverse Edit. Restore receipt: line 97 reads `    return re.sub(r"\s+", " ", text.translate(_FORMATTING))`. Raw green:

```
.                                                                        [100%]
1 passed, 124 deselected in 0.30s
```

## 11. Term normalisation (`_terms`)

- **Axis:** every seat term is stored through `_normalise(term).strip().lower()`, the same function as the degradation
  text, so a seat name with an emphasis character inside it (a custom seat name with `_`) still matches in full.
- **Neutralization:** `key = _normalise(term).strip().lower()` became `key = term.lower()` (the stored term is the raw
  lowercased term again).
- **Proving test:** `test_a_custom_seat_name_with_an_underscore_narrows_to_that_seat` (two texts: the plain and the
  backticked `test_role`). The record holds `test_role (round 1)` graded all `unknown` and `code-reviewer (round 1)`
  graded all `read`. Named in full, the claim narrows to the test seat, which is `unknown` and so not contradicted, and
  the result is `[]`. If the name fails to match, the claim widens to every seat that ran and the `read` code seat is
  listed. The earlier `test_a_custom_seat_name_with_an_underscore_matches` did not discriminate (its widening path gave
  the same answer); this test does.
- **Raw red** (`-k custom_seat_name_with_an_underscore_narrows`, verbatim minus the uv warning line):

```
FF                                                                       [100%]
=================================== FAILURES ===================================
_ test_a_custom_seat_name_with_an_underscore_narrows_to_that_seat[test_role (round 1) lacked core.md.] _
/home/user/wt-2364/plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py:280: in test_a_custom_seat_name_with_an_underscore_narrows_to_that_seat
    assert cd.contradicted(record, bullet(text)) == []
E   AssertionError: assert [{'degradatio...CLAUDE.md'}]}] == []
E     
E     Left contains one more item: {'degradation': 'test_role (round 1) lacked core.md.', 'seats': [{'name': 'code-reviewer (round 1)', 'line': 'code-reviewer (round 1): read its calibration: core.md, review-crew.md, CLAUDE.md'}]}
E     Use -v to get more diff
_ test_a_custom_seat_name_with_an_underscore_narrows_to_that_seat[`test_role` (round 1) lacked core.md.] _
/home/user/wt-2364/plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py:280: in test_a_custom_seat_name_with_an_underscore_narrows_to_that_seat
    assert cd.contradicted(record, bullet(text)) == []
E   AssertionError: assert [{'degradatio...CLAUDE.md'}]}] == []
E     
E     Left contains one more item: {'degradation': '`test_role` (round 1) lacked core.md.', 'seats': [{'name': 'code-reviewer (round 1)', 'line': 'code-reviewer (round 1): read its calibration: core.md, review-crew.md, CLAUDE.md'}]}
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py::test_a_custom_seat_name_with_an_underscore_narrows_to_that_seat[test_role (round 1) lacked core.md.]
FAILED plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py::test_a_custom_seat_name_with_an_underscore_narrows_to_that_seat[`test_role` (round 1) lacked core.md.]
2 failed, 104 deselected in 0.34s
```

- **Restore:** inverse Edit, `key = term.lower()` back to `key = _normalise(term).strip().lower()`.
- **Restore receipt:** the restored line reads `                key = _normalise(term).strip().lower()`.
- **Raw green** (`-k custom_seat_name_with_an_underscore_narrows`):

```
..                                                                       [100%]
2 passed, 104 deselected in 0.41s
```

**Retired (02:13Z scope order):** the guarded code was removed when the marker replaced free-prose seat narrowing; this entry's runs are history.

## 12. The doctrine exemption (`_claims`, `_EXEMPT`)

- **Axis:** a doctrine-prescribed show-it disclosure or a stock `calibrated verify/model/command` phrase is masked
  before the claim test, so it never reads as a claim that a seat lacked calibration; a real claim beside it still
  counts (the second half is pinned by `test_doctrine_disclosure_with_a_real_claim_still_refuses`, which runs green on
  the unneutralized code, and the DoD headline test).
- **Neutralization:** `masked = _EXEMPT.sub(" ", clause)` became `masked = clause`.
- **Raw red** (`-k doctrine_prescribed_disclosures_pass`, main test file; verbatim minus the uv warning line):

```
FFFF                                                                     [100%]
=================================== FAILURES ===================================
___________ test_doctrine_prescribed_disclosures_pass[costly-text0] ____________
/home/user/wt-2364/plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py:457: in test_doctrine_prescribed_disclosures_pass
    assert cd.contradicted(record, bullet(text, label)) == []
E   AssertionError: assert [{'degradatio...CLAUDE.md'}]}] == []
E     
E     Left contains one more item: {'degradation': 'The review owes the owner a direct look at the change, and this project declares no show-it surface. ...reviewer (round 1)', 'line': 'security-reviewer (round 1): read its calibration: core.md, review-crew.md, CLAUDE.md'}]}
E     Use -v to get more diff
___________ test_doctrine_prescribed_disclosures_pass[costly-text1] ____________
/home/user/wt-2364/plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py:457: in test_doctrine_prescribed_disclosures_pass
    assert cd.contradicted(record, bullet(text, label)) == []
E   assert [{'degradatio...CLAUDE.md'}]}] == []
E     
E     Left contains one more item: {'degradation': 'There is no live view for you to open: the project\'s calibration declares no show-it surface, so "Ho...reviewer (round 1)', 'line': 'security-reviewer (round 1): read its calibration: core.md, review-crew.md, CLAUDE.md'}]}
E     Use -v to get more diff
__________ test_doctrine_prescribed_disclosures_pass[harmless-text2] ___________
/home/user/wt-2364/plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py:457: in test_doctrine_prescribed_disclosures_pass
    assert cd.contradicted(record, bullet(text, label)) == []
E   assert [{'degradatio...CLAUDE.md'}]}] == []
E     
E     Left contains one more item: {'degradation': "The main merge at `05bed485` landed after session 6 closed. It brings only main's own reviewed conten...reviewer (round 1)', 'line': 'security-reviewer (round 1): read its calibration: core.md, review-crew.md, CLAUDE.md'}]}
E     Use -v to get more diff
__________ test_doctrine_prescribed_disclosures_pass[harmless-text3] ___________
/home/user/wt-2364/plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py:457: in test_doctrine_prescribed_disclosures_pass
    assert cd.contradicted(record, bullet(text, label)) == []
E   assert [{'degradatio...CLAUDE.md'}]}] == []
E     
E     Left contains one more item: {'degradation': "The pre-code brief check ran on codex's second allowlisted model, `gpt-6-astra`/high, not the calibra...reviewer (round 1)', 'line': 'security-reviewer (round 1): read its calibration: core.md, review-crew.md, CLAUDE.md'}]}
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py::test_doctrine_prescribed_disclosures_pass[costly-text0]
FAILED plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py::test_doctrine_prescribed_disclosures_pass[costly-text1]
FAILED plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py::test_doctrine_prescribed_disclosures_pass[harmless-text2]
FAILED plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py::test_doctrine_prescribed_disclosures_pass[harmless-text3]
4 failed, 110 deselected in 0.29s
```

- **Restore:** inverse Edit, `masked = clause` back to `masked = _EXEMPT.sub(" ", clause)`.
- **Restore receipt:** the restored line reads `        masked = _EXEMPT.sub(" ", clause)`.
- **Raw green** (`-k doctrine_prescribed_disclosures_pass`):

```
....                                                                     [100%]
4 passed, 110 deselected in 0.41s
```

**Re-run at the marker rewrite (02:13Z):** the mask now sits in `_mentions_calibration`; selector `-k
doctrine_prescribed_disclosures_pass` (4 cases, now `cd.problems(...) == []`). Neutralization: `masked = _EXEMPT.sub("
", clause)` became `masked = clause`. Raw red (verbatim minus the uv warning line, lines cut to 260 columns by the shell
`cut`; the `Left contains` and `where` detail is cut as printed):

```
FFFF                                                                     [100%]
=================================== FAILURES ===================================
___________ test_doctrine_prescribed_disclosures_pass[costly-text0] ____________
/home/user/wt-2364/plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py:504: in test_doctrine_prescribed_disclosures_pass
    assert cd.problems(record, bullet(text, label)) == []
E   AssertionError: assert [{'reason': '... the marker'}] == []
[... the other three failure blocks elided; each is the same shape, for costly-text1, harmless-text2 and harmless-text3 ...]
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py::test_doctrine_prescribed_disclosures_pass[costly-text0]
FAILED plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py::test_doctrine_prescribed_disclosures_pass[costly-text1]
FAILED plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py::test_doctrine_prescribed_disclosures_pass[harmless-text2]
FAILED plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py::test_doctrine_prescribed_disclosures_pass[harmless-text3]
4 failed, 121 deselected in 0.35s
```

Restore: inverse Edit. Restore receipt: line 127 reads `        masked = _EXEMPT.sub(" ", clause)`. Raw green:

```
....                                                                     [100%]
4 passed, 121 deselected in 0.33s
```

## 13. The narrowed identifier form (`_EXEMPT`)

- **Axis:** the model-identifier exemption applies only after "the" and only to a token that starts with a letter and
  holds a digit, so "calibrated" followed by a digit-led token or by a parenthesis never masks the word where it is
  itself the claim ("not calibrated (gpt-6.1-sol ran bare)", "not calibrated 2 rounds", "calibrated 3 files stripped").
- **Neutralization:** in `_EXEMPT`, the alternative `\bthe\s+calibrated\s+[a-z]\S*\d\S*` became
  `\bcalibrated\s+\S*\d\S*` (the old broad form).
- **Raw red** (`-k an_exemption_never_lets`, over the three test files; verbatim minus the uv warning line; each long
  `where` line is cut by pytest itself, as printed). All three cases went red, not only the two digit-led ones:
  the parenthesis-led case also matches the old `\S*\d\S*` (the `\S*` takes the `(`):

```
FFF                                                                      [100%]
=================================== FAILURES ===================================
_ test_an_exemption_never_lets_a_real_lack_claim_through[The code reviewer was not calibrated (gpt-6.1-sol ran bare).] _
/home/user/wt-2364/plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py:489: in test_an_exemption_never_lets_a_real_lack_claim_through
    assert cd.contradicted(record, bullet(text))
E   assert []
_ test_an_exemption_never_lets_a_real_lack_claim_through[The reviewers were not calibrated 2 rounds in a row.] _
/home/user/wt-2364/plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py:489: in test_an_exemption_never_lets_a_real_lack_claim_through
    assert cd.contradicted(record, bullet(text))
E   assert []
_ test_an_exemption_never_lets_a_real_lack_claim_through[The calibrated 3 files were stripped from the code reviewer.] _
/home/user/wt-2364/plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py:489: in test_an_exemption_never_lets_a_real_lack_claim_through
    assert cd.contradicted(record, bullet(text))
E   assert []
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py::test_an_exemption_never_lets_a_real_lack_claim_through[The code reviewer was not calibrated (gpt-6.1-sol ran bare).]
FAILED plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py::test_an_exemption_never_lets_a_real_lack_claim_through[The reviewers were not calibrated 2 rounds in a row.]
FAILED plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py::test_an_exemption_never_lets_a_real_lack_claim_through[The calibrated 3 files were stripped from the code reviewer.]
3 failed, 119 deselected in 0.55s
```

  The `where`/`and` detail lines under each `E   assert []` (the record and body dumps) are elided from this quote,
  about 1.5 KB; nothing else was cut. Nothing in the capture needed redaction.
- **Restore:** inverse Edit, `\bcalibrated\s+\S*\d\S*` back to `\bthe\s+calibrated\s+[a-z]\S*\d\S*`.
- **Restore receipt:** the restored line reads
  `    r"|\bshow-it surface\b|\bcalibrated[\s-]+(?:verify|model|command)s?\b|\bthe\s+calibrated\s+[a-z]\S*\d\S*", re.I)`.
- **Raw green** (`-k an_exemption_never_lets`):

```
...                                                                      [100%]
3 passed, 119 deselected in 0.62s
```

**Re-run at the marker rewrite (02:13Z):** selector `-k an_exemption_never_lets` (3 cases, now expecting
`calibration-disclosure-unmarked`). Neutralization: in `_EXEMPT`, `\bthe\s+calibrated\s+[a-z]\S*\d\S*` became
`\bcalibrated\s+\S*\d\S*`. Raw red (verbatim minus the uv warning line; the first failure block is shown and the other two
are the same shape):

```
FFF                                                                      [100%]
=================================== FAILURES ===================================
_ test_an_exemption_never_lets_a_real_lack_claim_through[The code reviewer was not calibrated (gpt-6.1-sol ran bare).] _
/home/user/wt-2364/plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py:536: in test_an_exemption_never_lets_a_real_lack_claim_through
    assert reasons(cd.problems(record, bullet(text))) == [cd.REASON_UNMARKED]
E   AssertionError: assert [] == ['calibration...ure-unmarked']
E     
E     Right contains one more item: 'calibration-disclosure-unmarked'
E     Use -v to get more diff
[... the blocks for "not calibrated 2 rounds in a row" and "The calibrated 3 files were stripped" elided, same shape ...]
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py::test_an_exemption_never_lets_a_real_lack_claim_through[The code reviewer was not calibrated (gpt-6.1-sol ran bare).]
FAILED plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py::test_an_exemption_never_lets_a_real_lack_claim_through[The reviewers were not calibrated 2 rounds in a row.]
FAILED plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py::test_an_exemption_never_lets_a_real_lack_claim_through[The calibrated 3 files were stripped from the code reviewer.]
3 failed, 122 deselected in 0.32s
```

Restore: inverse Edit. Restore receipt: line 80 reads `    r"|\bshow-it surface\b|\bcalibrated[\s-]+(?:verify|model|command)s?\b|\bthe\s+calibrated\s+[a-z]\S*\d\S*", re.I)`.
Raw green:

```
...                                                                      [100%]
3 passed, 122 deselected in 0.31s
```

## 14. Marker validity (`_valid_markers`)

- **Axis:** a span is a valid marker only when its files, split on a comma and one space, are a non-empty list of the
  three exact names `core.md`, `review-crew.md` and `CLAUDE.md` with no duplicate; any other span is left in the text
  and refused `calibration-disclosure-unmarked`, never passed.
- **Neutralization:** `if None not in labels and len(set(files)) == len(files):` became `if files:` (every non-empty
  split counts).
- **Raw red** (`-k malformed_marker`, 8 cases; verbatim minus the uv warning line, lines cut to 260 columns by the shell
  `cut`; the four failure blocks are shown as the first, the other three are the same shape). Four cases go red: the
  unknown file, the duplicate file, lowercase `claude.md` and two spaces after the comma. The other four (empty list,
  no space after the colon, empty brackets, no backticks) never match `_MARKER`, so the file-list check is not reached
  and they stay green, as they must:

```
F.FF.F..                                                                 [100%]
=================================== FAILURES ===================================
______________ test_a_malformed_marker_is_unmarked[unknown-file] _______________
/home/user/wt-2364/plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py:303: in test_a_malformed_marker_is_unmarked
    assert reasons(cd.problems(rec(reviewers), pr_body)) == [cd.REASON_UNMARKED]
E   AssertionError: assert [] == ['calibration...ure-unmarked']
E     
E     Right contains one more item: 'calibration-disclosure-unmarked'
E     Use -v to get more diff
[... the blocks for duplicate-file, lowercase-claude and two-spaces-after-comma elided, same shape ...]
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py::test_a_malformed_marker_is_unmarked[unknown-file]
FAILED plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py::test_a_malformed_marker_is_unmarked[duplicate-file]
FAILED plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py::test_a_malformed_marker_is_unmarked[lowercase-claude]
FAILED plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py::test_a_malformed_marker_is_unmarked[two-spaces-after-comma]
4 failed, 4 passed, 117 deselected in 0.35s
```

- **Restore:** inverse Edit, `if files:` back to `if None not in labels and len(set(files)) == len(files):`.
- **Restore receipt:** line 108 reads `        if None not in labels and len(set(files)) == len(files):`.
- **Raw green** (`-k malformed_marker`):

```
........                                                                 [100%]
8 passed, 117 deselected in 0.30s
```

## 15. The absent row (`problems`)

- **Axis:** a marker whose row name matches no row of the record exactly is refused `calibration-disclosure-unknown-seat`,
  naming the marker's text and every row; the match is never widened (a trailing space is a different name).
- **Neutralization:** `if not targets:` (the absent-row branch) became `if False:`, so no problem is added and the
  targets stay empty.
- **Raw red** (`-k absent_row`; verbatim minus the uv warning line):

```
F                                                                        [100%]
=================================== FAILURES ===================================
__________________ test_a_marker_naming_an_absent_row_refuses __________________
/home/user/wt-2364/plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py:188: in test_a_marker_naming_an_absent_row_refuses
    assert reasons(found) == [cd.REASON_UNKNOWN_SEAT]
E   AssertionError: assert [] == ['calibration...unknown-seat']
E     
E     Right contains one more item: 'calibration-disclosure-unknown-seat'
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py::test_a_marker_naming_an_absent_row_refuses
1 failed, 124 deselected in 0.30s
```

- **Restore:** inverse Edit, `if False:` back to `if not targets:`.
- **Restore receipt:** line 167 reads `                if not targets:`.
- **Raw green** (`-k absent_row`):

```
.                                                                        [100%]
1 passed, 124 deselected in 0.29s
```

## 16. Per-file contradiction (`_contradicts`)

- **Axis:** one named file graded `read` is enough to contradict a marker, so a partly false marker cannot pass.
- **Neutralization:** `return any(entry["label"] in labels and entry["read"] == calibration_vocab.READ for entry in
  files)` became two lines, `held = [entry for entry in files if entry["label"] in labels]` and `return bool(held) and
  all(entry["read"] == calibration_vocab.READ for entry in held)` (`all(...)` over every named label held).
- **Raw red** (`-k any_named_file_read`; verbatim minus the uv warning line). The fixture grades core `read` and
  review-crew `not-read` and names both files:

```
F                                                                        [100%]
=================================== FAILURES ===================================
_____________ test_a_marker_is_contradicted_by_any_named_file_read _____________
/home/user/wt-2364/plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py:176: in test_a_marker_is_contradicted_by_any_named_file_read
    assert reasons(cd.problems(rec(reviewers), both)) == [cd.REASON]
E   AssertionError: assert [] == ['calibration...contradicted']
E     
E     Right contains one more item: 'calibration-disclosure-contradicted'
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py::test_a_marker_is_contradicted_by_any_named_file_read
1 failed, 124 deselected in 0.31s
```

- **Restore:** inverse Edit, the two lines back to the single `return any(...)`.
- **Restore receipt:** line 141 reads `    return any(entry["label"] in labels and entry["read"] == calibration_vocab.READ for entry in files)`.
- **Raw green** (`-k any_named_file_read`):

```
.                                                                        [100%]
1 passed, 124 deselected in 0.30s
```

## 17. The marker is masked, and only the marker (`problems`, `_unmarked_text`)

- **Axis:** only the valid marker spans are replaced by a space before the unmarked test, so prose beside a marker is
  still read for a mention of calibration. (The other half, that the marker's own words do not trip the test, is pinned
  by `test_marker_prose_without_a_mention_passes` and `test_the_doctrine_example_is_the_module_constant`, which pass only
  because the span is masked; that half was not neutralized in this dispatch and is unproven by a red run.)
- **Neutralization:** `left = _unmarked_text(text, markers)` became `left = " "` (the whole bullet, not the marker span,
  replaced by a space before the unmarked test).
- **Raw red** (`-k does_not_cover_unmarked_prose`; verbatim minus the uv warning line):

```
F                                                                        [100%]
=================================== FAILURES ===================================
____________ test_a_marker_does_not_cover_unmarked_prose_beside_it _____________
/home/user/wt-2364/plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py:277: in test_a_marker_does_not_cover_unmarked_prose_beside_it
    assert reasons(cd.problems(rec(reviewers), pr_body)) == [cd.REASON_UNMARKED]
E   AssertionError: assert [] == ['calibration...ure-unmarked']
E     
E     Right contains one more item: 'calibration-disclosure-unmarked'
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py::test_a_marker_does_not_cover_unmarked_prose_beside_it
1 failed, 124 deselected in 0.31s
```

- **Restore:** inverse Edit, `left = " "` back to `left = _unmarked_text(text, markers)`.
- **Restore receipt:** line 179 reads `        left = _unmarked_text(text, markers)`.
- **Raw green** (`-k does_not_cover_unmarked_prose`):

```
.                                                                        [100%]
1 passed, 124 deselected in 0.28s
```

## 18. The unmarked refusal (`problems`)

- **Axis:** a bullet that mentions calibration outside a valid marker is refused `calibration-disclosure-unmarked`,
  whatever the record says.
- **Neutralization:** `if _mentions_calibration(_normalise(left)):` became `if False:` (the unmarked problem is never
  added).
- **Raw red** (`-k "dod_headline or unmarked_mention_refuses"`; verbatim minus the uv warning line):

```
FFF                                                                      [100%]
=================================== FAILURES ===================================
_ test_dod_headline_unmarked_is_refused[Calibration was stripped from the reviewers.] _
/home/user/wt-2364/plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py:124: in test_dod_headline_unmarked_is_refused
    assert result["ok"] is False and result["reason"] == "calibration-disclosure-unmarked"
E   assert (True is False)
_ test_dod_headline_unmarked_is_refused[Calibration (CLAUDE.md, .claude) was stripped from the reviewers by the sanitized view.] _
/home/user/wt-2364/plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py:124: in test_dod_headline_unmarked_is_refused
    assert result["ok"] is False and result["reason"] == "calibration-disclosure-unmarked"
E   assert (True is False)
__________ test_an_unmarked_mention_refuses_whatever_the_record_says ___________
/home/user/wt-2364/plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py:270: in test_an_unmarked_mention_refuses_whatever_the_record_says
    assert result["ok"] is False and result["reason"] == "calibration-disclosure-unmarked"
E   assert (True is False)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py::test_dod_headline_unmarked_is_refused[Calibration was stripped from the reviewers.]
FAILED plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py::test_dod_headline_unmarked_is_refused[Calibration (CLAUDE.md, .claude) was stripped from the reviewers by the sanitized view.]
FAILED plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py::test_an_unmarked_mention_refuses_whatever_the_record_says
3 failed, 122 deselected in 0.32s
```

- **Restore:** inverse Edit, `if False:` back to `if _mentions_calibration(_normalise(left)):`.
- **Restore receipt:** line 181 reads `        if _mentions_calibration(_normalise(left)):`.
- **Raw green** (`-k "dod_headline or unmarked_mention_refuses"`):

```
...                                                                      [100%]
3 passed, 122 deselected in 0.34s
```

## 19. Engine-record only (`_contradicts`)

- **Axis:** only an engine-record row can contradict a marker; a session-reported row (even one that carries `read`
  grades), a not-run row, an unmeasured row and a row whose order named none never do.
- **Neutralization:** the two lines `if row.get("ran") != "engine-record":` and `return False` were removed.
- **Raw red** (`-k no_measured_calibration`; verbatim minus the uv warning line, lines cut to 260 columns by the shell
  `cut`). Only the session-reported row that carries `read` grades (`only4`) goes red; the other four rows have no
  `read` grade to read, so they stay green under this neutralization:

```
....F                                                                    [100%]
=================================== FAILURES ===================================
_____ test_a_row_with_no_measured_calibration_is_never_contradicted[only4] _____
/home/user/wt-2364/plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py:441: in test_a_row_with_no_measured_calibration_is_never_contradicted
    assert cd.problems(rec([only]), pr_body) == []
E   AssertionError: assert [{'reason': '...ine record)'}] == []
E     
E     Left contains one more item: {'reason': 'calibration-disclosure-contradicted', 'degradation': '`calibration-lacked[code-reviewer (round 1)]: core.m... code-reviewer (round 1) contradicts <where>: code-reviewer (round 1): calibration read: not shown (no e
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_calibration_disclosure_2364.py::test_a_row_with_no_measured_calibration_is_never_contradicted[only4]
1 failed, 4 passed, 120 deselected in 0.33s
```

- **Restore:** inverse Edit, the two lines put back above `files = ...`.
- **Restore receipt:** lines 137 and 138 read `    if row.get("ran") != "engine-record":` and `        return False`.
- **Raw green** (`-k no_measured_calibration`):

```
.....                                                                    [100%]
5 passed, 120 deselected in 0.33s
```
