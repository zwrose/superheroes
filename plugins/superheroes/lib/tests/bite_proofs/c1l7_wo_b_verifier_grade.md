# C1-L7 WO-B verifier-grade bite-proof

Detector: `plugins/superheroes/lib/tests/test_verifier_grade_c1l7.py` (33 tests). Four guarded elements, G1 to G4,
declared by the order. One neutralization, one red and one green per element, each by a targeted edit undone by
the inverse edit. Every run used this command from the worktree root:

```
scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-wo-b -m pytest plugins/superheroes/lib/tests/test_verifier_grade_c1l7.py -q -n 4
```

Redaction: none needed; the captures hold no secrets, tokens or private URLs. The `UV_NATIVE_TLS` warning line and
the `bringing up nodes...` lines are kept as printed.

Restore receipt shape: the neutralized files are tracked and the committed head `a818bd6c` holds the graded code, so
after each restore `git status --porcelain <file>` and `git diff --stat` print nothing (empty output is the clean
result), and the restored lines are quoted back.

## G1 — the drop-branch `wrong` stamp

**Guarded element:** `plugins/superheroes/lib/verification.py:191` (the `"grade": {"verdict": "wrong", ...}` line in the
`drops.append` branch of `apply_verdicts`). Axis: a REFUTED that executed and gave a reason is graded `wrong`.

**Neutralization:** deleted the line

```python
                "grade": {"verdict": "wrong", "reason": reason.strip()},
```

**Raw red** (2 failed, 31 passed; the truth-table row and the driver fold ledger assertion):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
bringing up nodes...
bringing up nodes...

............F..................F.                                        [100%]
=================================== FAILURES ===================================
________ test_g1_executed_refuted_with_reason_drops_with_a_wrong_grade _________
[gw0] linux -- Python 3.12.13 /root/.cache/uv/builds-v0/.tmpTBgCTo/bin/python

    def test_g1_executed_refuted_with_reason_drops_with_a_wrong_grade():
        out = _apply({"id": "v0", "verdict": "REFUTED", "reason": "  the guard at line 40 returns early  "})
        assert out["findings"] == []
        assert len(out["drops"]) == 1
>       _assert_grade(out["drops"][0]["grade"], "wrong", "the guard at line 40 returns early")
                      ^^^^^^^^^^^^^^^^^^^^^^^^
E       KeyError: 'grade'

/home/user/wt-2211-b/plugins/superheroes/lib/tests/test_verifier_grade_c1l7.py:55: KeyError
_ test_g1_g3_the_driver_fold_grades_every_judged_finding_and_keeps_the_refuted_one_out_of_the_fix _
[gw1] linux -- Python 3.12.13 /root/.cache/uv/builds-v0/.tmpTBgCTo/bin/python

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-10/popen-gw1/test_g1_g3_the_driver_fold_gra0')

    def test_g1_g3_the_driver_fold_grades_every_judged_finding_and_keeps_the_refuted_one_out_of_the_fix(tmp_path):
        snapshots, final = _fold_drive(tmp_path)
        after_verify = snapshots[RD.P_SYNTHESIS]
        keys = {name: SC.finding_identity_key(f) for name, f in
                (("confirmed", _CONFIRMED), ("plausible", _PLAUSIBLE), ("refuted", _REFUTED))}
        ledger = _ledger(after_verify)
    
        refuted_row = ledger[keys["refuted"]]
        assert refuted_row["disposition"] == "refuted", refuted_row
>       _assert_grade(refuted_row["grade"], "wrong", _REFUTED_REASON)
                      ^^^^^^^^^^^^^^^^^^^^
E       KeyError: 'grade'

/home/user/wt-2211-b/plugins/superheroes/lib/tests/test_verifier_grade_c1l7.py:221: KeyError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_verifier_grade_c1l7.py::test_g1_executed_refuted_with_reason_drops_with_a_wrong_grade
FAILED plugins/superheroes/lib/tests/test_verifier_grade_c1l7.py::test_g1_g3_the_driver_fold_grades_every_judged_finding_and_keeps_the_refuted_one_out_of_the_fix
2 failed, 31 passed in 1.98s
```

**Restore:** inverse edit, re-inserted the deleted line after the axis comment.

**Restore receipt:** `git status --porcelain plugins/superheroes/lib/verification.py` and `git diff --stat` printed
nothing. Restored lines, `verification.py:190-192`:

```python
                # axis: a REFUTED that executed and gave a reason is graded wrong — see bite-proof record c1l7_wo_b_verifier_grade
                "grade": {"verdict": "wrong", "reason": reason.strip()},
            })
