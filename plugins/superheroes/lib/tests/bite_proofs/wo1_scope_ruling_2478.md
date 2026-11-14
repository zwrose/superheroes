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
