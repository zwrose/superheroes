# #2288 bite-proof — three returning-review gaps in `round_driver.py`

**Provenance:** implementer WO-1 / `lib/round_driver.py` (`_changed_sections_only`, `_returning_surface`, `_seed_carried`, `_after_audits`, `_with_carried` / `_move_audit_spawned`, `_stamp_fix_groups`), `lib/tests/test_c1_followups_2288.py`, `lib/tests/test_fix_groups_c1l11c.py` (one test edited, per the order).

Declared guarded elements (from the order): E1 to E6. Each was neutralized with one targeted edit through the edit tool and restored with the inverse edit; no `git checkout`, `restore`, `reset` or `stash` was used. Run from `/home/user/wt-2288` under `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest -q -p no:cacheprovider "<node id>"` (one test node per run, no `-n`). The captures are the runner's output for each run with the `UV_NATIVE_TLS` deprecation warning line left out (it is printed first on every run); nothing else is trimmed and nothing is redacted (no secrets, tokens or URLs appear). Each red run exited 1 and each green run exited 0.

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| E1 | `_returning_surface`: `_fix_delta_surface(state, *_changed_sections_only(baseline, head_diff), only=only)` | a file whose section is the same in both diffs never reaches the surface parser, so an unchanged binary cannot force the full panel | `test_c1_followups_2288.py::test_t1a_an_unchanged_binary_beside_a_one_line_change_gets_the_scoped_review_not_the_panel` |
| E2 | `_seed_carried`: `delta_surface.split_fix_surface(*_changed_sections_only(baseline, head_diff), usable)` | the carried findings' hunk split reads only changed sections, so an unchanged binary does not leave every carried finding unaudited | `test_c1_followups_2288.py::test_t1d_the_carried_audit_target_shows_no_section_of_a_file_unchanged_between_the_two_diffs[full]` |
| E3 | `_seed_carried`: `_audit_targets(state, cfg, hunks, reviewed_diff=baseline)` (the unfiltered baseline) | the audit's `fixerDelta` diffs the unfiltered baseline against the head, so a file unchanged between them never shows as an addition | the same `test_t1d_...[full]` |
| E4 | `_after_audits`, audit-first branch: `_bind_audit_spawned(state, new_issues, raised)` | a child an audit raised on the full returning path is linked to its parent | `test_c1_followups_2288.py::test_t2a_a_child_the_full_returning_audit_raised_is_linked_rides_the_parents_next_audit_and_is_not_left_unfixed` |
| E5 | `_with_carried`: `_move_audit_spawned(state, (fresh_key, held_key), new_key)` | a link bound to a key the merge replaced moves to the key the merged row keeps | `test_c1_followups_2288.py::test_t2b_a_compiled_child_bound_to_a_parent_keeps_its_link_under_the_key_the_merge_keeps_and_still_rides` |
| E6 | `_stamp_fix_groups`: the append into the round's `fixGroups` (`_record_round(state, "fixGroups", recorded)`) | a second synthesis wave of one round appends its groups, never replaces the first wave's | `test_c1_followups_2288.py::test_t3a_a_round_with_a_second_synthesis_wave_records_both_waves_groups_the_first_waves_first` |

E2 and E3 share one proving test: the two neutralizations fail it at different assertions (E2 at the first action, E3 at the fixer-delta content), so each bites on its own. E2's proving test is the `[full]` case; the `[changed]` case was not run for the proof.

