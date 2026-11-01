# C4 WO-2A bite-proof — the round-1 repository sweep

**Provenance:** claude (implementer), work order WO-2A-2. Detector file: `plugins/superheroes/lib/tests/test_c4_sweep.py`.
Worktree `/home/user/sh-2305`, branch `claude/issue-2305-workhorse-rq185r`, base commit `e33fcdb2ff0f6b2547f93e7335ca663f91ca95f6`.
Every run is `timeout 900 scripts/pinned-python -B -X pycache_prefix=/tmp/sh2305-pyc -m pytest "<node id>" -q -x` from the worktree, the
detector unedited, on the single test node named in each entry. Each neutralization is one targeted Edit of the product file, undone by the
inverse Edit; the restore receipt is the restored line quoted back from the file and the green run of the same node. At the end
`git status --porcelain` shows no `if False`-style residue (the final-tree check is in the last section). Captures are far under the
32 KiB / 128 KiB ceilings. Nothing was redacted (no credential-like text appears). Dropped from every capture: nothing — the
`UV_NATIVE_TLS` deprecation warning line is shown once per run and is omitted below; the red runs are shown whole otherwise.

## Guarded elements (declared in WO-2A) and how they are grouped

WO-2A declared g1–g15. Two of them are two distinct guards each, with different detectors and different failure modes, so they are
proven separately (17 entries): **g3a** the `_sweepDone` session mark and **g3b** the per-finding `_swept` membership (each alone is enough
to stop a second sweep in the usual flow, so each is neutralized alone against a test that reaches only that guard); **g4a** the
round-1 condition and **g4b** the returning-session condition. No element is left unproven.

| ID | Guarded element (axis) | File : site | Detector node |
|---|---|---|---|
| g1 | severity check: a confirmed Minor finding is not swept | `round_driver.py` `_sweep_qualifies` | `test_s1_a_minor_finding_is_not_swept_and_synthesis_goes_on_as_before` |
| g2 | verdict check: a PLAUSIBLE Important finding is not swept | `round_driver.py` `_sweep_qualifies` | `test_s1_a_plausible_important_finding_is_not_swept` |
| g3a | once per session: `_sweepDone` | `round_driver.py` `_begin_sweep` | `test_s1_a_finding_with_nothing_qualifying_marks_the_session_swept_so_a_later_pass_does_not_sweep` |
| g3b | once per finding: `_swept` membership | `round_driver.py` `_sweep_qualifies` | `test_s1_a_finding_already_swept_is_not_swept_again_even_when_the_session_is_not_marked_done` |
| g4a | round gate: round 1 only | `round_driver.py` `_begin_sweep` | `test_s1_a_later_round_never_sweeps_and_leaves_the_session_unswept[2]` |
| g4b | round gate: not a returning session | `round_driver.py` `_begin_sweep` | `test_s1_a_returning_session_never_sweeps` |
| g5 | the description's author is outside every maker family at sweep time | `round_driver.py` `_begin_sweep` | `test_s2_an_author_family_that_became_a_maker_family_before_the_sweep_is_not_run` |
| g6 | inside hits go to the verifiers, not the verified list | `round_driver.py` `_fold_sweep` | `test_s5_an_inside_hit_reaches_the_next_verifier_pass_and_once_confirmed_is_verified_beside_its_parent` |
| g7 | an ungraded hit is removed from the survivors | `round_driver.py` `_withhold_ungraded_sweep_hits` | `test_s5_an_inside_hit_with_no_verifier_grade_is_open_and_never_reaches_a_fix` |
| g8 | an outside hit lands under the sweep's own entry | `round_driver.py` `_fold_sweep` | `test_s4_a_hit_on_a_context_line_or_in_an_untouched_file_is_outside_under_the_sweeps_own_entry` |
| g9 | an outside hit's id counts every listed hit | `session_contract.py` `add_sweep_hit` | `test_s4_the_sweeps_outside_ids_follow_every_hit_already_listed_including_a_reviewers` |
| g10 | a hit at the parent's place is covered | `round_driver.py` `_fold_sweep` | `test_s4_a_hit_at_the_parents_own_place_or_one_of_its_places_is_covered_not_found_again` |
| g11 | a PR-body citation is dropped | `round_driver.py` `_fold_sweep` | `test_s4_malformed_hits_and_a_pr_body_citation_are_dropped_and_counted` |
| g12 | a missing seat is recorded under `missing` | `round_driver.py` `_fold_sweep` | `test_s4_a_missing_searcher_seat_folds_with_a_gap_and_is_recorded_and_disclosed` |
| g13 | the carry is restaged | `round_driver.py` `_fold_verifiers` | `test_s5_the_census_every_finding_staged_in_round_1_ends_verified_refuted_or_a_recorded_drop` |
| g14 | no searcher cell, no sweep | `round_driver.py` `_begin_sweep` | `test_s2_a_host_with_no_searcher_cell_runs_no_sweep_and_emits_no_order` |
| g15 | a not-run sweep is disclosed | `receipt_disclosures.py` `build_degraded_prose` | `test_s7_a_not_run_sweep_and_an_incomplete_one_are_degradations_never_a_hidden_pass` |

Two neutralizations (g9 `session_contract.py`, g15 `receipt_disclosures.py`) edit a file other than `round_driver.py`; both files are ones WO-2A
declared, and each was restored by the inverse Edit (the final-tree check below shows neither differs from the committed tree).

## g1 — severity check

