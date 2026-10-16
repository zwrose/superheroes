# Bite-proof record: c7l3_wo3_driver

The six guarded elements the driver work declared: the mirror hash check, the earlier-version gate on
the mirror, the state-write census, the "fix after the latest raise" condition, the complete-panel
condition, and the unseatable-grouping path keeping every verified finding. Each entry: the node was
confirmed by collection first (`--collect-only -q`, one test collected), the neutralization is one
targeted edit to `plugins/superheroes/lib/round_driver.py`, the detector ran unedited, and the
restore is the inverse edit. The pytest wrapper is `sbx-pytest.sh` (the CI-version interpreter, HOME
pointed at an empty directory). Nothing is redacted; the captures are far under the 32 KiB ceiling.

Run on the L3b build at `d749cdbc` plus the integration order's edits (the driver's decision-sources
delegation and the test changes), all uncommitted.

## 1. The mirror hash check

- **Element and axis:** `_read_mirror_state`, the `stateSha256` comparison. A mirror whose bytes do
  not hash to the hash it carries is torn, so it restores nothing.
- **Node:** `plugins/superheroes/lib/tests/test_session_repair_c7l3.py::test_a_mirror_whose_state_does_not_hash_to_its_hash_is_refused_as_before`
- **Collection:** `1 test collected in 0.52s`
- **Neutralization:** `if hashlib.sha256(state_bytes).hexdigest() != obj.get("stateSha256"):` became
  `if False and hashlib.sha256(state_bytes).hexdigest() != obj.get("stateSha256"):`
- **Raw red** (the session was restored and `cmd_next` carried on instead of refusing):
```
F                                                                        [100%]
=================================== FAILURES ===================================
___ test_a_mirror_whose_state_does_not_hash_to_its_hash_is_refused_as_before ___

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-55/test_a_mirror_whose_state_does0')

    def test_a_mirror_whose_state_does_not_hash_to_its_hash_is_refused_as_before(tmp_path):
        """axis: a mirror whose bytes do not hash to the hash it carries is torn, so it restores nothing —
        see bite-proof record c7l3_wo3_driver"""
        session_dir = _session(tmp_path)
        state = json.loads(_read(_state_path(session_dir)))
        honest_sha = hashlib.sha256(RD._canonical(state).encode("utf-8")).hexdigest()
        state["round"] = 9                                 # the text no longer says what the hash covers
        _forge_mirror(session_dir, state, sha=honest_sha)
        _truncate(_state_path(session_dir))
>       _assert_refused_as_before(session_dir, _read(_state_path(session_dir)))

/home/user/wt-1869-wo3/plugins/superheroes/lib/tests/test_session_repair_c7l3.py:256: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

session_dir = '/tmp/claude-0/pytest-of-root/pytest-55/test_a_mirror_whose_state_does0/s'
damaged_bytes = b'{"_changedSubjectsSincePanel":[],"_coverage":[],"_incompletePanel":false,"_ordersAnchors":{"1:dispatch-panel:0":{"he...ispositionSeqCounter":0,"findings":[],"fixBatch":[],"fullPanelRan":false,"headDiff":null,"independenceDegraded":false,'

    def _assert_refused_as_before(session_dir, damaged_bytes):
        out = RD.cmd_next(session_dir)
>       assert out == {"ok": False, "reason": REFUSAL}, out
E       AssertionError: {'ok': True, 'action': 'dispatch-panel', 'round': 1, 'phase': 'dispatch-panel', ...}
E       assert {'ok': True, ...h-panel', ...} == {'ok': False,... session dir'}
E         
E         Differing items:
E         {'ok': True} != {'ok': False}
E         Left contains 6 more items:
E         {'action': 'dispatch-panel',
E          'attempt': 0,
E          'expectedStateHash': 'e7c071afdc74ffee93a0543a4125c8b22945cf113b141c91f304fc6e50a0c8bf',...
E         
E         ...Full output truncated (80 lines hidden), use '-vv' to show

/home/user/wt-1869-wo3/plugins/superheroes/lib/tests/test_session_repair_c7l3.py:83: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_session_repair_c7l3.py::test_a_mirror_whose_state_does_not_hash_to_its_hash_is_refused_as_before
1 failed in 1.06s
```
- **Axis check:** the red is on the axis: a torn mirror was restored (`ok: True`, dispatch-panel)
  where the test requires the usual refusal.
