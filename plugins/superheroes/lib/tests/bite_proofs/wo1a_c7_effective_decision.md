# Bite-proof record — one effective decision per finding (test_effective_decision_c7.py)

Five entries, one per declared guarded element (BP-4 re-run and BP-5 added in review round 6). Each ran with the detector unedited, against HEAD
`5eb23f5b`, as a targeted edit to `plugins/superheroes/lib/round_driver.py` restored by the exact
inverse edit (no `git checkout`, `restore`, `reset` or `stash`). The BP-4 re-run and BP-5 ran
against HEAD `e7e5840d` plus the uncommitted round-6 fix, the same way. Every run used:

`python3 -B -X pycache_prefix=/tmp/claude-0/pyc -m pytest plugins/superheroes/lib/tests/test_effective_decision_c7.py -q -n 0 -k <test name>`

Nothing in the captures is redacted (no secrets, tokens, private URLs or PII appear). Every capture is
well under the 32 KiB per-element ceiling. Each green run follows the restore; the closing run of the
whole file and the post-restore `git diff` are at the end.

## BP-1 — the lineage write in `_stage_findings` (the `_LineageCarry` carry)

- guarded element: `_LineageCarry.apply`, `round_driver.py:1631-1650`, reached from `_stage_findings`
  at `round_driver.py:1677`.
- axis: a reworded finding at the decided file and line takes the decision (the lineage is written).
- detector: `test_t1_reword_carries_guidance_to_next_fix`
- neutralization (line 1633): the carry condition is never false, so `apply` always returns before the
  write.
  - before: `        if not self.readable or key in self.decided or key in lineage:`
  - after:  `        if True or not self.readable or key in self.decided or key in lineage:`
  - This differs from the earlier plan (a `return` before the write). The edit instead makes the guard
    unconditionally take the early return, so the carry condition is never true. Both reach the write.

Raw red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
_________________ test_t1_reword_carries_guidance_to_next_fix __________________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-0/test_t1_reword_carries_guidanc0')

    def test_t1_reword_carries_guidance_to_next_fix(tmp_path):
        """axis: a ruling recorded with its location binds a reworded finding at the next fixer order.
    
        bite-proof: plugins/superheroes/lib/tests/bite_proofs/wo1a_c7_effective_decision.md (BP-1)
        """
        session_dir, _, _, row_a, _row_b = RC._pending_fixer_two_findings(tmp_path)
        key_a = RD._fix_batch_row_key(row_a)
        path = RC._write_ruling_file(tmp_path / "r.json", [
            {"id": key_a, "ruling": "guidance", "reason": "keep it small", "guidance": "G1"}])
        assert RC._rule(session_dir, path)["ok"]
        state = RC._state(session_dir)
        logged = state["rulingsLog"][-1]
        assert (logged["file"], logged["line"]) == (row_a["file"], row_a["line"])
        state["round"] += 1
        reworded = _finding("bounds A, said differently", line=row_a["line"], file=row_a["file"])
        key_new = RD._finding_identity_key(reworded)
        assert key_new != key_a
        RD._stage_findings(state, [reworded])
>       assert state["findingLineage"] == {key_new: key_a}
               ^^^^^^^^^^^^^^^^^^^^^^^
E       KeyError: 'findingLineage'

