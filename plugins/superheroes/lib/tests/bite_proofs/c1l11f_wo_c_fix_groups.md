# Bite-proof record c1l11f_wo_c_fix_groups

The detectors this change adds (build #2279, C1-L11f, WO-C): `verification._tie_fix_group`'s test-carrier condition (C-a: a
fix group forms only when a carved-out member carries a break-it test, never for a `carriedTestLost` member alone),
`review_record_session._repaired_alone` (C-b: a member's bullet says it was repaired alone after the group's shared fix,
derived from the ordered per-round fix bindings) and `review_record._fix_group_fault`'s check of the new `repairedAlone`
key. Proven by `plugins/superheroes/lib/tests/test_c1l11f_wo_c_fix_groups.py`.

Guarded elements, declared up front by the order: C-G1 the test-carrier condition on the tie, C-G2 the later-alone-binding
derivation, C-G3 the "binds no other member in that round" condition, C-G4 the validator's check of the new key. One
neutralization and one red each, then one combined green.

Who ran it: the WO-C implementer, from `/home/user/wt-2279-c`. Every neutralization was one targeted edit through the edit
tool, undone by the inverse edit (the restored line is quoted back per element); no `git checkout`, `git restore`, `git
reset` or `git stash` was run. Every run used
`timeout 600 scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-wo-c -m pytest "<node id>" -q -p no:cacheprovider`.
Captures are the runner's whole output for the node, apart from the `UV_NATIVE_TLS` deprecation warning line, which is left
out. Nothing is redacted: no secrets, tokens or URLs appear (the `/tmp/claude-0/...` path is a pytest temp directory).

Red at the unchanged source (before the change), for the record: the six new tests that bite failed (`6 failed, 8
passed`): the C-a `carriedTestLost` + plain test (`assert [{'group_id':...['v0', 'v1']}] == []`), both two-member C-b tests
(`KeyError: 'repairedAlone'` and the symmetric case reading "one fix shared" for the member repaired later), the validator
test (`assert None == '.repairedAlone'`), and the three-member and other-group tests. Disclosure: that first run's synthetic
rows carried no `findingKey`, so the three-member and other-group tests failed there for a test-fixture reason (no binding
matched a row) and not on the axis; the rows were given `findingKey` afterwards, and those two tests' on-axis reds are the
C-G2 and C-G3 reds below.

---

## C-G1 — the tie needs a carved-out member that carries a test (`verification._tie_fix_group`)

- axis: a fix group forms only when a test-carrying member was carved out, never for a `carriedTestLost` one alone.
- neutralization: `if not carried_test or len(tied) + len(rest) < 2:` became `if not tied or len(tied) + len(rest) < 2:`.
- detector: `test_c1l11f_wo_c_fix_groups.py::test_a_carried_test_lost_member_beside_a_plain_one_is_carved_out_but_ties_no_fix_group`.
- red:
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_carried_test_lost_member_beside_a_plain_one_is_carved_out_but_ties_no_fix_group _

    def test_a_carried_test_lost_member_beside_a_plain_one_is_carved_out_but_ties_no_fix_group():
        out = V.merge_and_rank([_lost("v0"), _plain("v1")], [{"member_ids": ["v0", "v1"]}])
>       assert out["fixGroups"] == []
E       AssertionError: assert [{'group_id':...['v0', 'v1']}] == []
E         
E         Left contains one more item: {'group_id': 'g0', 'member_ids': ['v0', 'v1']}
E         Use -v to get more diff

/home/user/wt-2279-c/plugins/superheroes/lib/tests/test_c1l11f_wo_c_fix_groups.py:58: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l11f_wo_c_fix_groups.py::test_a_carried_test_lost_member_beside_a_plain_one_is_carved_out_but_ties_no_fix_group
1 failed in 2.31s
```
- restore: the inverse edit. Restore receipt, the line quoted back (`grep -n` over `verification.py`): `459:    if not carried_test or len(tied) + len(rest) < 2:`.

## C-G2 — the later-alone-binding derivation (`review_record_session._repaired_alone`)

- axis: a member reads repaired alone only when its latest binding follows a round that bound it with another member.
- neutralization: `later = any(s < n for s in shared_rounds)` became `later = False` (every member reads shared).
- detector: `test_c1l11f_wo_c_fix_groups.py::test_a_member_repaired_alone_after_the_shared_fix_reads_so_and_its_sibling_reads_shared`.
- red:
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_member_repaired_alone_after_the_shared_fix_reads_so_and_its_sibling_reads_shared _

grouped = <test_fix_groups_c1l11c.Grouped object at 0x7fe80b1bd400>

    def test_a_member_repaired_alone_after_the_shared_fix_reads_so_and_its_sibling_reads_shared(grouped):
        state, ka, kb = grouped.state, grouped.key_a, grouped.key_b
        shared, repair = _repair(grouped, repaired=kb, discharged=ka)
        listed = {f["title"]: f for f in RS._findings_and_merges(state)[0]}
>       assert listed[B_TITLE]["fixGroup"]["commit"] == repair and listed[B_TITLE]["fixGroup"]["repairedAlone"] is True
                                                                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       KeyError: 'repairedAlone'

/home/user/wt-2279-c/plugins/superheroes/lib/tests/test_c1l11f_wo_c_fix_groups.py:110: KeyError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l11f_wo_c_fix_groups.py::test_a_member_repaired_alone_after_the_shared_fix_reads_so_and_its_sibling_reads_shared
1 failed in 3.21s
```
- restore: the inverse edit; the line is back as `    later = any(s < n for s in shared_rounds)` (the final `git diff` over `review_record_session.py` shows it, and the combined green below ran on it).

