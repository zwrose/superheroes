# C1-L8b repeat marks bite-proof (driver carry, pool reading)

Detectors: `plugins/superheroes/lib/tests/test_repeat_marks_c1l8.py` (the restored FR-22 / edge 7 tests, T-2a, T-2b, T-2c,
T-3a, T-3b) and `plugins/superheroes/lib/tests/test_repeat_marks_module_c1l8a.py` (the S4 pool census). Four guarded
elements, D1 to D4, declared by the order. One neutralization, one red and one green per element, each by a targeted edit
through the edit tool, undone by the inverse edit; no detector was edited during a proof. Every run used this command
shape from the worktree root (node ids per element below):

```
timeout 600 scripts/pinned-python -B -X pycache_prefix=/tmp/shpyc-woe -m pytest <node ids> -q -n 4 -p no:cacheprovider
```

Redaction: none needed; the captures hold no secrets, tokens or private URLs. The `UV_NATIVE_TLS` warning line and the
`bringing up nodes...` lines are kept as printed. The red captures leave out the per-test `[gwN] linux -- Python ...`
interpreter lines, the `tmp_path = PosixPath(...)` lines and the leading part of each test's source listing (each
elided source part is marked `[... source listing elided ...]`; D2's two tests are shown whole); every `E` line, the
`>` failing line, the location lines and the summary lines are verbatim. Each red capture is under 7 KB; the whole
record is well under 128 KiB. The full unabridged captures were written to the session scratchpad
(`/tmp/claude-0/-home-user-wt-2253/fc3d5a4a-b39e-5371-819c-cf1fd020ee3e/scratchpad/d1_red.txt` to `d4_red.txt`) and are
a working artifact only, not a receipt.

Restore receipt shape: `round_driver.py`, `repeat_marks.py` and the test files carry this layer's uncommitted changes, so
`git status --porcelain` reads ` M` before and after every neutralization and cannot show the restore. The receipt is the
restored lines quoted back from the file (by `grep -n` after the inverse edit), plus a green run of the same detector
command.

## D1 — kept repeats leave the survivors and every group before the merge (`_repeat_plan`)

**Guarded element:** `plugins/superheroes/lib/round_driver.py` `_repeat_plan`, the lines under the axis comment at
`round_driver.py:4168` (`removed = ...` and the `survivors` entry). Axis: a kept repeat is out of the survivors and every
group before `merge_and_rank`, so it never merges into a fresh finding.

**Neutralization:** the two lines
```
    removed = kept_ids | {f.get("id") for f in refuted if isinstance(f, dict)}
    return {"marks": marks, "survivors": [s for s in verified if s.get("id") not in kept_ids],
```
became
```
    removed = set()
    return {"marks": marks, "survivors": verified,
```

**Detector command node ids:** `test_repeat_marks_c1l8.py::test_fr22_a_group_of_a_kept_member_and_a_fresh_member_fixes_the_fresh_one_alone`
(both parameters) and `test_repeat_marks_c1l8.py::test_edge7_a_group_whose_members_are_all_kept_leaves_the_merge_and_nothing_is_dropped`.

**Raw red** (3 failed; both named tests go red):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
bringing up nodes...
bringing up nodes...

FFF                                                                      [100%]
=================================== FAILURES ===================================
_ test_fr22_a_group_of_a_kept_member_and_a_fresh_member_fixes_the_fresh_one_alone[Important-Critical] _

    [... source listing elided ...]
        _synth(state, [_group(ids["kept one"], ids["fresh one"])])
        assert [(f["title"], f["severity"]) for f in state["findings"]] == [("fresh one", fresh_severity)]
        assert _batch(state) == ["fresh one"]
>       assert [m["member_ids"] for m in state["rounds"]["2"]["merges"]] == [[ids["fresh one"]]]
E       AssertionError: assert [['v0', 'v1']] == [['v1']]
E         
E         At index 0 diff: ['v0', 'v1'] != ['v1']
E         Use -v to get more diff

