# Work order WO-2 (#2493, #2494) bite-proof: the merge sheet lists what the record lists, and cards only what waits

**Provenance:** claude / sonnet-5.5 (implementer, WO-2), maker family claude. Production under proof: `plugins/superheroes/lib/pr_sheet.py` (`_record`, `_check_accounting`, `build`). Detector file: `plugins/superheroes/lib/tests/test_pr_sheet_listed_2493.py`.

Declared guarded-element set (from the order): **E-card**, **E-listed**, **E-null**, **E-null-important**, **E-consequence**, **E-account**, **E-census**. Seven elements, seven entries; no equivalence class is used. Elements the same file asserts that the order declared no neutralization for (the sheet-words keys, the schema's `listed` part, the page's `buildFolded("pr-listed"` line and `PR_WORD_KEYS` entry, `sheet_prose`'s listed row, the history `owned` list, the `_fixed_above` waiting reads, the `listed_keys` count) have **no neutralization run**: they are **unproven** by this record. The schema, prose and page tests (S-schema, S-prose, S-page) were run green only.

Every command is `scripts/pinned-python -B -X pycache_prefix=/tmp/claude-0/superheroes-pyc-wo2 -m pytest <target> -q -p no:xdist`, with the test node id, or `<file> -k <name>` for a test with parameters. The leading `warning: The UV_NATIVE_TLS environment variable is deprecated ...` line of every run is left out; it is the launcher's, not pytest's. Each neutralization is one Edit-tool edit, restored by the inverse Edit-tool edit; no `git checkout`, `git restore`, `git reset` or `git stash` was used. Nothing quoted is a secret, token, private URL or personal detail, so nothing is redacted. Where the tool output was cut by the harness the capture says so; the red tracebacks that are cut keep their first and last lines. Every capture is far under the 32 KiB per element and 128 KiB ceilings.

## E-census: no copy of the sheet's own outcome-plus-repeat question

- **guarded element:** `pr_sheet.py` reads "waits for the owner" only through `review_record.waits_for_owner`.
- **axis:** a copy of `== _LEFT` / `!= _LEFT` followed within 120 characters by `repeat_held_elsewhere`.
- **neutralization (disclosed deviation):** the order asked for a run on the unchanged base before the change. The production edits were already in the tree when the detector was written, so the red is **not a run on the base `9fded0c2`**. It is the detector run after the Edit tool put the five old sites back, each exactly as the base had it (`_fixed_above`'s `leftForOwner` rebuild, `_fixed_above`'s `held` list, the accounting loop, the card loop, the history `owned` list). The copies counted are 5, the count the order gives for the base. The five were then re-applied by the inverse Edits.
- **detector:** `test_s_census_the_sheet_never_asks_its_own_outcome_plus_repeat_question`

### raw red

```
F                                                                        [100%]
=================================== FAILURES ===================================
___ test_s_census_the_sheet_never_asks_its_own_outcome_plus_repeat_question ____

    def test_s_census_the_sheet_never_asks_its_own_outcome_plus_repeat_question():
        """axis: E-census: no left-for-owner outcome comparison in pr_sheet.py is followed within 120 characters by repeat_held_elsewhere."""
        source = (LIB / "pr_sheet.py").read_text(encoding="utf-8")
        copies = re.findall(r"(?:==|!=)\s*_LEFT\b[\s\S]{0,120}?repeat_held_elsewhere", source)
>       assert copies == [], f"{len(copies)} copies of the outcome-plus-repeat question remain in pr_sheet.py"
E       AssertionError: 5 copies of the outcome-plus-repeat question remain in pr_sheet.py
E       assert ['== _LEFT\n ...ld_elsewhere'] == []
E         
E         Left contains 5 more items, first extra item: '== _LEFT\n                                      and not review_record.repeat_held_elsewhere'
E         Use -v to get more diff

/home/user/wt-2493/plugins/superheroes/lib/tests/test_pr_sheet_listed_2493.py:170: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_pr_sheet_listed_2493.py::test_s_census_the_sheet_never_asks_its_own_outcome_plus_repeat_question
1 failed in 0.94s
```

### restore

The five inverse Edits (each site back to `review_record.waits_for_owner(f, r["findings"])`).

### restore receipt

The restored lines, as the file holds them (the card-loop line is quoted again under E-card; the other four are in the file at `_fixed_above` and the two `build` loops):

```
            record["leftForOwner"] = [review_record._name(f) for f in r["findings"] if review_record.waits_for_owner(f, r["findings"])]
            held = [n for n, f in enumerate(r["findings"]) if review_record.waits_for_owner(f, r["findings"])
            if review_record.waits_for_owner(f, r["findings"]):
            if not review_record.waits_for_owner(f, r["findings"]) or (r["pr"], n) in fixed:
        owned = [review_record.leftover_line(f) for f in r["findings"] if review_record.waits_for_owner(f, r["findings"])]
```

### raw green

```
.                                                                        [100%]
1 passed in 1.11s
```

## E-card: the card loop's waits_for_owner test

- **guarded element:** `pr_sheet.py` card loop, `if not review_record.waits_for_owner(f, r["findings"]) or (r["pr"], n) in fixed:` (the line at 1351).
- **axis:** a card is exactly a finding the record's `waits_for_owner` names; a listed finding is no card.
- **neutralization:** that clause back to `f["outcome"] != _LEFT or review_record.repeat_held_elsewhere(f, r["findings"])`, the line's trailing `or (r["pr"], n) in fixed` unchanged.
- **detector:** `test_s_card_a_listed_minor_is_in_the_listed_part_and_only_the_waiting_minor_is_a_card`

### raw red (tool output cut by the harness in the middle of the traceback; the cut is 2592 characters of `build` source echo; first and last lines kept)

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_s_card_a_listed_minor_is_in_the_listed_part_and_only_the_waiting_minor_is_a_card _

    def test_s_card_a_listed_minor_is_in_the_listed_part_and_only_the_waiting_minor_is_a_card():
        """axis: E-card, E-listed: the card loop cards exactly what waits, and the listed part holds exactly what the record lists."""
        listed, waiting = minor("L1", False), minor("W1", True)
>       sheet = build([record(10, [listed, waiting])], pr_input(leftovers={waiting["findingKey"]: ENTRY}))
...
[... 2592 characters truncated by the harness ...]
...
                call = _leftover_call(kind, r["pr"], f, leftovers)
>               options = _options(call["options"], words, True)
                                   ^^^^^^^^^^^^^^^
E               KeyError: 'options'

/home/user/wt-2493/plugins/superheroes/lib/pr_sheet.py:1360: KeyError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_pr_sheet_listed_2493.py::test_s_card_a_listed_minor_is_in_the_listed_part_and_only_the_waiting_minor_is_a_card
1 failed in 1.10s
```

### restore

Inverse Edit: the neutralized clause back to `if not review_record.waits_for_owner(f, r["findings"]) or (r["pr"], n) in fixed:`.

### restore receipt

```
1351:            if not review_record.waits_for_owner(f, r["findings"]) or (r["pr"], n) in fixed:
```

### raw green

```
.                                                                        [100%]
1 passed in 0.91s
```

## E-listed: the listed collection

- **guarded element:** `pr_sheet.py` `build`, `if review_record.listed_for_merge(f):` in the history/outcomes loop (1420) that appends to `merge_listed`.
- **axis:** the listed part holds exactly the findings the record lists for the merge verdict.
- **neutralization:** that predicate to `False`.
- **detector:** `test_s_card_a_listed_minor_is_in_the_listed_part_and_only_the_waiting_minor_is_a_card`

### raw red

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_s_card_a_listed_minor_is_in_the_listed_part_and_only_the_waiting_minor_is_a_card _

    def test_s_card_a_listed_minor_is_in_the_listed_part_and_only_the_waiting_minor_is_a_card():
        """axis: E-card, E-listed: the card loop cards exactly what waits, and the listed part holds exactly what the record lists."""
        listed, waiting = minor("L1", False), minor("W1", True)
        sheet = build([record(10, [listed, waiting])], pr_input(leftovers={waiting["findingKey"]: ENTRY}))
        assert [c["question"] for c in cards_of(sheet)] == ["Title of W1"]
>       assert sheet["prSheet"]["listed"] == [{"title": "Title of L1", "detail": "Minor: A label reads oddly."}]
               ^^^^^^^^^^^^^^^^^^^^^^^^^^
E       KeyError: 'listed'

/home/user/wt-2493/plugins/superheroes/lib/tests/test_pr_sheet_listed_2493.py:46: KeyError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_pr_sheet_listed_2493.py::test_s_card_a_listed_minor_is_in_the_listed_part_and_only_the_waiting_minor_is_a_card
1 failed in 0.96s
```

### restore

Inverse Edit: `if False:` back to `if review_record.listed_for_merge(f):`.

### restore receipt

```
1420:            if review_record.listed_for_merge(f):
1421-                reason = f.get("reason")
```

### raw green

```
.                                                                        [100%]
1 passed in 0.97s
```

## E-null: the validator's null admission

- **guarded element:** `pr_sheet.py` `_record`, the clause `not (out is None and (review_record.listed_for_merge(f) or waits))` (666).
- **axis:** a null outcome on a listed Minor or Nit (or a waiting one) is admitted.
- **neutralization:** `out is None` to `False`, so every null is refused.
- **detector:** `test_s_null_listed_a_no_outcome_minor_outside_every_risk_area_builds_and_is_listed` (both parameters, selected with `-k test_s_null_listed`)

### raw red (tool output cut by the harness: 11898 characters of `build` source echo between the first parameter's header and the end; first and last lines kept)

```
FF                                                                       [100%]
=================================== FAILURES ===================================
_ test_s_null_listed_a_no_outcome_minor_outside_every_risk_area_builds_and_is_listed[null] _

shape = 'null'

    @pytest.mark.parametrize("shape", ["null", "absent"])
    def test_s_null_listed_a_no_outcome_minor_outside_every_risk_area_builds_and_is_listed(shape):
        """axis: E-null: a null outcome on a listed Minor is admitted by the validator and shown with the no-outcome word."""
        found = minor("N1", False, outcome=None, reason=None, consequence=None)
        if shape == "absent":
            del found["outcome"]
>       sheet = build([record(10, [found])], pr_input())
...
[... 11898 characters truncated by the harness ...]
...
        if problems:
>           raise Refusal(problems)
E           pr_sheet.Refusal: ["record for PR #10: finding 'Title of N1' has outcome None, not one of fixed, shown-wrong, craft, left-for-owner, ruling"]

/home/user/wt-2493/plugins/superheroes/lib/pr_sheet.py:1341: Refusal
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_pr_sheet_listed_2493.py::test_s_null_listed_a_no_outcome_minor_outside_every_risk_area_builds_and_is_listed[null]
FAILED plugins/superheroes/lib/tests/test_pr_sheet_listed_2493.py::test_s_null_listed_a_no_outcome_minor_outside_every_risk_area_builds_and_is_listed[absent]
2 failed, 16 deselected in 1.35s
```

### restore

Inverse Edit: `not (False and (...))` back to `not (out is None and (...))`.

### restore receipt

```
666:        elif out not in rfs.OUTCOMES and not (out is None and (review_record.listed_for_merge(f) or waits)):
```

### raw green

```
..                                                                       [100%]
2 passed, 16 deselected in 0.97s
```

## E-null-important: the same admission, other direction

- **guarded element:** the same clause as E-null.
- **axis:** a no-outcome Important (any `inRiskArea`) stays refused; only a Minor or Nit may carry no outcome.
- **neutralization:** the admission to `not (out is None)`, so every null is admitted.
- **detector:** `test_s_null_important_a_no_outcome_important_is_still_refused` (three parameters, `-k test_s_null_important`)

### raw red

```
FFF                                                                      [100%]
=================================== FAILURES ===================================
_____ test_s_null_important_a_no_outcome_important_is_still_refused[True] ______

risk = True

    @pytest.mark.parametrize("risk", [True, False, UNSET])
    def test_s_null_important_a_no_outcome_important_is_still_refused(risk):
        """axis: E-null-important: only a Minor or Nit may carry no outcome; an Important with none is a missing outcome."""
        found = minor("I1", risk, outcome=None, severity="Important", reason=None, consequence=None)
>       problems = problems_of([record(10, [found])], pr_input())
                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

/home/user/wt-2493/plugins/superheroes/lib/tests/test_pr_sheet_listed_2493.py:83: 
...
E       Failed: DID NOT RAISE Refusal

/home/user/wt-2493/plugins/superheroes/lib/tests/test_pr_sheet.py:57: Failed
[the [False] and [risk2] (no inRiskArea) parameters fail the same way: DID NOT RAISE Refusal]
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_pr_sheet_listed_2493.py::test_s_null_important_a_no_outcome_important_is_still_refused[True]
FAILED plugins/superheroes/lib/tests/test_pr_sheet_listed_2493.py::test_s_null_important_a_no_outcome_important_is_still_refused[False]
FAILED plugins/superheroes/lib/tests/test_pr_sheet_listed_2493.py::test_s_null_important_a_no_outcome_important_is_still_refused[risk2]
3 failed, 15 deselected in 1.38s
```

(The middle lines marked `...` are the pytest echo of `problems_of` and the repeated parameter headers, shortened by me here; the full tool output had all three parameters in the same shape. This record's text is shortened; the run's own output was not truncated.)

### restore

Inverse Edit: `not (out is None)` back to `not (out is None and (review_record.listed_for_merge(f) or waits))`.

### restore receipt

```
666:        elif out not in rfs.OUTCOMES and not (out is None and (review_record.listed_for_merge(f) or waits)):
```

### raw green

```
...                                                                      [100%]
3 passed, 15 deselected in 1.10s
```

## E-consequence: a waiting finding needs a consequence

- **guarded element:** `pr_sheet.py` `_record`, `elif waits and not _text(f.get("consequence")):` (669).
- **axis:** the consequence requirement applies to every finding `waits_for_owner` names, whatever its outcome.
- **neutralization:** `waits` to `out == _LEFT`.
- **detector:** `test_s_null_card_a_no_outcome_minor_in_a_risk_area_is_a_card_and_needs_a_consequence`

### raw red

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_s_null_card_a_no_outcome_minor_in_a_risk_area_is_a_card_and_needs_a_consequence _

    def test_s_null_card_a_no_outcome_minor_in_a_risk_area_is_a_card_and_needs_a_consequence():
        """axis: E-consequence: a waiting finding needs a consequence whatever its outcome; a null-outcome one in a risk area is a card."""
        found = minor("R1", True, outcome=None, reason=None)
        sheet = build([record(10, [found])], pr_input(leftovers={found["findingKey"]: ENTRY}))
        assert [c["question"] for c in cards_of(sheet)] == ["Title of R1"] and "listed" not in sheet["prSheet"]
        bare = minor("R1", True, outcome=None, reason=None, consequence=None)
>       problems = problems_of([record(10, [bare])], pr_input(leftovers={bare["findingKey"]: ENTRY}))
                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

/home/user/wt-2493/plugins/superheroes/lib/tests/test_pr_sheet_listed_2493.py:75: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/home/user/wt-2493/plugins/superheroes/lib/tests/test_pr_sheet.py:58: in problems_of
    build(records, advisor, previous)
/home/user/wt-2493/plugins/superheroes/lib/tests/test_pr_sheet.py:49: in build
    return pr_sheet.build(copy.deepcopy(records), copy.deepcopy(advisor), WORDS, previous=previous)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/home/user/wt-2493/plugins/superheroes/lib/pr_sheet.py:1402: in build
    for where, card in zip(places, cards) if where is not None and not card["options"] for text in _shown(card) for found in _POINTER.finditer(text)]
                                                                                                   ^^^^^^^^^^^^
