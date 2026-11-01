# C4 WO-1 bite-proof — a finding names its kind of mistake and the other places that share it

**Provenance:** claude / sonnet-5.5 (implementer). Detector file: `plugins/superheroes/lib/tests/test_c4_kind_of_mistake.py`.
Worktree `/home/user/wt-2220`, branch `claude/workhorse-issue-2220-i8zkg1`, base commit `ff999bf1a6c8fdb7ec9d4c3da690ac67725231ab`.
Every run is `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_c4_kind_of_mistake.py -q -n auto`
plus the `-k` selector named in each entry, the detector unedited. Each neutralization is one targeted Edit, undone by the inverse Edit.
The restore receipt is the restored line quoted back from a Read or Grep, and at the end `git status --porcelain` shows no product file
modified (only the test file, which gained the two tests named below). Captures are far under the 32 KiB / 128 KiB ceilings.
Nothing was redacted (no credential-like text appears). Dropped from every capture: the `UV_NATIVE_TLS` deprecation warning line and the
two `bringing up nodes...` lines. Where a capture is shortened, the entry says what was elided.

## Guarded elements (declared in the order) and the cited sites

| ID | Class (failure mode) | Representative neutralized | Other cited sites in the class | Detector |
|---|---|---|---|---|
| g1 | the per-place audit arm: an unfixed/unanswered place no longer refuses a clearing ruling | `audits.py:590` | `audits.py:582` (the axis line of the same arm) | `test_t4_…`, `test_t4b_…`, `test_t4d_…` |
| g2 | the place scope check: a place on an untouched line is kept in `places` | `round_driver.py:1120` | `round_driver.py:1119` (axis line) | `test_t2_a_place_on_a_context_line_…` |
| g3a | the compile merge does not union the other finding's places | `round_driver.py:1054` | `round_driver.py:1053` (axis line) | `test_t3_…` |
| g3b | the verifier/shared merge drops a member's own citation | `verification.py:380` | `verification.py:379` (axis line) | `test_t3_…`, `test_t4d_…` |
| g4a | a maker family (or an unknown provenance) is stamped as an author | `round_driver.py:928,930` (`_executed_author`) | `round_driver.py:4078` (the panel fold's stamp, in the class); `round_driver.py:5233` (the seams fold's stamp, which carries no axis line) | `test_t7_a_known_maker_family_is_never_stamped` (added) |
| g4b | an `author` arriving inside a payload survives to the folds | `round_driver.py:3788` | `round_driver.py:3787` (axis line) | `test_t7_a_payload_supplied_author_…`, `test_t7_a_search_description_from_any_other_phase_…` |
| g5a | a null / non-object / blank-kind `searchDescription` stays on the compiled finding | `round_driver.py:1130` | `round_driver.py:1127` (axis line) | `test_t6_a_null_or_blank_…` |
| g5b | a null / non-object `kindOfMistake` is carried to the record projection | `review_record_session.py:595` | `review_record_session.py:594` (axis line) | `test_t6_a_null_or_blank_…` (last assertion) |
| g6a | the per-place results are not written to the live row | `round_driver.py:3235` | `round_driver.py:3223` (axis line) | `test_t5_place_results_survive_…` |
| g6b | the archive replaces the ledger entry and loses its results | `round_driver.py:3272` | `round_driver.py:3271` (axis line) | `test_t5_place_results_survive_…` |
| g6c | a live row without results hides the ledger row's results in the record | `review_record_session.py:608` | `review_record_session.py:609` (axis line) | `test_t5_place_results_survive_…` |
| g7 | the fix guidance does not name every place | `round_driver.py:14236` | `round_driver.py:14235` (axis line) | `test_t9_…` (added) |

## g1 — the per-place audit arm

**neutralization** (`audits.py:590`): `if incomplete and ruling in _CLEARS:` → `if False and incomplete and ruling in _CLEARS:`.

**raw red** (whole file, detector unedited; the three failures, each shown in full):
```
.....FFF.......................                                          [100%]
=================================== FAILURES ===================================
_ test_t4_one_of_two_places_answered_unfixed_is_not_discharged_with_the_disclosure _
>       assert out["discharged"] == [] and out["notDischarged"] == ["t-1"] and out["placesUnfixed"] == ["t-1"]
E       AssertionError: assert (['t-1'] == []
E         Left contains one more item: 't-1'
/home/user/wt-2220/plugins/superheroes/lib/tests/test_c4_kind_of_mistake.py:199: AssertionError
_______ test_t4b_places_left_unanswered_are_not_discharged_and_disclosed _______
>           assert out["discharged"] == [] and out["placesUnfixed"] == ["t-1"], places
E           AssertionError: None
E           assert (['t-1'] == []
E             Left contains one more item: 't-1'
/home/user/wt-2220/plugins/superheroes/lib/tests/test_c4_kind_of_mistake.py:209: AssertionError
_ test_t4d_a_fix_of_only_the_representative_of_a_merged_pair_is_not_discharged _
>       assert out["discharged"] == [] and "not answered: src/a.py:19" in out["audits"][0]["reason"]
E       AssertionError: assert (['t-1'] == []
E         Left contains one more item: 't-1'
/home/user/wt-2220/plugins/superheroes/lib/tests/test_c4_kind_of_mistake.py:238: AssertionError
=========================== short test summary info ============================
FAILED …::test_t4_one_of_two_places_answered_unfixed_is_not_discharged_with_the_disclosure
FAILED …::test_t4b_places_left_unanswered_are_not_discharged_and_disclosed
FAILED …::test_t4d_a_fix_of_only_the_representative_of_a_merged_pair_is_not_discharged
3 failed, 28 passed in 3.22s
```
(Elided from the failure sections: the `[gwN] linux -- Python 3.12.13 …` lines, the `def` / comment source lines above the `>` line, and the `Use -v to get more diff` lines.)

**restore:** inverse Edit. **restore receipt:** `audits.py:590:            if incomplete and ruling in _CLEARS:` (Grep after the restore).

**raw green** (`-k test_t4`):
```
......                                                                   [100%]
6 passed in 1.71s
```

## g2 — the place scope check

**neutralization** (`round_driver.py:1120`): `if _diff_scope_ok(place, valid):` → `if True or _diff_scope_ok(place, valid):`.