plugins/superheroes/lib/tests/test_repeat_marks_c1l8.py:437: AssertionError
_ test_fr22_a_group_of_a_kept_member_and_a_fresh_member_fixes_the_fresh_one_alone[Critical-Important] _

    [... source listing elided ...]
        _synth(state, [_group(ids["kept one"], ids["fresh one"])])
>       assert [(f["title"], f["severity"]) for f in state["findings"]] == [("fresh one", fresh_severity)]
E       AssertionError: assert [('kept one', 'Critical')] == [('fresh one', 'Important')]
E         
E         At index 0 diff: ('kept one', 'Critical') != ('fresh one', 'Important')
E         Use -v to get more diff

plugins/superheroes/lib/tests/test_repeat_marks_c1l8.py:435: AssertionError
_ test_edge7_a_group_whose_members_are_all_kept_leaves_the_merge_and_nothing_is_dropped _

    [... source listing elided ...]
        survivors, grouping = seen[-1]
>       assert sorted(s["id"] for s in survivors) == sorted([ids["fresh c"], ids["fresh d"]])
E       AssertionError: assert ['v0', 'v1', 'v2', 'v3'] == ['v2', 'v3']
E         
E         At index 0 diff: 'v0' != 'v2'
E         Left contains 2 more items, first extra item: 'v2'
E         Use -v to get more diff

