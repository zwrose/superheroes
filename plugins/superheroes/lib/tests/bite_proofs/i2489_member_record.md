# Bite-proof record — a merged member reads fixed only on its own member ruling, the record side (#2489, WO-2)

Detector file: `plugins/superheroes/lib/tests/test_merged_member_record_2489.py`, unedited between each red and its green. Every entry is a targeted, reversible edit to one production file, made and undone with the edit tool (no `git checkout`, `restore`, `reset` or `stash`). Runs: `scripts/pinned-python -B -X pycache_prefix=/tmp/wo2-pyc -m pytest plugins/superheroes/lib/tests/test_merged_member_record_2489.py -q -p no:cacheprovider -k <test name>`; output captured whole; the `UV_NATIVE_TLS` deprecation warning that `uv` prints first is the only line left out of each capture, and the tmp_path directory names are as printed. No secret, token, URL or personal data appears in any capture, so nothing is redacted. Three guarded elements, as the order declared them, none grouped. The restore receipt of each entry is the restored line quoted from a search run on its own after the inverse edit; `git diff --stat` after the last restore lists only the intended production and test files, with no residue.

## 1. E1 — the member gate in `_decide` (`review_record_session.py:774`)

- **Axis:** a merged member (`rep is not own`) whose representative reads fixed has no outcome unless `member_ruled_fixed(rep, its key)`; the gate sits once, after the representative's reading is known, behind all four fixed return sites.
- **Detector:** `test_merged_member_record_2489.py::test_edge3_a_fixed_representative_with_no_member_results_leaves_its_member_without_an_outcome` (`-k test_edge3_a_fixed_representative`).
- **Neutralization:** `    if outcome == _FIXED and rep is not own:` became `    if False and outcome == _FIXED and rep is not own:` (the member returns the representative's outcome unconditionally).

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_edge3_a_fixed_representative_with_no_member_results_leaves_its_member_without_an_outcome _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-5/test_edge3_a_fixed_representat0')

    def test_edge3_a_fixed_representative_with_no_member_results_leaves_its_member_without_an_outcome(tmp_path):
        # axis: the member gate; the representative reads fixed, the member must not inherit it without its own ruling
        rows = ledger()
        via_decide, via_account = both(tmp_path, rows)
>       assert via_decide == (None, rs.MERGED_MEMBER_UNAUDITED)
E       AssertionError: assert ('fixed', 'fi...d in round 2') == (None, 'its r...n part fixed')
E         
E         At index 0 diff: 'fixed' != None
E         Use -v to get more diff

/home/user/wt-2489-wo2/plugins/superheroes/lib/tests/test_merged_member_record_2489.py:103: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_merged_member_record_2489.py::test_edge3_a_fixed_representative_with_no_member_results_leaves_its_member_without_an_outcome
1 failed, 31 deselected in 0.99s
```

**Restore:** the inverse edit (`if False and outcome == _FIXED and rep is not own:` back to `if outcome == _FIXED and rep is not own:`).

**Restore receipt:** search for `outcome == _FIXED and rep is not own` in `review_record_session.py` printed `774:    if outcome == _FIXED and rep is not own:`.

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed, 31 deselected in 1.01s
```

## 2. E2 — `member_ruled_fixed` needs every answer true (`session_contract.py:422`)

- **Axis:** a member answered both ways (one true, one false, in either order) is not ruled fixed; the reader takes all answers for the member, not any.
- **Detector:** `test_merged_member_record_2489.py::test_edge6_a_member_answered_both_ways_is_not_ruled_fixed` (`-k test_edge6`; its three cases `[True, False]`, `[False, True]`, `[True, True, False]` all run and all go red).
- **Neutralization:** `    return bool(answers) and all(a is True for a in answers)` became `    return bool(answers) and any(a is True for a in answers)`.

**Raw red** (exit 1; the three cases print the same failure, the first is quoted whole and the other two keep their header, assertion line and error lines):

```
FFF                                                                      [100%]
=================================== FAILURES ===================================
_____ test_edge6_a_member_answered_both_ways_is_not_ruled_fixed[answers0] ______

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-7/test_edge6_a_member_answered_b0')
answers = [True, False]

    @pytest.mark.parametrize("answers", [[True, False], [False, True], [True, True, False]])
    def test_edge6_a_member_answered_both_ways_is_not_ruled_fixed(tmp_path, answers):
        # axis: every answer for the member must be true; one false answer withdraws the ruling whatever its position
        via_decide, via_account = both(tmp_path, ledger({RESULTS: [said(a) for a in answers]}))
>       assert via_decide == (None, rs.MERGED_MEMBER_UNAUDITED)
E       AssertionError: assert ('fixed', 'fi...n part fixed') == (None, 'its r...n part fixed')
E         
E         At index 0 diff: 'fixed' != None
E         Use -v to get more diff

/home/user/wt-2489-wo2/plugins/superheroes/lib/tests/test_merged_member_record_2489.py:137: AssertionError
_____ test_edge6_a_member_answered_both_ways_is_not_ruled_fixed[answers1] ______
 (answers = [False, True]; same assertion line 137, same error: 'fixed' != None)
_____ test_edge6_a_member_answered_both_ways_is_not_ruled_fixed[answers2] ______
 (answers = [True, True, False]; same assertion line 137, same error: 'fixed' != None)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_merged_member_record_2489.py::test_edge6_a_member_answered_both_ways_is_not_ruled_fixed[answers0]
FAILED plugins/superheroes/lib/tests/test_merged_member_record_2489.py::test_edge6_a_member_answered_both_ways_is_not_ruled_fixed[answers1]
FAILED plugins/superheroes/lib/tests/test_merged_member_record_2489.py::test_edge6_a_member_answered_both_ways_is_not_ruled_fixed[answers2]
3 failed, 29 deselected in 0.54s
```

(Elided: the repeated pytest source echo and traceback of cases 2 and 3, about 25 lines each, identical to case 1 apart from the `answers` value.)

**Restore:** the inverse edit (`any(` back to `all(`).

**Restore receipt:** search for `return bool\(answers\)` in `session_contract.py` printed `422:    return bool(answers) and all(a is True for a in answers)`.

**Raw green** (exit 0):

```
...                                                                      [100%]
3 passed, 29 deselected in 0.43s
```

## 3. E3 — a kept repeat that moves to fixed no longer takes its merged members with it (`review_record.py:1970-1971`, `_follow_repeats`)

- **Axis:** a finding merged into a kept repeat that moves to fixed keeps its own outcome; the ruling branch (members follow a cited ruling) is unchanged.
- **Detector:** `test_merged_member_record_2489.py::test_repeat_follows_fixed_leaves_a_merged_member_at_its_own_outcome_and_the_ruling_branch_still_moves_it` (`-k test_repeat_follows_fixed_leaves`).
- **Neutralization:** after `moved = True` in the `if follows:` branch, the removed member loop was put back (its note a literal, as the constant is gone): `for j in members_to_follow(i, kept):` then `handled.add(j)`, `h, was = out[j], out[j].get("reason")`, `note = "merged into f-2, so it reads fixed with it"` and `out[j] = by_key[_key(h)] = dict(h, outcome=_FIXED, reason=...)`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_repeat_follows_fixed_leaves_a_merged_member_at_its_own_outcome_and_the_ruling_branch_still_moves_it _

    def test_repeat_follows_fixed_leaves_a_merged_member_at_its_own_outcome_and_the_ruling_branch_still_moves_it():
        # axis: a member of a kept repeat that moves to fixed keeps its own outcome; the ruling branch still moves members
        given = repeat(repeatOf=mark_2438(kept={"outcome": LFO, "verdict": "wrong", "members": [MEMBER_RAW_2479]}))
        rec = build_2438([X_FIXED, given, member()])
        rows = by_id(rec)
        assert rows["f-2"]["outcome"] == "fixed" and rows["f-2"]["repeatOf"]["fixHolds"] is True  # the repeat itself follows
>       assert rows["f-3"]["outcome"] == LFO and rows["f-3"]["reason"] == WAS  # the member is untouched
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AssertionError: assert ('fixed' == 'left-for-owner'
E         
E         - left-for-owner
E         + fixed)

/home/user/wt-2489-wo2/plugins/superheroes/lib/tests/test_merged_member_record_2489.py:246: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_merged_member_record_2489.py::test_repeat_follows_fixed_leaves_a_merged_member_at_its_own_outcome_and_the_ruling_branch_still_moves_it
1 failed, 31 deselected in 0.50s
```

**Restore:** the inverse edit (the five added lines removed, the one-line axis comment back after `moved = True`).

**Restore receipt:** search for `merged into the repeat that moved to fixed` in `review_record.py` printed, with two lines of context either side:

```
1969-                    REPEAT_KEPT_FIELD: dict(kept, outcome=_FIXED, verdict=verdict)}))
1970-                moved = True
1971:                # axis: a finding merged into the repeat that moved to fixed keeps its own outcome, since no audit ruled its own part fixed — see bite-proof record i2489_member_record
1972-            else:
1973-                # axis: any other verdict keeps the repeat's own outcome and says so, so its owner card stays — see bite-proof record i2438_repeat_follows
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed, 31 deselected in 0.38s
```

## After the last restore

`git diff --stat` (tracked files; the new test file and this record are untracked):

```
 plugins/superheroes/lib/review_record.py               | 12 +++---------
 plugins/superheroes/lib/review_record_session.py       | 18 ++++++++++++++++++
 plugins/superheroes/lib/session_contract.py            | 17 ++++++++++++++++-
 .../lib/tests/test_repeat_marks_module_c1l8a.py        | 16 ++++++++++++----
 .../test_review_record_repeat_follows_merged_member.py | 13 +++++++------
 .../lib/tests/test_review_record_session.py            |  5 ++++-
 6 files changed, 60 insertions(+), 21 deletions(-)
```