**neutralization** (`round_driver.py`, `_sweep_qualifies`):
```diff
-    if circuit_breaker.canonical_severity(row.get("severity")) not in SWEEP_SEVERITIES:
+    if False and circuit_breaker.canonical_severity(row.get("severity")) not in SWEEP_SEVERITIES:
         return False
```
**raw red** (`::test_s1_a_minor_finding_is_not_swept_and_synthesis_goes_on_as_before`):
```
F
=================================== FAILURES ===================================
_____ test_s1_a_minor_finding_is_not_swept_and_synthesis_goes_on_as_before _____

world = <test_break_it_loop.World object at 0x7ff9a55b2180>

    def test_s1_a_minor_finding_is_not_swept_and_synthesis_goes_on_as_before(world):
        # axis: only a Critical or Important finding is searched for — see bite-proof record c4_wo2a_sweep
        _panel(world, code_reviewer=[_finding(severity="Minor")])
>       _not_sweeping(_verify(world))

/home/user/sh-2305/plugins/superheroes/lib/tests/test_c4_sweep.py:221: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

state = {'schemaVersion': 5, 'sessionGeneration': 7, 'config': {'leg': 'code', 'panel': False, 'code': True, 'vendors': ['claude', 'codex'], ...}, 'round': 1, ...}
reason = None, reached = True

    def _not_sweeping(state, reason=None, reached=True):
        """The round went past the sweep trigger without a sweep step; `reason` is the one every recorded sweep carries.
        `reached` is False for a round that never reaches the trigger's sweep step (a returning session)."""
>       assert state["step"] != RD.P_SWEEP and "_sweepPending" not in state
E       AssertionError: assert ('dispatch-sweep' != 'dispatch-sweep')
E        +  where 'dispatch-sweep' = RD.P_SWEEP

/home/user/sh-2305/plugins/superheroes/lib/tests/test_c4_sweep.py:168: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c4_sweep.py::test_s1_a_minor_finding_is_not_swept_and_synthesis_goes_on_as_before
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 2.80s
```
**restore:** the inverse Edit. **restore receipt** (grep of the file after): `4870:    if circuit_breaker.canonical_severity(row.get("severity")) not in SWEEP_SEVERITIES:`
**raw green** (same node):
```
.                                                                        [100%]
1 passed in 2.05s
```

## g2 — verdict check

**neutralization** (`round_driver.py`, `_sweep_qualifies`):
```diff
-    if row.get("verdict") != "CONFIRMED":
+    if False and row.get("verdict") != "CONFIRMED":
         return False
```
**raw red** (`::test_s1_a_plausible_important_finding_is_not_swept`):
```
F
=================================== FAILURES ===================================
______________ test_s1_a_plausible_important_finding_is_not_swept ______________

world = <test_break_it_loop.World object at 0x7f488235a180>

    def test_s1_a_plausible_important_finding_is_not_swept(world):
        # axis: only a CONFIRMED finding is searched for — see bite-proof record c4_wo2a_sweep
        _panel(world, code_reviewer=[_finding()])
>       _not_sweeping(_verify(world, {"Retry without a cap": PLAUSIBLE}))

/home/user/sh-2305/plugins/superheroes/lib/tests/test_c4_sweep.py:238: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

state = {'schemaVersion': 5, 'sessionGeneration': 7, 'config': {'leg': 'code', 'panel': False, 'code': True, 'vendors': ['claude', 'codex'], ...}, 'round': 1, ...}
reason = None, reached = True

    def _not_sweeping(state, reason=None, reached=True):
        """The round went past the sweep trigger without a sweep step; `reason` is the one every recorded sweep carries.
        `reached` is False for a round that never reaches the trigger's sweep step (a returning session)."""
>       assert state["step"] != RD.P_SWEEP and "_sweepPending" not in state
E       AssertionError: assert ('dispatch-sweep' != 'dispatch-sweep')
E        +  where 'dispatch-sweep' = RD.P_SWEEP

/home/user/sh-2305/plugins/superheroes/lib/tests/test_c4_sweep.py:168: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c4_sweep.py::test_s1_a_plausible_important_finding_is_not_swept
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 3.03s
```
**restore:** the inverse Edit (`if row.get("verdict") != "CONFIRMED":` quoted back from the file). **raw green** (same node):
```
.                                                                        [100%]
1 passed in 1.97s
```

## g3a — once per session (`_sweepDone`)

