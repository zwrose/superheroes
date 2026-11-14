# Bite-proof record: wo1_scope_ruling_2478

A verifier refutation that rests on a scope ruling is recorded as a ruling or left for the owner, never as shown wrong.

**Detector:** `finding_outcomes.ruling_rest` / `rests_on_ruling` and their consumers, guarded by
`plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py`.

**How the runs were made.** Each red and green run is the order's pinned command
`scripts/pinned-python -B -m pytest <node ids in the one new test file> -q -p no:cacheprovider`, narrowed to the test
node(s) that guard the element, with `--tb=short` or `--tb=line` added to shape the traceback only (nothing filtered).
Each neutralization is one targeted edit of the guarded line, and each restore is the inverse edit (never `git checkout`,
`restore`, `reset` or `stash`). The first line of every capture, `warning: The UV_NATIVE_TLS environment variable is
deprecated ...`, is a uv notice and is omitted here; nothing else is cut. No secrets or private URLs appear in a capture
(the URLs in the fixtures are the invented `o/r` ones). Every capture is far below the 32 KiB ceiling.

**Guarded-element set (declared by the order, all seven proven, none grouped except E7's two sites, below):**
E1 key match, E2 phrase match, E3 the mark written by `apply_verdicts`, E4 `_decide`'s ruling / left-for-owner branch,
E5 the `decidedBy` requirement, E6 `_recheck_carried`'s bypass of the two unchanged guards, E7 repeat precedence
(`_grade_verdict` and `decision_outcome`).

After the last restore, a search of the six edited library files for the neutralization shapes (`if False`,
`None and finding_outcomes`, `False and`) found only one older line (`review_record_session.py:1554`, `v.get("planned") is True
and v.get("ran") is False`), which is not mine.

---

## E1 — `ruling_rest` key match (`finding_outcomes.py`, the `len(named) == 1` branch)

Axis: a reason that names exactly one live standing-ruling key rests on that ruling, and the mark carries that key.

**Neutralization:** `    if len(named) == 1:` became `    if False and len(named) == 1:`.

**Raw red** (`test_a1_...`, `test_b1_...`):

```
FF                                                                       [100%]
=================================== FAILURES ===================================
____ test_a1_a_text_naming_exactly_one_live_ruling_key_rests_on_that_ruling ____
/home/user/wt-2478/plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py:71: in test_a1_a_text_naming_exactly_one_live_ruling_key_rests_on_that_ruling
    assert FO.ruling_rest(f"see {KEY} for why", [KEY]) == {"findingKey": KEY}
E   AssertionError: assert None == {'findingKey': 'rk:src/foo.py:12:unchecked-index'}
E    +  where None = <function ruling_rest at 0x7f06ed138540>('see rk:src/foo.py:12:unchecked-index for why', ['rk:src/foo.py:12:unchecked-index'])
E    +    where <function ruling_rest at 0x7f06ed138540> = FO.ruling_rest
_ test_b1_a_refuted_naming_a_standing_ruling_key_is_marked_and_the_record_reads_the_ruling_with_its_decision _
/home/user/wt-2478/plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py:130: in test_b1_a_refuted_naming_a_standing_ruling_key_is_marked_and_the_record_reads_the_ruling_with_its_decision
    assert grade == {"verdict": "wrong", "reason": ON_RULING, "restsOnRuling": {"findingKey": KEY}}
E   AssertionError: assert {'verdict': '...ngKey': None}} == {'verdict': '...ecked-index'}}
E     
E     Omitting 2 identical items, use -vv to show
E     Differing items:
E     {'restsOnRuling': {'findingKey': None}} != {'restsOnRuling': {'findingKey': 'rk:src/foo.py:12:unchecked-index'}}
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py::test_a1_a_text_naming_exactly_one_live_ruling_key_rests_on_that_ruling
FAILED plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py::test_b1_a_refuted_naming_a_standing_ruling_key_is_marked_and_the_record_reads_the_ruling_with_its_decision
2 failed in 0.35s
```

**Restore:** inverse edit, `    if False and len(named) == 1:` back to `    if len(named) == 1:`.
**Restore receipt:** a search of `finding_outcomes.py` for `if len\(named\) == 1|if False` returned only
`47:    if len(named) == 1:`; the restored line is `    if len(named) == 1:`; `git diff -U0` of the file shows only the
added block (no `if False`).

**Raw green:**

```
..                                                                       [100%]
2 passed in 0.36s
```

---

## E2 — `ruling_rest` phrase match (`finding_outcomes.py`, the `_RULING_PHRASE.search(text)` branch)

Axis: a reason that speaks of a standing or out-of-scope ruling rests on a ruling even with no key; a bare "out of scope" does not.

**Neutralization:** `    if len(named) > 1 or _RULING_PHRASE.search(text):` became
`    if len(named) > 1 or False and _RULING_PHRASE.search(text):`.

**Raw red** (`test_a2_...` all 11 phrases, `test_a6_...`; `--tb=line`):

```
FFFFFFFFFFFF                                                             [100%]
=================================== FAILURES ===================================
E   AssertionError: assert None == {'findingKey': None}
     +  where None = <function ruling_rest at 0x7f5df0f58540>('the standing ruling covers this')
     +    where <function ruling_rest at 0x7f5df0f58540> = FO.ruling_rest
/home/user/wt-2478/plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py:85: AssertionError: assert None == {'findingKey': None}
E   AssertionError: assert None == {'findingKey': None}
     +  where None = <function ruling_rest at 0x7f5df0f58540>('Standing Rulings cover this')
     +    where <function ruling_rest at 0x7f5df0f58540> = FO.ruling_rest
/home/user/wt-2478/plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py:85: AssertionError: assert None == {'findingKey': None}
E   AssertionError: assert None == {'findingKey': None}
     +  where None = <function ruling_rest at 0x7f5df0f58540>('standing-ruling covers this')
     +    where <function ruling_rest at 0x7f5df0f58540> = FO.ruling_rest
/home/user/wt-2478/plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py:85: AssertionError: assert None == {'findingKey': None}
E   AssertionError: assert None == {'findingKey': None}
     +  where None = <function ruling_rest at 0x7f5df0f58540>('this was ruled out of scope')
     +    where <function ruling_rest at 0x7f5df0f58540> = FO.ruling_rest
/home/user/wt-2478/plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py:85: AssertionError: assert None == {'findingKey': None}
E   AssertionError: assert None == {'findingKey': None}
     +  where None = <function ruling_rest at 0x7f5df0f58540>('the owner ruled it out of scope')
     +    where <function ruling_rest at 0x7f5df0f58540> = FO.ruling_rest
/home/user/wt-2478/plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py:85: AssertionError: assert None == {'findingKey': None}
E   AssertionError: assert None == {'findingKey': None}
     +  where None = <function ruling_rest at 0x7f5df0f58540>('they ruled this out of scope')
     +    where <function ruling_rest at 0x7f5df0f58540> = FO.ruling_rest
/home/user/wt-2478/plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py:85: AssertionError: assert None == {'findingKey': None}
E   AssertionError: assert None == {'findingKey': None}
     +  where None = <function ruling_rest at 0x7f5df0f58540>('the out of scope ruling applies')
     +    where <function ruling_rest at 0x7f5df0f58540> = FO.ruling_rest
/home/user/wt-2478/plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py:85: AssertionError: assert None == {'findingKey': None}
E   AssertionError: assert None == {'findingKey': None}
     +  where None = <function ruling_rest at 0x7f5df0f58540>('the out-of-scope rulings apply')
     +    where <function ruling_rest at 0x7f5df0f58540> = FO.ruling_rest
/home/user/wt-2478/plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py:85: AssertionError: assert None == {'findingKey': None}
E   AssertionError: assert None == {'findingKey': None}
     +  where None = <function ruling_rest at 0x7f5df0f58540>('it sits on an out-of-scope row')
     +    where <function ruling_rest at 0x7f5df0f58540> = FO.ruling_rest
/home/user/wt-2478/plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py:85: AssertionError: assert None == {'findingKey': None}
E   AssertionError: assert None == {'findingKey': None}
     +  where None = <function ruling_rest at 0x7f5df0f58540>('it matches the scope rows')
     +    where <function ruling_rest at 0x7f5df0f58540> = FO.ruling_rest
/home/user/wt-2478/plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py:85: AssertionError: assert None == {'findingKey': None}
E   AssertionError: assert None == {'findingKey': None}
     +  where None = <function ruling_rest at 0x7f5df0f58540>('an OUT  OF  SCOPE   ruling')
     +    where <function ruling_rest at 0x7f5df0f58540> = FO.ruling_rest
/home/user/wt-2478/plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py:85: AssertionError: assert None == {'findingKey': None}
E   AssertionError: assert False is True
     +  where False = <function rests_on_ruling at 0x7f5df0f585e0>({'verdict': 'wrong', 'reason': 'the standing ruling on rk:src/foo.py:12:unchecked-index routes this to the follow-up, so it is not raised here'})
     +    where <function rests_on_ruling at 0x7f5df0f585e0> = FO.rests_on_ruling
/home/user/wt-2478/plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py:112: AssertionError: assert False is True
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py::test_a2_the_ruling_phrases_rest_on_a_ruling_with_no_key[the standing ruling covers this]
FAILED plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py::test_a2_the_ruling_phrases_rest_on_a_ruling_with_no_key[Standing Rulings cover this]
FAILED plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py::test_a2_the_ruling_phrases_rest_on_a_ruling_with_no_key[standing-ruling covers this]
FAILED plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py::test_a2_the_ruling_phrases_rest_on_a_ruling_with_no_key[this was ruled out of scope]
FAILED plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py::test_a2_the_ruling_phrases_rest_on_a_ruling_with_no_key[the owner ruled it out of scope]
FAILED plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py::test_a2_the_ruling_phrases_rest_on_a_ruling_with_no_key[they ruled this out of scope]
FAILED plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py::test_a2_the_ruling_phrases_rest_on_a_ruling_with_no_key[the out of scope ruling applies]
FAILED plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py::test_a2_the_ruling_phrases_rest_on_a_ruling_with_no_key[the out-of-scope rulings apply]
FAILED plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py::test_a2_the_ruling_phrases_rest_on_a_ruling_with_no_key[it sits on an out-of-scope row]
FAILED plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py::test_a2_the_ruling_phrases_rest_on_a_ruling_with_no_key[it matches the scope rows]
FAILED plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py::test_a2_the_ruling_phrases_rest_on_a_ruling_with_no_key[an OUT  OF  SCOPE   ruling]
FAILED plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py::test_a6_rests_on_ruling_reads_the_mark_or_the_old_phrase_and_only_on_a_wrong_grade
12 failed in 0.35s
```

**Restore:** inverse edit back to `    if len(named) > 1 or _RULING_PHRASE.search(text):`.
**Restore receipt:** the restored line is `    if len(named) > 1 or _RULING_PHRASE.search(text):`; the `git diff -U0` of `finding_outcomes.py` after all restores shows only the intended added block (quoted in the return).

**Raw green:**

```
............                                                             [100%]
12 passed in 0.31s
```

---

## E3 — the `restsOnRuling` mark written by `apply_verdicts` (`verification.py`)

Axis: a REFUTED that rests on a ruling still drops, and its wrong grade carries the mark with the key.

**Neutralization:** `            rest = finding_outcomes.ruling_rest(` became `            rest = None and finding_outcomes.ruling_rest(`.

**Raw red** (`test_b1_...`, `test_f2_...`):

```
FF                                                                       [100%]
=================================== FAILURES ===================================
_ test_b1_a_refuted_naming_a_standing_ruling_key_is_marked_and_the_record_reads_the_ruling_with_its_decision _
/home/user/wt-2478/plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py:130: in test_b1_a_refuted_naming_a_standing_ruling_key_is_marked_and_the_record_reads_the_ruling_with_its_decision
    assert grade == {"verdict": "wrong", "reason": ON_RULING, "restsOnRuling": {"findingKey": KEY}}
E   AssertionError: assert {'verdict': '... raised here'} == {'verdict': '...ecked-index'}}
E     
E     Omitting 2 identical items, use -vv to show
E     Right contains 1 more item:
E     {'restsOnRuling': {'findingKey': 'rk:src/foo.py:12:unchecked-index'}}
E     Use -v to get more diff
_ test_f2_the_evidence_text_counts_and_a_code_scope_refutation_is_not_a_ruling _
/home/user/wt-2478/plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py:312: in test_f2_the_evidence_text_counts_and_a_code_scope_refutation_is_not_a_ruling
    assert done["drops"][0]["grade"]["restsOnRuling"] == {"findingKey": KEY}
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E   KeyError: 'restsOnRuling'
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py::test_b1_a_refuted_naming_a_standing_ruling_key_is_marked_and_the_record_reads_the_ruling_with_its_decision
FAILED plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py::test_f2_the_evidence_text_counts_and_a_code_scope_refutation_is_not_a_ruling
2 failed in 0.37s
```

**Restore:** inverse edit back to `            rest = finding_outcomes.ruling_rest(`.
**Restore receipt:** restored line quoted above; `git diff -U0` of `verification.py` shows the intended hunks only (the signature, docstring, the `rest = finding_outcomes.ruling_rest(...)` line and the `grade` dict).

**Raw green:**

```
..                                                                       [100%]
2 passed in 0.43s
```

---

## E4 — `_decide`'s ruling / left-for-owner branch (`review_record_session.py`)

Axis: a refuted row whose wrong grade rests on a ruling never reads `shown-wrong`.

**Neutralization:** `            if finding_outcomes.rests_on_ruling(grade, why):` became
`            if False and finding_outcomes.rests_on_ruling(grade, why):`.

**Raw red** (`test_b1_...`, `test_c2_...`):

```
FF                                                                       [100%]
=================================== FAILURES ===================================
_ test_b1_a_refuted_naming_a_standing_ruling_key_is_marked_and_the_record_reads_the_ruling_with_its_decision _
/home/user/wt-2478/plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py:132: in test_b1_a_refuted_naming_a_standing_ruling_key_is_marked_and_the_record_reads_the_ruling_with_its_decision
    assert outcome == "ruling" and outcome != "shown-wrong"
E   AssertionError: assert ('shown-wrong' == 'ruling'
E     
E     - ruling
E     + shown-wrong)
_ test_c2_a_left_for_owner_refutation_carries_no_decision_and_a_non_dict_mark_falls_back_to_the_phrase _
/home/user/wt-2478/plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py:189: in test_c2_a_left_for_owner_refutation_carries_no_decision_and_a_non_dict_mark_falls_back_to_the_phrase
    assert found["outcome"] == "left-for-owner" and found["decidedBy"] is None
E   AssertionError: assert ('shown-wrong' == 'left-for-owner'
E     
E     - left-for-owner
E     + shown-wrong)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py::test_b1_a_refuted_naming_a_standing_ruling_key_is_marked_and_the_record_reads_the_ruling_with_its_decision
FAILED plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py::test_c2_a_left_for_owner_refutation_carries_no_decision_and_a_non_dict_mark_falls_back_to_the_phrase
2 failed in 0.39s
```

**Restore:** inverse edit back to `            if finding_outcomes.rests_on_ruling(grade, why):`.
**Restore receipt:** restored line quoted above; `git diff -U0` of `review_record_session.py` shows the intended hunks only (`copy` and `finding_outcomes` imports, the three helpers, the `_decide` branch, the `decidedBy` line).

**Raw green:**

```
..                                                                       [100%]
2 passed in 0.45s
```

---

## E5 — the `decidedBy` requirement (`review_record_session.py`, `_scope_ruling_for`)

Axis: a ruling row with provenance but no dict `decidedBy` (an advisor message, a paraphrase) is not followable, so its refutation is left for the owner.

**Neutralization:** `    if not isinstance(sc.decided_by_of(row), dict):` became
`    if False and not isinstance(sc.decided_by_of(row), dict):`.

**Raw red** (`test_c1_...`, seven parameters):

```
FFF....                                                                  [100%]
=================================== FAILURES ===================================
_ test_c1_a_refutation_whose_ruling_cannot_be_followed_is_left_for_the_owner[provenance-but-no-decidedBy] _
/home/user/wt-2478/plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py:180: in test_c1_a_refutation_whose_ruling_cannot_be_followed_is_left_for_the_owner
    assert outcome == "left-for-owner" and outcome != "shown-wrong"
E   AssertionError: assert ('ruling' == 'left-for-owner'
E     
E     - left-for-owner
E     + ruling)
_ test_c1_a_refutation_whose_ruling_cannot_be_followed_is_left_for_the_owner[decidedBy-absent] _
/home/user/wt-2478/plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py:180: in test_c1_a_refutation_whose_ruling_cannot_be_followed_is_left_for_the_owner
    assert outcome == "left-for-owner" and outcome != "shown-wrong"
E   AssertionError: assert ('ruling' == 'left-for-owner'
E     
E     - left-for-owner
E     + ruling)
_ test_c1_a_refutation_whose_ruling_cannot_be_followed_is_left_for_the_owner[decidedBy-not-a-dict] _
/home/user/wt-2478/plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py:180: in test_c1_a_refutation_whose_ruling_cannot_be_followed_is_left_for_the_owner
    assert outcome == "left-for-owner" and outcome != "shown-wrong"
E   AssertionError: assert ('ruling' == 'left-for-owner'
E     
E     - left-for-owner
E     + ruling)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py::test_c1_a_refutation_whose_ruling_cannot_be_followed_is_left_for_the_owner[provenance-but-no-decidedBy]
FAILED plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py::test_c1_a_refutation_whose_ruling_cannot_be_followed_is_left_for_the_owner[decidedBy-absent]
FAILED plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py::test_c1_a_refutation_whose_ruling_cannot_be_followed_is_left_for_the_owner[decidedBy-not-a-dict]
3 failed, 4 passed in 0.37s
```

**Restore:** inverse edit back to `    if not isinstance(sc.decided_by_of(row), dict):`.
**Restore receipt:** restored line quoted above; it is the line the `git diff -U0` of `review_record_session.py` shows in the `_scope_ruling_for` hunk.

**Raw green:**

```
.......                                                                  [100%]
7 passed in 0.39s
```

---

## E6 — `_recheck_carried`'s bypass of the two unchanged guards (`review_record.py`)

Axis: a shown-wrong whose grade rested on a scope ruling skips "shown wrong without this session's verifier grade" and "shown wrong in the earlier record" and moves to fixed on a fixed check.

**Neutralization:** `        on_ruling = shown_wrong and finding_outcomes.rests_on_ruling(` became
`        on_ruling = False and shown_wrong and finding_outcomes.rests_on_ruling(`.

**Raw red** (`test_d1_...`, two parameters):

```
FF                                                                       [100%]
=================================== FAILURES ===================================
_ test_d1_a_shown_wrong_that_rested_on_a_ruling_moves_to_fixed_though_the_earlier_record_lists_it_shown_wrong[old-shape-phrase] _
/home/user/wt-2478/plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py:221: in test_d1_a_shown_wrong_that_rested_on_a_ruling_moves_to_fixed_though_the_earlier_record_lists_it_shown_wrong
    assert f["outcome"] == "fixed"
E   AssertionError: assert 'shown-wrong' == 'fixed'
E     
E     - fixed
E     + shown-wrong
_ test_d1_a_shown_wrong_that_rested_on_a_ruling_moves_to_fixed_though_the_earlier_record_lists_it_shown_wrong[marked-grade] _
/home/user/wt-2478/plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py:221: in test_d1_a_shown_wrong_that_rested_on_a_ruling_moves_to_fixed_though_the_earlier_record_lists_it_shown_wrong
    assert f["outcome"] == "fixed"
E   AssertionError: assert 'shown-wrong' == 'fixed'
E     
E     - fixed
E     + shown-wrong
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py::test_d1_a_shown_wrong_that_rested_on_a_ruling_moves_to_fixed_though_the_earlier_record_lists_it_shown_wrong[old-shape-phrase]
FAILED plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py::test_d1_a_shown_wrong_that_rested_on_a_ruling_moves_to_fixed_though_the_earlier_record_lists_it_shown_wrong[marked-grade]
2 failed in 0.29s
```

**Restore:** inverse edit back to `        on_ruling = shown_wrong and finding_outcomes.rests_on_ruling(`.
**Restore receipt:** restored line quoted above; the `git diff -U0` of `review_record.py` shows it as the added `on_ruling = shown_wrong and finding_outcomes.rests_on_ruling(grade, f.get("reason"))` line.

**Raw green:**

```
..                                                                       [100%]
2 passed in 0.37s
```

---

## E7 — repeat precedence: `_grade_verdict` (`round_driver.py`) and `decision_outcome` (`repeat_marks.py`)

Axis: a wrong grade that rests on a scope ruling neither keeps an earlier fixed/shown-wrong repeat as a code refutation
nor proves `fixHolds`; an earlier shown-wrong that rests on a ruling reads as open.

Two sites, one failure mode (a scope refutation read as a code refutation by the repeat table). Both were neutralized in one
run; the three tests are separate, each reaching only its own site (`test_e1_...` reaches `_grade_verdict`,
`test_e2_...` and `test_e3_...` reach `decision_outcome`), so the red shows each site bites on its own test.

**Neutralization:** in `round_driver.py` `    if finding_outcomes.rests_on_ruling(grade):` became
`    if False and finding_outcomes.rests_on_ruling(grade):`; in `repeat_marks.py`
`    if outcome == SHOWN_WRONG and finding_outcomes.rests_on_ruling(` became
`    if False and outcome == SHOWN_WRONG and finding_outcomes.rests_on_ruling(`.

**Raw red** (`test_e1_...`, `test_e2_...`, `test_e3_...`):

```
FFF                                                                      [100%]
=================================== FAILURES ===================================
_ test_e1_a_repeat_whose_grade_rests_on_a_ruling_is_no_code_refutation_and_proves_no_fix _
/home/user/wt-2478/plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py:256: in test_e1_a_repeat_whose_grade_rests_on_a_ruling_is_no_code_refutation_and_proves_no_fix
    assert RD._grade_verdict(on_ruling) is None
E   AssertionError: assert 'wrong' is None
E    +  where 'wrong' = <function _grade_verdict at 0x7f4164d80e00>({'grade': {'verdict': 'wrong', 'reason': 'the standing ruling on rk:src/foo.py:12:unchecked-index routes this to the follow-up, so it is not raised here', 'restsOnRuling': {'findingKey': 'rk:src/foo.py:12:unchecked-index'}}})
E    +    where <function _grade_verdict at 0x7f4164d80e00> = RD._grade_verdict
_ test_e2_an_earlier_shown_wrong_that_rests_on_a_ruling_reads_open_so_its_repeat_is_judged_fresh _
/home/user/wt-2478/plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py:273: in test_e2_an_earlier_shown_wrong_that_rests_on_a_ruling_reads_open_so_its_repeat_is_judged_fresh
    assert RM.decision_outcome(entry_) is None
E   AssertionError: assert 'shown-wrong' is None
E    +  where 'shown-wrong' = <function decision_outcome at 0x7f4164e1a200>({'outcome': 'shown-wrong', 'grade': {'verdict': 'wrong', 'reason': 'the standing ruling on rk:src/foo.py:12:unchecked-...this to the follow-up, so it is not raised here', 'restsOnRuling': {'findingKey': 'rk:src/foo.py:12:unchecked-index'}}})
E    +    where <function decision_outcome at 0x7f4164e1a200> = RM.decision_outcome
_ test_e3_a_record_finding_shown_wrong_on_a_ruling_pools_with_its_grade_and_reads_open _
/home/user/wt-2478/plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py:286: in test_e3_a_record_finding_shown_wrong_on_a_ruling_pools_with_its_grade_and_reads_open
    assert RM.decision_outcome(on_ruling) is None
E   AssertionError: assert 'shown-wrong' is None
E    +  where 'shown-wrong' = <function decision_outcome at 0x7f4164e1a200>({'source': 'record', 'key': 'rr1:x', 'outcome': 'shown-wrong', 'id': 'f-1', ...})
E    +    where <function decision_outcome at 0x7f4164e1a200> = RM.decision_outcome
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py::test_e1_a_repeat_whose_grade_rests_on_a_ruling_is_no_code_refutation_and_proves_no_fix
FAILED plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py::test_e2_an_earlier_shown_wrong_that_rests_on_a_ruling_reads_open_so_its_repeat_is_judged_fresh
FAILED plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py::test_e3_a_record_finding_shown_wrong_on_a_ruling_pools_with_its_grade_and_reads_open
3 failed in 0.38s
```

**Restore:** inverse edits at both sites, back to `    if finding_outcomes.rests_on_ruling(grade):` and
`    if outcome == SHOWN_WRONG and finding_outcomes.rests_on_ruling(`.
**Restore receipt:** both restored lines quoted above; the `git diff -U0` hunks of `round_driver.py` (`_grade_verdict`) and `repeat_marks.py` (`decision_outcome`) show them as added.

**Raw green:**

```
...                                                                      [100%]
3 passed in 0.34s
```

---

## E8 — the pooled citation: `session_entry` (`repeat_marks.py`), added by the review's fix of finding v0

Axis: a pooled scope-ruling outcome carries the decision the record writer cites for it in its family snapshot, so a
kept repeat restored from it keeps `decidedBy` for the writer's re-check. Typed by the build session at review-code's
`apply-fixes` step.

**Neutralization:** `    if isinstance(cited, dict) and not isinstance(family.get("decidedBy"), dict):` became
`    if False and isinstance(cited, dict) and not isinstance(family.get("decidedBy"), dict):`.

**Raw red** (the whole new file):

```
..............................................F...                       [100%]
E   KeyError: 'decidedBy'
/home/user/wt-2478/plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py:300: KeyError: 'decidedBy'
FAILED plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py::test_e4_a_pooled_scope_ruling_carries_its_cited_decision_so_a_kept_repeat_restores_it
1 failed, 49 passed in 0.46s
```

**Restore:** the inverse edit, back to `    if isinstance(cited, dict) and not isinstance(family.get("decidedBy"), dict):`.
**Restore receipt:** `git diff --stat` after the restore lists only the intended fix (`repeat_marks.py` 9 +/-,
`review_record_session.py` 7 +/-, the test file +17).

**Raw green:** `50 passed in 0.46s`.

---

## Final state

`git status --porcelain` over the six library files shows them modified (`M`) by the intended change only; the full new test
file then ran green: `49 passed in 0.52s`.

---

# WO-2 additions (order O-2482-V922): E9 to E13

**How these runs were made.** Same method as above: each run is the order's pinned command
`scripts/pinned-python -B -m pytest plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py -q -p no:cacheprovider --tb=line -k "<node selector>"`,
narrowed by `-k` to the tests that guard the element (`--tb=line` shapes the traceback only; nothing is filtered). Each
neutralization is one targeted edit and each restore is the inverse edit (never `git checkout`, `restore`, `reset` or `stash`).
The uv notice line (`warning: The UV_NATIVE_TLS ...`) that opens every capture is omitted; nothing else is cut. No secrets or
private URLs appear. Every capture is far below the 32 KiB ceiling. 20 red/green runs were used, one pair per
neutralization.

**Guarded-element set (declared by the order, none grouped):** E9 the ruling-aware kept verdict (the shared reader
`finding_outcomes.counted_verdict`, then each of its two session-writer call sites separately), E10 the widened wording
(each of the three new pattern alternatives separately), E11 the quoted-reason attribution, E12 whole-key matching, E13 the
fold's key/reason hand-off (the keys, then the reasons, separately). That is 3 + 3 + 1 + 1 + 2 = 10 neutralizations, 10 reds.

---

## E9a — the shared reader: `finding_outcomes.counted_verdict` (`finding_outcomes.py`)

Axis: a wrong grade resting on a scope ruling counts as no verdict at every repeat reader (`_grade_verdict` and both session
writer sites go through it).

**Neutralization:** `    if rests_on_ruling(grade):` became `    if False and rests_on_ruling(grade):` in `counted_verdict`.

**Raw red** (`-k "test_e1_ or test_e5 or test_e7"`):

```
FFFFFF                                                                   [100%]
=================================== FAILURES ===================================
E   AssertionError: assert 'wrong' is None
     +  where 'wrong' = <function _grade_verdict at 0x7f762afaa340>({'grade': {'verdict': 'wrong', 'reason': 'the standing ruling on rk:src/foo.py:12:unchecked-index routes this to the follow-up, so it is not raised here', 'restsOnRuling': {'findingKey': 'rk:src/foo.py:12:unchecked-index'}}})
     +    where <function _grade_verdict at 0x7f762afaa340> = RD._grade_verdict
/home/user/wt-2478/plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py:399: AssertionError: assert 'wrong' is None
E   AssertionError: assert {'outcome': '...ict': 'wrong'} == {'outcome': '...erdict': None}
      
      Differing items:
      {'outcome': 'fixed'} != {'outcome': 'left-for-owner'}
      {'verdict': 'wrong'} != {'verdict': None}
      Use -v to get more diff
/home/user/wt-2478/plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py:475: AssertionError: assert {'outcome': '...ict': 'wrong'} == {'outcome': '...erdict': None}
E   AssertionError: assert {'outcome': '...ict': 'wrong'} == {'outcome': '...erdict': None}
      
      Differing items:
      {'outcome': 'fixed'} != {'outcome': 'left-for-owner'}
      {'verdict': 'wrong'} != {'verdict': None}
      Use -v to get more diff
/home/user/wt-2478/plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py:475: AssertionError: assert {'outcome': '...ict': 'wrong'} == {'outcome': '...erdict': None}
E   AssertionError: assert {'outcome': '...ict': 'wrong'} == {'outcome': '...erdict': None}
      
      Differing items:
      {'outcome': 'fixed'} != {'outcome': 'left-for-owner'}
      {'verdict': 'wrong'} != {'verdict': None}
      Use -v to get more diff
/home/user/wt-2478/plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py:475: AssertionError: assert {'outcome': '...ict': 'wrong'} == {'outcome': '...erdict': None}
E   AssertionError: assert {'outcome': '...ict': 'wrong'} == {'outcome': '...erdict': None}
      
      Differing items:
      {'outcome': 'fixed'} != {'outcome': 'left-for-owner'}
      {'verdict': 'wrong'} != {'verdict': None}
      Use -v to get more diff
/home/user/wt-2478/plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py:475: AssertionError: assert {'outcome': '...ict': 'wrong'} == {'outcome': '...erdict': None}
E   AssertionError: assert 'wrong' is None
     +  where 'wrong' = <function counted_verdict at 0x7f762bb79a80>({'verdict': 'wrong', 'reason': 'the standing ruling on rk:src/foo.py:12:unchecked-index routes this to the follow-up, so it is not raised here', 'restsOnRuling': {'findingKey': 'rk:src/foo.py:12:unchecked-index'}})
     +    where <function counted_verdict at 0x7f762bb79a80> = FO.counted_verdict
     +    and   {'verdict': 'wrong', 'reason': 'the standing ruling on rk:src/foo.py:12:unchecked-index routes this to the follow-up, so it is not raised here', 'restsOnRuling': {'findingKey': 'rk:src/foo.py:12:unchecked-index'}} = drop_grade('the standing ruling on rk:src/foo.py:12:unchecked-index routes this to the follow-up, so it is not raised here')
/home/user/wt-2478/plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py:493: AssertionError: assert 'wrong' is None
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py::test_e1_a_repeat_whose_grade_rests_on_a_ruling_is_no_code_refutation_and_proves_no_fix
FAILED plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py::test_e5_a_kept_repeat_whose_wrong_grade_rests_on_a_ruling_is_kept_on_no_verdict_and_never_follows_a_fixed_earlier[marked-grade-round-repeat-mark]
FAILED plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py::test_e5_a_kept_repeat_whose_wrong_grade_rests_on_a_ruling_is_kept_on_no_verdict_and_never_follows_a_fixed_earlier[marked-grade-ledger-grade-fallback]
FAILED plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py::test_e5_a_kept_repeat_whose_wrong_grade_rests_on_a_ruling_is_kept_on_no_verdict_and_never_follows_a_fixed_earlier[old-shape-phrase-round-repeat-mark]
FAILED plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py::test_e5_a_kept_repeat_whose_wrong_grade_rests_on_a_ruling_is_kept_on_no_verdict_and_never_follows_a_fixed_earlier[old-shape-phrase-ledger-grade-fallback]
FAILED plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py::test_e7_counted_verdict_is_the_raw_verdict_unless_a_wrong_grade_rests_on_a_ruling
6 failed, 80 deselected in 9.14s
```

**Restore:** inverse edit, `    if False and rests_on_ruling(grade):` back to `    if rests_on_ruling(grade):`.
**Restore receipt:** a search of `finding_outcomes.py` for `if (False and )?rests_on_ruling\(grade\):` returned only
`92:    if rests_on_ruling(grade):`.

**Raw green** (same `-k`):

```
......                                                                   [100%]
6 passed, 80 deselected in 0.43s
```

---

## E9b — call site 1: `_kept_mark_verdicts` (`review_record_session.py`)

Axis: a kept repeat's round mark is read through the shared reader, so a ruling-resting wrong grade on the mark gives the
kept mark no verdict and the repeat does not follow a fixed earlier finding.

**Neutralization:** `                out[row["findingKey"]] = finding_outcomes.counted_verdict(grade)` became
`                out[row["findingKey"]] = grade.get("verdict") if isinstance(grade, dict) else None` (the pre-WO-2 raw read).

**Raw red** (`-k "test_e5 or test_e6"`; only the two round-repeat-mark params fail, the two fallback params and the healthy
siblings pass, so the other call site is not what this proves):

```
F.F...                                                                   [100%]
=================================== FAILURES ===================================
E   AssertionError: assert {'outcome': '...ict': 'wrong'} == {'outcome': '...erdict': None}
      
      Differing items:
      {'outcome': 'fixed'} != {'outcome': 'left-for-owner'}
      {'verdict': 'wrong'} != {'verdict': None}
      Use -v to get more diff
/home/user/wt-2478/plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py:475: AssertionError: assert {'outcome': '...ict': 'wrong'} == {'outcome': '...erdict': None}
E   AssertionError: assert {'outcome': '...ict': 'wrong'} == {'outcome': '...erdict': None}
      
      Differing items:
      {'outcome': 'fixed'} != {'outcome': 'left-for-owner'}
      {'verdict': 'wrong'} != {'verdict': None}
      Use -v to get more diff
/home/user/wt-2478/plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py:475: AssertionError: assert {'outcome': '...ict': 'wrong'} == {'outcome': '...erdict': None}
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py::test_e5_a_kept_repeat_whose_wrong_grade_rests_on_a_ruling_is_kept_on_no_verdict_and_never_follows_a_fixed_earlier[marked-grade-round-repeat-mark]
FAILED plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py::test_e5_a_kept_repeat_whose_wrong_grade_rests_on_a_ruling_is_kept_on_no_verdict_and_never_follows_a_fixed_earlier[old-shape-phrase-round-repeat-mark]
2 failed, 4 passed, 80 deselected in 0.25s
```

**Restore:** inverse edit back to `                out[row["findingKey"]] = finding_outcomes.counted_verdict(grade)`.
**Restore receipt:** the restored line is the one quoted above; the `git diff -U0` of `review_record_session.py` shows it as the added line
`+                out[row["findingKey"]] = finding_outcomes.counted_verdict(grade)` under its `# axis:` comment.

**Raw green** (same `-k`):

```
......                                                                   [100%]
6 passed, 80 deselected in 0.23s
```

---

## E9c — call site 2: the `_findings_and_merges` fallback (`review_record_session.py`)

Axis: with no round mark, the kept verdict falls back to the held grade read through the shared reader.

**Neutralization:** `                    finding_outcomes.counted_verdict(grade))` became
`                    grade.get("verdict") if isinstance(grade, dict) else None)` (the pre-WO-2 raw read).

**Raw red** (`-k "test_e5 or test_e6"`; only the two ledger-grade-fallback params fail):

```
.F.F..                                                                   [100%]
=================================== FAILURES ===================================
E   AssertionError: assert {'outcome': '...ict': 'wrong'} == {'outcome': '...erdict': None}
      
      Differing items:
      {'verdict': 'wrong'} != {'verdict': None}
      {'outcome': 'fixed'} != {'outcome': 'left-for-owner'}
      Use -v to get more diff
/home/user/wt-2478/plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py:475: AssertionError: assert {'outcome': '...ict': 'wrong'} == {'outcome': '...erdict': None}
E   AssertionError: assert {'outcome': '...ict': 'wrong'} == {'outcome': '...erdict': None}
      
      Differing items:
      {'verdict': 'wrong'} != {'verdict': None}
      {'outcome': 'fixed'} != {'outcome': 'left-for-owner'}
      Use -v to get more diff
/home/user/wt-2478/plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py:475: AssertionError: assert {'outcome': '...ict': 'wrong'} == {'outcome': '...erdict': None}
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py::test_e5_a_kept_repeat_whose_wrong_grade_rests_on_a_ruling_is_kept_on_no_verdict_and_never_follows_a_fixed_earlier[marked-grade-ledger-grade-fallback]
FAILED plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py::test_e5_a_kept_repeat_whose_wrong_grade_rests_on_a_ruling_is_kept_on_no_verdict_and_never_follows_a_fixed_earlier[old-shape-phrase-ledger-grade-fallback]
2 failed, 4 passed, 80 deselected in 0.29s
```

**Restore:** inverse edit back to `                    finding_outcomes.counted_verdict(grade))`.
**Restore receipt:** the restored line is the one quoted above; the `git diff -U0` of `review_record_session.py` shows it as the added line
`+                    finding_outcomes.counted_verdict(grade))`.

**Raw green** (same `-k`):

```
......                                                                   [100%]
6 passed, 80 deselected in 0.29s
```

---

## E10 — the widened wording (`finding_outcomes.py`, `_RULING_PHRASE`), three alternatives

Axis: any `ruling` / `rulings` / `ruled` word, or an accepted / supplied / standing / conservative / owner's / advisor's `rule`,
reads as resting on a ruling with no key; a code-scope refutation that mentions none of them does not (`test_a3_...`, which
passes in every run below, so the widening is no blanket).

### E10a — the `rulings?` alternative

**Neutralization:** `    r"\b(?:rulings?|ruled|scope[\s-]+rows?"` became `    r"\b(?:ruled|scope[\s-]+rows?"`.

**Raw red** (`-k "test_a2 or test_a3"`):

```
FFF...FF..FFFF................                                           [100%]
=================================== FAILURES ===================================
E   AssertionError: assert None == {'findingKey': None}
     +  where None = <function ruling_rest at 0x7febce515940>('the standing ruling covers this')
     +    where <function ruling_rest at 0x7febce515940> = FO.ruling_rest
/home/user/wt-2478/plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py:87: AssertionError: assert None == {'findingKey': None}
E   AssertionError: assert None == {'findingKey': None}
     +  where None = <function ruling_rest at 0x7febce515940>('Standing Rulings cover this')
     +    where <function ruling_rest at 0x7febce515940> = FO.ruling_rest
/home/user/wt-2478/plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py:87: AssertionError: assert None == {'findingKey': None}
E   AssertionError: assert None == {'findingKey': None}
     +  where None = <function ruling_rest at 0x7febce515940>('standing-ruling covers this')
     +    where <function ruling_rest at 0x7febce515940> = FO.ruling_rest
/home/user/wt-2478/plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py:87: AssertionError: assert None == {'findingKey': None}
E   AssertionError: assert None == {'findingKey': None}
     +  where None = <function ruling_rest at 0x7febce515940>('the out of scope ruling applies')
     +    where <function ruling_rest at 0x7febce515940> = FO.ruling_rest
/home/user/wt-2478/plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py:87: AssertionError: assert None == {'findingKey': None}
E   AssertionError: assert None == {'findingKey': None}
     +  where None = <function ruling_rest at 0x7febce515940>('the out-of-scope rulings apply')
     +    where <function ruling_rest at 0x7febce515940> = FO.ruling_rest
/home/user/wt-2478/plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py:87: AssertionError: assert None == {'findingKey': None}
E   AssertionError: assert None == {'findingKey': None}
     +  where None = <function ruling_rest at 0x7febce515940>('an OUT  OF  SCOPE   ruling')
     +    where <function ruling_rest at 0x7febce515940> = FO.ruling_rest
/home/user/wt-2478/plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py:87: AssertionError: assert None == {'findingKey': None}
E   AssertionError: assert None == {'findingKey': None}
     +  where None = <function ruling_rest at 0x7febce515940>('a ruling on tabs')
     +    where <function ruling_rest at 0x7febce515940> = FO.ruling_rest
/home/user/wt-2478/plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py:87: AssertionError: assert None == {'findingKey': None}
E   AssertionError: assert None == {'findingKey': None}
     +  where None = <function ruling_rest at 0x7febce515940>('this follows the accepted ruling')
     +    where <function ruling_rest at 0x7febce515940> = FO.ruling_rest
/home/user/wt-2478/plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py:105: AssertionError: assert None == {'findingKey': None}
E   AssertionError: assert None == {'findingKey': None}
     +  where None = <function ruling_rest at 0x7febce515940>('per the supplied ruling the finding is out')
     +    where <function ruling_rest at 0x7febce515940> = FO.ruling_rest
/home/user/wt-2478/plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py:105: AssertionError: assert None == {'findingKey': None}
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py::test_a2_the_ruling_phrases_rest_on_a_ruling_with_no_key[the standing ruling covers this]
FAILED plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py::test_a2_the_ruling_phrases_rest_on_a_ruling_with_no_key[Standing Rulings cover this]
FAILED plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py::test_a2_the_ruling_phrases_rest_on_a_ruling_with_no_key[standing-ruling covers this]
FAILED plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py::test_a2_the_ruling_phrases_rest_on_a_ruling_with_no_key[the out of scope ruling applies]
FAILED plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py::test_a2_the_ruling_phrases_rest_on_a_ruling_with_no_key[the out-of-scope rulings apply]
FAILED plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py::test_a2_the_ruling_phrases_rest_on_a_ruling_with_no_key[an OUT  OF  SCOPE   ruling]
FAILED plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py::test_a2_the_ruling_phrases_rest_on_a_ruling_with_no_key[a ruling on tabs]
FAILED plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py::test_a2b_the_field_wordings_of_a_ruling_rest_on_a_ruling_with_no_key[accepted-ruling]
FAILED plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py::test_a2b_the_field_wordings_of_a_ruling_rest_on_a_ruling_with_no_key[supplied-ruling]
9 failed, 21 passed, 56 deselected in 0.34s
```

**Restore:** inverse edit back to `    r"\b(?:rulings?|ruled|scope[\s-]+rows?"`.
**Restore receipt:** the restored line is quoted above and appears in the `git diff -U0` of `finding_outcomes.py` as the added line
`+    r"\b(?:rulings?|ruled|scope[\s-]+rows?"`.

**Raw green** (same `-k`):

```
..............................                                           [100%]
30 passed, 56 deselected in 0.33s
```

### E10b — the `ruled` alternative

**Neutralization:** `    r"\b(?:rulings?|ruled|scope[\s-]+rows?"` became `    r"\b(?:rulings?|scope[\s-]+rows?"`.

**Raw red** (`-k "test_a2 or test_a3"`):

```
...FFF.........FF....F........                                           [100%]
=================================== FAILURES ===================================
E   AssertionError: assert None == {'findingKey': None}
     +  where None = <function ruling_rest at 0x7f4e13979940>('this was ruled out of scope')
     +    where <function ruling_rest at 0x7f4e13979940> = FO.ruling_rest
/home/user/wt-2478/plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py:87: AssertionError: assert None == {'findingKey': None}
E   AssertionError: assert None == {'findingKey': None}
     +  where None = <function ruling_rest at 0x7f4e13979940>('the owner ruled it out of scope')
     +    where <function ruling_rest at 0x7f4e13979940> = FO.ruling_rest
/home/user/wt-2478/plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py:87: AssertionError: assert None == {'findingKey': None}
E   AssertionError: assert None == {'findingKey': None}
     +  where None = <function ruling_rest at 0x7f4e13979940>('they ruled this out of scope')
     +    where <function ruling_rest at 0x7f4e13979940> = FO.ruling_rest
/home/user/wt-2478/plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py:87: AssertionError: assert None == {'findingKey': None}
E   assert None == {'findingKey': None}
     +  where None = <function ruling_rest at 0x7f4e13979940>('the finding was ruled "out of scope" by the owner')
     +    where <function ruling_rest at 0x7f4e13979940> = FO.ruling_rest
/home/user/wt-2478/plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py:105: assert None == {'findingKey': None}
E   AssertionError: assert None == {'findingKey': None}
     +  where None = <function ruling_rest at 0x7f4e13979940>('the finding was ruled “out of scope” by the owner')
     +    where <function ruling_rest at 0x7f4e13979940> = FO.ruling_rest
/home/user/wt-2478/plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py:105: AssertionError: assert None == {'findingKey': None}
E   assert None == {'findingKey': None}
     +  where None = <function ruling_rest at 0x7f4e13979940>('it was ruled "not for this change" earlier')
     +    where <function ruling_rest at 0x7f4e13979940> = FO.ruling_rest
/home/user/wt-2478/plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py:105: assert None == {'findingKey': None}
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py::test_a2_the_ruling_phrases_rest_on_a_ruling_with_no_key[this was ruled out of scope]
FAILED plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py::test_a2_the_ruling_phrases_rest_on_a_ruling_with_no_key[the owner ruled it out of scope]
FAILED plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py::test_a2_the_ruling_phrases_rest_on_a_ruling_with_no_key[they ruled this out of scope]
FAILED plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py::test_a2b_the_field_wordings_of_a_ruling_rest_on_a_ruling_with_no_key[ruled-straight-quotes]
FAILED plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py::test_a2b_the_field_wordings_of_a_ruling_rest_on_a_ruling_with_no_key[ruled-curly-quotes]
FAILED plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py::test_a2b_the_field_wordings_of_a_ruling_rest_on_a_ruling_with_no_key[ruled-quoted-other-words]
6 failed, 24 passed, 56 deselected in 0.33s
```

**Restore:** inverse edit back to `    r"\b(?:rulings?|ruled|scope[\s-]+rows?"`.
**Restore receipt:** same restored line as E10a (the file's line 36 reads `    r"\b(?:rulings?|ruled|scope[\s-]+rows?"`).

**Raw green** (same `-k`):

```
..............................                                           [100%]
30 passed, 56 deselected in 0.29s
```

### E10c — the `accepted / supplied / standing / conservative / owner's / advisor's ... rule(s)` alternative

**Neutralization:** the tail `{0,2}\s+rules?)\b",` of line 37 became `{0,2}\s+rules?zz)\b",`.

**Raw red** (`-k "test_a2 or test_a3"`):

```
..............F..FFFF.........                                           [100%]
=================================== FAILURES ===================================
E   AssertionError: assert None == {'findingKey': None}
     +  where None = <function ruling_rest at 0x7f3021d49940>('this follows the accepted conservative rule')
     +    where <function ruling_rest at 0x7f3021d49940> = FO.ruling_rest
/home/user/wt-2478/plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py:105: AssertionError: assert None == {'findingKey': None}
E   AssertionError: assert None == {'findingKey': None}
     +  where None = <function ruling_rest at 0x7f3021d49940>('the standing rule covers it')
     +    where <function ruling_rest at 0x7f3021d49940> = FO.ruling_rest
/home/user/wt-2478/plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py:105: AssertionError: assert None == {'findingKey': None}
E   assert None == {'findingKey': None}
     +  where None = <function ruling_rest at 0x7f3021d49940>("the owner's rule covers it")
     +    where <function ruling_rest at 0x7f3021d49940> = FO.ruling_rest
/home/user/wt-2478/plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py:105: assert None == {'findingKey': None}
E   AssertionError: assert None == {'findingKey': None}
     +  where None = <function ruling_rest at 0x7f3021d49940>('the advisor rules apply')
     +    where <function ruling_rest at 0x7f3021d49940> = FO.ruling_rest
/home/user/wt-2478/plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py:105: AssertionError: assert None == {'findingKey': None}
E   AssertionError: assert None == {'findingKey': None}
     +  where None = <function ruling_rest at 0x7f3021d49940>('the owner’s rule covers it')
     +    where <function ruling_rest at 0x7f3021d49940> = FO.ruling_rest
/home/user/wt-2478/plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py:105: AssertionError: assert None == {'findingKey': None}
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py::test_a2b_the_field_wordings_of_a_ruling_rest_on_a_ruling_with_no_key[accepted-conservative-rule]
FAILED plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py::test_a2b_the_field_wordings_of_a_ruling_rest_on_a_ruling_with_no_key[standing-rule]
FAILED plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py::test_a2b_the_field_wordings_of_a_ruling_rest_on_a_ruling_with_no_key[owners-rule]
FAILED plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py::test_a2b_the_field_wordings_of_a_ruling_rest_on_a_ruling_with_no_key[advisor-rules]
FAILED plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py::test_a2b_the_field_wordings_of_a_ruling_rest_on_a_ruling_with_no_key[owners-rule-curly-apostrophe]
5 failed, 25 passed, 56 deselected in 0.35s
```

**Restore:** inverse edit back to `{0,2}\s+rules?)\b",`.
**Restore receipt:** the restored line 37 is quoted in the `git diff -U0` of `finding_outcomes.py` as
`+    r"|(?:accepted|supplied|standing|conservative|owner(?:['’]s)?|advisor(?:['’]s)?)(?:\s+[\w'’-]+){0,2}\s+rules?)\b",`.

**Raw green** (same `-k`):

```
..............................                                           [100%]
30 passed, 56 deselected in 0.35s
```

---

## E11 — the quoted-reason attribution (`finding_outcomes.py`, `ruling_rest` and `_quoted_ruling_keys`)

Axis: a quoted span (at least 12 characters after whitespace normalisation) of the verifier text that sits in exactly one
live ruling's reason attributes to that ruling's key; in two reasons it names no single key; a short span or one in no reason
attributes nothing.

**Neutralization:** `    named |= _quoted_ruling_keys(text, ruling_reasons)` became
`    named |= set() and _quoted_ruling_keys(text, ruling_reasons)`.

**Raw red** (`-k "test_a7 or test_a8 or test_a9 or test_b4"`):

```
FFFFF........F                                                           [100%]
=================================== FAILURES ===================================
E   assert None == {'findingKey': 'rk:src/foo.py:12:unchecked-index'}
     +  where None = <function ruling_rest at 0x7f196cd7d940>('the verifier saw it is "belongs to the follow-up" and left it', (), {'rk:src/foo.py:12:unchecked-index': 'this belongs to the follow-up, per the owner', 'rk:src/bar.py:3:other': 'an unrelated reason'})
     +    where <function ruling_rest at 0x7f196cd7d940> = FO.ruling_rest
/home/user/wt-2478/plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py:147: assert None == {'findingKey': 'rk:src/foo.py:12:unchecked-index'}
E   AssertionError: assert None == {'findingKey': 'rk:src/foo.py:12:unchecked-index'}
     +  where None = <function ruling_rest at 0x7f196cd7d940>('the verifier saw it is “belongs to the follow-up” and left it', (), {'rk:src/foo.py:12:unchecked-index': 'this belongs to the follow-up, per the owner', 'rk:src/bar.py:3:other': 'an unrelated reason'})
     +    where <function ruling_rest at 0x7f196cd7d940> = FO.ruling_rest
/home/user/wt-2478/plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py:147: AssertionError: assert None == {'findingKey': 'rk:src/foo.py:12:unchecked-index'}
E   AssertionError: assert None == {'findingKey': 'rk:src/foo.py:12:unchecked-index'}
     +  where None = <function ruling_rest at 0x7f196cd7d940>('the verifier saw it is `belongs to the follow-up` and left it', (), {'rk:src/foo.py:12:unchecked-index': 'this belongs to the follow-up, per the owner', 'rk:src/bar.py:3:other': 'an unrelated reason'})
     +    where <function ruling_rest at 0x7f196cd7d940> = FO.ruling_rest
/home/user/wt-2478/plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py:147: AssertionError: assert None == {'findingKey': 'rk:src/foo.py:12:unchecked-index'}
E   assert None == {'findingKey': 'rk:src/foo.py:12:unchecked-index'}
     +  where None = <function ruling_rest at 0x7f196cd7d940>('the verifier saw it is "belongs   to\nthe  follow-up" and left it', (), {'rk:src/foo.py:12:unchecked-index': 'this belongs to the follow-up, per the owner', 'rk:src/bar.py:3:other': 'an unrelated reason'})
     +    where <function ruling_rest at 0x7f196cd7d940> = FO.ruling_rest
/home/user/wt-2478/plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py:147: assert None == {'findingKey': 'rk:src/foo.py:12:unchecked-index'}
E   assert None == {'findingKey': None}
     +  where None = <function ruling_rest at 0x7f196cd7d940>('it is "belongs to the follow-up"', (), {'rk:src/foo.py:12:unchecked-index': 'this belongs to the follow-up', 'rk:src/bar.py:3:other': 'also belongs to the follow-up here'})
     +    where <function ruling_rest at 0x7f196cd7d940> = FO.ruling_rest
/home/user/wt-2478/plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py:155: assert None == {'findingKey': None}
E   KeyError: 'restsOnRuling'
/home/user/wt-2478/plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py:277: KeyError: 'restsOnRuling'
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py::test_a7_a_quoted_span_that_sits_in_exactly_one_rulings_reason_attributes_to_that_ruling[straight-double]
FAILED plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py::test_a7_a_quoted_span_that_sits_in_exactly_one_rulings_reason_attributes_to_that_ruling[curly-double]
FAILED plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py::test_a7_a_quoted_span_that_sits_in_exactly_one_rulings_reason_attributes_to_that_ruling[backtick]
FAILED plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py::test_a7_a_quoted_span_that_sits_in_exactly_one_rulings_reason_attributes_to_that_ruling[whitespace-normalised]
FAILED plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py::test_a8_a_quoted_span_in_two_rulings_reasons_names_no_single_key_and_a_short_or_absent_span_attributes_nothing
FAILED plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py::test_b4_the_fold_marks_a_refuted_that_quotes_the_standing_rulings_reason_and_leaves_a_code_refutation_unmarked
6 failed, 8 passed, 72 deselected in 0.33s
```

**Restore:** inverse edit back to `    named |= _quoted_ruling_keys(text, ruling_reasons)`.
**Restore receipt:** the `git diff -U0` of `finding_outcomes.py` shows the restored line as
`+    named |= _quoted_ruling_keys(text, ruling_reasons)`.

**Raw green** (same `-k`):

```
..............                                                           [100%]
14 passed, 72 deselected in 0.51s
```

---

## E12 — whole-key matching (`finding_outcomes.py`, `_whole_key`)

Axis: a key counts only when the character after it cannot continue a key, so `a.py::t@L1` is not found inside `a.py::t@L12`;
when one key is a prefix of another and both appear whole, both count.

**Neutralization:** in `_whole_key`, `re.escape(key) + r"(?![A-Za-z0-9_@/]|[-.:][A-Za-z0-9_])", text)` became
`re.escape(key) + r"", text)` (a plain substring match).

**Raw red** (`-k "test_a10 or test_a1_"`; `test_a1_` passes, so plain whole-key finds are unchanged):

```
.F                                                                       [100%]
=================================== FAILURES ===================================
E   AssertionError: assert {'findingKey': None} == {'findingKey': 'a.py::t@L12'}
      
      Differing items:
      {'findingKey': None} != {'findingKey': 'a.py::t@L12'}
      Use -v to get more diff
/home/user/wt-2478/plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py:175: AssertionError: assert {'findingKey': None} == {'findingKey': 'a.py::t@L12'}
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py::test_a10_a_key_counts_only_whole_so_a_key_is_not_found_inside_a_longer_key
1 failed, 1 passed, 84 deselected in 0.31s
```

**Restore:** inverse edit back to `re.escape(key) + r"(?![A-Za-z0-9_@/]|[-.:][A-Za-z0-9_])", text)`.
**Restore receipt:** the `git diff -U0` of `finding_outcomes.py` shows the restored line as
`+    return re.search(re.escape(key) + r"(?![A-Za-z0-9_@/]|[-.:][A-Za-z0-9_])", text) is not None`.

**Raw green** (same `-k`):

```
..                                                                       [100%]
2 passed, 84 deselected in 0.32s
```

---

## E13 — the fold's key/reason hand-off (`round_driver.py`, `_fold_verifiers`), two arguments

Axis: `_fold_verifiers` passes `apply_verdicts` the standing rulings' keys and reasons, built from the same
`_standing_rulings_for_orders(state)[0]` rows the orders list, so a REFUTED that names a key, or quotes a reason, with no ruling
wording is still marked.

### E13a — the keys

**Neutralization:** `verification.apply_verdicts(staged, verdicts, [r["findingKey"] for r in standing],` became
`verification.apply_verdicts(staged, verdicts, [],`.

**Raw red** (`-k "test_b3 or test_b4"`; `test_b4`, which needs only the reasons, still passes):

```
F.                                                                       [100%]
=================================== FAILURES ===================================
E   AssertionError: assert {'verdict': '...this finding'} == {'verdict': '...ecked-index'}}
      
      Omitting 2 identical items, use -vv to show
      Right contains 1 more item:
      {'restsOnRuling': {'findingKey': 'rk:src/foo.py:12:unchecked-index'}}
      Use -v to get more diff
/home/user/wt-2478/plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py:265: AssertionError: assert {'verdict': '...this finding'} == {'verdict': '...ecked-index'}}
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py::test_b3_the_fold_marks_a_refuted_that_names_only_the_standing_rulings_key_with_no_phrase
1 failed, 1 passed, 84 deselected in 0.45s
```

**Restore:** inverse edit back to `verification.apply_verdicts(staged, verdicts, [r["findingKey"] for r in standing],`.
**Restore receipt:** the `git diff -U0` of `round_driver.py` shows
`+    applied = verification.apply_verdicts(staged, verdicts, [r["findingKey"] for r in standing],`.

**Raw green** (same `-k`):

```
..                                                                       [100%]
2 passed, 84 deselected in 0.37s
```

### E13b — the reasons

**Neutralization:** the second argument line `{r["findingKey"]: r.get("reason") for r in standing})` became `None)`.

**Raw red** (`-k "test_b3 or test_b4"`; `test_b3`, which needs only the keys, still passes):

```
.F                                                                       [100%]
=================================== FAILURES ===================================
E   KeyError: 'restsOnRuling'
/home/user/wt-2478/plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py:277: KeyError: 'restsOnRuling'
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py::test_b4_the_fold_marks_a_refuted_that_quotes_the_standing_rulings_reason_and_leaves_a_code_refutation_unmarked
1 failed, 1 passed, 84 deselected in 0.35s
```

**Restore:** inverse edit back to `{r["findingKey"]: r.get("reason") for r in standing})`.
**Restore receipt:** the `git diff -U0` of `round_driver.py` shows the added continuation line
`+                                          {r["findingKey"]: r.get("reason") for r in standing})`.

**Raw green** (same `-k`):

```
..                                                                       [100%]
2 passed, 84 deselected in 0.41s
```

---

## WO-2 final state

The whole new test file ran green before the first neutralization (`86 passed in 1.46s`) and again after the last restore
(`86 passed in 1.05s`); the final `git diff -U0` of the four edited library files shows no neutralization left. The two scoped
suites ran green after the restores: the nine-file suite `389 passed` (its first run failed on two test fakes of
`apply_verdicts` that did not take the new keyword, `test_outcome_settle_c7.py::test_t6_...` and
`test_layer2e_staged_ids_1272.py::test_e1_...`; both fakes were given the keyword, as the order allows, and it was re-run), and the
`-k` suite `2392 passed, 4 skipped` (the four skips are `test_round_driver_run_verify_2133.py` lines 617, 635, 657 and 693,
each `claude write sandbox: /proc belongs to another PID namespace ...`, sandbox-only).

---

## E14 — the leading key boundary: `_whole_key` (`finding_outcomes.py`), added by review session 3's fix group fg-63a9c07a50a4

Axis: a ruling key counts only with a boundary on both sides, so the ruling on `a.py::…` is never read inside a code
refutation that cites `src/a.py::…`. Typed by the build session at review-code's `apply-fixes` step; the two tests are the
test role's break-it tests, written byte for byte.

**Neutralization:** the pre-fix code is the neutralized state: `_whole_key` without the leading lookbehind
`(?<![A-Za-z0-9_@/.:-])`.

**Raw red** (the two break-it tests, before the fix):

```
E   AssertionError: assert {'verdict': '...ed index@L3'}} == {'verdict': '...ed index@L3.'}
      Left contains 1 more item:
      {'restsOnRuling': {'findingKey': 'a.py::unchecked index@L3'}}
FAILED plugins/superheroes/lib/tests/test_scope_ruling_left_boundary_breakit_2478.py::test_code_refutation_does_not_inherit_a_suffix_paths_ruling
FAILED plugins/superheroes/lib/tests/test_scope_ruling_key_suffix_review.py::test_code_refutation_at_a_longer_path_does_not_inherit_a_suffix_ruling
2 failed in 0.25s
```

**Restore:** the fix adds the lookbehind; nothing else in `_whole_key` changed.
**Restore receipt:** `git diff` of `finding_outcomes.py` shows only the lookbehind, the docstring and the axis line.

**Raw green:** the two break-it tests plus this record's test file: `88 passed in 0.91s`.

---

## E15 — a quoted span never names a ruling: `ruling_rest` (`finding_outcomes.py`), order O-2482-V925

Axis: a quoted span (12 or more characters) of the verifier text that sits in a ruling's reason marks the text as resting on a
ruling (`{"findingKey": None}`) but never names one; a key named whole names its ruling only when no quoted span attributes to a
different ruling. So a REFUTED that quotes a decided ruling's reason, while meaning an undecided one, reads `left-for-owner` and
never `ruling` citing the decided ruling's `decidedBy`.

**Guarded element (one):** the rule that `quoted` never joins `named` (`len(named) == 1 and not quoted - named`). Detectors:
`test_a7_...`, `test_a8_...`, `test_b4_...` at the unit and fold level, and `test_b5_...` / `test_b6_...` at the seam (the fold's
own keys and reasons, `apply_verdicts`, the ledger row, `_findings_and_merges`). `test_a8b_...` and `test_b7_...` guard the other
half of the rule (a whole key plus a span of the same ruling's reason keeps the key; a whole key plus a span of a different
ruling's reason names none) and are not expected to go red under this neutralization; they pass in the red run below.

**Neutralization:** the old attribution restored: two lines inserted after `quoted = _quoted_ruling_keys(text, ruling_reasons)`:
`    named |= quoted  # NEUTRALIZATION E15` and `    quoted = set()  # NEUTRALIZATION E15`.

**How the runs were made:** the order's pinned command
`scripts/pinned-python -B -m pytest plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py -q -p no:cacheprovider`,
once with the neutralization (its output was cut in the middle by the tool, 2436 characters, so it is not quoted: incomplete),
then again with `--tb=line` added (traceback shape only; nothing filtered), which is the capture below. The uv notice line is
omitted; no secrets or private URLs appear.

**Raw red** (whole new file, `--tb=line`; the `-q` dots line and the failure lines, complete):

```
........................................FFFFF..............FFF.......... [ 80%]
..................                                                       [100%]
=================================== FAILURES ===================================
E   AssertionError: assert {'findingKey'...hecked-index'} == {'findingKey': None}
      Differing items:
      {'findingKey': 'rk:src/foo.py:12:unchecked-index'} != {'findingKey': None}
/home/user/wt-2478/plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py:147: AssertionError
(the same block for the curly-double, backtick and whitespace-normalised params at line 147, and for line 157 and line 293)
E   AssertionError: assert ('ruling' == 'left-for-owner'
      - left-for-owner
      + ruling)
/home/user/wt-2478/plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py:333: AssertionError
E   AssertionError: assert ('ruling' == 'left-for-owner'
      - left-for-owner
      + ruling)
/home/user/wt-2478/plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py:344: AssertionError
=========================== short test summary info ============================
FAILED ...::test_a7_a_quoted_span_that_sits_in_exactly_one_rulings_reason_marks_a_ruling_but_names_none[straight-double]
FAILED ...::test_a7_..._but_names_none[curly-double]
FAILED ...::test_a7_..._but_names_none[backtick]
FAILED ...::test_a7_..._but_names_none[whitespace-normalised]
FAILED ...::test_a8_a_quoted_span_marks_a_ruling_with_no_key_whether_one_or_two_reasons_hold_it_and_a_short_or_absent_span_contributes_nothing
FAILED ...::test_b4_the_fold_marks_a_refuted_that_quotes_the_standing_rulings_reason_with_no_key_and_leaves_a_code_refutation_unmarked
FAILED ...::test_b5_a_refuted_quoting_a_decided_rulings_reason_while_meaning_an_undecided_one_reads_left_for_owner_never_the_decided_ruling
FAILED ...::test_b6_a_refuted_that_quotes_out_of_scope_against_one_decided_ruling_reads_left_for_owner_never_ruling
8 failed, 82 passed in 0.66s
```

(This record abbreviates the repeated blocks and the `FAILED plugins/superheroes/lib/tests/test_scope_ruling_refutation_2478.py::`
path prefix with `...`; the live capture printed each in full.)

**Restore:** inverse edit; both inserted lines removed, leaving `    quoted = _quoted_ruling_keys(text, ruling_reasons)` followed by
`    if len(named) == 1 and not quoted - named:`.
**Restore receipt:** a search of `finding_outcomes.py` for `NEUTRALIZATION` returned no match, and returned lines 71, 72 and 75:
`    quoted = _quoted_ruling_keys(text, ruling_reasons)`, `    if len(named) == 1 and not quoted - named:` and
`    if named or quoted or _RULING_PHRASE.search(text):`.

**Raw green** (same command with `--tb=line`):

```
........................................................................ [ 80%]
..................                                                       [100%]
90 passed in 0.58s
```
