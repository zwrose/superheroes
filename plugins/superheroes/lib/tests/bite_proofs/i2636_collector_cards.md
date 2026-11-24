# Bite-proof record: i2636_collector_cards (#2636) list-item cards with dashed numbers, and the findings a list-item card carries

Detector under proof: `plugins/superheroes/lib/tests/test_pr_sheet_collector_2636.py` (unedited between the red and the green of every entry, except the one edit to `test_e11_the_carried_identity_is_in_the_card_id` made before E11's red, which the E11 entry names).
Guarded code: `plugins/superheroes/lib/pr_sheet.py` (`_LIST_NUMBER`, `_list_number`, `_list_key`, `_carries`, `_carried`, `_check_input`'s leftovers loop, `_check_collector`, `build`'s disposition loop, card loops and `_dependencies`). Base head `af6cfd27`.
Every neutralization was one targeted edit made with the Edit tool and undone by the inverse Edit before the next element.
No `git checkout`, `restore`, `reset`, `stash` or `sed` was used.
Command prefix for every run (worktree root), `-k` as per entry:
`timeout 600 scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-2636 -m pytest plugins/superheroes/lib/tests/test_pr_sheet_collector_2636.py -q -p no:cacheprovider --tb=short -k <selector>`
Restore receipts are the restored lines, quoted back by a Grep-tool read after each inverse Edit.

Guarded-element set (declared by the order): E1 the list-number shape; E2 duplicates across spellings; E3 the own-number exemption; E4 another dashed item is still refused; E5 a carriedBy naming no card; E6 a malformed carriedBy (extra key, bad number); E7 the alias conflict; E8 a carried finding makes no card; E9 a carried finding is no decided-for-you entry; E10 the carried section; E11 the carried identity in the card id; E12 the missing or blank carriedTitle; E13 byte identity with base; E14 the page. Rows and tests carry the tags `e01` to `e14`, so `-k eNN` selects an element.

Disclosures:
- Captures are the runner's output with uv's one `UV_NATIVE_TLS` deprecation warning line dropped. Nothing was redacted. Every capture is far under the 32 KiB ceiling.

## E1: the list-number shape

- **Guarded element / axis:** `pr_sheet.py:304`, `_LIST_NUMBER`. Axis: a list-item number has exactly one spelling, N or N-M with no leading zero and no zero part.
- **Neutralization:** `r"[1-9]\d*(?:-[1-9]\d*)?"` became `r"\d+(?:-\d+)?"` (the issue's own pattern, accepting leading zeros and zero parts).
- **Raw red** (`-k e01`; the four identical failure bodies, one per row, are quoted once):

```
....FFFF.....                                                            [100%]
___ test_e01_a_malformed_list_number_is_refused[e01-refused-'02273'] ___   (same body for '2273-01', '2273-0', '0')
test_pr_sheet_collector_2636.py:92: in test_e01_a_malformed_list_number_is_refused
    assert problems_of(records, advisor) == [NEEDS_NUMBER]
test_pr_sheet.py:57: in problems_of
    with pytest.raises(pr_sheet.Refusal) as caught:
E   Failed: DID NOT RAISE Refusal
FAILED ...::test_e01_a_malformed_list_number_is_refused[e01-refused-'02273']
FAILED ...::test_e01_a_malformed_list_number_is_refused[e01-refused-'2273-01']
FAILED ...::test_e01_a_malformed_list_number_is_refused[e01-refused-'2273-0']
FAILED ...::test_e01_a_malformed_list_number_is_refused[e01-refused-'0']
4 failed, 9 passed, 37 deselected in 1.96s
```

- **Restore:** the inverse Edit.
- **Restore receipt:** a Grep read printed `304:_LIST_NUMBER = re.compile(r"[1-9]\d*(?:-[1-9]\d*)?", re.ASCII)`.
- **Raw green** (same `-k`):

```
.............                                                            [100%]
13 passed, 37 deselected in 1.61s
```

## E2: a duplicate across spellings

- **Guarded element / axis:** `pr_sheet.py:876` (`elif _list_key(number) in seen:`) and `:879` (`seen.append(_list_key(number))`). Axis: `2273` and `"2273"` are one item, so listing both repeats; the comparison is by the canonical key.
- **Neutralization:** both `_list_key(number)` became `number` (duplicates compared as written), in one Edit over the four adjacent lines.
- **Raw red** (`-k e02`):

```
F                                                                        [100%]
___ test_e02_the_same_number_in_two_spellings_repeats ___
test_pr_sheet_collector_2636.py:99: in test_e02_the_same_number_in_two_spellings_repeats
    assert problems_of(records, advisor) == ["collectorItems 2273 repeats the number 2273"]
test_pr_sheet.py:57: in problems_of
    with pytest.raises(pr_sheet.Refusal) as caught:
E   Failed: DID NOT RAISE Refusal
FAILED ...::test_e02_the_same_number_in_two_spellings_repeats
1 failed, 49 deselected in 1.65s
```

- **Restore:** the inverse Edit.
- **Restore receipt:** a Grep read printed `876:        elif _list_key(number) in seen:` and `879:            seen.append(_list_key(number))`.
- **Raw green** (same `-k`):

```
.                                                                        [100%]
1 passed, 49 deselected in 1.50s
```

## E3: the own-number exemption

- **Guarded element / axis:** `pr_sheet.py:1104`, `if shown == own: continue` in `_dependencies`. Axis: a card's own collector number, dashed, in any scanned form (bare, `collector item`, `collector #`, `collector number`, `if you pick a on`, `card`), is not another question.
- **Neutralization:** `if shown == own:` became `if False:` (the own-number skip dropped).
- **Raw red** (`-k e03`). The tool display truncated the middle of this output ("[6941 characters truncated]"), so what follows is the incomplete capture: the first failure bodies are quoted once and the rest is the summary. All 12 rows failed the same way, with `pr_sheet.Refusal: ["dependent-question: collectorItems 2273-1: card '...' recommendation|option a depends on another question ('<the own form>') ..."]` raised at `pr_sheet.py:1585` (`raise Refusal(pointing + dependent)`):

```
FFFFFFFFFFFF                                                             [100%]
_ test_e03_a_cards_own_dashed_number_is_not_another_question[e03-2273-1-reason] _
test_pr_sheet_collector_2636.py:116: in test_e03_a_cards_own_dashed_number_is_not_another_question
    assert card_for(build(records, advisor), "2273-1")["question"] == card["title"]
pr_sheet.py:1585: in build
    raise Refusal(pointing + dependent)
E   pr_sheet.Refusal: ["dependent-question: collectorItems 2273-1: card 'Should the receipt page keep the old wording for gift orders?' recommendation depends on another question ('2273-1'); a question must be answerable on its own: ask the two as one card whose options name each combination, or hold this card until the other question is ruled and ask it then"]
[... 6941 characters truncated by the tool display; ten more rows of the same body ...]
FAILED ...::test_e03_a_cards_own_dashed_number_is_not_another_question[e03-2273-1-reason]
FAILED ...::test_e03_a_cards_own_dashed_number_is_not_another_question[e03-2273-1-consequence]
FAILED ...::test_e03_a_cards_own_dashed_number_is_not_another_question[e03-collector-item-2273-1-reason]
FAILED ...::test_e03_a_cards_own_dashed_number_is_not_another_question[e03-collector-item-2273-1-consequence]
FAILED ...::test_e03_a_cards_own_dashed_number_is_not_another_question[e03-collector-#2273-1-reason]
FAILED ...::test_e03_a_cards_own_dashed_number_is_not_another_question[e03-collector-#2273-1-consequence]
FAILED ...::test_e03_a_cards_own_dashed_number_is_not_another_question[e03-collector-number-2273-1-reason]
FAILED ...::test_e03_a_cards_own_dashed_number_is_not_another_question[e03-collector-number-2273-1-consequence]
FAILED ...::test_e03_a_cards_own_dashed_number_is_not_another_question[e03-if-you-pick-a-on-2273-1-reason]
FAILED ...::test_e03_a_cards_own_dashed_number_is_not_another_question[e03-if-you-pick-a-on-2273-1-consequence]
FAILED ...::test_e03_a_cards_own_dashed_number_is_not_another_question[e03-card-2273-1-reason]
FAILED ...::test_e03_a_cards_own_dashed_number_is_not_another_question[e03-card-2273-1-consequence]
12 failed, 38 deselected in 3.27s
```

- **Restore:** the inverse Edit.
- **Restore receipt:** a Grep read printed `1104:                if shown == own:` and `1105:                    continue`.
- **Raw green** (same `-k`):

```
............                                                             [100%]
12 passed, 38 deselected in 1.71s
```

## E4: another dashed item is still another question

- **Guarded element / axis:** `pr_sheet.py:1104`, `if shown == own:` in `_dependencies` (the same line as E3, the other axis of it). Axis: the exemption compares the whole canonical number, so `2273-2`, `2273-10` and `collector #2273-2` on card `2273-1`, and `2273-1` on plain card `2273`, are still another question.
- **Neutralization:** `if shown == own:` became `if shown.split("-")[0] == own.split("-")[0]:` (only the base digits compared).
- **Raw red** (`-k e04`, run with `--tb=line`, not `--tb=short`, to keep the capture short):

```
.FF.F..                                                                  [100%]
E   Failed: DID NOT RAISE Refusal   (x3, one per failed row)
FAILED ...::test_e04_another_dashed_item_is_still_another_question[e04-other-2273-10]
FAILED ...::test_e04_another_dashed_item_is_still_another_question[e04-other-collector-#2273-2]
FAILED ...::test_e04_a_plain_card_naming_a_dashed_item_is_refused
3 failed, 4 passed, 43 deselected in 1.60s
```

  The rows `e04-other-2273-2` and `e04-other-if-you-pick-a-on-2273-2` stay green under the neutralization: card `2273-2` is on the sheet, so the bare scan (D7) refuses them whatever the exemption does. The one-field row and the `7-123` row stay green too: the one-field row's other number is caught by D7 as well, and `7-123` has no own-number involvement. The three red rows are the ones that carry this element.
- **Restore:** the inverse Edit.
- **Restore receipt:** a Grep read printed `1104:                if shown == own:` and `1105:                    continue`.
- **Raw green** (same `-k`, `--tb=line`):

```
.......                                                                  [100%]
7 passed, 43 deselected in 1.52s
```

## E5: a carriedBy naming no card

- **Guarded element / axis:** `pr_sheet.py:829`, `elif _list_key(call["carriedBy"]) not in on_sheet:`. Axis: a carriedBy must name a collectorItems card on this sheet, so a carried finding is never listed on no card.
- **Neutralization:** the condition became `elif False:`.
- **Raw red** (`-k e05`):

```
F                                                                        [100%]
___ test_e05_a_carriedBy_naming_no_card_is_refused ___
test_pr_sheet_collector_2636.py:169: in test_e05_a_carriedBy_naming_no_card_is_refused
    assert problems_of(records, advisor) == [
test_pr_sheet.py:57: in problems_of
    with pytest.raises(pr_sheet.Refusal) as caught:
E   Failed: DID NOT RAISE Refusal
FAILED ...::test_e05_a_carriedBy_naming_no_card_is_refused
1 failed, 49 deselected in 1.59s
```

- **Restore:** the inverse Edit.
- **Restore receipt:** a Grep read printed `829:            elif _list_key(call["carriedBy"]) not in on_sheet:`.
- **Raw green** (same `-k`):

```
.                                                                        [100%]
1 passed, 49 deselected in 1.57s
```

## E6: a malformed carriedBy (a key beside it)

- **Guarded element / axis:** `pr_sheet.py:824`, `if len(call) > 1:`. Axis: carriedBy stands alone in its entry; a key beside it is refused with `carriedBy takes no other key`.
- **Neutralization:** `if len(call) > 1:` became `if False:`.
- **Raw red** (`-k e06`). This red is a crash, not a missing refusal: with the check off, the entry (which is then not exactly `{"carriedBy": ...}`) reaches the leftover-card builder, which raises `KeyError: 'options'`. It is red on the axis "a refusal, not a crash":

```
.F.                                                                      [100%]
___ test_e06_a_malformed_carriedBy_is_refused[e06-another-key] ___
test_pr_sheet_collector_2636.py:182: in test_e06_a_malformed_carriedBy_is_refused
    assert problems_of(records, advisor) == [f"leftovers {GIFT['findingKey']}: {expected}"]
test_pr_sheet.py:58: in problems_of
    build(records, advisor, previous)
test_pr_sheet.py:49: in build
    return pr_sheet.build(copy.deepcopy(records), copy.deepcopy(advisor), WORDS, previous=previous)
pr_sheet.py:1530: in build
    options = _options(call["options"], words, True)
E   KeyError: 'options'
FAILED ...::test_e06_a_malformed_carriedBy_is_refused[e06-another-key]
1 failed, 2 passed, 47 deselected in 1.95s
```

- **Restore:** the inverse Edit.
- **Restore receipt:** a Grep read printed `824:            if len(call) > 1:` and `825:                problems.append(f"leftovers {k}: carriedBy takes no other key")`.
- **Raw green** (same `-k`):

```
...                                                                      [100%]
3 passed, 47 deselected in 1.67s
```

- **Supplementary proof of the sibling branch.** The other two e06 rows (`e06-leading-zero`, `e06-null`) guard `elif not _list_number(call["carriedBy"]):` (`:826`), which the neutralization above does not touch (they stayed green under it). One more neutralization, made and undone the same way, covers them: `elif not _list_number(call["carriedBy"]):` became `elif False:`. Raw red (`-k e06`, `--tb=line`; with the check off the malformed value falls through to the names-no-card check, so the refusal exists but carries the wrong problem text):

```
F.F                                                                      [100%]
E   AssertionError: assert ['leftovers s... that number'] == ['leftovers s...ing N or N-M']
      At index 0 diff: 'leftovers shop/gift-tone: carriedBy 02273 names no list-item card on this sheet; give a collectorItems entry with that number' != 'leftovers shop/gift-tone: carriedBy must be a list-item number, an integer 1 or more or a string N or N-M'
E   AssertionError: assert ['leftovers s... that number'] == ['leftovers s...ing N or N-M']
      At index 0 diff: 'leftovers shop/gift-tone: carriedBy None names no list-item card on this sheet; give a collectorItems entry with that number' != 'leftovers shop/gift-tone: carriedBy must be a list-item number, an integer 1 or more or a string N or N-M'
FAILED ...::test_e06_a_malformed_carriedBy_is_refused[e06-leading-zero]
FAILED ...::test_e06_a_malformed_carriedBy_is_refused[e06-null]
2 failed, 1 passed, 47 deselected in 1.77s
```

  Restore: the inverse Edit. Restore receipt: a Grep read printed `826:            elif not _list_number(call["carriedBy"]):` and `827:                problems.append(f"leftovers {k}: carriedBy must be a list-item number, an integer 1 or more or a string N or N-M")`. Raw green (`-k e06`, `--tb=line`):

```
...                                                                      [100%]
3 passed, 47 deselected in 1.73s
```

## E7: the alias conflict

- **Guarded element / axis:** `pr_sheet.py:1462`, `if len(entered) > 1 and any(_carries(leftovers[k]) for k in entered):` in `build`'s disposition loop. Axis: a finding has one disposition; a carriedBy under one of its keys beside a second leftovers entry under another is refused (`give one entry`).
- **Neutralization:** `len(entered) > 1 and` became `False and`.
- **Raw red** (`-k e07`):

```
F                                                                        [100%]
___ test_e07_a_carriedBy_beside_a_second_entry_for_the_same_finding_is_refused ___
test_pr_sheet_collector_2636.py:189: in test_e07_a_carriedBy_beside_a_second_entry_for_the_same_finding_is_refused
    problems = problems_of(records, advisor)
test_pr_sheet.py:57: in problems_of
    with pytest.raises(pr_sheet.Refusal) as caught:
E   Failed: DID NOT RAISE Refusal
FAILED ...::test_e07_a_carriedBy_beside_a_second_entry_for_the_same_finding_is_refused
1 failed, 49 deselected in 2.26s
```

- **Restore:** the inverse Edit.
- **Restore receipt:** a Grep read printed `1462:                if len(entered) > 1 and any(_carries(leftovers[k]) for k in entered):`.
- **Raw green** (same `-k`):

```
.                                                                        [100%]
1 passed, 49 deselected in 1.66s
```

## E8: a carried finding makes no card of its own

- **Guarded element / axis:** `pr_sheet.py:1526`, `if _carried(call):` in `build`'s card loop. Axis: a finding whose leftovers value is carriedBy makes no `f-` card (the sheet's collector cards are all its cards), whichever way the card's number and the carriedBy are spelled (int, string, dashed).
- **Neutralization:** `if _carried(call):` became `if False and _carried(call):` (the carried finding falls through to the leftover-card builder).
- **Raw red** (`-k e08`, run with `--tb=line`). The red is a crash: the carried value has no `options`, so the fall-through raises `KeyError`; it is red on the axis "no card of its own":

```
FFF                                                                      [100%]
E   KeyError: 'options'   (x3, one per row)
pr_sheet.py:1530: KeyError: 'options'
FAILED ...::test_e08_a_carried_finding_makes_no_card_of_its_own[e08-int-card]
FAILED ...::test_e08_a_carried_finding_makes_no_card_of_its_own[e08-string-card]
FAILED ...::test_e08_a_carried_finding_makes_no_card_of_its_own[e08-dashed-card]
3 failed, 47 deselected in 1.59s
```

- **Restore:** the inverse Edit.
- **Restore receipt:** a Grep read printed `1526:            if _carried(call):`.
- **Raw green** (same `-k`, `--tb=line`):

```
...                                                                      [100%]
3 passed, 47 deselected in 1.63s
```

## E9: a carried finding is no decided-for-you entry

- **Guarded element / axis:** `pr_sheet.py:1528-1529`, the carried branch of `build`'s card loop (`carried.setdefault(...)` then `continue`). Axis: a carried finding is in no `prSheet.decidedForYou` entry; a real craft determination for another finding still is.
- **Neutralization:** one line inserted before the `continue`: `decided_for_you.append({"id": card_id("d-", r["pr"], f.get("findingKey") or f["id"], "decided-for-you"), "finding": _lookups(kind, r["pr"], f)[0], "title": _title(f), "ground": "x", "reason": "x"})`.
- **Raw red** (`-k e09`):

```
F                                                                        [100%]
___ test_e09_a_carried_finding_is_not_a_decided_for_you_entry ___
test_pr_sheet_collector_2636.py:205: in test_e09_a_carried_finding_is_not_a_decided_for_you_entry
    assert [e["title"] for e in sheet["prSheet"]["decidedForYou"]] == [TOTAL["title"]]
E   AssertionError: assert ['Gift receip...ow the total'] == ['The thank-y...ow the total']
E     At index 0 diff: 'Gift receipts read oddly to the buyer' != 'The thank-you line may show the total'
E     Left contains one more item: 'The thank-you line may show the total'
FAILED ...::test_e09_a_carried_finding_is_not_a_decided_for_you_entry
1 failed, 49 deselected in 1.69s
```

- **Restore:** the inverse Edit (the inserted line removed).
- **Restore receipt:** a Grep read printed `1528:                carried.setdefault(_list_key(call["carriedBy"]), []).append((_lookups(kind, r["pr"], f)[0], tag(r) + _title(f)))`, `1529:                continue`, `1530:            options = _options(call["options"], words, True)`.
- **Raw green** (same `-k`):

```
.                                                                        [100%]
1 passed, 49 deselected in 1.64s
```

## E10: the carried section

- **Guarded element / axis:** `pr_sheet.py:1562`, `*([_section(words["carriedTitle"], "bullets", [line for _, line in lines])] if lines else [])` in the collector card loop. Axis: the card that carries findings ends with a section titled by the words' `carriedTitle`, a bullets block of each carried finding's line in record order (`#<pr>: ` first on a stack); a card that carries none has no such section.
- **Neutralization:** `if lines else []` became `if False else []` (the section is never appended). The same edit serves E14, whose red was run while it stood; the restore below precedes both greens.
- **Raw red** (`-k e10`):

```
FF                                                                       [100%]
___ test_e10_the_carrying_card_lists_each_carried_finding_last_and_a_card_carrying_none_has_no_section ___
test_pr_sheet_collector_2636.py:213: in ...
    assert card_for(sheet, 2273)["context"][-1] == {"title": WORDS["carriedTitle"], "blocks": [{"bullets": [GIFT["title"], TOTAL["title"], FONT["title"]]}]}
E   AssertionError: assert {'title': 'If...s as well.'}]} == {'title': 'Th...een pages']}]}
E     {'title': 'If left'} != {'title': 'The review findings this decides'}
___ test_e10_on_a_stack_each_carried_line_starts_with_its_pr ___
test_pr_sheet_collector_2636.py:223: in test_e10_on_a_stack_each_carried_line_starts_with_its_pr
    assert card_for(sheet, number)["context"][-1] == {"title": WORDS["carriedTitle"], "blocks": [{"bullets": lines}]}
E   AssertionError: assert {'title': 'If...s as well.'}]} == {'title': 'Th...ut spaces']}]}
E     {'blocks': [{'paragraph': 'The new wording ships on gift receipts as well.'}]} != {'blocks': [{'bullets': ['#5: Gift card numbers print without spaces']}]}
FAILED ...::test_e10_the_carrying_card_lists_each_carried_finding_last_and_a_card_carrying_none_has_no_section
FAILED ...::test_e10_on_a_stack_each_carried_line_starts_with_its_pr
2 failed, 48 deselected in 1.74s
```

- **Restore:** the inverse Edit.
- **Restore receipt:** a Grep read printed `1562:                            *([_section(words["carriedTitle"], "bullets", [line for _, line in lines])] if lines else [])],`.
- **Raw green** (same `-k`):

```
..                                                                       [100%]
2 passed, 48 deselected in 1.67s
```

## E14: the page

- **Guarded element / axis:** the same line as E10 (`pr_sheet.py:1562`), seen through the page. Axis: the page shows the dashed number on each card's badge, each carried finding (with its `#<pr>: ` prefix) inside its own card's article and not the other's, none in the decided-for-you part, and answering every card with a non-send-back option unlocks Merge.
- **Neutralization:** the E10 edit (`if lines else []` became `if False else []`), still in place from the E10 red.
- **Raw red** (`-k e14`):

```
F                                                                        [100%]
___ test_e14_the_page_shows_each_carried_finding_on_its_own_card_and_the_answers_unlock_merge ___
test_pr_sheet_collector_2636.py:305: in test_e14_the_page_shows_each_carried_finding_on_its_own_card_and_the_answers_unlock_merge
    assert line in mine and line not in other
E   assert ('#5: Gift card numbers print without spaces' in "From your list · item 2273-1 Should the receipt page keep the old wording for gift orders? Why it's yours What a gift...g everywhere b. Keep the old wording for gift orders c. Hold the PR until gift orders are reworded Something else Note")
FAILED ...::test_e14_the_page_shows_each_carried_finding_on_its_own_card_and_the_answers_unlock_merge
1 failed, 49 deselected in 1.72s
```

- **Restore:** the inverse Edit (the E10 restore).
- **Restore receipt:** the E10 receipt above.
- **Raw green** (`-k e14`):

```
.                                                                        [100%]
1 passed, 49 deselected in 1.73s
```

## E11: the carried identity is in the card id

- **Guarded element / axis:** `pr_sheet.py:1557`, `[it["number"], [k for k, _ in lines]] if lines else it["number"]` as the identity passed to `_card`. Axis: a card's id changes with what it carries (the finding's key, not only its title) and is stable across builds; a card that carries nothing keeps its id from base (`k-42f04a278896`, `k-3fb4fe9f3b5f`).
- **Neutralization:** the identity became `it["number"]` (the number alone).
- **Raw red** (`-k e11`). Of the two e11 tests only the first is red: the second pins the base ids of cards that carry nothing, which this neutralization does not move. The first test was edited once before this red (its last assertion compared the 1501 card across two sheets in which 1501 itself carried the finding; it now compares the 2273 card that carries nothing with the same card on a sheet with no finding at all), so the first red is not a run of the file as first written:

```
F.                                                                       [100%]
___ test_e11_the_carried_identity_is_in_the_card_id ___
test_pr_sheet_collector_2636.py:233: in test_e11_the_carried_identity_is_in_the_card_id
    assert card_for(gift, 2273)["id"] != card_for(twin, 2273)["id"]
E   AssertionError: assert 'k-107df0253890' != 'k-107df0253890'
FAILED ...::test_e11_the_carried_identity_is_in_the_card_id
1 failed, 1 passed, 48 deselected in 1.60s
```

- **Restore:** the inverse Edit.
- **Restore receipt:** a Grep read printed `1557:        cards.append(_card("k-", number, [it["number"], [k for k, _ in lines]] if lines else it["number"],`.
- **Raw green** (same `-k`):

```
..                                                                       [100%]
2 passed, 48 deselected in 1.56s
```

## E12: a missing or blank carriedTitle

- **Guarded element / axis:** `pr_sheet.py:1493`, `if carrying and not _text(words.get("carriedTitle")):`. Axis: a carried finding needs the words' `carriedTitle`; its absence, a blank one or a null one is one refusal naming it, never a crash.
- **Neutralization:** `carrying and` became `False and`. The red is a crash, not a missing refusal: the card builder then reads `words["carriedTitle"]` and raises `KeyError`; it is red on the axis "a refusal, not a crash".
- **Raw red** (`-k e12`). The second e12 test (a sheet that carries nothing needs no carriedTitle) stays green, as designed:

```
F.                                                                       [100%]
___ test_e12_a_missing_or_blank_carriedTitle_is_a_refusal_naming_it_when_a_finding_is_carried ___
test_pr_sheet_collector_2636.py:259: in ...
    pr_sheet.build(copy.deepcopy(records), copy.deepcopy(advisor), words)
pr_sheet.py:1562: in build
    *([_section(words["carriedTitle"], "bullets", [line for _, line in lines])] if lines else [])],
E   KeyError: 'carriedTitle'
FAILED ...::test_e12_a_missing_or_blank_carriedTitle_is_a_refusal_naming_it_when_a_finding_is_carried
1 failed, 1 passed, 48 deselected in 1.73s
```

- **Restore:** the inverse Edit.
- **Restore receipt:** a Grep read printed `1493:    if carrying and not _text(words.get("carriedTitle")):`.
- **Raw green** (same `-k`):

```
..                                                                       [100%]
2 passed, 48 deselected in 1.69s
```

## E13: byte identity with base

- **Guarded element / axis:** `pr_sheet.py:1557`, the `else it["number"]` arm of the identity passed to `_card` (and, through it, every byte of a card that carries nothing). Axis: an input that uses neither new feature builds, through the command, the bytes the base commit `af6cfd27` built; the expected file `fixtures/pr_sheet/expected-collector-2636.json` was written by the command at base before any `pr_sheet.py` edit, and `cmp` showed it identical to a second base build.
- **Neutralization:** `else it["number"]` became `else str(it["number"])` (the id of an integer-numbered card hashed from its string, not its integer).
- **Raw red** (`-k e13`):

