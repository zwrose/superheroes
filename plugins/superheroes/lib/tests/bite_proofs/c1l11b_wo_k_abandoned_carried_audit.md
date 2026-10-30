# C1-L11b (WO-K) bite-proof — a finding carried from an abandoned session is still audited against the change since that session's final commit

**Provenance:** implementer for WO-K, guarding `lib/round_driver.py` `_carried_audit_base` and its two consumers (`_returning_overrides`, `_seed_carried`)

Declared guarded element (from the order): K1 the final-commit fallback in `round_driver._carried_audit_base` (the axis comment at `round_driver.py:1541` cites this record). It was neutralized with one targeted Edit and restored with the inverse Edit; no `git checkout`, `restore`, `reset` or `stash` was used. Run from `/home/user/wt-2266` (head `cbba2503` plus the uncommitted WO-K edits) under `timeout 600 scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-wo-k -m pytest <node ids> -q -p no:cacheprovider`. The captures are the runner's whole output for each run apart from the `UV_NATIVE_TLS` deprecation warning line, which is left out; nothing is redacted (no secrets, tokens or URLs appear in the captures).

| ID | Guarded element | Axis | Proving tests |
|---|---|---|---|
| K1 | `round_driver.py:1542` the `if isinstance(earlier, dict) and earlier.get("ok") is True and earlier.get("abandoned"):` fallback in `_carried_audit_base` | a carried finding of an abandoned session is audited first against the change since that session's own final commit, though the decision stays `full` and names no `lastReviewed` | `test_t2_..._stays_open_when_confirmed[full]` (red to green below); `test_t1_..._the_record_reads_reviewed[full]` (see the open conflict below) |

## Open conflict: T1 `[full]` cannot go green under this order

The order names T1 `[full]` as the proving test and says its assertions are not to change. Its line 144 asserts `state["config"]["returning"]["lastReviewed"] == s.reviewed`. The order also says the stored `returning` decision is unchanged, and for an abandoned record C1-L11a's decider answers `full` with `lastReviewed: None`. Both cannot hold. So T1 `[full]` passes line 143 (the audit is dispatched first) with the fallback in place, and fails at line 144 in the restored (green) run below. This record therefore uses T2 `[full]` as the test that goes red then green. T1 `[full]`'s failure moves from line 143 (red, no fallback) to line 144 (restored). Nothing in the test was edited. The orchestrator owns the ruling on line 144.

Not separately neutralized (the unproven part of this record): the `ok is True` term, the `abandoned` term, the `_is_sha` check on the record's final commit, and the `returningAuditBase` read in `_seed_carried`. The not-a-sha edge is exercised by `test_t2_an_abandoned_record_whose_final_commit_is_not_a_sha_...` but has no neutralization of its own.

---

## K1 — the final-commit fallback

**axis:** a carried finding of an abandoned session is audited first against the change since that session's own final commit, though the decision stays `full` and names no `lastReviewed`.

**neutralization** (`round_driver.py`, `_carried_audit_base`: the fallback branch switched off):
```python
-    if isinstance(earlier, dict) and earlier.get("ok") is True and earlier.get("abandoned"):
+    if False and isinstance(earlier, dict) and earlier.get("ok") is True and earlier.get("abandoned"):
```

