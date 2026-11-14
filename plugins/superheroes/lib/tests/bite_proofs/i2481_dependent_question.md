# Bite-proof record: i2481_dependent_question (#2481) a PR-sheet card never depends on another question's answer

Detector under proof: `plugins/superheroes/lib/tests/test_pr_sheet_dependent_question_2481.py` (unedited between the red and the green of every entry, except where an entry says rows were added before its red).
Guarded code: `plugins/superheroes/lib/pr_sheet.py` (`_DEPENDS`, `_AS_PR`, `_dependencies`, and the `dependent` list and `Refusal` at the scan site in `build`). Base head `07a0ff09`.
Every neutralization was one targeted edit made with the Edit tool and undone by the inverse Edit before the next element.
No `git checkout`, `restore`, `reset`, `stash` or `sed` was used.
Command prefix for every run (worktree root), `-k` as per entry:
`timeout 600 scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_pr_sheet_dependent_question_2481.py -q -p no:cacheprovider --tb=line -k <selector>`
Restore receipts are the restored lines, quoted back by a Grep-tool read after each inverse Edit.

Guarded-element set (declared by the order): G1 the scan's refusal; G2 option label and consequence are scanned; G3 recommendation text and reason are scanned;
G4 D1; G5 D2; G6 D3; G7 D4; G8 D5; G9 D6; G10 D7 (another on-sheet collector number); G11 D7's PR exemption; G12 D8 (own number allowed). No others.
Row ids carry the element tags (`g01` to `g12`), so `-k gNN` selects an element's rows.