Not neutralized by this record (the order's budget is one neutralization per declared element): the dedupe test inside E6's append (`group["id"] not in have`, pinned by `test_t3b_stamping_the_same_groups_again_in_one_round_does_not_duplicate_them`), the non-list reset inside E6 (pinned by `test_e6_...`), the conflict branch inside E5 (pinned by `test_t2b_two_different_parents_converging_on_one_merged_key_leave_no_link`), the multiset and one-sided-section arms of `_changed_sections_only` (pinned by `test_e1_`, `test_e2_`, `test_e3_` and `test_a_diff_with_no_section_has_nothing_to_drop`), and T1b and T1c. T1b has the same failure mode as T1a (E1's line), and T1c's changed-binary arm is the fail-closed contrast, which no neutralization of E1 to E6 turns red. These stand as unproven by neutralization.

---

## E1 — the filter in `_returning_surface`

**axis:** an unchanged binary section never reaches a diff parser on the returning path.

**neutralization** (`round_driver.py`, `_returning_surface`):
```python
-        delta = _fix_delta_surface(state, *_changed_sections_only(baseline, head_diff), only=only)
+        delta = _fix_delta_surface(state, baseline, head_diff, only=only)
```

**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_t1a_an_unchanged_binary_beside_a_one_line_change_gets_the_scoped_review_not_the_panel _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-2/test_t1a_an_unchanged_binary_b0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7f369c4ee1e0>

    def test_t1a_an_unchanged_binary_beside_a_one_line_change_gets_the_scoped_review_not_the_panel(tmp_path, monkeypatch):
        s = TS.Session(tmp_path, monkeypatch, first=_first_with(**{BLOB: BIN_A}), change=_one_line_change)
        assert "Binary files" in s.cfg["diff"] and "Binary files" in _baseline(s)  # premise: the binary is in both diffs
        _premise_unparseable(s)
        assert _sections(s.cfg["diff"], BLOB) == _sections(_baseline(s), BLOB) != []  # premise: and it did not change
        answer = s.next()
        state = s.state()
>       assert (answer["action"], answer["round"]) == (RD.P_SCOPED, 1), answer
E       AssertionError: {'ok': True, 'action': 'dispatch-panel', 'round': 1, 'phase': 'dispatch-panel', ...}
E       assert ('dispatch-panel', 1) == ('dispatch-scoped-finder', 1)
E         
E         At index 0 diff: 'dispatch-panel' != 'dispatch-scoped-finder'
E         Use -v to get more diff

/home/user/wt-2288/plugins/superheroes/lib/tests/test_c1_followups_2288.py:97: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1_followups_2288.py::test_t1a_an_unchanged_binary_beside_a_one_line_change_gets_the_scoped_review_not_the_panel
1 failed in 3.67s
```

**restore:** the inverse edit, the starred call put back.

**restore receipt:** `grep -n -B2 -A1 "_changed_sections_only(baseline, head_diff), only=only" plugins/superheroes/lib/round_driver.py` printed
```
1638-    try:
1639-        # axis: a file whose section is the same in both diffs never reaches a parser, so an unchanged binary or rename cannot force the full panel — see bite-proof record c1_followups_2288
1640:        delta = _fix_delta_surface(state, *_changed_sections_only(baseline, head_diff), only=only)
1641-    except Exception as exc:  # noqa: BLE001 — a surface nobody could work out is a full panel, never a hand-back
```

**raw green:**
```
.                                                                        [100%]
1 passed in 7.74s
```

---

## E2 — the filter in `_seed_carried`'s `split_fix_surface`

**axis:** the carried findings' hunk split reads only the sections that changed.

**neutralization** (`round_driver.py`, `_seed_carried`):
```python
-        split = delta_surface.split_fix_surface(*_changed_sections_only(baseline, head_diff), usable)
+        split = delta_surface.split_fix_surface(baseline, head_diff, usable)
```

**raw red** (the carried finding is no longer audited: `split_fix_surface` reads the unchanged binary, answers unknown, and the finding is sent back, so round 1 opens on the panel):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_t1d_the_carried_audit_target_shows_no_section_of_a_file_unchanged_between_the_two_diffs[full] _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-4/test_t1d_the_carried_audit_tar0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7f75f6414710>
record = {'abandoned': {'reason': 'the loop was closed before it ended'}}
read = 'full'

    @pytest.mark.parametrize("record,read", [(None, "changed"), (TC.ABANDONED, "full")], ids=["changed", "full"])
    def test_t1d_the_carried_audit_target_shows_no_section_of_a_file_unchanged_between_the_two_diffs(tmp_path, monkeypatch, record, read):
        first = dict(TC.FIRST, **{"src/other.py": TR.numbered("other", 12), BLOB: BIN_A})
        finding = TC._finding(27)
        s = TC._session(tmp_path, monkeypatch, [finding], first=first, change=TC.FIXES_LINE_27, record=record)
        _premise_unparseable(s)
        for file in ("src/other.py", BLOB):  # premise: both unchanged files are in both diffs, the same
            assert _sections(s.cfg["diff"], file) == _sections(_baseline(s), file) != []
        answer = s.next()
>       assert answer["action"] == RD.P_AUDITS and s.state()["config"]["returning"]["read"] == read, answer
E       AssertionError: {'ok': True, 'action': 'dispatch-panel', 'round': 1, 'phase': 'dispatch-panel', ...}
E       assert ('dispatch-panel' == 'dispatch-audits'
E         
E         - dispatch-audits
E         + dispatch-panel)

/home/user/wt-2288/plugins/superheroes/lib/tests/test_c1_followups_2288.py:152: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1_followups_2288.py::test_t1d_the_carried_audit_target_shows_no_section_of_a_file_unchanged_between_the_two_diffs[full]
1 failed in 8.08s
```

**restore:** the inverse edit, the starred call put back.

**restore receipt:** `grep -n -B1 -A1 "split_fix_surface(\*_changed" plugins/superheroes/lib/round_driver.py` printed
```
1676-        # axis: the carried findings' hunk split reads only the sections that changed; the audit's own delta below stays on the unfiltered pair — see bite-proof record c1_followups_2288
1677:        split = delta_surface.split_fix_surface(*_changed_sections_only(baseline, head_diff), usable)
1678-        hunks = {} if split.get("unknown") else split.get("auditTargets") or {}
```

**raw green:**
```
.                                                                        [100%]
1 passed in 3.31s
```

---

## E3 — the unfiltered baseline in the audit's fixer delta

**axis:** the audit's `fixerDelta` diffs the unfiltered baseline against the head, so a file unchanged between the two diffs never shows as an addition.

**neutralization** (`round_driver.py`, `_seed_carried`; the filtered baseline goes to `_audit_targets`):
```python
-    state["_auditTargets"] = _audit_targets(state, cfg, hunks, reviewed_diff=baseline)
+    state["_auditTargets"] = _audit_targets(state, cfg, hunks, reviewed_diff=_changed_sections_only(baseline, head_diff)[0])
```

**raw red** (the target's `fixerDelta` now lists the unchanged `src/other.py` as an addition):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_t1d_the_carried_audit_target_shows_no_section_of_a_file_unchanged_between_the_two_diffs[full] _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-6/test_t1d_the_carried_audit_tar0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7f2e6287f500>
record = {'abandoned': {'reason': 'the loop was closed before it ended'}}
read = 'full'

    @pytest.mark.parametrize("record,read", [(None, "changed"), (TC.ABANDONED, "full")], ids=["changed", "full"])
    def test_t1d_the_carried_audit_target_shows_no_section_of_a_file_unchanged_between_the_two_diffs(tmp_path, monkeypatch, record, read):
        first = dict(TC.FIRST, **{"src/other.py": TR.numbered("other", 12), BLOB: BIN_A})
        finding = TC._finding(27)
        s = TC._session(tmp_path, monkeypatch, [finding], first=first, change=TC.FIXES_LINE_27, record=record)
        _premise_unparseable(s)
        for file in ("src/other.py", BLOB):  # premise: both unchanged files are in both diffs, the same
            assert _sections(s.cfg["diff"], file) == _sections(_baseline(s), file) != []
        answer = s.next()
        assert answer["action"] == RD.P_AUDITS and s.state()["config"]["returning"]["read"] == read, answer
        [target] = answer["payload"]["targets"]
        assert target["id"] == finding[SC.FINDING_KEY_FIELD]
        delta = target["fixerDelta"]
        assert "-+edited_b = 1" in delta and "++edited_b = 2" in delta, delta  # positive control: the fix is there
>       assert not [ln for ln in delta if "other.py" in ln or "blob.bin" in ln or "value_other_" in ln or "Binary files" in ln], delta
E       AssertionError: ['diff --git a/src/shared.py b/src/shared.py', '@@ -1,5 +1,5 @@', ' diff --git a/src/shared.py b/src/shared.py', '-index d1e213f..4690478 100644', '+index d1e213f..6299d95 100644', ' --- a/src/shared.py', ...]
E       assert not ['diff --git a/src/other.py b/src/other.py', '+diff --git a/src/other.py b/src/other.py', '++++ b/src/other.py', '++value_other_0 = 0', '++value_other_1 = 1', '++value_other_2 = 2', ...]

/home/user/wt-2288/plugins/superheroes/lib/tests/test_c1_followups_2288.py:157: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1_followups_2288.py::test_t1d_the_carried_audit_target_shows_no_section_of_a_file_unchanged_between_the_two_diffs[full]
1 failed in 3.42s
```

**restore:** the inverse edit, `reviewed_diff=baseline` put back.

**restore receipt:** `grep -n "_audit_targets(state, cfg, hunks" plugins/superheroes/lib/round_driver.py` printed
```
1694:    state["_auditTargets"] = _audit_targets(state, cfg, hunks, reviewed_diff=baseline)
```

**raw green:**
```
.                                                                        [100%]
1 passed in 3.37s
```

---

## E4 — the spawn-map bind in the audit-first branch

**axis:** a child an audit raised on the full returning path is linked to its parent.

**neutralization** (`round_driver.py`, `_after_audits`; the call line deleted):
```python
         raised, drops = mechanical_compile(new_issues, state.get("reviewedDiff"))
-        _bind_audit_spawned(state, new_issues, raised)
         _record_compile_drops(state, drops)
```

**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_t2a_a_child_the_full_returning_audit_raised_is_linked_rides_the_parents_next_audit_and_is_not_left_unfixed _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-8/test_t2a_a_child_the_full_retu0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7f553492dc70>

    def test_t2a_a_child_the_full_returning_audit_raised_is_linked_rides_the_parents_next_audit_and_is_not_left_unfixed(tmp_path, monkeypatch):
        parent = TC._finding(27, tradeoff=False)
        pk = parent[SC.FINDING_KEY_FIELD]
        s = TC._session(tmp_path, monkeypatch, [parent], change=TC.TOUCHES_NEAR_27, record=TC.ABANDONED)
        respond = _spawning_responder(pk)
        # round 1, the full read: the carried parent is audited first, then the panel runs
        n, seen = TC._run(s, respond, stop_at=RD.P_VERIFIERS)
        assert n["action"] == RD.P_VERIFIERS and seen[:2] == [(RD.P_AUDITS, 1), (RD.P_PANEL, 1)], seen
        state = s.state()
        assert state["config"]["returning"]["read"] == "full"
        [ck] = [SC.finding_identity_key(f) for f in state["_toVerify"] if f.get("title") == CHILD["title"]]
        assert ck != pk
>       assert state["auditSpawned"] == {ck: pk}  # the link is bound where the audit's new issues are compiled
               ^^^^^^^^^^^^^^^^^^^^^
E       KeyError: 'auditSpawned'

/home/user/wt-2288/plugins/superheroes/lib/tests/test_c1_followups_2288.py:233: KeyError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1_followups_2288.py::test_t2a_a_child_the_full_returning_audit_raised_is_linked_rides_the_parents_next_audit_and_is_not_left_unfixed
1 failed in 3.96s
```

**restore:** the inverse edit, the call line put back between the compile and `_record_compile_drops`.

**restore receipt:** `grep -n -B2 -A3 "_bind_audit_spawned(state, new_issues, raised)" plugins/superheroes/lib/round_driver.py` printed
```
8403-        raised, drops = mechanical_compile(new_issues, state.get("reviewedDiff"))
8404-        # axis: a child an audit raised on the full returning path is linked to its parent here, as `_fold_scoped` links it, so a later audit of the parent carries it — see bite-proof record c1_followups_2288
8405:        _bind_audit_spawned(state, new_issues, raised)
8406-        _record_compile_drops(state, drops)
8407-        state["_carriedToVerify"] = (state.get("_carriedToVerify") or []) + raised
8408-        state["step"] = P_PANEL
```

**raw green:**
```
.                                                                        [100%]
1 passed in 4.08s
```

---

## E5 — the `auditSpawned` move in `_with_carried`

**axis:** a link bound to a key the merge replaced moves to the key the merged row keeps.

**neutralization** (`round_driver.py`, `_with_carried`; the call line deleted):
```python
-        _move_audit_spawned(state, (fresh_key, held_key), new_key)
```

**raw red** (the link stays under the fresh report's derived key, which no row holds any more):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_t2b_a_compiled_child_bound_to_a_parent_keeps_its_link_under_the_key_the_merge_keeps_and_still_rides _

    def test_t2b_a_compiled_child_bound_to_a_parent_keeps_its_link_under_the_key_the_merge_keeps_and_still_rides():
        state, parent, held, fresh, fresh_key = _merge_state(None)
        pk, hk = parent[SC.FINDING_KEY_FIELD], held[SC.FINDING_KEY_FIELD]
        new_issue = dict(fresh, originAuditId=pk)  # an audit of the parent raised it
        compiled = RD.mechanical_compile([dict(new_issue)], None)[0]
        RD._bind_audit_spawned(state, [new_issue], compiled)
        assert state["auditSpawned"] == {fresh_key: pk}  # premise: bound under the fresh report's key
        merged = RD._with_carried(state, compiled)
        [row] = merged
        assert RD._finding_identity_key(row) == hk  # the merged row keeps the held row's stored key
>       assert state["auditSpawned"] == {hk: pk}
E       AssertionError: assert {'src/shared....4a816d12b05c'} == {'rr1:81b3ad6...4a816d12b05c'}
E         
E         Left contains 1 more item:
E         {'src/shared.py::the first edit is stale@L3': 'rr1:6830197dfc65d27498e74a816d12b05c'}
E         Right contains 1 more item:
E         {'rr1:81b3ad69ccd34165f08eb188b3e12541': 'rr1:6830197dfc65d27498e74a816d12b05c'}
E         Use -v to get more diff

/home/user/wt-2288/plugins/superheroes/lib/tests/test_c1_followups_2288.py:286: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1_followups_2288.py::test_t2b_a_compiled_child_bound_to_a_parent_keeps_its_link_under_the_key_the_merge_keeps_and_still_rides
1 failed in 2.83s
```

**restore:** the inverse edit, the call line put back under its axis comment.

**restore receipt:** `grep -n -B2 -A2 "_move_audit_spawned(state, (fresh_key" plugins/superheroes/lib/round_driver.py` printed
```
1757-                    run["findingKey"] = new_key
1758-        # axis: a parent link bound to either key the merge replaced moves to the key the merged row keeps; two different parents leave no link — see bite-proof record c1_followups_2288
1759:        _move_audit_spawned(state, (fresh_key, held_key), new_key)
1760-    return rest + [rows[id(h)] for h in held]
1761-
```

**raw green:**
```
.                                                                        [100%]
1 passed in 2.83s
```

---

## E6 — the append in `_stamp_fix_groups`

**axis:** a second synthesis wave of one round appends its groups, never replaces the first wave's.

**neutralization** (`round_driver.py`, `_stamp_fix_groups`; the overwriting write restored):
```python
-    _record_round(state, "fixGroups", recorded)
+    _record_round(state, "fixGroups", stamped)
```

**raw red** (the round's `fixGroups` holds the second wave's group alone):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_t3a_a_round_with_a_second_synthesis_wave_records_both_waves_groups_the_first_waves_first _

    def test_t3a_a_round_with_a_second_synthesis_wave_records_both_waves_groups_the_first_waves_first():
        state = TRM._state()
        wave_one = _wave(state, "wave one", TFG.A_PATH, TFG.B_PATH)
        assert _groups(state, 1) == [(TFG._group_id(*wave_one), sorted(wave_one))]
        wave_two = _wave(state, "wave two", "tests/test_wave_two_a.py", "tests/test_wave_two_b.py")
        assert state["round"] == 1
>       assert _groups(state, 1) == [(TFG._group_id(*wave_one), sorted(wave_one)), (TFG._group_id(*wave_two), sorted(wave_two))]
E       AssertionError: assert [('fg-a683cde...two two@L2'])] == [('fg-8205276...two two@L2'])]
E         
E         At index 0 diff: ('fg-a683cdee456e', ['f.py::wave two one@L1', 'f.py::wave two two@L2']) != ('fg-820527661d37', ['f.py::wave one one@L1', 'f.py::wave one two@L2'])
E         Right contains one more item: ('fg-a683cdee456e', ['f.py::wave two one@L1', 'f.py::wave two two@L2'])
E         Use -v to get more diff

/home/user/wt-2288/plugins/superheroes/lib/tests/test_c1_followups_2288.py:359: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1_followups_2288.py::test_t3a_a_round_with_a_second_synthesis_wave_records_both_waves_groups_the_first_waves_first
1 failed in 3.12s
```

**restore:** the inverse edit, `recorded` put back.

**restore receipt:** `grep -n -B7 -A1 '_record_round(state, "fixGroups"' plugins/superheroes/lib/round_driver.py` printed
```
4595-    current = state["rounds"].setdefault(str(state["round"]), {}).get("fixGroups")
4596-    recorded = list(current) if isinstance(current, list) else []
4597-    have = {g.get("id") for g in recorded if isinstance(g, dict)}
4598-    for group in stamped:
4599-        if group["id"] not in have:
4600-            have.add(group["id"])
4601-            recorded.append(group)
4602:    _record_round(state, "fixGroups", recorded)
4603-
```

**raw green:**
```
.                                                                        [100%]
1 passed in 3.19s
```