- **Restore:** the inverse edit. **Restore receipt** (restored lines quoted back, and a byte compare
  of the file against its pre-neutralization copy printed `DIFF-EMPTY`):
```
    if hashlib.sha256(state_bytes).hexdigest() != obj.get("stateSha256"):
        return None
```
- **Raw green:**
```
.                                                                        [100%]
1 passed in 1.25s
```

## 2. The earlier-version gate on the mirror

- **Element and axis:** `_read_mirror_state`, the `_state_is_earlier_unfinished(state)` branch. A
  mirror of an unfinished earlier-version session is refused with the restart answer, never restored.
- **Node:** `plugins/superheroes/lib/tests/test_session_repair_c7l3.py::test_a_mirror_of_an_unfinished_earlier_version_session_gets_the_restart_refusal`
- **Collection:** `1 test collected in 0.51s`
- **Neutralization:** `if _state_is_earlier_unfinished(state):` became
  `if False and _state_is_earlier_unfinished(state):`
- **Raw red** (the earlier-version mirror was restored and the command carried on):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_mirror_of_an_unfinished_earlier_version_session_gets_the_restart_refusal _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-57/test_a_mirror_of_an_unfinished0')

    def test_a_mirror_of_an_unfinished_earlier_version_session_gets_the_restart_refusal(tmp_path):
        """axis: a mirror of an unfinished earlier-version session is refused with the restart answer,
        never restored — see bite-proof record c7l3_wo3_driver"""
        session_dir = _session(tmp_path)
        state = json.loads(_read(_state_path(session_dir)))
        assert not state.get("terminal")
        state["schemaVersion"] = RD.STATE_SCHEMA_VERSION - 1
        assert state["schemaVersion"] in RD.SUPPORTED_STATE_VERSIONS
        _forge_mirror(session_dir, state)
        _truncate(_state_path(session_dir))
        damaged = _read(_state_path(session_dir))
        out = RD.cmd_next(session_dir)
>       assert out["ok"] is False and out["reason"] == RD.SESSION_FROM_EARLIER_VERSION, out
E       AssertionError: {'ok': True, 'action': 'dispatch-panel', 'round': 1, 'phase': 'dispatch-panel', ...}
E       assert (True is False)

/home/user/wt-1869-wo3/plugins/superheroes/lib/tests/test_session_repair_c7l3.py:295: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_session_repair_c7l3.py::test_a_mirror_of_an_unfinished_earlier_version_session_gets_the_restart_refusal
1 failed in 1.25s
```
- **Axis check:** the red is on the axis: the earlier-version mirror was restored (`ok: True`) where
  the test requires `session-from-earlier-version`.
- **Restore:** the inverse edit. **Restore receipt** (byte compare against the copy printed
  `DIFF-EMPTY`; restored lines as `grep` printed them):
```
8081:    if _state_is_earlier_unfinished(state):
8082-        return state_bytes, state, True
```
- **Raw green:**
```
.                                                                        [100%]
1 passed in 4.99s
```

## 3. The state-write census

- **Element and axis:** the census over the driver source: no code writes the state file but through
  the one writer and the one stager, so no write site can skip its mirror.
- **Node:** `plugins/superheroes/lib/tests/test_session_repair_c7l3.py::test_no_code_writes_the_state_file_but_through_the_one_writer_and_the_one_stager`
- **Collection:** `1 test collected in 0.58s`
- **Neutralization:** an unused helper added before `_mirror_bytes`:
```
def _wo5_unused_state_writer(session_dir):
    with open(os.path.join(session_dir, STATE_FILE), "w") as fh:
        fh.write("{}")
```
- **Raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_no_code_writes_the_state_file_but_through_the_one_writer_and_the_one_stager _

    def test_no_code_writes_the_state_file_but_through_the_one_writer_and_the_one_stager():
        """axis: no write site of the state file can skip its mirror — the census names every function
        that writes it — see bite-proof record c7l3_wo3_driver"""
        with open(DRIVER_SOURCE, encoding="utf-8") as fh:
            writes = _all_state_writes_in(ast.parse(fh.read()))
>       assert set(writes) == {"_write_state_bytes", "_stage_state"}, writes
E       AssertionError: {'_wo5_unused_state_writer': [2257], '_stage_state': [2276], '_write_state_bytes': [2282]}
E       assert {'_stage_stat..._state_bytes'} == {'_stage_stat..._state_bytes'}
E         
E         Extra items in the left set:
E         '_wo5_unused_state_writer'
E         Use -v to get more diff

/home/user/wt-1869-wo3/plugins/superheroes/lib/tests/test_session_repair_c7l3.py:148: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_session_repair_c7l3.py::test_no_code_writes_the_state_file_but_through_the_one_writer_and_the_one_stager
1 failed in 0.93s
```
- **Axis check:** the red is on the axis: the census names the extra writing function.
- **Restore:** the inverse edit (the helper removed). **Restore receipt** (byte compare against the
  copy printed `DIFF-EMPTY`; `grep -n "_wo5_unused"` printed nothing; the lines around the
  insertion point):
