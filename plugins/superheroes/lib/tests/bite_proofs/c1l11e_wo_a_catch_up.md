# C1-L11e (WO-A) bite-proof — a stacked layer's handback refuses a head behind its lower layer, and a started review no longer refuses a moved lower layer; a returning round reads only the files the decider named as changed

**Provenance:** implementer WO-A2, recording the guards of WO-A (commit `f2a59ec3`, "wip(superheroes): C1-L11e WO-A …", which landed the code and tests and timed out before this record) on `lib/vet_slot.py` and `lib/round_driver.py`, proved by `lib/tests/test_c1l11e_catch_up.py` (issue #2277)

Declared guarded elements (from the order): G1 to G6 in the table below. The census (the Grep tool, pattern `c1l11e_wo_a_catch_up`, path `plugins/superheroes/lib`, glob `*.py`) printed these lines; the tool searches the directory recursively, so it also printed the lines in `lib/tests/test_c1l11e_catch_up.py`:

```
plugins/superheroes/lib/vet_slot.py:481:    # axis: a PR payload lacking base, base.repo or head as objects refuses stack-lower-unreadable — see bite-proof record c1l11e_wo_a_catch_up
plugins/superheroes/lib/vet_slot.py:487:    # axis: a base ref or default branch that is not a non-empty string refuses stack-lower-unreadable — see bite-proof record c1l11e_wo_a_catch_up
plugins/superheroes/lib/vet_slot.py:493:    # axis: a head sha that is not 40 hex characters refuses stack-lower-unreadable — see bite-proof record c1l11e_wo_a_catch_up
plugins/superheroes/lib/vet_slot.py:496:    # axis: a PR on the default branch is not stacked: no refusal and no compare read — see bite-proof record c1l11e_wo_a_catch_up
plugins/superheroes/lib/vet_slot.py:502:    # axis: a compare read that fails, times out, raises OSError or prints bad JSON refuses stack-lower-unreadable, original detail kept — see bite-proof record c1l11e_wo_a_catch_up
plugins/superheroes/lib/vet_slot.py:507:    # axis: a compare read that is not an object refuses stack-lower-unreadable — see bite-proof record c1l11e_wo_a_catch_up
plugins/superheroes/lib/vet_slot.py:511:    # axis: a behind_by that is missing, not an int, a bool or negative refuses stack-lower-unreadable — see bite-proof record c1l11e_wo_a_catch_up
plugins/superheroes/lib/vet_slot.py:514:    # axis: a head behind its lower branch refuses stack-not-caught-up — see bite-proof record c1l11e_wo_a_catch_up
plugins/superheroes/lib/round_driver.py:7330:        # axis: a returning round's surface holds only the files the decider named as changed, never a file whose only difference is a catch-up's index line — see bite-proof record c1l11e_wo_a_catch_up
plugins/superheroes/lib/tests/test_c1l11e_catch_up.py:19:Bite-proof record: c1l11e_wo_a_catch_up
plugins/superheroes/lib/tests/test_c1l11e_catch_up.py:168:    # axis: next on a started stacked session reads no remote head and refuses nothing for a moved lower layer — see bite-proof record c1l11e_wo_a_catch_up
plugins/superheroes/lib/tests/test_c1l11e_catch_up.py:277:    # axis: behind_by > 0 refuses stack-not-caught-up, naming the head, the count, the lower branch and the catch-up step — see bite-proof record c1l11e_wo_a_catch_up
plugins/superheroes/lib/tests/test_c1l11e_catch_up.py:396:    # axis: e1 — base, base.repo or head missing or not a dict refuses stack-lower-unreadable, with no compare read — see bite-proof record c1l11e_wo_a_catch_up
plugins/superheroes/lib/tests/test_c1l11e_catch_up.py:405:    # axis: e2 — base.ref or default_branch not a non-empty string refuses stack-lower-unreadable, with no compare read — see bite-proof record c1l11e_wo_a_catch_up
plugins/superheroes/lib/tests/test_c1l11e_catch_up.py:414:    # axis: e3 — head.sha not 40 hex characters refuses stack-lower-unreadable, with no compare read — see bite-proof record c1l11e_wo_a_catch_up
plugins/superheroes/lib/tests/test_c1l11e_catch_up.py:442:    # axis: e4 — the compare gh call fails, times out, raises OSError, or prints JSON that is bad or not an object: refuses stack-lower-unreadable with the original detail — see bite-proof record c1l11e_wo_a_catch_up
plugins/superheroes/lib/tests/test_c1l11e_catch_up.py:454:    # axis: e5 — behind_by missing, not an int, a bool, or negative refuses stack-lower-unreadable, never a pass — see bite-proof record c1l11e_wo_a_catch_up
plugins/superheroes/lib/tests/test_c1l11e_catch_up.py:486:    # axis: the returning round's surface holds only the files the decider named as changed; a catch-up's index line is not content — see bite-proof record c1l11e_wo_a_catch_up
plugins/superheroes/lib/tests/test_c1l11e_catch_up.py:517:    # axis: only=set skips every file not in it (no surface entry, no text); only=None is today's compare of raw sections — see bite-proof record c1l11e_wo_a_catch_up
plugins/superheroes/lib/tests/test_c1l11e_catch_up.py:532:    # axis: _returning_surface passes only=set(changedFiles) when the decider's list is all strings, and no filter otherwise — see bite-proof record c1l11e_wo_a_catch_up
plugins/superheroes/lib/tests/test_c1l11e_catch_up.py:576:    # axis: a carried check made at the caught-up head moves a fixed finding to fixed and names that head — see bite-proof record c1l11e_wo_a_catch_up
```

Each element was neutralized with one targeted Edit (the Edit tool) and restored with the inverse Edit; no `git checkout`, `restore`, `reset` or `stash` was used, and no shell command edited a file. Run from `/home/user/wt-2277-a` on head `f2a59ec3` under `timeout 600 scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-2277a2 -m pytest "<node id>" -q -p no:cacheprovider`. Each capture is the runner's whole output for that run apart from the `UV_NATIVE_TLS` deprecation warning line (the first line of each real output), which is left out; nothing else is trimmed. Each capture ends with an `exit=N` line: that is the shell's echo of the runner's exit status, appended to the command by the implementer, not runner output. Nothing is redacted: no secrets, tokens or URLs appear (the `/tmp/claude-0/...` paths are pytest temp directories; the branch name `claude/issue-2273-workhorse-xvcoga` in G3's capture is a test fixture's branch name). The restore receipt of each element is the restored line quoted back at its line number, read after the restore (G6: the two adjacent lines).

Line numbers are those of the tree at the time of the runs, which is the restored tree (the neutralizations changed no line count except G4 and G6, which were undone before the next element began).

| ID | Guarded element | Axis | Proving test (node id, in `plugins/superheroes/lib/tests/test_c1l11e_catch_up.py`) |
|---|---|---|---|
| G1 | `vet_slot.check_caught_up`, the `if behind > 0:` refusal (`vet_slot.py:515`) | a head behind its lower branch refuses `stack-not-caught-up` | `test_a_head_behind_its_lower_branch_refuses_stack_not_caught_up` |
| G2 | `vet_slot.check_caught_up`, the `behind_by` count test (`vet_slot.py:512`), its `or behind < 0` leg | a negative `behind_by` is not a count and refuses `stack-lower-unreadable` | `test_e5_a_behind_by_that_is_not_a_count_refuses_unreadable[negative]` |
| G3 | `vet_slot.check_caught_up`, the `except _Refusal` around the compare read (`vet_slot.py:505`, raising at `:506`) | a failed compare read refuses `stack-lower-unreadable`, not the read's own `read-failed` | `test_e4_a_compare_read_that_fails_or_is_not_an_object_refuses_unreadable[exit-nonzero]` |
| G4 | `vet_slot._run_verb`, the `check_caught_up(run, repo, payload)` call in the handback branch (`vet_slot.py:579`) | the CLI handback on a PR runs the catch-up check and exits 1 on a refusal | `test_cli_handback_on_a_pr_exits_one_when_the_head_is_behind` |
| G5 | `round_driver._fix_delta_surface`, the `if only is not None and file not in only: continue` filter (`round_driver.py:7331`) | a returning round's surface holds only the files the decider named as changed | `test_a_catch_up_over_a_file_the_layer_also_changes_converges_in_round_one_with_nothing_read` |
| G6 | `round_driver._dispatch`, the `next` branch: no stack refusal after the `check_base` refusal (`round_driver.py:16125` and `:16126`) | `next` on a started stacked session refuses nothing for a moved lower layer | `test_cli_next_after_the_lower_layer_moves_runs_on_the_pinned_commit` |

Every red is the runner's own failure of the unedited test, caused by the neutralization alone. G6 is a removal guard: its neutralization is an insertion (see its section).

Not separately neutralized (the unproven part of this record): each of these is covered by its test passing at the base, but is not separately shown red here.

- `check_caught_up` e1 (`vet_slot.py:481`, the payload-lacks-base-base.repo-or-head test), e2 (`:487`, the base ref or default branch is a non-empty string test) and e3 (`:493`, the head sha is 40 hex characters test): covered by `test_e1_…`, `test_e2_…` and `test_e3_…`, none run under a neutralization.
- The not-an-object leg (`vet_slot.py:507`, `if not isinstance(compare, dict):`): covered by the `E4` cases of `test_e4_…` whose compare read is JSON that is not an object; not run under a neutralization. G3's one case (`exit-nonzero`) shows the `except _Refusal` translation only; the other `E4` cases (timeout, `OSError`, bad JSON, not an object) are not shown red.
- The other legs of the `behind_by` count test (`vet_slot.py:512`): `not isinstance(behind, int)` (covers missing and non-int) and `isinstance(behind, bool)`; only the `behind < 0` leg is shown (G2). The `E5` cases `missing`, the non-int cases and `bool` are not shown red.
- The default-branch short-circuit (`vet_slot.py:496-498`, `if base_ref == default_branch: return None`): covered by `test_a_pr_on_the_default_branch_is_not_stacked_and_makes_no_compare_read`; not run under a neutralization.
- G3: the translation is neutralized by a bare `raise` (the order's neutralization); the `except _Refusal` clause itself and the original detail being kept (`exc.detail`) are shown only through the case named; the detail assertion is part of that test's later lines, which the red does not reach (it fails at the reason).
- G1 to G4: the `_HEAD_SHA_RE` pattern and the `urllib.parse.quote` of the lower branch (`test_the_lower_branch_is_quoted_into_the_compare_path_but_slashes_stay`) are not neutralized.
- `round_driver.py`: the call that hands `only=set(changedFiles)` to `_fix_delta_surface` from `_returning_surface` (`test_a_returning_surface_is_filtered_by_the_deciders_changed_files_only_when_it_is_a_list_of_strings`, test axis line 532) and the fix-delta test (`test_the_fix_delta_surface_keeps_out_every_file_outside_only`, line 517) are covered by their tests; neither was run under a neutralization. G5 shows the filter inside `_fix_delta_surface` only, through the end-to-end round.
- The carried-check test (`test_a_still_open_finding_is_rechecked_against_the_caught_up_head`, test axis line 576) is covered by its test and not neutralized: its guarded code carries no axis line in the census above.
- G6's companions, `test_cli_submit_after_…` and `test_cli_advance_after_…`, and `test_cli_next_never_reads_the_lower_branch_on_origin`, `test_the_stack_lower_refusals_and_their_names_are_gone` and `test_fresh_next_on_a_layer_that_lacks_the_lower_head_creates_state_normally`, are not run under a neutralization.

---

## G1 — the `behind > 0` refusal

**axis:** a head behind its lower branch refuses `stack-not-caught-up`.

**neutralization** (`vet_slot.py:515`, `check_caught_up`: the refusal never taken):
```python
-    if behind > 0:
+    if False:
```

**raw red:** `timeout 600 scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-2277a2 -m pytest "plugins/superheroes/lib/tests/test_c1l11e_catch_up.py::test_a_head_behind_its_lower_branch_refuses_stack_not_caught_up" -q -p no:cacheprovider` — exit 1
```
F                                                                        [100%]
=================================== FAILURES ===================================
_______ test_a_head_behind_its_lower_branch_refuses_stack_not_caught_up ________

    def test_a_head_behind_its_lower_branch_refuses_stack_not_caught_up():
        # axis: behind_by > 0 refuses stack-not-caught-up, naming the head, the count, the lower branch and the catch-up step — see bite-proof record c1l11e_wo_a_catch_up
        result, fake = _handback(_payload(), _compare(2))
>       assert result["ok"] is False and result["reason"] == "stack-not-caught-up" == VS.REASON_STACK_NOT_CAUGHT_UP
E       assert (True is False)

/home/user/wt-2277-a/plugins/superheroes/lib/tests/test_c1l11e_catch_up.py:279: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l11e_catch_up.py::test_a_head_behind_its_lower_branch_refuses_stack_not_caught_up
1 failed in 2.03s
exit=1
```
The red is on the axis: a handback on a head two commits behind its lower branch is let through (`ok` is True) where the test requires the `stack-not-caught-up` refusal.

**restore:** the inverse Edit.

**restore receipt** (`vet_slot.py:514-515`):
```python
    # axis: a head behind its lower branch refuses stack-not-caught-up — see bite-proof record c1l11e_wo_a_catch_up
    if behind > 0:
```

**raw green:** same command — exit 0
```
.                                                                        [100%]
1 passed in 2.13s
exit=0
```

---

## G2 — the `behind_by` count test, negative leg

**axis:** a negative `behind_by` is not a count and refuses `stack-lower-unreadable`, never a pass.

**neutralization** (`vet_slot.py:512`, `check_caught_up`: the `or behind < 0` leg dropped):
```python
-    if not isinstance(behind, int) or isinstance(behind, bool) or behind < 0:
+    if not isinstance(behind, int) or isinstance(behind, bool):
```

**raw red:** `... -m pytest "plugins/superheroes/lib/tests/test_c1l11e_catch_up.py::test_e5_a_behind_by_that_is_not_a_count_refuses_unreadable[negative]" -q -p no:cacheprovider` — exit 1
```
F                                                                        [100%]
=================================== FAILURES ===================================
_____ test_e5_a_behind_by_that_is_not_a_count_refuses_unreadable[negative] _____

name = 'negative', behind = -1

    @pytest.mark.parametrize("name,behind", E5, ids=[n for n, _ in E5])
    def test_e5_a_behind_by_that_is_not_a_count_refuses_unreadable(name, behind):
        # axis: e5 — behind_by missing, not an int, a bool, or negative refuses stack-lower-unreadable, never a pass — see bite-proof record c1l11e_wo_a_catch_up
        row = {"status": "identical", "ahead_by": 0}
        if name != "missing":
            row["behind_by"] = behind
>       _unreadable(_payload(), _out(json.dumps(row)))

/home/user/wt-2277-a/plugins/superheroes/lib/tests/test_c1l11e_catch_up.py:458: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

payload = {'number': 7, 'body': '## Advisor vet\n<!-- superheroes:advisor-vet -->\nold slot text\n\n<!-- superheroes:build-recor...73-workhorse-xvcoga', 'repo': {'default_branch': 'main'}}, 'head': {'sha': '5d3e97c07a92d74a015dd498ae7834ffc374f6f1'}}
compare = <function _out.<locals>.<lambda> at 0x7fe07ec4c540>

    def _unreadable(payload, compare=None):
        result, fake = _handback(payload, compare)
>       assert result["ok"] is False and result["reason"] == "stack-lower-unreadable" == VS.REASON_STACK_LOWER_UNREADABLE, result
E       AssertionError: {'ok': True, 'verb': 'handback', 'followups': ['FU1', 'FU2']}
E       assert (True is False)

/home/user/wt-2277-a/plugins/superheroes/lib/tests/test_c1l11e_catch_up.py:390: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l11e_catch_up.py::test_e5_a_behind_by_that_is_not_a_count_refuses_unreadable[negative]
1 failed in 6.55s
exit=1
```
The red is on the axis: a `behind_by` of -1 passes the handback (`ok` is True) where the test requires the `stack-lower-unreadable` refusal.

**restore:** the inverse Edit.

**restore receipt** (`vet_slot.py:511-512`):
```python
    # axis: a behind_by that is missing, not an int, a bool or negative refuses stack-lower-unreadable — see bite-proof record c1l11e_wo_a_catch_up
    if not isinstance(behind, int) or isinstance(behind, bool) or behind < 0:
```

**raw green:** same command — exit 0
```
.                                                                        [100%]
1 passed in 1.73s
exit=0
```

---

## G3 — the compare-read failure translation

**axis:** a compare read that fails refuses `stack-lower-unreadable`, with the read's original detail, not the read's own `read-failed` reason.

**neutralization** (`vet_slot.py:506`, `check_caught_up`: the translated refusal replaced by a bare `raise`, which re-raises the read's own `read-failed`):
```python
-        raise unreadable(exc.detail)
+        raise
```

**raw red:** `... -m pytest "plugins/superheroes/lib/tests/test_c1l11e_catch_up.py::test_e4_a_compare_read_that_fails_or_is_not_an_object_refuses_unreadable[exit-nonzero]" -q -p no:cacheprovider` — exit 1
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_e4_a_compare_read_that_fails_or_is_not_an_object_refuses_unreadable[exit-nonzero] _

name = 'exit-nonzero'
compare = <function _out.<locals>.<lambda> at 0x7fbd6fe65e40>
detail = 'boom: HTTP 404'

    @pytest.mark.parametrize("name,compare,detail", E4, ids=[n for n, _c, _d in E4])
    def test_e4_a_compare_read_that_fails_or_is_not_an_object_refuses_unreadable(name, compare, detail):
        # axis: e4 — the compare gh call fails, times out, raises OSError, or prints JSON that is bad or not an object: refuses stack-lower-unreadable with the original detail — see bite-proof record c1l11e_wo_a_catch_up
>       result, fake = _unreadable(_payload(), compare)
                       ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

/home/user/wt-2277-a/plugins/superheroes/lib/tests/test_c1l11e_catch_up.py:443: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

payload = {'number': 7, 'body': '## Advisor vet\n<!-- superheroes:advisor-vet -->\nold slot text\n\n<!-- superheroes:build-recor...73-workhorse-xvcoga', 'repo': {'default_branch': 'main'}}, 'head': {'sha': '5d3e97c07a92d74a015dd498ae7834ffc374f6f1'}}
compare = <function _out.<locals>.<lambda> at 0x7fbd6fe65e40>

    def _unreadable(payload, compare=None):
        result, fake = _handback(payload, compare)
>       assert result["ok"] is False and result["reason"] == "stack-lower-unreadable" == VS.REASON_STACK_LOWER_UNREADABLE, result
E       AssertionError: {'ok': False, 'reason': 'read-failed', 'detail': 'compare claude/issue-2273-workhorse-xvcoga...5d3e97c07a92: exit 1 boom: HTTP 404'}
E       assert (False is False and 'read-failed' == 'stack-lower-unreadable'
E         
E         - stack-lower-unreadable
E         + read-failed)

/home/user/wt-2277-a/plugins/superheroes/lib/tests/test_c1l11e_catch_up.py:390: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l11e_catch_up.py::test_e4_a_compare_read_that_fails_or_is_not_an_object_refuses_unreadable[exit-nonzero]
1 failed in 1.90s
exit=1
```
The red is on the axis: the failed compare read refuses, but with the reason `read-failed` where the test requires `stack-lower-unreadable`. (The carets under `_unreadable(` in the capture are exactly as the runner printed them.)

**restore:** the inverse Edit.

**restore receipt** (`vet_slot.py:503-506`):
```python
    try:
        compare = _gh_json(run, argv, what)
    except _Refusal as exc:
        raise unreadable(exc.detail)
```

**raw green:** same command — exit 0
```
.                                                                        [100%]
1 passed in 2.02s
exit=0
```

---

## G4 — the handback branch's `check_caught_up` call

**axis:** the CLI handback on a PR runs the catch-up check and exits 1 on a refusal (the break-it: a ready marking let through on a head behind its lower layer).

**neutralization** (`vet_slot.py:579`, `_run_verb`: the call removed):
```python
     if verb == "handback":
-        check_caught_up(run, repo, payload)
         return check_handback(_body_of(payload))
```

**raw red:** `... -m pytest "plugins/superheroes/lib/tests/test_c1l11e_catch_up.py::test_cli_handback_on_a_pr_exits_one_when_the_head_is_behind" -q -p no:cacheprovider` — exit 1
```
F                                                                        [100%]
=================================== FAILURES ===================================
_________ test_cli_handback_on_a_pr_exits_one_when_the_head_is_behind __________

capsys = <_pytest.capture.CaptureFixture object at 0x7f116f6fc710>

    def test_cli_handback_on_a_pr_exits_one_when_the_head_is_behind(capsys):
        # axis: the CLI handback --pr --repo runs the catch-up check and exits 1 on a refusal
>       assert VS.main(["handback", "--pr", str(PR), "--repo", REPO], run=FakeGh(_payload(), _compare(2))) == 1
E       AssertionError: assert 0 == 1
E        +  where 0 = <function main at 0x7f116f113ec0>(['handback', '--pr', '7', '--repo', 'o/r'], run=<test_c1l11e_catch_up.FakeGh object at 0x7f116f6f74a0>)
E        +    where <function main at 0x7f116f113ec0> = VS.main
E        +    and   <test_c1l11e_catch_up.FakeGh object at 0x7f116f6f74a0> = FakeGh({'number': 7, 'body': '## Advisor vet\n<!-- superheroes:advisor-vet -->\nold slot text\n\n<!-- superheroes:build-recor...73-workhorse-xvcoga', 'repo': {'default_branch': 'main'}}, 'head': {'sha': '5d3e97c07a92d74a015dd498ae7834ffc374f6f1'}}, <function _compare.<locals>.<lambda> at 0x7f116f0dbba0>)
E        +      where {'number': 7, 'body': '## Advisor vet\n<!-- superheroes:advisor-vet -->\nold slot text\n\n<!-- superheroes:build-recor...73-workhorse-xvcoga', 'repo': {'default_branch': 'main'}}, 'head': {'sha': '5d3e97c07a92d74a015dd498ae7834ffc374f6f1'}} = _payload()
E        +      and   <function _compare.<locals>.<lambda> at 0x7f116f0dbba0> = _compare(2)

/home/user/wt-2277-a/plugins/superheroes/lib/tests/test_c1l11e_catch_up.py:334: AssertionError
----------------------------- Captured stdout call -----------------------------
{"ok": true, "verb": "handback", "followups": ["FU1", "FU2"]}
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l11e_catch_up.py::test_cli_handback_on_a_pr_exits_one_when_the_head_is_behind
1 failed in 1.95s
exit=1
```
The red is on the axis: the handback on a head two commits behind its lower branch prints `"ok": true` and exits 0 where the test requires exit 1.

**restore:** the inverse Edit.

**restore receipt** (`vet_slot.py:578-580`):
```python
    if verb == "handback":
        check_caught_up(run, repo, payload)
        return check_handback(_body_of(payload))
```

**raw green:** same command — exit 0
```
.                                                                        [100%]
1 passed in 2.11s
exit=0
```

---

## G5 — the returning surface's `only` filter

**axis:** a returning round's surface holds only the files the decider named as changed, never a file whose only difference is a catch-up's index line.

**neutralization** (`round_driver.py:7331`, `_fix_delta_surface`: the filter never skips a file):
```python
-        if only is not None and file not in only:
+        if False:
             continue
```

**raw red:** `... -m pytest "plugins/superheroes/lib/tests/test_c1l11e_catch_up.py::test_a_catch_up_over_a_file_the_layer_also_changes_converges_in_round_one_with_nothing_read" -q -p no:cacheprovider` — exit 1
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_catch_up_over_a_file_the_layer_also_changes_converges_in_round_one_with_nothing_read _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-37/test_a_catch_up_over_a_file_th0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7faa8607eba0>

    def test_a_catch_up_over_a_file_the_layer_also_changes_converges_in_round_one_with_nothing_read(tmp_path, monkeypatch):
        # axis: the returning round's surface holds only the files the decider named as changed; a catch-up's index line is not content — see bite-proof record c1l11e_wo_a_catch_up
        s = _caught_up_session(tmp_path, monkeypatch)
>       state = _converged(s)
                ^^^^^^^^^^^^^

/home/user/wt-2277-a/plugins/superheroes/lib/tests/test_c1l11e_catch_up.py:488: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

s = <test_c1l11b_returning_session.Session object at 0x7faa85eda210>

    def _converged(s):
        answer = s.next()
>       assert answer["action"] == RD.P_TERMINAL and answer["payload"]["verdict"] == "converged", answer
E       AssertionError: {'ok': True, 'action': 'dispatch-scoped-finder', 'round': 1, 'phase': 'dispatch-scoped-finder', ...}
E       assert ('dispatch-scoped-finder' == 'terminal'
E         
E         - terminal
E         + dispatch-scoped-finder)

/home/user/wt-2277-a/plugins/superheroes/lib/tests/test_c1l11e_catch_up.py:481: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l11e_catch_up.py::test_a_catch_up_over_a_file_the_layer_also_changes_converges_in_round_one_with_nothing_read
1 failed in 1.99s
exit=1
```
The red is on the axis: with the filter gone, the shared file (changed only by the catch-up's index line) reaches the surface, so the round dispatches a finder (`dispatch-scoped-finder`) where the test requires round one to converge with nothing read.

**restore:** the inverse Edit.

**restore receipt** (`round_driver.py:7330-7332`):
```python
        # axis: a returning round's surface holds only the files the decider named as changed, never a file whose only difference is a catch-up's index line — see bite-proof record c1l11e_wo_a_catch_up
        if only is not None and file not in only:
            continue
```

**raw green:** same command — exit 0
```
.                                                                        [100%]
1 passed in 2.18s
exit=0
```

---

## G6 — no stack refusal on `next` after `check_base`

**axis:** `next` on a started stacked session reads no remote head and refuses nothing for a moved lower layer. G6 guards a removal: the shipped code has no refusal there, so the neutralization re-inserts one, the red is the proving test failing because the session is refused again, and the restore deletes the inserted line.

**neutralization** (`round_driver.py`, `_dispatch`, the `next` branch: one line inserted between the `check_base` refusal line (16125) and the `if fresh:` line (16126 before the insertion)):
```python
                 return _refuse_base_guard(args.session_dir, guard["reason"], guard.get("detail"))
+            if (review_base_guard.read_meta(args.session_dir)[1] or {}).get("stackLower") is True: return _refuse_base_guard(args.session_dir, "stack-lower-moved")
             if fresh:
```

**raw red:** `... -m pytest "plugins/superheroes/lib/tests/test_c1l11e_catch_up.py::test_cli_next_after_the_lower_layer_moves_runs_on_the_pinned_commit" -q -p no:cacheprovider` — exit 1
```
F                                                                        [100%]
=================================== FAILURES ===================================
_____ test_cli_next_after_the_lower_layer_moves_runs_on_the_pinned_commit ______

stack = <test_c1l11e_catch_up.Stack object at 0x7f19452d0320>
capsys = <_pytest.capture.CaptureFixture object at 0x7f19452c9c70>

    def test_cli_next_after_the_lower_layer_moves_runs_on_the_pinned_commit(stack, capsys):
        # axis: next on a started stacked session reads no remote head and refuses nothing for a moved lower layer — see bite-proof record c1l11e_wo_a_catch_up
>       sd = _started(stack, capsys)
             ^^^^^^^^^^^^^^^^^^^^^^^

/home/user/wt-2277-a/plugins/superheroes/lib/tests/test_c1l11e_catch_up.py:169: 

stack = <test_c1l11e_catch_up.Stack object at 0x7f19452d0320>
capsys = <_pytest.capture.CaptureFixture object at 0x7f19452c9c70>

    def _started(stack, capsys):
        sd = stack.session()
        rc, _ = _run(["next", "--session-dir", sd, "--repo-root", stack.repo,
                      "--diff-path", stack.round_diff(sd)], capsys)
>       assert rc == 0
E       assert 1 == 0

/home/user/wt-2277-a/plugins/superheroes/lib/tests/test_c1l11e_catch_up.py:144: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l11e_catch_up.py::test_cli_next_after_the_lower_layer_moves_runs_on_the_pinned_commit
1 failed in 2.15s
exit=1
```
What the red shows, and what it does not: the inserted refusal makes `next` exit 1 on the test's session, whose `meta.json` carries `stackLower: true` (the fixture at test file line 106-110 writes the meta as review-code Setup wrote it before this change), so the test fails at its first `next` (the `_started` helper, `assert rc == 0`) rather than at the later `next` after the lower layer moves. The runner's output does not print the refusal token, so that the exit-1 is the `stack-lower-moved` refusal is inferred from the insertion being the only change and the only refusal the insertion can raise, not read from the capture.

**restore:** the inverse Edit, deleting the inserted line.

**restore receipt** (`round_driver.py:16125-16126`: the `check_base` refusal line and the line after it, adjacent again):
```python
16125:                return _refuse_base_guard(args.session_dir, guard["reason"], guard.get("detail"))
16126:            if fresh:
```

**raw green:** same command — exit 0
```
.                                                                        [100%]
1 passed in 2.74s
exit=0
```