```

**Raw green:**

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
bringing up nodes...
bringing up nodes...

.................................                                        [100%]
33 passed in 2.57s
```

## G2 — no grade on silence

**Guarded element:** `plugins/superheroes/lib/verification.py:128-130` (`_grade`, the `reason_text is None` early
`return None`). Axis: a silent, reasonless, ambiguous or unknown verdict earns no grade.

**Neutralization:** graded silence `plausible`, replacing `return None` under `if reason_text is None:` with

```python
        return {"verdict": "plausible", "reason": "silent"}
```

**Raw red — INCOMPLETE.** The harness truncated this output in the middle (`... [10224 characters truncated] ...`).
What follows is exactly the output I received; the missing middle is lost, not reconstructed. The visible parts
include the final summary, which lists all 14 failures, the silent-verdict row
(`test_g2_a_silent_verdict_carries_no_grade`) among them.

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
bringing up nodes...
bringing up nodes...

.........FFFFFFFF..FFFFF...F.....                                        [100%]
=================================== FAILURES ===================================
_____ test_g2_an_unknown_or_reasonless_verdict_carries_no_grade[verdict2] ______
[gw3] linux -- Python 3.12.13 /root/.cache/uv/builds-v0/.tmpmSKGYb/bin/python

verdict = {'id': 'v0', 'verdict': 'CONFIRMED', 'reason': '   ', 'evidence': 'ran'}

    @pytest.mark.parametrize("verdict", [
        {"id": "v0", "verdict": "BOGUS", "reason": "hmm"},
        {"id": "v0", "verdict": "CONFIRMED", "reason": "", "evidence": "ran"},
        {"id": "v0", "verdict": "CONFIRMED", "reason": "   ", "evidence": "ran"},
        {"id": "v0", "verdict": "CONFIRMED", "evidence": "ran"},
        {"id": "v0", "verdict": "PLAUSIBLE", "reason": ""},
        {"id": "v0", "verdict": "PLAUSIBLE"},
        {"id": "v0", "verdict": "REFUTED", "reason": ""},
        {"id": "v0", "verdict": "REFUTED", "reason": "   "},
        {"id": "v0", "verdict": "REFUTED"},
        {"id": "v0", "verdict": "REFUTED", "reason": "", "evidence": "sh: vitest: command not found"},
    ])
    def test_g2_an_unknown_or_reasonless_verdict_carries_no_grade(verdict):
        out = _apply(verdict, grade={"verdict": "wrong", "reason": "seat said so"})
        assert out["drops"] == []
        assert len(out["findings"]) == 1
>       assert "grade" not in out["findings"][0], out["findings"][0]
E       AssertionError: {'file': 'a.py', 'line': 1, 'title': 'bug', 'severity': 'Important', ...}
E       assert 'grade' not in {'file': 'a.py', 'line': 1, 'title': 'bug', 'severity': 'Important', ...}

/home/user/wt-2211-b/plugins/superheroes/lib/tests/test_verifier_grade_c1l7.py:125: AssertionError
_____ test_g2_an_unknown_or_reasonless_verdict_carries_no_grade[verdict4] ______
[gw3] linux -- Python 3.12.13 /root/.cache/uv/builds-v0/.tmpmSKGYb/bin/python