**neutralization** (`round_driver.py`, `_begin_sweep`):
```diff
-    if state.get("_sweepDone"):
+    if False and state.get("_sweepDone"):
         return False
```
**raw red** (`::test_s1_a_finding_with_nothing_qualifying_marks_the_session_swept_so_a_later_pass_does_not_sweep`):
```
F
=================================== FAILURES ===================================
_ test_s1_a_finding_with_nothing_qualifying_marks_the_session_swept_so_a_later_pass_does_not_sweep _

world = <test_break_it_loop.World object at 0x7f05e6bb2180>

    def test_s1_a_finding_with_nothing_qualifying_marks_the_session_swept_so_a_later_pass_does_not_sweep(world):
        # axis: a session sweeps once; a later pass through this point never sweeps again — see bite-proof record c4_wo2a_sweep
        _panel(world, code_reviewer=[_finding(severity="Minor")])
        state = _verify(world)
        assert state["_sweepDone"] is True
        state["_verified"] = [dict(_finding(), verdict="CONFIRMED", id="v9")]
        assert RD._begin_sweep(state, state["config"], str(world.session)) is False
>       assert "_sweepPending" not in state and not _rows(state)
E       AssertionError: assert ('_sweepPending' not in {'schemaVersion': 5, 'sessionGeneration': 7, 'config': {'leg': 'code', 'panel': False, 'code': True, 'vendors': ['claude', 'codex'], ...}, 'round': 1, ...} and not [{'sweepId': 'S-1', 'findingKey': 'src/a.py::retry without a cap@L2', 'title': 'Retry without a cap', 'file': 'src/a.py', ...}])
E        +  where [{'sweepId': 'S-1', 'findingKey': 'src/a.py::retry without a cap@L2', 'title': 'Retry without a cap', 'file': 'src/a.py', ...}] = _rows({'schemaVersion': 5, 'sessionGeneration': 7, 'config': {'leg': 'code', 'panel': False, 'code': True, 'vendors': ['claude', 'codex'], ...}, 'round': 1, ...})

/home/user/sh-2305/plugins/superheroes/lib/tests/test_c4_sweep.py:287: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c4_sweep.py::test_s1_a_finding_with_nothing_qualifying_marks_the_session_swept_so_a_later_pass_does_not_sweep
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 1.96s
```
**restore:** the inverse Edit (`if state.get("_sweepDone"):` quoted back from the file). **raw green** (same node):
```
.                                                                        [100%]
1 passed in 1.92s
```

## g3b — once per finding (`_swept` membership)

**neutralization** (`round_driver.py`, `_sweep_qualifies`):
```diff
-    return bool(key) and key not in (swept if isinstance(swept, list) else ())
+    return bool(key) and (swept if isinstance(swept, list) else ()) is not None
```
**raw red** (`::test_s1_a_finding_already_swept_is_not_swept_again_even_when_the_session_is_not_marked_done`):
```
F
=================================== FAILURES ===================================
_ test_s1_a_finding_already_swept_is_not_swept_again_even_when_the_session_is_not_marked_done _

world = <test_break_it_loop.World object at 0x7f6d2dae2180>

    def test_s1_a_finding_already_swept_is_not_swept_again_even_when_the_session_is_not_marked_done(world):
        # axis: a session sweeps once; a finding already swept is not searched for again — see bite-proof record c4_wo2a_sweep
        state = _to_sweep(world)
        key = state["_swept"][0]
        for name in RD._SWEEP_PASS_KEYS + ("_sweepDone",):
            state.pop(name, None)
        state["_verified"] = [dict(_finding(), verdict="CONFIRMED", id="v0", findingKey=key)]
        state["step"] = RD.P_VERIFIERS
        assert RD._begin_sweep(state, state["config"], str(world.session)) is False
>       assert state["_swept"] == [key] and state["_sweepSeq"] == 1
E       AssertionError: assert (['src/a.py::r...out a cap@L2'] == ['src/a.py::r...out a cap@L2']
E         
E         Left contains one more item: 'src/a.py::retry without a cap@L2'
E         Use -v to get more diff)

/home/user/sh-2305/plugins/superheroes/lib/tests/test_c4_sweep.py:299: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c4_sweep.py::test_s1_a_finding_already_swept_is_not_swept_again_even_when_the_session_is_not_marked_done
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 2.06s
```
**restore:** the inverse Edit (`key not in (swept if isinstance(swept, list) else ())` quoted back from the file). **raw green** (same node):
```
.                                                                        [100%]
1 passed in 1.96s
```

## g4a — round gate, round 1 only

**neutralization** (`round_driver.py`, `_begin_sweep`):
```diff
-    if state.get("round") != SWEEP_ROUND or (isinstance(rec, dict) and rec.get("roundKind") == RETURNING_KIND):
+    if False or (isinstance(rec, dict) and rec.get("roundKind") == RETURNING_KIND):
```
**raw red** (`::test_s1_a_later_round_never_sweeps_and_leaves_the_session_unswept[2]`):
```
F
=================================== FAILURES ===================================
_____ test_s1_a_later_round_never_sweeps_and_leaves_the_session_unswept[2] _____

world = <test_break_it_loop.World object at 0x7f7121d5a180>, round_no = 2

    @pytest.mark.parametrize("round_no", [2, 3, 4])
    def test_s1_a_later_round_never_sweeps_and_leaves_the_session_unswept(world, round_no):
        # axis: the sweep belongs to round 1 of a session that is not a returning review — see bite-proof record c4_wo2a_sweep
        _panel(world, round_no=round_no, code_reviewer=[_finding()])
        state = _verify(world)
>       assert state["step"] != RD.P_SWEEP and "_sweepDone" not in state and "sweeps" not in state["rounds"][str(round_no)]
E       AssertionError: assert ('dispatch-sweep' != 'dispatch-sweep')
E        +  where 'dispatch-sweep' = RD.P_SWEEP

/home/user/sh-2305/plugins/superheroes/lib/tests/test_c4_sweep.py:266: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c4_sweep.py::test_s1_a_later_round_never_sweeps_and_leaves_the_session_unswept[2]
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 1.92s
```
**restore:** the inverse Edit (`state.get("round") != SWEEP_ROUND or (` quoted back). **raw green** (same node):
```
.                                                                        [100%]
1 passed in 1.89s
```

## g4b — round gate, not a returning session