**raw red:** `timeout 600 scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-wo-k -m pytest "plugins/superheroes/lib/tests/test_c1l11b_carried_findings.py::test_t1_a_carried_finding_a_later_commit_fixed_is_settled_fixed_and_the_record_reads_reviewed[full]" "plugins/superheroes/lib/tests/test_c1l11b_carried_findings.py::test_t2_a_carried_finding_the_audit_does_not_discharge_goes_to_the_verifier_and_stays_open_when_confirmed[full]" -q -p no:cacheprovider`
```
FF                                                                       [100%]
=================================== FAILURES ===================================
_ test_t1_a_carried_finding_a_later_commit_fixed_is_settled_fixed_and_the_record_reads_reviewed[full] _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-25/test_t1_a_carried_finding_a_la0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7f7e754b9730>
record = {'abandoned': {'reason': 'the loop was closed before it ended'}}
read = 'full', order = [('dispatch-audits', 1), ('dispatch-panel', 1)]

    @pytest.mark.parametrize("record,read,order", [
        (None, "changed", [(RD.P_AUDITS, 1), (RD.P_SCOPED, 1)]),
        (ABANDONED, "full", [(RD.P_AUDITS, 1), (RD.P_PANEL, 1)]),
    ], ids=["changed", "full"])
    def test_t1_a_carried_finding_a_later_commit_fixed_is_settled_fixed_and_the_record_reads_reviewed(tmp_path, monkeypatch, record, read, order):
        finding = _finding(27)
        s = _session(tmp_path, monkeypatch, [finding], record=record)
        first = s.next()
        state = s.state()
>       assert first["action"] == RD.P_AUDITS and first["round"] == 1, first
E       AssertionError: {'ok': True, 'action': 'dispatch-panel', 'round': 1, 'phase': 'dispatch-panel', ...}
E       assert ('dispatch-panel' == 'dispatch-audits'
E         
E         - dispatch-audits
E         + dispatch-panel)

/home/user/wt-2266/plugins/superheroes/lib/tests/test_c1l11b_carried_findings.py:143: AssertionError
_ test_t2_a_carried_finding_the_audit_does_not_discharge_goes_to_the_verifier_and_stays_open_when_confirmed[full] _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-25/test_t2_a_carried_finding_the_0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7f7e754baea0>
record = {'abandoned': {'reason': 'the loop was closed before it ended'}}
after = 'dispatch-panel'

    @pytest.mark.parametrize("record,after", [(None, RD.P_SCOPED), (ABANDONED, RD.P_PANEL)], ids=["changed", "full"])
    def test_t2_a_carried_finding_the_audit_does_not_discharge_goes_to_the_verifier_and_stays_open_when_confirmed(tmp_path, monkeypatch, record, after):
        finding = _finding(27, tradeoff=False)  # a row with no `tradeoff` key is held for the owner (I3 below), not fixed
        key = finding[SC.FINDING_KEY_FIELD]
        s = _session(tmp_path, monkeypatch, [finding], change=TOUCHES_NEAR_27, record=record)
        n, seen = _run(s, _respond(audit="not-discharged"), stop_at=RD.P_VERIFIERS)
>       assert n["action"] == RD.P_VERIFIERS and seen[:2] == [(RD.P_AUDITS, 1), (after, 1)], seen
E       AssertionError: [('dispatch-panel', 1), ('dispatch-verifiers', 1)]
E       assert ('dispatch-verifiers' == 'dispatch-verifiers'
E         
E           dispatch-verifiers and [('dispatch-p...erifiers', 1)] == [('dispatch-a...ch-panel', 1)]
E         
E         At index 0 diff: ('dispatch-panel', 1) != ('dispatch-audits', 1)
E         Use -v to get more diff)

/home/user/wt-2266/plugins/superheroes/lib/tests/test_c1l11b_carried_findings.py:204: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l11b_carried_findings.py::test_t1_a_carried_finding_a_later_commit_fixed_is_settled_fixed_and_the_record_reads_reviewed[full]
FAILED plugins/superheroes/lib/tests/test_c1l11b_carried_findings.py::test_t2_a_carried_finding_the_audit_does_not_discharge_goes_to_the_verifier_and_stays_open_when_confirmed[full]
2 failed in 2.41s
```

**restore:** the inverse edit — `False and ` removed from the condition.

**restore receipt** (`grep -n 'earlier.get("abandoned")' plugins/superheroes/lib/round_driver.py`; the file also carries the other uncommitted WO-K edits, so `git status` over it is not a restore receipt here):
```
1542:    if isinstance(earlier, dict) and earlier.get("ok") is True and earlier.get("abandoned"):
```

**raw green:** the same command. T2 `[full]` passes. T1 `[full]` fails at line 144, which is the open conflict above, not the fallback: it now gets past line 143.
```
F.                                                                       [100%]
=================================== FAILURES ===================================
_ test_t1_a_carried_finding_a_later_commit_fixed_is_settled_fixed_and_the_record_reads_reviewed[full] _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-26/test_t1_a_carried_finding_a_la0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7f4ede7fcce0>
record = {'abandoned': {'reason': 'the loop was closed before it ended'}}
read = 'full', order = [('dispatch-audits', 1), ('dispatch-panel', 1)]

    @pytest.mark.parametrize("record,read,order", [
        (None, "changed", [(RD.P_AUDITS, 1), (RD.P_SCOPED, 1)]),
        (ABANDONED, "full", [(RD.P_AUDITS, 1), (RD.P_PANEL, 1)]),
    ], ids=["changed", "full"])
    def test_t1_a_carried_finding_a_later_commit_fixed_is_settled_fixed_and_the_record_reads_reviewed(tmp_path, monkeypatch, record, read, order):
        finding = _finding(27)
        s = _session(tmp_path, monkeypatch, [finding], record=record)
        first = s.next()
        state = s.state()
        assert first["action"] == RD.P_AUDITS and first["round"] == 1, first
>       assert state["config"]["returning"]["read"] == read and state["config"]["returning"]["lastReviewed"] == s.reviewed
E       AssertionError: assert ('full' == 'full'
E         
E           full and None == 'db1908dcc59664e38a5b2fd44f0d6b295a99315c')
E        +  where 'db1908dcc59664e38a5b2fd44f0d6b295a99315c' = <test_c1l11b_returning_session.Session object at 0x7f4edee54e00>.reviewed

/home/user/wt-2266/plugins/superheroes/lib/tests/test_c1l11b_carried_findings.py:144: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l11b_carried_findings.py::test_t1_a_carried_finding_a_later_commit_fixed_is_settled_fixed_and_the_record_reads_reviewed[full]
1 failed, 1 passed in 3.21s
```