```
F                                                                        [100%]
___ test_e13_an_input_that_uses_neither_feature_builds_the_bytes_the_base_built ___
test_pr_sheet_collector_2636.py:278: in test_e13_an_input_that_uses_neither_feature_builds_the_bytes_the_base_built
    assert out.read_bytes() == (FIXTURES / "expected-collector-2636.json").read_bytes()
E   assert b'{\n  "schem...  }\n  ]\n}\n' == b'{\n  "schem...  }\n  ]\n}\n'
E     At index 872 diff: b'f' != b'4'
FAILED ...::test_e13_an_input_that_uses_neither_feature_builds_the_bytes_the_base_built
1 failed, 49 deselected in 2.32s
```

- **Restore:** the inverse Edit.
- **Restore receipt:** a Grep read printed `1557:        cards.append(_card("k-", number, [it["number"], [k for k, _ in lines]] if lines else it["number"],`.
- **Raw green** (same `-k`):

```
.                                                                        [100%]
1 passed, 49 deselected in 2.16s
```

## Whole scoped run and disclosures

- The final scoped run (the eight files the order names, `-n auto`) was made after E13's green and before the E6 supplementary proof; the code it ran is the code the supplementary proof restored to (every restore was read back by Grep). Its output ended `1451 passed in 50.70s`.
- E10 and E14 share one neutralization (`if lines else []` became `if False else []`): E10's red, then E14's red, then one restore, then E10's green and E14's green.
- E4's, E8's and E6's supplementary runs used `--tb=line`; the others used `--tb=short` as the order gives.
- E3's red capture is incomplete: the tool display truncated its middle ("[6941 characters truncated]"), and the entry says so. All twelve failures are listed in its summary lines.
- The first run of the file (before any bite-proof run) was 49 passed, 1 failed: `test_e11_the_carried_identity_is_in_the_card_id` asserted that the 1501 card has the same id on two sheets in one of which 1501 itself carried the finding. That was the test's mistake, not the code's; the assertion was rewritten (see E11) before E11's red.
- Elements whose red is a crash and not a missing refusal: E6 (`KeyError: 'options'`), E8 (`KeyError: 'options'`), E12 (`KeyError: 'carriedTitle'`). Each is red on the axis "a refusal, not a crash" or "no card of its own".
- E13's expected file was written by the command from the unedited base tree, before the first `pr_sheet.py` edit, and `cmp` showed it identical to a second base build written to a scratch file.