```
2253-    return state
2254-
2255-
2256:def _mirror_bytes(session_dir, state_bytes):
```
- **Raw green:**
```
.                                                                        [100%]
1 passed in 0.88s
```

## 4. The "fix after the latest raise" condition

- **Element and axis:** `_credit_fixes_not_reraised`, the `raised_round <= fix_round` leg. A fix
  report made before the finding's latest raise says nothing about the raise after it.
- **Node:** `plugins/superheroes/lib/tests/test_later_panel_credit_c7l3.py::test_a_fix_reported_before_the_latest_raise_gives_no_credit`
- **Collection:** `1 test collected in 1.50s`
- **Neutralization:** `if any(raised_round <= fix_round < state["round"] and key in keys` became
  `if any(fix_round < state["round"] and key in keys`
- **Raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_________ test_a_fix_reported_before_the_latest_raise_gives_no_credit __________

    def test_a_fix_reported_before_the_latest_raise_gives_no_credit():
        """axis: a fix report made before the finding's latest raise says nothing about the raise after
        it — see bite-proof record c7l3_wo3_driver"""
        state = _round_one_state(_finding())
        _fix(state)                                   # fix reported in round 1
        _panel(state, raised=[_finding()])            # raised again in round 2
        state["round"] = 3                            # round 3's panel omits it; round 2 fixed nothing
        state["rounds"].setdefault("3", {})
        _panel(state)
        row = _ledger(state)[_key()]
        assert row["raisedRound"] == 2
>       assert "disposition" not in row and "dispositionReceipt" not in row
E       AssertionError: assert ('disposition' not in {'file': 'f.py', 'line': 1, 'title': 'Bug', 'severity': 'Important', ...})

