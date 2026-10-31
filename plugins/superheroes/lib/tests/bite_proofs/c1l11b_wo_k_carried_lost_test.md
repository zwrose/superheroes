# C1-L11b (WO-K) bite-proof — a carried finding whose break-it test the record lost withholds certification through every round, unless the owner's audited out-of-scope ruling exempts it

**Provenance:** implementer WO-D2 (follow-up to WO-D of build #2279, C1-L11f), recording the guards that `round_driver.py` cites as `bite-proof record c1l11b_wo_k_carried_lost_test` (`_carried_findings`, `_break_it_kept_step`) and the guard WO-D added in the same function (K5). K1 to K4 are the guards of the earlier C1-L11b work; K5 is the exemption filter added by WO-D (D1).

Each element was neutralized with one targeted Edit and restored by the inverse Edit; no `git checkout`, `restore`, `reset` or `stash` was used. Run from `/home/user/wt-2279-d` (build base `4f350065` plus the WO-D commit `2ac92236`) under `timeout 600 scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-wo-d2 -m pytest <node ids> -q -p no:cacheprovider`. Each capture is the runner's whole output for that run apart from the `UV_NATIVE_TLS` deprecation warning line (the first line of each real output), which is left out; K1's first capture is incomplete (see K1). Nothing is redacted: no secrets, tokens or URLs appear (the `/tmp/claude-0/...` paths are pytest temp directories, where shown). The restore receipt of each element is the restored line quoted back at the line number it has in the restored tree, together with `git diff --stat` printing nothing (empty output) over the tree after the restore.

Proving tests (nodes), from `plugins/superheroes/lib/tests/`:

- c7 = `test_c1l11b_carried_findings.py::test_c7_a_carried_finding_with_a_lost_break_it_test_is_marked_and_withholds_certification_once_fixed`
- c8 = `test_c1l11b_carried_findings.py::test_c8_the_lost_test_marker_survives_a_merge_the_fresh_higher_severity_report_wins`
- c9 = `test_c1l11b_carried_findings.py::test_c9_the_lost_test_marker_survives_the_ledger_row_being_replaced_on_a_re_raise`
- l4b = `test_break_it_loop.py::test_l4b_merge_and_rank_never_merges_a_carried_test_lost_finding`
- a = `test_c1l11f_wo_d_exempt_and_new_issues.py::test_a_a_carried_lost_test_finding_the_owner_ruled_out_of_scope_and_the_audit_cleared_certifies` (2 cases: `[fixed]`, `[out-of-scope]`)
- b = `test_c1l11f_wo_d_exempt_and_new_issues.py::test_b_a_lost_test_finding_without_the_whole_exemption_still_parks` (6 cases)

Every red is the runner's own failure of the unedited test, caused by the neutralization alone, and on the axis the element claims. The mapping (which node each neutralization turned red, found by running the set under the neutralization):

| ID | Guarded element | Axis | Neutralization turns red | Stayed green under it |
|---|---|---|---|---|
| K1 | `_break_it_kept_step`, the lost-test park (`round_driver.py:8816`) | a carried finding whose test was lost and never re-attached withholds certification | c7; b (all 6 cases) | c8, c9, l4b |
| K2 | `_with_carried`, the marker kept through a merge (`round_driver.py:1708`) | a merge the fresh report wins keeps the carried finding's lost-test marker | c8 | c7, c9, l4b, a |
| K3 | `_seed_ledger_entry`, the marker kept on a re-raise (`round_driver.py:1936`) | a ledger row replaced on a re-raise keeps the lost-test marker | c9 | c7, c8, l4b, a |
| K4 | `verification.merge_and_rank`, the `carriedTestLost` carve-out (`verification.py:497`) | a carried lost-test finding is never folded into a fix group's representative | l4b | c7, c8, c9, a |
| K5 | `_break_it_kept_step`, the exemption filter (`round_driver.py:8816`) | a carried lost-test finding the owner ruled out of scope with an audit-cleared, attributed ruling owes no park | a (both cases) | none run with it (b and the mixed case c were not run under this neutralization) |

---

## K1 — the lost-test park

**axis:** a carried finding whose test was lost and never re-attached withholds certification, though no round-level run registers it.

**neutralization** (`round_driver.py:8816`, `_break_it_kept_step`: the list of parked keys emptied):
```python
-    lost = [key for key in _carried_test_lost_unresolved(state) if _break_it_ruled_exempt(state, key) is None]
+    lost = []
```

**raw red, mapping run (INCOMPLETE: the harness truncated the middle of this output, "3638 characters truncated", so only its head and tail are quoted; the truncated middle held the failures of four of the six `b` cases):** `timeout 600 scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-wo-d2 -m pytest <c7> <c8> <c9> <l4b> <b> -q -p no:cacheprovider` (each node as `plugins/superheroes/lib/tests/<node>`)
```
F...FFFFFF                                                               [100%]
=================================== FAILURES ===================================
... [3638 characters truncated by the harness] ...
FAILED plugins/superheroes/lib/tests/test_c1l11b_carried_findings.py::test_c7_a_carried_finding_with_a_lost_break_it_test_is_marked_and_withholds_certification_once_fixed
FAILED plugins/superheroes/lib/tests/test_c1l11f_wo_d_exempt_and_new_issues.py::test_b_a_lost_test_finding_without_the_whole_exemption_still_parks[unattributed]
FAILED plugins/superheroes/lib/tests/test_c1l11f_wo_d_exempt_and_new_issues.py::test_b_a_lost_test_finding_without_the_whole_exemption_still_parks[half-attributed]
FAILED plugins/superheroes/lib/tests/test_c1l11f_wo_d_exempt_and_new_issues.py::test_b_a_lost_test_finding_without_the_whole_exemption_still_parks[no-audit]
FAILED plugins/superheroes/lib/tests/test_c1l11f_wo_d_exempt_and_new_issues.py::test_b_a_lost_test_finding_without_the_whole_exemption_still_parks[not-discharged-audit]
FAILED plugins/superheroes/lib/tests/test_c1l11f_wo_d_exempt_and_new_issues.py::test_b_a_lost_test_finding_without_the_whole_exemption_still_parks[no-ruling]
FAILED plugins/superheroes/lib/tests/test_c1l11f_wo_d_exempt_and_new_issues.py::test_b_a_lost_test_finding_without_the_whole_exemption_still_parks[guidance-ruling]
7 failed, 3 passed in 4.99s
```
(Seven failures and three passes: c7 and the six `b` cases failed; c8, c9 and l4b passed.)

**raw red, c7 alone (complete):** `timeout 600 scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-wo-d2 -m pytest "plugins/superheroes/lib/tests/test_c1l11b_carried_findings.py::test_c7_a_carried_finding_with_a_lost_break_it_test_is_marked_and_withholds_certification_once_fixed" -q -p no:cacheprovider`
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_c7_a_carried_finding_with_a_lost_break_it_test_is_marked_and_withholds_certification_once_fixed _

monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7ff1c77decf0>

    def test_c7_a_carried_finding_with_a_lost_break_it_test_is_marked_and_withholds_certification_once_fixed(monkeypatch):
        run = {"test": "tests/test_x.py", "commit": "h", "status": "ran", "exitCode": 1, "output": "", "reason": None, "changedWhy": None}
        earlier = {"findings": [dict(_finding(27, tradeoff=False, breakItRuns=[run]), outcome=None)]}
        [row] = RD._carried_findings(earlier)
        assert row[RD.CARRIED_TEST_LOST_FIELD] is True
        plain = dict(_finding(27, tradeoff=False), outcome=None)
        assert RD.CARRIED_TEST_LOST_FIELD not in RD._carried_findings({"findings": [plain]})[0]
        fixed = dict(row, disposition="fixed")
        assert RD._carried_test_lost_unresolved(_lost_test_state(fixed)) == [RD._finding_identity_key(fixed)]
        # a reviewer who attaches the test again clears the obligation, and a finding not fixed owes nothing here
        assert RD._carried_test_lost_unresolved(_lost_test_state(dict(fixed, suggestion=BREAK_IT_BLOCK))) == []
        assert RD._carried_test_lost_unresolved(_lost_test_state(dict(row, disposition="refuted"))) == []
        parked = []
        monkeypatch.setattr(RD, "_park_cannot_certify", lambda state, detail: parked.append(detail))
>       assert RD._break_it_kept_step(_lost_test_state(fixed), {}) is True
E       AssertionError: assert False is True
E        +  where False = <function _break_it_kept_step at 0x7ff1c4423420>({'round': 2, 'rounds': {'1': {}, '2': {}}, 'dispositionLedger': [{'id': 'F-the', 'title': 'the edited value is wrong', 'severity': 'Important', 'file': 'src/shared.py', ...}], 'config': {}}, {})
E        +    where <function _break_it_kept_step at 0x7ff1c4423420> = RD._break_it_kept_step
E        +    and   {'round': 2, 'rounds': {'1': {}, '2': {}}, 'dispositionLedger': [{'id': 'F-the', 'title': 'the edited value is wrong', 'severity': 'Important', 'file': 'src/shared.py', ...}], 'config': {}} = _lost_test_state({'id': 'F-the', 'title': 'the edited value is wrong', 'severity': 'Important', 'file': 'src/shared.py', ...})

/home/user/wt-2279-d/plugins/superheroes/lib/tests/test_c1l11b_carried_findings.py:532: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l11b_carried_findings.py::test_c7_a_carried_finding_with_a_lost_break_it_test_is_marked_and_withholds_certification_once_fixed
1 failed in 1.68s
```

**restore** (the inverse Edit): the same line back, `round_driver.py:8816`:
```python
    lost = [key for key in _carried_test_lost_unresolved(state) if _break_it_ruled_exempt(state, key) is None]
```
**restore receipt:** the line above is the restored content at `round_driver.py:8816`; `git diff --stat` after the restore printed nothing.

**raw green:** `timeout 600 scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-wo-d2 -m pytest <c7> <c8> <c9> <l4b> <a> <b> -q -p no:cacheprovider`
```
............                                                             [100%]
12 passed in 2.74s
```

---

## K2 — the `_with_carried` marker

**axis:** a carried finding's lost-test marker survives a merge the fresh report wins (unless the fresh report attached a test), so no later audit can certify it without the test.

**neutralization** (`round_driver.py:1708`, `_with_carried`: the keep made unreachable):
```python
-        if h.get(CARRIED_TEST_LOST_FIELD) is True and not break_it.carries_test(merged):
+        if False and h.get(CARRIED_TEST_LOST_FIELD) is True and not break_it.carries_test(merged):
```

**raw red:** `timeout 600 scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-wo-d2 -m pytest <c7> <c8> <c9> <l4b> <a> -q -p no:cacheprovider`
```
.F....                                                                   [100%]
=================================== FAILURES ===================================
_ test_c8_the_lost_test_marker_survives_a_merge_the_fresh_higher_severity_report_wins _

    def test_c8_the_lost_test_marker_survives_a_merge_the_fresh_higher_severity_report_wins():
        run = {"test": "tests/test_x.py", "commit": "h", "status": "ran", "exitCode": 1, "output": "", "reason": None, "changedWhy": None}
        earlier = {"findings": [dict(_finding(27, severity="Minor", tradeoff=False, breakItRuns=[run]), outcome=None)]}
        [held] = RD._carried_findings(earlier)
        assert held[RD.CARRIED_TEST_LOST_FIELD] is True
        fresh = _compiled(held, severity="Important")
        [row] = RD._with_carried({"_carriedToVerify": [held]}, [fresh])
>       assert row["severity"] == "Important" and row[RD.CARRIED_TEST_LOST_FIELD] is True, row
                                                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       KeyError: 'carriedTestLost'

/home/user/wt-2279-d/plugins/superheroes/lib/tests/test_c1l11b_carried_findings.py:543: KeyError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l11b_carried_findings.py::test_c8_the_lost_test_marker_survives_a_merge_the_fresh_higher_severity_report_wins
1 failed, 5 passed in 2.10s
```

**restore** (the inverse Edit): `round_driver.py:1708`
```python
        if h.get(CARRIED_TEST_LOST_FIELD) is True and not break_it.carries_test(merged):
```
**restore receipt:** the line above is the restored content at `round_driver.py:1708`; `git diff --stat` after the restore printed nothing.

**raw green:** same command and nodes as the red.
```
......                                                                   [100%]
6 passed in 2.31s
```

---

## K3 — the `_seed_ledger_entry` marker

**axis:** a ledger row replaced on a re-raise keeps the lost-test marker it held unless the new row carries a test.

**neutralization** (`round_driver.py:1936`, `_seed_ledger_entry`: the keep made unreachable):
```python
-    if (isinstance(existing, dict) and existing.get(CARRIED_TEST_LOST_FIELD) is True
+    if (False and isinstance(existing, dict) and existing.get(CARRIED_TEST_LOST_FIELD) is True
```

**raw red:** `timeout 600 scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-wo-d2 -m pytest <c7> <c8> <c9> <l4b> <a> -q -p no:cacheprovider`
```
..F...                                                                   [100%]
=================================== FAILURES ===================================
_ test_c9_the_lost_test_marker_survives_the_ledger_row_being_replaced_on_a_re_raise _

    def test_c9_the_lost_test_marker_survives_the_ledger_row_being_replaced_on_a_re_raise():
        run = {"test": "tests/test_x.py", "commit": "h", "status": "ran", "exitCode": 1, "output": "", "reason": None, "changedWhy": None}
        earlier = {"findings": [dict(_finding(27, severity="Minor", tradeoff=False, breakItRuns=[run]), outcome=None)]}
        [held] = RD._carried_findings(earlier)
        key = RD._finding_identity_key(held)
        state = {"round": 2, "rounds": {"1": {}, "2": {}}, "config": {}}
        ledger = [dict(held, disposition="fixed")]
        seen = {key: 0}
        reraised = dict(_compiled(held, severity="Important"), **{SC.FINDING_KEY_FIELD: key})
        entry = RD._seed_ledger_entry(state, ledger, seen, reraised, key, 2)
>       assert entry[RD.CARRIED_TEST_LOST_FIELD] is True and ledger[0][RD.CARRIED_TEST_LOST_FIELD] is True, entry
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       KeyError: 'carriedTestLost'

/home/user/wt-2279-d/plugins/superheroes/lib/tests/test_c1l11b_carried_findings.py:561: KeyError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l11b_carried_findings.py::test_c9_the_lost_test_marker_survives_the_ledger_row_being_replaced_on_a_re_raise
1 failed, 5 passed in 2.56s
```

**restore** (the inverse Edit): `round_driver.py:1936`
```python
    if (isinstance(existing, dict) and existing.get(CARRIED_TEST_LOST_FIELD) is True
```
**restore receipt:** the line above is the restored content at `round_driver.py:1936`; `git diff --stat` after the restore printed nothing.

**raw green:** same command and nodes as the red.
```
......                                                                   [100%]
6 passed in 1.89s
```

---

## K4 — `verification.merge_and_rank`'s `carriedTestLost` carve-out

**axis:** a carried finding marked `carriedTestLost` stays out of any fix group's representative merge, so the marker the certification guard reads is not folded away.

**neutralization** (`verification.py:497`, `merge_and_rank`: the `carriedTestLost` leg removed from the carve-out):
```python
-                for m in [m for m in members if break_it.carries_test(m) or m.get("carriedTestLost") is True]:
+                for m in [m for m in members if break_it.carries_test(m)]:
```

**raw red:** `timeout 600 scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-wo-d2 -m pytest <c7> <c8> <c9> <l4b> <a> -q -p no:cacheprovider`
```
...F..                                                                   [100%]
=================================== FAILURES ===================================
_______ test_l4b_merge_and_rank_never_merges_a_carried_test_lost_finding _______

    def test_l4b_merge_and_rank_never_merges_a_carried_test_lost_finding():
        def finding(fid, **extra):
            out = {"id": fid, "file": "f%s.py" % fid, "line": 1, "title": "t%s" % fid,
                   "severity": "Minor", "suggestion": "s-%s" % fid}
            out.update(extra)
            return out
    
        lost = finding("v0", carriedTestLost=True)
        other = finding("v1", severity="Important")
        out = verification.merge_and_rank([lost, other], [{"group_id": "g0", "member_ids": ["v0", "v1"]}])
        by_id = {f["id"]: f for f in out["findings"]}
>       assert sorted(by_id) == ["v0", "v1"] and out["merges"] == []
E       AssertionError: assert (['v1'] == ['v0', 'v1']
E         
E         At index 0 diff: 'v1' != 'v0'
E         Right contains one more item: 'v1'
E         Use -v to get more diff)

/home/user/wt-2279-d/plugins/superheroes/lib/tests/test_break_it_loop.py:381: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_break_it_loop.py::test_l4b_merge_and_rank_never_merges_a_carried_test_lost_finding
1 failed, 5 passed in 2.01s
```

**restore** (the inverse Edit): `verification.py:497`
```python
                for m in [m for m in members if break_it.carries_test(m) or m.get("carriedTestLost") is True]:
```
**restore receipt:** the line above is the restored content at `verification.py:497`; `git diff --stat` after the restore printed nothing.

**raw green:** same command and nodes as the red.
```
......                                                                   [100%]
6 passed in 2.47s
```

---

## K5 — the exemption filter added by WO-D (D1)

**axis:** a carried lost-test finding the owner ruled out of scope with an attributed, audit-cleared ruling owes no park; every other one still parks.

**neutralization** (`round_driver.py:8816`, `_break_it_kept_step`: the filter removed, every unresolved lost-test key parks as before D1):
```python
-    lost = [key for key in _carried_test_lost_unresolved(state) if _break_it_ruled_exempt(state, key) is None]
+    lost = list(_carried_test_lost_unresolved(state))
```

**raw red:** `timeout 600 scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-wo-d2 -m pytest "plugins/superheroes/lib/tests/test_c1l11f_wo_d_exempt_and_new_issues.py::test_a_a_carried_lost_test_finding_the_owner_ruled_out_of_scope_and_the_audit_cleared_certifies" -q -p no:cacheprovider`
```
FF                                                                       [100%]
=================================== FAILURES ===================================
_ test_a_a_carried_lost_test_finding_the_owner_ruled_out_of_scope_and_the_audit_cleared_certifies[fixed] _

parked = ["break-it test not kept: the earlier session's test for rr1:6830197dfc65d27498e74a816d12b05c was lost and no reviewer attached it again"]
disposition = 'fixed'

    @pytest.mark.parametrize("disposition", ["fixed", "out-of-scope"])
    def test_a_a_carried_lost_test_finding_the_owner_ruled_out_of_scope_and_the_audit_cleared_certifies(parked, disposition):
        row = _lost_row(disposition=disposition)
        state = _state(row)
        _rule(state, row)
        _audit(state, row)
>       assert RD._break_it_kept_step(state, {}) is False
E       AssertionError: assert True is False
E        +  where True = <function _break_it_kept_step at 0x7f5be418ba60>({'round': 2, 'rounds': {'1': {}, '2': {'audits': [{'id': 'rr1:6830197dfc65d27498e74a816d12b05c', 'ruling': 'discharged...ited value is wrong', 'severity': 'Important', 'file': 'src/shared.py', ...}], 'dispositionLedgerOwner': 'ledger', ...}, {})

/home/user/wt-2279-d/plugins/superheroes/lib/tests/test_c1l11f_wo_d_exempt_and_new_issues.py:77: AssertionError
_ test_a_a_carried_lost_test_finding_the_owner_ruled_out_of_scope_and_the_audit_cleared_certifies[out-of-scope] _

parked = ["break-it test not kept: the earlier session's test for rr1:6830197dfc65d27498e74a816d12b05c was lost and no reviewer attached it again"]
disposition = 'out-of-scope'

    @pytest.mark.parametrize("disposition", ["fixed", "out-of-scope"])
    def test_a_a_carried_lost_test_finding_the_owner_ruled_out_of_scope_and_the_audit_cleared_certifies(parked, disposition):
        row = _lost_row(disposition=disposition)
        state = _state(row)
        _rule(state, row)
        _audit(state, row)
>       assert RD._break_it_kept_step(state, {}) is False
E       AssertionError: assert True is False
E        +  where True = <function _break_it_kept_step at 0x7f5be418ba60>({'round': 2, 'rounds': {'1': {}, '2': {'audits': [{'id': 'rr1:6830197dfc65d27498e74a816d12b05c', 'ruling': 'discharged...ited value is wrong', 'severity': 'Important', 'file': 'src/shared.py', ...}], 'dispositionLedgerOwner': 'ledger', ...}, {})

/home/user/wt-2279-d/plugins/superheroes/lib/tests/test_c1l11f_wo_d_exempt_and_new_issues.py:77: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l11f_wo_d_exempt_and_new_issues.py::test_a_a_carried_lost_test_finding_the_owner_ruled_out_of_scope_and_the_audit_cleared_certifies[fixed]
FAILED plugins/superheroes/lib/tests/test_c1l11f_wo_d_exempt_and_new_issues.py::test_a_a_carried_lost_test_finding_the_owner_ruled_out_of_scope_and_the_audit_cleared_certifies[out-of-scope]
2 failed in 1.93s
```

**restore** (the inverse Edit): `round_driver.py:8816`
```python
    lost = [key for key in _carried_test_lost_unresolved(state) if _break_it_ruled_exempt(state, key) is None]
```
**restore receipt:** the line above is the restored content at `round_driver.py:8816`; `git diff --stat` after the restore printed nothing.

**raw green:** `timeout 600 scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-wo-d2 -m pytest "plugins/superheroes/lib/tests/test_c1l11f_wo_d_exempt_and_new_issues.py::test_a_a_carried_lost_test_finding_the_owner_ruled_out_of_scope_and_the_audit_cleared_certifies" -q -p no:cacheprovider`
```
..                                                                       [100%]
2 passed in 1.80s
```

---

## Not separately neutralized (the unproven part of this record)

- K1 and K5 share the line `round_driver.py:8816`; the K1 neutralization (`lost = []`) removes the park and the filter together, so K1's reds on `b` show the park, not the filter. The filter's own bite is K5 (test `a`).
- K5 was shown red on `a` only. The `b` cases and the mixed two-finding case (`test_c_…`) were not run under the K5 neutralization; they ran green on the restored tree in the final run. With the filter removed every lost key parks, so those fail-closed cases are expected to stay green under K5 (they guard that the filter does not over-exempt, which no neutralization here removes); that expectation was not run.
- The two earlier legs of `_break_it_kept_step` (dropped at compile, working-copy restore failed) are not covered here.
- `_carried_findings`' marker assignment (`round_driver.py:1569`) and the `_carried_test_lost_unresolved` selector (`round_driver.py:1670`) were not neutralized; c7 passes against them, but no neutralization of either was run.
- K1's first (mapping) capture is incomplete as stated; its decisive node c7 is shown complete from a second run.

---

# C1-L12 addendum (build #2216, entries for C1-L11f's review-loop axis lines)

**Provenance:** implementer WO-4, order id `c1l12-wo4`, worktree `/home/user/wo4`, branch `c1l12-wo4`, head at dispatch `86e05768`. Each entry is **re-derived at `86e05768`** by this order: the fixers' own red/green lived in their review sessions' folders on a container that has been reclaimed, and PR #2283's review records and round comments carry no break-it red/green for these lines, so none is quoted. A13 was added by fixer commit `35644832`, A14 by `26b2256f`. Each guarded element was neutralized with one targeted Edit and restored with the inverse Edit (no `git checkout`, `restore`, `reset` or `stash`); after each restore `git status --porcelain` listed no `.py` file outside `plugins/superheroes/lib/tests/`. Every run is `timeout 600 scripts/pinned-python -B -X pycache_prefix=/tmp/shpyc-wo4 -m pytest "<node id>" -q -p no:cacheprovider`. Each capture is the runner's whole output apart from the `UV_NATIVE_TLS` deprecation warning line, which is left out. Nothing is redacted: no credential-like text appears (the `rr1:...` strings are finding keys; `/tmp/claude-0/...` paths are pytest temp directories). Every capture is under 32 KiB. Both nodes live in `test_c1l11f_wo_d_exempt_and_new_issues.py`.

| ID | Guarded element | Axis (verbatim) | Proving node |
|---|---|---|---|
| A13 | `_break_it_kept_step`, `exempt_rows.append({"findingKey": key, ... "outcome": "ruled-out-of-scope", ...})` (`round_driver.py:9021`) | an exempt carried lost-test finding gets its ruled-out-of-scope row, so the record reports the owner's ruling and never "fixed and audited" — see bite-proof record c1l11b_wo_k_carried_lost_test | `test_a_an_exempt_carried_lost_test_finding_gets_its_ruled_out_of_scope_row_and_the_record_reports_the_ruling` |
| A14 | `_break_it_kept_step`, `if exempt_rows:` before `_record_round(state, "breakItKept", exempt_rows)` in the `if lost:` branch (`round_driver.py:9026`) | the exempt rows are persisted before a mixed-case park, so the record reports the owner's ruling for the waived finding whatever happens next — see bite-proof record c1l11b_wo_k_carried_lost_test | `test_c_two_lost_test_findings_one_exempt_and_one_not_park_naming_the_one_that_is_not` |

## A13

**Neutralization:** `        exempt_rows.append({"findingKey": key, "path": None, "outcome": "ruled-out-of-scope",` became `        [].append({"findingKey": key, "path": None, "outcome": "ruled-out-of-scope",` (the row is built and thrown away; `exempt_rows` stays empty).

**Raw red** (`test_a_an_exempt_carried_lost_test_finding_gets_its_ruled_out_of_scope_row_and_the_record_reports_the_ruling`):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_an_exempt_carried_lost_test_finding_gets_its_ruled_out_of_scope_row_and_the_record_reports_the_ruling _

parked = []

    def test_a_an_exempt_carried_lost_test_finding_gets_its_ruled_out_of_scope_row_and_the_record_reports_the_ruling(parked):
        row = _lost_row()
        state = _state(row)
        key = RD._finding_identity_key(row)
        _rule(state, row)
        _audit(state, row)
        assert RD._break_it_kept_step(state, {}) is False
        kept = [r for rec in state["rounds"].values() for r in rec.get("breakItKept") or []]
>       assert [(r["findingKey"], r["outcome"], r["ruledBy"], r["ruledAt"]) for r in kept] == [
            (key, "ruled-out-of-scope", PROV["ruledBy"], PROV["ruledAt"])]
E       AssertionError: assert [] == [('rr1:683019...0T12:00:00Z')]
E         
E         Right contains one more item: ('rr1:6830197dfc65d27498e74a816d12b05c', 'ruled-out-of-scope', 'zach', '2026-10-20T12:00:00Z')
E         Use -v to get more diff

/home/user/wo4/plugins/superheroes/lib/tests/test_c1l11f_wo_d_exempt_and_new_issues.py:89: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l11f_wo_d_exempt_and_new_issues.py::test_a_an_exempt_carried_lost_test_finding_gets_its_ruled_out_of_scope_row_and_the_record_reports_the_ruling
1 failed in 1.68s
```

The red is on the claimed axis: the exempt finding is not parked (`is False` passes) but the record carries no `ruled-out-of-scope` row naming the owner's ruling.

**Restore** (the inverse Edit): `        [].append({"findingKey": key, ...` back to `        exempt_rows.append({"findingKey": key, "path": None, "outcome": "ruled-out-of-scope",`. **Restore receipt:** the line is back as `        exempt_rows.append({"findingKey": key, "path": None, "outcome": "ruled-out-of-scope",`, and `git status --porcelain` listed no `.py` file outside `plugins/superheroes/lib/tests/`.

**Raw green** (the same node):

```
.                                                                        [100%]
1 passed in 1.64s
```

## A14

**Neutralization:** `        if exempt_rows:` (the one above `_record_round(state, "breakItKept", exempt_rows)` and `_park_cannot_certify(`) became `        if exempt_rows and False:`.

**Raw red** (`test_c_two_lost_test_findings_one_exempt_and_one_not_park_naming_the_one_that_is_not`):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_c_two_lost_test_findings_one_exempt_and_one_not_park_naming_the_one_that_is_not _

parked = ["break-it test not kept: the earlier session's test for rr1:6463314fe6aec00a3b6acd67c21837e3 was lost and no reviewer attached it again"]

    def test_c_two_lost_test_findings_one_exempt_and_one_not_park_naming_the_one_that_is_not(parked):
        exempt = _lost_row(27, title="the edited value is wrong")
        owed = _lost_row(3, title="the first value is wrong")
        assert RD._finding_identity_key(exempt) != RD._finding_identity_key(owed)
        for rows in ((exempt, owed), (owed, exempt)):
            del parked[:]
            state = _state(*rows)
            _rule(state, exempt)
            _audit(state, exempt)
            assert RD._break_it_kept_step(state, {}) is True
            assert len(parked) == 1 and RD._finding_identity_key(owed) in parked[0], parked
            assert RD._finding_identity_key(exempt) not in parked[0], parked
            # the waived finding's ruling is recorded even though the other one parked
            key = RD._finding_identity_key(exempt)
            kept = [r for rec in state["rounds"].values() for r in rec.get("breakItKept") or []]
>           assert [(r["findingKey"], r["outcome"]) for r in kept] == [(key, "ruled-out-of-scope")], kept
E           AssertionError: []
E           assert [] == [('rr1:683019...ut-of-scope')]
E             
E             Right contains one more item: ('rr1:6830197dfc65d27498e74a816d12b05c', 'ruled-out-of-scope')
E             Use -v to get more diff

/home/user/wo4/plugins/superheroes/lib/tests/test_c1l11f_wo_d_exempt_and_new_issues.py:145: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l11f_wo_d_exempt_and_new_issues.py::test_c_two_lost_test_findings_one_exempt_and_one_not_park_naming_the_one_that_is_not
1 failed in 1.79s
```

The red is on the claimed axis: the park still happens and names only the owed finding (the earlier assertions pass), but the exempt finding's ruling row was not persisted before the park.

**Restore** (the inverse Edit): `        if exempt_rows and False:` back to `        if exempt_rows:`. **Restore receipt:** the line is back as `        if exempt_rows:` above `            _record_round(state, "breakItKept", exempt_rows)` and `        _park_cannot_certify(state, "break-it test not kept: the earlier session's test for %s was lost and no reviewer attached it again" % lost[0])`, and `git status --porcelain` listed no `.py` file outside `plugins/superheroes/lib/tests/`.

**Raw green** (the same node):

```
.                                                                        [100%]
1 passed in 1.66s
```
