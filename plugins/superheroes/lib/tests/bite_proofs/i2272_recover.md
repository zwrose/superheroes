# #2272 WO2 bite-proofs — recovery: the account limit as stop evidence, work-order branches, the helper read

Detector file: `plugins/superheroes/lib/tests/test_i2272_recover.py`. Production file neutralized: `plugins/superheroes/lib/cloud_recover.py`.
Every neutralization is a targeted edit of one production line (or one inserted block), undone by the inverse edit; no
`git checkout`, `git restore`, `git reset` or `git stash` was used. Command prefix for every run below
(run from the worktree root; `$T` stands for `plugins/superheroes/lib/tests/test_i2272_recover.py`):

```
scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest "$T::<node>" -q -p no:randomly
```

Captures are pasted as the runs printed them; the pytest `w = namespace(...)` lines are pytest's own truncation of the
fixture repr. The one `UV_NATIVE_TLS` warning line the wrapper prints is kept in the first capture and omitted from the
rest. Nothing in the captures is secret; the tmp paths are the sandbox's.

## (a) `limited is True` in `_limit_reading` — axis: a lapsed limit stops nothing

**Guarded element:** `cloud_recover.py:402` `reading.get("limited") is True`.

**Neutralization:** `reading.get("ok") is True and reading.get("limited") is True` became `reading.get("ok") is True`.

**Detector:** `test_2_a_limit_that_has_lapsed_is_not_stop_evidence_and_withdraws_an_earlier_stop`

**Red:**
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_2_a_limit_that_has_lapsed_is_not_stop_evidence_and_withdraws_an_earlier_stop _

w = namespace(root='/tmp/claude-0/pytest-of-root/pytest-21/test_2_a_limit_that_has_lapsed0/advisor', builder='/tmp/claude-...at_has_lapsed0'), gh=<test_cloud_recover.Gh object at 0x7faa1ae64740>, base='37462a1fecc7f855163bcb3201d54612aa20ebd9')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7faa1aef7560>

    def test_2_a_limit_that_has_lapsed_is_not_stop_evidence_and_withdraws_an_earlier_stop(w, monkeypatch):
        _lane(w, "l1")
        _limit(monkeypatch, _reading())
        assert _assess(w, state="unread")["verdict"] == "stopped"
        _limit(monkeypatch, _reading(limited=False))
        out = _assess(w, state="unread")
>       assert (out["verdict"], out["evidence"]) == ("unresolved", "session-unread")
E       AssertionError: assert ('stopped', 'account-limited') == ('unresolved'...ssion-unread')
E         
E         At index 0 diff: 'stopped' != 'unresolved'
E         Use -v to get more diff

/home/user/wt-2272-wo2/plugins/superheroes/lib/tests/test_i2272_recover.py:127: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_i2272_recover.py::test_2_a_limit_that_has_lapsed_is_not_stop_evidence_and_withdraws_an_earlier_stop
1 failed in 1.49s
```

**Restore:** inverse edit, `reading.get("ok") is True` back to `reading.get("ok") is True and reading.get("limited") is True`.
**Restore receipt:** `grep -n 'reading.get("limited") is True'` printed `402:    if (isinstance(reading, dict) and reading.get("ok") is True and reading.get("limited") is True`.

**Green:**
```
.                                                                        [100%]
1 passed in 1.46s
```

## (b) `start < recorded` in `_limit_reading` — axis: a lane launched after the limit was recorded is not stopped by it

**Guarded element:** `cloud_recover.py:403` `start < recorded`.

**Neutralization:** `and _is_number(start) and _is_number(recorded) and start < recorded):` became `and _is_number(start) and _is_number(recorded)):`.

**Detector:** `test_2_a_limit_recorded_before_the_lane_started_is_not_stop_evidence`

**Red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_____ test_2_a_limit_recorded_before_the_lane_started_is_not_stop_evidence _____

w = namespace(root='/tmp/claude-0/pytest-of-root/pytest-27/test_2_a_limit_recorded_before0/advisor', builder='/tmp/claude-...corded_before0'), gh=<test_cloud_recover.Gh object at 0x7f0262ef2180>, base='1069083618afee803034ead9fdaf38702cc289c4')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7f0261d3f710>

    def test_2_a_limit_recorded_before_the_lane_started_is_not_stop_evidence(w, monkeypatch):
        _lane(w, "l1", start_age=7200)
        _limit(monkeypatch, _reading(recorded_ago=9000))
        out = _assess(w, state="unread")
>       assert (out["verdict"], out["evidence"]) == ("unresolved", "session-unread")
E       AssertionError: assert ('stopped', 'account-limited') == ('unresolved'...ssion-unread')
E         
E         At index 0 diff: 'stopped' != 'unresolved'
E         Use -v to get more diff

/home/user/wt-2272-wo2/plugins/superheroes/lib/tests/test_i2272_recover.py:135: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_i2272_recover.py::test_2_a_limit_recorded_before_the_lane_started_is_not_stop_evidence
1 failed in 1.09s
```