## Review round 1 fixes: E15 and E16

Two elements added by the build session's review fix step (review-code round 1, findings on the conditional form of the own-number exemption and on the card id of a plain number's two spellings). The proofs were run by the build session, with the same rules as above (one targeted Edit-tool neutralization, the inverse Edit, no `git checkout`, `restore`, `reset`, `stash` or `sed`), and the prefix `scripts/pinned-python -B -X pycache_prefix=<session scratch>/pyc-probe -m pytest ... -q -p no:cacheprovider --tb=line`. Captures are trimmed to the summary lines; the uv deprecation warning line is dropped. Nothing was redacted.

### E15: a conditional whose target is the card's own number

- **Guarded element / axis:** `pr_sheet.py:1120`, `if target and target.group(1) == own:` (with `_TARGET_AFTER` at `:1118`). Axis: a `_DEPENDS` hit that ends on its target noun ("if you pick a on card", "on collector") and is followed by the card's own number is not another question; one followed by another number still is.
- **Neutralization:** `if target and target.group(1) == own:` became `if False:`.
- **Raw red** (files `test_pr_sheet_collector_2636.py`, `test_pr_sheet_collector_2636_conditional.py`, `test_pr_sheet_own_collector_reference_2636.py`; `-k "e03 or e15 or conditional or condition_can"`):

