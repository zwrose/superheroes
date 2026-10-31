# C1-L11f (WO-E) bite-proof — the verify gate after a restore: a rerun is recorded before the halt, an unknown-head pass halts, the in-process seam can report its head, a same-anchor merge carries `testCorrection`

**Provenance:** implementer WO-E and WO-E2, recording the guards on `lib/round_driver.py` (`_fold_verify`, `_run_seam`'s verify leg, `_merge_same_finding`), proved by `lib/tests/test_c1l11f_wo_e_verify_after_restore.py` and `lib/tests/test_c1l10b_test_restore.py`.

Declared guarded elements (from the order): E-G1 rerun entry before the restore-gate halt; E-G2 unknown-head halt after a restore; E-G3 `_merge_same_finding`'s `TEST_CORRECTION_FIELD` carry; E-G4 the seam's `headSha` take. The census (the Grep tool, pattern `c1l11f_wo_e_verify_after_restore`, over `plugins/superheroes/lib/*.py`) printed the axis lines in `round_driver.py` at 6870 (E-G1), 6883 (E-G2), 9509 (E-G4), and E-G3's at the `_merge_same_finding` carry (guarded tuple ends at line 864).

Each element was neutralized with one targeted Edit and restored with the inverse Edit; no `git checkout`, `restore`, `reset` or `stash` was used. Run from the worktree root under `timeout 600 scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-wo-e2 -m pytest <node ids> -q -p no:cacheprovider`. Each capture is the runner's whole output for that run apart from the `UV_NATIVE_TLS` deprecation warning line (the first line of each real output), which is left out; nothing else is trimmed. Nothing is redacted: no secrets, tokens or URLs appear (the `/tmp/claude-0/...` paths are pytest temp directories). The restore receipt of each element is the restored line quoted back; the whole-file receipt is `git diff HEAD --stat` over `round_driver.py`, quoted in the return, showing only the order's seam edit and the E-G3 axis-comment suffix.

| ID | Guarded element | Axis | Proving node ids |
|---|---|---|---|
| E-G1 | `_fold_verify`, the `if first is not None:` rerun-entry append inside the restore gate (`round_driver.py:6869`) | a retry that ran at another head after a restore leaves both runs in the review record before the gate halts | `test_c1l11f_wo_e_verify_after_restore.py::test_e1_a_retry_at_another_head_after_a_restore_records_both_runs_then_halts` |
| E-G2 | `_fold_verify`, `if restored is not None and head is None and result == "pass":` (`round_driver.py:6884`) | after a restore a pass whose head is unknown on both sides halts and never advances (also on `run_loop`'s in-process leg, which passes no head) | `test_e2_a_pass_with_no_known_head_after_a_restore_halts_and_does_not_advance`; `test_c1l10b_test_restore.py::test_t2_a_round_at_the_cap_restores_then_a_bare_pass_with_no_head_halts_with_certification_withheld` |
| E-G3 | `_merge_same_finding`, `TEST_CORRECTION_FIELD` in the carried-fields tuple (`round_driver.py:864`) | an attached test's `testCorrection` survives a same-anchor merge an ordinary finding wins | `test_e3_a_same_anchor_merge_an_ordinary_finding_wins_keeps_the_carriers_test_correction` |
| E-G4 | `_run_seam`, the verify leg's `headSha` take (`round_driver.py:9510`) | the in-process verify seam may report the head the run ran at (a non-empty string only), which the restore gate then counts | `test_c1l10b_test_restore.py::test_t2_a_round_at_the_cap_restores_then_hands_back_the_open_finding`; `test_seam_a_dict_return_gives_its_result_and_a_non_empty_string_head` |

## E-G1

**Neutralization:** `if first is not None:` (line 6869) became `if False and first is not None:`.

**Raw red** (`test_e1_a_retry_at_another_head_after_a_restore_records_both_runs_then_halts`):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_e1_a_retry_at_another_head_after_a_restore_records_both_runs_then_halts _

    def test_e1_a_retry_at_another_head_after_a_restore_records_both_runs_then_halts():
        # axis: the rerun entry with both runs is recorded before the restore gate's halt — see bite-proof record c1l11f_wo_e_verify_after_restore
        state = _restored_state()
        _fold(state, _artifact("fail", head=H1))
        assert "_verifyRerun" in state and not state.get("terminal")
        _fold(state, _artifact("pass", head=H2))
    
        assert state["terminal"] == "halted" and state["step"] == RD.P_TERMINAL
        assert _kinds(state)[-1] == "verify-unresolved"
>       (entry,) = _entries(state)
        ^^^^^^^^
E       ValueError: not enough values to unpack (expected 1, got 0)

/home/user/wt-2279-e/plugins/superheroes/lib/tests/test_c1l11f_wo_e_verify_after_restore.py:56: ValueError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l11f_wo_e_verify_after_restore.py::test_e1_a_retry_at_another_head_after_a_restore_records_both_runs_then_halts
1 failed in 1.10s
```

**Restore:** the inverse Edit, `if False and first is not None:` back to `if first is not None:`. **Restore receipt:** line 6869 reads `        if first is not None:` (Grep on the tool, after the restore), followed by the axis comment at 6870.

**Raw green:**

```
.                                                                        [100%]
1 passed in 0.94s
```

## E-G2

**Neutralization:** `if restored is not None and head is None and result == "pass":` (line 6884) became `if False and restored is not None and head is None and result == "pass":`.

**Raw red** (the two proving nodes in one run):

```
FF                                                                       [100%]
=================================== FAILURES ===================================
_ test_e2_a_pass_with_no_known_head_after_a_restore_halts_and_does_not_advance _

    def test_e2_a_pass_with_no_known_head_after_a_restore_halts_and_does_not_advance():
        # axis: the gate after a restore halts on a pass whose head is unknown on both sides — see bite-proof record c1l11f_wo_e_verify_after_restore
        state = _restored_state()
        _fold(state, _artifact("pass", head=None))
    
>       assert state["terminal"] == "halted" and state["step"] == RD.P_TERMINAL
E       AssertionError: assert (None == 'halted')

/home/user/wt-2279-e/plugins/superheroes/lib/tests/test_c1l11f_wo_e_verify_after_restore.py:115: AssertionError
_ test_t2_a_round_at_the_cap_restores_then_a_bare_pass_with_no_head_halts_with_certification_withheld _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-105/test_t2_a_round_at_the_cap_res0')

    def test_t2_a_round_at_the_cap_restores_then_a_bare_pass_with_no_head_halts_with_certification_withheld(tmp_path):
        # the in-process leg passes no head: a pass with no run head and no fold head after a restore never advances
        w = World(tmp_path, cap=2)
    
        def fix_step(batch, rnd, payload):
            assert payload.get("restoreOnly"), "the run must halt at the verify gate, before any settle fix"
            w.write(TEST_PATH, payload["restores"][0]["content"])
            _commit(w.root, "restore")
            return {"fixes": []}
    
        def reviewer(dim, tier, rnd, ctx):
            return {"findings": [], "vendor": "codex"}
    
        # axis: a bare "pass" from the in-process verify seam carries no head, so the gate after a restore halts — see bite-proof record c1l11f_wo_e_verify_after_restore
        seams = TRD._seams(auditor=lambda targets, rnd: w.audit_artifact()["results"], fix_step=fix_step,
                           reviewer=reviewer, verify_runner=lambda command, rnd: "pass")
        seams["panel_diff"] = lambda config, head: (TRD.DIFF, None)
>       _receipt, state = w.run_loop(seams)
                          ^^^^^^^^^^^^^^^^^

/home/user/wt-2279-e/plugins/superheroes/lib/tests/test_c1l10b_test_restore.py:379: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/home/user/wt-2279-e/plugins/superheroes/lib/tests/test_c1l10b_test_restore.py:204: in run_loop
    return TRD._run_loop_capturing_state(seams, self.cfg)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/home/user/wt-2279-e/plugins/superheroes/lib/tests/test_round_driver.py:196: in _run_loop_capturing_state
    result = RD.run_loop(seams, config)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^
/home/user/wt-2279-e/plugins/superheroes/lib/round_driver.py:9731: in run_loop
    artifact = _run_seam(seams, action, step["payload"], state, state["config"])
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/home/user/wt-2279-e/plugins/superheroes/lib/round_driver.py:9514: in _run_seam
    return seams["fix_step"](payload.get("batch"), state["round"], payload)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

batch = [{'id': 'tests/test_charge.py::retry charges twice@L1', 'findingKey': 'tests/test_charge.py::retry charges twice@L1', 'identity': 'tests/test_charge.py::retry charges twice', 'file': 'tests/test_charge.py', ...}]
rnd = 2
payload = {'batch': [{'id': 'tests/test_charge.py::retry charges twice@L1', 'findingKey': 'tests/test_charge.py::retry charges t...::retry charges twice', 'file': 'tests/test_charge.py', ...}], 'startHead': '6086c140da4fe7e49bad00e862a22b678139605f'}

    def fix_step(batch, rnd, payload):
>       assert payload.get("restoreOnly"), "the run must halt at the verify gate, before any settle fix"
E       AssertionError: the run must halt at the verify gate, before any settle fix
E       assert None
E        +  where None = <built-in method get of dict object at 0x7f260ab8de00>('restoreOnly')
E        +    where <built-in method get of dict object at 0x7f260ab8de00> = {'batch': [{'id': 'tests/test_charge.py::retry charges twice@L1', 'findingKey': 'tests/test_charge.py::retry charges t...::retry charges twice', 'file': 'tests/test_charge.py', ...}], 'startHead': '6086c140da4fe7e49bad00e862a22b678139605f'}.get

=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l11f_wo_e_verify_after_restore.py::test_e2_a_pass_with_no_known_head_after_a_restore_halts_and_does_not_advance
FAILED plugins/superheroes/lib/tests/test_c1l10b_test_restore.py::test_t2_a_round_at_the_cap_restores_then_a_bare_pass_with_no_head_halts_with_certification_withheld
2 failed in 3.10s
```

(Disclosure: the `...` inside the `payload = {...}` and `where ... = {...}` lines is pytest's own truncation; nothing in this capture was shortened by hand.)

**Restore:** the inverse Edit, `if False and restored is not None ...` back to `if restored is not None and head is None and result == "pass":`. **Restore receipt:** line 6884 reads `    if restored is not None and head is None and result == "pass":`.

**Raw green:**

```
..                                                                       [100%]
2 passed in 2.98s
```

## E-G3

**Neutralization:** the carried-fields tuple in `_merge_same_finding` lost its last member (`TEST_CORRECTION_FIELD`): `REVIEWER_TEST_FIELD,\n TEST_CORRECTION_FIELD):` became `REVIEWER_TEST_FIELD):`.

**Raw red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_e3_a_same_anchor_merge_an_ordinary_finding_wins_keeps_the_carriers_test_correction _

    def test_e3_a_same_anchor_merge_an_ordinary_finding_wins_keeps_the_carriers_test_correction():
        # axis: an attached test, its stamp and its runs survive a same-anchor merge the other finding wins — see bite-proof record c1l11f_wo_e_verify_after_restore
        correction = {"round": 2, "used": True, "outcome": "corrected"}
        carrier = {"file": "f.py", "line": 1, "title": "t", "severity": "Nit", "taxonomy": "break-it-test",
                   RD.break_it.RUN_FIELD: {"outcome": "failed"}, RD.TEST_CORRECTION_FIELD: correction}
        plain = {"file": "f.py", "line": 1, "title": "t", "severity": "Critical"}
        for existing, incoming in ((carrier, plain), (plain, carrier)):
            merged = RD._merge_same_finding(existing, incoming)
            assert merged["severity"] == "Critical"
>           assert merged[RD.TEST_CORRECTION_FIELD] == correction
                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E           KeyError: 'testCorrection'

/home/user/wt-2279-e/plugins/superheroes/lib/tests/test_c1l11f_wo_e_verify_after_restore.py:216: KeyError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l11f_wo_e_verify_after_restore.py::test_e3_a_same_anchor_merge_an_ordinary_finding_wins_keeps_the_carriers_test_correction
1 failed in 1.07s
```

