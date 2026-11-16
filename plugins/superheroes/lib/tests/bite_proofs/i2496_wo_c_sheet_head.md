# Work order WO-C (#2496) bite-proof: the merge sheet shows the head, carries no note, and can be held

**Provenance:** claude / sonnet-5.5 (implementer, WO-C), maker family claude, worktree `/home/user/wt-2496-c`, base `ff438e43c6209be7ca9e5689c9493af081b812b0`. Production under proof: `plugins/superheroes/lib/pr_sheet.py` (`build`'s `head_of`, `pr_state`), `plugins/superheroes/lib/sheet_prose.py` (`_pr_body`) and `plugins/superheroes/theme/review-template.html` (`prHead`, `render`). Detector files: `plugins/superheroes/lib/tests/test_pr_sheet_head_2496.py` and `plugins/superheroes/lib/tests/test_review_template.py`.

Declared guarded-element set (from the order): **E-headnow**, **E-nonote**, **E-held-state**, **E-held-page**. Four elements, four entries; no equivalence class is used.

Elements this file's tests assert that the order declared no neutralization for have **no neutralization run** and are **unproven** by this record: the refusal of a missing, partial or malformed `headNow` (`_check_head_now`), the refusal of `headNow` in spec mode, the carry-heads-equal-`headNow` check (`_check_carry_heads`), the `hold` verb and its refusals (`hold`, `_main_hold`), the schema's `prSheet.held`, the `sheet-words.json` `heldHeading` and `held` words, and the page's two side guards (`names` skipping the verdict read for a held sheet, and `countHost.hidden`). The `-k` selections below name the tests of each declared element only; the rest of the files were run green, unneutralized, in the run budget's runs 1 to 4.

Every command is `scripts/pinned-python -B -X pycache_prefix=/tmp/wo-c-pyc -m pytest <files> -k <expression> -q -p no:cacheprovider`, run from `/home/user/wt-2496-c`. The leading `warning: The UV_NATIVE_TLS environment variable is deprecated ...` line of every run is left out; it is the launcher's, not pytest's. Each neutralization is one Edit-tool edit, restored by the inverse Edit-tool edit; no `git checkout`, `git restore`, `git reset` or `git stash` was used. Nothing quoted is a secret, token, private URL or personal detail, so nothing is redacted. Every capture is far under the 32 KiB per element and 128 KiB ceilings. Run numbers are the order's test-command budget (12 of 12 used: 1 to 4 were the unneutralized runs, 5 to 12 are the eight below).

Two disclosures that bear on all four:

- **Comment added after the green runs.** After the E-headnow green run, one comment line (the `# axis: ... (E-headnow)` line above `if head_now is None:` in `head_of`) was added; it changes no code. No test was run after it (the budget was spent), so the file as it now stands has been byte-checked by reading, not by a run.
- **Surfaces neutralized together.** E-nonote and E-held-page each guard two surfaces (the chat prose and the page). Each was neutralized on both surfaces at once and run once, with the prose detector and the page detector named in one command. The failing tests split by surface (the prose tests can only fail through `sheet_prose.py`, the node page tests only through `review-template.html`), so each surface's red is its own, but the two neutralizations were not run apart.

## E-headnow: the sheet's commit and CI line are the head's, from `headNow`, never the record's

- **guarded element:** `pr_sheet.py`, `build`, the inner `head_of(r)` and its `if head_now is None:` line (read for the sheet's `commit`, `whatChanged.ci`, each stack `prs[].commit` and each stack "Checks were" line).
- **axis:** a records-built sheet's head commit(s) and CI come only from `headNow`; the record's `finalCommit.sha` and `ci` are read only in the spec-PR mode (where `headNow` is refused).
- **neutralization:** the line `        if head_now is None:` became `        if True:`, so every sheet reads the record's commit and CI.
- **detector:** `test_a_pr_sheet_shows_the_ci_and_commit_of_the_head_it_is_built_for_not_the_records` and `test_a_stack_sheet_reads_every_layers_head_and_ci_from_head_now`, run as `test_pr_sheet_head_2496.py -k "head_it_is_built_for or every_layers_head_and_ci"`.

### raw red (run 5)

```
FF                                                                       [100%]
=================================== FAILURES ===================================
_ test_a_pr_sheet_shows_the_ci_and_commit_of_the_head_it_is_built_for_not_the_records _

    def test_a_pr_sheet_shows_the_ci_and_commit_of_the_head_it_is_built_for_not_the_records():
        # Axis: a record that stored ci pending on commit A, with headNow naming head B green, builds a sheet whose commit is B and whose CI line is green on B.
        records, advisor = bundle(SMALL)
        records[0]["ci"] = {"state": "pending", "sha": OLD, "source": "GitHub checks"}
        assert records[0]["finalCommit"]["sha"] == OLD
        advisor["headNow"] = {"211": {"commit": NEW, "ci": "green"}}
        sheet = build(records, advisor)
>       assert sheet["prSheet"]["commit"] == NEW
E       AssertionError: assert '0f1e2d3c4b5a...2e1f001122334' == 'bbbbbbbbbbbb...bbbbbbbbbbbbb'
E         
E         - bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
E         + 0f1e2d3c4b5a69788796a5b4c3d2e1f001122334

/home/user/wt-2496-c/plugins/superheroes/lib/tests/test_pr_sheet_head_2496.py:62: AssertionError
_______ test_a_stack_sheet_reads_every_layers_head_and_ci_from_head_now ________

    def test_a_stack_sheet_reads_every_layers_head_and_ci_from_head_now():
        # Axis: on a stack, each layer's history line, each prs[].commit, the sheet's commit and its CI line are that layer's headNow entry, whatever its record stored.
        records, advisor = bundle(STACK)
        for record in records:
            record["ci"] = {"state": "pending", "sha": record["finalCommit"]["sha"], "source": "GitHub checks"}
        advisor["headNow"] = {"5": {"commit": LAYERS["5"], "ci": "red"}, "6": {"commit": LAYERS["6"], "ci": "pending"}, "7": {"commit": LAYERS["7"], "ci": "green"}}
        sheet = build(records, advisor)
        part = sheet["prSheet"]
>       assert [(p["number"], p["commit"]) for p in part["prs"]] == [(5, LAYERS["5"]), (6, LAYERS["6"]), (7, LAYERS["7"])]
E       AssertionError: assert [(5, '1111111...333333ccccc')] == [(5, '5555555...77777777777')]
E         
E         At index 0 diff: (5, '1111111aaaaaaa1111111aaaaaaa1111111aaaaa') != (5, '5555555555555555555555555555555555555555')
E         Use -v to get more diff

/home/user/wt-2496-c/plugins/superheroes/lib/tests/test_pr_sheet_head_2496.py:76: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_pr_sheet_head_2496.py::test_a_pr_sheet_shows_the_ci_and_commit_of_the_head_it_is_built_for_not_the_records
FAILED plugins/superheroes/lib/tests/test_pr_sheet_head_2496.py::test_a_stack_sheet_reads_every_layers_head_and_ci_from_head_now
2 failed, 44 deselected in 1.06s
```

### restore

The inverse Edit-tool edit: `        if True:` back to `        if head_now is None:`.

### restore receipt

The restored lines, as the file holds them (read back with the Grep tool right after the edit):

```
1484:        if head_now is None:
1485-            return {"commit": r["finalCommit"]["sha"], "ci": r["ci"]["state"], "ciCommit": r["ci"].get("sha")}
```

### raw green (run 6)

```
..                                                                       [100%]
2 passed, 44 deselected in 0.99s
```

## E-nonote: a carried sheet shows no note of the carry, in the prose and on the page

- **guarded element:** `sheet_prose.py:_pr_body`, the line `if "carriedForward" not in prsheet and "previousCommit" in prsheet:` (the prose), and `review-template.html:prHead`, the line `if (prSheet.carriedForward === undefined && prSheet.previousCommit !== undefined) parts.push(buildChanged(prSheet.previousCommit));` (the page).
- **axis:** a sheet republished after a non-material move shows neither a "carried forward" box nor the changed box; only an uncarried sheet with `previousCommit` shows the changed box.
- **neutralization (both at once):** the prose line became `    if "previousCommit" in prsheet:` and the page line became `      if (prSheet.previousCommit !== undefined) parts.push(buildChanged(prSheet.previousCommit));`, so a carried sheet draws the changed box ("The PR moved past commit ...") on both surfaces.
- **detector:** `test_a_carried_sheets_prose_carries_none_of_the_carried_words[pr|stack]` (prose) and `test_a_carried_sheet_renders_no_carried_note_and_no_changed_box` (page), run as `test_pr_sheet_head_2496.py test_review_template.py -k "carries_none_of_the_carried_words or renders_no_carried_note_and_no_changed_box"`.

### raw red (run 7)

```
FFF                                                                      [100%]
=================================== FAILURES ===================================
______ test_a_carried_sheets_prose_carries_none_of_the_carried_words[pr] _______

case = (['record-small.json'], 'input-small.json')

    @pytest.mark.parametrize("case", [SMALL, STACK], ids=["pr", "stack"])
    def test_a_carried_sheets_prose_carries_none_of_the_carried_words(case):
        # Bites on: the chat prose drawing the carried heading or its text, or the carry's date, what moved or why it is not material, or drawing the changed box in its place.
        # Axis: a sheet republished after a non-material move keeps its answers and verdict but shows no "carried forward" or "moved past" note; the carry's date, moved and whyNotMaterial are shown nowhere.
        records, advisor = bundle(case)
        previous = sheet_bytes(build(records, advisor))
        heads = {"211": "1" * 40} if case is SMALL else dict(LAYERS)
        advisor["headNow"] = {n: {"commit": c, "ci": "green"} for n, c in heads.items()}
        sheet = build(records, carried(advisor, heads), previous)
        assert "carriedForward" in sheet["prSheet"] and sheet_prose.check_sheet(sheet) == []
        prose = sheet_prose.render(sheet)
        for word in CARRIED_WORDS:
            assert word not in prose, word
        for key in ("carriedHeading", "carried", "changedHeading"):
>           assert WORDS.get(key, "\0") not in prose, key
E           AssertionError: changedHeading
E           assert 'This PR changed' not in '**Reword th... accepted.\n'
E             
E             'This PR changed' is contained here:
E               11111.
E               
E               **This PR changed**
E               
E               The PR moved past commit 0f1e2d3 since the last sheet was made. Your answers to unchanged items are kept; the merge verdict starts over on this sheet....
E             
E             ...Full output truncated, use '-vv' to show

/home/user/wt-2496-c/plugins/superheroes/lib/tests/test_pr_sheet_head_2496.py:182: AssertionError
_____ test_a_carried_sheets_prose_carries_none_of_the_carried_words[stack] _____

case = (['record-stack-1.json', 'record-stack-2.json', 'record-stack-3.json'], 'input-stack.json')

    @pytest.mark.parametrize("case", [SMALL, STACK], ids=["pr", "stack"])
    def test_a_carried_sheets_prose_carries_none_of_the_carried_words(case):
        # Bites on: the chat prose drawing the carried heading or its text, or the carry's date, what moved or why it is not material, or drawing the changed box in its place.
        # Axis: a sheet republished after a non-material move keeps its answers and verdict but shows no "carried forward" or "moved past" note; the carry's date, moved and whyNotMaterial are shown nowhere.
        records, advisor = bundle(case)
        previous = sheet_bytes(build(records, advisor))
        heads = {"211": "1" * 40} if case is SMALL else dict(LAYERS)
        advisor["headNow"] = {n: {"commit": c, "ci": "green"} for n, c in heads.items()}
        sheet = build(records, carried(advisor, heads), previous)
        assert "carriedForward" in sheet["prSheet"] and sheet_prose.check_sheet(sheet) == []
        prose = sheet_prose.render(sheet)
        for word in CARRIED_WORDS:
            assert word not in prose, word
        for key in ("carriedHeading", "carried", "changedHeading"):
>           assert WORDS.get(key, "\0") not in prose, key
E           AssertionError: changedHeading
E           assert 'This PR changed' not in '**Gift card... accepted.\n'
E             
E             'This PR changed' is contained here:
E               77777.
E               
E               **This PR changed**
E               
E               The PR moved past commit 3333333 since the last sheet was made. Your answers to unchanged items are kept; the merge verdict starts over on this sheet....
E             
E             ...Full output truncated, use '-vv' to show

/home/user/wt-2496-c/plugins/superheroes/lib/tests/test_pr_sheet_head_2496.py:182: AssertionError
_______ test_a_carried_sheet_renders_no_carried_note_and_no_changed_box ________

    def test_a_carried_sheet_renders_no_carried_note_and_no_changed_box():
        # Axis: a sheet republished after a non-material move draws no element with id pr-carried and no carried text, and no pr-changed box either; the verdict and its answers are untouched.
        sheet = _with_2496(_PR_SAMPLE_2496, _carry_2496)
        page = _pr_page_2496(sheet)["result"]
>       assert "pr-carried" not in page["ids"] and "pr-changed" not in page["ids"]
E       AssertionError: assert ('pr-carried' not in ['sheet-status', 'sheet-gate', 'sheet-error', 'sheet-error-list', 'sheet-cards', 'pr-what-changed', ...] and 'pr-changed' not in ['sheet-status', 'sheet-gate', 'sheet-error', 'sheet-error-list', 'sheet-cards', 'pr-what-changed', ...])

/home/user/wt-2496-c/plugins/superheroes/lib/tests/test_review_template.py:4740: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_pr_sheet_head_2496.py::test_a_carried_sheets_prose_carries_none_of_the_carried_words[pr]
FAILED plugins/superheroes/lib/tests/test_pr_sheet_head_2496.py::test_a_carried_sheets_prose_carries_none_of_the_carried_words[stack]
FAILED plugins/superheroes/lib/tests/test_review_template.py::test_a_carried_sheet_renders_no_carried_note_and_no_changed_box
3 failed, 292 deselected in 2.18s
```

### restore

Two inverse Edit-tool edits, each line back as it was.

### restore receipt

The restored lines, as the files hold them (the page line read back with the Grep tool; the prose line is the one `_pr_body` carries, quoted from the inverse edit):

```
    if "carriedForward" not in prsheet and "previousCommit" in prsheet:
      if (prSheet.carriedForward === undefined && prSheet.previousCommit !== undefined) parts.push(buildChanged(prSheet.previousCommit));
```

### raw green (run 8)

```
...                                                                      [100%]
3 passed, 292 deselected in 1.83s
```

## E-held-state: a held sheet reads no verdict (`being-fixed`), through no revision of its chain

- **guarded element:** `pr_sheet.py:pr_state`, the early return under `if sheet["prSheet"].get("held") is True:`.
- **axis:** a held sheet reads `being-fixed` with no verdict looked up at all: not under its own digest, and never by following the `carriedForward.sheets` chain.
- **neutralization:** the line became `    if sheet["prSheet"].get("held") is False:`, so a held sheet is read as any other and its chain is followed.
- **detector:** `test_a_held_sheet_that_had_a_standing_merge_reads_being_fixed[one-hop-earliest|two-hops-earliest|two-hops-middle|own-digest]`, run as `test_pr_sheet_head_2496.py -k "held_sheet_that_had_a_standing_merge"`. Each case first asserts the sheet read `ready` before it was held, so the Merge did stand.
- **what the red does not discriminate:** with the guard off, the held sheet (which has no cards) falls through to `needs-you`, not `ready`, because its cards are gone and a Merge's `covers` no longer match; the detector goes red on `being-fixed`, which only the guard produces. It does not show a verdict being wrongly accepted, because a held sheet's emptied cards keep a stored Merge from standing even without the guard; the guard still fixes the state to `being-fixed` and the lookup to none.

### raw red (run 9)

```
FFFF                                                                     [100%]
=================================== FAILURES ===================================
_ test_a_held_sheet_that_had_a_standing_merge_reads_being_fixed[one-hop-earliest] _

sheet = b'{\n  "schema": "superheroes-sheet/1",\n  "kind": "pr",\n  "title": "PR 1724",\n  "prSheet": {\n    "number": 1724,\n...ds one way."\n            }\n          ]\n        }\n      ],\n      "images": [],\n      "options": []\n    }\n  ]\n}'
stored_under = '0b3220346ba4d409da321fd760bd2384b55b6ef4d5cd7c9b37bceb272a3fb308'

    @pytest.mark.parametrize("sheet, stored_under", [(SHEET_B, A_ID), (SHEET_C, A_ID), (SHEET_C, B_ID), (SHEET_B, B_ID)],
                             ids=["one-hop-earliest", "two-hops-earliest", "two-hops-middle", "own-digest"])
    def test_a_held_sheet_that_had_a_standing_merge_reads_being_fixed(sheet, stored_under):
        # Bites on: pr_state looking up a verdict for a held sheet, under its own digest or any digest of its carry chain, so a taken-down sheet still lists as ready.
        # Axis: fail-closed edge: a held sheet's verdict is never read, through any revision in its chain; it reads being-fixed whatever the store holds.
        store = verdicts_of((stored_under, merge_doc(digest=stored_under)))
        assert state_of(sheet, store) == "ready", "the sheet stood before it was held"
        held = held_bytes(sheet)
>       assert state_of(held, store) == "being-fixed"
E       AssertionError: assert 'needs-you' == 'being-fixed'
E         
E         - being-fixed
E         + needs-you

/home/user/wt-2496-c/plugins/superheroes/lib/tests/test_pr_sheet_head_2496.py:265: AssertionError
(the three other cases, [two-hops-earliest], [two-hops-middle] and [own-digest], print the same traceback with only the sheet bytes and the stored_under digest differing, and the same `assert 'needs-you' == 'being-fixed'` at test_pr_sheet_head_2496.py:265)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_pr_sheet_head_2496.py::test_a_held_sheet_that_had_a_standing_merge_reads_being_fixed[one-hop-earliest]
FAILED plugins/superheroes/lib/tests/test_pr_sheet_head_2496.py::test_a_held_sheet_that_had_a_standing_merge_reads_being_fixed[two-hops-earliest]
FAILED plugins/superheroes/lib/tests/test_pr_sheet_head_2496.py::test_a_held_sheet_that_had_a_standing_merge_reads_being_fixed[two-hops-middle]
FAILED plugins/superheroes/lib/tests/test_pr_sheet_head_2496.py::test_a_held_sheet_that_had_a_standing_merge_reads_being_fixed[own-digest]
4 failed, 42 deselected in 1.04s
```

This capture condenses the three repeated tracebacks to the parenthetical line; the first traceback and the summary lines are the tool's own, word for word. The three repeats were in the tool's output in full; they are not reproduced.

### restore

The inverse Edit-tool edit: `is False` back to `is True`.

### restore receipt

The restored line, as the file holds it (read back with the Grep tool after the E-held-page restore, which came later):

```
1653:    if sheet["prSheet"].get("held") is True:
```

(Line 1653 is as of that read; the later comment-only edit to `head_of` moved it down by one.)

### raw green (run 10)

```
....                                                                     [100%]
4 passed, 42 deselected in 0.95s
```

## E-held-page: a held page and a held prose show only the notice, no card, no control

- **guarded element:** `sheet_prose.py:_pr_body`, the early return under `if prsheet.get("held") is True:` (the prose), and `review-template.html:render`, the line `heldSheet = revisedKind(sheetKind) && sheet.prSheet.held === true;` (the page: no card, no walk, no folded part, no verdict control, no verdict read).
- **axis:** a held pr or stack sheet draws one notice (the held heading and the held words) and nothing else, whatever else the sheet holds (cards left on it, a walk, a carry chain); the page shows no answer control.
- **neutralization (both at once):** the prose line became `    if prsheet.get("held") is False:` and the page line became `      heldSheet = revisedKind(sheetKind) && sheet.prSheet.held === false;`, so a held sheet is drawn as an ordinary one on both surfaces.
- **detector:** `test_a_held_sheets_prose_is_the_title_line_the_held_heading_and_the_notice_and_nothing_else[pr|stack-emptied|cards-left-on-it]` (prose), `test_a_held_sheet_renders_the_held_notice_no_card_and_no_verdict_control[plain|carried-chain-emptied|cards-left-on-the-sheet]` and `test_a_held_page_reads_a_verdict_nowhere_and_writes_nothing` (page), run as `test_pr_sheet_head_2496.py test_review_template.py -k "held_sheets_prose_is or held_sheet_renders_the_held_notice or held_page_reads_a_verdict"`.

### raw red (run 11): INCOMPLETE

The harness cut this output in the middle (`... [6472 characters truncated] ...`); below is exactly the output that came back, labelled incomplete, nothing reconstructed. The nine failures are named in full by the summary lines that close it.

```
FFFFFFFFF                                                                [100%]
=================================== FAILURES ===================================
_ test_a_held_sheets_prose_is_the_title_line_the_held_heading_and_the_notice_and_nothing_else[pr-emptied] _

case = (['record-big.json'], 'input-big.json'), emptied = True

    @pytest.mark.parametrize("emptied", [True, False], ids=["emptied", "cards-left-on-it"])
    @pytest.mark.parametrize("case", [BIG, STACK], ids=["pr", "stack"])
    def test_a_held_sheets_prose_is_the_title_line_the_held_heading_and_the_notice_and_nothing_else(case, emptied):
        # Bites on: the held prose still carrying what changed, a card, a folded part or the verdict line.
        # Axis: a held sheet's prose is the title line, the held heading and the held notice, whatever else the sheet holds.
        records, advisor = bundle(case)
        sheet = build(records, advisor)
        sheet["title"] = "Plain title"
        sheet["prSheet"]["held"] = True
        if emptied:
            sheet["cards"] = []
        assert sheet_prose.check_sheet(sheet) == []
        prose = sheet_prose.render(sheet)
        count = len(sheet["cards"])
>       assert prose == "**Plain title**: %d item%s for you.\n\n**%s**\n\n%s\n" % (count, "" if count == 1 else "s", WORDS["heldHeading"], WORDS["held"])
E       AssertionError: assert '**Plain titl...t accepted.\n' == '**Plain titl...ept for it.\n'
E         
E           **Plain title**: 0 items for you.
E           
E         - **This PR is being reviewed again**
E         + **What changed**
E           
E         - The PR changed after this sheet was made, in a way that needs a fresh review. Nothing here can be answered until the advisor brings a new sheet; your earlier answers are kept for it....
E         
E         ...Full output truncated, use '-vv' to show

/home/user/wt-2496-c/plugins/superheroes/lib/tests/test_pr_sheet_head_2496.py:287: AssertionError
_ test_a_held_sheets_prose_is_the_title_line_the_held_heading_and_the_notice_and_nothing_else[pr-cards-left-on-it] _

(the same traceback; its first differing lines read)
E           **Plain title**: 3 items for you.
E         - **This PR is being reviewed again**
E         + **What changed**

[... the harness cut 6472 characters here: the rest of the [stack-emptied] prose traceback, the [stack-cards-left-on-it] prose traceback, and the first three page tracebacks ...]

      Right contains one more item: ['This PR is being reviewed again', 'The PR changed after this sheet was made, in a way that needs a fresh review. Nothing here can be answered until the advisor brings a new sheet; your earlier answers are kept for it.']
E         Use -v to get more diff

/home/user/wt-2496-c/plugins/superheroes/lib/tests/test_review_template.py:4774: AssertionError
_ test_a_held_sheet_renders_the_held_notice_no_card_and_no_verdict_control[carried-chain-cards-left-on-the-sheet] _

emptied = False, carried = True

    @pytest.mark.parametrize("emptied", [True, False], ids=["emptied", "cards-left-on-the-sheet"])
    @pytest.mark.parametrize("carried", [False, True], ids=["plain", "carried-chain"])
    def test_a_held_sheet_renders_the_held_notice_no_card_and_no_verdict_control(emptied, carried):
        # Axis: fail-closed edge: a held page shows no card and no verdict control, whatever else the sheet holds (cards, a walk, a carry chain); its one box is the held heading and notice from the words file.
        sheet = _held_2496(_with_2496(_PR_SAMPLE_2496, _carry_2496) if carried else _PR_SAMPLE_2496, emptied)
        assert sheet["cards"] == [] or not emptied
        page = _pr_page_2496(sheet)["result"]
        words = WORDS["pr"]
>       assert page["heldBox"] == [[words["heldHeading"], words["held"]]]
E       AssertionError: assert [] == [['This PR is...ept for it.']]
E         
E         Right contains one more item: ['This PR is being reviewed again', 'The PR changed after this sheet was made, in a way that needs a fresh review. Nothing here can be answered until the advisor brings a new sheet; your earlier answers are kept for it.']
E         Use -v to get more diff
_________ test_a_held_page_reads_a_verdict_nowhere_and_writes_nothing __________

    def test_a_held_page_reads_a_verdict_nowhere_and_writes_nothing():
        # Bites on: a held page restoring a stored Merge onto a verdict control, or saving a document of its own.
        # Axis: a held page reads no verdict: a Merge stored under the sheet's own digest or its carry chain restores no control, and no document is written.
        carried = _with_2496(_PR_SAMPLE_2496, _carry_2496)
        merge = {"id": "a" * 64, "data": {"verdict": "merge", "note": "my verdict note", "sheet": "a" * 64, "covers": []}}
        host = {"collections": {"answers": [], "verdict": [merge]}}
        plain = _run_page(_sample_files(carried), host=host, scenario=_EVERYTHING_2496)
        assert "verdict" in plain["result"]["reads"], "the carried sheet that is not held reads its verdict, so the held page's silence below means something"
        page = _run_page(_sample_files(_held_2496(carried, emptied=True)), host=host, scenario=_EVERYTHING_2496)
        assert page["settled"] and page["errorHidden"] is True, page["errors"]
>       assert page["recordedSets"] == [] and page["result"]["controls"] == [] and page["result"]["reads"] == ["answers"]
E       AssertionError: assert ([] == []
E         
E         Use -v to get more diff and [{'text': 'Wo...: False}, ...] == []
E         
E         Left contains 20 more items, first extra item: {'text': 'Works', 'disabled': False}
E         Use -v to get more diff)

/home/user/wt-2496-c/plugins/superheroes/lib/tests/test_review_template.py:4791: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_pr_sheet_head_2496.py::test_a_held_sheets_prose_is_the_title_line_the_held_heading_and_the_notice_and_nothing_else[pr-emptied]
FAILED plugins/superheroes/lib/tests/test_pr_sheet_head_2496.py::test_a_held_sheets_prose_is_the_title_line_the_held_heading_and_the_notice_and_nothing_else[pr-cards-left-on-it]
FAILED plugins/superheroes/lib/tests/test_pr_sheet_head_2496.py::test_a_held_sheets_prose_is_the_title_line_the_held_heading_and_the_notice_and_nothing_else[stack-emptied]
FAILED plugins/superheroes/lib/tests/test_pr_sheet_head_2496.py::test_a_held_sheets_prose_is_the_title_line_the_held_heading_and_the_notice_and_nothing_else[stack-cards-left-on-it]
FAILED plugins/superheroes/lib/tests/test_review_template.py::test_a_held_sheet_renders_the_held_notice_no_card_and_no_verdict_control[plain-emptied]
FAILED plugins/superheroes/lib/tests/test_review_template.py::test_a_held_sheet_renders_the_held_notice_no_card_and_no_verdict_control[plain-cards-left-on-the-sheet]
FAILED plugins/superheroes/lib/tests/test_review_template.py::test_a_held_sheet_renders_the_held_notice_no_card_and_no_verdict_control[carried-chain-emptied]
FAILED plugins/superheroes/lib/tests/test_review_template.py::test_a_held_sheet_renders_the_held_notice_no_card_and_no_verdict_control[carried-chain-cards-left-on-the-sheet]
FAILED plugins/superheroes/lib/tests/test_review_template.py::test_a_held_page_reads_a_verdict_nowhere_and_writes_nothing
9 failed, 286 deselected in 2.52s
```

The bracketed `[... the harness cut ...]` and `(the same traceback; ...)` lines are this record's markers, not tool output; the `[pr-cards-left-on-it]` heading's own body is condensed to the three differing lines the tool printed above the cut. The first page traceback `[plain-emptied]` and `[plain-cards-left-on-the-sheet]` and `[carried-chain-emptied]` fall inside the cut, apart from the closing lines of one of them.

### restore

Two inverse Edit-tool edits: `is False` back to `is True`, and `=== false` back to `=== true`.

### restore receipt

The restored lines, read back with the Grep tool right after the edits:

```
plugins/superheroes/theme/review-template.html:2544:      heldSheet = revisedKind(sheetKind) && sheet.prSheet.held === true;
plugins/superheroes/lib/sheet_prose.py:552:    if prsheet.get("held") is True:
plugins/superheroes/lib/pr_sheet.py:1653:    if sheet["prSheet"].get("held") is True:
```

### raw green (run 12)

```
.........                                                                [100%]
9 passed, 286 deselected in 2.13s
```

---

## Added at layer 2's review, round 2: E-held-carry (2026-11-16, typed and run by the build session)

**guard:** `_check_previous` in `lib/pr_sheet.py`, `if part.get("held") is True:` refuses a `carriedForward` whose earlier sheet is held (commit 9cfede68).

**neutralization:** `if False and part.get("held") is True:`.

**raw red:** `scripts/pinned-python -B -X pycache_prefix=<scratch> -m pytest plugins/superheroes/lib/tests/test_pr_sheet_head_2496.py -k held_sheet_is_refused -q -p no:cacheprovider`, in a detached probe worktree at 9cfede68
```
E       Failed: DID NOT RAISE Refusal
1 failed, 46 deselected in 26.04s
```

**restore:** the inverse Edit; `git status --short` printed nothing. **green:** the same file, `47 passed in 1.52s`.