**raw red** (`-k test_t2_a_place_on_a_context_line_leaves_places_for_the_raising_seats_outside_entry`):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_t2_a_place_on_a_context_line_leaves_places_for_the_raising_seats_outside_entry _
>       assert staged["kindOfMistake"] == _kind(3)  # the touched place stays, the context line (1) left
E       AssertionError: assert {'kind': 'unc..., 'line': 1}]} == {'kind': 'unc..., 'line': 3}]}
E         Differing items:
E         {'places': [{'file': 'src/a.py', 'line': 3}, {'file': 'src/a.py', 'line': 1}]} != {'places': [{'file': 'src/a.py', 'line': 3}]}
/home/user/wt-2220/plugins/superheroes/lib/tests/test_c4_kind_of_mistake.py:130: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c4_kind_of_mistake.py::test_t2_a_place_on_a_context_line_leaves_places_for_the_raising_seats_outside_entry
1 failed in 1.65s
```

**restore:** inverse Edit. **restore receipt:** `1120:            if _diff_scope_ok(place, valid):` (Grep after the restore).

**raw green** (same selector):
```
.                                                                        [100%]
1 passed in 1.47s
```

## g3a — the compile merge unions both findings' places

**neutralization** (`round_driver.py:1054`): `verification.apply_kind_members(merged, [existing, incoming])` → `pass  # g3a NEUTRALIZED verification.apply_kind_members(merged, [existing, incoming])`.

**raw red** (`-k "test_t3 or test_t4d"`; `test_t4d`, which merges through `verification._merge_group`, stays green, so the compile merge is a different failure mode from g3b):
```
.FF                                                                      [100%]
=================================== FAILURES ===================================
_ test_t3_a_member_without_a_kind_still_leaves_its_citation_as_a_place_of_the_one_that_has_one _
>       assert RD._merge_same_finding(kept, other)["kindOfMistake"] == _kind(3, 19)
E       AssertionError: assert {'kind': 'unc..., 'line': 3}]} == {'kind': 'unc... 'line': 19}]}
E         Differing items:
E         {'places': [{'file': 'src/a.py', 'line': 3}]} != {'places': [{'file': 'src/a.py', 'line': 3}, {'file': 'src/a.py', 'line': 19}]}
/home/user/wt-2220/plugins/superheroes/lib/tests/test_c4_kind_of_mistake.py:166: AssertionError
___ test_t3_a_merge_keeps_the_union_of_places_and_every_members_own_citation ___
>       assert merged["kindOfMistake"] == _kind(3, 20, 19)  # own (2) dropped; the member's citation (19) joined
E       AssertionError: assert {'kind': 'unc..., 'line': 3}]} == {'kind': 'unc... 'line': 19}]}
E         Differing items:
E         {'places': [{'file': 'src/a.py', 'line': 3}]} != {'places': [{'file': 'src/a.py', 'line': 3}, {'file': 'src/a.py', 'line': 20}, {'file': 'src/a.py', 'line': 19}]}
/home/user/wt-2220/plugins/superheroes/lib/tests/test_c4_kind_of_mistake.py:156: AssertionError
=========================== short test summary info ============================
FAILED …::test_t3_a_member_without_a_kind_still_leaves_its_citation_as_a_place_of_the_one_that_has_one
FAILED …::test_t3_a_merge_keeps_the_union_of_places_and_every_members_own_citation
2 failed, 1 passed in 1.28s
```

**restore:** inverse Edit. **restore receipt:** Grep after the restore, over `round_driver.py` for `NEUTRALIZED|apply_kind_members\(merged`: `1054:    verification.apply_kind_members(merged, [existing, incoming])` and nothing for `NEUTRALIZED`.

**raw green** (same selector):
```
...                                                                      [100%]
3 passed in 1.30s
```
(Run-order note: this green run and the Edit that began g3b were issued in the same tool batch. The run passed 3 of 3, which a neutralized g3b would have failed, so it ran against the restored g3a and the intact g3b.)

## g3b — a merged-away member's own citation joins the places (the shared merge, reached by the verifier merge)

**neutralization** (`verification.py:380`): `candidates.append({"file": member.get("file"), "line": member.get("line")})` → `pass  # g3b NEUTRALIZED candidates.append({"file": member.get("file"), "line": member.get("line")})`.

**raw red** (`-k "test_t3 or test_t4d"`; `test_t4d` fails here, and it goes only through `verification._merge_group`):
```
FFF                                                                      [100%]
=================================== FAILURES ===================================
_ test_t4d_a_fix_of_only_the_representative_of_a_merged_pair_is_not_discharged _
>       assert out["discharged"] == [] and "not answered: src/a.py:19" in out["audits"][0]["reason"]
E       AssertionError: assert (['t-1'] == []
E         Left contains one more item: 't-1'
/home/user/wt-2220/plugins/superheroes/lib/tests/test_c4_kind_of_mistake.py:238: AssertionError
___ test_t3_a_merge_keeps_the_union_of_places_and_every_members_own_citation ___
>       assert merged["kindOfMistake"] == _kind(3, 20, 19)  # own (2) dropped; the member's citation (19) joined
E       AssertionError: assert {'kind': 'unc... 'line': 20}]} == {'kind': 'unc... 'line': 19}]}
E         Differing items:
E         {'places': [{'file': 'src/a.py', 'line': 3}, {'file': 'src/a.py', 'line': 20}]} != {'places': [{'file': 'src/a.py', 'line': 3}, {'file': 'src/a.py', 'line': 20}, {'file': 'src/a.py', 'line': 19}]}
/home/user/wt-2220/plugins/superheroes/lib/tests/test_c4_kind_of_mistake.py:156: AssertionError
_ test_t3_a_member_without_a_kind_still_leaves_its_citation_as_a_place_of_the_one_that_has_one _
>       assert RD._merge_same_finding(kept, other)["kindOfMistake"] == _kind(3, 19)
E       AssertionError: assert {'kind': 'unc..., 'line': 3}]} == {'kind': 'unc... 'line': 19}]}
/home/user/wt-2220/plugins/superheroes/lib/tests/test_c4_kind_of_mistake.py:166: AssertionError
=========================== short test summary info ============================
FAILED …::test_t4d_a_fix_of_only_the_representative_of_a_merged_pair_is_not_discharged
FAILED …::test_t3_a_merge_keeps_the_union_of_places_and_every_members_own_citation
FAILED …::test_t3_a_member_without_a_kind_still_leaves_its_citation_as_a_place_of_the_one_that_has_one
3 failed in 1.34s
```

**restore:** inverse Edit. **restore receipt:** Grep after the restore over `verification.py` for `NEUTRALIZED|candidates.append`: `380:        candidates.append({"file": member.get("file"), "line": member.get("line")})` and nothing for `NEUTRALIZED`.

**raw green** (same selector):
```
...                                                                      [100%]
3 passed in 1.37s
```

## g4a — a maker family is never stamped as an author