/home/user/wt-2493/plugins/superheroes/lib/pr_sheet.py:931: in _shown
    texts = [card["question"], *(t for b in blocks for v in b.values() for t in ([v] if isinstance(v, str) else v))]
            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E   TypeError: 'NoneType' object is not iterable

/home/user/wt-2493/plugins/superheroes/lib/pr_sheet.py:931: TypeError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_pr_sheet_listed_2493.py::test_s_null_card_a_no_outcome_minor_in_a_risk_area_is_a_card_and_needs_a_consequence
1 failed, 17 deselected in 1.17s
```

### restore

Inverse Edit: `elif out == _LEFT and not ...` back to `elif waits and not _text(f.get("consequence")):`.

### restore receipt

```
669:        elif waits and not _text(f.get("consequence")):
```

### raw green

```
.                                                                        [100%]
1 passed, 17 deselected in 0.92s
```

### later change (WO-5)

The red and green above were run on the clause as it read then. The clause and the key check below it now read `elif (out == _LEFT or waits) and not _text(f.get("consequence")):` (670) and `if _text(name) and (out == _LEFT or waits) and not (f.get("findingKey") or f.get("id")):` (674), so a left-for-owner repeat that another finding holds is asked for both again. The new test `test_s_record_a_held_left_for_owner_repeat_still_needs_a_consequence_and_a_key` (two parameters) ran green with the file (23 passed); **no neutralization was run for it** (the order named none and the command budget held no run for one), so it is **unproven** as a detector.

## E-account: the listed accounting target

- **guarded element:** `pr_sheet.py` `_check_accounting`, `elif targets[0] == "listed" and not (isinstance(value["listed"], str) and listed_keys.get(value["listed"], 0) == 1):` (1048).
- **axis:** a `listed` target must name exactly one finding the record lists for the merge verdict.
- **neutralization:** the clause to `not (isinstance(value["listed"], str))`, so any text key is accepted.
- **detector:** `test_s_accounting_a_listed_target_naming_no_listed_finding_is_refused` (two parameters; run with its sibling accounting tests by `-k test_s_accounting`, four tests)

### raw red

```
.FF.                                                                     [100%]
=================================== FAILURES ===================================
_ test_s_accounting_a_listed_target_naming_no_listed_finding_is_refused[waiting-<lambda>] _
...
>       problems = refused(records, advisor, bodies)
                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