/home/user/wt-1868/plugins/superheroes/lib/tests/test_effective_decision_c7.py:115: KeyError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_effective_decision_c7.py::test_t1_reword_carries_guidance_to_next_fix
1 failed, 20 deselected in 2.35s
```

The red is on the claimed axis: the first assertion after `_stage_findings` finds no `findingLineage`
at all, so the carry did not write.

- restore: the exact inverse edit, `if True or not self.readable ...` back to
  `if not self.readable or key in self.decided or key in lineage:`.
- restore receipt: `round_driver.py:1633` reads
  `        if not self.readable or key in self.decided or key in lineage:`. The final
  `git diff -- plugins/superheroes/lib/round_driver.py` is empty (below).

Raw green:

```
.                                                                        [100%]
1 passed, 20 deselected in 2.67s
```

## BP-2 — lineage resolution in the reader (latest across the group)

- guarded element: `_effective_decisions`, `round_driver.py:1857-1889` (the `_lineage_root` resolution
  in both loops and the group fan-out).
- axis: the original wording reads the newest decision given on any member of its group.
- detector: `test_t2_replaced_guidance_never_returns`
- neutralization: resolve per exact key only, by emptying the lineage the reader consults. One line
  inserted directly after `    lineage = _lineage_map(state)` at line 1870 of `_effective_decisions`
  (the 4-space-indented occurrence, not the one in `_LineageCarry.apply`):
  `    lineage = {}`
  Every `_lineage_root(lineage, key)` in the reader then returns `key` itself.

Raw red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
___________________ test_t2_replaced_guidance_never_returns ____________________

    def test_t2_replaced_guidance_never_returns():
        """axis: a ruling given on the reworded key is the group's decision; the original wording reads it.
    
        bite-proof: plugins/superheroes/lib/tests/bite_proofs/wo1a_c7_effective_decision.md (BP-2)
        """
        state = _mem_state(2)
        key_f = _key("original wording")
        _add_rule(state, key_f, "guidance", guidance="G1", rnd=1)
        reworded = _finding("reworded wording")
        key_k = RD._finding_identity_key(reworded)
        RD._stage_findings(state, [reworded])
        assert state["findingLineage"] == {key_k: key_f}
        _add_rule(state, key_k, "guidance", guidance="G2")
        state["round"] = 3
        original = _finding("original wording")
        RD._stage_findings(state, [original])
        assert state["findingLineage"] == {key_k: key_f}
>       assert RD._live_ruling_by_key(state)[key_f]["guidance"] == "G2"
E       AssertionError: assert 'G1' == 'G2'
E         
E         - G2
E         + G1

/home/user/wt-1868/plugins/superheroes/lib/tests/test_effective_decision_c7.py:147: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_effective_decision_c7.py::test_t2_replaced_guidance_never_returns
1 failed, 20 deselected in 1.45s
```

The red is on the claimed axis, and only past the lineage-write assertions (lines 141 and 146 passed,
so the lineage is still written): the original wording reads the replaced guidance `G1` instead of
the group's latest `G2`.

- restore: delete the inserted `    lineage = {}` line.
- restore receipt: `round_driver.py:1870-1871` reads `    lineage = _lineage_map(state)` followed by
  `    best = {}`. The final `git diff` is empty (below).

Raw green:

```
.                                                                        [100%]
1 passed, 20 deselected in 1.38s
```

## BP-3 — the single-entry rendering in `_gate_guidance_entries`

- guarded element: `_gate_guidance_entries`, `round_driver.py:3747-3835`: the effectiveness test on the
  current-round gate loop and the `covered_keys` skip on the rule-channel loop together make one
  effective decision render one entry.
- axis: only the effective decision renders; a replaced one never does.
- detector: `test_t3_precedence_latest_decision_renders_alone`
- neutralization: two edits that together let both sources render. Edits 1 and 2 are one
  neutralization.
  1. The gate-loop effectiveness test (`round_driver.py:3800-3803`) replaced by a never-true test.
     - before:
       ```
                       if (live is None or live.get("source") != "gate" or live.get("findingKey") != key
                               or str(live.get("round")) != str(rnd)
                               or live.get("guidance") != guidance.strip()):
                           continue
       ```
     - after:
       ```
                       if False:
                           continue
       ```
  2. The rule-channel dedupe (`round_driver.py:3810-3811`).
     - before: `        if key in covered_keys:` / `            continue`
     - after:  `        if False:` / `            continue`
  - Edit 1 alone would still show a single entry (the gate one). Edit 2 is what lets the rule row render
    as well, so both sources render.

Raw red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
_______________ test_t3_precedence_latest_decision_renders_alone _______________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-4/test_t3_precedence_latest_deci0')

    def test_t3_precedence_latest_decision_renders_alone(tmp_path):
        """axis: gate guidance and rule guidance on one key render one text — the later by one sequence.
    
        bite-proof: plugins/superheroes/lib/tests/bite_proofs/wo1a_c7_effective_decision.md (BP-3)
        """
        # gate guidance "A", then a rule guidance "B" -> only "B"
        session_dir = L2E._parked_judgment_session(tmp_path, name="gate-then-rule")
        out = L2E._pending_submit(session_dir, {"dispositions": [
            {"id": L2E._TRADEOFF_ID, "disposition": "fix-with-guidance", "guidance": "A"}]})
        assert out["ok"] is True, out
        state = L2E._load_state(session_dir)
        key = L2E._TRADEOFF_ID
        gate_rows = state["rounds"][str(state["round"])]["judgmentDispositions"]
        assert gate_rows[0]["rulingSeq"] == state["rulingSeqCounter"]
        assert key in {RD._fix_batch_row_key(r) for r in state["_fixBatch"]}
        _add_rule(state, key, "guidance", guidance="B", file="f.py", line=1)
        entries = _entries(state)