**Unproven before this record's test.** The order expected a red in the existing `test_t7_…` tests. There was none. The unit's own stop is earlier:
`test_t7_a_transport_row_naming_an_independent_vendor_…` runs a world with no `hostFamily` in the seat map, so for the native `claude` vendor
`family = host = None` and `_executed_author` returns `None` at `round_driver.py:926`, before either maker bar (`:928` `nonpanel_barred`, `:930`
`accumulated_maker_families`) is read. Three runs of `-k test_t7` with no red, each reported as run:
- run 9: `930` neutralized (`if False and family in …`) with the Edit issued in the same tool batch as the run, so which state it ran against is **unknown**: `12 passed in 1.46s`.
- run 10: `930` neutralized, the Edit confirmed applied first: `12 passed in 1.46s`.
- run 11: `928` and `930` both neutralized (`if False and receipt_disclosures.nonpanel_barred(state, config)(vendor):` and `if False and family in …`): `12 passed in 1.47s`.

(Each of those three captures was the full text `warning … / bringing up nodes... / ............ / 12 passed in …s`.)

**Added test** (the order's fail-closed edge 1; `test_c4_kind_of_mistake.py`, after `test_t7_a_transport_row_…`): `test_t7_a_known_maker_family_is_never_stamped`.
Its seat map carries `"hostFamily": "claude"` and `"makerFamilies": ["claude"]`, so the executed family resolves and only the maker bars withhold the stamp.
It also asserts the seat's `seatStatus` is `run`, so a not-run seat cannot make "unstamped" vacuous.

**neutralization** (`round_driver.py:928,930`, both): `if receipt_disclosures.nonpanel_barred(state, config)(vendor):` → `if False and receipt_disclosures.nonpanel_barred(state, config)(vendor):`, and `if family in receipt_disclosures.accumulated_maker_families(state):` → `if False and family in receipt_disclosures.accumulated_maker_families(state):`.

**raw red** (`-k test_t7_a_known_maker_family_is_never_stamped`):
```
F                                                                        [100%]
=================================== FAILURES ===================================
________________ test_t7_a_known_maker_family_is_never_stamped _________________
        assert state["rounds"]["1"]["seatStatus"]["code-reviewer"] == "run"  # the seat ran: only the stamp is withheld
>       assert _author_of(state) == "unstamped"
E       AssertionError: assert {'seat': 'code-reviewer', 'vendor': 'claude', 'family': 'claude'} == 'unstamped'
/home/user/wt-2220/plugins/superheroes/lib/tests/test_c4_kind_of_mistake.py:357: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c4_kind_of_mistake.py::test_t7_a_known_maker_family_is_never_stamped
1 failed in 1.42s
```

**restore:** inverse Edit of both lines. **restore receipt:** Read after the restore:
```
928:    if receipt_disclosures.nonpanel_barred(state, config)(vendor):
929:        return None
930:    if family in receipt_disclosures.accumulated_maker_families(state):
931:        return None
```

**raw green:** the order's separate g4a green run was folded into the g4b runs below (budget; disclosed in the return). The new test passed with `928,930` restored
in the g4b red run (`2 failed, 11 passed`; the two failures are g4b's, the new test is not among them) and in the g4b green run (`13 passed`, which includes it).

**Not proven by a neutralization of its own:** each of `928` and `930` alone (either one bars a maker on its own in this fixture, because the
fixer vendor is `claude` and the seat map names `claude` a maker). The unknown-provenance stops at `921` and `926` are guarded by the existing
`test_t7_unavailable_provenance_…` tests but were not neutralized here. The seams stamp at `5233` and the panel stamp at `4078` call this one function and share its class.

## g4b — a payload-supplied `author` is removed before any fold reads it

**neutralization** (`round_driver.py:3788`): `artifact, _stripped = _without_search_authors(artifact)` → `_stripped = False  # g4b NEUTRALIZED: artifact, _stripped = _without_search_authors(artifact)`.

**raw red** (`-k test_t7`):
```
.......F...F.                                                            [100%]
=================================== FAILURES ===================================
_ test_t7_a_payload_supplied_author_is_removed_and_replaced_only_by_the_driver_stamp[None-unstamped] _
>       assert author == "unstamped" if expected == "unstamped" else author["vendor"] == expected
E       assert False
/home/user/wt-2220/plugins/superheroes/lib/tests/test_c4_kind_of_mistake.py:366: AssertionError
_____ test_t7_a_search_description_from_any_other_phase_carries_no_author ______
>       assert "author" not in seen["syn"]["findings"][0]["searchDescription"]
E       AssertionError: assert 'author' not in {'kind': 'unchecked retry', 'looksLike': 'a retry with no cap', 'examples': ['while True: retry()'], 'author': {'seat': 'x', 'vendor': 'x', 'family': 'x'}}
/home/user/wt-2220/plugins/superheroes/lib/tests/test_c4_kind_of_mistake.py:375: AssertionError
=========================== short test summary info ============================
FAILED …::test_t7_a_payload_supplied_author_is_removed_and_replaced_only_by_the_driver_stamp[None-unstamped]
FAILED …::test_t7_a_search_description_from_any_other_phase_carries_no_author
2 failed, 11 passed in 1.67s
```

**restore:** inverse Edit. **restore receipt:** Grep after the restore: `3788:    artifact, _stripped = _without_search_authors(artifact)`, and a Grep over `round_driver.py` for `NEUTRALIZED|if False|if True or` printed nothing.

**raw green** (`-k test_t7`; this run also covers the restored g4a lines and the new g4a test):
```
.............                                                            [100%]
13 passed in 1.53s
```

## g5a — a null normalization at the compile (the `searchDescription` removal)

**neutralization** (`round_driver.py:1130`): `fc.pop(SEARCH_DESCRIPTION_FIELD, None)` → `pass  # g5a NEUTRALIZED: fc.pop(SEARCH_DESCRIPTION_FIELD, None)`.

**raw red** (`-k test_t6`): all five parameters of the null test fail on the same assertion; the first failure is shown, the other four are identical in message and elided here (their node ids are in the summary).
```
FFFF.F                                                                   [100%]
=================================== FAILURES ===================================
_ test_t6_a_null_or_blank_kind_of_mistake_is_removed_counted_and_never_refused[bad2] _
bad = ['a']
>       assert "kindOfMistake" not in staged["Retry without a cap"] and "searchDescription" not in staged["Retry without a cap"]
E       AssertionError: assert ('kindOfMistake' not in {'title': 'Retry without a cap', 'file': 'src/a.py', 'line': 2, 'severity': 'Important', ...} and 'searchDescription' not in {'title': 'Retry without a cap', 'file': 'src/a.py', 'line': 2, 'severity': 'Important', ...})
/home/user/wt-2220/plugins/superheroes/lib/tests/test_c4_kind_of_mistake.py:298: AssertionError
[… four more failures at :298, parameters [None], [text], [bad3], [bad4], elided …]
=========================== short test summary info ============================
FAILED …::test_t6_a_null_or_blank_kind_of_mistake_is_removed_counted_and_never_refused[bad2]
FAILED …::test_t6_a_null_or_blank_kind_of_mistake_is_removed_counted_and_never_refused[None]
FAILED …::test_t6_a_null_or_blank_kind_of_mistake_is_removed_counted_and_never_refused[text]
FAILED …::test_t6_a_null_or_blank_kind_of_mistake_is_removed_counted_and_never_refused[bad3]
FAILED …::test_t6_a_null_or_blank_kind_of_mistake_is_removed_counted_and_never_refused[bad4]
5 failed, 1 passed in 1.29s
```

**restore:** inverse Edit. **restore receipt:** Read after the restore:
```
1128:    description = _clean_search_description(fc)
1129:    if description is None:
1130:        fc.pop(SEARCH_DESCRIPTION_FIELD, None)
```

**raw green** (`-k test_t6`):
```
......                                                                   [100%]
6 passed in 1.51s
```

**Not neutralized separately:** the same normalization for `kindOfMistake` (`round_driver.py:1115`, `fc.pop(KIND_OF_MISTAKE_FIELD, None)`). It sits in the same class and is asserted on the same line (`:298`).

## g5b — a null normalization at the record projection

**neutralization** (`review_record_session.py:595`): `(k != "kindOfMistake" or isinstance(src[k], dict))` → `(k != "kindOfMistake" or True)`.

**raw red** (`-k test_t6_a_null_or_blank_kind_of_mistake_is_removed_counted_and_never_refused`). **This capture is INCOMPLETE:** the tool output carried a harness note
`[1207 characters truncated]` in the middle of the third failure. The text below is exactly what came back, shortened by me only where marked; the assertion line and the summary are intact.
```
FFFFF                                                                    [100%]
=================================== FAILURES ===================================
_ test_t6_a_null_or_blank_kind_of_mistake_is_removed_counted_and_never_refused[bad2] _
bad = ['a']
        # a null that reaches the account from a live row is not carried either: the record would refuse it
>       assert "kindOfMistake" not in rs._finding_parts({"kindOfMistake": None}, None)
E       AssertionError: assert 'kindOfMistake' not in {'kindOfMistake': None}
E        +  where {'kindOfMistake': None} = <function _finding_parts at 0x7fbffe5aaca0>({'kindOfMistake': None}, None)
/home/user/wt-2220/plugins/superheroes/lib/tests/test_c4_kind_of_mistake.py:303: AssertionError
[… the [bad3], [None] and [text] failures: the same assertion at :303; the [None] one is the part the harness truncated …]
[… the [bad4] failure: the same assertion at :303 …]
=========================== short test summary info ============================
FAILED …::test_t6_a_null_or_blank_kind_of_mistake_is_removed_counted_and_never_refused[bad2]
FAILED …::test_t6_a_null_or_blank_kind_of_mistake_is_removed_counted_and_never_refused[bad3]
FAILED …::test_t6_a_null_or_blank_kind_of_mistake_is_removed_counted_and_never_refused[None]
FAILED …::test_t6_a_null_or_blank_kind_of_mistake_is_removed_counted_and_never_refused[text]
FAILED …::test_t6_a_null_or_blank_kind_of_mistake_is_removed_counted_and_never_refused[bad4]
5 failed in 1.50s
```
The compile-side assertion at `:298` passes here and the first failure is at `:303`, the projection, so this is a separate red from g5a.

**restore:** inverse Edit. **restore receipt:** Read after the restore:
```
595:            if isinstance(src, dict) and k in src and (k != "kindOfMistake" or isinstance(src[k], dict)):
```

**raw green** (`-k test_t6`):
```
......                                                                   [100%]
6 passed in 1.53s
```

## g6a — the per-place results are written to the live row (and, with it, the ledger entry)

**SUPERSEDED by "Amendment — WO-1g redesign" below.** The code this entry neutralizes (`_record_place_results`, `_with_place_results`) is deleted; k1 replaces it.

**neutralization** (`round_driver.py:3235`): `row[KIND_OF_MISTAKE_FIELD] = _with_place_results(row[KIND_OF_MISTAKE_FIELD], answers[key])` → `pass  # g6a NEUTRALIZED: row[KIND_OF_MISTAKE_FIELD] = …`.

**raw red** (`-k test_t5_place_results_survive_save_reload_audit_archive_and_render`):
```
F                                                                        [100%]
=================================== FAILURES ===================================
______ test_t5_place_results_survive_save_reload_audit_archive_and_render ______
        RD._record_place_results(state, out["audits"])  # the one enrichment step, as the audit fold calls it
        live = state["findings"][0]["kindOfMistake"]["places"]
        held = state["dispositionLedger"][0]["kindOfMistake"]["places"]
>       assert [p.get("fixed") for p in live] == [True, False] and live == held
E       assert ([None, None] == [True, False]
E         At index 0 diff: None != True
/home/user/wt-2220/plugins/superheroes/lib/tests/test_c4_kind_of_mistake.py:272: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c4_kind_of_mistake.py::test_t5_place_results_survive_save_reload_audit_archive_and_render
1 failed in 1.44s
```
**restore:** inverse Edit. **restore receipt:** Read after the restore: `3235:            row[KIND_OF_MISTAKE_FIELD] = _with_place_results(row[KIND_OF_MISTAKE_FIELD], answers[key])`.

**raw green** (same selector):
```
.                                                                        [100%]
1 passed in 1.37s
```

**Not neutralized separately:** the ledger-entry write in the same function (`round_driver.py:3243`). The same assertion (`:272`, `live == held`) fails if only that write is removed.
I did not run that variant (budget), so it is unproven by a run.

## g6b — the archive keeps the ledger entry's results when the departing live copy replaces it

**SUPERSEDED by "Amendment — WO-1g redesign" below.** The `_archive_departures` carry-over this entry neutralizes (`_place_results_of`) is deleted; k4 replaces it.

**neutralization** (`round_driver.py:3272`): `if isinstance(prior.get(KIND_OF_MISTAKE_FIELD), dict):` → `if False and isinstance(prior.get(KIND_OF_MISTAKE_FIELD), dict):`.

**raw red** (same selector):
```
F                                                                        [100%]
=================================== FAILURES ===================================
______ test_t5_place_results_survive_save_reload_audit_archive_and_render ______
        RD._archive_departures(state, [fresh])
>       assert [p.get("fixed") for p in state["dispositionLedger"][0]["kindOfMistake"]["places"]] == [True, False]
E       assert [None, None] == [True, False]
E         At index 0 diff: None != True
/home/user/wt-2220/plugins/superheroes/lib/tests/test_c4_kind_of_mistake.py:277: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c4_kind_of_mistake.py::test_t5_place_results_survive_save_reload_audit_archive_and_render
1 failed in 1.40s
```

**restore:** inverse Edit. (The first neutralizing Edit dropped the trailing space of its `old_string` line, so the neutralized state read `held =_place_results_of(…`. The first undo attempt failed with "String to replace not found", changed nothing, and the undo was redone against the exact text.)
**restore receipt:** Read after the restore:
```
3272:            if isinstance(prior.get(KIND_OF_MISTAKE_FIELD), dict):
3273:                held = _place_results_of(prior[KIND_OF_MISTAKE_FIELD])
```
and `git status --porcelain` at the end lists no modified product file.

**raw green** (same selector):
```
.                                                                        [100%]
1 passed in 1.42s
```

## g6c — a live row's kind of mistake never hides the ledger row's results in the record

**SUPERSEDED by "Amendment — WO-1g redesign" below.** The `_finding_parts` merge of ledger `fixed` into the live row's places is deleted; k2 and k3 replace it.

**neutralization** (`review_record_session.py:608`): `… and isinstance(held_kind.get("places"), list) and isinstance(older_kind, dict):` → `… and isinstance(held_kind.get("places"), list) and False and isinstance(older_kind, dict):`.

**raw red** (same selector):
```
F                                                                        [100%]
=================================== FAILURES ===================================
______ test_t5_place_results_survive_save_reload_audit_archive_and_render ______
        parts = rs._finding_parts(live_row, state["dispositionLedger"][0])
>       assert [p.get("fixed") for p in parts["kindOfMistake"]["places"]] == [True, False]
E       assert [None, None] == [True, False]
E         At index 0 diff: None != True
/home/user/wt-2220/plugins/superheroes/lib/tests/test_c4_kind_of_mistake.py:282: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c4_kind_of_mistake.py::test_t5_place_results_survive_save_reload_audit_archive_and_render
1 failed in 1.26s
```

**restore:** inverse Edit. **restore receipt:** Read after the restore:
```
608:    if isinstance(held_kind, dict) and isinstance(held_kind.get("places"), list) and isinstance(older_kind, dict):
```

**raw green** (same selector):
```
.                                                                        [100%]
1 passed in 1.35s
```

## g7 — the fix guidance names every place

**Unproven before this record's test.** No WO-1 test reached `_apply_fixes_payload_fields` with a batch naming places.

**Added test** (`test_c4_kind_of_mistake.py`, new section T9): `test_t9_the_fix_guidance_names_every_place_for_a_batch_with_places_and_a_batch_without_has_none`.
It asserts that the guidance file the driver writes for a batch with a finding naming places holds `RD.KIND_PLACES_GUIDANCE`,
and that a batch whose findings name no place (an empty `places` list, and a finding with no kind) writes no guidance file (`guidancePath is None`).
The module docstring's list gained `T9 the fix guidance names every place`.

**neutralization** (`round_driver.py:14236`): `if _batch_names_places(state):` → `if False and _batch_names_places(state):`.

**raw red** (`-k test_t9`):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_t9_the_fix_guidance_names_every_place_for_a_batch_with_places_and_a_batch_without_has_none _
        fields = RD._apply_fixes_payload_fields(placed_dir, state, 1, 0)
>       assert fields["guidancePath"] is not None
E       assert None is not None
/home/user/wt-2220/plugins/superheroes/lib/tests/test_c4_kind_of_mistake.py:437: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c4_kind_of_mistake.py::test_t9_the_fix_guidance_names_every_place_for_a_batch_with_places_and_a_batch_without_has_none
1 failed in 1.33s
```

**restore:** inverse Edit. **restore receipt:** a Grep over `round_driver.py`, `audits.py`, `verification.py`, `review_record_session.py` for `NEUTRALIZED|if False|if True or|and False and` printed `No matches found`.

**raw green:** the order's separate g7 green run was folded into the whole-file final run below (budget; disclosed in the return). That run is the first run after the last restore and it includes the new test.

**Not neutralized separately:** the negative half (a batch without places gets no sentence). It is asserted (`:445`) but a `True or` variant was not run.

## Final run — the whole file, nothing neutralized

```
.................................                                        [100%]
33 passed in 1.67s
```

## Amendment — review round 1

**Provenance:** claude / sonnet-5.5 (implementer, work order WO-1e). Head at the start was `5d7aaee3a8203068185e53133676d972162763c9`.
Every run is `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest <node> -q --tb=short`, the detector unedited, one node per run.
Each neutralization is one targeted Edit, undone by the inverse Edit; the restore receipt is the restored line quoted back from a Grep.
Nothing was redacted (no credential-like text appears). Dropped from every capture: the `UV_NATIVE_TLS` deprecation warning line.
Captures are far under the 32 KiB / 128 KiB ceilings.

**F6 (axis declarations) adds no neutralization run.** Every test in the file now has an `# axis:` line. Eight of them (`test_t2_edges_…`, `test_t4c_…`,
`test_t4_edges_…`, `test_t4_the_submit_guard_…`, `test_t6_kind_missing_counts_…`, `test_t7_unavailable_provenance_…`, `test_t7_the_seams_fold_stamps_…`,
`test_t8_…`) are declarations only: they state what the test bites and do not cite this record, because none of them was neutralized here or in the entries above.

### h2 — a re-raise and an open-blocker dedup keep the places but give the kept finding no description

Two call sites, one failure mode (the merge gives the kept finding a `searchDescription` it never named). Each site was neutralized and run on its own.
Representative test: `test_t5_a_reraise_and_an_open_blocker_dedup_keep_the_places_but_gain_no_description`. The merge in `_merge_same_finding` (`round_driver.py:1054`) is excluded on purpose and keeps the default `with_description=True`; it was not neutralized.

**neutralization A** (`round_driver.py:9838`, `_union_open_blockers`): `verification.apply_kind_members(kept, [kept, f], with_description=False)` → `… with_description=True)`.

**raw red A:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_t5_a_reraise_and_an_open_blocker_dedup_keep_the_places_but_gain_no_description _
/home/user/wt-2220/plugins/superheroes/lib/tests/test_c4_kind_of_mistake.py:355: in test_t5_a_reraise_and_an_open_blocker_dedup_keep_the_places_but_gain_no_description
    assert "searchDescription" not in batch
E   AssertionError: assert 'searchDescription' not in {'title': 'Retry without a cap', 'file': 'src/a.py', 'line': 2, 'severity': 'Important', ...}
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c4_kind_of_mistake.py::test_t5_a_reraise_and_an_open_blocker_dedup_keep_the_places_but_gain_no_description
1 failed in 5.50s
```
**restore A:** inverse Edit, done before neutralization B.

**neutralization B** (`round_driver.py:2287`, `_seed_ledger_entry`): `verification.apply_kind_members(entry, [existing, entry], with_description=False)` → `… with_description=True)`.

**raw red B** (A restored, so the run gets past the dedup assertion and fails on the re-raise one):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_t5_a_reraise_and_an_open_blocker_dedup_keep_the_places_but_gain_no_description _
/home/user/wt-2220/plugins/superheroes/lib/tests/test_c4_kind_of_mistake.py:360: in test_t5_a_reraise_and_an_open_blocker_dedup_keep_the_places_but_gain_no_description
    assert "searchDescription" not in entry
E   AssertionError: assert 'searchDescription' not in {'title': 'Retry without a cap', 'file': 'src/a.py', 'line': 2, 'severity': 'Important', ...}
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c4_kind_of_mistake.py::test_t5_a_reraise_and_an_open_blocker_dedup_keep_the_places_but_gain_no_description
1 failed in 2.53s
```
**restore B:** inverse Edit. **restore receipt:** `grep -n apply_kind_members round_driver.py` after the restore:
```
1054:    verification.apply_kind_members(merged, [existing, incoming])
2287:        verification.apply_kind_members(entry, [existing, entry], with_description=False)
9838:                verification.apply_kind_members(kept, [kept, f], with_description=False)
```
**raw green:**
```
.                                                                        [100%]
1 passed in 3.34s
```