...
E       Failed: DID NOT RAISE Refusal

/home/user/wt-2493/plugins/superheroes/lib/tests/test_pr_sheet_fixed_above_2332.py:48: Failed
_ test_s_accounting_a_listed_target_naming_no_listed_finding_is_refused[nope-<lambda>] _
...
E       Failed: DID NOT RAISE Refusal

/home/user/wt-2493/plugins/superheroes/lib/tests/test_pr_sheet_fixed_above_2332.py:48: Failed
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_pr_sheet_listed_2493.py::test_s_accounting_a_listed_target_naming_no_listed_finding_is_refused[waiting-<lambda>]
FAILED plugins/superheroes/lib/tests/test_pr_sheet_listed_2493.py::test_s_accounting_a_listed_target_naming_no_listed_finding_is_refused[nope-<lambda>]
2 failed, 2 passed, 14 deselected in 0.99s
```

(The lines marked `...` are the repeated source echo of the test body, shortened by me in this record; the run's own output was not truncated.)

### restore

Inverse Edit: the clause back to `not (isinstance(value["listed"], str) and listed_keys.get(value["listed"], 0) == 1)`.

### restore receipt

```
1048:            elif targets[0] == "listed" and not (isinstance(value["listed"], str) and listed_keys.get(value["listed"], 0) == 1):
```

### raw green

```
....                                                                     [100%]
4 passed, 14 deselected in 1.02s
```

## E-listed-unique: a listed key shared by two listed findings names none (WO-5)

Commands for this and the next two entries: `scripts/pinned-python -B -X pycache_prefix=/tmp/claude-0/superheroes-pyc-wo5 -m pytest <node id> -q -p no:xdist`; the launcher's `UV_NATIVE_TLS` warning line is left out. Each neutralization and restore is one Edit-tool edit; no `git checkout`, `git restore`, `git reset` or `git stash`. Nothing quoted is secret; nothing is redacted. Captures are far under the ceilings.

- **guarded element:** `pr_sheet.py` `_check_accounting`, `listed_keys.get(value["listed"], 0) == 1` (1049).
- **axis:** a `listed` target names exactly one listed finding; a key two listed findings share names none.
- **neutralization:** `== 1` to `>= 1` in that clause.
- **detector:** `test_s_accounting_a_listed_key_shared_by_two_listed_findings_is_refused`

### raw red

```
F                                                                        [100%]
=================================== FAILURES ===================================
___ test_s_accounting_a_listed_key_shared_by_two_listed_findings_is_refused ____

    def test_s_accounting_a_listed_key_shared_by_two_listed_findings_is_refused():
        """axis: E-listed-unique: a listed target needs a key that names exactly one listed finding; two sharing a key name none."""
        first, second = minor("L1", False), minor("L2", False)
        second["id"] = first["id"]  # the collision, built as test_pr_sheet.py's _ambiguous builds it: the two share one reviewer id
        body = ACCEPTING + "- Minor label wording is accepted.\n"
        bullet = pr_sheet.listed_bullets(10, body)[0][0]
        advisor = pr_input(accounting={bullet: {"listed": first["id"]}})