**neutralization** (`round_driver.py`, `_begin_sweep`):
```diff
-    if state.get("round") != SWEEP_ROUND or (isinstance(rec, dict) and rec.get("roundKind") == RETURNING_KIND):
+    if state.get("round") != SWEEP_ROUND or (False and isinstance(rec, dict) and rec.get("roundKind") == RETURNING_KIND):
```
**raw red** (`::test_s1_a_returning_session_never_sweeps`):
```
F
=================================== FAILURES ===================================
___________________ test_s1_a_returning_session_never_sweeps ___________________

world = <test_break_it_loop.World object at 0x7f618574e180>

    def test_s1_a_returning_session_never_sweeps(world):
        # axis: the sweep belongs to round 1 of a session that is not a returning review — see bite-proof record c4_wo2a_sweep
        _panel(world, code_reviewer=[_finding()])
        RD._record_round(world.state, "roundKind", RD.RETURNING_KIND)
>       _not_sweeping(_verify(world), reached=False)

/home/user/sh-2305/plugins/superheroes/lib/tests/test_c4_sweep.py:258: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

state = {'schemaVersion': 5, 'sessionGeneration': 7, 'config': {'leg': 'code', 'panel': False, 'code': True, 'vendors': ['claude', 'codex'], ...}, 'round': 1, ...}
reason = None, reached = False

    def _not_sweeping(state, reason=None, reached=True):
        """The round went past the sweep trigger without a sweep step; `reason` is the one every recorded sweep carries.
        `reached` is False for a round that never reaches the trigger's sweep step (a returning session)."""
>       assert state["step"] != RD.P_SWEEP and "_sweepPending" not in state
E       AssertionError: assert ('dispatch-sweep' != 'dispatch-sweep')
E        +  where 'dispatch-sweep' = RD.P_SWEEP

/home/user/sh-2305/plugins/superheroes/lib/tests/test_c4_sweep.py:168: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c4_sweep.py::test_s1_a_returning_session_never_sweeps
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 1.95s
```
**restore:** the inverse Edit (`rec.get("roundKind") == RETURNING_KIND):` quoted back). **raw green** (same node):
```
.                                                                        [100%]
1 passed in 1.93s
```

## g5 — author eligibility at sweep time

**neutralization** (`round_driver.py`, `_begin_sweep`):
```diff
-        elif author.get("family") in makers:
+        elif False and author.get("family") in makers:
```
**raw red** (`::test_s2_an_author_family_that_became_a_maker_family_before_the_sweep_is_not_run`):
```
F
=================================== FAILURES ===================================
_ test_s2_an_author_family_that_became_a_maker_family_before_the_sweep_is_not_run _

world = <test_break_it_loop.World object at 0x7f256bfb2180>

    def test_s2_an_author_family_that_became_a_maker_family_before_the_sweep_is_not_run(world):
        # axis: the description's author must still be outside every maker family when the sweep is due — see bite-proof record c4_wo2a_sweep
        _panel(world, code_reviewer=[_finding()])
        assert world.state["_toVerify"][0]["searchDescription"]["author"]["family"] == "openai"
        world.state["formerFixerFamilies"] = ["openai"]  # codex became a maker after the description was stamped
>       _not_sweeping(_verify(world), "search-description-author-ineligible")

/home/user/sh-2305/plugins/superheroes/lib/tests/test_c4_sweep.py:330: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

state = {'schemaVersion': 5, 'sessionGeneration': 7, 'config': {'leg': 'code', 'panel': False, 'code': True, 'vendors': ['claude', 'codex'], ...}, 'round': 1, ...}
reason = 'search-description-author-ineligible', reached = True

    def _not_sweeping(state, reason=None, reached=True):
        """The round went past the sweep trigger without a sweep step; `reason` is the one every recorded sweep carries.
        `reached` is False for a round that never reaches the trigger's sweep step (a returning session)."""
>       assert state["step"] != RD.P_SWEEP and "_sweepPending" not in state
E       AssertionError: assert ('dispatch-sweep' != 'dispatch-sweep')
E        +  where 'dispatch-sweep' = RD.P_SWEEP

/home/user/sh-2305/plugins/superheroes/lib/tests/test_c4_sweep.py:168: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c4_sweep.py::test_s2_an_author_family_that_became_a_maker_family_before_the_sweep_is_not_run
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 2.01s
```
**restore:** the inverse Edit (`elif author.get("family") in makers:` quoted back). **raw green** (same node):
```
.                                                                        [100%]
1 passed in 1.82s
```

## g6 — inside hits go to the verifiers

**neutralization** (`round_driver.py`, `_fold_sweep`): inside hits are put straight on the verified list.
```diff
-        _stage_findings(state, staged)
+        state["_verified"] = staged
         state["_sweepHitKeys"] = hit_keys
```
**raw red** (`::test_s5_an_inside_hit_reaches_the_next_verifier_pass_and_once_confirmed_is_verified_beside_its_parent`):
```
F
=================================== FAILURES ===================================
_ test_s5_an_inside_hit_reaches_the_next_verifier_pass_and_once_confirmed_is_verified_beside_its_parent _

world = <test_break_it_loop.World object at 0x7f73f21d6fc0>
routed = [(['Retry without a cap'], [])]

    def test_s5_an_inside_hit_reaches_the_next_verifier_pass_and_once_confirmed_is_verified_beside_its_parent(world, routed):
        # axis: an inside hit goes to the verifiers, never straight to the verified list — see bite-proof record c4_wo2a_sweep
        _to_sweep(world)
        state = _sweep(world, _both(_hit(19, what="second site")))
>       assert state["_verified"] == [] and [f["title"] for f in state["_toVerify"]] == ["second site"]
E       AssertionError: assert ([{'title': 's...ortant', ...}] == []
E         
E         Left contains one more item: {'title': 'second site', 'file': 'src/a.py', 'line': 19, 'severity': 'Important', ...}
E         Use -v to get more diff)

/home/user/sh-2305/plugins/superheroes/lib/tests/test_c4_sweep.py:587: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c4_sweep.py::test_s5_an_inside_hit_reaches_the_next_verifier_pass_and_once_confirmed_is_verified_beside_its_parent
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 1.82s
```
**restore:** the inverse Edit (`_stage_findings(state, staged)` quoted back). **raw green** (same node):
```
.                                                                        [100%]
1 passed in 1.96s
```