### h3 — the seams artifact the adapter assembles carries the executed vendor, so the fold stamps the author on the durable path

Representative test: `test_t7_the_durable_seams_artifact_the_adapter_assembles_is_stamped_through_the_fold` (three parameters: an independent vendor with runner evidence, a maker family with runner evidence, and a landing with no runner evidence).

**neutralization** (`round_adapters.py:462`): `if phase == P_SEAMS:` → `if phase == P_SEAMS and False:`.

**raw red** (`-k test_t7_the_durable_seams_artifact`; the third parameter, no runner evidence, stays green because it expects no `ranManifest`):
```
FF.                                                                      [100%]
=================================== FAILURES ===================================
_ test_t7_the_durable_seams_artifact_the_adapter_assembles_is_stamped_through_the_fold[envelope0-True] _
/home/user/wt-2220/plugins/superheroes/lib/tests/test_c4_kind_of_mistake.py:509: in test_t7_the_durable_seams_artifact_the_adapter_assembles_is_stamped_through_the_fold
    assert ("ranManifest" in artifact) is (envelope["schema"] == RR.SEAT_RESULT_SCHEMA_V2)
E   AssertionError: assert ('ranManifest' in {'findings': [{'title': 'From seams', 'file': 'src/a.py', 'line': 2, 'severity': 'Important', ...}]}) is ('seat-result/2' == 'seat-result/2'
E
E       seat-result/2)
_ test_t7_the_durable_seams_artifact_the_adapter_assembles_is_stamped_through_the_fold[envelope1-False] _
/home/user/wt-2220/plugins/superheroes/lib/tests/test_c4_kind_of_mistake.py:509: in test_t7_the_durable_seams_artifact_the_adapter_assembles_is_stamped_through_the_fold
    assert ("ranManifest" in artifact) is (envelope["schema"] == RR.SEAT_RESULT_SCHEMA_V2)
E   AssertionError: assert ('ranManifest' in {'findings': [{'title': 'From seams', 'file': 'src/a.py', 'line': 2, 'severity': 'Important', ...}]}) is ('seat-result/2' == 'seat-result/2'
E
E       seat-result/2)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c4_kind_of_mistake.py::test_t7_the_durable_seams_artifact_the_adapter_assembles_is_stamped_through_the_fold[envelope0-True]
FAILED plugins/superheroes/lib/tests/test_c4_kind_of_mistake.py::test_t7_the_durable_seams_artifact_the_adapter_assembles_is_stamped_through_the_fold[envelope1-False]
2 failed, 1 passed, 38 deselected in 0.59s
```
The red stops at the `ranManifest` assertion, before the author assertion; the author assertion on the independent-vendor parameter is therefore unproven by this run.