>       problems = refused([record(10, [first, second])], advisor, {10: body})
                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

/home/user/wt-2493/plugins/superheroes/lib/tests/test_pr_sheet_listed_2493.py:129: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

records = [{'schema': 'review-record/1', 'pr': 10, 'sessionId': 'session-5', 'lane': {'value': 'full', 'reason': 'A new table holds money.', 'source': 'PR lane call'}, ...}]
advisor = {'schema': 'pr-sheet-input/1', 'kind': 'pr', 'number': 10, 'title': 'Round the balance', ...}
bodies = {10: "## What we're accepting\n\n- Minor label wording is accepted.\n"}

    def refused(records, advisor, bodies):
>       with pytest.raises(pr_sheet.Refusal) as caught:
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       Failed: DID NOT RAISE Refusal

/home/user/wt-2493/plugins/superheroes/lib/tests/test_pr_sheet_fixed_above_2332.py:48: Failed
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_pr_sheet_listed_2493.py::test_s_accounting_a_listed_key_shared_by_two_listed_findings_is_refused
1 failed in 4.84s
```

### restore

Inverse Edit: `>= 1` back to `== 1`.

### restore receipt

```
1049:            elif targets[0] == "listed" and not (isinstance(value["listed"], str) and listed_keys.get(value["listed"], 0) == 1):
```

### raw green

```
.                                                                        [100%]
1 passed in 1.65s
```

## E-history-owned: the history's owned leftovers are the waiting findings (WO-5)

- **guarded element:** `pr_sheet.py` `build`, the `owned` list's predicate (1443).
- **axis:** a `whatIsMissing` leftover line of a waiting finding, a no-outcome Minor in a risk area included, is counted as an owned leftover, not printed as an incomplete record.
- **neutralization:** the predicate `review_record.waits_for_owner(f, r["findings"])` to `f.get("outcome") == _LEFT and not review_record.repeat_held_elsewhere(f, r["findings"])`.
- **detector:** `test_s_history_a_waiting_minor_in_an_uncleared_record_shows_the_leftover_line_and_no_incomplete_line`

### raw red

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_s_history_a_waiting_minor_in_an_uncleared_record_shows_the_leftover_line_and_no_incomplete_line _

    def test_s_history_a_waiting_minor_in_an_uncleared_record_shows_the_leftover_line_and_no_incomplete_line():
        """axis: E-history-owned: a waiting no-outcome Minor's whatIsMissing line is an owned leftover, not an incomplete line."""
        waiting = minor("W1", True, outcome=None, reason=None)
        rec = {**record(10, [waiting]), "status": "awaits-owner", "whatIsMissing": [review_record.leftover_line(waiting)]}
        sheet = build([rec], pr_input(leftovers={waiting["findingKey"]: ENTRY}))
        history = sheet["prSheet"]["history"]
>       assert WORDS["historyLeftover"] in history, history
E       AssertionError: ['2 rounds ran.', "The review record is incomplete: finding W1 waits for the owner's decision."]
E       assert '1 finding is left for you below.' in ['2 rounds ran.', "The review record is incomplete: finding W1 waits for the owner's decision."]

/home/user/wt-2493/plugins/superheroes/lib/tests/test_pr_sheet_listed_2493.py:166: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_pr_sheet_listed_2493.py::test_s_history_a_waiting_minor_in_an_uncleared_record_shows_the_leftover_line_and_no_incomplete_line
1 failed in 1.39s
```

### restore

Inverse Edit: the predicate back to `review_record.waits_for_owner(f, r["findings"])`.

### restore receipt

```
1443:        owned = [review_record.leftover_line(f) for f in r["findings"] if review_record.waits_for_owner(f, r["findings"])]
```

### raw green

```
.                                                                        [100%]
1 passed in 0.91s
```

## E-listed-state: a listed-accounted bullet never counts toward the zero-card listed state (WO-5)

- **guarded element:** `pr_sheet.py` `build`, the `left` build that leaves out `shown_listed` bullets (about 1483-1488).
- **axis:** a bullet accounted `{"listed": key}` is left out of the bullets `nothingListed` and `canonAccounted` are read from, like a fixed-above one.
- **detector:** `test_s_accounting_a_listed_bullet_is_not_counted_toward_the_zero_card_listed_state` (ran green with the file: 23 passed).
- **status: unproven.** The order named a bite-proof for two elements only (E-listed-unique, E-history-owned) and a budget of two red runs, so **no neutralization was run** for this element and no red was observed. The protection of this detector is unverified until a run that drops `and bullet not in shown_listed` from the `left` build shows that test red.
