# C1-L8b repeat marks bite-proof (driver carry, pool reading)

Detectors: `plugins/superheroes/lib/tests/test_repeat_marks_c1l8.py` (the restored FR-22 / edge 7 tests, T-2a, T-2b, T-2c,
T-3a, T-3b) and `plugins/superheroes/lib/tests/test_repeat_marks_module_c1l8a.py` (the S4 pool census). Guarded
elements D1 to D10, declared by the orders; D3 and D4 are retired (see below), D1, D2 and D5 to D10 are proven. One
neutralization, one red and one green per element, each by a targeted edit through the edit tool, undone by the inverse
edit; no detector was edited during a proof. Every run used this command shape from the worktree root (node ids per
element below; D1 and D2 ran with the `/tmp/shpyc-woe` prefix and a 600 s timeout, D5 to D10 with `/tmp/shpyc-wog` and
a 900 s timeout):

```
timeout 900 scripts/pinned-python -B -X pycache_prefix=/tmp/shpyc-wog -m pytest <node ids> -q -n 4 -p no:cacheprovider
```

Redaction: none needed; the captures hold no secrets, tokens or private URLs. The `UV_NATIVE_TLS` warning line and the
`bringing up nodes...` lines are kept as printed. The red captures leave out the per-test `[gwN] linux -- Python ...`
interpreter lines, the `tmp_path = PosixPath(...)` lines and the leading part of each test's source listing (each
elided source part is marked `[... source listing elided ...]`; D2's two tests are shown whole); every `E` line, the
`>` failing line, the location lines and the summary lines are verbatim. Each red capture is under 8 KB; the whole
record is well under 128 KiB. The full unabridged D5 to D10 captures are under `/tmp/shpyc-wog/` (`d5_red.txt` to
`d10_green.txt`), a working artifact only, not a receipt.

Restore receipt shape: D1 and D2 were proven while `round_driver.py` carried uncommitted changes, so `git status
--porcelain` read ` M` before and after and could not show the restore; their receipt is the restored lines quoted back
from the file (by `grep -n` after the inverse edit), plus a green run of the same detector command. D5 to D10 were
proven on the tree committed at `b4b0afdd`: the receipt is the restored line quoted back by `grep -n`, plus a green run,
and `git status --porcelain` over the neutralized file printed nothing after each restore (a supplementary check).

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

## D3 and D4 — retired with the code they guarded

D3 (the `mergedInto` resolution in `session_entry`) and D4 (the `repeatKept` read through `_kept_outcome`) guarded
lines that no longer exist: `session_entry` no longer resolves the representative or reads `repeatKept` itself. Its
outcome and representative now come from the record writer's own decision (`review_record_session.row_decision`),
which D5 and D6 guard; the S4 census compares each pooled outcome with that same decision. Their entries (neutralization,
red, green) are removed with the code, not carried as proof of the current code.

## D5 — the outcome comes from the record writer's decision (`session_entry`)

**Guarded element:** `plugins/superheroes/lib/repeat_marks.py` `session_entry`, the line under the axis comment at
`repeat_marks.py:115` (`outcome, rep = review_record_session.row_decision(row, inputs)`, line 116). Axis: a ledger row
pools with the outcome the record writer's decision gives it (its disposition, `mergedInto` link, `repeatKept`, ruling
and break-it ruling are all read there), never a reading of its own.

**Neutralization:** `outcome, rep = review_record_session.row_decision(row, inputs)` became
`outcome, rep = row.get("disposition"), row`.

**Detector command node ids:** `test_repeat_marks_module_c1l8a.py::test_b2_an_out_of_scope_row_with_no_attributed_ruling_is_pooled_as_left_for_owner`,
`test_repeat_marks_module_c1l8a.py::test_b2_an_out_of_scope_row_with_an_attributed_ruling_is_pooled_as_a_ruling`,
`test_repeat_marks_module_c1l8a.py::test_b3_a_fixed_row_the_break_it_step_ruled_out_of_scope_is_pooled_as_a_ruling` and
`test_repeat_marks_module_c1l8a.py::test_s4_a_ledger_row_pools_with_the_outcome_the_record_writer_gives_it`.

**Raw red** (4 failed; all four go red; the census test's leading source listing is elided down to its decisive loop,
every `E` line is verbatim):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
bringing up nodes...
bringing up nodes...