**Restore:** inverse edit.
**Restore receipt:** `grep -n 'start < recorded'` printed `403:            and _is_number(start) and _is_number(recorded) and start < recorded):`.

**Green:**
```
.                                                                        [100%]
1 passed in 1.09s
```

## (c) placement after the parked leg — axis: a parked lane is never recovered, whatever the account's limit says

**Guarded element:** the position of the `account-limited` leg in `assess`'s `if/elif` chain, after the `parkComment` leg.

**Neutralization:** a copy of the leg (`elif (limit := _limit_reading(...)) is not None:` plus its two body lines) inserted directly above
`elif out["parkComment"] is not None:`; the original leg below it was left in place (it is unreachable behind the copy, so the
chain reads as the leg moved above the parked leg).

**Detector:** `test_2_a_builder_park_newer_than_the_pushed_work_is_parked_whatever_the_limit`

**Red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_2_a_builder_park_newer_than_the_pushed_work_is_parked_whatever_the_limit _

w = namespace(root='/tmp/claude-0/pytest-of-root/pytest-33/test_2_a_builder_park_newer_th0/advisor', builder='/tmp/claude-...park_newer_th0'), gh=<test_cloud_recover.Gh object at 0x7fb17abd3f20>, base='bc27d0f9d1d7c6b417a3b6312e729858a14f5f03')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7fb17a3e0da0>

    def test_2_a_builder_park_newer_than_the_pushed_work_is_parked_whatever_the_limit(w, monkeypatch):
        _lane(w, "l1")
        _pushed_at(w, 1500)
        w.gh.comments = [_comment(PARK, age=600, cid=12)]
        _limit(monkeypatch, _reading())
        out = _assess(w, state="idle")
>       assert (out["verdict"], out["evidence"]) == ("parked", "builder-park")
E       AssertionError: assert ('stopped', 'account-limited') == ('parked', 'builder-park')
E         
E         At index 0 diff: 'stopped' != 'parked'
E         Use -v to get more diff

/home/user/wt-2272-wo2/plugins/superheroes/lib/tests/test_i2272_recover.py:168: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_i2272_recover.py::test_2_a_builder_park_newer_than_the_pushed_work_is_parked_whatever_the_limit
1 failed in 1.82s
```

**Restore:** inverse edit removed the inserted copy (4 lines, including the `BITE-PROOF (c) NEUTRALIZATION` marker comment).
**Restore receipt:** `grep -n "_limit_reading("` printed two lines, the `def` (393) and the single `elif` (471); lines 458-476 read back in the
original order: `fresh`, `parkComment`, `_STOP_STATES`, `handover`, the account-limit leg, `unread`.

**Green:**
```
.                                                                        [100%]
1 passed in 1.78s
```

## (d) the containment rule that passes over a contained branch — axis: the lane's own branch is adopted when it contains the others

**Guarded element:** `cloud_recover.py:596` `if not all(_contained(repo_root, b, primary, env, run) for b in others):` returning the primary.

**Neutralization:** that line became `if others:` (any other branch refuses, even a contained one).

**Detector:** `test_3a_the_lanes_branch_with_a_pull_request_is_adopted_and_the_contained_work_order_branch_passed_over`

**Red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_3a_the_lanes_branch_with_a_pull_request_is_adopted_and_the_contained_work_order_branch_passed_over _

w = namespace(root='/tmp/claude-0/pytest-of-root/pytest-39/test_3a_the_lanes_branch_with_0/advisor', builder='/tmp/claude-..._branch_with_0'), gh=<test_cloud_recover.Gh object at 0x7f949ebc6600>, base='8e7ec33be733da4bb00fc264b854f5bddabc6f17')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7f949e3f2b70>

    def test_3a_the_lanes_branch_with_a_pull_request_is_adopted_and_the_contained_work_order_branch_passed_over(w, monkeypatch):
        wo, head = _contained_pair(w)
        _stopped(w, monkeypatch, premise=_no_stack(w))
        run = _runner(w, pulls={LANE: [5]})
        got = CR.successor(w.root, "l1", repo=REPO, run=run)
>       assert got["ok"] is True and got["branch"] == LANE and got["sha"] == head
E       assert (False is True)

/home/user/wt-2272-wo2/plugins/superheroes/lib/tests/test_i2272_recover.py:314: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_i2272_recover.py::test_3a_the_lanes_branch_with_a_pull_request_is_adopted_and_the_contained_work_order_branch_passed_over
1 failed in 1.71s
```