```
FAILED ...test_pr_sheet_collector_2636.py::test_e03_a_cards_own_dashed_number_is_not_another_question[e03-if-you-pick-a-on-card-2273-1-reason]
FAILED ...test_pr_sheet_collector_2636.py::test_e03_a_cards_own_dashed_number_is_not_another_question[e03-if-you-pick-a-on-card-2273-1-consequence]
FAILED ...test_pr_sheet_collector_2636.py::test_e03_a_cards_own_dashed_number_is_not_another_question[e03-if-you-pick-a-on-collector-item-2273-1-reason]
FAILED ...test_pr_sheet_collector_2636.py::test_e03_a_cards_own_dashed_number_is_not_another_question[e03-if-you-pick-a-on-collector-item-2273-1-consequence]
FAILED ...test_pr_sheet_collector_2636.py::test_e03_a_cards_own_dashed_number_is_not_another_question[e03-only-if-you-pick-b-on-card-#2273-1-reason]
FAILED ...test_pr_sheet_collector_2636.py::test_e03_a_cards_own_dashed_number_is_not_another_question[e03-only-if-you-pick-b-on-card-#2273-1-consequence]
FAILED ...test_pr_sheet_collector_2636.py::test_e15_a_field_naming_its_own_card_in_a_conditional_beside_another_item_reports_only_the_other
FAILED ...test_pr_sheet_collector_2636_conditional.py::test_conditional_can_name_its_own_dashed_card
FAILED ...test_pr_sheet_own_collector_reference_2636.py::test_a_condition_can_name_the_cards_own_dashed_collector_item
9 failed, 12 passed, 42 deselected in 2.25s
```

  Each red is the `dependent-question` refusal on the own conditional, for example `depends on another question ('if you pick a on card')`.