FFFF                                                                     [100%]
=================================== FAILURES ===================================
_ test_b2_an_out_of_scope_row_with_no_attributed_ruling_is_pooled_as_left_for_owner _

    def test_b2_an_out_of_scope_row_with_no_attributed_ruling_is_pooled_as_left_for_owner():
        row = _row(_raw("a"), "out-of-scope", outOfScopeReason="not this change's to fix")
>       assert _entry(row)["outcome"] == "left-for-owner"
E       AssertionError: assert 'out-of-scope' == 'left-for-owner'
E         
E         - left-for-owner
E         + out-of-scope

plugins/superheroes/lib/tests/test_repeat_marks_module_c1l8a.py:234: AssertionError
_ test_b3_a_fixed_row_the_break_it_step_ruled_out_of_scope_is_pooled_as_a_ruling _

    def test_b3_a_fixed_row_the_break_it_step_ruled_out_of_scope_is_pooled_as_a_ruling():
        row = _row(_raw("a"), "fixed")
        assert _entry(row)["outcome"] == "fixed"
        held = {"findingKey": _key(row), "outcome": "ruled-out-of-scope", "reason": "not this change's",
                "ruledBy": "the advisor", "ruledAt": "2026-01-02"}
        rounds = {"1": {"breakItKept": [held, {"findingKey": "other", "outcome": "kept"}]}}
>       assert _entry(row, rounds=rounds)["outcome"] == "ruling"
E       AssertionError: assert 'fixed' == 'ruling'
E         
E         - ruling
E         + fixed

plugins/superheroes/lib/tests/test_repeat_marks_module_c1l8a.py:252: AssertionError
_ test_b2_an_out_of_scope_row_with_an_attributed_ruling_is_pooled_as_a_ruling __

    def test_b2_an_out_of_scope_row_with_an_attributed_ruling_is_pooled_as_a_ruling():
        row = _row(_raw("a"), "out-of-scope", outOfScopeReason="not this change's to fix")
        ruled = [{"findingKey": _key(row), "ruling": "out-of-scope", "seq": 3,
                  "provenance": {"ruledBy": "the owner", "ruledAt": "2026-01-02"}}]
>       assert _entry(row, rulingsLog=ruled)["outcome"] == "ruling"
E       AssertionError: assert 'out-of-scope' == 'ruling'
E         
E         - ruling
E         + out-of-scope

plugins/superheroes/lib/tests/test_repeat_marks_module_c1l8a.py:243: AssertionError
____ test_s4_a_ledger_row_pools_with_the_outcome_the_record_writer_gives_it ____

    [... source listing elided ...]
        inputs = RM.read_inputs(state)
        pooled = {e["key"]: e for e in RM.build_pool(state, 2, [])}
        expected = {}
        for name, row in rows.items():
            outcome = RS.row_decision(inputs[0][_key(row)], inputs)[0]
            expected[name] = outcome
            if outcome is None:
                assert _key(row) not in pooled, name
            else:
>               assert _key(row) in pooled and pooled[_key(row)]["outcome"] == outcome, name
E               AssertionError: refuted + wrong grade
E               assert ('f.py::wrong rep@L1' in {'f.py::fixed rep@L1': {'source': 'session', 'key': 'f.py::fixed rep@L1', 'outcome': 'fixed', 'id': None, ...}, 'f.py:....}, 'f.py::ungraded@L1': {'source': 'session', 'key': 'f.py::ungraded@L1', 'outcome': 'refuted', 'id': None, ...}, ...} and 'refuted' == 'shown-wrong'
E                +  where 'f.py::wrong rep@L1' = _key({'severity': 'Important', 'file': 'f.py', 'consequence': 'a reviewer-found defect stays in the change', 'title': 'wrong rep', ...})
E                 
E                 - shown-wrong
E                 + refuted)

plugins/superheroes/lib/tests/test_repeat_marks_module_c1l8a.py:319: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_repeat_marks_module_c1l8a.py::test_b2_an_out_of_scope_row_with_no_attributed_ruling_is_pooled_as_left_for_owner
FAILED plugins/superheroes/lib/tests/test_repeat_marks_module_c1l8a.py::test_b3_a_fixed_row_the_break_it_step_ruled_out_of_scope_is_pooled_as_a_ruling
FAILED plugins/superheroes/lib/tests/test_repeat_marks_module_c1l8a.py::test_b2_an_out_of_scope_row_with_an_attributed_ruling_is_pooled_as_a_ruling
FAILED plugins/superheroes/lib/tests/test_repeat_marks_module_c1l8a.py::test_s4_a_ledger_row_pools_with_the_outcome_the_record_writer_gives_it
4 failed in 1.09s
```

(The elided source listing is the census test's `def` line, its comment, its `rows` table and the `state` construction;
nothing else was left out.)

**Restore:** inverse edit of the `outcome, rep = ...` line.

**Restore receipt:** restored line, `repeat_marks.py:116`:

```python
    outcome, rep = review_record_session.row_decision(row, inputs)
```

`git status --porcelain plugins/superheroes/lib/repeat_marks.py` printed nothing after the restore.

**Raw green** (4 passed):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
bringing up nodes...
bringing up nodes...

....                                                                     [100%]
4 passed in 6.63s
```

## D6 — the merged-into representative reaches the pool (`session_entry`)

**Guarded element:** `repeat_marks.py` `session_entry`, the decided round read from the representative at
`repeat_marks.py:118` (`decided = rep.get("dispositionRound") if isinstance(rep, dict) else None`). Axis: a merged
member pools under its representative's decision and its decided round, though it holds no decision of its own.

**Neutralization:** the first of the two neutralizations the order offered bit, so the `{}` ledger-by-key variant was not
used. `decided = rep.get("dispositionRound") if isinstance(rep, dict) else None` became
`decided = row.get("dispositionRound")` (`row_decision` still gives the outcome, the decided round is read from the
member row itself, which has none).

**Detector command node id:** `test_repeat_marks_c1l8.py::test_b1_a_merged_members_exact_repeat_is_marked_a_repeat_and_keeps_its_representatives_outcome`.

**Raw red** (1 failed):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
bringing up nodes...
bringing up nodes...

F                                                                        [100%]
=================================== FAILURES ===================================
_ test_b1_a_merged_members_exact_repeat_is_marked_a_repeat_and_keeps_its_representatives_outcome _

    def test_b1_a_merged_members_exact_repeat_is_marked_a_repeat_and_keeps_its_representatives_outcome():
        state = _state()
        rep, member = _raw("rep one", line=1), _raw("member one", line=2)
        RD._stage_findings(state, _compile([rep, member]))
        RD._record_merged_into(state, _key(member), _key(rep))
        RD._record_disposition(state, _key(rep), "craft", 1, settledReason="code quality only")
        assert "disposition" not in _row(state, member), "premise: the member holds no decision of its own"
        state["round"] = 2
        _verify(state, [member], {"member one": "CONFIRMED"})
>       assert [(e["title"], e["outcome"]) for e in RD._earlier_pool(state)] == [("rep one", "craft"), ("member one", "craft")]
E       AssertionError: assert [('rep one', 'craft')] == [('rep one', ...ne', 'craft')]
E         
E         Right contains one more item: ('member one', 'craft')
E         Use -v to get more diff

plugins/superheroes/lib/tests/test_repeat_marks_c1l8.py:230: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_repeat_marks_c1l8.py::test_b1_a_merged_members_exact_repeat_is_marked_a_repeat_and_keeps_its_representatives_outcome
1 failed in 1.04s
```

**Restore:** inverse edit of the `decided = ...` line.

**Restore receipt:** restored line, `repeat_marks.py:118`:

```python
    decided = rep.get("dispositionRound") if isinstance(rep, dict) else None
```

`git status --porcelain plugins/superheroes/lib/repeat_marks.py` printed nothing after the restore.

**Raw green** (1 passed):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
bringing up nodes...
bringing up nodes...

.                                                                        [100%]
1 passed in 0.89s
```

## D7 — a record finding's judged head is unknown (`record_entry`)

**Guarded element:** `repeat_marks.py` `record_entry`, `head=None` at `repeat_marks.py:144` (axis comment at line 143),
read through `read_earlier_findings`. Axis: a finding of the earlier review record names no commit it was judged on, so
its entry's `head` is None and `code_changed` reads the change as a change.

**Neutralization:** one edit in `read_earlier_findings`, line 160,
`entries = [e for e in (record_entry(f) for f in findings) if e is not None]` became
`entries = [dict(e, head=(payload.get("finalCommit") or {}).get("sha")) for e in (record_entry(f) for f in findings) if e is not None]`
(the record's final commit becomes each entry's judged head).

**Detector command node id:** `test_repeat_marks_c1l8.py::test_c1_a_record_finding_is_judged_on_an_unknown_head_so_a_confirmed_repeat_is_new_on_unchanged_code`
(both parameters, `CONFIRMED-False` and `REFUTED-True`). Both go red at the test's own `head` assertion (line 422), before
the round is driven; the confirmed case's later behavioural assertions are not reached under this neutralization.

**Raw red** (2 failed):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
bringing up nodes...
bringing up nodes...

FF                                                                       [100%]
=================================== FAILURES ===================================
_ test_c1_a_record_finding_is_judged_on_an_unknown_head_so_a_confirmed_repeat_is_new_on_unchanged_code[CONFIRMED-False] _

repo = namespace(root='/tmp/claude-0/pytest-of-root/pytest-26/popen-gw0/test_c1_a_record_finding_is_ju0/repo', first='77d493d...92014188d9eefd50', changed='275cee43c049b607e7c52e3c99b01279337f2a50', same='e728a33a424332c77fe3af6c821e757ae75cc6a5')
verdict = 'CONFIRMED', kept = False

    @pytest.mark.parametrize("verdict,kept", [("CONFIRMED", False), ("REFUTED", True)])
    def test_c1_a_record_finding_is_judged_on_an_unknown_head_so_a_confirmed_repeat_is_new_on_unchanged_code(
            repo, verdict, kept):
        raw = _raw("beta bug")
        stored = _record_finding(raw, "shown-wrong", id="R-4")
        entries, _ = RM.read_earlier_findings(_record_payload([stored], sha=repo.same))  # the record ended on the head
>       assert [e["head"] for e in entries] == [None]
E       AssertionError: assert ['e728a33a424...757ae75cc6a5'] == [None]
E         
E         At index 0 diff: 'e728a33a424332c77fe3af6c821e757ae75cc6a5' != None
E         Use -v to get more diff

plugins/superheroes/lib/tests/test_repeat_marks_c1l8.py:422: AssertionError
_ test_c1_a_record_finding_is_judged_on_an_unknown_head_so_a_confirmed_repeat_is_new_on_unchanged_code[REFUTED-True] _

repo = namespace(root='/tmp/claude-0/pytest-of-root/pytest-26/popen-gw1/test_c1_a_record_finding_is_ju0/repo', first='77d493d...92014188d9eefd50', changed='275cee43c049b607e7c52e3c99b01279337f2a50', same='e728a33a424332c77fe3af6c821e757ae75cc6a5')
verdict = 'REFUTED', kept = True

    @pytest.mark.parametrize("verdict,kept", [("CONFIRMED", False), ("REFUTED", True)])
    def test_c1_a_record_finding_is_judged_on_an_unknown_head_so_a_confirmed_repeat_is_new_on_unchanged_code(
            repo, verdict, kept):
        raw = _raw("beta bug")
        stored = _record_finding(raw, "shown-wrong", id="R-4")
        entries, _ = RM.read_earlier_findings(_record_payload([stored], sha=repo.same))  # the record ended on the head
>       assert [e["head"] for e in entries] == [None]
E       AssertionError: assert ['e728a33a424...757ae75cc6a5'] == [None]
E         
E         At index 0 diff: 'e728a33a424332c77fe3af6c821e757ae75cc6a5' != None
E         Use -v to get more diff

plugins/superheroes/lib/tests/test_repeat_marks_c1l8.py:422: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_repeat_marks_c1l8.py::test_c1_a_record_finding_is_judged_on_an_unknown_head_so_a_confirmed_repeat_is_new_on_unchanged_code[CONFIRMED-False]
FAILED plugins/superheroes/lib/tests/test_repeat_marks_c1l8.py::test_c1_a_record_finding_is_judged_on_an_unknown_head_so_a_confirmed_repeat_is_new_on_unchanged_code[REFUTED-True]
2 failed in 1.05s
```

**Restore:** inverse edit of the `entries = ...` line.

**Restore receipt:** restored line, `repeat_marks.py:160`:

```python
    entries = [e for e in (record_entry(f) for f in findings) if e is not None]
```

`git status --porcelain plugins/superheroes/lib/repeat_marks.py` printed nothing after the restore.

**Raw green** (2 passed):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
bringing up nodes...
bringing up nodes...

..                                                                       [100%]
2 passed in 0.97s
```

## D8 — the repeat mark is mirrored onto the live finding (`_record_repeat`)

**Guarded element:** `plugins/superheroes/lib/round_driver.py` `_record_repeat`, the live-finding row under the axis
comment at `round_driver.py:4212` (`rows += [live] if live is not None else []`, line 4213). Axis: the mark is on the
live finding too, so the archive that replaces the ledger row with the live copy keeps it.

**Neutralization:** `rows += [live] if live is not None else []` became `rows += []` (the live write is skipped).

**Detector command node id:** `test_repeat_marks_c1l8.py::test_d1_a_confirmed_repeat_of_a_fixed_finding_keeps_its_mark_through_its_fix_and_the_archive`.

**Raw red** (1 failed):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
bringing up nodes...
bringing up nodes...

F                                                                        [100%]
=================================== FAILURES ===================================
_ test_d1_a_confirmed_repeat_of_a_fixed_finding_keeps_its_mark_through_its_fix_and_the_archive _

    def test_d1_a_confirmed_repeat_of_a_fixed_finding_keeps_its_mark_through_its_fix_and_the_archive(tmp_path):
        bug, fresh = _driven("bug one", 1), _driven("fresh one", 2)
        scripted = {2: [fresh], 3: [bug]}  # round 3's scan raises the finding the round-2 audit decided fixed
        r = _Rounds(tmp_path, [bug], lambda rnd, state: scripted.get(rnd, []))
        r.drive()
        state = r.state()
        assert state["terminal"] and r.fixer_runs() == 3, r.seen  # rounds 1, 2 and 3 each fixed; round 4's scan was empty
        (again,) = state["rounds"]["3"]["repeatMarks"]
        assert (again["source"], again["kept"], again["repeatOf"]["fixHolds"]) == ("exact", False, False), again
        # the fix departed the live finding and the archive replaced the ledger row with its copy: the mark survives
        row = _row(state, bug)
>       assert row["repeatOf"]["findingKey"] == _key(bug) and row["repeatOf"]["fixHolds"] is False, row
               ^^^^^^^^^^^^^^^
E       KeyError: 'repeatOf'

plugins/superheroes/lib/tests/test_repeat_marks_c1l8.py:1106: KeyError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_repeat_marks_c1l8.py::test_d1_a_confirmed_repeat_of_a_fixed_finding_keeps_its_mark_through_its_fix_and_the_archive
1 failed in 4.91s
```

**Restore:** inverse edit of the `rows += ...` line.

**Restore receipt:** restored line, `round_driver.py:4213`:

```python
    rows += [live] if live is not None else []
```

`git status --porcelain plugins/superheroes/lib/round_driver.py` printed nothing after the restore.

**Raw green** (1 passed):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
bringing up nodes...
bringing up nodes...

.                                                                        [100%]
1 passed in 4.65s
```

## D9 — a preserved original link takes this round's `fixHolds` (`_apply_repeat_marks`)

**Guarded element:** `round_driver.py` `_apply_repeat_marks`, the preserved link under the axis comment at
`round_driver.py:4256` (line 4257). Axis: a finding matched to itself keeps its original link's target and takes this
round's `fixHolds`, never the old one.

**Neutralization:** `repeat_of = {"findingKey": original["findingKey"], "id": original.get("id"), "fixHolds": mark["fixHolds"]}`
became `repeat_of = dict(original)` (the old link, old `fixHolds` included, is carried over).

**Detector command node id:** `test_repeat_marks_c1l8.py::test_d2_a_preserved_link_takes_this_rounds_fix_holds_and_keeps_its_target`.

**Raw red** (1 failed):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
bringing up nodes...
bringing up nodes...

F                                                                        [100%]
=================================== FAILURES ===================================
__ test_d2_a_preserved_link_takes_this_rounds_fix_holds_and_keeps_its_target ___

    def test_d2_a_preserved_link_takes_this_rounds_fix_holds_and_keeps_its_target():
        state = _state()
        original = _raw("alpha bug", id="F-1")
        _earlier(state, original, "fixed", dispositionReceipt={"headSha": "a" * 40})
        state["round"] = 2
        reworded = _raw("alpha defect, reworded")
        _verify(state, [reworded], {"alpha defect, reworded": "REFUTED"})
        _synth(state, [_group(_ids(state)["alpha defect, reworded"], ref="e1")])
        held = {"findingKey": _key(original), "id": "F-1", "fixHolds": True}
        assert _row(state, reworded)["repeatOf"] == held, "premise: round 2 kept it as a repeat of the fixed finding"
        state["round"] = 3
        _verify(state, [reworded], {"alpha defect, reworded": "CONFIRMED"})
        _synth(state, None)
        (mark,) = state["rounds"]["3"]["repeatMarks"]
        assert mark["source"] == "exact" and mark["kept"] is False
        expected = dict(held, fixHolds=False)  # still the fixed finding's link, with this round's confirmed grade
>       assert mark["repeatOf"] == expected and _row(state, reworded)["repeatOf"] == expected
E       AssertionError: assert ({'findingKey'...xHolds': True} == {'findingKey'...Holds': False}
E         
E         Omitting 2 identical items, use -vv to show
E         Differing items:
E         {'fixHolds': True} != {'fixHolds': False}
E         Use -v to get more diff)

plugins/superheroes/lib/tests/test_repeat_marks_c1l8.py:359: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_repeat_marks_c1l8.py::test_d2_a_preserved_link_takes_this_rounds_fix_holds_and_keeps_its_target
1 failed in 1.06s
```

**Restore:** inverse edit of the `repeat_of = ...` line.

**Restore receipt:** restored line, `round_driver.py:4257`:

```python
            repeat_of = {"findingKey": original["findingKey"], "id": original.get("id"), "fixHolds": mark["fixHolds"]}
```

`git status --porcelain plugins/superheroes/lib/round_driver.py` printed nothing after the restore.

**Raw green** (1 passed):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
bringing up nodes...
bringing up nodes...

.                                                                        [100%]
1 passed in 1.14s
```

## D10 — the no-survivors shortcut reads the round's whole refuted list (`_fold_verifiers`)

**Guarded element:** `round_driver.py` `_fold_verifiers`, the no-survivors shortcut at `round_driver.py:3982`
(`if not state["_verified"] and not (state["_refuted"] and _earlier_pool(state)):`). Axis: a second pass that leaves
nothing still dispatches synthesis when any pass of the round refuted a finding against a non-empty earlier pool, so
the repeat is named; the shortcut reads `state["_refuted"]` (both passes), not the second pass's local list.

**Neutralization:** `not (state["_refuted"] and _earlier_pool(state))` became `not (refuted and _earlier_pool(state))`
(pass 2's local `refuted` list).

**Detector command node id:** `test_repeat_marks_c1l8.py::test_t2c_a_second_pass_with_nothing_left_still_dispatches_synthesis_when_the_first_pass_refuted_against_a_pool`.

**Raw red** (1 failed):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
bringing up nodes...
bringing up nodes...

F                                                                        [100%]
=================================== FAILURES ===================================
_ test_t2c_a_second_pass_with_nothing_left_still_dispatches_synthesis_when_the_first_pass_refuted_against_a_pool _

    def test_t2c_a_second_pass_with_nothing_left_still_dispatches_synthesis_when_the_first_pass_refuted_against_a_pool():
        state = _state()
        _earlier(state, _raw("craft A"), "craft", settledReason="cq")
        _held_round(state, [_raw("held one", line=2), _raw("gone", line=5)], "held one", {"gone": _REFUTED_V})
        state["_toVerify"] = []  # the second pass returns nothing: no survivor, nothing refuted in it
        _fold_pass(state, {})
>       assert state["step"] == RD.P_SYNTHESIS
E       AssertionError: assert 'terminal' == 'dispatch-synthesis'
E         
E         - dispatch-synthesis
E         + terminal

plugins/superheroes/lib/tests/test_repeat_marks_c1l8.py:964: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_repeat_marks_c1l8.py::test_t2c_a_second_pass_with_nothing_left_still_dispatches_synthesis_when_the_first_pass_refuted_against_a_pool
1 failed in 1.15s
```

**Restore:** inverse edit of the `if not state["_verified"] ...` line.

**Restore receipt:** restored line, `round_driver.py:3982`:

```python
    if not state["_verified"] and not (state["_refuted"] and _earlier_pool(state)):
```

`git status --porcelain plugins/superheroes/lib/round_driver.py plugins/superheroes/lib/repeat_marks.py` printed nothing
after the restore.

**Raw green** (1 passed):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
bringing up nodes...
bringing up nodes...

.                                                                        [100%]
1 passed in 1.00s
```