**restore:** inverse Edit. **restore receipt:** `grep -n "phase == P_SEAMS" -A6 round_adapters.py`:
```
462:        if phase == P_SEAMS:
463-            # axis: the seams artifact carries the executed vendor the authentication above checked, so the fold stamps a search description's author on the durable path as the panel's `ranManifest` does — see bite-proof record c4_wo1_kind
464-            ran_manifest = _trusted_vendors(roster, indexed, dispatch_manifest, {}, orders_manifest,
465-                                            _maker_barred(state, config))
466-            if ran_manifest:
467-                artifact["ranManifest"] = ran_manifest
```
**raw green** (same selector):
```
...                                                                      [100%]
3 passed, 38 deselected in 0.48s
```

### h4 — place answers reach the rows of members merged into the audited finding

**SUPERSEDED by "Amendment — WO-1g redesign" below.** The `_record_place_results` merged-member copy this entry neutralizes is deleted; k3 replaces it.

Test: `test_t5_place_answers_reach_the_rows_of_members_merged_into_the_audited_finding`.

**neutralization** (`round_driver.py:3243`): `results = answers.get(into) if isinstance(into, str) else None` → `results = answers.get(into) if False and isinstance(into, str) else None`.

**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_t5_place_answers_reach_the_rows_of_members_merged_into_the_audited_finding _
/home/user/wt-2220/plugins/superheroes/lib/tests/test_c4_kind_of_mistake.py:317: in test_t5_place_answers_reach_the_rows_of_members_merged_into_the_audited_finding
    assert [p.get("fixed") for p in by_key["k-shared"]] == [True, True]