verdict = {'id': 'v0', 'verdict': 'PLAUSIBLE', 'reason': ''}

    @pytest.mark.parametrize("verdict", [
        {"id": "v0", "verdict": "BOGUS", "reason": "hmm"},
        {"id": "v0", "verdict": "CONFIRMED", "reason": "", "evidence": "ran"},
        {"id": "v0", "verdict": "CONFIRMED", "reason": "   ", "evidence": "ran"},
        {"id": "v0", "verdict": "CONFIRMED", "evidence": "ran"},
        {"id": "v0", "verdict": "PLAUSIBLE", "reason": ""},
        {"id": "v0", "verdict": "PLAUSIBLE"},
        {"id": "v0", "verdict": "REFUTED", "reason": ""},
        {"id": "v0", "verdict": "REFUTED", "reason": "   "},
        {"id": "v0", "verdict": "REFUTED"},
        {"id": "v0", "verdict": "REFUTED", "reason": "", "evidence": "sh: vitest: command not found"},
    ])
    def test_g2_an_unknown_or_reasonless_verdict_carries_no_grade(verdict):
        out = _apply(verdict, grade={"verdict": "wrong", "reason": "seat said so"})
        assert out["drops"] == []
        assert len(out["findings"]) == 1
>       assert "grade" not in out["findings"][0], out["findings"][0]
E       AssertionError: {'file': 'a.py', 'line': 1, 'title': 'bug', 'severity': 'Important', ...}
E       assert 'grade' not in {'file': 'a.py', 'line': 1, 'title': 'bug', 'severity': 'Important', ...}

/home/user/wt-2211-b/plugins/superheroes/lib/tests/test_verifier_grade_c1l7.py:125: AssertionError
__________________ test_g2_a_silent_verdict_carries_no_grade ___________________
[gw2] linux -- Python 3.12.13 /root/.cache/uv/builds-v0/.tmpmSKGYb/bin/python

    def test_g2_a_silent_verdict_carries_no_grade():
        out = _apply(None)
>       assert "grade" not in out["findings"][0]
E       AssertionError: assert 'grade' not in {'file': 'a.py', 'line': 1, 'title': 'bug', 'severity': 'Important', ...}

/home/user/wt-2211-b/plugins/superheroes/lib/tests/test_verifier_grade_c1l7.py:99: AssertionError
_____ test_g2_an_unknown_or_reasonless_verdict_carries_no_grade[verdict7] ______
[gw3] linux -- Python 3.12.13 /root/.cache/uv/builds-v0/.tmpmSKGYb/bin/python