plugins/superheroes/lib/tests/test_repeat_marks_c1l8.py:456: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_repeat_marks_c1l8.py::test_fr22_a_group_of_a_kept_member_and_a_fresh_member_fixes_the_fresh_one_alone[Important-Critical]
FAILED plugins/superheroes/lib/tests/test_repeat_marks_c1l8.py::test_fr22_a_group_of_a_kept_member_and_a_fresh_member_fixes_the_fresh_one_alone[Critical-Important]
FAILED plugins/superheroes/lib/tests/test_repeat_marks_c1l8.py::test_edge7_a_group_whose_members_are_all_kept_leaves_the_merge_and_nothing_is_dropped
3 failed in 1.68s
```

**Restore:** inverse edit of the two lines above.

**Restore receipt:** restored lines, `round_driver.py:4168-4170`:

```python
    # axis: a kept repeat is out of the survivors and every group before the merge, so it never merges into a fresh finding — see bite-proof record c1l8_wo_a_repeat_marks
    removed = kept_ids | {f.get("id") for f in refuted if isinstance(f, dict)}
    return {"marks": marks, "survivors": [s for s in verified if s.get("id") not in kept_ids],
```

**Raw green:**

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
bringing up nodes...
bringing up nodes...

...                                                                      [100%]
3 passed in 1.04s
```

## D2 — pass 1's refuted findings reach pass 2 (`_fold_verifiers` second-test carry)

**Guarded element:** `round_driver.py` `_fold_verifiers`, the re-staging at `round_driver.py:3948` (with the carry set in
`_hold_for_second_test`, `state["_secondTestRefutedCarry"]`). Axis: after the verifiers' last pass of a round,
`state["_refuted"]` holds every finding refuted in any pass, and `_verified` plus `_refuted` carry pairwise-unique staged
ids.

**Neutralization:** `restaged = verification.stage_ids(carried + survivors + carried_refuted + refuted)` became
`restaged = verification.stage_ids(carried + survivors + refuted)` (the carried refuted list is dropped from the
re-staging).

**Detector command node ids:** `test_repeat_marks_c1l8.py::test_t2a_a_refuted_same_key_repeat_of_the_first_pass_takes_the_fixed_family_back_after_the_second_pass`
and `test_repeat_marks_c1l8.py::test_t2b_after_the_second_pass_the_round_holds_both_passes_findings_under_pairwise_unique_ids`.

**Raw red** (2 failed):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
bringing up nodes...
bringing up nodes...

FF                                                                       [100%]
=================================== FAILURES ===================================
_ test_t2b_after_the_second_pass_the_round_holds_both_passes_findings_under_pairwise_unique_ids _

    def test_t2b_after_the_second_pass_the_round_holds_both_passes_findings_under_pairwise_unique_ids():
        state = _state()
        repeat, held, plain = _raw("alpha bug", line=1), _raw("held one", line=2), _raw("plain one", line=3)
        _earlier(state, repeat, "fixed")
        _held_round(state, [held, plain, repeat], "held one",
                    {"alpha bug": _REFUTED_V, "plain one": _CONFIRMED_V})
        assert state["_secondTestRefutedCarry"][0]["title"] == "alpha bug"
        _fold_pass(state, {"held one": _CONFIRMED_V})
>       assert [f["title"] for f in state["_refuted"]] == ["alpha bug"]
E       AssertionError: assert [] == ['alpha bug']
E         
E         Right contains one more item: 'alpha bug'
E         Use -v to get more diff

plugins/superheroes/lib/tests/test_repeat_marks_c1l8.py:892: AssertionError
_ test_t2a_a_refuted_same_key_repeat_of_the_first_pass_takes_the_fixed_family_back_after_the_second_pass _

    def test_t2a_a_refuted_same_key_repeat_of_the_first_pass_takes_the_fixed_family_back_after_the_second_pass():
        state = _state()
        repeat, held, plain = _raw("alpha bug", line=1), _raw("held one", line=2), _raw("plain one", line=3)
        receipt = {"headSha": "a" * 40}
        _earlier(state, repeat, "fixed", dispositionReceipt=receipt)
        _held_round(state, [held, plain, repeat], "held one",
                    {"alpha bug": _REFUTED_V, "plain one": _CONFIRMED_V})
        _fold_pass(state, {"held one": _CONFIRMED_V})
        assert state["step"] == RD.P_SYNTHESIS
        _synth(state, None)
        row = _row(state, repeat)
>       assert row["repeatOf"] == {"findingKey": _key(repeat), "id": None, "fixHolds": True}
               ^^^^^^^^^^^^^^^
E       KeyError: 'repeatOf'

plugins/superheroes/lib/tests/test_repeat_marks_c1l8.py:877: KeyError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_repeat_marks_c1l8.py::test_t2b_after_the_second_pass_the_round_holds_both_passes_findings_under_pairwise_unique_ids
FAILED plugins/superheroes/lib/tests/test_repeat_marks_c1l8.py::test_t2a_a_refuted_same_key_repeat_of_the_first_pass_takes_the_fixed_family_back_after_the_second_pass
2 failed in 1.73s
```

**Restore:** inverse edit of the `stage_ids(...)` line.

**Restore receipt:** restored lines, `round_driver.py:3947-3950`:

```python
        # axis: the first pass's survivors and refuted findings and this pass's are staged afresh together, so the round's two lists carry unique ids and its refuted list holds both passes' — see bite-proof record c1l8_wo_a_repeat_marks
        restaged = verification.stage_ids(carried + survivors + carried_refuted + refuted)
        split = len(carried) + len(survivors)
        state["_verified"], state["_refuted"] = restaged[:split], restaged[split:]
```

**Raw green:**

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
bringing up nodes...
bringing up nodes...

..                                                                       [100%]
2 passed in 1.09s
```

## D3 — the `mergedInto` resolution in `session_entry`

**Guarded element:** `plugins/superheroes/lib/repeat_marks.py` `session_entry`, the representative read at
`repeat_marks.py:125`. Axis: a ledger row pools with the outcome the record writer gives it, which reads a merged member
through its representative; an unresolvable chain is not pooled.

**Neutralization:** `rep = row if by_key is None else session_contract.resolve_merged_into_entry(row, by_key)` became
`rep = row` (the row itself is read, not the resolved representative).

**Detector command node ids:** `test_repeat_marks_module_c1l8a.py::test_s4_a_ledger_row_pools_with_the_outcome_the_record_writer_gives_it`
(the census) and `test_repeat_marks_c1l8.py::test_t3a_a_non_representative_member_of_a_fixed_group_raised_again_is_marked_a_repeat_and_kept`.

**Raw red** (2 failed):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
bringing up nodes...
bringing up nodes...

FF                                                                       [100%]
=================================== FAILURES ===================================
____ test_s4_a_ledger_row_pools_with_the_outcome_the_record_writer_gives_it ____

    [... source listing elided ...]
        by_key = {_key(row): row for row in rows.values()}
        pooled = {e["key"]: e for e in RM.build_pool(list(rows.values()), 2, [])}
        expected = {}
        for name, row in rows.items():
            outcome = RS._decide(row, by_key, {})[0]
            expected[name] = outcome
            if outcome is None:
                assert _key(row) not in pooled, name
            else:
>               assert _key(row) in pooled and pooled[_key(row)]["outcome"] == outcome, name
E               AssertionError: member of a fixed group
E               assert ('f.py::fixed member@L1' in {'f.py::fixed rep@L1': {'source': 'session', 'key': 'f.py::fixed rep@L1', 'outcome': 'fixed', 'id': None, ...}, 'f.py:...None, ...}, 'f.py::craft@L1': {'source': 'session', 'key': 'f.py::craft@L1', 'outcome': 'craft', 'id': None, ...}, ...})
E                +  where 'f.py::fixed member@L1' = _key({'severity': 'Important', 'file': 'f.py', 'consequence': 'a reviewer-found defect stays in the change', 'title': 'fixed member', ...})

plugins/superheroes/lib/tests/test_repeat_marks_module_c1l8a.py:267: AssertionError
_ test_t3a_a_non_representative_member_of_a_fixed_group_raised_again_is_marked_a_repeat_and_kept _

    [... source listing elided ...]
        r.drive()
        state = r.state()
        assert seen.get("representative") == "fixed", (seen, r.seen, list(state["rounds"]))  # premise: the group was fixed
        assert r.fixer_runs() == 2 and state["terminal"], r.seen  # the group in round 1, the fresh finding in round 2
        row = _row(state, seen["member"])
>       assert row["repeatOf"]["findingKey"] == _key(seen["member"]), row
               ^^^^^^^^^^^^^^^
E       KeyError: 'repeatOf'

plugins/superheroes/lib/tests/test_repeat_marks_c1l8.py:989: KeyError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_repeat_marks_module_c1l8a.py::test_s4_a_ledger_row_pools_with_the_outcome_the_record_writer_gives_it
FAILED plugins/superheroes/lib/tests/test_repeat_marks_c1l8.py::test_t3a_a_non_representative_member_of_a_fixed_group_raised_again_is_marked_a_repeat_and_kept
2 failed in 3.92s
```

**Restore:** inverse edit of the `rep = row` line.

**Restore receipt:** restored lines, `repeat_marks.py:125-127`:

```python
    rep = row if by_key is None else session_contract.resolve_merged_into_entry(row, by_key)
    if not isinstance(rep, dict):
        return None
```

**Raw green:**

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
bringing up nodes...
bringing up nodes...

..                                                                       [100%]
2 passed in 3.62s
```

## D4 — the `repeatKept` read in `session_entry`

**Guarded element:** `repeat_marks.py` `session_entry`, the outcome read at `repeat_marks.py:129` (with `_kept_outcome`).
Axis: a representative's valid `repeatKept` (a known outcome and a non-empty reason string) gives the pool outcome before
its disposition does, as the record writer reads it; a malformed mark is ignored.

**Neutralization:** `outcome = (_kept_outcome(rep) if by_key is not None else None) or outcome_of(rep.get("disposition"), rep)`
became `outcome = outcome_of(rep.get("disposition"), rep)` (the `repeatKept` branch is skipped).

**Detector command node ids:** `test_repeat_marks_module_c1l8a.py::test_s4_a_ledger_row_pools_with_the_outcome_the_record_writer_gives_it`
(the census) and `test_repeat_marks_c1l8.py::test_t3b_a_judge_named_repeat_kept_as_shown_wrong_is_marked_and_kept_by_exact_identity_when_raised_again`.

**Raw red** (2 failed):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
bringing up nodes...
bringing up nodes...

FF                                                                       [100%]
=================================== FAILURES ===================================
____ test_s4_a_ledger_row_pools_with_the_outcome_the_record_writer_gives_it ____

    [... source listing elided ...]
        by_key = {_key(row): row for row in rows.values()}
        pooled = {e["key"]: e for e in RM.build_pool(list(rows.values()), 2, [])}
        expected = {}
        for name, row in rows.items():
            outcome = RS._decide(row, by_key, {})[0]
            expected[name] = outcome
            if outcome is None:
                assert _key(row) not in pooled, name
            else:
>               assert _key(row) in pooled and pooled[_key(row)]["outcome"] == outcome, name
E               AssertionError: valid repeatKept shown-wrong, confirmed grade
E               assert ('f.py::kept@L1' in {'f.py::fixed rep@L1': {'source': 'session', 'key': 'f.py::fixed rep@L1', 'outcome': 'fixed', 'id': None, ...}, 'f.py:...None, ...}, 'f.py::craft@L1': {'source': 'session', 'key': 'f.py::craft@L1', 'outcome': 'craft', 'id': None, ...}, ...})
E                +  where 'f.py::kept@L1' = _key({'severity': 'Important', 'file': 'f.py', 'consequence': 'a reviewer-found defect stays in the change', 'title': 'kept', ...})

plugins/superheroes/lib/tests/test_repeat_marks_module_c1l8a.py:267: AssertionError
_ test_t3b_a_judge_named_repeat_kept_as_shown_wrong_is_marked_and_kept_by_exact_identity_when_raised_again _

    [... source listing elided ...]
        # premise: round 2 kept it as shown-wrong on the judge's name alone, under its own confirmed grade
        (named,) = state["rounds"]["2"]["repeatMarks"]
        assert (named["source"], named["kept"], named["grade"]["verdict"]) == ("judge", True, "confirmed"), named
        assert named["repeatOf"]["findingKey"] == _key(shown_wrong)
>       assert r.fixer_runs() == 2 and state["terminal"], r.seen  # rounds 1 and 2 fixed; round 3 reached no fix
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AssertionError: ['dispatch-panel', 'dispatch-verifiers', 'dispatch-synthesis', 'dispatch-fixer', 'dispatch-audits', 'run-verify', ...]
E       assert (3 == 2)
E        +  where 3 = fixer_runs()
E        +    where fixer_runs = <test_repeat_marks_c1l8._Rounds object at 0x7ff56e15a0c0>.fixer_runs

plugins/superheroes/lib/tests/test_repeat_marks_c1l8.py:1015: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_repeat_marks_module_c1l8a.py::test_s4_a_ledger_row_pools_with_the_outcome_the_record_writer_gives_it
FAILED plugins/superheroes/lib/tests/test_repeat_marks_c1l8.py::test_t3b_a_judge_named_repeat_kept_as_shown_wrong_is_marked_and_kept_by_exact_identity_when_raised_again
2 failed in 4.60s
```

**Restore:** inverse edit of the `outcome = ...` line.

**Restore receipt:** restored line, `repeat_marks.py:129`:

```python
    outcome = (_kept_outcome(rep) if by_key is not None else None) or outcome_of(rep.get("disposition"), rep)
```

**Raw green:**

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
bringing up nodes...
bringing up nodes...

..                                                                       [100%]
2 passed in 3.60s
```

## Not proven

T-2c (`test_t2c_a_second_pass_with_nothing_left_still_dispatches_synthesis_when_the_first_pass_refuted_against_a_pool`)
guards a fifth element the order did not declare: the no-survivors shortcut in `_fold_verifiers` reading
`state["_refuted"]` rather than pass 2's local list. No neutralization was applied to it, so it is **unproven** here.