**Restore:** inverse edit.
**Restore receipt:** `grep -n "if not all(_contained"` printed `596:        if not all(_contained(repo_root, b, primary, env, run) for b in others):`.

**Green:**
```
.                                                                        [100%]
1 passed in 1.50s
```

## (e) the diverged / ahead refusal — axis: a branch holding work the lane's own lacks is never passed over

**Guarded element:** the same line, `cloud_recover.py:596`, read for its refusal: a branch whose head the primary does not contain.

**Neutralization:** that line became `if False:` (every other branch is passed over, contained or not).

**Detectors (two nodes, one invocation):** `test_3b_a_work_order_branch_with_work_found_nowhere_else_refuses` and
`test_3b2_a_work_order_branch_strictly_ahead_of_the_lanes_branch_refuses`.

**Red** (INCOMPLETE: I piped this run through `tail -40`, so the top of the 3b failure block is lost; what follows is the last 40 lines
the run printed, not the whole output; both tests are named in the short summary and the count line):
```
E         
E         ...Full output truncated, use '-vv' to show

/home/user/wt-2272-wo2/plugins/superheroes/lib/tests/test_i2272_recover.py:305: AssertionError
___ test_3b2_a_work_order_branch_strictly_ahead_of_the_lanes_branch_refuses ____

w = namespace(root='/tmp/claude-0/pytest-of-root/pytest-45/test_3b2_a_work_order_branch_s0/advisor', builder='/tmp/claude-...rder_branch_s0'), gh=<test_cloud_recover.Gh object at 0x7f60a5e23530>, base='5769b97fc99b934f6331f2a215453112a964f11e')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7f60a5a6fe60>

    def test_3b2_a_work_order_branch_strictly_ahead_of_the_lanes_branch_refuses(w, monkeypatch):
        head = _commit_branch(w, LANE, w.base, "a")
        _commit_branch(w, WO, head, "b")
        _stopped(w, monkeypatch, premise=_no_stack(w))
>       _refused(w, _runner(w, pulls={LANE: [5]}))

/home/user/wt-2272-wo2/plugins/superheroes/lib/tests/test_i2272_recover.py:343: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

w = namespace(root='/tmp/claude-0/pytest-of-root/pytest-45/test_3b2_a_work_order_branch_s0/advisor', builder='/tmp/claude-...rder_branch_s0'), gh=<test_cloud_recover.Gh object at 0x7f60a5e23530>, base='5769b97fc99b934f6331f2a215453112a964f11e')
run = <function _runner.<locals>.run at 0x7f60a58abec0>

    def _refused(w, run):
        got = CR.successor(w.root, "l1", repo=REPO, run=run)
>       assert got == {"ok": False, "reason": "pushed-branch-ambiguous"}
E       AssertionError: assert {'ok': True, ...e', ...}, ...} == {'ok': False,...ch-ambiguous'}
E         
E         Differing items:
E         {'ok': True} != {'ok': False}
E         Left contains 9 more items:
E         {'branch': 'issue-17-x',
E          'issue': 17,
E          'launchId': 'l1',...
E         
E         ...Full output truncated, use '-vv' to show

/home/user/wt-2272-wo2/plugins/superheroes/lib/tests/test_i2272_recover.py:305: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_i2272_recover.py::test_3b_a_work_order_branch_with_work_found_nowhere_else_refuses
FAILED plugins/superheroes/lib/tests/test_i2272_recover.py::test_3b2_a_work_order_branch_strictly_ahead_of_the_lanes_branch_refuses
2 failed in 2.13s
```

**Restore:** inverse edit.
**Restore receipt:** `grep -n "if not all(_contained"` printed `596:        if not all(_contained(repo_root, b, primary, env, run) for b in others):`.