## g7 — an ungraded hit is removed from the survivors

**neutralization** (`round_driver.py`, `_withhold_ungraded_sweep_hits`):
```diff
-        if not (_is_sweep_hit(state, survivor) and not isinstance(survivor.get(GRADE_FIELD), dict)):
+        if True or not (_is_sweep_hit(state, survivor) and not isinstance(survivor.get(GRADE_FIELD), dict)):
```
**raw red** (`::test_s5_an_inside_hit_with_no_verifier_grade_is_open_and_never_reaches_a_fix`):
```
F
=================================== FAILURES ===================================
_ test_s5_an_inside_hit_with_no_verifier_grade_is_open_and_never_reaches_a_fix _

world = <test_break_it_loop.World object at 0x7f912efb2180>
routed = [(['Retry without a cap'], []), (['Retry without a cap', 'ungraded site'], [])]

    def test_s5_an_inside_hit_with_no_verifier_grade_is_open_and_never_reaches_a_fix(world, routed):
        # axis: a sweep hit with no verifier grade is removed from the survivors — see bite-proof record c4_wo2a_sweep
        _to_sweep(world)
        _sweep(world, _both(_hit(19, what="ungraded site"), _hit(20)))
        state = _verify(world, silent=("ungraded site",))
>       assert routed[-1] == (["Retry without a cap"], [])
E       AssertionError: assert (['Retry with...ed site'], []) == (['Retry without a cap'], [])
E         
E         At index 0 diff: ['Retry without a cap', 'ungraded site'] != ['Retry without a cap']
E         Use -v to get more diff

/home/user/sh-2305/plugins/superheroes/lib/tests/test_c4_sweep.py:608: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c4_sweep.py::test_s5_an_inside_hit_with_no_verifier_grade_is_open_and_never_reaches_a_fix
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 1.81s
```
**restore:** the inverse Edit (the `if not (_is_sweep_hit(...` line quoted back). **raw green** (same node):
```
.                                                                        [100%]
1 passed in 1.87s
```

## g8 — outside routing to the sweep's own entry

**neutralization** (`round_driver.py`, `_fold_sweep`): the reviewer-entry helper replaces the sweep-entry helper.
```diff
-                session_contract.add_sweep_hit(entries, sweep_id, session_contract.SWEEP_SOURCE_NAME, file, line, title)
+                session_contract.add_outside_hit(entries, session_contract.SWEEP_SOURCE_NAME, file, line, title)
```
**raw red** (`::test_s4_a_hit_on_a_context_line_or_in_an_untouched_file_is_outside_under_the_sweeps_own_entry`):
```
F
=================================== FAILURES ===================================
_ test_s4_a_hit_on_a_context_line_or_in_an_untouched_file_is_outside_under_the_sweeps_own_entry _

world = <test_break_it_loop.World object at 0x7fdc88762180>

    def test_s4_a_hit_on_a_context_line_or_in_an_untouched_file_is_outside_under_the_sweeps_own_entry(world):
        # axis: an outside hit lands under its sweep's own entry, never a reviewer's — see bite-proof record c4_wo2a_sweep
        _to_sweep(world)
        state = _sweep(world, _both(_hit(1, what="retry on a context line"), _hit(4, "README.md", "retry in the readme")))
        (entry,) = state["outsideThisPR"]
>       assert entry["source"] == {"kind": "sweep", "name": "searchers", "sweepId": "S-1"}
E       AssertionError: assert {'kind': 'rev...weepId': None} == {'kind': 'swe...eepId': 'S-1'}
E         
E         Omitting 1 identical items, use -vv to show
E         Differing items:
E         {'sweepId': None} != {'sweepId': 'S-1'}
E         {'kind': 'reviewer'} != {'kind': 'sweep'}
E         Use -v to get more diff

/home/user/sh-2305/plugins/superheroes/lib/tests/test_c4_sweep.py:522: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c4_sweep.py::test_s4_a_hit_on_a_context_line_or_in_an_untouched_file_is_outside_under_the_sweeps_own_entry
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 2.00s
```
**restore:** the inverse Edit (`session_contract.add_sweep_hit(entries, sweep_id, ...` quoted back). **raw green** (same node):
```
.                                                                        [100%]
1 passed in 1.73s
```

## g9 — an outside hit's id counts every hit on every entry