E   assert [None, None] == [True, True]
E
E     At index 0 diff: None != True
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c4_kind_of_mistake.py::test_t5_place_answers_reach_the_rows_of_members_merged_into_the_audited_finding
1 failed in 0.40s
```
**restore:** inverse Edit. **restore receipt:** `grep -n "results = answers.get(into)" round_driver.py`: `3243:            results = answers.get(into) if isinstance(into, str) else None`.

**raw green:**
```
.                                                                        [100%]
1 passed in 0.48s
```
The unanswered-place half (`k-partial`'s place 7 stays unset) and the not-merged half (`k-other` untouched) are asserted in the same test and were not neutralized separately.

### h5 — the panel's kind-missing count is added to the count the round already holds

Test: `test_t6_the_first_panel_wave_adds_its_kind_missing_count_to_the_one_an_earlier_audit_recorded`.

**neutralization** (`round_driver.py:4148`): `(held_kind_missing if _is_plain_int(held_kind_missing) else 0)` → `(held_kind_missing if False and _is_plain_int(held_kind_missing) else 0)`.

**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_t6_the_first_panel_wave_adds_its_kind_missing_count_to_the_one_an_earlier_audit_recorded _
/home/user/wt-2220/plugins/superheroes/lib/tests/test_c4_kind_of_mistake.py:399: in test_t6_the_first_panel_wave_adds_its_kind_missing_count_to_the_one_an_earlier_audit_recorded
    assert state["rounds"]["1"]["kindMissing"] == 3  # 2 held + the panel's 1 finding without a kind
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E   assert 1 == 3
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c4_kind_of_mistake.py::test_t6_the_first_panel_wave_adds_its_kind_missing_count_to_the_one_an_earlier_audit_recorded
1 failed in 0.49s
```
**restore:** inverse Edit. **restore receipt:** `grep -n held_kind_missing round_driver.py`:
```
4146:    held_kind_missing = state["rounds"].get(str(state["round"]), {}).get(KIND_MISSING_FIELD)
4148:                  (held_kind_missing if _is_plain_int(held_kind_missing) else 0)
```
**raw green:**
```
.                                                                        [100%]
1 passed in 0.39s
```
The "no earlier count, so the count is the panel's own" edge is asserted by the existing `test_t6_kind_missing_counts_every_compile_…` (`== 0`) and `test_t6_a_null_or_blank_…` (`== 1`), which pass unchanged.