**Green:**
```
..                                                                       [100%]
2 passed in 2.27s
```

## (f) the failed-ancestry refusal — axis: an ancestry read that did not answer yes is never taken for contained

**Guarded element:** `cloud_recover.py:577` `return code == 0` in `_contained`.

**Neutralization:** `return code == 0` became `return code != 1` (a failed read counts as contained).

**Detector:** `test_3c_an_ancestry_read_that_fails_refuses[exit-128]`

**Red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
____________ test_3c_an_ancestry_read_that_fails_refuses[exit-128] _____________

w = namespace(root='/tmp/claude-0/pytest-of-root/pytest-52/test_3c_an_ancestry_read_that_0/advisor', builder='/tmp/claude-...ry_read_that_0'), gh=<test_cloud_recover.Gh object at 0x7febc2ca3d40>, base='1a03c23f3fa86321939eceac7290f99c40f15842')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7febc28eea50>
ancestry = 128

    @pytest.mark.parametrize("ancestry", [128, 2, "raise"], ids=["exit-128", "exit-2", "git-could-not-run"])
    def test_3c_an_ancestry_read_that_fails_refuses(w, monkeypatch, ancestry):
        _contained_pair(w)
        _stopped(w, monkeypatch, premise=_no_stack(w))
        run = _runner(w, pulls={LANE: [5]}, ancestry=ancestry)
>       _refused(w, run)

/home/user/wt-2272-wo2/plugins/superheroes/lib/tests/test_i2272_recover.py:358: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

w = namespace(root='/tmp/claude-0/pytest-of-root/pytest-52/test_3c_an_ancestry_read_that_0/advisor', builder='/tmp/claude-...ry_read_that_0'), gh=<test_cloud_recover.Gh object at 0x7febc2ca3d40>, base='1a03c23f3fa86321939eceac7290f99c40f15842')
run = <function _runner.<locals>.run at 0x7febc1f90c20>

    def _refused(w, run):
        got = CR.successor(w.root, "l1", repo=REPO, run=run)