**Restore:** the inverse Edit put `TEST_CORRECTION_FIELD` back on its own continuation line. **Restore receipt:** line 864 reads `                      TEST_CORRECTION_FIELD):`.

**Raw green:**

```
.                                                                        [100%]
1 passed in 1.10s
```

## E-G4

**Neutralization:** `if isinstance(ran.get("headSha"), str) and ran["headSha"]:` (line 9510) became `if False and isinstance(ran.get("headSha"), str) and ran["headSha"]:`.

**Raw red** (the three nodes the order named, plus the seam unit test):

```
.FF                                                                      [100%]
=================================== FAILURES ===================================
_____ test_t2_a_round_at_the_cap_restores_then_hands_back_the_open_finding _____

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-101/test_t2_a_round_at_the_cap_res0')

    def test_t2_a_round_at_the_cap_restores_then_hands_back_the_open_finding(tmp_path):
        # edge 11 / T6: the settle hands it back like any other open finding
        (body of the test as in the file; the full capture shows the same lines as the file)
>       assert state["terminal"] == "handed-back", (state["terminal"], state.get("certification"))
E       AssertionError: ('halted', {'shape': None, 'reason': 'verify passed at an unknown head, not the restored head 26d000c5f2f8d603fa90af38b6fc24ab4cb13eeb — halt, certification withheld'})
E       assert 'halted' == 'handed-back'
E         
E         - handed-back
E         + halted

/home/user/wt-2279-e/plugins/superheroes/lib/tests/test_c1l10b_test_restore.py:351: AssertionError
_ test_seam_a_dict_return_gives_its_result_and_a_non_empty_string_head _____

    def test_seam_a_dict_return_gives_its_result_and_a_non_empty_string_head():
        # axis: the in-process verify seam may report the head the run ran at, a non-empty string only — see bite-proof record c1l11f_wo_e_verify_after_restore
>       assert _seam_artifact({"result": "pass", "headSha": H1, "extra": "x"}) == {"result": "pass", "headSha": H1}
E       AssertionError: assert {'result': 'pass'} == {'result': 'p...111111111111'}
E         
E         Omitting 1 identical items, use -vv to show
E         Right contains 1 more item:
E         {'headSha': '1111111111111111111111111111111111111111'}
E         Use -v to get more diff

/home/user/wt-2279-e/plugins/superheroes/lib/tests/test_c1l11f_wo_e_verify_after_restore.py:183: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l10b_test_restore.py::test_t2_a_round_at_the_cap_restores_then_hands_back_the_open_finding
FAILED plugins/superheroes/lib/tests/test_c1l11f_wo_e_verify_after_restore.py::test_seam_a_dict_return_gives_its_result_and_a_non_empty_string_head
2 failed, 1 passed in 2.92s
```