**neutralization** (`session_contract.py`, `add_sweep_hit`; a file WO-2A declared, edited only for this run and restored): number from the hits of the sweep's own entry only.
```diff
-        total += len(hits)
         src = entry.get("source") if isinstance(entry.get("source"), dict) else {}
+        if src.get("kind") == "sweep" and src.get("sweepId") == sweep_id:
+            total += len(hits)
         if src.get("kind") == "sweep" and src.get("sweepId") == sweep_id and target is None:
```
**raw red** (`::test_s4_the_sweeps_outside_ids_follow_every_hit_already_listed_including_a_reviewers`):
```
F
=================================== FAILURES ===================================
_ test_s4_the_sweeps_outside_ids_follow_every_hit_already_listed_including_a_reviewers _

world = <test_break_it_loop.World object at 0x7f3e4351b230>

    def test_s4_the_sweeps_outside_ids_follow_every_hit_already_listed_including_a_reviewers(world):
        # axis: an outside hit's id counts every hit already listed on every entry — see bite-proof record c4_wo2a_sweep
        _to_sweep(world, _finding(kindOfMistake={"kind": KIND, "places": [{"file": "src/a.py", "line": 1}]}))
        reviewer = world.state["outsideThisPR"]
        assert [e["source"]["kind"] for e in reviewer] == ["reviewer"] and len(reviewer[0]["hits"]) == 1
        state = _sweep(world, _both(_hit(20, what="a"), _hit(21, what="b")))
        assert [e["source"]["kind"] for e in state["outsideThisPR"]] == ["reviewer", "sweep"]
>       assert [h["id"] for h in state["outsideThisPR"][1]["hits"]] == ["O-2", "O-3"]
E       AssertionError: assert ['O-1', 'O-2'] == ['O-2', 'O-3']
E         
E         At index 0 diff: 'O-1' != 'O-2'
E         Use -v to get more diff

/home/user/sh-2305/plugins/superheroes/lib/tests/test_c4_sweep.py:539: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c4_sweep.py::test_s4_the_sweeps_outside_ids_follow_every_hit_already_listed_including_a_reviewers
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 1.92s
```
**restore:** the inverse Edit (`        total += len(hits)` back above the `src = ...` line). **raw green** (same node):
```
.                                                                        [100%]
1 passed in 1.83s
```

## g10 — a hit at the parent's own place or one of its places is covered

**neutralization** (`round_driver.py`, `_fold_sweep`):
```diff
-            if (file, line) in places:
+            if False and (file, line) in places:
```
**raw red** (`::test_s4_a_hit_at_the_parents_own_place_or_one_of_its_places_is_covered_not_found_again`):
```
F
=================================== FAILURES ===================================
_ test_s4_a_hit_at_the_parents_own_place_or_one_of_its_places_is_covered_not_found_again _

world = <test_break_it_loop.World object at 0x7f559b3b2180>

    def test_s4_a_hit_at_the_parents_own_place_or_one_of_its_places_is_covered_not_found_again(world):
        # axis: a hit at the parent's own place or one of its places is already known — see bite-proof record c4_wo2a_sweep
        _to_sweep(world, _finding(kindOfMistake={"kind": KIND, "places": [{"file": "src/a.py", "line": 3}]}))
        state = _sweep(world, _both(_hit(2), _hit(3), _hit(2, what="again")))
        (row,) = _rows(state)
>       assert (row["covered"], row["inside"], row["outside"], row["dropped"]) == (2, 0, 0, 0)
E       assert (0, 2, 0, 0) == (2, 0, 0, 0)
E         
E         At index 0 diff: 0 != 2
E         Use -v to get more diff

/home/user/sh-2305/plugins/superheroes/lib/tests/test_c4_sweep.py:513: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c4_sweep.py::test_s4_a_hit_at_the_parents_own_place_or_one_of_its_places_is_covered_not_found_again
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 1.97s
```
**restore:** the inverse Edit (`if (file, line) in places:` quoted back). **raw green** (same node):
```
.                                                                        [100%]
1 passed in 1.98s
```

## g11 — a hit citing the PR body is dropped

**neutralization** (`round_driver.py`, `_fold_sweep`):
```diff
-                    or file == pr_body_stage.CITATION):
+                    or False):
```
**raw red** (`::test_s4_malformed_hits_and_a_pr_body_citation_are_dropped_and_counted`):
```
F
=================================== FAILURES ===================================
____ test_s4_malformed_hits_and_a_pr_body_citation_are_dropped_and_counted _____

world = <test_break_it_loop.World object at 0x7f733775a210>

    def test_s4_malformed_hits_and_a_pr_body_citation_are_dropped_and_counted(world):
        # axis: a hit citing the PR body is dropped and counted, never staged — see bite-proof record c4_wo2a_sweep
        _to_sweep(world)
        bad = [{"file": pr_body_stage.CITATION, "line": 3, "what": "in the PR body"},
               {"file": "", "line": 3}, {"file": "  ", "line": 3}, {"file": None, "line": 3}, {"line": 3},
               {"file": "src/b.py", "line": "3"}, {"file": "src/b.py", "line": True}, {"file": "src/b.py", "line": None},
               {"file": "src/b.py", "line": 2.5}, {"file": 7, "line": 3}]
        state = _sweep(world, _both(*bad))
        (row,) = _rows(state)
>       assert (row["dropped"], row["inside"], row["outside"], row["covered"]) == (10, 0, 0, 0)
E       assert (9, 1, 0, 0) == (10, 0, 0, 0)
E         
E         At index 0 diff: 9 != 10
E         Use -v to get more diff

/home/user/sh-2305/plugins/superheroes/lib/tests/test_c4_sweep.py:489: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c4_sweep.py::test_s4_malformed_hits_and_a_pr_body_citation_are_dropped_and_counted
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 2.03s
```
**restore:** the inverse Edit (`or file == pr_body_stage.CITATION):` quoted back). **raw green** (same node):
```
.                                                                        [100%]
1 passed in 2.04s
```

## g12 — a missing searcher seat is recorded under `missing`