Disclosures:
- Captures are the runner's output with uv's one `UV_NATIVE_TLS` deprecation warning line dropped. Nothing was redacted. Each capture is far under the 32 KiB ceiling; the `DID NOT RAISE Refusal` failure bodies repeat per row and are quoted once per distinct body where they repeat.
- Rows added during the proof: the three other D4 shapes (`g07-d4-card-12`, `g07-d4-when-item-12-is`, `g07-d4-collector-hash-12`) before the G7 run, and `g09-d6-card-above` before the G9 run. The G1 to G6 runs were made on the file before those four rows existed; the rows carry only the `g07` and `g09` tags, so the rows each earlier `-k` selected did not change.
- G1: `test_g01_a_pointer_and_a_dependent_question_are_both_listed_pointer_first` stays green under the neutralization, because the neutralized `if pointing:` still raises `pointing + dependent` when a pointer problem exists. It pins the pointer-first order (E9), not the refusal itself; the field-case test carries G1.
- G4: the second D1 row (`g04-d1-if-you-chose-for-the-other`) is red on the matched text, not on a missing refusal: with D1 off, D6 still matches `the other card`, so the refusal is raised with `the other card` in place of `if you chose a for the other`.
- G8: the `-k` was `"g08 or g01_the_field or g12"` (a wider selector than the order's per-element `-k`), so its red also shows the field case and the dashed own-number row; the `g08` row is the one that carries the element.
- G12: the two `g12-ok-` rows are the ones that bite. The dashed control rows (`test_g12_a_dashed_form_...`) stay green under the neutralization, as designed: a dashed reference is refused with or without the exemption.
- The order's final scoped run (eight files) is red: see "Whole scoped run" at the end. It is a finding, not a bite-proof half.

## G1: the dependent-question problems reach the Refusal

- **Guarded element / axis:** `pr_sheet.py:1389`, `if pointing or dependent:` (the raise at `:1390`). Axis: a card whose option or recommendation depends on another question makes `build` refuse; without it the problems are computed and dropped.
- **Neutralization:** `if pointing or dependent:` became `if pointing:`.
- **Raw red** (`-k g01`):

```
F.                                                                       [100%]
E   Failed: DID NOT RAISE Refusal
/home/user/wt-2481/plugins/superheroes/lib/tests/test_pr_sheet.py:57: Failed: DID NOT RAISE Refusal
FAILED plugins/superheroes/lib/tests/test_pr_sheet_dependent_question_2481.py::test_g01_the_field_case_from_the_issue_is_refused
1 failed, 1 passed, 41 deselected in 0.70s
```

- **Restore:** the inverse Edit, `if pointing:` back to `if pointing or dependent:`.
- **Restore receipt:** a Grep read printed `1389:    if pointing or dependent:`.
- **Raw green** (same `-k`):

```
..                                                                       [100%]
2 passed, 41 deselected in 0.71s
```

## G2: option label and consequence are scanned

- **Guarded element / axis:** `pr_sheet.py:934`, `fields = [(f"option {o['id']}", o[k]) for o in card["options"] for k in ("label", "consequence")]`. Axis: an option's label and its consequence are both read by the scan.
- **Neutralization:** `for k in ("label", "consequence")]` became `for k in ()]` (no option field is read).
- **Raw red** (`-k g02`):

```
FFFF                                                                     [100%]
E   Failed: DID NOT RAISE Refusal   (x4)
FAILED ...::test_a_card_depending_on_another_question_is_refused[g04-g02-d1-only-if-you-pick-for-item]
FAILED ...::test_a_card_depending_on_another_question_is_refused[g02-g07-d4-in-a-collector-option-label]
FAILED ...::test_an_items_entry_option_label_is_scanned[g02-g07-label]
FAILED ...::test_an_items_entry_option_label_is_scanned[g02-g05-label]
4 failed, 39 deselected in 0.70s
```

- **Restore:** the inverse Edit, `for k in ()]` back to `for k in ("label", "consequence")]`.
- **Restore receipt:** a Grep read printed `934:    fields = [(f"option {o['id']}", o[k]) for o in card["options"] for k in ("label", "consequence")]`.
- **Raw green** (same `-k`):

```
....                                                                     [100%]
4 passed, 39 deselected in 0.71s
```

## G3: recommendation text and reason are scanned

- **Guarded element / axis:** `pr_sheet.py:935`, `fields += [("recommendation", rec[k]) for k in ("text", "reason") if k in rec]`. Axis: a recommendation's text and its reason are both read by the scan.
- **Neutralization:** `for k in ("text", "reason") if k in rec]` became `for k in () if k in rec]`.
- **Raw red** (`-k g03`):

```
FFFF                                                                     [100%]
E   Failed: DID NOT RAISE Refusal   (x4)
FAILED ...::test_a_card_depending_on_another_question_is_refused[g03-g05-d2-in-the-recommendation-reason]
FAILED ...::test_a_card_depending_on_another_question_is_refused[g03-g07-d4-in-the-recommendation-reason]
FAILED ...::test_a_card_depending_on_another_question_is_refused[g03-g10-d7-in-the-recommendation-text]
FAILED ...::test_a_card_depending_on_another_question_is_refused[g03-g09-d6-in-the-recommendation-text-of-the-other-card]
4 failed, 39 deselected in 0.70s
```

- **Restore:** the inverse Edit, `for k in () if k in rec]` back to `for k in ("text", "reason") if k in rec]`.
- **Restore receipt:** a Grep read printed `935:    fields += [("recommendation", rec[k]) for k in ("text", "reason") if k in rec]`.
- **Raw green** (same `-k`):

```
....                                                                     [100%]
4 passed, 39 deselected in 0.76s
```

## G4: D1, a choice made somewhere else

- **Guarded element / axis:** `pr_sheet.py:228`, the D1 alternative of `_DEPENDS` (`\b(?:only\s+)?(?:if|unless|once|when|after|until)\s+you\s+(?:pick|...`). Axis: "only if you pick b for item 12", "if you chose a for the other card".
- **Neutralization:** the alternative opened `r"(?!)\b(?:only\s+)?(?:if|...` (it can never match).
- **Raw red** (`-k g04`):

```
FF                                                                       [100%]
E   Failed: DID NOT RAISE Refusal
E   assert ['dependent-q... ask it then'] == ['dependent-q... ask it then']
      At index 0 diff: "dependent-question: collectorItems 1435: card 'Should the receipt page keep the old wording for gift orders?' option b depends on another question ('the other card'); ... != "... option b depends on another question ('if you chose a for the other'); ...
FAILED ...::test_a_card_depending_on_another_question_is_refused[g04-g02-d1-only-if-you-pick-for-item]
FAILED ...::test_a_card_depending_on_another_question_is_refused[g04-d1-if-you-chose-for-the-other]
2 failed, 41 deselected in 0.62s
```

- **Restore:** the inverse Edit, `r"(?!)\b(?:only...` back to `r"\b(?:only...`.
- **Restore receipt:** a Grep read printed `228:    r"\b(?:only\s+)?(?:if|unless|once|when|after|until)\s+you\s+(?:pick|picked|choose|chose|chosen|answer|answered|rule|ruled"`.
- **Raw green** (same `-k`):

```
..                                                                       [100%]
2 passed, 41 deselected in 0.63s
```

## G5: D2, depending on an answer

- **Guarded element / axis:** `pr_sheet.py:232`, the D2 alternative (`\b(?:depending|depends|dependent|contingent|conditional)\s+on\s+...`). Axis: "depends on your answer to ...".
- **Neutralization:** the alternative opened `r"|(?!)\b(?:depending|depends|...`.
- **Raw red** (`-k g05`):

```
FFF                                                                      [100%]
E   Failed: DID NOT RAISE Refusal   (x3)
FAILED ...::test_a_card_depending_on_another_question_is_refused[g05-d2-depends-on-your-answer]
FAILED ...::test_a_card_depending_on_another_question_is_refused[g03-g05-d2-in-the-recommendation-reason]
FAILED ...::test_an_items_entry_option_label_is_scanned[g02-g05-label]
3 failed, 40 deselected in 0.70s
```

- **Restore:** the inverse Edit, `r"|(?!)\b(?:depending` back to `r"|\b(?:depending`.
- **Restore receipt:** a Grep read printed `232:    r"|\b(?:depending|depends|dependent|contingent|conditional)\s+on\s+(?:your|the|how\s+you|what\s+you|which)\b[^.;]{0,40}?"`.
- **Raw green** (same `-k`):

```
...                                                                      [100%]
3 passed, 40 deselected in 0.72s
```

## G6: D3, the same answer as another

- **Guarded element / axis:** `pr_sheet.py:235-236`, the two D3 sub-alternatives (`(?:same|matching)\s+(?:choice|...)\s+(?:as|you\s+(?:gave|...))` and `whichever\s+(?:option\s+)?you\s+...`). Axis: "the same choice as ...", "whichever option you pick on ...".
- **Neutralization:** both lines opened with `(?!)` (`r"|(?!)\b(?:same|matching)...` and `r"|(?!)\bwhichever...`), one Edit.
- **Raw red** (`-k g06`):

```
FF                                                                       [100%]
E   Failed: DID NOT RAISE Refusal   (x2)
FAILED ...::test_a_card_depending_on_another_question_is_refused[g06-d3-same-choice-as]
FAILED ...::test_a_card_depending_on_another_question_is_refused[g06-d3-whichever-option-you-pick-on]
2 failed, 41 deselected in 0.71s
```

- **Restore:** the inverse Edit, both `(?!)` removed.
- **Restore receipt:** Grep reads printed `235:    r"|\b(?:same|matching)\s+(?:choice|answer|pick|option|letter|ruling)\s+(?:as|you\s+(?:gave|made|picked|chose))\b"` and `236:    r"|\bwhichever\s+(?:option\s+)?you\s+(?:pick|picked|choose|chose)\s+(?:on|for|in|at)\b"`.
- **Raw green** (same `-k`):

```
..                                                                       [100%]
2 passed, 41 deselected in 0.72s
```

## G7: D4, a question named by number

- **Guarded element / axis:** `pr_sheet.py:238-239`, the `(?P<numbered>...)` group holding the four D4 shapes (`decision item N`, `collector #N`, `card N`, `when item N is`). Axis: a question named by number.
- **Neutralization:** the whole group made unmatchable: `(?P<numbered>(?!)(?:\b(?:collector|decision|list)\s+item ... stays)\b))` (an opening `(?!)(?:` on line 238 and one more closing paren at the end of line 239). A first attempt that put `(?!)` before the first shape only was reverted before any run.
- **Raw red** (`-k g07`, after the three other-shape rows were added):

```
FFFFFFF                                                                  [100%]
E   Failed: DID NOT RAISE Refusal   (x7)
FAILED ...::test_a_card_depending_on_another_question_is_refused[g07-d4-decision-item-12]
FAILED ...::test_a_card_depending_on_another_question_is_refused[g07-d4-card-12]
FAILED ...::test_a_card_depending_on_another_question_is_refused[g07-d4-when-item-12-is]
FAILED ...::test_a_card_depending_on_another_question_is_refused[g07-d4-collector-hash-12]
FAILED ...::test_a_card_depending_on_another_question_is_refused[g02-g07-d4-in-a-collector-option-label]
FAILED ...::test_a_card_depending_on_another_question_is_refused[g03-g07-d4-in-the-recommendation-reason]
FAILED ...::test_an_items_entry_option_label_is_scanned[g02-g07-label]
7 failed, 39 deselected in 0.78s
```

- **Restore:** the inverse Edits (the `(?!)(?:` opening and the extra closing paren removed).
- **Restore receipt:** a Read of `pr_sheet.py:238-239` printed the group as `(?P<numbered>\b(?:collector|decision|list)\s+item\s+#?\d+(?:-\d+)?\b|\bcollector\s+(?:#\d+|(?:number|entry)\s+#?\d+)` / `|\b(?:card|question)\s+#?\d+(?:-\d+)?\b|\b(?:if|unless|once|when)\s+item\s+#?\d+(?:-\d+)?\s+(?:is|was|gets|goes|lands|stays)\b)"`.
- **Raw green** (same `-k`):

```
.......                                                                  [100%]
7 passed, 39 deselected in 0.73s
```

## G8: D5, a bare dashed collector reference

- **Guarded element / axis:** `pr_sheet.py:241`, `r"|(?<![\w-])\d{3,}-\d{1,2}(?![\w-])"`. Axis: "1435-1".
- **Neutralization:** the alternative opened `r"|(?!)(?<![\w-])\d{3,}...`.
- **Raw red** (`-k "g08 or g01_the_field or g12"`, a wider selector than the per-element one; see Disclosures):

```
FF..F.                                                                   [100%]
E   Failed: DID NOT RAISE Refusal   (x3)
FAILED ...::test_a_card_depending_on_another_question_is_refused[g08-d5-bare-dashed-reference]
FAILED ...::test_g01_the_field_case_from_the_issue_is_refused
FAILED ...::test_g12_a_dashed_form_of_the_cards_own_number_is_always_refused[a-dashed-form-of-the-cards-own-number]
3 failed, 3 passed, 40 deselected in 0.72s
```

- **Restore:** the inverse Edit, `r"|(?!)(?<![\w-])` back to `r"|(?<![\w-])`.
- **Restore receipt:** a Grep read printed `241:    r"|(?<![\w-])\d{3,}-\d{1,2}(?![\w-])"`.
- **Raw green** (same `-k`):

```
......                                                                   [100%]
6 passed, 40 deselected in 0.71s
```

## G9: D6, the other question by position

- **Guarded element / axis:** `pr_sheet.py:243-244`, the two D6 sub-alternatives (`the (other|previous|...) (card|question|decision|collector item)` and `(card|question|decision) (above|below)`). Axis: "the other question", "the card above".
- **Neutralization:** both lines opened with `(?!)` (`r"|(?!)\bthe\s+(?:other...` and `r"|(?!)\b(?:card|question|decision)\s+(?:above|below)\b"`), one Edit; the `card above` row was added before this run.
- **Raw red** (`-k g09`):

```
FFF                                                                      [100%]
E   Failed: DID NOT RAISE Refusal   (x3)
FAILED ...::test_a_card_depending_on_another_question_is_refused[g09-d6-the-other-question]
FAILED ...::test_a_card_depending_on_another_question_is_refused[g09-d6-card-above]
FAILED ...::test_a_card_depending_on_another_question_is_refused[g03-g09-d6-in-the-recommendation-text-of-the-other-card]
3 failed, 44 deselected in 0.67s
```

- **Restore:** the inverse Edit, both `(?!)` removed.
- **Restore receipt:** a Read of `pr_sheet.py:243-244` printed `    r"|\bthe\s+(?:other|previous|next|earlier|later|first|second|last)\s+(?:card|question|decision|collector\s+item)\b"` / `    r"|\b(?:card|question|decision)\s+(?:above|below)\b", re.IGNORECASE)`.
- **Raw green** (same `-k`):

```
...                                                                      [100%]
3 passed, 44 deselected in 0.72s
```

## G10: D7, another collector number on this sheet, written bare

- **Guarded element / axis:** `pr_sheet.py:938`, `bare = re.compile(...) if others else None` in `_dependencies`. Axis: the bare number of a different `collectorItems` entry.
- **Neutralization:** `if others else None` became `if False else None`.
- **Raw red** (`-k g10`):

```
FF                                                                       [100%]
E   Failed: DID NOT RAISE Refusal   (x2)
FAILED ...::test_a_card_depending_on_another_question_is_refused[g10-d7-another-collector-number]
FAILED ...::test_a_card_depending_on_another_question_is_refused[g03-g10-d7-in-the-recommendation-text]
2 failed, 45 deselected in 0.74s
```

- **Restore:** the inverse Edit, `if False else None` back to `if others else None`.
- **Restore receipt:** a Grep read printed `938:    bare = re.compile(r"(?<!\d)(?<!\d-)(?:" + "|".join(str(n) for n in others) + r")(?!\d)(?!-\d)") if others else None`.
- **Raw green** (same `-k`):

```
..                                                                       [100%]
2 passed, 45 deselected in 0.69s
```

## G11: D7's PR exemption

- **Guarded element / axis:** `pr_sheet.py:246`, `_AS_PR = re.compile(r"(?:#|\bPR\s)$", re.IGNORECASE)`, read at `:950` (`if not _AS_PR.search(text[:hit.start()])`). Axis: a collector number written `#N`, `PR N` or `PR #N` names a pull request and is not refused.
- **Neutralization:** `r"(?:#|\bPR\s)$"` became `r"(?!)(?:#|\bPR\s)$"` (the exemption never fires).
- **Raw red** (`-k g11`):

```
FFF                                                                      [100%]
E   pr_sheet.Refusal: ["dependent-question: collectorItems 1435: card 'Should the receipt page keep the old wording for gift orders?' option a depends on another question ('1501'); a question must be answerable on its own: ask the two as one card whose options name each combination, or hold this card until the other question is ruled and ask it then"]   (x3)
FAILED ...::test_a_healthy_card_still_builds[g11-ok-another-collector-number-written-as-a-pr]
FAILED ...::test_a_healthy_card_still_builds[g11-ok-another-collector-number-written-as-a-pr-hash]
FAILED ...::test_a_healthy_card_still_builds[g11-ok-another-collector-number-with-a-hash]
3 failed, 44 deselected in 0.79s
```

- **Restore:** the inverse Edit, `r"(?!)(?:#|\bPR\s)$"` back to `r"(?:#|\bPR\s)$"`.
- **Restore receipt:** a Grep read printed `246:_AS_PR = re.compile(r"(?:#|\bPR\s)$", re.IGNORECASE)`.
- **Raw green** (same `-k`):

```
...                                                                      [100%]
3 passed, 44 deselected in 0.79s
```

## G12: D8, a card's own number is not another question

- **Guarded element / axis:** `pr_sheet.py:945`, `if int(digits.group(1)) == own and not digits.group(2) and not re.match(r"-\d", text[hit.end():]):` followed by `continue`. Axis: a D4 match whose number, with no dash part, is the card's own collector number is not refused.
- **Neutralization:** the condition became `if False and int(digits.group(1)) == own and ...`.
- **Raw red** (`-k g12`):

```
FF..                                                                     [100%]
E   pr_sheet.Refusal: ["dependent-question: collectorItems 1435: card 'Should the receipt page keep the old wording for gift orders?' recommendation depends on another question ('collector item 1435'); a question must be answerable on its own: ask the two as one card whose options name each combination, or hold this card until the other question is ruled and ask it then"]
E   pr_sheet.Refusal: ["dependent-question: collectorItems 1435: card 'Should the receipt page keep the old wording for gift orders?' option a depends on another question ('Card 1435'); a question must be answerable on its own: ask the two as one card whose options name each combination, or hold this card until the other question is ruled and ask it then"]
FAILED ...::test_a_healthy_card_still_builds[g12-ok-the-cards-own-number]
FAILED ...::test_a_healthy_card_still_builds[g12-ok-the-cards-own-number-after-card]
2 failed, 2 passed, 43 deselected in 0.79s
```

- **Restore:** the inverse Edit, `if False and int(...` back to `if int(...`.
- **Restore receipt:** a Grep read printed `945:                if int(digits.group(1)) == own and not digits.group(2) and not re.match(r"-\d", text[hit.end():]):`.
- **Raw green** (same `-k`):

```
....                                                                     [100%]
4 passed, 43 deselected in 0.69s
```

## Elements in no class

None. G1 to G12 each have their own neutralization and red. Unproven elements: none.

## Whole scoped run (the order's eight-file command): RED, two existing tests

Command: `timeout 600 scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_pr_sheet.py plugins/superheroes/lib/tests/test_pr_sheet_spec.py plugins/superheroes/lib/tests/test_pr_sheet_fixed_above_2332.py plugins/superheroes/lib/tests/test_pr_sheet_assignment_accounting_2332.py plugins/superheroes/lib/tests/test_review_template_pr.py plugins/superheroes/lib/tests/test_leftover_visible_within_line_2389.py plugins/superheroes/lib/tests/test_sheet_schema.py plugins/superheroes/lib/tests/test_pr_sheet_dependent_question_2481.py -q -p no:cacheprovider --tb=line`

```
E   assert (2 == 1)
     +  where 2 = len(["items accepting: card 'Disclosures' sends the owner to a list item ('collector item 1435') instead of carrying that ... as one card whose options name each combination, or hold this card until the other question is ruled and ask it then"])
/home/user/wt-2481/plugins/superheroes/lib/tests/test_pr_sheet.py:2375: assert (2 == 1)
E   assert (2 == 1)
     +  where 2 = len(["items accepting: card 'Disclosures' sends the owner to a list item ('list item 1435') instead of carrying that decis... as one card whose options name each combination, or hold this card until the other question is ruled and ask it then"])
/home/user/wt-2481/plugins/superheroes/lib/tests/test_pr_sheet.py:2375: assert (2 == 1)
FAILED plugins/superheroes/lib/tests/test_pr_sheet.py::test_a_pointer_is_found_wherever_an_option_less_card_shows_text[in-the-recommendation-text]
FAILED plugins/superheroes/lib/tests/test_pr_sheet.py::test_a_pointer_is_found_wherever_an_option_less_card_shows_text[in-the-recommendation-reason]
2 failed, 1344 passed in 133.12s (0:02:13)
```

Cause: `POINTER_PLACES` in `test_pr_sheet.py` (lines 2360-2361) gives an option-less items card a recommendation `{"text": "Accept collector item 1435", ...}` and `{"text": "Accept", "reason": "Covered by list item 1435."}`. The new scan reads the recommendation of every card, an option-less one included, so `collector item 1435` and `list item 1435` (D4) add a `dependent-question` problem beside the pointer problem, and those tests expect exactly one problem. The build session stopped here: no test, fixture or pattern was edited.