(Disclosure: the body of the first failing test, which the runner printed in full, is replaced by one parenthetical line here; the rest is verbatim.)

**The first of the three nodes passing is a finding, not a bite:** `test_t2_the_extra_audit_round_restores_then_verifies_then_hands_back_open` stays green under this neutralization, because it drives `World.verify`, which folds `{"result": "pass", "headSha": ...}` straight into `_fold` and never passes through `_run_seam`. It is therefore **not** a detector for E-G4; it proves the known-head path of the gate (`headSha` equal to the restored head advances), not the seam's take. The bites for E-G4 are the cap test (run_loop, through the seam) and the seam unit test.

**Restore:** the inverse Edit, `if False and isinstance(...)` back to `if isinstance(ran.get("headSha"), str) and ran["headSha"]:`. **Restore receipt:** line 9510 reads `        if isinstance(ran.get("headSha"), str) and ran["headSha"]:`.

**Raw green** (the same three node ids):

```
...                                                                      [100%]
3 passed in 3.01s
```

## Not separately neutralized (unproven)

- E-G4: the `non-empty` and `str` legs of the `headSha` test and the dict-without-`result` path are pinned by `test_seam_a_head_that_is_not_a_non_empty_string_is_ignored` and `test_seam_a_dict_with_no_result_has_no_result_and_fails_closed_as_unresolved` passing, but were not run under a neutralization; they are **unproven** as separate guards.
- E-G2: the `result == "pass"` leg (a fail with an unknown head goes the rerun path; a skip keeps today's advance) is pinned by `test_e2_a_fail_with_no_known_head...` and `test_e2_a_skip_with_no_verify_command...` passing, not by a neutralization: **unproven**. The second `if first is not None:` (the rerun append before the unknown-head halt, line 6885) is pinned by `test_e2_a_retry_pass_with_no_known_head_after_a_restore_records_both_runs_then_halts` but was not neutralized: **unproven**.
- E-G1: `force_head_moved` inside `_verify_rerun_entry` (the `heads` and `decision` of the restore-gate entry) is covered by the same test's `entry["decision"]`/`entry["heads"]` assertions but was not neutralized separately: **unproven** as its own guard.

---

# WO-G addendum (build #2279, C1-L11f seam fix after the capped review)

**Provenance:** implementer WO-G, order id `wo-g`, in the worktree `/home/user/wt-2279`, head at dispatch `a722e5f5`. One guard, G3-a, in `_fold_verify`, proved by `test_c1l11f_wo_e_verify_after_restore.py::test_e4_a_first_pass_that_moved_head_while_running_after_a_restore_halts_naming_both_heads` (the fold) and `test_c1l10b_test_restore.py::test_t2_a_first_pass_whose_head_moved_while_running_halts_through_the_run_loop_callback` (the `run_loop` callback). Neutralized with one targeted Edit and restored with the inverse Edit (no `git checkout`, `restore`, `reset` or `stash`). Captures are the runner's whole output apart from the `UV_NATIVE_TLS` deprecation warning line, which is left out. Nothing is redacted.

| ID | Guarded element | Axis | Proving node |
|---|---|---|---|
| G3-a | `_fold_verify`, `if restored is not None and first is None and moved and result == "pass":` (`round_driver.py:6905`) | after a restore a first passing run whose head moved during the run halts with certification withheld and a `verify-unresolved` decision naming both heads; a pending retry keeps the rerun path's `head-moved` record | the two nodes above |

## G3-a

**Red before the fix** (both new nodes run against the unchanged `_fold_verify`, the two files in one invocation; whole output):

```
............F.......F                                                    [100%]
=================================== FAILURES ===================================
_ test_e4_a_first_pass_that_moved_head_while_running_after_a_restore_halts_naming_both_heads _

    def test_e4_a_first_pass_that_moved_head_while_running_after_a_restore_halts_naming_both_heads():
        # axis: the gate after a restore halts on a result whose head moved during the run, whether or not a retry is pending — see bite-proof record c1l11f_wo_e_verify_after_restore
        state = _restored_state()
        _fold(state, _artifact("pass", head=H1, after=H2))
    
>       assert state["terminal"] == "halted" and state["step"] == RD.P_TERMINAL
E       AssertionError: assert (None == 'halted')

/home/user/wt-2279/plugins/superheroes/lib/tests/test_c1l11f_wo_e_verify_after_restore.py:182: AssertionError
_ test_t2_a_first_pass_whose_head_moved_while_running_halts_through_the_run_loop_callback _

(traceback through run_loop elided here: about 3 KiB; it ends in the fix_step callback)

E       AssertionError: the run must halt at the verify gate, before any settle fix
E       assert None
E        +  where None = <built-in method get of dict object at 0x7f70bdc7bc80>('restoreOnly')

/home/user/wt-2279/plugins/superheroes/lib/tests/test_c1l10b_test_restore.py:424: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l11f_wo_e_verify_after_restore.py::test_e4_a_first_pass_that_moved_head_while_running_after_a_restore_halts_naming_both_heads
FAILED plugins/superheroes/lib/tests/test_c1l10b_test_restore.py::test_t2_a_first_pass_whose_head_moved_while_running_halts_through_the_run_loop_callback
2 failed, 19 passed in 2.51s
```

(Disclosure: the middle of the second failure, its `run_loop` call stack and the `fix_step` source lines the runner echoed, is replaced by the one parenthetical line; the rest is verbatim. The loop advanced past the verify gate into a settle fix, which is the defect. The axis comment on the first node was reworded afterwards, as the node's pending-retry wording was inexact.)

**Neutralization:** `    if restored is not None and first is None and moved and result == "pass":` became `    if False and restored is not None and first is None and moved and result == "pass":`.

**Raw red** (`test_e4_a_first_pass_that_moved_head_while_running_after_a_restore_halts_naming_both_heads`):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_e4_a_first_pass_that_moved_head_while_running_after_a_restore_halts_naming_both_heads _

    def test_e4_a_first_pass_that_moved_head_while_running_after_a_restore_halts_naming_both_heads():
        # axis: the gate after a restore halts on a result whose head moved during the run, whether or not a retry is pending — see bite-proof record c1l11f_wo_e_verify_after_restore
        state = _restored_state()
        _fold(state, _artifact("pass", head=H1, after=H2))
    
>       assert state["terminal"] == "halted" and state["step"] == RD.P_TERMINAL
E       AssertionError: assert (None == 'halted')

/home/user/wt-2279/plugins/superheroes/lib/tests/test_c1l11f_wo_e_verify_after_restore.py:182: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l11f_wo_e_verify_after_restore.py::test_e4_a_first_pass_that_moved_head_while_running_after_a_restore_halts_naming_both_heads
1 failed in 0.90s
```

**Restore** (the inverse Edit): `if False and restored is not None and first is None and moved and result == "pass":` back to `if restored is not None and first is None and moved and result == "pass":`. **Restore receipt:** `grep -n "if restored is not None and first is None and moved" round_driver.py` prints `6905:    if restored is not None and first is None and moved and result == "pass":`.

**Raw green** (the same node, and then both files after the fix, `93 passed in 18.59s`, whose output was `........................................................................ [ 77%]` / `.....................                                                    [100%]`):

```
.                                                                        [100%]
1 passed in 0.95s
```

Not separately neutralized (unproven): the `first is None` leg (a pending retry keeps the rerun path) is pinned by `test_e1_a_retry_at_the_restored_head_that_moved_during_the_run_halts_on_the_rerun_path` passing; the `result == "pass"` leg (a moved `fail` keeps the fail path) by `test_e4_a_first_failure_that_moved_head_while_running_after_a_restore_keeps_the_fail_path` passing; the `restored is not None` leg by `test_e4_without_a_restore_a_first_pass_that_moved_head_behaves_as_today` passing. None was run under a neutralization.

---

# C1-L12 addendum (build #2216, entries for C1-L11f's review-loop axis lines)

**Provenance:** implementer WO-4, order id `c1l12-wo4`, worktree `/home/user/wo4`, branch `c1l12-wo4`, head at dispatch `86e05768`. Each entry is **re-derived at `86e05768`** by this order: the fixers' own red/green lived in their review sessions' folders on a container that has been reclaimed, and PR #2283's review records and round comments carry no break-it red/green for these lines, so none is quoted. A6 was added by fixer commit `dd84d915`, A7 and A8 by `6f91c091`. Each guarded element was neutralized with one targeted Edit and restored with the inverse Edit (no `git checkout`, `restore`, `reset` or `stash`); after each restore `git status --porcelain` listed no `.py` file outside `plugins/superheroes/lib/tests/`. Every run is `timeout 600 scripts/pinned-python -B -X pycache_prefix=/tmp/shpyc-wo4 -m pytest "<node id>" -q -p no:cacheprovider`. Each capture is the runner's whole output apart from the `UV_NATIVE_TLS` deprecation warning line, which is left out. Nothing is redacted: no secrets, tokens or URLs appear (the `/tmp/claude-0/...` paths are pytest temp directories). Every capture is under 32 KiB. A6 and A8 are axis lines written in tests; the guarded element is the production code the test exercises.

| ID | Guarded element | Axis (verbatim) | Proving node |
|---|---|---|---|
| A6 | the rerun decision in `round_driver.py`, `elif head_unresolved or artifact.get("result") != "pass":` (`round_driver.py:6838`); axis line at `test_c1l11f_wo_e_verify_after_restore.py:162` | the rejected retry is recorded as non-advancing, so the record never calls it a re-run on unchanged code — see bite-proof record c1l11f_wo_e_verify_after_restore | `test_e2_a_retry_pass_with_no_known_head_after_a_restore_records_both_runs_then_halts` |
| A7 | `_run_seam`, the `P_VERIFY` key tuple `("headSha", "headShaAfter", "treeSha", "treeShaAfter")` (`round_driver.py:9692`) | the seam's after-head and tree digests reach the fold, so a run that moved the head or changed the tree is seen as one — see bite-proof record c1l11f_wo_e_verify_after_restore | `test_seam_a_dict_return_carries_the_after_head_and_the_tree_digests_to_the_fold` (added by this order) |
| A8 | `_run_seam`, the `"headShaAfter"` member of the same tuple (`round_driver.py:9692`); axis line at `test_c1l10b_test_restore.py:387` | the seam's after-head reaches the fold, so a passing retry that straddled a head change is not called unchanged code — see bite-proof record c1l11f_wo_e_verify_after_restore | `test_c1l10b_test_restore.py::test_t2_a_retry_pass_whose_head_moved_while_running_halts_through_the_run_loop_callback` |

## A6

**Neutralization:** `    elif head_unresolved or artifact.get("result") != "pass":` became `    elif artifact.get("result") != "pass":` (`head_unresolved or` dropped).

**Raw red** (`test_e2_a_retry_pass_with_no_known_head_after_a_restore_records_both_runs_then_halts`):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_e2_a_retry_pass_with_no_known_head_after_a_restore_records_both_runs_then_halts _

    def test_e2_a_retry_pass_with_no_known_head_after_a_restore_records_both_runs_then_halts():
        state = _restored_state()
        _fold(state, _artifact("fail", head=None))
        _fold(state, _artifact("pass", head=None))
    
        assert state["terminal"] == "halted" and _kinds(state)[-1] == "verify-unresolved"
        assert "_verifyRerun" not in state
        (entry,) = _entries(state)
        assert len(entry["runs"]) == 2
        # axis: the rejected retry is recorded as non-advancing, so the record never calls it a re-run on unchanged code — see bite-proof record c1l11f_wo_e_verify_after_restore
>       assert entry["decision"] == "failed"
E       AssertionError: assert 'went-on' == 'failed'
E         
E         - failed
E         + went-on

/home/user/wo4/plugins/superheroes/lib/tests/test_c1l11f_wo_e_verify_after_restore.py:163: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l11f_wo_e_verify_after_restore.py::test_e2_a_retry_pass_with_no_known_head_after_a_restore_records_both_runs_then_halts
1 failed in 0.84s
```

The red is on the claimed axis: the run still halts (the earlier assertions pass) but the rejected retry's entry reads `went-on`, a re-run on unchanged code, instead of `failed`.

**Restore** (the inverse Edit): `    elif artifact.get("result") != "pass":` back to `    elif head_unresolved or artifact.get("result") != "pass":`. **Restore receipt:** the line is back as `    elif head_unresolved or artifact.get("result") != "pass":` followed by `        rerun_decision = "failed"`, and `git status --porcelain` listed no `.py` file outside `plugins/superheroes/lib/tests/`.

**Raw green** (the same node):

```
.                                                                        [100%]
1 passed in 0.96s
```

## A7

**Test added by this order:** `test_seam_a_dict_return_carries_the_after_head_and_the_tree_digests_to_the_fold` in `test_c1l11f_wo_e_verify_after_restore.py`, beside the other `test_seam_a_*` tests: it sends `headSha`, `headShaAfter`, `treeSha` and `treeShaAfter` through the in-process verify seam (`_seam_artifact`) and expects all four back. No existing node sends the tree digests through the seam. Collected with the module (`21 tests collected`) before use.

**Neutralization:** `        for key in ("headSha", "headShaAfter", "treeSha", "treeShaAfter"):` became `        for key in ("headSha",):`.

**Raw red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_seam_a_dict_return_carries_the_after_head_and_the_tree_digests_to_the_fold _

    def test_seam_a_dict_return_carries_the_after_head_and_the_tree_digests_to_the_fold():
        # bites on: the key tuple of the verify seam in `_run_seam` (A7): the after-head and both tree digests survive
        returned = {"result": "pass", "headSha": H1, "headShaAfter": H2, "treeSha": "a" * 40, "treeShaAfter": "b" * 40}
>       assert _seam_artifact(returned) == returned
E       AssertionError: assert {'result': 'p...111111111111'} == {'result': 'p...aaaaaaa', ...}
E         
E         Omitting 2 identical items, use -vv to show
E         Right contains 3 more items:
E         {'headShaAfter': '2222222222222222222222222222222222222222',
E          'treeSha': 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
E          'treeShaAfter': 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'}
E         Use -v to get more diff

/home/user/wo4/plugins/superheroes/lib/tests/test_c1l11f_wo_e_verify_after_restore.py:223: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l11f_wo_e_verify_after_restore.py::test_seam_a_dict_return_carries_the_after_head_and_the_tree_digests_to_the_fold
1 failed in 1.01s
```

The red is on the claimed axis: the after-head and both tree digests the seam was handed do not reach the artifact.

**Restore** (the inverse Edit): `        for key in ("headSha",):` back to `        for key in ("headSha", "headShaAfter", "treeSha", "treeShaAfter"):`. **Restore receipt:** the line is back as `        for key in ("headSha", "headShaAfter", "treeSha", "treeShaAfter"):`, and `git status --porcelain` listed no `.py` file outside `plugins/superheroes/lib/tests/`.

**Raw green** (the same node):

```
.                                                                        [100%]
1 passed in 0.88s
```

Not separately neutralized (unproven): each digest on its own (`treeSha`, `treeShaAfter`); the new node drops all three together, and only `headShaAfter` has a second node (A8).

## A8

**Neutralization:** `        for key in ("headSha", "headShaAfter", "treeSha", "treeShaAfter"):` became `        for key in ("headSha", "treeSha", "treeShaAfter"):` (`"headShaAfter"` dropped).

**Raw red** (`test_c1l10b_test_restore.py::test_t2_a_retry_pass_whose_head_moved_while_running_halts_through_the_run_loop_callback`):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_t2_a_retry_pass_whose_head_moved_while_running_halts_through_the_run_loop_callback _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-33/test_t2_a_retry_pass_whose_hea0')

    def test_t2_a_retry_pass_whose_head_moved_while_running_halts_through_the_run_loop_callback(tmp_path):
        # axis: the seam's after-head reaches the fold, so a passing retry that straddled a head change is not called unchanged code — see bite-proof record c1l11f_wo_e_verify_after_restore
        w = World(tmp_path, cap=2)
        moved_to = "f" * 40
        runs = []

        def fix_step(batch, rnd, payload):
            assert payload.get("restoreOnly"), "the run must halt at the verify gate, before any settle fix"
            w.write(TEST_PATH, payload["restores"][0]["content"])
            _commit(w.root, "restore")
            return {"fixes": []}

        def verify(command, rnd):
            head = _git(w.root, "rev-parse", "HEAD").strip()
            runs.append(head)
            if len(runs) == 1:
                return {"result": "fail", "headSha": head}
            return {"result": "pass", "headSha": head, "headShaAfter": moved_to}

        seams = TRD._seams(auditor=lambda targets, rnd: w.audit_artifact()["results"], fix_step=fix_step,
                           reviewer=lambda dim, tier, rnd, ctx: {"findings": [], "vendor": "codex"},
                           verify_runner=verify)
        seams["panel_diff"] = lambda config, head: (TRD.DIFF, None)
>       _receipt, state = w.run_loop(seams)
                          ^^^^^^^^^^^^^^^^^

/home/user/wo4/plugins/superheroes/lib/tests/test_c1l10b_test_restore.py:409: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/home/user/wo4/plugins/superheroes/lib/tests/test_c1l10b_test_restore.py:204: in run_loop
    return TRD._run_loop_capturing_state(seams, self.cfg)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/home/user/wo4/plugins/superheroes/lib/tests/test_round_driver.py:196: in _run_loop_capturing_state
    result = RD.run_loop(seams, config)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/home/user/wo4/plugins/superheroes/lib/round_driver.py:9914: in run_loop
    artifact = _run_seam(seams, action, step["payload"], state, state["config"])
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/home/user/wo4/plugins/superheroes/lib/round_driver.py:9697: in _run_seam
    return seams["fix_step"](payload.get("batch"), state["round"], payload)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

batch = [{'id': 'tests/test_charge.py::retry charges twice@L1', 'findingKey': 'tests/test_charge.py::retry charges twice@L1', 'identity': 'tests/test_charge.py::retry charges twice', 'file': 'tests/test_charge.py', ...}]
rnd = 2
payload = {'batch': [{'id': 'tests/test_charge.py::retry charges twice@L1', 'findingKey': 'tests/test_charge.py::retry charges t...::retry charges twice', 'file': 'tests/test_charge.py', ...}], 'startHead': '98c3e44a75f5f5767fb53ff803955422ad567364'}

    def fix_step(batch, rnd, payload):
>       assert payload.get("restoreOnly"), "the run must halt at the verify gate, before any settle fix"
E       AssertionError: the run must halt at the verify gate, before any settle fix
E       assert None
E        +  where None = <built-in method get of dict object at 0x7fd205c7dd80>('restoreOnly')
E        +    where <built-in method get of dict object at 0x7fd205c7dd80> = {'batch': [{'id': 'tests/test_charge.py::retry charges twice@L1', 'findingKey': 'tests/test_charge.py::retry charges t...::retry charges twice', 'file': 'tests/test_charge.py', ...}], 'startHead': '98c3e44a75f5f5767fb53ff803955422ad567364'}.get

/home/user/wo4/plugins/superheroes/lib/tests/test_c1l10b_test_restore.py:393: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l10b_test_restore.py::test_t2_a_retry_pass_whose_head_moved_while_running_halts_through_the_run_loop_callback
1 failed in 2.67s
```

The red is on the claimed axis, by its consequence: with the after-head dropped at the seam, the passing retry that straddled a head change is no longer refused, so the run goes on to the settle fix, which the test's own guard (`the run must halt at the verify gate, before any settle fix`) rejects. It is not an import error or an unrelated assertion; the `verify-rerun-head-moved` assertions after `run_loop` are not reached, so the red proves the run did not halt, not the recorded entry.

**Restore** (the inverse Edit): `        for key in ("headSha", "treeSha", "treeShaAfter"):` back to `        for key in ("headSha", "headShaAfter", "treeSha", "treeShaAfter"):`. **Restore receipt:** the line is back as `        for key in ("headSha", "headShaAfter", "treeSha", "treeShaAfter"):`, and `git status --porcelain` listed no `.py` file outside `plugins/superheroes/lib/tests/`.

**Raw green** (the same node):

```
.                                                                        [100%]
1 passed in 2.25s
```