`git status --porcelain` after the final run lists `M plugins/superheroes/lib/tests/test_c4_kind_of_mistake.py` and untracked files that were not made by this dispatch (`.bash_profile`, `.bashrc`, `.claude/`, `.gitconfig`, `.gitmodules`, `.idea`, `.mcp.json`, `.profile`, `.ripgreprc`, `.vscode`, `.zprofile`, `.zshrc`); no product file is modified.

## Amendment — WO-1g redesign

**Provenance:** claude / sonnet-5.5 (implementer, work order WO-1g). Head at the start was `e57b5322860ae6fe50be0bd80b0242d76b61a61e`.
The per-place answers now ride the fix disposition: `placeResults` is a member of `DISPOSITION_FAMILY_FIELDS`, written by `_fold_audits` through `_record_disposition(..., "fixed", placeResults=...)`
for every id in the outcome's `discharged` list (which holds both clearing rulings: `audits.py` appends a `discharged-but-new-issue` clearance to `discharged` at the same place as a `discharged` one).
The record reads each place's `fixed` at render time in `review_record_session._kind_with_place_results`. The g6a, g6b, g6c and h4 entries above guard deleted code and are superseded by k1-k4.
Every run is `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest <file> -k <node> -q --tb=short`, the detector unedited, one node per run.
Each neutralization is one targeted Edit, undone by the inverse Edit; the restore receipt is the restored line quoted back from a Grep. Nothing was redacted (no credential-like text appears).
Dropped from every capture: the `UV_NATIVE_TLS` deprecation warning line. Captures are far under the 32 KiB / 128 KiB ceilings.
Guarded-element set: k1, k2, k3, k4. Spares run beyond the order: k2b, k3b, k4b (sub-elements of k2, k3, k4).

### k1 — the chokepoint write of `placeResults`, for both clearing rulings

Detector: `test_t5_the_clearing_fold_writes_the_places_answers_into_the_fix_disposition`, parametrized over `discharged` and `discharged-but-new-issue`.

**neutralization** (`round_driver.py:8907`, `_fold_audits`): `placeResults=place_answers.get(tid) or None)` → `placeResults=None)  # k1 NEUTRALIZED: …`.

**raw red:**
```
FF                                                                       [100%]
=================================== FAILURES ===================================
_ test_t5_the_clearing_fold_writes_the_places_answers_into_the_fix_disposition[discharged] _
/home/user/wt-2220/plugins/superheroes/lib/tests/test_c4_kind_of_mistake.py:327: in test_t5_the_clearing_fold_writes_the_places_answers_into_the_fix_disposition
    assert row["disposition"] == "fixed" and row["placeResults"] == answers
                                             ^^^^^^^^^^^^^^^^^^^
E   KeyError: 'placeResults'
_ test_t5_the_clearing_fold_writes_the_places_answers_into_the_fix_disposition[discharged-but-new-issue] _
/home/user/wt-2220/plugins/superheroes/lib/tests/test_c4_kind_of_mistake.py:327: in test_t5_the_clearing_fold_writes_the_places_answers_into_the_fix_disposition
    assert row["disposition"] == "fixed" and row["placeResults"] == answers
                                             ^^^^^^^^^^^^^^^^^^^
E   KeyError: 'placeResults'
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c4_kind_of_mistake.py::test_t5_the_clearing_fold_writes_the_places_answers_into_the_fix_disposition[discharged]
FAILED plugins/superheroes/lib/tests/test_c4_kind_of_mistake.py::test_t5_the_clearing_fold_writes_the_places_answers_into_the_fix_disposition[discharged-but-new-issue]
2 failed, 45 deselected in 1.04s
```
**restore:** inverse Edit. **restore receipt:** Grep after the restore: `8907:                            placeResults=place_answers.get(tid) or None)`.

**raw green:**
```
..                                                                       [100%]
2 passed, 45 deselected in 2.20s
```

### k2 — the render-time read of a finding's own disposition

Detector: `test_t5_an_unanswered_or_unfixed_place_reads_not_fixed_and_so_does_every_place_of_an_unfixed_disposition`.

**neutralization** (`review_record_session.py:625`, `_kind_with_place_results`): `for row in (rep.get("placeResults") if fixed_rep else None) or []:` → `for row in []:  # k2 NEUTRALIZED: …`.

**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_t5_an_unanswered_or_unfixed_place_reads_not_fixed_and_so_does_every_place_of_an_unfixed_disposition _
/home/user/wt-2220/plugins/superheroes/lib/tests/test_c4_kind_of_mistake.py:389: in test_t5_an_unanswered_or_unfixed_place_reads_not_fixed_and_so_does_every_place_of_an_unfixed_disposition
    assert _fixed_of(found["f-1"]) == [True, False, None]