>       assert got == {"ok": False, "reason": "pushed-branch-ambiguous"}
E       AssertionError: assert {'ok': True, ...2', ...}, ...} == {'ok': False,...ch-ambiguous'}
E         
E         Differing items:
E         {'ok': True} != {'ok': False}
E         Left contains 9 more items:
E         {'branch': 'issue-17-x',
E          'issue': 17,
E          'launchId': 'l1',...
E         
E         ...Full output truncated, use '-vv' to show

/home/user/wt-2272-wo2/plugins/superheroes/lib/tests/test_i2272_recover.py:305: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_i2272_recover.py::test_3c_an_ancestry_read_that_fails_refuses[exit-128]
1 failed in 1.49s
```

**Restore:** inverse edit.
**Restore receipt:** `grep -n "return code == 0"` printed `577:    return code == 0`.

**Green:**
```
.                                                                        [100%]
1 passed in 1.46s
```

## (f2) the primary requirement — axis: no single pull request names the lane's own branch, so nothing is adopted

**Guarded element:** `cloud_recover.py:568-569` in `_primary`, `return None` when a pull request read failed or the count of branches with a pull request is not one.

**Neutralization:** `return None` became `return entries[0]` (any survivor is the primary).

**Detector:** `test_3c2_no_single_branch_with_a_pull_request_refuses[no-branch-has-one]`

**Red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
___ test_3c2_no_single_branch_with_a_pull_request_refuses[no-branch-has-one] ___

w = namespace(root='/tmp/claude-0/pytest-of-root/pytest-57/test_3c2_no_single_branch_with0/advisor', builder='/tmp/claude-...e_branch_with0'), gh=<test_cloud_recover.Gh object at 0x7fb8abdaa6c0>, base='fc67c57e1b8d6f10fe698eb9cdb710126fb69265')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7fb8ab9bf5f0>
pulls = {}

    @pytest.mark.parametrize("pulls", [{}, {LANE: [5], WO: [6]}], ids=["no-branch-has-one", "two-branches-have-one"])
    def test_3c2_no_single_branch_with_a_pull_request_refuses(w, monkeypatch, pulls):
        _contained_pair(w)
        _stopped(w, monkeypatch, premise=_no_stack(w))
>       _refused(w, _runner(w, pulls=pulls))

/home/user/wt-2272-wo2/plugins/superheroes/lib/tests/test_i2272_recover.py:366: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

w = namespace(root='/tmp/claude-0/pytest-of-root/pytest-57/test_3c2_no_single_branch_with0/advisor', builder='/tmp/claude-...e_branch_with0'), gh=<test_cloud_recover.Gh object at 0x7fb8abdaa6c0>, base='fc67c57e1b8d6f10fe698eb9cdb710126fb69265')
run = <function _runner.<locals>.run at 0x7fb8abb5fa60>

    def _refused(w, run):
        got = CR.successor(w.root, "l1", repo=REPO, run=run)
>       assert got == {"ok": False, "reason": "pushed-branch-ambiguous"}
E       AssertionError: assert {'ok': True, ...5', ...}, ...} == {'ok': False,...ch-ambiguous'}
E         
E         Differing items:
E         {'ok': True} != {'ok': False}
E         Left contains 9 more items:
E         {'branch': 'issue-17-x',
E          'issue': 17,
E          'launchId': 'l1',...
E         
E         ...Full output truncated, use '-vv' to show

/home/user/wt-2272-wo2/plugins/superheroes/lib/tests/test_i2272_recover.py:305: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_i2272_recover.py::test_3c2_no_single_branch_with_a_pull_request_refuses[no-branch-has-one]
1 failed in 1.52s
```

**Restore:** inverse edit.
**Restore receipt:** `grep -n "found.count(True) != 1" -A1` printed `568:    if any(f is None for f in found) or found.count(True) != 1:` and `569:        return None`.

**Green:**
```
.                                                                        [100%]
1 passed in 1.43s
```

## (f3) the reopened-handback leg — axis: a handed-back lane a fix order reopened is assessed, not ended

**Guarded element:** `cloud_recover.py:441` the `latest == "handback" and _reopened_handback(...)` clause of `open_again`.

**Neutralization:** `open_again = latest in ("park", "died") or (latest == "handback" and _reopened_handback(repo_root, info, env))`
became `open_again = latest in ("park", "died")`.

**Detector:** `test_3x_a_handed_back_lane_a_vet_not_ready_reopened_is_stopped_by_the_limit`

**Red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_3x_a_handed_back_lane_a_vet_not_ready_reopened_is_stopped_by_the_limit __

w = namespace(root='/tmp/claude-0/pytest-of-root/pytest-60/test_3x_a_handed_back_lane_a_v0/advisor', builder='/tmp/claude-...back_lane_a_v0'), gh=<test_cloud_recover.Gh object at 0x7f2d560d7ce0>, base='3b68e17735bbcb62e380f48a27e5c5e6ffe4e413')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7f2d5615dfa0>

    def test_3x_a_handed_back_lane_a_vet_not_ready_reopened_is_stopped_by_the_limit(w, monkeypatch):
        _handed_back(w)
        assert ll.amend(w.root, "l1", "vet", "not-ready", "needs the narrow fix")["ok"] is True
        _limit(monkeypatch, _reading())
        out = _assess(w, state="unread")
>       assert out["ok"] is True and (out["verdict"], out["evidence"]) == ("stopped", "account-limited")
E       AssertionError: assert (True is True and ('ended', None) == ('stopped', 'account-limited')
E         
E         At index 0 diff: 'ended' != 'stopped'
E         Use -v to get more diff)

/home/user/wt-2272-wo2/plugins/superheroes/lib/tests/test_i2272_recover.py:196: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_i2272_recover.py::test_3x_a_handed_back_lane_a_vet_not_ready_reopened_is_stopped_by_the_limit
1 failed in 1.63s
```

**Restore:** inverse edit.
**Restore receipt:** `grep -n "open_again = "` printed `441:    open_again = latest in ("park", "died") or (latest == "handback" and _reopened_handback(repo_root, info, env))`.

**Green:**
```
.                                                                        [100%]
1 passed in 1.35s
```

## (g) the four-field restriction — axis: the helper posts exactly the fields the takeover check reads and nothing else

**Guarded element:** `cloud_recover.py:57` `HELPER_READ_FIELDS`.

**Neutralization:** `("id", "session_status", "status_bucket", "archived")` became `("id", "session_status", "status_bucket", "archived", "usage")`.

**Detector:** `test_4_the_helper_read_names_the_four_fields_the_takeover_check_reads_and_no_others`

**Red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_4_the_helper_read_names_the_four_fields_the_takeover_check_reads_and_no_others _

    def test_4_the_helper_read_names_the_four_fields_the_takeover_check_reads_and_no_others():
        got = CR.helper_read(REPO, 17, ["session_abc", "session_d-e_f"])
>       assert got["ok"] is True and got["fields"] == FOUR and list(CR.HELPER_READ_FIELDS) == FOUR
E       AssertionError: assert (True is True and ['id', 'sessi...ved', 'usage'] == ['id', 'sessi...', 'archived']
E         
E         Left contains one more item: 'usage'
E         Use -v to get more diff)

/home/user/wt-2272-wo2/plugins/superheroes/lib/tests/test_i2272_recover.py:431: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_i2272_recover.py::test_4_the_helper_read_names_the_four_fields_the_takeover_check_reads_and_no_others
1 failed in 0.95s
```