- **Restore:** the inverse Edit.
- **Restore receipt:** the restored line reads `if target and target.group(1) == own:` at `:1120`; `git status --porcelain` showed only the review fix step's own uncommitted edits.
- **Raw green** (same selection): `21 passed, 42 deselected in 2.25s`.
- The other-number side of the axis (`e04-other-if-you-pick-a-on-card-2273-2`, `e04-other-if-you-pick-a-on-collector-item-2273-2`, `e04-other-if-you-pick-a-on-the-other-card`, and the `both == other_only` leg of e15) stays green under this neutralization, as designed: those texts are refused with or without the exemption.

### E16: one card id for a plain number in either spelling

- **Guarded element / axis:** `pr_sheet.py:1574`, the card-id identity `_card_number(it["number"])` (the helper `_card_number`). Axis: 2273 and "2273" give one card id, so a republish that changes only the number's JSON type keeps the saved answer.
- **Neutralization:** the no-carry branch `else _card_number(it["number"])` became `else it["number"]`.
- **Raw red** (`-k "e16 or e11 or e13"`):

```
E   AssertionError: assert 'k-16ebf59a8c01' == 'k-f6536279684f'
FAILED ...::test_e16_a_plain_number_keeps_one_card_id_in_either_spelling
1 failed, 3 passed, 57 deselected in 2.11s
```

  The e11 and e13 rows stay green under it, as designed: they pin the integer ids, which the neutralization does not change.