E   assert [None, None, None] == [True, False, None]
E     
E     At index 0 diff: None != True
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c4_kind_of_mistake.py::test_t5_an_unanswered_or_unfixed_place_reads_not_fixed_and_so_does_every_place_of_an_unfixed_disposition
1 failed, 46 deselected in 0.50s
```

**restore:** inverse Edit. **restore receipt:** Grep after the restore: `625:    for row in (rep.get("placeResults") if fixed_rep else None) or []:`.

**raw green:**
```
.                                                                        [100%]
1 passed, 46 deselected in 0.43s
```

**k2b (spare) — a disposition that is not `fixed` answers nothing.** Neutralization (`review_record_session.py`): `fixed_rep = isinstance(rep, dict) and rep.get("disposition") == "fixed"` → `fixed_rep = isinstance(rep, dict)  # k2b NEUTRALIZED: …`. Same detector.
**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_t5_an_unanswered_or_unfixed_place_reads_not_fixed_and_so_does_every_place_of_an_unfixed_disposition _
/home/user/wt-2220/plugins/superheroes/lib/tests/test_c4_kind_of_mistake.py:390: in test_t5_an_unanswered_or_unfixed_place_reads_not_fixed_and_so_does_every_place_of_an_unfixed_disposition
    assert _fixed_of(found["f-2"]) == [None, None]
E   assert [True, True] == [None, None]
E     
E     At index 0 diff: True != None
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c4_kind_of_mistake.py::test_t5_an_unanswered_or_unfixed_place_reads_not_fixed_and_so_does_every_place_of_an_unfixed_disposition
1 failed, 46 deselected in 0.54s
```
**restore:** inverse Edit; a Grep for `NEUTRALIZED` over `plugins/superheroes/lib/*.py` after it printed `No matches found`. **raw green:** the same selector's green run was folded into the four-file run after the last restore: `136 passed in 5.11s` (`test_c4_kind_of_mistake.py`, `test_layer2g_ledger_reader_1272.py`, `test_round_orders.py`, `test_disposition_family_home_1272.py`).

### k3 — a merged member reads its representative's disposition through `mergedInto`, the representative's own place included

Detector: `test_t5_a_merged_member_reads_its_representatives_places_and_the_representatives_own_place`.

**neutralization** (`review_record_session.py:622`): `rep = sc.resolve_merged_into_entry(own, by_key) if isinstance(own, dict) else None` → `rep = own if isinstance(own, dict) else None  # k3 NEUTRALIZED: …`.

**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_t5_a_merged_member_reads_its_representatives_places_and_the_representatives_own_place _
/home/user/wt-2220/plugins/superheroes/lib/tests/test_c4_kind_of_mistake.py:370: in test_t5_a_merged_member_reads_its_representatives_places_and_the_representatives_own_place
    assert _fixed_of(found["f-k-shared"]) == [True, True]
E   assert [None, None] == [True, True]
E     
E     At index 0 diff: None != True
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c4_kind_of_mistake.py::test_t5_a_merged_member_reads_its_representatives_places_and_the_representatives_own_place
1 failed, 46 deselected in 0.44s
```

**restore:** inverse Edit. **restore receipt:** Grep after the restore: `622:    rep = sc.resolve_merged_into_entry(own, by_key) if isinstance(own, dict) else None`.

**raw green:**
```
.                                                                        [100%]
1 passed, 46 deselected in 0.52s
```

**k3b (spare) — the representative's own place.** Neutralization (`review_record_session.py:630`): `own_place = (rep.get("file"), rep.get("line")) if fixed_rep and rep is not own else None` → `own_place = None  # k3b NEUTRALIZED: …`. Same detector.
**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_t5_a_merged_member_reads_its_representatives_places_and_the_representatives_own_place _
/home/user/wt-2220/plugins/superheroes/lib/tests/test_c4_kind_of_mistake.py:370: in test_t5_a_merged_member_reads_its_representatives_places_and_the_representatives_own_place
    assert _fixed_of(found["f-k-shared"]) == [True, True]
E   assert [True, None] == [True, True]
E     
E     At index 1 diff: None != True
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c4_kind_of_mistake.py::test_t5_a_merged_member_reads_its_representatives_places_and_the_representatives_own_place
1 failed, 46 deselected in 0.53s
```
**restore:** inverse Edit. **restore receipt:** Grep after the restore: `630:    own_place = (rep.get("file"), rep.get("line")) if fixed_rep and rep is not own else None`.
**raw green:**
```
.                                                                        [100%]
1 passed, 46 deselected in 0.40s
```

### k4 — survival through the archive, which is the family carry

Detector: `test_t5_place_results_survive_save_reload_audit_archive_and_render`.

**neutralization** (`round_driver.py:3221`, `_archive_departures`): `if field in prior and field not in replacement:` → `… and field != "placeResults":  # k4 NEUTRALIZED: …`. The generic family carry loop skips this one member; every other member (the disposition itself included) is still carried.

**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
______ test_t5_place_results_survive_save_reload_audit_archive_and_render ______
/home/user/wt-2220/plugins/superheroes/lib/tests/test_c4_kind_of_mistake.py:352: in test_t5_place_results_survive_save_reload_audit_archive_and_render
    assert archived["disposition"] == "fixed" and archived["placeResults"] == [_row(3, True), _row(19, True)]
                                                  ^^^^^^^^^^^^^^^^^^^^^^^^
E   KeyError: 'placeResults'
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c4_kind_of_mistake.py::test_t5_place_results_survive_save_reload_audit_archive_and_render
1 failed, 46 deselected in 0.44s
```

**restore:** inverse Edit. **restore receipt:** Grep after the restore: `3221:                    if field in prior and field not in replacement:`.

**raw green:**
```
.                                                                        [100%]
1 passed, 46 deselected in 0.44s
```

**k4b (spare) — membership in `DISPOSITION_FAMILY_FIELDS`.** Neutralization (`session_contract.py:381`): `"placeResults"` removed from the tuple (`# k4b NEUTRALIZED: …`). Same detector.
**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
______ test_t5_place_results_survive_save_reload_audit_archive_and_render ______
/home/user/wt-2220/plugins/superheroes/lib/tests/test_c4_kind_of_mistake.py:346: in test_t5_place_results_survive_save_reload_audit_archive_and_render
    assert _ledger_of(state, key)["placeResults"] == [_row(3, True), _row(19, True)]
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E   KeyError: 'placeResults'
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c4_kind_of_mistake.py::test_t5_place_results_survive_save_reload_audit_archive_and_render
1 failed, 46 deselected in 0.49s
```
The red stops at the assertion before the archive: the family write (`apply_disposition_family`) drops a field the tuple does not name, so the answer never reaches the ledger row. This shows the family membership is what carries it everywhere; it is not an archive-specific red (k4 is).
**restore:** inverse Edit. **restore receipt:** Grep after the restore: `381:    "disposition", "dispositionRound", "dispositionReceipt", "placeResults", "refutedReason",`.
**raw green:**
```
.                                                                        [100%]
1 passed, 46 deselected in 0.46s
```

**Not neutralized separately:** the duplicate-row rule (`answers.get(pair, True) and row["fixed"]`) and the chain-end `fixed: None` for a dangling `mergedInto`; both are asserted in `test_t5_an_unanswered_or_unfixed_…` and are unproven by a run.