**Restore:** inverse edit.
**Restore receipt:** `grep -n "^HELPER_READ_FIELDS"` printed `57:HELPER_READ_FIELDS = ("id", "session_status", "status_bucket", "archived")`.

**Green:**
```
.                                                                        [100%]
1 passed in 1.06s
```

## Round 2 — the stand-down stamp and the second limit read

**(r2a) the stand-down stamp.** Guarded element: `cloud_recover._limit_reading`, the `standDown == 1` (an int, not a bool) test on the lane's reserved premise. Neutralization: prefixed the test with `False and`. Command: `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_i2272_recover.py -q -p no:randomly`. Red: the five `test_2_a_lane_without_a_valid_stand_down_stamp_is_not_stopped_by_the_limit[...]` cases failed (`absent`, `zero`, `two`, `bool`, `string`); an unstamped lane with a limited reading was stopped. Restore: `False and` removed. Green: the file passes.

**(r2b) the second limit read.** Guarded element: `cloud_recover.successor`, the `limited_stop and _limit_reading(...) is None` refusal just before the supersession is recorded. Neutralization: prefixed it with `False and`. Same command. Red: `test_3c_a_limit_that_expires_during_the_pushed_work_read_refuses_before_the_supersession_is_recorded` and `test_3c_an_account_limit_stop_that_still_holds_is_adopted_and_the_limit_is_reread` (the second read is gone) failed. Restore: `False and` removed. Green: the file passes.

## Round 7 — the stand-down comment leg and the shared eligibility rule

**(r7a) the stand-down comment leg.** Guarded element: `cloud_recover.assess`, the `elif stood_down is not None:` leg right after the handover leg (a comment opening with `cloud_builder.STAND_DOWN_HEADER`, created at or after the lane's start, is stop evidence `stand-down`). Neutralization: `elif stood_down is not None:` became `elif False and stood_down is not None:`. Command: `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_i2272_recover.py -k test_5 -q -p no:randomly`.

Red (final lines):
```
FAILED plugins/superheroes/lib/tests/test_i2272_recover.py::test_5_a_stand_down_comment_after_the_lanes_start_is_stop_evidence_and_is_recorded_like_a_handover
FAILED plugins/superheroes/lib/tests/test_i2272_recover.py::test_5_a_stand_down_stop_is_resumed_by_the_successor_after_the_limit_reset
2 failed, 2 passed, 56 deselected in 14.06s
```
Restore: `False and ` removed by the inverse edit. Green (final line): `4 passed, 56 deselected in 1.86s`.

**(r7b) the shared rule's stamp test.** Guarded element: `cloud_recover._stand_down_stamped` (used by `limit_relief`, which the launcher and `_limit_reading` both call), the `not isinstance(stand_down, bool)` exclusion. Neutralization: the clause was removed. Command: `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_i2272_recover.py::test_5_limit_relief_edges plugins/superheroes/lib/tests/test_i2272_launcher.py::test_only_a_stand_down_stamp_of_one_relieves_a_limited_lane -q -p no:randomly`.

Red (final lines):
```
FAILED plugins/superheroes/lib/tests/test_i2272_recover.py::test_5_limit_relief_edges
FAILED plugins/superheroes/lib/tests/test_i2272_launcher.py::test_only_a_stand_down_stamp_of_one_relieves_a_limited_lane[True]
2 failed, 4 passed in 3.93s
```
Restore: the clause put back by the inverse edit. Green (final line): `6 passed in 4.25s`.

## After all nine

Every neutralization was restored by its inverse edit before the next began. The final run of the whole detector file, with the
production file in its restored state: `46 passed in 18.36s`.