- **Restore:** the inverse Edit.
- **Restore receipt:** the restored line reads `... if lines else _card_number(it["number"]),` at `:1574`.
- **Raw green** (same `-k`): `4 passed, 57 deselected in 1.67s`.

## Review round 2 fixes: E17 and E18

Two elements added at review-code round 2's fix step, where the audit found that the E15 exemption ran after any hit and swallowed real cross-card dependencies. The rules and command shape are the round 1 entries' (`-k e15`, over `test_pr_sheet_collector_2636.py`).

### E17: the exemption reads only a choice made on a target

- **Guarded element / axis:** `pr_sheet.py`, `elif own is not None and _CHOICE_ON_NOUN.fullmatch(hit.group(0)):` (with `_CHOICE_ON_NOUN`). Axis: only a D1 hit that names a choice made on a target and ends on its noun is followed by its target's number; a positional hit (`card above`, `decisions above`) never is.
- **Neutralization:** the condition became `elif own is not None:`.
- **Raw red:**

```
FAILED ...::test_e15_the_cards_own_number_used_to_describe_another_card_is_still_another_question[e15-card-above]
FAILED ...::test_e15_the_cards_own_number_used_to_describe_another_card_is_still_another_question[e15-card-below]
FAILED ...::test_e15_the_cards_own_number_used_to_describe_another_card_is_still_another_question[e15-decisions-above]
3 failed, 4 passed, 60 deselected in 8.20s
```

  Each red is `DID NOT RAISE Refusal`. The possessive and list rows stay green under this neutralization, because E18's lookahead still refuses them; E18 proves those rows.
- **Restore:** the inverse Edit. **Restore receipt:** the line reads `elif own is not None and _CHOICE_ON_NOUN.fullmatch(hit.group(0)):` again.
- **Raw green:** `7 passed, 60 deselected in 6.00s`.

### E18: the number must complete the target

- **Guarded element / axis:** `_TARGET_AFTER`'s two lookaheads, `(?![\w'’-])(?!\s*(?:,|&|\band\b|\bor\b)\s*#?\d)`. Axis: a number that is a possessive (`2273-1's twin`) or one of several targets (`card 2273-1 or 12`) is not the whole target, so the choice still depends on another question.
- **Neutralization:** the two lookaheads became `(?![\w-])`.
- **Raw red** (run after the row `e15-one-of-several-targets` was added to the parametrize, so the list leg has a row that only this element guards):

```
FAILED ...::test_e15_the_cards_own_number_used_to_describe_another_card_is_still_another_question[e15-possessive-target]
FAILED ...::test_e15_the_cards_own_number_used_to_describe_another_card_is_still_another_question[e15-one-of-several-targets]
2 failed, 6 passed, 60 deselected in 1.68s
```

- **Restore:** the inverse Edit. **Restore receipt:** the pattern reads `#?(\d+(?:-\d+)?)(?![\w'’-])(?!\s*(?:,|&|\band\b|\bor\b)\s*#?\d)` again.
- **Raw green:** `8 passed, 60 deselected in 2.67s`.
- Disclosure: a first E18 run, before the `e15-one-of-several-targets` row existed, reddened only `e15-possessive-target` (`1 failed, 6 passed`). The plural-list row `e15-a-list-of-cards` is guarded by E17 (a plural noun is not a choice target), not by E18.