/home/user/wt-1869-wo3/plugins/superheroes/lib/tests/test_later_panel_credit_c7l3.py:144: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_later_panel_credit_c7l3.py::test_a_fix_reported_before_the_latest_raise_gives_no_credit
1 failed in 1.48s
```
- **Axis check:** the red is on the axis: the finding re-raised in round 2 was credited from the
  round 1 fix report.
- **Restore:** the inverse edit. **Restore receipt** (the byte compare against the copy was refused by
  the sandbox from this entry on; the restored line as `grep` printed it, and the diffstat of the
  file against `HEAD` is unchanged at the integration order's `1 insertion(+), 20 deletions(-)`):
```
2797:        if any(raised_round <= fix_round < state["round"] and key in keys
```
- **Raw green:**
```
.                                                                        [100%]
1 passed in 1.73s
```

## 5. The complete-panel condition

- **Element and axis:** `_fold_panel`, the `not incomplete` leg guarding the credit. Only a complete
  panel can confirm a fix by silence.
- **Node:** `plugins/superheroes/lib/tests/test_later_panel_credit_c7l3.py::test_an_incomplete_panel_gives_no_credit`
- **Collection:** `1 test collected in 1.83s`
- **Neutralization:** `if state["round"] >= 2 and not incomplete:` (the line above
  `_credit_fixes_not_reraised(state, compiled)`) became `if state["round"] >= 2:`
- **Raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
___________________ test_an_incomplete_panel_gives_no_credit ___________________

    def test_an_incomplete_panel_gives_no_credit():
        """axis: only a complete panel can confirm a fix by silence — an incomplete one may simply not have
        looked — see bite-proof record c7l3_wo3_driver"""
        state = _round_one_state(_finding())
        _fix(state)
        absent = next(d for d in RD._panel_dimensions(state["config"]) if d != "code-reviewer")
        _panel(state, missing=(absent,))
        assert state["fullPanelRan"] is False
        row = _ledger(state)[_key()]
>       assert "disposition" not in row and "dispositionReceipt" not in row
E       AssertionError: assert ('disposition' not in {'file': 'f.py', 'line': 1, 'title': 'Bug', 'severity': 'Important', ...})

/home/user/wt-1869-wo3/plugins/superheroes/lib/tests/test_later_panel_credit_c7l3.py:111: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_later_panel_credit_c7l3.py::test_an_incomplete_panel_gives_no_credit
1 failed in 1.58s
```
- **Axis check:** the red is on the axis: a panel with a missing seat (`fullPanelRan` false)
  credited the fix.
- **Restore:** the inverse edit. **Restore receipt** (as entry 4: byte compare unavailable; the
  restored lines as `grep` printed them, the credit site at 3002):
```
3001:    # axis: only a complete panel can confirm a fix by silence — an incomplete one may simply not have looked — see bite-proof record c7l3_wo3_driver
3002:    if state["round"] >= 2 and not incomplete:
3003-        _credit_fixes_not_reraised(state, compiled)
```
- **Raw green:**
```
.                                                                        [100%]
1 passed in 1.55s
```

## 6. The unseatable-grouping path keeps every verified finding

- **Element and axis:** `_fold_verifiers`, the unseatable-synthesis branch into
  `_fold_synthesis(state, config, {"grouping": None})`. An unseatable synthesis seat folds no
  grouping, so every verified finding survives the fold.
- **Node:** `plugins/superheroes/lib/tests/test_synthesis_seat_1858.py::test_c1_library_unseatable_synthesis_drops_nothing`
- **Collection:** `1 test collected in 2.05s`
- **Neutralization:** one line added in that branch, before the `_fold_synthesis` call:
  `state["_verified"] = (state.get("_verified") or [])[:1]`
- **Raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
______________ test_c1_library_unseatable_synthesis_drops_nothing ______________

monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7f6d33508320>

    def test_c1_library_unseatable_synthesis_drops_nothing(monkeypatch):
        """The unseatable-grouping path (`_nonpanel_unseatable(state, session_dir, P_SYNTHESIS)` into
        `_fold_synthesis(state, config, {"grouping": None})`) keeps both verified findings, separate.
    
        axis: an unseatable synthesis seat folds no grouping, so every verified finding survives the fold
        — see bite-proof record c7l3_wo3_driver"""
        two = [dict(_A_FINDING[0]), dict(_A_FINDING[0], line=2)]
        calls = []
        result, loop_receipt, state = _lib_run(
            monkeypatch, "cursor", lambda findings, rnd: calls.append(rnd), "cursor", findings=two,
            **_VERIFIER_ONLY)
        assert calls == []
        assert state["rounds"]["1"]["synthesisUnseatable"]
        assert state["rounds"]["1"]["merges"] == []
        ledger = {RD.session_contract.finding_identity_key(e): e
                  for e in state[RD.session_contract.DISPOSITION_LEDGER_KEY]}
        assert sorted(ledger) == ["f.py::bug@L1", "f.py::bug@L2"], sorted(ledger)
        # both reached the fixer and were audited: a finding dropped at the fold would be settled instead
>       assert [ledger[k]["disposition"] for k in sorted(ledger)] == ["fixed", "fixed"], ledger
E       AssertionError: {'f.py::bug@L1': {'title': 'bug', 'severity': 'Important', 'file': 'f.py', 'line': 1, ...}, 'f.py::bug@L2': {'title': 'bug', 'severity': 'Important', 'file': 'f.py', 'line': 2, ...}}
E       assert ['fixed', 'left-for-owner'] == ['fixed', 'fixed']
E         
E         At index 1 diff: 'left-for-owner' != 'fixed'
E         Use -v to get more diff

plugins/superheroes/lib/tests/test_synthesis_seat_1858.py:207: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_synthesis_seat_1858.py::test_c1_library_unseatable_synthesis_drops_nothing
1 failed in 1.99s
```
- **Axis check:** the red is on the axis: the finding dropped at the fold settled as
  `left-for-owner` instead of reaching the fixer (`fixed`).
- **Restore:** the inverse edit (the added line removed). **Restore receipt** (as entry 4: byte
  compare unavailable; the restored lines as `grep` printed them):
```
3342:                  "no synthesis seat outside the makers' families on a proven cell; findings not grouped")
3343-        _fold_synthesis(state, config, {"grouping": None})
3344-        return
```
- **Raw green:**
```
.                                                                        [100%]
1 passed in 1.93s
```