verdict = {'id': 'v0', 'verdict': 'REFUTED', 'reason': '   '}

    @pytest.mark.parametrize("verdict", [
        {"id": "v0", "verdict": "BOGUS", "reason": "hmm"},
        {"id": "v0", "verdict": "CONFIRMED", "reason": "", "evidence": "ran"},
        {"id": "v0", "verdict": "CONFIRMED", "reason": "   ", "evidence": "ran"},
        {"id": "v0", "verdict": "CONFIRMED", "evidence": "ran"},
        {"id": "v0", "verdict": "PLAUSIBLE", "reason": ""},
        {"id": "v0", "verdict": "PLAUSIBLE"},
        {"id": "v0", "verdict": "REFUTED", "reason": ""},
        {"id": "v0", "verdict": "REFUTED", "reason": "   "},
        {"id": "v0", "verdict": "REFUTED"},
        {"id": "v0", "verdict": "REFUTED", "reason": "", "evidence": "sh: vitest: command not found"},
    ])
    def test_g2_an_unknown_or_reasonless_verdict_carries_no_grade(verdict):
        out = _apply(verdict, grade={"verdict

... [10224 characters truncated] ...

ug', 'severity': 'Important', ...}

/home/user/wt-2211-b/plugins/superheroes/lib/tests/test_verifier_grade_c1l7.py:125: AssertionError
___________ test_g2_an_unmatched_verdict_leaves_the_finding_ungraded ___________
[gw0] linux -- Python 3.12.13 /root/.cache/uv/builds-v0/.tmpmSKGYb/bin/python

    def test_g2_an_unmatched_verdict_leaves_the_finding_ungraded():
        out = _apply({"id": "v99", "verdict": "PLAUSIBLE", "reason": "wrong id"})
        assert out["unmatched"] == ["v99"]
>       assert "grade" not in out["findings"][0]
E       AssertionError: assert 'grade' not in {'file': 'a.py', 'line': 1, 'title': 'bug', 'severity': 'Important', ...}

/home/user/wt-2211-b/plugins/superheroes/lib/tests/test_verifier_grade_c1l7.py:147: AssertionError
___________________ test_g2_an_ambiguous_id_carries_no_grade ___________________
[gw1] linux -- Python 3.12.13 /root/.cache/uv/builds-v0/.tmpmSKGYb/bin/python

    def test_g2_an_ambiguous_id_carries_no_grade():
        findings = TV._stage([TV._f("a.py", "bug", "Important", grade={"verdict": "wrong", "reason": "x"})])
        out = V.apply_verdicts(findings, [
            {"id": "v0", "verdict": "PLAUSIBLE", "reason": "x"},
            {"id": "v0", "verdict": "REFUTED", "reason": "safe"},
        ])
        assert out["ambiguous"] == ["v0"]
>       assert "grade" not in out["findings"][0]
E       AssertionError: assert 'grade' not in {'file': 'a.py', 'line': 1, 'title': 'bug', 'severity': 'Important', ...}

/home/user/wt-2211-b/plugins/superheroes/lib/tests/test_verifier_grade_c1l7.py:141: AssertionError
_______ test_a_verdict_id_resolving_to_no_staged_finding_writes_no_grade _______
[gw1] linux -- Python 3.12.13 /root/.cache/uv/builds-v0/.tmpmSKGYb/bin/python

    def test_a_verdict_id_resolving_to_no_staged_finding_writes_no_grade():
        state = RD.new_state(_fold_cfg())
        compiled, _ = RD.mechanical_compile([dict(_CONFIRMED)], None)
        RD._stage_findings(state, compiled)
        before = [dict(e) for e in state[SC.DISPOSITION_LEDGER_KEY]]
        RD._fold_verifiers(state, state["config"], {"verdicts": [
            {"id": "v99", "verdict": "PLAUSIBLE", "reason": "no such staged id"}]})
>       assert [e for e in state[SC.DISPOSITION_LEDGER_KEY]] == before
E       AssertionError: assert [{'title': 'c...ine': 1, ...}] == [{'title': 'c...ine': 1, ...}]
E         
E         At index 0 diff: {'title': 'confirmed bug', 'severity': 'Important', 'file': 'f.py', 'line': 1, 'consequence': 'a reviewer-found defect stays in the change', 'classification': 'mechanical', 'findingKey': 'f.py::confirmed bug@L1', 'raisedRound': 1, 'raisedSeq': 1, 'grade': {'verdict': 'plausible', 'reason': 'silent'}} != {'title': 'confirmed bug', 'severity': 'Important', 'file': 'f.py', 'line': 1, 'consequence': 'a reviewer-found defect stays in the change', 'classification': 'mechanical', 'findingKey': 'f.py::confirmed bug@L1', 'raisedRound': 1, 'raisedSeq': 1}
E         Use -v to get more diff

plugins/superheroes/lib/tests/test_verifier_grade_c1l7.py:321: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_verifier_grade_c1l7.py::test_g2_an_unknown_or_reasonless_verdict_carries_no_grade[verdict2]
FAILED plugins/superheroes/lib/tests/test_verifier_grade_c1l7.py::test_g2_an_unknown_or_reasonless_verdict_carries_no_grade[verdict4]
FAILED plugins/superheroes/lib/tests/test_verifier_grade_c1l7.py::test_g2_a_silent_verdict_carries_no_grade
FAILED plugins/superheroes/lib/tests/test_verifier_grade_c1l7.py::test_g2_an_unknown_or_reasonless_verdict_carries_no_grade[verdict7]
FAILED plugins/superheroes/lib/tests/test_verifier_grade_c1l7.py::test_g2_an_unknown_or_reasonless_verdict_carries_no_grade[verdict1]
FAILED plugins/superheroes/lib/tests/test_verifier_grade_c1l7.py::test_g2_an_unknown_or_reasonless_verdict_carries_no_grade[verdict3]
FAILED plugins/superheroes/lib/tests/test_verifier_grade_c1l7.py::test_g2_an_unknown_or_reasonless_verdict_carries_no_grade[verdict8]
FAILED plugins/superheroes/lib/tests/test_verifier_grade_c1l7.py::test_g2_a_silent_verdict_removes_a_grade_the_staged_copy_already_carried
FAILED plugins/superheroes/lib/tests/test_verifier_grade_c1l7.py::test_g2_an_unknown_or_reasonless_verdict_carries_no_grade[verdict6]
FAILED plugins/superheroes/lib/tests/test_verifier_grade_c1l7.py::test_g2_an_unknown_or_reasonless_verdict_carries_no_grade[verdict5]
FAILED plugins/superheroes/lib/tests/test_verifier_grade_c1l7.py::test_g2_an_unknown_or_reasonless_verdict_carries_no_grade[verdict9]
FAILED plugins/superheroes/lib/tests/test_verifier_grade_c1l7.py::test_g2_an_unmatched_verdict_leaves_the_finding_ungraded
FAILED plugins/superheroes/lib/tests/test_verifier_grade_c1l7.py::test_g2_an_ambiguous_id_carries_no_grade
FAILED plugins/superheroes/lib/tests/test_verifier_grade_c1l7.py::test_a_verdict_id_resolving_to_no_staged_finding_writes_no_grade
14 failed, 19 passed in 2.66s
```

The capture above is exactly the output received, except for the middle the harness cut; the orchestrator can
reproduce the full red with the neutralization above.

**Restore:** inverse edit, `return {"verdict": "plausible", "reason": "silent"}` back to `return None`.

**Restore receipt:** `git status --porcelain plugins/superheroes/lib/verification.py` and `git diff --stat` printed
nothing. Restored lines, `verification.py:128-130`:

```python
    # axis: a silent, reasonless, ambiguous or unknown verdict earns no grade — see bite-proof record c1l7_wo_b_verifier_grade
    if reason_text is None:
        return None
```

**Raw green:**

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
bringing up nodes...
bringing up nodes...

.................................                                        [100%]
33 passed in 6.55s
```

## G3 — the grade written onto the refuted ledger row

**Guarded element:** `plugins/superheroes/lib/round_driver.py:3829` (the `_record_grade(state, key, d.get(GRADE_FIELD))`
call in the drops loop of `_fold_verifiers`, before `_record_disposition`). Axis: the refuted ledger row carries the
`wrong` grade that closed it.

**Neutralization:** deleted the line

```python
                _record_grade(state, key, d.get(GRADE_FIELD))
```

**Raw red** (1 failed, 32 passed):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
bringing up nodes...
bringing up nodes...

...............................F.                                        [100%]
=================================== FAILURES ===================================
_ test_g1_g3_the_driver_fold_grades_every_judged_finding_and_keeps_the_refuted_one_out_of_the_fix _
[gw1] linux -- Python 3.12.13 /root/.cache/uv/builds-v0/.tmpg35bYv/bin/python

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-18/popen-gw1/test_g1_g3_the_driver_fold_gra0')

    def test_g1_g3_the_driver_fold_grades_every_judged_finding_and_keeps_the_refuted_one_out_of_the_fix(tmp_path):
        snapshots, final = _fold_drive(tmp_path)
        after_verify = snapshots[RD.P_SYNTHESIS]
        keys = {name: SC.finding_identity_key(f) for name, f in
                (("confirmed", _CONFIRMED), ("plausible", _PLAUSIBLE), ("refuted", _REFUTED))}
        ledger = _ledger(after_verify)
    
        refuted_row = ledger[keys["refuted"]]
        assert refuted_row["disposition"] == "refuted", refuted_row
>       _assert_grade(refuted_row["grade"], "wrong", _REFUTED_REASON)
                      ^^^^^^^^^^^^^^^^^^^^
E       KeyError: 'grade'

/home/user/wt-2211-b/plugins/superheroes/lib/tests/test_verifier_grade_c1l7.py:221: KeyError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_verifier_grade_c1l7.py::test_g1_g3_the_driver_fold_grades_every_judged_finding_and_keeps_the_refuted_one_out_of_the_fix
1 failed, 32 passed in 6.09s
```

**Restore:** inverse edit, re-inserted the call on the line before `_record_disposition(...)`.

**Restore receipt:** `git status --porcelain plugins/superheroes/lib/round_driver.py` and `git diff --stat` printed
nothing. Restored lines, `round_driver.py:3828-3830`:

```python
                # axis: the refuted ledger row carries the wrong grade that closed it, written before the disposition — see bite-proof record c1l7_wo_b_verifier_grade
                _record_grade(state, key, d.get(GRADE_FIELD))
                _record_disposition(state, key, "refuted", state["round"], refutedReason=reason)
```

**Raw green:**

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
bringing up nodes...
bringing up nodes...

.................................                                        [100%]
33 passed in 6.71s
```

## G4 — the seat-grade strip in `_seed_ledger_entry`

**Guarded element:** `plugins/superheroes/lib/round_driver.py:1625` (`entry.pop(GRADE_FIELD, None)` in
`_seed_ledger_entry`). Axis: a grade a seat supplied is never seeded; only the verifier fold grades.

**Neutralization:** deleted the line

```python
    entry.pop(GRADE_FIELD, None)
```

**Raw red** (2 failed, 31 passed):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
bringing up nodes...
bringing up nodes...

.........................F...F...                                        [100%]
=================================== FAILURES ===================================
______ test_g4_stage_findings_strips_a_seat_grade_from_every_staged_entry ______
[gw2] linux -- Python 3.12.13 /root/.cache/uv/builds-v0/.tmpFa9fS3/bin/python

    def test_g4_stage_findings_strips_a_seat_grade_from_every_staged_entry():
        state = RD.new_state(TRD._cfg())
        compiled, _ = RD.mechanical_compile([dict(_CONFIRMED, grade=dict(_SEAT_GRADE))], None)
        assert compiled[0].get("grade") == _SEAT_GRADE  # the premise: compile does not strip it
        RD._stage_findings(state, compiled)
>       assert all("grade" not in f for f in state["_toVerify"])
E       assert False
E        +  where False = all(<generator object test_g4_stage_findings_strips_a_seat_grade_from_every_staged_entry.<locals>.<genexpr> at 0x7fdcc1ce1150>)

/home/user/wt-2211-b/plugins/superheroes/lib/tests/test_verifier_grade_c1l7.py:266: AssertionError
___ test_g4_a_panel_seats_own_grade_reaches_neither_to_verify_nor_the_ledger ___
[gw1] linux -- Python 3.12.13 /root/.cache/uv/builds-v0/.tmpFa9fS3/bin/python

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-20/popen-gw1/test_g4_a_panel_seats_own_grad0')

    def test_g4_a_panel_seats_own_grade_reaches_neither_to_verify_nor_the_ledger(tmp_path):
        finding = dict(_CONFIRMED, grade=dict(_SEAT_GRADE))
        d = str(tmp_path)
        n = TRD._drive_to_phase(d, TRD._cfg(), TRD._responder(round1_findings=[finding]), RD.P_VERIFIERS)
        ok, state = RD.load_state(d)
        assert ok, state
        assert state["_toVerify"], state
>       assert all("grade" not in f for f in state["_toVerify"]), state["_toVerify"]
E       AssertionError: [{'classification': 'mechanical', 'consequence': 'a reviewer-found defect stays in the change', 'consequenceKind': None, 'dimension': 'code-reviewer', ...}]
E       assert False
E        +  where False = all(<generator object test_g4_a_panel_seats_own_grade_reaches_neither_to_verify_nor_the_ledger.<locals>.<genexpr> at 0x7f7e60726330>)

/home/user/wt-2211-b/plugins/superheroes/lib/tests/test_verifier_grade_c1l7.py:253: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_verifier_grade_c1l7.py::test_g4_stage_findings_strips_a_seat_grade_from_every_staged_entry
FAILED plugins/superheroes/lib/tests/test_verifier_grade_c1l7.py::test_g4_a_panel_seats_own_grade_reaches_neither_to_verify_nor_the_ledger
2 failed, 31 passed in 7.06s
```

**Restore:** inverse edit, re-inserted `entry.pop(GRADE_FIELD, None)` after the axis comment.

**Restore receipt:** `git status --porcelain plugins/superheroes/lib/round_driver.py plugins/superheroes/lib/verification.py`
and `git diff --stat` printed nothing. Restored lines, `round_driver.py:1624-1626`:

```python
    # axis: a grade a seat supplied is never seeded; only the verifier fold grades — see bite-proof record c1l7_wo_b_verifier_grade
    entry.pop(GRADE_FIELD, None)
    entry.pop(session_contract.RAISED_SEQ_FIELD, None)
```

**Raw green:**

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
bringing up nodes...
bringing up nodes...

.................................                                        [100%]
33 passed in 3.52s
```