**neutralization** (`round_driver.py`, `_fold_sweep`):
```diff
             if result is None or _adapters().payload_fault(P_SWEEP, result, "") is not None:
-                missing.append(part["part"])
                 continue
```
**raw red** (`::test_s4_a_missing_searcher_seat_folds_with_a_gap_and_is_recorded_and_disclosed`):
```
F
=================================== FAILURES ===================================
_ test_s4_a_missing_searcher_seat_folds_with_a_gap_and_is_recorded_and_disclosed _

world = <test_break_it_loop.World object at 0x7f932114e180>

    def test_s4_a_missing_searcher_seat_folds_with_a_gap_and_is_recorded_and_disclosed(world):
        # axis: a part whose searcher returned no usable result is recorded missing, never as a part that found nothing — see bite-proof record c4_wo2a_sweep
        _to_sweep(world)
        state = _sweep(world, {_seat("S-1", 1): [_hit(19)]})  # part 2 answered nothing
        (row,) = _rows(state)
>       assert row["missing"] == [2] and row["inside"] == 1
E       assert ([] == [2]
E         
E         Right contains one more item: 2
E         Use -v to get more diff)

/home/user/sh-2305/plugins/superheroes/lib/tests/test_c4_sweep.py:459: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c4_sweep.py::test_s4_a_missing_searcher_seat_folds_with_a_gap_and_is_recorded_and_disclosed
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 1.98s
```
**restore:** the inverse Edit (`missing.append(part["part"])` put back above `continue`). **raw green** (same node):
```
.                                                                        [100%]
1 passed in 1.98s
```

## g13 — the carry is restaged with the sweep pass's survivors

**neutralization** (`round_driver.py`, `_fold_verifiers`): the sweep restage reads a carry key that holds nothing, so the carried verified findings are not restaged.
```diff
-        _restage_with_carry(state, "_sweepCarry", "_sweepRefutedCarry", survivors, refuted,
+        _restage_with_carry(state, "_sweepCarryX", "_sweepRefutedCarry", survivors, refuted,
```
**raw red** (`::test_s5_the_census_every_finding_staged_in_round_1_ends_verified_refuted_or_a_recorded_drop`):
```
F
=================================== FAILURES ===================================
_ test_s5_the_census_every_finding_staged_in_round_1_ends_verified_refuted_or_a_recorded_drop _

world = <test_break_it_loop.World object at 0x7f5fb8b4a180>
routed = [(['Plain', 'Held'], ['Gone']), (['site one', 'site six'], ['Gone', 'site two', 'site three'])]

    def test_s5_the_census_every_finding_staged_in_round_1_ends_verified_refuted_or_a_recorded_drop(world, routed):
        # axis: the carry is restaged with the sweep pass's survivors, so no finding staged in round 1 is lost — see bite-proof record c4_wo2a_sweep
        _panel(world, code_reviewer=[_finding("Plain", line=2), _finding("Held", line=3),
                                     _finding("Gone", line=5, file="src/b.py")])
        for staged in world.state["_toVerify"]:
            if staged["title"] == "Held":
                staged["breakItRun"] = {"outcome": "passed"}
        state = _verify(world, {"Held": MISSED_PATH, "Gone": REFUTED})
        if state["step"] == RD.P_SECOND_TEST:
            RD._fold_second_test(state, state["config"], {"findings": []}, session_dir=str(world.session))
        assert state["step"] == RD.P_VERIFIERS and state["_secondTestPass"] is True
        state = _verify(world)  # the second test pass: the held finding is confirmed
        assert state["step"] == RD.P_SWEEP, state["step"]
        assert sorted(r["title"] for r in _rows(state)) == ["Held", "Plain"]
        hits = {_seat("S-1", 1): [_hit(19, what="site one"), _hit(1, "src/b.py", "site two"),
                                  _hit(2, "src/b.py", "site three"), _hit(3, "src/b.py", "site four"),
                                  _hit(1, "README.md", "outside five"), {"file": "", "line": 1}],
                _seat("S-2", 2): [_hit(4, "src/b.py", "site six")]}
        state = _sweep(world, hits)
        state = _verify(world, {"site two": REFUTED, "site three": REFUTED}, silent=("site four",))
        verified, refuted = routed[-1]
>       assert sorted(verified) == ["Held", "Plain", "site one", "site six"]
E       AssertionError: assert ['site one', 'site six'] == ['Held', 'Pla...', 'site six']
E         
E         At index 0 diff: 'site one' != 'Held'
E         Right contains 2 more items, first extra item: 'site one'
E         Use -v to get more diff

/home/user/sh-2305/plugins/superheroes/lib/tests/test_c4_sweep.py:646: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c4_sweep.py::test_s5_the_census_every_finding_staged_in_round_1_ends_verified_refuted_or_a_recorded_drop
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 1.90s
```
**restore:** the inverse Edit (`"_sweepCarry", "_sweepRefutedCarry"` quoted back). **raw green** (same node):
```
.                                                                        [100%]
1 passed in 1.88s
```

## g14 — a host with no searcher cell runs no sweep