>       assert [(e["id"], e["guidance"], bool(e.get("rulingChannel"))) for e in entries] == [
            (key, "B", True)]
E       AssertionError: assert [('f.py::wide...', 'B', True)] == [('f.py::wide...', 'B', True)]
E         
E         At index 0 diff: ('f.py::widen the api@L1', 'A', False) != ('f.py::widen the api@L1', 'B', True)
E         Left contains one more item: ('f.py::widen the api@L1', 'B', True)
E         Use -v to get more diff

/home/user/wt-1868/plugins/superheroes/lib/tests/test_effective_decision_c7.py:172: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_effective_decision_c7.py::test_t3_precedence_latest_decision_renders_alone
1 failed, 20 deselected in 1.45s
```

The red is on the claimed axis: the replaced gate guidance `A` renders first and the effective rule
guidance `B` renders after it ("Left contains one more item"), so two entries come out where one is
required.

- restore: the exact inverse of both edits (edit 1's `if False:` / `continue` back to the four-line
  effectiveness test; edit 2's `if False:` back to `if key in covered_keys:`).
- restore receipt: `round_driver.py:3800-3803` and `3810-3811` read as in the "before" blocks above.
  The final `git diff` is empty (below).

Raw green:

```
.                                                                        [100%]
1 passed, 20 deselected in 1.38s
```

## BP-4 — the gate-skip candidate in the reader

Re-run in review round 6 (the owner-gate ruling narrowed the carry to guidance), against the
revised detector; the earlier capture against `test_t4_gate_skip_binds_a_reword` is superseded
because that detector asserted a skip carries to a reword, which the narrowed carry no longer does.

- guarded element: `_gate_decision_candidates`, the `skip` arm (`round_driver.py:1929-1930`).
- axis: an owner-gate `skip` is a decision on its own finding — restaged, the finding stays
  out of scope.
- detector: `test_t4_gate_skip_binds_its_finding_but_never_a_reword`
- neutralization: drop gate `skip` candidates.
  - before: `            if disposition == "skip":` / `                ruling = "out-of-scope"`
  - after:  `            if disposition == "skip":` / `                continue`

Raw red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
____________ test_t4_gate_skip_binds_its_finding_but_never_a_reword ____________

tmp_path = PosixPath('/tmp/pytest-of-root/pytest-96/test_t4_gate_skip_binds_its_fi0')

    def test_t4_gate_skip_binds_its_finding_but_never_a_reword(tmp_path):
        """axis: an owner-gate skip is a decision on its own finding (restaged, it stays skipped and is
        not put to the owner again) — and it never carries: a later, different finding at the skipped
        location is judged fresh and reaches the fix batch.
    
        bite-proof: plugins/superheroes/lib/tests/bite_proofs/wo1a_c7_effective_decision.md (BP-4, BP-5)
        """
        session_dir = L2E._parked_judgment_session(tmp_path)
        out = L2E._pending_submit(session_dir, {"dispositions": [
            {"id": L2E._TRADEOFF_ID, "disposition": "skip", "reason": "product choice",
             "followUp": dict(L2E._WELL_FORMED)}]})
        assert out["ok"] is True, out
        state = L2E._load_state(session_dir)
        skip_row = state["rounds"][str(state["round"])]["judgmentDispositions"][0]
        assert (skip_row["file"], skip_row["line"]) == ("f.py", 1)
        assert skip_row["rulingSeq"] == state["rulingSeqCounter"]
        assert skip_row["followUp"] == L2E._WELL_FORMED
        base = copy.deepcopy(state)
        # the skipped finding itself, restaged a round later: the whole decision, follow-up included
        state["round"] += 1
        original = _finding("widen the API", line=1, file="f.py", tradeoff=True)
        RD._stage_findings(state, [original])
        restaged = L2E._ledger_by_key(state)[L2E._TRADEOFF_ID]
>       assert restaged["disposition"] == "out-of-scope"
               ^^^^^^^^^^^^^^^^^^^^^^^
E       KeyError: 'disposition'

/home/user/wt-l2a/plugins/superheroes/lib/tests/test_effective_decision_c7.py:216: KeyError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_effective_decision_c7.py::test_t4_gate_skip_binds_its_finding_but_never_a_reword
1 failed, 33 deselected in 1.43s
```