## C-G3 — the "binds no other member in that round" condition (`review_record_session._repaired_alone`)

- axis: and only when that latest binding's commit binds no other member of the group in its round.
- neutralization: `return later and commit not in with_others` became `return later` (any later binding counts).
- detector: `test_c1l11f_wo_c_fix_groups.py::test_three_members_two_rebound_together_later_read_shared_and_none_reads_alone`.
- red:
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_three_members_two_rebound_together_later_read_shared_and_none_reads_alone _

    def test_three_members_two_rebound_together_later_read_shared_and_none_reads_alone():
        state = _synthetic({1: [("a", "c1"), ("b", "c1"), ("c", "c1")], 2: [("a", "c2"), ("b", "c2")]}, ["a", "b", "c"])
        bullets = _synthetic_bullets(state)
>       assert all(SHARED in bullets[m] and ALONE not in bullets[m] for m in "abc")
E       assert False
E        +  where False = all(<generator object test_three_members_two_rebound_together_later_read_shared_and_none_reads_alone.<locals>.<genexpr> at 0x7f4c90a15a80>)

/home/user/wt-2279-c/plugins/superheroes/lib/tests/test_c1l11f_wo_c_fix_groups.py:156: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l11f_wo_c_fix_groups.py::test_three_members_two_rebound_together_later_read_shared_and_none_reads_alone
1 failed in 2.23s
```
- restore: the inverse edit; the line is back as `    return later and commit not in with_others`.

## C-G4 — the validator takes `repairedAlone` only as `true` (`review_record._fix_group_fault`)

- axis: `repairedAlone` is present only as the value true.
- neutralization: `return ".repairedAlone" if "repairedAlone" in g and g["repairedAlone"] is not True else None` became `return None`.
  (The first inverse edit was refused by the edit tool because `return None` matched 51 places; the restore was redone with the
  two preceding lines as context, and the file was checked.)
- detector: `test_c1l11f_wo_c_fix_groups.py::test_the_record_takes_repaired_alone_only_as_true_and_the_bullet_reads_it`.
- red:
```
F                                                                        [100%]
=================================== FAILURES ===================================
__ test_the_record_takes_repaired_alone_only_as_true_and_the_bullet_reads_it ___

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-35/test_the_record_takes_repaired0')

    def test_the_record_takes_repaired_alone_only_as_true_and_the_bullet_reads_it(tmp_path):
        group = {"id": "fg-1", "members": ["a", "b"], "commit": "abc1234"}
        assert REC._fix_group_fault(dict(group, repairedAlone=True)) is None
        for bad in (False, "true", 1, None, [], {}):
>           assert REC._fix_group_fault(dict(group, repairedAlone=bad)) == ".repairedAlone", bad
E           AssertionError: False
E           assert None == '.repairedAlone'
E            +  where None = <function _fix_group_fault at 0x7f6b2ea59800>({'id': 'fg-1', 'members': ['a', 'b'], 'commit': 'abc1234', 'repairedAlone': False})
E            +    where <function _fix_group_fault at 0x7f6b2ea59800> = REC._fix_group_fault
E            +    and   {'id': 'fg-1', 'members': ['a', 'b'], 'commit': 'abc1234', 'repairedAlone': False} = dict({'id': 'fg-1', 'members': ['a', 'b'], 'commit': 'abc1234'}, repairedAlone=False)

/home/user/wt-2279-c/plugins/superheroes/lib/tests/test_c1l11f_wo_c_fix_groups.py:200: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l11f_wo_c_fix_groups.py::test_the_record_takes_repaired_alone_only_as_true_and_the_bullet_reads_it
1 failed in 2.00s
```
- restore: the inverse edit; the line is back as `    return ".repairedAlone" if "repairedAlone" in g and g["repairedAlone"] is not True else None`.

## Green

All four restored: the whole of `test_c1l11f_wo_c_fix_groups.py` (14 tests) printed `14 passed in 4.12s`, and the final run over it and `test_fix_groups_c1l11c.py`, `test_break_it_loop.py`, `test_c1l10b_test_restore.py` printed `145 passed in 40.00s`.

Not separately neutralized (unproven here): `_fix_bindings_by_round`'s unreadable-round returns (the four `test_unreadable_rounds_read_shared_never_alone` cases pin them passing, none was run under a neutralization); the key mapping through `review_record._key`; and the bullet's `repairedAlone is True` test (the validator test reads it, no neutralization was run).