**neutralization** (`round_driver.py`, `_begin_sweep`):
```diff
-        elif searcher is None:
+        elif False and searcher is None:
```
**raw red** (`::test_s2_a_host_with_no_searcher_cell_runs_no_sweep_and_emits_no_order`):
```
F
=================================== FAILURES ===================================
____ test_s2_a_host_with_no_searcher_cell_runs_no_sweep_and_emits_no_order _____

world = <test_break_it_loop.World object at 0x7fc7b4b5a180>

    def test_s2_a_host_with_no_searcher_cell_runs_no_sweep_and_emits_no_order(world):
        # axis: a host with no searcher cell runs no sweep and emits no order — see bite-proof record c4_wo2a_sweep
        world.state["config"]["seatMap"]["hostFamily"] = "openai"  # codex's family has no native vendor with a mechanical cell
        _panel(world, code_reviewer=[_finding()])
>       _not_sweeping(_verify(world), "no-searcher-cell")

/home/user/sh-2305/plugins/superheroes/lib/tests/test_c4_sweep.py:346: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

state = {'schemaVersion': 5, 'sessionGeneration': 7, 'config': {'leg': 'code', 'panel': False, 'code': True, 'vendors': ['claude', 'codex'], ...}, 'round': 1, ...}
reason = 'no-searcher-cell', reached = True

    def _not_sweeping(state, reason=None, reached=True):
        """The round went past the sweep trigger without a sweep step; `reason` is the one every recorded sweep carries.
        `reached` is False for a round that never reaches the trigger's sweep step (a returning session)."""
        assert state["step"] != RD.P_SWEEP and "_sweepPending" not in state
        assert state.get("_sweepDone") is (True if reached else None)
        if reason is None:
            assert not _rows(state)
        else:
>           assert [r.get("notRun") for r in _rows(state)] == [reason]
E           AssertionError: assert ['no-file-list'] == ['no-searcher-cell']
E             
E             At index 0 diff: 'no-file-list' != 'no-searcher-cell'
E             Use -v to get more diff

/home/user/sh-2305/plugins/superheroes/lib/tests/test_c4_sweep.py:173: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c4_sweep.py::test_s2_a_host_with_no_searcher_cell_runs_no_sweep_and_emits_no_order
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 1.99s
```
**restore:** the inverse Edit (`elif searcher is None:` quoted back). **raw green** (same node):
```
.                                                                        [100%]
1 passed in 1.95s
```

## g15 — the not-run line is disclosed on the receipt

**neutralization** (`receipt_disclosures.py`, `build_degraded_prose`; a file WO-2A declared, edited only for this run and restored):
```diff
-                if sweep.get("notRun"):
+                if False and sweep.get("notRun"):
```
**raw red** (`::test_s7_a_not_run_sweep_and_an_incomplete_one_are_degradations_never_a_hidden_pass`):
```
F
=================================== FAILURES ===================================
_ test_s7_a_not_run_sweep_and_an_incomplete_one_are_degradations_never_a_hidden_pass _

world = <test_break_it_loop.World object at 0x7f15b43b2180>

    def test_s7_a_not_run_sweep_and_an_incomplete_one_are_degradations_never_a_hidden_pass(world):
        # axis: a sweep that did not run is disclosed — see bite-proof record c4_wo2a_sweep
        _panel(world, code_reviewer=[_finding(searchDescription=None)])
        state = _verify(world)
        lines = RD.build_receipt(state)["degraded"]
>       assert ('sweep-not-run (round 1): S-1 for "Retry without a cap" — no-search-description; '
                "no search ran and nothing stood in") in lines
E       assert 'sweep-not-run (round 1): S-1 for "Retry without a cap" — no-search-description; no search ran and nothing stood in' in ['reviewer-fell-open-seatmap-unavailable (round 1): live panel vendor(s) claude, codex but no seat map submitted — fal...bmitted and is readable, but its violation basis is incomplete (no-seats) — "no breach" is unproven rather than clean']

/home/user/sh-2305/plugins/superheroes/lib/tests/test_c4_sweep.py:736: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c4_sweep.py::test_s7_a_not_run_sweep_and_an_incomplete_one_are_degradations_never_a_hidden_pass
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 2.06s
```
(The `…` inside the list in the last assertion line is pytest's own truncation of the receipt's `degraded` list, as printed.)
**restore:** the inverse Edit (`if sweep.get("notRun"):` quoted back). **raw green** (same node):
```
.                                                                        [100%]
1 passed in 2.15s
```

## Final tree after every restore

Full detector run, every element restored (`timeout 900 scripts/pinned-python -B -X pycache_prefix=/tmp/sh2305-pyc -m pytest plugins/superheroes/lib/tests/test_c4_sweep.py -q`):
```
......................................................................   [100%]
70 passed in 12.52s
```
`git diff --stat` at that point (product files): only `round_driver.py` (the 3-line rename of the new helper `_sweep_record(records, sweep_id)` to `_sweep_row`, which is
not a neutralization), `rubric/orders/dispatch-sweep.md` and its golden fixture (the hit-object shape added to the template) differ from the committed tree;
`session_contract.py` and `receipt_disclosures.py` do not differ, and a repository grep for `if False`, `or False`, `_sweepCarryX` and `True or not` finds none of the
neutralizations in `round_driver.py`, `session_contract.py` or `receipt_disclosures.py`.

## Notes on the redundant-guard pair (g3a / g3b)

In a normal flow `_sweepDone` and the per-finding `_swept` check each stop a second sweep, so neutralizing one alone leaves the other standing. Each is therefore
proven against a test that reaches that guard alone: g3a against a fresh qualifying row whose key is not in `_swept`; g3b against a swept row with `_sweepDone`
cleared. If both are removed, the sweep-hit test `test_s1_a_sweep_hit_the_verifier_confirms_important_never_starts_a_sweep_of_its_own` is the one that would
catch a second sweep; it was not separately neutralized (the pair is proven by its two halves).