The red is on the claimed axis: the gate-fold assertions before it passed, so the skip was
recorded; with the candidate dropped the restaged finding carries no out-of-scope disposition.

- restore: `continue` changed back to `ruling = "out-of-scope"` by the exact inverse edit.

Raw green:

```
.                                                                        [100%]
1 passed, 33 deselected in 1.46s
```

## BP-5 — only a guidance decision carries (`_LineageCarry.apply`)

- guarded element: the guidance-only check in `_LineageCarry.apply` (`round_driver.py:1682`).
- axis: a skip — an owner-gate skip or a `rule` out-of-scope ruling — never carries to a later,
  different finding at the decided location; that finding is judged fresh and reaches the fix batch.
- detectors: `test_t4_gate_skip_binds_its_finding_but_never_a_reword`,
  `test_a_rule_out_of_scope_ruling_never_carries_to_a_reword`
- neutralization: let an out-of-scope decision carry again.
  - before: `        if not isinstance(effective, dict) or effective.get("ruling") != "guidance":`
  - after:  `        if not isinstance(effective, dict) or effective.get("ruling") not in ("guidance", "out-of-scope"):`

Run: `python3 -B -X pycache_prefix=/tmp/claude-0/pyc -m pytest plugins/superheroes/lib/tests/test_effective_decision_c7.py -q -n 0 -p no:cacheprovider -k "test_t4_gate_skip_binds_its_finding_but_never_a_reword or test_a_rule_out_of_scope_ruling_never_carries_to_a_reword"`

Raw red:

```
FF                                                                       [100%]
=================================== FAILURES ===================================
____________ test_t4_gate_skip_binds_its_finding_but_never_a_reword ____________

tmp_path = PosixPath('/tmp/pytest-of-root/pytest-94/test_t4_gate_skip_binds_its_fi0')

    def test_t4_gate_skip_binds_its_finding_but_never_a_reword(tmp_path):
        """axis: an owner-gate skip is a decision on its own finding (restaged, it stays skipped and is
        not put to the owner again) — and it never carries: a later, different finding at the skipped
        location is judged fresh and reaches the fix batch.
    
        bite-proof: plugins/superheroes/lib/tests/bite_proofs/wo1a_c7_effective_decision.md (BP-4, BP-5)
        """
        session_dir = L2E._parked_judgment_session(tmp_path)
        out = L2E._pending_submit(session_dir, {"dispositions": [
            {"id": L2E._TRADEOFF_ID, "disposition": "skip", "reason": "product choice",
             "followUp": dict(L2E._WELL_FORMED)}]})
        assert out["ok"] is True, out
        state = L2E._load_state(session_dir)
        skip_row = state["rounds"][str(state["round"])]["judgmentDispositions"][0]
        assert (skip_row["file"], skip_row["line"]) == ("f.py", 1)
        assert skip_row["rulingSeq"] == state["rulingSeqCounter"]
        assert skip_row["followUp"] == L2E._WELL_FORMED
        base = copy.deepcopy(state)
        # the skipped finding itself, restaged a round later: the whole decision, follow-up included
        state["round"] += 1
        original = _finding("widen the API", line=1, file="f.py", tradeoff=True)
        RD._stage_findings(state, [original])
        restaged = L2E._ledger_by_key(state)[L2E._TRADEOFF_ID]
        assert restaged["disposition"] == "out-of-scope"
        assert restaged["followUp"] == L2E._WELL_FORMED
        assert RD._filter_excluded_discharged_fixes(state, [original]) == ([], None)
        # normal routing honors it: never put to the owner again
        state["findings"] = [dict(original, verdict="CONFIRMED")]
        RD._after_findings_settled(state, state["config"])
        assert state["step"] != RD.P_JUDGMENT
        assert not state.get("_judgmentFindings")
        assert any(d["kind"] == "fix-batch-excluded" for d in state["decisions"])
        # the review record's rulings list stays rule-sourced only
        assert RD._standing_rulings_for_orders(state) == ([], None)
        # a later, different finding at the skipped location is judged fresh: it reaches the fix batch
        state = base
        state["round"] += 1
        different = _finding("widen the public API", line=1, file="f.py")
        key_new = RD._finding_identity_key(different)
        RD._stage_findings(state, [different])
>       assert key_new not in (state.get("findingLineage") or {})
E       AssertionError: assert 'f.py::widen the public api@L1' not in (({'f.py::widen the public api@L1': 'f.py::widen the api@L1'}))
E        +  where {'f.py::widen the public api@L1': 'f.py::widen the api@L1'} = <built-in method get of dict object at 0x7f48d075e6c0>('findingLineage')
E        +    where <built-in method get of dict object at 0x7f48d075e6c0> = {'_changedSubjectsSincePanel': [], '_coverage': [], '_incompletePanel': False, '_receiptFault': None, ...}.get

/home/user/wt-l2a/plugins/superheroes/lib/tests/test_effective_decision_c7.py:233: AssertionError
__________ test_a_rule_out_of_scope_ruling_never_carries_to_a_reword ___________

    def test_a_rule_out_of_scope_ruling_never_carries_to_a_reword():
        """axis: a rule out-of-scope ruling binds its own finding only — a reworded finding at its
        location is judged fresh and is not excluded from the fix batch."""
        state = _mem_state()
        _add_rule(state, _key("original"), "out-of-scope", rnd=1)
        reworded = _finding("reworded")
        RD._stage_findings(state, [reworded])
>       _no_carry(state)

/home/user/wt-l2a/plugins/superheroes/lib/tests/test_effective_decision_c7.py:531: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

state = {'schemaVersion': 5, 'sessionGeneration': 4, 'config': {'leg': 'code', 'panel': False, 'code': True, 'vendors': ['claude', 'codex'], ...}, 'round': 2, ...}

    def _no_carry(state):
>       assert not state.get("findingLineage")
E       AssertionError: assert not {'a.py::reworded@L10': 'a.py::original@L10'}
E        +  where {'a.py::reworded@L10': 'a.py::original@L10'} = <built-in method get of dict object at 0x7f48d0753140>('findingLineage')
E        +    where <built-in method get of dict object at 0x7f48d0753140> = {'schemaVersion': 5, 'sessionGeneration': 4, 'config': {'leg': 'code', 'panel': False, 'code': True, 'vendors': ['claude', 'codex'], ...}, 'round': 2, ...}.get

/home/user/wt-l2a/plugins/superheroes/lib/tests/test_effective_decision_c7.py:93: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_effective_decision_c7.py::test_t4_gate_skip_binds_its_finding_but_never_a_reword
FAILED plugins/superheroes/lib/tests/test_effective_decision_c7.py::test_a_rule_out_of_scope_ruling_never_carries_to_a_reword
2 failed, 32 deselected in 1.49s
```

Both reds are on the claimed axis: with the narrowing neutralized, the different finding is written
into `findingLineage` under the skipped finding (gate skip) and under the out-of-scope ruling.

- restore: the exact inverse edit; line 1682 reads
  `        if not isinstance(effective, dict) or effective.get("ruling") != "guidance":` again.

Raw green:

```
..                                                                       [100%]
2 passed, 32 deselected in 1.50s
```

## Closing evidence (after the last restore)

Whole-file run, `python3 -B -X pycache_prefix=/tmp/claude-0/pyc -m pytest plugins/superheroes/lib/tests/test_effective_decision_c7.py -q -n 0 -p no:cacheprovider`:

```
..................................                                       [100%]
34 passed in 3.21s
```

The BP-4 and BP-5 edits were each restored by the exact inverse edit before this run; the only
remaining `round_driver.py` change at that point was the uncommitted round-6 fix itself.

## What is NOT proven by this record

The fail-closed edge tests (`test_t5` .. `test_t11`) and the extra tests have no recorded
neutralization; the declared set is exactly the five elements above.
